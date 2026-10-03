# -*- coding: utf-8 -*-
"""TOLERANS PENCERESİ ve PARÇA BAZLI K (gerçek tkinter, xvfb).

Kullanıcı: "tolerans düzeltme toplu ya da belirli ölçü, PDF / DXF
güncellensin"; "K değişimi parça bazlı, seçip yazıp değiştirebilmeliyim".
Denetim: 1) TOLERANS penceresi seçili parçanın ölçü listesini (arama
kutulu) açar; süreç / sınıf toplu, tek ölçüye özel ± yazılır; "yalnız
kaydet" parca_ayar[kod]["tolerans"]'a ve motor diline (_parca_ayar_p)
geçer; 2) açınım listesindeki K sütunu: k_duzenle ile parça bazlı K
yazılır, _k_parca motor diline verir, istisna kaydı K'yi silmez; 3)
motor (acilim_yaz) parça bazlı K'yi kullanır (sahte sac_acilim).

    xvfb-run -a python test/gui_tolerans_k.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk                                              # noqa: E402
from tkinter import ttk                                           # noqa: E402
import lisans_yardim                                              # noqa: E402
lisans_yardim.gecici_lisans()
import pf3_gui as G                                               # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


kok = tk.Tk()
u = G.Uygulama(kok)
t0 = time.time()
while u.M is None and time.time() - t0 < 120:
    kok.update(); time.sleep(0.05)
M = u.M
AYAR = {}
M.ayar_oku = lambda: dict(AYAR)
M.ayar_yaz = lambda **y: AYAR.update(y)
u.v_out.set("")                   # klasöre yazılmasın
u.kayit = []
u.komp = [{"kod": "SAC_1", "ad": "SAC 1", "adet": 1, "sinif": "parca", "indeks": [0]}]
u.satirlar = [{"kod": "SAC_1", "poz": 1, "olculer": [
    {"id": "ON|konum|yatay|400|0|500|400|500", "gorunus": "ON", "tur": "konum", "yon": "yatay",
     "deger": 400.0, "surec": "pres", "bant": 0.4, "tol": 0.2, "L_ref": 400.0, "uclar": (0, 500, 400, 500)},
    {"id": "ON|gabari|yatay|1.800|0|0|1800|0", "gorunus": "ON", "tur": "gabari", "yon": "yatay",
     "deger": 1800.0, "surec": "lazer", "bant": 1.5, "tol": 0.75, "L_ref": 1800.0, "uclar": (0, 0, 1800, 0)}]}]
u._istisna_kod = lambda: "SAC_1"


def senaryo():
    p = u._tolerans_pencere
    if not p:
        kok.after(150, senaryo); return
    ag = p["ag"]
    dogru("pencerede 2 ölçü", len(ag.get_children()) == 2)
    ag.v_ara.set("gabari"); kok.update()
    dogru("arama süzdü", len(ag.get_children()) == 1)
    ag.v_ara.set(""); kok.update()
    ilk = ag.get_children()[0]
    ag.selection_set(ilk); ag.event_generate("<<TreeviewSelect>>"); kok.update()
    p["v_tol"].set("0,1")
    for b in p["w"].winfo_children():
        pass
    # özel ± uygula: penceredeki "Uygula" düğmesini bul
    def dugme(w, metin):
        for c in w.winfo_children():
            try:
                if c.winfo_class() == "TButton" and c.cget("text") == metin:
                    return c
            except Exception:
                pass
            r = dugme(c, metin)
            if r:
                return r
        return None
    dugme(p["w"], "Uygula").invoke(); kok.update()
    dogru("özel ± satırda", "ÖZEL" in ag.set(ilk, "uyari") and ag.set(ilk, "tol") == "±0,1",
          (ag.set(ilk, "uyari"), ag.set(ilk, "tol")))
    p["v_surec"].set("CNC freze / torna")
    p["v_sinif"].set("ISO 2768-m (orta)")
    p["kaydet"](False)


kok.after(300, senaryo)
u.tolerans_penceresi()
tol = (u.parca_ayar.get("SAC_1") or {}).get("tolerans") or {}
dogru("tolerans kaydedildi (süreç, sınıf, özel)",
      tol.get("surec") == "cnc" and tol.get("sinif") == "iso2768-m"
      and abs(list((tol.get("olcu") or {}).values())[0] - 0.1) < 1e-9, tol)
dogru("motor diline geçti", (u._parca_ayar_p().get("SAC_1") or {}).get("tolerans") == tol)

# parça bazlı K
from tkinter import simpledialog                                   # noqa: E402
simpledialog.askstring = lambda *a, **k: "0,33"
u.ac_satir = {}
iid = u.ac_agac.insert("", "end", values=("1", "SAC_1", "SAC 1", "1,5", "", "", "", ""))
u.ac_satir[iid] = 0
u.k_duzenle(iid); kok.update()
dogru("K yazıldı (parca_ayar)", (u.parca_ayar.get("SAC_1") or {}).get("k_faktor") == 0.33, u.parca_ayar)
dogru("K sütununda 0,33", u.ac_agac.set(iid, "k") == "0,33", u.ac_agac.set(iid, "k"))
dogru("_k_parca motor dili", u._k_parca() == {M._tr_sade("SAC_1"): 0.33}, u._k_parca())
u.v_ist_gor.set("OTOMATİK")
u.istisna_kaydet()
dogru("istisna kaydı K ve toleransı silmedi",
      (u.parca_ayar.get("SAC_1") or {}).get("k_faktor") == 0.33
      and (u.parca_ayar.get("SAC_1") or {}).get("tolerans"), u.parca_ayar)

# motor: acilim_yaz parça bazlı K kullanır
kullanilan = []
M_sac = M.sac_acilim
M.sac_acilim = lambda sh, k, k_faktor=None, **kw: kullanilan.append(k_faktor) or {"hata": "sahte"}
import tempfile                                                    # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox                    # noqa: E402
from OCP.gp import gp_Pnt                                          # noqa: E402
kutu = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 100, 50, 1.5).Shape()
try:
    M.acilim_yaz([("SAC_1", kutu)], [dict(u.komp[0], indeks=[0])], u._P(), tempfile.mkdtemp(),
                 kodlar={"SAC_1"}, k_faktor=0.4, k_parca=u._k_parca(), log=lambda *_: None)
except Exception as ex:
    print("   (acilim_yaz:", str(ex)[:80], ")")
M.sac_acilim = M_sac
dogru("açınım parça bazlı K ile hesaplandı (0,33)", kullanilan and kullanilan[0] == 0.33, kullanilan)
kok.destroy()
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
