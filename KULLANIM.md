# KULLANIM

3B model dosyasından **parça listesi (BOM)**, **detay resimleri** ve
**montaj resmi** üretme programı. Parça farketmez, montaj farketmez — her
dosya için aynı akış çalışır. Okunan biçimler: **STEP, IGES, BREP**
(ayrıntı: "Hangi dosya biçimleri okunur").

İki kullanım yolu var, ikisi de aynı hesap motorunu çağırır:

* **`pf3_gui.py`** – pencereli arayüz, komut yazmaya gerek yok *(önerilen)*
* **`pf3_olcu.py`** – komut satırı, toplu iş ve otomasyon için

---

## 1. Kurulum (bir kereye mahsus)

Python 3.10 veya üstü gerekir. Kurulu değilse <https://www.python.org/downloads/>
adresinden indirin; kurarken **“Add Python to PATH”** kutusunu işaretleyin.

### En kolayı: `Pi3D_baslat.bat` (Windows)

Klasördeki **`Pi3D_baslat.bat`** dosyasına çift tıklayın. İlk
çalıştırmada bu klasörde `.venv` adında **ayrı bir Python ortamı** kurar,
paketleri oraya yükler ve programı açar. Sonraki çalıştırmalarda doğrudan
açar. Komut yazmanıza gerek yok.

### Elle kurmak isterseniz

> ⚠ **Paketleri ana Python'unuza kurmayın.** `cadquery`, `numpy 2`
> istiyor; `tensorflow`, `pandas 2.1`, `scikit-learn 1.3` gibi paketler ise
> `numpy 1` istiyor. İkisi aynı ortamda bir arada duramaz. Bu yüzden
> Pi3D'u **kendi sanal ortamında** çalıştırın — hem bu program çalışır,
> hem mevcut kurulumunuz bozulmaz.

Windows'ta, bu klasörde komut penceresi açıp:

```
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Bundan sonra her yeni komut penceresinde önce `.venv\Scripts\activate`
yazın; satır başında `(.venv)` görürseniz doğru ortamdasınız.

Linux / macOS:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Kurulan paketler: `cadquery-ocp` (OpenCascade — STEP okuma/geometri),
`ezdxf` (DXF yazma), `matplotlib` (önizleme). Yaklaşık **150 MB indirme,
1,3 GB boş disk** ister (cadquery ile birlikte 1,8 GB idi).

> `cadquery` paketi **gerekmez**. Kod doğrudan OCP kullanır; `cadquery`
> beraberinde `casadi`, `numba`, `llvmlite`, `scipy`, `trame` gibi
> ~350 MB'lık, bu programın kullanmadığı bağımlılık getiriyordu.
>
> `pf2_fikstur.py` ve `pfd_dxf2stp.py` kullanacaksanız onlar için
> `pip install -r requirements-ekstra.txt` gerekir (cadquery + shapely).

> `tkinter` ayrıca kurulmaz, Python ile birlikte gelir. (Yalnız Linux'ta
> bazı dağıtımlarda ayrı paket olabilir: `sudo apt install python3-tk`.)

### Kurulumda "No space left on device" / "Errno 28"

Disk dolu demektir. Boş alan açmanın en hızlı yolu pip'in indirme
önbelleğini temizlemek (genelde birkaç yüz MB):

```
pip cache purge
```

Yetmezse Pi3D klasörünü boş alanı olan başka bir sürücüye taşıyıp
`Pi3D_baslat.bat`'ı oradan çalıştırın; `.venv` o sürücüde kurulur.

Üçüncü yol — **küçük kurulum** (~800 MB):

```
.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-kucuk.txt
```

`cadquery-ocp`'nin 7.7.2 sürümü `vtk`'sız gelir; bu program `vtk`
kullanmadığı için sonuç birebir aynıdır (`parca.stp` üzerinde 41
komponentin bütün ölçüleri, kütleleri, delik/radüs sayıları ve montaj
gabarisi güncel sürümle aynı çıktı; 16 çizimin hepsinde kesit taraması
oluştu). Hazır paketi Python 3.8–3.11 için vardır; 3.12 ve üstündeyseniz
normal `requirements.txt` kullanın.

Kurulumun tamam olduğunu görmek için:

```
python pf3_olcu.py --malzeme-liste
```

Malzeme tablosu ekrana gelirse her şey hazır demektir.

### "No Python at '...\Python311\python.exe'"

`.venv` klasörü duruyor ama içindeki Python açılmıyor. Sanal ortam, kendisini
kuran Python'un **yolunu hatırlar** (`\.venv\pyvenv.cfg` içindeki `home`
satırı); o Python kaldırılmış, güncellenmiş ya da başka bir klasöre taşınmışsa
ortam ölür.

Çözüm: **`.venv` klasörünü silin**, `Pi3D_baslat.bat`'ı çalıştırın.
Güncel başlatıcı bu durumu kendisi fark edip ortamı yeniler — ölçüt olarak
`.venv\Scripts\python.exe` dosyasının varlığına değil, gerçekten
**çalışıp çalışmadığına** bakar.

Python'un kurulu olduğunu doğrulamak için:

```
py -3 -V
```

Sürüm yazmıyorsa Python yok demektir; <https://www.python.org/downloads/>
adresinden kurun, kurarken **"Add Python to PATH"** işaretli olsun.

### Ana Python'a kurduysanız ve diğer paketleriniz bozulduysa

`pip install -r requirements.txt` komutunu doğrudan ana Python'unuzda
çalıştırdıysanız `numpy`, `scipy` ve `matplotlib` yükseltilmiş, bu da
`tensorflow` / `pandas` / `scikit-learn` gibi paketleri kırmış olabilir.
Eski hâle döndürmek için:

```
pip install "numpy==1.26.4" "scipy==1.12.0" "matplotlib==3.8.2"
```

Sonra Pi3D'u yukarıdaki gibi kendi `.venv` ortamında çalıştırın; iki
kurulum birbirine karışmaz.

### Çalıştırılabilir dosya (.exe) yapmak

Python kurulu olmayan bilgisayarlarda da çalışsın istiyorsanız:

```
EXE_YAP.bat
```

Önce `Pi3D_baslat.bat` ile `.venv` kurulmuş olmalı. Bu dosya
PyInstaller'ı kurar ve `pi3d.spec` tarifine göre derler.

Çıktı: **`dist\Pi3D\Pi3D.exe`**

> **Klasörün tamamını kopyalayın, tek başına `.exe` çalışmaz.** OpenCascade
> kütüphanesi yanındaki DLL'lerle birlikte gelir; klasör ~1 GB olur.
>
> Tek dosyalık (`--onefile`) sürüm **önerilmez**: 1 GB'lık içerik her
> açılışta geçici klasöre açılır, program 1-2 dakikada açılır ve disk iki
> kat yer kaplar. `onedir` sürümü anında açılır.

Derleme yalnız **çalıştırıldığı işletim sistemi için** üretir: Windows'ta
derlerseniz Windows `.exe`'si çıkar, Linux'ta derlerseniz Linux çalıştırılabiliri.

#### Derlerken çıkan uyarılar

```
WARNING: Failed to collect submodules for 'OCP.TopoDS.TopoDS' because
importing 'OCP.TopoDS.TopoDS' raised:
ModuleNotFoundError: No module named 'OCP.TopoDS.OCP'
```

**Bu bir hata değil, zararsız bir uyarıdır.** Sebebi: OCP'de her modülün
içinde kendi adıyla bir isim vardır (`OCP.TopoDS` modülünün içinde
`TopoDS`). PyInstaller alt modülleri gezerken bunu da bir alt modül sanıp
`OCP.TopoDS.TopoDS` diye içeri almaya çalışır, bulamaz ve bu satırı basar.
Toplama kaldığı yerden devam eder: **OCP'nin 321 modülünün hepsi, `TopoDS`
dahil, pakete girer.**

`pi3d.spec` bu satırı `on_error="ignore"` ile susturur; toplanan
dosyalarda hiçbir değişiklik olmaz. Eski bir spec dosyanız varsa uyarıyı
görmezden gelebilirsiniz.

**Derlemenin gerçekten tuttuğunu nasıl anlarsınız:** derleme bittikten
sonra `dist\Pi3D\Pi3D.exe` açılıyor ve bir STEP dosyasını
okuyup DXF üretiyorsa iş tamamdır. Paketlenmiş program ile Python'dan
çalıştırılan program **aynı sayıları** vermelidir; burada denendi, aynı
DXF çıktı (167 varlık, toplam çizgi boyu 1889,8418 mm).

Derleme durursa (uyarı değil, **ERROR** ya da `Build failed`), sık sebep
disk doludur: paket klasörü ~700 MB, derleme sırasında geçici olarak iki
katı yer ister.

---

## 1b. Logolar ve ikon — logolu / logosuz sürüm

İki sürüm derlenebilir. `EXE_YAP.bat` derlemeye başlarken sorar:

```
  1 = LOGOLU    PiVision ve Pi3D logoları exe'nin İÇİNE gömülür;
                yanındaki klasörden silinemez, değiştirilemez.
  2 = LOGOSUZ   hiç logo konmaz; başlıkta yalnız "Pi3D" yazar,
                exe'nin kendi ikonu da olmaz.
```

Sormasını istemiyorsanız `EXE_YAP.bat 1` / `EXE_YAP.bat 2`, ya da
derlemeden önce `set PI3D_LOGO=0` (logosuz) / `=1` (logolu).

### Logolu sürüm

Program açıldığında üstte koyu bir şerit görürsünüz: solda **PiVision**
logosu, sağda uygulama adı ve ikonu. Pencerenin ve `.exe`'nin ikonu da
uygulama ikonudur.

Logolar **koda gömülüdür** (`pi3d_logo.py`): exe'nin içindedirler,
yanındaki klasörden silinemez ya da değiştirilemezler. `logo/` klasörü
de pakete konur ama program önce gömülü kopyayı kullanır — kaynak
koddan çalıştıranlar klasördekini görür.

Kaynak dosyalar `logo/` klasöründedir ve **her ölçü ayrı ayrı** hazırdır:

* `pi3d.ico` – 16/24/32/48/64/128/256 boyutları tek dosyada. Windows
  görev çubuğunda 32'yi, masaüstünde 48'i, dosya gezgininde 256'yı ister;
  hepsi içinde olduğu için ikon hiçbir yerde bulanık çıkmaz.
* `pi3d_16.png` … `pi3d_1024.png` – Windows dışı ve belge için.
  Üst şeritte 72 px'lik olanı kullanılıyor.
* `pivision_64.png` / `_56` / `_44` / `_32` – arayüz şeridi için hazır
  boyutlar; şeritte 64 px'lik kullanılıyor.

Logoyu değiştirmek isterseniz aynı adla, aynı ölçüde yenisini koyun,
sonra **gömülü kopyayı tazeleyin**:

```bash
python logo_gom.py
```

Bu komut `logo/` klasöründen `pi3d_logo.py`'yi yeniden üretir. Yapmazsanız
kaynak koddan çalıştırdığınızda yeni logoyu görürsünüz ama exe'de eskisi
kalır. Ayrıntı: `logo/OKU.md`.

### Logosuz sürüm

Gömülü modül ve `logo/` klasörü pakete hiç girmez; exe'nin kendi ikonu
da olmaz. Başlık şeridinde yalnızca büyük puntoyla **Pi3D** ve altında
açıklaması yazar. Program bunun dışında birebir aynıdır.

---

## 2. Arayüzle kullanım (kolay yol)

`Pi3D_baslat.bat`'a çift tıklayın, ya da sanal ortamı etkinleştirip:

```
python pf3_gui.py
```

Pencere adım adım ilerler; bir adım bitmeden sonraki sekme açılmaz.

### Adım 1 — VERİ

* **Model dosyası:** *Gözat…* ile `.stp` / `.step`, `.igs` / `.iges` ya da
  `.brep` dosyasını seçin (bkz. aşağıdaki biçim tablosu).
* **Kaydedilecek klasör:** boş bırakırsanız STEP'in yanına `<dosyaadı>_cikti`
  klasörü açılır. İsterseniz başka yer seçin.
* **İNCELE ▸**

STEP okunur, aynı parçanın kopyaları tek komponentte toplanır, parça /
standart eleman / kaynak dikişi ayrımı yapılır. Büyük montajlarda bu adım
bir-iki dakika sürebilir; pencere kilitlenmez, altta günlük akar.

### Adım 2 — BOM ve MALZEME

Komponentler tabloda listelenir. **KAYNAK** sütunu malzemenin nereden
geldiğini söyler:

| değer | anlamı |
|-------|--------|
| `data'dan` | STEP'in malzeme alanında ya da parça adında yazıyor (`1.4301`, `S235`, `AlMg3`, `POM`…), size sorulmaz |
| `seçim` | siz verdiniz |
| `varsayılan` | hiçbiri yoksa çelik kabul edildi |

Malzeme vermenin yolları:

* Soldaki kutudan malzemeyi seçip **Hepsine uygula**
* Tablodan satır(lar) seçip **Seçili satırlara** *(Ctrl ile çoklu seçim)*
* **malzeme.csv yaz…** ile şablon çıkarıp Excel'de doldurun, sonra
  **malzeme.csv yükle…** ile geri verin
* **CAD'inizin parça listesini** doğrudan yükleyin: CATIA'nın
  *Analyze ▸ Bill of Material* çıktısı, SolidWorks BOM'u ya da Excel'den
  kaydedilmiş bir CSV olur. `Part Number` ve `Material` sütunları
  başlıklarından bulunur (bkz. `CATIA_MALZEME.md`)

> Kutudaki malzeme yalnız **uygulanacak** malzemedir. Bir parçaya alüminyum
> verdiğinizde diğerleri çelik kalır.

**BOM ÇIKART ▸** → `BOM.csv`, `BOM.md`, `BOM_AGAC.csv`, `BOM_AGAC.md`,
`olculer.csv`, `olculer.json`, `rapor.md` yazılır. Tablo gerçek ölçü ve
kütlelerle dolar.

#### Hiyerarşik (çok kademeli) BOM

Tablo, **montaj ağacını** olduğu gibi gösterir:

```
1          ▸ 520260925 XL-S KAYAR BABA            montaj   1
1.1        ▸ 510260925-01 ...                     montaj   1
1.1.1.1    ▸ 510260901-50 GOVDE                   montaj   1
1.1.1.1.1    01.051.000.01 C-Profil-Runge XL-H    parça    1
1.1.1.1.2  ▸ 01.050.000.20 BG Mechanismus         montaj   1
1.1.1.1.2.1  01.050.000.01 U-Blech-Mechanismus    parça    1
```

Ana ürün → alt montaj → alt montajın altı… kaç kademe varsa o kadar iner.
Üstteki kutucukla düz listeye geçebilirsiniz.

> **ADET her zaman bir üst montaj başınadır** (montaj tekniğindeki alışılmış
> kural). Bir alt montaj 2 kez geçiyorsa kendi satırında `2` yazar,
> altındaki parçada o montaj başına düşen sayı yazar; ürünün tamamındaki
> sayı parantez içinde `(top …)` ve dosyada `toplam_adet` sütununda verilir.

Aynı yapı `BOM_AGAC.csv` (Excel) ve `BOM_AGAC.md` dosyalarına da yazılır;
`poz` sütunu `1.1.2.3` biçiminde kademe numarasıdır.

### Adım 3 — GÖRÜNÜŞ ve KESİT

* **Görünüşler:** ÖN, ARKA, SAĞ, SOL, ÜST, ALT arasından **en çok 4 tane**.
  Beşinciyi işaretlerseniz en eski seçim kendiliğinden kapanır.
  Yerleşim 1. açı (Avrupa/ISO-E): SAĞ sola, SOL sağa, ARKA en sağa,
  ÜST alta, ALT üste.
* **Kesit:** *olmasın (H)* ya da *A-A kesit eklensin (E)*. Kesme düzlemi
  rastgele ortadan değil, **en çok deliği açan** yerden geçer; kesilen
  malzeme taranır, kesme çizgisi görünüşe **A—A** olarak işaretlenir.
* **Çizim:** gizli çizgiler açık/kapalı, montaj resmi üretilsin mi,
  en az delik çapı (bunun altındaki silindirler delik değil radüs sayılır).
* **Örnek resim hangi parçadan üretilsin:** varsayılan olarak en çok çeşit
  delik/radüs taşıyan parça gelir; listeden değiştirebilirsiniz.

**ÖRNEK DXF ÜRET ▸**

### Adım 4 — ÖRNEK ONAY

Üretilen örnek resim pencerede gösterilir. Yazı boyutları gerçek boyutta
çizilir, yani önizlemede gördüğünüz çakışma gerçek çakışmadır.

* Beğenmediyseniz **◂ AYARA DÖN**, ayarı değiştirip yeni örnek üretin.
* DXF'i kendi CAD programınızda açmak için **DXF'i harici programda aç**.
* Beğendiyseniz **ONAYLA – TÜM ÇİZİMLERİ ÜRET ▸**

### Adım 5 — TÜM ÇİZİMLER

Bütün detay resimleri (ve istediyseniz montaj resmi) üretilir, dosyalar
listelenir. Listede bir DXF'e çift tıklarsanız önizlemesi açılır.

* **ZIP OLUŞTUR** → `cizimler.zip` (bütün DXF'ler + BOM + tablolar)
* **Klasörü aç** → çıktı klasörünü dosya yöneticisinde açar

Ağır işler arka planda çalışır: pencere kilitlenmez, ilerleme çubuğu dolar,
**İptal** çalışan adım bitince işi bırakır.

### Adım 6 — AÇINIM (bükümlü sac parçalar)

Bükümlü bir sac parçanın **düz haldeki blank ölçüsünü** ve büküm
çizgilerinin yerlerini çıkarır. BOM'u beklemez: komponentler okunur
okunmaz bu sayfa açılır.

1. Sayfa açılınca program **bükümlü sac parçaları kendisi bulur** ve
   **listede yalnız onlar kalır**; hepsi seçili gelir. Düz sac ve sac
   olmayan parçalar listeye hiç alınmaz — düz sacın açınımı zaten
   kendisidir, sac olmayanın açınımı diye bir şey yoktur. İstemediğiniz
   varsa seçimden çıkarın.
2. Gerekirse **K-faktörünü** değiştirin (ilk kurulumda 0,40).
   0,10 – 0,60 arası her değeri girebilirsiniz – 0,32 de olur;
   ondalık ayracı virgül ya da nokta olabilir. **Verdiğiniz
   değer saklanır**, bir daha girmeniz gerekmez.
3. **İŞARETLİ PARÇALARIN AÇINIMINI ÜRET** deyin.

#### Bükümlü parçalar nasıl bulunuyor

Kullanıcıya "hangileri sac?" diye sormak yanlış: bunu modelin ölçüsü
söyler. Program **silindirik yüzeylere** bakar. Bir bükümün iç ve dış
silindiri aynı eksendedir ve aralarındaki fark sac kalınlığıdır;
deliğin böyle bir eşi yoktur, köşe yuvarlatmasının ekseni ise sac
yüzüne dik durur ve boyu sac kalınlığı kadardır. Bu üçünü ayırmak
bükümü bulmaya yeter.

Tarama **açınım hesabı yapmaz**, o yüzden ucuzdur: parça başına ~20 ms,
açınım hesabıysa 15–30 saniye. 300 komponentli bir montajda hepsini
denemek saatler sürerdi; tarama saniyeler alır.

Listede her parça için ne bulunduğu yazar:

| DURUM | anlamı |
|-------|--------|
| `N büküm bulundu – açınımı çıkarılacak` | bükümlü sac; işaretlenir |
| `… (büküm eksenleri paralel değil, çıkmayabilir)` | bükümlüdür ama bükümler farklı yönlere; denenir, çıkmazsa sebebi yazılır |
| `düz sac, bükümü yok – açınımı kendisidir` | plaka; açınımı zaten parçanın kendisidir |
| `bükümlü sac değil` | freze/tornalama parçası, profil, blok |

Örnek montajda ölçüldü: 16 parçanın 7'si "bükümlü" çıktı ve açınımı
gerçekten olan **5 parçanın hepsi** bu 7'nin içindeydi — hiçbiri
kaçmadı. Kalan 2'si zaten "eksenler paralel değil" diye önceden
işaretliydi ve denemeleri saniyenin altında sürdü.

Tarama bir **ön elemedir, söz değildir.** "Bükümlü sac" çıkan bir
parçanın açınımı yine de verilemeyebilir; gerçek kararı hesap verir ve
sebebini yazar. Tarama ters yönde hata yapmamaya çalışır: bükümlü bir
parçayı elemek, onun listede hiç görünmemesi demektir.

Her parça için `P<poz>_<kod>_acinim.dxf` ve hepsi için `ACINIM.csv`
yazılır. **Açınım, detay resmiyle aynı adı taşır**, yalnız sonuna
`_acinim` eklenir:

```
P05_01_050_000_01.dxf          <- detay resmi
P05_01_050_000_01_acinim.dxf   <- açınımı
PDF/P05_01_050_000_01_A3.pdf
PDF/P05_01_050_000_01_acinim_A3.pdf
```

Eskiden açınım `A5_...` diye ayrı bir harfle başlıyordu; aynı parçanın
iki resmi klasörde yan yana durmuyordu. 7. adımda ikisi de listelenir
ve ikisinin de paftası ve PDF'i çıkar. Açınımı çıkarılamayan parçaların **nedeni** hem listede hem
`ACINIM_yapilamayanlar.txt` dosyasında yazar.

**Hesap.** Açınım genişliği, düz duvarların uzunlukları ile her bükümün
*büküm payının* toplamıdır:

```
büküm payı (BA) = büküm açısı (radyan) × (iç yarıçap + K × sac kalınlığı)
```

K-faktörü nötr eksenin sac içinde nerede olduğunu söyler; tezgâha ve
malzemeye göre değişir. Program K'yı **tahmin etmez**, size sorar:
değiştirirseniz açınım boyu değişir. İlk kurulumda 0,40'tır; 0,10 – 0,60
arası istediğiniz değeri girebilirsiniz. Verdiğiniz değer
`%LOCALAPPDATA%\Pi3D\ayarlar.json` dosyasında saklanır, her seferinde
tekrar girmenize gerek kalmaz. (Program eskiden PiFikstür adıyla
çalışıyordu; o sürümde girdiğiniz K-faktörü kaybolmaz, ilk açılışta
eski dosyadan okunur.)

Örnek (2 bükümlü, 3 mm sac, aynı parça):

| K | açınım genişliği |
|---|------------------|
| 0,40 | 129,69 mm |
| 0,32 | 128,94 mm |

Program kesiti parçadan kendisi alır, kesitin orta çizgisini kurar ve
sonucu **kesit alanı ÷ sac kalınlığı** ile çapraz denetler. İkisi
tutmazsa sonuç verilmez, sebebi yazılır. Yani yanlış bir açınım ölçüsü
çıkmaz; ya doğrusu çıkar ya da hiç çıkmaz.

**Sınırlar – şu durumlarda açınım verilmez, nedeni yazılır:**

| ne yazar | ne demek |
|----------|----------|
| Parçada büküm bulunamadı | İç ve dış yüzü aynı eksende, yarıçap farkı sac kalınlığı kadar olan bir silindir çifti yok. Parça düz sac ya da sac parça değil (cıvata, somun, pul…). |
| Bükümlerin eksenleri birbirine paralel değil | Parça birden çok yönde bükülmüş (kutu/köşe). Bu sürüm tek yönde bükülmüş profilleri açar: L, U, C, Z, köşebent. |
| Kesit tek bir şerit oluşturmuyor / orta çizgi kurulamadı | Kesit sabit kalınlıkta bir sac şeridi gibi çözülemedi. Kaynaklı, ekli ya da kalınlığı değişen parça. |
| Kapalı profil / büküm ağacında çevrim | Boru, kutu profil, kıvrılıp kendine değen sac: düzleme açılamaz. |
| Duvarların şu kadarı büküm ağacına bağlanamadı | Gerçek bir duvar zincirin dışında kaldı; parça tek bir sac şeridi değil. |
| Açınım denetimi tutmadı | Orta çizgi uzunluğu ile kesit alanından çıkan uzunluk tutmuyor. Sonuç güvenilir değil, bu yüzden verilmiyor. |

**Resim iki türlü çıkar. Resmin üstünde hangisi olduğu yazar.**

**1. KESİM KONTURU** – lazer/pres için doğrudan kullanılır. Dış kontur,
bütün kesikler ve **bütün delikler gerçek yerlerinde**dir; üstüne büküm
çizgileri ve büküm çizelgesi konur.

Bu durumda açınım kesitten değil, **yüzeylerin kendisinden** açılır:
her düz duvar kendi düzlemindeki sac yüzeyidir ve düzleme olduğu gibi
taşınır; her büküm, silindir yüzeyinin nötr eksende açılmasıdır. Duvarlar
ve bükümler bir ağaç oluşturur, ağaç gezilerek hepsi yerine oturtulur.
Parçanın kesiti boy boyunca değişiyorsa – bir bölümünde fazladan flanş
varsa – bu yöntem onu da doğru açar.

**2. BLANK ÖLÇÜSÜ** – yalnız açınım genişliği, boy ve büküm çizgilerinin
yerleri. Kesim konturu çıkarılamadığında verilir ve **sebebi resmin
üstüne yazılır**. Büküm tezgâhı için yeter, lazer için yetmez.

**Kesim konturu şu üç denetimden geçmeden verilmez:**

1. **Hacim denetimi.** Düzlemdeki alan × sac kalınlığı, parçanın gerçek
   hacmine eşit olmalı (büküm payının K-faktöründen gelen küçük farkı
   hesaba katılarak). Sapma %3'ü geçerse kontur verilmez: bir duvar
   eksik kalmış ya da bir parça iki kere binmiş demektir.
2. **Tek parça denetimi.** Açınım düzlemde tek parça çıkmalı. Parçalı
   çıkarsa aradaki dikişler kesim çizgisi gibi görünür ve lazerde parça
   ikiye ayrılır; o yüzden verilmez.
3. **İki yöntem karşılaştırması.** Kesitten çıkan açınım genişliği ile
   yüzeyden açılan konturun genişliği tutmalı. Tutmuyorsa resme not
   düşülür.

Kısacası: **yanlış bir kesim konturu çıkmaz.** Ya doğrusu çıkar, ya blank
ölçüsü çıkar ve nedeni yazar. Lazerde hurda çıkarmaktansa hiç vermemek
daha iyidir.


#### Orta çizgi kurulamazsa: şerit genişliği

Rollform profillerde parçanın kesiti çok karmaşık olabilir ve program
orta çizgiyi kuramayabilir. O zaman **açınım resmi verilmez** — ama
parça boy boyunca aynı kesitteyse **şerit (bobin) genişliği** yine
verilir, çünkü rollform için zaten istenen odur:

```
genişlik = kesit alanı / sac kalınlığı
```

İki kapıdan geçer, ikisi de tutmazsa hiçbir şey verilmez:

1. **Parça prizmatik mi?** Boy boyunca dokuz istasyonda kesit alanı
   ölçülür; %0,5'ten çok oynuyorsa tek bir şerit genişliğinden söz
   edilemez.
2. **Kesit alanı × boy, parçanın gerçek hacmine eşit mi?** Eşitse
   kesit doğru ölçülmüş demektir.

**K-faktörü burada da işler.** `alan / kalınlık`, sacın **orta
yüzeyinin** uzunluğudur — yani K = 0,50 karşılığı. Gerçek K daha
küçükse nötr eksen içe kayar ve şerit daralır; düzeltme her büküm için
θ × t × (0,5 − K) kadardır. Bükümlerin açıları, eşleştirmeye gerek
kalmadan, **içbükey silindir yüzeylerinden** okunur: her bükümün bir
tane içbükey yüzü vardır.

Resmin üstüne **ŞERİT GENİŞLİĞİDİR** yazar, doğrulama sayılarıyla
birlikte; büküm yerleri ve kesim konturu verilmediği açıkça belirtilir.

> Gerçek bir örnek: TIRSAN rayı (3 mm sac, 200 mm boy, 38 büküm).
> Kesit alanı 1936,5 mm² → orta yüzey **645,8 mm**. Hacim denetimi:
> 1936,5 × 200 = 387.290 mm³, parçanın gerçek hacmi de 387.290 mm³.
> Bükümlerin toplam açısı 3076°; K = 0,40 için −16,1 mm düzeltmeyle
> şerit genişliği **629,7 mm**.
>
> Bu rayda açınım resmi neden çıkmıyor: büküm, "eş merkezli iki
> silindir, yarıçap farkı = sac kalınlığı" diye tanınır. Kesitteki 67
> yayın **66 ayrı merkezi** var — iç ve dış yüz eş merkezli değil, ki
> rollformda beklenen budur. O yüzden orta çizgi zinciri kurulamıyor
> ve büküm yerleri verilemiyor.

#### Büküm yöntemi: abkant mı, rollform mu

Program her sac parça için **hangi tezgâhta yapılabileceğini** söyler.
Bu bir tahmin değil, fizik:

- **Kanat**: abkantta parça bir **V kalıbın ağzına oturur** ve bıçak
  bastırır. Kanat kalıbın ağzını tutamayacak kadar kısaysa parça
  kalıbın içine düşer — büküm **imkânsızdır**. Bu, yöntemi belirler:
  rollform (ya da başka bir yöntem) gerekir.
- **İç yarıçap**: küçük yarıçap bükümü **riskli** kılar, imkânsız
  değil. Çatlayıp çatlamayacağı malzeme kalitesine, hadde yönüne ve
  kalıbın keskinliğine bağlıdır; ince sacta 0,5×t iç yarıçap keskin
  kalıpla bükülür. Bu yüzden yarıçap parçayı rollform ilan **etmez**,
  yalnız **uyarı** verir.

İkisi aynı şey değildir ve program da öyle davranır.

Sonuç açınım resminin üstüne, `ACINIM.csv`'ye ve 6. adımdaki
**YÖNTEM** sütununa yazılır — ölçüsüyle ve gerekçesiyle:

```
BUKUM YONTEMI: ROLLFORM  (olası)
Abkantta yapılamaz: en kısa kanat 2,5 mm = kalınlığın 0,8 katı
(abkant için en az 4 kat gerekir; daha kısa kanat V kalıbın ağzını
tutmaz); en küçük iç yarıçap 0,50 mm = kalınlığın 0,17 katı (abkant
için en az 0,6 kat gerekir; altında sac çatlar).
```

**Sınırlar sizin tezgâhınıza göredir**, kanun değil. Varsayılanlar hava
bükme için yaygın değerlerdir:

| sınır | varsayılan | anlamı |
|-------|-----------|--------|
| `abkant_en_az_kanat` | 4 × kalınlık | en kısa kanat bundan kısaysa abkant olmaz |
| `abkant_en_az_r` | 0,6 × kalınlık | iç yarıçap bundan küçükse **uyarı** (yasak değil) |
| `silindir_en_az_r` | 20 × kalınlık | bundan geniş yarıçap silindirde (kalender) yapılır |

Kendi kalıbınıza göre değiştirmek için ayar dosyasını düzenleyin
(K-faktörüyle aynı dosya, bkz. aşağıdaki not).

Gerçek bir şasi montajında (1262 katı, 148 parça) ölçülen:

| | sayı |
|---|---|
| açınımı çıkan sac parça | 60 |
| **abkant** | 53 |
| **rollform** (kanat çok kısa) | 7 |
| küçük yarıçap uyarısı alan | 12 |

Kanat oranının dağılımında net bir boşluk var: 3,1×t ile 5×t arasında
hiçbir parça yok. Varsayılan 4×t eşiği tam o boşluğa düşüyor, o yüzden
kararı verilere dayanıyor. Rollform çıkanların kanatları 1,0–3,0×t
arasında — 2 mm sacta 5 mm kanat standart bir V kalıba oturmaz.

Yarıçap ayrı hikâye: aynı montajda 12 parçanın iç yarıçapı 0,40–0,60×t
arasındaydı ve **hepsi abkant parçasıydı**. İlk sürümde yarıçapı da
yasaklayıcı saymıştım; bu 12 parçayı yanlışlıkla rollform ilan
ediyordu. Ölçüm düzeltti.

---

### Adım 7 — PAFTA

Buraya kadar çıkan resimler **1:1**'dir ve öyle kalır. Bu adım onları
silmez, ölçeklerini değiştirmez, çizimin kendisine dokunmaz. Yaptığı iş
şudur: **resmin kendi DXF dosyasına** `PAFTA` adında bir kâğıt sekmesi
ekler. Model sekmesi olduğu gibi kalır.

#### Neden kopya değil, dosyanın kendisi

Önceki sürüm paftayı ayrı bir `PAFTA` klasöründeki kopyaya yazıyordu.
Bunun pratikte bozulan yeri şu: resme sonradan bir ölçü eklerseniz ya
da bir ölçüyü düzeltirseniz, paftayı yeniden üretmeniz gerekir; bir kez
unutulunca elinizde **iki ayrı resim** olur — asıl DXF düzeltilmiş,
paftalı kopya eski. Hangisinin atölyeye gittiğini kimse bilemez.

Şimdi tek dosya var. Ölçüyü eklersiniz, aynı dosyanın `PAFTA` sekmesi
o düzeltilmiş çizime bakar; ayrışacak bir kopya yoktur. Aynı resmi
ikinci kez paftaya alırsanız eski pafta sekmesi silinip yenisi kurulur,
**sekmeler birikmez ve model uzayına yine dokunulmaz.**

Kâğıda basılan **PDF**'ler ayrıdır: çıktı klasörünün altındaki `PDF`
klasörüne, kâğıt adı ekiyle yazılır — `P07_KONSOL_A3.pdf`. PDF bir
çıktıdır, kaynak değil; dosya ismine bakıp hangi kâğıda basıldığını
görürsünüz.

Ölçek, paftanın **penceresine** aittir — çizime değil. "1:10 bastım"
demek çizimi küçülttüm demek değildir; aynı 1:1 çizime uzaktan bakmak
demektir. Paftalı dosyayı AutoCAD'de açıp Model sekmesine geçerseniz her
ölçüyü yine birebir ölçersiniz. Program bunu her pafta yazımında
kendisi de denetler: model uzayında tek bir varlık oynamışsa pafta
yazılmaz, hata verir.

#### Paftanın yapısı

**Kâğıdın yönünü program seçer.** Boyu siz verirsiniz (A3), yönü
parçaya bakılarak belirlenir: yatay ve dikey ikisi de denenir, hangisi
daha büyük ölçek veriyorsa o kullanılır; eşitse yatay kalır.

Bu, önceki sürümün "her zaman yatay" kuralının düzeltilmesidir. Dik
duran uzun bir parça — 3 m boyunda bir profilin ön görünüşü — yatay
A3'te 1:20'ye, montajda 1:50'ye kadar düşüyor ve resim neredeyse
görünmüyordu. Aynı parça dikey kâğıtta bir kademe büyük çıkıyor:
ölçülen örnekte 230 × 3000 mm'lik bir çizim yatayda 1:20, dikeyde
1:10. Kâğıdı parçaya uydurmak, parçayı kâğıda kurban etmekten iyidir.

Listede ve paftanın sağ üst köşesinde hangi yön kullanıldığı yazar
("A3 dikey"), PDF adına da girer: `P04_KONSOL_A3D.pdf`. Yönü kendiniz
dayatmak isterseniz komut satırında `--kagit A3-D` diyebilirsiniz.

Aşağıdaki şema yatay A3'tir (420 × 297 mm); dikeyde aynı yapı 90°
döner, antet kutusu yine sağ alt köşededir:

```
 +----------------------------------------------------+
 |   1     2     3     4     5     6     7     8       |   <- bölge rakamları
 | +------------------------------------------------+ |
 |A|                                    RESIM NO     |A|
 | |                               kod  ve  isim     | |
 |B|          Ç İ Z İ M   B U R A Y A                |B|
 | |                                                 | |
 |C|                                                 |C|
 | |                          . . . . . . . . . . .  | |
 |D|                          . antet alanı: BOŞ  .  |D|
 | +--------------------------. 150 x 100 mm . . .---+ |
 |   1     2     3     4     5     6     7     8       |
 +----------------------------------------------------+
```

- Çerçeve kâğıdın kenarından **15 mm** içeridedir; resim hiçbir zaman
  bundan dışarı taşmaz ve çerçeveye de dayanmaz, 12 mm daha boşluk
  bırakır.
- Sağ alt köşedeki **150 × 100 mm**'lik alan **boş bırakılır** ve oraya
  **asla çizim gelmez**. Antetinizi oraya kopyala-yapıştır ile
  koyarsınız. Bu alan **çizilmez** — kendi çerçevesi olan bir anteti
  yapıştırınca iki çizgi üst üste binerdi.
- **Resim no ve ismi sağ üst köşededir**; altında kâğıt ve pafta
  ölçeği yazar. Çerçevenin üstündeki iç payın içine yazılır, yani
  çizim alanından yer almaz — ölçeği düşürmez.
- Kenarlardaki rakam ve harfler bölge işaretleridir ("B3'teki delik"
  demek için). Kenar ortalarındaki kısa çizgiler katlama işareti.
- Her biri ayrı katmandadır (`PAFTA_CERCEVE`, `PAFTA_ANTET_ALANI`,
  `PAFTA_BOLGE`, `PAFTA_BILGI`); istemediğinizi tek tıkla silersiniz.

Program kendiliğinden antet **çizmez**. Her firmanın anteti başka;
programın uyduracağı bir şey değil. Kutuyu boş bırakır, gerisi sizin.

#### Firma anteti (EXE_YAP.bat'ta 2. seçenek)

Firmanızın kendi antetini kullanabilirsiniz. O zaman **çerçeve, bölge
işaretleri, antet ve firma logosu firmanın kendi çiziminden gelir**;
Pi3D yalnız kutuları doldurur:

| kutu | nereden gelir |
|------|---------------|
| Scale | paftanın ölçeği |
| Weight | BOM'daki kütle |
| Material | BOM'daki malzeme |
| Part Name | parçanın adı |
| Drawing No. | parçanın kodu |
| Drawn – Date / Name | **programda sorulur** (tarih, çizen) |
| Checked – Date / Name | **programda sorulur** (tarih, onaylayan) |
| FILE | dosya adı |

Tarih, çizen ve onaylayan 7. adımda üç kutuya yazılır ve **saklanır**;
bir daha girmeniz gerekmez. Değerler DXF'e yazıldığı için **PDF'te de
çıkar** — baskı paftadan alınır.

**Kâğıt boyu.** Şablon hangi kâğıt için çizildiyse (verilen antet A2,
594 × 420 mm), başka bir kâğıda basılırken şablonun **tamamı tek bir
oranla** ölçeklenir: A3'te 0,707, A1'de 1,416, A0'da 2,002. Bunlar
ISO'nun kendi kâğıt basamağıdır; antet kâğıtla birlikte büyür küçülür,
sayfadaki oranı hiç değişmez.

**Yön.** Firma anteti yatay çizilmiştir, dikey karşılığı yoktur; bu
yüzden antetli paftada kâğıt her zaman yatay kalır.

**Sürüm seçimi.** `EXE_YAP.bat` iki sürüm sorar:

```
1 = PI3D    Pi3D ve PiVision logolari gomulu, FIRMA ANTETI YOK
            (sag alt kosede 150x100 mm bos alan; kendi antetinizi
             oraya yapistirirsiniz)
2 = FIRMA   Pi3D logolari konmaz; antet klasorundeki FIRMA ANTETI
            kullanilir, kutularini Pi3D doldurur
```

Firmanın kendi anteti varken Pi3D'nin logosunu da basmak doğru
değildir: resim firmanındır.

#### Kendi antetinizi şablona çevirmek

`antet/` klasöründe iki dosya bulunur: `firma.dxf` (antet, tek blok
hâlinde) ve `firma.json` (hangi kutuya ne yazılacağı). Başka bir antet
için firmanın **çerçeve + antet DXF'ini** verip şablon üretirsiniz:

```
1)  Antetin sınırını CAD'de ölçün (sol alt ve sağ üst köşe).
2)  Kutuları listeleyin:
    python pf5_antet.py firma_cerceve.dxf --incele --antet 400.6,9.8,583.5,95.1
3)  Çıkan listeden her alanın kutusunun ORTASINI
    antet/firma_tanim.json içine yazın.
4)  Şablonu üretin:
    python pf5_antet.py firma_cerceve.dxf --tanim antet/firma_tanim.json \
           --cikti antet/firma
```

Yazının nereye geleceği **tahmin edilmez, ölçülür**: kutudaki etiketin
("Part Name :") kapladığı yer bulunur, değer onun sağından başlar.
Değer kutuya sığmıyorsa önce küçültülür, 1,5 mm'ye inince kısaltılır —
komşu kutuya asla taşmaz.

Antetin yazıları çoğu zaman patlatılmış (kontur) gelir ve dosya çok
büyük olur; şablon hazırlanırken konturlar 0,03 mm toleransla
sadeleştirilir. Verilen antette dosya **11,5 MB'tan 0,55 MB'a** indi,
görüntü değişmedi. Antet her resme bir **blok** olarak girer: blok
tanımı dosyada bir kez durur, ölçek blok referansının üstündedir.

**Antet zorunlu değildir.** `antet/` klasörü yoksa ya da 7. adımda
kutucuğu kapatırsanız Pi3D kendi sade paftasını çizer. Antet
bulunamazsa 7. adımda **nereye bakıldığı yazar** — tarih/çizen/
onaylayan kutuları sessizce yok olmaz.

Antet üç yerde aranır, bu sırayla:

1. **exe'nin yanındaki** `antet\` klasörü — buraya koyduğunuz antet
   gömülü olanı geçersiz kılar, exe'yi yeniden derlemeniz gerekmez
2. exe'ye **gömülü** antet (EXE_YAP.bat → 2 ile derlenmişse)
3. çıktı klasöründeki `antet\`

Kaynaktan çalıştırıyorsanız `pf3_gui.py`'nin yanındaki `antet\`
klasörüne bakılır.

#### Görünüşler kâğıda nasıl dağılır

Resim tek parça hâlinde bir pencereden gösterilmez. Program her
görünüşü **ayrı pencereye** alır ve kâğıda **ortadan dışa, eşit
aralıklarla** dağıtır:

- Resimdeki büyük model boşlukları atılır; yerine kâğıtta eşit aralık
  konur (en az 12, en çok 45 mm). Öbek kâğıdın ortasına oturur —
  dayanak noktası hiçbir zaman kenar değildir.
- **İzdüşüm ızgarası bozulmaz:** aynı satırdaki görünüşler kâğıtta da
  aynı hizada, aynı sütundakiler aynı düşeydedir, hepsi aynı ölçektedir.
- Çerçeveden ve antet alanından her yönde **12 mm** boşluk kalır.
- Hiçbir çizgi açıkta kalmaz: her varlık en yakın görünüşe yazılır,
  pencereler ne çakışır ne de bir şeyi dışarıda bırakır.

Bu, aynı kâğıtta **daha büyük ölçek** demektir. Örnek montajın 16
parçasında ölçekler 1:20'den 1:10'a, 1:5'ten 1:2'ye çıktı; resimlerin
yazıları 1,4 mm'den 2,8 mm'ye büyüdü.

Görünüş işareti taşımayan resimler (eski çıktılar, elle çizilmiş
DXF'ler) tek pencereyle, yine ortalanarak yerleşir.

#### Ölçek nasıl seçilir

Çizim, antet kutusunun **üstündeki** (366 × 143 mm) ya da **solundaki**
(216 × 243 mm) boşluğa oturur; hangisi daha büyük ölçek veriyorsa o
kullanılır. Ölçek standart merdivenden seçilir: **1:1, 1:2, 1:5, 1:10,
1:20, 1:50…** Ara ölçek uydurulmaz, 1:7 diye bir resim olmaz.
Kendiliğinden **büyütme yapılmaz**: küçük bir parça 2:1 çizilmez.

> **Ölçüler her zaman 1:1'dir.** Ölçek paftanın penceresinin işidir,
> rakamın değil. 1860 mm'lik bir parçayı A3'e 1:10 sığdırsanız da
> ölçü çizgisinde **1860** yazar ve CAD'de ölçtüğünüzde 1860 çıkar.
> Program hiçbir ölçü rakamına dokunmaz, `DIMLFAC` çarpanını
> değiştirmez; denetim betiği her sürümde bunu ayrıca doğrular.

Ölçek **geometriye göre değil, yazılar dahil** seçilir. Büküm tablosu,
ölçü rakamı, başlık — hepsi resmin parçasıdır; pencereyi yalnız
geometriye göre açarsak bunlar kenardan kırpılır.

Seçtiğiniz kâğıda sığmayan resim **üretilmez**; satırda hangi kâğıtta
hangi ölçekte oturacağı yazar. Kâğıt kutusundan A4/A2/A1/A0 da
seçebilirsiniz.

> **Uzun parçalarda yazıya dikkat.** 2,5 m'lik bir sac A3'e ancak 1:10
> girer; resmin kendi yazıları da 10'a bölünür ve kâğıtta 0,7 mm kalır —
> okunmaz. Program bunu satırda **DİKKAT** diye yazar ve "A2 olsa 1:5
> olurdu" der. Böyle parçalar için büyük kâğıt seçin.

#### Baskı

**Kendiliğinden yapılmaz.** PDF istediğinizde üretilir: paftası hazır
satırları seçip **"SEÇİLİ PAFTALARI BAS (PDF)"**. PDF'ler çıktı
klasörünün altındaki **`PDF`** klasörüne, kâğıt adı ekiyle yazılır:

```
cikti/
  P07_KONSOL.dxf          <- çizim + PAFTA sekmesi, ikisi bir arada
  PDF/
    P07_KONSOL_A3.pdf     <- baskı
```

PDF'in sayfa ölçüsü kâğıdın birebir ölçüsüdür (A3 → 420×297 mm),
çizgiler siyahtır. Yazıcıda **"sayfaya sığdır" demeyin**, %100 basın;
yoksa ölçek bozulur.

---

### Türkçe harfler (Ğ Ş İ Ç Ö Ü)

DXF dosyasının kendisinde bir sorun yoktur: dosya UTF-8'dir ve "Ğ"
içine gerçekten iki bayt (`C4 9E`) olarak yazılır. Harflerin "?" ya da
boş kutu görünmesinin sebebi **fonttur**. AutoCAD yazıyı yazı stilinin
gösterdiği font dosyasıyla çizer; DXF'in hazır `Standard` stili
`txt.shx`'i gösterir ve o SHX fontun içinde yalnızca ASCII glifleri
vardır — Ğ Ş İ Ç Ö Ü'nün çizimi yoktur.

Program bu yüzden kendi yazı stilini kurar:

| | |
|---|---|
| stil adı | `PI3D` |
| font | `arial.ttf` (TrueType, Türkçe harfleri içerir) |
| kullanan | bütün yazılar, başlıklar, büküm tablosu **ve ölçü rakamları** (`dimtxsty`) |

Hazır `Standard` stiline **dokunulmaz**: bu çizimi başka bir dosyaya
INSERT/XREF ederseniz oranın kendi yazıları bozulmasın diye.

Başka bir font isterseniz AutoCAD'de `STYLE` komutuyla `PI3D` stilini
tek yerden değiştirin, bütün yazılar birden değişir. ISOCPEUR gibi
teknik resim fontları da Türkçe harf taşır.

**Daha önce üretilmiş resimler:** o dosyalar `Standard`/`txt` ile
yazılmıştı. Bunları paftaya aldığınızda program yazıları kendiliğinden
`PI3D` stiline taşır ve satırda kaç yazının düzeltildiğini söyler —
STEP'i baştan okumanıza gerek kalmaz. Metne ve konuma dokunulmaz,
yalnız yazı stili değişir.

#### Konum ölçüleri

Resimde artık yalnız gabari yok: deliklerin **kenardan yeri** de
ölçülendirilir.

Zincir şöyle kurulur — kenardan ilk deliğe, sonra dizinin adımı, sonra
son delikten öbür kenara:

```
|--10--|-------------- 123 x 20 --------------|--10--|
|------------------------ 2480 ---------------------|
```

**Dizi tek ölçüye iner.** 124 deliğin her birine 20 mm yazmak resmi
okunmaz yapar ve hiçbir şey eklemez; adımlar eşitse (%2 payla) dizi
sayılır ve `123 x 20` diye tek ölçü konur. Dizi değilse ve delik sayısı
azsa her biri tek tek ölçülür; ikisi de değilse yalnız uçlar verilir,
tam liste `olculer.csv`'dedir.

**Gabari en dışarıdadır.** Teknik resimde küçük ölçüler içeride, toplam
ölçü en dışarıda durur; tersi olursa ölçü çizgileri kesişir. Bu yüzden
gabari ölçüsü konum ölçülerinden SONRA, onların **ölçülen** sınırının
dışına çizilir.

**Yer tahmin edilmez, ölçülür.** Dar bir aralıkta ("3,2") yazı ölçünün
içine sığmaz ve CAD onu uzatma çizgilerinin dışına kaçırır; nereye
kaçıracağı ölçü stiline bağlıdır. Her ölçü çizilir, yazısının gerçek
sınırı ölçülür, çakışıyorsa silinip bir alt kademede yeniden denenir.
Örnek montajın 16 resminde 435 yazıda sıfır çakışma.

> **Henüz yok:** açısal ölçüler, çapraz (pahlı) kesimlerin ölçüsü ve
> girinti/çıkıntı ölçüleri. Kesit düzlemi en çok deliği açan yerden
> geçiyor ama bunun da iyileştirilmesi gerekiyor.

---

### Adım 8 — LAZER (kesim resimleri)

Bu resimler **okunmak için değil, kesilmek için** üretilir. İçlerinde
yalnız **kesim konturu** vardır: dış kontur ve delikler, **1:1**, tek
katmanda (`KESIM`), hepsi kapalı çokgen.

Bilerek çıplaktırlar. Ne büküm çizgisi, ne büküm tablosu, ne ölçü, ne
yazı, ne çerçeve, ne antet — ve **paftaya alınmazlar, PDF'leri
basılmaz**; 7. adımın listesinde hiç görünmezler.

Sebebi tek cümlede: CAM yazılımı dosyadaki her çizgiyi kesim yolu
sayabilir. Resmin üstündeki bir yazı ya da ölçü çizgisi sacın üstüne
kesilir. Parçanın kimliği **dosya adındadır**:

```
P05_01_050_000_01_U-Blech.dxf          detay resmi (ölçülü, paftalı)
P05_01_050_000_01_U-Blech_acinim.dxf   açınım (büküm çizgileri, tablo)
P05_01_050_000_01_U-Blech_Lzr.dxf      LAZER: yalnız kontur
```

#### Listede kimler var

| grup | ne | seçim |
|------|----|-------|
| üstte | 6. adımda **açınımı çıkan** parçalar | **seçili gelir** |
| altta | montajdaki diğer **sac** parçalar (bükümlü ve düz) | siz seçersiniz |
| — | sac olmayanlar (freze, torna, profil) | listeye hiç alınmaz |

Kontur nereden gelir:

- **bükümlü sac** → açınımın kesim konturu. 6. adımda hesaplanmışsa
  yeniden hesaplanmaz; açınım parça başına 15–30 saniye sürer.
- **düz sac** → parçanın kendi yüzü. En büyük düzlem yüz bulunur,
  normali Z'ye döndürülür, dış ve iç halkaları alınır.

Düz sacta sonuç **bağımsız bir ölçüyle** denetlenir: gabarinin en ince
yönü ile hacim/alan tutmak zorundadır. Cepli, çıkıntılı ya da kademeli
bir parçada tutmaz ve **kontur verilmez** — lazerde hurda çıkarmaktansa
hiç vermemek gerekir. Örnek montajda 10 sac parçanın 6'sının konturu
çıktı, 4'ünün sebebi yazıldı (rollform rayın kesim konturu yok; üç
parçanın büküm eksenleri paralel değil).

Ayrıca **LAZER.csv** yazılır: poz, kod, ad, adet, kalınlık, en × boy,
delik sayısı ve konturun nereden geldiği. Nesting için doğrudan
kullanılır.

---

## 2b. Hangi dosya biçimleri okunur

| biçim | okunur mu | notu |
|-------|-----------|------|
| **STEP** `.stp` `.step` | ✔ **önerilen** | parça adları, montaj ağacı, malzeme alanı — hepsi gelir |
| **IGES** `.igs` `.iges` | ✔ | ölçüler doğru çıkar, **ama parça adı ve montaj ağacı yoktur**: BOM'da kod/tanım olmaz, civata-somun ayrımı yapılamaz. Yalnız yüzey taşıyan IGES'te program yüzeyleri dikip katı yapmayı dener |
| **BREP** `.brep` | ✔ | OpenCascade'in kendi biçimi, ad taşımaz |
| CATIA `.CATPart` `.CATProduct` | ✘ | üreticiye ait kapalı biçim |
| SolidWorks `.sldprt` `.sldasm` | ✘ | " |
| NX / Creo `.prt` `.asm` | ✘ | " |
| Inventor `.ipt` `.iam` | ✘ | " |
| Parasolid `.x_t` `.x_b`, ACIS `.sat` | ✘ | " |
| STL, OBJ, glTF, VRML, 3MF | ✘ | yalnız üçgen ağ; içinde delik/radüs/düzlem bilgisi yok |

Programın çekirdeği **OpenCascade**'dir; açık kaynak olduğu için üreticilerin
kapalı biçimlerini açamaz — bu bir eksiklik değil, lisans meselesidir.

### CATProduct / CATPart için ne yapmalı

CATIA'dan **STEP olarak kaydedin**, program onu okur:

```
CATIA V5:  File > Save As > "STEP (*.stp)"
```

Montajın tamamı tek STEP dosyası olur; **parça ağacı ve parça adları
korunur**, yani BOM eksiksiz çıkar. AP214 ya da AP242 fark etmez.

**Malzeme STEP'e geçmiyor** — CATIA'da tanımlı olsa bile. Çözümü ayrı bir
belgede anlattım: **`CATIA_MALZEME.md`**. Özeti:

1. CATIA'da `.CATProduct` açıkken **Analyze ▸ Bill of Material**
2. **Define formats** ile *Material* sütununu görünür listeye ekleyin
3. **Save As…** ile `.txt` olarak kaydedin
4. Pi3D 2. adımda → **malzeme.csv yükle…** → o dosyayı seçin

Program `Part Number` ve `Material` sütunlarını başlıklarından bulur,
ayırıcıyı (sekme / `;` / `,`) kendi anlar, `Steel` · `Aluminium` ·
`Stainless Steel` gibi İngilizce adları tanır. Tanıyamadığı bir ad olursa
hangisi olduğunu söyler. Geometri STEP'ten, malzeme bu listeden gelir.

Toplu iş için `catia_malzeme_cikar.CATScript` makrosu da pakette.

Program tanımadığı bir dosya seçtiğinizde susmaz: biçimin ne olduğunu ve
hangi CAD menüsünden STEP alınacağını söyler.

---

## 2c. Ölçek ve birim

Çizim **1:1**'dir ve **1 çizim birimi = 1 mm**'dir. Her detay resminin
başlığında `olcek 1:1   birim: mm` satırı bunu söyler.

### "Kendi çizdiğim ölçü ×100 yazıyor"

Dosyadaki **aktif ölçü stili** bozuksa olur: o stilin `DIMLFAC` değeri 100
ise AutoCAD ölçtüğü uzunluğu 100 ile çarpıp yazar — 45,80 mm'lik mesafeye
`4580` yazar. Geometri doğrudur, yalnız yazı yanlıştır; başka dosyalarda
görülmez çünkü onların aktif stili birebirdir.

Eski sürümlerde bu vardı: DXF'i yazan kütüphane metre/santimetre için
hazırlanmış `EZDXF`, `EZ_M_100_H25_CM` gibi stilleri kuruyor ve birini
**dosyanın aktif stili** yapıyordu; o stillerde `dimlfac = 100`. Bizim
ölçülerimiz ayrı stil kullandığı için doğru çıkıyordu, ama sizin sonradan
çizdiğiniz ölçüler bozuluyordu. Artık o stiller hiç kurulmuyor; dosyada
yalnız `Standard` ve `PF_MM` var, ikisinin de `dimlfac = 1`, aktif stil
`PF_MM`, başlıkta `$DIMLFAC = 1`.

Kontrol: AutoCAD'de `DIMSTYLE` komutu → aktif stil `PF_MM` olmalı;
`DIMLFAC` yazıp Enter → **1** dönmeli.

### "30 yazıyor ama AutoCAD 3000 ölçüyor"

DXF dosyasına artık `$INSUNITS = 4` (millimeters) yazılıyor. Bu satır
yokken AutoCAD dosyayı **birimsiz** sayar; başka bir çizime `INSERT` ya da
`XREF` ile eklerseniz hedef çizimin birimine göre ölçekler. Ölçü yazıları
çizgiye dönüştürülmüş olduğu için eski değerde kalır — **"30 yazıyor ama
3000 ölçüyor"** durumu tam olarak budur.

Kontrol listesi:

1. DXF'i **ayrı açın** (INSERT etmeyin): `DIST` ile iki nokta arası ölçün,
   ölçü yazısıyla aynı çıkmalı.
2. Hedef çizimde `UNITS` komutu → *Insertion scale* **Millimeters** olsun.
   *Unitless* ise AutoCAD tahmin yürütür.
3. `INSERT` ederken ölçek kutusunun **1** olduğunu doğrulayın.
4. Başlıktaki `olcek 1:1  birim: mm` satırıyla ölçtüğünüz değer
   uyuşmuyorsa dosya yolda ölçeklenmiş demektir.

> Annotation çubuğundaki `1:1` **kâğıt (layout) ölçeğidir**, model uzayındaki
> birimle ilgisi yoktur; oradaki değere bakarak birim doğrulanamaz.

---

## 3. Komut satırıyla kullanım

```
python pf3_olcu.py parca.stp --liste             # önce neler var, bir bakalım
python pf3_olcu.py parca.stp -o cikti            # 1 + 2 + 3, hepsi
```

### Aşamalar

| aşama | ne yapar | çıktı |
|-------|----------|-------|
| 1 | komponent detaylandırma + BOM | `BOM.csv`, `BOM.md`, `BOM_AGAC.csv/md` (hiyerarşik), `olculer.csv/json`, `rapor.md` |
| 2 | detay parçaların çizimi ve ölçülendirilmesi | `P01_<kod>.dxf`, `P02_…` |
| 3 | montaj resmi + içinde BOM tablosu | `00_MONTAJ.dxf` |

```
python pf3_olcu.py parca.stp -o cikti --asama 1        # yalnız BOM
python pf3_olcu.py parca.stp -o cikti --asama 2        # yalnız detay resimleri
python pf3_olcu.py parca.stp -o cikti --asama 3        # yalnız montaj resmi
```

### Malzeme

```
python pf3_olcu.py parca.stp -o cikti --malzeme aluminyum       # hepsine tek
python pf3_olcu.py parca.stp -o cikti --malzeme-dosya malzeme.csv
python pf3_olcu.py parca.stp -o cikti --malzeme-sor             # terminalden sorar
python pf3_olcu.py --malzeme-liste                              # tabloyu göster
```

`malzeme.csv` biçimi (noktalı virgülle ayrılmış, Excel'de açılır):

```
kod;malzeme;ad
01.051.000.01;celik;C-Profil-Runge XL-H
09.020.000.03;aluminyum;Rollenplatte
```

Hiçbir malzeme seçeneği vermezseniz program çeliği varsayar, bunu **açıkça
söyler** ve çıktı klasörüne doldurmaya hazır bir `malzeme.csv` şablonu yazar.

### Görünüş, kesit, zip

```
python pf3_olcu.py parca.stp -o cikti --gorunus ON,SAG,UST --kesit --zip
python pf3_olcu.py parca.stp -o cikti --tek 01.050.000.01 --asama 2
                                                  # yalnız tek parçanın resmi
python pf3_olcu.py parca.stp -o cikti --asama 1 --acinim 01.051.000.01
                                                  # yalnız açınım
python pf3_olcu.py parca.stp -o cikti --acinim HEPSI --k-faktor 0.32
```

### Pafta

Pafta işi ayrı bir programdır; istediğiniz DXF'e uygulanır:

```bash
# hangi resim hangi ölçekte oturuyor - hiçbir şey yazmaz, sadece söyler
python pf4_pafta.py --plan cikti/*.dxf

# paftaya al (varsayılan A3)
python pf4_pafta.py --cikti cikti/PAFTA --bas cikti/*.dxf

# büyük kâğıt
python pf4_pafta.py --kagit A2 --cikti cikti/PAFTA cikti/*.dxf
```

| seçenek | ne yapar |
|---------|----------|
| `--kagit A4..A0` | kâğıt boyu (varsayılan A3); yönü program seçer. `A3-D` denirse yalnız dikey kullanılır |
| `--olcek 0.1` | ölçeği elle verir; kâğıda sığmıyorsa pafta yazılmaz |
| `--cikti KLASÖR` | paftaların yazılacağı klasör (varsayılan `PAFTA`) |
| `--plan` | hiçbir şey yazmaz, yalnız ölçek raporu verir |
| `--bas` | paftaların PDF'ini de üretir |
| `--no` | sağ üst köşeye yazılacak resim no (verilmezse dosya adı) |
| `--ad` | resim no'nun altına yazılacak isim |

Kaynak DXF'lere dokunulmaz; her pafta ayrı bir dosyaya yazılır.

### Bütün seçenekler

| seçenek | ne işe yarar |
|---------|--------------|
| `-o, --out` | çıktı klasörü |
| `--asama 1,2,3` | çalıştırılacak aşamalar |
| `--liste` | yalnız komponent listesini ekrana yaz |
| `--malzeme <ad>` | hepsine tek malzeme |
| `--malzeme-dosya <csv/json>` | parça bazlı malzeme eşlemesi |
| `--malzeme-sor` | terminalden sor |
| `--malzeme-liste` | malzeme tablosunu yaz |
| `--yogunluk <kg/mm3>` | malzeme seçimini ezer (uzman kullanımı) |
| `--gorunus ON,ARKA,SAG,SOL,UST,ALT` | görünüş seçimi, en çok 4 |
| `--kesit` | A-A tam kesit görünüşü ekle |
| `--zip` | çıktıları `cizimler.zip`'te topla |
| `--tek <kod>` | yalnız bu kodu çiz |
| `--en-cok <n>` | en çok bu kadar komponent çiz |
| `--en-az-hacim <mm3>` | bu hacmin altındaki katıları atla |
| `--en-az-delik <mm>` | bu çapın altındaki silindirler delik sayılmaz |
| `--gizli` / `--gizli-yok` | gizli (kesik) çizgiler |
| `--montaj-yok` | montaj çizimini atla |
| `--acinim <kod,kod>` / `--acinim HEPSI` | bükümlü sacların açınımı |
| `--k-faktor <0.40>` | büküm payı K-faktörü; verilen değer saklanır |

---

## 4. Çıktıları okumak

### `BOM.csv` / `BOM.md`

Her poz için: kod, tanım, adet, malzeme, ölçü (BOY×EN×KALINLIK), adet başına
kütle, toplam kütle, çizim dosyası. Civata, somun, pul gibi **standart
elemanlar BOM'a kod + adet olarak girer**, çizimleri üretilmez. Kaynak
dikişleri BOM'a girmez, ayrıca sayılır.

### `P01_<kod>.dxf` — detay resmi

Başlık bloğunda yalnız parça kimliği ve genel ölçüler vardır:

```
POZ 5   01.050.000.01   01.050.000.01 U-Blech-Mechanismus
adet: 1
BOY x EN x KALINLIK : 483.04 x 76.5 x 32.0 mm
hacim 163651.2 mm3   kutle 1.2847 kg   yuzey 114694.7 mm2
malzeme: Celik (S235JR / St37)   yogunluk 7.85 g/cm3   [varsayilan]
```

Çizimde tablo yoktur: delikler görünüşlerde `2x Ø9`, kenar yuvarlamaları
`4x R3` olarak ölçülendirilir; yazı deliğin hemen yanına, kısa bir kılavuz
çizgisiyle konur. Tam delik ve radüs listeleri `rapor.md`, `olculer.csv` ve
`olculer.json` dosyalarındadır.

> **Çap yalnız tam çember delikler için verilir.** Bir silindirik yüzeyin
> açısal açıklığı toplanır; 360°'ye yakınsa delik, değilse kenar
> yuvarlamasıdır ve radüs tablosunda **yarıçap** olarak listelenir.

Ölçüler **milimetre**, birebir ölçek. Çap ölçüsünün çizgisi her zaman
deliğin merkezinden geçer; yazılar görünüşün üstünde satır satır dizilir,
ne birbirine ne görünüşe biner.

Katmanlar: `GORUNEN`, `GIZLI` (kesik), `EKSEN` (uzun-kısa), `OLCU`, `YAZI`,
`TARAMA` — hepsi 0,09 mm çizgi kalınlığında. (DXF'te çizgi kalınlığı
serbest bir sayı değil, sabit bir merdivendir: 0,05 – 0,09 – 0,13 – 0,15…
"0,10" o listede yok; yazılırsa 0,13'e yuvarlanır. İstenen 0,10'a en
yakın geçerli değer 0,09'dur.)

**Görünen çizginin üstüne gizli çizgi çizilmez.** Teknik resim kuralı
budur: bir kenar hem görünüyor hem arkada da varsa, görünen kazanır.
Program gizli parçanın görünenle çakışan bölümünü **keser**, kalanını
çizer. Ölçüler her zaman karşılaştırılan iki parçanın kendi arasında
alınır; parça montajda orijinden metrelerce uzakta olsa bile sonuç
değişmez.

### `00_MONTAJ.dxf` — montaj resmi

Gabari görünüşleri + genel ölçüler + içine çizilmiş BOM tablosu.

### `rapor.md`

Okunabilir özet: çizilen parçalar, standart elemanlar, kaynak dikişleri,
parça parça delik ve radüs tabloları.

### Önizleme

Bir DXF'i CAD açmadan PNG olarak görmek için:

```
python ornek/olcu/onizle3.py cizim.dxf onizleme.png
```

Yazılar gerçek boyutta çizilir; önizlemede çakışma görünüyorsa çizimde de
gerçekten vardır.

---

## 5. Sık sorulanlar

**Program parçayı nasıl tanıyor?**
STEP'i XCAF ile okur, montaj ağacındaki gerçek parça adlarını alır. Aynı ad
+ aynı hacim + aynı gabari = aynı parçanın kopyası sayılır ve tek pozda
adediyle toplanır.

**Standart eleman ayrımını neye göre yapıyor?**
Parça adında DIN/ISO/EN numarası ya da civata, somun, pul, pim, perçin, yay,
rulman, segman, saplama gibi ifadeler geçiyorsa standart eleman sayar; çizim
üretmez, BOM'a kod + adet olarak koyar.

**Ölçüler neye göre veriliyor?**
Komponentin **kendi eksenlerine** göre. En büyük düz yüzeyin normali
kalınlık ekseni, o yüzeydeki en uzun kenar yönü boy eksenidir. Böylece
montaj içinde eğik duran bir sac da kendi boy/en/kalınlık ölçüsüyle çıkar.

**Kütle neye göre hesaplanıyor?**
`hacim × yoğunluk`. Yoğunluk malzemeye bağlıdır; program tahmin etmez.
Önce data'ya bakar, bulamazsa sorar. Seçilen malzeme ve yoğunluğu resmin
başlık bloğuna ve BOM'a yazılır — yani kütlenin neye göre çıktığı resimden
okunur.

**Büyük montajda ne kadar sürer?**
Örnek dosyada (112 katı, 41 komponent) STEP okuma ~10 sn, 16 detay resmi
~45 sn, montaj resmi ~2 dk. Montaj resmi en pahalı adımdır; gerekmiyorsa
`--montaj-yok` ya da arayüzde ilgili kutuyu kapatın.

**Bir parça çizilemezse ne olur?**
O parçanın satırında `HATA:` yazar, program diğerlerine devam eder. Kesit
anlamlı çıkmıyorsa o parçada kesit çizilmez, diğer görünüşler yine çizilir.

---

## 6. Klasördeki diğer programlar

| dosya | ne yapar |
|-------|----------|
| `pf3_olcu.py` | **ana motor** — STEP → BOM + detay resmi + montaj resmi |
| `pf3_gui.py` | **ana arayüz** — yukarıdaki 7 adımlı pencere |
| `pf4_pafta.py` | **pafta** — resmin kendi dosyasına standart A3 pafta sekmesi ekler (model 1:1 kalır), PDF'i `PDF` klasörüne basar, eski dosyaların yazılarını Türkçe stile taşır |
| `logo_gom.py` | logoları koda gömer (`logo/` → `pi3d_logo.py`) |
| `pf1_referans.py` | STEP'ten XYZ referans yönü ve 3 konumlandırma noktası önerir |
| `pf_gui.py` | `pf1_referans` için 3B önizlemeli arayüz |
| `pf2_fikstur.py` | kaynak/montaj fikstürü üretici (3-2-1 prensibi) |
| `pfd_dxf2stp.py` | DXF görünüşlerinden 3B STEP üretir (renk = parça kimliği) |
| `Pi3D_baslat.bat` | Windows'ta tek tıkla kurulum + başlatma |
| `Pi3D_baslat_KUCUK.bat` | dar disk için küçük kurulum (~800 MB) |
| `EXE_YAP.bat` + `pi3d.spec` | çalıştırılabilir dosya (.exe) üretir |
| `CATIA_MALZEME.md` | CATIA malzemesini kaybetmeden aktarma |
| `catia_malzeme_cikar.CATScript` | CATIA makrosu: ağacı gezip `malzeme.csv` yazar |

Ayrıntılar için `README.md`.

---

## 7. Henüz yapılmayan, not alınmış işler

1. **Otomatik kesit kararı** — şu an kesit isteğe bağlı (E/H). İki delik ya
   da iki form görünüşte üst üste binip anlamsızlaştığında programın bunu
   kendi fark edip o görünüş yerine kesit koyması.
