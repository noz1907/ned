"""Bilinen bir katıdan 3 görünüş DXF üret, çeviriciyle geri kur, hacmi karşılaştır."""
import sys, math; sys.path.insert(0, "/home/user/ned")
import cadquery as cq, ezdxf
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_TangentialDeflection

GOR = {"ON": ((0,-1,0),(1,0,0)), "UST": ((0,0,1),(1,0,0)), "SAG": ((1,0,0),(0,1,0))}

def kenarlar(shape, goz, xref):
    algo = HLRBRep_Algo(); algo.Add(shape)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0,0,0), gp_Dir(*goz), gp_Dir(*xref))))
    algo.Update(); algo.Hide()
    hs = HLRBRep_HLRToShape(algo)
    out=[]
    for sh in (hs.VCompound(), hs.OutLineVCompound(), hs.HCompound(), hs.OutLineHCompound()):
        if sh.IsNull(): continue
        ex = TopExp_Explorer(sh, TopAbs_EDGE)
        while ex.More():
            c = BRepAdaptor_Curve(TopoDS.Edge_s(ex.Current()))
            d = GCPnts_TangentialDeflection(c, 0.02, 0.05)
            p = [c.Value(d.Parameter(i)) for i in range(1, d.NbPoints()+1)]
            out.append([(q.X(), q.Y()) for q in p]); ex.Next()
    return out

def dxf_yaz(kati, yol, bosluk=60.0):
    doc = ezdxf.new("R2010"); msp = doc.modelspace()
    for k in ("GORUNEN","YAZI"): doc.layers.add(k)
    bb = kati.BoundingBox(); W,D,H = bb.xlen, bb.ylen, bb.zlen
    yer = {"ON": (0,0), "UST": (0, H+bosluk), "SAG": (W+bosluk, 0)}
    for ad,(goz,xref) in GOR.items():
        pl = kenarlar(kati.wrapped, goz, xref)
        ox,oy = yer[ad]
        xs=[p[0] for c in pl for p in c]; ys=[p[1] for c in pl for p in c]
        dx,dy = ox-min(xs), oy-min(ys)
        for c in pl:
            msp.add_lwpolyline([(x+dx, y+dy) for x,y in c], dxfattribs={"layer":"GORUNEN"})
        msp.add_text(ad, dxfattribs={"layer":"YAZI","height":6}).set_placement((ox+ (max(xs)-min(xs))/2, oy-14))
    doc.saveas(yol)
    return (W,D,H)

# --- test cismi: L kesitli, delikli, centikli plaka
kati = (cq.Workplane("XY").box(120, 80, 24, centered=False)
        .faces(">Z").workplane().pushPoints([(30,25),(90,55)]).hole(12)
        .edges("|Z and >X").chamfer(8))
kati = kati.cut(cq.Workplane("XY").box(40, 30, 10, centered=False).translate((0,0,14)))
kati = kati.val()
print(f"kaynak kati: hacim={kati.Volume():.1f} mm3  kutu={[round(v,1) for v in (kati.BoundingBox().xlen, kati.BoundingBox().ylen, kati.BoundingBox().zlen)]}")
W,D,H = dxf_yaz(kati, "test_3gorunus.dxf")
cq.exporters.export(cq.Workplane().add(kati), "test_kaynak.step")

import pfd_dxf2stp as D
P = dict(D.VARSAYILAN)
c = D.Cizim("test_3gorunus.dxf", P)
b, cer, _ = D.bolgele(c, P)
print(f"okunan: {len(c.atom)} atom, {len(b)} bolge")
for r in b: print(f"   #{r.no} etiket={r.etiket} G={r.g:.2f} Y={r.y:.2f} yuz={len(r.poligonla(P))}")
nes = D.nesne_esle(b, P)
print(f"{len(nes)} nesne")
for n in nes:
    k = D.nesne_kur(n, P)
    print("  ", n.ozet())
    if k is not None:
        v = sum(s.Volume() for s in k.Solids())
        print(f"   -> kurulan hacim={v:.1f} mm3   fark={100*(v-kati.Volume())/kati.Volume():+.2f}%")
        cq.exporters.export(cq.Workplane().add(k), "test_kurulan.step")
