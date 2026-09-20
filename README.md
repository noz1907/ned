# PiFikstur Maker

STEP montajından kaynak fikstürü öneren araç seti. Her adım **karar vermez, önerir**;
onay kullanıcıdadır.

| adım | dosya | ne yapar |
|------|-------|----------|
| 1 | `pf1_referans.py` / `pf_gui.py` | grubu seçer, 6 yönü puanlar, datum A ve 3 nokta önerir → `referans_*.json` |
| 2 | `pf2_fikstur.py` | seçilen grup için 3-2-1 kaynak fikstürü üretir → STEP + DXF + JSON + rapor |

## Kurulum

```
pip install -r requirements.txt        # cadquery (OCP), ezdxf, matplotlib
```

## Kullanım

```
python pf1_referans.py ornek/parca.stp --liste
python pf1_referans.py ornek/parca.stp --grup G03            # referans.json yazar
python pf2_fikstur.py  ornek/parca.stp --referans ornek/referans_G03.json --yon +Y --png
```

`pf2_fikstur.py` seçenekleri:

- `--referans` : adım 1 JSON'u (grup ve yön buradan alınır); `--grup G03` / `--parca 7` ile de seçilebilir
- `--yon +Y` : yukarı yönü zorla (`--yon=-Y` biçimi eksi yönler için gerekir)
- `--png` : 2B ön izleme PNG'leri (tam boy, kapak ucu, itme klempi yakın plan)
- `--hizli` : DXF'te parçayı sınır kutusu olarak çiz (büyük parçalarda hız)
- `--param p.json` : `PARAM` sözlüğündeki ölçüleri (dayama yüksekliği, taban kalınlığı, ...) üzerine yaz
- `-o` : çıktı ön eki (varsayılan `fikstur_<grup>`)

## Fikstür mantığı (adım 2)

Fikstür koordinatları: **+Z yukarı, +X parça boyu, taban plakası üst yüzü Z=0.**
Parça, seçilen "yukarı" yönü +Z olacak şekilde döndürülür; JSON'da dönüşüm matrisi ve
öteleme yazılır, rapordaki her basma noktası ayrıca orijinal parça koordinatına çevrilir.

Sınıflandırma: en büyük hacimli katı **ana gövde**, adı `Kehlnaht/kaynak/weld` olan (ya da
adsız ve ana gövdenin %1'inden küçük) katılar **kaynak dikişi**, kalanlar **ek parça**dır.

| eleman | görev |
|--------|-------|
| `DAYAMA_A_nn` | datum A: ana gövde alt yüzü; ≤500 mm aralıkla, kaynak dikişlerine 60 mm yaklaşmadan; her dayamanın gerçek temas alanı ölçülür (web delik/slotuna denk gelirse kaydırılır) |
| `DAYAMA_B_nn` | datum B: -Y yan yüz, 2 nokta |
| `YUVA_C_nn` | datum C + ek parça yuvası: arka duvar (X), raf (Z), -Y kulak (Y) |
| `KLEMP_DIKEY_nn` | köprü ayaklı dikey klemp, ana gövdenin üst yüzlerine (dudaklara) basar |
| `KLEMP_YATAY_nn` | yan dayamaların karşısından -Y'ye iter |
| `KLEMP_ITME_nn` | parça serbest ucundan datum C'ye doğru eksenel iter (plaka ayak) |
| `KLEMP_*_KAPAK_nn` | ek parçayı rafa ve -Y kulağa bastırır |
| `TABAN_PLAKA`, `ISKELET_*` | 15 mm taban plakası + 60×40×3 kutu profil iskelet, 6×Ø13 montaj deliği |

Kontroller (JSON `kontrol` ve rapor): fikstür–parça ve fikstür–fikstür **çakışma** (boolean
kesişim hacmi), her konumlandırıcı/klemp ayağının hedefe **temas**ı (mesafe < 0,05 mm),
her kaynak dikişi için +Z etrafında 60° koni içinde **torç erişimi** (fikstür tek başına ve
parçanın kendi gölgesiyle birlikte), dar oturma yüzü **uyarı**sı.

Klempler zarf modelidir (GH-201-B dikey / GH-304-CM yatay sınıfı); üretimde tedarikçi
modeliyle değiştirilir.

## Örnek: `ornek/parca.stp` – G03 (C-Profil Teleskop + Dachplatte, 9,53 kg)

`ornek/cikti/` altında hazır çıktı: `fikstur_G03.step`, `.dxf`, `.json`, `.md`, `.png`.

Adım 1 puanlamasında -Y ve +Y eşit çıkar (0,5094 / 0,5092). Adım 2 **+Y** ile üretildi çünkü
-Y'de parça 3,5 mm'lik dudaklarına oturur (araç uyarı verir) ve kanal içindeki köşe
kaynakları aşağı bakar; +Y'de parça 91 mm'lik web'i üzerine oturur ve üç dikiş de kanal
ağzından üstten erişilebilir. Adım 1'in -Y için önerdiği P1 noktası (X=-43,9) dudağın
altında kaldığı için zaten ulaşılamazdır.

`ornek/fikstur_3D_gercek_solid.step`: mevcut gerçek fikstürün kaba rekonstrüksiyonu
(referans amaçlı, adım 2 bunu kullanmaz).
