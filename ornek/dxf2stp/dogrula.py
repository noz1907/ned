"""Uretilen katilari kaynak gorunuslerle yan yana ciz."""
import sys, math, json; sys.path.insert(0,'/home/user/ned')
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon as MPoly
import cadquery as cq
import pfd_dxf2stp as D
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_TangentialDeflection

def izdusum(shape, goz, xref):
    a = HLRBRep_Algo(); a.Add(shape)
    a.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0,0,0), gp_Dir(*goz), gp_Dir(*xref))))
    a.Update(); a.Hide()
    hs = HLRBRep_HLRToShape(a); out=[]
    for sh in (hs.VCompound(), hs.OutLineVCompound()):
        if sh.IsNull(): continue
        ex = TopExp_Explorer(sh, TopAbs_EDGE)
        while ex.More():
            c = BRepAdaptor_Curve(TopoDS.Edge_s(ex.Current()))
            d = GCPnts_TangentialDeflection(c, 0.05, 0.1)
            p=[c.Value(d.Parameter(i)) for i in range(1,d.NbPoints()+1)]
            out.append([(q.X(),q.Y()) for q in p]); ex.Next()
    return out

P = dict(D.VARSAYILAN)
ciz = D.Cizim('fikstur_2xls.dxf', P)
ciz.atom = [q for q in ciz.atom if -441300 <= (q["kutu"][0]+q["kutu"][2])/2 <= -440000
            and 420000 <= (q["kutu"][1]+q["kutu"][3])/2 <= 425000]
ciz.segment = [s for q in ciz.atom for s in q["seg"]]
bol, cer, _ = D.bolgele(ciz, P)
nes = D.nesne_esle(bol, P)
for n in nes:
    try: D.nesne_kur(n, P)
    except Exception as e: n.not_.append(str(e))
kurulan = [n for n in nes if n.kati is not None]
print(f"{len(kurulan)} kati")

fig, axs = plt.subplots(len(kurulan), 4, figsize=(19, 3.4*len(kurulan)))
if len(kurulan)==1: axs=[axs]
for r,(n,sat) in enumerate(zip(kurulan, axs)):
    # sol sutun: kaynak gorunusler
    ax = sat[0]
    for b in n.gorunus:
        al = b.dolu_alan(P)
        if al is None: continue
        for pg in (list(al.geoms) if al.geom_type=="MultiPolygon" else [al]):
            ax.add_patch(MPoly(list(pg.exterior.coords), closed=True, fc="#9cf", ec="#036", lw=.7, alpha=.7))
            for h in pg.interiors:
                ax.add_patch(MPoly(list(h.coords), closed=True, fc="white", ec="#036", lw=.7))
        ax.text(b.merkez[0], b.y1, f"#{b.no} {n.rol.get(b.no)}", fontsize=7, ha="center", color="#036")
    ax.set_aspect("equal"); ax.autoscale(); ax.set_title(f"N{n.no:03d} KAYNAK GORUNUSLER", fontsize=8)
    ax.tick_params(labelsize=6)
    # sag uc sutun: kurulan katinin izdusumleri
    for ci,(ad,goz,xr) in enumerate((("ON (kurulan)",(0,-1,0),(1,0,0)),
                                     ("UST (kurulan)",(0,0,1),(1,0,0)),
                                     ("SAG (kurulan)",(1,0,0),(0,1,0)))):
        ax = sat[1+ci]
        pl = izdusum(n.kati.wrapped, goz, xr)
        if pl: ax.add_collection(LineCollection([[(x,y) for x,y in c] for c in pl], colors="#900", linewidths=.8))
        ax.set_aspect("equal"); ax.autoscale(); ax.grid(True, lw=.2, alpha=.4)
        o = n.olcu
        ax.set_title(f"{ad}  {o[0]:.0f}x{o[1]:.0f}x{o[2]:.0f}", fontsize=8); ax.tick_params(labelsize=6)
fig.suptitle("Solda DXF'ten okunan gorunusler - sagda uretilen katinin izdusumleri", fontsize=11)
fig.tight_layout(); fig.savefig("dogrulama.png", dpi=85); plt.close(fig)
print("dogrulama.png yazildi")
