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

Sekmeler bir **öneri sırasıdır, zorunluluk değil**. Model okununca (İNCELE)
bütün sekmeler açılır; BOM'u, görünüşü, çizimleri, açınımı, paftayı ve
lazeri istediğiniz sırayla, **istediğiniz kadar yeniden** yapabilirsiniz.
Daha önce çıktı aldığınız bir klasörde **eksik kalan** adımı da yalnız o
adımı yaparak tamamlarsınız — bkz. *Önceki çıktıdan devam*.

### Küçük ekran (15 inç dizüstü)

Ekran 1500 pikselden dar ya da 950 pikselden kısaysa (1366x768; 1920x1080
%125 ölçekte 1536x864) pencere **tam ekran** açılır ve sıkı düzene geçer:
başlık şeridi incelir, günlük 3 satıra iner, uzun açıklamalar tek satır
olur — üzerine tıklayınca tamamı açılır (*▸ ayrıntı*). Düğme şeritleri ve
alttaki ilerleme / İPTAL / günlük / durum çubuğu **her zaman yer alır**;
yer daralırsa önce listeler kısalır. 1280x650'lik pencerede bile hiçbir
düğme gizli kalmaz (`test/gui_ekran_denetimi.py`).

### Çıktı klasörünün düzeni

```
<çıktı klasörü>/
    BOM.csv  BOM.md  BOM_AGAC.csv  BOM_AGAC.md  olculer.*  rapor.md
    DXF/       detay resimleri + 00_MONTAJ.dxf  (paftaları içlerinde)
    ACINIM/    ..._acinim.dxf + ACINIM.csv     (BÜKÜM RESMİ)
    LZR/       ..._acinim_lzr.dxf / ..._Lzr.dxf + LAZER.csv
                                               (lazer kesim; paftaya girmez)
    PDF/       basılmış paftalar  ..._A3.pdf
    pi3d_is.json   iş durumu: hangi çizim hangi model ve ayarla, ne zaman
                   üretildi; yapılan işlemler ve süreleri
```

Eski sürümlerin her şeyi tek klasöre yazdığı çıktılar da okunur (dosyanın
türü adından anlaşılır: `_acinim.dxf`, `_acinim_lzr.dxf`, `_Lzr.dxf`).

`ACINIM.csv` ve `LAZER.csv` artık **birleştirilir**: 2 parçanın açınımını
yeniden üretince tablodaki diğer parçaların satırları silinmez.

### Önceki çıktıdan devam — eksik ya da yeniden

1. sayfada **ÖNCEKİ ÇIKTIYI AÇ…** ile klasörü seçin. Altta ne olduğu yazar:

```
Bu klasörde önceki çalışma bulundu:
  BOM ................ var  (26.09.2026 14:10)
  detay resmi (DXF) .. 166
  montaj resmi ....... var
  açınım ............. 0
  lazer (LZR) ........ 0
  PDF ................ 0
Model dosyası AYNI: üretilmiş çizimler geçerli, yalnız eksikler üretilebilir.
```

* **Pafta ve PDF** için modeli okumaya gerek yoktur: 7. sekme hemen açılır.
  Paftası daha önce kurulmuş resimler listede *pafta kurulu* diye gelir;
  **SEÇİLİ PAFTALARI BAS** doğrudan PDF çıkarır. PDF'i güncel olanlar
  *PDF'i var (güncel)* yazar.
* **Eksik çizim, açınım, lazer** için model gerekir: kayıtlı STEP kutuya
  yazılır, **İNCELE** deyin. Malzeme, görünüş, kesit ayarlarınız klasörden
  **geri gelir**.
  * 5. sekmede **ÇİZİMLERİ ÜRET** — *Yalnız EKSİK ya da ESKİMİŞ çizimleri
    üret* işaretliyse güncel resimlere dokunulmaz.
  * 6. sekmede açınımı bu modelden önceden üretilmiş parçalar *önceden
    üretildi* yazar ve seçili gelmez; eksikler seçili gelir.
  * 8. sekmede de öyle.

**Bir çizim ne zaman "güncel" sayılır:** aynı model dosyası (içerik özeti —
dosyayı kopyalamak ya da tarihini değiştirmek bozmaz, içeriği değişirse
bozar) + aynı görünüş / kesit / gizli çizgi / en küçük delik ayarı + aynı
malzeme + aynı poz ve adet + aynı Pi3D çizim sürümü ile üretildiği
`pi3d_is.json`'da **kayıtlıysa**. Kayıt yoksa (eski sürüm çıktısı) ya da
tutmuyorsa çizim yeniden üretilir: eski resmi yeni diye vermek, hiç
vermemekten kötüdür.

Tam üretimden sonra karşılığı kalmayan eski resimler (ör. sınıf değişip
poz numaraları kaydıysa eski `P07_...`) **silinmez**, `DXF/ESKI/`
klasörüne taşınır — pafta listesine girip yanlış parçanın resmi gibi
basılmasın.

Komut satırında: `python pf3_olcu.py model.stp -o cikti --eksik`

### İşlemler ve süreler (sağdaki panel)

Pencerenin sağında yapılan her işlem, açıklaması ve süresi listelenir:
*Model okuma: K0_KASA...stp — 3 dk 56 sn*, *BOM çıkarma — 41 sn*,
*Eksik çizimler — 12 dk 05 sn* … En altta **TOPLAM (bu oturum)** ve **bu
çıktı klasöründe toplam** süre yazar; önceki oturumların işlemleri soluk
renkte görünür. Çalışan işin geçen süresi ve — ilerleme biliniyorsa —
**ölçülen hıza göre kalan süre** üstte yazar (tahmin değil: yapılan iş /
geçen süre). Süreler `pi3d_is.json`'a da yazılır.

**İş bitince** panelde yeşil zeminle **✔ TAMAMLANDI: <iş>** ve bir sonraki
adım yazar (*BOM çıkarma* bitti → *sonraki adım: örnek resim ya da TÜMÜNÜ
ÜRET*; *Açınım* bitti → *lazer resmi*…); durum çubuğunun başına da
✔ TAMAMLANDI eklenir, günlüğe `===== ✔ TAMAMLANDI … =====` satırı düşer
ve kısa bir ses çalar. Hata olursa kırmızı **✖ HATA**, iptalde turuncu
**■ İPTAL EDİLDİ** yazar. Yeşil yazıyı görmeden bir sonraki adıma
geçmeyin.

### Adım 1 — VERİ

* **Model dosyası:** *Gözat…* ile `.stp` / `.step`, `.igs` / `.iges` ya da
  `.brep` dosyasını seçin (bkz. aşağıdaki biçim tablosu).
* **Kaydedilecek klasör:** boş bırakırsanız STEP'in yanına `<dosyaadı>_cikti`
  klasörü açılır. İsterseniz başka yer seçin.
* **İNCELE ▸**

STEP okunur, aynı parçanın kopyaları tek komponentte toplanır, parça /
standart eleman / kaynak dikişi ayrımı yapılır. Büyük montajlarda bu adım
bir-iki dakika sürebilir; pencere kilitlenmez, altta günlük akar.

#### Parça mı, standart mı, kaynak dikişi mi

STEP'te "bu satın alınan bir parçadır" diye bir bilgi **yoktur**. En kesin
yol CAD'in kendi **Made / Bought** alanıdır (aşağıda *CAD'den: Made / Bought*);
o yoksa program bunu ADDAN, MONTAJ AĞACINDAN ve BİÇİMDEN çıkarır:

| kural | örnek | sonuç |
|-------|-------|-------|
| kaynak dikişi | `K0 25 MM TEK KAYNAK.2`, `BRAKET KAYNAGI`, `Kehlnaht` | dikiş — parça değil |
| kaynak ile birleşen eleman | `M10 KAYNAK SOMUNU`, `M6X20 KAYNAK CIVATASI` | **standart** (dikiş değil) |
| norm numarası | `DIN 912`, `ISO 7090` | standart |
| **üretim ismi** geçiyor | `CIVATA LAMASI`, `SOMUN SACI`, `KAMERA BRAKETI` | **parça** — Türkçe tamlamada asıl isim sondadır: cıvata lamaSI bir lamadır |
| standart / satın alınan | cıvata, somun (`FL SOMUN_2` dahil), pul, perçin, rulman, menteşe, kamera, sensör, yük bağlama halkası, kauçuk takoz/stoper | standart |
| **satın alınan ürün = TEK KALEM** | `153-02-10-004 - GOMME SALLAMA ...` (gömme yük bağlama halkası: sac, halka, taşı, pim...) | ürünün kendisi tek satır (`153-02-10-004` × kopya sayısı); içindeki parçalar **ona bağlıdır**, ayrı kalem değildir — aynı parça ürünün dışında da kullanılıyorsa yalnız dıştaki adedi kalır |
| adsız satın alınan ürün | `001_T573679C8D002kh5` (toolbox kilidi: 23 adsız katı — yay, pul, somun, o-ring) | küçük (≤ 250 mm) alt montaj, içinde en az bir adsız parça, yalnız standart / adsız küçük parçalar, en az biri tanınmış standart eleman, adıyla üretim parçası yok → tek kalem, **kontrol listesinde onay ister** |
| katısız (yüzey modeli) standart | `153-13-05-20_YAPRAK MENTESE` × 2 | STEP'te katı yok ama adıyla standart: BOM'a girer (önceden hiç görünmüyordu), kontrol listesinde onay ister |
| dikiş grubunun içi | `K0 KAYNAKLAR` altındaki `ARA DIKME` | dikiş |
| `KAYNAKLI ...` | kaynaklı montaj / parça | **dikiş değil** |

Tek kaleme İNMEYENLER: adı standart ama içinde **adıyla üretim parçası**
olan grup (`..SACI`, `..BRAKETI`: adı yanıltıcı bir üretim montajı
olabilir, günlüğe yazılır); içindekilerin HEPSİ adıyla belli olan grup
(`K0 DIS TRIM ARKA AYAR GRUBU` = 4 x `M6 KAYNAK SOMUNU`: bir klasördür,
somunlar kendi adlarıyla kalem olur). Ölçüldü: kaynaklı kasada gömme
sallama ve kilit tek kalem oldu, kontrol listesi 22 belirsiz parçadan 4'e
indi (kilidin 23 adsız katısı artık ayrı ayrı sorulmuyor); televrede kilit
ve iki menteşe tek kalem, 4 katısız standart eleman BOM'a girdi.

#### Adı bilgi taşımayan katılar: GEOMETRİDEN tanıma

**Kaynak dikişleri ölçülür: `KAYNAK.xlsx`.** Dikiş BOM'a girmez ama her
dikiş katısı geometriden ölçülür: model biçimi (köşe kaynağı — düz,
dışbükey ya da içbükey kesitli; CATIA'nın düz çubuk dikişi; nokta
(punta); çevre / kollu dikiş), **boy** (köşede iki bacak düzleminin
kesişme doğrultusundaki gerçek uzunluk, ötekinde hacim / kesit),
**kesit**, **a ölçüsü** (köşede iç üçgenin yüksekliği, ötekinde aynı
kesitli köşe kaynağınınki = √kesit) ve **kaynak metali kütlesi** (dikiş
hacmi × 7,85 g/cm³). İkinci sayfa **a ölçüsüne göre** toplam boy ve kg
verir. Kaynak YÖNTEMİ (gazaltı, TIG, elektrot) geometriden anlaşılmaz:
gazaltı teli sarfiyatı = kaynak metali / yöntemin verimi.

**Ölçüldü** — kaynaklı kasa: 944 dikişin hepsi ölçüldü (toplam 37,25 m,
kaynak metali 1,686 kg; a2 30,15 m, a3 5,08 m). Adında boy yazan 141
dikişin (`K0 25 MM TEK KAYNAK` ...) **141'inde** ölçülen boy adla aynı.
Bu modeldeki `25 MM TEK KAYNAK` dikişleri çeyrek daire kesitli (2,5 x 2,5
dışbükey köşe, ölçülen a 1,77 -> a2); ilk sürüm onları düz üçgen sanıp boyu 15,9
buluyordu.

#### Kaynak resimleri: `KAYNAK/<grup>_kaynak.pdf`

5. sayfadaki **KAYNAK RESİMLERİ (PDF)** düğmesi her **kaynaklı alt grup**
için ayrı bir kaynak resmi çıkarır. Bu **ayrı bir iştir**, "tüm çizimler"
ile kendiliğinden çalışmaz: çok dikişli modelde uzun sürer (944 dikişli
kasada ~13 dakika). Çalışırken ilerleme çubuğu, kalan süre ve günlükte
hangi grubun çizildiği görünür; **İptal** ile durdurulur. Komut
satırında: `--kaynak-resmi`. Resimler **yalnız
PDF**'tir ve ayrı `KAYNAK` klasörüne yazılır (DXF üretilmez). Artık
karşılığı olmayan eski `*_kaynak.pdf` dosyaları o klasörden silinir.

**Resimde yalnız kaynak ölçüleri ve kaynak konumları vardır.** Parça
ölçüsü (gabari, delik, büküm) yoktur; parçalar yalnız dikişin nerede
olduğunu göstermek için çizilir. Dikişler kırmızı ve kalındır.

**Kaynak ölçüleri ondalıksızdır** (resim, dikiş listesi ve
`KAYNAK.xlsx`). Değer yarım yukarı yuvarlanır: 2,7 çıkan a **3**'tür,
1,77 çıkan a **2**'dir. Önemli olan dikişin **yeri, boyu ve varlığıdır**;
kaynakta alt-milimetre hassasiyet aranmaz.

**Grup nasıl bulunur.** Dikişin grubu, modelde nerede durduğuna göre
değil, **birleştirdiği parçalara** göre bulunur. CAD'de dikişler çoğu
zaman ayrı bir `K0 KAYNAKLAR` ağacında durur ve kamyonun dört bir yanına
dağılır. Program her dikişe **değen** parçaları ölçer (0,2 mm). O
parçaların montaj ağacındaki en yakın ortak üst grubu dikişin grubudur.
Kaynak her zaman **iki** parçayı birleştirir. CAD'de dikiş gövdesi
parçaya her zaman tam oturtulmaz. Kasa modelinde yakıt dolum braketini
traverse bağlayan dikişlerden biri traversten 1,1 mm, biri braketten
2 mm uzakta çizilmişti. Değen parça ikiden azsa, eksik parça **2,5 mm'ye
kadar** boşlukta en yakın parçadan tamamlanır. Böylece bu dikişler tek
parçaya bağlanıp üç ayrı resme dağılmaz, konumları "?" çıkmaz.
Braketin kendi dikişleri braketin grubunda kalır; braketi şasiye
bağlayan dikiş bir üst grupta kalır. Aynı gruptaki birbirinden kopuk
kümeler ayrı resim olur. Aynı biçimli kopyalar tek resim ve adet olur.
Dosya adı grubun adıdır: `K0 DIS TRIM BAGLANTI_GRUP 6_SOL_kaynak.pdf`.

**Sayfalar** (A3 yatay, her sayfada antet ve sayfa numarası). Düzen
kullanıcıyla denenip onaylandı:

1. **Genel görünüş: yalnız dört izometrik.** Üstten ön-sağ, üstten
   ön-sol, alttan ön-sağ, alttan ön-sol; sayfada biri üstte biri altta
   (sağ taraf bir sayfada, sol taraf öbüründe). Dik görünüş (ÖN, ÜST,
   SAĞ) genel sayfada yoktur; bölgeleri tanıtmak için izometrikler
   yeter.
   - Dikişler yakınlığa göre **bölgelere** ayrılır. Her bölgenin **tek
     harfi** vardır (A..Z; Q, W, X yok). Harf, bölgenin dikişlerinden en
     az biri açıkça göründüğü izometriklerde daire içinde, bölgenin
     ortasına kısa bir çizgiyle bağlı durur. Harfler grubun en geniş
     göründüğü düzlemde soldan sağa, yukarıdan aşağı sıralanır.
   - Bölge sayısı harf sayısını aşmasın diye çok dikişli grupta
     bölgeler büyütülür (250 dikişli şasi 23 bölge).
   - Az bölgeli grupta (6'ya kadar) dört izometrik tek sayfadadır; dikiş
     listesi de kısaysa (10 satıra kadar) bu sayfanın üstündedir.
2. **Kaynak listesi:** K no, tip, a, z, boy, **konum** (`-`,
   `kenardan 20`, `K8 + 51`; aşağıda) ve başlangıç / bitiş koordinatları. Koordinatlar grubun sınır kutusunun en küçük
   köşesine göre, mm'dir. Listede ayrıca birleştirdiği pozlar
   (P12 + P31) ve dikişin gösterildiği detay yer alır. Resim ne kadar
   kalabalık olursa olsun yer ve ölçü buradan kesin okunur.
3. **Detay sayfaları** (sayfa başına 4 detay), bölge bölge. Başlıkta
   detay ve bölge: `DETAY D2 - BÖLGE D (İZOMETRİK ALTTAN ÖN-SAĞ, 1:9)`.
   Bölge birden çok yönden gösterilirse A1, A2 ... diye gider.
   - **Önce izometrik:** dik görünüşte bir sacın iki yüzündeki ya da
     arka arkaya duran dikişler aynı çizgiye düşer; dikişin içte mi
     dışta mı olduğu anlaşılmaz. Dikişi gören bir izometrik varsa detay
     ondan çizilir (sekiz izometrik: üstten ve alttan, dört köşe). Hiçbir
     izometrikte görünmeyen dikiş dik görünüşe kalır.
   - Sıralı kaynağın ölçüleri izometrikte de verilir: dikiş ekseni
     boyunca çizilir, üstünde **gerçek** değer yazar. Bir zincirin
     kaynakları bölgelere bölünmez, aynı detaya düşer; aralar böylece
     resimde görünür.

**Ölçek serbesttir.** Kaynak resminde ölçek standart olmak zorunda
değil; görünüş sayfayı dolduracak tam sayılı ölçekle çizilir (1:17,
1:9, 2:1). Standart ölçeğe (1:20) yuvarlamak görünüşü sayfanın yarısına
küçültüyordu. Ölçüler gerçek değerle yazılır.

**Görünürlük ölçülür, tahmin edilmez.** Dikiş boyunca 5 dilimden,
dikişin göze bakan yüzeyinden göze doğru ışın gönderilir. Işın bir
parçaya çarpıyorsa dikiş o noktada gizlidir. Dikiş ancak dilimlerin
%60'ı açıkken o görünüşe konur.

İki dikiş aynı çizgiye izdüşebilir (ör. bir sacın iki yüzündeki
dikişler). Bu durumda ikincisi o görünüşe konmaz, göründüğü başka bir
yöne alınır. Hiçbir yönden net görünmeyen dikiş listede `(gizli)` diye
işaretlenir.

**Renkler:** dikişin kendisi **kırmızı** ve kalındır; dikişin ekseni
ince **mavi kesikli** çizgidir. Kırmızı yalnız dikişin kendi
çizgisidir: bir çizgi 1 mm'de bir örneklenir, noktalarının çoğu dikişin
üstündeyse kırmızı çizilir (eskiden ortası dikişin yanından geçen uzun
sac kenarı baştan sona kırmızı oluyor, dikiş onun içinde
kayboluyordu).

**Etiketler üst üste binmez, parçaya karışmaz:** semboller görünüşün
iki yanında, görünüşten 6 yazı boyu uzakta bir sütunda durur.
Yan yana (kâğıtta 30 mm içinde) ve özellikleri aynı (tip, a, boy)
dikişler **tek sembol** alır; o sembolden her dikişe ayrı ok gider
(en çok 3). Balonda numaralar `K12-K14` ya da `K3,K7` diye yazar.
Uzaktaki aynı dikiş kendi sembolünü alır. `SİM.` notu balonun
altındadır, parçanın üstünde değil.

**Yazılar asla üst üste binmez, parçanın çizgisine binmez.** Etiketler
sayfa bazında yerleşir: önce sayfadaki dört detayın görünüşleri konur;
her etiketin tam kutusu (referans çizgisi, a / boy, balon, not) başka
bir etikete, öbür detayın görünüşüne ya da başlığına değiyorsa boş yer
bulunana kadar aşağı kaydırılır. Sıralı kaynak ölçüsünün yazısı başka
bir ölçüye ya da parçanın bir çizgisine binecekse ölçü dışarı ya da öbür
yana kaydırılır; hiçbir yere sığmıyorsa çizilmez, değeri listede kalır.

Ölçüldü (gerçek modeller, her resim ölçülmüş yazı sınırlarıyla):
kasa modelinin bütün kaynak resimleri (26 PDF, 172 sayfa, 944 kaynak)
yazı-yazı çakışması 0, parça çizgisi üstünde yazı 0 (döndürülmüş yazı
gerçek dikdörtgeniyle ölçülür: `test/yazi_dikdortgeni.py`). Normal detay resimlerinde
kasa (144 resim, 4.164 yazı), Karluna (55 resim, 1.809 yazı), Televre
(111 resim, 3.330 yazı): çakışma 0 (`test/cizim_cakisma_denetimi.py`).

**Sembol (ISO 2553):**
- ok dikişe değer, sonra kırılır ve yatay referans çizgisine bağlanır;
- çizginin altında (ok tarafı) köşe kaynağı üçgeni vardır;
- üçgenin solunda `a` (boğaz), sağında **boy** yazar;
- uçtaki balonda K numarası vardır;
- çevre kaynağında kırılmada daire, puntada daire sembolü kullanılır.

**Konum ölçüsü yalnız SIRALI kaynakta.** Kaynakların çoğunun yeri
zaten bellidir: parçanın kesim yerinde, yarıkta, köşede, çıkıntının ya
da ayağın kenarında. Oraya ölçü vermek gereksizdir; **tek duran
kaynağa konum ölçüsü konmaz**, listede konumu `-`'dir. Ölçü, iki
parçanın **boyuna ya da enine art arda** kaynaklandığı yerde önemlidir
(sıralı / aralıklı kaynak):

- **Zincir:** aynı parçaları, **aynı eksen** üzerinde (eksenler 1,5 mm
  içinde) art arda birleştiren, eksen boyunca üst üste binmeyen
  kaynaklar. Bir sacın iki yüzündeki yan yana kaynaklar zincir değildir.
- Zincirin **ilk** kaynağına kenardan başlangıç: tam kenardan ya da
  köşeden başlıyorsa (2 mm'den yakın) ölçü yok, listede `kenardan`;
  değilse `kenardan 20`. Zincirin başı, kenara yakın olan ucudur.
- **Sonraki** kaynaklara bir öncekiyle **ara**: listede `K8 + 51`
  (K8'in bitiminden 51 mm sonra başlar), resimde ölçü çizgisi.
- Zincirin **son** kaynağı da kenarda ya da köşede bitiyorsa (2 mm'den
  yakın) onun ara ölçüsü çizilmez, listede `kenara kadar`: yeri köşeden
  bellidir. `– o –` üçlüsünde yalnız ortadaki ölçülür.
- **Simetrik zincirler:** aynı düzende paralel iki zincir (sacın
  karşılıklı iki kenarı ya da bir sacın iki yüzü; boylar, aralar ve
  kaynakların eksen boyundaki yerleri aynı, 1,5 mm içinde) ölçüler
  **bir kez** verilir: numarası küçük olan zincirde. Öbürünün
  kaynakları listede `SİM. K3` (karşılığı), resimde ilk kaynağının
  yanında `SİM. K1-K3` notu.
- **Küçük üründe** (grubun en büyük ölçüsü 300 mm'den küçük) resimde
  konum ölçüsü yoktur; parçanın nereye takılacağı zaten bellidir.
  Değer listededir.

Başlangıç ölçüsü dikişin **kök çizgisi** üzerinde ölçülür. Kök
çizgisi, dikişin iki parçaya oturan bacak yüzlerinin kesişimidir; bu
çizgi boyunca iki parçanın da yüzeyinin sürdüğü aralık (birleşme
çizgisi) ölçülür.
- Bacak yüzü yüzün 25 noktasından denetlenir: ince sacın kenarındaki
  dikişte bacak sacdan geniştir, ortası sacın dışına düşer.
- CAD'de dikiş parçaya birkaç onda mm boşlukla çizilmişse (şasede
  0,27 mm) ölçülen boşluk kadar pay verilir (en çok 2,5 mm).
- Üç parçaya değen dikişte bacağı oturan iki parça kullanılır.
- Ölçü çizgisi dik görünüşte yalnız dikiş görünüş düzlemine
  paralelken çizilir; izometrikte eksen boyunca. Ucu detay penceresinin
  dışındaysa çizilmez; değer yine listededir.
- Bacak yüzü bulunamazsa ya da kök çizgisi dikişin uçlarından
  geçmiyorsa başlangıç verilmez: `?`. Ara ölçüleri yine verilir.

Kaynak YÖNTEMİ ve dikişin hangi tarafa yapılacağı (ok tarafı / karşı
taraf) geometriden anlaşılmaz. Sembol ok tarafına çizilir.

CAD bazen katıya ad vermez (`COMPOUND`, `SOLID`, `Body`) ya da ad yalnız
**parça numarasıdır** (`FT108161`, `SB108164`, `55RS865978`). Adından hiçbir
şey anlaşılmaz; program o zaman katının **yüzlerine** bakar ve karar verir.
(Tente kompleksinde 41 flanşlı cıvata, 29 mercimek başlı cıvata ve 69 perçin
somun böyle adlandırılmıştı; eskiden geometri yalnız öneri yazıyordu, hepsi
üretim parçası kalıyordu.)

| tanınan | geometrik imza |
|---------|----------------|
| **pul** | eksene dik iki düz yüz + dış silindir + boydan boya delik; kalınlık ≤ dış çapın %30'u |
| **somun** | eksene paralel 6 düz yüz 60° aralıklı (ya da 4 yüz 90°), boydan boya delik; anahtar ağzı / delik 1,3–2,4 |
| **cıvata** | delik yok; bir ucunda altıgen, silindirik, **mercimek (kubbe, ISO 7380)** ya da havşa baş (imbus yuvası da tanınır), gövde en az bir çap boyunda |
| **perçin** | gövde + bir ucunda kubbe ya da havşa baş |
| **pim** | tek çaplı, başsız, uçları pahlı, çap ≤ 12 |
| **perçin somun** | ince başlı burç, delik baştan girer; deliğin baş tarafı geniş (sıkışma bölgesi), uç tarafı dar (dişli kısım) — ya da gövde altıgen/tırtıllı. Kapalı uçlusu da tanınır. |
| **diş modelli somun / cıvata** | diş, tırtıl ya da serbest yüzle modellenmiş parçada yüz tipleri bir şey söylemez; parça **ölçülür**: eksen boyunca 48 kotta 8 yöne ışın atılır, her kotta delik ve dış yarıçap, dış biçim (altıgen = en büyük/en küçük 1,155) bulunur |
| **o-ring** | yalnız tor yüzü |
| **kaynak dikişi** | birbirine dik iki düz bacak yüzü + hipotenüs: uzun üçgen prizma; bacaklar hacimden ve alanlardan hesaplanır (1–20 mm) |

#### YAPISAL tanıma: tipleri saymak yerine öğelere ayırmak

Cıvata, somun, pul, rulman tiplerinin sonu yok (imbus, torx, yıldız, düz;
bombe, mercimek, havşa, mantar, para, kare, flanşlı; kronlu, kelebek,
kapalı, manşon, kaynak somunu, T-somun...). Program her birine ayrı kalıp
yazmaz; parçayı **yapısal öğelerine** ayırır (`pf11_yapi`): eksen boyunca
60 kotta 24 yöne ışın atar, her kotta dış ve iç biçimin kaç katlı simetrik
olduğunu (2: yarık, 4: kare / çarpı, 6: altıgen / torx, 8+: diş, tırtıl)
ölçer. Tip öğelerin birleşiminden çıkar:

| öğeler | tip |
|--------|-----|
| **gövde + baş** | cıvata / vida — başın biçimi (altıköşe, altıköşe flanşlı, kare, harici torx, silindir, alçak silindir, bombe, mantar, mercimek, havşa, para) + **lokma** (imbus, torx, yıldız, düz, kare) |
| **delik + tutma yüzü**, başsız, kısa | somun — altıköşe, kare, flanşlı, tırtıllı flanşlı, kronlu, kapalı (kör), manşon (uzatma) |
| **delik + ince flanş + gövde**, delik kademeli ya da gövde altıgen | perçin somun (düz delikli yuvarlak olan "perçin somun / flanşlı burç" adayı) |
| **delik + iki eş merkezli halka** (her yönde) | rulman — iç Ø x dış Ø x genişlik ISO 15 serileriyle karşılaştırılır: "rulman (608 ölçüsünde)" |
| **delik + ince halka** | pul — dış dişli, iç dişli, yaylı (grover), konik (belleville / havşa); düz ve kare pul yalnız ADAY (yapıca delikli plakayla aynı) |
| **başsız gövde + uçta lokma** | setskur |
| **yalnız küre** | bilye |
| **spir**: eksene paralel ışın tel kesitini düzenli aralıkla, eşit kalınlıkta keser; ışın eksen çevresinde 90° dönünce kesitler **çeyrek adım** kayar (ya da ince dilimlerde telin açısı kotla düzgün döner) | **yay** — uçlar eksen boyunca taşıyorsa (halka / kanca) *çekme yayı*, yana taşıyorsa (bacak) *burulma yayı*, uçsuz ve açık sarımsa *basma yayı*, iki uç çapı farklıysa *konik basma yayı*; tel, dış çap, adım, sarım sayısı ve sağ / sol helis yazılır |
| tekrarlanan eşit katman, dönmeden aynı (disk / yaprak yay paketi, spiral yay) | katmanlı yay — yalnız ADAY |
| **düz açık halka** + boşluğa simetrik iki kulak deliği | **segman**: eş merkezli kenar içteyse mil segmanı (DIN 471), dıştaysa delik segmanı (DIN 472) |
| düz açık halka, deliksiz, ağız 60 – 180° | E-segman (DIN 6799) — büyük ya da kalınlığı seri dışıysa ADAY (C biçimli sac olabilir) |
| **ince cidarlı tüp + boydan boya yarık** | yaylı pim: et/çap ≥ 0,15 ağır tip (ISO 8752), altı hafif tip (ISO 13337) |
| iki eş **yarım silindir uç** + düz yanlar, b × h DIN 6885 tablosunda | paralel kama (DIN 6885 A); düz uçlu kutu (B tipi) lama ile aynı biçim — yalnız ADAY |
| baskın **koni** yüzü, koniklik **1:50** (yarım açı 0,573°) | konik pim (ISO 2339 / DIN 1) |
| **küre baş + altıköşe** (anahtar ağzı 7 / 9 / 11) + eksenel ince delik | gres nipeli (DIN 71412 A) |
| başsız gövde + uçta lokma; **öbür ucun biçimi** | setskur uç tipi: düz (DIN 913), konik — çap uca doğru sıfıra iner (914), pim uçlu — sabit ince basamak (915), çanak — uç yüzde çukur (916) |
| tek çaplı, pahlı dolu silindir + bir ucunda eş eksenli **kör delik** (d → M: 6→M4, 8→M5, 10→M6, 12→M6, 16→M8, 20→M10) | çekmeli (iç dişli) pim (ISO 8735 / DIN 7979); deliksizse silindirik pim / merkezleme pimi (ISO 2338 / 8734); uçta lokma varsa setskur |
| aynı çaplı bükülmüş çubuk | U / J cıvata, kulp, kanca — ADAY |

Yay, segman, pim, kama ve nipel ayrı modüllerdedir (`pf11_yapi.yay`,
`pf13_aile`). Yay ölçümü helis yüzeyde OCC ışını yerine **üçgen ağ**
üzerinde yapılır (ışın başına ~0,2 ms): yay 1 – 4 saniyede tanınır. İçi
boş, yüzeyi çoğunlukla düzlem olmayan parçada yay ÖNCE denenir; eskiden
aynı parça dönel ölçümlerde dakikalarca bekliyordu.

**Ölçüldü (yay)** — 5 gerçek modelin 1.139 parçasında: kaynaklı kasa ve
televre modelindeki adsız `COMPOUND` bacaklı **burulma yayı** (~10 sarım,
dış Ø3,2), `Druckfeder 1 x 6,5` basma yayı (tel ~Ø0,8, dış Ø6,5),
`Druckfeder-Rungenkeil` basma yayı (dış Ø14,5, ~19 sarım) — dördü de
doğru; yay olmayan hiçbir parçaya yay kararı verilmedi. Kör perçin ve iki
büyük sac (oluklu yüzey) önce "katmanlı yay?" adayı çıkıyordu; en az 5
katman ve katman aralığı ≤ 4 × kalınlık şartıyla ayıklandı.

Öğeler tanıdık bir bağlantı elemanı oranındaysa karar verilir; oran
alışılmadıksa yalnız kontrol listesine aday olarak girer. Sentetik
denetimde yukarıdaki tiplerin hepsi düz ve uzayda döndürülmüş olarak
doğru adlandırılır; kademeli mil, flanş, flanşlı burç ve delikli sac
plaka hiçbir şey sayılmaz.

Emin olunmayan katıya **karar verilmez**. Düz uçlu, pahsız bir Ø5 çubuk
pim de olabilir kaynak dikişi de (CATIA dikişi çoğu zaman böyle modeller);
o parça kalır. Tanınamayan adsız katı 2. sekmede **parca – ADSIZ** yazar.

**Ölçüldü** — 4 gerçek modelde adı belli 636 komponentle karşılaştırıldı:
geometri 236 karar verdi, **1'i yanlış (%0,42)**. 182 kaynak kararının
hepsi doğru, hiçbir üretim parçası dikiş sayılmadı. Işın ölçümü 13 karar
ekledi (perçin somun, diş modelli somunlar, flanşlı cıvata), hepsi doğru;
denerken çıkan iki yanlış düzeltildi: 24×24×3 delikli bağlantı braketi
kare somun, saplamalı kauçuk takoz cıvata sanılıyordu (somun yüksekliği
en az 0,45 d, cıvata başı en çok 2,6 d genişlik / 1,2 d yükseklik). Tek
yanlış adında `SAC` geçen pul biçimli bir parça; adı olduğu için ad
kazanır, geometri orada yalnız **öneri** olarak yazar (`parca – öneri: pul?`).

Adı olan parçada her zaman **ad geçerlidir**; geometri yalnız öneridir.
`rapor.md`'de *Geometriden tanıma* başlığı altında her kararın gerekçesi
yazar: `somun: 6 yüz 60° aralıklı, anahtar ağzı 13,0, delik Ø6,9,
yükseklik 3,5`.

Adsız bir katıyı elle sınıflarsanız kural **adla değil geometrik parmak
iziyle** (hacim + üç ölçü) saklanır: bir COMPOUND'u standart yapmak
bütün COMPOUND'ları standart yapmaz, ama aynı tedarikçi parçası başka bir
modelde yine tanınır.

#### KURAL: standart tanımı belirsizse program söyler

Cıvata, somun, pul, yay, rulman... tiplerinin sonu yok; hepsine kural
yazılamaz. Bu yüzden program, CAD hangisi olursa olsun, **standart
(satın alınan) parça tanımı belirsiz olan her parçayı listeler** ve BOM
ya da tüm çizimlerden ÖNCE sorar:

| durum | ne demek |
|-------|----------|
| geometri: standart sayıldı – onaylayın | adı bilgi taşımıyor, biçiminden cıvata / somun / perçin somun... sayıldı |
| standart olabilir – kontrol edin | adı bilgi taşımıyor, biçiminde satın alınan eleman işareti var: **dönel küçük parça**, **diş / helis / tırtıl modelli**, **helis yay** |
| tanınmadı: adsız katı | adı yok, biçimi bilinen bir elemana uymuyor |
| ad ile biçim çelişiyor | adı üretim diyor, biçimi standart eleman |

Soru penceresinde:

- **EVET** – olduğu gibi kabul et ve devam et. Kabul, tarihiyle çıktı
  klasörüne ve `rapor.md`'ye yazılır ("çıkana razı olundu").
- **HAYIR** – liste `STANDART_KONTROL.xlsx` olarak yazılır, iş durur.
  Tasarımcı CAD'de düzeltir (Source = Made/Bought ya da parça adı) **ya da**
  listedeki `kaynak` sütununa **Bought / Made** yazar; dosya 2. adımda
  **Malzeme listesi yükle (Excel / CSV)…** ile geri verilince sınıflar oradan alınır (aynı
  numarayı taşıyan farklı parçalar ölçüleriyle ayrılır).
- **İPTAL** – vazgeç.

Aynı liste bir kez kabul edildiyse bir daha sorulmaz. İşaretler **karar
değildir**: 5 gerçek modelde adı standart diyen 60 komponentin hepsi en az
bir işaret taşıyor, ama adı üretim diyen 14 parça da (burç, kare delikli
plaka) taşıyor; bu yüzden liste yalnız adı bilgi taşımayan parçaları kapsar.

#### Bir kez düzeltin, benzerlerini program tanısın (öğrenme)

Kural bilmediği bir parçayı yanlış sınıflarsa **2. sekmede** satırı seçip
**Üretim parçası / Standart / Kaynak dikişi** düğmesine basın. Program iki
şey saklar:

1. **Adı** — aynı adlı parça bundan sonra her modelde öyle sınıflanır.
2. **Biçimi** — ölçekten ve duruştan bağımsız bir *biçim imzası*: yüz
   sayısı, yüz tiplerinin alan payı, eylemsizlik oranları, yoğunluk.
   Adı bir şey söylemeyen (`510206505-00`, `COMPOUND`) ve biçimi
   buna benzeyen parçalar da **kendiliğinden** aynı sınıfa geçer — o
   modelde hemen, sonraki modellerde açılırken. M6 perçin somunu bir kez
   gösterilince M8'i de tanınır; her yeni parçayı tek tek bildirmeniz
   gerekmez.

Adı ne olduğunu söyleyen parçaya (`... SACI`, `... BRAKETI`, `M6 SOMUN`)
öğrenme dokunmaz; bir parçanın kendi elle verilmiş sınıfı her zaman
önce gelir. Listede *(benzerinden öğrenildi)* yazar.

**Ölçüldü** — 4 gerçek modelde adları farklı 636 komponent arasında 13190
benzer çift çıktı; yalnız 1'i farklı sınıftan (bir bağlantı braketi ile
25×6,5×1 pul — ikisinin de adı ne olduğunu söylediği için öğrenme onlara
zaten uygulanmaz).

Sınıf değişince BOM'u yeniden çıkarın.

#### AI ile kontrol (isteğe bağlı)

2. sekmede **AI ile kontrol et**. Akış:

1. **Önce program** kendi bildiği kadar tanımlar (ad, montaj ağacı, geometri
   ölçümü, profil, öğrenilmiş kurallar) — yukarıdakilerin hepsi.
2. **AI 1. tur (yazı):** bütün parçaların sınıfını, kararın kaynağını ve
   programın ölçtüğü bulguları okur; her biri için *doğru / düzelt / belirsiz*.
3. **AI 2. tur (görüntü):** 1. turda emin olamadığı ve programın zaten
   belirsiz bulduğu parçaların **resmi** (gölgelendirilmiş iki görünüş +
   ölçü) gönderilir; AI resme bakıp yeniden karar verir.
4. **Öneriler** listelenir (%80 ve üstü güvenle). Onaylarsanız uygulanır ve
   program **öğrenir**; emin olunmayanlar kontrol listesinde kalır.

Kullanıcının elle verdiği ve CAD'in Made/Bought ile söylediği sınıflar
kesindir, AI'a sorulmaz.

**Ne gönderilir:** parça adı, kodu, adedi, ölçüleri, programın bulguları ve
(2. turda) parçanın resmi. CAD dosyası **gönderilmez**. Veri Anthropic'e
(Claude) gider — firmanızın izni olmalı; program ilk kullanımda sorar.

**Kurulum:** `pip install anthropic` (requirements.txt'te var) ve bir API
anahtarı (console.anthropic.com): `ANTHROPIC_API_KEY` ortam değişkeni ya da
ilk kullanımda program sorar, ayar dosyasına saklar. İnternet yoksa program
AI'sız çalışmaya devam eder.

**Maliyet:** her çalışmada GERÇEK kullanım (token) üzerinden hesaplanıp
günlüğe yazılır; göndermeden önce tahmini tutar sorulur. Ölçülen girdi
büyüklüğüyle tahmin (Claude Opus 5, $5 / $25 her 1M girdi / çıktı token):

| model | parça | 1. tur | resimli 2. tur | toplam (tahmin) |
|-------|-------|--------|----------------|-----------------|
| tente kompleksi | 67 | ~7 bin girdi, ~7 bin çıktı token | ~15 resim | **≈ $0,35** |
| kaynaklı kasa | 197 | ~20 bin girdi, ~18 bin çıktı token | ~40 resim | **≈ $0,80** |

Daha ucuz model için ayar dosyasına `"ai_model": "claude-sonnet-5"`
yazın (~2,5 kat ucuz). Düğmeye basılmadıkça hiçbir şey gönderilmez,
ücret de çıkmaz.

#### Standart ürün kataloğu (STANDART_KATALOG klasörü)

Programın yanındaki `STANDART_KATALOG` klasörüne **yalnız standart (satın
alınan) ürün** konur — adı olmasa da. Sac, lama, profil, üretim parçası
KONMAZ: buradaki her şey standart sayılır.

- **STEP dosyası** (tedarikçinin sitesinden indirilen CAD) — en doğru yol.
  Program biçim imzasını çıkarır; modelde bu biçimdeki, adı bilgi taşımayan
  parça **AI'sız ve ücretsiz** standart sayılır; aynı ailenin başka ölçüsü
  de (M6 konursa M8). Tipi: `katalog: tedarikci / rivnut M8`. İmzalar
  klasöre önbelleklenir, dosya değişmedikçe yeniden okunmaz.
- **Resim** (.jpg / .png, tekli ya da toplu, yüzlerce) — "AI ile kontrol
  et"in resimli turunda **referans** olarak gider. Resimler en çok 8
  paftada toplanır ve önbelleğe alınır (ilk istekten sonra onda bir
  fiyatına). En çok firmaya özel satın alınan ürünlerde işe yarar (özel
  menteşe, kilit, kulp); sıradan cıvatayı AI zaten tanır.

`ornek_*` klasörleri programın kendi çizdiği örnek resimlerdir (AI'a giden
parça resimleriyle aynı biçimde; telif sorunu yok). Başka klasör için ayar
dosyasına `"katalog_klasoru": "..."`. Ayrıntı: klasördeki `OKU.txt`.

#### CAD'den: Made / Bought (en kesin yol)

CATIA'da her ürünün **Özellikler ▸ Ürün ▸ Source** alanı vardır: *Made*
(üretilen) ya da *Bought* (satın alınan). Bu tasarımcının kendi bilgisidir;
addan ya da biçimden tahminden her zaman doğrudur. Pi3D'nin CATIA makrosu
(`catia_malzeme_cikar.CATScript`, Yardım ▸ Malzemeyi CAD'den al) bunu
`malzeme.csv`'nin 4. sütununa (`kaynak`) yazar; CATIA'nın Bill of Material
listesine **Source** sütununu eklerseniz o da olur. Dosyayı 2. adımda
**Malzeme listesi yükle (Excel / CSV)…** ile verince:

- `Bought` → satın alınan (standart): BOM'a adediyle girer, resmi çizilmez;
- `Made` → üretim parçası (adı "kamera" olsa bile);
- bir **alt montaj** Bought ise altındaki bütün parçalar satın alınan sayılır.

Sütun başlığı `Source`, `kaynak`, `Make/Buy`, `Beschaffungsart` olabilir;
değerler `Bought / Made`, `Satın alınan / Üretim`, `Kaufteil / Eigenfertigung`
tanınır. Elle verdiğiniz sınıf bundan da önce gelir.

#### Profiller: kutu, boru, köşebent, U, lama, ekstrüzyon

**Ekstrüzyonun resmi SADEDİR.** Kesit tedarikçinin kalıbıdır; atölye
onu ölçüsüyle değil profil kodu + kesim boyuyla ister. Kesitin göründüğü
uç görünüşlerde kalıbın iç ayrıntısı (R0,97 gibi iç radüsler, iç duvar /
pencere konumları, pahlar) ölçülmez, yalnız gabari; boy görünüşlerinde
iç duvarların gizli çizgileri çizilmez; başlığa `kesit: ekstrüzyon profil
125,5x112,5 (3 hücre, 2 T-kanal, 2 oluk) - kesit ölçüleri tedarikçi
kataloğundan` yazılır. Profil eksenine DİK delikler (işleme) ve
konumları aynen ölçülür.

**Ekstrüzyonun malzemesi SORULUR.** Malzeme CAD'den, malzeme dosyasından
ya da parça adından ("AlMg3") gelmiyorsa program çelik de alüminyum da
varsaymaz: BOM ve Tümünü Üret'ten önce "Evet = Alüminyum, Hayır = Çelik,
İptal = vazgeç" diye sorar; cevap o profillerin koduna yazılır, klasör
ayarında saklanır, bir daha sorulmaz. Komut satırında terminal varsa
sorar, yoksa uyarı yazar.

**Kısa ekstrüzyon da profildir.** Boyu kesitinin 3 katından kısa parça
normalde profil sayılmaz (plaka, blok); ama kesiti ekstrüzyon kanıtı
taşıyorsa (kapalı hücre, T-kanal ya da vida kanalı ve en az 3 öğe) ve 9
istasyonda birebir aynıysa kısa kesilmiş ekstrüzyondur. Böyle bir kesit
bükülerek yapılamayacağı için sac taraması da onu "bükümlü sac"
saymaz. Ölçüldü: `TIRSAN_Ray 112,5` (200 mm, kesit 125,5 x 112,5, 3 hücre
+ 2 T-kanal) artık PROFIL listesinde; yalnız "2 oluk" taşıyan kısa lama
ve saclar (K0 CIVATA LAMASI_3, tente saç parçaları) eskisi gibi profil
değil.

Program adına bakmadan **profilleri** bulur. Parça boyuna 9 yerden kesilir:
kesitlerin çoğu aynıysa, hiçbiri ondan büyük değilse (delik yalnız
küçültür; büyükse kademeli ya da flanşlıdır) ve hacim ≈ kesit × boy ise
parça sabit kesitlidir. Kesitin türü kesitin kendisinden ölçülür:

| kesit | nasıl anlaşılır | yazılan |
|-------|-----------------|---------|
| kutu / kare kutu | tek iç boşluk, dış ve iç dikdörtgen, cidar eşit | `kutu profil 30x50x2` |
| boru | tek iç boşluk, dış ve iç daire | `boru Ø27x8` |
| köşebent (L) | dış hattın dışbükey örtüsünde 1 köşe cebi, 1 büküm (90°) | `köşebent (L) 40x40x4` |
| U / C | 1 yan cebi, 2 büküm (180°); ağzı dar ya da 4 büküm → C | `U profil 50x30x2` |
| I/H, T, Z | 2 cep: karşılıklı yan → I; komşu köşe → T; çapraz → Z | `I/H profil 100x50x5` |
| lama, mil | dolu dikdörtgen / daire | `lama 50x5`, `mil Ø20` |
| ekstrüzyon | içi çok şekilli kesit: birden çok **hücre**, **T-kanal** (ağzı içinden dar oluk), **oluk**, **vida kanalı** ya da 24'ten çok kenar | `ekstrüzyon profil 210,8x26 (2 hücre, 3 T-kanal)`, `sigma (T-kanallı) ekstrüzyon profil 40x40 (4 T-kanal, 1 vida kanalı)` |
| özel kesit (basit) | tek ya da birkaç düz öğeli özel kesit: genellikle kalıp, dövme ya da bükme | `özel kesit profil 60x40 (basit kesit: kalıp / dövme / bükme)` |

Cidar kalınlığı alan ve çevreden hesaplanır (bükümlü köşeler dâhil
doğru çıkar). Parça döndürülmüş, gönye / açılı kesilmiş, delikli ya da
yanları serbest yüzle (B-spline) yazılmış olsa da tanınır.

**Profil biçimli her parça profil değildir:** 1,5 mm sacdan bükülmüş bir U
da sabit kesitlidir ama lazerde kesilip bükülür. Açık kesitte sac taraması
"bükümlü sac" diyorsa parça **sac** kalır, tipine yalnız kesiti yazılır
(`bükümlü sac, U kesit 40x15x1,5`) ve açınımı çıkar. 3 mm ve incesi lama
da sac şerididir. Kutu, boru, mil ve özel kesit profildir.

Profiller **`PROFIL.xlsx`** (ve `PROFIL.csv`) kesim listesine girer:

- *Kesim listesi*: poz, kod, profil, kesit, malzeme, **boy**, adet, toplam
  boy, kesit alanı, kg/m, kütle;
- *Stok özeti*: kesit + malzeme başına toplam boy, en uzun parça ve **6 m
  çubuk sayısı** (toplam boy / 6 m — testere payı ve yerleşim firesi yok,
  sipariş öncesi kaba ihtiyaç).

**Ölçüldü** — 4 gerçek modelde 38 profil (kare kutu 24, boru 7, kutu 4,
alüminyum ekstrüzyon 3) ve 76 profil biçimli bükümlü sac bulundu; kesitler
resmi çizilip tek tek karşılaştırıldı. Denerken çıkan yanlışlar
düzeltildi: kolları eşit olmayan U köşebent, oluklu sac C, 45° kanatlı
sac T sanılıyordu (artık dönüş açısı tam 90° / 180° değilse *özel kesit*).
Kapalı profilin (kutu, boru) açınımı istenirse program gerekçesiyle
reddeder. Sentetik denetim:
kutu, delikli kutu, gönyeli kutu, boru, L, U, dudaklı C, T, I, lama, mil,
sigma — düz ve uzayda döndürülmüş; plaka, blok, kademeli mil, flanşlı
boru ve kısa burç profil sayılmaz.

**Kaynak dikişleri** parça değildir: BOM'a girmez, poz almaz, resmi
çizilmez, montaj resminde görünür. Listede tek satırda toplanır
(*KAYNAK DİKİŞLERİ – 25 tür*), açınca türleri ve adetleri görünür:
`K0 25 MM TEK KAYNAK x103`. Hiyerarşik BOM'da her montajın altında tek
satırdır. `rapor.md`'de türlere göre tablo vardır.

### Adım 2 — BOM ve MALZEME

Komponentler tabloda listelenir. **KAYNAK** sütunu malzemenin nereden
geldiğini söyler:

| değer | anlamı |
|-------|--------|
| `data'dan` | STEP'in malzeme alanında ya da parça adında yazıyor (`1.4301`, `S235`, `AlMg3`, `POM`…), size sorulmaz |
| `seçim` | siz verdiniz |
| `varsayılan` | hiçbiri yoksa çelik kabul edildi |

**Arama:** tablonun üstündeki **Ara (kod / tanım / poz)** kutusuna
yazıp Enter'a (ya da **Bul ▸**'e) basın. Kod, tanım ya da pozunda o
metin geçen satır seçilir ve gösterilir; kapalı alt montaj dalı kendisi
açılır. Enter'a yeniden basınca sıradakine geçer, yanda `2 / 5` gibi
sayaç yazar. Büyük-küçük harf ve Türkçe harf farkı yoktur: CAD adları
çoğu zaman Türkçe harfsizdir (`DIK`, `KOSE`); `dik`, `dık` ya da `köşe`
yazmak yeter. BOM çıkınca sıralama değişir; parçayı satır satır aramak
gerekmez.

**Seçili parçanın resmi:** tablodan bir satır seçince sağdaki **Seçili
parça** kutusunda parçanın küçük izometrik resmi (görünen kenarlar) ve
adı çıkar. Adından ne olduğu anlaşılmayan parçada malzeme / standart /
üretim parçası kararını vermeyi kolaylaştırır. Resim ayrı iş
parçacığında çizilir, program beklemez; aynı parça ikinci kez
seçilince beklemeden gelir. Alt montaj satırında resim yoktur.

Malzeme vermenin yolları:

* Soldaki kutudan malzemeyi seçip **Hepsine uygula**
* Tablodan satır(lar) seçip **Seçili satırlara** *(Ctrl ile çoklu seçim)*
* **Malzeme şablonu yaz (Excel)…** ile şablon çıkarıp Excel'de doldurun, sonra
  **Malzeme listesi yükle (Excel / CSV)…** ile geri verin
* **CAD'inizin parça listesini** doğrudan yükleyin: CATIA'nın
  *Analyze ▸ Bill of Material* çıktısı, SolidWorks BOM'u ya da Excel'den
  kaydedilmiş bir CSV olur. `Part Number` ve `Material` sütunları
  başlıklarından bulunur (bkz. `CATIA_MALZEME.md`)
* **Adım adım:** **Malzemeyi CAD'den al (adım adım)…** düğmesi ya da
  **Yardım** menüsü — aşağıda.
* **CATIA BOM ile eşleştir (adet, eksik, malzeme)…** — CATIA'nın
  *Analyze ▸ Bill of Material ▸ Save As* kaydını (Excel `.xls` / `.xlsx`
  ya da Text) verin; aşağıda.

#### CATIA BOM ile eşleştirme — adet, eksik parça, gerçek malzeme

CATIA V5 (R14 / R17) *Analyze ▸ Bill of Material* kaydı tek tablo
değildir: her alt montaj için ayrı bir **"Bill of Material: <montaj>"**
bölümü, her bölümün kendi başlık satırı ve sonda **"Recapitulation of:
<montaj>"** özeti (parça başına toplam adet, "Different parts / Total
parts") vardır. Pi3D bu dosyayı bölüm bölüm okur (eski sürüm tek tablo
sanıp özet bölümündeki TraceParts sütunlarını kod / malzeme diye
okuyordu — düzeltildi) ve STEP'ten çıkan BOM ile eşleştirir:

* **Eşleşme anahtarları:** Part Number, Nomenclature (çoğu zaman STEP
  dosya adıdır: `ALP0043-01-01-01.stp`), örnek adı (`X.1.1`), CATPart
  dosya adı; `.CATPart.28`, `.1` gibi ekler ve "Copy (1) of" dikkate
  alınır. Aynı STEP kaydına düşen sağ / sol profil (aynı nomenclature)
  tek öbek sayılır, adetleri toplanır.
* **Durumlar:** `eşleşti` (adet aynı), `adet farklı` (CATIA / STEP
  adedi ayrı — modeli ya da STEP dışa aktarımını denetleyin), `STEP'te
  yok` (CATIA'da var, STEP'te katı yok — çoğu zaman STEP'e alınmamış
  cıvata / somun / perçin), `CATIA'da yok` (STEP'te var, listede yok).
  Alt montajlar eksik sayılmaz.
* **Çıktı:** çıktı klasörüne `BOM_ESLESTIRME.csv` / `.xlsx` / `.md`;
  ekranda renkli tablo (turuncu: adet farklı, kırmızı: CATIA'da yok,
  gri: STEP'te yok). Çıktı klasörü seçili değilse yalnız ekranda.
* **Gerçek malzeme:** listede **Material** sütunu varsa (Define formats
  ile görünür yapılmışsa) parçaların malzemesi oradan alınır (KAYNAK:
  seçim); standart elemanlarda TraceParts `materialgruppe` alanı
  (ör. `Steel`) kullanılır. Material sütunu yoksa program bunu söyler;
  eşleştirme yine yapılır. **Source** (Made / Bought) doluysa sınıf da
  oradan alınır.
* **Malzeme listesi yükle** düğmesine böyle bir dosya verilirse de aynı
  eşleştirme çalışır.

Komut satırı: `--catia-bom dosya.xls` (aşağıda).

#### Malzemeyi CAD'den almak — sihirbaz

STEP geometriyi taşır, malzemeyi çoğu zaman **taşımaz**: AP214/AP242'de
malzeme adı ve yoğunluğu için yer vardır ama CAD'lerin çoğu varsayılan
ayarla yazmaz. Malzemesi bilinmeyen parça çelik sayılır, kütlesi yanlış
çıkar. **Yardım ▸ Malzemeyi CAD'den al** dört adımda yol gösterir:

| adım | ne olur |
|------|---------|
| 1 STEP'te ne var | açık modelde kaç parçanın malzemesinin STEP'ten geldiği, kaçının adından tanındığı, kaçının bilinmediği |
| 2 CAD sistemi | SolidWorks, CATIA V5, Siemens NX, PTC Creo, Autodesk Inventor, Solid Edge, Parasolid/diğer |
| 3 Parça listesi | o CAD'de **parça no + malzeme (+ yoğunluk)** sütunlu listeyi almanın adımları; SolidWorks ve CATIA için **makro** (Makroyu kaydet…) |
| 4 Dosya | seçilen dosya **önizlenir** — hangi parça hangi malzemeyi alacak, hangisi dosyada yok, hangi ad tanınmadı; ancak **UYGULA** ile işlenir |

Okunan dosyalar: CSV, TXT, sekmeli metin, **Excel .xlsx**, JSON.
Ayırıcı (sekme ; ,) ve kodlama (UTF-8, UTF-16, Windows Türkçe) kendiliğinden
anlaşılır. Başlıklar İngilizce, Almanca, Fransızca, Türkçe ya da CAD'in
kendi adıyla olabilir (`Part Number`, `Teilenummer`, `SW-Material`,
`PTC_MATERIAL_NAME`, `Werkstoff`, `Malzeme`...). Eski Excel (.xls) okunmaz;
program bunu söyler ve .xlsx/CSV olarak kaydetmenizi ister.

**Yoğunluk sütunu önerilir** (`Density`, `SW-Density`, `Dichte`,
`Yoğunluk`; kg/m³ ya da g/cm³ - birim hücrede ya da başlıkta yazıyorsa
oradan, yazmıyorsa büyüklüğünden anlaşılır). Yoğunluk verilirse:

* adı **tanınmayan** malzeme (ör. `Sonderlegierung AX7`, 2,71) çeliğe
  düşmez — CAD'in yoğunluğuyla ayrı bir malzeme olarak alınır ve malzeme
  kutusunda görünür;
* adı tanınan ama yoğunluğu tablodakinden **%2'den çok** farklıysa
  CAD'inki esas alınır.

Tanınan malzeme adları için **Yardım ▸ Tanınan malzemeler**. `Steel`,
`Stahl`, `S235`, `C45`, `42CrMo4`, `AISI 1020`, `1.0038`, `Hardox`,
`AISI 304`, `1.4301`, `AlMg3`, `6082`, `CuSn8`, `Brass`, `POM`... gibi
adlar ve malzeme numaraları tanınır.

**STEP'teki malzeme de okunur** (bu sürümde düzeltildi — önceki sürümler
STEP'e yazılmış malzemeyi hiç okumuyordu). Malzeme adı ve yoğunluğu
yazılmışsa KAYNAK sütununda `data'dan` görünür.

> SolidWorks makrosu SolidWorks olmadan yazıldı ve denenemedi; ilk
> kullanımda 4. adımdaki önizlemeyi kontrol edin.

> Kutudaki malzeme yalnız **uygulanacak** malzemedir. Bir parçaya alüminyum
> verdiğinizde diğerleri çelik kalır.

**BOM ÇIKART ▸** → `BOM.xlsx`/`.csv`, `BOM.md`, `BOM_AGAC.xlsx`/`.csv`,
`BOM_AGAC.md`, `olculer.xlsx`/`.csv`, `olculer.json`, `rapor.md` ve profil
varsa `PROFIL.xlsx` (kesim listesi) yazılır. Tablo gerçek ölçü ve
kütlelerle dolar. **Excel'de .xlsx'i açın** (bkz. 4. bölüm: CSV'deki
`15.2243` Türkçe Excel'de `152.243` görünür).

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

Bütün detay resimleri (ve istediyseniz montaj resmi) `DXF/` klasörüne
üretilir, dosyalar listelenir. Listede bir DXF'e çift tıklarsanız önizlemesi
açılır. Bu sekmenin kendi **ÇİZİMLERİ ÜRET** düğmesi vardır: örnek onayına
dönmeden çizimleri yeniden ya da yalnız eksikleri üretebilirsiniz.

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

**Büküm ekseni (B1, B2 …).** Her büküm için resimde **tek** bir
noktalı-çizgili (-.-.-) çizgi vardır: **büküm ekseni**, yani büküm
bölgesinin (büküm payının) ortası. Abkantta bıçak bu çizgiye gelir.
Kenar ölçüleri ve çizelgedeki **EKSEN** sütunu bu çizgiye verilir;
**BÖLGE** sütunu yarıçapın başladığı ve bittiği yerdir (iki teğet
çizgisi, resimde çizilmez). Eski sürüm her büküm için bölgenin başını ve
sonunu iki çizgi olarak çiziyordu; iki çizgi büküm ekseni sanılıyordu.
Büküm **yönü** (yukarı / aşağı) resme yazılmaz: yalnız bükümlerin birbirine
göre yönü bilinir, resmin baktığı yüze göre mutlak yönü güvenilir değil.

**Profil görünüşü (yön).** Büküm resminin sağında parçanın **büküm
ekseni yönünden bakışı** (profil) çizilir; kanatlar **K1 …** (dış
ölçüsüyle) ve bükümler **B1 …** açınımdaki numaralarla işaretlidir.
Hangi kanadın hangi yöne büküldüğü buradan okunur – program yönü
tahmin etmez, gösterir. Kesim konturu çıkmayan (yalnız blank ölçüsü verilen)
parçada da profil kesitten çizilir. Kısa kanatlar yazıya göre küçükse
profil standart ölçekle büyütülür (2:1, 5:1 …; başlıkta yazar).
Profilin altında parçanın küçük bir **perspektifi** (izometrik) vardır:
bükülmüş hâli bir bakışta görünür.

**ABKANT (CNC) tablosu – kanat DIŞ ölçüleri.** CNC abkant (Baysal,
Delem ünite vb.) büküm çizgisine göre değil **dayamaya** göre büker:
usta parçanın profilini kanat **dış** ölçüleriyle girer, dayamanın
yerini tezgâh kendisi hesaplar. Açınım resminde bu yüzden her kanadın
dış ölçüsü **sanal köşeye** (dış yüzlerin uzantılarının kesiştiği yere)
kadar verilir: K1, K2 … ve aralarındaki büküm (B1 …), iç açı, iç R.

- Düz kısımlar açınımdaki büküm bölgeleri arasındaki gerçek duvar
  boylarıdır. Her büküm, iki yanındaki kanada (iç R + t)·tan(büküm/2)
  kadar dış pay ekler; 90° bükümde bu iç R + t'dir.
- Bu ölçü **K-faktöründen bağımsızdır**: atölyenin gerçek K'sı farklı
  olsa da değişmez. Büküm ekseninin açınımdaki yeri ise K'ya bağlıdır.
- Kenarlar açınımın en dış kenarlarıdır (en geniş yer).
- Aynı ölçüler `ACINIM.csv / .xlsx` listesinde `kanat_dis_olculeri_mm`
  sütunundadır.
- Doğrulama: K0_ON KILIT SACI_IC → 13 – 26 – 53 – 26 – 13; parçanın 3B
  gabarisi 26 × 53 (omega profil). L sacta (100 + R3 + t2) 105 – 105,
  K 0,33 / 0,4 / 0,5'te aynı.

**Bükümü kesen pencere tek deliktir.** Pencere ya da kesik büküm
bölgesine taşıyorsa duvar ve büküm ayrı açılır; aralarında kesilemeyecek
incelikte (sac kalınlığının dörtte birinden dar, en az 0,2 en çok 0,5 mm)
malzeme şeridi kalırsa iki delik tek delik yapılır. Yoksa lazer boşluğun
içinde fazladan kesim yapar (K0_ON KILIT SACI_IC ve simetriğinde 0,06 mm
şerit vardı; birleşen pencerenin alanı, bükümsüz öbür pencereyle birebir
aynı: 1.057,9 mm²). Uzak deliklere dokunulmaz.

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

#### Çok yönlü büküm — 3B genel açınım

Büküm eksenleri birbirine paralel olmayan sac (gövdesi kırık dikme,
iki yönde kanatlı braket, kilit sacı) 2B yöntemle açılamaz: 2B yöntem
büküm eksenini Z'ye döndürüp tek kesit alır. Böyle parçalarda program
**3B genel açınımı** kullanır: her duvar kendi bükümünün ekseni
etrafında döndürülerek düzleme serilir, büküm bölgesi açı × nötr
yarıçap kadar yayılır, delikler aynı dönüşümden geçer; sonuç yine
hacimle (alan × kalınlık) ve tek parça olmakla denetlenir. Karluna
SOL_DIKME'de (533 mm şapka profili + 768 mm 5° kırık kanal, tek sac)
1312,84 × 287,48 mm çıktı; CATIA'nın kendi açınımı 1312,8 × 287,4.

Resimde büküm çizgileri eğik olabilir; çizelgede her bükümün ekseni iki
uç noktasıyla (x; y, sol alt köşeden) yazılır, etiketi (B1, B2 …)
çizginin kendi ucunda durur, başlıkta "ÇOK YÖNLÜ BÜKÜM" notu olur.
ABKANT kanat dış ölçüsü çizelgesi bu parçalarda yazılmaz (kanat dizisi
tek doğrultuda değildir).

3B yöntemin tanıdığı özel durumlar:

- **Levhanın ortasından kesilip bükülmüş dil** (bağlantı braketi): dilin
  büküm teğeti levhanın dış kenarında değil kesiğin kenarındadır; hangi
  yanın malzeme olduğu duvarın kendi dış çizgisiyle (delikler dahil)
  sınanır, dil açınımda kesiğin içine serilir.
- **Yarıkla bölünmüş kanat**: tek büküm hattı üstünde, aynı düzlemde
  ama birbirinden ayrı duran kanat parçaları (1920 mm'lik yardımcı şasi
  kanadı üç parça). Büküm her parça için kendi aralığıyla kopyalanır;
  çizelgede ayrı satır çıkar. Aynı duvara ikinci bir yoldan varılıyorsa
  (üç parça da aynı sürekli dönüş kanadına bağlanır) dönüşümler eşitse
  çevrim sayılmaz; farklıysa parça kapalı kesittir ve açınım verilmez.
- **Büküm ağacına bağlanamayan duvar** sessiz geçilmez: alanı küçük de
  olsa resimde "DİKKAT: n duvar (… mm2) büküm ağacına bağlanamadı,
  konturda EKSİK olabilir - MODEL KONTROL" yazar.

Açılamayan parçalar (tasarım gereği): kapalı kesit (boru, kutu profil,
büküp kapatılmış sac), hacim denetimi tutmayan parça (kabartma, pres
şekli), sac olmayan gövde.

#### Açınım ölçüleri — paralel ve düz

Açınım resminde blank gabarisinden başka: sol tarafta **düz zincir**
(kenar → B1 → B2 … → kenar: blank'ta çizilip ölçülecek kanat boyları;
rakamı sığmayan dar halka yazılmaz) ve her büküm ekseninin alt kenardan
**paralel** ölçüsü kademeli olarak verilir — açınımı teyit için ikisi
birden. Konturun çıkıntı / girinti basamakları (kenara paralel ama
kenarda olmayan doğrular) için derinlik ve başlangıç / bitiş konumu
yalnız istenirse ölçülenir (ayar dosyasında `acinim_basamak: 1`;
varsayılan kapalı, çünkü sık basamaklı parçada bu ölçüler konturla
çakışıyordu).

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

**Kâğıt her zaman yataydır.** Boyu siz verirsiniz (A3); yön yataydır.
Program dik duran parça için kendiliğinden dikeye geçmez — teknik
resimde alışılmış olan yatay paftadır ve dosyalama böyle kolaydır.
Dikey kâğıt yalnız siz isterseniz kullanılır: komut satırında
`--kagit A3-D`. O zaman listede ve paftanın sağ üst köşesinde "A3 dikey"
yazar, PDF adına da girer: `P04_KONSOL_A3D.pdf`.

Aşağıdaki şema yatay A3'tir (420 × 297 mm); istenen dikeyde aynı yapı
90° döner, antet kutusu yine sağ alt köşededir:

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

#### Pi3D anteti (firma anteti yokken)

Firma anteti tanımlı değilse sağ alttaki 150 × 100 mm kutuya **Pi3D'nin
kendi anteti** çizilir: üstte Pi3D ve PiVision logolu şerit (DXF'e IMAGE
olarak girer; `pi3d_antet.png` dosyası DXF'in yanına bir kez yazılır, CAD
programı ve PDF basımı oradan okur), altında şu kutular kendiliğinden
dolar:

| kutu | nereden gelir |
|------|---------------|
| PARÇA ADI, RESİM NO, DOSYA | parçanın adı, kodu, DXF dosya adı |
| MALZEME, KÜTLE | BOM |
| ÖLÇEK, KÂĞIT / SAYFA | paftanın ölçeği, kâğıt ve sayfa numarası |
| ÇİZEN, ONAYLAYAN | 7. adımda yazılan tarih, çizen, onaylayan (saklanır) |

Sığmayan yazı önce küçülür, sonra kısaltılır (ölçülerek). Kutuyu boş
isteyenler (kendi antetini yapıştıracaklar) ayar dosyasına
`"antet_pi3d": 0` yazar: o zaman alan eskisi gibi çizilmez.

Firma anteti tanımlıysa Pi3D anteti çizilmez; resim firmanındır.

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
            (sag alt kosede Pi3D logolu antet; antet_pi3d: 0 ile
             bos birakilir, kendi antetinizi oraya yapistirirsiniz)
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
sayılır ve `123 x 20` diye tek ölçü konur. Bu ISO'nun kendi
sadeleştirmesidir.

**Dizi dışındaki her konum ÖLÇÜSÜ AYNI KENARDAN alınır** (datumdan
ölçülendirme). Zincir (noktadan noktaya) ölçülendirme kullanılmaz,
iki sebepten:

1. **Tolerans birikir.** Zincirdeki her ölçünün toleransı bir
   sonrakine eklenir; son deliğin yeri ilk deliğinkinden çok daha
   belirsiz olur. ISO 129-1 bunu açıkça uyarır.
2. **Okunmaz.** İlk sürümde zincir farklı delik grupları arasında
   kuruluyordu: 175 mm'lik plakada `10 | 3,2 | 148,5 | 3,2 | 10`
   çıkıyordu. Oradaki 3,2, Ø10,2 deliğiyle Ø8,1 deliği arasındaki
   boşluktu — kimsenin işine yaramayan bir sayı — ve Ø8,1'in kenardan
   yerini bulmak için toplama yapmak gerekiyordu. Datumdan ölçüde
   `10 | 13,2 | 161,7 | 165 | 175` yazar, hepsi doğrudan okunur.

Kısa ölçü içeride, uzun dışarıda durur; ölçü çizgileri kesişmez.

**Ayna çiftleri iki kez ölçülmez.** 175 mm'lik plakada delikler 10 /
13,2 / 161,8 / 165'te duruyorsa parça ortadan simetriktir
(10+165 = 13,2+161,8 = 175). Dördünü de ölçmek gereksiz: **ikisi
yeter**, gabari (175) ve simetri işareti öbür ikisini zaten verir —
"tekrarlanan öznitelik bir kez ölçülendirilir". Simetri bulunduğunda
resme **simetri ekseni ve işareti** (eksen çizgisinin uçlarında iki
kısa paralel çizgi) konur; işaret olmadan okuyan öbür yarının nereye
geldiğini bilemez.

Simetri yalnız dağınık deliklerde aranır; eşit adımlı dizi zaten
"n x adım" ile tek ölçüye inmiştir.

#### Köşe pahı mı, eğik kesim mi

Eksenlere paralel olmayan bir kenar resimde **iki ayrı şey** olabilir
ve ikisi başka türlü ölçülendirilir:

**Köşe pahı (pah kırma).** Üç şartı birden tutar: (1) iki ucu da
birbirine dik, eksene paralel iki kenara değiyor — yani bir köşeyi
kesiyor, (2) bacakları eşit (45°), (3) görünüşe göre küçük (en çok
%20). Böyle bir kenarın **açısı ölçü konusu değildir**: keskin köşe
kalmasın diye kırılmıştır. Ok (kılavuz) ucunda `5 x 5` diye yazılır,
aynı ölçüdekiler tek notta toplanır: `4x 5 x 5`.

> İlk sürümde buna hipotenüs (`7,1`) ve açı (`45°`) veriliyordu.
> İkisi de atölyenin işine yaramıyor, üstelik resmi kalabalıklaştırıyordu.

**Eğik kesim.** Köşe kırma değil, parçanın gerçek biçimi. Dış hattaki
eğik kesimler **girinti olarak**, uçlarının sanal keskin köşesinden
ölçülür (aşağıda). İçerideki eğik çizgilerin uçlarına ayrıca konum
verilmez: doğrulamada bu türün %70'inin bir yuvarlatmanın teğet
noktasına, yani tasarımda karşılığı olmayan bir yere denk geldiği
görüldü.

Üç şart birden aranır, çünkü bir köşeden geçen **büyük** bir 45°
kesim parçanın biçimidir, köşe kırma değil: 120 × 80 plakada 20 × 20
bir kesim pah sayılmaz, 5 × 5 sayılır.

Bunun için kenarlar **çiziminden geri tanınıyor**: HLR izdüşümü
kenarları analitik korumuyor (ölçülen: bir görünüşte 8 doğru + 2 daire
ama 18 B-spline), pahlar ve kesikler B-spline olarak geliyor. Her
kenar örneklenip doğru / yay / eğri diye ayrılıyor.

Ölçü yazıları makul hassasiyette: izdüşümden 11,8674 gibi değerler
çıkabiliyor, tam sayıya yakınsa tam sayı yazılır — o kadar hassas bir
ölçü ne ölçülür ne tutturulur.

**Gabari en dışarıdadır.** Teknik resimde küçük ölçüler içeride, toplam
ölçü en dışarıda durur; tersi olursa ölçü çizgileri kesişir. Bu yüzden
gabari ölçüsü konum ölçülerinden SONRA, onların **ölçülen** sınırının
dışına çizilir.

**Yer tahmin edilmez, ölçülür.** Dar bir aralıkta ("3,2") yazı ölçünün
içine sığmaz ve CAD onu uzatma çizgilerinin dışına kaçırır; nereye
kaçıracağı ölçü stiline bağlıdır. Her ölçü çizilir, yazısının gerçek
sınırı ölçülür, çakışıyorsa silinip bir alt kademede yeniden denenir.
Örnek montajın 16 resminde 435 yazıda sıfır çakışma.

#### Datum: parçanın kendi XYZ çerçevesi

STEP dosyasında datum bilgisi yoktur (ölçüldü: örnek montajda tek bir
DATUM ya da tolerans varlığı geçmiyor), "ilk işlenen yüzey" dosyadan
bilinemez. Program kendi üç düzlemli çerçevesini kurar (ISO 5459):
parçanın sınır kutusunun en küçük köşesi sıfır noktası, orada buluşan
üç yüzey **A, B, C**. En geniş yüzey A'dır. Bütün görünüşler bu tek
çerçeveden ölçülür; ekseni ters dönen görünüşte (ARKA, SOL, ALT) sıfır
karşı kenardadır. Böylece ÜST'te 25 olan delik ALT'ta da 25'tir.
A/B/C simgeleri (dolu üçgen + kare içinde harf) her biri bir kez,
göründüğü ilk görünüşe konur.

Bir delik yalnız **bir görünüşte** konumlanır — çapının yazıldığı
görünüşte. SAĞ ile SOL aynı delikleri gösterir; ikisinde birden ölçmek
tekrar olur.

#### Girinti, çıkıntı ve iç pencere (yuva)

Kenardan alınmış çentik, dışarı taşan kulak, köşe kesiği ve parçanın
içindeki yuva / pencere de konumlanır:

- **Girinti:** başı ve sonu datumdan; iç çentikse derinliği ayrıca.
  Köşe kesiğine derinlik yazılmaz — iki bacağını iki konum verir.
- **Çıkıntı:** ayrı bir tür değildir; dışarı taşan kulağın iki yanı
  girinti olarak çıkar ve verilen ölçüler kulağın yerini verir.
- **İç pencere (yuva, cep):** dört kenarı datumdan.
- **Slot (uzun delik):** kenarından (teğet çizgisinden) DEĞİL, **yay
  merkezlerinden** ölçülür (ISO 129-1): slot boyunca datumdan yakın yay
  merkezine konum + **iki merkez arası** (slot boyu), dik yönde slotun
  **merkez çizgisine** konum; genişlik `2x R5,5` ile. Slotta eksen çizgisi
  ve iki merkezde dik kısa çizgi çizilir (ölçünün gittiği yer görünsün).
  Slot **3B modelden** bulunur (delik gibi): aynı yarıçaplı, paralel
  eksenli iki yarım silindir. Görünüşte gizli kalan slot da (üst flanşın
  altındaki) göründüğü ilk görünüşte konum alır. Delik dizisinin
  aralığına düşen slotun konumu atılmaz (yalnız dizinin kendi elemanları
  tekrar ölçülmez). Delikler zaten her zaman merkezlerinden ölçülür; bir
  çizginin ikiye böldüğü delik (flanş çizgisi deliğin üstünden geçiyor)
  "pencere" sayılıp kenarlarından ölçülmez.

  ```
  eskisi (yanlış)                    şimdi
  |--52--| slotun alt kenarı          |--34,5--| birinci yay merkezi
  |----64----| slotun üst kenarı      |--34,5--|--11--| merkezler arası
  ```

**Bükümlü sacın dış hattı.** Girinti, pencere ve slot ölçüsü görünüşün
DIŞ HATTI kurulabilirse verilir. Bükümlü saclarda dış hat üç sebeple
kurulamıyordu, üçü de düzeltildi: HLR aynı kenarı **ters yönde** iki kez
veriyordu (kopya sayılmıyordu), flanş çizgileri dış hatta **T biçiminde**
biniyordu (uç, öbür kenarın ortasına değiyor: kenar orada bölünür),
**köprü** kenar (iki yanında aynı yüz) yüzü bütünüyle attırıyordu (köprü
ayıklanır). Ölçüldü: 5 modelde resme giren konum ölçüsü 4.220'den
4.933'e çıktı (slot 292 → 618, girinti 604 → 773, pencere 498 → 624),
3B doğrulamada **hatalı 0**.

**Dizi adımı** 0,01'e yuvarlanır ve Türkçe yazılır: `2 x 90` (modelin
0,0005 mm'lik kayması `2 x 89.9995` yazdırıyordu).

**Ø / R yazısı elemanın yanına** konur: yer denetlenirken görünüşün
KUTUSU değil gerçek ÇİZGİLERİ (görünüş, gizli, eksen, ölçü çizgileri) ve
yazılar dolu sayılır; yazı parçanın içindeki boş alana, deliğin ya da
slotun hemen yanına gelebilir. Önceden kutu dolu sayıldığı için her yazı
görünüşün dışına, uzun kılavuzla gidiyordu. Yakında yer yoksa yine
görünüşün üstüne çıkar.

**Ölçü okları:** DXF'te her ölçünün iki ucunda dolu ok vardır (AutoCAD
kendi çizer). Programın önizlemesi ok bloklarını çizmiyordu; artık
çiziyor.

**Sanal köşe.** Çentiğin ağzı yuvarlatılmışsa ölçü yayın teğet
noktasına değil, doğru kenarın uzantısının kesiştiği **sanal keskin
köşeye** verilir — tasarımın asıl ölçüsü odur. Örnek: Dachplatte'nin
köşe kesiği teğet noktalarında 41,09 / 22,51 çıkıyordu; doğru ölçü
45 / 20,05, yani 20 x 5'lik bir kesik.

Kenarın ucundaki yuvarlatma girinti sayılmaz (R ölçüsü zaten var).
Çok girintili bir kenar (dövme parçanın eğri hattı gibi) "düz kenar +
çentik" değil biçimin kendisidir; ölçülmez.

#### Hata oranı: her konum 3B modelle doğrulanır

Kural: **hata olasılığı yüksek olan ölçü türü hiç yazılmaz.** Hedef
%0,5–1'in altı.

Program her konumu görünüşten (2B) bulur. Resme yazmadan önce aynı
konumun 3B modelde gerçek bir **tasarım seviyesine** denk geldiğine
bakar: o eksene dik düz yüzey, delik ekseni, silindirin ucu ya da eğik
bir kenarın sanal köşesi. Denk gelmeyen ya da iki ayrı seviye arasında
belirsiz kalan konum **yazılmaz**. Geçen değer modeldeki tam seviyeye
oturtulur; basılan sayı tasarım ölçüsünün kendisidir.

Ölçüldü (4 gerçek model, 183 parça): **1992 konum ölçüsünde 0 hata**
— %95 güvenle oran %0,15'in altında. Bu denetim olmasa şasi montajında
ölçülerin %6,4'ü yanlış olurdu (girintilerin %27'si).

Bilerek yazılmayanlar:

- Eksenlere tam paralel olmayan (0,06°'den fazla eğik) deliklerin
  konumu — çapı yazılır. 0,4° eğik bir duvarda deliğin merkezi sacın
  bir yüzünden öbürüne 0,02 mm kayıyordu.
- Dövme, döküm ve eğri yüzeyli parçalarda karşılığı kesinleşmeyen
  girinti ve konumlar.
- Datumu gerçek bir yüzey olmayan yöndeki konumlar (yuvarlak bir
  kenarın ucu, eğik bir yüzün köşesi).

Kendi modelinizde denetlemek için:

```
python test/olcu_dogrulama.py model.stp            tür tür hata oranı
python test/olcu_dogrulama.py --ayrinti model.stp  her hatayı yazar
```

> **Henüz yok:** form/büküm başlangıç konumları ve açısal ölçüler.

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
P05_01_050_000_01_U-Blech.dxf              detay resmi (ölçülü, paftalı)
P05_01_050_000_01_U-Blech_acinim.dxf       BÜKÜM RESMİ (açınım, büküm
                                           eksenleri, ABKANT tablosu, profil)
P05_01_050_000_01_U-Blech_acinim_lzr.dxf   LAZER (bükümlü): yalnız kontur
P07_09_020_000_03_Plaka_Lzr.dxf            LAZER (düz sac): yalnız kontur
```

**Kural: açınımı çıkan her parçanın iki dosyası vardır.** Açınım (6.
adım) çalışınca büküm resmi `ACINIM/..._acinim.dxf` ile birlikte lazer
kesim dosyası `LZR/..._acinim_lzr.dxf` de **kendiliğinden** yazılır ve
`LAZER.csv`'ye girer. Lazer dosyasında büküm eksenleri yoktur. Açınımı
çıkıp da kesim konturu çıkarılamayan parça (yalnız blank ölçüsü)
`LAZER_yapilamayanlar.txt`'de sebebiyle yazılır.

#### Listede kimler var

**Lazer kesim bütün sac parçalar içindir** — yalnız bükülecekler
değil. Uygulamanın yapısı: **AÇINIM (6. adım) = bükülecek saclar**
(abkant / pres), **LAZER (8. adım) = bütün saclar**: düz sac doğrudan
kendi konturundan kesilir, bükümlü sac açınımının konturundan kesilir
ve sonra bükülür.

| grup | ne | seçim |
|------|----|-------|
| üstte | 6. adımda **açınımı çıkan** bükümlü saclar (kontur hazır) | **seçili gelir** |
| sonra | öbür **bükümlü** saclar (açınım burada hesaplanır) | **seçili gelir** |
| sonra | **düz** saclar — lazer kesim düz, kendi konturundan | **seçili gelir** |
| altta | önceden üretilmişler | seçisiz |
| — | sac olmayanlar (freze, torna, profil) | listeye hiç alınmaz |

6. adıma uğranmamışsa sac taraması burada yapılır (parça başına ~20 ms).

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
3. **Save As…** ile **Excel (`.xls`)** ya da `.txt` olarak kaydedin — CSV
   gerekmez, Pi3D eski Excel (`.xls`), `.xlsx`, sekmeli metin ve HTML
   tabloyu doğrudan okur
4. Pi3D'de **Yardım ▸ Malzemeyi CAD'den al** → 4. adımda o dosyayı seçin
   (ya da 2. adımda → **Malzeme listesi yükle (Excel / CSV)…**)

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

CATIA'nın *Analyze ▸ Bill of Material* kaydıyla BOM eşleştirme (adet,
eksik parça) ve — Material sütunu varsa — gerçek malzeme:

```
python pf3_olcu.py montaj.stp -o cikti --catia-bom montaj_bom.xls
```

Çıktı klasörüne `BOM_ESLESTIRME.csv / .xlsx / .md` yazılır; özet
terminale basılır. Ayrıntı: Adım 2'deki "CATIA BOM ile eşleştirme".

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
| `--kagit A4..A0` | kâğıt boyu (varsayılan A3), her zaman yatay. `A3-D` denirse dikey kullanılır |
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
| `--zip` | çıktıları `cizimler.zip`'te topla (klasör düzeniyle) |
| `--eksik` | yalnız eksik ya da eskimiş çizimleri üret; aynı model ve ayarla üretildiği kayıtlı olanlar atlanır |
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

### Excel: `BOM.xlsx`, `BOM_AGAC.xlsx`, `olculer.xlsx`, `PROFIL.xlsx`, `ACINIM.xlsx`, `LAZER.xlsx`

**Excel'de .xlsx'i açın.** CSV'de rakam yazıdır, Excel onu bölgesel ayara
göre yorumlar: Türkçe Excel'de nokta *binlik* ayırıcıdır, CSV'deki
`15.2243` kg **152.243** görünür (yüz elli iki bin!), poz `1.1` tarihe
(1 Oca) döner, eski Excel'de Türkçe harfler bozulur. .xlsx'te her hücrenin
türü dosyada yazılıdır: kütle SAYI, poz ve kod YAZI; hiçbir ayar onu
değiştiremez. Başlık satırı dondurulmuş ve süzgeçlidir; kütle 3 ondalıklı.

CSV'ler de artık Türkçe Excel'e göre yazılır: ondalık **virgül**, binlik
**nokta** (`1.513,76`), sütun `;`. Tam değerli sayı binliksiz kalır (`1234`):
eski sürümlerin noktalı ondalığı (`152.243` = 152,243) ile karışmasın diye;
program eski CSV'yi okurken de bu kuralı kullanır (virgül varsa Türkçe
yazım, virgülsüz tek nokta eski ondalık). .xlsx'te sayılar `#.##0,000`
biçimindedir: Türkçe Excel binlik noktayı kendisi koyar. Rapor, pafta
tablosu (BOM, büküm tablosu, gabari, toplam kütle), ekrandaki ölçü ve kg
yazıları da aynı Türkçe yazımdadır. Çizimdeki **ölçü rakamı** ondalık
virgüllü, binliksiz yazılır (`1513,8`): teknik resimde (ISO 129) ölçü
rakamına binlik ayracı konmaz.
Başka bir programa aktarmak için CSV'yi, Excel için .xlsx'i kullanın.
Excel'de açık olan bir .xlsx'in üstüne yazılamazsa yenisi `..._yeni.xlsx`
adıyla yanına yazılır.

### `BOM.csv` / `BOM.md`

Her poz için: kod, tanım, adet, sınıf, **tip** (standartta `perçin somun`,
`somun`...; profilde `kutu profil 30x50x2`; profil biçimli sacta
`bükümlü sac, U kesit 40x15x1,5`), malzeme, ölçü (BOY × EN × KALINLIK), adet başına
kütle, toplam kütle, çizim dosyası. Civata, somun, pul gibi **standart
elemanlar BOM'a kod + adet olarak girer**, çizimleri üretilmez. Kaynak
dikişleri BOM'a girmez, türüne göre ayrıca sayılır. Detay ve montaj
resimleri `DXF/`, açınımlar `ACINIM/`, lazer resimleri `LZR/`, PDF'ler
`PDF/` klasöründedir.

### `P01_<kod>.dxf` — detay resmi

Başlık bloğunda yalnız parça kimliği ve genel ölçüler vardır:

```
POZ 5   01.050.000.01   01.050.000.01 U-Blech-Mechanismus
adet: 1
GABARİ (boy x en x yükseklik): 483,04 x 76,5 x 32 mm   sac kalınlığı 3 mm
kütle 1,285 kg   malzeme: Celik
ölçek 1:1   birim: mm
```

Üç kutu ölçüsü yalnız **düz sacta** `BOY x EN x KALINLIK` diye yazılır.
Öbür parçalarda satır **GABARİ**dir: C profilde en küçük kutu ölçüsü
40 mm'dir, sac 1,5 mm — ona "kalınlık" demek yanlış olurdu. Bükümlü
sacta sac kalınlığı büküm taramasından ölçülür ve ayrıca yazılır
(`olculer.csv`: `yukseklik_mm` gabari, `sac_kalinlik_mm` sac).

**Bükümlü sacın kesit görünüşü** (büküm eksenine bakan, ör. C profilde
SAĞ/SOL): sac kalınlığından ve büküm radüsünden doğan seviyeler (iç
yüz, radüs teğeti: 38 / 39,5 / 4 / 63 gibi) ölçülmez. Kesitte yalnız
gabari ve **kanat genişliği** (dış yüzden sacın serbest ucuna, ör. 15)
verilir; iki kanat eşitse simetri işaretiyle tek ölçü. Sac kalınlığı
başlıkta yazar.

**Ölçülendirme kuralları** (ayrıntı ve gerekçe: `CLAUDE.md`):

- **Parça montaj yönünde çizilir, döndürülmez:** modelde nasıl duruyorsa
  ÖN / SAĞ / ÜST öyledir.
- **Dış ölçüler önce ve kesinlikle:** ana görünüş (en çok bilgi veren
  görünüş) iki boyutunu en dışta taşır; derinlik yan görünüşte (sac
  profili kesitte) verilir.
- **Karışık bölge detaya taşınır:** ana görünüşte yalnız hiçbir şeyi
  kesmeyen ölçüler kalır; kalabalık uç ya da köşe bir çerçeveyle
  işaretlenir ve büyütülmüş `DETAY D (2,5:1)` görünüşünde tam
  ölçülendirilir. Detaylar görünüşlerin altına sırayla dizilir.
- **Referans:** her yönde tek referans (düz yüz ya da eksen). Konumlar
  referanstan zincirle (0 → A → B) ya da paralel verilir.
- **Ölçü çizgisi delik / slot üstünden geçmez:** geçecekse ölçü öbür
  yana, o da kapalıysa deliğin yanına, en yakın ölçülü komşusundan
  konur.
- **Sığmayan ölçü atılmaz:** öbür yan, deliğin yanı, referanstan paralel
  ölçü, slot notu (`3x SLOT 80x180`), en son büyütülmüş **DETAY**
  görünüşü (`DETAY D (4:1)`).
- **Aynı eleman bir kez:** `9x SLOT 6`, `3x 70`, `10 x 20 = 200`,
  `4x 30°`.
- **Ölçülendirme el kitaplarının özeti "anayasa"dır** (ayrıntı, gerekçe
  ve kaynak: `OLCULENDIRME_KURALLARI.md`): yazı 3,5 mm (en az 2,5), ok
  3 mm / 30°, uzatma boşluğu 1,5 mm, taşma 2 mm, ilk ölçü hattı parçadan
  10 mm, hatlar arası 8 mm, kılavuz çizgisi 30 / 45 / 60°. Hepsi yazı
  boyunun katı olarak uygulanır; DXF'teki ölçü stili bu değerlerdendir.
- **PDF okumak içindir**, üstünden ölçü alınmaz; ölçü 1:1 DXF'ten
  alınır. PDF'te ölçek serbesttir (1:9, 1:11, 1:13 …): çizim kâğıdı
  doldurur, antet boş kalır.
- **Ana resim büyük kalır, PDF çok sayfalı olabilir:** detay görünüşleri
  1. sayfada ana resmi küçültüyorsa aynı PDF'in 2. sayfasına
  ("DETAYLAR") gider; tek sayfada yazı 1,2 mm'nin altında kalıyorsa ve
  ana görünüş tek başına en az 1,3 kat büyüyorsa yan görünüşler de 2.
  sayfaya alınır. Bilgi bloğu (parça adı, malzeme) hep 1. sayfadadır.
  2. sayfanın başlığında kendi ölçeği yazar; detay büyütmeleri (`2:1`)
  ayrıca detay adında. DXF'te sayfalar `PAFTA`, `PAFTA_2` … sekmeleridir.

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
