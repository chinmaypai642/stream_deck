# Deck

A custom ESP32-S3 control deck for Spotify and desktop shortcuts. The deck uses capacitive touch buttons, a rotary encoder, and a 1.3 inch OLED display to control playback, browse playlists, launch apps, and show animated now-playing and idle screens.

The hardware enclosure, faceplate, knob, and internal component layout were designed from scratch in SolidWorks.

## Features

- Spotify playback controls that work while Spotify is foregrounded, minimized, or running in the background
- USB HID media-control fallback for play/pause, next, previous, and seek controls
- Rotary encoder for volume, menu navigation, and item selection
- OLED now-playing screen with title, artist, progress, volume, and playback state
- Animated OLED screens including waveform, flames, clock, vinyl, data rain, and blinking eyes
- Vinyl-style transition animation for next and previous track actions
- Playlist browser with Liked Songs pinned at the top
- Windows companion app with a system tray icon
- Hidden startup mode so the companion can run without keeping PowerShell open
- Custom CAD files for the enclosure and knob

## Hardware

- ESP32-S3 Super Mini
- 5 capacitive touch buttons
- Rotary encoder with push button
- 1.3 inch SH1106 OLED display
- Custom 3D printed enclosure
- Custom 3D printed volume knob

There are no LEDs, LED strips, voice changer modules, or extra macro deck parts required for this build.

## Controls

| Input | Action |
| --- | --- |
| Touch 1 | Seek back 5 seconds |
| Touch 2 | Previous track |
| Touch 3 | Play / pause |
| Touch 4 | Next track |
| Touch 5 | Seek forward 5 seconds |
| Rotate knob | Volume up / down or menu scroll |
| Short-press knob | Mute / unmute or select menu item |
| Long-press knob | Open app launcher |
| Long-press touch 2 | Change now-playing animation style |
| Long-press touch 4 | Open Spotify playlist browser |

## App Launcher

Long-press the rotary encoder button to open the app launcher on the OLED. Rotate the knob to move through the list and press the knob once to open the selected app.

Default launcher items:

```text
1 Spotify
2 Terminal Admin
3 Files
4 Opera
5 WhatsApp
6 Codex
7 Idle Mode
```

## Spotify Playlist Browser

Long-press touch 4 in Spotify mode to open the playlist browser.

```text
Rotate knob -> scroll
Press knob  -> open playlist or play selected song
Touch 5     -> back / exit
```

Liked Songs is pinned at the top of the playlist list. Other Spotify playlists are loaded through the Spotify Web API.

The first Spotify API use may open a browser login page. After approval, the companion stores a local `spotify_token.json` file. This token file is ignored by Git and should not be uploaded.

## OLED Screens

Idle animations:

```text
Waveform
Flames
Clock
Vinyl
Data Rain
Blinking Eyes
```

Now-playing screens include a compact track display and animated vinyl-style playback views. When playback is paused for more than a few seconds, the deck can return to idle mode.

## Wiring

```text
OLED SDA  -> GPIO7
OLED SCL  -> GPIO8

Encoder CLK -> GPIO1
Encoder DT  -> GPIO2
Encoder SW  -> GPIO3

Touch 1 -> GPIO11
Touch 2 -> GPIO10
Touch 3 -> GPIO12
Touch 4 -> GPIO9
Touch 5 -> GPIO13
```

## Firmware Setup

Open the firmware in Arduino IDE:

```text
firmware/deck_s3/deck_s3.ino
```

Recommended Arduino IDE settings:

```text
Board: ESP32S3 Dev Module
USB CDC On Boot: Enabled
USB Mode: USB-OTG / TinyUSB if using native USB HID
```

Required Arduino libraries:

```text
Adafruit GFX Library
Adafruit SH110X
Adafruit BusIO
```

Upload the sketch to the ESP32-S3 after closing any Serial Monitor that may be using the COM port.

## Windows Companion Setup

Install the Python dependencies:

```powershell
pip install -r requirements_spotify_deck.txt
```

Start the companion with a visible console:

```text
Start_Deck.bat
```

Start it silently in the background:

```text
Start_Deck_Hidden.bat
```

Stop the companion before uploading firmware again:

```text
Stop_Deck.bat
```

The companion creates a Deck system tray icon with shortcuts for opening Spotify, reconnecting the deck, opening the project folder, and exiting the companion.

## Optional Startup Install

To make the companion start automatically when Windows logs in, run:

```text
Install_Deck_Startup.bat
```

To remove it from Windows startup:

```text
Uninstall_Deck_Startup.bat
```

## Spotify Developer Setup

For playlist browsing and richer Spotify status, create a Spotify Developer app and enable the Web API. Add a local redirect URI in the Spotify dashboard, then add the client ID to the companion configuration.

The companion uses these Spotify scopes:

```text
user-read-playback-state
user-read-currently-playing
user-modify-playback-state
user-library-read
playlist-read-private
playlist-read-collaborative
```

Do not commit `spotify_token.json`, logs, build folders, or packaged binaries with personal data.

## Project Structure

```text
firmware/deck_s3/          ESP32-S3 firmware
deck_project_cad_files/    SolidWorks, STEP, and STL design files
spotify_deck_win.py        Windows companion app
requirements_spotify_deck.txt
Start_Deck.bat
Start_Deck_Hidden.bat
Stop_Deck.bat
Install_Deck_Startup.bat
Uninstall_Deck_Startup.bat
```

## CAD Files

The repository includes CAD files for the enclosure, bottom plate, capacitive touch plates, and volume knob. The design was iterated around real component fit, wiring space, 3D printing tolerances, and PLA shrinkage.

## Notes

This is a personal hardware project, so pin mappings, app paths, and Spotify setup may need small changes for another computer or deck layout.
