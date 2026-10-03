# Pi3D – Teknik resim ve ölçülendirme kuralları (normalize)

Bu belge programın **uzmanlığıdır**: detay resmi çizilirken ve
ölçülendirilirken uyulan kurallar, her kuralın gerekçesi, kaynağı ve
kodda nerede uygulandığı. Kısa liste `CLAUDE.md`'dedir; burası tam
sürümüdür.

Kaynaklar (kısaltma):
- **K** = kullanıcının verdiği kural (atölye pratiği, firma standardı).
- **CH s.N** = Chevalier, *Guide du dessinateur industriel* (taranmış
  57 sayfalık bölüm; sayfa = PDF sayfası, kitap sayfası = PDF + 38).
- **LC s.N** = "Le dessin technique – La cotation" (NF P 02-001 ders
  notu, 10 sayfa): yerleşimin mm değerleri.
- **RC s.N** = "Dessin technique – Règles de cotation" (13 sayfa, Kuzey
  Amerika geleneği): iki aşamalı yöntem, kılavuz açıları.
  Bu üçü ANAYASA'dır (kullanıcı). Metin kopyalanmadı, kurallar kendi
  cümlelerimizle özetlendi; özetler scratchpad `kaynak_pdf/*.md`.
- **ISO** = ISO 128 (çizgi / görünüş), ISO 129-1 (ölçülendirme),
  ISO 5455 (ölçek), ISO 5459 (datum), ISO 2768 (genel tolerans).
- **Kod** = `pf3_olcu.py` (çizim), `pf4_pafta.py` (pafta / PDF).

Öncelik çelişkide: **K > CH > ISO**. Kullanıcının kuralı firmanın
resmini tanımlar; kitap ve standart gerekçe ve boşluk doldurma içindir.

---

## 0. Temel ilkeler

| # | Kural | Gerekçe | Kaynak | Kod |
|---|-------|---------|--------|-----|
| 0.1 | **Yanlış ölçü asla.** Emin olunmayan ölçü yazılmaz, raporda sayılır (`yer_yok`, `gabari_yok`, `atlanan`). | Yanlış rakam atölyede hurdadır; eksik rakam sorulur. | K | `SON_RAPOR`, `olcu_dogrulama.py` (399 ölçü, 0 hata) |
| 0.2 | **Ölç, tahmin etme.** Yazının yeri, çakışma, ölçek hesapla değil ölçülerek bulunur. | Yazı tipine bağlı genişlik hesapla tutmaz. | K | `_yazi_siniri`, `mtext_kutusu`, `_cizgi_kesiyor`, `cizim_cakisma_denetimi.py` |
| 0.3 | **Uzman ressam gibi:** karışıklık ana görünüşe tıkıştırılmaz, detaya taşınır (bkz. 6). | Okunmayan resim yanlış okunur. | K | `bolge_sec`, `bolge_detaylari` |
| 0.4 | Her değişiklik dört gerçek modelde (kasa 144, Karluna 55, Televre 111, tente 61 parça) denetlenir: kayıp ölçü 0, çakışma 0. | | K | `test/`, `dxfdene/tum.py` |

## 1. Çizgiler ve yazı – sayısal ANAYASA

Kod: `pf3_olcu.ANAYASA` (kâğıt mm, A3, yazı 3,5 mm; DXF'te yazı boyunun
katı). Üç kaynağın uzlaşması:

| öğe | CH | LC | RC | Pi3D |
|---|---|---|---|---|
| rakam yüksekliği | 3,5 | 2,5–5 | – | 3,5 (asla < 2,5) |
| ok boyu / açıklık | – / 30° | 3–5 / 30–45° | – | 3 / 30° |
| uzatma – kontur boşluğu | (ISO ~1) | 2–5 | ~1 | 1,5 |
| uzatma taşması | 1–2 | ~1–2 | ~2 | 2 |
| ilk ölçü çizgisi – görünüş | (8–10) | 10 | ~10 | 10 |
| ölçü çizgileri arası | (6–8) | 7–10 | ~10 | 8 |
| kılavuz eğimi | – | – | 30/45/60° | 30/45/60° |
| rakam yeri | çizgi üstü, sağdan okunur | çizgi üstü, düşeyde dönük | çizgi içinde (ANSI) | ISO: çizgi üstü |
| ok – uzatma çizgisi | – | – | tam değer, boşluk 0 | 0 |


| # | Kural | Gerekçe | Kaynak | Kod |
|---|-------|---------|--------|-----|
| 1.1 | Kontur (görünen kenar, ana gövde) **bir tık kalın: 0,18 mm**; ölçü / uzatma / kılavuz / eksen / gizli / tarama **ince** 0,09 mm sürekli çizgi. Ölçü çizgisi kalın asla. | Ölçü resmi bastırmaz; kullanıcı: "ana gövde ölçü çizgileriyle karışıyor"; ISO 128 çizgi grubu kalın : ince = 2 : 1. | K; CH s.2; ISO 128 | `KONTUR_KAL` 18, `CIZGI_KAL` 9 (DXF merdiveni); lazer `KESIM` 0,09 |
| 1.2 | Ok dolu, 30°, boyu yazı boyu kadar; bir resimde tek tip uç. Dar zincir halkasında ok yerine **nokta**. | Küçük halkada oklar üst üste biner, kuyruk komşu rakama girer. | CH s.3; K ("aynı hizada") | `_ara_ciz(sik=True)`: `DOTSMALL`, `dimsoxd` |
| 1.3 | Parçanın **içinde** biten kılavuz (kalınlık "t 1,5", not) noktayla, kontura değen kılavuz okla biter. | | CH s.9 | `kalinlik_notu` |
| 1.4 | Yazı boyu parçaya göre: `yazi_boyu = min(20, max(1,8, boy/70))`; PDF'te en az ~1 mm, hedef 1,2–2 mm. | "Karınca duası" olmaz. | K; CH s.3 (3,5 mm) | `yazi_boyu`, pafta `yazi_mm` |
| 1.5 | Rakam ölçü çizgisinin üstünde, çizgiye paralel; hiçbir çizgi rakamı kesmez. Düşey ölçüde rakam yatay okunur (ISO yöntem 2). | Okunurluk. | CH s.3, s.9; ISO 129-1 | `dimtoh/dimtih = 1`; `_dim_yaziya_degiyor` |
| 1.6 | Birim mm, yazılmaz; ondalık **virgül**, ölçüde binlik ayracı yok (1513,8); açıda "°". | Türkçe yazım. | K; CH s.3 | `XL.tr`, `dimdsep` |

## 2. Görünüşler

| # | Kural | Gerekçe | Kaynak | Kod |
|---|-------|---------|--------|-----|
| 2.1 | **Parça montaj yönünde çizilir, döndürülmez.** ÖN / SAĞ / ÜST modeldeki yöndür. | Atölye parçayı montajdaki gibi görür; ters resim hataya yol açar (kabin koruma). | K | `dxf_komponent` (döndürme yalnız `P["ana_gorunus_dondur"]`) |
| 2.2 | **Görünüş seçimi OTOMATİK, sayı girişi yok.** Altı görünüşle başlanır, ölçülerek elenir: aynı görünen ayna çifti (SAĞ = SOL, ÜST = ALT, ÖN = ARKA) tek çizilir; o yönden delik / slot göstermeyen, dış hattı düz dikdörtgen görünüş çizilmez; sade profilde (ekstrüzyon) kalıbın boyuna çizgilerinden başka şey göstermeyen boy görünüşü çizilmez. Tek duvar deliği taşıyan görünüş (2.8) ve bükümlü sacın profil görünüşü korunur. Konum / gabari planı hiç ölçü vermeyen görünüş çizilmez (ÖN ve ana görünüş kalır). 6 görünüş şart değil, gerekirse evet; sıkışan bölgeler detaya (6.x). Açık liste (komut satırı, parça bazlı) verilirse elenmez. | Kullanıcı: "sistem parçadaki özelliklere göre 6 görüntü + 5-6 detay bile yapabilir, kaynaktaki gibi". Bilgi eklemeyen görünüş yer kaplar, ölçeği düşürür. | K; CH s.49 | `VARSAYILAN_GORUNUS`, `gorunus_sec`, `ayna_ayni`, `bilgisiz_gorunus(sade)`, `gorunus_zorla` |
| 2.3 | **Ana görünüş** = uzun-geniş yüzü gösteren bakış (en büyük alan; delik / slot yalnız %5 içinde eşit alanlarda karar verdirir). Gabari onun üstünde (bkz. 4.1). | "Dar kenarlar çok nadiren ön görünüştür." | K; CH s.49 | `ana_gorunus` |
| 2.4 | Bükümlü sacın büküm eksenine bakan görünüşü **profil (kesit yerine)**: kanat dış ölçüleri, kalınlık ve açılar oradadır; iç yüz ve radüs teğeti ölçülmez. | Profilde ölçü nettir; ince şeritte okunmaz. | K ("kenar 54'ü kesitten ver") | `sac_kesit_gorunusleri`, `kanat_olculeri` |
| 2.5 | Görünen çizginin üstüne gizli çizgi çizilmez; çakışan bölüm kesilir. | Teknik resim kuralı. | ISO 128 | `hlr`, `test_gizli_cizgi.py` |
| 2.6 | İsteğe bağlı **kesit**: kesit düzlemi ana görünüşte uçlarında kalın kısa çizgi + bakış okları + harf; kesit görünüşünün üstünde "A-A"; tarama ince; tarama rakamın çevresinde kesilir. | | CH s.9, s.49, s.51 | `kesit_ciz`, `kesit_isareti` (`P["kesit"]`) |
| 2.7 | Perspektif üzerine ölçü verilmez; büküm resmindeki izometrik yalnız yön içindir. **Her detay resmine küçük perspektif fazladan konur**: önden-sağdan-üstten izometrik, yalnız görünen çizgiler, en uzun kenarı parçanın %22'si, öbeğin sağ üstünde; paftada serbest pencere, hep 1. sayfada. | Kullanıcı: "ufak olarak perspektif yerleştir resimlerde, fazladan olsun". Okuyan parçayı bir bakışta tanır. | K | `perspektif_ciz`, `IZO_AD`, `P["perspektif"]` |
| 2.10 | **Yerleşim parçanın durumuna göre** (Chevalier'nin iki dizilişi): GENİŞ görünümlü parça (ÖN'ün eni boyunun 1,2 katından büyük: yan kapak, panel) SÜTUN düzeni - ALT, ÖN, ÜST, ARKA alt alta; SAĞ solda, SOL sağda. Dar ya da eşit büyüklükte parça standart haç - ARKA en sağda. 1. açı bozulmaz. | ARKA sağ uca konsa geniş parçada resim iki kat genişler, ölçek yarıya düşer; sütunda hepsi tek sayfaya sığar. | K; CH s.49 | `genis_gorunumlu`, `gorunus_yerlesimi` |
| 2.12 | **Eğik yüz için yardımcı görünüş** (yüzde delik varsa): eksenlere 3°'den çok eğik düz yüz kümesine dik bakış ("YARDIMCI GÖRÜNÜŞ D"), yalnız o yüzler, gerçek boy; üstündeki delikler yüzün kenarından zincirle (kalabalık ya da dar zincirde delik tablosu), yüzün boyu ve eni, "n x Ø"; yüzün kenar göründüğü esas görünüşte bakış oku + harf. İnce kenar yüzleri ve küçük yüzler (en büyük yüzün %2'si altı) sayılmaz. | Eğik yüzün delikleri esas görünüşte eğik eksenli diye konumsuz kalıyordu; eğik yüz esas görünüşte kısalmış görünür (ISO 128-3, ASME Y14.3). Kullanıcı: "eğik yüz / büküm için detay lazım". | K; ISO 128-3 | `egik_yuzler`, `yardimci_gorunusler` |
| 2.13 | **Simetrik eş denetimi**: "Symmetry of X" adlı parça X ile ölçülerek karşılaştırılır (hacim, gabari, delik adedi, delikler arası uzaklıklar, slot adedi); fark varsa "! MODEL KONTROL: simetrik eşi ile uyuşmuyor". | Kullanıcı: "gerçekten simetri değilse uyarmalısın". Adı simetrik olup geometrisi farklı parça atölyede yanlış üretilir. | K | `simetri_anahtari`, `simetri_farklari`, `calistir` |
| 2.11 | **Parça bazlı istek**: ana görünüş, görünüş listesi, kesit, perspektif tek parça için ortak ayarı ezer; yalnız o parça yeniden üretilir. | Kullanıcı: "görselleri, detayları, kesit sayısını özellik şeklinde isteyebilirim; komple değil, seçtiğim parça". | K | `parca_ayar`, GUI istisna satırı, "YALNIZ BU PARÇA" |
| 2.9 | **ÖN görünüş = uzun-geniş düşey yüz; görünüş adları bakış yönünden (Chevalier s.49).** A "vue de face" parçayı en iyi anlatan yüzdür: parça yalnız düşey eksen etrafında döndürülür (üstü üstte), geniş düşey yüz ÖN'e gelir; okuyan aracın dışından bakar. Yatay geniş yüz (levha) dikilmez, ana görünüş ÜST olur. Öbür görünüşlerin adı ÖN'e göre bakış yönünden: üstten B = ÜST (altına), sağdan C = SAĞ (soluna), soldan D = SOL (sağına), alttan E = ALT (üstüne), arkadan F = ARKA (uca); 1. açı; araç modunda ad değişmez. | Kullanıcı: "dar kenarlar çok nadiren ön görünüştür". Ad bakış yönünü söyler; aracın yanı araç yönü ayarından bellidir. | CH s.49; K | `on_yuz_dondurme`, `cizim_cercevesi`, `ana_gorunus`, `gorunus_adi`, `gorunus_yerlesimi` |
| 2.8 | **Tek yönden görünüp öbür yönden görünmeyen delik / slot / parça için ek detay ya da komple görünüş şart.** Tek duvar deliği duvarının göründüğü görünüşte düz çizgiyle çizilir ve ölçülenir; gereken görünüş yoksa eklenir, ayna / bilgisizlik elemesi silemez. | Okuyan hangi deliğin hangi yüzde olduğunu resimden bilmeli; aksi hâlde hepsini aynı yüze deler. | K (Karluna yan kapak) | `delik_duvarlari`, `slot_duvarlari`, `delik_gorunusu`, `gerekli_delik_gorunusleri` |

## 3. Referans (datum)

| # | Kural | Gerekçe | Kaynak | Kod |
|---|-------|---------|--------|-----|
| 3.1 | Her yönde **tek referans**; sağ / sol ya da üst / alt için ayrı referans olmaz. | İki sıfır noktası okuyanı şaşırtır; ISO tek ortak referans ister. | K; ISO 129-1 | `konum_plani` (`datum`) |
| 3.2 | Datum **düz yüz ya da eksen**; radüs teğeti asla. Uç radüsse içerideki ilk düz yüz / eksen. | Radüs üzerinde ölçü alınamaz. | K; CH s.27 | `tasarim_seviyeleri(datum=True)`, `_datum_seviyesi` |
| 3.3 | Datum simgesi: üçgen + kare içinde harf (A, B, C). Yüzey datumu kontur ya da uzatma çizgisi üstünde; eksen datumu ilgili ölçünün okuyla hizalı. Parçanın XYZ çerçevesi: en geniş yüz A. | | CH s.27; ISO 5459 | `datum_isaretleri`, `_datum_duz_yuze`, `_datum_uzantiya` |
| 3.4 | Simetrik parçada simetri ekseni çizilir, simetrik eşe ikinci ölçü konmaz; eksen yazıyı kesmez. | Her öznitelik bir kez. | K; CH s.6 | `simetri_isareti` |

## 4. Konum ölçüleri

| # | Kural | Gerekçe | Kaynak | Kod |
|---|-------|---------|--------|-----|
| 4.1 | **Dış ölçüler kesinlikle ve önce.** Ana görünüş iki boyutunu en dışta taşır; derinlik yan görünüşte / profilde. Gabarinin uzatma yolu önceden ayrılır; `gabari_yok` 0. | Okuyan parçanın büyüklüğünü ilk bakışta görür. | K | `gabari_plani`, `_gabari_yolu_ayir`, `gabari_olculeri` |
| 4.2 | Konum **referanstan başlar**; sonra zincir (0→A→B) ya da paralel (0→A, 0→B), yapıya göre. Tek hatta rakam dizmek (cetvel / rollform ayar ölçüsü) kullanılmaz. | Zincir hata biriktirir ama okunur; kümülatif hat atölyede kullanılmaz. | K; CH s.8 | `_kosu_hatti`, `_kosu_dene` |
| 4.3 | Son delikten kenara ölçü **verilmez**: gabari ile zincir onu belirler (artık ölçü yasağı). | Fazla ölçü tolerans çelişkisi doğurur. | CH s.39–40 | `konum_plani` (son→kenar kaldırıldı) |
| 4.4 | Ölçü gösterdiği özelliğe **yakın yana** konur, iki yana dengeli; uzatma çizgisi özelliğin kendisinden başlar. | Uzun uzatma çizgisi resmi keser. | K | `_taraf_sec` |
| 4.5 | **Uzatma / ölçü çizgisi delik, slot, pencere üstünden geçmez.** Temiz yan seçilir; iki yan da kapalıysa bölge detaya (6). | Şekil üstünden geçen çizgi şekli bozar. | K | `_engel_sayisi`, `yerel` |
| 4.6 | Rakam kendi aralığının hizasında; düşey zincirde rakamlar hattın aynı yanında, aynı eksende. | Komşu aralığa kayan rakam yanlış okunur. | K; CH s.9 ("aynı hiza") | `_yazi_hizasinda` |
| 4.7 | Kısa ölçüler içeride, uzunlar dışarıda; ölçü çizgileri kesişmez; ölçü çizgisi kontur ya da eksenle aynı doğrultuda olmaz. | | CH s.9; ISO 129-1 | `_seviyele`, `_ara_yerlestir` |
| 4.8 | Eşit adımlı dizi: kenardan ilk delik, sonra **"n x p = toplam"** (n aralık sayısı). Izgara (sık kesim): iç ölçü verilmez, bölge kesik çizgiyle işaretlenir, başı ve sonu referanstan. | Lazer DXF'i içi verir. | K; CH s.7 | `_dizi`, `izgara_bolgeleri` |
| 4.9 | Delik grubu (kare / daire içinde yakın delikler): ilk delik referanstan; **düzenli** desende delikten deliğe zincir / dizi, **düzensiz** öbekte her delik grubun referans deliğinden paralel (iki delik arası mesafe kendi içinde önemli: ayrı zımbalar); kalabalıksa detayda, değilse parça üzerinde; aynı desenler bir kez "3x 70". Düzensiz öbekte her delik referanstan. | Freze mantığı: 0→A→B. | K | `_delik_gruplari`, `_duzenli_grup`, `_grup_imzasi` |
| 4.15 | **Delik koordinat tablosu yalnız çok delikli görünüşte** (20 ve üstü delik): konum ölçüsü yerine tablo (NO, X, Y, Ø; sıfır görünüşün sol alt köşesi), çap etiketi ve merkez işaretleri kalır. 4 delik ya da dağınık 3-4'lük gruplar normal ölçülenir. | Kullanıcı: "çok çoklu delikte koordinat koyalım; 4'er 3'er dağınık olursa hayır". Çok delikte ölçü hatları okunmaz olur; tablo lazer / zımba programıyla aynı dili konuşur. | K (web 10.3) | `KOORDINAT_ESIK`, `tablo_gorunusleri`, `koordinat_tablolari` |
| 4.10 | Aynı eleman bir kez: "6x Ø45", "9x SLOT 6", "4x 30°". | Tekrar bilgi eklemez. | K; CH s.7, s.40 | `cap_olculeri`, slot dedupe, `aci_olculeri` |
| 4.11 | **İki aşama**: önce biçim ölçüleri (gabari, kademe, kanat), sonra konum ölçüleri (delik merkezleri). Zincirin bir ucu ölçüsüz (gabari kapatır). | | RC s.5–8, s.12 | `dxf_komponent` sırası, `_gabari_yolu_ayir` |
| 4.12 | Gizli (kesik) çizgiye ölçü verilmez; özellik görünür olduğu görünüşte ölçülür. Silindirik biçim merkezine, prizmatik biçim yüzeyine göre konumlanır. | | RC s.9, s.10 | `DELIK_GOR` (ilk görünen görünüş), `konum_plani` |
| 4.14 | **Aynı hiza sayılan seviyeler**: datumdan ölçülerde birbirine 0,5 mm içinde (toplam 1 mm) kalan seviyeler (104,2 / 104,3 / 104,5 / 104,6'daki dört delik) tek sıradır; ortalamaya en yakın GERÇEK değer yazılır, öbürleri ona bağlanır; başlıkta "! MODEL KONTROL: ÜST düşey 104,2..104,6 arası 4 özellik aynı hizada sayıldı (104,5)". Ölçü uydurulmaz, kullanıcı modeli denetler. | Çizim gürültüsü dört ayrı ölçü değildir; uyarı, yanlış sonucu önler. | K (YANLIŞ SONUÇ ASLA) | `konum_plani`, `YAKIN_SEVIYE_MM`, `PLAN_UYARI` |
| 4.13 | Gereksiz ölçü yok, önemli konum eksiksiz: her delik / slot / kesik / kanat / açı için konum + gereken özel ölçü; artık, tekrar, iç yüz / radüs teğeti ölçüsü yok. | | K; CH s.39–40 | `konum_plani`, `sac_kesit`, raporlar |

## 5. Delik, slot, açı, pah, sac

| # | Kural | Gerekçe | Kaynak | Kod |
|---|-------|---------|--------|-----|
| 5.1 | Ø etiketi "n x Ø" deliğin yanında, kılavuz **radyal** (uzantısı merkezden geçer); R tek oklu. | | CH s.5, s.9 | `_cap_koy` (`add_diameter_dim`, `add_radius_dim`) |
| 5.2 | Slot / anahtar deliği: konum **yay merkezinden**; slot boyu merkezler arası + R (K). Sığmazsa not "n x SLOT genişlik x boy". | Kutu kenarına ölçü teğet noktasına ölçüdür. | K (CH s.5 dış boy + genişlik verir; K önde) | `tel_slotlari`, `_buyuk_yay`, `slot_notlari` |
| 5.3 | Sacta delik / kesik pres ya da lazer: **konum + özel ölçü**; özel şekilde (pencere, anahtar deliği) yalnız konum ve ana eksen. Çok abartmadan. | Biçim lazer DXF'inden gelir. | K | `konum_plani` (pencere merkez) |
| 5.4 | Açı: eğik kenar / kanat açısı yay ölçüsüyle, yay küçük açıyı tarar; hepsi aynıysa bir kez "n x açı"; sacın iki yüzü **tek duvar**; yazıdan kısa kenara açı yok. | | K; CH s.4 | `_egik_kenarlar` (`AYNI_DUVAR_MM`), `_aci_dogru` |
| 5.5 | Pah "a x 45°" kılavuzla; açısı verilmez (bacakları verilir). | | CH s.4; K | `pah_notlari` |
| 5.6 | Bükümlü sac: her kanat **dıştan dışa, sanal keskin köşeye** (ABKANT tablosuyla aynı, K-faktöründen bağımsız); kanatlar tek hizada; kalınlık profilde "t 1,5"; iç yüz / radüs teğeti ölçülmez; ayna kanatlarda <1 mm fark "MODEL KONTROL". | Abkant operatörü dış ölçüyle çalışır. | K; CH s.2 (sanal köşe) | `sac_duvarlari`, `kanat_olculeri`, `_hizali_diz`, `kanat_uyarilari` |

## 6. Detay görünüşü – karışıklık detaya taşınır

| # | Kural | Gerekçe | Kaynak | Kod |
|---|-------|---------|--------|-----|
| 6.1 | Ana görünüşte yalnız **temiz** ölçüler kalır: uzatma çizgisi iki yanda da şekil kesen, zincir halkası rakamın yarısından kısa (KISA_HALKA) ya da dışarıda yeri olmayan ölçünün bölgesi ayrılır. | Uzman ressam kalabalık ucu tıkıştırmaz. | K | `konum_olculeri` (deneme geçişi), `yerel`, `_kisa` |
| 6.2 | Bölge = karışık özelliklerin dikdörtgeni; her yönde parça kenarına yakınsa kenara uzar (ince parçada boydan boya bant, levhada köşe); kesişenler birleşir; detaya sığmayan iki yönde bölünür; en çok 6 bölge. | Bütün parçayı kaplayan detay detay değildir. | K; CH s.20, s.41 | `bolge_sec`, `DETAY_BANT_EN`, `BOLGE_UC` |
| 6.3 | Bölgedeki konumlar ana görünüşten çıkar, detayda referanstan **zincirle**: bölge datum kenarını içeriyorsa kenar, içermiyorsa ana görünüşte ölçülü **bağlantı** özelliği kalır ve referans olur (tek referans bozulmaz). İki ucu bölgede olan slot boyu / grup içi ölçüler de detayda. | | K | `bolge_plani`, `bolge_detaylari` |
| 6.4 | Ana görünüşte ince çerçeve (yazılardan kaçar) + harf; detay başlığı "DETAY D (2,5:1)"; büyütme 2 / 2,5 / 4 / 5 / 10 (ISO 5455), en kısa ölçü okunacak kadar; detaydaki rakam **gerçek değer** (dimlfac). | | CH s.20, s.41, s.39 | `_bant_detayi_kur`, `_yazidan_kacan_kutu`, `_harf_koy`, `_EK_OVR["dimlfac"]` |
| 6.5 | İki geçiş: önce deneme (temiz yerleşmeyenler bulunur, deneme silinir), sonra bölgesiz ana görünüş + detaylar. Tek tek kaybolan ölçü için daire detayı (eski yol) yedektir. | | K | `_varlik_geri_al`, `detay_gorunusleri` |
| 6.6 | Sığmayan ölçü **atılmaz**, sırayla: öbür yan → özelliğin yanı → referanstan paralel → detay → slot notu. `yer_yok` 0 olmalı. | | K | `_yanina_koy`, `_ara_yerlestir`, `slot_notlari` |
| 6.7 | Paftada detaylar izdüşüm ızgarasına girmez; görünüş öbeğinin **altına** okuma sırasıyla dizilir; altta yer yoksa kâğıdın başka boş yeri; antete değmez. | | K | `pf4_pafta._serbest_yerlestir` |
| 6.8 | Aynı hizada iki bölgeye düşen özelliklerin ölçüsü **bölünür**: bant içi kopyası detaya, bant dışı "dik"ler ana planda kalır. | İki slotlu sacda ölçü ne detaya ne ana görünüşe giriyordu. | K | `bolge_plani` |
| 6.9 | Daire detayı tavanı görünüşün %12'si **ama en az 12 yazı boyu**; geniş öbekte (uçlar ayrı) en küçük büyütmeyle gevşek tavan (%50 / 20 yazı boyu). Küçük parçada detay kurulamayıp ölçü düşmez. | Sığmayan ölçü atılmaz (6.6). | K | `_detay_kur`, `DETAY_EN_AZ_YARI`, `DETAY_EN_GEVSEK` |
| 6.10 | Detayda yer bulamayan ölçü için **takas**: uzatma yolundaki (uçların sütun / satır koridoru) önce konmuş detay ölçüleri geçici kaldırılır, ölçü konur, kaldırılanlar yeniden yerleşir; biri yer bulamazsa her şey geri alınır. Uçları ayrı sırada olan ölçüde hat uçlardan birinin yanında (arada) da denenir. | Önce gelen önce yer buluyor, uzun uzatma çizgili ölçü hep sonda kalıyordu. | K | `_detay_takas`, `_detay_olcu` |

## 7. Çakışma – sıfır

| # | Kural | Gerekçe | Kaynak | Kod |
|---|-------|---------|--------|-----|
| 7.1 | Yazı yazıya, yazı **hiçbir** çizgiye (kontur, gizli, eksen, ölçü, uzatma, kılavuz, açı yayı) binmez; çizgi çizginin üstüne binmez. | | K; CH s.9 | `_cakisiyor`, `_cizgi_kesiyor`, `_kendi_ustunde`, `_ust_uste`, `_dim_yaziya_degiyor` |
| 7.2 | Her yazı (etiket, harf, Ø, açı, girinti derinliği) konmadan önce yeri ölçülür; yer yoksa alternatif yer, en son bir sonraki adım (6.6). | | K | `_harf_koy`, `gorunus_etiketi`, `_cap_koy`, `girinti_olculeri` |
| 7.3 | Bağımsız denetim: `test/cizim_cakisma_denetimi.py` (yazı-yazı, kontur üstünde, çizgi üstünde) 4 modelde 371 resimde 0. | Yanılan denetim olmayandan kötüdür; kendini de sınar. | K | `--kendini-dene` |

## 8. PDF (pafta)

| # | Kural | Gerekçe | Kaynak | Kod |
|---|-------|---------|--------|-----|
| 8.1 | **DXF 1:1 çalışma dosyasıdır**, ölçü ondan alınır. **PDF okumak içindir**, üstünden ölçü alınmaz; DXF'in birebir kopyası olmak zorunda değildir. | | K | `pafta_denetimi.py` (1:1 değişmez) |
| 8.2 | Kâğıt **her zaman yatay**; dikey yalnız açıkça istenirse ("A3-D"). | Alışılmış pafta, dosyalama. | K | `yerlesim`, `pafta_kur` |
| 8.2a | **Ana resim büyük kalır**: detaylar 1. sayfada ölçeği düşürüyorsa 2. sayfaya ("DETAYLAR", aynı PDF, kendi ölçeğinde); gerekirse daha çok sayfa. | Karınca duası yerine çok sayfa. | K | `tam_kagit_plani(serbest_sayfa2)`, `_detay_sayfalari`, `bas` (PdfPages) |
| 8.3 | Çizim kâğıdın ~%70–75'ini doldurur; ölçek serbest ve ara değerde (1:9, 1:11, 1:14 …) — sığan **en büyük** ölçek; 1-2-5 serisine zorlanmaz. | Küçük ölçek okunmaz. | K (ISO 5455 esnetildi) | `KUCULTME`, `tam_kagit_plani` |
| 8.4 | Antet alanına çizim girmez: Pi3D anteti çizilirken kutu alçak (A3'te sağ alt 150 x 40); firma kendi antetini yapıştıracaksa 150 x 100 boş. Dolu pencereler antete ve çerçeveye değmez. Görünüşler yakın (arası ≤ 15 mm). | Kullanıcı: "antet yüksek gelmiş; normal antette bu yerleşim mümkün". | K | `ARA_EN_COK`, `antet_kutusu`, `ANTET_BOY_PI3D` |
| 8.7 | **1. sayfa dağılmaz**: ÖN + bir yan (SAĞ, yoksa SOL) + bir üst / alt + kesit birlikte izdüşüm düzeninde kalır; yalnız ekstra görünüşler (ARKA, ikinci yan, ikinci üst / alt) yazı küçük kalıyorsa ve ana resim ≥ 1,3 kat büyüyorsa 2. sayfaya gider, orada tek sırada resimdeki hizada, detaylar altına. Bilgi bloğu ızgaranın boş hücresine düşüyorsa orada, yeni satır / sütun açıyorsa serbest pencere. | Kullanıcı: "böyle dağınık çizim yapılmaz; arka ve sağ aynı düzeyde olmalı". | K | `_ekstra_gorunusler`, `_gorunus_sirasi_yerlestir`, `cok_pencere_plani` |
| 8.5 | Pencere sınırı yazıyı **ölçerek** (MTEXT tek satır, ölçü bloğu içindeki de, Türkçe harf noktaları) kapsar; yazı kırpılmaz. | "6x Ø45" kırpılıyordu, "ÜST" "UST" çıkıyordu. | K | `_varlik_kutulari`, `_mtext_kutusu` |
| 8.6 | Yazılar okunur: PDF'te yazı ~1 mm altına düşerse ölçek / yerleşim gözden geçirilir. | | K | `yazi_mm` raporu |

## 9. Kitapta olup programda (henüz) olmayanlar

Bilinçli olarak yapılmayan ya da sonraya bırakılanlar; gerekçesiyle:

- **Kümülatif (tek raylı) ölçü** (CH s.8): kullanıcı istemiyor ("rollform
  ayarı için olur, ölçülendirme olmaz"). Yapılmaz.
- **Delik koordinat tablosu** (CH s.8): çok delikli sacda seçenek olabilir;
  şimdilik ızgara bölgesi + lazer DXF'i yeterli. Aday.
- **Gabari "(L)" parantezli yardımcı ölçü** (CH s.40): zincirin son halkası
  verilmediği için gabari artık ölçü değildir; parantez gerekmez.
- **Slot dış boy + genişlik** (CH s.5): kullanıcı merkezler arası + R
  istedi; sığmayan slotta not genişlik x dış boy verir.
- **Toleranslar, yüzey durumu, geometrik tolerans, ISO 2768 notu**
  (CH s.16–38): detay resminde şimdilik yok; antete genel tolerans notu
  aday.
- **Kesit (A-A) tarama** yalnız isteğe bağlı kesitte; bükümlü sacda profil
  görünüşü kesit yerine kullanılır.

## 10. Web araştırması (02.10.2026) - kendi cümlelerimizle

Kullanıcı: "web'ten 2D AutoCAD ölçülü resimler araştır, çok farklı kurallar
ve düzenler görebilirsin." Arama özetleri okundu (imalatçı rehberleri,
ISO 129-1 / 5456-2 / 128-3, ASME Y14.3, forumlar); metin kopyalanmadı.

| # | Bulunan kural (özet) | Bizde |
|---|---|---|
| 10.1 | Sacta ana datum deliklerin açıldığı büyük düz yüz; en / boy kenarları ikinci ve üçüncü datum. | Uygulandı (3.1, 3.2). |
| 10.2 | Delik deseninde ilk delik iki kenardan, öbürleri ilk delikten; iki delik arası mesafe işlevselse doğrudan yazılır, tolerans yazılan ölçüye uygulanır. | Uygulandı (4.9: düzenli zincir / dizi, düzensiz öbekte referans delikten paralel). |
| 10.3 | Çok delikli lazer / zımba parçada koordinat (ordinat) ölçülendirme: sol alt köşe 0,0, hata birikmez; delik tablosu (X, Y, takım, adet). | Tek hatta rakam dizme yok (4.2). Delik tablosu yalnız çok delikli görünüşte (4.15), kullanıcı onayıyla. |
| 10.4 | Görünüş sayısı gereken en az (2-3); gizli çizgi gerektirmeyen görünüşler seçilir; eğik yüz için yardımcı görünüş. | Uygulandı (2.2: otomatik seçim, ölçüsüz görünüş çizilmez; 2.12 yardımcı görünüş). |
| 10.5 | Ana görünüş en çok bilgi veren bakış, parça çalışma / montaj konumunda (ISO 5456-2); 1. açı yerleşimi. | Uygulandı (2.1, 2.3, 2.9, 2.10). |
| 10.6 | Kesit iki uçta aynı büyük harf (A-A), kâğıdın altından okunur; standart yerinde olmayan görünüşe harf + bakış oku. | Kesit uygulandı (2.6). Sütun düzeninde ARKA adıyla işaretli (ad yazılı), ok konmuyor. |
| 10.7 | İlk ölçü hattı konturdan 7-10 mm, uzatma taşması 1,5-2 mm, konturla uzatma arasında boşluk. | Uygulandı (1.x, ANAYASA). |
| 10.8 | Delik daire göründüğü görünüşte, merkez çizgisine ölçülenir; gizli çizgiye ölçü verilmez. | Uygulandı (4.12). |
| 10.9 | Sac BÜKÜLMÜŞ hâliyle ölçülenir; açınım yalnız istenirse, açınım gabarisi referans (parantez); açınımda büküm çizgileri, yön, iç büküm yarıçapı; iki büküm arası sanal keskin köşeye. | Bükümlü hâl + sanal köşe uygulandı (5.6). Açınımda iç yarıçap notu ve parantezli gabari ADAY. |
| 10.10 | DFM: delik kenara en az t (1,5-2t), büküme en az 2,5t + R; delikler arası en az 2t / 3Ø; eşit aralıklı delikler "n x p". | "n x p" uygulandı (4.8). Kenara / büküme çok yakın delik için "MODEL KONTROL" uyarısı ADAY. |
