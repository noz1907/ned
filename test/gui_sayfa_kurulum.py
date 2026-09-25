# -*- coding: utf-8 -*-
"""tkinter olmayan makinede arayuzu SAHTE tk ile kurup, sayfa kurulum
kodunda ad/yazim hatasi kalmadigini dogrular."""
import os, re, sys, types
from unittest.mock import MagicMock

class SahteVar:
    def __init__(self, value=None, **k): self._v = value
    def get(self): return self._v
    def set(self, v): self._v = v
    def trace_add(self, *a, **k): pass

tk = types.ModuleType("tkinter")
class SahteWidget:
    """Her cagriyi yutan, her niteligi yine kendisi olan sahte pencere ogesi."""
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return SahteWidget()
    def __getattr__(self, ad):
        # DUNDER'LARI KARSILAMA. Karsilanirsa "for x in <eksik alan>"
        # sonsuz donguye giriyor: __iter__ bir SahteWidget veriyor,
        # __next__ de her seferinde yenisini.
        if ad.startswith("__") and ad.endswith("__"):
            raise AttributeError(ad)
        return SahteWidget()
    def __setitem__(self, k, v): pass
    def __getitem__(self, k):
        # Sayi anahtarinda IndexError SART: __iter__ yokken Python eski
        # usul yinelemeye duser ve __getitem__(0), (1), (2)... diye
        # sonsuza kadar sorar. Her seferinde SahteWidget donunce
        # "*widget.get_children()" acilimi hic bitmiyordu.
        if isinstance(k, int):
            raise IndexError(k)
        return SahteWidget()

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
fd = types.ModuleType("tkinter.filedialog"); fd.askopenfilename = fd.askdirectory = fd.asksaveasfilename = SahteWidget()
mb = types.ModuleType("tkinter.messagebox")
mb.showinfo = mb.showwarning = mb.showerror = mb.askyesno = SahteWidget()
tk.ttk, tk.filedialog, tk.messagebox = ttk, fd, mb
sys.modules.update({"tkinter": tk, "tkinter.ttk": ttk,
                    "tkinter.filedialog": fd, "tkinter.messagebox": mb})

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_gui as G

u = G.Uygulama.__new__(G.Uygulama)          # __init__'i atla, alanlari elle kur
u.master = SahteWidget(); u.M = None
u.sayfa = [SahteWidget() for _ in G.ADIM]
u.gorunus_sirasi = []; u.malzemeler = {}; u.komp = []; u.kayit = []
u.ac_satir = {}
import queue as _q
u.kuyruk = _q.Queue()
for ad in ("pack", "grid", "configure"):
    pass
hata = []
sayfalar = sorted((a for a in dir(G.Uygulama)
                   if re.fullmatch(r"_sayfa\d+", a)),
                  key=lambda a: int(a[6:]))
assert sayfalar, "hic sayfa kurulum islevi bulunamadi"
# Her sayfa islevi programda GERCEKTEN cagriliyor mu? Bu test islevleri
# kendisi cagirdigi icin, programin cagirmayi unuttugu sayfa burada
# kurulur ve gozden kacardi: 8. adim (LAZER) tanimliydi ama hic
# cagrilmiyordu, sekme bos aciliyordu.
_kaynak = open(G.__file__, encoding="utf-8").read()
_cagri = set(re.findall(r"self\.(_sayfa\d+)\(\)", _kaynak))
eksik = [fn for fn in sayfalar if fn not in _cagri]
print("programda cagrilan sayfalar:", sorted(_cagri, key=lambda a: int(a[6:])))
if eksik:
    print("  HATA: tanimli ama hic cagrilmiyor:", eksik)
    hata.append(("cagri", f"cagrilmayan sayfa: {eksik}"))
if len(sayfalar) != len(G.ADIM):
    print(f"  HATA: {len(G.ADIM)} sekme var, {len(sayfalar)} sayfa islevi var")
    hata.append(("sayfa sayisi", f"{len(G.ADIM)} sekme, {len(sayfalar)} islev"))
for i, fn in enumerate(sayfalar, 1):
    try:
        getattr(u, fn)()
        print(f"  {fn}  kuruldu")
    except Exception as e:
        hata.append((fn, e))
        print(f"  {fn}  HATA: {type(e).__name__}: {e}")
# 7. sayfa: firma anteti varsa tarih / cizen / onaylayan kutulari
# ACILMALI. Bunlar acilmayinca kullanici "sormuyor" diyordu; sebebi
# sablonun bulunamamasiydi ve sessizce oluyordu.
_antet = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "antet")
if os.path.isdir(_antet):
    print("\nantet sablonu:", "bulundu" if u.sablon else "BULUNAMADI")
    if u.sablon is None:
        hata.append(("antet", "sablon bulunamadi: "
                     + str(getattr(u, "antet_neden", ""))))
    else:
        for alan in ("v_tarih", "v_cizen", "v_onay"):
            if not hasattr(u, alan):
                hata.append(("antet girisi", f"{alan} kutusu acilmamis"))
            else:
                print(f"    {alan} = {getattr(u, alan).get()!r}")
        if not hasattr(u, "v_antet"):
            hata.append(("antet secimi", "v_antet kutucugu yok"))

# Acinim sayfasinin kendi mantigi: poz_numaralari ve doldurma
import pf3_olcu as M
u.M = M
u.komp = [{"kod": "01.050.000.01", "ad": "U-Blech", "sinif": "parca", "adet": 2},
          {"kod": "M8", "ad": "M8 Somun", "sinif": "standart", "adet": 4},
          {"kod": "", "ad": "Kehlnaht", "sinif": "kaynak", "adet": 1},
          {"kod": "01.051.000.01", "ad": "C-Profil", "sinif": "parca", "adet": 1},
          {"kod": "09.020.000.03", "ad": "Plaka", "sinif": "parca", "adet": 1}]
print("\npoz numaralari:", M.poz_numaralari(u.komp))
class SahteAgac:
    """Sutun listesi arayuzden okunur: sutun eklenince test kirilmasin."""
    def __init__(self, sut=None):
        self.satir = {}; self.n = 0
        self.sut = list(sut or ("poz", "kod", "ad", "kalinlik",
                                "acinim", "yontem", "durum"))
    def delete(self, *a):
        if a:                       # tek satir silme (tarama elemesi)
            for s in a: self.satir.pop(s, None)
        else:
            self.satir.clear()
    def get_children(self): return list(self.satir)
    def insert(self, p, k, values=()):
        self.n += 1; s = f"I{self.n}"; self.satir[s] = list(values); return s
    def set(self, s, c, v=None):
        i = self.sut.index(c)
        if v is None: return self.satir[s][i]
        self.satir[s][i] = v
    def selection(self): return list(self.secili or self.satir)
    def selection_set(self, s): self.secili = list(s) if isinstance(s, (list, tuple)) else [s]
    def see(self, s): pass
    def exists(self, s): return s in self.satir
    def focus(self): return ""
SahteAgac.secili = None
u.ac_agac = SahteAgac(); u.b_acilim = SahteWidget()
# 8. adim (LAZER) listesi de gercek bir sahte agac olsun ki
# lazer_doldur'un mantigi denetlensin.
u.lz_agac = SahteAgac(("poz", "kod", "ad", "tip", "kalinlik", "olcu", "durum"))
u.b_lazer = SahteWidget(); u.v_lz_ozet = SahteVar("")
u.acilim_liste = []
u.tarama = {}
u.tarama_kod = {}

# Sac taramasi arka planda calisir; testte SIRAYLA calissin diye
# is parcacigi yakalanir.
BEKLEYEN = []
class SahteIplik:
    def __init__(self, target=None, args=(), **k): BEKLEYEN.append((target, args))
    def start(self): pass
_eski_thread = G.threading.Thread
G.threading.Thread = SahteIplik

# Taramaya gercek kati verilsin: biri bukumlu sac, oburu kalin blok.
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from sac_tarama_denetimi import bukumlu_sac
# 0 = kalin blok (sac degil), 3 = bukumlu sac, 4 = duz plaka
u.komp[0]["indeks"] = [0]; u.komp[3]["indeks"] = [1]; u.komp[4]["indeks"] = [2]
u.kayit = [(None, BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 60.0, 50.0, 40.0).Shape()),
           (None, bukumlu_sac()),
           (None, BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 200.0, 100.0, 5.0).Shape())]
u.iptal_istendi = False
u.kuyruk = _q.Queue()
u.v_durum = SahteVar("")
u._acilim_doldur()
print("acinim listesi:")
for s, v in u.ac_agac.satir.items(): print("   ", v)

print("\ntarama (program kendisi buluyor):")
assert BEKLEYEN, "tarama isi baslatilmadi"
u.v_ac_ozet = SahteVar("")
t, a = BEKLEYEN.pop(); t(*a)                    # _tarama_is
tip, veri = u.kuyruk.get_nowait()
assert tip == "tarama", tip
u._tarama_geldi(veri)
for s, v in u.ac_agac.satir.items(): print("   ", v)
print("    ozet:", u.v_ac_ozet.get())
kalan = [v[1] for v in u.ac_agac.satir.values()]
secili = [u.ac_agac.satir[s][1] for s in (u.ac_agac.secili or [])
          if s in u.ac_agac.satir]
print("    listede kalan:", kalan, " secili:", secili)
# Listede YALNIZ bukumlu sac kalmali; kalin blok elenmeli.
if kalan != ["01.051.000.01"]:
    hata.append(("sac taramasi", f"listede {kalan}, beklenen ['01.051.000.01']"))
if secili != ["01.051.000.01"]:
    hata.append(("sac secimi", f"secilen {secili}, beklenen ['01.051.000.01']"))
G.threading.Thread = _eski_thread
u._bitir = lambda: None
u.v_out = SahteVar("/tmp")
u._acilim_geldi([{"kod": "01.051.000.01", "kalinlik_mm": 2.5,
                  "acinim_genislik_mm": 233.9, "acinim_boy_mm": 2480.0,
                  "bukum_sayisi": 4, "dxf": "A1_x_acinim.dxf"}],
                [("01.050.000.01", "Bükümlerin eksenleri paralel değil.\nikinci satır")],
                "/tmp")
print("sonuc yazildiktan sonra:")
for s, v in u.ac_agac.satir.items(): print("   ", v)
# --- 8. adim: acinimi cikan parca SECILI, oburu listede ama secisiz
print("\nlazer listesi (acinim sonrasi):")
u.acilim_liste = [{"kod": "01.051.000.01", "kontur_dis": [[(0, 0)]],
                   "kontur_delik": [], "kalinlik_mm": 2.5}]
u.lazer_doldur()
for v in u.lz_agac.satir.values():
    print("   ", v)
print("    ozet:", u.v_lz_ozet.get())
kalan = [v[1] for v in u.lz_agac.satir.values()]
secili = [u.lz_agac.satir[s][1] for s in (u.lz_agac.secili or [])
          if s in u.lz_agac.satir]
# Acinimi cikan USTTE ve SECILI; duz plaka listede ama SECISIZ;
# kalin blok (sac degil) listeye HIC girmemeli.
if secili != ["01.051.000.01"]:
    hata.append(("lazer secimi", f"secilen {secili}, beklenen ['01.051.000.01']"))
if "09.020.000.03" not in kalan:
    hata.append(("lazer listesi", f"duz plaka listede yok: {kalan}"))
if "01.050.000.01" in kalan:
    hata.append(("lazer elemesi", f"sac olmayan parca listede: {kalan}"))
if kalan and kalan[0] != "01.051.000.01":
    hata.append(("lazer sirasi", f"acinimi cikan ustte degil: {kalan}"))

print("\nSONUC:", "HATA VAR" if hata else "tum sayfalar kuruldu")
sys.exit(1 if hata else 0)
