# -*- coding: utf-8 -*-
"""EKSTRÜZYON PROFİL MALZEMESİ PENCERESİ (gerçek tkinter, xvfb).

Kullanıcı: "hani ben değiştirebiliyordum, resim gösteriyordun; listede
binlerce parça varsa nereden bulacağım, arama da yok; aynı standart
penceresi gibi pencere aç, sorunlu parçaları listele, seçebileyim."
Denetim: malzemesi belirsiz profiller pencerede listelenir; ARAMA kutusu
satırları süzer; seçilince resim çizilir; ALÜMİNYUM / ÇELİK / kutudaki
malzeme parça başına uygulanır, "kalanlara" kalan hepsine; kararsız
varken DEVAM durur; hepsi kararlıyken True döner ve malzemeler sözlüğüne
yazılır; Vazgeç None döner.

    xvfb-run -a python test/gui_malzeme_pencere.py
"""
import os, sys, time
import tkinter as tk
from tkinter import ttk, messagebox
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lisans_yardim                                              # noqa: E402
lisans_yardim.gecici_lisans()
import pf3_gui as G                                              # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox                  # noqa: E402
from OCP.gp import gp_Pnt                                         # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


uyarilar = []
messagebox.showwarning = lambda *a, **k: uyarilar.append(a[0])
kok = tk.Tk()
try:
    ttk.Style().theme_use("clam")
except Exception:
    pass
u = G.Uygulama(kok)
t0 = time.time()
while u.M is None and time.time() - t0 < 120:
    kok.update(); time.sleep(0.05)
M = u.M
kutu = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 1900, 40, 40).Shape()
u.kayit = [("RAY_1", kutu), ("RAY_2", kutu), ("KAPAK_PROFILI", kutu)]
u.komp = []
for i, (kod, ad) in enumerate((("RAY_1", "KARLUNA_1900X400 RAY"),
                               ("RAY_2", "Symmetry of KARLUNA_1900X400 RAY"),
                               ("KAPAK_PROFILI", "ARKA KAPAK TESTERE KESİ"))):
    u.komp.append({"kod": kod, "ad": ad, "adet": 2, "sinif": "parca", "tip": "ekstrüzyon profil",
                   "indeks": [i], "hacim_mm3": 1.0e6, "olc": [1900.0, 40.0, 40.0],
                   "profil": {"tur": "ekstrüzyon", "kesit": "40x40 3 hücre"}})
u.satirlar = []
u.malzemeler = {}
ek = M.malzemesi_sorulacak(u.komp, {})
dogru("3 profil sorulacak", len(ek) == 3, [k["kod"] for k in ek])


def senaryo():
    p = u._malzeme_pencere
    if not p:
        kok.after(200, senaryo); return
    ag = p["ag"]
    cocuk = ag.get_children()
    dogru("pencerede 3 satır", len(cocuk) == 3)
    # arama: KAPAK -> 1 satır
    ag.v_ara.set("kapak"); kok.update()
    dogru("arama süzdü (1 satır)", len(ag.get_children()) == 1 and ag.set(ag.get_children()[0], "kod") == "KAPAK_PROFILI",
          [ag.set(c, "kod") for c in ag.get_children()])
    dogru("süzülen satır seçildi", ag.selection() and ag.selection()[0] == ag.get_children()[0])
    ag.v_ara.set(""); kok.update()
    dogru("arama temizlenince 3 satır, sıra aynı", [ag.set(c, "kod") for c in ag.get_children()] == ["RAY_1", "RAY_2", "KAPAK_PROFILI"])
    # resim
    ag.selection_set(cocuk[0]); ag.event_generate("<<TreeviewSelect>>"); kok.update()
    t1 = time.time()
    while time.time() - t1 < 20:
        kok.update(); time.sleep(0.05)
        if id(u.komp[0]) in u._resim_onbellek:
            break
    dogru("parça resmi çizildi (önbellekte)", id(u.komp[0]) in u._resim_onbellek)
    # 1. parça ÇELİK
    p["bu_parcaya"]("celik"); kok.update()
    dogru("RAY_1 çelik", u.malzemeler.get("ray_1") == "celik", u.malzemeler)
    dogru("sonraki satıra geçti", ag.selection()[0] == cocuk[1])
    # kararsız varken DEVAM durur
    uyarilar.clear()
    for b in p["w"].winfo_children()[-1].winfo_children():
        if b.cget("text") == "DEVAM":
            b.invoke()
    kok.update()
    dogru("kararsız varken DEVAM uyardı, pencere açık", uyarilar and p["w"].winfo_exists())
    # kalanlara kutudaki (alüminyum)
    p["kalanlara"](); kok.update()
    dogru("kalanlar alüminyum", u.malzemeler.get("ray_2") == "aluminyum" and u.malzemeler.get("kapak_profili") == "aluminyum", u.malzemeler)
    dogru("malzeme sütunu dolu", all(ag.set(c, "karar") for c in cocuk), [ag.set(c, "karar") for c in cocuk])
    for b in p["w"].winfo_children()[-1].winfo_children():
        if b.cget("text") == "DEVAM":
            b.invoke(); break


kok.after(300, senaryo)
cvp = u._malzeme_karar_penceresi(ek)
dogru("pencere True döndü (devam)", cvp is True, cvp)
dogru("artık sorulacak profil yok", M.malzemesi_sorulacak(u.komp, dict(u.malzemeler)) == [])
dogru("_profil_malzeme_sor True (sormadan)", u._profil_malzeme_sor() is True)
# vazgeç
u.malzemeler = {}


def vazgec():
    p = u._malzeme_pencere
    if not p:
        kok.after(100, vazgec); return
    for b in p["w"].winfo_children()[-1].winfo_children():
        if str(b.cget("text")).startswith("Vazgeç"):
            b.invoke(); break


kok.after(300, vazgec)
cvp = u._profil_malzeme_sor()
dogru("Vazgeç -> False (iş durur)", cvp is False, cvp)
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
kok.destroy()
sys.exit(0 if not HATA else 1)
