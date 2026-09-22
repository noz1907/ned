@echo off
REM ==========================================================================
REM  Pi3D - tek tikla baslatma (Windows)
REM
REM  Ilk calistirmada bu klasorde .venv adinda ayri bir Python ortami kurar
REM  ve gerekli paketleri oraya yukler. Boylece bilgisayardaki diger Python
REM  kurulumlarina - tensorflow, pandas, scikit-learn - dokunmaz.
REM  Sonraki calistirmalarda dogrudan programi acar.
REM
REM  Gereken bos disk alani: yaklasik 1,3 GB.
REM  Diskiniz darsa: Pi3D_baslat_KUCUK.bat - yaklasik 800 MB.
REM ==========================================================================
setlocal
cd /d "%~dp0"
set ISTEK=requirements.txt
set ETIKET=Yaklasik 150 MB indirilecek, 1,3 GB bos disk alani gerekiyor.

REM --- 1) Ortam var mi?
if not exist ".venv\Scripts\python.exe" goto YENI_ORTAM

REM --- 2) Ortam CALISIYOR mu? Python kaldirilmis/tasinmis olabilir; o zaman
REM        .venv icindeki python.exe "No Python at ..." deyip cikar.
".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
if errorlevel 1 goto BOZUK_ORTAM

REM --- 3) Paketler tam mi?
".venv\Scripts\python.exe" -c "import OCP, ezdxf" >nul 2>&1
if errorlevel 1 goto PAKETLER
goto CALISTIR

:BOZUK_ORTAM
echo.
echo  Onceki .venv ortami calismiyor.
echo  Sebebi genelde sudur: ortami kuran Python surumu kaldirilmis,
echo  guncellenmis ya da baska bir klasore tasinmis. Ortam yenileniyor...
echo.
rmdir /s /q .venv

:YENI_ORTAM
echo.
echo  Ayri Python ortami kuruluyor.
echo  %ETIKET%
echo  Birkac dakika surebilir...
echo.
py -3 -m venv .venv
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" goto YOK_PYTHON
".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
if errorlevel 1 goto YOK_PYTHON

:PAKETLER
REM --no-cache-dir: pip indirdigini bir de onbellekte tutmasin,
REM ayni dosya iki kere yer kaplamasin.
".venv\Scripts\python.exe" -m pip install --no-cache-dir -r %ISTEK%
if errorlevel 1 goto KURULMADI
echo.
echo  Kurulum tamam.
echo.
goto CALISTIR

:YOK_PYTHON
echo.
echo  HATA: calisan bir Python bulunamadi.
echo  https://www.python.org/downloads/ adresinden Python 3.10+ kurun,
echo  kurarken "Add Python to PATH" kutusunu isaretleyin, sonra bu dosyayi
echo  tekrar calistirin.
echo.
echo  Kurulu oldugunu dusunuyorsaniz su komutla dogrulayin:   py -3 -V
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
echo         Pi3D_baslat_KUCUK.bat ile kucuk kurulum, yaklasik 800 MB
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
