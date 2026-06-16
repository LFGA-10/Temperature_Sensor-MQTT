#!/usr/bin/env python3
"""
PC-Side Serial-to-MQTT Bridge
------------------------------
Reads temperature readings from the Arduino Uno serial port and 
publishes them to an MQTT broker on a VPS.

Requirements:
    pip install pyserial paho-mqtt==1.6.1

Usage:
    python pc_monitor.py [--port COM_PORT] [--broker BROKER_ADDRESS] [--topic TOPIC]
"""

import utils.transport
import utils.session
import sys
import time
import argparse
import serial
import serial.tools.list_ports
import paho.mqtt.client as mqtt

def parse_arguments():
    parser = argparse.ArgumentParser(description="Temperature Display and MQTT Monitoring Bridge")
    parser.add_argument(
        "--port", 
        type=str, 
        default=None, 
        help="Serial port of Arduino (e.g., COM3 on Windows, /dev/ttyACM0 on Linux). Auto-detected if not specified."
    )
    parser.add_argument(
        "--baud", 
        type=int, 
        default=9600, 
        help="Baud rate matching Arduino's Serial.begin (default: 9600)"
    )
    parser.add_argument(
        "--broker", 
        type=str, 
        default="test.mosquitto.org", 
        help="MQTT Broker hostname/IP address (default: test.mosquitto.org)"
    )
    parser.add_argument(
        "--port-mqtt", 
        type=int, 
        default=1883, 
        help="MQTT Broker port (default: 1883)"
    )
    parser.add_argument(
        "--topic", 
        type=str, 
        default="sensor/arduino/temperature", 
        help="MQTT Topic to publish temperature values to (default: sensor/arduino/temperature)"
    )
    return parser.parse_args()

def auto_detect_port(requested_port):
    """
    Finds the active serial port. If requested_port is provided, returns it.
    Otherwise, lists available COM ports and chooses or prompts the user.
    """
    if requested_port:
        return requested_port
        
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("[-] Error: No serial ports detected!")
        print("    Ensure the Arduino Uno is plugged into your PC's USB port.")
        sys.exit(1)
        
    if len(ports) == 1:
        detected = ports[0].device
        print(f"[+] Auto-detected single serial port: {detected} ({ports[0].description})")
        return detected
        
    print("\n[*] Multiple serial ports found:")
    for idx, port in enumerate(ports):
        print(f"  [{idx + 1}] {port.device} - {port.description}")
        
    if not sys.stdin.isatty():
        # Fallback if running in non-interactive environment
        fallback = ports[0].device
        print(f"[!] Non-interactive environment. Selecting first port: {fallback}")
        return fallback
        
    while True:
        try:
            choice = input(f"Select COM port (1-{len(ports)}) [default: 1]: ").strip()
            if not choice:
                return ports[0].device
            val = int(choice)
            if 1 <= val <= len(ports):
                return ports[val - 1].device
            print(f"[-] Invalid choice. Please select 1 to {len(ports)}.")
        except ValueError:
            print("[-] Please enter a valid number.")

def on_connect(client, userdata, flags, rc):
    """Callback for when the client receives a CONNACK response from the broker."""
    if rc == 0:
        print("[+] MQTT: Successfully connected to broker!")
    else:
        print(f"[-] MQTT: Connection failed with result code {rc}")

def main():
    args = parse_arguments()
    
    # 1. Detect and establish Serial Connection
    com_port = auto_detect_port(args.port)
    print(f"[*] Opening Serial port {com_port} at {args.baud} baud...")
    
    try:
        # We set a timeout of 1.0 second so that the read loop is responsive to Ctrl+C
        ser = serial.Serial(com_port, args.baud, timeout=1.0)
        # Standard Arduino resets upon DTR connection; wait 2s for bootloader to finish
        print("[*] Waiting 2 seconds for Arduino reset...")
        time.sleep(2)
        print("[+] Serial connection established.")
    except Exception as e:
        print(f"[-] Serial Error: Could not open port {com_port}.\n    Details: {e}")
        sys.exit(1)
        
    # 2. Setup MQTT Client
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    
    print(f"[*] Connecting to MQTT Broker at {args.broker}:{args.port_mqtt}...")
    try:
        mqtt_client.connect(args.broker, args.port_mqtt, keepalive=60)
        # Start the background loop to process network events/reconnects
        mqtt_client.loop_start()
    except Exception as e:
        print(f"[-] MQTT Error: Failed to connect to broker.\n    Details: {e}")
        ser.close()
        sys.exit(1)
        
    # 3. Read and publish loop
    print("\n" + "="*70)
    print(f" Monitoring Temperature on {com_port} -> Publishing to MQTT: {args.broker}")
    print(f" Topic: {args.topic}")
    print(" Press Ctrl+C to stop the monitor.")
    print("="*70)
    print(f"{'Timestamp':<20} | {'Raw Serial Data':<20} | {'Parsed Temp (°C)':<18} | {'MQTT Status':<12}")
    print("-"*70)
    
    try:
        while True:
            try:
                # Read line from Serial port
                line = ser.readline().decode('utf-8', errors='ignore').strip()
            except (serial.SerialException, OSError) as e:
                print(f"\n[-] Serial Connection Error: {e}")
                print("    Please check:")
                print("    1. The Arduino board is firmly connected to USB.")
                print("    2. No other program (e.g. Arduino IDE Serial Monitor) is using COM8.")
                break
            
            # Skip empty lines (often returned on serial timeouts)
            if not line:
                continue
                
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            
            try:
                # Try to parse the temperature string from Arduino
                temp_value = float(line)
                
                # Publish the temperature to the MQTT Broker (QoS 1 guarantees delivery)
                publish_info = mqtt_client.publish(args.topic, payload=f"{temp_value:.2f}", qos=1)
                
                # Display in real-time
                print(f"{timestamp:<20} | {line:<20} | {temp_value:<18.2f} | Published")
                
            except ValueError:
                # Print non-numeric messages sent by Arduino (e.g. "Initializing...")
                print(f"{timestamp:<20} | {line:<20} | {'[Info text]':<18} | Skipped")
                
    except KeyboardInterrupt:
        print("\n\n[*] Monitoring stopped by user.")
    finally:
        # Cleanup resource handles
        print("[*] Cleaning up connections...")
        ser.close()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        print("[+] Done. Exited clean.")

if __name__ == "__main__":
    main()
