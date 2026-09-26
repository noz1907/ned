# -*- coding: utf-8 -*-
"""Yardım menüsü ve "Malzemeyi CAD'den al" sihirbazı - gerçek pencereyle.

Kullanıcının yapacağını sırayla yapar: menü var mı, sihirbaz açılıyor mu,
1. adım STEP raporu, 2. adımda SolidWorks seçimi, 3. adımda talimat ve
makronun kaydı, 4. adımda bir SolidWorks parça listesinin ÖNİZLENMESİ
(hangi parça eşleşti, hangisi dosyada yok, hangi ad tanınmadı) ve UYGULA
ile malzemenin parçalara işlenmesi.

tkinter + ekran ve gerçek pf3_olcu gerekir; yoksa "atlandi" deyip 0 ile
çıkar (derleme makinesinde tkinter olmayabilir):

    xvfb-run -a python3 test/gui_malzeme_sihirbazi.py
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import tkinter as tk
    import tkinter.messagebox as mb
    tk.Tk().destroy()
except Exception as ex:
    print(f"atlandi: tkinter/ekran yok ({type(ex).__name__}: {str(ex)[:60]})")
    sys.exit(0)

KUTU = []
for _t in ("showerror", "showinfo", "showwarning"):
    setattr(mb, _t, lambda *a, _t=_t, **k: KUTU.append((_t,) + a[:2]))

import pf3_gui as G                                              # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


kok = tk.Tk()
kok.report_callback_exception = lambda e, v, tb: HATA.append(f"tk: {v}")
u = G.Uygulama(kok)
t0 = time.time()
while u.M is None and time.time() - t0 < 120:
    kok.update(); time.sleep(0.05)
dogru("motor yüklendi", u.M is not None)

print("-- Yardım menüsü")
cubuk = kok.nametowidget(kok["menu"]) if kok["menu"] else None
etiket = []
if cubuk is not None:
    for i in range(cubuk.index("end") + 1):
        if cubuk.type(i) == "cascade":
            alt = kok.nametowidget(cubuk.entrycget(i, "menu"))
            etiket += [alt.entrycget(j, "label")
                       for j in range(alt.index("end") + 1)
                       if alt.type(j) == "command"]
print("     menü:", etiket)
dogru("Yardım menüsünde sihirbaz var",
      any("CAD'den al" in e for e in etiket), str(etiket))

# Montaj yerine elle kurulmuş iki parça (STEP okumaya gerek yok).
u.komp = [
    {"kod": "09.020.000.03", "ad": "09.020.000.03 Rollenplatte", "adet": 1,
     "sinif": "parca", "indeks": [0], "hacim_mm3": 1000.0, "tip": "",
     "malzeme_data": None},
    {"kod": "01.050.000.01", "ad": "01.050.000.01 U-Blech", "adet": 2,
     "sinif": "parca", "indeks": [1], "hacim_mm3": 1000.0, "tip": "",
     "malzeme_data": None},
    {"kod": "06.001.001.34", "ad": "06.001.001.34 Keil", "adet": 1,
     "sinif": "parca", "indeks": [2], "hacim_mm3": 1000.0, "tip": "",
     "malzeme_data": None}]
u.kayit = [None] * 3
u._agac_doldur()

print("-- sihirbaz")
u.malzeme_sihirbazi()
sz = u.sihirbaz
kok.update()
metin = lambda: "\n".join(                                       # noqa: E731
    w.get("1.0", "end") for w in _tum(sz.govde) if isinstance(w, tk.Text))


def _tum(w):
    for c in w.winfo_children():
        yield c
        yield from _tum(c)


dogru("1. adım: bilinmeyen malzeme sayısı gösteriliyor",
      "BİLİNMEYEN:              3" in metin(), metin()[:300])
sz.ileri(); kok.update()
sz.v_sis.set("solidworks")
sz.ileri(); kok.update()
dogru("3. adım: SolidWorks talimatında SW-Material geçiyor",
      "SW-Material" in metin(), metin()[:200])
kl = tempfile.mkdtemp(prefix="sihirbaz_")
y = sz.S6.makro_yaz("solidworks", kl)
dogru("SolidWorks makrosu kaydedildi", y and os.path.isfile(y), str(y))
if y:
    ic = open(y, encoding="cp1254").read()
    dogru("makro malzeme ve yoğunluk okuyor",
          "GetMaterialPropertyName2" in ic and "Density" in ic)
yc = sz.S6.makro_yaz("catia", kl)
dogru("CATIA makrosu kaydedildi", yc and os.path.isfile(yc), str(yc))
sz.ileri(); kok.update()

bom = os.path.join(kl, "sw_bom.csv")
with open(bom, "w", encoding="utf-8") as f:
    f.write("ITEM NO.,PART NUMBER,DESCRIPTION,SW-Material,SW-Density,QTY.\n"
            "1,09.020.000.03,Rollenplatte,AISI 304,7900,1\n"
            "2,01.050.000.01,U-Blech,Unobtainium,,2\n"
            "3,99.999.999.99,Montajda yok,Brass,8500,1\n")
sz.dosya_yukle(bom)
kok.update()
r = sz.rapor
satir = [sz.ag.item(i, "values") for i in sz.ag.get_children()]
print("     önizleme:")
for s in satir:
    print("       ", s)
print("     özet:", sz.v_ozet.get())
dogru("önizlemede 3 satır", len(satir) == 3, str(len(satir)))
dogru("yalnız 09.020.000.03 eşleşti",
      [k["kod"] for k, _m in r["eslesen"]] == ["09.020.000.03"],
      str([k["kod"] for k, _m in r["eslesen"]]))
dogru("tanınmayan ad raporlandı",
      [x["malzeme"] for x in r["taninmayan"]] == ["Unobtainium"])
dogru("tanınmayan adlı parça 'dosyada yok' SAYILMADI",
      [k["kod"] for k in r["adi_taninmayan"]] == ["01.050.000.01"]
      and [k["kod"] for k in r["eslesmeyen"]] == ["06.001.001.34"],
      f"{[k['kod'] for k in r['adi_taninmayan']]} / "
      f"{[k['kod'] for k in r['eslesmeyen']]}")
dogru("montajda karşılığı olmayan satır raporlandı",
      [x["kod"] for x in r["kullanilmayan"]] == ["99.999.999.99"])
dogru("UYGULA açık", str(sz.b_uygula["state"]) == "normal")
dogru("uygulamadan önce hiçbir şey değişmedi", not u.malzemeler,
      str(u.malzemeler))
sz.uygula()
kok.update()
dogru("uygulandı: 09.020.000.03 -> paslanmaz",
      u.malzemeler.get("09.020.000.03") == "paslanmaz", str(u.malzemeler))
dogru("diğer parçalara dokunulmadı", len(u.malzemeler) == 1,
      str(u.malzemeler))
dogru("hata kutusu çıkmadı", not [k for k in KUTU if k[0] == "showerror"],
      str(KUTU))
kok.destroy()

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                     else f"{len(HATA)} DENETIM KALDI: " + ", ".join(map(str, HATA))))
sys.exit(1 if HATA else 0)
