# -*- coding: utf-8 -*-
"""Logo denetimi.

Iki surum var: logolu ve logosuz. Ikisinin de calismasi gerekir.

  1. Gomulu resimler logo/ klasorundekilerle BIREBIR AYNI mi?
     (Gomulu kopya bozuksa ekranda bozuk logo cikar, kimse fark etmez.)
  2. Gomulu modul yoksa klasore dusuyor mu? (kaynak koddan calistiranlar)
  3. Ikisi de yoksa program cokmuyor, logo_var() False diyor mu?
     (Logosuz surumde baslikta yalniz "Pi3D" yazmasini bu saglar.)
"""
import base64
import hashlib
import os
import sys
import types

# pf3_olcu agir; arayuz modulunu tkinter olmadan da okuyabilelim diye
# sahte tk konur. Logo islevleri tk'siz calisir, PhotoImage'a girmez.
class _Sahte:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return _Sahte()
    def __getattr__(self, ad): return _Sahte()


tk = types.ModuleType("tkinter")
for ad in ("Tk", "Frame", "Canvas", "Text", "PhotoImage", "Label", "Button",
           "Entry", "StringVar", "BooleanVar", "IntVar", "DoubleVar"):
    setattr(tk, ad, _Sahte)
tk.TclError = Exception
tk.END = "end"
ttk = types.ModuleType("tkinter.ttk")
for ad in ("Frame", "Label", "Button", "Entry", "Combobox", "Notebook",
           "Treeview", "Scrollbar", "Progressbar", "Checkbutton",
           "Radiobutton", "LabelFrame", "Style", "Separator", "PanedWindow"):
    setattr(ttk, ad, _Sahte)
fd = types.ModuleType("tkinter.filedialog")
fd.askopenfilename = fd.askdirectory = fd.asksaveasfilename = _Sahte()
mb = types.ModuleType("tkinter.messagebox")
mb.showinfo = mb.showwarning = mb.showerror = mb.askyesno = _Sahte()
tk.ttk, tk.filedialog, tk.messagebox = ttk, fd, mb
sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk,
                    "tkinter.filedialog": fd, "tkinter.messagebox": mb})

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import pf3_gui as G                                           # noqa: E402

hata = []


def dogru(ad, kosul, aciklama=""):
    if kosul:
        print(f"  tamam {ad}")
    else:
        hata.append(f"{ad}: {aciklama}")
        print(f"  HATA  {ad}: {aciklama}")


def ozet(b):
    return hashlib.sha256(b).hexdigest()


print("\n-- gomulu resimler klasordekiyle ayni mi")
gomulu = getattr(G, "_GOMULU", None)
dogru("pi3d_logo bulundu", gomulu is not None,
      "gomulu modul yok - logo_gom.py calistirilmali")
if gomulu:
    for ad, b64 in gomulu.LOGO.items():
        y = os.path.join(KOK, "logo", ad)
        if not os.path.isfile(y):
            dogru(f"{ad} klasorde var", False, "klasorde yok")
            continue
        dogru(f"{ad} birebir ayni",
              ozet(base64.b64decode(b64)) == ozet(open(y, "rb").read()),
              "gomulu kopya klasordekinden farkli")

print("\n-- arayuzun kullandigi resimler gomuldu mu")
for ad in ("pi3d.ico", "pi3d_72.png", "pi3d_64.png", "pivision_64.png"):
    dogru(f"{ad} var", G.logo_baytlari(ad) is not None, "hicbir yerde yok")
dogru("logo_var() dogru", G.logo_var() is True, "logolu surumde False dedi")

print("\n-- gomulu modul olmasa klasore duser mi")
G._GOMULU = None
try:
    ham = G.logo_baytlari("pi3d_64.png")
    dogru("klasorden okundu", ham is not None, "klasorden de okuyamadi")
    if ham:
        dogru("klasordeki dosyayla ayni",
              ozet(ham) == ozet(open(os.path.join(KOK, "logo",
                                                  "pi3d_64.png"), "rb").read()),
              "farkli bayt dondu")
    dogru("logo_var() hala True", G.logo_var() is True, "False dedi")

    print("\n-- LOGOSUZ surum: ikisi de yoksa")
    eski = G.LOGO_KLASOR
    G.LOGO_KLASOR = "boyle_bir_klasor_yok"
    try:
        dogru("logo_baytlari None donuyor",
              G.logo_baytlari("pi3d_64.png") is None, "bir sey dondurdu")
        dogru("logo_yukle None donuyor",
              G.logo_yukle("pi3d_64.png") is None, "bir sey dondurdu")
        dogru("logo_var() False", G.logo_var() is False, "True dedi")
        dogru("ikon baytlari da yok",
              G.logo_baytlari("pi3d.ico") is None, "ikon bulundu")
    finally:
        G.LOGO_KLASOR = eski
finally:
    G._GOMULU = gomulu

print("\nSONUC:", "TUM DENETIMLER GECTI" if not hata
      else f"{len(hata)} HATA\n  " + "\n  ".join(hata))
sys.exit(1 if hata else 0)
