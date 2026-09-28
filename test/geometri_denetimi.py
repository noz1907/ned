# -*- coding: utf-8 -*-
"""Geometriden tanıma (pf8_tani): adsız katı pul mu, somun mu, cıvata mı, yay mı,
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
import shutil
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
def _don(a):
    tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(a))
    return tr
def _don_x(a):
    tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(20, 0, 0), gp_Dir(0, 1, 0)), math.radians(a))
    return tr
def _kaydir(x, y, z):
    tr = gp_Trsf(); tr.SetTranslation(gp_Vec(x, y, z))
    return tr
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

print("\n-- YAPISAL tanıma: öğelerden tip (baş + lokma, delik + tutma yüzü)")
import pf11_yapi as Y                                            # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone as _Koni       # noqa: E402


def yildiz(ri, ro, n, h, z=0):
    return prizma([((ro if i % 2 == 0 else ri) * math.cos(math.pi * i / n),
                    (ro if i % 2 == 0 else ri) * math.sin(math.pi * i / n))
                   for i in range(2 * n)], h, z)


def kutu_(x0, y0, z0, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x0, y0, z0), dx, dy, dz).Shape()


saft = cyl(4, 40)
YP = {
    "imbus silindir başlı": (cut(fuse(saft, cyl(6.5, 8, 40)), hexa(6, 4, 44)),
                             ["silindir başlı", "imbus"]),
    "torx silindir başlı": (cut(fuse(saft, cyl(6.5, 8, 40)), yildiz(1.9, 2.8, 6, 4, 44)),
                            ["silindir başlı", "torx"]),
    "yıldız silindir başlı": (cut(cut(fuse(saft, cyl(6.5, 5, 40)), kutu_(-3, -0.6, 42, 6, 1.2, 3)),
                                  kutu_(-0.6, -3, 42, 1.2, 6, 3)), ["yıldız"]),
    "düz (yarık) silindir başlı": (cut(fuse(saft, cyl(6.5, 5, 40)), kutu_(-8, -0.6, 43, 16, 1.2, 2)),
                                   ["düz (yarık)"]),
    "havşa başlı imbus": (cut(fuse(saft, _Koni(gp_Ax2(gp_Pnt(0, 0, 40), gp_Dir(0, 0, 1)),
                                               4, 8, 4).Shape()), hexa(5, 3, 41)),
                          ["havşa başlı", "imbus"]),
    "bombe başlı imbus (ISO 7380)": (cut(fuse(saft, cut(BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 34), 10.4).Shape(),
                                                         kutu_(-20, -20, 14, 40, 40, 26))),
                                         hexa(5, 3, 42.4)), ["bombe başlı", "imbus"]),
    "altıköşe flanşlı başlı": (fuse(fuse(saft, cyl(9, 1.5, 40)), hexa(13, 6, 41.5)),
                               ["altıköşe flanşlı"]),
    "kare başlı": (fuse(saft, prizma([(-6.5, -6.5), (6.5, -6.5), (6.5, 6.5), (-6.5, 6.5)], 6, 40)),
                   ["kare başlı"]),
    "kronlu somun": (cut(cut(cut(cut(hexa(17, 13), cyl(5, 13)), kutu_(-10, -1.5, 9, 20, 3, 4)),
                             BRepBuilderAPI_Transform(kutu_(-10, -1.5, 9, 20, 3, 4), _don(60), True).Shape()),
                         BRepBuilderAPI_Transform(kutu_(-10, -1.5, 9, 20, 3, 4), _don(120), True).Shape()),
                     ["kronlu"]),
    "kapalı somun": (cut(fuse(hexa(17, 9), cut(BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 9), 7).Shape(),
                                               kutu_(-9, -9, 0, 18, 18, 9))), cyl(5, 12)),
                     ["kapalı"]),
    "manşon somun": (cut(hexa(13, 30), cyl(4, 30)), ["manşon"]),
    "setskur": (cut(cyl(4, 12), hexa(4, 3, 9)), ["setskur", "imbus"]),
}
for ad, (sh, beklenen) in YP.items():
    for d in (False, True):
        r = Y.yapisal_tani(dondur(sh) if d else sh)
        ok = bool(r) and r[0] == "standart" and r[3] and all(b in r[1] for b in beklenen)
        print(f"  {'tamam' if ok else 'HATA '} {ad:30s} {'döndü' if d else '     '} "
              f"{(r[1] + ' | ' + r[2]) if r else '(karar yok)'}")
        if not ok:
            HATA.append("yapı " + ad)
# rulman: iç halka + dış halka + 8 bilye (bileşik katı), 6204 ölçüsünde
from OCP.TopoDS import TopoDS_Compound                          # noqa: E402
from OCP.BRep import BRep_Builder                               # noqa: E402
_b, _rul = BRep_Builder(), TopoDS_Compound()
_b.MakeCompound(_rul)
_b.Add(_rul, cut(cyl(14.5, 14), cyl(10, 14)))
_b.Add(_rul, cut(cyl(23.5, 14), cyl(19.5, 14)))
for _i in range(8):
    _a = math.radians(45 * _i)
    _b.Add(_rul, BRepPrimAPI_MakeSphere(gp_Pnt(17 * math.cos(_a), 17 * math.sin(_a), 7), 3.4).Shape())
for ad, sh, bek, kesin in (
        ("rulman 6204", _rul, "6204", True),
        ("dış dişli pul", cut(yildiz(9, 10.5, 12, 0.8), cyl(4.3, 0.8)), "dış dişli", True),
        ("yaylı (grover) pul", cut(cut(cyl(7.5, 1.6), cyl(4.2, 1.6)), kutu_(3.5, -0.4, 0, 5, 0.8, 1.6)),
         "yaylı", True),
        ("düz pul (yalnız aday)", cut(cyl(8, 1.6), cyl(4.3, 1.6)), "düz pul", False)):
    for d in (False, True):
        r = Y.yapisal_tani(dondur(sh) if d else sh)
        ok = bool(r) and bek in r[1] and r[3] == kesin
        print(f"  {'tamam' if ok else 'HATA '} {ad:30s} {'döndü' if d else '     '} "
              f"{(r[1] + ' | ' + r[2]) if r else '(karar yok)'}")
        if not ok:
            HATA.append("yapı " + ad)
u = fuse(fuse(cyl(4, 60, 0), BRepBuilderAPI_Transform(cyl(4, 60, 0), _kaydir(40, 0, 0), True).Shape()),
         BRepBuilderAPI_Transform(BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(20, 0, 0), gp_Dir(0, 1, 0)),
                                                        20, 4, math.pi).Shape(), _don_x(180), True).Shape())
r = Y.bukulmus_cubuk(u)
ok = bool(r) and "Ø8" in r[0]
print(f"  {'tamam' if ok else 'HATA '} U cıvata (bükülmüş çubuk)          {r[0] if r else '(yok)'}")
if not ok:
    HATA.append("yapı U cıvata")
for ad, sh in (("kademeli mil", fuse(cyl(15, 100), cyl(10, 40, 100))),
               ("flanş", cut(fuse(cyl(40, 10), cyl(20, 30, 10)), cyl(12, 40))),
               ("delikli kare plaka", cut(prizma([(-12, -12), (12, -12), (12, 12), (-12, 12)], 3),
                                          cyl(5.5, 3)))):
    r = Y.yapisal_tani(sh)
    ok = not (r and r[3])
    print(f"  {'tamam' if ok else 'HATA '} {ad:30s} kesin karar yok: {r[1] if r else '-'}")
    if not ok:
        HATA.append("yapı " + ad)

print("\n-- YAY: spir yapısı (tel kesiti her 90°'de çeyrek adım kayar) + uç türü")
from OCP.Geom import Geom_CylindricalSurface, Geom_ConicalSurface  # noqa: E402
from OCP.Geom2d import Geom2d_Line                               # noqa: E402
from OCP.gp import gp_Ax3, gp_Pnt2d, gp_Dir2d, gp_Circ           # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire  # noqa: E402
from OCP.BRepLib import BRepLib                                   # noqa: E402
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell        # noqa: E402
from OCP.BRepAdaptor import BRepAdaptor_CompCurve                # noqa: E402
from OCP.BRep import BRep_Builder                                # noqa: E402
from OCP.TopoDS import TopoDS_Compound                           # noqa: E402


def helis(R, adim, tur, d, konik=0.0, sol=False):
    """Tel çapı d, orta yarıçap R, hatve adim, tur sarım; iki uç noktası da döner."""
    ax = gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    if konik:
        yuz = Geom_ConicalSurface(ax, math.radians(konik), R)
        va = adim / math.cos(math.radians(konik))
    else:
        yuz, va = Geom_CylindricalSurface(ax, R), adim
    lin = Geom2d_Line(gp_Pnt2d(0, 0), gp_Dir2d(-2 * math.pi if sol else 2 * math.pi, va))
    e = BRepBuilderAPI_MakeEdge(lin, yuz, 0.0, tur * math.hypot(2 * math.pi, va)).Edge()
    BRepLib.BuildCurves3d_s(e)
    w = BRepBuilderAPI_MakeWire(e).Wire()
    c = BRepAdaptor_CompCurve(w)
    p0, v0, p1, v1 = gp_Pnt(), gp_Vec(), gp_Pnt(), gp_Vec()
    c.D1(c.FirstParameter(), p0, v0)
    c.D1(c.LastParameter(), p1, v1)
    prof = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(
        gp_Circ(gp_Ax2(p0, gp_Dir(v0)), d / 2)).Edge()).Wire()
    ps = BRepOffsetAPI_MakePipeShell(w)
    ps.SetMode(gp_Dir(0, 0, 1))
    ps.Add(prof)
    ps.Build()
    ps.MakeSolid()
    return ps.Shape(), p0, p1


def cyl_yon(p, d, r, h):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(p, d), r, h).Shape()


def cekme_yayi():
    sh, _a, _b = helis(5, 1.02, 10, 1.0)
    zt = 10 * 1.02
    for zc in (zt + 5, -5):
        sh = fuse(sh, BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(0, 0, zc), gp_Dir(1, 0, 0)), 5, 0.5).Shape())
    return sh


def burulma_yayi(bukum=False):
    """sık sarım + teğet bacak; bukum: bacak ucu eksene paralel bükülür
    (sarımın yanından boydan boya iner - gerçek modeldeki gibi)."""
    sh, a, b = helis(3, 0.84, 5, 0.8)
    # bacaklar önce kendi aralarında birleşir: helis ucuna tek tek eklenince
    # OCC birleştirmesi sarımı kaybedebiliyor (hacim denetlenir)
    bacak = None
    for p in (a, b):
        parca = cyl_yon(p, gp_Dir(0, -1, 0), 0.4, 8)
        if bukum:
            uc = gp_Pnt(p.X(), p.Y() - 8, p.Z())
            parca = fuse(parca, cyl_yon(uc, gp_Dir(0, 0, 1) if p.Z() < 1 else gp_Dir(0, 0, -1),
                                        0.4, 4))
        bacak = parca if bacak is None else fuse(bacak, parca)
    return fuse(sh, bacak)


def disk_paketi():
    bld, cmp = BRep_Builder(), TopoDS_Compound()
    bld.MakeCompound(cmp)
    for i in range(6):
        up = i % 2 == 0
        dis = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, 3.0 * i), gp_Dir(0, 0, 1)),
                                   20 if up else 10.5, 10.5 if up else 20, 1.5).Shape()
        bld.Add(cmp, cut(dis, cyl(10.2, 4, 3.0 * i - 1)))
    return cmp


YAY = (("basma yayı", helis(8, 5, 8, 1.6)[0], "basma yayı", "sağ"),
       ("basma yayı (sol helis)", helis(8, 5, 8, 1.6, sol=True)[0], "basma yayı", "sol"),
       ("çekme yayı (halkalı)", cekme_yayi(), "çekme yayı", "sağ"),
       ("burulma yayı (bacaklı)", burulma_yayi(), "burulma yayı", "sağ"),
       ("burulma yayı (bükülü bacak)", burulma_yayi(True), "burulma yayı", "sağ"),
       ("konik basma yayı", helis(12, 6, 6, 2.0, konik=-8)[0], "konik basma yayı", "sağ"))
for ad, sh, bek, yon in YAY:
    for d in (False, True):
        r = T.tani(dondur(sh) if d else sh)
        ok = bool(r) and r[0] == "standart" and r[1].startswith(bek) and f"{yon} helis" in r[2]
        print(f"  {'tamam' if ok else 'HATA '} {ad:30s} {'döndü' if d else '     '} "
              f"{(r[1] + ' | ' + r[2]) if r else '(karar yok)'}")
        if not ok:
            HATA.append("yay " + ad)
r = Y.yay(helis(8, 5, 8, 1.6)[0])
ok = bool(r) and "dış Ø17,6" in r[2] and "adım 5," in r[2]
print(f"  {'tamam' if ok else 'HATA '} basma yayı ölçüsü (dış Ø17,6, adım 5)  {r[2] if r else '-'}")
if not ok:
    HATA.append("yay ölçüsü")
# yay OLMAYAN: katmanlar dönmeden aynı (disk paketi) karar değil, en çok aday;
# dişi modellenmiş cıvata içi dolu
for ad, sh in (("disk yay paketi (aday olabilir)", disk_paketi()),
               ("dişli cıvata", fuse(cyl(4.4, 25), helis(4.6, 1.25, 20, 1.0)[0])),
               ("boru", cut(cyl(10, 60), cyl(9, 60))),
               ("o-ring", BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 8, 1.5).Shape())):
    r = Y.yay(sh)
    ok = not (r and r[3])
    print(f"  {'tamam' if ok else 'HATA '} {ad:30s} kesin yay kararı yok: {r[1] if r else '-'}")
    if not ok:
        HATA.append("yay değil " + ad)

print("\n-- STANDART AİLELER (pf13_aile): segman, yaylı pim, kama, konik pim, gres nipeli")
import pf13_aile as A                                            # noqa: E402


def kutu(x, y, z, a, b, c):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), a, b, c).Shape()


def cyl(r, h, z=0, x=0, y=0):                                     # noqa: F811
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), r, h).Shape()


def segman_471(d1=20, s=1.2, d3=18.5, a=4.0, d5=2.0, b=2.6):
    """mil segmanı: iç çap d3 (eş merkezli), dış kenar EKSANTRİK (boşluğun
    karşısında en geniş b), boşluğun iki yanında dışa taşan delikli kulaklar."""
    ri = d3 / 2
    e = 0.45 * b                            # eksantriklik (-x yönüne)
    ro = ri + b - e
    r = cut(cyl(ro, s, 0, -e, 0), cyl(ri, s))
    acik = 0.18 * d1
    r = cut(r, kutu(0, -acik / 2, 0, ro + 5, acik, s))
    for sgn in (1, -1):
        yc = sgn * (acik / 2 + a / 2)
        xc = ri + a * 0.45
        r = fuse(r, cyl(a / 2, s, 0, xc, yc))
        r = cut(r, cyl(d5 / 2, s, 0, xc, yc))
    return cut(r, cyl(ri, s))


def segman_472(d1=20, s=1.0, d3=21.5, a=4.1, d5=2.0, b=2.4):
    """delik segmanı: dış çap d3 (eş merkezli), iç kenar EKSANTRİK, kulaklar içe."""
    ro = d3 / 2
    e = 0.45 * b
    ri = ro - b + e
    r = cut(cyl(ro, s), cyl(ri, s, 0, e, 0))
    acik = 0.18 * d1
    r = cut(r, kutu(0, -acik / 2, 0, ro + 5, acik, s))
    for sgn in (1, -1):
        yc = sgn * (acik / 2 + a / 2)
        xc = ro - a * 0.45
        r = fuse(r, cut(cyl(a / 2, s, 0, xc, yc), cut(cyl(ro + 5, s), cyl(ro, s))))
        r = cut(r, cyl(d5 / 2, s, 0, xc, yc))
    return r


def e_segman(s=0.7, d2=6, d3=12.3):
    """DIN 6799: dış Ø d3, iç yuva, açık ağız ~120°, üç iç tırnak."""
    r = cut(cyl(d3 / 2, s), cyl(d2 / 2 + 1.2, s))
    # ağız: +x yönünde geniş açıklık
    r = cut(r, prizma([(0, 0), (d3, -d3 * 0.8), (d3, d3 * 0.8)], s))
    for ang in (180, 70, -70):
        a = math.radians(ang)
        x, y = (d2 / 2 + 0.6) * math.cos(a), (d2 / 2 + 0.6) * math.sin(a)
        r = fuse(r, cyl(0.7, s, 0, x, y))
    return r


def yayli_pim(d=6, L=30, s=1.2, yarik=1.0, pah=0.6):
    t = cut(cyl(d / 2, L), cyl(d / 2 - s, L))
    t = cut(t, kutu(-yarik / 2, 0, 0, yarik, d, L))
    # uç pahları (dış): koni kesimi
    for z0, yon in ((0, 1), (L, -1)):
        k = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, z0 - yon * 0.001), gp_Dir(0, 0, yon)),
                                 d / 2 - pah, d / 2 + 0.001, pah).Shape()
        dis = cut(cyl(d, pah + 0.002, z0 if yon == 1 else z0 - pah - 0.002), k)
        t = cut(t, dis)
    return t


def kama_a(b=8, h=7, L=40):
    """DIN 6885 A: uçları yarım daire (R = b/2)."""
    orta = kutu(-(L / 2 - b / 2), -b / 2, 0, L - b, b, h)
    return fuse(fuse(orta, cyl(b / 2, h, 0, -(L / 2 - b / 2), 0)), cyl(b / 2, h, 0, L / 2 - b / 2, 0))


def kama_b(b=8, h=7, L=40):
    return kutu(-L / 2, -b / 2, 0, L, b, h)


def konik_pim(d=6, L=40):
    """ISO 2339: 1:50 koniklik, d küçük uç."""
    D = d + L / 50.0
    return BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), d / 2, D / 2, L).Shape()


def gres_nipeli(M=8, s=9):
    """DIN 71412 A: diş gövdesi + altıköşe + boyun + küre baş + eksenel delik."""
    g = cyl(M / 2, 5.5)
    g = fuse(g, hexa(s, 5, 5.5))
    g = fuse(g, cyl(2.3, 3, 10.5))
    g = fuse(g, BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 14.2), 3.25).Shape())
    return cut(g, cyl(1.0, 20, -1))



AILE = (("mil segmanı", segman_471(), "mil segmanı (DIN 471)", True),
        ("delik segmanı", segman_472(), "delik segmanı (DIN 472)", True),
        ("E-segman", e_segman(), "E-segman (DIN 6799)", True),
        ("yaylı pim", yayli_pim(), "yaylı pim (ISO 8752", True),
        ("kama A", kama_a(), "paralel kama (DIN 6885 A)", True),
        ("konik pim", konik_pim(), "konik pim (ISO 2339", True),
        ("gres nipeli", gres_nipeli(), "gres nipeli (DIN 71412 A)", True))
for ad, sh, bek, _k in AILE:
    for d in (False, True):
        r = T.tani(dondur(sh) if d else sh)
        ok = bool(r) and r[0] == "standart" and r[1].startswith(bek)
        print(f"  {'tamam' if ok else 'HATA '} {ad:30s} {'döndü' if d else '     '} "
              f"{(r[1] + ' | ' + r[2]) if r else '(karar yok)'}")
        if not ok:
            HATA.append("aile " + ad)
def setskur(uc="duz", d=8, L=12):
    """imbus setskur: üstte altıgen lokma; alt uç: duz / konik / pim / canak."""
    r = d / 2
    g = cyl(r, L)
    g = cut(g, hexa(4, 3.5, L - 3.5))
    if uc == "duz":
        k = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), r - 0.6, r + 0.001, 0.6).Shape()
        g = cut(g, cut(cyl(r + 1, 0.6), k))
    elif uc == "konik":
        k = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0.2, r, 3.0).Shape()
        g = fuse(cut(g, cyl(r + 1, 3.0)), k)
    elif uc == "pim":
        g = fuse(cut(g, cyl(r + 1, 3.0)), cyl(0.6 * r, 3.0))
    elif uc == "canak":
        k = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0.6 * r, 0.05, 1.5).Shape()
        g = cut(g, k)
    return g


def cekmeli_pim(d=8, L=30, M=5, derin=10):
    """ISO 8735 / DIN 7979: dolu silindir, bir ucunda iç dişli kör delik (çekirdek Ø)."""
    g = cyl(d / 2, L)
    for z0, yon in ((0, 1), (L, -1)):
        k = BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(0, 0, z0 - yon * 0.001), gp_Dir(0, 0, yon)),
                                 d / 2 - 0.5, d / 2 + 0.001, 0.5).Shape()
        g = cut(g, cut(cyl(d, 0.502, z0 if yon == 1 else z0 - 0.502), k))
    return cut(g, cyl(0.84 * M / 2, derin, L - derin))


for uc, bek in (("duz", "düz uç (DIN 913)"), ("konik", "konik uç (DIN 914)"),
                ("pim", "pim uç (DIN 915)"), ("canak", "çanak uç (DIN 916)")):
    for L in (12, 20):
        for d in (False, True):
            sh = setskur(uc, L=L)
            r = T.tani(dondur(sh) if d else sh)
            ok = bool(r) and "setskur" in r[1] and bek in r[1]
            print(f"  {'tamam' if ok else 'HATA '} setskur {uc:6s} L{L} {'döndü' if d else '     '} "
                  f"{r[1] if r else '(karar yok)'}")
            if not ok:
                HATA.append(f"setskur {uc} {L}")
for d_, L_, M_ in ((6, 24, 4), (8, 30, 5), (10, 40, 6)):
    r = T.tani(cekmeli_pim(d_, L_, M_))
    ok = bool(r) and r[1].startswith("çekmeli") and f"M{M_}" in r[2]
    print(f"  {'tamam' if ok else 'HATA '} çekmeli pim Ø{d_} -> M{M_}          {r[1] if r else '-'}")
    if not ok:
        HATA.append(f"çekmeli pim {d_}")
r = T.tani(pahla(cyl(3, 30)))
ok = bool(r) and r[1].startswith("silindirik pim")
print(f"  {'tamam' if ok else 'HATA '} pahlı dolu pim -> silindirik pim     {r[1] if r else '-'}")
if not ok:
    HATA.append("silindirik pim")
r = A.aile_tani(kama_b())
ok = bool(r) and not r[3] and "6885 B" in r[1]
print(f"  {'tamam' if ok else 'HATA '} kama B yalnız ADAY (lama olabilir)   {r[1] if r else '-'}")
if not ok:
    HATA.append("aile kama B")
# AİLE OLMAYAN: kapalı pul pul kalır; grover, düz plaka, kapalı boru, dolu
# pim, somun, büyük C biçimli sac aileye girmez
for ad, sh, bek in (("düz pul", cut(cyl(8, 1.6), cyl(4.3, 1.6)), "pul"),
                    ("grover pul", cut(cut(cyl(7.5, 1.6), cyl(4.2, 1.6)),
                                       kutu(3.5, -0.4, 0, 5, 0.8, 1.6)), None),
                    ("delikli plaka", cut(kutu(-20, -15, 0, 40, 30, 3), cyl(5, 3)), None),
                    ("kapalı boru", cut(cyl(3, 30), cyl(1.8, 30)), None),
                    ("dolu pim", cyl(3, 30), None),
                    ("C biçimli sac (Ø120)", cut(cut(cyl(60, 3), cyl(40, 3)),
                                                  kutu(0, -25, 0, 70, 50, 3)), None),
                    ("somun", cut(hexa(13, 6.5), cyl(4, 6.5)), None)):
    r = A.aile_tani(sh)
    ok = not (r and r[3])
    if bek:
        r2 = T.tani(sh)
        ok = ok and bool(r2) and r2[1] == bek
    print(f"  {'tamam' if ok else 'HATA '} {ad:30s} aileye girmedi: {r[1] if r else '-'}")
    if not ok:
        HATA.append("aile değil " + ad)

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

print("\n-- KISA ekstrüzyon (boy < 3 x kesit): yalnız kesit güçlüyse profil")
# TIRSAN_Ray 112,5 gibi: 150 mm boyunda 100 x 80 kesit, 3 hücre + T-kanal
kx = cut(cut(cut(kutu_(0, 0, 0, 100, 80, 150), kutu_(4, 4, -1, 28, 72, 152)),
             kutu_(36, 4, -1, 28, 72, 152)), kutu_(68, 4, -1, 28, 72, 152))
kx = cut(cut(kx, kutu_(44, 74, -1, 12, 7, 152)), kutu_(40, 76, -1, 20, 2, 152))
r = T.profil(kx)
ok = bool(r) and r["tur"] == "ekstrüzyon"
print(f"  {'tamam' if ok else 'HATA '} 150 mm, 3 hücreli kesit ekstrüzyon     {r['ad'] if r else '(yok)'}")
if not ok:
    HATA.append("kısa ekstrüzyon")
# 17 x 99 x 100 lama, iki oluk: kısa + zayıf kanıt -> profil DEĞİL
lm = cut(cut(kutu_(0, 0, 0, 99, 17, 100), kutu_(20, 14, -1, 6, 4, 102)), kutu_(73, 14, -1, 6, 4, 102))
r = T.profil(lm)
ok = not r
print(f"  {'tamam' if ok else 'HATA '} 17 x 99 x 100 oluklu lama profil değil  {r['ad'] if r else '(yok)'}")
if not ok:
    HATA.append("kısa lama")

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
         "hacim_mm3": 100.0 * (i + 1), "olc": [i + 1.0, 10.0, 20.0]}
        for i, (a, _s) in enumerate(ogr)]
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

print("\n-- standart ürün kataloğu: tedarikçi STEP'i klasöre konur")
import tempfile                                                  # noqa: E402
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs  # noqa: E402
kd = tempfile.mkdtemp(prefix="katalog_")
os.makedirs(os.path.join(kd, "tedarikci"))
w = STEPControl_Writer()
w.Transfer(ogr[1][1], STEPControl_AsIs)                         # M8 perçin somun
w.Write(os.path.join(kd, "tedarikci", "rivnut M8.stp"))
kat = M.katalog_imzalari(kd, log=lambda t: None)
ok = len(kat) == 1 and kat[0][1] == "tedarikci / rivnut M8"
print(f"  {'tamam' if ok else 'HATA '} katalog STEP'i okundu: {[e for _i, e in kat]}")
if not ok:
    HATA.append("katalog okuma")
ok = os.path.isfile(os.path.join(kd, ".pi3d_katalog.json"))
print(f"  {'tamam' if ok else 'HATA '} imza önbelleğe yazıldı (bir daha okunmaz)")
if not ok:
    HATA.append("katalog önbellek")
komp = [{"ad": a, "kod": a, "sinif": "parca", "tip": "", "indeks": [i],
         "hacim_mm3": 100.0 * (i + 1), "olc": [i + 1.0, 10.0, 20.0]}
        for i, (a, _s) in enumerate(ogr)]
n = M.katalogdan_sinifla(kayit, komp, {}, katalog=M.katalog_imzalari(kd, log=lambda t: None),
                         log=lambda t: None)
for k, bek in zip(komp, ("standart", "standart", "parca", "parca", "parca")):
    ok = k["sinif"] == bek
    print(f"  {'tamam' if ok else 'HATA '} {k['ad']:30s} {k['sinif']} {k['tip']}")
    if not ok:
        HATA.append("katalog " + k["ad"])
import pf12_katalog as KT                                        # noqa: E402
KT.ornek_uret(kd)
pf = KT.paftalar(kd, log=lambda t: None)
ok = 1 <= len(pf) <= KT.PAFTA_EN_COK and all(b[:4] == b"\x89PNG" for b in pf)
print(f"  {'tamam' if ok else 'HATA '} katalog resimleri paftalandı ({len(pf)} pafta)")
if not ok:
    HATA.append("katalog pafta")
shutil.rmtree(kd, ignore_errors=True)

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
