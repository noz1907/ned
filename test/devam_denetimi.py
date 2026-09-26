# -*- coding: utf-8 -*-
"""Klasör düzeni (DXF / ACINIM / LZR / PDF) ve önceki çıktıdan devam.

Hesap motoru (OpenCascade) GEREKMEZ; pf7_is saf Python'dur.

Denetlenen:
  - dosyalar türüne göre kendi klasöründe; eski sürümün köke yazdıkları
    da bulunuyor, aynı ad iki yerdeyse klasördeki alınıyor
  - bir çizim YALNIZ aynı model içeriği + aynı ayarla üretildiği
    kayıtlıysa "güncel" sayılıyor (model değişirse, ayar değişirse,
    dosya silinirse, kayıt yoksa -> yeniden üretilir)
  - model özeti içeriğe bağlı: dosyayı kopyalamak özeti değiştirmez
  - ACINIM.csv / LAZER.csv birleştiriliyor: 2 parçayı yeniden üretmek
    diğer 3 parçanın satırını silmiyor; dosyası silinmiş satır düşüyor
  - ..._yapilamayanlar.txt: denenip başaranlar listeden düşüyor
  - iş durumu dosyası bozuksa program çökmüyor
  - işlem süreleri kaydediliyor

    python3 test/devam_denetimi.py
"""
import csv
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf7_is as IS                                              # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def yaz(yol, icerik="0\nSECTION\n0\nEOF\n"):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        f.write(icerik)


kok = tempfile.mkdtemp(prefix="devam_")
try:
    print("-- klasör düzeni")
    yaz(os.path.join(IS.alt_klasor(kok, "dxf"), "P01_A.dxf"))
    yaz(os.path.join(IS.alt_klasor(kok, "dxf"), "00_MONTAJ.dxf"))
    yaz(os.path.join(IS.alt_klasor(kok, "acinim"), "P01_A_acinim.dxf"))
    yaz(os.path.join(IS.alt_klasor(kok, "lazer"), "P01_A_Lzr.dxf"))
    yaz(os.path.join(IS.alt_klasor(kok, "pdf"), "P01_A_A3.pdf"))
    # eski sürüm: köke yazılmış
    yaz(os.path.join(kok, "P02_B.dxf"))
    yaz(os.path.join(kok, "P02_B_acinim.dxf"))
    yaz(os.path.join(kok, "P01_A.dxf"))             # klasörde de var
    ad = lambda t: [os.path.relpath(y, kok).replace("\\", "/")   # noqa: E731
                    for y in IS.dosyalar(kok, t)]
    dogru("DXF: klasördeki + kökteki eski, tekrar yok",
          ad("dxf") == ["DXF/00_MONTAJ.dxf", "DXF/P01_A.dxf", "P02_B.dxf"],
          str(ad("dxf")))
    dogru("ACINIM", ad("acinim") == ["ACINIM/P01_A_acinim.dxf",
                                     "P02_B_acinim.dxf"], str(ad("acinim")))
    dogru("LZR", ad("lazer") == ["LZR/P01_A_Lzr.dxf"], str(ad("lazer")))
    dogru("PDF", ad("pdf") == ["PDF/P01_A_A3.pdf"], str(ad("pdf")))
    dogru("dosya_bul klasörü tercih ediyor",
          IS.dosya_bul(kok, "P01_A.dxf") == os.path.join(kok, "DXF", "P01_A.dxf"))
    dogru("dosya_bul eski kökü de buluyor",
          IS.dosya_bul(kok, "P02_B.dxf") == os.path.join(kok, "P02_B.dxf"))

    print("\n-- model özeti içeriğe bağlı")
    st = os.path.join(kok, "model.stp")
    yaz(st, "ISO-10303-21;\nDATA;\n#1=X();\nENDSEC;\n")
    kopya = os.path.join(kok, "kopya.stp")
    shutil.copy(st, kopya)
    oz = IS.dosya_ozeti(st)
    dogru("kopyanın özeti aynı", IS.dosya_ozeti(kopya) == oz)
    with open(kopya, "a", encoding="utf-8") as f:
        f.write("#2=Y();\n")
    dogru("içerik değişince özet değişiyor", IS.dosya_ozeti(kopya) != oz)

    print("\n-- güncel mi")
    ayar = IS.cizim_ayari({"gizli": True, "en_az_delik": 1.0,
                           "gorunusler": ["ON", "UST"], "kesit": False})
    im = IS.imza(oz, ayar, "celik", 7.85, 1, 2)
    IS.model_kaydet(kok, st)
    IS.cizim_kaydet(kok, "dxf", "P01_A.dxf", imza=im, kod="A", step_ozet=oz)
    dogru("aynı model + ayar -> güncel", IS.guncel_mi(kok, "P01_A.dxf", im))
    ayar2 = dict(ayar, kesit=True)
    dogru("kesit açılınca -> güncel DEĞİL",
          not IS.guncel_mi(kok, "P01_A.dxf", IS.imza(oz, ayar2, "celik",
                                                     7.85, 1, 2)))
    dogru("malzeme değişince -> güncel DEĞİL",
          not IS.guncel_mi(kok, "P01_A.dxf", IS.imza(oz, ayar, "paslanmaz",
                                                     7.9, 1, 2)))
    dogru("model değişince -> güncel DEĞİL",
          not IS.guncel_mi(kok, "P01_A.dxf",
                           IS.imza(IS.dosya_ozeti(kopya), ayar, "celik",
                                   7.85, 1, 2)))
    dogru("kaydı olmayan eski çizim -> güncel DEĞİL",
          not IS.guncel_mi(kok, "P02_B.dxf", im))
    os.remove(os.path.join(kok, "DXF", "P01_A.dxf"))
    os.remove(os.path.join(kok, "P01_A.dxf"))
    dogru("dosyası silinmiş -> güncel DEĞİL",
          not IS.guncel_mi(kok, "P01_A.dxf", im))

    print("\n-- açınım tablosu birleşiyor")
    ak = IS.alt_klasor(kok, "acinim", True)
    bas = ["poz", "kod", "ad", "dxf"]
    for i in range(1, 6):
        yaz(os.path.join(ak, f"P0{i}_{i}_acinim.dxf"))
    IS.csv_birlestir(os.path.join(ak, "ACINIM.csv"), bas,
                     [[i, f"K{i}", f"parca {i}", f"P0{i}_{i}_acinim.dxf"]
                      for i in range(1, 6)], {f"K{i}" for i in range(1, 6)}, ak)
    # 2 ve 4 yeniden üretiliyor; 5'in dosyası silinmiş
    os.remove(os.path.join(ak, "P05_5_acinim.dxf"))
    n = IS.csv_birlestir(os.path.join(ak, "ACINIM.csv"), bas,
                         [[2, "K2", "parca 2 yeni", "P02_2_acinim.dxf"],
                          [4, "K4", "parca 4 yeni", "P04_4_acinim.dxf"]],
                         {"K2", "K4"}, ak)
    with open(os.path.join(ak, "ACINIM.csv"), encoding="utf-8-sig") as f:
        sat = list(csv.DictReader(f, delimiter=";"))
    dogru("4 satır (5'in dosyası yok)", n == 4 and len(sat) == 4, str(n))
    dogru("sıra ve yeniler", [(r["kod"], r["ad"]) for r in sat] == [
        ("K1", "parca 1"), ("K2", "parca 2 yeni"), ("K3", "parca 3"),
        ("K4", "parca 4 yeni")], str([(r["kod"], r["ad"]) for r in sat]))

    print("\n-- yapılamayanlar listesi")
    hy = os.path.join(ak, "ACINIM_yapilamayanlar.txt")
    IS.hata_birlestir(hy, [("K7", "eksen paralel değil"), ("K8", "kontur\nyok")],
                      {"K7", "K8"})
    IS.hata_birlestir(hy, [("K9", "kalınlık yok")], {"K7", "K9"})
    ic = open(hy, encoding="utf-8").read()
    dogru("K7 başardı, düştü; K8 korunuyor; K9 eklendi",
          "K7" not in ic and "K8\n    kontur\n    yok" in ic and "K9" in ic, ic)
    IS.hata_birlestir(hy, [], {"K8", "K9"})
    dogru("hepsi başarınca dosya siliniyor", not os.path.exists(hy))

    print("\n-- klasör özeti ve süreler")
    IS.islem_kaydet(kok, "BOM çıkarma", 41.2)
    IS.islem_kaydet(kok, "Tüm çizimler", 725.0, "iptal")
    d = IS.durum_oku(kok)
    dogru("iki işlem kayıtlı", [r["ad"] for r in d["islemler"]]
          == ["BOM çıkarma", "Tüm çizimler"])
    dogru("süre metni", IS.sure_metni(725) == "12 dk 05 sn"
          and IS.sure_metni(41.2) == "41 sn" and IS.sure_metni(7322) == "2 sa 02 dk",
          IS.sure_metni(725))
    r = IS.cikti_durumu(kok, st)
    dogru("özet sayıları", (r["dxf"], r["montaj"], r["acinim"], r["lazer"],
                            r["pdf"]) == (1, 1, 6, 1, 1),
          str((r["dxf"], r["montaj"], r["acinim"], r["lazer"], r["pdf"])))
    dogru("aynı model tanındı", r["ayni_model"] is True)
    dogru("model değişince uyarı",
          IS.cikti_durumu(kok, kopya)["ayni_model"] is False
          and "DEĞİŞMİŞ" in IS.durum_metni(IS.cikti_durumu(kok, kopya)))
    IS.model_kaydet(kok, kopya)          # yeni model okundu
    dogru("yeni model okununca eski çizimler 'aynı model' görünmüyor",
          IS.cikti_durumu(kok, kopya)["ayni_model"] is False)

    print("\n-- bozuk durum dosyası")
    with open(os.path.join(kok, IS.DURUM_DOSYASI), "w") as f:
        f.write("{bozuk")
    d = IS.durum_oku(kok)
    dogru("boş durumla devam", d["dxf"] == {} and d["islemler"] == [])
    IS.islem_kaydet(kok, "X", 1)
    dogru("üstüne yazılabiliyor", IS.durum_oku(kok)["islemler"][0]["ad"] == "X")
finally:
    shutil.rmtree(kok, ignore_errors=True)

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                     else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(1 if HATA else 0)
