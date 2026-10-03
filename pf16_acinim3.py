"""3B GENEL AÇINIM - büküm eksenleri paralel olmayan (çok yönlü bükülmüş)
sac parçalar.

pf3_olcu.sac_ac tek yönde bükülmüş sacı açar: büküm ekseni Z'ye
döndürülür, her şey XY düzleminde 2B çözülür. Karluna SOL_DIKME gibi
parçalarda bükümler paralel değildir (alt kanalın büküm eksenleri üst
şapka profilininkinden 8,6° dönük, gövde 5° kırık): orada 2B yöntem
duvarları ağaca bağlayamaz. Bu modül aynı işi 3B'de yapar:

  * DUVAR: birbirine kalınlık kadar uzak, aynı yönlü iki düzlem yüz
    kümesi (herhangi bir yönde). Orta düzlemi (n, d) ile tutulur.
  * BÜKÜM: aynı eksen üzerinde, yarıçap farkı kalınlık olan silindir
    çifti (herhangi bir eksen).
  * AĞAÇ: büküm, nötr silindiri orta düzlemine TEĞET olan ve eksen
    boyunca örtüşen iki duvara değer.
  * SERME: kök duvar düzleme olduğu gibi konur. Komşu duvar, büküm
    EKSENİ etrafında büküm açısı kadar döndürülür (iki duvar aynı
    düzleme gelir, teğet çizgileri çakışır), sonra teğet çizgisine dik
    yönde büküm payı (açı x nötr yarıçap) kadar ötelenir. Büküm yüzeyi
    açıyla orantılı serilir (açı x nötr yarıçap). Deliklerin telleri de
    aynı dönüşümden geçer.
  * DENETİM: düzlemdeki alan x kalınlık = hacim (pf3_olcu ile aynı),
    tek parça.

Sonuç pf3_olcu.acilim_kesim ile aynı sözlüktür; ek olarak her bükümde
"cizgi": düzlemdeki büküm ekseni (iki uç noktası) - eğik olabilir."""
from __future__ import annotations
import math
from collections import defaultdict

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRep import BRep_Tool
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS


def _v(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _d(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _c(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _n(a):
    L = math.sqrt(_d(a, a)) or 1.0
    return (a[0] / L, a[1] / L, a[2] / L)


def _s(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _p(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _koseler(f):
    out = []
    ex = TopExp_Explorer(f, TopAbs_VERTEX)
    while ex.More():
        p = BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current()))
        out.append((p.X(), p.Y(), p.Z()))
        ex.Next()
    return out


def _alan(f):
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(f, g)
    return g.Mass()


def _agirlik(f):
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(f, g)
    c = g.CentreOfMass()
    return (c.X(), c.Y(), c.Z())


def _rodrigues(p, m, a, fi):
    """p noktasını (m, a) ekseni etrafında fi kadar döndürür."""
    v = _v(p, m)
    ca, sa = math.cos(fi), math.sin(fi)
    r = _p(_p(_s(v, ca), _s(_c(a, v), sa)), _s(a, _d(a, v) * (1 - ca)))
    return _p(m, r)


# ------------------------------------------------------------- duvarlar
def duvarlar3(sh, t, M, tol=None):
    """Sac duvarları: herhangi yönde, kalınlık kadar aralıklı düzlem
    çiftleri. Döner: [{"n", "d", "yuzler", "alan", "kose", "merkez"}]
    n: orta düzlemin normali (seçilen yüz kümesinden dışa), d: n.x = d."""
    tol = tol or max(0.08, 0.08 * t)
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(sh, TopAbs_FACE, m)
    kume = []                       # (n_kanonik, d, [yüz])
    for i in range(1, m.Extent() + 1):
        f = TopoDS.Face_s(m.FindKey(i))
        ad = BRepAdaptor_Surface(f)
        if ad.GetType() != GeomAbs_Plane:
            continue
        a = _alan(f)
        if a < 1.0:
            continue
        dn = ad.Plane().Axis().Direction()
        n = _n((dn.X(), dn.Y(), dn.Z()))
        if (round(n[0], 6), round(n[1], 6), round(n[2], 6)) < (0, 0, 0):
            n = _s(n, -1.0)
        q = ad.Plane().Location()
        d = _d((q.X(), q.Y(), q.Z()), n)
        # sac KENAR yüzü (kalınlık kadar dar şerit) duvar değildir
        ks = _koseler(f)
        if len(ks) >= 2:
            u1 = _n(_c(n, (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)))
            u2 = _c(n, u1)
            e1 = [_d(k, u1) for k in ks]
            e2 = [_d(k, u2) for k in ks]
            if min(max(e1) - min(e1), max(e2) - min(e2)) <= 1.6 * t:
                continue
        for g in kume:
            if abs(g[0][0] - n[0]) < 1e-4 and abs(g[0][1] - n[1]) < 1e-4 \
                    and abs(g[0][2] - n[2]) < 1e-4 and abs(g[1] - d) < tol / 2:
                g[2].append(f)
                break
        else:
            kume.append((n, d, [f]))
    # aynı düzlemdeki ayrı şeritler ayrı duvar
    parcalar = []
    for n, d, yz in kume:
        for grp in M._bitisik_gruplar(yz):
            parcalar.append({"n": n, "d": d, "yuzler": grp,
                             "alan": sum(_alan(f) for f in grp),
                             "kose": [k for f in grp for k in _koseler(f)]})
    # kalınlık kadar uzak eşini bul
    duvar, kul = [], set()
    for i, a in enumerate(parcalar):
        if i in kul:
            continue
        en = None
        for j, b in enumerate(parcalar):
            if j == i or j in kul or _d(a["n"], b["n"]) < 0.9998:
                continue
            if abs(abs(a["d"] - b["d"]) - t) > tol:
                continue
            # düzlem içinde örtüşüyorlar mı (kutu)
            u1 = _n(_c(a["n"], (1.0, 0.0, 0.0) if abs(a["n"][0]) < 0.9 else (0.0, 1.0, 0.0)))
            u2 = _c(a["n"], u1)
            ka = [(min(_d(k, u1) for k in a["kose"]), max(_d(k, u1) for k in a["kose"]),
                   min(_d(k, u2) for k in a["kose"]), max(_d(k, u2) for k in a["kose"]))]
            kb = [(min(_d(k, u1) for k in b["kose"]), max(_d(k, u1) for k in b["kose"]),
                   min(_d(k, u2) for k in b["kose"]), max(_d(k, u2) for k in b["kose"]))]
            ox = min(ka[0][1], kb[0][1]) - max(ka[0][0], kb[0][0])
            oy = min(ka[0][3], kb[0][3]) - max(ka[0][2], kb[0][2])
            if ox <= 0.5 or oy <= 0.5:
                continue
            puan = ox * oy
            if en is None or puan > en[0]:
                en = (puan, j)
        if en is None:
            continue
        j = en[1]
        b = parcalar[j]
        kul.add(i); kul.add(j)
        sec = a if a["alan"] >= b["alan"] else b      # büyük yüzlü taraf
        dm = (a["d"] + b["d"]) / 2.0
        # normal dışa (seçilen yüzden orta düzleme doğru DEĞİL, dışa)
        n = sec["n"] if sec["d"] >= dm else _s(sec["n"], -1.0)
        kose = sec["kose"]
        duvar.append({"n": n, "d": dm * (1.0 if sec["d"] >= dm else -1.0),
                      "yuzler": sec["yuzler"], "alan": sec["alan"], "kose": kose,
                      "merkez": _s(tuple(sum(k[i] for k in kose) for i in range(3)),
                                   1.0 / len(kose))})
    return duvar


# -------------------------------------------------------------- bükümler
def bukumler3(sh, t, M, tol=None):
    """Eş eksenli, yarıçap farkı kalınlık olan silindir çiftleri."""
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
        dd = c.Position().Direction()
        a = _n((dd.X(), dd.Y(), dd.Z()))
        if (round(a[0], 6), round(a[1], 6), round(a[2], 6)) < (0, 0, 0):
            a = _s(a, -1.0)
        q = c.Position().Location()
        q = (q.X(), q.Y(), q.Z())
        s0 = _d(q, a)
        q0 = _v(q, _s(a, s0))                      # eksenin orijine en yakın noktası
        try:
            aci = abs(ad.LastUParameter() - ad.FirstUParameter())
        except Exception:
            aci = math.pi / 2
        if aci > 0.95 * 2 * math.pi:
            continue                               # tam tur: delik
        key = (round(a[0], 3), round(a[1], 3), round(a[2], 3),
               round(q0[0] / 0.05), round(q0[1] / 0.05), round(q0[2] / 0.05))
        grup[key].append((f, c.Radius(), a, q0))
    out = []
    for lst in grup.values():
        r = [x[1] for x in lst]
        r_ic, r_dis = min(r), max(r)
        if abs((r_dis - r_ic) - t) > tol:
            continue
        taraf = defaultdict(list)
        for f, rr, a, q0 in lst:
            taraf[round(rr, 3)].append((f, _alan(f)))
        en_iyi = max(taraf.values(), key=lambda v: sum(x[1] for x in v))
        a, q0 = lst[0][2], lst[0][3]
        ks = [k for f, _ in en_iyi for k in _koseler(f)]
        sr = [_d(k, a) for k in ks]
        if not sr or max(sr) - min(sr) < 2.0 * t:
            continue                               # köşe yuvarlatması
        out.append({"m": q0, "a": a, "r_ic": r_ic, "yuzler": [f for f, _ in en_iyi],
                    "s": (min(sr), max(sr)), "alan": sum(x[1] for x in en_iyi)})
    return out


def _malzeme_yonu(w, tA, wA, a, t):
    """Teğet çizgisinin hangi yanında duvar malzemesi var? +1: wA yönü
    boş (büküm o yana açılır), -1: -wA boş, None: belirsiz. Duvarın yüz
    telleri (delikler dahil) kendi düzlemine izdüşürülüp nokta-çokgen
    testi yapılır; sınama noktası teğet çizgisinden 1,5 t ötede."""
    if "_halka" not in w:
        n = w["n"]
        u1 = _n(_c(n, (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)))
        u2 = _c(n, u1)
        w["_u"] = (u1, u2)
        w["_halka"] = []
        for f in w["yuzler"]:
            try:
                from pf3_olcu import _yuz_telleri
                dis, ic = _yuz_telleri(f)
            except Exception:
                continue
            w["_halka"].append(([(_d((p.X(), p.Y(), p.Z()), u1), _d((p.X(), p.Y(), p.Z()), u2)) for p in dis],
                                [[(_d((p.X(), p.Y(), p.Z()), u1), _d((p.X(), p.Y(), p.Z()), u2)) for p in q] for q in ic]))
    if not w["_halka"]:
        return None
    u1, u2 = w["_u"]

    def icinde(p3):
        p = (_d(p3, u1), _d(p3, u2))
        for dis, ic in w["_halka"]:
            if _nokta_icinde(p, dis) and not any(_nokta_icinde(p, q) for q in ic):
                return True
        return False
    # bükümün orta noktasında sına
    from pf16_acinim3 import _p as _p_
    orta = tA
    arti = icinde(_p_(orta, _s(wA, 1.5 * t)))
    eksi = icinde(_p_(orta, _s(wA, -1.5 * t)))
    if arti == eksi:
        return None
    return 1.0 if (eksi and not arti) else -1.0


def _nokta_icinde(p, halka):
    x, y = p
    ic = False
    n = len(halka)
    for i in range(n):
        x1, y1 = halka[i]
        x2, y2 = halka[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xk = x1 + (y - y1) * (x2 - x1) / ((y2 - y1) or 1e-12)
            if xk > x:
                ic = not ic
    return ic


# ------------------------------------------------------------------ ağaç
def agac3(duvarlar, bukumler, t, tol=None):
    """Her büküme teğet iki duvar. Döner: (bükümler[ duvar: [{i, tA, sd}] ])"""
    tol = tol or max(0.15, 0.1 * t)
    hedef = t / 2.0
    for b in bukumler:
        b["duvar"] = []
        for i, w in enumerate(duvarlar):
            if abs(_d(w["n"], b["a"])) > 0.05:
                continue                           # eksen duvara paralel değil
            sd = _d(b["m"], w["n"]) - w["d"]       # eksenden orta düzleme imzalı uzaklık
            # Modelde büküm duvara tam teğet olmayabilir (Karluna tel
            # braket: eksen orta düzleme 1 mm, olması gereken 3): kalınlık
            # kadar sapmaya izin verilir, teğet noktası duvarın gerçek
            # düzleminde alınır; hacim denetimi büyük hatayı yine yakalar.
            if abs(abs(sd) - (b["r_ic"] + hedef)) > max(tol, 1.1 * t):
                continue
            # eksen boyunca örtüşme
            sw = [_d(k, b["a"]) for k in w["kose"]]
            ort = min(max(sw), b["s"][1]) - max(min(sw), b["s"][0])
            # Örtüşme kısa olanın en az dörtte biri olmalı: eş düzlemli
            # komşu kanat (alt kanalın flanşı) bükümün ucuna 2 mm
            # değiyordu ve yanlış duvar seçiliyordu (Karluna aynalı dikme).
            kisa = max(1e-6, min(b["s"][1] - b["s"][0], max(sw) - min(sw)))
            if ort < 0.5 or ort < 0.25 * kisa:
                continue
            # teğet çizgisi duvarın KENARINDA mı (büküm ortadan geçmez)
            tA = _v(b["m"], _s(w["n"], sd))
            wA = _n(_c(b["a"], w["n"]))
            # wA: teğet çizgisinden duvarın MALZEMESİ OLMAYAN yöne (büküm
            # oraya açılır). Ağırlık merkezi kuralı levhanın ortasından
            # kesilip bükülmüş dilde (bağlantı braketi) ters düşüyordu:
            # teğetin iki yanındaki noktalardan hangisi duvarın içinde?
            # sınama bükümün eksen boyu ORTASINDA: tA eksenin orijine en
            # yakın noktasından türer, parçanın dışında olabilir
            orta_s = (b["s"][0] + b["s"][1]) / 2.0 - _d(_v(tA, b["m"]), b["a"])
            yon = _malzeme_yonu(w, _p(tA, _s(b["a"], orta_s)), wA, b["a"], t)
            if yon is not None:
                wA = _s(wA, yon)
            elif _d(_v(tA, w["merkez"]), wA) < 0:
                wA = _s(wA, -1.0)
            kw = [_d(k, wA) for k in w["kose"]]
            kenar = max(kw) - _d(tA, wA)           # teğet çizgisi kenardan ne kadar içeride
            # duvar yüzü büküm bölgesine 1-2 kalınlık taşabilir (modelde
            # yüz silindirin altına kadar uzar); düzlemde birleşince
            # çakışan bölge iki kez sayılmaz
            if kenar > 2.2 * t + 0.5:
                # Levhanın ORTASINDAN kesilip bükülmüş dil (Karluna bağlantı
                # braketi): teğet çizgisi dış sınırın içinde ama kesiğin
                # kenarında. Duvar sınırının (delik / kesik köşeleri dahil)
                # büküm boyunca teğet çizgisine değmesi yeter.
                yakin = [k for k in w["kose"]
                         if abs(_d(k, wA) - _d(tA, wA)) <= 0.6 * t
                         and b["s"][0] - t <= _d(k, b["a"]) <= b["s"][1] + t]
                if len(yakin) < 2:
                    continue
                kenar = 0.0
            b["duvar"].append({"i": i, "tA": tA, "sd": sd, "wA": wA,
                               "s_w": (min(sw), max(sw)),
                               "hata": abs(abs(sd) - (b["r_ic"] + hedef)) + abs(kenar)})
        if len(b["duvar"]) > 2:
            # YARIKLA BÖLÜNMÜŞ KANAT: tek büküm hattı üstünde, aynı
            # düzlemde ama eksen boyunca AYRI aralıklarda duran kanat
            # parçaları (Karluna yardımcı şasi: 1920 mm'lik kanat üç
            # parça; kasa yakıt hattı braketi: iki dil). Büküm her kanat
            # parçası için kendi aralığıyla kopyalanır; aralıkları
            # çakışan eş düzlemli adaylarda eski "en iyi çift" kuralı.
            kopya = _bukum_bol(b, duvarlar)
            if kopya:
                b["duvar"] = []
                b["_kopya"] = kopya
                continue
        if len(b["duvar"]) > 2:
            # Aynı düzlemdeki iki şerit (eş düzlemli duvarlar) bir bükümün
            # iki yanı OLAMAZ; en iyi eş düzlemli olmayan çift seçilir.
            b["duvar"].sort(key=lambda d: d["hata"])
            en = None
            for x in range(len(b["duvar"])):
                for y in range(x + 1, len(b["duvar"])):
                    wx, wy = duvarlar[b["duvar"][x]["i"]], duvarlar[b["duvar"][y]["i"]]
                    if abs(_d(wx["n"], wy["n"])) > 0.9999 and abs(wx["d"] - wy["d"]) < 0.5 \
                            and _d(wx["n"], wy["n"]) > 0:
                        continue
                    puan = b["duvar"][x]["hata"] + b["duvar"][y]["hata"]
                    if en is None or puan < en[0]:
                        en = (puan, x, y)
            b["duvar"] = [b["duvar"][en[1]], b["duvar"][en[2]]] if en else []
    out = []
    for b in bukumler:
        if b.get("_kopya"):
            out.extend(b["_kopya"])
        elif len(b["duvar"]) == 2:
            out.append(b)
    return out


def _duzlem_anahtari(w):
    n, d = w["n"], w["d"]
    for c in n:
        if abs(c) > 1e-6:
            if c < 0:
                n, d = _s(n, -1.0), -d
            break
    return (round(n[0], 3), round(n[1], 3), round(n[2], 3), round(d / 0.3))


def _bukum_bol(b, duvarlar):
    """İkiden çok adayı olan bükümü, iki düzlemdeki kanat parçalarına
    göre kopyalara böler. Döner: kopya listesi ya da None (bölünemez)."""
    grup = defaultdict(list)
    for d in b["duvar"]:
        grup[_duzlem_anahtari(duvarlar[d["i"]])].append(d)
    if len(grup) != 2:
        return None
    A, B = grup.values()
    for g in (A, B):                       # aynı düzlemdekiler ayrık aralıklarda olmalı
        g.sort(key=lambda d: d["s_w"][0])
        for x, y in zip(g, g[1:]):
            if y["s_w"][0] < x["s_w"][1] - 0.5:
                return None
    if len(A) == 1 and len(B) == 1:
        return None
    kopya = []
    yuz_s = []
    for f in b["yuzler"]:
        sr = [_d(k, b["a"]) for k in _koseler(f)]
        yuz_s.append((min(sr), max(sr)) if sr else b["s"])
    for x in A:
        for y in B:
            s0 = max(x["s_w"][0], y["s_w"][0], b["s"][0])
            s1 = min(x["s_w"][1], y["s_w"][1], b["s"][1])
            if s1 - s0 < 1.0:
                continue
            yuzler = [f for f, (f0, f1) in zip(b["yuzler"], yuz_s)
                      if min(f1, s1) - max(f0, s0) > 0.5]
            if not yuzler:
                continue
            k = dict(b, s=(s0, s1), yuzler=yuzler, duvar=[dict(x), dict(y)])
            k.pop("_kopya", None)
            kopya.append(k)
    return kopya or None


# ---------------------------------------------------------------- serme
class _Donusum:
    """3B noktayı düzleme taşıyan katı dönüşüm: önce (varsa) eksen
    etrafında dönme + öteleme zinciri, sonra kök duvarın çerçevesi."""
    def __init__(self, adim, cerceve):
        self.adim = adim                # [(m, a, fi, kaydir)] - uygulanma sırasıyla
        self.e1, self.e2, self.e3, self.o = cerceve

    def uygula3(self, p):
        for m, a, fi, kay in self.adim:
            p = _p(_rodrigues(p, m, a, fi), kay)
        return p

    def __call__(self, p):
        q = _v(self.uygula3(p), self.o)
        return (_d(q, self.e1), _d(q, self.e2))

    def yon(self, v):
        """Vektörü (öteleme olmadan) düzleme taşır."""
        for m, a, fi, kay in self.adim:
            v = _v(_rodrigues(v, (0.0, 0.0, 0.0), a, fi), (0.0, 0.0, 0.0))
        return (_d(v, self.e1), _d(v, self.e2))


def _en_kucuk_dikdortgen_acisi(w, en_az=15.0):
    """Çokgenin en küçük alanlı çevre dikdörtgenini veren kenar yönü
    (radyan). Yalnız en_az'dan uzun kenarlar aday."""
    en = None
    n = len(w)
    for i in range(n):
        (x1, y1), (x2, y2) = w[i], w[(i + 1) % n]
        L = math.hypot(x2 - x1, y2 - y1)
        if L < en_az:
            continue
        a = math.atan2(y2 - y1, x2 - x1)
        ca, sa = math.cos(-a), math.sin(-a)
        xs = [x * ca - y * sa for x, y in w]; ys = [x * sa + y * ca for x, y in w]
        alan = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if en is None or alan < en[0] - 1e-6:
            en = (alan, a)
    return en[1] if en else 0.0


def _yapistir2(w, cizgiler, tol):
    """Çokgenin bir büküm çizgisine tol'dan yakın noktalarını o çizgiye
    (dik izdüşümüyle) oturtur; çizginin uzanımı dışındakiler dokunulmaz."""
    out = []
    for x, y in w:
        en = None
        for (x1, y1), (x2, y2) in cizgiler:
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            if L2 < 1e-12:
                continue
            u = ((x - x1) * dx + (y - y1) * dy) / L2
            if u < -tol / math.sqrt(L2) or u > 1 + tol / math.sqrt(L2):
                continue
            px, py = x1 + u * dx, y1 + u * dy
            m = math.hypot(x - px, y - py)
            if m <= tol and (en is None or m < en[0]):
                en = (m, px, py)
        out.append((en[1], en[2]) if en else (x, y))
    return out


def _sadelestir(w, tol=1e-3):
    """Çokgenden ardışık çakışık noktaları, aynı doğru üstündeki ara
    noktaları ve sıfır alanlı dikenleri (geri dönüşleri) atar.

    Büküm yüzünün uç kenarı (büküm rahatlatma yuvarlaması) teğet
    çizgisinin ötesine taşınca açı [0, teta]'ya kırpılır; kırpılan noktalar
    kenar çizgisi üstünde geri dönen bir diken olur. Böyle çokgenden yüz
    kurulunca birleştirme bükümü komşu duvara eklemek yerine çıkarıyordu
    (Karluna bağlantı braketi: 1196 - 613 = 583 mm2)."""
    pts = []
    for q in w:                                 # ardışık çakışık noktalar
        if not pts or math.hypot(q[0] - pts[-1][0], q[1] - pts[-1][1]) > tol:
            pts.append(q)
    while len(pts) > 3 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) <= tol:
        pts.pop()
    degisti = True
    while degisti and len(pts) > 3:              # aynı doğrultu / diken: tek tek
        degisti = False
        n = len(pts)
        for i in range(n):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
            capraz = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            uz = math.hypot(b[0] - a[0], b[1] - a[1]) * math.hypot(c[0] - b[0], c[1] - b[1])
            if uz > 0 and abs(capraz) <= tol * math.sqrt(uz):
                del pts[i]
                degisti = True
                break
    return pts


def _cerceve(w):
    """Kök duvarın düzlem çerçevesi: e1 en uzun yön, e2 = n x e1."""
    n = w["n"]
    ks = w["kose"]
    c = w["merkez"]
    # en uzun yön: köşelerin kovaryansı yerine en uzak iki köşe
    en = None
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            L = math.dist(ks[i], ks[j])
            if en is None or L > en[0]:
                en = (L, i, j)
    v = _v(ks[en[2]], ks[en[1]]) if en else (1.0, 0.0, 0.0)
    v = _v(v, _s(n, _d(v, n)))
    e1 = _n(v)
    e2 = _n(_c(n, e1))
    return (e1, e2, n, c)


def acilim3(sh, t, k_faktor, M, hacim=None, en_cok_sapma=0.03):
    """Genel açınım. M: pf3_olcu modülü (yardımcıları için).
    Döner: pf3_olcu.acilim_kesim ile aynı anahtarlar + "cok_yonlu": True."""
    AcilimYok = M.AcilimYok
    duvarlar = duvarlar3(sh, t, M)
    if not duvarlar:
        raise AcilimYok("3B açınım: sac duvarı bulunamadı.")
    bukumler = agac3(duvarlar, bukumler3(sh, t, M), t)
    if not bukumler:
        raise AcilimYok("3B açınım: hiçbir büküm iki duvara birden teğet değil.")
    komsu = defaultdict(list)
    for bi, b in enumerate(bukumler):
        a, c = b["duvar"]
        komsu[a["i"]].append((bi, a, c))
        komsu[c["i"]].append((bi, c, a))
    kok = max(komsu, key=lambda i: duvarlar[i]["alan"])
    cer = _cerceve(duvarlar[kok])
    harita = {kok: _Donusum([], cer)}
    b_harita, sira, atlanan, cevrim = {}, [kok], [], []
    while sira:
        wi = sira.pop()
        T = harita[wi]
        for bi, bu, obur in komsu[wi]:
            if bi in b_harita:
                continue
            b = bukumler[bi]
            A = duvarlar[wi]
            vA = _v(bu["tA"], b["m"]); vW = _v(obur["tA"], b["m"])
            cosT = max(-1.0, min(1.0, _d(_n(vA), _n(vW))))
            teta = math.acos(cosT)
            if teta < 1e-3:
                continue
            r_n = b["r_ic"] + k_faktor * t
            pay = teta * r_n
            # dönme işareti: W düzlemi A düzlemine gelsin, W A'nın uzağına açılsın
            # +teta da -teta da W'yi A'nın düzlemine getirir (biri dışa
            # AÇAR, öbürü A'nın üstüne KATLAR): eş düzleme gelenler
            # arasında A'dan uzağa açılanı (dis en büyük) seç.
            # Sınama noktası W'nin ağırlık merkezi DEĞİL, W'nin kendi teğet
            # çizgisinin hemen malzeme tarafındaki nokta: levhanın ortasından
            # kesilip bükülmüş dilde (bağlantı braketi) levhanın merkezi
            # dilin yanına düşüyor ve işaret ters seçiliyordu. Doğru
            # katlamada bu nokta A'nın düzlemine gelir ve A'nın teğetinin
            # ÖTESİNDE (büküm payının açıldığı yanda) durur.
            orta_s = (b["s"][0] + b["s"][1]) / 2.0 - _d(_v(obur["tA"], b["m"]), b["a"])
            sonda = _v(_p(obur["tA"], _s(b["a"], orta_s)), _s(obur["wA"], 1.5 * t))
            # teğet noktası modelde 1,1 t'ye kadar kayabilir (agac3): eşik
            # ona göre; yanlış katlama 2 (r + t/2) ~ 5 t uzakta kalır
            esik = 1.5 * t + 1.0
            sec = None
            for fi in (teta, -teta):
                q = _rodrigues(sonda, b["m"], b["a"], fi)
                duz = abs(_d(_v(q, bu["tA"]), A["n"]))
                dis = _d(_v(q, bu["tA"]), bu["wA"])
                if duz > esik or dis <= 0:
                    continue
                # küçük açılı bükümde (5° kırma) iki işaret de eşiğin
                # içinde: düzleme EN YAKIN gelen doğrudur (yanlışı 2 sin θ
                # kadar yukarıda), eşitlikte dışa en çok açılan
                if sec is None or (round(duz, 3), -dis) < (round(sec[0], 3), -sec[1]):
                    sec = (duz, dis, fi)
            if sec is None or sec[1] <= 0:
                atlanan.append(f"B{bi} {wi}->{obur['i']} teta {math.degrees(teta):.0f} "
                               f"sec {None if sec is None else (round(sec[0], 2), round(sec[1], 1))}")
                continue                   # döndürünce aynı düzleme / dışa gelmiyor
            fi = sec[2]
            kay = _s(bu["wA"], pay)
            adim = [(b["m"], b["a"], fi, kay)] + T.adim
            if obur["i"] in harita:
                # Duvara ikinci yol: yarıkla bölünmüş kanat parçalarının
                # hepsi aynı sürekli kanada bağlanır (yardımcı şasi: alt
                # kanat üç parça, dönüş kanadı tek). Dönüşüm aynıysa
                # çevrim DEĞİLDİR; farklıysa kapalı kesittir.
                T2 = _Donusum(adim, cer)
                kose = duvarlar[obur["i"]]["kose"][:16]
                sap = max(math.dist(harita[obur["i"]](q), T2(q)) for q in kose) if kose else 0.0
                if sap > max(0.5, 0.25 * t):
                    cevrim.append(f"B{bi} {wi}->{obur['i']} sapma {sap:.1f} mm")
                    continue
            b_harita[bi] = {"ust": wi, "alt": obur["i"], "tA": bu["tA"], "wA": bu["wA"],
                            "a": b["a"], "vA": vA, "vW": vW, "teta": teta, "pay": pay,
                            "r_n": r_n, "T": T}
            if obur["i"] not in harita:
                harita[obur["i"]] = _Donusum(adim, cer)
                sira.append(obur["i"])
    disarda = [i for i in range(len(duvarlar)) if i not in harita]
    toplam = sum(w["alan"] for w in duvarlar) or 1.0
    alan_d = sum(duvarlar[i]["alan"] for i in disarda)
    if alan_d > 0.03 * toplam:
        raise AcilimYok(
            f"3B açınım: duvarların {len(disarda)} tanesi büküm ağacına bağlanamadı "
            f"(sac yüzeyinin %{M.XL.tr(100 * alan_d / toplam, 0, sade=False)}'i)."
            + (" Atlanan bükümler: " + "; ".join(atlanan) if atlanan else ""))
    if cevrim:
        raise AcilimYok("3B açınım: büküm ağacında çevrim var (kapalı kesit): " + "; ".join(cevrim))
    # ---- düzlem telleri
    parca, delik = [], []
    for wi, T in harita.items():
        for f in duvarlar[wi]["yuzler"]:
            dis, ic = M._yuz_telleri(f)
            if len(dis) > 2:
                parca.append([T((p.X(), p.Y(), p.Z())) for p in dis])
            delik += [[T((p.X(), p.Y(), p.Z())) for p in q] for q in ic if len(q) > 2]
    bkm = []
    for bi, bh in b_harita.items():
        b = bukumler[bi]
        T, tA, wA, a = bh["T"], bh["tA"], bh["wA"], bh["a"]
        u1 = _n(bh["vA"])
        u2 = _n(_c(a, u1))
        yon = 1.0 if _d(bh["vW"], u2) >= 0 else -1.0

        def hb(p, T=T, tA=tA, wA=wA, a=a, u1=u1, u2=u2, yon=yon, m=b["m"], r_n=bh["r_n"],
               teta=bh["teta"]):
            v = _v(p, m)
            s = _d(v, a)
            vr = _v(v, _s(a, s))
            psi = math.atan2(yon * _d(vr, u2), _d(vr, u1))
            psi = max(0.0, min(teta, psi))
            return T(_p(_p(tA, _s(a, s - _d(_v(tA, m), a))), _s(wA, psi * r_n)))

        for f in b["yuzler"]:
            dis, ic = M._yuz_telleri(f)
            if len(dis) > 2:
                parca.append([hb((p.X(), p.Y(), p.Z())) for p in dis])
            delik += [[hb((p.X(), p.Y(), p.Z())) for p in q] for q in ic if len(q) > 2]
        s0, s1 = b["s"]
        s0 -= _d(_v(tA, b["m"]), a); s1 -= _d(_v(tA, b["m"]), a)
        bas = [T(_p(tA, _s(a, s0))), T(_p(tA, _s(a, s1)))]
        son = [T(_p(_p(tA, _s(a, s0)), _s(wA, bh["pay"]))),
               T(_p(_p(tA, _s(a, s1)), _s(wA, bh["pay"])))]
        bkm.append({"r_ic": round(b["r_ic"], 2), "r_dis": round(b["r_ic"] + t, 2),
                    "aci_derece": round(math.degrees(bh["teta"]), 1),
                    "pay_mm": round(bh["pay"], 2), "bas": bas, "son": son})
    # ---- dikişe yapıştır: duvar kenarı ile büküm bölgesinin sınırı
    # arasında modelden gelen küçük boşluk (Karluna: dış yüzün kenarı
    # teğet çizgisinden 1 mm kısa) parçaları birleştirmez; kalınlığın
    # yarısından yakın noktalar büküm çizgisine oturtulur.
    cizgiler = [q for b in bkm for q in (b["bas"], b["son"])]
    parca = [_sadelestir(_yapistir2(w, cizgiler, 0.75 * t)) for w in parca]
    delik = [_sadelestir(_yapistir2(w, cizgiler, 0.75 * t)) for w in delik]
    parca = [w for w in parca if len(w) > 2]
    delik = [w for w in delik if len(w) > 2]
    # ---- düzlemde birleştir, denetle
    taban = M._birlestir([f for f in (M._cokgen_yuzu(w) for w in parca) if f])
    if taban is None:
        raise AcilimYok("3B açınım: parçalar düzlemde birleştirilemedi.")
    delik_yuz = [f for f in (M._cokgen_yuzu(w) for w in delik) if f]
    if delik_yuz:
        op = BRepAlgoAPI_Cut(taban, M._birlestir(delik_yuz, sadelestir=False))
        op.SetFuzzyValue(0.01)
        op.Build()
        if op.IsDone():
            taban = op.Shape()
    alan = _alan(taban)
    if hacim:
        duzelt = sum(math.radians(b["aci_derece"]) * t * t
                     * math.dist(b["bas"][0], b["bas"][1]) * (0.5 - k_faktor) for b in bkm)
        sapma = (alan * t + duzelt - hacim) / hacim
        if abs(sapma) > en_cok_sapma:
            raise AcilimYok(
                f"3B açınım denetimi tutmadı: düzlemdeki alan x kalınlık "
                f"{M.XL.tr(alan * t + duzelt, 0, sade=False)} mm3, parçanın hacmi "
                f"{M.XL.tr(hacim, 0, sade=False)} mm3 "
                f"(%{('+' if sapma >= 0 else '') + M.XL.tr(100 * sapma, 1, sade=False)}).")
    dis, ic = M._dis_halkalar(taban)
    if not dis:
        raise AcilimYok("3B açınım: sınır çıkarılamadı.")
    ic = M.delikleri_birlestir(ic, M.ince_serit(t))
    if len(dis) != 1:
        ayri = sorted((abs(M._cokgen_alani(w)) for w in dis), reverse=True)
        raise AcilimYok(
            f"3B açınım düzlemde {len(dis)} ayrı parça çıktı; duvarlar uç uca "
            "oturmadı. Parça alanları: "
            + ", ".join(f"{M.XL.tr(a_, 0, sade=False)} mm2" for a_ in ayri[:4]) + "."
            + (" Atlanan bükümler: " + "; ".join(atlanan) if atlanan else ""))
    # ---- yönlendir: en küçük alanlı çevre dikdörtgeni eksenlere otursun,
    # uzun kenar X boyunca (2B açınımla aynı alışkanlık: büküm çizgileri
    # çoğunlukla yatay). Kök duvarın çerçevesi rastgele dönüktü.
    aci = _en_kucuk_dikdortgen_acisi(dis[0])
    ca, sa = math.cos(-aci), math.sin(-aci)

    def dondur(w):
        return [(x * ca - y * sa, x * sa + y * ca) for x, y in w]
    dis = [dondur(w) for w in dis]; ic = [dondur(w) for w in ic]
    for b in bkm:
        b["bas"] = dondur(b["bas"]); b["son"] = dondur(b["son"])
    xs = [p[0] for w in dis for p in w]; ys = [p[1] for w in dis for p in w]
    takas = max(xs) - min(xs) < max(ys) - min(ys)
    if takas:                                         # uzun kenar X'e
        dis = [[(y, -x) for x, y in w] for w in dis]; ic = [[(y, -x) for x, y in w] for w in ic]
        for b in bkm:
            b["bas"] = [(y, -x) for x, y in b["bas"]]; b["son"] = [(y, -x) for x, y in b["son"]]
        xs = [p[0] for w in dis for p in w]; ys = [p[1] for w in dis for p in w]
    dx, dy = -min(xs), -min(ys)

    def kay(w):
        return [(x + dx, y + dy) for x, y in w]
    for b in bkm:
        b["bas"] = kay(b["bas"]); b["son"] = kay(b["son"])
        b["cizgi"] = [((b["bas"][0][0] + b["son"][0][0]) / 2.0, (b["bas"][0][1] + b["son"][0][1]) / 2.0),
                      ((b["bas"][1][0] + b["son"][1][0]) / 2.0, (b["bas"][1][1] + b["son"][1][1]) / 2.0)]
        # çizelge için: büküm bölgesi çizgisinin "y" konumu (ortalama) - eğikse bilgi
        b["acinimda_bas_mm"] = round(min(q[1] for q in b["bas"] + b["son"]), 2)
        b["acinimda_son_mm"] = round(max(q[1] for q in b["bas"] + b["son"]), 2)
    bkm.sort(key=lambda b: (b["cizgi"][0][1] + b["cizgi"][1][1]))
    yon_ = M.bukum_yontemi(
        t, [math.sqrt(w["alan"]) for w in duvarlar],
        [b["r_ic"] for b in bkm], [math.radians(b["aci_derece"]) for b in bkm],
        max(ys) - min(ys))
    # DÜZLEM EKSENLERİ 3B'de (girdi katının çerçevesinde; araç yönüne
    # oturtmak için, bkz. pf3_olcu.acinim_arac_yonu): her duvarın düzlem
    # çerçevesi (e1, e2) bu duvarın serme dönüşümüyle ve son döndürmeyle
    # düzleme gider; dönüşüm ortogonaldir, tersi devriğidir.
    def son_yon(v2):
        x, y = v2
        x, y = x * ca - y * sa, x * sa + y * ca
        return (y, -x) if takas else (x, y)
    duz_duvar, kok_x = [], None
    for wi, don in harita.items():
        try:
            e1, e2, n_, _o = _cerceve(duvarlar[wi])
            a1, a2 = son_yon(don.yon(e1))
            b1, b2 = son_yon(don.yon(e2))
        except Exception:
            continue
        yy = _n(_p(_s(e1, a2), _s(e2, b2)))          # düzlemin +Y'si 3B'de
        xx = _n(_p(_s(e1, a1), _s(e2, b1)))          # düzlemin +X'i 3B'de
        duz_duvar.append((duvarlar[wi]["alan"], yy, tuple(n_)))
        if wi == kok:
            kok_x = xx
    duz_yon = {"x": kok_x, "duvar": duz_duvar} if kok_x and duz_duvar else None
    return {"yontem": yon_, "profil": None, "cok_yonlu": True, "duz_yon": duz_yon,
            "baglanamayan_alan_mm2": round(alan_d, 1), "baglanamayan_duvar": len(disarda),
            "kontur_dis": [kay(w) for w in dis], "kontur_delik": [kay(w) for w in ic],
            "delik_adedi": len(ic),
            "acinim_boy_mm": round(max(xs) - min(xs), 2),
            "acinim_genislik_mm": round(max(ys) - min(ys), 2),
            "acinim_alan_mm2": round(alan, 1),
            "duvar_sayisi": len(harita), "bukum_sayisi": len(bkm),
            "bukumler": bkm,
            "bukum_yerleri": [(b["acinimda_bas_mm"], b["acinimda_son_mm"]) for b in bkm]}
