# -*- coding: utf-8 -*-
"""BOM sayfası "Seçili parça" resmi KÜÇÜK EKRANDA görünüyor mu (gerçek
tkinter, xvfb). Kullanıcı: "burada parça görünüyor mu?" - 230x150 ayarlı
tuval kısa listede alttan kesiliyor, resim kesilen kısımda kalıyordu.
Denetim: 1280x650 pencerede tuval pencerenin içinde; çizilen bütün çizgi
noktaları tuvalin GÖRÜNEN alanının içinde; pencere büyüyünce yeniden
çizilip büyüyor.

    xvfb-run -a -s "-screen 0 1366x768x24" python3 test/gui_parca_resmi.py
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
import pf3_gui as G                                              # noqa: E402

HATA = []
kok = tk.Tk()
u = G.Uygulama(kok)
t0 = time.time()
while u.M is None and time.time() - t0 < 120:
    kok.update(); time.sleep(0.05)
u.defter.tab(1, state="normal"); u.defter.select(1)
# sahte kenarlar: 1000 x 300 mm'lik yatık parça (üçgenimsi)
ken = [[(0, 0), (1000, 0)], [(1000, 0), (1000, 300)], [(1000, 300), (0, 0)],
       [(0, 0), (0, 120)], [(0, 120), (400, 300)]]


def olc(boy):
    kok.geometry(boy + "+0+0")
    for _ in range(10):
        kok.update(); time.sleep(0.02)
    c = u.c_parca
    u._parca_resmi_ciz(ken)
    kok.update()
    W, H = c.winfo_width(), c.winfo_height()
    kx, ky = kok.winfo_rootx(), kok.winfo_rooty()
    x, y = c.winfo_rootx() - kx, c.winfo_rooty() - ky
    icerde = x >= 0 and y >= 0 and x + W <= kok.winfo_width() + 1 and y + H <= kok.winfo_height() + 1
    xs, ys = [], []
    for it in c.find_all():
        k = c.coords(it)
        xs += k[0::2]; ys += k[1::2]
    sigdi = bool(xs) and min(xs) >= 0 and min(ys) >= 0 and max(xs) <= W and max(ys) <= H
    print(f"{boy}: tuval {W}x{H} konum {x},{y} pencere {kok.winfo_width()}x{kok.winfo_height()} "
          f"içerde={icerde} çizim x {min(xs):.0f}..{max(xs):.0f} y {min(ys):.0f}..{max(ys):.0f} sığdı={sigdi}")
    if not icerde:
        HATA.append(f"{boy}: tuval pencerenin dışına taşıyor")
    if not sigdi:
        HATA.append(f"{boy}: çizim tuvalin görünen alanına sığmıyor")
    return W, H, max(xs) - min(xs)


w1, h1, g1 = olc("1280x650")
w2, h2, g2 = olc("1366x900")
# kayar sayfada kısa pencerede tuval ezilmez (sayfa kayar); resim en
# azından küçülmemeli ve tuvali doldurmalı
if h2 > h1 + 20 and g2 < g1 - 1:
    HATA.append(f"pencere büyüyünce resim küçüldü ({g1:.0f} -> {g2:.0f})")
if g2 < 0.85 * w2:
    HATA.append(f"geniş resim tuvali doldurmuyor ({g2:.0f} / {w2})")
kok.destroy()
if HATA:
    print("\nHATA:"); [print(" ", h) for h in HATA]
    sys.exit(1)
print("\nSONUC: parca resmi gorunuyor")
