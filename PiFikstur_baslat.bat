@echo off
REM ==========================================================================
REM  PiFikstur - tek tikla baslatma (Windows)
REM
REM  Ilk calistirmada bu klasorde .venv adinda ayri bir Python ortami kurar
REM  ve gerekli paketleri oraya yukler. Boylece bilgisayardaki diger Python
REM  kurulumlarina - tensorflow, pandas, scikit-learn - dokunmaz.
REM  Sonraki calistirmalarda dogrudan programi acar.
REM
REM  Gereken bos disk alani: yaklasik 1,3 GB.
REM  Diskiniz darsa: PiFikstur_baslat_KUCUK.bat - yaklasik 800 MB.
REM ==========================================================================
setlocal
cd /d "%~dp0"

REM Ortam var mi ve paketleri tam mi? Yarim kalmis kurulumda da tamamlar.
if not exist ".venv\Scripts\python.exe" goto KUR
".venv\Scripts\python.exe" -c "import OCP, ezdxf" >nul 2>&1
if errorlevel 1 goto KUR
goto CALISTIR

:KUR
echo.
echo  Ayri Python ortami kuruluyor.
echo  Yaklasik 150 MB indirilecek, 1,3 GB bos disk alani gerekiyor.
echo  Birkac dakika surebilir...
echo.

if exist ".venv\Scripts\python.exe" goto PAKETLER
py -3 -m venv .venv
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" goto YOK_PYTHON

:PAKETLER
REM --no-cache-dir: pip indirdigini bir de onbellekte tutmasin,
REM ayni dosya iki kere yer kaplamasin.
".venv\Scripts\python.exe" -m pip install --no-cache-dir -r requirements.txt
if errorlevel 1 goto KURULMADI

echo.
echo  Kurulum tamam.
echo.
goto CALISTIR

:YOK_PYTHON
echo.
echo  HATA: Python bulunamadi.
echo  https://www.python.org/downloads/ adresinden Python 3.10+ kurun,
echo  kurarken "Add Python to PATH" kutusunu isaretleyin.
echo.
pause
exit /b 1

:KURULMADI
echo.
echo  HATA: paketler kurulamadi. Sik gorulen iki sebep:
echo.
echo   1 - DISK DOLU.  Hata satirinda "No space left on device"
echo       ya da "Errno 28" yaziyorsa budur. Cozum sirasiyla:
echo         pip cache purge
echo         PiFikstur_baslat_KUCUK.bat ile kucuk kurulum, yaklasik 800 MB
echo         ya da bu klasoru bos alani olan baska bir surucuye tasiyin
echo.
echo   2 - INTERNET baglantisi yok ya da kesildi.
echo.
echo  Sorunu giderip bu dosyayi tekrar calistirin, kaldigi yerden devam eder.
echo.
pause
exit /b 1

:CALISTIR
".venv\Scripts\python.exe" pf3_gui.py
if errorlevel 1 pause
endlocal
