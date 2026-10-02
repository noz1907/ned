# Pi3D - çalışma kuralları

Pi3D: STEP modelinden BOM, detay resmi (DXF + PDF pafta), açınım, lazer,
kaynak resmi üreten program. Ana dosyalar: `pf3_olcu.py` (ölçü, detay
resmi), `pf4_pafta.py` (pafta / PDF), `pf14_kaynak.py` (kaynak resmi),
`pf3_gui.py` (arayüz), `pf7_is.py` (iş kaydı, `PI3D_SURUM`). Açınım:
`pf3_olcu.sac_acilim` önce 2B, açamazsa `pf16_acinim3.py` (3B genel
açınım: her duvar kendi bükümü etrafında döndürülür; dil, yarıklı kanat,
çevrim denetimi). Her açınım değişikliği 4 modelde `sac_acilim` ile
koşulur: eksenleri paralel olmayan parçada HATA 0, çakışma 0.

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
- Müşteriye giden paket: `py exebuild.py` → `Pi3D_Kurulum_v<sürüm>.exe`
  (Inno Setup). Pakette `.py` / `.pyc` / `.spec`, özel anahtar,
  `lisans_masasi/` OLMAZ (bariyer). Lisans makine bazlı (`pf17_lisans`,
  PiProduct düzeni): deneme 8 model, sonra TAM. Özel anahtar depoya
  girmez (`lisans_masasi/keys/` .gitignore'da).
- Testler: `test/` (bkz. `test/OKU.md`). Çakışma denetimi:
  `python test/cizim_cakisma_denetimi.py <dxf klasörü>` - sonuç 0 olmalı.

## Ölçülendirme - programın uzmanlığı

Ayrıntı, gerekçe ve kaynak: `OLCULENDIRME_KURALLARI.md`. Kararlar ezbere
değil, belirli bir mantığa göre verilir; her kuralın gerekçesi yazılıdır.

### ANAYASA (kitaplar)

Kullanıcı: "bu kitaplar bizim anayasamız, her ölçü bunlara göre
şekillenecek." Üç kaynak: **Chevalier** (Guide du dessinateur industriel),
**"La cotation"** (NF P 02-001 ders notu), **"Règles de cotation"** ders
notu. Kitap metni kopyalanmaz; kurallar kendi cümlelerimizle özetlenir
(özetler: scratchpad `kaynak_pdf/*.md`; kalıcı: `OLCULENDIRME_KURALLARI.md`).
Çelişkide öncelik: kullanıcının kuralı > kitap > ISO. Sayısal standart
koddaki tek sözlükte durur (`pf3_olcu.ANAYASA`; kâğıt mm, A3, yazı 3,5 mm;
DXF'te yazı boyunun katı olarak uygulanır):

| öğe | değer | kaynak |
|---|---|---|
| rakam yüksekliği | 3,5 mm (asla < 2,5) | CH s.3; La cotation s.3 |
| ok | dolu, 3 mm, 30°; bir resimde tek tip; dar halkada nokta | La cotation s.4; CH s.3 |
| uzatma çizgisi | konturdan 2 mm açık başlar, ölçü çizgisini 1,5 mm aşar | La cotation s.3; CH s.2 |
| ilk ölçü çizgisi | görünüşe 10 mm | La cotation s.3 |
| paralel ölçü çizgileri arası | 8 mm | La cotation s.3 (7-10) |
| rakam yeri | yatayda çizginin üstünde ortada; düşeyde yatay okunur (ISO yöntem 2) | La cotation s.3; ISO 129-1 |
| kısa ölçü içte, uzun dışta; ölçü çizgileri kesişmez; ölçü çizgisi kontur / eksenle aynı doğrultuda olmaz | | CH s.9 |
| bir ölçü bir kez, en net görünüşte; artık (toplam = zincir) ölçü yok | | CH s.39-40 |
| Ø kılavuzu radyal, R tek oklu; "n x Ø"; sanal keskin köşe | | CH s.5, s.7, s.2 |
| detay: ince daire / çerçeve + harf, "DETAY D (2,5:1)", rakam gerçek değer | | CH s.20, s.41 |
| kesit: kesit çizgisi + oklar + harf, "A-A", tarama rakamın çevresinde kesik | | CH s.9, s.49 |
| perspektif üstüne ölçü yok; birim mm yazılmaz; ondalık virgül | | K; CH s.3 |

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
7. **DIŞ ÖLÇÜLER KESİNLİKLE YER ALIR**, önce onlar: ANA görünüş (en
   çok bilgi veren görünüş; parça döndürülmez, o görünüş hangisiyse)
   kendi iki boyutunu her zaman en dışta taşır; konum ölçüleri onun
   içine girer. Öbür görünüşler yalnız ana görünüşün gösteremediğini
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
    olan öbür yana alınır; iki yan da kapalıysa o bölge DETAYA taşınır
    (bkz. 14).
13. **Rakam kendi ölçüsünün hizasında**: aralık rakamı alıyorsa rakamın
    ortası aralığın içindedir (komşu aralığın yanına kayan rakam onun
    ölçüsü gibi okunur). Düşey zincirde bütün rakamlar hattın aynı
    yanında, aynı eksende. Dar zincir halkasında ok yerine NOKTA, dışarı
    kuyruk çıkmaz; zincir yine tek hizada kalır.
14. **KARIŞIKLIK DETAYA TAŞINIR** (uzman ressam gibi): ana görünüşte
    yalnız temiz, hiçbir şeyi kesmeyen ölçüler kalır. Ölçü çizgisi iki
    yanda da şekil kesiyorsa, zincir halkası rakamın yarısından kısaysa
    ya da ölçüye dışarıda yer yoksa o bölge AYRILIR:
    - Bölge = karışık özelliklerin dikdörtgeni; her yönde parça kenarına
      yakınsa kenara uzar (ince uzun parçada boydan boya bant: sol uç /
      sağ uç; levhada köşe); kesişenler birleşir; detaya sığmayacak
      kadar büyük bölge bölünür; en çok 6 bölge.
    - Bölgedeki bütün konumlar ana görünüşten çıkar, DETAY görünüşünde
      (büyütülmüş, "DETAY D (2,5:1)", ana görünüşte ince çerçeve + harf)
      zincirle verilir: referans bölge datum kenarını içeriyorsa kenar;
      içermiyorsa ana görünüşte ölçülü BAĞLANTI özelliği (bölgenin datuma
      en yakın, temiz yerleşen özelliği ana görünüşte kalır) - tek
      referans bozulmaz.
    - DETAY KÜÇÜK KALIR: büyütülmüş bölge görünüşün en uzun kenarının
      %30'unu aşmaz, büyütme en kısa ölçü okunacak kadardır (2, 2,5, 4,
      5, 10); detaylar ana görünüşün ölçeğini düşürmemeli.
    - İki geçiş: önce deneme (temiz yerleşmeyenler bulunur, deneme
      silinir), sonra bölgesiz ana görünüş + detaylar.
    - Pafta: detaylar izdüşüm ızgarasına girmez; görünüş öbeğinin ALTINA
      okuma sırasıyla dizilir (altta yer yoksa kâğıdın başka boş yeri).
    Sığmayan ölçü yine de ATILMAZ: detay kurulamazsa özelliğin yanına,
    o da olmazsa slot notu ("3x SLOT 80x180"). Raporda `yer_yok` 0 olmalı.
    Küçük parçada detay dairesi en az 12 yazı boyu olabilir; detayda yer
    bulamayan ölçü için önce konmuş ölçülerle yer TAKASI denenir.
    Aynı hizada iki bölgeye düşen özelliklerin ölçüsü bölünür.
15. **Aynı görünen ayna görünüşler** (SAĞ = SOL, ÜST = ALT) tek çizilir.
16. **Gereksiz ölçü yok, önemli konum eksiksiz**: her delik / slot /
    kesik / kanat / açı için konum ve gereken özel ölçü (Ø, boy, açı)
    kesinlikle vardır; artık ölçü (toplamı zaten belli), tekrar, iç yüz
    / radüs teğeti gibi işe yaramayan ölçü yoktur.
    **Sacta delik / kesik** pres ya da lazerle yapılır: konumu verilir;
    çap, boy, genişlik yalnız özel ise. Özel şekillerde (pencere, anahtar
    deliği) yalnız konum, ana eksene göre. Çok abartmadan ölçü.
    Delikten deliğe zincir yalnız DÜZENLİ desende (iki delik ya da tam
    dikdörtgen); düzensiz öbekte her delik referanstan. Aynı desenli
    grupların iç ölçüsü bir kez: "3x 70".
    Sacın iki yüzü (paralel, kalınlık kadar aralı çizgiler) TEK duvardır:
    açı ve ölçü bir kez sayılır (4 eğik duvar "4x 30°", 8x değil).
    **Tek duvar deliği** (içi boş kutu / ekstrüzyon: delik yalnız bir
    duvarda) duvarının GÖRÜNDÜĞÜ görünüşte düz çizgiyle çizilir ve
    ölçülenir; gereken görünüş yoksa EKLENİR (`delik_duvarlari`,
    `delik_gorunusu`, `gerekli_delik_gorunusleri`). Simetri yalnız TAM
    simetride (0,05 mm; L'ye bağlı pay yok).
    Birbirine 0,5 mm içinde kalan datum seviyeleri (104,2 / 104,3 / 104,5)
    tek sıradır: ortalamaya en yakın gerçek değer yazılır, başlıkta
    "! MODEL KONTROL" uyarısı çıkar (ölçü uydurulmaz, model denetlenir).
17. **Parça KULLANIM (ARAÇ) YÖNÜNDE çizilir, döndürülmez, yatırılmaz**:
    araçta nasıl duruyorsa öyle, üstü üstte, önü önde (kullanıcı: "parça
    kesinlikle kullanım yönünde olmalı; araç yönü bizim için önemli; ön
    panel baş aşağı"). Araç yönü ayarı (`P["arac"]`: önü -X/+X/-Y/+Y,
    üstü +Z; öneri parça adlarından ÖN/ARKA, SAĞ/SOL) model eksenlerini
    çizim çerçevesine çevirir (`arac_cercevesi`, `cizim_cercevesi`);
    `hizali_kati` (en büyük yüzü yatıran eski hizalama) çizimde
    KULLANILMAZ, yalnız BOM gabarisi içindir. Eğik parça en yakın eksene
    en küçük açıyla (`eksene_oturt`, 3°). ÖN = aracın önünden bakış;
    SAĞ / SOL = aracın kendi yanı (`gorunus_adi`, yerleşim 1. açı).
    **Ana görünüş = uzun-geniş yüzü gösteren bakış** (`ana_gorunus`);
    istisna parça başına elle (`parca_ayar[kod]["ana_gorunus"]`). "En çok
    bilgi veren yüzü öne çevirme" YAPILMAZ. Görünüş seçimi: bilgi
    eklemeyen görünüş çizilmez, SAĞ = SOL / ÜST = ALT ise biri.
18. Perspektif üzerine ölçü verilmez.
19. **GENEL KURAL (kullanıcı): tek yönden görünüp öbür yönden görünmeyen
    delik, slot ya da parça için ek detay resmi ya da komple görünüş
    ŞARTTIR.** Özellik duvarının / yüzünün göründüğü görünüşte düz
    çizgiyle çizilir ve orada ölçülenir; o görünüş seçili değilse program
    EKLER (`gerekli_delik_gorunusleri`), ayna ve bilgisizlik elemesi onu
    silemez. Öbür görünüşte yalnız merkez işareti kalır. Hangi deliğin
    hangi yüzde olduğu resimden okunmalıdır (Karluna yan kapak: 4 delik
    dış duvarda, 6 delik iç duvarda).

## PDF (pafta)

- PDF okumak ve atölyede iş yapmak içindir; DXF'le aynı şey değildir.
  Üstünden ölçü alınmaz (kumpas vb. yok), yalnız rakamlar okunur.
- Kâğıt HER ZAMAN YATAY; dikey yalnız açıkça istenirse ("A3-D").
- ANA RESİM BÜYÜK KALIR: detaylar 1. sayfada ana görünüşün ölçeğini
  düşürüyorsa 2. SAYFAYA ("DETAYLAR", aynı PDF'in sonraki sayfası, kendi
  ölçeğinde) gider; gerekirse daha çok sayfa. Karınca duası yerine çok
  sayfa (kullanıcı: "gerekirse aynı kaynak gibi birden fazla sayfa").
  Tek sayfada en küçük yazı 1,2 mm'nin altında kalıyorsa ve ana görünüş
  tek başına en az 1,3 kat büyüyorsa yan görünüşler de 2. sayfaya
  gider; bilgi bloğu (parça adı, malzeme) hep 1. sayfada, ızgara dışında.
- Çizim kâğıdın yaklaşık %70-75'ini doldurur; ölçek serbest ve ara
  değerde olabilir (1:12, 1:14, 1:17 ...). Standart 1-2-5 serisine
  zorlanmaz.
- Antet LİSANSA GÖRE: DENEME'de her çıktı Pi3D / PiVision antetli
  (firma anteti ve `antet_pi3d: 0` yok sayılır); TAM'da Yardım > Firma
  anteti ile verilen A3 antet DXF'i ölçülerek şablona çevrilir
  (`pf5_antet.otomatik_tanim`, LOCALAPPDATA\Pi3D\antet, ayar
  `antet_sablon`), pafta / PDF / kaynak resminde kullanılır. Tek exe
  (1/2 derleme seçimi kalktı). Firma antet DXF'i depoya girmez.
- Antet alanına (A3'te sağ alt 150 x 100 mm) ÇİZİM GİRMEZ; firma anteti
  yoksa oraya Pi3D logolu antet çizilir (`antet_pi3d: 0` ile boş). Dolu
  pencereler (görünüşler, başlık) antete değmez, boş hücre antetin
  üstüne düşebilir.
- Görünüşler birbirine yakın durur (arası en çok 15 mm), dağılmaz.
- Yazılar okunur olmalı; "karınca duası" resim kabul edilmez.
