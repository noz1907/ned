# -*- coding: utf-8 -*-
"""BOM sayfası: ARAMA ve SEÇİLİ PARÇANIN RESMİ - gerçek pencereyle.

Kullanıcı istekleri:
  1. "BOM çıktıktan sonra malzemesi değişecek ya da belirsiz parçayı
     listeden seçince ufak da olsa resmini görebilirsem malzeme / standart
     / parça kararını daha hızlı veririz."
  2. "Ürün arayabileyim: bir parça vardı, liste tamamlanınca sıralama
     değiştiği için göremedim; o kadar parça arasında satır satır baktım,
     listede olduğundan eminim ama gözden kaçıyor."

Denetlenen:
  1. arama kutusu: kod / tanım içinde geçen her satır bulunur, büyük-küçük
     harf ve Türkçe İ/ı fark etmez; Enter sıradakine gider, sayaç "1 / 2";
     olmayan metin "bulunamadı",
  2. bulunan satır seçilir ve görünür olur (kapalı montaj dalı açılır),
  3. seçili parçanın izometrik resmi sağdaki pencerede çizilir (çizgi var),
     alt montaj satırında resim yok, yazı var.

tkinter + ekran gerekir; yoksa "atlandi" deyip 0 ile çıkar:

    xvfb-run -a python3 test/gui_bom_arama_denetimi.py
"""
import os
import sys
import time

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
sys.path.insert(0, os.path.join(KOK, "test"))
try:
    import tkinter as tk
    tk.Tk().destroy()
except Exception as ex:
    print(f"atlandi: tkinter/ekran yok ({type(ex).__name__}: {str(ex)[:60]})")
    sys.exit(0)

import pf3_gui as G                                              # noqa: E402
from kaynak_resmi_denetimi import model                          # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def bekle(kok, kosul, sn=60):
    t0 = time.time()
    while not kosul() and time.time() - t0 < sn:
        kok.update()
        time.sleep(0.03)
    kok.update()


def main():
    print("BOM sayfası: arama ve parça resmi (gerçek pencere)")
    kok = tk.Tk()
    u = G.Uygulama(kok)
    bekle(kok, lambda: u.M is not None, 120)
    kayit, komp, agac = model()
    u._komponent_geldi(kayit, komp, agac)
    kok.update()
    satir = list(u._tum_satirlar())
    dogru("ağaç doldu", len(satir) >= 4, len(satir))

    # 1. arama: küçük harfle "lama" -> LAMA_A, LAMA_B (ve LAMA_GRUBU montajı)
    u.v_ara.set("lama")
    u.ara_bul()
    kok.update()
    bulunan = list(u._ara_liste)
    degerler = [u.ag.item(i, "values")[1:3] for i in bulunan]
    dogru("küçük harfle aranınca LAMA satırları bulundu",
          any("LAMA_A" in " ".join(v) for v in degerler)
          and any("LAMA_B" in " ".join(v) for v in degerler), degerler)
    dogru("ilk bulunan seçili", u.ag.selection() == (bulunan[0],), u.ag.selection())
    dogru("sayaç 1 / n", u.v_ara_sonuc.get() == f"1 / {len(bulunan)}", u.v_ara_sonuc.get())
    u.ara_bul()
    kok.update()
    dogru("Enter sıradakine gider", u.ag.selection() == (bulunan[1],)
          and u.v_ara_sonuc.get().startswith("2 / "), (u.ag.selection(), u.v_ara_sonuc.get()))
    # bulunan satırın bütün üst dalları açık (görünür)
    ust = u.ag.parent(bulunan[1])
    acik = True
    while ust:
        acik = acik and bool(u.ag.item(ust, "open"))
        ust = u.ag.parent(ust)
    dogru("bulunan satır görünür (üst dallar açık)", acik)
    # Türkçe harf farkı yok: "dik", "dık", "DİK" hepsi DIK parçasını bulur
    # (CAD adları Türkçe harfsiz yazılır)
    for q in ("dik", "dık", "DİK"):
        u.v_ara.set(q)
        u.ara_bul()
        kok.update()
        bul = [u.ag.item(i, "values")[1] for i in u._ara_liste]
        dogru(f"'{q}' DIK parçasını buluyor", "DIK" in bul, bul)
    u.v_ara.set("yokboyleparca")
    u.ara_bul()
    kok.update()
    dogru("olmayan metin: bulunamadı", u.v_ara_sonuc.get() == "bulunamadı",
          u.v_ara_sonuc.get())

    # 2. parça resmi: TABAN seç -> çizgiler
    u.v_ara.set("TABAN")
    u.ara_bul()
    bekle(kok, lambda: len(u.c_parca.find_withtag("all")) > 3, 180)
    cizgi = [i for i in u.c_parca.find_all() if u.c_parca.type(i) == "line"]
    dogru("seçili parçanın resmi çizildi", len(cizgi) >= 8, len(cizgi))
    dogru("parça adı yazıyor", "TABAN" in u.v_parca_ad.get(), u.v_parca_ad.get())
    xs = [x for i in cizgi for x in u.c_parca.coords(i)[0::2]]
    dogru("resim pencereye sığıyor", xs and min(xs) >= 0 and max(xs) <= 231,
          (min(xs), max(xs)) if xs else None)
    # ikinci seçimde önbellekten, anında
    u.v_ara.set("LAMA_A")
    u.ara_bul()
    bekle(kok, lambda: "LAMA_A" in u.v_parca_ad.get(), 10)
    bekle(kok, lambda: any(u.c_parca.type(i) == "line" for i in u.c_parca.find_all()), 60)
    u.v_ara.set("TABAN")
    u.ara_bul()
    kok.update()
    cizgi2 = [i for i in u.c_parca.find_all() if u.c_parca.type(i) == "line"]
    dogru("aynı parça ikinci kez önbellekten, beklemeden", len(cizgi2) == len(cizgi),
          (len(cizgi2), len(cizgi)))
    # alt montaj satırı
    u.v_ara.set("GOVDE_GRUBU")
    u.ara_bul()
    kok.update()
    dogru("alt montajda resim yerine yazı",
          "alt montaj" in u.v_parca_ad.get() or "satır seçin" in u.v_parca_ad.get(),
          u.v_parca_ad.get())
    kok.destroy()
    print()
    if HATA:
        print(f"{len(HATA)} HATA")
        sys.exit(1)
    print("SONUC: TUM DENETIMLER GECTI")


if __name__ == "__main__":
    main()
