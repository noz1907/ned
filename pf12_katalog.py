# -*- coding: utf-8 -*-
"""STANDART ÜRÜN KATALOĞU: resimler.

STANDART_KATALOG klasörüne YALNIZ standart (satın alınan) ürün resmi
konur - tekli ya da toplu, adı olsun olmasın. Sac, lama, profil, üretim
parçası KONMAZ. Program bu resimleri AI kontrolünün resimli turuna
REFERANS olarak verir: "bunların hepsi bu firmanın satın aldığı
ürünlerdir; parça resmi bunlardan birine YAPISAL olarak benziyorsa
standarttır".

Yüzlerce resim tek tek gönderilmez (pahalı): küçük resimler ızgara
paftalarda toplanır (küçükler 20, orta boylar 4), büyük / toplu resimler kendi
paftasında küçültülür; en çok PAFTA_EN_COK pafta gider. Paftalar
isteklerde önbelleklenir: ilk istek tam, sonrakiler onda bir fiyatına.

Bu modül ayrıca kataloğa programın KENDİ çizdiği standart parça
resimlerini koyabilir (ornek_uret: cıvata, somun, pul, perçin, segman,
pim, kama, nipel, yay): AI'a giden parça resimleriyle aynı
biçimde oldukları için karşılaştırma tutarlıdır; telif sorunu yoktur.
"""
from __future__ import annotations

import io
import os

RESIM = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
PAFTA_EN_COK = 8
# Resim boyuna göre üç sınıf: küçük (tekli ürün) 5x4 ızgarada 180 px,
# orta 2x2 ızgarada 480 px, büyük (toplu resim) kendi paftasında 1000 px.
HUCRE = 180
SUTUN = 5
SATIR = 4
ORTA = 520                  # bundan büyük: 2x2 ızgara
BUYUK = 1000                # bundan büyük: kendi paftasında


def resimler(klasor):
    out = []
    for kok, _d, dosyalar in os.walk(klasor or ""):
        for d in sorted(dosyalar):
            if d.lower().endswith(RESIM) and not d.startswith("."):
                out.append(os.path.join(kok, d))
    return sorted(out)


def _etiket(yol, klasor):
    """Dosya adı anlamlıysa o, değilse (IMG_1234, 23) klasör adı."""
    ad = os.path.splitext(os.path.basename(yol))[0]
    ust = os.path.basename(os.path.dirname(yol))
    anlamsiz = ad.replace("_", "").replace("-", "").replace(" ", "").isdigit() \
        or ad.lower().startswith(("img", "dsc", "resim", "image", "foto"))
    if anlamsiz:
        return ust if os.path.abspath(os.path.dirname(yol)) != os.path.abspath(klasor) else ""
    return ad.replace("_", " ")[:24]


def paftalar(klasor, en_cok=PAFTA_EN_COK, log=print):
    """Katalog resimlerinden PNG pafta baytları listesi."""
    from PIL import Image, ImageDraw
    yollar = resimler(klasor)
    if not yollar:
        return []
    kucuk, orta, buyuk = [], [], []
    for y in yollar:
        try:
            im = Image.open(y)
            im.load()
        except Exception:
            log(f"! katalog: {os.path.basename(y)} açılamadı")
            continue
        m = max(im.size)
        (buyuk if m > BUYUK else orta if m > ORTA else kucuk).append(
            (im.convert("RGB"), _etiket(y, klasor)))
    out = []
    for im, et in buyuk:
        im.thumbnail((BUYUK, BUYUK))
        out.append(im)

    def izgara(liste, sutun, satir, hucre):
        n = sutun * satir
        for i in range(0, len(liste), n):
            pafta = Image.new("RGB", (sutun * hucre, satir * (hucre + 18)), "white")
            c = ImageDraw.Draw(pafta)
            for j, (im, et) in enumerate(liste[i:i + n]):
                im = im.copy()
                im.thumbnail((hucre - 8, hucre - 8))
                x, y = (j % sutun) * hucre, (j // sutun) * (hucre + 18)
                pafta.paste(im, (x + (hucre - im.width) // 2, y + (hucre - im.height) // 2))
                if et:
                    c.text((x + 4, y + hucre), et, fill="black")
            out.append(pafta)
    izgara(orta, 2, 2, 480)
    izgara(kucuk, SUTUN, SATIR, HUCRE)
    if len(out) > en_cok:
        # hepsinden örnek: eşit aralıkla seç
        adim = len(out) / en_cok
        out = [out[int(i * adim)] for i in range(en_cok)]
        log(f"katalog: {len(yollar)} resimden {en_cok} pafta seçildi (sınır)")
    bayt = []
    for im in out:
        b = io.BytesIO()
        im.save(b, format="PNG", optimize=True)
        bayt.append(b.getvalue())
    return bayt


# ------------------------------------------------------------ örnekler
def ornek_uret(klasor):
    """Programın kendi modellediği standart parçaların resimlerini
    (JPG) kataloğa yazar. Döner: yazılan dosya sayısı."""
    import math
    from PIL import Image
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import (BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism,
                                 BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeBox,
                                 BRepPrimAPI_MakeCone, BRepPrimAPI_MakeTorus)
    from OCP.gp import gp_Pnt, gp_Vec, gp_Ax2, gp_Dir
    import pf8_tani as TN

    def cyl(r, h, z=0):
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)), r, h).Shape()

    def cut(a, b):
        return BRepAlgoAPI_Cut(a, b).Shape()

    def fuse(a, b):
        return BRepAlgoAPI_Fuse(a, b).Shape()

    def prizma(pts, h, z=0):
        p = BRepBuilderAPI_MakePolygon()
        for x, y in pts:
            p.Add(gp_Pnt(x, y, z))
        p.Close()
        return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(p.Wire()).Face(),
                                     gp_Vec(0, 0, h)).Shape()

    def hexa(s, h, z=0):
        R = s / math.sqrt(3)
        return prizma([(R * math.cos(math.radians(30 + 60 * i)),
                        R * math.sin(math.radians(30 + 60 * i))) for i in range(6)], h, z)

    def kutu(x, y, z, a, b, c):
        return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), a, b, c).Shape()

    def yildiz(ri, ro, n, h, z=0):
        return prizma([((ro if i % 2 == 0 else ri) * math.cos(math.pi * i / n),
                        (ro if i % 2 == 0 else ri) * math.sin(math.pi * i / n))
                       for i in range(2 * n)], h, z)

    def helis(R, adim, tur, d):
        """Tel çapı d, orta yarıçap R, hatve adim: helis süpürme katı ve uçları."""
        from OCP.BRepAdaptor import BRepAdaptor_CompCurve
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
        from OCP.BRepLib import BRepLib
        from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
        from OCP.Geom import Geom_CylindricalSurface
        from OCP.Geom2d import Geom2d_Line
        from OCP.gp import gp_Ax3, gp_Circ, gp_Dir2d, gp_Pnt2d
        yuz = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), R)
        e = BRepBuilderAPI_MakeEdge(Geom2d_Line(gp_Pnt2d(0, 0), gp_Dir2d(2 * math.pi, adim)),
                                    yuz, 0.0, tur * math.hypot(2 * math.pi, adim)).Edge()
        BRepLib.BuildCurves3d_s(e)
        w = BRepBuilderAPI_MakeWire(e).Wire()
        c = BRepAdaptor_CompCurve(w)
        p0, v0, p1, v1 = gp_Pnt(), gp_Vec(), gp_Pnt(), gp_Vec()
        c.D1(c.FirstParameter(), p0, v0)
        c.D1(c.LastParameter(), p1, v1)
        ps = BRepOffsetAPI_MakePipeShell(w)
        ps.SetMode(gp_Dir(0, 0, 1))
        ps.Add(BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(
            gp_Circ(gp_Ax2(p0, gp_Dir(v0)), d / 2)).Edge()).Wire())
        ps.Build()
        ps.MakeSolid()
        return ps.Shape(), p0, p1

    def cyl_xy(r, h, x, y, z=0):
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), r, h).Shape()

    def burulma():
        sh, a, b = helis(6, 1.6, 6, 1.5)
        bacak = fuse(BRepPrimAPI_MakeCylinder(gp_Ax2(a, gp_Dir(0, -1, 0)), 0.75, 18).Shape(),
                     BRepPrimAPI_MakeCylinder(gp_Ax2(b, gp_Dir(0, -1, 0)), 0.75, 18).Shape())
        return fuse(sh, bacak)

    def segman():
        ri, s_, e = 9.25, 1.2, 1.2
        r = cut(BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(-e, 0, 0), gp_Dir(0, 0, 1)),
                                         ri + 2.6 - e, s_).Shape(), cyl(ri, s_))
        r = cut(r, kutu(0, -1.8, 0, 20, 3.6, s_))
        for sg in (1, -1):
            r = fuse(r, cyl_xy(2, s_, ri + 1.8, sg * 3.8))
            r = cut(r, cyl_xy(1, s_, ri + 1.8, sg * 3.8))
        return cut(r, cyl(ri, s_))

    def yayli_pim():
        t = cut(cut(cyl(3, 30), cyl(1.8, 30)), kutu(-0.5, 0, 0, 1, 4, 30))
        return t

    def kama():
        return fuse(fuse(kutu(-16, -4, 0, 32, 8, 7), cyl_xy(4, 7, -16, 0)), cyl_xy(4, 7, 16, 0))

    def nipel():
        g = fuse(fuse(cyl(4, 5.5), hexa(9, 5, 5.5)), cyl(2.3, 3, 10.5))
        g = fuse(g, BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 14.2), 3.25).Shape())
        return cut(g, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -1), gp_Dir(0, 0, 1)), 1, 20).Shape())

    saft = cyl(4, 40)
    kube = cut(BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 34), 10.4).Shape(), kutu(-20, -20, 14, 40, 40, 26))
    parcalar = {
        "civata/altikose basli civata": fuse(saft, hexa(13, 5.5, 40)),
        "civata/altikose flansli civata": fuse(fuse(saft, cyl(9, 1.5, 40)), hexa(13, 6, 41.5)),
        "civata/imbus silindir basli civata": cut(fuse(saft, cyl(6.5, 8, 40)), hexa(6, 4, 44)),
        "civata/torx silindir basli civata": cut(fuse(saft, cyl(6.5, 8, 40)),
                                                 yildiz(1.9, 2.8, 6, 4, 44)),
        "civata/bombe basli imbus civata (ISO 7380)": cut(fuse(saft, kube), hexa(5, 3, 42.4)),
        "civata/havsa basli imbus civata": cut(fuse(saft, BRepPrimAPI_MakeCone(
            gp_Ax2(gp_Pnt(0, 0, 40), gp_Dir(0, 0, 1)), 4, 8, 4).Shape()), hexa(5, 3, 41)),
        "civata/yildiz silindir basli vida": cut(cut(fuse(saft, cyl(6.5, 5, 40)),
                                                     kutu(-3, -0.6, 42, 6, 1.2, 3)),
                                                 kutu(-0.6, -3, 42, 1.2, 6, 3)),
        "civata/duz (yarik) basli vida": cut(fuse(saft, cyl(6.5, 5, 40)), kutu(-8, -0.6, 43, 16, 1.2, 2)),
        "civata/kare basli civata": fuse(saft, prizma([(-6.5, -6.5), (6.5, -6.5), (6.5, 6.5),
                                                       (-6.5, 6.5)], 6, 40)),
        "civata/setskur (basliksiz imbus)": cut(cyl(4, 12), hexa(4, 3, 9)),
        "somun/altikose somun": cut(hexa(13, 6.5), cyl(4, 6.5)),
        "somun/flansli somun": cut(fuse(cyl(9, 1.5), hexa(13, 7, 1.5)), cyl(4, 8.5)),
        "somun/kare somun": cut(prizma([(-6.5, -6.5), (6.5, -6.5), (6.5, 6.5), (-6.5, 6.5)], 5), cyl(4, 5)),
        "somun/kapali somun": cut(fuse(hexa(17, 9), cut(BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 9), 7).Shape(),
                                                        kutu(-9, -9, 0, 18, 18, 9))), cyl(5, 12)),
        "somun/manson (uzatma) somun": cut(hexa(13, 30), cyl(4, 30)),
        "somun/percin somun": cut(cut(fuse(cyl(5.2, 1), cyl(4.5, 13, 1)), cyl(4, 4)), cyl(3, 14)),
        "pul-percin-pim/duz pul": cut(cyl(8, 1.6), cyl(4.2, 1.6)),
        "pul-percin-pim/kubbe basli percin": fuse(cut(BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 0), 6).Shape(),
                                                      kutu(-7, -7, -7, 14, 14, 7)), cyl(3, 15, -15)),
        "pul-percin-pim/o-ring": BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)),
                                                       8, 1.5).Shape(),
        "pul-percin-pim/mil segmani DIN 471": segman(),
        "pul-percin-pim/yayli pim ISO 8752": yayli_pim(),
        "pul-percin-pim/paralel kama DIN 6885 A": kama(),
        "pul-percin-pim/gres nipeli DIN 71412": nipel(),
        "yay/basma yayi": helis(8, 5, 8, 1.6)[0],
        "yay/burulma yayi (bacakli)": burulma(),
    }
    n = 0
    for ad, sh in parcalar.items():
        png = TN.parca_png(sh, boyut=250)
        if not png:
            continue
        y = os.path.join(klasor, "ornek_" + ad.split("/")[0], ad.split("/")[1] + ".jpg")
        os.makedirs(os.path.dirname(y), exist_ok=True)
        Image.open(io.BytesIO(png)).convert("RGB").save(y, quality=85)
        n += 1
    return n
