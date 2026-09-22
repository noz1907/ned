@echo off
REM ==========================================================================
REM  Pi3D'u calistirilabilir dosyaya (.exe) cevirir.
REM
REM  Once Pi3D_baslat.bat ile .venv kurulmus olmali.
REM  Cikti:  dist\Pi3D\Pi3D.exe
REM
REM  Olusan klasor Python kurulu OLMAYAN bilgisayarlarda da calisir;
REM  klasorun tamamini kopyalayin, tek basina .exe yetmez.
REM ==========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto ORTAM_YOK

REM Ortam gercekten calisiyor mu? .venv'i kuran Python kaldirilmis ya da
REM tasinmis olabilir; o zaman python.exe "No Python at ..." deyip cikar.
".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
if errorlevel 1 goto ORTAM_BOZUK

".venv\Scripts\python.exe" -c "import OCP, ezdxf" >nul 2>&1
if errorlevel 1 goto PAKET_EKSIK

echo.
echo  PyInstaller kuruluyor...
".venv\Scripts\python.exe" -m pip install --no-cache-dir pyinstaller
if errorlevel 1 goto OLMADI

echo.
echo  Derleniyor, birkac dakika surebilir...
echo.
echo  NOT: Akan yazilarda WARNING satirlari gorebilirsiniz. Uyari hata
echo  degildir, derleme devam eder. Sonunda "Tamam" yaziyorsa is bitmistir.
echo.
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean pi3d.spec
if errorlevel 1 goto OLMADI

echo.
echo  Tamam:  dist\Pi3D\Pi3D.exe
echo  Bu klasorun TAMAMINI kopyalayin, tek basina exe calismaz.
echo.
echo  Yukarida WARNING satirlari varsa onemli degil; derleme tamamlandi.
echo  Denemek icin exe yi acip bir STEP dosyasi okutun, DXF uretiyorsa tamamdir.
echo.
pause
exit /b 0

:ORTAM_YOK
echo.
echo  HATA: .venv ortami yok.
echo  Once Pi3D_baslat.bat dosyasini calistirin.
echo.
pause
exit /b 1

:ORTAM_BOZUK
echo.
echo  HATA: .venv ortami var ama calismiyor.
echo  "No Python at ..." mesaji goruyorsaniz sebebi sudur: bu ortami kuran
echo  Python surumu kaldirilmis, guncellenmis ya da baska klasore tasinmis.
echo  Sanal ortam eski yolu hatirladigi icin acilamiyor.
echo.
echo  Cozum: .venv klasorunu silip Pi3D_baslat.bat dosyasini calistirin.
echo  Yeni baslatici bunu kendisi fark edip ortami yeniler.
echo.
pause
exit /b 1

:PAKET_EKSIK
echo.
echo  HATA: .venv icinde gerekli paketler yok.
echo  Once Pi3D_baslat.bat dosyasini calistirip kurulumu tamamlayin.
echo.
pause
exit /b 1

:OLMADI
echo.
echo  HATA: derleme tamamlanamadi. Yukaridaki mesaja bakin.
echo  Disk doluysa "No space left on device" ya da "Errno 28" yazar;
echo  derleme icin yaklasik 2 GB bos alan gerekir.
echo.
pause
exit /b 1
