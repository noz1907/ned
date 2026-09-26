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
