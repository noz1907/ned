# -*- coding: utf-8 -*-
"""AÇINIM ve LAZER ölçü kuralı (kullanıcı: "lazer kesimde ölçülendirme yok;
açınımda yalnız dış ölçüler ve delik konumları, bunun dışında ölçü yok;
üç resim: ölçülü, ölçüsüz ve izometrik bükümlü - DXF'te ve PDF'te").

Sentetik bükümlü açınım sonucu (r) ile dxf_acilim ve dxf_lazer çağrılır.
Denetim: açınımda doğrusal ölçü yalnız 2 tane (boy, en - gabari), öbür
ölçüler koordinatlı (ordinate: delik konumu) ve değerleri gerçek delik
merkezleri ya da 0; büküm konum ölçüsü yok; "ÖLÇÜSÜZ AÇINIM" ikinci resmi
var (kontur iki kez); izometrik resim var; lazerde ölçü ve yazı yok,
yalnız KESIM katmanında kapalı konturlar.

    python test/acinim_olcu_denetimi.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                      # noqa: E402
import pf3_olcu as M                                              # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def daire(cx, cy, r=3.0, n=16):
    import math
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


boy, gen = 600.0, 200.0
delikler = [(30.0, 20.0), (30.0, 180.0), (300.0, 20.0), (570.0, 180.0)]
r = {"acinim_genislik_mm": gen, "acinim_boy_mm": boy, "kalinlik_mm": 1.5,
     "kontur_dis": [[(0, 0), (boy, 0), (boy, gen), (0, gen)]],
     "kontur_delik": [daire(x, y) for x, y in delikler],
     "bukumler": [{"acinimda_bas_mm": 98.0, "acinimda_son_mm": 102.0, "aci_derece": 90.0,
                   "r_ic": 2.0, "pay_mm": 4.0}],
     "bukum_sayisi": 1, "k_faktor": 0.4,
     "izo": [[(0, 0), (100, 50)], [(100, 50), (100, 150)]]}
kl = tempfile.mkdtemp(prefix="pi3d_ac_")
yol = os.path.join(kl, "a.dxf")
try:
    M.dxf_acilim(r, {"kod": "T", "ad": "T", "adet": 1, "poz": 1}, yol)
except Exception as ex:
    HATA.append(f"dxf_acilim: {ex}")
    print(ex)
d = ezdxf.readfile(yol)
msp = d.modelspace()
lin = [e for e in msp.query("DIMENSION") if (e.dxf.dimtype & 7) in (0, 1)]
ordn = [e for e in msp.query("DIMENSION") if (e.dxf.dimtype & 7) == 6]
dogru("doğrusal ölçü yalnız gabari (2)", sorted(round(e.get_measurement(), 1) for e in lin) == [gen, boy],
      [round(e.get_measurement(), 1) for e in lin])
gercek = {0.0} | {x for x, _y in delikler} | {y for _x, y in delikler}
deg = []
for e in ordn:
    m = e.get_measurement()
    # X tipi koordinatlı ölçüde dimtype'ın 64 biti açıktır: X değeri; yoksa Y
    deg.append(round(abs(m[0] if (e.dxf.dimtype & 64) else m[1]), 1))
dogru("koordinatlı ölçüler delik konumu (ya da 0)", ordn and all(any(abs(v - g) < 0.06 for g in gercek) for v in deg),
      deg)
dogru("büküm konumu (100) ölçülmedi", not any(abs(v - 100.0) < 0.06 for v in deg))
dogru("başka ölçü türü yok", all((e.dxf.dimtype & 7) in (0, 1, 6) for e in msp.query("DIMENSION")))
yazi = [e.dxf.text for e in msp.query("TEXT")]
dogru("ÖLÇÜSÜZ AÇINIM resmi var", any("ÖLÇÜSÜZ AÇINIM" in t for t in yazi), yazi[:5])
dis = [e for e in msp.query("LWPOLYLINE") if len(e) == 4]
dogru("dış kontur iki kez (ölçülü + ölçüsüz)", len(dis) >= 2, len(dis))
dogru("izometrik resim var", any("PERSPEKTİF" in t for t in yazi))
# tablolar seçenekli (varsayılan açık)
dogru("varsayılan: büküm çizelgesi var", any(t.startswith("BÜKÜM  AÇI") for t in yazi))
y2 = os.path.join(kl, "a2.dxf")
M.dxf_acilim(r, {"kod": "T", "ad": "T", "adet": 1, "poz": 1}, y2, {"acinim_tablo": False})
yazi2 = [e.dxf.text for e in ezdxf.readfile(y2).modelspace().query("TEXT")]
dogru("tablo kapalı: büküm / abkant tablosu yok",
      not any(t.startswith(("BÜKÜM  AÇI", "ABKANT", "KANAT  DIŞ")) for t in yazi2), yazi2[:8])
dogru("tablo kapalı: ölçüsüz ve izometrik resim yine var",
      any("ÖLÇÜSÜZ AÇINIM" in t for t in yazi2) and any("PERSPEKTİF" in t for t in yazi2))
# IZGARA: sık delik deseni tek tek ölçülmez; kesik çerçeve + iki köşe;
# hiçbir ölçü çizgisi desenin içinden geçmez; seyrek delikler yine ölçülür
boy3, gen3 = 800.0, 300.0
# desen alt kenara yakın: 325'teki deliğin kılavuzu en yakın (alt) kenara
# desenin içinden giderdi, üste çıkmalı; 400; 50 deliğinin sola giden Y
# kılavuzu desenden geçerdi, Y değeri başlığa düşmeli
izg = [(300.0 + 10.0 * i, 40.0 + 10.0 * j) for i in range(6) for j in range(3)]
seyrek3 = [(30.0, 20.0), (30.0, 280.0), (325.0, 110.0), (400.0, 50.0)]
r3 = dict(r, acinim_genislik_mm=gen3, acinim_boy_mm=boy3,
          kontur_dis=[[(0, 0), (boy3, 0), (boy3, gen3), (0, gen3)]],
          kontur_delik=[daire(x, y) for x, y in izg + seyrek3])
y3 = os.path.join(kl, "a3.dxf")
M.dxf_acilim(r3, {"kod": "T3", "ad": "T3", "adet": 1, "poz": 1}, y3)
m3 = ezdxf.readfile(y3).modelspace()
bolge = [e for e in m3.query("LWPOLYLINE") if e.dxf.layer == "BOLGE"]
dogru("ızgara kesik çerçeveyle işaretli", len(bolge) == 1, len(bolge))
kx0, ky0, kx1, ky1 = 297.0, 37.0, 353.0, 63.0
deg3 = set()
icinden = []


def kesisir(a, b, k):
    """a-b doğru parçası k kutusunun İÇİNE (0,5 mm içeriden) giriyor mu."""
    x0, y0, x1, y1 = k[0] + 0.5, k[1] + 0.5, k[2] - 0.5, k[3] - 0.5
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for pp, qq in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if abs(pp) < 1e-12:
            if qq < 0:
                return False
            continue
        t = qq / pp
        if pp < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    return t0 < t1


for e in m3.query("DIMENSION"):
    if (e.dxf.dimtype & 7) != 6:
        continue
    mm = e.get_measurement()
    deg3.add(round(abs(mm[0] if (e.dxf.dimtype & 64) else mm[1]), 1))
    for v in e.virtual_entities():
        if v.dxftype() == "LINE" and kesisir(v.dxf.start, v.dxf.end, (kx0, ky0, kx1, ky1)):
            icinden.append(round(abs(mm[0] if (e.dxf.dimtype & 64) else mm[1]), 1))
dogru("ızgara deliklerinin iç konumları yok", not any(abs(v - x) < 0.06 for v in deg3 for x in (310.0, 340.0, 350.0)),
      sorted(deg3))
dogru("ızgara başı ve sonu ölçülü (297 / 353 ya da 37 / 63)",
      any(abs(v - 297.0) < 0.06 or abs(v - 37.0) < 0.06 for v in deg3)
      and any(abs(v - 353.0) < 0.06 or abs(v - 63.0) < 0.06 for v in deg3), sorted(deg3))
dogru("seyrek delikler ölçülü (30, 325, 110)", {30.0, 325.0, 110.0} <= deg3, sorted(deg3))
dogru("hiçbir ölçü çizgisi ızgaranın içinden geçmiyor", not icinden, icinden)
not3 = " ".join(e.dxf.text for e in m3.query("TEXT") if "DELİK KONUMU" in e.dxf.text)
dogru("desenden geçecek kılavuz başlığa düştü (400; 50)", "400; 50" in not3, not3[:120])
# cıvata deliği dizisi (Ø6, 40 aralık, iki sıra) IZGARA DEĞİLDİR: tek tek ölçülür
civ = [(100.0 + 40.0 * i, 60.0 + 40.0 * j) for i in range(8) for j in range(2)]
r4 = dict(r3, kontur_delik=[daire(x, y) for x, y in civ])
y4 = os.path.join(kl, "a4.dxf")
M.dxf_acilim(r4, {"kod": "T4", "ad": "T4", "adet": 1, "poz": 1}, y4)
m4 = ezdxf.readfile(y4).modelspace()
dogru("cıvata dizisi ızgara sayılmadı", not [e for e in m4.query("LWPOLYLINE") if e.dxf.layer == "BOLGE"])
deg4 = set()
for e in m4.query("DIMENSION"):
    if (e.dxf.dimtype & 7) == 6:
        mm = e.get_measurement()
        deg4.add(round(abs(mm[0] if (e.dxf.dimtype & 64) else mm[1]), 1))
dogru("cıvata dizisinin her konumu ölçülü", {100.0 + 40.0 * i for i in range(8)} | {60.0, 100.0} <= deg4, sorted(deg4))
# lazer
ly = os.path.join(kl, "l.dxf")
M.dxf_lazer(r["kontur_dis"], r["kontur_delik"], ly)
ld = ezdxf.readfile(ly).modelspace()
tipler = {e.dxftype() for e in ld}
dogru("lazerde ölçü / yazı yok, yalnız kontur", tipler == {"LWPOLYLINE"} and {e.dxf.layer for e in ld} == {"KESIM"},
      tipler)
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
