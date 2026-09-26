# -*- coding: utf-8 -*-
"""GEOMETRİDEN TANIMA: adı olmayan katı pul mu, somun mu, cıvata mı,
perçin mi, pim mi, kaynak dikişi mi?

CAD'ler bazen katıya ad vermez ("COMPOUND", "SOLID", "Body"): addan
sınıflama o zaman hiçbir şey bilemez, cıvata "üretim parçası" sayılıp
resmi çizilir. Burada katının YÜZLERİNE bakılır.

İlke: yalnız KESİN imzası olan tanınır; emin olunmayan hiçbir şey
söylenmez (None döner, parça parça kalır). Her karar ölçülerle birlikte
gerekçesini yazar ("somun: 6 yüz 60° aralıklı, anahtar ağzı 16,0,
delik Ø10,0, yükseklik 8,0").

İmzalar
  dönel parça: yüzlerin (düz yüzler dâhil) en az %90'ı TEK bir eksene
  göre dizilmiş olmalı - silindir/koni/küre/tor bu eksende, düz
  yüzler eksene dik ya da paralel.
    pul      eksene dik iki düz yüz + dış silindir + boydan boya delik;
             kalınlık <= dış çapın %30'u, iç/dış çap oranı 0,25-0,85
    somun    eksene paralel 6 düz yüz, normalleri 60° aralıklı ve
             eksenden eşit uzakta (altıgen) ya da 4 yüz 90° (kare);
             boydan boya delik; anahtar ağzı / delik 1,3-2,4
    cıvata   boydan boya delik YOK; bir ucunda altıgen ya da daha geniş
             silindirik baş, gövdesi (şaft) başından en az 1 çap uzun
    perçin   şaft + bir ucunda kubbe (küre/tor) ya da havşa (koni) baş
    pim      tek dış çap (pahlar hariç), başsız, boy/çap >= 2, çap <= 12
  kaynak dikişi (köşe kaynağı): birbirine DİK iki düz "bacak" yüzü ve
  bir hipotenüs yüzü; uzun üçgen prizma. Bacak uzunlukları hacimden ve
  yüz alanlarından HESAPLANIR (A1*A2 = 2*V*L), 1-20 mm olmalı, dikiş
  boyu bacağın en az 3 katı, hipotenüs alanı hesapla %20 içinde.
"""
from __future__ import annotations

import math
import re

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp, BRepGProp_Face
from OCP.Bnd import Bnd_Box
from OCP.GeomAbs import (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
                         GeomAbs_Sphere, GeomAbs_Torus)
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

ACI_TOL = math.radians(1.5)       # paralel / dik sayılan sapma
EKSEN_TOL = 0.05                  # iki eksen aynı çizgi mi (mm)
EN_BUYUK = 400.0                  # bundan büyük katı bağlantı elemanı sayılmaz

# Adı bilgi taşımayan katılar: yalnız bunlarda geometri KARAR verir.
ISIMSIZ = (r"^(?:(?:compound|solid|body|bodies|part|parca|parça|kati|katı"
           r"|shape|brep|product|korper|körper|bauteil|volume|mesh|feature"
           r"|pad|extrude|partbody)(?:[\s_.\-]*\d+)*|\d{1,3})$")
# (Uzun sayı - "510206504-00" - parça numarasıdır, adsız sayılmaz.)


def isimsiz(ad):
    a = re.sub(r"^(?:symmetry of|mirror of)\s+", "", (ad or "").strip().lower())
    return bool(re.match(ISIMSIZ, a))


# ------------------------------------------------------------ yüzler
def _yuzler(sh):
    out = []
    ex = TopExp_Explorer(sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        g = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, g)
        a = g.Mass()
        if a <= 1e-9:
            continue
        s = BRepAdaptor_Surface(f)
        t = s.GetType()
        y = {"f": f, "alan": a, "tip": "diger"}
        if t == GeomAbs_Plane:
            n = s.Plane().Axis().Direction()
            p = s.Plane().Location()
            y.update(tip="duz", n=(n.X(), n.Y(), n.Z()), p=(p.X(), p.Y(), p.Z()))
        elif t in (GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus):
            if t == GeomAbs_Cylinder:
                ax, r = s.Cylinder().Axis(), s.Cylinder().Radius()
                y["tip"] = "silindir"
            elif t == GeomAbs_Cone:
                ax, r = s.Cone().Axis(), s.Cone().RefRadius()
                y["tip"] = "koni"
            elif t == GeomAbs_Torus:
                ax, r = s.Torus().Axis(), s.Torus().MajorRadius()
                y["tip"] = "tor"
            else:
                c = s.Sphere().Location()
                y.update(tip="kure", c=(c.X(), c.Y(), c.Z()),
                         r=s.Sphere().Radius())
                out.append(y)
                continue
            d, p = ax.Direction(), ax.Location()
            y.update(d=(d.X(), d.Y(), d.Z()), o=(p.X(), p.Y(), p.Z()), r=r)
        out.append(y)
    return out


def _nokta(a, b):
    return sum(x * y for x, y in zip(a, b))


def _fark(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _uzunluk(a):
    return math.sqrt(_nokta(a, a))


def _eksene_uzak(p, o, d):
    v = _fark(p, o)
    k = _nokta(v, d)
    return _uzunluk(tuple(v[i] - k * d[i] for i in range(3)))


def _paralel(a, b):
    return abs(abs(_nokta(a, b)) - 1.0) < 1 - math.cos(ACI_TOL)


def _dik(a, b):
    return abs(_nokta(a, b)) < math.sin(ACI_TOL)


def _ana_eksen(yz):
    """Dönel yüzlerin en çok alan topladığı eksen: (o, d) ya da None."""
    gruplar = []
    for y in yz:
        if y["tip"] not in ("silindir", "koni", "tor"):
            continue
        for g in gruplar:
            if _paralel(g["d"], y["d"]) and _eksene_uzak(y["o"], g["o"], g["d"]) < EKSEN_TOL:
                g["alan"] += y["alan"]
                break
        else:
            gruplar.append({"o": y["o"], "d": y["d"], "alan": y["alan"]})
    if not gruplar:
        return None
    g = max(gruplar, key=lambda t: t["alan"])
    return g["o"], g["d"]


def _eksene_tasi(sh, o, d):
    """Katıyı eksen Z olacak, eksen orijinden geçecek şekilde taşır."""
    t = gp_Trsf()
    t.SetTransformation(gp_Ax3(gp_Pnt(*o), gp_Dir(*d)))   # genel -> eksen
    return BRepBuilderAPI_Transform(sh, t, True).Shape()


def _kutu(sh):
    b = Bnd_Box()
    BRepBndLib.Add_s(sh, b)
    b.SetGap(0.0)
    return b.Get()


def _ice_bakar(y):
    """Yüzün (malzemeden dışarı bakan) normali eksene doğru mu: silindirde
    DELİK, düz yan yüzde altıgen YUVA (imbus). Normal, yüzün yönü hesaba
    katılarak alınır."""
    s = BRepAdaptor_Surface(y["f"])
    u = 0.5 * (s.FirstUParameter() + s.LastUParameter())
    v = 0.5 * (s.FirstVParameter() + s.LastVParameter())
    p, n = gp_Pnt(), gp_Vec()
    BRepGProp_Face(y["f"]).Normal(u, v, p, n)
    radyal = (p.X(), p.Y(), 0.0)          # eksen Z'de, orijinden geçer
    return _nokta(radyal, (n.X(), n.Y(), n.Z())) < 0


_delik_mi = _ice_bakar


# ------------------------------------------------------------ tanıma
def tani(sh, hacim=None):
    """(sinif, tip, gerekce) ya da None (emin değil)."""
    try:
        return _tani(sh, hacim)
    except Exception:
        return None


def _tani(sh, V):
    if V is None:
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(sh, g)
        V = g.Mass()
    if V <= 1e-6:
        return None
    x0, y0, z0, x1, y1, z1 = _kutu(sh)
    if max(x1 - x0, y1 - y0, z1 - z0) > EN_BUYUK:
        return None
    yz = _yuzler(sh)
    if not yz:
        return None
    toplam = sum(y["alan"] for y in yz)
    r = _kaynak_dikisi(yz, toplam, V)
    if r:
        return r
    # O-ring / halka conta: yalnız tor yüzlerinden oluşan katı
    if all(y["tip"] == "tor" for y in yz):
        R = max(y["r"] for y in yz)
        return ("standart", "o-ring",
                f"o-ring: yalnız tor yüzü, orta çap Ø{2 * R:.1f}".replace(".", ","))
    e = _ana_eksen(yz)
    if not e:
        return None
    return _donel(sh, e, V)


def _kaynak_dikisi(yz, toplam, V):
    duz = sorted((y for y in yz if y["tip"] == "duz"), key=lambda y: -y["alan"])
    for i in range(min(3, len(duz))):
        for j in range(i + 1, min(4, len(duz))):
            a, b = duz[i], duz[j]
            if not _dik(a["n"], b["n"]):
                continue
            L = a["alan"] * b["alan"] / (2.0 * V)
            ba, bb = a["alan"] / L, b["alan"] / L
            if not (1.0 <= ba <= 20.0 and 1.0 <= bb <= 20.0):
                continue
            if L < 3.0 * max(ba, bb) or max(ba, bb) > 3.0 * min(ba, bb):
                continue
            hip = math.hypot(ba, bb) * L
            kalan = [y for y in yz if y is not a and y is not b]
            h = max(kalan, key=lambda y: y["alan"], default=None)
            if h is None or abs(h["alan"] - hip) > 0.2 * hip:
                continue
            uclar = toplam - a["alan"] - b["alan"] - h["alan"]
            if uclar > 0.15 * toplam:
                continue
            return ("kaynak", "",
                    f"köşe kaynağı: dik iki bacak {ba:.1f} x {bb:.1f} mm, "
                    f"boy {L:.0f} mm")
    return None


def _donel(sh, eksen, V):
    o, d = eksen
    t = _eksene_tasi(sh, o, d)
    yz = _yuzler(t)
    toplam = sum(y["alan"] for y in yz)
    z = (0.0, 0.0, 1.0)
    x0, y0, z0, x1, y1, z1 = _kutu(t)
    H = z1 - z0
    D = max(x1 - x0, y1 - y0)
    if H <= 0 or D <= 0:
        return None

    donel, dik_duz, yan_duz, diger = [], [], [], 0.0
    for y in yz:
        if y["tip"] in ("silindir", "koni", "tor"):
            if _paralel(y["d"], z) and _eksene_uzak(y["o"], (0, 0, 0), z) < EKSEN_TOL:
                bx = _kutu(y["f"])
                y["z"] = (bx[2] - z0, bx[5] - z0)
                y["rmax"] = max(abs(bx[0]), abs(bx[1]), abs(bx[3]), abs(bx[4]))
                donel.append(y)
                continue
        elif y["tip"] == "kure":
            if _eksene_uzak(y["c"], (0, 0, 0), z) < EKSEN_TOL:
                bx = _kutu(y["f"])
                y["z"] = (bx[2] - z0, bx[5] - z0)
                y["rmax"] = max(abs(bx[0]), abs(bx[1]), abs(bx[3]), abs(bx[4]))
                donel.append(y)
                continue
        elif y["tip"] == "duz":
            if _paralel(y["n"], z):
                dik_duz.append(y)
                continue
            if _dik(y["n"], z):
                y["uzak"] = abs(_nokta(y["p"], y["n"]))
                y["aci"] = math.degrees(math.atan2(y["n"][1], y["n"][0])) % 360
                bx = _kutu(y["f"])
                y["z"] = (bx[2] - z0, bx[5] - z0)
                yan_duz.append(y)
                continue
        diger += y["alan"]
    if diger > 0.10 * toplam:
        return None                    # dönel değil (ya da dişler modelli)

    sil = [y for y in donel if y["tip"] == "silindir"]
    for y in sil:
        y["delik"] = _delik_mi(y)
    # Boydan boya delik: eksen çizgisi baştan sona malzemenin DIŞINDA.
    # (Deliğin ağzı pahlıysa silindir tam boyu kaplamaz; o yüzden yüzün
    # boyuna değil, eksen üstündeki noktalara bakılır.)
    delikler = [y for y in sil if y["delik"]]
    delik_r = 0.0
    if delikler and _eksen_bos(t, z0, H):
        delik_r = max(y["r"] for y in delikler)
    dis = [y for y in sil if not y["delik"]]

    # İçe bakan yan yüzler başın içindeki yuvadır (imbus, torx): biçimi
    # dıştan belirleyen yüzler değil.
    yuva = [y for y in yan_duz if _ice_bakar(y)]
    yan_duz = [y for y in yan_duz if not _ice_bakar(y)]
    # --- altıgen / kare prizma (somun, cıvata başı)
    cok = _cokgen(yan_duz)

    def m(v):
        return f"{v:.1f}".replace(".", ",")

    if cok and delik_r > 0:
        n, s, zb = cok
        if 1.3 <= s / (2 * delik_r) <= 2.4 and 0.25 <= H / (2 * delik_r) <= 1.6:
            return ("standart", "somun",
                    f"somun: {n} yüz {360 // n}° aralıklı, anahtar ağzı {m(s)}, "
                    f"delik Ø{m(2 * delik_r)}, yükseklik {m(H)}")
        return None
    if cok and delik_r == 0:
        n, s, zb = cok
        # baş bir uçta; kalan boyda başa göre ince şaft
        saft = [y for y in dis if y["r"] < 0.45 * s
                and (y["z"][1] - y["z"][0]) > 0.3 * H]
        if saft and zb[1] - zb[0] < 0.6 * H:
            ds = 2 * max(y["r"] for y in saft)
            Ls = H - (zb[1] - zb[0])
            if Ls >= ds and (zb[0] < 0.05 * H + 0.05 or zb[1] > 0.95 * H - 0.05):
                return ("standart", "civata",
                        f"cıvata: {n} köşe baş (anahtar ağzı {m(s)}), "
                        f"gövde Ø{m(ds)} x {m(Ls)}")
        return None
    if yan_duz and sum(y["alan"] for y in yan_duz) > 0.05 * toplam:
        return None                    # başka düz yan yüzler: bilinmeyen biçim

    if not dis:
        return None
    Rmax = max(y["r"] for y in dis)

    # --- pul
    if delik_r > 0 and H <= 0.30 * 2 * Rmax and 0.25 <= delik_r / Rmax <= 0.85:
        buyuk = [y for y in dis if abs(y["r"] - Rmax) < 1e-3]
        if buyuk and len(dik_duz) >= 2 and len({round(y["r"], 2) for y in dis}) <= 2:
            return ("standart", "pul",
                    f"pul: Ø{m(2 * Rmax)} / Ø{m(2 * delik_r)} x {m(H)}")
        return None

    # --- başlı eleman: bir uçta geniş baş, kalan boyda şaft
    saft_r = min((y["r"] for y in dis if (y["z"][1] - y["z"][0]) > 0.4 * H),
                 default=None)
    if saft_r is None:
        return None
    ds = 2 * saft_r
    # Baş: şafttan belirgin geniş (%30) dönel yüzler. Şaftın ucundaki
    # pah konisi baş değildir.
    bas = [y for y in donel if not y.get("delik") and y["rmax"] > 1.3 * saft_r]
    if bas:
        bz0 = min(y["z"][0] for y in bas)
        bz1 = max(y["z"][1] for y in bas)
        uc = bz0 < 0.05 * H + 0.05 or bz1 > 0.95 * H - 0.05
        Ls = H - (bz1 - bz0)
        genis = D / ds
        if uc and Ls >= ds and 1.4 <= genis <= 3.0 and bz1 - bz0 < 0.5 * H:
            kubbe = any(y["tip"] in ("kure", "tor") and y["r"] > saft_r for y in bas)
            havsa = any(y["tip"] == "koni" for y in bas)
            if kubbe or havsa:
                return ("standart", "perçin" if delik_r or Ls <= 6 * ds else "civata",
                        f"{'perçin' if delik_r or Ls <= 6 * ds else 'cıvata'}: "
                        f"{'kubbe' if kubbe else 'havşa'} baş Ø{m(D)}, "
                        f"gövde Ø{m(ds)} x {m(Ls)}")
            if delik_r == 0:
                return ("standart", "civata",
                        f"cıvata: silindirik baş Ø{m(D)}, gövde Ø{m(ds)} x {m(Ls)}")
        return None

    # --- pim: tek çap, başsız, UÇLARI PAHLI ya da yuvarlatılmış.
    # Düz uçlu çıplak silindir BELİRSİZDİR: CATIA kaynak dikişini çoğu
    # zaman Ø5 çubuk olarak modeller (kaynaklı kasada 21 dikiş böyleydi);
    # ona karar verilmez.
    cap = {round(y["r"], 2) for y in dis}
    uc = [y for y in donel if y["tip"] in ("koni", "tor", "kure")]
    if (len(cap) == 1 and uc and H >= 2 * ds and ds <= 12.0 + 1e-6
            and delik_r == 0):
        return ("standart", "pim", f"pim: Ø{m(ds)} x {m(H)}, uçları pahlı")
    return None


def _eksen_bos(sh, z0, H, n=9):
    """Eksen (Z) üstündeki noktaların hepsi katının dışında mı."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_OUT
    for i in range(n):
        z = z0 + H * (0.03 + 0.94 * i / (n - 1))
        c = BRepClass3d_SolidClassifier(sh, gp_Pnt(0.0, 0.0, z), 1e-6)
        if c.State() != TopAbs_OUT:
            return False
    return True


def _cokgen(yan):
    """Eksene paralel düz yüzlerden altıgen (6 x 60°) ya da kare (4 x 90°)
    prizma: (köşe sayısı, anahtar ağzı, (z0, z1)) ya da None."""
    if len(yan) < 4:
        return None
    for n in (6, 4):
        adim = 360.0 / n
        gruplar = {}
        for y in yan:
            k = round(y["uzak"], 1)
            gruplar.setdefault(k, []).append(y)
        for uz, g in sorted(gruplar.items(), key=lambda t: -len(t[1])):
            acilar = sorted({round(y["aci"] % 360, 1) for y in g})
            if len(acilar) != n:
                continue
            fark = [(acilar[(i + 1) % n] - acilar[i]) % 360 for i in range(n)]
            if all(abs(f - adim) < 1.5 for f in fark):
                z0 = min(y["z"][0] for y in g)
                z1 = max(y["z"][1] for y in g)
                return n, 2 * uz, (z0, z1)
    return None
