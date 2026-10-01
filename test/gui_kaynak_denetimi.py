# -*- coding: utf-8 -*-
"""Kaynak resimleri düğmesi ve malzeme düğmeleri - gerçek pencereyle.

Kullanıcının bildirdiği sorun: "çizim esnasında program takılıyor, çok
uzun ve bitmiyor". Kaynak resimleri "tüm çizimler"in sonuna eklenmişti;
ilerleme çubuğu dolduktan sonra büyük modelde dakikalarca hiçbir şey
göstermeden çalışıyordu. Şimdi AYRI bir iştir.

Denetlenen:
  1. 5. sayfada KAYNAK RESİMLERİ düğmesi var, model kaynak içeriyorsa açık,
  2. basınca KAYNAK/<grup>_kaynak.pdf'ler yazılıyor, ilerleme çubuğu
     sona geliyor, günlükte grup grup "[1/2] ... çiziliyor" yazıyor,
     iş TAMAMLANDI ile bitiyor,
  3. İptal: iş hemen iptal edilirse TAMAMLANDI değil İPTAL görünüyor,
  4. malzeme düğmelerinde yalnız "csv" yazmıyor (Excel de okunuyor).

tkinter + ekran gerekir; yoksa "atlandi" deyip 0 ile çıkar:

    xvfb-run -a python3 test/gui_kaynak_denetimi.py
"""
import os
import sys
import tempfile
import time

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
sys.path.insert(0, os.path.join(KOK, "test"))
try:
    import tkinter as tk
    import tkinter.messagebox as mb
    from tkinter import ttk
    tk.Tk().destroy()
except Exception as ex:
    print(f"atlandi: tkinter/ekran yok ({type(ex).__name__}: {str(ex)[:60]})")
    sys.exit(0)

KUTU = []
for _t in ("showerror", "showinfo", "showwarning"):
    setattr(mb, _t, lambda *a, _t=_t, **k: KUTU.append((_t,) + a[:2]))

import os as _os, sys as _sys                                     # noqa: E402
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__))))
import lisans_yardim                                              # noqa: E402
lisans_yardim.gecici_lisans()        # geçici TAM lisans: kapılar açık
import pf3_gui as G                                              # noqa: E402
from kaynak_resmi_denetimi import model                          # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def bekle(u, kok, sn=300):
    t0 = time.time()
    kok.update()
    while u.calisiyor and time.time() - t0 < sn:
        kok.update(); time.sleep(0.03)
    for _ in range(10):
        kok.update(); time.sleep(0.01)


def tum(w):
    for c in w.winfo_children():
        yield c
        yield from tum(c)


def main():
    print("kaynak resimleri düğmesi (gerçek pencere)")
    kok = tk.Tk()
    u = G.Uygulama(kok)
    t0 = time.time()
    while u.M is None and time.time() - t0 < 120:
        kok.update(); time.sleep(0.05)
    yazilar = [str(w.cget("text")) for w in tum(kok) if isinstance(w, ttk.Button)]
    dogru("malzeme yükle düğmesi Excel diyor",
          any("Malzeme listesi yükle" in t and "Excel" in t for t in yazilar), yazilar)
    dogru("hiçbir düğme 'malzeme.csv' demiyor",
          not any("malzeme.csv" in t for t in yazilar), yazilar)

    kayit, komp, agac = model()
    with tempfile.TemporaryDirectory() as on:
        u.kayit, u.komp, u.agac = kayit, komp, agac
        u.v_out.set(on)
        u._bitir()
        kok.update()
        dogru("KAYNAK RESİMLERİ düğmesi açık", str(u.b_kaynak.cget("state")) == "normal",
              u.b_kaynak.cget("state"))
        gunluk = []
        eski = u._yaz
        u._yaz = lambda m: (gunluk.append(str(m)), eski(m))[1]
        ilerle = []
        asil_put = u.kuyruk.put
        u.kuyruk.put = lambda m: (ilerle.append(m[1]) if m[0] == "ilerleme" else None,
                                  asil_put(m))[1]
        u.kaynak_resimleri_uret()
        dogru("iş başladı", u.calisiyor)
        dogru("çalışırken düğme kapalı", str(u.b_kaynak.cget("state")) == "disabled")
        bekle(u, kok)
        kl = os.path.join(on, "KAYNAK")
        pdf = sorted(a for a in os.listdir(kl)) if os.path.isdir(kl) else []
        dogru("iki kaynak resmi yazıldı",
              pdf == ["GOVDE_GRUBU_kaynak.pdf", "LAMA_GRUBU_kaynak.pdf"], pdf)
        # (iş bitince çubuk sıfırlanır; iş SIRASINDA gelen bildirimlere bakılır)
        dogru("ilerleme adım adım sona geldi",
              len(ilerle) > 3 and ilerle[-1][0] == ilerle[-1][1] > 1
              and all(a[0] <= b[0] for a, b in zip(ilerle, ilerle[1:])), ilerle)
        u.kuyruk.put = asil_put
        dogru("günlükte grup grup ilerleme", any("[1/2]" in g and "çiziliyor" in g
                                                  for g in gunluk), gunluk[-6:])
        dogru("TAMAMLANDI", "TAMAMLANDI" in u.v_simdi.get(), u.v_simdi.get())
        dogru("hata kutusu çıkmadı", not [k for k in KUTU if k[0] == "showerror"], KUTU)

        # iptal
        u.kaynak_resimleri_uret()
        u.iptal()
        bekle(u, kok)
        dogru("İptal edilince İPTAL görünüyor", "İPTAL" in u.v_simdi.get(), u.v_simdi.get())
        dogru("iptal sonrası düğme yine açık", str(u.b_kaynak.cget("state")) == "normal")
    kok.destroy()
    print()
    if HATA:
        print(f"{len(HATA)} HATA")
        sys.exit(1)
    print("SONUC: TUM DENETIMLER GECTI")


if __name__ == "__main__":
    main()
