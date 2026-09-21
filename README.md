# PiFikstur Maker

STEP montajından **kaynak veya montaj fikstürü** öneren araç seti. Parça sayısı
sınırlı değildir (2, 3, N parça); seçim, yönlendirme ve XYZ referans noktaları
kullanıcı onayından geçer. Araçlar **karar vermez, önerir**.

| adım | dosya | ne yapar |
|------|-------|----------|
| 1 | `pf1_referans.py` / `pf_gui.py` | parçayı/grubu seçer, 6 yönü puanlar, datum A ve 3 nokta önerir |
| 2 | `pf2_fikstur.py` | seçilen parçalar için 3-2-1 fikstürü üretir, kontrol eder, onay paketi yazar |

## Kurulum

```
pip install -r requirements.txt        # cadquery (OCP), ezdxf, matplotlib
```

## İş akışı

```
# 1) neler var?
python pf1_referans.py ornek/parca.stp --liste

# 2) fikstürü üret (ilk öneri)
python pf2_fikstur.py ornek/parca.stp --sec "0,/DESTEK_SACi/,G03" --yon=-Y --png

# 3) fikstur_*_onay.png ve fikstur_*_onay.json dosyalarına bak,
#    gerekirse istasyon X konumlarını düzenle, "onay": true yap

# 4) onaylanmış konumlarla tekrar üret
python pf2_fikstur.py ornek/parca.stp --sec "0,/DESTEK_SACi/,G03" --onay fikstur_..._onay.json
```

### Parça seçimi (`--sec`)

Virgülle ayrılmış jetonlar, istediğiniz kadar:

| jeton | anlamı |
|-------|--------|
| `G03` | temas gruplama ile bulunan 3. grubun tüm katıları |
| `0` | 0 numaralı katı (`--liste` çıktısındaki sıra) |
| `/DESTEK_SACi/` | adı bu ifadeyle eşleşen tüm katılar (büyük/küçük harf duyarsız) |

Örnek: `--sec "0,/DESTEK_SACi/,G03"` → P1 gövde sacı + onu teleskopa bağlayan
10 kaynak dikişi + G03 teleskop grubu = 16 katı.

### Diğer seçenekler

- `--yon +Y` : yukarı yönü zorla (eksi yönler için `--yon=-Y` yazımı gerekir)
- `--onay dosya.json` : onaylanmış istasyon konumlarını ve yönü kullan
- `--mod kaynak|montaj` : kaynak dikişlerine torç erişimi / parça arayüzlerine takım erişimi
- `--referans` : ADIM 1 JSON'u (grup ve yön buradan alınır)
- `--png` : 2B ön izlemeler (tam boy, uç yakın plan, kaynak istasyonu yakın planı)
- `--hizli` : DXF'te parçayı sınır kutusu olarak çiz (büyük parçalarda hız)
- `--param p.json` : `PARAM` sözlüğündeki ölçüleri üzerine yaz
- `-o` : çıktı ön eki

## Çıktılar

| dosya | içerik |
|-------|--------|
| `<o>.step` / `.stp` | fikstür + parça, adlandırılmış montaj ağacı |
| `<o>.dxf` | üst/ön/yan görünüş (HLR), ölçüler, eleman listesi, `REFERANS` katmanında numaralı temas noktaları |
| `<o>_onay.png` | **parça üzerinde numaralı XYZ referans/temas noktaları** (tipine göre renkli) |
| `<o>_onay.json` | aynı noktaların fikstür ve orijinal parça koordinatları + düzenlenebilir `istasyon` listesi |
| `<o>.json` | eleman kutuları, malzemeler, kontrol sonuçları, kullanılan parametreler |
| `<o>.md` | okunabilir tasarım raporu |
| `<o>.png` | 2B ön izleme |

## Fikstür mantığı

Fikstür koordinatları: **+Z yukarı, +X parça boyu, taban plakası üst yüzü Z=0.**
Parça, seçilen "yukarı" yönü +Z olacak şekilde döndürülür; dönüşüm matrisi ve
öteleme JSON'a yazılır, her temas noktası ayrıca orijinal parça koordinatına çevrilir.

**Sınıflandırma.** En büyük hacimli katı *ana gövde*; adı `Kehlnaht/kaynak/weld`
olan (ya da adsız ve ana gövdenin %1'inden küçük) katılar *dikiş*; kalanlar *ek
parça*. Ek parçalar ikiye ayrılır: ana gövdenin içinden geçen **iç içe** parçalar
(ör. runge içindeki teleskop) ve ucuna oturan **uç plakaları**.

| eleman | görev |
|--------|-------|
| `DAYAMA_A_nn` | datum A: ana gövde alt yüzü; gerçek temas alanı ölçülür, delik/slota denk gelirse kaydırılır |
| `DAYAMA_A_UC_nn` | iç içe parçanın ana gövdeden taşan ucunun altı |
| `DAYAMA_B_nn` | datum B: -Y yan yüz; yüzey boolean kesişimle bulunur, en dışta ana gövde yoksa kaydırılır |
| `DAYAMA_C_nn` | datum C: ana gövdenin uç yüzü; iç içe parça **üstten açık çataldan** geçer |
| `DAYAMA_C_PLAKA_nn` | uç plakasının dikişsiz Y bantlarında eksenel post + plaka altı raf; postun üstü torç konisini kesmeyecek şekilde sınırlanır |
| `KLEMP_DIKEY_nn` | köprü ayaklı dikey klemp; ayak izinin dolu malzemeye bastığı yer aranır |
| `KLEMP_YATAY_nn` | yan dayamaların karşısından -Y'ye iter |
| `KLEMP_ITME_nn` | eksenel itme: parçayı datum C'ye bastırır |
| `TABAN_PLAKA`, `ISKELET_*` | taban plakası + kutu profil iskelet, Ø13 montaj delikleri |

**Kontroller** (JSON `kontrol` ve rapor):

- **Çakışma**: fikstür–parça ve fikstür–fikstür boolean kesişim hacmi, 0 olmalı.
- **Temas**: her konumlandırıcı/klemp ayağının hedefe mesafesi < 0,05 mm.
- **Erişim**: her dikiş (kaynak modu) veya parça arayüzü (montaj modu) için +Z
  etrafında 60° koni içinde 25 yön taranır. Fikstür yönlerin yarısından fazlasını
  kapatmamalı ve parçanın kendi gölgesinden arta kalan erişimin en az yarısını
  korumalı. Parçanın kendi gölgesi ayrıca raporlanır.
- **Uyarılar**: dar oturma yüzü, basma yeri bulunamayan klemp vb.

Klempler zarf modelidir (GH-201-B dikey / GH-304-CM yatay sınıfı); üretimde
tedarikçi modeliyle değiştirilir. Kaynak/montaj makinesi üretilmez, yalnız fikstür.

## Örnekler

### `ornek/cikti/` — G03 tek başına (2 parça + 3 dikiş, 9,53 kg)

C-Profil Teleskop + Dachplatte. `--yon +Y`. Adım 1 puanlamasında -Y ve +Y eşit
çıkar; +Y seçildi çünkü -Y'de parça 3,5 mm'lik dudaklarına oturur (araç uyarı
verir) ve kanal içindeki köşe kaynakları aşağı bakar.

### `ornek/cikti_P1_G03/` — P1 + G03 birleşimi (3 parça + 13 dikiş, 20,22 kg)

`--sec "0,/DESTEK_SACi/,G03" --yon=-Y`. Teleskop, runge C-profilinin içine 0,5 mm
boşlukla girer ve 5 istasyonda çift köşe dikişiyle (10 adet) bağlanır. Bu dikişler
parçanın -Y yüzünde olduğu için fikstürde **-Y yukarı** seçilir: parça 254 151 mm²
rungesırtına oturur, 10 dikişin tamamı 25/25 yönden erişilebilir.

Teleskop Y ve Z yönünde rungenin kendi içinde konumlanır (toplam boşluk ~2 mm);
fikstür yalnız eksenel konumu (uç plakası postları) ve taşan ucu tutar. Dikiş
aralığının daha sıkı olması isteniyorsa runge sırtından itme pimleri gerekir —
sırtta o istasyonlarda delik yoktur, tasarımcı kararıdır.

`ornek/fikstur_3D_gercek_solid.step`: mevcut gerçek fikstürün kaba
rekonstrüksiyonu (referans amaçlı, araç bunu kullanmaz).

---

# DXF -> 3D STEP dönüştürücü (`pfd_dxf2stp.py`)

Parça ya da fikstür fark etmeksizin bir DXF'i 3B katıya çevirir ve STEP yazar.
Kip, dosyaya bakılarak seçilir:

| kip | ne zaman | sonuç |
|-----|----------|-------|
| DOGRUDAN | DXF zaten 3B taşıyor (3DFACE / MESH / POLYFACE / Z'si değişen polyline) | birebir |
| EKSTRUZYON | tek 2B kontur + `--kalinlik` | birebir |
| KESISIM | hizalı 2-3 ortografik görünüş (ÖN/ÜST/SAĞ) | prizmatik parçalarda birebir |

```
python pfd_dxf2stp.py cizim.dxf --liste                  # ne gördüğünü yaz
python pfd_dxf2stp.py cizim.dxf                          # STEP üret
python pfd_dxf2stp.py cizim.dxf --kalinlik 15            # tek görünüş + kalınlık
python pfd_dxf2stp.py cizim.dxf --pencere x0,y0,x1,y1    # sayfanın bir bölgesi
python pfd_dxf2stp.py cizim.dxf --delik yok              # iç konturları delik sayma
```

## Nasıl çalışıyor

1. **Okuma.** ezdxf ile modelspace ve bloklar (iç içe INSERT'ler dahil) okunur;
   yay, daire, elips ve spline doğru parçalarına bölünür. Her DXF varlığı bir
   *atom* olarak saklanır.
2. **Yüz çıkarma.** Çizimin tamamı bir kerede kapalı yüzlere çevrilir
   (shapely `polygonize`). Gizli çizgi katmanları (`GIZLI`, `HIDDEN`, `DASHED`)
   kontur oluşturmaz. Sayfa çerçevesi ve grup çerçeveleri ayıklanır.
3. **Bölgeleme.** Birbirine değen yüzler tek bölgedir. Bu kural ölçekten
   bağımsızdır: ayrı görünüşlerin yüzleri değmez, bir görünüşün parçaları değer.
4. **Görünüş eşleme.** Aynı satırda duran ve yüksekliği tutan bölgeler ön-yan
   çifti, aynı sütunda duran ve genişliği tutan bölgeler ön-üst çiftidir.
   Görünüş adı yazısı (ON/ÜST/SAĞ/ALT/SOL/ARKA) varsa rol ondan alınır.
5. **3B kurma.** Her görünüş kendi ekseninde prizmaya süpürülür, prizmalar
   kesiştirilir. Dış sınıra değmeyen kapalı bölgeler delik sayılıp çıkarılır.
6. **Çıktı.** Adlandırılmış montaj olarak STEP, `_kontrol.png` (programın ne
   anladığı) ve `.json` (bölge, rol, ölçü, uyarı).

## Doğrulama: gidiş-dönüş testi

`ornek/dxf2stp/test_gidis_donus.py` bilinen bir katıdan üç görünüş üretir,
çeviriciyle geri kurar ve hacmi karşılaştırır.

| büyüklük | kaynak | kurulan |
|---|---|---|
| dış ölçü | 120 x 80 x 24 | 120 x 80 x 24 (birebir) |
| hacim | 212 521 mm³ | 223 433 mm³ (+%5,1) |

Fark, yöntemin bilinen sınırıdır: **her görünüşte arkasında malzeme kalan bir
cep**, siluetten geri kazanılamaz. Test parçasındaki 40x30x10 cep tam olarak bu
durumda. Delikler ve profil doğru çıkar, dış ölçüde hata yoktur.

## Gerçek örnek

`ornek/dxf2stp/fikstur_2xls.dxf` üç kuşak içerir: Kaynaklı Ürün, Kaynaklı
Fikstür, Fikstür Parçaları ve Dayamalar. Üçüncü kuşak `--pencere` ile alınıp
çevrildi (`parcalar_3d.step`): fikstür parçaları ve dayamalar tek tek katıya
döndü, ölçüleri 110x35x146, 50x15x700, 50x15x49 gibi.

## Sınırlar

- Her görünüşte gizlenen cep ve ada geri kazanılamaz (görsel kabuk üst sınırdır).
- İç kontur delik mi ada mı olduğu 2B'den kesin bilinemez; `--delik` ile seçilir.
- Eğik (eksenlere paralel olmayan) yüzeyler yalnız o yönde prizmatikse doğru çıkar.
- Sağ/sol görünüş ayna yönü çizim geleneğine bağlıdır; ölçü çatışması raporlanır.

## Renk kipi: her renk bir parça

Çizimde her parça ayrı renkle çiziliyorsa bu, hangi görünüşün hangi parçaya ait
olduğunu söyleyen en güvenilir bilgidir. Program bunu kendiliğinden kullanır
(`--renk auto`, üç veya daha çok renk varsa açılır):

1. Her renk **ayrı ayrı** polygonize edilir, üst üste çizilmiş parçalar karışmaz.
2. Bir rengin bölgeleri, çizimdeki görünüş yazısına (ÖN / SAĞ / ALT) göre gruplanır.
   Kesit görünüşünde malzeme kopuk olsa da (C profilin yandan görünüşü iki şerittir)
   aynı yazının altındakiler tek görünüş sayılır.
3. Aynı renk bir görünüşte birkaç kez geçiyorsa (parçanın iki kopyası) en büyük
   öbek alınır, kutu şişmez.
4. Nesne = renk. Görünüş eşlemesi için geometrik tahmine hiç gerek kalmaz.

Görünüş düzeni: **ÖN görünüş referanstır**, yanında SAĞ, altında ALT görünüş.

### `ornek/dxf2stp/fikstur_2a.dxf` sonucu

Kaynaklı üç parça + fikstür parçaları, on renk. Yedi nesne katıya döndü:

| nesne | ölçü (mm) | not |
|---|---|---|
| yeşil gövde sacı | 120 x 34,5 x 2480 | STEP'teki gerçek ölçüyle birebir |
| macenta teleskop | 195 x 50 x 1948 | doğru |
| üçüncü kaynak parçası | 92 x 37,4 x 700 | ALT görünüşte 2,4 mm çatışma |
| fikstür dayaması | 110 x 35 x 146 | |
| fikstür dayaması | 50 x 35 x 146 | |
| uzun dayama | 420 x 15 x 49 | çatışmasız |

Ölçü çatışmaları raporlanır; görünüşler arasında paylaşılan ölçü tutmuyorsa
program bunu gizlemez.

---

# STEP -> DXF ve ölçü (`pf3_olcu.py`)

Herhangi bir STEP dosyasından montaj ve komponent bazında DXF görünüşleri ve
ölçü tablosu üretir.

```
python pf3_olcu.py parca.stp --liste          # komponent listesi
python pf3_olcu.py parca.stp -o cikti         # DXF + tablo üret
python pf3_olcu.py parca.stp -o cikti --tek 01.050.000.01 --montaj-yok
                                              # yalnız tek komponentin çizimi
```

## Çizim kuralları

| katman | çizgi | kalınlık |
|--------|-------|----------|
| GORUNEN | düz | 0,10 mm |
| GIZLI | kesik | 0,10 mm |
| EKSEN | uzun-kısa | 0,10 mm |
| OLCU / YAZI | düz | 0,10 mm |

Görünen kenarla tam üst üste düşen gizli kenar çizilmez (görünen kazanır),
böylece görünüşler kesik çizgiyle dolmaz.

Ölçüler **milimetre**, birebir ölçek (`dimlfac = 1`). Yazı boyu parçaya göre
ölçeklenir, `max(boy, en, kalınlık) / 45`, en az 2,5 mm en çok 25 mm.

**Çap yalnız tam çember delikler için verilir.** Bir silindirik yüzeyin açısal
açıklığı toplanır; 360°'ye yakınsa delik, değilse kenar yuvarlamasıdır ve ayrı
radüs tablosunda yarıçap olarak listelenir. Bir delik CAD'de iki yarım silindire
bölünmüş olsa da eksen konumu aynı olduğu için tek delik sayılır.

Çizimde her delik grubunun çapı `124x Ø6.8`, her radüs grubu `4x R3`
biçiminde ölçülendirilir; delik merkezlerine merkez çizgisi konur.

**Yerleşim.** Ölçü çizgisi her zaman deliğin/yuvarlamanın merkezinden geçer
(`dimtofl = 1`); yazı, görünüşün üstünde her grup kendi satırına gelecek
biçimde dizilir, yeri `location` ile doğrudan verilir. Başlık bloğunun yeri
çizilen her şeyin üst sınırından hesaplanır, tablolar da sağ sınırdan; böylece
yazılar ne görünüşlerin ne de birbirinin üstüne biner.

Örnek çıktı: `ornek/olcu/ORNEK_01_050_000_01.dxf` (+ `.png` önizleme).
`ornek/olcu/onizle3.py` bir DXF'i gerçek yazı boyutlarıyla PNG'ye çevirir:
`python ornek/olcu/onizle3.py cizim.dxf onizleme.png`.

## Sınıflandırma

Civata, somun, pul, pim, perçin, yay, rulman, segman, saplama ve DIN/ISO/EN
numaralı parçalar **standart eleman** sayılır: çizim üretilmez, kod ve adet
listelenir. Kaynak dikişleri ayrı tutulur, parça sayılmaz.

## Sonraki adımlar (not alındı, henüz yapılmadı)

1. **BOM**: montaj çiziminde BOM tablosu, komponent çizimlerinde BOM poz
   numarası ve tanımı.
2. **Kesit görünüş**: iki delik veya iki form görünüşte üst üste binip anlamsız
   hale geldiğinde o görünüş yerine kesit almak.
