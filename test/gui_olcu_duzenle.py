# -*- coding: utf-8 -*-
"""ÖLÇÜ / TOLERANS DÜZENLEME PENCERESİ (gerçek tkinter, xvfb).

Çıktı klasörü (DXF/ + pi3d_is.json) verilir, model YÜKLENMEZ. Denetim:
pencere detay resimlerini listeler; seçilen resmin numaralı ölçüleri
listede; önizleme PNG'si numara balonlarıyla çizilir; bir ölçüye özel ±,
birine toleransı sil, birine ölçüyü sil; KAYDET DXF'i düzenler, PDF'i
basar, düzenlemeyi parçanın ayarına kimlikle yazar.

    xvfb-run -a python test/gui_olcu_duzenle.py <çıktı klasörü>
    (klasör verilmezse sentetik resimle çalışır)
"""
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk                                              # noqa: E402
from tkinter import messagebox                                    # noqa: E402
import lisans_yardim                                              # noqa: E402
lisans_yardim.gecici_lisans()
import pf3_gui as G                                               # noqa: E402
import pf7_is as IS                                               # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


messagebox.showinfo = messagebox.showwarning = lambda *a, **k: None
messagebox.askyesno = lambda *a, **k: True
kaynak = sys.argv[1] if len(sys.argv) > 1 else None
on = tempfile.mkdtemp(prefix="pi3d_god_")
if kaynak:
    shutil.copytree(os.path.join(kaynak, "DXF"), os.path.join(on, "DXF"))
    shutil.copy(os.path.join(kaynak, IS.DURUM_DOSYASI), on)
else:
    import olcu_duzenle_denetimi as OD                            # noqa: F401  (sentetik t.dxf üretir)
    os.makedirs(os.path.join(on, "DXF"))
    doc, _l = OD.resim({})
    doc.saveas(os.path.join(on, "DXF", "P01_T.dxf"))
    IS.cizim_kaydet(on, "dxf", "P01_T.dxf", kod="T")
kok = tk.Tk()
u = G.Uygulama(kok)
t0 = time.time()
while u.M is None and time.time() - t0 < 120:
    kok.update(); time.sleep(0.05)
u.v_out.set(on)
AYAR = {}
u.M.ayar_oku = lambda: dict(AYAR)
u.M.ayar_yaz = lambda **y: AYAR.update(y)
w = u.olcu_duzenle_penceresi()
for _ in range(40):
    kok.update(); time.sleep(0.05)
p = u._olcu_pencere
ag_d, ag, durum = p["ag_d"], p["ag"], p["durum"]
dogru("resim listesi dolu", len(ag_d.get_children()) >= 1, len(ag_d.get_children()))
t1 = time.time()
while not durum["png"] and time.time() - t1 < 60:
    kok.update(); time.sleep(0.1)
dogru("numaralı ölçüler listede", len(ag.get_children()) >= 3, len(ag.get_children()))
dogru("önizleme (balonlu) çizildi", durum["png"] and os.path.isfile(durum["png"]))
dxf = durum["dxf"]
once = {x["no"]: x for x in u.M.olcu_listesi(dxf)}
nolar = [int(i) for i in ag.get_children()]
tol_no = next(n for n in nolar if once[n]["tur"] in ("konum", "gabari"))
ref_no = next(n for n in nolar if n != tol_no and once[n]["tur"] in ("konum", "gabari", "delik_cap"))
sil_no = next(n for n in nolar if n not in (tol_no, ref_no))
ag.selection_set(str(tol_no)); p["v_tol"].set("0,15"); p["isle"]("tol")
ag.selection_set(str(ref_no)); p["isle"]("ref")
ag.selection_set(str(sil_no)); p["isle"]("sil")
kok.update()
dogru("değişiklik sütunu", "SİLİNECEK" in ag.set(str(sil_no), "durum"), ag.set(str(sil_no), "durum"))
p["kaydet"]()
for _ in range(10):
    kok.update(); time.sleep(0.05)
sonra = {x["no"]: x for x in u.M.olcu_listesi(dxf)}
dogru("ölçü silindi", sil_no not in sonra, list(sonra)[:10])
dogru("özel ±0,15", sonra[tol_no]["tol"] == 0.15 and sonra[tol_no]["ozel"], sonra[tol_no])
dogru("tolerans silindi (referans)", sonra[ref_no]["ref"], sonra[ref_no])
dogru("değerler aynı", all(abs(sonra[n]["deger"] - once[n]["deger"]) < 1e-9 for n in sonra))
pdf_kl = u._pdf_klasoru()
pdfler = [a for a in os.listdir(pdf_kl)] if os.path.isdir(pdf_kl) else []
dogru("PDF basıldı", any(a.lower().endswith(".pdf") for a in pdfler), (pdf_kl, pdfler))
ad = os.path.basename(dxf)
kod = (IS.durum_oku(on)["dxf"].get(ad) or {}).get("kod")
tol = ((u.parca_ayar.get(kod) or {}).get("tolerans") or {})
dogru("düzenleme parçanın ayarına yazıldı", len(tol.get("sil") or []) == 1
      and len(tol.get("olcu") or {}) == 2, tol)
w.destroy()
kok.destroy()
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
