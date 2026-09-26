# -*- coding: utf-8 -*-
"""Arayuz dongusu: is bitince sonuc ekrana GERCEKTEN geliyor mu?

Sahada cikan hata suydu: kuyruk dongusunde bir mesaj islenirken hata
olunca dongu oluyor, motor isini bitiriyor ama sonucu kimse almiyordu.
Ekranda "STEP okunuyor" yazili kaliyor, program bitmis gibi gorunmuyordu.

Bu betik pf3_olcu yerine 8 saniye uyuyan SAHTE bir motor koyar, arayuzu
acar, INCELE'ye basar ve durum cubugunu izler. Is bitince durumun
"komponentler hazir" satirina donmesi gerekir.

tkinter ve bir X ekrani gerekir:  xvfb-run -a python3 test/gui_dongu_denetimi.py
Ikisi de yoksa betik "atlandi" deyip 0 ile ciker.
"""
import os, sys, threading, time, types

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

try:
    import tkinter as tk
    import tkinter.messagebox as mb
    tk.Tk().destroy()
except Exception as ex:
    print(f"atlandi: tkinter/ekran yok ({type(ex).__name__}: {str(ex)[:60]})")
    sys.exit(0)

UYKU = 8.0

sahte = types.ModuleType("pf3_olcu")
sahte.MALZEME = {"celik": ("Celik (S235JR / St37)", 7.85)}
sahte.VARSAYILAN_MALZEME = "celik"
sahte.K_FAKTOR = 0.40
sahte.RHO = 7.85e-6
sahte.GORUNUS = {k: ((0, -1, 0), (1, 0, 0))
                 for k in ("ON", "ARKA", "SAG", "SOL", "UST", "ALT")}
sahte.GORUNUS_AD = {"ON": "ÖN", "ARKA": "ARKA", "SAG": "SAĞ", "SOL": "SOL",
                    "UST": "ÜST", "ALT": "ALT"}
sahte.VARSAYILAN_GORUNUS = ("ON", "SAG", "SOL", "UST")
sahte.EN_COK_GORUNUS = 4
sahte.KESIT_AD = "KESIT"


class _E:
    class OkunamazBicim(Exception):
        pass

    @staticmethod
    def bicim_tani(y):
        return "STEP"


sahte.E = _E()
sahte.k_faktor_ayari = lambda: 0.40
sahte.ayar_yaz = lambda **k: k
sahte.ayar_oku = lambda: {}
sahte.poz_numaralari = lambda komp, poz_harita=None: {i: i + 1 for i in range(len(komp))}
sahte.malzeme_tahmin = lambda *a, **k: None
sahte.malzeme_ata = lambda k, esl, genel: (genel, "genel")
sahte.gorunus_sec = lambda g: tuple(g or sahte.VARSAYILAN_GORUNUS)
sahte.yogunluk_kg_mm3 = lambda m: 7.85e-6
sahte.agac_derinlik = lambda a: 2
sahte.agac_dugum_sayisi = lambda a: 4
sahte.agac_bom = lambda agac, komp, satirlar: [
    {"poz": str(i + 1), "seviye": 0, "tur": "parca", "kod": k["kod"],
     "ad": k["ad"], "adet": 1, "toplam_adet": 1, "sinif": "parca",
     "malzeme_ad": "Celik", "malzeme_kaynak": "genel",
     "kutle_kg": 1.0, "toplam_kg": 1.0} for i, k in enumerate(komp)]


def _oku(yol, P, log=print):
    log(f"sahte motor: {UYKU:.0f} saniyelik agir okuma taklidi")
    time.sleep(UYKU)
    komp = [{"kod": f"PRC.{i}", "ad": f"parca {i}", "adet": 1,
             "sinif": "parca", "tip": "", "indeks": [i],
             "hacim_mm3": 1000.0, "malzeme_data": None} for i in range(3)]
    return [(0, None)] * 3, komp, {"ad": "montaj", "cocuk": [], "adet": 1}


sahte.step_komponentleri = _oku
sahte.calistir = lambda *a, **k: []
sys.modules["pf3_olcu"] = sahte

mb.showerror = mb.showinfo = mb.showwarning = lambda *a, **k: None
import pf3_gui as G

kok = tk.Tk()
u = G.Uygulama(kok)
u.pack(fill="both", expand=True)
u.v_step.set(__file__)                  # varligi yeten herhangi bir dosya
u.v_out.set(os.path.join(KOK, "_gui_deneme_cikti"))

t0 = time.time()
durumlar, bitti = [], []


def izle():
    d = u.v_durum.get()
    if not durumlar or durumlar[-1] != d:
        durumlar.append(d)
    # Sonuç ekrana geldi mi: durum çubuğunda 2. adımın yönlendirmesi
    # görünüyor ve parça listesi dolu.
    if not bitti and "komponentler hazır" in d and u.komp:
        bitti.append(time.time() - t0)
    # Arka plandaki açınım taraması da bitsin: yönlendirmeyi SİLMEMELİ,
    # yanına eklemeli (silindiği bir hata vardı).
    if bitti and "bükümlü sac" in d:
        kok.destroy()
        return
    if time.time() - t0 > UYKU + 12:
        kok.destroy()
        return
    kok.after(200, izle)


threading.Thread(target=lambda: (time.sleep(1.5),
                                 kok.after(0, u.incele)), daemon=True).start()
kok.after(200, izle)
kok.mainloop()

gunluk = "\n".join(durumlar)
# Tarama bittikten sonra da yönlendirme durum çubuğunda kalmalı.
if bitti and not any("komponentler hazır" in d for d in durumlar[-1:]):
    print("HATA   2. adımın yönlendirmesi durum çubuğundan silindi:")
    print("         " + durumlar[-1])
    sys.exit(1)
if bitti:
    print(f"TAMAM  sonuc {bitti[0]:.1f} saniyede ekrana geldi "
          f"(sahte is {UYKU:.0f} s)")
    print(f"       durum cubugu {len(durumlar)} kez degisti - arayuz donmadi")
    sys.exit(0)
print("HATA   is bitti ama sonuc ekrana GELMEDI.")
print("       gorulen durumlar:\n         " + "\n         ".join(durumlar[-6:]))
sys.exit(1)
