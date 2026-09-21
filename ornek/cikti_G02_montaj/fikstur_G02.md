# G02 kaynak fikstürü – tasarım raporu

Kaynak dosya: `/home/user/ned/ornek/parca.stp`  |  yön: **-Y** yukarı  |  parça: 0.38 kg, 13 katı (2 kaynak dikişi)

Fikstür koordinatları: +Z yukarı, +X parça boyu, taban plakası üst yüzü Z=0.

Parça zarfı (fikstürde): X 149.0..326.0, Y -50.0..51.0, Z 31.4..56.0

## Konumlandırma (3-2-1)

- **Datum A (Z, 3+ nokta):** ana gövde alt yüzü, alan 7219 mm², dayama üstü Z=40.00; dayama X konumları: [237.5]
- **Datum B (Y, 2 nokta):** -Y yan yüz, yan dayamalar DAYAMA_B_01/02
- **Datum C (X):** ayrı eksenel dayama gerekmedi.

İç içe geçen parçalar: 09.020.000.05 Rillenkugellager DIN, 09.020.000.05 Rillenkugellager DIN, 09.020.000.05 Rillenkugellager DIN, 09.020.000.05 Rillenkugellager DIN, M8 Somun, M8 Somun, 09.020.000.06 Unterlegscheibe 8,4x, 09.020.000.06 Unterlegscheibe 8,4x, 09.020.000.06 Unterlegscheibe 8,4x, 09.020.000.06 Unterlegscheibe 8,4x. Bunlar ana gövdenin içine oturduğu için Y ve Z yönünde ana gövde tarafından konumlanır; fikstür yalnız eksenel konumu ve taşan ucu tutar.

## Elemanlar

| # | ad | tip | boyut (X×Y×Z) | kg | malzeme | not |
|---|----|-----|---------------|----|---------|-----|
| 1 | DAYAMA_A_01 | dayama_A | 49×80×40 | 1.21 | C45 sertleştirilmiş | temas alanı 0 mm² (0 %) |
| 2 | DAYAMA_B_01 | dayama_B | 40×30×44 | 0.40 | C45 sertleştirilmiş | temas yüzü Y=-50.00, Z 40.0..43.5 |
| 3 | DAYAMA_B_02 | dayama_B | 40×30×44 | 0.40 | C45 sertleştirilmiş | temas yüzü Y=-50.00, Z 40.0..43.5 |
| 4 | KLEMP_YATAY_01 | klemp_yatay | 50×135×155 | 1.44 | GH-304-CM sınıfı (St) | mil ekseni Z=45.0, itme yönü -Y, yükseltici 15 mm |
| 5 | KLEMP_YATAY_02 | klemp_yatay | 50×135×155 | 1.44 | GH-304-CM sınıfı (St) | mil ekseni Z=45.0, itme yönü -Y, yükseltici 15 mm |
| 6 | TABAN_PLAKA | taban | 390×500×15 | 22.87 | S355JR | 390 x 500 x 15 mm, 6 x Ø13 montaj deliği |
| 7 | ISKELET_BOY_01 | iskelet | 350×60×40 | 1.55 | S235JR kutu profil | 60x40x3 - L=350 |
| 8 | ISKELET_BOY_02 | iskelet | 350×60×40 | 1.55 | S235JR kutu profil | 60x40x3 - L=350 |
| 9 | ISKELET_EN_01 | iskelet | 60×320×40 | 1.42 | S235JR kutu profil | 60x40x3 - L=320 |
| 10 | ISKELET_EN_02 | iskelet | 60×320×40 | 1.42 | S235JR kutu profil | 60x40x3 - L=320 |
| 11 | ISKELET_EN_03 | iskelet | 60×320×40 | 1.42 | S235JR kutu profil | 60x40x3 - L=320 |

Fikstür toplam: **35.1 kg**

## Temas / basma noktaları (fikstür → parça koordinatı)

- DAYAMA_A_01: F(237.5, 0.0, 40.0) → P(-5.68, -57.32, 2795.5)
- DAYAMA_B_01: F(172.5, -50.0, 41.8) → P(-70.68, -59.07, 2745.5)
- DAYAMA_B_02: F(302.5, -50.0, 41.8) → P(59.32, -59.07, 2745.5)
- KLEMP_YATAY_01: F(202.5, 50.0, 45.0) → P(-40.68, -62.32, 2845.5)
- KLEMP_YATAY_02: F(272.5, 50.0, 45.0) → P(29.32, -62.32, 2845.5)

## Kontroller

- Çakışma (fikstür–parça, fikstür–fikstür): 0 adet
- Temas DAYAMA_A_01: 0.0 mm ✓
- Temas DAYAMA_B_01: 0.0 mm ✓
- Temas DAYAMA_B_02: 0.0 mm ✓
- Temas KLEMP_YATAY_01: 0.0 mm ✓
- Temas KLEMP_YATAY_02: 0.0 mm ✓
- Kaynak erişimi M8x16 Anahtar Basli Civata @F(163.3, -5.0, 42.4): yalnız fikstür 25/25, yalnız parça 1/25, birlikte 1/25 yön açık (60° koni) ✓
- Kaynak erişimi M8x16 Anahtar Basli Civata @F(311.8, -5.0, 42.4): yalnız fikstür 25/25, yalnız parça 1/25, birlikte 1/25 yön açık (60° koni) ✓

**SONUÇ: GEÇTİ**

## Notlar

- Klempler zarf modelidir (GH-201-B / GH-304-CM sınıfı); üretimde tedarikçi modeliyle değiştirilir.
- Dayamalar altından M8 ile taban plakasına bağlanır (taban Ø9 delik, dayama M8 diş).
- Kapak yuvası -Y kulağı datumdur; +Y tarafı yatay klemple itilir (plaka genişlik toleransı).
- Kaynak dikişlerine 60 mm'den yakın eleman yerleştirilmemiştir; torç kanal içine üstten girer.
