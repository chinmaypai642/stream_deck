#ifndef CONFIG_H
#define CONFIG_H

// DECK Identity
#define DEVICE_NAME "Deck"

// Board Pins (ESP32-S3 Super Mini + 5 TTP223 capacitive buttons)
// Touch mapping:
// BTN_1 = Play/Pause, BTN_2 = Next, BTN_3 = Previous,
// BTN_4 = +5 sec, BTN_5 = -5 sec
#define BTN_1 11
#define BTN_2 10
#define BTN_3 12
#define BTN_4 9
#define BTN_5 13

#define ENC_A 1
#define ENC_B 2
#define ENC_BUT 3

// Matches the direction from the earlier working SpotifyDeck_USBHID sketch.
// Change to 0 only if clockwise lowers the Spotify volume.
#define INVERT_ENCODER_DIRECTION 1

#define SDA_PIN 7
#define SCL_PIN 8

#define BUTTON_COUNT 5

#endif
