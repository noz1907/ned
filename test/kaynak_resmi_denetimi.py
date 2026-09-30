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
    # TEK DURAN kaynağa konum ölçüsü verilmez: yeri parçadan belli
    # (kullanıcı). Konum hesabının kendisi yine doğru olmalı.
    dogru("tek duran kaynakta konum yok", d1 and d1.get("konum") is None
          and d2 and d2.get("konum") is None, (d1 and d1.get("konum"), d2 and d2.get("konum")))
    dogru("listede konum '-'", d1 and KR._konum_yazisi(d1) == "-", d1 and KR._konum_yazisi(d1))
    for d_, bek in ((d1, 20), (d2, 0)):
        if not d_:
            continue
        s_ = kayit[d_["j"]][1]
        p0, p1, o_, y_ = KR.dikis_ekseni(s_)
        k_ = KR.konum_hesapla({"sh": s_, "olcu": d_["olcu"], "p0": p0, "p1": p1,
                               "orta": o_, "yon": y_}, [kayit[0][1], kayit[1][1]])
        dogru(f"konum hesabı {kayit[d_['j']][0]}: kenardan {bek}",
              k_ is not None and k_["deger"] == bek, k_)
    dogru("iki dikiş görünür", all(d["gorunur"] for d in ds), [d["gorunur"] for d in ds])
    dogru("numaralar K1, K2", sorted(d["no"] for d in ds) == ["K1", "K2"],
          [d["no"] for d in ds])

    # RESMİN DÜZENİ (kullanıcıyla denenip onaylandı): genel görünüş yalnız
    # dört izometrik, bölgeler tek harf, detaylar izometrik, "dikiş" yok
    import pf3_olcu as O
    yakala = []
    asil = KR.pdf_yaz
    KR.pdf_yaz = lambda sayfalar, yol: yakala.extend(sayfalar)
    try:
        KR.kaynak_resmi(O, kayit, komp, govde, satirlar, "x_kaynak.pdf")
    finally:
        KR.pdf_yaz = asil
    yazi = [e.dxf.text for doc in yakala for e in doc.modelspace().query("TEXT")]
    basliklar = [t for t in yazi if "(" in t and ":" in t]
    for ad in ("İZOMETRİK ÖN-SAĞ", "İZOMETRİK ÖN-SOL", "İZOMETRİK ALTTAN ÖN-SAĞ",
               "İZOMETRİK ALTTAN ÖN-SOL"):
        dogru(f"genel görünüşte {ad}", any(t.startswith(ad + " ") for t in basliklar),
              basliklar)
    dogru("genel görünüşte dik görünüş yok",
          not any(t.split("  ")[0].strip() in ("ÖN", "ÜST", "SAĞ") for t in basliklar),
          basliklar)
    dogru("detay başlığında bölge harfi", any(t.startswith("DETAY A") and "BÖLGE A" in t
                                              for t in yazi), basliklar)
    dogru("kâğıtta 'dikiş' kelimesi yok", not any("dikiş" in t.lower() for t in yazi),
          [t for t in yazi if "dikiş" in t.lower()])

    # bölgeler: 250 kaynak -> en çok 23 bölge, her kaynak tek bölgede,
    # harfler tek
    import random
    rnd = random.Random(1)
    sahte = [{"orta": (rnd.uniform(0, 2500), rnd.uniform(0, 900), rnd.uniform(0, 300))}
             for _ in range(250)]
    goz, xr = O.GORUNUS["UST"]
    bl = KR.bolgeler(sahte, goz, xr, 2500.0)
    dogru("250 kaynak harf sayısı kadar bölgeye sığdı", len(bl) <= len(KR.HARFLER), len(bl))
    dogru("her kaynak tek bölgede", sorted(id(d) for b in bl for d in b)
          == sorted(id(d) for d in sahte))

    # serbest ölçek: sayfayı doldurur
    dogru("ölçek 1:17 (standart 1:20'ye küçültülmez)",
          abs(KR.olcek_sec(1 / 16.4) - 1 / 17) < 1e-12, KR.olcek_sec(1 / 16.4))
    dogru("büyütme 2:1", KR.olcek_sec(2.4) == 2.0, KR.olcek_sec(2.4))

    # CAD BOŞLUĞU: dikiş ikinci parçaya 1,2 mm uzak çizilmiş -> yine iki
    # parçayı birleştirir; 4 mm uzaktaki parça bağlanmaz
    k2 = [("A", kutu(0, 0, 0, 100, 40, 4)), ("B", kutu(0, 0, 5.2, 4, 40, 44)),
          ("UZAK", kutu(10, 0, 8, 14, 40, 44)),
          ("KAYNAK_B", ucgen_prizma((4, 4), (7, 4), (4, 7), 0, 40))]
    komp2 = [{"kod": ad, "ad": ad, "indeks": [i], "adet": 1, "hacim_mm3": 1.0,
              "sinif": "kaynak" if ad.startswith("KAYNAK") else "parca", "tip": ""}
             for i, (ad, _) in enumerate(k2)]
    agac2 = {"ad": "M", "montaj": True, "alt": [
        {"ad": ad, "katilar": [i], "tum": [i], "alt": []} for i, (ad, _) in enumerate(k2)]}
    g2 = KR.kaynakli_gruplar(k2, komp2, agac2, log=lambda t: None)
    dg = g2[0]["degen"][3] if g2 else []
    dogru("1,2 mm boşluklu dikiş iki parçaya bağlandı", sorted(dg) == [0, 1], dg)

    # SIRALI KAYNAK: 400 mm dik sacın bir yanında art arda üç kaynak
    # (y 20..60, 110..150, 200..240 -> kenardan 20, ara 50, 50), öbür
    # yanında y 20..60'ta bir kaynak (yan yana: zincire girmez)
    zk = [("TABAN", kutu(0, 0, 0, 200, 400, 5)), ("DIK", kutu(50, 0, 5, 55, 400, 85)),
          ("Z1", ucgen_prizma((55, 5), (59, 5), (55, 9), 20, 60)),
          ("Z2", ucgen_prizma((55, 5), (59, 5), (55, 9), 110, 150)),
          ("Z3", ucgen_prizma((55, 5), (59, 5), (55, 9), 200, 240)),
          ("YAN", ucgen_prizma((50, 5), (46, 5), (50, 9), 20, 60))]
    zkomp = [{"kod": ad, "ad": ad, "indeks": [i], "adet": 1, "hacim_mm3": 1.0,
              "sinif": "parca" if i < 2 else "kaynak", "tip": ""}
             for i, (ad, _) in enumerate(zk)]
    zagac = {"ad": "Z", "montaj": True, "alt": [
        {"ad": ad, "katilar": [i], "tum": [i], "alt": []} for i, (ad, _) in enumerate(zk)]}
    zg = KR.kaynakli_gruplar(zk, zkomp, zagac, log=lambda t: None)
    zsat = [{"kod": "TABAN", "poz": 1}, {"kod": "DIK", "poz": 2}]
    yakala = []
    KR.pdf_yaz = lambda sayfalar, yol: yakala.extend(sayfalar)
    try:
        zd = KR.kaynak_resmi(O, zk, zkomp, zg[0], zsat, "z_kaynak.pdf")
    finally:
        KR.pdf_yaz = asil
    ad_ = {zk[d["j"]][0]: d for d in zd}
    z1, z2, z3, yan = (ad_.get(a) for a in ("Z1", "Z2", "Z3", "YAN"))
    dogru("zincirin ilki kenardan 20", z1 and (z1.get("konum") or {}).get("deger") == 20,
          z1 and z1.get("konum"))
    dogru("ikinci: birinciyle ara 50", z2 and z2.get("ara") and z2["ara"]["deger"] == 50
          and z2["ara"]["onceki"] is z1, z2 and z2.get("ara"))
    dogru("üçüncü: ikinciyle ara 50", z3 and z3.get("ara") and z3["ara"]["deger"] == 50
          and z3["ara"]["onceki"] is z2, z3 and z3.get("ara"))
    dogru("listede 'kenardan 20' ve 'K + 50'",
          z1 and KR._konum_yazisi(z1) == "kenardan 20"
          and KR._konum_yazisi(z2) == f"{z1['no']} + 50", z1 and (KR._konum_yazisi(z1),
                                                               KR._konum_yazisi(z2)))
    dogru("öbür yüzdeki yan yana kaynak zincire girmedi",
          yan and "zincir_sira" not in yan and yan.get("konum") is None, yan and yan.get("ara"))
    olcu = [e.dxf.text for doc in yakala for e in doc.modelspace().query("TEXT")
            if e.dxf.layer == "OLCU"]
    dogru("resimde başlangıç (20) ve ara (50) ölçüsü", "20" in olcu and "50" in olcu, olcu)
    # küçük üründe resimde ölçü yok, listede var
    eski = KR.KUCUK_URUN
    KR.KUCUK_URUN = 10000.0
    yakala.clear()
    KR.pdf_yaz = lambda sayfalar, yol: yakala.extend(sayfalar)
    try:
        zd2 = KR.kaynak_resmi(O, zk, zkomp, zg[0], zsat, "z_kaynak.pdf")
    finally:
        KR.pdf_yaz = asil
        KR.KUCUK_URUN = eski
    olcu = [e.dxf.text for doc in yakala for e in doc.modelspace().query("TEXT")
            if e.dxf.layer == "OLCU" and e.dxf.text in ("20", "50")]
    dogru("küçük üründe resimde konum ölçüsü yok", not olcu, olcu)
    dogru("küçük üründe listede yine var",
          any(KR._konum_yazisi(d).endswith("+ 50") for d in zd2))

    # ZİNCİRİN İKİ UCU KÖŞEDE: 260 mm birleşmede y 0..40, 110..150,
    # 220..260 -> ilki "kenardan", ortadaki ara 70, sonuncusu "kenara
    # kadar" (ölçüsü yok; kullanıcı: "- o -" üçlüsünde yalnız ortadaki).
    # Dik sacın öbür yanında AYNI yerlerde üç kaynak: simetrik zincir,
    # ölçüleri tekrar yazılmaz ("SİM.").
    def ucgen_sol(y0, y1):
        return ucgen_prizma((50, 5), (46, 5), (50, 9), y0, y1)
    # taban 320: küçük ürün sayılmasın (resimde ölçü çizilsin)
    uk = [("TABAN", kutu(0, 0, 0, 320, 260, 5)), ("DIK", kutu(50, 0, 5, 55, 260, 85)),
          ("U1", ucgen_prizma((55, 5), (59, 5), (55, 9), 0, 40)),
          ("U2", ucgen_prizma((55, 5), (59, 5), (55, 9), 110, 150)),
          ("U3", ucgen_prizma((55, 5), (59, 5), (55, 9), 220, 260)),
          ("S1", ucgen_sol(0, 40)), ("S2", ucgen_sol(110, 150)), ("S3", ucgen_sol(220, 260))]
    ukomp = [{"kod": ad, "ad": ad, "indeks": [i], "adet": 1, "hacim_mm3": 1.0,
              "sinif": "parca" if i < 2 else "kaynak", "tip": ""}
             for i, (ad, _) in enumerate(uk)]
    uagac = {"ad": "U", "montaj": True, "alt": [
        {"ad": ad, "katilar": [i], "tum": [i], "alt": []} for i, (ad, _) in enumerate(uk)]}
    ug = KR.kaynakli_gruplar(uk, ukomp, uagac, log=lambda t: None)
    yakala.clear()
    KR.pdf_yaz = lambda sayfalar, yol: yakala.extend(sayfalar)
    try:
        ud = KR.kaynak_resmi(O, uk, ukomp, ug[0], zsat, "u_kaynak.pdf")
    finally:
        KR.pdf_yaz = asil
    ua = {uk[d["j"]][0]: d for d in ud}
    yaz_ = {a: KR._konum_yazisi(d) for a, d in ua.items()}
    # hangi yan asıl, hangisi simetrik: numarası küçük olan asıl
    asil_, sim_ = (("U", "S") if int(ua["U1"]["no"][1:]) < int(ua["S1"]["no"][1:])
                   else ("S", "U"))
    dogru("köşeden başlayan: 'kenardan'", yaz_[asil_ + "1"] == "kenardan", yaz_)
    dogru("ortadaki: ara 70", yaz_[asil_ + "2"] == f"{ua[asil_ + '1']['no']} + 70", yaz_)
    dogru("köşede biten: 'kenara kadar'", yaz_[asil_ + "3"] == "kenara kadar", yaz_)
    dogru("karşı yandaki aynı düzen simetrik",
          all(yaz_[sim_ + str(i)] == f"SİM. {ua[asil_ + str(i)]['no']}" for i in (1, 2, 3)), yaz_)
    olcu = [e.dxf.text for doc in yakala for e in doc.modelspace().query("TEXT")
            if e.dxf.layer == "OLCU"]
    dogru("resimde yalnız ortadaki ara (70) - bir kez", olcu.count("70") == 1, olcu)
    dogru("resimde SİM. notu", any(t.startswith("SİM.") for t in olcu), olcu)

    # KIRMIZI yalnız dikiş: ortası dikişin yanından geçen uzun sac kenarı
    # eskiden baştan sona kırmızıydı, dikiş içinde kayboluyordu
    for gad in ("ISO1", "ISO3", "ON"):
        R = KR._Resim(O, [kayit[0][1], kayit[1][1]], [kayit[2][1], kayit[3][1]], gad)
        uz = [sum(math.dist(a, b) for a, b in zip(q, q[1:]))
              for k_, q in R.cizgi if k_ == "KAYNAK"]
        dogru(f"{gad}: kırmızı çizgi var, hiçbiri dikişten (40) uzun değil",
              uz and max(uz) <= 41.0, [round(v, 1) for v in sorted(uz)[-3:]])
    # dikiş ekseni: mavi (5), kesikli
    doc0 = yakala[-1] if yakala else None
    eks = [e for doc in yakala for e in doc.modelspace().query("LINE") if e.dxf.layer == "EKSEN"]
    dogru("dikiş ekseni çizildi", len(eks) >= 6, len(eks))
    if doc0:
        ly = doc0.layers.get("EKSEN")
        dogru("eksen mavi ve kesikli", ly.dxf.color == 5 and ly.dxf.linetype == "KESIK",
              (ly.dxf.color, ly.dxf.linetype))
    # YAN YANA AYNI ÖZELLİKLİ dikişler tek sembol, en çok 3 ok; her
    # numara bir kez yazılır
    balon = [e.dxf.text for doc in yakala for e in doc.modelspace().query("TEXT")
             if e.dxf.layer == "OLCU" and e.dxf.text.startswith("K")]
    def ac(b_):                           # "K2-K4" -> K2, K3, K4
        out = []
        for n in b_.split(","):
            if "-" in n:
                a_, z_ = (int(x.strip()[1:]) for x in n.split("-"))
                out += [f"K{i}" for i in range(a_, z_ + 1)]
            else:
                out.append(n.strip())
        return out
    nolar = [n for b_ in balon for n in ac(b_)]
    dogru("her dikiş numarası bir kez", sorted(nolar) == sorted(d["no"] for d in ud), balon)
    dogru("yan yana aynı dikişler birleşti (tek sembol, birden çok ok)",
          any(len(ac(b_)) > 1 for b_ in balon) and all(len(ac(b_)) <= 3 for b_ in balon), balon)
    dogru("etiket birleşince sembol sayısı azaldı", len(balon) < len(ud), (len(balon), len(ud)))

    # YAZILAR ÜST ÜSTE BİNMEZ: bütün sayfalarda ölçü, etiket ve not
    # yazılarının ölçülmüş sınırları kesişmez (kullanıcı: balonlar ve
    # SİM. notları, paralel zincirlerin ara ölçüleri üst üste biniyordu)
    import yazi_dikdortgeni as YD
    cift = [c for doc in yakala for c in YD.sayfa_denetimi(doc)[0]]
    ust = [t for doc in yakala for t in YD.sayfa_denetimi(doc)[1]]
    dogru("ölçü / etiket yazıları üst üste binmiyor", not cift, cift[:6])
    dogru("ölçü / etiket yazısı parça çizgisinin üstünde değil", not ust, ust[:6])

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
