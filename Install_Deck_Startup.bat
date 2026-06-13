@echo off
setlocal
cd /d "%~dp0"
title Install Deck Startup

echo Installing Deck startup mode...
echo.

python -m pip install -r requirements_spotify_deck.txt

set "PYTHONW="
for /f "usebackq delims=" %%P in (`python -c "import sys, os; p=sys.executable; print(os.path.join(os.path.dirname(p), 'pythonw.exe'))"`) do set "PYTHONW=%%P"

if not exist "%PYTHONW%" (
  echo Could not find pythonw.exe.
  echo Startup install failed.
  pause
  exit /b 1
)

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "Deck" /t REG_SZ /d "\"%PYTHONW%\" \"%~dp0spotify_deck_win.py\"" /f
echo Installed hidden Python app:
echo   "%PYTHONW%" "%~dp0spotify_deck_win.py"

echo.
echo Done. Deck will start silently when Windows logs in.
echo You do not have to keep PowerShell open.
echo.
pause
