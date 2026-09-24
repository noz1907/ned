# -*- coding: utf-8 -*-
"""7. adim (PAFTA) bastan sona calisiyor mu?

Sayfanin kurulmasi yetmez: kullanicinin yaptigi sirayla
  klasor sec -> Listeyi tazele -> Tumunu sec -> PAFTAYA AL -> BAS
adimlarinin hepsi denenir ve dosyalarin gercekten yazildigi
dogrulanir. Arayuzun is parcaciklari burada SIRAYLA calistirilir,
kuyruk elle bosaltilir; boylece tkinter'siz makinede de kosar.
"""
import os
import shutil
import sys
import tempfile
import types

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)


class SahteVar:
    def __init__(self, value=None, **k): self._v = value
    def get(self): return self._v
    def set(self, v): self._v = v
    def trace_add(self, *a, **k): pass


class SahteWidget:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return SahteWidget()
    def __getattr__(self, ad): return SahteWidget()
    def __setitem__(self, k, v): pass
    def __getitem__(self, k): return SahteWidget()


mesaj = []
tk = types.ModuleType("tkinter")
for ad in ("Tk", "Frame", "Canvas", "Text", "Listbox", "Menu", "Toplevel",
           "PhotoImage", "Label", "Button", "Entry"):
    setattr(tk, ad, SahteWidget)
tk.StringVar = tk.BooleanVar = tk.IntVar = tk.DoubleVar = SahteVar
tk.TclError = Exception
tk.END = "end"
ttk = types.ModuleType("tkinter.ttk")
for ad in ("Frame", "Label", "Button", "Entry", "Combobox", "Notebook",
           "Treeview", "Scrollbar", "Progressbar", "Checkbutton",
           "Radiobutton", "LabelFrame", "Style", "Separator", "PanedWindow"):
    setattr(ttk, ad, SahteWidget)
fd = types.ModuleType("tkinter.filedialog")
fd.askopenfilename = fd.askdirectory = fd.asksaveasfilename = SahteWidget()
mb = types.ModuleType("tkinter.messagebox")


def _kaydet(baslik, metin="", *a, **k):
    mesaj.append((baslik, metin))


mb.showinfo = mb.showwarning = mb.showerror = _kaydet
mb.askyesno = lambda *a, **k: True
tk.ttk, tk.filedialog, tk.messagebox = ttk, fd, mb
sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk,
                    "tkinter.filedialog": fd, "tkinter.messagebox": mb})

import ezdxf                                                  # noqa: E402
import pf3_gui as G                                           # noqa: E402

# Arayuz agir isleri is parcaciginda calistirir. Testte onlari SIRAYLA
# calistiriyoruz: baslatilan is kaydedilir, biz cagiririz. Boylece
# sonuc her kosuda ayni olur.
BEKLEYEN = []


class SahteIs:
    def __init__(self, target=None, args=(), daemon=None, **k):
        self.t, self.a = target, args
    def start(self):
        BEKLEYEN.append((self.t, self.a))


G.threading.Thread = SahteIs
import pf3_olcu as M                                          # noqa: E402
import pf4_pafta as P                                         # noqa: E402

hata = []


def dogru(ad, kosul, aciklama=""):
    if kosul:
        print(f"  tamam {ad}")
    else:
        hata.append(f"{ad}: {aciklama}")
        print(f"  HATA  {ad}: {aciklama}")


def esit(ad, olan, beklenen):
    dogru(ad, olan == beklenen, f"{olan!r} != {beklenen!r}")


class SahteAgac:
    """Sutunlari arayuzden ogrenen sahte Treeview."""
    def __init__(self, sut):
        self.sut = list(sut); self.satir = {}; self.n = 0
    def delete(self, *a): self.satir.clear()
    def get_children(self): return list(self.satir)
    def exists(self, s): return s in self.satir
    def insert(self, p, k, values=()):
        self.n += 1; s = f"I{self.n}"; self.satir[s] = list(values); return s
    def set(self, s, c, v=None):
        i = self.sut.index(c)
        if v is None:
            return self.satir[s][i]
        self.satir[s][i] = v
    def selection(self): return getattr(self, "_sec", list(self.satir))
    def selection_set(self, x): self._sec = list(x)
    def focus(self): return ""


def cizim(yol, gen, boy, ad="DENEME"):
    d = ezdxf.new(setup=True)
    d.header["$INSUNITS"] = 4
    m = d.modelspace()
    m.add_lwpolyline([(0, 0), (gen, 0), (gen, boy), (0, boy)], close=True,
                     dxfattribs={"layer": "GORUNEN"})
    m.add_circle((gen / 2, boy / 2), min(gen, boy) / 8,
                 dxfattribs={"layer": "GORUNEN"})
    m.add_linear_dim(base=(0, -boy / 4), p1=(0, 0), p2=(gen, 0)).render()
    m.add_text(ad, height=max(boy / 20, 2)).set_placement((0, boy * 1.1))
    d.saveas(yol)


kl = tempfile.mkdtemp(prefix="gui_pafta_")
try:
    # --- cikti klasoru: uc 1:1 resim
    cikti = os.path.join(kl, "cikti")
    os.makedirs(cikti)
    cizim(os.path.join(cikti, "P01_KUCUK.dxf"), 200.0, 120.0, "P01")
    cizim(os.path.join(cikti, "P02_ORTA.dxf"), 350.0, 200.0, "P02")
    cizim(os.path.join(cikti, "P03_UZUN.dxf"), 1800.0, 240.0, "P03")
    # DIK duran uzun parca: yatay kagitta bir kademe kucuk kalir,
    # program dikey kagidi secmeli.
    cizim(os.path.join(cikti, "P04_DIK.dxf"), 230.0, 1800.0, "P04")
    # Acinim resmi: detay resmiyle AYNI adi tasir, sonuna _acinim gelir.
    cizim(os.path.join(cikti, "P01_KUCUK_acinim.dxf"), 260.0, 150.0, "P01")

    u = G.Uygulama.__new__(G.Uygulama)
    u.M = M
    u.kuyruk = __import__("queue").Queue()
    u.calisiyor = False
    u.satirlar = [{"dxf": "P01_KUCUK.dxf", "kod": "01.001", "ad": "Kucuk sac"},
                  {"dxf": "P02_ORTA.dxf", "kod": "01.002", "ad": "Orta sac"}]
    u.komp = None
    u.v_out = SahteVar(cikti)
    u.v_kagit = SahteVar("A3")
    u.v_durum = SahteVar("")
    u.ilerleme = SahteWidget()
    u.gunluk = SahteWidget()
    u.b_pafta = SahteWidget(); u.b_bas = SahteWidget()
    u.b_incele = u.b_bom = u.b_ornek = u.b_onay = u.b_iptal = SahteWidget()
    # SahteWidget.__getattr__ eksik her alani DOLU gosterir; antetle
    # ilgili alanlari acikca bos birakmak gerekiyor, yoksa antetsiz
    # senaryo bile anteti acik saniyor.
    u.sablon = None
    u.v_antet = None
    u.acilim_sonuc = {}
    u.after = lambda *a, **k: None
    u._basla = lambda d: u.v_durum.set(d)
    u._bitir = lambda: None
    u._yaz = lambda m: None
    sut = ("dosya", "tip", "olcu", "kagit", "olcek", "durum")
    u.pf_agac = SahteAgac(sut)

    def kuyrugu_bosalt():
        """Arayuzun kuyrugunu ele alir: is parcaciklarinin urettigi
        mesajlari, gercek _kuyruk_isle gibi dagitir."""
        import queue as Q
        while True:
            try:
                tip, veri = u.kuyruk.get_nowait()
            except Q.Empty:
                return
            if tip == "plan":
                u._plan_geldi(*veri)
            elif tip == "pafta":
                u._pafta_geldi(veri)
            elif tip == "baski":
                u._baski_geldi(veri)
            elif tip == "hata":
                hata.append("is parcacigi HATA verdi:\n" + str(veri))
                print("  HATA  is parcacigi:", str(veri))

    print("\n-- Listeyi tazele")
    # pafta_doldur kendi is parcacigini baslatir; burada onu beklemek
    # yerine ayni isi sirayla yapiyoruz, sonra listeyi temizleyip
    # kuyrugu bosaltiyoruz - iki kere dolmasin.
    u.pafta_doldur()
    esit("bir is baslatildi", len(BEKLEYEN), 1)
    t, a = BEKLEYEN.pop(); t(*a)          # _plan_is
    kuyrugu_bosalt()
    esit("listelenen resim", len(u.pf_agac.satir), 5)
    for s, v in u.pf_agac.satir.items():
        print(f"     {v[0]:24s} {v[1]:7s} {v[2]:>14s}  {v[3]:9s} {v[4]:6s}  {v[5][:36]}")
    dogru("hepsi yerlesebiliyor",
          all(u.pf_satir.get(s) for s in u.pf_agac.satir),
          "bazi satirlar yerlesemedi")

    # Detay resmi de acinim da listede ve HEPSI SECILI gelmeli: ikisinin
    # de paftasi ve PDF'i cikacak.
    tipler = {v[0]: v[1] for v in u.pf_agac.satir.values()}
    esit("acinim tipi taniniyor", tipler.get("P01_KUCUK_acinim.dxf"), "açınım")
    esit("detay tipi taniniyor", tipler.get("P01_KUCUK.dxf"), "detay")
    esit("hepsi secili geldi",
         len(u.pf_agac.selection()), len(u.pf_agac.satir))

    # Yon parcaya gore secilmeli.
    yonler = {v[0]: v[3] for v in u.pf_agac.satir.values()}
    print("     yonler:", yonler)
    esit("dik duran parca dikey kagida", yonler.get("P04_DIK.dxf"), "A3 dikey")
    esit("yatik duran parca yatay kagida", yonler.get("P03_UZUN.dxf"), "A3 yatay")

    print("\n-- hicbir satir secilmemisken PAFTAYA AL")
    # Kullanici listeyi tazeleyip dogrudan butona basarsa hicbir sey
    # olmamamali degil - butun satirlar alinmali.
    u.pf_agac.selection_set([])
    mesaj.clear()
    u.pafta_uret()
    dogru("secim yokken de is baslatildi", len(BEKLEYEN) == 1,
          f"{len(BEKLEYEN)} is, mesaj={mesaj}")
    if BEKLEYEN:
        t, a = BEKLEYEN.pop()
        esit("butun satirlar alindi", len(a[0]), 5)
    kuyrugu_bosalt()

    print("\n-- PAFTAYA AL")
    u.pf_agac.selection_set(u.pf_agac.get_children())
    u.pafta_uret()
    esit("pafta isi baslatildi", len(BEKLEYEN), 1)
    t, a = BEKLEYEN.pop(); t(*a)          # _pafta_is
    kuyrugu_bosalt()
    # Pafta artik AYRI BIR KOPYAYA degil, resmin KENDI dosyasina yazilir.
    dogru("ayri pafta klasoru acilmadi",
          not os.path.isdir(os.path.join(cikti, "PAFTA")),
          "PAFTA klasoru olusturulmus")
    yazilan = sorted(v[0] for v in u.pf_agac.satir.values())
    esit("paftalanan resim", len(u.pafta_dosya), 5)
    for s, v in u.pf_agac.satir.items():
        print(f"     {v[0]:16s} -> {v[4][:60]}")
        dogru(f"{v[0]} hatasiz", not v[4].startswith("HATA"), v[4][:70])

    print("\n-- paftalarin icerigi (resmin kendi dosyasinda)")
    for s, (yol, kagit) in u.pafta_dosya.items():
        a = os.path.basename(yol)
        d = ezdxf.readfile(yol)
        pf = d.layout("PAFTA")
        vp = [e for e in pf if e.dxftype() == "VIEWPORT" and e.dxf.id != 1]
        dogru(f"{a}: pencere var", len(vp) >= 1, "pencere yok")
        esit(f"{a}: kagit", P.pafta_olcusu(yol), P.KAGIT[kagit])
        yz = " ".join(e.dxf.text for e in pf if e.dxftype() == "TEXT")
        # Resim no artik poz degil, parcanin CIZIM NO'sudur: BOM'da
        # varsa kodu, yoksa dosya adinin poz onekinden sonrasi.
        bek = {"P01_KUCUK.dxf": "01.001", "P01_KUCUK_acinim.dxf": "01.001",
               "P02_ORTA.dxf": "01.002"}.get(a, a.split("_", 1)[-1][:-4])
        dogru(f"{a}: resim no yazili", bek in yz, f"{bek!r} yok: {yz[:80]}")
        # Model uzayi 1:1 KALMALI: pafta onu ellememeli.
        esit(f"{a}: pafta sekmesi tek",
             sum(1 for t_ in d.layout_names() if t_ == "PAFTA"), 1)
        # Turkce harfler: yazilar SHX degil TrueType stile bagli olmali.
        st = d.styles.get(d.modelspace().query("TEXT").first.dxf.style) \
            if d.modelspace().query("TEXT").first is not None else None
        if st is not None:
            dogru(f"{a}: yazi fontu TrueType",
                  str(st.dxf.font).lower().endswith((".ttf", ".otf")),
                  f"font={st.dxf.font}")

    print("\n-- ayni dosyaya IKINCI kez pafta (olcu eklenmis gibi)")
    u.pf_agac.selection_set(u.pf_agac.get_children())
    u.pafta_uret()
    t, a = BEKLEYEN.pop(); t(*a)
    kuyrugu_bosalt()
    for s, (yol, kagit) in u.pafta_dosya.items():
        d = ezdxf.readfile(yol)
        esit(f"{os.path.basename(yol)}: yine tek pafta",
             sum(1 for t_ in d.layout_names() if t_ == "PAFTA"), 1)

    print("\n-- BAS (PDF)")
    u.pf_agac.selection_set(u.pf_agac.get_children())
    u.pafta_bas()
    esit("baski isi baslatildi", len(BEKLEYEN), 1)
    t, a = BEKLEYEN.pop(); t(*a)          # _bas_is
    kuyrugu_bosalt()
    pk = u._pdf_klasoru()
    pdf = sorted(a for a in os.listdir(pk)) if os.path.isdir(pk) else []
    esit("uretilen PDF", len(pdf), 5)
    dogru("PDF adlarinda kagit eki var",
          all(a.endswith("_A3.pdf") or a.endswith("_A3D.pdf") for a in pdf),
          str(pdf))
    dogru("acinimin da PDF'i cikti",
          "P01_KUCUK_acinim_A3.pdf" in pdf, str(pdf))
    dogru("dik parca dikey basildi", "P04_DIK_A3D.pdf" in pdf, str(pdf))
    dogru("PDF ayri klasorde", os.path.basename(pk) == "PDF", pk)

    print("\n-- baska kagit boylari")
    for kagit in ("A4", "A2", "A1", "A0"):
        u.v_kagit.set(kagit)
        u.pf_agac.delete()
        u._plan_is(sorted(os.path.join(cikti, f) for f in os.listdir(cikti)
                          if f.endswith(".dxf")), kagit)
        kuyrugu_bosalt()
        olan = sum(1 for s in u.pf_agac.satir if u.pf_satir.get(s))
        print(f"     {kagit}: {olan}/{len(u.pf_agac.satir)} resim yerlesiyor")
        dogru(f"{kagit} calisiyor", olan >= 1, "hicbiri yerlesmedi")
finally:
    shutil.rmtree(kl, ignore_errors=True)

print("\nSONUC:", "TUM DENETIMLER GECTI" if not hata
      else f"{len(hata)} HATA\n  " + "\n  ".join(hata))
sys.exit(1 if hata else 0)
