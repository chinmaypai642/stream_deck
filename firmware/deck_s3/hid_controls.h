#pragma once

#include <Arduino.h>

void initHidControls();
bool sendHidCommand(const String &command);
