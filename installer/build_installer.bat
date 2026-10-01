@echo off
REM  Pi3D - Kurulum Sihirbazi (.exe) uretici  (PiVision)
REM  Once exe derlenmis olmali:  py exebuild.py   (dist\Pi3D_v<surum>\Pi3D)
setlocal
chcp 65001 >nul 2>&1
title Pi3D - Kurulum Sihirbazi Uret
cd /d "%~dp0.."
set "PROJ=%CD%"
set "PYEXE="
where python >nul 2>&1 && set "PYEXE=python"
if not defined PYEXE ( where py >nul 2>&1 && set "PYEXE=py" )
if not defined PYEXE if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
if not defined PYEXE ( echo [HATA] Python bulunamadi. & goto :fail )
set "VER="
for /f "usebackq delims=" %%V in (`%PYEXE% -c "import pf7_is;print(pf7_is.PI3D_SURUM)" 2^>nul`) do set "VER=%%V"
if not defined VER ( echo [HATA] Surum okunamadi ^(pf7_is.PI3D_SURUM^). & goto :fail )
echo   Surum: %VER%
set "SRC=%PROJ%\dist\Pi3D_v%VER%\Pi3D"
if not exist "%SRC%\Pi3D.exe" if exist "%PROJ%\dist\Pi3D_v%VER%.zip" (
  echo   Klasor yok, zip'ten aciliyor...
  powershell -NoProfile -Command "Expand-Archive -LiteralPath '%PROJ%\dist\Pi3D_v%VER%.zip' -DestinationPath '%PROJ%\dist\Pi3D_v%VER%' -Force"
)
if not exist "%SRC%\Pi3D.exe" (
  echo [UYARI] Program dosyalari yok: "%SRC%\Pi3D.exe"
  echo   Once derleyin:  %PYEXE% exebuild.py
  goto :fail
)
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
  echo [HATA] Inno Setup 6 bulunamadi:  https://jrsoftware.org/isdl.php
  goto :fail
)
echo   Inno Setup: %ISCC%
"%ISCC%" "installer\Pi3D_Setup.iss" /DMyVer="%VER%" /DMySrc="%SRC%"
if errorlevel 1 ( echo [HATA] Derleme basarisiz. & goto :fail )
echo.
echo   TAMAM: %PROJ%\installer\Output\Pi3D_Kurulum_v%VER%.exe
echo   Bu TEK dosyayi musteriye verin.
goto :end
:fail
echo   (Yukaridaki mesaji okuyun.)
:end
pause
endlocal
