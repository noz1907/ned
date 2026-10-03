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
# lazer
ly = os.path.join(kl, "l.dxf")
M.dxf_lazer(r["kontur_dis"], r["kontur_delik"], ly)
ld = ezdxf.readfile(ly).modelspace()
tipler = {e.dxftype() for e in ld}
dogru("lazerde ölçü / yazı yok, yalnız kontur", tipler == {"LWPOLYLINE"} and {e.dxf.layer for e in ld} == {"KESIM"},
      tipler)
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
