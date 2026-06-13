@echo off
title Stop Deck

echo Stopping Deck companion...
taskkill /F /IM Deck.exe /T >nul 2>nul
taskkill /F /IM pythonw.exe /T >nul 2>nul

echo Done.
pause
