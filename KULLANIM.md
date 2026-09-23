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

## 1b. Logolar ve ikon

Program açıldığında üstte koyu bir şerit görürsünüz: solda **PiVision**
logosu, sağda uygulama adı ve ikonu. Pencerenin ve `.exe`'nin ikonu da
uygulama ikonudur.

Bütün görseller `logo/` klasöründedir ve **her ölçü ayrı ayrı** hazırdır:

* `pi3d.ico` – 16/24/32/48/64/128/256 boyutları tek dosyada. Windows
  görev çubuğunda 32'yi, masaüstünde 48'i, dosya gezgininde 256'yı ister;
  hepsi içinde olduğu için ikon hiçbir yerde bulanık çıkmaz.
* `pi3d_16.png` … `pi3d_1024.png` – Windows dışı ve belge için.
  Üst şeritte 72 px'lik olanı kullanılıyor.
* `pivision_64.png` / `_56` / `_44` / `_32` – arayüz şeridi için hazır
  boyutlar; şeritte 64 px'lik kullanılıyor.

Logoyu değiştirmek isterseniz aynı adla, aynı ölçüde yenisini koyun;
kodda değişiklik gerekmez. Ayrıntı: `logo/OKU.md`.

Dosyalar silinse bile program çalışır: pencere varsayılan ikonla açılır,
şeritte resim yerine yazı görünür.

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

1. Listeden **açınımını istediğiniz parçaları seçin** – Ctrl ile tek tek,
   Shift ile aralık, ya da **Tümünü seç**. Parçanın kaç bükümü olduğu
   fark etmez.
2. Gerekirse **K-faktörünü** değiştirin (ilk kurulumda 0,40).
   0,10 – 0,60 arası her değeri girebilirsiniz – 0,32 de olur;
   ondalık ayracı virgül ya da nokta olabilir. **Verdiğiniz
   değer saklanır**, bir daha girmeniz gerekmez.
3. **SEÇİLENLERİN AÇINIMINI ÜRET** deyin.

Her parça için `A<poz>_<kod>_acinim.dxf` ve hepsi için `ACINIM.csv`
yazılır. Açınımı çıkarılamayan parçaların **nedeni** hem listede hem
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

---

### Adım 7 — ANTET ve PAFTA

Buraya kadar çıkan resimler **1:1**'dir ve öyle kalır. Bu adım onları
silmez, ölçeklerini değiştirmez, üzerlerine yazmaz. Yaptığı iş şudur:
her resmin bir **kopyasına** firma antetinizi ve seçtiğiniz kâğıdı
ekler, kopyayı `PAFTA` alt klasörüne yazar.

Ölçek, paftanın **penceresine** aittir — çizime değil. "1:10 bastım"
demek çizimi küçülttüm demek değildir; aynı 1:1 çizime uzaktan bakmak
demektir. Paftalı dosyayı AutoCAD'de açıp Model sekmesine geçerseniz her
ölçüyü yine birebir ölçersiniz. Program bunu her pafta yazımında
kendisi de denetler: model uzayında tek bir varlık oynamışsa pafta
yazılmaz, hata verir.

**Antet nasıl hazırlanır.** Anteti kendi CAD'inizde çizip DXF olarak
kaydedin. Kâğıdın sol alt köşesi (0,0) olsun. Değerin geleceği yerlere
alan adını yazın:

```
<<FIRMA>>   <<PROJE>>   <<AD>>      <<KOD>>     <<POZ>>     <<ADET>>
<<MALZEME>> <<KALINLIK>> <<KUTLE>>  <<OLCU>>    <<OLCEK>>   <<PAFTA>>
<<CIZEN>>   <<KONTROL>> <<ONAY>>    <<TARIH>>   <<REVIZYON>>
<<ACIKLAMA>> <<TOLERANS>> <<YUZEY>> <<DOSYA>>   <<BIRIM>>   <<SAYFA>>
```

Program bu yazıları bulup gerçek değerle değiştirir. İstemediğiniz alanı
hiç koymazsınız; değeri olmayan alan **boş bırakılır**, paftada
`<<CIZEN>>` yazısı kalmaz.

Çizimin oturacağı boşluğu da siz belirlersiniz: `CIZIM_ALANI` adlı bir
katmana bir dikdörtgen koyun. O dikdörtgen paftada görünmez, yalnız
çizimin yerini ve ölçeğini belirler. Koymazsanız program kâğıdın
kenarından 10 mm pay bırakıp kalanını kullanır — o zaman çizim antetin
üstüne binebilir.

Elinizde antet yoksa **"Örnek antet üret…"** düğmesine basın: çalışır
durumda bir A3 antet yazar. Hem işinizi görür hem de kendi antetinizi
çizerken şablon olur.

**Kâğıt seçimi.** A4 ya da A3'e **1:1 sığan** resim oraya, birebir
çizilir — teknik resimde tercih her zaman budur. Sığmayanlar için
aşağıdaki kutudan kâğıt seçersiniz (A3 / A2 / A1 / A0); o kâğıda sığan
**en büyük standart ölçek** (1:2, 1:5, 1:10, 1:20…) kendiliğinden
bulunur. Ara ölçek uydurulmaz. Seçtiğiniz kâğıda standart bir ölçekle
sığmayan resim için satırda ne gerektiği yazar ve o satır üretilmez.

Her kâğıda ayrı antet çizmek isterseniz: `ANTET.dxf`'in yanına
`ANTET_A1.dxf` koyun, A1 paftada o kullanılır. Koymazsanız tek antet
kâğıttan kâğıda oranlanır (A3 anteti A1'de iki kat büyür; yazı boyları
da büyür).

**Baskı kendiliğinden yapılmaz.** PDF istediğinizde üretilir: paftası
hazır satırları seçip **"SEÇİLİ PAFTALARI BAS (PDF)"**. PDF'in sayfa
ölçüsü kâğıdın birebir ölçüsüdür (A3 → 420×297 mm), çizgiler siyahtır.
Yazıcıda **"sayfaya sığdır" demeyin**, %100 basın; yoksa ölçek bozulur.

Antet yolu, firma, çizen gibi bilgiler saklanır; her açılışta yeniden
yazmazsınız.

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

### Antet ve pafta

Pafta işi ayrı bir programdır; istediğiniz DXF'e uygulanır:

```bash
# önce elinizde antet yoksa bir örnek üretin
python pf4_pafta.py --ornek-antet ANTET_A3.dxf --firma "FİRMA A.Ş."

# hangi resim hangi kâğıda 1:1 sığıyor - hiçbir şey yazmaz, sadece söyler
python pf4_pafta.py --plan --antet ANTET_A3.dxf cikti/*.dxf

# paftaya al (kâğıt verilmezse A4/A3'e sığanlar yapılır, kalanı listelenir)
python pf4_pafta.py --antet ANTET_A3.dxf --kagit A2 --cikti cikti/PAFTA \
       --firma "FİRMA A.Ş." --cizen "N. ÖZDEMİR" --proje "K0 TELEVRE" \
       --bas  cikti/*.dxf
```

| seçenek | ne yapar |
|---------|----------|
| `--antet YOL` | `<<ALAN>>` yer tutuculu antet DXF'i |
| `--ornek-antet YOL` | çalışır durumda örnek antet üretir, çıkar |
| `--kagit A4..A0` | kâğıt; verilmezse sığan en küçüğü seçilir |
| `--olcek 0.1` | ölçeği elle verir; kâğıda sığmıyorsa pafta yazılmaz |
| `--cikti KLASÖR` | paftaların yazılacağı klasör (varsayılan `PAFTA`) |
| `--plan` | hiçbir şey yazmaz, yalnız kâğıt/ölçek raporu verir |
| `--bas` | paftaların PDF'ini de üretir |
| `--firma --cizen --proje --aciklama` | antete yazılacak ortak bilgiler |

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
| `pf4_pafta.py` | **antet ve pafta** — 1:1 resmin kopyasını Ax kâğıda yerleştirir, PDF basar |
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
