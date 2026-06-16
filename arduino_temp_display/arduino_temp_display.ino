#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const char* displayName = "SANDRA";
const int TEMP_SENSOR_PIN = A0;
const int TEMP_VCC_PIN = 8;

LiquidCrystal_I2C lcd(0x27, 16, 2);

unsigned long lastTempUpdate = 0;
const unsigned long TEMP_UPDATE_INTERVAL = 1000;

unsigned long lastScrollTime = 0;
const unsigned long SCROLL_INTERVAL = 350;

int scrollPos = 0;
int nameLength = 0;

void setup() {
  Serial.begin(9600);
  
  pinMode(TEMP_VCC_PIN, OUTPUT);
  digitalWrite(TEMP_VCC_PIN, HIGH);
  
  lcd.init();
  lcd.backlight();
  
  nameLength = strlen(displayName);
  
  if (nameLength <= 16) {
    lcd.setCursor(0, 0);
    lcd.print(displayName);
    for (int i = nameLength; i < 16; i++) {
      lcd.print(" ");
    }
  } else {
    updateLCDScroll();
  }
  
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");
}

void loop() {
  unsigned long currentMillis = millis();
  
  if (nameLength > 16) {
    if (currentMillis - lastScrollTime >= SCROLL_INTERVAL) {
      lastScrollTime = currentMillis;
      updateLCDScroll();
    }
  }
  
  if (currentMillis - lastTempUpdate >= TEMP_UPDATE_INTERVAL) {
    lastTempUpdate = currentMillis;
    float temperature = readTemperatureCelsius();
    updateLCDTempDisplay(temperature);
    Serial.println(temperature, 2);
  }
}

float readTemperatureCelsius() {
  long rawSum = 0;
  const int NUM_READINGS = 10;
  for (int i = 0; i < NUM_READINGS; i++) {
    rawSum += analogRead(TEMP_SENSOR_PIN);
    delay(10);
  }
  float rawAverage = (float)rawSum / NUM_READINGS;
  float tempC = rawAverage * (5.0 * 100.0 / 1024.0);
  return tempC;
}

void updateLCDTempDisplay(float temp) {
  lcd.setCursor(0, 1);
  lcd.print("Temp: ");
  lcd.print(temp, 1);
  lcd.print((char)223);
  lcd.print("C");
  lcd.print("    ");
}

void updateLCDScroll() {
  int paddedLen = nameLength + 4;
  char displayBuf[17];
  for (int i = 0; i < 16; i++) {
    int idx = (scrollPos + i) % paddedLen;
    if (idx < nameLength) {
      displayBuf[i] = displayName[idx];
    } else {
      displayBuf[i] = ' ';
    }
  }
  displayBuf[16] = '\0';
  lcd.setCursor(0, 0);
  lcd.print(displayBuf);
  scrollPos = (scrollPos + 1) % paddedLen;
}
