# -*- coding: utf-8 -*-
"""YENİ İŞ ve ÇIKIŞ (gerçek tkinter, xvfb).

Kullanıcı: "işlem bittikten sonra sistemi yenileyebilmeliyim, kapatıp
açma gerekmemeli; bir de quit butonu". Denetim:
  - durum çubuğunda YENİ İŞ ve ÇIKIŞ düğmeleri var, görünür;
  - Dosya menüsünde Yeni iş / Çıkış;
  - iş durumu doldurulup YENİ İŞ yapılınca model, listeler, süreler,
    "yapıldı" imzaları sıfırlanır; motor (M) ve lisans kalır; sekmeler
    yeniden kurulur, 1. sekme açık, öbürleri kapalı; pencere boyutu
    değişmez;
  - iş çalışırken YENİ İŞ yapılmaz (önce İPTAL);
  - ÇIKIŞ pencereyi kapatır.

    xvfb-run -a -s "-screen 0 1366x768x24" python3 test/gui_yeni_is.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    tk.Tk().destroy()
except Exception as ex:
    print(f"atlandi: tkinter/ekran yok ({type(ex).__name__}: {str(ex)[:60]})")
    sys.exit(0)
import lisans_yardim                                              # noqa: E402
lisans_yardim.gecici_lisans()
import pf3_gui as G                                              # noqa: E402

HATA = []
mesajlar = []
messagebox.showinfo = lambda *a, **k: mesajlar.append(("info", a[0]))
messagebox.askyesno = lambda *a, **k: mesajlar.append(("soru", a[0])) or True

kok = tk.Tk()
u = G.Uygulama(kok)
t0 = time.time()
while u.M is None and time.time() - t0 < 120:
    kok.update(); time.sleep(0.05)
kok.geometry("1300x760+0+0")
for _ in range(5):
    kok.update(); time.sleep(0.02)

# düğmeler ve menü
for ad in ("b_yeni", "b_cikis"):
    b = getattr(u, ad, None)
    if b is None or not b.winfo_ismapped():
        HATA.append(f"{ad} yok ya da görünmüyor")
try:
    cubuk = kok.nametowidget(kok.cget("menu"))
    etiketler = [cubuk.entrycget(i, "label") for i in range(cubuk.index("end") + 1)]
    if "Dosya" not in etiketler:
        HATA.append(f"Dosya menüsü yok: {etiketler}")
    dosya = kok.nametowidget(cubuk.entrycget(etiketler.index("Dosya"), "menu"))
    alt = [dosya.entrycget(i, "label") for i in range(dosya.index("end") + 1)
           if dosya.type(i) == "command"]
    if not any("Yeni iş" in a for a in alt) or "Çıkış" not in alt:
        HATA.append(f"Dosya menüsü eksik: {alt}")
except Exception as ex:
    HATA.append(f"menü okunamadı: {ex}")

# iş durumu doldur
M, lisans = u.M, u.lisans
u.v_step.set("/yok/model.stp"); u.v_out.set("/yok/cikti")
u.satirlar = [{"kod": "A"}]; u.malzemeler = {"A": "S235"}; u.parca_ayar = {"A": {}}
u.kayit = object(); u.komp = [1, 2]; u._yapildi = {"bom": "imza"}
u.oturum_sure = 42.0; u._toplam_yaz()
for i in range(8):
    u.defter.tab(i, state="normal")
u.defter.select(5)
u.ac_agac.insert("", "end", values=("1", "A", "ad", "2", "", "", ""))
eski_agac = u.ac_agac
geom = kok.geometry()

# çalışırken YENİ İŞ yapılmaz
u.calisiyor = True
if u.yeni_is() is not False or not mesajlar or mesajlar[-1][0] != "info":
    HATA.append("iş çalışırken YENİ İŞ engellenmedi")
u.calisiyor = False

# YENİ İŞ
mesajlar.clear()
if u.yeni_is() is not True:
    HATA.append("YENİ İŞ yapılmadı")
if not mesajlar or mesajlar[-1][0] != "soru":
    HATA.append("YENİ İŞ sormadı")
for _ in range(8):
    kok.update(); time.sleep(0.02)
if u.M is not M or u.lisans is not lisans:
    HATA.append("motor / lisans korunmadı")
if u.v_step.get() or u.v_out.get() or u.satirlar or u.malzemeler or u.parca_ayar \
        or u.kayit is not None or u.komp is not None or u._yapildi:
    HATA.append("iş durumu sıfırlanmadı")
if u.oturum_sure != 0.0:
    HATA.append(f"oturum süresi sıfırlanmadı: {u.oturum_sure}")
if u.ac_agac is eski_agac or u.ac_agac.get_children():
    HATA.append("açınım listesi yeniden kurulmadı / boş değil")
if u.defter.index(u.defter.select()) != 0:
    HATA.append("1. sekme açık değil")
if any(u.defter.tab(i, "state") == "normal" for i in range(1, 8)):
    HATA.append("sonraki sekmeler kapalı gelmedi")
if kok.geometry().split("+")[0] != geom.split("+")[0]:
    HATA.append(f"pencere boyutu değişti: {geom} -> {kok.geometry()}")
if "hazır" not in u.v_durum.get() and "yeni iş" not in u.v_durum.get():
    HATA.append(f"durum: {u.v_durum.get()}")
for ad in ("b_yeni", "b_cikis", "b_iptal", "b_incele"):
    b = getattr(u, ad, None)
    if b is None or not b.winfo_ismapped():
        HATA.append(f"yeni kurulumda {ad} görünmüyor")
# ikinci kez de çalışmalı
if u.yeni_is(sor=False) is not True:
    HATA.append("ikinci YENİ İŞ yapılmadı")
kok.update()

# ÇIKIŞ: çalışırken sorar (hayır -> kalır), boşta kapatır
messagebox.askyesno = lambda *a, **k: False
u.calisiyor = True
if u.cikis() is not False or not kok.winfo_exists():
    HATA.append("çalışırken ÇIKIŞ 'hayır' denince pencere kapandı")
u.calisiyor = False
u.cikis()
try:
    kok.update(); var = kok.winfo_exists()
except tk.TclError:
    var = False
if var:
    HATA.append("ÇIKIŞ pencereyi kapatmadı")

if HATA:
    print("\nHATA:"); [print(" ", h) for h in HATA]
    sys.exit(1)
print("SONUC: YENI IS ve CIKIS calisiyor")
