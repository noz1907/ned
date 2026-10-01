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
import pf7_is as IS
import pf8_tani as TN
import pf9_excel as XL

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
    # Alaşımsız / düşük alaşımlı çelik numaraları: AISI/SAE 10xx-11xx, C45,
    # Ck45, 42CrMo4, Hardox, DIN malzeme no 1.0xxx - 1.1xxx (1.0038=S235JR)
    (r"\b(?:AISI|SAE)\s*1[01]\d\d\b|\bC[kK]?\s?(?:1[05]|2[25]|3[05]|4[05]|60)\b"
     r"|\b\d{2}CrMo\d|\b\d{2}CrNiMo|\bhardox\b|\bweldox\b|\bstrenx\b"
     r"|\b1\.[01]\d{3}\b", "celik"),
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
    # CAD'den gelen özel malzemeler ("cad:...") yalnız KENDİ anahtarıyla
    # bulunur. Bulanık aramaya girerlerse görünen adlarındaki "Steel"
    # yüzünden sonraki bütün "Steel" satırları o özel malzemeye (ör. 7,50
    # g/cm3) bağlanıyordu - ölçtük.
    tablo = [(k, v) for k, v in MALZEME.items() if not k.startswith("cad:")]
    for k, _v in tablo:
        if a.startswith(k) or k.startswith(a):
            return k
    for k, (tam, _r) in tablo:
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
    # Perçin somun EN BAŞTA: "M6 SOMUN PERCIN" hem somun hem perçin
    # içerir; aynı yerde bitenlerden listede önce gelen tip alınır.
    (r"(?:somun|nut|mutter)[\s_-]*per[cç]in|per[cç]in[\s_-]*somun|rivet[\s_-]*nut"
     r"|rivnut|nutsert|(?:blind|ein)?niet[\s_-]*mutter|pop[\s_-]*nut"
     r"|insert[\s_-]*nut|threaded[\s_-]*insert", "perçin somun"),
    # "Sicherungsscheibe" (E-segman) ve "Scheibenfeder" (yarım ay kama)
    # pul kalıbındaki "scheibe"yi içerir: pulun ÖNÜNDE durmalılar.
    (r"sicherungs?scheibe|sicherungsring|\be[\s_-]?segman|\be[\s_-]?clip|snap[\s_-]*ring"
     r"|retaining[\s_-]*ring", "segman"),
    (r"\bkama\b|passfeder|scheibenfeder|feather[\s_-]*key|parallel[\s_-]*key|woodruff",
     "kama"),
    (r"gres[\s_-]*nipel|gres[oö]rl[uü]k|grease[\s_-]*(?:nipple|fitting)|schmiernippel",
     "gres nipeli"),
    (r"yayl[ıi][\s_-]*pim|spannstift|spiralstift|spring[\s_-]*pin|roll[\s_-]*pin"
     r"|kegelstift|konik[\s_-]*pim|taper[\s_-]*pin|zylinderstift|\bdowel|kopilya"
     r"|\bsplint|cotter[\s_-]*pin", "pim"),
    (r"civata|cıvata|bolt|screw|schraube", "civata"),
    (r"\bsomun(?:u|lar[ıi]?)?\b|\bnut\b|mutter", "somun"),
    (r"\bpul(?:u|lar[ıi]?)?\b|rondela|washer|scheibe|unterlegscheibe", "pul"),
    (r"percin|perçin|rivet|niet", "perçin"),
    (r"\bpim\b|bolzen|\bpin\b|\bmil\b", "pim"),
    (r"\byay\b|\bfeder\b|spring|druckfeder|zugfeder|drehfeder|schenkelfeder|tellerfeder"
     r"|belleville", "yay"),
    (r"rulman|lager|bearing|kugellager", "rulman"),
    (r"segman|sicherung|circlip|seeger", "segman"),
    (r"saplama|stud|gewindestift", "saplama"),
]
# Norm numarası taşımayan SATIN ALINAN elemanlar (ticari ürün). Kaynaklı
# kasa örneğinde kamera, yük bağlama halkası, gömme sallama ve kauçuk
# takozlar üretim parçası sayılıp resmi çiziliyordu.
TICARI = [
    (r"sallama|ba[gğ]lama halka|kald[ıi]rma halka|lashing|zurr|\bmapa\b"
     r"|lifting eye|eye ?bolt|ringschraube|ringmutter|\bhalka(?:s[ıi])?\b",
     "bağlama elemanı"),
    (r"kau[cç]uk (?:takoz|stoper|stopper|tampon|bur[cç])"
     r"|(?:takoz|stoper|stopper|tampon) kau[cç]uk|\bstop+er\b"
     r"|gummipuffer|rubber (?:buffer|bumper|stop)", "kauçuk eleman"),
    (r"\bkamera|\bcamera\b|sens[oö]r|\bsensor\b|\bmotor\b|red[uü]kt[oö]r"
     r"|\bvalf|\bvalve\b|konnekt[oö]r|connector|\bkablo\b|\blamba\b"
     r"|mente[sş]e|\bhinge\b|scharnier|\bkilit\b|amortis[oö]r|gasfeder"
     r"|gas spring", "ticari ürün"),
]
# ÜRETİM PARÇASI olduğunu söyleyen isimler. Türkçe tamlamada asıl isim
# SONDADIR: "CIVATA LAMASI" bir lamadır (üretilir), "SOMUN SACI" bir
# sactır; "KAYNAK SOMUNU" ise bir somundur, "GOVDE PERCINI" perçindir.
# Norm numarası (DIN/ISO/EN) yoksa, üretim ismi standart isimden SONRA
# geliyorsa parça üretim parçasıdır. Kaynaklı kasa
# örneğinde 4 çeşit "K0 CIVATA LAMASI" ve "K0 ON PANEL SOMUN SACI"
# standart sayılıp resmi hiç çizilmiyordu.
URETIM = (r"\blama|\bsac(?:[ıi]|lar[ıi]?)?\b|plaka|braket|bracket|halter"
          r"|profil|destek|tutucu|\bkapa[kg]|\bblo[kg]|g[oö]vde|travers"
          r"|konsol|\blevha|blech|platte|winkel|lasche|\bbock\b|lagerbock"
          r"|\bplate\b|\bsheet\b|\bmontaj|assembly|baugruppe")
NORM = r"\b(?:DIN|ISO|EN)\s*\d{2,}"
# Kaynak dikişleri de ayrı tutulur (parça değildir).
# Dikkat: "naht" serbest bırakılırsa "Anahtar" gibi kelimelere takılır;
# sözcük sonuna sabitlenir. "KAYNAKLI" (kaynaklı montaj/parça) dikiş
# DEĞİLDİR; "KAYNAĞI" (braket kaynağı) dikiştir.
KAYNAK = (r"kehlnaht|naht\b|kayna(?:k|[gğ][ıi])(?!l[ıi])|kaynaklar"
          r"|weld(?!ed|ment)|\bseam\b|diki[sş]")
# Montaj ağacında YALNIZ DİKİŞ toplayan grup: "K0 KAYNAKLAR",
# "KO TELEVRE KAYNAKLAR". İçindeki adsız/garip adlı katılar da dikiştir.
KAYNAK_GRUBU = (r"kaynaklar|diki[sş]ler|\bwelds\b|schwei(?:ss|ß)n[aä]hte"
                r"|\bn[aä]hte\b")


# "KAYNAK" geçen her ad kaynak dikişi DEĞİLDİR: kaynak somunu, kaynak
# cıvatası (saplaması) satın alınan standart elemandır, sac parçaya
# kaynatılır ama BOM'a adediyle girer. Kaynaklı montaj örneğinde
# "M6X20 KAYNAK CIVATASI" (84 adet) ve "M10 KAYNAK SOMUNU" (22 adet)
# dikiş sayılıp BOM'dan düşüyordu.
KAYNAK_ELEMANI = (r"kaynak\s*(?:somun|c[iı]vata|saplama|vida|pim|bur[cç])"
                  r"|(?:somun|c[iı]vata|saplama)\w*\s+kaynak"
                  r"|weld(?:ing)?[\s_-]*(?:nut|stud|bolt|screw|pin)"
                  r"|schwei(?:ss|ß)[\s_-]*(?:mutter|bolzen|schraube)"
                  r"|anschwei(?:ss|ß)mutter")


def _ad_sade(ad):
    return re.sub(r"\s+", " ", (ad or "").strip())


def _sinif_adi(ad):
    """Sınıflama için ad: "_", "." ayraç sayılır. "FL SOMUN_2" ve
    "SOMUN.1" içindeki SOMUN sözcüğü \\b ile yakalanmıyordu ('_' harf
    sayılır) ve M10 flanşlı somun üretim parçası çıkıyordu."""
    return re.sub(r"\s+", " ", re.sub(r"[_.]+", " ", ad or "")).strip().lower()


def kural_anahtari(ad, k=None):
    """Kullanıcının elle verdiği sınıfın saklandığı anahtar: kopya ekleri
    atılmış ad ("Symmetry of X.2" -> "x").

    ADSIZ katıda (COMPOUND, SOLID) ad anahtar olamaz - bir COMPOUND'u
    standart yapmak bütün COMPOUND'ları standart yapardı. Onlarda anahtar
    GEOMETRİK PARMAK İZİDİR: hacim + üç ölçü. Aynı tedarikçi parçası
    başka bir modelde yine tanınır. Adı yalnız parça numarası olanlarda
    da (aynı numara birden çok farklı parçada olabiliyor) anahtar budur."""
    # Adı yalnız parça numarası olan katıda da ad anahtar olamaz: tente
    # kompleksinde 20'den fazla FARKLI parça aynı "55460008672" adını
    # taşıyordu; birini standart yapmak hepsini (sacları) standart yapardı.
    if k is not None and k.get("olc") and not ad_bilgili(ad):
        return ("geo:" + f"{float(k['hacim_mm3']):.1f}:"
                + "x".join(f"{float(v):.1f}" for v in k["olc"]))
    return _sinif_adi(kaynak_tipi(ad))


def sekil_anahtari(imza):
    """Biçim imzasıyla saklanan kural: "sekil:{...}" (bkz. pf8_tani)."""
    return "sekil:" + json.dumps(imza, sort_keys=True, separators=(",", ":"))


def sekil_kurallari(kural):
    out = []
    for a, s in (kural or {}).items():
        if a.startswith("sekil:") and s in ("parca", "standart", "kaynak"):
            try:
                out.append((json.loads(a[6:]), s))
            except ValueError:
                pass
    return out


def ad_bilgili(ad):
    """Ad parçanın ne olduğunu söylüyor mu (norm, kaynak, üretim ya da
    standart eleman sözcüğü). Söylemiyorsa ("510206504-00", "COMPOUND")
    karar biçimden verilir."""
    a = _sinif_adi(ad)
    if TN.isimsiz(ad):
        return False
    return bool(re.search(KAYNAK, a, re.I) or re.search(NORM, a, re.I)
                or re.search(URETIM, a, re.I) or re.search(KAYNAK_ELEMANI, a, re.I)
                or any(re.search(d, a, re.I) for d, _t in STANDART + TICARI))


def benzerden_sinifla(kayit, komp, kural=None, log=print):
    """ÖĞRENME: kullanıcının elle düzelttiği parçaların BİÇİM İMZASI
    saklanır; adı bilgi taşımayan ve biçimi onlara benzeyen parçalar da
    aynı sınıfa geçer (M6 perçin somunu bir kez gösterilince M8'i de).
    Adı ne olduğunu söyleyen parçaya dokunulmaz; o parçanın kendi elle
    verilmiş kuralı da her zaman önce gelir.

    Ölçüldü (4 gerçek model, adı belli 636 komponent): adları farklı
    parçalar arasında 13190 benzer çift çıktı; yalnız 1'i farklı sınıftan
    (bir bağlantı braketi ile 25x6,5x1 pul) - ikisinin de adı ne olduğunu
    söylediği için öğrenme onlara zaten uygulanmaz."""
    if kural is None:
        kural = ayar_oku().get("sinif_kurali") or {}
    kurallar = sekil_kurallari(kural)
    if not kurallar:
        return 0
    n = 0
    for k in komp:
        if _kural(kural, k) or (ad_bilgili(k["ad"]) and not k.get("geometri")) \
                or not k["indeks"] or k.get("satin_alinan_montaj"):
            continue
        if "imza" not in k:
            k["imza"] = TN.bicim_imzasi(kayit[k["indeks"][0]][1])
        for im, s in kurallar:
            if TN.benzer(k["imza"], im):
                if s != k["sinif"]:
                    k["sinif"] = s
                    k["tip"] = "benzerinden öğrenildi" if s == "standart" else ""
                    k["ogrenildi"] = True
                    for a in ("geometri", "oneri", "isimsiz"):
                        k.pop(a, None)
                    n += 1
                break
    if n:
        log(f"benzerinden öğrenme: {n} komponent daha önce elle düzeltilen "
            f"parçalara biçimce benzediği için sınıflandı")
    return n


# ------------------------------------------------ standart ürün kataloğu
# STANDART_KATALOG klasörü: içine YALNIZ standart (satın alınan) ürün
# konur - adı olmasa da. Sac, lama, profil, üretim parçası KONMAZ.
#   *.stp / *.step  tedarikçinin CAD'i: biçim imzası çıkarılır; modelde
#                   aynı biçimli (ölçeği farklı olsa da) ve adı bilgi
#                   taşımayan parça YEREL olarak (AI'sız) standart sayılır
#   *.jpg / *.png   AI kontrolünün resimli turuna referans (pf10_ai)
KATALOG_ADI = "STANDART_KATALOG"


def katalog_klasoru():
    """Ayarda 'katalog_klasoru' varsa o; yoksa programın yanındaki
    STANDART_KATALOG (kaynak klasör, exe'nin yanı, paket içi)."""
    y = (ayar_oku().get("katalog_klasoru") or "").strip()
    if y and os.path.isdir(y):
        return y
    if getattr(sys, "frozen", False):
        # exe: kullanıcının dosya ekleyeceği klasör exe'nin YANINDADIR; yoksa
        # paketteki örneklerle kurulur (paket içi geçici ve salt okunur)
        k = os.path.join(os.path.dirname(sys.executable), KATALOG_ADI)
        if not os.path.isdir(k):
            ic = os.path.join(getattr(sys, "_MEIPASS", ""), KATALOG_ADI)
            try:
                import shutil
                if os.path.isdir(ic):
                    shutil.copytree(ic, k)
                else:
                    os.makedirs(k)
            except OSError:
                return ic if os.path.isdir(ic) else None
        return k
    k = os.path.join(os.path.dirname(os.path.abspath(__file__)), KATALOG_ADI)
    return k if os.path.isdir(k) else None


def katalog_dosyalari(klasor, uzanti):
    out = []
    for kok, _d, dosyalar in os.walk(klasor or ""):
        for d in sorted(dosyalar):
            if d.lower().endswith(uzanti):
                out.append(os.path.join(kok, d))
    return sorted(out)


def katalog_imzalari(klasor=None, log=print):
    """Katalogdaki STEP'lerin biçim imzaları: [(imza, etiket)]. Okunan
    dosyanın imzası klasördeki .pi3d_katalog.json'a saklanır (dosya
    değişmedikçe yeniden okunmaz)."""
    klasor = klasor or katalog_klasoru()
    if not klasor:
        return []
    onbellek_yol = os.path.join(klasor, ".pi3d_katalog.json")
    try:
        onbellek = json.load(open(onbellek_yol, encoding="utf-8"))
    except Exception:
        onbellek = {}
    yeni, out, degisti = {}, [], False
    for y in katalog_dosyalari(klasor, (".stp", ".step")):
        st = os.stat(y)
        anahtar = os.path.relpath(y, klasor)
        imza_ = f"{st.st_size}:{int(st.st_mtime)}"
        kayit_ = onbellek.get(anahtar)
        if not kayit_ or kayit_.get("imza") != imza_:
            try:
                katilar = E.oku(y)
                sek = [TN.bicim_imzasi(k[1]) for k in katilar]
                kayit_ = {"imza": imza_, "sekiller": [q for q in sek if q]}
            except Exception as ex:
                log(f"! katalog: {anahtar} okunamadı ({type(ex).__name__})")
                kayit_ = {"imza": imza_, "sekiller": []}
            degisti = True
        yeni[anahtar] = kayit_
        etiket = os.path.splitext(anahtar)[0].replace(os.sep, " / ")
        out += [(q, etiket) for q in kayit_["sekiller"]]
    if degisti or set(yeni) != set(onbellek):
        try:
            json.dump(yeni, open(onbellek_yol, "w", encoding="utf-8"), ensure_ascii=False)
        except OSError:
            pass
    return out


def katalogdan_sinifla(kayit, komp, kural=None, katalog=None, log=print):
    """Katalogdaki bir STEP şekline benzeyen, adı bilgi taşımayan üretim
    parçasını standart yapar (tip: "katalog: <dosya adı>"). Elle verilen
    sınıfa ve adı ne olduğunu söyleyen parçaya dokunulmaz."""
    if katalog is None:
        katalog = katalog_imzalari(log=log)
    if not katalog:
        return 0
    if kural is None:
        kural = ayar_oku().get("sinif_kurali") or {}
    n = 0
    for k in komp:
        if k["sinif"] != "parca" or _kural(kural, k) or ad_bilgili(k["ad"]) \
                or k.get("cad_kaynak"):
            continue
        if "imza" not in k:
            k["imza"] = TN.bicim_imzasi(kayit[k["indeks"][0]][1])
        for im, etiket in katalog:
            if TN.benzer(k["imza"], im):
                k["sinif"], k["tip"] = "standart", f"katalog: {etiket}"
                k["katalog"] = etiket
                for a in ("aday", "isimsiz", "oneri"):
                    k.pop(a, None)
                n += 1
                break
    if n:
        log(f"standart ürün kataloğu: {n} komponent katalogdaki bir ürüne biçimce "
            "benzediği için standart sayıldı")
    return n


def _kural(kural, k):
    """Komponent için kullanıcının kuralı (yoksa None)."""
    if not kural:
        return None
    return kural.get(kural_anahtari(k["ad"], k))


def sinifla(ad, kural=None):
    """Komponent sınıfı: ('standart', tip) | ('kaynak', '') | ('parca', '').

    Sıra: kullanıcının kuralı > kaynak dikişi > norm (DIN/ISO/EN) >
    üretim ismi (lama, sac, braket ...) > standart / ticari eleman."""
    if kural:
        k = kural.get(kural_anahtari(ad))
        if k in ("parca", "standart", "kaynak"):
            return k, ("elle" if k == "standart" else "")
    a = _sinif_adi(ad)
    eleman = re.search(KAYNAK_ELEMANI, a, re.I)
    if re.search(KAYNAK, a, re.I) and not eleman:
        return "kaynak", ""
    m = re.search(NORM, a, re.I)
    if m:
        return "standart", m.group(0).split()[0].upper()[:3]
    # İkisi birden geçiyorsa SONDAKİ kazanır (asıl isim sondadır):
    # "CIVATA LAMASI" lama -> parça, "GOVDE PERCINI" perçin -> standart.
    uretim = max((m.end() for m in re.finditer(URETIM, a, re.I)), default=-1)
    std = [(max(m.end() for m in re.finditer(d, a, re.I)), t)
           for d, t in STANDART + TICARI if re.search(d, a, re.I)]
    if std and max(e for e, _ in std) > uretim:
        # aynı yerde bitenlerden listede önce geleni (tipi) al
        son = max(e for e, _ in std)
        return "standart", next(t for e, t in std if e == son)
    if uretim >= 0:
        return "parca", ""
    if eleman:
        return "standart", "kaynak elemanı"
    return "parca", ""


URUN_EN_BUYUK = 250.0      # adsız satın alınan ürün (kilit, mandal): gabari sınırı, mm
URUN_PARCA_EN_BUYUK = 150.0


def satin_alinan_montajlar(agac, komp, kayit=None, kural=None, log=print):
    """SATIN ALINAN ÜRÜN TEK KALEMDİR; içindeki / ona bağlı parçalar ONA
    AİTTİR (gömme sallamanın sacı, halkası, yayı bir bütündür).

    "153-02-10-004 - GOMME SALLAMA" bir tedarikçi ürünüdür; STEP'te kendi
    alt montajı olarak gelir. Önceden BOM'a ürünün kendisi değil İÇİNDEKİ
    parçalar ayrı ayrı giriyordu. Şimdi:

      1) ADIYLA standart / ticari (sinifla) EN DIŞ alt montaj tek kalem
         olur: kod addan, adet = ağaçtaki toplam kopya sayısı.
      2) ADSIZ ÜRÜN (tedarikçi kodlu kilit "001_T573679..."): küçük (en
         çok URUN_EN_BUYUK) alt montaj; içinde YALNIZ standart ya da adsız
         küçük parçalar var, en az biri tanınmış bir standart eleman (yay,
         pul, somun...), hiçbiri adıyla üretim parçası ya da dikiş değil.
         Tek kalem olur ama KONTROL listesine "onaylayın" diye düşer.
      3) KATISIZ (yüzey modeli) yaprak adıyla standartsa (yaprak menteşe)
         BOM'a kalem olarak girer; önceden hiç görünmüyordu.

    İçindeki komponentler ("icerik") BOM'a girmez; aynı parça ürünün
    DIŞINDA da kullanılıyorsa yalnız dıştaki adedi kalır. Kopyalar dahil
    sayılır (okuyucu her düğüme bütün kopyaların katılarını "tum" diye
    bağlar). Adında standart sözcük geçen grubun içinde ADIYLA üretim
    parçası varsa (..SACI, ..BRAKETI) birleştirilmez, günlüğe yazılır.
    Döner: tek kaleme inen ürün sayısı."""
    if not agac:
        return 0
    kati_komp = {}
    for i, k in enumerate(komp):
        for j in k["indeks"]:
            kati_komp[j] = i

    def tum(d):
        out = list(d.get("tum") or d.get("katilar") or [])
        for a in d.get("alt") or []:
            out += tum(a)
        return out

    def gabari(kl):
        if kayit is None or not kl:
            return []
        b = Bnd_Box()
        for j in kl:
            BRepBndLib.Add_s(kayit[j][1], b)
        x0, y0, z0, x1, y1, z1 = b.Get()
        return sorted(round(t, 1) for t in (x1 - x0, y1 - y0, z1 - z0))

    def uretim_adli(k):
        # ADINA bakılır, sınıfına değil: agactan_sinifla adı standart grubun
        # çocuklarını zaten "standart" yapmış olur
        return ad_bilgili(k["ad"]) and sinifla(k["ad"], kural)[0] == "parca"

    def adsiz_urun(d, kl, say):
        """Adsız ürün mü: gerekçe ya da None."""
        ad = d.get("ad") or ""
        if ad_bilgili(ad) or len(kl) < 3 or kayit is None:
            return None
        olc = gabari(kl)
        if not olc or olc[-1] > URUN_EN_BUYUK:
            return None
        # içinde en az bir ADSIZ parça olmalı (ürünün bilinmeyen içi); hepsi
        # adıyla standartsa (4 x "M6 KAYNAK SOMUNU") grup bir klasördür,
        # elemanlar zaten kendi adlarıyla kalem olur
        if all(ad_bilgili(komp[i]["ad"]) for i in say):
            return None
        std = []
        for i in say:
            k = komp[i]
            if k["sinif"] == "kaynak" or uretim_adli(k):
                return None
            if k["sinif"] == "parca" and ad_bilgili(k["ad"]):
                return None
            if max(k.get("olc") or [0]) > URUN_PARCA_EN_BUYUK:
                return None
            if k["sinif"] == "standart":
                std.append((k.get("tip") or "standart").replace(" (geometri)", ""))
        if not std:
            return None
        oz = Counter(t.split(" (")[0] for t in std)
        return (f"yapı: {len(kl)} katılı küçük alt montaj ({' x '.join(XL.tr(v, 0) for v in olc)}), "
                f"içinde yalnız standart / adsız küçük parça ("
                + ", ".join(f"{t}" for t, _n in oz.most_common(4))
                + "); adıyla üretim parçası yok: satın alınan ürün")

    gruplar, katisiz = [], []

    def gez(d, carpan, kok):
        adet = d.get("adet", 1) * carpan
        if not kok and d.get("alt"):
            kl = tum(d)
            say = Counter(kati_komp[j] for j in kl if j in kati_komp)
            if sinifla(d.get("ad") or "", kural)[0] == "standart":
                uretim = [komp[i]["ad"] for i in say if uretim_adli(komp[i])]
                if uretim:
                    log(f"! '{_ad_sade(d['ad'])[:50]}' adı standart ama içinde üretim "
                        f"parçası var ({', '.join(u[:30] for u in uretim[:3])}): tek "
                        "kaleme İNDİRİLMEDİ")
                else:
                    gruplar.append((d, adet, kl, say, None))
                    return
            else:
                g = adsiz_urun(d, kl, say)
                if g:
                    gruplar.append((d, adet, kl, say, g))
                    return
        if not kok and not d.get("alt") and d.get("katisiz") and \
                sinifla(d.get("ad") or "", kural)[0] == "standart":
            katisiz.append((d, adet))
        for a in d.get("alt") or []:
            gez(a, adet, False)
    gez(agac, 1, True)
    if not gruplar and not katisiz:
        return 0
    yeni = []
    ic_sayi = Counter()
    for d, adet, kl, say, gerekce in gruplar:
        for i, c in say.items():
            ic_sayi[i] += c
        ad = _ad_sade(d.get("ad") or "")
        if gerekce:
            tip = "satın alınan ürün (adsız)"
        else:
            tip = sinifla(ad, kural)[1] or "satın alınan montaj"
        k = {"ad": ad, "kod": kod_cikar(ad), "adet": adet, "indeks": kl,
             "hacim_mm3": round(sum(komp[i]["hacim_mm3"] * c for i, c in say.items())
                                / max(adet, 1), 1),
             "olc": gabari(d.get("katilar") or kl[:1]) or gabari(kl),
             "sinif": "standart", "tip": tip, "malzeme_data": None,
             "malzeme_yogunluk": None, "satin_alinan_montaj": True,
             "icerik": sorted({_ad_sade(komp[i]["ad"]) for i in say})}
        if gerekce:
            k["geometri"] = gerekce
        yeni.append(k)
        d["satin_alinan"] = True
    for d, adet in katisiz:
        ad = _ad_sade(d.get("ad") or "")
        yeni.append({"ad": ad, "kod": kod_cikar(ad), "adet": adet, "indeks": [],
                     "hacim_mm3": 0.0, "olc": [], "sinif": "standart",
                     "tip": sinifla(ad, kural)[1] or "satın alınan",
                     "malzeme_data": None, "malzeme_yogunluk": None, "katisiz": True,
                     # STEP'te katı yok: adet montaj ağacından - onaylansın
                     "geometri": "katı yok (yüzey modeli): adıyla standart, adet montaj "
                                 "ağacından; CAD'de katı olarak dışa aktarılmamış"})
    kalan = []
    for i, k in enumerate(komp):
        c = ic_sayi.get(i, 0)
        if c >= k["adet"]:
            continue                    # bütünüyle ürünün içinde
        if c:
            k["adet"] -= c              # ürünün dışında da kullanılıyor
        kalan.append(k)
    cikan = len(komp) - len(kalan)
    komp[:] = kalan + yeni
    if gruplar:
        log(f"satın alınan ürün: {len(gruplar)} grup tek kalem oldu ("
            + ", ".join(_ad_sade(g[0].get('ad') or '')[:36] for g in gruplar[:4])
            + f"); içindeki {cikan} komponent ona bağlandı, ayrı kalem değil"
            + (f"; {sum(1 for g in gruplar if g[4])} adsız ürün kontrol listesinde"
               if any(g[4] for g in gruplar) else ""))
    if katisiz:
        log(f"katısız (yüzey modeli) satın alınan {len(katisiz)} eleman BOM'a eklendi: "
            + ", ".join(_ad_sade(d.get('ad') or '')[:36] for d, _a in katisiz[:4]))
    return len(gruplar)


def agactan_sinifla(agac, komp, kural=None, log=print):
    """Adı tek başına yetmeyen katıları MONTAJ AĞACINDAN sınıflar.

    1) Satın alınan bir grubun (ör. "153-02-10-004 - GOMME SALLAMA ...")
       altındaki her katı o grubun parçasıdır: çizilmez, standart sayılır.
    2) Yalnız dikiş toplayan bir grubun ("K0 KAYNAKLAR") altındaki katı
       dikiştir ("ARA DIKME" 171 mm3 dolgu kaynağı parça sayılıyordu).
    Kullanıcının elle verdiği sınıfa dokunulmaz. Bir komponentin BÜTÜN
    kopyaları aynı yerde olmalı; biri başka yerdeyse sınıfı değişmez."""
    if not agac:
        return 0
    ata = {}                 # katı indeksi -> [(ata adı, montaj mı)], yakından uzağa

    def gez(d, yol):
        alt = d.get("alt") or []
        if not alt:
            for j in d.get("katilar") or []:
                ata[j] = yol
        for a in alt:
            gez(a, [d.get("ad") or ""] + yol)
    gez(agac, [])
    degisen = 0
    for k in komp:
        if k["sinif"] != "parca" or _kural(kural, k):
            continue
        # Ağaç, tekrar eden alt montajın yalnız İLK kopyasının katılarını
        # tutar; diğer kopyalar ağaçta görünmez. Görünenler karar verir.
        yollar = [ata[j] for j in k["indeks"] if ata.get(j)]
        if not yollar:
            continue
        # 2) en yakın üst grup dikiş grubu mu
        if all(re.search(KAYNAK_GRUBU, _sinif_adi(y[0]), re.I)
               and not re.search(r"\bgrup|group|montaj|assembly", _sinif_adi(y[0]))
               for y in yollar):
            k["sinif"], k["tip"] = "kaynak", ""
            degisen += 1
            continue
        # 1) üstlerden biri satın alınan eleman mı (kök hariç)
        tic = []
        for y in yollar:
            bul = next((u for u in y[:-1] if sinifla(u, kural)[0] == "standart"),
                       None)
            tic.append(bul)
        if all(tic):
            k["sinif"] = "standart"
            k["tip"] = "satın alınan grup: " + _ad_sade(tic[0])[:40]
            degisen += 1
    if degisen:
        log(f"montaj ağacından {degisen} komponentin sınıfı düzeltildi "
            "(satın alınan grubun içi / dikiş grubu)")
    return degisen


def kaynak_tipi(ad):
    """Kaynak dikişinin TÜRÜ: CAD'in kopyaya eklediği ekler atılır.

    "Symmetry of K0 25 MM TEK KAYNAK.2" ve "K0 25 MM TEK KAYNAK_1" aynı
    dikiştir (25 mm tek kaynak); listede tek satırda sayılır."""
    a = _ad_sade(ad)
    a = re.sub(r"^(?:symmetry of|mirror of|simetri(?:si)?)\s+", "", a, flags=re.I)
    a = re.sub(r"(?:[._]\d+)+$", "", a).strip(" ._,")
    return a or "kaynak"


def kaynak_ozeti(satirlar, en_cok=6):
    """[(tür, adet), ...] - en çok geçen önce. satirlar: {ad, adet}."""
    say = {}
    for r in satirlar:
        t = kaynak_tipi(r.get("ad"))
        say[t] = say.get(t, 0) + int(r.get("adet") or 1)
    return sorted(say.items(), key=lambda t: (-t[1], t[0]))


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
def delik_ve_radus(sh, en_az_cap=1.0, tam_oran=0.90, slot_listesi=None):
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
        # Eksenin model ekseninden sapması (sin açı). 0,9 eşiği deliği bir
        # eksene BAĞLAR ama konumu kesinleştirmez: 01.050.000.01'de 0,4°
        # eğik duvardaki deliğin merkezi sacın bir yüzünden öbürüne 0,02
        # mm kayıyor. Konum ölçüsü yalnız tam paralel deliklere verilir.
        egim = math.sqrt(max(0.0, 1.0 - eks[e] ** 2)) if e >= 0 else 1.0
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
        # Yayın ORTASI eksenden hangi yöne bakıyor (slot ucu dışarı bakar)
        yon = None
        if e >= 0:
            try:
                um = (ad.FirstUParameter() + ad.LastUParameter()) / 2.0
                vm = (ad.FirstVParameter() + ad.LastVParameter()) / 2.0
                q = ad.Value(um, vm)
                q = (q.X(), q.Y(), q.Z())
                v2 = [q[t] - eksen_nokta[t] for t in range(3) if t != e]
                nv = math.hypot(*v2)
                if nv > 1e-9:
                    yon = (v2[0] / nv, v2[1] / nv)
            except Exception:
                yon = None
        if an in tek:
            tek[an]["aci"] += aci
            tek[an]["boy"] = max(tek[an]["boy"], boy)
            tek[an]["egim"] = max(tek[an]["egim"], egim)
            if aci > tek[an]["_en_aci"]:
                tek[an]["_en_aci"], tek[an]["yon"] = aci, yon
        else:
            m2 = list(merkez)
            if e >= 0:
                m2[e] = c.Coord(e + 1)        # eksen yönünde yüzeyin orta noktası
            tek[an] = {"r": r, "eksen": e, "aci": aci, "boy": boy,
                       "merkez": tuple(m2), "egim": egim, "yon": yon, "_en_aci": aci}

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
                         # 4 ondalık: 2 ondalığa yuvarlanan merkez (284,00)
                         # yakındaki iki gerçek seviye arasında (283,987 /
                         # 284,004) hangisi olduğu belirsiz kalıyordu.
                         "merkezler": [[round(v, 4) for v in h["merkez"]] for h in lst[:200]],
                         "egim": [round(h["egim"], 6) for h in lst[:200]]})
    # SLOT: aynı yarıçaplı, aynı eksenli (paralel) iki YARIM silindir
    # (~180°), eksenleri birbirinden uzak. Görünüşten (HLR) değil 3B'den
    # bulunur: gizli kalan slot da (üst flanşın altındaki) konum alır.
    # Karşılıklı en yakın ikililer eşlenir.
    slotlar = []
    for (r, eks), lst in radus_g.items():
        if eks < 0:
            continue
        yarim = [h for h in lst if 0.85 * math.pi <= h["aci"] <= 1.15 * math.pi]

        def uz(a, b):
            return math.sqrt(sum((a["merkez"][t] - b["merkez"][t]) ** 2
                                 for t in range(3) if t != eks))
        en_yakin = {}
        for i, a in enumerate(yarim):
            aday = [(uz(a, b), j) for j, b in enumerate(yarim) if j != i
                    and abs(a["merkez"][eks] - b["merkez"][eks]) < max(1.0, 2 * r)]
            if aday:
                en_yakin[i] = min(aday)
        kul = set()
        for i, (d, j) in en_yakin.items():
            if i in kul or j in kul or en_yakin.get(j, (0, -1))[1] != i:
                continue
            if d < 0.05 or d > 40 * r:
                continue
            kul.update((i, j))
            slotlar.append({"yaricap_mm": round(r, 3), "eksen": "XYZ"[eks],
                            "c1": [round(v, 4) for v in yarim[i]["merkez"]],
                            "c2": [round(v, 4) for v in yarim[j]["merkez"]],
                            "boy_mm": round(d, 3)})
            yarim[i]["_slot"] = yarim[j]["_slot"] = True
        # BÖLÜNMÜŞ SLOT UCU: slot bir kanalın / bükümün üstünden geçiyorsa
        # uç yarım silindir parçalara bölünür, düz yüzde 90° kadarı kalır
        # (P06: R40 slotlar V kanalların üstünde; konumsuz kalıyorlardı).
        # Aynı yarıçaplı iki yay BİRBİRİNİN TAM KARŞISINA bakıyorsa (her
        # yayın ortası öbür merkezden dışarı yönde) slotun iki ucudur.
        # Pencere köşesinin yuvarlatması çapraz baktığı için eşlenmez.
        aday2 = [h for h in lst if not h.get("_slot") and h.get("yon")
                 and 0.6 * math.pi <= h["aci"] <= 1.15 * math.pi]   # köşe yuvarlatması 90°

        def dis_bakar(a, b):
            pa = [a["merkez"][t] for t in range(3) if t != eks]
            pb = [b["merkez"][t] for t in range(3) if t != eks]
            L_ = math.dist(pa, pb)
            if L_ < 0.05:
                return False
            u = ((pa[0] - pb[0]) / L_, (pa[1] - pb[1]) / L_)
            return a["yon"][0] * u[0] + a["yon"][1] * u[1] > 0.98
        en_yakin = {}
        for i, a in enumerate(aday2):
            ad_ = [(uz(a, b), j) for j, b in enumerate(aday2) if j != i
                   and dis_bakar(a, b) and dis_bakar(b, a)]
            if ad_:
                en_yakin[i] = min(ad_)
        kul = set()
        for i, (d, j) in en_yakin.items():
            if i in kul or j in kul or en_yakin.get(j, (0, -1))[1] != i or d > 40 * r:
                continue
            kul.update((i, j))
            slotlar.append({"yaricap_mm": round(r, 3), "eksen": "XYZ"[eks],
                            "c1": [round(v, 4) for v in aday2[i]["merkez"]],
                            "c2": [round(v, 4) for v in aday2[j]["merkez"]],
                            "boy_mm": round(d, 3)})
    radusler = []
    for (r, eks), lst in sorted(radus_g.items(), key=lambda t: (-len(t[1]), t[0][0])):
        radusler.append({"yaricap_mm": r, "adet": len(lst),
                         "eksen": "XYZ"[eks] if eks >= 0 else "eğik",
                         "uzunluk_mm": round(max(h["boy"] for h in lst), 2),
                         "merkezler": [[round(v, 2) for v in h["merkez"]] for h in lst[:200]]})
    if slot_listesi is not None:
        slot_listesi.extend(slotlar)
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
def tel_slotlari(s):
    """Düz yüzlerin İÇ TELLERİNDEN slotlar: tel yalnız yay ve doğrulardan
    oluşur, yaylar iki merkezde toplanır, iki merkezin yarıçapı aynı ve
    her birinde toplam yay açısı yarım tur. Sacın iki yüzü aynı slotu
    iki kez verir; bir kez sayılır. Yalnız model eksenine dik yüzler.
    Döner: delik_ve_radus'un slot kaydıyla aynı biçim."""
    out, gor = [], set()
    ex = TopExp_Explorer(s, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        try:
            ad = BRepAdaptor_Surface(f)
            if ad.GetType() != GeomAbs_Plane:
                continue
            n = ad.Plane().Axis().Direction()
            nv = (n.X(), n.Y(), n.Z())
            k = max(range(3), key=lambda a: abs(nv[a]))
            if abs(abs(nv[k]) - 1.0) > 1e-6:
                continue
            dis = BRepTools.OuterWire_s(f)
            wx = TopExp_Explorer(f, TopAbs_WIRE)
            while wx.More():
                w = wx.Current()
                wx.Next()
                if w.IsSame(dis):
                    continue
                yay = defaultdict(lambda: [0.0, 0.0, None])   # merkez -> [açı, r, 3B]
                dogru = 0
                iyi = True
                kx = TopExp_Explorer(w, TopAbs_EDGE)
                while kx.More():
                    c = BRepAdaptor_Curve(TopoDS.Edge_s(kx.Current()))
                    kx.Next()
                    t = c.GetType()
                    if t == GeomAbs_Line:
                        dogru += 1
                    elif t == GeomAbs_Circle:
                        ci = c.Circle()
                        m = ci.Location()
                        m3 = (m.X(), m.Y(), m.Z())
                        anah = tuple(round(m3[a], 2) for a in range(3) if a != k)
                        yay[anah][0] += abs(c.LastParameter() - c.FirstParameter())
                        yay[anah][1] = ci.Radius()
                        yay[anah][2] = m3
                    else:
                        iyi = False
                        break
                if not iyi or dogru < 1 or len(yay) != 2:
                    continue
                (a1, r1, m1), (a2, r2, m2) = yay.values()
                if abs(r1 - r2) > 1e-3 or not all(0.9 * math.pi <= a_ <= 1.1 * math.pi for a_ in (a1, a2)):
                    continue
                anah = (k,) + tuple(sorted(yay.keys()))
                if anah in gor:
                    continue
                gor.add(anah)
                d = math.dist([m1[a] for a in range(3) if a != k], [m2[a] for a in range(3) if a != k])
                if d < 0.05:
                    continue
                out.append({"yaricap_mm": round(r1, 3), "eksen": "XYZ"[k],
                            "c1": [round(v, 4) for v in m1], "c2": [round(v, 4) for v in m2],
                            "boy_mm": round(d, 3)})
        except Exception:
            continue
    return out


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
        "sac_tip": None, "bukum_ekseni": None,
        "agirlik_merkezi": [round(q, 2) for q in agirlik_merkezi(s)],
        "delikler": None, "radusler": None,
        "dis_capler": dis_capler(s),
        "hizalama": [[round(q, 4) for q in r] for r in R],
    }
    # BÜKÜMLÜ SAC: gabarinin en küçük ölçüsü sac kalınlığı DEĞİLDİR (C
    # profilde 40 mm; sac 1,5 mm). Kalınlık büküm taramasından gelir.
    try:
        tr_ = sac_taramasi(s, k)
    except Exception:
        tr_ = {"sac": False}
    if tr_.get("sac"):
        o["sac_tip"] = tr_["tip"]
        if tr_["tip"] == "bukumlu sac":
            o["sac_kalinlik_mm"] = tr_["kalinlik_mm"]
            if tr_.get("eksen"):
                o["bukum_ekseni"] = [round(q, 6) for q in tr_["eksen"]]
    o["slotlar"] = []
    o["delikler"], o["radusler"] = delik_ve_radus(s, P.get("en_az_delik", 1.0),
                                                  slot_listesi=o["slotlar"])
    # Yarım silindirleri bölünmüş slotu (P06'daki üç büyük R40 slot)
    # yukarıdaki arama kaçırıyordu: slotlar konumsuz kalıyordu. Düz yüzün
    # İÇ TELİ iki eşit yarım daire + doğrulardan oluşuyorsa o da slottur.
    try:
        for sl in tel_slotlari(s):
            e_ = "XYZ".index(sl["eksen"])
            ayni = any(o_["eksen"] == sl["eksen"] and all(
                math.dist([a[t] for t in range(3) if t != e_], [b[t] for t in range(3) if t != e_]) < 0.05
                for a, b in ((o_["c1"], sl["c1"]), (o_["c2"], sl["c2"])))
                or o_["eksen"] == sl["eksen"] and all(
                math.dist([a[t] for t in range(3) if t != e_], [b[t] for t in range(3) if t != e_]) < 0.05
                for a, b in ((o_["c1"], sl["c2"]), (o_["c2"], sl["c1"])))
                for o_ in o["slotlar"])
            if not ayni:
                o["slotlar"].append(sl)
    except Exception:
        pass
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
SON_RAPOR = {}          # son dxf_komponent'in atladıkları (gabari_yok 0 olmalı)
YAKIN_SEVIYE_MM = 0.5   # bu kadar yakın datum seviyeleri tek sıra sayılır (MODEL KONTROL uyarısıyla)
PLAN_UYARI = []         # konum_plani'nin başlığa yazılacak uyarıları (dxf_komponent temizler)
GORUNUS_TR = {"ON": "ÖN", "ARKA": "ARKA", "SAG": "SAĞ", "SOL": "SOL", "UST": "ÜST", "ALT": "ALT"}
ANA_GORUNUS = "ON"      # eşitlikte ana görünüş (bkz. ana_gorunus)
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
# Delik ekseni model ekseninden bu kadar sapıyorsa (sin açı; ~0,06°)
# konumu yazılmaz: sacın kalınlığı boyunca merkez 0,01 mm'den çok kayar.
DELIK_EGIM_SINIR = 1e-3
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
    """Ölçü yazısı: tam sayıya yakınsa tam sayı, değilse bir ondalık.
    Ondalık VİRGÜL; teknik resimde (ISO 129) ölçü rakamına binlik
    ayracı konmaz: 1513,8."""
    return f"{round(v):g}" if abs(v - round(v)) < 0.05 else f"{v:.1f}".replace(".", ",")


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
    "BOLGE":   (4, CIZGI_KAL),   # ızgara bölgesi sınırı (kesik)
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
        doc.layers.get("BOLGE").dxf.linetype = "KESIK"
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
    # ANAYASA (kitap değerleri, yazı boyunun katı; bkz. ANAYASA sözlüğü):
    st.dxf.dimasz = h * _k("ok_mm")             # ok boyu 3 mm
    st.dxf.dimexe = h * _k("uzatma_tasma_mm")   # uzatma çizgisi taşması 1,5 mm
    st.dxf.dimexo = h * _k("uzatma_bosluk_mm")  # uzatma çizgisi boşluğu 2 mm
    st.dxf.dimgap = h * 0.35
    st.dxf.dimdec = 1              # mm, bir ondalık
    st.dxf.dimzin = 8              # sondaki sıfırları yazma
    st.dxf.dimdsep = 44            # ondalık ayracı VİRGÜL (Türkçe / ISO)
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


def mtext_kutusu(v):
    """MTEXT'in GERÇEK sınırı (x0, y0, x1, y1).

    ezdxf'in sınır kutusu, genişliği verilmemiş MTEXT'i BOŞLUKLARDAN
    satırlara kırılmış sayıyor: "3 x 200 = 600" 26 mm eninde, 79 mm
    boyunda bir sütun ölçülüyordu (resimde tek satır). Ölçü yazısının
    kendi çizgisini kestiği sanılıp ölçü gereksiz yere dışarı atılıyordu.
    Burada satır genişliği yazı ölçüm aracından (mtext_size) alınır,
    hizalama noktası ve dönüşle kutu kurulur."""
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


def _yaz(msp, metin, x, y, h=4.0, kat="YAZI"):
    stil = YAZI_STILI if YAZI_STILI in msp.doc.styles else "Standard"
    e = msp.add_text(str(metin),
                     dxfattribs={"layer": kat, "height": h, "style": stil})
    e.set_placement((x, y))
    return e


def _yazi_siniri(e):
    """Çizilmiş bir yazının ÖLÇÜLMÜŞ sınırı; ölçülemezse None. MTEXT
    tek satır ölçülür (bkz. mtext_kutusu)."""
    if e.dxftype() == "MTEXT":
        try:
            return mtext_kutusu(e)
        except Exception:
            pass
    try:
        k = ezdxf.bbox.extents([e], fast=False)
        return None if not k.has_data else (k.extmin.x, k.extmin.y,
                                            k.extmax.x, k.extmax.y)
    except Exception:
        return None


def gorunus_ciz(msp, kenar, ox, oy, ad, h=4.0, olcu2=True, etiket=None,
                pay_x=4.0, pay_y=4.0, etiket_ciz=True):
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
    if etiket_ciz:
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


def gorunus_etiketi(msp, ad, gk, h):
    """Görünüş adı ("ÖN", "ÜST") ölçüler konduktan SONRA, görünüşün
    üstünde ilk boş yere yazılır.

    Eskiden sol üst köşeye, ölçülerden önce yazılıyordu. Datum çoğu
    görünüşte sol alttadır; ölçüler görünüşün üstüne de dağıtılınca
    datumun uzatma çizgisi tam o köşeden yukarı çıkar ve etiketi keserdi.
    Yer ÖLÇÜLÜR: yazı başka bir yazıya ya da çizgiye değmez.
    Döner: etiketin üst kenarı."""
    metin = GORUNUS_AD.get(ad, ad)
    dolu = _yazi_kutulari(msp)
    alan = (gk[0] - 20 * h, gk[1], gk[2] + 20 * h, gk[3] + 60 * h)
    cizgi = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "EKSEN", "OLCU", "BOLGE"))
    e = None
    xs = [gk[0], gk[0] - 3.0 * h] + [gk[0] + 2.0 * h * i for i in range(1, int((gk[2] - gk[0]) / (2.0 * h)))]
    for i in range(80):
        y = gk[3] + (0.7 + 0.5 * i) * h
        for x in xs:
            if e is None:
                e = _yaz(msp, metin, x, y, 1.3 * h)
            else:
                e.set_placement((x, y))
            k = _yazi_siniri(e)
            if k and not _cakisiyor(k, dolu, 0.25 * h) and not _cizgi_kesiyor(k, cizgi, 0.2 * h):
                return k[3]
    k = _yazi_siniri(e) if e is not None else None
    return k[3] if k else gk[3] + 2.0 * h


def _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "EKSEN", "OLCU")):
    """alan (x0, y0, x1, y1) içindeki ÇİZGİ PARÇALARI: görünüş, gizli,
    eksen ve ölçü çizgileri (ölçünün kendi çizgileri dahil). Yazının yerini
    görünüşün KUTUSUYLA değil gerçek çizgilerle denetlemek için: kutu dolu
    sayılınca parçanın ortasındaki deliğin yazısı hep görünüşün dışına,
    uzun kılavuzla gidiyordu."""
    out = []

    def ekle(p, q):
        if (max(p[0], q[0]) < alan[0] or min(p[0], q[0]) > alan[2]
                or max(p[1], q[1]) < alan[1] or min(p[1], q[1]) > alan[3]):
            return
        out.append((p, q))

    def gez(e):
        t = e.dxftype()
        try:
            if t == "LINE":
                ekle((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))
            elif t == "LWPOLYLINE":
                p = [(a, b) for a, b in e.get_points("xy")]
                if e.closed and p:
                    p.append(p[0])
                for a, b in zip(p, p[1:]):
                    ekle(a, b)
            elif t in ("CIRCLE", "ARC"):
                p = [(q.x, q.y) for q in e.flattening(max(0.05, e.dxf.radius / 8.0))]
                for a, b in zip(p, p[1:]):
                    ekle(a, b)
            elif t in ("DIMENSION", "INSERT"):
                for v in e.virtual_entities():
                    gez(v)
        except Exception:
            pass
    for e in msp:
        if e.dxf.layer in katman:
            gez(e)
    return out


def _cizgi_kesiyor(k, parcalar, pay=0.0):
    """Dikdörtgen k (pay kadar büyütülmüş) çizgi parçalarından birini
    kesiyor ya da içine alıyor mu (Liang-Barsky)."""
    x0, y0, x1, y1 = k[0] - pay, k[1] - pay, k[2] + pay, k[3] + pay
    for (ax, ay), (bx, by) in parcalar:
        if max(ax, bx) < x0 or min(ax, bx) > x1 or max(ay, by) < y0 or min(ay, by) > y1:
            continue
        dx, dy = bx - ax, by - ay
        t0, t1 = 0.0, 1.0
        ok = True
        for pp, qq in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
            if abs(pp) < 1e-12:
                if qq < 0:
                    ok = False
                    break
                continue
            r = qq / pp
            if pp < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                ok = False
                break
        if ok:
            return True
    return False


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
        kut = [_yazi_siniri(v) for v in dim.dimension.virtual_entities()
               if v.dxftype() in ("TEXT", "MTEXT")]
        kut = [k for k in kut if k]
        if not kut:
            return None
        return (min(k[0] for k in kut), min(k[1] for k in kut),
                max(k[2] for k in kut), max(k[3] for k in kut))
    except Exception:
        return None


def _olcu_sil(msp, dim):
    """Yeri tutmayan ölçüyü resimden kaldırır, bloğunu da bırakmaz."""
    kl = getattr(dim, "_kilavuz", None)
    if kl is not None:
        try:
            msp.delete_entity(kl)
        except Exception:
            pass
    try:
        e = dim.dimension
        ad = e.dxf.get("geometry", None)
        msp.delete_entity(e)
        if ad and ad in msp.doc.blocks:
            msp.doc.blocks.delete_block(ad, safe=False)
    except Exception:
        pass


def slot_notlari(o, kayip, rapor=None):
    """Boyu resimde HİÇBİR YERE sığmayan slotun ölçüsü kaybolmaz: yay
    yarıçapı yazısının yerine "3x SLOT 80x180" (genişlik x boy) notu
    konur. Sacta slot pres / lazerle kesilir; biçim ölçüsü not olarak
    verilir, konumu zaten referanstan ölçülü (kullanıcı: "çap, uzunluk,
    kısalık varsa özel eksen, onlar verilir"). Notun karşılığı olan
    kayıp kayıttan düşer. Döner: kalan kayıplar."""
    kalan = []
    for k in kayip:
        if "SLOT" not in (k.get("metin") or ""):
            kalan.append(k)
            continue
        i = 0 if k["yon"] == "yatay" else 1
        bulundu = False
        for d in o.get("radusler") or []:
            if k["gad"] not in DELIK_GOR.get(d.get("eksen"), ()):
                continue
            q = [izdusum(c, k["gad"]) for c in d.get("merkezler") or []]
            if not (any(abs(p[i] - k["a"]) < 0.2 for p in q)
                    and any(abs(p[i] - k["b"]) < 0.2 for p in q)):
                continue
            r_ = float(d["yaricap_mm"])
            n_ = max(1, len(q) // 2)
            w_, L_ = 2.0 * r_, abs(k["b"] - k["a"]) + 2.0 * r_
            d["slot_notu"] = (f"{n_}x " if n_ > 1 else "") + \
                f"SLOT {XL.tr(round(w_, 2), 2)}x{XL.tr(round(L_, 2), 2)}"
            bulundu = True
            break
        if bulundu:
            if rapor is not None:
                rapor["yer_yok"] -= 1
        else:
            kalan.append(k)
    return kalan


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
    # kılavuz eğimi yalnız 30° / 45° / 60° aileleri (Règles de cotation s.11;
    # ANAYASA): ne yatay / düşey ne rastgele açı
    YON = [45, 135, 225, 315, 30, 150, 210, 330, 60, 120, 240, 300]
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
        # Görünüşün KUTUSU dolu sayılmaz, ÇİZGİLERİ sayılır: yazı parçanın
        # içindeki boş alana (plaka yüzeyi, slotun yanı) konabilir - deliğin
        # yanında. Kutu dolu sayılınca her yazı görünüşün dışına, uzun
        # kılavuzla gidiyordu. Yazılar ve öbür görünüşler yine dolu.
        dolu = ([etiket_k] + [v for a, v in gkutu.items() if a != gad]
                + [b for b in _yazi_kutulari(msp) if _cakisiyor(b, [yakin])])
        cizgi = _cizgi_parcalari(msp, yakin)
        gruplar.sort(key=lambda q: -q[2])
        for tip, d, r in gruplar:
            noktalar = [(p[0] + dx, p[1] + dy)
                        for p in (izdusum(c, gad) for c in d["merkezler"])]
            # Görünüşün ortasına en uzak delik: yazı dışarı doğru çıksın.
            # Yer bulunamazsa grubun öbür delikleri de denenir.
            mx, my = (gk[0] + gk[2]) / 2.0, (gk[1] + gk[3]) / 2.0
            hedefler = sorted(noktalar, key=lambda q: -((q[0] - mx) ** 2 + (q[1] - my) ** 2))[:6]
            kutu_y = None
            for x, y in hedefler:
                kutu_y = _cap_koy(msp, tip, d, r, x, y, gk, h, dolu, cizgi, en_ust, gad, YON)
                if kutu_y:
                    break
            if kutu_y is None:
                # son çare: kılavuz bir yazının yanından geçebilir ama yazının
                # kendisi hiçbir şeye binmez - çap bilgisi kaybolmasın
                x, y = hedefler[0]
                kutu_y = _cap_koy(msp, tip, d, r, x, y, gk, h, dolu, cizgi, en_ust, gad,
                                  YON, kilavuz_denet=False)
            if kutu_y is None:
                continue                 # hiçbir yere sığmadı: yazma
            dolu.append(kutu_y)
            # yeni etiketin KILAVUZU da artık bir çizgi: sonraki yazılar
            # onun üstüne konmasın (P06: "7x Ø8" SLOT notunun kılavuzunda)
            cizgi = _cizgi_parcalari(msp, yakin)
            en_ust[gad] = max(en_ust.get(gad, gk[3]), kutu_y[3] + 0.6 * h)
            en_sag = max(en_sag, kutu_y[2] + h)
    return en_ust, en_sag


def _cap_koy(msp, tip, d, r, x, y, gk, h, dolu, cizgi, en_ust, gad, YON,
             kilavuz_denet=True):
    """Tek Ø / R etiketi (x, y) deliğine; yeri ölçülerek. Kılavuz da başka
    bir yazının içinden geçmez (P06: "7x Ø8" kılavuzu zincirdeki "20"yi
    kesiyordu). Döner: yazı kutusu ya da None."""
    onek = f"{d['adet']}x " if d["adet"] > 1 else ""
    metin = (f"{onek}%%c{d['cap_mm']:g}" if tip == "cap"
             else f"{onek}R{d['yaricap_mm']:g}").replace(".", ",")
    if d.get("slot_notu"):
        metin = d["slot_notu"]         # bkz. slot_notlari
    yw, yy = len(metin) * 0.72 * h, 1.3 * h       # yazı kutusu
    adaylar, yazi_yeri = [], None
    for uz_k in range(10):                         # uzaklık kademeleri
        uz = r + (1.8 + 1.3 * uz_k) * h
        for a in YON:
            ra = math.radians(a)
            px, py = x + math.cos(ra) * uz, y + math.sin(ra) * uz
            # Yazının hangi yöne doğru yazılacağı ölçü stiline göre
            # değişebildiğinden iki yana da yer ayrılır; böylece
            # hangi hizalama kullanılırsa kullanılsın çakışma olmaz.
            k = (px - yw, py - yy / 2, px + yw, py + yy / 2)
            if not _cakisiyor(k, dolu, 0.3 * h) and \
                    not _cizgi_kesiyor(k, cizgi, 0.25 * h):
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
        if not _cakisiyor(k, dolu + [gk], 0.3 * h) and \
                not _cizgi_kesiyor(k, cizgi, 0.25 * h):
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
        # kılavuz da başka bir yazının içinden geçmemeli (P06: "7x Ø8"
        # kılavuzu zincirdeki "20"yi kesiyordu)
        if gercek is None or (not _cakisiyor(gercek, dolu, 0.3 * h)
                              and not _cizgi_kesiyor(gercek, cizgi, 0.15 * h)
                              and not (kilavuz_denet and (
                                  _dim_yaziya_degiyor(dim, dolu[1:], 0.1 * h)
                                  or _ust_uste(dim, cizgi, h)))):
            kutu_y = gercek or kaba
            break
        _olcu_sil(msp, dim)      # yeri tutmadı, bir sonrakini dene
        kutu_y = None
    return kutu_y

# Konum ölçüsü: bir dizi sayılabilmesi için en az bu kadar delik gerek.
DIZI_EN_AZ = 3
DIZI_PAY = 0.02          # adımlar bu oranda tutuyorsa dizi sayılır
# Dizi değilse bir sırada en çok bu kadar deliğin konumu yazılır. Eskiden
# 6'ydı ve fazlasında yalnız iki uç veriliyordu (P06'nın orta sırasındaki
# Ø45 ve Ø8'lerin konumu yoktu). Ortak başlangıçlı hat çok konumu tek
# çizgide taşıdığı için sınır yükseldi.
KONUM_EN_COK = 40
KISA_HALKA = 0.5      # yazı boyunun bu katından kısa zincir halkası dış hatta girmez


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
    parca = _kopya_at(_t_bol(parca, tol), tol)
    parca = _asili_buda(parca, tol)
    parca = _kopru_at(parca, tol)
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
        # orta nokta YÖNDEN BAĞIMSIZ: iki noktalı çizgide q[1] bitiş
        # noktasıdır; TERS YÖNDE gelen kopya (63,4 -> 63,0 / 63,0 -> 63,4)
        # farklı "orta" verip kopya sayılmıyor, dış hattı bozuyordu
        m1, m2 = q[len(q) // 2], q[(len(q) - 1) // 2]
        o = ((m1[0] + m2[0]) / 2.0, (m1[1] + m2[1]) / 2.0)
        im = (min(a, b), max(a, b), round(uz, 3),
              round(o[0], 2), round(o[1], 2))
        if im not in gor:
            gor.add(im)
            tek.append(q)
    return tek


def _t_bol(parca, tol=HALKA_TOL):
    """T BİRLEŞİMLERİNİ böler: bir kenarın UCU başka bir kenarın ORTASINA
    değiyorsa o kenar orada iki parçaya ayrılır.

    Yüz dolaşımı yalnız uç uca buluşan kenarları tanır. Bükümlü sacın ÖN
    görünüşünde flanş çizgileri dış hatta T biçiminde biner; bölünmezse
    o uçlar "asılı" sayılıp budanıyor ve DIŞ HAT HİÇ KAPANMIYORDU (ölçtük:
    K0 TELEVRE ON KOSE_SOL'un ÖN ve ÜST görünüşünde dış hat yoktu, R15
    ve R5,5 slotlar, girintiler konumsuz kalıyordu)."""
    uclar = [p for q in parca for p in (q[0], q[-1])]
    if not uclar:
        return parca
    hucre = max(1.0, 50 * tol)
    kova = defaultdict(list)
    for p in uclar:
        kova[(int(math.floor(p[0] / hucre)), int(math.floor(p[1] / hucre)))].append(p)
    out = []
    for q in parca:
        yeni = [q[0]]
        kesik = []                      # yeni listede bölünecek nokta indeksleri
        for a, b in zip(q, q[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            if L2 > tol * tol:
                L = math.sqrt(L2)
                x0, x1 = sorted((a[0], b[0]))
                y0, y1 = sorted((a[1], b[1]))
                aday = []
                for ix in range(int(math.floor((x0 - tol) / hucre)), int(math.floor((x1 + tol) / hucre)) + 1):
                    for iy in range(int(math.floor((y0 - tol) / hucre)), int(math.floor((y1 + tol) / hucre)) + 1):
                        for e in kova.get((ix, iy), ()):
                            t = ((e[0] - a[0]) * dx + (e[1] - a[1]) * dy) / L2
                            if t * L <= tol or (1 - t) * L <= tol:
                                continue
                            d = abs((e[0] - a[0]) * dy - (e[1] - a[1]) * dx) / L
                            if d <= tol:
                                aday.append((t, e))
                for t, e in sorted(set(aday)):
                    if math.dist(yeni[-1], e) > tol:
                        yeni.append(e)
                        kesik.append(len(yeni) - 1)
            yeni.append(b)
        if not kesik:
            out.append(q)
            continue
        bas = 0
        for k in kesik:
            out.append(yeni[bas:k + 1])
            bas = k
        out.append(yeni[bas:])
    return [q for q in out if len(q) >= 2]


def _kopru_at(parca, tol=HALKA_TOL):
    """KÖPRÜ kenarları atar: iki bölgeyi birbirine bağlayan, iki yanında da
    aynı yüz olan kenar (kaldırılınca uçları ayrı kalır). Köprü hiçbir
    yüzün sınırı değildir; dolaşımda iki kez geçilir ve o yüz BÜTÜNÜYLE
    atılıyordu - bükümlü sacın ÖN görünüşünde bu yüz DIŞ HATTIN kendisiydi.
    Tarjan köprü bulma (yinelemeli, çoklu kenar güvenli)."""
    n = len(parca)
    if n < 2:
        return parca
    dug, _yer = _dugumle([p for q in parca for p in (q[0], q[-1])], tol)
    kom = defaultdict(list)
    for i in range(n):
        a, b = dug[2 * i], dug[2 * i + 1]
        if a == b:
            continue
        kom[a].append((b, i))
        kom[b].append((a, i))
    giris, dusuk, kopru = {}, {}, set()
    sayac = 0
    for kok in list(kom):
        if kok in giris:
            continue
        giris[kok] = dusuk[kok] = sayac; sayac += 1
        yigin = [(kok, -1, iter(kom[kok]))]
        while yigin:
            v, ust_kenar, it = yigin[-1]
            ilerle = False
            for w, ki in it:
                if ki == ust_kenar:
                    continue
                if w not in giris:
                    giris[w] = dusuk[w] = sayac; sayac += 1
                    yigin.append((w, ki, iter(kom[w])))
                    ilerle = True
                    break
                dusuk[v] = min(dusuk[v], giris[w])
            if ilerle:
                continue
            yigin.pop()
            if yigin:
                u = yigin[-1][0]
                dusuk[u] = min(dusuk[u], dusuk[v])
                if dusuk[v] > giris[u]:
                    kopru.add(ust_kenar)
    return [q for i, q in enumerate(parca) if i not in kopru] if kopru else parca


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
                       en_cok=GIRINTI_EN_COK, sinir=GIRINTI_SINIR, duz=None,
                       tip=None):
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
    gelmediğini söyler; verilmezse her parça doğru sayılır. `tip[i]`
    ("dogru" / "yay" / "egri") verilirse duz ondan çıkar.

    SERBEST EĞRİ ÖLÇÜLMEZ. Girintinin ucuna giden yolda ya da en derin
    yerinde doğru veya yay olmayan bir kenar varsa, o girinti dövme,
    döküm ya da kabartma yüzeyinin bir parçasıdır; konumunun tasarımda
    bir karşılığı yoktur. Doğrulama gerçek modellerde bunların çoğunun
    yanlış çıktığını gösterdi; o girinti bütünüyle atlanır.

    Döner: [{"taraf", "yon", "a", "b", "derinlik", "ic"}]; a ile b,
    ölçünün alınacağı yöndeki HAM izdüşüm koordinatlarıdır."""
    if not dis or not kutu_:
        return []
    if tip is not None:
        duz = [t == "dogru" for t in tip]
        egri = [t == "egri" for t in tip]
    else:
        egri = [False] * len(dis)
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
            uzat. ic_yon: çentik büyük boy tarafındaysa +1, değilse -1.
            Yolda serbest eğri varsa None: bu uç güvenilir değil."""
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
                if egri[sg]:
                    return None
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
                parca.append((bp, uzak(p), bq, uzak(q), i))
            olay = sorted({a, b} | {boy(q) for q in dis
                                    if a - 1e-9 <= boy(q) <= b + 1e-9})
            if len(olay) * len(parca) > 2_000_000:
                return None
            eps = 1e-7 * max(1.0, b - a)
            en, en_sg = None, None
            for v in olay:
                for x in (v - eps, v + eps):
                    if not a < x < b:
                        continue
                    z, z_sg = None, None
                    for bp, dp, bq, dq, sg in parca:
                        if (bp - x) * (bq - x) > 0:
                            continue
                        w = dp + (dq - dp) * (x - bp) / (bq - bp)
                        if z is None or w < z:
                            z, z_sg = w, sg
                    if z is not None and (en is None or z > en):
                        en, en_sg = z, z_sg
            if en is None or egri[en_sg]:
                return None            # dip serbest eğride: güvenilmez
            return round(en, 4)

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
            if a is None or b is None:
                kk = j                 # ucu serbest eğride: girinti atlanır
                continue
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
    tip = []
    for q in kay:
        k = id(q)
        if k not in sinif:
            sinif[k] = "dogru" if len(q) == 2 else kenar_tani(q)["tip"]
        tip.append(sinif[k])
    return kontur_ozellikleri(dis, kutu_, tip=tip)


PENCERE_EN_COK = 4          # bir görünüşte konumu verilecek en çok iç pencere
PENCERE_EN_COK_HALKA = 400  # bundan çok halkalı görünüşte pencere aranmaz


def _slot(kaynaklar):
    """Halka bir SLOT (uzun delik) mu: iki EŞİT yarıçaplı yay (her biri
    ~180°, parçalı olabilir) + düz kenarlar. Döner {"c1", "c2", "r"} ya da
    None. Slot ölçüsü merkezlerden verilir (ISO 129-1): konum yay
    merkezine, boy iki merkez arası, genişlik R ile - kenar (teğet)
    çizgilerinden değil."""
    yay = {}
    gorulen = set()
    for q in kaynaklar:
        # kaynak listesi her çizgi parçası için kenarı TEKRAR verir
        if id(q) in gorulen:
            continue
        gorulen.add(id(q))
        t = kenar_tani(q) if len(q) > 2 else {"tip": "dogru"}
        if not t:
            continue
        if t["tip"] == "yay":
            k = None
            for (cx, cy, r) in yay:
                if math.hypot(cx - t["merkez"][0], cy - t["merkez"][1]) <= max(0.05, 0.01 * r) \
                        and abs(r - t["r"]) <= max(0.03, 0.01 * r):
                    k = (cx, cy, r)
                    break
            if k is None:
                k = (t["merkez"][0], t["merkez"][1], t["r"])
                yay[k] = 0.0
            # açı, noktalar boyunca açı adımlarının toplamı (kenar_tani'nin
            # "aci"sı 0°'dan geçen çeyrek yayda 270 diyebiliyor)
            cx, cy = t["merkez"]
            aci = 0.0
            for u, v in zip(q, q[1:]):
                d = math.atan2(v[1] - cy, v[0] - cx) - math.atan2(u[1] - cy, u[0] - cx)
                aci += abs((d + math.pi) % (2 * math.pi) - math.pi)
            yay[k] += math.degrees(aci)
        elif t["tip"] != "dogru":
            return None
    if len(yay) != 2:
        return None
    (a, aa), (b, ba) = yay.items()
    if abs(a[2] - b[2]) > max(0.03, 0.01 * a[2]) or not all(150 <= v <= 210 for v in (aa, ba)):
        return None
    if math.hypot(a[0] - b[0], a[1] - b[1]) < 0.05:
        return None                         # tek merkez: daire
    return {"c1": (a[0], a[1]), "c2": (b[0], b[1]), "r": (a[2] + b[2]) / 2}


def _buyuk_yay(kaynaklar):
    """Halkanın YARIM TURDAN BÜYÜK yayı var mı (anahtar deliği: R39 daire +
    alt dil)? Varsa merkezi (cx, cy). Böyle bir kesiğin konumu yay
    MERKEZİNDEN verilir; dış kutusunun kenarından verilince P01'de yanındaki
    Ø7 delikle arasında anlamsız bir "2,5" çıkıyordu."""
    yay = {}
    gorulen = set()
    for q in kaynaklar:
        if id(q) in gorulen:
            continue
        gorulen.add(id(q))
        t = kenar_tani(q) if len(q) > 2 else None
        if not t or t["tip"] != "yay":
            continue
        k = None
        for (cx, cy, r) in yay:
            if math.hypot(cx - t["merkez"][0], cy - t["merkez"][1]) <= max(0.05, 0.01 * r) \
                    and abs(r - t["r"]) <= max(0.03, 0.01 * r):
                k = (cx, cy, r)
                break
        if k is None:
            k = (t["merkez"][0], t["merkez"][1], t["r"])
            yay[k] = 0.0
        cx, cy = t["merkez"]
        aci = 0.0
        for u, v in zip(q, q[1:]):
            d = math.atan2(v[1] - cy, v[0] - cx) - math.atan2(u[1] - cy, u[0] - cx)
            aci += abs((d + math.pi) % (2 * math.pi) - math.pi)
        yay[k] += math.degrees(aci)
    buyuk = [(a, k) for k, a in yay.items() if a >= 185.0]
    if not buyuk:
        return None
    a, k = max(buyuk)
    return (k[0], k[1])


def _daire_parcasi(kaynaklar):
    """Halka tek bir dairenin PARÇASI mı (yay(lar)ı tek merkezli + kiriş):
    bir çizginin ikiye böldüğü delik. Delik 3B'den merkezinden ölçülür;
    yarımları pencere sayılıp kenarlarından ölçülmemeli (ölçtük: flanş
    çizgisinin böldüğü Ø8,5 delik ÜST'te dört "pencere" çıkıyordu)."""
    merkez = None
    yay_var = False
    gorulen = set()
    for q in kaynaklar:
        if id(q) in gorulen:
            continue
        gorulen.add(id(q))
        t = kenar_tani(q) if len(q) > 2 else {"tip": "dogru"}
        if not t or t["tip"] == "egri":
            return False
        if t["tip"] == "yay":
            m = (t["merkez"][0], t["merkez"][1], t["r"])
            if merkez and (math.hypot(m[0] - merkez[0], m[1] - merkez[1]) > max(0.05, 0.01 * m[2])
                           or abs(m[2] - merkez[2]) > max(0.03, 0.01 * m[2])):
                return False
            merkez = merkez or m
            yay_var = True
    return yay_var


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
        if _daire_parcasi(kay[i]):
            continue                   # bölünmüş delik: delik olarak ölçülüyor
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
        sl_ = _slot(kay[i])
        out.append({"kutu": tuple(round(v, 4) for v in k),
                    "alan": _cokgen_alani(h), "slot": sl_,
                    "merkez": None if sl_ else _buyuk_yay(kay[i])})
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


# ------------------------------------------------ 3B tasarım seviyeleri
# Görünüşten (2B) bulunan her konum, 3B modelde gerçek bir TASARIM
# SEVİYESİNE denk gelmedikçe resme yazılmaz. İki bağımsız yöntem aynı
# sonucu vermeli - açınımda kesit ile yüzey konturunun karşılaştırıldığı
# gibi. Ölçtük (test/olcu_dogrulama.py, 4 gerçek model): bu denetim
# olmadan girinti konumlarının %15'i, eğik kesim uçlarının %70'i tasarımda
# karşılığı olmayan noktalara (teğet noktası, eğik yüzün köşesi, eğri
# yüzeyin silüeti) veriliyordu.
SEVIYE_TOL = 0.01          # mm


def _yuz_ornekle(f, n=7):
    ad = BRepAdaptor_Surface(TopoDS.Face_s(f))
    u0, u1 = ad.FirstUParameter(), ad.LastUParameter()
    v0, v1 = ad.FirstVParameter(), ad.LastVParameter()
    if max(abs(u0), abs(u1), abs(v0), abs(v1)) > 1e7:
        return []
    out = []
    for a in range(n):
        for b in range(n):
            p = ad.Value(u0 + (u1 - u0) * a / (n - 1),
                         v0 + (v1 - v0) * b / (n - 1))
            out.append((p.X(), p.Y(), p.Z()))
    return out


def _kenar_ornekle(e, n=9):
    c = BRepAdaptor_Curve(TopoDS.Edge_s(e))
    t0, t1 = c.FirstParameter(), c.LastParameter()
    if max(abs(t0), abs(t1)) > 1e7:
        return []
    return [(q.X(), q.Y(), q.Z()) for q in
            (c.Value(t0 + (t1 - t0) * k / (n - 1)) for k in range(n))]


def tasarim_seviyeleri(s, datum=False):
    """Her model ekseni (0=X, 1=Y, 2=Z) için ölçü verilebilecek seviyeler.

    datum=True ise ikinci bir liste de döner: DATUM olabilecek seviyeler.
    Datum yalnız DÜZ YÜZEYE ya da bir EKSENE konur; radüsün teğet noktası
    (silindirin eksen ± r ucu) ölçü alınabilecek bir yer olsa da referans
    olmaz - kullanıcı: "radüs üzerinde referanslama yapılmaz".

      1. o eksene DİK düz yüzey (çentik duvarı, basamak, kenar),
      2. o eksene dik silindirin uçları (eksen ± r: yuva ucu, yuvarlak
         dip); parçalarının toplam açısı yarım turu geçen silindirin
         EKSENİ (delik, yuva ucu merkezi) - tek başına çeyrek olan
         yuvarlatmanın ekseni sayılmaz, teğet noktası ölçü yeri değildir,
      3. SANAL KÖŞE: o düzlemde eğik duran DOĞRU bir kenarın, öbür eksene
         dik bir düz yüzey seviyesini kestiği yer.

    Tip adına güvenilmez, geometriye bakılır: bu STEP'lerde eğik kenarlar
    B-rep'te bile B-spline, delikler dört çeyrek yüzey olarak kayıtlı.

    Döner: [sıralı liste] x 3"""
    kb = kutu(s)
    boy_ = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2], 1.0)
    et = 1e-6 * boy_ + 1e-7
    duz = [set() for _ in range(3)]
    ek = [set() for _ in range(3)]
    eksen_sv = [set() for _ in range(3)]      # yarım turu geçen silindirin ekseni
    silindir = defaultdict(list)
    ex = TopExp_Explorer(s, TopAbs_FACE)
    while ex.More():
        pts = _yuz_ornekle(ex.Current())
        ex.Next()
        if not pts:
            continue
        for i in range(3):
            c = [q[i] for q in pts]
            if max(c) - min(c) < 10 * et:
                duz[i].add(round(sum(c) / len(c), 5))
        for k in range(3):
            i, j = [a for a in range(3) if a != k]
            if max(q[k] for q in pts) - min(q[k] for q in pts) < 10 * et:
                continue
            cf = _cember_uydur([(q[i], q[j]) for q in pts])
            if not cf:
                continue
            cx, cy, r, sap = cf
            if sap > 1e-4 * r + 10 * et or r > 1e5:
                continue
            silindir[(k, round(cx, 3), round(cy, 3), round(r, 3))] += [
                math.atan2(q[j] - cy, q[i] - cx) for q in pts]
            for eks, mer in ((i, cx), (j, cy)):
                ek[eks].add(round(mer - r, 5))
                ek[eks].add(round(mer + r, 5))
    for (k, cx, cy, r), aci in silindir.items():
        ac = sorted(set(round(a, 6) for a in aci))
        if len(ac) < 2:
            continue
        bos = max([ac[t + 1] - ac[t] for t in range(len(ac) - 1)]
                  + [2 * math.pi - (ac[-1] - ac[0])])
        if (2 * math.pi - bos) >= 0.99 * math.pi:
            i, j = [a for a in range(3) if a != k]
            ek[i].add(round(cx, 5))
            ek[j].add(round(cy, 5))
            eksen_sv[i].add(round(cx, 5))
            eksen_sv[j].add(round(cy, 5))
    ex = TopExp_Explorer(s, TopAbs_EDGE)
    while ex.More():
        pts = _kenar_ornekle(ex.Current())
        ex.Next()
        if len(pts) < 2:
            continue
        a, b = pts[0], pts[-1]
        uz = math.dist(a, b)
        if uz < 1e-6:
            continue
        D = [(b[k] - a[k]) / uz for k in range(3)]
        sap = 0.0
        for q in pts[1:-1]:
            w = [q[k] - a[k] for k in range(3)]
            t_ = sum(w[k] * D[k] for k in range(3))
            sap = max(sap, math.sqrt(max(0.0, sum(x * x for x in w) - t_ * t_)))
        if sap > 1e-5 * uz + 10 * et:
            continue                   # doğru değil
        for j in range(3):
            if abs(D[j]) < 1e-7:
                continue
            for i in range(3):
                if i == j or abs(D[i]) < 1e-7:
                    continue
                for bb in duz[j]:
                    v = a[i] + (bb - a[j]) / D[j] * D[i]
                    if kb[i] - SEVIYE_TOL <= v <= kb[i + 3] + SEVIYE_TOL:
                        ek[i].add(round(v, 5))
    hepsi = [sorted(duz[i] | ek[i]) for i in range(3)]
    if datum:
        return hepsi, [sorted(duz[i] | eksen_sv[i]) for i in range(3)]
    return hepsi


def sac_uc_seviyeleri(s, eksen, t, tol=0.05):
    """Bükümlü sacın KESİTİNDE ölçüye değer seviyeler: sacın SERBEST
    UÇLARI (kanat ucu, dudak ucu).

    Kesit görünüşünde (büküm eksenine bakan görünüş) sac, kalınlığı t
    olan bir şerittir. Görünüşten bulunan girinti/pencere seviyelerinin
    çoğu bu şeridin kendisinden gelir ve anlamsızdır: iç yüz (dış yüz ±
    t), büküm radüsünün teğet çizgisi (dış yüz ± (R + t)). C profilde
    38 / 39,5 / 4 / 63 böyle çıkıyordu. Atölyenin istediği kanat
    genişliği + kalınlıktır; kanat genişliği gabariden (dış yüz) serbest
    uca kadardır. Serbest uç: büküm eksenine paralel, eksene dik yönde
    genişliği t olan ve parça BOYUNCA uzanan düz yüz. Boy şartı olmazsa
    uçtaki büküm boşaltma kesiği (C profilin iki ucunda 4 mm) ve slotun
    yan duvarı da "serbest uç" sayılıyordu: ikisi de sac kalınlığı
    genişliğinde ama kısa; yerleri kesitte değil ÜST görünüşte ölçülür.

    eksen: büküm ekseninin model ekseni (0/1/2).
    Döner: [set] x 3 - her model ekseninde serbest uç seviyeleri."""
    kb = kutu(s)
    boy_ = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2], 1.0)
    et = 1e-6 * boy_ + 1e-7
    uc = [set() for _ in range(3)]
    ex = TopExp_Explorer(s, TopAbs_FACE)
    while ex.More():
        pts = _yuz_ornekle(ex.Current())
        ex.Next()
        if not pts:
            continue
        for i in range(3):
            if i == eksen:
                continue
            c = [q[i] for q in pts]
            if max(c) - min(c) >= 10 * et:
                continue
            j = 3 - i - eksen
            gen = max(q[j] for q in pts) - min(q[j] for q in pts)
            uzun = max(q[eksen] for q in pts) - min(q[eksen] for q in pts)
            if abs(gen - t) <= tol and uzun >= 0.5 * (kb[eksen + 3] - kb[eksen]):
                uc[i].add(round(sum(c) / len(c), 5))
    return uc


def sac_kesit_gorunusleri(s, o, gorunusler):
    """Bükümlü sacın kesitinin göründüğü görünüşler ve serbest uç
    seviyeleri: {görünüş: [set] x 3}. Büküm ekseni bir model eksenine
    oturmuyorsa ya da sac değilse boş."""
    e = o.get("bukum_ekseni")
    t = o.get("sac_kalinlik_mm")
    if not e or not t or o.get("sac_tip") != "bukumlu sac":
        return {}
    a = max(range(3), key=lambda i: abs(e[i]))
    if abs(e[a]) < 0.999:
        return {}
    try:
        uc = sac_uc_seviyeleri(s, a, float(t))
    except Exception:
        return {}
    return {g: uc for g in DELIK_GOR["XYZ"[a]] if g in gorunusler}


def seviyede(liste, v, tol=SEVIYE_TOL):
    """v, sıralı listedeki bir seviyenin tol kadar yakınında mı?"""
    i = bisect.bisect_left(liste, v - tol)
    return i < len(liste) and liste[i] <= v + tol


def seviyeye_otur(liste, v, tol=SEVIYE_TOL):
    """v'yi modeldeki TAM seviyeye oturtur; yoksa ya da BELİRSİZSE None.

    Kapıdan geçen değer seviyeden 0,01 mm'ye kadar sapabilir; yuvarlama
    sınırına denk gelirse yanlış basılır (15,05 yerine 15,041 -> "15").
    Oturtulunca basılan sayı tasarım değerinin kendisidir. Pencerede
    birbirinden AYRI iki seviye varsa hangisi olduğu bilinemez; yazılmaz."""
    i = bisect.bisect_left(liste, v - tol)
    aday = []
    while i < len(liste) and liste[i] <= v + tol:
        aday.append(liste[i])
        i += 1
    # 2 mikrondan yakın seviyeler AYNI seviyedir (CAD gürültüsü: C profilde
    # 60,0008 / 60,0010); hiçbir tasarım ölçüsü bu kadar yakın değildir.
    if not aday or aday[-1] - aday[0] > 0.002:
        return None
    return sum(aday) / len(aday)


def model_ham(gad, yon, m):
    """ham_model'in tersi: model koordinatı -> HAM izdüşüm koordinatı."""
    i1, i2, tx, ty = GOR_EKSEN[gad]
    ters = tx if yon == "yatay" else ty
    return -m if ters else m


def ham_model(gad, yon, v):
    """HAM izdüşüm koordinatı -> (model ekseni, model koordinatı)."""
    i1, i2, tx, ty = GOR_EKSEN[gad]
    if yon == "yatay":
        return i1, (-v if tx else v)
    return i2, (-v if ty else v)


GRUP_ORAN = 0.08      # delik grubu: iki delik arası görünüşün bu oranından az
GRUP_YAZI = 10.0      # ... ve yazı boyunun bu katından az
GRUP_EN_COK = 12      # bundan kalabalık öbek bağlantı deseni değil


def _delik_gruplari(nokta_cap, kutu_, h):
    """Aynı çaplı, birbirine yakın delik öbekleri (tek bağlantılı).
    Döner: [[(x, y), ...]] - en az iki delikli, en çok GRUP_EN_COK."""
    if not nokta_cap or not kutu_:
        return []
    buyuk = max(kutu_[2] - kutu_[0], kutu_[3] - kutu_[1])
    cap_g = defaultdict(list)
    for q, c in nokta_cap:
        cap_g[round(c, 2)].append(q)
    out = []
    for c, lst in cap_g.items():
        esik = max(2.0 * c, min(GRUP_ORAN * buyuk, GRUP_YAZI * h))
        n = len(lst)
        ata = list(range(n))

        def bul(a):
            while ata[a] != a:
                ata[a] = ata[ata[a]]
                a = ata[a]
            return a
        for i in range(n):
            for j in range(i + 1, n):
                if math.dist(lst[i], lst[j]) <= esik:
                    ata[bul(i)] = bul(j)
        ob = defaultdict(list)
        for i in range(n):
            ob[bul(i)].append(lst[i])
        out.extend(g for g in ob.values()
                   if 2 <= len(g) <= GRUP_EN_COK and _duzenli_grup(g))
    return out


def _duzenli_grup(g, tol=0.2):
    """Delikten deliğe ölçü yalnız DÜZENLİ desende anlamlıdır: iki delik ya
    da tam dikdörtgen desen (her sütunda her satırın deliği var). Düzensiz
    öbekte zincir birbirine hizasız deliklerin farkını yazar (P06: 6,5 /
    25 / 31,5 / 174,5 - kimsenin işine yaramayan sayılar); o delikler
    referanstan tek tek ölçülür. Kullanıcı: "kare veya daire içindeki
    delikler art arda"."""
    if len(g) == 2:
        return True
    xs = sorted({round(q[0] / tol) for q in g})
    ys = sorted({round(q[1] / tol) for q in g})
    return len(xs) * len(ys) == len(g) and len(xs) >= 2 and len(ys) >= 2


def _grup_imzasi(g, nd=1):
    """Grubun biçimi (ilk deliğe göre göreli konumlar): aynı desenler aynı
    imzayı verir."""
    x0 = min(q[0] for q in g)
    y0 = min(q[1] for q in g)
    return tuple(sorted((round(q[0] - x0, nd), round(q[1] - y0, nd)) for q in g))


def _datum_seviyesi(liste, m, L, tol=SEVIYE_TOL):
    """Datum olabilecek (düz yüz / eksen) seviyelerden, parçanın m ucuna
    EN YAKIN olanı. Uç düz bir yüzse kendisidir; uç bir radüsün teğetiyse
    içerideki ilk düz yüz ya da eksen. Parçanın yarısından derindeyse
    None (o yönde güvenilir bir referans yok)."""
    en = None
    for v in liste:
        d = abs(v - m)
        if d <= 0.5 * L + tol and (en is None or d < en[0]):
            en = (d, v)
    return None if en is None else en[1]


def konum_plani(o, gorunusler, ham, h, kenarlar=None, tol=0.05,
                seviye=None, rapor=None, sac_kesit=None, datum_sv=None,
                izgara=None, sac_kanat=False):
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

    BÜKÜMLÜ SACIN KESİT GÖRÜNÜŞÜ (sac_kesit, bkz. sac_kesit_gorunusleri):
    şeridin iç yüzü ve büküm teğetleri ölçülmez; girinti/pencere
    seviyelerinden yalnız sacın serbest uçları (kanat genişliği) kalır.

    DATUM (datum_sv): yalnız düz yüz ya da eksen. Parçanın o yöndeki ucu
    bir radüsün teğetiyse referans içerideki ilk düz yüze / eksene alınır.

    IZGARA (izgara: {görünüş: [kutu]}): sık kesim bölgesinin içindeki
    delik ve pencereler tek tek ölçülmez (lazer DXF'i verir); bölgenin
    başı ve sonu datumdan verilir.

    Döner: {gorunus: {"yatay": [...], "dusey": [...], "datum": {...}}}
    Her kayıt: {"a","b","metin","seviye","kosu","deger","dik"}; HAM
    izdüşüm koordinatında. kosu=True: datumdan ölçü (ortak başlangıçlı
    hatta çizilir), deger ucu özelliktir, dik özelliğin öbür eksendeki
    koordinatları (uzatma çizgisi oradan başlar, hangi yana konacağı
    ona göre seçilir)."""
    plan = {}
    sac_kesit = sac_kesit or {}
    izgara = izgara or {}
    atlanan = Counter()      # 3B'de karşılığı olmadığı için yazılmayanlar
    # AYNA GÖRÜNÜŞLER (ÖN/ARKA, SAĞ/SOL, ÜST/ALT) aynı dış hattı iki
    # yandan gösterir. Girinti birinde ölçülür; öbüründe tekrarı ISO
    # 129-1'in "her öznitelik bir kez" kuralına aykırı olurdu. Ölçtük:
    # TIRSAN rayında SAĞ ve SOL aynı 9 girintiyi ikişer kez yazıyordu.
    ayna_verildi = set()
    for gad in gorunusler:
        kutu_ = ham.get(gad)
        if not kutu_:
            continue
        nokta, nokta_cap = [], []
        for d in (o or {}).get("delikler") or []:
            # Delik YALNIZ BİR görünüşte konumlanır - çapının yazıldığı
            # görünüşte (cap_olculeri de ilk uygun görünüşü seçer). SAĞ
            # ile SOL aynı delikleri gösterir; ikisinde birden ölçmek
            # "her öznitelik bir kez" kuralına aykırı ve resmi kalabalık
            # yapıyordu.
            ilk = next((g for g in DELIK_GOR.get(d["eksen"], ())
                        if g in gorunusler), None)
            if gad != ilk:
                continue
            egim = d.get("egim") or [0.0] * len(d.get("merkezler") or [])
            for c, eg in zip(d.get("merkezler") or [], egim):
                if eg > DELIK_EGIM_SINIR:
                    continue           # eğik eksen: konumu kesin değil
                q = izdusum(c, gad)
                if any(_icinde(q, b) for b in izgara.get(gad, ())):
                    continue           # ızgaranın içi: lazer DXF'i verir
                nokta.append(q)
                nokta_cap.append((q, d["cap_mm"]))
        # SLOT (3B'den: iki yarım silindir) - delik gibi, eksenine dik İLK
        # seçili görünüşte; görünüşte gizli kalsa da (flanşın altında)
        slot3 = []
        for sl in (o or {}).get("slotlar") or []:
            ilk = next((g for g in DELIK_GOR.get(sl["eksen"], ()) if g in gorunusler), None)
            if gad == ilk:
                slot3.append({"c1": izdusum(sl["c1"], gad), "c2": izdusum(sl["c2"], gad),
                              "r": sl["yaricap_mm"]})
        # EĞİK KESİMİN UÇLARI da konum ister: köşe kırma değil,
        # parçanın gerçek biçimidir; atölye nereden nereye keseceğini
        # ancak uçlarının kenarlardan yerinden bilir. (Pahlar buraya
        # girmez, onlar ok ucunda "5 x 5" diye verilir.)
        # EĞİK KESİM UÇLARI KONUM ALMAZ. Doğrulama (test/olcu_dogrulama.py)
        # dört gerçek modelde bu türün %70'inin tasarım koordinatına
        # denk GELMEDİĞİNİ gösterdi: dövme ve eğri parçalarda eğik
        # çizginin ucu çoğu zaman bir yuvarlatmanın teğet noktası. Kural:
        # hata oranı %1'i aşan ölçü türü yazılmaz. Dış hattaki köşe
        # kesikleri yine ölçülüyor - girinti olarak, sanal köşeden.
        kesim = []
        # GİRİNTİ / ÇIKINTI: çentiğin başı ve sonu da konum ister -
        # delikten farkı yok, atölye nereden nereye keseceğini bilmeli.
        cift = AYNA_CIFT.get(gad)
        ayna_bos = kenarlar and gad in kenarlar and cift not in ayna_verildi
        ozel = gorunus_ozellikleri(kenarlar[gad], kutu_) if ayna_bos else []
        # İÇ PENCERE (yuva, cep): kenarı değil bütün kutusu konum ister.
        pencere = ic_pencereler(kenarlar[gad], kutu_) if ayna_bos else []
        pencere = [r for r in pencere if not any(
            _icinde(((r["kutu"][0] + r["kutu"][2]) / 2, (r["kutu"][1] + r["kutu"][3]) / 2), b)
            for b in izgara.get(gad, ()))]
        # 3B'den gelen slotla aynı olan görünüş slotu ikinci kez ölçülmez
        # (ham koordinatta merkezler aynı)
        if slot3:
            def ayni(a, b):
                return math.dist(a, b) <= 0.2
            pencere = [r for r in pencere if not (r.get("slot") and any(
                (ayni(r["slot"]["c1"], s_["c1"][:2]) and ayni(r["slot"]["c2"], s_["c2"][:2]))
                or (ayni(r["slot"]["c1"], s_["c2"][:2]) and ayni(r["slot"]["c2"], s_["c1"][:2]))
                for s_ in slot3))]
        if ozel or pencere:
            ayna_verildi.add(cift)
        # YOĞUNLUK: bir görünüş, yazı boyuna göre ancak bu kadar girinti
        # taşır. 12 mm'lik parçada yazı 2,5 mm - parçanın beşte biri;
        # ilk sürüm oraya 25 ölçü ekledi, hiçbiri çakışmıyordu ama resim
        # okunmuyordu. Kural: görünüşün uzun kenarının her 4 yazı boyuna
        # bir girinti, en çok GIRINTI_EN_COK. Büyükler öncelikli (liste
        # zaten alanına göre sıralı); tam liste olculer.csv'de.
        # Derinlik de 3B'de karşılığı olan bir seviyeye inmeli: çentiğin
        # dibi. İnmiyorsa derinlik yazılmaz (konumlar yine denetlenir).
        sk = sac_kesit.get(gad)
        if sk is not None:
            for r in ozel:             # şeridin derinliği = t ya da R + t
                if r.get("derinlik") is not None:
                    r["derinlik"] = None
                    atlanan["sac_kesit"] += 1
        if seviye is not None:
            for r in ozel:
                if r.get("derinlik") is None:
                    continue
                if r["yon"] == "yatay":
                    dik = "dusey"
                    kenar = kutu_[1] if r["taraf"] == "alt" else kutu_[3]
                    isaret = 1.0 if r["taraf"] == "alt" else -1.0
                else:
                    dik = "yatay"
                    kenar = kutu_[0] if r["taraf"] == "sol" else kutu_[2]
                    isaret = 1.0 if r["taraf"] == "sol" else -1.0
                dip = kenar + isaret * r["derinlik"]
                # Dip de kenar da modeldeki TAM seviyeye oturtulur;
                # derinlik ikisinin tam farkıdır.
                i_, m_ = ham_model(gad, dik, dip)
                lv_dip = seviyeye_otur(seviye[i_], m_)
                i_, m_ = ham_model(gad, dik, kenar)
                lv_ken = seviyeye_otur(seviye[i_], m_)
                if lv_dip is None or lv_ken is None:
                    r["derinlik"] = None
                    atlanan["derinlik"] += 1
                    continue
                r["derinlik"] = round(abs(model_ham(gad, dik, lv_dip)
                                          - model_ham(gad, dik, lv_ken)), 4)
        if ozel or pencere:
            buyuk_ = max(kutu_[2] - kutu_[0], kutu_[3] - kutu_[1])
            sigar = max(1, int(buyuk_ / (4.0 * h)))
            ozel = ozel[:min(GIRINTI_EN_COK, sigar)]
            pencere = pencere[:min(PENCERE_EN_COK, sigar)]
        izg = list(izgara.get(gad, ()))
        if not nokta and not kesim and not ozel and not pencere and not slot3 and not izg:
            continue
        datum = {}
        # DELİK GRUPLARI: aynı çaplı, birbirine yakın delikler (bağlantı
        # deseni). Kullanıcı: "referanstan ilk deliği ver, sonra o delikten
        # öbür deliği" - grubun yalnız ilk deliği datumdan, öbürleri grup
        # içinde delikten deliğe ölçülür, ölçü grubun yanına konur.
        gruplar = _delik_gruplari(nokta_cap, kutu_, h)
        cikti = {}
        for ad, eksen, e0, e1 in (("yatay", 0, kutu_[0], kutu_[2]),
                                  ("dusey", 1, kutu_[1], kutu_[3])):
            # DATUM parçanın kendi XYZ çerçevesinden gelir, görünüşün
            # sol/alt kenarından değil. Ekseni ters çevrilmiş görünüşte
            # (ARKA, SOL, ALT) sıfır noktası izdüşümün ÖBÜR ucundadır.
            uc = datum_ucu(gad, ad)
            dat, oteki = (e1, e0) if uc else (e0, e1)
            # Datum da bir TASARIM yüzeyi olmalı; yuvarlak bir kenarın ucu
            # ya da eğik bir yüzün köşesi ise o yöndeki konumlar kesin bir
            # yerden ölçülmüş olmaz - hiç verilmez.
            if seviye is not None:
                i_, m_ = ham_model(gad, ad, dat)
                lv_ken = seviyeye_otur(seviye[i_], m_)
                if datum_sv is not None:
                    # RADÜS ÜZERİNDE REFERANS OLMAZ: datum düz yüz ya da eksen
                    lv = _datum_seviyesi(datum_sv[i_], m_, abs(e1 - e0))
                else:
                    lv = lv_ken
                if lv is None:
                    atlanan["datum"] += 1
                    cikti[ad] = []
                    cikti[ad + "_simetrik"] = False
                    continue
                kenar_ = model_ham(gad, ad, lv_ken) if lv_ken is not None else dat
                dat = model_ham(gad, ad, lv)       # tam seviye
                i_, m_ = ham_model(gad, ad, oteki)
                lv = seviyeye_otur(seviye[i_], m_)
                if lv is not None:
                    oteki = model_ham(gad, ad, lv)
                if uc:
                    e1, e0 = kenar_, oteki
                else:
                    e0, e1 = kenar_, oteki
            datum[ad] = dat
            # Grup içi zincir: grubun datuma en yakın değeri ortak hatta,
            # öbürleri delikten deliğe
            lokal = set()              # (değer, dik) - ortak hatta yazılmaz
            lokal_zincir = []
            # AYNI DESENLİ gruplar: iç ölçü bir kez, önüne adedi ("3x 70");
            # her grubun ilk deliği yine referanstan verilir. Kullanıcı:
            # "hepsi aynı ise 1 tane koyman yeterli, x9 dersin".
            imza_say = Counter(_grup_imzasi(g_) for g_ in gruplar)
            imza_gor = set()
            for g_ in gruplar:
                deg = sorted({round(q[eksen], 2) for q in g_})
                if len(deg) < 2:
                    continue
                im_ = _grup_imzasi(g_)
                tekrar = im_ in imza_gor
                imza_gor.add(im_)
                on_ek = f"{imza_say[im_]}x " if imza_say[im_] > 1 else ""
                ref = min(deg, key=lambda v: abs(v - dat))
                for q in g_:
                    if abs(round(q[eksen], 2) - ref) > 0.01:
                        lokal.add((round(q[eksen], 2), round(q[1 - eksen], 2)))
                if tekrar:
                    continue           # iç ölçüsü ilk eşinde "Nx" ile verildi
                sira_ = sorted(deg, key=lambda v: abs(v - ref))
                dz_ = _dizi(sorted(deg)) if len(deg) >= DIZI_EN_AZ else None
                if dz_:
                    lokal_zincir.append({"a": sira_[0], "b": sira_[-1],
                                         "dik_a": [q[1 - eksen] for q in g_ if abs(q[eksen] - sira_[0]) < 0.011],
                                         "dik_b": [q[1 - eksen] for q in g_ if abs(q[eksen] - sira_[-1]) < 0.011],
                                         "grup": g_, "metin": on_ek + f"{dz_[0] - 1} x {XL.tr(round(dz_[1], 2), 2)}"
                                         f" = {XL.tr(round((dz_[0] - 1) * dz_[1], 2), 2)}"})
                    continue
                for v1, v2 in zip(sira_, sira_[1:]):
                    d1 = [q[1 - eksen] for q in g_ if abs(q[eksen] - v1) < 0.011]
                    d2 = [q[1 - eksen] for q in g_ if abs(q[eksen] - v2) < 0.011]
                    lokal_zincir.append({"a": v1, "b": v2, "dik_a": d1, "dik_b": d2,
                                         "grup": g_,
                                         "metin": (on_ek + "<>") if on_ek else None})
            # Aynı sıradaki delikleri bir araya topla, dizi mi diye bak.
            obek = defaultdict(list)
            obek_dik = {}
            for q in nokta:
                ob_ = round(q[1 - eksen] / max(tol, 1e-9))
                obek[ob_].append(q[eksen])
                obek_dik[ob_] = q[1 - eksen]
            # her konumun ÖZELLİĞİ öbür eksende nerede (uzatma çizgisi)
            kaynak_dik = defaultdict(list)
            dizi, tekil = [], set()
            # Her konumun NEREDEN geldiği (delik, kesim, girinti, pencere):
            # doğrulama hata oranını tür tür ölçer, sınırı aşan tür kapanır.
            kaynak = defaultdict(set)

            def otur(v):
                """v'nin modeldeki TAM karşılığı (HAM koordinatta); 3B'de
                karşılığı yoksa ya da belirsizse None."""
                if seviye is None:
                    return v
                i_, m_ = ham_model(gad, ad, v)
                lv = seviyeye_otur(seviye[i_], m_)
                return None if lv is None else model_ham(gad, ad, lv)

            def seviyeli(v):
                return otur(v) is not None

            def ekle(v, tur, dik=None):
                v = otur(v)
                if v is None:
                    atlanan[tur] += 1
                    return
                if sk is not None and tur in ("girinti", "pencere", "kesim") and sac_kanat:
                    atlanan["sac_kesit"] += 1     # kanat dış ölçüleri verir
                    return
                if sk is not None and tur in ("girinti", "pencere", "kesim"):
                    i_, m_ = ham_model(gad, ad, v)
                    if not any(abs(m_ - u) <= 0.01 for u in sk[i_]):
                        atlanan["sac_kesit"] += 1
                        return
                v = round(v, 4)
                tekil.add(v)
                kaynak[v].add(tur)
                if dik is not None:
                    kaynak_dik[v].extend(dik if isinstance(dik, (list, tuple)) else [dik])
            for q in kesim:                # eğik kesimin uçları: tekil
                ekle(q[eksen], "kesim")
            for r in ozel:                 # girintinin başı ve sonu
                if r["yon"] != ad:
                    continue
                for v in (r["a"], r["b"]):
                    # Kenarın UCUNA dayanan girintinin o ucu gabarinin
                    # kendisidir; konum diye bir daha yazılmaz. Ölçtük:
                    # 483,04 / 125,48 / 112,52 gabarinin ikinci kopyası
                    # olarak resme giriyordu.
                    if min(abs(v - e0), abs(v - e1)) > 0.2:
                        ekle(v, "girinti", kutu_[{"alt": 1, "ust": 3, "sol": 0,
                                                   "sag": 2}.get(r["taraf"], 1)])
            slot_ara = []
            for r in [{"kutu": None, "slot": s_} for s_ in slot3] + pencere:
                k = r["kutu"]
                sl = r.get("slot")
                if sl:
                    # SLOT: konum yay MERKEZİNE (datuma yakın olan), sonra
                    # iki merkez arası; kenar (teğet) çizgisine değil
                    m1, m2 = sorted((sl["c1"][eksen], sl["c2"][eksen]),
                                    key=lambda v: abs(v - dat))
                    c_ = sl["c1"] if abs(sl["c1"][eksen] - m1) < 1e-9 else sl["c2"]
                    ekle(m1, "slot", c_[1 - eksen])
                    if abs(m2 - m1) > 0.2:
                        a_, b_ = otur(m1), otur(m2)
                        if a_ is not None and b_ is not None:
                            slot_ara.append({"a": a_, "b": b_, "metin": None,
                                             "kaynak": ["slot"],
                                             "dik": [sl["c1"][1 - eksen],
                                                     sl["c2"][1 - eksen]]})
                        else:
                            atlanan["slot"] += 1
                    continue
                if r.get("merkez"):
                    # yuvarlak kesik (anahtar deliği): konum yay MERKEZİNE
                    ekle(r["merkez"][eksen], "pencere", r["merkez"][1 - eksen])
                    continue
                ekle(k[eksen], "pencere", (k[1 - eksen], k[3 - eksen]))
                ekle(k[eksen + 2], "pencere", (k[1 - eksen], k[3 - eksen]))
            # IZGARA: bölgenin başı ve sonu (içi lazer DXF'inde)
            for b_ in izg:
                ekle(b_[eksen], "izgara", (b_[1 - eksen], b_[3 - eksen]))
                ekle(b_[eksen + 2], "izgara", (b_[1 - eksen], b_[3 - eksen]))
            for _k, v in obek.items():
                dik_ = obek_dik[_k]
                v = sorted(set(round(x, 3) for x in v))
                dz = _dizi(v)
                if dz and not all(seviyeli(v[0] + t * dz[1])
                                  for t in range(dz[0])):
                    atlanan["dizi"] += 1
                    continue           # dizinin bir elemanı modelde yok
                if dz:
                    dizi.append({"bas": otur(v[0]), "son": otur(v[-1]),
                                 "adet": dz[0], "adim": dz[1], "dik": dik_})
                elif len(v) <= KONUM_EN_COK:
                    for x in v:
                        if (round(x, 2), round(dik_, 2)) in lokal:
                            continue           # grup içinde ölçülüyor
                        ekle(x, "delik", dik_)
                else:
                    # Ne dizi ne az sayıda: yalnız uçlar verilir, tam
                    # liste olculer.csv'dedir. Aksi hâlde resim okunmaz.
                    ekle(v[0], "delik", dik_)
                    ekle(v[-1], "delik", dik_)
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
                    ara.append({"a": dat, "b": yakin, "metin": None,
                                "kaynak": ["dizi"], "kosu": True,
                                "deger": yakin, "dik": [r["dik"]]})
                ara.append({"a": r["bas"], "b": r["son"],
                            # adım 0,01'e yuvarlanır, Türkçe yazılır: modelin
                            # 0,0005'lik kayması "2 x 89.9995" yazdırıyordu
                            # "3 x 46 = 138" (ISO 129-1: adet x adım = toplam)
                            "metin": f"{r['adet'] - 1} x {XL.tr(round(r['adim'], 2), 2)}"
                                     f" = {XL.tr(round((r['adet'] - 1) * r['adim'], 2), 2)}",
                            "kaynak": ["dizi"], "adet": r["adet"],
                            "adim": r["adim"], "dik": [r["dik"]]})
                # Son delikten öbür kenara ölçü VERİLMEZ: ikinci bir
                # referans olurdu. Tek referans datumdur (kullanıcı:
                # "sağ için ayrı sol için ayrı referans olamaz").
            # 2) Tekil delikler: HEPSİ AYNI DATUMDAN
            for x in sorted(tekil):
                # Dizinin bir ELEMANINI ikinci kez ölçme. Yalnız eleman:
                # dizinin aralığına düşen slot / pencere konumu atılmamalı
                # (ölçtük: 63..243 delik dizisinin arasındaki slotlar 79,5 /
                # 147,5 konumsuz kalıyordu).
                if any(r["bas"] - 0.2 <= x <= r["son"] + 0.2 and r["adim"] > 0
                       and abs((x - r["bas"]) - round((x - r["bas"]) / r["adim"])
                               * r["adim"]) <= 0.2 for r in dizi):
                    continue
                # HEPSİ AYNI KENARDAN. En yakın kenarı seçmek ölçüyü
                # kısaltır ama görünüşte İKİ AYRI DATUM oluşturur:
                # okuyan hangi ölçünün nereden alındığını ayırt edemez.
                # ISO 129-1 tek ortak referans ister.
                if abs(x - dat) > 0.2:
                    ara.append({"a": dat, "b": x, "metin": None,
                                "kaynak": sorted(kaynak[x]), "kosu": True,
                                "deger": x, "dik": list(kaynak_dik.get(x, []))})
            # 3) Slot: iki yay merkezi arası (boyu); R ayrıca yazılır. AYNI
            # boy ve yarıçaptaki slotlar BİR KEZ ölçülür, adedi önüne yazılır
            # ("9x 6"): bir eleman resimde bir kez ölçülendirilir.
            slot_say = Counter(round(abs(z["b"] - z["a"]), 2) for z in slot_ara)
            slot_gor = set()
            for z in slot_ara:
                an_ = round(abs(z["b"] - z["a"]), 2)
                if an_ in slot_gor:
                    continue
                slot_gor.add(an_)
                if slot_say[an_] > 1:
                    z["metin"] = f"{slot_say[an_]}x SLOT <>"
                ara.append(z)
            # 4) Delik grubu içi: delikten deliğe (grubun yanında)
            for z in lokal_zincir:
                a_, b_ = otur(z["a"]), otur(z["b"])
                if a_ is None or b_ is None:
                    atlanan["grup"] += 1
                    continue
                if simetrik and all((v < orta - 0.05) if uc else (v > orta + 0.05)
                                    for v in (a_, b_)):
                    continue           # öbür yarı: simetri işareti verir
                ara.append({"a": a_, "b": b_, "metin": z.get("metin"), "kaynak": ["grup"],
                            "lokal": True, "dik_a": z["dik_a"], "dik_b": z["dik_b"],
                            "dik": z["dik_a"] + z["dik_b"],
                            "grup_kutu": (min(q[0] for q in z["grup"]), min(q[1] for q in z["grup"]),
                                          max(q[0] for q in z["grup"]), max(q[1] for q in z["grup"]))})
            # Aynı ölçüyü iki kez yazma.
            gor, temiz = {}, []
            for r in ara:
                if r["a"] > r["b"]:   # çizim a<b bekler; ölçünün değeri aynı
                    r["a"], r["b"] = r["b"], r["a"]
                k = (round(r["a"], 2), round(r["b"], 2))
                if k not in gor:
                    gor[k] = r
                    r["seviye"] = 1
                    temiz.append(r)
                else:                  # aynı konumdaki özellikler birleşir
                    gor[k].setdefault("dik", []).extend(r.get("dik") or [])
            # AYNI HİZA SAYILAN SEVİYELER: modelde 104,2 / 104,3 / 104,5 /
            # 104,6'da dört delik (çizim gürültüsü) dört ayrı ölçü değil,
            # tek sıradır. YAKIN_SEVIYE_MM içindeki datum ölçüleri birleşir:
            # ortalamaya en yakın GERÇEK değer yazılır, öbürleri ona
            # bağlanır; fark başlıkta "MODEL KONTROL" uyarısı olur (ölçü
            # uydurulmaz, kullanıcı modeli denetler). Karluna televre sacı.
            kos = [r for r in temiz if r.get("kosu") and r.get("deger") is not None]
            kos.sort(key=lambda r: r["deger"])
            i = 0
            while i < len(kos):
                j = i + 1
                while j < len(kos) and kos[j]["deger"] - kos[j - 1]["deger"] <= YAKIN_SEVIYE_MM:
                    j += 1
                grup = kos[i:j]
                if len(grup) > 1 and grup[-1]["deger"] - grup[0]["deger"] <= 2 * YAKIN_SEVIYE_MM:
                    ort = sum(r["deger"] for r in grup) / len(grup)
                    kal = min(grup, key=lambda r: abs(r["deger"] - ort))
                    for r in grup:
                        if r is kal:
                            continue
                        kal.setdefault("dik", []).extend(r.get("dik") or [])
                        temiz.remove(r)
                    PLAN_UYARI.append(
                        f"{GORUNUS_TR.get(gad, gad)} {'düşey' if ad == 'dusey' else ad} "
                        f"{_sayi(grup[0]['deger'])}..{_sayi(grup[-1]['deger'])} arası "
                        f"{len(grup)} özellik aynı hizada sayıldı ({_sayi(kal['deger'])})")
                i = j
            # Datumdan ölçüde KISA olan içeride durur (ISO 129-1):
            # ölçü çizgileri kesişmesin.
            temiz.sort(key=lambda r: abs(r["b"] - r["a"]))
            cikti[ad] = temiz
            cikti[ad + "_simetrik"] = simetrik and not dizi
        _seviyele(cikti.get("yatay", []), h)
        _seviyele(cikti.get("dusey", []), h)
        # ENGELLER: bu görünüşte daire / yuva / pencere olarak görünen
        # özelliklerin kutuları. Ölçünün uzatma çizgisi bunların üstünden
        # geçmez (kullanıcı: "ölçü çizgisi şekil ve delikler üzerinden
        # geçmemeli; deliğin yanından ver, illa en dıştan verme").
        engel = []
        for d in (o or {}).get("delikler") or []:
            if gad not in DELIK_GOR.get(d["eksen"], ()):
                continue
            r_ = d["cap_mm"] / 2.0
            for c in d.get("merkezler") or []:
                q = izdusum(c, gad)
                engel.append((q[0] - r_, q[1] - r_, q[0] + r_, q[1] + r_))
        for s_ in slot3:
            (x1, y1), (x2, y2), r_ = s_["c1"][:2], s_["c2"][:2], s_["r"]
            engel.append((min(x1, x2) - r_, min(y1, y2) - r_,
                          max(x1, x2) + r_, max(y1, y2) + r_))
        engel.extend(tuple(r["kutu"]) for r in pencere if r.get("kutu"))
        engel.extend(tuple(b_) for b_ in izg)
        if cikti.get("yatay") or cikti.get("dusey"):
            plan[gad] = {"yatay": cikti.get("yatay", []),
                         "engel": engel,
                         "dusey": cikti.get("dusey", []),
                         "datum": datum, "kutu": kutu_, "izgara": izg,
                         "yatay_simetrik": cikti.get("yatay_simetrik", False),
                         "dusey_simetrik": cikti.get("dusey_simetrik", False),
                         "ozellik": ozel,
                         "slot": [{"c1": tuple(s_["c1"][:2]), "c2": tuple(s_["c2"][:2]),
                                   "r": s_["r"]} for s_ in slot3]
                         + [r["slot"] for r in pencere if r.get("slot")]}
    if rapor is not None:
        rapor.update(atlanan)
    return plan


def _serbest_araliklar(a0, a1, engel):
    """[a0, a1] aralığından engel aralıklarını çıkarır."""
    parca = [(a0, a1)]
    for e0, e1 in sorted(engel):
        yeni = []
        for p0, p1 in parca:
            if e1 <= p0 or e0 >= p1:
                yeni.append((p0, p1))
                continue
            if e0 > p0:
                yeni.append((p0, e0))
            if e1 < p1:
                yeni.append((e1, p1))
        parca = yeni
    return parca


def simetri_isareti(msp, plan, gkutu, h):
    """Simetri ekseni ve işareti.

    Simetrik konumların yalnız yarısı ölçülendiriliyor; bunun resimde
    GÖRÜNMESİ şart. İşaret olmadan okuyan, öbür yarının nereye
    geldiğini bilemez ve ölçü eksik sayılır.

    İşaret (ISO 128): eksen çizgisinin her iki ucunda, eksene DİK iki
    kısa paralel çizgi.

    Eksen YAZILARIN ÜSTÜNDEN GEÇMEZ (kullanıcı: C profilin SAĞ
    görünüşünde çizgi "SAĞ" ve "15"in üstünden geçiyordu): en son
    çizilir, yazıların ölçülmüş kutuları çizginin boyundan çıkarılır;
    uçlar yazıya değiyorsa kısalır."""
    dolu = _yazi_kutulari(msp)
    for gad, pl in plan.items():
        if gad not in gkutu:
            continue
        gk = gkutu[gad]
        for yon in ("yatay", "dusey"):
            if not pl.get(yon + "_simetrik"):
                continue
            c = 0.9 * h                    # işaret çizgilerinin yarı boyu
            d = 0.45 * h                   # iki çizgi arası
            pay = 0.3 * h
            if yon == "yatay":             # düşey eksen çizgisi
                x = (gk[0] + gk[2]) / 2.0
                engel = [(k[1] - pay, k[3] + pay) for k in dolu
                         if k[0] - pay - c <= x <= k[2] + pay + c]
                parca = _serbest_araliklar(gk[1] - 1.6 * h, gk[3] + 1.6 * h, engel)
            else:                          # yatay eksen çizgisi
                y = (gk[1] + gk[3]) / 2.0
                engel = [(k[0] - pay, k[2] + pay) for k in dolu
                         if k[1] - pay - c <= y <= k[3] + pay + c]
                parca = _serbest_araliklar(gk[0] - 1.6 * h, gk[2] + 1.6 * h, engel)
            parca = [p for p in parca if p[1] - p[0] > 0.2 * h]
            if not parca:
                continue
            for p0, p1 in parca:
                if yon == "yatay":
                    msp.add_line((x, p0), (x, p1), dxfattribs={"layer": "EKSEN"})
                else:
                    msp.add_line((p0, y), (p1, y), dxfattribs={"layer": "EKSEN"})
            # işaret: eksenin iki UCUNDA (ilk ve son parçanın dış ucu)
            for u, yon_i in ((parca[0][0], 1), (parca[-1][1], -1)):
                for k in (0, 1):
                    v = u + yon_i * k * d
                    if yon == "yatay":
                        msp.add_line((x - c, v), (x + c, v), dxfattribs={"layer": "EKSEN"})
                    else:
                        msp.add_line((v, y - c), (v, y + c), dxfattribs={"layer": "EKSEN"})


def datum_isaretleri(msp, harfler, gorunusler, gkutu, h, plan=None, kaydir=None,
                     kenarlar=None):
    """Datum yüzey simgeleri - ISO 5459.

    Bütün konum ölçüleri artık parçanın kendi XYZ çerçevesinden
    veriliyor. Okuyanın sıfırın NEREDE olduğunu görmesi gerekir; aksi
    hâlde ölçülerin hepsinin aynı yerden gittiği bilgisi resimde
    yazılı değil, yalnız bizim aklımızda kalır.

    Simge: datum yüzeyinin çizgisine TABANI oturan içi dolu üçgen,
    kısa bir kılavuz, kare çerçeve içinde harf.

    Simge DÜZ BİR YÜZÜN görünen çizgisine oturur - radüse DEĞİL
    (kullanıcı: "radüs üzerinde referanslama yapılmaz"). Görünüşün kutu
    kenarı, parçanın o yandaki en uç noktasıdır; orası bir büküm
    radüsüyse ilk sürüm simgeyi radüsün üstüne koyuyordu. Şimdi datum
    seviyesinde (plan["datum"]) duran GÖRÜNEN DOĞRU çizgiler bulunur,
    simge onların üstüne konur. Görünüşte öyle bir çizgi yoksa (datum
    bir eksen ya da yüz görünmüyor) seviyenin uzantısına, görünüşün
    dışına ince bir çizgi çekilir, simge onun ucuna konur.

    Her datum BİR KEZ işaretlenir - göründüğü ilk görünüşte.

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
            uc = datum_ucu(gad, yon)
            dat = ((plan or {}).get(gad) or {}).get("datum", {}).get(yon)
            if dat is None or kaydir is None:
                # planı olmayan görünüş: eski yol (kutu kenarı)
                if plan and any(harf == harfler.get(GOR_EKSEN[g][0 if y == "yatay" else 1])
                                and ((plan.get(g) or {}).get("datum") or {}).get(y) is not None
                                for g in gorunusler for y in ("yatay", "dusey")):
                    continue       # bu harfin gerçek datumu başka görünüşte
                if _datum_ciz(msp, gk, yon, uc, harf, h):
                    yazildi.add(harf)
                continue
            v = dat + (kaydir[gad][0] if yon == "yatay" else kaydir[gad][1])
            if _datum_duz_yuze(msp, gk, yon, uc, v, harf, h, kenarlar.get(gad) if kenarlar else None,
                               kaydir[gad]):
                yazildi.add(harf)
    # hiçbir görünüşte düz çizgi bulunamayan harf: uzantı çizgisiyle
    for gad in gorunusler:
        gk = gkutu.get(gad)
        if not gk or kaydir is None:
            continue
        i1, i2, _tx, _ty = GOR_EKSEN[gad]
        for eksen, yon in ((i1, "yatay"), (i2, "dusey")):
            harf = harfler.get(eksen)
            dat = ((plan or {}).get(gad) or {}).get("datum", {}).get(yon)
            if not harf or harf in yazildi or dat is None:
                continue
            v = dat + (kaydir[gad][0] if yon == "yatay" else kaydir[gad][1])
            if _datum_uzantiya(msp, gk, yon, datum_ucu(gad, yon), v, harf, h):
                yazildi.add(harf)
    return yazildi


def _datum_simge(msp, taban, ucu, mrk, yon, d, c, harf, h):
    msp.add_solid([taban[0], taban[1], ucu], dxfattribs={"layer": "OLCU"})
    ic = (mrk[0] - d * c, mrk[1]) if yon == "yatay" else (mrk[0], mrk[1] - d * c)
    msp.add_line(ucu, ic, dxfattribs={"layer": "OLCU"})
    msp.add_lwpolyline(
        [(mrk[0] - c, mrk[1] - c), (mrk[0] + c, mrk[1] - c),
         (mrk[0] + c, mrk[1] + c), (mrk[0] - c, mrk[1] + c)],
        close=True, dxfattribs={"layer": "OLCU"})
    e = _yaz(msp, harf, mrk[0], mrk[1], 0.72 * h, kat="OLCU")
    ky = _yazi_siniri(e)
    if ky:
        e.set_placement((mrk[0] - (ky[2] - ky[0]) / 2.0, mrk[1] - (ky[3] - ky[1]) / 2.0))


def _datum_yeri_bos(msp, taban, ucu, mrk, c, h, dolu, cizgi):
    """Simgenin kılavuzu ve çerçevesi bir yazıya ya da çizgiye değiyor mu?
    Üçgenin tabanı yüzeye oturduğu için tabana değil, ucundan dışarısına
    bakılır."""
    kutu_ = (min(ucu[0], mrk[0] - c), min(ucu[1], mrk[1] - c),
             max(ucu[0], mrk[0] + c), max(ucu[1], mrk[1] + c))
    uc_ = (min(q[0] for q in (*taban, ucu)), min(q[1] for q in (*taban, ucu)),
           max(q[0] for q in (*taban, ucu)), max(q[1] for q in (*taban, ucu)))
    if _cakisiyor(kutu_, dolu, 0.2 * h) or _cakisiyor(uc_, dolu, 0.1 * h):
        return False
    return not _cizgi_kesiyor(kutu_, cizgi, 0.15 * h)


def _datum_duz_yuze(msp, gk, yon, uc, v, harf, h, kenar, kay):
    """Datum seviyesindeki (v, çizim koordinatı) GÖRÜNEN DOĞRU çizginin
    üstüne simge. Döner: konduysa True."""
    if not kenar:
        return False
    dx, dy = kay
    tol = max(0.02, 1e-4 * h)
    aralik = []
    for p in kenar.get("GORUNEN", []):
        for a, b in zip(p, p[1:]):
            ax, ay, bx, by = a[0] + dx, a[1] + dy, b[0] + dx, b[1] + dy
            if yon == "yatay" and abs(ax - v) <= tol and abs(bx - v) <= tol:
                aralik.append((min(ay, by), max(ay, by)))
            elif yon == "dusey" and abs(ay - v) <= tol and abs(by - v) <= tol:
                aralik.append((min(ax, bx), max(ax, bx)))
    if not aralik:
        return False
    aralik.sort()
    birles = []
    for a0, a1 in aralik:
        if birles and a0 <= birles[-1][1] + tol:
            birles[-1] = (birles[-1][0], max(birles[-1][1], a1))
        else:
            birles.append((a0, a1))
    t = 0.3 * h
    c = 0.58 * h
    d = 1.0 if uc else -1.0
    dolu = _yazi_kutulari(msp)
    alan = (gk[0] - 10 * h, gk[1] - 10 * h, gk[2] + 10 * h, gk[3] + 10 * h)
    cizgi = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    for a0, a1 in sorted(birles, key=lambda q: -(q[1] - q[0])):
        if a1 - a0 < 2.4 * t:
            continue
        adim = max(0.5 * h, (a1 - a0) / 200.0)
        n_ = int((a1 - a0 - 2.4 * t) / adim) + 1
        paylar = [0.86, 0.14, 0.68, 0.32, 0.5] + sorted(
            (i_ / max(1, n_ - 1) for i_ in range(n_)),
            key=lambda q: min(abs(q - 0.86), abs(q - 0.14)))
        for pay in paylar:
            m = a0 + 1.2 * t + pay * (a1 - a0 - 2.4 * t)
            if yon == "yatay":
                taban = ((v, m - t), (v, m + t))
                ucu = (v + d * 1.6 * t, m)
                mrk = (ucu[0] + d * (c + 0.3 * h), m)
            else:
                taban = ((m - t, v), (m + t, v))
                ucu = (m, v + d * 1.6 * t)
                mrk = (m, ucu[1] + d * (c + 0.3 * h))
            if _datum_yeri_bos(msp, taban, ucu, mrk, c, h, dolu, cizgi):
                _datum_simge(msp, taban, ucu, mrk, yon, d, c, harf, h)
                return True
    return False


def _datum_uzantiya(msp, gk, yon, uc, v, harf, h):
    """Datum seviyesi görünüşte düz bir çizgi değilse (eksen ya da gizli
    yüz): seviyenin uzantısına, görünüşün dışına ince çizgi + simge."""
    t = 0.3 * h
    c = 0.58 * h
    dolu = _yazi_kutulari(msp)
    alan = (gk[0] - 14 * h, gk[1] - 14 * h, gk[2] + 14 * h, gk[3] + 14 * h)
    cizgi = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    for taraf in (1, 0):
        for boy in (2.0, 3.5, 5.0, 7.0):
            if yon == "yatay":     # düşey seviye çizgisi: görünüşün üstüne / altına uzar
                y0 = gk[3] + 0.5 * h if taraf else gk[1] - 0.5 * h
                y1 = y0 + (boy * h if taraf else -boy * h)
                d = 1.0 if uc else -1.0
                taban = ((v, y1 - (t if taraf else -t) * 2.2), (v, y1))
                m = (taban[0][1] + taban[1][1]) / 2
                taban = ((v, m - t), (v, m + t))
                ucu = (v + d * 1.6 * t, m)
                mrk = (ucu[0] + d * (c + 0.3 * h), m)
                uz = ((v, y0), (v, y1))
            else:
                x0 = gk[2] + 0.5 * h if taraf else gk[0] - 0.5 * h
                x1 = x0 + (boy * h if taraf else -boy * h)
                d = 1.0 if uc else -1.0
                m = x1 - (t * 1.2 if taraf else -t * 1.2)
                taban = ((m - t, v), (m + t, v))
                ucu = (m, v + d * 1.6 * t)
                mrk = (m, ucu[1] + d * (c + 0.3 * h))
                uz = ((x0, v), (x1, v))
            uzk = (min(uz[0][0], uz[1][0]), min(uz[0][1], uz[1][1]),
                   max(uz[0][0], uz[1][0]), max(uz[0][1], uz[1][1]))
            if _cakisiyor(uzk, dolu, 0.2 * h):
                continue
            if _datum_yeri_bos(msp, taban, ucu, mrk, c, h, dolu, cizgi):
                msp.add_line(uz[0], uz[1], dxfattribs={"layer": "OLCU"})
                _datum_simge(msp, taban, ucu, mrk, yon, d, c, harf, h)
                return True
    return False


def _datum_ciz(msp, gk, yon, uc, harf, h):
    """Tek datum simgesi.

    Yeri TAHMİN EDİLMEZ: simgenin kaplayacağı yer hesaplanır, resimde
    ölçülmüş olan her şeyle karşılaştırılır, çakışıyorsa kenar boyunca
    kaydırılıp yeniden denenir. Ölçü çizgileri de aynı kenardan
    çıkıyor - üstlerine basmasın."""
    # Üçgenin TABANI datum yüzeyinin çizgisine oturur; varlık kutusuyla
    # bakmak her yeri dolu gösterirdi. Bakılacak olan yazılardır.
    dolu = _yazi_kutulari(msp)
    cizgi_ = _cizgi_parcalari(msp, (gk[0] - 10 * h, gk[1] - 10 * h, gk[2] + 10 * h, gk[3] + 10 * h),
                              katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    # Simge ölçü yazısından KÜÇÜK olmalı; ilk sürümde çerçeve 1,2 h,
    # üçgen 1,2 h tabanlıydı - küçük görünüşte (C profilin kesiti)
    # görünüşün kendisi kadar yer tutuyordu. Kullanıcı: "referans yüzey
    # işaretini küçült". Harf 0,72 h kalır: kâğıtta okunur en küçük yazı
    # sınırının (pf4_pafta.EN_AZ_YAZI_MM) altına inmesin.
    t = 0.3 * h                        # üçgenin yarı tabanı
    c = 0.58 * h                       # harf çerçevesinin yarısı (harf 0,72 h rahat sığsın)
    d = 1.0 if uc else -1.0            # parçadan DIŞARI bakan yön
    # Ölçü rakamları ölçünün ORTASINDA durur; simge kenarın uçlarına
    # yakın dursun ki ilk denemede yerini bulsun.
    for pay in (0.86, 0.14, 0.68, 0.32, 0.5):
        if yon == "yatay":             # düşey kenar -> simge yanda
            x = gk[2] if uc else gk[0]
            y = gk[1] + pay * (gk[3] - gk[1])
            taban = ((x, y - t), (x, y + t))
            ucu = (x + d * 1.6 * t, y)
            mrk = (ucu[0] + d * (c + 0.3 * h), y)
        else:                          # yatay kenar -> simge altta/üstte
            y = gk[3] if uc else gk[1]
            x = gk[0] + pay * (gk[2] - gk[0])
            taban = ((x - t, y), (x + t, y))
            ucu = (x, y + d * 1.6 * t)
            mrk = (x, ucu[1] + d * (c + 0.3 * h))
        nokta = [taban[0], taban[1], ucu,
                 (mrk[0] - c, mrk[1] - c), (mrk[0] + c, mrk[1] + c)]
        kutu_ = (min(q[0] for q in nokta), min(q[1] for q in nokta),
                 max(q[0] for q in nokta), max(q[1] for q in nokta))
        cerc = (mrk[0] - c, mrk[1] - c, mrk[0] + c, mrk[1] + c)
        if _cakisiyor(kutu_, dolu, 0.2 * h) or _cizgi_kesiyor(cerc, cizgi_, 0.15 * h):
            continue
        msp.add_solid([taban[0], taban[1], ucu],
                      dxfattribs={"layer": "OLCU"})
        ic = (mrk[0] - d * c, mrk[1]) if yon == "yatay" else (mrk[0], mrk[1] - d * c)
        msp.add_line(ucu, ic, dxfattribs={"layer": "OLCU"})
        msp.add_lwpolyline(
            [(mrk[0] - c, mrk[1] - c), (mrk[0] + c, mrk[1] - c),
             (mrk[0] + c, mrk[1] + c), (mrk[0] - c, mrk[1] + c)],
            close=True, dxfattribs={"layer": "OLCU"})
        e = _yaz(msp, harf, mrk[0], mrk[1], 0.72 * h, kat="OLCU")
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
        # yalnız görünen kontur değil: gizli, eksen, ölçü ve kılavuz
        # çizgileri de (P15: "5,5" bir gizli çizginin üstündeydi)
        kont = _cizgi_parcalari(msp, (gk[0] - pay_k, gk[1] - pay_k,
                                      gk[2] + pay_k, gk[3] + pay_k),
                                katman=("GORUNEN", "GIZLI", "EKSEN", "OLCU", "BOLGE"))
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
                        or _cizgi_kesiyor(ky, kont, 0.1 * h)
                        or _kendi_ustunde(dim, ky, h)
                        or _dim_yaziya_degiyor(dim, dolu, 0.1 * h)):
                    if ky:
                        dolu.append(ky)
                    yazili[dik].add(round(der, 1))
                    sayi += 1
                    break
                _olcu_sil(msp, dim)
    return sayi


def _icinde(q, b, pay=0.0):
    """q noktası b kutusunun (x0, y0, x1, y1) içinde mi?"""
    return (b[0] - pay <= q[0] <= b[2] + pay) and (b[1] - pay <= q[1] <= b[3] + pay)


KOSU_ARA = 1.3        # ortak hattaki iki rakamın eksenleri arası en az (yazı boyu katı)
KOSU_YAZI_PAY = 0.8   # rakamın hatta yakın ucu (uzatma çizgisi 0,6 h taşar)
# ------------------------------------------------------------ ANAYASA
# Ölçülendirmenin sayısal standardı: Chevalier (Guide du dessinateur
# industriel), "La cotation" (NF P 02-001) ve "Règles de cotation" ders
# notları - kullanıcı: "bu kitaplar bizim anayasamız, her ölçü bunlara göre
# şekillenecek". Değerler KÂĞIT mm'sidir (A3, yazı 3,5 mm); DXF 1:1'de yazı
# boyu parçaya göre değiştiği için hepsi YAZI BOYUNUN KATI olarak uygulanır
# (3,5 mm yazıda birebir kitap değeri). Tek yerden okunur; kitap değeri
# değişirse yalnız burası değişir. Bkz. OLCULENDIRME_KURALLARI.md.
ANAYASA = {
    "yazi_mm": 3.5,          # rakam yüksekliği (CH s.3; La cotation 2,5-5 -> 3,5)
    "yazi_en_az_mm": 2.5,    # kâğıtta bunun altı "karınca duası" (La cotation s.3)
    "ok_mm": 3.0,            # ok boyu 3-5 (La cotation s.4), açıklık 30° (CH s.3)
    "ok_aci": 30,
    "uzatma_bosluk_mm": 1.5, # uzatma çizgisi konturdan açık başlar: La cotation 2-5, Règles ~1, ISO ~1 -> 1,5
    "uzatma_tasma_mm": 2.0,  # uzatma çizgisi ölçü çizgisini ~2 mm aşar (Règles s.4; CH 1-2)
    "ilk_hat_mm": 10.0,      # ilk ölçü çizgisi görünüşe 10 mm (La cotation s.3)
    "hat_adim_mm": 8.0,      # paralel ölçü çizgileri arası 7-10 mm (La cotation s.3)
    "kilavuz_bosluk_mm": 1.0,
    "kilavuz_aci": (30, 45, 60),  # kılavuz eğimi (Règles s.11)
}


def _k(ad):
    """ANAYASA değeri, yazı boyunun katı olarak (3,5 mm yazı bazı)."""
    return ANAYASA[ad] / ANAYASA["yazi_mm"]


KOSU_ILK = _k("ilk_hat_mm")      # ilk ölçü hattı parçadan bu kadar yazı boyu uzakta (10 mm)
KOSU_ADIM = _k("hat_adim_mm")    # ölçü hatları arası (8 mm)


def _yay(istek, ara, alt=None, ust=None):
    """Tek eksende rakam yerleri: her biri istediği yere en yakın, ikisi
    arası en az `ara`. Sıkışan rakamlar kümelenip kümenin ortasına göre
    iki yana açılır (etiket yerleştirme)."""
    n = len(istek)
    if not n:
        return []
    sira = sorted(range(n), key=lambda i: istek[i])
    kume = []                                  # [ilk, adet, merkez]
    for i in sira:
        kume.append([len(kume) and 0, 1, istek[i], [i]])
        while len(kume) > 1:
            a, b = kume[-2], kume[-1]
            a_son = a[2] + (a[1] - 1) * ara / 2.0
            b_ilk = b[2] - (b[1] - 1) * ara / 2.0
            if b_ilk - a_son >= ara - 1e-9:
                break
            # birleşen kümenin merkezi: istenen yerlerin ortalaması
            uye = a[3] + b[3]
            m = sum(istek[j] for j in uye) / len(uye)
            kume[-2:] = [[0, len(uye), m, uye]]
    yer = [0.0] * n
    for _i, adet, m, uye in kume:
        bas = m - (adet - 1) * ara / 2.0
        if alt is not None and bas < alt:
            bas = alt
        if ust is not None and bas + (adet - 1) * ara > ust:
            bas = max(alt if alt is not None else -1e18, ust - (adet - 1) * ara)
        for k, j in enumerate(sorted(uye, key=lambda j: istek[j])):
            yer[j] = bas + k * ara
    # kaydırılan sınır yüzünden kümeler yine çakışmış olabilir: ileri geçiş
    sira = sorted(range(n), key=lambda i: yer[i])
    for p, q in zip(sira, sira[1:]):
        if yer[q] < yer[p] + ara:
            yer[q] = yer[p] + ara
    return yer


def _dim_kutusu(dim):
    """Çizilmiş ölçünün TÜM çizgi ve yazılarının sınırı."""
    try:
        k = ezdxf.bbox.extents(list(dim.dimension.virtual_entities()), fast=True)
        if k.has_data:
            return (k.extmin.x, k.extmin.y, k.extmax.x, k.extmax.y)
    except Exception:
        pass
    return None


def _dim_cizgileri(dim):
    """Ölçünün kendi çizgi parçaları (uzatma, ölçü çizgisi, kılavuz)."""
    out = []
    kl = getattr(dim, "_kilavuz", None)
    if kl is not None:
        out.append(((kl.dxf.start.x, kl.dxf.start.y), (kl.dxf.end.x, kl.dxf.end.y)))
    try:
        for v in dim.dimension.virtual_entities():
            if v.dxftype() == "LINE":
                out.append(((v.dxf.start.x, v.dxf.start.y), (v.dxf.end.x, v.dxf.end.y)))
            elif v.dxftype() == "ARC":
                # açı ölçüsünün yayı ve rakama uzanan UZATMA YAYLARI da
                # çizgidir: 60°'lik uzatma yayı komşu yazıların içinden
                # geçiyordu (Karluna P16, tente P46)
                c, r = v.dxf.center, v.dxf.radius
                a0 = math.radians(v.dxf.start_angle)
                sw = math.radians((v.dxf.end_angle - v.dxf.start_angle) % 360.0)
                n = max(2, int(math.degrees(sw) / 10.0) + 1)
                pts = [(c.x + r * math.cos(a0 + sw * i / n), c.y + r * math.sin(a0 + sw * i / n))
                       for i in range(n + 1)]
                out.extend(zip(pts, pts[1:]))
    except Exception:
        pass
    return out


def _kendi_ustunde(dim, ky, h):
    """Ölçünün rakamı KENDİ uzatma çizgisinin üstünde mi? (Rakam iki uzatma
    çizgisi arasına sığmayıp ortada kalınca çizgiler rakamı keser.)"""
    if not ky:
        return False
    k = (ky[0] + 0.05 * h, ky[1] + 0.05 * h, ky[2] - 0.05 * h, ky[3] - 0.05 * h)
    return any(_parca_kutuda(a, b, k) for a, b in _dim_cizgileri(dim))


def _ust_uste(dim, cizgi, h):
    """Ölçünün (ya da kılavuzun) bir çizgisi mevcut bir çizginin TAM
    ÜSTÜNDE mi: paralel, aralarında 0,15 h'den az, üst üste binen boy
    0,5 h'den fazla. (P10: "8x Ø5,3" kılavuzu 32,5'in uzatma çizgisinin
    üstünde yatıyordu.)"""
    for a, b in _dim_cizgileri(dim):
        L = math.dist(a, b)
        if L < 1e-9:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        for c, d in cizgi:
            L2 = math.dist(c, d)
            if L2 < 1e-9:
                continue
            if abs(ux * (d[1] - c[1]) - uy * (d[0] - c[0])) / L2 > 0.02:
                continue                  # paralel değil
            if abs((c[0] - a[0]) * uy - (c[1] - a[1]) * ux) > 0.15 * h:
                continue                  # aynı doğru üstünde değil
            t1 = (c[0] - a[0]) * ux + (c[1] - a[1]) * uy
            t2 = (d[0] - a[0]) * ux + (d[1] - a[1]) * uy
            if min(L, max(t1, t2)) - max(0.0, min(t1, t2)) > 0.5 * h:
                return True
    return False


def _dim_yaziya_degiyor(dim, dolu, pay=0.0):
    """Ölçünün bir ÇİZGİSİ (uzatma ya da ölçü çizgisi) bir yazının
    üstünden geçiyor mu? Görünüş adı ("ÖN") da bir yazıdır."""
    for a, b in _dim_cizgileri(dim):
        for k in dolu:
            if _parca_kutuda(a, b, (k[0] - pay, k[1] - pay, k[2] + pay, k[3] + pay)):
                return True
    return False


def _kosu_ciz(msp, yon, p1, p2, cizgi, yazi, h, metin=None):
    """Ortak başlangıçlı (running, ISO 129-1) hattın TEK ölçüsü.

    p1 datum noktası (başlangıç dairesi), p2 özelliğin noktası: uzatma
    çizgisi özelliğin kendisinden başlar, ölçü hattına kadar iner.
    Rakam uzatma çizgisine paralel, ölçü hattının dışında, `yazi`
    noktasını merkez alır."""
    metin = "<>" if metin is None else metin
    ovr = {"dimsah": 1, "dimblk1": "ORIGIN", "dimblk2": "", "dimtmove": 2,
           "dimtix": 0, "dimtofl": 0}
    try:
        if yon == "yatay":
            dim = msp.add_linear_dim(
                base=(0, cizgi), p1=p1, p2=p2, location=yazi, text=metin,
                dimstyle=OLCU_STILI, override=ovr,
                dxfattribs={"layer": "OLCU", "text_rotation": 90.0})
        else:
            dim = msp.add_linear_dim(
                base=(cizgi, 0), p1=p1, p2=p2, angle=90, location=yazi,
                text=metin, dimstyle=OLCU_STILI, override=ovr,
                dxfattribs={"layer": "OLCU", "text_rotation": 0.0})
        dim.render()
        return dim
    except Exception:
        return None


# Detay görünüşünde büyütülmüş geometriye konan ölçülerin ölçek çarpanı
# (dimlfac = 1 / büyütme): ölçü GERÇEK değeri yazar.
_EK_OVR = {}


def _ara_ciz(msp, yon, p1, p2, cizgi, h, metin=None, sik=False):
    """Ortak hattın dışında kalan iki uçlu ölçü (dizi adımı, slot boyu).

    sik=True: DAR ZİNCİR ölçüsü - ok yerine NOKTA, ölçü çizgisi iki
    uzatma çizgisinin arasında kalır, dışarı kuyruk çıkmaz (Chevalier:
    sıkışık zincirde oklar noktayla değiştirilir). Kısa ölçünün dışarı
    taşan ok kuyruğu komşu ölçünün rakamına giriyordu (P06 SAĞ: 31,7
    kanatları hizadan çıkıp dışarı itiliyordu)."""
    metin = "<>" if metin is None else metin
    ovr = dict({"dimtoh": 1, "dimtih": 1, "dimtmove": 1, "dimatfit": 3}, **_EK_OVR)
    if sik:
        ovr.update({"dimblk": "DOTSMALL", "dimtofl": 1, "dimsoxd": 1})
    try:
        if yon == "yatay":
            dim = msp.add_linear_dim(base=(0, cizgi), p1=p1, p2=p2, text=metin,
                                     dimstyle=OLCU_STILI, override=ovr,
                                     dxfattribs={"layer": "OLCU"})
        else:
            dim = msp.add_linear_dim(base=(cizgi, 0), p1=p1, p2=p2, angle=90,
                                     text=metin, dimstyle=OLCU_STILI, override=ovr,
                                     dxfattribs={"layer": "OLCU"})
        dim.render()
        return dim
    except Exception:
        return None


def _taraf_sec(kayitlar, lo, hi):
    """Her datum ölçüsü görünüşün hangi yanına: özelliğe YAKIN olan yana
    (uzatma çizgisi kısa, ölçü gösterdiği yerin dibinde). Bir yan öbürünün
    iki katından kalabalıksa ortaya en yakın olanlar karşı yana geçer -
    ölçüler iki yana DENGELİ dağılır. Referans değişmez: hepsi datumdan."""
    fark = []
    for r in kayitlar:
        d = r.get("dik") or []
        if not d:
            r["_taraf"] = 0
            fark.append(-1e18)
            continue
        dl = min(abs(v - lo) for v in d)
        dh = min(abs(hi - v) for v in d)
        r["_taraf"] = 0 if dl <= dh else 1
        fark.append(dl - dh)
    n = len(kayitlar)
    for _ in range(n):
        n1 = sum(r["_taraf"] for r in kayitlar)
        n0 = n - n1
        cok, az = (0, 1) if n0 > n1 else (1, 0)
        if max(n0, n1) <= 2 * min(n0, n1) + 1:
            break
        # yalnız ORTA BANTTAKİ özellik karşıya geçer: kenara yakın deliğin
        # ölçüsü karşı yana konursa uzatma çizgisi bütün görünüşü keser
        aday = [i for i, r in enumerate(kayitlar) if r["_taraf"] == cok
                and r.get("dik") and abs(fark[i]) <= 0.35 * (hi - lo)]
        if not aday:
            break
        i = min(aday, key=lambda i: abs(fark[i]))
        kayitlar[i]["_taraf"] = az
    return kayitlar


def _engel_sayisi(yon, deger, dik, taraf, lo, hi, engel, pay=0.3):
    """Özellikten (deger, dik) görünüşün taraf yanına giden uzatma
    çizgisi kaç ENGELİN (delik, yuva, pencere kutusu) içinden geçer.
    Özelliğin kendisi ve AYNI SEVİYEDEKİ özellikler (merkezi çizginin
    üstünde) sayılmaz: çizgi onların ekseninden geçer, aynı ölçüdür.
    Ham izdüşüm koordinatında."""
    if not dik or not engel:
        return 0
    i, j = (0, 1) if yon == "yatay" else (1, 0)
    bas = min(dik) if taraf == 0 else max(dik)
    son = lo if taraf == 0 else hi
    s0, s1 = min(bas, son), max(bas, son)
    n = 0
    for b in engel:
        if not (b[i] + pay < deger < b[i + 2] - pay):
            continue                   # çizgi kutunun yanından geçiyor
        if abs((b[i] + b[i + 2]) / 2.0 - deger) <= pay:
            continue                   # aynı seviye: kendi ekseni
        if b[j] - pay <= bas <= b[j + 2] + pay:
            continue                   # özelliğin kendisi / içinde başlıyor
        if b[j + 2] > s0 and b[j] < s1:
            n += 1
    return n


def konum_olculeri(msp, plan, kaydir, gkutu, h, en_cok_kademe=8, rapor=None,
                   kayip=None):
    """Planı çizer ve YERİNİ ÖLÇEREK doğrular.

    ORTAK BAŞLANGIÇLI ÖLÇÜ (ISO 129-1 "superimposed running
    dimensioning"): datumdan verilen bütün konumlar görünüşün bir
    yanında TEK bir ölçü hattında toplanır. Başlangıçta küçük daire
    (datum), her özellikte bir ok, rakam uzatma çizgisinin ucunda ona
    paralel. Eski yöntemde her ölçü ayrı bir kademeydi: 13 konum 13 iç
    içe çizgi demekti, hangi rakamın hangi deliğe ait olduğu seçilmiyordu
    (kullanıcı: "ölçüler birbiri üstüne gelmiş").

    YAN SEÇİMİ: her ölçü özelliğe yakın yana konur (üstteki delik üstte,
    sağdaki sağda) ve iki yan dengelenir. Referans DEĞİŞMEZ; üstteki
    hat da alttaki de aynı datumdan başlar. Uzatma çizgisi özelliğin
    kendisinden başlar - ölçü gösterdiği noktaya ulaşır.

    Rakamlar sıkışırsa hat boyunca iki yana açılır, rakamla ok arasına
    ince bir kılavuz çizilir. Yer yine ÖLÇÜLÜR: rakam başka bir yazıya,
    başka bir görünüşe değiyorsa hat dışarı kaydırılır, olmuyorsa o
    ölçü öbür yana geçer; orada da yer yoksa yazılmaz (rapora sayılır)
    - üst üste binen ölçü, olmayan ölçüden kötüdür.

    Döner: {gorunus: (en_alt_y, en_sol_x)} - gabari ölçüsü bunların
    DIŞINA konacak."""
    sinir = {}
    for gad, pl in plan.items():
        if gad not in gkutu:
            continue
        dx, dy = kaydir[gad]
        gk = gkutu[gad]
        for sl in pl.get("slot") or []:
            (x1, y1), (x2, y2), r = sl["c1"], sl["c2"], sl["r"]
            L = math.hypot(x2 - x1, y2 - y1) or 1.0
            ux, uy = (x2 - x1) / L, (y2 - y1) / L
            u = r + max(1.5, 0.4 * h)
            msp.add_line((x1 - ux * u + dx, y1 - uy * u + dy),
                         (x2 + ux * u + dx, y2 + uy * u + dy), dxfattribs={"layer": "EKSEN"})
            for cx, cy in ((x1, y1), (x2, y2)):
                msp.add_line((cx - uy * u + dx, cy + ux * u + dy),
                             (cx + uy * u + dx, cy - ux * u + dy), dxfattribs={"layer": "EKSEN"})
        yabanci = [(k[0] - 0.3 * h, k[1] - 0.3 * h, k[2] + 0.3 * h, k[3] + 0.3 * h)
                   for g, k in gkutu.items() if g != gad]
        kutu_ = pl.get("kutu")
        sonra = []
        for yon, kayd, dkay in (("yatay", dx, dy), ("dusey", dy, dx)):
            kay = pl.get(yon) or []
            if not kay:
                continue
            dat = (pl.get("datum") or {}).get(yon)
            if kutu_:
                lo, hi = (kutu_[1], kutu_[3]) if yon == "yatay" else (kutu_[0], kutu_[2])
            else:
                lo, hi = ((gk[1] - dkay, gk[3] - dkay) if yon == "yatay"
                          else (gk[0] - dkay, gk[2] - dkay))
            kosu = [r for r in kay if r.get("kosu") and dat is not None]
            ara_ = [r for r in kay if r not in kosu]
            _taraf_sec(kosu, lo, hi)
            # Uzatma çizgisi delik / yuva / pencere üstünden geçiyorsa
            # temiz olan öbür yana alınır.
            engel = pl.get("engel") or []
            for r in kosu:
                c_ = [_engel_sayisi(yon, r["deger"], r.get("dik"), t_, lo, hi, engel)
                      for t_ in (0, 1)]
                r["_engel"] = c_
                t_ = r["_taraf"]
                if c_[t_] > 0 and c_[1 - t_] < c_[t_]:
                    r["_taraf"] = 1 - t_
            for r in ara_:
                d = r.get("dik") or []
                r["_taraf"] = (0 if not d or min(abs(v - lo) for v in d)
                               <= min(abs(hi - v) for v in d) else 1)
            # Her yan TEK hattır: bir yanda yer bulamayan ölçü öbür yana
            # geçer ve o yan BÜTÜN listesiyle yeniden çizilir (ikinci bir
            # hat açılmaz).
            # DIŞ ZİNCİRE GİRMEYENLER - özelliğin YANINDA verilir
            # (kullanıcı: "ölçü çizgileri zorunlu olmadıkça form, delik,
            # şekil üzerinden geçmemeli; deliklere sağdan soldan çizgi
            # gelmesin"):
            #   1. uzatma çizgisi İKİ yanda da bir deliği / yuvayı kesiyor,
            #   2. zincir halkası rakamın yarısından kısa (Televre P04'ün
            #      "3"ü: neredeyse aynı hizadaki iki özellik - dış hatta
            #      okunmuyor, anlamsız görünüyor). Bu, zincir ÇİZİLİRKEN
            #      gerçek sıraya göre denetlenir (bkz. _kosu_dene).
            yerel = [r for r in kosu if min(r.get("_engel") or [0, 0]) > 0]
            liste_ = {0: [r for r in kosu if r["_taraf"] == 0 and r not in yerel],
                      1: [r for r in kosu if r["_taraf"] == 1 and r not in yerel]}
            cizim = {0: [], 1: []}
            tamam = {0: False, 1: False}
            gecti = set()
            dusen = []
            for _tur in range(4):
                if tamam[0] and tamam[1]:
                    break
                for taraf in (0, 1):
                    if tamam[taraf]:
                        continue
                    _kosu_geri_al(msp, cizim[taraf])
                    cizim[taraf], kalan = ([], []) if not liste_[taraf] else _kosu_hatti(
                        msp, yon, taraf, liste_[taraf], dat, kayd, dkay, gk, h, yabanci)
                    tamam[taraf] = True
                    for r in kalan:
                        liste_[taraf].remove(r)
                        if r.get("_kisa"):
                            yerel.append(r)      # kısa halka: detaya
                            continue
                        if id(r) in gecti:
                            if rapor is not None:
                                rapor["yer_yok"] += 1
                            dusen.append(r)
                            continue
                        gecti.add(id(r))
                        liste_[1 - taraf].append(r)
                        tamam[1 - taraf] = False
            # Yer bulamayan datum ölçüsü DETAY GÖRÜNÜŞÜNE gider: orada, çizilmiş
            # en yakın komşusundan (ya da datumdan) ölçülür.
            cizilmis = liste_[0] + liste_[1]
            if rapor is not None:
                rapor["yer_yok"] += len(yerel)     # yerleşince aşağıda düşülür
            dusen = yerel + dusen
            for r in dusen:
                # Komşu, resimde EN YAKIN ölçülü özellik (2B uzaklık): değerce
                # en yakın seviye parçanın öbür ucunda olabiliyordu (Televre
                # P04: 191'deki delik x=2408'de, kayıp 222,5 x=760'ta) - yanına
                # konan ölçü de detay dairesi de bütün parçayı kaplıyordu.
                rd = list(r.get("dik") or [])
                ad_ = [(abs(dat - r["deger"]), dat, [])]
                for q in cizilmis:
                    qd = list(q.get("dik") or [])
                    if not qd or not rd or abs(q["deger"] - r["deger"]) < 1e-6:
                        continue
                    pq = min(((u, w) for u in qd for w in rd), key=lambda t: abs(t[0] - t[1]))
                    ad_.append((math.hypot(q["deger"] - r["deger"], pq[0] - pq[1]),
                                q["deger"], [pq[0]]))
                _d, dv, dd = min(ad_, key=lambda t: t[0])
                # KARIŞIK BÖLGE -> DETAY (kullanıcı: "bu tarz karışıklıkları
                # hep detay görünüşlere taşı"): uzatma çizgisi iki yanda da
                # şekil kesen ya da çok kısa halkalı ölçü ana görünüşe hiç
                # konmaz; detayda verilir (detay kurulamazsa orada özelliğin
                # yanına konur, bkz. detay_gorunusleri).
                if kayip is not None:
                    kayip.append({"gad": gad, "yon": yon, "a": dv, "b": r["deger"],
                                  "dik_a": dd or list(r.get("dik") or []),
                                  "dik_b": list(r.get("dik") or []), "metin": None,
                                  "kayd": kayd, "dkay": dkay})
                    continue
                # DIŞARIDAN yer yok: özelliğin YANINDA, en yakın ölçülü
                # komşusundan (kullanıcı: "deliğin yanından ver, illa en
                # dıştan verme")
                if _yanina_koy(msp, yon, dv, r["deger"], dd or list(r.get("dik") or []),
                               list(r.get("dik") or []), None, kayd, dkay, h, yabanci):
                    if rapor is not None:
                        rapor["yer_yok"] -= 1
                    continue
                # Son çare (detaydan önce): REFERANSTAN PARALEL ölçü (0 -> B),
                # hattın dışında ayrı bir kademede - yalnız uzatma çizgisi
                # hiçbir deliğin / yuvanın üstünden geçmeyen yandan.
                paralel = False
                for t_ in sorted((0, 1), key=lambda t: (r.get("_engel") or [0, 0])[t]):
                    if (r.get("_engel") or [0, 0])[t_] > 0:
                        continue
                    rr = {"a": dat, "b": r["deger"], "metin": None,
                          "dik": list(r.get("dik") or []), "_taraf": t_}
                    if _ara_yerlestir_yan(msp, yon, rr, t_, kayd, dkay, gk, h,
                                          yabanci, en_cok_kademe):
                        paralel = True
                        break
                if paralel:
                    if rapor is not None:
                        rapor["yer_yok"] -= 1
                    continue
                if kayip is not None:
                    kayip.append({"gad": gad, "yon": yon, "a": dv, "b": r["deger"],
                                  "dik_a": dd or list(r.get("dik") or []),
                                  "dik_b": list(r.get("dik") or []), "metin": None,
                                  "kayd": kayd, "dkay": dkay})
            sonra.append((yon, kayd, dkay, ara_))
        # İKİ YÖNÜN ZİNCİRLERİ konduktan SONRA iki uçlu ölçüler (dizi adımı,
        # slot boyu, delik grubu içi): önce konsalardı zincirin uzatma
        # çizgileri onların rakamlarından geçemediği için düşüyordu (P06'da
        # 149'daki sıranın yüksekliği). Grup içi olanlar önce grubun YANINA.
        for yon, kayd, dkay, ara_ in sonra:
            for r in ara_:
                if r.get("lokal") and _lokal_yerlestir(msp, yon, r, kayd, dkay, h, yabanci):
                    continue
                if not _ara_yerlestir(msp, yon, r, kayd, dkay, gk, h, yabanci,
                                      en_cok_kademe):
                    if _yanina_koy(msp, yon, r["a"], r["b"],
                                   list(r.get("dik_a") or r.get("dik") or []),
                                   list(r.get("dik_b") or r.get("dik") or []),
                                   r.get("metin"), kayd, dkay, h, yabanci):
                        continue       # özelliğin yanına kondu
                    if rapor is not None:
                        rapor["yer_yok"] += 1
                    if kayip is not None:
                        kayip.append({"gad": gad, "yon": yon, "a": r["a"], "b": r["b"],
                                      "dik_a": list(r.get("dik_a") or r.get("dik") or []),
                                      "dik_b": list(r.get("dik_b") or r.get("dik") or []),
                                      "metin": r.get("metin"), "kayd": kayd, "dkay": dkay})
    # sınırlar: her görünüşün KENDİ ölçüleri altında / solunda ne kadar
    # yer tuttu (ölçünün iki ucu o görünüşün içindeyse onundur)
    for gad, gk in gkutu.items():
        alt, sol = gk[1], gk[0]
        p_ = 0.01 * h + 1e-3
        for e in msp.query("DIMENSION"):
            try:
                u1, u2 = e.dxf.defpoint2, e.dxf.defpoint3
            except Exception:
                continue
            if not (_icinde((u1.x, u1.y), gk, p_) and _icinde((u2.x, u2.y), gk, p_)):
                continue
            k = _dim_kutusu(type("D", (), {"dimension": e})())
            if not k:
                continue
            if k[1] < gk[1]:
                alt = min(alt, k[1])
            if k[0] < gk[0]:
                sol = min(sol, k[0])
        sinir[gad] = (alt, sol)
    return sinir


def _kosu_hatti(msp, yon, taraf, liste, dat, kayd, dkay, gk, h, yabanci):
    """Bir yanın ortak başlangıçlı hattı. Döner: (çizilenler, sığmayanlar).

    Hat görünüşe en yakın kademeden başlayarak dışarı doğru denenir; ilk
    hepsinin sığdığı kademe kullanılır. Hiçbirinde hepsi sığmıyorsa en
    çoğunun sığdığı kademede sığmayanlar çıkarılıp yeniden çizilir."""
    liste = sorted(liste, key=lambda r: abs(r["deger"] - dat))
    en_iyi = None
    for k in range(7):
        cizilen, olmadi = _kosu_dene(msp, yon, taraf, liste, dat, kayd, dkay, gk, h, yabanci, k)
        if not olmadi:
            return cizilen, [r for r in liste if r.get("_kisa")]
        if en_iyi is None or len(cizilen) > en_iyi[0]:
            en_iyi = (len(cizilen), k)
        _kosu_geri_al(msp, cizilen)
    if not en_iyi or not en_iyi[0]:
        return [], list(liste)
    k = en_iyi[1]
    kalan, atilan = list(liste), []
    for _ in range(len(liste)):
        cizilen, olmadi = _kosu_dene(msp, yon, taraf, kalan, dat, kayd, dkay, gk, h, yabanci, k)
        if not olmadi:
            return cizilen, atilan + [r for r in kalan if r.get("_kisa")]
        _kosu_geri_al(msp, cizilen)
        atilan.extend(olmadi)
        kalan = [r for r in kalan if r not in olmadi]
        if not kalan:
            break
    return [], atilan + kalan


def _kosu_geri_al(msp, cizilen):
    for _r, dim, kl in cizilen:
        _olcu_sil(msp, dim)
        if kl is not None:
            msp.delete_entity(kl)


def _kosu_dene(msp, yon, taraf, liste, dat, kayd, dkay, gk, h, yabanci, k):
    """k. kademedeki hatta ZİNCİR ölçü: referanstan ilk özelliğe, sonra her
    ölçü bir öncekinden (kullanıcı: "referanstan başlar, sonra ondan ona
    devam"). Rakam iki okun ortasında; sığmıyorsa hattın dışına kayar,
    kılavuzla bağlanır. Döner: (çizilen, sığmayan)."""
    yatay = yon == "yatay"
    disa = -1.0 if taraf == 0 else 1.0
    if yatay:
        kenar = gk[1] if taraf == 0 else gk[3]
    else:
        kenar = gk[0] if taraf == 0 else gk[2]
    cizgi = kenar + disa * (KOSU_ILK + KOSU_ADIM * k) * h
    dolu = _yazi_kutulari(msp)
    if yatay:
        alan = (gk[0] - 6 * h, min(cizgi, kenar) - 8 * h, gk[2] + 6 * h, max(cizgi, kenar) + 8 * h)
    else:
        alan = (min(cizgi, kenar) - 8 * h, gk[1] - 6 * h, max(cizgi, kenar) + 8 * h, gk[3] + 6 * h)
    cizgiler = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    cizilen, olmadi = [], []
    onceki = (dat + kayd, kenar)          # (değer, uzatma çizgisinin başladığı yer)
    for r in liste:
        r.pop("_kisa", None)
    for r in liste:
        x = r["deger"] + kayd
        # KISA HALKA dış zincire girmez (rakamın yarısından kısa: neredeyse
        # aynı hizadaki iki özellik, Televre P04'ün "3"ü) - detayda verilir
        if abs(x - onceki[0]) < KISA_HALKA * h:
            r["_kisa"] = True
            continue
        d = r.get("dik") or []
        dk = ((min(d) if taraf == 0 else max(d)) + dkay) if d else kenar
        if yatay:
            p1, p2 = (onceki[0], onceki[1]), (x, dk)
        else:
            p1, p2 = (onceki[1], onceki[0]), (dk, x)
        dim, ky = None, None
        # yazı yerleri: önce iki okun ortası, sonra hattın YANINDA ölçünün
        # tam ortası (rakam kendi aralığının hizasında kalır; hat boyunca
        # kaydırılan rakam komşu aralığın hizasına düşüp o aralığın
        # ölçüsü gibi okunuyordu - P06 ÖN sol zincir), en son iki yana
        # DÜŞEY ölçüde rakam yataydır: önce hattın dış yanında, aralığın
        # ortasında - bütün rakamlar hattın AYNI yanında, aynı eksende
        sira_ = ((0.0, None, 1.4, -1.4, 2.8, -2.8) if not yatay
                 else (None, 0.0, 1.4, -1.4, 2.8, -2.8))
        for yer_ in sira_:
            if yer_ is None:
                dim = _ara_ciz(msp, yon, p1, p2, cizgi, h, r.get("metin"))
            else:
                m = (onceki[0] + x) / 2.0 + yer_ * max(abs(x - onceki[0]), 3.0 * h) * 0.5
                dim = _disari_ciz(msp, yon, p1, p2, cizgi, disa, m, h, r.get("metin"))
            ky = _olcu_yazi_kutusu(dim) if dim is not None else None
            kh = _dim_kutusu(dim) if dim is not None else None
            if (dim is not None and ky is not None
                    and _yazi_hizasinda(ky, yon, onceki[0], x, h)
                    and not _cakisiyor(ky, dolu, 0.15 * h) and not _cakisiyor(ky, yabanci)
                    and not _cizgi_kesiyor(ky, cizgiler, 0.1 * h)
                    and not (kh and _cakisiyor(kh, yabanci))
                    and not _kendi_ustunde(dim, ky, h)
                    and not _dim_yaziya_degiyor(dim, dolu, 0.1 * h)):
                break
            if dim is not None:
                _olcu_sil(msp, dim)
            dim = None
        if dim is None:
            olmadi.append(r)
            continue
        dolu.append(ky)
        cizilen.append((r, dim, None))
        onceki = (x, dk)
    return cizilen, olmadi


def _yazi_hizasinda(ky, yon, a, b, h):
    """Rakam KENDİ aralığının hizasında mı? Aralık rakamı alacak kadar
    genişse rakamın ortası aralığın içinde olmalı; yoksa komşu aralığın
    hizasına düşer ve onun ölçüsü gibi okunur (P06 ÖN sol zincir: "14,5"
    103,5'lik aralığın yanında duruyordu). Dar aralıkta (rakam sığmıyor)
    dışarı kılavuzla alınması serbesttir."""
    if not ky:
        return False
    lo, hi = min(a, b), max(a, b)
    i = 0 if yon == "yatay" else 1
    boy = ky[i + 2] - ky[i]
    if hi - lo < boy + 0.6 * h:
        return True
    c = (ky[i] + ky[i + 2]) / 2.0
    return lo <= c <= hi


def _disari_ciz(msp, yon, p1, p2, cizgi, disa, m, h, metin=None):
    """Rakamı ölçü hattının DIŞINA (disa yönünde), hat boyunca m noktasına
    koyar; yazının gerçek genişliği ÖLÇÜLÜR ve yakın kenarı hattan 0,5 h
    uzakta durur (yatay yazı düşey hatta genişliği kadar yer tutar)."""
    yatay = yon == "yatay"
    ofs = cizgi + disa * 1.3 * h
    dim = _zincir_disari(msp, yon, p1, p2, cizgi, (m, ofs) if yatay else (ofs, m), h, metin)
    ky = _olcu_yazi_kutusu(dim) if dim is not None else None
    if not ky:
        return dim
    if yatay:
        yakin = ky[3] if disa < 0 else ky[1]
        kay_ = (cizgi + disa * 0.5 * h) - yakin
        if abs(kay_) > 0.05 * h:
            _olcu_sil(msp, dim)
            dim = _zincir_disari(msp, yon, p1, p2, cizgi, (m, ofs + kay_), h, metin)
    else:
        yakin = ky[2] if disa < 0 else ky[0]
        kay_ = (cizgi + disa * 0.5 * h) - yakin
        if abs(kay_) > 0.05 * h:
            _olcu_sil(msp, dim)
            dim = _zincir_disari(msp, yon, p1, p2, cizgi, (ofs + kay_, m), h, metin)
    # ölçü hattından rakama İNCE KILAVUZ: rakam havada kalmasın
    ky = _olcu_yazi_kutusu(dim) if dim is not None else None
    if dim is not None and ky:
        a_, b_ = (p1[0], p2[0]) if yatay else (p1[1], p2[1])
        lo, hi = min(a_, b_), max(a_, b_)
        if yatay:
            cx = min(max((ky[0] + ky[2]) / 2.0, lo), hi)
            hedef = (min(max(cx, ky[0]), ky[2]), ky[3] if disa < 0 else ky[1])
            bas = (cx, cizgi)
        else:
            cy = min(max((ky[1] + ky[3]) / 2.0, lo), hi)
            hedef = (ky[2] if disa < 0 else ky[0], min(max(cy, ky[1]), ky[3]))
            bas = (cizgi, cy)
        if math.dist(bas, hedef) > 0.3 * h:
            dim._kilavuz = msp.add_line(bas, hedef, dxfattribs={"layer": "OLCU"})
    return dim


def _zincir_disari(msp, yon, p1, p2, cizgi, yazi, h, metin=None):
    """Kısa zincir halkası: rakam okların arasına sığmıyor, hattın dışına
    kılavuzla alınır."""
    metin = "<>" if metin is None else metin
    ovr = dict({"dimtmove": 1, "dimtoh": 1, "dimtih": 1, "dimatfit": 3}, **_EK_OVR)
    try:
        if yon == "yatay":
            dim = msp.add_linear_dim(base=(0, cizgi), p1=p1, p2=p2, location=yazi,
                                     text=metin, dimstyle=OLCU_STILI, override=ovr,
                                     dxfattribs={"layer": "OLCU"})
        else:
            dim = msp.add_linear_dim(base=(cizgi, 0), p1=p1, p2=p2, angle=90,
                                     location=yazi, text=metin, dimstyle=OLCU_STILI,
                                     override=ovr, dxfattribs={"layer": "OLCU"})
        dim.render()
        return dim
    except Exception:
        return None


def _ara_yerlestir(msp, yon, r, kayd, dkay, gk, h, yabanci, en_cok_kademe=8):
    """İki uçlu ölçüyü (dizi adımı, slot boyu) kendi yanında, ortak hattın
    dışında ilk boş kademeye koyar; yeri ölçülür. O yanda yer yoksa ÖBÜR
    yan denenir (P10: "3 x 200 = 600"ün uzatma çizgisi üstteki "23,8"in
    rakamından geçiyordu, alt yan boştu ama ölçü hiç konmuyordu)."""
    taraf0 = r.get("_taraf", 0)
    for taraf in (taraf0, 1 - taraf0):
        if _ara_yerlestir_yan(msp, yon, r, taraf, kayd, dkay, gk, h, yabanci,
                              en_cok_kademe):
            return True
    return False


def _ara_yerlestir_yan(msp, yon, r, taraf, kayd, dkay, gk, h, yabanci, en_cok_kademe):
    yatay = yon == "yatay"
    disa = -1.0 if taraf == 0 else 1.0
    kenar = (gk[1] if taraf == 0 else gk[3]) if yatay else (gk[0] if taraf == 0 else gk[2])
    # o yanda şu an en dıştaki çizim
    en_dis = kenar
    a0_, b0_ = r["a"] + kayd, r["b"] + kayd
    # O yandaki ölçülerin ÖLÇÜ ÇİZGİSİ (defpoint) ve yazısı: uzatma
    # çizgileri görünüşün içinden başladığı için kutuya bakmak yetmez
    for e in msp.query("DIMENSION"):
        try:
            dp = e.dxf.defpoint
        except Exception:
            continue
        ky = _olcu_yazi_kutusu(type("D", (), {"dimension": e})())
        k = _dim_kutusu(type("D", (), {"dimension": e})())
        if not k:
            continue
        # yalnız BU ölçünün boyuyla (± yazı payı) üst üste gelenler: yan
        # yandaki ölçüler aynı kademeyi paylaşabilir (9 slotun "6"sı
        # merdiven gibi aşağı iniyordu)
        pay_ = 4.0 * h
        if yatay and not (k[2] > min(a0_, b0_) - pay_ and k[0] < max(a0_, b0_) + pay_):
            continue
        if not yatay and not (k[3] > min(a0_, b0_) - pay_ and k[1] < max(a0_, b0_) + pay_):
            continue
        if yatay and k[2] > gk[0] and k[0] < gk[2]:
            if taraf == 0 and dp.y < gk[1] - 1e-6:
                en_dis = min(en_dis, dp.y, ky[1] if ky else dp.y)
            elif taraf == 1 and dp.y > gk[3] + 1e-6:
                en_dis = max(en_dis, dp.y, ky[3] if ky else dp.y)
        elif not yatay and k[3] > gk[1] and k[1] < gk[3]:
            if taraf == 0 and dp.x < gk[0] - 1e-6:
                en_dis = min(en_dis, dp.x, ky[0] if ky else dp.x)
            elif taraf == 1 and dp.x > gk[2] + 1e-6:
                en_dis = max(en_dis, dp.x, ky[2] if ky else dp.x)
    a, b = r["a"] + kayd, r["b"] + kayd
    # KÜÇÜK özelliğin ölçüsü görünüşten uzağa itilmez: uzun uzatma
    # çizgileriyle görünüşler arasına sarkıyordu. Sığmazsa DETAY'a gider.
    if abs(b - a) < 3.0 * h:
        en_cok_kademe = min(en_cok_kademe, 2)
    d = r.get("dik") or []
    dk = ((min(d) if taraf == 0 else max(d)) + dkay) if d else kenar
    dolu = _yazi_kutulari(msp)
    if yatay:
        alan = (min(a, b) - 8 * h, min(kenar, en_dis) - 16 * h, max(a, b) + 8 * h, max(kenar, en_dis) + 16 * h)
    else:
        alan = (min(kenar, en_dis) - 16 * h, min(a, b) - 8 * h, max(kenar, en_dis) + 16 * h, max(a, b) + 8 * h)
    parca_ = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    for sev in range(en_cok_kademe):
        cizgi = en_dis + disa * (1.6 + KOSU_ADIM * sev) * h
        if yatay:
            p1, p2 = (a, dk), (b, dk)
        else:
            p1, p2 = (dk, a), (dk, b)
        dim = _ara_dene(msp, yon, p1, p2, cizgi, disa, h, r.get("metin"),
                        dolu, parca_, yabanci)
        if dim is not None:
            return True
    return False


def _ara_dene(msp, yon, p1, p2, cizgi, disa, h, metin, dolu, parca_, yabanci):
    """İki uçlu ölçüyü verilen hatta dener: rakam önce okların ortasında,
    sığmıyorsa hattın dışında iki yana kaydırılmış (kılavuzlu). Rakam hiçbir
    yazıya, çizgiye ve KENDİ uzatma çizgisine değmiyorsa ölçü kalır."""
    yatay = yon == "yatay"
    a, b = (p1[0], p2[0]) if yatay else (p1[1], p2[1])
    sira_ = ((0.0, None, "sik", 1.0, -1.0, 2.0, -2.0) if not yatay
             else (None, 0.0, "sik", 1.0, -1.0, 2.0, -2.0))
    for yer_ in sira_:
        if yer_ is None or yer_ == "sik":
            dim = _ara_ciz(msp, yon, p1, p2, cizgi, h, metin, sik=yer_ == "sik")
        else:
            m = (a + b) / 2.0 + yer_ * (abs(b - a) / 2.0 + 2.5 * h)
            dim = _disari_ciz(msp, yon, p1, p2, cizgi, disa, m, h, metin)
        if dim is None:
            continue
        ky = _olcu_yazi_kutusu(dim)
        kh = _dim_kutusu(dim)
        if (ky and not _cakisiyor(ky, dolu, 0.15 * h) and not _cakisiyor(ky, yabanci)
                and (yer_ in (1.0, -1.0, 2.0, -2.0) or _yazi_hizasinda(ky, yon, a, b, h))
                and not (kh and _cakisiyor(kh, yabanci))
                and not _cizgi_kesiyor(ky, parca_, 0.1 * h)
                and not _kendi_ustunde(dim, ky, h)
                and not _dim_yaziya_degiyor(dim, dolu, 0.1 * h)):
            return dim
        _olcu_sil(msp, dim)
    return None


def _yanina_koy(msp, yon, a, b, dik_a, dik_b, metin, kayd, dkay, h, yabanci):
    """Dışarıda yer bulamayan ölçüyü ÖZELLİKLERİN HEMEN YANINA koyar
    (grup içi ölçü gibi, bkz. _lokal_yerlestir). a, b ham eksen değerleri;
    dik_a / dik_b uçların öbür eksendeki yerleri."""
    if not dik_a or not dik_b:
        return False
    dik = list(dik_a) + list(dik_b)
    if yon == "yatay":
        gb = (min(a, b), min(dik), max(a, b), max(dik))
    else:
        gb = (min(dik), min(a, b), max(dik), max(a, b))
    r = {"a": a, "b": b, "dik_a": list(dik_a), "dik_b": list(dik_b),
         "metin": metin, "grup_kutu": gb}
    return _lokal_yerlestir(msp, yon, r, kayd, dkay, h, yabanci)


def _lokal_yerlestir(msp, yon, r, kayd, dkay, h, yabanci):
    """Delik grubunun içindeki ölçü (delikten deliğe) grubun HEMEN
    YANINA: uzatma çizgileri kısa, ölçü gösterdiği deliklerin dibinde.
    Yazı hiçbir yazıya ve çizgiye değmiyorsa konur; yoksa False (ölçü
    görünüşün dışına, ortak hattın ötesine gider)."""
    yatay = yon == "yatay"
    gb = r["grup_kutu"]
    lo, hi = (gb[1], gb[3]) if yatay else (gb[0], gb[2])
    a, b = r["a"] + kayd, r["b"] + kayd
    dolu = _yazi_kutulari(msp)
    # alan geniş: rakam hattın dışına kılavuzla kayabilir, oradaki
    # çizgiler de sayılmalı (P06: "3x SLOT 100" dar alanın dışındaki bir
    # çizgiye düşüyordu)
    if yatay:
        alan = (min(a, b) - 16 * h, lo + dkay - 16 * h, max(a, b) + 16 * h, hi + dkay + 16 * h)
    else:
        alan = (lo + dkay - 16 * h, min(a, b) - 16 * h, hi + dkay + 16 * h, max(a, b) + 16 * h)
    cizgi = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    for k in range(8):
        for yan in (1, -1):
            c_ = (hi + dkay + (1.2 + 0.9 * k) * h) if yan > 0 else (lo + dkay - (1.2 + 0.9 * k) * h)
            da = min(r["dik_a"], key=lambda v: abs(v + dkay - c_)) + dkay
            db = min(r["dik_b"], key=lambda v: abs(v + dkay - c_)) + dkay
            p1, p2 = ((a, da), (b, db)) if yatay else ((da, a), (db, b))
            if _ara_dene(msp, yon, p1, p2, c_, float(yan), h, r.get("metin"),
                         dolu, cizgi, yabanci) is not None:
                return True
    return False


ACI_EN_AZ = 0.5       # derece; bundan az sapan kenar eğik sayılmaz
ACI_EN_COK = 6        # görünüş başına en çok bu kadar farklı açı
AYNI_DUVAR_MM = 6.0   # bundan yakın paralel eğik çizgiler sacın iki yüzü


def _egik_kenarlar(kenar, kutu_, h):
    """Görünüşün EĞİK DOĞRU kenarları: (P, Q, açı_sapma, referans ekseni).
    Eğri (çok noktalı, doğrusal olmayan) kenarlar alınmaz."""
    buyuk = max(kutu_[2] - kutu_[0], kutu_[3] - kutu_[1])
    # Yazıdan KISA kenara açı verilmez: yayın yarıçapı yazıdan küçük kalır,
    # rakam açının dışına düşer ve uzatma yayı köşeyi dolaşır (1,6 mm'lik
    # kenarlara 0,5° / 38° yazılıyordu). Çok kısa eğik kenar pah ya da
    # kalıp ayrıntısıdır; pah notu ayrıca verilir.
    en_az = max(1.5 * h, 0.02 * buyuk)
    out = []
    for p in kenar.get("GORUNEN", []):
        if len(p) < 2:
            continue
        P, Q = p[0], p[-1]
        L = math.dist(P, Q)
        if L < en_az:
            continue
        ux, uy = (Q[0] - P[0]) / L, (Q[1] - P[1]) / L
        if any(abs((q[0] - P[0]) * uy - (q[1] - P[1]) * ux) > max(0.02, 1e-4 * L) for q in p[1:-1]):
            continue                   # doğru değil
        t = math.degrees(math.atan2(uy, ux)) % 180.0
        sap_y = min(t, 180.0 - t)                  # yataya göre
        sap_d = abs(90.0 - t)                      # düşeye göre
        if min(sap_y, sap_d) < ACI_EN_AZ:
            continue
        ref = "yatay" if sap_y <= sap_d else "dusey"
        out.append((P, Q, round(min(sap_y, sap_d), 1), ref, L))
    # HLR bir kenarı kesişen çizgilerde PARÇALARA böler: aynı doğrunun
    # parçaları tek kenar sayılır (yoksa "8x" yazıyordu, kenar 2 tane)
    dogru = []
    for P, Q, d, ref, L in sorted(out, key=lambda e: -e[4]):
        ux, uy = (Q[0] - P[0]) / L, (Q[1] - P[1]) / L
        for g in dogru:
            gP, gu = g["P"], g["u"]
            if abs(ux * gu[1] - uy * gu[0]) < 2e-4 and \
                    abs((P[0] - gP[0]) * gu[1] - (P[1] - gP[1]) * gu[0]) < max(0.05, 1e-4 * L):
                ts = [((q[0] - gP[0]) * gu[0] + (q[1] - gP[1]) * gu[1]) for q in (P, Q)] + g["t"]
                g["t"] = [min(ts), max(ts)]
                break
        else:
            dogru.append({"P": P, "u": (ux, uy), "t": [0.0, L], "d": d, "ref": ref})
    birlesik = []
    for g in dogru:
        t0, t1 = g["t"]
        P_ = (g["P"][0] + g["u"][0] * t0, g["P"][1] + g["u"][1] * t0)
        Q_ = (g["P"][0] + g["u"][0] * t1, g["P"][1] + g["u"][1] * t1)
        birlesik.append((P_, Q_, g["d"], g["ref"], t1 - t0))
    # SACIN İKİ YÜZÜ: eğik bir duvar kesitte iki paralel çizgidir (iç ve
    # dış yüz, aralarında sac kalınlığı). İkisi TEK duvardır; ayrı
    # sayılınca 4 eğik duvara "8x 30°" yazılıyordu (kullanıcı: "4 tane
    # var sadece"). Paralel, arası AYNI_DUVAR_MM'den az ve boyca üst
    # üste gelen çizgilerden uzun olanı kalır.
    tek = []
    for e in sorted(birlesik, key=lambda e: -e[4]):
        P, Q, L = e[0], e[1], e[4]
        ux, uy = (Q[0] - P[0]) / L, (Q[1] - P[1]) / L
        ikiz = False
        for f in tek:
            fP, fQ, fL = f[0], f[1], f[4]
            fu = ((fQ[0] - fP[0]) / fL, (fQ[1] - fP[1]) / fL)
            if abs(ux * fu[1] - uy * fu[0]) > 0.01:
                continue               # paralel değil
            ara = abs((P[0] - fP[0]) * fu[1] - (P[1] - fP[1]) * fu[0])
            if ara > AYNI_DUVAR_MM:
                continue
            ts = sorted((q[0] - fP[0]) * fu[0] + (q[1] - fP[1]) * fu[1] for q in (P, Q))
            ortak = min(ts[1], fL) - max(ts[0], 0.0)
            if ortak >= 0.5 * min(L, fL):
                ikiz = True
                break
        if not ikiz:
            tek.append(e)
    return tek


def aci_olculeri(msp, kenarlar, gorunusler, kaydir, gkutu, h):
    """EĞİK KENARLARIN AÇISI (kullanıcı: "açısal hiç bir ölçü yok").

    Görünüşteki her eğik doğru kenarın yataya ya da düşeye (hangisine
    yakınsa, yani 45°'den küçük tarafı) açısı. Değer HLR kenarının iki
    ucundan hesaplanır - geometrinin kendisidir, 0,1°'ye yuvarlanır.
    Aynı açı bir görünüşte BİR KEZ yazılır ("2x 12,5°"); ayna görünüşte
    (SAĞ/SOL) tekrarlanmaz. Yeri ölçülür: yazı başka yazıya ya da
    çizgiye değmez, yoksa o açı yazılmaz.
    Döner: çizilen açı ölçüsü sayısı."""
    sayi = 0
    ayna = defaultdict(set)
    for gad in gorunusler:
        if gad not in gkutu or gad not in kenarlar:
            continue
        gk = gkutu[gad]
        dx, dy = kaydir[gad]
        kb = (gk[0] - dx, gk[1] - dy, gk[2] - dx, gk[3] - dy)
        egik = _egik_kenarlar(kenarlar[gad], kb, h)
        if not egik:
            continue
        cift = AYNA_CIFT.get(gad)
        grup = defaultdict(list)
        for e in egik:
            grup[e[2]].append(e)
        yazildi = 0
        for deger, lst in sorted(grup.items(), key=lambda t: -max(e[4] for e in t[1])):
            if yazildi >= ACI_EN_COK:
                break
            if deger in ayna[cift]:
                continue
            lst.sort(key=lambda e: -e[4])
            metin = f"{len(lst)}x <>" if len(lst) > 1 else "<>"
            konuldu = False
            for P, Q, _d, ref, L in lst[:3]:
                for A, B in ((P, Q), (Q, P)):
                    A2 = (A[0] + dx, A[1] + dy)
                    B2 = (B[0] + dx, B[1] + dy)
                    if ref == "yatay":
                        R2 = (A2[0] + (1 if B2[0] > A2[0] else -1) * L, A2[1])
                    else:
                        R2 = (A2[0], A2[1] + (1 if B2[1] > A2[1] else -1) * L)
                    if _aci_koy(msp, A2, B2, R2, L, metin, h):
                        konuldu = True
                        break
                if konuldu:
                    break
            if konuldu:
                ayna[cift].add(deger)
                sayi += 1
                yazildi += 1
    return sayi


def _aci_dogru(dim, u1, u2):
    """Çizilen açı ölçüsü DOĞRU mu: (1) yazılan değer kenarlar arasındaki
    açı, (2) yayı KÜÇÜK açıyı tarıyor. Yalnız yazıya bakmak yetmiyordu:
    ezdxf rakamı 5,1° yazıp yayı 354,9° boyunca, köşenin çevresinde
    dolaştırabiliyordu - yay yakındaki yazıların üstünden geçiyordu
    (Karluna P16, kasa P72: 18 resimde)."""
    try:
        ic = list(dim.dimension.virtual_entities())
        yazilan = [v.text if v.dxftype() == "MTEXT" else v.dxf.text
                   for v in ic if v.dxftype() in ("MTEXT", "TEXT")]
        beklenen_d = math.degrees(math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))))
        beklenen = XL.tr(round(beklenen_d, 1), 1)
        if not any(re.search(r"(^|[^0-9,])" + re.escape(beklenen) + "°", t or "")
                   for t in yazilan):
            return False
        # yay yazı için bölünebilir: parçaların toplamı küçük açıyı aşmamalı
        tarama = sum((v.dxf.end_angle - v.dxf.start_angle) % 360.0
                     for v in ic if v.dxftype() == "ARC")
        return tarama <= 180.0
    except Exception:
        return False


def _aci_koy(msp, A, B, R, L, metin, h):
    """A köşesinde AB kenarı ile AR referansı arasına açı ölçüsü."""
    u1 = ((B[0] - A[0]) / L, (B[1] - A[1]) / L)
    u2 = ((R[0] - A[0]) / L, (R[1] - A[1]) / L)
    bx, by = u1[0] + u2[0], u1[1] + u2[1]
    bn = math.hypot(bx, by) or 1.0
    bx, by = bx / bn, by / bn
    dolu = _yazi_kutulari(msp)
    alan = (A[0] - L - 10 * h, A[1] - L - 10 * h, A[0] + L + 10 * h, A[1] + L + 10 * h)
    cizgi = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    ovr = {"dimadec": 1, "dimazin": 2, "dimtih": 1, "dimtoh": 1, "dimtmove": 1}
    for oran in (0.45, 0.3, 0.65, 0.85):
        r_ = min(max(3.0 * h, oran * L), 14.0 * h, 0.95 * L)
        base = (A[0] + bx * r_, A[1] + by * r_)
        # dar açıda açıortay kenarın dibinden geçer: yazı yana da kayar
        for uz, yan in ((1.6, 0), (2.6, 0), (1.6, 2.5), (1.6, -2.5), (2.6, 4.0),
                        (2.6, -4.0), (3.8, 0), (3.8, 5.5), (3.8, -5.5)):
            yazi = (A[0] + bx * (r_ + uz * h) - by * yan * h,
                    A[1] + by * (r_ + uz * h) + bx * yan * h)
            # ezdxf açıyı line2'den line1'e saat yönü tersine ölçer:
            # kenar referansın hangi yanındaysa sıra ona göre (yoksa 355°)
            capraz = u2[0] * u1[1] - u2[1] * u1[0]
            siralar = (((A, B), (A, R)), ((A, R), (A, B)))
            if capraz <= 0:
                siralar = siralar[::-1]
            dim = None
            for l1, l2 in siralar:
                try:
                    dim = msp.add_angular_dim_2l(
                        base=base, line1=l1, line2=l2, location=yazi, text=metin,
                        dimstyle=OLCU_STILI, override=ovr, dxfattribs={"layer": "OLCU"})
                    dim.render()
                except Exception:
                    dim = None
                    continue
                if _aci_dogru(dim, u1, u2):
                    break
                _olcu_sil(msp, dim)
                dim = None
            if dim is None:
                return False           # iki sırada da doğru çizilemedi
            ky = _olcu_yazi_kutusu(dim)
            if (ky and not _cakisiyor(ky, dolu, 0.15 * h)
                    and not _cizgi_kesiyor(ky, cizgi, 0.1 * h)
                    and not _kendi_ustunde(dim, ky, h)
                    and not _dim_yaziya_degiyor(dim, dolu, 0.1 * h)):
                return True
            _olcu_sil(msp, dim)
    return False


# ----------------------------------------------------------- detay görünüşü
DETAY_OLCEK = (2, 2.5, 4, 5, 10)      # ISO 5455 büyütme ölçekleri
DETAY_HARF = "DEFGHJKLMNPRSTUVYZ"     # A, B, C datumlarda
DETAY_EN_COK = 4
DETAY_OLCU_PAYI = 16.0    # detayın ölçüleri daire / çerçeveden en çok bu kadar (yazı boyu) dışarı çıkar
DETAY_BAG = 12.0          # detay bölgesinde iki nokta arası en çok (yazı boyu katı)
DETAY_EN_BUYUK = 0.12     # detay dairesi (büyütülmüş yarıçap) görünüşün en uzun kenarına oranla
DETAY_EN_AZ_YARI = 12.0   # ... ama en az bu kadar yazı boyu (küçük parçada 2:1 detay kurulabilsin)
DETAY_EN_GEVSEK = 0.50    # geniş öbekte en küçük büyütmeyle gevşek tavan (ölçü atılmaz)


def _daire_kirp(a, b, c, r):
    """a-b parçasının c merkezli r yarıçaplı dairenin İÇİNDE kalan kısmı."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = a[0] - c[0], a[1] - c[1]
    A = dx * dx + dy * dy
    if A < 1e-18:
        return None
    B = 2 * (fx * dx + fy * dy)
    C = fx * fx + fy * fy - r * r
    D = B * B - 4 * A * C
    if D <= 0:
        return None
    sD = math.sqrt(D)
    t0, t1 = max(0.0, (-B - sD) / (2 * A)), min(1.0, (-B + sD) / (2 * A))
    if t0 >= t1:
        return None
    return ((a[0] + dx * t0, a[1] + dy * t0), (a[0] + dx * t1, a[1] + dy * t1))


def detay_gorunusleri(msp, kenarlar, kaydir, gkutu, kayip, h, rapor=None,
                      harf=None, kullanilan=None, engel=()):
    """OTOMATİK DETAY GÖRÜNÜŞÜ (kullanıcı: "çok karışık resimlerde detay
    yapılabilir, aynı kaynaktaki gibi").

    Ana görünüşte yer bulamayan ölçüler (kayip) atılmaz: bölgeleri ince
    bir daireyle işaretlenir, yanına harf konur ("D"), bölge standart bir
    büyütmeyle (2:1 ... 10:1) boş bir hücreye çizilir, başlığı "DETAY D
    (5:1)". Ölçüler detayda verilir; ölçek çarpanı ölçünün kendisine
    işlenir (dimlfac), rakam GERÇEK değeri yazar. Datum ölçüsü detayda
    çizilmiş en yakın komşusundan (ya da datumdan) verilir.

    Detay, izdüşüm ızgarasındaki BOŞ hücreye konur (SAĞ'ın ya da SOL'un
    altı, ÜST'le aynı satır); yoksa her şeyin altına. Yeri ölçülür.
    Döner: [(ad, kutu)] - pafta bunları ayrı pencere yapar."""
    if not kayip:
        return []
    cikti = []
    kullanilan = [] if kullanilan is None else kullanilan
    harf = iter(DETAY_HARF) if harf is None else harf
    for gad in list(dict.fromkeys(k["gad"] for k in kayip)):
        if gad not in gkutu or gad not in kenarlar:
            continue
        lst = [k for k in kayip if k["gad"] == gad]
        noktalar = []
        for k in lst:
            yat = k["yon"] == "yatay"
            # İki ucun BİRBİRİNE EN YAKIN özellikleri: bir seviyede birkaç
            # delik olabilir; ilkini almak bölgeyi görünüş boyu açıyordu
            # (Televre P04: 2456 ile 760 -> 1700 mm'lik daire, hiçbir
            # hücreye sığmadı, ölçü düştü).
            da_, db_ = list(k["dik_a"] or []), list(k["dik_b"] or [])
            if da_ and db_:
                da_, db_ = map(lambda t: [t], min(((p, q) for p in da_ for q in db_),
                                                  key=lambda t: abs(t[0] - t[1])))
            for v, dd in ((k["a"], da_), (k["b"], db_)):
                if not dd:
                    continue
                d = dd[0]
                x, y = ((v + k["kayd"], d + k["dkay"]) if yat
                        else (d + k["dkay"], v + k["kayd"]))
                noktalar.append((x, y, id(k)))
        # tek bağlantılı öbek: DETAY_BAG x h (derli toplu bölgeler; bütün
        # parçayı kaplayan bölge detay değildir)
        obek = []
        for x, y, i in noktalar:
            for o_ in obek:
                if any(math.dist((x, y), q[:2]) <= DETAY_BAG * h for q in o_):
                    o_.append((x, y, i))
                    break
            else:
                obek.append([(x, y, i)])
        konan = set()        # bir ölçü bir kez: iki ucu iki öbeğe düşebilir
        for o_ in obek:
            if len(cikti) >= DETAY_EN_COK:
                break
            ids = {q[2] for q in o_} - konan
            kl = [k for k in lst if id(k) in ids]
            if not kl:
                continue
            konan |= ids
            xs, ys = [q[0] for q in o_], [q[1] for q in o_]
            c = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
            R = max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0 + 3.0 * h
            R = max(R, 4.0 * h)
            en_kisa = min(max(abs(k["b"] - k["a"]), 1e-3) for k in kl)
            yabanci = [(k_[0] - 0.3 * h, k_[1] - 0.3 * h, k_[2] + 0.3 * h, k_[3] + 0.3 * h)
                       for k_ in gkutu.values()]
            onceki_h = {e.dxf.handle for e in msp}
            kur = _detay_kur(msp, gad, c, R, en_kisa, kenarlar, kaydir, gkutu, h,
                             kullanilan, harf,
                             engel=list(engel) + [kt for _a, kt in cikti])
            if kur is None:
                # Detay kurulamadı: ölçü yine düşmez, özelliğin YANINA
                for k in kl:
                    if _yanina_koy(msp, k["yon"], k["a"], k["b"], list(k["dik_a"] or []),
                                   list(k["dik_b"] or []), k.get("metin"), k["kayd"],
                                   k["dkay"], h, yabanci) and rapor is not None:
                        rapor["yer_yok"] -= 1
                continue
            H, olcek, dc, Rd = kur
            # ölçüler: gerçek değer (dimlfac)
            _EK_OVR["dimlfac"] = 1.0 / olcek
            kalan_, yerler_ = [], {}
            try:
                for k in kl:
                    once_ = {e.dxf.handle for e in msp}
                    if _detay_olcu(msp, k, c, dc, olcek, Rd, h, yabanci):
                        yerler_[id(k)] = {e.dxf.handle for e in msp} - once_
                    else:
                        kalan_.append(k)
                if kalan_:
                    kalan_ = _detay_takas(msp, kalan_, {id(k): k for k in kl}, yerler_,
                                          c, dc, olcek, Rd, h, yabanci)
                if rapor is not None:
                    rapor["yer_yok"] -= len(kl) - len(kalan_)
            finally:
                _EK_OVR.clear()
            # pencere ŞİMDİ ölçülür (yanına düşenler ana görünüşe çizilir);
            # ana görünüşteki işaret (daire + harf) pencereye girmez
            isaret = [e for e in msp if e.dxf.handle not in onceki_h
                      and _icinde(_varlik_kutulari_liste([e])[0][:2] if _varlik_kutulari_liste([e]) else (1e18, 1e18),
                                  (c[0] - R - 3 * h, c[1] - R - 3 * h, c[0] + R + 3 * h, c[1] + R + 3 * h))]
            pencere = _olculen_pencere(msp, onceki_h | {e.dxf.handle for e in isaret},
                                       _detay_kutusu(dc, Rd, h), h)
            for k in kalan_:                   # detayda da yer yok: yanına
                if _yanina_koy(msp, k["yon"], k["a"], k["b"], list(k["dik_a"] or []),
                               list(k["dik_b"] or []), k.get("metin"), k["kayd"],
                               k["dkay"], h, yabanci) and rapor is not None:
                    rapor["yer_yok"] -= 1
            cikti.append((f"DETAY {H}", pencere))
    return cikti


# ------------------------------------------------------------ bölge detayı
# Kullanıcı: "sol tarafı ayır, sağ tarafı ayır, ana görünüşte kesişmeyen
# ölçüleri ver; bu tarz karışıklıkları hep detay görünüşlere taşı". Uzman
# ressam kalabalık bir ucu ana görünüşe tıkıştırmaz: o BÖLGEYİ ayırır,
# büyütür ve orada tam ölçülendirir; ana görünüşte yalnız temiz ölçüler
# ve bölgenin bağlantı ölçüsü kalır.
#
# Bölge, görünüşü uzun yönüne DİK boydan boya kesen bir BANTTIR (daire
# değil): bant parçanın iki uzun kenarını içerdiği için dik yöndeki
# konumlar detayda doğrudan datum kenarından verilir; bant datum ucunu
# içeriyorsa uzun yöndeki konumlar da. İçermiyorsa bölgenin ana
# görünüşte ölçülü BAĞLANTI özelliğinden zincirlenir - tek referans.
BOLGE_EN_COK = 6
BOLGE_BAG = 10.0      # iki bant arası bundan (yazı boyu katı) azsa birleşir
BOLGE_PAY = 2.5       # bölgenin özelliklerden taşma payı (yazı boyu katı)
DETAY_BANT_EN = 0.30  # bant detayı (büyütülmüş) en çok görünüşün bu kadarı
BOLGE_UC = 0.12       # banda bu kadar (uzun kenar oranı) yakın uç banda katılır


def _varlik_geri_al(msp, onceki):
    """onceki (handle kümesi) sonrasında eklenen her şeyi siler; ölçülerin
    blokları da (deneme geçişini geri almak için)."""
    for e in list(msp):
        if e.dxf.handle in onceki:
            continue
        try:
            ad = e.dxf.get("geometry", None) if e.dxftype() == "DIMENSION" else None
            msp.delete_entity(e)
            if ad and ad in msp.doc.blocks:
                msp.doc.blocks.delete_block(ad, safe=False)
        except Exception:
            pass


def _kayip_noktalari(k):
    """Kayıp ölçünün ÖZELLİK noktaları (ham izdüşüm): b ucundakiler."""
    yat = k["yon"] == "yatay"
    return [((k["b"], d) if yat else (d, k["b"])) for d in (k.get("dik_b") or [])]


def bolge_sec(kayip, gkutu, kaydir, h):
    """Ana görünüşte TEMİZ yerleşemeyen özelliklerden DETAY BÖLGELERİ
    (dikdörtgen).

    Sıra: özellikler 2B'de tek bağlantılı öbeklere ayrılır (BOLGE_BAG) ->
    öbeğin kutusu + pay -> HER YÖNDE parçanın kenarına yakınsa (o yöndeki
    boyun BOLGE_UC'u) kenara kadar uzatılır: ince uzun parçada iki uzun
    kenar da yakın olduğundan bölge boydan boya BANT olur (dik konumlar
    datum kenarından), levhada köşedeki öbek yalnız köşeyi alır (1036 mm'lik
    levhanın bütün yüksekliği detay olmaz) -> kesişen bölgeler birleşir ->
    detayda en az 2:1 büyütüleceği için bir yönde DETAY_BANT_EN'i aşan
    bölge o yönde EŞİT parçalara bölünür -> en çok özelliği içeren
    BOLGE_EN_COK bölge. Döner: [{"gad", "k", "ek", "n"}] (çizim koord.)."""
    adaylar = []
    for gad in dict.fromkeys(k["gad"] for k in kayip):
        if gad not in gkutu:
            continue
        dx, dy = kaydir[gad]
        gk = gkutu[gad]
        ek = 0 if (gk[2] - gk[0]) >= (gk[3] - gk[1]) else 1      # uzun eksen
        L = max(gk[2] - gk[0], gk[3] - gk[1])
        en_bant = DETAY_BANT_EN * L / min(DETAY_OLCEK)
        pts = list(dict.fromkeys((round(x + dx, 3), round(y + dy, 3))
                                 for k in kayip if k["gad"] == gad
                                 for x, y in _kayip_noktalari(k)))
        if not pts:
            continue
        obek = []
        for q in pts:
            bag = [o_ for o_ in obek if any(math.dist(q, r_) <= BOLGE_BAG * h for r_ in o_)]
            yeni = [q]
            for o_ in bag:
                yeni.extend(o_)
                obek.remove(o_)
            obek.append(yeni)
        kutular = []
        for o_ in obek:
            k = [min(q[0] for q in o_) - BOLGE_PAY * h, min(q[1] for q in o_) - BOLGE_PAY * h,
                 max(q[0] for q in o_) + BOLGE_PAY * h, max(q[1] for q in o_) + BOLGE_PAY * h]
            for i in (0, 1):
                boy = gk[i + 2] - gk[i]
                if k[i] - gk[i] <= BOLGE_UC * boy:
                    k[i] = gk[i] - 1.5 * h                   # sol / alt kenar
                if gk[i + 2] - k[i + 2] <= BOLGE_UC * boy:
                    k[i + 2] = gk[i + 2] + 1.5 * h           # sağ / üst kenar
            kutular.append(k)
        # kesişen bölgeler birleşir
        degisti = True
        while degisti:
            degisti = False
            for i in range(len(kutular)):
                for j in range(i + 1, len(kutular)):
                    a, b = kutular[i], kutular[j]
                    if a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                        kutular[i] = [min(a[0], b[0]), min(a[1], b[1]),
                                      max(a[2], b[2]), max(a[3], b[3])]
                        del kutular[j]
                        degisti = True
                        break
                if degisti:
                    break
        # detay sınırını aşan bölge eşit parçalara bölünür (iki yönde de)
        for k in kutular:
            nx = max(1, math.ceil((k[2] - k[0]) / en_bant - 1e-9))
            ny = max(1, math.ceil((k[3] - k[1]) / en_bant - 1e-9))
            ax_, ay_ = (k[2] - k[0]) / nx, (k[3] - k[1]) / ny
            for i in range(nx):
                for j in range(ny):
                    kt = (k[0] + i * ax_, k[1] + j * ay_, k[0] + (i + 1) * ax_, k[1] + (j + 1) * ay_)
                    n_ = sum(1 for q in pts if kt[0] <= q[0] <= kt[2] and kt[1] <= q[1] <= kt[3])
                    if n_:
                        adaylar.append({"gad": gad, "k": kt, "ek": ek, "n": n_})
    adaylar.sort(key=lambda b: -b["n"])
    return adaylar[:BOLGE_EN_COK]

def _bant_birlestir(bantlar, h):
    """Aynı görünüşte kesişen ya da BOLGE_BAG'dan yakın bantlar TEK bant
    olur (ana görünüşte üst üste binen iki çerçeve ve aynı delikleri iki
    kez gösteren iki detay olmaz)."""
    bantlar = list(bantlar)
    degisti = True
    while degisti:
        degisti = False
        for i in range(len(bantlar)):
            for j in range(i + 1, len(bantlar)):
                a, b = bantlar[i], bantlar[j]
                if a["gad"] != b["gad"] or a["ek"] != b["ek"]:
                    continue
                e = a["ek"]
                if a["k"][e] - BOLGE_BAG * h <= b["k"][e + 2] and b["k"][e] - BOLGE_BAG * h <= a["k"][e + 2]:
                    k = (min(a["k"][0], b["k"][0]), min(a["k"][1], b["k"][1]),
                         max(a["k"][2], b["k"][2]), max(a["k"][3], b["k"][3]))
                    bantlar[i] = {"gad": a["gad"], "k": k, "ek": e, "n": a["n"] + b["n"]}
                    del bantlar[j]
                    degisti = True
                    break
            if degisti:
                break
    return bantlar


def _bolgede(x, y, b, h):
    """Çizim koordinatındaki nokta b bandının İÇİNDE mi (kenardan pay)."""
    k = b["k"]
    return k[0] + 0.5 * h <= x <= k[2] - 0.5 * h and k[1] + 0.5 * h <= y <= k[3] - 0.5 * h


def bolge_plani(plan, bolgeler, kaydir, h, kayip_deneme):
    """Ana görünüş planından bantların İÇİNDEKİ özelliklerin ölçüleri
    çıkarılır (detayda verilecek). Her bant ve yön için referans: bant
    datum kenarını içeriyorsa kenar; içermiyorsa banttaki, denemede ana
    görünüşe temiz yerleşmiş, datuma en yakın özellik ana görünüşte
    KALIR (bağlantı) ve detayın referansı olur.

    Döner: (süzülmüş plan, {bant no: {"yatay", "dusey", "ref", "ara"}})."""
    import copy
    yeni = copy.deepcopy(plan)
    kayip_sv = {(k["gad"], k["yon"], round(k["b"], 2)) for k in kayip_deneme}
    olcu = {}
    for bi, b in enumerate(bolgeler):
        gad = b["gad"]
        pl = yeni.get(gad)
        if not pl:
            continue
        dx, dy = kaydir[gad]
        bo = olcu.setdefault(bi, {"yatay": [], "dusey": [], "ref": {}, "ara": []})
        for yon in ("yatay", "dusey"):
            yat = yon == "yatay"
            dat = (pl.get("datum") or {}).get(yon)
            if dat is None:
                continue

            def nokta(deger, v):
                return (deger + dx, v + dy) if yat else (v + dx, deger + dy)

            # Aynı hizadaki özelliklerden (iki bantta birer slot) yalnız
            # banttakiler bu detaya gider: ölçü BÖLÜNÜR - bant içi kopyası
            # detaya, kalan "dik"ler ana planda kalır (hepsi bantta ise
            # ölçü ana görünüşten bütünüyle çıkar). Önce "hepsi bantta"
            # aranıyordu; iki slotlu sacda ölçü ne detaya ne ana görünüşe
            # giriyor, düşüyordu (kasa TRIM bağlantı sacı 4).
            icer = []
            for r in pl.get(yon) or []:
                if not r.get("kosu"):
                    continue
                d = list(r.get("dik") or [])
                d_ic = [v for v in d if _bolgede(*nokta(r["deger"], v), b, h)]
                if not d_ic:
                    continue
                if len(d_ic) == len(d):
                    icer.append(r)
                else:
                    r2 = dict(r, dik=d_ic)
                    r["dik"] = [v for v in d if v not in d_ic]
                    icer.append(r2)
            if not icer:
                continue
            k = b["k"]
            dat_c = dat + (dx if yat else dy)
            if (k[0] if yat else k[1]) - 1e-6 <= dat_c <= (k[2] if yat else k[3]) + 1e-6:
                pdik = ((k[1] + k[3]) / 2.0 - dy) if yat else ((k[0] + k[2]) / 2.0 - dx)
                bo["ref"][yon] = (dat, [pdik], True)
                cikan = icer
            else:
                temiz = [r for r in icer if (gad, yon, round(r["deger"], 2)) not in kayip_sv]
                bag = min(temiz or icer, key=lambda r: abs(r["deger"] - dat))
                bo["ref"][yon] = (bag["deger"], list(bag.get("dik") or []), False)
                cikan = [r for r in icer if r is not bag]
            bo[yon].extend(cikan)
            pl[yon] = [r for r in pl[yon] if not any(r is q for q in cikan)]
            # iki ucu da bantta olan iki uçlu ölçüler (slot boyu, grup içi)
            ara = []
            for r in pl[yon]:
                if r.get("kosu"):
                    continue
                da_ = r.get("dik_a") or r.get("dik") or []
                db_ = r.get("dik_b") or r.get("dik") or []
                if da_ and db_ and all(_bolgede(*nokta(r["a"], v), b, h) for v in da_) \
                        and all(_bolgede(*nokta(r["b"], v), b, h) for v in db_):
                    ara.append(r)
            bo["ara"].extend((yon, r) for r in ara)
            pl[yon] = [r for r in pl[yon] if not any(r is q for q in ara)]
    return yeni, olcu


def _kutu_kirp(a, b, k):
    """a-b parçasının k kutusunun İÇİNDE kalan kısmı (Liang-Barsky)."""
    x0, y0 = a
    dx_, dy_ = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p_, q_ in ((-dx_, x0 - k[0]), (dx_, k[2] - x0), (-dy_, y0 - k[1]), (dy_, k[3] - y0)):
        if abs(p_) < 1e-12:
            if q_ < 0:
                return None
            continue
        t = q_ / p_
        if p_ < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return ((x0 + dx_ * t0, y0 + dy_ * t0), (x0 + dx_ * t1, y0 + dy_ * t1))


def _yazidan_kacan_kutu(msp, k, h, n=400):
    """k kutusunun ince çerçevesi (ana görünüşte bölge işareti); yazıların
    üstüne düşen kısımları çizilmez."""
    dolu = [(q[0] - 0.2 * h, q[1] - 0.2 * h, q[2] + 0.2 * h, q[3] + 0.2 * h)
            for q in _yazi_kutulari(msp)]
    kose = [(k[0], k[1]), (k[2], k[1]), (k[2], k[3]), (k[0], k[3]), (k[0], k[1])]
    for p, q in zip(kose, kose[1:]):
        L = math.dist(p, q)
        m = max(2, int(n * L / (2 * ((k[2] - k[0]) + (k[3] - k[1])))))
        pts = [(p[0] + (q[0] - p[0]) * i / m, p[1] + (q[1] - p[1]) * i / m) for i in range(m + 1)]
        bas = None
        for i in range(m):
            orta = ((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
            serbest = not any(d[0] <= orta[0] <= d[2] and d[1] <= orta[1] <= d[3] for d in dolu)
            if serbest and bas is None:
                bas = pts[i]
            if not serbest and bas is not None:
                msp.add_line(bas, pts[i], dxfattribs={"layer": "OLCU"})
                bas = None
        if bas is not None:
            msp.add_line(bas, pts[m], dxfattribs={"layer": "OLCU"})


def _bant_detayi_kur(msp, b, en_kisa, kenarlar, kaydir, gkutu, h, harf, ust=None,
                     engel=()):
    """Bant detayını KURAR: büyütme, yer (resmin altındaki serbest alan),
    ana görünüşte bant çerçevesi + harf, büyütülmüş geometri, çerçeve ve
    başlık. Döner: (harf, büyütme, merkez, (yarı en, yarı boy)) ya da None."""
    gad, k = b["gad"], b["k"]
    w, hh = k[2] - k[0], k[3] - k[1]
    L = max(max(g[2] - g[0], g[3] - g[1]) for g in gkutu.values())
    # DETAY KÜÇÜK KALIR: büyütülmüş bölge görünüşün en uzun kenarının
    # DETAY_BANT_EN'ini aşmaz - detaylar kâğıtta yer kapladıkça ana
    # görünüşün ölçeği düşüyordu (P01: 1:12 -> 1:16, yazı 0,9 mm). En
    # küçük büyütme (2:1) bile sınırı belirgin aşıyorsa bölge detay için
    # çok büyüktür: None (ölçüler özelliğin yanına). Yeterli büyütme:
    # en kısa ölçü okunacak kadar (2,5 yazı boyu); fazlası yer israfı.
    sigan = [m for m in DETAY_OLCEK
             if m * max(w, hh) <= DETAY_BANT_EN * L
             or (m == min(DETAY_OLCEK) and m * max(w, hh) <= 1.5 * DETAY_BANT_EN * L)]
    if not sigan:
        return None
    olcek = next((m for m in sigan if m * en_kisa >= 2.5 * h), max(sigan))
    yw, yh = w * olcek / 2.0, hh * olcek / 2.0
    yer_ = _detay_serbest_kutu(msp, gkutu, yw + DETAY_OLCU_PAYI * h, yh + DETAY_OLCU_PAYI * h, h, ust=ust,
                               engel=engel)
    if yer_ is None:
        return None
    H = next(harf, None)
    if H is None:
        return None
    dc = yer_
    c = ((k[0] + k[2]) / 2.0, (k[1] + k[3]) / 2.0)
    _yazidan_kacan_kutu(msp, k, h)
    _bant_harfi(msp, k, H, h)
    dx, dy = kaydir[gad]
    for kat in ("GORUNEN", "GIZLI"):
        for p in kenarlar[gad].get(kat, []):
            for a, bb in zip(p, p[1:]):
                a2, b2 = (a[0] + dx, a[1] + dy), (bb[0] + dx, bb[1] + dy)
                kp = _kutu_kirp(a2, b2, k)
                if kp is None:
                    continue
                q1 = ((kp[0][0] - c[0]) * olcek + dc[0], (kp[0][1] - c[1]) * olcek + dc[1])
                q2 = ((kp[1][0] - c[0]) * olcek + dc[0], (kp[1][1] - c[1]) * olcek + dc[1])
                if math.dist(q1, q2) > 1e-6:
                    msp.add_line(q1, q2, dxfattribs={"layer": kat})
    ol = f"{olcek:g}".replace(".", ",")
    _yaz(msp, f"DETAY {H} ({ol}:1)", dc[0] - yw, dc[1] + yh + 1.2 * h, 1.3 * h)
    return H, olcek, dc, (yw, yh)


def _detay_serbest_kutu(msp, gkutu, yw, yh, h, ust=None, engel=()):
    """yw x yh yarı boyutlu kutunun merkezi, görünüşlerin ALTINDAKİ serbest
    alanda: detaylar YAN YANA bir sıra, sığmazsa alttaki sıra. ust: sıranın
    üst sınırı (görünüşlerin ve ölçülerinin altı; detaylardan ÖNCE ölçülür
    - yoksa her detay bir öncekinin altına iniyordu)."""
    dolu = _varlik_kutulari(msp) + list(engel)    # engel: konmuş detay pencereleri
    if not dolu:
        return None
    x0 = min(g[0] for g in gkutu.values())
    x1 = max(max(g[2] for g in gkutu.values()), x0 + 2 * yw)
    alt = min(q[1] for q in dolu) if ust is None else ust
    y = alt - 4.0 * h
    for _sira in range(6):
        cy = y - yh
        x = x0 + yw
        while x <= x1 - yw + 1e-6:
            kt = (x - yw, cy - yh, x + yw, cy + yh)
            if not _cakisiyor(kt, dolu, 1.0 * h):
                return (x, cy)
            x += 0.1 * yw + h
        # bu sırada yer yok: bu sıradaki en alt detayın altına
        ic = [q for q in dolu if q[3] <= y + 1e-6 and q[1] >= y - 3 * max(yh, h) * 2]
        y = (min(q[1] for q in ic) if ic else cy - yh) - 4.0 * h
    return None


def bolge_detaylari(msp, bolgeler, bolge_olcu, kenarlar, kaydir, gkutu, h,
                    rapor=None, harf=None, kullanilan=None):
    """Her bant için DETAY görünüşü: banttaki bütün konumlar referanstan
    (datum kenarı ya da ana görünüşte ölçülü bağlantı özelliği) ZİNCİRLE
    (0 -> A -> B); iki ucu bantta olan slot boyu / grup içi ölçüler de.
    Detay kurulamazsa ölçüler düşmez: özelliğin yanına konur.
    Döner: [(ad, kutu)]."""
    cikti = []
    harf = iter(DETAY_HARF) if harf is None else harf
    yabanci = [(k_[0] - 0.3 * h, k_[1] - 0.3 * h, k_[2] + 0.3 * h, k_[3] + 0.3 * h)
               for k_ in gkutu.values()]
    dolu0 = _varlik_kutulari(msp)
    ust = min(q[1] for q in dolu0) if dolu0 else None     # detay sırasının üstü
    for bi, b in enumerate(bolgeler):
        bo = bolge_olcu.get(bi)
        if not bo or not (bo["yatay"] or bo["dusey"] or bo["ara"]):
            continue
        gad = b["gad"]
        dx, dy = kaydir[gad]
        halka = []
        for yon in ("yatay", "dusey"):
            if not bo[yon] or yon not in bo["ref"]:
                continue
            yat = yon == "yatay"
            kayd, dkay = (dx, dy) if yat else (dy, dx)
            ref, rdik, _kenar = bo["ref"][yon]

            def banttaki(deger, dik):
                return [v for v in dik if _bolgede(*(((deger + dx, v + dy) if yat
                                                      else (v + dx, deger + dy))), b, h)] or list(dik)
            onceki = (ref, banttaki(ref, rdik))
            for r in sorted(bo[yon], key=lambda q: abs(q["deger"] - ref)):
                dk = banttaki(r["deger"], r.get("dik") or [])
                halka.append({"gad": gad, "yon": yon, "a": onceki[0], "b": r["deger"],
                              "dik_a": onceki[1], "dik_b": dk, "metin": None,
                              "kayd": kayd, "dkay": dkay})
                onceki = (r["deger"], dk)
        for yon, r in bo["ara"]:
            yat = yon == "yatay"
            kayd, dkay = (dx, dy) if yat else (dy, dx)
            halka.append({"gad": gad, "yon": yon, "a": r["a"], "b": r["b"],
                          "dik_a": list(r.get("dik_a") or r.get("dik") or []),
                          "dik_b": list(r.get("dik_b") or r.get("dik") or []),
                          "metin": r.get("metin"), "kayd": kayd, "dkay": dkay})
        if not halka:
            continue
        en_kisa = min(max(abs(k["b"] - k["a"]), 1e-3) for k in halka)
        onceki_h = {e.dxf.handle for e in msp}
        kur = _bant_detayi_kur(msp, b, en_kisa, kenarlar, kaydir, gkutu, h, harf, ust=ust,
                               engel=[kt for _a, kt in cikti])
        if kur is None:
            for k in halka:
                if not _yanina_koy(msp, k["yon"], k["a"], k["b"], k["dik_a"], k["dik_b"],
                                   k.get("metin"), k["kayd"], k["dkay"], h, yabanci):
                    if rapor is not None:
                        rapor["yer_yok"] += 1
            continue
        H, olcek, dc, (yw, yh) = kur
        c = ((b["k"][0] + b["k"][2]) / 2.0, (b["k"][1] + b["k"][3]) / 2.0)
        _EK_OVR["dimlfac"] = 1.0 / olcek
        kalan, yerler = [], {}
        try:
            for k in halka:
                once_ = {e.dxf.handle for e in msp}
                if _detay_olcu(msp, k, c, dc, olcek, max(yw, yh), h, yabanci):
                    yerler[id(k)] = {e.dxf.handle for e in msp} - once_
                else:
                    kalan.append(k)
            if kalan:
                kalan = _detay_takas(msp, kalan, {id(k): k for k in halka}, yerler,
                                     c, dc, olcek, max(yw, yh), h, yabanci)
        finally:
            _EK_OVR.clear()
        # Pencere ŞİMDİ ölçülür - yanına düşen ölçüler ana görünüşe çizilir,
        # pencereye girmemeli (P04: pencere ÜST görünüşün üstüne taşıp
        # paftayı bozuyordu). Ana görünüşteki işaret (çerçeve + harf) de
        # pencereye girmez.
        kb_ = b["k"]
        isaret = [e for e in msp if e.dxf.handle not in onceki_h
                  and (lambda kl: bool(kl) and _icinde(kl[0][:2], (kb_[0] - 4 * h, kb_[1] - 4 * h,
                                                                   kb_[2] + 4 * h, kb_[3] + 4 * h)))(
                      _varlik_kutulari_liste([e]))]
        pencere = _olculen_pencere(
            msp, onceki_h | {e.dxf.handle for e in isaret},
            (dc[0] - yw - 1.5 * h, dc[1] - yh - 1.5 * h, dc[0] + yw + 1.5 * h, dc[1] + yh + 3.2 * h), h)
        # detayda yer bulamayan ölçü DÜŞMEZ: ana görünüşte özelliğin yanına
        for k in kalan:
            if not _yanina_koy(msp, k["yon"], k["a"], k["b"], k["dik_a"], k["dik_b"],
                               k.get("metin"), k["kayd"], k["dkay"], h, yabanci):
                if rapor is not None:
                    rapor["yer_yok"] += 1
        cikti.append((f"DETAY {H}", pencere))
    return cikti

def _detay_kutusu(dc, Rd, h):
    return (dc[0] - Rd - 1.5 * h, dc[1] - Rd - 1.5 * h, dc[0] + Rd + 1.5 * h, dc[1] + Rd + 3.0 * h)


def _olculen_pencere(msp, onceki, varsayilan, h):
    """Detay penceresi ÖLÇÜLEREK: detay için eklenen bütün varlıkların
    (daire / çerçeve, başlık, geometri, ölçüler, kılavuzlar) sınırı +
    pay. Eskiden daire + 6 yazı boyu paydı; pay pencereyi büyütüp ana
    görünüşün ölçeğini düşürüyordu (P01 1:20), dar tutulunca da dışarı
    taşan ölçü pencereden kesiliyordu. Ölçmek ikisini de çözer."""
    yeni_ = [e for e in msp if e.dxf.handle not in onceki]
    if not yeni_:
        return varsayilan
    kl = _varlik_kutulari_liste(yeni_)
    if not kl:
        return varsayilan
    return (min(k[0] for k in kl) - 0.8 * h, min(k[1] for k in kl) - 0.8 * h,
            max(k[2] for k in kl) + 0.8 * h, max(k[3] for k in kl) + 0.8 * h)


def _varlik_kutulari_liste(varlik):
    """Verilen varlıkların sınırları [(x0, y0, x1, y1)]; ölçü bloğu açılır,
    MTEXT tek satır ölçülür."""
    out = []
    for e in varlik:
        try:
            if e.dxftype() == "DIMENSION":
                k = _dim_kutusu(type("D", (), {"dimension": e})())
                if k:
                    out.append(k)
                continue
            if e.dxftype() == "MTEXT":
                out.append(mtext_kutusu(e))
                continue
            b = ezdxf.bbox.extents([e], fast=False)
            if b.has_data:
                out.append((b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y))
        except Exception:
            continue
    return out


def _detay_kur(msp, gad, c, R, en_kisa, kenarlar, kaydir, gkutu, h, kullanilan, harf,
               engel=()):
    """Bir detay görünüşünü KURAR: büyütme, yer, ana görünüşte daire + harf,
    büyütülmüş geometri, detay dairesi ve başlığı ("DETAY D (2:1)").
    Ölçüleri çağıran koyar. Döner: (harf, büyütme, merkez, yarıçap) ya da
    None (sığmadı / harf bitti).

    Yer: önce izdüşüm ızgarasının boş hücresi, yoksa resmin ALTINDAKİ
    serbest alan (pafta detayı ızgaradan bağımsız, kâğıdın boş yerine
    koyar). Büyütme: detay dairesi görünüşün en uzun kenarının
    DETAY_EN_BUYUK'unu aşmaz - bütün parçayı kaplayan detay detay değildir;
    en kısa ölçü okunacak kadar (3,5 yazı boyu) büyütülür."""
    # Izgaranın boş hücresi BAŞLIĞA kalır (1. sayfanın parçası); detay
    # görünüşlerin altına gider, paftada zaten serbest penceredir (1. sayfada
    # boş yere ya da 2. sayfaya). Detay hücreyi alınca başlık tepeye çıkıyor,
    # görünüş öbeğine bir satır ekleniyor ve ölçek düşüyordu (P01 1:16).
    hucre = []
    # Küçük parçada (100 mm'lik braket) %12 en küçük daireden (4 yazı boyu)
    # bile dar kalıyor, detay hiç kurulamıyor ve ölçü düşüyordu (kasa TRIM
    # bağlantı sacları): tavanın mutlak alt sınırı DETAY_EN_AZ_YARI.
    L_ = max(max(g[2] - g[0], g[3] - g[1]) for g in gkutu.values())
    en_yari = max(DETAY_EN_BUYUK * L_, DETAY_EN_AZ_YARI * h)
    sigan = [m for m in DETAY_OLCEK if m * R <= en_yari]
    if not sigan and min(DETAY_OLCEK) * R <= max(DETAY_EN_GEVSEK * L_, 20.0 * h):
        # Öbek geniş (iki uç DETAY_BAG kadar ayrı): ölçü ATILMAZ, en küçük
        # büyütmeyle kurulur - detay görünüşün DETAY_EN_GEVSEK'ini aşmasın.
        sigan = [min(DETAY_OLCEK)]
    if not sigan:
        return None
    # yeterli büyütme (en kısa ölçü 2,5 yazı boyu): fazlası kâğıtta yer
    # kaplar, ana görünüşün ölçeğini düşürür (P01 DETAY F: 4:1'de tek
    # slot için koca daire)
    olcek = next((m for m in sigan if m * en_kisa >= 2.5 * h), max(sigan))
    Rd = R * olcek
    yer_ = _detay_yeri(msp, hucre, Rd + DETAY_OLCU_PAYI * h, h) if hucre else None
    if yer_ is None:
        yer_ = _detay_serbest_yeri(msp, gkutu, Rd + DETAY_OLCU_PAYI * h, h, engel=engel)
    if yer_ is None:
        return None
    H = next(harf, None)
    if H is None:
        return None
    dc, hc_ = yer_
    if hc_ is not None:
        kullanilan.append(hc_)
    # ana görünüşte işaret: ince daire + harf. Daire bir yazının
    # üstünden geçmez: yazıların olduğu yerde boşluk bırakılır.
    _yazidan_kacan_daire(msp, c, R, h)
    _detay_harfi(msp, c, R, H, h)
    # büyütülmüş geometri
    dx, dy = kaydir[gad]
    for kat in ("GORUNEN", "GIZLI"):
        for p in kenarlar[gad].get(kat, []):
            for a, b in zip(p, p[1:]):
                a2, b2 = (a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)
                kp = _daire_kirp(a2, b2, c, R)
                if kp is None:
                    continue
                q1 = ((kp[0][0] - c[0]) * olcek + dc[0], (kp[0][1] - c[1]) * olcek + dc[1])
                q2 = ((kp[1][0] - c[0]) * olcek + dc[0], (kp[1][1] - c[1]) * olcek + dc[1])
                if math.dist(q1, q2) > 1e-6:
                    msp.add_line(q1, q2, dxfattribs={"layer": kat})
    msp.add_circle(dc, Rd, dxfattribs={"layer": "OLCU"})
    ol = f"{olcek:g}".replace(".", ",")
    _yaz(msp, f"DETAY {H} ({ol}:1)", dc[0] - Rd, dc[1] + Rd + 1.0 * h, 1.3 * h)
    return H, olcek, dc, Rd


def _bos_hucreler(gkutu, h):
    """İzdüşüm ızgarasının BOŞ hücreleri: SAĞ / SOL / ARKA sütunu ile ÜST
    satırının kesiştiği yer. Detay buraya konursa pafta ızgarası
    bozulmaz (sütun ve satır sayısı değişmez)."""
    out = []
    if "UST" in gkutu:
        u = gkutu["UST"]
        on = gkutu.get("ON")
        for yan in ("SAG", "SOL", "ARKA"):
            if yan in gkutu:
                g = gkutu[yan]
                x0, y0, x1, y1 = g[0], u[1], g[2], u[3]
                # Hücre görünüşlerin arasındaki boşluğun YARISINA kadar
                # büyür (ÖN'e doğru): SAĞ'ın eni x ÜST'ün boyu (105 x 105)
                # detaya hiç yer bırakmıyordu, kâğıttaki boşluk ise çok
                # daha büyüktü (Televre P04). Yer yine ölçülür.
                if on is not None:
                    if g[2] <= on[0]:
                        x1 = max(x1, (g[2] + on[0]) / 2.0)
                    elif g[0] >= on[2]:
                        x0 = min(x0, (on[2] + g[0]) / 2.0)
                    if u[3] <= on[1]:
                        y1 = max(y1, (u[3] + on[1]) / 2.0)
                out.append((x0, y0, x1, y1))
    return out


def _detay_serbest_yeri(msp, gkutu, yari, h, engel=()):
    """Detayın merkezi, resmin ALTINDAKİ serbest alanda: çizilmiş her şeyin
    altında bir sıra, soldan sağa, hiçbir çizime değmeyen ilk yer.
    Döner: (merkez, None)."""
    dolu = _varlik_kutulari(msp) + list(engel)
    if not dolu:
        return None
    x0 = min(g[0] for g in gkutu.values())
    x1 = max(max(g[2] for g in gkutu.values()), x0 + 2 * yari)
    alt = min(k[1] for k in dolu)
    for sira in range(3):
        cy = alt - 6.0 * h - yari - sira * (2 * yari + 6.0 * h)
        x = x0 + yari
        while x <= x1 - yari + 1e-6:
            kutu_ = (x - yari, cy - yari, x + yari, cy + yari)
            if not _cakisiyor(kutu_, dolu, 1.0 * h):
                return (x, cy), None
            x += 0.5 * yari
    return None


def _detay_yeri(msp, hucreler, yari, h):
    """Detayın merkezi: boş hücrenin İÇİNDE, hiçbir çizime değmeyen yer.
    Hücreden taşan yer seçilmez. Döner: (merkez, hücre) ya da None."""
    dolu = _varlik_kutulari(msp)
    for hc in hucreler:
        if 2 * yari > min(hc[2] - hc[0], hc[3] - hc[1]):
            continue
        cx0, cy0 = (hc[0] + hc[2]) / 2.0, (hc[1] + hc[3]) / 2.0
        ax, ay = (hc[2] - hc[0]) / 2.0 - yari, (hc[3] - hc[1]) / 2.0 - yari
        for fx, fy in ((0, 0), (0, 1), (0, -1), (-1, 0), (1, 0), (-1, 1), (1, 1),
                       (-1, -1), (1, -1)):
            cx, cy = cx0 + fx * ax, cy0 + fy * ay
            kutu_ = (cx - yari, cy - yari, cx + yari, cy + yari)
            if not _cakisiyor(kutu_, dolu, 0.5 * h):
                return (cx, cy), hc
    return None


def _yazidan_kacan_daire(msp, c, R, h, n=360):
    """c merkezli R yarıçaplı ince daire; yazı kutularının (0,2 h payla)
    içine düşen kısımları çizilmez - değer hiçbir çizgiyle kesilmez."""
    dolu = [(k[0] - 0.2 * h, k[1] - 0.2 * h, k[2] + 0.2 * h, k[3] + 0.2 * h)
            for k in _yazi_kutulari(msp)]
    serbest = []
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        x, y = c[0] + R * math.cos(a), c[1] + R * math.sin(a)
        serbest.append(not any(k[0] <= x <= k[2] and k[1] <= y <= k[3] for k in dolu))
    if all(serbest):
        msp.add_circle(c, R, dxfattribs={"layer": "OLCU"})
        return
    # serbest ardışık dilimleri yay olarak çiz
    i0 = next((i for i in range(n) if not serbest[i]), 0)
    parca = []
    for j in range(1, n + 1):
        i = (i0 + j) % n
        if serbest[i]:
            if not parca or parca[-1][1] != j - 1:
                parca.append([j, j])
            else:
                parca[-1][1] = j
    for b0, b1 in parca:
        a0 = 360.0 * ((i0 + b0) % n) / n
        a1 = 360.0 * ((i0 + b1 + 1) % n) / n
        msp.add_arc(c, R, a0, a1, dxfattribs={"layer": "OLCU"})


def _harf_koy(msp, adaylar, H, h):
    """Detay harfini ilk BOŞ adaya koyar: hiçbir yazıya ve hiçbir çizgiye
    (kontur, gizli, eksen, ölçü, kılavuz) değmeyen yer - ölçülür. Harf
    önce konup sonra kontrol edilmiyordu; çizgi ve kontur üstünde kalan
    harfler oldu (18 resim). Döner: True / False."""
    dolu = _yazi_kutulari(msp)
    xs = [a[0] for a in adaylar]
    ys = [a[1] for a in adaylar]
    alan = (min(xs) - 4 * h, min(ys) - 4 * h, max(xs) + 4 * h, max(ys) + 4 * h)
    cz = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "EKSEN", "OLCU", "BOLGE"))
    e = None
    for x, y in adaylar:
        if e is None:
            e = _yaz(msp, H, x - 0.5 * h, y - 0.65 * h, 1.3 * h, kat="OLCU")
        else:
            e.set_placement((x - 0.5 * h, y - 0.65 * h))
        k = _yazi_siniri(e)
        if k and not _cakisiyor(k, dolu, 0.2 * h) and not _cizgi_kesiyor(k, cz, 0.1 * h):
            return True
    if e is not None:
        msp.delete_entity(e)
    return False


def _detay_harfi(msp, c, R, H, h):
    ad = []
    for uz in (1.3, 2.3, 3.5, 5.0):
        for a in (45, 135, 315, 225, 90, 0, 180, 270, 22, 68, 112, 158, 202, 248, 292, 338):
            ra = math.radians(a)
            ad.append((c[0] + math.cos(ra) * (R + uz * h), c[1] + math.sin(ra) * (R + uz * h)))
    _harf_koy(msp, ad, H, h)


def _bant_harfi(msp, k, H, h):
    """Bant çerçevesinin harfi: köşelerin dışında, sonra kenar ortalarında,
    giderek uzaklaşarak - ölçülen ilk boş yer."""
    ad = []
    for uz in (0.9, 2.0, 3.2, 4.5):
        ad += [(k[0] + 0.6 * h, k[3] + uz * h), (k[2] - 0.6 * h, k[3] + uz * h),
               (k[0] + 0.6 * h, k[1] - uz * h), (k[2] - 0.6 * h, k[1] - uz * h),
               (k[0] - uz * h, (k[1] + k[3]) / 2.0), (k[2] + uz * h, (k[1] + k[3]) / 2.0),
               ((k[0] + k[2]) / 2.0, k[3] + uz * h), ((k[0] + k[2]) / 2.0, k[1] - uz * h)]
    _harf_koy(msp, ad, H, h)


def _detay_uclar(k, c, dc, olcek):
    """Kayıp ölçünün detaydaki (büyütülmüş) iki ucu: detay dairesinin
    İÇİNDEKİ özellikler (merkeze en yakın olanlar)."""
    yat = k["yon"] == "yatay"

    def don(v, d):
        x, y = (v + k["kayd"], d + k["dkay"]) if yat else (d + k["dkay"], v + k["kayd"])
        return ((x - c[0]) * olcek + dc[0], (y - c[1]) * olcek + dc[1])
    m_ = c[1] if yat else c[0]
    da = min(k["dik_a"] or k["dik_b"], key=lambda d: abs(d + k["dkay"] - m_))
    db = min(k["dik_b"] or k["dik_a"], key=lambda d: abs(d + k["dkay"] - m_))
    return don(k["a"], da), don(k["b"], db)


def _detay_takas(msp, kalan, kobj, yerler, c, dc, olcek, Rd, h, yabanci):
    """Detayda yer bulamayan ölçü için TAKAS: uzatma çizgisinin yolundaki
    (iki ucun sütun / satır koridoru) daha önce konmuş detay ölçüleri
    geçici kaldırılır, ölçü konur, kaldırılanlar yeniden yerleştirilir.
    Biri yer bulamazsa her şey geri alınır. Önce gelen önce yer buluyor,
    uzun uzatma çizgili (uçları ayrı sırada) ölçü hep sonda kalıyordu
    (Televre P04 175 -> 200, Karluna P10 "2x 61").
    yerler: {id(k): konan varlık handle'ları}. Döner: hâlâ konamayanlar."""
    def _sil(hs):
        for e in list(msp):
            if e.dxf.handle in hs:
                try:
                    ad = e.dxf.get("geometry", None) if e.dxftype() == "DIMENSION" else None
                    msp.delete_entity(e)
                    if ad and ad in msp.doc.blocks:
                        msp.doc.blocks.delete_block(ad, safe=False)
                except Exception:
                    pass

    def _koy(k):
        once = {e.dxf.handle for e in msp}
        if _detay_olcu(msp, k, c, dc, olcek, Rd, h, yabanci):
            yerler[id(k)] = {e.dxf.handle for e in msp} - once
            return True
        return False
    out = []
    for k in kalan:
        p1, p2 = _detay_uclar(k, c, dc, olcek)
        yat = k["yon"] == "yatay"
        kor = []
        for p in (p1, p2):
            if yat:
                kor.append((p[0] - 0.6 * h, min(p1[1], p2[1]) - 16 * h,
                            p[0] + 0.6 * h, max(p1[1], p2[1]) + 16 * h))
            else:
                kor.append((min(p1[0], p2[0]) - 16 * h, p[1] - 0.6 * h,
                            max(p1[0], p2[0]) + 16 * h, p[1] + 0.6 * h))
        engel = []
        for kid, hs in list(yerler.items()):
            # yalnız YAZI kutuları: ölçünün çizgileri koridorda olabilir,
            # engel yazıdır (uzatma çizgisi yazıdan geçemez)
            kts = []
            for e in msp:
                if e.dxf.handle not in hs:
                    continue
                if e.dxftype() == "DIMENSION":
                    kt = _olcu_yazi_kutusu(type("D", (), {"dimension": e})())
                    if kt:
                        kts.append(kt)
                elif e.dxftype() in ("TEXT", "MTEXT"):
                    kt = _yazi_siniri(e)
                    if kt:
                        kts.append(kt)
            if any(_cakisiyor(kt, kor) for kt in kts):
                engel.append(kobj[kid])
        if not engel or len(engel) > 8:
            out.append(k)
            continue
        for kj in engel:
            _sil(yerler.pop(id(kj)))
        ok = _koy(k)
        geri = []
        for kj in engel:
            if not _koy(kj):
                break
            geri.append(kj)
        if ok and len(geri) == len(engel):
            continue
        # geri al: yeni konanları sil, eskileri yeniden koy
        for kk in ([k] if ok else []) + geri:
            _sil(yerler.pop(id(kk), set()))
        for kj in engel:
            _koy(kj)
        out.append(k)
    return out


def _detay_olcu(msp, k, c, dc, olcek, Rd, h, yabanci):
    """Kayıp ölçüyü detayda çizer (büyütülmüş koordinatta)."""
    yat = k["yon"] == "yatay"
    p1, p2 = _detay_uclar(k, c, dc, olcek)
    dolu = _yazi_kutulari(msp)
    alan = (dc[0] - Rd - 10 * h, dc[1] - Rd - 10 * h, dc[0] + Rd + 10 * h, dc[1] + Rd + 10 * h)
    cz = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    for j in range(10):
        for yan in (1, -1):
            if yat:
                cizgi = ((max(p1[1], p2[1]) + (1.5 + 1.4 * j) * h) if yan > 0
                         else (min(p1[1], p2[1]) - (1.5 + 1.4 * j) * h))
            else:
                cizgi = ((max(p1[0], p2[0]) + (1.5 + 1.4 * j) * h) if yan > 0
                         else (min(p1[0], p2[0]) - (1.5 + 1.4 * j) * h))
            if _ara_dene(msp, k["yon"], p1, p2, cizgi, float(yan), h, k.get("metin"),
                         dolu, cz, yabanci) is not None:
                return True
    # Uçları ayrı sıralarda (y 13 ile 222) olan ölçüde iki ucun dışındaki
    # hat uzun uzatma çizgisiyle detaydaki yazıları kesiyordu (Televre P04
    # 175 -> 200): hat UÇLARDAN BİRİNİN yanında, iki ucun ARASINDA da
    # denenir (ISO 129: uzatma çizgisi ölçü çizgisine kadar gider, yönü
    # serbest).
    u1, u2 = (p1[1], p2[1]) if yat else (p1[0], p2[0])
    if abs(u1 - u2) > 4.0 * h:
        for j in range(6):
            for uc in (u1, u2):
                for yan in (1, -1):
                    cizgi = uc + yan * (1.5 + 1.4 * j) * h
                    if min(u1, u2) < cizgi < max(u1, u2) and _ara_dene(
                            msp, k["yon"], p1, p2, cizgi, float(yan), h, k.get("metin"),
                            dolu, cz, yabanci) is not None:
                        return True
    return False


def _hat_alani(yatay, cizgi, disa, alt, ust, h):
    u = cizgi + disa * 8 * h
    if yatay:
        return (alt, min(cizgi, u) - h, ust, max(cizgi, u) + h)
    return (min(cizgi, u) - h, alt, max(cizgi, u) + h, ust)


def ayna_ayni(ka, kb, boy, oran=0.97):
    """İki ayna görünüşün (SAĞ / SOL) GÖRÜNEN çizgileri, biri aynaya
    çevrilince aynı mı? Çizgiler boyun 1/400'ü aralıklı ızgarada
    örneklenir; ortak hücre oranı (Jaccard) >= oran ise aynıdır."""
    hucre = max(boy / 400.0, 0.2)

    def iz(k, ayna):
        pts = [q for p in k.get("GORUNEN", []) for q in p]
        if not pts:
            return set()
        x0, x1 = min(q[0] for q in pts), max(q[0] for q in pts)
        y0 = min(q[1] for q in pts)
        out = set()
        for p in k.get("GORUNEN", []):
            for a, b in zip(p, p[1:]):
                n = max(1, int(math.dist(a, b) / hucre))
                for t in range(n + 1):
                    x = a[0] + (b[0] - a[0]) * t / n
                    y = a[1] + (b[1] - a[1]) * t / n
                    x = (x1 - x) if ayna else (x - x0)
                    out.add((round(x / hucre), round((y - y0) / hucre)))
        return out
    A, B = iz(ka, False), iz(kb, True)
    if not A or not B:
        return False
    # bir hücrelik kaymayı affet (yuvarlama)
    B2 = {(x + dx, y + dy) for x, y in B for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    A2 = {(x + dx, y + dy) for x, y in A for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    ortak_a = sum(1 for q in A if q in B2) / len(A)
    ortak_b = sum(1 for q in B if q in A2) / len(B)
    return min(ortak_a, ortak_b) >= oran


def ana_gorunus(gkutu, o):
    """ANA görünüş: parça döndürülmediği için ÖN olmak zorunda değil - en çok
    bilgi veren görünüş (bkz. _gorunus_puani: alan + o yönden daire görünen
    delik / slot). Eşitlikte ÖN."""
    puan = [0.0, 0.0, 0.0]
    try:
        alan = {}
        for gad, gk in gkutu.items():
            if gad in GOR_EKSEN:
                i = "XYZ".index("XYZ"[max(range(3), key=lambda k: abs(GORUNUS[gad][0][k]))])
                alan[i] = max(alan.get(i, 0.0), (gk[2] - gk[0]) * (gk[3] - gk[1]))
        oz = [0, 0, 0]
        for d in (o or {}).get("delikler") or []:
            if d.get("eksen") in ("X", "Y", "Z"):
                oz["XYZ".index(d["eksen"])] += d.get("adet", 1)
        for sl in (o or {}).get("slotlar") or []:
            if sl.get("eksen") in ("X", "Y", "Z"):
                oz["XYZ".index(sl["eksen"])] += 2
        top = max(1, sum(oz))
        en_alan = max(alan.values()) if alan else 1.0
        puan = [alan.get(i, 0.0) / max(en_alan, 1e-9) + 0.6 * oz[i] / top for i in range(3)]
    except Exception:
        pass
    adaylar = [g for g in gkutu if g in GOR_EKSEN]
    if not adaylar:
        return ANA_GORUNUS

    def eks(g):
        return max(range(3), key=lambda k: abs(GORUNUS[g][0][k]))
    return max(adaylar, key=lambda g: (puan[eks(g)], g == ANA_GORUNUS, g in ("ON", "UST", "SAG")))


def gabari_plani(gkutu, sac_kesit=None, bukum_ekseni=None, ana=None):
    """Her GENEL ölçü (boy / en / yükseklik) BİR KEZ, EN NET göründüğü
    görünüşte verilir (ISO 129-1; kullanıcı: "kenar 54 ölçüsü kesitten
    ver, ölçü en net nerden görünüyorsa oradan verilir, ezbere değil").

    Mantık, sırayla:
      0. ANA GÖRÜNÜŞ (ÖN) kendi boyunu ve yüksekliğini HER ZAMAN taşır,
         en dışta (kullanıcı: "komple yükseklik nerde, önce dış
         ölçüler"). Konum ölçüleri onun içine girer; okuyan ana
         görünüşte parçanın büyüklüğünü başka görünüşe bakmadan görür.
         Öbür görünüşler yalnız ÖN'ün gösteremediği ölçüyü (derinlik)
         verir.
      1. Bükümlü sacın profil ölçüleri KESİT görünüşünde nettir (sac
         kalınlığı, kanat yükseklikleri orada okunur).
      2. Yoksa o ölçüyü taşıyan görünüşlerden İNCE ŞERİT olmayanı: görünüşün
         öbür kenarı ne kadar uzunsa ölçü o kadar rahat okunur. 1854 x 54'lük
         bir şeritte 54'ü okumak zordur.
    Döner: {görünüş: {"yatay", "dusey"}} - hangi görünüşte hangi gabari."""
    sac_kesit = sac_kesit or {}
    b_ek = None
    if bukum_ekseni:
        b_ek = max(range(3), key=lambda i: abs(bukum_ekseni[i]))
    aday = defaultdict(list)          # model ekseni -> [(puan, gad, yon)]
    for gad, gk in gkutu.items():
        if gad not in GOR_EKSEN:
            continue
        i1, i2, _tx, _ty = GOR_EKSEN[gad]
        G, Y = gk[2] - gk[0], gk[3] - gk[1]
        for eks, yon, oteki, bu in ((i1, "yatay", Y, G), (i2, "dusey", G, Y)):
            puan = oteki / max(G, Y, 1e-9)
            if gad == (ana or ANA_GORUNUS):
                puan += 200.0
            if gad in sac_kesit and eks != b_ek:
                puan += 100.0
            aday[eks].append((puan, gad, yon))
    plan = defaultdict(set)
    for eks, lst in aday.items():
        _p, gad, yon = max(lst)
        plan[gad].add(yon)
    return plan


def _gabari_yolu_ayir(msp, gkutu, plan, h, boy=40.0):
    """Gabari ölçüsünün uzatma çizgilerinin gideceği yolu geçici çizgiyle
    ayırır (OLCU katmanında: yazı yerleştirmeleri bu çizgilerden kaçar).
    Döner: silinecek geçici çizgiler."""
    out = []
    for gad, gk in gkutu.items():
        for yon in plan.get(gad, ()):
            if yon == "yatay":            # gabari altta: iki düşey uzatma
                for x in (gk[0], gk[2]):
                    out.append(msp.add_line((x, gk[1]), (x, gk[1] - boy * h),
                                            dxfattribs={"layer": "OLCU"}))
            else:                         # gabari solda: iki yatay uzatma
                for y in (gk[1], gk[3]):
                    out.append(msp.add_line((gk[0], y), (gk[0] - boy * h, y),
                                            dxfattribs={"layer": "OLCU"}))
    return out


def gabari_olculeri(msp, gkutu, sinir, h, plan=None):
    """Görünüşün TOPLAM ölçüsü - en dışarıda.

    Konum ölçülerinden SONRA çizilir ve onların ÖLÇÜLEN sınırının
    dışına konur. Önce çizilip yeri tahmin edilirse, bir konum ölçüsü
    yerini bulamayıp alt kademeye kaçtığında gabarinin içine düşüyor
    ve ölçü çizgileri kesişiyordu. Teknik resimde küçük ölçüler
    içeride, toplam ölçü en dışarıdadır.
    Döner: konamayan gabari sayısı (0 olmalı; rapora yazılır)."""
    eksik = 0                             # yeri bulunamayan gabari (0 olmalı)
    dolu = _varlik_kutulari(msp)          # resimde ne varsa, ölçülmüş
    yazilar_ = _yazi_kutulari(msp)
    for gad, gk in gkutu.items():
        alt, sol = sinir.get(gad, (gk[1], gk[0]))
        for yon, tabanlar in (
                ("yatay", [min(alt, gk[1]) - (2.4 + KOSU_ADIM * i) * h
                           for i in range(10)]),
                ("dusey", [min(sol, gk[0]) - (2.4 + KOSU_ADIM * i) * h
                           for i in range(10)])):
            if plan is not None and yon not in plan.get(gad, ()):
                continue                  # bu genel ölçü başka görünüşte
            kondu = False
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
                # gabarinin uzatma çizgileri de önceden konmuş bir yazının
                # içinden geçmemeli (P01: ÖN'ün gabarisi "41,4"ü kesiyordu)
                if ky is not None and _kendi_ustunde(dim, ky, h):
                    # kısa gabari: rakam iki uzatma çizgisinin arasına
                    # sığmıyor - yana, kılavuzla (P10'un 22,3'ü)
                    _olcu_sil(msp, dim)
                    if yon == "yatay":
                        p1, p2, m0 = (gk[0], gk[1]), (gk[2], gk[1]), gk[2]
                    else:
                        p1, p2, m0 = (gk[0], gk[1]), (gk[0], gk[3]), gk[3]
                    dim = None
                    for m_ in (m0 + 2.5 * h, m0 + 4.0 * h, (gk[0] if yon == "yatay" else gk[1]) - 2.5 * h):
                        dim = _disari_ciz(msp, yon, p1, p2, t, -1.0, m_, h)
                        ky = _olcu_yazi_kutusu(dim) if dim is not None else None
                        if (dim is not None and ky and not _cakisiyor(ky, dolu, 0.2 * h)
                                and not _kendi_ustunde(dim, ky, h)
                                and not _dim_yaziya_degiyor(dim, yazilar_, 0.05 * h)):
                            break
                        if dim is not None:
                            _olcu_sil(msp, dim)
                        dim = None
                    if dim is None:
                        continue
                    dolu.append(ky)
                    yazilar_.append(ky)
                    kondu = True
                    break
                if ky is None or (not _cakisiyor(ky, dolu, 0.2 * h)
                                  and not _dim_yaziya_degiyor(dim, yazilar_, 0.05 * h)):
                    if ky:
                        dolu.append(ky)
                        yazilar_.append(ky)
                    kondu = True
                    break
                _olcu_sil(msp, dim)
            if not kondu:
                eksik += 1
    return eksik


# ------------------------------------------------------------- ızgara bölgesi
IZGARA_EN_AZ = 12          # bu kadar kesimden az öbek ızgara sayılmaz
IZGARA_BAG = 2.5           # iki kesim arası boşluk, küçük ölçünün bu katına kadar: aynı öbek
IZGARA_EN_COK_KESIM = 4000


def _ic_teller(s, k):
    """k eksenine DİK düz yüzlerin iç telleri (delik, pencere, yuva):
    model koordinatında (i0, j0, i1, j1) kutuları; sacın iki yüzü aynı
    kesimi iki kez verir, bir kez sayılır."""
    i, j = [a for a in range(3) if a != k]
    kutular = set()
    ex = TopExp_Explorer(s, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        try:
            ad = BRepAdaptor_Surface(f)
            if ad.GetType() != GeomAbs_Plane:
                continue
            n = ad.Plane().Axis().Direction()
            nv = (n.X(), n.Y(), n.Z())
            if abs(abs(nv[k]) - 1.0) > 1e-6:
                continue
            dis = BRepTools.OuterWire_s(f)
            wx = TopExp_Explorer(f, TopAbs_WIRE)
            while wx.More():
                w = wx.Current()
                wx.Next()
                if w.IsSame(dis):
                    continue
                b = Bnd_Box()
                BRepBndLib.Add_s(w, b)
                x0, y0, z0, x1, y1, z1 = b.Get()
                lo, hi = (x0, y0, z0), (x1, y1, z1)
                kutular.add((round(lo[i], 2), round(lo[j], 2), round(hi[i], 2), round(hi[j], 2)))
                if len(kutular) > IZGARA_EN_COK_KESIM:
                    return []
        except Exception:
            continue
    return sorted(kutular)


def izgara_obekleri(kutular, en_az=IZGARA_EN_AZ, bag=IZGARA_BAG):
    """Sık kesimleri öbekler (tek bağlantılı kümeleme): iki kesim arası
    boşluk, küçük olanın dar ölçüsünün `bag` katından azsa aynı öbek.
    En az `en_az` kesimli, en az iki sıra ve iki sütunlu öbek IZGARADIR.
    Döner: [(x0, y0, x1, y1, adet)]"""
    n = len(kutular)
    if n < en_az:
        return []
    ata = list(range(n))

    def bul(a):
        while ata[a] != a:
            ata[a] = ata[ata[a]]
            a = ata[a]
        return a
    dar = [max(1e-6, min(b[2] - b[0], b[3] - b[1])) for b in kutular]
    sira = sorted(range(n), key=lambda t: kutular[t][0])
    en_bag = bag * max(dar)
    for p in range(n):
        a = sira[p]
        A = kutular[a]
        for q in range(p + 1, n):
            b = sira[q]
            B = kutular[b]
            if B[0] - A[2] > en_bag:
                break
            gx = max(0.0, B[0] - A[2], A[0] - B[2])
            gy = max(0.0, B[1] - A[3], A[1] - B[3])
            if max(gx, gy) <= bag * min(dar[a], dar[b]):
                ra, rb = bul(a), bul(b)
                if ra != rb:
                    ata[ra] = rb
    obek = defaultdict(list)
    for t in range(n):
        obek[bul(t)].append(kutular[t])
    out = []
    for uye in obek.values():
        if len(uye) < en_az:
            continue
        sx = {round((b[0] + b[2]) / 2, 0) for b in uye}
        sy = {round((b[1] + b[3]) / 2, 0) for b in uye}
        if len(sx) < 2 or len(sy) < 2:
            continue               # tek sıra: dizi ölçüsü ("n x adım") verir
        out.append((min(b[0] for b in uye), min(b[1] for b in uye),
                    max(b[2] for b in uye), max(b[3] for b in uye), len(uye)))
    return out


def izgara_bolgeleri(s, gorunusler):
    """IZGARA (sık kesim) bölgeleri: {görünüş: [(x0, y0, x1, y1, adet)]} HAM
    izdüşümde.

    Kullanıcı: "ızgara başlangıcı, ızgara sonu; iç ölçüleri çoğu lazer,
    çok da elzem değil; bölgeyi işaretle - alt üst, sağ sol başlangıç
    çizgisi kesik çizgi". P01'de 424 pencere tek tek ölçülemezdi; bölgenin
    yeri datumdan verilir, içi lazer DXF'indedir."""
    out = {}
    eksen_obek = {}
    for gad in gorunusler:
        goz = GORUNUS[gad][0]
        k = max(range(3), key=lambda a: abs(goz[a]))
        if k not in eksen_obek:
            eksen_obek[k] = izgara_obekleri(_ic_teller(s, k))
        if not eksen_obek[k]:
            continue
        i, j = [a for a in range(3) if a != k]
        lst = []
        for x0, y0, x1, y1, n in eksen_obek[k]:
            ps = []
            for a_, b_ in ((x0, y0), (x1, y1)):
                p = [0.0, 0.0, 0.0]
                p[i], p[j] = a_, b_
                ps.append(izdusum(p, gad))
            lst.append((min(ps[0][0], ps[1][0]), min(ps[0][1], ps[1][1]),
                        max(ps[0][0], ps[1][0]), max(ps[0][1], ps[1][1]), n))
        out[gad] = lst
    return out


def izgara_ciz(msp, izgara, kaydir, gkutu, h):
    """Izgara bölgesinin sınırı: KESİK çizgi dikdörtgen. Kesik boyu yazı
    boyuna göre: 1:20 paftada 2 mm'lik kesik kâğıtta düz çizgi görünür."""
    doc = msp.doc
    ad = f"BOLGE_{h:.2f}".replace(".", "_")
    try:
        if ad not in doc.linetypes:
            doc.linetypes.add(ad, pattern=[1.6 * h, 1.0 * h, -0.6 * h])
        doc.layers.get("BOLGE").dxf.linetype = ad
    except Exception:
        pass
    for gad, lst in (izgara or {}).items():
        if gad not in gkutu:
            continue
        dx, dy = kaydir[gad]
        for x0, y0, x1, y1, _n in lst:
            p = 0.4 * h                    # kesimlerin üstüne binmesin
            msp.add_lwpolyline([(x0 - p + dx, y0 - p + dy), (x1 + p + dx, y0 - p + dy),
                                (x1 + p + dx, y1 + p + dy), (x0 - p + dx, y1 + p + dy)],
                               close=True, dxfattribs={"layer": "BOLGE"})


# ------------------------------------------------------ bükümlü sac: kanat ölçüleri
def sac_duvarlari(s, eksen, t, tol=0.05):
    """Bükümlü sacın KESİTİNDEKİ düz duvarlar ve DIŞTAN DIŞA boyları.

    Kullanıcı: "dıştan dışa tüm büküm çıkıntıları mutlaka ölçülü olmalı"
    - ABKANT tablosundaki kanat dış ölçüsü: duvarın bükümlü ucu, komşu
    duvarın DIŞ yüzüyle kesiştiği SANAL KESKİN KÖŞEYE kadar uzar; serbest
    uçta sacın ucudur.

    Kesit düzleminde (büküm eksenine dik) her duvar kalınlığı t olan iki
    paralel düz yüzdür; yönü ne olursa olsun bulunur. Bükümlü uçta komşu
    duvar, aynı büküm silindirine teğet olan duvardır; iki duvarın yüz
    doğrularının dört kesişiminden büküm merkezine EN UZAK olanı dış
    köşedir. Eğik komşu (Z sacın 2,5° kademesi) da böylece doğru hesaplanır.

    Yalnız model eksenlerine oturan duvarlar döner (ölçüsü yatay/düşey
    çizilebilir); eğik duvarın açısı açı ölçüsüyle verilir. Bükümlü ucunun
    komşusu bulunamayan duvar döndürülmez (yanlış ölçü yazılmaz).
    Döner: [{"n": normal ekseni, "j": boy ekseni, "a", "b": dış uçlar,
             "sev": (yüz1, yüz2)}]"""
    i_, j_ = [q for q in range(3) if q != eksen]
    kb = kutu(s)
    boy = kb[eksen + 3] - kb[eksen]
    yuz = []                 # (n2, d, umin, umax)
    sil = []                 # (merkez2, r)
    ex = TopExp_Explorer(s, TopAbs_FACE)
    while ex.More():
        f = ex.Current()
        ex.Next()
        try:
            ad = BRepAdaptor_Surface(TopoDS.Face_s(f))
            tip = ad.GetType()
        except Exception:
            continue
        if tip == GeomAbs_Cylinder:
            c = ad.Cylinder()
            dr = c.Axis().Direction()
            if abs(abs((dr.X(), dr.Y(), dr.Z())[eksen]) - 1.0) < 1e-6:
                m_ = c.Location()
                m3 = (m_.X(), m_.Y(), m_.Z())
                sil.append(((m3[i_], m3[j_]), c.Radius()))
            continue
        if tip != GeomAbs_Plane:
            continue
        n = ad.Plane().Axis().Direction()
        n3 = (n.X(), n.Y(), n.Z())
        if abs(n3[eksen]) > 1e-6:
            continue
        pts = _yuz_ornekle(f)
        if not pts:
            continue
        n2 = (n3[i_], n3[j_])
        L = math.hypot(*n2)
        n2 = (n2[0] / L, n2[1] / L)
        # yön birliği: normalin ilk sıfır olmayan bileşeni artı
        if n2[0] < -1e-9 or (abs(n2[0]) <= 1e-9 and n2[1] < 0):
            n2 = (-n2[0], -n2[1])
        u2 = (-n2[1], n2[0])
        d = sum(n2[0] * q[i_] + n2[1] * q[j_] for q in pts) / len(pts)
        us = [u2[0] * q[i_] + u2[1] * q[j_] for q in pts]
        es = [q[eksen] for q in pts]
        yuz.append((n2, d, min(us), max(us), min(es), max(es)))
    # Aynı düzlemde, kesitte üst üste gelen yüz PARÇALARI tek yüzdür: slot
    # ve delikler gövdeyi boyuna parçalara böler (P06). Uzunluk şartı
    # parçaların toplam boyuna bakar; kısa kesik (büküm boşaltması) yine elenir.
    obek = []
    for y in sorted(yuz, key=lambda y: (round(y[0][0], 4), round(y[0][1], 4), round(y[1], 2), y[2])):
        o_ = obek[-1] if obek else None
        if (o_ and abs(o_[0][0] - y[0][0]) < 1e-4 and abs(o_[0][1] - y[0][1]) < 1e-4
                and abs(o_[1] - y[1]) < 0.01 and y[2] <= o_[3] + tol):
            o_[3] = max(o_[3], y[3])
            o_[4] = min(o_[4], y[4])
            o_[5] = max(o_[5], y[5])
        else:
            obek.append(list(y))
    yuz = [tuple(o_[:4]) for o_ in obek if o_[5] - o_[4] >= 0.5 * boy]
    duvar = []
    kul = set()
    for p_, A in enumerate(yuz):
        if p_ in kul or A[3] - A[2] <= t + tol:
            continue
        for q_ in range(p_ + 1, len(yuz)):
            B = yuz[q_]
            if q_ in kul or abs(A[0][0] * B[0][1] - A[0][1] * B[0][0]) > 1e-4:
                continue
            if abs(abs(B[1] - A[1]) - t) > tol or min(A[3], B[3]) - max(A[2], B[2]) <= 0:
                continue
            kul.update((p_, q_))
            duvar.append({"n2": A[0], "d": (min(A[1], B[1]), max(A[1], B[1])),
                          "u": (min(A[2], B[2]), max(A[3], B[3]))})
            break

    def nokta(w, uu, dd):
        n2 = w["n2"]
        u2 = (-n2[1], n2[0])
        return (n2[0] * dd + u2[0] * uu, n2[1] * dd + u2[1] * uu)

    def kesisim(n1, d1, n2, d2):
        det = n1[0] * n2[1] - n1[1] * n2[0]
        if abs(det) < 1e-9:
            return None
        return ((d1 * n2[1] - d2 * n1[1]) / det, (n1[0] * d2 - n2[0] * d1) / det)

    def bukum_ucu(w, uu):
        """Duvarın uu ucuna teğet büküm silindiri: (merkez, r) ya da None."""
        u2 = (-w["n2"][1], w["n2"][0])
        for c2, r in sil:
            cu = u2[0] * c2[0] + u2[1] * c2[1]
            cd = w["n2"][0] * c2[0] + w["n2"][1] * c2[1]
            if abs(cu - uu) > tol:
                continue
            if any(abs(abs(cd - dd) - rr) <= tol for dd in w["d"] for rr in (r, r + t, r - t)):
                return c2, r
        return None
    temiz = []
    for w in duvar:
        uclar = []
        iyi = True
        for uu in w["u"]:
            bk = bukum_ucu(w, uu)
            if bk is None:                 # serbest uç
                uclar.append(uu)
                continue
            c2, r = bk
            komsu = [v for v in duvar if v is not w and any(
                bukum_ucu(v, vu) is not None and math.dist(bukum_ucu(v, vu)[0], c2) <= tol
                for vu in v["u"])]
            if not komsu:
                iyi = False
                break
            v = komsu[0]
            en = None
            for d1 in w["d"]:
                for d2 in v["d"]:
                    X = kesisim(w["n2"], d1, v["n2"], d2)
                    if X is not None and (en is None or math.dist(X, c2) > en[0]):
                        en = (math.dist(X, c2), X)
            if en is None:
                iyi = False
                break
            u2 = (-w["n2"][1], w["n2"][0])
            uclar.append(u2[0] * en[1][0] + u2[1] * en[1][1])
        if not iyi:
            continue
        n2 = w["n2"]
        if abs(abs(n2[0]) - 1.0) < 1e-6:
            n_ax, j_ax = i_, j_
        elif abs(abs(n2[1]) - 1.0) < 1e-6:
            n_ax, j_ax = j_, i_
        else:
            continue                        # eğik duvar: açı ölçüsü verir
        p1 = nokta(w, uclar[0], w["d"][0])
        p2 = nokta(w, uclar[1], w["d"][0])
        k1 = p1[0] if j_ax == i_ else p1[1]
        k2 = p2[0] if j_ax == i_ else p2[1]
        sev = tuple(sorted(dd * (n2[0] if n_ax == i_ else n2[1]) for dd in w["d"]))
        temiz.append({"n": n_ax, "j": j_ax, "sev": sev, "a": min(k1, k2), "b": max(k1, k2)})
    return temiz


def kanat_uyarilari(duvar, tol=1.0):
    """NEREDEYSE EŞİT kanatlar: aynı yöndeki iki kanadın dış ölçüsü
    birbirinden 1 mm'den az farklıysa büyük ihtimalle modelleme hatasıdır
    (P03: sol kanat 39,5, sağ kanat 40 - sol dudak 0,5 mm aşağıda).
    Program modeldekini yazar; tasarımcıya uyarı döner."""
    out = []
    if not duvar:
        return out
    for i, a in enumerate(duvar):
        for b in duvar[i + 1:]:
            if a["n"] != b["n"] or a["j"] != b["j"]:
                continue
            # yalnız AYNA KARŞILIĞI olan kanatlar (C profilin iki yanı):
            # parçanın ortasına göre simetrik yerde ve aynı seviyeden başlar
            sev = [v for w in duvar for v in w["sev"] if w["n"] == a["n"]]
            orta = (min(sev) + max(sev)) / 2.0
            if abs((sum(a["sev"]) + sum(b["sev"])) / 4.0 - orta) > 1.0:
                continue
            if abs(a["a"] - b["a"]) > 0.05 and abs(a["b"] - b["b"]) > 0.05:
                continue
            la, lb = a["b"] - a["a"], b["b"] - b["a"]
            if 0.05 < abs(la - lb) < tol:
                out.append(f"kanatlar {XL.tr(round(max(la, lb), 2), 2)} / "
                           f"{XL.tr(round(min(la, lb), 2), 2)} mm, "
                           f"{XL.tr(round(abs(la - lb), 2), 2)} mm fark (modeli kontrol edin)")
    return out


def kalinlik_notu(msp, s, o, sac_kesit, kaydir, gkutu, h):
    """Bükümlü sacın KESİTİNDE sac kalınlığı: sacın içinde NOKTAYLA biten
    ince kılavuz + "t 1,5" (Chevalier: yüzeyi gösteren kılavuz okla değil
    noktayla biter). Kullanıcı: "kalınlık nerede" - yalnız başlıkta
    yazıyordu. Yeri ölçülür."""
    e = o.get("bukum_ekseni")
    t = o.get("sac_kalinlik_mm")
    if not e or not t:
        return False
    eksen = max(range(3), key=lambda i: abs(e[i]))
    try:
        duvar = sac_duvarlari(s, eksen, float(t))
    except Exception:
        return False
    gad = next((g for g in sac_kesit if g in gkutu), None)
    if not duvar or gad is None:
        return False
    i1, i2, _tx, _ty = GOR_EKSEN[gad]
    dx, dy = kaydir[gad]
    metin = f"t {XL.tr(float(t), 2)}"
    dolu = _yazi_kutulari(msp)
    gk = gkutu[gad]
    alan = (gk[0] - 20 * h, gk[1] - 20 * h, gk[2] + 20 * h, gk[3] + 20 * h)
    cz = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    for w in sorted(duvar, key=lambda w: -(w["b"] - w["a"])):
        m = [0.0, 0.0, 0.0]
        m[w["j"]] = (w["a"] + w["b"]) / 2.0
        m[w["n"]] = sum(w["sev"]) / 2.0
        if w["j"] not in (i1, i2) or w["n"] not in (i1, i2):
            continue
        px = model_ham(gad, "yatay", m[i1]) + dx
        py = model_ham(gad, "dusey", m[i2]) + dy
        for a in (45, 135, 315, 225, 60, 120, 300, 240):
            for uz in (3.0, 4.5, 6.0):
                ra = math.radians(a)
                qx, qy = px + math.cos(ra) * uz * h, py + math.sin(ra) * uz * h
                sag = math.cos(ra) >= 0
                tx = qx + (0.3 * h if sag else -0.3 * h)
                ty = qy - 0.5 * h
                ey = _yaz(msp, metin, tx, ty, h, kat="OLCU")
                k = _yazi_siniri(ey)
                if k and not sag:
                    ey.set_placement((tx - (k[2] - k[0]), ty))
                    k = _yazi_siniri(ey)
                kl = ((px, py), (qx, qy))
                if (k and not _cakisiyor(k, dolu, 0.2 * h) and not _cizgi_kesiyor(k, cz, 0.1 * h)
                        and not any(_parca_kutuda(kl[0], kl[1], d) for d in dolu)):
                    msp.add_line(kl[0], kl[1], dxfattribs={"layer": "OLCU"})
                    r_ = 0.18 * h
                    msp.add_circle((px, py), r_, dxfattribs={"layer": "OLCU"})
                    msp.add_solid([(px - r_ * 0.7, py - r_ * 0.7), (px + r_ * 0.7, py - r_ * 0.7),
                                   (px - r_ * 0.7, py + r_ * 0.7), (px + r_ * 0.7, py + r_ * 0.7)],
                                  dxfattribs={"layer": "OLCU"})
                    return True
                msp.delete_entity(ey)
    return False


def kanat_olculeri(msp, s, o, sac_kesit, kaydir, gkutu, h):
    """Bükümlü sacın kesit görünüşünde her duvarın DIŞTAN DIŞA ölçüsü.
    Gabarinin kendisi olan duvar tekrar yazılmaz. Döner: çizilen sayı."""
    e = o.get("bukum_ekseni")
    t = o.get("sac_kalinlik_mm")
    if not e or not t:
        return 0
    eksen = max(range(3), key=lambda i: abs(e[i]))
    try:
        duvar = sac_duvarlari(s, eksen, float(t))
    except Exception:
        return 0
    if not duvar:
        return 0
    kb = kutu(s)
    sayi = 0
    # AYNA görünüşlerde (SAĞ / SOL) aynı kesit iki kez görünür; kanat
    # ölçüleri yalnız ilkinde (her öznitelik bir kez)
    for gad in [g for g in sac_kesit if g in gkutu][:1]:
        gk = gkutu[gad]
        dx, dy = kaydir[gad]
        i1, i2, _tx, _ty = GOR_EKSEN[gad]
        yabanci = [(k[0] - 0.3 * h, k[1] - 0.3 * h, k[2] + 0.3 * h, k[3] + 0.3 * h)
                   for g, k in gkutu.items() if g != gad]
        yazili = set()
        grup = defaultdict(list)
        for w in sorted(duvar, key=lambda w: -(w["b"] - w["a"])):
            boy_ = w["b"] - w["a"]
            if abs(w["a"] - kb[w["j"]]) < 0.05 and abs(w["b"] - kb[w["j"] + 3]) < 0.05:
                continue             # gabari ölçüsü zaten bu
            yon = "yatay" if w["j"] == i1 else ("dusey" if w["j"] == i2 else None)
            if yon is None:
                continue
            dik_yon = "dusey" if yon == "yatay" else "yatay"
            a = model_ham(gad, yon, w["a"])
            b = model_ham(gad, yon, w["b"])
            dik = [model_ham(gad, dik_yon, v) for v in w["sev"]]
            kayd, dkay = (dx, dy) if yon == "yatay" else (dy, dx)
            lo, hi = ((gk[1] - dy, gk[3] - dy) if yon == "yatay"
                      else (gk[0] - dx, gk[2] - dx))
            anahtar = (yon, round(min(a, b), 2), round(max(a, b), 2))
            if anahtar in yazili:
                continue
            yazili.add(anahtar)
            r = {"a": min(a, b), "b": max(a, b), "metin": None, "dik": dik,
                 "_taraf": 0 if min(abs(v - lo) for v in dik) <= min(abs(hi - v) for v in dik) else 1,
                 "kayd": kayd, "dkay": dkay, "yon": yon}
            grup[(yon, r["_taraf"])].append(r)
        # AYNI YANDAKİ kanat ölçüleri TEK HİZADA (kullanıcı: "ölçü çizgileri
        # mümkün olduğu kadar aynı hizaya gitmeli, girintili çıkıntılı
        # değil"): hepsi aynı kademede denenir; biri sığmazsa hepsi birlikte
        # bir kademe dışarı. Hiçbir kademede olmazsa tek tek yerleşir.
        for (yon, taraf), lst in grup.items():
            sayi += _hizali_diz(msp, yon, taraf, lst, gk, h, yabanci)
    return sayi


def _hizali_diz(msp, yon, taraf, lst, gk, h, yabanci, en_cok=8):
    """Aynı yandaki iki uçlu ölçüleri tek hatta dizer. Döner: çizilen."""
    yatay = yon == "yatay"
    disa = -1.0 if taraf == 0 else 1.0
    kenar = (gk[1] if taraf == 0 else gk[3]) if yatay else (gk[0] if taraf == 0 else gk[2])
    dolu0 = _yazi_kutulari(msp)
    alan = (gk[0] - 30 * h, gk[1] - 30 * h, gk[2] + 30 * h, gk[3] + 30 * h)
    cz0 = _cizgi_parcalari(msp, alan, katman=("GORUNEN", "GIZLI", "OLCU", "EKSEN", "BOLGE"))
    for k in range(en_cok):
        cizgi = kenar + disa * (KOSU_ILK + KOSU_ADIM * k) * h
        dolu = list(dolu0)
        cizilen = []
        for r in lst:
            d = r["dik"]
            dk = ((min(d) if taraf == 0 else max(d)) + r["dkay"]) if d else kenar
            a, b = r["a"] + r["kayd"], r["b"] + r["kayd"]
            p1, p2 = ((a, dk), (b, dk)) if yatay else ((dk, a), (dk, b))
            dim = _ara_dene(msp, yon, p1, p2, cizgi, disa, h, None, dolu, cz0, yabanci)
            if dim is None:
                break
            ky = _olcu_yazi_kutusu(dim)
            if ky:
                dolu.append(ky)
            cizilen.append(dim)
        if len(cizilen) == len(lst):
            return len(cizilen)
        for dim in cizilen:
            _olcu_sil(msp, dim)
    n = 0
    for r in lst:
        if _ara_yerlestir(msp, yon, r, r["kayd"], r["dkay"], gk, h, yabanci):
            n += 1
    return n


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
                           f"{XL.tr(en_kucuk_r / t, 0, sade=False)} katı; bu kadar geniş "
                           f"yarıçap abkantta değil silindirde (kalender) "
                           f"yapılır."))
    uyari = ""
    if en_kucuk_r / t < r_k:
        uyari = (f"En küçük iç yarıçap {XL.tr(en_kucuk_r, 2, sade=False)} mm = kalınlığın "
                 f"{XL.tr(en_kucuk_r / t, 2, sade=False)} katı ({XL.tr(r_k)} katın altında). "
                 f"Bükülebilir ama çatlama riski var: malzeme kalitesine, "
                 f"hadde yönüne ve kalıbın keskinliğine bakın.")
    if kanatlar and en_kisa / t < kanat_k:
        return dict(olcu, yontem="rollform", kesinlik="olası", uyari=uyari,
                    neden=(f"Abkantta yapılamaz: en kısa kanat "
                           f"{XL.tr(en_kisa, 1, sade=False)} mm = kalınlığın {XL.tr(en_kisa / t, 1, sade=False)} "
                           f"katı; abkant için en az {XL.tr(kanat_k)} kat gerekir, "
                           f"daha kısa kanat V kalıbın ağzını tutmaz, parça "
                           f"kalıbın içine düşer. Rollform ya da başka bir "
                           f"yöntemle üretilmiş olmalı."))
    ek = ""
    if len(yaricaplar) >= 8 and boy_mm >= 1000:
        ek = (f" ({len(yaricaplar)} büküm ve {XL.tr(boy_mm, 0, sade=False)} mm boy rollform "
              f"için de tipiktir; seri büyükse orayı da değerlendirin.)")
    return dict(olcu, yontem="abkant", kesinlik="kesin", uyari=uyari,
                neden=(f"Bütün kanatlar en az kalınlığın {XL.tr(kanat_k)} katı "
                       f"(en kısası {XL.tr(en_kisa / t, 1, sade=False)} kat): abkantta "
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
                              f"({XL.tr(olc[2], 0, sade=False)} mm / t={XL.tr(t, 1, sade=False)} mm): sac değil")
        try:
            eksen = bukum_ekseni(ciftler)
            paralel = True
        except AcilimYok:
            eksen, paralel = None, False
        return {"sac": True, "tip": "bukumlu sac", "kalinlik_mm": round(t, 2),
                "bukum_sayisi": len(ciftler), "eksen_paralel": paralel,
                "eksen": eksen,
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
                             f"{XL.tr(min(ry) / t, 2, sade=False)}..{XL.tr(max(ry) / t, 2, sade=False)} x kalınlık; "
                             f"{kucuk} tanesi abkant sınırı {XL.tr(r_k)} katın "
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
                f"genişlik = kesit alanı / kalınlık = {XL.tr(a, 1, sade=False)} / {XL.tr(t, 2, sade=False)} = "
                f"{XL.tr(gen_orta, 1, sade=False)} mm (orta yüzey, K=0,50). Hacimle "
                f"doğrulandı: {XL.tr(a, 0, sade=False)} x {XL.tr(boy, 0, sade=False)} = {XL.tr(a * boy, 0, sade=False)} mm3, "
                f"parçanın hacmi {XL.tr(hac, 0, sade=False)} mm3."
                + (f" K={XL.tr(k_faktor)} icin {ic_say} bukumun toplam "
                   f"{XL.tr(math.degrees(ic_aci), 0, sade=False)} derecesinden {('+' if (duzelt) >= 0 else '') + XL.tr(duzelt, 1, sade=False)} mm "
                   f"duzeltme: {XL.tr(gen, 1, sade=False)} mm." if ic_say else "")
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
            f"Açınım denetimi tutmadı: orta çizgi {XL.tr(orta, 1, sade=False)} mm, kesit "
            f"alanından çıkan {XL.tr(alan / t, 1, sade=False)} mm. Aradaki fark, kesitin sac "
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
    # PROFİL görünüşü (büküm ekseni yönünden): kesitin kendisi. Kesim
    # konturu çıkmasa da (yalnız blank ölçüsü) büküm yönü resimden okunsun.
    # K / B etiketleri zincir sırasıyla = açınımdaki sırayla.
    try:
        tel = _tel_dizisi(BRepTools.OuterWire_s(yuz))
        cizgi = [[(p.X(), p.Y()) for p in tel]]
        if cizgi[0] and cizgi[0][0] != cizgi[0][-1]:
            cizgi[0].append(cizgi[0][0])
        kanat = []
        for z in zincir:
            if z["tip"] == "duz":
                ux, uy = z["yon"]
                kanat.append((((z["p"][0] + z["q"][0]) / 2.0, (z["p"][1] + z["q"][1]) / 2.0),
                              (-uy, ux)))
        sonuc["profil"] = {"cizgi": cizgi, "kanat": kanat,
                           "bukum": [tuple(z["m"]) for z in bkm]}
    except Exception:
        pass
    # Küçük PERSPEKTİF (izometrik): parçanın bükülmüş hâli bir bakışta.
    # Büküm ekseni burada Z; göz üç eksenden eşit uzaklıkta.
    try:
        sonuc["izo"] = hlr(sh, _birim3((1.0, -1.0, 0.8)), _birim3((1.0, 1.0, 0.0)),
                           gizli=False)["GORUNEN"]
    except Exception:
        pass
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
                    f"Not: kesitten çıkan açınım genişliği {XL.tr(gen, 1, sade=False)} mm, "
                    f"yüzeyden açılan kontur {XL.tr(ac['acinim_genislik_mm'], 1, sade=False)} mm. "
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


def ince_serit(t):
    """Lazerde kesilemeyecek şerit: bundan dar malzeme köprüsü açınımın
    hatasıdır (duvar ve büküm parçası uç uca tam oturmaz), tasarım değil."""
    return min(0.5, max(0.2, 0.25 * t))


def _halka_uzakligi(a, b):
    """İki kapalı çokgen arasındaki en kısa uzaklık (kenar-kenar)."""
    import numpy as np
    A, B = np.asarray(a, float), np.asarray(b, float)

    def nokta_kenar(P, Q):
        q0, q1 = Q, np.roll(Q, -1, axis=0)
        d = q1 - q0
        L2 = np.maximum((d * d).sum(1), 1e-18)
        v = P[:, None, :] - q0[None, :, :]
        t = np.clip((v * d[None]).sum(2) / L2[None], 0.0, 1.0)
        yak = q0[None] + t[..., None] * d[None]
        return float(np.sqrt(((P[:, None, :] - yak) ** 2).sum(2)).min())
    return min(nokta_kenar(A, B), nokta_kenar(B, A))


def delikleri_birlestir(ic, serit):
    """Aralarında `serit`ten dar malzeme kalan delikleri tek delik yapar
    (morfolojik kapama: yalnız bu delikler serit/2 büyütülür, birleştirilir,
    geri küçültülür; köşeler aynen döner, öbür deliklere dokunulmaz)."""
    if len(ic) < 2:
        return ic
    kutu_ = [(min(p[0] for p in w), min(p[1] for p in w),
              max(p[0] for p in w), max(p[1] for p in w)) for w in ic]
    ata = list(range(len(ic)))

    def bul(i):
        while ata[i] != i:
            ata[i] = ata[ata[i]]
            i = ata[i]
        return i
    for i in range(len(ic)):
        for j in range(i + 1, len(ic)):
            a, b = kutu_[i], kutu_[j]
            if a[0] - serit > b[2] or b[0] - serit > a[2] or \
                    a[1] - serit > b[3] or b[1] - serit > a[3]:
                continue
            if _halka_uzakligi(ic[i], ic[j]) < serit:
                ata[bul(i)] = bul(j)
    gruplar = {}
    for i in range(len(ic)):
        gruplar.setdefault(bul(i), []).append(i)
    out = []
    for g in gruplar.values():
        if len(g) == 1:
            out.append(ic[g[0]])
            continue
        w = _halkalari_kapat([ic[i] for i in g], serit / 2.0 + 0.01)
        out.extend(w if w else [ic[i] for i in g])
    return out


def _halkalari_kapat(halkalar, r):
    """Halkaları r büyüt, birleştir, r küçült -> yeni halka(lar)."""
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
    from OCP.GeomAbs import GeomAbs_Arc

    def ofset(yuz, d):
        o = BRepOffsetAPI_MakeOffset(yuz, GeomAbs_Arc)
        o.Perform(d)
        if not o.IsDone():
            return None
        yuzler = []
        ex = TopExp_Explorer(o.Shape(), TopAbs_WIRE)
        while ex.More():
            f = BRepBuilderAPI_MakeFace(TopoDS.Wire_s(ex.Current()), True)
            ex.Next()
            if f.IsDone():
                yuzler.append(f.Face())
        return yuzler
    try:
        buyuk = []
        for h in halkalar:
            y = _cokgen_yuzu(h)
            if y is None:
                return None
            buyuk += ofset(y, r) or []
        bir = _birlestir(buyuk)
        out = []
        ex = TopExp_Explorer(bir, TopAbs_FACE)
        while ex.More():
            f = TopoDS.Face_s(ex.Current())
            ex.Next()
            for k in ofset(f, -r) or []:
                p = _tel_dizisi(BRepTools.OuterWire_s(k))
                n = [(q.X(), q.Y()) for q in p]
                if len(n) > 2:
                    out.append(n)
        return out or None
    except Exception:
        return None


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
                f"{XL.tr(alan * t + duzelt, 0, sade=False)} mm3, parçanın hacmi {XL.tr(hacim, 0, sade=False)} "
                f"mm3 (%{('+' if (100 * sapma) >= 0 else '') + XL.tr(100 * sapma, 1, sade=False)}). Açma haritası bu parçada "
                f"doğru kurulamamış; kontur verilmiyor.")
    # Sınırı topolojiden çıkar: paylaşılan kenarlar iç dikiştir.
    dis, ic = _dis_halkalar(taban)
    if not dis:
        raise AcilimYok("Açınımın sınırı çıkarılamadı.")
    # Bükümü kesen pencere duvar ve büküm parçasından ayrı ayrı açılır;
    # aralarında kesilemeyecek incelikte (0,06 mm) şerit kalırsa lazer
    # boşluğun içinde FAZLADAN kesim yapar (K0_ON KILIT SACI_IC). Böyle
    # yakın delikler tek delik olur.
    ic = delikleri_birlestir(ic, ince_serit(t))
    # Açınım TEK PARÇA olmak zorundadır. Parçalı çıkıyorsa duvarlar
    # düzlemde uç uca oturmamış demektir; o zaman aradaki dikişler
    # kesim çizgisi gibi görünür ve lazerde parça ikiye ayrılır.
    if len(dis) != 1:
        ayri = sorted((abs(_cokgen_alani(w)) for w in dis), reverse=True)
        raise AcilimYok(
            f"Açınım düzlemde {len(dis)} ayrı parça çıktı; duvarlar uç uca "
            f"oturmadı. Parça alanları: "
            + ", ".join(f"{XL.tr(a, 0, sade=False)} mm2" for a in ayri[:4])
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
    # PROFİL: büküm ekseni yönünden bakış (parça burada zaten eksen Z
    # olacak şekilde döndürülmüş). Kanat ve büküm etiketleri açınımdaki
    # sırayla (alt kenardan yukarı) eşlenir: K1 açınımın alt kenarındaki
    # kanat, B1 ilk büküm. Büküm yönü tahmin edilmez, resimden okunur.
    profil = None
    try:
        hl = hlr(sh, (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), gizli=False)["GORUNEN"]
        kan = []
        for wi, (A, B) in harita.items():
            w = duvarlar[wi]
            pm = (w["p"][0] + w["p"][1]) / 2.0
            n, u = w["n"], w["u"]
            kan.append((A + B * pm, (n[0] * w["d0"] + u[0] * pm, n[1] * w["d0"] + u[1] * pm),
                        (n[0], n[1])))
        kan.sort(key=lambda x: x[0])
        buk = sorted(((min(b["s"], b["s_son"]), tuple(bukumler[bi]["m"]))
                      for bi, b in b_harita.items()), key=lambda x: x[0])
        if hl:
            profil = {"cizgi": hl, "kanat": [(p, n) for _, p, n in kan],
                      "bukum": [m for _, m in buk]}
    except Exception:
        profil = None
    return {"yontem": yon,
            "profil": profil,
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
            sat.append(f"  alan {XL.tr(w['alan'], 0):>8s} mm2 - hiç büküm yok")
            continue
        _, uz, hedef, ort = en_iyi
        if ort < 0.5:
            neden = f"boy boyunca hiç örtüşmüyor ({XL.tr(ort, 1, sade=False)} mm)"
        elif abs(uz - hedef) > 0.15:
            neden = (f"teğet değil: bükümden uzaklık {XL.tr(uz, 2, sade=False)} mm, "
                     f"olması gereken {XL.tr(hedef, 2, sade=False)} mm")
        else:
            neden = "ağacın kopuk bir dalında kalmış"
        sat.append(f"  alan {XL.tr(w['alan'], 0):>8s} mm2  boy [{XL.tr(w['z'][0], 0, sade=False)}, "
                   f"{XL.tr(w['z'][1], 0, sade=False)}]  ->  {neden}")
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
            f"(sac yüzeyinin %{XL.tr(100 * alan / toplam, 0, sade=False)}'i). Parça tek bir "
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
        raise AcilimYok(f"Sac kalınlığı makul değil: {XL.tr(t, 2, sade=False)} mm.")
    # Gabarinin en ince yönü ile hacimden çıkan kalınlık tutmalı.
    # Tutmuyorsa parça düz bir plaka değildir (cep, çıkıntı, kademe).
    if abs(ince - t) > max(0.05, en_cok_sapma * t):
        raise AcilimYok(
            f"Parça düz plaka değil: gabarinin en ince yönü {XL.tr(ince, 2, sade=False)} mm, "
            f"hacim/alan {XL.tr(t, 2, sade=False)} mm veriyor. Cebi, çıkıntısı ya da "
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


def olcek_yazisi_kisa(v):
    return f"{XL.tr(v)}:1" if v >= 1 else f"1:{XL.tr(round(1 / v, 1))}"


def _birim3(v):
    n = math.sqrt(sum(a * a for a in v)) or 1.0
    return tuple(a / n for a in v)


def kanat_dis_olculeri(r):
    """ABKANT (CNC) için kanatların DIŞ ölçüsü - sanal köşeye (dış yüzlerin
    uzantılarının kesiştiği yere) kadar. CNC abkant (Delem vb.) parçanın
    profilini böyle ister, dayamanın yerini kendisi hesaplar.

    Düz kısımlar açınımdaki büküm bölgeleri ARASIDIR (modelin gerçek duvar
    boyları; K-faktöründen bağımsız). Her büküm, iki yanındaki kanada dış
    payını (r_iç + t)·tan(büküm/2) ekler (90° bükümde r_iç + t).
    Kenarlar açınımın en dış kenarlarıdır (en geniş yer).
    Döner: [dış ölçü, ...] (kanat sayısı = büküm sayısı + 1) ya da []."""
    bk = sorted(r.get("bukumler") or [], key=lambda b: b["acinimda_bas_mm"])
    if not bk:
        return []
    t = float(r["kalinlik_mm"])
    gen = float(r["acinim_genislik_mm"])
    pay = [(b["r_ic"] + t) * math.tan(math.radians(b["aci_derece"]) / 2.0) for b in bk]
    sinir = [0.0] + [x for b in bk for x in (b["acinimda_bas_mm"], b["acinimda_son_mm"])] + [gen]
    out = []
    for i in range(len(bk) + 1):
        duz = sinir[2 * i + 1] - sinir[2 * i]
        out.append(duz + (pay[i - 1] if i > 0 else 0.0) + (pay[i] if i < len(bk) else 0.0))
    return out


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
        # BÜKÜM EKSENİ: büküm bölgesinin (payın) ortası - abkantta bıçağın
        # geldiği çizgi. Önce bölgenin başı ve sonu (iki teğet çizgisi)
        # çiziliyordu; iki çizgi büküm ekseni sanılıyordu. Bölge sınırları
        # çizelgede yazılıdır.
        orta = (b["acinimda_bas_mm"] + b["acinimda_son_mm"]) / 2.0
        msp.add_line((0, orta), (boy, orta), dxfattribs={"layer": "EKSEN"})
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
        _yaz(msp, "BÜKÜM  AÇI      İÇ R   PAY    EKSEN (alt kenardan)   BÖLGE", x, y, h)
    y -= 2.0 * h
    for i, b in enumerate(r["bukumler"], 1):
        eks = (b["acinimda_bas_mm"] + b["acinimda_son_mm"]) / 2.0
        _yaz(msp, f"B{i:<5d} {XL.tr(b['aci_derece'], 1, False):>6s}  "
                  f"{XL.tr(b['r_ic'], 2, False):>6s} "
                  f"{XL.tr(b['pay_mm'], 2, False):>6s}  "
                  f"{XL.tr(eks, 2, False):>10s}             "
                  f"{XL.tr(b['acinimda_bas_mm'], 2, False)} - "
                  f"{XL.tr(b['acinimda_son_mm'], 2, False)}", x, y, h)
        y -= 1.8 * h
    kanat = kanat_dis_olculeri(r)
    if kanat:
        # ABKANT (CNC): usta profili kanat DIŞ ölçüsüyle girer; dayamayı
        # tezgâh hesaplar. Büküm ekseni tezgâh için dayanak değildir.
        bk = sorted(r["bukumler"], key=lambda b: b["acinimda_bas_mm"])
        y -= 1.2 * h
        _yaz(msp, "ABKANT (CNC) - kanat DIŞ ölçüleri (sanal köşeye), 3B modelden", x, y, h)
        y -= 2.0 * h
        _yaz(msp, "KANAT  DIŞ ÖLÇÜ   BÜKÜM  İÇ AÇI   İÇ R", x, y, h)
        y -= 2.0 * h
        for i, kd in enumerate(kanat, 1):
            b = bk[i - 1] if i <= len(bk) else None
            _yaz(msp, f"K{i:<5d} {XL.tr(kd, 1, False):>8s}   "
                      + (f"B{i:<5d} {XL.tr(180.0 - b['aci_derece'], 1, False):>6s}  "
                         f"{XL.tr(b['r_ic'], 2, False):>6s}" if b else "-"), x, y, h)
            y -= 1.8 * h
    pr = r.get("profil")
    if pr and pr.get("cizgi"):
        # PROFİL görünüşü: bükümlerin yönü buradan okunur (K / B etiketleri
        # açınımdaki kanat ve bükümlerle aynı numara).
        kdo = kanat_dis_olculeri(r)
        # Kısa kanat yazıya göre küçükse profil büyütülür (etiketler
        # binmesin); ölçek başlıkta yazar.
        en_kisa = min(kdo) if kdo else 0.0
        olc = 1.0
        if en_kisa > 0:
            for v in (1.0, 2.0, 2.5, 4.0, 5.0, 10.0):
                olc = v
                if en_kisa * v >= 5.0 * yazi_h:
                    break
        pr = dict(pr, cizgi=[[(a * olc, b * olc) for a, b in q] for q in pr["cizgi"]],
                  kanat=[((p[0] * olc, p[1] * olc), n) for p, n in pr["kanat"]],
                  bukum=[(m[0] * olc, m[1] * olc) for m in pr["bukum"]])
        pts = [p for q in pr["cizgi"] for p in q]
        px0, py0 = min(p[0] for p in pts), min(p[1] for p in pts)
        px1, py1 = max(p[0] for p in pts), max(p[1] for p in pts)
        y -= 1.5 * h
        _yaz(msp, "PROFİL - büküm ekseni yönünden bakış (K: kanat, B: büküm)"
             + (f"   ölçek {XL.tr(olc)}:1" if olc != 1.0 else ""), x, y, h)
        y -= 2.5 * h
        ox, oy = x + 3.0 * h - px0, y - (py1 - py0) - 2.0 * h - py0
        for q in pr["cizgi"]:
            msp.add_lwpolyline([(a + ox, b + oy) for a, b in q],
                               dxfattribs={"layer": "GORUNEN"})
        cx, cy = (px0 + px1) / 2.0, (py0 + py1) / 2.0
        for i, (p, n) in enumerate(pr["kanat"], 1):
            sg = 1.0 if (p[0] - cx) * n[0] + (p[1] - cy) * n[1] >= 0 else -1.0
            tx = p[0] + sg * n[0] * (t / 2.0 + 1.2 * yazi_h) + ox
            ty = p[1] + sg * n[1] * (t / 2.0 + 1.2 * yazi_h) + oy
            et = f"K{i}" + (f" {XL.tr(kdo[i - 1], 1)}" if len(kdo) == len(pr["kanat"]) else "")
            _yaz(msp, et, tx - 0.36 * len(et) * yazi_h, ty - 0.45 * yazi_h, yazi_h, kat="OLCU")
        for i, m in enumerate(pr["bukum"], 1):
            msp.add_circle((m[0] + ox, m[1] + oy), 0.25 * yazi_h, dxfattribs={"layer": "EKSEN"})
            _yaz(msp, f"B{i}", m[0] + ox + 0.4 * yazi_h, m[1] + oy + 0.2 * yazi_h,
                 0.8 * yazi_h, kat="EKSEN")
        y = oy + py0 - 2.0 * h
    izo = r.get("izo")
    if izo:
        pts = [p for q in izo for p in q]
        ix0, iy0 = min(p[0] for p in pts), min(p[1] for p in pts)
        ix1, iy1 = max(p[0] for p in pts), max(p[1] for p in pts)
        hedef = 60.0 * yazi_h                  # küçük bir resim
        ideal = hedef / max(ix1 - ix0, iy1 - iy0, 1e-6)
        olc2 = max([v for v in (0.05, 0.1, 0.2, 0.25, 0.5, 1.0, 2.0) if v <= ideal] or [0.05])
        y -= 1.5 * h
        _yaz(msp, f"PERSPEKTİF (izometrik)   ölçek {olcek_yazisi_kisa(olc2)}", x, y, h)
        y -= 2.0 * h
        ox = x + 3.0 * h - ix0 * olc2
        oy = y - (iy1 - iy0) * olc2 - 1.0 * h - iy0 * olc2
        for q in izo:
            msp.add_lwpolyline([(a * olc2 + ox, b * olc2 + oy) for a, b in q],
                               dxfattribs={"layer": "GORUNEN"})
        y = oy + iy0 * olc2 - 2.0 * h
    if len(r["bukumler"]) <= 4:
        # Sol tarafa, genel genişlik ölçüsünün dışına diz: sağda büküm
        # etiketleri ve çizelge var.
        for i, b in enumerate(r["bukumler"], 1):
            msp.add_linear_dim(base=(-d - i * 3.5 * h, 0), p1=(boy, 0),
                               p2=(boy, (b["acinimda_bas_mm"] + b["acinimda_son_mm"]) / 2.0),
                               angle=90,
                               dimstyle=OLCU_STILI,
                               dxfattribs={"layer": "OLCU"}).render()
    poz = f"POZ {k['poz']}   " if k.get("poz") else ""
    sat = [(f"{poz}{k.get('kod','')}   {(k.get('ad') or '')[:60]}   AÇINIM", 1.5 * h),
           (f"adet: {k.get('adet','-')}", 1.1 * h),
           (f"AÇINIM: {XL.tr(gen, 1)} x {XL.tr(boy, 1)} mm   sac kalınlığı {XL.tr(t, 2)} mm",
            1.1 * h),
           ((f"{r['bukum_sayisi']} büküm   K-faktörü {XL.tr(r['k_faktor'], 2)}"
             + (f"   {len(r.get('kontur_delik') or [])} delik" if kesim else ""))
            if r.get("k_faktor") is not None
            else "büküm yerleri verilmedi", 1.1 * h),
           ("ölçek 1:1   birim: mm   -.-.- büküm ekseni (büküm bölgesinin ortası)",
            1.1 * h)]
    yn = r.get("yontem") or {}
    if yn.get("yontem"):
        sat.append((f"BÜKÜM YÖNTEMİ: {yn['yontem'].upper()}"
                    + (f"  ({yn['kesinlik']})" if yn.get("kesinlik") else ""),
                    1.2 * h))
        for p in textwrap.wrap(yn.get("neden", ""), 108):
            sat.append((p, 1.0 * h))
        for p in textwrap.wrap("DIKKAT: " + yn["uyari"], 108) if yn.get("uyari") else []:
            sat.append((p, 1.0 * h))
    if kesim:
        sat.append(("KESİM KONTURUDUR: dış kontur ve delikler gerçek "
                    "yerlerinde.", 1.1 * h))
    else:
        sat.append(("ŞERİT GENİŞLİĞİDİR: büküm yerleri ve kesim konturu yok."
                    if r.get("serit_genisligi") else
                    "BLANK ÖLÇÜSÜDÜR: dış kontur kesikleri ve delikler "
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
            + ("_acinim_lzr" if acinim and lazer else "_acinim" if acinim
               else "_Lzr" if lazer else "")
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
               log=print, ilerleme=None, iptal=None, eksik=False):
    """Seçilen parçaların açınımını hesaplar, DXF ve tablo yazar.

    KURAL: açınımı çıkan her parça için iki dosya olur -
      ACINIM/..._acinim.dxf   BÜKÜM RESMİ: açınım, büküm eksenleri, büküm
                              ve ABKANT (kanat dış ölçüsü) tablosu, profil
      LZR/..._acinim_lzr.dxf  LAZER KESİM: yalnız kesim konturu

    klasor: ÇIKTI KÖK KLASÖRÜ; dosyalar onun ACINIM alt klasörüne yazılır,
    ACINIM.csv eskisiyle BİRLEŞTİRİLİR (başka parçaların satırı silinmez).
    eksik: aynı modelden aynı K-faktörüyle üretilmiş açınım atlanır.
    kodlar None ise bütün komponentler denenir. Geriye (sonuclar, hatalar)
    döner; hata listesi kullanıcıya OLDUĞU GİBİ gösterilmelidir, çünkü
    hangi parçanın neden açılamadığını tek tek söyler."""
    kok = klasor
    klasor = IS.alt_klasor(kok, "acinim", olustur=True)
    lz_klasor = IS.alt_klasor(kok, "lazer", olustur=True)
    step_oz = IS.durum_oku(kok).get("step_ozet", "")
    sonuc, hata, denenen = [], [], set()
    lz_sonuc, lz_hata, lz_denenen = [], [], set()
    yazilan_ac, yazilan_lz = set(), set()
    pozlar = poz_numaralari(komp)
    secili = [(pozlar[i], k) for i, k in enumerate(komp)
              if kodlar is None or (k.get("kod") or k.get("ad")) in kodlar]
    for i, (poz, k) in enumerate(secili):
        if iptal and iptal():
            break
        ad = k.get("kod") or k.get("ad") or "?"
        if ilerleme:
            ilerleme(i, len(secili), ad)
        # güncel açınım atlanır - lazer dosyası da varsa (eski sürüm
        # açınımın yanına lazer yazmıyordu)
        if eksik and IS.onceden_uretilmis(kok, "acinim", ad, step_oz,
                                          k_faktor=k_faktor) \
                and IS.onceden_uretilmis(kok, "lazer", ad, step_oz, k_faktor=k_faktor):
            log(f"  {ad}: açınım güncel (aynı model, K={k_faktor}) - atlandı")
            continue
        denenen.add(ad)
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
        IS.eskiyi_kaldir(kok, "acinim", ad, os.path.basename(dosya), log,
                         korunan=yazilan_ac)
        dxf_acilim(r, dict(k, poz=poz), dosya, P)
        yazilan_ac.add(os.path.basename(dosya))
        r["kod"] = ad
        r["ad"] = k.get("ad", "")
        r["poz"] = poz
        r["adet"] = k.get("adet", 1)
        r["dxf"] = os.path.basename(dosya)
        sonuc.append(r)
        IS.cizim_kaydet(kok, "acinim", ad, dxf=r["dxf"], step_ozet=step_oz,
                        k_faktor=k_faktor)
        log(f"  {os.path.basename(dosya)}  {XL.tr(r['acinim_genislik_mm'])} x "
            f"{XL.tr(r['acinim_boy_mm'])} mm, t={XL.tr(r['kalinlik_mm'])}, "
            f"{r['bukum_sayisi']} büküm")
        # KURAL: açınım varsa LAZER KESİM dosyası da vardır (xxxx_acinim_lzr):
        # yalnız kesim konturu, büküm ekseni / yazı / ölçü yok.
        lz_denenen.add(ad)
        if r.get("kontur_dis"):
            try:
                lz_sonuc.append(_lazer_dosyasi(
                    kok, lz_klasor, poz or (i + 1), k, r["kontur_dis"],
                    r.get("kontur_delik") or [], r["kalinlik_mm"], "açınım",
                    step_oz, k_faktor, log, korunan=yazilan_lz))
            except Exception as e:
                lz_hata.append((ad, f"lazer dosyası yazılamadı: {e}"))
        else:
            lz_hata.append((ad, "açınım var ama kesim konturu çıkarılamadı "
                                "(yalnız blank ölçüsü): lazer kesim dosyası yok. "
                                + (r.get("kontur_notu") or "")[:200]))
            log(f"  {ad}: lazer kesim dosyası yok - açınımın kesim konturu çıkarılamadı")
    if lz_denenen:
        _lazer_tablosu(lz_klasor, lz_sonuc, lz_hata, lz_denenen, log)
    if denenen:
        yeni = []
        for r in sonuc:
            yeni.append([r["poz"], r["kod"], r["ad"], r["adet"],
                            r["kalinlik_mm"], r["acinim_genislik_mm"],
                            r["acinim_boy_mm"], r["bukum_sayisi"],
                            (r.get("yontem") or {}).get("yontem", ""),
                            (r.get("yontem") or {}).get("en_kisa_kanat_mm", ""),
                            (r.get("yontem") or {}).get("en_kisa_kanat_t", ""),
                            (r.get("yontem") or {}).get("en_kucuk_r_t", ""),
                            (r.get("yontem") or {}).get("neden", ""),
                            (r.get("yontem") or {}).get("uyari", ""),
                            r["k_faktor"],
                            " | ".join(f"{XL.tr(b['aci_derece'])}d R{XL.tr(b['r_ic'])} "
                                       f"pay{XL.tr(b['pay_mm'])} eksen@"
                                       f"{XL.tr(round((b['acinimda_bas_mm'] + b['acinimda_son_mm']) / 2, 2))}"
                                       for b in r["bukumler"]),
                            " - ".join(XL.tr(v, 1, sade=False) for v in kanat_dis_olculeri(r)),
                            r["dxf"]])
        n = IS.csv_birlestir(
            os.path.join(klasor, "ACINIM.csv"),
            ["poz", "kod", "ad", "adet", "kalinlik_mm",
             "acinim_genislik_mm", "acinim_boy_mm", "bukum_sayisi",
             "yontem", "en_kisa_kanat_mm", "en_kisa_kanat_t",
             "en_kucuk_r_t", "yontem_nedeni", "uyari",
             "k_faktor", "bukumler", "kanat_dis_olculeri_mm", "dxf"], yeni, denenen,
            klasor)
        if sonuc:
            log(f"  ACINIM/ACINIM.csv  ({len(sonuc)} yeni, tabloda {n} parça)")
        h = IS.hata_birlestir(os.path.join(klasor, "ACINIM_yapilamayanlar.txt"),
                              hata, denenen)
        if hata:
            log(f"  ACINIM/ACINIM_yapilamayanlar.txt  ({h} parça)")
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

    klasor: ÇIKTI KÖK KLASÖRÜ; dosyalar LZR alt klasörüne yazılır,
    LAZER.csv eskisiyle birleştirilir.

    Geriye (sonuclar, hatalar) döner."""
    kok = klasor
    klasor = IS.alt_klasor(kok, "lazer", olustur=True)
    step_oz = IS.durum_oku(kok).get("step_ozet", "")
    sonuc, hata, denenen, yazilan = [], [], set(), set()
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
        denenen.add(ad)
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
        sonuc.append(_lazer_dosyasi(kok, klasor, poz or (i + 1), k, dis, ic, t, nere,
                                    step_oz, k_faktor, log, korunan=yazilan))
    _lazer_tablosu(klasor, sonuc, hata, denenen, log)
    return sonuc, hata


def _lazer_dosyasi(kok, klasor, poz, k, dis, ic, t, nere, step_oz, k_faktor, log=print,
                   korunan=None):
    """Bir parçanın lazer kesim dosyasını yazar ve kaydeder; LAZER tablosu
    satırını döndürür. Açınımdan gelen kontur '_acinim_lzr.dxf', düz sac
    '_Lzr.dxf' adını alır. Yalnız kesim konturu: büküm çizgisi, yazı,
    ölçü YOK."""
    ad = k.get("kod") or k.get("ad") or "?"
    dosya = resim_dosyasi(poz, ad, k.get("ad"), acinim=(nere == "açınım"), lazer=True)
    IS.eskiyi_kaldir(kok, "lazer", ad, dosya, log, korunan=korunan or ())
    dxf_lazer(dis, ic, os.path.join(klasor, dosya))
    if korunan is not None:
        korunan.add(dosya)
    xs = [q[0] for w in dis for q in w]
    ys = [q[1] for w in dis for q in w]
    kayd = {"poz": poz, "kod": ad, "ad": k.get("ad", ""),
            "adet": k.get("adet", 1), "kalinlik_mm": t,
            "boy_mm": round(max(ys) - min(ys), 2),
            "en_mm": round(max(xs) - min(xs), 2),
            "delik_adedi": len(ic), "kaynak": nere, "dxf": dosya}
    IS.cizim_kaydet(kok, "lazer", ad, dxf=dosya, step_ozet=step_oz, k_faktor=k_faktor)
    log(f"  LZR/{dosya}  {XL.tr(kayd['en_mm'])} x {XL.tr(kayd['boy_mm'])} mm, "
        f"t={XL.tr(t)}, {len(ic)} delik  ({nere})")
    return kayd


def _lazer_tablosu(klasor, sonuc, hata, denenen, log=print):
    """LZR/LAZER.csv (+ .xlsx) ve yapılamayanlar listesi, eskisiyle birleşik."""
    if denenen:
        alan = ("poz", "kod", "ad", "adet", "kalinlik_mm", "en_mm", "boy_mm",
                "delik_adedi", "kaynak", "dxf")
        n = IS.csv_birlestir(os.path.join(klasor, "LAZER.csv"), list(alan),
                             [[r[c] for c in alan] for r in sonuc],
                             denenen, klasor)
        if sonuc:
            log(f"  LZR/LAZER.csv  ({len(sonuc)} yeni, tabloda {n} parça)")
        h = IS.hata_birlestir(os.path.join(klasor, "LAZER_yapilamayanlar.txt"),
                              hata, denenen)
        if hata:
            log(f"  LZR/LAZER_yapilamayanlar.txt  ({h} parça)")
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


def sade_profil(s2, o, k, P):
    """EKSTRÜZYON profilin SADE resmi için (P, o): profil ekseni resmin
    çerçevesinde bulunur; o eksene paralel delik / radüs / slot (kalıbın
    iç ayrıntısı) resimden çıkarılır, eksene dik olanlar (işleme) kalır.
    Ekstrüzyon değilse (P, o) aynen döner."""
    r = k.get("profil") or {}
    if r.get("tur") != "ekstrüzyon":
        return P, o
    kb = kutu(s2)
    ext = (kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2])
    eks = "XYZ"[min(range(3), key=lambda i: abs(ext[i] - float(r.get("boy") or 0)))]
    o2 = dict(o)
    for a in ("delikler", "radusler", "slotlar"):
        o2[a] = [d for d in (o.get(a) or []) if d.get("eksen") != eks]
    return (dict(P, sade_eksen=eks,
                 sade_not=f"kesit: {r.get('ad', 'ekstrüzyon profil')[:70]} - kesit ölçüleri "
                          "tedarikçi kataloğundan"), o2)


def gabari_satiri(o):
    """Başlıktaki ölçü satırı.

    Üç kutu ölçüsü yalnız DÜZ SACTA "boy x en x kalınlık"tır. C profilde
    en küçük kutu ölçüsü 40 mm'dir, sac 1,5 mm; "KALINLIK 40" yazmak
    yanlıştı. Öbür parçalarda satır GABARİ'dir, sac kalınlığı ayrıca
    yazılır."""
    L, W, T = (XL.tr(o[a], 2) for a in ("boy_mm", "en_mm", "kalinlik_mm"))
    t = o.get("sac_kalinlik_mm")
    if o.get("sac_tip") == "duz sac" and t and abs(float(t) - float(o["kalinlik_mm"])) < 0.01:
        return f"BOY x EN x KALINLIK: {L} x {W} x {T} mm"
    satir = f"GABARİ (boy x en x yükseklik): {L} x {W} x {T} mm"
    if t:
        satir += f"   sac kalınlığı {XL.tr(t, 2)} mm"
    return satir


YAZI_ORAN = 70.0     # yazı boyu = en büyük ölçü / bu
YAZI_EN_AZ = 1.8
YAZI_EN_COK = 20.0   # 1:10 paftada kâğıtta 2 mm (16 ile 1:20'de 0,8 mm: okunmuyordu)


def yazi_boyu(L, W, T):
    """Detay resminin yazı / ölçü rakamı boyu (model mm)."""
    return min(YAZI_EN_COK, max(YAZI_EN_AZ, max(L, W, T) / YAZI_ORAN))


def _gorunus_puani(s, o):
    """Her model ekseni için, o eksenden BAKAN görünüşün bilgi puanı:
    görünüş alanı (öbür iki ölçünün çarpımı, en büyüğe göre) + o eksende
    daire olarak görünen delik / slot / yay sayısının payı."""
    kb = kutu(s)
    ext = (kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2])
    alan = [ext[(i + 1) % 3] * ext[(i + 2) % 3] for i in range(3)]
    oz = [0, 0, 0]
    for d in o.get("delikler") or []:
        if d.get("eksen") in ("X", "Y", "Z"):
            oz["XYZ".index(d["eksen"])] += d.get("adet", 1)
    for sl in o.get("slotlar") or []:
        if sl.get("eksen") in ("X", "Y", "Z"):
            oz["XYZ".index(sl["eksen"])] += 2
    top = max(1, sum(oz))
    return [alan[i] / max(max(alan), 1e-9) + 0.6 * oz[i] / top for i in range(3)]


def ana_gorunus_dondur(s, o):
    """EN DOĞRU GÖRÜNÜŞ ÖN GÖRÜNÜŞ OLUR (kullanıcı: "önce en doğru görünüş
    yerleştirilir, sonra sağ / sol, sonra gerekirse üst / alt").

    Parça modelde nasıl duruyorsa ön görünüş o değildi: P01'de "ÖN"
    1854 x 54'lük bir şeritti, bütün delikler ve ızgara ÜST'teydi. En
    çok bilgi veren yön (bkz. _gorunus_puani) ön görünüşe çevrilir; ön
    görünüşte uzun kenar yatay durur. Yalnız ÇİZİM için döner: delik
    merkezleri, slotlar, büküm ekseni aynı dönüşle döner, ölçü
    değerleri değişmez. Döner: (s, o)."""
    puan = _gorunus_puani(s, o)
    en = max(range(3), key=lambda i: (puan[i], i == 1))
    I = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    if en == 2:
        # Z -> -Y: ÖN görünüş, modelin ÜSTTEN görünüşünün AYNISI olur (aynı
        # yüz, modelin +Y'si yukarıda). Önce Z -> +Y idi: parçaya ALTTAN
        # bakılıyor, resim ters çıkıyordu (kullanıcı: "parça ters, kabin
        # koruma da neden").
        R = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
    elif en == 0:
        R = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]        # X -> Y
    else:
        R = I
    kb = kutu(s)
    ext = [kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]]
    yeni_ext = [sum(abs(R[r][c]) * ext[c] for c in range(3)) for r in range(3)]
    if yeni_ext[0] + 1e-6 < yeni_ext[2]:              # uzun kenar yatay (X)
        Ry = [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]
        R = [[sum(Ry[r][k_] * R[k_][c] for k_ in range(3)) for c in range(3)] for r in range(3)]
    if R == I:
        return s, o
    s2 = donustur(s, R)
    k2 = kutu(s2)
    t = (-k2[0], -k2[1], -k2[2])
    s2 = donustur(s2, I, t)

    def nokta(p):
        q = [sum(R[r][c] * p[c] for c in range(3)) for r in range(3)]
        return [round(q[i] + t[i], 4) for i in range(3)]

    def eksen(harf):
        if harf not in ("X", "Y", "Z"):
            return harf
        v = [R[r]["XYZ".index(harf)] for r in range(3)]
        return "XYZ"[max(range(3), key=lambda i: abs(v[i]))]
    import copy as _copy
    o2 = _copy.deepcopy(o)
    for d in (o2.get("delikler") or []) + (o2.get("radusler") or []):
        d["eksen"] = eksen(d.get("eksen"))
        if d.get("merkezler"):
            d["merkezler"] = [nokta(p) for p in d["merkezler"]]
    for sl in o2.get("slotlar") or []:
        sl["eksen"] = eksen(sl.get("eksen"))
        sl["c1"], sl["c2"] = nokta(sl["c1"]), nokta(sl["c2"])
    if o2.get("bukum_ekseni"):
        e = o2["bukum_ekseni"]
        o2["bukum_ekseni"] = [round(sum(R[r][c] * e[c] for c in range(3)), 6) for r in range(3)]
    if o2.get("agirlik_merkezi"):
        o2["agirlik_merkezi"] = [round(v, 2) for v in nokta(o2["agirlik_merkezi"])]
    return s2, o2


def bilgisiz_gorunus(kenar, gad, o, sac_kesit):
    """Görünüş bilgi EKLEMİYOR mu: o yönden görünen delik / slot yok, sacın
    kesiti değil ve dış hattı düz bir dikdörtgen (en çok 6 görünen çizgi)."""
    eks = "XYZ"[max(range(3), key=lambda i: abs(GORUNUS[gad][0][i]))]
    if gad in (sac_kesit or {}):
        return False
    if any(d.get("eksen") == eks for d in (o.get("delikler") or []) + (o.get("slotlar") or [])):
        return False
    return len(kenar.get("GORUNEN", [])) <= 6


def dxf_komponent(s, o, k, yol, P):
    """Bir komponentin detay resmi: seçili görünüşler + ölçüler + tablolar."""
    doc = dxf_kur(); msp = doc.modelspace()
    # PARÇA DÖNDÜRÜLMEZ: modelde (montajda) nasıl duruyorsa öyle çizilir
    # (kullanıcı: "parça hep doğru yönde olacak, montaj yönü neyse ona göre
    # konulur"). Eski "en çok bilgi veren yüzü öne çevir" kuralı parçayı
    # ters gösteriyordu (kabin koruma). ana_gorunus_dondur yalnız açıkça
    # istenirse (P["ana_gorunus_dondur"]).
    if P.get("ana_gorunus_dondur"):
        try:
            s, o = ana_gorunus_dondur(s, o)
        except Exception:
            pass
    kb = kutu(s)
    L, W, T = kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]
    # Yazı boyu parçaya göre: küçük parçada küçük, büyükte büyük ama okunur.
    # Kullanıcı: "DXF'te ve PDF'te de punto azalt" - eskisi (boy / 45, en
    # çok 25) yoğun resimde ölçüleri birbirine bindiriyordu.
    h = yazi_boyu(L, W, T)
    olcu_stili(doc, h)
    gorunusler = gorunus_sec(P.get("gorunusler"))
    # Görünüşler arası boşluk: araya giren ölçü çizgisi + yazı + kılavuz kadar.
    # Görünüşler arası boşluk: ölçü hatları + yazılar sığsın (pafta boşluğu
    # kâğıtta yine sıkıştırır). Dar olunca ÖN'ün ölçüleri ÜST'ün satırına
    # sarkıyor, pafta ızgarası bozulup 1:20'ye düşüyordu.
    g = max(L, W, T) * 0.10 + 26 * h
    yer = gorunus_yerlesimi(L, W, T, g, gorunusler)
    # Konum ölçüleri ÖNCE planlanır: gabari ölçüsünün ne kadar dışarı
    # iteleneceği kaç seviye konum ölçüsü gireceğine bağlı.
    # Görünüşler BİR KEZ hesaplanır; plan da bu izdüşümlere dayanır.
    # SADE resim (ekstrüzyon profil): gizli çizgi yok; kesitin göründüğü uç
    # görünüşlerde kalıbın iç ayrıntısı (radüs, iç duvar, pencere, pah)
    # ölçülmez - kesit tedarikçinin kalıbıdır. İşleme (delik) ölçüleri kalır.
    # BÜKÜMLÜ SACIN KESİTİ SAĞ'da ve SOL'da AYNIDIR (ayna): ikisini birden
    # çizmek bilgi eklemez, yalnız yer kaplar. P01'de SAĞ + ÖN + SOL yan
    # yana A3'e 1:10'da sığmadığı için pafta 1:20'ye düşüyor, yazılar
    # kâğıtta 0,8 mm kalıyordu (kullanıcı: "karınca duası"). Görünüşleri
    # kullanıcı kendisi seçtiyse dokunulmaz.
    if not P.get("gorunus_zorla") and "SAG" in gorunusler and "SOL" in gorunusler:
        try:
            _sk = sac_kesit_gorunusleri(s, o, gorunusler)
        except Exception:
            _sk = {}
        if "SAG" in _sk and "SOL" in _sk:
            gorunusler = tuple(g for g in gorunusler if g != "SOL")
            g = max(L, W, T) * 0.10 + 26 * h
            yer = gorunus_yerlesimi(L, W, T, g, gorunusler)
    sade = P.get("sade_eksen")
    uc_gor = set(DELIK_GOR.get(sade, ())) if sade else set()
    kenarlar = {gad: hlr(s, *GORUNUS[gad], gizli=P.get("gizli", True) and not sade)
                for gad in gorunusler}
    # AYNI GÖRÜNEN AYNA GÖRÜNÜŞLER TEK ÇİZİLİR (kullanıcı: "sağ ve sol
    # arasında resimsel ve anlam olarak fark yoksa bir sağ ya da bir sol
    # yeter; alt ve üst için de"). Karar ÖLÇÜLEREK verilir: görünen
    # çizgiler aynaya çevrilip ızgarada karşılaştırılır.
    if not P.get("gorunus_zorla"):
        for a_, b_ in (("SAG", "SOL"), ("UST", "ALT"), ("ON", "ARKA")):
            if a_ in kenarlar and b_ in kenarlar and ayna_ayni(kenarlar[a_], kenarlar[b_],
                                                               max(L, W, T)):
                del kenarlar[b_]
                gorunusler = tuple(g_ for g_ in gorunusler if g_ != b_)
                yer = gorunus_yerlesimi(L, W, T, g, gorunusler)
        # BİLGİ EKLEMEYEN yan görünüş çizilmez ("ekstra bilgi vermeyecekse 3
        # görüntü yeterli"); ön görünüş ve en az bir yan görünüş kalır.
        try:
            _sk2 = sac_kesit_gorunusleri(s, o, gorunusler)
        except Exception:
            _sk2 = {}
        for b_ in [g_ for g_ in gorunusler if g_ != "ON"]:
            if len(gorunusler) <= 2:
                break
            if bilgisiz_gorunus(kenarlar[b_], b_, o, _sk2):
                del kenarlar[b_]
                gorunusler = tuple(g_ for g_ in gorunusler if g_ != b_)
                yer = gorunus_yerlesimi(L, W, T, g, gorunusler)
    ham = {gad: _kenar_kutusu(k) for gad, k in kenarlar.items()}
    kenar_olcu = {gad: k for gad, k in kenarlar.items() if gad not in uc_gor}
    # 3B tasarım seviyeleri: görünüşten bulunan her konum modelde bir
    # karşılığa denk gelmedikçe yazılmaz (bkz. tasarim_seviyeleri).
    try:
        seviye, datum_sv = tasarim_seviyeleri(s, datum=True)
    except Exception:
        seviye = [[], [], []]      # ölçülemezse hiçbir konum geçmez
        datum_sv = [[], [], []]
    atlanan = Counter()
    sac_kesit = sac_kesit_gorunusleri(s, o, gorunusler)
    try:
        izgara = izgara_bolgeleri(s, gorunusler)
    except Exception:
        izgara = {}
    # Bükümlü sacın kesitinde kanatlar DIŞTAN DIŞA ölçülür (ABKANT);
    # duvarlar bulunamazsa (eğik kanat) eski yol: yalnız serbest uçlar.
    sac_kanat = False
    if sac_kesit:
        try:
            e_ = o["bukum_ekseni"]
            sac_kanat = bool(sac_duvarlari(s, max(range(3), key=lambda i: abs(e_[i])),
                                           float(o["sac_kalinlik_mm"])))
        except Exception:
            sac_kanat = False
    PLAN_UYARI.clear()
    kplan = (konum_plani(o, gorunusler, ham, h, kenar_olcu, seviye=seviye,
                         rapor=atlanan, sac_kesit=sac_kesit, datum_sv=datum_sv,
                         izgara=izgara, sac_kanat=sac_kanat)
             if P.get("konum", True) else {})
    ust, kaydir, gkutu = {}, {}, {}
    for gad in gorunusler:
        ox, oy = yer[gad]
        # Gabari burada ÇİZİLMEZ: konum ölçüleri yerleştikten sonra,
        # onların ÖLÇÜLEN sınırının dışına konur (bkz. gabari_olculeri).
        G, Y, dx, dy = gorunus_ciz(msp, kenarlar[gad], ox, oy, gad, h=h,
                                   olcu2=False, etiket_ciz=False)
        ust[gad] = oy + Y + 2.2 * h          # görünüş etiketinin de üstü
        kaydir[gad] = (dx, dy)
        gkutu[gad] = (ox, oy, ox + G, oy + Y)
    merkez_cizgileri(msp, o, yer, kaydir)
    izgara_ciz(msp, izgara, kaydir, gkutu, h)
    kayip = []
    # DIŞ ÖLÇÜLER KESİNLİKLE YER ALIR: gabari en son, en dışa çizilir ama
    # uzatma çizgilerinin yolu (parçanın uç kenarlarından dışarı) şimdiden
    # AYRILIR - konum rakamları o yola konmaz. Yoksa kenar dibindeki küçük
    # bir rakam ("11,4") gabarinin bütün kademelerini kapatıyor, 1854
    # hiç yazılmıyordu (P01).
    gplan = gabari_plani(gkutu, sac_kesit, o.get("bukum_ekseni"), ana=ana_gorunus(gkutu, o))
    gabari_yolu = _gabari_yolu_ayir(msp, gkutu, gplan, h)
    # KONUM ÖLÇÜLERİ İKİ GEÇİŞ: önce DENEME - ana görünüşe temiz
    # yerleşemeyenler bulunur, deneme silinir; onlardan DETAY BÖLGELERİ
    # seçilir, bölgelerin içindeki özellikler ana görünüşten çıkar (bkz.
    # bolge_plani), sonra asıl yerleşim.
    bolgeler, bolge_olcu, kplan_ana = [], {}, kplan
    if kplan:
        import copy as _copy
        onceki_h = {e.dxf.handle for e in msp}
        kayip_top = []
        # En çok 3 deneme: her denemede ana görünüşe temiz yerleşemeyenler
        # BİRİKİR, bantlar onlardan yeniden seçilir (bir bant çıkınca
        # başka bir ölçü de düşebilir - onu da banda almak için).
        for _deneme in range(3):
            kayip_d = []
            konum_olculeri(msp, _copy.deepcopy(kplan_ana), kaydir, gkutu, h,
                           rapor=Counter(), kayip=kayip_d)
            _varlik_geri_al(msp, onceki_h)
            if not kayip_d:
                break
            kayip_top.extend(kayip_d)
            bolgeler = bolge_sec(kayip_top, gkutu, kaydir, h)
            if not bolgeler:
                break
            kplan_ana, bolge_olcu = bolge_plani(kplan, bolgeler, kaydir, h, kayip_top)
    sinir = konum_olculeri(msp, kplan_ana, kaydir, gkutu, h, rapor=atlanan,
                           kayip=kayip) if kplan else {}
    if sac_kanat:
        kanat_olculeri(msp, s, o, sac_kesit, kaydir, gkutu, h)
    if sac_kesit:
        kalinlik_notu(msp, s, o, sac_kesit, kaydir, gkutu, h)
    uyari = list(dict.fromkeys(PLAN_UYARI))
    if sac_kanat:
        try:
            e_ = o["bukum_ekseni"]
            uyari = uyari + kanat_uyarilari(sac_duvarlari(s, max(range(3), key=lambda i: abs(e_[i])),
                                                  float(o["sac_kalinlik_mm"])))
        except Exception:
            pass
    if kplan:
        girinti_olculeri(msp, kplan, kaydir, gkutu, h)
    if P.get("capraz", True):
        pah_notlari(msp, kenar_olcu, kaydir, gkutu, h)
    for e_ in gabari_yolu:
        msp.delete_entity(e_)
    atlanan["gabari_yok"] += gabari_olculeri(msp, gkutu, sinir, h, plan=gplan)
    kayip[:] = slot_notlari(o, kayip, atlanan)
    ust, sag = cap_olculeri(msp, o, yer, kaydir, gkutu, h, ust)
    if P.get("konum", True):
        aci_olculeri(msp, kenar_olcu, gorunusler, kaydir, gkutu, h)
    # Ana görünüşte yer bulamayan ölçüler kaybolmaz: DETAY görünüşüne
    harf_ = iter(DETAY_HARF)
    kullanilan_ = []
    detaylar = bolge_detaylari(msp, bolgeler, bolge_olcu, kenarlar, kaydir, gkutu, h,
                               rapor=atlanan, harf=harf_, kullanilan=kullanilan_)
    detaylar += detay_gorunusleri(msp, kenarlar, kaydir, gkutu, kayip, h, rapor=atlanan,
                                  harf=harf_, kullanilan=kullanilan_,
                                  engel=[kt for _a, kt in detaylar])
    SON_RAPOR.clear()
    SON_RAPOR.update(atlanan)            # denetim / test: son resmin eksikleri
    for gad, gk_ in gkutu.items():
        ust[gad] = max(ust.get(gad, gk_[3]), gorunus_etiketi(msp, gad, gk_, h) + 0.5 * h)
    if kplan:
        # Datum ve simetri EN SON: yerlerini bütün yazı ve çizgiler
        # konduktan sonra ölçerek bulurlar.
        datum_isaretleri(msp, datum_cercevesi(L, W, T), gorunusler, gkutu, h,
                         plan=kplan, kaydir=kaydir, kenarlar=kenarlar)
        simetri_isareti(msp, kplan, gkutu, h)
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
    # Başlık çizilmiş HER ŞEYİN üstünde: ölçüler artık görünüşün üstüne de
    # konuyor; yer tahminle değil ölçülen sınırla bulunur.
    tepe_ = max((b[3] for b in _varlik_kutulari(msp)), default=max(ust.values()))
    y0 = max(max(ust.values()), tepe_ + 0.5 * h) + 2.5 * h
    poz = f"POZ {k['poz']}   " if k.get("poz") else ""
    ad_ = str(k.get("ad") or "")[:60]
    kod_ = str(k.get("kod") or "")
    # kod ile ad aynıysa (ya da ad kodu içeriyorsa) bir kez yazılır
    kimlik = ad_ if (not kod_ or kod_ == ad_ or kod_ in ad_) else f"{kod_}   {ad_}"
    diger = [
        (f"adet: {k['adet']}", 1.1 * h),
        (gabari_satiri(o), 1.1 * h),
        (f"kütle {XL.tr(o['kutle_kg'], 3)} kg   malzeme: {k.get('malzeme_ad', '-')}", 1.1 * h),
    ] + ([(P["sade_not"], 1.1 * h)] if P.get("sade_not") else []) + [
        (f"! MODEL KONTROL: {u}", 1.1 * h) for u in uyari[:2]] + [
        # Ölçek ve birim resmin üstünde yazsın: DXF başka bir çizime
        # eklendiğinde ölçek kaymışsa bu satırdan anlaşılır.
        ("ölçek 1:1   birim: mm", 1.1 * h),
    ]
    satir = [(f"{poz}{kimlik}", 1.5 * h)] + diger
    # BAŞLIK ÖNCE IZGARANIN BOŞ HÜCRESİNE (SAĞ'ın altı, ÜST'le aynı satır):
    # en üstte dururken görünüşlerin yüksekliğine ekleniyor, A3'te antetin
    # üstündeki şeride sığmayan resim bir kademe küçük ölçeğe düşüyordu.
    # Hücreye sığmazsa ya da bir çizime değerse eski yerine, en üste.
    bos = [hc for hc in _bos_hucreler(gkutu, h)
           if not any(_cakisiyor(hc, [kt]) for _a, kt in detaylar)]
    yerlesti = False
    def _bol(metin, th, en_):
        """Satırı hücre enine göre kelime kelime böler."""
        sig = max(12, int(en_ / (0.62 * th)))
        sat_, cur = [], ""
        for w in metin.split():
            if cur and len(cur) + 1 + len(w) > sig:
                sat_.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            sat_.append(cur)
        return [(t, th) for t in sat_]
    for hc in bos:
        en_ = hc[2] - hc[0]
        satir_h = [q for t, th in satir for q in _bol(t, th, en_)]
        dolu_ = _varlik_kutulari(msp)
        onceki = {e.dxf.handle for e in msp}
        _tablo(msp, satir_h, hc[0], hc[3] - 1.2 * h, h, sat_h)
        yeni_ = [e for e in msp if e.dxf.handle not in onceki]
        try:
            kb_ = ezdxf.bbox.extents(yeni_, fast=False)
            bk = (kb_.extmin.x, kb_.extmin.y, kb_.extmax.x, kb_.extmax.y)
        except Exception:
            bk = None
        if (bk and bk[0] >= hc[0] - 1e-6 and bk[2] <= hc[2] + 1e-6
                and bk[1] >= hc[1] - 1e-6 and not _cakisiyor(bk, dolu_, 0.5 * h)):
            gorunus_isareti(msp, "BILGI", bk)
            yerlesti = True
            break
        for e in yeni_:
            msp.delete_entity(e)
    if not yerlesti:
        tepe = y0 + len(satir) * sat_h
        onceki = {e.dxf.handle for e in msp}
        _tablo(msp, satir, sol, tepe, h, sat_h)
        # Başlığın yeri TAHMİN EDİLMEZ, ÖLÇÜLÜR: yazının kapladığı yer yazı
        # tipine bağlıdır. Ölçüm, görünüş işaretleri konmadan ÖNCE yapılır
        # - yoksa kendi işaretlerimizi de ölçer ve başlık bütün resmi kaplar.
        _baslik_isareti(msp, onceki, (sol, y0, sol + 40.0 * h, tepe))
    # Görünüşlerin yerini işaretle: pafta bunlara bakıp her görünüşü ayrı
    # pencereye alır ve kâğıda eşit dağıtır.
    for gad, kt in gkutu.items():
        gorunus_isareti(msp, gad, kt)
    for ad_d, kt in detaylar:
        gorunus_isareti(msp, ad_d, kt)
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
             (f"gabari BOY x EN x YUKSEKLIK : {XL.tr(L, 2, False)} x {XL.tr(W, 2, False)} x "
              f"{XL.tr(H, 2, False)} mm", 1.1 * h),
             (f"kati sayisi: {len(katilar)}", 1.1 * h)]
    if bom:
        agir = sum((r.get("toplam_kg") or 0.0) for r in bom)
        satir.append((f"toplam kutle: {XL.tr(agir, 3, False)} kg   poz sayisi: {len(bom)}", 1.1 * h))
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
    ka = XL.tr(r["kg_adet"], 3, False) if r.get("kg_adet") else "-"
    tk = XL.tr(r["toplam_kg"], 3, False) if r.get("toplam_kg") else "-"
    return (f"{str(r['poz']):>3s} {r['kod'][:22]:<22s} {r['ad'][:30]:<30s} "
            f"{r['adet']:>4d} {(r.get('malzeme_ad') or '-')[:22]:<22s} "
            f"{(r.get('olcu') or '-'):<22s} {ka:>9s} {tk:>9s}")


def bom_satirlari(bom, h, en_cok=40):
    """BOM tablosunu DXF yazı satırlarına çevirir."""
    st = [("BOM - PARÇA LİSTESİ", 1.3 * h),
          (f"{'poz':>3} {'kod':<22s} {'tanım':<30s} {'adet':>4} {'malzeme':<22s} "
           f"{'ölçü (BxExK)':<22s} {'kg/adet':>9s} {'toplam kg':>9s}", 1.05 * h)]
    for r in bom[:en_cok]:
        st.append((_bom_metin(r), 1.05 * h))
    if len(bom) > en_cok:
        st.append((f"... +{len(bom) - en_cok} poz daha (BOM.csv)", 1.05 * h))
    return st


# ---------------------------------------------------------------- komponentleme
def geometriden_sinifla(kayit, komp, kural=None, log=print):
    """ADI BİLGİ TAŞIMAYAN katıları YÜZLERİNE bakarak sınıflar: pul, somun,
    cıvata, perçin, perçin somun, pim, o-ring, kaynak dikişi (pf8_tani).

    Adı bilgi taşımayan: adsız ("COMPOUND", "SOLID", "Body") ya da yalnız
    parça numarası ("FT108161", "55RS865978"). Tente kompleksi modelinde
    41 flanşlı cıvata, 29 mercimek başlı cıvata ve 69 perçin somun
    böyle adlandırılmıştı; geometri tanıyordu ama yalnız öneri yazıyordu,
    hepsi üretim parçası kalıyordu. Adı ne olduğunu söyleyen parçada
    ("... SACI", "M6 SOMUN") ad kazanır; geometri yalnız ÖNERİ olarak
    yazılır (k["oneri"]) - 2. sekmede görünür, kullanıcı isterse
    sınıfını değiştirir.

    Ölçüldü (5 gerçek model): geometri 236 karar verdi, 1'i yanlış
    (%0,42 - adında SAC geçen pul biçimli parça);
    182 kaynak kararının hepsi doğru, hiçbir üretim parçası dikiş
    sayılmadı. Emin olunmayan katıya karar verilmez."""
    karar = oneri = numarali = 0
    isimsiz = []
    for k in komp:
        if k["sinif"] != "parca" or _kural(kural, k):
            continue
        adsiz = TN.isimsiz(k["ad"])
        try:
            r = TN.tani(kayit[k["indeks"][0]][1], k.get("hacim_mm3"))
        except Exception:
            r = None
        if not r:
            if adsiz:
                k["isimsiz"] = True
                isimsiz.append(k)
            continue
        if adsiz or not ad_bilgili(k["ad"]):
            k["sinif"], k["tip"] = r[0], (r[1] or "") + " (geometri)"
            k["geometri"] = r[2]
            karar += 1
            numarali += not adsiz
        else:
            k["oneri"] = r
            oneri += 1
    if karar or oneri or isimsiz:
        log(f"geometriden tanıma: {karar} komponent sınıflandı"
            + (f" ({numarali} tanesinin adı yalnız parça numarası)" if numarali else "")
            + (f", {oneri} parçada öneri" if oneri else "")
            + (f"; {len(isimsiz)} adsız katı TANINAMADI (parça sayıldı, "
               "2. sekmede elle sınıflayın)" if isimsiz else ""))
    return karar, oneri


# ------------------------------------------------ standart tanımı kontrolü
# KURAL: CAD ne olursa olsun, standart (satın alınan) parçanın tanımı
# belirsizse program SÖYLER. Tasarımcı ya CAD'de düzeltir (ad ya da
# Made/Bought) ya da listeyi olduğu gibi kabul eder; kabul kayda geçer.
KONTROL_DOSYASI = "STANDART_KONTROL.xlsx"
KONTROL_BASLIK = ["durum", "kod", "ad", "adet", "olcu", "simdiki_sinif", "oneri",
                  "gerekce", "kaynak"]


def standart_denetimi(kayit, komp, kural=None, log=print):
    """Adı bilgi taşımayan (adsız ya da yalnız parça numarası) ve biçimi
    satın alınan elemana benzeyen üretim parçalarına k["aday"] yazar:
    dönel küçük parça, diş / helis modelli, helis yay. KARAR DEĞİLDİR;
    kontrol listesine gerekçesiyle girer.

    Ölçüldü (5 gerçek model): adı standart diyen 60 komponentin hepsi
    bu işaretlerden en az birini taşıyor (cıvata, somun, pul, rulman,
    pim, perçin, kauçuk takoz, yay); adı üretim diyen 14 parça da
    taşıyor (burç, kare delikli plaka) - o yüzden karar değil uyarı."""
    if kural is None:
        kural = ayar_oku().get("sinif_kurali") or {}
    n = 0
    for k in komp:
        k.pop("aday", None)
        if (k["sinif"] != "parca" or _kural(kural, k) or k.get("profil")
                or k.get("cad_kaynak") or ad_bilgili(k["ad"])):
            continue
        isr = TN.aday_isaretleri(kayit[k["indeks"][0]][1], k.get("hacim_mm3"))
        if isr:
            k["aday"] = [g for _a, g in isr]
            n += 1
    liste = kontrol_listesi(komp)
    if liste:
        log(f"! STANDART TANIMI KONTROL: {len(liste)} parça belirsiz "
            f"({sum(r[0].startswith('geometri') for r in liste)} biçiminden standart "
            f"sayıldı, {sum(r[0].startswith('standart olabilir') for r in liste)} standart "
            f"olabilir, {sum(r[0].startswith('tanınmadı') for r in liste)} adsız ve "
            f"tanınmadı). Tasarımcı CAD'de düzeltsin ya da listeyi onaylayın.")
    return n


def kontrol_listesi(komp):
    """Standart tanımı belirsiz parçalar: [durum, kod, ad, adet, ölçü,
    şimdiki sınıf, öneri, gerekçe, kaynak(boş - tasarımcı doldurur)]."""
    out = []
    for k in komp:
        olc = _olc_metni(k)
        if k["sinif"] == "standart" and k.get("geometri"):
            out.append(["geometri: standart sayıldı - onaylayın", k["kod"], k["ad"],
                        k["adet"], olc, "standart", (k.get("tip") or "").replace(" (geometri)", ""),
                        k["geometri"], ""])
        elif k["sinif"] == "parca" and k.get("aday"):
            out.append(["standart olabilir - kontrol edin", k["kod"], k["ad"], k["adet"],
                        olc, "parca", "standart?", "; ".join(k["aday"]), ""])
        elif k["sinif"] == "parca" and k.get("isimsiz"):
            out.append(["tanınmadı: adsız katı", k["kod"], k["ad"], k["adet"], olc,
                        "parca", "", "adı yok, biçimi bilinen bir elemana uymuyor", ""])
        elif k["sinif"] == "parca" and k.get("oneri") and k["oneri"][0] != "parca":
            out.append(["ad ile biçim çelişiyor", k["kod"], k["ad"], k["adet"], olc,
                        "parca", k["oneri"][1] or k["oneri"][0], k["oneri"][2], ""])
        else:
            continue
        a = k.get("ai")
        if a:
            out[-1][6] = (f"AI ({a.get('karar', '')}): {a['sinif']}"
                          + (f" ({a['tip']})" if a["tip"] else "")
                          + f" %{XL.tr(100 * a['guven'], 0, sade=False)}")
            out[-1][7] = f"{out[-1][7]} | AI: {a['gerekce']}"
    return out


def _karar_kaynagi(k):
    if k.get("ogrenildi"):
        return "benzerinden öğrenme (daha önce elle düzeltilen parçaya benziyor)"
    if k.get("katalog"):
        return "standart ürün kataloğundaki bir STEP'e biçimce benziyor"
    if k.get("geometri"):
        return "geometri ölçümü"
    if k.get("profil"):
        return "kesit ölçümü (profil)"
    if TN.isimsiz(k["ad"]):
        return "yok: adsız katı, bilinen biçime uymadı"
    if ad_bilgili(k["ad"]):
        return "parça adı / montaj ağacı"
    return "yok: ad yalnız numara, biçim bilinen bir elemana uymadı (varsayılan: parca)"


def ai_girdisi(komp, kural=None):
    """AI kontrolüne gidecek veri: kaynak dikişleri, kullanıcının ELLE
    verdiği ve CAD'in Made/Bought ile söylediği sınıflar HARİÇ bütün
    komponentler; her birinin sınıfı, kararın kaynağı ve programın
    ölçtüğü bulgular. CAD dosyası / geometri gitmez.
    Döner: (parcalar, baglam, oncelik) - no = komp listesindeki sıra,
    oncelik = programın zaten belirsiz bulduğu (kontrol listesi)."""
    if kural is None:
        kural = ayar_oku().get("sinif_kurali") or {}
    kontrol = {id(k) for k in _kontrol_komp(komp)}
    parcalar, oncelik = [], []
    for i, k in enumerate(komp):
        if k["sinif"] == "kaynak" or k.get("cad_kaynak") or _kural(kural, k):
            continue
        b = []
        if k.get("geometri"):
            b.append("program ölçtü: " + k["geometri"])
        if k.get("profil"):
            b.append("program ölçtü: " + k["profil"]["gerekce"])
        for g in k.get("aday") or []:
            b.append("program ölçtü (işaret): " + g)
        if k.get("oneri"):
            b.append("program ölçtü (biçim önerisi): " + k["oneri"][2])
        parcalar.append({"no": i, "kod": k["kod"], "ad": k["ad"], "adet": k["adet"],
                         "olcu_mm": [round(float(v), 1) for v in (k.get("olc") or [])],
                         "program_sinif": k["sinif"], "program_tip": k.get("tip") or "",
                         "karar_kaynagi": _karar_kaynagi(k), "bulgular": b})
        if id(k) in kontrol:
            oncelik.append(i)
    uretim = [k["kod"] for k in komp if k["sinif"] == "parca"
              and (k.get("profil") or "sac" in (k.get("tip") or ""))][:25]
    baglam = {"komponent_sayisi": len(komp),
              "uretim_parcasi_numara_ornekleri": uretim,
              "standart_numara_ornekleri": [k["kod"] for k in komp
                                            if k["sinif"] == "standart"
                                            and not k.get("geometri")][:25]}
    return parcalar, baglam, oncelik


def ai_goruntu(kayit, komp):
    """AI'ın 2. turu için: no -> parçanın PNG resmi."""
    def f(no):
        return TN.parca_png(kayit[komp[no]["indeks"][0]][1], boyut=384)
    return f


def ai_isle(komp, sonuc):
    """AI sonuçlarını komponentlere yazar (k["ai"]); sınıfı DEĞİŞTİRMEZ."""
    for no, r in sonuc.items():
        if 0 <= no < len(komp):
            komp[no]["ai"] = r
    return len(sonuc)


def _kontrol_komp(komp):
    out = []
    for k in komp:
        if ((k["sinif"] == "standart" and k.get("geometri"))
                or (k["sinif"] == "parca" and (k.get("aday") or k.get("isimsiz")
                                               or (k.get("oneri") and k["oneri"][0] != "parca")))):
            out.append(k)
    return out


def kontrol_yaz(on, komp):
    """STANDART_KONTROL.xlsx: tasarımcıya gönderilecek liste. 'kaynak'
    sütununa Bought (satın alınan) ya da Made (üretim) yazılıp dosya
    2. adımda 'Malzeme listesi yükle...' ile geri verilince sınıflar oradan
    alınır. Liste boşsa eski dosya silinir. Yazılan yolu döner."""
    y = os.path.join(on, KONTROL_DOSYASI)
    liste = kontrol_listesi(komp)
    if not liste:
        if os.path.isfile(y):
            try:
                os.remove(y)
            except OSError:
                pass
        return None
    os.makedirs(on, exist_ok=True)
    aciklama = [
        ["Bu listedeki parçaların standart (satın alınan) mı üretim mi olduğu "
         "modelden kesin anlaşılamadı."],
        ["Kısa yol: 'kaynak' sütununa Bought (satın alınan) ya da Made (üretim) "
         "yazın, dosyayı Pi3D'de 2. adımda 'Malzeme listesi yükle...' ile verin."],
        ["Kalıcı çözüm: CAD'de parçanın Source (Made / Bought) alanını doldurun "
         "ya da adını düzeltin (ör. 'ISO 7380 M8x16'). Pi3D bir kez düzeltilen "
         "parçanın biçimini öğrenir; benzerleri kendiliğinden tanınır."]]
    return XL.xlsx_yaz(y, [("Kontrol", KONTROL_BASLIK, liste),
                           ("Nasıl doldurulur", ["açıklama"], aciklama)])


# Açık kesitin kısa adı ("bükümlü sac, U kesit 40x15x1,5" gibi)
KESIT_KISA = {"köşebent": "L", "U profil": "U", "C profil": "C", "T profil": "T",
              "Z profil": "Z", "I/H profil": "I", "lama": "düz", "ekstrüzyon": "özel",
              "özel kesit": "özel",
              "dolu çubuk": "dikdörtgen", "kare çubuk": "kare"}
KAPALI_PROFIL = ("kutu", "kare kutu", "boru", "mil")


def profilden_tanimla(kayit, komp, log=print):
    """Üretim parçalarından PROFİLLERİ bulur: kutu, boru, köşebent, U, C,
    I, T, lama, mil, alüminyum ekstrüzyon (pf8_tani.profil - adına
    bakılmaz, parça boyuna kesilip kesit ölçülür).

    Profil biçimli her parça profil DEĞİLDİR: 1,5 mm sacdan bükülmüş U
    da sabit kesitlidir ama açınımla lazerde kesilip bükülür. Açık kesitte
    sac taraması "bükümlü sac" diyorsa parça sac sayılır (tipine yalnız
    kesiti yazılır); kutu / boru / mil ve dolu sac olamayacak özel kesit
    profildir. Profiller k["profil"]'e yazılır, PROFIL.xlsx kesim
    listesine girer.

    Ölçüldü (4 gerçek model): 38 profil (kare kutu 24, boru 7, kutu 4,
    alüminyum ekstrüzyon 3) ve 76 profil biçimli bükümlü sac; kesitler
    resmi çizilip tek tek karşılaştırıldı."""
    say, sacli = Counter(), 0
    for k in komp:
        if k["sinif"] != "parca":
            continue
        sh = kayit[k["indeks"][0]][1]
        try:
            r = TN.profil(sh, k.get("hacim_mm3"))
        except Exception:
            r = None
        # 5 mm'den ince, 20 mm'den kısa "profil" yay teli, pim gibi
        # küçük parçadır; kesim listesine girmez
        if not r or max(r["W"], r["H"]) < 5.0 or r["boy"] < 20.0:
            continue
        sac = ""
        y_ = r.get("yapi") or {}
        # kapalı hücre / T-kanal / vida kanalı olan ekstrüzyon bükülerek
        # yapılamaz: ince eşit cidarı sac taramasına "bükümlü sac" dedirtse de
        # profildir (TIRSAN_Ray 112,5: 3 hücre + 2 T-kanal)
        ekstruzyon = (r["tur"] == "ekstrüzyon"
                      and y_.get("hucre", 0) + y_.get("t_kanal", 0) + y_.get("vida", 0) >= 2)
        if r["tur"] not in KAPALI_PROFIL and not ekstruzyon:
            try:
                sac = sac_taramasi(sh)["tip"]
            except Exception:
                sac = ""
        # 3 mm ve incesi "lama" lazerde kesilmiş sac şerididir (lama
        # stoğu 3 mm'den başlar): kaynaklı kasada 30 x 1,5 bağlantı saçı
        if (sac == "bukumlu sac" or (r["tur"] == "lama" and (
                sac == "duz sac" or min(r["W"], r["H"]) <= 3.0))):
            k["kesit"] = r
            k["tip"] = (f"{'bükümlü' if sac == 'bukumlu sac' else 'düz'} sac, "
                        f"{KESIT_KISA.get(r['tur'], r['tur'])} kesit {r['kesit']}")
            sacli += 1
            continue
        k["profil"] = r
        k["tip"] = r["ad"]
        say[r["tur"]] += 1
    if say or sacli:
        log(f"profil: {sum(say.values())} parça"
            + (" (" + ", ".join(f"{t} {n}" for t, n in say.most_common()) + ")"
               if say else "")
            + (f"; {sacli} parça profil biçimli sac (açınımla üretilir)" if sacli else ""))
    return say, sacli


def komponentle(kayit, P, kural=None):
    """Aynı parçanın kopyalarını tek komponentte toplar (ad + hacim + gabari)."""
    if kural is None:
        kural = ayar_oku().get("sinif_kurali") or {}
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
        sinif, tip = sinifla(ad, kural)
        k = {"hacim_mm3": v, "olc": list(_olc)}
        g = _kural(kural, dict(k, ad=ad)) if not ad_bilgili(ad) else None
        if g in ("parca", "standart", "kaynak"):
            sinif, tip = g, ("elle" if g == "standart" else "")
        out.append({"ad": ad, "kod": kod_cikar(ad), "adet": len(idx), "indeks": idx,
                    "hacim_mm3": v, "olc": list(_olc), "sinif": sinif, "tip": tip,
                    "malzeme_data": mal.get(an),
                    "malzeme_yogunluk": getattr(mal.get(an), "yogunluk", None)})
    return out


# ---------------------------------------------------------------- malzeme seçimi
# CAD'lerin parça listesi dışa aktarımlarında sütun başlıkları.
# Sütun başlıkları. SIRA ÖNEMLİ: önce en belirgin olan aranır. Inventor'ın
# listesinde ilk sütun "Item" (1, 2, 3...) - "item" genel adaylardan önce
# gelseydi parça kodu yerine sıra numarası seçilirdi.
KOD_BASLIK = ("part number", "partnumber", "part no", "partno", "part no.",
              "teilenummer", "sachnummer", "artikelnummer", "document number",
              "db_part_no", "model name", "part name", "file name",
              "kod", "code", "reference", "référence", "malzeme no",
              "stok kodu", "parca", "parça", "part", "number", "no")
MAL_BASLIK = ("sw-material", "ptc_material_name", "material name",
              "malzeme adi", "malzeme adı", "material", "malzeme", "werkstoff",
              "matiere", "matière", "materyal")
YOG_BASLIK = ("sw-density", "density", "yogunluk", "yoğunluk", "dichte",
              "densite", "densité", "masse volumique")


class MalzemeDosyaHatasi(Exception):
    """Malzeme dosyası okunamadı; ileti kullanıcıya ne yapacağını söyler."""


def _ayirici(satir):
    for a in ("\t", ";", ","):
        if a in satir:
            return a
    return ";"


def _sutun(basliklar, adaylar):
    """Başlık satırında aranan sütunun indeksi; yoksa None.

    Adaylar ÖNCELİK sırasıyla denenir: önce tam eşleşme, sonra içinde
    geçen - sütun sırasına göre değil."""
    b = [_tr_sade(x) for x in basliklar]
    for a in adaylar:
        for i, x in enumerate(b):
            if x == a:
                return i
    for a in adaylar:
        for i, x in enumerate(b):
            # içinde geçen: yalnız BAŞLIK gibi kısa hücrede. CATIA'nın
            # "Bill of Material: JMS_KIT_KARLUNA" bölüm satırı malzeme
            # sütunu sanılıyordu.
            if a in x and len(x) <= 40 and ":" not in x:
                return i
    return None


def _metin_coz(ham):
    """Baytları metne çevirir. CAD'lerin dışa aktardığı dosyalar UTF-8,
    UTF-16 (Excel "Unicode metin") ya da Windows Türkçe (cp1254) olabilir.
    Eski kod her şeyi UTF-8 sayıp bozuk baytları '?' yapıyordu: CATIA
    makrosunun ANSI yazdığı "Çelik" "?elik" oluyordu."""
    if ham[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return ham.decode("utf-16")
    for kod in ("utf-8-sig", "cp1254"):
        try:
            return ham.decode(kod)
        except UnicodeDecodeError:
            pass
    return ham.decode("latin-1")


def _xlsx_satirlari(ham):
    """Excel .xlsx'in İLK sayfası -> satır listesi. Ek paket gerekmez:
    .xlsx bir zip içinde XML'dir; standart kütüphaneyle okunur (EXE'ye
    yeni bağımlılık girmesin)."""
    import io as _io
    import zipfile
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    try:
        z = zipfile.ZipFile(_io.BytesIO(ham))
    except zipfile.BadZipFile:
        raise MalzemeDosyaHatasi("Excel dosyası açılamadı (bozuk ya da "
                                 "parolalı olabilir). CSV olarak kaydedin.")
    ortak = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            ortak.append("".join(t.text or "" for t in si.iter(
                "{%s}t" % ns["m"])))
    # İlk sayfanın dosyası: workbook.xml + ilişkiler
    sayfa = "xl/worksheets/sheet1.xml"
    try:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        ilk = wb.find("m:sheets/m:sheet", ns)
        rid = ilk.get("{%s}id" % ns["r"]) if ilk is not None else None
        rel = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        for r in rel:
            if r.get("Id") == rid:
                h = r.get("Target").lstrip("/")
                sayfa = h if h.startswith("xl/") else "xl/" + h
    except Exception:
        pass
    if sayfa not in z.namelist():
        raise MalzemeDosyaHatasi("Excel dosyasında sayfa bulunamadı.")

    def sutun_no(ref):
        n = 0
        for c in ref:
            if c.isalpha():
                n = n * 26 + (ord(c.upper()) - 64)
            else:
                break
        return n - 1

    satirlar = []
    for row in ET.fromstring(z.read(sayfa)).iter("{%s}row" % ns["m"]):
        hucre = {}
        for c in row.findall("m:c", ns):
            t = c.get("t")
            v = c.find("m:v", ns)
            if t == "s" and v is not None:
                deger = ortak[int(v.text)] if v.text and v.text.isdigit() \
                    and int(v.text) < len(ortak) else ""
            elif t == "inlineStr":
                deger = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
            else:
                deger = v.text if v is not None and v.text else ""
            hucre[sutun_no(c.get("r") or "A")] = deger
        if hucre:
            satirlar.append([hucre.get(k, "") for k in range(max(hucre) + 1)])
    return satirlar


def _html_satirlari(metin):
    """HTML tablo (<tr><td>/<th>) -> satır listesi."""
    import html as H
    out = []
    for tr in re.findall(r"<tr\b.*?>(.*?)</tr\s*>", metin, re.I | re.S):
        hucre = re.findall(r"<t[dh]\b.*?>(.*?)</t[dh]\s*>", tr, re.I | re.S)
        sat = [H.unescape(re.sub(r"<[^>]+>", "", h)).replace("\xa0", " ").strip()
               for h in hucre]
        if any(sat):
            out.append(sat)
    return out


def _tablo_satirlari(yol):
    """Tablo dosyası (CSV / TXT / TSV / XLSX) -> satır listesi (str)."""
    with open(yol, "rb") as f:
        ham = f.read()
    if ham[:4] == b"PK\x03\x04":
        return _xlsx_satirlari(ham)
    if ham[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        # eski Excel (.xls, Excel 97-2003): CATIA'nın Bill of Material >
        # Save As > Excel kaydı. Ek paket gerekmeden okunur (pf9_excel).
        try:
            return [[str(h).strip() for h in r] for r in XL.xls_satirlari(ham)]
        except Exception as ex:
            raise MalzemeDosyaHatasi(
                f"Bu eski Excel dosyası (.xls) okunamadı ({ex}). Excel'de açıp "
                "'Farklı kaydet' ile .xlsx olarak kaydedip yeniden deneyin.")
    metin = _metin_coz(ham)
    if re.search(r"<\s*(table|tr)\b", metin[:20000], re.I):
        # CATIA'nın "Excel" kaydı bazı kurulumlarda .xls uzantılı HTML tablodur
        return _html_satirlari(metin)
    dolu = [x for x in metin.splitlines() if x.strip()]
    if not dolu:
        return []
    ayr = _ayirici(dolu[0] if len(dolu) == 1 else
                   max(dolu[:5], key=lambda x: sum(x.count(a) for a in "\t;,")))
    # csv modülü tırnaklı hücreleri doğru ayırır ("Steel, AISI 1020").
    return [[h.strip() for h in r] for r in csv.reader(dolu, delimiter=ayr)]


def _yogunluk_coz(hucre, baslik=""):
    """Yoğunluk hücresi -> g/cm³ (ya da None).

    Birim hücrede ya da başlıkta yazıyorsa ondan çözülür; yazmıyorsa
    değerin büyüklüğünden: 100'den büyükse kg/m³ sayılır (çelik 7850),
    küçükse g/cm³ (çelik 7,85). 0,3 - 23 g/cm³ dışı reddedilir - bilinen
    hiçbir mühendislik malzemesi o aralığın dışında değildir."""
    t = _tr_sade(str(hucre or "")).replace(",", ".")
    m = re.search(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", t)
    if not m:
        return None
    try:
        v = float(m.group())
    except ValueError:
        return None
    b = t + " " + _tr_sade(baslik or "")
    if "kg/mm" in b:
        v *= 1e6
    elif "g/mm" in b:
        v *= 1e3
    elif "kg/m" in b:
        v /= 1000.0
    elif "lb/in" in b:
        v *= 27.6799
    elif "lb/ft" in b:
        v *= 0.0160185
    elif any(x in b for x in ("g/cm", "g/cc", "kg/dm", "g/ml", "t/m")):
        pass
    elif v > 100:
        v /= 1000.0
    return round(v, 4) if 0.3 <= v <= 23.0 else None


def malzeme_ozel(ad, yogunluk, taban=None):
    """CAD'den gelen, tabloda karşılığı olmayan (ya da yoğunluğu
    tablodakinden farklı) malzemeyi çalışma süresince tanımlar.

    Eskiden adı tanınmayan malzeme sessizce VARSAYILAN malzemeye (çelik)
    düşüyordu: 2,7 g/cm³'lük bir alüminyum alaşımı adı tanınmasa çelik
    kütlesiyle yazılıyordu. Yoğunluk biliniyorsa kütle onunla hesaplanır.
    Döner: MALZEME sözlüğüne eklenen anahtar."""
    ad = (str(ad or "").strip() or "CAD malzemesi")[:60]
    anahtar = _tr_sade(f"cad:{ad}@{yogunluk:.3f}")
    if anahtar not in MALZEME:
        gor = f"{ad}  (CAD: {XL.tr(yogunluk, 2, sade=False)} g/cm3)"
        MALZEME[anahtar] = (gor, float(yogunluk))
    return anahtar


def malzeme_yogunluklu(ad, yogunluk=None, pay=0.02):
    """Ad + (varsa) yoğunluk -> malzeme anahtarı; hiçbiri yoksa None.

    Ad tanınır ve yoğunluk tablodakiyle %2 içinde tutarsa tablo malzemesi;
    yoğunluk farklıysa ya da ad tanınmıyorsa CAD'in yoğunluğuyla özel
    malzeme. CAD'deki yoğunluk o parçanın GERÇEK tanımıdır; tablodaki
    ise yalnız bir varsayımdır."""
    m = malzeme_coz(ad) if ad else None
    if yogunluk:
        if m and abs(MALZEME[m][1] - yogunluk) <= pay * MALZEME[m][1]:
            return m
        return malzeme_ozel(ad or (MALZEME[m][0] if m else ""), yogunluk, m)
    return m


def malzeme_tablosu(yol):
    """Malzeme dosyasının satır satır çözümü (sihirbazın önizlemesi için).

    Döner: [{"kod", "malzeme", "yogunluk", "anahtar", "durum"}]
      durum: "tanındı" / "CAD yoğunluğuyla" / "tanınmadı"
    Hata: MalzemeDosyaHatasi (ileti kullanıcıya gösterilebilir)."""
    if yol.lower().endswith(".json"):
        ham = json.load(open(yol, encoding="utf-8")) or {}
        tablo = [["kod", "malzeme"]] + [[k, str(v)] for k, v in ham.items()]
    else:
        tablo = _tablo_satirlari(yol)
    if not tablo:
        return []
    ik = im = iy = bas = None
    for n, sat in enumerate(tablo[:15]):
        k = _sutun(sat, KOD_BASLIK)
        m = _sutun(sat, MAL_BASLIK)
        if k is not None and m is not None and k != m:
            ik, im, bas = k, m, n
            iy = _sutun(sat, YOG_BASLIK)
            if iy in (ik, im):
                iy = None
            break
    if bas is None:
        # Parça no başlığı var ama malzeme sütunu yok (CATIA'da Material
        # görünür listeye alınmamış): "kod;malzeme" varsayımı burada YANLIŞ
        # sonuç verir (Part Number malzeme sanılır) - açıkça söylenir.
        for sat in tablo[:15]:
            if _sutun(sat, KOD_BASLIK) is not None and \
                    sum(1 for h in sat if str(h).strip()) >= 2:
                raise MalzemeDosyaHatasi(
                    "Dosyada MALZEME sütunu yok (bulunan sütunlar: "
                    + ", ".join(str(h) for h in sat if str(h).strip())[:120]
                    + "). CATIA'da: Analyze > Bill of Material > Define formats > "
                    "'Hidden Properties' listesinden Material'i (ve Source'u) seçip "
                    "'>' ile görünür tarafa alın > OK > Save As > Excel.")
        ik, im, bas = 0, 1, -1          # başlık yok: kod;malzeme varsayılır
    ybas = tablo[bas][iy] if (bas >= 0 and iy is not None) else ""
    out = []
    for sat in tablo[bas + 1:]:
        if len(sat) <= max(ik, im):
            continue
        kod, mal = sat[ik].strip().strip('"'), sat[im].strip().strip('"')
        if not kod or _tr_sade(kod) in KOD_BASLIK:
            continue
        y = (_yogunluk_coz(sat[iy], ybas)
             if iy is not None and iy < len(sat) else None)
        if not mal and not y:
            continue
        taban = malzeme_coz(mal) if mal else None
        a = malzeme_yogunluklu(mal, y)
        durum = ("tanınmadı" if not a else
                 "CAD yoğunluğuyla" if a.startswith("cad:") else "tanındı")
        out.append({"kod": kod, "malzeme": mal, "yogunluk": y,
                    "anahtar": a, "taban": taban, "durum": durum})
    return out


def malzeme_dosya_oku(yol):
    """kod -> malzeme eşlemesi okur.

    Biçimler: bizim şablonumuz (kod;malzeme;ad), CAD'lerin parça listesi
    çıktısı (CATIA, SolidWorks, NX, Creo, Inventor, Solid Edge - CSV, TXT,
    sekmeli metin ya da Excel .xlsx), JSON. Başlıklar adlarından bulunur,
    ayırıcı ve kodlama kendiliğinden anlaşılır; yoğunluk sütunu varsa
    kullanılır (bkz. malzeme_yogunluklu).

    Döner: (eşleme, tanınmayan adlar). Okunamazsa MalzemeDosyaHatasi."""
    esl, bilinmeyen = {}, []
    for r in malzeme_tablosu(yol):
        if r["anahtar"]:
            esl[_tr_sade(r["kod"])] = r["anahtar"]
        elif r["malzeme"]:
            bilinmeyen.append(r["malzeme"])
    return esl, sorted(set(bilinmeyen))


# CAD'in "Made / Bought" (üretilen / satın alınan) alanı. CATIA'da her
# ürünün Özellikler > Ürün > "Source" alanıdır; Pi3D'nin CATIA makrosu
# (catia_malzeme_cikar.CATScript) malzeme.csv'nin 4. sütununa yazar.
# Tasarımcının kendi verdiği bilgidir: addan ya da biçimden TAHMİNDEN
# her zaman daha doğrudur.
KAYNAK_BASLIK = ("source", "kaynak", "make/buy", "make or buy", "tedarik",
                 "beschaffungsart", "beschaffung", "procurement", "provenance")
_SATIN = r"bought|\bbuy|purchas|sat[ıi]n|kaufteil|zukauf|achat|fremdteil|standart"
_URET = r"\bmade\b|\bmake\b|[uü]retim|imalat|eigenfertig|eigenteil|fabriqu|\bpar[cç]a\b"


def cad_kaynagi_oku(yol):
    """Dosyada "Source / kaynak" sütunu varsa kod -> "standart" | "parca".
    Sütun yoksa boş sözlük (malzeme dosyası yine malzeme için okunur)."""
    if yol.lower().endswith(".json"):
        return {}
    try:
        tablo = _tablo_satirlari(yol)
    except Exception:
        return {}
    for n, sat in enumerate(tablo[:15]):
        ik = _sutun(sat, KOD_BASLIK)
        ic = _sutun(sat, KAYNAK_BASLIK)
        if ik is None or ic is None or ik == ic:
            continue
        # Kontrol listesinde ölçü de vardır: aynı kodu taşıyan FARKLI
        # parçalar (tente kompleksinde 20'den fazla parça "55460008672")
        # ölçüleriyle ayrılır; anahtar "kod|ölçü".
        io = next((i for i, h in enumerate(sat) if _tr_sade(h) in ("olcu", "ölçü")), None)
        out = {}
        for r in tablo[n + 1:]:
            if len(r) <= max(ik, ic):
                continue
            kod, v = r[ik].strip().strip('"'), _tr_sade(r[ic])
            if not kod:
                continue
            s_ = ("standart" if re.search(_SATIN, v, re.I) else
                  "parca" if re.search(_URET, v, re.I) else None)
            if not s_:
                continue
            a = _tr_sade(kod)
            if io is not None and io < len(r) and r[io].strip():
                a += "|" + r[io].strip()
            out[a] = s_
        return out
    return {}


def _olc_metni(k):
    """Kontrol listesindeki ölçü yazımı (eşleştirme anahtarı)."""
    return " x ".join(f"{float(v):g}".replace(".", ",") for v in (k.get("olc") or []))


def malzeme_sutunu_var(yol):
    """Dosyanın ilk satırlarında malzeme sütunu başlığı var mı."""
    if yol.lower().endswith(".json"):
        return True
    try:
        tablo = _tablo_satirlari(yol)
    except Exception:
        return False
    for sat in tablo[:15]:
        m = _sutun(sat, MAL_BASLIK)
        if m is not None and _sutun(sat, KOD_BASLIK) not in (None, m):
            return True
    return False


def cad_kaynagiyla_sinifla(komp, harita, kural=None, log=print):
    """CAD'in Made/Bought bilgisiyle sınıflar: Bought -> standart (satın
    alınan, resmi çizilmez), Made -> üretim parçası. Kaynak dikişine ve
    kullanıcının elle verdiği sınıfa dokunulmaz. Eşleştirme malzemedeki
    gibi: parça kodu (Part Number) ya da adın içinde geçen kod."""
    if not harita:
        return 0
    if kural is None:
        kural = ayar_oku().get("sinif_kurali") or {}
    n = 0
    kod_say = Counter(_tr_sade(k["kod"]) for k in komp)
    for k in komp:
        if k["sinif"] == "kaynak" or _kural(kural, k):
            continue
        v = harita.get(_tr_sade(k["kod"]) + "|" + _olc_metni(k))
        if v is None and kod_say[_tr_sade(k["kod"])] > 1 and any(
                a.startswith(_tr_sade(k["kod"]) + "|") for a in harita):
            continue                    # ortak kod, bu ölçü listede yok
        if v is None:
            v = harita.get(_tr_sade(k["kod"]))
        if v is None:
            kod_s, ad_s = _tr_sade(k["kod"]), _tr_sade(k["ad"])
            for kod, s in harita.items():
                if len(kod) < 5 or "|" in kod:
                    continue
                dsn = r"(?<![0-9a-z])" + re.escape(kod) + r"(?![0-9a-z])"
                if re.search(dsn, kod_s) or re.search(dsn, ad_s):
                    v = s
                    break
        if v is None:
            continue
        k["cad_kaynak"] = v
        if v != k["sinif"]:
            k["sinif"] = v
            k["tip"] = "CAD: satın alınan" if v == "standart" else ""
            for a in ("geometri", "oneri", "isimsiz", "profil", "kesit"):
                k.pop(a, None)
            n += 1
    log(f"CAD'in Made/Bought bilgisi: {len(harita)} kayıt; {n} komponentin "
        f"sınıfı buna göre değişti")
    return n


def malzeme_sablonu(komp, yol):
    """Kullanıcının doldurup geri vereceği şablon: .xlsx (Excel) ya da
    .csv - yolun uzantısına göre."""
    sat = [[k["kod"], VARSAYILAN_MALZEME, k["ad"][:70]] for k in komp
           if k["sinif"] != "kaynak"]
    if yol.lower().endswith(".xlsx"):
        XL.xlsx_yaz(yol, [("Malzeme", ["kod", "malzeme", "ad"], sat)])
        return yol
    with open(yol, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["kod", "malzeme", "ad"])
        w.writerows(sat)
    return yol


def tablo_basliklari(yol, n=15):
    """Dosyanın ilk satırlarındaki dolu hücreler (malzeme sütunu yoksa
    kullanıcıya ne bulunduğunu söylemek için)."""
    try:
        tablo = _tablo_satirlari(yol)
    except Exception:
        return []
    for sat in tablo[:n]:
        dolu = [h for h in sat if str(h).strip()]
        if len(dolu) >= 2 and _sutun(sat, KOD_BASLIK) is not None:
            return dolu
    return []


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


def malzemesi_sorulacak(komp, esl):
    """Malzemesi SORULMASI gereken komponentler: EKSTRÜZYON profil (çok
    hücreli / kanallı kesit - çoğu alüminyumdur ama çelik de olabilir) ve
    malzemesi ne CAD'den (data) ne eşlemeden (dosya / kullanıcı) geliyor.
    Program burada çelik ya da alüminyum VARSAYMAZ, sorar (kullanıcı
    kararı)."""
    out = []
    for k in komp:
        if k.get("sinif") != "parca" or (k.get("profil") or {}).get("tur") != "ekstrüzyon":
            continue
        _m, kaynak = malzeme_ata(k, esl, VARSAYILAN_MALZEME)
        if kaynak == "genel":
            out.append(k)
    return out


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
        # STEP'te malzeme adı ve yoğunluğu varsa ikisi birlikte çözülür;
        # yoksa parça adındaki ipuçlarından ("S235", "AlMg3") tanınır.
        yog = k.get("malzeme_yogunluk")
        m = None
        if k.get("malzeme_data") and yog:
            yog = _yogunluk_coz(yog)
            m = malzeme_yogunluklu(str(k.get("malzeme_data")), yog)
        m = m or malzeme_tahmin(k.get("malzeme_data"), k.get("ad"))
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
    kural = ayar_oku().get("sinif_kurali") or {}
    komp = komponentle(kayit, P, kural)
    agac = ag[0] if ag else None
    if agac:
        agactan_sinifla(agac, komp, kural, log)
    geometriden_sinifla(kayit, komp, kural, log)
    benzerden_sinifla(kayit, komp, kural, log)
    try:
        katalogdan_sinifla(kayit, komp, kural, log=log)
    except Exception as ex:
        log(f"! katalog kullanılamadı: {type(ex).__name__}: {ex}")
    if agac:
        # geometri tanındıktan SONRA: adsız ürünü içindeki yay / pul / somun ele verir
        satin_alinan_montajlar(agac, komp, kayit, kural, log)
    profilden_tanimla(kayit, komp, log)
    standart_denetimi(kayit, komp, kural, log)
    sayim = Counter(k["sinif"] for k in komp)
    kyn = [k for k in komp if k["sinif"] == "kaynak"]
    log(f"{len(komp) - len(kyn)} komponent  ("
        + ", ".join(f"{a}: {b}" for a, b in sayim.items() if a != "kaynak") + ")"
        + (f"  + {len(kaynak_ozeti(kyn))} tür kaynak dikişi "
           f"({sum(k['adet'] for k in kyn)} adet, parça sayılmaz)" if kyn else ""))
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
        if d.get("satin_alinan"):
            # satın alınan montaj: TEK kalem, içi açılmaz (parçaları ona bağlı)
            sat["tur"], sat["kod"] = "standart", kod_cikar(d["ad"])
            out.append(sat)
            return
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
        # Kaynak dikişleri komponent DEĞİLDİR: her biri ayrı satır olunca
        # kaynaklı bir grupta 20 dikiş 20 "parça" gibi görünüyordu. Aynı
        # montajın altındaki dikişler TEK satırda, türüyle sayılır:
        #   KAYNAK DİKİŞLERİ (parça değil): K0 25 MM TEK KAYNAK x3, ...
        # Diğer kardeşler kesintisiz numaralanır (1, 2, 3 ...).
        dikis, n = [], 0
        for a in d.get("alt") or []:
            if _kaynak_yapragi(a):
                dikis.append({"ad": a["ad"], "adet": a.get("adet", 1)})
                continue
            n += 1
            gez(a, f"{poz}.{n}", seviye + 1, toplam)
        if dikis:
            oz = kaynak_ozeti(dikis)
            adet = sum(t[1] for t in oz)
            metin = ", ".join(f"{t} x{a}" for t, a in oz[:6])
            if len(oz) > 6:
                metin += f" (+{len(oz) - 6} tür)"
            out.append({"poz": f"{poz}.K", "seviye": seviye + 1, "kod": "",
                        "ad": f"KAYNAK DİKİŞLERİ (parça değil): {metin}",
                        "adet": adet, "toplam_adet": adet * toplam,
                        "tur": "kaynak", "malzeme_ad": "",
                        "malzeme_kaynak": "", "olcu": "", "kg_adet": "",
                        "toplam_kg": "", "kaynak_turleri": oz})

    def _kaynak_yapragi(d):
        if d.get("montaj") or d.get("alt") or not d.get("katilar"):
            return False
        ki = kati_komp.get(d["katilar"][0])
        return ki is not None and komp[ki]["sinif"] == "kaynak"

    gez(agac, "1", 0, 1)
    return out


def agac_bom_yaz(on, agac_satir):
    """Hiyerarşik BOM'u CSV ve okunabilir tablo olarak yazar."""
    alan = ["poz", "seviye", "tur", "kod", "ad", "adet", "toplam_adet",
            "malzeme_ad", "malzeme_kaynak", "olcu", "kg_adet", "toplam_kg"]
    XL.tablo_yaz(os.path.join(on, "BOM_AGAC.csv"), alan,
                 XL.sozlukten(alan, agac_satir), "BOM_AGAC")
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


def zip_yap(on, ad="cizimler.zip", desen=(".dxf", ".pdf")):
    """Üretilen çizimleri tek dosyada toplar; klasör düzeni korunur
    (DXF/, ACINIM/, LZR/, PDF/ ve kökteki tablolar)."""
    import zipfile
    yol = os.path.join(on, ad)
    tablo = (KONTROL_DOSYASI, "BOM.csv", "BOM.xlsx", "BOM.md", "BOM_AGAC.csv", "BOM_AGAC.xlsx",
             "BOM_AGAC.md", "olculer.csv", "olculer.xlsx", "olculer.json",
             "rapor.md", "ACINIM.csv", "ACINIM.xlsx", "LAZER.csv", "LAZER.xlsx",
             "PROFIL.csv", "PROFIL.xlsx", "KAYNAK.csv", "KAYNAK.xlsx")
    with zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED) as z:
        for d in sorted(os.listdir(on)):
            y = os.path.join(on, d)
            if d == ad:
                continue
            if os.path.isfile(y) and (d.lower().endswith(tuple(desen))
                                      or d in tablo):
                z.write(y, d)
        for tur in ("dxf", "acinim", "lazer", "pdf", "kaynak"):
            k = IS.alt_klasor(on, tur)
            if not os.path.isdir(k):
                continue
            for d in sorted(os.listdir(k)):
                if d.lower().endswith(tuple(desen)) or d in tablo:
                    z.write(os.path.join(k, d), f"{IS.ALT_KLASOR[tur]}/{d}")
        n = len(z.namelist())
    return yol, n


def _eski_cizimleri_kaldir(on, dxf_kl, simdiki, log=print):
    """Tam üretimden sonra, ARTIK KARŞILIĞI OLMAYAN detay resimlerini
    DXF/ESKI klasörüne taşır (silmez).

    Poz numarası dosya adındadır (P07_...). Model ya da sınıflama değişip
    numaralar kayınca eski P07 dosyası klasörde kalır, pafta listesine
    girip yanlış parçanın resmi gibi basılabilirdi. Yalnız Pi3D'nin
    kendi ürettiği (iş durumunda kayıtlı) dosyalara dokunulur."""
    d = IS.durum_oku(on)
    eski = [a for a, r in d["dxf"].items()
            if a not in simdiki and r.get("kod") != "montaj"
            and os.path.isfile(os.path.join(dxf_kl, a))]
    if not eski:
        return 0
    hedef = os.path.join(dxf_kl, "ESKI")
    os.makedirs(hedef, exist_ok=True)
    for a in eski:
        os.replace(os.path.join(dxf_kl, a), os.path.join(hedef, a))

    def _d(x):
        for a in eski:
            x["dxf"].pop(a, None)
    IS.durum_guncelle(on, _d)
    log(f"  {len(eski)} eski çizim (artık karşılığı yok) DXF/ESKI klasörüne "
        "taşındı")
    return len(eski)


def calistir(step, on, kayit, komp, P, asama=(1, 2, 3), esl=None, agac=None,
             genel=VARSAYILAN_MALZEME, yogunluk=0.0, en_az_hacim=0.0,
             tek=None, en_cok=0, poz_harita=None, tablo_yok=False,
             eksik=False, log=print, ilerleme=None, iptal=None):
    """Üç aşamalı iş akışını yürütür. GUI ve komut satırı aynı yolu kullanır.

    asama    : 1 BOM, 2 detay resmi, 3 montaj resmi
    esl      : kod -> malzeme eşlemesi (parça bazlı)
    genel    : eşlemede olmayanlar için malzeme
    ilerleme : ilerleme(yapilan, toplam) geri çağrısı
    iptal    : True döndürürse iş bırakılır
    eksik    : yalnız EKSİK ya da ESKİMİŞ çizimleri üret. Bir çizim ancak
               aynı model dosyası (içerik özeti) + aynı görünüş/kesit/
               malzeme ayarıyla üretildiği KAYITLIYSA atlanır (pf7_is).

    Çizimler çıktı klasörünün DXF alt klasörüne yazılır; tablolar kökte.
    """
    # Eşleme anahtarları sadeleştirilir: "01.050.000.01" ile "01.050.000.01 "
    # ya da büyük/küçük harf farkı eşleşmeyi bozmasın.
    asama = set(asama)
    esl = {_tr_sade(a): b for a, b in (esl or {}).items() if b}
    os.makedirs(on, exist_ok=True)
    dur = (lambda: bool(iptal and iptal()))
    step_oz = IS.model_kaydet(on, step)
    ayar = IS.cizim_ayari(P)
    dxf_kl = IS.alt_klasor(on, "dxf", olustur=bool({2, 3} & asama))
    onceki = IS.durum_oku(on) if eksik else None
    atlanan = 0

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
                # dikiş ölçülür: tip, boy, kesit, a, kaynak metali (KAYNAK.xlsx)
                try:
                    sat["kaynak_olcu"] = TN.kaynak_olcu(kayit[k["indeks"][0]][1],
                                                        k.get("hacim_mm3"))
                except Exception:
                    pass
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
        # Tabloda üçüncü kutu ölçüsü "yükseklik"tir: C profilde 40 mm'ye
        # "kalınlık" demek yanlıştı (sac 1,5 mm, sac_kalinlik_mm sütunu).
        sat["yukseklik_mm"] = o["kalinlik_mm"]
        sat["delikler"], sat["radusler"] = o["delikler"], o["radusler"]
        sat["dis_capler"] = o["dis_capler"]
        sat["malzeme"] = mal
        sat["malzeme_ad"] = MALZEME[mal][0]
        sat["yogunluk_g_cm3"] = round(yog * 1e6, 3)
        sat["malzeme_kaynak"] = {"data": "data'dan", "secim": "secim",
                                 "genel": "varsayilan"}[kaynak]
        # Türkçe yazım (ondalık virgül, binlik nokta): "1.513,76 x 1.281,19 x 1"
        sat["olcu"] = " x ".join(XL.tr(float(v), 2)
                                 for v in (o["boy_mm"], o["en_mm"], o["kalinlik_mm"]))
        if k.get("profil"):
            sat["profil"] = k["profil"]
        sat["kg_adet"] = o["kutle_kg"]
        sat["toplam_kg"] = round(o["kutle_kg"] * k["adet"], 4)
        if 2 in asama and id(k) in ciz_id:
            dosya = resim_dosyasi(gercek_poz, k["kod"] or k["ad"], k["ad"])
            im = IS.imza(step_oz, ayar, mal, round(yog * 1e9, 6),
                         gercek_poz, k["adet"])
            if eksik and IS.guncel_mi(on, dosya, im, onceki):
                sat["dxf"] = dosya
                atlanan += 1
                log(f"  {dosya}  güncel (aynı model ve ayar) - atlandı")
                satirlar.append(sat)
                if ilerleme:
                    ilerleme(sira, toplam)
                continue
            # Tek parça uzun sürerse (karmaşık yüzey, çok delik) ilerleme
            # çubuğu durur: program takıldı sanılmasın diye hangi parçanın
            # çizildiği günlüğe yazılır.
            import threading
            uzun = threading.Timer(15.0, lambda d=dosya: log(
                f"  {d} çiziliyor... (karmaşık parça, uzun sürüyor - İptal ile "
                "durdurulabilir)"))
            uzun.daemon = True
            uzun.start()
            try:
                P_, o_ = sade_profil(s2, o, k, P)
                dxf_komponent(s2, o_, sat, os.path.join(dxf_kl, dosya), P_)
                IS.cizim_kaydet(on, "dxf", dosya, imza=im, kod=k["kod"],
                                step_ozet=step_oz)
                sat["dxf"] = dosya
                log(f"  {dosya}  {XL.tr(o['boy_mm'])}x{XL.tr(o['en_mm'])}x{XL.tr(o['kalinlik_mm'])} mm, "
                    f"{o['delik_adedi']} delik, {sat['malzeme_ad'].split(' (')[0]}, "
                    f"{XL.tr(o['kutle_kg'])} kg")
            except Exception as ex:
                sat["dxf"] = f"HATA: {ex}"[:80]
                log(f"  {dosya}: HATA {ex}"[:110])
            finally:
                uzun.cancel()
        satirlar.append(sat)
        if ilerleme:
            ilerleme(sira, toplam)

    if (2 in asama and not tek and not en_cok and not tablo_yok
            and not en_az_hacim and not dur()):
        _eski_cizimleri_kaldir(on, dxf_kl, {r["dxf"] for r in satirlar
                                            if r.get("dxf")}, log)
    if (2 in asama and not tek and not en_cok and not tablo_yok and not dur()
            and P.get("kaynak_resmi", False)
            and any(k["sinif"] == "kaynak" for k in komp)):
        # KAYNAK RESİMLERİ: her kaynaklı alt grup için ayrı PDF (KAYNAK/).
        # Kendiliğinden ÇALIŞMAZ: büyük kaynaklı modelde 10-15 dakika sürer
        # ve çizimlerin sonuna eklenince program takılmış gibi görünüyordu.
        # GUI'de ayrı düğme, komut satırında --kaynak-resmi.
        try:
            import pf14_kaynak as KR
            KR.kaynak_resimleri(on, kayit, komp, agac, satirlar, log=log, iptal=dur)
        except Exception as ex:
            log(f"  ! kaynak resimleri üretilemedi: {ex}"[:160])
    bom = [r for r in satirlar if r["sinif"] != "kaynak"]
    if atlanan:
        log(f"  {atlanan} çizim zaten güncel olduğu için yeniden üretilmedi")
    if tablo_yok:                      # örnek resim turu: tabloları bozma
        return {"klasor": on, "dxf_klasor": dxf_kl, "satirlar": satirlar,
                "bom": bom, "montaj": None, "atlanan": atlanan}
    montaj = None
    if 3 in asama and not dur():
        im = IS.imza(step_oz, "montaj", ayar,
                     [(r["poz"], r["kod"], r["adet"]) for r in bom])
        if eksik and IS.guncel_mi(on, "00_MONTAJ.dxf", im, onceki):
            log("  00_MONTAJ.dxf  güncel (aynı model ve ayar) - atlandı")
            atlanan += 1
            g = onceki["dxf"]["00_MONTAJ.dxf"].get("gabari")
            if g:                      # rapordaki gabari satırı kaybolmasın
                montaj = dict(zip(("boy_mm", "en_mm", "yukseklik_mm"), g))
        else:
            log("  montaj resmi hesaplanıyor (büyük montajda sürebilir)...")
            montaj = dxf_montaj([r[1] for r in kayit],
                                os.path.join(dxf_kl, "00_MONTAJ.dxf"),
                                os.path.basename(step), P, bom=bom)
            IS.cizim_kaydet(on, "dxf", "00_MONTAJ.dxf", imza=im, kod="montaj",
                            step_ozet=step_oz,
                            gabari=[montaj["boy_mm"], montaj["en_mm"],
                                    montaj["yukseklik_mm"]])
            log(f"  DXF/00_MONTAJ.dxf   gabari {XL.tr(montaj['boy_mm'])} x "
                f"{XL.tr(montaj['en_mm'])} x {XL.tr(montaj['yukseklik_mm'])} mm")
        if ilerleme:
            ilerleme(toplam, toplam)

    if 1 in asama:
        bom_yaz(on, bom, satirlar)
        y = kontrol_yaz(on, komp)
        if y:
            log(f"  ! {os.path.basename(y)}  ({len(kontrol_listesi(komp))} parçanın "
                "standart tanımı belirsiz - tasarımcıya gönderin)")
        n = profil_listesi_yaz(on, satirlar)
        if n:
            log(f"  PROFIL.xlsx, PROFIL.csv  ({n} profil - kesim listesi ve stok özeti)")
        ko = kaynak_listesi_yaz(on, satirlar)
        if ko:
            log(f"  KAYNAK.xlsx, KAYNAK.csv  ({ko['adet']} dikiş, toplam boy "
                f"{XL.tr(ko['boy_m'], 2)} m, kaynak metali {XL.tr(ko['kg'], 3)} kg)")
        if agac:
            ags = agac_bom(agac, komp, satirlar)
            agac_bom_yaz(on, ags)
            log(f"  BOM_AGAC.csv, BOM_AGAC.md  ({len(ags)} satır, "
                f"{agac_derinlik(agac)} kademe)")
    alan = ["poz", "kod", "ad", "adet", "sinif", "tip", "malzeme_ad", "yogunluk_g_cm3",
            "boy_mm", "en_mm", "yukseklik_mm", "sac_kalinlik_mm", "hacim_mm3",
            "kutle_kg", "toplam_kg", "yuzey_mm2", "delik_adedi", "radus_adedi", "dxf"]
    XL.tablo_yaz(os.path.join(on, "olculer.csv"), alan,
                 XL.sozlukten(alan, satirlar), "olculer")
    json.dump({"step": step, "montaj": montaj, "komponent": satirlar},
              open(os.path.join(on, "olculer.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    rapor_yaz(on, step, kayit, komp, satirlar, montaj)
    log("  BOM.csv/.xlsx, BOM.md, olculer.csv/.xlsx, olculer.json, rapor.md")
    return {"klasor": on, "dxf_klasor": dxf_kl, "satirlar": satirlar,
            "bom": bom, "montaj": montaj, "atlanan": atlanan}


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
--kaynak-resmi verilirse asama 2 her kaynakli alt grubun kaynak resmini de
uretir: KAYNAK/<grup>_kaynak.pdf (yalniz PDF; buyuk modelde uzun surer).
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
    ap.add_argument("--eksik", action="store_true",
                    help="yalnız eksik ya da eskimiş çizimleri üret: aynı model "
                         "ve aynı ayarla üretildiği kayıtlı olanlar atlanır")
    ap.add_argument("--surum", "--version", action="version",
                    version=f"Pi3D v{IS.PI3D_SURUM} ({IS.PI3D_SURUM_TARIHI})")
    ap.add_argument("--kaynak-resmi", action="store_true",
                    help="aşama 2'de kaynak resimlerini de üret (KAYNAK/<grup>_kaynak.pdf; "
                         "büyük kaynaklı modelde uzun sürer)")
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
         "gorunusler": gor, "kesit": bool(a.kesit),
         "kaynak_resmi": bool(a.kaynak_resmi)}
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
    IS.model_kaydet(on, a.step)       # açınım/lazer kaydı model özetini bilsin

    # ---- malzeme: kütle bunun üzerinden hesaplanır, tahmin edilmez
    esl, genel = {}, VARSAYILAN_MALZEME
    if a.malzeme_dosya and not malzeme_sutunu_var(a.malzeme_dosya) \
            and cad_kaynagi_oku(a.malzeme_dosya):
        cad_kaynagiyla_sinifla(komp, cad_kaynagi_oku(a.malzeme_dosya), log=print)
        a.malzeme_dosya = None           # yalnız sınıf (kontrol listesi) dosyası
    if a.malzeme_dosya:
        try:
            esl, bilinmeyen = malzeme_dosya_oku(a.malzeme_dosya)
        except MalzemeDosyaHatasi as ex:
            sys.exit(f"HATA: malzeme dosyası okunamadı: {ex}")
        print(f"malzeme dosyası: {a.malzeme_dosya} ({len(esl)} kayıt eşleşti)")
        cad_kaynagiyla_sinifla(komp, cad_kaynagi_oku(a.malzeme_dosya), log=print)
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
    # EKSTRÜZYON profilin malzemesi verilmediyse SORULUR (varsayılmaz)
    ek = malzemesi_sorulacak(komp, esl) if not a.malzeme and not a.yogunluk else []
    if ek:
        print(f"! {len(ek)} ekstrüzyon profilin malzemesi verilmedi: "
              + ", ".join(k["ad"][:30] for k in ek[:4]))
        if sys.stdin.isatty():
            c = input("  malzemesi ne? (aluminyum / celik / baska ad; bos = celik): ").strip()
            m = malzeme_coz(c) or VARSAYILAN_MALZEME
            for k in ek:
                esl[_tr_sade(k["kod"])] = m
            print(f"  -> {MALZEME[m][0]}")
        else:
            print("  terminal yok: çelik sayıldı - --malzeme-dosya ile ya da arayüzden verin")
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
            acilim_yaz(kayit, komp, P, on, kodlar=kodlar, k_faktor=kf,
                       eksik=a.eksik)
    calistir(a.step, on, kayit, komp, P, asama=asama, esl=esl, agac=agac, genel=genel,
             yogunluk=a.yogunluk, en_az_hacim=a.en_az_hacim, tek=a.tek,
             en_cok=a.en_cok, eksik=a.eksik,
             log=lambda t: print(f"{t}  [{time.time()-t0:.0f}s]"))
    if a.zip:
        z, n = zip_yap(on)
        print(f"  {os.path.basename(z)}  ({n} dosya)")
    print(f"bitti [{time.time()-t0:.0f}s]  ->  {on}/")


STOK_BOY_MM = 6000.0          # profil çubuk boyu (stok özeti için)


def kaynak_ozet_satirlari(satirlar):
    """Dikişler türe ve ölçüye göre gruplanır. Döner: (satırlar, a özeti,
    toplam) - satır: [tür, model biçimi, adet, boy, kesit, a, toplam boy,
    toplam hacim, kaynak metali kg]."""
    grup = {}
    for r in satirlar:
        if r.get("sinif") != "kaynak":
            continue
        o = r.get("kaynak_olcu") or {}
        boy, A, a = o.get("boy_mm"), o.get("kesit_mm2"), o.get("a_mm")
        # kaynak ölçüleri ondalıksız (a 1,77 -> 2; boy 24,7 -> 25)
        k = (kaynak_tipi(r.get("ad")), o.get("tip") or "-",
             XL.tam(boy) if boy else None, XL.tam(A) if A else None,
             XL.tam(a) if a else None)
        g = grup.setdefault(k, {"adet": 0, "hacim": 0.0})
        n = int(r.get("adet") or 1)
        g["adet"] += n
        g["hacim"] += n * (o.get("hacim_mm3") or r.get("hacim_mm3") or 0.0)
    sat = []
    for (tur, tip, boy, A, a), g in sorted(grup.items(), key=lambda t: (t[0][0], t[0][2] or 0)):
        sat.append([tur, tip, g["adet"], boy, A, a,
                    boy * g["adet"] if boy else None, XL.tam(g["hacim"]),
                    round(g["hacim"] * TN.KAYNAK_YOGUNLUK, 4)])
    # a ölçüsüne göre (tam mm): toplam boy ve kaynak metali
    aoz = {}
    for tur, tip, n, boy, A, a, tb, hac, kg in sat:
        s_ = f"a {a}" if a else ("nokta" if "nokta" in tip else "ölçülemedi")
        o = aoz.setdefault(s_, [0, 0.0, 0.0])
        o[0] += n; o[1] += tb or 0.0; o[2] += kg
    aoz = [[k, v[0], round(v[1] / 1000.0, 3), round(v[2], 4)] for k, v in sorted(aoz.items())]
    top = {"adet": sum(r[2] for r in sat), "boy_m": sum((r[6] or 0) for r in sat) / 1000.0,
           "kg": sum(r[8] for r in sat)}
    return sat, aoz, top


KAYNAK_BAS = ["kaynak_turu", "model_bicimi", "adet", "boy_mm", "kesit_mm2", "a_mm",
              "toplam_boy_mm", "toplam_hacim_mm3", "kaynak_metali_kg"]
KAYNAK_OZET_BAS = ["a_sinifi", "adet", "toplam_boy_m", "kaynak_metali_kg"]


def kaynak_listesi_yaz(on, satirlar):
    """KAYNAK.xlsx / KAYNAK.csv: dikiş listesi (tür, model biçimi, boy,
    kesit, a, toplam boy, kaynak metali) ve a ölçüsüne göre özet. Dikiş
    yoksa eski dosyalar silinir. Döner: toplam dict ya da None."""
    sat, aoz, top = kaynak_ozet_satirlari(satirlar)
    if not sat:
        for u in ("KAYNAK.csv", "KAYNAK.xlsx"):
            y = os.path.join(on, u)
            if os.path.isfile(y):
                try:
                    os.remove(y)
                except OSError:
                    pass
        return None
    with open(os.path.join(on, "KAYNAK.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(KAYNAK_BAS)
        for r in sat:
            w.writerow(XL.tr_satir(r))
        w.writerow([])
        w.writerow(["# a ÖLÇÜSÜNE GÖRE ÖZET (kaynak metali = dikiş hacmi x 7,85 g/cm3)"])
        w.writerow(KAYNAK_OZET_BAS)
        for r in aoz:
            w.writerow(XL.tr_satir(r))
    try:
        XL.xlsx_yaz(os.path.join(on, "KAYNAK.xlsx"),
                    [("Dikişler", KAYNAK_BAS, sat), ("a özeti", KAYNAK_OZET_BAS, aoz)])
    except Exception:
        pass
    return top


def profil_listesi_yaz(on, satirlar):
    """PROFIL.xlsx / PROFIL.csv: kesim listesi (parça başına boy) ve
    stok özeti (kesit + malzeme başına toplam boy, 6 m çubuk sayısı).
    Profil yoksa eski dosyalar silinir (başka modelden kalmasın)."""
    pr = [r for r in satirlar if r.get("profil") and r.get("sinif") == "parca"]
    if not pr:
        for u in ("PROFIL.csv", "PROFIL.xlsx"):
            y = os.path.join(on, u)
            if os.path.isfile(y):
                try:
                    os.remove(y)
                except OSError:
                    pass
        return 0
    bas = ["poz", "kod", "ad", "profil", "kesit", "malzeme_ad", "boy_mm", "adet",
           "toplam_boy_m", "kesit_mm2", "kg_m", "kg_adet", "toplam_kg"]
    kes, oz = [], {}
    for r in sorted(pr, key=lambda r: (r["profil"]["tur"], r["profil"]["kesit"],
                                       -r["profil"]["boy"])):
        p = r["profil"]
        yog = r.get("yogunluk_g_cm3") or 7.85
        kg_m = round(p["alan"] * yog * 1e-3, 3)
        top = round(p["boy"] * r["adet"] / 1000.0, 3)
        tur = p["ad"].rsplit(" ", 1)[0]
        kes.append([r["poz"], r["kod"], r["ad"], tur, p["kesit"], r.get("malzeme_ad", ""),
                    p["boy"], r["adet"], top, p["alan"], kg_m, r.get("kg_adet"),
                    r.get("toplam_kg")])
        a = (tur, p["kesit"], r.get("malzeme_ad", ""))
        o = oz.setdefault(a, [0, 0.0, 0.0, kg_m, 0.0])
        o[0] += r["adet"]
        o[1] += p["boy"] * r["adet"]
        o[2] = max(o[2], p["boy"])
        o[4] += r.get("toplam_kg") or 0.0
    obas = ["profil", "kesit", "malzeme_ad", "parca_adedi", "toplam_boy_m",
            "en_uzun_parca_mm", "cubuk_6m_adedi", "kg_m", "toplam_kg"]
    osat = []
    for (tur, kesit, mal), (n, boy, uz, kg_m, kg) in sorted(oz.items()):
        # Kaba ihtiyaç: toplam boy / 6 m, yukarı yuvarlanır. Testere payı ve
        # kesim yerleşimi (fire) hesaba katılmaz - sipariş öncesi kontrol.
        cubuk = math.ceil(boy / STOK_BOY_MM - 1e-9) if uz <= STOK_BOY_MM else None
        osat.append([tur, kesit, mal, n, round(boy / 1000.0, 3), uz, cubuk, kg_m,
                     round(kg, 3)])
    with open(os.path.join(on, "PROFIL.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(bas)
        for s in kes:
            w.writerow(XL.tr_satir(s))
        w.writerow([])
        w.writerow(["# STOK ÖZETİ (6 m çubuk, fire hariç)"])
        w.writerow(obas)
        for s in osat:
            w.writerow(XL.tr_satir(s))
    try:
        XL.xlsx_yaz(os.path.join(on, "PROFIL.xlsx"),
                     [("Kesim listesi", bas, kes), ("Stok özeti", obas, osat)])
    except Exception:
        pass
    return len(pr)


def bom_yaz(on, bom, satirlar):
    """AŞAMA 1 çıktısı: parça listesi (BOM) — CSV + okunabilir tablo."""
    alan = ["poz", "kod", "ad", "adet", "sinif", "tip", "malzeme_ad", "olcu",
            "kg_adet", "toplam_kg", "dxf"]
    XL.tablo_yaz(os.path.join(on, "BOM.csv"), alan, XL.sozlukten(alan, bom), "BOM")
    agir = sum((r.get("toplam_kg") or 0.0) for r in bom)
    L = ["# BOM – parça listesi\n",
         f"{len(bom)} poz, toplam kütle {XL.tr(agir, 3, sade=False)} kg\n",
         "| poz | kod | tanım | adet | malzeme | ölçü BxExK | kg/adet | toplam kg | dxf |",
         "|-----|-----|-------|------|---------|------------|---------|-----------|-----|"]
    for r in bom:
        ka = f"{XL.tr(r['kg_adet'], 3, sade=False)}" if r.get("kg_adet") else "-"
        tk = f"{XL.tr(r['toplam_kg'], 3, sade=False)}" if r.get("toplam_kg") else "-"
        L.append(f"| {r['poz']} | {r['kod'][:28]} | {r['ad'][:40]} | {r['adet']} | "
                 f"{r.get('malzeme_ad') or '-'} | {r.get('olcu') or '-'} | {ka} | {tk} | "
                 f"{r['dxf'] or '-'} |")
    kyn = [r for r in satirlar if r["sinif"] == "kaynak"]
    if kyn:
        oz = kaynak_ozeti(kyn)
        L.append(f"\nKaynak dikişleri BOM'a girmez (parça değildir): "
                 f"{len(oz)} tür, toplam {sum(t[1] for t in oz)} adet.")
    open(os.path.join(on, "BOM.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def rapor_yaz(on, step, kayit, komp, satirlar, montaj):  # noqa: C901
    L = [f"# {os.path.basename(step)} – ölçü raporu\n",
         f"_Pi3D v{IS.PI3D_SURUM} ({IS.PI3D_SURUM_TARIHI})_\n",
         f"{len(kayit)} katı, "
         f"{sum(1 for k in komp if k['sinif'] != 'kaynak')} komponent"
         + (f" + {sum(1 for k in komp if k['sinif'] == 'kaynak')} kaynak "
            "dikişi (parça değil)" if any(k["sinif"] == "kaynak" for k in komp)
            else "") + ".\n"]
    if montaj:
        L.append(f"**Montaj gabarisi:** {XL.tr(montaj['boy_mm'])} x {XL.tr(montaj['en_mm'])} x "
                 f"{XL.tr(montaj['yukseklik_mm'])} mm (boy x en x yükseklik)\n")
    L.append("## Çizilen parçalar\n")
    L.append("| poz | kod | adet | malzeme | boy | en | yükseklik | sac kalınlığı | kg | delik | radüs | dxf |")
    L.append("|-----|-----|------|---------|-----|----|-----------|---------------|----|-------|-------|-----|")
    for r in satirlar:
        if r["sinif"] != "parca":
            continue
        L.append(f"| {r['poz']} | {r['kod'][:26]} | {r['adet']} | "
                 f"{(r.get('malzeme_ad') or '-').split(' (')[0]} | {XL.tr(r.get('boy_mm'))} | "
                 f"{XL.tr(r.get('en_mm'))} | {XL.tr(r.get('kalinlik_mm'))} | {XL.tr(r.get('sac_kalinlik_mm')) or '-'} | "
                 f"{XL.tr(r.get('kutle_kg'))} | {r.get('delik_adedi')} | {r.get('radus_adedi')} | "
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
        oz = kaynak_ozeti(kyn)
        L.append(f"\n## Kaynak dikişleri\n\n{len(oz)} tür, toplam "
                 f"{sum(t[1] for t in oz)} adet. Parça değildir: BOM'a "
                 "girmez, poz almaz, çizimi üretilmez; montaj resminde "
                 "görünür.\n")
        sat, aoz, top = kaynak_ozet_satirlari(kyn)
        L.append(f"Toplam dikiş boyu **{XL.tr(top['boy_m'], 2)} m**, kaynak metali "
                 f"**{XL.tr(top['kg'], 3)} kg** (dikiş katılarının hacminden, 7,85 "
                 "g/cm³). Kaynak yöntemi (gazaltı, TIG...) geometriden anlaşılmaz; "
                 "tel sarfiyatı = kaynak metali / yöntemin verimi. Ayrıntı: "
                 "`KAYNAK.xlsx`.\n")
        L.append("| kaynak türü | model biçimi | adet | boy mm | a mm | toplam boy mm | kg |")
        L.append("|-------------|--------------|------|--------|------|---------------|----|")
        for tur, tip, n, boy, A, a, tb, hac, kg in sat:
            L.append(f"| {tur} | {tip} | {n} | {XL.tr(boy, 1) if boy else '-'} | "
                     f"{XL.tr(a, 2) if a else '-'} | {XL.tr(tb, 1) if tb else '-'} | "
                     f"{XL.tr(kg, 4)} |")
        L.append("\n| a sınıfı | adet | toplam boy m | kaynak metali kg |")
        L.append("|----------|------|--------------|------------------|")
        for k_, n, bm, kg in aoz:
            L.append(f"| {k_} | {n} | {XL.tr(bm, 3)} | {XL.tr(kg, 4)} |")
    geo = [k for k in komp if k.get("geometri")]
    oner = [k for k in komp if k.get("oneri")]
    adsiz = [k for k in komp if k.get("isimsiz") and k["sinif"] == "parca"]
    if geo or oner or adsiz:
        L.append("\n## Geometriden tanıma\n")
        L.append("Adı bilgi taşımayan katılar (COMPOUND, SOLID ...) yüzlerine "
                 "bakılarak sınıflandı. Adı olan parçada ad geçerlidir; "
                 "geometri yalnız öneridir.\n")
        if geo:
            L.append("| ad | adet | sınıf | gerekçe |")
            L.append("|----|------|-------|---------|")
            for k in geo:
                L.append(f"| {k['ad'][:30]} | {k['adet']} | {k['sinif']} | "
                         f"{k['geometri']} |")
        if oner:
            L.append("\n**Öneri (adı olduğu için uygulanmadı):**\n")
            for k in oner:
                L.append(f"- {k['ad'][:50]}: {k['oneri'][2]}")
        if adsiz:
            L.append(f"\n**Tanınamayan adsız katı: {len(adsiz)}** — parça "
                     "sayıldı; arayüzün 2. sekmesinde elle sınıflayın.")
    ogr = [k for k in komp if k.get("ogrenildi")]
    cad = [k for k in komp if k.get("cad_kaynak")]
    if ogr or cad:
        L.append("\n## Öğrenilen ve CAD'den gelen sınıflar\n")
        if cad:
            L.append(f"CAD'in Made/Bought bilgisi {len(cad)} komponentte kullanıldı "
                     f"({sum(k['sinif'] == 'standart' for k in cad)} satın alınan).\n")
        for k in ogr:
            L.append(f"- {k['ad'][:50]}: {k['sinif']} — daha önce elle düzeltilen "
                     "bir parçaya biçimce benziyor")
    kl = kontrol_listesi(komp)
    if kl:
        kk = IS.durum_oku(on).get("standart_kontrol") or {}
        L.append("\n## Standart tanımı kontrolü\n")
        L.append(f"**{len(kl)} parçanın** standart (satın alınan) mı üretim mi olduğu "
                 "modelden kesin anlaşılamadı; liste `STANDART_KONTROL.xlsx`. "
                 + ("Kullanıcı listeyi **olduğu gibi kabul etti** "
                    f"({kk.get('tarih', '')})." if kk.get("kabul") else
                    "Liste henüz onaylanmadı.") + "\n")
        L.append("| durum | ad | adet | öneri | gerekçe |")
        L.append("|-------|----|------|-------|---------|")
        for r in kl:
            L.append(f"| {r[0]} | {str(r[2])[:30]} | {r[3]} | {r[6]} | {r[7]} |")
    prf = [k for k in komp if k.get("profil")]
    if prf:
        L.append("\n## Profiller\n")
        L.append("Sabit kesitli parçalar (boyuna 9 kesit alındı). Kesim listesi "
                 "ve 6 m çubuk özeti: `PROFIL.xlsx`.\n")
        L.append("| ad | adet | profil | boy mm | gerekçe |")
        L.append("|----|------|--------|--------|---------|")
        for k in prf:
            p_ = k["profil"]
            L.append(f"| {k['ad'][:30]} | {k['adet']} | {p_['ad']} | "
                     f"{XL.tr(p_['boy'])} | {p_['gerekce'].split(': ', 1)[-1]} |")
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
                L.append(f"| Ø{XL.tr(d['cap_mm'])} | {d['adet']} | {d['eksen']} | {XL.tr(d['derinlik_mm'])} |")
        if r.get("radusler"):
            L.append("")
            L.append("| radüs | adet | eksen | uzunluk |")
            L.append("|-------|------|-------|---------|")
            for d in r["radusler"][:20]:
                L.append(f"| R{XL.tr(d['yaricap_mm'])} | {d['adet']} | {d['eksen']} | {XL.tr(d['uzunluk_mm'])} |")
    open(os.path.join(on, "rapor.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
