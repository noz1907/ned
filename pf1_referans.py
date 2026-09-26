"""
Pi3D Maker – ADIM 1 : REFERANS BELİRLEME
=============================================
Amaç: STEP dosyasından, montajlı parçanın iç parçalarına EN KOLAY ERİŞİM
veren XYZ yönlendirmesini bulmak ve 3 konumlandırma noktası önermek.

    python pf1_referans.py parca.stp --liste            # parçaları/grupları göster
    python pf1_referans.py parca.stp --grup KG01        # grup seç ve analiz et
    python pf1_referans.py parca.stp --parca 3          # tek katı seç
    python pf1_referans.py parca.stp --grup KG01 --yon -Y   # (a) onay yoksa yönü zorla

Çıktı: ekranda karşılaştırma tablosu + referans.json (onay için)

Bu modül KARAR VERMEZ, ÖNERİR. Onay kullanıcıdadır.
"""
from __future__ import annotations
import argparse, json, math, os, re, sys
from collections import defaultdict, Counter

from OCP.STEPControl import STEPControl_Reader
from OCP.IGESControl import IGESControl_Reader
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.TCollection import TCollection_ExtendedString
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Shape
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_REVERSED, TopAbs_IN, TopAbs_ON
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.gp import gp_Pnt, gp_Dir, gp_Vec
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform, BRepBuilderAPI_MakeVertex
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepClass3d import BRepClass3d_SolidClassifier

RHO = 7.85e-6
YONLER = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0),
          "-Y": (0, -1, 0), "+Z": (0, 0, 1), "-Z": (0, 0, -1)}


# ========================================================== STEP okuma
def _ad(lab):
    n = TDataStd_Name()
    if lab.FindAttribute(TDataStd_Name.GetID_s(), n):
        return n.Get().ToExtString()
    return None


class MalzemeAdi(str):
    """STEP'te okunan malzeme adı; varsa YOĞUNLUĞU da taşır (.yogunluk,
    dosyada yazdığı birimle - g/cm3 ya da kg/m3, çağıran çözer).

    str'dir: adı kullanan her yer (desenle tanıma, rapor, JSON) aynen
    çalışır; yoğunluğu isteyen getattr(ad, "yogunluk", None) ile alır."""
    yogunluk = None


def _malzeme_tablosu(mt):
    """Belgedeki bütün malzemeler: {yoğunluk: [ad, ...]}.

    Malzeme etiketlerindeki XCAFDoc_Material özniteliğinden okunur.
    (GetMaterial_s'in çıkış parametreleri Python bağlamasında DOLMUYOR:
    True döner ama ad boş kalır - ölçtük.)"""
    out = {}
    if mt is None:
        return out
    try:
        from OCP.XCAFDoc import XCAFDoc_Material
        seq = TDF_LabelSequence()
        mt.GetMaterialLabels(seq)
        for i in range(1, seq.Length() + 1):
            a = XCAFDoc_Material()
            if not seq.Value(i).FindAttribute(XCAFDoc_Material.GetID_s(), a):
                continue
            ad = (a.GetName().ToCString() if a.GetName() else "").strip()
            y = float(a.GetDensity())
            if y > 0:
                lst = out.setdefault(round(y, 6), [])
                if ad and ad not in lst:
                    lst.append(ad)
    except Exception:
        return {}
    return out


def _malzeme(mt, lab, tablo=None):
    """XCAF'te tanımlıysa parçanın malzemesi (MalzemeAdi), yoksa None.

    DÜZELTME: eski kod GetMaterial_s'e parçanın etiketini veriyordu (o
    MALZEME etiketini ister) ve her zaman "yok" dönüyordu - STEP'e
    yazılmış malzeme hiç okunmamıştı. Ölçtük: 'AISI 304', 7,93 yazılı
    STEP'ten None çıkıyordu.

    Parçadan malzemeye bağ XCAF'te bir TreeNode'dur, ama o özniteliği bu
    Python bağlamasında aramak ÇÖKERTİYOR (segmentation fault; örnek
    montajın 50 etiketinde ölçüldü). Güvenli yol: parçanın yoğunluğu
    GetDensityForShape_s ile alınır, ad o yoğunluktaki malzemeden gelir.
    Aynı yoğunlukta birden çok malzeme varsa adlar birlikte verilir
    ("Steel / S235") - hangisi olduğu tahmin edilmez; kütle zaten
    yoğunluktan hesaplanır.

    Sınır: yoğunluğu yazılmamış (yalnız adı olan) malzeme bağlanamaz."""
    if mt is None:
        return None
    try:
        from OCP.XCAFDoc import XCAFDoc_MaterialTool
        y = float(XCAFDoc_MaterialTool.GetDensityForShape_s(lab))
    except Exception:
        return None
    if not y > 0:
        return None
    if tablo is None:
        tablo = _malzeme_tablosu(mt)
    # GetDensityForShape yoğunluğu MODEL BİRİMİNE çevirir: 7,93 g/cm3
    # yazılmış malzeme mm'lik belgede 0,00793 döner - ölçtük. Çevrim bir
    # birim dönüşümü, yani 10'un tam kuvvetidir; tablodaki (yazıldığı
    # birimdeki) yoğunluklardan oranı 10'un kuvveti olan TEK malzeme
    # parçanınkidir. Birden çok ya da hiç yoksa bağ kurulmaz.
    aday = []
    for d, adlar in tablo.items():
        if d <= 0:
            continue
        r = y / d
        us = round(math.log10(r))
        if abs(r / (10.0 ** us) - 1.0) < 1e-6:
            aday.append((d, adlar))
    if len(aday) != 1:
        return None
    d, adlar = aday[0]
    m = MalzemeAdi(" / ".join(adlar))
    m.yogunluk = d                     # dosyada yazdığı birimle
    return m


# ---------------------------------------------------------- biçim tanıma
# Doğrudan okunabilen biçimler (katı/B-Rep taşırlar).
BICIM = {".stp": "STEP", ".step": "STEP", ".stpz": "STEP",
         ".igs": "IGES", ".iges": "IGES",
         ".brep": "BREP", ".brp": "BREP"}

# Okunamayan, CAD'den dışa aktarım isteyen kapalı biçimler.
# OpenCascade bunları açamaz; ticari çevirici ya da CAD'in kendi
# "Save As / Export -> STEP" komutu gerekir.
CEVIR_GEREK = {
    ".catpart": ("CATIA V5 parça", "CATIA: File > Save As > STEP (.stp)"),
    ".catproduct": ("CATIA V5 montaj",
                    "CATIA: File > Save As > STEP (.stp). Montajın tamamı "
                    "tek STEP olur, parça ağacı ve adlar korunur."),
    ".cgr": ("CATIA görsel gösterim", "CATIA: özgün CATPart'tan STEP alın"),
    ".sldprt": ("SolidWorks parça", "SolidWorks: Dosya > Farklı Kaydet > STEP"),
    ".sldasm": ("SolidWorks montaj", "SolidWorks: Dosya > Farklı Kaydet > STEP"),
    ".prt": ("NX / Creo parça", "NX: File > Export > STEP214"),
    ".asm": ("Creo montaj", "Creo: File > Save As > STEP"),
    ".ipt": ("Inventor parça", "Inventor: Farklı Kaydet > STEP"),
    ".iam": ("Inventor montaj", "Inventor: Farklı Kaydet > STEP"),
    ".x_t": ("Parasolid metin", "CAD'den STEP olarak aktarın"),
    ".x_b": ("Parasolid ikili", "CAD'den STEP olarak aktarın"),
    ".sat": ("ACIS", "CAD'den STEP olarak aktarın"),
    ".3dm": ("Rhino", "Rhino: Dosya > Farklı Kaydet > STEP"),
    ".dwg": ("AutoCAD çizimi", "3B katı için STEP olarak aktarın"),
}

# Okunabilir ama YALNIZ üçgen ağ (mesh) taşıyan biçimler: delik, radüs,
# düzlem gibi bilgiler yoktur, bu program bunları ölçemez.
AG_BICIM = {".stl": "STL", ".obj": "OBJ", ".ply": "PLY",
            ".gltf": "glTF", ".glb": "glTF", ".wrl": "VRML", ".3mf": "3MF"}


class OkunamazBicim(Exception):
    """Dosya biçimi bu programla okunamıyor; mesaj kullanıcıya gösterilir."""


def bicim_tani(yol):
    """Dosya uzantısına göre biçim adı. Okunamayan biçimde açıklamalı hata."""
    u = os.path.splitext(yol)[1].lower()
    if u in BICIM:
        return BICIM[u]
    if u in CEVIR_GEREK:
        ad, nasil = CEVIR_GEREK[u]
        raise OkunamazBicim(
            f"{u} dosyasi ({ad}) dogrudan okunamiyor.\n\n"
            f"Bu bicim uretici firmaya ait kapali bir bicimdir; acik kaynak\n"
            f"OpenCascade cekirdegi onu acamaz.\n\n"
            f"Cozum: parcayi kendi CAD programinizdan STEP olarak kaydedin.\n"
            f"  {nasil}\n\n"
            f"STEP (.stp / .step) disinda IGES (.igs) ve BREP de okunur.")
    if u in AG_BICIM:
        raise OkunamazBicim(
            f"{u} dosyasi ({AG_BICIM[u]}) yalnizca ucgen ag (mesh) tasir.\n\n"
            f"Icinde duzlem, silindir, delik, radus bilgisi yoktur; bu program\n"
            f"olcu ve delik tablosu cikaramaz.\n\n"
            f"Cozum: parcayi CAD'den STEP (.stp) olarak kaydedin.")
    raise OkunamazBicim(
        f"'{u}' uzantisi taninmiyor.\n\n"
        f"Okunabilen bicimler: STEP (.stp, .step), IGES (.igs, .iges), "
        f"BREP (.brep).")


def _katilari_topla(sh, ad, malzeme, out, mal=None):
    """Bir şekilden katıları toplar; katı yoksa yüzeyleri dikip katı yapar."""
    ex = TopExp_Explorer(sh, TopAbs_SOLID)
    n = 0
    while ex.More():
        k = TopoDS.Solid_s(ex.Current())
        out.append((ad, k, mal) if malzeme else (ad, k))
        n += 1
        ex.Next()
    if n:
        return n
    # IGES çoğu zaman yalnız yüzey taşır: yüzeyleri dikip kapalı kabuktan
    # katı elde etmeye çalış.
    try:
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
        from OCP.TopAbs import TopAbs_SHELL
        dik = BRepBuilderAPI_Sewing(1e-3)
        dik.Add(sh)
        dik.Perform()
        dikili = dik.SewedShape()
        ex = TopExp_Explorer(dikili, TopAbs_SHELL)
        while ex.More():
            mk = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(ex.Current()))
            if mk.IsDone():
                out.append((ad, mk.Solid(), mal) if malzeme else (ad, mk.Solid()))
                n += 1
            ex.Next()
    except Exception:
        pass
    return n


def iges_oku(yol, malzeme=False):
    """IGES okur. Katı yoksa yüzeyleri dikip katıya çevirmeyi dener."""
    rd = IGESControl_Reader()
    if rd.ReadFile(yol) != IFSelect_RetDone:
        raise OkunamazBicim(f"IGES dosyasi okunamadi: {yol}")
    rd.TransferRoots()
    out = []
    ad = os.path.splitext(os.path.basename(yol))[0]
    if not _katilari_topla(rd.OneShape(), ad, malzeme, out):
        raise OkunamazBicim(
            "IGES dosyasinda kati (solid) bulunamadi; yuzeyler de kapali bir\n"
            "hacim olusturmuyor. Bu dosyadan olcu cikarilamaz.\n\n"
            "Cozum: CAD'den STEP (.stp) olarak kaydedin - STEP kati tasir.")
    return out


def brep_oku(yol, malzeme=False):
    """OpenCascade'in kendi BREP biçimi."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Shape
    from OCP.BRepTools import BRepTools
    sh = TopoDS_Shape()
    if not BRepTools.Read_s(sh, yol, BRep_Builder()):
        raise OkunamazBicim(f"BREP dosyasi okunamadi: {yol}")
    out = []
    ad = os.path.splitext(os.path.basename(yol))[0]
    if not _katilari_topla(sh, ad, malzeme, out):
        raise OkunamazBicim("BREP dosyasinda kati bulunamadi.")
    return out


def oku(yol, malzeme=False, agac=None):
    """Dosyayı biçimine göre okur: STEP, IGES ya da BREP.

    Geri dönüş: (ad, katı) ikilileri; malzeme=True ise (ad, katı, malzeme).
    Okunamayan biçimde, ne yapılacağını anlatan OkunamazBicim yükseltir."""
    b = bicim_tani(yol)
    if b == "IGES":
        return iges_oku(yol, malzeme)
    if b == "BREP":
        return brep_oku(yol, malzeme)
    return step_oku(yol, malzeme, agac)


def _dugum(ad, kod=""):
    return {"ad": ad, "kod": kod, "adet": 1, "alt": [], "katilar": [],
            "montaj": False}


def step_oku(yol, malzeme=False, agac=None):
    """XCAF ile okur: montaj ağacı + gerçek parça adları.

    malzeme=True verilirse her katı (ad, katı, malzeme) üçlüsü olarak döner;
    malzeme STEP'te tanımlı değilse None'dır. Olmazsa düz okuyucuya düşer.

    agac bir listeyse, montaj ağacı oraya konur: iç içe sözlükler
    {"ad", "kod", "adet", "montaj", "alt": [...], "katilar": [kayıt indeksi]}.
    Aynı alt montajın kopyaları tek düğümde toplanır, adet'i artar."""
    try:
        app = XCAFApp_Application.GetApplication_s()
        doc = TDocStd_Document(TCollection_ExtendedString("d"))
        app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)
        rd = STEPCAFControl_Reader()
        rd.SetNameMode(True)
        if rd.ReadFile(yol) != IFSelect_RetDone:
            raise RuntimeError
        rd.Transfer(doc)
        st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
        try:
            from OCP.XCAFDoc import XCAFDoc_MaterialTool
            # DocumentTool'un malzeme aracı; Set_s(doc.Main()) YANLIŞ
            # etikette boş bir araç açıyordu (malzeme listesi hep boş).
            mt = (XCAFDoc_DocumentTool.MaterialTool_s(doc.Main())
                  if malzeme else None)
        except Exception:
            mt = None
        mtab = _malzeme_tablosu(mt)       # bir kez: {yoğunluk: [ad]}
        out = []

        def _anahtar(lab):
            """Aynı parçanın/alt montajın kopyalarını eşleştiren kimlik."""
            try:
                return lab.EntryDumpToString()
            except Exception:
                return _ad(lab) or "?"

        def gez(lab, loc, ust, say=True):
            """Ağacı gezer.

            say=False: bu dal, daha önce sayılmış bir alt montajın
            KOPYASIDIR. Katıları yine toplanır (montaj resmi için her
            kopyanın kendi konumu gerekir) ama ağaçta yeni düğüm açılmaz
            ve çocukların adedi bir daha artırılmaz — çok kademeli BOM'da
            adet HER ZAMAN bir üst montaj başınadır."""
            ad = _ad(lab) or "?"
            an = _anahtar(lab)
            bu = None
            if ust is not None:
                for d in ust["alt"]:
                    if d.get("_an") == an:
                        bu = d
                        break
                if bu is None:
                    bu = _dugum(ad)
                    bu["_an"] = an
                    ust["alt"].append(bu)
                elif say:
                    bu["adet"] += 1
                    say = False        # bundan sonrası kopya dalı
            if st.IsAssembly_s(lab):
                if bu is not None:
                    bu["montaj"] = True
                ch = TDF_LabelSequence(); st.GetComponents_s(lab, ch)
                for i in range(1, ch.Length() + 1):
                    c = ch.Value(i)
                    ref = TDF_Label()
                    cl = st.GetLocation_s(c)
                    if st.GetReferredShape_s(c, ref):
                        gez(ref, loc.Multiplied(cl), bu, say)
                    else:
                        gez(c, loc.Multiplied(cl), bu, say)
            else:
                sh = st.GetShape_s(lab)
                if sh.IsNull():
                    return
                if not loc.IsIdentity():
                    sh = BRepBuilderAPI_Transform(sh, loc.Transformation(), True).Shape()
                mal = _malzeme(mt, lab, mtab) if malzeme else None
                ex = TopExp_Explorer(sh, TopAbs_SOLID)
                while ex.More():
                    k = TopoDS.Solid_s(ex.Current())
                    out.append((ad, k, mal) if malzeme else (ad, k))
                    if bu is not None and say:
                        bu["katilar"].append(len(out) - 1)
                    ex.Next()

        kok = _dugum(os.path.splitext(os.path.basename(yol))[0])
        kok["montaj"] = True
        free = TDF_LabelSequence(); st.GetFreeShapes(free)
        for i in range(1, free.Length() + 1):
            gez(free.Value(i), TopLoc_Location(), kok)
        if out:
            if agac is not None:
                # Tek serbest kök varsa onu ana ürün yap, sahte kökü atla.
                agac.append(kok["alt"][0] if len(kok["alt"]) == 1 else kok)
            return out
    except Exception:
        pass
    rd = STEPControl_Reader()
    if rd.ReadFile(yol) != IFSelect_RetDone:
        sys.exit(f"HATA: STEP okunamadı: {yol}")
    rd.TransferRoots()
    out, ex = [], TopExp_Explorer(rd.OneShape(), TopAbs_SOLID)
    i = 0
    while ex.More():
        i += 1
        k = TopoDS.Solid_s(ex.Current())
        out.append((f"SOLID_{i:03d}", k, None) if malzeme else (f"SOLID_{i:03d}", k))
        ex.Next()
    return out


# ========================================================== temel ölçüler
def kutu(sh):
    b = Bnd_Box(); BRepBndLib.Add_s(sh, b)
    return b.Get()


def hacim(sh):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g); return g.Mass()


def yuzey_bilgi(sd):
    """Katının düz yüzeyleri: (alan, normal, merkez) – normaller dışa bakar."""
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sd, TopAbs_FACE, m)
    duz, sil = [], []
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(f, g)
        c = g.CentreOfMass()
        if ad.GetType() == GeomAbs_Plane:
            n = ad.Plane().Axis().Direction()
            if f.Orientation() == TopAbs_REVERSED:
                n = gp_Dir(-n.X(), -n.Y(), -n.Z())
            duz.append({"i": i, "f": f, "alan": g.Mass(),
                        "n": (n.X(), n.Y(), n.Z()),
                        "c": (c.X(), c.Y(), c.Z())})
        elif ad.GetType() == GeomAbs_Cylinder:
            cyl = ad.Cylinder()
            d = cyl.Position().Direction()
            sil.append({"i": i, "f": f, "r": cyl.Radius(), "alan": g.Mass(),
                        "eksen": (d.X(), d.Y(), d.Z()),
                        "c": (c.X(), c.Y(), c.Z()),
                        "ic": f.Orientation() == TopAbs_REVERSED})
    duz.sort(key=lambda x: -x["alan"])
    return duz, sil


# ========================================================== temas / gruplama
def temas_grupla(kayit, min_alan=5.0):
    """Birbirine değen katıları grupla (patlatılmış montajı birleştirir)."""
    kova = defaultdict(list)
    for pi, (ad, sd) in enumerate(kayit):
        duz, _ = yuzey_bilgi(sd)
        for d in duz:
            nx, ny, nz = d["n"]
            k = (round(abs(nx), 3), round(abs(ny), 3), round(abs(nz), 3))
            sgn = 1
            for v in (nx, ny, nz):
                if abs(v) > 1e-3:
                    sgn = 1 if v > 0 else -1
                    break
            cn = (round(nx * sgn, 3), round(ny * sgn, 3), round(nz * sgn, 3))
            off = round((d["c"][0] * cn[0] + d["c"][1] * cn[1] + d["c"][2] * cn[2]) / 0.05) * 0.05
            kova[(cn, round(off, 2))].append((pi, d))

    n = len(kayit)
    ebeveyn = list(range(n))
    def kok(x):
        while ebeveyn[x] != x:
            ebeveyn[x] = ebeveyn[ebeveyn[x]]; x = ebeveyn[x]
        return x
    temaslar = []
    for (cn, off), lst in kova.items():
        if len(lst) < 2:
            continue
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                pa, da = lst[a]; pb, db = lst[b]
                if pa == pb:
                    continue
                if sum(x * y for x, y in zip(da["n"], db["n"])) > -0.999:
                    continue
                try:
                    com = BRepAlgoAPI_Common(da["f"], db["f"]); com.Build()
                    if not com.IsDone():
                        continue
                    g = GProp_GProps(); BRepGProp.SurfaceProperties_s(com.Shape(), g)
                    alan = g.Mass()
                except Exception:
                    continue
                if alan < min_alan:
                    continue
                bb = Bnd_Box(); BRepBndLib.Add_s(com.Shape(), bb)
                c = g.CentreOfMass()
                temaslar.append({"a": pa, "b": pb, "alan": alan, "normal": cn,
                                 "merkez": (c.X(), c.Y(), c.Z()), "kutu": bb.Get()})
                ra, rb = kok(pa), kok(pb)
                if ra != rb:
                    ebeveyn[ra] = rb
    gr = defaultdict(list)
    for i in range(n):
        gr[kok(i)].append(i)
    gruplar = sorted(gr.values(), key=lambda v: -len(v))
    return gruplar, temaslar, kok


# ========================================================== erişim puanı
class Erisim:
    """Bir noktadan verilen yönde dışarı çıkılabiliyor mu (parçaya girmeden)?"""
    def __init__(self, solids):
        self.cls = [BRepClass3d_SolidClassifier(s) for s in solids]

    def acik(self, p, u, L):
        adim = [2, 5, 10, 20, 40, 80, 150, 300, L * 0.4, L * 0.8]
        for t in adim:
            if t > L:
                break
            q = gp_Pnt(p[0] + u[0] * t, p[1] + u[1] * t, p[2] + u[2] * t)
            for c in self.cls:
                c.Perform(q, 1e-7)
                if c.State() in (TopAbs_IN, TopAbs_ON):
                    return False
        return True


def yon_puanla(kayit, uyeler, temaslar):
    """6 ana yön için: iç birleşimlere erişim, oturma alanı, yükseklik."""
    solids = [kayit[i][1] for i in uyeler]
    er = Erisim(solids)
    xm, ym, zm, xM, yM, zM = kutu_birlesik(solids)
    L = math.dist((xm, ym, zm), (xM, yM, zM))
    ic = [t for t in temaslar if t["a"] in uyeler and t["b"] in uyeler]
    toplam_alan = sum(t["alan"] for t in ic) or 1.0

    duz_hepsi = []
    for s in solids:
        d, _ = yuzey_bilgi(s)
        duz_hepsi += d

    sonuc = []
    for ad, u in YONLER.items():
        # 1) iç birleşimlere erişim (tabanca / tornavida yukarıdan gelir)
        acik = sum(t["alan"] for t in ic if er.acik(t["merkez"], u, L))
        # 2) oturma: -u yönüne bakan dış düz yüzeylerin alanı
        alt = (-u[0], -u[1], -u[2])
        otur = 0.0
        for d in duz_hepsi:
            if sum(x * y for x, y in zip(d["n"], alt)) < 0.98:
                continue
            if er.acik(d["c"], alt, L):
                otur += d["alan"]
        # 3) yükseklik (alçak duruş daha kararlı)
        h = {"X": xM - xm, "Y": yM - ym, "Z": zM - zm}[ad[1]]
        sonuc.append({"yon": ad, "u": u,
                      "erisim_orani": acik / toplam_alan,
                      "erisim_mm2": round(acik, 1),
                      "oturma_mm2": round(otur, 1),
                      "yukseklik_mm": round(h, 1)})
    en_otur = max(s["oturma_mm2"] for s in sonuc) or 1
    en_h = max(s["yukseklik_mm"] for s in sonuc) or 1
    for s in sonuc:
        s["puan"] = round(0.60 * s["erisim_orani"]
                          + 0.30 * (s["oturma_mm2"] / en_otur)
                          + 0.10 * (1 - s["yukseklik_mm"] / en_h), 4)
    sonuc.sort(key=lambda s: -s["puan"])
    return sonuc, ic


def kutu_birlesik(solids):
    b = Bnd_Box()
    for s in solids:
        BRepBndLib.Add_s(s, b)
    return b.Get()


# ========================================================== 3 nokta
def nokta_yuzeyde(f, p, tol=0.3):
    v = BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
    d = BRepExtrema_DistShapeShape(v, f)
    return d.IsDone() and d.Value() < tol


def uc_nokta(kayit, uyeler, u, er, ic_temaslar, pay=15.0):
    """Seçilen yöne göre ALT yüzeydeki en geniş üçgen (datum A üstünde 3 nokta)."""
    alt = (-u[0], -u[1], -u[2])
    solids = [kayit[i][1] for i in uyeler]
    xm, ym, zm, xM, yM, zM = kutu_birlesik(solids)
    L = math.dist((xm, ym, zm), (xM, yM, zM))
    adaylar = []
    for si, s in enumerate(solids):
        duz, _ = yuzey_bilgi(s)
        for d in duz:
            if sum(x * y for x, y in zip(d["n"], alt)) < 0.98:
                continue
            if not er.acik(d["c"], alt, L):
                continue
            adaylar.append((d, uyeler[si]))
    if not adaylar:
        return None, []
    adaylar.sort(key=lambda x: -x[0]["alan"])
    taban = adaylar[0][0]

    # eksen indeksleri: k = yön ekseni, i/j = düzlem içi
    k = max(range(3), key=lambda t: abs(u[t]))
    ij = [t for t in range(3) if t != k]
    fb = kutu(taban["f"])
    mn = [fb[0], fb[1], fb[2]]; mx = [fb[3], fb[4], fb[5]]
    ci = (mn[ij[0]] + mx[ij[0]]) / 2
    cj = (mn[ij[1]] + mx[ij[1]]) / 2
    wi = mx[ij[0]] - mn[ij[0]]; wj = mx[ij[1]] - mn[ij[1]]
    sabit = taban["c"][k]

    def pt(di, dj):
        p = [0, 0, 0]; p[k] = sabit; p[ij[0]] = ci + di; p[ij[1]] = cj + dj
        return tuple(p)

    for o in (0.42, 0.36, 0.30, 0.24, 0.18, 0.12, 0.06):
        ucgen = [pt(-o * wi, -o * wj), pt(o * wi, -o * wj), pt(0, o * wj)]
        if all(nokta_yuzeyde(taban["f"], p) for p in ucgen):
            return taban, ucgen
    # dar/uzun yüzey: tarayarak 3 nokta
    bulunan = []
    for a in range(16):
        for b in range(8):
            p = pt(mn[ij[0]] + (a + 0.5) * wi / 16 - ci, mn[ij[1]] + (b + 0.5) * wj / 8 - cj)
            if nokta_yuzeyde(taban["f"], p):
                bulunan.append(p)
    if len(bulunan) < 3:
        return taban, []
    secili = [bulunan[0]]
    for p in bulunan:
        if all(math.dist(p, q) > 0.2 * max(wi, wj) for q in secili):
            secili.append(p)
        if len(secili) == 3:
            break
    return taban, secili[:3]


# ========================================================== CLI
def main():
    ap = argparse.ArgumentParser(description="ADIM 1 – referans belirleme")
    ap.add_argument("step")
    ap.add_argument("--liste", action="store_true", help="parça ve grup listesi")
    ap.add_argument("--grup", help="grup no (G01 gibi)")
    ap.add_argument("--parca", type=int, help="tek katı no")
    ap.add_argument("--yon", help="+X -X +Y -Y +Z -Z  (onay yoksa yönü zorla)")
    ap.add_argument("-o", "--out", default="referans.json")
    a = ap.parse_args()

    kayit = step_oku(a.step)
    print(f"{a.step}: {len(kayit)} katı okundu")

    gruplar, temaslar, kok = temas_grupla(kayit)

    if a.liste:
        print(f"\n{len(gruplar)} grup bulundu (birbirine değen katılar tek grup)\n")
        print(f"{'no':5s}{'katı':>6s}{'kg':>10s}  ilk parçalar")
        for gi, uy in enumerate(gruplar, 1):
            kg = sum(hacim(kayit[i][1]) for i in uy) * RHO
            adlar = Counter(re.sub(r"[-_]?\d+$", "", kayit[i][0]) for i in uy)
            ilk = ", ".join(f"{q}x {nm[:28]}" for nm, q in adlar.most_common(3))
            print(f"G{gi:02d}  {len(uy):5d}{kg:10.2f}  {ilk}")
        print("\nSeçim:  --grup G01   |   tek katı için:  --parca <no>")
        return

    if a.grup:
        gi = int(re.sub(r"\D", "", a.grup)) - 1
        if not (0 <= gi < len(gruplar)):
            sys.exit(f"HATA: {a.grup} yok, 1..{len(gruplar)}")
        uyeler = gruplar[gi]; sec_ad = a.grup.upper()
    elif a.parca:
        if not (1 <= a.parca <= len(kayit)):
            sys.exit(f"HATA: 1..{len(kayit)}")
        uyeler = [a.parca - 1]; sec_ad = kayit[a.parca - 1][0]
    else:
        sys.exit("Önce --liste ile seç, sonra --grup veya --parca ver.")

    kg = sum(hacim(kayit[i][1]) for i in uyeler) * RHO
    print(f"\nSEÇİLEN: {sec_ad} – {len(uyeler)} katı, {kg:.2f} kg")
    for i in uyeler[:12]:
        print(f"    {kayit[i][0]}")
    if len(uyeler) > 12:
        print(f"    ... +{len(uyeler)-12} katı")

    puan, ic = yon_puanla(kayit, uyeler, temaslar)
    print(f"\nİç birleşim sayısı: {len(ic)}")
    print(f"\n{'yön':5s}{'puan':>8s}{'iç erişim':>11s}{'erişim mm2':>13s}{'oturma mm2':>13s}{'yükseklik':>11s}")
    for s in puan:
        print(f"{s['yon']:5s}{s['puan']:8.3f}{s['erisim_orani']*100:10.1f}%{s['erisim_mm2']:13.1f}"
              f"{s['oturma_mm2']:13.1f}{s['yukseklik_mm']:11.1f}")

    sec = puan[0]
    if a.yon:
        sec = next((s for s in puan if s["yon"] == a.yon.upper()), None)
        if sec is None:
            sys.exit(f"HATA: yön {a.yon} geçersiz")
        print(f"\n>>> Yön kullanıcı tarafından zorlandı: {sec['yon']}")
    else:
        print(f"\n>>> ÖNERİLEN YÖN: {sec['yon']} (yukarı), parça {sec['yon'][1]} ekseninde yatar")

    er = Erisim([kayit[i][1] for i in uyeler])
    taban, ucgen = uc_nokta(kayit, uyeler, sec["u"], er, ic)
    if taban is None:
        print("UYARI: oturma yüzeyi bulunamadı, başka yön deneyin (--yon).")
        return
    print(f"\nOTURMA YÜZEYİ (datum A): alan {taban['alan']:.1f} mm², "
          f"normal {tuple(round(v,3) for v in taban['n'])}")
    if len(ucgen) < 3:
        print("UYARI: yüzeyde 3 nokta bulunamadı.")
    else:
        print(f"\n3 KONUMLANDIRMA NOKTASI")
        for i, p in enumerate(ucgen, 1):
            print(f"   P{i}   X {p[0]:10.2f}   Y {p[1]:10.2f}   Z {p[2]:10.2f}")
        a_ = math.dist(ucgen[0], ucgen[1]); b_ = math.dist(ucgen[1], ucgen[2])
        c_ = math.dist(ucgen[0], ucgen[2])
        sp = (a_ + b_ + c_) / 2
        alan = math.sqrt(max(sp * (sp - a_) * (sp - b_) * (sp - c_), 0))
        print(f"   üçgen kenarları {a_:.1f} / {b_:.1f} / {c_:.1f} mm, alan {alan:.0f} mm²")

    json.dump({"dosya": a.step, "secim": sec_ad, "kati_sayisi": len(uyeler),
               "agirlik_kg": round(kg, 3),
               "yon_siralamasi": puan, "secilen_yon": sec["yon"],
               "datum_A": {"alan_mm2": round(taban["alan"], 1),
                           "normal": [round(v, 4) for v in taban["n"]],
                           "merkez": [round(v, 2) for v in taban["c"]]},
               "uc_nokta": [[round(v, 2) for v in p] for p in ucgen],
               "onay": False},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n(a) ONAY BEKLİYOR  ->  {a.out}")
    print("    onaylarsan: dosyada \"onay\": true yap veya bana söyle")
    print("    onaylamazsan: --yon +X / -X / +Y / -Y / +Z / -Z ile tekrar çalıştır")


if __name__ == "__main__":
    main()
