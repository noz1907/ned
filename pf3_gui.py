"""
Pi3D – STEP'ten BOM ve teknik resim (ARAYÜZ)
==================================================
Komut satırına gerek yok:

    python pf3_gui.py

Pencere adım adım ilerler, her adım bitmeden sonraki açılmaz:

    1. VERİ      incelenecek STEP dosyası + kaydedilecek klasör
    2. BOM       komponentler çıkarılır; malzeme data'da tanımlıysa oradan
                 alınır, değilse parça bazlı ya da hepsine birden seçilir
    3. AYAR      kaç görünüş (ÖN/ARKA/SAĞ/SOL/ÜST/ALT, en çok 4), kesit E/H
    4. ÖRNEK     bir parçanın resmi üretilir, ekranda gösterilir, onaylanır
    5. TÜMÜ      onay sonrası bütün DXF'ler üretilir ve ZIP'lenir

Hesap motoru pf3_olcu.py'dir; arayüz onunla aynı yolu kullanır, kendi
hesabını yapmaz. Motor ağır (OpenCascade) olduğu için pencere açıldıktan
sonra arka planda yüklenir; arayüz hiçbir işte kilitlenmez.
"""
from __future__ import annotations
import base64, math, os, queue, sys, threading, time, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --------------------------------------------------------------- logolar
# Logo dosyalari kaynaktan calisirken programin yanindaki logo/ klasorunde,
# exe'den calisirken PyInstaller'in actigi gecici klasorde durur.
LOGO_KLASOR = "logo"


def kaynak(*ad):
    """Program yanindaki bir dosyanin tam yolu (exe'den de calisir)."""
    kok = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.abspath(__file__))
    return os.path.join(kok, *ad)


try:                       # logolu surumde koda gomulu resimler
    import pi3d_logo as _GOMULU
except Exception:          # logosuz surum: dosya derlemeye katilmamistir
    _GOMULU = None


def logo_baytlari(ad):
    """Bir logonun ham bayti. Once GOMULU olana bakilir.

    Gomulu resim exe'nin icindedir; klasorden silinemez, degistirilemez.
    Gomulu yoksa logo/ klasorune bakilir - kaynak koddan calistiranlar
    icin. O da yoksa None: program logosuz calisir."""
    if _GOMULU is not None:
        v = getattr(_GOMULU, "LOGO", {}).get(ad)
        if v:
            try:
                return base64.b64decode(v)
            except Exception:
                pass
    try:
        y = kaynak(LOGO_KLASOR, ad)
        if os.path.isfile(y):
            return open(y, "rb").read()
    except Exception:
        pass
    return None


def logo_yukle(ad):
    """Logoyu tkinter goruntusune cevirir.

    Dosya yoksa ya da Tk PNG okuyamiyorsa None doner: logo olmadan da
    program calisir, sadece basliktaki resim gorunmez."""
    ham = logo_baytlari(ad)
    if ham is None:
        return None
    try:
        return tk.PhotoImage(data=base64.b64encode(ham).decode("ascii"))
    except Exception:
        return None


def logo_var():
    """Bu surumde logo var mi? Yoksa baslikta yalniz 'Pi3D' yazar."""
    return logo_baytlari("pi3d_64.png") is not None


BASLIK = "Pi3D  –  3B modelden BOM ve teknik resim"

EKSIK_PAKET = """'{paket}' paketi bu Python kurulumunda yok.

Kullanilan Python:
{py}

Pi3D'i KENDI ortaminda calistirmak gerekiyor; boylece bilgisayardaki
diger Python kurulumlarina (TensorFlow, pandas, scikit-learn vb.) dokunmaz.

En kolayi: program klasorundeki

    Pi3D_baslat.bat

dosyasina cift tiklayin. Ilk acilista .venv ortamini kurar (birkac dakika
surebilir), sonra programi acar.

Elle yapmak isterseniz, program klasorunde komut penceresi acip:

    py -3 -m venv .venv
    .venv\\Scripts\\activate
    pip install -r requirements.txt
    python pf3_gui.py
"""
ADIM = ["1  VERİ", "2  BOM ve MALZEME", "3  GÖRÜNÜŞ ve KESİT",
        "4  ÖRNEK ONAY", "5  TÜM ÇİZİMLER", "6  AÇINIM", "7  PAFTA"]


# =============================================================== yardımcılar
def klasor_ac(yol):
    """Çıktı klasörünü işletim sisteminin dosya yöneticisinde açar."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(yol)                                   # noqa: S606
        elif sys.platform == "darwin":
            os.system(f'open "{yol}"')
        else:
            os.system(f'xdg-open "{yol}" >/dev/null 2>&1 &')
    except Exception:
        pass


def dxf_onizleme(dxf_yol, png_yol, gen=11.0, boy=7.5):
    """DXF'i PNG'ye çevirir. Yazılar gerçek boyutta çizilir, böylece
    önizlemede görünen çakışma gerçek çakışmadır."""
    import ezdxf, matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Polygon

    segs = {"GORUNEN": [], "GIZLI": [], "OLCU": [], "EKSEN": [], "YAZI": [],
            "TARAMA": [], "DIGER": []}
    yazi, tarama = [], []

    def topla(e, ovr=None):
        k = ovr or (e.dxf.layer if e.dxf.layer in segs else "DIGER")
        t = e.dxftype()
        try:
            if t == "LWPOLYLINE":
                p = [(a, b) for a, b in e.get_points("xy")]
                segs[k].extend([a, b] for a, b in zip(p, p[1:]))
            elif t == "LINE":
                segs[k].append([(e.dxf.start.x, e.dxf.start.y),
                                (e.dxf.end.x, e.dxf.end.y)])
            elif t in ("CIRCLE", "ARC"):
                c, r = e.dxf.center, e.dxf.radius
                a0, a1 = (0, 360) if t == "CIRCLE" else (e.dxf.start_angle, e.dxf.end_angle)
                if a1 < a0:
                    a1 += 360
                p = [(c.x + r * math.cos(math.radians(q)),
                      c.y + r * math.sin(math.radians(q)))
                     for q in [a0 + (a1 - a0) * i / 32 for i in range(33)]]
                segs[k].extend([a, b] for a, b in zip(p, p[1:]))
            elif t == "SOLID":
                v = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx2]
                segs[k].append([(v[0].x, v[0].y), (v[1].x, v[1].y)])
                segs[k].append([(v[1].x, v[1].y), (v[2].x, v[2].y)])
            elif t == "HATCH":
                for yol in e.paths:
                    try:
                        q = [(v[0], v[1]) for v in yol.vertices]
                    except Exception:
                        q = []
                    if len(q) > 2:
                        tarama.append(q)
            elif t == "TEXT":
                yazi.append((e.dxf.text, e.dxf.insert.x, e.dxf.insert.y, e.dxf.height))
            elif t == "MTEXT":
                yazi.append((e.text, e.dxf.insert.x, e.dxf.insert.y, e.dxf.char_height))
        except Exception:
            pass

    d = ezdxf.readfile(dxf_yol)
    for e in d.modelspace():
        if e.dxftype() == "DIMENSION":
            try:
                for e2 in d.blocks.get(e.dxf.geometry):
                    topla(e2, "OLCU")
            except Exception:
                pass
        else:
            topla(e)
    xs = [p[0] for v in segs.values() for sg in v for p in sg] + [p[0] for q in tarama for p in q]
    ys = [p[1] for v in segs.values() for sg in v for p in sg] + [p[1] for q in tarama for p in q]
    for t, x, y, hh in yazi:
        xs += [x, x + len(str(t)) * 0.72 * hh]
        ys += [y, y + hh]
    if not xs:
        raise ValueError("çizimde gösterilecek bir şey yok")
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pay = 0.02 * max(x1 - x0, y1 - y0, 1.0)
    x0 -= pay; x1 += pay; y0 -= pay; y1 += pay
    sf, sc = (x1 - x0) / max(y1 - y0, 1e-9), gen / boy
    if sf > sc:
        ek = ((x1 - x0) / sc - (y1 - y0)) / 2; y0 -= ek; y1 += ek
    else:
        ek = ((y1 - y0) * sc - (x1 - x0)) / 2; x0 -= ek; x1 += ek

    fig, ax = plt.subplots(figsize=(gen, boy))
    for q in tarama:
        ax.add_patch(Polygon(q, closed=True, facecolor="none", edgecolor="#06c",
                             hatch="////", linewidth=0.4))
    renk = {"GORUNEN": ("#111", 1.0), "GIZLI": ("#b00", 0.5), "OLCU": ("#06c", 0.55),
            "EKSEN": ("#a0a", 0.4), "YAZI": ("#060", 0.5), "TARAMA": ("#06c", 0.4),
            "DIGER": ("#888", 0.4)}
    for k, v in segs.items():
        if v:
            ax.add_collection(LineCollection(v, colors=renk[k][0], linewidths=renk[k][1]))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal")
    ax.set_position([0, 0, 1, 1]); ax.axis("off")
    pb = gen * 72.0 / (x1 - x0)                 # veri birimi başına punto
    for t, x, y, hh in yazi:
        ax.text(x, y, str(t).replace("%%c", "Ø"), fontsize=hh * pb * 0.95,
                color="#036", family="monospace", va="bottom", ha="left")
    fig.savefig(png_yol, dpi=100, facecolor="white")
    plt.close(fig)
    return png_yol


# =============================================================== ana pencere
class Uygulama(ttk.Frame):
    def __init__(self, usta):
        super().__init__(usta, padding=6)
        self.pack(fill="both", expand=True)
        self.M = None                    # pf3_olcu (ağır, arka planda yüklenir)
        self.kayit = self.komp = None
        self.sablon = None                 # firma anteti; 7. adımda aranır
        self.satirlar = []               # hesaplanmış BOM satırları
        self.malzemeler = {}             # kod -> malzeme anahtarı (kullanıcı seçimi)
        self.ornek_dxf = None
        self.onizleme_png = None
        self.onizleme_resmi = None       # PhotoImage referansı (GC'ye yem olmasın)
        self.kuyruk = queue.Queue()
        self.calisiyor = False
        self.iptal_istendi = False
        self.gorunus_sirasi = []         # seçim sırası (en çok 4 tutmak için)
        self.ornek_adaylar = []
        self.agac = None                 # montaj ağacı (hiyerarşik BOM)
        self._kur()
        self.after(80, self._kuyruk_isle)
        threading.Thread(target=self._motoru_yukle, daemon=True).start()

    # ------------------------------------------------------------ iskelet
    def _kur(self):
        self.master.title(BASLIK)
        self.master.minsize(1100, 720)
        self._pencere_ikonu()
        try:
            ttk.Style().configure("Bas.TButton", font=("Segoe UI", 10, "bold"))
            ttk.Style().configure("Baslik.TLabel", font=("Segoe UI", 12, "bold"))
        except Exception:
            pass
        self._baslik_seridi()
        self.defter = ttk.Notebook(self)
        self.defter.pack(fill="both", expand=True)
        self.sayfa = []
        for ad in ADIM:
            f = ttk.Frame(self.defter, padding=10)
            self.defter.add(f, text=ad, state="disabled")
            self.sayfa.append(f)
        self._sayfa1(); self._sayfa2(); self._sayfa3()
        self._sayfa4(); self._sayfa5(); self._sayfa6(); self._sayfa7()
        self.ilerleme = ttk.Progressbar(self, mode="determinate")
        self.ilerleme.pack(fill="x", pady=(6, 2))
        gf = ttk.LabelFrame(self, text=" Günlük ", padding=4)
        gf.pack(fill="both")
        self.gunluk = tk.Text(gf, height=7, wrap="none", font=("Consolas", 9))
        gk = ttk.Scrollbar(gf, orient="vertical", command=self.gunluk.yview)
        self.gunluk.configure(yscrollcommand=gk.set, state="disabled")
        self.gunluk.pack(side="left", fill="both", expand=True)
        gk.pack(side="right", fill="y")
        self.v_durum = tk.StringVar(value="motor yükleniyor…")
        ttk.Label(self, textvariable=self.v_durum, relief="sunken",
                  anchor="w", padding=3).pack(fill="x", pady=(4, 0))
        self._adim_ac(0)

    def _pencere_ikonu(self):
        """Pencere ve gorev cubugu ikonu.

        Windows .ico ISTER ve DOSYA YOLU ister; gomulu ikonu once gecici
        bir dosyaya yazariz. Digerleri PNG ile yetinir. Ikisi de yoksa
        varsayilan ikonla devam edilir - logosuz surum boyle calisir."""
        ham = logo_baytlari("pi3d.ico")
        if ham:
            try:
                import tempfile
                d = os.path.join(tempfile.gettempdir(), "pi3d_ikon.ico")
                if not os.path.isfile(d) or os.path.getsize(d) != len(ham):
                    with open(d, "wb") as f:
                        f.write(ham)
                self.master.iconbitmap(default=d)
                return
            except Exception:
                pass
        g = logo_yukle("pi3d_64.png")
        if g is not None:
            self._ikon = g                     # referans tutulmazsa silinir
            try:
                self.master.iconphoto(True, g)
            except Exception:
                pass

    def _baslik_seridi(self):
        """Ustteki koyu serit.

        Logolu surumde: solda PiVision logosu, sagda Pi3D logosu ve adi.
        Logosuz surumde: yalnizca 'Pi3D' yazisi. Logo dosyalarinin
        varligina gore degil, SURUME gore davranir; yarim logolu bir
        ekran cikmaz."""
        ZEMIN, YAZI, SOLUK = "#0b2340", "#ffffff", "#8fb3d9"
        s = tk.Frame(self, bg=ZEMIN, height=84)
        s.pack(fill="x", side="top")
        s.pack_propagate(False)
        varmi = logo_var()
        if varmi:
            self._logo = (logo_yukle("pivision_64.png")
                          or logo_yukle("pivision_56.png"))
            if self._logo is not None:
                tk.Label(s, image=self._logo, bg=ZEMIN, bd=0
                         ).pack(side="left", padx=(14, 0), pady=4)
            self._ikon_kucuk = (logo_yukle("pi3d_72.png")
                                or logo_yukle("pi3d_64.png"))
            if self._ikon_kucuk is not None:
                tk.Label(s, image=self._ikon_kucuk, bg=ZEMIN, bd=0
                         ).pack(side="right", padx=(0, 14), pady=6)
        sag = tk.Frame(s, bg=ZEMIN)
        sag.pack(side="right", padx=(0, 10))
        tk.Label(sag, text="Pi3D", bg=ZEMIN, fg=YAZI, bd=0,
                 font=("Segoe UI", 17 if varmi else 26, "bold")).pack(anchor="e")
        tk.Label(sag, text="3B modelden parça listesi ve teknik resim",
                 bg=ZEMIN, fg=SOLUK, bd=0, font=("Segoe UI", 9)
                 ).pack(anchor="e")

    def _adim_ac(self, i, gecis=True):
        self.defter.tab(i, state="normal")
        if gecis:
            self.defter.select(i)

    # ------------------------------------------------------------ 1 VERİ
    def _sayfa1(self):
        f = self.sayfa[0]
        ttk.Label(f, text="İncelenecek data ve kaydedilecek klasör",
                  style="Baslik.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self.v_step = tk.StringVar(); self.v_out = tk.StringVar()
        ttk.Label(f, text="STEP dosyası:").grid(row=1, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_step, width=76).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(f, text="Gözat…", command=self.step_sec).grid(row=1, column=2)
        ttk.Label(f, text="Kaydedilecek klasör:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(f, textvariable=self.v_out, width=76).grid(row=2, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(f, text="Gözat…", command=self.out_sec).grid(row=2, column=2, pady=(6, 0))
        self.b_incele = ttk.Button(f, text="İNCELE  ▸", style="Bas.TButton",
                                   command=self.incele, state="disabled")
        self.b_incele.grid(row=3, column=1, sticky="e", pady=14, ipadx=14, ipady=5)
        ttk.Label(f, foreground="#555", justify="left", text=(
            "Okunan biçimler: STEP (.stp, .step), IGES (.igs), BREP.\n"
            "CATIA (.CATProduct/.CATPart), SolidWorks, NX, Inventor gibi kapali\n"
            "bicimler dogrudan acilamaz; CAD'den STEP olarak kaydedip verin.\n\n"
            "Dosya okunur, kopyalar birleştirilir, parça / standart eleman /\n"
            "kaynak dikişi ayrımı yapılır. Büyük montajlarda bir-iki dakika sürebilir.")
        ).grid(row=4, column=0, columnspan=3, sticky="w")
        f.columnconfigure(1, weight=1)

    # ------------------------------------------------------------ 2 BOM
    def _sayfa2(self):
        f = self.sayfa[1]
        ttk.Label(f, text="Komponentler, BOM ve malzeme",
                  style="Baslik.TLabel").pack(anchor="w", pady=(0, 6))
        sut = ("poz", "kod", "tanim", "adet", "sinif", "malzeme", "kaynak", "olcu", "kg")
        gen = (40, 165, 250, 45, 70, 145, 80, 120, 70)
        cer = ttk.Frame(f); cer.pack(fill="both", expand=True)
        self.ag = ttk.Treeview(cer, columns=sut, show="tree headings",
                               selectmode="extended")
        self.ag.column("#0", width=150, stretch=False)
        self.ag.heading("#0", text="KADEME")
        for c, w in zip(sut, gen):
            self.ag.heading(c, text=c.upper())
            self.ag.column(c, width=w,
                           anchor="w" if c in ("kod", "tanim", "malzeme") else "center")
        kay = ttk.Scrollbar(cer, orient="vertical", command=self.ag.yview)
        self.ag.configure(yscrollcommand=kay.set)
        self.ag.pack(side="left", fill="both", expand=True); kay.pack(side="right", fill="y")
        self.ag.tag_configure("std", foreground="#777")
        self.ag.tag_configure("kaynak", foreground="#b06")
        self.ag.tag_configure("data", foreground="#070")
        self.ag.tag_configure("montaj", foreground="#036", font=("Segoe UI", 9, "bold"))
        self.v_hiyerarsik = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="montaj ağacı olarak göster  "
                               "(ana ürün ▸ alt montaj ▸ parça)",
                        variable=self.v_hiyerarsik,
                        command=self._agac_doldur).pack(anchor="w", pady=(4, 0))

        mf = ttk.LabelFrame(f, text=" Malzeme – kütle = hacim × yoğunluk ", padding=6)
        mf.pack(fill="x", pady=(8, 0))
        self.v_mal = tk.StringVar()
        self.cb_mal = ttk.Combobox(mf, textvariable=self.v_mal, state="readonly", width=40)
        self.cb_mal.grid(row=0, column=0, rowspan=2, padx=(0, 8))
        ttk.Button(mf, text="Hepsine uygula",
                   command=lambda: self.malzeme_uygula(False)).grid(row=0, column=1, sticky="ew")
        ttk.Button(mf, text="Seçili satırlara",
                   command=lambda: self.malzeme_uygula(True)).grid(row=1, column=1, sticky="ew", pady=(3, 0))
        ttk.Button(mf, text="malzeme.csv yükle…",
                   command=self.malzeme_dosya).grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ttk.Button(mf, text="malzeme.csv yaz…",
                   command=self.malzeme_sablon).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=(3, 0))
        ttk.Label(mf, foreground="#555", justify="left", text=(
            "KAYNAK sütunu malzemenin nereden geldiğini söyler: data'dan (STEP'te ya da\n"
            "parça adında tanımlı), seçim (sizin verdiğiniz), varsayılan (hiçbiri yoksa).")
        ).grid(row=0, column=3, rowspan=2, sticky="w", padx=12)
        mf.columnconfigure(3, weight=1)

        af = ttk.Frame(f); af.pack(fill="x", pady=(8, 0))
        self.b_bom = ttk.Button(af, text="BOM ÇIKART  ▸", style="Bas.TButton",
                                command=self.bom_cikart)
        self.b_bom.pack(side="right", ipadx=14, ipady=5)
        self.v_bom_ozet = tk.StringVar(value="")
        ttk.Label(af, textvariable=self.v_bom_ozet).pack(side="left")

    # ------------------------------------------------------------ 3 AYAR
    def _sayfa3(self):
        f = self.sayfa[2]
        ttk.Label(f, text="Görünüşler, kesit ve çizim ayarları",
                  style="Baslik.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        gf = ttk.LabelFrame(f, text=" Görünüşler (en çok 4) ", padding=8)
        gf.grid(row=1, column=0, sticky="nsew")
        self.v_gor = {}
        for i, (k, ad) in enumerate((("ON", "ÖN (referans)"), ("ARKA", "ARKA"),
                                     ("SAG", "SAĞ"), ("SOL", "SOL"),
                                     ("UST", "ÜST"), ("ALT", "ALT"))):
            v = tk.BooleanVar(value=k in ("ON", "SAG", "SOL", "UST"))
            self.v_gor[k] = v
            if v.get():
                self.gorunus_sirasi.append(k)
            ttk.Checkbutton(gf, text=ad, variable=v,
                            command=lambda kk=k: self.gorunus_degisti(kk)
                            ).grid(row=i % 3, column=i // 3, sticky="w", padx=(0, 18))
        self.v_gor_bilgi = tk.StringVar()
        ttk.Label(gf, textvariable=self.v_gor_bilgi, foreground="#555"
                  ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        kf = ttk.LabelFrame(f, text=" Kesit ", padding=8)
        kf.grid(row=1, column=1, sticky="nsew", padx=8)
        self.v_kesit = tk.BooleanVar(value=False)
        ttk.Radiobutton(kf, text="Kesit olmasın  (H)", variable=self.v_kesit, value=False).pack(anchor="w")
        ttk.Radiobutton(kf, text="A-A kesit eklensin  (E)", variable=self.v_kesit, value=True).pack(anchor="w")
        ttk.Label(kf, foreground="#555", justify="left", wraplength=250, text=(
            "Kesme düzlemi en çok deliği açan yerden geçer, kesilen malzeme taranır, "
            "kesme çizgisi A—A olarak görünüşe işaretlenir.")).pack(anchor="w", pady=(6, 0))

        sf = ttk.LabelFrame(f, text=" Çizim ", padding=8)
        sf.grid(row=1, column=2, sticky="nsew")
        self.v_gizli = tk.BooleanVar(value=True)
        self.v_montaj = tk.BooleanVar(value=True)
        ttk.Checkbutton(sf, text="gizli çizgiler", variable=self.v_gizli).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(sf, text="montaj resmi de üretilsin", variable=self.v_montaj).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(sf, text="en az delik çapı (mm)").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.v_delik = tk.StringVar(value="1.0")
        ttk.Entry(sf, textvariable=self.v_delik, width=7).grid(row=2, column=1, sticky="w", pady=(4, 0))

        of = ttk.LabelFrame(f, text=" Örnek resim hangi parçadan üretilsin ", padding=8)
        of.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.v_ornek = tk.StringVar()
        self.cb_ornek = ttk.Combobox(of, textvariable=self.v_ornek, state="readonly", width=70)
        self.cb_ornek.pack(side="left")
        ttk.Label(of, foreground="#555", text="  (varsayılan: en çok çeşit delik/radüs taşıyan parça)"
                  ).pack(side="left")
        self.b_ornek = ttk.Button(f, text="ÖRNEK DXF ÜRET  ▸", style="Bas.TButton",
                                  command=self.ornek_uret)
        self.b_ornek.grid(row=3, column=2, sticky="e", pady=12, ipadx=14, ipady=5)
        f.columnconfigure(0, weight=1); f.columnconfigure(1, weight=1); f.columnconfigure(2, weight=1)
        self.gorunus_degisti(None)

    # ------------------------------------------------------------ 4 ÖRNEK
    def _sayfa4(self):
        f = self.sayfa[3]
        ust = ttk.Frame(f); ust.pack(fill="x")
        ttk.Label(ust, text="Örnek resmi inceleyin", style="Baslik.TLabel").pack(side="left")
        self.v_ornek_bilgi = tk.StringVar()
        ttk.Label(ust, textvariable=self.v_ornek_bilgi, foreground="#555").pack(side="left", padx=12)
        self.tuval = tk.Canvas(f, bg="white", highlightthickness=1, highlightbackground="#bbb")
        self.tuval.pack(fill="both", expand=True, pady=6)
        self.tuval.bind("<Configure>", lambda e: self._onizleme_ciz())
        af = ttk.Frame(f); af.pack(fill="x")
        ttk.Button(af, text="◂  AYARA DÖN", command=lambda: self.defter.select(2)).pack(side="left")
        ttk.Button(af, text="DXF'i harici programda aç",
                   command=self.ornek_ac).pack(side="left", padx=8)
        self.b_onay = ttk.Button(af, text="ONAYLA  –  TÜM ÇİZİMLERİ ÜRET  ▸",
                                 style="Bas.TButton", command=self.tumunu_uret)
        self.b_onay.pack(side="right", ipadx=14, ipady=5)

    # ------------------------------------------------------------ 5 TÜMÜ
    def _sayfa5(self):
        f = self.sayfa[4]
        ttk.Label(f, text="Tüm çizimler", style="Baslik.TLabel").pack(anchor="w", pady=(0, 8))
        self.v_sonuc = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.v_sonuc, justify="left").pack(anchor="w")
        self.liste = tk.Listbox(f, font=("Consolas", 9))
        self.liste.pack(fill="both", expand=True, pady=8)
        self.liste.bind("<Double-1>", self.liste_onizle)
        af = ttk.Frame(f); af.pack(fill="x")
        self.b_zip = ttk.Button(af, text="ZIP OLUŞTUR", command=self.zip_olustur, state="disabled")
        self.b_zip.pack(side="left")
        ttk.Button(af, text="Klasörü aç", command=self.klasoru_ac).pack(side="left", padx=8)
        self.b_iptal = ttk.Button(af, text="İptal", command=self.iptal, state="disabled")
        self.b_iptal.pack(side="right")

    # ------------------------------------------------------------ 6 AÇINIM
    def _sayfa6(self):
        f = self.sayfa[5]
        ttk.Label(f, text="Bükümlü sac parçaların açınımı",
                  style="Baslik.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(f, foreground="#555", justify="left", wraplength=1000, text=(
            "Program bükümlü sac parçaları KENDİSİ bulur; listede "
            "yalnız onlar kalır ve hepsi seçili gelir. İstemediğiniz "
            "varsa seçimden çıkarın (Ctrl ile tıklayın), sonra ÜRET "
            "deyin. Düz sac ve sac olmayan parçalar listeye hiç "
            "alınmaz. Üretilen resim KESİM "
            "KONTURUDUR: dış kontur, kenar kesikleri ve delikler gerçek "
            "yerlerindedir; üstüne büküm çizgileri ve büküm tablosu işlenir. "
            "Hesap güvenilir değilse açınım hiç verilmez, sebebi yazılır. "
            "YÖNTEM sütunu parçanın abkantta bükülüp bükülemeyeceğini söyler: "
            "kanat V kalıbın ağzını tutamayacak kadar kısaysa ya da iç "
            "yarıçap fazla küçükse abkantta yapılamaz, rollform gerekir.")
                  ).pack(anchor="w", pady=(0, 8))

        orta = ttk.Frame(f); orta.pack(fill="both", expand=True)
        sut = ("poz", "kod", "ad", "kalinlik", "acinim", "yontem", "durum")
        basl = {"poz": ("POZ", 50), "kod": ("KOD", 150), "ad": ("AD", 260),
                "kalinlik": ("SAC KALINLIK", 100), "acinim": ("AÇINIM  G x B", 150),
                "yontem": ("YÖNTEM", 110), "durum": ("DURUM", 360)}
        self.ac_agac = ttk.Treeview(orta, columns=sut, show="headings",
                                    selectmode="extended", height=14)
        for c in sut:
            self.ac_agac.heading(c, text=basl[c][0])
            self.ac_agac.column(c, width=basl[c][1],
                                anchor="w" if c in ("kod", "ad", "durum")
                                else "center")
        kd = ttk.Scrollbar(orta, orient="vertical", command=self.ac_agac.yview)
        self.ac_agac.configure(yscrollcommand=kd.set)
        self.ac_agac.pack(side="left", fill="both", expand=True)
        kd.pack(side="right", fill="y")
        self.ac_agac.bind("<Double-1>", self.acilim_onizle)

        self.v_ac_ozet = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.v_ac_ozet, foreground="#555",
                  justify="left").pack(anchor="w", pady=(6, 0))

        alt = ttk.Frame(f); alt.pack(fill="x", pady=(8, 0))
        ttk.Label(alt, text="K-faktörü:").pack(side="left")
        self.v_kfaktor = tk.StringVar(
            value=str(self.M.k_faktor_ayari() if self.M else 0.40))
        ttk.Entry(alt, textvariable=self.v_kfaktor, width=7).pack(side="left", padx=(4, 6))
        ttk.Label(alt, foreground="#555", text=(
            "büküm payı = açı × (iç yarıçap + K × kalınlık). Tezgâha ve "
            "malzemeye göre değişir; yumuşak çelikte 0,40 – 0,50.")
                  ).pack(side="left")
        ttk.Button(alt, text="Tümünü seç",
                   command=lambda: self.ac_agac.selection_set(
                       self.ac_agac.get_children())).pack(side="right", padx=4)
        self.b_acilim = ttk.Button(
            alt, text="İŞARETLİ PARÇALARIN AÇINIMINI ÜRET  ▸",
            style="Bas.TButton",
            command=self.acilim_uret, state="disabled")
        self.b_acilim.pack(side="right", padx=4, ipadx=10, ipady=3)

    def _acilim_doldur(self):
        """Parça listesini açınım sayfasına yazar ve TARAMAYI başlatır."""
        if not hasattr(self, "ac_agac"):
            return
        self.ac_agac.delete(*self.ac_agac.get_children())
        self.ac_satir = {}
        pozlar = self.M.poz_numaralari(self.komp)
        for i, k in enumerate(self.komp):
            if k.get("sinif") != "parca":
                continue        # standart eleman ve kaynak dikişi sac değil
            s = self.ac_agac.insert("", "end", values=(
                pozlar[i], k.get("kod", ""), (k.get("ad") or "")[:60],
                "", "", "", "taranıyor…"))
            self.ac_satir[s] = i
        self.b_acilim.configure(state="normal" if self.ac_satir else "disabled")
        if self.ac_satir:
            # Hangi parçanın bükümü var - açınım hesabı YAPMADAN. Tarama
            # parça başına ~20 ms sürer (açınım 15-30 s), yine de arka
            # planda çalışır: 300 komponentli bir montajda arayüz
            # donmasın.
            threading.Thread(target=self._tarama_is,
                             args=(dict(self.ac_satir),), daemon=True).start()

    def _tarama_is(self, satirlar):
        try:
            out = {}
            for n, (s, i) in enumerate(satirlar.items(), 1):
                if self.iptal_istendi:
                    break
                try:
                    sh = self.kayit[self.komp[i]["indeks"][0]][1]
                    out[s] = self.M.sac_taramasi(sh)
                except Exception as ex:
                    out[s] = {"sac": False, "tip": "sac degil",
                              "kalinlik_mm": None, "bukum_sayisi": 0,
                              "eksen_paralel": None,
                              "neden": f"taranamadı: {type(ex).__name__}"}
                if n % 25 == 0:
                    self.kuyruk.put(("ilerleme", (n, len(satirlar))))
            self.kuyruk.put(("tarama", out))
        except Exception:
            self.kuyruk.put(("hata", "Sac taraması sırasında hata:\n\n"
                             + traceback.format_exc()))

    def _tarama_geldi(self, out):
        """Tarama bitti: listede YALNIZ bükümlü sac parçalar kalır.

        Düz sac ve sac olmayan parçaların açınımı diye bir şey yok -
        düz sacın açınımı zaten kendisidir. Onları listede tutmak
        kullanıcıyı boş yere seçim yapmaya zorluyordu. Kalanlar seçili
        gelir; istenmeyen varsa seçimden çıkarılır."""
        self.tarama = out
        sec, duz, degil = [], 0, 0
        for s, r in out.items():
            if not self.ac_agac.exists(s):
                continue
            if r["tip"] == "bukumlu sac":
                sec.append(s)
                if r["kalinlik_mm"]:
                    self.ac_agac.set(s, "kalinlik", f"{r['kalinlik_mm']} mm")
                d = f"{r['bukum_sayisi']} büküm bulundu – açınımı çıkarılacak"
                if r.get("eksen_paralel") is False:
                    # Söz vermiyoruz: eksenler paralel değilse açınım
                    # çıkmayabilir. Yine de listede kalsın, denemesi
                    # saniyenin altında sürer ve sebebini o zaman yazar.
                    d += "  (büküm eksenleri paralel değil, çıkmayabilir)"
                self.ac_agac.set(s, "durum", d)
            else:
                if r["tip"] == "duz sac":
                    duz += 1
                else:
                    degil += 1
                self.ac_agac.delete(s)          # listeden çıkar
                self.ac_satir.pop(s, None)
        if sec:
            self.ac_agac.selection_set(sec)
            self.ac_agac.see(sec[0])
        self.b_acilim.configure(state="normal" if sec else "disabled")
        elendi = (f"  Listeye alınmayan {duz + degil} parça: "
                  f"{duz} düz sac (açınımı kendisidir), "
                  f"{degil} bükümlü sac değil.") if (duz or degil) else ""
        self.v_ac_ozet.set(
            (f"{len(sec)} bükümlü sac parça bulundu, hepsi seçili."
             if sec else "Bu montajda bükümlü sac parça bulunamadı.")
            + elendi)
        self.v_durum.set(
            f"açınım taraması: {len(sec)} bükümlü sac parça bulundu ve "
            f"seçildi ({len(out)} parça tarandı) – ÜRET deyin"
            if sec else
            f"açınım taraması: {len(out)} parçanın hiçbirinde büküm yok")

    def acilim_uret(self):
        sec = self.ac_agac.selection()
        if not sec:
            messagebox.showinfo(
                "Açınım", "Seçili parça yok.\n\n"
                "Program bükümlü sac parçaları tarayıp kendiliğinden "
                "seçer; hiçbiri seçilmediyse bu montajda bükümlü sac "
                "parça bulunamamış demektir. İsterseniz listeden elle "
                "seçip yine de deneyebilirsiniz.")
            return
        try:
            kf = float(self.v_kfaktor.get().replace(",", "."))
            if not 0.1 <= kf <= 0.6:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "K-faktörü",
                "K-faktörü 0,10 ile 0,60 arasında bir sayı olmalı.\n"
                "Ondalık ayracı virgül de olabilir: 0,32 / 0.32")
            return
        on = self.v_out.get().strip()
        if not on:
            messagebox.showwarning("Klasör", "Önce çıktı klasörünü seçin.")
            return
        os.makedirs(on, exist_ok=True)
        self.M.ayar_yaz(k_faktor=kf)       # bir daha girmeye gerek kalmasın
        kodlar = {self.komp[self.ac_satir[s]].get("kod")
                  or self.komp[self.ac_satir[s]].get("ad") for s in sec}
        for s in sec:
            self.ac_agac.set(s, "durum", "hesaplanıyor…")
        self._basla("açınım hesaplanıyor…")
        threading.Thread(target=self._acilim_is, args=(on, kodlar, kf,
                                                       self._P()),
                         daemon=True).start()

    def _acilim_is(self, on, kodlar, kf, P):
        try:
            sonuc, hata = self.M.acilim_yaz(
                self.kayit, self.komp, P, on, kodlar=kodlar, k_faktor=kf,
                log=self._yaz,
                ilerleme=lambda y, t, ad: self.kuyruk.put(("ilerleme", (y, t))),
                iptal=lambda: self.iptal_istendi)
            self.kuyruk.put(("acilim", (sonuc, hata, on)))
        except Exception:
            self.kuyruk.put(("hata", "Açınım sırasında hata:\\n\\n"
                             + traceback.format_exc()))

    def _acilim_geldi(self, sonuc, hata, on):
        self._bitir()
        olan = {r["kod"]: r for r in sonuc}
        neden = dict(hata)
        self.acilim_sonuc = getattr(self, "acilim_sonuc", {})
        for r in sonuc:                    # pafta, antet alanları için kullanır
            self.acilim_sonuc[r["dxf"]] = r
        for s, i in getattr(self, "ac_satir", {}).items():
            ad = self.komp[i].get("kod") or self.komp[i].get("ad")
            if ad in olan:
                r = olan[ad]
                self.ac_agac.set(s, "kalinlik", f"{r['kalinlik_mm']} mm")
                self.ac_agac.set(s, "acinim",
                                 f"{r['acinim_genislik_mm']} x {r['acinim_boy_mm']}")
                yn = r.get("yontem") or {}
                self.ac_agac.set(s, "yontem", yn.get("yontem", ""))
                d = f"{r['bukum_sayisi']} büküm  –  {r['dxf']}"
                if yn.get("yontem") == "rollform":
                    d = "ABKANTTA YAPILAMAZ  –  " + d
                self.ac_agac.set(s, "durum", d)
            elif ad in neden:
                self.ac_agac.set(s, "durum",
                                 "açınım yok: " + neden[ad].splitlines()[0])
        self.v_durum.set(f"açınım: {len(sonuc)} parça üretildi, "
                         f"{len(hata)} parça yapılamadı")
        if hata and not sonuc:
            messagebox.showinfo(
                "Açınım yapılamadı",
                "Seçilen parçaların hiçbirinin açınımı çıkarılamadı.\\n\\n"
                + "\\n\\n".join(f"{a}:\\n{m}" for a, m in hata[:3]))

    def acilim_onizle(self, _e=None):
        s = self.ac_agac.focus()
        if not s:
            return
        d = self.ac_agac.set(s, "durum")
        if d.endswith(".dxf"):
            yol = os.path.join(self.v_out.get().strip(), d.split("–")[-1].strip())
            if os.path.isfile(yol):
                klasor_ac(yol)

    # ----------------------------------------------------------- 7 PAFTA
    def _sayfa7(self):
        f = self.sayfa[6]
        ttk.Label(f, text="1:1 resimleri standart A3 paftaya yerleştir",
                  style="Baslik.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(f, foreground="#555", justify="left", wraplength=1050, text=(
            "Buraya kadar çıkan resimler 1:1'dir ve ÖYLE KALIR: bu adım "
            "onları silmez, ölçeklerini değiştirmez. Pafta KOPYAYA değil, "
            "resmin KENDİ DOSYASINA eklenir: çizim Model sekmesinde yine "
            "birebir durur, paftası yanında ayrı bir sekmedir. Böylece "
            "sonradan bir ölçü ekler ya da düzeltirseniz pafta da aynı "
            "dosyada güncel kalır; kopya ile asıl resim ayrışmaz.\n"
            "Kâğıdın YÖNÜNÜ program seçer: parça hangi yönde daha büyük "
            "görünüyorsa kâğıt o yöne çevrilir (dik duran 3 m'lik bir "
            "parça yatay A3'te 1:50'ye düşüp okunmaz oluyordu). "
            "Kâğıdın kenarından 15 mm pay bırakılır, "
            "sağ alt köşedeki 150 x 100 mm'lik kutu BOŞ kalır — oraya asla "
            "resim gelmez, kendi antetinizi oraya yapıştırırsınız. Baskı "
            "kendiliğinden yapılmaz: PDF'i siz istediğinizde, çıktı "
            "klasöründeki PDF klasörüne ..._A3.pdf adıyla üretilir.\n"
            "Listede HEM detay resimleri HEM açınımlar vardır ve hepsi "
            "seçili gelir; ikisinin de paftası ve PDF'i çıkar. Kâğıdın "
            "YÖNÜNÜ program seçer: parça hangi yönde daha büyük "
            "görünüyorsa kâğıt o yöne çevrilir.")
                  ).pack(anchor="w", pady=(0, 8))

        # --- firma anteti (varsa)
        self.sablon = self._sablon_bul()
        if self.sablon is not None:
            an = ttk.Frame(f); an.pack(fill="x", pady=(0, 6))
            self.v_antet = tk.BooleanVar(value=True)
            ttk.Checkbutton(an, text="Firma anteti kullanılsın",
                            variable=self.v_antet,
                            command=self.pafta_doldur).pack(side="left")
            ttk.Label(an, foreground="#555", text=(
                f"  ({self.sablon.bilgi.get('ad', 'antet')} – çerçeve, "
                "bölge işaretleri, antet ve logo firmanın çiziminden "
                "gelir; kâğıtla birlikte ölçeklenir)")).pack(side="left")
            gir = ttk.Frame(f); gir.pack(fill="x", pady=(0, 6))
            ttk.Label(gir, text="Tarih:").pack(side="left")
            self.v_tarih = tk.StringVar(
                value=(self.M.ayar_oku().get("tarih") if self.M else "")
                      or time.strftime("%d.%m.%Y"))
            ttk.Entry(gir, textvariable=self.v_tarih, width=12).pack(
                side="left", padx=(4, 12))
            ttk.Label(gir, text="Çizen:").pack(side="left")
            self.v_cizen = tk.StringVar(
                value=(self.M.ayar_oku().get("cizen") if self.M else "") or "")
            ttk.Entry(gir, textvariable=self.v_cizen, width=16).pack(
                side="left", padx=(4, 12))
            ttk.Label(gir, text="Onaylayan:").pack(side="left")
            self.v_onay = tk.StringVar(
                value=(self.M.ayar_oku().get("onaylayan") if self.M else "") or "")
            ttk.Entry(gir, textvariable=self.v_onay, width=16).pack(
                side="left", padx=4)
            ttk.Label(gir, foreground="#555", text=(
                "  antetteki Drawn / Checked satırlarına yazılır, "
                "saklanır")).pack(side="left")

        sec = ttk.Frame(f); sec.pack(fill="x")
        ttk.Label(sec, text="Kâğıt:").pack(side="left")
        self.v_kagit = tk.StringVar(value="A3")
        kb = ttk.Combobox(sec, textvariable=self.v_kagit, width=6,
                          state="readonly", values=("A3", "A4", "A2", "A1", "A0"))
        kb.pack(side="left", padx=4)
        kb.bind("<<ComboboxSelected>>", lambda _e: self.pafta_doldur())
        ttk.Label(sec, foreground="#555", text=(
            "boyu siz seçin, YÖNÜ (yatay/dikey) program seçer: hangisi "
            "daha büyük ölçek veriyorsa o. Sığmazsa o resim üretilmez, "
            "hangi kâğıt gerektiği satırda yazar.")).pack(side="left")
        ttk.Button(sec, text="Listeyi tazele",
                   command=self.pafta_doldur).pack(side="right", padx=4)

        orta = ttk.Frame(f); orta.pack(fill="both", expand=True, pady=(8, 0))
        sut = ("dosya", "tip", "olcu", "kagit", "olcek", "durum")
        basl = {"dosya": ("RESİM", 280), "tip": ("TİP", 70),
                "olcu": ("ÖLÇÜ  mm", 130),
                "kagit": ("KÂĞIT", 95), "olcek": ("ÖLÇEK", 80),
                "durum": ("DURUM", 400)}
        self.pf_agac = ttk.Treeview(orta, columns=sut, show="headings",
                                    selectmode="extended", height=13)
        for c in sut:
            self.pf_agac.heading(c, text=basl[c][0])
            self.pf_agac.column(c, width=basl[c][1],
                                anchor="w" if c in ("dosya", "durum") else "center")
        kd = ttk.Scrollbar(orta, orient="vertical", command=self.pf_agac.yview)
        self.pf_agac.configure(yscrollcommand=kd.set)
        self.pf_agac.pack(side="left", fill="both", expand=True)
        kd.pack(side="right", fill="y")

        alt = ttk.Frame(f); alt.pack(fill="x", pady=(8, 0))
        ttk.Button(alt, text="Tümünü seç",
                   command=lambda: self.pf_agac.selection_set(
                       self.pf_agac.get_children())).pack(side="left")
        ttk.Button(alt, text="PDF klasörünü aç",
                   command=self.pdf_klasor_ac).pack(side="left", padx=6)
        self.b_bas = ttk.Button(alt, text="SEÇİLİ PAFTALARI BAS (PDF)",
                                command=self.pafta_bas, state="disabled")
        self.b_bas.pack(side="right", padx=4, ipadx=6, ipady=3)
        self.b_pafta = ttk.Button(alt, text="SEÇİLİ RESİMLERİ PAFTAYA AL  ▸",
                                  style="Bas.TButton", command=self.pafta_uret,
                                  state="disabled")
        self.b_pafta.pack(side="right", padx=4, ipadx=10, ipady=3)

    @staticmethod
    def _resim_tipi(yol):
        """Listede görünen tip: açınım mı, detay resmi mi, montaj mı."""
        ad = os.path.basename(yol).lower()
        if ad.endswith("_acinim.dxf"):
            return "açınım"
        if "montaj" in ad:
            return "montaj"
        return "detay"

    def _sablon_bul(self):
        """Firma antetini arar: program klasörü, çıktı klasörü, ev.

        Antet ZORUNLU DEĞİLDİR. Bulunmazsa 7. adımda antet kutusu hiç
        görünmez ve Pi3D kendi sade paftasını çizer (sağ alt köşe boş).
        EXE_YAP.bat'ta 2 (logosuz) seçilerek derlenen sürümde antet
        klasörü exe'nin yanına konur."""
        try:
            import pf5_antet as PA
        except Exception:
            return None
        kok = os.path.dirname(os.path.abspath(
            getattr(sys, "_MEIPASS", None) or __file__))
        aday = [os.path.join(kok, "antet"),
                os.path.join(os.path.dirname(sys.executable), "antet")]
        try:                       # çıktı klasörü henüz seçilmemiş olabilir
            on = (self.v_out.get() or "").strip()
            if on:
                aday.append(os.path.join(on, "antet"))
        except Exception:
            pass
        try:
            return PA.sablon_bul(*aday)
        except Exception:
            return None

    def _antet_acik(self):
        # getattr: sayfa 7 henüz kurulmamışsa (denetim betikleri sayfayı
        # atlayabiliyor) antet yok sayılır, iş durmaz.
        return (getattr(self, "sablon", None) is not None
                and bool(getattr(self, "v_antet", None)
                         and self.v_antet.get()))

    def _pdf_klasoru(self):
        """Baskılar buraya gider. Paftanın kendisi resmin dosyasındadır,
        ayrı bir pafta klasörü YOKTUR."""
        return os.path.join(self.v_out.get().strip() or ".", "PDF")

    def pdf_klasor_ac(self):
        k = self._pdf_klasoru()
        if os.path.isdir(k):
            klasor_ac(k)
        else:
            messagebox.showinfo("PDF", "Henüz PDF basılmadı.")

    def pafta_doldur(self):
        """Çıktı klasöründeki 1:1 DXF'leri listeler, hangi ölçekte
        oturacaklarını hesaplar. Hiçbir dosya yazmaz."""
        if not hasattr(self, "pf_agac"):
            return
        on = self.v_out.get().strip()
        if not on or not os.path.isdir(on):
            messagebox.showinfo("Pafta", "Önce çıktı klasörünü seçin ve "
                                         "resimleri üretin.")
            return
        import glob
        dosyalar = sorted(glob.glob(os.path.join(on, "*.dxf")))
        self.pf_agac.delete(*self.pf_agac.get_children())
        self.pf_satir = {}
        if not dosyalar:
            self.b_pafta.configure(state="disabled")
            messagebox.showinfo("Pafta", "Çıktı klasöründe DXF yok. Önce "
                                         "5. adımda resimleri üretin.")
            return
        kagit = self.v_kagit.get()
        self._basla(f"{kagit} yerleşimi hesaplanıyor…")
        threading.Thread(target=self._plan_is,
                         args=(dosyalar, kagit,
                               self.sablon if self._antet_acik() else None),
                         daemon=True).start()

    def _plan_is(self, dosyalar, kagit, sablon=None):
        try:
            import pf4_pafta as PF
            self.kuyruk.put(("plan", (PF.kagit_plani(dosyalar, kagit,
                                                     sablon=sablon), kagit)))
        except Exception:
            self.kuyruk.put(("hata", "Yerleşim hesaplanırken hata:\n\n"
                             + traceback.format_exc()))

    def _plan_geldi(self, p, kagit):
        self._bitir()
        import pf4_pafta as PF
        for s in p["birebir"] + p["olcekli"]:
            d = "birebir çizilecek"
            if abs(s["olcek"] - 1.0) > 1e-9:
                d = f"{PF.olcek_metni(s['olcek'])} çizilecek"
                di = s.get("daha_iyi")
                if di:
                    d += (f"  ({PF.kagit_adi(di[0])} kâğıtta "
                          f"{PF.olcek_metni(di[1])} olurdu)")
            if 0 < s.get("yazi_mm", 0) < PF.EN_AZ_YAZI_MM:
                d += f"  –  DİKKAT: yazılar kâğıtta {s['yazi_mm']:.1f} mm kalıyor"
            i = self.pf_agac.insert("", "end", values=(
                os.path.basename(s["dosya"]), self._resim_tipi(s["dosya"]),
                f"{s['olcu'][0]:.0f} x {s['olcu'][1]:.0f}",
                PF.kagit_adi(s.get("kagit") or kagit),
                PF.olcek_metni(s["olcek"]), d))
            # Yönü de birlikte saklıyoruz: üretimde aynı yön kullanılsın,
            # yeniden hesaplanıp listedekinden farklı çıkmasın.
            self.pf_satir[i] = {"dosya": s["dosya"],
                                "kagit": s.get("kagit") or kagit}
        for s in p["sigmayan"]:
            sec = ", ".join(f"{PF.kagit_adi(k)} {PF.olcek_metni(o)}"
                            for k, o in s["secenek"][:4])
            i = self.pf_agac.insert("", "end", values=(
                os.path.basename(s["dosya"]), self._resim_tipi(s["dosya"]),
                f"{s['olcu'][0]:.0f} x {s['olcu'][1]:.0f}", kagit, "-",
                f"{kagit} kâğıda sığmıyor  –  " + (sec or "hiçbir kâğıda sığmıyor")))
            self.pf_satir[i] = None
        for y, e in p["hata"]:
            i = self.pf_agac.insert("", "end", values=(
                os.path.basename(y), self._resim_tipi(y), "-", "-", "-",
                "okunamadı: " + e))
            self.pf_satir[i] = None
        # Hepsi seçili gelsin: detay resmi de açınımı da paftalanacak.
        hepsi = [i for i in self.pf_agac.get_children() if self.pf_satir.get(i)]
        if hepsi:
            self.pf_agac.selection_set(hepsi)
        self.b_pafta.configure(state="normal")
        self.b_bas.configure(state="disabled")
        self.pafta_dosya = {}
        n = len(p["birebir"]) + len(p["olcekli"])
        ac = sum(1 for s in p["birebir"] + p["olcekli"]
                 if self._resim_tipi(s["dosya"]) == "açınım")
        self.v_durum.set(f"{kagit}: {n} resim yerleşiyor "
                         f"({ac} açınım, {n - ac} detay/montaj; "
                         f"{len(p['birebir'])} tanesi 1:1), "
                         f"{len(p['sigmayan'])} resim sığmıyor")

    def pafta_uret(self):
        # Hiçbir satır seçilmemişse HEPSİNİ al. Eskiden "seçim yok" deyip
        # duruyordu; kullanıcı listeyi tazeleyip butona basınca hiçbir
        # şey olmuyor gibi görünüyordu.
        sec = [s for s in self.pf_agac.selection()
               if getattr(self, "pf_satir", {}).get(s)]
        if not sec:
            sec = [s for s in self.pf_agac.get_children()
                   if getattr(self, "pf_satir", {}).get(s)]
            if sec:
                self.pf_agac.selection_set(sec)
        if not sec:
            messagebox.showinfo(
                "Pafta", "Paftaya alınacak resim yok.\n\n"
                "Listede satır varsa hiçbiri seçtiğiniz kâğıda sığmıyor "
                "demektir; DURUM sütununda hangi kâğıdın gerektiği yazar. "
                "Liste boşsa önce 'Listeyi tazele'ye basın.")
            return
        try:                              # ayar saklanamazsa iş durmasın
            if self.M:
                self.M.ayar_yaz(kagit=self.v_kagit.get())
        except Exception:
            pass
        sablon = self.sablon if self._antet_acik() else None
        ortak = {}
        if sablon is not None:
            ortak = {"cizen": self.v_cizen.get().strip(),
                     "onaylayan": self.v_onay.get().strip(),
                     "cizen_tarih": self.v_tarih.get().strip(),
                     "onay_tarih": self.v_tarih.get().strip()}
            try:                       # bir daha yazmaya gerek kalmasın
                self.M.ayar_yaz(tarih=ortak["cizen_tarih"],
                                cizen=ortak["cizen"],
                                onaylayan=ortak["onaylayan"])
            except Exception:
                pass
        isler = []
        for s in sec:
            it = dict(self.pf_satir[s]); it["_satir"] = s
            it.update(self._resim_kimligi(it["dosya"]))
            it["antet"] = dict(ortak, **it.pop("antet_ek", {}))
            isler.append(it)
            self.pf_agac.set(s, "durum", "paftaya alınıyor…")
        self._basla("pafta hazırlanıyor…")
        threading.Thread(target=self._pafta_is, args=(isler, sablon),
                         daemon=True).start()

    def _resim_kimligi(self, dosya):
        """Resmin sağ üst köşesine yazılacak no ve isim.

        No, dosya adının başındaki P07 / A12 gibi damgadır; isim BOM'dan
        gelir. BOM'da yoksa dosya adı kullanılır."""
        ad = os.path.basename(dosya)
        kok = os.path.splitext(ad)[0]
        # Detay resmi ile açınımı aynı adı taşır; BOM'da yalnız detayın
        # adı geçer, açınımı onun üstünden bulunur.
        temel = kok[:-7] + ".dxf" if kok.endswith("_acinim") else ad
        acinim = temel != ad
        for sat in self.satirlar or []:
            if sat.get("dxf") == temel:
                no = sat.get("kod") or kok.split("_", 1)[-1]
                return {"resim_no": no,
                        "resim_adi": (sat.get("ad") or "")
                                     + ("   AÇINIM" if acinim else ""),
                        "antet_ek": {
                            "malzeme": (sat.get("malzeme_ad") or "").split(" (")[0]
                                       if sat.get("malzeme_ad") else "",
                            "kutle": (f"{sat['kg_adet']:.3f} kg".replace(".", ",")
                                      if sat.get("kg_adet") else "")}}
        r = getattr(self, "acilim_sonuc", {}).get(ad)
        if r:
            return {"resim_no": r.get("kod") or kok,
                    "resim_adi": f"{r.get('ad', '')}   AÇINIM".strip(),
                    "antet_ek": {}}
        no = kok.split("_", 1)[-1] if kok[:1] == "P" else kok
        return {"resim_no": no, "resim_adi": "", "antet_ek": {}}

    def _pafta_is(self, isler, sablon=None):
        try:
            import pf4_pafta as PF
            sonuc = {}
            for n, it in enumerate(isler, 1):
                self.kuyruk.put(("ilerleme", (n, len(isler))))
                ad = os.path.splitext(os.path.basename(it["dosya"]))[0]
                try:
                    # cikti_dxf=None: pafta resmin KENDİ dosyasına yazılır.
                    r = PF.pafta_kur(
                        it["dosya"], None,
                        it["kagit"], resim_no=it.get("resim_no"),
                        resim_adi=it.get("resim_adi"),
                        sablon=sablon, antet=it.get("antet"))
                    # pafta_kur hangi YÖNÜ seçtiyse onu kullan: listede
                    # yazan yönle basılan PDF'in adı ayrışmasın.
                    r["kagit_adi"] = r.get("kagit") or it["kagit"]
                    sonuc[it["_satir"]] = ("ok", r)
                    self._yaz(f"  pafta  {it['kagit']} {r['olcek_metni']}  "
                              + os.path.basename(r["dosya"]))
                except Exception as ex:
                    sonuc[it["_satir"]] = ("hata", str(ex))
                    self._yaz(f"  pafta HATA  {ad}: {ex}")
                    if not isinstance(ex, PF.PaftaYok):
                        # Beklenmeyen hata: tam izini günlüğe yaz, yoksa
                        # "üretilmiyor" deyip nedenini bilemeyiz.
                        self._yaz(traceback.format_exc())
            self.kuyruk.put(("pafta", sonuc))
        except Exception:
            self.kuyruk.put(("hata", "Pafta hazırlanırken hata:\n\n"
                             + traceback.format_exc()))

    def _pafta_geldi(self, sonuc):
        self._bitir()
        self.pafta_dosya = getattr(self, "pafta_dosya", {})
        iyi = 0
        for s, (tip, v) in sonuc.items():
            if not self.pf_agac.exists(s):
                continue
            if tip == "ok":
                iyi += 1
                import pf4_pafta as PF
                self.pf_agac.set(s, "olcek", v["olcek_metni"])
                self.pf_agac.set(s, "kagit",
                                 PF.kagit_adi(v.get("kagit_adi") or "A3"))
                d = ("pafta resmin kendi dosyasına eklendi: "
                     + os.path.basename(v["dosya"]))
                if v.get("yazi_duzeltildi"):
                    d += f"  (+{v['yazi_duzeltildi']} yazı Türkçe stile alındı)"
                if v.get("yazi_kucuk"):
                    d += (f"  –  DİKKAT: yazılar kâğıtta "
                          f"{v['yazi_mm']:.1f} mm")
                self.pf_agac.set(s, "durum", d)
                self.pafta_dosya[s] = (v["dosya"],
                                       v.get("kagit_adi") or "A3")
            else:
                self.pf_agac.set(s, "durum", "HATA: " + v.splitlines()[0])
        self.b_bas.configure(state="normal" if self.pafta_dosya else "disabled")
        self.v_durum.set(f"pafta: {iyi} resim paftaya alındı"
                         + (f", {len(sonuc) - iyi} hata" if iyi < len(sonuc) else ""))
        # Sonucu HER ZAMAN söyle: sessizce bitmesin.
        yanlis = [v for t, v in sonuc.values() if t == "hata"]
        if iyi and not yanlis:
            messagebox.showinfo(
                "Pafta", f"{iyi} resmin kendi DXF dosyasına pafta eklendi.\n\n"
                "Model sekmesi hâlâ 1:1'dir. PDF istiyorsanız satırları "
                "seçip 'SEÇİLİ PAFTALARI BAS' deyin; PDF'ler "
                f"{self._pdf_klasoru()} klasörüne yazılır.")
        elif yanlis:
            messagebox.showwarning(
                "Pafta", f"{iyi} pafta yazıldı, {len(yanlis)} tanesi "
                f"yapılamadı.\n\nİlk sebep:\n{yanlis[0][:300]}\n\n"
                "Ayrıntı için alttaki Günlük penceresine bakın.")

    # ---- baskı (kendiliğinden çalışmaz, kullanıcı ister)
    def pafta_bas(self):
        sec = [s for s in self.pf_agac.selection()
               if getattr(self, "pafta_dosya", {}).get(s)]
        if not sec:
            messagebox.showinfo("Baskı", "Önce paftası hazırlanmış "
                                         "satırlardan seçin.")
            return
        self._basla("PDF üretiliyor…")
        threading.Thread(
            target=self._bas_is,
            args=([(s,) + tuple(self.pafta_dosya[s]) for s in sec],
                  self._pdf_klasoru()),
            daemon=True).start()

    def _bas_is(self, isler, klasor):
        try:
            import pf4_pafta as PF
            os.makedirs(klasor, exist_ok=True)
            sonuc = {}
            for n, (s, y, kagit) in enumerate(isler, 1):
                self.kuyruk.put(("ilerleme", (n, len(isler))))
                try:
                    # PDF asıl resmin yanına değil, PDF klasörüne ve
                    # kâğıt adı ekiyle: ..._A3.pdf
                    ad = os.path.splitext(os.path.basename(y))[0]
                    # Kâğıt eki dosya adına: A3 yatay -> _A3,
                    # A3 dikey -> _A3D. Hangi kâğıda basıldığı ada baksın.
                    ek = str(kagit).replace("-", "")
                    p = PF.bas(y, os.path.join(klasor, f"{ad}_{ek}.pdf"))
                    sonuc[s] = ("ok", p)
                    self._yaz("  PDF  " + os.path.basename(p))
                except Exception as ex:
                    sonuc[s] = ("hata", str(ex))
                    self._yaz(f"  PDF HATA  {os.path.basename(y)}: {ex}")
            self.kuyruk.put(("baski", sonuc))
        except Exception:
            self.kuyruk.put(("hata", "PDF üretilirken hata:\n\n"
                             + traceback.format_exc()))

    def _baski_geldi(self, sonuc):
        self._bitir()
        iyi = sum(1 for t, _ in sonuc.values() if t == "ok")
        for s, (tip, v) in sonuc.items():
            if self.pf_agac.exists(s):
                self.pf_agac.set(s, "durum",
                                 ("PDF hazır: " + os.path.basename(v))
                                 if tip == "ok" else "PDF HATASI: " + v[:60])
        self.v_durum.set(f"baskı: {iyi} PDF üretildi")
        if iyi:
            messagebox.showinfo(
                "Baskı", f"{iyi} PDF üretildi:\n{self._pdf_klasoru()}\n\n"
                "Kâğıt ölçüsü birebirdir; yazıcıda 'sayfaya sığdır' "
                "DEMEYİN, %100 basın.")

    # ------------------------------------------------------------ kuyruk
    def _yaz(self, metin):
        self.kuyruk.put(("log", metin))

    def _kuyruk_isle(self):
        try:
            while True:
                tip, veri = self.kuyruk.get_nowait()
                if tip == "log":
                    self.gunluk.configure(state="normal")
                    self.gunluk.insert("end", str(veri) + "\n")
                    self.gunluk.see("end")
                    self.gunluk.configure(state="disabled")
                elif tip == "durum":
                    self.v_durum.set(veri)
                elif tip == "ilerleme":
                    y, t = veri
                    self.ilerleme.configure(maximum=max(t, 1), value=y)
                elif tip == "motor":
                    self._motor_geldi(veri)
                elif tip == "komponent":
                    self._komponent_geldi(*veri)
                elif tip == "bom":
                    self._bom_geldi(veri)
                elif tip == "ornek":
                    self._ornek_geldi(veri)
                elif tip == "tumu":
                    self._tumu_geldi(veri)
                elif tip == "tarama":
                    self._tarama_geldi(veri)
                elif tip == "acilim":
                    self._acilim_geldi(*veri)
                elif tip == "plan":
                    self._plan_geldi(*veri)
                elif tip == "pafta":
                    self._pafta_geldi(veri)
                elif tip == "baski":
                    self._baski_geldi(veri)
                elif tip == "onizleme":
                    self.onizleme_png = veri
                    self._onizleme_ciz()
                elif tip == "hata":
                    self._bitir()
                    self.v_durum.set("hata")
                    messagebox.showerror("Hata", veri)
        except queue.Empty:
            pass
        except Exception:
            # Bir mesajı işlerken hata çıkarsa DÖNGÜ ÖLMEMELİ. Ölürse motor
            # işini bitirir ama sonucu kimse almaz: ekranda "STEP okunuyor"
            # yazılı kalır, program bitmiş gibi görünmez. Hatayı göster,
            # döngü aşağıdaki finally ile devam etsin.
            iz = traceback.format_exc()
            try:
                self._bitir()
                self.v_durum.set("iç hata – ayrıntı günlükte")
                self._yaz("İÇ HATA (arayüz):\n" + iz)
                messagebox.showerror(
                    "İç hata",
                    "Arayüzde beklenmeyen bir hata oldu. İşlem sürüyor "
                    "olabilir; günlükteki ayrıntıyı gönderin.\n\n" + iz)
            except Exception:
                pass
        finally:
            self.after(80, self._kuyruk_isle)

    def _basla(self, durum):
        self.calisiyor = True; self.iptal_istendi = False
        self.is_basi = time.time()
        self.is_adi = durum
        self._sayaci_isle()
        for b in (self.b_incele, self.b_bom, self.b_ornek, self.b_onay):
            b.configure(state="disabled")
        self.b_iptal.configure(state="normal")
        self.v_durum.set(durum)

    def _sayaci_isle(self):
        """Çalışan işin yanında geçen süreyi say. Program takıldı mı yoksa
        çalışıyor mu, kullanıcı buradan anlar."""
        if not self.calisiyor:
            return
        g = int(time.time() - getattr(self, "is_basi", time.time()))
        self.v_durum.set(f"{self.is_adi}   ({g // 60}:{g % 60:02d} geçti"
                         + ("  –  uzun sürüyor, İptal ile durdurabilirsiniz)"
                            if g > 90 else ")"))
        self.after(1000, self._sayaci_isle)

    def _bitir(self):
        if self.calisiyor:
            g = time.time() - getattr(self, "is_basi", time.time())
            self._yaz(f"  ({g:.1f} saniye sürdü)")
        self.calisiyor = False
        self.ilerleme.stop(); self.ilerleme.configure(mode="determinate")
        self.b_incele.configure(state="normal" if self.v_step.get() else "disabled")
        self.b_bom.configure(state="normal" if self.komp else "disabled")
        self.b_ornek.configure(state="normal" if self.satirlar else "disabled")
        self.b_onay.configure(state="normal" if self.ornek_dxf else "disabled")
        self.b_iptal.configure(state="disabled")

    def iptal(self):
        self.iptal_istendi = True
        self.v_durum.set("iptal isteniyor – çalışan adım bitince duracak…")

    # ------------------------------------------------------------ motor
    def _motoru_yukle(self):
        try:
            import pf3_olcu as M
            # Saklanmış ayarı da BURADA, arka planda oku. Ana iş parçacığında
            # dosya okumak, o dosya ağ sürücüsündeyse arayüzü dondurur.
            try:
                M.k_faktor_ayari()
            except Exception:
                pass
            self.kuyruk.put(("motor", M))
        except ModuleNotFoundError as ex:
            # En sık sebep: program, paketlerin kurulu olmadığı bir Python ile
            # açılmış. Kullanıcıya traceback yerine ne yapacağını söyle.
            self.kuyruk.put(("hata", EKSIK_PAKET.format(
                paket=getattr(ex, "name", "?"), py=sys.executable)))
        except Exception:
            self.kuyruk.put(("hata", "Hesap motoru yüklenemedi:\n\n"
                             + traceback.format_exc(limit=3)))

    def _pafta_ayari_tazele(self):
        """Son kullanılan kâğıdı geri getirir."""
        if not self.M or not hasattr(self, "v_kagit"):
            return
        try:
            k = self.M.ayar_oku().get("kagit")
        except Exception:
            return
        if k in ("A4", "A3", "A2", "A1", "A0"):
            self.v_kagit.set(k)

    def _kfaktoru_tazele(self):
        """Motor yüklendikten sonra kutuya saklanmış K-faktörünü koyar."""
        try:
            self.v_kfaktor.set(str(self.M.k_faktor_ayari()))
        except Exception:
            pass

    def _motor_geldi(self, M):
        self.M = M
        adlar = [f"{k} – {t} ({r} g/cm³)" for k, (t, r) in M.MALZEME.items()]
        self.cb_mal.configure(values=adlar)
        self.v_mal.set(next(a for a in adlar if a.startswith(M.VARSAYILAN_MALZEME + " ")))
        self._kfaktoru_tazele()
        self._pafta_ayari_tazele()
        self.v_durum.set("hazır – STEP dosyasını seçin")
        self._yaz(f"motor hazır, {len(M.MALZEME)} malzeme tanımlı")
        if self.v_step.get():
            self.b_incele.configure(state="normal")

    def _secili_malzeme(self):
        return (self.v_mal.get().split(" – ")[0] or self.M.VARSAYILAN_MALZEME).strip()

    def _P(self):
        try:
            d = float(str(self.v_delik.get()).replace(",", "."))
        except ValueError:
            d = 1.0
        return {"gizli": bool(self.v_gizli.get()), "en_az_delik": d,
                "yogunluk": self.M.RHO,
                "gorunusler": self.M.gorunus_sec(
                    [k for k, v in self.v_gor.items() if v.get()]),
                "kesit": bool(self.v_kesit.get())}

    def _is_girdisi(self):
        """Tk değişkenlerini ANA İŞ PARÇACIĞINDA okuyup düz veriye çevirir.

        Tk çok iş parçacıklı değildir: arka plandaki iş, StringVar/BooleanVar
        okumaya kalkarsa "main thread is not in main loop" hatası alır.
        Bu yüzden arka plana yalnız buradan çıkan düz sözlük gider."""
        P = self._P()
        return {"step": self.v_step.get().strip(), "on": self.v_out.get().strip(),
                # genel = yalnız hiç seçim yapılmamış parçalar için varsayılan.
                # Kutudaki malzeme "uygulanacak" malzemedir, herkesin varsayılanı
                # değildir: bir parçaya alüminyum verince diğerleri çelik kalır.
                "P": P, "esl": dict(self.malzemeler),
                "genel": self.M.VARSAYILAN_MALZEME,
                "kesit": bool(self.v_kesit.get()),
                "gorunus_ad": ", ".join(self.M.GORUNUS_AD[x] for x in P["gorunusler"])}

    def _calistir(self, g, asama, komp=None, **ek):
        """Motoru arka planda, yalnız düz veriyle çağırır."""
        return self.M.calistir(
            g["step"], g["on"], self.kayit, komp or self.komp, g["P"],
            asama=asama, esl=g["esl"], agac=self.agac, genel=g["genel"],
            log=self._yaz,
            ilerleme=lambda y, t: self.kuyruk.put(("ilerleme", (y, t))),
            iptal=lambda: self.iptal_istendi, **ek)

    # ------------------------------------------------------------ 1 VERİ
    def step_sec(self):
        y = filedialog.askopenfilename(
            title="İncelenecek 3B model dosyası",
            filetypes=[("3B model", "*.stp *.step *.igs *.iges *.brep "
                                     "*.STP *.STEP *.IGS *.IGES"),
                       ("STEP", "*.stp *.step *.STP *.STEP"),
                       ("IGES", "*.igs *.iges *.IGS *.IGES"),
                       ("BREP", "*.brep *.brp"),
                       ("Tümü", "*.*")])
        if y:
            self.v_step.set(y)
            if not self.v_out.get():
                self.v_out.set(os.path.splitext(y)[0] + "_cikti")
            if self.M:
                self.b_incele.configure(state="normal")

    def out_sec(self):
        y = filedialog.askdirectory(title="Kaydedilecek klasör")
        if y:
            self.v_out.set(y)

    def klasoru_ac(self):
        y = self.v_out.get()
        if y and os.path.isdir(y):
            klasor_ac(y)
        else:
            messagebox.showinfo("Klasör", "Çıktı klasörü henüz yok.")

    def incele(self):
        yol = self.v_step.get().strip()
        if not os.path.isfile(yol):
            messagebox.showwarning("Dosya", "Geçerli bir dosya seçin."); return
        try:
            self.v_durum.set(f"biçim: {self.M.E.bicim_tani(yol)}")
        except self.M.E.OkunamazBicim as ex:
            messagebox.showwarning("Bu biçim okunamıyor", str(ex))
            self.v_durum.set("okunamayan biçim"); return
        if not self.v_out.get():
            self.v_out.set(os.path.splitext(yol)[0] + "_cikti")
        self._basla("STEP okunuyor…")
        self.ilerleme.configure(mode="indeterminate"); self.ilerleme.start(12)
        threading.Thread(target=self._incele_is, args=(yol, self._P()),
                         daemon=True).start()

    def _incele_is(self, yol, P):
        try:
            kayit, komp, agac = self.M.step_komponentleri(yol, P, log=self._yaz)
            self.kuyruk.put(("komponent", (kayit, komp, agac)))
        except Exception:
            self.kuyruk.put(("hata", "STEP okunamadı:\n\n" + traceback.format_exc(limit=3)))

    def _komponent_geldi(self, kayit, komp, agac=None):
        self.kayit, self.komp, self.satirlar = kayit, komp, []
        self.agac = agac
        self.ornek_dxf = None
        self.malzemeler = {}
        self._bitir()
        self._agac_doldur()
        n = sum(1 for k in komp if k["sinif"] == "parca")
        d = sum(1 for k in komp if k["sinif"] == "parca"
                and self.M.malzeme_tahmin(k.get("malzeme_data"), k["ad"]))
        self.v_bom_ozet.set(f"{len(komp)} komponent, {n} parça – "
                            f"{d} parçanın malzemesi data'dan okundu, "
                            f"{n - d} parçaya malzeme vermeniz gerekiyor")
        self._acilim_doldur()
        self._adim_ac(1)
        self._adim_ac(5, gecis=False)     # açınım BOM'u beklemez
        self._adim_ac(6, gecis=False)     # pafta da
        self.v_durum.set("komponentler hazır – malzemeyi verip BOM ÇIKART deyin")

    # ------------------------------------------------------------ 2 BOM
    def _malzeme_onizle(self, k):
        """Üretimden önce, bir parçaya hangi malzemenin gideceğini gösterir."""
        m, kaynak = self.M.malzeme_ata(k, self.malzemeler, self.M.VARSAYILAN_MALZEME)
        return m, {"data": "data'dan", "secim": "seçim", "genel": "varsayılan"}[kaynak]

    def _agac_doldur(self):
        self.ag.delete(*self.ag.get_children())
        if self.agac and self.v_hiyerarsik.get():
            self._hiyerarsik_doldur()
            return
        if self.satirlar:
            for r in self.satirlar:
                t = ("std",) if r["sinif"] == "standart" else \
                    ("kaynak",) if r["sinif"] == "kaynak" else \
                    ("data",) if r.get("malzeme_kaynak") == "data'dan" else ()
                kg = f"{r['kg_adet']:.3f}" if r.get("kg_adet") else "-"
                self.ag.insert("", "end", tags=t,
                               values=(r["poz"], r["kod"][:40], r["ad"][:60], r["adet"],
                                       r["sinif"], (r.get("malzeme_ad") or "-")[:28],
                                       r.get("malzeme_kaynak") or "-",
                                       r.get("olcu") or "-", kg))
            return
        for i, k in enumerate(self.komp or [], 1):
            if k["sinif"] == "parca":
                m, kay = self._malzeme_onizle(k)
                mal, t = self.M.MALZEME[m][0][:28], ("data",) if kay == "data'dan" else ()
            else:
                mal, kay = "-", "-"
                t = ("std",) if k["sinif"] == "standart" else ("kaynak",)
            self.ag.insert("", "end", tags=t,
                           values=(i, k["kod"][:40], k["ad"][:60], k["adet"],
                                   k["sinif"], mal, kay, "-", "-"))

    def _hiyerarsik_doldur(self):
        """Montaj ağacını kademeli göster: ana ürün > alt montaj > parça."""
        satir = self.M.agac_bom(self.agac, self.komp, self.satirlar or [])
        # BOM henüz çıkarılmadıysa malzeme sütunu boş kalmasın: hangi
        # malzemenin gideceğini şimdiden göster (düz listede de böyle).
        kod_komp = {k["kod"]: k for k in self.komp or []}
        for r in satir:
            if not r["malzeme_ad"] and r["tur"] == "parca":
                k = kod_komp.get(r["kod"])
                if k:
                    m, kay = self._malzeme_onizle(k)
                    r["malzeme_ad"] = self.M.MALZEME[m][0]
                    r["kaynak"] = kay
        for r in satir:
            ust = r["poz"].rsplit(".", 1)[0] if "." in r["poz"] else ""
            t = ("montaj",) if r["tur"] == "montaj" else \
                ("std",) if r["tur"] == "standart" else \
                ("kaynak",) if r["tur"] == "kaynak" else ()
            ad = r["ad"][:60]
            if r["tur"] == "montaj":
                ad = "▸ " + ad
            adet = f"{r['adet']}" + (f"  (top {r['toplam_adet']})"
                                     if r["toplam_adet"] != r["adet"] else "")
            try:
                self.ag.insert(ust, "end", iid=r["poz"], open=r["seviye"] < 3,
                               tags=t,
                               values=(r["poz"], r["kod"][:40], ad, adet,
                                       r["tur"], (r["malzeme_ad"] or "-")[:28],
                                       r.get("kaynak") or r.get("malzeme_kaynak") or "-",
                                       r["olcu"] or "-", r["kg_adet"] or "-"))
            except Exception:
                pass

    def malzeme_uygula(self, yalniz_secili):
        if not self.komp:
            return
        m = self._secili_malzeme()
        kodlar = None
        if yalniz_secili:
            kodlar = {self.ag.item(i, "values")[1] for i in self.ag.selection()}
            if not kodlar:
                messagebox.showinfo("Malzeme", "Önce listeden satır seçin."); return
        n = 0
        for k in self.komp:
            if k["sinif"] != "parca":
                continue
            if kodlar is not None and k["kod"][:40] not in kodlar:
                continue
            self.malzemeler[k["kod"]] = m
            n += 1
        self.satirlar = []
        self._agac_doldur()
        self._yaz(f"malzeme '{m}' {n} parçaya uygulandı")

    def malzeme_dosya(self):
        if not (self.M and self.komp):
            return
        y = filedialog.askopenfilename(
            title="Malzeme listesi  (kendi şablonumuz ya da CAD'in parça listesi)",
            filetypes=[("Malzeme listesi", "*.csv *.txt *.tsv *.json"),
                       ("Tümü", "*.*")])
        if not y:
            return
        try:
            esl, bilinmeyen = self.M.malzeme_dosya_oku(y)
        except Exception as ex:
            messagebox.showerror("Malzeme dosyası", str(ex)); return
        n = 0
        for k in self.komp:
            if k["sinif"] != "parca":
                continue
            m, kay = self.M.malzeme_ata(k, esl, "", data_oncelik=False)
            if kay == "secim" and m:
                self.malzemeler[k["kod"]] = m
                n += 1
        self.satirlar = []
        self._agac_doldur()
        self._yaz(f"{os.path.basename(y)}: {len(esl)} kayıt okundu, {n} parça eşleşti")
        if bilinmeyen:
            self._yaz("! tanınmayan malzeme adı: " + ", ".join(bilinmeyen[:8]))
            messagebox.showwarning(
                "Tanınmayan malzeme",
                "Dosyadaki şu malzeme adları tanınmadı, bu parçalar varsayılan "
                "malzemede kalır:\n\n" + "\n".join(bilinmeyen[:15])
                + "\n\nTanınan adlar için malzeme kutusundaki listeye bakın.")

    def malzeme_sablon(self):
        if not (self.M and self.komp):
            messagebox.showinfo("Şablon", "Önce STEP inceleyin."); return
        y = filedialog.asksaveasfilename(title="malzeme şablonu", defaultextension=".csv",
                                         initialfile="malzeme.csv", filetypes=[("CSV", "*.csv")])
        if y:
            self.M.malzeme_sablonu(self.komp, y)
            self._yaz(f"şablon yazıldı: {y}")

    def bom_cikart(self):
        self._basla("BOM çıkarılıyor…")
        threading.Thread(target=self._bom_is, args=(self._is_girdisi(),), daemon=True).start()

    def _bom_is(self, g):
        try:
            sonuc = self._calistir(g, asama=(1,))
            self.kuyruk.put(("bom", sonuc))
        except Exception:
            self.kuyruk.put(("hata", "BOM çıkarılamadı:\n\n" + traceback.format_exc(limit=4)))

    def _bom_geldi(self, sonuc):
        self.satirlar = sonuc["satirlar"]
        self._bitir()
        self._agac_doldur()
        kg = sum((r.get("toplam_kg") or 0.0) for r in sonuc["bom"])
        self.v_bom_ozet.set(f"{len(sonuc['bom'])} poz, toplam {kg:.3f} kg – BOM.csv yazıldı")
        # örnek parça adayları: en çok çeşit delik + radüs taşıyan önce
        p = [r for r in self.satirlar if r["sinif"] == "parca"]
        p.sort(key=lambda r: -(len(r.get("delikler") or []) + len(r.get("radusler") or [])))
        self.ornek_adaylar = p
        self.cb_ornek.configure(values=[f"{r['poz']}  {r['kod']}  {r['ad'][:40]}" for r in p])
        if p:
            self.v_ornek.set(f"{p[0]['poz']}  {p[0]['kod']}  {p[0]['ad'][:40]}")
        self._adim_ac(2)
        self.v_durum.set("BOM hazır – görünüş ve kesit ayarını yapın")

    # ------------------------------------------------------------ 3 AYAR
    def gorunus_degisti(self, k):
        if k:
            if self.v_gor[k].get():
                self.gorunus_sirasi.append(k)
                en_cok = self.M.EN_COK_GORUNUS if self.M else 4
                while len(self.gorunus_sirasi) > en_cok:
                    esk = self.gorunus_sirasi.pop(0)
                    self.v_gor[esk].set(False)
                    self._yaz(f"en çok 4 görünüş: {esk} kapatıldı")
            elif k in self.gorunus_sirasi:
                self.gorunus_sirasi.remove(k)
        n = sum(1 for v in self.v_gor.values() if v.get())
        self.v_gor_bilgi.set(f"{n} görünüş seçili (en çok 4). Yerleşim 1. açı "
                             f"(Avrupa): SAĞ sola, SOL sağa, ÜST alta, ALT üste.")

    def ornek_uret(self):
        if not self.satirlar:
            return
        i = max(self.cb_ornek.current(), 0)
        r = self.ornek_adaylar[i] if self.ornek_adaylar else None
        if not r:
            messagebox.showinfo("Örnek", "Çizilecek parça yok."); return
        self._basla(f"örnek resim üretiliyor: {r['kod']}")
        threading.Thread(target=self._ornek_is, args=(r, self._is_girdisi()),
                         daemon=True).start()

    def _ornek_is(self, r, g):
        try:
            komp = [k for k in self.komp if k["kod"] == r["kod"] and k["sinif"] == "parca"]
            sonuc = self._calistir(g, asama=(2,), komp=komp, tablo_yok=True,
                                   poz_harita={x["kod"]: x["poz"] for x in self.satirlar})
            ciz = [x for x in sonuc["satirlar"] if x.get("dxf", "").endswith(".dxf")]
            if not ciz:
                raise RuntimeError("örnek resim üretilemedi")
            self.kuyruk.put(("ornek", (os.path.join(g["on"], ciz[0]["dxf"]), ciz[0],
                                       g["gorunus_ad"], g["kesit"])))
        except Exception:
            self.kuyruk.put(("hata", "Örnek resim üretilemedi:\n\n"
                             + traceback.format_exc(limit=4)))

    def _ornek_geldi(self, veri):
        yol, r, gor_ad, kesit = veri
        self.ornek_dxf = yol
        self._bitir()
        self.v_ornek_bilgi.set(f"{r['kod']} – {gor_ad}"
                               + (" + A-A KESİT" if kesit else "")
                               + f" – {os.path.basename(yol)}")
        self._adim_ac(3)
        self.v_durum.set("örnek hazır – inceleyip onaylayın")
        threading.Thread(target=self._onizle_is, args=(yol,), daemon=True).start()

    def ornek_ac(self):
        if self.ornek_dxf:
            klasor_ac(self.ornek_dxf)

    # ------------------------------------------------------------ 4/5 tümü
    def tumunu_uret(self):
        asama = [2] + ([3] if self.v_montaj.get() else [])
        self._basla("tüm çizimler üretiliyor…")
        self._adim_ac(4)
        self.liste.delete(0, "end")
        threading.Thread(target=self._tumu_is,
                         args=(tuple(asama), self._is_girdisi()), daemon=True).start()

    def _tumu_is(self, asama, g):
        try:
            self.kuyruk.put(("tumu", self._calistir(g, asama=(1,) + asama)))
        except Exception:
            self.kuyruk.put(("hata", "Üretim sırasında hata:\n\n"
                             + traceback.format_exc(limit=4)))

    def _tumu_geldi(self, sonuc):
        self.satirlar = sonuc["satirlar"]
        self._bitir()
        self._agac_doldur()
        on = sonuc["klasor"]
        d = sorted(x for x in os.listdir(on) if x.lower().endswith(".dxf"))
        self.liste.delete(0, "end")
        for x in d:
            self.liste.insert("end", x)
        for x in ("BOM.csv", "BOM.md", "olculer.csv", "rapor.md"):
            if os.path.isfile(os.path.join(on, x)):
                self.liste.insert("end", x)
        kg = sum((r.get("toplam_kg") or 0.0) for r in sonuc["bom"])
        self.v_sonuc.set(f"{len(d)} DXF, {len(sonuc['bom'])} poz, toplam {kg:.3f} kg\n{on}")
        self.b_zip.configure(state="normal")
        self.v_durum.set("bitti – ZIP oluşturabilirsiniz")

    def zip_olustur(self):
        try:
            y, n = self.M.zip_yap(self.v_out.get())
            self._yaz(f"{os.path.basename(y)} ({n} dosya)")
            self.v_durum.set(f"ZIP hazır: {y}")
            messagebox.showinfo("ZIP", f"{n} dosya paketlendi:\n{y}")
        except Exception as ex:
            messagebox.showerror("ZIP", str(ex))

    def liste_onizle(self, _olay=None):
        s = self.liste.curselection()
        if not s:
            return
        ad = self.liste.get(s[0])
        if not ad.lower().endswith(".dxf"):
            return
        self.defter.select(3)
        self.v_ornek_bilgi.set(ad)
        threading.Thread(target=self._onizle_is,
                         args=(os.path.join(self.v_out.get(), ad),), daemon=True).start()

    # ------------------------------------------------------------ önizleme
    def _onizle_is(self, yol):
        try:
            import tempfile
            png = os.path.join(tempfile.gettempdir(),
                               "pf3_onizleme_" + os.path.basename(yol) + ".png")
            dxf_onizleme(yol, png)
            self.kuyruk.put(("onizleme", png))
        except Exception as ex:
            self.kuyruk.put(("durum", f"önizleme yapılamadı: {ex}"))

    def _onizleme_ciz(self):
        if not self.onizleme_png or not os.path.isfile(self.onizleme_png):
            return
        try:
            ham = tk.PhotoImage(file=self.onizleme_png)
            gw = max(self.tuval.winfo_width(), 1)
            gh = max(self.tuval.winfo_height(), 1)
            k = max(1, min(-(-ham.width() // gw), -(-ham.height() // gh)))
            self.onizleme_resmi = ham.subsample(k, k) if k > 1 else ham
            self.tuval.delete("all")
            self.tuval.create_image(gw // 2, gh // 2, image=self.onizleme_resmi)
        except Exception as ex:
            self.v_durum.set(f"önizleme çizilemedi: {ex}")


def main():
    kok = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    Uygulama(kok)
    kok.mainloop()


if __name__ == "__main__":
    main()
