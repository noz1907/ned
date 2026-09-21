# 0+DESTEK_SACI+G03 kaynak fikstürü – tasarım raporu

Kaynak dosya: `/home/user/ned/ornek/parca.stp`  |  yön: **-Y** yukarı  |  parça: 20.22 kg, 16 katı (13 kaynak dikişi)

Fikstür koordinatları: +Z yukarı, +X parça boyu, taban plakası üst yüzü Z=0.

Parça zarfı (fikstürde): X 150.0..3069.5, Y -97.5..97.5, Z 40.0..91.5

## Konumlandırma (3-2-1)

- **Datum A (Z, 3+ nokta):** ana gövde alt yüzü, alan 254151 mm², dayama üstü Z=40.00; dayama X konumları: [268.0, 690.4, 1112.8, 1475.2, 2037.6, 2500.0]
- **Datum B (Y, 2 nokta):** -Y yan yüz, yan dayamalar DAYAMA_B_01/02
- **Datum C (X, 1 nokta):** DAYAMA_C_01 (ana gövde uç yüzü X=2630.00; 09.025.000.02 C-Profil T üstten açık çataldan geçer (boşluk 1.5 mm)); DAYAMA_C_PLAKA_01a (09.020.000.01 Dachplatte: iç yüz X=3061.50, Y -97.5..-73.0, raf Z=41.50, üst Z=69.3 (torç konisi)); DAYAMA_C_PLAKA_01b (09.020.000.01 Dachplatte: iç yüz X=3061.50, Y 73.0..97.5, raf Z=41.50, üst Z=69.3 (torç konisi)). Parçalar eksenel itme klempleriyle bu dayamalara bastırılır.

İç içe geçen parçalar: 09.025.000.02 C-Profil Teleskop. Bunlar ana gövdenin içine oturduğu için Y ve Z yönünde ana gövde tarafından konumlanır; fikstür yalnız eksenel konumu ve taşan ucu tutar.

## Elemanlar

| # | ad | tip | boyut (X×Y×Z) | kg | malzeme | not |
|---|----|-----|---------------|----|---------|-----|
| 1 | DAYAMA_A_01 | dayama_A | 60×80×40 | 1.48 | C45 sertleştirilmiş | temas alanı 4541 mm² (95 %) |
| 2 | DAYAMA_A_02 | dayama_A | 60×80×40 | 1.48 | C45 sertleştirilmiş | temas alanı 4551 mm² (95 %) |
| 3 | DAYAMA_A_03 | dayama_A | 60×80×40 | 1.48 | C45 sertleştirilmiş | temas alanı 4800 mm² (100 %) |
| 4 | DAYAMA_A_04 | dayama_A | 60×80×40 | 1.48 | C45 sertleştirilmiş | temas alanı 4800 mm² (100 %) |
| 5 | DAYAMA_A_05 | dayama_A | 60×80×40 | 1.48 | C45 sertleştirilmiş | temas alanı 4800 mm² (100 %) |
| 6 | DAYAMA_A_06 | dayama_A | 60×80×40 | 1.48 | C45 sertleştirilmiş | temas alanı 4646 mm² (97 %) |
| 7 | DAYAMA_B_01 | dayama_B | 40×30×73 | 0.67 | C45 sertleştirilmiş | temas yüzü Y=-60.00, Z 40.0..73.0 |
| 8 | DAYAMA_B_02 | dayama_B | 40×30×73 | 0.67 | C45 sertleştirilmiş | temas yüzü Y=-60.00, Z 40.0..73.0 |
| 9 | DAYAMA_C_01 | dayama_C | 40×160×75 | 2.71 | S355JR | ana gövde uç yüzü X=2630.00; 09.025.000.02 C-Profil T üstten açık çataldan geçer (boşluk 1.5 mm) |
| 10 | DAYAMA_A_UC_01a | dayama_A | 60×94×44 | 1.92 | C45 sertleştirilmiş | 09.025.000.02 C-Profil T taşan ucu, üst yüz Z=44.00 |
| 11 | DAYAMA_C_PLAKA_01a | yuva_C | 48×25×69 | 0.58 | S355JR | 09.020.000.01 Dachplatte: iç yüz X=3061.50, Y -97.5..-73.0, raf Z=41.50, üst Z=69.3 (torç konisi) |
| 12 | DAYAMA_C_PLAKA_01b | yuva_C | 48×25×69 | 0.58 | S355JR | 09.020.000.01 Dachplatte: iç yüz X=3061.50, Y 73.0..97.5, raf Z=41.50, üst Z=69.3 (torç konisi) |
| 13 | KLEMP_DIKEY_01 | klemp_dikey | 50×250×201 | 2.73 | GH-201-B sınıfı + köprü ayak (St) | basma Z=74.5, ayaklar Y=[-41.0, 41.0], yükseltici 36 mm, kol +Y yönünden |
| 14 | KLEMP_DIKEY_02 | klemp_dikey | 50×250×201 | 2.73 | GH-201-B sınıfı + köprü ayak (St) | basma Z=74.5, ayaklar Y=[-41.0, 41.0], yükseltici 36 mm, kol +Y yönünden |
| 15 | KLEMP_DIKEY_03 | klemp_dikey | 50×250×201 | 2.73 | GH-201-B sınıfı + köprü ayak (St) | basma Z=74.5, ayaklar Y=[-41.0, 41.0], yükseltici 36 mm, kol +Y yönünden |
| 16 | KLEMP_YATAY_01 | klemp_yatay | 50×135×155 | 1.44 | GH-304-CM sınıfı (St) | mil ekseni Z=45.0, itme yönü -Y, yükseltici 15 mm |
| 17 | KLEMP_YATAY_02 | klemp_yatay | 50×135×155 | 1.44 | GH-304-CM sınıfı (St) | mil ekseni Z=45.0, itme yönü -Y, yükseltici 15 mm |
| 18 | KLEMP_ITME_06 | klemp_itme | 209×130×167 | 3.24 | GH-304-CM sınıfı (St) + plaka ayak | mil ekseni Z=57.3, itme yönü +X, plaka ayak 130x41, yükseltici 27 mm |
| 19 | KLEMP_DIKEY_UC_07 | klemp_dikey | 50×222×198 | 2.54 | GH-201-B sınıfı + köprü ayak (St) | basma Z=71.5, ayaklar Y=[-22.8, 22.8], yükseltici 33 mm, kol +Y yönünden |
| 20 | KLEMP_ITME_08 | klemp_itme | 209×201×177 | 4.05 | GH-304-CM sınıfı (St) + plaka ayak | mil ekseni Z=66.5, itme yönü -X, plaka ayak 201x54, yükseltici 37 mm |
| 21 | TABAN_PLAKA | taban | 3440×520×15 | 210.54 | S355JR | 3440 x 520 x 15 mm, 6 x Ø13 montaj deliği |
| 22 | ISKELET_BOY_01 | iskelet | 3400×60×40 | 15.05 | S235JR kutu profil | 60x40x3 - L=3400 |
| 23 | ISKELET_BOY_02 | iskelet | 3400×60×40 | 15.05 | S235JR kutu profil | 60x40x3 - L=3400 |
| 24 | ISKELET_EN_01 | iskelet | 60×340×40 | 1.51 | S235JR kutu profil | 60x40x3 - L=340 |
| 25 | ISKELET_EN_02 | iskelet | 60×340×40 | 1.51 | S235JR kutu profil | 60x40x3 - L=340 |
| 26 | ISKELET_EN_03 | iskelet | 60×340×40 | 1.51 | S235JR kutu profil | 60x40x3 - L=340 |

Fikstür toplam: **282.1 kg**

## Temas / basma noktaları (fikstür → parça koordinatı)

- DAYAMA_A_01: F(268.0, -0.0, 40.0) → P(-5.68, -23.82, 18.0)
- DAYAMA_A_02: F(690.4, -0.0, 40.0) → P(-5.68, -23.82, 440.4)
- DAYAMA_A_03: F(1112.8, -0.0, 40.0) → P(-5.68, -23.82, 862.8)
- DAYAMA_A_04: F(1475.2, -0.0, 40.0) → P(-5.68, -23.82, 1225.2)
- DAYAMA_A_05: F(2037.6, -0.0, 40.0) → P(-5.68, -23.82, 1787.6)
- DAYAMA_A_06: F(2500.0, -0.0, 40.0) → P(-5.68, -23.82, 2250.0)
- DAYAMA_B_01: F(690.4, -60.0, 56.5) → P(54.32, -40.32, 440.4)
- DAYAMA_B_02: F(2037.6, -60.0, 61.5) → P(54.32, -45.27, 1787.6)
- DAYAMA_C_01: F(2630.0, 0.0, 42.0) → P(-5.68, -25.82, 2380.0)
- DAYAMA_A_UC_01a: F(2855.1, -0.0, 44.0) → P(-5.68, -27.82, 2605.13)
- DAYAMA_C_PLAKA_01a: F(3061.5, -85.3, 66.5) → P(79.57, -50.32, 2811.5)
- DAYAMA_C_PLAKA_01b: F(3061.5, 85.3, 66.5) → P(-90.93, -50.32, 2811.5)
- KLEMP_DIKEY_01: F(468.0, -41.0, 74.5) → P(35.32, -58.32, 218.0)
- KLEMP_DIKEY_01: F(468.0, 41.0, 74.5) → P(-46.68, -58.32, 218.0)
- KLEMP_DIKEY_02: F(1475.2, -41.0, 74.5) → P(35.32, -58.32, 1225.2)
- KLEMP_DIKEY_02: F(1475.2, 41.0, 74.5) → P(-46.68, -58.32, 1225.2)
- KLEMP_DIKEY_03: F(2500.0, -41.0, 74.5) → P(35.32, -58.32, 2250.0)
- KLEMP_DIKEY_03: F(2500.0, 41.0, 74.5) → P(-46.68, -58.32, 2250.0)
- KLEMP_YATAY_01: F(690.4, 60.0, 45.0) → P(-65.68, -28.82, 440.4)
- KLEMP_YATAY_02: F(2037.6, 60.0, 45.0) → P(-65.68, -28.82, 1787.6)
- KLEMP_ITME_06: F(150.0, 0.0, 57.3) → P(-5.68, -41.07, -100.0)
- KLEMP_DIKEY_UC_07: F(2824.2, -22.8, 71.5) → P(17.07, -55.32, 2574.18)
- KLEMP_DIKEY_UC_07: F(2824.2, 22.8, 71.5) → P(-28.43, -55.32, 2574.18)
- KLEMP_ITME_08: F(3069.5, -0.0, 66.5) → P(-5.68, -50.32, 2819.5)

## Kontroller

- Çakışma (fikstür–parça, fikstür–fikstür): 0 adet
- Temas DAYAMA_A_01: 0.0 mm ✓
- Temas DAYAMA_A_02: 0.0 mm ✓
- Temas DAYAMA_A_03: 0.0 mm ✓
- Temas DAYAMA_A_04: 0.0 mm ✓
- Temas DAYAMA_A_05: 0.0 mm ✓
- Temas DAYAMA_A_06: 0.0 mm ✓
- Temas DAYAMA_B_01: 0.0 mm ✓
- Temas DAYAMA_B_02: 0.0 mm ✓
- Temas DAYAMA_C_01: 0.0 mm ✓
- Temas DAYAMA_A_UC_01a: 0.0 mm ✓
- Temas DAYAMA_C_PLAKA_01a: 0.0 mm ✓
- Temas DAYAMA_C_PLAKA_01b: 0.0 mm ✓
- Temas KLEMP_DIKEY_01: 0.0 mm ✓
- Temas KLEMP_DIKEY_02: 0.0 mm ✓
- Temas KLEMP_DIKEY_03: 0.0 mm ✓
- Temas KLEMP_YATAY_01: 0.0 mm ✓
- Temas KLEMP_YATAY_02: 0.0 mm ✓
- Temas KLEMP_ITME_06: 0.0 mm ✓
- Temas KLEMP_DIKEY_UC_07: 0.0 mm ✓
- Temas KLEMP_ITME_08: 0.0 mm ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(1925.0, 26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(1925.0, -26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(1245.0, 26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(1585.0, 26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(2265.0, 26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(2605.0, 26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(1245.0, -26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(1585.0, -26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(2265.0, -26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi WELDING_KAYAR_BABA_XL-S_DESTEK_SACi @F(2605.0, -26.2, 74.0): yalnız fikstür 25/25, yalnız parça 25/25, birlikte 25/25 yön açık (60° koni) ✓
- Kaynak erişimi Kehlnaht 1-oa1 @F(3060.5, -47.2, 57.8): yalnız fikstür 16/25, yalnız parça 6/25, birlikte 6/25 yön açık (60° koni) ✓
- Kaynak erişimi Kehlnaht 1-oa1 @F(3060.5, 47.2, 57.8): yalnız fikstür 16/25, yalnız parça 6/25, birlikte 6/25 yön açık (60° koni) ✓
- Kaynak erişimi Kehlnaht 2-oa2 @F(3060.5, -0.0, 67.5): yalnız fikstür 16/25, yalnız parça 6/25, birlikte 6/25 yön açık (60° koni) ✓

**SONUÇ: GEÇTİ**

## Notlar

- Klempler zarf modelidir (GH-201-B / GH-304-CM sınıfı); üretimde tedarikçi modeliyle değiştirilir.
- Dayamalar altından M8 ile taban plakasına bağlanır (taban Ø9 delik, dayama M8 diş).
- Kapak yuvası -Y kulağı datumdur; +Y tarafı yatay klemple itilir (plaka genişlik toleransı).
- Kaynak dikişlerine 60 mm'den yakın eleman yerleştirilmemiştir; torç kanal içine üstten girer.
