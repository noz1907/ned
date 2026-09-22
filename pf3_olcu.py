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

import ezdxf

from OCP.gp import gp_Pnt, gp_Dir, gp_Trsf, gp_Ax2, gp_Vec
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
from OCP.GeomAbs import (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
                         GeomAbs_Sphere, GeomAbs_Line)
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_REVERSED
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRep import BRep_Builder
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepTools import BRepTools
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
    "TARAMA":  (5, CIZGI_KAL),   # kesit taraması
}


def dxf_kur(doc=None):
    doc = doc or ezdxf.new("R2010", setup=True)
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


def gorunus_ciz(msp, kenar, ox, oy, ad, h=4.0, olcu2=True, etiket=None):
    """Bir görünüşü çizer. (genişlik, yükseklik, dx, dy) döndürür; dx/dy,
    ham izdüşüm koordinatını çizim koordinatına taşıyan kaydırmadır."""
    xs = [p[0] for v in kenar.values() for c in v for p in c]
    ys = [p[1] for v in kenar.values() for c in v for p in c]
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    dx, dy = ox - min(xs), oy - min(ys)

    # Teknik resim kuralı: görünen çizgiyle aynı yere düşen gizli çizgi
    # ÇİZİLMEZ (görünen kazanır). HLR görünen ve gizli kenarları ayrı ayrı
    # noktalara böldüğü için uç noktaları karşılaştırmak yetmez: aynı doğru
    # parçası iki tarafta farklı noktalanmış olabilir. Bu yüzden her parça
    # "hangi doğru üzerinde" ve "o doğrunun neresinde" diye saklanır, gizli
    # parça o aralıkla ÖRTÜŞÜYORSA atılır.
    AC_TOL, UZ_TOL = 0.02, 0.12          # radyan, mm

    def _dogru(a, b):
        ux, uy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(ux, uy)
        if n < 1e-9:
            return None
        ux, uy = ux / n, uy / n
        if (ux, uy) < (0.0, 0.0):        # yön ters olsa da aynı doğru
            ux, uy = -ux, -uy
        aci = math.atan2(uy, ux) % math.pi
        uzak = ux * a[1] - uy * a[0]     # doğrunun orijine dik uzaklığı
        t0, t1 = (a[0] * ux + a[1] * uy), (b[0] * ux + b[1] * uy)
        return aci, uzak, min(t0, t1), max(t0, t1)

    gorunen = defaultdict(list)          # (açı kovası, uzaklık kovası) -> aralıklar
    for c in kenar.get("GORUNEN", []):
        for a, b in zip(c, c[1:]):
            d = _dogru(a, b)
            if not d:
                continue
            aci, uzak, t0, t1 = d
            gorunen[(round(aci / AC_TOL), round(uzak / UZ_TOL))].append((t0, t1))

    def _ortusuyor(a, b):
        d = _dogru(a, b)
        if not d:
            return False
        aci, uzak, t0, t1 = d
        ka, ku = round(aci / AC_TOL), round(uzak / UZ_TOL)
        # Komşu kovalara da bak: yuvarlama sınırına denk gelen parçalar kaçmasın.
        for i in (ka - 1, ka, ka + 1):
            for j in (ku - 1, ku, ku + 1):
                for g0, g1 in gorunen.get((i, j), ()):
                    if min(t1, g1) - max(t0, g0) > 0.3 * (t1 - t0):
                        return True
        return False
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
                if _ortusuyor(a, b):
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
    _yaz(msp, etiket or GORUNUS_AD.get(ad, ad), ox, oy + Y + 0.7 * h, 1.3 * h)
    if olcu2:
        d = 4.0 * h                              # ölçü çizgisi uzaklığı
        msp.add_linear_dim(base=(ox, oy - d), p1=(ox, oy), p2=(ox + G, oy),
                           dimstyle=OLCU_STILI, dxfattribs={"layer": "OLCU"}).render()
        msp.add_linear_dim(base=(ox - d, oy), p1=(ox, oy), p2=(ox, oy + Y),
                           angle=90, dimstyle=OLCU_STILI, dxfattribs={"layer": "OLCU"}).render()
    return G, Y, dx, dy


def _cakisiyor(k, digerleri, pay=0.0):
    """İki dikdörtgen (x0, y0, x1, y1) üst üste biniyor mu?"""
    for d in digerleri:
        if (k[0] - pay < d[2] and k[2] + pay > d[0]
                and k[1] - pay < d[3] and k[3] + pay > d[1]):
            return True
    return False


def cap_olculeri(msp, o, yer, kaydir, gkutu, h, ust, en_cok_grup=8):
    """Delik çapı ve kenar radüsü ölçüleri.

    Ölçü çizgisi deliğin/yuvarlamanın merkezinden geçer (dimtofl=1). Yazı
    deliğin HEMEN YANINA, kısa bir kılavuz çizgisiyle konur: önce 45°'lik
    köşegenler denenir (çizim geleneği), yer tutulmuşsa sırayla başka yön
    ve biraz daha uzak nokta denenir. Böylece yazı ne görünüşün üstüne
    biner ne de gereksiz uzağa kaçar.
    Aynı ölçüdeki delikler tek ölçüyle verilir, adet önüne konur: "2x Ø9"."""
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
    for gad, gruplar in kova.items():
        dx, dy = kaydir[gad]
        gk = gkutu[gad]
        # Görünüşün kendisi ve üstündeki görünüş etiketi doludur.
        et = GORUNUS_AD.get(gad, gad)
        etiket_k = (gk[0], gk[3] + 0.7 * h,
                    gk[0] + len(et) * 0.72 * 1.3 * h, gk[3] + 2.0 * h)
        dolu = [gk, etiket_k]
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
            yazi_yeri, kutu_y = None, None
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
                        yazi_yeri, kutu_y = (px, py), k
                        break
                if yazi_yeri:
                    break
            if not yazi_yeri:              # hiç yer yoksa görünüşün üstüne
                py = en_ust.get(gad, gk[3]) + 1.2 * h
                for _ in range(12):        # boş satır bulana dek yukarı çık
                    k = (x - yw, py - yy / 2, x + yw, py + yy / 2)
                    if not _cakisiyor(k, dolu, 0.3 * h):
                        break
                    py += 1.6 * h
                yazi_yeri, kutu_y = (x, py), k
            dolu.append(kutu_y)
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
            en_ust[gad] = max(en_ust.get(gad, gk[3]), kutu_y[3] + 0.6 * h)
            en_sag = max(en_sag, kutu_y[2] + h)
    return en_ust, en_sag


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
    ust, kaydir, gkutu = {}, {}, {}
    for gad in gorunusler:
        goz, xref = GORUNUS[gad]
        kenar = hlr(s, goz, xref, gizli=P.get("gizli", True))
        ox, oy = yer[gad]
        G, Y, dx, dy = gorunus_ciz(msp, kenar, ox, oy, gad, h=h, olcu2=True)
        ust[gad] = oy + Y + 2.2 * h          # görünüş etiketinin de üstü
        kaydir[gad] = (dx, dy)
        gkutu[gad] = (ox, oy, ox + G, oy + Y)
    merkez_cizgileri(msp, o, yer, kaydir)
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
    _tablo(msp, satir, sol, tepe, h, sat_h)
    # Çizimde tablo yok: delikler görünüşlerde "2x Ø9", kenar yuvarlamaları
    # "4x R3" olarak ölçülendirilir. Tam delik ve radüs listeleri rapor.md,
    # olculer.csv ve olculer.json dosyalarındadır.
    doc.saveas(yol)


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
    ust = {}
    for gad in gorunusler:
        goz, xref = GORUNUS[gad]
        kenar = hlr(s, goz, xref, gizli=False)       # montajda gizli çizgi kapalı
        ox, oy = yer[gad]
        G, Y, _dx, _dy = gorunus_ciz(msp, kenar, ox, oy, gad, h=h, olcu2=True)
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
               "malzeme_ad": "", "olcu": "", "kg_adet": "", "toplam_kg": ""}
        # Yaprak düğüm: hangi komponente denk geldiğini katı indeksinden bul.
        if not montaj and d.get("katilar"):
            ki = kati_komp.get(d["katilar"][0])
            if ki is not None:
                k = komp[ki]
                sat["kod"] = k["kod"]
                sat["tur"] = k["sinif"]
                r = poz_komp.get(k["kod"])
                if r:
                    for alan in ("malzeme_ad", "olcu", "kg_adet"):
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
            "malzeme_ad", "olcu", "kg_adet", "toplam_kg"]
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
            dosya = (f"P{gercek_poz:02d}_"
                     + re.sub(r"[^\w\-]+", "_", k["kod"] or k["ad"])[:34] + ".dxf")
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
