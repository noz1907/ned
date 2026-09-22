# CATIA malzemesini kaybetmeden PiFikstür'e aktarmak

**Sorun:** CATIA'da malzeme tanımlı, ama `.CATProduct` → STEP çevirisinde
malzeme bilgisi kayboluyor.

**Sebebi:** STEP'in kendisinde malzeme için standart bir alan yok sayılır.
AP214/AP242'de malzeme taşıyan varlıklar (`material_designation`) tanımlıdır
ama CATIA'nın STEP yazıcısı bunları varsayılan ayarlarla doldurmaz. Yani
kayıp çeviricinin değil, dışa aktarım seçeneklerinin sonucudur.

**Çözüm:** Geometriyi STEP'ten, malzemeyi ayrı bir listeden alın. PiFikstür
ikisini kod üzerinden birleştirir. Malzemeyi çıkarmanın iki yolu var.

---

## Yol 1 — CATIA'nın kendi parça listesi *(önerilen, kod yazmadan)*

CATIA V5, montaj ağacındaki her parçanın özelliklerini tablo olarak dışa
aktarabilir; **Material** bunlardan biridir.

1. `.CATProduct` açıkken menüden **Analyze ▸ Bill of Material**
2. Açılan pencerede **Define formats** düğmesi
3. *Hidden Properties* listesinden **Material**'i seçip **>** ile
   *Displayed Properties* tarafına atın.
   *Part Number* zaten görünür listede olmalı; değilse onu da ekleyin.
4. **OK** → **Save As…** → tür olarak **Text (\*.txt)** ya da
   **Excel (\*.xls)** seçip kaydedin

Elinizde şuna benzer, sekmeyle ayrılmış bir dosya olur:

```
Part Number	Nomenclature	Material	Quantity
01.050.000.01	U-Blech-Mechanismus	Steel	1
09.020.000.03	Rollenplatte	Aluminium	1
06.001.001.34	Keil-forging	Stainless Steel	1
```

5. PiFikstür'de **2. adım**ta → **malzeme.csv yükle…** → bu dosyayı seçin

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

## Sonra ne oluyor

PiFikstür malzemeyi şu sırayla belirler:

1. **Yüklediğiniz liste** (CATIA BOM ya da kendi `malzeme.csv`'niz) → `seçim`
2. **Data'da yazan** (STEP malzeme alanı ya da parça adında geçen `1.4301`,
   `S235`, `AlMg3`, `POM` gibi ifadeler) → `data'dan`
3. Hiçbiri yoksa çelik → `varsayılan`

Hangi parçanın malzemesinin nereden geldiği tabloda **KAYNAK** sütununda ve
BOM dosyasında yazar. Kütle bu malzemenin yoğunluğuyla hesaplanır, detay
resminin başlığına da yazılır.

---

## Neden CATProduct doğrudan okunamıyor

PiFikstür'ün geometri çekirdeği **OpenCascade**'dir. `.CATPart` /
`.CATProduct`, Dassault Systèmes'in kapalı biçimidir; açık kaynak bir çekirdek
onu okuyamaz. Okuyabilmek için ticari çevirici lisansı gerekir
(CAD Exchanger, Datakit CrossManager, ODA). Bu bir eksiklik değil, lisans
meselesidir — ve yukarıdaki iki yol, lisans almadan aynı sonucu verir:
geometri STEP'ten, malzeme listeden.
