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
import sys

import ezdxf
import ezdxf.bbox
import pf9_excel as XL
import ezdxf.enums          # ezdxf sürümüne göre kendiliğinden gelmeyebilir

# ---------------------------------------------------------------- kâğıt
# Kâğıt YATAY ya da DİKEY olabilir; hangisi daha büyük ölçek veriyorsa o
# kullanılır. Önce yalnız yatay vardı: gerekçe, sac açınımlarının hep
# uzun olması ve antet kutusunun sağ alt köşede sabit durmasıydı. Ama
# uzun bir parça DİK duruyorsa (3000 mm boyunda bir profilin ön
# görünüşü) yatay kâğıtta 1:50'ye düşüyor ve resim neredeyse
# görünmüyordu; aynı parça dikey kâğıtta 1:20 çıkıyor. Kâğıdı parçaya
# uydurmak, parçayı kâğıda kurban etmekten iyidir.
#
# Dikey karşılıkların adı "-D" ekiyle yazılır: "A3" yatay, "A3-D"
# dikey. Böylece kâğıda bakan bütün işlevler (cerceve, antet_kutusu,
# cizim_alanlari, BOLGE...) tek bir sözlükten okumaya devam eder.
YON_EKI = "-D"

def _yon_ekle(d):
    """Her yatay kâğıdın dikey karşılığını da sözlüğe koyar."""
    for ad, (g, y) in list(d.items()):
        d[ad + YON_EKI] = (y, g)
    return d


KAGIT = _yon_ekle({
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
})
KAGIT_BOY = ("A4", "A3", "A2", "A1", "A0")     # yalnız boylar, yönsüz
KAGIT_SIRA = tuple(k for b in KAGIT_BOY for k in (b, b + YON_EKI))
VARSAYILAN_KAGIT = "A3"


def kagit_boyu(kagit):
    """Yön ekini atar: "A3-D" -> "A3"."""
    return kagit[:-len(YON_EKI)] if kagit.endswith(YON_EKI) else kagit


def dikey_mi(kagit):
    return kagit.endswith(YON_EKI)


def kagit_yonleri(kagit):
    """Bu boyun iki yönü: (yatay, dikey). Yön eki verilse de aynı."""
    b = kagit_boyu(kagit)
    return (b, b + YON_EKI)


def yon_adi(kagit):
    return "dikey" if dikey_mi(kagit) else "yatay"


def kagit_adi(kagit):
    """Kullanıcıya gösterilecek ad: "A3 yatay" / "A3 dikey"."""
    return f"{kagit_boyu(kagit)} {yon_adi(kagit)}"

KENAR = 15.0                 # çerçeve kâğıdın kenarından bu kadar içeride
DIS_PAY = 5.0                # ince dış çizgi kâğıdın kenarından
ANTET_EN, ANTET_BOY = 150.0, 100.0     # sağ alt köşede boş bırakılan kutu (firma anteti yapıştırılacak)
ANTET_BOY_PI3D = 65.0                  # Pi3D anteti çizilince (DENEME) alçak kutu: resim yeri kazanır

# Bölge bölümleri (ISO 5457): rakamlar soldan sağa, harfler yukarıdan
# aşağıya. "B3'teki delik" demek için. Sütun ve satır sayısı çifttir.
BOLGE = {"A4": (6, 4), "A3": (8, 4), "A2": (12, 6),
         "A1": (16, 8), "A0": (24, 12)}
# Dikey kâğıtta sütun ve satır sayısı yer değiştirir: bölge kareleri
# yine kareye yakın kalsın.
BOLGE.update({a + YON_EKI: (y, x) for a, (x, y) in list(BOLGE.items())})
BOLGE_HARF = "ABCDEFGHIJKL"

GORUNUS_KATMAN = "PI3D_GORUNUS_ALANI"   # motorun bıraktığı görünüş yerleri
GORUNUS_APPID = "PI3D"
BASLIK_AD = "BASLIK"
IC_PAY = 12.0            # çerçevenin ve antet alanının resme uzaklığı
# Çerçevenin üstünde resim no/isim için ayrılan şerit. Yazıların
# gerçekten ihtiyacı kadar: 4,5 + 3,0 mm yazı + paylar. Bir mm fazlası
# ölçeği bir kademe düşürebiliyor (A3'te 1:2 yerine 1:5), o yüzden dar
# tutuluyor.
BASLIK_YAZI, BASLIK_ALT_YAZI = 4.5, 3.0
BASLIK_SERIT = 11.7          # sag ust baslik seridi: 0,8 + 4,5lik satir + 1,6 + 3,0luk satir,
                            # yaziların olculen tasmalariyla birlikte
# Görünüşler arasındaki aralık. EN_AZ bir tercih değil, alt sınırdır:
# yüksek tutmak bir kademe ölçek kaybettirebiliyor (A3'te 1:2 yerine
# 1:5, yani resim yarı yarıya küçülüyor). 8 mm iki görünüşü ayırmaya
# yeter; yer varsa zaten EN_COK'a kadar açılıyor.
ARA_EN_AZ = 10.0
ARA_EN_COK = 15.0        # ve en çok bu kadar; görünüşler birbirine yakın dursun (kullanıcı: "sağ görüntüyü yanaştır")
SAYFA_AYIR_ORAN = 1.3    # yan görünüşler 2. sayfaya: ana görünüş ancak bu kadar büyüyorsa
SAYFA_AYIR_YAZI_MM = 1.2 # ... ve tek sayfada en küçük yazı bunun altında kalıyorsa
BILGI_AD = "BILGI"       # başlık bloğunun ızgara hücresi (pf3_olcu gorunus_isareti "BILGI")

HARF_ORAN = 0.62         # yazı genişliği ~ harf sayısı x yükseklik x bu
EN_AZ_YAZI_MM = 1.8      # kâğıtta bundan küçük yazı okunmaz (ISO 3098: 2,5)

# Teknik resimde kullanılan standart ölçekler (ISO 5455). Ara ölçek
# uydurulmaz: 1:7 diye bir resim olmaz.
#
# PDF yalnız GÖRSELDİR, ondan ölçü alınmaz (ölçü DXF'te 1:1). Kullanıcı:
# "1/15 1/17 1/14 1/8 ne bileyim, %70'ine yerleştir". Yalnız 1-2-5
# serisiyle bir kademe aşağı düşen resim kâğıdın küçük bir kısmında
# "karınca duası" gibi kalıyordu (P01: 1:10 sığmıyor, 1:20'de yazı 0,7
# mm). Sık aralıklı ölçekler arasından SIĞAN EN BÜYÜĞÜ seçilir.
KUCULTME = (1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
            17, 18, 20, 22, 25, 28, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 120,
            150, 200, 250, 300, 400, 500, 700, 1000)
BUYUTME = (1.5, 2, 2.5, 3, 4, 5, 10)

KAT_CERCEVE = "PAFTA_CERCEVE"
KAT_ANTET = "PAFTA_ANTET_ALANI"
KAT_BILGI = "PAFTA_BILGI"
KAT_BOLGE = "PAFTA_BOLGE"

# ---------------------------------------------------------- Pi3D anteti
# Firma anteti yoksa sağ alttaki 150 x 100 mm kutuya Pi3D'nin kendi
# anteti çizilir: üstte logo şeridi (Pi3D + PiVision), altında parça adı,
# resim no, malzeme, kütle, ölçek, kâğıt / sayfa, çizen, onaylayan.
# Logo DXF'e IMAGE olarak girer; resim dosyası (pi3d_antet.png) DXF'in
# yanına bir kez yazılır (CAD programı ve PDF basımı oradan okur).
# Ayar dosyasında antet_pi3d: 0 ise kutu eskisi gibi BOŞ bırakılır.
PI3D_ANTET_PNG = "pi3d_antet.png"
PI3D_ANTET_PX = (1031, 240)           # logo şeridi piksel ölçüsü (en, boy)
PI3D_ANTET_BANT = 17.0                # logo şeridi yüksekliği (mm)
PI3D_ANTET_ETIKET = 2.0               # alan adı yazı boyu (mm)
PI3D_ANTET_DEGER = 3.2                # alan değeri yazı boyu (mm)
PI3D_LACIVERT = (19, 53, 83)          # PiVision yazısının kâğıt üstündeki rengi
_IMGDEF = {}                           # belge -> IMAGEDEF (sayfalar paylaşır)


def pi3d_antet_acik(istek=None):
    """Pi3D anteti çizilsin mi? Çağıran açıkça söylemişse o; yoksa ayar
    dosyasındaki antet_pi3d (varsayılan 1)."""
    # DENEME lisansında (ya da lisanssız) her pafta Pi3D / PiVision
    # antetlidir: ne firma anteti ne boş kutu (kullanıcı: "deneme
    # sürümünde kesinlikle PiVision çıkacak").
    try:
        import pf5_antet as PA
        if PA.deneme_mi():
            return True
    except Exception:
        pass
    if istek is not None:
        return bool(istek)
    try:
        import pf3_olcu
        return bool(int(pf3_olcu.ayar_oku().get("antet_pi3d", 1)))
    except Exception:
        return True


def lisansli_sablon(sablon):
    """Firma anteti yalnız lisanslıda: DENEME'de verilen şablon yok sayılır."""
    if sablon is None:
        return None
    try:
        import pf5_antet as PA
        return None if PA.deneme_mi() else sablon
    except Exception:
        return sablon


def ayarli_firma_anteti():
    """Ayarda kayıtlı firma anteti (Yardım > Firma anteti ile kurulan);
    lisans izin vermiyorsa None."""
    try:
        import pf5_antet as PA
        return PA.ayarli_sablon() if PA.firma_anteti_izinli() else None
    except Exception:
        return None


def _logo_baytlari(ad):
    """Logonun ham baytı: önce exe'ye gömülü pi3d_logo, yoksa logo/ klasörü."""
    try:
        import pi3d_logo
        v = getattr(pi3d_logo, "LOGO", {}).get(ad)
        if v:
            if isinstance(v, str):          # gömülü resim base64 metindir
                import base64
                return base64.b64decode(v)
            return v
    except Exception:
        pass
    kok = os.path.dirname(os.path.abspath(__file__))
    for yol in (os.path.join(kok, "logo", ad),
                os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "logo", ad)):
        if os.path.isfile(yol):
            with open(yol, "rb") as f:
                return f.read()
    return None


def pi3d_antet_resmi(klasor):
    """Antet logo şeridini (Pi3D logosu + lacivert PiVision yazısı) klasöre
    PNG olarak yazar; varsa dokunmaz. Döner: dosya adı ya da None."""
    yol = os.path.join(klasor, PI3D_ANTET_PNG)
    if os.path.isfile(yol):
        return PI3D_ANTET_PNG
    try:
        import io
        from PIL import Image
        import numpy as np
        a = Image.open(io.BytesIO(_logo_baytlari("pi3d_256.png"))).convert("RGBA")
        b = Image.open(io.BytesIO(_logo_baytlari("pivision_beyaz.png"))).convert("RGBA")
        H = PI3D_ANTET_PX[1]
        a = a.resize((H, H), Image.LANCZOS)
        b = b.resize((int(round(b.width * H / b.height)), H), Image.LANCZOS)
        px = np.array(b)
        px[:, :, :3] = PI3D_LACIVERT          # beyaz yazı kâğıtta görünmez: lacivert
        b = Image.fromarray(px)
        out = Image.new("RGBA", (H + 40 + b.width, H), (255, 255, 255, 255))
        out.alpha_composite(a, (0, 0))
        out.alpha_composite(b, (H + 40, 0))
        out = out.convert("RGB")
        if out.size != PI3D_ANTET_PX:
            out = out.resize(PI3D_ANTET_PX, Image.LANCZOS)
        out.save(yol)
        return PI3D_ANTET_PNG
    except Exception:
        return None


def _antet_yazi(pafta, metin, x, y, genislik, h, stil, sag=False):
    """Antet kutusuna yazı; sığmıyorsa önce küçültür, sonra kısaltır
    (ölçülerek - pf5_antet.Sablon._yaz ile aynı mantık)."""
    metin = str(metin)
    if not metin:
        return None

    def koy(m, yuk):
        t = pafta.add_text(m, height=yuk, dxfattribs={"layer": KAT_ANTET, "style": stil})
        t.set_placement((x, y), align=(ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT if sag
                                       else ezdxf.enums.TextEntityAlignment.LEFT))
        return t
    t = koy(metin, h)
    for _ in range(8):
        try:
            k = ezdxf.bbox.extents([t], fast=False)
        except Exception:
            return t
        en = k.extmax.x - k.extmin.x
        if en <= genislik:
            return t
        pafta.delete_entity(t)
        if h > 1.8:
            h = max(h * 0.85, 1.8)
        elif len(metin) > 4:
            n = max(3, min(len(metin) - 1, int(len(metin) * genislik / en) - 1))
            metin = metin[:n] + "…"
        else:
            return koy(metin, h)
        t = koy(metin, h)
    return t


def _pi3d_antet_ciz(pafta, kagit, deger, stil):
    """Pi3D antetini sağ alt kutuya çizer (firma anteti yokken)."""
    d = pafta.doc
    if KAT_ANTET not in d.layers:
        d.layers.add(KAT_ANTET, color=7)
    x0, y0, x1, y1 = antet_kutusu(kagit)
    W = x1 - x0

    def cizgi(ax, ay, bx, by, kalin=13):
        pafta.add_line((ax, ay), (bx, by), dxfattribs={"layer": KAT_ANTET, "lineweight": kalin})
    cizgi(x0, y1, x1, y1, 35)              # üst ve sol kenar (sağ / alt çerçevedir)
    cizgi(x0, y0, x0, y1, 35)
    bant = PI3D_ANTET_BANT
    yb = y1 - bant
    cizgi(x0, yb, x1, yb, 35)
    # --- logo şeridi
    klasor = deger.get("_klasor")
    ad = pi3d_antet_resmi(klasor) if klasor else None
    if ad:
        anahtar = id(d)
        if anahtar not in _IMGDEF:
            _IMGDEF[anahtar] = d.add_image_def(filename=ad, size_in_pixel=PI3D_ANTET_PX)
        hi = bant - 5.0
        wi = hi * PI3D_ANTET_PX[0] / PI3D_ANTET_PX[1]
        pafta.add_image(image_def=_IMGDEF[anahtar], insert=(x0 + 3.0, yb + 2.5),
                        size_in_units=(wi, hi), dxfattribs={"layer": KAT_ANTET})
    else:
        _antet_yazi(pafta, "Pi3D  ·  PiVision", x0 + 3.0, yb + 9.0, W - 6.0, 6.0, stil)
    try:
        import pf7_is
        surum = f"Pi3D v{pf7_is.PI3D_SURUM}"
    except Exception:
        surum = "Pi3D"
    _antet_yazi(pafta, surum, x1 - 2.0, yb + 1.5, 40.0, PI3D_ANTET_ETIKET, stil, sag=True)
    # --- alanlar: 5 satır, bazıları iki sütun
    r = (yb - y0) / 5.0
    xm = x0 + W / 2.0

    def m(ad):
        v = deger.get(ad, "")
        return v if isinstance(v, str) else ("" if v is None else str(v))
    deger = {k: m(k) for k in ("parca_adi", "resim_no", "dosya", "malzeme", "kutle", "olcek",
                               "kagit", "cizen", "cizen_tarih", "onaylayan", "onay_tarih")} | \
        {"sayfa": deger.get("sayfa")}
    satirlar = [
        [("PARÇA ADI", deger.get("parca_adi", ""))],
        [("RESİM NO", deger.get("resim_no", "")), ("DOSYA", deger.get("dosya", ""))],
        [("MALZEME", deger.get("malzeme", "")), ("KÜTLE", deger.get("kutle", ""))],
        [("ÖLÇEK", deger.get("olcek", "")),
         ("KÂĞIT / SAYFA", "  ·  ".join(v for v in (deger.get("kagit", ""),
                                                   f"sayfa {deger['sayfa']}" if deger.get("sayfa") else "") if v))],
        [("ÇİZEN", "  ".join(v for v in (deger.get("cizen", ""), deger.get("cizen_tarih", "")) if v)),
         ("ONAYLAYAN", "  ".join(v for v in (deger.get("onaylayan", ""), deger.get("onay_tarih", "")) if v))],
    ]
    for i, hucreler in enumerate(satirlar):
        yt = yb - i * r                     # satırın üst kenarı
        if i:
            cizgi(x0, yt, x1, yt)
        if len(hucreler) == 2:
            cizgi(xm, yt, xm, yt - r)
        for j, (etiket, v) in enumerate(hucreler):
            xa = x0 if (j == 0) else xm
            gen = (W if len(hucreler) == 1 else W / 2.0) - 4.0
            _antet_yazi(pafta, etiket, xa + 2.0, yt - PI3D_ANTET_ETIKET - 1.2, gen, PI3D_ANTET_ETIKET, stil)
            _antet_yazi(pafta, v, xa + 2.0, yt - r + 2.0, gen, PI3D_ANTET_DEGER, stil)


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


def _mtext_kutusu(v):
    """MTEXT'in TEK SATIR ölçülmüş sınırı (x0, y0, x1, y1).

    ezdxf'in sınır kutusu genişliği verilmemiş MTEXT'i boşluklardan
    satırlara kırılmış sayar: "6x Ø45" iki satırlık dar bir sütun
    ölçülür, PDF'te ise tek satır basılır. Pencere dar açılıyor, yazı
    kenardan kırpılıyordu (P06: "6x Ø4"). Genişlik yazı ölçüm aracından
    (mtext_size) alınır; pf3_olcu.mtext_kutusu ile aynı hesap."""
    import math
    from ezdxf.tools import text_size as _ts
    m = _ts.mtext_size(v)
    w, hh = m.total_width, m.total_height
    ap = v.dxf.get("attachment_point", 1)
    ox = {1: 0, 4: 0, 7: 0, 2: -w / 2, 5: -w / 2, 8: -w / 2}.get(ap, -w)
    oy = {1: -hh, 2: -hh, 3: -hh, 4: -hh / 2, 5: -hh / 2, 6: -hh / 2}.get(ap, 0.0)
    td = v.dxf.get("text_direction", None)
    if td is not None and (abs(td[0]) + abs(td[1])) > 1e-12:
        a = math.atan2(td[1], td[0])
    else:
        a = math.radians(v.dxf.get("rotation", 0.0) or 0.0)
    ca, sa = math.cos(a), math.sin(a)
    ix, iy = v.dxf.insert.x, v.dxf.insert.y
    pts = [(ix + x * ca - y * sa, iy + x * sa + y * ca)
           for x, y in ((ox, oy), (ox + w, oy), (ox + w, oy + hh), (ox, oy + hh))]
    return (min(q[0] for q in pts), min(q[1] for q in pts),
            max(q[0] for q in pts), max(q[1] for q in pts))


def _varlik_kutulari(varlik, harf_payi=False):
    """Her varlığın sınırı [(x0, y0, x1, y1)] - boş olanlar atlanır.
    MTEXT tek satır ölçülür (bkz. _mtext_kutusu), gerisi ezdxf'ten.

    harf_payi: TEXT kutusu Ü/Ö/Ğ'nin noktası ve Ç/Ş/Ğ'nin kuyruğu kadar
    büyütülür. ezdxf kutusu büyük harf boyundadır; pencere buna göre
    açılınca etiketin noktaları kırpılıyor, PDF'te "ÜST" "UST", "SAĞ"
    "SAG" basılıyordu. Yalnız pencere BOYU için kullanılır."""
    # ÖNBELLEK: pafta_kur bu işlevi aynı belge için onlarca kez çağırır
    # (her plan denemesi); ezdxf'in kutu hesabı 12 bin varlıkta 1,4 s
    # sürüyor, büyük parçada pafta 85 s oluyordu. Kutu varlığın
    # handle'ına göre bir kez hesaplanır (varlık pafta kurulurken
    # değişmez; model uzayı pafta_denetimi ile de doğrulanır).
    varlik = list(varlik)
    out = []
    eksik = [e for e in varlik if (id(e.doc), e.dxf.handle, harf_payi) not in _KUTU_ONBELLEK]
    if eksik:
        for e, k in zip(eksik, ezdxf.bbox.multi_flat(eksik)):
            _KUTU_ONBELLEK[(id(e.doc), e.dxf.handle, harf_payi)] = _varlik_kutusu_tek(e, k, harf_payi)
    for e in varlik:
        b = _KUTU_ONBELLEK[(id(e.doc), e.dxf.handle, harf_payi)]
        if b is not None:
            out.append(b)
    return out


_KUTU_ONBELLEK = {}


def _varlik_kutusu_tek(e, k, harf_payi):
    """Tek varlığın kutusu (bkz. _varlik_kutulari) ya da None."""
    if True:
        if not k.has_data:
            return None
        b = (k.extmin.x, k.extmin.y, k.extmax.x, k.extmax.y)
        t = e.dxftype()
        if harf_payi and t == "TEXT":
            try:
                hh = float(e.dxf.height or 0)
                b = (b[0], b[1] - 0.3 * hh, b[2], b[3] + 0.35 * hh)
            except Exception:
                pass
        try:
            # ölçünün yazısı da bloğunun içinde bir MTEXT'tir
            ic = ([e] if t == "MTEXT" else
                  [v for v in e.virtual_entities() if v.dxftype() == "MTEXT"]
                  if t == "DIMENSION" else [])
            for v in ic:
                m = _mtext_kutusu(v)
                b = (min(b[0], m[0]), min(b[1], m[1]),
                     max(b[2], m[2]), max(b[3], m[3]))
        except Exception:
            pass
        return b


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
        kl = _varlik_kutulari(
            [e for e in d.modelspace() if e.dxf.layer != GORUNUS_KATMAN])
        if kl:
            return (float(min(b[0] for b in kl)), float(min(b[1] for b in kl)),
                    float(max(b[2] for b in kl)), float(max(b[3] for b in kl)))
    except Exception:
        pass                      # eski ezdxf ya da bozuk varlık: kabaca ölç
    k = _varlik_kutusu(d.modelspace())
    if not k:
        raise PaftaYok(f"{os.path.basename(yol)}: çizimde varlık yok.")
    return k


def gorunus_alanlari(d):
    """Motorun işaretlediği görünüş yerleri: {ad: (x0, y0, x1, y1)}.

    Yoksa boş sözlük döner - eski resimler ve elle çizilmiş DXF'ler
    tek pencereyle yerleşir."""
    a = {}
    for e in d.modelspace().query(f'LWPOLYLINE[layer=="{GORUNUS_KATMAN}"]'):
        try:
            x = e.get_xdata(GORUNUS_APPID)
        except Exception:
            continue
        ad = next((v for k, v in x if k == 1000), None)
        if not ad:
            continue
        p = [(q[0], q[1]) for q in e.get_points()]
        a[ad] = (min(q[0] for q in p), min(q[1] for q in p),
                 max(q[0] for q in p), max(q[1] for q in p))
    return a


def _kumele(araliklar, pay=1e-6):
    """Üst üste binen aralıkları gruplar, küçükten büyüğe sıralı döner.

    Görünüşler izdüşüm ızgarasındadır: aynı sütundakiler x'te örtüşür,
    aynı satırdakiler y'de. Örtüşmeye bakmak merkezleri yuvarlamaktan
    sağlamdır - görünüş boyları birbirinden çok farklı olabilir."""
    if not araliklar:
        return []
    sirali = sorted(araliklar, key=lambda t: t[0])
    grup = [[sirali[0][0], sirali[0][1], [sirali[0][2]]]]
    for a, b, ad in sirali[1:]:
        if a < grup[-1][1] - pay:
            grup[-1][1] = max(grup[-1][1], b)
            grup[-1][2].append(ad)
        else:
            grup.append([a, b, [ad]])
    return grup


def _kutu_uzakligi(k, b):
    """Bir varlık kutusunun bir görünüş kutusuna uzaklığı (içindeyse 0)."""
    dx = max(b[0] - k[2], k[0] - b[2], 0.0)
    dy = max(b[1] - k[3], k[1] - b[3], 0.0)
    return dx * dx + dy * dy


def _gorunus_kutulari(d, alanlar, haric=()):
    """Her görünüşün GERÇEK sınırı: ona ait bütün çizgi, ölçü ve yazı.

    Motorun bıraktığı işaret yalnız görünüşün kendisini gösterir; ölçü
    çizgileri, etiketler, çap yazıları onun dışına taşar. Her varlık en
    yakın görünüşe verilir, sınır o varlıklardan çıkarılır. Hücrelerin
    GERÇEKTEN dar olması şart: görünüşler arasındaki büyük model
    boşlukları böyle dışarıda kalır ve kâğıtta yerlerine eşit aralıklar
    konur. Aynı kâğıtta daha büyük ölçek buradan çıkar.

    Hiçbir varlık dışarıda kalmaz: her biri bir görünüşe yazılır."""
    gor = {k: v for k, v in alanlar.items() if k != BASLIK_AD}
    if not gor:
        return {}
    bas = alanlar.get(BASLIK_AD)
    kutu = {k: list(v) for k, v in gor.items()}
    try:
        varlik = [e for e in d.modelspace() if e.dxf.layer != GORUNUS_KATMAN]
        kutular = list(zip(_varlik_kutulari(varlik),
                           _varlik_kutulari(varlik, harf_payi=True)))
    except Exception:
        return {k: tuple(v) for k, v in kutu.items()}
    for b0, b in kutular:
        if bas and (b0[0] >= bas[0] - 0.01 and b0[1] >= bas[1] - 0.01
                    and b0[2] <= bas[2] + 0.01 and b0[3] <= bas[3] + 0.01):
            continue                    # başlık bloğunun parçası
        if any(b0[0] >= c[0] - 0.02 and b0[1] >= c[1] - 0.02
               and b0[2] <= c[2] + 0.02 and b0[3] <= c[3] + 0.02 for c in haric):
            continue                    # 2. sayfadaki pencerenin parçası
        ad = min(gor, key=lambda a: _kutu_uzakligi(b, gor[a]))
        q = kutu[ad]
        q[0] = min(q[0], b[0]); q[1] = min(q[1], b[1])
        q[2] = max(q[2], b[2]); q[3] = max(q[3], b[3])
    return {k: tuple(v) for k, v in kutu.items()}


IZO_AD = "IZO"           # küçük perspektif (pf3_olcu.IZO_AD); serbest, hep 1. sayfada
SAYFA1_SERBEST = (IZO_AD, BASLIK_AD)   # 2. sayfaya gitmeyen serbest pencereler (bilgi bloğu ayrıca)


def _serbest_mi(ad):
    """DETAY ve PERSPEKTİF görünüşleri izdüşüm ızgarasının parçası değildir:
    kâğıdın boş yerine SERBEST pencere olarak konur (bkz. _serbest_yerlestir)."""
    return str(ad).startswith("DETAY") or str(ad) == IZO_AD


def _serbest_kutular(d, alanlar):
    """Serbest pencerelerin (detaylar) gerçek model sınırları {ad: kutu}."""
    if not any(_serbest_mi(a) for a in alanlar):
        return {}
    return {k: v for k, v in _gorunus_kutulari(d, alanlar).items() if _serbest_mi(k)}


def _izgara(d, alanlar, kutu, haric=()):
    """Görünüşleri satır/sütun ızgarasına oturtur.

    İzdüşüm ızgarası BOZULMAZ: aynı satırdaki görünüşler kâğıtta da aynı
    hizada, aynı sütundakiler aynı düşeyde kalır. Bunu sağlamak için bir
    satırdaki bütün hücreler o satırın ORTAK y aralığını, bir sütundaki
    hücreler ortak x aralığını kullanır; yoksa görünüşler birbirinden
    kayar ve resim teknik resim olmaktan çıkar.

    Döner: (sutun_gen, satir_boy, hucre) ya da None."""
    dar = {k: v for k, v in _gorunus_kutulari(d, alanlar, haric=haric).items()
           if not _serbest_mi(k)}
    if len(dar) < 1:
        return None
    if len(dar) == 1:                    # tek görünüş (öbürleri 2. sayfada)
        ad, v = next(iter(dar.items()))
        return ([v[2] - v[0]], [v[3] - v[1]], {ad: (0, 0, tuple(v))})
    sut = _kumele([(v[0], v[2], k) for k, v in dar.items()])
    sat = _kumele([(v[1], v[3], k) for k, v in dar.items()])
    if len(sut) < 2 and len(sat) < 2:
        return None                     # tek göz: dağıtılacak bir şey yok
    for g in (sut, sat):                # gruplar üst üste binmemeli
        for a, b in zip(g, g[1:]):
            if b[0] < a[1] - 1e-6:
                return None
    yerm = {}
    for j, g in enumerate(sut):
        for ad in g[2]:
            yerm.setdefault(ad, [0, 0])[0] = j
    for i, g in enumerate(sat):
        for ad in g[2]:
            yerm.setdefault(ad, [0, 0])[1] = i
    hucre = {ad: (j, i, (sut[j][0], sat[i][0], sut[j][1], sat[i][1]))
             for ad, (j, i) in yerm.items()}
    return ([g[1] - g[0] for g in sut], [g[1] - g[0] for g in sat], hucre)


def _pencere_temiz_mi(d, hucreler, haric=()):
    """Her çizgi TAM OLARAK BİR pencerenin içinde mi?

    Bu denetim şart, çünkü bir pencere kendisine "ait" olanı değil,
    DİKDÖRTGENİNE DÜŞEN HER ŞEYİ gösterir. Bir yazı iki pencerenin
    sınırına denk gelirse ikisinde de, yarım yarım çıkar; hiçbirine
    düşmezse hiç çıkmaz. Montaj resminde tam bu oldu: başlık bloğu
    görünüş pencerelerinin sınırına denk geldi ve paftada hem doğru
    yerinde hem de görünüşlerin arasında parça parça göründü.

    Bir tane bile şüpheli varlık varsa çok pencereli yerleşimden
    vazgeçilir; tek pencere, bozuk resimden iyidir."""
    # Önce pencereler birbirinin üstüne binmesin: binerse ortak bölgedeki
    # çizgi İKİ kere basılır.
    for i in range(len(hucreler)):
        for j in range(i + 1, len(hucreler)):
            a, b = hucreler[i], hucreler[j]
            if (a[0] < b[2] - 0.02 and a[2] > b[0] + 0.02
                    and a[1] < b[3] - 0.02 and a[3] > b[1] + 0.02):
                return False
    try:
        varlik = [e for e in d.modelspace() if e.dxf.layer != GORUNUS_KATMAN]
        for b in _varlik_kutulari(varlik):
            # 2. sayfaya giden detayın varlıkları bu sayfanın denetimine
            # girmez (haric: detay pencereleri)
            if any(b[0] >= c[0] - 0.02 and b[1] >= c[1] - 0.02
                   and b[2] <= c[2] + 0.02 and b[3] <= c[3] + 0.02 for c in haric):
                continue
            # Ölçüt tek: varlık TAM OLARAK BİR hücrenin içinde olmalı.
            # Hücreler birbiriyle çakışmadığı için "birden fazlasının
            # içinde" olamaz; hiçbirinin içinde değilse ya sınırı aşıyor
            # (iki pencerede yarım yarım çıkar) ya da hepsinin dışında
            # (hiç çıkmaz). İkisi de kabul edilemez.
            #
            # Pay şart: görünüşün tam kenarında duran sıfır genişlikli
            # çizgiler var (parçanın kenar konturu), onlar hücrenin
            # içinde sayılmalı.
            if sum(1 for c in hucreler
                   if b[0] >= c[0] - 0.02 and b[1] >= c[1] - 0.02
                   and b[2] <= c[2] + 0.02 and b[3] <= c[3] + 0.02) != 1:
                return False
    except Exception:
        return False
    return True


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
        return f"1:{round(1 / o, 2):g}".replace(".", ",")
    return f"{round(o, 2):g}:1".replace(".", ",")


def cerceve(kagit=VARSAYILAN_KAGIT, sablon=None):
    """Çerçevenin köşeleri (x0, y0, x1, y1).

    Firma anteti kullanılıyorsa çerçeve de ONUN çerçevesidir: antet ve
    çerçeve aynı çizimden gelir, ikisini ayırmak resmin kenar paylarını
    firmanınkinden farklı yapardı."""
    if kagit not in KAGIT:
        raise PaftaYok(f"Bilinmeyen kâğıt: {kagit}")
    g, y = KAGIT[kagit]
    if sablon is not None:
        return sablon.cerceve((g, y))
    return (KENAR, KENAR, g - KENAR, y - KENAR)


def antet_kutusu(kagit=VARSAYILAN_KAGIT, sablon=None):
    """Sağ alt köşede BOŞ bırakılan alan (x0, y0, x1, y1).

    Buraya asla resim gelmez; firma kendi antetini oraya yapıştırır.
    ÇİZİLMEZ - kendi çerçevesi olan bir anteti yapıştırınca iki çizgi
    üst üste binerdi. Alan yalnız hesapta vardır.

    Ölçüsü kâğıttan kâğıda değişmez: antet A3'te ne kadarsa A1'de de
    o kadardır. Yazı boyları kâğıtla büyümez."""
    if sablon is not None:
        return sablon.antet_kutusu(KAGIT[kagit])
    x0, y0, x1, y1 = cerceve(kagit)
    # Pi3D anteti çizilecekse (DENEME, ya da firma anteti yokken ayar açık)
    # kutu ALÇAKTIR (kullanıcı: "antet yüksek gelmiş; normal antette bu
    # yerleşim mümkün"): 100 mm'lik kutu yalnız firma kendi antetini
    # yapıştıracaksa (antet_pi3d: 0) ayrılır.
    boy = ANTET_BOY_PI3D if pi3d_antet_acik() else ANTET_BOY
    return (max(x0, x1 - ANTET_EN), y0, x1, min(y1, y0 + boy))


def cizim_alanlari(kagit=VARSAYILAN_KAGIT, sablon=None):
    """Çizimin oturabileceği iki dikdörtgen.

    Antet kutusu sağ alt köşeyi yediği için kalan boşluk L biçimindedir.
    Bir resim dikdörtgendir; L'ye iki türlü sığar: kutunun ÜSTÜNE tam
    genişlikte, ya da SOLUNA tam yükseklikte. Hangisi daha büyük ölçek
    veriyorsa o kullanılır.

    Alanlar çerçeveye ve antet alanına DAYANMAZ: her yönde IC_PAY
    kadar (12 mm) boşluk bırakılır. Çerçeveye yapışmış bir resim hem
    kötü görünür hem de baskıda kenara taşma riski taşır. Çerçevenin
    üstünde ayrıca BASLIK_SERIT kadar yer resim no ve isim içindir."""
    fx0, fy0, fx1, fy1 = cerceve(kagit, sablon)
    ax0, _, _, ay1 = antet_kutusu(kagit, sablon)
    p = IC_PAY
    # Resim no/isim, çerçevenin üstündeki İÇ PAYIN İÇİNE yazılır; o pay
    # zaten boştu. Ayrıca yer ayırmak gereksiz yere ölçek düşürüyordu -
    # A3'te 1:2 yerine 1:5, yani resim yarı yarıya küçülüyordu.
    # Firma anteti varsa resim no ve isim ANTETE yazılır; çerçevenin
    # üstünde ayrıca başlık şeridine gerek yoktur.
    ust = fy1 - (p if sablon is not None else max(p, BASLIK_SERIT + 1.0))
    return {"ust": (fx0 + p, ay1 + p, fx1 - p, ust),
            "sol": (fx0 + p, fy0 + p, ax0 - p, ust)}


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


def yerlesim(gx, gy, kagit=VARSAYILAN_KAGIT, buyutme=False, sablon=None):
    """Çizim bu kâğıda nasıl oturur.

    Döner: {"olcek":, "yer": "ust"/"sol", "alan": (x0,y0,x1,y1),
            "kagit": kullanılan kâğıt (yön ekiyle)}
    Sığmıyorsa None.

    Yön ekiyle bir kâğıt verilirse ("A3-D") yalnız o yön denenir.
    Yönsüz verilirse ("A3") İKİ YÖN DE denenir ve daha büyük ölçek
    veren seçilir; eşitse yatay kalır (teknik resimde alışılmış olan
    odur, ayrıca dosyalama kolaylığı).

    Firma anteti kullanılıyorsa yön aranmaz: antet yatay çizilmiştir,
    dikey karşılığı yoktur."""
    # Kâğıt HER ZAMAN YATAY (kullanıcı: "resimler yatay olacak"); dikey
    # yalnız açıkça istenirse ("A3-D").
    adaylar = (((kagit_boyu(kagit),) if not dikey_mi(kagit) else (kagit,))
               if sablon is None else (kagit_boyu(kagit),))
    en_iyi = None
    for kg in adaylar:
        for yer, a in cizim_alanlari(kg, sablon).items():
            o = sigan_olcek(gx, gy, a[2] - a[0], a[3] - a[1], buyutme)
            if o and (en_iyi is None or o > en_iyi["olcek"]):
                en_iyi = {"olcek": o, "yer": yer, "alan": a, "kagit": kg}
    return en_iyi


def kagit_sec(gx, gy, adaylar=KAGIT_BOY, en_az_olcek=1.0, sablon=None):
    """Çizimi istenen ölçekte alan EN KÜÇÜK kâğıt (yön ekiyle). Yoksa None."""
    for k in adaylar:
        y = yerlesim(gx, gy, k, sablon=sablon)
        if y and y["olcek"] >= en_az_olcek - 1e-9:
            return y.get("kagit", k)
    return None


# --------------------------------------------------------------- pafta
def cok_pencere_plani(d, kutu, alan_g, alan_y, olcek_zorla=None, serbest_izin=False, baslik_serbest=False,
                      serbest_sayfa2=False, sayfa2_gorunus=()):
    """Görünüşleri kâğıda ORTADAN DIŞA, eşit aralıklarla dağıtan plan.

    Mantık: görünüşler resimde zaten izdüşüm ızgarasındadır (ÖN'ün solu
    SAĞ, sağı SOL, altı ÜST). O ızgara bozulmaz - bozulursa resim teknik
    resim olmaktan çıkar. Değişen yalnız ARALIKLAR: resimdeki büyük
    model boşlukları atılır, yerine kâğıtta eşit aralıklar konur ve
    öbek kâğıdın ortasına oturur.

    Dar ve uzun bir parçada da kural aynıdır; yalnız ölçek düşer ve
    aralık daralır. Dayanak noktası hiçbir zaman kenar değildir.

    Döner: {"olcek", "sutun", "satir", "hucre", "baslik", ...} ya da
    None (ızgara kurulamadıysa; o zaman tek pencere kullanılır)."""
    alanlar = gorunus_alanlari(d)
    # 2. SAYFAYA GİDEN GÖRÜNÜŞLER (sayfa2_gorunus): ana resim tek başına
    # belirgin büyük çıkıyorsa yan görünüşler 2. sayfaya (kullanıcı: "ana
    # resmi büyüt, gerekirse birden fazla sayfa"). Bu sayfanın ızgarasına
    # girmezler; varlıkları bu sayfanın denetiminde sayılmaz.
    gor2, bilgi_serbest = {}, {}
    if sayfa2_gorunus:
        dar_hepsi = _gorunus_kutulari(d, alanlar)
        gor2 = {a: dar_hepsi[a] for a in sayfa2_gorunus if a in dar_hepsi}
        alanlar = {a: b for a, b in alanlar.items() if a not in gor2}
        # Bilgi bloğu (parça adı, malzeme) 1. sayfada kalır ama ızgaraya
        # girmez: ızgarada ana görünüşün yanına sütun açar, resmi küçültür.
        # Serbest pencere gibi kâğıdın boş yerine konur.
        if BILGI_AD in alanlar and BILGI_AD in dar_hepsi:
            bilgi_serbest = {BILGI_AD: dar_hepsi[BILGI_AD]}
            alanlar = {a: b for a, b in alanlar.items() if a != BILGI_AD}
    elif serbest_izin and BILGI_AD in alanlar:
        # Bilgi bloğu ızgaranın boş bir hücresine düşüyorsa orada kalır; YENİ
        # satır ya da sütun açıyorsa (ARKA sütunun altına inince boşalan
        # yere konmuş, satır eklemiş; yan kapak 1:7'den 1:11'e düşmüştü)
        # serbest pencere olur, kâğıdın boş yerine konur.
        dar_hepsi = _gorunus_kutulari(d, alanlar)
        alansiz = {a: b for a, b in alanlar.items() if a != BILGI_AD}
        iz_w = _izgara(d, alanlar, kutu)
        iz_wo = _izgara(d, alansiz, kutu, haric=[dar_hepsi[BILGI_AD]] if BILGI_AD in dar_hepsi else ())
        if iz_wo and (not iz_w or len(iz_w[0]) > len(iz_wo[0]) or len(iz_w[1]) > len(iz_wo[1])):
            bilgi_serbest = {BILGI_AD: dar_hepsi[BILGI_AD]}
            alanlar = alansiz
    iz = _izgara(d, alanlar, kutu, haric=list(gor2.values()) + list(bilgi_serbest.values()))
    if not iz:
        return None
    sutun, satir, hucre = iz
    baslik = alanlar.get(BASLIK_AD)
    bg = (baslik[2] - baslik[0]) if baslik else 0.0
    bb = (baslik[3] - baslik[1]) if baslik else 0.0
    serbest = _serbest_kutular(d, alanlar)
    if serbest and not (serbest_izin or serbest_sayfa2):
        return None          # detaylar yalnız tam kâğıt planında yerleşir
    # Detaylar 2. SAYFAYA gidebilir; perspektif (IZO) hep 1. sayfada kalır
    sayfa2 = {a: b for a, b in serbest.items() if a not in SAYFA1_SERBEST} if serbest_sayfa2 else {}
    if serbest_sayfa2:
        serbest = {a: b for a, b in serbest.items() if a in SAYFA1_SERBEST}
    serbest = dict(serbest, **bilgi_serbest)   # bilgi bloğu hep 1. sayfada
    if baslik_serbest and baslik is not None and serbest_izin:
        # BAŞLIK BLOĞU SERBEST: öbeğin üstünde tam genişlikte şerit açmak
        # yerine kâğıdın boş yerine (yan kapakta öbeğin üstündeki 28 mm'lik
        # şerit ARKA satırını antete bindiriyor, 1:8 yerine 1:11 çıkıyordu)
        serbest = dict(serbest, **{BASLIK_AD: baslik})
        baslik = None
        bg = bb = 0.0
    sayfa2.update(gor2)
    hepsi = ([h[2] for h in hucre.values()] + ([baslik] if baslik else [])
             + list(serbest.values()))
    if not _pencere_temiz_mi(d, hepsi, haric=list(sayfa2.values())):
        return None

    ts, tr = sum(sutun), sum(satir)
    nj, ni = len(sutun), len(satir)
    olcek = None
    for k in (KUCULTME if olcek_zorla is None else (1.0 / olcek_zorla,)):
        o = 1.0 / k
        gen = max(ts * o + (nj - 1) * ARA_EN_AZ, bg * o)
        boy = tr * o + (ni - 1) * ARA_EN_AZ + (bb * o + ARA_EN_AZ if baslik else 0)
        if gen <= alan_g + 1e-6 and boy <= alan_y + 1e-6:
            olcek = o
            break
    if not olcek:
        return None

    def _kis(v, alt, ust):
        return alt if v < alt else (ust if v > ust else v)

    ax = _kis((alan_g - ts * olcek) / (nj + 1), ARA_EN_AZ, ARA_EN_COK) if nj > 1 else 0.0
    kalan_y = alan_y - (bb * olcek + ARA_EN_AZ if baslik else 0)
    ay = _kis((kalan_y - tr * olcek) / (ni + 1), ARA_EN_AZ, ARA_EN_COK) if ni > 1 else 0.0
    obek_g = ts * olcek + (nj - 1) * ax
    obek_y = tr * olcek + (ni - 1) * ay
    return {"olcek": olcek, "sutun": sutun, "satir": satir, "hucre": hucre,
            "serbest": serbest, "sayfa2": sayfa2,
            "baslik": baslik, "ara_x": ax, "ara_y": ay,
            "obek": (max(obek_g, bg * olcek),
                     obek_y + (bb * olcek + ARA_EN_AZ if baslik else 0)),
            "gorunus_obek": (obek_g, obek_y), "baslik_olcu": (bg, bb)}


def _hucre_kutulari(plan, sol, alt):
    """Planın DOLU pencerelerinin kâğıttaki dikdörtgenleri (başlık dahil);
    _cok_pencere_ciz ile aynı hesap."""
    o = plan["olcek"]
    og, _oy = plan["gorunus_obek"]
    tg, ty = plan["obek"]
    bg, bb = plan["baslik_olcu"]
    out = []
    if plan["baslik"]:
        out.append((sol, alt + ty - bb * o, sol + bg * o, alt + ty))
    gsol = sol + (tg - og) / 2.0
    for _ad, (j, i, _c) in plan["hucre"].items():
        gx = gsol + sum(plan["sutun"][:j]) * o + j * plan["ara_x"]
        gy = alt + sum(plan["satir"][:i]) * o + i * plan["ara_y"]
        out.append((gx, gy, gx + plan["sutun"][j] * o, gy + plan["satir"][i] * o))
    return out


def tam_kagit_plani(d, kutu, kagit=VARSAYILAN_KAGIT, sablon=None, serbest_sayfa2=False,
                    sayfa2_gorunus=()):
    """ANTETİN ÜSTÜ ve SOLU birlikte: öbek kâğıdın bütün çerçevesine
    yayılabilir, yalnız DOLU pencereler (görünüşler, başlık) antete ve
    çerçeveye değmez; boş hücre antetin üstüne düşebilir. Kullanıcı:
    "büyüt şu resmi, %72-%75 olur, yeter ki antet sığsın". Eski yol öbeği
    tek dikdörtgen sayıp antetin üstündeki şeride ya da soluna sıkıştırıyor,
    kâğıdın yarısı boş kalıyordu.
    Döner: plan ("sabit_yer": (sol, alt) ile) ya da None."""
    fx0, fy0, fx1, fy1 = cerceve(kagit, sablon)
    ic = (fx0 + IC_PAY, fy0 + IC_PAY, fx1 - IC_PAY, fy1 - IC_PAY)
    ant = antet_kutusu(kagit, sablon)
    ant = (ant[0] - IC_PAY, ant[1] - IC_PAY, ant[2] + IC_PAY, ant[3] + IC_PAY)
    ilkler = [cok_pencere_plani(d, kutu, ic[2] - ic[0], ic[3] - ic[1], serbest_izin=True,
                                serbest_sayfa2=serbest_sayfa2, sayfa2_gorunus=sayfa2_gorunus,
                                baslik_serbest=bs) for bs in (False, True)]
    ilkler = [p for p in ilkler if p]
    if not ilkler:
        return None
    en_buyuk = max(p["olcek"] for p in ilkler)
    # Her ölçekte iki diziliş denenir: başlık öbeğin üstünde (önce) ya da
    # serbest pencere; büyük ölçekte sığan kazanır.
    for k, bs in ((k, bs) for k in KUCULTME for bs in (False, True)):
        o = 1.0 / k
        if o > en_buyuk + 1e-12:
            continue
        p = cok_pencere_plani(d, kutu, ic[2] - ic[0], ic[3] - ic[1], olcek_zorla=o,
                              serbest_izin=True, serbest_sayfa2=serbest_sayfa2,
                              sayfa2_gorunus=sayfa2_gorunus, baslik_serbest=bs)
        if not p:
            continue
        pg, py = p["obek"]
        en_iyi = None
        ust_yasla = bool(p.get("serbest"))      # detaylar öbeğin altına dizilir
        for fx in (0.0, 0.25, 0.5, 0.75, 1.0):
            for fy in ((1.0,) if ust_yasla else (1.0, 0.75, 0.5, 0.25, 0.0)):
                sol = ic[0] + fx * max(0.0, (ic[2] - ic[0]) - pg)
                alt = ic[1] + fy * max(0.0, (ic[3] - ic[1]) - py)
                kut = _hucre_kutulari(p, sol, alt)
                if any(k_[0] < ic[0] - 1e-6 or k_[1] < ic[1] - 1e-6 or k_[2] > ic[2] + 1e-6
                       or k_[3] > ic[3] + 1e-6 for k_ in kut):
                    continue
                if any(k_[0] < ant[2] and k_[2] > ant[0] and k_[1] < ant[3] and k_[3] > ant[1]
                       for k_ in kut):
                    continue
                sy = _serbest_yerlestir(p, kut, ic, ant)
                if sy is None:
                    continue           # detaylar bu yerleşimde kâğıda sığmıyor
                cx, cy = sol + pg / 2.0, alt + py / 2.0
                u = (cx - (fx0 + fx1) / 2.0) ** 2 + (cy - (fy0 + fy1) / 2.0) ** 2
                if en_iyi is None or u < en_iyi[0]:
                    en_iyi = (u, sol, alt, sy)
        if en_iyi:
            p["sabit_yer"] = (en_iyi[1], en_iyi[2])
            p["serbest_yer"] = en_iyi[3]
            p["yer"], p["alan"] = "tam", ic
            return p
    return None


def _ekstra_gorunusler(al_, ana):
    """2. sayfaya alınabilecek EKSTRA görünüşler. 1. sayfada kalan çekirdek:
    ana görünüş, ÖN, bir yan (SAĞ varsa SAĞ, yoksa SOL), bir üst / alt
    (ÜST varsa ÜST, yoksa ALT) ve kesit. Geri kalan (ARKA, ikinci yan,
    ikinci üst / alt) ekstradır; sırası resimdeki (soldan sağa)."""
    cekirdek = {ana, "ON"}
    for cift in (("SAG", "SOL"), ("UST", "ALT")):
        if not cekirdek & set(cift):
            for g in cift:
                if g in al_:
                    cekirdek.add(g)
                    break
    for a in al_:
        if "KESIT" in str(a).upper():
            cekirdek.add(a)
    return tuple(sorted((a for a in al_ if a not in cekirdek), key=lambda a: al_[a][0]))


def _gorunus_sirasi_yerlestir(gor, o, ic, ant):
    """2. sayfadaki GÖRÜNÜŞLER (ARKA, ikinci yan ...) TEK SIRADA, resimdeki
    hizada: resimde aynı satırdaysa kâğıtta da aynı düzeyde durur
    (kullanıcı: "arka ve sağ aynı düzeyde olmalılar"). Sıra kâğıdın sol
    üstünden başlar, görünüşler resimdeki soldan sağa sırayla ARA_EN_AZ
    aralıkla; antete değmez. Döner: {ad: (sol, alt)} ya da None (sığmadı)."""
    if not gor:
        return {}
    y0 = min(c[1] for c in gor.values())
    y1 = max(c[3] for c in gor.values())
    boy = (y1 - y0) * o
    sira = sorted(gor, key=lambda a: gor[a][0])
    gen = sum((gor[a][2] - gor[a][0]) * o for a in sira) + (len(sira) - 1) * ARA_EN_AZ
    if gen > ic[2] - ic[0] + 1e-6 or boy > ic[3] - ic[1] + 1e-6:
        return None
    out, x = {}, ic[0]
    ust = ic[3]
    for a in sira:
        c = gor[a]
        w, hh = (c[2] - c[0]) * o, (c[3] - c[1]) * o
        alt = ust - boy + (c[1] - y0) * o
        k = (x, alt, x + w, alt + hh)
        if k[0] < ant[2] and k[2] > ant[0] and k[1] < ant[3] and k[3] > ant[1]:
            return None
        out[a] = (x, alt)
        x += w + ARA_EN_AZ
    return out


def _serbest_yerlestir(plan, dolu, ic, ant, adim=4.0):
    """Serbest pencereleri (detaylar) kâğıdın BOŞ yerine koyar: çerçevenin
    içinde, antete ve dolu pencerelere (görünüşler, başlık) ARA_EN_AZ
    kadar yaklaşmadan. Büyükten küçüğe; her biri görünüşlere en yakın boş
    yere (resim dağılmasın). Döner: {ad: (sol, alt)} ya da None (sığmadı)."""
    serbest = plan.get("serbest") or {}
    if not serbest:
        return {}
    o = plan["olcek"]
    engel = [(k[0] - ARA_EN_AZ, k[1] - ARA_EN_AZ, k[2] + ARA_EN_AZ, k[3] + ARA_EN_AZ)
             for k in dolu] + [ant]
    out = {}
    # Okuma sırası: resimdeki (DXF) sırayla - yukarıdan aşağı, soldan sağa;
    # her detay görünüş öbeğinin ALTINDA, olabildiğince yukarıda ve solda
    # (kâğıda saçılmaz, öbeğin altına sıra halinde dizilir). Altta yer
    # yoksa kâğıdın başka boş yeri.
    obek_alt = min(k[1] for k in dolu) - ARA_EN_AZ if dolu else ic[3]
    for ad, b in sorted(serbest.items(), key=lambda t: (-round(t[1][3], -1), t[1][0])):
        w, hh = (b[2] - b[0]) * o, (b[3] - b[1]) * o
        en_iyi = None
        for alt_sart in (True, False):
            y = ic[1]
            while y + hh <= ic[3] + 1e-6:
                x = ic[0]
                while x + w <= ic[2] + 1e-6:
                    k = (x, y, x + w, y + hh)
                    if alt_sart and k[3] > obek_alt + 1e-6:
                        break
                    if not any(k[0] < e[2] and k[2] > e[0] and k[1] < e[3] and k[3] > e[1]
                               for e in engel):
                        u = (-round(y + hh, 0), x)      # önce yukarı, sonra sola
                        if en_iyi is None or u < en_iyi[0]:
                            en_iyi = (u, x, y)
                    x += adim
                y += adim
            if en_iyi is not None:
                break
        if en_iyi is None:
            return None
        _u, x, y = en_iyi
        out[ad] = (x, y)
        engel.append((x - ARA_EN_AZ, y - ARA_EN_AZ, x + w + ARA_EN_AZ, y + hh + ARA_EN_AZ))
    return out


def _detay_sayfalari(d, pafta_adi, kagit, detaylar, no, resim_adi, sablon, deger,
                     pi3d_antet=False):
    """DETAY SAYFALARI: 1. sayfaya sığmayan (ya da ana resmi küçültecek)
    detaylar, aynı kâğıt boyunda "PAFTA_2", "PAFTA_3" ... sayfalarına.
    Her sayfada detaylar sığan EN BÜYÜK ortak ölçekle (küçültme merdiveni;
    detay geometrisi zaten büyütülmüş olduğundan 1:1'e kadar) satır satır
    dizilir; antete değmez. Döner: açılan pencere sayısı."""
    fx0, fy0, fx1, fy1 = cerceve(kagit, sablon)
    ic = (fx0 + IC_PAY, fy0 + IC_PAY, fx1 - IC_PAY, fy1 - IC_PAY)
    ant = antet_kutusu(kagit, sablon)
    ant = (ant[0] - IC_PAY, ant[1] - IC_PAY, ant[2] + IC_PAY, ant[3] + IC_PAY)
    kalan = dict(detaylar)
    say, n = 0, 2
    while kalan and n < 12:
        # bu sayfaya sığan en büyük ölçek; sığmayanlar sonraki sayfaya
        secim, yerler, olcek = {}, {}, None
        gor2 = {a: c for a, c in kalan.items() if not _serbest_mi(a)}
        det2 = {a: c for a, c in kalan.items() if _serbest_mi(a)}
        for k in KUCULTME:
            o = 1.0 / k
            # önce görünüşler tek sırada, aynı hizada; detaylar altına
            gy = _gorunus_sirasi_yerlestir(gor2, o, ic, ant)
            if gy is None:
                continue
            dolu = [(x, y, x + (gor2[a][2] - gor2[a][0]) * o, y + (gor2[a][3] - gor2[a][1]) * o)
                    for a, (x, y) in gy.items()]
            sy = _serbest_yerlestir({"olcek": o, "serbest": det2}, dolu, ic, ant)
            if sy is not None:
                secim, yerler, olcek = dict(kalan), dict(gy, **sy), o
                break
        if not secim:
            # en büyüğü bile hiçbir ölçekte tek sayfaya sığmıyor: teker teker
            ad = max(kalan, key=lambda a: (kalan[a][2] - kalan[a][0]) * (kalan[a][3] - kalan[a][1]))
            for k in KUCULTME:
                o = 1.0 / k
                sy = _serbest_yerlestir({"olcek": o, "serbest": {ad: kalan[ad]}}, [], ic, ant)
                if sy is not None:
                    secim, yerler, olcek = {ad: kalan[ad]}, sy, o
                    break
            if not secim:
                break
        pafta = d.layouts.new(f"{pafta_adi}_{n}")
        kg, ky = KAGIT[kagit]
        pafta.page_setup(size=(round(kg), round(ky)), margins=(0, 0, 0, 0), units="mm", scale=16)
        # Detay başlığındaki büyütme (2:1) DXF'e göredir; kâğıtta ayrıca bu
        # sayfanın ölçeğiyle çarpılır - ikisi de yazılır, PDF'ten ölçü
        # alınmaz (kural 8.1)
        gorunus_var = any(not _serbest_mi(a) for a in secim)
        not_ = (f"{kagit_adi(kagit)}  sayfa {n}  ÖLÇEK {olcek_metni(olcek)}"
                + ("  (detay büyütmesi ayrıca yazılı)" if any(_serbest_mi(a) for a in secim) else "")
                + ("" if gorunus_var else "  DETAYLAR"))
        _pafta_cerceve_ciz(pafta, kagit, no, resim_adi, not_, sablon=sablon,
                           antet_degerleri=dict(deger or {}, sayfa=n,
                                                olcek=olcek_metni(olcek)),
                           pi3d_antet=pi3d_antet)
        for ad, (x, y) in yerler.items():
            c = secim[ad]
            w, hh = (c[2] - c[0]) * olcek, (c[3] - c[1]) * olcek
            pafta.add_viewport(center=(x + w / 2.0, y + hh / 2.0), size=(w, hh),
                               view_center_point=((c[0] + c[2]) / 2.0, (c[1] + c[3]) / 2.0),
                               view_height=(c[3] - c[1]))
            say += 1
            kalan.pop(ad, None)
        n += 1
    return say


def _cok_pencere_ciz(pafta, plan, sol, alt):
    """Planı kâğıda koyar. (sol, alt) öbeğin sol alt köşesi."""
    o = plan["olcek"]
    og, oy = plan["gorunus_obek"]
    tg, ty = plan["obek"]
    bg, bb = plan["baslik_olcu"]
    say = 0
    if plan["baslik"]:
        x0, y0, x1, y1 = plan["baslik"]
        pafta.add_viewport(
            center=(sol + bg * o / 2.0, alt + ty - bb * o / 2.0),
            size=(bg * o, bb * o),
            view_center_point=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
            view_height=(y1 - y0))
        say += 1
    gsol = sol + (tg - og) / 2.0          # görünüş öbeği kendi içinde ortalı
    for _ad, (j, i, c) in plan["hucre"].items():
        gx = gsol + sum(plan["sutun"][:j]) * o + j * plan["ara_x"]
        gy = alt + sum(plan["satir"][:i]) * o + i * plan["ara_y"]
        w, hh = plan["sutun"][j] * o, plan["satir"][i] * o
        pafta.add_viewport(
            center=(gx + w / 2.0, gy + hh / 2.0), size=(w, hh),
            view_center_point=((c[0] + c[2]) / 2.0, (c[1] + c[3]) / 2.0),
            view_height=(c[3] - c[1]))
        say += 1
    # serbest pencereler (detaylar): tam kâğıt planının bulduğu yerde
    for ad, (x, y) in (plan.get("serbest_yer") or {}).items():
        c = plan["serbest"][ad]
        w, hh = (c[2] - c[0]) * o, (c[3] - c[1]) * o
        pafta.add_viewport(
            center=(x + w / 2.0, y + hh / 2.0), size=(w, hh),
            view_center_point=((c[0] + c[2]) / 2.0, (c[1] + c[3]) / 2.0),
            view_height=(c[3] - c[1]))
        say += 1
    return say


YAZI_STILI = "PI3D"
YAZI_FONTU = "arial.ttf"
YAZI_AILESI = "Arial"


def yazi_stili(d):
    """Pafta yazıları için Türkçe harf gösteren TrueType stil.

    Hazır "Standard" stili txt.shx kullanır; o SHX fontunda Ğ Ş İ Ç Ö Ü
    glifi yoktur ve AutoCAD bu harfleri "?" ya da boş kutu çizer. Dosya
    UTF-8'dir, eksik olan fonttur. pf3_olcu'nun ürettiği çizimlerde bu stil
    zaten vardır; dışarıdan gelen bir DXF'e pafta eklenirse burada kurulur."""
    try:
        if YAZI_STILI in d.styles:
            st = d.styles.get(YAZI_STILI)
        else:
            st = d.styles.add(YAZI_STILI, font=YAZI_FONTU)
        st.dxf.font = YAZI_FONTU
        try:
            st.set_extended_font_data(family=YAZI_AILESI,
                                      italic=False, bold=False)
        except Exception:
            pass
        return YAZI_STILI
    except Exception:
        return "Standard"


def turkce_duzelt(d):
    """Çizimdeki eski yazıları Türkçe gösteren stile taşır.

    Sorunun kaynağı dosyanın kodlaması DEĞİLDİR: DXF R2010 UTF-8'dir ve
    "Ğ" dosyaya gerçekten C4 9E olarak yazılır. AutoCAD yazıyı STİLİN font
    dosyasıyla çizer; hazır "Standard" stili txt.shx'tir ve o SHX fontta
    yalnızca ASCII glifleri vardır - Ğ Ş İ Ç Ö Ü yerine "?" ya da boş kutu
    çıkar.

    Yeni üretilen çizimler zaten PI3D stiliyle yazılıyor. Bu işlev, daha
    önce üretilmiş dosyalar için: SHX fontlu stildeki yazıları PI3D'ye
    çevirir, böylece STP'yi baştan okumaya gerek kalmaz. Yalnız yazı
    stili değişir, metin ve konum ellenmez.

    Döndürdüğü: değiştirilen varlık sayısı."""
    stil = yazi_stili(d)
    if stil != YAZI_STILI:
        return 0

    def _shx(ad):
        """Bu yazı stili SHX (Türkçe harfsiz) mi?"""
        try:
            st = d.styles.get(ad)
        except Exception:
            return False
        f = (st.dxf.font or "").strip().lower()
        return not f.endswith(".ttf") and not f.endswith(".otf")

    n = 0
    for uzay in [d.modelspace()] + [d.layout(a) for a in d.layout_names()
                                    if a != "Model"]:
        for e in uzay:
            t = e.dxftype()
            if t in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF"):
                if _shx(e.dxf.get("style", "Standard")):
                    e.dxf.style = stil
                    n += 1
            elif t == "DIMENSION":
                # Ölçü yazısının fontu stilden değil, ölçü stilinden
                # (dimtxsty) gelir; ölçü ayrıca çizildiği anda bloğa
                # dönüştüğü için blok içindeki MTEXT de düzeltilir.
                try:
                    if _shx(e.dxf.get("dimtxsty", "Standard")):
                        e.dxf.dimtxsty = stil
                        n += 1
                except Exception:
                    pass
    for blok in d.blocks:
        for e in blok:
            if (e.dxftype() in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF")
                    and _shx(e.dxf.get("style", "Standard"))):
                e.dxf.style = stil
                n += 1
    for ds in d.dimstyles:
        try:
            if _shx(ds.dxf.get("dimtxsty", "Standard")):
                ds.dxf.dimtxsty = stil
                n += 1
        except Exception:
            pass
    return n


def _pafta_cerceve_ciz(pafta, kagit, resim_no="", resim_adi="", bilgi="",
                       sablon=None, antet_degerleri=None, pi3d_antet=False):
    """Standart pafta çerçevesini çizer.

        - kâğıdın kenarında ince dış çizgi
        - 15 mm içeride kalın çizim çerçevesi
        - ikisinin arasında bölge şeridi: rakamlar ve harfler
        - kenar ortalarında katlama/ortalama işaretleri
        - SAĞ ÜST köşede resim no ve ismi

    Sağ alt köşedeki antet alanı ÇİZİLMEZ, yalnız boş bırakılır: kendi
    çerçevesi olan bir anteti oraya yapıştırınca iki çizgi üst üste
    binerdi.

    Her biri ayrı katmanda: istemediğinizi tek tıkla silersiniz."""
    d = pafta.doc
    for ad, renk in ((KAT_CERCEVE, 7), (KAT_BOLGE, 7), (KAT_BILGI, 7)):
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

    stil = yazi_stili(pafta.doc)

    def yaz(x, y, m, h=3.5, kat=KAT_BOLGE):
        t = pafta.add_text(m, height=h, dxfattribs={"layer": kat,
                                                    "lineweight": 13,
                                                    "style": stil})
        t.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        return t

    if sablon is not None:
        # Firma anteti: çerçeve, bölge işaretleri, antet ve logo hepsi
        # firmanın kendi çiziminden gelir. Pi3D'nin sade çerçevesi
        # çizilmez - ikisi üst üste binerdi.
        sablon.ciz(pafta, (kg, ky), antet_degerleri or {}, stil=stil)
        return

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

    # --- sağ üst köşe: resim no, ismi ve paftanın ölçeği.
    # Ölçek yazılmak ZORUNDA: model uzayı 1:1 olduğu için çizimin kendi
    # başlığında "olcek 1:1" yazar, kâğıtta ise 1:5 olabilir.
    sag = fx1 - 2.0

    def sagust_yaz(metin, h, kalin, ust):
        """Yazıyı sağa dayar ve ÜST kenarı tam `ust` hizasına gelecek
        şekilde koyar; kapladığı yerin ALT kenarını döndürür.

        Hesapla değil ÖLÇEREK: "09_020_000_03" gibi bir resim no'sunda
        alt çizgiler (_) taban çizgisinin ALTINA taşar, "Ğ" ve "Ö" ise
        harf boyunun ÜSTÜNE. Taban çizgisini yazı yüksekliğinden
        çıkararak yer ayırınca alt çizgiler bir alttaki satırın harfleri
        arasına giriyordu ve resim no da çerçeve çizgisine değiyordu."""
        t = pafta.add_text(str(metin), height=h,
                           dxfattribs={"layer": KAT_BILGI,
                                       "lineweight": kalin, "style": stil})
        t.set_placement((sag, ust - h),
                        align=ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT)
        try:
            k = ezdxf.bbox.extents([t], fast=False)
            kayma = ust - k.extmax.y          # ölçülen üst kenarı hizaya al
            if abs(kayma) > 1e-6:
                t.set_placement((sag, ust - h + kayma),
                                align=ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT)
                k = ezdxf.bbox.extents([t], fast=False)
            return float(k.extmin.y)
        except Exception:
            return ust - h

    # Üstte çerçeve çizgisinin yarı kalınlığı kadar (0,5 mm çizgi) pay
    # yeter; artan yer iki satır ARASINA verilir. Resim no'da alt çizgi
    # (09_020_000_03) çok olur, alttaki satıra yakın durması okumayı
    # zorlaştırıyordu. Toplam yükseklik değişmez: başlık şeridi yine
    # çizimin kendi iç payına yazılır, ölçek düşmez.
    y = fy1 - 0.8
    if resim_no:
        y = sagust_yaz(resim_no, BASLIK_YAZI, 35, y) - 1.6
    alt = "   ".join(x for x in (str(resim_adi or ""), bilgi) if x)
    if alt:
        sagust_yaz(alt, BASLIK_ALT_YAZI, 13, y)
    if pi3d_antet:
        _pi3d_antet_ciz(pafta, kagit, antet_degerleri or {}, stil)


def pafta_kur(kaynak_dxf, cikti_dxf=None, kagit=VARSAYILAN_KAGIT, olcek=None,
              buyutme=False, pafta_adi="PAFTA", bilgi=True, cok=True,
              resim_no=None, resim_adi=None, sablon=None, antet=None,
              pi3d_antet=None):
    """1:1 DXF'in KOPYASINA standart bir pafta ekler.

    kaynak_dxf : 1:1 çizim.
    cikti_dxf  : None ise pafta ÇİZİMİN KENDİ İÇİNE eklenir (önerilen).
                 Bir yol verilirse kopyaya eklenir, kaynak dosyaya
                 dokunulmaz.

                 NEDEN YERİNDE: pafta, model uzayına bir PENCEREDEN
                 bakar. Aynı dosyanın içindeyse, model uzayına sonradan
                 ölçü eklediğinizde ya da bir şey düzelttiğinizde pafta
                 da o anda güncellenir. Kopya tutulursa iki dosya
                 zamanla birbirinden ayrılır ve hangisinin doğru olduğu
                 belli olmaz.

                 MODEL UZAYI YİNE DEĞİŞMEZ: eklenen şey yalnız kâğıt
                 uzayıdır (layout). Program her yazımda model uzayının
                 varlık sayısını önce ve sonra karşılaştırır; bir tanesi
                 bile oynarsa dosya yazılmaz.
    kagit      : "A4".."A0". Yön eki verilmezse ("A3") YATAY ve DİKEY
                 ikisi de denenir, daha büyük ölçek veren seçilir;
                 "A3-D" denirse yalnız dikey kullanılır.
    olcek      : 1.0 / 0.1 gibi. None ise sığan en büyük standart ölçek.
    cok        : görünüşleri ayrı pencerelere alıp kâğıda ortadan dışa
                 eşit aralıklarla dağıt. Resimde görünüş işareti yoksa
                 ya da bölünemiyorsa kendiliğinden tek pencereye düşer.
    resim_no   : sağ üst köşeye (antetli paftada "Drawing No." kutusuna)
                 yazılır; verilmezse dosya adı kullanılır
    resim_adi  : resim no'nun altına (antetli paftada "Part Name")
    sablon     : pf5_antet.Sablon - firma anteti. Verilirse çerçeve,
                 bölge işaretleri ve antet firmanın çiziminden gelir.
    antet      : antet kutularına yazılacak değerler
                 {"malzeme":..., "kutle":..., "cizen":..., "tarih":...}
    pi3d_antet : firma anteti yokken sağ alt kutuya Pi3D anteti (logo
                 şeridi + alanlar) çizilsin mi. None: ayar dosyasındaki
                 antet_pi3d (varsayılan açık). Firma anteti varsa çizilmez.

    Döner: {"olcek":, "olcek_metni":, "kagit":, "yer":, "olcu": (gx,gy),
            "alan": (g,y), "dosya":}
    """
    sablon = lisansli_sablon(sablon)      # DENEME'de firma anteti yok
    _KUTU_ONBELLEK.clear()           # handle'lar belgeye özel
    _IMGDEF.clear()
    if kagit not in KAGIT:
        raise PaftaYok(f"Bilinmeyen kâğıt: {kagit}")
    istenen = kagit

    hedef_adi = cikti_dxf or kaynak_dxf
    d = ezdxf.readfile(kaynak_dxf)
    # Dosya nasılsa baştan yazılacak: eski çizimlerdeki SHX fontlu yazılar
    # da bu arada Türkçe gösteren stile taşınır (bkz. turkce_duzelt).
    duzeltilen = turkce_duzelt(d)
    msp = d.modelspace()
    once = len(list(msp))

    x0, y0, x1, y1 = cizim_kutusu(kaynak_dxf)
    gx, gy = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)

    # --- hangi YÖN? Yön eki verilmediyse ikisi de denenir ve daha
    # büyük ölçek veren kazanır. Uzun bir parça dik duruyorsa yatay
    # kâğıtta 1:50'ye düşüp okunmaz oluyordu; aynı parça dikey kâğıtta
    # 1:20 çıkıyor. Eşitlikte yatay kalır: adaylar sırası öyle.
    # Kâğıt HER ZAMAN YATAY (kullanıcı: "resimler yatay olacak, nereden
    # çıktı portre"): daha büyük ölçek veriyor diye dikeye geçilmez.
    # Dikey yalnız açıkça istenirse ("A3-D").
    adaylar = (((kagit_boyu(istenen),) if not dikey_mi(istenen) else (istenen,))
               if sablon is None else (kagit_boyu(istenen),))

    # --- görünüşleri kâğıda eşit dağıtan plan (varsa)
    plan, kagit = None, adaylar[0]
    if cok and olcek is None:
        for kg_ad in adaylar:
            yon_en = None
            for ad, a in cizim_alanlari(kg_ad, sablon).items():
                p = cok_pencere_plani(d, (x0, y0, x1, y1),
                                      a[2] - a[0], a[3] - a[1])
                if p and (yon_en is None or p["olcek"] > yon_en["olcek"]):
                    p["yer"], p["alan"] = ad, a
                    yon_en = p
            tp = tam_kagit_plani(d, (x0, y0, x1, y1), kg_ad, sablon)
            if tp and (yon_en is None or tp["olcek"] > yon_en["olcek"] + 1e-12):
                yon_en = tp
            # ANA RESİM BÜYÜK KALIR (kullanıcı: "ana resmi büyüt, karınca duası
            # olmasın, gerekirse birden fazla sayfa yap"): detaylar 1. sayfada
            # ölçeği düşürüyorsa 2. SAYFAYA (DETAYLAR) gider.
            if _serbest_kutular(d, gorunus_alanlari(d)):
                tp2 = tam_kagit_plani(d, (x0, y0, x1, y1), kg_ad, sablon, serbest_sayfa2=True)
                if tp2 and (yon_en is None or tp2["olcek"] > yon_en["olcek"] + 1e-12):
                    yon_en = tp2
            # ANA GÖRÜNÜŞ TEK BAŞINA: yan görünüşler (ve detaylar) 2. sayfaya
            # alınınca ana görünüş belirgin (SAYFA_AYIR_ORAN) büyüyorsa öyle
            # yapılır - antet alanı ve yan görünüş ana resmi küçültmesin.
            # Yalnız tek sayfada yazı KÜÇÜK kalıyorsa (SAYFA_AYIR_YAZI_MM):
            # yazı okunuyorsa görünüşler bir arada kalır (izdüşüm bütünlüğü).
            # Başlık (BILGI) her zaman 1. sayfada.
            al_ = {a: b for a, b in gorunus_alanlari(d).items()
                   if a not in (BASLIK_AD, BILGI_AD) and not _serbest_mi(a)}
            yz_tek = (en_kucuk_yazi(kaynak_dxf) * yon_en["olcek"]) if yon_en else 0.0
            # Yalnız EKSTRA görünüşler gider (kullanıcı: "böyle dağınık çizim
            # yapılmaz: ön, sağ ya da sol, alt yaparsın; ekstra arka ve
            # detaylar yaparsın"): ÖN + bir yan + bir üst/alt 1. sayfada
            # izdüşüm düzeninde kalır; ARKA, ikinci yan, ikinci üst/alt
            # 2. sayfaya alınabilir.
            if len(al_) >= 2 and (yon_en is None or yz_tek < SAYFA_AYIR_YAZI_MM):
                ana = max(al_, key=lambda a: (al_[a][2] - al_[a][0]) * (al_[a][3] - al_[a][1]))
                digerleri = _ekstra_gorunusler(al_, ana)
                tp3 = (tam_kagit_plani(d, (x0, y0, x1, y1), kg_ad, sablon, serbest_sayfa2=True,
                                       sayfa2_gorunus=digerleri) if digerleri else None)
                if tp3 and (yon_en is None
                            or tp3["olcek"] > yon_en["olcek"] * SAYFA_AYIR_ORAN + 1e-12):
                    yon_en = tp3
            if yon_en and (plan is None or yon_en["olcek"] > plan["olcek"] + 1e-12):
                plan, kagit = yon_en, kg_ad

    # --- ölçek ve hangi boşluğa oturacağı
    if olcek is None:
        # Dağıtılmış plan tek pencereden daha büyük ölçek vermiyorsa
        # kullanılmaz: amaç resmi büyütmek.
        tek = yerlesim(gx, gy, istenen, buyutme, sablon)
        if plan and tek and tek["olcek"] > plan["olcek"]:
            plan = None
        if plan:
            olcek = plan["olcek"]
            yer = {"olcek": olcek, "yer": plan["yer"], "alan": plan["alan"]}
        else:
            yer = tek
            if not yer:
                raise PaftaYok(
                    f"{os.path.basename(kaynak_dxf)}: {XL.tr(gx, 0, sade=False)}x{XL.tr(gy, 0, sade=False)} mm "
                    f"çizim {kagit_boyu(istenen)} paftaya (yatay ya da "
                    f"dikey) standart bir ölçekle sığmıyor. "
                    "Daha büyük kâğıt seçin.")
            kagit = yer.get("kagit", adaylar[0])
            olcek = yer["olcek"]
    else:
        yer = None
        for kg_ad in adaylar:
            for ad, a in cizim_alanlari(kg_ad, sablon).items():
                if (gx * olcek <= a[2] - a[0] + 1e-6
                        and gy * olcek <= a[3] - a[1] + 1e-6):
                    yer, kagit = {"olcek": olcek, "yer": ad, "alan": a}, kg_ad
                    break
            if yer:
                break
        if not yer:
            # Ölçeği kullanıcı verdiyse de kâğıda sığmayan pafta yazılmaz:
            # taşan çizim, olmayan çizimden beterdir.
            raise PaftaYok(
                f"{os.path.basename(kaynak_dxf)}: {XL.tr(gx, 0, sade=False)}x{XL.tr(gy, 0, sade=False)} mm çizim "
                f"{olcek_metni(olcek)} ölçekte "
                f"{XL.tr(gx * olcek, 0, sade=False)}x{XL.tr(gy * olcek, 0, sade=False)} mm yer ister; {kagit} "
                f"paftada en büyük boşluk {_en_buyuk_alan_metni(kagit, sablon)}. "
                "Ölçeği küçültün ya da kâğıdı büyütün.")
    alan = yer["alan"]
    ag, ay = alan[2] - alan[0], alan[3] - alan[1]
    # Pencere tam çizim kadar olsun ve MÜMKÜN OLDUĞUNCA KÂĞIDIN
    # ORTASINDA dursun.
    #
    # Önce tam kâğıt ortası denenir; antet kutusuna değmiyorsa iş
    # bitmiştir. Değiyorsa, çizimin sığdığı HER boşluk için kâğıt
    # ortasına en yakın nokta bulunur ve bunların en yakını seçilir -
    # yalnız ölçeği veren boşluğa bakmak yetmez, ölçek aynıysa öbür
    # boşluk daha ortada olabilir. Böylece kısa parçalar kâğıdın bir
    # kenarına sıkışmaz, uzun olanlar da anteti ezmez.
    if plan:
        pg, py = plan["obek"]
    else:
        pg, py = max(gx * olcek, 1e-6), max(gy * olcek, 1e-6)
    pg, py = max(pg, 1e-6), max(py, 1e-6)
    fx0, fy0, fx1, fy1 = cerceve(kagit, sablon)
    ox, oy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
    kutu = antet_kutusu(kagit, sablon)

    def _uygun(cx, cy):
        """Bu merkezde duran çizim çerçevenin içinde, kenarlardan ve
        antet kutusundan IC_PAY kadar uzakta mı?"""
        r = (cx - pg / 2, cy - py / 2, cx + pg / 2, cy + py / 2)
        return (r[0] >= fx0 + IC_PAY - 1e-6 and r[1] >= fy0 + IC_PAY - 1e-6
                and r[2] <= fx1 - IC_PAY + 1e-6 and r[3] <= fy1 - IC_PAY + 1e-6
                and not (r[0] < kutu[2] + IC_PAY - 1e-6
                         and r[2] > kutu[0] - IC_PAY + 1e-6
                         and r[1] < kutu[3] + IC_PAY - 1e-6
                         and r[3] > kutu[1] - IC_PAY + 1e-6))

    def _kis(v, alt, ust):
        return alt if v < alt else (ust if v > ust else v)

    if plan and plan.get("sabit_yer"):
        mx, my = plan["sabit_yer"][0] + pg / 2.0, plan["sabit_yer"][1] + py / 2.0
    elif _uygun(ox, oy):
        mx, my = ox, oy
    else:
        aday = []
        for a in cizim_alanlari(kagit, sablon).values():
            if pg > a[2] - a[0] + 1e-6 or py > a[3] - a[1] + 1e-6:
                continue
            cx = _kis(ox, a[0] + pg / 2, a[2] - pg / 2)
            cy = _kis(oy, a[1] + py / 2, a[3] - py / 2)
            if _uygun(cx, cy):
                aday.append(((cx - ox) ** 2 + (cy - oy) ** 2, cx, cy))
        if not aday:                     # olmamalı; olduysa pafta yazılmaz
            raise PaftaYok(
                f"{os.path.basename(kaynak_dxf)}: {olcek_metni(olcek)} "
                f"ölçekteki çizim {kagit} paftada antet alanını ezmeden "
                "yerleştirilemedi.")
        _, mx, my = min(aday)

    # --- paftayı kur
    try:
        d.layouts.delete(pafta_adi)
    except Exception:
        pass
    # Aynı resme ikinci kez pafta eklenebilmeli: kullanıcı bir ölçü
    # ekleyip "tekrar paftaya al" diyebilir. Eski pafta sekmesi silinir,
    # yenisi kurulur; MODEL UZAYINA DOKUNULMAZ, çizim 1:1 kalır.
    if pafta_adi in d.layout_names():
        try:
            d.layouts.delete(pafta_adi)
        except Exception:
            pass
    pafta = d.layouts.new(pafta_adi)
    kg, ky = KAGIT[kagit]              # seçilen yönün ölçüleri
    pafta.page_setup(size=(round(kg), round(ky)), margins=(0, 0, 0, 0),
                     units="mm", scale=16)   # 16 = 1 kâğıt birimi : 1 mm

    not_ = ""
    if bilgi:
        not_ = (f"{kagit_adi(kagit)}  ÖLÇEK {olcek_metni(olcek)}"
                + ("  (model 1:1)" if abs(olcek - 1) > 1e-9 else ""))
    no = resim_no if resim_no is not None else os.path.splitext(
        os.path.basename(kaynak_dxf))[0]
    # Sağ üst köşedeki yazılar çerçeveden taşmasın: kalan genişliğe kaç
    # harf sığıyorsa o kadar.
    kg2 = (kg - 2 * KENAR) - 4.0
    no = str(no)[:max(4, int(kg2 / (HARF_ORAN * BASLIK_YAZI)))]
    if resim_adi:
        sig = max(4, int(kg2 / (HARF_ORAN * BASLIK_ALT_YAZI)) - len(not_) - 3)
        resim_adi = str(resim_adi)[:sig]
    # Antet kutularına ne yazılacak (firma anteti ya da Pi3D anteti).
    # Ölçek ve dosya adı burada bilinir; malzeme, kütle, çizen ve tarih
    # çağırandan gelir.
    deger = dict(antet or {})
    deger.setdefault("olcek", olcek_metni(olcek))
    deger.setdefault("resim_no", no)
    deger.setdefault("parca_adi", resim_adi or "")
    deger.setdefault("dosya", os.path.basename(hedef_adi))
    deger.setdefault("kagit", kagit_adi(kagit))
    deger["sayfa"] = 1
    deger["_klasor"] = os.path.dirname(os.path.abspath(hedef_adi))
    pi3d_antet = sablon is None and pi3d_antet_acik(pi3d_antet)
    _pafta_cerceve_ciz(pafta, kagit, no, resim_adi or "", not_,
                       sablon=sablon, antet_degerleri=deger, pi3d_antet=pi3d_antet)

    # --- pencere(ler): 1:1 çizime buradan bakılır
    sayfa = 1
    if plan:
        pencere = _cok_pencere_ciz(pafta, plan, mx - pg / 2.0, my - py / 2.0)
        if plan.get("sayfa2"):
            for ad_ in list(d.layout_names()):
                if ad_.startswith(pafta_adi + "_") and ad_[len(pafta_adi) + 1:].isdigit():
                    try:
                        d.layouts.delete(ad_)
                    except Exception:
                        pass
            pencere += _detay_sayfalari(d, pafta_adi, kagit, plan["sayfa2"], no,
                                        resim_adi or "", sablon, deger, pi3d_antet)
            sayfa = 1 + sum(1 for ad_ in d.layout_names()
                            if ad_.startswith(pafta_adi + "_") and ad_[len(pafta_adi) + 1:].isdigit())
    else:
        pafta.add_viewport(
            center=(mx, my), size=(pg, py),
            view_center_point=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
            view_height=gy)
        pencere = 1

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
    hedef = hedef_adi
    os.makedirs(os.path.dirname(os.path.abspath(hedef)) or ".", exist_ok=True)
    if cikti_dxf:
        d.saveas(cikti_dxf)
    else:
        # Yerine yazarken ÖNCE geçici dosyaya: yazma yarıda kalırsa
        # (disk dolu, program kapandı) resim bozulmasın.
        gec = hedef + ".yeni"
        d.saveas(gec)
        os.replace(gec, hedef)
    yz = en_kucuk_yazi(kaynak_dxf) * olcek
    return {"olcek": olcek, "olcek_metni": olcek_metni(olcek), "kagit": kagit,
            "yer": yer["yer"], "olcu": (gx, gy), "alan": (ag, ay),
            "dosya": hedef, "yerinde": cikti_dxf is None,
            "yazi_duzeltildi": duzeltilen,
            "yazi_mm": round(yz, 2),
            "yazi_kucuk": 0 < yz < EN_AZ_YAZI_MM,
            "pencere": pencere, "dagitildi": bool(plan), "sayfa": sayfa,
            "obek": (round(pg, 1), round(py, 1))}


def _en_buyuk_alan_metni(kagit, sablon=None):
    a = cizim_alanlari(kagit, sablon)
    return "  /  ".join(f"{XL.tr((v[2] - v[0]), 0, sade=False)}x{XL.tr((v[3] - v[1]), 0, sade=False)} mm"
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


def mevcut_pafta(dxf_yolu, pafta_adi="PAFTA"):
    """Resmin içinde daha önce kurulmuş pafta varsa kâğıdı ("A3",
    "A3D" ...), yoksa None. Önceki oturumda paftalanmış resmin PDF'i,
    paftayı yeniden kurmadan basılabilsin diye."""
    try:
        d = ezdxf.readfile(dxf_yolu)
        if pafta_adi not in d.layout_names():
            return None
        lay = d.layout(pafta_adi)
        alt, ust = lay.get_paper_limits()
        g, y = float(ust.x - alt.x), float(ust.y - alt.y)
        if g < 1.0 or y < 1.0:
            g, y = float(lay.dxf.paper_width), float(lay.dxf.paper_height)
    except Exception:
        return None
    for k, (kg, ky) in KAGIT.items():
        if abs(kg - g) < 1.0 and abs(ky - y) < 1.0:
            return k
    return None


def bas(dxf_yolu, cikti, pafta_adi="PAFTA", siyah=True, dpi=300):
    """Paftayı PDF ya da PNG olarak basar.

    Bu işlev KENDİLİĞİNDEN ÇAĞRILMAZ. Kullanıcı "BAS" dediğinde çalışır.
    Kâğıda birebir oturur: A3 pafta, 420x297 mm PDF olur; yazıcıda
    'sayfaya sığdır' demeye gerek kalmaz, %100 basılır."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # matplotlib arka ucu ADIYLA, çalışma anında yükler: .pdf görünce
    # backend_pdf'i import eder. PyInstaller bunu göremediği için
    # exe'de "No module named 'matplotlib.backends.backend_pdf'" diye
    # patlıyordu. Burada ÖNCEDEN denenir: hata anlaşılır olsun.
    if str(cikti).lower().endswith(".pdf"):
        try:
            import matplotlib.backends.backend_pdf     # noqa: F401
        except ImportError:
            raise PaftaYok(
                "matplotlib'in PDF arka ucu (backend_pdf) bu pakette yok, "
                "PDF üretilemiyor. Kaynaktan çalıştırıyorsanız "
                "'pip install -U matplotlib' deyin; exe kullanıyorsanız "
                "exe eski demektir, EXE_YAP.bat ile yeniden derleyin. "
                "PNG basımı bundan etkilenmez.")
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import (Configuration, ColorPolicy,
                                             BackgroundPolicy)

    d = ezdxf.readfile(dxf_yolu)
    try:
        d.layout(pafta_adi)
    except Exception:
        raise PaftaYok(f"{os.path.basename(dxf_yolu)} içinde "
                       f"'{pafta_adi}' paftası yok.")
    # Sayfalar: PAFTA, PAFTA_2, PAFTA_3 ... (detay sayfaları) tek PDF'te
    sayfalar = [pafta_adi] + sorted(
        (a for a in d.layout_names()
         if a.startswith(pafta_adi + "_") and a[len(pafta_adi) + 1:].isdigit()),
        key=lambda a: int(a[len(pafta_adi) + 1:]))
    if not str(cikti).lower().endswith(".pdf"):
        sayfalar = sayfalar[:1]           # PNG: yalnız 1. sayfa
    ayar = Configuration(
        color_policy=ColorPolicy.BLACK if siyah else ColorPolicy.COLOR,
        background_policy=BackgroundPolicy.WHITE,
        lineweight_scaling=1.0,
    )
    os.makedirs(os.path.dirname(os.path.abspath(cikti)) or ".", exist_ok=True)

    def _cizim(ad):
        kg, ky = pafta_olcusu(dxf_yolu, ad)
        if kg < 1 or ky < 1:
            kg, ky = KAGIT[VARSAYILAN_KAGIT]
        fig = plt.figure(figsize=(kg / 25.4, ky / 25.4), dpi=dpi)
        eksen = fig.add_axes([0, 0, 1, 1])
        eksen.set_axis_off()
        Frontend(RenderContext(d), MatplotlibBackend(eksen), config=ayar
                 ).draw_layout(d.layout(ad), finalize=False)
        eksen.set_xlim(0, kg)
        eksen.set_ylim(0, ky)
        eksen.set_aspect("equal")
        return fig
    if len(sayfalar) == 1:
        fig = _cizim(sayfalar[0])
        fig.savefig(cikti, dpi=dpi, facecolor="white")
        plt.close(fig)
        return cikti
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(cikti) as pdf:
        for ad in sayfalar:
            fig = _cizim(ad)
            pdf.savefig(fig, dpi=dpi, facecolor="white")
            plt.close(fig)
    return cikti


# --------------------------------------------------------------- toplu
def kagit_plani(dosyalar, tercih=VARSAYILAN_KAGIT, sablon=None, dur=None):
    """Hangi çizim seçilen kâğıda hangi ölçekte oturur.

    Hiçbir dosya yazmaz, sadece bakar. Kullanıcı "hangisi 1:1 çıkıyor,
    hangisi küçülecek" diye görmek ister."""
    birebir, olcekli, sigmayan, hata = [], [], [], []
    for y in dosyalar:
        if dur and dur():              # kullanıcı İPTAL dedi
            break
        try:
            x0, y0, x1, y1 = cizim_kutusu(y)
            gx, gy = x1 - x0, y1 - y0
        except Exception as e:
            hata.append((y, str(e)))
            continue
        # Yön ekli bir tercih gelmediyse iki yön de denenir; seçilen yön
        # kayda yazılır ki kullanıcı listede "A3 dikey" görsün.
        ye = yerlesim(gx, gy, tercih, sablon=sablon)
        kayit = {"dosya": y, "olcu": (gx, gy),
                 "kagit": (ye or {}).get("kagit", tercih),
                 "olcek": ye["olcek"] if ye else None,
                 "yer": ye["yer"] if ye else None}
        if not ye:
            kayit["birebir_kagit"] = kagit_sec(gx, gy, sablon=sablon)
            kayit["secenek"] = [(yerlesim(gx, gy, k, sablon=sablon)["kagit"],
                                 yerlesim(gx, gy, k, sablon=sablon)["olcek"])
                                for k in KAGIT_BOY
                                if yerlesim(gx, gy, k, sablon=sablon)]
            sigmayan.append(kayit)
        elif abs(ye["olcek"] - 1.0) < 1e-9:
            birebir.append(kayit)
        else:
            kayit["birebir_kagit"] = kagit_sec(gx, gy, sablon=sablon)
            kayit["daha_iyi"] = next(
                ((yerlesim(gx, gy, k, sablon=sablon)["kagit"],
                  yerlesim(gx, gy, k, sablon=sablon)["olcek"])
                 for k in KAGIT_BOY
                 if KAGIT[k][0] > KAGIT[kagit_boyu(tercih)][0]
                 and yerlesim(gx, gy, k, sablon=sablon)
                 and yerlesim(gx, gy, k, sablon=sablon)["olcek"] > ye["olcek"]),
                None)
            olcekli.append(kayit)
        try:
            kayit["yazi_mm"] = round(en_kucuk_yazi(y) * (kayit["olcek"] or 1), 2)
        except Exception:
            kayit["yazi_mm"] = 0.0
    return {"birebir": birebir, "olcekli": olcekli, "sigmayan": sigmayan,
            "hata": hata, "kagit": tercih}


def toplu_pafta(isler, cikti_klasor=None, resim_no=None, resim_adi=None,
                sablon=None, antet=None):
    """isler: [{"dosya":..., "kagit":"A3", "olcek": None}, ...]

    cikti_klasor None ise pafta ÇİZİMLERİN KENDİ İÇİNE eklenir; bir
    klasör verilirse kopyalarına eklenir."""
    sablon = lisansli_sablon(sablon)
    if cikti_klasor:
        os.makedirs(cikti_klasor, exist_ok=True)
    yapilan, hata = [], []
    for it in isler:
        y = it["dosya"]
        ad = os.path.splitext(os.path.basename(y))[0]
        kagit = it.get("kagit", VARSAYILAN_KAGIT)
        try:
            cik = (os.path.join(cikti_klasor,
                                f"{ad}_{kagit.replace('-', '')}.dxf")
                   if cikti_klasor else None)
            r = pafta_kur(y, cik, kagit, olcek=it.get("olcek"),
                          resim_no=it.get("resim_no", resim_no),
                          resim_adi=it.get("resim_adi", resim_adi),
                          sablon=sablon,
                          antet=dict(antet or {}, **it.get("antet", {})))
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
        description="Pi3D – 1:1 DXF'lere standart A3 pafta ekler. Pafta "
                    "resmin KENDİ dosyasına yazılır (Model sekmesi 1:1 "
                    "kalır); PDF istenirse PDF klasörüne ..._A3.pdf olarak "
                    "basılır.")
    a.add_argument("dxf", nargs="+", help="1:1 DXF dosyaları (joker olur)")
    a.add_argument("--kagit", default=VARSAYILAN_KAGIT,
                   choices=list(KAGIT_SIRA),
                   help="yön verilmezse (A3) yatay ve dikey denenir, "
                        "daha büyük ölçek veren seçilir; A3-D yalnız dikey")
    a.add_argument("--olcek", type=float, default=None,
                   help="1 / 0.1 gibi; verilmezse sığan en büyüğü")
    a.add_argument("--kopya", metavar="KLASOR", default=None,
                   help="paftayı dosyanın içine değil, bu klasördeki "
                        "kopyaya ekle (önerilmez: kopya ile asıl resim "
                        "zamanla ayrışır)")
    a.add_argument("--pdf-klasor", default="PDF",
                   help="--bas verildiğinde PDF'lerin yazılacağı klasör")
    a.add_argument("--plan", action="store_true",
                   help="hiçbir şey yazma, hangi ölçekte oturduğunu söyle")
    a.add_argument("--bas", action="store_true", help="PDF de üret")
    a.add_argument("--no", help="sağ üst köşeye yazılacak resim no "
                                "(verilmezse dosya adı)")
    a.add_argument("--ad", help="resim no'nun altına yazılacak isim")
    n = a.parse_args()

    dosya = []
    for d in n.dxf:
        dosya += sorted(_glob.glob(d)) if any(c in d for c in "*?[") else [d]
    if not dosya:
        a.error("DXF bulunamadı.")

    p = kagit_plani(dosya, n.kagit)
    for s in p["birebir"]:
        print(f"  {n.kagit}  1:1   {os.path.basename(s['dosya'])}"
              f"   ({XL.tr(s['olcu'][0], 0, sade=False)}x{XL.tr(s['olcu'][1], 0, sade=False)})")
    for s in p["olcekli"]:
        di = s.get("daha_iyi")
        ek = f"   [{di[0]} olsa {olcek_metni(di[1])}]" if di else ""
        if 0 < s.get("yazi_mm", 0) < EN_AZ_YAZI_MM:
            ek += f"   [DIKKAT yazilar kagitta {XL.tr(s['yazi_mm'], 1, sade=False)} mm kaliyor]"
        print(f"  {n.kagit}  {olcek_metni(s['olcek'])}   "
              f"{os.path.basename(s['dosya'])}"
              f"   ({XL.tr(s['olcu'][0], 0, sade=False)}x{XL.tr(s['olcu'][1], 0, sade=False)}){ek}")
    for s in p["sigmayan"]:
        sec = ", ".join(f"{k} {olcek_metni(o)}" for k, o in s["secenek"][:4])
        print(f"  SIĞMADI  {os.path.basename(s['dosya'])}"
              f"   ({XL.tr(s['olcu'][0], 0, sade=False)}x{XL.tr(s['olcu'][1], 0, sade=False)})  ->  "
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
    sb = ayarli_firma_anteti()
    if sb is not None:
        print(f"  firma anteti: {sb.bilgi.get('ad', 'antet')}")
    r = toplu_pafta(isler, n.kopya, n.no, n.ad, sablon=sb)
    print()
    if n.bas:
        os.makedirs(n.pdf_klasor, exist_ok=True)
    for it in r["yapilan"]:
        nere = "yazıldı " if n.kopya else "içine eklendi"
        print(f"  {nere}  {it['kagit']} {it['olcek_metni']}  "
              f"{os.path.basename(it['dosya'])}")
        if n.bas:
            ad = os.path.splitext(os.path.basename(it["dosya"]))[0]
            ek = str(it["kagit"]).replace("-", "")   # A3 yatay -> A3, dikey -> A3D
            print("           ",
                  bas(it["dosya"],
                      os.path.join(n.pdf_klasor, f"{ad}_{ek}.pdf")))
    for y, e in r["hata"]:
        print(f"  HATA  {os.path.basename(y)}: {e}")


if __name__ == "__main__":
    _cli()
