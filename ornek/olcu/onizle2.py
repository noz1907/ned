import ezdxf, math, sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
def topla(e, segs, yazi, kat_ovr=None):
    k = kat_ovr or (e.dxf.layer if e.dxf.layer in segs else "DIGER")
    t = e.dxftype()
    try:
        if t == "LWPOLYLINE":
            p = [(a,b) for a,b in e.get_points('xy')]
            for a,b in zip(p,p[1:]): segs[k].append([a,b])
        elif t == "LINE":
            segs[k].append([(e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y)])
        elif t in ("CIRCLE","ARC"):
            c=e.dxf.center; r=e.dxf.radius
            a0,a1=(0,360) if t=="CIRCLE" else (e.dxf.start_angle,e.dxf.end_angle)
            if a1<a0: a1+=360
            p=[(c.x+r*math.cos(math.radians(a)), c.y+r*math.sin(math.radians(a))) for a in [a0+(a1-a0)*i/24 for i in range(25)]]
            for a,b in zip(p,p[1:]): segs[k].append([a,b])
        elif t == "SOLID":
            v=[e.dxf.vtx0,e.dxf.vtx1,e.dxf.vtx2]
            segs[k].append([(v[0].x,v[0].y),(v[1].x,v[1].y)]); segs[k].append([(v[1].x,v[1].y),(v[2].x,v[2].y)])
        elif t == "TEXT":
            yazi.append((e.dxf.text, e.dxf.insert.x, e.dxf.insert.y, e.dxf.height))
        elif t == "MTEXT":
            yazi.append((e.text, e.dxf.insert.x, e.dxf.insert.y, e.dxf.char_height))
    except Exception: pass
def ciz(dosya, cikti, baslik, kirp=None):
    d = ezdxf.readfile(dosya); m = d.modelspace()
    segs = {"GORUNEN":[], "GIZLI":[], "OLCU":[], "EKSEN":[], "YAZI":[], "DIGER":[]}
    yazi=[]
    for e in m:
        if e.dxftype()=="DIMENSION":
            try:
                blk = d.blocks.get(e.dxf.geometry)
                for e2 in blk: topla(e2, segs, yazi, "OLCU")
            except Exception: pass
        else: topla(e, segs, yazi)
    fig, ax = plt.subplots(figsize=(19,13))
    renk = {"GORUNEN":("#111",1.0),"GIZLI":("#b00",0.5),"OLCU":("#06c",0.6),
            "EKSEN":("#a0a",0.4),"YAZI":("#060",0.5),"DIGER":("#888",0.4)}
    for k,v in segs.items():
        if v: ax.add_collection(LineCollection(v, colors=renk[k][0], linewidths=renk[k][1]))
    for t,x,y,h in yazi:
        ax.text(x, y, str(t).replace("%%c","Ø"), fontsize=max(4,min(13,h*1.25)), color="#036", family="monospace")
    ax.set_aspect("equal")
    if kirp: ax.set_xlim(kirp[0],kirp[2]); ax.set_ylim(kirp[1],kirp[3])
    else: ax.autoscale()
    ax.grid(True, lw=.2, alpha=.3); ax.set_title(baslik, fontsize=12)
    fig.tight_layout(); fig.savefig(cikti, dpi=100); plt.close(fig)
    print(cikti)
ciz(sys.argv[1], sys.argv[2], sys.argv[3], [float(v) for v in sys.argv[4].split(",")] if len(sys.argv)>4 else None)
