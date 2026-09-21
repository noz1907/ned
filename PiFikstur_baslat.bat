@echo off
REM ==========================================================================
REM  PiFikstur - tek tikla baslatma (Windows)
REM
REM  Ilk calistirmada bu klasorde .venv adinda ayri bir Python ortami kurar
REM  ve gerekli paketleri oraya yukler. Boylece bilgisayarindaki diger
REM  Python kurulumlarina (tensorflow, pandas, scikit-learn vb.) dokunmaz.
REM  Sonraki calistirmalarda dogrudan programi acar.
REM
REM  Gereken bos disk alani: yaklasik 1,3 GB.
REM ==========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  Ilk calistirma: ayri Python ortami kuruluyor.
    echo  Yaklasik 150 MB indirilecek, 1,3 GB bos disk alani gerekiyor.
    echo  Birkac dakika surebilir...
    echo.
    py -3 -m venv .venv
    if errorlevel 1 python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo  HATA: Python bulunamadi.
        echo  https://www.python.org/downloads/ adresinden Python 3.10+ kurun,
        echo  kurarken "Add Python to PATH" kutusunu isaretleyin.
        echo.
        pause
        exit /b 1
    )
    REM --no-cache-dir: pip indirdigini bir de onbellekte tutmasin,
    REM ayni dosya iki kere yer kaplamasin.
    ".venv\Scripts\python.exe" -m pip install --no-cache-dir -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  HATA: paketler kurulamadi. Sik gorulen iki sebep:
        echo.
        echo    1) DISK DOLU  ("No space left on device" / "Errno 28")
        echo       Bu surucudeki bos alan:
        for /f "tokens=3" %%A in ('dir /-c "%~d0\" ^| findstr /C:"bytes free"') do echo       %%A bayt
        echo       Yer acmak icin:  pip cache purge
        echo       Ya da bu klasoru bos alani olan baska bir surucuye tasiyin.
        echo.
        echo    2) INTERNET baglantisi yok ya da kesildi.
        echo.
        echo  Yarim kalan ortam siliniyor, sorunu giderip tekrar calistirin.
        rmdir /s /q .venv
        echo.
        pause
        exit /b 1
    )
    echo.
    echo  Kurulum tamam.
    echo.
)

".venv\Scripts\python.exe" pf3_gui.py
if errorlevel 1 pause
endlocal
