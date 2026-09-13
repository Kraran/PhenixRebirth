@echo off
title Phenix Rebirth - Build EXE
cd /d "%~dp0"

echo.
echo  Building PhenixRebirth.exe (folder mode, more reliable)...
echo.

python -m pip install --upgrade pyinstaller pygame
if errorlevel 1 (
    echo [ERREUR] pip / pyinstaller
    pause
    exit /b 1
)

python -m PyInstaller --noconfirm --clean --windowed --name "PhenixRebirth" ^
  --icon "assets\icon.ico" ^
  --paths src ^
  --add-data "src;src" ^
  --add-data "assets;assets" ^
  --hidden-import game ^
  --hidden-import settings ^
  --hidden-import player ^
  --hidden-import enemy ^
  --hidden-import boss ^
  --hidden-import explosion ^
  --hidden-import starfield ^
  --hidden-import sounds ^
  --hidden-import i18n ^
  --hidden-import highscores ^
  main.py

if errorlevel 1 (
    echo.
    echo  [ERREUR] Build failed.
    pause
    exit /b 1
)

echo.
echo  OK - Executable folder:
echo    dist\PhenixRebirth\PhenixRebirth.exe
echo.
echo  Zip the whole folder dist\PhenixRebirth to distribute.
echo.
pause
