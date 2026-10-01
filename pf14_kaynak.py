# -*- coding: utf-8 -*-
"""KAYNAK RESMİ: her kaynaklı alt grup için dikişlerin yeri, ölçüsü, sembolü.

Montaj ağacında içinde dikiş yaprağı olan en yakın düğüm bir KAYNAKLI
GRUPTUR ("K0 CIVATA LAMASI_2_MONTAJ", "K0 ON PANEL KAYNAK_SAG"). Her grup
kendi resmini alır:

  * PARÇALAR: dikişe fiziksel olarak DEĞEN katılar (0,2 mm; ikinci parça
    bulunamazsa CAD boşluğu payı 2,5 mm). Dikişin grubu bu parçaların
    montaj ağacındaki ortak üst düğümüdür.
  * GENEL GÖRÜNÜŞ: yalnız DÖRT İZOMETRİK - üstten ve alttan, ön-sağ ve
    ön-sol; sayfada biri üstte biri altta. Dikişler kırmızı. Dikişler
    yakınlığa göre BÖLGELERE ayrılır; her bölge TEK harf (A..Z), göründüğü
    izometriklerde daire içinde işaretli.
  * DETAYLAR: bölge bölge, büyütülmüş; önce İZOMETRİK (dik görünüşte bir
    sacın iki yüzündeki dikiş aynı çizgiye düşer, içte mi dışta mı
    anlaşılmaz). Bölge birden çok yönden gösterilirse A1, A2 ...
  * GÖRÜNÜRLÜK ÖLÇÜLÜR: dikiş boyunca 5 noktadan göze doğru ışın (parça
    ağında): ışın bir parçaya çarpıyorsa o noktada dikiş gizlidir. Her dikiş
    NET göründüğü TEK detayda işaretlenir.
  * SEMBOL (ISO 2553): ok + referans çizgisi + köşe kaynağı üçgeni +
    "a2" (boğaz) + "25" (boy) + K numarası balonu.
  * KONUM ÖLÇÜSÜ YALNIZ SIRALI KAYNAKTA: tek duran kaynağın yeri
    parçanın kesiminden, yarığından, köşesinden zaten bellidir; ölçü
    verilmez. Aynı parçaları aynı eksen üzerinde art arda birleştiren
    kaynaklarda (zincir) ilkine kenardan başlangıç (tam kenardan /
    köşeden başlıyorsa yok), sonrakilere bir öncekiyle ARA ölçüsü.
    İzometrikte eksen boyunca, gerçek değer. Küçük üründe (gabari
    < KUCUK_URUN) resimde ölçü yok, listede var.
  * KAYNAK LİSTESİ: K no, tip, a, z, boy, konum (- / kenardan / K8 + 51),
    başlangıç / bitiş koordinatı (grubun sınır kutusunun köşesine göre,
    mm), birleştirdiği pozlar, detay. Resim ne kadar kalabalık olursa
    olsun ölçü ve yer buradan KESİN okunur.
  * ÖLÇEK serbesttir (1:13 gibi): görünüş sayfayı doldurur, ölçüler
    gerçek değerle yazılır.

Kaynak YÖNTEMİ (gazaltı, TIG) geometriden anlaşılmaz; yazılmaz.
"""
from __future__ import annotations

import math
import os
from collections import Counter

import pf8_tani as TN
import pf9_excel as XL

DEGME_TOL = 0.2            # mm: dikişe bu kadar yakın katı onun parçasıdır
BOSLUK_TOL = 2.5           # mm: ikinci parça bulunamazsa CAD boşluğu payı
GORUNUR_ORAN = 0.6         # dikiş noktalarının bu kadarı görünüyorsa "net"
# izometrik yönler: göz yönü; X ekseni yatay (-b, a, 0) -> Z hep yukarı
ISO_YON = {"ISO1": (1.0, -1.0, 1.0), "ISO2": (-1.0, 1.0, 1.0),
           "ISO3": (-1.0, -1.0, 1.0), "ISO4": (1.0, 1.0, 1.0),
           "ISO5": (1.0, -1.0, -1.0), "ISO6": (-1.0, 1.0, -1.0),
           "ISO7": (-1.0, -1.0, -1.0), "ISO8": (1.0, 1.0, -1.0)}
ISO_GOR = {k: (g, (-g[1], g[0], 0.0)) for k, g in ISO_YON.items()}
GOR_AD = {"ON": "ÖN", "UST": "ÜST", "SAG": "SAĞ", "ARKA": "ARKA", "SOL": "SOL",
          "ALT": "ALT", "ISO1": "İZOMETRİK ÖN-SAĞ", "ISO2": "İZOMETRİK ARKA-SOL",
          "ISO3": "İZOMETRİK ÖN-SOL", "ISO4": "İZOMETRİK ARKA-SAĞ",
          "ISO5": "İZOMETRİK ALTTAN ÖN-SAĞ", "ISO6": "İZOMETRİK ALTTAN ARKA-SOL",
          "ISO7": "İZOMETRİK ALTTAN ÖN-SOL", "ISO8": "İZOMETRİK ALTTAN ARKA-SAĞ"}


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


class IptalEdildi(Exception):
    """Kullanıcı İPTAL dedi."""


def _dur(iptal):
    if iptal and iptal():
        raise IptalEdildi()


def kaynakli_gruplar(kayit, komp, agac=None, log=print, ilerleme=None, iptal=None):
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
    for n, j in enumerate(dikisler):
        _dur(iptal)
        if ilerleme:
            ilerleme(n, len(dikisler))
        dg = degen_katilar(kayit[j][1], parca_aday, kayit, kutular, sinif)
        if len(dg) < 2:
            dg = dg + ikinci_parca(kayit[j][1], parca_aday, kayit, kutular, dg)
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


def ikinci_parca(sh, adaylar, kayit, kutular, degen):
    """Kaynak İKİ parçayı birleştirir. CAD'de dikiş gövdesi parçaya her
    zaman tam oturtulmaz: kasa modelinde yakıt dolum braketini traverse
    bağlayan üç dikişten biri iki parçaya değiyor, biri traversten 1,1 mm,
    biri braketten 2 mm uzakta çizilmiş. DEGME_TOL (0,2) ile bu dikişler
    tek parçaya (ya da hiçbir parçaya) bağlanıyor, üç ayrı gruba
    dağılıyordu ve konumu "?" çıkıyordu.

    Değen parça ikiden azsa eksik olan, BOSLUK_TOL içindeki EN YAKIN
    parça(lar)dan tamamlanır (kesin uzaklık). Döner: eklenecek katılar."""
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    kb = TN._kutu(sh)
    aday = []
    for j in adaylar:
        if j in degen or not _kutu_yakin(kb, kutular[j], BOSLUK_TOL):
            continue
        try:
            d = BRepExtrema_DistShapeShape(sh, kayit[j][1])
            if d.IsDone() and d.Value() <= BOSLUK_TOL:
                aday.append((d.Value(), j))
        except Exception:
            continue
    aday.sort()
    return [j for _v, j in aday[:2 - len(degen)]]


# ------------------------------------------------------------ konum
def _bacak(dikis_sh, parca_sh, tol=None):
    """Dikişin parçaya oturan BACAK yüzü (düzlem): (nokta, normal).

    Yüzün tek bir noktasına (ağırlık merkezine) bakmak yetmiyordu: ince
    sacın kenarındaki dikişte bacak sacdan geniştir, ortası sacın dışına
    düşer; şasede "?" konumların çoğu buydu. Yüz üzerine 5 x 5 nokta
    serpilir; en az üçte biri parçaya tol içinde değen düzlemlerin en
    genişi bacaktır."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE, TopAbs_IN
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt2d
    tol = DEGME_TOL if tol is None else tol
    # Değme, parçanın dikişe YAKIN yüzlerine izdüşümle denetlenir; katı
    # sınıflayıcı büyük sacda nokta başına ~80 ms sürüyordu (250 dikişli
    # şasi 5 dk -> 20 dk üstü).
    yz = _kutu_yuzleri(parca_sh, TN._kutu(dikis_sh), tol)
    if not yz:
        return None
    en = None
    ex = TopExp_Explorer(dikis_sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        s = BRepAdaptor_Surface(f)
        if s.GetType() != GeomAbs_Plane:
            continue
        u0, u1, v0, v1 = BRepTools.UVBounds_s(f)
        pts = []
        for a in range(1, 6):
            for b in range(1, 6):
                u, v = u0 + (u1 - u0) * a / 6.0, v0 + (v1 - v0) * b / 6.0
                if BRepClass_FaceClassifier(f, gp_Pnt2d(u, v), 1e-7).State() == TopAbs_IN:
                    q = s.Value(u, v)
                    pts.append((q.X(), q.Y(), q.Z()))
        if not pts:
            continue
        deg = sum(1 for q in pts if _yuzeyde(q, yz, tol))
        if deg < max(1, len(pts) / 3.0):
            continue                       # yüz parçaya oturmuyor
        g = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, g)
        if en is None or g.Mass() > en[0]:
            ax = s.Plane().Axis()
            p, n = ax.Location(), ax.Direction()
            en = (g.Mass(), (p.X(), p.Y(), p.Z()), (n.X(), n.Y(), n.Z()))
    return None if en is None else en[1:]


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


def _kutu_yuzleri(sh, kutu, tol):
    """Katının, verilen kutuya tol'dan yakın yüzleri: [(yüzey, sınıflayıcı)]."""
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
        if _kutu_yakin(TN._kutu(f), kutu, tol + 0.5):
            out.append((BRep_Tool.Surface_s(f), BRepTopAdaptor_FClass2d(f, 0.05)))
    return out


def _bosluk(dikis_sh, parca_sh, en_cok):
    """Dikişin köşelerinin parça yüzeyine en küçük uzaklığı (en_cok'a
    kadar; daha uzaksa None). CAD'de dikiş parçaya tam oturtulmamışsa
    boşluk budur."""
    from OCP.BRep import BRep_Tool
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.TopAbs import TopAbs_OUT, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt2d
    yz = _kutu_yuzleri(parca_sh, TN._kutu(dikis_sh), en_cok)
    en = None
    ex = TopExp_Explorer(dikis_sh, TopAbs_VERTEX)
    while ex.More():
        q = BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current()))
        ex.Next()
        for srf, cls in yz:
            pr = GeomAPI_ProjectPointOnSurf(q, srf)
            if pr.NbPoints() == 0 or pr.LowerDistance() > en_cok:
                continue
            u_, v_ = pr.LowerDistanceParameters()
            if cls.Perform(gp_Pnt2d(u_, v_)) != TopAbs_OUT:
                d_ = pr.LowerDistance()
                en = d_ if en is None else min(en, d_)
    return en


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
    if len(parca_sh) > 2:
        # üçüncü parça dikişin ucuna değiyor olabilir: bacağı OTURAN iki
        # parça birleştirilen parçalardır; iki taneden fazlaysa belirsiz
        bc = [(_bacak(d["sh"], sh), sh) for sh in parca_sh]
        bc = [t for t in bc if t[0] is not None]
        if len(bc) != 2:
            return None
        parca_sh = [sh for _b, sh in bc]
    if len(parca_sh) != 2:
        return None
    bc = [_bacak(d["sh"], sh) for sh in parca_sh]
    bosluk = 0.0
    for i_, sh in enumerate(parca_sh):
        if bc[i_] is None:
            # CAD boşluğu: dikiş parçaya 0,27 mm uzak çizilmiş olabilir;
            # ölçülen boşluk kadar payla bir kez daha (en çok BOSLUK_TOL)
            g_ = _bosluk(d["sh"], sh, BOSLUK_TOL)
            if g_ is not None:
                bosluk = max(bosluk, g_)
                bc[i_] = _bacak(d["sh"], sh, g_ + DEGME_TOL)
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
    tol = 0.3 + bosluk                     # kaynakta alt-mm hassasiyet aranmaz
    yz = [_hat_yuzleri(sh, k, u, tol) for sh in parca_sh]

    def ic(t):
        p = tuple(k + u * t)
        return all(_yuzeyde(p, y, tol) for y in yz)
    if not ic(tm):                         # kök çizgisi parçalarda değil
        return None
    T0, T1 = _sinir(ic, tm, -1), _sinir(ic, tm, +1)
    if T0 is None or T1 is None or T1 - T0 < 0.5 * (w1 - w0):
        return None
    # kök çizgisi dikişin kendi uçlarından geçmeli (bacak yüzü yanlış
    # seçildiyse çizgi kayar): değilse sonuç verilmez
    z = (d["olcu"].get("a_mm") or 2.0) * math.sqrt(2)
    for p_, w_ in ((d["p0"], None), (d["p1"], None)):
        q_ = np.array(p_)
        r_ = q_ - k - u * float((q_ - k) @ u)
        if np.linalg.norm(r_) > max(3.0, 2.0 * z):
            return None
    s0, s1 = w0 - T0, T1 - w1
    # dikiş ucu parça kenarını geçebilir (kenarı döner) ya da kenara bir-iki
    # mm kala biter: atölyede ikisi de "uçtan başlar"
    if min(s0, s1) < UCTAN_PAY:
        return {"deger": 0, "birlesme": (tuple(k + u * T0), tuple(k + u * T1))}
    if s0 <= s1:
        uc, bas, v = T0, w0, s0
    else:
        uc, bas, v = T1, w1, s1
    # tam mm: kaynakta ondalık yok (atölye ölçüsü)
    return {"deger": XL.tam(v), "uc": tuple(k + u * uc), "bas": tuple(k + u * bas),
            "birlesme": (tuple(k + u * T0), tuple(k + u * T1))}


ZINCIR_TOL = 1.5           # mm: sıralı kaynakların eksenleri bu kadar içinde aynı çizgi
KUCUK_URUN = 300.0         # mm: gabarisi bundan küçük grupta resimde konum ölçüsü yok


def zincirler(dikisler):
    """SIRALI KAYNAKLAR: aynı parçaları AYNI EKSEN üzerinde art arda
    birleştiren kaynaklar (iki sacın uzun birleşiminde 40 mm kaynak,
    100 mm boşluk, 40 mm kaynak ...). Döner: [[dikiş, ...]] (eksen
    boyunca sıralı, en az iki).

    Kullanıcı: "çoğu kaynağın yeri zaten belli (parçanın kesim yerinde, ya
    da yarıkta, köşede); ölçü gereksiz. İki parça uzunlamasına ya da
    genişlemesine art arda kaynaklanıyorsa pozisyon önemli: başlangıç
    ölçüsü (tam kenardan / köşeden başlamıyorsa) ve ara ölçüler." Tek
    duran kaynağa bu yüzden konum ölçüsü verilmez.

    Aynı eksen: yönler paralel, eksenler 1,5 mm içinde aynı çizgi ve
    eksen boyunca ÜST ÜSTE BİNMİYORLAR. Bir sacın iki yüzündeki yan yana
    kaynaklar (eksenleri sac kalınlığı kadar ayrık, boyları aynı aralıkta)
    zincir değildir; ilk denemede öyle sayılıp "K2 + 0" yazılıyordu."""
    kume = {}
    for d in dikisler:
        if len(d.get("degen") or ()) >= 2:
            kume.setdefault(frozenset(d["degen"]), []).append(d)
    out = []
    for ds in kume.values():
        ata = list(range(len(ds)))

        def bul(i):
            while ata[i] != i:
                ata[i] = ata[ata[i]]
                i = ata[i]
            return i
        def aralik(d, u, o):
            t = [sum((p[k] - o[k]) * u[k] for k in range(3)) for p in (d["p0"], d["p1"])]
            return min(t), max(t)
        for i, a in enumerate(ds):
            for j in range(i + 1, len(ds)):
                b = ds[j]
                if abs(sum(a["yon"][k] * b["yon"][k] for k in range(3))) < 0.99:
                    continue
                v = [b["orta"][k] - a["orta"][k] for k in range(3)]
                t = sum(v[k] * a["yon"][k] for k in range(3))
                r = math.sqrt(max(0.0, sum(x * x for x in v) - t * t))
                if r > ZINCIR_TOL:
                    continue
                (a0, a1), (b0, b1) = aralik(a, a["yon"], a["orta"]), aralik(b, a["yon"], a["orta"])
                if min(a1, b1) - max(a0, b0) > -1.0:
                    continue               # üst üste biniyor: yan yana kaynak
                ata[bul(j)] = bul(i)
        gr = {}
        for i, d in enumerate(ds):
            gr.setdefault(bul(i), []).append(d)
        for z in gr.values():
            if len(z) < 2:
                continue
            u = z[0]["yon"]
            o = z[0]["orta"]

            def t_(p):
                return sum((p[k] - o[k]) * u[k] for k in range(3))
            z.sort(key=lambda d: t_(d["orta"]))
            out.append(z)
    return out


def _zincir_ara(z):
    """Zincir eksen boyunca sıralıyken her kaynağın başı/sonu ve bir
    öncekiyle arası (tam mm). Kaynağın p0'ı zincir yönünde BAŞI olur."""
    u = z[0]["yon"]
    if sum((z[-1]["orta"][k] - z[0]["orta"][k]) * u[k] for k in range(3)) < 0:
        u = tuple(-x for x in u)
    o = z[0]["orta"]

    def t_(p):
        return sum((p[k] - o[k]) * u[k] for k in range(3))
    for d in z:
        if t_(d["p1"]) < t_(d["p0"]):
            d["p0"], d["p1"] = d["p1"], d["p0"]
    for i, d in enumerate(z):
        d["zincir_sira"] = i
        d["ara"] = None
        if i:
            on = z[i - 1]
            g = max(0.0, t_(d["p0"]) - t_(on["p1"]))
            d["ara"] = {"deger": XL.tam(g), "a": on["p1"], "b": d["p0"], "onceki": on}


def _eksen_t(z):
    """Zincir yönünde (ilk kaynağın başından son kaynağın sonuna) konum."""
    a, b = z[0]["p0"], z[-1]["p1"]
    L = math.dist(a, b) or 1.0
    u = [(b[k] - a[k]) / L for k in range(3)]
    return lambda p: sum((p[k] - a[k]) * u[k] for k in range(3))


def _kenara_uzak(z, birlesme):
    """Zincirin son kaynağının sonundan birleşme çizgisinin o yandaki
    ucuna uzaklık (mm)."""
    t = _eksen_t(z)
    return max(t(q) for q in birlesme) - t(z[-1]["p1"])


def _simetrik_zincirler(zin, tol=1.5):
    """Aynı düzendeki paralel zincirler (sacın karşılıklı iki kenarı: boylar
    ve aralar aynı, kaynaklar eksen boyunca aynı yerlerde). Ölçüler
    numarası küçük olanda verilir; öbürünün her kaynağı d["sim"] =
    karşılığı, resimde "SİM." notu (kullanıcı: alt kenar üsttekinin
    simetriği, ölçü iki kez yazılmaz)."""
    def no(d):
        try:
            return int(str(d.get("no", "K0"))[1:])
        except ValueError:
            return 0
    bitti = set()
    for i, a in enumerate(zin):
        for b in zin[i + 1:]:
            if len(a) != len(b) or id(b) in bitti or id(a) in bitti:
                continue
            if abs(sum(a[0]["yon"][k] * b[0]["yon"][k] for k in range(3))) < 0.99:
                continue
            t = _eksen_t(a)
            ia = [sorted((t(d["p0"]), t(d["p1"]))) for d in a]
            ib = sorted(sorted((t(d["p0"]), t(d["p1"]))) for d in b)
            if not all(abs(x[0] - y[0]) <= tol and abs(x[1] - y[1]) <= tol
                       for x, y in zip(sorted(ia), ib)):
                continue
            asil, kopya = (a, b) if no(a[0]) <= no(b[0]) else (b, a)
            ta = _eksen_t(asil)
            es = sorted(asil, key=lambda d: ta(d["orta"]))
            for d in sorted(kopya, key=lambda d: ta(d["orta"])):
                d["sim"] = es.pop(0)
            ilk = min(kopya, key=no)
            ilk["sim_not"] = f"SİM. {min(asil, key=no)['no']}-{max(asil, key=no)['no']}"
            bitti.add(id(kopya))


def _olcu_ciz(msp, R, a3, b3, deger, yon, h, dolu=None):
    """Eksen boyunca ölçü (kâğıtta; yazı gerçek mm). Çizilemiyorsa False:
    eksen bakışa eğik (dik görünüşte boy kısalır) ya da uç pencere dışı."""
    c = abs(sum(x * y for x, y in zip(yon, R.goz)))
    if c > (0.9 if R.gad in ISO_GOR else 0.25):
        return False
    if R.kirpik:
        x0, y0, x1, y1 = R.kutu
        for p in (a3, b3):
            q = _izdusum(p, R.goz, R.xr)
            if not (x0 <= q[0] <= x1 and y0 <= q[1] <= y1):
                return False
    a, b = R.p3(a3), R.p3(b3)
    L = math.dist(a, b)
    if L < 1.5:
        return False
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = -uy, ux
    if ny < 0 or (abs(ny) < 1e-9 and nx < 0):
        nx, ny = -nx, -ny
    # Yazı başka bir ölçünün yazısına binecekse ölçü dışarı kaydırılır;
    # hiçbir yere sığmıyorsa çizilmez (değer listede). Sıralı kaynakların
    # ara ölçüleri paralel zincirlerde üst üste biniyordu (236 / 70 / 115).
    t_ = str(deger)
    mx0, my0 = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    off = None
    for o_ in (2.4, 4.6, 6.8, -2.4, -4.6, 9.0, -6.8, 11.2, 13.4):
        # yazının merkezi ölçü çizgisinin 1 yazı boyu DIŞINDA; öbür yana
        # (eksi) kaydırılınca da dışında (işaret hatası: kutu yazıdan 2 h
        # uzağa bakıyordu, kabin korumada 105 / 35 çizgiye bindi)
        sg = 1.0 if o_ > 0 else -1.0
        cx, cy = mx0 + nx * (o_ + sg) * h, my0 + ny * (o_ + sg) * h
        yk = max(_en(t_, h) / 2, 0.7 * h)
        kutu_ = (cx - yk - 0.3 * h, cy - yk - 0.3 * h, cx + yk + 0.3 * h, cy + yk + 0.3 * h)
        bos = dolu is None or not any(not (kutu_[2] < k[0] or k[2] < kutu_[0]
                                           or kutu_[3] < k[1] or k[3] < kutu_[1])
                                      for k in dolu)
        # yazı kendi görünüşünün penceresinde kalsın (dışarı kayan ölçü
        # komşu detayın çizgilerine / ölçülerine biniyordu - kabin koruma)
        # ve parçanın çizgisine binmesin (kullanıcı: yazılar parçanın
        # çizimine engel olmamalı)
        pa, pb = R.p(R.kutu[:2]), R.p(R.kutu[2:])
        icinde = (pa[0] <= kutu_[0] and kutu_[2] <= pb[0]
                  and pa[1] <= kutu_[1] and kutu_[3] <= pb[1])
        if bos and icinde and not R.cizgiye_degiyor(kutu_):
            off = o_ * h
            if dolu is not None:
                dolu.append(kutu_)
            break
    if off is None:
        return False
    if off < 0:
        nx, ny, off = -nx, -ny, -off
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
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90 or ang <= -90:
        ang -= 180 if ang > 0 else -180
    mx, my = (a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2
    # Yazı, yeri denetlenen kutunun TAM ORTASINA (orta hizalı) konur.
    # Alttan hizalı yazı okunurluk için 180° çevrilince ölçü çizgisinin iç
    # yanına düşüyordu; denetlenen yerde değildi (kabin korumada 189 / 189
    # ve çizgi üstünde 105, 70 böyle kaldı).
    cx, cy = mx + nx * 1.0 * h, my + ny * 1.0 * h
    e = _yaz(msp, str(deger), cx, cy, h, kat="OLCU")
    try:
        from ezdxf.enums import TextEntityAlignment
        e.set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)
    except Exception:
        pass
    e.dxf.rotation = ang
    return True


def _konum_olcusu(msp, R, d, h, bu_detay=(), dolu=None):
    """Sıralı kaynağın ölçüleri: zincirin ilk kaynağına kenardan başlangıç
    (kenardan / köşeden başlıyorsa yok), sonrakilere bir öncekiyle ARA.
    Ara, iki kaynak da aynı detaydaysa çizilir; değil ise listededir."""
    if d.get("_olcusuz") or d.get("sim"):
        return
    r = d.get("ara")
    if r and not r.get("kenara_kadar") and any(x is r["onceki"] for x in bu_detay):
        _olcu_ciz(msp, R, r["a"], r["b"], r["deger"], d["yon"], h, dolu)
    k = d.get("konum")
    if not k or not k.get("uc") or not k.get("gorunur", True):
        return
    _olcu_ciz(msp, R, k["uc"], k["bas"], XL.tam(k["deger"]), d["yon"], h, dolu)


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
          "ISO5", "ISO6", "ISO7", "ISO8")
# GENEL GÖRÜNÜŞ: bölgeleri tanıtmak için dört izometrik yeter (kullanıcı:
# "izometrik üst sağ-sol, alt sağ-sol yeterli, daha fazla görüntüye gerek
# yok"). Dik görünüşler genel sayfada yok; kaynak bilgisi detaylarda.
GENEL = ("ISO1", "ISO3", "ISO5", "ISO7")
ANA = ("ON", "UST", "SAG", "ISO1")
DETAY_EN_COK = 8          # bir detay görünüşünde en çok dikiş
TABLO_BAS = ("K", "tip", "a", "z", "boy", "konum", "başlangıç (x; y; z)",
             "bitiş (x; y; z)", "birleştirdiği", "detay / görünüş")


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


HARFLER = "ABCDEFGHIJKLMNOPRSTUVYZ"   # bölge adları (Q, W, X yok: Türkçede yok)


def genel_gorunus(O, kutu3):
    """Bölgelerin kümelendiği düzlem: grubun en GENİŞ göründüğü dik görünüş
    (izdüşüm alanı en büyük) - şasede ÜST, dik duran duvarda ÖN. Bu
    düzlemde yakın kaynaklar aynı bölgeye girer; bölge harfleri de bu
    düzlemde soldan sağa, yukarıdan aşağı sıralanır."""
    en = None
    for gad in ("UST", "ON", "SAG"):
        goz, xr = _gorunus(O, gad)
        pts = [_izdusum((a, b, c), goz, xr) for a in (kutu3[0], kutu3[3])
               for b in (kutu3[1], kutu3[4]) for c in (kutu3[2], kutu3[5])]
        alan = ((max(p[0] for p in pts) - min(p[0] for p in pts))
                * (max(p[1] for p in pts) - min(p[1] for p in pts)))
        if en is None or alan > en[0] * 1.05:
            en = (alan, gad)
    return en[1]


def bolgeler(dikisler, goz, xr, L, birlikte=()):
    """Kaynakları genel_gorunus düzleminde yakınlığa göre kümeler; küme
    sayısı harf sayısını (A..Z) aşmayana kadar bölge büyütülür. Bölgeler
    planda soldan sağa, yukarıdan aşağı sıralı döner (A sol üstte).

    birlikte: BÖLÜNMEYECEK kaynak listeleri (sıralı kaynak zincirleri). Ara
    ölçüsü iki kaynak aynı detaydaysa çizilir; zincir bölgelere
    dağılırsa ara ölçüler resimden düşüyordu."""
    for d in dikisler:
        q = _izdusum(d["orta"], goz, xr)
        d["_q"] = (q[0], q[1], 0.0)
    birim, gordu = [], set()
    for z in birlikte:
        z = [d for d in z if id(d) not in gordu]
        if z:
            gordu.update(id(d) for d in z)
            birim.append(z)
    birim += [[d] for d in dikisler if id(d) not in gordu]

    def mrk(g):
        return (sum(d["_q"][0] for d in g) / len(g), sum(d["_q"][1] for d in g) / len(g), 0.0)
    birim = [(mrk(b), b) for b in birim]
    en_cok = max(DETAY_EN_COK, math.ceil(len(dikisler) / (len(HARFLER) - 2)))
    cap = min(max(L / 6.0, 80.0), 300.0)
    while True:
        kalan = sorted(birim, key=lambda t: (t[0][0], -t[0][1]))
        out = []
        while kalan:
            tohum = kalan.pop(0)
            grp = [tohum]
            kalan.sort(key=lambda t: math.dist(t[0], tohum[0]))
            while kalan and sum(len(b) for _, b in grp) + len(kalan[0][1]) <= en_cok:
                m, _b = kalan[0]
                if max(math.dist(m, g[0]) for g in grp) > cap:
                    break
                grp.append(kalan.pop(0))
            out.append([d for _, b in grp for d in b])
        if len(out) <= len(HARFLER) or cap > 4 * L:
            break
        cap *= 1.25
        en_cok += 1
    # okuma sırası: planda yukarıdan aşağı satırlar, satırda soldan sağa
    ys = sorted(mrk(g)[1] for g in out)
    bant = max(cap, (ys[-1] - ys[0]) / 4.0 if ys else 1.0)
    out.sort(key=lambda g: (-round(mrk(g)[1] / bant), mrk(g)[0]))
    return out


def _yaz(msp, t, x, y, h, kat="YAZI"):
    from pf3_olcu import _yaz as yz
    return yz(msp, t, x, y, h, kat=kat)


def _en(t, h):
    return len(str(t)) * 0.72 * h


def _sembol(msp, q, dirsek, taraf, d, h, ek=(), not_=None):
    """ISO 2553 sembolü: ok (dikişe) -> kırılma -> yatay referans çizgisi;
    çizginin ALTINDA (ok tarafı) köşe kaynağı üçgeni, solunda a, sağında
    boy; kırılmada daire = çevre kaynağı; uçta K numarası balonu. Punta:
    daire sembolü."""
    kat = {"layer": "OLCU"}
    x, y = dirsek
    # ek: aynı özellikli yan yana dikişler [(q, d)] - tek sembol, her
    # birine ayrı ok (kullanıcı: bilgiler üst üste binmesin)
    for q_ in [q] + [e[0] for e in ek]:
        msp.add_line(q_, (x, y), dxfattribs=kat)
        ang = math.atan2(y - q_[1], x - q_[0])
        ok_b = 1.2 * h
        msp.add_solid([q_, (q_[0] + ok_b * math.cos(ang + 0.3), q_[1] + ok_b * math.sin(ang + 0.3)),
                       (q_[0] + ok_b * math.cos(ang - 0.3), q_[1] + ok_b * math.sin(ang - 0.3))],
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
    no = _no_yazisi([d["no"]] + [e[1]["no"] for e in ek])
    rx, ry = _balon(no, h)
    bx = x2 + taraf * rx
    if ek:                                 # birden çok numara: basık çerçeve
        msp.add_lwpolyline([(bx - rx, y - ry), (bx + rx, y - ry), (bx + rx, y + ry),
                            (bx - rx, y + ry)], close=True, dxfattribs=kat)
    else:
        msp.add_circle((bx, y), rx, dxfattribs=kat)
    _yaz(msp, no, bx - 0.36 * _en(no, h) / 0.72, y - 0.5 * h, h, kat="OLCU")
    if not_:                               # "SİM. K1-K3": balonun altında, parçadan uzakta
        # referans çizgisinin altındaki a / boy yazısı y - 1,4 h'den aşağı
        # iner: not ondan ve balondan en az yarım yazı boyu aşağıda
        _yaz(msp, not_, bx - _en(not_, h) / 2, min(y - ry, y - 1.6 * h) - 2.2 * h, h,
             kat="OLCU")
    return abs(x2 - x) + 2 * rx


def _balon(no, h):
    """Numara balonunun yarı eni / yarı boyu: tek numara daire, birden
    çok numara ("K12,K14") basık çerçeve - büyük daire alttaki etikete
    biniyordu."""
    if "," in no or "-" in no:
        return _en(no, h) / 2 + 0.6 * h, 1.0 * h
    r = 0.45 * _en(no, h) + 0.6 * h
    return r, r


def _etiket_yuksekligi(uye, h):
    """Bir etiketin referans çizgisinin üstünde / altında kapladığı yer
    (not dahil): (üst, alt)."""
    no = _no_yazisi([d["no"] for _q, d in uye])
    _rx, ry = _balon(no, h)
    alt = max(ry, 1.6 * h)
    if any(e.get("sim_not") and not e.get("_olcusuz") for _q, e in uye):
        alt = max(ry, 1.6 * h) + 3.4 * h
    return max(ry, 0.6 * h), alt


def _no_yazisi(nolar):
    """Balondaki numaralar: ardışıksa "K12-K14", değilse "K3,K7"."""
    try:
        n = sorted(int(x[1:]) for x in nolar)
    except ValueError:
        return ",".join(nolar)
    if len(n) > 2 and n[-1] - n[0] == len(n) - 1:
        return f"K{n[0]}-K{n[-1]}"
    return ",".join(f"K{v}" for v in n)


YAN_YANA = 30.0            # kâğıtta mm: aynı özellikli dikişler bu kadar yakınsa tek sembol
TEK_SEMBOL_EN_COK = 3      # bir sembolden en çok bu kadar ok


def _etiket_anahtari(d):
    o = d["olcu"]
    tip = o.get("tip") or ""
    return (tip.startswith("çevre"), "nokta" in tip,
            XL.tam(o["a_mm"]) if o.get("a_mm") else None,
            XL.tam(o["boy_mm"]) if o.get("boy_mm") else None)


def _yogun(q, adim):
    """Çoklu çizginin noktaları, en çok 'adim' aralıkla (düz çizgi iki
    noktadır; ortası da denetlensin)."""
    out = [q[0]]
    for a, b in zip(q, q[1:]):
        n = max(1, int(math.dist(a, b) / adim))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
                for k in range(1, n + 1)]
    return out


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
        # Kırmızı yalnız DİKİŞİN KENDİ çizgisi. Eskiden bir çizginin yalnız
        # ORTA noktasına bakılıyordu: ortası bir dikişin yanından geçen
        # uzun sac kenarı baştan sona kırmızı çiziliyor, kısa dikiş onun
        # içinde kayboluyordu (kullanıcı). Şimdi çizgi 1 mm'de bir
        # örneklenir; noktalarının çoğu dikişin üstündeyse dikiştir.
        izk = {}
        for q in (kk or {}).get("GORUNEN", []):
            for p in _yogun(q, 0.5):
                izk.setdefault((round(p[0]), round(p[1])), []).append(p)

        def yakin(m):
            return any(math.dist(p, m) <= 0.3 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                       for p in izk.get((round(m[0]) + dx, round(m[1]) + dy), ()))

        def kaynak_mi(q):
            ps = _yogun(q, 1.0)
            return sum(1 for m in ps if yakin(m)) >= 0.6 * len(ps)
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
        self.kirpik = bool(pencere)
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

    def cizgiye_degiyor(self, k):
        """Kâğıttaki k kutusu görünüşün bir çizgisine değiyor mu (yazı
        parçanın üstüne binmesin). Kâğıttaki parçalar bir kez hesaplanıp
        10 mm'lik ızgaraya konur (görünüş yerleştikten sonra çağrılır);
        her denetim yalnız yakın parçalara bakar."""
        if getattr(self, "_izgara_yer", None) != (self.ox, self.oy, self.olcek):
            iz = {}
            for _kat, q in self.cizgi:
                for a, b in zip(q, q[1:]):
                    a, b = self.p(a), self.p(b)
                    for gx in range(int(min(a[0], b[0]) // 10), int(max(a[0], b[0]) // 10) + 1):
                        for gy in range(int(min(a[1], b[1]) // 10),
                                        int(max(a[1], b[1]) // 10) + 1):
                            iz.setdefault((gx, gy), []).append((a, b))
            self._izgara, self._izgara_yer = iz, (self.ox, self.oy, self.olcek)
        bak = set()
        for gx in range(int(k[0] // 10), int(k[2] // 10) + 1):
            for gy in range(int(k[1] // 10), int(k[3] // 10) + 1):
                for ab in self._izgara.get((gx, gy), ()):
                    if id(ab) in bak:
                        continue
                    bak.add(id(ab))
                    if _parca_kutuda(ab[0], ab[1], k):
                        return True
        return False


def _parca_kutuda(a, b, k):
    """(a, b) doğru parçası k dikdörtgenine değiyor mu (Liang-Barsky)."""
    x0, y0 = a
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - k[0]), (dx, k[2] - x0), (-dy, y0 - k[1]), (dy, k[3] - y0)):
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


def _etiket_kutusu(uye, x_dirsek, y, taraf, h, not_):
    """Etiketin (referans çizgisi, a / boy yazıları, balon, not) kâğıtta
    kapladığı dikdörtgen."""
    d = uye[0][1]
    o = d["olcu"]
    tip = o.get("tip") or ""
    sol_t = f"a{XL.tam(o['a_mm'])}" if o.get("a_mm") and "nokta" not in tip else ""
    sag_t = str(XL.tam(o["boy_mm"])) if o.get("boy_mm") and "nokta" not in tip else ""
    Lr = max(12 * h, _en(sol_t, h) + _en(sag_t, h) + 5 * h)
    no = _no_yazisi([e["no"] for _q, e in uye])
    rx, ry = _balon(no, h)
    bx = x_dirsek + taraf * (Lr + rx)
    ust_, alt_ = _etiket_yuksekligi(uye, h)
    xs = [x_dirsek, bx + taraf * rx]
    if not_:
        xs += [bx - _en(not_, h) / 2, bx + _en(not_, h) / 2]
    return (min(xs) - 0.3 * h, y - alt_ - 0.3 * h, max(xs) + 0.3 * h, y + ust_ + 0.3 * h)


def _kesisir(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _etiketle(msp, R, dikisler, h, sayfa_dolu=None):
    """Görünüşün sağına ve soluna, yukarıdan aşağı sıralı etiket sütunu.

    sayfa_dolu: sayfada DOLU yerler (başka detayların görünüşleri ve
    etiketleri). Etiket onlardan birine değecekse aşağı kaydırılır: yan
    yana iki detayın etiket sütunları sayfanın ortasında birbirine
    biniyordu."""
    sayfa_dolu = [] if sayfa_dolu is None else sayfa_dolu
    kendi = None
    x0, y0 = R.p(R.kutu[:2])
    x1, y1 = R.p(R.kutu[2:])
    kendi = (x0, y0, x1, y1)
    x0, y0 = R.p(R.kutu[:2])
    x1, y1 = R.p(R.kutu[2:])
    orta = (x0 + x1) / 2
    # dikiş EKSENİ: ince, kesikli, mavi (dikişin kendisi kırmızı kalsın)
    for d in dikisler:
        msp.add_line(R.p3(d["p0"]), R.p3(d["p1"]), dxfattribs={"layer": "EKSEN"})
    for taraf in (-1, 1):
        ds = [(R.p3(d["ok"]), d) for d in dikisler]
        ds = [(q, d) for q, d in ds if (q[0] >= orta) == (taraf > 0)]
        ds.sort(key=lambda t: -t[0][1])
        # yan yana, aynı özellikli dikişler tek sembol (en çok 3 ok);
        # uzaktakiler ayrı sembol
        gr = []
        for q, d in ds:
            k = _etiket_anahtari(d)
            g = next((g for g in gr if g[0] == k and len(g[1]) < TEK_SEMBOL_EN_COK
                      and math.dist(g[1][0][0], q) <= YAN_YANA), None)
            if g:
                g[1].append((q, d))
            else:
                gr.append((k, [(q, d)]))
        # etiketler üst üste binmesin: her birinin gerçek yüksekliği (balon,
        # SİM. notu) kadar yer ayrılır
        alt_son = y1 + 3.0 * h
        for _k, uye in gr:
            q, d = uye[0]
            ust_, alt_ = _etiket_yuksekligi(uye, h)
            y = min(max(p[1] for p, _ in uye), alt_son - ust_ - 0.8 * h)
            # bilgi parçanın DIŞINDA: kırılma görünüşün kenarından 6 yazı
            # boyu uzakta (kullanıcı: bilgi parçaya karışmasın)
            x_dirsek = (x1 + 6 * h) if taraf > 0 else (x0 - 6 * h)
            not_ = next((e.get("sim_not") for _q, e in uye if e.get("sim_not")
                         and not e.get("_olcusuz")), None)
            # sayfadaki başka bir şeye (öbür detayın görünüşü ya da
            # etiketi) değiyorsa boş yer bulunana kadar aşağı
            for _ in range(400):
                k_ = _etiket_kutusu(uye, x_dirsek, y, taraf, h, not_)
                if not any(_kesisir(k_, b) for b in sayfa_dolu if b != kendi):
                    break
                y -= 0.5 * h
            sayfa_dolu.append(k_)
            alt_son = y - alt_
            _sembol(msp, q, (x_dirsek, y), taraf, d, h, ek=uye[1:], not_=not_)
    dolu = []                              # bu görünüşte yazılan ölçü yazıları
    for d in dikisler:
        _konum_olcusu(msp, R, d, h, dikisler, dolu)


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


def _konum_yazisi(d):
    """Listede konum: tek duran kaynakta "-" (yeri parçadan belli);
    sıralı kaynakta ilk için kenardan başlangıç, sonrakiler için
    bir öncekiyle ara."""
    if d.get("sim"):
        return f"SİM. {d['sim']['no']}"
    r = d.get("ara")
    if r and r.get("kenara_kadar"):
        return "kenara kadar"
    if r:
        return f"{r['onceki']['no']} + {XL.tr(r['deger'], 0)}"
    if "zincir_sira" in d:
        k = d.get("konum") or {}
        if k.get("deger") is None:
            return "?"
        return "kenardan " + XL.tr(XL.tam(k["deger"]), 0) if k["deger"] else "kenardan"
    return "-"


def kaynak_resmi(O, kayit, komp, grup, satirlar, yol, P=None, log=print,
                 ilerleme=None, iptal=None):
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
            # İZOMETRİK ÖNCE: dik görünüşte bir sacın iki yüzündeki ya da
            # arka arkaya duran kaynaklar aynı çizgiye düşer, okunmaz
            # (kullanıcı: "üst üste kaynak çizgisi anlaşılmaz").
            puan = (gor > 0 and gad in ISO_GOR, gor, gad in ANA, boy)
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
            _dur(iptal)
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
    ana = list(GENEL)
    # ---- etiket planı
    detaylar = []                          # [(harf, yön, [dikiş], pencere3B)]
    bolge_l = []
    plan_gad = genel_gorunus(O, gk)
    goz_p, xr_p = _gorunus(O, plan_gad)
    adlar = iter(list(HARFLER) + [f"{a}{b}" for a in HARFLER for b in HARFLER])
    zin = zincirler(dikisler)
    for bolge in bolgeler(dikisler, goz_p, xr_p, L, zin):
        harf = next(adlar)
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
        for d in bolge:
            d["_isin"] = isin
            d["bolge"] = harf
        yonler_ = ata(bolge, isin)
        bolge_l.append({"harf": harf, "k3": k3, "dikis": bolge})
        for m, (gad, bu) in enumerate(yonler_, 1):
            detaylar.append({"harf": harf if len(yonler_) == 1 else f"{harf}{m}",
                             "bolge": harf, "gad": gad, "dikis": bu, "k3": k3,
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
    def adim(oran):
        _dur(iptal)
        if ilerleme:
            ilerleme(min(1.0, max(0.0, oran)))
    adim(0.3)
    kucuk = max(gk[3] - gk[0], gk[4] - gk[1], gk[5] - gk[2]) < KUCUK_URUN
    for z in zin:
        # zincirin BAŞI, kenara yakın ucudur: iki uçtan da konum ölçülür
        uclar = []
        for d in (z[0], z[-1]):
            try:
                uclar.append((konum_hesapla(d, [kayit[j][1] for j in d["degen"]]), d))
            except Exception:
                uclar.append((None, d))
        var = [(k, d) for k, d in uclar if k is not None]
        if var and min(var, key=lambda t: t[0]["deger"])[1] is z[-1]:
            z.reverse()
        _zincir_ara(z)
        bas = next((k for k, d in uclar if d is z[0]), None)
        z[0]["konum"] = bas if bas is not None else {"deger": None}
        # zincirin SONU da kenarda / köşede bitiyorsa son aranın ölçüsü
        # gereksiz: son kaynağın yeri köşeden belli (kullanıcı: "- o -"
        # üçlüsünde yalnız ortadaki ölçülür)
        son = next((k for k, d in uclar if d is z[-1]), None)
        if son and son.get("birlesme") and z[-1].get("ara"):
            if _kenara_uzak(z, son["birlesme"]) < UCTAN_PAY:
                z[-1]["ara"]["kenara_kadar"] = True
    _simetrik_zincirler(zin)
    for n, d in enumerate(dikisler):
        adim(0.3 + 0.3 * n / max(1, len(dikisler)))
        d.setdefault("konum", None)
        d["_olcusuz"] = kucuk
        k = d["konum"] or {}
        if k.get("bas") and math.dist(k["bas"], d["p1"]) < math.dist(k["bas"], d["p0"]):
            d["p0"], d["p1"] = d["p1"], d["p0"]     # başlangıç = ölçülen uç
        if k.get("uc") and d.get("_isin") is not None:
            # ölçünün iki ucu da o görünüşte görünmeli (önde parça yoksa);
            # nokta birleşme köşesinden dikişe doğru biraz içeri alınır
            goz, _ = _gorunus(O, d["gorunus"])
            v = [d["orta"][i] - k["bas"][i] for i in range(3)]
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            ic_ = [x / n * min(0.5, n) for x in v]
            k["gorunur"] = all(d["_isin"].acik_mi(tuple(p[i] + ic_[i] for i in range(3)), goz)
                               for p in (k["uc"], k["bas"]))
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
        tab.append((d["no"], (o.get("tip") or "-").replace("dikiş", "kaynak")[:34],
                    str(XL.tam(o["a_mm"])) if o.get("a_mm") else "-",
                    str(XL.tam(z)) if z else "-",
                    XL.tr(XL.tam(o["boy_mm"]), 0) if o.get("boy_mm") else "-",
                    _konum_yazisi(d),
                    kk_(d["p0"]), kk_(d["p1"]), birl, yer))
    ana_r = [_Resim(O, parca_sh, [d["sh"] for d in dikisler], g) for g in ana]
    det_r = []
    for n, dt in enumerate(detaylar):
        adim(0.6 + 0.25 * n / max(1, len(detaylar)))
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
    # bölge, dikişlerinin en az biri NET göründüğü genel görünüşlerde
    # işaretlenir; hiçbirinde görünmüyorsa en çok göründüğü birinde
    for b in bolge_l:
        say = {}
        for gad in GENEL:
            goz, _ = _gorunus(O, gad)
            say[gad] = sum(1 for d in b["dikis"] if isin_tum is not None
                           and gorunurluk(d, isin_tum, goz)[0] >= GORUNUR_ORAN)
        b["gorunen"] = {g for g, n in say.items() if n} or {max(say, key=say.get)}
    bilgi["genel"] = (bolge_l, ana_r)
    if (P or {}).get("balon"):
        # SUNUM / BALONLU resim: tablo yok, ad yok; kaynak noktaları
        # büyütülmüş dairelerde, ana görünüşe uçan çizgiyle bağlı
        sayfalar = _balon_sayfalari(O, bilgi, detaylar, det_r,
                                    os.path.dirname(os.path.abspath(yol)))
    else:
        sayfalar = _sayfalar(O, bilgi, tab, detaylar, det_r)
    adim(0.9)
    pdf_yaz(sayfalar, yol)
    for d in dikisler:
        d.pop("sh", None)
        d.pop("_ornek", None)
        d.pop("_isin", None)
    return dikisler


# ------------------------------------------------------------ sayfa
KAGIT = (420.0, 297.0)      # A3 yatay, mm
KENAR = 10.0
ANTET_Y = 18.0
YH = 2.5                    # kâğıtta yazı yüksekliği, mm
UCTAN_PAY = 2.0             # dikiş uca bundan yakınsa "uçtan başlar" (0)
KISA_TABLO = 10             # bu kadar dikişe kadar tablo genel görünüş sayfasında
ETIKET_PAY = 60.0           # görünüşün iki yanında etiket sütunu
# ISO 5455 ölçekleri (kâğıt / gerçek)
KATMAN_RENK = {"GORUNEN": 7, "KAYNAK": 1, "OLCU": 5, "YAZI": 7, "CERCEVE": 7,
               "DETAY": 6, "EKSEN": 5, "BOLGE": 6}


def olcek_sec(ideal):
    """ideal'den büyük olmayan en büyük TAM SAYILI ölçek (1:n ya da n:1).

    Kaynak resminde ölçek standart olmak zorunda değil (kullanıcı: "kaynak
    resimlerinde ölçek çok önemli değil; pozisyon, uzunluk ve kaynak
    bilgisi önemli"). Standart ölçeğe (1:10 / 1:20) yuvarlamak görünüşü
    sayfanın yarısına küçültüyordu; 1:13 sayfayı doldurur. Ölçüler zaten
    gerçek değerle yazılır."""
    ideal = max(ideal, 1e-4)
    if ideal >= 1.0:
        return float(min(10, math.floor(ideal * 1.0001)))
    return 1.0 / math.ceil(1.0 / ideal - 1e-6)


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
    for kat in ("DETAY", "EKSEN"):
        try:
            doc.layers.get(kat).dxf.linetype = "KESIK"
        except Exception:
            pass
    doc.layers.get("EKSEN").dxf.lineweight = 13
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
    _yaz(msp, f"adet {bilgi['adet']}   -   {bilgi['dikis']} kaynak, toplam boy "
              f"{XL.tr(XL.tam(bilgi['boy']), 0)} mm", KENAR + 253, KENAR + 10.5, YH)
    _yaz(msp, "a: boğaz, z: kenar boyu (z = a·√2); ölçüler mm", KENAR + 253, KENAR + 3.5,
         YH)
    _yaz(msp, f"SAYFA {no} / {toplam}", W - KENAR - 42, KENAR + 10.5, 3.5)
    import pf7_is as IS
    _yaz(msp, f"Pi3D v{IS.PI3D_SURUM}", W - KENAR - 42, KENAR + 3.5, YH)


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
    if n == 1:                             # tek görünüş: bütün sayfa
        return [(x0, y0, x1, y_ust)]
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


def _sayfalar(O, bilgi, tab, detaylar, det_r):
    """Sayfa listesi (her biri ezdxf belgesi, kâğıt mm): genel görünüş
    (dört izometrik, bölge harfleri), kaynak listesi, bölge detayları."""
    sayfalar = []
    W, H = KAGIT
    ust = H - KENAR - 5
    # kısa liste, az bölgeli grupta genel görünüş sayfasının üstünde
    kisa = len(tab) <= KISA_TABLO and len(bilgi["genel"][0]) <= 4
    sayfalar += _genel_sayfalari(O, bilgi, tab if kisa else None)
    # 2. dikiş tablosu
    for parca in ([] if kisa else _tablo_sayfalari(tab)):
        doc = _yeni_sayfa(O)
        msp = doc.modelspace()
        _yaz(msp, "KAYNAK LİSTESİ  -  koordinatlar grubun sınır kutusunun en küçük "
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
                         f"DETAY {dt['harf']}   -   BÖLGE {dt['bolge']}   "
                         f"({_ad(dt['gad'])}, {olcek_yazisi(R.olcek)})")
            x0, y0 = R.p(R.kutu[:2])
            x1, y1 = R.p(R.kutu[2:])
            msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True,
                               dxfattribs={"layer": "DETAY"})
        # etiketler görünüşlerin HEPSİ yerleştikten sonra: hiçbir etiket
        # öbür detayın görünüşüne ya da etiketine binmesin
        dolu_s = []
        for R in det_r[i0:i0 + 4]:
            a_, b_ = R.p(R.kutu[:2]), R.p(R.kutu[2:])
            dolu_s.append((a_[0], a_[1], b_[0], b_[1]))
            # görünüşün başlığı ("DETAY B2 - BÖLGE B (...)") da dolu
            dolu_s.append((a_[0], b_[1] + 2.0, a_[0] + 130.0, b_[1] + 7.0))
        for dt, R in zip(detaylar[i0:i0 + 4], det_r[i0:i0 + 4]):
            _etiketle(msp, R, dt["dikis"], YH, dolu_s)
        sayfalar.append(doc)
    for i, doc in enumerate(sayfalar, 1):
        _antet(doc.modelspace(), bilgi, i, len(sayfalar))
    return sayfalar


def _cakisik(k, dolu, pay=0.8):
    return any(not (k[2] + pay < b[0] or b[2] + pay < k[0] or k[3] + pay < b[1]
                    or b[3] + pay < k[1]) for b in dolu)


def _genel_sayfalari(O, bilgi, tab=None):
    """GENEL GÖRÜNÜŞ: dört izometrik (üstten ön-sağ, ön-sol; alttan ön-sağ,
    ön-sol). Her bölge, göründüğü görünüşlerde daire içinde TEK harfle,
    bölgenin ortasına kısa bir çizgiyle bağlı. Az bölgeli grupta dördü
    tek sayfada (tablo da üstte); çok bölgelide her biri ayrı sayfada,
    büyük."""
    bolge_l, ana_r = bilgi["genel"]
    W, H = KAGIT
    ust = H - KENAR - 5
    tek_sayfa = len(bolge_l) <= 6
    out = []
    # çok bölgelide sayfa başına İKİ görünüş, biri üstte biri altta
    # (üstten + alttan aynı taraf): ISO1+ISO5 sağ, ISO3+ISO7 sol
    gruplar = [ana_r] if tek_sayfa else [[ana_r[0], ana_r[2]], [ana_r[1], ana_r[3]]]
    for grp in gruplar:
        doc = _yeni_sayfa(O)
        msp = doc.modelspace()
        y_h = ust - 8
        if tab is not None and not out:
            _, th = _tablo_ciz(msp, [TABLO_BAS] + list(tab), KENAR + 5, ust - 9, YH)
            y_h = ust - 9 - th - 4
        _yaz(msp, "GENEL GÖRÜNÜŞ  -  bölgeler (harf); her bölgenin kaynakları DETAY "
                  "sayfalarında (A, B1, B2 ...)", KENAR + 5, ust - 4, 3.5)
        if tek_sayfa:
            hucre = _hucreler(len(grp), y_h)
        else:
            x0, x1, y0 = KENAR + 5, W - KENAR - 5, KENAR + ANTET_Y + 5
            hh = (y_h - y0) / 2
            hucre = [(x0, y_h - hh, x1, y_h), (x0, y0, x1, y_h - hh)]
        s_ = olcek_sec(min(min((c[2] - c[0] - 16) / max(R.kutu[2] - R.kutu[0], 1e-6),
                               (c[3] - c[1] - 16) / max(R.kutu[3] - R.kutu[1], 1e-6))
                           for R, c in zip(grp, hucre)))
        dolu = []
        r = 3.0
        for R, c in zip(grp, hucre):
            R.olcek = s_
            _hucreye_koy(msp, R, c, False, f"{_ad(R.gad)}   ({olcek_yazisi(s_)})")
            for b in bolge_l:
                if R.gad not in b["gorunen"]:
                    continue
                pts = [R.p3(d["orta"]) for d in b["dikis"]]
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                for dx, dy in ((0, 0), (0, 7), (0, -7), (7, 0), (-7, 0), (7, 7), (-7, -7),
                               (7, -7), (-7, 7), (0, 14), (0, -14), (14, 0), (-14, 0),
                               (14, 14), (-14, -14), (14, -14), (-14, 14)):
                    kk = (cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r)
                    if not _cakisik(kk, dolu, 0.6):
                        break
                dolu.append(kk)
                mx, my = cx + dx, cy + dy
                if (dx, dy) != (0, 0):
                    n = math.hypot(dx, dy)
                    msp.add_line((cx, cy), (mx - dx / n * r, my - dy / n * r),
                                 dxfattribs={"layer": "BOLGE"})
                msp.add_circle((mx, my), r, dxfattribs={"layer": "BOLGE"})
                e = _yaz(msp, b["harf"], mx, my, 3.2 if len(b["harf"]) == 1 else 2.3,
                         kat="BOLGE")
                try:
                    from ezdxf.enums import TextEntityAlignment
                    e.set_placement((mx, my), align=TextEntityAlignment.MIDDLE_CENTER)
                except Exception:
                    pass
        out.append(doc)
    return out


# ------------------------------------------------------------ balonlu (sunum) resim
BALON_R = 33.0             # büyütülmüş kaynak dairesinin yarıçapı (kâğıt mm)
BALON_SAYFA = 8            # sayfa başına en çok balon
BALON_YH = 2.0             # balon etiketlerinin yazı boyu
BALON_ETIKET = 44.0        # dairenin dış yanında sembol için ayrılan şerit (mm)


def _daire_kesisim(a, b, c, r):
    """a-b doğru parçasının c merkezli r yarıçaplı daireyle kesişim
    parametreleri (0..1), küçükten büyüğe."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = a[0] - c[0], a[1] - c[1]
    A = dx * dx + dy * dy
    if A < 1e-12:
        return []
    B = 2 * (fx * dx + fy * dy)
    C = fx * fx + fy * fy - r * r
    disk = B * B - 4 * A * C
    if disk < 0:
        return []
    k = math.sqrt(disk)
    return sorted(t for t in ((-B - k) / (2 * A), (-B + k) / (2 * A)) if 0.0 < t < 1.0)


def _daire_kirp(q, c, r):
    """Çoklu çizginin daire İÇİNDE kalan parçaları."""
    def ara(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    def icte(p):
        return math.dist(p, c) <= r
    out, cur = [], []
    for a, b in zip(q, q[1:]):
        ia, ib = icte(a), icte(b)
        if ia and ib:
            if not cur:
                cur = [a]
            cur.append(b)
            continue
        ts = _daire_kesisim(a, b, c, r)
        if ia and not ib:
            if not cur:
                cur = [a]
            cur.append(ara(a, b, ts[0]) if ts else b)
            out.append(cur)
            cur = []
        elif ib and not ia:
            cur = [ara(a, b, ts[-1]) if ts else a, b]
        elif len(ts) == 2:
            out.append([ara(a, b, ts[0]), ara(a, b, ts[1])])
    if cur:
        out.append(cur)
    return [w for w in out if len(w) > 1]


def _balon_yuvalari(n):
    """n balon için sayfadaki daire merkezleri ve ana görünüşün kutusu.
    Balonlar sayfanın sol / sağ sütununda (üçer), 7-8 balonda altta iki
    tane daha; ana görünüş ortada kalan alanda."""
    W, H = KAGIT
    R = BALON_R
    ust = H - KENAR - 24.0                 # üstte logo şeridi
    alt = KENAR + 8.0
    sol, sag = KENAR + 4.0 + BALON_ETIKET + R, W - KENAR - 4.0 - BALON_ETIKET - R
    yuva = []
    def dizi(x, k):
        if k <= 0:
            return []
        adim = (ust - alt - 2 * R) / max(1, k - 1) if k > 1 else 0.0
        if k == 1:
            return [(x, (ust + alt) / 2.0)]
        return [(x, ust - R - i * adim) for i in range(k)]
    if n <= 3:
        yuva += dizi(sag, n)
        kutu = (KENAR + 8.0, alt, sag - R - 10.0, ust)
    else:
        n_sag = min(3, n - min(3, n - 3)) if n <= 6 else 3
        n_sol = min(3, n - n_sag) if n <= 6 else 3
        yuva += dizi(sol, n_sol) + dizi(sag, n_sag)
        kalan = n - n_sol - n_sag
        if kalan > 0:
            xs = [W / 2.0 - R - 30.0, W / 2.0 + R + 30.0][:kalan] if kalan == 2 else [W / 2.0]
            yuva += [(x, alt + R) for x in xs]
            kutu = (sol + R + 10.0, alt + 2 * R + 12.0, sag - R - 10.0, ust)
        else:
            kutu = (sol + R + 10.0, alt, sag - R - 10.0, ust)
    return yuva, kutu


def _balon_sayfalari(O, bilgi, detaylar, det_r, klasor):
    """SUNUM resmi: her sayfada ortada bir izometrik genel görünüş (parçalar
    siyah, kaynaklar kırmızı), çevresinde her bölge için BÜYÜTÜLMÜŞ daire
    (bölgenin detay görünüşü daireye kırpılmış, kaynak sembolleri dairenin
    dış yanında), ana görünüşteki küçük daireden büyüğe uçan çizgi.
    Tablo yok, parça / grup adı yok; sol üstte Pi3D logosu."""
    bolge_l, ana_r = bilgi["genel"]
    W, H = KAGIT
    R = BALON_R
    h = BALON_YH
    sayfalar = []
    paketler = [list(range(i, min(i + BALON_SAYFA, len(detaylar))))
                for i in range(0, len(detaylar), BALON_SAYFA)] or [[]]
    try:
        import pf4_pafta as PF
        logo = PF.pi3d_antet_resmi(klasor)
    except Exception:
        logo = None
    for sayfa_no, paket in enumerate(paketler, 1):
        doc = _yeni_sayfa(O)
        doc.filename = os.path.join(klasor, "_balon.dxf")   # IMAGE yolu buradan
        msp = doc.modelspace()
        kat = {"layer": "CERCEVE"}
        msp.add_lwpolyline([(KENAR, KENAR), (W - KENAR, KENAR), (W - KENAR, H - KENAR),
                            (KENAR, H - KENAR)], close=True, dxfattribs=kat)
        # --- logo şeridi (uçan: hafif eğik gölge çizgisiyle) + başlık
        if logo:
            try:
                px = PF.PI3D_ANTET_PX
                hi = 14.0
                wi = hi * px[0] / px[1]
                idef = doc.add_image_def(filename=logo, size_in_pixel=px)
                msp.add_image(image_def=idef, insert=(KENAR + 6.0, H - KENAR - 4.0 - hi),
                              size_in_units=(wi, hi), dxfattribs={"layer": "CERCEVE"})
            except Exception:
                _yaz(msp, "Pi3D", KENAR + 6.0, H - KENAR - 14.0, 8.0)
        _yaz(msp, "KAYNAK RESMİ", W - KENAR - 70.0, H - KENAR - 10.0, 5.0)
        _yaz(msp, f"SAYFA {sayfa_no} / {len(paketler)}", W - KENAR - 70.0,
             H - KENAR - 16.0, 3.0)
        import pf7_is as IS
        _yaz(msp, f"Pi3D v{IS.PI3D_SURUM}", W - KENAR - 30.0, KENAR + 3.0, 2.5)
        yuva, kutu = _balon_yuvalari(len(paket))
        # --- ana görünüş: bu sayfanın bölgelerinin en çok göründüğü izometrik
        bu_harf = {detaylar[i]["bolge"] for i in paket}
        en = None
        for Rm in ana_r:
            n = sum(1 for b in bolge_l if b["harf"] in bu_harf and Rm.gad in b["gorunen"])
            if en is None or n > en[0]:
                en = (n, Rm)
        Rm = en[1] if en else ana_r[0]
        w1 = max(Rm.kutu[2] - Rm.kutu[0], 1e-6)
        h1 = max(Rm.kutu[3] - Rm.kutu[1], 1e-6)
        Rm.olcek = min((kutu[2] - kutu[0]) / w1, (kutu[3] - kutu[1]) / h1)
        wm, hm = Rm.boyut()
        Rm.yerlestir((kutu[0] + kutu[2]) / 2 - wm / 2, (kutu[1] + kutu[3]) / 2 + hm / 2)
        Rm.ciz(msp)
        # --- balonlar
        kucuk = {}                          # bölge -> ana görünüşteki küçük daire
        for (cx, cy), i in zip(yuva, paket):
            dt, Rd = detaylar[i], det_r[i]
            # ana görünüşte küçük daire (bölgenin BÜTÜN kaynakları, bir kez)
            if dt["bolge"] not in kucuk:
                b = next(b for b in bolge_l if b["harf"] == dt["bolge"])
                pts = [Rm.p3(d["orta"]) for d in b["dikis"]]
                ex = [Rm.p3(p) for d in b["dikis"] for p in (d["p0"], d["p1"])]
                mx = sum(p[0] for p in pts) / len(pts)
                my = sum(p[1] for p in pts) / len(pts)
                rs = max(4.0, max(math.dist((mx, my), p) for p in ex) + 2.0)
                msp.add_circle((mx, my), rs, dxfattribs={"layer": "BOLGE"})
                kucuk[dt["bolge"]] = (mx, my, rs)
            mx, my, rs = kucuk[dt["bolge"]]
            # büyük daire (düz çizgi)
            msp.add_circle((cx, cy), R, dxfattribs={"layer": "OLCU"})
            # uçan çizgi: küçük dairenin kenarından büyüğün kenarına
            vx, vy = cx - mx, cy - my
            L_ = math.hypot(vx, vy) or 1.0
            ux, uy = vx / L_, vy / L_
            if L_ > rs + R:
                msp.add_line((mx + ux * rs, my + uy * rs), (cx - ux * R, cy - uy * R),
                             dxfattribs={"layer": "BOLGE"})
            # bölge harfi: büyük dairenin üstüne teğet küçük daire
            hx, hy = cx, cy + R + 4.0
            msp.add_circle((hx, hy), 4.0, dxfattribs={"layer": "BOLGE"})
            e = _yaz(msp, dt["harf"], hx, hy, 3.2 if len(dt["harf"]) == 1 else 2.4, kat="BOLGE")
            try:
                from ezdxf.enums import TextEntityAlignment
                e.set_placement((hx, hy), align=TextEntityAlignment.MIDDLE_CENTER)
            except Exception:
                pass
            # detay görünüşü daireye: kenar 1,3 R'lik kareye sığacak ölçek
            wd = max(Rd.kutu[2] - Rd.kutu[0], 1e-6)
            hd = max(Rd.kutu[3] - Rd.kutu[1], 1e-6)
            Rd.olcek = min(1.3 * R / wd, 1.3 * R / hd)
            wdd, hdd = Rd.boyut()
            Rd.yerlestir(cx - wdd / 2, cy + hdd / 2)
            for kat_, q in Rd.cizgi:
                for w in _daire_kirp([Rd.p(a) for a in q], (cx, cy), R - 0.6):
                    msp.add_lwpolyline(w, dxfattribs={"layer": kat_})
            # kaynak sembolleri dairenin DIŞ yanında: sütuna göre dışa doğru
            taraf = -1 if cx < W / 2 - 1 else 1
            if abs(cx - W / 2) <= R + 10 and cy < H / 2:      # alt sıra: sağa / sola
                taraf = -1 if cx <= W / 2 else 1
            ds = sorted(dt["dikis"], key=lambda d: -Rd.p3(d["ok"])[1])
            n = len(ds)
            for k, d in enumerate(ds):
                q = Rd.p3(d["ok"])
                yy = cy + 0.7 * R - (1.4 * R * k / max(1, n - 1) if n > 1 else 0.7 * R)
                dx_ = math.sqrt(max(0.0, R * R - (yy - cy) ** 2))
                xe = cx + taraf * (dx_ + 3.0)
                # ok dairenin içinden çıkar: kırılma dışarıda, ok ucu kaynakta
                msp.add_line(Rd.p3(d["p0"]), Rd.p3(d["p1"]), dxfattribs={"layer": "EKSEN"})
                _sembol(msp, q, (xe, yy), taraf, d, h)
        sayfalar.append(doc)
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


def kaynak_resimleri(on, kayit, komp, agac, satirlar, log=print, iptal=None,
                     ilerleme=None, balon=False):
    """Bütün kaynaklı alt grupların kaynak resimleri: KAYNAK/<grup>_kaynak.pdf.
    Artık karşılığı olmayan eski *_kaynak.pdf dosyaları silinir (yalnız bu
    klasörde, yalnız bu programın ürettiği adlar). Döner: dosya listesi.

    ilerleme(yapilan, toplam): iş birimi dikiştir - önce gruplama (her
    dikişin değdiği parçalar), sonra çizim (grubun dikiş sayısı kadar);
    böylece büyük grup çizilirken de çubuk ilerler. İptal edilirse o ana
    kadar yazılanlar kalır, eski dosyalar silinmez.

    balon=True: SUNUM resmi (balonlu) - tablo ve ad yok, kaynak noktaları
    büyütülmüş dairelerde; dosya adı G1_kaynak.pdf, G2_... (grup adı
    yazılmaz)."""
    import pf3_olcu as O
    import pf7_is as IS
    n_dikis = sum(1 for k in komp if k["sinif"] == "kaynak" for _ in k["indeks"])
    toplam = max(1, 2 * n_dikis)

    def bildir(y):
        if ilerleme:
            ilerleme(int(min(y, toplam)), toplam)
    log(f"  kaynaklı alt gruplar bulunuyor ({n_dikis} kaynağın değdiği parçalar)...")
    try:
        gruplar = kaynakli_gruplar(kayit, komp, agac, log=log, iptal=iptal,
                                   ilerleme=lambda y, t: bildir(y * n_dikis / max(t, 1)))
    except IptalEdildi:
        log("! iptal edildi")
        return []
    if not gruplar:
        log("  kaynaklı alt grup bulunamadı")
        return []
    log(f"  {len(gruplar)} kaynaklı alt grup; resimler çiziliyor "
        "(büyük grup birkaç dakika sürebilir)")
    kl = IS.alt_klasor(on, "kaynak", olustur=True)
    kullanilan, yazilan = set(), []
    yapilan = n_dikis
    tum_dikis = max(1, sum(len(g["dikis"]) for g in gruplar))
    for i, g in enumerate(gruplar, 1):
        if iptal and iptal():
            log("! iptal edildi")
            return yazilan
        ad = f"G{i}_kaynak.pdf" if balon else dosya_adi(g["dugum_ad"], kullanilan)
        pay = n_dikis * len(g["dikis"]) / tum_dikis
        log(f"  [{i}/{len(gruplar)}] KAYNAK/{ad}  ({len(g['dikis'])} kaynak) çiziliyor...")
        try:
            d = kaynak_resmi(O, kayit, komp, g, satirlar, os.path.join(kl, ad),
                             {"balon": True} if balon else None, log=log, iptal=iptal,
                             ilerleme=lambda o, b=yapilan, p=pay: bildir(b + o * p))
            yazilan.append(ad)
            gizli = sum(1 for x in d if not x.get("gorunur"))
            log(f"        tamam: {len(d)} kaynak"
                + (f", {len(set(x.get('detay') for x in d) - {None})} detay"
                   if any(x.get("detay") for x in d) else "")
                + (f", {gizli} kaynak hiçbir yönden net görünmüyor (tabloda)" if gizli else ""))
        except IptalEdildi:
            log("! iptal edildi")
            return yazilan
        except Exception as ex:
            log(f"  KAYNAK/{ad}: HATA {ex}"[:160])
        yapilan += pay
        bildir(yapilan)
    for a in os.listdir(kl):
        if a.lower().endswith("_kaynak.pdf") and a not in yazilan:
            try:
                os.remove(os.path.join(kl, a))
            except OSError:
                pass
    log(f"  KAYNAK/  {len(yazilan)} kaynak resmi (PDF)")
    return yazilan
