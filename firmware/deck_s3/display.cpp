#include "display.h"
#include "config.h"
#include "leds.h"
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <string.h>
#include "bitmaps.h"

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
#define OLED_ADDRESS  0x3C

// S3 SH1106G driver
Adafruit_SH1106G *display;

bool oledDirty = true;
unsigned long lastOledUpdate = 0;

String npSong = "";
String npArtist = "";
int npPosition = 0;
int npDuration = 0;
int npScrollOffset = 0;
unsigned long npScrollTimer = 0;
int npArtScrollOffset = 0;
unsigned long npArtScrollTimer = 0;
#define NP_SCROLL_MS 400
bool npPlaying = false;
bool hasAlbumArt = false;
uint8_t albumArt[512]; // 64x64 1-bit bitmap

int trackedVolume = 50;
bool trackedMuted = false;
String trackedTarget = "master";

String overlayText = "";
unsigned long overlayStart = 0;
bool showingOverlay = false;
#define OVERLAY_MS 2000

bool displayShowingVolumeBar = false;
unsigned long displayVolumeBarStart = 0;
#define VOLUME_BAR_DISP_MS 1600

int idleAnimationMode = 0;
int nowPlayingStyle = 0;
#define IDLE_ANIMATION_COUNT 6
#define NOW_PLAYING_STYLE_COUNT 3

bool appMenuActive = false;
int appMenuIndex = 0;
const char *APP_MENU_ITEMS[] = {
  "Spotify",
  "Terminal Admin",
  "Files",
  "Opera",
  "WhatsApp",
  "Codex",
  "Idle Mode"
};
#define APP_MENU_COUNT 7

bool idleMenuActive = false;
int idleMenuIndex = 0;
const char *IDLE_MENU_ITEMS[] = {
  "Waveform",
  "Flames",
  "Clock",
  "Vinyl",
  "Data Rain",
  "Blinking Eyes"
};

bool npStyleMenuActive = false;
int npStyleMenuIndex = 0;
const char *NP_STYLE_MENU_ITEMS[] = {
  "Vinyl",
  "Minimal",
  "Big Title"
};

bool queueMenuActive = false;
int queueSelectedRow = 0;
int queueAbsoluteIndex = 0;
int queueTotal = 0;
String queueRows[5] = {"", "", "", "", ""};
#define QUEUE_VISIBLE_ROWS 5

String currentModeText = "Ruben Live";
String currentFooterText = "RUBEN LIVE";
String currentClockText = "00:00";

void initDisplay() {
  Wire.begin(SDA_PIN, SCL_PIN);
  
  if (display == nullptr) {
    display = new Adafruit_SH1106G(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
  }
  
  if (!display->begin(OLED_ADDRESS, true)) {
    if (!display->begin(0x3D, true)) {
      Serial.println(F("ERROR:OLED_FAIL"));
      return;
    }
  }
  
  display->setContrast(255);
  display->setRotation(0);
  display->clearDisplay();
  display->setTextColor(SH110X_WHITE);
  display->display();
}

String formatTime(int seconds) {
  int h = seconds / 3600;
  int m = (seconds % 3600) / 60;
  int s = seconds % 60;
  String r = "";
  if (h > 0) {
    r += String(h) + ":";
    if (m < 10) r += "0";
  }
  r += String(m) + ":";
  if (s < 10) r += "0";
  r += String(s);
  return r;
}

void drawIdleFlames() {
  display->clearDisplay();

  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(F("RUBEN DECK"));

  display->setCursor(128 - (currentClockText.length() * 6), 0);
  display->print(currentClockText);

  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  for (int i = 0; i < 21; i++) {
    int x = i * 6;
    int wave = (int)(sin((millis() / 130.0f) + i * 0.65f) * 5);
    int centerLift = 18 - abs(i - 10);
    int h = constrain(9 + wave + random(0, 14) + centerLift / 3, 4, 28);
    int topY = 52 - h;
    display->fillRect(x, topY + 4, 4, h - 4, SH110X_WHITE);
    display->fillTriangle(x, topY + 5, x + 3, topY + 5, x + 2, topY, SH110X_WHITE);
    if ((i + millis() / 110) % 5 == 0 && topY > 14) {
      display->drawPixel(x + 2, topY - 5, SH110X_WHITE);
    }
  }
  
  display->setTextSize(1);
  display->drawLine(0, 51, 128, 51, SH110X_WHITE);
  display->fillRect(0, 52, 128, 12, SH110X_BLACK);
  display->setCursor(37, 56);
  display->print(F("RUBEN LIVE"));

  display->display();
}

void drawIdleWaveform() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(F("WAVEFORM"));
  display->setCursor(98, 0);
  display->print(currentClockText);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  int mid = 33;
  for (int x = 0; x < 128; x += 3) {
    float a = (millis() / 150.0f) + x * 0.12f;
    int y = mid + (int)(sin(a) * 12) + (int)(sin(a * 0.43f) * 5);
    display->drawPixel(x, y, SH110X_WHITE);
    display->drawPixel(x + 1, y + 1, SH110X_WHITE);
    if (x > 0) display->drawLine(x - 3, mid, x, y, SH110X_WHITE);
  }

  display->drawLine(0, 51, 128, 51, SH110X_WHITE);
  display->setCursor(34, 56);
  display->print(F("RUBEN WAVE"));
  display->display();
}

void drawIdleBigClock() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(F("RUBEN TIME"));
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);
  display->setTextSize(3);
  int x = (128 - currentClockText.length() * 18) / 2;
  display->setCursor(x >= 0 ? x : 0, 23);
  display->print(currentClockText);
  display->setTextSize(1);
  display->drawLine(0, 51, 128, 51, SH110X_WHITE);
  display->setCursor(37, 56);
  display->print(F("RUBEN LIVE"));
  display->display();
}

void drawIdleBouncingVinyl() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(F("VINYL IDLE"));
  display->setCursor(98, 0);
  display->print(currentClockText);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  int x = 18 + abs((int)((millis() / 18) % 92) - 46);
  int y = 31 + (int)(sin(millis() / 170.0f) * 6);
  display->drawCircle(x, y, 13, SH110X_WHITE);
  display->drawCircle(x, y, 8, SH110X_WHITE);
  display->fillCircle(x, y, 3, SH110X_WHITE);
  display->drawLine(x - 9, y - 9, x + 9, y + 9, SH110X_WHITE);
  display->drawLine(x + 9, y - 9, x - 9, y + 9, SH110X_WHITE);

  display->drawLine(0, 51, 128, 51, SH110X_WHITE);
  display->setCursor(28, 56);
  display->print(F("BOUNCING DISC"));
  display->display();
}

void drawIdleRain() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(F("RUBEN RAIN"));
  display->setCursor(98, 0);
  display->print(currentClockText);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  for (int x = 0; x < 128; x += 8) {
    int offset = (millis() / 80 + x * 3) % 44;
    for (int y = 10 + offset; y > 10; y -= 11) {
      display->drawFastVLine(x, y, 5, SH110X_WHITE);
      display->drawPixel(x + 2, y + 2, SH110X_WHITE);
    }
  }

  display->drawLine(0, 51, 128, 51, SH110X_WHITE);
  display->setCursor(34, 56);
  display->print(F("DATA RAIN"));
  display->display();
}

void drawIdleBlinkingEyes() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(F("RUBEN EYES"));
  display->setCursor(98, 0);
  display->print(currentClockText);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  int blinkPhase = (millis() / 120) % 38;
  bool closed = blinkPhase == 0 || blinkPhase == 1 || blinkPhase == 2;
  int look = (int)(sin(millis() / 900.0f) * 3);

  int leftX = 38;
  int rightX = 90;
  int eyeY = 31;

  if (closed) {
    display->drawFastHLine(leftX - 16, eyeY, 32, SH110X_WHITE);
    display->drawFastHLine(rightX - 16, eyeY, 32, SH110X_WHITE);
    display->drawPixel(leftX - 18, eyeY - 1, SH110X_WHITE);
    display->drawPixel(leftX + 18, eyeY - 1, SH110X_WHITE);
    display->drawPixel(rightX - 18, eyeY - 1, SH110X_WHITE);
    display->drawPixel(rightX + 18, eyeY - 1, SH110X_WHITE);
  } else {
    display->drawRoundRect(leftX - 18, eyeY - 10, 36, 21, 9, SH110X_WHITE);
    display->drawRoundRect(rightX - 18, eyeY - 10, 36, 21, 9, SH110X_WHITE);
    display->fillCircle(leftX + look, eyeY, 5, SH110X_WHITE);
    display->fillCircle(rightX + look, eyeY, 5, SH110X_WHITE);
    display->fillCircle(leftX + look + 2, eyeY - 2, 1, SH110X_BLACK);
    display->fillCircle(rightX + look + 2, eyeY - 2, 1, SH110X_BLACK);
  }

  display->drawLine(0, 51, 128, 51, SH110X_WHITE);
  display->setCursor(31, 56);
  display->print(F("BLINKING EYES"));
  display->display();
}

void drawIdleEyes() {
  switch (idleAnimationMode) {
    case 0:
      drawIdleWaveform();
      break;
    case 1:
      drawIdleFlames();
      break;
    case 2:
      drawIdleBigClock();
      break;
    case 3:
      drawIdleBouncingVinyl();
      break;
    case 4:
      drawIdleRain();
      break;
    case 5:
      drawIdleBlinkingEyes();
      break;
    default:
      drawIdleWaveform();
      break;
  }
}

static void drawMusicNote(int x, int y) {
  // Left note head
  display->fillRect(x, y + 5, 3, 2, SH110X_WHITE);
  // Right note head
  display->fillRect(x + 5, y + 4, 3, 2, SH110X_WHITE);
  // Left stem
  display->drawFastVLine(x + 2, y + 1, 5, SH110X_WHITE);
  // Right stem
  display->drawFastVLine(x + 7, y, 5, SH110X_WHITE);
  // Beam
  display->drawFastHLine(x + 2, y, 6, SH110X_WHITE);
  display->drawFastHLine(x + 2, y + 1, 6, SH110X_WHITE);
}

static void drawScrollText(int x, int y, String text, int maxChars, int &scrollOffset, unsigned long &scrollTimer) {
  display->setTextSize(1);
  String toPrint = text;
  if ((int)text.length() > maxChars) {
    if (millis() - scrollTimer > NP_SCROLL_MS) {
      scrollTimer = millis();
      scrollOffset++;
      if (scrollOffset > (int)text.length() - maxChars + 3)
        scrollOffset = 0;
    }
    toPrint = text.substring(scrollOffset, scrollOffset + maxChars);
  } else {
    scrollOffset = 0;
  }
  
  display->setCursor(x, y);
  display->print(toPrint);
}

void drawMinimalNowPlaying() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(npPlaying ? F("PLAYING") : F("PAUSED"));
  display->setCursor(98, 0);
  display->print(currentClockText);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  drawScrollText(0, 17, npSong, 21, npScrollOffset, npScrollTimer);
  drawScrollText(0, 28, npArtist, 21, npArtScrollOffset, npArtScrollTimer);

  display->drawRect(0, 42, 128, 7, SH110X_WHITE);
  if (npDuration > 0) {
    int w = (int)((long)npPosition * 126 / npDuration);
    if (w > 126) w = 126;
    display->fillRect(1, 43, w, 5, SH110X_WHITE);
  }

  display->setCursor(0, 55);
  display->print(formatTime(npPosition));
  String durStr = formatTime(npDuration);
  display->setCursor(128 - durStr.length() * 6, 55);
  display->print(durStr);
  display->display();
}

void drawBigTitleNowPlaying() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(npPlaying ? F("NOW PLAYING") : F("PAUSED"));
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  display->setTextSize(2);
  String title = npSong;
  if (title.length() > 10) title = title.substring(0, 10);
  int tx = (128 - title.length() * 12) / 2;
  display->setCursor(tx >= 0 ? tx : 0, 18);
  display->print(title);

  display->setTextSize(1);
  String artist = npArtist;
  if (artist.length() > 20) artist = artist.substring(0, 20);
  int ax = (128 - artist.length() * 6) / 2;
  display->setCursor(ax >= 0 ? ax : 0, 39);
  display->print(artist);

  display->drawRect(8, 53, 112, 5, SH110X_WHITE);
  if (npDuration > 0) {
    int w = (int)((long)npPosition * 110 / npDuration);
    if (w > 110) w = 110;
    display->fillRect(9, 54, w, 3, SH110X_WHITE);
  }
  display->display();
}

void drawNowPlaying() {
  display->clearDisplay();

  // If nothing is playing, show the idle eyes
  if (npSong == "") {
    drawIdleEyes();
    return;
  }

  if (nowPlayingStyle == 1) {
    drawMinimalNowPlaying();
    return;
  }
  if (nowPlayingStyle == 2) {
    drawBigTitleNowPlaying();
    return;
  }

  // Draw Top Header
  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(currentModeText);

  // Clock in Top Right
  display->setCursor(128 - (currentClockText.length() * 6), 0);
  display->print(currentClockText);

  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  // Dynamic layout parameters based on whether hours are shown
  bool showHours = (npDuration >= 3600);

  int cx, cy, r_outer, r_groove1, r_groove2, r_label;
  int dotted_x, text_x, scroll_chars, pbar_x, pbar_w, pbar_fill_max, pbar_fill_offset;
  int slash_x1, slash_x2;
  
  if (showHours) {
    cx = 17; cy = 30;
    r_outer = 15; r_groove1 = 11; r_groove2 = 7; r_label = 4;
    dotted_x = 35;
    text_x = 37;
    scroll_chars = 15;
    pbar_x = 37; pbar_w = 87; pbar_fill_max = 83; pbar_fill_offset = 39;
    slash_x1 = 81; slash_x2 = 82;
  } else {
    cx = 24; cy = 30;
    r_outer = 18; r_groove1 = 14; r_groove2 = 10; r_label = 6;
    dotted_x = 50;
    text_x = 53;
    scroll_chars = 12;
    pbar_x = 53; pbar_w = 71; pbar_fill_max = 67; pbar_fill_offset = 55;
    slash_x1 = 87; slash_x2 = 88;
  }

  // Draw the vinyl record
  display->drawCircle(cx, cy, r_outer, SH110X_WHITE);
  display->drawCircle(cx, cy, r_groove1, SH110X_WHITE);
  display->drawCircle(cx, cy, r_groove2, SH110X_WHITE);
  display->fillCircle(cx, cy, r_label, SH110X_WHITE);
  
  // Tiny black music note in the center of the label
  if (showHours) {
    display->fillRect(cx - 1, cy + 1, 1, 1, SH110X_BLACK);
    display->drawFastVLine(cx, cy - 3, 5, SH110X_BLACK);
    display->fillRect(cx + 1, cy - 3, 1, 1, SH110X_BLACK);
  } else {
    display->fillRect(cx - 2, cy + 1, 2, 2, SH110X_BLACK);
    display->drawFastVLine(cx, cy - 4, 6, SH110X_BLACK);
    display->fillRect(cx + 1, cy - 4, 2, 2, SH110X_BLACK);
  }
  
  // Rotating shine/reflections. This freezes when Spotify is paused.
  static float shineAngle = 0;
  if (npPlaying) {
    shineAngle += 0.22f;
    if (shineAngle >= 2 * 3.14159265f) shineAngle -= 2 * 3.14159265f;
  }

  int spinnerInner = showHours ? 5 : 7;
  int spinnerOuter = showHours ? 14 : 17;

  // Four moving rim markers make the disc visibly spin on a 1-bit OLED.
  for (int i = 0; i < 4; i++) {
    float a = shineAngle + (i * 1.57079633f);
    int px = cx + (int)(spinnerOuter * cos(a));
    int py = cy + (int)(spinnerOuter * sin(a));
    display->fillCircle(px, py, 1, SH110X_WHITE);
  }

  // A black sweep across the label gives the center a turntable feel.
  int sx1 = cx + (int)(2 * cos(shineAngle));
  int sy1 = cy + (int)(2 * sin(shineAngle));
  int sx2 = cx + (int)((r_label - 1) * cos(shineAngle));
  int sy2 = cy + (int)((r_label - 1) * sin(shineAngle));
  display->drawLine(sx1, sy1, sx2, sy2, SH110X_BLACK);
  
  // Draw rotating shine lines (opposing wedges)
  for (int i = -1; i <= 1; i++) {
    float a1 = shineAngle + (i * 0.1f);
    float a2 = shineAngle + 3.14159265f + (i * 0.1f);
    
    // Line 1
    int x1 = cx + (int)(spinnerInner * cos(a1));
    int y1 = cy + (int)(spinnerInner * sin(a1));
    int x2 = cx + (int)(spinnerOuter * cos(a1));
    int y2 = cy + (int)(spinnerOuter * sin(a1));
    display->drawLine(x1, y1, x2, y2, SH110X_WHITE);
    
    // Line 2
    int x3 = cx + (int)(spinnerInner * cos(a2));
    int y3 = cy + (int)(spinnerInner * sin(a2));
    int x4 = cx + (int)(spinnerOuter * cos(a2));
    int y4 = cy + (int)(spinnerOuter * sin(a2));
    display->drawLine(x3, y3, x4, y4, SH110X_WHITE);
  }

  // Tiny tonearm on the side, just enough detail to sell the record look.
  int armBaseX = cx + r_outer + 5;
  int armBaseY = cy - r_outer + 1;
  display->drawCircle(armBaseX, armBaseY, 2, SH110X_WHITE);
  display->drawLine(armBaseX - 1, armBaseY + 2, cx + r_outer - 3, cy - 5, SH110X_WHITE);

  // Vertical dotted line in the middle area
  for (int y = 10; y < 51; y += 2) {
    display->drawPixel(dotted_x, y, SH110X_WHITE);
  }
  
  // Right side starts in the middle area
  // Song Title (Bold-like size 1, scrolls if long)
  drawScrollText(text_x, 12, npSong, scroll_chars, npScrollOffset, npScrollTimer);
  
  // Artist Name (Size 1, scrolls if long)
  display->setTextSize(1);
  int artChars = scroll_chars;
  String toPrintArtist = npArtist;
  if ((int)npArtist.length() > artChars) {
    if (millis() - npArtScrollTimer > NP_SCROLL_MS) {
      npArtScrollTimer = millis();
      npArtScrollOffset++;
      if (npArtScrollOffset > (int)npArtist.length() - artChars + 3)
        npArtScrollOffset = 0;
    }
    toPrintArtist = npArtist.substring(npArtScrollOffset, npArtScrollOffset + artChars);
  } else {
    npArtScrollOffset = 0;
  }
  display->setCursor(text_x, 21);
  display->print(toPrintArtist);
  
  // Dotted progress bar
  display->drawRect(pbar_x, 31, pbar_w, 4, SH110X_WHITE);
  if (npDuration > 0) {
    int w = (int)((long)npPosition * pbar_fill_max / npDuration);
    if (w > pbar_fill_max) w = pbar_fill_max;
    for (int i = 0; i < w; i += 2) {
      display->drawFastVLine(pbar_fill_offset + i, 32, 2, SH110X_WHITE);
    }
  }
  
  // Time indicator at bottom of right side (Y=39)
  String posStr = formatTime(npPosition);
  String durStr = formatTime(npDuration);
  display->setTextSize(1);
  display->setCursor(text_x, 39);
  display->print(posStr);
  
  // Draw premium diagonal slash divider
  display->drawLine(slash_x1, 45, slash_x2, 40, SH110X_WHITE);
  
  int durX = 128 - (durStr.length() * 6);
  display->setCursor(durX >= text_x ? durX : text_x, 39);
  display->print(durStr);

  // Draw Bottom Footer
  display->setTextSize(1);
  display->drawLine(0, 51, 128, 51, SH110X_WHITE);
  int fx = (128 - currentFooterText.length() * 6) / 2;
  display->setCursor(fx >= 0 ? fx : 0, 54);
  display->print(currentFooterText);

  display->display();
}

void drawVolumeBar() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setCursor(0, 0);
  display->print(currentModeText + " | " + trackedTarget);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  display->setTextSize(3);
  String volStr = String(trackedVolume) + "%";
  int vx = (128 - volStr.length() * 18) / 2;
  display->setCursor(vx, 15);
  display->print(volStr);

  display->drawRoundRect(4, 46, 120, 8, 3, SH110X_WHITE);
  int fw = (trackedVolume * 116) / 100;
  if (fw > 0)
    display->fillRoundRect(6, 48, fw, 4, 1, SH110X_WHITE);

  if (trackedMuted) {
    if ((millis() / 500) % 2 == 0) {
      display->fillRect(0, 15, 128, 40, SH110X_BLACK); // Clear the volume number area
      display->setTextSize(2);
      display->setCursor(25, 25);
      display->print(F("MUTED"));
    }
  }
  display->display();
}

void drawAppMenu() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setTextColor(SH110X_WHITE);
  display->setCursor(0, 0);
  display->print(F("APP LAUNCHER"));

  String page = String(appMenuIndex + 1) + "/" + String(APP_MENU_COUNT);
  display->setCursor(128 - page.length() * 6, 0);
  display->print(page);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  int first = appMenuIndex - 2;
  if (first < 0) first = 0;
  if (first > APP_MENU_COUNT - 5) first = APP_MENU_COUNT - 5;
  if (first < 0) first = 0;

  for (int row = 0; row < 5; row++) {
    int item = first + row;
    if (item >= APP_MENU_COUNT) break;

    int y = 13 + row * 10;
    bool selected = (item == appMenuIndex);
    if (selected) {
      display->fillRect(0, y - 1, 128, 9, SH110X_WHITE);
      display->setTextColor(SH110X_BLACK);
    } else {
      display->setTextColor(SH110X_WHITE);
    }

    display->setCursor(2, y);
    display->print(selected ? ">" : " ");
    display->print(item + 1);
    display->print(F(" "));
    display->print(APP_MENU_ITEMS[item]);
  }

  display->setTextColor(SH110X_WHITE);
  display->display();
}

void drawIdleMenu() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setTextColor(SH110X_WHITE);
  display->setCursor(0, 0);
  display->print(F("IDLE ANIMATION"));

  String page = String(idleMenuIndex + 1) + "/" + String(IDLE_ANIMATION_COUNT);
  display->setCursor(128 - page.length() * 6, 0);
  display->print(page);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  int first = idleMenuIndex - 2;
  if (first < 0) first = 0;
  if (first > IDLE_ANIMATION_COUNT - 5) first = IDLE_ANIMATION_COUNT - 5;
  if (first < 0) first = 0;

  for (int row = 0; row < 5; row++) {
    int item = first + row;
    if (item >= IDLE_ANIMATION_COUNT) break;

    int y = 13 + row * 10;
    bool selected = (item == idleMenuIndex);
    if (selected) {
      display->fillRect(0, y - 1, 128, 9, SH110X_WHITE);
      display->setTextColor(SH110X_BLACK);
    } else {
      display->setTextColor(SH110X_WHITE);
    }

    display->setCursor(2, y);
    display->print(selected ? ">" : " ");
    display->print(item + 1);
    display->print(F(" "));
    display->print(IDLE_MENU_ITEMS[item]);
  }

  display->setTextColor(SH110X_WHITE);
  display->display();
}

void drawNowPlayingStyleMenu() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setTextColor(SH110X_WHITE);
  display->setCursor(0, 0);
  display->print(F("NOW PLAYING STYLE"));

  String page = String(npStyleMenuIndex + 1) + "/" + String(NOW_PLAYING_STYLE_COUNT);
  display->setCursor(128 - page.length() * 6, 0);
  display->print(page);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  for (int row = 0; row < NOW_PLAYING_STYLE_COUNT; row++) {
    int y = 17 + row * 12;
    bool selected = (row == npStyleMenuIndex);
    if (selected) {
      display->fillRect(0, y - 1, 128, 9, SH110X_WHITE);
      display->setTextColor(SH110X_BLACK);
    } else {
      display->setTextColor(SH110X_WHITE);
    }

    display->setCursor(2, y);
    display->print(selected ? ">" : " ");
    display->print(row + 1);
    display->print(F(" "));
    display->print(NP_STYLE_MENU_ITEMS[row]);
  }

  display->setTextColor(SH110X_WHITE);
  display->display();
}

void drawQueueMenu() {
  display->clearDisplay();
  display->setTextSize(1);
  display->setTextColor(SH110X_WHITE);
  display->setCursor(0, 0);
  display->print(F("SPOTIFY LIST"));

  String page = String(queueAbsoluteIndex + 1) + "/" + String(queueTotal);
  if (queueTotal <= 0) page = "0/0";
  display->setCursor(128 - page.length() * 6, 0);
  display->print(page);
  display->drawLine(0, 9, 128, 9, SH110X_WHITE);

  if (queueTotal <= 0) {
    display->setCursor(18, 28);
    display->print(F("No liked songs"));
    display->display();
    return;
  }

  for (int row = 0; row < QUEUE_VISIBLE_ROWS; row++) {
    int y = 13 + row * 10;
    bool selected = (row == queueSelectedRow);
    if (selected) {
      display->fillRect(0, y - 1, 128, 9, SH110X_WHITE);
      display->setTextColor(SH110X_BLACK);
    } else {
      display->setTextColor(SH110X_WHITE);
    }

    String item = queueRows[row];
    if (item.length() > 19) item = item.substring(0, 19);
    display->setCursor(2, y);
    display->print(selected ? ">" : " ");
    display->print(item);
  }

  display->setTextColor(SH110X_WHITE);
  display->display();
}


void updateDisplay() {
  if (queueMenuActive) {
    if (millis() - lastOledUpdate < 100) return;
    lastOledUpdate = millis();
    drawQueueMenu();
    return;
  }

  if (idleMenuActive) {
    if (millis() - lastOledUpdate < 100) return;
    lastOledUpdate = millis();
    drawIdleMenu();
    return;
  }

  if (npStyleMenuActive) {
    if (millis() - lastOledUpdate < 100) return;
    lastOledUpdate = millis();
    drawNowPlayingStyleMenu();
    return;
  }

  if (appMenuActive) {
    if (millis() - lastOledUpdate < 100) return;
    lastOledUpdate = millis();
    drawAppMenu();
    return;
  }

  if (displayShowingVolumeBar) {
    if (millis() - displayVolumeBarStart < VOLUME_BAR_DISP_MS) {
      drawVolumeBar();
      return;
    }
    displayShowingVolumeBar = false;
  }

  if (showingOverlay) {
    if (millis() - overlayStart < OVERLAY_MS) {
      display->clearDisplay();
      int len = overlayText.length();
      int sz = (len > 10) ? 1 : 2;
      display->setTextSize(sz);
      int cw = (sz == 1) ? 6 : 12;
      int ch = (sz == 1) ? 8 : 16;
      int x = (128 - len * cw) / 2;
      display->setCursor(x >= 0 ? x : 0, (64 - ch) / 2);
      display->print(overlayText);
      display->display();
      return;
    }
    showingOverlay = false;
  }

  if (millis() - lastOledUpdate < 100) return;
  lastOledUpdate = millis();

  if (npSong == "") {
    drawIdleEyes();
  } else {
    drawNowPlaying();
  }
}

void setNowPlaying(String song, String artist, int position, int duration) {
  if (song != npSong) { 
    npScrollOffset = 0; npScrollTimer = millis(); 
    npArtScrollOffset = 0; npArtScrollTimer = millis();
  }
  npSong = song;
  npArtist = artist;
  npPosition = position;
  npDuration = duration;
}

void clearNowPlaying() {
  npSong = ""; npArtist = ""; npPosition = 0; npDuration = 0;
  hasAlbumArt = false;
}

void setModeText(String text) { currentModeText = text; }
void setFooterText(String text) { currentFooterText = text; }
void setClockText(String text) { currentClockText = text; }

void setVolumeStatus(String target, int volume, bool muted) {
  trackedTarget = target;
  trackedVolume = volume;
  trackedMuted = muted;
  displayShowingVolumeBar = true;
  displayVolumeBarStart = millis();
}

void showOverlay(String text) {
  overlayText = text;
  overlayStart = millis();
  showingOverlay = true;
}

void setPlaybackStatus(bool playing) {
  npPlaying = playing;
}

void setIdleAnimation(int index) {
  idleAnimationMode = constrain(index, 0, IDLE_ANIMATION_COUNT - 1);
  showingOverlay = false;
  displayShowingVolumeBar = false;
  idleMenuActive = false;
}

void setNowPlayingStyle(int index) {
  nowPlayingStyle = constrain(index, 0, NOW_PLAYING_STYLE_COUNT - 1);
  showingOverlay = false;
  displayShowingVolumeBar = false;
  npStyleMenuActive = false;
}

void drawTransitionDisc(int x, int y, int r) {
  display->drawCircle(x, y, r, SH110X_WHITE);
  display->drawCircle(x, y, r - 5, SH110X_WHITE);
  display->fillCircle(x, y, 4, SH110X_WHITE);
  display->drawLine(x - r + 3, y - 3, x + r - 3, y + 3, SH110X_WHITE);
  display->drawLine(x - r + 3, y + 3, x + r - 3, y - 3, SH110X_WHITE);
}

void runTrackTransition(String direction) {
  direction.toUpperCase();
  bool isNext = direction != "PREVIOUS";
  const char *label = isNext ? "NEXT" : "PREVIOUS";

  for (int frame = 0; frame < 12; frame++) {
    display->clearDisplay();
    display->setTextSize(2);
    int labelWidth = strlen(label) * 12;
    display->setCursor((128 - labelWidth) / 2, 0);
    display->print(label);
    display->drawLine(0, 19, 128, 19, SH110X_WHITE);

    int outX = isNext ? 32 - frame * 6 : 32 + frame * 6;
    int inX = isNext ? 150 - frame * 7 : -22 + frame * 7;
    int lift = frame < 6 ? frame : 12 - frame;

    if (outX > -22 && outX < 150) drawTransitionDisc(outX, 40 - lift, 15);
    if (frame > 4 && inX > -22 && inX < 150) drawTransitionDisc(inX, 40, 15);

    if (frame == 6) {
      display->setTextSize(1);
      display->setCursor(42, 55);
      display->print(F("loading"));
    }

    display->display();
    delay(35);
  }
}

void setAppMenuIndex(int index) {
  appMenuIndex = constrain(index, 0, APP_MENU_COUNT - 1);
  appMenuActive = true;
  idleMenuActive = false;
  npStyleMenuActive = false;
  showingOverlay = false;
  displayShowingVolumeBar = false;
}

void clearAppMenu() {
  appMenuActive = false;
}

void setIdleMenuIndex(int index) {
  idleMenuIndex = constrain(index, 0, IDLE_ANIMATION_COUNT - 1);
  idleMenuActive = true;
  appMenuActive = false;
  queueMenuActive = false;
  npStyleMenuActive = false;
  showingOverlay = false;
  displayShowingVolumeBar = false;
}

void clearIdleMenu() {
  idleMenuActive = false;
}

void setNowPlayingStyleMenuIndex(int index) {
  npStyleMenuIndex = constrain(index, 0, NOW_PLAYING_STYLE_COUNT - 1);
  npStyleMenuActive = true;
  appMenuActive = false;
  idleMenuActive = false;
  queueMenuActive = false;
  showingOverlay = false;
  displayShowingVolumeBar = false;
}

void clearNowPlayingStyleMenu() {
  npStyleMenuActive = false;
}

void setQueueMenuFromPayload(String payload) {
  int firstPipe = payload.indexOf('|');
  String header = firstPipe >= 0 ? payload.substring(0, firstPipe) : payload;

  int c1 = header.indexOf(',');
  int c2 = header.indexOf(',', c1 + 1);
  if (c1 < 0 || c2 < 0) return;

  queueSelectedRow = constrain((int)header.substring(0, c1).toInt(), 0, QUEUE_VISIBLE_ROWS - 1);
  queueAbsoluteIndex = (int)header.substring(c1 + 1, c2).toInt();
  queueTotal = (int)header.substring(c2 + 1).toInt();
  if (queueAbsoluteIndex < 0) queueAbsoluteIndex = 0;
  if (queueTotal < 0) queueTotal = 0;

  for (int i = 0; i < QUEUE_VISIBLE_ROWS; i++) {
    queueRows[i] = "";
  }

  String rest = firstPipe >= 0 ? payload.substring(firstPipe + 1) : "";
  for (int i = 0; i < QUEUE_VISIBLE_ROWS; i++) {
    int nextPipe = rest.indexOf('|');
    if (nextPipe < 0) {
      queueRows[i] = rest;
      break;
    }
    queueRows[i] = rest.substring(0, nextPipe);
    rest = rest.substring(nextPipe + 1);
  }

  queueMenuActive = true;
  appMenuActive = false;
  idleMenuActive = false;
  npStyleMenuActive = false;
  showingOverlay = false;
  displayShowingVolumeBar = false;
}

void clearQueueMenu() {
  queueMenuActive = false;
}

void receiveImageChunk(int chunkIdx, String hex) {
  Serial.print(F("D:Chunk ")); Serial.print(chunkIdx); 
  Serial.print(F(" Data: ")); Serial.println(hex.substring(0, 16) + "...");
  if (chunkIdx < 0 || chunkIdx >= 8) return; 
  if (hex.length() < 128) return; // 64 bytes * 2 chars/byte
  hasAlbumArt = true;
  const char* p = hex.c_str();
  for (int i = 0; i < 64; i++) {
    char b[3] = {p[i*2], p[i*2+1], 0};
    albumArt[chunkIdx * 64 + i] = (uint8_t)strtol(b, NULL, 16);
  }
}
