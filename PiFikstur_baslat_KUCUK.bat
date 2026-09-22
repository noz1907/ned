@echo off
REM ==========================================================================
REM  PiFikstur - KUCUK KURULUM, dar disk icin
REM
REM  Ilk calistirmada bu klasorde .venv adinda ayri bir Python ortami kurar
REM  ve gerekli paketleri oraya yukler. Boylece bilgisayardaki diger Python
REM  kurulumlarina - tensorflow, pandas, scikit-learn - dokunmaz.
REM  Sonraki calistirmalarda dogrudan programi acar.
REM
REM  Normal kurulum yaklasik 1,2 GB yer kaplar. Bu dosya cadquery-ocp'nin
REM  vtk'siz gelen 7.7.2 surumunu kurar: yaklasik 800 MB. Sonuc birebir
REM  aynidir. Python 3.8 - 3.11 gerekir.
REM ==========================================================================
setlocal
cd /d "%~dp0"
set ISTEK=requirements-kucuk.txt
set ETIKET=Kucuk kurulum: yaklasik 800 MB.

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
echo  https://www.python.org/downloads/ adresinden Python 3.10 ya da 3.11 kurun,
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
echo   1 - Disk hala darsa once su komutu calistirin:  pip cache purge
echo   2 - Python 3.12 ve ustundeyseniz bu dosya calismaz,
echo       PiFikstur_baslat.bat kullanin.
echo   3 - Internet baglantisini kontrol edin.
echo.
echo  Sorunu giderip bu dosyayi tekrar calistirin, kaldigi yerden devam eder.
echo.
pause
exit /b 1

:CALISTIR
".venv\Scripts\python.exe" pf3_gui.py
if errorlevel 1 pause
endlocal
