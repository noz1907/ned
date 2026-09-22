# -*- coding: utf-8 -*-
"""Cakisma olcumu, cizim kodundan BAGIMSIZ ama YEREL olcuyle:
gizli parcanin dogrusuna gorunen parcanin IKI UCU da 0.12 mm'den
yakinsa ve paralelse, cakisan bolumu sayar."""
import os, sys, math, ezdxf
from collections import defaultdict

def oku(yol):
    d = ezdxf.readfile(yol); g = {"GORUNEN": [], "GIZLI": []}
    for e in d.modelspace().query("LWPOLYLINE"):
        if e.dxf.layer not in g: continue
        p = [(x, y) for x, y, *_ in e.get_points()]
        if e.closed and len(p) > 1: p.append(p[0])
        for a, b in zip(p, p[1:]):
            if math.dist(a, b) > 1e-9: g[e.dxf.layer].append((a, b))
    return g

def olc(yol, AC=0.02, UZ=0.12, HUC=5.0):
    g = oku(yol)
    iz = defaultdict(list)
    for i, (c, d) in enumerate(g["GORUNEN"]):
        n = int(math.dist(c, d) / HUC) + 1
        for j in range(n + 1):
            cx = int((c[0] + (d[0]-c[0]) * j / n) // HUC)
            cy = int((c[1] + (d[1]-c[1]) * j / n) // HUC)
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1): iz[(cx+ox, cy+oy)].append(i)
    top, adet = 0.0, 0
    for a, b in g["GIZLI"]:
        L = math.dist(a, b); ux, uy = (b[0]-a[0])/L, (b[1]-a[1])/L
        n = int(L / HUC) + 1
        aday = set()
        for j in range(n + 1):
            aday.update(iz.get((int((a[0]+ux*L*j/n)//HUC),
                                int((a[1]+uy*L*j/n)//HUC)), ()))
        ort = 0.0
        for i in aday:
            c, d = g["GORUNEN"][i]
            vx, vy = d[0]-c[0], d[1]-c[1]; m = math.hypot(vx, vy)
            if abs(ux*vy - uy*vx) > AC*m: continue
            if abs(ux*(c[1]-a[1]) - uy*(c[0]-a[0])) > UZ: continue
            if abs(ux*(d[1]-a[1]) - uy*(d[0]-a[0])) > UZ: continue
            g0 = (c[0]-a[0])*ux + (c[1]-a[1])*uy
            g1 = (d[0]-a[0])*ux + (d[1]-a[1])*uy
            ort = max(ort, min(L, max(g0, g1)) - max(0.0, min(g0, g1)))
        if ort > 0.05: top += ort; adet += 1
    return adet, top, len(g["GIZLI"]), len(g["GORUNEN"])

for yol in sys.argv[1:]:
    a, t, ng, nv = olc(yol)
    print(f"{yol.split('/')[-1]:34s} cakisan gizli parca {a:4d}, toplam "
          f"{t:8.2f} mm   (gizli {ng}, gorunen {nv})")
