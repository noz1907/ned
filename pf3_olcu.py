"""
PiFikstur – ADIM 0 : STEP'TEN ÇİZİM VE ÖLÇÜ ÇIKARMA
====================================================
Herhangi bir STEP dosyasından, montaj ve komponent bazında DXF görünüşleri ve
ölçü tablosu üretir. Civata, somun, pul gibi standart elemanlar için çizim
üretilmez; yalnız kodu ve adedi listelenir.

    python pf3_olcu.py parca.stp
    python pf3_olcu.py parca.stp -o cikti --en-az-hacim 50
    python pf3_olcu.py parca.stp --liste            # yalnız komponent listesi

Çıktılar (-o klasörü):
    00_MONTAJ.dxf          montajın ÖN / ÜST / SAĞ görünüşü + genel ölçüler
    K01_<ad>.dxf           her komponent için 3 görünüş + ölçüler + delik tablosu
    olculer.csv            tüm komponentlerin ölçü tablosu (Excel'de açılır)
    olculer.json           aynı veri, makine okunur
    rapor.md               okunabilir rapor + standart eleman listesi

Ölçüler komponentin KENDİ eksenlerine göre verilir: en büyük düz yüzeyin
normali kalınlık ekseni, o yüzeydeki en uzun kenar yönü boy eksenidir. Böylece
montaj içinde eğik duran bir sac da kendi boy/en/kalınlık ölçüsüyle çıkar.
"""
from __future__ import annotations
import argparse, csv, json, math, os, re, sys, time
from collections import Counter, defaultdict

import cadquery as cq
import ezdxf

from OCP.gp import gp_Pnt, gp_Dir, gp_Trsf, gp_Ax2, gp_Vec
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_REVERSED
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.GCPnts import GCPnts_TangentialDeflection

import pf1_referans as E

RHO = 7.85e-6          # kg/mm3 (çelik); --yogunluk ile değiştirilir

# ---------------------------------------------------------------- standart eleman
# Bu desenlere uyan parçalar için çizim üretilmez, sadece kod + adet listelenir.
STANDART = [
    (r"\bDIN\s*\d+", "DIN"), (r"\bISO\s*\d+", "ISO"), (r"\bEN\s*\d{3,}", "EN"),
    (r"civata|cıvata|bolt|screw|schraube", "civata"),
    (r"\bsomun\b|\bnut\b|mutter", "somun"),
    (r"\bpul\b|rondela|washer|scheibe|unterlegscheibe", "pul"),
    (r"percin|perçin|rivet|niet", "perçin"),
    (r"\bpim\b|bolzen|\bpin\b|\bmil\b", "pim"),
    (r"\byay\b|\bfeder\b|spring|druckfeder|zugfeder", "yay"),
    (r"rulman|lager|bearing|kugellager", "rulman"),
    (r"segman|sicherung|circlip|seeger", "segman"),
    (r"saplama|stud|gewindestift", "saplama"),
]
# Kaynak dikişleri de ayrı tutulur (parça değildir).
# Dikkat: "naht" serbest bırakılırsa "Anahtar" gibi kelimelere takılır;
# sözcük sonuna sabitlenir.
KAYNAK = r"kehlnaht|naht\b|kaynak|weld|\bseam\b|diki[sş]"


def _ad_sade(ad):
    return re.sub(r"\s+", " ", (ad or "").strip())


def sinifla(ad):
    """Komponent sınıfı: ('standart', tip) | ('kaynak', '') | ('parca', '')."""
    a = _ad_sade(ad)
    if re.search(KAYNAK, a, re.I):
        return "kaynak", ""
    for desen, tip in STANDART:
        if re.search(desen, a, re.I):
            return "standart", tip
    return "parca", ""


def kod_cikar(ad):
    """Parça kodunu addan ayıklar (ör. 510206300-06_KAYAR... -> 510206300-06)."""
    a = _ad_sade(ad)
    m = re.match(r"([0-9][0-9.\-]{5,}[0-9])", a)
    if m:
        return m.group(1)
    m = re.search(r"\b((?:DIN|ISO|EN)\s*\d+[\w\-]*)", a, re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).upper()
    return a[:40]


# ---------------------------------------------------------------- temel ölçüler
def hacim(sh):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g); return g.Mass()


def yuzey_alani(sh):
    g = GProp_GProps(); BRepGProp.SurfaceProperties_s(sh, g); return g.Mass()


def agirlik_merkezi(sh):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g); c = g.CentreOfMass()
    return (c.X(), c.Y(), c.Z())


def kutu(sh):
    b = Bnd_Box(); BRepBndLib.Add_s(sh, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    return (x0, y0, z0, x1, y1, z1)


def _birim(v):
    n = math.sqrt(sum(t * t for t in v))
    return tuple(t / n for t in v) if n > 1e-12 else (0.0, 0.0, 1.0)


def _capraz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def hizalama(sh):
    """Komponentin kendi eksenleri: (X=boy, Y=en, Z=kalınlık) döndürür.

    En büyük düz yüzeyin normali Z; o yüzeydeki en uzun doğru kenarın yönü X.
    Düz yüzey yoksa en büyük silindirin ekseni Z alınır, yoksa birim matris."""
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    en_duz, en_duz_alan, en_sil, en_sil_alan = None, 0.0, None, 0.0
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
        a = g.Mass()
        if ad.GetType() == GeomAbs_Plane and a > en_duz_alan:
            n = ad.Plane().Axis().Direction()
            en_duz, en_duz_alan = (f, (n.X(), n.Y(), n.Z())), a
        elif ad.GetType() == GeomAbs_Cylinder and a > en_sil_alan:
            d = ad.Cylinder().Position().Direction()
            en_sil, en_sil_alan = (d.X(), d.Y(), d.Z()), a
    if en_duz is None:
        z = _birim(en_sil) if en_sil else (0.0, 0.0, 1.0)
        x = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
        x = _birim([x[i] - sum(x[j] * z[j] for j in range(3)) * z[i] for i in range(3)])
        return [list(x), list(_capraz(z, x)), list(z)]
    f, z = en_duz
    z = _birim(z)
    # o yüzeydeki en uzun doğru kenarın yönü
    en_uzun, yon = 0.0, None
    ex = TopExp_Explorer(f, TopAbs_EDGE)
    while ex.More():
        e = cq.Edge(TopoDS.Edge_s(ex.Current()))
        try:
            if e.geomType() == "LINE" and e.Length() > en_uzun:
                p, q = e.startPoint(), e.endPoint()
                en_uzun, yon = e.Length(), (q.x - p.x, q.y - p.y, q.z - p.z)
        except Exception:
            pass
        ex.Next()
    if yon is None:
        yon = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
    x = _birim([yon[i] - sum(yon[j] * z[j] for j in range(3)) * z[i] for i in range(3)])
    return [list(x), list(_capraz(z, x)), list(z)]


def donustur(sh, R, t=(0.0, 0.0, 0.0)):
    tr = gp_Trsf()
    tr.SetValues(R[0][0], R[0][1], R[0][2], t[0],
                 R[1][0], R[1][1], R[1][2], t[1],
                 R[2][0], R[2][1], R[2][2], t[2])
    return BRepBuilderAPI_Transform(sh, tr, True).Shape()


def hizali_kati(sh):
    """Komponenti kendi eksenlerine oturtup orijine taşır."""
    R = hizalama(sh)
    s2 = donustur(sh, R)
    k = kutu(s2)
    s3 = donustur(s2, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], (-k[0], -k[1], -k[2]))
    return s3, R


# ---------------------------------------------------------------- delikler
def delikler(sh, en_az_cap=1.0):
    """İç silindirik yüzeyleri delik olarak toplar ve çap/eksene göre gruplar."""
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    ham = []
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        cyl = ad.Cylinder()
        ic = f.Orientation() == TopAbs_REVERSED          # iç yüzey = delik
        d = cyl.Position().Direction()
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
        c = g.CentreOfMass()
        kf = kutu(f)
        boy = max(kf[3] - kf[0], kf[4] - kf[1], kf[5] - kf[2])
        ham.append({"cap": 2 * cyl.Radius(), "ic": ic, "alan": g.Mass(),
                    "eksen": (abs(d.X()), abs(d.Y()), abs(d.Z())),
                    "merkez": (c.X(), c.Y(), c.Z()), "boy": boy})
    # Bir delik CAD'de çoğu kez iki yarım silindir yüzeyden oluşur; aynı eksen
    # üzerindeki aynı çaplı yüzeyler TEK delik sayılır.
    tek = {}
    for h in ham:
        if not h["ic"]:
            continue
        e = max(range(3), key=lambda t: h["eksen"][t]) if max(h["eksen"]) > 0.9 else -1
        if e >= 0:
            dik = tuple(round(h["merkez"][t], 1) for t in range(3) if t != e)
        else:
            dik = tuple(round(v, 1) for v in h["merkez"])
        an = (round(h["cap"], 2), e, dik)
        if an in tek:
            tek[an]["boy"] = max(tek[an]["boy"], h["boy"])
            tek[an]["alan"] += h["alan"]
        else:
            tek[an] = dict(h)
    grup = defaultdict(list)
    for (cap, e, _), h in tek.items():
        grup[(cap, e)].append(h)
    out = []
    for (cap, eks), lst in sorted(grup.items(), key=lambda t: (-len(t[1]), t[0][0])):
        if cap < en_az_cap:
            continue                      # radüs/pah artığı, delik değil
        out.append({"cap_mm": cap, "adet": len(lst), "eksen": "XYZ"[eks] if eks >= 0 else "eğik",
                    "derinlik_mm": round(max(h["boy"] for h in lst), 2),
                    "merkezler": [[round(v, 2) for v in h["merkez"]] for h in lst[:40]]})
    return out


def dis_capler(sh):
    """Dış silindirik yüzeyler (mil, boru dış çapı)."""
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    c = Counter()
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() == GeomAbs_Cylinder and f.Orientation() != TopAbs_REVERSED:
            c[round(2 * ad.Cylinder().Radius(), 2)] += 1
    return [{"cap_mm": k, "yuzey": v} for k, v in sorted(c.items(), key=lambda t: -t[0])[:10]]


def sac_kalinligi(sh, k):
    """Plaka/sac ise kalınlık: en küçük kutu ölçüsü, karşılıklı düz yüzey varsa."""
    olc = sorted([k[3] - k[0], k[4] - k[1], k[5] - k[2]])
    if olc[0] < 1e-9:
        return None
    if olc[2] >= 4 * olc[0] and olc[1] >= 4 * olc[0]:
        return round(olc[0], 2)
    return None


# ---------------------------------------------------------------- komponent ölçüsü
def komponent_olcu(sh, P):
    s, R = hizali_kati(sh)
    k = kutu(s)
    L, W, T = k[3] - k[0], k[4] - k[1], k[5] - k[2]
    v = hacim(s)
    o = {
        "boy_mm": round(L, 2), "en_mm": round(W, 2), "kalinlik_mm": round(T, 2),
        "hacim_mm3": round(v, 1), "kutle_kg": round(v * P["yogunluk"], 4),
        "yuzey_mm2": round(yuzey_alani(s), 1),
        "sac_kalinlik_mm": sac_kalinligi(s, k),
        "agirlik_merkezi": [round(q, 2) for q in agirlik_merkezi(s)],
        "delikler": delikler(s, P.get("en_az_delik", 1.0)),
        "dis_capler": dis_capler(s),
        "hizalama": [[round(q, 4) for q in r] for r in R],
    }
    o["delik_adedi"] = sum(d["adet"] for d in o["delikler"])
    return s, o


# ---------------------------------------------------------------- HLR görünüş
GORUNUS = {"ON": ((0, -1, 0), (1, 0, 0)),      # göz -Y'de, bakış +Y
           "UST": ((0, 0, 1), (1, 0, 0)),      # göz +Z'de, bakış -Z
           "SAG": ((1, 0, 0), (0, 1, 0))}      # göz +X'te, bakış -X


def hlr(sh, goz, xref, gizli=True):
    algo = HLRBRep_Algo(); algo.Add(sh)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*goz), gp_Dir(*xref))))
    algo.Update(); algo.Hide()
    hs = HLRBRep_HLRToShape(algo)
    out = {"GORUNEN": [], "GIZLI": []}
    kaynaklar = [("GORUNEN", hs.VCompound()), ("GORUNEN", hs.OutLineVCompound())]
    if gizli:
        kaynaklar += [("GIZLI", hs.HCompound()), ("GIZLI", hs.OutLineHCompound())]
    for kat, sh2 in kaynaklar:
        if sh2.IsNull():
            continue
        ex = TopExp_Explorer(sh2, TopAbs_EDGE)
        while ex.More():
            c = BRepAdaptor_Curve(TopoDS.Edge_s(ex.Current()))
            d = GCPnts_TangentialDeflection(c, 0.05, 0.1)
            p = [c.Value(d.Parameter(i)) for i in range(1, d.NbPoints() + 1)]
            if len(p) > 1:
                out[kat].append([(q.X(), q.Y()) for q in p])
            ex.Next()
    return out


def dxf_kur(doc=None):
    doc = doc or ezdxf.new("R2010", setup=True)
    for kat, renk in (("GORUNEN", 7), ("GIZLI", 8), ("OLCU", 4), ("YAZI", 3),
                      ("EKSEN", 1), ("CERCEVE", 5)):
        if kat not in doc.layers:
            doc.layers.add(kat, color=renk)
    try:
        if "KESIK" not in doc.linetypes:
            doc.linetypes.add("KESIK", pattern=[3.0, 2.0, -1.0])
        doc.layers.get("GIZLI").dxf.linetype = "KESIK"
    except Exception:
        pass
    return doc


def _yaz(msp, metin, x, y, h=4.0, kat="YAZI"):
    msp.add_text(str(metin), dxfattribs={"layer": kat, "height": h}).set_placement((x, y))


def gorunus_ciz(msp, kenar, ox, oy, ad, olcu2=None):
    xs = [p[0] for v in kenar.values() for c in v for p in c]
    ys = [p[1] for v in kenar.values() for c in v for p in c]
    if not xs:
        return 0.0, 0.0
    dx, dy = ox - min(xs), oy - min(ys)
    for kat, poli in kenar.items():
        for c in poli:
            msp.add_lwpolyline([(x + dx, y + dy) for x, y in c], dxfattribs={"layer": kat})
    G, Y = max(xs) - min(xs), max(ys) - min(ys)
    _yaz(msp, ad, ox, oy - 10, 5)
    if olcu2:
        # yatay ve düşey genel ölçü
        msp.add_linear_dim(base=(ox, oy - 22), p1=(ox, oy), p2=(ox + G, oy),
                           dxfattribs={"layer": "OLCU"}).render()
        msp.add_linear_dim(base=(ox - 22, oy), p1=(ox, oy), p2=(ox, oy + Y),
                           angle=90, dxfattribs={"layer": "OLCU"}).render()
    return G, Y


def dxf_komponent(s, o, ad, kod, adet, yol, P):
    doc = dxf_kur(); msp = doc.modelspace()
    k = kutu(s)
    L, W, T = k[3] - k[0], k[4] - k[1], k[5] - k[2]
    # Görünüş yerleşimi: ÖN sol üstte, SAĞ onun sağında, ÜST onun altında.
    # Boşluk her görünüşün KENDİ ölçüsüne göre hesaplanır, yoksa üst üste biner.
    g = max(L, W, T) * 0.18 + 30
    yer = {"ON": (0.0, 0.0), "SAG": (L + g, 0.0), "UST": (0.0, -(W + g))}
    for gad, (goz, xref) in GORUNUS.items():
        kenar = hlr(s, goz, xref, gizli=P["gizli"])
        ox, oy = yer[gad]
        gorunus_ciz(msp, kenar, ox, oy, gad, olcu2=True)
    # başlık ve ölçü listesi: ÖN görünüşün üstünde
    y0 = T + g * 0.5
    satir = [
        f"{kod}   {ad[:60]}",
        f"adet: {adet}",
        f"BOY x EN x KALINLIK : {o['boy_mm']} x {o['en_mm']} x {o['kalinlik_mm']} mm",
        f"hacim {o['hacim_mm3']} mm3   kutle {o['kutle_kg']} kg   yuzey {o['yuzey_mm2']} mm2",
    ]
    if o["sac_kalinlik_mm"]:
        satir.append(f"sac kalinligi: {o['sac_kalinlik_mm']} mm")
    if o["dis_capler"]:
        satir.append("dis capler: " + ", ".join(f"O{d['cap_mm']}" for d in o["dis_capler"][:6]))
    satir.append(f"toplam delik: {o['delik_adedi']}")
    for i, t in enumerate(satir):
        _yaz(msp, t, 0.0, y0 + (len(satir) - i) * 9, 6 if i == 0 else 4.5)
    if o["delikler"]:
        x0 = L + g + W + g                      # SAĞ görünüşün sağında
        _yaz(msp, "DELIK TABLOSU", x0, y0 + len(satir) * 9, 5)
        _yaz(msp, f"{'cap':>8s} {'adet':>5s} {'eksen':>6s} {'derinlik':>9s}", x0, y0 + (len(satir) - 1) * 9, 4)
        for i, d in enumerate(o["delikler"][:18], 2):
            _yaz(msp, f"O{d['cap_mm']:>7.2f} {d['adet']:>5d} {d['eksen']:>6s} {d['derinlik_mm']:>9.2f}",
                 x0, y0 + (len(satir) - i) * 9, 4)
    doc.saveas(yol)


def dxf_montaj(katilar, yol, ad, P):
    b = Bnd_Box()
    for s in katilar:
        BRepBndLib.Add_s(s, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    comp = cq.Compound.makeCompound([cq.Shape.cast(s) for s in katilar])
    s = donustur(comp.wrapped, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], (-x0, -y0, -z0))
    L, W, H = x1 - x0, y1 - y0, z1 - z0
    doc = dxf_kur(); msp = doc.modelspace()
    g = max(L, W, H) * 0.08 + 40
    yer = {"ON": (0.0, 0.0), "SAG": (L + g, 0.0), "UST": (0.0, -(W + g))}
    for gad, (goz, xref) in GORUNUS.items():
        kenar = hlr(s, goz, xref, gizli=False)       # montajda gizli çizgi kapalı
        ox, oy = yer[gad]
        gorunus_ciz(msp, kenar, ox, oy, gad, olcu2=True)
    satir = [f"MONTAJ  {ad}",
             f"gabari BOY x EN x YUKSEKLIK : {L:.2f} x {W:.2f} x {H:.2f} mm",
             f"kati sayisi: {len(katilar)}"]
    for i, t in enumerate(satir):
        _yaz(msp, t, 0.0, H + g * 0.4 + (len(satir) - i) * 12, 9 if i == 0 else 7)
    doc.saveas(yol)
    return {"boy_mm": round(L, 2), "en_mm": round(W, 2), "yukseklik_mm": round(H, 2)}


# ---------------------------------------------------------------- komponentleme
def komponentle(kayit, P):
    """Aynı parçanın kopyalarını tek komponentte toplar (ad + hacim + gabari)."""
    grup = defaultdict(list)
    for i, (ad, sh) in enumerate(kayit):
        v = hacim(sh)
        k = kutu(sh)
        olc = tuple(sorted(round(t, 1) for t in (k[3] - k[0], k[4] - k[1], k[5] - k[2])))
        grup[(_ad_sade(ad), round(v, 1), olc)].append(i)
    out = []
    for (ad, v, olc), idx in sorted(grup.items(), key=lambda t: -t[0][1] * len(t[1])):
        sinif, tip = sinifla(ad)
        out.append({"ad": ad, "kod": kod_cikar(ad), "adet": len(idx), "indeks": idx,
                    "hacim_mm3": v, "sinif": sinif, "tip": tip})
    return out


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="STEP'ten DXF görünüş ve ölçü çıkarma")
    ap.add_argument("step")
    ap.add_argument("-o", "--out", help="çıktı klasörü (varsayılan: <step adı>_olcu)")
    ap.add_argument("--liste", action="store_true", help="yalnız komponent listesi")
    ap.add_argument("--en-az-hacim", type=float, default=0.0,
                    help="bu hacmin altındaki katılar atlanır (mm3)")
    ap.add_argument("--yogunluk", type=float, default=RHO, help="kg/mm3 (varsayılan çelik)")
    ap.add_argument("--en-az-delik", type=float, default=1.0,
                    help="bu çapın altındaki silindirler delik sayılmaz (radüs/pah)")
    ap.add_argument("--gizli", action="store_true", default=True, help="komponentte gizli çizgi")
    ap.add_argument("--gizli-yok", dest="gizli", action="store_false")
    ap.add_argument("--montaj-yok", action="store_true", help="montaj çizimini atla")
    ap.add_argument("--en-cok", type=int, default=0, help="en çok bu kadar komponent çiz")
    a = ap.parse_args()
    P = {"yogunluk": a.yogunluk, "gizli": a.gizli, "en_az_delik": a.en_az_delik}

    t0 = time.time()
    kayit = E.step_oku(a.step)
    print(f"{a.step}: {len(kayit)} katı okundu  [{time.time()-t0:.0f}s]")
    komp = komponentle(kayit, P)
    print(f"{len(komp)} komponent (kopyalar birleştirildi)")

    sayim = Counter(k["sinif"] for k in komp)
    print("  " + ", ".join(f"{k}: {v}" for k, v in sayim.items()))
    if a.liste:
        print(f"\n{'kod':<24s}{'adet':>5s}{'hacim mm3':>14s}  sınıf      ad")
        for k in komp:
            print(f"{k['kod'][:24]:<24s}{k['adet']:>5d}{k['hacim_mm3']:>14.1f}  "
                  f"{k['sinif']:<10s} {k['ad'][:50]}")
        return

    on = a.out or (os.path.splitext(os.path.basename(a.step))[0] + "_olcu")
    os.makedirs(on, exist_ok=True)

    montaj = None
    if not a.montaj_yok:
        katilar = [sh for _, sh in kayit]
        montaj = dxf_montaj(katilar, os.path.join(on, "00_MONTAJ.dxf"),
                            os.path.basename(a.step), P)
        print(f"  00_MONTAJ.dxf   gabari {montaj['boy_mm']} x {montaj['en_mm']} x "
              f"{montaj['yukseklik_mm']} mm  [{time.time()-t0:.0f}s]")

    cizilecek = [k for k in komp if k["sinif"] == "parca"
                 and k["hacim_mm3"] >= a.en_az_hacim]
    if a.en_cok:
        cizilecek = cizilecek[:a.en_cok]
    satirlar, no = [], 0
    for k in komp:
        ana = kayit[k["indeks"][0]][1]
        ciz = k in cizilecek
        if k["sinif"] == "standart":
            satirlar.append({"no": "", "kod": k["kod"], "ad": k["ad"], "adet": k["adet"],
                             "sinif": "standart", "tip": k["tip"],
                             "hacim_mm3": k["hacim_mm3"], "dxf": ""})
            continue
        if k["sinif"] == "kaynak":
            satirlar.append({"no": "", "kod": k["kod"], "ad": k["ad"], "adet": k["adet"],
                             "sinif": "kaynak", "tip": "", "hacim_mm3": k["hacim_mm3"],
                             "dxf": ""})
            continue
        s, o = komponent_olcu(ana, P)
        sat = {"no": "", "kod": k["kod"], "ad": k["ad"], "adet": k["adet"],
               "sinif": "parca", "tip": "", "dxf": ""}
        sat.update({q: o[q] for q in ("boy_mm", "en_mm", "kalinlik_mm", "hacim_mm3",
                                      "kutle_kg", "yuzey_mm2", "sac_kalinlik_mm",
                                      "delik_adedi")})
        sat["delikler"] = o["delikler"]; sat["dis_capler"] = o["dis_capler"]
        if ciz:
            no += 1
            sat["no"] = f"K{no:02d}"
            dosya = f"K{no:02d}_" + re.sub(r"[^\w\-]+", "_", k["kod"])[:34] + ".dxf"
            try:
                dxf_komponent(s, o, k["ad"], k["kod"], k["adet"],
                              os.path.join(on, dosya), P)
                sat["dxf"] = dosya
                print(f"  {dosya}  {o['boy_mm']}x{o['en_mm']}x{o['kalinlik_mm']} mm, "
                      f"{o['delik_adedi']} delik  [{time.time()-t0:.0f}s]")
            except Exception as ex:
                sat["dxf"] = f"HATA: {ex}"[:80]
                print(f"  {dosya}: HATA {ex}"[:110])
        satirlar.append(sat)

    # ---- tablolar
    alan = ["no", "kod", "ad", "adet", "sinif", "tip", "boy_mm", "en_mm", "kalinlik_mm",
            "sac_kalinlik_mm", "hacim_mm3", "kutle_kg", "yuzey_mm2", "delik_adedi", "dxf"]
    with open(os.path.join(on, "olculer.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=alan, extrasaction="ignore", delimiter=";")
        w.writeheader()
        for s2 in satirlar:
            w.writerow(s2)
    json.dump({"step": a.step, "montaj": montaj, "komponent": satirlar},
              open(os.path.join(on, "olculer.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- rapor
    L = [f"# {os.path.basename(a.step)} – ölçü raporu\n",
         f"{len(kayit)} katı, {len(komp)} komponent.\n"]
    if montaj:
        L.append(f"**Montaj gabarisi:** {montaj['boy_mm']} x {montaj['en_mm']} x "
                 f"{montaj['yukseklik_mm']} mm (boy x en x yükseklik)\n")
    L.append("## Çizilen parçalar\n")
    L.append("| no | kod | adet | boy | en | kalınlık | sac | kg | delik | dxf |")
    L.append("|----|-----|------|-----|----|----------|-----|----|-------|-----|")
    for s2 in satirlar:
        if s2["sinif"] != "parca":
            continue
        L.append(f"| {s2['no']} | {s2['kod'][:26]} | {s2['adet']} | {s2.get('boy_mm')} | "
                 f"{s2.get('en_mm')} | {s2.get('kalinlik_mm')} | {s2.get('sac_kalinlik_mm') or '-'} | "
                 f"{s2.get('kutle_kg')} | {s2.get('delik_adedi')} | {s2['dxf']} |")
    std = [s2 for s2 in satirlar if s2["sinif"] == "standart"]
    if std:
        L.append("\n## Standart elemanlar (çizim üretilmedi)\n")
        L.append("| kod | tip | adet | ad |")
        L.append("|-----|-----|------|----|")
        for s2 in std:
            L.append(f"| {s2['kod'][:30]} | {s2['tip']} | {s2['adet']} | {s2['ad'][:52]} |")
    kyn = [s2 for s2 in satirlar if s2["sinif"] == "kaynak"]
    if kyn:
        L.append(f"\n## Kaynak dikişleri\n\n{len(kyn)} çeşit, toplam "
                 f"{sum(s2['adet'] for s2 in kyn)} adet (parça değildir, çizim üretilmez).\n")
    L.append("\n## Delik tabloları\n")
    for s2 in satirlar:
        if s2["sinif"] != "parca" or not s2.get("delikler"):
            continue
        L.append(f"\n**{s2['no'] or '-'} {s2['kod'][:30]}**\n")
        L.append("| çap | adet | eksen | derinlik |")
        L.append("|-----|------|-------|----------|")
        for d in s2["delikler"][:20]:
            L.append(f"| Ø{d['cap_mm']} | {d['adet']} | {d['eksen']} | {d['derinlik_mm']} |")
    open(os.path.join(on, "rapor.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"  olculer.csv, olculer.json, rapor.md")
    print(f"bitti [{time.time()-t0:.0f}s]  ->  {on}/")


if __name__ == "__main__":
    main()
