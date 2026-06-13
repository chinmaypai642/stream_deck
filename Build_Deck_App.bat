@echo off
setlocal
cd /d "%~dp0"
title Build Deck App

echo ===================================================
echo   Deck - Windows App Builder
echo ===================================================
echo.
echo Installing dependencies...
python -m pip install -r requirements_spotify_deck.txt
python -m pip install pyinstaller
echo.
echo Building hidden tray app...
python -m PyInstaller Deck.spec --clean --noconfirm
echo.
if not exist "%~dp0dist\Deck.exe" (
  echo Build failed. Deck.exe was not created.
  pause
  exit /b 1
)
echo Build complete:
echo   %~dp0dist\Deck.exe
echo.
echo To install it at Windows login, run:
echo   Install_Deck_Startup.bat
echo.
pause
