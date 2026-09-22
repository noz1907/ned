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

### En kolayı: `PiFikstur_baslat.bat` (Windows)

Klasördeki **`PiFikstur_baslat.bat`** dosyasına çift tıklayın. İlk
çalıştırmada bu klasörde `.venv` adında **ayrı bir Python ortamı** kurar,
paketleri oraya yükler ve programı açar. Sonraki çalıştırmalarda doğrudan
açar. Komut yazmanıza gerek yok.

### Elle kurmak isterseniz

> ⚠ **Paketleri ana Python'unuza kurmayın.** `cadquery`, `numpy 2`
> istiyor; `tensorflow`, `pandas 2.1`, `scikit-learn 1.3` gibi paketler ise
> `numpy 1` istiyor. İkisi aynı ortamda bir arada duramaz. Bu yüzden
> PiFikstur'u **kendi sanal ortamında** çalıştırın — hem bu program çalışır,
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

Yetmezse PiFikstur klasörünü boş alanı olan başka bir sürücüye taşıyıp
`PiFikstur_baslat.bat`'ı oradan çalıştırın; `.venv` o sürücüde kurulur.

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

Çözüm: **`.venv` klasörünü silin**, `PiFikstur_baslat.bat`'ı çalıştırın.
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

Sonra PiFikstur'u yukarıdaki gibi kendi `.venv` ortamında çalıştırın; iki
kurulum birbirine karışmaz.

### Çalıştırılabilir dosya (.exe) yapmak

Python kurulu olmayan bilgisayarlarda da çalışsın istiyorsanız:

```
EXE_YAP.bat
```

Önce `PiFikstur_baslat.bat` ile `.venv` kurulmuş olmalı. Bu dosya
PyInstaller'ı kurar ve `pifikstur.spec` tarifine göre derler.

Çıktı: **`dist\PiFikstur\PiFikstur.exe`**

> **Klasörün tamamını kopyalayın, tek başına `.exe` çalışmaz.** OpenCascade
> kütüphanesi yanındaki DLL'lerle birlikte gelir; klasör ~1 GB olur.
>
> Tek dosyalık (`--onefile`) sürüm **önerilmez**: 1 GB'lık içerik her
> açılışta geçici klasöre açılır, program 1-2 dakikada açılır ve disk iki
> kat yer kaplar. `onedir` sürümü anında açılır.

Derleme yalnız **çalıştırıldığı işletim sistemi için** üretir: Windows'ta
derlerseniz Windows `.exe`'si çıkar, Linux'ta derlerseniz Linux çalıştırılabiliri.

---

## 2. Arayüzle kullanım (kolay yol)

`PiFikstur_baslat.bat`'a çift tıklayın, ya da sanal ortamı etkinleştirip:

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
4. PiFikstür 2. adımda → **malzeme.csv yükle…** → o dosyayı seçin

Program `Part Number` ve `Material` sütunlarını başlıklarından bulur,
ayırıcıyı (sekme / `;` / `,`) kendi anlar, `Steel` · `Aluminium` ·
`Stainless Steel` gibi İngilizce adları tanır. Tanıyamadığı bir ad olursa
hangisi olduğunu söyler. Geometri STEP'ten, malzeme bu listeden gelir.

Toplu iş için `catia_malzeme_cikar.CATScript` makrosu da pakette.

Program tanımadığı bir dosya seçtiğinizde susmaz: biçimin ne olduğunu ve
hangi CAD menüsünden STEP alınacağını söyler.

---

## 2c. Ölçek ve birim — "30 yazıyor ama AutoCAD 3000 ölçüyor"

Çizim **1:1**'dir ve **1 çizim birimi = 1 mm**'dir. Her detay resminin
başlığında `olcek 1:1   birim: mm` satırı bunu söyler.

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
```

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
`TARAMA` — hepsi 0,10 mm çizgi kalınlığında.

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
| `pf3_gui.py` | **ana arayüz** — yukarıdaki 5 adımlı pencere |
| `pf1_referans.py` | STEP'ten XYZ referans yönü ve 3 konumlandırma noktası önerir |
| `pf_gui.py` | `pf1_referans` için 3B önizlemeli arayüz |
| `pf2_fikstur.py` | kaynak/montaj fikstürü üretici (3-2-1 prensibi) |
| `pfd_dxf2stp.py` | DXF görünüşlerinden 3B STEP üretir (renk = parça kimliği) |
| `PiFikstur_baslat.bat` | Windows'ta tek tıkla kurulum + başlatma |
| `PiFikstur_baslat_KUCUK.bat` | dar disk için küçük kurulum (~800 MB) |
| `EXE_YAP.bat` + `pifikstur.spec` | çalıştırılabilir dosya (.exe) üretir |
| `CATIA_MALZEME.md` | CATIA malzemesini kaybetmeden aktarma |
| `catia_malzeme_cikar.CATScript` | CATIA makrosu: ağacı gezip `malzeme.csv` yazar |

Ayrıntılar için `README.md`.

---

## 7. Henüz yapılmayan, not alınmış işler

1. **Otomatik kesit kararı** — şu an kesit isteğe bağlı (E/H). İki delik ya
   da iki form görünüşte üst üste binip anlamsızlaştığında programın bunu
   kendi fark edip o görünüş yerine kesit koyması.
