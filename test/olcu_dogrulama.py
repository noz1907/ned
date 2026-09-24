# -*- coding: utf-8 -*-
"""Resme giren HER konum ölçüsü doğru mu? - 3B modelden BAĞIMSIZ denetim.

Kural (kullanıcının koyduğu): hata oranı %0,5 - 1'in altında olacak;
hata olasılığı yüksek olan ölçü türü hiç yazılmaz.

Bu betik programın plan kodunu çalıştırır, sonra her ölçünün iki ucunu
B-rep'ten (HLR'siz, 2B kontursuz) toplanan TASARIM KOORDİNATLARIYLA
karşılaştırır. Bir eksende tasarım koordinatı şunlardır:

  1. O eksene DİK düz yüzeylerin seviyesi (çentik duvarı, basamak, kenar),
  2. Silindirin o eksendeki uç noktaları (eksen ± r) - yuva ucu, yuvarlak
     dip; yarım turdan geniş silindirin (delik, yuva ucu) EKSENİ,
  3. SANAL KÖŞE: o düzlemde EĞİK duran doğru bir kenarın, öbür eksene dik
     bir düz yüzey seviyesiyle kesiştiği yer (köşe kesiği, pah uzantısı),
  4. (yalnız gabari ve datum için) parçanın sınır kutusu.

Salt "modelde orada bir köşe var" YETMEZ: yuvarlatmanın teğet noktası da
bir köşedir ama ressam oraya ölçü vermez. Teğet noktası yukarıdakilerin
hiçbirine girmez (yuvarlatma çeyrek silindirdir, ekseni sayılmaz), yani
teğet noktasına verilmiş ölçü HATA sayılır.

Dizi ("n x adım") için dizinin her elemanı ayrıca aranır. Girinti
derinliği için çentiğin dibi aranır.

    python test/olcu_dogrulama.py model1.stp [model2.stp ...]
    python test/olcu_dogrulama.py --ayrinti model.stp     (her hatayı yazar)
    python test/olcu_dogrulama.py --kapisiz model.stp     (3B kapı olmasa)
"""
import bisect
import math
import os
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as O                                          # noqa: E402

from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve  # noqa: E402
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE                # noqa: E402
from OCP.TopExp import TopExp_Explorer                          # noqa: E402
from OCP.TopoDS import TopoDS                                   # noqa: E402

TOL = 0.01          # mm; resme yazılan değer bu kadar içinde tutmalı


def _gez(sh, tur):
    ex = TopExp_Explorer(sh, tur)
    while ex.More():
        yield ex.Current()
        ex.Next()


def _yuz_ornek(f, n=7):
    ad = BRepAdaptor_Surface(TopoDS.Face_s(f))
    u0, u1 = ad.FirstUParameter(), ad.LastUParameter()
    v0, v1 = ad.FirstVParameter(), ad.LastVParameter()
    if max(abs(u0), abs(u1), abs(v0), abs(v1)) > 1e7:
        return []
    out = []
    for a in range(n):
        for b in range(n):
            p = ad.Value(u0 + (u1 - u0) * a / (n - 1), v0 + (v1 - v0) * b / (n - 1))
            out.append((p.X(), p.Y(), p.Z()))
    return out


def _kenar_ornek(e, n=9):
    c = BRepAdaptor_Curve(TopoDS.Edge_s(e))
    t0, t1 = c.FirstParameter(), c.LastParameter()
    if max(abs(t0), abs(t1)) > 1e7:
        return []
    return [(q.X(), q.Y(), q.Z()) for q in
            (c.Value(t0 + (t1 - t0) * k / (n - 1)) for k in range(n))]


def tasarim_koordinatlari(s):
    """Her model ekseni (0=X, 1=Y, 2=Z) için sıralı tasarım koordinatları.

    TİP ADINA GÜVENİLMEZ, geometriye bakılır: bu STEP'lerde eğik kenarlar
    B-rep'te bile B-spline olarak kayıtlı (09.020.000.03'te 168 kenarın
    74'ü). Yüzey ve kenar örneklenir; düzlem mi, silindir mi, doğru mu,
    noktalardan anlaşılır.

    Döner: (tasarim, kutu_koord) - ikincisi yalnız gabari/datum için."""
    kb = O.kutu(s)
    boy = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2], 1.0)
    et = 1e-6 * boy + 1e-7
    duz = [set() for _ in range(3)]
    ek = [set() for _ in range(3)]
    # Aynı silindirin parçaları: bir delik 2 yarım ya da 4 ÇEYREK yüzden
    # oluşabiliyor (01.051.000.01'de Ø6,8 deliklerin hepsi 4 çeyrek).
    # Eksen ancak parçaların TOPLAM açısı yarım turu geçerse sayılır;
    # tek başına çeyrek olan yuvarlatmanın ekseni sayılmaz.
    silindir = defaultdict(list)
    for f in _gez(s, TopAbs_FACE):
        pts = _yuz_ornek(f)
        if not pts:
            continue
        for i in range(3):
            c = [q[i] for q in pts]
            if max(c) - min(c) < 10 * et:           # 1) eksene DİK düzlem
                duz[i].add(round(sum(c) / len(c), 5))
        for k in range(3):                          # 2) ekseni k'ya paralel silindir
            i, j = [a for a in range(3) if a != k]
            if max(q[k] for q in pts) - min(q[k] for q in pts) < 10 * et:
                continue                            # k boyunca uzamıyor
            cf = O._cember_uydur([(q[i], q[j]) for q in pts])
            if not cf:
                continue
            cx, cy, r, sap = cf
            if sap > 1e-4 * r + 10 * et or r > 1e5:
                continue
            anahtar = (k, round(cx, 3), round(cy, 3), round(r, 3))
            silindir[anahtar] += [math.atan2(q[j] - cy, q[i] - cx) for q in pts]
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
    # 3) sanal köşe: EĞİK doğru kenar x düz yüzey seviyesi
    for e in _gez(s, TopAbs_EDGE):
        pts = _kenar_ornek(e)
        if len(pts) < 2:
            continue
        a, b = pts[0], pts[-1]
        uz = math.dist(a, b)
        if uz < 1e-6:
            continue
        D = [(b[k] - a[k]) / uz for k in range(3)]
        # doğru mu: ara noktalar kirişten sapmamalı
        sap = 0.0
        for q in pts[1:-1]:
            w = [q[k] - a[k] for k in range(3)]
            t_ = sum(w[k] * D[k] for k in range(3))
            sap = max(sap, math.sqrt(max(0.0, sum(w[k] ** 2 for k in range(3)) - t_ * t_)))
        if sap > 1e-5 * uz + 10 * et:
            continue
        for j in range(3):
            if abs(D[j]) < 1e-7:
                continue
            for i in range(3):
                if i == j or abs(D[i]) < 1e-7:
                    continue
                for bb in duz[j]:
                    t_ = (bb - a[j]) / D[j]
                    v = a[i] + t_ * D[i]
                    if kb[i] - TOL <= v <= kb[i + 3] + TOL:
                        ek[i].add(round(v, 5))
    tasarim = [sorted(duz[i] | ek[i]) for i in range(3)]
    kutu_k = [sorted({round(kb[i], 5), round(kb[i + 3], 5)}) for i in range(3)]
    return tasarim, kutu_k


def _var(liste, v, tol=TOL):
    i = bisect.bisect_left(liste, v - tol)
    return i < len(liste) and liste[i] <= v + tol


def _model(gad, yon, v):
    """HAM izdüşüm koordinatı -> (model ekseni, model koordinatı)."""
    i1, i2, tx, ty = O.GOR_EKSEN[gad]
    if yon == "yatay":
        return i1, (-v if tx else v)
    return i2, (-v if ty else v)


def parca_denetle(s, o, P, ayrinti=None, kapisiz=False):
    """Bir parçanın planını denetler. Döner: {tur: [toplam, hata]}.

    Plan, programın kendi yaptığı gibi 3B seviye kapısıyla kurulur
    (kapisiz=True ise kapı kapalı: kapı olmasa ne olurdu). Denetimin
    kendisi bu dosyadaki AYRI yazılmış tasarim_koordinatlari ile yapılır -
    programın koduna dayanmaz."""
    kb = O.kutu(s)
    L, W, T = kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]
    h = min(25.0, max(2.5, max(L, W, T) / 45.0))
    gor = O.gorunus_sec(P.get("gorunusler"))
    ken = {g: O.hlr(s, *O.GORUNUS[g], gizli=P.get("gizli", True)) for g in gor}
    ham = {g: O._kenar_kutusu(k) for g, k in ken.items()}
    seviye = None if kapisiz else O.tasarim_seviyeleri(s)
    atl = Counter()
    plan = O.konum_plani(o, gor, ham, h, ken, seviye=seviye, rapor=atl)
    tas, kutu_k = tasarim_koordinatlari(s)
    say = defaultdict(lambda: [0, 0])

    def yokla(tur, gad, yon, v, gabari_olur=False):
        i, m = _model(gad, yon, v)
        dogru = _var(tas[i], m) or (gabari_olur and _var(kutu_k[i], m))
        say[tur][0] += 1
        if not dogru:
            say[tur][1] += 1
            if ayrinti is not None:
                ayrinti.append((tur, gad, yon, round(v, 3), "XYZ"[i],
                                round(m, 3)))
        return dogru

    for gad, pl in plan.items():
        kutu_ = ham[gad]
        for yon, e0, e1 in (("yatay", kutu_[0], kutu_[2]),
                            ("dusey", kutu_[1], kutu_[3])):
            if pl.get(yon):
                dat = e1 if O.datum_ucu(gad, yon) else e0
                yokla("datum", gad, yon, dat, gabari_olur=True)
                # Bilgi: datum bir TASARIM yüzeyi mi, yoksa yalnız sınır
                # kutusunun ucu mu (eğik yüzün köşesi gibi)?
                yokla("(bilgi) datum yüzeyde", gad, yon, dat)
            for r in pl.get(yon) or []:
                tur = "+".join(r.get("kaynak") or ["?"])
                if r.get("adet"):
                    # Dizinin HER elemanı gerçek bir delik ekseninde mi?
                    for k in range(r["adet"]):
                        yokla("dizi-eleman", gad, yon,
                              min(r["a"], r["b"]) + k * r["adim"])
                    continue
                for v in (r["a"], r["b"]):
                    if abs(v - e0) < 1e-6 or abs(v - e1) < 1e-6:
                        continue       # datum / gabari ucu: ayrıca denetlendi
                    yokla(tur, gad, yon, v)
        for r in pl.get("ozellik") or []:
            if not r.get("ic") or r.get("derinlik") is None:
                continue
            # Çentiğin dibi: kenardan derinlik kadar içeride.
            yatay = r["yon"] == "yatay"
            dik = "dusey" if yatay else "yatay"
            if yatay:
                kenar = kutu_[1] if r["taraf"] == "alt" else kutu_[3]
                dip = kenar + (r["derinlik"] if r["taraf"] == "alt"
                               else -r["derinlik"])
            else:
                kenar = kutu_[0] if r["taraf"] == "sol" else kutu_[2]
                dip = kenar + (r["derinlik"] if r["taraf"] == "sol"
                               else -r["derinlik"])
            yokla("derinlik", gad, dik, dip)
    for t, n in atl.items():
        say["(atıldı) " + t][0] += n
    return say


def main(argv):
    ayr = "--ayrinti" in argv
    kapisiz = "--kapisiz" in argv
    dosyalar = [a for a in argv if not a.startswith("--")]
    if not dosyalar:
        print(__doc__)
        return 2
    P = {"gizli": True, "en_az_delik": 1.0, "yogunluk": O.RHO,
         "gorunusler": O.VARSAYILAN_GORUNUS, "kesit": False}
    genel = defaultdict(lambda: [0, 0])
    hatalar = []
    t0 = time.time()
    for yol in dosyalar:
        kayit, komp, _ = O.step_komponentleri(yol, P, log=lambda *a: None)
        parca = [k for k in komp if k["sinif"] == "parca"]
        print(f"\n== {os.path.basename(yol)}: {len(parca)} parça")
        for k in parca:
            try:
                s, o = O.komponent_olcu(kayit[k["indeks"][0]][1], P)
                liste = []
                say = parca_denetle(s, o, P, liste, kapisiz=kapisiz)
            except Exception as ex:
                print(f"   atlandı {k['kod'][:30]}: {ex}"[:100])
                continue
            for t, (n, h) in say.items():
                genel[t][0] += n
                genel[t][1] += h
            if liste:
                hatalar += [(os.path.basename(yol)[:14], k["kod"][:24]) + x
                            for x in liste]
                if ayr:
                    for x in liste:
                        print(f"   HATA {k['kod'][:24]:24s} {x}")
    print(f"\n{'tür':22s} {'ölçü':>6s} {'hatalı':>7s} {'oran':>7s}")
    top_n = top_h = 0
    for t in sorted(genel, key=lambda t: -genel[t][0]):
        n, h = genel[t]
        if not t.startswith("("):
            top_n += n
            top_h += h
        print(f"{t:22s} {n:6d} {h:7d} {100.0 * h / max(n, 1):6.2f}%")
    print(f"{'TOPLAM':22s} {top_n:6d} {top_h:7d} "
          f"{100.0 * top_h / max(top_n, 1):6.2f}%   [{time.time() - t0:.0f}s]")
    if hatalar and not ayr:
        print("\nilk hatalar:")
        for x in hatalar[:25]:
            print("  ", x)
    return 0 if top_h <= 0.005 * max(top_n, 1) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
