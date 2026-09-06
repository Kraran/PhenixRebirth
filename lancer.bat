@echo off
title Phenix Rebirth
cd /d "%~dp0"

echo.
echo  ========================================
echo         PHENIX REBIRTH - Launch
echo  ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERREUR] Python n'est pas installe.
    pause
    exit /b 1
)

echo  Lancement du jeu...
echo  Log : %cd%\boot.log
echo.
python -u main.py
set EXITCODE=%ERRORLEVEL%
echo.
echo  exit=%EXITCODE%
if exist boot.log (
    echo  --- boot.log ---
    type boot.log
    echo  ----------------
)
if %EXITCODE% NEQ 0 (
    echo  [ERREUR] Le jeu a plante. Copie boot.log.
    pause
    exit /b %EXITCODE%
)
exit /b 0
