@echo off
title Uninstall Deck Startup

echo Removing Deck from Windows startup...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "Deck" /f

echo.
echo Done. The Deck companion will no longer start automatically at login.
pause
