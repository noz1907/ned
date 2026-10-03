# -*- coding: utf-8 -*-
"""Açınım sayfası KAYAR PENCERE (gerçek tkinter, xvfb).

Kullanıcı: listenin altındaki özet satırı ve ÜRET düğmesi kısa pencerede
altta kalıyordu; "kayar pencere o, onu istiyorum, başka bir şey
değiştirme". Denetim: 1280x650'de içerik tuvalden uzunsa kaydırma
çubuğu çalışır ve sona kaydırınca ÜRET düğmesi tuvalin içinde görünür;
1280x1000'de içerik tuval kadar uzar (liste alanı boş kalmaz).

    xvfb-run -a -s "-screen 0 1366x768x24" python3 test/gui_kayar_sayfa.py
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
u.defter.tab(5, state="normal"); u.defter.select(5)
f = u.sayfa[5]
tuval = [w for w in f.winfo_children() if isinstance(w, tk.Canvas)]
if not tuval:
    HATA.append("açınım sayfasında kayar tuval yok")
else:
    tuval = tuval[0]
    icf = tuval.winfo_children()[0]
    for boy in ("1280x650", "1280x1000"):
        kok.geometry(boy + "+0+0")
        for _ in range(10):
            kok.update(); time.sleep(0.02)
        th, ih = tuval.winfo_height(), icf.winfo_reqheight()
        print(f"{boy}: tuval {th}, içerik {ih}, yview {tuval.yview()}")
        if boy == "1280x650":
            if ih <= th:
                print("  (içerik zaten sığıyor, kaydırma gerekmedi)")
                continue
            if tuval.yview()[1] >= 0.999:
                HATA.append(f"{boy}: içerik uzun ama kaydırma bölgesi yok")
            tuval.yview_moveto(1.0)
            for _ in range(3):
                kok.update()
            b = u.b_acilim
            ust = b.winfo_rooty() - tuval.winfo_rooty()
            alt = ust + b.winfo_height()
            print(f"  sona kaydırıldı: ÜRET düğmesi {ust}..{alt}, tuval 0..{th}")
            if not (0 <= ust and alt <= th + 1):
                HATA.append(f"{boy}: kaydırınca ÜRET düğmesi görünmüyor ({ust}..{alt} / {th})")
        else:
            if icf.winfo_height() < th - 2:
                HATA.append(f"{boy}: içerik tuval kadar uzamadı ({icf.winfo_height()} < {th})")
kok.destroy()
if HATA:
    print("\nHATA:"); [print(" ", h) for h in HATA]
    sys.exit(1)
print("\nSONUC: kayar sayfa calisiyor")
