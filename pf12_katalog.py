# -*- coding: utf-8 -*-
"""STANDART ÜRÜN KATALOĞU: resimler.

STANDART_KATALOG klasörüne YALNIZ standart (satın alınan) ürün resmi
konur - tekli ya da toplu, adı olsun olmasın. Sac, lama, profil, üretim
parçası KONMAZ. Program bu resimleri AI kontrolünün resimli turuna
REFERANS olarak verir: "bunların hepsi bu firmanın satın aldığı
ürünlerdir; parça resmi bunlardan birine YAPISAL olarak benziyorsa
standarttır".

Yüzlerce resim tek tek gönderilmez (pahalı): küçük resimler ızgara
paftalarda toplanır (pafta başına 20), büyük / toplu resimler kendi
paftasında küçültülür; en çok PAFTA_EN_COK pafta gider. Paftalar
isteklerde önbelleklenir: ilk istek tam, sonrakiler onda bir fiyatına.

Bu modül ayrıca kataloğa programın KENDİ çizdiği standart parça
resimlerini koyabilir (ornek_uret): AI'a giden parça resimleriyle aynı
biçimde oldukları için karşılaştırma tutarlıdır; telif sorunu yoktur.
"""
from __future__ import annotations

import io
import os

RESIM = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
PAFTA_EN_COK = 8
HUCRE = 180                 # ızgara hücresi (px)
SUTUN = 5
SATIR = 4
BUYUK = 700                 # bundan büyük resim kendi paftasında (toplu resim)


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
    kucuk, buyuk = [], []
    for y in yollar:
        try:
            im = Image.open(y)
            im.load()
        except Exception:
            log(f"! katalog: {os.path.basename(y)} açılamadı")
            continue
        (buyuk if max(im.size) > BUYUK else kucuk).append((im.convert("RGB"), _etiket(y, klasor)))
    out = []
    for im, et in buyuk:
        im.thumbnail((1000, 1000))
        out.append(im)
    n = SUTUN * SATIR
    for i in range(0, len(kucuk), n):
        grup = kucuk[i:i + n]
        pafta = Image.new("RGB", (SUTUN * HUCRE, SATIR * (HUCRE + 18)), "white")
        c = ImageDraw.Draw(pafta)
        for j, (im, et) in enumerate(grup):
            im = im.copy()
            im.thumbnail((HUCRE - 8, HUCRE - 8))
            x, y = (j % SUTUN) * HUCRE, (j // SUTUN) * (HUCRE + 18)
            pafta.paste(im, (x + (HUCRE - im.width) // 2, y + (HUCRE - im.height) // 2))
            if et:
                c.text((x + 4, y + HUCRE), et, fill="black")
        out.append(pafta)
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
    }
    n = 0
    for ad, sh in parcalar.items():
        png = TN.parca_png(sh, boyut=384)
        if not png:
            continue
        y = os.path.join(klasor, "ornek_" + ad.split("/")[0], ad.split("/")[1] + ".jpg")
        os.makedirs(os.path.dirname(y), exist_ok=True)
        Image.open(io.BytesIO(png)).convert("RGB").save(y, quality=85)
        n += 1
    return n
