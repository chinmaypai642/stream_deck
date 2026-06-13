#include "config.h"
#include "inputs.h"
#include "leds.h"
#include <Arduino.h>

volatile int8_t encoderPos = 0;
volatile int8_t lastEncoderState = 0;

#define ENC_BUT_DEBOUNCE_MS  50
#define LONG_PRESS_TIME      800
byte encButStableState = HIGH;
byte encButLastRawState = HIGH;
unsigned long encButLastChangeMs = 0;
unsigned long encButDownTime = 0;
bool longPressFired = false;

#define BTN_LONG_PRESS_MS 600
#define BTN_DEBOUNCE_MS   50

const int btnPins[BUTTON_COUNT] = { BTN_1, BTN_2, BTN_3, BTN_4, BTN_5 };
bool btnPressed[BUTTON_COUNT] = { false };
bool btnLastRawState[BUTTON_COUNT] = { false };
unsigned long btnLastDebounceTime[BUTTON_COUNT] = { 0 };
unsigned long btnPressStart[BUTTON_COUNT] = { 0 };
bool btnLongFired[BUTTON_COUNT] = { false };

unsigned long lastInterruptTime = 0;

void IRAM_ATTR readEncoderISR() {
  unsigned long interruptTime = millis();
  if (interruptTime - lastInterruptTime < 1) return;
  lastInterruptTime = interruptTime;

  byte a = digitalRead(ENC_A);
  byte b = digitalRead(ENC_B);
  int8_t currentState = (a << 1) | b;

  if (currentState != lastEncoderState) {
    if ((lastEncoderState == 0 && currentState == 1) ||
        (lastEncoderState == 1 && currentState == 3) ||
        (lastEncoderState == 3 && currentState == 2) ||
        (lastEncoderState == 2 && currentState == 0)) {
      encoderPos++;
    }
    else if ((lastEncoderState == 0 && currentState == 2) ||
             (lastEncoderState == 2 && currentState == 3) ||
             (lastEncoderState == 3 && currentState == 1) ||
             (lastEncoderState == 1 && currentState == 0)) {
      encoderPos--;
    }
    lastEncoderState = currentState;
  }
}

void initInputs() {
  Serial.println(F("D:InputsInit"));
  pinMode(ENC_A, INPUT_PULLUP);
  pinMode(ENC_B, INPUT_PULLUP);
  pinMode(ENC_BUT, INPUT_PULLUP);

  byte a = digitalRead(ENC_A);
  byte b = digitalRead(ENC_B);
  lastEncoderState = (a << 1) | b;

  attachInterrupt(digitalPinToInterrupt(ENC_A), readEncoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_B), readEncoderISR, CHANGE);

  for (int i = 0; i < BUTTON_COUNT; i++) {
    pinMode(btnPins[i], INPUT);
    btnLastRawState[i] = (digitalRead(btnPins[i]) == HIGH);
  }
}

void checkEncoderStep() {
  if (encoderPos >= 2) {
#if INVERT_ENCODER_DIRECTION
    Serial.println(F("ENC:-1"));
#else
    Serial.println(F("ENC:+1"));
#endif
    encoderPos = 0;
  } else if (encoderPos <= -2) {
#if INVERT_ENCODER_DIRECTION
    Serial.println(F("ENC:+1"));
#else
    Serial.println(F("ENC:-1"));
#endif
    encoderPos = 0;
  }
}

void readEncoderButton() {
  byte raw = digitalRead(ENC_BUT);
  if (raw != encButLastRawState) {
    encButLastChangeMs = millis();
    encButLastRawState = raw;
  }
  if ((millis() - encButLastChangeMs) > ENC_BUT_DEBOUNCE_MS) {
    if (raw != encButStableState) {
      encButStableState = raw;
      if (encButStableState == LOW) {
        encButDownTime = millis();
        longPressFired = false;
      } else {
        if (!longPressFired) {
           Serial.println(F("CLICK:short"));
        }
      }
    }
  }
  if (encButStableState == LOW && !longPressFired) {
    if ((millis() - encButDownTime) > LONG_PRESS_TIME) {
      longPressFired = true;
      Serial.println(F("CLICK:long"));
    }
  }
}

void readButtons() {
  for (int i = 0; i < BUTTON_COUNT; i++) {
    bool rawReading = (digitalRead(btnPins[i]) == HIGH);
    if (rawReading != btnLastRawState[i]) {
      btnLastDebounceTime[i] = millis();
      btnLastRawState[i] = rawReading;
    }
    if ((millis() - btnLastDebounceTime[i]) > BTN_DEBOUNCE_MS) {
      if (rawReading && !btnPressed[i]) {
        btnPressed[i] = true;
        btnPressStart[i] = millis();
        btnLongFired[i] = false;
        setButtonPress(i);
      }
      if (!rawReading && btnPressed[i]) {
        btnPressed[i] = false;
        if (!btnLongFired[i]) {
          Serial.print(F("BTN:")); Serial.println(i + 1);
        }
      }
      if (rawReading && btnPressed[i] && !btnLongFired[i]) {
        if (millis() - btnPressStart[i] > BTN_LONG_PRESS_MS) {
          btnLongFired[i] = true;
          Serial.print(F("BTNL:")); Serial.println(i + 1);
        }
      }
    }
  }
}

void updateInputs() {
  checkEncoderStep();
  readEncoderButton();
  readButtons();
}
