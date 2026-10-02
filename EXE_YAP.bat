@echo off
REM ==========================================================================
REM  Pi3D'u calistirilabilir dosyaya (.exe) cevirir.  TEK SURUM.
REM
REM  Once Pi3D_baslat.bat ile .venv kurulmus olmali.
REM
REM  Antet derlemede SECILMEZ, calisma aninda lisansa gore belirlenir:
REM    - deneme lisansi : her pafta Pi3D / PiVision antetli
REM    - tam lisans     : Yardim > Firma anteti ile verilen A3 antet DXF'i
REM                       (program kutulari olcup esler, sablon ayara
REM                        kaydedilir, sonradan degistirilir / kaldirilir)
REM
REM  Musteriye giden kurulum paketi icin:  py exebuild.py
REM  (PyInstaller + bariyer + zip + Inno Setup kurulum sihirbazi)
REM
REM  Cikti:  dist\Pi3D\Pi3D.exe   (klasorun tamami gerekir, tek exe yetmez)
REM ==========================================================================
setlocal
cd /d "%~dp0"
set "PI3D_LOGO=1"
if exist ".venv\Scripts\python.exe" (set "PYEXE=.venv\Scripts\python.exe") else (set "PYEXE=python")
echo.
echo  Pi3D exe derleniyor (tek surum)...
"%PYEXE%" -m PyInstaller --noconfirm --clean pi3d.spec
if errorlevel 1 (
  echo.
  echo  [HATA] Derleme basarisiz - yukaridaki ciktiya bakin.
  pause
  exit /b 1
)
echo.
echo  Tamam: dist\Pi3D\Pi3D.exe
echo  Kurulum paketi (musteri) icin: py exebuild.py
pause
