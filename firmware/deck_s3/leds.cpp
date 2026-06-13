#include "leds.h"
#include <Arduino.h>

LedMode currentMode = LED_MODE_OFF;

void initLeds() {
  Serial.println(F("D:LedsDisabled"));
}

void updateLeds() {}

void setLedMode(LedMode mode) {
  currentMode = mode;
}

void cycleLedMode() {
  currentMode = (LedMode)((currentMode + 1) % LED_MODE_COUNT);
}

void showLedVolumeBar(int percent, bool isUp) {
  (void)percent;
  (void)isUp;
}

void setMuteFlash(bool on) {
  (void)on;
}

void setButtonPress(int buttonIdx) {
  (void)buttonIdx;
}

void setLedsColor(int r, int g, int b) {
  (void)r;
  (void)g;
  (void)b;
}
