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
