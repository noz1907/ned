# -*- coding: utf-8 -*-
"""Kaynak resmi (pf14_kaynak): grup, görünürlük, konum, PDF.

Sentetik model: 200 x 100 x 5 taban sacı, üstünde 5 mm dik sac (T
birleşimi). Dik sacın iki yanında köşe dikişi:
  * D1: sağ yanda, y = 20 .. 60 (40 mm), bacak 4 -> kenardan 20 mm,
  * D2: sol yanda, y = 0 .. 30 (30 mm) -> kenardan başlar (0).
Ayrıca uzakta, kendi başına ikinci bir kaynaklı grup (iki küçük sac +
bir dikiş) -> iki ayrı resim.

Denetlenen:
  1. dikişler birleştirdikleri parçalara göre gruplanıyor mu (iki grup),
  2. dikiş ölçüsü (köşe, a = 4/√2, boy),
  3. KONUM: kök çizgisinin ucundan dikiş başına mesafe (20 ve 0),
  4. görünürlük: iki dikiş de bir görünüşte net görünüyor,
  5. PDF: KAYNAK/<grup>_kaynak.pdf, A3 sayfalar, eski dosya temizleniyor.
"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf14_kaynak as KR                                       # noqa: E402

from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakePolygon,    # noqa: E402
                                BRepBuilderAPI_MakeFace)
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakePrism  # noqa: E402
from OCP.gp import gp_Pnt, gp_Vec                              # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    if kosul:
        print(f"  tamam {ad}")
    else:
        print(f"  HATA  {ad}  {neden}")
        HATA.append(ad)


def kutu(x0, y0, z0, x1, y1, z1):
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), gp_Pnt(x1, y1, z1)).Shape()


def ucgen_prizma(a, b, c, y0, y1):
    """xz düzleminde a, b, c üçgeni, y0'dan y1'e uzatılmış (köşe dikişi)."""
    pl = BRepBuilderAPI_MakePolygon(gp_Pnt(a[0], y0, a[1]), gp_Pnt(b[0], y0, b[1]),
                                    gp_Pnt(c[0], y0, c[1]), True).Wire()
    f = BRepBuilderAPI_MakeFace(pl).Face()
    return BRepPrimAPI_MakePrism(f, gp_Vec(0, y1 - y0, 0)).Shape()


def model():
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    def kati(s):
        ex = TopExp_Explorer(s, TopAbs_SOLID)
        return TopoDS.Solid_s(ex.Current())
    k = [("TABAN", kati(kutu(0, 0, 0, 200, 100, 5))),
         ("DIK", kati(kutu(50, 0, 5, 55, 100, 85))),
         ("KAYNAK_1", kati(ucgen_prizma((55, 5), (59, 5), (55, 9), 20, 60))),
         ("KAYNAK_2", kati(ucgen_prizma((50, 5), (46, 5), (50, 9), 0, 30))),
         # uzakta ikinci grup
         ("LAMA_A", kati(kutu(1000, 0, 0, 1080, 40, 4))),
         ("LAMA_B", kati(kutu(1000, 0, 4, 1004, 40, 44))),
         ("KAYNAK_3", kati(ucgen_prizma((1004, 4), (1007, 4), (1004, 7), 0, 40)))]
    komp = []
    for i, (ad, sh) in enumerate(k):
        from OCP.BRepGProp import BRepGProp
        from OCP.GProp import GProp_GProps
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(sh, g)
        komp.append({"kod": ad, "ad": ad, "indeks": [i], "adet": 1, "hacim_mm3": g.Mass(),
                     "sinif": "kaynak" if ad.startswith("KAYNAK") else "parca", "tip": ""})
    agac = {"ad": "MONTAJ", "montaj": True, "alt": [
        {"ad": "GOVDE_GRUBU", "montaj": True, "alt": [
            {"ad": ad, "katilar": [i], "tum": [i], "alt": []} for i, (ad, _) in enumerate(k[:4])]},
        {"ad": "LAMA_GRUBU", "montaj": True, "alt": [
            {"ad": ad, "katilar": [i + 4], "tum": [i + 4], "alt": []}
            for i, (ad, _) in enumerate(k[4:])]},
        {"ad": "KAYNAKLAR", "montaj": True, "alt": []}]}
    return k, komp, agac


def main():
    print("kaynak resmi denetimi")
    kayit, komp, agac = model()
    gr = KR.kaynakli_gruplar(kayit, komp, agac, log=lambda t: None)
    dogru("iki kaynaklı grup", len(gr) == 2, [g["ad"] for g in gr])
    govde = next((g for g in gr if g["dugum_ad"] == "GOVDE_GRUBU"), None)
    dogru("gövde grubu: 2 dikiş, 2 parça", govde and len(govde["dikis"]) == 2
          and sorted(govde["parca"]) == [0, 1], govde)
    lama = next((g for g in gr if g["dugum_ad"] == "LAMA_GRUBU"), None)
    dogru("lama grubu: 1 dikiş", lama and len(lama["dikis"]) == 1, lama)

    satirlar = [{"kod": k["kod"], "poz": i + 1} for i, k in enumerate(komp)
                if k["sinif"] != "kaynak"]
    with tempfile.TemporaryDirectory() as on:
        kl = os.path.join(on, "KAYNAK")
        os.makedirs(kl)
        eski = os.path.join(kl, "ESKI_GRUP_kaynak.pdf")
        open(eski, "w").close()
        yaz = KR.kaynak_resimleri(on, kayit, komp, agac, satirlar, log=lambda t: None)
        dogru("iki PDF", sorted(yaz) == ["GOVDE_GRUBU_kaynak.pdf", "LAMA_GRUBU_kaynak.pdf"],
              yaz)
        dogru("eski kaynak resmi silindi", not os.path.exists(eski))
        dogru("KAYNAK klasöründe DXF yok",
              not any(a.lower().endswith(".dxf") for a in os.listdir(kl)))
        y = os.path.join(kl, "GOVDE_GRUBU_kaynak.pdf")
        bas = open(y, "rb").read(5)
        dogru("PDF dosyası", bas == b"%PDF-", bas)
        try:
            import pymupdf
            d = pymupdf.open(y)
            r = d[0].rect
            dogru("A3 yatay (420 x 297 mm)",
                  abs(r.width / 72 * 25.4 - 420) < 1 and abs(r.height / 72 * 25.4 - 297) < 1,
                  (r.width, r.height))
        except ImportError:
            pass

    # dikiş ayrıntısı: resmi bir kez daha üretip dönen listeye bak
    with tempfile.TemporaryDirectory() as on:
        from pf3_olcu import GORUNUS  # noqa: F401 - O modülü yüklensin
        import pf3_olcu as O
        ds = KR.kaynak_resmi(O, kayit, komp, govde, satirlar,
                             os.path.join(on, "g_kaynak.pdf"))
    by = {kayit[d["j"]][0]: d for d in ds}
    d1, d2 = by.get("KAYNAK_1"), by.get("KAYNAK_2")
    dogru("D1 köşe dikişi", d1 and (d1["olcu"].get("tip") or "").startswith("köşe"),
          d1 and d1["olcu"])
    dogru("D1 a = 4/√2", d1 and abs(d1["olcu"]["a_mm"] - 4 / math.sqrt(2)) < 0.05,
          d1 and d1["olcu"].get("a_mm"))
    dogru("D1 boy 40", d1 and abs(d1["olcu"]["boy_mm"] - 40) < 0.1,
          d1 and d1["olcu"].get("boy_mm"))
    dogru("D1 kenardan 20", d1 and d1.get("konum") and d1["konum"]["deger"] == 20,
          d1 and d1.get("konum"))
    dogru("D2 kenardan başlıyor (0)", d2 and d2.get("konum") and d2["konum"]["deger"] == 0,
          d2 and d2.get("konum"))
    dogru("D1 başlangıcı ölçülen uç (y = 20)", d1 and abs(d1["p0"][1] - 20) < 0.1,
          d1 and d1["p0"])
    dogru("iki dikiş görünür", all(d["gorunur"] for d in ds), [d["gorunur"] for d in ds])
    dogru("numaralar K1, K2", sorted(d["no"] for d in ds) == ["K1", "K2"],
          [d["no"] for d in ds])

    # kaynakta ondalık yok: 2,7 -> 3, 1,77 -> 2, 24,6 -> 25
    import pf3_olcu as O
    import pf9_excel as XL
    dogru("yarım yukarı tam sayı", (XL.tam(2.7), XL.tam(1.77), XL.tam(2.5), XL.tam(24.49))
          == (3, 2, 3, 24))
    sat, aoz, _ = O.kaynak_ozet_satirlari([
        {"sinif": "kaynak", "ad": "K0 25 MM TEK KAYNAK", "adet": 2,
         "kaynak_olcu": {"tip": "köşe 3 x 3 (dışbükey)", "boy_mm": 24.6, "kesit_mm2": 4.9,
                         "a_mm": 1.77, "hacim_mm3": 120.0}}])
    dogru("KAYNAK listesinde a, boy, kesit tam sayı",
          sat and sat[0][3] == 25 and sat[0][4] == 5 and sat[0][5] == 2 and sat[0][6] == 50,
          sat)
    dogru("a sınıfı 'a 2'", aoz and aoz[0][0] == "a 2", aoz)

    print()
    if HATA:
        print(f"{len(HATA)} HATA")
        sys.exit(1)
    print("hepsi tamam")


if __name__ == "__main__":
    main()
