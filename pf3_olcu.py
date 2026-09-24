"""
Pi3D – ADIM 0 : STEP'TEN ÇİZİM VE ÖLÇÜ ÇIKARMA
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
import argparse, bisect, csv, json, math, os, re, sys, textwrap, time
from collections import Counter, defaultdict

import ezdxf
import ezdxf.bbox

from OCP.gp import gp_Pnt, gp_Dir, gp_Trsf, gp_Ax2, gp_Ax3, gp_Vec
from OCP.BRepBuilderAPI import (BRepBuilderAPI_Transform,
                                BRepBuilderAPI_MakeFace,
                                BRepBuilderAPI_MakePolygon)
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.GeomAbs import (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
                         GeomAbs_Sphere, GeomAbs_Line, GeomAbs_Circle,
                         GeomAbs_Ellipse)
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_REVERSED
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopTools import (TopTools_IndexedMapOfShape,
                          TopTools_ListOfShape,
                          TopTools_HSequenceOfShape,
                          TopTools_IndexedDataMapOfShapeListOfShape)
from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.TopAbs import TopAbs_WIRE
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
# Parça adında/STEP malzeme alanında geçen ifadelerden malzeme tanıma.
# Data'da malzeme tanımlıysa kullanıcıya sorulmaz, okunan değer kullanılır.
MALZEME_DESEN = [
    (r"1\.4301|1\.4404|\bAISI\s*30[46]\b|paslanmaz|rostfrei|stainless|\binox\b", "paslanmaz"),
    (r"\bS235|\bSt\s*37|\bS355|\bSt\s*52|\bDC0[1-6]\b|\bQSt", "celik"),
    (r"\bAlMg|\bAlSi|\bAlCuMg|\b6060\b|\b6082\b|\b5754\b|aluminyum|alüminyum|aluminium|aluminum", "aluminyum"),
    (r"\bGG\s*\d\d|\bGGG\b|\bEN-?GJ|dokum|döküm|cast\s*iron|gusseisen", "dokum"),
    (r"\bCuZn|pirinc|pirinç|\bbrass\b|messing", "pirinc"),
    (r"\bCuSn|bronz|\bbronze\b", "bronz"),
    (r"\bCu-?ETP\b|\bbakir\b|bakır|\bcopper\b|kupfer", "bakir"),
    (r"\bTi6Al|titanyum|titanium|\btitan\b", "titanyum"),
    (r"\bPA\s*6\b|\bPA6\b|poliamid|polyamid|\bnylon\b", "plastik"),
    (r"\bPOM\b|asetal|acetal|delrin", "pom"),
    (r"\bPE-?HD\b|\bHDPE\b|polietilen|polyethylen", "pe"),
    (r"\bPP\b|polipropilen|polypropylen", "pp"),
    (r"\bPVC\b", "pvc"),
    (r"\bABS\b", "abs"),
    (r"\bPTFE\b|teflon", "ptfe"),
    (r"kaucuk|kauçuk|\brubber\b|gummi|\bNBR\b|\bEPDM\b", "kaucuk"),
    (r"\bahsap\b|ahşap|\bwood\b|\bholz\b", "ahsap"),
    (r"\bcam\b|\bglass\b|\bglas\b", "cam"),
    (r"\bsteel\b|\bstahl\b|\bcelik\b|çelik", "celik"),
    (r"\biron\b|\bdemir\b|\beisen\b", "celik"),
    (r"\bplastic\b|\bplastik\b|\bkunststoff\b", "plastik"),
]


def malzeme_tahmin(*metinler):
    """Parça adı / STEP malzeme alanı içinden malzemeyi tanır, yoksa None."""
    t = " ".join(str(m or "") for m in metinler)
    for desen, anahtar in MALZEME_DESEN:
        if re.search(desen, t, re.I):
            return anahtar
    return None
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
    # CATIA/SolidWorks gibi programlar malzemeyi İngilizce yazar
    # ("Steel", "Aluminium", "Stainless Steel", "Rubber"...); desenlerden tanı.
    return malzeme_tahmin(ad)


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
        try:
            c = BRepAdaptor_Curve(TopoDS.Edge_s(ex.Current()))
            if c.GetType() == GeomAbs_Line:
                p, q = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
                u = p.Distance(q)
                if u > en_uzun:
                    en_uzun = u
                    yon = (q.X() - p.X(), q.Y() - p.Y(), q.Z() - p.Z())
        except Exception:
            pass
        ex.Next()
    if yon is None:
        yon = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
    x = _birim([yon[i] - sum(yon[j] * z[j] for j in range(3)) * z[i] for i in range(3)])
    return [list(x), list(_capraz(z, x)), list(z)]


def bilesik(katilar):
    """Katıları tek bir bileşik şekilde toplar (OCP; cadquery gerekmez)."""
    c = TopoDS_Compound()
    b = BRep_Builder()
    b.MakeCompound(c)
    for sh in katilar:
        b.Add(c, sh)
    return c


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
# ---------------------------------------------------------------- görünüşler
# Altı görünüş tanımlı; çizime hangilerinin gireceği seçilir (şimdilik en çok 4).
# (göz yönü, izdüşüm düzleminin X ekseni)
GORUNUS = {
    "ON":   ((0, -1, 0), (1, 0, 0)),     # göz -Y'de   -> X yatay,  Z düşey
    "ARKA": ((0, 1, 0), (-1, 0, 0)),     # göz +Y'de   -> -X yatay, Z düşey
    "SAG":  ((1, 0, 0), (0, 1, 0)),      # göz +X'te   -> Y yatay,  Z düşey
    "SOL":  ((-1, 0, 0), (0, -1, 0)),    # göz -X'te   -> -Y yatay, Z düşey
    "UST":  ((0, 0, 1), (1, 0, 0)),      # göz +Z'de   -> X yatay,  Y düşey
    "ALT":  ((0, 0, -1), (1, 0, 0)),     # göz -Z'de   -> X yatay,  -Y düşey
}
GORUNUS_AD = {"ON": "ÖN", "ARKA": "ARKA", "SAG": "SAĞ", "SOL": "SOL",
              "UST": "ÜST", "ALT": "ALT"}
GORUNUS_SIRA = ("ON", "ARKA", "SAG", "SOL", "UST", "ALT")
VARSAYILAN_GORUNUS = ("ON", "SAG", "SOL", "UST")
EN_COK_GORUNUS = 4
KESIT_AD = "A-A KESIT"

# görünüş -> (yatay eksen indeksi, düşey eksen indeksi, yatay ters, düşey ters)
GOR_EKSEN = {
    "ON":   (0, 2, False, False),
    "ARKA": (0, 2, True, False),
    "SAG":  (1, 2, False, False),
    "SOL":  (1, 2, True, False),
    "UST":  (0, 1, False, False),
    "ALT":  (0, 1, False, True),
}
# Aynı dış hattı iki yandan gösteren görünüş çiftleri.
AYNA_CIFT = {"ON": 0, "ARKA": 0, "SAG": 1, "SOL": 1, "UST": 2, "ALT": 2}
# Bir eksene paralel deliğin DAİRE göründüğü görünüşler (öncelik sırasıyla).
DELIK_GOR = {"Y": ("ON", "ARKA"), "X": ("SAG", "SOL"), "Z": ("UST", "ALT")}


def gorunus_sec(istek):
    """Kullanıcının seçtiği görünüşleri düzeltir: geçerli olanlar, sırayla,
    en çok EN_COK_GORUNUS tane. Boşsa varsayılan dörtlü."""
    out = [g for g in GORUNUS_SIRA if g in set(istek or ())]
    return tuple(out[:EN_COK_GORUNUS]) or tuple(VARSAYILAN_GORUNUS)


def izdusum(p, gad):
    """3B noktanın o görünüşteki (ham) 2B karşılığı — HLR ile aynı eksenler."""
    i1, i2, tx, ty = GOR_EKSEN[gad]
    return (-p[i1] if tx else p[i1], -p[i2] if ty else p[i2])


# ---------------------------------------------------------------- datum
# ISO 5459 üç düzlemli datum çerçevesi. Parçanın kendi sınır kutusunun
# en küçük köşesi sıfır noktası, o köşede buluşan üç yüzey A, B, C'dir.
DATUM_HARF = ("A", "B", "C")


def datum_cercevesi(L, W, T):
    """Üç düzlemli datum çerçevesi; hangi eksene dik yüzey hangi harf?

    STEP dosyasında datum/PMI bilgisi YOK - ölçtük: ornek/parca.stp'de
    68 varlık tipi içinde tek bir DATUM, GEOMETRIC_TOLERANCE ya da
    ANNOTATION geçmiyor, dosya saf geometri. Yani "ilk işlenen yüzey"
    dosyadan türetilemez; program kendi çerçevesini kurar ve BÜTÜN
    görünüşlerde ona sadık kalır. Önemli olan referansın hangi yüzey
    olduğu değil, her ölçünün AYNI yerden gitmesidir.

    Harf sırası alan büyüklüğüne göre: birincil datum (A) en geniş
    yüzeydir, bağlamada üç nokta ona oturur. Bir eksene dik yüzeyin
    alanı öbür iki ölçünün çarpımıdır, yani EN KÜÇÜK ölçüye dik yüzey
    en geniştir. 175 x 80 x 5 plakada A, 175 x 80'lik yüzeydir.

    Döner: {eksen indeksi (0=X, 1=Y, 2=Z): harf}"""
    olc = (L, W, T)
    sira = sorted(range(3), key=lambda i: (olc[i], i))
    return {e: DATUM_HARF[n] for n, e in enumerate(sira)}


def datum_ucu(gad, yon):
    """Bu görünüşte datum, izdüşümün HANGİ ucundadır?

    0 = düşük koordinatlı uç (sol / alt), 1 = yüksek uç (sağ / üst).

    ÖN'de yatay eksen +X'tir, X'in sıfırı görünüşün solundadır. ARKA'ya
    öbür taraftan bakılır, izdüşüm -X'tir: AYNI yüzey görünüşün SAĞINDA
    çıkar. Datum yüzeyi değişmedi, yeri değişti. Bunu görmezden gelip
    her görünüşte soldan ölçmek iki ayrı sıfır noktası demektir; ÖN'de
    10 olan delik ARKA'da 165 çıkar ve resim kendi kendisiyle çelişir."""
    _i1, _i2, tx, ty = GOR_EKSEN[gad]
    return int(tx if yon == "yatay" else ty)


def gorunus_olcusu(gad, L, W, T):
    """Görünüşün (genişlik, yükseklik) ölçüsü."""
    d = (L, W, T)
    i1, i2, _tx, _ty = GOR_EKSEN[gad]
    return d[i1], d[i2]


def gorunus_yerlesimi(L, W, T, g, gorunusler=VARSAYILAN_GORUNUS):
    """1. açı (Avrupa/ISO-E) yerleşimi. ÖN referans, (0,0) noktasında:
    sağdan bakılan görünüş SOLA, soldan bakılan SAĞA, arka en sağa,
    üstten bakılan ALTA, alttan bakılan ÜSTE çizilir."""
    gorunusler = set(gorunusler)
    yer = {"ON": (0.0, 0.0)}
    if "SAG" in gorunusler:
        yer["SAG"] = (-(gorunus_olcusu("SAG", L, W, T)[0] + g), 0.0)
    x = L + g
    if "SOL" in gorunusler:
        yer["SOL"] = (x, 0.0)
        x += gorunus_olcusu("SOL", L, W, T)[0] + g
    if "ARKA" in gorunusler:
        yer["ARKA"] = (x, 0.0)
    if "UST" in gorunusler:
        yer["UST"] = (0.0, -(gorunus_olcusu("UST", L, W, T)[1] + g))
    if "ALT" in gorunusler:
        yer["ALT"] = (0.0, T + g)
    return {k: v for k, v in yer.items() if k in gorunusler}


def kesit_yeri(yer, L, W, T, g, gorunusler):
    """Kesit görünüşü, çizimin en sağındaki görünüşün sağına konur."""
    sag = max((x + gorunus_olcusu(gd, L, W, T)[0] for gd, (x, _y) in yer.items()),
              default=L)
    return (sag + g, 0.0)


def _duz_mu(p, tol=0.02):
    """Örneklenen noktalar bir DOĞRU üstünde mi? (en büyük sapma)"""
    if len(p) < 3:
        return True
    x0, y0 = p[0]; x1, y1 = p[-1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return False
    return max(abs(dy * x - dx * y + x1 * y0 - y1 * x0) / L
               for x, y in p[1:-1]) <= tol


def _cember_uydur(p):
    """Noktalara en iyi oturan çember: (merkez_x, merkez_y, r, sapma).

    En küçük kareler (Kasa yöntemi): çemberin denklemi
    x^2+y^2 + D*x + E*y + F = 0 doğrusaldır, doğrudan çözülür."""
    n = len(p)
    if n < 4:
        return None
    sx = sy = sxx = syy = sxy = sz = szx = szy = 0.0
    for x, y in p:
        z = x * x + y * y
        sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y
        sz += z; szx += z * x; szy += z * y
    A = [[sxx, sxy, sx], [sxy, syy, sy], [sx, sy, float(n)]]
    b = [-szx, -szy, -sz]
    # 3x3 Gauss
    for i in range(3):
        pv = max(range(i, 3), key=lambda r: abs(A[r][i]))
        if abs(A[pv][i]) < 1e-12:
            return None
        A[i], A[pv] = A[pv], A[i]; b[i], b[pv] = b[pv], b[i]
        for r in range(i + 1, 3):
            f = A[r][i] / A[i][i]
            for c in range(i, 3):
                A[r][c] -= f * A[i][c]
            b[r] -= f * b[i]
    x3 = [0.0] * 3
    for i in (2, 1, 0):
        x3[i] = (b[i] - sum(A[i][c] * x3[c] for c in range(i + 1, 3))) / A[i][i]
    D, E, F = x3
    cx, cy = -D / 2.0, -E / 2.0
    k = cx * cx + cy * cy - F
    if k <= 0:
        return None
    r = math.sqrt(k)
    sapma = max(abs(math.hypot(x - cx, y - cy) - r) for x, y in p)
    return (cx, cy, r, sapma)


def kenar_tani(p, duz_tol=0.02, yay_tol=0.05):
    """Örneklenmiş bir kenarı DOĞRU / YAY / EĞRİ diye ayırır.

    Niçin gerek var: HLR izdüşümü kenarları analitik korumuyor. Aynı
    görünüşte 8 doğru + 2 daire çıkarken pahlar ve kesikler B-spline
    olarak geliyordu (ölçülen: 18 tane). Açı, çapraz kesim ve
    girinti/çıkıntı ölçüleri doğrudan bu ayrıma dayandığı için kenarı
    çiziminden geri tanımak gerekiyor.

    Döner: {"tip": "dogru", "p0","p1","aci","uz"} ya da
           {"tip": "yay", "merkez","r","p0","p1","aci"} ya da
           {"tip": "egri", "p0","p1"}"""
    if len(p) < 2:
        return None
    p0, p1 = p[0], p[-1]
    if _duz_mu(p, duz_tol):
        uz = math.dist(p0, p1)
        if uz < 1e-9:
            return None
        return {"tip": "dogru", "p0": p0, "p1": p1, "uz": uz,
                "aci": math.degrees(math.atan2(p1[1] - p0[1],
                                               p1[0] - p0[0])) % 180.0}
    c = _cember_uydur(p)
    if c and c[3] <= max(yay_tol, 0.01 * c[2]):
        cx, cy, r, _sp = c
        a0 = math.degrees(math.atan2(p0[1] - cy, p0[0] - cx))
        a1 = math.degrees(math.atan2(p1[1] - cy, p1[0] - cx))
        ort = math.degrees(math.atan2(p[len(p) // 2][1] - cy,
                                      p[len(p) // 2][0] - cx))
        # Yayın gerçek açısı: orta noktadan geçen yön hangisiyse o.
        d = (a1 - a0) % 360.0
        if not ((a0 + 1e-9) % 360 <= ort % 360 <= (a0 + d) % 360
                or d > 359.0):
            d = d - 360.0
        return {"tip": "yay", "merkez": (cx, cy), "r": r,
                "p0": p0, "p1": p1, "aci": abs(d)}
    return {"tip": "egri", "p0": p0, "p1": p1}


def _sayi(v):
    """Ölçü yazısı: tam sayıya yakınsa tam sayı, değilse bir ondalık."""
    return f"{round(v):g}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"


def capraz_kenarlar(kenar, en_az_uz=3.0, aci_pay=1.5, komsu_pay=0.15,
                    bacak_pay=0.10, en_cok_oran=0.20):
    """Görünüşteki ÇAPRAZ (eksenlere paralel olmayan) düz kenarlar.

    İkiye ayrılır, çünkü resimde iki ayrı şeydir:

    PAH (köşe kırma): üç şartı birden tutar -
      (1) iki ucu da birbirine DİK ve eksene paralel iki kenara
          değiyor, yani bir köşeyi kesiyor;
      (2) bacakları eşit (45°);
      (3) görünüşe göre KÜÇÜK (en çok %20).
      Bunun açısı ölçü konusu değildir; keskin köşe kalmasın diye
      kırılmıştır. Resimde ok (kılavuz) ucunda "5 x 5" diye yazılır.
      Üç şart birden aranır: bir köşeden geçen BÜYÜK bir 45° kesim
      parçanın biçimidir, köşe kırma değil.

    EĞİK KESİM: köşe kırma değil, parçanın gerçek biçimi. Bunun
      açısını değil, uçlarının KENARLARDAN yerini vermek gerekir -
      atölye nereden nereye keseceğini böyle bilir.

    Döner: [{"p0","p1","uz","aci","pah","bacak"}]"""
    tanili = [t for t in (kenar_tani(p) for p in kenar.get("GORUNEN", []))
              if t and t["tip"] == "dogru"]

    # Görünüşün gabarisi: "küçük" ne demek, ona göre ölçülür.
    xs = [q[0] for e in tanili for q in (e["p0"], e["p1"])]
    ys = [q[1] for e in tanili for q in (e["p0"], e["p1"])]
    kutu_ = (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 1, 1)

    def eksene_paralel(e):
        a = e["aci"]
        return min(abs(a), abs(a - 90.0), abs(a - 180.0)) <= aci_pay

    out = []
    for t in tanili:
        if t["uz"] < en_az_uz or eksene_paralel(t):
            continue
        # Uçlarına değen, eksene paralel kenarların doğrultuları
        yon = set()
        for e in tanili:
            if e is t or not eksene_paralel(e):
                continue
            for a in (t["p0"], t["p1"]):
                if min(math.dist(a, e["p0"]), math.dist(a, e["p1"])) <= komsu_pay:
                    yon.add(0 if min(abs(e["aci"]), abs(e["aci"] - 180.0))
                            <= aci_pay else 90)
        t = dict(t)
        ba, bb = (abs(t["p1"][0] - t["p0"][0]),
                  abs(t["p1"][1] - t["p0"][1]))
        t["bacak"] = (ba, bb)
        esit = abs(ba - bb) <= bacak_pay * max(ba, bb, 1e-9)
        kucuk = (ba <= en_cok_oran * max(kutu_[2] - kutu_[0], 1e-9)
                 and bb <= en_cok_oran * max(kutu_[3] - kutu_[1], 1e-9))
        t["pah"] = (0 in yon and 90 in yon) and esit and kucuk
        out.append(t)

    # Aynı kenar birkaç kaynaktan gelebilir (VCompound + OutLine...) ve
    # parçanın üst/alt yüzündeki aynı pah izdüşümde üst üste düşer.
    # Uç noktalarına göre ayıklamak yakalamıyordu (uçlar mikron farkla
    # ayrılıyor); ORTA NOKTA ve DOĞRULTU ile ayıklanır.
    gor, tek = set(), []
    for t in sorted(out, key=lambda t: -t["uz"]):
        k = (round((t["p0"][0] + t["p1"][0]) / 2, 1),
             round((t["p0"][1] + t["p1"][1]) / 2, 1),
             round(t["aci"], 0), round(t["uz"], 1))
        if k in gor:
            continue
        gor.add(k); tek.append(t)
    return tek


def pah_notlari(msp, kenarlar, kaydir, gkutu, h, en_cok=8):
    """Köşe pahlarını OK (kılavuz) ucunda "5 x 5" diye yazar.

    Pahın açısı ve hipotenüsü ölçülendirilmez: keskin köşe kalmasın
    diye kırılmış bir köşenin ölçüsü iki bacağıdır. İlk sürümde
    hipotenüs (7,1) ve açı (45°) veriliyordu - ikisi de atölyenin
    işine yaramayan, üstelik resmi kalabalıklaştıran sayılardı."""
    say = 0
    for gad, kenar in kenarlar.items():
        if gad not in gkutu:
            continue
        dx, dy = kaydir[gad]
        gk = gkutu[gad]
        mx, my = (gk[0] + gk[2]) / 2.0, (gk[1] + gk[3]) / 2.0
        dolu = _varlik_kutulari(msp)
        pahlar = [t for t in capraz_kenarlar(kenar) if t["pah"]]
        # Aynı ölçüdeki pahlar tek notla verilir: "4x 5 x 5".
        kova = defaultdict(list)
        for t in pahlar:
            kova[(round(t["bacak"][0], 1), round(t["bacak"][1], 1))].append(t)
        for (ba, bb), lst in sorted(kova.items(), key=lambda kv: -kv[0][0])[:en_cok]:
            # Görünüşün ortasına en uzak pah: ok dışarı çıksın.
            t = max(lst, key=lambda t: ((t["p0"][0] + t["p1"][0]) / 2 + dx - mx) ** 2
                    + ((t["p0"][1] + t["p1"][1]) / 2 + dy - my) ** 2)
            ox = (t["p0"][0] + t["p1"][0]) / 2.0 + dx
            oy = (t["p0"][1] + t["p1"][1]) / 2.0 + dy
            nx, ny = ox - mx, oy - my
            L = math.hypot(nx, ny) or 1.0
            nx, ny = nx / L, ny / L
            onek = f"{len(lst)}x " if len(lst) > 1 else ""
            metin = f"{onek}{_sayi(ba)} x {_sayi(bb)}"
            for kat in range(1, 9):
                uz = (1.2 + 1.4 * kat) * h
                yer = (ox + nx * uz, oy + ny * uz)
                e = _yaz(msp, metin, yer[0] + (0.3 * h if nx >= 0 else
                                               -0.3 * h - len(metin) * 0.62 * h),
                         yer[1] - 0.45 * h, 0.9 * h)
                kt = _yazi_siniri(e)
                if kt is None or not _cakisiyor(kt, dolu, 0.25 * h):
                    msp.add_line((ox, oy), yer, dxfattribs={"layer": "OLCU"})
                    if kt:
                        dolu.append(kt)
                    say += 1
                    break
                msp.delete_entity(e)
    return say


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
# DXF'te çizgi kalınlığı serbest bir sayı DEĞİL, sabit bir merdivendir:
# 0.05, 0.09, 0.13, 0.15, 0.18, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50 ...
# "10" (0,10 mm) bu listede yok; yazılırsa en yakın değere, 0,13'e yuvarlanır.
# İstenen 0,1 mm'ye en yakın geçerli değer 0,09 mm olduğu için 9 kullanılır.
CIZGI_KAL = 9
KATMAN = {
    "GORUNEN": (7, CIZGI_KAL),      # görünen kenar
    "GIZLI":   (8, CIZGI_KAL),      # görünmeyen kenar (kesik)
    "EKSEN":   (1, CIZGI_KAL),      # merkez çizgisi
    "OLCU":    (4, CIZGI_KAL),      # ölçülendirme
    "YAZI":    (3, CIZGI_KAL),
    "CERCEVE": (5, CIZGI_KAL),
    "TARAMA":  (5, CIZGI_KAL),   # kesit taraması
}


GORUNUS_KATMAN = "PI3D_GORUNUS_ALANI"   # görünüş yerleri; çizim değildir
GORUNUS_APPID = "PI3D"


def gorunus_isareti(msp, ad, kutu_):
    """Bir görünüşün resimde nerede durduğunu işaretler.

    Bu bir çizgi değil, BİLGİDİR: paftaya yerleştirirken hangi
    görünüşün nerede olduğunu bilmek gerekir ki her biri ayrı pencereye
    alınıp kâğıda eşit aralıklarla dağıtılabilsin. Kendi katmanındadır,
    baskıya girmez, sınır hesabına katılmaz; silmek isteyen katmanı
    siler, resim bundan etkilenmez."""
    d = msp.doc
    if GORUNUS_KATMAN not in d.layers:
        k = d.layers.add(GORUNUS_KATMAN, color=8)
        k.dxf.plot = 0
        k.off()
    if GORUNUS_APPID not in d.appids:
        d.appids.add(GORUNUS_APPID)
    x0, y0, x1, y1 = kutu_
    e = msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                           close=True, dxfattribs={"layer": GORUNUS_KATMAN})
    e.set_xdata(GORUNUS_APPID, [(1000, str(ad))])
    return e


YAZI_STILI = "PI3D"
YAZI_FONTU = "arial.ttf"
YAZI_AILESI = "Arial"


def yazi_stili(doc):
    """Türkçe harfleri gösteren TrueType yazı stili.

    DXF dosyasının kendisi UTF-8'dir; "Ğ" gerçekten iki bayt (C4 9E) olarak
    yazılır. Ama AutoCAD/LibreCAD yazıyı STİLİN font dosyasıyla çizer ve
    hazır "Standard" stili txt.shx kullanır. txt.shx bir SHX vektör
    fontudur, içinde yalnızca ASCII vardır: Ğ Ş İ Ç Ö Ü karakterlerinin
    glifi yoktur, o yüzden ekranda "?" ya da boş kutu görünür. Dosya bozuk
    değildir, font eksiktir.

    Çözüm, Unicode kapsayan bir TrueType font tanımlamaktır. "Standard"
    stiline dokunmuyoruz: bu çizim başka bir dosyaya INSERT/XREF edilirse
    hedef çizimin kendi Standard'ı bozulmasın. Kendi stilimizi kurup
    yazılarda ve ölçülerde onu kullanıyoruz; kullanıcı isterse tek yerden
    (STYLE komutu, "PI3D") fontu değiştirebilir."""
    if YAZI_STILI in doc.styles:
        st = doc.styles.get(YAZI_STILI)
    else:
        st = doc.styles.add(YAZI_STILI, font=YAZI_FONTU)
    st.dxf.font = YAZI_FONTU
    try:
        # TrueType fontlar DXF'te iki yerden okunur: STYLE tablosundaki
        # dosya adı ve XDATA'daki font ailesi adı. İkincisi yazılmazsa
        # AutoCAD dosya adını SHX sanıp yine txt.shx'e düşebilir.
        st.set_extended_font_data(family=YAZI_AILESI, italic=False, bold=False)
    except Exception:
        pass
    try:
        doc.header["$TEXTSTYLE"] = YAZI_STILI
    except Exception:
        pass
    return YAZI_STILI


def dxf_kur(doc=None):
    # setup=False ÖNEMLİ: ezdxf'in hazır kurulumu metre/santimetre için
    # tasarlanmış EZDXF, EZ_M_100_H25_CM gibi ölçü stilleri kurar ve
    # bunlardan birini DOSYANIN AKTİF STİLİ yapar. O stillerde
    # dimlfac = 100'dür; dosya AutoCAD'de açılıp YENİ bir ölçü çizildiğinde
    # uzunluk 100 ile çarpılarak yazılır (45,80 mm -> "4580"). Bizim kendi
    # ölçülerimiz ayrı stil kullandığı için doğruydu, ama kullanıcının
    # sonradan çizdiği ölçüler bozuluyordu.
    doc = doc or ezdxf.new("R2010", setup=False)
    doc.header["$LWDISPLAY"] = 1            # çizgi kalınlıkları ekranda görünsün
    doc.header["$MEASUREMENT"] = 1          # metrik
    # BIRIM: 1 çizim birimi = 1 mm. $INSUNITS yazılmazsa AutoCAD dosyayı
    # "birimsiz" sayar; başka bir çizime INSERT/XREF edildiğinde hedef
    # çizimin birimine göre ölçekler (mm -> m eklenirse 1000 kat büyür,
    # ölçü yazıları çizgiye dönüşmüş olduğu için eski değerde kalır ve
    # "30 yazıyor ama 3000 ölçüyor" durumu çıkar).
    doc.header["$INSUNITS"] = 4             # 4 = millimeters
    doc.header["$LUNITS"] = 2               # ondalık
    doc.header["$DIMLUNIT"] = 2
    # Ölçü başlık değişkenleri birebir ölçek olsun: dosyada sonradan
    # çizilen ölçüler de mm cinsinden doğru yazsın.
    doc.header["$DIMLFAC"] = 1.0            # uzunluk çarpanı = 1
    doc.header["$DIMSCALE"] = 1.0
    doc.header["$DIMALTF"] = 1.0
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
    yazi_stili(doc)
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
    # Ölçü yazısının fontu: Ø, ° ve Türkçe harfler için TrueType.
    try:
        st.dxf.dimtxsty = yazi_stili(doc)
    except Exception:
        pass
    try:
        st.dxf.dimclrt = 3
        st.dxf.dimclrd = 4
        st.dxf.dimclre = 4
    except Exception:
        pass
    # Dosyanın AKTİF ölçü stili bu olsun: AutoCAD'de sonradan çizilen
    # ölçüler de mm ve 1:1 çıksın.
    try:
        doc.header["$DIMSTYLE"] = OLCU_STILI
        doc.header["$DIMTXT"] = h
        doc.header["$DIMLFAC"] = 1.0
        # Hazır "Standard" stili de birebir kalsın.
        if "Standard" in doc.dimstyles:
            doc.dimstyles.get("Standard").dxf.dimlfac = 1.0
    except Exception:
        pass
    return OLCU_STILI


def _yaz(msp, metin, x, y, h=4.0, kat="YAZI"):
    stil = YAZI_STILI if YAZI_STILI in msp.doc.styles else "Standard"
    e = msp.add_text(str(metin),
                     dxfattribs={"layer": kat, "height": h, "style": stil})
    e.set_placement((x, y))
    return e


def _yazi_siniri(e):
    """Çizilmiş bir yazının ÖLÇÜLMÜŞ sınırı; ölçülemezse None."""
    try:
        k = ezdxf.bbox.extents([e], fast=False)
        return None if not k.has_data else (k.extmin.x, k.extmin.y,
                                            k.extmax.x, k.extmax.y)
    except Exception:
        return None


def gorunus_ciz(msp, kenar, ox, oy, ad, h=4.0, olcu2=True, etiket=None,
                pay_x=4.0, pay_y=4.0):
    """Bir görünüşü çizer. (genişlik, yükseklik, dx, dy) döndürür; dx/dy,
    ham izdüşüm koordinatını çizim koordinatına taşıyan kaydırmadır."""
    xs = [p[0] for v in kenar.values() for c in v for p in c]
    ys = [p[1] for v in kenar.values() for c in v for p in c]
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    dx, dy = ox - min(xs), oy - min(ys)

    # Teknik resim kuralı: görünen çizgiyle aynı yere düşen gizli çizgi
    # ÇİZİLMEZ (görünen kazanır). HLR görünen ve gizli kenarları ayrı ayrı
    # noktalara böldüğü için uç noktaları karşılaştırmak yetmez: aynı kenar
    # iki tarafta farklı noktalanmış olabilir. Bu yüzden her gizli parça,
    # yakınındaki görünen parçalarla tek tek karşılaştırılır; çakışan
    # BÖLÜMÜ kesilir, kalanı çizilir.
    #
    # Ölçüler HER ZAMAN karşılaştırılan iki parçanın kendi arasında alınır.
    # Doğrunun orijine dik uzaklığı gibi bir ölçü kullanılamaz: parça
    # montajda orijinden binlerce mm uzakta durabilir, o uzaklıkta yarım
    # derecelik bir örnekleme farkı dik uzaklığı on milimetrelerce kaydırır
    # ve aynı kenar iki ayrı kenar gibi görünür.
    AC_TOL, UZ_TOL = 0.02, 0.12          # paralellik (sinüs), mm
    EN_KISA = 0.05                       # bundan kısa kalıntı çizilmez, mm
    enb = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    HUCRE = max(0.5, enb / 400.0)        # kaba arama ızgarasının göz boyu
    gx0, gy0 = min(xs), min(ys)

    def _hucreler(a, b):
        """Parçanın geçtiği ızgara gözleri."""
        n = int(math.dist(a, b) / HUCRE) + 1
        return {(int((a[0] + (b[0] - a[0]) * i / n - gx0) // HUCRE),
                 int((a[1] + (b[1] - a[1]) * i / n - gy0) // HUCRE))
                for i in range(n + 1)}

    izgara, gor_par = defaultdict(list), []
    for c in kenar.get("GORUNEN", []):
        for a, b in zip(c, c[1:]):
            if math.dist(a, b) < 1e-9:
                continue
            k = len(gor_par)
            gor_par.append((a, b))
            # Gözleri bir kademe genişlet: göz sınırına denk gelen parça
            # kaçmasın (aradığımız kayma 0,12 mm, göz ondan çok büyük).
            for cx, cy in {(h[0] + i, h[1] + j) for h in _hucreler(a, b)
                           for i in (-1, 0, 1) for j in (-1, 0, 1)}:
                izgara[(cx, cy)].append(k)

    def _kalan(a, b):
        """Gizli parçanın görünenle ÇAKIŞMAYAN bölümleri; nokta çiftleri."""
        L = math.dist(a, b)
        if L < 1e-9:
            return []
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        aday = set()
        for h in _hucreler(a, b):
            aday.update(izgara.get(h, ()))
        kapali = []
        for i in aday:
            c, d = gor_par[i]
            vx, vy = d[0] - c[0], d[1] - c[1]
            m = math.hypot(vx, vy)
            if abs(ux * vy - uy * vx) > AC_TOL * m:
                continue                             # paralel değil
            # c ve d, gizli parçanın doğrusuna ne kadar uzakta?
            if abs(ux * (c[1] - a[1]) - uy * (c[0] - a[0])) > UZ_TOL:
                continue
            if abs(ux * (d[1] - a[1]) - uy * (d[0] - a[0])) > UZ_TOL:
                continue
            g0 = (c[0] - a[0]) * ux + (c[1] - a[1]) * uy
            g1 = (d[0] - a[0]) * ux + (d[1] - a[1]) * uy
            p, q = max(0.0, min(g0, g1)), min(L, max(g0, g1))
            if q > p:
                kapali.append((p, q))
        if not kapali:
            return [(a, b)]
        kapali.sort()
        birlesik = [list(kapali[0])]
        for p, q in kapali[1:]:
            if p <= birlesik[-1][1] + 1e-9:
                birlesik[-1][1] = max(birlesik[-1][1], q)
            else:
                birlesik.append([p, q])
        aralik, onceki = [], 0.0
        for p, q in birlesik:
            if p - onceki > EN_KISA:
                aralik.append((onceki, p))
            onceki = max(onceki, q)
        if L - onceki > EN_KISA:
            aralik.append((onceki, L))
        return [((a[0] + p * ux, a[1] + p * uy),
                 (a[0] + q * ux, a[1] + q * uy)) for p, q in aralik]

    def _ciz(par):
        if len(par) > 1:
            msp.add_lwpolyline([(x + dx, y + dy) for x, y in par],
                               dxfattribs={"layer": "GIZLI"})

    for kat, poli in kenar.items():
        for c in poli:
            if kat != "GIZLI":
                msp.add_lwpolyline([(x + dx, y + dy) for x, y in c],
                                   dxfattribs={"layer": kat})
                continue
            # Görünen kenarla üst üste düşen gizli bölümleri kes, kalan
            # kesintisiz parçaları ayrı çizgi olarak çiz.
            par = []
            for a, b in zip(c, c[1:]):
                for p, q in _kalan(a, b):
                    if par and abs(par[-1][0] - p[0]) < 1e-7 \
                           and abs(par[-1][1] - p[1]) < 1e-7:
                        par.append(q)
                    else:
                        _ciz(par)
                        par = [p, q]
            _ciz(par)
    G, Y = max(xs) - min(xs), max(ys) - min(ys)
    # Etiket görünüşün SOL ÜST köşesinde, parçanın ve ölçülerin dışında.
    _yaz(msp, etiket or GORUNUS_AD.get(ad, ad), ox, oy + Y + 0.7 * h, 1.3 * h)
    if olcu2:
        # Gabari ölçüsü EN DIŞARIDA durur: konum ölçüleri varsa onların
        # dışına itilir. Teknik resimde küçük ölçüler içeride, toplam
        # ölçü en dışarıdadır; tersi olursa ölçü çizgileri kesişir.
        msp.add_linear_dim(base=(ox, oy - pay_x * h), p1=(ox, oy),
                           p2=(ox + G, oy), dimstyle=OLCU_STILI,
                           dxfattribs={"layer": "OLCU"}).render()
        msp.add_linear_dim(base=(ox - pay_y * h, oy), p1=(ox, oy),
                           p2=(ox, oy + Y), angle=90, dimstyle=OLCU_STILI,
                           dxfattribs={"layer": "OLCU"}).render()
    return G, Y, dx, dy


def _cakisiyor(k, digerleri, pay=0.0):
    """İki dikdörtgen (x0, y0, x1, y1) üst üste biniyor mu?"""
    for d in digerleri:
        if (k[0] - pay < d[2] and k[2] + pay > d[0]
                and k[1] - pay < d[3] and k[3] + pay > d[1]):
            return True
    return False


def _varlik_kutulari(msp):
    """Resimdeki her varlığın ÖLÇÜLMÜŞ sınırı. Yer ayırırken kullanılır."""
    try:
        return [(k.extmin.x, k.extmin.y, k.extmax.x, k.extmax.y)
                for k in ezdxf.bbox.multi_flat(list(msp)) if k.has_data]
    except Exception:
        return []


def _yazi_kutulari(msp):
    """Resimdeki her YAZININ ölçülmüş sınırı; ölçü bloklarının içindeki
    rakamlar da dâhil.

    _varlik_kutulari yerine bunun gerektiği yer var: bir simge parçanın
    KENDİ konturuna değecek şekilde konuyorsa (datum üçgeni yüzeyin
    çizgisine oturur), varlık kutusuyla bakmak her yeri dolu gösterir -
    görünüşün sınır kutusu bütün görünüştür. Sorulacak doğru soru,
    simgenin bir YAZIYI kapatıp kapatmadığıdır."""
    out = []
    for e in msp:
        t = e.dxftype()
        if t in ("TEXT", "MTEXT"):
            k = _yazi_siniri(e)
            if k:
                out.append(k)
        elif t == "DIMENSION":
            try:
                for v in e.virtual_entities():
                    if v.dxftype() in ("TEXT", "MTEXT"):
                        k = _yazi_siniri(v)
                        if k:
                            out.append(k)
            except Exception:
                pass
    return out


def _olcu_yazi_kutusu(dim):
    """Çizilmiş bir ölçünün YAZISININ gerçek sınırı.

    Ölçünün çizgileri değil, yalnız yazısı: çakışmayı yaratan odur,
    kılavuz çizgisinin bir şeyin üstünden geçmesi normaldir."""
    try:
        kut = [ezdxf.bbox.extents([v], fast=False)
               for v in dim.dimension.virtual_entities()
               if v.dxftype() in ("TEXT", "MTEXT")]
        kut = [k for k in kut if k.has_data]
        if not kut:
            return None
        return (min(k.extmin.x for k in kut), min(k.extmin.y for k in kut),
                max(k.extmax.x for k in kut), max(k.extmax.y for k in kut))
    except Exception:
        return None


def _olcu_sil(msp, dim):
    """Yeri tutmayan ölçüyü resimden kaldırır, bloğunu da bırakmaz."""
    try:
        e = dim.dimension
        ad = e.dxf.get("geometry", None)
        msp.delete_entity(e)
        if ad and ad in msp.doc.blocks:
            msp.doc.blocks.delete_block(ad, safe=False)
    except Exception:
        pass


def cap_olculeri(msp, o, yer, kaydir, gkutu, h, ust, en_cok_grup=8):
    """Delik çapı ve kenar radüsü ölçüleri.

    Ölçü çizgisi deliğin/yuvarlamanın merkezinden geçer (dimtofl=1). Yazı
    deliğin HEMEN YANINA, kısa bir kılavuz çizgisiyle konur: önce 45°'lik
    köşegenler denenir (çizim geleneği), yer tutulmuşsa sırayla başka yön
    ve biraz daha uzak nokta denenir. Böylece yazı ne görünüşün üstüne
    biner ne de gereksiz uzağa kaçar.
    Aynı ölçüdeki delikler tek ölçüyle verilir, adet önüne konur: "2x Ø9".

    İKİ ŞEY TAHMİN EDİLMEZ, ÖLÇÜLÜR:
    1. Resimde hâlihazırda ne varsa (görünüş çizgileri, etiketler ve
       ÇİZGİSEL ÖLÇÜ YAZILARI) sınırları ölçülür ve dolu sayılır. Eskiden
       yalnız görünüş kutusu ve daha önce konan Ø/R yazıları biliniyordu;
       "34,5" gibi bir çizgisel ölçünün yazısı hesaba katılmadığı için
       üstüne "4x R3.5" biniyordu.
    2. Yazı çizildikten SONRA gerçek yeri ölçülür. Tahmin tutmazsa ölçü
       silinir ve bir sonraki aday yer denenir. Yazının kâğıtta kapladığı
       yer ölçü stiline ve yazı tipine bağlıdır; hesapla bulunmaz."""
    kova = defaultdict(list)
    for tip, liste in (("cap", o.get("delikler") or []), ("radus", o.get("radusler") or [])):
        for d in liste:
            gad = next((g for g in DELIK_GOR.get(d["eksen"], ()) if g in yer), None)
            if not gad or not d.get("merkezler"):
                continue
            r = (d["cap_mm"] / 2.0) if tip == "cap" else d["yaricap_mm"]
            if r < 0.5 or len(kova[gad]) >= en_cok_grup:
                continue
            kova[gad].append((tip, d, r))
    # Denenecek yönler: köşegenler önce, sonra dik yönler.
    YON = [45, 135, 225, 315, 90, 270, 0, 180]
    en_ust = dict(ust)
    en_sag = max(k[2] for k in gkutu.values())
    mevcut = _varlik_kutulari(msp)      # resimde şu an ne varsa, ölçülmüş
    for gad, gruplar in kova.items():
        dx, dy = kaydir[gad]
        gk = gkutu[gad]
        # Görünüşün kendisi, etiketi ve çevresindeki her şey doludur.
        et = GORUNUS_AD.get(gad, gad)
        etiket_k = (gk[0], gk[3] + 0.7 * h,
                    gk[0] + len(et) * 0.72 * 1.3 * h, gk[3] + 2.0 * h)
        yakin = (gk[0] - 14 * h, gk[1] - 14 * h, gk[2] + 14 * h, gk[3] + 14 * h)
        # ÖBÜR GÖRÜNÜŞLER DE DOLUDUR. Yer bulamayan bir yazı yukarı
        # tırmanırken kendi görünüşünün alanından çıkıp komşusunun
        # içine düşebiliyor: gerçek montajda ÜST görünüşün deliğine ait
        # "R5.06" yazısı 85 mm yukarı tırmanıp ÖN görünüşün konturuna
        # oturmuştu. Yakın çevre süzgeci o mesafeyi görmüyordu.
        dolu = ([gk, etiket_k] + [v for a, v in gkutu.items() if a != gad]
                + [b for b in mevcut if _cakisiyor(b, [yakin])])
        gruplar.sort(key=lambda q: -q[2])
        for tip, d, r in gruplar:
            noktalar = [(p[0] + dx, p[1] + dy)
                        for p in (izdusum(c, gad) for c in d["merkezler"])]
            # Görünüşün ortasına en uzak delik: yazı dışarı doğru çıksın.
            mx, my = (gk[0] + gk[2]) / 2.0, (gk[1] + gk[3]) / 2.0
            x, y = max(noktalar, key=lambda q: (q[0] - mx) ** 2 + (q[1] - my) ** 2)
            onek = f"{d['adet']}x " if d["adet"] > 1 else ""
            metin = (f"{onek}%%c{d['cap_mm']:g}" if tip == "cap"
                     else f"{onek}R{d['yaricap_mm']:g}")
            yw, yy = len(metin) * 0.72 * h, 1.3 * h       # yazı kutusu
            adaylar, yazi_yeri = [], None
            for uz_k in range(7):                          # uzaklık kademeleri
                uz = r + (1.8 + 1.3 * uz_k) * h
                for a in YON:
                    ra = math.radians(a)
                    px, py = x + math.cos(ra) * uz, y + math.sin(ra) * uz
                    # Yazının hangi yöne doğru yazılacağı ölçü stiline göre
                    # değişebildiğinden iki yana da yer ayrılır; böylece
                    # hangi hizalama kullanılırsa kullanılsın çakışma olmaz.
                    k = (px - yw, py - yy / 2, px + yw, py + yy / 2)
                    if not _cakisiyor(k, dolu, 0.3 * h):
                        adaylar.append(((px, py), k))
                        yazi_yeri = True
                        if len(adaylar) >= 6:
                            break
                if len(adaylar) >= 6:
                    break
            # Yakında yer yoksa görünüşün üstüne, boş satır bulana dek
            # yukarı çıkarak. Buradan her zaman bir yer çıkar; ölçü
            # düşürmek son çaredir, düşen ölçü eksik resim demektir.
            py = en_ust.get(gad, gk[3]) + 1.2 * h
            for _ in range(14):
                k = (x - yw, py - yy / 2, x + yw, py + yy / 2)
                if not _cakisiyor(k, dolu, 0.3 * h):
                    adaylar.append(((x, py), k))
                py += 1.6 * h
            # Hiçbir yere sığmadıysa kılavuzu uzatıp görünüşün soluna
            # koy: orası her zaman boştur, kaçacak komşu yoktur.
            if not adaylar:
                px = gk[0] - 2.0 * yw
                for _ in range(10):
                    k = (px - yw, y - yy / 2, px + yw, y + yy / 2)
                    if not _cakisiyor(k, dolu, 0.3 * h):
                        adaylar.append(((px, y), k))
                        break
                    px -= 1.4 * yw
            ovr = {"dimtofl": 1, "dimtad": 0, "dimtix": 0, "dimtmove": 1,
                   "dimatfit": 3, "dimgap": h * 0.3,
                   # dimtoh/dimtih = 1: yazı HER ZAMAN YATAY.
                   # Bu bir süsleme değil, çakışmanın kaynağıydı: yazı
                   # ölçü çizgisiyle dönünce yukarıda yatay olarak
                   # ayrılan yer tutmuyor, kılavuz dikleşince yazı
                   # görünüşün konturuna biniyordu.
                   "dimtoh": 1, "dimtih": 1}
            kutu_y = None
            for yer_d, kaba in adaylar:
                try:
                    if tip == "cap":
                        dim = msp.add_diameter_dim(
                            center=(x, y), radius=r, location=yer_d,
                            dimstyle=OLCU_STILI, override=ovr, text=metin,
                            dxfattribs={"layer": "OLCU"})
                    else:
                        dim = msp.add_radius_dim(
                            center=(x, y), radius=r, location=yer_d,
                            dimstyle=OLCU_STILI, override=ovr, text=metin,
                            dxfattribs={"layer": "OLCU"})
                    dim.render()
                except Exception:
                    kutu_y = None
                    continue
                gercek = _olcu_yazi_kutusu(dim)
                if gercek is None or not _cakisiyor(gercek, dolu, 0.3 * h):
                    kutu_y = gercek or kaba
                    break
                _olcu_sil(msp, dim)      # yeri tutmadı, bir sonrakini dene
                kutu_y = None
            if kutu_y is None:
                continue                 # hiçbir yere sığmadı: yazma
            dolu.append(kutu_y)
            en_ust[gad] = max(en_ust.get(gad, gk[3]), kutu_y[3] + 0.6 * h)
            en_sag = max(en_sag, kutu_y[2] + h)
    return en_ust, en_sag


# Konum ölçüsü: bir dizi sayılabilmesi için en az bu kadar delik gerek.
DIZI_EN_AZ = 3
DIZI_PAY = 0.02          # adımlar bu oranda tutuyorsa dizi sayılır
KONUM_EN_COK = 6         # dizi değilse görünüş başına en çok bu kadar delik


def _dizi(v, pay=DIZI_PAY):
    """Sıralı koordinatlar eşit aralıklı bir dizi mi?

    Döner: (adet, adım) ya da None. Bir sacta 124 delik 20 mm arayla
    dizilmişse her birine ayrı konum ölçüsü konmaz - konamaz da, resim
    okunmaz olur. Onun yerine kenardan ilk deliğe, sonra "123 x 20"
    zinciri, sonra son delikten kenara yazılır."""
    if len(v) < DIZI_EN_AZ:
        return None
    a = [v[i + 1] - v[i] for i in range(len(v) - 1)]
    ort = sum(a) / len(a)
    if ort <= 1e-6:
        return None
    if max(abs(x - ort) for x in a) <= max(0.05, pay * ort):
        return (len(v), ort)
    return None


def _kenar_kutusu(kenar):
    """Bir görünüşün HAM izdüşüm sınırı (x0, y0, x1, y1)."""
    xs, ys = [], []
    for grup in kenar.values():
        for p in grup:
            for q in p:
                xs.append(q[0]); ys.append(q[1])
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _yazi_eni(v, h, metin=None):
    """Ölçü yazısının kaplayacağı genişlik (mm), kabaca ama tutarlı."""
    t = metin if metin is not None else f"{v:.1f}".rstrip("0").rstrip(".")
    return max(1.0, len(t)) * 0.62 * h * 1.15


def _seviyele(araliklar, h):
    """Her ölçüyü çakışmayacağı ilk kademeye koyar.

    Kısa bir aralığın yazısı aralıktan geniştir: "3,2" yazısı 3,2 mm'ye
    sığmaz, komşusunun üstüne biner. Gerçek resimde de böyle ölçüler
    alt alta kademelendirilir. Kademe sayısı sonra gabari ölçüsünü ne
    kadar dışarı iteceğimizi söyler."""
    kademe = []                       # her kademede dolu [x0, x1] aralıkları
    # Datumdan ölçülerde hepsi aynı kenardan başlar ve iç içe geçer;
    # kısa olan içeride durmalı. Sıra çağıran tarafta verilir.
    for r in araliklar:
        a, b = min(r["a"], r["b"]), max(r["a"], r["b"])
        orta = (a + b) / 2.0
        en = max(b - a, _yazi_eni(b - a, h, r.get("metin")))
        k0, k1 = orta - en / 2, orta + en / 2
        for i, dolu in enumerate(kademe):
            if all(k1 <= d0 or k0 >= d1 for d0, d1 in dolu):
                dolu.append((k0, k1)); r["seviye"] = i + 1
                break
        else:
            kademe.append([(k0, k1)]); r["seviye"] = len(kademe)
    return len(kademe)


# ------------------------------------------------- kapalı kontur (halka) çıkarımı
# HLR görünüşü ayrık parçalar hâlinde verir; hangi parçanın hangisiyle bir
# halka kurduğunu söylemez. Girinti/çıkıntı ölçüsü için KAPALI KONTUR şart:
# parçanın dış hattı bilinmeden neyin girinti olduğu söylenemez.
HALKA_TOL = 0.02          # mm; iki ucun çakıştığı sayılacağı en büyük aralık


def _dugumle(noktalar, tol=HALKA_TOL):
    """Birbirine değen uçları tek düğümde toplar.

    Koordinatı yuvarlamak tek başına YETMEZ: hücre sınırına düşen iki uç
    ayrı hücrelere gider ve halka orada kopar. Komşu dokuz hücreye de
    bakılır.

    Döner: (her noktanın düğüm indeksi, düğüm koordinatları)."""
    hucre, dugum, out = {}, [], []
    for q in noktalar:
        i = (int(math.floor(q[0] / tol)), int(math.floor(q[1] / tol)))
        bul = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in hucre.get((i[0] + dx, i[1] + dy), ()):
                    r = dugum[j]
                    if (r[0] - q[0]) ** 2 + (r[1] - q[1]) ** 2 <= tol * tol:
                        bul = j
                        break
                if bul is not None:
                    break
            if bul is not None:
                break
        if bul is None:
            bul = len(dugum)
            dugum.append(q)
            hucre.setdefault(i, []).append(bul)
        out.append(bul)
    return out, dugum


def halkalar(kenar, katman=("GORUNEN",), tol=HALKA_TOL, en_cok_kenar=6000,
             kaynak=False):
    """Görünüşteki bütün KAPALI halkalar.

    Uçtan uca zincirleme YETMEZ, denedik: üç ya da daha çok parçanın
    buluştuğu düğümde (teğet geçiş, çakışan kenar, ortak köşe) hangisiyle
    devam edileceği belirsizdir; zincir ya yanlış dallanır ya hiç kapanmaz.
    İlk denemede ya 0 halka ya da her şeyi yutan tek bir halka çıkıyordu.

    Doğrusu DÜZLEMSEL YÜZ DOLAŞIMI: her düğümde çıkan yarı-kenarlar açıya
    göre sıralanır; bir yarı-kenarla düğüme varınca, onun TERSİNİN açısal
    sıradaki bir öncekiyle devam edilir. Bu kural düzlemsel bir çizgede
    her yüzü tam bir kez dolaşır; dallanma ve çakışma bozmaz. Her halka
    biri artı biri eksi alanlı olmak üzere iki kez çıkar - dış hat
    EN EKSİ alanlı olandır.

    Dolaşımdan önce iki temizlik şart; ikisi de ölçülerek bulundu:
      * kopya kenar (HLR aynı çizgiyi iki kez verir),
      * asılı kenar (bir ucu boşta biten siluet çizgisi).

    Döner: [[(x, y), ...], ...]; kaynak=True ise [(noktalar, kenarlar)]
    - kenarlar[i], noktalar[i] -> noktalar[i+1] parçasının geldiği HLR
    kenarıdır (doğru mu yay mı, oradan anlaşılır)."""
    parca = [q for kat in katman for q in (kenar.get(kat) or ())
             if len(q) >= 2]
    if not parca or len(parca) > en_cok_kenar:
        return []
    parca = _kopya_at(parca, tol)
    parca = _asili_buda(parca, tol)
    n = len(parca)
    if n < 2:
        return []
    dug, _yer = _dugumle([p for q in parca for p in (q[0], q[-1])], tol)
    bas = [0] * (2 * n); son = [0] * (2 * n); aci = [0.0] * (2 * n)
    for i, q in enumerate(parca):
        a, b = dug[2 * i], dug[2 * i + 1]
        bas[2 * i], son[2 * i] = a, b
        bas[2 * i + 1], son[2 * i + 1] = b, a
        aci[2 * i] = math.atan2(q[1][1] - q[0][1], q[1][0] - q[0][0])
        aci[2 * i + 1] = math.atan2(q[-2][1] - q[-1][1], q[-2][0] - q[-1][0])
    cikan = defaultdict(list)
    for hh in range(2 * n):
        cikan[bas[hh]].append(hh)
    sira = {}
    for _d, hs in cikan.items():
        hs.sort(key=lambda hh: aci[hh])
        for k, hh in enumerate(hs):
            sira[hh] = k

    def sonraki(hh):
        ters = hh ^ 1                  # varış düğümünden çıkan ters yarı-kenar
        hs = cikan[son[hh]]
        return hs[(sira[ters] - 1) % len(hs)]

    gorulen, cikti = set(), []
    for h0 in range(2 * n):
        if h0 in gorulen:
            continue
        dizi, hh = [], h0
        while hh not in gorulen:
            gorulen.add(hh)
            dizi.append(hh)
            hh = sonraki(hh)
        # Budamadan sonra kalan tek çift geçiş köprü kenarlarıdır (iki
        # halkayı birbirine bağlayan çizgi); onlar da yüz sınırı değil.
        if len(set(hh2 >> 1 for hh2 in dizi)) != len(dizi):
            continue
        nokta, kay = [], []
        for hh2 in dizi:
            q = parca[hh2 >> 1]
            ek = (q if not (hh2 & 1) else q[::-1])[:-1]
            nokta += ek
            kay += [q] * len(ek)
        if len(nokta) >= 3:
            cikti.append((nokta, kay) if kaynak else nokta)
    return cikti


def _kopya_at(parca, tol=HALKA_TOL):
    """Aynı kenarın ikinci kopyasını atar.

    HLR aynı çizgiyi iki kez verebilir: VCompound ile OutLineVCompound
    çakışır. İkinci kopya düzlemsel dolaşımda sıfır alanlı sahte bir yüz
    yaratır ve dış hattı yutar. Ölçtük: 01.051.000.01'in ÖN görünüşünde
    alt kenar iki kez geliyor, dış hattın alanı 85560 yerine 0 çıkıyordu."""
    dug, _yer = _dugumle([p for q in parca for p in (q[0], q[-1])], tol)
    gor, tek = set(), []
    for i, q in enumerate(parca):
        a, b = dug[2 * i], dug[2 * i + 1]
        uz = sum(math.dist(q[j], q[j + 1]) for j in range(len(q) - 1))
        o = q[len(q) // 2]
        im = (min(a, b), max(a, b), round(uz, 3),
              round(o[0], 2), round(o[1], 2))
        if im not in gor:
            gor.add(im)
            tek.append(q)
    return tek


def _asili_buda(parca, tol=HALKA_TOL):
    """Bir ucu boşta biten kenarları atar.

    Asılı kenar hiçbir yüzün sınırı değildir: dolaşımda gidilip geri
    dönülerek geçilir ve halkayı görünüşün dört köşesine kadar
    sürükler; alanı sıfıra yakın, sınır kutusu bütün görünüş olan sahte
    bir "dış hat" çıkar. HLR eğri yüzeylerde bunlardan bol bol verir -
    ölçtük: 01.050.000.14'ün ÖN görünüşünde 122 açık uç.

    Budama yinelemelidir: bir kenar kalkınca komşusu açıkta kalabilir."""
    dug, _yer = _dugumle([p for q in parca for p in (q[0], q[-1])], tol)
    n = len(parca)
    derece = Counter()
    for i in range(n):
        derece[dug[2 * i]] += 1
        derece[dug[2 * i + 1]] += 1
    canli = [True] * n
    degisti = True
    while degisti:
        degisti = False
        for i in range(n):
            if not canli[i]:
                continue
            a, b = dug[2 * i], dug[2 * i + 1]
            if a == b:                 # kendine kapanan kenar: asılı değil
                continue
            if derece[a] <= 1 or derece[b] <= 1:
                canli[i] = False
                derece[a] -= 1
                derece[b] -= 1
                degisti = True
    return [q for i, q in enumerate(parca) if canli[i]]


def dis_kontur(kenar, katman=("GORUNEN",), tol=HALKA_TOL, kaynak=False):
    """Görünüşün DIŞ HATTI; saat yönünün tersine. Bulunamazsa None.

    Dış hat, yüz dolaşımının EN EKSİ alanlı halkasıdır: dışarıdaki
    sonsuz yüz, parçanın çevresini ters yönde dolaşır. "En büyük artı
    alanlı halka" demek yanlış olurdu - iç çizgileri olan bir görünüşte
    (C profil, büküm çizgisi) parçanın içi birkaç yüze bölünür ve
    hiçbiri tek başına dış hattı vermez.

    kaynak=True ise (noktalar, kenarlar) döner; bkz. halkalar."""
    hl = halkalar(kenar, katman, tol, kaynak=True)
    if not hl:
        return None
    a, h, ky = min(((_cokgen_alani(q), q, k) for q, k in hl),
                   key=lambda t: t[0])
    if a >= 0:
        return None
    n_ = len(h)
    h = h[::-1]
    # Ters çevrilen halkada i. parça, eskisinin (n-2-i). parçasıdır.
    ky = [ky[(n_ - 2 - i) % n_] for i in range(n_)]
    # DENETİM: dış hat görünüşün dört kenarına da DEĞMELİ.
    # Dövme/döküm parçalarda HLR'nin siluet kenarları havada biter
    # (ölçtük: 01.050.000.14'ün ÖN görünüşünde 122 açık uç); o zaman
    # dolaşım kapalı bir halka bulur ama o halka parçanın dış hattı
    # değil, içerideki küçük bir çevrimdir. Böyle bir halkadan
    # çıkarılacak girinti/çıkıntı ölçüsü yanlış olurdu; hiç vermemek
    # yeğdir.
    gk = _kenar_kutusu(kenar)
    if not gk:
        return None
    hk = (min(q[0] for q in h), min(q[1] for q in h),
          max(q[0] for q in h), max(q[1] for q in h))
    pay = max(0.05, 0.004 * max(gk[2] - gk[0], gk[3] - gk[1]))
    if any(abs(hk[i] - gk[i]) > pay for i in range(4)):
        return None
    return (h, ky) if kaynak else h


GIRINTI_EN_AZ_ORAN = 0.02   # görünüşün uzun kenarına göre en küçük anlamlı girinti
GIRINTI_EN_COK = 5          # bir görünüşte ölçülecek en çok girinti
GIRINTI_SINIR = 12          # bundan fazlası girinti değil, biçimin kendisidir


def kontur_ozellikleri(dis, kutu_, en_az_oran=GIRINTI_EN_AZ_ORAN,
                       en_cok=GIRINTI_EN_COK, sinir=GIRINTI_SINIR, duz=None):
    """Dış konturun GİRİNTİ ve ÇIKINTILARI.

    Gabari ölçüsü parçanın o yöndeki en uç noktalarını verir; kenarın
    ortasından alınmış bir çentiğin ya da dışarı taşan bir kulağın nerede
    başlayıp nerede bittiğini söylemez. Atölyenin ihtiyacı olan da odur:
    delik konumu gibi girinti konumu da ölçülendirilir.

    YÖNTEM - YAKIN ZARF. Kenar boyunca adım adım ilerlenir ve her adımda
    konturun o kenara EN YAKIN noktasının uzaklığı yazılır. Kenara değen
    adımlar parçanın o kenara oturduğu yerlerdir; aralarında kalan
    değmeyen diziler girintidir.

    Halkayı dolaşıp "kenardan uzaklaşan diziyi girinti say" demek
    YANLIŞTIR, denedik: dikdörtgen bir görünüşte halka alt kenardan
    ayrılıp üst kenardan geçip döner ve bütün kenar "175 mm boyunda,
    5 mm derinliğinde girinti" diye çıkar. Karşı kenar girinti değildir;
    sorulacak olan, kenarın her noktasının KARŞISINDA konturun ne kadar
    yakından geçtiğidir.

    Çıkıntı ayrı bir durum değildir: dışarı taşan bir kulak gabariyi
    kendi ucuyla belirlediği için iki yanı girinti olarak çıkar ve
    verilen ölçüler kulağın yerini verir - istenen de budur.

    Kapılar, eğik kesimde öğrendiğimizle aynı: görünüşün %2'sinden sığ ya
    da dar çentik gürültüdür; sayısı GIRINTI_SINIR'ı aşıyorsa o kenar
    "düz kenar + çentik" değil, biçimin kendisidir - ölçülmez.

    SANAL KÖŞE. Çentiğin ağzı yuvarlatılmışsa (teğet yay), kontur
    kenardan yayın TEĞET NOKTASINDA ayrılır. Ressam oraya ölçü vermez;
    yayın öbür ucundaki DOĞRU kenarı kenara uzatır ve ölçüyü o kesişme
    noktasına, yani sanal keskin köşeye verir - tasarımın asıl ölçüsü
    odur, yay sonradan kırılmış bir kenardır. Ölçtük: Dachplatte'nin
    köşe kesiği teğet noktalarında 41,09 / 22,51 çıkıyordu; kesik
    doğrusu uzatılınca 45,0 / 20,05 - yani 20 x 5'lik bir kesik.
    `duz[i]`, i. parçanın (dis[i] -> dis[i+1]) doğru bir kenardan gelip
    gelmediğini söyler; verilmezse her parça doğru sayılır.

    Döner: [{"taraf", "yon", "a", "b", "derinlik", "ic"}]; a ile b,
    ölçünün alınacağı yöndeki HAM izdüşüm koordinatlarıdır."""
    if not dis or not kutu_:
        return []
    x0, y0, x1, y1 = kutu_
    buyuk = max(x1 - x0, y1 - y0)
    if buyuk <= 0:
        return []
    tol = max(0.05, 0.004 * buyuk)
    en_az = en_az_oran * buyuk
    adim = max(tol, buyuk / 800.0)
    n = len(dis)
    out = []
    for taraf, yon, uzak, boy, e0, e1 in (
            ("alt", "yatay", lambda q: q[1] - y0, lambda q: q[0], x0, x1),
            ("ust", "yatay", lambda q: y1 - q[1], lambda q: q[0], x0, x1),
            ("sol", "dusey", lambda q: q[0] - x0, lambda q: q[1], y0, y1),
            ("sag", "dusey", lambda q: x1 - q[0], lambda q: q[1], y0, y1)):
        boyu = e1 - e0
        if boyu <= 0:
            continue
        K = max(16, min(2000, int(boyu / adim) + 1))
        zarf = [None] * K
        # Örnek aralığı kutucuğun ÜÇTE BİRİ. Kutucuk kadar olunca bazı
        # kutucuklara kenarın kendisinden hiç örnek düşmüyor, yalnız karşı
        # kenardan düşüyordu: 120 x 80'lik düz dikdörtgenin üst kenarında
        # 48 tane "80 mm derin" sahte girinti çıktı.
        for i in range(n):
            p, q = dis[i], dis[(i + 1) % n]
            m = max(1, int(3.0 * math.dist(p, q) / adim) + 1)
            for j in range(m):
                t = j / m
                r = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
                kk = min(K - 1, max(0, int((boy(r) - e0) / boyu * K)))
                d = uzak(r)
                if zarf[kk] is None or d < zarf[kk]:
                    zarf[kk] = d
        # Örnek düşmeyen kutucuğu komşusundan doldur (iki yönde).
        onceki = None
        for kk in range(K):
            if zarf[kk] is None:
                zarf[kk] = onceki
            else:
                onceki = zarf[kk]
        onceki = None
        for kk in range(K - 1, -1, -1):
            if zarf[kk] is None:
                zarf[kk] = onceki
            else:
                onceki = zarf[kk]
        if any(v is None for v in zarf):
            continue
        deger = [v <= tol for v in zarf]
        if not any(deger):
            continue
        # Kutucuk yaklaşık bir yer verir (± bir adım); resme yazılacak
        # ölçü TAM olmalı. Ölçtük: 50..70 arası çentik 50,2..69,8 diye
        # çıkıyordu. Uçlar, kenara değen GERÇEK kontur köşesine oturtulur:
        # boşluğun solundaki son, sağındaki ilk değen köşe. Boşluğun
        # içinde değen köşe olamaz (olsaydı o kutucuk değerdi), yani bu
        # iki köşe çentiğin tam başı ve sonudur. Kenarın ucuna dayanan
        # boşlukta o uç gabarinin kendisidir. Yaklaşık değer ASLA yazılmaz.
        #
        # "Değen" köşe gerçekten ÜSTÜNDE olandır (1 mikron): gabari
        # kutusu bu köşelerden hesaplandı. Kutucukların payı (tol) burada
        # kullanılmaz; 195 mm'lik parçada o 0,8 mm'dir ve kenara 0,5 mm
        # yaklaşan bir köşeyi yanlışlıkla çentiğin başı yapardı.
        degen = sorted((boy(q), i) for i, q in enumerate(dis)
                       if uzak(q) <= 1e-3)
        degen_b = [t[0] for t in degen]

        def sanal(i, ic_yon):
            """i. köşeden çentiğe doğru yürü; ilk DOĞRU parçayı kenara
            uzat. ic_yon: çentik büyük boy tarafındaysa +1, değilse -1."""
            v0 = boy(dis[i])
            if duz is None:
                return v0
            for yuru in (1, -1):
                j = (i + yuru) % n
                if (uzak(dis[j]) > 1e-3
                        and (boy(dis[j]) - v0) * ic_yon > -1e-9):
                    break
            else:
                return v0
            k = i
            for _ in range(n):
                sg = k if yuru == 1 else (k - 1) % n
                if duz[sg]:
                    if k == i:         # ilk parça zaten doğru: keskin köşe
                        return v0
                    p, q = dis[sg], dis[(sg + 1) % n]
                    up, uq = uzak(p), uzak(q)
                    if abs(uq - up) < 1e-9:
                        return v0      # kenara paralel: kesişme yok
                    t = up / (up - uq)
                    x = boy(p) + (boy(q) - boy(p)) * t
                    # Makul mü: çentik tarafında ve yayın boyunu aşmayan
                    # bir uzaklıkta olmalı.
                    if ((x - v0) * ic_yon >= -1e-6
                            and abs(x - v0) <= abs(boy(p) - v0) + tol):
                        return round(x, 4)
                    return v0
                k = (k + yuru) % n
                if k == i:
                    break
            return v0

        def bas_kose(v):
            i = bisect.bisect_right(degen_b, v + 1e-9) - 1
            return sanal(degen[i][1], 1) if i >= 0 else e0

        def son_kose(v):
            i = bisect.bisect_left(degen_b, v - 1e-9)
            return sanal(degen[i][1], -1) if i < len(degen) else e1

        def der_tam(a, b):
            """Çentiğin TAM derinliği; bulunamazsa None.

            Kutucuk zarfı en derin yeri eksik bulur - eğim dikleştikçe
            hata büyür: 6,33 x 17,67'lik köşe kesiğinde 15,73 çıkıyordu.
            Tam değer için zarf konturun KENDİSİNDEN kurulur: bir hizada
            konturu kesen her parça o hizada kesilir, kenara en yakını
            zarfın değeridir.

            Zarf parça parça doğrusaldır; en yüksek değeri bir köşenin
            hizasında olur. Ama tam köşenin hizasında değil, HEMEN YANINDA
            aranır: dik duvarlı çentikte dibin köşesi duvarın ayağıyla
            aynı hizadadır, zarf orada 0'dan 15'e SIÇRAR - tam hizada
            bakılınca derinlik 0 çıkıyordu."""
            parca = []
            for i in range(n):
                p, q = dis[i], dis[(i + 1) % n]
                bp, bq = boy(p), boy(q)
                if abs(bq - bp) < 1e-12:
                    continue           # kenara dik parça: zarfa girmez
                if max(bp, bq) < a - 1e-9 or min(bp, bq) > b + 1e-9:
                    continue
                parca.append((bp, uzak(p), bq, uzak(q)))
            olay = sorted({a, b} | {boy(q) for q in dis
                                    if a - 1e-9 <= boy(q) <= b + 1e-9})
            if len(olay) * len(parca) > 2_000_000:
                return None
            eps = 1e-7 * max(1.0, b - a)
            en = None
            for v in olay:
                for x in (v - eps, v + eps):
                    if not a < x < b:
                        continue
                    z = None
                    for bp, dp, bq, dq in parca:
                        if (bp - x) * (bq - x) > 0:
                            continue
                        w = dp + (dq - dp) * (x - bp) / (bq - bp)
                        z = w if z is None else min(z, w)
                    if z is not None:
                        en = z if en is None else max(en, z)
            return None if en is None else round(en, 4)

        kk = 0
        while kk < K:
            if deger[kk]:
                kk += 1
                continue
            j = kk
            while j < K and not deger[j]:
                j += 1
            if j - kk < 3:
                # Birkaç kutucukluk boşluk örnekleme artığıdır; gerçek
                # girinti en az GIRINTI_EN_AZ_ORAN kadardır (~16 kutucuk).
                kk = j
                continue
            a = e0 if kk == 0 else bas_kose(e0 + boyu * kk / K)
            b = e1 if j >= K else son_kose(e0 + boyu * j / K)
            der = max(zarf[kk:j])
            en = b - a
            # KÖŞE YUVARLAMASI GİRİNTİ DEĞİLDİR. Kenarın ucunda duran,
            # eni boyuna yakın küçük bir boşluk R'dir ya da pahtır;
            # ikisinin de ölçüsü resimde zaten var (R ölçüsü, "5 x 5"
            # notu). İkinci kez konum vermek ISO 129-1'in "tekrarlanan
            # öznitelik bir kez ölçülendirilir" kuralına aykırı olurdu.
            # Ölçtük: 175 x 100 plakada dört köşe R6,5 dört ayrı
            # girinti diye geliyordu.
            ucta = (a - e0 <= tol) or (e1 - b <= tol)
            kose = (ucta and der <= 0.15 * buyuk
                    and abs(en - der) <= 0.40 * max(en, der))
            if en >= en_az and der >= en_az and not kose:
                out.append({"taraf": taraf, "yon": yon,
                            "a": a, "b": b,
                            "derinlik": der_tam(a, b) if not ucta else None,
                            # İÇ çentik: iki ucu da kenara değiyor.
                            # Kenarın ucuna dayanan basamağın derinliği
                            # komşu kenarda ayrı bir girintinin KONUMU
                            # olarak zaten çıkar (köşe kesiği iki kenarda
                            # birden görünür); ikinci kez yazılmaz.
                            "ic": not ucta})
            kk = j
    if len(out) > sinir:
        return []
    out.sort(key=lambda r: -((r["b"] - r["a"]) * (r["derinlik"] or 0.0)))
    return out[:en_cok]


def gorunus_ozellikleri(kenar, kutu_):
    """Bir görünüşün girinti/çıkıntıları; kontur çıkarılamazsa boş.

    Her parçanın doğru mu yay mı olduğu kaynağı olan HLR kenarından
    anlaşılır: iki noktalı kenar doğrudur, çok noktalı kenar
    kenar_tani'ye sorulur (HLR doğruları da B-spline verebiliyor)."""
    dk = dis_kontur(kenar, kaynak=True)
    if not dk:
        return []
    dis, kay = dk
    sinif = {}
    duz = []
    for q in kay:
        k = id(q)
        if k not in sinif:
            sinif[k] = (len(q) == 2 or kenar_tani(q)["tip"] == "dogru")
        duz.append(sinif[k])
    return kontur_ozellikleri(dis, kutu_, duz=duz)


PENCERE_EN_COK = 4          # bir görünüşte konumu verilecek en çok iç pencere
PENCERE_EN_COK_HALKA = 400  # bundan çok halkalı görünüşte pencere aranmaz


def ic_pencereler(kenar, kutu_, en_az_oran=GIRINTI_EN_AZ_ORAN,
                  en_cok=PENCERE_EN_COK):
    """Görünüşün İÇİNDEKİ daire olmayan kapalı halkalar: yuva, pencere,
    cep. Girintinin iç hâli - kenara açılmıyor ama o da yer ister.

    Ölçtük: Dachplatte'de iki uzun yuva vardı, resimde yalnız "8x R1"
    yazıyordu; yuvaların NEREDE olduğu hiçbir yerden okunmuyordu.

    Pencere sayılan halka:
      * iç yüzü boş kalan (içinde başka halka yok) - yoksa parçanın bir
        yüzüdür, pencere değil (C profilin gövde yüzü delikleri içerir),
      * görünüşün dış kutusuna DEĞMEYEN,
      * hiçbir yönde görünüşün %60'ından büyük olmayan,
      * DAİRE OLMAYAN - daireler delik olarak 3B'den ölçülüyor,
      * dış hattın içinde kalan.

    Döner: [{"kutu": (x0, y0, x1, y1), "alan"}] - büyükten küçüğe."""
    if not kutu_:
        return []
    dis = dis_kontur(kenar)
    if not dis:
        return []
    hl, kay = [], []
    for q, k_ in halkalar(kenar, kaynak=True):
        if _cokgen_alani(q) > 0:
            hl.append(q)
            kay.append(k_)
    if len(hl) > PENCERE_EN_COK_HALKA:
        return []
    sinif = {}

    def islenmis(kaynaklar):
        """Halka yalnız DOĞRU ve YAYLARDAN mı oluşuyor? İşlenmiş ya da
        kesilmiş bir pencere böyledir. Serbest eğrili halka dövme/döküm
        yüzeyinin bir bölgesidir; ölçtük: Handhebel'de iç içe geçen iki
        eğri bölge "pencere" diye 149,16 / 157,43 gibi rastgele konumlar
        veriyordu."""
        for q in kaynaklar:
            k_ = id(q)
            if k_ not in sinif:
                sinif[k_] = (len(q) == 2
                             or kenar_tani(q)["tip"] in ("dogru", "yay"))
            if not sinif[k_]:
                return False
        return True
    x0, y0, x1, y1 = kutu_
    G, Y = x1 - x0, y1 - y0
    buyuk = max(G, Y)
    tol = max(0.05, 0.004 * buyuk)
    en_az = en_az_oran * buyuk
    kutular = [(min(q[0] for q in h), min(q[1] for q in h),
                max(q[0] for q in h), max(q[1] for q in h)) for h in hl]
    out = []
    for i, (h, k) in enumerate(zip(hl, kutular)):
        if (k[0] - x0 <= tol or k[1] - y0 <= tol
                or x1 - k[2] <= tol or y1 - k[3] <= tol):
            continue
        en, boy_ = k[2] - k[0], k[3] - k[1]
        if max(en, boy_) < en_az or en > 0.6 * G or boy_ > 0.6 * Y:
            continue
        # Kıl inceliğinde şerit pencere değil, iki çizgi arasındaki
        # boşluktur (ölçtük: 12 mm'lik parçada 4 x 0,33).
        if min(en, boy_) < 1.0 and min(en, boy_) < 0.1 * max(en, boy_):
            continue
        if not islenmis(kay[i]):
            continue
        # DAİRE Mİ? Yalnız köşelere bakmak YETMEZ: dikdörtgenin dört
        # köşesi tam bir çemberin üstündedir, 20 x 10'luk pencere "delik"
        # sayılıp atlanıyordu. Kenar ORTALARI da çembere yakın olmalı -
        # gerçek dairenin örneklemesinde sehim 0,1 mm'yi geçmez.
        c = _cember_uydur(h)
        if c:
            cx, cy, r, _s = c
            m_ = len(h)
            orta = [((h[t][0] + h[(t + 1) % m_][0]) / 2.0,
                     (h[t][1] + h[(t + 1) % m_][1]) / 2.0) for t in range(m_)]
            sap = max(abs(math.hypot(x - cx, y - cy) - r)
                      for x, y in list(h) + orta)
            if sap <= max(0.12, 0.01 * r):
                continue               # daire: delik
        if not _nokta_icinde(h[0], dis) and not _nokta_icinde(
                ((k[0] + k[2]) / 2.0, (k[1] + k[3]) / 2.0), dis):
            continue
        # Yaprak mı: içinde başka bir halka var mı?
        dolu = False
        for j, (h2, k2) in enumerate(zip(hl, kutular)):
            if j == i or k2[0] < k[0] - 1e-6 or k2[2] > k[2] + 1e-6 \
                    or k2[1] < k[1] - 1e-6 or k2[3] > k[3] + 1e-6:
                continue
            if k2 == k and abs(_cokgen_alani(h2) - _cokgen_alani(h)) < 1e-6:
                continue               # kendisinin kopyası
            q = h2[len(h2) // 2]
            if _nokta_icinde(q, h):
                dolu = True
                break
        if dolu:
            continue
        # Aynı pencereyi iki kez sayma.
        if any(abs(r["kutu"][0] - k[0]) < 1e-3 and abs(r["kutu"][1] - k[1]) < 1e-3
               and abs(r["kutu"][2] - k[2]) < 1e-3 and abs(r["kutu"][3] - k[3]) < 1e-3
               for r in out):
            continue
        out.append({"kutu": tuple(round(v, 4) for v in k),
                    "alan": _cokgen_alani(h)})
    # Birbirine BİNEN adaylar tek bir bölgenin parçalarıdır (aralarından
    # bir teğet çizgisi geçiyor); hangisinin gerçek öznitelik olduğu
    # bilinemez. Birleştirip tahmin etmek yerine hiçbiri ölçülmez.
    # Ölçtük: Handhebel'de iki komşu yüz 141,7..151,6 ve 149,2..157,4.
    temiz = []
    for r in out:
        k = r["kutu"]
        if any(r2 is not r and k[0] < k2[2] and k2[0] < k[2]
               and k[1] < k2[3] and k2[1] < k[3]
               for r2 in out for k2 in (r2["kutu"],)):
            continue
        temiz.append(r)
    temiz.sort(key=lambda r: -r["alan"])
    return temiz[:en_cok]


KESIM_EN_AZ_ORAN = 0.10   # görünüşün uzun kenarına göre en kısa anlamlı kesim
KESIM_EN_COK = 6          # bir görünüşte konumu verilecek en çok kesim
KESIM_SINIR = 8           # bundan fazlası kesim değil, eğri siluettir


def kesim_uclari(kenar, kutu_, log=None):
    """Konumu verilecek EĞİK KESİMLERİN uçları.

    Her eğik çizgi bir kesim değildir. Dövme ya da döküm bir parçanın
    silueti HLR'den onlarca kısa eğik parçaya bölünmüş gelir; o bir
    EĞRİdir, kesim değil. Ölçtük: 01.050.000.14'ün SOL görünüşünde 28
    "eğik kenar" çıkıyor, 56 uç, 43 ayrı konum ölçüsü - resim okunmaz
    olur ve o ölçülerin hiçbiri gerçek bir kesimi göstermez.

    İki kapı:
      1. Görünüşün uzun kenarının %10'undan kısa eğik gürültüdür.
      2. Geriye KESIM_SINIR'dan fazlası kalıyorsa siluet eğridir;
         program hangisinin gerçek kesim olduğunu ayırt EDEMEZ, o
         yüzden hiçbirinin konumunu vermez. Yanlış ölçü vermektense
         ölçü vermemek yeğdir - gabari, Ø ve delik konumları yerinde
         kalır, kesim ölçüsü olculer.csv'den okunur.

    Döner: [(x, y), ...] - konumu verilecek uç noktalar."""
    if not kutu_:
        return []
    buyuk = max(kutu_[2] - kutu_[0], kutu_[3] - kutu_[1])
    kes = [t for t in capraz_kenarlar(kenar)
           if not t["pah"] and t["uz"] >= KESIM_EN_AZ_ORAN * buyuk]
    if len(kes) > KESIM_SINIR:
        if log:
            log(f"    {len(kes)} eğik kenar: siluet eğri sayıldı, "
                f"kesim konumu verilmedi")
        return []
    kes.sort(key=lambda t: -t["uz"])
    uc = []
    for t in kes[:KESIM_EN_COK]:
        uc += [t["p0"], t["p1"]]
    return uc


def konum_plani(o, gorunusler, ham, h, kenarlar=None, tol=0.05):
    """Konum ölçülerinin planı - HİÇBİR ŞEY ÇİZMEDEN.

    YÖNTEM: DATUMDAN ÖLÇÜLENDİRME (baseline / parallel dimensioning).
    Her konum ölçüsü AYNI sıfır noktasından başlar. Sıfır noktası
    görünüşün sol/alt kenarı değil, PARÇANIN kendi XYZ çerçevesidir
    (bkz. datum_cercevesi / datum_ucu): ekseni ters çevrilmiş bir
    görünüşte aynı yüzey karşı kenarda çıkar, ölçü oradan gider.
    Böylece ÖN'de 10 olan delik ÜST'te de 10'dur; resim iki ayrı
    sıfır noktası taşımaz. Zincir (point-to-point) ölçülendirme
    kullanılmaz; iki sebepten:

      1. Tolerans birikir. Zincirdeki her ölçünün toleransı bir
         sonrakine eklenir, son deliğin yeri ilk deliğinkinden çok
         daha belirsiz olur (ISO 129-1, "chain dimensioning" uyarısı).
      2. Okunmaz. İlk denemede zincir FARKLI DELİK GRUPLARI arasında
         kuruluyordu: 175 mm'lik plakada "10 | 3,2 | 148,5 | 3,2 | 10"
         çıkıyordu. Oradaki 3,2, Ø10,2 deliğiyle Ø8,1 deliği
         arasındaki boşluktu - kimsenin işine yaramayan bir sayı - ve
         Ø8,1'in kenardan yerini (13,2) bulmak için toplama yapmak
         gerekiyordu. Datumdan ölçüde 10 ve 13,2 doğrudan yazar.

    TEK İSTİSNA - eşit adımlı dizi: kenardan ilk deliğe, sonra
    "n x adım", sonra son delikten öbür kenara. Bu ISO'nun kendi
    sadeleştirmesidir; 124 deliğin her birine ayrı ölçü koymak resmi
    okunmaz yapar ve hiçbir şey eklemez.

    Döner: {gorunus: {"yatay": [...], "dusey": [...]}}
    Her kayıt: {"a","b","metin","seviye"}; HAM izdüşüm koordinatında."""
    plan = {}
    # AYNA GÖRÜNÜŞLER (ÖN/ARKA, SAĞ/SOL, ÜST/ALT) aynı dış hattı iki
    # yandan gösterir. Girinti birinde ölçülür; öbüründe tekrarı ISO
    # 129-1'in "her öznitelik bir kez" kuralına aykırı olurdu. Ölçtük:
    # TIRSAN rayında SAĞ ve SOL aynı 9 girintiyi ikişer kez yazıyordu.
    ayna_verildi = set()
    for gad in gorunusler:
        kutu_ = ham.get(gad)
        if not kutu_:
            continue
        nokta = []
        for d in (o or {}).get("delikler") or []:
            if gad not in DELIK_GOR.get(d["eksen"], ()):
                continue
            for c in d.get("merkezler") or []:
                nokta.append(izdusum(c, gad))
        # EĞİK KESİMİN UÇLARI da konum ister: köşe kırma değil,
        # parçanın gerçek biçimidir; atölye nereden nereye keseceğini
        # ancak uçlarının kenarlardan yerinden bilir. (Pahlar buraya
        # girmez, onlar ok ucunda "5 x 5" diye verilir.)
        kesim = (kesim_uclari(kenarlar[gad], kutu_)
                 if kenarlar and gad in kenarlar else [])
        # GİRİNTİ / ÇIKINTI: çentiğin başı ve sonu da konum ister -
        # delikten farkı yok, atölye nereden nereye keseceğini bilmeli.
        cift = AYNA_CIFT.get(gad)
        ayna_bos = kenarlar and gad in kenarlar and cift not in ayna_verildi
        ozel = gorunus_ozellikleri(kenarlar[gad], kutu_) if ayna_bos else []
        # İÇ PENCERE (yuva, cep): kenarı değil bütün kutusu konum ister.
        pencere = ic_pencereler(kenarlar[gad], kutu_) if ayna_bos else []
        if ozel or pencere:
            ayna_verildi.add(cift)
        # YOĞUNLUK: bir görünüş, yazı boyuna göre ancak bu kadar girinti
        # taşır. 12 mm'lik parçada yazı 2,5 mm - parçanın beşte biri;
        # ilk sürüm oraya 25 ölçü ekledi, hiçbiri çakışmıyordu ama resim
        # okunmuyordu. Kural: görünüşün uzun kenarının her 4 yazı boyuna
        # bir girinti, en çok GIRINTI_EN_COK. Büyükler öncelikli (liste
        # zaten alanına göre sıralı); tam liste olculer.csv'de.
        if ozel or pencere:
            buyuk_ = max(kutu_[2] - kutu_[0], kutu_[3] - kutu_[1])
            sigar = max(1, int(buyuk_ / (4.0 * h)))
            ozel = ozel[:min(GIRINTI_EN_COK, sigar)]
            pencere = pencere[:min(PENCERE_EN_COK, sigar)]
        if not nokta and not kesim and not ozel and not pencere:
            continue
        cikti = {}
        for ad, eksen, e0, e1 in (("yatay", 0, kutu_[0], kutu_[2]),
                                  ("dusey", 1, kutu_[1], kutu_[3])):
            # DATUM parçanın kendi XYZ çerçevesinden gelir, görünüşün
            # sol/alt kenarından değil. Ekseni ters çevrilmiş görünüşte
            # (ARKA, SOL, ALT) sıfır noktası izdüşümün ÖBÜR ucundadır.
            uc = datum_ucu(gad, ad)
            dat, oteki = (e1, e0) if uc else (e0, e1)
            # Aynı sıradaki delikleri bir araya topla, dizi mi diye bak.
            obek = defaultdict(list)
            for q in nokta:
                obek[round(q[1 - eksen] / max(tol, 1e-9))].append(q[eksen])
            dizi, tekil = [], set()
            for q in kesim:                # eğik kesimin uçları: tekil
                tekil.add(round(q[eksen], 3))
            for r in ozel:                 # girintinin başı ve sonu
                if r["yon"] != ad:
                    continue
                for v in (r["a"], r["b"]):
                    # Kenarın UCUNA dayanan girintinin o ucu gabarinin
                    # kendisidir; konum diye bir daha yazılmaz. Ölçtük:
                    # 483,04 / 125,48 / 112,52 gabarinin ikinci kopyası
                    # olarak resme giriyordu.
                    if min(abs(v - e0), abs(v - e1)) > 0.2:
                        tekil.add(round(v, 3))
            for r in pencere:              # pencerenin iki kenarı
                k = r["kutu"]
                tekil.add(round(k[eksen], 3))
                tekil.add(round(k[eksen + 2], 3))
            for _k, v in obek.items():
                v = sorted(set(round(x, 3) for x in v))
                dz = _dizi(v)
                if dz:
                    dizi.append({"bas": v[0], "son": v[-1],
                                 "adet": dz[0], "adim": dz[1]})
                elif len(v) <= KONUM_EN_COK:
                    tekil.update(v)
                else:
                    # Ne dizi ne az sayıda: yalnız uçlar verilir, tam
                    # liste olculer.csv'dedir. Aksi hâlde resim okunmaz.
                    tekil.update((v[0], v[-1]))
            # SİMETRİ: ayna görüntüsü olan konumları İKİ KEZ ölçme.
            # 175 mm'lik plakada delikler 10 / 13,2 / 161,8 / 165'te;
            # 10+165 = 13,2+161,8 = 175, yani parça ortadan simetrik.
            # Dördünü de ölçmek gereksiz: ikisi yeter, gabari (175) ve
            # simetri işareti öbür ikisini zaten verir. "Tekrarlanan
            # öznitelik bir kez ölçülendirilir."
            L = e1 - e0
            orta = (e0 + e1) / 2.0
            tekil_l = sorted(tekil)
            simetrik = (len(tekil_l) >= 2 and L > 1e-9 and all(
                any(abs((e0 + e1 - x) - y) <= max(0.05, 0.002 * L)
                    for y in tekil_l) for x in tekil_l))
            if simetrik:
                # Ölçülen yarı, DATUMUN bulunduğu yarıdır.
                tekil = {x for x in tekil_l
                         if (x >= orta - 0.05 if uc else x <= orta + 0.05)}
            ara = []
            # 1) Diziler: datumdan ilk deliğe + "n x adım" + öbür kenara
            for r in dizi:
                if abs(r["bas"] - dat) <= abs(r["son"] - dat):
                    yakin, uzak = r["bas"], r["son"]
                else:
                    yakin, uzak = r["son"], r["bas"]
                if abs(yakin - dat) > 0.2:
                    ara.append({"a": dat, "b": yakin, "metin": None})
                ara.append({"a": r["bas"], "b": r["son"],
                            "metin": f"{r['adet'] - 1} x {r['adim']:g}"})
                if abs(oteki - uzak) > 0.2:
                    ara.append({"a": uzak, "b": oteki, "metin": None})
            # 2) Tekil delikler: HEPSİ AYNI DATUMDAN
            for x in sorted(tekil):
                # Dizinin içindeki bir deliği ikinci kez ölçme.
                if any(r["bas"] - 0.2 <= x <= r["son"] + 0.2 for r in dizi):
                    continue
                # HEPSİ AYNI KENARDAN. En yakın kenarı seçmek ölçüyü
                # kısaltır ama görünüşte İKİ AYRI DATUM oluşturur:
                # okuyan hangi ölçünün nereden alındığını ayırt edemez.
                # ISO 129-1 tek ortak referans ister.
                if abs(x - dat) > 0.2:
                    ara.append({"a": dat, "b": x, "metin": None})
            # Aynı ölçüyü iki kez yazma.
            gor, temiz = set(), []
            for r in ara:
                if r["a"] > r["b"]:   # çizim a<b bekler; ölçünün değeri aynı
                    r["a"], r["b"] = r["b"], r["a"]
                k = (round(r["a"], 2), round(r["b"], 2))
                if k not in gor:
                    gor.add(k)
                    r["seviye"] = 1
                    temiz.append(r)
            # Datumdan ölçüde KISA olan içeride durur (ISO 129-1):
            # ölçü çizgileri kesişmesin.
            temiz.sort(key=lambda r: abs(r["b"] - r["a"]))
            cikti[ad] = temiz
            cikti[ad + "_simetrik"] = simetrik and not dizi
        _seviyele(cikti.get("yatay", []), h)
        _seviyele(cikti.get("dusey", []), h)
        if cikti.get("yatay") or cikti.get("dusey"):
            plan[gad] = {"yatay": cikti.get("yatay", []),
                         "dusey": cikti.get("dusey", []),
                         "yatay_simetrik": cikti.get("yatay_simetrik", False),
                         "dusey_simetrik": cikti.get("dusey_simetrik", False),
                         "ozellik": ozel}
    return plan


def simetri_isareti(msp, plan, gkutu, h):
    """Simetri ekseni ve işareti.

    Simetrik konumların yalnız yarısı ölçülendiriliyor; bunun resimde
    GÖRÜNMESİ şart. İşaret olmadan okuyan, öbür yarının nereye
    geldiğini bilemez ve ölçü eksik sayılır.

    İşaret (ISO 128): eksen çizgisinin her iki ucunda, eksene DİK iki
    kısa paralel çizgi."""
    for gad, pl in plan.items():
        if gad not in gkutu:
            continue
        gk = gkutu[gad]
        for yon in ("yatay", "dusey"):
            if not pl.get(yon + "_simetrik"):
                continue
            c = 0.9 * h                    # işaret çizgilerinin yarı boyu
            d = 0.45 * h                   # iki çizgi arası
            if yon == "yatay":             # düşey eksen çizgisi
                x = (gk[0] + gk[2]) / 2.0
                y0, y1 = gk[1] - 1.6 * h, gk[3] + 1.6 * h
                msp.add_line((x, y0), (x, y1), dxfattribs={"layer": "EKSEN"})
                for y, yon_i in ((y0, 1), (y1, -1)):
                    for k in (0, 1):
                        yy = y + yon_i * k * d
                        msp.add_line((x - c, yy), (x + c, yy),
                                     dxfattribs={"layer": "EKSEN"})
            else:                          # yatay eksen çizgisi
                y = (gk[1] + gk[3]) / 2.0
                x0, x1 = gk[0] - 1.6 * h, gk[2] + 1.6 * h
                msp.add_line((x0, y), (x1, y), dxfattribs={"layer": "EKSEN"})
                for x, yon_i in ((x0, 1), (x1, -1)):
                    for k in (0, 1):
                        xx = x + yon_i * k * d
                        msp.add_line((xx, y - c), (xx, y + c),
                                     dxfattribs={"layer": "EKSEN"})

def datum_isaretleri(msp, harfler, gorunusler, gkutu, h):
    """Datum yüzey simgeleri - ISO 5459.

    Bütün konum ölçüleri artık parçanın kendi XYZ çerçevesinden
    veriliyor. Okuyanın sıfırın NEREDE olduğunu görmesi gerekir; aksi
    hâlde ölçülerin hepsinin aynı yerden gittiği bilgisi resimde
    yazılı değil, yalnız bizim aklımızda kalır.

    Simge: datum yüzeyinin çizgisine TABANI oturan içi dolu üçgen,
    kısa bir kılavuz, kare çerçeve içinde harf.

    Her datum BİR KEZ işaretlenir - göründüğü ilk görünüşte. Aynı
    yüzeyi her görünüşte yeniden işaretlemek bilgi eklemez, kalabalık
    yapar.

    Döner: işaretlenen harfler kümesi."""
    yazildi = set()
    for gad in gorunusler:
        gk = gkutu.get(gad)
        if not gk:
            continue
        i1, i2, _tx, _ty = GOR_EKSEN[gad]
        for eksen, yon in ((i1, "yatay"), (i2, "dusey")):
            harf = harfler.get(eksen)
            if not harf or harf in yazildi:
                continue
            if _datum_ciz(msp, gk, yon, datum_ucu(gad, yon), harf, h):
                yazildi.add(harf)
    return yazildi


def _datum_ciz(msp, gk, yon, uc, harf, h):
    """Tek datum simgesi.

    Yeri TAHMİN EDİLMEZ: simgenin kaplayacağı yer hesaplanır, resimde
    ölçülmüş olan her şeyle karşılaştırılır, çakışıyorsa kenar boyunca
    kaydırılıp yeniden denenir. Ölçü çizgileri de aynı kenardan
    çıkıyor - üstlerine basmasın."""
    # Üçgenin TABANI datum yüzeyinin çizgisine oturur; varlık kutusuyla
    # bakmak her yeri dolu gösterirdi. Bakılacak olan yazılardır.
    dolu = _yazi_kutulari(msp)
    t = 0.6 * h                        # üçgenin yarı tabanı = yüksekliği
    d = 1.0 if uc else -1.0            # parçadan DIŞARI bakan yön
    # Ölçü rakamları ölçünün ORTASINDA durur; simge kenarın uçlarına
    # yakın dursun ki ilk denemede yerini bulsun.
    for pay in (0.86, 0.14, 0.68, 0.32, 0.5):
        if yon == "yatay":             # düşey kenar -> simge yanda
            x = gk[2] if uc else gk[0]
            y = gk[1] + pay * (gk[3] - gk[1])
            taban = ((x, y - t), (x, y + t))
            ucu = (x + d * 1.4 * t, y)
            mrk = (ucu[0] + d * 1.9 * t, y)
        else:                          # yatay kenar -> simge altta/üstte
            y = gk[3] if uc else gk[1]
            x = gk[0] + pay * (gk[2] - gk[0])
            taban = ((x - t, y), (x + t, y))
            ucu = (x, y + d * 1.4 * t)
            mrk = (x, ucu[1] + d * 1.9 * t)
        nokta = [taban[0], taban[1], ucu,
                 (mrk[0] - t, mrk[1] - t), (mrk[0] + t, mrk[1] + t)]
        kutu_ = (min(q[0] for q in nokta), min(q[1] for q in nokta),
                 max(q[0] for q in nokta), max(q[1] for q in nokta))
        if _cakisiyor(kutu_, dolu, 0.2 * h):
            continue
        msp.add_solid([taban[0], taban[1], ucu],
                      dxfattribs={"layer": "OLCU"})
        msp.add_line(ucu, mrk, dxfattribs={"layer": "OLCU"})
        msp.add_lwpolyline(
            [(mrk[0] - t, mrk[1] - t), (mrk[0] + t, mrk[1] - t),
             (mrk[0] + t, mrk[1] + t), (mrk[0] - t, mrk[1] + t)],
            close=True, dxfattribs={"layer": "OLCU"})
        e = _yaz(msp, harf, mrk[0], mrk[1], 1.2 * t, kat="OLCU")
        ky = _yazi_siniri(e)
        if ky:                         # harf kutunun ortasına otursun
            e.set_placement((mrk[0] - (ky[2] - ky[0]) / 2.0,
                             mrk[1] - (ky[3] - ky[1]) / 2.0))
        return True
    return False


def _gorunen_parcalar(msp, kutu_=None, katman=("GORUNEN",)):
    """Resimdeki görünen çizgilerin DÜZ PARÇALARI; kutu verilirse
    yalnız ona değenler.

    Yazının "konturun üstünde" olup olmadığı SINIR KUTUSUYLA
    anlaşılmaz: ince uzun bir çokgenin kutusu bütün görünüşü kaplar.
    Sorulacak olan, yazının GERÇEK BİR ÇİZGİYE değip değmediğidir."""
    out = []
    for e in msp:
        try:
            if e.dxf.layer not in katman:
                continue
            t = e.dxftype()
            if t == "LINE":
                p = [(e.dxf.start.x, e.dxf.start.y),
                     (e.dxf.end.x, e.dxf.end.y)]
            elif t == "LWPOLYLINE":
                p = [(x, y) for x, y in e.get_points("xy")]
                if e.closed and len(p) > 2:
                    p.append(p[0])
            elif t in ("CIRCLE", "ARC"):
                p = [(q.x, q.y) for q in e.flattening(0.2)]
            else:
                continue
        except Exception:
            continue
        for a, b in zip(p, p[1:]):
            if kutu_ and (max(a[0], b[0]) < kutu_[0] or
                          min(a[0], b[0]) > kutu_[2] or
                          max(a[1], b[1]) < kutu_[1] or
                          min(a[1], b[1]) > kutu_[3]):
                continue
            out.append((a, b))
    return out


def _parca_kutuda(a, b, k):
    """(a, b) doğru parçası k dikdörtgenine değiyor mu? (Liang-Barsky)"""
    x0, y0 = a
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - k[0]), (dx, k[2] - x0),
                 (-dy, y0 - k[1]), (dy, k[3] - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return False
                t0 = max(t0, r)
            else:
                if r < t0:
                    return False
                t1 = min(t1, r)
    return t0 <= t1


def girinti_olculeri(msp, plan, kaydir, gkutu, h, en_cok_oran=0.5):
    """Girintinin DERİNLİĞİ - kenara dik.

    Konumu (başı ve sonu) datumdan verildi; geriye ne kadar derin
    olduğu kalıyor ve o, bu görünüşte başka yerden okunamaz.

    Yalnız GERÇEKTEN çentik olanlar ölçülür: derinliği o yöndeki
    görünüş boyunun yarısını geçen boşluk çentik değil, parçanın
    biçiminin kendisidir (U profilin ağzı gibi) - onun ölçüsü karşı
    görünüşten ya da gabariden okunur.

    Yeri ÖLÇÜLEREK doğrulanır, iki soruyla: yazı başka bir yazıya
    biniyor mu, yazı konturun bir ÇİZGİSİNE değiyor mu. İlk sürüm
    yalnız birincisine bakıyordu; dar çentikte yazı çentiğin
    duvarlarına biniyordu (ölçtük: 16 resimde 16 yazı). Önce çentiğin
    içinde birkaç yer denenir, olmazsa yazı çentiğin DIŞINA, parçanın
    kenarının ötesine alınır. Hiçbir yer tutmazsa derinlik yazılmaz -
    çizgiyi kapatan bir ölçü, olmayan ölçüden kötüdür.

    Döner: çizilen ölçü sayısı."""
    sayi = 0
    for gad, pl in plan.items():
        gk = gkutu.get(gad)
        if not gk:
            continue
        dx, dy = kaydir[gad]
        G, Y = gk[2] - gk[0], gk[3] - gk[1]
        dolu = _yazi_kutulari(msp)
        pay_k = 6.0 * h
        kont = _gorunen_parcalar(msp, (gk[0] - pay_k, gk[1] - pay_k,
                                       gk[2] + pay_k, gk[3] + pay_k))
        # Bu görünüşte ZATEN yazılı değerler. Derinlik bunlardan biriyse
        # ikinci kez yazılmaz: ters T biçiminde kolun boyu, gövdenin
        # datumdan konumuyla aynı sayıdır (ölçtük: 01.050.000.02'de "36"
        # üç kez yazılıyordu).
        yazili = {"yatay": {round(abs(q["b"] - q["a"]), 1)
                            for q in pl.get("yatay") or []},
                  "dusey": {round(abs(q["b"] - q["a"]), 1)
                            for q in pl.get("dusey") or []}}
        for r in pl.get("ozellik") or []:
            yatay = r["yon"] == "yatay"
            der = r["derinlik"]
            # Yalnız İÇ çentik, yalnız TAM değer (bkz. kontur_ozellikleri).
            if not r.get("ic") or der is None:
                continue
            if der > en_cok_oran * (Y if yatay else G):
                continue
            # Derinlik, girintinin konumuna DİK yöndedir.
            dik = "dusey" if yatay else "yatay"
            if round(der, 1) in yazili[dik]:
                continue
            kayd = dx if yatay else dy
            a, b = r["a"] + kayd, r["b"] + kayd
            if yatay:
                t = gk[1] if r["taraf"] == "alt" else gk[3]
                disa = -1.0 if r["taraf"] == "alt" else 1.0
            else:
                t = gk[0] if r["taraf"] == "sol" else gk[2]
                disa = -1.0 if r["taraf"] == "sol" else 1.0
            u = t - disa * der             # çentiğin dibi
            adaylar = [(pay, None) for pay in (0.5, 0.3, 0.7)]
            adaylar += [(pay, k) for k in (1.0, 2.0, 3.2)
                        for pay in (0.5, 0.25, 0.75)]
            for pay, dis_k in adaylar:
                m = a + (b - a) * pay
                if dis_k is None:
                    yer = None
                elif yatay:
                    yer = (m + 0.9 * h, t + disa * dis_k * h)
                else:
                    yer = (t + disa * dis_k * h, m + 0.9 * h)
                try:
                    if yatay:
                        dim = msp.add_linear_dim(
                            base=(m, 0), p1=(m, t), p2=(m, u), angle=90,
                            location=yer, text="<>", dimstyle=OLCU_STILI,
                            dxfattribs={"layer": "OLCU"})
                    else:
                        dim = msp.add_linear_dim(
                            base=(0, m), p1=(t, m), p2=(u, m),
                            location=yer, text="<>", dimstyle=OLCU_STILI,
                            dxfattribs={"layer": "OLCU"})
                    dim.render()
                except Exception:
                    break
                ky = _olcu_yazi_kutusu(dim)
                if ky is None or not (
                        _cakisiyor(ky, dolu, 0.2 * h)
                        or any(_parca_kutuda(p, q, ky) for p, q in kont)):
                    if ky:
                        dolu.append(ky)
                    yazili[dik].add(round(der, 1))
                    sayi += 1
                    break
                _olcu_sil(msp, dim)
    return sayi


def konum_olculeri(msp, plan, kaydir, gkutu, h, en_cok_kademe=8):
    """Planı çizer ve YERİNİ ÖLÇEREK doğrular.

    Kademeleme tek başına yetmiyor: dar bir aralıkta ("3,2") yazı
    ölçünün içine sığmaz, CAD onu uzatma çizgilerinin DIŞINA kaçırır
    ve nereye kaçıracağı ölçü stiline bağlıdır. Hesapla bulunmaz.
    Bu yüzden her ölçü çizilir, yazısının gerçek sınırı ölçülür,
    çakışıyorsa SİLİNİP bir alt kademede yeniden denenir.

    Uzun aralıklar önce yerleşir: en çok okunanlar onlardır, en iyi
    yeri onlar alsın.

    Döner: {gorunus: (en_alt_y, en_sol_x)} - gabari ölçüsü bunların
    DIŞINA konacak."""
    sinir = {}
    for gad, pl in plan.items():
        if gad not in gkutu:
            continue
        dx, dy = kaydir[gad]
        gk = gkutu[gad]
        dolu = _varlik_kutulari(msp)      # resimde şu an ne varsa, ölçülmüş
        for yon, kayd in (("yatay", dx), ("dusey", dy)):
            sirali = sorted(pl[yon], key=lambda r: -(r["b"] - r["a"]))
            for r in sirali:
                a, b = r["a"] + kayd, r["b"] + kayd
                kutu_y = None
                for sev in range(r["seviye"], r["seviye"] + en_cok_kademe):
                    dim = _konum_ciz(msp, gk, yon, a, b, h, sev,
                                     r.get("metin"))
                    if dim is None:
                        break
                    kutu_y = _olcu_yazi_kutusu(dim)
                    if kutu_y is None or not _cakisiyor(kutu_y, dolu, 0.2 * h):
                        break
                    _olcu_sil(msp, dim)
                    dim = None
                if dim is not None and kutu_y:
                    dolu.append(kutu_y)
                    s0, s1 = sinir.get(gad, (gk[1], gk[0]))
                    sinir[gad] = (min(s0, kutu_y[1]), min(s1, kutu_y[0]))
    return sinir


def gabari_olculeri(msp, gkutu, sinir, h):
    """Görünüşün TOPLAM ölçüsü - en dışarıda.

    Konum ölçülerinden SONRA çizilir ve onların ÖLÇÜLEN sınırının
    dışına konur. Önce çizilip yeri tahmin edilirse, bir konum ölçüsü
    yerini bulamayıp alt kademeye kaçtığında gabarinin içine düşüyor
    ve ölçü çizgileri kesişiyordu. Teknik resimde küçük ölçüler
    içeride, toplam ölçü en dışarıdadır."""
    dolu = _varlik_kutulari(msp)          # resimde ne varsa, ölçülmüş
    for gad, gk in gkutu.items():
        alt, sol = sinir.get(gad, (gk[1], gk[0]))
        for yon, tabanlar in (
                ("yatay", [min(alt, gk[1]) - (2.2 + 1.7 * i) * h
                           for i in range(6)]),
                ("dusey", [min(sol, gk[0]) - (2.2 + 1.7 * i) * h
                           for i in range(6)])):
            for t in tabanlar:
                try:
                    if yon == "yatay":
                        dim = msp.add_linear_dim(
                            base=(0, t), p1=(gk[0], gk[1]), p2=(gk[2], gk[1]),
                            dimstyle=OLCU_STILI, dxfattribs={"layer": "OLCU"})
                    else:
                        dim = msp.add_linear_dim(
                            base=(t, 0), p1=(gk[0], gk[1]), p2=(gk[0], gk[3]),
                            angle=90, dimstyle=OLCU_STILI,
                            dxfattribs={"layer": "OLCU"})
                    dim.render()
                except Exception:
                    break
                # Yeri TAHMİN EDİLMEZ, ölçülür: dar bir görünüşte gabari
                # yazısı konturun üstüne düşebiliyor.
                ky = _olcu_yazi_kutusu(dim)
                if ky is None or not _cakisiyor(ky, dolu, 0.2 * h):
                    if ky:
                        dolu.append(ky)
                    break
                _olcu_sil(msp, dim)


def _konum_ciz(msp, gk, yon, a, b, h, seviye, metin=None):
    """Tek bir konum ölçüsü; görünüşün altına (yatay) ya da soluna."""
    d = (1.8 + 1.7 * (seviye - 1)) * h
    # text="<>" ÖLÇÜLEN DEĞERİ yazdırır. None verilirse ezdxf bunu bir
    # metin sanıp ölçünün üstüne düz "None" yazıyor.
    metin = "<>" if metin is None else metin
    ovr = {"dimtoh": 1, "dimtih": 1, "dimtmove": 1, "dimatfit": 3}
    try:
        if yon == "yatay":
            dim = msp.add_linear_dim(
                base=(0, gk[1] - d), p1=(a, gk[1]), p2=(b, gk[1]),
                text=metin, dimstyle=OLCU_STILI, override=ovr,
                dxfattribs={"layer": "OLCU"})
        else:
            dim = msp.add_linear_dim(
                base=(gk[0] - d, 0), p1=(gk[0], a), p2=(gk[0], b),
                angle=90, text=metin, dimstyle=OLCU_STILI, override=ovr,
                dxfattribs={"layer": "OLCU"})
        dim.render()
        return dim
    except Exception:
        return None


def merkez_cizgileri(msp, o, yer, kaydir, en_cok=1500):
    """Deliğin daire göründüğü HER (seçili) görünüşte merkez çizgisi."""
    sayac = 0
    for d in o.get("delikler") or []:
        for gad in DELIK_GOR.get(d["eksen"], ()):
            if gad not in yer:
                continue
            dx, dy = kaydir[gad]
            u = max(d["cap_mm"] / 2.0 + 1.5, 2.0)
            for c in d.get("merkezler") or []:
                if sayac >= en_cok:
                    return sayac
                p = izdusum(c, gad)
                x, y = p[0] + dx, p[1] + dy
                msp.add_line((x - u, y), (x + u, y), dxfattribs={"layer": "EKSEN"})
                msp.add_line((x, y - u), (x, y + u), dxfattribs={"layer": "EKSEN"})
                sayac += 1
    return sayac


# ---------------------------------------------------------------- açınım
# Sac büküm açınımı: bükümü açıp düz sac hâlini verir.
#
# Kapsam: bütün büküm eksenleri BİRBİRİNE PARALEL olan parçalar - C, U, L, Z
# profilleri, köşebentler, kutu kesitler. Bu tür parçada açınım tek boyutlu
# bir problemdir: profil kesiti boyunca düz parçalar uzunluklarını korur,
# bükümler ise NÖTR EKSEN yayı kadar yer kaplar.
#
# Büküm payı (bend allowance):   BA = teta * (r_ic + K * t)
#   teta  büküm açısı (radyan), r_ic iç yarıçap, t sac kalınlığı,
#   K     nötr eksenin sac içindeki yeri (K-faktörü). Yumuşak çelikte
#         genellikle 0,40 - 0,50.
# K-faktörü tezgâha ve malzemeye göre değişir, bu yüzden dışarıdan verilir;
# arayüzdeki kutudan ya da --k-faktor ile değiştirilir.
K_FAKTOR = 0.40


# ---------------------------------------------------------------- ayarlar
# Kullanıcının verdiği K-faktörü gibi ayarlar, program kapansa da kalsın.
# Dosya kullanıcının kendi klasöründe durur: program Program Files gibi
# yazma izni olmayan bir yere kurulmuş olabilir.
def _ayar_yolu():
    """Ayar dosyasının yeri.

    Windows'ta LOCALAPPDATA kullanılır, %USERPROFILE% değil: kurumsal
    bilgisayarlarda kullanıcı klasörü ağ sürücüsünde (gezici profil)
    olabilir; oradan dosya okumak ağ yavaşsa saniyeler sürer, sürücü
    erişilemezse program o satırda bekler. LOCALAPPDATA her zaman
    yereldir."""
    kok = (os.environ.get("LOCALAPPDATA")
           or os.environ.get("XDG_CONFIG_HOME")
           or os.path.join(os.path.expanduser("~"), ".config"))
    try:
        d = os.path.join(kok, "Pi3D")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "ayarlar.json")
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".pi3d.json")


AYAR_DOSYA = _ayar_yolu()


# Program eskiden "PiFikstur" adıyla çalışıyordu. Ad değişti diye
# kullanıcının girdiği K-faktörü kaybolmasın: yeni dosya yoksa eskisi
# okunur, ilk yazışta yenisine geçilir.
ESKI_AYAR = [os.path.join(os.path.dirname(os.path.dirname(AYAR_DOSYA)),
                          "PiFikstur", "ayarlar.json"),
             os.path.join(os.path.expanduser("~"), ".pifikstur.json")]


def ayar_oku():
    for y in [AYAR_DOSYA] + ESKI_AYAR:
        try:
            with open(y, encoding="utf-8") as f:
                a = json.load(f)
            if isinstance(a, dict):
                return a
        except Exception:
            continue
    return {}


def ayar_yaz(**yeni):
    """Verilen ayarları saklar. Yazamazsa sessizce geçer: ayar
    saklanamaması işi durdurmaz."""
    a = ayar_oku()
    a.update({k: v for k, v in yeni.items() if v is not None})
    try:
        with open(AYAR_DOSYA, "w", encoding="utf-8") as f:
            json.dump(a, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return a


def k_faktor_ayari():
    """Saklanmış K-faktörü; yoksa varsayılan."""
    try:
        k = float(ayar_oku().get("k_faktor", K_FAKTOR))
        return k if 0.1 <= k <= 0.6 else K_FAKTOR
    except (TypeError, ValueError):
        return K_FAKTOR


# ------------------------------------------------- büküm yöntemi
# Abkant (pres büküm) sınırları. Tezgâha, kalıba ve malzemeye göre
# değişir; ayarlardan değiştirilebilir. Varsayılanlar hava bükme için
# yaygın kullanılan değerlerdir, kanun değildir - kendi kalıbınıza
# göre ayarlayın.
ABKANT_EN_AZ_KANAT = 4.0     # en kısa kanat, kalınlığın bu katı kadar olmalı
ABKANT_EN_AZ_R = 0.6         # iç yarıçap bunun altındaysa UYARI (yasak değil)
SILINDIR_EN_AZ_R = 20.0      # iç yarıçap bu katın üstündeyse silindir bükümü


def abkant_siniri():
    """Saklanmış abkant sınırları; yoksa varsayılan."""
    a = ayar_oku()
    def _f(ad, vars_):
        try:
            v = float(a.get(ad, vars_))
            return v if 0 < v < 100 else vars_
        except (TypeError, ValueError):
            return vars_
    return (_f("abkant_en_az_kanat", ABKANT_EN_AZ_KANAT),
            _f("abkant_en_az_r", ABKANT_EN_AZ_R),
            _f("silindir_en_az_r", SILINDIR_EN_AZ_R))


def bukum_yontemi(t, kanatlar, yaricaplar, aciler=(), boy_mm=0.0):
    """Parça hangi yöntemle bükülmüş: abkant mı, rollform mu?

    Karar FİZİĞE dayanır, tahmine değil. Abkantta parça bir V kalıbın
    ağzına oturur ve bıçak bastırır; kanat kalıbın ağzını tutamayacak
    kadar kısaysa parça kalıbın içine düşer, bükülemez. Aynı şekilde iç
    yarıçap kalınlığın belli bir oranının altına inemez - sac çatlar.

    İKİSİ AYNI ŞEY DEĞİLDİR:
      - Kanat çok kısaysa büküm İMKÂNSIZDIR. Kalıbın ağzı tutmaz,
        parça içine düşer. Bu, yöntemi belirler: rollform gerekir.
      - İç yarıçap küçükse büküm RİSKLİDİR, imkânsız değil. Çatlayıp
        çatlamayacağı malzeme kalitesine, hadde yönüne ve kalıbın
        keskinliğine bağlıdır. İnce sacta 0,5xt iç yarıçap keskin
        kalıpla bükülür. Bu yüzden yarıçap parçayı rollform ilan
        etmez, yalnız UYARI verir.

    (Gerçek bir montajda ölçüldü: 60 sac parçanın 12'sinin iç yarıçapı
    0,40-0,60xt arasındaydı ve hepsi abkant parçasıydı; yarıçapı
    yasaklayıcı saymak bunları yanlışlıkla rollform ilan ediyordu.)

    Döner: {"yontem", "kesinlik", "neden", "uyari", ...ölçüler}
    """
    kanat_k, r_k, sil_k = abkant_siniri()
    if not yaricaplar:
        return {"yontem": "düz sac", "kesinlik": "kesin",
                "neden": "Parçada büküm yok."}
    if t <= 0:
        return {"yontem": "bilinmiyor", "kesinlik": "-",
                "neden": "Sac kalınlığı ölçülemedi."}
    en_kisa = min(kanatlar) if kanatlar else 0.0
    en_kucuk_r = min(yaricaplar)
    olcu = {"en_kisa_kanat_mm": round(en_kisa, 2),
            "en_kisa_kanat_t": round(en_kisa / t, 2),
            "en_kucuk_r_mm": round(en_kucuk_r, 2),
            "en_kucuk_r_t": round(en_kucuk_r / t, 2),
            "bukum_sayisi": len(yaricaplar),
            "sinir_kanat_t": kanat_k, "sinir_r_t": r_k}

    if min(yaricaplar) / t >= sil_k:
        return dict(olcu, yontem="silindir bükümü", kesinlik="olası",
                    neden=(f"En küçük iç yarıçap kalınlığın "
                           f"{en_kucuk_r / t:.0f} katı; bu kadar geniş "
                           f"yarıçap abkantta değil silindirde (kalender) "
                           f"yapılır."))
    uyari = ""
    if en_kucuk_r / t < r_k:
        uyari = (f"En küçük iç yarıçap {en_kucuk_r:.2f} mm = kalınlığın "
                 f"{en_kucuk_r / t:.2f} katı ({r_k:g} katın altında). "
                 f"Bükülebilir ama çatlama riski var: malzeme kalitesine, "
                 f"hadde yönüne ve kalıbın keskinliğine bakın.")
    if kanatlar and en_kisa / t < kanat_k:
        return dict(olcu, yontem="rollform", kesinlik="olası", uyari=uyari,
                    neden=(f"Abkantta yapılamaz: en kısa kanat "
                           f"{en_kisa:.1f} mm = kalınlığın {en_kisa / t:.1f} "
                           f"katı; abkant için en az {kanat_k:g} kat gerekir, "
                           f"daha kısa kanat V kalıbın ağzını tutmaz, parça "
                           f"kalıbın içine düşer. Rollform ya da başka bir "
                           f"yöntemle üretilmiş olmalı."))
    ek = ""
    if len(yaricaplar) >= 8 and boy_mm >= 1000:
        ek = (f" ({len(yaricaplar)} büküm ve {boy_mm:.0f} mm boy rollform "
              f"için de tipiktir; seri büyükse orayı da değerlendirin.)")
    return dict(olcu, yontem="abkant", kesinlik="kesin", uyari=uyari,
                neden=(f"Bütün kanatlar en az kalınlığın {kanat_k:g} katı "
                       f"(en kısası {en_kisa / t:.1f} kat): abkantta "
                       f"bükülür." + ek))


class AcilimYok(Exception):
    """Bu parçanın açınımı çıkarılamıyor; mesaj kullanıcıya gösterilir."""


def bukum_yuzeyleri(sh, en_az_oran=0.05, en_cok_yaricap=60.0):
    """Büküm olabilecek silindir yüzeyleri toplar.

    Delik de silindirdir. İki kaba eleme burada yapılır:
      * yarıçap büyük olamaz (yuvarlatılmış bir sac bükümü değildir),
      * silindir TAM tur atmamalıdır - delik 360 derece döner, büküm dönmez.
    Asıl ayıklama bukum_ciftleri'nde yapılır: gerçek büküm, iç ve dış
    yüzü aynı eksen üzerinde duran ve yarıçap farkı sac kalınlığına eşit
    olan bir ÇİFTTİR; delikte böyle bir eş yoktur."""
    kb = kutu(sh)
    enb = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2])
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    out = []
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        cyl = ad.Cylinder()
        r = cyl.Radius()
        if r > en_cok_yaricap:
            continue
        fk = kutu(f)
        uz = max(fk[3] - fk[0], fk[4] - fk[1], fk[5] - fk[2])
        if uz < en_az_oran * enb:
            continue
        try:
            aci = abs(ad.LastUParameter() - ad.FirstUParameter())
        except Exception:
            aci = math.pi / 2
        if aci > 0.95 * 2 * math.pi:
            continue                      # tam tur: delik ya da pim
        d = cyl.Position().Direction()
        ek = cyl.Position().Location()
        e3 = (d.X(), d.Y(), d.Z())
        # Silindirin KENDİ EKSENİ boyunca uzunluğu. Büküm sacın boyunca
        # gider, uzundur; köşe yuvarlatması sac kalınlığı kadar kısadır.
        pr = []
        ex = TopExp_Explorer(f, TopAbs_VERTEX)
        while ex.More():
            p = BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current()))
            pr.append(p.X() * e3[0] + p.Y() * e3[1] + p.Z() * e3[2])
            ex.Next()
        out.append({"yuz": f, "r": r, "aci": aci, "eksen": e3,
                    "eksen_uz": (max(pr) - min(pr)) if pr else 0.0,
                    "merkez": (ek.X(), ek.Y(), ek.Z()),
                    "ic": f.Orientation() == TopAbs_REVERSED})
    return out


def _paralel(a, b, tol=0.02):
    return abs(abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) - 1.0) < tol


def _eksen_adi(b, yuvarla=0.05):
    """Silindirin EKSEN DOĞRUSUNU tek biçimde adlandırır: yön (işaretsiz)
    ve doğrunun orijine en yakın noktası. Aynı eksen üzerindeki iç ve dış
    yüzey aynı adı alır."""
    d = _birim(b["eksen"])
    if (d[0], d[1], d[2]) < (0.0, 0.0, 0.0):
        d = (-d[0], -d[1], -d[2])
    p = b["merkez"]
    s = p[0] * d[0] + p[1] * d[1] + p[2] * d[2]
    q = (p[0] - s * d[0], p[1] - s * d[1], p[2] - s * d[2])
    return (round(d[0], 3), round(d[1], 3), round(d[2], 3),
            round(q[0] / yuvarla), round(q[1] / yuvarla), round(q[2] / yuvarla))


def bukum_ciftleri(bukumler, en_az_kalinlik=0.2, en_cok_kalinlik=25.0):
    """Aynı eksen üzerindeki iç ve dış silindiri tek bükümde birleştirir.

    Deliğin karşılık gelen ikinci bir silindiri yoktur, bu yüzden elenir.
    Kalan çiftlerden sac kalınlığı ORTANCA ile bulunur; kalınlığı tutmayan
    çiftler (havşa, pah, cep) atılır."""
    grup = defaultdict(list)
    for b in bukumler:
        grup[_eksen_adi(b)].append(b)
    ham = []
    for lst in grup.values():
        r_ic, r_dis = min(x["r"] for x in lst), max(x["r"] for x in lst)
        t = r_dis - r_ic
        if t < en_az_kalinlik or t > en_cok_kalinlik:
            continue
        # Köşe yuvarlatmasını ayıkla: onun ekseni sac yüzüne DİK durur,
        # bu yüzden eksen boyu sac kalınlığı kadardır. Büküm ise sacın
        # boyunca gider.
        uz = max(x["eksen_uz"] for x in lst)
        if uz < 2.0 * t:
            continue
        ham.append({"r_ic": r_ic, "r_dis": r_dis, "t": t, "eksen_uz": uz,
                    "aci": max(x["aci"] for x in lst),
                    "eksen": lst[0]["eksen"], "merkez": lst[0]["merkez"]})
    if not ham:
        return []
    s = sorted(x["t"] for x in ham)
    ortanca = s[len(s) // 2]
    pay = max(0.05, 0.05 * ortanca)
    return [x for x in ham if abs(x["t"] - ortanca) <= pay]


def sac_taramasi(sh, kb=None):
    """Parça bükümlü sac mı — AÇINIM HESABI YAPMADAN söyler.

    Niçin ayrı bir tarama: açınım hesabı parçayı döndürüp kesit alır,
    parça başına 15-30 saniye sürer. Bir montajda 300 komponent olabilir;
    hepsine açınım denemek saatler alır. Oysa "bu parça bükümlü sac mı"
    sorusunun cevabı çok daha ucuza bulunur: SİLİNDİRİK YÜZEYLERE bakmak
    yeter. Bükümün iç ve dış silindiri aynı eksen üzerindedir ve
    aralarındaki fark sac kalınlığıdır; delikte böyle bir çift yoktur,
    köşe yuvarlatmasının ekseni ise sac yüzüne diktir (bkz.
    bukum_ciftleri). Böylece kullanıcı listeden parça seçmek zorunda
    kalmaz, program bükümlüleri kendisi bulur.

    Bu bir ÖN ELEMEDİR, açınım sözü değildir: burada "bükümlü sac" çıkan
    bir parçanın açınımı yine de verilemeyebilir (büküm eksenleri
    paralel değilse, boydan boya delik varsa...). Gerçek karar
    sac_acilim'indir ve sebebini o yazar. Ters yönde hata yapmamaya
    çalışılır: bükümlü bir parçayı "sac değil" diye elemek, listede
    görünmemesi demektir.

    Döndürdüğü:
      {"sac": bool, "tip": "bukumlu sac" / "duz sac" / "sac degil",
       "kalinlik_mm": float|None, "bukum_sayisi": int,
       "eksen_paralel": bool|None, "neden": str}
    """
    bos = {"sac": False, "tip": "sac degil", "kalinlik_mm": None,
           "bukum_sayisi": 0, "eksen_paralel": None, "neden": ""}
    try:
        kb = kb or kutu(sh)
    except Exception:
        return dict(bos, neden="parçanın gabarisi okunamadı")
    olc = sorted([kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]])
    if olc[0] < 1e-9:
        return dict(bos, neden="parçanın kalınlığı sıfır")

    try:
        ciftler = bukum_ciftleri(bukum_yuzeyleri(sh))
    except Exception as e:
        ciftler = []
        bos["neden"] = f"büküm taraması yapılamadı: {type(e).__name__}"

    if ciftler:
        t = sorted(c["t"] for c in ciftler)[len(ciftler) // 2]
        # Sac, KENDİ KALINLIĞINDAN çok daha büyük bir parçadır. Kalın bir
        # blokta da radüs vardır; oran bakılmazsa freze parçası "sac"
        # sayılır.
        if olc[2] < 4.0 * t:
            return dict(bos, kalinlik_mm=round(t, 2),
                        neden=f"gabari kalınlığa göre küçük "
                              f"({olc[2]:.0f} mm / t={t:.1f} mm): sac değil")
        try:
            bukum_ekseni(ciftler)
            paralel = True
        except AcilimYok:
            paralel = False
        return {"sac": True, "tip": "bukumlu sac", "kalinlik_mm": round(t, 2),
                "bukum_sayisi": len(ciftler), "eksen_paralel": paralel,
                "neden": ("" if paralel else
                          "büküm eksenleri paralel değil; açınım "
                          "denenecek ama çıkmayabilir")}

    t = sac_kalinligi(sh, kb)
    if t:
        # Bükümü yok: açınımı parçanın kendisidir, ayrıca hesaplanmaz.
        return {"sac": True, "tip": "duz sac", "kalinlik_mm": t,
                "bukum_sayisi": 0, "eksen_paralel": None,
                "neden": "büküm yok: düz sac, açınımı kendisidir"}
    return dict(bos, neden=bos["neden"] or "bükümü ve sac kesiti yok")


def bukum_ekseni(ciftler):
    """Bütün büküm eksenleri paralel mi? Değilse açınım çıkarılamaz.
    Geriye eksenlerin ORTALAMASI döner: eksenler tasarımda tam tam
    üstüne oturmaz, ortalama alınırsa kesit hiçbir bükümde eğik kalmaz."""
    if not ciftler:
        raise AcilimYok(
            "Parçada büküm bulunamadı.\n"
            "Sacın iç ve dış yüzü aynı eksen üzerinde, yarıçap farkı sac "
            "kalınlığı kadar olan bir silindir çifti aranır; bu parçada "
            "öyle bir çift yok. Parça düz sac ya da sac parça değil.")
    e0 = ciftler[0]["eksen"]
    for b in ciftler[1:]:
        if not _paralel(e0, b["eksen"]):
            raise AcilimYok(
                "Bükümlerin eksenleri birbirine paralel değil.\n"
                "Bu sürüm yalnız tek yönde bükülmüş parçaların - C, U, L, Z\n"
                "profilleri, köşebentler - açınımını çıkarabilir.")
    top = [0.0, 0.0, 0.0]
    for b in ciftler:
        yon = 1.0 if sum(e0[i] * b["eksen"][i] for i in range(3)) >= 0 else -1.0
        for i in range(3):
            top[i] += yon * b["eksen"][i]
    return _birim(tuple(top))


def _dik_birim(e):
    """e'ye dik birim vektör."""
    y = (0.0, 0.0, 1.0) if abs(e[2]) < 0.9 else (1.0, 0.0, 0.0)
    return _birim(_capraz(e, y))


def _eksene_dondur(sh, eksen):
    """Katıyı, büküm ekseni Z ile çakışacak biçimde döndürür. Böylece
    kesit her zaman XY düzleminde alınır; parçanın montajdaki duruşu
    hesabı etkilemez."""
    tr = gp_Trsf()
    tr.SetTransformation(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(*eksen)))
    return BRepBuilderAPI_Transform(sh, tr, True).Shape()


def _kesit_yuzu(sh, konum, kb):
    """z = konum düzlemindeki kesit yüzü. Kesit TEK parça ve deliksiz
    değilse None döner: açınım genişliği ancak sağlam bir kesitten
    ölçülebilir."""
    try:
        kesik = kesit_kati(sh, 2, konum, kb)
    except Exception:
        return None
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(kesik, TopAbs_FACE, m)
    bul = []
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Plane:
            continue
        d = ad.Plane().Axis().Direction()
        if abs(d.Z()) < 0.999:
            continue
        if abs(ad.Plane().Location().Z() - konum) > 1e-3:
            continue
        bul.append(f)
    if len(bul) != 1:
        return None                       # kesit parçalı: sac şeridi değil
    # İÇ TELLER ATILMAZ. Eskiden yalnız dış tel alınıyordu, gerekçe
    # "sacın ortasındaki delikler kesitin dış sınırını değiştirmez"di.
    # Açık C/U profilde doğru, ama kendi içine kapanan bir profilde
    # (rollform ray, kapalı kutu profil) atılan iç tel DELİK DEĞİL,
    # profilin BOŞLUĞUDUR; atılınca alan şişer.
    #
    # Ölçülen: TIRSAN rayında dış tel 4219 mm2 veriyordu, telleriyle
    # 1936,5 mm2 - ve parça prizmatik olduğu için doğrusu hacim/boy =
    # 387290/200 = 1936,5. Şişmiş alan açınım genişliğini 1407 mm
    # gösteriyordu, doğrusu 646 mm.
    #
    # Kesit bir sac deliğinden geçerse şerit ikiye ayrılır ve yukarıdaki
    # "parçalı" denetimi zaten eler; o istasyon atlanır.
    return bul[0]


def _kenar_2b(yuz):
    """Kesit yüzünün kenarlarını 2B doğru ve yay olarak çıkarır."""
    duz, yay = [], []
    ex = TopExp_Explorer(yuz, TopAbs_EDGE)
    while ex.More():
        e = TopoDS.Edge_s(ex.Current())
        ex.Next()
        c = BRepAdaptor_Curve(e)
        p0, p1 = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
        a, b = (p0.X(), p0.Y()), (p1.X(), p1.Y())
        if c.GetType() == GeomAbs_Line:
            if math.dist(a, b) > 1e-6:
                duz.append([a, b])
        elif c.GetType() == GeomAbs_Circle:
            ci = c.Circle()
            mk = (ci.Location().X(), ci.Location().Y())
            span = abs(c.LastParameter() - c.FirstParameter())
            if span > 1e-6:
                yay.append({"m": mk, "r": ci.Radius(), "aci": span,
                            "p": a, "q": b})
        elif c.GetType() == GeomAbs_Ellipse:
            # Büküm eksenleri tasarımda birbirine tam paralel olmayabilir;
            # birkaç yüzde derecelik eğiklik silindiri ELİPS olarak keser.
            # Neredeyse dairesel olanı daire sayarız, yarıçapı küçük eksendir.
            el = c.Ellipse()
            kucuk, buyuk = el.MinorRadius(), el.MajorRadius()
            span = abs(c.LastParameter() - c.FirstParameter())
            if kucuk > 1e-9 and buyuk / kucuk < 1.02 and span > 1e-6:
                yay.append({"m": (el.Location().X(), el.Location().Y()),
                            "r": kucuk, "aci": span, "p": a, "q": b})
    return duz, yay


def _duzleri_birlestir(duz, tol=1e-6):
    """Aynı doğru üzerinde uç uca eklenmiş parçaları tek doğru yapar."""
    kalan, cikti = list(duz), []
    while kalan:
        a = kalan.pop()
        degisti = True
        while degisti:
            degisti = False
            for i, b in enumerate(kalan):
                ux, uy = a[1][0] - a[0][0], a[1][1] - a[0][1]
                n = math.hypot(ux, uy)
                ux, uy = ux / n, uy / n
                vx, vy = b[1][0] - b[0][0], b[1][1] - b[0][1]
                if abs(ux * vy - uy * vx) > 1e-6 * math.hypot(vx, vy):
                    continue              # paralel değil
                if abs((b[0][0] - a[0][0]) * uy - (b[0][1] - a[0][1]) * ux) > 1e-4:
                    continue              # aynı doğru üzerinde değil
                uc = [a[0], a[1], b[0], b[1]]
                t = [(p[0] - a[0][0]) * ux + (p[1] - a[0][1]) * uy for p in uc]
                if min(t[2], t[3]) - max(t[0], t[1]) > 1e-4 or \
                   min(t[0], t[1]) - max(t[2], t[3]) > 1e-4:
                    continue              # değmiyorlar
                s = sorted(zip(t, uc))
                a = [s[0][1], s[-1][1]]
                kalan.pop(i); degisti = True
                break
        cikti.append(a)
    return cikti


def _orta_ogeler(yuz, t, tol=None):
    """Kesitin orta çizgi ÖĞELERİNİ çıkarır (henüz sırasız).

    Sac kesiti, kalınlığı t olan bir şerittir: her düz duvar karşılıklı
    iki paralel doğru, her büküm ise eş merkezli iki yaydır. Önce bu
    çiftler eşleştirilir, sonra uçlarından zincire dizilir. Açınımda
    uzunluğunu koruyan çizgi bu orta çizgidir."""
    tol = tol or max(0.05, 0.08 * t)
    duz, yay = _kenar_2b(yuz)
    duz = _duzleri_birlestir(duz)
    ogeler = []

    # --- düz duvarlar: paralel, aralarındaki dik uzaklık t
    kul = set()
    for i, a in enumerate(duz):
        if i in kul:
            continue
        ux, uy = a[1][0] - a[0][0], a[1][1] - a[0][1]
        n = math.hypot(ux, uy); ux, uy = ux / n, uy / n
        en_iyi = None
        for j in range(len(duz)):
            if j == i or j in kul:
                continue
            b = duz[j]
            vx, vy = b[1][0] - b[0][0], b[1][1] - b[0][1]
            if abs(ux * vy - uy * vx) > 0.02 * math.hypot(vx, vy):
                continue
            u1 = (b[0][0] - a[0][0]) * -uy + (b[0][1] - a[0][1]) * ux
            u2 = (b[1][0] - a[0][0]) * -uy + (b[1][1] - a[0][1]) * ux
            if abs(abs(u1) - t) > tol or abs(u1 - u2) > tol:
                continue
            ta = sorted([(p[0] - a[0][0]) * ux + (p[1] - a[0][1]) * uy for p in a])
            tb = sorted([(p[0] - a[0][0]) * ux + (p[1] - a[0][1]) * uy for p in b])
            ort = min(ta[1], tb[1]) - max(ta[0], tb[0])
            if ort <= tol:
                continue
            if not en_iyi or ort > en_iyi[0]:
                en_iyi = (ort, j, (u1 + u2) / 2.0, max(ta[0], tb[0]), min(ta[1], tb[1]))
        if not en_iyi:
            continue                      # eş bulunamadı: uç kapağı ya da pah
        _, j, fark_u, s0, s1 = en_iyi
        kul.add(i); kul.add(j)
        # Orta çizgi iki yüzün TAM ORTASINDAN geçer: karşı yüzün uzaklığının
        # yarısı kadar kaydır.
        orta_u = fark_u / 2.0
        kok = (a[0][0] + orta_u * -uy, a[0][1] + orta_u * ux)
        ogeler.append({"tip": "duz", "uz": s1 - s0, "yon": (ux, uy),
                       "p": (kok[0] + s0 * ux, kok[1] + s0 * uy),
                       "q": (kok[0] + s1 * ux, kok[1] + s1 * uy)})

    # --- bükümler: eş merkezli, yarıçap farkı t
    kul = set()
    for i, a in enumerate(yay):
        if i in kul:
            continue
        for j in range(len(yay)):
            if j == i or j in kul:
                continue
            b = yay[j]
            if math.dist(a["m"], b["m"]) > tol:
                continue
            if abs(abs(a["r"] - b["r"]) - t) > tol:
                continue
            if abs(a["aci"] - b["aci"]) > 0.02:
                continue
            kul.add(i); kul.add(j)
            r_ic, r_dis = min(a["r"], b["r"]), max(a["r"], b["r"])
            r_o = (r_ic + r_dis) / 2.0
            dis = a if a["r"] > b["r"] else b
            uc = []
            for p in (dis["p"], dis["q"]):
                ac = math.atan2(p[1] - a["m"][1], p[0] - a["m"][0])
                uc.append((a["m"][0] + r_o * math.cos(ac),
                           a["m"][1] + r_o * math.sin(ac)))
            ogeler.append({"tip": "bukum", "r_ic": r_ic, "r_orta": r_o,
                           "aci": a["aci"], "m": a["m"],
                           "p": uc[0], "q": uc[1]})
            break

    if not ogeler:
        raise AcilimYok("Kesitin orta çizgisi kurulamadı: karşılıklı "
                        "yüzeyler eşleşmedi.")
    return ogeler


def _zincir(ogeler, birles=0.2):
    """Orta çizgi öğelerini uç uca sıralar. Sac şeridi tek parça, açık
    bir zincir olmak zorundadır."""
    uc = [[o["p"], o["q"]] for o in ogeler]

    def komsu(k, p):
        return [d for d in range(len(ogeler)) if d != k and
                min(math.dist(p, uc[d][0]), math.dist(p, uc[d][1])) < birles]

    kom = [(komsu(k, uc[k][0]), komsu(k, uc[k][1])) for k in range(len(ogeler))]
    kopuk = [k for k, (a, b) in enumerate(kom) if not a and not b]
    if kopuk:
        raise AcilimYok(
            f"Orta çizginin {len(kopuk)} parçası hiçbir komşuya değmiyor; "
            f"kesit tek bir sac şeridi değil.")
    uclar = [k for k, (a, b) in enumerate(kom) if not a or not b]
    if not uclar:
        raise AcilimYok("Kesitin orta çizgisi KAPALI çıktı. Kapalı profil - "
                        "boru, kutu profil - açınımı verilemez.")
    if len(uclar) != 2:
        raise AcilimYok(
            f"Orta çizginin {len(uclar)} serbest ucu var; sac şeridinin iki "
            f"ucu olur. Kesitte dallanma ya da kopukluk var.")
    k = uclar[0]
    p = uc[k][0] if not kom[k][0] else uc[k][1]     # zincirin SERBEST ucu
    zincir, gidilen = [], set()
    while True:
        zincir.append(ogeler[k]); gidilen.add(k)
        i = 0 if math.dist(p, uc[k][0]) < math.dist(p, uc[k][1]) else 1
        obur = uc[k][1 - i]
        ileri = [d for d in kom[k][1 - i] if d not in gidilen]
        if not ileri:
            break
        k, p = ileri[0], obur
    if len(gidilen) != len(ogeler):
        raise AcilimYok(
            f"Kesit tek bir şerit oluşturmuyor ({len(ogeler)} parçanın "
            f"{len(gidilen)} tanesi zincire girdi). Parça tek yönde bükülmüş "
            f"düz sac değil ya da kesitte kaynak/ek var.")
    return zincir


def _serit_genisligi(sh, kb, t, alan, boy, sebep, k_faktor=K_FAKTOR,
                     istasyon=9, sapma=0.03):
    """Prizmatik bir profilin şerit (bobin) genişliği.

    Orta çizgi kurulamayan parçalarda son çare. İki denetimden geçer,
    ikisi de tutmazsa hiçbir şey verilmez:

    1. Parça boy boyunca AYNI KESİTTE mi? Birkaç istasyonda alan
       ölçülür; oynuyorsa parça prizmatik değildir, tek bir şerit
       genişliğinden söz edilemez.
    2. Kesit alanı x boy, parçanın GERÇEK HACMİNE eşit mi? Eşitse kesit
       doğru ölçülmüş demektir. (TIRSAN rayında ölçülen: 1936,5 x 200 =
       387.290 mm3, parçanın hacmi de 387.290 mm3.)

    K-FAKTÖRÜ: alan/kalınlık, sacın ORTA YÜZEYİNİN uzunluğudur, yani
    K = 0,50 karşılığıdır. Gerçek K daha küçükse nötr eksen içe kayar
    ve şerit daralır. Düzeltme her büküm için θ·t·(0,5−K) kadardır;
    bükümlerin açıları, eşleştirme gerekmeden, içbükey (concave)
    silindir yüzeylerinden okunur - her bükümün bir tane içbükey yüzü
    vardır. (Rayda: 38 büküm, toplam 3076°; K 0,50'den 0,40'a inince
    genişlik 645,9'dan 629,8 mm'ye düşüyor.)
    """
    alanlar = []
    for i in range(istasyon):
        z = kb[2] + boy * (i + 0.5) / istasyon
        yz = _kesit_yuzu(sh, z, kb)
        if yz is None:
            continue
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(yz, g)
        alanlar.append(g.Mass())
    if len(alanlar) < max(3, istasyon - 2):
        return None                       # kesit her yerde alınamadı
    if max(alanlar) - min(alanlar) > 0.005 * max(alanlar):
        return None                       # kesit boy boyunca değişiyor
    a = sum(alanlar) / len(alanlar)
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g)
    hac = g.Mass()
    if hac <= 0 or abs(a * boy - hac) > sapma * hac:
        return None                       # kesit hacimle tutmuyor
    gen_orta = a / t                      # orta yüzey: K = 0,50 karşılığı
    ic_aci = 0.0
    ic_say = 0
    try:
        for b in bukum_yuzeyleri(sh):
            if b.get("ic"):
                ic_aci += b["aci"]; ic_say += 1
    except Exception:
        ic_aci = 0.0
    duzelt = ic_aci * t * (0.5 - k_faktor)
    gen = gen_orta - duzelt
    # Yöntem: kanat uzunlukları bilinmiyor (orta çizgi kurulamadı), ama
    # BÜKÜM YARIÇAPLARI biliniyor. Hepsi abkant sınırının altındaysa bu
    # parça abkantta yapılamaz - söylenebilecek kadarı budur.
    yon = {}
    try:
        ry = [b["r"] for b in bukum_yuzeyleri(sh)]
        if ry:
            _, r_k, _ = abkant_siniri()
            kucuk = sum(1 for r in ry if r / t < r_k)
            yon = {"yontem": "rollform" if kucuk > len(ry) / 2 else "",
                   "kesinlik": "olası", "bukum_sayisi": len(ry),
                   "en_kucuk_r_t": round(min(ry) / t, 2),
                   "neden": (f"{len(ry)} büküm yüzeyi var, yarıçapları "
                             f"{min(ry) / t:.2f}..{max(ry) / t:.2f} x kalınlık; "
                             f"{kucuk} tanesi abkant sınırı {r_k:g} katın "
                             f"altında. Kanat uzunlukları ölçülemedi.")}
            if not yon["yontem"]:
                yon = {}
    except Exception:
        yon = {}
    return {"kalinlik_mm": round(t, 2), "yontem": yon,
            "acinim_genislik_mm": round(gen, 2),
            "orta_yuzey_genislik_mm": round(gen_orta, 2),
            "k_duzeltmesi_mm": round(-duzelt, 2),
            "acinim_boy_mm": round(boy, 2),
            "bukum_sayisi": ic_say, "duvar_sayisi": 0,
            "k_faktor": k_faktor if ic_say else None,
            "kesit_alani_mm2": round(a, 1),
            "orta_cizgi_mm": round(gen, 2),
            "bukum_yerleri": [], "bukumler": [],
            "serit_genisligi": True,
            "kontur_notu": (
                f"ŞERİT GENİŞLİĞİDİR, açınım resmi değildir. Orta çizgi "
                f"kurulamadı ({sebep}) Parça boy boyunca aynı kesitte; "
                f"genişlik = kesit alanı / kalınlık = {a:.1f} / {t:.2f} = "
                f"{gen_orta:.1f} mm (orta yüzey, K=0,50). Hacimle "
                f"doğrulandı: {a:.0f} x {boy:.0f} = {a * boy:.0f} mm3, "
                f"parçanın hacmi {hac:.0f} mm3."
                + (f" K={k_faktor:g} icin {ic_say} bukumun toplam "
                   f"{math.degrees(ic_aci):.0f} derecesinden {duzelt:+.1f} mm "
                   f"duzeltme: {gen:.1f} mm." if ic_say else "")
                + " Büküm YERLERİ ve kesim konturu VERİLMEDİ.")}


def sac_acilim(sh, o=None, k_faktor=K_FAKTOR, istasyon=11,
               kontur=True):
    """Tek yönde bükülmüş sac parçanın açınımını hesaplar.

    Yöntem: büküm ekseni Z'ye döndürülür, parçadan DELİKSİZ bir kesit
    alınır, kesitin orta çizgisi sıralı olarak kurulur. Açınım genişliği
    düz duvarların uzunlukları ile her bükümün payının (BA) toplamıdır.
    Hesap ayrıca kesit alanıyla çapraz denetlenir: alan / kalınlık, orta
    çizginin uzunluğuna eşit olmak zorundadır."""
    ciftler = bukum_ciftleri(bukum_yuzeyleri(sh))
    eksen = bukum_ekseni(ciftler)
    t = sum(c["t"] for c in ciftler) / len(ciftler)
    ham = sh                            # döndürülmemiş hâli: kesim konturu
    sh = _eksene_dondur(sh, eksen)      # büküm ekseni artık Z

    kb = kutu(sh)
    boy = kb[5] - kb[2]
    # Deliksiz kesit ara: delik alanı yer yer götürür, sağlam istasyon
    # lazım. İlk tarama boş dönerse daha sık dene; delikli bir parçada
    # temiz aralık dar olabilir.
    en_iyi, konum = None, None
    for n in (istasyon, istasyon * 4):
        for i in range(n):
            z = kb[2] + boy * (i + 0.5) / n
            yuz = _kesit_yuzu(sh, z, kb)
            if yuz is None:
                continue
            g = GProp_GProps(); BRepGProp.SurfaceProperties_s(yuz, g)
            if not en_iyi or g.Mass() > en_iyi[0]:
                en_iyi, konum = (g.Mass(), yuz), z
        if en_iyi:
            break
    if not en_iyi:
        raise AcilimYok(
            "Parçanın hiçbir yerinde deliksiz, tek parça kesit bulunamadı.\n"
            "Boydan boya giden delik ya da oyuk varsa açınım genişliği "
            "güvenilir ölçülemez.")
    alan, yuz = en_iyi

    try:
        ogeler = _orta_ogeler(yuz, t)
        zincir = _zincir(ogeler, max(0.2, 0.1 * t))
        duzler = [z for z in zincir if z["tip"] == "duz"]
        bkm = [z for z in zincir if z["tip"] == "bukum"]
        if not bkm:
            raise AcilimYok("Kesitte büküm yayı bulunamadı.")
    except AcilimYok as e:
        # Orta çizgi kurulamadı. Yine de ŞERİT GENİŞLİĞİ verilebilir:
        # parça boy boyunca aynı kesitteyse (prizmatik) genişlik,
        # kesit alanı / kalınlıktır ve bunu HACİM bağımsız olarak
        # doğrular. Rollform profillerde zaten istenen budur: bobin
        # genişliği. Büküm yerleri ve kesim konturu verilmez.
        r = _serit_genisligi(sh, kb, t, alan, boy, str(e), k_faktor)
        if r is None:
            raise
        return r

    # Çapraz denetim: orta çizgi uzunluğu = kesit alanı / kalınlık
    orta = sum(z["uz"] for z in duzler) + sum(z["aci"] * z["r_orta"] for z in bkm)
    if abs(orta - alan / t) > max(0.5, 0.01 * orta):
        raise AcilimYok(
            f"Açınım denetimi tutmadı: orta çizgi {orta:.1f} mm, kesit "
            f"alanından çıkan {alan / t:.1f} mm. Aradaki fark, kesitin sac "
            f"şeridi gibi çözülemediğini gösteriyor; bu parçanın açınımı "
            f"verilemez.")

    # Açınım: düz duvarlar aynen, bükümler nötr eksen yayı kadar (BA)
    gen, yer, bilgi = 0.0, [], []
    for z in zincir:
        if z["tip"] == "duz":
            gen += z["uz"]
        else:
            ba = z["aci"] * (z["r_ic"] + k_faktor * t)
            bilgi.append({"r_ic": round(z["r_ic"], 2),
                          "r_dis": round(z["r_ic"] + t, 2),
                          "aci_derece": round(math.degrees(z["aci"]), 1),
                          "pay_mm": round(ba, 2),
                          "acinimda_bas_mm": round(gen, 2),
                          "acinimda_son_mm": round(gen + ba, 2)})
            yer.append((gen, gen + ba))
            gen += ba
    sonuc = {"kalinlik_mm": round(t, 2),
             "acinim_genislik_mm": round(gen, 2),
             "acinim_boy_mm": round(boy, 2),
             "bukum_sayisi": len(bkm),
             "duvar_sayisi": len(duzler),
             "k_faktor": k_faktor,
             "kesit_konumu_mm": round(konum - kb[2], 1),
             "kesit_alani_mm2": round(alan, 1),
             "orta_cizgi_mm": round(orta, 2),
             "bukum_yerleri": yer,
             "bukumler": bilgi}
    # Parça hangi yöntemle bükülmüş? Kanat uzunlukları ve iç yarıçaplar
    # buna karar vermeye yeter; tasarımcıya "bu abkantta yapılamaz"
    # demek, yanlış tezgâha gönderilmesini önler.
    sonuc["yontem"] = bukum_yontemi(
        t, [z["uz"] for z in duzler], [z["r_ic"] for z in bkm],
        [z["aci"] for z in bkm], boy)

    # Kesim konturu: lazer/pres için gereken gerçek dış kontur ve delikler.
    # Kesitten değil, YÜZEYLERDEN açılır; kesiti boy boyunca değişen
    # parçalar da böyle doğru çıkar.
    if kontur:
        hac = o.get("hacim_mm3") if isinstance(o, dict) else None
        # ÖNCE DÖNDÜRÜLMEMİŞ HÂLİ. Kesim konturu kendi eksenini zaten
        # buluyor, döndürülmüşe ihtiyacı yok; üstelik döndürmek zarar
        # veriyor. Teleskop profilinde ölçülen: ham parça 193,47x1940,
        # 96 delikle tam çıkıyor, döndürülmüşünde OpenCascade'in yüzey
        # birleştirmesi bozulup açınımı ikiye ayırıyordu (246188 +
        # 39864 mm2, oysa toplam 360236). Döndürme her yüzeyi yeniden
        # hesaplatıyor ve boole işlemlerinin sağlamlığını düşürüyor.
        #
        # Yine de ikisi de denenir: parça montajda eğik duruyorsa bu kez
        # ham hâli zorlanabilir. Her denemeyi hacim ve tek-parça
        # denetimleri ayrı ayrı korur, yani yanlış bir kontur geçemez.
        try:
            try:
                ac = acilim_kesim(ham, t, k_faktor, hacim=hac)
            except AcilimYok:
                ac = acilim_kesim(sh, t, k_faktor, hacim=hac)
            sonuc.update(ac)
            # İki bağımsız yöntem aynı genişliği vermeli: kesitten çıkan
            # orta çizgi hesabı ile yüzeyden açılan konturun genişliği.
            if abs(ac["acinim_genislik_mm"] - gen) > max(0.5, 0.01 * gen):
                sonuc["kontur_notu"] = (
                    f"Not: kesitten çıkan açınım genişliği {gen:.1f} mm, "
                    f"yüzeyden açılan kontur {ac['acinim_genislik_mm']:.1f} mm. "
                    f"Fark, parçanın kesitinin boy boyunca değişmesinden "
                    f"gelir; kontur ölçüsü geçerlidir.")
        except AcilimYok as e:
            sonuc["kontur_notu"] = (f"Kesim konturu çıkarılamadı: {e} "
                                    f"Resimde yalnız blank ölçüsü var.")
        except Exception as e:
            sonuc["kontur_notu"] = (
                f"Kesim konturu çıkarılamadı ({type(e).__name__}). "
                f"Resimde yalnız blank ölçüsü var.")
    return sonuc


def _nokta_icinde(p, halka):
    """Nokta çokgenin içinde mi (ışın yöntemi)."""
    x, y = p
    ic = False
    n = len(halka)
    for i in range(n):
        x1, y1 = halka[i]
        x2, y2 = halka[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            kes = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if kes > x:
                ic = not ic
    return ic


def _dis_halkalar(sekil, sapma=0.02):
    """Birleştirilmiş bölgenin sınır halkalarını çıkarır.

    OpenCascade eş düzlemli yüzleri her zaman tek yüze kaynatmıyor;
    kaynatmadığında yüz yüz sınır almak, aradaki dikişleri de kesim
    çizgisi gibi gösterir. Bunun yerine TOPOLOJİ kullanılır: iki yüzün
    paylaştığı kenar iç dikiştir, yalnız TEK yüze ait kenarlar bölgenin
    gerçek sınırıdır. Kalan kenarlar halkalara dizilir."""
    h = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(sekil, TopAbs_EDGE, TopAbs_FACE, h)
    kenar = TopTools_HSequenceOfShape()
    for i in range(1, h.Extent() + 1):
        if h.FindFromIndex(i).Extent() == 1:
            kenar.Append(h.FindKey(i))
    if kenar.Length() == 0:
        return [], []
    teller = TopTools_HSequenceOfShape()
    ShapeAnalysis_FreeBounds.ConnectEdgesToWires_s(kenar, 1e-5, False, teller)
    halka = []
    for i in range(1, teller.Length() + 1):
        p = _tel_dizisi(TopoDS.Wire_s(teller.Value(i)), sapma)
        n = [(q.X(), q.Y()) for q in p]
        if len(n) > 2:
            halka.append(n)
    if not halka:
        return [], []
    # En büyük halka dış konturdur; içinde kalanlar deliktir. İçinde
    # kalmayan ikinci bir halka varsa açınım parçalı demektir.
    halka.sort(key=lambda w: abs(_cokgen_alani(w)), reverse=True)
    dis, ic = [halka[0]], []
    for w in halka[1:]:
        (ic if _nokta_icinde(w[0], halka[0]) else dis).append(w)
    return dis, ic


def acilim_kesim(sh, t, k_faktor, hacim=None, en_cok_sapma=0.03):
    """Sacı yüzeylerinden açar ve KESİM KONTURUNU döndürür.

    Sonuç, bağımsız bir ölçüyle denetlenir: düzlemdeki alan x kalınlık,
    parçanın gerçek hacmine eşit olmak zorundadır (büküm payının
    K-faktöründen gelen küçük farkı hesaba katılarak). Tutmazsa sonuç
    verilmez: lazerde hurda çıkarmaktansa hiç vermemek gerekir."""
    parca, delik, harita, b_harita, duvarlar, bukumler = sac_ac(sh, t, k_faktor)
    taban = _birlestir([f for f in (_cokgen_yuzu(w) for w in parca) if f])
    if taban is None:
        raise AcilimYok("Açınım parçaları düzlemde birleştirilemedi.")
    delik_yuz = [f for f in (_cokgen_yuzu(w) for w in delik) if f]
    if delik_yuz:
        op = BRepAlgoAPI_Cut(taban, _birlestir(delik_yuz, sadelestir=False))
        op.SetFuzzyValue(0.01)
        op.Build()
        if op.IsDone():
            taban = op.Shape()
    g = GProp_GProps(); BRepGProp.SurfaceProperties_s(taban, g)
    alan = g.Mass()
    if hacim:
        # K != 0,5 olduğunda büküm bölgesi, orta yüzey alanından biraz
        # farklı hacim tutar; farkı tam olarak hesaplayıp düş.
        duzelt = sum(b["aci"] * t * t
                     * (bukumler[bi]["z"][1] - bukumler[bi]["z"][0])
                     * (0.5 - k_faktor) for bi, b in b_harita.items())
        sapma = (alan * t + duzelt - hacim) / hacim
        if abs(sapma) > en_cok_sapma:
            raise AcilimYok(
                f"Açınım denetimi tutmadı: düzlemdeki alan x kalınlık "
                f"{alan * t + duzelt:.0f} mm3, parçanın hacmi {hacim:.0f} "
                f"mm3 (%{100 * sapma:+.1f}). Açma haritası bu parçada "
                f"doğru kurulamamış; kontur verilmiyor.")
    # Sınırı topolojiden çıkar: paylaşılan kenarlar iç dikiştir.
    dis, ic = _dis_halkalar(taban)
    if not dis:
        raise AcilimYok("Açınımın sınırı çıkarılamadı.")
    # Açınım TEK PARÇA olmak zorundadır. Parçalı çıkıyorsa duvarlar
    # düzlemde uç uca oturmamış demektir; o zaman aradaki dikişler
    # kesim çizgisi gibi görünür ve lazerde parça ikiye ayrılır.
    if len(dis) != 1:
        ayri = sorted((abs(_cokgen_alani(w)) for w in dis), reverse=True)
        raise AcilimYok(
            f"Açınım düzlemde {len(dis)} ayrı parça çıktı; duvarlar uç uca "
            f"oturmadı. Parça alanları: "
            + ", ".join(f"{a:.0f} mm2" for a in ayri[:4])
            + ". Kesim konturu verilmiyor.")
    xs = [p[0] for w in dis for p in w]; ys = [p[1] for w in dis for p in w]
    dx, dy = -min(xs), -min(ys)
    kay = lambda w: [(x + dx, y + dy) for x, y in w]
    # Büküm çizgileri: ağaçtaki her bükümün düzlemdeki başı ve sonu
    bkm = []
    for bi, b in sorted(b_harita.items(), key=lambda kv: min(kv[1]["s"],
                                                             kv[1]["s_son"])):
        a1, a2 = sorted((b["s"] + dy, b["s_son"] + dy))
        bkm.append({"r_ic": round(bukumler[bi]["r_ic"], 2),
                    "r_dis": round(bukumler[bi]["r_ic"] + t, 2),
                    "aci_derece": round(math.degrees(b["aci"]), 1),
                    "pay_mm": round(b["pay"], 2),
                    "acinimda_bas_mm": round(a1, 2),
                    "acinimda_son_mm": round(a2, 2)})
    # Büküm yöntemi BURADAN hesaplanır, kesitten değil: kesit parçanın
    # tek bir yerinden geçer, boy boyunca değişen dar kanatları
    # kaçırabilir. Yüzey ağacı bütün parçayı görür.
    yon = bukum_yontemi(
        t, [abs(d["p"][1] - d["p"][0]) for d in duvarlar],
        [bukumler[bi]["r_ic"] for bi in b_harita],
        [b["aci"] for b in b_harita.values()],
        max((d["z"][1] - d["z"][0] for d in duvarlar), default=0.0))
    return {"yontem": yon,
            "kontur_dis": [kay(w) for w in dis],
            "kontur_delik": [kay(w) for w in ic],
            "delik_adedi": len(ic),
            "acinim_boy_mm": round(max(xs) - min(xs), 2),
            "acinim_genislik_mm": round(max(ys) - min(ys), 2),
            "acinim_alan_mm2": round(alan, 1),
            "duvar_sayisi": len(harita),
            "bukum_sayisi": len(bkm),
            "bukumler": bkm,
            "bukum_yerleri": [(b["acinimda_bas_mm"], b["acinimda_son_mm"])
                              for b in bkm]}


# ------------------------------------------------------- açınım konturu
# Açınım resmi kesim içindir: lazer, pres, delme. O yüzden BLANK
# dikdörtgeni değil, parçanın GERÇEK kesim konturu ve delikleri çıkar.
#
# Yöntem, sacın fiziksel olarak açılmasının aynısıdır:
#   * Her düz duvar, kendi düzlemindeki sac yüzüdür. Yüzün sınırı
#     (dış kontur + delikler) düzleme OLDUĞU GİBİ taşınır; duvar zaten
#     düzdür, şekli bozulmaz.
#   * Her büküm, silindir yüzeyinin NÖTR EKSENDE açılmasıdır. Silindirin
#     sınırı, açı farkı x nötr yarıçap ile düzleme yayılır. Büküm
#     boşaltmaları (relief) da böylece kendiliğinden gelir.
#   * Parçalar düzlemde birleştirilir, aradaki teğet çizgileri silinir.
#
# Düzlem koordinatları:  X = büküm ekseni boyunca (z),  Y = açınım
# boyunca (s). Böylece büküm çizgileri yatay olur.
SAPMA = 0.05                      # eğri -> çokgen çevirme sapması, mm


def _tel_dizisi(tel, sapma=SAPMA):
    """Bir teli SIRALI nokta dizisine çevirir."""
    p = []
    ex = BRepTools_WireExplorer(tel)
    while ex.More():
        e = ex.Current()
        ters = e.Orientation() == TopAbs_REVERSED
        c = BRepAdaptor_Curve(e)
        d = GCPnts_TangentialDeflection(c, sapma, 0.2)
        q = [c.Value(d.Parameter(i)) for i in range(1, d.NbPoints() + 1)]
        if ters:
            q.reverse()
        if p and q and math.dist((p[-1].X(), p[-1].Y(), p[-1].Z()),
                                 (q[0].X(), q[0].Y(), q[0].Z())) > 1e-6:
            q.reverse()
        p += q[1:] if p else q
        ex.Next()
    return p


def _yuz_telleri(yuz, sapma=SAPMA):
    """(dış tel noktaları, [delik teli noktaları, ...])"""
    dis_tel = BRepTools.OuterWire_s(yuz)
    dis, ic = _tel_dizisi(dis_tel, sapma), []
    ex = TopExp_Explorer(yuz, TopAbs_WIRE)
    while ex.More():
        w = TopoDS.Wire_s(ex.Current())
        if not w.IsSame(dis_tel):
            ic.append(_tel_dizisi(w, sapma))
        ex.Next()
    return dis, ic


def _duvar_yuzleri(sh, oge, t, tol=None):
    """Bir düz duvarın sac yüzleri. Sacın İKİ yüzü de aday; toplam alanı
    büyük olan taraf seçilir. Havşa/cep varsa o taraftaki delik büyük
    görünür; büyük alanlı taraf, gerçek geçme deliğini veren taraftır."""
    tol = tol or max(0.1, 0.1 * t)
    ux, uy = _duz_yon(oge)
    nx, ny = -uy, ux                       # duvara dik yön
    d_orta = oge["p"][0] * nx + oge["p"][1] * ny
    s_bas = oge["p"][0] * ux + oge["p"][1] * uy
    s_son = s_bas + oge["uz"]
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    taraf = {1: [], -1: []}
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Plane:
            continue
        dn = ad.Plane().Axis().Direction()
        if abs(dn.Z()) > 0.02:
            continue                        # eksene dik değil: uç yüzey
        if abs(abs(dn.X() * nx + dn.Y() * ny) - 1.0) > 0.02:
            continue                        # bu duvara paralel değil
        q = ad.Plane().Location()
        d = q.X() * nx + q.Y() * ny
        for yon in (1, -1):
            if abs(d - (d_orta + yon * t / 2.0)) <= tol:
                fk = kutu(f)
                # yüzün duvar üzerindeki aralığı, öğeyle örtüşüyor mu?
                ks = [(fk[0], fk[1]), (fk[0], fk[4]), (fk[3], fk[1]), (fk[3], fk[4])]
                pr = [a * ux + b * uy for a, b in ks]
                if min(max(pr), s_son) - max(min(pr), s_bas) > 0.1:
                    g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
                    taraf[yon].append((g.Mass(), f))
    a1 = sum(x for x, _ in taraf[1]); a2 = sum(x for x, _ in taraf[-1])
    sec = taraf[1] if a1 >= a2 else taraf[-1]
    return [f for _, f in sec]


def _bukum_yuzleri_kati(sh, oge, tol=0.2):
    """Bir bükümün silindir yüzeyleri (iç ve dış)."""
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    out = []
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        c = ad.Cylinder()
        d = c.Position().Direction()
        if abs(abs(d.Z()) - 1.0) > 0.02:
            continue
        ek = c.Position().Location()
        if math.dist((ek.X(), ek.Y()), oge["m"]) > tol:
            continue
        if min(abs(c.Radius() - oge["r_ic"]),
               abs(c.Radius() - (oge["r_ic"] + 2 * (oge["r_orta"] - oge["r_ic"])))) > tol:
            continue
        out.append(f)
    return out


def _aci_farki(a, b):
    """b - a, (-pi, pi] aralığına indirgenmiş."""
    return (b - a + math.pi) % (2 * math.pi) - math.pi


def _duz_yon(oge):
    """Düz öğenin zincirdeki gidiş yönü (p'den q'ya)."""
    dx, dy = oge["q"][0] - oge["p"][0], oge["q"][1] - oge["p"][1]
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-9 else oge.get("yon", (1.0, 0.0))


def acilim_telleri(sh, zincir, t, k_faktor):
    """Açınımın düzlemdeki tellerini üretir.

    Geri dönüş: (parça dış telleri, delik telleri). Noktalar düzlem
    koordinatındadır: (z, s)."""
    parca, delik = [], []
    s0 = 0.0
    for oge in zincir:
        if oge["tip"] == "duz":
            ux, uy = _duz_yon(oge)
            s_bas = oge["p"][0] * ux + oge["p"][1] * uy
            taban = s0

            def harita(p, ux=ux, uy=uy, s_bas=s_bas, taban=taban):
                return (p.Z(), taban + (p.X() * ux + p.Y() * uy) - s_bas)

            yuzler = _duvar_yuzleri(sh, oge, t)
            ilerle = oge["uz"]
        else:
            mx, my = oge["m"]
            r_n = oge["r_ic"] + k_faktor * t
            f_bas = math.atan2(oge["p"][1] - my, oge["p"][0] - mx)
            f_son = math.atan2(oge["q"][1] - my, oge["q"][0] - mx)
            yon = 1.0 if _aci_farki(f_bas, f_son) >= 0 else -1.0
            taban = s0

            def harita(p, mx=mx, my=my, f_bas=f_bas, yon=yon, r_n=r_n, taban=taban):
                f = math.atan2(p.Y() - my, p.X() - mx)
                return (p.Z(), taban + yon * _aci_farki(f_bas, f) * r_n)

            yuzler = _bukum_yuzleri_kati(sh, oge)
            ilerle = oge["aci"] * r_n
        for f in yuzler:
            try:
                dis, ic = _yuz_telleri(f)
            except Exception:
                continue
            if len(dis) > 2:
                parca.append([harita(p) for p in dis])
            delik += [[harita(p) for p in w] for w in ic if len(w) > 2]
        s0 += ilerle
    if not parca:
        raise AcilimYok("Açınım konturu kurulamadı: duvarların sac yüzeyleri "
                        "bulunamadı.")
    return parca, delik


# ------------------------------------------------- yüzeyden açma (genel)
# Tek kesitten kurulan zincir, kesiti boy boyunca DEĞİŞEN parçalarda
# yanılır: bir bölümünde fazladan flanşı olan sac, kesiti nereden alırsan
# al ya o flanşı görmez ya da yalnız onu görür. Bu yüzden açınım
# doğrudan YÜZEYLERDEN kurulur:
#
#   duvar  = birbirine sac kalınlığı kadar uzak, eksene paralel iki düzlem
#   büküm  = ekseni sac eksenine paralel, iç/dış yarıçap farkı kalınlık
#            kadar olan silindir çifti
#   komşuluk = bükümün nötr silindiri duvarın ORTA DÜZLEMİNE teğettir
#
# Duvarlar ve bükümler bir AĞAÇ oluşturur. Ağaç kökten gezilir, her
# duvara düzlemdeki yeri (s = A + B*p) verilir, bükümler nötr eksende
# açılır. Böylece parçanın hangi bölümünde hangi flanşın olduğu fark
# etmez; her yüzey kendi yerine oturur.


def _kanonik_yon3(n):
    """Düzlem normalini tek biçime indirir (3B).

    Karşılaştırmalar SIFIRA TOLERANSLIDIR: tam eksenel bir yüzeyde
    bileşenin 1e-17'lik işareti, aynı düzlemi iki ayrı düzlem gibi
    gösterip eşleşmeyi bozuyordu."""
    x, y, z = n
    b = math.sqrt(x * x + y * y + z * z)
    if b < 1e-9:
        return None
    x, y, z = x / b, y / b, z / b
    if y < -1e-12 or (abs(y) <= 1e-12 and x < -1e-12) or \
       (abs(y) <= 1e-12 and abs(x) <= 1e-12 and z < 0.0):
        x, y, z = -x, -y, -z
    if abs(x) <= 1e-12:
        x = 0.0
    if abs(y) <= 1e-12:
        y = 0.0
    if abs(z) <= 1e-12:
        z = 0.0
    return (x, y, z)


def _kenar_anahtari(e, yuvarla=1e-4):
    """Bir kenarı uçlarından tek biçimde adlandırır. İki yüz aynı kenarı
    paylaşıyorsa aynı anahtarı verir."""
    uc = []
    ex = TopExp_Explorer(e, TopAbs_VERTEX)
    gor = []
    while ex.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current()))
        t = (round(p.X() / yuvarla), round(p.Y() / yuvarla), round(p.Z() / yuvarla))
        if t not in gor:
            gor.append(t)
        ex.Next()
    uc = sorted(gor)
    return tuple(uc)


def _bitisik_gruplar(yuzler):
    """Aynı düzlemdeki yüzleri KENAR KOMŞULUĞUNA göre ayrı parçalara böler.

    Bir duvar, aynı düzlemde olsa bile başka bir duvarla kesilmiş olabilir:
    sacın ortasına basılmış bir kaburga, alt yüzeyi iki ayrı şeride böler.
    Bu iki şerit açınımda AYRI yerlere düşer; tek duvar sayılırlarsa
    büküm ağacı yanlış kurulur."""
    anahtar = []
    for f in yuzler:
        k = set()
        ex = TopExp_Explorer(f, TopAbs_EDGE)
        while ex.More():
            k.add(_kenar_anahtari(TopoDS.Edge_s(ex.Current())))
            ex.Next()
        anahtar.append(k)
    ana = list(range(len(yuzler)))

    def kok(i):
        while ana[i] != i:
            ana[i] = ana[ana[i]]; i = ana[i]
        return i

    for i in range(len(yuzler)):
        for j in range(i + 1, len(yuzler)):
            if anahtar[i] & anahtar[j]:
                ana[kok(i)] = kok(j)
    grup = defaultdict(list)
    for i, f in enumerate(yuzler):
        grup[kok(i)].append(f)
    return list(grup.values())


def _yuz_p_araligi(yuzler, u):
    """Yüzlerin duvar üzerindeki (u yönündeki) uzanımı."""
    pr = []
    for f in yuzler:
        ex = TopExp_Explorer(f, TopAbs_VERTEX)
        while ex.More():
            p = BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current()))
            pr.append(p.X() * u[0] + p.Y() * u[1])
            ex.Next()
    return (min(pr), max(pr)) if pr else None


def _ayni_duvar_birlestir(gruplar, n, en_az_ortusme=0.5):
    """Aynı duvarın, boy boyunca kesiklerle ayrılmış parçalarını birleştirir.

    Kenar komşuluğuna göre bölmek şart: sacın ortasına basılmış bir
    kaburga, alt yüzeyi iki AYRI duvara böler ve bunlar açınımda ayrı
    yerlere düşer. Ama uzun bir flanşı boydan boya kesikler de bölüyor;
    onlar AYNI duvardır, açınımda aynı yere düşerler.

    İkisini ayıran ölçü: kesitteki uzanım (p). Kaburganın iki yanındaki
    şeritler p'de ayrıktır; kesiklerle bölünmüş flanş parçaları ise aynı
    p aralığını paylaşır, yalnız boyda (z) ayrıktır."""
    u = _kanonik_yon((-n[1], n[0]))
    if not u or len(gruplar) < 2:
        return gruplar
    kutu = [(_yuz_p_araligi(g, u), g) for g in gruplar]
    kutu = [(a, g) for a, g in kutu if a]
    birlesik = []
    for a, g in sorted(kutu, key=lambda x: x[0][0]):
        for b in birlesik:
            ort = min(a[1], b["p"][1]) - max(a[0], b["p"][0])
            en_dar = min(a[1] - a[0], b["p"][1] - b["p"][0])
            if ort > en_az_ortusme * max(en_dar, 1e-9):
                b["yuz"] += g
                b["p"] = (min(a[0], b["p"][0]), max(a[1], b["p"][1]))
                break
        else:
            birlesik.append({"p": a, "yuz": list(g)})
    return [b["yuz"] for b in birlesik]


def _duzlem_duvarlar(sh, t, tol=None):
    """Sac duvarları: eksene paralel, kalınlık kadar aralıklı düzlem çifti.

    Duvar "eksene tam paralel" olmayabilir. Büküm eksenleri tasarımda
    birbirine tam oturmadığı için parçayı döndürünce duvarlar yarım
    derece eğik kalır. Bu yüzden düzlem 3B olarak tutulur; uzaklıklar
    düzlemin kendi normali boyunca ölçülür."""
    tol = tol or max(0.08, 0.08 * t)
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    kume = {}
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Plane:
            continue
        d3 = ad.Plane().Axis().Direction()
        if abs(d3.Z()) > 0.05:
            continue                       # eksene dik: uç kapağı
        n = _kanonik_yon3((d3.X(), d3.Y(), d3.Z()))
        if not n:
            continue
        q = ad.Plane().Location()
        d0 = q.X() * n[0] + q.Y() * n[1] + q.Z() * n[2]
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
        fk = kutu(f)
        # Aynı düzlemdeki yüzeyler aynı (n, d0) verir; kova sınırına
        # denk gelenler için komşu kovaya da bak.
        anahtar = None
        for kk in kume:
            if abs(kk[0] - n[0]) < 1e-4 and abs(kk[1] - n[1]) < 1e-4 \
               and abs(kk[2] - n[2]) < 1e-4 and abs(kume[kk]["d0"] - d0) < tol / 2:
                anahtar = kk
                break
        if anahtar is None:
            anahtar = (round(n[0], 6), round(n[1], 6), round(n[2], 6),
                       round(d0, 4))
            kume[anahtar] = {"n": n, "d0": d0, "uye": [], "alan": 0.0,
                             "z": [fk[2], fk[5]]}
        g0 = kume[anahtar]
        g0["uye"].append(f); g0["alan"] += g.Mass()
        g0["z"] = [min(g0["z"][0], fk[2]), max(g0["z"][1], fk[5])]
    # Aynı düzlemdeki ayrı şeritleri böl: her biri kendi duvarıdır.
    duzlemler = []
    for v in kume.values():
        if v["alan"] <= 1.0:
            continue
        for parcalar in _ayni_duvar_birlestir(_bitisik_gruplar(v["uye"]),
                                              v["n"]):
            a = 0.0; zr = []
            for f in parcalar:
                g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
                a += g.Mass(); fk = kutu(f); zr += [fk[2], fk[5]]
            u0 = _kanonik_yon((-v["n"][1], v["n"][0]))
            pr = []
            for f in parcalar:
                ex = TopExp_Explorer(f, TopAbs_VERTEX)
                while ex.More():
                    p = BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current()))
                    pr.append(p.X() * u0[0] + p.Y() * u0[1])
                    ex.Next()
            duzlemler.append({"n": v["n"], "d0": v["d0"], "uye": parcalar,
                              "alan": a, "z": [min(zr), max(zr)],
                              "p": (min(pr), max(pr))})
    # Düzlemleri kalınlık kadar uzaklıkta eşleştir: bir duvar, sacın iki
    # yüzeyidir. Paralel düzlemlerde bu uzaklık z'den bağımsızdır.
    duvar, kullanildi = [], set()
    for i, a in enumerate(duzlemler):
        if i in kullanildi:
            continue
        en_iyi = None
        for j in range(len(duzlemler)):
            if j == i or j in kullanildi:
                continue
            b = duzlemler[j]
            if sum(a["n"][k] * b["n"][k] for k in range(3)) < 0.9998:
                continue
            if abs(abs(a["d0"] - b["d0"]) - t) > tol:
                continue
            if min(a["z"][1], b["z"][1]) - max(a["z"][0], b["z"][0]) < 0.5:
                continue
            ortusme = (min(a["p"][1], b["p"][1]) - max(a["p"][0], b["p"][0]))
            if ortusme < 0.5 * min(a["p"][1] - a["p"][0], b["p"][1] - b["p"][0]):
                continue                   # sacın karşı yüzü değil
            puan = min(a["alan"], b["alan"]) / max(a["alan"], b["alan"])
            if not en_iyi or puan > en_iyi[0]:
                en_iyi = (puan, j)
        if not en_iyi:
            continue
        j = en_iyi[1]; b = duzlemler[j]
        kullanildi.add(i); kullanildi.add(j)
        # Delikler için TEK taraf kullanılır: alanı büyük olan taraf.
        # Havşa/cep açılmış tarafta delik büyük görünür; alanı büyük olan
        # taraf gerçek geçme deliğini verir.
        sec = a if a["alan"] >= b["alan"] else b
        u = _kanonik_yon((-a["n"][1], a["n"][0]))
        if not u:
            continue
        pr, zr = [], []
        for f in sec["uye"]:
            ex = TopExp_Explorer(f, TopAbs_VERTEX)
            while ex.More():
                p = BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current()))
                pr.append(p.X() * u[0] + p.Y() * u[1]); zr.append(p.Z())
                ex.Next()
        if not pr:
            continue
        duvar.append({"n": a["n"], "u": u, "d0": (a["d0"] + b["d0"]) / 2.0,
                      "yuzler": sec["uye"], "alan": sec["alan"],
                      "p": (min(pr), max(pr)), "z": (min(zr), max(zr))})
    return duvar


def _kanonik_yon(n2):
    """İki boyutlu yön için tek biçim."""
    nx, ny = n2
    b = math.hypot(nx, ny)
    if b < 1e-9:
        return None
    nx, ny = nx / b, ny / b
    if ny < -1e-12 or (abs(ny) <= 1e-12 and nx < 0.0):
        nx, ny = -nx, -ny
    if abs(ny) <= 1e-12:
        return (1.0, 0.0)
    if abs(nx) <= 1e-12:
        return (0.0, 1.0)
    return (nx, ny)


def _silindir_bukumler(sh, t, tol=None):
    """Bükümler: ekseni Z'ye paralel, yarıçap farkı kalınlık kadar olan
    silindir çiftleri."""
    tol = tol or max(0.08, 0.08 * t)
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    grup = defaultdict(list)
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        c = ad.Cylinder()
        d3 = c.Position().Direction()
        if abs(abs(d3.Z()) - 1.0) > 0.02:
            continue
        ek = c.Position().Location()
        grup[(round(ek.X() / 0.05), round(ek.Y() / 0.05))].append((f, c, ek))
    out = []
    for lst in grup.values():
        r = [x[1].Radius() for x in lst]
        r_ic, r_dis = min(r), max(r)
        if abs((r_dis - r_ic) - t) > tol:
            continue
        zr = []
        for f, _c, _e in lst:
            fk = kutu(f); zr += [fk[2], fk[5]]
        # Bükümün İÇ ve DIŞ silindiri düzlemde neredeyse üst üste düşer.
        # İkisini birden haritalamak, boole işlemine iki çakışık yüz verip
        # kıymık yüzeyler doğurur. Alanı büyük olan taraf (dış) yeter.
        taraf = defaultdict(list)
        for f, c, _e in lst:
            g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
            taraf[round(c.Radius(), 3)].append((f, g.Mass()))
        en_iyi = max(taraf.values(), key=lambda v: sum(x[1] for x in v))
        zr = []
        for f, _a in en_iyi:
            fk = kutu(f); zr += [fk[2], fk[5]]
        out.append({"m": (lst[0][2].X(), lst[0][2].Y()), "r_ic": r_ic,
                    "yuzler": [f for f, _a in en_iyi], "z": (min(zr), max(zr))})
    return out


def _agac_kur(duvarlar, bukumler, t, tol=None):
    """Büküm hangi iki duvara değiyor? Nötr silindir duvarın orta
    düzlemine TEĞETTİR: eksenin düzleme uzaklığı = r_ic + t/2."""
    tol = tol or max(0.15, 0.1 * t)
    r_yari = t / 2.0
    for b in bukumler:
        b["duvar"] = []
        hedef = b["r_ic"] + r_yari
        for i, w in enumerate(duvarlar):
            ort = (max(w["z"][0], b["z"][0]), min(w["z"][1], b["z"][1]))
            if ort[1] - ort[0] < 0.5:
                continue                   # z'de hiç örtüşmüyorlar
            # Duvar eksene tam paralel olmayabilir; uzaklığı ikisinin
            # ORTAK BOYUNUN ortasında ölç.
            zo = (ort[0] + ort[1]) / 2.0
            sd = (b["m"][0] * w["n"][0] + b["m"][1] * w["n"][1]
                  + zo * w["n"][2] - w["d0"])
            if abs(abs(sd) - hedef) > tol + abs(w["n"][2]) * (ort[1] - ort[0]):
                continue
            # teğet nokta duvarın uzanımı içinde mi, z'de örtüşüyor mu?
            q = (b["m"][0] - sd * w["n"][0], b["m"][1] - sd * w["n"][1])
            p = q[0] * w["u"][0] + q[1] * w["u"][1]
            if not (w["p"][0] - tol <= p <= w["p"][1] + tol):
                continue
            b["duvar"].append({"i": i, "p": p, "sd": sd,
                               "aci": math.atan2(-sd * w["n"][1],
                                                 -sd * w["n"][0])})
        if len(b["duvar"]) > 2:            # en yakın iki duvarı tut
            b["duvar"].sort(key=lambda d: abs(abs(d["sd"]) - hedef))
            b["duvar"] = b["duvar"][:2]
    return [b for b in bukumler if len(b["duvar"]) == 2]


def _bagsiz_duvar_raporu(duvarlar, bukumler, disarda, t, en_cok=6):
    """Bağlanamayan duvarları, NEDEN bağlanamadıklarıyla birlikte yazar.

    Her duvar için en yakın bükümü bulup iki ölçüyü gösterir: teğetlik
    uzaklığı (olması gereken r_ic + t/2) ve boy boyunca örtüşme. Hangisi
    tutmuyorsa sorun oradadır."""
    if not disarda:
        return ""
    sat = ["", "Bağlanamayan duvarlar (en büyükten):"]
    sirali = sorted(disarda, key=lambda i: -duvarlar[i]["alan"])
    for i in sirali[:en_cok]:
        w = duvarlar[i]
        en_iyi = None
        for b in bukumler:
            ort = (max(w["z"][0], b["z"][0]), min(w["z"][1], b["z"][1]))
            zo = (ort[0] + ort[1]) / 2.0 if ort[1] > ort[0] else w["z"][0]
            uz = abs(b["m"][0] * w["n"][0] + b["m"][1] * w["n"][1]
                     + zo * w["n"][2] - w["d0"])
            hedef = b["r_ic"] + t / 2.0
            puan = abs(uz - hedef)
            if en_iyi is None or puan < en_iyi[0]:
                en_iyi = (puan, uz, hedef, ort[1] - ort[0])
        if en_iyi is None:
            sat.append(f"  alan {w['alan']:8.0f} mm2 - hiç büküm yok")
            continue
        _, uz, hedef, ort = en_iyi
        if ort < 0.5:
            neden = f"boy boyunca hiç örtüşmüyor ({ort:.1f} mm)"
        elif abs(uz - hedef) > 0.15:
            neden = (f"teğet değil: bükümden uzaklık {uz:.2f} mm, "
                     f"olması gereken {hedef:.2f} mm")
        else:
            neden = "ağacın kopuk bir dalında kalmış"
        sat.append(f"  alan {w['alan']:8.0f} mm2  boy [{w['z'][0]:.0f}, "
                   f"{w['z'][1]:.0f}]  ->  {neden}")
    if len(sirali) > en_cok:
        sat.append(f"  ... ve {len(sirali) - en_cok} duvar daha")
    return "\n".join(sat)


def _acma_haritasi(duvarlar, bukumler, t, k_faktor):
    """Ağacı gezerek her duvara ve her büküme düzlemdeki yerini verir.

    Duvar için  s = A + B * p   (p: duvar üzerindeki uzaklık)
    Büküm için  s = s_teget + e * dfi * r_n"""
    komsu = defaultdict(list)
    for bi, b in enumerate(bukumler):
        a, c = b["duvar"]
        komsu[a["i"]].append((bi, a, c))
        komsu[c["i"]].append((bi, c, a))
    if not komsu:
        raise AcilimYok("Hiçbir büküm iki duvara birden değmiyor; parçanın "
                        "duvar-büküm zinciri kurulamadı.")
    kok = min(komsu)
    harita = {kok: (0.0, 1.0)}
    b_harita, gidilen, sira = {}, {kok}, [kok]
    while sira:
        wi = sira.pop()
        A, B = harita[wi]
        w = duvarlar[wi]
        orta = (w["p"][0] + w["p"][1]) / 2.0
        for bi, bu, obur in komsu[wi]:
            if bi in b_harita:
                continue
            b = bukumler[bi]
            r_n = b["r_ic"] + k_faktor * t
            aci = abs(_aci_farki(bu["aci"], obur["aci"]))
            if aci < 1e-3:
                continue
            s_teget = A + B * bu["p"]
            e = B * (1.0 if bu["p"] >= orta else -1.0)
            yon = 1.0 if _aci_farki(bu["aci"], obur["aci"]) >= 0 else -1.0
            b_harita[bi] = {"s": s_teget, "e": e, "yon": yon, "r_n": r_n,
                            "aci_bas": bu["aci"], "aci": aci,
                            "pay": aci * r_n,
                            "s_son": s_teget + e * aci * r_n}
            oi = obur["i"]
            if oi in gidilen:
                continue
            w2 = duvarlar[oi]
            orta2 = (w2["p"][0] + w2["p"][1]) / 2.0
            B2 = e * (1.0 if obur["p"] <= orta2 else -1.0)
            harita[oi] = (b_harita[bi]["s_son"] - B2 * obur["p"], B2)
            gidilen.add(oi); sira.append(oi)
    # Ağaca girmeyen duvar kalabilir: kenar pahı, küçük bir çıkıntı.
    # Küçükse sorun değil, ama gerçek bir duvar dışarıda kalıyorsa
    # açınım eksik demektir.
    disarda = [i for i in range(len(duvarlar)) if i not in harita]
    toplam = sum(w["alan"] for w in duvarlar) or 1.0
    alan = sum(duvarlar[i]["alan"] for i in disarda)
    if alan > 0.03 * toplam:
        raise AcilimYok(
            f"Duvarların {len(disarda)} tanesi büküm ağacına bağlanamadı "
            f"(sac yüzeyinin %{100 * alan / toplam:.0f}'i). Parça tek bir "
            f"sac şeridi değil; kaynaklı ya da çok yönlü bükülmüş olabilir."
            + _bagsiz_duvar_raporu(duvarlar, bukumler, disarda, t))
    if len(b_harita) > len(harita) - 1:
        raise AcilimYok(
            f"Büküm ağacında çevrim var ({len(harita)} duvar, "
            f"{len(b_harita)} büküm). Kapalı kesit - kutu profil, kıvrılıp "
            f"kendine değen sac - düzleme açılamaz.")
    return harita, b_harita


def _dikise_yapistir(tel, dikis, pay=0.002):
    """Dikişe çok yakın düşen noktaları tam dikiş değerine oturtur.

    pay 2 mikron: gerçek bir kenarı kaydırmayacak kadar küçük, kayan
    nokta gürültüsünü (nanometreler) kapatacak kadar büyük."""
    if not dikis:
        return tel
    out = []
    for x, y in tel:
        i = bisect.bisect_left(dikis, y)
        for j in (i - 1, i):
            if 0 <= j < len(dikis) and abs(dikis[j] - y) <= pay:
                y = dikis[j]
                break
        out.append((x, y))
    return out


def sac_ac(sh, t, k_faktor, en_az_alan=1.0):
    """Sacı yüzeylerinden açar. (düzlem telleri, delik telleri, büküm
    bilgisi, kullanılan duvar sayısı) döndürür."""
    duvarlar = _duzlem_duvarlar(sh, t)
    if not duvarlar:
        raise AcilimYok("Sac duvarı bulunamadı: birbirine kalınlık kadar "
                        "uzak, eksene paralel düzlem çifti yok.")
    bukumler = _agac_kur(duvarlar, _silindir_bukumler(sh, t), t)
    if not bukumler:
        raise AcilimYok("Bükümler duvarlara oturmadı; açınım ağacı kurulamadı.")
    harita, b_harita = _acma_haritasi(duvarlar, bukumler, t, k_faktor)
    parca, delik = [], []
    for wi, (A, B) in harita.items():
        w = duvarlar[wi]
        ux, uy = w["u"]

        def hw(p, A=A, B=B, ux=ux, uy=uy):
            return (p.Z(), A + B * (p.X() * ux + p.Y() * uy))

        for f in w["yuzler"]:
            dis, ic = _yuz_telleri(f)
            if len(dis) > 2:
                parca.append([hw(p) for p in dis])
            delik += [[hw(p) for p in q] for q in ic if len(q) > 2]
    for bi, bh in b_harita.items():
        b = bukumler[bi]
        mx, my = b["m"]

        def hb(p, mx=mx, my=my, bh=bh):
            f = math.atan2(p.Y() - my, p.X() - mx)
            return (p.Z(), bh["s"] + bh["e"] * bh["yon"]
                    * _aci_farki(bh["aci_bas"], f) * bh["r_n"])

        for f in b["yuzler"]:
            dis, ic = _yuz_telleri(f)
            if len(dis) > 2:
                parca.append([hb(p) for p in dis])
            delik += [[hb(p) for p in q] for q in ic if len(q) > 2]
    # Dikişleri tam oturt. Duvar düzlemdeki yerini DOĞRUSAL, büküm ise
    # AÇISAL formülle buluyor; ikisi teğet çizgisinde aynı sayıyı vermek
    # zorunda ama kayan noktada nanometrelerce ayrılıyorlar. O kadarcık
    # ayrılık bile boole işleminde parçaların kaynamamasına yetiyor.
    # Teğet çizgilerinin yeri zaten tam biliniyor: oraya yapıştır.
    dikis = sorted({round(v, 9) for b in b_harita.values()
                    for v in (b["s"], b["s_son"])})
    parca = [_dikise_yapistir(w, dikis) for w in parca]
    delik = [_dikise_yapistir(w, dikis) for w in delik]
    return parca, delik, harita, b_harita, duvarlar, bukumler


def _cokgen_alani(noktalar):
    """Çokgenin İŞARETLİ alanı. Artı: saat yönünün tersi."""
    a = 0.0
    for i in range(len(noktalar)):
        x1, y1 = noktalar[i]
        x2, y2 = noktalar[(i + 1) % len(noktalar)]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def _cokgen_yuzu(noktalar, en_az_alan=0.02):
    """Düzlemdeki nokta dizisinden kapalı yüz. Çok küçükse None.

    Çokgen HER ZAMAN saat yönünün tersine çevrilir. Yönü ters olan yüzün
    normali de ters bakar; OpenCascade ters normalli iki yüzü, uç uca
    dursalar bile birleştirmez. Açma haritası duvarları kâh düz kâh ters
    yönde taşıdığı için bu şart."""
    if len(noktalar) < 3:
        return None
    if _cokgen_alani(noktalar) < 0:
        noktalar = noktalar[::-1]
    p = BRepBuilderAPI_MakePolygon()
    onceki = None
    for x, y in noktalar:
        if onceki and abs(x - onceki[0]) < 1e-7 and abs(y - onceki[1]) < 1e-7:
            continue
        p.Add(gp_Pnt(x, y, 0.0)); onceki = (x, y)
    p.Close()
    if not p.IsDone():
        return None
    yap = BRepBuilderAPI_MakeFace(p.Wire())
    if not yap.IsDone():
        return None
    f = yap.Face()
    g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
    return f if g.Mass() > en_az_alan else None


def _birlestir(yuzler, sadelestir=True):
    """Düzlemdeki yüzleri tek parçaya kaynatır, aradaki teğet çizgilerini
    siler.

    Tek tek birleştirmek yerine HEPSİ BİR SEFERDE verilir: n parça için
    n-1 boole işlemi yerine tek işlem olur. Yüz sayısı yüzlere çıkan
    parçalarda aradaki fark dakikalarladır."""
    if not yuzler:
        return None
    if len(yuzler) == 1:
        sonuc = yuzler[0]
    else:
        op = BRepAlgoAPI_Fuse()
        a, b = TopTools_ListOfShape(), TopTools_ListOfShape()
        a.Append(yuzler[0])
        for f in yuzler[1:]:
            b.Append(f)
        op.SetArguments(a); op.SetTools(b)
        op.SetFuzzyValue(0.01)
        op.Build()
        if not op.IsDone():
            raise AcilimYok("Açınım parçaları düzlemde birleştirilemedi.")
        sonuc = op.Shape()
    if not sadelestir:
        return sonuc
    bir = ShapeUpgrade_UnifySameDomain(sonuc, True, True, True)
    bir.Build()
    return bir.Shape()


def acilim_konturu(sh, zincir, t, k_faktor):
    """Açınımın kesim konturu: (dış konturlar, delikler) nokta dizileri."""
    parca, delik = acilim_telleri(sh, zincir, t, k_faktor)
    taban = _birlestir([f for f in (_cokgen_yuzu(w) for w in parca) if f])
    if taban is None:
        raise AcilimYok("Açınım konturu birleştirilemedi.")
    delik_yuz = [f for f in (_cokgen_yuzu(w) for w in delik) if f]
    if delik_yuz:
        d = _birlestir(delik_yuz, sadelestir=False)
        op = BRepAlgoAPI_Cut(taban, d)
        op.SetFuzzyValue(0.01)
        op.Build()
        if op.IsDone():
            taban = op.Shape()
    dis, ic = [], []
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(taban, TopAbs_FACE, m)
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        d0, i0 = _yuz_telleri(f, sapma=0.02)
        dis.append([(p.X(), p.Y()) for p in d0])
        ic += [[(p.X(), p.Y()) for p in w] for w in i0]
    return dis, ic


def duz_sac_konturu(sh, en_cok_sapma=0.03):
    """Bükümü olmayan sac parçanın KESİM KONTURU.

    Bükümlü parçanın konturunu açınım hesabı verir (acilim_kesim).
    Düz bir plakanın açınımı yoktur: kesim konturu parçanın kendi
    yüzüdür. Yine de "yüzü al, bitti" denmez - parça gerçekten plaka
    mı, önce ölçülür.

    Yöntem: en büyük düzlem yüz bulunur, normali Z'ye döndürülür,
    yüzün dış ve iç halkaları düzlem çokgeni olarak alınır. Sonuç
    BAĞIMSIZ bir ölçüyle denetlenir: alan x kalınlık = hacim. Cepli,
    çıkıntılı ya da kademeli bir parçada bu tutmaz ve kontur
    verilmez - lazerde hurda çıkarmaktansa hiç vermemek gerekir.

    Döner: {"kontur_dis", "kontur_delik", "kalinlik_mm", "olcu"}
    """
    v = hacim(sh)
    if v <= 0:
        raise AcilimYok("Parçanın hacmi okunamadı.")
    # En büyük düzlem yüz: plakanın yüzü. (Silindirik ya da eğri
    # yüzeyler burada aranmaz; onlar zaten plaka değildir.)
    en_iyi = None
    ex = TopExp_Explorer(sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        ad = BRepAdaptor_Surface(f, True)
        if ad.GetType() != GeomAbs_Plane:
            continue
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
        if en_iyi is None or g.Mass() > en_iyi[0]:
            d = ad.Plane().Axis().Direction()
            en_iyi = (g.Mass(), f, (d.X(), d.Y(), d.Z()))
    if en_iyi is None:
        raise AcilimYok("Parçada düzlem yüz yok: sac plaka değil.")
    alan, yuz, normal = en_iyi

    t = v / alan
    kb = kutu(sh)
    ince = min(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2])
    if t <= 0 or t > 25.0:
        raise AcilimYok(f"Sac kalınlığı makul değil: {t:.2f} mm.")
    # Gabarinin en ince yönü ile hacimden çıkan kalınlık tutmalı.
    # Tutmuyorsa parça düz bir plaka değildir (cep, çıkıntı, kademe).
    if abs(ince - t) > max(0.05, en_cok_sapma * t):
        raise AcilimYok(
            f"Parça düz plaka değil: gabarinin en ince yönü {ince:.2f} mm, "
            f"hacim/alan {t:.2f} mm veriyor. Cebi, çıkıntısı ya da "
            f"kademesi olan bir parçanın kesim konturu tek düzlemden "
            f"çıkarılamaz; kontur verilmiyor.")

    d = _dis_halkalar(_eksene_dondur(yuz, normal))
    dis, ic = d
    if not dis:
        raise AcilimYok("Plakanın sınırı çıkarılamadı.")
    if len(dis) != 1:
        raise AcilimYok(
            f"Plaka düzlemde {len(dis)} ayrı parça çıktı; tek parça "
            "olmayan bir kontur lazerde işe yaramaz.")
    xs = [p[0] for w in dis + ic for p in w]
    ys = [p[1] for w in dis + ic for p in w]
    dx, dy = -min(xs), -min(ys)
    kay = lambda w: [(x + dx, y + dy) for x, y in w]
    return {"kontur_dis": [kay(w) for w in dis],
            "kontur_delik": [kay(w) for w in ic],
            "kalinlik_mm": round(t, 2),
            "olcu": (round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2))}


LAZER_KATMAN = "KESIM"


def dxf_lazer(kontur_dis, kontur_delik, yol, P=None):
    """Lazer/CNC kesim resmi: YALNIZ kontur, 1:1.

    Bilerek çıplaktır. Ne büküm çizgisi, ne büküm tablosu, ne ölçü, ne
    başlık, ne çerçeve - ve PAFTAYA DA ALINMAZ. Sebebi şu: bu dosya
    okunmak için değil, KESİLMEK için üretilir. CAM yazılımı dosyadaki
    her çizgiyi kesim yolu sayabilir; resmin üstündeki bir yazı ya da
    ölçü çizgisi sacın üstüne kesilir. Parçanın kimliği dosya
    ADINDADIR (..._Lzr.dxf).

    Bütün konturlar tek katmandadır (KESIM) ve kapalı çokgendir:
    dıştaki dış kontur, içtekiler delik."""
    doc = dxf_kur(); msp = doc.modelspace()
    if LAZER_KATMAN not in doc.layers:
        doc.layers.add(LAZER_KATMAN, color=7)
    doc.layers.get(LAZER_KATMAN).dxf.lineweight = CIZGI_KAL
    n = 0
    for w in list(kontur_dis) + list(kontur_delik):
        if len(w) < 3:
            continue
        msp.add_lwpolyline(w, close=True, dxfattribs={"layer": LAZER_KATMAN})
        n += 1
    if not n:
        raise AcilimYok("Kesilecek kontur yok.")
    os.makedirs(os.path.dirname(os.path.abspath(yol)) or ".", exist_ok=True)
    doc.saveas(yol)
    return yol


def dxf_acilim(r, k, yol, P=None):
    """Açınım resmi: kesim konturu, delikler ve büküm çizgileri.

    Kontur çıkarılabildiyse resim KESİME HAZIRDIR: dış kontur ve bütün
    delikler gerçek yerlerindedir, lazer/pres için doğrudan kullanılır.
    Çıkarılamadıysa yalnız blank dikdörtgeni çizilir ve sebebi resmin
    üstüne yazılır."""
    gen, boy, t = r["acinim_genislik_mm"], r["acinim_boy_mm"], r["kalinlik_mm"]
    kesim = bool(r.get("kontur_dis"))
    doc = dxf_kur(); msp = doc.modelspace()
    # Yazı boyu KISA kenara göre: uzun bir profilde boya göre seçilirse
    # yazılar açınım genişliğinden büyük çıkar, etiketler üst üste biner.
    h = min(12.0, max(2.0, min(gen, boy) / 30.0))
    olcu_stili(doc, h)
    if kesim:
        for w in r["kontur_dis"]:
            msp.add_lwpolyline(w, close=True, dxfattribs={"layer": "GORUNEN"})
        for w in r["kontur_delik"]:
            msp.add_lwpolyline(w, close=True, dxfattribs={"layer": "GORUNEN"})
    else:
        msp.add_lwpolyline([(0, 0), (boy, 0), (boy, gen), (0, gen), (0, 0)],
                           dxfattribs={"layer": "GORUNEN"})
    # Büküm çizgileri ve etiketleri. Bükümler birbirine yakınsa (bu
    # profilde 5 mm) etiketler üst üste biner; o yüzden her etiket
    # bir öncekinin altına sığmıyorsa SAĞA KAYDIRILIR. Aynı hizada
    # kalır, okunur ve çakışmaz.
    yazi_h = 0.9 * h
    kul = []                                   # ölçülmüş dolu kutular
    etiket_sag = boy
    for i, b in enumerate(r["bukumler"], 1):
        for y in (b["acinimda_bas_mm"], b["acinimda_son_mm"]):
            msp.add_line((0, y), (boy, y), dxfattribs={"layer": "EKSEN"})
        orta = (b["acinimda_bas_mm"] + b["acinimda_son_mm"]) / 2.0
        ey = orta - 0.45 * yazi_h
        ex = boy + 0.6 * h
        # Yazının yeri TAHMİN EDİLMEZ, ÖLÇÜLÜR: yaz, sınırını ölç,
        # çakışıyorsa sil ve sağa kaydırıp yeniden yaz. Bükümler 5 mm
        # arayken etiketler üst üste biniyordu.
        for _ in range(14):
            e = _yaz(msp, f"B{i}", ex, ey, yazi_h)
            kt = _yazi_siniri(e)        # k parametredir, gölgelenmemeli
            if kt is None or not _cakisiyor(kt, kul, 0.15 * yazi_h):
                kul.append(kt or (ex, ey, ex + yazi_h, ey + yazi_h))
                etiket_sag = max(etiket_sag, kt[2] if kt else ex + yazi_h)
                break
            msp.delete_entity(e)
            ex = kt[2] + 0.5 * yazi_h
    d = 4.0 * h
    msp.add_linear_dim(base=(0, -d), p1=(0, 0), p2=(boy, 0),
                       dimstyle=OLCU_STILI, dxfattribs={"layer": "OLCU"}).render()
    msp.add_linear_dim(base=(-d, 0), p1=(0, 0), p2=(0, gen), angle=90,
                       dimstyle=OLCU_STILI, dxfattribs={"layer": "OLCU"}).render()
    # Büküm çizelgesi. Konumlar burada yazılı olduğu için ölçü çizgisi
    # yalnız az bükümlü parçalara konur; çok bükümlüde üst üste binerdi.
    # Tablo, büküm etiketlerinin bittiği yerden sonra başlar. Etiketler
    # bükümler sıkışıksa sağa kayıyor; sabit bir yerden başlatılırsa
    # tablonun üstüne biniyorlardı.
    # Büküm yoksa çizelge de olmaz; ama BAŞLIK yine yazılır, o yüzden
    # burada çıkılmaz, yalnız çizelge atlanır.
    x = max(boy + 4.0 * h, etiket_sag + 2.0 * h)
    y = gen
    if r["bukumler"]:
        _yaz(msp, "BUKUM  ACI      IC R   PAY      ALT KENARDAN", x, y, h)
    y -= 2.0 * h
    for i, b in enumerate(r["bukumler"], 1):
        _yaz(msp, f"B{i:<5d} {b['aci_derece']:>6.1f}  {b['r_ic']:>6.2f} "
                  f"{b['pay_mm']:>6.2f}  {b['acinimda_bas_mm']:>8.2f} - "
                  f"{b['acinimda_son_mm']:.2f}", x, y, h)
        y -= 1.8 * h
    if len(r["bukumler"]) <= 4:
        # Sol tarafa, genel genişlik ölçüsünün dışına diz: sağda büküm
        # etiketleri ve çizelge var.
        for i, b in enumerate(r["bukumler"], 1):
            msp.add_linear_dim(base=(-d - i * 3.5 * h, 0), p1=(boy, 0),
                               p2=(boy, b["acinimda_bas_mm"]), angle=90,
                               dimstyle=OLCU_STILI,
                               dxfattribs={"layer": "OLCU"}).render()
    poz = f"POZ {k['poz']}   " if k.get("poz") else ""
    sat = [(f"{poz}{k.get('kod','')}   {(k.get('ad') or '')[:60]}   AÇINIM", 1.5 * h),
           (f"adet: {k.get('adet','-')}", 1.1 * h),
           (f"ACINIM : {gen} x {boy} mm   sac kalinlik {t} mm", 1.1 * h),
           ((f"{r['bukum_sayisi']} bukum   K-faktoru {r['k_faktor']}"
             + (f"   {r.get('delik_adedi', 0)} delik" if kesim else ""))
            if r.get("k_faktor") is not None
            else "bukum yerleri verilmedi", 1.1 * h),
           ("olcek 1:1   birim: mm", 1.1 * h)]
    yn = r.get("yontem") or {}
    if yn.get("yontem"):
        sat.append((f"BUKUM YONTEMI: {yn['yontem'].upper()}"
                    + (f"  ({yn['kesinlik']})" if yn.get("kesinlik") else ""),
                    1.2 * h))
        for p in textwrap.wrap(yn.get("neden", ""), 108):
            sat.append((p, 1.0 * h))
        for p in textwrap.wrap("DIKKAT: " + yn["uyari"], 108) if yn.get("uyari") else []:
            sat.append((p, 1.0 * h))
    if kesim:
        sat.append(("KESIM KONTURUDUR: dis kontur ve delikler gercek "
                    "yerlerinde.", 1.1 * h))
    else:
        sat.append(("SERIT GENISLIGIDIR: bukum yerleri ve kesim konturu yok."
                    if r.get("serit_genisligi") else
                    "BLANK OLCUSUDUR: dis kontur kesikleri ve delikler "
                    "bu resimde YOKTUR.", 1.1 * h))
        if r.get("kontur_notu"):
            # Sebebi KESME, SARDIR. Eskiden 110 karakterde kesiliyordu ve
            # tam da işe yarayan yerde - "Parça alanları: 2461" diye -
            # bitiyordu; okuyan neyin yanlış olduğunu anlayamıyordu.
            for p in textwrap.wrap(r["kontur_notu"], 108):
                sat.append((p, 1.0 * h))
    y = gen + 4.0 * h + len(sat) * 2.2 * h
    for metin, yaz_h in sat:
        _yaz(msp, metin, 0.0, y, yaz_h)
        y -= 2.2 * h
    doc.saveas(yol)
    return yol


def poz_numaralari(komp, poz_harita=None):
    """Komponent sırasına göre poz numaraları. calistir'daki ile aynı
    kural: kaynak dikişi poz almaz, standart eleman alır."""
    poz, out = 0, {}
    for i, k in enumerate(komp):
        if k.get("sinif") == "kaynak":
            out[i] = ""
            continue
        poz += 1
        out[i] = (poz_harita or {}).get(k.get("kod"), poz)
    return out


def resim_dosyasi(poz, kod, ad=None, acinim=False, lazer=False):
    """Bir parçanın resim dosyası adı.

    Poz + çizim no + parça adı: P05_01_050_000_01_U-Blech.dxf
    Dosyadan parçayı tanımak için ikisi birlikte gerekir - çizim no
    hangi resim olduğunu, parça adı ne olduğunu söyler. Parça adı
    yoksa ya da çizim no'nun aynısıysa tekrar yazılmaz.

    Detay resmi ile açınımı AYNI ADI taşır, açınımın sonuna "_acinim"
    eklenir. Eskiden açınım "A5_..." diye ayrı bir harfle başlıyordu;
    aynı parçanın iki resmi klasörde yan yana durmuyor, poz numarası
    da sıfırsız yazıldığı için sıralama bozuluyordu."""
    def sade(v, n=34):
        return re.sub(r"[^\w\-]+", "_", str(v or "")).strip("_")[:n]

    # Çizim no yoksa parça adı onun yerine geçer; "?" gibi bir şey
    # yazılmaz - Windows dosya adında "?" kullanılamaz.
    k = sade(kod) or sade(ad) or "isimsiz"
    a = sade(ad, 60)
    # CAD'lerde parça adı çoğu zaman kodla BAŞLAR
    # ("01.051.000.01 C-Profil-Runge XL-H"). Olduğu gibi eklersek dosya
    # adında kod iki kez çıkar:
    #   P01_01_051_000_01_01_051_000_01_C-Profil-Runge.dxf
    # Baştaki tekrar atılır, kalan ad eklenir.
    if a.lower().startswith(k.lower()):
        a = a[len(k):].strip("_")
    a = a[:28].strip("_")
    try:
        p = f"P{int(poz):02d}"
    except (TypeError, ValueError):
        p = "P00"
    return (f"{p}_{k}" + (f"_{a}" if a else "")
            + ("_acinim" if acinim else "") + ("_Lzr" if lazer else "")
            + ".dxf")


def sac_parcalari(kayit, komp, log=print):
    """Montajdaki BÜKÜMLÜ SAC parçaları bulur; kod kümesi döndürür.

    Kullanıcının listeden parça seçmesine gerek kalmasın diye. Açınım
    hesabı yapmaz, yalnız sac_taramasi'nı çağırır: parça başına ~20 ms,
    açınım hesabıysa 15-30 saniye. Örnek montajda 16 parçanın 7'si
    bükümlü çıktı, açınımı gerçekten olan 5 parçanın hepsi bu 7'nin
    içindeydi (hiçbiri kaçmadı); kalan 2'si "büküm eksenleri paralel
    değil" diye zaten önceden işaretli ve denemesi saniyenin altında
    sürüyor."""
    kod, duz, degil = set(), 0, 0
    for k in komp:
        if k.get("sinif") != "parca":
            continue            # standart eleman ve kaynak dikişi sac değil
        try:
            r = sac_taramasi(kayit[k["indeks"][0]][1])
        except Exception:
            degil += 1
            continue
        if r["tip"] == "bukumlu sac":
            kod.add(k.get("kod") or k.get("ad"))
        elif r["tip"] == "duz sac":
            duz += 1
        else:
            degil += 1
    log(f"sac taraması: {len(kod)} bükümlü sac parça bulundu "
        f"({duz} düz sac, {degil} sac değil)")
    return kod


def acilim_yaz(kayit, komp, P, klasor, kodlar=None, k_faktor=K_FAKTOR,
               log=print, ilerleme=None, iptal=None):
    """Seçilen parçaların açınımını hesaplar, DXF ve tablo yazar.

    kodlar None ise bütün komponentler denenir. Geriye (sonuclar, hatalar)
    döner; hata listesi kullanıcıya OLDUĞU GİBİ gösterilmelidir, çünkü
    hangi parçanın neden açılamadığını tek tek söyler."""
    os.makedirs(klasor, exist_ok=True)
    sonuc, hata = [], []
    pozlar = poz_numaralari(komp)
    secili = [(pozlar[i], k) for i, k in enumerate(komp)
              if kodlar is None or (k.get("kod") or k.get("ad")) in kodlar]
    for i, (poz, k) in enumerate(secili):
        if iptal and iptal():
            break
        ad = k.get("kod") or k.get("ad") or "?"
        if ilerleme:
            ilerleme(i, len(secili), ad)
        try:
            sh = kayit[k["indeks"][0]][1]
            r = sac_acilim(sh, k, k_faktor=k_faktor)
        except AcilimYok as e:
            hata.append((ad, str(e)))
            log(f"  {ad}: açınım yok - {str(e).splitlines()[0]}")
            continue
        except Exception as e:
            hata.append((ad, f"beklenmeyen hata: {type(e).__name__}: {e}"))
            log(f"  {ad}: hata - {type(e).__name__}: {e}")
            continue
        dosya = os.path.join(klasor,
                             resim_dosyasi(poz or (i + 1), ad,
                                           k.get("ad"), acinim=True))
        dxf_acilim(r, dict(k, poz=poz), dosya, P)
        r["kod"] = ad
        r["ad"] = k.get("ad", "")
        r["poz"] = poz
        r["adet"] = k.get("adet", 1)
        r["dxf"] = os.path.basename(dosya)
        sonuc.append(r)
        log(f"  {os.path.basename(dosya)}  {r['acinim_genislik_mm']} x "
            f"{r['acinim_boy_mm']} mm, t={r['kalinlik_mm']}, "
            f"{r['bukum_sayisi']} bükum")
    if sonuc:
        yol = os.path.join(klasor, "ACINIM.csv")
        with open(yol, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["poz", "kod", "ad", "adet", "kalinlik_mm",
                        "acinim_genislik_mm", "acinim_boy_mm", "bukum_sayisi",
                        "yontem", "en_kisa_kanat_mm", "en_kisa_kanat_t",
                        "en_kucuk_r_t", "yontem_nedeni", "uyari",
                        "k_faktor", "bukumler", "dxf"])
            for r in sonuc:
                w.writerow([r["poz"], r["kod"], r["ad"], r["adet"],
                            r["kalinlik_mm"], r["acinim_genislik_mm"],
                            r["acinim_boy_mm"], r["bukum_sayisi"],
                            (r.get("yontem") or {}).get("yontem", ""),
                            (r.get("yontem") or {}).get("en_kisa_kanat_mm", ""),
                            (r.get("yontem") or {}).get("en_kisa_kanat_t", ""),
                            (r.get("yontem") or {}).get("en_kucuk_r_t", ""),
                            (r.get("yontem") or {}).get("neden", ""),
                            (r.get("yontem") or {}).get("uyari", ""),
                            r["k_faktor"],
                            " | ".join(f"{b['aci_derece']:g}d R{b['r_ic']:g} "
                                       f"pay{b['pay_mm']:g} @"
                                       f"{b['acinimda_bas_mm']:g}"
                                       for b in r["bukumler"]),
                            r["dxf"]])
        log(f"  ACINIM.csv  ({len(sonuc)} parça)")
    if hata:
        yol = os.path.join(klasor, "ACINIM_yapilamayanlar.txt")
        with open(yol, "w", encoding="utf-8") as f:
            for ad, m in hata:
                f.write(f"{ad}\n    " + m.replace("\n", "\n    ") + "\n\n")
        log(f"  ACINIM_yapilamayanlar.txt  ({len(hata)} parça)")
    return sonuc, hata


def lazer_yaz(kayit, komp, klasor, kodlar=None, k_faktor=K_FAKTOR,
              acilim=None, log=print, ilerleme=None, iptal=None):
    """Seçilen sac parçalar için LAZER KESİM resimleri (..._Lzr.dxf).

    Kontur nereden gelir:
      bükümlü sac -> açınımın kesim konturu (varsa hazırı kullanılır,
                     yoksa açınım burada hesaplanır)
      düz sac     -> parçanın kendi yüzü (duz_sac_konturu)

    `acilim`: daha önce hesaplanmış açınım sonuçları. Verilirse aynı
    parça ikinci kez açılmaz - açınım parça başına 15-30 saniye sürer.

    Geriye (sonuclar, hatalar) döner."""
    os.makedirs(klasor, exist_ok=True)
    sonuc, hata = [], []
    pozlar = poz_numaralari(komp)
    haz = {a.get("kod"): a for a in (acilim or []) if a.get("kontur_dis")}
    secili = [(pozlar[i], k) for i, k in enumerate(komp)
              if k.get("sinif") == "parca"
              and (kodlar is None or (k.get("kod") or k.get("ad")) in kodlar)]
    for i, (poz, k) in enumerate(secili):
        if iptal and iptal():
            log("! iptal edildi")
            break
        ad = k.get("kod") or k.get("ad") or "?"
        if ilerleme:
            ilerleme(i, len(secili), ad)
        try:
            sh = kayit[k["indeks"][0]][1]
            r = haz.get(ad)
            if r:
                dis, ic = r["kontur_dis"], r["kontur_delik"]
                t, nere = r["kalinlik_mm"], "açınım"
            elif sac_taramasi(sh)["tip"] == "bukumlu sac":
                a = sac_acilim(sh, k, k_faktor=k_faktor)
                if not a.get("kontur_dis"):
                    raise AcilimYok(
                        "Açınım çıktı ama kesim konturu çıkarılamadı; "
                        "lazer resmi verilemez.")
                dis, ic = a["kontur_dis"], a["kontur_delik"]
                t, nere = a["kalinlik_mm"], "açınım"
            else:
                c = duz_sac_konturu(sh)
                dis, ic = c["kontur_dis"], c["kontur_delik"]
                t, nere = c["kalinlik_mm"], "düz sac"
        except AcilimYok as e:
            hata.append((ad, str(e)))
            log(f"  {ad}: lazer resmi yok - {str(e).splitlines()[0]}")
            continue
        except Exception as e:
            hata.append((ad, f"beklenmeyen hata: {type(e).__name__}: {e}"))
            log(f"  {ad}: hata - {type(e).__name__}: {e}")
            continue
        dosya = resim_dosyasi(poz or (i + 1), ad, k.get("ad"), lazer=True)
        dxf_lazer(dis, ic, os.path.join(klasor, dosya))
        xs = [q[0] for w in dis for q in w]
        ys = [q[1] for w in dis for q in w]
        kayd = {"poz": poz, "kod": ad, "ad": k.get("ad", ""),
                "adet": k.get("adet", 1), "kalinlik_mm": t,
                "boy_mm": round(max(ys) - min(ys), 2),
                "en_mm": round(max(xs) - min(xs), 2),
                "delik_adedi": len(ic), "kaynak": nere, "dxf": dosya}
        sonuc.append(kayd)
        log(f"  {dosya}  {kayd['en_mm']} x {kayd['boy_mm']} mm, "
            f"t={t}, {len(ic)} delik  ({nere})")
    if sonuc:
        yol = os.path.join(klasor, "LAZER.csv")
        with open(yol, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["poz", "kod", "ad", "adet", "kalinlik_mm", "en_mm",
                        "boy_mm", "delik_adedi", "kaynak", "dxf"])
            for r in sonuc:
                w.writerow([r[c] for c in ("poz", "kod", "ad", "adet",
                                           "kalinlik_mm", "en_mm", "boy_mm",
                                           "delik_adedi", "kaynak", "dxf")])
        log(f"  LAZER.csv  ({len(sonuc)} parça)")
    if hata:
        yol = os.path.join(klasor, "LAZER_yapilamayanlar.txt")
        with open(yol, "w", encoding="utf-8") as f:
            for ad, m in hata:
                f.write(f"{ad}\n    " + m.replace("\n", "\n    ") + "\n\n")
        log(f"  LAZER_yapilamayanlar.txt  ({len(hata)} parça)")
    return sonuc, hata


# ---------------------------------------------------------------- kesit
def kesit_kati(sh, eksen, konum, kb):
    """Parçayı `eksen` yönünde `konum` düzleminden kesip yakın yarıyı atar.
    Geriye kalan katı, aynı yönden bakıldığında tam kesit görünüşü verir."""
    pay = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]) * 0.1 + 10.0
    al = [kb[0] - pay, kb[1] - pay, kb[2] - pay]
    ust = [kb[3] + pay, kb[4] + pay, kb[5] + pay]
    ust[eksen] = konum
    kutu_sh = BRepPrimAPI_MakeBox(gp_Pnt(*al), gp_Pnt(*ust)).Shape()
    # Build() şart: yapıcı tek başına bazı katılarda boş sonuç veriyor.
    op = BRepAlgoAPI_Cut(sh, kutu_sh)
    op.Build()
    if not op.IsDone():
        raise ValueError("kesit boole işlemi başarısız")
    return op.Shape()


def _tel_noktalari(w):
    """Bir teli (wire) noktalara böler."""
    p = []
    ex = TopExp_Explorer(w, TopAbs_EDGE)
    while ex.More():
        c = BRepAdaptor_Curve(TopoDS.Edge_s(ex.Current()))
        d = GCPnts_TangentialDeflection(c, 0.05, 0.1)
        q = [c.Value(d.Parameter(i)) for i in range(1, d.NbPoints() + 1)]
        if p and q and (p[-1].Distance(q[-1]) < p[-1].Distance(q[0])):
            q.reverse()
        p += q
        ex.Next()
    return p


def kesit_tara(msp, kesik, eksen, konum, gad, dx, dy, tol=1e-4):
    """Kesme düzleminde kalan yüzeyleri tarar (hatch). Kesilen malzeme
    böylece resimde taralı görünür, geri planda kalan kenarlardan ayrılır."""
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(kesik, TopAbs_FACE, m)
    n = 0
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Plane:
            continue
        d = ad.Plane().Axis().Direction()
        if abs((d.X(), d.Y(), d.Z())[eksen]) < 0.999:
            continue
        if abs(ad.Plane().Location().Coord(eksen + 1) - konum) > 1e-3:
            continue
        dis = BRepTools.OuterWire_s(f)
        yollar = []
        ex = TopExp_Explorer(f, TopAbs_WIRE)
        while ex.More():
            w = TopoDS.Wire_s(ex.Current())
            p = _tel_noktalari(w)
            if len(p) > 2:
                yollar.append((w.IsSame(dis),
                               [(izdusum((q.X(), q.Y(), q.Z()), gad)[0] + dx,
                                 izdusum((q.X(), q.Y(), q.Z()), gad)[1] + dy) for q in p]))
            ex.Next()
        if not yollar:
            continue
        try:
            ht = msp.add_hatch(color=5, dxfattribs={"layer": "TARAMA"})
            ht.set_pattern_fill("ANSI31", scale=1.0)
            for dismi, pts in yollar:
                ht.paths.add_polyline_path(pts, is_closed=True,
                                           flags=1 if dismi else 0)
            n += 1
        except Exception:
            continue
    return n


def kesit_konumu(o, kb, eksen, kenar_payi=0.15):
    """Kesme düzlemini anlamlı bir yere koyar: kesildiğinde en çok deliği
    açan konum. Delik yoksa parçanın ortasından geçer.

    Düzlem parçanın kenarına çok yakın olursa kesit anlamsızlaşır (parçanın
    neredeyse tamamı atılır ya da hiç kesilmez), bu yüzden aday konumlar
    ortadaki %70'lik bantla sınırlanır."""
    a0, a1 = kb[eksen], kb[eksen + 3]
    orta = (a0 + a1) / 2.0
    alt, ust = a0 + (a1 - a0) * kenar_payi, a1 - (a1 - a0) * kenar_payi
    eks_ad = "XYZ"[eksen]
    sayim = Counter()
    for d in (o or {}).get("delikler") or []:
        if d["eksen"] == eks_ad:          # düzleme dik delik kesilmez, görünür
            continue
        for c in d.get("merkezler") or []:
            v = round(c[eksen], 2)
            if alt <= v <= ust:
                sayim[v] += 1
    if not sayim:
        return orta
    en = max(sayim.values())
    # Eşitlikte ortaya en yakın olanı seç.
    return min((k for k, v in sayim.items() if v == en), key=lambda k: abs(k - orta))


def kesit_isareti(msp, o, yer, kaydir, eksen, konum, h, L, W, T):
    """Kesme düzlemini, düzlemin çizgi olarak göründüğü bir görünüşte
    A—A kesme çizgisi olarak işaretler."""
    for gad in ("UST", "ALT", "SAG", "SOL", "ON", "ARKA"):
        if gad not in yer:
            continue
        i1, i2, _tx, _ty = GOR_EKSEN[gad]
        if eksen not in (i1, i2):
            continue
        dx, dy = kaydir[gad]
        gw, gy = gorunus_olcusu(gad, L, W, T)
        ox, oy = yer[gad]
        p = [0.0, 0.0, 0.0]; p[eksen] = konum
        u, v = izdusum(p, gad)
        if eksen == i2:                      # düzlem yatay çizgi gibi görünür
            y = v + dy
            a, b = (ox - 2 * h, y), (ox + gw + 2 * h, y)
        else:                                # düşey çizgi
            x = u + dx
            a, b = (x, oy - 2 * h), (x, oy + gy + 2 * h)
        msp.add_line(a, b, dxfattribs={"layer": "EKSEN"})
        for q in (a, b):
            _yaz(msp, "A", q[0] - 0.3 * h, q[1] + 0.4 * h, 1.2 * h)
        return gad
    return None


def kesit_ciz(msp, sh, kb, yer, h, gizli, gad="ON", eksen=1, o=None):
    """Kesit görünüşünü çizer. Kesme düzlemi en çok deliği açan yerden geçer;
    kesilen yüzeyler taranır. (genişlik, yükseklik, üst sınır) döndürür."""
    konum = kesit_konumu(o, kb, eksen)
    kesik = kesit_kati(sh, eksen, konum, kb)
    # Kesit, parçanın makul bir kısmını bırakmalı: bırakmıyorsa düzlemi
    # ortaya alıp bir daha dene, yine olmazsa kesit çizilmez.
    tam = hacim(sh)
    if hacim(kesik) < 0.15 * tam:
        konum = (kb[eksen] + kb[eksen + 3]) / 2.0
        kesik = kesit_kati(sh, eksen, konum, kb)
        if hacim(kesik) < 0.05 * tam:
            raise ValueError("kesme düzlemi parçadan anlamlı bir kesit bırakmıyor")
    goz, xref = GORUNUS[gad]
    kenar = hlr(kesik, goz, xref, gizli=gizli)
    ox, oy = yer
    G, Y, dx, dy = gorunus_ciz(msp, kenar, ox, oy, gad, h=h, olcu2=True,
                               etiket=KESIT_AD)
    kesit_tara(msp, kesik, eksen, konum, gad, dx, dy)
    return G, Y, oy + Y + 2.2 * h, konum


def _tablo(msp, satirlar, x, y_ust, h, sat_h):
    """Sol üst köşesi (x, y_ust) olan yazı tablosu. Genişliğini döndürür."""
    for i, (t, th) in enumerate(satirlar):
        _yaz(msp, t, x, y_ust - i * sat_h, th)
    # tek aralıklı yazıda karakter eni ~0,72*yükseklik; sağına pay bırak
    return max((len(t) + 2) * 0.72 * th for t, th in satirlar)


def dxf_komponent(s, o, k, yol, P):
    """Bir komponentin detay resmi: seçili görünüşler + ölçüler + tablolar."""
    doc = dxf_kur(); msp = doc.modelspace()
    kb = kutu(s)
    L, W, T = kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]
    # Yazı boyu parçaya göre: küçük parçada küçük, büyükte büyük ama okunur.
    h = min(25.0, max(2.5, max(L, W, T) / 45.0))
    olcu_stili(doc, h)
    gorunusler = gorunus_sec(P.get("gorunusler"))
    # Görünüşler arası boşluk: araya giren ölçü çizgisi + yazı + kılavuz kadar.
    g = max(L, W, T) * 0.10 + 14 * h
    yer = gorunus_yerlesimi(L, W, T, g, gorunusler)
    # Konum ölçüleri ÖNCE planlanır: gabari ölçüsünün ne kadar dışarı
    # iteleneceği kaç seviye konum ölçüsü gireceğine bağlı.
    # Görünüşler BİR KEZ hesaplanır; plan da bu izdüşümlere dayanır.
    kenarlar = {gad: hlr(s, *GORUNUS[gad], gizli=P.get("gizli", True))
                for gad in gorunusler}
    ham = {gad: _kenar_kutusu(k) for gad, k in kenarlar.items()}
    kplan = (konum_plani(o, gorunusler, ham, h, kenarlar)
             if P.get("konum", True) else {})
    ust, kaydir, gkutu = {}, {}, {}
    for gad in gorunusler:
        ox, oy = yer[gad]
        # Gabari burada ÇİZİLMEZ: konum ölçüleri yerleştikten sonra,
        # onların ÖLÇÜLEN sınırının dışına konur (bkz. gabari_olculeri).
        G, Y, dx, dy = gorunus_ciz(msp, kenarlar[gad], ox, oy, gad, h=h,
                                   olcu2=False)
        ust[gad] = oy + Y + 2.2 * h          # görünüş etiketinin de üstü
        kaydir[gad] = (dx, dy)
        gkutu[gad] = (ox, oy, ox + G, oy + Y)
    merkez_cizgileri(msp, o, yer, kaydir)
    sinir = konum_olculeri(msp, kplan, kaydir, gkutu, h) if kplan else {}
    if kplan:
        simetri_isareti(msp, kplan, gkutu, h)
        # Ölçülerin hangi yüzeylerden gittiğini resimde göster.
        datum_isaretleri(msp, datum_cercevesi(L, W, T), gorunusler, gkutu, h)
    if kplan:
        girinti_olculeri(msp, kplan, kaydir, gkutu, h)
    if P.get("capraz", True):
        pah_notlari(msp, kenarlar, kaydir, gkutu, h)
    gabari_olculeri(msp, gkutu, sinir, h)
    ust, sag = cap_olculeri(msp, o, yer, kaydir, gkutu, h, ust)
    if P.get("kesit"):
        try:
            ky0 = kesit_yeri(yer, L, W, T, g, gorunusler)
            kg, _ky, kust, konum = kesit_ciz(msp, s, kb, ky0, h,
                                             P.get("gizli", True), o=o)
            ust[KESIT_AD] = kust
            sag = max(sag, ky0[0] + kg)
            kesit_isareti(msp, o, yer, kaydir, 1, konum, h, L, W, T)
        except Exception as ex:
            print(f"    kesit çizilemedi: {ex}"[:100])
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
        (f"kutle {o['kutle_kg']} kg   malzeme: {k.get('malzeme_ad', '-')}", 1.1 * h),
        # Ölçek ve birim resmin üstünde yazsın: DXF başka bir çizime
        # eklendiğinde ölçek kaymışsa bu satırdan anlaşılır.
        ("olcek 1:1   birim: mm", 1.1 * h),
    ]
    tepe = y0 + len(satir) * sat_h
    onceki = {e.dxf.handle for e in msp}
    _tablo(msp, satir, sol, tepe, h, sat_h)
    # Görünüşlerin ve başlığın yerini işaretle: pafta bunlara bakıp her
    # görünüşü ayrı pencereye alır ve kâğıda eşit dağıtır.
    #
    # Başlığın yeri TAHMİN EDİLMEZ, ÖLÇÜLÜR: yazının kapladığı yer yazı
    # tipine bağlıdır, harf sayısından hesaplanan genişlik tutmaz.
    # Ölçüm, görünüş işaretleri konmadan ÖNCE yapılır - yoksa kendi
    # işaretlerimizi de ölçer ve başlık bütün resmi kaplar.
    _baslik_isareti(msp, onceki, (sol, y0, sol + 40.0 * h, tepe))
    for gad, kt in gkutu.items():
        gorunus_isareti(msp, gad, kt)
    if KESIT_AD in ust:
        gorunus_isareti(msp, KESIT_AD,
                        (ky0[0], ky0[1], ky0[0] + kg, ust[KESIT_AD]))
    # Çizimde tablo yok: delikler görünüşlerde "2x Ø9", kenar yuvarlamaları
    # "4x R3" olarak ölçülendirilir. Tam delik ve radüs listeleri rapor.md,
    # olculer.csv ve olculer.json dosyalarındadır.
    doc.saveas(yol)


def _baslik_isareti(msp, onceki, kaba, ad="BASLIK"):
    """Yazı bloğunun gerçek sınırını ölçüp işaretler."""
    yeni = [e for e in msp if e.dxf.handle not in onceki
            and e.dxf.layer != GORUNUS_KATMAN]
    kutu_ = kaba
    try:
        k = ezdxf.bbox.extents(yeni, fast=False)
        if k.has_data:
            kutu_ = (k.extmin.x, k.extmin.y, k.extmax.x, k.extmax.y)
    except Exception:
        pass
    return gorunus_isareti(msp, ad, kutu_)


def dxf_montaj(katilar, yol, ad, P, bom=None):
    """Montaj resmi: seçili gabari görünüşleri + BOM tablosu."""
    b = Bnd_Box()
    for sh in katilar:
        BRepBndLib.Add_s(sh, b)
    x0, y0, z0, x1, y1, z1 = b.Get()
    s = donustur(bilesik(katilar), [[1, 0, 0], [0, 1, 0], [0, 0, 1]], (-x0, -y0, -z0))
    L, W, H = x1 - x0, y1 - y0, z1 - z0
    doc = dxf_kur(); msp = doc.modelspace()
    h = min(40.0, max(3.0, max(L, W, H) / 45.0))
    olcu_stili(doc, h)
    gorunusler = gorunus_sec(P.get("gorunusler"))
    g = max(L, W, H) * 0.08 + 10 * h
    yer = gorunus_yerlesimi(L, W, H, g, gorunusler)
    ust, gkutu = {}, {}
    for gad in gorunusler:
        goz, xref = GORUNUS[gad]
        kenar = hlr(s, goz, xref, gizli=False)       # montajda gizli çizgi kapalı
        ox, oy = yer[gad]
        G, Y, _dx, _dy = gorunus_ciz(msp, kenar, ox, oy, gad, h=h, olcu2=True)
        ust[gad] = oy + Y + 2.2 * h
        gkutu[gad] = (ox, oy, ox + G, oy + Y)
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
    onceki = {e.dxf.handle for e in msp}
    _tablo(msp, satir, sol, tepe, h, sat_h)
    _baslik_isareti(msp, onceki, (sol, tepe - len(satir) * sat_h,
                                  sol + 40.0 * h, tepe))
    if bom:
        onceki = {e.dxf.handle for e in msp}
        _tablo(msp, bom_satirlari(bom, h), sag + 6.0 * h, tepe, h, sat_h)
        # BOM tablosu da bir "görünüş"tür: paftada kendi penceresine
        # alınıp yerleştirilsin, yoksa görünüşlerle birlikte tek blok
        # gibi taşınır ve kâğıdın yarısı boş kalır.
        _baslik_isareti(msp, onceki, (sag + 6.0 * h, 0.0,
                                      sag + 46.0 * h, tepe), "BOM")
    for gad, kt in gkutu.items():
        gorunus_isareti(msp, gad, kt)
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
    grup, mal = defaultdict(list), {}
    for i, r in enumerate(kayit):
        ad, sh = r[0], r[1]
        v = hacim(sh)
        k = kutu(sh)
        olc = tuple(sorted(round(t, 1) for t in (k[3] - k[0], k[4] - k[1], k[5] - k[2])))
        an = (_ad_sade(ad), round(v, 1), olc)
        grup[an].append(i)
        if len(r) > 2 and r[2] and an not in mal:
            mal[an] = r[2]              # STEP'te tanımlı malzeme
    out = []
    for an, idx in sorted(grup.items(), key=lambda t: -t[0][1] * len(t[1])):
        ad, v, _olc = an
        sinif, tip = sinifla(ad)
        out.append({"ad": ad, "kod": kod_cikar(ad), "adet": len(idx), "indeks": idx,
                    "hacim_mm3": v, "sinif": sinif, "tip": tip,
                    "malzeme_data": mal.get(an)})
    return out


# ---------------------------------------------------------------- malzeme seçimi
# CAD'lerin parça listesi dışa aktarımlarında sütun başlıkları.
KOD_BASLIK = ("kod", "code", "part number", "partnumber", "part no", "partno",
              "reference", "référence", "malzeme no", "stok kodu", "item",
              "no", "number", "parca", "parça", "part")
MAL_BASLIK = ("malzeme", "material", "matiere", "matière", "werkstoff",
              "material name", "malzeme adi", "malzeme adı")
YOG_BASLIK = ("yogunluk", "yoğunluk", "density", "densite", "densité", "dichte")


def _ayirici(satir):
    for a in ("\t", ";", ","):
        if a in satir:
            return a
    return ";"


def _sutun(basliklar, adaylar):
    """Başlık satırında aranan sütunun indeksi; yoksa None."""
    b = [_tr_sade(x) for x in basliklar]
    for i, x in enumerate(b):                    # tam eşleşme önce
        if x in adaylar:
            return i
    for i, x in enumerate(b):                    # sonra içinde geçen
        if any(a in x for a in adaylar):
            return i
    return None


def malzeme_dosya_oku(yol):
    """kod -> malzeme eşlemesi okur.

    İki biçimi de anlar:
      * bizim şablonumuz            kod;malzeme;ad
      * CAD'in parça listesi çıktısı (CATIA "Analyze > Bill of Material",
        SolidWorks BOM, Excel'den CSV): başlık satırındaki "Part Number" ve
        "Material" sütunları adlarından bulunur, sekme/noktalı virgül/virgül
        ayırıcı kendiliğinden anlaşılır.

    Malzeme adı İngilizce ya da Fransızca olabilir ("Steel", "Aluminium",
    "Stainless Steel"); desenlerden tanınır. Tanınmayanlar ayrıca döndürülür
    ki kullanıcıya hangi malzemeleri eşleyemediğimiz söylenebilsin."""
    if yol.lower().endswith(".json"):
        ham = {_tr_sade(k): str(v) for k, v in
               (json.load(open(yol, encoding="utf-8")) or {}).items()}
        esl = {k: malzeme_coz(v) for k, v in ham.items()}
        return {k: v for k, v in esl.items() if v}, \
               sorted({ham[k] for k, v in esl.items() if not v})

    with open(yol, encoding="utf-8-sig", errors="replace") as f:
        satirlar = [x.rstrip("\n") for x in f if x.strip()]
    if not satirlar:
        return {}, []
    ayr = _ayirici(satirlar[0])
    tablo = [x.split(ayr) for x in satirlar]

    # Başlık satırını bul: ilk 10 satırdan kod + malzeme sütunu bulunanı.
    ik = im = iy = bas = None
    for n, sat in enumerate(tablo[:10]):
        k = _sutun(sat, KOD_BASLIK)
        m = _sutun(sat, MAL_BASLIK)
        if k is not None and m is not None and k != m:
            ik, im, bas = k, m, n
            iy = _sutun(sat, YOG_BASLIK)
            break
    if bas is None:                     # başlık yok: kod;malzeme varsayılır
        ik, im, bas = 0, 1, -1

    esl, bilinmeyen = {}, []
    for sat in tablo[bas + 1:]:
        if len(sat) <= max(ik, im):
            continue
        kod, mal = sat[ik].strip().strip('"'), sat[im].strip().strip('"')
        if not kod or not mal or _tr_sade(kod) in KOD_BASLIK:
            continue
        m = malzeme_coz(mal)
        if m:
            esl[_tr_sade(kod)] = m
        else:
            bilinmeyen.append(mal)
    return esl, sorted(set(bilinmeyen))


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


def malzeme_ata(k, esl, genel, data_oncelik=True):
    """Bir komponentin malzemesi ve nereden geldiği.

    Sıra: eşleme dosyası/kullanıcı seçimi > data'da tanımlı malzeme > genel.
    Data'da (STEP malzeme alanı ya da parça adı) malzeme okunabiliyorsa
    kullanıcıya sorulmasına gerek kalmaz."""
    if esl:
        m = malzeme_coz(esl.get(_tr_sade(k["kod"]), "") or "")
        if not m:
            # Tam eşleşme yoksa adın içinde geçen kodu ara. Kısa anahtarlar
            # ("1", "A12" gibi) neredeyse her kodun içinde geçer ve yanlış
            # malzeme atanmasına yol açar; bu yüzden en az 5 karakter ve
            # sınırları harf/rakam olmayan bir eşleşme aranır.
            kod_s, ad_s = _tr_sade(k["kod"]), _tr_sade(k["ad"])
            for kod, mal in esl.items():
                if not kod or len(kod) < 5:
                    continue
                dsn = r"(?<![0-9a-z])" + re.escape(kod) + r"(?![0-9a-z])"
                if re.search(dsn, kod_s) or re.search(dsn, ad_s):
                    m = malzeme_coz(mal)
                    break
        if m:
            return m, "secim"
    if data_oncelik:
        m = malzeme_tahmin(k.get("malzeme_data"), k.get("ad"))
        if m:
            return m, "data"
    return genel, "genel"


# ---------------------------------------------------------------- iş akışı
def step_komponentleri(step, P, log=print):
    """STEP'i okur, kopyaları birleştirip komponent listesini döndürür."""
    b = E.bicim_tani(step)
    ag = []
    kayit = E.oku(step, malzeme=True, agac=ag)
    log(f"{os.path.basename(step)}: {b}, {len(kayit)} katı okundu")
    if b != "STEP":
        # IGES ve BREP montaj ağacı ve parça adı taşımaz: ölçüler doğru
        # çıkar ama BOM'da kod/tanım olmaz, standart eleman ayrımı yapılamaz.
        log(f"! {b} parça adı ve montaj ağacı taşımaz: ölçüler doğru çıkar, "
            f"ama BOM'da kod ve tanım olmaz, civata/somun ayrımı yapılamaz. "
            f"Tam BOM için CAD'den STEP olarak kaydedin.")
    komp = komponentle(kayit, P)
    sayim = Counter(k["sinif"] for k in komp)
    log(f"{len(komp)} komponent  (" + ", ".join(f"{a}: {b}" for a, b in sayim.items()) + ")")
    agac = ag[0] if ag else None
    if agac:
        kat = agac_derinlik(agac)
        log(f"montaj ağacı: {agac_dugum_sayisi(agac)} düğüm, {kat} kademe")
    return kayit, komp, agac


def agac_derinlik(d, k=1):
    return max([k] + [agac_derinlik(a, k + 1) for a in d.get("alt") or []])


def agac_dugum_sayisi(d):
    return 1 + sum(agac_dugum_sayisi(a) for a in d.get("alt") or [])


def agac_bom(agac, komp, satirlar):
    """Çok kademeli (hiyerarşik) parça listesi.

    Ana ürün, alt montajlar ve onların altındaki parçalar kademe kademe
    numaralanır: 1, 1.1, 1.1.1 ... ADET HER ZAMAN BİR ÜST MONTAJ BAŞINADIR
    (montaj tekniğindeki alışılmış kural): bir alt montaj 2 kez geçiyorsa
    kendi satırında 2 yazar, altındaki parçalarda o montaj başına düşen
    sayı yazar. Toplam adet ayrıca 'toplam_adet' sütununda verilir."""
    # katı indeksi -> komponent  eşlemesi (ölçü/malzeme oradan gelir)
    kati_komp = {}
    for i, k in enumerate(komp):
        for j in k["indeks"]:
            kati_komp[j] = i
    poz_komp = {}
    for r in satirlar:
        poz_komp[r["kod"]] = r

    out = []

    def gez(d, poz, seviye, ust_adet):
        montaj = bool(d.get("montaj")) or bool(d.get("alt"))
        adet = d.get("adet", 1)
        toplam = adet * ust_adet
        sat = {"poz": poz, "seviye": seviye, "kod": "", "ad": d["ad"],
               "adet": adet, "toplam_adet": toplam,
               "tur": "montaj" if montaj else "parca",
               "malzeme_ad": "", "malzeme_kaynak": "", "olcu": "",
               "kg_adet": "", "toplam_kg": ""}
        # Yaprak düğüm: hangi komponente denk geldiğini katı indeksinden bul.
        if not montaj and d.get("katilar"):
            ki = kati_komp.get(d["katilar"][0])
            if ki is not None:
                k = komp[ki]
                sat["kod"] = k["kod"]
                sat["tur"] = k["sinif"]
                r = poz_komp.get(k["kod"])
                if r:
                    for alan in ("malzeme_ad", "olcu", "kg_adet",
                                 "malzeme_kaynak"):
                        sat[alan] = r.get(alan) or ""
                    if r.get("kg_adet"):
                        sat["toplam_kg"] = round(r["kg_adet"] * toplam, 4)
        out.append(sat)
        for i, a in enumerate(d.get("alt") or [], 1):
            gez(a, f"{poz}.{i}", seviye + 1, toplam)

    gez(agac, "1", 0, 1)
    return out


def agac_bom_yaz(on, agac_satir):
    """Hiyerarşik BOM'u CSV ve okunabilir tablo olarak yazar."""
    alan = ["poz", "seviye", "tur", "kod", "ad", "adet", "toplam_adet",
            "malzeme_ad", "malzeme_kaynak", "olcu", "kg_adet", "toplam_kg"]
    with open(os.path.join(on, "BOM_AGAC.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=alan, extrasaction="ignore", delimiter=";")
        w.writeheader()
        for r in agac_satir:
            w.writerow(r)
    L = ["# Hiyerarşik parça listesi (çok kademeli BOM)\n",
         "Ana ürün → alt montaj → parça. **Adet bir üst montaj başınadır**; "
         "ürünün tamamındaki sayı `toplam` sütunundadır.\n",
         "| poz | kademe | tür | kod | tanım | adet | toplam | malzeme | ölçü | kg/adet |",
         "|-----|--------|-----|-----|-------|------|--------|---------|------|---------|"]
    for r in agac_satir:
        girinti = "&nbsp;" * (4 * r["seviye"])
        L.append(f"| {r['poz']} | {r['seviye']} | {r['tur']} | {r['kod'][:26]} | "
                 f"{girinti}{r['ad'][:44]} | {r['adet']} | {r['toplam_adet']} | "
                 f"{(r['malzeme_ad'] or '-')[:26]} | {r['olcu'] or '-'} | "
                 f"{r['kg_adet'] or '-'} |")
    open(os.path.join(on, "BOM_AGAC.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def ornek_sec(komp, en_az_hacim=0.0):
    """Örnek resim için en zengin parçayı seçer: en çok çeşit delik + radüs
    olan, yani her özellikten birden fazla örnek taşıyan parça."""
    aday = [k for k in komp if k["sinif"] == "parca" and k["hacim_mm3"] >= en_az_hacim]
    return aday[0] if aday else None


def zip_yap(on, ad="cizimler.zip", desen=(".dxf",)):
    """Üretilen çizimleri tek dosyada toplar."""
    import zipfile
    yol = os.path.join(on, ad)
    with zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED) as z:
        for d in sorted(os.listdir(on)):
            if d == ad:
                continue
            if d.lower().endswith(tuple(desen)) or d in (
                    "BOM.csv", "BOM.md", "olculer.csv", "olculer.json", "rapor.md"):
                z.write(os.path.join(on, d), d)
        n = len(z.namelist())
    return yol, n


def calistir(step, on, kayit, komp, P, asama=(1, 2, 3), esl=None, agac=None,
             genel=VARSAYILAN_MALZEME, yogunluk=0.0, en_az_hacim=0.0,
             tek=None, en_cok=0, poz_harita=None, tablo_yok=False,
             log=print, ilerleme=None, iptal=None):
    """Üç aşamalı iş akışını yürütür. GUI ve komut satırı aynı yolu kullanır.

    asama    : 1 BOM, 2 detay resmi, 3 montaj resmi
    esl      : kod -> malzeme eşlemesi (parça bazlı)
    genel    : eşlemede olmayanlar için malzeme
    ilerleme : ilerleme(yapilan, toplam) geri çağrısı
    iptal    : True döndürürse iş bırakılır
    """
    # Eşleme anahtarları sadeleştirilir: "01.050.000.01" ile "01.050.000.01 "
    # ya da büyük/küçük harf farkı eşleşmeyi bozmasın.
    asama = set(asama)
    esl = {_tr_sade(a): b for a, b in (esl or {}).items() if b}
    os.makedirs(on, exist_ok=True)
    dur = (lambda: bool(iptal and iptal()))

    cizilecek = [k for k in komp if k["sinif"] == "parca"
                 and k["hacim_mm3"] >= en_az_hacim]
    if tek:
        t = tek.lower()
        cizilecek = [k for k in cizilecek if t in k["kod"].lower() or t in k["ad"].lower()]
    if en_cok:
        cizilecek = cizilecek[:en_cok]
    ciz_id = {id(k) for k in cizilecek}
    toplam = len(komp) + (1 if 3 in asama else 0)

    satirlar, poz = [], 0
    for sira, k in enumerate(komp, 1):
        if dur():
            log("! iptal edildi"); break
        poz += 1
        gercek_poz = (poz_harita or {}).get(k["kod"], poz)
        sat = {"poz": gercek_poz, "kod": k["kod"], "ad": k["ad"], "adet": k["adet"],
               "sinif": k["sinif"], "tip": k["tip"], "dxf": "",
               "hacim_mm3": k["hacim_mm3"], "olcu": ""}
        if k["sinif"] in ("standart", "kaynak"):
            # Standart eleman ve kaynak dikişi için çizim yok; kod + adet yeter.
            if k["sinif"] == "kaynak":
                poz -= 1; sat["poz"] = ""
            satirlar.append(sat)
            if ilerleme:
                ilerleme(sira, toplam)
            continue
        mal, kaynak = malzeme_ata(k, esl, genel)
        yog = yogunluk if yogunluk else yogunluk_kg_mm3(mal)
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
        sat["malzeme_kaynak"] = {"data": "data'dan", "secim": "secim",
                                 "genel": "varsayilan"}[kaynak]
        sat["olcu"] = f"{o['boy_mm']}x{o['en_mm']}x{o['kalinlik_mm']}"
        sat["kg_adet"] = o["kutle_kg"]
        sat["toplam_kg"] = round(o["kutle_kg"] * k["adet"], 4)
        if 2 in asama and id(k) in ciz_id:
            dosya = resim_dosyasi(gercek_poz, k["kod"] or k["ad"], k["ad"])
            try:
                dxf_komponent(s2, o, sat, os.path.join(on, dosya), P)
                sat["dxf"] = dosya
                log(f"  {dosya}  {o['boy_mm']}x{o['en_mm']}x{o['kalinlik_mm']} mm, "
                    f"{o['delik_adedi']} delik, {sat['malzeme_ad'].split(' (')[0]}, "
                    f"{o['kutle_kg']} kg")
            except Exception as ex:
                sat["dxf"] = f"HATA: {ex}"[:80]
                log(f"  {dosya}: HATA {ex}"[:110])
        satirlar.append(sat)
        if ilerleme:
            ilerleme(sira, toplam)

    bom = [r for r in satirlar if r["sinif"] != "kaynak"]
    if tablo_yok:                      # örnek resim turu: tabloları bozma
        return {"klasor": on, "satirlar": satirlar, "bom": bom, "montaj": None}
    montaj = None
    if 3 in asama and not dur():
        log("  montaj resmi hesaplanıyor (büyük montajda sürebilir)...")
        montaj = dxf_montaj([r[1] for r in kayit], os.path.join(on, "00_MONTAJ.dxf"),
                            os.path.basename(step), P, bom=bom)
        log(f"  00_MONTAJ.dxf   gabari {montaj['boy_mm']} x {montaj['en_mm']} x "
            f"{montaj['yukseklik_mm']} mm")
        if ilerleme:
            ilerleme(toplam, toplam)

    if 1 in asama:
        bom_yaz(on, bom, satirlar)
        if agac:
            ags = agac_bom(agac, komp, satirlar)
            agac_bom_yaz(on, ags)
            log(f"  BOM_AGAC.csv, BOM_AGAC.md  ({len(ags)} satır, "
                f"{agac_derinlik(agac)} kademe)")
    alan = ["poz", "kod", "ad", "adet", "sinif", "tip", "malzeme_ad", "yogunluk_g_cm3",
            "boy_mm", "en_mm", "kalinlik_mm", "sac_kalinlik_mm", "hacim_mm3",
            "kutle_kg", "toplam_kg", "yuzey_mm2", "delik_adedi", "radus_adedi", "dxf"]
    with open(os.path.join(on, "olculer.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=alan, extrasaction="ignore", delimiter=";")
        w.writeheader()
        for r in satirlar:
            w.writerow(r)
    json.dump({"step": step, "montaj": montaj, "komponent": satirlar},
              open(os.path.join(on, "olculer.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    rapor_yaz(on, step, kayit, komp, satirlar, montaj)
    log("  BOM.csv, BOM.md, olculer.csv, olculer.json, rapor.md")
    return {"klasor": on, "satirlar": satirlar, "bom": bom, "montaj": montaj}


# ---------------------------------------------------------------- CLI
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
    ap.add_argument("step", nargs="?",
                    help="okunacak dosya: STEP (.stp/.step), IGES (.igs) ya da BREP")
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
    ap.add_argument("--gorunus", default=",".join(VARSAYILAN_GORUNUS),
                    help="çizilecek görünüşler, en çok 4: ON,ARKA,SAG,SOL,UST,ALT")
    ap.add_argument("--kesit", action="store_true",
                    help="parçanın ortasından A-A tam kesit görünüşü ekle")
    ap.add_argument("--acinim", default="OTO",
                    help="bükümlü sacların açınımı. OTO (varsayılan): "
                         "bükümlü sac parçaları program kendisi bulur. "
                         "Ayrıca kod listesi (virgülle), HEPSI ya da "
                         "YOK yazılabilir")
    ap.add_argument("--k-faktor", type=float, default=None,
                    help=f"büküm payı K-faktörü, 0.10 - 0.60 arası "
                         f"(saklanan değer; ilk kurulumda {K_FAKTOR})")
    ap.add_argument("--zip", action="store_true", help="çıktıları cizimler.zip'te topla")
    a = ap.parse_args()
    if a.malzeme_liste:
        malzeme_listele()
        if not a.step:
            return
    if not a.step:
        ap.error("STEP dosyası verilmedi")
    asama = {int(t) for t in re.findall(r"[123]", a.asama)} or {1, 2, 3}
    if a.montaj_yok:
        asama.discard(3)
    gor = gorunus_sec([t.strip().upper() for t in a.gorunus.replace(";", ",").split(",")])
    P = {"gizli": a.gizli, "en_az_delik": a.en_az_delik, "yogunluk": RHO,
         "gorunusler": gor, "kesit": bool(a.kesit)}
    print("görünüşler: " + ", ".join(GORUNUS_AD[g] for g in gor)
          + (" + " + KESIT_AD if a.kesit else ""))

    t0 = time.time()
    try:
        E.bicim_tani(a.step)
    except E.OkunamazBicim as ex:
        print("\n" + str(ex) + "\n")
        return
    kayit, komp, agac = step_komponentleri(
        a.step, P, log=lambda t: print(f"{t}  [{time.time()-t0:.0f}s]"))
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
        esl, bilinmeyen = malzeme_dosya_oku(a.malzeme_dosya)
        print(f"malzeme dosyası: {a.malzeme_dosya} ({len(esl)} kayıt eşleşti)")
        if bilinmeyen:
            print("! tanınmayan malzeme adı: " + ", ".join(bilinmeyen[:10])
                  + (f" (+{len(bilinmeyen)-10})" if len(bilinmeyen) > 10 else ""))
            print("  --malzeme-liste ile tanınan adlara bakıp dosyada düzeltin.")
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
        print("  --malzeme <ad> | --malzeme-dosya <csv> | --malzeme-sor ile değiştirin.")
        print(f"  Şablon yazıldı: {sab}  (doldurup --malzeme-dosya ile verin)")

    istek = (a.acinim or "").strip()
    if istek.upper() in ("YOK", "HAYIR", "KAPALI"):
        istek = ""
    if istek:
        kf = a.k_faktor if a.k_faktor is not None else k_faktor_ayari()
        if not 0.1 <= kf <= 0.6:
            print(f"hata: K-faktörü 0.10 - 0.60 arasında olmalı ({kf} verildi)")
            return
        if a.k_faktor is not None:
            ayar_yaz(k_faktor=kf)          # bir daha yazmaya gerek kalmasın
        if istek.upper() in ("HEPSI", "HEPSİ", "*"):
            kodlar = None                  # hepsini dene, tarama yok
        elif istek.upper() in ("OTO", "OTOMATIK", "OTOMATİK"):
            kodlar = sac_parcalari(kayit, komp)
        else:
            kodlar = {t.strip() for t in istek.replace(";", ",").split(",")
                      if t.strip()}
        if kodlar is not None and not kodlar:
            print("açınım: bükümlü sac parça bulunamadı")
        else:
            print(f"açınım (K-faktörü {kf}):")
            acilim_yaz(kayit, komp, P, on, kodlar=kodlar, k_faktor=kf)
    calistir(a.step, on, kayit, komp, P, asama=asama, esl=esl, agac=agac, genel=genel,
             yogunluk=a.yogunluk, en_az_hacim=a.en_az_hacim, tek=a.tek,
             en_cok=a.en_cok, log=lambda t: print(f"{t}  [{time.time()-t0:.0f}s]"))
    if a.zip:
        z, n = zip_yap(on)
        print(f"  {os.path.basename(z)}  ({n} dosya)")
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
