@echo off
REM ==========================================================================
REM  PiFikstur - KUCUK KURULUM (dar disk icin)
REM
REM  Normal kurulum ~1,2 GB yer kaplar. Bu dosya cadquery-ocp'nin vtk'siz
REM  gelen 7.7.2 surumunu kurar: ~800 MB. Bu program vtk kullanmadigi icin
REM  sonuc birebir aynidir (41 komponentin olculeri, kutleleri ve montaj
REM  gabarisi guncel surumle ayni cikacak sekilde dogrulandi).
REM
REM  Python 3.8 - 3.11 gerekir. 3.12 ve ustundeyseniz PiFikstur_baslat.bat
REM  kullanin.
REM ==========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  Kucuk kurulum: ayri Python ortami kuruluyor ^(~800 MB^)...
    echo.
    py -3 -m venv .venv
    if errorlevel 1 python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo  HATA: Python bulunamadi.
        echo  https://www.python.org/downloads/ adresinden Python 3.10 ya da
        echo  3.11 kurun, kurarken "Add Python to PATH" kutusunu isaretleyin.
        echo.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --no-cache-dir -r requirements-kucuk.txt
    if errorlevel 1 (
        echo.
        echo  HATA: paketler kurulamadi.
        echo  Bu surucudeki bos alan:
        for /f "tokens=3" %%A in ('dir /-c "%~d0\" ^| findstr /C:"bytes free"') do echo     %%A bayt
        echo.
        echo  Yer acmak icin once su komutu deneyin:   pip cache purge
        echo  Python 3.12+ kullaniyorsaniz bu dosya calismaz,
        echo  PiFikstur_baslat.bat kullanin.
        echo.
        echo  Yarim kalan ortam siliniyor.
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
