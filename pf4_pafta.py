# -*- coding: utf-8 -*-
"""
Pi3D – ANTET ve PAFTA

1:1 çizilmiş DXF'leri firma antetiyle, istenen kâğıt boyutunda paftaya
yerleştirir. Ve bunu yaparken:

    MODEL UZAYINA ASLA DOKUNULMAZ.

Bu bir kural, tercih değil. 1:1 çizim gerçeğin kendisidir; ölçüsü,
konumu, hiçbir şeyi değişmez. Pafta, o çizime bir PENCEREDEN bakar
(paper space viewport). Ölçek pencerenin özelliğidir, geometrinin değil.
Dolayısıyla "1:10 bastım" demek çizimi küçülttüm demek değildir; aynı
1:1 çizime uzaktan bakmak demektir. AutoCAD'de model sekmesine
geçtiğinizde her şeyi eskisi gibi, birebir ölçüsünde bulursunuz.

ANTET NASIL HAZIRLANIR
    Anteti kendi CAD'inizde çizip DXF olarak kaydedin. Değerin geleceği
    yerlere ALAN ADINI yazın:

        <<KOD>>      <<AD>>       <<MALZEME>>   <<CIZEN>>
        <<TARIH>>    <<OLCEK>>    <<PAFTA>>     ...

    Program bu yazıları bulup gerçek değerle değiştirir. Hangi alanı
    nereye koyacağınıza siz karar verirsiniz; istemediğiniz alanı hiç
    koymazsınız. Tam liste aşağıda ALANLAR'da.

    Çizimin yerleşeceği boşluğu da siz belirlersiniz: anteti çizerken
    CIZIM_ALANI adlı bir katmana bir dikdörtgen koyun, çizim oraya
    oturur. Koymazsanız program kâğıdın kenarından pay bırakıp kalanı
    kullanır.
"""
from __future__ import annotations
import datetime
import os
import re

import ezdxf
from ezdxf.addons import Importer

# ---------------------------------------------------------------- kâğıt
# Yatay (landscape) mm ölçüleri. Dikey isterseniz KAGIT_DIK kullanın.
KAGIT = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}
KAGIT_SIRA = ("A4", "A3", "A2", "A1", "A0")

# Teknik resimde kullanılan standart ölçekler (ISO 5455).
# Küçültme ve büyütme ayrı ayrı; arada olmayan bir ölçek seçilmez.
KUCULTME = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
BUYUTME = (2, 5, 10)

KENAR_PAYI = 10.0          # antet yoksa kâğıdın kenarından bırakılan pay
CIZIM_KATMAN = "CIZIM_ALANI"   # antette çizim alanını gösteren dikdörtgen

# Antette kullanılabilecek alanlar. Program bunları doldurur; antette
# olmayan alan atlanır, olmayan değer boş bırakılır.
ALANLAR = {
    "FIRMA": "firma adı (ayarlardan)",
    "PROJE": "proje / iş adı",
    "AD": "parçanın adı",
    "KOD": "parça kodu",
    "POZ": "poz numarası",
    "ADET": "montajdaki adedi",
    "MALZEME": "malzeme adı",
    "KALINLIK": "sac kalınlığı (varsa)",
    "KUTLE": "parça kütlesi kg",
    "OLCU": "boy x en x kalınlık",
    "OLCEK": "pafta ölçeği, program yazar",
    "PAFTA": "kâğıt boyutu, program yazar",
    "CIZEN": "çizen kişi",
    "KONTROL": "kontrol eden",
    "ONAY": "onaylayan",
    "TARIH": "tarih",
    "REVIZYON": "revizyon",
    "ACIKLAMA": "serbest açıklama",
    "TOLERANS": "genel tolerans notu",
    "YUZEY": "yüzey işlem notu",
    "DOSYA": "kaynak dosya adı",
    "BIRIM": "birim (mm)",
    "SAYFA": "sayfa no / toplam",
}
YER_TUTUCU = re.compile(r"<<\s*([A-ZÇĞİÖŞÜ0-9_]+)\s*>>")


class PaftaYok(Exception):
    """Pafta kurulamadı; mesaj kullanıcıya gösterilir."""


# ------------------------------------------------------------ yardımcı
def _varlik_kutusu(uzay):
    """Bir uzaydaki çizginin sınırları (x0, y0, x1, y1) ya da None."""
    xs, ys = [], []
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
                p = e.dxf.insert
                xs.append(p.x); ys.append(p.y)
            elif t == "POINT":
                xs.append(e.dxf.location.x); ys.append(e.dxf.location.y)
        except Exception:
            continue
    if not xs:
        return None
    return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))


def cizim_kutusu(yol):
    """1:1 DXF'in model uzayındaki sınırları. Ölçü ve yazılar dahil
    değildir: pafta ölçeğini GEOMETRİ belirler, yazı boyu değil."""
    d = ezdxf.readfile(yol)
    say = [e for e in d.modelspace()
           if e.dxftype() in ("LWPOLYLINE", "LINE", "CIRCLE", "ARC")]
    k = _varlik_kutusu(say) or _varlik_kutusu(d.modelspace())
    if not k:
        raise PaftaYok(f"{os.path.basename(yol)}: çizimde varlık yok.")
    return k


def olcek_metni(o):
    """0.1 -> '1:10',  2 -> '2:1',  1 -> '1:1'"""
    if abs(o - 1.0) < 1e-9:
        return "1:1"
    if o < 1:
        return f"1:{round(1 / o)}"
    return f"{round(o)}:1"


def sigan_olcek(gx, gy, alan_g, alan_y, buyutme=False):
    """Çizimi alana sığdıran EN BÜYÜK standart ölçek. Sığmıyorsa None.

    Önce 1:1 denenir - teknik resimde tercih her zaman birebirdir.
    Sonra sırayla küçültülür. Büyütme İSTENMEDİKÇE yapılmaz: kimse
    küçük bir parçanın kendiliğinden 2:1 çizilmesini beklemez."""
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


def kagit_sec(gx, gy, adaylar=("A4", "A3"), pay=KENAR_PAYI, antet_alani=None):
    """Çizimi 1:1 alan EN KÜÇÜK kâğıt. Hiçbirine sığmazsa None.

    antet_alani: {kağıt: (genişlik, yükseklik)} - antetin bıraktığı boşluk.
    Verilmezse kâğıttan kenar payı düşülür."""
    for k in adaylar:
        if k not in KAGIT:
            continue
        if antet_alani and k in antet_alani:
            ag, ay = antet_alani[k]
        else:
            ag, ay = KAGIT[k][0] - 2 * pay, KAGIT[k][1] - 2 * pay
        if gx <= ag and gy <= ay:
            return k
    return None


# -------------------------------------------------------------- antet
def antet_incele(antet_yolu):
    """Antet DXF'ini okur, ne içerdiğini söyler.

    Döner: {"alanlar": [...], "bilinmeyen": [...], "cizim_alani": (g,y) ya da
            None, "kutu": (x0,y0,x1,y1), "kagit": tahmin}
    Kullanıcı anteti seçtiğinde ona ne bulduğumuzu göstermek için."""
    if not antet_yolu or not os.path.isfile(antet_yolu):
        raise PaftaYok(f"Antet dosyası yok: {antet_yolu}")
    try:
        d = ezdxf.readfile(antet_yolu)
    except Exception as e:
        raise PaftaYok(f"Antet DXF okunamadı: {e}")

    bulunan = []
    for e in d.modelspace():
        if e.dxftype() in ("TEXT", "MTEXT", "ATTDEF"):
            m = e.text if e.dxftype() == "MTEXT" else e.dxf.text
            for ad in YER_TUTUCU.findall(m or ""):
                if ad not in bulunan:
                    bulunan.append(ad)

    kutu = _varlik_kutusu(d.modelspace())
    if kutu is None:
        raise PaftaYok("Antet DXF'i boş.")
    ag, ay = kutu[2] - kutu[0], kutu[3] - kutu[1]

    kagit = antet_kagidi(kutu)

    ca = None
    for e in d.modelspace():
        if e.dxf.layer.upper() != CIZIM_KATMAN:
            continue
        k = _varlik_kutusu([e])
        if k:
            ca = k
            break

    return {
        "alanlar": [a for a in bulunan if a in ALANLAR],
        "bilinmeyen": [a for a in bulunan if a not in ALANLAR],
        "kutu": kutu,
        "olcu": (ag, ay),
        "kagit": kagit,
        "cizim_alani": ca,
    }


def antet_kagidi(kutu):
    """Antetin hangi kâğıda çizildiği.

    Antet kâğıt koordinatlarında çizilir: sol alt köşe (0,0), sağ üst
    köşe kâğıdın boyu. Çerçeve kenardan pay bırakacağı için varlıkların
    sınırı kâğıttan biraz küçüktür; o yüzden 'sığdığı en küçük kâğıt'
    aranır. Hiçbirine sığmazsa (çok büyük ya da 0,0'dan uzakta çizilmiş)
    None döner, o zaman varlık sınırı kâğıt sayılır."""
    x0, y0, x1, y1 = kutu
    if x0 < -1.0 or y0 < -1.0:
        return None
    for k in KAGIT_SIRA:
        g, y = KAGIT[k]
        if x1 <= g + 1.0 and y1 <= y + 1.0:
            return k
    return None


def _antet_olcekle(kutu, hedef):
    """Anteti hedef kâğıda oturtan (katsayı, dx, dy).

    Antet A3'e çizilmişse ve A1'e basılacaksa A1 boyuna büyütülür;
    böylece tek antetle bütün kâğıtlar kullanılabilir. Ölçek kâğıttan
    kâğıda oranla hesaplanır (A3->A1 = 2 kat), antetin çizgilerinin
    nerede bittiğine göre değil - yoksa kenar payı yutulur."""
    kaynak = antet_kagidi(kutu)
    hg, hy = hedef
    if kaynak:
        sg, sy = KAGIT[kaynak]
        kat = min(hg / sg, hy / sy)
        return kat, (hg - sg * kat) / 2.0, (hy - sy * kat) / 2.0
    x0, y0, x1, y1 = kutu
    ag, ay = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    kat = min(hg / ag, hy / ay)
    return kat, (hg - ag * kat) / 2.0 - x0 * kat, (hy - ay * kat) / 2.0 - y0 * kat


def _yer_tutucu_doldur(varliklar, degerler):
    """<<ALAN>> yazılarını gerçek değerle değiştirir. Değeri verilmeyen
    alan BOŞ bırakılır - ekranda '<<CIZEN>>' yazısı kalmaz."""
    say = 0

    def _degis(m):
        nonlocal say
        say += 1
        return str(degerler.get(m.group(1), "") or "")

    for e in varliklar:
        t = e.dxftype()
        if t == "MTEXT":
            y = e.text or ""
            if "<<" in y:
                e.text = YER_TUTUCU.sub(_degis, y)
        elif t == "TEXT":
            y = e.dxf.text or ""
            if "<<" in y:
                e.dxf.text = YER_TUTUCU.sub(_degis, y)
    return say


# --------------------------------------------------------------- pafta
def pafta_kur(kaynak_dxf, antet_dxf, kagit, degerler, cikti_dxf,
              olcek=None, buyutme=False, pafta_adi="PAFTA"):
    """1:1 DXF'in KOPYASINA antetli bir pafta ekler.

    kaynak_dxf   : 1:1 çizim. AÇILIR, OKUNUR, DEĞİŞTİRİLMEZ.
    antet_dxf    : <<ALAN>> yer tutuculu antet. None ise yalın pafta.
    kagit        : "A4".."A0"
    degerler     : {"KOD": "...", "CIZEN": "..."} - ALANLAR'daki adlar
    cikti_dxf    : yeni dosya. Kaynak dosyaya dokunulmaz.
    olcek        : 1.0 / 0.1 gibi. None ise sığan en büyük ölçek seçilir.

    Döner: {"olcek": ..., "kagit": ..., "olcu": (gx,gy), "alan": (g,y)}
    """
    if kagit not in KAGIT:
        raise PaftaYok(f"Bilinmeyen kâğıt: {kagit}")
    kg, ky = KAGIT[kagit]

    d = ezdxf.readfile(kaynak_dxf)
    msp = d.modelspace()
    once = len(list(msp))

    # --- çizimin ölçüsü
    x0, y0, x1, y1 = cizim_kutusu(kaynak_dxf)
    gx, gy = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)

    # --- paftayı kur
    try:
        d.layouts.delete(pafta_adi)
    except Exception:
        pass
    pafta = d.layouts.new(pafta_adi)
    pafta.page_setup(size=(round(kg), round(ky)), margins=(0, 0, 0, 0),
                     units="mm", scale=16)   # 16 = 1 kâğıt birimi : 1 mm

    # --- anteti pafta uzayına taşı
    alan = None
    if antet_dxf:
        bilgi = antet_incele(antet_dxf)
        kat, dx, dy = _antet_olcekle(bilgi["kutu"], (kg, ky))
        kaynak = ezdxf.readfile(antet_dxf)
        eski = {e.dxf.handle for e in msp}
        imp = Importer(kaynak, d)
        imp.import_modelspace()
        imp.finalize()
        from ezdxf.math import Matrix44
        M = Matrix44.scale(kat, kat, 1.0) @ Matrix44.translate(dx, dy, 0.0)
        tasinan = [e for e in msp if e.dxf.handle not in eski]
        for e in tasinan:
            try:
                e.transform(M)
            except Exception:
                pass
            msp.unlink_entity(e)
            pafta.add_entity(e)
        if bilgi["cizim_alani"]:
            a0, b0, a1, b1 = bilgi["cizim_alani"]
            alan = (a0 * kat + dx, b0 * kat + dy, a1 * kat + dx, b1 * kat + dy)
        # Çizim alanı dikdörtgeni işini gördü; paftada görünmesin.
        for e in list(pafta):
            if e.dxf.layer.upper() == CIZIM_KATMAN:
                pafta.delete_entity(e)

    if alan is None:
        alan = (KENAR_PAYI, KENAR_PAYI, kg - KENAR_PAYI, ky - KENAR_PAYI)
    ag, ay = alan[2] - alan[0], alan[3] - alan[1]

    # --- ölçek
    if olcek is None:
        olcek = sigan_olcek(gx, gy, ag, ay, buyutme=buyutme)
        if not olcek:
            raise PaftaYok(
                f"{os.path.basename(kaynak_dxf)}: {gx:.0f}x{gy:.0f} mm çizim "
                f"{kagit} kâğıdın {ag:.0f}x{ay:.0f} mm alanına standart bir "
                f"ölçekle sığmıyor. Daha büyük kâğıt seçin.")
    elif gx * olcek > ag + 1e-6 or gy * olcek > ay + 1e-6:
        # Ölçeği kullanıcı verdiyse de kâğıda sığmayan pafta yazılmaz:
        # taşan çizim, olmayan çizimden beterdir.
        raise PaftaYok(
            f"{os.path.basename(kaynak_dxf)}: {gx:.0f}x{gy:.0f} mm çizim "
            f"{olcek_metni(olcek)} ölçekte {gx * olcek:.0f}x{gy * olcek:.0f} mm "
            f"yer ister; {kagit} kâğıtta {ag:.0f}x{ay:.0f} mm alan var. "
            "Ölçeği küçültün ya da kâğıdı büyütün.")

    # --- pencere: 1:1 çizime buradan bakılır
    pafta.add_viewport(
        center=((alan[0] + alan[2]) / 2.0, (alan[1] + alan[3]) / 2.0),
        size=(ag, ay),
        view_center_point=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
        view_height=ay / olcek,
    )

    # --- alanları doldur
    tam = dict(degerler or {})
    tam.setdefault("OLCEK", olcek_metni(olcek))
    tam.setdefault("PAFTA", kagit)
    tam.setdefault("BIRIM", "mm")
    tam.setdefault("TARIH", datetime.date.today().strftime("%d.%m.%Y"))
    tam.setdefault("DOSYA", os.path.basename(kaynak_dxf))
    _yer_tutucu_doldur(pafta, tam)

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
    return {"olcek": olcek, "olcek_metni": olcek_metni(olcek), "kagit": kagit,
            "olcu": (gx, gy), "alan": (ag, ay), "dosya": cikti_dxf}


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
    'ölçekle' demeye gerek kalmaz, %100 basılır."""
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
        kg, ky = KAGIT["A3"]

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


# ---------------------------------------------------- örnek/şablon antet
def ornek_antet(yol, kagit="A3", firma="FİRMA ADI"):
    """Çalışır durumda bir örnek antet üretir.

    Firma kendi antetini çizene kadar bununla iş görülür; çizerken de
    yer tutucuların nasıl yazıldığını görmek için şablon olur.
    Ölçüler ISO 7200'e yakındır: 180x63 mm antet, sağ alt köşede."""
    if kagit not in KAGIT:
        raise PaftaYok(f"Bilinmeyen kâğıt: {kagit}")
    kg, ky = KAGIT[kagit]
    d = ezdxf.new(setup=True)
    d.header["$INSUNITS"] = 4
    m = d.modelspace()
    for ad, renk in (("CERCEVE", 7), ("ANTET", 7), (CIZIM_KATMAN, 8)):
        if ad not in d.layers:
            d.layers.add(ad, color=renk)
    d.layers.get(CIZIM_KATMAN).dxf.plot = 0
    if "ANTET" not in d.styles:
        d.styles.add("ANTET", font="isocp.shx")

    p = 10.0                                   # kenar payı
    cx0, cy0, cx1, cy1 = p, p, kg - p, ky - p
    m.add_lwpolyline([(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1)],
                     close=True, dxfattribs={"layer": "CERCEVE",
                                             "lineweight": 50})

    ag, ay = 180.0, 63.0                       # antet kutusu
    ax0, ay0 = cx1 - ag, cy0
    m.add_lwpolyline([(ax0, ay0), (cx1, ay0), (cx1, ay0 + ay), (ax0, ay0 + ay)],
                     close=True, dxfattribs={"layer": "ANTET",
                                             "lineweight": 50})

    # Çizim alanı: çerçevenin içi, antetin üstü
    m.add_lwpolyline([(cx0, ay0 + ay), (cx1, ay0 + ay), (cx1, cy1), (cx0, cy1)],
                     close=True, dxfattribs={"layer": CIZIM_KATMAN})

    def cizgi(x1, y1, x2, y2):
        m.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "ANTET"})

    def yaz(x, y, s, h=2.5, kalin=False):
        t = m.add_text(s, height=h, dxfattribs={
            "layer": "ANTET", "style": "ANTET",
            "lineweight": 35 if kalin else 18})
        t.set_placement((x, y))
        return t

    # satır yükseklikleri (alttan yukarı): 8,8,8,8,8,8,15
    st = [ay0 + h for h in (8, 16, 24, 32, 40, 48)]
    for y in st:
        cizgi(ax0, y, cx1, y)
    for x in (ax0 + 60, ax0 + 120):
        cizgi(x, ay0, x, ay0 + 48)

    yaz(ax0 + 3, ay0 + 52, "<<FIRMA>>", 6.0, True)
    yaz(ax0 + 3, ay0 + 42, "PROJE"); yaz(ax0 + 22, ay0 + 42, "<<PROJE>>")
    yaz(ax0 + 3, ay0 + 34, "PARÇA"); yaz(ax0 + 22, ay0 + 34, "<<AD>>")
    yaz(ax0 + 3, ay0 + 26, "KOD");   yaz(ax0 + 22, ay0 + 26, "<<KOD>>")
    yaz(ax0 + 3, ay0 + 18, "MALZ.");  yaz(ax0 + 22, ay0 + 18, "<<MALZEME>>")
    yaz(ax0 + 3, ay0 + 10, "KALINLIK"); yaz(ax0 + 30, ay0 + 10, "<<KALINLIK>>")
    yaz(ax0 + 3, ay0 + 2.5, "AÇIKLAMA"); yaz(ax0 + 30, ay0 + 2.5, "<<ACIKLAMA>>")

    yaz(ax0 + 63, ay0 + 42, "POZ"); yaz(ax0 + 85, ay0 + 42, "<<POZ>>")
    yaz(ax0 + 63, ay0 + 34, "ADET"); yaz(ax0 + 85, ay0 + 34, "<<ADET>>")
    yaz(ax0 + 63, ay0 + 26, "KÜTLE"); yaz(ax0 + 85, ay0 + 26, "<<KUTLE>>")
    yaz(ax0 + 63, ay0 + 18, "ÖLÇÜ"); yaz(ax0 + 85, ay0 + 18, "<<OLCU>>")
    yaz(ax0 + 63, ay0 + 10, "TOLERANS"); yaz(ax0 + 90, ay0 + 10, "<<TOLERANS>>")

    yaz(ax0 + 123, ay0 + 42, "ÇİZEN"); yaz(ax0 + 145, ay0 + 42, "<<CIZEN>>")
    yaz(ax0 + 123, ay0 + 34, "KONTROL"); yaz(ax0 + 148, ay0 + 34, "<<KONTROL>>")
    yaz(ax0 + 123, ay0 + 26, "TARİH"); yaz(ax0 + 145, ay0 + 26, "<<TARIH>>")
    yaz(ax0 + 123, ay0 + 18, "REV."); yaz(ax0 + 145, ay0 + 18, "<<REVIZYON>>")
    yaz(ax0 + 123, ay0 + 10, "ÖLÇEK"); yaz(ax0 + 145, ay0 + 10, "<<OLCEK>>", 4.0, True)
    yaz(ax0 + 123, ay0 + 2.5, "KÂĞIT"); yaz(ax0 + 145, ay0 + 2.5, "<<PAFTA>>", 4.0, True)

    # Firma adını da gerçek değerle yazabilmek için yer tutucu bıraktık;
    # sabit isterseniz aşağıdaki satırı silin ve <<FIRMA>> yerine yazın.
    d.saveas(yol)
    return yol


# --------------------------------------------------------------- toplu
def antet_sec(antet, kagit):
    """Kâğıda özel antet varsa onu kullan.

    ANTET.dxf'in yanında ANTET_A1.dxf duruyorsa A1 paftada o kullanılır.
    Böylece isteyen her kâğıda ayrı antet çizer (yazı boyları standart
    kalır); istemeyen tek antetle devam eder, program onu kâğıda göre
    oranlar."""
    if not antet:
        return None
    kok, uzanti = os.path.splitext(antet)
    ozel = f"{kok}_{kagit}{uzanti}"
    return ozel if os.path.isfile(ozel) else antet


def bom_degerleri(sat, acinim=None):
    """BOM satırını antet alanlarına çevirir.

    sat: pf3_olcu'nun ürettiği satır sözlüğü. Olmayan alan yazılmaz."""
    d = {}
    if not sat:
        return d
    e = {"POZ": sat.get("poz"), "KOD": sat.get("kod"), "AD": sat.get("ad"),
         "ADET": sat.get("adet"), "MALZEME": sat.get("malzeme_ad")
         or sat.get("malzeme"), "OLCU": sat.get("olcu")}
    k = sat.get("sac_kalinlik_mm") or sat.get("kalinlik_mm")
    if k:
        e["KALINLIK"] = f"{k} mm"
    if sat.get("kutle_kg") is not None:
        e["KUTLE"] = f"{sat['kutle_kg']} kg"
    if acinim:
        e["ACIKLAMA"] = (f"AÇINIM  {acinim.get('acinim_genislik_mm')} x "
                         f"{acinim.get('acinim_boy_mm')} mm   "
                         f"{acinim.get('bukum_sayisi')} büküm   "
                         f"K={acinim.get('k_faktor')}")
    for a, v in e.items():
        if v not in (None, ""):
            d[a] = str(v)
    return d


def antet_alanlari(bilgi, kagitlar=KAGIT_SIRA):
    """Antet her kâğıda oturtulduğunda çizime kalan boşluk.
    {"A3": (g, y), ...}"""
    sonuc = {}
    for k in kagitlar:
        kg, ky = KAGIT[k]
        if bilgi and bilgi.get("cizim_alani"):
            kat, _, _ = _antet_olcekle(bilgi["kutu"], (kg, ky))
            a0, b0, a1, b1 = bilgi["cizim_alani"]
            sonuc[k] = ((a1 - a0) * kat, (b1 - b0) * kat)
        else:
            sonuc[k] = (kg - 2 * KENAR_PAYI, ky - 2 * KENAR_PAYI)
    return sonuc


def kagit_plani(dosyalar, antet_dxf=None, tercih=("A4", "A3")):
    """Hangi çizim hangi kâğıda 1:1 sığıyor, hangisi sığmıyor.

    Kullanıcıya "şunlar sığmadı, hangi kâğıt olsun?" diye sormadan önce
    çalıştırılır. Hiçbir dosya yazmaz, sadece bakar."""
    bilgi = antet_incele(antet_dxf) if antet_dxf else None
    alanlar = antet_alanlari(bilgi)
    sigan, sigmayan, hata = [], [], []
    for y in dosyalar:
        try:
            x0, y0, x1, y1 = cizim_kutusu(y)
            gx, gy = x1 - x0, y1 - y0
        except Exception as e:
            hata.append((y, str(e)))
            continue
        k = kagit_sec(gx, gy, tercih, antet_alani=alanlar)
        (sigan if k else sigmayan).append({"dosya": y, "olcu": (gx, gy),
                                           "kagit": k})
    # Sığmayanlar için önerilecek kâğıtlar: 1:1 alacak en küçüğünden başla
    for s in sigmayan:
        gx, gy = s["olcu"]
        s["birebir"] = kagit_sec(gx, gy, KAGIT_SIRA, antet_alani=alanlar)
        s["secenek"] = []
        for k in KAGIT_SIRA:
            o = sigan_olcek(gx, gy, *alanlar[k])
            if o:
                s["secenek"].append((k, o, olcek_metni(o)))
    return {"sigan": sigan, "sigmayan": sigmayan, "hata": hata,
            "antet": bilgi, "alanlar": alanlar}


def toplu_pafta(isler, antet_dxf, cikti_klasor, ortak=None):
    """isler: [{"dosya":..., "kagit":"A3", "olcek":None, "degerler":{...}}, ...]

    Her biri için kaynağın KOPYASINA pafta eklenir. Kaynak dosyalara
    dokunulmaz; çıktı ayrı klasöre yazılır."""
    os.makedirs(cikti_klasor, exist_ok=True)
    yapilan, hata = [], []
    for it in isler:
        y = it["dosya"]
        ad = os.path.splitext(os.path.basename(y))[0]
        cik = os.path.join(cikti_klasor, f"{ad}_{it['kagit']}.dxf")
        d = dict(ortak or {})
        d.update(it.get("degerler") or {})
        try:
            r = pafta_kur(y, antet_sec(antet_dxf, it["kagit"]), it["kagit"],
                          d, cik, olcek=it.get("olcek"))
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
        description="Pi3D – 1:1 DXF'leri antetli paftaya yerleştirir.")
    a.add_argument("dxf", nargs="*", help="1:1 DXF dosyaları (joker olur)")
    a.add_argument("--antet", help="antet DXF'i")
    a.add_argument("--ornek-antet", metavar="YOL",
                   help="örnek antet üret ve çık")
    a.add_argument("--kagit", default=None,
                   help="A4..A0; verilmezse sığan en küçüğü seçilir")
    a.add_argument("--olcek", type=float, default=None,
                   help="1 / 0.1 gibi; verilmezse sığan en büyüğü")
    a.add_argument("--cikti", default="PAFTA", help="çıktı klasörü")
    a.add_argument("--plan", action="store_true",
                   help="hiçbir şey yazma, hangi kâğıda sığdığını söyle")
    a.add_argument("--bas", action="store_true", help="PDF de üret")
    a.add_argument("--firma", default="")
    a.add_argument("--cizen", default="")
    a.add_argument("--proje", default="")
    a.add_argument("--aciklama", default="")
    n = a.parse_args()

    if n.ornek_antet:
        print("örnek antet:", ornek_antet(n.ornek_antet, n.kagit or "A3",
                                          n.firma or "FİRMA ADI"))
        return

    dosya = []
    for d in n.dxf:
        dosya += sorted(_glob.glob(d)) if any(c in d for c in "*?[") else [d]
    if not dosya:
        a.error("DXF verilmedi.")

    if n.plan or not n.kagit:
        p = kagit_plani(dosya, n.antet)
        for s in p["sigan"]:
            print(f"  {s['kagit']}  1:1   {os.path.basename(s['dosya'])}"
                  f"   ({s['olcu'][0]:.0f}x{s['olcu'][1]:.0f})")
        for s in p["sigmayan"]:
            sec = ", ".join(f"{k} {m}" for k, _, m in s["secenek"][:4])
            print(f"  SIĞMADI  {os.path.basename(s['dosya'])}"
                  f"   ({s['olcu'][0]:.0f}x{s['olcu'][1]:.0f})  ->  {sec}")
        for y, e in p["hata"]:
            print(f"  HATA  {os.path.basename(y)}: {e}")
        if n.plan:
            return
        isler = [{"dosya": s["dosya"], "kagit": s["kagit"]}
                 for s in p["sigan"]]
        if p["sigmayan"]:
            print(f"\n{len(p['sigmayan'])} çizim A4/A3'e sığmadı; "
                  "--kagit ile boy verin.")
    else:
        isler = [{"dosya": y, "kagit": n.kagit, "olcek": n.olcek}
                 for y in dosya]

    ortak = {k: v for k, v in (("FIRMA", n.firma), ("CIZEN", n.cizen),
                               ("PROJE", n.proje),
                               ("ACIKLAMA", n.aciklama)) if v}
    r = toplu_pafta(isler, n.antet, n.cikti, ortak)
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
