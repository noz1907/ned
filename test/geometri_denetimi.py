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

print("-- sentetik şekiller (düz ve döndürülmüş)")
for ad, (sh, bek) in S.items():
    for d in (False, True):
        r = T.tani(dondur(sh) if d else sh)
        ok = (r[0] if r else None) == bek
        print(f"  {'tamam' if ok else 'HATA '} {ad:30s} {'döndü' if d else '     '} "
              f"{r[2] if r else '(karar yok)'}")
        if not ok:
            HATA.append(ad)

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
