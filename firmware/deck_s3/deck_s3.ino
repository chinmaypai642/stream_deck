/*  PROJECT: DECK S3 - Wired PC Control Panel
    BOARD: ESP32-S3
*/

#include "config.h"
#include "display.h"
#include "hid_controls.h"
#include "inputs.h"
#include "leds.h"
#include <Arduino.h>

void setup() {
  // ESP32-S3 Native USB can be tricky.
  // We use Serial for communication.
  Serial.begin(115200);
  randomSeed((uint32_t)esp_random());

  // Wait for USB connection
  unsigned long t = millis();
  while (!Serial && millis() - t < 3000) {
    delay(10);
  }

  initDisplay();
  initHidControls();
  initLeds();
  initInputs();

  delay(500);
  showOverlay("RUBEN DECK");
  Serial.println(F("READY"));
  setLedMode(LED_MODE_RAINBOW);
}

String cmdBuffer = "";
unsigned long lastSerialTime = 0;
#define SERIAL_TIMEOUT_MS 3000

void loop() {
  updateInputs();
  updateLeds();
  updateDisplay();

  // Serial command processing
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdBuffer.length() > 0) {
        lastSerialTime = millis();
        cmdBuffer.trim();
        processCommand(cmdBuffer);
        cmdBuffer = "";
      }
    } else {
      cmdBuffer += c;
      if (cmdBuffer.length() > 256)
        cmdBuffer = "";
    }
  }

  // Small yield to keep S3 happy
  yield();
}

void processCommand(String cmd) {
  if (cmd.startsWith("LED:")) {
    String data = cmd.substring(4);
    if (data == "OFF")
      setLedMode(LED_MODE_OFF);
    else if (data == "ON" || data == "RAINBOW")
      setLedMode(LED_MODE_RAINBOW);
    else if (data == "BPM")
      setLedMode(LED_MODE_BPM);
    else if (data == "CONFETTI")
      setLedMode(LED_MODE_CONFETTI);
    else if (data == "JUGGLE")
      setLedMode(LED_MODE_JUGGLE);
    else if (data == "WHITE")
      setLedMode(LED_MODE_WHITE);
    else if (data == "CYCLE") {
      cycleLedMode();
    } else if (data == "MUTE")
      setMuteFlash(true);
    else if (data == "UNMUTE")
      setMuteFlash(false);
    else if (data.startsWith("VOL,")) {
      char dir;
      int pct;
      if (sscanf(data.c_str(), "VOL,%c,%d", &dir, &pct) == 2)
        showLedVolumeBar(pct, dir == '+');
    }
  } else if (cmd.startsWith("MEDIA:")) {
    String data = cmd.substring(6);
    if (data == "STOP") {
      clearNowPlaying();
      return;
    }
    int s1 = data.indexOf('|');
    int s2 = data.indexOf('|', s1 + 1);
    int s3 = data.indexOf('|', s2 + 1);
    if (s1 > 0 && s2 > 0 && s3 > 0) {
      setNowPlaying(data.substring(0, s1), data.substring(s1 + 1, s2),
                    data.substring(s2 + 1, s3).toInt(),
                    data.substring(s3 + 1).toInt());
    }
  } else if (cmd.startsWith("STATUS:")) {
    int status = cmd.substring(7).toInt();
    setPlaybackStatus(status == 1);
  } else if (cmd.startsWith("OLED:")) {
    String data = cmd.substring(5);
    if (data.startsWith("VOL:")) {
      int c1 = data.indexOf(',');
      int c2 = data.indexOf(',', c1 + 1);
      if (c1 > 0 && c2 > 0) {
        setVolumeStatus(data.substring(4, c1),
                        data.substring(c1 + 1, c2).toInt(),
                        data.substring(c2 + 1) == "1");
      }
    } else if (data.startsWith("APPMENU:")) {
      String menuData = data.substring(8);
      if (menuData == "OFF") {
        clearAppMenu();
      } else {
        setAppMenuIndex(menuData.toInt());
      }
    } else if (data.startsWith("IDLEMENU:")) {
      String menuData = data.substring(9);
      if (menuData == "OFF") {
        clearIdleMenu();
      } else {
        setIdleMenuIndex(menuData.toInt());
      }
    } else if (data.startsWith("NPSTYLEMENU:")) {
      String menuData = data.substring(12);
      if (menuData == "OFF") {
        clearNowPlayingStyleMenu();
      } else {
        setNowPlayingStyleMenuIndex(menuData.toInt());
      }
    } else if (data.startsWith("QUEUE:")) {
      String queueData = data.substring(6);
      if (queueData == "OFF") {
        clearQueueMenu();
      } else {
        setQueueMenuFromPayload(queueData);
      }
    } else if (data.startsWith("IDLE:")) {
      setIdleAnimation(data.substring(5).toInt());
    } else if (data.startsWith("NPSTYLE:")) {
      setNowPlayingStyle(data.substring(8).toInt());
    } else if (data.startsWith("TRANSITION:")) {
      runTrackTransition(data.substring(11));
    } else if (data.startsWith("MODE:")) {
      setModeText(data.substring(5));
    } else if (data.startsWith("FOOTER:")) {
      setFooterText(data.substring(7));
    } else if (data.startsWith("CLOCK:")) {
      setClockText(data.substring(6));
    } else if (data == "CLEAR") {
      showOverlay("");
    } else {
      showOverlay(data);
    }
  } else if (cmd.startsWith("IMG:")) {
    int firstColon = cmd.indexOf(':');
    int secondColon = cmd.indexOf(':', firstColon + 1);
    if (firstColon != -1 && secondColon != -1) {
      int chunkIdx = cmd.substring(firstColon + 1, secondColon).toInt();
      String hex = cmd.substring(secondColon + 1);
      receiveImageChunk(chunkIdx, hex);
    }
  } else if (cmd.startsWith("HID:")) {
    String data = cmd.substring(4);
    bool ok = sendHidCommand(data);
    Serial.print(F("HID:"));
    Serial.print(data);
    Serial.println(ok ? F(":OK") : F(":FAIL"));
  }

  // Connection watchdog: if no serial for 10s, clear display to eyes
  if (millis() - lastSerialTime > SERIAL_TIMEOUT_MS) {
    if (lastSerialTime != 0) { // Only if we once had a connection
      clearNowPlaying();
    }
  }
}
