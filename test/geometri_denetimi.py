# -*- coding: utf-8 -*-
"""Geometriden tanıma (pf8_tani): adsız katı pul mu, somun mu, cıvata mı,
perçin mi, pim mi, o-ring mi, kaynak dikişi mi - YA DA HİÇBİRİ Mİ.

Asıl denetlenen ikinci kısımdır: üretim parçası (blok, delikli plaka,
kademeli mil, kalın burç, flanş, L köşebent, uzun mil, pahlı mil, kör
delikli burç) ve BELİRSİZ şekil (düz uçlu Ø5 çubuk - CATIA kaynak
dikişini böyle modelliyor) HİÇBİR ŞEY sayılmamalı. Her şekil bir de
uzayda rastgele döndürülüp kaydırılarak denenir.

Gerçek modellerde ölçmek için (adı belli komponentlerle karşılaştırır):
    python3 test/geometri_denetimi.py model1.stp model2.stp ...

    python3 test/geometri_denetimi.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf8_tani as T                                             # noqa: E402
from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer          # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus                # noqa: E402
from OCP.TopAbs import TopAbs_EDGE                               # noqa: E402
from OCP.TopExp import TopExp_Explorer                           # noqa: E402
from OCP.TopoDS import TopoDS                                    # noqa: E402

from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeBox, BRepPrimAPI_MakePrism, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeCone
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
from OCP.gp import gp_Pnt, gp_Vec, gp_Ax2, gp_Dir, gp_Trsf, gp_Ax1
def cyl(r,h,z=0): return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0,0,z),gp_Dir(0,0,1)),r,h).Shape()
def cut(a,b): return BRepAlgoAPI_Cut(a,b).Shape()
def fuse(a,b): return BRepAlgoAPI_Fuse(a,b).Shape()
def prizma(pts,h,z=0):
    p=BRepBuilderAPI_MakePolygon()
    for x,y in pts: p.Add(gp_Pnt(x,y,z))
    p.Close()
    f=BRepBuilderAPI_MakeFace(p.Wire()).Face()
    return BRepPrimAPI_MakePrism(f,gp_Vec(0,0,h)).Shape()
def hexa(s,h,z=0):
    R=s/math.sqrt(3)
    return prizma([(R*math.cos(math.radians(30+60*i)),R*math.sin(math.radians(30+60*i))) for i in range(6)],h,z)
def dondur(sh, ax=(1,1,0.3), a=37, t=(120,-40,55)):
    tr=gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(*ax)),math.radians(a))
    t2=gp_Trsf(); t2.SetTranslation(gp_Vec(*t))
    sh=BRepBuilderAPI_Transform(sh,tr,True).Shape()
    return BRepBuilderAPI_Transform(sh,t2,True).Shape()
def sekiller():
    S={}
    S["pul M10"]=(cut(cyl(10,2),cyl(5.3,2)),"standart")
    S["somun M10"]=(cut(hexa(16,8),cyl(5,8)),"standart")
    S["kare somun"]=(cut(prizma([(-8,-8),(8,-8),(8,8),(-8,8)],6),cyl(4,6)),"standart")
    S["civata M10x40 altigen"]=(fuse(hexa(16,6.4),cyl(5,40,6.4)),"standart")
    S["imbus M8x30"]=(cut(fuse(cyl(6.5,8),cyl(4,30,8)),hexa(6,4,0)),"standart")
    S["percin kubbe"]=(fuse(cut(BRepPrimAPI_MakeSphere(gp_Pnt(0,0,0),6).Shape(),BRepPrimAPI_MakeBox(gp_Pnt(-7,-7,-7),14,14,7).Shape()),cyl(3,15,-15)),"standart")
    S["pim 6x30"]=(cyl(3,30),"standart")
    tri=prizma([(0,0),(5,0),(0,5)],80)
    S["kose kaynagi a5 L80"]=(tri,"kaynak")
    S["blok"]=(BRepPrimAPI_MakeBox(40,30,20).Shape(),None)
    S["delikli plaka"]=(cut(BRepPrimAPI_MakeBox(gp_Pnt(-50,-30,0),100,60,5).Shape(),cyl(5,5)),None)
    S["kademeli mil 30"]=(fuse(cyl(15,100),cyl(10,40,100)),None)
    S["burc (kalin)"]=(cut(cyl(20,30),cyl(10,30)),None)
    S["flans"]=(cut(fuse(cyl(40,10),cyl(20,30,10)),cyl(12,40)),None)
    S["L kosebent"]=(prizma([(0,0),(40,0),(40,4),(4,4),(4,40),(0,40)],100),None)
    S["uzun mil 20x300"]=(cyl(10,300),None)
    return S


def pahla(sh, d=0.5):
    m = BRepFilletAPI_MakeChamfer(sh)
    e = TopExp_Explorer(sh, TopAbs_EDGE)
    while e.More():
        m.Add(d, TopoDS.Edge_s(e.Current()))
        e.Next()
    return m.Shape()


HATA = []
S = sekiller()
S["pim 6x30"] = (pahla(cyl(3, 30)), "standart")
S["düz uçlu Ø5 çubuk (kaynak?)"] = (cyl(2.5, 25), None)
S["o-ring"] = (BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)),
                                     8, 1.5).Shape(), "standart")
S["pahlı cıvata"] = (pahla(fuse(hexa(16, 6.4), cyl(5, 40, 6.4)), 0.3), "standart")
S["pahlı pul"] = (pahla(cut(cyl(10, 2), cyl(5.3, 2)), 0.3), "standart")
S["pahlı somun"] = (pahla(cut(hexa(16, 8), cyl(5, 8)), 0.4), "standart")
S["pahlı mil Ø30"] = (pahla(cyl(15, 120), 1), None)
S["kör delikli burç"] = (cut(cyl(10, 2), cyl(5, 1.5, 0.5)), None)
# perçin somun: ince başlı burç; delik baş tarafında geniş (Ø8), uçta
# dişli kısım (Ø6). Kaynaklı kasadaki "M6 SOMUN PERCIN" bu biçimde.
S["perçin somun M6"] = (cut(cut(fuse(cyl(5.2, 1), cyl(4.5, 13, 1)), cyl(4, 4)),
                            cyl(3, 14)), "standart")
S["perçin somun altıgen gövde"] = (cut(fuse(cyl(6.5, 1.2), hexa(9, 12, 1.2)),
                                       cyl(3, 13.2)), "standart")
S["perçin somun kapalı uçlu"] = (cut(cut(fuse(cyl(5.2, 1), cyl(4.5, 16, 1)),
                                         cyl(4, 4)), cyl(3, 11)), "standart")
# diş modelli somun: delik silindir değil (20 köşeli), yüzlerden
# anlaşılmaz; ışın ölçümü tanır
S["dişli somun (20 köşe delik)"] = (cut(hexa(16, 8), prizma(
    [(5 * math.cos(math.radians(18 * i)), 5 * math.sin(math.radians(18 * i)))
     for i in range(20)], 8)), "standart")
# bunlar HİÇBİR ŞEY sayılmamalı
S["flanşlı burç (düz delik)"] = (cut(fuse(cyl(9, 2), cyl(6, 15, 2)), cyl(4, 17)), None)
S["saplamalı kauçuk takoz"] = (fuse(cyl(15, 20), cyl(4, 20, 20)), None)
S["kare delikli plaka 24x24x3"] = (cut(prizma([(-12, -12), (12, -12), (12, 12),
                                               (-12, 12)], 3), cyl(5.5, 3)), None)

print("-- sentetik şekiller (düz ve döndürülmüş)")
for ad, (sh, bek) in S.items():
    for d in (False, True):
        r = T.tani(dondur(sh) if d else sh)
        ok = (r[0] if r else None) == bek
        print(f"  {'tamam' if ok else 'HATA '} {ad:30s} {'döndü' if d else '     '} "
              f"{r[2] if r else '(karar yok)'}")
        if not ok:
            HATA.append(ad)

print("\n-- profil (sabit kesitli parça): tür ve kesit ölçüsü")


def kutu_prof(a, b, t, L):
    return cut(prizma([(0, 0), (a, 0), (a, b), (0, b)], L),
               prizma([(t, t), (a - t, t), (a - t, b - t), (t, b - t)], L))


def delikli(sh, L, r=4, n=5, eks="x"):
    for i in range(n):
        z = L * (i + 0.5) / n
        c = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(-50, 12, z), gp_Dir(1, 0, 0)), r, 200).Shape()
        sh = cut(sh, c)
    return sh


def gonye(sh, a, L):
    """iki ucu 45° gönye kesilmiş"""
    k = BRepPrimAPI_MakeBox(gp_Pnt(-100, -100, -200), 400, 400, 200).Shape()
    tr = gp_Trsf()
    tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), math.radians(45))
    sh = cut(sh, BRepBuilderAPI_Transform(k, tr, True).Shape())
    tr2 = gp_Trsf()
    tr2.SetRotation(gp_Ax1(gp_Pnt(0, 0, L), gp_Dir(0, 1, 0)), math.radians(-45))
    k2 = BRepPrimAPI_MakeBox(gp_Pnt(-100, -100, L), 400, 400, 200).Shape()
    return cut(sh, BRepBuilderAPI_Transform(k2, tr2, True).Shape())


# alüminyum sigma profil: ortada delik, dört yanda T kanal
sigma = cut(prizma([(0, 0), (40, 0), (40, 40), (0, 40)], 500),
            BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(20, 20, 0), gp_Dir(0, 0, 1)),
                                     3.4, 500).Shape())
kanal = [(16, 0), (24, 0), (24, 3), (28, 3), (28, 9), (12, 9), (12, 3), (16, 3)]
for i in range(4):
    a = math.radians(90 * i)
    sigma = cut(sigma, prizma([(20 + (x - 20) * math.cos(a) - (y - 20) * math.sin(a),
                                20 + (x - 20) * math.sin(a) + (y - 20) * math.cos(a))
                               for x, y in kanal], 500))
PR = {
    "kutu 30x50x2": (kutu_prof(30, 50, 2, 1000), "kutu", "30x50x2"),
    "kare kutu 40x40x3": (kutu_prof(40, 40, 3, 600), "kare kutu", "40x40x3"),
    "kutu 30x50x2 delikli": (delikli(kutu_prof(30, 50, 2, 1000), 1000), "kutu", "30x50x2"),
    "kutu 40x40x2 gönyeli": (gonye(kutu_prof(40, 40, 2, 800), 40, 800), "kare kutu", "40x40x2"),
    "boru Ø48,3x3": (cut(cyl(24.15, 600), cyl(21.15, 600)), "boru", "Ø48,3x3"),
    "köşebent 40x40x4": (prizma([(0, 0), (40, 0), (40, 4), (4, 4), (4, 40), (0, 40)], 1000),
                         "köşebent", "40x40x4"),
    "U 50x30x2": (prizma([(0, 0), (30, 0), (30, 2), (2, 2), (2, 48), (30, 48), (30, 50),
                          (0, 50)], 800), "U profil", "50x30x2"),
    "C 60x30x2 dudaklı": (prizma([(0, 0), (30, 0), (30, 10), (28, 10), (28, 2), (2, 2),
                                  (2, 58), (28, 58), (28, 50), (30, 50), (30, 60),
                                  (0, 60)], 800), "C profil", "60x30x2"),
    "T 50x50x5": (prizma([(0, 45), (22.5, 45), (22.5, 0), (27.5, 0), (27.5, 45), (50, 45),
                          (50, 50), (0, 50)], 700), "T profil", "50x50x5"),
    "I 100x50x5": (prizma([(0, 0), (50, 0), (50, 5), (27.5, 5), (27.5, 95), (50, 95),
                           (50, 100), (0, 100), (0, 95), (22.5, 95), (22.5, 5), (0, 5)],
                          900), "I/H profil", "100x50x5"),
    "lama 50x5": (prizma([(0, 0), (50, 0), (50, 5), (0, 5)], 500), "lama", "50x5"),
    "mil Ø20": (cyl(10, 300), "mil", "Ø20"),
    "alüminyum sigma 40x40": (sigma, "ekstrüzyon", "40x40"),
    # profil DEĞİL
    "plaka 400x300x5": (prizma([(0, 0), (400, 0), (400, 300), (0, 300)], 5), None, None),
    "blok 40x30x20": (BRepPrimAPI_MakeBox(40, 30, 20).Shape(), None, None),
    "kademeli mil": (fuse(cyl(15, 100), cyl(10, 100, 100)), None, None),
    "flanşlı boru": (fuse(cut(cyl(24, 400), cyl(21, 400)),
                          cut(cyl(60, 10), cyl(21, 10))), None, None),
    "kısa boru (burç)": (cut(cyl(24, 60), cyl(21, 60)), None, None),
}
for ad, (sh, tur, kesit) in PR.items():
    for d in (False, True):
        r = T.profil(dondur(sh) if d else sh)
        ok = (r["tur"] if r else None) == tur and (r["kesit"] if r else None) == kesit
        print(f"  {'tamam' if ok else 'HATA '} {ad:30s} {'döndü' if d else '     '} "
              f"{r['gerekce'] if r else '(profil değil)'}")
        if not ok:
            HATA.append("profil " + ad)

print("\n-- benzerinden öğrenme (biçim imzası)")
import pf3_olcu as M                                             # noqa: E402


def percin_somun(rf, hf, rg, L, rb, db, rd):
    """flanş (rf, hf) + gövde (rg, L); baş tarafta geniş delik (rb, db),
    kalanı dişli delik (rd)"""
    return cut(cut(fuse(cyl(rf, hf), cyl(rg, L, hf)), cyl(rb, db)), cyl(rd, hf + L))


ogr = [("510206504-00", percin_somun(5.2, 1.0, 4.5, 13, 4.0, 4, 3.0)),      # M6: öğretilen
       ("510206505-00", percin_somun(6.8, 1.5, 5.5, 16, 5.0, 5, 4.0)),      # M8: benzeri
       ("K0 BAGLANTI SACI", percin_somun(5.2, 1.0, 4.5, 13, 4.0, 4, 3.0)),  # adı sac diyor
       ("COMPOUND", cut(prizma([(-12, -12), (12, -12), (12, 12), (-12, 12)], 3),
                        cyl(5.5, 3))),                                      # delikli plaka
       ("PARCA-77", cut(fuse(cyl(9, 2), cyl(6, 15, 2)), cyl(4, 17)))]       # flanşlı burç
kayit = [(a, dondur(sh) if i % 2 else sh) for i, (a, sh) in enumerate(ogr)]
komp = [{"ad": a, "kod": a, "sinif": "parca", "tip": "", "indeks": [i],
         "hacim_mm3": 0.0, "olc": [0, 0, 0]} for i, (a, _s) in enumerate(ogr)]
im0 = T.bicim_imzasi(kayit[0][1])
kural = {M.kural_anahtari(komp[0]["ad"], komp[0]): "standart",
         M.sekil_anahtari(im0): "standart"}
komp[0]["sinif"] = "standart"
n = M.benzerden_sinifla(kayit, komp, kural, log=lambda t: None)
for k, bek in zip(komp, ("standart", "standart", "parca", "parca", "parca")):
    ok = k["sinif"] == bek
    print(f"  {'tamam' if ok else 'HATA '} {k['ad']:30s} {k['sinif']} {k['tip']}")
    if not ok:
        HATA.append("öğrenme " + k["ad"])
ok = n == 1
print(f"  {'tamam' if ok else 'HATA '} yalnız M8 değişti ({n})")
if not ok:
    HATA.append("öğrenme sayısı")

print("\n-- adsız mı")
for ad, bek in (("COMPOUND", True), ("SOLID", True), ("Body1", True),
                 ("Symmetry of COMPOUND.2", True), ("1", True), ("PartBody", True),
                 ("K0 KAMERA", False), ("Ausprägung_2-oa0", False),
                 ("510206504-00", False)):
    ok = T.isimsiz(ad) == bek
    print(f"  {'tamam' if ok else 'HATA '} {ad:30s} {T.isimsiz(ad)}")
    if not ok:
        HATA.append(ad)

if len(sys.argv) > 1:
    import pf3_olcu as M
    from collections import Counter
    P = {"gizli": False, "en_az_delik": 1.0, "yogunluk": M.RHO,
         "gorunusler": M.gorunus_sec(["ON"]), "kesit": False}
    say = Counter()
    for y in sys.argv[1:]:
        kayit, komp, _ = M.step_komponentleri(y, P, log=lambda t: None)
        for k in komp:
            if T.isimsiz(k["ad"]) or k.get("geometri"):
                continue
            r = T.tani(kayit[k["indeks"][0]][1], k["hacim_mm3"])
            if r:
                say[(k["sinif"], r[0])] += 1
    dogru = sum(v for (a, b), v in say.items() if a == b)
    tum = sum(say.values())
    print(f"\n-- gerçek modeller: {tum} karar, {tum - dogru} yanlış "
          f"(%{100.0 * (tum - dogru) / max(tum, 1):.2f})  {dict(say)}")

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                     else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(1 if HATA else 0)
