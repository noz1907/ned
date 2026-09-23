# -*- coding: utf-8 -*-
"""
Pi3D – PAFTA

1:1 çizilmiş DXF'leri standart bir A3 paftaya yerleştirir. Ve bunu
yaparken:

    MODEL UZAYINA ASLA DOKUNULMAZ.

Bu bir kural, tercih değil. 1:1 çizim gerçeğin kendisidir; ölçüsü,
konumu, hiçbir şeyi değişmez. Pafta, o çizime bir PENCEREDEN bakar
(paper space viewport). Ölçek pencerenin özelliğidir, geometrinin değil.
Dolayısıyla "1:10 bastım" demek çizimi küçülttüm demek değildir; aynı
1:1 çizime uzaktan bakmak demektir. AutoCAD'de Model sekmesine
geçtiğinizde her şeyi eskisi gibi, birebir ölçüsünde bulursunuz.

PAFTANIN YAPISI (A3, 420 x 297 mm)

    +--------------------------------------------------+
    |  15 mm pay                                       |
    |   +------------------------------------------+   |
    |   |                                          |   |
    |   |          ÇİZİM BURAYA                    |   |
    |   |                                          |   |
    |   |                          +---------------+   |
    |   |                          |  ANTET ALANI  |   |
    |   +--------------------------+  150 x 100 mm +   |
    |                                                  |
    +--------------------------------------------------+

Antet ÇİZİLMEZ. Her firmanın anteti başka; programın uyduracağı bir
şey değil. Sağ alt köşedeki 150 x 100 mm'lik kutu boş bırakılır ve
oraya ASLA çizim gelmez - firma kendi antetini oraya yapıştırır.

Çizim, antet kutusunun üstündeki ya da solundaki alanlardan hangisi
daha büyük ölçek veriyorsa oraya oturur.
"""
from __future__ import annotations
import os

import ezdxf
import ezdxf.bbox

# ---------------------------------------------------------------- kâğıt
# HER ZAMAN YATAY (landscape). Dikey pafta yok: antet kutusu sağ alt
# köşede sabittir ve uzun parçalar - sac açınımları hep uzundur - yatay
# kâğıda sığar. Aşağıdaki ölçüler yatay ölçülerdir, döndürülmez.
KAGIT = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}
KAGIT_SIRA = ("A4", "A3", "A2", "A1", "A0")
VARSAYILAN_KAGIT = "A3"

KENAR = 15.0                 # çerçeve kâğıdın kenarından bu kadar içeride
DIS_PAY = 5.0                # ince dış çizgi kâğıdın kenarından
ANTET_EN, ANTET_BOY = 150.0, 100.0     # sağ alt köşede boş bırakılan kutu

# Bölge bölümleri (ISO 5457): rakamlar soldan sağa, harfler yukarıdan
# aşağıya. "B3'teki delik" demek için. Sütun ve satır sayısı çifttir.
BOLGE = {"A4": (6, 4), "A3": (8, 4), "A2": (12, 6),
         "A1": (16, 8), "A0": (24, 12)}
BOLGE_HARF = "ABCDEFGHIJKL"

HARF_ORAN = 0.62         # yazı genişliği ~ harf sayısı x yükseklik x bu
EN_AZ_YAZI_MM = 1.8      # kâğıtta bundan küçük yazı okunmaz (ISO 3098: 2,5)

# Teknik resimde kullanılan standart ölçekler (ISO 5455). Ara ölçek
# uydurulmaz: 1:7 diye bir resim olmaz.
KUCULTME = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
BUYUTME = (2, 5, 10)

KAT_CERCEVE = "PAFTA_CERCEVE"
KAT_ANTET = "PAFTA_ANTET_ALANI"
KAT_BILGI = "PAFTA_BILGI"
KAT_BOLGE = "PAFTA_BOLGE"


class PaftaYok(Exception):
    """Pafta kurulamadı; mesaj kullanıcıya gösterilir."""


# ------------------------------------------------------------ yardımcı
def _yazi_kutusu(e):
    """Bir yazının kapladığı yerin yaklaşık sınırı.

    DXF yazının genişliğini saklamaz; yazı tipine göre değişir. CAD'in
    txt/iso yazı tipinde harf ilerlemesi yaklaşık yüksekliğin 0,62'si
    kadardır. Amaç ölçü vermek değil, yazının kâğıt dışında kalmasını
    önlemek."""
    t = e.dxftype()
    try:
        if t == "MTEXT":
            h = float(e.dxf.char_height or 2.5)
            sat = (e.text or "").replace("\\P", "\n").split("\n")
            g = float(getattr(e.dxf, "width", 0) or 0)
            if g <= 0:
                g = HARF_ORAN * h * max((len(x) for x in sat), default=0)
            b = h * 1.6 * max(len(sat), 1)
            x, y = e.dxf.insert.x, e.dxf.insert.y
            # MTEXT dayanak noktası: 1-3 üst, 4-6 orta, 7-9 alt
            d = int(getattr(e.dxf, "attachment_point", 1) or 1)
            x -= {1: 0, 2: 0.5, 0: 0}.get((d - 1) % 3, 1.0) * g
            y -= {0: 1.0, 1: 0.5, 2: 0.0}.get((d - 1) // 3, 1.0) * b
            return (x, y, x + g, y + b)
        h = float(e.dxf.height or 2.5)
        m = e.dxf.text or ""
        g = HARF_ORAN * h * len(m) * float(getattr(e.dxf, "width", 1.0) or 1.0)
        yatay = int(getattr(e.dxf, "halign", 0) or 0)
        dusey = int(getattr(e.dxf, "valign", 0) or 0)
        p = e.dxf.align_point if yatay or dusey else e.dxf.insert
        x, y = p.x, p.y
        x -= {0: 0.0, 1: 0.5, 2: 1.0, 4: 0.5}.get(yatay, 0.0) * g
        y -= {0: 0.0, 1: 0.0, 2: 0.5, 3: 1.0}.get(dusey, 0.0) * h
        return (x, y, x + g, y + h)
    except Exception:
        return None


def _varlik_kutusu(uzay, yazi=True):
    """Bir uzaydaki çizimin sınırları (x0, y0, x1, y1) ya da None."""
    xs, ys = [], []

    def ekle(k):
        if k:
            xs.extend((k[0], k[2])); ys.extend((k[1], k[3]))

    for e in uzay:
        t = e.dxftype()
        try:
            if t == "LWPOLYLINE":
                for x, y, *_ in e.get_points():
                    xs.append(x); ys.append(y)
            elif t == "LINE":
                xs += [e.dxf.start.x, e.dxf.end.x]
                ys += [e.dxf.start.y, e.dxf.end.y]
            elif t in ("CIRCLE", "ARC"):
                c, r = e.dxf.center, e.dxf.radius
                xs += [c.x - r, c.x + r]; ys += [c.y - r, c.y + r]
            elif t in ("TEXT", "MTEXT"):
                if yazi:
                    ekle(_yazi_kutusu(e))
            elif t == "POINT":
                xs.append(e.dxf.location.x); ys.append(e.dxf.location.y)
        except Exception:
            continue
    if not xs:
        return None
    return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))


def cizim_kutusu(yol):
    """1:1 DXF'in model uzayındaki sınırları — HER ŞEY DAHİL.

    Yazı da, ölçü de resmin parçasıdır. Pencereyi yalnız geometriye göre
    açarsak bunlar kenardan kırpılır; ilk denemede tam da bu oldu:
    büküm tablosu yarıdan kesildi, sol taraftaki genişlik ölçüsü
    (parçanın 154 mm solunda duruyordu) resme hiç girmedi.

    Ölçüler DIMENSION varlığıdır ve çizgileri adsız bir BLOK içinde
    durur; elle gezerek bulunamaz. ezdxf'in kendi sınır hesabı blokları
    açar ve yazıyı yazı tipinden ölçer, o yüzden önce o denenir."""
    d = ezdxf.readfile(yol)
    try:
        k = ezdxf.bbox.extents(d.modelspace(), fast=False)
        if k.has_data:
            return (float(k.extmin.x), float(k.extmin.y),
                    float(k.extmax.x), float(k.extmax.y))
    except Exception:
        pass                      # eski ezdxf ya da bozuk varlık: kabaca ölç
    k = _varlik_kutusu(d.modelspace())
    if not k:
        raise PaftaYok(f"{os.path.basename(yol)}: çizimde varlık yok.")
    return k


def en_kucuk_yazi(yol):
    """Çizimdeki en küçük yazının model uzayındaki yüksekliği (mm).

    Ölçekle çarpılınca kâğıtta kaç mm kalacağı çıkar. Uzun parçalar
    küçük ölçeğe düşer ve yazıları okunmaz hale gelir; kullanıcının
    bunu paftayı basmadan önce bilmesi gerekir."""
    d = ezdxf.readfile(yol)
    h = []
    for e in d.modelspace():
        try:
            if e.dxftype() == "TEXT":
                h.append(float(e.dxf.height))
            elif e.dxftype() == "MTEXT":
                h.append(float(e.dxf.char_height))
        except Exception:
            continue
    return min((v for v in h if v > 0), default=0.0)


def olcek_metni(o):
    """0.1 -> '1:10',  2 -> '2:1',  1 -> '1:1'"""
    if abs(o - 1.0) < 1e-9:
        return "1:1"
    if o < 1:
        return f"1:{round(1 / o)}"
    return f"{round(o)}:1"


def cerceve(kagit=VARSAYILAN_KAGIT):
    """Çerçevenin köşeleri (x0, y0, x1, y1)."""
    if kagit not in KAGIT:
        raise PaftaYok(f"Bilinmeyen kâğıt: {kagit}")
    g, y = KAGIT[kagit]
    return (KENAR, KENAR, g - KENAR, y - KENAR)


def antet_kutusu(kagit=VARSAYILAN_KAGIT):
    """Sağ alt köşede boş bırakılan alan (x0, y0, x1, y1).

    Ölçüsü kâğıttan kâğıda değişmez: antet A3'te ne kadarsa A1'de de
    o kadardır. Yazı boyları kâğıtla büyümez."""
    x0, y0, x1, y1 = cerceve(kagit)
    return (max(x0, x1 - ANTET_EN), y0, x1, min(y1, y0 + ANTET_BOY))


def cizim_alanlari(kagit=VARSAYILAN_KAGIT):
    """Çizimin oturabileceği iki dikdörtgen.

    Antet kutusu sağ alt köşeyi yediği için kalan boşluk L biçimindedir.
    Bir resim dikdörtgendir; L'ye iki türlü sığar: kutunun ÜSTÜNE tam
    genişlikte, ya da SOLUNA tam yükseklikte. Hangisi daha büyük ölçek
    veriyorsa o kullanılır."""
    fx0, fy0, fx1, fy1 = cerceve(kagit)
    ax0, _, _, ay1 = antet_kutusu(kagit)
    return {"ust": (fx0, ay1, fx1, fy1),
            "sol": (fx0, fy0, ax0, fy1)}


def sigan_olcek(gx, gy, alan_g, alan_y, buyutme=False):
    """Çizimi alana sığdıran EN BÜYÜK standart ölçek. Sığmıyorsa None.

    Önce 1:1 denenir - teknik resimde tercih her zaman birebirdir.
    Sonra sırayla küçültülür. Büyütme İSTENMEDİKÇE yapılmaz: kimse
    küçük bir parçanın kendiliğinden 2:1 çizilmesini beklemez."""
    if alan_g <= 0 or alan_y <= 0:
        return None
    if gx <= alan_g and gy <= alan_y:
        if buyutme:
            for b in reversed(BUYUTME):
                if gx * b <= alan_g and gy * b <= alan_y:
                    return float(b)
        return 1.0
    for k in KUCULTME[1:]:
        if gx / k <= alan_g and gy / k <= alan_y:
            return 1.0 / k
    return None


def yerlesim(gx, gy, kagit=VARSAYILAN_KAGIT, buyutme=False):
    """Çizim bu kâğıda nasıl oturur.

    Döner: {"olcek":, "yer": "ust"/"sol", "alan": (x0,y0,x1,y1)}
    Sığmıyorsa None."""
    en_iyi = None
    for yer, a in cizim_alanlari(kagit).items():
        o = sigan_olcek(gx, gy, a[2] - a[0], a[3] - a[1], buyutme)
        if o and (en_iyi is None or o > en_iyi["olcek"]):
            en_iyi = {"olcek": o, "yer": yer, "alan": a}
    return en_iyi


def kagit_sec(gx, gy, adaylar=KAGIT_SIRA, en_az_olcek=1.0):
    """Çizimi istenen ölçekte alan EN KÜÇÜK kâğıt. Yoksa None."""
    for k in adaylar:
        y = yerlesim(gx, gy, k)
        if y and y["olcek"] >= en_az_olcek - 1e-9:
            return k
    return None


# --------------------------------------------------------------- pafta
def _pafta_cerceve_ciz(pafta, kagit, bilgi=""):
    """Standart pafta çerçevesini çizer.

        - kâğıdın kenarında ince dış çizgi
        - 15 mm içeride kalın çizim çerçevesi
        - ikisinin arasında bölge şeridi: rakamlar ve harfler
        - kenar ortalarında katlama/ortalama işaretleri
        - sağ alt köşede BOŞ antet kutusu

    Her biri ayrı katmanda: istemediğinizi tek tıkla silersiniz."""
    d = pafta.doc
    for ad, renk in ((KAT_CERCEVE, 7), (KAT_ANTET, 7),
                     (KAT_BOLGE, 7), (KAT_BILGI, 8)):
        if ad not in d.layers:
            d.layers.add(ad, color=renk)
    kg, ky = KAGIT[kagit]
    fx0, fy0, fx1, fy1 = cerceve(kagit)

    def dikdortgen(x0, y0, x1, y1, kat, kalin):
        pafta.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                             close=True,
                             dxfattribs={"layer": kat, "lineweight": kalin})

    def cizgi(x0, y0, x1, y1, kat=KAT_BOLGE, kalin=13):
        pafta.add_line((x0, y0), (x1, y1),
                       dxfattribs={"layer": kat, "lineweight": kalin})

    def yaz(x, y, m, h=3.5, kat=KAT_BOLGE):
        t = pafta.add_text(m, height=h, dxfattribs={"layer": kat,
                                                    "lineweight": 13})
        t.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        return t

    dikdortgen(DIS_PAY, DIS_PAY, kg - DIS_PAY, ky - DIS_PAY, KAT_CERCEVE, 13)
    dikdortgen(fx0, fy0, fx1, fy1, KAT_CERCEVE, 50)

    # --- bölge şeridi
    sut, sat = BOLGE.get(kagit, (8, 4))
    bs = (fx1 - fx0) / sut
    for i in range(sut):
        x = fx0 + i * bs
        if i:
            cizgi(x, DIS_PAY, x, fy0); cizgi(x, fy1, x, ky - DIS_PAY)
        yaz(x + bs / 2, (DIS_PAY + fy0) / 2, str(i + 1))
        yaz(x + bs / 2, (fy1 + ky - DIS_PAY) / 2, str(i + 1))
    bh = (fy1 - fy0) / sat
    for j in range(sat):
        y = fy1 - (j + 1) * bh                    # harfler yukarıdan aşağıya
        if j:
            cizgi(DIS_PAY, y + bh, fx0, y + bh)
            cizgi(fx1, y + bh, kg - DIS_PAY, y + bh)
        yaz((DIS_PAY + fx0) / 2, y + bh / 2, BOLGE_HARF[j])
        yaz((fx1 + kg - DIS_PAY) / 2, y + bh / 2, BOLGE_HARF[j])

    # --- kenar ortası işaretleri (katlarken hizalamak için)
    for x, y, dx, dy in ((kg / 2, fy0, 0, -1), (kg / 2, fy1, 0, 1),
                         (fx0, ky / 2, -1, 0), (fx1, ky / 2, 1, 0)):
        cizgi(x, y, x + dx * (KENAR - DIS_PAY), y + dy * (KENAR - DIS_PAY),
              KAT_CERCEVE, 50)

    # --- antet kutusu: BOŞ. Firma kendi antetini buraya yapıştırır.
    ax0, ay0, ax1, ay1 = antet_kutusu(kagit)
    dikdortgen(ax0, ay0, ax1, ay1, KAT_ANTET, 50)

    if bilgi:
        # Paftanın ölçeği yazılmak zorunda: model uzayı 1:1 olduğu için
        # çizimin kendi başlığında "olcek 1:1" yazar, kâğıtta ise 1:5
        # olabilir. Antet kutusunun üst kenarına, kendi katmanında.
        # Kendi antetinizi yapıştırırken bu katmanı kapatın: sizin
        # antetinizde zaten ölçek gözü vardır.
        t = pafta.add_text(bilgi, height=3.0,
                           dxfattribs={"layer": KAT_BILGI, "lineweight": 13})
        t.set_placement((ax0 + 3, ay1 - 5))


def pafta_kur(kaynak_dxf, cikti_dxf, kagit=VARSAYILAN_KAGIT, olcek=None,
              buyutme=False, pafta_adi="PAFTA", bilgi=True):
    """1:1 DXF'in KOPYASINA standart bir pafta ekler.

    kaynak_dxf : 1:1 çizim. AÇILIR, OKUNUR, DEĞİŞTİRİLMEZ.
    cikti_dxf  : yeni dosya. Kaynak dosyaya dokunulmaz.
    kagit      : "A4".."A0", her zaman yatay. Varsayılan A3.
    olcek      : 1.0 / 0.1 gibi. None ise sığan en büyük standart ölçek.

    Döner: {"olcek":, "olcek_metni":, "kagit":, "yer":, "olcu": (gx,gy),
            "alan": (g,y), "dosya":}
    """
    if kagit not in KAGIT:
        raise PaftaYok(f"Bilinmeyen kâğıt: {kagit}")
    kg, ky = KAGIT[kagit]

    d = ezdxf.readfile(kaynak_dxf)
    msp = d.modelspace()
    once = len(list(msp))

    x0, y0, x1, y1 = cizim_kutusu(kaynak_dxf)
    gx, gy = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)

    # --- ölçek ve hangi boşluğa oturacağı
    if olcek is None:
        yer = yerlesim(gx, gy, kagit, buyutme)
        if not yer:
            raise PaftaYok(
                f"{os.path.basename(kaynak_dxf)}: {gx:.0f}x{gy:.0f} mm çizim "
                f"{kagit} paftaya standart bir ölçekle sığmıyor "
                f"(en büyük boşluk {_en_buyuk_alan_metni(kagit)}). "
                "Daha büyük kâğıt seçin.")
        olcek = yer["olcek"]
    else:
        yer = None
        for ad, a in cizim_alanlari(kagit).items():
            if (gx * olcek <= a[2] - a[0] + 1e-6
                    and gy * olcek <= a[3] - a[1] + 1e-6):
                yer = {"olcek": olcek, "yer": ad, "alan": a}
                break
        if not yer:
            # Ölçeği kullanıcı verdiyse de kâğıda sığmayan pafta yazılmaz:
            # taşan çizim, olmayan çizimden beterdir.
            raise PaftaYok(
                f"{os.path.basename(kaynak_dxf)}: {gx:.0f}x{gy:.0f} mm çizim "
                f"{olcek_metni(olcek)} ölçekte "
                f"{gx * olcek:.0f}x{gy * olcek:.0f} mm yer ister; {kagit} "
                f"paftada en büyük boşluk {_en_buyuk_alan_metni(kagit)}. "
                "Ölçeği küçültün ya da kâğıdı büyütün.")
    alan = yer["alan"]
    ag, ay = alan[2] - alan[0], alan[3] - alan[1]
    # Pencere tam çizim kadar olsun; ölçek küçükse çizim alanının
    # ortasında değil, KÂĞIDIN ortasında dursun - antet kutusuna
    # girmiyorsa. Yoksa kısa parçalar kâğıdın bir kenarına sıkışıyor.
    pg, py = max(gx * olcek, 1e-6), max(gy * olcek, 1e-6)
    mx, my = (alan[0] + alan[2]) / 2.0, (alan[1] + alan[3]) / 2.0
    fx0, fy0, fx1, fy1 = cerceve(kagit)
    ox, oy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
    ax0, ay0, ax1, ay1 = antet_kutusu(kagit)
    if (ox - pg / 2 >= fx0 - 1e-6 and ox + pg / 2 <= fx1 + 1e-6
            and oy - py / 2 >= fy0 - 1e-6 and oy + py / 2 <= fy1 + 1e-6
            and not (ox - pg / 2 < ax1 and ox + pg / 2 > ax0
                     and oy - py / 2 < ay1 and oy + py / 2 > ay0)):
        mx, my = ox, oy

    # --- paftayı kur
    try:
        d.layouts.delete(pafta_adi)
    except Exception:
        pass
    pafta = d.layouts.new(pafta_adi)
    pafta.page_setup(size=(round(kg), round(ky)), margins=(0, 0, 0, 0),
                     units="mm", scale=16)   # 16 = 1 kâğıt birimi : 1 mm

    not_ = ""
    if bilgi:
        not_ = (f"{kagit}   PAFTA ÖLÇEĞİ {olcek_metni(olcek)}"
                + ("   (model uzayı 1:1)" if abs(olcek - 1) > 1e-9 else "")
                + f"   {os.path.basename(kaynak_dxf)}")
    _pafta_cerceve_ciz(pafta, kagit, not_)

    # --- pencere: 1:1 çizime buradan bakılır
    pafta.add_viewport(
        center=(mx, my), size=(pg, py),
        view_center_point=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
        view_height=gy,
    )

    # --- model uzayı bozulmadı mı? Bu kontrol pazarlık konusu değil.
    sonra = len(list(msp))
    if sonra != once:
        raise PaftaYok(
            f"İÇ HATA: model uzayı değişti ({once} -> {sonra}). "
            "Pafta yazılmadı, 1:1 çizim korundu.")

    d.set_modelspace_vport(height=max(gx, gy) * 1.1,
                           center=((x0 + x1) / 2.0, (y0 + y1) / 2.0))
    try:
        d.layouts.set_active_layout(pafta_adi)
    except Exception:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(cikti_dxf)) or ".",
                exist_ok=True)
    d.saveas(cikti_dxf)
    yz = en_kucuk_yazi(kaynak_dxf) * olcek
    return {"olcek": olcek, "olcek_metni": olcek_metni(olcek), "kagit": kagit,
            "yer": yer["yer"], "olcu": (gx, gy), "alan": (ag, ay),
            "dosya": cikti_dxf, "yazi_mm": round(yz, 2),
            "yazi_kucuk": 0 < yz < EN_AZ_YAZI_MM}


def _en_buyuk_alan_metni(kagit):
    a = cizim_alanlari(kagit)
    return "  /  ".join(f"{(v[2] - v[0]):.0f}x{(v[3] - v[1]):.0f} mm"
                        for v in a.values())


# --------------------------------------------------------------- baskı
def pafta_olcusu(dxf_yolu, pafta_adi="PAFTA"):
    """Paftanın kâğıt ölçüsü (mm)."""
    d = ezdxf.readfile(dxf_yolu)
    lay = d.layout(pafta_adi)
    alt, ust = lay.get_paper_limits()
    g, y = float(ust.x - alt.x), float(ust.y - alt.y)
    if g < 1.0 or y < 1.0:
        g, y = float(lay.dxf.paper_width), float(lay.dxf.paper_height)
    return g, y


def bas(dxf_yolu, cikti, pafta_adi="PAFTA", siyah=True, dpi=300):
    """Paftayı PDF ya da PNG olarak basar.

    Bu işlev KENDİLİĞİNDEN ÇAĞRILMAZ. Kullanıcı "BAS" dediğinde çalışır.
    Kâğıda birebir oturur: A3 pafta, 420x297 mm PDF olur; yazıcıda
    'sayfaya sığdır' demeye gerek kalmaz, %100 basılır."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import (Configuration, ColorPolicy,
                                             BackgroundPolicy)

    d = ezdxf.readfile(dxf_yolu)
    try:
        lay = d.layout(pafta_adi)
    except Exception:
        raise PaftaYok(f"{os.path.basename(dxf_yolu)} içinde "
                       f"'{pafta_adi}' paftası yok.")
    kg, ky = pafta_olcusu(dxf_yolu, pafta_adi)
    if kg < 1 or ky < 1:
        kg, ky = KAGIT[VARSAYILAN_KAGIT]

    fig = plt.figure(figsize=(kg / 25.4, ky / 25.4), dpi=dpi)
    eksen = fig.add_axes([0, 0, 1, 1])
    eksen.set_axis_off()
    ayar = Configuration(
        color_policy=ColorPolicy.BLACK if siyah else ColorPolicy.COLOR,
        background_policy=BackgroundPolicy.WHITE,
        lineweight_scaling=1.0,
    )
    Frontend(RenderContext(d), MatplotlibBackend(eksen), config=ayar
             ).draw_layout(lay, finalize=False)
    eksen.set_xlim(0, kg)
    eksen.set_ylim(0, ky)
    eksen.set_aspect("equal")
    os.makedirs(os.path.dirname(os.path.abspath(cikti)) or ".", exist_ok=True)
    fig.savefig(cikti, dpi=dpi, facecolor="white")
    plt.close(fig)
    return cikti


# --------------------------------------------------------------- toplu
def kagit_plani(dosyalar, tercih=VARSAYILAN_KAGIT):
    """Hangi çizim seçilen kâğıda hangi ölçekte oturur.

    Hiçbir dosya yazmaz, sadece bakar. Kullanıcı "hangisi 1:1 çıkıyor,
    hangisi küçülecek" diye görmek ister."""
    birebir, olcekli, sigmayan, hata = [], [], [], []
    for y in dosyalar:
        try:
            x0, y0, x1, y1 = cizim_kutusu(y)
            gx, gy = x1 - x0, y1 - y0
        except Exception as e:
            hata.append((y, str(e)))
            continue
        ye = yerlesim(gx, gy, tercih)
        kayit = {"dosya": y, "olcu": (gx, gy), "kagit": tercih,
                 "olcek": ye["olcek"] if ye else None,
                 "yer": ye["yer"] if ye else None}
        if not ye:
            kayit["birebir_kagit"] = kagit_sec(gx, gy)
            kayit["secenek"] = [(k, yerlesim(gx, gy, k)["olcek"])
                                for k in KAGIT_SIRA if yerlesim(gx, gy, k)]
            sigmayan.append(kayit)
        elif abs(ye["olcek"] - 1.0) < 1e-9:
            birebir.append(kayit)
        else:
            kayit["birebir_kagit"] = kagit_sec(gx, gy)
            kayit["daha_iyi"] = next(
                ((k, yerlesim(gx, gy, k)["olcek"]) for k in KAGIT_SIRA
                 if KAGIT[k][0] > KAGIT[tercih][0] and yerlesim(gx, gy, k)
                 and yerlesim(gx, gy, k)["olcek"] > ye["olcek"]), None)
            olcekli.append(kayit)
        try:
            kayit["yazi_mm"] = round(en_kucuk_yazi(y) * (kayit["olcek"] or 1), 2)
        except Exception:
            kayit["yazi_mm"] = 0.0
    return {"birebir": birebir, "olcekli": olcekli, "sigmayan": sigmayan,
            "hata": hata, "kagit": tercih}


def toplu_pafta(isler, cikti_klasor):
    """isler: [{"dosya":..., "kagit":"A3", "olcek": None}, ...]

    Her biri için kaynağın KOPYASINA pafta eklenir. Kaynak dosyalara
    dokunulmaz; çıktı ayrı klasöre yazılır."""
    os.makedirs(cikti_klasor, exist_ok=True)
    yapilan, hata = [], []
    for it in isler:
        y = it["dosya"]
        ad = os.path.splitext(os.path.basename(y))[0]
        kagit = it.get("kagit", VARSAYILAN_KAGIT)
        try:
            r = pafta_kur(y, os.path.join(cikti_klasor, f"{ad}_{kagit}.dxf"),
                          kagit, olcek=it.get("olcek"))
            r["kaynak"] = y
            yapilan.append(r)
        except Exception as e:
            hata.append((y, str(e)))
    return {"yapilan": yapilan, "hata": hata}


# ----------------------------------------------------------------- CLI
def _cli():
    import argparse
    import glob as _glob
    a = argparse.ArgumentParser(
        description="Pi3D – 1:1 DXF'leri standart A3 paftaya yerleştirir. "
                    "Kaynak dosyalara dokunulmaz.")
    a.add_argument("dxf", nargs="+", help="1:1 DXF dosyaları (joker olur)")
    a.add_argument("--kagit", default=VARSAYILAN_KAGIT,
                   choices=list(KAGIT_SIRA), help="her zaman yatay")
    a.add_argument("--olcek", type=float, default=None,
                   help="1 / 0.1 gibi; verilmezse sığan en büyüğü")
    a.add_argument("--cikti", default="PAFTA", help="çıktı klasörü")
    a.add_argument("--plan", action="store_true",
                   help="hiçbir şey yazma, hangi ölçekte oturduğunu söyle")
    a.add_argument("--bas", action="store_true", help="PDF de üret")
    n = a.parse_args()

    dosya = []
    for d in n.dxf:
        dosya += sorted(_glob.glob(d)) if any(c in d for c in "*?[") else [d]
    if not dosya:
        a.error("DXF bulunamadı.")

    p = kagit_plani(dosya, n.kagit)
    for s in p["birebir"]:
        print(f"  {n.kagit}  1:1   {os.path.basename(s['dosya'])}"
              f"   ({s['olcu'][0]:.0f}x{s['olcu'][1]:.0f})")
    for s in p["olcekli"]:
        di = s.get("daha_iyi")
        ek = f"   [{di[0]} olsa {olcek_metni(di[1])}]" if di else ""
        if 0 < s.get("yazi_mm", 0) < EN_AZ_YAZI_MM:
            ek += f"   [DIKKAT yazilar kagitta {s['yazi_mm']:.1f} mm kaliyor]"
        print(f"  {n.kagit}  {olcek_metni(s['olcek'])}   "
              f"{os.path.basename(s['dosya'])}"
              f"   ({s['olcu'][0]:.0f}x{s['olcu'][1]:.0f}){ek}")
    for s in p["sigmayan"]:
        sec = ", ".join(f"{k} {olcek_metni(o)}" for k, o in s["secenek"][:4])
        print(f"  SIĞMADI  {os.path.basename(s['dosya'])}"
              f"   ({s['olcu'][0]:.0f}x{s['olcu'][1]:.0f})  ->  "
              + (sec or "hiçbir kâğıda sığmıyor"))
    for y, e in p["hata"]:
        print(f"  HATA  {os.path.basename(y)}: {e}")
    if n.plan:
        return

    isler = [{"dosya": s["dosya"], "kagit": n.kagit, "olcek": n.olcek}
             for s in p["birebir"] + p["olcekli"]]
    if n.olcek:                       # ölçeği elle veren sığmayanları da dener
        isler += [{"dosya": s["dosya"], "kagit": n.kagit, "olcek": n.olcek}
                  for s in p["sigmayan"]]
    r = toplu_pafta(isler, n.cikti)
    print()
    for it in r["yapilan"]:
        print(f"  yazıldı  {it['kagit']} {it['olcek_metni']}  "
              f"{os.path.basename(it['dosya'])}")
        if n.bas:
            print("           ", bas(it["dosya"],
                                     os.path.splitext(it["dosya"])[0] + ".pdf"))
    for y, e in r["hata"]:
        print(f"  HATA  {os.path.basename(y)}: {e}")


if __name__ == "__main__":
    _cli()
