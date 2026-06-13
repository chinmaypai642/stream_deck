# Deck

This version is for **your hardware only**:

- ESP32-S3 Super Mini
- 5 capacitive touch buttons
- 1 rotary encoder with push button
- 1.3 inch OLED display

There are **no LEDs, no LED strip, no voice changer, and no extra macro deck hardware** needed.

## What It Does

- Touch 1: Play / Pause
- Touch 2: Next track
- Touch 3: Previous track
- Touch 4: Seek forward 5 seconds
- Touch 5: Seek back 5 seconds
- Rotate knob: Spotify volume up/down
- Press knob: Spotify mute/unmute, or opens Spotify if Spotify is closed
- Hold knob: app launcher menu
- OLED: shows Spotify title, artist, progress, volume, app menu, queue, and idle animations
- Next/previous track: vinyl transition animation

Spotify can be in the foreground, background, or minimized.

Spotify still needs to be open.

## App Launcher

Hold the rotary encoder button to open the app launcher on the OLED.

Rotate the knob to choose:

```text
1 Spotify
2 Terminal Admin
3 Files
4 Opera
5 WhatsApp
6 Codex
```

Press the rotary encoder button once to open the selected app.
Hold the rotary encoder button again to close the app launcher.

## Animation Controls

When the deck is idle, long-press touch buttons 1-5 to choose idle animations:

```text
1 Flames
2 Waveform
3 Big clock
4 Bouncing vinyl
5 Data rain
```

When music is active:

```text
Long press touch 2 -> cycle now-playing screen style
Long press touch 4 -> real Spotify queue browser
```

The first time you open the queue browser, your laptop will open a Spotify login
page. Approve it once. After that, the companion stores a local token file and
the queue browser should open normally.

Queue browser controls:

```text
Rotate knob -> scroll queue
Press knob  -> play selected queue item directly
Hold knob   -> close queue browser
Touch 5     -> close queue browser
```

## Upload This Firmware

Open this file in Arduino IDE:

```text
C:\Users\sally\Desktop\deck_project\firmware\deck_s3\deck_s3.ino
```

Arduino IDE settings:

```text
Board: ESP32S3 Dev Module
USB CDC On Boot: Enabled
```

Then upload.

## Wiring

```text
OLED SDA  -> GPIO7
OLED SCL  -> GPIO8

Encoder CLK -> GPIO1
Encoder DT  -> GPIO2
Encoder SW  -> GPIO3

Touch 1 Play/Pause -> GPIO11
Touch 2 Next       -> GPIO10
Touch 3 Previous   -> GPIO12
Touch 4 +5 sec     -> GPIO9
Touch 5 -5 sec     -> GPIO13
```

## After Uploading

Close Arduino Serial Monitor if it is open.

Then double-click:

```text
C:\Users\sally\Desktop\deck_project\Start_Deck.bat
```

That starts the Deck companion.

For normal use without keeping a window open, double-click:

```text
C:\Users\sally\Desktop\deck_project\Start_Deck_Hidden.bat
```

That starts the companion silently in the background.

## Windows Startup

I already installed startup mode for you.

That means after Windows logs in, the packaged Deck app should start silently in the background. You do **not** need to keep PowerShell open.

The companion also creates a small **Deck** icon in the Windows system tray.
Right-click it for:

```text
Open Spotify
Open Queue Browser
Reconnect Deck
Open Project Folder
Exit Deck
```

The packaged app is:

```text
C:\Users\sally\Desktop\deck_project\dist\Deck.exe
```

If you edit the Python companion later and want to rebuild the app, double-click:

```text
C:\Users\sally\Desktop\deck_project\Build_Deck_App.bat
```

## Before Uploading Again

If you want to upload new firmware later, first double-click:

```text
C:\Users\sally\Desktop\deck_project\Stop_Deck.bat
```

This frees the ESP32 COM port for Arduino IDE.
