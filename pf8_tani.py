# -*- coding: utf-8 -*-
"""GEOMETRİDEN TANIMA: adı olmayan katı pul mu, somun mu, cıvata mı,
perçin mi, perçin somun mu, pim mi, kaynak dikişi mi; parça bir PROFİL mi
(kutu, boru, L, U, lama, ekstrüzyon); iki parça BİÇİMCE benzer mi.

Bölümler:
  tani()          yüz tiplerinden (_donel) ya da ışın ölçümüyle
                  (_donel_isin: diş / tırtıl modelli parça) bağlantı elemanı
  profil()        boyuna 9 kesit: sabit kesitli mi, kesit türü ve ölçüsü
  bicim_imzasi()  ölçekten ve duruştan bağımsız imza (öğrenme için)

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
             boydan boya delik; anahtar ağzı / delik 1,3-2,4;
             yükseklik / delik >= 0,45 (daha yassısı delikli plakadır)
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

import pf9_excel as XL

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp, BRepGProp_Face
from OCP.Bnd import Bnd_Box
from OCP.GeomAbs import (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
                         GeomAbs_Sphere, GeomAbs_Torus)
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

ACI_TOL = math.radians(1.5)       # paralel / dik sayılan sapma
EKSEN_TOL = 0.05                  # iki eksen aynı çizgi mi (mm)
EN_BUYUK = 400.0                  # bundan büyük katı bağlantı elemanı sayılmaz
YAPI_EN_BUYUK = 160.0             # yapısal tanıma (1440 ışın) bu boyuta kadar

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
    """(sinif, tip, gerekce) ya da None (emin değil).

    Sıra: yüz tipleri (_donel, temiz model) -> ışın ölçümü (_donel_isin:
    diş / tırtıl modelli) -> YAPISAL tanıma (pf11_yapi: gövde + baş +
    lokma, delik + tutma yüzü...) -> YAY (pf11_yapi.yay: spir yapısı) ->
    AİLELER (pf13_aile: segman, yaylı pim, kama, konik pim, gres nipeli).
    Yapısal tanıma yalnız KESİN
    sonucunda karar verir; ayrıca cıvata / somun kararlarının tipini
    ayrıntılandırır ("altıköşe flanşlı başlı cıvata", "bombe başlı
    cıvata, imbus")."""
    # YAY önce: içi boş, yüzeyi helis olan parçada öbür ölçümler (OCC
    # ışını helis yüzde yavaştır) dakikalar sürer; yay ağ üzerinde ~2 sn.
    try:
        import pf11_yapi as Y
        if max(_boyutlar(sh)) <= EN_BUYUK and Y.yay_olabilir(sh, hacim):
            y = Y.yay(sh, hacim)
            if y:
                # kesin: spir (basma / çekme / burulma / konik yay); değilse
                # katmanlı yay adayı: karar yok, aday işaretinde görünür
                return (y[0], y[1], y[2]) if y[3] else None
    except Exception:
        pass
    try:
        r = _tani(sh, hacim)
    except Exception:
        return None
    # standart AİLELER (pf13_aile): segman "pul" sanılmasın (açık halka +
    # kulak deliği); karar çıkmayanda yaylı pim, kama, konik pim, nipel
    if r is None or r[1] == "pul":
        try:
            import pf13_aile as A
            a = A.aile_tani(sh)
            if a and a[3]:
                return (a[0], a[1], a[2])
        except Exception:
            pass
    try:
        import pf11_yapi as Y
        if r is None:
            if max(_boyutlar(sh)) <= YAPI_EN_BUYUK:
                y = Y.yapisal_tani(sh)
                if y and y[3] and y[0] == "standart":
                    return (y[0], y[1], y[2])
            return None
        if r[0] == "standart" and r[1] in ("civata", "somun"):
            y = Y.yapisal_tani(sh)
            if y and y[3] and (("cıvata" in y[1]) == (r[1] == "civata")) \
                    and "perçin" not in y[1]:
                return (r[0], y[1], f"{r[2]}; {y[2]}")
    except Exception:
        pass
    return r


def _boyutlar(sh):
    kb = _kutu(sh)
    return (kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2])


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
    # Bilye: yalnız küre yüzü (rulman elemanı, bilyeli kilit...)
    if all(y["tip"] == "kure" for y in yz):
        R = max(y["r"] for y in yz)
        return ("standart", "bilye",
                f"bilye: yalnız küre yüzü, Ø{2 * R:.2f}".replace(".", ","))
    # O-ring / halka conta: yalnız tor yüzlerinden oluşan katı
    if all(y["tip"] == "tor" for y in yz):
        R = max(y["r"] for y in yz)
        return ("standart", "o-ring",
                f"o-ring: yalnız tor yüzü, orta çap Ø{2 * R:.1f}".replace(".", ","))
    e = _ana_eksen(yz)
    if e:
        r = _donel(sh, e, V) or _donel_isin(sh, e)
        if r:
            return r
    # Dönel yüzü olmayan (dişi serbest yüzle modellenmiş) parçada eksen
    # eylemsizlikten bulunur: iki asal momenti eşit olan eksen simetri
    # eksenidir (altıgen, kare, silindir için doğru).
    e2 = _simetri_ekseni(sh)
    if e2 and not (e and _paralel(e[1], e2[1])
                   and _eksene_uzak(e2[0], e[0], e[1]) < EKSEN_TOL):
        return _donel_isin(sh, e2)
    return None


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
        return XL.tr(v, 1, sade=False)

    if cok and delik_r > 0:
        n, s, zb = cok
        if 1.3 <= s / (2 * delik_r) <= 2.4 and 0.45 <= H / (2 * delik_r) <= 1.6:
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


def _simetri_ekseni(sh):
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(sh, g)
    p = g.PrincipalProperties()
    I = p.Moments()
    I = (I[0], I[1], I[2])
    eks = (p.FirstAxisOfInertia(), p.SecondAxisOfInertia(), p.ThirdAxisOfInertia())
    c = g.CentreOfMass()
    for i in range(3):
        j, k = [x for x in range(3) if x != i]
        if abs(I[j] - I[k]) <= 0.005 * max(I[j], I[k]) \
                and abs(I[i] - I[j]) > 0.02 * max(I[i], I[j]):
            d = eks[i]
            return (c.X(), c.Y(), c.Z()), (d.X(), d.Y(), d.Z())
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


# ================================================================ PROFİL
# Profil (kutu, boru, köşebent, U, I, T, lama, mil, alüminyum ekstrüzyon):
# bir eksen boyunca SABİT KESİTLİ parça. Adına bakılmaz; parça boyuna
# birkaç yerden kesilir:
#   - kesitlerin çoğu aynı alanda (delik/pah/gönye kesimi birkaçını
#     bozabilir; ortanca alınır)
#   - hacim ~ kesit alanı x boy (gönye kesimli uçlar hacmi biraz düşürür)
#   - boy, kesitin en büyük ölçüsünün en az 3 katı (yoksa plaka/blok)
# Kesit türü kesitin kendisinden ÖLÇÜLÜR: iç boşluk sayısı, dış çizginin
# dışbükey örtüsündeki cepler (L'de 1 köşe cebi, U'da 1 yan cebi, I'da 2
# karşılıklı yan cebi, T'de 2 komşu köşe cebi...).
PROFIL_NARIN = 3.0          # boy / kesit en büyük ölçüsü alt sınırı
PROFIL_ISTASYON = 9


def _cizgi_kenarlari(sh):
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE
    out = []
    ex = TopExp_Explorer(sh, TopAbs_EDGE)
    while ex.More():
        c = BRepAdaptor_Curve(TopoDS.Edge_s(ex.Current()))
        ex.Next()
        if c.GetType() != GeomAbs_Line:
            continue
        p, q = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        v = (q.X() - p.X(), q.Y() - p.Y(), q.Z() - p.Z())
        u = _uzunluk(v)
        if u > 1e-6:
            out.append((u, tuple(x / u for x in v)))
    return out


def _eksen_adaylari(sh, yz):
    """Profil ekseni adayları: en uzun doğru kenar yönü, en büyük
    silindirin ekseni (boru, mil)."""
    ad = []
    ke = sorted(_cizgi_kenarlari(sh), key=lambda t: -t[0])
    if ke:
        ad.append(ke[0][1])
    sil = [y for y in yz if y["tip"] == "silindir"]
    if sil:
        ad.append(max(sil, key=lambda y: y["alan"])["d"])
    tek = []
    for d in ad:
        if not any(_paralel(d, e) for e in tek):
            tek.append(d)
    return tek


def _kesit(sh, z):
    """z düzlemindeki kesit: [(nokta listesi, alan, derinlik)], net alan,
    ayrı bölge sayısı. Boole kesmesi yerine düzlem kesiti (5 kat hızlı):
    kesit eğrileri tellere bağlanır; bir tel başka birinin içindeyse
    boşluktur (derinlik tek), onun içindeki yine malzemedir."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopTools import TopTools_HSequenceOfShape
    from OCP.gp import gp_Pln
    op = BRepAlgoAPI_Section(sh, gp_Pln(gp_Pnt(0.0, 0.0, z), gp_Dir(0.0, 0.0, 1.0)))
    op.Build()
    if not op.IsDone():
        return [], 0.0, 0
    kenar = TopTools_HSequenceOfShape()
    ex = TopExp_Explorer(op.Shape(), TopAbs_EDGE)
    while ex.More():
        kenar.Append(ex.Current())
        ex.Next()
    teller = TopTools_HSequenceOfShape()
    ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(kenar, 1e-5, False, teller)
    out = []
    for i in range(1, teller.Length() + 1):
        w = TopoDS.Wire_s(teller.Value(i))
        if not w.Closed() and not _kapali(w):
            return [], 0.0, 0                  # açık tel: kesit güvenilmez
        mf = BRepBuilderAPI_MakeFace(w, True)
        if not mf.IsDone():
            return [], 0.0, 0
        g = GProp_GProps()
        BRepGProp.SurfaceProperties_s(mf.Face(), g)
        p = _tel_nokta(w, 0.05)
        if len(p) < 3:
            continue
        out.append([p, abs(g.Mass()), 0, w])
    out.sort(key=lambda t: -t[1])
    for i, t in enumerate(out):
        q = t[0][0]
        t[2] = sum(1 for u in out[:i] if _icinde(q, u[0]))
    net = sum(t[1] * (-1) ** t[2] for t in out)
    bolge = sum(1 for t in out if t[2] % 2 == 0)
    return out, net, bolge


def _uc_kesimi(istasyon, fark):
    """Dış ölçüsü farklı istasyonlar yalnız UÇLARDA ve alanları uca doğru
    sürekli küçülüyorsa bu açılı / ağız (balık ağzı) kesimdir, kademe
    değil: kısa bir kutunun iki ucu açılı kesilince 9 istasyonun 4'ü
    farklı çıkıyordu. Kademeli milde küçük kesitler kendi aralarında
    EŞİTTİR; o reddedilir."""
    n = len(fark)
    bas = 0
    while bas < n and fark[bas]:
        bas += 1
    son = n
    while son > bas and fark[son - 1]:
        son -= 1
    if any(fark[bas:son]) or son - bas < 3:
        return False                      # ortada farklı istasyon: kademe
    for uc in (istasyon[:bas][::-1], istasyon[son:]):   # ortadan uca doğru
        a = [s_[2] for s_ in uc]
        if any(y >= 0.995 * x for x, y in zip(a, a[1:])):
            return False                  # uca doğru küçülmüyor
    return True


def _dis_olcu(tel):
    """Kesit tellerinin X ve Y aralığı (eksen çerçevesinde)."""
    xs = [q[0] for t in tel for q in t[0]]
    ys = [q[1] for t in tel for q in t[0]]
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), max(xs), min(ys), max(ys))


def _kapali(w):
    from OCP.BRep import BRep_Tool
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS_Vertex
    a, b = TopoDS_Vertex(), TopoDS_Vertex()
    TopExp.Vertices_s(w, a, b)
    if a.IsNull() or b.IsNull():
        return False
    return BRep_Tool.Pnt_s(a).Distance(BRep_Tool.Pnt_s(b)) < 1e-4


def _icinde(q, p):
    """Nokta çokgenin içinde mi (ışın sayma)."""
    x, y = q
    ic = False
    n = len(p)
    for i in range(n):
        x1, y1 = p[i]
        x2, y2 = p[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xk = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xk > x:
                ic = not ic
    return ic


def _tel_nokta(w, sapma=0.02):
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_TangentialDeflection
    p = []
    ex = BRepTools_WireExplorer(w)
    while ex.More():
        e = ex.Current()
        c = BRepAdaptor_Curve(e)
        d = GCPnts_TangentialDeflection(c, sapma, 0.1)
        q = [c.Value(d.Parameter(i)) for i in range(1, d.NbPoints() + 1)]
        q = [(t.X(), t.Y()) for t in q]
        from OCP.TopAbs import TopAbs_REVERSED
        if e.Orientation() == TopAbs_REVERSED:
            q.reverse()
        if p and q and math.dist(p[-1], q[0]) < 1e-6:
            q = q[1:]
        p += q
        ex.Next()
    if len(p) > 1 and math.dist(p[0], p[-1]) < 1e-6:
        p.pop()
    return p


def _alan2(p):
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1]
                     for i in range(len(p)))


def _cevre(p):
    return sum(math.dist(p[i], p[(i + 1) % len(p)]) for i in range(len(p)))


def _ortu(p):
    """Dışbükey örtünün köşe İNDEKSLERİ (monoton zincir), p'nin sırasıyla.
    Noktalar 0,0001 mm'ye yuvarlanır: döndürülmüş parçada aynı doğrudaki
    noktaların x'i 1e-12 oynar, sıralama bozulur, örtü içbükey çıkar."""
    p = [(round(x, 4), round(y, 4)) for x, y in p]
    s = sorted(range(len(p)), key=lambda i: p[i])

    def cap(o, a, b):
        return (p[a][0] - p[o][0]) * (p[b][1] - p[o][1]) - (p[a][1] - p[o][1]) * (p[b][0] - p[o][0])
    alt, ust = [], []
    for i in s:
        while len(alt) >= 2 and cap(alt[-2], alt[-1], i) <= 1e-9:
            alt.pop()
        alt.append(i)
    for i in reversed(s):
        while len(ust) >= 2 and cap(ust[-2], ust[-1], i) <= 1e-9:
            ust.pop()
        ust.append(i)
    return sorted(set(alt[:-1] + ust[:-1]))


def _cepler(p, W, H):
    """Dış çizgi ile dışbükey örtüsü arasındaki cepler:
    [(alan, açıldığı kenar(lar) {'x0','x1','y0','y1'}, ağız, iç genişlik)]"""
    if _alan2(p) < 0:
        p = p[::-1]
    h = _ortu(p)
    n = len(p)
    tol = 0.02 * max(W, H) + 0.05
    out = []
    for a, b in zip(h, h[1:] + h[:1]):
        zincir = [p[(a + k) % n] for k in range(((b - a) % n) + 1)]
        if len(zincir) < 3:
            continue
        A = abs(_alan2(zincir))
        if A <= 0:
            continue
        pa, pb = zincir[0], zincir[-1]

        def yanlar(q):
            return {k for k, v in (("x0", q[0]), ("x1", q[0] - W),
                                   ("y0", q[1]), ("y1", q[1] - H)) if abs(v) < tol}
        # Ağzın iki ucu AYNI kenar üstündeyse cep o kenara açılır (U, C,
        # I'nın yanları): tek kenar. Değilse ağız çaprazdır, cep bir
        # KÖŞEDEDİR (L, T, Z): iki kenar.
        ortak = yanlar(pa) & yanlar(pb)
        kenar = ortak if ortak else (yanlar(pa) | yanlar(pb))
        # Ağız: örtü kenarı üstünde malzemenin BIRAKTIĞI en büyük açıklık
        # (dudaklı C'de dudak uçları arası). İç genişlik: kenar üstünde
        # olmayan noktaların kenar boyunca yayılımı.
        uz = math.dist(pa, pb)
        ux, uy = (pb[0] - pa[0]) / uz, (pb[1] - pa[1]) / uz
        ic_ = []
        agiz, son_ust, disarda = 0.0, 0.0, False
        for q in zincir:
            t_ = (q[0] - pa[0]) * ux + (q[1] - pa[1]) * uy
            d_ = abs((q[0] - pa[0]) * uy - (q[1] - pa[1]) * ux)
            if d_ < 0.2 * tol:
                # çizgiye DÖNÜŞ: ayrıldığı yerle arası açıklıktır; çizgi
                # üstünde yürünen kısım (dolu kenar) açıklık değildir
                if disarda:
                    agiz = max(agiz, abs(t_ - son_ust))
                    disarda = False
                son_ust = t_
            else:
                disarda = True
                ic_.append(t_)
        if agiz == 0.0:
            agiz = uz
        gen = (max(ic_) - min(ic_)) if ic_ else agiz
        don = _donus(zincir)
        # Yan cep kenarın yarısından kısaysa ÇENTİKTİR (girinti, oluk):
        # U'nun cebi kenarın neredeyse tamamını kaplar.
        if len(kenar) == 1:
            yan_boy = H if next(iter(kenar)) in ("x0", "x1") else W
            if gen < 0.5 * yan_boy:
                don = 0.0
        out.append((A, kenar, agiz, gen, don))
    return out


def _donus(zincir):
    """Cebin kenarı boyunca İÇBÜKEY dönüşlerin toplamı (derece). Cebi
    kaç büküm çeviriyor: L 90, U 180 (kolları eşit olmasa da), dudaklı
    C 360. Kanat uçlarındaki dışbükey dönüşler sayılmaz; büküm yayı
    dönüşü parçalara böler, toplamı değiştirmez. Çokgen saat yönünün
    tersine dolaşılır, içbükey dönüş eksi işaretlidir."""
    yon = []
    for a, b in zip(zincir, zincir[1:]):
        if math.dist(a, b) > 1e-6:
            yon.append(math.atan2(b[1] - a[1], b[0] - a[0]))
    t = 0.0
    for a, b in zip(yon, yon[1:]):
        d = (b - a + math.pi) % (2 * math.pi) - math.pi
        if d < 0:
            t -= d
    return math.degrees(t)


def _hizala2_tel(teller):
    """Kesiti, doğru kenarları X/Y'ye paralel olacak açıyla döndürür.
    Açı 1° kovalarda oylanır, sonra kazanan kovadaki kenarların boyca
    ağırlıklı ortalaması alınır (yuvarlanmış açı, döndürülmüş parçada
    30 mm'lik kenarı 30,1 gösteriyordu)."""
    kenar = []
    for w in teller:
        for u, d in _cizgi_kenarlari(w):
            kenar.append((u, math.degrees(math.atan2(d[1], d[0])) % 90.0))
    if not kenar:
        return 0.0
    toplam = {}
    for u, a in kenar:
        k = round(a) % 90
        toplam[k] = toplam.get(k, 0.0) + u
    en = max(toplam.items(), key=lambda t: t[1])[0]
    pay, ag = 0.0, 0.0
    for u, a in kenar:
        f = (a - en + 45.0) % 90.0 - 45.0
        if abs(f) <= 1.0:
            pay += u * f
            ag += u
    return math.radians(en + (pay / ag if ag else 0.0))


def _m(v):
    return XL.tr(v, 1)


def profil(sh, hacim=None):
    """Profil ise sözlük, değilse None:
    {"tur": "kutu", "ad": "kutu profil 30x50x2", "kesit": "30x50x2",
     "boy": 1854.0, "alan": 304.0, "gerekce": "..."}"""
    try:
        return _profil(sh, hacim)
    except Exception:
        return None


def _profil(sh, V):
    if V is None:
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(sh, g)
        V = g.Mass()
    if V <= 1e-6:
        return None
    yz = _yuzler(sh)
    for d in _eksen_adaylari(sh, yz):
        if not _yanal_baskin(yz, d):
            continue
        r = _profil_eksen(sh, V, d)
        if r:
            return r
    return None


def _yanal_baskin(yz, d):
    """Ucuz ön eleme (kesit almadan): profilin yüzey alanının çoğu eksene
    PARALEL yüzlerdir (normali eksene dik düzlem, ekseni eksene paralel
    silindir). Delikler ve uç yüzler payı düşürür ama %60'ın altına
    indirmez; döküm / işlenmiş parçada pay küçüktür, kesit hiç alınmaz."""
    top, yan = 0.0, 0.0
    for y in yz:
        top += y["alan"]
        if y["tip"] == "duz" and _dik(y["n"], d):
            yan += y["alan"]
        elif y["tip"] in ("silindir", "koni") and _paralel(y["d"], d):
            yan += y["alan"]
        elif y["tip"] == "diger" and _serbest_yanal(y["f"], d):
            yan += y["alan"]
    return top > 0 and yan >= 0.6 * top


def _serbest_yanal(f, d):
    """Serbest (B-spline) yüz eksene paralel mi: 9 noktada normal eksene
    dik. Bazı CAD'ler ekstrüzyon profilin yanlarını B-spline yazar
    (tente kompleksindeki 1515 mm ray)."""
    s = BRepAdaptor_Surface(f)
    u0, u1 = s.FirstUParameter(), s.LastUParameter()
    v0, v1 = s.FirstVParameter(), s.LastVParameter()
    if not all(math.isfinite(x) for x in (u0, u1, v0, v1)):
        return False
    bf = BRepGProp_Face(f)
    p, n = gp_Pnt(), gp_Vec()
    for a in (0.1, 0.5, 0.9):
        for b in (0.1, 0.5, 0.9):
            bf.Normal(u0 + a * (u1 - u0), v0 + b * (v1 - v0), p, n)
            m = n.Magnitude()
            if m < 1e-12 or abs(n.X() * d[0] + n.Y() * d[1] + n.Z() * d[2]) / m > math.sin(ACI_TOL):
                return False
    return True


def _profil_eksen(sh, V, d):
    t = _eksene_tasi(sh, (0.0, 0.0, 0.0), d)
    kb = _kutu(t)
    L = kb[5] - kb[2]
    B = max(kb[3] - kb[0], kb[4] - kb[1])
    if L <= 0 or B <= 0 or L < PROFIL_NARIN * B:
        return None
    istasyon = []
    for i in range(PROFIL_ISTASYON):
        z = kb[2] + L * (0.08 + 0.84 * i / (PROFIL_ISTASYON - 1))
        tel, net, bolge = _kesit(t, z)
        istasyon.append((z, tel, net, bolge))
    # Kesit alanı: en çok tekrarlanan alan. Delikler ve kesilmiş yerler
    # kesiti yalnız KÜÇÜLTÜR; hiçbir istasyon ondan büyük olamaz (olursa
    # parça sabit kesitli değildir: flanşlı, çıkıntılı, kademeli).
    alanlar = [s_[2] for s_ in istasyon if s_[2] > 0]
    if not alanlar:
        return None
    A = max(alanlar, key=lambda a: (sum(abs(b - a) <= 0.005 * a for b in alanlar), a))
    ayni = [s_ for s_ in istasyon if abs(s_[2] - A) <= 0.005 * A and s_[3] == 1]
    if len(ayni) < 4 or max(alanlar) > 1.01 * A:
        return None
    # Delik kesitin İÇİNİ boşaltır, DIŞ ölçüsünü değiştirmez. Küçük
    # kesitlerin dış ölçüsü de küçülmüşse parça kademelidir (kademeli
    # mil, boyunlu parça): profil değil. Uçlardaki kertik için 2 istasyon
    # pay bırakılır.
    ref = _dis_olcu(ayni[len(ayni) // 2][1])
    tol = 0.01 * max(ref[1] - ref[0], ref[3] - ref[2]) + 0.05
    fark = [not s_[1] or any(abs(a - b) > tol for a, b in zip(_dis_olcu(s_[1]), ref))
            for s_ in istasyon]
    if sum(fark) > 2 and not _uc_kesimi(istasyon, fark):
        return None
    # hacim / (kesit x boy): delik ve gönye kesimi düşürür
    dolu = V / (A * L)
    if not 0.60 <= dolu <= 1.02:
        return None
    # ortanca kesit: tek bölge (iki ayrı parça yan yana değil)
    z, tel, _a, _b = ayni[len(ayni) // 2]
    dis_t = [u for u in tel if u[2] == 0][0]
    ic_t = [u for u in tel if u[2] == 1]
    aci = _hizala2_tel([u[3] for u in tel])
    c, s_ = math.cos(-aci), math.sin(-aci)

    def don(p):
        return [(x * c - y * s_, x * s_ + y * c) for x, y in p]
    dis = don(dis_t[0])
    ic = [don(u[0]) for u in ic_t]
    ada = any(u[2] >= 2 for u in tel)     # boşluğun içinde ada: özel kesit
    x0 = min(q[0] for q in dis)
    y0 = min(q[1] for q in dis)
    dis = [(x - x0, y - y0) for x, y in dis]
    ic = [[(x - x0, y - y0) for x, y in p] for p in ic]
    W = max(q[0] for q in dis)
    H = max(q[1] for q in dis)
    Ad = abs(_alan2(dis))                 # dış çizginin içi (boşluk dahil)
    P = _cevre(dis)
    a, b = sorted((W, H))
    boy = L
    temel = {"boy": round(boy, 1), "alan": round(A, 1), "W": round(W, 2),
             "H": round(H, 2), "dolu": round(dolu, 3)}
    gerekce = (f"{len(ayni)}/{PROFIL_ISTASYON} kesit aynı ({_m(A)} mm²), "
               f"hacim/(kesit x boy) = {dolu:.2f}")

    def sonuc(tur, ad, kesit, **ek):
        r = dict(temel, tur=tur, ad=ad, kesit=kesit,
                 gerekce=f"{ad}: {gerekce}")
        r.update(ek)
        return r

    daire = abs(W - H) < 0.02 * W and abs(Ad - math.pi * W * H / 4) < 0.02 * Ad
    dikdortgen = Ad >= 0.93 * W * H
    buyuk_ic = [p for p in ic if abs(_alan2(p)) > 0.02 * Ad]
    cep_var = bool([c_ for c_ in _cepler(dis, W, H) if c_[0] > 0.03 * W * H])
    if len(buyuk_ic) == 1 and len(ic) == 1 and not ada and not cep_var:
        p = buyuk_ic[0]
        wi = max(q[0] for q in p) - min(q[0] for q in p)
        hi = max(q[1] for q in p) - min(q[1] for q in p)
        xi = (max(q[0] for q in p) + min(q[0] for q in p)) / 2
        yi = (max(q[1] for q in p) + min(q[1] for q in p)) / 2
        Ai = abs(_alan2(p))
        ortali = abs(xi - W / 2) < 0.02 * W + 0.05 and abs(yi - H / 2) < 0.02 * H + 0.05
        ic_daire = abs(wi - hi) < 0.02 * wi and abs(Ai - math.pi * wi * hi / 4) < 0.02 * Ai
        ic_dik = Ai >= 0.93 * wi * hi
        esit_cidar = abs((W - wi) - (H - hi)) <= 0.1 * max(W - wi, H - hi) + 0.05
        if not (ortali and esit_cidar and ((daire and ic_daire) or (dikdortgen and ic_dik))):
            buyuk_ic = None               # iç boşluk dış biçime uymuyor: özel kesit
    if buyuk_ic and len(buyuk_ic) == 1 and len(ic) == 1 and not ada and not cep_var:
        if daire:
            et = (W - wi) / 2
            return sonuc("boru", f"boru Ø{_m(W)}x{_m(et)}", f"Ø{_m(W)}x{_m(et)}",
                         et=round(et, 2))
        if dikdortgen:
            et = ((W - wi) + (H - hi)) / 4
            tur = "kare kutu" if abs(W - H) < 0.02 * W else "kutu"
            k = f"{_m(a)}x{_m(b)}x{_m(et)}"
            return sonuc(tur, f"{tur} profil {k}", k, et=round(et, 2))
    if not ic:
        if daire:
            return sonuc("mil", f"mil Ø{_m(W)}", f"Ø{_m(W)}")
        if dikdortgen:
            if b >= 2.5 * a:
                return sonuc("lama", f"lama {_m(b)}x{_m(a)}", f"{_m(b)}x{_m(a)}")
            if abs(W - H) < 0.02 * W:
                return sonuc("kare çubuk", f"kare çubuk {_m(a)}x{_m(a)}", f"{_m(a)}x{_m(a)}")
            return sonuc("dolu çubuk", f"dolu çubuk {_m(b)}x{_m(a)}", f"{_m(b)}x{_m(a)}")
        cep = [c_ for c_ in _cepler(dis, W, H) if c_[0] > 0.03 * W * H]
        # ince cidarlı açık kesit: 2t² - P t + 2A = 0
        disk = P * P - 16 * A
        et = (P - math.sqrt(disk)) / 4 if disk > 0 else None
        ince = et is not None and et <= 0.25 * a
        k = f"{_m(b)}x{_m(a)}" + (f"x{_m(et)}" if ince else "")
        tur = None
        # çentik (kenarın küçük bir kısmındaki girinti, dönüşü 0 sayılır)
        # türü belirlemez ama kesiti özel yapar
        centik = [c_ for c_ in cep if c_[4] < 45]
        ana = [c_ for c_ in cep if c_[4] >= 45]
        # temiz biçim: dönüş tam 90 (bir büküm) ya da 180 (iki büküm);
        # arada kalan (45° pah, oluklu sac) özel kesittir
        d90 = [c_ for c_ in ana if 75 <= c_[4] <= 105]
        d180 = [c_ for c_ in ana if 160 <= c_[4] <= 200]
        if centik:
            tur = None
        elif len(ana) == 1 and d90:
            tur = "köşebent (L)"
            k = f"{_m(W)}x{_m(H)}" + (f"x{_m(et)}" if ince else "")
        elif len(ana) == 1 and len(ana[0][1]) == 1 and (d180 or 340 <= ana[0][4] <= 380):
            # dudaklı C: dudaklar iki büküm daha ekler (360) ya da ağız
            # (dudak uçları arası) cebin içinden dardır. C ve U'nun cebi
            # TEK kenara açılır; köşeye açılan 360° oluklu sactır.
            c_ = ana[0]
            tur = "C profil" if (c_[4] >= 340 or c_[2] < 0.85 * c_[3]) else "U profil"
        elif len(ana) == 1 and d180:
            tur = "U profil"          # kolları eşit olmayan U: ağız çapraz
        elif len(ana) == 2 and len(d180) == 2 and all(len(c_[1]) == 1 for c_ in d180):
            if {next(iter(d180[0][1])), next(iter(d180[1][1]))} in ({"x0", "x1"}, {"y0", "y1"}):
                tur = "I/H profil"
        elif len(ana) == 2 and len(d90) == 2:
            tur = "T profil" if d90[0][1] & d90[1][1] else "Z profil"
        if tur and ince:
            return sonuc(tur.split(" (")[0], f"{tur} {k}", k, et=round(et, 2))
        if tur:
            return sonuc(tur.split(" (")[0], f"{tur} {k}", k)
    # geri kalan: çok boşluklu / girintili kesit (alüminyum ekstrüzyon vb.)
    # Şekil kalıbı yerine YAPISI sayılır: kapalı hücre, T-kanal (ağzı
    # içinden dar oluk), açık oluk, vida kanalı (küçük yuvarlak delik).
    k = f"{_m(b)}x{_m(a)}"
    y = kesit_yapisi(dis, ic, W, H)
    kenar = 0
    for u in tel:
        ex = TopExp_Explorer(u[3], TopAbs_EDGE)
        while ex.More():
            kenar += 1
            ex.Next()
    y["kenar"] = kenar
    parca_ = []
    if y["hucre"]:
        parca_.append(f"{y['hucre']} hücre")
    if y["t_kanal"]:
        parca_.append(f"{y['t_kanal']} T-kanal")
    if y["oluk"]:
        parca_.append(f"{y['oluk']} oluk")
    if y["vida"]:
        parca_.append(f"{y['vida']} vida kanalı")
    # Üretim yöntemi kesitin KARMAŞIKLIĞINDAN: içi çok şekilli kesit
    # (birden çok hücre / kanal / oluk / vida kanalı ya da 24'ten çok
    # kenar) ekstrüzyondur; tek ya da birkaç düz öğeli özel kesit
    # genellikle kalıp, dövme ya da bükmedir.
    karmasik = (y["hucre"] + y["t_kanal"] + y["oluk"] + y["vida"] >= 2
                or y["t_kanal"] or y["vida"] or kenar >= 24)
    y["yontem"] = "ekstrüzyon" if karmasik else "kalıp / dövme / bükme"
    if y["t_kanal"] >= 2 and abs(W - H) < 0.05 * max(W, H):
        ad = "sigma (T-kanallı) ekstrüzyon profil"
    elif karmasik:
        ad = "ekstrüzyon profil"
    else:
        ad = "özel kesit profil"
        parca_.append("basit kesit: kalıp / dövme / bükme")
    return sonuc("ekstrüzyon" if karmasik else "özel kesit",
                 f"{ad} {k}" + (f" ({', '.join(parca_)})" if parca_ else ""),
                 k, yapi=y)


def kesit_yapisi(dis, ic, W, H):
    """Kesitin yapısal öğeleri: kapalı hücre (büyük iç boşluk), vida
    kanalı (küçük, yuvarlağa yakın iç boşluk: Ø2-10), T-kanal (dış
    çizgideki ağzı içinden dar cep), oluk (ağzı açık cep)."""
    Ad = abs(_alan2(dis)) or 1.0
    hucre = vida = 0
    for p in ic:
        A = abs(_alan2(p))
        xs = [q[0] for q in p]
        ys = [q[1] for q in p]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        daire = w > 0 and abs(w - h) < 0.15 * w and A > 0.6 * w * h
        if daire and 1.5 <= w <= 12.0 and A < 0.05 * Ad:
            vida += 1
        elif A > 0.01 * Ad:
            hucre += 1
    t_kanal = oluk = 0
    for c_ in _cepler(dis, W, H):
        if c_[0] < 0.005 * W * H:
            continue
        if c_[2] < 0.85 * c_[3]:
            t_kanal += 1
        elif c_[2] < 0.5 * max(W, H):
            oluk += 1
    return {"hucre": hucre, "vida": vida, "t_kanal": t_kanal, "oluk": oluk}


# ================================================== DÖNEL PARÇA: IŞINLA
# Yüz tiplerine bakan _donel "temiz" modeli tanır. Diş açılmış, tırtıllı
# ya da CAD'in serbest yüzle (B-spline) modellediği parçada yüzler
# silindir değildir; _donel emin olamaz. Burada parçanın kendisi
# ÖLÇÜLÜR: eksen boyunca 48 kotta, eksenden 8 yöne ışın atılır; her
# kotta iç yarıçap (delik), dış yarıçap ve dış yarıçapın yöne göre
# değişimi (altıgen: en büyük / en küçük = 1,155) bulunur. Diş ve tırtıl
# yarıçapı birkaç onda bir oynatır, biçimi değiştirmez.
ISIN_KOT = 48
ISIN_YON = tuple(7.5 * i for i in range(8))      # 0 - 52,5°: altıgen ve kare


def meridyen(t):
    """Eksen Z'de, orijinden geçen katı için [(z, r_ic, r_dis_min,
    r_dis_max)]. r_ic = 0: eksen malzemenin içinde (dolu)."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin
    kb = _kutu(t)
    z0, z1 = kb[2], kb[5]
    R = 2.0 * max(abs(v) for v in (kb[0], kb[1], kb[3], kb[4])) + 1.0
    it = IntCurvesFace_ShapeIntersector()
    it.Load(t, 1e-6)
    out = []
    for i in range(ISIN_KOT):
        z = z0 + (z1 - z0) * (i + 0.5) / ISIN_KOT
        ic, dis = [], []
        for a in ISIN_YON:
            c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
            it.Perform(gp_Lin(gp_Pnt(0.0, 0.0, z), gp_Dir(c, s, 0.0)), 0.0, R)
            p = sorted(it.WParameter(k) for k in range(1, it.NbPnt() + 1))
            p = [x for j, x in enumerate(p) if j == 0 or x - p[j - 1] > 1e-6]
            if not p:
                ic.append(None)
                dis.append(0.0)
                continue
            ic.append(0.0 if len(p) % 2 else p[0])
            dis.append(p[-1])
        if any(x is None for x in ic):
            out.append((z - z0, None, 0.0, 0.0))
            continue
        ic.sort()
        out.append((z - z0, ic[len(ic) // 2], min(dis), max(dis)))
    return z1 - z0, out


def _donel_isin(sh, eksen):
    o, d = eksen
    t = _eksene_tasi(sh, o, d)
    H, m = meridyen(t)
    if H <= 0 or any(r[1] is None for r in m):
        return None                      # bir kotta malzeme yok: dönel değil
    n = len(m)

    def f(v):
        return XL.tr(v, 1, sade=False)
    Dmax = 2 * max(r[3] for r in m)
    if Dmax > 60 or Dmax <= 0:
        return None
    # dış biçim: kotta en büyük / en küçük dış yarıçap
    oran = [r[3] / r[2] if r[2] > 0 else 9 for r in m]

    def bicim(q):
        if q < 1.04:
            return "yuvarlak"
        if 1.12 <= q <= 1.19:
            return "altıgen"
        if 1.35 <= q <= 1.45:
            return "kare"
        return "?"
    bic = [bicim(q) for q in oran]
    delikli = [r[1] > 0 for r in m]
    # --- baş: bir uçta, gövdeden belirgin geniş kotlar
    govde_r = sorted(r[3] for r in m)[n // 2]
    bas_uc = None
    for uc, sira in (("alt", list(range(n))), ("ust", list(range(n - 1, -1, -1)))):
        # Kubbe (mercimek) başın tepesi gövdeden dardır: uçta yarıçapı
        # BÜYÜYEREK genişleyen kotlar başa sayılır (en çok boyun %12'si).
        # ISO 7380 M8'de tepe Ø5,5, gövde Ø8, baş Ø14: eskiden baş hiç
        # bulunmuyordu.
        j = 0
        while (j < len(sira) - 1 and j < 0.12 * n and m[sira[j]][3] < 1.08 * govde_r
               and m[sira[j + 1]][3] >= m[sira[j]][3]):
            j += 1
        if j and m[sira[j]][3] < 1.08 * govde_r:
            j = 0
        k = j
        for i in sira[j:]:
            if m[i][3] >= 1.08 * govde_r:
                k += 1
            else:
                break
        if j < k <= 0.3 * n:
            if bas_uc is None or k > bas_uc[1]:
                bas_uc = (uc, k)
    # gövde kotları: baş dışındakiler (uçtaki pah kotları hariç)
    if bas_uc:
        bas = list(range(bas_uc[1])) if bas_uc[0] == "alt" else list(range(n - bas_uc[1], n))
    else:
        bas = []
    govde = [i for i in range(n) if i not in bas]
    if len(govde) < 0.5 * n:
        return None
    # uçlardaki pah kotlarını ayıkla: gövdenin ortanca dış yarıçapından
    # %8'den fazla küçük kotlar
    gr = sorted(m[i][3] for i in govde)[len(govde) // 2]
    govde_ic = [i for i in govde if m[i][3] >= 0.92 * gr]
    if len(govde_ic) < 0.4 * n:
        return None
    gbic = max(set(bic[i] for i in govde_ic), key=lambda b: sum(bic[i] == b for i in govde_ic))
    if sum(bic[i] == gbic for i in govde_ic) < 0.8 * len(govde_ic) or gbic == "?":
        return None
    Hb = H * len(bas) / n
    Lg = H - Hb
    Dg = 2 * gr

    # --- SOMUN (diş modelli): başsız, altıgen/kare, boydan boya delik
    if not bas and all(delikli) and gbic in ("altıgen", "kare"):
        s_ = 2 * min(m[i][2] for i in govde_ic)           # anahtar ağzı
        dr = 2 * sorted(m[i][1] for i in govde_ic)[len(govde_ic) // 2]
        # Yükseklik en az 0,45 d: ince somun (DIN 439) 0,5 d. Daha yassı
        # altıgen/kare delikli parça bir PLAKADIR (kaynaklı kasada 24x24x3,
        # Ø11 delikli bağlantı braketi kare somun sanılıyordu).
        if 1.3 <= s_ / dr <= 2.6 and 0.45 <= H / dr <= 1.6:
            return ("standart", "somun",
                    f"somun: {gbic} (ışın ölçümü), anahtar ağzı {f(s_)}, "
                    f"delik Ø{f(dr)}, yükseklik {f(H)}")
        return None
    if not bas:
        return None
    Db = 2 * max(m[i][3] for i in bas)
    bas_delik = all(delikli[i] for i in bas)
    govde_delik = [delikli[i] for i in govde]

    # --- PERÇİN SOMUN: başlı, ince cidarlı burç; delik baştan girer.
    # Delik ya boydan boya ya da (kapalı uçlu tipte) baştan başlayıp
    # gövdenin en az yarısına iner. Ayırıcı imza: deliğin BAŞ TARAFI
    # geniş (sıkışma bölgesi), uç tarafı dar (dişli kısım) - ya da
    # gövde altıgen / tırtıllı (yuvarlak değil).
    if bas_delik and Db <= 2.2 * Dg and Hb <= 0.25 * H and Lg >= 0.8 * Dg:
        sira = govde if bas_uc[0] == "alt" else govde[::-1]   # baştan uca
        delik_boy = 0
        for i in sira:
            if delikli[i]:
                delik_boy += 1
            else:
                break
        acik = delik_boy == len(sira)
        if delik_boy >= 0.5 * len(sira) and all(not delikli[i] for i in sira[delik_boy:]):
            ri = [m[i][1] for i in sira[:delik_boy]]
            yakin = sorted(ri[: max(1, len(ri) // 4)])[0]
            uzak = sorted(ri[-max(1, len(ri) // 3):])[len(ri[-max(1, len(ri) // 3):]) // 2]
            cidar = uzak / gr
            kademeli = yakin >= 1.08 * uzak
            if 0.45 <= cidar <= 0.85 and (kademeli or gbic != "yuvarlak"):
                return ("standart", "perçin somun",
                        f"perçin somun: baş Ø{f(Db)}, gövde Ø{f(Dg)} ({gbic}) x {f(Lg)}, "
                        f"delik Ø{f(2 * uzak)}"
                        + (f" / baş tarafı Ø{f(2 * yakin)}" if kademeli else "")
                        + ("" if acik else ", kapalı uçlu"))
        return None

    # --- CIVATA (diş modelli): baş bir uçta, gövde dolu ve başa göre ince
    # Baş, gövde çapının 1,4 - 2,6 katı ve en çok 1,2 d yüksekliğinde
    # (imbus başı 1 d, altıgen 0,7 d). Daha iri "baş" başka bir şeydir:
    # saplamalı kauçuk takoz (Ø30 kauçuk + M8 saplama) cıvata sanılıyordu.
    if (not any(govde_delik) and Lg >= Dg and 1.4 * Dg <= Db <= 2.6 * Dg
            and Hb <= min(0.5 * H, 1.2 * Dg)):
        bb = max(set(bic[i] for i in bas), key=lambda b: sum(bic[i] == b for i in bas))
        # başın gövdeden tepeye yarıçap dizisi: tepe daralıyorsa mercimek
        # (kubbe, ISO 7380), gövde tarafı darsa havşa, düzse silindirik
        rs = [m[i][3] for i in (bas if bas_uc[0] == "ust" else bas[::-1])]
        yuvarlak_tur = ("kubbe baş" if rs[-1] < 0.8 * max(rs) else
                        "havşa baş" if rs[0] < 0.8 * max(rs) else "silindirik baş")
        tur = {"altıgen": "altıgen baş", "kare": "kare baş"}.get(bb, yuvarlak_tur)
        if bb in ("altıgen", "kare") or (bb == "yuvarlak" and gbic == "yuvarlak"):
            return ("standart", "civata",
                    f"cıvata: {tur} Ø{f(Db)}, gövde Ø{f(Dg)} x {f(Lg)} (ışın ölçümü)")
    return None


# ================================================ BİÇİM İMZASI (öğrenme)
# Kullanıcı bir parçanın sınıfını bir kez düzeltince BENZERLERİ de o
# sınıfa geçsin: M6 perçin somunu gösterilince M4 - M10 da tanınsın,
# ama delikli bir plaka "somun" olmasın. İmza ölçekten bağımsızdır
# (boyut değil ORAN) ve parçanın duruşundan bağımsızdır (eylemsizlik):
#   y   yüz sayısı (aynı tedarikçinin aynı ailesinde aynıdır)
#   t   yüz tiplerinin alan payı: düz, silindir, koni, küre, tor, diğer
#   g   dönme yarıçaplarının oranı (en küçük / en büyük, orta / en büyük)
#   k   yoğunluk: hacim / (yüzey alanı ^ 1,5)
# İki imza "benzer": yüz sayısı aynı, her oran ve pay 0,08 içinde,
# yoğunluk %25 içinde.
IMZA_TOL = 0.08


def bicim_imzasi(sh):
    try:
        yz = _yuzler(sh)
        if not yz:
            return None
        top = sum(y["alan"] for y in yz)
        pay = {}
        for y in yz:
            pay[y["tip"]] = pay.get(y["tip"], 0.0) + y["alan"] / top
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(sh, g)
        V = g.Mass()
        if V <= 1e-9:
            return None
        I = sorted(g.PrincipalProperties().Moments())
        r = [math.sqrt(max(i, 0.0) / V) for i in I]
        return {"y": len(yz),
                "t": [round(pay.get(t, 0.0), 3) for t in
                      ("duz", "silindir", "koni", "kure", "tor", "diger")],
                "g": [round(r[0] / r[2], 3), round(r[1] / r[2], 3)],
                "k": round(V / top ** 1.5, 4)}
    except Exception:
        return None


def benzer(a, b, tol=IMZA_TOL):
    if not a or not b or a.get("y") != b.get("y"):
        return False
    for x, y in zip(a["t"] + a["g"], b["t"] + b["g"]):
        if abs(x - y) > tol:
            return False
    # Yoğunluk aile içinde daha çok oynar (M6 perçin somunda cidar / çap
    # 0,33, M8'de 0,27): %25 pay.
    return abs(a["k"] - b["k"]) <= 0.25 * max(a["k"], b["k"])


# ================================================ SATIN ALINAN ADAYI
# Cıvata, somun, pul, yay, rulman, pim, segman... tipleri saymakla
# bitmez. Tek tek imza yerine SATIN ALINAN ELEMANIN GENEL İŞARETLERİNE
# bakılır; işaretler KARAR DEĞİLDİR, "standart tanımı kontrol" listesine
# gerekçesiyle düşer (tasarımcı düzeltir ya da onaylar).
ADAY_EN_BUYUK = 100.0              # bundan büyük parça aday sayılmaz (mm)


def donel_mi(sh):
    """Parça bir eksen çevresinde dönel (ya da altıgen/kare prizma) mı:
    ışınla ölçülür, diş ve tırtıl sonucu değiştirmez.
    Döner: (eksen, serbest yüz payı) ya da None."""
    yz = _yuzler(sh)
    if not yz:
        return None
    top = sum(y["alan"] for y in yz)
    serbest = sum(y["alan"] for y in yz if y["tip"] == "diger") / top
    adaylar = [e for e in (_ana_eksen(yz), _simetri_ekseni(sh)) if e]
    for o, d in adaylar:
        t = _eksene_tasi(sh, o, d)
        H, m = meridyen(t)
        if H <= 0 or any(r[1] is None for r in m):
            continue
        iyi = sum(1 for r in m if r[2] > 0 and (r[3] / r[2] < 1.04
                                               or 1.12 <= r[3] / r[2] <= 1.19
                                               or 1.35 <= r[3] / r[2] <= 1.45))
        if iyi >= 0.9 * len(m):
            return (o, d), serbest
    return None


def yay_mi(sh, V):
    """Helis yay biçimi: simetri ekseni var, eksen boyunca içi boş, katı
    kapladığı silindirin %35'inden azını doldurur ve dönel DEĞİLDİR
    (tel her yönde başka yükseklikte)."""
    e = _simetri_ekseni(sh)
    if not e:
        return None
    t = _eksene_tasi(sh, *e)
    kb = _kutu(t)
    H = kb[5] - kb[2]
    R = max(abs(v) for v in (kb[0], kb[1], kb[3], kb[4]))
    if H <= 0 or R <= 0:
        return None
    dol = V / (math.pi * R * R * H)
    if dol >= 0.35 or not _eksen_bos(t, kb[2], H):
        return None
    _H, m = meridyen(t)
    eksik = sum(1 for r in m if r[1] is None)
    if eksik < 0.3 * len(m):
        return None
    return f"helis yay biçimi: Ø{XL.tr(2 * R, 1)} x {XL.tr(H, 1)}, doluluk %{100 * dol:.0f}"


def aday_isaretleri(sh, V=None):
    """Biçimden gelen işaretler: [(anahtar, gerekçe)]."""
    try:
        if V is None:
            g = GProp_GProps()
            BRepGProp.VolumeProperties_s(sh, g)
            V = g.Mass()
        kb = _kutu(sh)
        B = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2])
        if B > ADAY_EN_BUYUK or V <= 0:
            return []
        out = []
        try:
            import pf11_yapi as Y
            if Y.yay_olabilir(sh, V):
                yy = Y.yay(sh, V)
                if yy:
                    return [("yay", f"{yy[1]}{'' if yy[3] else '?'} ({yy[2]})")]
        except Exception:
            pass
        try:
            import pf13_aile as A
            a = A.aile_tani(sh)
            if a and not a[3]:
                out.append(("aile", f"{a[1]}? ({a[2]})"))
        except Exception:
            pass
        try:
            import pf11_yapi as Y
            y = Y.yapisal_tani(sh) if B <= YAPI_EN_BUYUK else None
            if y and not y[3]:
                out.append(("yapi", f"{y[1]}? ({y[2]})"))
            bc = Y.bukulmus_cubuk(sh)
            if bc:
                out.append(("bukulmus", f"{bc[0]}: {bc[1]}"))
        except Exception:
            pass
        d = donel_mi(sh)
        if d:
            out.append(("donel", f"dönel küçük parça (en büyük ölçü {B:.0f} mm)"))
            if d[1] >= 0.2:
                out.append(("dis", "diş / helis / tırtıl modelli (serbest yüz "
                                   f"%{100 * d[1]:.0f})"))
        else:
            y = yay_mi(sh, V)
            if y:
                out.append(("yay", y))
        return out
    except Exception:
        return []


# ================================================ GÖRÜNTÜ (AI için)
def parca_png(sh, boyut=512):
    """Parçanın gölgelendirilmiş resmi (PNG baytları): sol yarıda eş
    ölçülü (izometrik) görünüş, sağ yarıda en uzun eksen boyunca bakış.
    AI'a "bu ne" diye sormak için: biçim, delik, baş, diş görünür.
    Ölçek çubuğu yazılır (mm)."""
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopAbs import TopAbs_REVERSED
    kb = _kutu(sh)
    B = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]) or 1.0
    BRepMesh_IncrementalMesh(sh, B / 150.0, False, 0.3, True)
    ucg = []
    ex = TopExp_Explorer(sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        loc = TopLoc_Location()
        t = BRep_Tool.Triangulation_s(f, loc)
        if t is None:
            continue
        tr = loc.Transformation()
        pts = [t.Node(i).Transformed(tr) for i in range(1, t.NbNodes() + 1)]
        ters = f.Orientation() == TopAbs_REVERSED
        for i in range(1, t.NbTriangles() + 1):
            a, b, c = t.Triangle(i).Get()
            if ters:
                b, c = c, b
            ucg.append([(pts[j - 1].X(), pts[j - 1].Y(), pts[j - 1].Z()) for j in (a, b, c)])
        if len(ucg) > 60000:
            break
    if not ucg:
        return None
    isik = (0.4, -0.5, 0.75)

    def renk(u):
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = u
        n = ((y1 - y0) * (z2 - z0) - (z1 - z0) * (y2 - y0),
             (z1 - z0) * (x2 - x0) - (x1 - x0) * (z2 - z0),
             (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0))
        m = math.sqrt(sum(v * v for v in n)) or 1.0
        k = abs(sum(n[i] * isik[i] for i in range(3))) / m / math.sqrt(sum(v * v for v in isik))
        g = 0.35 + 0.6 * k
        return (0.55 * g, 0.62 * g, 0.72 * g)
    renkler = [renk(u) for u in ucg]
    orta = ((kb[0] + kb[3]) / 2, (kb[1] + kb[4]) / 2, (kb[2] + kb[5]) / 2)
    uz = [kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]]
    en_uzun = uz.index(max(uz))
    bakis = [(30, -60), {0: (0, 0), 1: (0, -90), 2: (90, -90)}[en_uzun]]
    fig = plt.figure(figsize=(2 * boyut / 100, boyut / 100), dpi=100)
    for j, (el, az) in enumerate(bakis):
        ax = fig.add_subplot(1, 2, j + 1, projection="3d")
        ax.add_collection3d(Poly3DCollection(ucg, facecolors=renkler, edgecolors="none"))
        for eks, o in zip("xyz", orta):
            getattr(ax, f"set_{eks}lim")(o - B / 2, o + B / 2)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=el, azim=az)
        ax.set_axis_off()
    fig.suptitle(f"ölçü {XL.tr(uz[0], 1)} x {XL.tr(uz[1], 1)} x {XL.tr(uz[2], 1)} mm",
                 fontsize=10)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=0.92, wspace=0)
    bio = io.BytesIO()
    fig.savefig(bio, format="png", facecolor="white")
    plt.close(fig)
    return bio.getvalue()
