@echo off
REM ==========================================================================
REM  PiFikstur'u calistirilabilir dosyaya (.exe) cevirir.
REM
REM  Once PiFikstur_baslat.bat ile .venv kurulmus olmali.
REM  Cikti:  dist\PiFikstur\PiFikstur.exe
REM
REM  Olusan klasor Python kurulu OLMAYAN bilgisayarlarda da calisir;
REM  klasorun tamamini kopyalayin, tek basina .exe yetmez.
REM ==========================================================================
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto DEVAM
echo.
echo  HATA: once PiFikstur_baslat.bat calistirilip .venv kurulmali.
echo.
pause
exit /b 1

:DEVAM
echo.
echo  PyInstaller kuruluyor...
".venv\Scripts\python.exe" -m pip install --no-cache-dir pyinstaller
if errorlevel 1 goto OLMADI

echo.
echo  Derleniyor, birkac dakika surebilir...
echo.
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean pifikstur.spec
if errorlevel 1 goto OLMADI

echo.
echo  Tamam:  dist\PiFikstur\PiFikstur.exe
echo  Bu klasorun TAMAMINI kopyalayin, tek basina exe calismaz.
echo.
pause
exit /b 0

:OLMADI
echo.
echo  HATA: derleme tamamlanamadi. Yukaridaki mesaja bakin.
echo.
pause
exit /b 1
