# -*- coding: utf-8 -*-
"""Parça / standart / kaynak dikişi ayrımı.

Adların hepsi GERÇEK modellerden (kaynaklı kasa, TIRSAN ray, arka kapak)
alındı. Her satır bir hatanın ya da bir sınırın kaydıdır:

  - "KAYNAK SOMUNU", "KAYNAK CIVATASI" dikiş değil standart eleman
  - "CIVATA LAMASI", "SOMUN SACI" standart değil ÜRETİM parçası
    (Türkçe tamlamada asıl isim sondadır)
  - "FL SOMUN_2": '_' sözcük sınırını bozuyordu, parça çıkıyordu
  - "KAYNAKLI ..." kaynaklı montaj/parça, dikiş değil
  - "WELDING_..." dikiş
Ayrıca montaj ağacından sınıflama: satın alınan grubun içi standart,
dikiş grubunun içi dikiş; kullanıcının elle verdiği sınıf her şeyden
önce gelir.

    python3 test/sinif_denetimi.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as M                                             # noqa: E402

HATA = []


def esit(ad, olan, beklenen):
    iyi = olan == beklenen
    print(f"  {'tamam' if iyi else 'HATA '} {ad:48s} {olan}"
          + ("" if iyi else f"   (beklenen {beklenen})"))
    if not iyi:
        HATA.append(ad)


TABLO = [
    # kaynak dikişi
    ("K0 25 MM TEK KAYNAK.2", "kaynak"),
    ("Symmetry of K0 30 MM CIFT KAYNAK_1", "kaynak"),
    ("K0 BRAKET KAYNAGI", "kaynak"),
    ("Kehlnaht 2-oa2", "kaynak"),
    ("WELDING_KAYAR_BABA_XL-S_DESTEK_SAC_i", "kaynak"),
    ("K0 KAYNAKLAR", "kaynak"),
    # kaynakla birleşen standart eleman
    ("M10 KAYNAK SOMUNU", "standart"),
    ("Symmetry of M6 KAYNAK SOMUNU.1_1", "standart"),
    ("M6X20 KAYNAK CIVATASI", "standart"),
    ("Weld nut M8", "standart"),
    # standart
    ("Symmetry of M10X1,5 FL SOMUN_2", "standart"),
    ("M6X15 FLANSLI CIVATA", "standart"),
    ("K0 7X25X2 MM PUL", "standart"),
    ("M6 SOMUN PERCIN", "standart"),
    ("M8 perçin somun", "standart"),
    ("RIVNUT M6", "standart"),
    ("Blindnietmutter M5", "standart"),
    ("K0 PERCIN SOMUN BRAKETI", "parca"),
    ("Kayar Baba Mekanizma Govde Percini_Q8x58", "standart"),
    ("09.020.000.05 Rillenkugellager DIN 608 2RSR", "standart"),
    ("ISO 7090 WASHER 8X16", "standart"),
    ("K0 KAMERA", "standart"),
    ("K0 YUK BAGLAMA HALKASI", "standart"),
    ("KAUCUK STOPER.3", "standart"),
    ("K0 KAUCUK TAKOZ", "standart"),
    ("K0 CIFT EKSENLI MENTESE_1_NEVSEHIR", "standart"),
    # üretim parçası
    ("K0 CIVATA LAMASI_2", "parca"),
    ("Symmetry of K0 CIVATA LAMASI_1", "parca"),
    ("K0 ON PANEL SOMUN SACI", "parca"),
    ("K0 GERI GORUS KAMERASI BRAKETI", "parca"),
    ("K0 KAYNAKLI BRAKET", "parca"),
    ("K0 SASI BRAKET KAUCUK", "parca"),
    ("Lagerbock", "parca"),
    ("Motor Halter", "parca"),
    ("01.050.000.01 U-Blech", "parca"),
    ("Anahtar", "parca"),
    ("06.001.001.34 Keil", "parca"),
]

print("-- addan sınıflama")
for ad, bek in TABLO:
    esit(ad, M.sinifla(ad)[0], bek)

print("\n-- kaynak türü (kopya ekleri atılır)")
esit("Symmetry of ... .2", M.kaynak_tipi("Symmetry of K0 25 MM TEK KAYNAK.2"),
     "K0 25 MM TEK KAYNAK")
esit("..._3", M.kaynak_tipi("K0 30 MM TEK KAYNAK_3"), "K0 30 MM TEK KAYNAK")
oz = M.kaynak_ozeti([{"ad": "K0 25 MM TEK KAYNAK", "adet": 3},
                     {"ad": "Symmetry of K0 25 MM TEK KAYNAK.1", "adet": 2},
                     {"ad": "K0 40 MM TEK KAYNAK_1", "adet": 1}])
esit("özet", oz, [("K0 25 MM TEK KAYNAK", 5), ("K0 40 MM TEK KAYNAK", 1)])

print("\n-- montaj ağacından")
agac = {"ad": "KOK", "alt": [
    {"ad": "153-02-10-004 - GOMME SALLAMA KUCUK", "montaj": True,
     "alt": [{"ad": "151B-02-10-004", "katilar": [0]}]},
    {"ad": "K0 KAYNAKLAR", "montaj": True,
     "alt": [{"ad": "ARA DIKME", "katilar": [1]}]},
    {"ad": "K0 KAYNAKLI GRUP", "montaj": True,
     "alt": [{"ad": "LEVHA", "katilar": [2]}]},
    {"ad": "K0 CIVATA LAMASI_4_MONTAJ", "montaj": True,
     "alt": [{"ad": "PLAKA X", "katilar": [3]}]}]}
komp = [{"ad": "151B-02-10-004", "sinif": "parca", "tip": "", "indeks": [0, 9]},
        {"ad": "ARA DIKME", "sinif": "parca", "tip": "", "indeks": [1]},
        {"ad": "LEVHA", "sinif": "parca", "tip": "", "indeks": [2]},
        {"ad": "PLAKA X", "sinif": "parca", "tip": "", "indeks": [3]}]
M.agactan_sinifla(agac, komp, {}, log=lambda t: None)
esit("satın alınan grubun içi (2. kopya ağaçta yok)", komp[0]["sinif"], "standart")
esit("dikiş grubunun içi", komp[1]["sinif"], "kaynak")
esit("KAYNAKLI grubun içi parça kalır", komp[2]["sinif"], "parca")
esit("CIVATA LAMASI montajının içi parça kalır", komp[3]["sinif"], "parca")

print("\n-- kullanıcının kuralı önce gelir")
kural = {M.kural_anahtari("K0 KAMERA"): "parca",
         M.kural_anahtari("COMPOUND"): "standart"}
esit("K0 KAMERA elle parça", M.sinifla("K0 KAMERA", kural)[0], "parca")
esit("Symmetry of K0 KAMERA.1 de", M.sinifla("Symmetry of K0 KAMERA.1", kural)[0],
     "parca")
esit("COMPOUND elle standart", M.sinifla("COMPOUND", kural)[0], "standart")
komp = [{"ad": "ARA DIKME", "sinif": "parca", "tip": "", "indeks": [1]}]
M.agactan_sinifla(agac, komp, {M.kural_anahtari("ARA DIKME"): "parca"},
                  log=lambda t: None)
esit("ağaç kuralı elle verileni ezmez", komp[0]["sinif"], "parca")

print("\n-- perçin somun tipi (somun ya da perçin değil)")
for ad in ("M6 SOMUN PERCIN", "M8 perçin somun", "Rivet nut M5", "Einnietmutter M8"):
    esit(ad, M.sinifla(ad), ("standart", "perçin somun"))
esit("Govde Percini hâlâ perçin", M.sinifla("Govde Percini"), ("standart", "perçin"))
esit("M6 SOMUN hâlâ somun", M.sinifla("M6 SOMUN"), ("standart", "somun"))

print("\n-- ad bilgi taşıyor mu (öğrenme yalnız taşımayanlara uygulanır)")
for ad, bek in (("510206504-00", False), ("COMPOUND", False), ("151B-02-01-038", False),
                ("K0 TRIM BAGLANTI SACI", True), ("M6 SOMUN", True),
                ("K0 25 MM TEK KAYNAK", True), ("ISO 4762 M6x20", True)):
    esit(ad, M.ad_bilgili(ad), bek)

print("\n-- CAD'in Made / Bought bilgisi")
import tempfile                                                  # noqa: E402
d = tempfile.mkdtemp(prefix="cad_kaynak_")
y = os.path.join(d, "malzeme.csv")
with open(y, "w", encoding="utf-8") as f:
    f.write("kod;malzeme;ad;kaynak\n"
            "510206504-00;Steel;Tedarikci parcasi;Bought\n"
            "K0 KAMERA;Steel;Kamera;Made\n"
            "01.050.000.01;Steel;U-Blech;Made\n"
            "ISO 4762 M6x20;Steel;Civata;\n")
har = M.cad_kaynagi_oku(y)
esit("Bought -> standart, Made -> parca, boş -> yok", har,
     {"510206504-00": "standart", "k0 kamera": "parca", "01.050.000.01": "parca"})
komp = [{"kod": "510206504-00", "ad": "510206504-00", "sinif": "parca", "tip": ""},
        {"kod": "K0 KAMERA", "ad": "K0 KAMERA", "sinif": "standart", "tip": "ticari ürün"},
        {"kod": "X", "ad": "01.050.000.01 U-Blech", "sinif": "parca", "tip": ""},
        {"kod": "K", "ad": "K0 25 MM TEK KAYNAK", "sinif": "kaynak", "tip": ""}]
n = M.cad_kaynagiyla_sinifla(komp, har, {}, log=lambda t: None)
esit("tedarikçi parçası CAD'e göre standart", (komp[0]["sinif"], komp[0]["tip"]),
     ("standart", "CAD: satın alınan"))
esit("adı 'kamera' ama CAD 'Made' diyor", komp[1]["sinif"], "parca")
esit("kod adın içinden eşleşti", komp[2]["sinif"], "parca")
esit("dikişe dokunulmaz", komp[3]["sinif"], "kaynak")
esit("değişen sayısı", n, 2)
kural = {M.kural_anahtari("510206504-00"): "parca"}
komp[0]["sinif"] = "parca"
M.cad_kaynagiyla_sinifla(komp[:1], har, kural, log=lambda t: None)
esit("elle verilen sınıf CAD'den de önce gelir", komp[0]["sinif"], "parca")
with open(y, "w", encoding="utf-8") as f:
    f.write("kod;malzeme\nA;Steel\n")
esit("kaynak sütunu yoksa boş", M.cad_kaynagi_oku(y), {})

print("\n-- standart tanımı kontrol listesi (tasarımcıya giden, geri gelen)")
import pf9_excel as XL                                           # noqa: E402
komp = [{"kod": "FT108161", "ad": "FT108161", "sinif": "standart", "tip": "civata (geometri)",
         "geometri": "cıvata: 6 köşe baş", "adet": 41, "olc": [18.7, 18.7, 24.5]},
        {"kod": "55460008672", "ad": "55460008672", "sinif": "parca", "tip": "",
         "aday": ["dönel küçük parça"], "adet": 6, "olc": [9, 27.1, 27.1]},
        {"kod": "55460008672", "ad": "55460008672", "sinif": "parca", "tip": "",
         "adet": 1, "olc": [1, 1281.2, 1513.8]},
        {"kod": "COMPOUND", "ad": "COMPOUND", "sinif": "parca", "tip": "", "isimsiz": True,
         "adet": 1, "olc": [2, 3, 11]},
        {"kod": "K0 SAC", "ad": "K0 SAC", "sinif": "parca", "tip": "", "adet": 1,
         "oneri": ("standart", "pul", "pul: Ø18"), "olc": [2, 18, 18]}]
kl = M.kontrol_listesi(komp)
esit("dört durum da listede, düz sac yok", [r[0].split(":")[0].split(" -")[0] for r in kl],
     ["geometri", "standart olabilir", "tanınmadı", "ad ile biçim çelişiyor"])
y = M.kontrol_yaz(d, komp)
esit("STANDART_KONTROL.xlsx yazıldı", os.path.basename(y), "STANDART_KONTROL.xlsx")
esit("doldurulmamış liste hiçbir şey değiştirmez", M.cad_kaynagi_oku(y), {})
sat = [r[:8] + ["Bought" if r[1] == "55460008672" else ""] for r in kl]
XL.xlsx_yaz(y, [("Kontrol", M.KONTROL_BASLIK, sat)])
esit("malzeme sütunu yok (yalnız sınıf dosyası)", M.malzeme_sutunu_var(y), False)
har = M.cad_kaynagi_oku(y)
M.cad_kaynagiyla_sinifla(komp, har, {}, log=lambda t: None)
esit("ortak kodlu halka Bought -> standart", komp[1]["sinif"], "standart")
esit("AYNI KODLU sac (başka ölçü) üretimde kalır", komp[2]["sinif"], "parca")
esit("liste boşalınca dosya silinir", M.kontrol_yaz(d, []) is None and not os.path.isfile(y), True)

print("\n-- hiyerarşik BOM: dikişler tek satır")
agac = {"ad": "KOK", "montaj": True, "alt": [
    {"ad": "PARCA A", "katilar": [0]},
    {"ad": "K0 25 MM TEK KAYNAK", "katilar": [1]},
    {"ad": "K0 25 MM TEK KAYNAK.1", "katilar": [2]},
    {"ad": "PARCA B", "katilar": [3]}]}
komp = [{"kod": "A", "ad": "PARCA A", "sinif": "parca", "indeks": [0]},
        {"kod": "K", "ad": "K0 25 MM TEK KAYNAK", "sinif": "kaynak", "indeks": [1, 2]},
        {"kod": "B", "ad": "PARCA B", "sinif": "parca", "indeks": [3]}]
sat = M.agac_bom(agac, komp, [])
esit("poz sırası kesintisiz", [r["poz"] for r in sat], ["1", "1.1", "1.2", "1.K"])
esit("dikiş satırı", (sat[-1]["tur"], sat[-1]["adet"]), ("kaynak", 2))

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                     else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(1 if HATA else 0)
