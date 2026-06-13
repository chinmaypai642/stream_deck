#include "hid_controls.h"

#ifndef ARDUINO_USB_MODE
#warning This ESP32 board/core does not expose native USB HID.
void initHidControls() {}
bool sendHidCommand(const String &command) { return false; }
#elif ARDUINO_USB_MODE == 1
#warning Select USB-OTG / TinyUSB mode for USB HID on ESP32-S3.
void initHidControls() {}
bool sendHidCommand(const String &command) { return false; }
#else

#include "USB.h"
#include "USBHIDConsumerControl.h"

USBHIDConsumerControl ConsumerControl;

void initHidControls() {
  ConsumerControl.begin();
  USB.begin();
}

bool sendHidCommand(const String &command) {
  uint16_t usage = 0;

  if (command == "PLAY_PAUSE") {
    usage = CONSUMER_CONTROL_PLAY_PAUSE;
  } else if (command == "NEXT") {
    usage = CONSUMER_CONTROL_SCAN_NEXT;
  } else if (command == "PREVIOUS") {
    usage = CONSUMER_CONTROL_SCAN_PREVIOUS;
  } else if (command == "MUTE") {
    usage = CONSUMER_CONTROL_MUTE;
  } else if (command == "VOLUME_UP") {
    usage = CONSUMER_CONTROL_VOLUME_INCREMENT;
  } else if (command == "VOLUME_DOWN") {
    usage = CONSUMER_CONTROL_VOLUME_DECREMENT;
  } else if (command == "SEEK_FORWARD_5") {
    usage = CONSUMER_CONTROL_FAST_FORWARD;
  } else if (command == "SEEK_BACK_5") {
    usage = CONSUMER_CONTROL_REWIND;
  }

  if (!usage) {
    return false;
  }

  ConsumerControl.press(usage);
  delay(28);
  ConsumerControl.release();
  return true;
}

#endif
