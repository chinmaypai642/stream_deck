#ifndef DISPLAY_H
#define DISPLAY_H

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>

void initDisplay();
void updateDisplay();
void setNowPlaying(String song, String artist, int position, int duration);
void clearNowPlaying();
void setModeText(String text);
void setFooterText(String text);
void setClockText(String text);
void setVolumeStatus(String target, int volume, bool muted);
void setPlaybackStatus(bool playing);
void setAppMenuIndex(int index);
void clearAppMenu();
void setIdleMenuIndex(int index);
void clearIdleMenu();
void setNowPlayingStyleMenuIndex(int index);
void clearNowPlayingStyleMenu();
void setIdleAnimation(int index);
void setNowPlayingStyle(int index);
void runTrackTransition(String direction);
void setQueueMenuFromPayload(String payload);
void clearQueueMenu();
void receiveImageChunk(int chunkIdx, String hex);
void drawIdleEyes();
void showOverlay(String text);

#endif
