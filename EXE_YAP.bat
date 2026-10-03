@echo off
REM ==========================================================================
REM  Pi3D derleme.  Iki secenek:
REM    1  Yalniz exe (gelistirici):  PyInstaller pi3d.spec
REM                                  -> dist\Pi3D\Pi3D.exe (klasorun tamami gerekir)
REM    2  Musteri kurulum paketi:    py exebuild.py
REM                                  PyInstaller + bariyer (kaynak kod / anahtar /
REM                                  lisans masasi pakette YOK) + zip + Inno Setup
REM                                  -> installer\Output\Pi3D_Kurulum_v<surum>.exe
REM
REM  Once Pi3D_baslat.bat ile .venv kurulmus olmali.
REM  Antet derlemede SECILMEZ, calisma aninda lisansa gore belirlenir
REM  (deneme: Pi3D / PiVision anteti; tam lisans: Yardim > Firma anteti).
REM ==========================================================================
setlocal
cd /d "%~dp0"
set "PI3D_LOGO=1"
if exist ".venv\Scripts\python.exe" (set "PYEXE=.venv\Scripts\python.exe") else (set "PYEXE=python")
echo.
echo  Pi3D derleme
echo    1  Yalniz exe (gelistirici denemesi)        : dist\Pi3D\Pi3D.exe
echo    2  Musteri kurulum paketi (bariyer + Inno)  : installer\Output\Pi3D_Kurulum_v...exe
echo    3  Ikisi de (once exe, sonra paket)
echo.
set "SECIM=%~1"
if "%SECIM%"=="" set /p SECIM="Secim [1/2/3] (varsayilan 2): "
if "%SECIM%"=="" set "SECIM=2"
if "%SECIM%"=="1" goto EXE
if "%SECIM%"=="2" goto PAKET
if "%SECIM%"=="3" goto IKISI
echo  Gecersiz secim: %SECIM%
pause
exit /b 1

:EXE
echo.
echo  [exe] PyInstaller derliyor...
"%PYEXE%" -m PyInstaller --noconfirm --clean pi3d.spec
if errorlevel 1 (
  echo.
  echo  [HATA] Derleme basarisiz - yukaridaki ciktiya bakin.
  pause
  exit /b 1
)
echo.
echo  Tamam: dist\Pi3D\Pi3D.exe
pause
exit /b 0

:PAKET
echo.
echo  [paket] exebuild.py: PyInstaller + bariyer + zip + Inno Setup...
"%PYEXE%" exebuild.py
if errorlevel 1 (
  echo.
  echo  [HATA] Paket basarisiz - yukaridaki ciktiya bakin.
  pause
  exit /b 1
)
echo.
echo  Tamam: installer\Output\Pi3D_Kurulum_v*.exe
pause
exit /b 0

:IKISI
echo.
echo  [exe] PyInstaller derliyor...
"%PYEXE%" -m PyInstaller --noconfirm --clean pi3d.spec
if errorlevel 1 (
  echo  [HATA] exe derlemesi basarisiz.
  pause
  exit /b 1
)
echo.
echo  [paket] exebuild.py...
"%PYEXE%" exebuild.py
if errorlevel 1 (
  echo  [HATA] Paket basarisiz.
  pause
  exit /b 1
)
echo.
echo  Tamam: dist\Pi3D\Pi3D.exe  ve  installer\Output\Pi3D_Kurulum_v*.exe
pause
exit /b 0
