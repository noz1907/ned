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

Çizgi kalınlıkları: görünen 0,50 mm, görünmeyen 0,35 mm, merkez çizgisi 0,20 mm.
Çap yalnız tam çember delikler için verilir; kenar yuvarlamaları ayrı radüs
tablosunda yarıçap olarak listelenir.

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

# ---------------------------------------------------------------- malzeme
# Kütle = hacim x yoğunluk. Yoğunluk MALZEMEYE bağlıdır; program malzemeyi
# kendiliğinden bilemez, sorar (--malzeme / --malzeme-dosya / --malzeme-sor).
# anahtar -> (tam ad, yoğunluk g/cm3)
MALZEME = {
    "celik":      ("Celik (S235JR / St37)",      7.85),
    "celik-yuksek": ("Celik (S355 / St52)",      7.85),
    "paslanmaz":  ("Paslanmaz celik (1.4301)",   7.90),
    "dokum":      ("Dokme demir (GG25)",         7.20),
    "aluminyum":  ("Aluminyum (AlMg3 / 6060)",   2.70),
    "pirinc":     ("Pirinc (CuZn37)",            8.50),
    "bakir":      ("Bakir (Cu-ETP)",             8.96),
    "bronz":      ("Bronz (CuSn8)",              8.80),
    "titanyum":   ("Titanyum (Ti6Al4V)",         4.43),
    "cinko":      ("Cinko dokum (ZnAl4)",        6.70),
    "magnezyum":  ("Magnezyum (AZ91)",           1.81),
    "kursun":     ("Kursun",                    11.34),
    "plastik":    ("Plastik (PA6 - poliamid)",   1.14),
    "pom":        ("POM (asetal)",               1.41),
    "pe":         ("PE-HD (polietilen)",         0.95),
    "pp":         ("PP (polipropilen)",          0.91),
    "pvc":        ("PVC",                        1.40),
    "abs":        ("ABS",                        1.05),
    "ptfe":       ("PTFE (teflon)",              2.20),
    "kaucuk":     ("Kaucuk (NBR)",               1.30),
    "ahsap":      ("Ahsap (kayin)",              0.72),
    "cam":        ("Cam",                        2.50),
}
VARSAYILAN_MALZEME = "celik"
_TR = str.maketrans("çğıİöşüÇĞIÖŞÜ", "cgiiosucgiosu")


def _tr_sade(t):
    return (t or "").strip().translate(_TR).lower()


def malzeme_coz(ad):
    """Kullanıcının yazdığı malzeme adını tablodaki anahtara çevirir."""
    a = _tr_sade(ad)
    if not a:
        return None
    if a in MALZEME:
        return a
    for k in MALZEME:
        if a.startswith(k) or k.startswith(a):
            return k
    for k, (tam, _r) in MALZEME.items():
        if a in _tr_sade(tam):
            return k
    return None


def yogunluk_kg_mm3(anahtar):
    return MALZEME[anahtar][1] * 1e-6


def malzeme_listele():
    print("Malzemeler (yogunluk g/cm3):")
    for k, (tam, r) in MALZEME.items():
        print(f"  {k:<14s} {tam:<28s} {r:>6.2f}")


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
def delik_ve_radus(sh, en_az_cap=1.0, tam_oran=0.90):
    """İç silindirik yüzeyleri DELİK ve RADÜS olarak ayırır.

    Delik = açısal olarak tam çember (360°) kapatan silindir. Kenar
    yuvarlaması (fillet) çoğunlukla 90°'lik bir silindir parçasıdır ve çap
    değil YARIÇAP olarak verilir. Bir delik CAD'de iki yarım silindire
    bölünmüş olabilir; aynı eksendeki aynı yarıçaplı yüzeylerin açıları
    toplanır, toplam 360°'ye yakınsa delik sayılır."""
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    tek = {}
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        if f.Orientation() != TopAbs_REVERSED:
            continue                                  # dış yüzey, delik değil
        cyl = ad.Cylinder()
        r = cyl.Radius()
        d = cyl.Position().Direction()
        eks = (abs(d.X()), abs(d.Y()), abs(d.Z()))
        e = max(range(3), key=lambda t: eks[t]) if max(eks) > 0.9 else -1
        try:
            aci = abs(ad.LastUParameter() - ad.FirstUParameter())
        except Exception:
            aci = 2 * math.pi
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
        c = g.CentreOfMass()
        kf = kutu(f)
        boy = max(kf[3] - kf[0], kf[4] - kf[1], kf[5] - kf[2])
        # Anahtar, yüzeyin ağırlık merkezi DEĞİL silindirin EKSEN KONUMUDUR:
        # bir delik iki yarım silindire bölündüğünde her yarımın ağırlık
        # merkezi farklı yerdedir, ama eksenleri aynıdır.
        ek = cyl.Position().Location()
        eksen_nokta = (ek.X(), ek.Y(), ek.Z())
        merkez = eksen_nokta if e >= 0 else (c.X(), c.Y(), c.Z())
        dik = (tuple(round(eksen_nokta[t], 2) for t in range(3) if t != e) if e >= 0
               else tuple(round(v, 2) for v in eksen_nokta))
        an = (round(r, 3), e, dik)
        if an in tek:
            tek[an]["aci"] += aci
            tek[an]["boy"] = max(tek[an]["boy"], boy)
        else:
            m2 = list(merkez)
            if e >= 0:
                m2[e] = c.Coord(e + 1)        # eksen yönünde yüzeyin orta noktası
            tek[an] = {"r": r, "eksen": e, "aci": aci, "boy": boy, "merkez": tuple(m2)}

    delik_g, radus_g = defaultdict(list), defaultdict(list)
    for h in tek.values():
        tam = h["aci"] >= tam_oran * 2 * math.pi
        (delik_g if tam else radus_g)[(round(2 * h["r"], 2) if tam else round(h["r"], 2),
                                       h["eksen"])].append(h)
    delikler = []
    for (cap, eks), lst in sorted(delik_g.items(), key=lambda t: (-len(t[1]), t[0][0])):
        if cap < en_az_cap:
            continue
        delikler.append({"cap_mm": cap, "adet": len(lst),
                         "eksen": "XYZ"[eks] if eks >= 0 else "eğik",
                         "derinlik_mm": round(max(h["boy"] for h in lst), 2),
                         "merkezler": [[round(v, 2) for v in h["merkez"]] for h in lst[:200]]})
    radusler = []
    for (r, eks), lst in sorted(radus_g.items(), key=lambda t: (-len(t[1]), t[0][0])):
        radusler.append({"yaricap_mm": r, "adet": len(lst),
                         "eksen": "XYZ"[eks] if eks >= 0 else "eğik",
                         "uzunluk_mm": round(max(h["boy"] for h in lst), 2),
                         "merkezler": [[round(v, 2) for v in h["merkez"]] for h in lst[:200]]})
    return delikler, radusler


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
        "delikler": None, "radusler": None,
        "dis_capler": dis_capler(s),
        "hizalama": [[round(q, 4) for q in r] for r in R],
    }
    o["delikler"], o["radusler"] = delik_ve_radus(s, P.get("en_az_delik", 1.0))
    o["delik_adedi"] = sum(d["adet"] for d in o["delikler"])
    o["radus_adedi"] = sum(d["adet"] for d in o["radusler"])
    return s, o


# ---------------------------------------------------------------- HLR görünüş
# Dört görünüş yeter: ÖN (referans), SAĞ, SOL, ÜST.
# (göz yönü, izdüşüm düzleminin X ekseni)
GORUNUS = {"ON":  ((0, -1, 0), (1, 0, 0)),     # göz -Y'de, bakış +Y  -> X yatay, Z düşey
           "SAG": ((1, 0, 0), (0, 1, 0)),      # göz +X'te            -> Y yatay, Z düşey
           "SOL": ((-1, 0, 0), (0, -1, 0)),    # göz -X'te            -> -Y yatay, Z düşey
           "UST": ((0, 0, 1), (1, 0, 0))}      # göz +Z'de            -> X yatay, Y düşey
GORUNUS_AD = {"ON": "ÖN", "SAG": "SAĞ", "SOL": "SOL", "UST": "ÜST"}


# Bir eksene paralel deliğin DAİRE göründüğü görünüş(ler).
# (görünüş, yatay eksen indeksi, düşey eksen indeksi, yatay aynalı mı)
# SOL görünüşte yatay eksen -Y olduğu için ayna gerekir.
DAIRE_GOR = {
    "Y": [("ON", 0, 2, False)],
    "Z": [("UST", 0, 1, False)],
    "X": [("SAG", 1, 2, False), ("SOL", 1, 2, True)],
}


def gorunus_olcusu(gad, L, W, T):
    """Görünüşün (genişlik, yükseklik) ölçüsü."""
    return {"ON": (L, T), "SAG": (W, T), "SOL": (W, T), "UST": (L, W)}[gad]


def gorunus_yerlesimi(L, W, T, g):
    """1. açı (Avrupa/ISO-E) yerleşimi: sağdan bakılan görünüş SOLA,
    soldan bakılan SAĞA, üstten bakılan ALTA çizilir. ÖN referanstır."""
    return {"SAG": (-(W + g), 0.0), "ON": (0.0, 0.0),
            "SOL": (L + g, 0.0), "UST": (0.0, -(W + g))}


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


# Katman -> (renk, çizgi kalınlığı 1/100 mm)
# Tüm katmanlar 0,10 mm çizgi kalınlığı (DXF birimi 1/100 mm).
CIZGI_KAL = 10
KATMAN = {
    "GORUNEN": (7, CIZGI_KAL),      # görünen kenar
    "GIZLI":   (8, CIZGI_KAL),      # görünmeyen kenar (kesik)
    "EKSEN":   (1, CIZGI_KAL),      # merkez çizgisi
    "OLCU":    (4, CIZGI_KAL),      # ölçülendirme
    "YAZI":    (3, CIZGI_KAL),
    "CERCEVE": (5, CIZGI_KAL),
}


def dxf_kur(doc=None):
    doc = doc or ezdxf.new("R2010", setup=True)
    doc.header["$LWDISPLAY"] = 1            # çizgi kalınlıkları ekranda görünsün
    doc.header["$MEASUREMENT"] = 1          # metrik
    for kat, (renk, kal) in KATMAN.items():
        if kat not in doc.layers:
            doc.layers.add(kat, color=renk)
        doc.layers.get(kat).dxf.lineweight = kal
    try:
        if "KESIK" not in doc.linetypes:
            doc.linetypes.add("KESIK", pattern=[3.0, 2.0, -1.0])
        doc.layers.get("GIZLI").dxf.linetype = "KESIK"
        if "EKSENCIZGI" not in doc.linetypes:      # uzun-kısa-uzun
            doc.linetypes.add("EKSENCIZGI", pattern=[12.0, 8.0, -2.0, 0.0, -2.0])
        doc.layers.get("EKSEN").dxf.linetype = "EKSENCIZGI"
    except Exception:
        pass
    return doc


OLCU_STILI = "PF_MM"


def olcu_stili(doc, h):
    """Milimetre ölçü stili.

    ezdxf'in hazır stilleri metre/santimetre içindir (dimlfac=100): 8 mm'lik
    bir ölçüyü 800 yazar ve yazıyı 0,25 birim yüksekliğinde koyar. Burada
    ölçek birebir (dimlfac=1) ve yazı boyu parçaya göre ölçeklenir."""
    if OLCU_STILI in doc.dimstyles:
        st = doc.dimstyles.get(OLCU_STILI)
    else:
        st = doc.dimstyles.add(OLCU_STILI)
    st.dxf.dimlfac = 1.0           # ölçü birebir mm
    st.dxf.dimscale = 1.0
    st.dxf.dimtxt = h              # yazı yüksekliği
    st.dxf.dimasz = h * 0.8        # ok boyu
    st.dxf.dimexe = h * 0.6        # uzatma çizgisi taşması
    st.dxf.dimexo = h * 0.5        # uzatma çizgisi boşluğu
    st.dxf.dimgap = h * 0.35
    st.dxf.dimdec = 1              # mm, bir ondalık
    st.dxf.dimzin = 8              # sondaki sıfırları yazma
    st.dxf.dimtad = 1              # yazı ölçü çizgisinin üstünde
    st.dxf.dimtih = 0
    st.dxf.dimtoh = 0
    try:
        st.dxf.dimclrt = 3
        st.dxf.dimclrd = 4
        st.dxf.dimclre = 4
    except Exception:
        pass
    return OLCU_STILI


def _yaz(msp, metin, x, y, h=4.0, kat="YAZI"):
    msp.add_text(str(metin), dxfattribs={"layer": kat, "height": h}).set_placement((x, y))


def gorunus_ciz(msp, kenar, ox, oy, ad, h=4.0, olcu2=True):
    xs = [p[0] for v in kenar.values() for c in v for p in c]
    ys = [p[1] for v in kenar.values() for c in v for p in c]
    if not xs:
        return 0.0, 0.0
    dx, dy = ox - min(xs), oy - min(ys)

    def _anahtar(a, b):
        a = (round(a[0], 1), round(a[1], 1)); b = (round(b[0], 1), round(b[1], 1))
        return (a, b) if a <= b else (b, a)

    gorunen = set()
    for c in kenar.get("GORUNEN", []):
        for a, b in zip(c, c[1:]):
            gorunen.add(_anahtar(a, b))
    for kat, poli in kenar.items():
        for c in poli:
            if kat != "GIZLI":
                msp.add_lwpolyline([(x + dx, y + dy) for x, y in c],
                                   dxfattribs={"layer": kat})
                continue
            # Görünen kenarla üst üste düşen gizli parçaları at, kalan
            # kesintisiz parçaları ayrı çizgi olarak çiz.
            par = []
            for a, b in zip(c, c[1:]):
                if _anahtar(a, b) in gorunen:
                    if len(par) > 1:
                        msp.add_lwpolyline([(x + dx, y + dy) for x, y in par],
                                           dxfattribs={"layer": kat})
                    par = []
                else:
                    if not par:
                        par = [a]
                    par.append(b)
            if len(par) > 1:
                msp.add_lwpolyline([(x + dx, y + dy) for x, y in par],
                                   dxfattribs={"layer": kat})
    G, Y = max(xs) - min(xs), max(ys) - min(ys)
    # Etiket görünüşün SOL ÜST köşesinde, parçanın ve ölçülerin dışında.
    _yaz(msp, GORUNUS_AD.get(ad, ad), ox, oy + Y + 0.7 * h, 1.3 * h)
    if olcu2:
        d = 4.0 * h                              # ölçü çizgisi uzaklığı
        msp.add_linear_dim(base=(ox, oy - d), p1=(ox, oy), p2=(ox + G, oy),
                           dimstyle=OLCU_STILI, dxfattribs={"layer": "OLCU"}).render()
        msp.add_linear_dim(base=(ox - d, oy), p1=(ox, oy), p2=(ox, oy + Y),
                           angle=90, dimstyle=OLCU_STILI, dxfattribs={"layer": "OLCU"}).render()
    return G, Y


def cap_olculeri(msp, o, yer, h, olcu, ust, en_cok_grup=6):
    """Her görünüşte, o görünüşte daire görünen delikler için çap ölçüsü.

    Ölçü çizgisi deliğin merkezinden geçer (dimtofl=1). Yazı, görünüşün
    üstünde satır satır dizilir: her çap grubu kendi satırına konur, böylece
    yazılar ne birbirinin ne de görünüşlerin üstüne biner.
    Aynı çaptaki delikler için tek ölçü yazılır, adet önüne konur ("2x Ø9").
    Radüsler ayrıca R olarak verilir."""
    L, W, T = olcu
    kova = defaultdict(list)                 # görünüş -> ölçülecek gruplar
    for tip, liste in (("cap", o.get("delikler") or []), ("radus", o.get("radusler") or [])):
        for d in liste:
            hedef = DAIRE_GOR.get(d["eksen"])
            if not hedef or not d.get("merkezler"):
                continue
            gad, i1, i2, ayna = hedef[0]     # ölçü tek görünüşe konur
            if gad not in yer:
                continue
            r = (d["cap_mm"] / 2.0) if tip == "cap" else d["yaricap_mm"]
            if r < 0.5 or len(kova[gad]) >= en_cok_grup:
                continue
            kova[gad].append((tip, d, i1, i2, ayna, r))
    en_ust = dict(ust)
    en_sag = max(x + gorunus_olcusu(gd, L, W, T)[0] for gd, (x, _y) in yer.items())
    for gad, gruplar in kova.items():
        ox, oy = yer[gad]
        gw, _gy = gorunus_olcusu(gad, L, W, T)
        # Büyük çap üstte: kılavuz çizgileri birbirini az kessin.
        gruplar.sort(key=lambda q: -q[5])
        for k, (tip, d, i1, i2, ayna, r) in enumerate(gruplar):
            # Ölçü, o gruptaki deliklerden görünüşün ortasına en uzak olanına
            # konur; yazı dışarı taşsın, görünüşü kapatmasın.
            def _x(q):
                return ox + (gw - q[i1] if ayna else q[i1])
            c = max(d["merkezler"], key=lambda q: abs(_x(q) - (ox + gw / 2.0)))
            x, y = _x(c), oy + c[i2]
            satir_y = en_ust.get(gad, oy) + (0.4 + 1.9 * k) * h
            yazi_yeri = (x + 1.2 * h, satir_y)
            onek = f"{d['adet']}x " if d["adet"] > 1 else ""
            metin = (f"{onek}%%c{d['cap_mm']:g}" if tip == "cap"
                     else f"{onek}R{d['yaricap_mm']:g}")
            ovr = {"dimtofl": 1, "dimtad": 0, "dimtix": 0, "dimtmove": 1,
                   "dimatfit": 3, "dimgap": h * 0.3}
            try:
                if tip == "cap":
                    msp.add_diameter_dim(center=(x, y), radius=r, location=yazi_yeri,
                                         dimstyle=OLCU_STILI, override=ovr, text=metin,
                                         dxfattribs={"layer": "OLCU"}).render()
                else:
                    msp.add_radius_dim(center=(x, y), radius=r, location=yazi_yeri,
                                       dimstyle=OLCU_STILI, override=ovr, text=metin,
                                       dxfattribs={"layer": "OLCU"}).render()
            except Exception:
                continue
            en_ust[gad] = max(en_ust.get(gad, oy), satir_y + 1.4 * h)
            en_sag = max(en_sag, yazi_yeri[0] + (len(metin) + 1) * 0.72 * h)
    return en_ust, en_sag


def merkez_cizgileri(msp, o, yer, L, W, T, en_cok=1200):
    """Deliğin daire göründüğü HER görünüşte merkez çizgisi."""
    sayac = 0
    for d in o.get("delikler") or []:
        for gad, i1, i2, ayna in DAIRE_GOR.get(d["eksen"], []):
            if gad not in yer:
                continue
            ox, oy = yer[gad]
            gw, _gy = gorunus_olcusu(gad, L, W, T)
            r = d["cap_mm"] / 2.0
            u = max(r + 1.5, 2.0)
            for c in d.get("merkezler") or []:
                if sayac >= en_cok:
                    return sayac
                x = ox + (gw - c[i1] if ayna else c[i1])
                y = oy + c[i2]
                msp.add_line((x - u, y), (x + u, y), dxfattribs={"layer": "EKSEN"})
                msp.add_line((x, y - u), (x, y + u), dxfattribs={"layer": "EKSEN"})
                sayac += 1
    return sayac


def _tablo(msp, satirlar, x, y_ust, h, sat_h):
    """Sol üst köşesi (x, y_ust) olan yazı tablosu. Genişliğini döndürür."""
    for i, (t, th) in enumerate(satirlar):
        _yaz(msp, t, x, y_ust - i * sat_h, th)
    # tek aralıklı yazıda karakter eni ~0,72*yükseklik; sağına pay bırak
    return max((len(t) + 2) * 0.72 * th for t, th in satirlar)


def dxf_komponent(s, o, k, yol, P):
    """Bir komponentin detay resmi: ÖN / SAĞ / SOL / ÜST + ölçüler + tablolar."""
    doc = dxf_kur(); msp = doc.modelspace()
    kb = kutu(s)
    L, W, T = kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]
    # Yazı boyu parçaya göre: küçük parçada küçük, büyükte büyük ama okunur.
    h = min(25.0, max(2.5, max(L, W, T) / 45.0))
    olcu_stili(doc, h)
    # Görünüşler arası boşluk: araya giren ölçü çizgisi + yazı + kılavuz kadar.
    g = max(L, W, T) * 0.10 + 14 * h
    yer = gorunus_yerlesimi(L, W, T, g)
    ust = {}
    for gad, (goz, xref) in GORUNUS.items():
        kenar = hlr(s, goz, xref, gizli=P["gizli"])
        ox, oy = yer[gad]
        G, Y = gorunus_ciz(msp, kenar, ox, oy, gad, h=h, olcu2=True)
        ust[gad] = oy + Y + 2.2 * h          # görünüş etiketinin de üstü
    merkez_cizgileri(msp, o, yer, L, W, T)
    ust, sag = cap_olculeri(msp, o, yer, h, (L, W, T), ust)
    sol = min(x for x, _y in yer.values()) - 5.0 * h
    # Başlık bloğu: çizilen her şeyin üstünde, en sol görünüşle aynı hizada.
    # İçerik yalnız parça kimliği ve genel ölçüler; delik/radüs ayrıntısı
    # tablolarda durur.
    sat_h = 2.2 * h
    y0 = max(ust.values()) + 2.5 * h
    poz = f"POZ {k['poz']}   " if k.get("poz") else ""
    satir = [
        (f"{poz}{k['kod']}   {k['ad'][:60]}", 1.5 * h),
        (f"adet: {k['adet']}", 1.1 * h),
        (f"BOY x EN x KALINLIK : {o['boy_mm']} x {o['en_mm']} x {o['kalinlik_mm']} mm", 1.1 * h),
        (f"hacim {o['hacim_mm3']} mm3   kutle {o['kutle_kg']} kg   yuzey {o['yuzey_mm2']} mm2", 1.1 * h),
        (f"malzeme: {k.get('malzeme_ad', '-')}   yogunluk {k.get('yogunluk_g_cm3', '-')} g/cm3", 1.1 * h),
    ]
    tepe = y0 + len(satir) * sat_h
    _tablo(msp, satir, sol, tepe, h, sat_h)
    # Delik ve radüs tabloları: çizimin sağında, yan yana, üstleri aynı hizada.
    x = sag + 6.0 * h
    for baslik, liste, bicim in (
        ("DELIK TABLOSU", o.get("delikler") or [],
         lambda d: f"%%c{d['cap_mm']:>6.2f} {d['adet']:>5d} {d['eksen']:>6s} {d['derinlik_mm']:>9.2f}"),
        ("RADUS TABLOSU (kenar yuvarlamalari)", o.get("radusler") or [],
         lambda d: f"R{d['yaricap_mm']:>7.2f} {d['adet']:>5d} {d['eksen']:>6s} {d['uzunluk_mm']:>9.2f}"),
    ):
        if not liste:
            continue
        radus = baslik.startswith("RADUS")
        st = [(baslik, 1.3 * h),
              (f"{'R' if radus else 'cap':>8s} {'adet':>5s} {'eksen':>6s} "
               f"{'uzunluk' if radus else 'derinlik':>9s}", 1.05 * h)]
        st += [(bicim(d), 1.05 * h) for d in liste[:18]]
        if len(liste) > 18:
            st.append((f"... +{len(liste) - 18} satir daha", 1.05 * h))
        x += _tablo(msp, st, x, tepe, h, sat_h) + 4.0 * h
    doc.saveas(yol)


def dxf_montaj(katilar, yol, ad, P, bom=None):
    """Montaj resmi: ÖN / SAĞ / SOL / ÜST gabari görünüşleri + BOM tablosu."""
    b = Bnd_Box()
    for sh in katilar:
        BRepBndLib.Add_s(sh, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    comp = cq.Compound.makeCompound([cq.Shape.cast(sh) for sh in katilar])
    s = donustur(comp.wrapped, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], (-x0, -y0, -z0))
    L, W, H = x1 - x0, y1 - y0, z1 - z0
    doc = dxf_kur(); msp = doc.modelspace()
    h = min(40.0, max(3.0, max(L, W, H) / 45.0))
    olcu_stili(doc, h)
    g = max(L, W, H) * 0.08 + 10 * h
    yer = gorunus_yerlesimi(L, W, H, g)
    ust = {}
    for gad, (goz, xref) in GORUNUS.items():
        kenar = hlr(s, goz, xref, gizli=False)       # montajda gizli çizgi kapalı
        ox, oy = yer[gad]
        G, Y = gorunus_ciz(msp, kenar, ox, oy, gad, h=h, olcu2=True)
        ust[gad] = oy + Y + 2.2 * h
    sol = min(x for x, _y in yer.values()) - 5.0 * h
    sag = max(x + gorunus_olcusu(gd, L, W, H)[0] for gd, (x, _y) in yer.items())
    sat_h = 2.2 * h
    satir = [(f"MONTAJ   {ad}", 1.5 * h),
             (f"gabari BOY x EN x YUKSEKLIK : {L:.2f} x {W:.2f} x {H:.2f} mm", 1.1 * h),
             (f"kati sayisi: {len(katilar)}", 1.1 * h)]
    if bom:
        agir = sum((r.get("toplam_kg") or 0.0) for r in bom)
        satir.append((f"toplam kutle: {agir:.3f} kg   poz sayisi: {len(bom)}", 1.1 * h))
    tepe = max(ust.values()) + 2.5 * h + len(satir) * sat_h
    _tablo(msp, satir, sol, tepe, h, sat_h)
    if bom:
        _tablo(msp, bom_satirlari(bom, h), sag + 6.0 * h, tepe, h, sat_h)
    doc.saveas(yol)
    return {"boy_mm": round(L, 2), "en_mm": round(W, 2), "yukseklik_mm": round(H, 2)}


# ---------------------------------------------------------------- BOM
BOM_BASLIK = ("poz", "kod", "tanim", "adet", "malzeme", "olcu", "kg/adet", "toplam kg")


def _bom_metin(r):
    ka = f"{r['kg_adet']:.3f}" if r.get("kg_adet") else "-"
    tk = f"{r['toplam_kg']:.3f}" if r.get("toplam_kg") else "-"
    return (f"{str(r['poz']):>3s} {r['kod'][:22]:<22s} {r['ad'][:30]:<30s} "
            f"{r['adet']:>4d} {(r.get('malzeme_ad') or '-')[:22]:<22s} "
            f"{(r.get('olcu') or '-'):<22s} {ka:>9s} {tk:>9s}")


def bom_satirlari(bom, h, en_cok=40):
    """BOM tablosunu DXF yazı satırlarına çevirir."""
    st = [("BOM - PARCA LISTESI", 1.3 * h),
          (f"{'poz':>3} {'kod':<22s} {'tanim':<30s} {'adet':>4} {'malzeme':<22s} "
           f"{'olcu (BxExK)':<22s} {'kg/adet':>9s} {'toplam kg':>9s}", 1.05 * h)]
    for r in bom[:en_cok]:
        st.append((_bom_metin(r), 1.05 * h))
    if len(bom) > en_cok:
        st.append((f"... +{len(bom) - en_cok} poz daha (BOM.csv)", 1.05 * h))
    return st


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


# ---------------------------------------------------------------- malzeme seçimi
def malzeme_dosya_oku(yol):
    """kod;malzeme biçiminde eşleme dosyası (CSV veya JSON)."""
    esl = {}
    if yol.lower().endswith(".json"):
        for kod, mal in (json.load(open(yol, encoding="utf-8")) or {}).items():
            esl[_tr_sade(kod)] = mal
        return esl
    with open(yol, encoding="utf-8-sig") as f:
        ilk = f.readline()
        ayr = ";" if ";" in ilk else ("," if "," in ilk else "\t")
        f.seek(0)
        for sat in csv.reader(f, delimiter=ayr):
            if len(sat) < 2 or _tr_sade(sat[0]) in ("kod", "poz", ""):
                continue
            esl[_tr_sade(sat[0])] = sat[1].strip()
    return esl


def malzeme_sablonu(komp, yol):
    """Kullanıcının doldurup --malzeme-dosya ile geri vereceği şablon."""
    with open(yol, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["kod", "malzeme", "ad"])
        for k in komp:
            if k["sinif"] == "kaynak":
                continue
            w.writerow([k["kod"], VARSAYILAN_MALZEME, k["ad"][:70]])
    return yol


def malzeme_sor(komp):
    """Terminalden malzeme sorar: hepsine tek malzeme ya da parça parça."""
    malzeme_listele()
    c = input(f"\nHepsine tek malzeme icin ad yazin (bos = {VARSAYILAN_MALZEME}), "
              f"parca parca sormak icin 'tek': ").strip()
    if _tr_sade(c) != "tek":
        m = malzeme_coz(c) or VARSAYILAN_MALZEME
        print(f"  -> hepsi: {MALZEME[m][0]} ({MALZEME[m][1]} g/cm3)")
        return {}, m
    esl, son = {}, VARSAYILAN_MALZEME
    for k in komp:
        if k["sinif"] == "kaynak":
            continue
        c = input(f"  {k['kod'][:26]:<26s} {k['ad'][:34]:<34s} [{son}]: ").strip()
        m = malzeme_coz(c) or son
        esl[_tr_sade(k["kod"])] = m
        son = m
    return esl, VARSAYILAN_MALZEME


def malzeme_ata(k, esl, genel):
    """Bir komponentin malzemesi: eşleme dosyası > genel seçim > varsayılan."""
    m = None
    if esl:
        m = malzeme_coz(esl.get(_tr_sade(k["kod"]), "") or "")
        if not m:
            for kod, mal in esl.items():
                if kod and (kod in _tr_sade(k["kod"]) or kod in _tr_sade(k["ad"])):
                    m = malzeme_coz(mal)
                    break
    return m or genel


# ---------------------------------------------------------------- CLI
# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(
        description="STEP'ten BOM, detay resmi ve montaj resmi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""islem akisi:
  1  komponent parcalarin detaylandirilmasi ve BOM cikarilmasi
  2  detay parcalarin cizilmesi ve olculendirilmesi
  3  montaj resmi ve olculendirilmesi
--asama ile tek tek ya da birlikte calistirilir (varsayilan: 1,2,3)""")
    ap.add_argument("step")
    ap.add_argument("-o", "--out", help="çıktı klasörü (varsayılan: <step adı>_olcu)")
    ap.add_argument("--asama", default="1,2,3",
                    help="çalıştırılacak aşamalar: 1 / 2 / 3 / 1,2 / 1,2,3")
    ap.add_argument("--liste", action="store_true", help="yalnız komponent listesi")
    ap.add_argument("--malzeme", help="hepsine tek malzeme (ör. --malzeme aluminyum)")
    ap.add_argument("--malzeme-dosya", help="kod;malzeme eşleme dosyası (csv/json)")
    ap.add_argument("--malzeme-sor", action="store_true",
                    help="malzemeyi terminalden sor (hepsine tek ya da parça parça)")
    ap.add_argument("--malzeme-liste", action="store_true", help="malzeme tablosunu yaz")
    ap.add_argument("--en-az-hacim", type=float, default=0.0,
                    help="bu hacmin altındaki katılar atlanır (mm3)")
    ap.add_argument("--yogunluk", type=float, default=0.0,
                    help="kg/mm3, malzeme seçimini ezer (uzman kullanımı)")
    ap.add_argument("--en-az-delik", type=float, default=1.0,
                    help="bu çapın altındaki silindirler delik sayılmaz (radüs/pah)")
    ap.add_argument("--gizli", action="store_true", default=True, help="komponentte gizli çizgi")
    ap.add_argument("--gizli-yok", dest="gizli", action="store_false")
    ap.add_argument("--montaj-yok", action="store_true", help="montaj çizimini atla (= aşama 3 yok)")
    ap.add_argument("--en-cok", type=int, default=0, help="en çok bu kadar komponent çiz")
    ap.add_argument("--tek", help="yalnız bu kodu/no'yu çiz (ör. --tek 01.050.000.01)")
    a = ap.parse_args()
    if a.malzeme_liste:
        malzeme_listele(); return
    asama = {int(t) for t in re.findall(r"[123]", a.asama)} or {1, 2, 3}
    if a.montaj_yok:
        asama.discard(3)
    P = {"gizli": a.gizli, "en_az_delik": a.en_az_delik, "yogunluk": RHO}

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

    # ---- malzeme: kütle bunun üzerinden hesaplanır, tahmin edilmez
    esl, genel = {}, VARSAYILAN_MALZEME
    if a.malzeme_dosya:
        esl = malzeme_dosya_oku(a.malzeme_dosya)
        print(f"malzeme dosyası: {a.malzeme_dosya} ({len(esl)} kayıt)")
    if a.malzeme:
        genel = malzeme_coz(a.malzeme)
        if not genel:
            print(f"! bilinmeyen malzeme '{a.malzeme}' -- --malzeme-liste ile bakın")
            return
        print(f"malzeme (hepsi): {MALZEME[genel][0]} ({MALZEME[genel][1]} g/cm3)")
    elif a.malzeme_sor or (not esl and not a.yogunluk and sys.stdin.isatty()):
        esl2, genel = malzeme_sor(komp)
        esl.update(esl2)
    elif not esl and not a.yogunluk:
        sab = malzeme_sablonu(komp, os.path.join(on, "malzeme.csv"))
        print(f"! malzeme belirtilmedi -> hepsi '{VARSAYILAN_MALZEME}' "
              f"({MALZEME[VARSAYILAN_MALZEME][1]} g/cm3) varsayıldı.")
        print(f"  --malzeme <ad> | --malzeme-dosya <csv> | --malzeme-sor ile değiştirin.")
        print(f"  Şablon yazıldı: {sab}  (doldurup --malzeme-dosya ile verin)")

    # ---- AŞAMA 1: komponent detaylandırma + BOM
    cizilecek = [k for k in komp if k["sinif"] == "parca"
                 and k["hacim_mm3"] >= a.en_az_hacim]
    if a.tek:
        t = a.tek.lower()
        cizilecek = [k for k in cizilecek if t in k["kod"].lower() or t in k["ad"].lower()]
    if a.en_cok:
        cizilecek = cizilecek[:a.en_cok]
    ciz_id = {id(k) for k in cizilecek}

    satirlar, poz = [], 0
    for k in komp:
        poz += 1
        sat = {"poz": poz, "kod": k["kod"], "ad": k["ad"], "adet": k["adet"],
               "sinif": k["sinif"], "tip": k["tip"], "dxf": "",
               "hacim_mm3": k["hacim_mm3"], "olcu": ""}
        if k["sinif"] in ("standart", "kaynak"):
            # Standart eleman ve kaynak dikişi için çizim yok; kod + adet yeter.
            if k["sinif"] == "kaynak":
                poz -= 1; sat["poz"] = ""
            satirlar.append(sat)
            continue
        mal = malzeme_ata(k, esl, genel)
        yog = a.yogunluk if a.yogunluk else yogunluk_kg_mm3(mal)
        ana = kayit[k["indeks"][0]][1]
        s2, o = komponent_olcu(ana, dict(P, yogunluk=yog))
        sat.update({q: o[q] for q in ("boy_mm", "en_mm", "kalinlik_mm", "hacim_mm3",
                                      "kutle_kg", "yuzey_mm2", "sac_kalinlik_mm",
                                      "delik_adedi", "radus_adedi")})
        sat["delikler"], sat["radusler"] = o["delikler"], o["radusler"]
        sat["dis_capler"] = o["dis_capler"]
        sat["malzeme"] = mal
        sat["malzeme_ad"] = MALZEME[mal][0]
        sat["yogunluk_g_cm3"] = round(yog * 1e6, 3)
        sat["olcu"] = f"{o['boy_mm']}x{o['en_mm']}x{o['kalinlik_mm']}"
        sat["kg_adet"] = o["kutle_kg"]
        sat["toplam_kg"] = round(o["kutle_kg"] * k["adet"], 4)
        # ---- AŞAMA 2: detay resmi
        if 2 in asama and id(k) in ciz_id:
            dosya = f"P{poz:02d}_" + re.sub(r"[^\w\-]+", "_", k["kod"] or k["ad"])[:34] + ".dxf"
            try:
                dxf_komponent(s2, o, sat, os.path.join(on, dosya), P)
                sat["dxf"] = dosya
                print(f"  {dosya}  {o['boy_mm']}x{o['en_mm']}x{o['kalinlik_mm']} mm, "
                      f"{o['delik_adedi']} delik, {sat['malzeme_ad'].split(' (')[0]}, "
                      f"{o['kutle_kg']} kg  [{time.time()-t0:.0f}s]")
            except Exception as ex:
                sat["dxf"] = f"HATA: {ex}"[:80]
                print(f"  {dosya}: HATA {ex}"[:110])
        satirlar.append(sat)

    bom = [r for r in satirlar if r["sinif"] != "kaynak"]

    # ---- AŞAMA 3: montaj resmi
    montaj = None
    if 3 in asama:
        katilar = [sh for _, sh in kayit]
        montaj = dxf_montaj(katilar, os.path.join(on, "00_MONTAJ.dxf"),
                            os.path.basename(a.step), P, bom=bom)
        print(f"  00_MONTAJ.dxf   gabari {montaj['boy_mm']} x {montaj['en_mm']} x "
              f"{montaj['yukseklik_mm']} mm  [{time.time()-t0:.0f}s]")

    # ---- tablolar
    if 1 in asama:
        bom_yaz(on, bom, satirlar)
    alan = ["poz", "kod", "ad", "adet", "sinif", "tip", "malzeme_ad", "yogunluk_g_cm3",
            "boy_mm", "en_mm", "kalinlik_mm", "sac_kalinlik_mm", "hacim_mm3",
            "kutle_kg", "toplam_kg", "yuzey_mm2", "delik_adedi", "radus_adedi", "dxf"]
    with open(os.path.join(on, "olculer.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=alan, extrasaction="ignore", delimiter=";")
        w.writeheader()
        for s3 in satirlar:
            w.writerow(s3)
    json.dump({"step": a.step, "montaj": montaj, "komponent": satirlar},
              open(os.path.join(on, "olculer.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    rapor_yaz(on, a.step, kayit, komp, satirlar, montaj)
    print("  BOM.csv, BOM.md, olculer.csv, olculer.json, rapor.md")
    print(f"bitti [{time.time()-t0:.0f}s]  ->  {on}/")


def bom_yaz(on, bom, satirlar):
    """AŞAMA 1 çıktısı: parça listesi (BOM) — CSV + okunabilir tablo."""
    alan = ["poz", "kod", "ad", "adet", "sinif", "tip", "malzeme_ad", "olcu",
            "kg_adet", "toplam_kg", "dxf"]
    with open(os.path.join(on, "BOM.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=alan, extrasaction="ignore", delimiter=";")
        w.writeheader()
        for r in bom:
            w.writerow(r)
    agir = sum((r.get("toplam_kg") or 0.0) for r in bom)
    L = ["# BOM – parça listesi\n",
         f"{len(bom)} poz, toplam kütle {agir:.3f} kg\n",
         "| poz | kod | tanım | adet | malzeme | ölçü BxExK | kg/adet | toplam kg | dxf |",
         "|-----|-----|-------|------|---------|------------|---------|-----------|-----|"]
    for r in bom:
        ka = f"{r['kg_adet']:.3f}" if r.get("kg_adet") else "-"
        tk = f"{r['toplam_kg']:.3f}" if r.get("toplam_kg") else "-"
        L.append(f"| {r['poz']} | {r['kod'][:28]} | {r['ad'][:40]} | {r['adet']} | "
                 f"{r.get('malzeme_ad') or '-'} | {r.get('olcu') or '-'} | {ka} | {tk} | "
                 f"{r['dxf'] or '-'} |")
    kyn = [r for r in satirlar if r["sinif"] == "kaynak"]
    if kyn:
        L.append(f"\nKaynak dikişleri BOM'a girmez: {len(kyn)} çeşit, "
                 f"toplam {sum(r['adet'] for r in kyn)} adet.")
    open(os.path.join(on, "BOM.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def rapor_yaz(on, step, kayit, komp, satirlar, montaj):
    L = [f"# {os.path.basename(step)} – ölçü raporu\n",
         f"{len(kayit)} katı, {len(komp)} komponent.\n"]
    if montaj:
        L.append(f"**Montaj gabarisi:** {montaj['boy_mm']} x {montaj['en_mm']} x "
                 f"{montaj['yukseklik_mm']} mm (boy x en x yükseklik)\n")
    L.append("## Çizilen parçalar\n")
    L.append("| poz | kod | adet | malzeme | boy | en | kalınlık | sac | kg | delik | radüs | dxf |")
    L.append("|-----|-----|------|---------|-----|----|----------|-----|----|-------|-------|-----|")
    for r in satirlar:
        if r["sinif"] != "parca":
            continue
        L.append(f"| {r['poz']} | {r['kod'][:26]} | {r['adet']} | "
                 f"{(r.get('malzeme_ad') or '-').split(' (')[0]} | {r.get('boy_mm')} | "
                 f"{r.get('en_mm')} | {r.get('kalinlik_mm')} | {r.get('sac_kalinlik_mm') or '-'} | "
                 f"{r.get('kutle_kg')} | {r.get('delik_adedi')} | {r.get('radus_adedi')} | "
                 f"{r['dxf'] or '-'} |")
    std = [r for r in satirlar if r["sinif"] == "standart"]
    if std:
        L.append("\n## Standart elemanlar (çizim üretilmedi, kod + adet yeter)\n")
        L.append("| poz | kod | tip | adet | ad |")
        L.append("|-----|-----|-----|------|----|")
        for r in std:
            L.append(f"| {r['poz']} | {r['kod'][:30]} | {r['tip']} | {r['adet']} | {r['ad'][:52]} |")
    kyn = [r for r in satirlar if r["sinif"] == "kaynak"]
    if kyn:
        L.append(f"\n## Kaynak dikişleri\n\n{len(kyn)} çeşit, toplam "
                 f"{sum(r['adet'] for r in kyn)} adet (parça değildir, çizim üretilmez).\n")
    L.append("\n## Delik ve radüs tabloları\n")
    L.append("Çap yalnız TAM ÇEMBER delikler için verilir. Kenar yuvarlamaları "
             "(fillet) delik değildir, ayrı tabloda yarıçap olarak listelenir.\n")
    for r in satirlar:
        if r["sinif"] != "parca" or not (r.get("delikler") or r.get("radusler")):
            continue
        L.append(f"\n**poz {r['poz']} {r['kod'][:30]}**\n")
        if r.get("delikler"):
            L.append("| çap | adet | eksen | derinlik |")
            L.append("|-----|------|-------|----------|")
            for d in r["delikler"][:20]:
                L.append(f"| Ø{d['cap_mm']} | {d['adet']} | {d['eksen']} | {d['derinlik_mm']} |")
        if r.get("radusler"):
            L.append("")
            L.append("| radüs | adet | eksen | uzunluk |")
            L.append("|-------|------|-------|---------|")
            for d in r["radusler"][:20]:
                L.append(f"| R{d['yaricap_mm']} | {d['adet']} | {d['eksen']} | {d['uzunluk_mm']} |")
    open(os.path.join(on, "rapor.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
