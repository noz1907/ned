# G03 kaynak fikstürü – tasarım raporu

Kaynak dosya: `/home/user/ned/ornek/parca.stp`  |  yön: **+Y** yukarı  |  parça: 9.53 kg, 5 katı (3 kaynak dikişi)

Fikstür koordinatları: +Z yukarı, +X parça boyu, taban plakası üst yüzü Z=0.

Parça zarfı (fikstürde): X 150.0..2098.0, Y -97.5..97.5, Z 20.0..70.0

## Konumlandırma (3-2-1)

- **Datum A (Z, 3+ nokta):** ana gövde alt yüzü, alan 171676 mm², dayama üstü Z=40.00; dayama X konumları: [190.0, 641.8, 1093.5, 1545.3, 1997.0]
- **Datum B (Y, 2 nokta):** -Y yan yüz, yan dayamalar DAYAMA_B_01/02
- **Datum C (X, 1 nokta):** kapak plakası dış yüzü yuva arka duvarına dayanır (YUVA_C); profil, itme klempi ile kapağa doğru itilir.

## Elemanlar

| # | ad | tip | boyut (X×Y×Z) | kg | malzeme | not |
|---|----|-----|---------------|----|---------|-----|
| 1 | DAYAMA_A_01 | dayama_A | 60×79×40 | 1.47 | C45 sertleştirilmiş | temas alanı 4631 mm² (98 %) |
| 2 | DAYAMA_A_02 | dayama_A | 60×79×40 | 1.47 | C45 sertleştirilmiş | temas alanı 4631 mm² (98 %) |
| 3 | DAYAMA_A_03 | dayama_A | 60×79×40 | 1.47 | C45 sertleştirilmiş | temas alanı 4631 mm² (98 %) |
| 4 | DAYAMA_A_04 | dayama_A | 60×79×40 | 1.47 | C45 sertleştirilmiş | temas alanı 4631 mm² (98 %) |
| 5 | DAYAMA_A_05 | dayama_A | 60×79×40 | 1.47 | C45 sertleştirilmiş | temas alanı 4224 mm² (89 %) |
| 6 | DAYAMA_B_01 | dayama_B | 40×30×66 | 0.60 | C45 sertleştirilmiş | temas yüzü Y=-50.00, Z 40.0..66.0 |
| 7 | DAYAMA_B_02 | dayama_B | 40×30×66 | 0.60 | C45 sertleştirilmiş | temas yüzü Y=-50.00, Z 40.0..66.0 |
| 8 | YUVA_C_01 | yuva_C | 53×210×75 | 5.03 | S355JR | 09.020.000.01 Dachplatte 45x19: arka duvar X=2098.00, raf Z=20.00, kulak Y=-97.50 |
| 9 | KLEMP_DIKEY_01 | klemp_dikey | 50×237×194 | 2.45 | GH-201-B sınıfı + köprü ayak (St) | basma Z=67.5, ayaklar Y=[-37.8, 37.8], yükseltici 29 mm, kol +Y yönünden |
| 10 | KLEMP_DIKEY_02 | klemp_dikey | 50×237×194 | 2.45 | GH-201-B sınıfı + köprü ayak (St) | basma Z=67.5, ayaklar Y=[-37.8, 37.8], yükseltici 29 mm, kol +Y yönünden |
| 11 | KLEMP_DIKEY_03 | klemp_dikey | 50×237×194 | 2.45 | GH-201-B sınıfı + köprü ayak (St) | basma Z=67.5, ayaklar Y=[-37.8, 37.8], yükseltici 29 mm, kol +Y yönünden |
| 12 | KLEMP_YATAY_01 | klemp_yatay | 50×135×155 | 1.44 | GH-304-CM sınıfı (St) | mil ekseni Z=45.0, itme yönü -Y, yükseltici 15 mm |
| 13 | KLEMP_YATAY_02 | klemp_yatay | 50×135×155 | 1.44 | GH-304-CM sınıfı (St) | mil ekseni Z=45.0, itme yönü -Y, yükseltici 15 mm |
| 14 | KLEMP_ITME_06 | klemp_itme | 209×110×164 | 2.96 | GH-304-CM sınıfı (St) + plaka ayak | mil ekseni Z=53.8, itme yönü +X, plaka ayak 110x34, yükseltici 24 mm |
| 15 | KLEMP_DIKEY_KAPAK_07 | klemp_dikey | 150×50×196 | 2.30 | GH-201-B sınıfı, mafsallı lastik ayak | basma Z=70.0, ayaklar Y=[-89.5], yükseltici 31 mm, kol +X yönünden |
| 16 | KLEMP_YATAY_KAPAK_08 | klemp_yatay | 50×120×155 | 1.42 | GH-304-CM sınıfı (St) | mil ekseni Z=45.0, itme yönü -Y, yükseltici 15 mm |
| 17 | TABAN_PLAKA | taban | 2400×560×15 | 158.16 | S355JR | 2400 x 560 x 15 mm, 6 x Ø13 montaj deliği |
| 18 | ISKELET_BOY_01 | iskelet | 2360×60×40 | 10.45 | S235JR kutu profil | 60x40x3 - L=2360 |
| 19 | ISKELET_BOY_02 | iskelet | 2360×60×40 | 10.45 | S235JR kutu profil | 60x40x3 - L=2360 |
| 20 | ISKELET_EN_01 | iskelet | 60×380×40 | 1.68 | S235JR kutu profil | 60x40x3 - L=380 |
| 21 | ISKELET_EN_02 | iskelet | 60×380×40 | 1.68 | S235JR kutu profil | 60x40x3 - L=380 |
| 22 | ISKELET_EN_03 | iskelet | 60×380×40 | 1.68 | S235JR kutu profil | 60x40x3 - L=380 |

Fikstür toplam: **214.6 kg**

## Temas / basma noktaları (fikstür → parça koordinatı)

- DAYAMA_A_01: F(190.0, 0.0, 40.0) → P(-5.68, -55.32, 911.5)
- DAYAMA_A_02: F(641.8, 0.0, 40.0) → P(-5.68, -55.32, 1363.25)
- DAYAMA_A_03: F(1093.5, 0.0, 40.0) → P(-5.68, -55.32, 1815.0)
- DAYAMA_A_04: F(1545.3, 0.0, 40.0) → P(-5.68, -55.32, 2266.75)
- DAYAMA_A_05: F(1997.0, 0.0, 40.0) → P(-5.68, -55.32, 2718.5)
- DAYAMA_B_01: F(641.8, -50.0, 53.0) → P(-55.68, -42.32, 1363.25)
- DAYAMA_B_02: F(1545.3, -50.0, 53.0) → P(-55.68, -42.32, 2266.75)
- YUVA_C_01: F(2098.0, -0.0, 45.0) → P(-5.68, -50.32, 2819.5)
- YUVA_C_01: F(2094.0, -0.0, 20.0) → P(-5.68, -75.32, 2815.5)
- YUVA_C_01: F(2094.0, -97.5, 45.0) → P(-103.18, -50.32, 2815.5)
- KLEMP_DIKEY_01: F(190.0, -37.8, 67.5) → P(-43.48, -27.82, 911.5)
- KLEMP_DIKEY_01: F(190.0, 37.8, 67.5) → P(32.12, -27.82, 911.5)
- KLEMP_DIKEY_02: F(1093.5, -37.8, 67.5) → P(-43.48, -27.82, 1815.0)
- KLEMP_DIKEY_02: F(1093.5, 37.8, 67.5) → P(32.12, -27.82, 1815.0)
- KLEMP_DIKEY_03: F(1997.0, -37.8, 67.5) → P(-43.48, -27.82, 2718.5)
- KLEMP_DIKEY_03: F(1997.0, 37.8, 67.5) → P(32.12, -27.82, 2718.5)
- KLEMP_YATAY_01: F(641.8, 50.0, 45.0) → P(44.32, -50.32, 1363.25)
- KLEMP_YATAY_02: F(1545.3, 50.0, 45.0) → P(44.32, -50.32, 2266.75)
- KLEMP_ITME_06: F(150.0, 0.0, 53.8) → P(-5.68, -41.57, 871.5)
- KLEMP_DIKEY_KAPAK_07: F(2094.0, -89.5, 70.0) → P(-95.18, -25.32, 2815.5)
- KLEMP_YATAY_KAPAK_08: F(2094.0, 97.5, 45.0) → P(91.82, -50.32, 2815.5)

## Kontroller

- Çakışma (fikstür–parça, fikstür–fikstür): 0 adet
- Temas DAYAMA_A_01: 0.0 mm ✓
- Temas DAYAMA_A_02: 0.0 mm ✓
- Temas DAYAMA_A_03: 0.0 mm ✓
- Temas DAYAMA_A_04: 0.0 mm ✓
- Temas DAYAMA_A_05: 0.0 mm ✓
- Temas DAYAMA_B_01: 0.0 mm ✓
- Temas DAYAMA_B_02: 0.0 mm ✓
- Temas YUVA_C_01: 0.0 mm ✓
- Temas KLEMP_DIKEY_01: 0.0 mm ✓
- Temas KLEMP_DIKEY_02: 0.0 mm ✓
- Temas KLEMP_DIKEY_03: 0.0 mm ✓
- Temas KLEMP_YATAY_01: 0.0 mm ✓
- Temas KLEMP_YATAY_02: 0.0 mm ✓
- Temas KLEMP_ITME_06: 0.0 mm ✓
- Temas KLEMP_DIKEY_KAPAK_07: 0.0 mm ✓
- Temas KLEMP_YATAY_KAPAK_08: 0.0 mm ✓
- Kaynak erişimi Kehlnaht 1-oa1 @F(2089.0, 47.2, 53.8): yalnız fikstür 19/25, yalnız parça 6/25, birlikte 6/25 yön açık (60° koni) ✓
- Kaynak erişimi Kehlnaht 1-oa1 @F(2089.0, -47.2, 53.8): yalnız fikstür 17/25, yalnız parça 6/25, birlikte 5/25 yön açık (60° koni) ✓
- Kaynak erişimi Kehlnaht 2-oa2 @F(2089.0, -0.0, 44.0): yalnız fikstür 18/25, yalnız parça 14/25, birlikte 14/25 yön açık (60° koni) ✓

**SONUÇ: GEÇTİ**

## Notlar

- Klempler zarf modelidir (GH-201-B / GH-304-CM sınıfı); üretimde tedarikçi modeliyle değiştirilir.
- Dayamalar altından M8 ile taban plakasına bağlanır (taban Ø9 delik, dayama M8 diş).
- Kapak yuvası -Y kulağı datumdur; +Y tarafı yatay klemple itilir (plaka genişlik toleransı).
- Kaynak dikişlerine 60 mm'den yakın eleman yerleştirilmemiştir; torç kanal içine üstten girer.
