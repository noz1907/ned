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
REM  vtk'siz gelen 7.7.2 surumunu kurar: yaklasik 800 MB. Bu program vtk
REM  kullanmadigi icin sonuc birebir aynidir; 41 komponentin olculeri,
REM  kutleleri ve montaj gabarisi guncel surumle ayni cikacak sekilde
REM  dogrulandi.  Python 3.8 - 3.11 gerekir.
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
echo  Kucuk kurulum: ayri Python ortami kuruluyor, yaklasik 800 MB.
echo  Birkac dakika surebilir...
echo.

if exist ".venv\Scripts\python.exe" goto PAKETLER
py -3 -m venv .venv
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if not exist ".venv\Scripts\python.exe" goto YOK_PYTHON

:PAKETLER
REM --no-cache-dir: pip indirdigini bir de onbellekte tutmasin,
REM ayni dosya iki kere yer kaplamasin.
".venv\Scripts\python.exe" -m pip install --no-cache-dir -r requirements-kucuk.txt
if errorlevel 1 goto KURULMADI

echo.
echo  Kurulum tamam.
echo.
goto CALISTIR

:YOK_PYTHON
echo.
echo  HATA: Python bulunamadi.
echo  https://www.python.org/downloads/ adresinden Python 3.10 ya da 3.11
echo  kurun, kurarken "Add Python to PATH" kutusunu isaretleyin.
echo.
pause
exit /b 1

:KURULMADI
echo.
echo  HATA: paketler kurulamadi. Sirayla deneyin:
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
