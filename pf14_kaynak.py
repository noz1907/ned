# -*- coding: utf-8 -*-
"""KAYNAK RESMİ: her kaynaklı alt grup için dikişlerin yeri, ölçüsü, sembolü.

Montaj ağacında içinde dikiş yaprağı olan en yakın düğüm bir KAYNAKLI
GRUPTUR ("K0 CIVATA LAMASI_2_MONTAJ", "K0 ON PANEL KAYNAK_SAG"). Her grup
kendi resmini alır:

  * PARÇALAR: dikişe fiziksel olarak DEĞEN katılar (0,2 mm) + aynı
    düğümdeki kardeş parçalar. Dikişler ayrı "KAYNAKLAR" ağacında dursa da
    birleştirdikleri parçalar böylece bulunur.
  * GÖRÜNÜŞLER: ÖN, ÜST, SAĞ + iki izometrik (ön-sağ-üst, arka-sol-üst).
    Dikiş kenarları kırmızı, kalın çizilir.
  * GÖRÜNÜRLÜK ÖLÇÜLÜR: dikiş boyunca 5 noktadan göze doğru ışın (parça
    ağında): ışın bir parçaya çarpıyorsa o noktada dikiş gizlidir. Her dikiş
    NET göründüğü ve boyunun en uzun göründüğü TEK görünüşte işaretlenir;
    dik görünüşlerde görünmüyorsa izometrikte.
  * SEMBOL (ISO 2553): ok + referans çizgisi + köşe kaynağı üçgeni +
    "a2" (boğaz) + "25" (boy) + K numarası balonu. Punta: daire sembolü.
  * TABLO: K no, tip, a, boy, başlangıç / bitiş koordinatı (grubun sınır
    kutusunun köşesine göre, mm), birleştirdiği pozlar, işaretlendiği
    görünüş. Görünüş ne kadar kalabalık olursa olsun ölçü ve yer buradan
    KESİN okunur.

Kaynak YÖNTEMİ (gazaltı, TIG) geometriden anlaşılmaz; yazılmaz.
"""
from __future__ import annotations

import math
import os
from collections import Counter

import pf8_tani as TN
import pf9_excel as XL

DEGME_TOL = 0.2            # mm: dikişe bu kadar yakın katı onun parçasıdır
GORUNUR_ORAN = 0.6         # dikiş noktalarının bu kadarı görünüyorsa "net"
# izometrik yönler: göz yönü; X ekseni yatay (-b, a, 0) -> Z hep yukarı
ISO_YON = {"ISO1": (1.0, -1.0, 1.0), "ISO2": (-1.0, 1.0, 1.0),
           "ISO3": (-1.0, -1.0, 1.0), "ISO4": (1.0, 1.0, 1.0),
           "ISO5": (1.0, -1.0, -1.0), "ISO6": (-1.0, 1.0, -1.0)}
ISO_GOR = {k: (g, (-g[1], g[0], 0.0)) for k, g in ISO_YON.items()}
GOR_AD = {"ON": "ÖN", "UST": "ÜST", "SAG": "SAĞ", "ARKA": "ARKA", "SOL": "SOL",
          "ALT": "ALT", "ISO1": "İZOMETRİK ÖN-SAĞ", "ISO2": "İZOMETRİK ARKA-SOL",
          "ISO3": "İZOMETRİK ÖN-SOL", "ISO4": "İZOMETRİK ARKA-SAĞ",
          "ISO5": "İZOMETRİK ALTTAN ÖN-SAĞ", "ISO6": "İZOMETRİK ALTTAN ARKA-SOL"}
SIRA = ("ON", "UST", "SAG", "ISO1", "ISO2")


def _birim(v):
    n = math.sqrt(sum(a * a for a in v)) or 1.0
    return tuple(a / n for a in v)


def _izdusum(p, goz, xref):
    """3B nokta -> görünüş (x, y): HLR ile aynı çerçeve (x = X, y = N x X)."""
    N, X = goz, xref
    Y = (N[1] * X[2] - N[2] * X[1], N[2] * X[0] - N[0] * X[2], N[0] * X[1] - N[1] * X[0])
    return (sum(a * b for a, b in zip(p, X)), sum(a * b for a, b in zip(p, Y)))


# ------------------------------------------------------------ gruplar
def _ebeveynler(agac):
    """katı indeksi -> yaprak düğüm, düğüm id -> (düğüm, üst düğüm)."""
    yaprak, ust = {}, {}

    def gez(d, u):
        ust[id(d)] = (d, u)
        for j in d.get("tum") or d.get("katilar") or []:
            yaprak.setdefault(j, d)
        for a in d.get("alt") or []:
            gez(a, d)
    if agac:
        gez(agac, None)
    return yaprak, ust


def _yol(d, ust):
    out = []
    while d is not None:
        out.append(d)
        d = ust[id(d)][1]
    return out[::-1]


def kaynakli_gruplar(kayit, komp, agac=None, log=print):
    """KAYNAKLI ALT GRUPLAR: [{ad, adet, dikis: [katı], parca: [katı]}].

    Dikişin grubu, modelde nerede durduğuna (ayrı "KAYNAKLAR" ağacı) göre
    DEĞİL, birleştirdiği parçalara göre bulunur:
      1. her dikişe DEĞEN parçalar ölçülür (DEGME_TOL);
      2. o parçaların montaj ağacındaki EN YAKIN ORTAK ÜST DÜĞÜMÜ dikişin
         alt grubudur (braket kaynağı braketin grubunda, braketi şasiye
         bağlayan kaynak bir üst grupta kalır);
      3. aynı düğümdeki dikişler, parça paylaşarak FİZİKSEL OLARAK BAĞLI
         kümelere ayrılır: birbirinden kopuk iki braket ayrı resimdir;
      4. aynı biçimdeki kümeler (alt montajın kopyaları, simetrikler) tek
         resim + adet olur."""
    kati_komp = {}
    for i, k in enumerate(komp):
        for j in k["indeks"]:
            kati_komp[j] = i
    dikisler = [j for j in range(len(kayit))
                if j in kati_komp and komp[kati_komp[j]]["sinif"] == "kaynak"]
    if not dikisler:
        return []
    parca_aday = [j for j in range(len(kayit))
                  if j in kati_komp and komp[kati_komp[j]]["sinif"] != "kaynak"]
    kutular = {j: TN._kutu(kayit[j][1]) for j in parca_aday}
    yaprak, ust = _ebeveynler(agac)
    kok = agac
    # 1-2: değen parçalar ve ortak üst düğüm
    dugum_dikis = {}
    degen = {}
    sinif = {}
    for j in dikisler:
        dg = degen_katilar(kayit[j][1], parca_aday, kayit, kutular, sinif)
        degen[j] = dg
        yollar = [_yol(yaprak[p], ust) for p in dg if p in yaprak]
        if yollar:
            n = 0                              # ortak önek uzunluğu
            while all(len(y) > n and y[n] is yollar[0][n] for y in yollar):
                n += 1
            y = yollar[0][:n]
            dugum = y[-1]
            if not dugum.get("alt") and len(y) > 1:   # yaprak (parça): onun grubu
                dugum = y[-2]
        else:
            dugum = kok
        dugum_dikis.setdefault(id(dugum), (dugum, []))[1].append(j)
    # 3: bağlı kümeler (dikiş - parça ağı)
    kumeler = []
    for dugum, js in dugum_dikis.values():
        kume_of = {}
        ata = {}

        def bul(x):
            while ata.setdefault(x, x) != x:
                ata[x] = ata[ata[x]]
                x = ata[x]
            return x
        for j in js:
            for p in degen[j]:
                ata[bul(("d", j))] = bul(("p", p))
            bul(("d", j))
        for j in js:
            kume_of.setdefault(bul(("d", j)), []).append(j)
        for kjs in kume_of.values():
            parca = sorted({p for j in kjs for p in degen[j]})
            kumeler.append({"dugum": dugum, "dikis": kjs, "parca": parca})
    # 4: aynı biçim -> tek resim
    grup = {}
    for k in kumeler:
        imza = (id(k["dugum"]),
                tuple(sorted(Counter(kati_komp[p] for p in k["parca"]).items())),
                tuple(sorted(Counter(kati_komp[j] for j in k["dikis"]).items())))
        if imza in grup:
            grup[imza]["adet"] += 1
        else:
            grup[imza] = dict(k, adet=1)
    out = []
    for g in grup.values():
        ad = (g["dugum"] or {}).get("ad") or "?"
        if g["parca"]:
            en = max(g["parca"], key=lambda p: komp[kati_komp[p]].get("hacim_mm3") or 0)
            ana = komp[kati_komp[en]]["ad"]
            if ana and ana not in ad:
                ad = f"{ad} - {ana}"
        out.append({"ad": ad, "dugum_ad": (g["dugum"] or {}).get("ad") or "KAYNAK",
                    "adet": g["adet"], "dikis": g["dikis"],
                    "parca": g["parca"], "degen": {j: degen[j] for j in g["dikis"]}})
    out.sort(key=lambda g: -len(g["dikis"]))
    return out


# ------------------------------------------------------------ dikiş
def dikis_ekseni(sh):
    """(p0, p1, orta, yön): dikişin en uzun asal ekseni boyunca uçları."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(sh, g)
    c = g.CentreOfMass()
    p = g.PrincipalProperties()
    I = p.Moments()
    m = (p.FirstAxisOfInertia(), p.SecondAxisOfInertia(), p.ThirdAxisOfInertia())
    e = m[min(range(3), key=lambda i: I[i])]
    d = (e.X(), e.Y(), e.Z())
    o = (c.X(), c.Y(), c.Z())
    kb = TN._kutu(TN._eksene_tasi(sh, o, d))
    p0 = tuple(o[i] + d[i] * kb[2] for i in range(3))
    p1 = tuple(o[i] + d[i] * kb[5] for i in range(3))
    return p0, p1, o, d


def _kutu_yakin(a, b, pay):
    return not (a[3] + pay < b[0] or b[3] + pay < a[0] or a[4] + pay < b[1]
                or b[4] + pay < a[1] or a[5] + pay < b[2] or b[5] + pay < a[2])


def degen_katilar(sh, adaylar, kayit, kutular, siniflayici=None):
    """sh'ye DEGME_TOL'dan yakın katılar (indeks listesi).

    Hız: önce dikişin KÖŞELERİ parçaya göre sınıflanır (köşe dikişinin
    bacak uçları sacın üstündedir; ms mertebesi). Köşesi değmeyen aday
    için kesin uzaklık hesaplanır (dikiş parçaya yalnız bir yüzün ya da
    kenarın ortasında değebilir). Sonuç yalnız kesin uzaklığınkiyle
    AYNIDIR; kaynaklı kasada 200 dikişte fark 0, süre 60 sn -> 4,7 sn."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.TopAbs import TopAbs_OUT, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    siniflayici = {} if siniflayici is None else siniflayici
    kb = TN._kutu(sh)
    kose = []
    ex = TopExp_Explorer(sh, TopAbs_VERTEX)
    while ex.More():
        kose.append(BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current())))
        ex.Next()
    out = []
    for j in adaylar:
        if not _kutu_yakin(kb, kutular[j], DEGME_TOL + 0.5):
            continue
        try:
            c = siniflayici.get(j)
            if c is None:
                c = siniflayici[j] = BRepClass3d_SolidClassifier(kayit[j][1])
            deger = False
            for p in kose:
                c.Perform(p, DEGME_TOL)
                if c.State() != TopAbs_OUT:
                    deger = True
                    break
            if not deger:
                d = BRepExtrema_DistShapeShape(sh, kayit[j][1])
                deger = d.IsDone() and d.Value() <= DEGME_TOL
            if deger:
                out.append(j)
        except Exception:
            continue
    return out


# ------------------------------------------------------------ konum
def _bacak(dikis_sh, parca_sh):
    """Dikişin parçaya oturan BACAK yüzü (düzlem, en geniş): (nokta, normal)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    en = None
    ex = TopExp_Explorer(dikis_sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        s = BRepAdaptor_Surface(f)
        if s.GetType() != GeomAbs_Plane:
            continue
        g = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, g)
        c = g.CentreOfMass()
        if not _degiyor((c.X(), c.Y(), c.Z()), parca_sh, DEGME_TOL):
            continue                       # yüzün ortası parçada değil
        if en is None or g.Mass() > en[0]:
            ax = s.Plane().Axis()
            p, n = ax.Location(), ax.Direction()
            en = (g.Mass(), (p.X(), p.Y(), p.Z()), (n.X(), n.Y(), n.Z()))
    return None if en is None else en[1:]


_SINIF_ONB = {}


def _degiyor(p, sh, tol):
    """p, katının yüzeyine tol'dan yakın (ya da içinde) mı. Nokta
    sınıflayıcı katı başına bir kez kurulur."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_OUT
    from OCP.gp import gp_Pnt
    c = _SINIF_ONB.get(id(sh))
    if c is None or c[0] is not sh:
        c = _SINIF_ONB[id(sh)] = (sh, BRepClass3d_SolidClassifier(sh))
    c[1].Perform(gp_Pnt(*p), tol)
    return c[1].State() != TopAbs_OUT


def _hat_yuzleri(sh, k, u, tol):
    """Katının, k + t·u doğrusuna tol'dan yakın geçebilen yüzleri (sınır
    kutusu - doğru kesişimi): [(yüzey, sınıflayıcı)]. Kök çizgisi boyunca
    yürürken yalnız bunlara bakılır; büyük sacın yüzlerce yüzü elenir."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepTopAdaptor import BRepTopAdaptor_FClass2d
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    out = []
    ex = TopExp_Explorer(sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        b = TN._kutu(f)
        t0, t1 = -1e18, 1e18
        for i in range(3):
            lo, hi = b[i] - tol - 0.5, b[i + 3] + tol + 0.5
            if abs(u[i]) < 1e-12:
                if not lo <= k[i] <= hi:
                    t0, t1 = 1.0, 0.0
                    break
            else:
                a_, c_ = (lo - k[i]) / u[i], (hi - k[i]) / u[i]
                t0, t1 = max(t0, min(a_, c_)), min(t1, max(a_, c_))
        if t0 <= t1:
            out.append((BRep_Tool.Surface_s(f), BRepTopAdaptor_FClass2d(f, 0.05)))
    return out


def _yuzeyde(p, yuzler, tol):
    """p, yüzlerden birinin içine (sınırı dahil) tol'dan yakın mı."""
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Pnt, gp_Pnt2d
    from OCP.TopAbs import TopAbs_OUT
    q = gp_Pnt(*p)
    for srf, cls in yuzler:
        pr = GeomAPI_ProjectPointOnSurf(q, srf)
        if pr.NbPoints() == 0 or pr.LowerDistance() > tol:
            continue
        u_, v_ = pr.LowerDistanceParameters()
        if cls.Perform(gp_Pnt2d(u_, v_)) != TopAbs_OUT:
            return True
    return False


def _sinir(ic, t, yon, en_cok=3000.0):
    """t'den yon (+1/-1) doğrultusunda ic(t)'nin bittiği yer (0,1 mm)."""
    adim, a = 0.5, t
    while adim <= en_cok:
        b = t + yon * adim
        if not ic(b):
            break
        a = b
        adim *= 2.0
    else:
        return None                        # sınır yok (çok uzun)
    for _ in range(24):
        m = (a + b) / 2.0
        if ic(m):
            a = m
        else:
            b = m
        if abs(b - a) < 0.1:
            break
    return (a + b) / 2.0


def konum_hesapla(d, parca_sh):
    """Dikişin KÖK ÇİZGİSİ üzerindeki yeri.

    Kök çizgisi, dikişin iki parçaya oturan BACAK yüzlerinin düzlemlerinin
    kesişimidir (dikişin kendi geometrisinden, kesin). Bu çizgi boyunca
    iki parçanın da yüzeyi sürdüğü aralık [T0, T1] ölçülür: çizgi
    üzerindeki nokta iki parçaya da değiyorsa birleşme oradadır (sınır
    0,1 mm'ye bölünerek bulunur). Dikiş bir uçtan başlamıyorsa YAKIN
    uçtan dikiş başına mesafe döner: {"deger", "uc" (3B), "bas" (3B)};
    uçtan başlıyorsa deger 0; iki parçalı değilse ya da ölçülemezse None."""
    import numpy as np
    if len(parca_sh) != 2:
        return None
    bc = [_bacak(d["sh"], sh) for sh in parca_sh]
    if any(b is None for b in bc):
        return None
    (pa, na), (pb, nb) = [(np.array(p), np.array(n)) for p, n in bc]
    u = np.cross(na, nb)
    if np.linalg.norm(u) < 0.2:            # bacaklar paralel: kök çizgisi yok
        return None
    u = u / np.linalg.norm(u)
    e = np.array(d["yon"])
    if u @ e < 0:
        u = -u
    if abs(u @ e) < 0.95:                  # kök çizgisi dikiş boyunca değil
        return None
    # iki düzlemin ve dikiş ortasından geçen dik düzlemin kesişim noktası
    o = np.array(d["orta"])
    M = np.array([na, nb, u])
    k = np.linalg.solve(M, np.array([na @ pa, nb @ pb, u @ o]))
    w0 = float((np.array(d["p0"]) - k) @ u)
    w1 = float((np.array(d["p1"]) - k) @ u)
    w0, w1 = min(w0, w1), max(w0, w1)
    tm = (w0 + w1) / 2.0
    tol = 0.3                              # kaynakta alt-mm hassasiyet aranmaz
    yz = [_hat_yuzleri(sh, k, u, tol) for sh in parca_sh]

    def ic(t):
        p = tuple(k + u * t)
        return all(_yuzeyde(p, y, tol) for y in yz)
    if not ic(tm):                         # kök çizgisi parçalarda değil
        return None
    T0, T1 = _sinir(ic, tm, -1), _sinir(ic, tm, +1)
    if T0 is None or T1 is None or T1 - T0 < 0.5 * (w1 - w0):
        return None
    s0, s1 = w0 - T0, T1 - w1
    # dikiş ucu parça kenarını geçebilir (kenarı döner) ya da kenara bir-iki
    # mm kala biter: atölyede ikisi de "uçtan başlar"
    if min(s0, s1) < UCTAN_PAY:
        return {"deger": 0}
    if s0 <= s1:
        uc, bas, v = T0, w0, s0
    else:
        uc, bas, v = T1, w1, s1
    # tam mm: kaynakta ondalık yok (atölye ölçüsü)
    return {"deger": XL.tam(v), "uc": tuple(k + u * uc), "bas": tuple(k + u * bas)}


def _konum_olcusu(msp, R, d, h):
    """Kenardan dikiş başına ölçü (kâğıtta; yazı gerçek mm)."""
    k = d.get("konum")
    if not k or not k.get("uc"):
        return
    if abs(sum(x * y for x, y in zip(d["yon"], R.goz))) > 0.25:
        return                             # eksen görünüşe eğik: boy kısalır
    a, b = R.p3(k["uc"]), R.p3(k["bas"])
    L = math.dist(a, b)
    if L < 1.5:
        return
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = -uy, ux
    if ny < 0 or (abs(ny) < 1e-9 and nx < 0):
        nx, ny = -nx, -ny
    off = 2.4 * h
    kat = {"layer": "OLCU"}
    a2 = (a[0] + nx * off, a[1] + ny * off)
    b2 = (b[0] + nx * off, b[1] + ny * off)
    for p, q in ((a, a2), (b, b2)):
        msp.add_line((p[0] + nx * 0.6, p[1] + ny * 0.6),
                     (q[0] + nx * 0.8, q[1] + ny * 0.8), dxfattribs=kat)
    msp.add_line(a2, b2, dxfattribs=kat)
    ok = min(0.8 * h, L / 3)
    for p, sgn in ((a2, 1), (b2, -1)):
        tx, ty = ux * sgn, uy * sgn
        msp.add_solid([p, (p[0] + ok * tx + 0.3 * ok * nx, p[1] + ok * ty + 0.3 * ok * ny),
                       (p[0] + ok * tx - 0.3 * ok * nx, p[1] + ok * ty - 0.3 * ok * ny)],
                      dxfattribs=kat)
    t = str(XL.tam(k["deger"]))
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90 or ang <= -90:
        ang -= 180 if ang > 0 else -180
    mx, my = (a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2
    e = _yaz(msp, t, mx + nx * 0.5 * h, my + ny * 0.5 * h, h, kat="OLCU")
    try:
        from ezdxf.enums import TextEntityAlignment
        e.set_placement((mx + nx * 0.5 * h, my + ny * 0.5 * h),
                        align=TextEntityAlignment.BOTTOM_CENTER)
    except Exception:
        pass
    e.dxf.rotation = ang


# ------------------------------------------------------------ görünürlük
def _yonlu_ag(sh):
    """Katının üçgenleri, normalleri MALZEMEDEN DIŞARI bakacak sırada
    (ters yönlü yüzde düğüm sırası çevrilir)."""
    import numpy as np
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    kb = TN._kutu(sh)
    B = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]) or 1.0
    BRepMesh_IncrementalMesh(sh, min(0.2, B / 100.0), False, 0.3, True)
    out = []
    ex = TopExp_Explorer(sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        loc = TopLoc_Location()
        t = BRep_Tool.Triangulation_s(f, loc)
        if t is None:
            continue
        tr = loc.Transformation()
        pts = np.array([[q.X(), q.Y(), q.Z()] for q in
                        (t.Node(i).Transformed(tr) for i in range(1, t.NbNodes() + 1))])
        ic = np.array([t.Triangle(i).Get() for i in range(1, t.NbTriangles() + 1)]) - 1
        if f.Orientation() == TopAbs_REVERSED:
            ic = ic[:, [0, 2, 1]]
        out.append(pts[ic])
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


class _Isin:
    """Parça ağı üzerinde göze doğru ışın: dikişin o noktası görünür mü."""

    def __init__(self, ag):
        self.ag0 = ag
        self.cache = {}

    def _yon(self, goz):
        from OCP.gp import gp_Trsf, gp_Ax3, gp_Pnt, gp_Dir
        if goz not in self.cache:
            t = gp_Trsf()
            t.SetTransformation(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(*goz)))
            self.cache[goz] = (t, self.ag0.tasi((0.0, 0.0, 0.0), goz))
        return self.cache[goz]

    def acik_mi(self, p, goz):
        from OCP.gp import gp_Pnt
        t, ag = self._yon(goz)
        q = gp_Pnt(*p).Transformed(t)
        return not ag.kes(q.X(), q.Y(), q.Z() + 0.02, q.Z() + 1e6)


def dikis_ornekleri(d, n=5):
    """Dikişin ekseni boyunca n dilimden, dışarı bakan yüzey noktaları:
    [(dilim, nokta, normal)]."""
    import numpy as np
    u = _yonlu_ag(d["sh"])
    if len(u) == 0:
        return []
    nr = np.cross(u[:, 1] - u[:, 0], u[:, 2] - u[:, 0])
    ln = np.linalg.norm(nr, axis=1)
    ok = ln > 1e-12
    u, nr, ln = u[ok], nr[ok] / ln[ok][:, None], ln[ok] / 2.0
    # üçgen başına barisentrik ızgara: düzlem yüzün üçgenleri dikiş boyunca
    # uzanır, merkezleri her dilime düşmez
    k = 6
    w = np.array([(i, j, k - i - j) for i in range(k + 1) for j in range(k + 1 - i)],
                 float) / k
    w = 0.9 * w + 0.1 / 3.0                    # kenarlara değil, içe
    pts = np.einsum("wk,tkd->twd", w, u)       # (üçgen, nokta, 3)
    o, e = np.array(d["orta"]), np.array(d["yon"])
    t = (pts - o) @ e
    t0, t1 = t.min(), t.max()
    dl = np.clip(((t - t0) / max(t1 - t0, 1e-9) * n).astype(int), 0, n - 1)
    out = []
    for ti in range(len(u)):
        for dilim in set(dl[ti].tolist()):
            m = pts[ti][dl[ti] == dilim].mean(0)
            out.append((dilim, tuple(m + 0.05 * nr[ti]), tuple(nr[ti]), float(ln[ti])))
    return out


def gorunurluk(d, isin, goz, n=5):
    """(görünen dilim oranı, oka en uygun görünen nokta)."""
    gor, ok_n = set(), None
    ornek = d.setdefault("_ornek", dikis_ornekleri(d, n))
    for dilim in range(n):
        aday = sorted((x for x in ornek if x[0] == dilim
                       and sum(a * b for a, b in zip(x[2], goz)) > 0.15),
                      key=lambda x: -sum(a * b for a, b in zip(x[2], goz)) * x[3])[:4]
        for _, p, nrm, _ in aday:
            if isin is None or isin.acik_mi(p, goz):
                gor.add(dilim)
                if ok_n is None or abs(dilim - n // 2) < abs(ok_n[0] - n // 2):
                    ok_n = (dilim, p)
                break
    return len(gor) / float(n), (ok_n[1] if ok_n else None)


# ------------------------------------------------------------ resim
YONLER = ("ON", "UST", "SAG", "ARKA", "SOL", "ALT", "ISO1", "ISO2", "ISO3", "ISO4",
          "ISO5", "ISO6")
ANA = ("ON", "UST", "SAG", "ISO1")
# detay çerçevesinin gösterildiği ana görünüş
CERCEVE_GOR = {"ON": "ON", "ARKA": "ON", "UST": "UST", "ALT": "UST", "SAG": "SAG",
               "SOL": "SAG", "ISO1": "ISO1", "ISO2": "ISO1", "ISO3": "ISO1",
               "ISO4": "ISO1", "ISO5": "ISO1", "ISO6": "ISO1"}
DETAYSIZ_EN_COK = 8       # bu kadar dikişe kadar etiketler ana görünüşlerde
DETAY_EN_COK = 8          # bir detay görünüşünde en çok dikiş
TABLO_BAS = ("K", "tip", "a", "z", "boy", "kenardan", "başlangıç (x; y; z)",
             "bitiş (x; y; z)", "birleştirdiği", "görünüş")


def _gorunus(O, gad):
    if gad in ISO_GOR:
        g, x = ISO_GOR[gad]
        return _birim(g), _birim(x)
    return O.GORUNUS[gad]


def _ad(gad):
    return GOR_AD[gad]


def _kirp(q, x0, y0, x1, y1):
    """Çoklu çizgiyi dikdörtgene kırpar (Liang-Barsky, parça parça)."""
    out, cur = [], []
    for a, b in zip(q, q[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1 = 0.0, 1.0
        ok = True
        for p, r in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
            if abs(p) < 1e-12:
                if r < 0:
                    ok = False
                    break
            else:
                t = r / p
                if p < 0:
                    t0 = max(t0, t)
                else:
                    t1 = min(t1, t)
        if not ok or t0 > t1:
            if len(cur) > 1:
                out.append(cur)
            cur = []
            continue
        pa = (a[0] + t0 * dx, a[1] + t0 * dy)
        pb = (a[0] + t1 * dx, a[1] + t1 * dy)
        if cur and math.dist(cur[-1], pa) < 1e-9:
            cur.append(pb)
        else:
            if len(cur) > 1:
                out.append(cur)
            cur = [pa, pb]
        if t1 < 1.0:
            out.append(cur)
            cur = []
    if len(cur) > 1:
        out.append(cur)
    return out


def _nokta_dogru(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _cakisir(d, kabul, goz, xr):
    """d'nin izdüşümü, kabul edilmiş bir dikişinkiyle üst üste mi (biri
    ötekinin şeridinde kalıyor mu)."""
    q = [_izdusum(p, goz, xr) for p in (d["p0"], d["orta"], d["p1"])]
    for e in kabul:
        r = [_izdusum(p, goz, xr) for p in (e["p0"], e["orta"], e["p1"])]
        tol = max(1.5, (d["olcu"].get("a_mm") or 1.0) + (e["olcu"].get("a_mm") or 1.0))
        if all(_nokta_dogru(p, r[0], r[2]) < tol for p in q) or \
                all(_nokta_dogru(p, q[0], q[2]) < tol for p in r):
            return True
    return False


def _bilesik(katilar):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    b = BRep_Builder()
    c = TopoDS_Compound()
    b.MakeCompound(c)
    for s in katilar:
        b.Add(c, s)
    return c


def _bolgele(dikisler, cap):
    """Dikişleri en çok DETAY_EN_COK'lu, çapı ~cap olan yakın kümelere
    ayırır (açgözlü: en uçtaki dikişten başla, en yakınları ekle)."""
    kalan = sorted(dikisler, key=lambda d: (d["orta"][0], d["orta"][1], d["orta"][2]))
    out = []
    while kalan:
        tohum = kalan.pop(0)
        grp = [tohum]
        kalan.sort(key=lambda d: math.dist(d["orta"], tohum["orta"]))
        while kalan and len(grp) < DETAY_EN_COK:
            d = kalan[0]
            if max(math.dist(d["orta"], g["orta"]) for g in grp) > cap:
                break
            grp.append(kalan.pop(0))
        out.append(grp)
    return out


def _yaz(msp, t, x, y, h, kat="YAZI"):
    from pf3_olcu import _yaz as yz
    return yz(msp, t, x, y, h, kat=kat)


def _en(t, h):
    return len(str(t)) * 0.72 * h


def _sembol(msp, q, dirsek, taraf, d, h):
    """ISO 2553 sembolü: ok (dikişe) -> kırılma -> yatay referans çizgisi;
    çizginin ALTINDA (ok tarafı) köşe kaynağı üçgeni, solunda a, sağında
    boy; kırılmada daire = çevre kaynağı; uçta K numarası balonu. Punta:
    daire sembolü."""
    kat = {"layer": "OLCU"}
    x, y = dirsek
    msp.add_line(q, (x, y), dxfattribs=kat)
    ang = math.atan2(y - q[1], x - q[0])
    ok_b = 1.2 * h
    msp.add_solid([q, (q[0] + ok_b * math.cos(ang + 0.3), q[1] + ok_b * math.sin(ang + 0.3)),
                   (q[0] + ok_b * math.cos(ang - 0.3), q[1] + ok_b * math.sin(ang - 0.3))],
                  dxfattribs=kat)
    o = d["olcu"]
    tip = o.get("tip") or ""
    # kaynak ölçüsü ondalıksız: a 1,77 -> a2
    sol_t = f"a{XL.tam(o['a_mm'])}" if o.get("a_mm") and "nokta" not in tip else ""
    sag_t = str(XL.tam(o["boy_mm"])) if o.get("boy_mm") and "nokta" not in tip else ""
    Lr = max(12 * h, _en(sol_t, h) + _en(sag_t, h) + 5 * h)
    x2 = x + taraf * Lr
    msp.add_line((x, y), (x2, y), dxfattribs=kat)
    if tip.startswith("çevre"):
        msp.add_circle((x, y), 0.8 * h, dxfattribs=kat)
    xs = min(x, x2) + _en(sol_t, h) + 1.5 * h
    if "nokta" in tip:
        msp.add_circle((xs + 0.8 * h, y), 0.7 * h, dxfattribs=kat)
    else:
        msp.add_lwpolyline([(xs, y), (xs, y - 1.4 * h), (xs + 1.4 * h, y), (xs, y)],
                           dxfattribs=kat)
    if sol_t:
        _yaz(msp, sol_t, xs - _en(sol_t, h) - 0.4 * h, y - 1.4 * h, h, kat="OLCU")
    if sag_t:
        _yaz(msp, sag_t, xs + 2.0 * h, y - 1.4 * h, h, kat="OLCU")
    r = 0.45 * _en(d["no"], h) + 0.6 * h
    bx = x2 + taraf * r
    msp.add_circle((bx, y), r, dxfattribs=kat)
    _yaz(msp, d["no"], bx - 0.36 * _en(d["no"], h) / 0.72, y - 0.5 * h, h, kat="OLCU")
    return abs(x2 - x) + 2 * r


class _Resim:
    """Bir görünüşün çizimi: parçalar (+ dikişler kırmızı), istenirse bir
    3B pencereye kırpılmış ve ölçeklenmiş."""

    def __init__(self, O, parcalar, dikis_sh, gad, pencere=None, olcek=1.0):
        self.gad = gad
        self.goz, self.xr = _gorunus(O, gad)
        self.olcek = olcek
        tum = _bilesik(list(parcalar) + list(dikis_sh))
        ken = O.hlr(tum, self.goz, self.xr, gizli=False)
        kk = O.hlr(_bilesik(dikis_sh), self.goz, self.xr, gizli=False) if dikis_sh else None
        izk = {}
        for q in (kk or {}).get("GORUNEN", []):
            for p in q:
                izk.setdefault((round(p[0]), round(p[1])), []).append(p)

        def kaynak_mi(q):
            m = q[len(q) // 2]
            return any(math.dist(p, m) <= 0.3 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                       for p in izk.get((round(m[0]) + dx, round(m[1]) + dy), ()))
        cizgi = [("KAYNAK" if izk and kaynak_mi(q) else "GORUNEN", q) for q in ken["GORUNEN"]]
        if pencere:
            x0, y0, x1, y1 = pencere
            cizgi = [(k, p) for k, q in cizgi for p in _kirp(q, x0, y0, x1, y1)]
        else:
            pts = [p for _, q in cizgi for p in q] or [(0.0, 0.0)]
            x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
            x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
        self.cizgi = cizgi
        self.kutu = (x0, y0, x1, y1)
        self.ox = self.oy = 0.0

    def boyut(self):
        x0, y0, x1, y1 = self.kutu
        return (x1 - x0) * self.olcek, (y1 - y0) * self.olcek

    def yerlestir(self, x, y_ust):
        """Sol üst köşe (x, y_ust)."""
        x0, y0, x1, y1 = self.kutu
        self.ox = x - x0 * self.olcek
        self.oy = y_ust - y1 * self.olcek

    def p(self, q2):
        return (q2[0] * self.olcek + self.ox, q2[1] * self.olcek + self.oy)

    def p3(self, p):
        return self.p(_izdusum(p, self.goz, self.xr))

    def ciz(self, msp):
        for kat, q in self.cizgi:
            msp.add_lwpolyline([self.p(a) for a in q], dxfattribs={"layer": kat})


def _etiketle(msp, R, dikisler, h):
    """Görünüşün sağına ve soluna, yukarıdan aşağı sıralı etiket sütunu."""
    x0, y0 = R.p(R.kutu[:2])
    x1, y1 = R.p(R.kutu[2:])
    orta = (x0 + x1) / 2
    for taraf in (-1, 1):
        ds = [(R.p3(d["ok"]), d) for d in dikisler]
        ds = [(q, d) for q, d in ds if (q[0] >= orta) == (taraf > 0)]
        ds.sort(key=lambda t: -t[0][1])
        y_son = y1 + 3.0 * h
        for q, d in ds:
            y = min(q[1], y_son - 3.0 * h)
            y_son = y
            x_dirsek = (x1 + 4 * h) if taraf > 0 else (x0 - 4 * h)
            _sembol(msp, q, (x_dirsek, y), taraf, d, h)
    for d in dikisler:
        _konum_olcusu(msp, R, d, h)


def _tablo_ciz(msp, satirlar, x, y_ust, h):
    """Sütunları hizalı, çizgili tablo. Döner: (genişlik, yükseklik)."""
    # büyük Türkçe harfler (İ, Ş, Ğ) ortalamadan geniş: sütunda pay
    en = [max(_en(s[i], h) * 1.12 for s in satirlar) + 2 * h
          for i in range(len(satirlar[0]))]
    sat_h = 2.0 * h
    kat = {"layer": "CERCEVE"}
    W = sum(en)
    for i, s in enumerate(satirlar):
        y = y_ust - (i + 1) * sat_h
        xx = x
        for t, e in zip(s, en):
            _yaz(msp, t, xx + h, y + 0.5 * h, h)
            xx += e
        msp.add_line((x, y), (x + W, y), dxfattribs=kat)
    msp.add_line((x, y_ust), (x + W, y_ust), dxfattribs=kat)
    xx = x
    for e in [0] + en:
        xx += e
        msp.add_line((xx, y_ust), (xx, y_ust - len(satirlar) * sat_h), dxfattribs=kat)
    msp.add_line((x, y_ust), (x, y_ust - len(satirlar) * sat_h), dxfattribs=kat)
    return W, len(satirlar) * sat_h


def kaynak_resmi(O, kayit, komp, grup, satirlar, yol, P=None, log=print):
    """Bir kaynaklı alt grubun kaynak resmi (DXF). Döner: dikiş listesi.

    Az dikişli grupta semboller ana görünüşlere konur. Çok dikişli grupta
    ana görünüşler yalnız yerleşimi gösterir (dikişler kırmızı, bölgeler
    harfli çerçeve); dikişler yakınlığa göre bölgelere ayrılır ve her
    bölge, dikişlerinin EN ÇOK göründüğü yönden BÜYÜTÜLMÜŞ bir DETAY
    görünüşüne çizilir. Detayda görünmeyen dikiş, göründüğü başka yönden
    ikinci bir detaya alınır."""
    import pf11_yapi as Y
    kati_komp = {}
    for i, k in enumerate(komp):
        for j in k["indeks"]:
            kati_komp[j] = i
    poz = {r["kod"]: r.get("poz") for r in satirlar if r.get("poz") not in (None, "")}
    parcalar = [j for j in grup["parca"]]
    dikisler = []
    for j in grup["dikis"]:
        sh = kayit[j][1]
        try:
            o = TN.kaynak_olcu(sh)
            p0, p1, orta, yon = dikis_ekseni(sh)
        except Exception:
            continue
        dikisler.append({"no": "", "j": j, "sh": sh, "olcu": o, "p0": p0, "p1": p1,
                         "orta": orta, "yon": yon, "degen": grup["degen"].get(j, []),
                         "kutu": TN._kutu(sh)})
    if not dikisler:
        return []
    parca_sh = [kayit[j][1] for j in parcalar]
    hepsi = _bilesik(parca_sh + [d["sh"] for d in dikisler])
    gk = TN._kutu(hepsi)
    datum = gk[:3]
    L = max(gk[3] - gk[0], gk[4] - gk[1], gk[5] - gk[2], 1.0)
    ag = Y._Ag(_bilesik(parca_sh)) if parca_sh else None
    detayli = len(dikisler) > DETAYSIZ_EN_COK

    def yon_sec(ds, isin, adaylar):
        """ds için en iyi yön: (görünen sayısı, ana görünüş, dik görünüş,
        izdüşüm boyu)."""
        en = None
        for gad in adaylar:
            goz, xr = _gorunus(O, gad)
            gor, boy = 0, 0.0
            for d in ds:
                oran, _ = gorunurluk(d, isin, goz)
                if oran >= GORUNUR_ORAN:
                    gor += 1
                    boy += math.dist(_izdusum(d["p0"], goz, xr), _izdusum(d["p1"], goz, xr))
            puan = (gor, gad in ANA, gad not in ISO_GOR, boy)
            if en is None or puan > en[0]:
                en = (puan, gad)
        return en[1]

    def ata(ds, isin):
        """Dikişleri yönlere dağıtır: [(yön, [dikiş])]. Her yönde yalnız NET
        görünen ve başka bir dikişle ÜST ÜSTE DÜŞMEYEN dikiş alınır (bir
        sacın iki yüzündeki dikişler aynı çizgiye izdüşer); kalan, sıradaki
        en iyi yöne kalır."""
        out, kalan, yonler = [], list(ds), list(YONLER)
        while kalan and yonler:
            gad = yon_sec(kalan, isin, yonler)
            yonler.remove(gad)
            goz, xr = _gorunus(O, gad)
            bu = []
            for d in sorted(kalan, key=lambda d: -(d["olcu"].get("boy_mm") or 0)):
                oran, ok = gorunurluk(d, isin, goz)
                if oran >= GORUNUR_ORAN and not _cakisir(d, bu, goz, xr):
                    d["gorunus"], d["ok"], d["gorunur"] = gad, ok, True
                    bu.append(d)
            if bu:
                out.append((gad, bu))
                kalan = [d for d in kalan if d not in bu]
        if kalan:                           # hiçbir yönden net değil
            gad = out[0][0] if out else "ISO1"
            goz, xr = _gorunus(O, gad)
            for d in kalan:
                oran, ok = gorunurluk(d, isin, goz)
                d["gorunus"], d["ok"], d["gorunur"] = gad, ok or d["orta"], False
            if out:
                out[0][1].extend(kalan)
            else:
                out.append((gad, kalan))
        return out

    isin_tum = _Isin(ag) if ag is not None else None
    # ---- ana görünüşler
    ana = list(ANA)
    # ---- etiket planı
    detaylar = []                          # [(harf, yön, [dikiş], pencere3B)]
    if not detayli:
        for gad, _ in ata(dikisler, isin_tum):
            if gad not in ana:
                ana.append(gad)
    else:
        cap = min(max(L / 6.0, 80.0), 300.0)
        harf = iter("ABCDEFGHJKLMNPRSTUVYZ" + "".join(f"{a}{b}" for a in "ABCDEFGH"
                                                        for b in "ABCDEFGHJKLMNPRSTUVYZ"))
        for bolge in _bolgele(dikisler, cap):
            kb = TN._kutu(_bilesik([d["sh"] for d in bolge]))
            pay = max(15.0, 0.25 * max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]))
            k3 = (kb[0] - pay, kb[1] - pay, kb[2] - pay, kb[3] + pay, kb[4] + pay, kb[5] + pay)
            yakin = [j for j in parcalar if _kutu_yakin(TN._kutu(kayit[j][1]), k3, 0.0)]
            if ag is not None:
                # detayda yalnız bölgeye giren parçalar çizilir; görünürlük
                # de onlarla ölçülür (önde duran uzak parça detayda yok)
                sec = ((ag.xmax >= k3[0]) & (ag.xmin <= k3[3]) &
                       (ag.ymax >= k3[1]) & (ag.ymin <= k3[4]) &
                       (ag.zmax >= k3[2]) & (ag.zmin <= k3[5]))
                isin = _Isin(Y._Ag(ucg=ag.u[sec])) if sec.any() else None
            else:
                isin = None
            for gad, bu in ata(bolge, isin):
                detaylar.append({"harf": next(harf), "gad": gad, "dikis": bu, "k3": k3,
                                 "parca": yakin})
    # numaralar: detay / görünüş sırasına, görünüşte yukarıdan aşağı
    sira = []
    if detaylar:
        for n, dt in enumerate(detaylar):
            for d in dt["dikis"]:
                d["detay"] = dt["harf"]
                q = _izdusum(d["ok"], *_gorunus(O, dt["gad"]))
                sira.append(((n, -q[1], q[0]), d))
    else:
        for d in dikisler:
            q = _izdusum(d["ok"], *_gorunus(O, d["gorunus"]))
            sira.append(((YONLER.index(d["gorunus"]), -q[1], q[0]), d))
    sira.sort(key=lambda t: t[0])
    dikisler = [d for _, d in sira]
    for no, d in enumerate(dikisler, 1):
        d["no"] = f"K{no}"
    for d in dikisler:
        try:
            d["konum"] = konum_hesapla(d, [kayit[j][1] for j in d["degen"]])
        except Exception:
            d["konum"] = None
        k = d["konum"] or {}
        if k.get("bas") and math.dist(k["bas"], d["p1"]) < math.dist(k["bas"], d["p0"]):
            d["p0"], d["p1"] = d["p1"], d["p0"]     # başlangıç = ölçülen uç
    # ---- tablo satırları
    def kk_(p):
        return "; ".join(XL.tr(XL.tam(p[i] - datum[i]), 0) for i in range(3))
    tab = []
    for d in dikisler:
        o = d["olcu"]
        birl = " + ".join(sorted({f"P{poz.get(komp[kati_komp[j]]['kod'], '?')}"
                                  for j in d["degen"] if j in kati_komp})) or "-"
        z = o["a_mm"] * math.sqrt(2) if o.get("a_mm") else None
        yer = (f"DETAY {d['detay']}" if d.get("detay") else _ad(d["gorunus"])) \
            + ("" if d["gorunur"] else " (gizli)")
        tab.append((d["no"], (o.get("tip") or "-")[:34],
                    str(XL.tam(o["a_mm"])) if o.get("a_mm") else "-",
                    str(XL.tam(z)) if z else "-",
                    XL.tr(XL.tam(o["boy_mm"]), 0) if o.get("boy_mm") else "-",
                    XL.tr(XL.tam(d["konum"]["deger"]), 0) if d.get("konum") else "?",
                    kk_(d["p0"]), kk_(d["p1"]), birl, yer))
    ana_r = [_Resim(O, parca_sh, [d["sh"] for d in dikisler], g) for g in ana]
    det_r = []
    for dt in detaylar:
        goz, xr = _gorunus(O, dt["gad"])
        k3 = dt["k3"]
        pts = [_izdusum((a, b, c), goz, xr) for a in (k3[0], k3[3])
               for b in (k3[1], k3[4]) for c in (k3[2], k3[5])]
        pen = (min(p[0] for p in pts), min(p[1] for p in pts),
               max(p[0] for p in pts), max(p[1] for p in pts))
        det_r.append(_Resim(O, [kayit[j][1] for j in dt["parca"]],
                            [d["sh"] for d in dikisler if _kutu_yakin(d["kutu"], k3, 0.0)],
                            dt["gad"], pencere=pen))
    toplam_boy = sum(d["olcu"].get("boy_mm") or 0 for d in dikisler)
    bilgi = {"ad": grup["ad"], "adet": grup["adet"], "dikis": len(dikisler),
             "boy": toplam_boy}
    sayfalar = _sayfalar(O, bilgi, tab, ana_r, dikisler, detaylar, det_r, detayli)
    pdf_yaz(sayfalar, yol)
    for d in dikisler:
        d.pop("sh", None)
        d.pop("_ornek", None)
    return dikisler


# ------------------------------------------------------------ sayfa
KAGIT = (420.0, 297.0)      # A3 yatay, mm
KENAR = 10.0
ANTET_Y = 18.0
YH = 2.5                    # kâğıtta yazı yüksekliği, mm
UCTAN_PAY = 2.0             # dikiş uca bundan yakınsa "uçtan başlar" (0)
KISA_TABLO = 10             # bu kadar dikişe kadar tablo genel görünüş sayfasında
ETIKET_PAY = 50.0           # görünüşün iki yanında etiket sütunu
# ISO 5455 ölçekleri (kâğıt / gerçek)
OLCEKLER = (1 / 500, 1 / 200, 1 / 100, 1 / 50, 1 / 20, 1 / 10, 1 / 5, 1 / 2, 1.0,
            2.0, 5.0, 10.0, 20.0, 50.0)
KATMAN_RENK = {"GORUNEN": 7, "KAYNAK": 1, "OLCU": 5, "YAZI": 7, "CERCEVE": 7,
               "DETAY": 6, "EKSEN": 6}


def olcek_sec(ideal):
    """ideal'den büyük olmayan en büyük standart ölçek."""
    return max([v for v in OLCEKLER if v <= ideal * 1.0001] or [OLCEKLER[0]])


def olcek_yazisi(v):
    if v >= 1:
        return f"{XL.tr(v, 0)}:1"
    return f"1:{XL.tr(round(1 / v), 0)}"


def _yeni_sayfa(O):
    doc = O.dxf_kur()
    for kat, renk in KATMAN_RENK.items():
        if kat not in doc.layers:
            doc.layers.add(kat)
        doc.layers.get(kat).color = renk
    doc.layers.get("KAYNAK").dxf.lineweight = 50
    doc.layers.get("GORUNEN").dxf.lineweight = 25
    try:
        doc.layers.get("DETAY").dxf.linetype = "KESIK"
    except Exception:
        pass
    return doc


def _antet(msp, bilgi, no, toplam):
    """Çerçeve + alt şerit antet."""
    W, H = KAGIT
    kat = {"layer": "CERCEVE"}
    msp.add_lwpolyline([(KENAR, KENAR), (W - KENAR, KENAR), (W - KENAR, H - KENAR),
                        (KENAR, H - KENAR)], close=True, dxfattribs=kat)
    y1 = KENAR + ANTET_Y
    msp.add_line((KENAR, y1), (W - KENAR, y1), dxfattribs=kat)
    for x in (KENAR + 250, W - KENAR - 45):
        msp.add_line((x, KENAR), (x, y1), dxfattribs=kat)
    _yaz(msp, "KAYNAK RESMİ", KENAR + 3, KENAR + 10.5, 4.0)
    _yaz(msp, bilgi["ad"][:95], KENAR + 3, KENAR + 3.5, YH)
    _yaz(msp, f"adet {bilgi['adet']}   -   {bilgi['dikis']} dikiş, toplam boy "
              f"{XL.tr(XL.tam(bilgi['boy']), 0)} mm", KENAR + 253, KENAR + 10.5, YH)
    _yaz(msp, "a: boğaz, z: kenar boyu (z = a·√2); ölçüler mm", KENAR + 253, KENAR + 3.5,
         YH)
    _yaz(msp, f"SAYFA {no} / {toplam}", W - KENAR - 42, KENAR + 10.5, 3.5)
    _yaz(msp, "Pi3D", W - KENAR - 42, KENAR + 3.5, YH)


def _tablo_sayfalari(tab):
    """Tabloyu sayfalara böler (başlık her sayfada)."""
    sat_h = 2.0 * YH
    kullan = KAGIT[1] - 2 * KENAR - ANTET_Y - 20.0
    n = max(5, int(kullan / sat_h) - 1)
    return [tab[i:i + n] for i in range(0, len(tab), n)] or [[]]


def _hucreler(n, y_ust):
    """Çizim alanını 2 sütunlu hücrelere böler: [(x0, y0, x1, y1)]."""
    W = KAGIT[0]
    x0, x1 = KENAR + 5, W - KENAR - 5
    y0 = KENAR + ANTET_Y + 5
    satir = max(1, (n + 1) // 2)
    hh = (y_ust - y0) / satir
    ww = (x1 - x0) / 2
    return [(x0 + (i % 2) * ww, y_ust - (i // 2 + 1) * hh,
             x0 + (i % 2 + 1) * ww, y_ust - (i // 2) * hh) for i in range(n)]


def _hucreye_koy(msp, R, hucre, etiketli, baslik):
    """R'yi hücrenin ortasına koyar (ölçeği önceden verilmiş), başlık yazar."""
    x0, y0, x1, y1 = hucre
    w, h = R.boyut()
    cx = (x0 + x1) / 2
    ust = y1 - 9.0
    R.yerlestir(cx - w / 2, ust - max(0.0, (ust - y0 - h) / 2))
    R.ciz(msp)
    bx, by = R.p(R.kutu[:2])
    _yaz(msp, baslik, bx, R.p(R.kutu[2:])[1] + 3.0, 3.0)


def _sayfalar(O, bilgi, tab, ana_r, dikisler, detaylar, det_r, detayli):
    """Sayfa listesi (her biri ezdxf belgesi, kâğıt mm)."""
    sayfalar = []
    W, H = KAGIT
    ust = H - KENAR - 5
    kisa = not detayli and len(tab) <= KISA_TABLO
    # 1. genel görünüş(ler); kısa tablo ilk sayfanın üstünde
    for i0 in range(0, len(ana_r), 4):
        grp = ana_r[i0:i0 + 4]
        doc = _yeni_sayfa(O)
        msp = doc.modelspace()
        y_h = ust - 8
        if kisa and i0 == 0:
            _, th = _tablo_ciz(msp, [TABLO_BAS] + list(tab), KENAR + 5, ust - 9, YH)
            y_h = ust - 9 - th - 4
        hucre = _hucreler(len(grp), y_h)
        _yaz(msp, "GENEL GÖRÜNÜŞ" + ("" if detayli else "  -  dikiş sembolleri ve numaraları")
             + ("  -  harfli çerçeveler detay sayfalarındadır" if detayli else ""),
             KENAR + 5, ust - 4, 3.5)
        pay = 0.0 if detayli else ETIKET_PAY
        ideal = min(min((c[2] - c[0] - 2 * pay - 6) / max(R.boyut()[0], 1e-6),
                        (c[3] - c[1] - 14) / max(R.boyut()[1], 1e-6))
                    for R, c in zip(grp, hucre))
        s = olcek_sec(ideal)
        for R, c in zip(grp, hucre):
            R.olcek = s
            _hucreye_koy(msp, R, c, not detayli, f"{_ad(R.gad)}   ({olcek_yazisi(s)})")
            if not detayli:
                _etiketle(msp, R, [d for d in dikisler if d["gorunus"] == R.gad], YH)
            else:
                for dt in detaylar:
                    if CERCEVE_GOR.get(dt["gad"]) != R.gad:
                        continue
                    k3 = dt["k3"]
                    pts = [R.p3((a, b, c_)) for a in (k3[0], k3[3]) for b in (k3[1], k3[4])
                           for c_ in (k3[2], k3[5])]
                    ax0, ay0 = min(p[0] for p in pts), min(p[1] for p in pts)
                    ax1, ay1 = max(p[0] for p in pts), max(p[1] for p in pts)
                    msp.add_lwpolyline([(ax0, ay0), (ax1, ay0), (ax1, ay1), (ax0, ay1)],
                                       close=True, dxfattribs={"layer": "DETAY"})
                    _yaz(msp, dt["harf"], ax1 + 0.5, ay1 + 0.5, YH, kat="DETAY")
        sayfalar.append(doc)
    # 2. dikiş tablosu
    for parca in ([] if kisa else _tablo_sayfalari(tab)):
        doc = _yeni_sayfa(O)
        msp = doc.modelspace()
        _yaz(msp, "DİKİŞ LİSTESİ  -  koordinatlar grubun sınır kutusunun en küçük "
                  "köşesine göre (x; y; z), mm", KENAR + 5, ust - 4, 3.5)
        _tablo_ciz(msp, [TABLO_BAS] + list(parca), KENAR + 5, ust - 9, YH)
        sayfalar.append(doc)
    # 3. detaylar: sayfa başına 4
    for i0 in range(0, len(detaylar), 4):
        doc = _yeni_sayfa(O)
        msp = doc.modelspace()
        hucre = _hucreler(4, ust)
        for dt, R, c in zip(detaylar[i0:i0 + 4], det_r[i0:i0 + 4], hucre):
            w1 = (R.kutu[2] - R.kutu[0]) or 1e-6
            h1 = (R.kutu[3] - R.kutu[1]) or 1e-6
            R.olcek = olcek_sec(min((c[2] - c[0] - 2 * ETIKET_PAY - 6) / w1,
                                    (c[3] - c[1] - 14) / h1))
            _hucreye_koy(msp, R, c, True,
                         f"DETAY {dt['harf']}   ({_ad(dt['gad'])}, {olcek_yazisi(R.olcek)})")
            x0, y0 = R.p(R.kutu[:2])
            x1, y1 = R.p(R.kutu[2:])
            msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                               dxfattribs={"layer": "DETAY"})
            _etiketle(msp, R, dt["dikis"], YH)
        sayfalar.append(doc)
    for i, doc in enumerate(sayfalar, 1):
        _antet(doc.modelspace(), bilgi, i, len(sayfalar))
    return sayfalar


def pdf_yaz(sayfalar, yol):
    """Sayfaları tek PDF'e basar: A3 yatay, 1:1 (kâğıt mm)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.backends.backend_pdf as bpdf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import (Configuration, ColorPolicy,
                                             BackgroundPolicy)
    W, H = KAGIT
    os.makedirs(os.path.dirname(os.path.abspath(yol)) or ".", exist_ok=True)
    gec = yol + ".yeni"
    ayar = Configuration(color_policy=ColorPolicy.COLOR,
                         background_policy=BackgroundPolicy.WHITE,
                         lineweight_scaling=1.0)
    with bpdf.PdfPages(gec) as pdf:
        for doc in sayfalar:
            fig = plt.figure(figsize=(W / 25.4, H / 25.4))
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_axis_off()
            Frontend(RenderContext(doc), MatplotlibBackend(ax), config=ayar
                     ).draw_layout(doc.modelspace(), finalize=False)
            ax.set_xlim(0, W)
            ax.set_ylim(0, H)
            ax.set_aspect("equal")
            fig.set_size_inches(W / 25.4, H / 25.4)
            pdf.savefig(fig, facecolor="white")
            plt.close(fig)
    os.replace(gec, yol)
    return yol


# ------------------------------------------------------------ toplu
def dosya_adi(ad, kullanilan):
    """'<grup adı>_kaynak.pdf'; aynı ad ikinci kez gelirse _2, _3."""
    import re
    kok = re.sub(r"[^\w\-]+", "_", str(ad or "KAYNAK")).strip("_")[:80] or "KAYNAK"
    a, n = kok, 1
    while a.lower() in kullanilan:
        n += 1
        a = f"{kok}_{n}"
    kullanilan.add(a.lower())
    return a + "_kaynak.pdf"


def kaynak_resimleri(on, kayit, komp, agac, satirlar, log=print, iptal=None):
    """Bütün kaynaklı alt grupların kaynak resimleri: KAYNAK/<grup>_kaynak.pdf.
    Artık karşılığı olmayan eski *_kaynak.pdf dosyaları silinir (yalnız bu
    klasörde, yalnız bu programın ürettiği adlar). Döner: dosya listesi."""
    import pf3_olcu as O
    import pf7_is as IS
    log("  kaynaklı alt gruplar bulunuyor (dikişlerin değdiği parçalar)...")
    gruplar = kaynakli_gruplar(kayit, komp, agac, log=log)
    if not gruplar:
        return []
    kl = IS.alt_klasor(on, "kaynak", olustur=True)
    kullanilan, yazilan = set(), []
    for i, g in enumerate(gruplar, 1):
        if iptal and iptal():
            log("! iptal edildi")
            return yazilan
        ad = dosya_adi(g["dugum_ad"], kullanilan)
        try:
            d = kaynak_resmi(O, kayit, komp, g, satirlar, os.path.join(kl, ad), log=log)
            yazilan.append(ad)
            gizli = sum(1 for x in d if not x.get("gorunur"))
            log(f"  KAYNAK/{ad}  {len(d)} dikiş"
                + (f", {len(set(x.get('detay') for x in d) - {None})} detay"
                   if any(x.get("detay") for x in d) else "")
                + (f", {gizli} dikiş hiçbir yönden net görünmüyor (tabloda)" if gizli else ""))
        except Exception as ex:
            log(f"  KAYNAK/{ad}: HATA {ex}"[:160])
    for a in os.listdir(kl):
        if a.lower().endswith("_kaynak.pdf") and a not in yazilan:
            try:
                os.remove(os.path.join(kl, a))
            except OSError:
                pass
    log(f"  KAYNAK/  {len(yazilan)} kaynak resmi (PDF)")
    return yazilan
