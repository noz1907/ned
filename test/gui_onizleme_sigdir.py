# -*- coding: utf-8 -*-
"""ÖRNEK ÖNİZLEMESİ SIĞAR ve BÜYÜTÜLÜR (gerçek tkinter, xvfb).

Kullanıcı: "resim görülmüyor, nesini onaylayayım" - geniş resim tuvalden
taşıyor, üstü ve altı kesiliyordu (iki yönün küçük katsayısı
alınıyordu). "Sığmayan her durumda pencere yap, mümkün olan yerde
genişlet." Denetim: DXF'ten üretilen PNG tuvale İKİ yönde de sığar;
BÜYÜT penceresi açılır, açılışta sığar, + ile büyür, 1:1 gerçek boyut,
kaydırma bölgesi resim kadar; parça resmi çift tıkla büyük pencerede.

    xvfb-run -a -s "-screen 0 1366x768x24" python3 test/gui_onizleme_sigdir.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import tkinter as tk
    tk.Tk().destroy()
except Exception as ex:
    print(f"atlandi: tkinter/ekran yok ({type(ex).__name__}: {str(ex)[:60]})")
    sys.exit(0)
import lisans_yardim                                              # noqa: E402
lisans_yardim.gecici_lisans()
import ezdxf                                                      # noqa: E402
import pf3_gui as G                                              # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


# geniş, alçak bir çizim: 1900 x 400 parça + üstte / altta görünüşler
import tempfile                                                   # noqa: E402
kl = tempfile.mkdtemp(prefix="pi3d_oniz_")
d = ezdxf.new(); m = d.modelspace()
for y0 in (0, 700, 1400):
    m.add_lwpolyline([(0, y0), (1900, y0), (1900, y0 + 400), (0, y0 + 400)], close=True,
                     dxfattribs={"layer": "GORUNEN"})
m.add_text("ARKA", dxfattribs={"layer": "YAZI", "height": 20}).set_placement((0, 1820))
dxf = os.path.join(kl, "ornek.dxf"); d.saveas(dxf)
png = os.path.join(kl, "ornek.png")
G.dxf_onizleme(dxf, png)
from PIL import Image                                             # noqa: E402
im = Image.open(png)
print(f"PNG {im.width}x{im.height}")

kok = tk.Tk()
u = G.Uygulama(kok)
t0 = time.time()
while u.M is None and time.time() - t0 < 120:
    kok.update(); time.sleep(0.05)
kok.geometry("1280x650+0+0")
u.defter.tab(3, state="normal"); u.defter.select(3)
for _ in range(6):
    kok.update(); time.sleep(0.02)
u.onizleme_png = png
u._onizleme_ciz(); kok.update()
gw, gh = u.tuval.winfo_width(), u.tuval.winfo_height()
r = u.onizleme_resmi
print(f"tuval {gw}x{gh}, resim {r.width()}x{r.height()}")
dogru("resim tuvale iki yönde de sığıyor", r.width() <= gw and r.height() <= gh, (r.width(), r.height(), gw, gh))
dogru("resim tuvali dolduruyor (bir yön >= %95)", r.width() >= gw * 0.95 or r.height() >= gh * 0.95)
# BÜYÜT penceresi
w = u.onizleme_penceresi()
for _ in range(8):
    kok.update(); time.sleep(0.03)
p = u._onizleme_pencere
c, durum = p["c"], p["durum"]
cw, ch = c.winfo_width(), c.winfo_height()
rr = durum["resim"]
print(f"pencere tuvali {cw}x{ch}, resim {rr.width()}x{rr.height()} oran {durum['oran']:.2f}")
dogru("büyütme penceresi açıldı, resim sığdı", rr.width() <= cw and rr.height() <= ch and cw > gw)
o1 = durum["oran"]
p["yakin"](1.25); kok.update()
dogru("+ büyüttü", durum["oran"] > o1 and durum["resim"].width() > rr.width())
p["ciz"](1.0); kok.update()
dogru("1:1 gerçek boyut", durum["resim"].width() == im.width, (durum["resim"].width(), im.width))
sr = [float(v) for v in c.cget("scrollregion").split()]
dogru("kaydırma bölgesi resim kadar", sr[2] >= im.width - 1 and sr[3] >= im.height - 1, sr)
w.destroy(); kok.update()
# parça resmi büyük pencere
u.defter.tab(1, state="normal"); u.defter.select(1); kok.update()
ken = [[(0, 0), (1000, 0)], [(1000, 0), (1000, 300)], [(1000, 300), (0, 0)]]
u._parca_resmi_ciz(ken); kok.update()
pw = u.parca_resmi_penceresi(u.c_parca)
for _ in range(6):
    kok.update(); time.sleep(0.03)
pc = u._parca_resmi_pencere["c"]
xs = [x for it in pc.find_all() for x in pc.coords(it)[0::2]]
dogru("parça resmi büyük pencerede çizildi ve sığdı",
      xs and max(xs) - min(xs) > 500 and max(xs) <= pc.winfo_width(), (max(xs) - min(xs)) if xs else None)
pw.destroy()
kok.destroy()
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
