#ifndef LEDS_H
#define LEDS_H

#include "config.h"
#include <Arduino.h>

enum LedMode {
  LED_MODE_RAINBOW,
  LED_MODE_BPM,
  LED_MODE_CONFETTI,
  LED_MODE_JUGGLE,
  LED_MODE_WHITE,
  LED_MODE_OFF,
  LED_MODE_COUNT
};

void initLeds();
void updateLeds();
void setLedMode(LedMode mode);
void cycleLedMode();
void showLedVolumeBar(int percent, bool isUp);
void setMuteFlash(bool on);
void setButtonPress(int buttonIdx);
void setLedsColor(int r, int g, int b);

#endif
