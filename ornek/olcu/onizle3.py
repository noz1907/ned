"""DXF -> PNG onizleme. Yazilar gercek boyutta (veri biriminde) cizilir,
boylece cakisma goruntude de gercekte oldugu gibi gorunur."""
import ezdxf, math, sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

def topla(e, segs, yazi, ovr=None):
    k = ovr or (e.dxf.layer if e.dxf.layer in segs else "DIGER")
    t = e.dxftype()
    try:
        if t == "LWPOLYLINE":
            p = [(a, b) for a, b in e.get_points('xy')]
            for a, b in zip(p, p[1:]): segs[k].append([a, b])
        elif t == "LINE":
            segs[k].append([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)])
        elif t in ("CIRCLE", "ARC"):
            c = e.dxf.center; r = e.dxf.radius
            a0, a1 = (0, 360) if t == "CIRCLE" else (e.dxf.start_angle, e.dxf.end_angle)
            if a1 < a0: a1 += 360
            p = [(c.x + r*math.cos(math.radians(a)), c.y + r*math.sin(math.radians(a)))
                 for a in [a0 + (a1-a0)*i/32 for i in range(33)]]
            for a, b in zip(p, p[1:]): segs[k].append([a, b])
        elif t == "SOLID":
            v = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx2]
            segs[k].append([(v[0].x, v[0].y), (v[1].x, v[1].y)])
            segs[k].append([(v[1].x, v[1].y), (v[2].x, v[2].y)])
        elif t == "TEXT":
            yazi.append((e.dxf.text, e.dxf.insert.x, e.dxf.insert.y, e.dxf.height))
        elif t == "MTEXT":
            yazi.append((e.text, e.dxf.insert.x, e.dxf.insert.y, e.dxf.char_height))
    except Exception:
        pass

def ciz(dosya, cikti, kirp=None, gen=22.0, boy=15.0):
    d = ezdxf.readfile(dosya); m = d.modelspace()
    segs = {"GORUNEN": [], "GIZLI": [], "OLCU": [], "EKSEN": [], "YAZI": [], "DIGER": []}
    yazi = []
    for e in m:
        if e.dxftype() == "DIMENSION":
            try:
                for e2 in d.blocks.get(e.dxf.geometry): topla(e2, segs, yazi, "OLCU")
            except Exception: pass
        else:
            topla(e, segs, yazi)
    xs = [p[0] for v in segs.values() for s in v for p in s] + [t[1] for t in yazi]
    ys = [p[1] for v in segs.values() for s in v for p in s] + [t[2] for t in yazi]
    for t, x, y, h in yazi:
        xs.append(x + len(str(t)) * 0.72 * h); ys.append(y + h)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if kirp: x0, y0, x1, y1 = kirp
    pay = 0.02 * max(x1 - x0, y1 - y0)
    x0 -= pay; x1 += pay; y0 -= pay; y1 += pay
    # en-boy oranini sayfaya uydur
    sf, sc = (x1 - x0) / (y1 - y0), gen / boy
    if sf > sc:
        ek = ((x1 - x0) / sc - (y1 - y0)) / 2; y0 -= ek; y1 += ek
    else:
        ek = ((y1 - y0) * sc - (x1 - x0)) / 2; x0 -= ek; x1 += ek
    fig, ax = plt.subplots(figsize=(gen, boy))
    renk = {"GORUNEN": ("#111", 1.1), "GIZLI": ("#b00", 0.55), "OLCU": ("#06c", 0.6),
            "EKSEN": ("#a0a", 0.45), "YAZI": ("#060", 0.5), "DIGER": ("#888", 0.4)}
    for k, v in segs.items():
        if v: ax.add_collection(LineCollection(v, colors=renk[k][0], linewidths=renk[k][1]))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal")
    ax.set_position([0, 0, 1, 1]); ax.axis("off")
    # veri birimi basina punto: 1 inc = 72 punto
    pb = gen * 72.0 / (x1 - x0)
    for t, x, y, h in yazi:
        ax.text(x, y, str(t).replace("%%c", "Ø"), fontsize=h * pb * 0.95,
                color="#036", family="monospace", va="bottom", ha="left")
    fig.savefig(cikti, dpi=90, facecolor="white"); plt.close(fig)
    print(cikti, f"{x1-x0:.0f} x {y1-y0:.0f} mm")

ciz(sys.argv[1], sys.argv[2],
    [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else None)
