# Hiyerarşik parça listesi (çok kademeli BOM)

Ana ürün → alt montaj → parça. **Adet bir üst montaj başınadır**; ürünün tamamındaki sayı `toplam` sütunundadır.

| poz | kademe | tür | kod | tanım | adet | toplam | malzeme | ölçü | kg/adet |
|-----|--------|-----|-----|-------|------|--------|---------|------|---------|
| 1 | 0 | montaj |  | 520260925_XL-S_KAYAR_BABA_KAPAKSIZ_5-SIRA_YA | 1 | 1 | - | - | - |
| 1.1 | 1 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;510260925-01_XL-S_KAYAR_BABA_KAPAKSIZ_5-SIRA | 1 | 1 | - | - | - |
| 1.1.1 | 2 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Assem1 | 1 | 1 | - | - | - |
| 1.1.1.1 | 3 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;510260901-50_KAYAR_BABA_XL-S_GMRKSZ_GOVDE | 1 | 1 | - | - | - |
| 1.1.1.1.1 | 4 | parca | 01.051.000.01 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.051.000.01 C-Profil-Runge XL-H | 1 | 1 | Celik (S235JR / St37) | 2480.0x120.0x34.5 | 10.6724 |
| 1.1.1.1.2 | 4 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.050.000.20 BG Mechanismus | 1 | 1 | - | - | - |
| 1.1.1.1.2.1 | 5 | parca | 01.050.000.01 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.050.000.01 U-Blech-Mechanismus | 1 | 1 | Celik (S235JR / St37) | 483.04x76.5x32.0 | 1.2847 |
| 1.1.1.1.2.2 | 5 | parca | 06.001.001.34 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;06.001.001.34-Keil-forging | 1 | 1 | Celik (S235JR / St37) | 175.42x70.65x31.95 | 1.0859 |
| 1.1.1.1.2.3 | 5 | standart | 06.002.001.03 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;06.002.001.03-Handhebellagerung-600 | 1 | 1 | - | - | - |
| 1.1.1.1.2.4 | 5 | standart | 06.001.001.06 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;06.001.001.06-Bolzen 8x68 | 1 | 1 | - | - | - |
| 1.1.1.1.2.5 | 5 | parca | 01.050.000.02 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.050.000.02 Federanschlag | 1 | 1 | Celik (S235JR / St37) | 77.0x70.0x5.0 | 0.0708 |
| 1.1.1.1.2.6 | 5 | standart | 06.001.001.05 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;06.001.001.05 Druckfeder-Rungenkeil-Einbaulä | 1 | 1 | - | - | - |
| 1.1.1.1.2.7 | 5 | standart | 01.050.000.05 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.050.000.05 Bolzen 8x46 | 1 | 1 | - | - | - |
| 1.1.1.1.2.8 | 5 | standart | 01.050.000.09 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.050.000.09 Bolzen 10x100 | 1 | 1 | - | - | - |
| 1.1.1.1.2.9 | 5 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.050.000.03 Führungsschale | 1 | 1 | - | - | - |
| 1.1.1.1.2.9.1 | 6 | parca | 01.050.000.14 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.050.000.14 Führungsschale-Fuß-links mecha | 1 | 1 | Celik (S235JR / St37) | 301.65x45.01x68.07 | 1.2144 |
| 1.1.1.1.2.9.2 | 6 | parca | 01.050.000.15 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.050.000.15 Führungsschale-FuB-rechts mech | 1 | 1 | Celik (S235JR / St37) | 301.65x45.01x68.07 | 1.2144 |
| 1.1.1.1.2.9.3 | 6 | standart | 01.050.000.06 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;01.050.000.06 Bolzen 12x100 | 1 | 1 | - | - | - |
| 1.1.1.1.2.9.4 | 6 | parca | 1 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;1 | 1 | 1 | Celik (S235JR / St37) | 12.3x12.35x9.89 | 0.0065 |
| 1.1.1.1.2.9.5 | 6 | parca | Ausprägung 2-oa0 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ausprägung 2-oa0 | 1 | 1 | Celik (S235JR / St37) | 12.3x12.35x9.89 | 0.007 |
| 1.1.1.1.2.10 | 5 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Assem1 | 1 | 1 | - | - | - |
| 1.1.1.1.2.10.1 | 6 | parca | 07.007.070.04 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;07.007.070.04 - Kniehebel - KTL | 1 | 1 | Celik (S235JR / St37) | 211.01x48.01x21.01 | 0.2123 |
| 1.1.1.1.2.10.2 | 6 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;07.007.070.50 - BG Handhebe | 1 | 1 | - | - | - |
| 1.1.1.1.2.10.2.1 | 7 | parca | 06.000.001.07 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;06.000.001.07 - Handhebel - roh | 1 | 1 | Celik (S235JR / St37) | 166.0x38.0x23.0 | 0.2431 |
| 1.1.1.1.2.10.2.2 | 7 | standart | 06.000.001.08 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;06.000.001.08 - Sicherung - verzinkt | 1 | 1 | - | - | - |
| 1.1.1.1.2.10.2.3 | 7 | standart | 06.000.001.09 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;06.000.001.09 - Druckfeder 1 x 6,5 x L1 = 27 | 1 | 1 | - | - | - |
| 1.1.1.1.2.10.2.4 | 7 | standart | 06.000.001.10 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;06.000.001.10 - Blindniet ISO 15983 - 5 × 10 | 1 | 1 | - | - | - |
| 1.1.1.1.2.10.3 | 6 | standart | 07.007.070.05 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;07.007.070.05 - Halbhohlniet Ø8x37 - KTL | 1 | 1 | - | - | - |
| 1.1.1.1.2.11 | 5 | standart | Kayar Baba Mekanizma Govde | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Kayar Baba Mekanizma Govde Percini_Q8x58 | 1 | 1 | - | - | - |
| 1.1.1.1.2.12 | 5 | standart | ISO 7090 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ISO 7090 WASHER 8X16 STEEL GRADE A PLAIN CHA | 1 | 1 | - | - | - |
| 1.1.1.1.3 | 4 | kaynak | WELDING_KAYAR_BABA_Mekaniz | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;WELDING_KAYAR_BABA_Mekanizma-1 | 1 | 1 | - | - | - |
| 1.1.1.1.4 | 4 | kaynak | WELDING_KAYAR_BABA_Mekaniz | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;WELDING_KAYAR_BABA_Mekanizma-2 | 1 | 1 | - | - | - |
| 1.1.1.1.5 | 4 | kaynak | WELDING_KAYAR_BABA_XL-S_DE | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;WELDING_KAYAR_BABA_XL-S_DESTEK_SACi | 1 | 1 | - | - | - |
| 1.1.1.1.6 | 4 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Assem1 | 1 | 1 | - | - | - |
| 1.1.1.1.6.1 | 5 | parca | 09.025.000.02 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;09.025.000.02 C-Profil Teleskop | 1 | 1 | Celik (S235JR / St37) | 1940.0x100.0x27.5 | 8.9579 |
| 1.1.1.1.6.2 | 5 | parca | 09.020.000.01 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;09.020.000.01 Dachplatte 45x195mm | 1 | 1 | Celik (S235JR / St37) | 195.0x50.0x8.0 | 0.5671 |
| 1.1.1.1.6.3 | 5 | kaynak | Kehlnaht 1-oa1 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Kehlnaht 1-oa1 | 2 | 2 | - | - | - |
| 1.1.1.1.6.4 | 5 | kaynak | Kehlnaht 2-oa2 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Kehlnaht 2-oa2 | 1 | 1 | - | - | - |
| 1.1.2 | 2 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;KAYAR_BABA_5_SIRA_YAN_YAPI_SET | 1 | 1 | - | - | - |
| 1.1.2.1 | 3 | parca | 510206504-00 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;510206504-00_KAYAR BABA YAN YAPI YUVASI GALV | 10 | 10 | Celik (S235JR / St37) | 7.0x4.0x1.5 | 0.0002 |
| 1.1.3 | 2 | standart | 6,4x14_Percin_percinli | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;6,4x14_Percin_percinli | 10 | 10 | - | - | - |
| 1.2 | 1 | standart | 06.002.008.30 | &nbsp;&nbsp;&nbsp;&nbsp;06.002.008.30 - Rungenlager, kurz TIRSAN | 1 | 1 | - | - | - |
| 1.3 | 1 | parca | TIRSAN_Ray 112,5 | &nbsp;&nbsp;&nbsp;&nbsp;TIRSAN_Ray 112,5 | 1 | 1 | Celik (S235JR / St37) | 200.0x112.52x125.48 | 3.0402 |
| 1.4 | 1 | montaj |  | &nbsp;&nbsp;&nbsp;&nbsp;09.020.000.20_BG Rollenplatte | 1 | 1 | - | - | - |
| 1.4.1 | 2 | parca | 09.020.000.03 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;09.020.000.03 Rollenplatte | 1 | 1 | Celik (S235JR / St37) | 175.0x100.0x5.0 | 0.2833 |
| 1.4.2 | 2 | standart | 09.020.000.07 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;09.020.000.07 Bolzen 7,9x24 | 2 | 2 | - | - | - |
| 1.4.3 | 2 | standart | 09.020.000.06 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;09.020.000.06 Unterlegscheibe 8,4x16x1,6 DIN | 4 | 4 | - | - | - |
| 1.4.4 | 2 | standart | 09.020.000.05 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;09.020.000.05 Rillenkugellager DIN 608 2RSR | 4 | 4 | - | - | - |
| 1.4.5 | 2 | standart | M8x16 Anahtar Basli Civata | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;M8x16 Anahtar Basli Civata | 2 | 2 | - | - | - |
| 1.4.6 | 2 | standart | M8 Somun | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;M8 Somun | 2 | 2 | - | - | - |
