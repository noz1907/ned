@echo off
REM ==========================================================================
REM  Pi3D'u calistirilabilir dosyaya (.exe) cevirir.
REM
REM  Once Pi3D_baslat.bat ile .venv kurulmus olmali.
REM  Iki surum vardir, secim sorulur:
REM    1 = PI3D  : Pi3D ve PiVision logolari gomulur, FIRMA ANTETI YOK
REM                (paftanin sag alt kosesi bos kalir, yalniz cerceve
REM                 cizgileri olur; kendi antetinizi oraya yapistirirsiniz)
REM    2 = FIRMA : Pi3D logolari KONMAZ, bunun yerine antet klasorundeki
REM                FIRMA ANTETI kullanilir - cerceve, bolge isaretleri,
REM                antet ve firma logosu firmanin kendi ciziminden gelir,
REM                kutulari (Part Name, Drawing No, Material, Weight,
REM                Scale, Drawn/Checked, FILE) Pi3D doldurur.
REM
REM  Sormasini istemiyorsaniz once set PI3D_LOGO=1 / 0 verin, ya da
REM  EXE_YAP.bat 1   /   EXE_YAP.bat 2  diye calistirin.
REM
REM  Cikti:  dist\Pi3D\Pi3D.exe
REM
REM  Olusan klasor Python kurulu OLMAYAN bilgisayarlarda da calisir;
REM  klasorun tamamini kopyalayin, tek basina .exe yetmez.
REM ==========================================================================
setlocal
cd /d "%~dp0"

REM ---- logolu mu logosuz mu -------------------------------------------
if not "%~1"=="" set "PI3D_LOGO=%~1"
REM  Menude 2 = logosuz; spec 0 bekler.
if "%PI3D_LOGO%"=="2" set "PI3D_LOGO=0"
if not "%PI3D_LOGO%"=="" goto SECILDI
echo.
echo  Hangi surum derlensin?
echo.
echo    1 = PI3D     PiVision ve Pi3D logolari exe'nin ICINE gomulur.
echo                 Paftada FIRMA ANTETI YOKTUR: sag alt kosede
echo                 150x100 mm'lik alan bos birakilir, kendi
echo                 antetinizi oraya yapistirirsiniz.
echo.
echo    2 = FIRMA    Pi3D logolari konmaz; baslikta yalniz "Pi3D" yazar.
echo                 Bunun yerine antet klasorundeki FIRMA ANTETI
echo                 kullanilir: cerceve, bolge isaretleri, antet ve
echo                 firma logosu firmanin kendi ciziminden gelir.
echo                 Part Name, Drawing No, Material, Weight, Scale,
echo                 Drawn/Checked ve FILE kutularini Pi3D doldurur;
echo                 tarih, cizen ve onaylayan programda sorulur.
echo.
set "PI3D_LOGO="
set "SECIM="
set /p SECIM=  Seciminiz [1]: 
if "%SECIM%"=="2" (set "PI3D_LOGO=0") else (set "PI3D_LOGO=1")

:SECILDI
if "%PI3D_LOGO%"=="0" (
  echo  FIRMA surumu derlenecek: Pi3D logosu yok, firma anteti var.
  if not exist "antet\*.json" (
    echo.
    echo  DIKKAT: antet klasorunde hazir sablon yok.
    echo  Program antetsiz calisir; antet eklemek icin firmanin
    echo  cerceve+antet DXF'ini su komutla sablona cevirin:
    echo      .venv\Scripts\python.exe pf5_antet.py --yardim
    echo.
  )
) else (
  echo  PI3D surumu derlenecek: logolar gomulu, firma anteti yok.
)

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
if "%PI3D_LOGO%"=="0" (echo  Tamam - FIRMA surumu: firma anteti kullanilir.) else (echo  Tamam - PI3D surumu, logolar exe'nin icinde, antet yok.)
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
