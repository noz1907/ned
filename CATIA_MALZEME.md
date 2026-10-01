# CATIA malzemesini kaybetmeden Pi3D'e aktarmak

**Sorun:** CATIA'da malzeme tanımlı, ama `.CATProduct` → STEP çevirisinde
malzeme bilgisi kayboluyor.

**Sebebi:** STEP'in kendisinde malzeme için standart bir alan yok sayılır.
AP214/AP242'de malzeme taşıyan varlıklar (`material_designation`) tanımlıdır
ama CATIA'nın STEP yazıcısı bunları varsayılan ayarlarla doldurmaz. Yani
kayıp çeviricinin değil, dışa aktarım seçeneklerinin sonucudur.

**Çözüm:** Geometriyi STEP'ten, malzemeyi ayrı bir listeden alın. Pi3D
ikisini kod üzerinden birleştirir. Malzemeyi çıkarmanın iki yolu var.

---

## Yol 1 — CATIA'nın kendi parça listesi *(önerilen, kod yazmadan)*

CATIA V5, montaj ağacındaki her parçanın özelliklerini tablo olarak dışa
aktarabilir; **Material** bunlardan biridir.

1. `.CATProduct` açıkken menüden **Analyze ▸ Bill of Material**
2. Açılan pencerede **Define formats** düğmesi
3. *Hidden Properties* listesinden **Material**'i seçip **>** ile
   *Displayed Properties* tarafına atın. **Source**'u da ekleyin (aşağıya bakın).
   *Part Number* zaten görünür listede olmalı; değilse onu da ekleyin.
4. **OK** → **Save As…** → tür olarak **Excel (\*.xls)** ya da
   **Text (\*.txt)** seçip kaydedin. **CSV'ye çevirmeniz gerekmez:**
   Pi3D CATIA'nın Excel kaydını doğrudan okur: gerçek eski Excel
   (`.xls`, Excel 97-2003), `.xlsx`, sekmeli metin ya da HTML tablo -
   hepsi, ek program kurmadan.

   **Material sütunu listede yoksa** (yalnız Number, Part Number,
   Definition, Quantity) dosyadan malzeme çıkmaz; Pi3D bunu söyler.
   3. adıma dönüp Material'i görünür listeye alın.

Elinizde şuna benzer, sekmeyle ayrılmış bir dosya olur:

```
Part Number	Nomenclature	Material	Quantity
01.050.000.01	U-Blech-Mechanismus	Steel	1
09.020.000.03	Rollenplatte	Aluminium	1
06.001.001.34	Keil-forging	Stainless Steel	1
```

5. Pi3D'de **Yardım ▸ Malzemeyi CAD'den al** → 4. adımda bu dosyayı seçin
   (önizleme: hangi parça hangi malzemeyi alacak), ya da 2. adımda →
   **Malzeme listesi yükle (Excel / CSV)…**

### Source (Made / Bought): hangi parça satın alınıyor?

CATIA'da her ürünün **Özellikler ▸ Ürün ▸ Source** alanı vardır: *Made*
(üretilen) ya da *Bought* (satın alınan). Tasarımcı bunu dolduruyorsa Pi3D
parçanın standart mı üretim mi olduğunu **tahmin etmez, CAD'den okur**:

- Bill of Material'e **Source** sütununu ekleyin (yukarıdaki 3. adım), ya da
  makroyu kullanın (4. sütun `kaynak` olarak yazılır).
- `Bought` → satın alınan (standart): BOM'da adediyle, resmi çizilmez.
- `Made` → üretim parçası: resmi, açınımı çıkar.
- Bir **alt montaj** Bought ise altındaki bütün parçalar satın alınan sayılır
  (hazır alınan grup).

Adından ya da biçiminden tanınamayan parça (perçin somun, tedarikçi parçası,
parça numarasıyla adlandırılmış eleman) için en kesin ve en hızlı yol budur:
CATIA'da bir kez doldurulan alan her modelde geçerlidir.

Program başlık satırındaki `Part Number` ve `Material` sütunlarını adlarından
bulur; ayırıcının sekme mi, noktalı virgül mü, virgül mü olduğunu kendi
anlar. Malzeme adları **İngilizce ya da Fransızca olabilir** — `Steel`,
`Aluminium`, `Stainless Steel`, `Brass`, `Copper`, `Titanium`, `Rubber`,
`Glass`, `Wood`, `Plastic`, `Iron` tanınır. Tanınmayan bir ad çıkarsa program
susmaz, hangi adları eşleyemediğini söyler; dosyada düzeltip yeniden
yükleyebilirsiniz.

> Sütun başlıkları Türkçe (`Kod`, `Malzeme`) ya da Fransızca (`Référence`,
> `Matière`) olsa da bulunur.

---

## Yol 2 — Makro ile *(toplu iş için)*

Çok sayıda montaj varsa `catia_malzeme_cikar.CATScript` dosyasını kullanın:
açık olan `.CATProduct`'ın ağacını gezip `malzeme.csv` yazar.

**Çalıştırmak:** CATIA'da `.CATProduct`'ı açın →
**Tools ▸ Macro ▸ Macros…** → *Select an external file* ile bu dosyayı seçip
**Run**.

> Bu makroyu ben test edemedim (burada CATIA yok). Ortamınızda hata verirse
> Yol 1'i kullanın — o menü üzerinden, kodsuz ve kesin çalışır. Makronun
> hatası genelde `CATMatManagerVBExt` arayüzünün sürümünüzde farklı
> adlanmasından gelir; makro üç ayrı yolu sırayla dener ve hangisinin
> tutmadığını yazar.

---

## Bölümlü BOM kaydı (alt montajlı ürün) ve BOM eşleştirme

Alt montajlı bir üründe CATIA'nın kaydı tek tablo değildir: her alt
montaj için ayrı **"Bill of Material: <montaj>"** bölümü, her bölümün
kendi başlık satırı ve sonda **"Recapitulation of"** özeti (parça başına
toplam adet) olur. Pi3D bunu bölüm bölüm okur: malzemeyi yalnız
**Material** sütunundan (standart elemanda TraceParts `materialgruppe`)
alır, başlık satırlarını asla kod sanmaz. Aynı dosyayla **BOM
eşleştirme** de yapar: STEP'ten çıkan parçalarla CATIA parça no /
Nomenclature / dosya adı üzerinden eşleşir, adet farklarını, STEP'e
alınmamış elemanları (cıvata, somun, perçin) ve CATIA listesinde olmayan
parçaları `BOM_ESLESTIRME.xlsx`'e yazar (Adım 2 → **CATIA BOM ile
eşleştir…** ya da `--catia-bom`). Ayrıntı: KULLANIM.md, Adım 2.

## Sonra ne oluyor

Pi3D malzemeyi şu sırayla belirler:

1. **Yüklediğiniz liste** (CATIA BOM ya da kendi `malzeme.csv`'niz) → `seçim`
2. **Data'da yazan** (STEP malzeme alanı ya da parça adında geçen `1.4301`,
   `S235`, `AlMg3`, `POM` gibi ifadeler) → `data'dan`
3. Hiçbiri yoksa çelik → `varsayılan`

Hangi parçanın malzemesinin nereden geldiği tabloda **KAYNAK** sütununda ve
BOM dosyasında yazar. Kütle bu malzemenin yoğunluğuyla hesaplanır, detay
resminin başlığına da yazılır.

---

## Neden CATProduct doğrudan okunamıyor

Pi3D'ün geometri çekirdeği **OpenCascade**'dir. `.CATPart` /
`.CATProduct`, Dassault Systèmes'in kapalı biçimidir; açık kaynak bir çekirdek
onu okuyamaz. Okuyabilmek için ticari çevirici lisansı gerekir
(CAD Exchanger, Datakit CrossManager, ODA). Bu bir eksiklik değil, lisans
meselesidir — ve yukarıdaki iki yol, lisans almadan aynı sonucu verir:
geometri STEP'ten, malzeme listeden.
