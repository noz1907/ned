# -*- coding: utf-8 -*-
"""STANDART PARÇA TANIMI PENCERESİ (gerçek tkinter, xvfb altında).

Belirsiz parçalar ayrı pencerede liste olarak açılır; seçilince parçanın
izometrik resmi çizilir; her parça için STANDART / ÜRETİM / olduğu gibi
kalsın kararı ve ad düzeltmesi (adsız katıya ad) anında uygulanır ve kural
olarak saklanır. "Kalanları kabul et ve DEVAM" True döner.

    xvfb-run -a python test/gui_standart_pencere.py
"""
import os, sys, time
import tkinter as tk
from tkinter import ttk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lisans_yardim                                              # noqa: E402
lisans_yardim.gecici_lisans()
import pf3_gui as G                                              # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder   # noqa: E402
from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir                                     # noqa: E402

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
M = u.M
# ayarlar geçici sözlükte: kullanıcının gerçek ayar dosyasına yazılmaz
AYAR = {}
M.ayar_oku = lambda: dict(AYAR)
M.ayar_yaz = lambda **y: AYAR.update(y)
u.M.benzerden_sinifla = lambda *a, **k: 0

kutu = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 60, 40, 5).Shape()
sil = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 6.0, 30.0).Shape()
u.kayit = [("SOLID", kutu), ("PIM", sil)]
u.komp = [
    {"kod": "SOLID", "ad": "SOLID", "adet": 3, "sinif": "parca", "tip": "", "indeks": [0],
     "hacim_mm3": 12000.0, "olc": [60.0, 40.0, 5.0], "isimsiz": True},
    {"kod": "PIM", "ad": "PIM", "adet": 1, "sinif": "parca", "tip": "", "indeks": [1],
     "hacim_mm3": 3392.9, "olc": [30.0, 12.0, 12.0], "aday": ["silindirik pim?"]},
]
u.satirlar = []
liste = M.kontrol_listesi(u.komp)
dogru("kontrol listesi 2 satır", len(liste) == 2, liste)
sonuc = {}


def senaryo():
    p = u._standart_pencere
    if not p:
        kok.after(200, senaryo); return
    ag, karar = p["ag"], p["karar"]
    cocuk = ag.get_children()
    dogru("pencerede 2 satır", len(cocuk) == 2)
    # 1. satır: adsız katı -> ad ver + ÜRETİM
    ag.selection_set(cocuk[0]); ag.event_generate("<<TreeviewSelect>>"); kok.update()
    t1 = time.time()
    while time.time() - t1 < 20:
        kok.update(); time.sleep(0.05)
        if any(id(k) in u._resim_onbellek for k in u.komp):
            break
    dogru("parça resmi çizildi (önbellekte)", id(u.komp[0]) in u._resim_onbellek)
    p["v_ad"].set("ARA BRAKET SACI")
    karar("parca"); kok.update()
    dogru("ad ve kod düzeltildi", u.komp[0]["ad"] == "ARA BRAKET SACI" and u.komp[0]["kod"] == "ARA BRAKET SACI",
          (u.komp[0]["ad"], u.komp[0]["kod"]))
    dogru("ad kuralı saklandı", any(v == "ARA BRAKET SACI" for v in (AYAR.get("ad_kurali") or {}).values()), AYAR)
    dogru("'isimsiz' işareti kalktı", "isimsiz" not in u.komp[0])
    # 2. satır: STANDART
    ag.selection_set(cocuk[1]); ag.event_generate("<<TreeviewSelect>>"); kok.update()
    karar("standart"); kok.update()
    dogru("PIM standart oldu", u.komp[1]["sinif"] == "standart", u.komp[1]["sinif"])
    dogru("sınıf kuralı saklandı", "standart" in (AYAR.get("sinif_kurali") or {}).values(), AYAR.get("sinif_kurali"))
    dogru("karar sütunu dolu", ag.set(cocuk[0], "karar").startswith("ÜRETİM") and ag.set(cocuk[1], "karar") == "STANDART",
          (ag.set(cocuk[0], "karar"), ag.set(cocuk[1], "karar")))
    # devam
    for b in p["w"].winfo_children():
        pass
    p["sonuc"]["cvp"] = True
    p["w"].destroy()


kok.after(300, senaryo)
cvp = u._standart_karar_penceresi(liste)
dogru("pencere True döndü (devam)", cvp is True, cvp)
dogru("kalan belirsiz parça yok", M.kontrol_listesi(u.komp) == [], M.kontrol_listesi(u.komp))
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
kok.destroy()
sys.exit(0 if not HATA else 1)
