@echo off
REM ==========================================================================
REM  PiFikstur - tek tikla baslatma (Windows)
REM
REM  Ilk calistirmada bu klasorde .venv adinda ayri bir Python ortami kurar
REM  ve gerekli paketleri oraya yukler. Boylece bilgisayarindaki diger
REM  Python kurulumlarina (tensorflow, pandas, scikit-learn vb.) dokunmaz.
REM  Sonraki calistirmalarda dogrudan programi acar.
REM ==========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  Ilk calistirma: ayri Python ortami kuruluyor, birkac dakika surebilir...
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
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  HATA: paketler kurulamadi. Internet baglantisini kontrol edin.
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
