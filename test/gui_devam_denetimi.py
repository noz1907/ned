# -*- coding: utf-8 -*-
"""Önceki çıktıdan devam, süre paneli ve sınıf değiştirme - gerçek
pencereyle.

Kullanıcının yaptığı sırayla:
  1. BOM + DXF'leri çıkarmış, PDF'i unutmuş, programı kapatmış
     (klasör DXF/ ve ACINIM/ ile hazırlanır; STEP OKUNMAZ)
  2. programı açıp ÖNCEKİ ÇIKTIYI AÇ der
       -> 1. sayfada ne var ne yok yazıyor mu
       -> pafta sekmesi modeli okumadan açılıyor mu
  3. pafta listesi (DXF/ + ACINIM/, LZR/ hariç) -> PAFTAYA AL -> BAS
       -> PDF/ klasörüne PDF yazılıyor mu
  4. programı kapatıp yeniden açar, yine ÖNCEKİ ÇIKTIYI AÇ
       -> pafta kurulu resimler tanınıyor, BAS doğrudan açık mı
       -> PDF'i olan 'güncel' diye yazıyor mu
  5. sağdaki panelde işlemler ve toplam süre var mı; önceki oturumun
     işlemleri de geliyor mu
  6. 2. sekmede satır seçip 'Standart' deyince sınıf değişiyor ve kural
     saklanıyor mu (ayar dosyası geçici klasöre yönlendirilir)

tkinter + ekran gerekir; yoksa "atlandi" deyip 0 ile çıkar:

    xvfb-run -a python3 test/gui_devam_denetimi.py
"""
import os
import shutil
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

import ezdxf                                                     # noqa: E402
import pf3_gui as G                                              # noqa: E402
import pf7_is as IS                                              # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def cizim(yol, gen, boy):
    d = ezdxf.new("R2010", setup=True)
    m = d.modelspace()
    m.add_lwpolyline([(0, 0), (gen, 0), (gen, boy), (0, boy)], close=True)
    m.add_text("P", dxfattribs={"height": 3.5}).set_placement((5, 5))
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    d.saveas(yol)


def bekle(u, kok, sn=120):
    """Arka plandaki iş bitene kadar pencereyi döndür."""
    t0 = time.time()
    kok.update()
    while u.calisiyor and time.time() - t0 < sn:
        kok.update(); time.sleep(0.03)
    for _ in range(10):
        kok.update(); time.sleep(0.01)


def sekme_acik(u, i):
    return str(u.defter.tab(i, "state")) == "normal"



def ikinci_oturum(cikti):
    """Programı kapatıp yeniden açan kullanıcı: yeni süreç, aynı klasör."""
    print("-- 2. oturum: yeniden aç, pafta ve PDF tanınıyor mu")
    kok = tk.Tk()
    kok.report_callback_exception = lambda e, v, tb: HATA.append(f"tk: {v}")
    u = G.Uygulama(kok)
    t0 = time.time()
    while u.M is None and time.time() - t0 < 120:
        kok.update(); time.sleep(0.05)
    u.M.AYAR_DOSYA = os.path.join(cikti, "_ayar.json")
    u.onceki_ac(cikti); kok.update()
    oz = u.v_onceki.get()
    dogru("özette 3 PDF", "PDF ................ 3" in oz, oz)
    u.defter.select(6); bekle(u, kok)       # sekmeye geçince liste dolar
    durum = [u.pf_agac.item(i, "values")[5] for i in u.pf_agac.get_children()]
    print("     " + "\n     ".join(durum))
    dogru("liste sekmeye geçince kendiliğinden doldu", len(durum) == 3, str(durum))
    dogru("hepsi 'PDF'i var (güncel)'",
          all(d.startswith("PDF'i var (güncel)") for d in durum), str(durum))
    dogru("BAS doğrudan açık", str(u.b_bas["state"]) == "normal")
    sure = [u.sure_agac.item(i, "values")[0] for i in u.sure_agac.get_children()]
    dogru("önceki iki oturumun işlemleri geldi", len(sure) >= 5, str(sure))

    print("-- sınıf değiştirme (2. sekme)")
    u.komp = [
        {"kod": "K0 KAMERA", "ad": "K0 KAMERA", "adet": 1, "sinif": "standart",
         "tip": "ticari ürün", "indeks": [0], "hacim_mm3": 1.0,
         "malzeme_data": None},
        {"kod": "COMPOUND", "ad": "COMPOUND", "adet": 1, "sinif": "parca",
         "tip": "", "indeks": [1], "hacim_mm3": 375.9, "olc": [5.1, 15.0, 15.2],
         "malzeme_data": None, "isimsiz": True}]
    u.kayit = [None, None]
    u.agac = None
    u.acilim_liste = []
    u._acilim_doldur = lambda: None           # tarama gerçek katı ister
    u._agac_doldur()
    satir = {u.ag.item(i, "values")[1]: i for i in u.ag.get_children()}
    u.ag.selection_set(satir["COMPOUND"]); kok.update()
    u.sinif_degistir("standart"); kok.update()
    dogru("COMPOUND standart oldu", u.komp[1]["sinif"] == "standart")
    kural = u.M.ayar_oku().get("sinif_kurali") or {}
    dogru("adsız katının kuralı ADLA değil parmak iziyle saklandı",
          kural.get("geo:375.9:5.1x15.0x15.2") == "standart"
          and "compound" not in kural, str(kural))
    dogru("başka bir COMPOUND bundan etkilenmiyor",
          u.M.sinifla("COMPOUND", kural)[0] == "parca")
    dogru("aynı parmak izli COMPOUND tanınıyor",
          u.M._kural(kural, {"ad": "COMPOUND", "hacim_mm3": 375.9,
                             "olc": [5.1, 15.0, 15.2]}) == "standart")
    satir = {u.ag.item(i, "values")[1]: i for i in u.ag.get_children()}
    u.ag.selection_set(satir["K0 KAMERA"]); kok.update()
    u.sinif_degistir("parca"); kok.update()
    dogru("K0 KAMERA üretim parçası oldu", u.komp[0]["sinif"] == "parca")
    dogru("hata kutusu çıkmadı", not [k for k in KUTU if k[0] == "showerror"],
          str(KUTU))
    kok.destroy()
    os._exit(1 if HATA else 0)


if len(sys.argv) > 2 and sys.argv[1] == "--ikinci":
    ikinci_oturum(sys.argv[2])


cikti = tempfile.mkdtemp(prefix="devam_gui_")
ayar_eski = None
try:
    cizim(os.path.join(cikti, "DXF", "P01_01_001_Plaka.dxf"), 180, 90)
    cizim(os.path.join(cikti, "DXF", "00_MONTAJ.dxf"), 900, 500)
    cizim(os.path.join(cikti, "ACINIM", "P01_01_001_Plaka_acinim.dxf"), 260, 120)
    cizim(os.path.join(cikti, "LZR", "P01_01_001_Plaka_Lzr.dxf"), 260, 120)
    with open(os.path.join(cikti, "BOM.csv"), "w", encoding="utf-8-sig") as f:
        f.write("poz;kod;ad;adet;sinif;tip;malzeme_ad;olcu;kg_adet;toplam_kg;dxf\n"
                "1;01.001;01.001 Plaka;2;parca;;Celik;180x90x5;0,636;1,272;"
                "P01_01_001_Plaka.dxf\n")
    IS.islem_kaydet(cikti, "Model okuma: onceki.stp", 236.0)
    IS.islem_kaydet(cikti, "Tüm çizimler", 610.0)

    print("-- 1. oturum: ÖNCEKİ ÇIKTIYI AÇ")
    kok = tk.Tk()
    kok.report_callback_exception = lambda e, v, tb: HATA.append(f"tk: {v}")
    u = G.Uygulama(kok)
    t0 = time.time()
    while u.M is None and time.time() - t0 < 120:
        kok.update(); time.sleep(0.05)
    dogru("motor yüklendi", u.M is not None)
    # ayar dosyası geçici yere: kullanıcının gerçek ayarına dokunma
    ayar_eski = u.M.AYAR_DOSYA
    u.M.AYAR_DOSYA = os.path.join(cikti, "_ayar.json")

    u.onceki_ac(cikti)
    kok.update()
    oz = u.v_onceki.get()
    print("     " + oz.replace("\n", "\n     "))
    dogru("özet: 1 detay + montaj + 1 açınım + 1 lazer",
          "detay resmi (DXF) .. 1" in oz and "montaj resmi ....... var" in oz
          and "açınım ............. 1" in oz and "lazer (LZR) ........ 1" in oz,
          oz)
    dogru("pafta sekmesi modelsiz açık", sekme_acik(u, 6))
    dogru("çizim listesi sekmesi açık", sekme_acik(u, 4))
    dogru("BOM sekmesi KAPALI (model yok)", not sekme_acik(u, 1))
    liste = list(u.liste.get(0, "end"))
    dogru("5. sekme listesi klasör düzeniyle",
          "DXF/P01_01_001_Plaka.dxf" in liste and "LZR/P01_01_001_Plaka_Lzr.dxf" in liste,
          str(liste))
    sure = [u.sure_agac.item(i, "values") for i in u.sure_agac.get_children()]
    dogru("önceki oturumun işlemleri panelde", len(sure) == 2
          and "Tüm çizimler" in sure[1][0], str(sure))
    dogru("klasör toplamı 14 dk 06 sn", "14 dk 06 sn" in u.v_toplam.get(),
          u.v_toplam.get())

    print("-- pafta ve PDF")
    u.defter.select(6); kok.update()
    u.pafta_doldur(); bekle(u, kok)
    dosya = [u.pf_agac.item(i, "values")[0] for i in u.pf_agac.get_children()]
    dogru("pafta listesi DXF + ACINIM, LZR yok",
          sorted(dosya) == ["00_MONTAJ.dxf", "P01_01_001_Plaka.dxf",
                            "P01_01_001_Plaka_acinim.dxf"], str(dosya))
    dogru("BAS kapalı (henüz pafta yok)", str(u.b_bas["state"]) == "disabled")
    u.pafta_uret(); bekle(u, kok)
    u.pf_agac.selection_set(u.pf_agac.get_children())
    u.pafta_bas(); bekle(u, kok, 240)
    pdf = sorted(os.listdir(os.path.join(cikti, "PDF"))) \
        if os.path.isdir(os.path.join(cikti, "PDF")) else []
    dogru("3 PDF, PDF/ klasöründe", len(pdf) == 3, str(pdf))
    sure = [u.sure_agac.item(i, "values")[0] for i in u.sure_agac.get_children()]
    dogru("panelde pafta ve PDF işlemleri",
          any(s.startswith("Pafta (3") for s in sure)
          and any(s.startswith("PDF basımı (3") for s in sure), str(sure))
    dogru("bu oturumun toplamı yazıyor",
          "TOPLAM (bu oturum)" in u.v_toplam.get(), u.v_toplam.get())
    kok.destroy()

    # Programı kapatıp yeniden açmak: 2. oturum AYRI süreçte.
    import subprocess
    r = subprocess.run([sys.executable, os.path.abspath(__file__), "--ikinci",
                        cikti], capture_output=True, text=True, timeout=600)
    print("\n".join(l for l in r.stdout.splitlines() if l.startswith(("--", "  ", "     "))))
    for l in r.stdout.splitlines():
        if l.startswith("  HATA"):
            HATA.append("2. oturum: " + l[8:60])
    if r.returncode not in (0, 1):
        HATA.append(f"2. oturum çöktü ({r.returncode}): {r.stderr[-300:]}")
finally:
    if ayar_eski:
        import pf3_olcu
        pf3_olcu.AYAR_DOSYA = ayar_eski
    shutil.rmtree(cikti, ignore_errors=True)

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                     else f"{len(HATA)} DENETIM KALDI: " + ", ".join(map(str, HATA))))
os._exit(1 if HATA else 0)
