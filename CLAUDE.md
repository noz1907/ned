# Pi3D - çalışma kuralları

Pi3D: STEP modelinden BOM, detay resmi (DXF + PDF pafta), açınım, lazer,
kaynak resmi üreten program. Ana dosyalar: `pf3_olcu.py` (ölçü, detay
resmi), `pf4_pafta.py` (pafta / PDF), `pf14_kaynak.py` (kaynak resmi),
`pf3_gui.py` (arayüz), `pf7_is.py` (iş kaydı, `PI3D_SURUM`).

## Genel

- Kod yorumları, belgeler, arayüz metinleri ve commit mesajları TÜRKÇE.
- YANLIŞ SONUÇ ASLA: emin olunmayan ölçü yazılmaz, raporda sayılır.
- ÖLÇ, TAHMİN ETME: yazının yeri, çakışma, ölçek hesapla değil ölçülerek
  bulunur; her değişiklik gerçek modellerde (kasa, Karluna, Televre,
  tente) denetlenir.
- Kullanıcı sorun listesi toplarken "tamam" demeden kod değiştirilmez.
- Firma CAD / Excel dosyaları depoya GİRMEZ. Kitap / web sayfaları
  kopyalanmaz, kurallar kendi cümlelerimizle özetlenir.
- Yapay zekâ verisi Anthropic'e yalnız firma izniyle gider (program sorar).
- Her teslimde `PI3D_SURUM` (pf7_is.py) artar, `SURUM.txt` ve
  `KULLANIM.md` güncellenir.
- Testler: `test/` (bkz. `test/OKU.md`). Çakışma denetimi:
  `python test/cizim_cakisma_denetimi.py <dxf klasörü>` - sonuç 0 olmalı.

## Ölçülendirme - programın uzmanlığı

Ayrıntı, gerekçe ve kaynak: `OLCULENDIRME_KURALLARI.md`. Kararlar ezbere
değil, belirli bir mantığa göre verilir; her kuralın gerekçesi yazılıdır.

1. **DXF 1:1 çalışma dosyasıdır**, ölçü ondan alınır, başka ölçekte
   çalışılmaz. **PDF insanın okuması içindir**, üstünden ölçü alınmaz;
   DXF'in birebir kopyası olmak zorunda değildir. PDF'te çizim kâğıdın
   yaklaşık %70'ini doldurur (ara ölçek serbest: 1:14, 1:17 ...), yazılar
   okunur olmalı ("karınca duası" olmaz).
2. **Referans (datum)**: her yönde TEK referans; sağ / sol, üst / alt için
   ayrı referans olmaz. Datum düz yüzey ya da eksen olur, radüs teğeti
   asla. Referans seçimi gerekçelidir (en büyük düz yüz, eksen, simetri).
3. **Konum ölçüsü**: referanstan başlar; sonra zincir (0 -> A -> B) ya da
   paralel (0 -> A, 0 -> B), önem ve yapıya göre. Tek hatta rakam dizmek
   (cetvel / rollform ayar ölçüsü gibi) KULLANILMAZ.
4. **Dağılım**: ölçü gösterdiği özelliğe yakın yana konur, dört yana
   dengeli dağılır; uzatma çizgisi özelliğin kendisinden başlar.
5. **Delik grupları** (kare / daire içinde yakın delikler): ilk delik
   referanstan, öbürleri delikten deliğe art arda.
6. **Aynı eleman bir kez**: "9x SLOT 6", "3 x 200 = 600", "6x Ø45".
   Simetrik eşe ikinci ölçü konmaz; simetri ekseni çizilir.
7. **DIŞ ÖLÇÜLER KESİNLİKLE YER ALIR**, önce onlar: ANA görünüş (ÖN)
   kendi boyunu ve yüksekliğini her zaman en dışta taşır; konum ölçüleri
   onun içine girer. Öbür görünüşler yalnız ÖN'ün gösteremediğini
   (derinlik) verir - en net göründüğü yerde (sac profili kesitte; ince
   şeritte değil). Gabarinin uzatma çizgisi yolu önceden ayrılır; konamayan
   gabari raporda `gabari_yok` sayılır ve 0 olmalıdır.
8. **Bükümlü sac**: her kanat dıştan dışa (sanal keskin köşe, ABKANT
   tablosuyla aynı); kalınlık kesitte "t 1,5" (noktayla biten kılavuz).
   Neredeyse eşit ayna kanatlar (<1 mm fark) "MODEL KONTROL" uyarısıdır.
9. **Açılar**: eğik kenar / kanat açısı verilir; hepsi aynıysa bir kez
   "n x açı".
10. **Slot / yuvarlak kesik**: konum yay MERKEZİNDEN (kutu kenarından
    değil), slot boyu merkezler arası + R.
11. **Izgara** (sık kesim): iç ölçüsü verilmez (lazer DXF'i verir); bölge
    kesik çizgiyle işaretlenir, başı ve sonu referanstan ölçülür.
12. **Çakışma YOK**: yazı yazıya, yazı herhangi bir çizgiye (ölçü,
    uzatma, kılavuz, eksen dahil), çizgi çizginin üstüne binmez.
    Çizgiler ince, ölçü çizgisi kalın asla.
    **Ölçü / uzatma çizgisi delik, slot, pencere üstünden geçmez**:
    özellikten dışarı giden yol başka bir özelliği kesiyorsa ölçü temiz
    olan öbür yana alınır; iki yan da kapalıysa ölçü dışarıdan değil,
    özelliğin YANINDAN, en yakın ölçülü komşusundan verilir.
13. **Rakam kendi ölçüsünün hizasında**: aralık rakamı alıyorsa rakamın
    ortası aralığın içindedir (komşu aralığın yanına kayan rakam onun
    ölçüsü gibi okunur). Düşey zincirde bütün rakamlar hattın aynı
    yanında, aynı eksende. Dar zincir halkasında ok yerine NOKTA, dışarı
    kuyruk çıkmaz; zincir yine tek hizada kalır.
14. **Sığmayan ölçü atılmaz**, sırayla: öbür yan -> özelliğin yanı ->
    özel şekilde not ("3x SLOT 80x180": genişlik x boy) -> DETAY görünüşü
    (ana görünüşte daire + harf, "DETAY D (4:1)", boş hücrede). Raporda
    `yer_yok` 0 olmalı.
15. **Aynı görünen ayna görünüşler** (SAĞ = SOL, ÜST = ALT) tek çizilir.
16. **Sacta delik / kesik** pres ya da lazerle yapılır: konumu verilir;
    çap, boy, genişlik yalnız özel ise. Özel şekillerde (pencere, anahtar
    deliği) yalnız konum, ana eksene göre. Çok abartmadan ölçü.
    Delikten deliğe zincir yalnız DÜZENLİ desende (iki delik ya da tam
    dikdörtgen); düzensiz öbekte her delik referanstan. Aynı desenli
    grupların iç ölçüsü bir kez: "3x 70".
    Sacın iki yüzü (paralel, kalınlık kadar aralı çizgiler) TEK duvardır:
    açı ve ölçü bir kez sayılır (4 eğik duvar "4x 30°", 8x değil).
17. **Görünüş seçimi**: önce en doğru (en çok bilgi veren) görünüş ön
    görünüş olur; sonra gerekirse sağ / sol, sonra gerekirse üst / alt.
    Bilgi eklemeyen görünüş çizilmez; çoğu zaman 3 görünüş yeter.
18. Perspektif üzerine ölçü verilmez.

## PDF (pafta)

- PDF okumak ve atölyede iş yapmak içindir; DXF'le aynı şey değildir.
  Üstünden ölçü alınmaz (kumpas vb. yok), yalnız rakamlar okunur.
- Çizim kâğıdın yaklaşık %70-75'ini doldurur; ölçek serbest ve ara
  değerde olabilir (1:12, 1:14, 1:17 ...). Standart 1-2-5 serisine
  zorlanmaz.
- Antet alanı (A3'te sağ alt 150 x 100 mm) BOŞ kalır; dolu pencereler
  (görünüşler, başlık) antete değmez, boş hücre antetin üstüne düşebilir.
- Görünüşler birbirine yakın durur (arası en çok 15 mm), dağılmaz.
- Yazılar okunur olmalı; "karınca duası" resim kabul edilmez.
