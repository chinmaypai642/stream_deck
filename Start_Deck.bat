@echo off
setlocal
cd /d "%~dp0"
title Deck Companion

echo Deck Companion
echo Deck will work when Spotify is running in foreground or background.
echo Keep this window open, or use Start_Deck_Hidden.bat for no window.
echo.

if exist "%~dp0dist\Deck.exe" (
  "%~dp0dist\Deck.exe"
) else (
  python spotify_deck_win.py
)

echo.
echo Deck companion stopped.
pause
