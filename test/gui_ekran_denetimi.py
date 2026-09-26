# -*- coding: utf-8 -*-
"""15 inç ekranda (1366x768; 1920x1080 %125 ölçekte 1536x864) her
sekmedeki her düğme, giriş kutusu ve alt çubuk (ilerleme, İPTAL,
günlük, durum) pencerenin İÇİNDE görünüyor mu - gerçek pencereyle.

Eskiden pencere 1755x993 piksel istiyordu: 15 inçte alttaki İPTAL,
günlük ve durum çubuğu ile 6-7. adımın ÜRET / PAFTAYA AL / BAS
düğmeleri ekran dışında kalıyordu.

Görev çubuğu ve pencere başlığı düşülmüş boyutlar denenir. Liste
(tablo) en az 3 satır (60 piksel) göstermeli.

tkinter + ekran gerekir; yoksa "atlandi" deyip 0 ile çıkar. Ekranın
küçük olduğunu programın görmesi için sanal ekran 1366x768 açılmalı:

    xvfb-run -a -s "-screen 0 1366x768x24" python3 test/gui_ekran_denetimi.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import tkinter as tk
    from tkinter import ttk
    tk.Tk().destroy()
except Exception as ex:
    print(f"atlandi: tkinter/ekran yok ({type(ex).__name__}: {str(ex)[:60]})")
    sys.exit(0)

import pf3_gui as G                                              # noqa: E402

HATA = []
SINIF = ("TButton", "Button", "TEntry", "TCheckbutton", "TRadiobutton",
         "TCombobox")


def tum(w):
    for c in w.winfo_children():
        yield c
        yield from tum(c)


kok = tk.Tk()
try:
    ttk.Style().theme_use("clam")
except Exception:
    pass
u = G.Uygulama(kok)
t0 = time.time()
while u.M is None and time.time() - t0 < 120:
    kok.update(); time.sleep(0.05)
print(f"ekran {kok.winfo_screenwidth()}x{kok.winfo_screenheight()}, "
      f"küçük ekran düzeni: {u.kucuk}")
if kok.winfo_screenheight() < 950 and not u.kucuk:
    HATA.append("küçük ekran tanınmadı")

for boy in ("1366x700", "1280x650"):
    W, H = map(int, boy.split("x"))
    kok.state("normal")
    kok.geometry(f"{W}x{H}+0+0")
    for _ in range(10):
        kok.update(); time.sleep(0.02)
    kx, ky = kok.winfo_rootx(), kok.winfo_rooty()
    kw, kh = kok.winfo_width(), kok.winfo_height()

    def gorunur(w):
        x, y = w.winfo_rootx() - kx, w.winfo_rooty() - ky
        return (w.winfo_ismapped() and w.winfo_height() > 4
                and w.winfo_width() > 4 and x >= 0 and y >= 0
                and x + w.winfo_width() <= kw + 1
                and y + w.winfo_height() <= kh + 1)

    print(f"-- pencere {W}x{H}")
    for i in range(len(G.ADIM)):
        u.defter.tab(i, state="normal"); u.defter.select(i)
        for _ in range(5):
            kok.update()
        gizli = [w for w in tum(u.sayfa[i]) if w.winfo_class() in SINIF
                 and not gorunur(w)]
        agac = [w.winfo_height() for w in tum(u.sayfa[i])
                if w.winfo_class() == "Treeview"]
        kisa = [h for h in agac if h < 60]
        iyi = not gizli and not kisa
        print(f"  {'tamam' if iyi else 'HATA '} {G.ADIM[i]:22s} "
              f"liste {agac}" + "".join(
                  f"\n         gizli: {str(w.cget('text'))[:40]!r}" for w in gizli)
              + (f"\n         liste çok kısa: {kisa}" if kisa else ""))
        if not iyi:
            HATA.append(f"{boy} {G.ADIM[i]}")
    for ad, w in (("ilerleme", u.ilerleme), ("İPTAL", u.b_iptal),
                  ("günlük", u.gunluk), ("durum çubuğu", u.durum_etiket)):
        ok = gorunur(w)
        print(f"  {'tamam' if ok else 'HATA '} {ad}")
        if not ok:
            HATA.append(f"{boy} {ad}")

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                     else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
os._exit(1 if HATA else 0)
