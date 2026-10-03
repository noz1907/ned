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
  (`EXE_YAP.bat` sorar: 1 yalnız exe, 2 müşteri paketi, 3 ikisi)
  (Inno Setup). Pakette `.py` / `.pyc` / `.spec`, özel anahtar,
  `lisans_masasi/` OLMAZ (bariyer). Lisans makine bazlı (`pf17_lisans`,
  PiProduct düzeni): deneme 8 model, sonra TAM. Özel anahtar depoya
  girmez (`lisans_masasi/keys/` .gitignore'da).
- **Parça hakkında karar isteyen her soru** (standart mı üretim mi,
  ekstrüzyon profilin malzemesi ...) EVET / HAYIR kutusuyla değil AYNI
  TÜR PENCEREYLE sorulur: sorunlu parçaların listesi + ARAMA kutusu
  (binlerce parçada bulunabilsin) + seçilince parça resmi ve bilgisi +
  parça başına karar (`_karar_listesi`, `_resim_paneli`,
  `_standart_karar_penceresi`, `_malzeme_karar_penceresi`). Parça resmi
  tuvalin GÖRÜNEN boyutuna göre çizilir, boyut değişince yeniden çizilir.
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
   referanstan, öbürleri delikten deliğe art arda. **İki delik arası
   mesafe kendi içinde önemlidir** (kullanıcı: "genellikle ayrı zımbalar
   olabilir"): düzenli desende zincir / dizi, düzensiz öbekte her delik
   grubun referans deliğinden paralel; grup ölçüleri kalabalıksa
   detayda, değilse doğrudan parça üzerinde.
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
    Çizgiler ince, ölçü çizgisi kalın asla. **Görünen kontur (ana gövde)
    bir tık kalın**: 0,18 mm, öbür her şey 0,09 mm (ISO 128 kalın : ince =
    2 : 1; `KONTUR_KAL`, `CIZGI_KAL`; kullanıcı: "ölçü çizgileriyle
    karışıyor"); lazer kesim DXF'i değişmez.
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
    Delikten deliğe ZİNCİR yalnız DÜZENLİ desende (iki delik ya da tam
    dikdörtgen); düzensiz öbekte her delik grubun REFERANS deliğinden
    paralel (zincir hizasız delikleri karıştırır). Aynı desenli
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
    en küçük açıyla (`eksene_oturt`, 3°).
    **ÖN GÖRÜNÜŞ = UZUN-GENİŞ DÜŞEY YÜZ** (ANAYASA Chevalier s.49, A "vue
    de face"; kullanıcı: "dar kenarlar çok nadiren ön görünüştür"): parça
    yalnız DÜŞEY eksen etrafında 90° döndürülür (`on_yuz_dondurme`,
    üstü üstte kalır, yatırılmaz, dikilmez); okuyan aracın DIŞINDAN
    bakar (montaj merkezine göre, `montaj_merkezi`). Yatay geniş yüz
    (levha, taban) dikilmez: ana görünüş ÜST olur (`ana_gorunus` = en
    büyük alan; delik / slot yalnız %5 içinde eşit alanlarda karar
    verdirir). İstisna parça başına elle (`parca_ayar[kod]["ana_gorunus"]`).
    **Görünüş adları ANAYASA'dan (Chevalier s.49):** ad, ÖN görünüşe göre
    BAKIŞ YÖNÜNDEN gelir - sağdan bakış SAĞ (ÖN'ün soluna), soldan bakış
    SOL (sağına), üstten ÜST (altına), alttan ALT (üstüne), ARKA uca
    (1. açı). Araç modunda da takas yok (aracın kendi yanına göre
    adlandırma denendi, kaldırıldı). "En çok bilgi veren yüzü öne
    çevirme" (yatırma) YAPILMAZ.
    **YERLEŞİM parçanın durumuna göre** (kullanıcı, Chevalier'nin iki
    dizilişi): GENİŞ görünümlü parça (ÖN'ün eni boyunun 1,2 katından
    büyük: yan kapak, panel) SÜTUN düzeni - ALT, ÖN, ÜST, ARKA alt alta,
    SAĞ solda, SOL sağda (`genis_gorunumlu`, `gorunus_yerlesimi`); dar
    ya da eşit büyüklükte parça standart haç - ARKA en sağda. Gerekçe:
    ARKA sağ uca konsa geniş parçada resim iki kat genişler, ölçek yarıya
    düşer.
    **GÖRÜNÜŞ SEÇİMİ OTOMATİK, SAYI GİRİŞİ YOK** (kullanıcı: "görünüm
    sayısı girişi istemiyorum; sistem parçadaki özelliklere göre 6
    görüntü + 5-6 detay bile yapabilir, aynı kaynakta olduğu gibi"):
    altı görünüşle başlanır (`VARSAYILAN_GORUNUS`), ÖLÇÜLEREK elenir -
    aynı görünen ayna çifti (SAĞ = SOL, ÜST = ALT, ÖN = ARKA) tek
    çizilir (`ayna_ayni`); o yönden delik / slot göstermeyen, dış hattı
    düz dikdörtgen görünüş çizilmez; sade profilde (ekstrüzyon) kalıbın
    boyuna çizgilerinden başka şey göstermeyen boy görünüşü (ÜST / ALT
    şeridi) çizilmez (`bilgisiz_gorunus(sade)`); tek duvar deliği
    taşıyan görünüş (19) ve bükümlü sacın profil görünüşü korunur.
    **Ölçü taşımayan görünüş çizilmez**: konum ve gabari planı bir
    görünüşe hiç ölçü vermiyorsa atılır (tutamakta SOL / ARKA / ALT boş
    kalıyordu; ÖN, ana, korunan, profil kalır). 6 görünüş şart değil,
    gerekirse evet; sıkışan bölgeler detaya (14).
    Komut satırı `--gorunus` ya da parça bazlı liste verilirse o liste
    çizilir, elenmez (`gorunus_zorla`).
18. Perspektif üzerine ölçü verilmez. **Küçük perspektif her resme
    fazladan konur** (kullanıcı: "ufak olarak perspektif yerleştir"):
    önden-sağdan-üstten izometrik, yalnız görünen çizgiler, en uzun
    kenarı parçanın %22'si, öbeğin sağ üstünde (`perspektif_ciz`,
    `IZO_AD`); paftada serbest penceredir, hep 1. sayfada kalır. Ortak
    ayar `P["perspektif"]`, parça bazlı kapatılabilir.
20. **PARÇA BAZLI İSTEK** (kullanıcı: "görselleri, detayları, kesit
    sayısını özellik şeklinde isteyebilirim; komple değil, seçtiğim resim
    ya da parça"): `parca_ayar[kod]` = {`ana_gorunus`, `gorunusler`
    (açık liste), `kesit`, `perspektif`}; ortak ayarı o parça için ezer,
    çizim imzasına girer (`IS.imza(..., pa)`), GUI'de istisna satırı +
    "YALNIZ BU PARÇA (DXF + PDF)" ile yalnız o parça yeniden üretilir.
22. **EĞİK YÜZ İÇİN YARDIMCI GÖRÜNÜŞ** (kullanıcı: "eğik yüz / büküm için
    detay lazım"; ISO 128-3): normali her eksenden 3°'den çok sapan düz
    yüz kümesi (eğik büküm kanadı, eğik duvar; ince kenar yüzleri ve en
    büyük yüzün %2'sinden küçükler sayılmaz) ÜSTÜNDE DELİK VARSA yüze
    DİK bakan "YARDIMCI GÖRÜNÜŞ D" çizilir (`egik_yuzler`,
    `yardimci_gorunusler`; deliksiz eğik kanat çizilmez: gerçek eni sac
    profilinde zaten ölçülüdür, ölçüsüz görünüş çizilmez):
    yalnız o yüzler, gerçek boy; üstündeki delikler (ekseni yüze dik; esas
    görünüşte eğik diye konumsuz kalırdı) yüzün sol / alt kenarından
    ZİNCİRLE (dar halkada nokta), yüzün boyu ve eni, "n x Ø". Delik 8'den
    çok, bir yönde 7'den çok konum ya da halka 3 yazı boyundan darsa
    konumlar zincir yerine o görünüşün DELİK TABLOSUYLA (yüzün sol alt
    köşesinden X, Y) verilir (SOL DİKME: 1300 mm'lik eğik parçada 16
    delik). Referanstan paralel yığın denendi, rakamlar biniyordu. Yüzün KENAR göründüğü esas
    görünüşe bakış oku + harf, yeri çizgi ve yazılarla ölçülerek (yer
    yoksa ok konmaz). Paftada serbest pencere (`YARDIMCI ...`).
23. **DELİK KOORDİNAT TABLOSU yalnız ÇOK delikli görünüşte** (kullanıcı:
    "çok çoklu delikte koordinat koyalım; 4 delik ya da dağınık 3-4'lük
    gruplarda hayır"): bir görünüşte `KOORDINAT_ESIK` (20) ve üstü delik
    varsa o deliklerin konumu ölçüyle değil tabloyla verilir (NO, X, Y, Ø;
    sıfır görünüşün sol alt köşesi; önce X sonra Y; 30 satırda bir yeni
    sütun); çap etiketi ve merkez işaretleri kalır. Eşiğin altı normal
    ölçülenir. `tablo_gorunusleri`, `koordinat_tablolari`; paftada serbest
    (`TABLO ...`); `P["koordinat_tablosu"]` ile kapanır.
24. **SİMETRİK EŞ DENETİMİ** (kullanıcı: "simetrik isimlendirmeli parçayı
    simetrisiyle karşılaştır; gerçekten simetrik değilse uyar"):
    "Symmetry of X" / "Mirror of X" / "X SİMETRİ" adlı parça X ile
    ÖLÇÜLEREK karşılaştırılır (`simetri_anahtari`, `simetri_farklari`):
    hacim (%0,5), yüzey, sıralı gabari (0,2 mm), çap başına delik adedi,
    delikler arası uzaklık kümesi (aynada değişmez), slot adedi. Fark
    varsa başlıkta "! MODEL KONTROL: simetrik eşi (kod) ile uyuşmuyor:
    ...", BOM satırında `model_uyari`, günlükte satır. Ölçü uydurulmaz,
    model denetlenir.
21. **Bu mantıklar KURALDIR**: kullanıcının verdiği her yerleşim / seçim
    mantığı gerekçesiyle buraya ve `OLCULENDIRME_KURALLARI.md`'ye yazılır;
    program seçim yaparken önce bu kuralları uygular, ezbere karar vermez.
19. **GENEL KURAL (kullanıcı): tek yönden görünüp öbür yönden görünmeyen
    delik, slot ya da parça için ek detay resmi ya da komple görünüş
    ŞARTTIR.** Özellik duvarının / yüzünün göründüğü görünüşte düz
    çizgiyle çizilir ve orada ölçülenir; o görünüş seçili değilse program
    EKLER (`gerekli_delik_gorunusleri`), ayna ve bilgisizlik elemesi onu
    silemez. Öbür görünüşte yalnız merkez işareti kalır. Hangi deliğin
    hangi yüzde olduğu resimden okunmalıdır (Karluna yan kapak: 4 delik
    dış duvarda, 6 delik iç duvarda).

25. **SONUÇ ANALİZİ ve DÜZELTME DÖNGÜSÜ** (kullanıcı: "bunları mantıksal
    bazda sakla; resim datası taranırken 'burası şöyle daha doğru olur'
    denebilsin; PDF'te sonuç analiz edilsin, gerekirse düzeltme, sonra
    PDF ve DXF yeniden çıksın"; "ölçüler birbirine girmesin: dış ölçüleri
    verirdim ama burayı detaya alırdım, ana ölçüden / delikten / köşeden
    referanslayarak"; onay "tamam" 03.10.2026). UYGULAMA: konum
    ölçülerinin DENEME geçişinde çizilen İÇ ölçüler (ölçü çizgisi
    görünüşün içinde: özelliğin yanına konmuş yerel ölçü, delik grubu içi;
    dış zincir katılmaz, onun kısa halkası `_kosu_hatti`'nde ayıklanır)
    ÖLÇÜLÜR (`yigilma_kayiplari`): yazı kutuları `YIGILMA_ARALIK`·h (1)
    içinde değen ya da uçları `YIGILMA_UC`·h (3) içinde olan ölçüler bir
    öbektir; öbekte `YIGILMA_EN_AZ` (3) ve daha çok ölçü ya da kısa
    halkalı (`KISA_HALKA`·h) en az 2 ölçü varsa iki ucu da (iç ölçünün iki
    ucu da özelliktir) kayıp listesine girer; `bolge_sec` bölgeyi seçer
    (köşeye yakınsa köşeye uzar, kenarın 0,5·h dışına kadar), `bolge_plani`
    bölgedeki konumları ana görünüşten çıkarır, detayda referans bölge
    datum kenarını / köşeyi içeriyorsa kenar, içermiyorsa ana görünüşte
    ölçülü BAĞLANTI özelliği (14. kuralla aynı). Yön ölçünün açısından
    okunur (5 x 50 çapraz iki deliğin "5"i yataydır). Örnek: kasa P01 "K0
    KABIN KORUMA - ON DUVAR SACI" ARKA sol üst köşe (66, 5, 50, 21,5, 7,5,
    73 + "ARKA" iç içeydi) -> DETAY D, sağ üst (66, 5, 67) -> DETAY F,
    164/260/912/.../435 ana görünüşte. Kapatma: `P["yigilma_analizi"]`.
    Ayrıntı günlüğü: `PI3D_AYRINTI=1` (her deneme: kayıp, yığılma, bölge).
    Sorunlu örnekler `test/OKU.md`'deki listede tutulur, her değişiklik
    onlarla sınanır (`test/yigilma_denetimi.py`).
    **KÂĞIT ÖLÇEĞİNDE ikinci tur** (`sonuc_analizi_dongusu`, v1.0.18): resim
    çizildikten sonra pafta planı kuru koşulur (`pafta_kur(yalniz_plan=True)`,
    dosyaya yazılmaz); ölçü rakamı kâğıtta `SONUC_YAZI_MM` (2,5) altında ya
    da yazılar `SONUC_ARALIK_MM` (0,8) içinde ise kural: yazı boyu çarpanı
    (`yazi_kat`, en çok 1,8) büyütülür, yığılma aralığı +0,5·h; DXF yeniden
    çizilir (PDF aynı DXF'ten). En çok `SONUC_TUR` (3) tur; büyütmek kâğıtta
    kazandırmıyorsa (çizim büyüyüp ölçek düşüyor) durur, en iyi tur (rakam
    en büyük, yığılma en az) dosyada kalır. Bulgu ve karar günlükte ve
    olculer.json'da (`analiz`). `P["sonuc_analizi"]`, `--analiz-yok`.

26. **TOLERANS** (kullanıcı tablosu 03.10.2026; onay "tamam", v1.0.18):
    tolerans REFERANS ZİNCİRİNE göre verilir (referansın kendi
    belirsizliği + uzaklık); değerler toplam bant: boy <= 1 m 0,3, <= 1,5
    m 0,5, üstü 0,8 (CNC; konvansiyonel +0,15); pres delik konumu 0,4;
    abkant 1; rollform 0,25-0,8; düzlemsellik rollform 1/m, pres 0,8/m;
    iç kesim 0,6, delik çapı 0,4; diklik CNC 0,4 / pres 0,6 / rollform 0,6
    / abkant 1; kaynak konumu 1; açı 1°-1,5° (kalınlığa göre); toplam boy
    1,5 m üstü 1,5-2; küçük lazer / pres parça 0,6. ISO sınıfı seçeneği
    (ISO 2768 f/m/c/v + H/K/L, ISO 13920 A-D, ISO 9013, DIN 6930).
    Montajda giydirme değil referansa göre; açınım / lazer DXF'ine
    tolerans girilmez; düzeltme arayüzü toplu ya da ölçü ölçü, DXF + PDF
    birlikte güncellenir; K-faktörü parça bazlı. Ayrıntı ve kaynaklar:
    `OLCULENDIRME_KURALLARI.md` 11.
    UYGULAMA: `pf3_olcu.TOLERANS` (tek sözlük), `ISO2768`, `tolerans_bandi`,
    `surec_tahmini` (bükümlü sac: kesim lazer, konum pres, kanat abkant;
    düz sac lazer / pres; profil; öbürü CNC), `tolerans_isle` (çizilmiş
    her ölçü: görünüş, tür, yön, değer, süreç, bant, ±, referanstan uzaklık
    `L_ref`, zincir birikimi, uyarı; kimlik `id` aynı çizimde değişmez),
    `tolerans_etiketleri` (özel ± ölçünün yanına, yer ölçülerek). Gabari =
    değer gabariye eşit VE uçlar görünüşün iki kenarında. **Ara referans**
    (kullanıcı): CNC ve preste boydan boya işte her ~500 mm'de referans
    noktası zinciri böler (3 m'de bile ±2'nin altı); **abkant ve rollformda
    ara referans OLMAZ**. Kontrol fikstürü gibi hassas işlerde (honlama,
    taşlama, yüzey toleransı) tablo yetmez: parça bazlı özel ± / ISO sınıfı
    kullanılır; ileride yüzey ve geometrik tolerans genişletilecek.
    Parça bazlı: `parca_ayar[kod]["tolerans"]` = {surec, sinif, olcu: {id: ±}}
    (GUI TOLERANS penceresi); `parca_ayar[kod]["k_faktor"]` (açınım K
    sütunu, `k_parca` -> `acilim_yaz` / `lazer_yaz`; çizim imzasına girmez).

27. **ÖLÇÜ / TOLERANS DÜZENLEME** (kullanıcı: "her resim seçilebilir
    olmalı; ölçüler numaralı çıkmalı; toleransı değiştirebilmeli ya da
    silebilmeliyim; ölçüyü silebilmeliyim; değiştirme olmaz çünkü ölçüyü
    doğru kabul ediyorum; değişiklik PDF ve DXF dahil; genel akışın içinde
    ya da dışında"): her ölçü çizimde numaralanır (`olculeri_numarala`:
    görünüş sırası, yukarıdan aşağı, soldan sağa) ve DXF'e XDATA yazılır
    (PI3D: OLCU, kimlik, no, tür, değer, ±, görünüş, ref, özel; kılavuz
    ve ± etiketi ölçünün handle'ıyla bağlı). `olcu_listesi` / `olcu_duzenle`
    model olmadan DXF'i düzenler: özel ± (etiket ölçülerek; yer yoksa
    ölçü yazısının içine), toleransı sil = referans ölçü "(..)" (ISO 129-1),
    genele dön, ölçüyü sil (blok, kılavuz, etiketle). DEĞER DEĞİŞMEZ.
    Kayıt kimlikle `parca_ayar[kod]["tolerans"]` = {olcu: {id: ± | "ref"},
    sil: [id]}; yeniden çizimde `tolerans_isle` uygular. GUI
    `olcu_duzenle_penceresi`: resim listesi + numara balonlu önizleme
    (balon yalnız pencerede) + ölçü listesi; KAYDET = DXF + pafta + PDF.
28. **AÇINIM ve LAZER ÖLÇÜSÜ** (kullanıcı: "lazer kesimde ölçülendirme
    yok; açınımda yalnız dış ölçüler ve delik pozisyonları, bunun dışında
    ölçü olmayacak; üç resim: ölçülü, ölçüsüz ve izometrik bükümlü - hem
    DXF'te hem PDF'te"): lazer DXF'i yalnız KESIM konturları (CAM her
    çizgiyi keser). Açınımda doğrusal ölçü yalnız boy ve en; delik
    konumları sol alt köşeden KOORDİNATLI ölçü (`_acinim_delik_konumlari`:
    "0" köşede; X kılavuzu yakın kenara, Y sola; kılavuz başka deliğin
    üstünden geçecekse başlıkta x; y; rakam yeri ölçülür, gabari yolu
    önceden ayrılır). **IZGARA** (11. kural): detay resmiyle AYNI öbek kuralı
    (`izgara_obekleri`: en az 12 kesim, boşluk dar ölçünün 2,5 katından
    az, en az iki sıra ve iki sütun; cıvata deliği öbeği ızgara değildir,
    8 yakın delik ölçütü uzun şasi kolunda 39 cıvata deliğini gizliyordu)
    tek tek ölçülmez;
    bölge kesik çerçeveyle işaretlenir, iki köşesi (başı ve sonu) sol alt
    köşeden ölçülür; çerçeve ENGELDİR, hiçbir ölçü çizgisi desenin
    içinden geçmez (geçecekse o delik başlıkta x; y). Kalan konum
    rakamları kenar boyuna SIĞMIYORSA (ölçülerek) ya da bir yönde 60'tan
    çoksa ölçü yok, lazer DXF'i verir (Karluna UST_SAC: 114 delik, 96'sı
    ızgara; önce hiç konum yoktu). Büküm konum ölçüsü YOK (yerleri büküm çizelgesinde).
    Açınım resminde: ölçülü açınım, altında ÖLÇÜSÜZ açınım (kontur +
    büküm eksenleri), sağda izometrik bükümlü resim; çizelgeler (büküm,
    abkant kanat) ve profil kalır. **Tablolar SEÇENEKLİ** (kullanıcı: "tablo
    kalsın ya da seçenek koy, müşteri isteyebilir"): `P["acinim_tablo"]` /
    ayar `acinim_tablo` (varsayılan açık), GUI 6. sekme kutusu,
    `--acinim-tablo-yok`; kapalıyken profil ve izometrik kalır, K / B
    adları kalır, kanat değerleri yazılmaz. Açınım kaydına `tablo` girer.
    Ölçüsüz kopya çizilmiş HER ŞEYİN altına ölçülerek konur.
    **AÇINIM ARAÇ YÖNÜNDE** (kural 17; kullanıcı: "bu resim neden ters;
    ölçerek değil, araç konumunda hangi yöndeyse; alt ve üst
    karışmamalı; arka görüntü aynı, sadece tersi olur"): açınım hesabı
    parçayı büküm ekseni Z olacak biçimde yatırır; düzlemin eksenleri
    3B'de bilinir (`duz_yon`: +X büküm ekseni, her duvarda +Y = B·u) ve
    çizim (araç) çerçevesine çevrilir (`acinim_araca_oturt`,
    `acinim_arac_yonu`, `acinim_cevir`). Parça DİKEY ise (dikey duvar
    alanı yataydan büyük) alanca ağır basan dikey duvarlar YUKARI okunur;
    YATAY ise (levha, dikey dudakları olsa da) ÜST görünüş gibi. Sağ-sol
    görünüşün sağına eşlenir (olmazsa ayna kabul). Kontur, delik, büküm
    yeri / sırası (B1 hep alt kenarda), profil etiket sırası ve lazer
    DXF'i birlikte çevrilir. İZOMETRİK bükümlü resim detaydaki
    perspektifle aynı çerçeveden (`IZO_GOZ`); PROFİL resmi büküm ekseni
    yönünden bakan detay görünüşü gibi (eksen X -> SAĞ, Y -> ÖN, Z ->
    ÜST; `profil_araca_oturt`). Karluna ÜST SAÇ açınımı baş aşağıydı
    (menteşeler üstte; araçta altta), ön panel profili yatıktı. 3B
    (çok yönlü) açınımda da aynı: her duvarın serme dönüşümünden düzlem
    eksenleri 3B'de çıkar (kök duvarın +X'i), eğik büküm çizgileri birlikte
    döner.
    Açınım kaydına `cizim` (ACINIM_CIZIM_SURUMU) ve `arac` girer: kod ya
    da araç yönü değişince eski açınım yeniden çizilir.

## PDF (pafta)

- PDF okumak ve atölyede iş yapmak içindir; DXF'le aynı şey değildir.
  Üstünden ölçü alınmaz (kumpas vb. yok), yalnız rakamlar okunur.
- Kâğıt HER ZAMAN YATAY; dikey yalnız açıkça istenirse ("A3-D").
- ANA RESİM BÜYÜK KALIR: detaylar 1. sayfada ana görünüşün ölçeğini
  düşürüyorsa 2. SAYFAYA ("DETAYLAR", aynı PDF'in sonraki sayfası, kendi
  ölçeğinde) gider; gerekirse daha çok sayfa. Karınca duası yerine çok
  sayfa (kullanıcı: "gerekirse aynı kaynak gibi birden fazla sayfa").
  1. SAYFA DAĞILMAZ (kullanıcı: "böyle dağınık çizim yapılmaz: ön, sağ
  ya da sol, alt yaparsın; ekstra arka ve detaylar yaparsın"): ÖN + bir
  yan (SAĞ, yoksa SOL) + bir üst / alt + kesit hep 1. sayfada izdüşüm
  düzeninde kalır. Yalnız EKSTRA görünüşler (ARKA, ikinci yan, ikinci
  üst / alt; `_ekstra_gorunusler`) tek sayfada yazı 1,2 mm'nin altında
  kalıyorsa ve çekirdek en az 1,3 kat büyüyorsa 2. sayfaya gider; 2.
  sayfadaki görünüşler TEK SIRADA, resimdeki hizada durur
  (`_gorunus_sirasi_yerlestir`), detaylar altına. Bilgi bloğu (parça
  adı, malzeme) hep 1. sayfada; ızgaranın boş hücresine düşüyorsa
  orada, yeni satır / sütun açıyorsa serbest pencere (yan kapakta
  ızgaraya satır olarak girip 1:7'yi 1:11'e düşürmüştü). Perspektif
  (IZO) serbest pencere, hep 1. sayfada.
- **ÇOK KÜÇÜLTME GEREKEN RESİMDE SAYFA KURALI** (kullanıcı, 03.10.2026:
  "bu tarz çok fazla küçültme yapılacak resimlerde: tablo seçilirse ön
  resim + tablo + yan görünüş sağ ya da sol 1. sayfada; ölçüsüz resim ya
  da kalan görünüm 2. sayfada; her zaman, her durumda, her paftada, PDF'te
  ve DXF'te geçerli"; "resimler ya da ne varsa A3'ün antet ve kenar
  boşlukları dışındaki alanının en çoğunu kaplayacak; 2. sayfa ilk sayfa
  hangi boydaysa o boyda"; "kural koy buna da"). UYGULAMA: tek sayfada
  yazı `SAYFA_AYIR_YAZI_MM` (1,2 mm) altına düşüyorsa:
  1. kademe ekstralar 2. sayfaya (yukarıdaki kural); 2. kademe yazı hâlâ
  küçükse üst / alt görünüş de gider - 1. sayfada ana görünüş, ÖN, bir
  yan (SAĞ, yoksa SOL), kesit (`_yan_cekirdek`). TABLO (delik koordinat
  tablosu, açınım büküm / abkant tablosu) ve açınımın PROFİL'i (yan
  görünüş) 1. sayfada kalan serbest pencerelerdir (`SAYFA1_ONEK`); TABLO
  penceresi KENDİ ÖLÇEĞİNDE: yazısı kâğıtta `TABLO_YAZI_MM` (2,5) olacak
  kadar (ana ölçekten küçük değil; yer yoksa `TABLO_ESNEK` ile geri).
  AÇINIM resmi bölümlerini işaretler (`gorunus_isareti`: ON = ölçülü
  açınım, `TABLO ACINIM`, `PROFIL`, `IZOMETRIK`, `BASLIK`, `OLCUSUZ`);
  açınımda ana görünüş ÖN'dür (`_ana_gorunus`: yalnız standart adlar),
  çok küçültmede ÖLÇÜSÜZ açınım ve İZOMETRİK 2. sayfaya gider (kazanç
  şartı aranmaz). Büyük profil DXF'te küçültülür (`PROFIL_EN_COK` 30
  yazı boyu; etiketler temiz yerleşmezse bir büyük ölçeğe dönülür).
  Sağ sütun ölçülü açınımın ölçülmüş sağ sınırından başlar, başlık
  satırları açınımın genişliğinde kırılır (pencereler üst üste binerse
  pafta tek pencereye düşüyordu). Açınım KÂĞITTA ölçülür
  (`acinim_kagit_dongusu`): rakam 1,5 mm (`ACINIM_YAZI_EN_AZ_MM`; kullanıcı:
  "1,5'ta olabilir; üst ve sol kenar sıkıntı yok") altındaysa yazı büyütülüp
  yeniden çizilir, ama ölçeği ilk turun %85'inin altına düşüren tur
  alınmaz (resim büyük kalır). 2. sayfa aynı kâğıt boyunda, sığan en
  büyük ölçekte. DXF'te sayfalar PAFTA, PAFTA_2 ... sekmeleridir. Örnek:
  Karluna ÜST SAÇ açınımı 1:16 tek sayfa (rakam 0,5 mm) -> 1. sayfa 1:7
  (açınım + tablo + profil), 2. sayfa ölçüsüz + izometrik.
- Çizim kâğıdın yaklaşık %70-75'ini doldurur; ölçek serbest ve ara
  değerde olabilir (1:12, 1:14, 1:17 ...). Standart 1-2-5 serisine
  zorlanmaz.
- Antet LİSANSA GÖRE: DENEME'de her çıktı Pi3D / PiVision antetli
  (firma anteti ve `antet_pi3d: 0` yok sayılır); TAM'da Yardım > Firma
  anteti ile verilen A3 antet DXF'i ölçülerek şablona çevrilir
  (`pf5_antet.otomatik_tanim`, LOCALAPPDATA\Pi3D\antet, ayar
  `antet_sablon`), pafta / PDF / kaynak resminde kullanılır. Tek exe
  (1/2 derleme seçimi kalktı). Firma antet DXF'i depoya girmez.
- Antette sayfa "n / toplam" (ISO 7200; kullanıcı: "1/2 gibi sayfa
  kısmı"): bütün sayfalar açıldıktan sonra yazılır (`_sayfa_sayisini_yaz`).
- Antet alanına ÇİZİM GİRMEZ. Pi3D anteti çizilirken (DENEME ya da firma
  anteti yokken) kutu ALÇAKTIR: A3'te sağ alt 150 x 40 mm (logo şeridi 12 + 4 satır)
  (`ANTET_BOY_PI3D`; kullanıcı: "antet yüksek gelmiş, normal antette bu
  yerleşim mümkün"); firma kendi antetini yapıştıracaksa (`antet_pi3d:
  0`) 150 x 100 boş kalır. Dolu pencereler (görünüşler, başlık) antete
  değmez, boş hücre antetin üstüne düşebilir.
- Görünüşler birbirine yakın durur (arası en çok 15 mm), dağılmaz.
- Yazılar okunur olmalı; "karınca duası" resim kabul edilmez.
