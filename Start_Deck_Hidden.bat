@echo off
setlocal
cd /d "%~dp0"

set "PYTHONW="
for /f "usebackq delims=" %%P in (`python -c "import sys, os; p=sys.executable; print(os.path.join(os.path.dirname(p), 'pythonw.exe'))"`) do set "PYTHONW=%%P"

if not exist "%PYTHONW%" (
  echo Could not find pythonw.exe.
  echo Use Start_Deck.bat instead.
  pause
  exit /b 1
)

start "" "%PYTHONW%" "%~dp0spotify_deck_win.py"
exit /b 0
