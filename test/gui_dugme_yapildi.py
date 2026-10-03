# -*- coding: utf-8 -*-
"""YAPILAN İŞİN DÜĞMESİ PASİF (gerçek tkinter, xvfb altında).

Kullanıcı: "yapılan işin butonu dezaktif olsun, tekrar tekrar basmayayım".
İş aynı girdilerle bitince alt iş düğmesi pasif ve metninde "✓ yapıldı";
girdi (malzeme, ayar, seçim) değişince düğme kendiliğinden açılır.

    xvfb-run -a python test/gui_dugme_yapildi.py
"""
import os, sys, time
import tkinter as tk
from tkinter import ttk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lisans_yardim                                              # noqa: E402
lisans_yardim.gecici_lisans()
import pf3_gui as G                                              # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


kok = tk.Tk()
try:
    ttk.Style().theme_use("clam")
except Exception:
    pass
u = G.Uygulama(kok)
t0 = time.time()
while u.M is None and time.time() - t0 < 120:
    kok.update(); time.sleep(0.05)
u.komp = [{"kod": "P1", "ad": "LEVHA", "adet": 1, "sinif": "parca", "tip": "", "indeks": [0],
           "hacim_mm3": 100.0, "olc": [10.0, 10.0, 1.0]}]
u.v_step.set(os.path.abspath(__file__))
u.v_out.set(os.path.dirname(os.path.abspath(__file__)))
u._dugmeleri_tazele(); kok.update()
dogru("BOM düğmesi önce aktif", str(u.b_bom.cget("state")) == "normal", u.b_bom.cget("state"))
# BOM işi bitti (aynı girdilerle)
u._basla("BOM çıkarılıyor…", "BOM çıkarma"); u._bitir("tamam"); kok.update()
dogru("BOM bitince düğme pasif", str(u.b_bom.cget("state")) == "disabled", u.b_bom.cget("state"))
dogru("metinde '✓ yapıldı'", "yapıldı" in u.b_bom.cget("text"), u.b_bom.cget("text"))
dogru("öbür düğmeler etkilenmedi (ÖRNEK aktif)", str(u.b_ornek.cget("state")) == "normal", u.b_ornek.cget("state"))
# girdi değişti: malzeme
u.malzemeler["p1"] = "aluminyum"
u._dugmeleri_tazele(); kok.update()
dogru("malzeme değişince BOM düğmesi açıldı", str(u.b_bom.cget("state")) == "normal", u.b_bom.cget("state"))
dogru("asıl metin geri geldi", "yapıldı" not in u.b_bom.cget("text"), u.b_bom.cget("text"))
# tüm çizimler: ayar değişince açılır
u._basla("çizimler üretiliyor…", "Tüm çizimler (1 parça)"); u._bitir("tamam"); kok.update()
dogru("ÇİZİMLERİ ÜRET bitince pasif", str(u.b_tumu.cget("state")) == "disabled", u.b_tumu.cget("state"))
u.v_perspektif.set(not u.v_perspektif.get())
u._dugmeleri_tazele(); kok.update()
dogru("ayar (perspektif) değişince açıldı", str(u.b_tumu.cget("state")) == "normal", u.b_tumu.cget("state"))
# hata ile biten iş düğmeyi kilitlemez
u._basla("BOM çıkarılıyor…", "BOM çıkarma"); u._bitir("hata"); kok.update()
dogru("hatayla biten iş düğmeyi kilitlemez", str(u.b_bom.cget("state")) == "normal", u.b_bom.cget("state"))
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
kok.destroy()
sys.exit(0 if not HATA else 1)
