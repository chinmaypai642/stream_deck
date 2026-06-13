"""
Deck Windows companion.

This is the laptop-side bridge for:
- ESP32-S3 Super Mini
- 5 TTP223 capacitive buttons
- 1 rotary encoder with push switch
- 1.3 inch 128x64 OLED

The ESP32 sends simple serial events:
  BTN:1  Seek back 5 seconds
  BTN:2  Previous
  BTN:3  Play/Pause
  BTN:4  Next
  BTN:5  Seek forward 5 seconds
  ENC:+1 Spotify volume up
  ENC:-1 Spotify volume down
  CLICK:short Spotify mute/unmute

This app runs quietly in the background and controls Spotify even when Spotify
is minimized or behind another window. Spotify must still be open.
"""

import asyncio
import base64
import ctypes
import hashlib
import http.server
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from ctypes import wintypes
from pathlib import Path

import serial
import serial.tools.list_ports
import pystray
from comtypes import CoInitialize
from PIL import Image, ImageDraw
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation, ISimpleAudioVolume
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus


SERIAL_BAUD = 115200
SPOTIFY_PROCESS = "spotify.exe"
SPOTIFY_APP_HINT = "spotify"
VOLUME_STEP = 0.05
SEEK_STEP_MS = 5000
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    if APP_DIR.name.lower() == "dist":
        APP_DIR = APP_DIR.parent
else:
    APP_DIR = Path(__file__).resolve().parent

LOG_PATH = APP_DIR / "spotify_deck.log"
LOCK_PORT = 49631
SPOTIFY_CLIENT_ID = "23690a9a484041a68decf948a766422c"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8765/callback"
SPOTIFY_SCOPES = "user-read-playback-state user-read-currently-playing user-modify-playback-state user-library-read playlist-read-private playlist-read-collaborative"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_API_TIMEOUT_SECONDS = 5
TOKEN_PATH = APP_DIR / "spotify_token.json"
SPOTIFY_APP_ID = r"SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"
OPERA_APP_ID = r"OperaSoftware.OperaGXWebBrowser.1747169853"
WHATSAPP_APP_ID = r"5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"
CODEX_APP_ID = r"shell:AppsFolder\OpenAI.Codex_2p2nqsd0c76g0!App"
CODEX_RAW_APP_ID = r"OpenAI.Codex_2p2nqsd0c76g0!App"
CODEX_EXE_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Packages" / "OpenAI.Codex_2p2nqsd0c76g0" / "LocalCache" / "Local" / "OpenAI" / "Codex" / "bin" / "codex.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin" / "7dea4a003bc76627" / "codex.exe",
]
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_MAXIMIZE = 3
SW_RESTORE = 9
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SetActiveWindow.argtypes = [wintypes.HWND]
user32.SetActiveWindow.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

serial_port = None
lock_socket = None
main_loop = None
tray_icon = None
last_command_times = {}
last_title = None
last_artist = None
last_position = None
last_duration = None
last_status = None
last_volume_status = None
last_clock_min = -1
last_touch_long_time = 0
last_media_timeout_log = 0
token_refresh_block_until = 0
paused_since = None
deck_idle = True
active_app_mode = "spotify"
manual_idle_requested = False
app_menu_active = False
app_menu_index = 0
idle_menu_active = False
idle_menu_index = 0
np_style_menu_active = False
np_style_menu_index = 0
liked_songs_menu_active = False
liked_songs_index = 0
liked_songs_items = []
playlist_browser_active = False
playlist_browser_level = "playlists"
playlist_index = 0
playlist_items = []
playlist_track_index = 0
playlist_track_items = []
idle_animation_index = 0
now_playing_style_index = 0
APP_MENU_ITEMS = [
    "Spotify",
    "Terminal Admin",
    "Files",
    "Opera",
    "WhatsApp",
    "Codex",
    "Idle Mode",
]
IDLE_MENU_ITEMS = [
    "Waveform",
    "Flames",
    "Clock",
    "Vinyl",
    "Data Rain",
    "Blinking Eyes",
]
NP_STYLE_MENU_ITEMS = [
    "Vinyl",
    "Minimal",
    "Big Title",
]
PLAYLIST_MENU_NAMES = []


def log(message):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {message}"
    try:
        print(line)
    except Exception:
        pass
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def acquire_single_instance_lock():
    global lock_socket
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        lock_socket.bind(("127.0.0.1", LOCK_PORT))
        lock_socket.listen(1)
        return True
    except OSError:
        return False


def get_window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def get_window_process_name(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return Path(buffer.value).name.lower()
    finally:
        kernel32.CloseHandle(handle)
    return ""


def visible_windows():
    windows = []

    @WNDENUMPROC
    def enum_proc(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            title = get_window_title(hwnd).strip()
            process_name = get_window_process_name(hwnd)
            if title or process_name:
                windows.append((hwnd, title, process_name))
        return True

    user32.EnumWindows(enum_proc, 0)
    return windows


def send_alt_unlock():
    user32.keybd_event(0x12, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.05)


def send_key(vk_code):
    user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(vk_code, 0, 2, 0)


def send_media_key_for_command(command):
    media_keys = {
        "PREVIOUS": VK_MEDIA_PREV,
        "PLAY_PAUSE": VK_MEDIA_PLAY_PAUSE,
        "NEXT": VK_MEDIA_NEXT,
    }
    vk = media_keys.get(command)
    if not vk:
        return False
    send_key(vk)
    return True


def focus_window(hwnd, maximize=False):
    foreground = user32.GetForegroundWindow()
    current_thread = kernel32.GetCurrentThreadId()
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0

    send_alt_unlock()
    user32.ShowWindow(hwnd, SW_MAXIMIZE if maximize else SW_RESTORE)
    attached_target = False
    attached_foreground = False
    try:
        if target_thread and target_thread != current_thread:
            attached_target = bool(user32.AttachThreadInput(current_thread, target_thread, True))
        if foreground_thread and foreground_thread != current_thread:
            attached_foreground = bool(user32.AttachThreadInput(current_thread, foreground_thread, True))

        user32.BringWindowToTop(hwnd)
        user32.SetActiveWindow(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    finally:
        if attached_target:
            user32.AttachThreadInput(current_thread, target_thread, False)
        if attached_foreground:
            user32.AttachThreadInput(current_thread, foreground_thread, False)

    return bool(user32.GetForegroundWindow() == hwnd)


def focus_visible_window(process_names=None, title_keywords=None, maximize=False):
    process_names = {Path(name).name.lower() for name in (process_names or [])}
    process_names.update({Path(name).stem.lower() + ".exe" for name in (process_names or [])})
    title_keywords = [word.lower() for word in (title_keywords or [])]

    for hwnd, title, process_name in visible_windows():
        title_lower = title.lower()
        if process_name in process_names or any(word in title_lower for word in title_keywords):
            focused = focus_window(hwnd, maximize=maximize)
            log(f"Focused visible window: {title or '<untitled>'} ({process_name}) {'ok' if focused else 'requested'}")
            return True
    return False


def powershell_array(values):
    escaped = [str(value).replace("'", "''") for value in values]
    return "@(" + ",".join(f"'{value}'" for value in escaped) + ")"


def powershell_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def launch_or_switch_app(target):
    name = target["name"]
    raw_process_names = target.get("processes", [])
    process_names = [Path(p).stem for p in raw_process_names]
    title_keywords = target.get("titles", [])
    app_id = target.get("app_id", "")
    shell_uri = target.get("shell_uri", "")
    exe = target.get("exe", "")
    maximize = bool(target.get("maximize", False))
    launch_if_running = bool(target.get("launch_if_running", False))
    special = target.get("special", "")
    ps_maximize = "$true" if maximize else "$false"
    ps_launch_if_running = "$true" if launch_if_running else "$false"

    if focus_visible_window(raw_process_names, title_keywords, maximize=maximize):
        return "ok"

    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$sig = @'
using System;
using System.Runtime.InteropServices;
public class DeckLauncherWin {{
  [DllImport("user32.dll")]
  public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
}}
'@
try {{ Add-Type $sig -ErrorAction SilentlyContinue }} catch {{ }}
$ws = New-Object -ComObject WScript.Shell
$names = {powershell_array(process_names)}
$titles = {powershell_array(title_keywords)}
$shouldMaximize = {ps_maximize}
$launchIfRunning = {ps_launch_if_running}

function Unlock-Foreground {{
  try {{
    [DeckLauncherWin]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 25
    [DeckLauncherWin]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 70
  }} catch {{ }}
}}

function Maximize-Active {{
  if (-not $shouldMaximize) {{ return }}
  try {{
    [DeckLauncherWin]::keybd_event(0x5B, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 20
    [DeckLauncherWin]::keybd_event(0x26, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 20
    [DeckLauncherWin]::keybd_event(0x26, 0, 2, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 20
    [DeckLauncherWin]::keybd_event(0x5B, 0, 2, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 80
  }} catch {{ }}
}}

function Try-Activate {{
  foreach ($title in $titles) {{
    Unlock-Foreground
    if ($ws.AppActivate($title)) {{
      Start-Sleep -Milliseconds 120
      Maximize-Active
      exit 0
    }}
  }}

  foreach ($name in $names) {{
    $proc = Get-Process -Name $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($proc) {{
      Unlock-Foreground
      if ($ws.AppActivate([int]$proc.Id)) {{
        Start-Sleep -Milliseconds 120
        Maximize-Active
        exit 0
      }}
      return 10
    }}
  }}
  return 1
}}

$state = Try-Activate
if ($state -eq 10 -and -not $launchIfRunning) {{ exit 10 }}
if ($state -eq 0) {{ exit 0 }}

$special = {powershell_string(special)}
if ($special -eq 'terminal_admin') {{
  Start-Process wt -Verb RunAs -ErrorAction SilentlyContinue
  if (-not $?) {{ Start-Process powershell -Verb RunAs }}
  exit 0
}}

$shellUri = {powershell_string(shell_uri)}
$appId = {powershell_string(app_id)}
$exePath = {powershell_string(exe)}

if ($shellUri.Length -gt 0) {{
  Start-Process $shellUri
}} elseif ($appId.Length -gt 0) {{
  Start-Process explorer.exe -ArgumentList ('shell:AppsFolder\\' + $appId)
}} elseif ($exePath.Length -gt 0) {{
  if ($shouldMaximize) {{
    Start-Process -FilePath $exePath -WindowStyle Maximized
  }} else {{
    Start-Process -FilePath $exePath
  }}
}} else {{
  exit 2
}}

Start-Sleep -Milliseconds 1800
$state = Try-Activate
if ($state -eq 10) {{ exit 0 }}
exit 0
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            log(f"Launcher switched/opened {name}.")
            return "ok"
        if result.returncode == 10:
            log(f"Launcher found {name} running but Windows blocked focus; not opening duplicate.")
            return "already_open"
        log(f"Launcher failed for {name}: exit {result.returncode}")
        return "failed"
    except Exception as exc:
        log(f"Launcher exception for {name}: {exc}")
        return "failed"


def focus_existing_process_with_appactivate(process_names=None, title_keywords=None, maximize=False):
    process_bases = []
    for name in process_names or []:
        base = Path(name).stem
        if base:
            process_bases.append(base)
    ps_maximize = "$true" if maximize else "$false"

    script = f"""
$sig = @'
using System;
using System.Runtime.InteropServices;
public class WinFocus {{
  [DllImport("user32.dll")]
  public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
}}
'@
try {{ Add-Type $sig -ErrorAction SilentlyContinue }} catch {{ }}
$ws = New-Object -ComObject WScript.Shell
$unlock = {{
  try {{
    [WinFocus]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 30
    [WinFocus]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 80
  }} catch {{ }}
}}
$maximizeWindow = {{
  try {{
    [WinFocus]::keybd_event(0x5B, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 20
    [WinFocus]::keybd_event(0x26, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 20
    [WinFocus]::keybd_event(0x26, 0, 2, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 20
    [WinFocus]::keybd_event(0x5B, 0, 2, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 80
  }} catch {{ }}
}}
$shouldMaximize = {ps_maximize}
$names = {powershell_array(process_bases)}
foreach ($name in $names) {{
  $procs = @(Get-Process -Name $name -ErrorAction SilentlyContinue | Select-Object -First 1)
  if ($procs.Count -gt 0) {{
    foreach ($p in $procs) {{
      try {{
        & $unlock
        if ($ws.AppActivate([int]$p.Id)) {{
          Start-Sleep -Milliseconds 80
          & $unlock
          $ws.AppActivate([int]$p.Id) | Out-Null
          if ($shouldMaximize) {{ & $maximizeWindow }}
          exit 0
        }}
      }} catch {{ }}
    }}
    exit 0
  }}
}}
$titles = {powershell_array(title_keywords or [])}
foreach ($title in $titles) {{
  try {{
    & $unlock
    if ($ws.AppActivate($title)) {{
      Start-Sleep -Milliseconds 80
      & $unlock
      $ws.AppActivate($title) | Out-Null
      if ($shouldMaximize) {{ & $maximizeWindow }}
      exit 0
    }}
  }} catch {{ }}
}}
exit 1
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            log("Focused or found existing app process.")
            return True
    except Exception as exc:
        log(f"AppActivate focus failed: {exc}")
    return False


def focus_existing_window(process_names=None, title_keywords=None, maximize=False):
    process_names = {name.lower() for name in (process_names or [])}
    title_keywords = [word.lower() for word in (title_keywords or [])]
    windows = visible_windows()

    for hwnd, title, process_name in windows:
        if process_name in process_names:
            focus_window(hwnd)
            if maximize:
                user32.ShowWindow(hwnd, 3)
            log(f"Focused existing window: {title} ({process_name})")
            return True

    for hwnd, title, process_name in windows:
        title_lower = title.lower()
        if any(word in title_lower for word in title_keywords):
            focus_window(hwnd)
            if maximize:
                user32.ShowWindow(hwnd, 3)
            log(f"Focused existing window by title: {title} ({process_name})")
            return True

    return focus_existing_process_with_appactivate(process_names, title_keywords, maximize=maximize)



def clean_text(value, fallback):
    value = (value or "").replace("|", "-").replace("\r", " ").replace("\n", " ").strip()
    if not value:
        value = fallback
    return "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in value)[:96]


def b64url(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def load_token():
    if not TOKEN_PATH.exists():
        return None
    try:
        with TOKEN_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log(f"Token load failed: {exc}")
        return None


def save_token(token):
    token["expires_at"] = time.time() + int(token.get("expires_in", 3600)) - 60
    try:
        with TOKEN_PATH.open("w", encoding="utf-8") as f:
            json.dump(token, f)
    except Exception as exc:
        log(f"Token save failed: {exc}")


def post_spotify_token(data):
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(
        SPOTIFY_TOKEN_URL,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=SPOTIFY_API_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def refresh_spotify_token(token):
    global token_refresh_block_until
    if time.time() < token_refresh_block_until:
        return None
    if not token or not token.get("refresh_token"):
        return None
    try:
        refreshed = post_spotify_token({
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id": SPOTIFY_CLIENT_ID,
        })
        if "refresh_token" not in refreshed:
            refreshed["refresh_token"] = token["refresh_token"]
        save_token(refreshed)
        token_refresh_block_until = 0
        return refreshed
    except Exception as exc:
        token_refresh_block_until = time.time() + 60
        log(f"Spotify token refresh failed: {exc}")
        return None


def run_spotify_login():
    verifier = b64url(os.urandom(64))
    challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = secrets.token_urlsafe(18)
    result = {}

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            result["code"] = params.get("code", [None])[0]
            result["state"] = params.get("state", [None])[0]
            result["error"] = params.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h2>Deck connected.</h2>"
                b"<p>You can close this tab and return to the deck.</p></body></html>"
            )

        def log_message(self, format, *args):
            return

    server = http.server.HTTPServer(("127.0.0.1", 8765), CallbackHandler)
    server.timeout = 180

    query = urllib.parse.urlencode({
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SPOTIFY_SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "state": state,
    })
    webbrowser.open(f"{SPOTIFY_AUTH_URL}?{query}")
    server.handle_request()
    server.server_close()

    if result.get("error"):
        raise RuntimeError(f"Spotify login error: {result['error']}")
    if result.get("state") != state or not result.get("code"):
        raise RuntimeError("Spotify login timed out or state mismatch")

    token = post_spotify_token({
        "grant_type": "authorization_code",
        "code": result["code"],
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "code_verifier": verifier,
    })
    save_token(token)
    return token


def ensure_spotify_token():
    token = load_token()
    if token and token.get("access_token"):
        return token
    return run_spotify_login()


def spotify_api_request(method, path, body=None):
    token = ensure_spotify_token()
    data = None
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{SPOTIFY_API_BASE}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=SPOTIFY_API_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="replace").strip()
            if not raw:
                return None
            if raw[0] not in "[{":
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            refreshed = refresh_spotify_token(load_token())
            if refreshed:
                request = urllib.request.Request(
                    f"{SPOTIFY_API_BASE}{path}",
                    data=data,
                    headers={
                        "Authorization": f"Bearer {refreshed['access_token']}",
                        **({"Content-Type": "application/json"} if body is not None else {}),
                    },
                    method=method,
                )
                with urllib.request.urlopen(request, timeout=SPOTIFY_API_TIMEOUT_SECONDS) as response:
                    raw = response.read().decode("utf-8", errors="replace").strip()
                    if not raw:
                        return None
                    if raw[0] not in "[{":
                        return None
                    return json.loads(raw)
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Spotify API {exc.code}: {detail}") from exc


def get_api_playback_snapshot():
    state = spotify_api_request("GET", "/me/player")
    if not state:
        return None

    item = state.get("item") or {}
    if not item:
        return None

    artists = item.get("artists") or []
    artist_names = [artist.get("name", "") for artist in artists if artist.get("name")]
    artist = ", ".join(artist_names) or "Unknown artist"
    title = item.get("name") or "Unknown title"
    return (
        clean_text(title, "Unknown title"),
        clean_text(artist, "Unknown artist"),
        int((state.get("progress_ms") or 0) / 1000),
        int((item.get("duration_ms") or 0) / 1000),
        1 if state.get("is_playing") else 0,
    )


def run_spotify_api_control_command(command):
    if command == "PLAY_PAUSE":
        state = spotify_api_request("GET", "/me/player")
        if state and state.get("is_playing"):
            spotify_api_request("PUT", "/me/player/pause")
        else:
            spotify_api_request("PUT", "/me/player/play")
        return True
    if command == "NEXT":
        spotify_api_request("POST", "/me/player/next")
        return True
    if command == "PREVIOUS":
        spotify_api_request("POST", "/me/player/previous")
        return True
    if command in ("SEEK_FORWARD_5", "SEEK_BACK_5"):
        state = spotify_api_request("GET", "/me/player")
        if not state:
            return False
        progress = int(state.get("progress_ms") or 0)
        item = state.get("item") or {}
        duration = int(item.get("duration_ms") or 0)
        delta = SEEK_STEP_MS if command == "SEEK_FORWARD_5" else -SEEK_STEP_MS
        target = max(0, progress + delta)
        if duration > 0:
            target = min(target, duration)
        spotify_api_request("PUT", f"/me/player/seek?position_ms={target}")
        return True
    return False


def get_liked_songs(limit=50):
    try:
        response = spotify_api_request("GET", f"/me/tracks?limit={limit}")
    except RuntimeError as exc:
        if "Spotify API 403" not in str(exc):
            raise
        run_spotify_login()
        response = spotify_api_request("GET", f"/me/tracks?limit={limit}")
    songs = []
    for item in (response or {}).get("items", []):
        track = item.get("track") or {}
        uri = track.get("uri")
        title = track.get("name") or "Unknown title"
        artists = track.get("artists") or []
        artist = ", ".join(a.get("name", "") for a in artists if a.get("name")) or "Unknown artist"
        if uri:
            songs.append({
                "title": clean_text(title, "Unknown title"),
                "artist": clean_text(artist, "Unknown artist"),
                "uri": uri,
            })
    return songs


def play_track_uri(uri):
    spotify_api_request("PUT", "/me/player/play", {"uris": [uri]})
    return True


def play_track_in_context(context_uri, track_uri):
    spotify_api_request("PUT", "/me/player/play", {
        "context_uri": context_uri,
        "offset": {"uri": track_uri},
    })
    return True


def play_context_uri(context_uri):
    spotify_api_request("PUT", "/me/player/play", {"context_uri": context_uri})
    return True


def play_liked_song_by_offset(offset):
    spotify_api_request("PUT", "/me/player/play", {
        "context_uri": "spotify:collection:tracks",
        "offset": {"position": int(offset)},
    })
    return True


def get_user_playlists(limit=50):
    try:
        response = spotify_api_request("GET", f"/me/playlists?limit={limit}")
    except RuntimeError as exc:
        if "Spotify API 403" not in str(exc):
            raise
        run_spotify_login()
        response = spotify_api_request("GET", f"/me/playlists?limit={limit}")

    filters = {name.strip().casefold() for name in PLAYLIST_MENU_NAMES if name.strip()}
    playlists = [{
        "id": "__liked_songs__",
        "name": "Liked Songs",
        "uri": "spotify:collection:tracks",
        "tracks_href": "",
        "special": "liked",
    }]
    for item in (response or {}).get("items", []):
        playlist_id = item.get("id")
        name = item.get("name") or "Playlist"
        if filters and name.casefold() not in filters:
            continue
        if playlist_id:
            tracks_href = ((item.get("tracks") or {}).get("href") or "")
            playlists.append({
                "id": playlist_id,
                "name": clean_text(name, "Playlist"),
                "uri": item.get("uri") or "",
                "tracks_href": tracks_href,
            })
    return playlists


def spotify_path_from_url(url):
    parsed = urllib.parse.urlparse(url or "")
    path = parsed.path or ""
    if parsed.query:
        path += "?" + parsed.query
    return path


def get_playlist_tracks(playlist, limit=50):
    tracks_href = playlist.get("tracks_href") or ""
    path = spotify_path_from_url(tracks_href)
    if not path:
        path = f"/playlists/{playlist['id']}/tracks"
    separator = "&" if "?" in path else "?"
    if "limit=" not in path:
        path += f"{separator}limit={limit}"
        separator = "&"
    if "market=" not in path:
        path += f"{separator}market=from_token"

    response = spotify_api_request("GET", path)
    tracks = []
    for item in (response or {}).get("items", []):
        track = item.get("track") or {}
        if not track or track.get("is_local"):
            continue
        uri = track.get("uri")
        title = track.get("name") or "Unknown title"
        artists = track.get("artists") or []
        artist = ", ".join(a.get("name", "") for a in artists if a.get("name")) or "Unknown artist"
        if uri:
            tracks.append({
                "title": clean_text(title, "Unknown title"),
                "artist": clean_text(artist, "Unknown artist"),
                "uri": uri,
            })
    return tracks


def score_port(port):
    text = f"{port.device} {port.description} {port.hwid}".lower()
    if "bluetooth" in text:
        return -10
    if "usb serial device" in text:
        return 100
    if "esp32" in text or "cp210" in text or "ch340" in text or "jtag/serial" in text:
        return 90
    if "usb" in text and "serial" in text:
        return 80
    if "serial" in text:
        return 10
    return 0


def find_serial_port():
    ports = list(serial.tools.list_ports.comports())
    ports.sort(key=score_port, reverse=True)
    for port in ports:
        if score_port(port) > 0:
            return port.device
    return None


async def send_to_device(message, quiet=False):
    global serial_port
    if serial_port and serial_port.is_open:
        try:
            serial_port.write((message + "\n").encode("utf-8"))
            if not quiet:
                log(f"TX {message}")
        except Exception as exc:
            log(f"Serial write failed: {exc}")
            try:
                serial_port.close()
            except Exception:
                pass
            serial_port = None


async def send_hid_media_command(command):
    hid_commands = {
        "PREVIOUS",
        "PLAY_PAUSE",
        "NEXT",
        "MUTE",
        "VOLUME_UP",
        "VOLUME_DOWN",
        "SEEK_FORWARD_5",
        "SEEK_BACK_5",
    }
    if command not in hid_commands:
        return False
    if serial_port and serial_port.is_open:
        await send_to_device(f"HID:{command}")
        return True
    return send_media_key_for_command(command)


async def send_spotify_control_with_hid_fallback(command):
    api_commands = {"PLAY_PAUSE", "NEXT", "PREVIOUS", "SEEK_FORWARD_5", "SEEK_BACK_5"}
    if command in api_commands:
        try:
            ok = await asyncio.wait_for(
                asyncio.to_thread(run_spotify_api_control_command, command),
                timeout=SPOTIFY_API_TIMEOUT_SECONDS + 1,
            )
            if ok:
                log(f"{command} ok via Spotify API")
                return True, "api"
        except Exception as exc:
            log(f"{command} Spotify API failed; falling back to HID: {exc}")

    ok = await send_hid_media_command(command)
    return ok, "hid" if ok else "failed"


async def send_local_now_playing_hint():
    global last_title, last_artist, last_position, last_duration, last_status, deck_idle, paused_since
    deck_idle = False
    paused_since = None
    title = "Spotify"
    artist = "Local playback"
    pos = (last_position + 1) if last_title == title and isinstance(last_position, int) else 0
    dur = 240
    last_title, last_artist, last_position, last_duration, last_status = title, artist, pos, dur, 1
    await send_to_device(f"MEDIA:{title}|{artist}|{pos}|{dur}", quiet=False)
    await send_to_device("STATUS:1", quiet=False)


def liked_song_row(song):
    row = f"{song['title']} - {song['artist']}"
    return clean_text(row, "Liked song")[:28]


async def send_liked_songs_menu():
    if not liked_songs_items:
        await send_to_device("OLED:QUEUE:0,0,0|No liked songs")
        return

    total = len(liked_songs_items)
    selected = max(0, min(liked_songs_index, total - 1))
    first = selected - 2
    if first < 0:
        first = 0
    if first > total - 5:
        first = max(0, total - 5)
    selected_row = selected - first
    rows = [liked_song_row(song) for song in liked_songs_items[first:first + 5]]
    while len(rows) < 5:
        rows.append("")
    payload = f"{selected_row},{selected},{total}|" + "|".join(rows)
    await send_to_device(f"OLED:QUEUE:{payload}")


async def open_liked_songs_menu():
    global liked_songs_menu_active, liked_songs_index, liked_songs_items
    await send_to_device("OLED:Loading liked")
    try:
        liked_songs_items = await asyncio.wait_for(asyncio.to_thread(get_liked_songs), timeout=8)
    except Exception as exc:
        liked_songs_items = []
        liked_songs_menu_active = False
        await send_to_device("OLED:Liked unavailable")
        log(f"Liked songs fetch failed: {exc}")
        return

    liked_songs_index = 0
    liked_songs_menu_active = True
    await send_liked_songs_menu()
    log(f"Liked songs menu opened with {len(liked_songs_items)} tracks")


async def play_selected_liked_song():
    global liked_songs_menu_active
    if not liked_songs_items:
        await send_to_device("OLED:No liked songs")
        return
    song = liked_songs_items[max(0, min(liked_songs_index, len(liked_songs_items) - 1))]
    try:
        await asyncio.wait_for(asyncio.to_thread(play_liked_song_by_offset, liked_songs_index), timeout=8)
        liked_songs_menu_active = False
        await send_to_device("OLED:QUEUE:OFF")
        await send_to_device(f"OLED:Playing {song['title'][:10]}")
        log(f"Liked song selected: {song['title']} - {song['artist']}")
    except Exception as exc:
        await send_to_device("OLED:Play failed")
        log(f"Liked song play failed: {exc}")


def playlist_row(playlist):
    return clean_text(playlist.get("name"), "Playlist")[:28]


def playlist_track_row(track):
    row = f"{track['title']} - {track['artist']}"
    return clean_text(row, "Track")[:28]


async def send_spotify_browser_menu():
    if playlist_browser_level == "playlists":
        items = playlist_items
        selected = playlist_index
        empty = "No playlists"
        row_fn = playlist_row
    else:
        items = playlist_track_items
        selected = playlist_track_index
        empty = "No tracks"
        row_fn = playlist_track_row

    if not items:
        await send_to_device(f"OLED:QUEUE:0,0,0|{empty}")
        return

    total = len(items)
    selected = max(0, min(selected, total - 1))
    first = selected - 2
    if first < 0:
        first = 0
    if first > total - 5:
        first = max(0, total - 5)
    selected_row = selected - first
    rows = [row_fn(item) for item in items[first:first + 5]]
    while len(rows) < 5:
        rows.append("")
    payload = f"{selected_row},{selected},{total}|" + "|".join(rows)
    await send_to_device(f"OLED:QUEUE:{payload}")


async def open_playlist_browser():
    global playlist_browser_active, playlist_browser_level, playlist_index, playlist_items
    global playlist_track_index, playlist_track_items
    await send_to_device("OLED:Loading lists")
    try:
        playlist_items = await asyncio.wait_for(asyncio.to_thread(get_user_playlists), timeout=8)
    except Exception as exc:
        playlist_items = []
        playlist_browser_active = False
        await send_to_device("OLED:Lists unavailable")
        log(f"Playlist fetch failed: {exc}")
        return

    playlist_browser_active = True
    playlist_browser_level = "playlists"
    playlist_index = 0
    playlist_track_index = 0
    playlist_track_items = []
    await send_spotify_browser_menu()
    log(f"Playlist browser opened with {len(playlist_items)} playlists")


async def enter_selected_playlist():
    global playlist_browser_level, playlist_track_index, playlist_track_items
    if not playlist_items:
        await send_to_device("OLED:No playlists")
        return

    playlist = playlist_items[max(0, min(playlist_index, len(playlist_items) - 1))]
    await send_to_device("OLED:Loading songs")
    try:
        if playlist.get("special") == "liked":
            playlist_track_items = await asyncio.wait_for(asyncio.to_thread(get_liked_songs), timeout=8)
        else:
            playlist_track_items = await asyncio.wait_for(
                asyncio.to_thread(get_playlist_tracks, playlist),
                timeout=8,
            )
    except Exception as exc:
        playlist_track_items = []
        if playlist.get("uri"):
            try:
                await asyncio.wait_for(asyncio.to_thread(play_context_uri, playlist["uri"]), timeout=8)
                await send_to_device("OLED:Playing list")
                log(f"Playlist started directly after track-list fetch failed: {playlist['name']}: {exc}")
                return
            except Exception as play_exc:
                log(f"Playlist direct play also failed for {playlist['name']}: {play_exc}")
        await send_to_device("OLED:Songs unavailable")
        log(f"Playlist tracks fetch failed for {playlist['name']}: {exc}")
        return

    playlist_browser_level = "tracks"
    playlist_track_index = 0
    await send_spotify_browser_menu()
    log(f"Playlist opened: {playlist['name']} with {len(playlist_track_items)} tracks")


async def play_selected_playlist_track():
    if not playlist_track_items:
        await send_to_device("OLED:No tracks")
        return
    track = playlist_track_items[max(0, min(playlist_track_index, len(playlist_track_items) - 1))]
    playlist = playlist_items[max(0, min(playlist_index, len(playlist_items) - 1))] if playlist_items else None
    try:
        if playlist and playlist.get("special") == "liked":
            await asyncio.wait_for(asyncio.to_thread(play_liked_song_by_offset, playlist_track_index), timeout=8)
        elif playlist and playlist.get("uri"):
            await asyncio.wait_for(
                asyncio.to_thread(play_track_in_context, playlist["uri"], track["uri"]),
                timeout=8,
            )
        else:
            await asyncio.wait_for(asyncio.to_thread(play_track_uri, track["uri"]), timeout=8)
        await send_to_device(f"OLED:Playing {track['title'][:10]}")
        log(f"Playlist track selected: {track['title']} - {track['artist']}")
    except Exception as exc:
        await send_to_device("OLED:Play failed")
        log(f"Playlist track play failed: {exc}")


async def playlist_browser_back():
    global playlist_browser_active, playlist_browser_level
    if playlist_browser_level == "tracks":
        playlist_browser_level = "playlists"
        await send_spotify_browser_menu()
        return
    playlist_browser_active = False
    await send_to_device("OLED:QUEUE:OFF")
    await send_to_device("OLED:Browser closed")


def get_spotify_audio_controls():
    CoInitialize()
    controls = []
    for session in AudioUtilities.GetAllSessions():
        process = session.Process
        if process and process.name().lower() == SPOTIFY_PROCESS:
            controls.append(session._ctl.QueryInterface(ISimpleAudioVolume))
    return controls


def get_spotify_audio_state():
    controls = get_spotify_audio_controls()
    if not controls:
        return False, 50
    muted = any(bool(control.GetMute()) for control in controls)
    volume = int(round(max(control.GetMasterVolume() for control in controls) * 100))
    return muted, max(0, min(volume, 100))


def get_spotify_audio_activity():
    CoInitialize()
    found = False
    peak = 0.0
    for session in AudioUtilities.GetAllSessions():
        process = session.Process
        if process and process.name().lower() == SPOTIFY_PROCESS:
            found = True
            try:
                meter = session._ctl.QueryInterface(IAudioMeterInformation)
                peak = max(peak, float(meter.GetPeakValue()))
            except Exception:
                pass
    return found, peak


APP_TARGETS = [
    {
        "name": "Spotify",
        "processes": ["Spotify"],
        "titles": ["Spotify"],
        "app_id": SPOTIFY_APP_ID,
        "maximize": True,
        "launch_if_running": True,
    },
    {
        "name": "Terminal Admin",
        "processes": [],
        "titles": ["Administrator:", "Admin"],
        "special": "terminal_admin",
        "maximize": True,
    },
    {
        "name": "Files",
        "processes": [],
        "titles": ["File Explorer", "This PC", "Downloads", "Desktop"],
        "shell_uri": "explorer.exe",
        "maximize": True,
        "launch_if_running": True,
    },
    {
        "name": "Opera",
        "processes": ["opera"],
        "titles": ["Opera"],
        "app_id": OPERA_APP_ID,
        "maximize": True,
    },
    {
        "name": "WhatsApp",
        "processes": ["WhatsApp", "WhatsAppBeta"],
        "titles": ["WhatsApp"],
        "shell_uri": "whatsapp:",
        "app_id": WHATSAPP_APP_ID,
        "maximize": True,
        "launch_if_running": True,
    },
    {
        "name": "Codex",
        "processes": ["Codex"],
        "titles": ["Codex"],
        "app_id": CODEX_RAW_APP_ID,
        "maximize": True,
        "launch_if_running": True,
    },
]


def open_spotify():
    launch_or_switch_app(APP_TARGETS[0])


def open_terminal_admin():
    launch_or_switch_app(APP_TARGETS[1])


def open_files():
    launch_or_switch_app(APP_TARGETS[2])


def open_opera():
    launch_or_switch_app(APP_TARGETS[3])


def open_whatsapp():
    launch_or_switch_app(APP_TARGETS[4])


def open_codex():
    launch_or_switch_app(APP_TARGETS[5])


def open_idle_mode():
    return None


def open_project_folder():
    os.startfile(Path(__file__).parent)


APP_LAUNCHERS = [
    open_spotify,
    open_terminal_admin,
    open_files,
    open_opera,
    open_whatsapp,
    open_codex,
    open_idle_mode,
]


def launch_app_safely(index, name):
    try:
        APP_LAUNCHERS[index]()
    except Exception as exc:
        log(f"App launch failed for {name}: {exc}")


async def send_volume_state(force=False):
    global last_volume_status
    muted, volume = get_spotify_audio_state()
    status = (muted, volume)
    if force or status != last_volume_status:
        last_volume_status = status
        await send_to_device(f"OLED:VOL:Spotify,{volume},{1 if muted else 0}", quiet=not force)
        await send_to_device("LED:MUTE" if muted else "LED:UNMUTE", quiet=True)


def adjust_spotify_volume(delta):
    controls = get_spotify_audio_controls()
    if not controls:
        log("Spotify audio session not found. Open Spotify and play once.")
        return False
    for control in controls:
        new_volume = max(0.0, min(control.GetMasterVolume() + delta, 1.0))
        control.SetMasterVolume(new_volume, None)
        if new_volume > 0:
            control.SetMute(0, None)
    return True


def toggle_spotify_mute():
    controls = get_spotify_audio_controls()
    if not controls:
        log("Spotify audio session not found. Open Spotify and play once.")
        return False
    currently_muted = any(bool(control.GetMute()) for control in controls)
    for control in controls:
        control.SetMute(0 if currently_muted else 1, None)
    return True


async def find_spotify_media_session():
    manager = await asyncio.wait_for(MediaManager.request_async(), timeout=2.5)
    sessions = manager.get_sessions()
    for session in sessions:
        app_id = (session.source_app_user_model_id or "").lower()
        if SPOTIFY_APP_HINT in app_id:
            return session
    return None


async def run_spotify_media_command(command):
    session = await find_spotify_media_session()
    if session is None:
        log("Spotify media session not found. Open Spotify and play once.")
        return False

    if command == "PLAY_PAUSE":
        return bool(await asyncio.wait_for(session.try_toggle_play_pause_async(), timeout=2.5))
    if command == "NEXT":
        return bool(await asyncio.wait_for(session.try_skip_next_async(), timeout=2.5))
    if command == "PREVIOUS":
        return bool(await asyncio.wait_for(session.try_skip_previous_async(), timeout=2.5))
    if command in ("SEEK_FORWARD_5", "SEEK_BACK_5"):
        timeline = session.get_timeline_properties()
        current_ms = int(timeline.position.total_seconds() * 1000)
        duration_ms = int(timeline.end_time.total_seconds() * 1000)
        delta_ms = SEEK_STEP_MS if command == "SEEK_FORWARD_5" else -SEEK_STEP_MS
        target_ms = max(0, current_ms + delta_ms)
        if duration_ms > 0:
            target_ms = min(target_ms, duration_ms)
        return bool(await asyncio.wait_for(session.try_change_playback_position_async(target_ms * 10000), timeout=2.5))

    return False


async def handle_input_command(line):
    global app_menu_active, app_menu_index
    global idle_menu_active, idle_menu_index, idle_animation_index, now_playing_style_index
    global np_style_menu_active, np_style_menu_index
    global liked_songs_menu_active, liked_songs_index
    global playlist_browser_active, playlist_browser_level, playlist_index, playlist_track_index
    global active_app_mode
    global last_touch_long_time
    global manual_idle_requested, deck_idle, last_title, last_artist, last_position, last_duration, last_status

    now = time.time()
    if line in last_command_times and (now - last_command_times[line]) < 0.12:
        return
    last_command_times[line] = now

    if playlist_browser_active:
        if line == "ENC:+1":
            if playlist_browser_level == "playlists":
                playlist_index = (playlist_index + 1) % max(1, len(playlist_items))
            else:
                playlist_track_index = (playlist_track_index + 1) % max(1, len(playlist_track_items))
            await send_spotify_browser_menu()
        elif line == "ENC:-1":
            if playlist_browser_level == "playlists":
                playlist_index = (playlist_index - 1) % max(1, len(playlist_items))
            else:
                playlist_track_index = (playlist_track_index - 1) % max(1, len(playlist_track_items))
            await send_spotify_browser_menu()
        elif line == "CLICK:short":
            if playlist_browser_level == "playlists":
                await enter_selected_playlist()
            else:
                await play_selected_playlist_track()
        elif line in ("CLICK:long", "BTN:4", "BTN:5"):
            await playlist_browser_back()
        return

    if liked_songs_menu_active:
        if line == "ENC:+1":
            liked_songs_index = (liked_songs_index + 1) % max(1, len(liked_songs_items))
            await send_liked_songs_menu()
        elif line == "ENC:-1":
            liked_songs_index = (liked_songs_index - 1) % max(1, len(liked_songs_items))
            await send_liked_songs_menu()
        elif line == "CLICK:short":
            await play_selected_liked_song()
        elif line in ("CLICK:long", "BTN:4", "BTN:5"):
            liked_songs_menu_active = False
            await send_to_device("OLED:QUEUE:OFF")
            await send_to_device("OLED:Liked closed")
        return

    if np_style_menu_active:
        if line == "ENC:+1":
            np_style_menu_index = (np_style_menu_index + 1) % len(NP_STYLE_MENU_ITEMS)
            await send_to_device(f"OLED:NPSTYLEMENU:{np_style_menu_index}")
        elif line == "ENC:-1":
            np_style_menu_index = (np_style_menu_index - 1) % len(NP_STYLE_MENU_ITEMS)
            await send_to_device(f"OLED:NPSTYLEMENU:{np_style_menu_index}")
        elif line == "CLICK:short":
            now_playing_style_index = np_style_menu_index
            np_style_menu_active = False
            await send_to_device("OLED:NPSTYLEMENU:OFF")
            await send_to_device(f"OLED:NPSTYLE:{now_playing_style_index}")
            log(f"Now-playing style selected: {NP_STYLE_MENU_ITEMS[now_playing_style_index]}")
        elif line == "CLICK:long" or line == "BTN:4":
            np_style_menu_active = False
            await send_to_device("OLED:NPSTYLEMENU:OFF")
            await send_to_device("OLED:Style menu closed")
        return

    if idle_menu_active:
        if line == "ENC:+1":
            idle_menu_index = (idle_menu_index + 1) % len(IDLE_MENU_ITEMS)
            await send_to_device(f"OLED:IDLEMENU:{idle_menu_index}")
        elif line == "ENC:-1":
            idle_menu_index = (idle_menu_index - 1) % len(IDLE_MENU_ITEMS)
            await send_to_device(f"OLED:IDLEMENU:{idle_menu_index}")
        elif line == "CLICK:short":
            idle_animation_index = idle_menu_index
            idle_menu_active = False
            await send_to_device("OLED:IDLEMENU:OFF")
            await send_to_device(f"OLED:IDLE:{idle_animation_index}")
            log(f"Idle animation selected: {IDLE_MENU_ITEMS[idle_animation_index]}")
        elif line == "CLICK:long" or line == "BTN:4":
            idle_menu_active = False
            await send_to_device("OLED:IDLEMENU:OFF")
            await send_to_device("OLED:Idle menu closed")
        return

    if app_menu_active:
        if line == "ENC:+1":
            app_menu_index = (app_menu_index + 1) % len(APP_MENU_ITEMS)
            await send_to_device(f"OLED:APPMENU:{app_menu_index}")
        elif line == "ENC:-1":
            app_menu_index = (app_menu_index - 1) % len(APP_MENU_ITEMS)
            await send_to_device(f"OLED:APPMENU:{app_menu_index}")
        elif line == "CLICK:short":
            name = APP_MENU_ITEMS[app_menu_index]
            selected_app_index = app_menu_index
            app_menu_active = False
            await send_to_device("OLED:APPMENU:OFF")
            if name == "Idle Mode":
                manual_idle_requested = True
                active_app_mode = "idle"
                deck_idle = True
                last_title = None
                last_artist = None
                last_position = None
                last_duration = None
                last_status = 0
                await send_to_device("MEDIA:STOP")
                await send_to_device("STATUS:0")
                await send_to_device("OLED:MODE:Idle")
                await send_to_device("OLED:FOOTER:IDLE")
                await send_to_device("OLED:Idle Mode")
                log("App menu selected: Idle Mode")
                return

            asyncio.create_task(asyncio.to_thread(launch_app_safely, selected_app_index, name))
            active_app_mode = "spotify" if app_menu_index == 0 else name.lower()
            manual_idle_requested = False
            if active_app_mode == "spotify":
                await send_to_device("OLED:MODE:Spotify")
                await send_to_device("OLED:FOOTER:SPOTIFY")
                await send_to_device("OLED:Spotify Mode")
            else:
                await send_to_device(f"OLED:MODE:{name}")
                await send_to_device("OLED:FOOTER:APP MODE")
                await send_to_device(f"OLED:Opening {name}")
            log(f"App menu launched: {name}")
        elif line == "CLICK:long":
            app_menu_active = False
            await send_to_device("OLED:APPMENU:OFF")
            await send_to_device("OLED:Menu closed")
        elif line == "BTN:4":
            app_menu_active = False
            await send_to_device("OLED:APPMENU:OFF")
            await send_to_device("OLED:Menu closed")
        return

    mapping = {
        "BTN:1": "PLAY_PAUSE",
        "BTN:2": "NEXT",
        "BTN:3": "PREVIOUS",
        "BTN:4": "SEEK_FORWARD_5",
        "BTN:5": "SEEK_BACK_5",
    }

    if line.startswith("BTNL:"):
        try:
            button = int(line.split(":", 1)[1])
        except ValueError:
            return

        if (now - last_touch_long_time) < 0.9:
            log(f"Ignored extra long-touch event: {line}")
            return
        last_touch_long_time = now

        if active_app_mode == "spotify" and button == 3:
            np_style_menu_active = True
            np_style_menu_index = now_playing_style_index
            await send_to_device(f"OLED:NPSTYLEMENU:{np_style_menu_index}")
            log("Now-playing style menu opened")
        elif active_app_mode == "spotify" and button in (2, 4):
            await open_playlist_browser()
        elif active_app_mode == "spotify":
            log(f"Long touch {button} ignored in Spotify mode")
        elif deck_idle and 1 <= button <= 5:
            idle_menu_active = True
            idle_menu_index = idle_animation_index
            await send_to_device(f"OLED:IDLEMENU:{idle_menu_index}")
            log("Idle animation menu opened")
        elif 1 <= button <= 5:
            idle_menu_active = True
            idle_menu_index = idle_animation_index
            await send_to_device(f"OLED:IDLEMENU:{idle_menu_index}")
            log("Idle animation menu opened")
        return

    if active_app_mode != "spotify" and (line in mapping or line.startswith("ENC:") or line == "CLICK:short"):
        await send_to_device("OLED:Hold knob menu")
        log(f"{line} ignored outside Spotify mode")
        return

    if line in mapping:
        if line == "BTN:2":
            await send_to_device("OLED:TRANSITION:NEXT")
        elif line == "BTN:3":
            await send_to_device("OLED:TRANSITION:PREVIOUS")
        command = mapping[line]
        ok, route = await send_spotify_control_with_hid_fallback(command)
        if not ok:
            await send_to_device("OLED:Control failed")
        elif command in ("PLAY_PAUSE", "PREVIOUS", "NEXT", "SEEK_FORWARD_5", "SEEK_BACK_5"):
            await send_local_now_playing_hint()
        if ok and line not in ("BTN:2", "BTN:3"):
            await send_to_device(f"OLED:{command.replace('_', ' ')}")
        log(f"{line} -> {command} {'ok' if ok else 'failed'} via {route}")
    elif line == "ENC:+1":
        if adjust_spotify_volume(VOLUME_STEP):
            await send_volume_state(force=True)
            await send_to_device("LED:VOL,+,70", quiet=True)
    elif line == "ENC:-1":
        if adjust_spotify_volume(-VOLUME_STEP):
            await send_volume_state(force=True)
            await send_to_device("LED:VOL,-,30", quiet=True)
    elif line == "CLICK:short":
        try:
            session = await asyncio.wait_for(find_spotify_media_session(), timeout=3.0)
        except Exception as exc:
            session = None
            log(f"Spotify session check failed: {exc}")
        if session is None and not get_spotify_audio_controls():
            open_spotify()
            await send_to_device("OLED:Opening Spotify")
            log("CLICK:short -> opening Spotify")
        elif toggle_spotify_mute():
            await send_volume_state(force=True)
    elif line == "CLICK:long":
        app_menu_active = True
        app_menu_index = 0
        await send_to_device("OLED:APPMENU:0")


async def sync_static_oled():
    if active_app_mode == "spotify":
        await send_to_device("OLED:MODE:Spotify", quiet=True)
        await send_to_device("OLED:FOOTER:SPOTIFY", quiet=True)
    else:
        await send_to_device("OLED:MODE:Deck", quiet=True)
        await send_to_device("OLED:FOOTER:APP MENU", quiet=True)
    await send_to_device(f"OLED:IDLE:{idle_animation_index}", quiet=True)
    await send_to_device(f"OLED:NPSTYLE:{now_playing_style_index}", quiet=True)
    await send_volume_state(force=True)


async def clock_loop():
    global last_clock_min
    while True:
        try:
            now = time.localtime()
            if serial_port and serial_port.is_open and now.tm_min != last_clock_min:
                last_clock_min = now.tm_min
                await send_to_device(f"OLED:CLOCK:{time.strftime('%H:%M')}", quiet=True)
        except Exception as exc:
            log(f"Clock sync failed: {exc}")
        await asyncio.sleep(5)


async def media_monitor_loop():
    global last_title, last_artist, last_position, last_duration, last_status, paused_since, deck_idle
    global last_media_timeout_log
    global active_app_mode, manual_idle_requested
    manager = None
    stopped_seconds = 0
    fallback_position = 0
    estimated_duration = 240

    while True:
        try:
            title = ""
            artist = ""
            pos = 0
            dur = 240
            status = 0

            try:
                if manager is None:
                    manager = await asyncio.wait_for(MediaManager.request_async(), timeout=2.5)

                session = manager.get_current_session() if manager else None
                if session:
                    props = await asyncio.wait_for(session.try_get_media_properties_async(), timeout=2.5)
                    if props:
                        raw_title = props.title or ""
                        raw_artist = props.artist or ""
                        timeline = session.get_timeline_properties()
                        playback = session.get_playback_info()
                        status = 1 if playback and int(playback.playback_status) == 4 else 0

                        if timeline:
                            try:
                                pos = int(timeline.position.total_seconds())
                                dur = int(timeline.end_time.total_seconds())
                            except Exception:
                                pos = fallback_position
                                dur = estimated_duration

                        title = clean_text(raw_title, "Unknown title")
                        artist = clean_text(raw_artist, "Unknown artist")
                        estimated_duration = dur if dur > 0 else estimated_duration
            except asyncio.TimeoutError:
                manager = None
                now = time.time()
                if now - last_media_timeout_log > 20:
                    log("Windows metadata timed out; using local Spotify audio fallback.")
                    last_media_timeout_log = now
            except Exception as exc:
                manager = None
                log(f"Windows metadata failed; using local Spotify audio fallback: {exc}")

            if not title:
                try:
                    snapshot = await asyncio.wait_for(
                        asyncio.to_thread(get_api_playback_snapshot),
                        timeout=SPOTIFY_API_TIMEOUT_SECONDS + 1,
                    )
                    if snapshot:
                        title, artist, pos, dur, status = snapshot
                except Exception as exc:
                    now = time.time()
                    if now - last_media_timeout_log > 20:
                        log(f"Spotify now-playing API fallback failed: {exc}")
                        last_media_timeout_log = now

            if not title:
                spotify_found, peak = await asyncio.to_thread(get_spotify_audio_activity)
                if spotify_found and peak > 0.002:
                    status = 1
                    fallback_position = (fallback_position + 1) % 240
                    title = "Spotify"
                    artist = "Local playback"
                    pos = fallback_position
                    dur = 240

            now = time.time()

            if title and status == 1:
                if active_app_mode == "idle":
                    active_app_mode = "spotify"
                    await send_to_device("OLED:MODE:Spotify", quiet=True)
                    await send_to_device("OLED:FOOTER:SPOTIFY", quiet=True)
                manual_idle_requested = False
                paused_since = None
                deck_idle = False
                stopped_seconds = 0
            else:
                if paused_since is None:
                    paused_since = now
                stopped_seconds += 1
                if manual_idle_requested or stopped_seconds >= 10:
                    deck_idle = True
                    await send_to_device("MEDIA:STOP", quiet=True)
                    last_title = None
                    last_artist = None
                    last_position = None
                    last_duration = None
                    if status != last_status:
                        await send_to_device(f"STATUS:{status}", quiet=True)
                        last_status = status
                    await send_volume_state()
                    await asyncio.sleep(1)
                    continue
                deck_idle = False

            if title and (title, artist, pos, dur) != (last_title, last_artist, last_position, last_duration):
                await send_to_device(f"MEDIA:{title}|{artist}|{pos}|{dur}", quiet=False)
                last_title, last_artist, last_position, last_duration = title, artist, pos, dur
            if status != last_status:
                await send_to_device(f"STATUS:{status}", quiet=False)
                last_status = status
            await send_volume_state()
        except asyncio.TimeoutError:
            now = time.time()
            if now - last_media_timeout_log > 20:
                log("Windows now-playing timeout; playback controls still use HID.")
                last_media_timeout_log = now
        except Exception as exc:
            log(f"Media monitor failed: {exc}")
            manager = None
        await asyncio.sleep(1)


async def connectivity_loop():
    global serial_port
    while True:
        try:
            if serial_port and serial_port.is_open:
                if serial_port.in_waiting:
                    line = serial_port.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        log(f"RX {line}")
                        if line == "READY":
                            await sync_static_oled()
                        elif line.startswith(("BTN:", "BTNL:", "ENC:", "CLICK:")):
                            await handle_input_command(line)
                await asyncio.sleep(0.01)
                continue

            port_name = find_serial_port()
            if port_name:
                try:
                    if serial_port:
                        try:
                            serial_port.close()
                        except Exception:
                            pass
                    serial_port = serial.Serial(port_name, SERIAL_BAUD, timeout=0.1)
                    serial_port.dtr = serial_port.rts = True
                    log(f"Connected to {port_name}")
                    await asyncio.sleep(1.5)
                    await sync_static_oled()
                except Exception as exc:
                    log(f"Could not open {port_name}: {exc}")
                    serial_port = None
            await asyncio.sleep(2)
        except Exception as exc:
            log(f"Connectivity failed: {exc}")
            try:
                if serial_port:
                    serial_port.close()
            except Exception:
                pass
            serial_port = None
            await asyncio.sleep(2)


def build_tray_image():
    image = Image.new("RGB", (64, 64), (18, 18, 18))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 56, 56), radius=10, fill=(30, 185, 84))
    draw.text((24, 21), "D", fill=(255, 255, 255))
    return image


def run_async_from_tray(coro):
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, main_loop)


def tray_open_spotify(icon, item):
    open_spotify()


def tray_open_folder(icon, item):
    open_project_folder()


def tray_reconnect(icon, item):
    global serial_port
    try:
        if serial_port:
            serial_port.close()
    except Exception:
        pass
    serial_port = None
    log("Tray requested reconnect.")


def tray_exit(icon, item):
    global serial_port
    try:
        if serial_port:
            serial_port.close()
    except Exception:
        pass
    try:
        icon.stop()
    except Exception:
        pass
    os._exit(0)


def setup_tray():
    global tray_icon
    try:
        menu = pystray.Menu(
            pystray.MenuItem("Deck is running", lambda icon, item: None, enabled=False),
            pystray.MenuItem("Open Spotify", tray_open_spotify),
            pystray.MenuItem("Reconnect Deck", tray_reconnect),
            pystray.MenuItem("Open Project Folder", tray_open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Deck", tray_exit),
        )
        tray_icon = pystray.Icon("Deck", build_tray_image(), "Deck", menu)
        tray_icon.run()
    except Exception as exc:
        log(f"Tray icon failed: {exc}")


async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    threading.Thread(target=setup_tray, daemon=True).start()
    log("Deck companion started. Deck works with Spotify foreground or background.")
    asyncio.create_task(clock_loop())
    asyncio.create_task(media_monitor_loop())
    await connectivity_loop()


if __name__ == "__main__":
    try:
        if not acquire_single_instance_lock():
            log("Another Deck companion is already running. Exiting.")
            sys.exit(0)
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
