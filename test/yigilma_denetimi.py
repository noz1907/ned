# -*- coding: utf-8 -*-
"""YIĞILMA ANALİZİ (CLAUDE.md 25): birbirine giren ölçü öbeği kayıp sayılır,
bölge seçimi onu detaya taşır.

Sentetik çizim: bir görünüş kutusu; sol üst köşede birbirine 0,5·h yakın
dört kısa ölçü (5, 7,5, 50, 21,5 gibi) + uzakta iki temiz ölçü. Beklenen:
köşedeki dört ölçünün özellikleri kayıp listesine girer, uzaktakiler
girmez; bolge_sec köşeyi içeren bir bölge döndürür.

    python test/yigilma_denetimi.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as M                                              # noqa: E402

HATA = []
h = 20.0
doc = M.dxf_kur()
msp = doc.modelspace()
M.olcu_stili(doc, h)
gk = (0.0, 0.0, 1800.0, 1000.0)
gkutu = {"ARKA": gk}
kaydir = {"ARKA": (0.0, 0.0)}
onceki = {e.dxf.handle for e in msp}
stil = {"dimstyle": "PI3D"} if "PI3D" in doc.dimstyles else {}


def lin(p1, p2, base, angle=0):
    d = msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, **stil)
    d.render()
    return d


# köşede yığılan kısa İÇ ölçüler (sol üst, y ~ 1000; ölçü çizgisi
# görünüşün içinde = özelliğin yanına konmuş yerel ölçü)
lin((20, 980), (25, 980), (20, 980 - 1.2 * h))              # 5 (kısa halka)
lin((25, 980), (75, 980), (25, 980 - 1.2 * h))              # 50
lin((20, 980), (20, 972.5), (20 + 1.2 * h, 980), angle=90)  # 7,5 (kısa, düşey)
lin((20, 972.5), (20, 951), (20 + 1.2 * h, 980), angle=90)  # 21,5
# uzakta temiz iç ölçüler (iki tane, uçları uzak: öbek olmaz)
lin((900, 500), (1400, 500), (900, 500 - 3 * h))            # 500
lin((1700, 300), (1700, 700), (1700 - 3 * h, 300), angle=90)  # 400
# dış zincir (ölçü çizgisi görünüşün dışında): katılmaz
lin((0, 1000), (164, 1000), (0, 1000 + 3 * h))
lin((164, 1000), (424, 1000), (0, 1000 + 3 * h))
lin((424, 1000), (1336, 1000), (0, 1000 + 3 * h))
kayip = []
n = M.yigilma_kayiplari(msp, onceki, gkutu, kaydir, h, kayip)
print(f"kayıp eklendi: {n}")
for k in kayip:
    print("  ", k["gad"], k["yon"], round(k["b"], 1), [round(v, 1) for v in k["dik_b"]])
pts = [M._kayip_noktalari(k)[0] for k in kayip]
kose = [p for p in pts if p[0] <= 80 and p[1] >= 940]
uzak = [p for p in pts if p[0] >= 800 or (300 <= p[1] <= 700 and p[0] >= 1600)]
zincir = [p for p in pts if abs(p[1] - 1000) < 0.01 and p[0] > 100]
if zincir:
    HATA.append(f"dış zincir halkaları kayıp sayıldı: {zincir}")
if not kayip or len(kose) < 4:
    HATA.append(f"köşedeki yığılma kayıp sayılmadı ({len(kose)} nokta)")
if uzak:
    HATA.append(f"uzaktaki temiz ölçüler kayıp sayıldı: {uzak}")
bolgeler = M.bolge_sec(kayip, gkutu, kaydir, h) if kayip else []
print("bölgeler:", [(b["gad"], [round(v) for v in b["k"]]) for b in bolgeler])
if not bolgeler or not any(b["k"][0] <= 25 <= b["k"][2] and b["k"][1] <= 972 <= b["k"][3] for b in bolgeler):
    HATA.append("köşeyi içeren bölge seçilmedi")
if bolgeler and any(b["k"][2] > 900 for b in bolgeler):
    HATA.append("bölge görünüşün yarısından geniş (köşe olmalı)")
if HATA:
    print("\nHATA:"); [print(" ", x) for x in HATA]
    sys.exit(1)
print("\nSONUC: yigilma analizi dogru")
