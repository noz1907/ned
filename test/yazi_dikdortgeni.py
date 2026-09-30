# -*- coding: utf-8 -*-
"""Döndürülmüş yazının GERÇEK dikdörtgeni ve çakışma denetimleri.

Eksene hizalı sınır kutusu döndürülmüş yazıda (30°) yazının kendisinden
çok büyüktür: kaynak resminde birbirine hiç değmeyen merdiven dizilişli
beş "189" ölçüsünü çakışıyor sanıyordu. Yazı önce döndürülmeden ölçülür
(en, boy), sonra dikdörtgen merkezinin çevresinde döndürülür; iki
dikdörtgen ayırma ekseni sınamasıyla (SAT) karşılaştırılır."""
import copy
import math

import ezdxf.bbox


def dikdortgen(e):
    """TEXT varlığının köşeleri [(x, y)] x 4; ölçülemezse None."""
    try:
        k = ezdxf.bbox.extents([e], fast=False)
        if not k.has_data:
            return None
        cx, cy = (k.extmin.x + k.extmax.x) / 2, (k.extmin.y + k.extmax.y) / 2
        e2 = copy.deepcopy(e)
        e2.dxf.rotation = 0.0
        k2 = ezdxf.bbox.extents([e2], fast=False)
        w, h = k2.extmax.x - k2.extmin.x, k2.extmax.y - k2.extmin.y
    except Exception:
        return None
    a = math.radians(e.dxf.get("rotation", 0.0))
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -uy, ux
    return [(cx + sx * w / 2 * ux + sy * h / 2 * vx, cy + sx * w / 2 * uy + sy * h / 2 * vy)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _eksenler(p):
    for i in range(4):
        a, b = p[i], p[(i + 1) % 4]
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        yield (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)


def kesisir(p, q, pay=0.2):
    """İki dikdörtgen pay'dan fazla iç içe mi (SAT)."""
    for ax, ay in list(_eksenler(p)) + list(_eksenler(q)):
        pa = [x * ax + y * ay for x, y in p]
        qa = [x * ax + y * ay for x, y in q]
        if min(max(pa), max(qa)) - max(min(pa), min(qa)) <= pay:
            return False
    return True


def cizgiye_degiyor(p, a, b):
    """a-b doğru parçası dikdörtgen p'ye değiyor mu (dikdörtgenin
    eksenlerine göre döndürülüp Liang-Barsky)."""
    cx = sum(x for x, _ in p) / 4
    cy = sum(y for _, y in p) / 4
    ux, uy = p[1][0] - p[0][0], p[1][1] - p[0][1]
    w = math.hypot(ux, uy) or 1e-9
    ux, uy = ux / w, uy / w
    h = math.hypot(p[3][0] - p[0][0], p[3][1] - p[0][1])

    def yerel(q):
        dx, dy = q[0] - cx, q[1] - cy
        return (dx * ux + dy * uy, -dx * uy + dy * ux)
    a, b = yerel(a), yerel(b)
    k = (-w / 2, -h / 2, w / 2, h / 2)
    x0, y0 = a
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, x0 - k[0]), (dx, k[2] - x0), (-dy, y0 - k[1]), (dy, k[3] - y0)):
        if abs(pp) < 1e-12:
            if qq < 0:
                return False
        else:
            r = qq / pp
            if pp < 0:
                if r > t1:
                    return False
                t0 = max(t0, r)
            else:
                if r < t0:
                    return False
                t1 = min(t1, r)
    return t0 <= t1


def sayfa_denetimi(doc, katman=("OLCU",), cizgi=("GORUNEN", "KAYNAK")):
    """(üst üste binen yazı çiftleri, parça çizgisine binen yazılar)."""
    msp = doc.modelspace()
    yz = [(e.dxf.text, dikdortgen(e)) for e in msp.query("TEXT") if e.dxf.layer in katman]
    yz = [(t, p) for t, p in yz if p]
    cift = [(ta, tb) for i, (ta, pa) in enumerate(yz) for tb, pb in yz[i + 1:]
            if kesisir(pa, pb)]
    ks = [(a, b) for e in msp.query("LWPOLYLINE") if e.dxf.layer in cizgi
          for pts in [[(x, y) for x, y in e.get_points("xy")]] for a, b in zip(pts, pts[1:])]
    ust = [t for t, p in yz if any(cizgiye_degiyor(p, a, b) for a, b in ks)]
    return cift, ust
