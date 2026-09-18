@echo off
cd /d "%~dp0"
echo Applying stereo pan to this install...
python inject_pan.py
if errorlevel 1 py inject_pan.py
echo.
echo You can close this window and launch the game.
pause
