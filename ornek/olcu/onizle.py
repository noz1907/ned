import ezdxf, math, sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
def ciz(dosya, cikti, baslik):
    d = ezdxf.readfile(dosya); m = d.modelspace()
    segs = {"GORUNEN":[], "GIZLI":[], "OLCU":[], "DIGER":[]}
    yazi = []
    for e in m:
        k = e.dxf.layer if e.dxf.layer in segs else "DIGER"
        t = e.dxftype()
        try:
            if t == "LWPOLYLINE":
                p = [(a,b) for a,b in e.get_points('xy')]
                for a,b in zip(p,p[1:]): segs[k].append([a,b])
            elif t == "LINE":
                segs[k].append([(e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y)])
            elif t == "TEXT":
                yazi.append((e.dxf.text, e.dxf.insert.x, e.dxf.insert.y, e.dxf.height))
        except Exception: pass
    for blk in m.query('INSERT'):
        try:
            for e in blk.virtual_entities():
                k = e.dxf.layer if e.dxf.layer in segs else "DIGER"
                if e.dxftype()=="LINE": segs[k].append([(e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y)])
                elif e.dxftype()=="LWPOLYLINE":
                    p=[(a,b) for a,b in e.get_points('xy')]
                    for a,b in zip(p,p[1:]): segs[k].append([a,b])
                elif e.dxftype()=="MTEXT": yazi.append((e.text, e.dxf.insert.x, e.dxf.insert.y, e.dxf.char_height))
        except Exception: pass
    fig, ax = plt.subplots(figsize=(17,12))
    renk = {"GORUNEN":("#111",0.7),"GIZLI":("#b00",0.3),"OLCU":("#06c",0.5),"DIGER":("#888",0.4)}
    for k,v in segs.items():
        if v: ax.add_collection(LineCollection(v, colors=renk[k][0], linewidths=renk[k][1]))
    for t,x,y,h in yazi:
        ax.text(x, y, str(t), fontsize=max(4, min(11, h*1.1)), color="#060", family="monospace")
    ax.set_aspect("equal"); ax.autoscale(); ax.grid(True, lw=.2, alpha=.3)
    ax.set_title(baslik, fontsize=11)
    fig.tight_layout(); fig.savefig(cikti, dpi=95); plt.close(fig)
    print(cikti)
ciz(sys.argv[1], sys.argv[2], sys.argv[3])
