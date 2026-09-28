# -*- coding: utf-8 -*-
"""Excel çıktısı (pf9_excel): .xlsx'te sayı SAYI, yazı YAZI olmalı.

Kullanıcının gördüğü hata: CSV'deki 15.2243 kg, Türkçe Excel'de
152.243 (nokta binlik ayırıcı) görünüyordu; poz 1.1 tarihe dönüyordu.
Denetlenen:
  - .xlsx geçerli bir zip + XML; sayfa adları, başlık, dondurulmuş satır
  - kg sayı hücresi (t yok), poz "1.1" ve kod "001" yazı hücresi
  - Türkçe harf ve XML'e özel karakterler bozulmuyor
  - CSV Türkçe Excel biçiminde: ondalık virgül, ; ayırıcı
  - eski sürümün noktalı CSV'si okunup birleştirilince .xlsx'e SAYI yazılıyor
  - açık (kilitli) dosyanın yerine _yeni.xlsx yazılıyor

    python3 test/excel_denetimi.py
"""
import csv
import os
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf7_is as IS                                              # noqa: E402
import pf9_excel as XL                                           # noqa: E402

HATA = []
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def hucreler(yol, sayfa=1):
    """{ "A2": ("n", "15.2243"), "B2": ("s", "001") }"""
    z = zipfile.ZipFile(yol)
    for ad in z.namelist():
        ET.fromstring(z.read(ad))                     # her parça geçerli XML
    x = ET.fromstring(z.read(f"xl/worksheets/sheet{sayfa}.xml"))
    out = {}
    for c in x.iter("{%s}c" % NS["m"]):
        if c.get("t") == "inlineStr":
            out[c.get("r")] = ("s", c.find("m:is/m:t", NS).text)
        else:
            out[c.get("r")] = ("n", c.find("m:v", NS).text)
    return out, z


kok = tempfile.mkdtemp(prefix="excel_")
try:
    print("-- BOM tablosu")
    alan = ["poz", "kod", "ad", "adet", "olcu", "kg_adet", "toplam_kg"]
    sat = [{"poz": 1, "kod": "001", "ad": "Bağlama elemanı <şğüçöıİ> & Co",
            "adet": 2, "olcu": "1513.76x1281.19x1.0", "kg_adet": 15.2243,
            "toplam_kg": 30.4486},
           {"poz": "1.1", "kod": "A", "ad": "x", "adet": 1, "kg_adet": 1e-05,
            "toplam_kg": ""}]
    y = XL.tablo_yaz(os.path.join(kok, "BOM.csv"), alan, XL.sozlukten(alan, sat), "BOM")
    h, z = hucreler(y)
    dogru("kg SAYI", h["F2"] == ("n", "15.2243"), str(h.get("F2")))
    dogru("adet SAYI", h["D2"] == ("n", "2"), str(h.get("D2")))
    dogru("poz 1.1 YAZI (tarih olmaz)", h["A3"] == ("s", "1.1"), str(h.get("A3")))
    dogru("kod 001 YAZI (sıfırlar kalır)", h["B2"] == ("s", "001"), str(h.get("B2")))
    dogru("Türkçe ve özel karakter", h["C2"] == ("s", "Bağlama elemanı <şğüçöıİ> & Co"),
          str(h.get("C2")))
    dogru("boş hücre yazılmıyor", "G3" not in h)
    wb = z.read("xl/workbook.xml").decode()
    dogru("sayfa adı", 'name="BOM"' in wb)
    dogru("başlık satırı dondurulmuş", b'state="frozen"' in z.read("xl/worksheets/sheet1.xml"))
    with open(os.path.join(kok, "BOM.csv"), encoding="utf-8-sig") as f:
        satir = f.read().splitlines()
    dogru("CSV ondalık virgül", satir[1].endswith(";15,2243;30,4486"), satir[1])
    dogru("CSV küçük sayı bilimsel yazılmıyor", ";0,00001;" in satir[2], satir[2])

    print("\n-- açınım tablosu: eski (noktalı) satır + yeni satır")
    ak = os.path.join(kok, "ACINIM")
    os.makedirs(ak)
    for d in ("P01_A_acinim.dxf", "P02_B_acinim.dxf"):
        open(os.path.join(ak, d), "w").write("0\nEOF\n")
    with open(os.path.join(ak, "ACINIM.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["poz", "kod", "kalinlik_mm", "dxf"])
        w.writerow(["1", "A", "1.5", "P01_A_acinim.dxf"])        # eski sürüm: nokta
    IS.csv_birlestir(os.path.join(ak, "ACINIM.csv"), ["poz", "kod", "kalinlik_mm", "dxf"],
                     [[2, "B", 2.0, "P02_B_acinim.dxf"]], {"B"}, ak)
    h, _ = hucreler(os.path.join(ak, "ACINIM.xlsx"))
    dogru("eski 1.5 -> sayı", h["C2"] == ("n", "1.5"), str(h.get("C2")))
    dogru("yeni 2.0 -> sayı", h["C3"] == ("n", "2.0") or h["C3"] == ("n", "2"),
          str(h.get("C3")))
    with open(os.path.join(ak, "ACINIM.csv"), encoding="utf-8-sig") as f:
        ic = f.read()
    dogru("CSV'de eski satır korunuyor", "P01_A_acinim.dxf" in ic)

    print("\n-- sayiya")
    for sut, v, bek in (("kalinlik_mm", "1,5", 1.5), ("kalinlik_mm", "2", 2),
                        ("poz", "1.1", "1.1"), ("kod", "0012", "0012"),
                        ("kg_adet", "15.2243", 15.2243), ("ad", "3,5", "3,5")):
        dogru(f"{sut}={v!r}", XL.sayiya(sut, v) == bek, repr(XL.sayiya(sut, v)))

    print("\n-- Türkçe yazım: ondalık virgül, binlik nokta")
    for v, nd, bek in ((1513.76, None, "1.513,76"), (4.2, None, "4,2"),
                       (-1234.5, None, "-1.234,5"), (1234567.891, None, "1.234.567,891"),
                       (0.5, 3, "0,5"), (1234, None, "1.234"), (0.00001, None, "0,00001")):
        dogru(f"tr({v!r}) = {bek}", XL.tr(v, nd) == bek, XL.tr(v, nd))
    dogru("sabit basamak 1.513,760", XL.tr(1513.76, 3, sade=False) == "1.513,760")
    for t, bek in (("1.513,76", 1513.76), ("3.027,520", 3027.52), ("15,22", 15.22),
                   ("1.234.567", 1234567), ("152.243", 152.243), ("12", 12),
                   ("abc", None), ("1,2,3", None)):
        dogru(f"oku {t!r} -> {bek}", XL.sayi_oku(t) == bek, repr(XL.sayi_oku(t)))
    dogru("CSV binlik nokta (1.513,76)", XL.tr_sayi(1513.76) == "1.513,76")
    dogru("CSV tam değer binliksiz (eski noktalı ondalıkla karışmaz)",
          XL.tr_sayi(1234.0) == "1234" and XL.sayi_oku(XL.tr_sayi(1234.0)) == 1234)
    for v in (1513.76, 0.0123, 98765.4321, 7.85, 152.243):
        dogru(f"gidiş-dönüş {v}", XL.sayi_oku(XL.tr_sayi(v)) == v)
    st = z.read("xl/styles.xml").decode()
    dogru("xlsx tam sayı biçimi binlikli (numFmtId 3 = #,##0)", 'numFmtId="3"' in st)
    dogru("xlsx ondalık biçimi binlikli (#,##0.000)", "#,##0.000" in st)

    print("\n-- açık (kilitli) dosya")
    kilit = os.path.join(kok, "kilitli.xlsx")
    os.makedirs(kilit)                    # os.replace dizinin üstüne yazamaz
    y2 = XL.xlsx_yaz(kilit, [("A", ["x"], [[1]])])
    dogru("yanına _yeni.xlsx yazıldı", y2.endswith("kilitli_yeni.xlsx")
          and os.path.isfile(y2), y2)
finally:
    shutil.rmtree(kok, ignore_errors=True)

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                     else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(1 if HATA else 0)
