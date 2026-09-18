@echo off
cd /d "%~dp0"
echo ========================================
echo  PHENIX REBIRTH - Restaure EQ .pheq
echo ========================================
python "%~dp0_patch_eq.py"
if errorlevel 1 (
  echo [ERREUR] Patch rate.
  pause
  exit /b 1
)
echo OK. Relance le jeu.
pause
