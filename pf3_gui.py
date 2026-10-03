"""
Pi3D – STEP'ten BOM ve teknik resim (ARAYÜZ)
==================================================
Komut satırına gerek yok:

    python pf3_gui.py

Pencere adım adım ilerler, her adım bitmeden sonraki açılmaz:

    1. VERİ      incelenecek STEP dosyası + kaydedilecek klasör
    2. BOM       komponentler çıkarılır; malzeme data'da tanımlıysa oradan
                 alınır, değilse parça bazlı ya da hepsine birden seçilir
    3. AYAR      görünüşler otomatik (özelliklere göre, 6'ya kadar), kesit E/H, araç yönü, parça istisnası
    4. ÖRNEK     bir parçanın resmi üretilir, ekranda gösterilir, onaylanır
    5. TÜMÜ      onay sonrası bütün DXF'ler üretilir ve ZIP'lenir

Hesap motoru pf3_olcu.py'dir; arayüz onunla aynı yolu kullanır, kendi
hesabını yapmaz. Motor ağır (OpenCascade) olduğu için pencere açıldıktan
sonra arka planda yüklenir; arayüz hiçbir işte kilitlenmez.
"""
from __future__ import annotations
import base64, json, math, os, queue, sys, threading, time, traceback
import tkinter as tk
import pf7_is as IS
import pf9_excel as XL
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


try:                       # lisans (makine bazlı, imzalı .lic)
    import pf17_lisans as L
except Exception:          # pragma: no cover - lisans modülü eksikse program kilitli
    L = None

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


BASLIK = f"Pi3D v{IS.PI3D_SURUM}  –  3B modelden BOM ve teknik resim"

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
        "4  ÖRNEK ONAY", "5  TÜM ÇİZİMLER", "6  AÇINIM", "7  PAFTA",
        "8  LAZER"]


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


def dxf_onizleme(dxf_yol, png_yol, gen=11.0, boy=7.5, dpi=200):
    """DXF'i PNG'ye çevirir. Yazılar gerçek boyutta çizilir, böylece
    önizlemede görünen çakışma gerçek çakışmadır. dpi 200: büyütme
    penceresinde 2 kat yakınlaşınca da keskin kalsın."""
    import ezdxf, matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Polygon

    segs = {"GORUNEN": [], "GIZLI": [], "OLCU": [], "EKSEN": [], "YAZI": [],
            "TARAMA": [], "DIGER": []}
    yazi, tarama, dolgu = [], [], []

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
                # dolu üçgen: ölçü OKU (dolu ok ucu)
                v = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx2]
                dolgu.append(([(q.x, q.y) for q in v], k))
            elif t == "INSERT":
                # blok içindekiler (ölçünün ok blokları) yerine oturtulmuş hâlde
                for v in e.virtual_entities():
                    topla(v, ovr)
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
            # ölçü bloğu: çizgiler, yazı ve OK UÇLARI (ok bir blok INSERT'idir;
            # önceden çizilmiyordu - önizlemede ölçüler oksuz görünüyordu)
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
    for q, k in dolgu:
        ax.add_patch(Polygon(q, closed=True, facecolor=renk.get(k, renk["DIGER"])[0],
                             edgecolor="none"))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal")
    ax.set_position([0, 0, 1, 1]); ax.axis("off")
    pb = gen * 72.0 / (x1 - x0)                 # veri birimi başına punto
    for t, x, y, hh in yazi:
        ax.text(x, y, str(t).replace("%%c", "Ø"), fontsize=hh * pb * 0.95,
                color="#036", family="monospace", va="bottom", ha="left")
    fig.savefig(png_yol, dpi=dpi, facecolor="white")
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
        self.acilim_liste = []             # 8. adım açınım konturunu kullanır
        self.tarama = {}                   # sac taraması: satır -> sonuç
        self.tarama_kod = {}               # aynısı: parça kodu -> sonuç
        self.satirlar = []               # hesaplanmış BOM satırları
        self.malzemeler = {}             # kod -> malzeme anahtarı (kullanıcı seçimi)
        self.parca_ayar = {}             # kod -> {"ana_gorunus_ad": "ÜST"} (istisna)
        self.arac_oneri = None           # arac_yonu_oner sonucu (model okununca)
        self.ornek_dxf = None
        self.onizleme_png = None
        self.onizleme_resmi = None       # PhotoImage referansı (GC'ye yem olmasın)
        self.kuyruk = queue.Queue()
        self._yapildi = {}               # düğme anahtarı -> işin yapıldığı girdi imzası
        self.calisiyor = False
        self.iptal_istendi = False
        self.ornek_adaylar = []
        self.agac = None                 # montaj ağacı (hiyerarşik BOM)
        # LİSANS: makineye kilitli pi3d.lic; yoksa / geçersizse program açılır
        # ama model işlenmez, lisans penceresi makine kimliğini gösterir.
        self.lisans = self._lisans_yukle()
        self._kur()
        self.after(80, self._kuyruk_isle)
        threading.Thread(target=self._motoru_yukle, daemon=True).start()
        if not (self.lisans or {}).get("gecerli"):
            self.after(700, self.lisans_penceresi)

    # ------------------------------------------------------------ lisans
    def _lisans_yukle(self):
        if L is None:
            return {"gecerli": False, "sebep": "Lisans modülü (pf17_lisans) yüklenemedi.",
                    "makine": "?", "moduller": set()}
        try:
            return L.yukle()
        except Exception as ex:
            return {"gecerli": False, "sebep": f"Lisans okunamadı: {ex}",
                    "makine": "?", "moduller": set()}

    def _lisans_izin(self, modul=None):
        """İşlem başlamadan lisans kapısı: lisans yoksa ya da modül kapsam
        dışıysa açıklar, lisans penceresini açar ve False döner."""
        d = getattr(self, "lisans", None)
        if not isinstance(d, dict):
            d = {}
        if not d.get("gecerli"):
            messagebox.showwarning(
                "Lisans", "Bu bilgisayarda geçerli bir Pi3D lisansı yok.\n\n"
                + str(d.get("sebep", "")) + "\n\nYardım > Lisans ekranındaki makine "
                "kimliğini PiVision'a gönderin; gelen pi3d.lic dosyasını aynı "
                "ekrandan yükleyin.")
            self.lisans_penceresi()
            return False
        if modul and not L.modul_acik(d, modul):
            messagebox.showwarning(
                "Lisans kapsamı",
                f"'{L.MODULLER.get(modul, modul)}' bu lisansın kapsamında değil "
                f"({d.get('paket', '')}).\nTam lisans için PiVision'a başvurun.")
            return False
        return True

    def firma_anteti_penceresi(self):
        """Yardım > Firma anteti: A3 antet DXF'i seçilir, program çerçeveyi,
        antet bloğunu, kutuları ve etiketleri ÖLÇEREK bulur, alan eşlemesini
        önerir; kullanıcı tabloda onaylar / düzeltir; şablon kalıcı klasöre
        yazılır ve ayara kaydedilir (sonradan değiştirilir / kaldırılır).
        Yalnız tam lisansta: deneme sürümünde her çıktı Pi3D antetlidir."""
        try:
            import pf5_antet as PA
        except Exception as ex:
            messagebox.showerror("Firma anteti", f"pf5_antet yüklenemedi: {ex}")
            return
        PA.lisans_durumu(yenile=True)
        if not PA.firma_anteti_izinli():
            messagebox.showinfo(
                "Firma anteti",
                "Deneme sürümünde (ya da lisanssız) her pafta Pi3D / PiVision "
                "antetlidir.\n\nFirma anteti TAM lisansla açılır: Yardım > Lisans ve "
                "makine kimliği.")
            return
        p = tk.Toplevel(self.master)
        p.title("Firma anteti (A3 antet DXF'inden şablon)")
        p.geometry("1100x720")
        f = ttk.Frame(p, padding=10); f.pack(fill="both", expand=True)
        bil = PA.ayarli_sablon_bilgi()
        v_durum = tk.StringVar(value=(
            f"KAYITLI: {bil.get('antet_ad')}  (kaynak {bil.get('antet_kaynak')}, "
            f"{bil.get('antet_tarih')})" if bil.get("antet_sablon")
            else "Kayıtlı firma anteti yok: paftalar Pi3D antetli çıkar."))
        ttk.Label(f, textvariable=v_durum, font=("", 10, "bold"), wraplength=1060,
                  justify="left").pack(anchor="w")
        ttk.Label(f, foreground="#555", wraplength=1060, justify="left", text=(
            "Antetinizi A3 YATAY kâğıda çerçevesiyle birlikte DXF olarak kaydedin (antet "
            "sağ altta, kutuları çizgiyle çizilmiş, blok ise patlatılmış). Program kâğıdı, "
            "çerçeveyi, antet bloğunu ve kapalı kutuları ölçer; kutudaki yazı okunabiliyorsa "
            "(Part Name, Drawing No, Material, Weight, Scale, Drawn, Checked, FILE…) alanı "
            "kendisi önerir. Aşağıdaki tabloda her alanın hangi kutuya gideceğini onaylayın; "
            "KAYDET deyince şablon kalıcı klasöre yazılır ve bütün paftalarda, PDF'lerde ve "
            "kaynak resimlerinde kullanılır.")).pack(anchor="w", pady=(2, 6))
        ust = ttk.Frame(f); ust.pack(fill="x")
        durum = {"tanim": None, "secim": {}, "png": None}
        tuval = tk.Canvas(f, height=300, background="white", highlightthickness=1,
                          highlightbackground="#bbb")
        tuval.pack(fill="x", pady=(6, 6))
        orta = ttk.Frame(f); orta.pack(fill="both", expand=True)
        sut = ("no", "kutu", "etiket", "alan")
        tab = ttk.Treeview(orta, columns=sut, show="headings", height=9)
        for c, ad, w in zip(sut, ("#", "kutu (x, y, en x boy mm)", "kutudaki yazı", "alan"),
                            (40, 220, 300, 200)):
            tab.heading(c, text=ad); tab.column(c, width=w, anchor="w")
        tab.pack(side="left", fill="both", expand=True)
        sb_ = ttk.Scrollbar(orta, orient="vertical", command=tab.yview)
        sb_.pack(side="left", fill="y"); tab.configure(yscrollcommand=sb_.set)
        sag = ttk.Frame(orta, padding=(8, 0)); sag.pack(side="left", fill="y")
        ttk.Label(sag, text="Seçili kutuya alan ata:").pack(anchor="w")
        alan_ad = dict(PA.ALAN_ACIKLAMA)
        v_alan = tk.StringVar()
        cb_alan = ttk.Combobox(sag, textvariable=v_alan, state="readonly", width=34,
                               values=["(boş)"] + [f"{k} – {v}" for k, v in alan_ad.items()])
        cb_alan.pack(anchor="w", pady=(2, 4))

        def tablo_doldur():
            tab.delete(*tab.get_children())
            t = durum["tanim"]
            if not t:
                return
            ters = {}
            for alan, i in durum["secim"].items():
                ters.setdefault(i, []).append(alan)
            for i, h in enumerate(t["hucreler"]):
                tab.insert("", "end", iid=str(i), values=(
                    i, f"{h[0]:.1f}, {h[1]:.1f}   {h[2] - h[0]:.1f} x {h[3] - h[1]:.1f}",
                    t["etiketler"][i][:60], ", ".join(ters.get(i, []))))
            try:
                PA.tanim_onizleme_png(t, durum["png"], durum["secim"])
                ham = tk.PhotoImage(file=durum["png"])
                gw = max(tuval.winfo_width(), 900)
                k = max(1, -(-ham.width() // gw), -(-ham.height() // 300))
                durum["resim"] = ham.subsample(k, k) if k > 1 else ham
                tuval.delete("all")
                tuval.create_image(gw // 2, 150, image=durum["resim"])
            except Exception as ex:
                self._yaz(f"antet önizlemesi çizilemedi: {ex}")

        def ata():
            sec = tab.selection()
            if not sec or not durum["tanim"]:
                return
            i = int(sec[0])
            v = v_alan.get()
            # bu kutudaki eski alanları kaldır
            for alan in [a for a, j in durum["secim"].items() if j == i]:
                durum["secim"].pop(alan)
            if v and not v.startswith("("):
                alan = v.split(" – ")[0]
                durum["secim"][alan] = i
            tablo_doldur()
            tab.selection_set(str(i))

        def sec_degisti(_e=None):
            sec = tab.selection()
            if not sec:
                return
            i = int(sec[0])
            alanlar = [a for a, j in durum["secim"].items() if j == i]
            v_alan.set(f"{alanlar[0]} – {alan_ad[alanlar[0]]}" if alanlar else "(boş)")
        tab.bind("<<TreeviewSelect>>", sec_degisti)
        ttk.Button(sag, text="Ata", command=ata).pack(anchor="w")
        v_not = tk.StringVar(value="")
        ttk.Label(sag, textvariable=v_not, foreground="#b00020", wraplength=260,
                  justify="left").pack(anchor="w", pady=(10, 0))

        def analiz():
            y = filedialog.askopenfilename(
                title="Firma anteti DXF (A3 yatay, çerçeveyle)", parent=p,
                filetypes=[("DXF", "*.dxf"), ("Tümü", "*.*")])
            if not y:
                return
            try:
                t = PA.otomatik_tanim(y, log=self._yaz)
            except Exception as ex:
                messagebox.showerror("Firma anteti", f"Antet çözülemedi:\n\n{ex}", parent=p)
                return
            durum["tanim"] = t
            durum["secim"] = dict(t["oneri"])
            import tempfile
            durum["png"] = os.path.join(tempfile.gettempdir(), "pi3d_antet_onizleme.png")
            v_durum.set(f"ÇÖZÜLDÜ: {os.path.basename(y)}  -  kâğıt {t['kagit_ad'] or '?'} "
                        f"{t['kagit'][0]:.0f} x {t['kagit'][1]:.0f} mm, {len(t['hucreler'])} kutu, "
                        f"{len(t['oneri'])} alan önerildi. Tabloyu denetleyip KAYDET deyin.")
            v_not.set("\n".join(t["notlar"]))
            tablo_doldur()

        def kaydet():
            t = durum["tanim"]
            if not t:
                messagebox.showinfo("Firma anteti", "Önce antet DXF'ini seçin.", parent=p); return
            if "parca_adi" not in durum["secim"] and "resim_no" not in durum["secim"]:
                messagebox.showwarning("Firma anteti", "En azından parça adı ya da resim no "
                                       "kutusunu atayın.", parent=p); return
            try:
                sb = PA.sablon_kur(t, durum["secim"], log=self._yaz)
            except Exception as ex:
                messagebox.showerror("Firma anteti", f"Şablon kurulamadı:\n\n{ex}", parent=p)
                return
            self.sablon = sb
            self.antet_neden = ""
            v_durum.set(f"KAYDEDİLDİ: {sb.bilgi.get('ad')}  ->  {sb.kok}.dxf / .json")
            self._yaz(f"firma anteti kaydedildi: {sb.kok}")
            try:
                self.pafta_doldur()
            except Exception:
                pass
            messagebox.showinfo("Firma anteti", "Firma anteti kaydedildi. Bundan sonraki "
                                "paftalar, PDF'ler ve kaynak resimleri bu antetle çıkar.\n\n"
                                "Değiştirmek için aynı pencereden yeni DXF seçin; kaldırmak "
                                "için KALDIR.", parent=p)

        def kaldir():
            if PA.sablon_kaldir():
                self.sablon = None
                v_durum.set("Firma anteti kaldırıldı: paftalar Pi3D antetli çıkar.")
                self._yaz("firma anteti kaldırıldı")
                try:
                    self.pafta_doldur()
                except Exception:
                    pass
        ttk.Button(ust, text="Antet DXF'ini seç ve çöz…", command=analiz).pack(side="left")
        ttk.Button(ust, text="KAYDET ve kullan", style="Bas.TButton", command=kaydet
                   ).pack(side="left", padx=(8, 0), ipadx=8)
        ttk.Button(ust, text="KALDIR (Pi3D antetine dön)", command=kaldir).pack(side="left", padx=(8, 0))
        ttk.Button(ust, text="Kapat", command=p.destroy).pack(side="right")

    def lisans_penceresi(self):
        """Yardım > Lisans: makine kimliği (kopyala), durum, .lic yükleme."""
        if L is None:
            messagebox.showerror("Lisans", "Lisans modülü yüklenemedi.")
            return
        p = getattr(self, "_lisans_pencere", None)
        if p is not None:
            try:
                p.lift()
                return
            except Exception:
                pass
        p = tk.Toplevel(self.master)
        self._lisans_pencere = p
        p.title("Pi3D lisansı")
        p.resizable(False, False)
        f = ttk.Frame(p, padding=14)
        f.pack(fill="both", expand=True)
        d = getattr(self, "lisans", None) or {}
        ttk.Label(f, text="MAKİNE KİMLİĞİ (bu bilgisayar)", font=("", 10, "bold")).pack(anchor="w")
        kutu = ttk.Frame(f); kutu.pack(fill="x", pady=(2, 8))
        v_kimlik = tk.StringVar(value=d.get("makine") or L.makine_kimligi())
        e = ttk.Entry(kutu, textvariable=v_kimlik, width=28, font=("Consolas", 12), state="readonly")
        e.pack(side="left")

        def kopyala():
            try:
                self.master.clipboard_clear()
                self.master.clipboard_append(v_kimlik.get())
                v_durum.set("Makine kimliği panoya kopyalandı; PiVision'a gönderin.")
            except Exception:
                pass
        ttk.Button(kutu, text="Kopyala", command=kopyala).pack(side="left", padx=6)
        ttk.Label(f, foreground="#555", wraplength=520, justify="left", text=(
            "Bu kodu PiVision lisans masasına gönderin. Lisans dosyası (pi3d.lic) "
            "bu makineye kilitlidir; başka bilgisayarda çalışmaz.")).pack(anchor="w")
        ttk.Separator(f).pack(fill="x", pady=8)
        ttk.Label(f, text="LİSANS DURUMU", font=("", 10, "bold")).pack(anchor="w")
        v_durum = tk.StringVar(value=L.ozet(d))
        ttk.Label(f, textvariable=v_durum, wraplength=520, justify="left",
                  foreground=("#1a7f37" if d.get("gecerli") else "#b00020")).pack(anchor="w", pady=(2, 8))
        if d.get("dosya"):
            ttk.Label(f, foreground="#777", text=f"dosya: {d['dosya']}").pack(anchor="w")

        def yukle():
            y = filedialog.askopenfilename(
                title="Lisans dosyası (pi3d.lic)",
                filetypes=[("Lisans", "*.lic"), ("Tümü", "*.*")])
            if not y:
                return
            try:
                self.lisans = L.kur(y)
            except Exception as ex:
                messagebox.showerror("Lisans", f"Lisans kabul edilmedi:\n\n{ex}", parent=p)
                return
            v_durum.set(L.ozet(self.lisans))
            self.v_durum.set("lisans yüklendi: " + L.ozet(self.lisans).splitlines()[0])
            messagebox.showinfo("Lisans", "Lisans yüklendi:\n\n" + L.ozet(self.lisans), parent=p)
        alt = ttk.Frame(f); alt.pack(fill="x", pady=(8, 0))
        ttk.Button(alt, text="Lisans dosyasını yükle…", command=yukle).pack(side="left")
        ttk.Button(alt, text="Kapat", command=p.destroy).pack(side="right")

        def kapandi(_e=None):
            self._lisans_pencere = None
        p.bind("<Destroy>", kapandi)

    # ------------------------------------------------------------ iskelet
    def _kur(self):
        self.master.title(BASLIK)
        # KÜÇÜK EKRAN (15" dizüstü: 1366x768, ya da 1920x1080 %125 ölçekle
        # 1536x864). Görev çubuğu ve pencere başlığı düşünce ~700 piksel
        # kalır. Eskiden pencere 1755x993 istiyordu: alttaki İPTAL, günlük
        # ve durum çubuğu ile 6-7. adımın düğmeleri ekran dışında kalıyordu.
        try:
            sw, sh = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
        except Exception:
            sw, sh = 1920, 1080
        self.kucuk = sh < 950 or sw < 1500
        self.master.minsize(1000, 600)
        self._pencere_ikonu()
        try:
            ttk.Style().configure("Bas.TButton", font=("Segoe UI", 10, "bold"))
            ttk.Style().configure("Baslik.TLabel", font=("Segoe UI", 12, "bold"))
        except Exception:
            pass
        self._baslik_seridi()
        orta = ttk.Frame(self)
        orta.pack(fill="both", expand=True)
        self._sure_paneli(orta)            # sağda: işlemler ve süreleri
        self.defter = ttk.Notebook(orta)
        self.defter.pack(side="left", fill="both", expand=True)
        self.sayfa = []
        for ad in ADIM:
            f = ttk.Frame(self.defter, padding=10)
            self.defter.add(f, text=ad, state="disabled")
            self.sayfa.append(f)
        # İptal düğmesi sayfalardan ÖNCE kurulur: _basla/_bitir onu
        # sayfa kurulurken de çağırabilir.
        self._durum_cubugu()
        self._sayfa1(); self._sayfa2(); self._sayfa3()
        self._sayfa4(); self._sayfa5(); self._sayfa6(); self._sayfa7()
        self._sayfa8()
        self.defter.bind("<<NotebookTabChanged>>", self._sekme_degisti)
        self._menu()
        # ALT ÇUBUKLAR ÖNCE YER ALIR: pencere küçükse sekmeler küçülür,
        # durum çubuğu / günlük / ilerleme + İPTAL asla ekran dışına
        # itilmez (side="bottom", before=orta: paketleme sırasında önde).
        self.v_durum = tk.StringVar(value="motor yükleniyor…")
        self.durum_etiket = ttk.Label(self, textvariable=self.v_durum,
                                      relief="sunken", anchor="w", padding=3)
        self.durum_etiket.pack(side="bottom", fill="x", pady=(4, 0), before=orta)
        gf = ttk.LabelFrame(self, text=" Günlük ", padding=2 if self.kucuk else 4)
        gf.pack(side="bottom", fill="x", before=orta)
        self.gunluk = tk.Text(gf, height=3 if self.kucuk else 7, wrap="none",
                              font=("Consolas", 9))
        gk = ttk.Scrollbar(gf, orient="vertical", command=self.gunluk.yview)
        self.gunluk.configure(yscrollcommand=gk.set, state="disabled")
        self.gunluk.pack(side="left", fill="both", expand=True)
        gk.pack(side="right", fill="y")
        self._durum_ic.pack(side="bottom", fill="x", pady=(4, 2), before=orta)
        for i, sf in enumerate(self.sayfa):
            # 1. sayfada yer boldur ve oradaki yol gösterme ("önceki
            # çıktıyı aç ...") her zaman okunmalı: kısaltılmaz.
            self._sayfa_sikistir(sf, kisalt=(i != 0))
        self._adim_ac(0)
        self._pencereyi_yerlestir(sw, sh)

    def _sayfa_sikistir(self, f, kisalt=True):
        """Bir sayfayı küçük ekrana uydurur.

        1) Listeden (genişleyen öğe) SONRA gelen her şey - özet satırı,
           düğme şeridi - sayfanın ALTINA sabitlenir ve paketleme
           sırasında listenin önüne alınır: yer daralınca önce LİSTE
           küçülür, düğmeler hiç kaybolmaz.
        2) Tablo sütunları, toplamı sayfaya sığmayacaksa orantılı
           daraltılır (genişleyince yine açılırlar).
        3) Küçük ekranda uzun açıklamalar tek satıra iner; tıklayınca
           tamamı açılır."""
        try:
            kolelar = f.pack_slaves()
        except Exception:
            return
        gen = [w for w in kolelar if str(w.pack_info().get("expand")) in ("1", "True", "true")]
        if gen:
            ilk = gen[0]
            sonra = kolelar[kolelar.index(ilk) + 1:]
            for w in reversed(sonra):
                bilgi = {k: v for k, v in w.pack_info().items() if k != "in"}
                bilgi.update(side="bottom", before=ilk)
                w.pack(**bilgi)
        for w in [f] + list(self._tum_cocuklar(f)):
            sinif = w.winfo_class()
            if sinif == "Treeview":
                self._sutun_daralt(w)
            elif sinif in ("TLabel", "Label") and kisalt:
                self._aciklama_kisalt(w)
            elif sinif in ("TFrame", "Frame", "TLabelframe"):
                self._serit_duzelt(w)

    def _serit_duzelt(self, fr):
        """Düğme şeridi: sağa yaslı düğmeler ÖNCE yer alsın (dar pencerede
        soldaki açıklama yazısı onları dışarı itmesin); şeritteki uzun
        tek satırlık açıklama kaydırılarak sarılsın."""
        try:
            kole = fr.pack_slaves()
        except Exception:
            return
        if not kole:
            return
        sag = [w for w in kole if w.pack_info().get("side") == "right"]
        sol = [w for w in kole if w.pack_info().get("side") == "left"]
        if sag and sol:
            ilk = kole[0]
            for w in sag:
                if w is ilk:
                    continue
                bilgi = {k: v for k, v in w.pack_info().items() if k != "in"}
                bilgi["before"] = ilk
                w.pack(**bilgi)
        for w in sol:
            if w.winfo_class() in ("TLabel", "Label"):
                try:
                    t = str(w.cget("text"))
                    if len(t) > 50 and not int(str(w.cget("wraplength") or 0)):
                        w.configure(wraplength=480 if self.kucuk else 560,
                                    justify="left")
                except Exception:
                    pass

    @staticmethod
    def _tum_cocuklar(w):
        for c in w.winfo_children():
            yield c
            yield from Uygulama._tum_cocuklar(c)

    def _sutun_daralt(self, agac):
        sut = [c for c in (agac["columns"] or ())]
        if agac.cget("show") and "tree" in str(agac.cget("show")):
            sut = ["#0"] + list(sut)
        gen = [int(agac.column(c, "width")) for c in sut]
        sinir = 820 if self.kucuk else 1150
        if sum(gen) <= sinir:
            return
        k = sinir / float(sum(gen))
        for c, g in zip(sut, gen):
            agac.column(c, width=max(36, int(g * k)), stretch=True,
                        minwidth=30)

    def _aciklama_kisalt(self, w):
        """Uzun gri açıklama: küçük ekranda ilk cümlesi + '… (tıklayın)'."""
        try:
            metin = str(w.cget("text"))
        except Exception:
            return
        if len(metin) < 160 or str(w.cget("textvariable")):
            return
        try:
            if int(str(w.cget("wraplength") or 0)) > 0:
                w.configure(wraplength=780 if self.kucuk else 900)
        except Exception:
            pass
        if not self.kucuk:
            return
        ilk = metin.replace("\n", " ").split(". ")[0].strip()
        if len(ilk) > 150:
            ilk = ilk[:147].rstrip() + "…"
        kisa = ilk.rstrip(".") + ".   ▸ ayrıntı (tıklayın)"
        izgara = w.winfo_manager() == "grid"
        w.configure(text=kisa, cursor="hand2",
                    wraplength=360 if izgara else 780, justify="left")
        w._pi_uzun, w._pi_kisa, w._pi_acik = metin, kisa, False

        def degis(_e=None, w=w):
            w._pi_acik = not w._pi_acik
            w.configure(text=(w._pi_uzun + "   ▴ kapat") if w._pi_acik
                        else w._pi_kisa)
        w.bind("<Button-1>", degis)

    def _pencereyi_yerlestir(self, sw, sh):
        """Pencere ekrandan büyük açılmasın. Küçük ekranda tam ekran
        (Windows'ta 'zoomed'), büyükte ekranın %90'ı. YENİ İŞ'te
        kullanıcının pencere boyutu korunur."""
        if getattr(self, "_yeniden_kuruluyor", False):
            return
        try:
            if self.kucuk:
                try:
                    self.master.state("zoomed")
                    return
                except Exception:
                    pass
                self.master.geometry(f"{sw - 16}x{sh - 80}+0+0")
            else:
                g, y = min(1600, int(sw * 0.9)), min(1000, int(sh * 0.9))
                self.master.geometry(f"{g}x{y}+{(sw - g) // 2}+{(sh - y) // 3}")
        except Exception:
            pass

    def _durum_cubugu(self):
        """İlerleme çubuğu ve İPTAL düğmesi - her sayfadan görünür.

        İptal eskiden yalnız 5. sayfadaydı. 6 (açınım) ve 7 (pafta)
        adımlarında iş uzayınca durum çubuğu "İptal ile
        durdurabilirsiniz" yazıyor ama ortada basılacak bir düğme
        olmuyordu."""
        ic = ttk.Frame(self)
        self._durum_ic = ic               # _kur alta sabitler
        # Sağda: ÇIKIŞ, YENİ İŞ, İPTAL (kullanıcı: "işlem bittikten sonra
        # sistemi yenileyebilmeliyim, kapatıp açma gerekmemeli; bir de
        # quit butonu"). Her sayfadan görünür.
        self.b_cikis = ttk.Button(ic, text="ÇIKIŞ", command=self.cikis, width=8)
        self.b_cikis.pack(side="right", padx=(8, 0))
        self.b_yeni = ttk.Button(ic, text="YENİ İŞ", command=self.yeni_is, width=9)
        self.b_yeni.pack(side="right", padx=(8, 0))
        self.b_iptal = ttk.Button(ic, text="İPTAL", command=self.iptal,
                                  state="disabled", width=9)
        self.b_iptal.pack(side="right", padx=(8, 0))
        self.ilerleme = ttk.Progressbar(ic, mode="determinate")
        self.ilerleme.pack(side="left", fill="x", expand=True)

    def _sekme_degisti(self, _e=None):
        """Sekmeye geçilince listesi boşsa klasörden doldur: önceki
        çıktıyı açan kullanıcı 'Listeyi tazele' aramak zorunda kalmasın."""
        try:
            i = self.defter.index(self.defter.select())
        except Exception:
            return
        if self.calisiyor or not (self.v_out.get() or "").strip():
            return
        if i == 4 and self.liste.size() == 0:
            self._cikti_listesi()
        elif (i == 6 and hasattr(self, "pf_agac")
              and not self.pf_agac.get_children()
              and (IS.dosyalar(self.v_out.get().strip(), "dxf")
                   or IS.dosyalar(self.v_out.get().strip(), "acinim"))):
            self.pafta_doldur()

    def _sure_paneli(self, ust):
        """Sağdaki panel: yapılan her işlem, açıklaması ve süresi; en altta
        TOPLAM süre. Çalışan işin geçen süresi ve - ilerleme biliniyorsa -
        ÖLÇÜLEN hıza göre kalan süresi de burada yazar.

        Süreler çıktı klasörüne (pi3d_is.json) de yazılır: iş birkaç
        oturuma yayılsa da klasörün toplam süresi kaybolmaz."""
        p = ttk.LabelFrame(ust, text=" İşlemler ve süreler ", padding=4)
        p.pack(side="right", fill="y", padx=(6, 0))
        k = getattr(self, "kucuk", False)
        self.v_simdi = tk.StringVar(value="şu an çalışan iş yok")
        self.simdi_etiket = tk.Label(p, textvariable=self.v_simdi, justify="left",
                                     anchor="w", wraplength=200 if k else 250,
                                     fg="#0b2340", font=("Segoe UI", 9, "bold"))
        self.simdi_etiket.pack(fill="x", pady=(0, 4))
        cer = ttk.Frame(p); cer.pack(fill="both", expand=True)
        self.sure_agac = ttk.Treeview(cer, columns=("islem", "sure"),
                                      show="headings", height=6 if k else 16,
                                      selectmode="none")
        self.sure_agac.heading("islem", text="İŞLEM")
        self.sure_agac.heading("sure", text="SÜRE")
        self.sure_agac.column("islem", width=130 if k else 170, anchor="w")
        self.sure_agac.column("sure", width=64 if k else 72, anchor="e",
                              stretch=False)
        self.sure_agac.tag_configure("eski", foreground="#888")
        self.sure_agac.tag_configure("hata", foreground="#b00")
        self.sure_agac.tag_configure("iptal", foreground="#a60")
        kd = ttk.Scrollbar(cer, orient="vertical", command=self.sure_agac.yview)
        self.sure_agac.configure(yscrollcommand=kd.set)
        self.sure_agac.pack(side="left", fill="both", expand=True)
        kd.pack(side="right", fill="y")
        self.v_toplam = tk.StringVar(value="")
        tk.Label(p, textvariable=self.v_toplam, justify="left", anchor="w",
                 wraplength=200 if k else 250, font=("Segoe UI", 9, "bold")
                 ).pack(fill="x", pady=(4, 0))
        self.oturum_sure = 0.0
        self.klasor_sure = 0.0
        self._toplam_yaz()

    def _toplam_yaz(self):
        self.v_toplam.set(
            f"TOPLAM (bu oturum): {IS.sure_metni(self.oturum_sure)}\n"
            f"Bu çıktı klasöründe toplam: "
            f"{IS.sure_metni(self.klasor_sure + self.oturum_sure)}")

    def _sure_satiri(self, ad, sure, sonuc="tamam", eski=False):
        ek = {"hata": "  (HATA)", "iptal": "  (iptal)"}.get(sonuc, "")
        tag = ("eski",) if eski else ((sonuc,) if sonuc in ("hata", "iptal")
                                      else ())
        i = self.sure_agac.insert("", "end", values=(ad + ek,
                                                     IS.sure_metni(sure)),
                                  tags=tag)
        self.sure_agac.see(i)

    def _klasor_sureleri(self):
        """Seçilen çıktı klasörünün önceki oturumlarındaki işlemleri
        panele (soluk renkte) getirir."""
        self.sure_agac.delete(*self.sure_agac.get_children())
        on = (self.v_out.get() or "").strip() if hasattr(self, "v_out") else ""
        d = IS.durum_oku(on) if on else None
        self.klasor_sure = 0.0
        if d and d["islemler"]:
            for r in d["islemler"][-60:]:
                self._sure_satiri(f"{r.get('tarih', '')[5:16]}  {r['ad']}",
                                  r.get("sure", 0), r.get("sonuc", "tamam"),
                                  eski=True)
            self.klasor_sure = sum(float(r.get("sure") or 0)
                                   for r in d["islemler"])
            # Bu oturumda yapılanlar zaten dosyada; iki kez sayılmasın.
            self.klasor_sure = max(0.0, self.klasor_sure - self.oturum_sure)
        self._toplam_yaz()

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
        k = getattr(self, "kucuk", False)
        s = tk.Frame(self, bg=ZEMIN, height=52 if k else 84)
        s.pack(fill="x", side="top")
        s.pack_propagate(False)
        varmi = logo_var()
        if varmi:
            self._logo = ((logo_yukle("pivision_44.png") if k else None)
                          or logo_yukle("pivision_64.png")
                          or logo_yukle("pivision_56.png"))
            if self._logo is not None:
                tk.Label(s, image=self._logo, bg=ZEMIN, bd=0
                         ).pack(side="left", padx=(14, 0), pady=2 if k else 4)
            self._ikon_kucuk = ((logo_yukle("pi3d_48.png") if k else None)
                                or logo_yukle("pi3d_72.png")
                                or logo_yukle("pi3d_64.png"))
            if self._ikon_kucuk is not None:
                tk.Label(s, image=self._ikon_kucuk, bg=ZEMIN, bd=0
                         ).pack(side="right", padx=(0, 14), pady=2 if k else 6)
        sag = tk.Frame(s, bg=ZEMIN)
        sag.pack(side="right", padx=(0, 10))
        tk.Label(sag, text=f"Pi3D  v{IS.PI3D_SURUM}", bg=ZEMIN, fg=YAZI, bd=0,
                 font=("Segoe UI", 14 if k else (17 if varmi else 26), "bold")
                 ).pack(anchor="e")
        tk.Label(sag, text="3B modelden parça listesi ve teknik resim",
                 bg=ZEMIN, fg=SOLUK, bd=0, font=("Segoe UI", 8 if k else 9)
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
        dg = ttk.Frame(f); dg.grid(row=3, column=1, sticky="e", pady=14)
        ttk.Button(dg, text="ÖNCEKİ ÇIKTIYI AÇ…", command=self.onceki_ac
                   ).pack(side="left", padx=(0, 10), ipadx=6, ipady=5)
        self.b_incele = ttk.Button(dg, text="İNCELE  ▸", style="Bas.TButton",
                                   command=self.incele, state="disabled")
        self.b_incele.pack(side="left", ipadx=14, ipady=5)
        # Önceki çalışmanın özeti: ne var, ne eksik.
        self.v_onceki = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.v_onceki, justify="left",
                  font=("Consolas", 9), foreground="#036"
                  ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(12, 0))
        ttk.Label(f, foreground="#555", justify="left", text=(
            "Okunan biçimler: STEP (.stp, .step), IGES (.igs), BREP.\n"
            "CATIA (.CATProduct/.CATPart), SolidWorks, NX, Inventor gibi kapali\n"
            "bicimler dogrudan acilamaz; CAD'den STEP olarak kaydedip verin.\n\n"
            "Dosya okunur, kopyalar birleştirilir, parça / standart eleman /\n"
            "kaynak dikişi ayrımı yapılır. Büyük montajlarda bir-iki dakika sürebilir.\n\n"
            "HER ADIM AYRI YAPILABİLİR, İSTENDİĞİ KADAR TEKRARLANABİLİR. Daha önce\n"
            "çıktı aldığınız klasörü seçerseniz ne var ne eksik aşağıda yazar:\n"
            "  - pafta ve PDF için modeli okumaya gerek yok: ÖNCEKİ ÇIKTIYI AÇ yeter;\n"
            "  - eksik çizim, açınım ve lazer için İNCELE ile model okunur, sonra\n"
            "    istediğiniz sekmeye geçersiniz; ayarlarınız (malzeme, görünüş)\n"
            "    geri gelir, güncel çizimler yeniden üretilmez.")
        ).grid(row=4, column=0, columnspan=3, sticky="w")
        f.columnconfigure(1, weight=1)

    # ------------------------------------------------------------ 2 BOM
    def _sayfa2(self):
        f = self.sayfa[1]
        bf = ttk.Frame(f); bf.pack(fill="x", pady=(0, 6))
        ttk.Label(bf, text="Komponentler, BOM ve malzeme",
                  style="Baslik.TLabel").pack(side="left")
        # ARAMA: BOM çıkınca sıralama değişir; yüzlerce satırda bir parçayı
        # gözle bulmak zor (kullanıcı: "listede olduğundan eminim ama gözden
        # kaçıyor"). Kod, tanım ya da poz içinde geçen her satır; Enter /
        # Bul ile sıradakine gider, kapalı montaj dalı açılır.
        self.v_ara_sonuc = tk.StringVar(value="")
        ttk.Label(bf, textvariable=self.v_ara_sonuc, foreground="#555"
                  ).pack(side="right", padx=(6, 0))
        ttk.Button(bf, text="Bul ▸", command=self.ara_bul).pack(side="right")
        self.v_ara = tk.StringVar()
        self.e_ara = ttk.Entry(bf, textvariable=self.v_ara, width=28)
        self.e_ara.pack(side="right", padx=(4, 4))
        self.e_ara.bind("<Return>", lambda e: self.ara_bul())
        self.v_ara.trace_add("write", lambda *a: self._ara_sifirla())
        ttk.Label(bf, text="Ara (kod / tanım / poz):").pack(side="right")
        self._ara_liste, self._ara_i = [], -1
        sut = ("poz", "kod", "tanim", "adet", "sinif", "malzeme", "kaynak", "olcu", "kg")
        gen = (40, 150, 220, 45, 140, 135, 75, 110, 65)
        cer = ttk.Frame(f); cer.pack(fill="both", expand=True)
        # SEÇİLİ PARÇANIN RESMİ: malzeme / standart / parça kararı adla
        # verilemiyorsa parçayı görmek yeter (kullanıcı isteği). Küçük
        # izometrik, yalnız görünen kenarlar; ayrı iş parçacığında çizilir.
        rf = ttk.LabelFrame(cer, text=" Seçili parça ", padding=4)
        rf.pack(side="right", fill="y", padx=(6, 0))
        # ad üstte: liste kısa kalınca (15 inç ekran) resmin altı kesilse de
        # hangi parça olduğu okunur
        self.v_parca_ad = tk.StringVar(value="listeden bir satır seçin")
        ttk.Label(rf, textvariable=self.v_parca_ad, wraplength=230, justify="left",
                  foreground="#333").pack(anchor="w", pady=(0, 4))
        # Tuval kalan yeri alır ve GERÇEK boyutuna göre çizer: eskiden 230x150
        # ayarlı tuval kısa listede alttan kesiliyor, resim kesilen kısımda
        # kalıyordu (kullanıcı: "burada parça görünüyor mu?" - görünmüyordu).
        self.c_parca = tk.Canvas(rf, width=230, height=150, background="white",
                                 highlightthickness=1, highlightbackground="#ccc")
        self.c_parca.pack(fill="both", expand=True)
        self._tuval_yeniden_ciz(self.c_parca)
        self.c_parca.bind("<Double-1>", lambda e: self.parca_resmi_penceresi(self.c_parca))
        ttk.Label(rf, foreground="#777", text="çift tık: büyük pencere").pack(anchor="w")
        self._resim_onbellek, self._resim_istek = {}, None
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
        self.ag.bind("<<TreeviewSelect>>", lambda e: self.parca_resmi_goster())
        self.ag.tag_configure("std", foreground="#777")
        self.ag.tag_configure("kaynak", foreground="#b06")
        self.ag.tag_configure("data", foreground="#070")
        self.ag.tag_configure("montaj", foreground="#036", font=("Segoe UI", 9, "bold"))
        self.v_hiyerarsik = tk.BooleanVar(value=True)
        sf = ttk.Frame(f); sf.pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(sf, text="montaj ağacı olarak göster  "
                                "(ana ürün ▸ alt montaj ▸ parça)",
                        variable=self.v_hiyerarsik,
                        command=self._agac_doldur).pack(side="left")
        # Sınıf addan ve montaj ağacından bulunur; bulunamayanı kullanıcı
        # düzeltir ve program ÖĞRENİR (ayar dosyasına yazılır, sonraki
        # modellerde de geçerli).
        ttk.Button(sf, text="AI ile kontrol et", command=self.ai_sor
                   ).pack(side="right", padx=(8, 0))
        for ad, sinif in (("Kaynak dikişi", "kaynak"),
                          ("Standart / satın alınan", "standart"),
                          ("Üretim parçası", "parca")):
            ttk.Button(sf, text=ad, command=lambda c=sinif: self.sinif_degistir(c)
                       ).pack(side="right", padx=(4, 0))
        ttk.Label(sf, text="seçilenin sınıfını değiştir:", foreground="#555"
                  ).pack(side="right", padx=(0, 4))

        mf = ttk.LabelFrame(f, text=" Malzeme – kütle = hacim × yoğunluk ", padding=6)
        mf.pack(fill="x", pady=(8, 0))
        self.v_mal = tk.StringVar()
        self.cb_mal = ttk.Combobox(mf, textvariable=self.v_mal, state="readonly", width=40)
        self.cb_mal.grid(row=0, column=0, rowspan=2, padx=(0, 8))
        ttk.Button(mf, text="Hepsine uygula",
                   command=lambda: self.malzeme_uygula(False)).grid(row=0, column=1, sticky="ew")
        ttk.Button(mf, text="Seçili satırlara",
                   command=lambda: self.malzeme_uygula(True)).grid(row=1, column=1, sticky="ew", pady=(3, 0))
        ttk.Button(mf, text="Malzeme listesi yükle (Excel / CSV)…",
                   command=self.malzeme_dosya).grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ttk.Button(mf, text="Malzeme şablonu yaz (Excel)…",
                   command=self.malzeme_sablon).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=(3, 0))
        ttk.Button(mf, text="Malzemeyi CAD'den al  (adım adım)…",
                   command=self.malzeme_sihirbazi).grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=(3, 0))
        ttk.Button(mf, text="CATIA BOM ile eşleştir (adet, eksik, malzeme)…",
                   command=self.catia_bom_esle).grid(
            row=3, column=1, columnspan=2, sticky="ew", pady=(3, 0))
        ttk.Label(mf, foreground="#555", justify="left", text=(
            "KAYNAK sütunu malzemenin nereden geldiğini söyler: data'dan (STEP'te ya da\n"
            "parça adında tanımlı), seçim (sizin verdiğiniz), varsayılan (hiçbiri yoksa).\n"
            "STEP malzeme taşımıyorsa: SolidWorks, CATIA, NX, Creo, Inventor... parça\n"
            "listesinden almak için soldaki düğme ya da Yardım menüsü.")
        ).grid(row=0, column=3, rowspan=3, sticky="w", padx=12)
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
        # GÖRÜNÜŞ SEÇİMİ OTOMATİK (kullanıcı: "görünüm sayısı girişi
        # istemiyorum; sistem parçadaki özelliklere göre 6 görüntü + 5-6
        # detay bile yapabilir"): seçim kutuları kalktı. Parça bazlı istek
        # (görünüş listesi, kesit, perspektif) aşağıdaki istisna satırında.
        gf = ttk.LabelFrame(f, text=" Görünüşler (otomatik) ", padding=8)
        gf.grid(row=1, column=0, sticky="nsew")
        self.v_gor = {}
        self.v_perspektif = tk.BooleanVar(value=True)
        ttk.Checkbutton(gf, text="küçük perspektif (izometrik) de konsun",
                        variable=self.v_perspektif).grid(row=0, column=0, columnspan=2, sticky="w")
        self.v_gor_bilgi = tk.StringVar()
        # wraplength ŞART: uzun tek satır sütunu genişletip Kesit kutusunu
        # 1280 px ekranda 24 px'e sıkıştırıyordu
        ttk.Label(gf, textvariable=self.v_gor_bilgi, foreground="#555",
                  wraplength=330, justify="left"
                  ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

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
        # gizli çizgi + montaj resmi aynı satırda: altta araç yönü satırı
        # eklendi, 15 inç ekranda (1280x650) sayfa taşmasın
        ttk.Checkbutton(sf, text="gizli çizgiler", variable=self.v_gizli).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(sf, text="montaj resmi de üretilsin", variable=self.v_montaj).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(sf, text="en az delik çapı (mm)").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.v_delik = tk.StringVar(value="1.0")
        ttk.Entry(sf, textvariable=self.v_delik, width=7).grid(row=2, column=1, sticky="w", pady=(4, 0))

        # --- ARAÇ YÖNÜ: parça KULLANIM yönünde çizilir (yatırılmaz, çevrilmez).
        # Kullanıcı: "araç yönü bizim için önemli; ön panel baş aşağı
        # konulmuş". Aracın önü hangi eksendeyse ÖN görünüş oradan bakar,
        # ÜST üstten; geniş yüz ÖN'e döner (Chevalier). Küçük ekrana sığsın
        # diye "Çizim" kutusunun içinde durur.
        ttk.Label(sf, text="aracın önü / üstü").grid(row=3, column=0, sticky="w", pady=(4, 0))
        ar_ = ttk.Frame(sf); ar_.grid(row=3, column=1, sticky="w", pady=(4, 0))
        self.v_arac_on = tk.StringVar(value="oto (parça adlarından öneri)")
        self.cb_arac_on = ttk.Combobox(
            ar_, textvariable=self.v_arac_on, state="readonly", width=20,
            values=["oto (parça adlarından öneri)", "yok (model eksenleri olduğu gibi)",
                    "-X", "+X", "-Y", "+Y"])
        self.cb_arac_on.pack(side="left")
        self.v_arac_ust = tk.StringVar(value="+Z")
        ttk.Combobox(ar_, textvariable=self.v_arac_ust, state="readonly", width=4,
                     values=["+Z", "-Z", "+Y", "-Y", "+X", "-X"]).pack(side="left", padx=(4, 0))
        # öneri metni (model okununca) kutunun kendisinde ve günlükte durur
        self.v_arac_bilgi = tk.StringVar(value="")

        of = ttk.LabelFrame(f, text=" Örnek resim hangi parçadan üretilsin ", padding=6)
        of.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        self.v_ornek = tk.StringVar()
        self.cb_ornek = ttk.Combobox(of, textvariable=self.v_ornek, state="readonly", width=70)
        self.cb_ornek.pack(side="left")
        ttk.Label(of, foreground="#555", text="  (varsayılan: en çok çeşit delik/radüs taşıyan parça)"
                  ).pack(side="left")
        # --- parça istisnası (ana görünüş elle) + YALNIZ BU PARÇAYI yeniden
        # üret: ÖRNEK düğmesiyle aynı satırda (küçük ekranda sayfa taşmasın)
        # kendi satırında ve ÜÇ sütuna yayılı: iki sütuna sıkışınca 1280 px
        # ekranda Kesit kutusu 24 px'e düşüyor, radyo düğmeleri kayboluyordu
        pf_ = ttk.Frame(f); pf_.grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Label(pf_, text="İstisna – parça:").pack(side="left")
        self.v_ist_parca = tk.StringVar()
        self.cb_ist = ttk.Combobox(pf_, textvariable=self.v_ist_parca, state="readonly", width=34)
        self.cb_ist.pack(side="left", padx=(4, 6))
        self.cb_ist.bind("<<ComboboxSelected>>", lambda e: self._istisna_goster())
        ttk.Label(pf_, text="ana görünüş:").pack(side="left")
        self.v_ist_gor = tk.StringVar(value="OTOMATİK")
        ttk.Combobox(pf_, textvariable=self.v_ist_gor, state="readonly", width=9,
                     values=["OTOMATİK", "ÖN", "ARKA", "SAĞ", "SOL", "ÜST", "ALT"]
                     ).pack(side="left", padx=(4, 4))
        ttk.Button(pf_, text="Kaydet", width=7, command=self.istisna_kaydet).pack(side="left")
        ttk.Button(pf_, text="YALNIZ BU PARÇA (DXF + PDF)  ▸",
                   command=self.tek_parca_uret).pack(side="left", padx=(6, 0))
        # PARÇA BAZLI İSTEK (kullanıcı: "görselleri, detayları, kesit sayısını
        # özellik şeklinde isteyebilirim; komple değil, seçtiğim parça"):
        # görünüş listesi (boş = otomatik), kesit ve perspektif bu parça için.
        pf2_ = ttk.Frame(f); pf2_.grid(row=5, column=0, columnspan=3, sticky="w", pady=(0, 2))
        ttk.Label(pf2_, text="   bu parça için görünüşler:").pack(side="left")
        self.v_ist_v = {}
        for k, ad in (("ON", "ÖN"), ("ARKA", "ARKA"), ("SAG", "SAĞ"), ("SOL", "SOL"),
                      ("UST", "ÜST"), ("ALT", "ALT")):
            v = tk.BooleanVar(value=False)
            self.v_ist_v[k] = v
            ttk.Checkbutton(pf2_, text=ad, variable=v).pack(side="left", padx=(2, 0))
        ttk.Label(pf2_, text="(hiçbiri = otomatik)   kesit:").pack(side="left", padx=(6, 0))
        self.v_ist_kesit = tk.StringVar(value="ortak ayar")
        ttk.Combobox(pf2_, textvariable=self.v_ist_kesit, state="readonly", width=10,
                     values=["ortak ayar", "evet", "hayır"]).pack(side="left", padx=(2, 0))
        ttk.Label(pf2_, text="perspektif:").pack(side="left", padx=(6, 0))
        self.v_ist_persp = tk.StringVar(value="ortak ayar")
        ttk.Combobox(pf2_, textvariable=self.v_ist_persp, state="readonly", width=10,
                     values=["ortak ayar", "evet", "hayır"]).pack(side="left", padx=(2, 0))
        self.v_ist_bilgi = tk.StringVar(value="")
        self.b_ornek = ttk.Button(f, text="ÖRNEK DXF ÜRET  ▸", style="Bas.TButton",
                                  command=self.ornek_uret)
        self.b_ornek.grid(row=3, column=2, sticky="e", pady=(6, 2), ipadx=14, ipady=5)
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
        self.tuval.bind("<Double-1>", lambda e: self.onizleme_penceresi())
        af = ttk.Frame(f); af.pack(fill="x")
        ttk.Button(af, text="◂  AYARA DÖN", command=lambda: self.defter.select(2)).pack(side="left")
        ttk.Button(af, text="DXF'i harici programda aç",
                   command=self.ornek_ac).pack(side="left", padx=8)
        ttk.Button(af, text="BÜYÜT  (ayrı pencere, yakınlaştır)",
                   command=self.onizleme_penceresi).pack(side="left")
        ttk.Label(af, foreground="#555", text="resme çift tıklayınca da açılır"
                  ).pack(side="left", padx=8)
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
        uf = ttk.Frame(f); uf.pack(fill="x", pady=(0, 6))
        self.v_eksik = tk.BooleanVar(value=True)
        ttk.Checkbutton(uf, variable=self.v_eksik, text=(
            "Yalnız EKSİK ya da ESKİMİŞ çizimleri üret  (aynı model ve aynı "
            "ayarla üretildiği kayıtlı olanlara dokunulmaz)")
                        ).pack(side="left")
        self.b_tumu = ttk.Button(uf, text="ÇİZİMLERİ ÜRET  ▸", style="Bas.TButton",
                                 command=self.tumunu_uret, state="disabled")
        self.b_tumu.pack(side="right", ipadx=12, ipady=4)
        # Kaynak resimleri AYRI iş: büyük kaynaklı modelde dakikalar sürer;
        # çizimlerin sonuna eklenince program takılmış gibi görünüyordu.
        kf = ttk.Frame(f); kf.pack(fill="x", pady=(0, 6))
        ttk.Label(kf, foreground="#555", text=(
            "Kaynak resimleri: her kaynaklı alt grup için KAYNAK/<grup>_kaynak.pdf "
            "(yalnız PDF). Çok dikişli modelde uzun sürer; ilerleme aşağıda "
            "görünür, İptal ile durdurulabilir.")).pack(side="left")
        self.b_kaynak = ttk.Button(kf, text="KAYNAK RESİMLERİ (PDF)  ▸",
                                   command=self.kaynak_resimleri_uret, state="disabled")
        self.b_kaynak.pack(side="right", ipadx=12, ipady=4)
        af = ttk.Frame(f); af.pack(fill="x")
        self.b_zip = ttk.Button(af, text="ZIP OLUŞTUR", command=self.zip_olustur, state="disabled")
        self.b_zip.pack(side="left")
        ttk.Button(af, text="Klasörü aç", command=self.klasoru_ac).pack(side="left", padx=8)
        ttk.Button(af, text="Listeyi tazele", command=self._cikti_listesi
                   ).pack(side="left")
        # (İptal düğmesi artık ortak durum çubuğunda, her sayfadan
        #  erişilebilir.)

    def _kayar_sayfa(self, f):
        """Sayfayı KAYAR PENCERE yapar (kullanıcı: açınım sayfasında
        listenin altındaki özet ve düğmeler pencerenin altında kalıyordu,
        "kayar pencere o, onu istiyorum"): içerik bir tuvalin içindeki
        çerçeveye kurulur, sağda düşey kaydırma çubuğu; içerik
        pencereden uzunsa fare tekerleği / çubukla kaydırılır, kısaysa
        çubuk görünse de iş yapmaz. Dönen çerçeve sayfanın yerine
        kullanılır."""
        tuval = tk.Canvas(f, highlightthickness=0, borderwidth=0)
        cubuk = ttk.Scrollbar(f, orient="vertical", command=tuval.yview)
        tuval.configure(yscrollcommand=cubuk.set)
        cubuk.pack(side="right", fill="y")
        tuval.pack(side="left", fill="both", expand=True)
        ic = ttk.Frame(tuval)
        kimlik = tuval.create_window((0, 0), window=ic, anchor="nw")

        def _ic_degisti(_e=None):
            tuval.configure(scrollregion=tuval.bbox("all"))

        def _tuval_degisti(e):
            # iç çerçeve tuval kadar geniş; pencere içerikten yüksekse
            # içerik de o yüksekliğe açılır (liste alanı genişler)
            yuk = max(e.height, ic.winfo_reqheight())
            tuval.itemconfigure(kimlik, width=e.width, height=yuk)
            tuval.configure(scrollregion=(0, 0, e.width, yuk))

        def _teker(e):
            if tuval.winfo_height() >= ic.winfo_reqheight():
                return
            adim = -1 if (e.num == 4 or e.delta > 0) else 1
            tuval.yview_scroll(adim, "units")

        ic.bind("<Configure>", _ic_degisti)
        tuval.bind("<Configure>", _tuval_degisti)
        for w in (tuval, ic):
            w.bind("<MouseWheel>", _teker)
            w.bind("<Button-4>", _teker)
            w.bind("<Button-5>", _teker)
        ic.kayar_tuval = tuval
        ic.kayar_teker = _teker
        return ic

    def _kayar_bagla(self, ic):
        """Sayfa kurulduktan sonra: fare tekerleği içerikteki her öğenin
        üstünde de sayfayı kaydırır (Tk'de olay üst çerçeveye çıkmaz).
        Liste (Treeview) kendi kaydırmasını yapar, ona dokunulmaz."""
        for w in self._tum_cocuklar(ic):
            if w.winfo_class() == "Treeview":
                continue
            for olay in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                w.bind(olay, ic.kayar_teker)

    # ------------------------------------------------------------ 6 AÇINIM
    def _sayfa6(self):
        f = self._kayar_sayfa(self.sayfa[5])
        ttk.Label(f, text="Bükümlü sac parçaların açınımı",
                  style="Baslik.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(f, foreground="#555", justify="left", wraplength=900, text=(
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
        self._kayar_bagla(f)

    def _onceki_uretim(self, tur):
        """Bu klasörde AYNI MODELDEN daha önce üretilmiş açınım/lazer
        resimleri: {kod: dosya adı}. Model değiştiyse boş döner - eski
        modelin açınımı 'var' sayılmaz."""
        on = (self.v_out.get() or "").strip()
        if not on:
            return {}
        d = IS.durum_oku(on)
        oz = IS.dosya_ozeti((self.v_step.get() or "").strip())
        return {k: r["dxf"] for k, r in d[tur].items()
                if oz and r.get("step_ozet") == oz
                and IS.dosya_bul(on, r.get("dxf"))}

    def _acilim_doldur(self):
        """Parça listesini açınım sayfasına yazar ve TARAMAYI başlatır."""
        if not hasattr(self, "ac_agac"):
            return
        self.ac_agac.delete(*self.ac_agac.get_children())
        self.ac_satir = {}
        pozlar = self.M.poz_numaralari(self.komp)
        profil = 0
        for i, k in enumerate(self.komp):
            if k.get("sinif") != "parca":
                continue        # standart eleman ve kaynak dikişi sac değil
            if k.get("profil"):
                # Profil (ekstrüzyon, kutu, boru, çekme L/U) sac değildir:
                # açınımı yoktur, PROFIL kesim listesine girer. Taramaya
                # sokulmaz; ince cidarlı ekstrüzyon "bükümlü sac" sanılıp
                # listeye giriyordu (alüminyum ray).
                profil += 1
                continue
            s = self.ac_agac.insert("", "end", values=(
                pozlar[i], k.get("kod", ""), (k.get("ad") or "")[:60],
                "", "", "", "taranıyor…"))
            self.ac_satir[s] = i
        self.b_acilim.configure(state="normal" if self.ac_satir else "disabled")
        if profil:
            self._yaz(f"açınım listesi: {profil} profil parça (ekstrüzyon / kutu / "
                      "boru) listeye alınmadı - açınımı yoktur, PROFIL listesindedir")
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
        # Tarama sonucunu KODA göre de sakla. Aşağıda bükümlü olmayan
        # satırlar listeden siliniyor; 8. adım (lazer) bu sonuçları
        # kullanıyor ve satır anahtarları silinince "taranmadı"
        # sanıyordu - düz sac parçalar tipsiz, sac olmayanlar da
        # gereksiz yere listeye giriyordu.
        for s_, r_ in out.items():
            i_ = getattr(self, "ac_satir", {}).get(s_)
            if i_ is not None:
                self.tarama_kod[self.komp[i_].get("kod")
                                or self.komp[i_].get("ad")] = r_
        sec, duz, degil, var = [], 0, 0, 0
        onceki = self._onceki_uretim("acinim")
        for s, r in out.items():
            if not self.ac_agac.exists(s):
                continue
            if r["tip"] == "bukumlu sac":
                i_ = self.ac_satir.get(s)
                kod_ = (self.komp[i_].get("kod") or self.komp[i_].get("ad")
                        if i_ is not None else None)
                if r["kalinlik_mm"]:
                    self.ac_agac.set(s, "kalinlik", f"{XL.tr(r['kalinlik_mm'])} mm")
                if kod_ in onceki:
                    # Aynı modelden zaten üretilmiş: seçili gelmez, isterseniz
                    # seçip yeniden üretirsiniz.
                    var += 1
                    self.ac_agac.set(s, "durum", "önceden üretildi  –  "
                                     + onceki[kod_])
                    continue
                sec.append(s)
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
        self.b_acilim.configure(state="normal" if (sec or var) else "disabled")
        elendi = (f"  Listeye alınmayan {duz + degil} parça: "
                  f"{duz} düz sac (açınımı kendisidir), "
                  f"{degil} bükümlü sac değil.") if (duz or degil) else ""
        self.v_ac_ozet.set(
            (f"{len(sec) + var} bükümlü sac parça bulundu"
             + (f"; {var} tanesinin açınımı bu modelden önceden üretilmiş "
                "(seçili değil, isterseniz seçip yeniden üretin), "
                f"{len(sec)} tanesi seçili." if var else ", hepsi seçili.")
             if (sec or var) else "Bu montajda bükümlü sac parça bulunamadı.")
            + elendi)
        # Tarama ARKA PLANDA biter, kullanıcı o sırada genellikle 2.
        # adımdadır. Sonucu durum çubuğuna tek başına yazmak 2. adımın
        # yönlendirmesini ("malzemeyi verip BOM ÇIKART deyin") siliyor ve
        # yerine 6. adımın "ÜRET deyin"ini koyuyordu. Yönlendirme kalır,
        # tarama sonucu yanına eklenir; ayrıntısı günlüktedir.
        ozet = (f"6. adım: {len(sec)} bükümlü sac bulundu, seçili"
                if sec else f"bükümlü sac yok ({len(out)} parça tarandı)")
        self._yaz("açınım taraması: " + ozet)
        ipucu = getattr(self, "_durum_ipucu", "")
        self.v_durum.set(f"{ipucu}   ·   {ozet}" if ipucu else ozet)
        self.lazer_doldur()      # 8. adım da taramanın sonucunu kullanır

    def acilim_uret(self):
        if not self._lisans_izin("acinim"):
            return
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
        self._basla("açınım hesaplanıyor…", f"Açınım ({len(kodlar)} parça)")
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
        # Lazer adımı açınımın KONTURUNU yeniden kullanır: aynı parçayı
        # ikinci kez açmak parça başına 15-30 saniye ederdi.
        eski = {r["kod"]: r for r in (getattr(self, "acilim_liste", None) or [])}
        eski.update({r["kod"]: r for r in sonuc})
        self.acilim_liste = list(eski.values())
        for s, i in getattr(self, "ac_satir", {}).items():
            ad = self.komp[i].get("kod") or self.komp[i].get("ad")
            if ad in olan:
                r = olan[ad]
                self.ac_agac.set(s, "kalinlik", f"{XL.tr(r['kalinlik_mm'])} mm")
                self.ac_agac.set(s, "acinim",
                                 f"{XL.tr(r['acinim_genislik_mm'])} x {XL.tr(r['acinim_boy_mm'])}")
                yn = r.get("yontem") or {}
                self.ac_agac.set(s, "yontem", yn.get("yontem", ""))
                d = f"{r['bukum_sayisi']} büküm  –  {r['dxf']}"
                if yn.get("yontem") == "rollform":
                    d = "ABKANTTA YAPILAMAZ  –  " + d
                self.ac_agac.set(s, "durum", d)
            elif ad in neden:
                self.ac_agac.set(s, "durum",
                                 "açınım yok: " + neden[ad].splitlines()[0])
        n_lz = sum(1 for r in sonuc if r.get("kontur_dis"))
        self.v_durum.set(f"açınım: {len(sonuc)} büküm resmi (ACINIM/..._acinim.dxf), "
                         f"{n_lz} lazer kesim (LZR/..._acinim_lzr.dxf), "
                         f"{len(hata)} parça yapılamadı")
        self.lazer_doldur()                # açınımı çıkanlar seçili gelsin
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
            yol = IS.dosya_bul(self.v_out.get().strip(),
                               d.split("–")[-1].strip())
            if yol:
                klasor_ac(yol)

    # ----------------------------------------------------------- 7 PAFTA
    def _sayfa7(self):
        f = self.sayfa[6]
        ttk.Label(f, text="1:1 resimleri standart A3 paftaya yerleştir",
                  style="Baslik.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(f, foreground="#555", justify="left", wraplength=900, text=(
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
        if self.sablon is None:
            # Sessizce yok olmasın: kullanıcı "çizen/tarih neden
            # sorulmuyor" diye takılıyordu. Nereye bakıldığı yazılır.
            ttk.Label(f, foreground="#777", justify="left", wraplength=900,
                      text=("Firma anteti yok – Pi3D antetli pafta çizilecek: "
                            "sağ alt köşede Pi3D / PiVision logolu antet; parça adı, "
                            "resim no, malzeme, kütle, ölçek, sayfa, çizen ve onaylayan "
                            "kendiliğinden dolar (ayar antet_pi3d: 0 ile kutu boş kalır). "
                            + getattr(self, "antet_neden", "") + "\n"
                            "Firma anteti istiyorsanız (tam lisans): Yardım > Firma "
                            "anteti… ile A3 antet DXF'inizi verin; program kutuları "
                            "ölçüp eşler, şablon ayara kaydedilir, sonradan "
                            "değiştirilebilir. Hazır şablon (firma.dxf + firma.json) "
                            "şu klasörlerden de okunur — "
                            + "   |   ".join(getattr(self, "antet_aranan", []))
                            )).pack(anchor="w", pady=(0, 6))
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
        # tarih, çizen, onaylayan: firma anteti ya da Pi3D anteti, ikisinde de
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
            "  antetin çizen / onaylayan kutularına yazılır, "
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

    # ---------------------------------------------------------- 8 LAZER
    def _sayfa8(self):
        f = self.sayfa[7]
        ttk.Label(f, text="Lazer kesim resimleri  (…_Lzr.dxf)",
                  style="Baslik.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Label(f, foreground="#555", justify="left", wraplength=900, text=(
            "Bu resimler OKUNMAK için değil, KESİLMEK için üretilir. "
            "İçinde yalnız kesim konturu vardır: dış kontur ve delikler, "
            "1:1, tek katmanda (KESIM). Büküm çizgisi, büküm tablosu, "
            "ölçü, yazı, çerçeve ve antet YOKTUR — CAM yazılımı "
            "dosyadaki her çizgiyi kesim yolu sayabilir, resmin "
            "üstündeki bir yazı sacın üstüne kesilir. Parçanın kimliği "
            "dosya ADINDADIR.\n"
            "Bu dosyalar PAFTAYA ALINMAZ ve PDF'i BASILMAZ; 7. adımın "
            "listesinde görünmezler.\n"
            "LAZER KESİM BÜTÜN SAC PARÇALAR İÇİNDİR: DÜZ SAC doğrudan "
            "kendi konturundan kesilir; BÜKÜMLÜ SAC açınımının konturundan "
            "kesilir, sonra abkant / preste bükülür (6. adım). Montajdaki "
            "bütün sac parçalar listede SEÇİLİ gelir; sac olmayanlar (freze, "
            "torna, profil) listeye girmez."
                  )).pack(anchor="w", pady=(0, 8))

        orta = ttk.Frame(f); orta.pack(fill="both", expand=True)
        sut = ("poz", "kod", "ad", "tip", "kalinlik", "olcu", "durum")
        basl = {"poz": ("POZ", 50), "kod": ("KOD", 150), "ad": ("AD", 240),
                "tip": ("TİP", 110), "kalinlik": ("SAC KALINLIK", 100),
                "olcu": ("EN x BOY  mm", 130), "durum": ("DURUM", 330)}
        self.lz_agac = ttk.Treeview(orta, columns=sut, show="headings",
                                    selectmode="extended", height=14)
        for c in sut:
            self.lz_agac.heading(c, text=basl[c][0])
            self.lz_agac.column(c, width=basl[c][1],
                                anchor="w" if c in ("kod", "ad", "durum")
                                else "center")
        kd = ttk.Scrollbar(orta, orient="vertical", command=self.lz_agac.yview)
        self.lz_agac.configure(yscrollcommand=kd.set)
        self.lz_agac.pack(side="left", fill="both", expand=True)
        kd.pack(side="right", fill="y")

        self.v_lz_ozet = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.v_lz_ozet, foreground="#555",
                  justify="left").pack(anchor="w", pady=(6, 0))

        alt = ttk.Frame(f); alt.pack(fill="x", pady=(8, 0))
        ttk.Button(alt, text="Listeyi tazele",
                   command=self.lazer_doldur).pack(side="left")
        ttk.Button(alt, text="Tümünü seç",
                   command=lambda: self.lz_agac.selection_set(
                       self.lz_agac.get_children())).pack(side="left", padx=6)
        self.b_lazer = ttk.Button(
            alt, text="SEÇİLİ PARÇALARIN LAZER RESMİNİ ÜRET  ▸",
            style="Bas.TButton", command=self.lazer_uret, state="disabled")
        self.b_lazer.pack(side="right", padx=4, ipadx=10, ipady=3)

    def lazer_doldur(self):
        """BÜTÜN sac parçaları listeler ve SEÇİLİ getirir (kullanıcı:
        "lazer kesim illa bükülecek saclar değil: açınım = bükülecek
        saclar (abkant / pres), düz saclar = lazer kesim düz").

        Üstte açınımı çıkanlar (kontur hazır), sonra bükümlü saclar
        (açınım burada hesaplanır), sonra düz saclar (kendi konturu);
        önceden üretilmişler en altta, seçisiz. Sac olmayanlar listeye
        girmez. Tarama 6. adımda yapıldıysa yeniden yapılmaz; yapılmadıysa
        burada yapılır (parça başına ~20 ms)."""
        if not hasattr(self, "lz_agac") or not self.komp:
            return
        self.lz_agac.delete(*self.lz_agac.get_children())
        self.lz_satir, sec = {}, []
        pozlar = self.M.poz_numaralari(self.komp)
        acilan = {r.get("kod") for r in (getattr(self, "acilim_liste", None)
                                         or [])}
        acilan |= set(self._onceki_uretim("acinim"))
        lz_var = self._onceki_uretim("lazer")
        kod_tip = {a: r["tip"] for a, r in self.tarama_kod.items()}
        sira = []
        for i, k in enumerate(self.komp):
            if k.get("sinif") != "parca" or k.get("profil"):
                continue        # profil: lazer konturu yok (PROFIL listesi)
            ad = k.get("kod") or k.get("ad")
            tip = kod_tip.get(ad)
            if tip is None:
                # 6. adıma uğranmamış: burada tara (sac mı, bükümlü mü)
                try:
                    r_ = self.M.sac_taramasi(self.kayit[k["indeks"][0]][1])
                except Exception:
                    r_ = {"sac": False, "tip": "sac degil"}
                self.tarama_kod[ad] = r_
                tip = r_["tip"]
            if tip == "sac degil":
                continue        # freze / torna / profil: lazer konturu yok
            if ad in lz_var:
                sira.append((3, i, "önceden üretildi  –  " + lz_var[ad], False))
            elif ad in acilan:
                sira.append((0, i, "bükümlü sac – açınımdan (abkant / pres)", True))
            elif tip == "bukumlu sac":
                sira.append((1, i, "bükümlü sac – açınımdan (abkant / pres)", True))
            else:
                sira.append((2, i, "düz sac – lazer kesim düz", True))
        sira.sort(key=lambda t: (t[0], t[1]))
        say = {"b": 0, "d": 0}
        for _, i, tip, secili in sira:
            k = self.komp[i]
            onc = tip.startswith("önceden")
            s = self.lz_agac.insert("", "end", values=(
                pozlar[i], k.get("kod", ""), (k.get("ad") or "")[:55],
                "" if onc else tip, "", "",
                tip if onc else
                ("seçili – üretilecek" if secili else "isterseniz seçin")))
            self.lz_satir[s] = i
            if secili:
                sec.append(s)
                say["b" if tip.startswith("bükümlü") else "d"] += 1
        if sec:
            self.lz_agac.selection_set(sec)
        self.b_lazer.configure(state="normal" if self.lz_satir else "disabled")
        onc_n = len(self.lz_satir) - len(sec)
        self.v_lz_ozet.set(
            f"{len(sec)} sac parça seçili geldi: {say['b']} bükümlü (kontur "
            f"açınımdan, sonra abkant / pres), {say['d']} düz (lazer kesim düz)."
            + (f"  {onc_n} parça önceden üretilmiş, seçisiz." if onc_n else "")
            if sec else
            f"Listede {len(self.lz_satir)} parça var; hepsi önceden üretilmiş."
            if self.lz_satir else "Montajda sac parça bulunamadı.")

    def lazer_uret(self):
        if not self._lisans_izin("lazer"):
            return
        sec = [s for s in self.lz_agac.selection()
               if getattr(self, "lz_satir", {}).get(s) is not None]
        if not sec:
            messagebox.showinfo("Lazer", "Önce listeden parça seçin.")
            return
        on = self.v_out.get().strip()
        if not on:
            messagebox.showwarning("Klasör", "Önce çıktı klasörünü seçin.")
            return
        os.makedirs(on, exist_ok=True)
        try:
            kf = float(self.v_kfaktor.get().replace(",", "."))
        except Exception:
            kf = 0.40
        kodlar = {self.komp[self.lz_satir[s]].get("kod")
                  or self.komp[self.lz_satir[s]].get("ad") for s in sec}
        for s in sec:
            self.lz_agac.set(s, "durum", "hesaplanıyor…")
        self._basla("lazer resimleri hazırlanıyor…",
                    f"Lazer resmi ({len(kodlar)} parça)")
        threading.Thread(target=self._lazer_is,
                         args=(on, kodlar, kf, dict(self.lz_satir)),
                         daemon=True).start()

    def _lazer_is(self, on, kodlar, kf, satirlar):
        try:
            sonuc, hata = self.M.lazer_yaz(
                self.kayit, self.komp, on, kodlar=kodlar, k_faktor=kf,
                acilim=getattr(self, "acilim_liste", None),
                log=self._yaz,
                ilerleme=lambda y, t, ad: self.kuyruk.put(("ilerleme", (y, t))),
                iptal=lambda: self.iptal_istendi)
            self.kuyruk.put(("lazer", (sonuc, hata, satirlar)))
        except Exception:
            self.kuyruk.put(("hata", "Lazer resmi üretilirken hata:\n\n"
                             + traceback.format_exc()))

    def _lazer_geldi(self, sonuc, hata, satirlar):
        self._bitir()
        olan = {r["kod"]: r for r in sonuc}
        neden = dict(hata)
        for s, i in satirlar.items():
            if not self.lz_agac.exists(s):
                continue
            ad = self.komp[i].get("kod") or self.komp[i].get("ad")
            if ad in olan:
                r = olan[ad]
                self.lz_agac.set(s, "kalinlik", f"{XL.tr(r['kalinlik_mm'])} mm")
                self.lz_agac.set(s, "olcu", f"{XL.tr(r['en_mm'])} x {XL.tr(r['boy_mm'])}")
                self.lz_agac.set(s, "durum",
                                 f"{r['delik_adedi']} delik  –  {r['dxf']}")
            elif ad in neden:
                self.lz_agac.set(s, "durum",
                                 "lazer resmi yok: " + neden[ad].splitlines()[0])
        self.v_durum.set(f"lazer: {len(sonuc)} resim üretildi, "
                         f"{len(hata)} parça yapılamadı")
        if sonuc:
            messagebox.showinfo(
                "Lazer", f"{len(sonuc)} lazer resmi LZR klasörüne yazıldı "
                f"(…_Lzr.dxf) ve LAZER.csv.\n\nBu dosyalar paftaya alınmaz, PDF'i "
                "basılmaz: içlerinde yalnız kesim konturu vardır.")
        elif hata:
            messagebox.showwarning(
                "Lazer", "Hiçbir parçanın lazer resmi çıkarılamadı.\n\n"
                + "\n\n".join(f"{a}:\n{m}" for a, m in hata[:3]))

    def _sablon_bul(self):
        """Firma antetini arar: program klasörü, çıktı klasörü, ev.

        Antet ZORUNLU DEĞİLDİR. Bulunmazsa 7. adımda antet kutusu hiç
        görünmez ve Pi3D kendi sade paftasını çizer (sağ alt köşe boş).
        EXE_YAP.bat'ta 2 (logosuz) seçilerek derlenen sürümde antet
        klasörü exe'nin yanına konur."""
        self.antet_aranan = []
        try:
            import pf5_antet as PA
        except Exception as e:
            self.antet_neden = f"pf5_antet yüklenemedi: {e}"
            return None
        # LİSANS KURALI: deneme sürümünde (ya da lisanssız) firma anteti
        # kullanılmaz; her pafta Pi3D / PiVision antetlidir.
        try:
            PA.lisans_durumu(yenile=True)
            if not PA.firma_anteti_izinli():
                self.antet_neden = ("deneme lisansı: her pafta Pi3D / PiVision antetli "
                                    "(firma anteti tam lisansla açılır)")
                return None
            sb = PA.ayarli_sablon()
            if sb is not None:
                self.antet_neden = ""
                self.antet_aranan = [sb.kok + ".dxf"]
                return sb
        except Exception as e:
            self.antet_neden = f"antet ayarı okunamadı: {e}"
        aday = []
        if getattr(sys, "frozen", False):
            # exe'de İKİ yere bakılır ve ÖNCE EXE'NİN YANINA:
            #   dist\Pi3D\antet          kullanıcının koyduğu antet
            #   sys._MEIPASS\antet        derlemeye gömülen antet
            # Böylece anteti değiştirmek için exe'yi yeniden derlemek
            # gerekmez. Eskiden _MEIPASS'in BİR ÜSTÜNE bakılıyordu;
            # gömülü antet orada olmadığı için hiç bulunamıyordu.
            aday.append(os.path.join(
                os.path.dirname(os.path.abspath(sys.executable)), "antet"))
            if getattr(sys, "_MEIPASS", None):
                aday.append(os.path.join(sys._MEIPASS, "antet"))
        else:
            aday.append(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "antet"))
        try:                       # çıktı klasörü henüz seçilmemiş olabilir
            on = (self.v_out.get() or "").strip()
            if on:
                aday.append(os.path.join(on, "antet"))
        except Exception:
            pass
        self.antet_aranan = aday
        try:
            sb = PA.sablon_bul(*aday)
        except Exception as e:
            self.antet_neden = f"antet okunamadı: {e}"
            return None
        if sb is None:
            self.antet_neden = ("antet klasöründe şablon yok "
                                "(<ad>.dxf ve <ad>.json gerekli)")
        return sb

    def _antet_acik(self):
        # getattr: sayfa 7 henüz kurulmamışsa (denetim betikleri sayfayı
        # atlayabiliyor) antet yok sayılır, iş durmaz.
        return (getattr(self, "sablon", None) is not None
                and bool(getattr(self, "v_antet", None)
                         and self.v_antet.get()))

    def _pdf_klasoru(self):
        """Baskılar buraya gider. Paftanın kendisi resmin dosyasındadır,
        ayrı bir pafta klasörü YOKTUR."""
        return IS.alt_klasor(self.v_out.get().strip() or ".", "pdf")

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
        if self.calisiyor:
            # İkinci bir plan işi başlarsa iki sonuç üst üste listeye
            # eklenir (sekmeye geçince kendiliğinden + 'Listeyi tazele').
            self.v_durum.set("bir iş sürüyor – bitince listeyi tazeleyin")
            return
        on = self.v_out.get().strip()
        if not on or not os.path.isdir(on):
            messagebox.showinfo("Pafta", "Önce çıktı klasörünü seçin ve "
                                         "resimleri üretin.")
            return
        # Detay + montaj (DXF/) ve açınım (ACINIM/); eski sürümlerin köke
        # yazdıkları da. ..._Lzr.dxf LAZER KESİM dosyasıdır: içinde yalnız
        # kontur vardır, paftası çıkmaz, PDF'i basılmaz. Listeye alınmaz.
        dosyalar = IS.dosyalar(on, "dxf") + IS.dosyalar(on, "acinim")
        self.pf_agac.delete(*self.pf_agac.get_children())
        self.pf_satir = {}
        if not dosyalar:
            self.b_pafta.configure(state="disabled")
            messagebox.showinfo("Pafta", "Çıktı klasöründe DXF yok (DXF ve "
                                         "ACINIM klasörleri boş). Önce "
                                         "5. ya da 6. adımda resimleri üretin.")
            return
        kagit = self.v_kagit.get()
        self._basla(f"{kagit} yerleşimi hesaplanıyor…",
                    f"Pafta planı ({len(dosyalar)} resim)")
        threading.Thread(target=self._plan_is,
                         args=(dosyalar, kagit,
                               self.sablon if self._antet_acik() else None,
                               self._pdf_klasoru()),
                         daemon=True).start()

    def _plan_is(self, dosyalar, kagit, sablon=None, pk=None):
        try:
            import pf4_pafta as PF
            plan = PF.kagit_plani(dosyalar, kagit, sablon=sablon,
                                  dur=lambda: self.iptal_istendi)
            # Önceki oturumdan kalan pafta ve PDF'ler: pafta yeniden
            # kurulmadan PDF basılabilsin, PDF'i olan belli olsun.
            plan["mevcut"] = {}
            for y in dosyalar if pk else []:
                if self.iptal_istendi:
                    break
                k = PF.mevcut_pafta(y)
                if k:
                    ad = os.path.splitext(os.path.basename(y))[0]
                    pdf = os.path.join(pk, f"{ad}_{k.replace('-', '')}.pdf")
                    taze = (os.path.isfile(pdf)
                            and os.path.getmtime(pdf) >= os.path.getmtime(y))
                    plan["mevcut"][y] = (k, taze)
            self.kuyruk.put(("plan", (plan, kagit)))
        except Exception:
            self.kuyruk.put(("hata", "Yerleşim hesaplanırken hata:\n\n"
                             + traceback.format_exc()))

    def _plan_geldi(self, p, kagit):
        self._bitir()
        import pf4_pafta as PF
        self.pf_agac.delete(*self.pf_agac.get_children())
        self.pf_satir = {}
        for s in p["birebir"] + p["olcekli"]:
            d = "birebir çizilecek"
            if abs(s["olcek"] - 1.0) > 1e-9:
                d = f"{PF.olcek_metni(s['olcek'])} çizilecek"
                di = s.get("daha_iyi")
                if di:
                    d += (f"  ({PF.kagit_adi(di[0])} kâğıtta "
                          f"{PF.olcek_metni(di[1])} olurdu)")
            if 0 < s.get("yazi_mm", 0) < PF.EN_AZ_YAZI_MM:
                d += f"  –  DİKKAT: yazılar kâğıtta {XL.tr(s['yazi_mm'], 1, sade=False)} mm kalıyor"
            i = self.pf_agac.insert("", "end", values=(
                os.path.basename(s["dosya"]), self._resim_tipi(s["dosya"]),
                f"{XL.tr(s['olcu'][0], 0, sade=False)} x {XL.tr(s['olcu'][1], 0, sade=False)}",
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
                f"{XL.tr(s['olcu'][0], 0, sade=False)} x {XL.tr(s['olcu'][1], 0, sade=False)}", kagit, "-",
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
        self.pafta_dosya = {}
        # Paftası zaten kurulu olanlar doğrudan basılabilir.
        mevcut = p.get("mevcut") or {}
        pdf_var = pafta_var = 0
        for i in self.pf_agac.get_children():
            st = self.pf_satir.get(i)
            if not st or st["dosya"] not in mevcut:
                continue
            k, taze = mevcut[st["dosya"]]
            self.pafta_dosya[i] = (st["dosya"], k)
            pafta_var += 1
            pdf_var += taze
            self.pf_agac.set(i, "durum", (
                "PDF'i var (güncel)  –  pafta kurulu, yeniden basılabilir"
                if taze else "pafta kurulu, PDF'i yok  –  doğrudan BAS "
                "diyebilirsiniz") + f"  [{PF.kagit_adi(k)}]")
        self.b_bas.configure(state="normal" if self.pafta_dosya else "disabled")
        n = len(p["birebir"]) + len(p["olcekli"])
        ac = sum(1 for s in p["birebir"] + p["olcekli"]
                 if self._resim_tipi(s["dosya"]) == "açınım")
        self.v_durum.set(f"{kagit}: {n} resim yerleşiyor "
                         f"({ac} açınım, {n - ac} detay/montaj; "
                         f"{len(p['birebir'])} tanesi 1:1), "
                         f"{len(p['sigmayan'])} resim sığmıyor"
                         + (f"  ·  {pafta_var} resmin paftası önceden kurulu "
                            f"({pdf_var} tanesinin PDF'i güncel)"
                            if pafta_var else ""))

    def pafta_uret(self):
        if not self._lisans_izin("pafta"):
            return
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
        if True:                       # firma anteti de Pi3D anteti de aynı kutuları kullanır
            def _kutu(ad):
                """Giriş kutusunun metni; kutu kurulmamışsa boş (sayfa
                kurulmadan çağrılan testler, eski kayıtlar)."""
                try:
                    v = getattr(self, ad).get()
                except Exception:
                    return ""
                return v.strip() if isinstance(v, str) else ""
            ortak = {"cizen": _kutu("v_cizen"), "onaylayan": _kutu("v_onay"),
                     "cizen_tarih": _kutu("v_tarih"), "onay_tarih": _kutu("v_tarih")}
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
        self._basla("pafta hazırlanıyor…", f"Pafta ({len(isler)} resim)")
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
        for sat in (self.satirlar or getattr(self, "bom_kimlik", None) or []):
            if sat.get("dxf") == temel:
                no = sat.get("kod") or kok.split("_", 1)[-1]
                return {"resim_no": no,
                        "resim_adi": (sat.get("ad") or "")
                                     + ("   AÇINIM" if acinim else ""),
                        "antet_ek": {
                            "malzeme": (sat.get("malzeme_ad") or "").split(" (")[0]
                                       if sat.get("malzeme_ad") else "",
                            "kutle": (XL.tr(sat['kg_adet'], 3, sade=False) + " kg"
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
                if self.iptal_istendi:
                    self._yaz("  ! pafta iptal edildi")
                    break
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
                          f"{XL.tr(v['yazi_mm'], 1, sade=False)} mm")
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
        if not self._lisans_izin("pafta"):
            return
        sec = [s for s in self.pf_agac.selection()
               if getattr(self, "pafta_dosya", {}).get(s)]
        if not sec:
            messagebox.showinfo("Baskı", "Önce paftası hazırlanmış "
                                         "satırlardan seçin.")
            return
        self._basla("PDF üretiliyor…", f"PDF basımı ({len(sec)} pafta)")
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
                if self.iptal_istendi:
                    self._yaz("  ! baskı iptal edildi")
                    break
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
        # alt iş düğmeleri yarım saniyede bir tazelenir (girdi değişti mi?)
        self._tazele_sayac = getattr(self, "_tazele_sayac", 0) + 1
        if self._tazele_sayac % 6 == 0 and not getattr(self, "calisiyor", False):
            try:
                self._dugmeleri_tazele()
            except Exception:
                pass
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
                elif tip == "tek_parca":
                    self._tek_parca_geldi(veri)
                elif tip == "tumu":
                    self._tumu_geldi(veri)
                elif tip == "kaynak":
                    self._kaynak_geldi(veri)
                elif tip == "tarama":
                    self._tarama_geldi(veri)
                elif tip == "lazer":
                    self._lazer_geldi(*veri)
                elif tip == "acilim":
                    self._acilim_geldi(*veri)
                elif tip == "plan":
                    self._plan_geldi(*veri)
                elif tip == "pafta":
                    self._pafta_geldi(veri)
                elif tip == "baski":
                    self._baski_geldi(veri)
                elif tip == "ai":
                    self._ai_geldi(veri)
                elif tip == "parca_resmi":
                    self._parca_resmi_geldi(*veri)
                elif tip == "onizleme":
                    self.onizleme_png = veri
                    self._onizleme_ciz()
                elif tip == "hata":
                    self._bitir("hata")
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
                self._bitir("hata")
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

    def _basla(self, durum, islem=None):
        """durum: durum çubuğundaki yazı; islem: süre panelindeki ad."""
        self.calisiyor = True; self.iptal_istendi = False
        self.is_basi = time.time()
        try:
            self.simdi_etiket.configure(fg="#0b2340", bg=self.simdi_etiket.master
                                        .winfo_toplevel().cget("bg"))
        except Exception:
            pass
        self.is_adi = durum
        self.is_islem = islem or durum.rstrip("… .")
        self._sayaci_isle()
        for b in (self.b_incele, self.b_bom, self.b_ornek, self.b_onay,
                  getattr(self, "b_tumu", None), getattr(self, "b_devam", None),
                  getattr(self, "b_kaynak", None)):
            if b is not None:
                b.configure(state="disabled")
        self.b_iptal.configure(state="normal")
        self.v_durum.set(durum)

    # İş bitince bir SONRAKİ adım (işlem adının başına göre)
    SONRAKI = (("Model okuma", "BOM ÇIKAR"),
               ("BOM çıkarma", "örnek resim ya da TÜMÜNÜ ÜRET"),
               ("Örnek resim", "resmi onayla, sonra TÜMÜNÜ ÜRET"),
               ("Tüm çizimler", "açınım / lazer / pafta ya da ZIP"),
               ("Eksik çizimler", "açınım / lazer / pafta ya da ZIP"),
               ("Açınım", "lazer resmi"),
               ("Lazer resmi", "pafta planı"),
               ("Pafta planı", "pafta"),
               ("Pafta", "PDF basımı"),
               ("PDF basımı", "ZIP"),
               ("Kaynak resimleri", "KAYNAK klasörü / ZIP"),
               ("AI malzeme", "BOM'u gözden geçir, TÜMÜNÜ ÜRET"))

    def _bitti_bildir(self, ad, g, sonuc):
        """İş bitti: kullanıcı bir sonraki adıma geçebileceğini AÇIKÇA
        görsün - yeşil TAMAMLANDI (panel + durum çubuğu + günlük + ses).
        Hata / iptal kırmızı / turuncu."""
        sure = IS.sure_metni(g)
        if sonuc == "tamam":
            sonraki = next((n for a, n in self.SONRAKI if ad.startswith(a)), "")
            yazi = (f"✔ TAMAMLANDI: {ad}\n({sure})"
                    + (f"\nsonraki adım: {sonraki}" if sonraki else ""))
            renk, zemin, bas = "#0a6b1f", "#dff3e3", "✔ TAMAMLANDI"
        elif sonuc == "iptal":
            yazi, renk, zemin, bas = (f"■ İPTAL EDİLDİ: {ad}\n({sure})", "#8a4b00",
                                      "#fbeed9", "■ İPTAL EDİLDİ")
        else:
            yazi, renk, zemin, bas = (f"✖ HATA: {ad}\n({sure}) – ayrıntı günlükte",
                                      "#a30f0f", "#f8dede", "✖ HATA")
        self.v_simdi.set(yazi)
        try:
            self.simdi_etiket.configure(fg=renk, bg=zemin)
        except Exception:
            pass
        self._yaz(f"===== {bas}: {ad} ({sure}) =====")
        try:
            self.simdi_etiket.bell()
        except Exception:
            pass

        # durum çubuğunu çağıran iş kendi özetiyle hemen sonra yazar: onun
        # başına eklenir
        def durum():
            if self.calisiyor:
                return
            v = self.v_durum.get()
            if not v.startswith(bas):
                self.v_durum.set(f"{bas} – {v}" if v and v != "hata" else bas)
        self.after(60, durum)

    def _sayaci_isle(self):
        """Çalışan işin yanında geçen süreyi say. Program takıldı mı yoksa
        çalışıyor mu, kullanıcı buradan anlar."""
        if not self.calisiyor:
            return
        g = int(time.time() - getattr(self, "is_basi", time.time()))
        self.v_durum.set(f"{self.is_adi}   ({g // 60}:{g % 60:02d} geçti"
                         + ("  –  uzun sürüyor, İptal ile durdurabilirsiniz)"
                            if g > 90 else ")"))
        # Kalan süre TAHMİN EDİLMEZ, ÖLÇÜLÜR: yapılan iş / geçen süre.
        # İlerleme bilinmiyorsa (STEP okuma) yalnız geçen süre yazar.
        kalan = ""
        try:
            y = float(self.ilerleme["value"]); t = float(self.ilerleme["maximum"])
            if (str(self.ilerleme["mode"]) == "determinate" and 0 < y < t
                    and g >= 5):
                kalan = f"\nkalan ≈ {IS.sure_metni(g * (t - y) / y)}  " \
                        f"({int(y)}/{int(t)})"
        except Exception:
            pass
        self.v_simdi.set(f"ŞU AN: {self.is_islem}\ngeçen {IS.sure_metni(g)}"
                         + kalan)
        self.after(1000, self._sayaci_isle)

    def _bitir(self, sonuc=None):
        if self.calisiyor:
            g = time.time() - getattr(self, "is_basi", time.time())
            self._yaz(f"  ({XL.tr(g, 1, sade=False)} saniye sürdü)")
            sonuc = sonuc or ("iptal" if self.iptal_istendi else "tamam")
            ad = getattr(self, "is_islem", "") or "işlem"
            self._sure_satiri(ad, g, sonuc)
            self.oturum_sure += g
            self._toplam_yaz()
            self._bitti_bildir(ad, g, sonuc)
            # Çıktı klasörü henüz yoksa (ilk iş genelde model okumadır)
            # süre bekletilir, klasör oluşunca yazılır: kaybolmasın.
            self._bekleyen_islem = getattr(self, "_bekleyen_islem", [])
            self._bekleyen_islem.append((ad, g, sonuc))
            on = (self.v_out.get() or "").strip()
            if on and os.path.isdir(on):
                try:
                    for b in self._bekleyen_islem:
                        IS.islem_kaydet(on, *b)
                    self._bekleyen_islem = []
                except Exception:
                    pass
            # YAPILAN İŞİN DÜĞMESİ PASİF KALIR (kullanıcı: "yapılan işin
            # butonu dezaktif olsun, tekrar tekrar basmayayım"): iş aynı
            # girdilerle bitti; girdi (model, malzeme, ayar, seçim)
            # değişince düğme kendiliğinden açılır (_dugmeleri_tazele).
            if sonuc == "tamam":
                anahtar = next((k for a, k in self.IS_ANAHTAR if ad.startswith(a)), None)
                if anahtar:
                    try:
                        self._yapildi[anahtar] = self._girdi_imzasi(anahtar)
                    except Exception:
                        pass
        self.calisiyor = False
        self.ilerleme.stop(); self.ilerleme.configure(mode="determinate")
        self._dugmeleri_tazele()
        self.b_iptal.configure(state="disabled")

    # iş adı (süre panelindeki) -> düğme anahtarı
    IS_ANAHTAR = (("Model okuma", "incele"), ("STEP okun", "incele"), ("BOM çıkarma", "bom"),
                  ("Örnek resim", "ornek"), ("Tüm çizimler", "tumu"), ("Eksik çizimler", "tumu"),
                  ("Kaynak resimleri", "kaynak"), ("Açınım", "acilim"), ("Lazer resmi", "lazer"),
                  ("Pafta (", "pafta"), ("PDF basımı", "bas"))

    def _girdi_imzasi(self, anahtar):
        """Bir düğmenin işini belirleyen GİRDİLERİN imzası: değişince iş
        yeniden yapılabilir (düğme açılır). Ucuz olmalı (yarım saniyede bir
        hesaplanır)."""
        step = (self.v_step.get() or "").strip()
        try:
            mt = os.path.getmtime(step) if step and os.path.isfile(step) else 0
        except OSError:
            mt = 0
        on = (self.v_out.get() or "").strip()
        komp = tuple((k.get("kod"), k.get("ad"), k.get("sinif")) for k in (self.komp or []))
        mal = tuple(sorted((self.malzemeler or {}).items()))

        def ayar():
            try:
                return json.dumps(self._P(), sort_keys=True, default=str)
            except Exception:
                return ""
        kf = self.v_kfaktor.get() if hasattr(self, "v_kfaktor") else ""
        if anahtar == "incele":
            return (step, mt, on)
        if anahtar == "bom":
            return (step, mt, on, komp, mal, self.v_mal.get() if hasattr(self, "v_mal") else "")
        if anahtar == "ornek":
            return (step, mt, on, komp, mal, ayar(),
                    self.cb_ornek.current() if hasattr(self, "cb_ornek") else -1)
        if anahtar == "tumu":
            return (step, mt, on, komp, mal, ayar(),
                    bool(self.v_montaj.get()) if hasattr(self, "v_montaj") else True)
        if anahtar == "kaynak":
            return (step, mt, on, komp)
        if anahtar == "acilim":
            return (step, mt, on, tuple(self.ac_agac.selection()) if hasattr(self, "ac_agac") else (), kf)
        if anahtar == "lazer":
            return (step, mt, on, tuple(self.lz_agac.selection()) if hasattr(self, "lz_agac") else (), kf)
        if anahtar == "pafta":
            return (on, tuple(self.pf_agac.selection()) if hasattr(self, "pf_agac") else (),
                    self.v_kagit.get() if hasattr(self, "v_kagit") else "",
                    bool(self._antet_acik()) if hasattr(self, "_antet_acik") else True)
        if anahtar == "bas":
            return (on, tuple(self.pf_agac.selection()) if hasattr(self, "pf_agac") else (),
                    tuple(sorted(str(v) for v in (self.pafta_dosya or {}).values())) if hasattr(self, "pafta_dosya") else ())
        return ()

    def _yapildi_mi(self, anahtar):
        try:
            return self._yapildi.get(anahtar) is not None and \
                self._yapildi.get(anahtar) == self._girdi_imzasi(anahtar)
        except Exception:
            return False

    def _dugme_durum(self, b, anahtar, kosul):
        """Düğme: ön koşul yoksa pasif; iş aynı girdilerle yapıldıysa pasif
        ve metninde '✓ yapıldı'; yoksa aktif, asıl metni."""
        if b is None:
            return
        if not hasattr(b, "_asil_metin"):
            b._asil_metin = b.cget("text")
        yapildi = bool(kosul) and self._yapildi_mi(anahtar)
        try:
            b.configure(state="normal" if (kosul and not yapildi) else "disabled",
                        text=(b._asil_metin.replace("▸", "").rstrip() + "   ✓ yapıldı") if yapildi
                        else b._asil_metin)
        except Exception:
            pass

    def _dugmeleri_tazele(self):
        """Alt iş düğmelerinin durumu: ön koşul + yapıldı mı (girdi imzası)."""
        if getattr(self, "calisiyor", False):
            return
        if not hasattr(self, "_yapildi"):
            self._yapildi = {}
        # Motor (OpenCascade) yüklenmeden İNCELE açılmaz: yüklenmemişken
        # basılırsa self.M None'dır ve program çöküyordu.
        self._dugme_durum(self.b_incele, "incele", bool(self.v_step.get() and self.M))
        self._dugme_durum(self.b_bom, "bom", bool(self.komp))
        self._dugme_durum(self.b_ornek, "ornek", bool(self.komp))
        self._dugme_durum(self.b_onay, "tumu", bool(self.ornek_dxf))
        self._dugme_durum(getattr(self, "b_tumu", None), "tumu", bool(self.komp))
        self._dugme_durum(getattr(self, "b_kaynak", None), "kaynak",
                          any(k.get("sinif") == "kaynak" for k in (self.komp or [])))
        if hasattr(self, "ac_agac"):
            self._dugme_durum(getattr(self, "b_acilim", None), "acilim", bool(self.ac_agac.selection()))
        if hasattr(self, "lz_agac"):
            self._dugme_durum(getattr(self, "b_lazer", None), "lazer", bool(self.lz_agac.selection()))
        if hasattr(self, "pf_agac"):
            self._dugme_durum(getattr(self, "b_pafta", None), "pafta",
                              bool(self.pf_agac.get_children()) and bool(self.pf_agac.selection()))
            self._dugme_durum(getattr(self, "b_bas", None), "bas",
                              bool(getattr(self, "pafta_dosya", None)) and bool(self.pf_agac.selection()))

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

    # ------------------------------------------------------------ yardım
    def _menu(self):
        """Pencerenin üstündeki Yardım menüsü (F1: kullanım kılavuzu)."""
        try:
            cubuk = tk.Menu(self.master, tearoff=0)
            d = tk.Menu(cubuk, tearoff=0)
            d.add_command(label="Yeni iş  (ekranı sıfırla)", accelerator="Ctrl+N",
                          command=self.yeni_is)
            d.add_separator()
            d.add_command(label="Çıkış", accelerator="Ctrl+Q", command=self.cikis)
            cubuk.add_cascade(label="Dosya", menu=d)
            y = tk.Menu(cubuk, tearoff=0)
            y.add_command(label="Malzemeyi CAD'den al  (adım adım)…",
                          command=self.malzeme_sihirbazi)
            y.add_command(label="Tanınan malzemeler…",
                          command=self.malzeme_listesi_goster)
            y.add_separator()
            y.add_command(label="Kullanım kılavuzu", accelerator="F1",
                          command=self.kilavuz_ac)
            y.add_command(label="Lisans ve makine kimliği…", command=self.lisans_penceresi)
            y.add_command(label="Firma anteti (lisanslı)…", command=self.firma_anteti_penceresi)
            y.add_command(label="Hakkında", command=self.hakkinda)
            cubuk.add_cascade(label="Yardım", menu=y)
            self.master.config(menu=cubuk)
            self.master.bind("<F1>", lambda _e: self.kilavuz_ac())
            self.master.bind("<Control-n>", lambda _e: self.yeni_is())
            self.master.bind("<Control-q>", lambda _e: self.cikis())
            self.master.protocol("WM_DELETE_WINDOW", self.cikis)
        except Exception:
            pass                       # menü olmadan da çalışır

    # ------------------------------------------------------------ yeni iş / çıkış
    # __init__'teki iş durumu: YENİ İŞ bunları sıfırlar, motor (M), lisans
    # ve kalıcı ayarlar (malzeme tablosu, K-faktörü, kâğıt, antet) kalır.
    _IS_DURUMU = dict(kayit=None, komp=None, sablon=None, acilim_liste=list,
                      tarama=dict, tarama_kod=dict, satirlar=list,
                      malzemeler=dict, parca_ayar=dict, arac_oneri=None,
                      ornek_dxf=None, onizleme_png=None, onizleme_resmi=None,
                      _yapildi=dict, calisiyor=False, iptal_istendi=False,
                      ornek_adaylar=list, agac=None, rapor=None,
                      _bekleyen_islem=list, _lisans_pencere=None,
                      _standart_pencere=None, sihirbaz=None)

    def yeni_is(self, sor=True):
        """YENİ İŞ: arayüz kapatılıp açılmadan sıfırlanır (kullanıcı:
        "işlem bittikten sonra sistemi yenileyebilmeliyim, kapatıp açma
        gerekmemeli"). Çalışan iş varsa önce İPTAL istenir. Açık yardımcı
        pencereler kapanır, sekmeler ve listeler ilk açılıştaki gibi
        yeniden kurulur; hesap motoru yeniden yüklenmez (saniyeler
        kazanılır), lisans ve kayıtlı ayarlar aynen kalır. Üretilmiş
        dosyalara dokunulmaz."""
        if getattr(self, "calisiyor", False):
            messagebox.showinfo("Yeni iş", "Bir iş çalışıyor. Önce İPTAL "
                                "deyin, iş durunca YENİ İŞ yapabilirsiniz.")
            return False
        if sor and not messagebox.askyesno(
                "Yeni iş", "Ekran sıfırlansın mı?\n\nSeçili model, listeler ve "
                "bu oturumun süreleri temizlenir; üretilmiş dosyalar, "
                "lisans ve kayıtlı ayarlar (malzeme, K-faktörü, kâğıt, "
                "antet) kalır."):
            return False
        self._yardimci_pencereleri_kapat()
        for ad, deger in self._IS_DURUMU.items():
            setattr(self, ad, deger() if callable(deger) else deger)
        try:
            while True:
                self.kuyruk.get_nowait()
        except queue.Empty:
            pass
        for w in list(self.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
        self._yeniden_kuruluyor = True
        try:
            self._kur()
        finally:
            self._yeniden_kuruluyor = False
        if self.M is not None:
            self._motor_geldi(self.M)
            self.v_durum.set("yeni iş – STEP dosyasını seçin")
        self._yaz("===== YENİ İŞ: ekran sıfırlandı =====")
        return True

    def _yardimci_pencereleri_kapat(self):
        """Ana pencereye bağlı açık Toplevel'ler (lisans, standart parça,
        malzeme sihirbazı, önizleme) kapatılır."""
        try:
            kok = self.master.winfo_toplevel()
            for w in list(kok.winfo_children()):
                if isinstance(w, tk.Toplevel):
                    try:
                        w.destroy()
                    except Exception:
                        pass
        except Exception:
            pass

    def cikis(self):
        """ÇIKIŞ (düğme, Dosya > Çıkış, Ctrl+Q, pencere çarpısı). Çalışan
        iş varsa sorar: yarım kalan iş sonraki açılışta 'eksikleri üret'
        ile tamamlanabilir."""
        if getattr(self, "calisiyor", False):
            if not messagebox.askyesno(
                    "Çıkış", "Bir iş çalışıyor. Yine de çıkılsın mı?\n\n"
                    "Yarım kalan iş sonraki açılışta aynı klasörle "
                    "tamamlanabilir."):
                return False
        try:
            self.master.winfo_toplevel().destroy()
        except Exception:
            try:
                self.master.quit()
            except Exception:
                pass
        return True

    def malzeme_sihirbazi(self):
        if self.M is None:
            messagebox.showinfo("Pi3D", "Hesap motoru henüz yükleniyor; "
                                "günlükte 'motor hazır' yazınca tekrar deneyin.")
            return
        self.sihirbaz = MalzemeSihirbazi(self)

    def malzeme_listesi_goster(self):
        if self.M is None:
            return
        w = tk.Toplevel(self.master)
        w.title("Tanınan malzemeler")
        w.geometry("640x520")
        t = tk.Text(w, wrap="word", font=("Consolas", 10), padx=8, pady=6)
        t.pack(fill="both", expand=True)
        sat = ["Pi3D'nin malzeme tablosu (kütle = hacim x yoğunluk):", ""]
        for k, (ad, r) in self.M.MALZEME.items():
            sat.append(f"  {k:22s} {XL.tr(r, 2, sade=False):>6s} g/cm3   {ad}")
        sat += ["", "Parça listelerinde tanınan adlar (Türkçe, İngilizce, "
                "Almanca, Fransızca), örnek:",
                "  Steel, Stahl, S235, S355, St37, C45, 42CrMo4, AISI 1020, "
                "1.0038, Hardox",
                "  Stainless steel, AISI 304, 1.4301, Inox, rostfrei",
                "  Aluminium, AlMg3, 6060, 6082, 5754",
                "  Brass/Messing, Bronze/CuSn8, Copper/Kupfer, Titanium, "
                "PA6, POM, PE, PP, PVC ...", "",
                "Tanınmayan bir ad YOĞUNLUĞUYLA verilirse (Density / Dichte /",
                "Yoğunluk sütunu), CAD'in yoğunluğuyla ayrı bir malzeme olarak",
                "alınır - çeliğe düşmez."]
        t.insert("1.0", "\n".join(sat))
        t.configure(state="disabled")

    def kilavuz_ac(self):
        for kl in (os.path.dirname(os.path.abspath(sys.argv[0] or ".")),
                   os.path.dirname(os.path.abspath(__file__)),
                   getattr(sys, "_MEIPASS", "")):
            y = os.path.join(kl, "KULLANIM.md") if kl else ""
            if y and os.path.isfile(y):
                klasor_ac(y)
                return
        messagebox.showinfo("Kılavuz", "KULLANIM.md bulunamadı; programın "
                            "klasöründe olmalı.")

    def hakkinda(self):
        surum = ""
        for kl in (os.path.dirname(os.path.abspath(sys.argv[0] or ".")),
                   os.path.dirname(os.path.abspath(__file__)),
                   getattr(sys, "_MEIPASS", "")):
            y = os.path.join(kl, "SURUM.txt") if kl else ""
            if y and os.path.isfile(y):
                try:
                    with open(y, encoding="utf-8") as f:
                        surum = "".join(f.readlines()[:4])
                except Exception:
                    pass
                break
        lis = ("\n\nLisans: " + L.ozet(getattr(self, "lisans", None) or {})) if L is not None else ""
        messagebox.showinfo("Hakkında", f"Pi3D v{IS.PI3D_SURUM}  ({IS.PI3D_SURUM_TARIHI})\n\n"
                            + (surum or BASLIK)
                            + "\n\nPiVision - Industrial Smart Vision System" + lis)

    def _malzeme_listesi_tazele(self):
        """Malzeme kutusunu MALZEME tablosundan yeniden doldurur - CAD'den
        gelen özel malzemeler ("cad:...") de listede görünsün."""
        M = self.M
        adlar = [f"{k} – {t} ({XL.tr(r)} g/cm³)" for k, (t, r) in M.MALZEME.items()]
        self.cb_mal.configure(values=adlar)
        if not self.v_mal.get():
            self.v_mal.set(next(a for a in adlar
                                if a.startswith(M.VARSAYILAN_MALZEME + " ")))

    def _motor_geldi(self, M):
        self.M = M
        self._malzeme_listesi_tazele()
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
                "gorunusler": [],          # OTO: program özelliklere göre seçer
                "perspektif": bool(self.v_perspektif.get()) if hasattr(self, "v_perspektif") else True,
                "kesit": bool(self.v_kesit.get()),
                "arac": self._arac(), "parca_ayar": self._parca_ayar_p()}

    def _arac(self):
        """Araç yönü ayarı: {"on": "-X", "ust": "+Z"} ya da None (model
        eksenleri). 'oto' seçiliyse model okununca çıkan öneri."""
        v = str(getattr(self, "v_arac_on", None) and self.v_arac_on.get() or "oto").strip().lower()
        if v.startswith("oto"):
            o = self.arac_oneri or {}
            return ({"on": o["on"], "ust": o.get("ust", "+Z")}
                    if o.get("on") and o["on"] != "yok" else None)
        if v.startswith("yok"):
            return None
        return {"on": v[:2].upper(),
                "ust": (self.v_arac_ust.get() or "+Z")[:2].upper()}

    _GOR_AD_ANAHTAR = {"ÖN": "ON", "ARKA": "ARKA", "SAĞ": "SAG", "SOL": "SOL",
                       "ÜST": "UST", "ALT": "ALT"}

    def _parca_ayar_p(self):
        """Parça istisnaları motor diline: ana görünüş (ad -> anahtar; adlar
        bakış yönünden, Chevalier s.49), görünüş listesi, kesit, perspektif."""
        out = {}
        for kod, a in (self.parca_ayar or {}).items():
            a = a or {}
            d = {}
            key = self._GOR_AD_ANAHTAR.get(str(a.get("ana_gorunus_ad") or "").upper())
            if key:
                d["ana_gorunus"] = key
            gor = [g for g in (a.get("gorunusler") or []) if g in self._GOR_AD_ANAHTAR.values()]
            if gor:
                d["gorunusler"] = gor
            for ad in ("kesit", "perspektif"):
                if a.get(ad) is not None:
                    d[ad] = bool(a[ad])
            if d:
                out[kod] = d
        return out

    def _istisna_kod(self):
        v = self.v_ist_parca.get() if hasattr(self, "v_ist_parca") else ""
        for k in self.komp or []:
            if k["sinif"] == "parca" and v.endswith("  " + k["kod"] + "  " + k["ad"][:40]):
                return k["kod"]
        return None

    def _istisna_doldur(self):
        """İstisna kutusunu parçalarla doldurur (model okununca)."""
        if not hasattr(self, "cb_ist") or not self.M:
            return
        poz = self.M.poz_numaralari(self.komp or [])
        self.cb_ist.configure(values=[f"{poz[i]}  {k['kod']}  {k['ad'][:40]}"
                                      for i, k in enumerate(self.komp or [])
                                      if k["sinif"] == "parca"])
        self._istisna_goster()

    def _istisna_goster(self):
        kod = self._istisna_kod()
        a = self.parca_ayar.get(kod) if kod else None
        a = a or {}
        if hasattr(self, "v_ist_gor"):
            self.v_ist_gor.set(a.get("ana_gorunus_ad") or "OTOMATİK")
        if hasattr(self, "v_ist_v"):
            for k, v in self.v_ist_v.items():
                v.set(k in (a.get("gorunusler") or []))
            uc = {None: "ortak ayar", True: "evet", False: "hayır"}
            self.v_ist_kesit.set(uc.get(a.get("kesit"), "ortak ayar"))
            self.v_ist_persp.set(uc.get(a.get("perspektif"), "ortak ayar"))
        n = len(self.parca_ayar)
        self.v_ist_bilgi.set(
            (f"{n} parçada istisna: " + ", ".join(
                f"{k} → {self._istisna_ozet(v)}" for k, v in list(self.parca_ayar.items())[:6])
             + (" …" if n > 6 else "")) if n else "istisna yok (hepsi otomatik)")

    @staticmethod
    def _istisna_ozet(a):
        a = a or {}
        par = []
        if a.get("ana_gorunus_ad"):
            par.append("ana " + a["ana_gorunus_ad"])
        if a.get("gorunusler"):
            par.append("+".join(a["gorunusler"]))
        if a.get("kesit") is not None:
            par.append("kesit " + ("evet" if a["kesit"] else "hayır"))
        if a.get("perspektif") is not None:
            par.append("perspektif " + ("evet" if a["perspektif"] else "hayır"))
        return ", ".join(par) or "otomatik"

    def istisna_kaydet(self):
        kod = self._istisna_kod()
        if not kod:
            messagebox.showinfo("İstisna", "Önce listeden parça seçin."); return
        g = self.v_ist_gor.get()
        a = {}
        if g != "OTOMATİK":
            a["ana_gorunus_ad"] = g
        if hasattr(self, "v_ist_v"):
            gor = [k for k, v in self.v_ist_v.items() if v.get()]
            if gor:
                a["gorunusler"] = gor
            uc = {"evet": True, "hayır": False}
            if self.v_ist_kesit.get() in uc:
                a["kesit"] = uc[self.v_ist_kesit.get()]
            if self.v_ist_persp.get() in uc:
                a["perspektif"] = uc[self.v_ist_persp.get()]
        if a:
            self.parca_ayar[kod] = a
        else:
            self.parca_ayar.pop(kod, None)
        on = (self.v_out.get() or "").strip()
        if on:
            try:
                IS.ayar_kaydet(on, parca_ayar=dict(self.parca_ayar))
            except Exception:
                pass
        self._istisna_goster()
        self._yaz(f"istisna: {kod} → {self._istisna_ozet(a)}")

    def tek_parca_uret(self):
        """YALNIZ seçili parçanın detay DXF'i, paftası ve PDF'i yeniden
        üretilir; öbür dosyalara dokunulmaz (kullanıcı: "tekrar sadece o
        parçanın düzeltilmiş şekilde pdf dxf alınabilmesi")."""
        if not self._lisans_izin("pafta"):
            return
        kod = self._istisna_kod()
        if not kod or not self.komp:
            messagebox.showinfo("Tek parça", "Önce listeden parça seçin."); return
        on = (self.v_out.get() or "").strip()
        if not on:
            messagebox.showwarning("Klasör", "Önce çıktı klasörünü seçin."); return
        k = next((x for x in self.komp if x["kod"] == kod and x["sinif"] == "parca"), None)
        if k is None:
            return
        kagit = self.v_kagit.get() if hasattr(self, "v_kagit") else "A3"
        sablon = self.sablon if self._antet_acik() else None

        def _kutu(ad):
            try:
                v = getattr(self, ad).get()
            except Exception:
                return ""
            return v.strip() if isinstance(v, str) else ""
        ortak = {"cizen": _kutu("v_cizen"), "onaylayan": _kutu("v_onay"),
                 "cizen_tarih": _kutu("v_tarih"), "onay_tarih": _kutu("v_tarih")}
        self._basla(f"tek parça üretiliyor: {kod}", f"Tek parça: {kod[:30]}")
        threading.Thread(target=self._tek_parca_is,
                         args=(k, self._is_girdisi(), kagit, sablon, ortak),
                         daemon=True).start()

    def _tek_parca_is(self, k, g, kagit, sablon, ortak):
        try:
            import pf4_pafta as PF
            poz = {r["kod"]: r["poz"] for r in (self.satirlar or getattr(self, "bom_kimlik", None) or [])
                   if r.get("kod")}
            if k["kod"] not in poz:
                pz = self.M.poz_numaralari(self.komp)
                poz = {x["kod"]: pz[i] for i, x in enumerate(self.komp)}
            sonuc = self._calistir(g, asama=(2,), komp=[k], tablo_yok=True, poz_harita=poz)
            ciz = [x for x in sonuc["satirlar"] if str(x.get("dxf", "")).endswith(".dxf")]
            if not ciz:
                raise RuntimeError("detay resmi üretilemedi: "
                                   + "; ".join(str(x.get("dxf")) for x in sonuc["satirlar"]))
            yeni = ciz[0]
            dxf = os.path.join(sonuc["dxf_klasor"], yeni["dxf"])
            # BOM satırını yenisiyle değiştir (malzeme / kütle / dxf adı)
            for i, r in enumerate(self.satirlar or []):
                if r.get("kod") == k["kod"]:
                    self.satirlar[i] = yeni
            self._yaz(f"  {yeni['dxf']} yeniden çizildi")
            kim = self._resim_kimligi(yeni["dxf"])
            antet = dict(ortak, **kim.pop("antet_ek", {}))
            r = PF.pafta_kur(dxf, None, kagit, resim_no=kim.get("resim_no"),
                             resim_adi=kim.get("resim_adi"), sablon=sablon, antet=antet)
            self._yaz(f"  pafta  {r.get('kagit') or kagit} {r['olcek_metni']}")
            klasor = self._pdf_klasoru()
            os.makedirs(klasor, exist_ok=True)
            ad = os.path.splitext(os.path.basename(dxf))[0]
            ek = str(r.get("kagit") or kagit).replace("-", "")
            pdf = PF.bas(dxf, os.path.join(klasor, f"{ad}_{ek}.pdf"))
            self._yaz("  PDF  " + os.path.basename(pdf))
            self.kuyruk.put(("tek_parca", (dxf, pdf)))
        except Exception:
            self.kuyruk.put(("hata", "Tek parça üretilemedi:\n\n"
                             + traceback.format_exc(limit=4)))

    def _tek_parca_geldi(self, veri):
        dxf, pdf = veri
        self._bitir()
        self._agac_doldur()
        self.v_durum.set(f"tek parça hazır: {os.path.basename(dxf)}  +  {os.path.basename(pdf)}")
        messagebox.showinfo("Tek parça", "Yalnız bu parça yeniden üretildi:\n\n"
                            f"{dxf}\n{pdf}\n\nÖbür dosyalara dokunulmadı.")

    def _is_girdisi(self):
        """Tk değişkenlerini ANA İŞ PARÇACIĞINDA okuyup düz veriye çevirir.

        Tk çok iş parçacıklı değildir: arka plandaki iş, StringVar/BooleanVar
        okumaya kalkarsa "main thread is not in main loop" hatası alır.
        Bu yüzden arka plana yalnız buradan çıkan düz sözlük gider."""
        P = self._P()
        on = self.v_out.get().strip()
        if on:
            # Ayarlar çıktı klasörüne yazılır: sonra bu klasör açılınca
            # malzeme ve görünüş seçimi geri gelir, yeniden girilmez.
            try:
                IS.ayar_kaydet(on, malzemeler=dict(self.malzemeler),
                               perspektif=bool(P.get("perspektif", True)),
                               kesit=P["kesit"], gizli=P["gizli"],
                               en_az_delik=P["en_az_delik"],
                               montaj=bool(self.v_montaj.get()),
                               arac_secim=(self.v_arac_on.get() if hasattr(self, "v_arac_on") else None),
                               arac_ust=(self.v_arac_ust.get() if hasattr(self, "v_arac_ust") else None),
                               parca_ayar=dict(self.parca_ayar or {}))
            except Exception as ex:
                self._yaz(f"ayar klasöre yazılamadı: {ex}")
        return {"step": self.v_step.get().strip(), "on": on,
                # genel = yalnız hiç seçim yapılmamış parçalar için varsayılan.
                # Kutudaki malzeme "uygulanacak" malzemedir, herkesin varsayılanı
                # değildir: bir parçaya alüminyum verince diğerleri çelik kalır.
                "P": P, "esl": dict(self.malzemeler),
                "genel": self.M.VARSAYILAN_MALZEME,
                "kesit": bool(self.v_kesit.get()),
                "gorunus_ad": (", ".join(self.M.GORUNUS_AD[x] for x in P["gorunusler"])
                               if P.get("gorunusler") else "otomatik (özelliklere göre)")}

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
            self._onceki_tazele()

    def out_sec(self):
        y = filedialog.askdirectory(title="Kaydedilecek klasör")
        if y:
            self.v_out.set(y)
            self._onceki_tazele()

    def _onceki_tazele(self):
        """1. sayfadaki 'bu klasörde ne var' özetini ve süre panelini
        seçilen çıktı klasörüne göre tazeler."""
        on = (self.v_out.get() or "").strip()
        if not on or not os.path.isdir(on):
            self.v_onceki.set("")
            self._klasor_sureleri()
            return None
        r = IS.cikti_durumu(on, self.v_step.get().strip() or None)
        self.v_onceki.set(IS.durum_metni(r))
        self._klasor_sureleri()
        return r

    def onceki_ac(self, klasor=None):
        """Daha önce çıktı alınmış bir klasörü açar. Modeli OKUMAZ:
        pafta ve PDF hemen yapılabilir, çizim listesi görünür. Eksik
        çizim / açınım / lazer için model gerekir; kayıtlı model
        dosyası bulunursa kutuya yazılır, İNCELE demek yeter."""
        y = klasor or filedialog.askdirectory(title="Önceki çıktı klasörü")
        if not y:
            return
        if not os.path.isdir(y):
            messagebox.showwarning("Klasör", "Klasör bulunamadı:\n" + y)
            return
        self.v_out.set(y)
        d = IS.durum_oku(y)
        if d.get("step") and os.path.isfile(d["step"]) and \
                not self.v_step.get().strip():
            self.v_step.set(d["step"])
            if self.M:
                self.b_incele.configure(state="normal")
        r = self._onceki_tazele()
        if not r or not any((r["bom"], r["dxf"], r["montaj"], r["acinim"],
                             r["lazer"], r["pdf"])):
            messagebox.showinfo(
                "Önceki çıktı", "Bu klasörde önceki bir çalışma bulunamadı "
                "(BOM, DXF, açınım, lazer ya da PDF yok).\n\n" + y)
            return
        self._bom_kimlik_oku()
        # Model gerektirmeyen adımlar hemen açılır.
        self._adim_ac(4, gecis=False)
        self._adim_ac(6, gecis=False)
        self._cikti_listesi()
        self._durum_ipucu = ("önceki çıktı açıldı – pafta/PDF hemen "
                             "yapılabilir; eksik çizim, açınım, lazer için "
                             "İNCELE")
        self.v_durum.set(self._durum_ipucu)
        self._yaz(f"önceki çıktı: {y}")

    def _bom_kimlik_oku(self):
        """BOM.csv'den resim kimlikleri (no, ad, malzeme, kg): model
        okunmadan paftalanan resmin antetine doğru bilgi gitsin."""
        self.bom_kimlik = []
        y = os.path.join((self.v_out.get() or "").strip(), "BOM.csv")
        if not os.path.isfile(y):
            return
        import csv
        try:
            with open(y, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f, delimiter=";"):
                    try:
                        r["kg_adet"] = float(XL.sayi_oku(r.get("kg_adet"))) or None
                    except (TypeError, ValueError):
                        r["kg_adet"] = None
                    self.bom_kimlik.append(r)
        except Exception as ex:
            self._yaz(f"BOM.csv okunamadı: {ex}")

    def klasoru_ac(self):
        y = self.v_out.get()
        if y and os.path.isdir(y):
            klasor_ac(y)
        else:
            messagebox.showinfo("Klasör", "Çıktı klasörü henüz yok.")

    def incele(self):
        if self.M is None:
            messagebox.showinfo("Pi3D", "Hesap motoru henüz yükleniyor "
                                "(ilk açılışta birkaç saniye sürer). "
                                "Günlükte 'motor hazır' yazınca tekrar deneyin.")
            return
        yol = self.v_step.get().strip()
        if not os.path.isfile(yol):
            messagebox.showwarning("Dosya", "Geçerli bir dosya seçin."); return
        if not self._lisans_izin():
            return
        izin, n, lim = L.veri_izni(self.lisans, yol)
        if not izin:
            messagebox.showwarning(
                "Deneme lisansı",
                f"Deneme lisansı {lim} farklı model ile sınırlıdır; {n} model işlendi.\n\n"
                "Daha önce işlenen modeller yeniden açılabilir. Yeni modeller için "
                "tam lisans gerekir: Yardım > Lisans ekranındaki makine kimliğini "
                "PiVision'a gönderin.")
            self.lisans_penceresi()
            return
        if self.lisans.get("tip") == "DENEME":
            self.v_durum.set(f"deneme lisansı: {n} / {lim} model")
        try:
            self.v_durum.set(f"biçim: {self.M.E.bicim_tani(yol)}")
        except self.M.E.OkunamazBicim as ex:
            messagebox.showwarning("Bu biçim okunamıyor", str(ex))
            self.v_durum.set("okunamayan biçim"); return
        if not self.v_out.get():
            self.v_out.set(os.path.splitext(yol)[0] + "_cikti")
        self._basla("STEP okunuyor…",
                    "Model okuma: " + os.path.basename(yol)[:40])
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
        if hasattr(self, "_resim_onbellek"):
            self._resim_onbellek.clear()      # yeni model: eski resimler geçersiz
        self.agac = agac
        self.ornek_dxf = None
        self.malzemeler = {}
        self.parca_ayar = {}
        # araç yönü önerisi: parça adlarından (ÖN / ARKA, SAĞ / SOL)
        try:
            self.arac_oneri = self.M.arac_yonu_oner(kayit, komp)
        except Exception as ex:
            self.arac_oneri = None
            self._yaz(f"araç yönü önerilemedi: {ex}")
        if hasattr(self, "v_arac_bilgi"):
            o = self.arac_oneri or {}
            self.v_arac_bilgi.set(
                (f"öneri: önü {o['on']}, üstü {o.get('ust', '+Z')}  ({o.get('neden', '')})"
                 if o.get("on") and o["on"] != "yok"
                 else f"öneri yok: {o.get('neden', '')} - model eksenleri kullanılır"))
            self._yaz("araç yönü: " + self.v_arac_bilgi.get())
            try:
                oto = (f"oto (öneri: önü {o['on']}, üstü {o.get('ust', '+Z')})"
                       if o.get("on") and o["on"] != "yok" else "oto (öneri yok: model eksenleri)")
                v = self.cb_arac_on.cget("values")
                self.cb_arac_on.configure(values=[oto] + [x for x in v if not str(x).startswith("oto")])
                if str(self.v_arac_on.get()).startswith("oto"):
                    self.v_arac_on.set(oto)
            except Exception:
                pass
        self._istisna_doldur()
        self._bitir()
        self._agac_doldur()
        n = sum(1 for k in komp if k["sinif"] == "parca")
        # malzeme_ata ile AYNI kural: STEP'te ad + yoğunluk varsa ikisi
        # birlikte çözülür (adı tanınmasa da yoğunluğu yeter).
        d = sum(1 for k in komp if k["sinif"] == "parca"
                and self.M.malzeme_ata(k, {}, None)[1] == "data")
        nk = sum(1 for k in komp if k["sinif"] == "kaynak")
        self.v_bom_ozet.set(f"{len(komp) - nk} komponent, {n} parça"
                            + (f" (+{nk} kaynak dikişi, parça sayılmaz)"
                               if nk else "") + " – "
                            f"{d} parçanın malzemesi data'dan okundu, "
                            f"{n - d} parçaya malzeme vermeniz gerekiyor")
        kl = (self.M.kontrol_listesi(komp)
              if hasattr(self.M, "kontrol_listesi") else [])
        if kl:
            self.v_bom_ozet.set(self.v_bom_ozet.get() + f"\n⚠ {len(kl)} parçanın standart "
                                "tanımı belirsiz: BOM'dan önce sorulacak (SINIF sütunu)")
        geri = self._ayar_geri_yukle()
        on = (self.v_out.get() or "").strip()
        if on:
            try:                  # açınım/lazer kaydı hangi modelden bilsin
                IS.model_kaydet(on, self.v_step.get().strip())
            except Exception as ex:
                self._yaz(f"iş durumu yazılamadı: {ex}")
        self._acilim_doldur()
        self.acilim_liste = []
        self.lazer_doldur()
        self._ornek_adaylari()
        self._adim_ac(1)
        # HER ADIM AYRI YAPILABİLİR: model okununca bütün sekmeler açılır.
        # Sıra bir öneridir, zorunluluk değil; BOM'u, görünüşü, çizimleri,
        # açınımı, paftayı, lazeri istediğiniz sırayla, istediğiniz kadar
        # yeniden yapabilirsiniz.
        for i in range(2, len(ADIM)):
            self._adim_ac(i, gecis=False)
        self._bom_kimlik_oku()
        self._cikti_listesi()
        r = self._onceki_tazele()
        self._durum_ipucu = "komponentler hazır – malzemeyi verip BOM ÇIKART deyin"
        if r and (r["bom"] or r["dxf"] or r["acinim"] or r["lazer"]):
            self._durum_ipucu = ("önceki çıktı bulundu – istediğiniz adıma "
                                 "geçin; eksik çizimler için 5. sekme")
        self.v_durum.set(self._durum_ipucu)
        if geri:
            self._yaz("önceki ayarlar geri yüklendi: " + geri)

    def _ayar_geri_yukle(self):
        """Çıktı klasörüne kaydedilmiş malzeme / görünüş / kesit ayarını
        geri getirir. Eksik çizim üretiminde güncel çizimlerin
        ATLANABİLMESİ için ayarın aynı olması gerekir; kullanıcı yeniden
        girmek zorunda kalmasın."""
        on = (self.v_out.get() or "").strip()
        a = IS.durum_oku(on)["ayar"] if on else {}
        if not a:
            return ""
        ne = []
        kodlar = {k["kod"] for k in self.komp or []}
        mal = {k: v for k, v in (a.get("malzemeler") or {}).items()
               if k in kodlar and v in self.M.MALZEME}
        if mal:
            self.malzemeler.update(mal)
            ne.append(f"{len(mal)} parçanın malzemesi")
        # görünüş listesi artık kaydedilmez / okunmaz (seçim otomatik)
        if a.get("perspektif") is not None and hasattr(self, "v_perspektif"):
            self.v_perspektif.set(bool(a.get("perspektif")))
        for ad, v in (("kesit", self.v_kesit), ("gizli", self.v_gizli),
                      ("montaj", self.v_montaj)):
            if ad in a:
                v.set(bool(a[ad]))
        if a.get("en_az_delik") is not None:
            self.v_delik.set(str(a["en_az_delik"]))
        ne.append("kesit / gizli çizgi / delik ayarı")
        if a.get("arac_secim") and hasattr(self, "v_arac_on"):
            self.v_arac_on.set(a["arac_secim"])
            if a.get("arac_ust"):
                self.v_arac_ust.set(a["arac_ust"])
            ne.append("araç yönü")
        pa = a.get("parca_ayar")
        if isinstance(pa, dict) and pa:
            self.parca_ayar = {k: v for k, v in pa.items() if k in kodlar and isinstance(v, dict)}
            if self.parca_ayar:
                ne.append(f"{len(self.parca_ayar)} parça istisnası")
            self._istisna_goster()
        if mal:
            self._agac_doldur()
        return ", ".join(ne)

    def _ornek_adaylari(self):
        """Örnek resim adayları. BOM çıktıysa en çok delik/radüs taşıyan
        önce; çıkmadıysa model sırasıyla parçalar - örnek resim BOM'u
        beklemesin."""
        if self.satirlar:
            p = [r for r in self.satirlar if r["sinif"] == "parca"]
            p.sort(key=lambda r: -(len(r.get("delikler") or [])
                                   + len(r.get("radusler") or [])))
        else:
            poz = self.M.poz_numaralari(self.komp or [])
            p = [{"poz": poz[i], "kod": k["kod"], "ad": k["ad"]}
                 for i, k in enumerate(self.komp or []) if k["sinif"] == "parca"]
        self.ornek_adaylar = p
        self.cb_ornek.configure(values=[f"{r['poz']}  {r['kod']}  {r['ad'][:40]}"
                                        for r in p])
        if p:
            self.v_ornek.set(f"{p[0]['poz']}  {p[0]['kod']}  {p[0]['ad'][:40]}")

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
                if r["sinif"] == "kaynak":
                    continue               # aşağıda tek satırda toplanır
                t = ("std",) if r["sinif"] == "standart" else \
                    ("data",) if r.get("malzeme_kaynak") == "data'dan" else ()
                kg = f"{XL.tr(r['kg_adet'], 3, sade=False)}" if r.get("kg_adet") else "-"
                self.ag.insert("", "end", tags=t,
                               values=(r["poz"], r["kod"][:40], r["ad"][:60], r["adet"],
                                       self._sinif_metni(r["sinif"], r["kod"]),
                                       (r.get("malzeme_ad") or "-")[:28],
                                       r.get("malzeme_kaynak") or "-",
                                       r.get("olcu") or "-", kg))
            self._kaynak_satiri(self.satirlar)
            return
        for i, k in enumerate(self.komp or [], 1):
            if k["sinif"] == "kaynak":
                continue
            if k["sinif"] == "parca":
                m, kay = self._malzeme_onizle(k)
                mal, t = self.M.MALZEME[m][0][:28], ("data",) if kay == "data'dan" else ()
            else:
                mal, kay = "-", "-"
                t = ("std",)
            self.ag.insert("", "end", tags=t,
                           values=(i, k["kod"][:40], k["ad"][:60], k["adet"],
                                   self._sinif_metni(k["sinif"], k["kod"]),
                                   mal, kay, "-", "-"))
        self._kaynak_satiri(self.komp or [])

    def _sinif_metni(self, sinif, kod):
        """SINIF sütunu: sınıf + nereden geldiği (geometri, öneri, adsız)."""
        k = next((x for x in self.komp or [] if x["kod"] == kod), None)
        if not k:
            return sinif
        if k.get("geometri"):
            return f"{sinif} (geometri)"
        if k.get("oneri") and k["oneri"][0] != sinif:
            return f"{sinif} – öneri: {k['oneri'][1] or k['oneri'][0]}?"
        if k.get("aday") and sinif == "parca":
            return "parca – standart olabilir?"
        if k.get("isimsiz") and sinif == "parca":
            return "parca – ADSIZ"
        if k.get("ogrenildi"):
            return f"{sinif} (benzerinden öğrenildi)"
        if k.get("cad_kaynak") and sinif == "standart":
            return "standart (CAD: satın alınan)"
        if k.get("katalog") and sinif == "standart":
            return "standart (katalog)"
        if k.get("profil") and sinif == "parca":
            return f"profil: {k['profil']['ad']}"
        if sinif == "standart" and k.get("tip") and k["tip"] not in ("elle",):
            return f"standart: {k['tip']}"
        return sinif

    def _kaynak_satiri(self, liste):
        """Kaynak dikişleri KOMPONENT DEĞİLDİR: listede tek bir kapalı
        satırda toplanır, altında türüne göre adetleri durur. Eskiden
        her dikiş ayrı satırdı; kaynaklı bir montajda 142 dikiş 142
        parça gibi listeyi dolduruyordu."""
        kyn = [r for r in liste if r["sinif"] == "kaynak"]
        if not kyn:
            return
        oz = self.M.kaynak_ozeti(kyn)
        ust = self.ag.insert("", "end", tags=("kaynak",), open=False, values=(
            "", "", f"KAYNAK DİKİŞLERİ – {len(oz)} tür (parça değil, "
            "BOM'a girmez, çizilmez)", sum(a for _, a in oz), "kaynak",
            "-", "-", "-", "-"))
        for t, a in oz:
            self.ag.insert(ust, "end", tags=("kaynak",),
                           values=("", "", t[:60], a, "kaynak",
                                   "-", "-", "-", "-"))

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
                                       self._sinif_metni(r["tur"], r["kod"])
                                       if r["tur"] in ("parca", "standart")
                                       else r["tur"],
                                       (r["malzeme_ad"] or "-")[:28],
                                       r.get("kaynak") or r.get("malzeme_kaynak") or "-",
                                       r["olcu"] or "-",
                                       XL.tr(r["kg_adet"], 3, sade=False)
                                       if isinstance(r["kg_adet"], (int, float))
                                       and r["kg_adet"] else (r["kg_adet"] or "-")))
                # Kaynak özeti kapalı gelir; açılınca türleri görünür.
                for j, (tur, a) in enumerate(r.get("kaynak_turleri") or []):
                    self.ag.insert(r["poz"], "end", iid=f"{r['poz']}#{j}",
                                   tags=("kaynak",),
                                   values=("", "", tur[:60], a, "kaynak",
                                           "-", "-", "-", "-"))
                if r.get("kaynak_turleri"):
                    self.ag.item(r["poz"], open=False)
            except Exception:
                pass

    # ------------------------------------------------------------ arama
    _ASCII = str.maketrans("ıİIşŞğĞüÜöÖçÇ", "iiissgguuoocc")

    @staticmethod
    def _kucuk(t):
        """Arama için sade yazı: büyük/küçük ve Türkçe harf farkı yok. CAD
        adları çoğu zaman Türkçe harfsizdir (DIK, KOSE); "dik" de "dık"
        da "köşe" de bulsun."""
        return str(t).translate(Uygulama._ASCII).lower()

    def _ara_sifirla(self):
        self._ara_liste, self._ara_i = [], -1
        self.v_ara_sonuc.set("")

    def _tum_satirlar(self, ust=""):
        for i in self.ag.get_children(ust):
            yield i
            yield from self._tum_satirlar(i)

    def ara_bul(self):
        """Arama kutusundaki metnin geçtiği SIRADAKİ satırı seçip gösterir."""
        q = self._kucuk(self.v_ara.get().strip())
        if not q:
            return
        if not self._ara_liste:
            self._ara_liste = [i for i in self._tum_satirlar()
                               if any(q in self._kucuk(v)
                                      for v in (self.ag.item(i, "values") or ())[:3])]
            self._ara_i = -1
        if not self._ara_liste:
            self.v_ara_sonuc.set("bulunamadı")
            return
        self._ara_i = (self._ara_i + 1) % len(self._ara_liste)
        iid = self._ara_liste[self._ara_i]
        self.ag.see(iid)                   # kapalı üst dallar açılır
        self.ag.selection_set(iid)
        self.ag.focus(iid)
        self.v_ara_sonuc.set(f"{self._ara_i + 1} / {len(self._ara_liste)}")

    # ------------------------------------------------------------ parça resmi
    def parca_resmi_goster(self):
        """Seçili satırın parçasını sağdaki küçük pencerede izometrik çizer."""
        if not hasattr(self, "c_parca"):
            return
        sec = self._secili_kompler() if self.komp else []
        c = self.c_parca
        if not sec or not self.kayit:
            c.delete("all")
            sel = self.ag.selection()
            v = self.ag.item(sel[0], "values") if sel else ()
            self.v_parca_ad.set("alt montaj: resim için parçasını seçin"
                                if v and str(v[2]).startswith("▸ ") else
                                "listeden bir satır seçin")
            return
        k = sec[0]
        self.v_parca_ad.set(f"{k['kod'][:50]}\n{k['ad'][:80]}\n"
                            f"{self._sinif_metni(k['sinif'], k['kod'])}")
        anahtar = id(k)
        self._resim_istek = anahtar
        if anahtar in self._resim_onbellek:
            self._parca_resmi_ciz(self._resim_onbellek[anahtar])
            return
        c.delete("all")
        c.create_text(115, 100, text="çiziliyor…", fill="#888")
        sh = self.kayit[k["indeks"][0]][1]
        self._resim_isi_ver(anahtar, sh,
                            lambda a, ken: self.kuyruk.put(("parca_resmi", (a, ken))))

    def _resim_isi_ver(self, anahtar, sh, sonuc_cb):
        """Parça resmi (HLR) istekleri TEK işçi iş parçacığında sırayla
        çizilir: listede hızlı gezinince her satır için ayrı iş parçacığı
        açılıyor, OCC'nin HLR'si yan yana koşunca kat kat yavaşlıyordu
        (BOM arama testinde TABAN resmi 180 sn'de gelmiyordu). İşçi en
        SON isteği çizer, arada yığılanları atlar (zaten gösterilmez);
        sonuç sonuc_cb(anahtar, kenarlar) ile çağırana döner."""
        if not hasattr(self, "_resim_istekler"):
            self._resim_istekler = queue.Queue()
            threading.Thread(target=self._resim_iscisi, daemon=True).start()
        self._resim_istekler.put((anahtar, sh, sonuc_cb))

    def _resim_iscisi(self):
        while True:
            anahtar, sh, cb = self._resim_istekler.get()
            try:
                while True:          # yığılan istekler: yalnız sonuncusu
                    anahtar, sh, cb = self._resim_istekler.get_nowait()
            except queue.Empty:
                pass
            ken = self._parca_resmi_is(sh)
            try:
                cb(anahtar, ken)
            except Exception:
                pass

    def _parca_resmi_is(self, sh):
        try:
            r3 = 1.0 / math.sqrt(3.0)
            r2 = 1.0 / math.sqrt(2.0)
            return self.M.hlr(sh, (r3, -r3, r3), (r2, r2, 0.0), gizli=False)["GORUNEN"]
        except Exception:
            return None

    def _parca_resmi_geldi(self, anahtar, ken):
        self._resim_onbellek[anahtar] = ken
        if anahtar == self._resim_istek:
            self._parca_resmi_ciz(ken)

    def parca_resmi_penceresi(self, kaynak):
        """Küçük parça resmine çift tık: aynı kenarlar ekranın %80'i kadar
        ayrı pencerede, pencere büyüdükçe yeniden çizilir (kullanıcı:
        "sığmayan her durumda pencere yap, mümkün olan yerde genişlet")."""
        ken = getattr(kaynak, "_son_ken", None)
        if not ken:
            return None
        w = tk.Toplevel(self)
        w.title("Parça resmi" + ((" – " + self.v_parca_ad.get().splitlines()[0])
                                 if kaynak is getattr(self, "c_parca", None)
                                 and hasattr(self, "v_parca_ad") else ""))
        try:
            sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
            gw, gh = int(sw * 0.8), int(sh * 0.8)
            w.geometry(f"{gw}x{gh}+{(sw - gw) // 2}+{(sh - gh) // 3}")
        except Exception:
            pass
        c = tk.Canvas(w, bg="white", highlightthickness=0)
        c.pack(fill="both", expand=True)
        c._son_ken = ken
        self._tuval_yeniden_ciz(c)
        w.bind("<Escape>", lambda e: w.destroy())
        self._parca_resmi_pencere = {"w": w, "c": c}
        return w

    def _tuval_yeniden_ciz(self, c):
        """Tuvalin boyutu değişince son resim yeni boyuta göre yeniden
        çizilir (resim hep görünen alana sığar)."""
        def degisti(e):
            son = getattr(c, "_son_ken", None)
            if son is None:
                return
            if (e.width, e.height) != getattr(c, "_son_boy", None):
                c._son_boy = (e.width, e.height)
                self._parca_resmi_ciz(son, c)
        c.bind("<Configure>", degisti)

    def _parca_resmi_ciz(self, ken, c=None):
        c = c or self.c_parca
        c.delete("all")
        c._son_ken = ken
        # görünen boyut; henüz yerleşmediyse ayarlanan boyut
        W = c.winfo_width() if c.winfo_width() > 10 else int(c["width"])
        H = c.winfo_height() if c.winfo_height() > 10 else int(c["height"])
        pay = 10
        if not ken:
            c.create_text(W / 2, H / 2, text="resim çıkarılamadı", fill="#888")
            return
        xs = [p[0] for q in ken for p in q]
        ys = [p[1] for q in ken for p in q]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        o = min((W - 2 * pay) / max(x1 - x0, 1e-6), (H - 2 * pay) / max(y1 - y0, 1e-6))
        dx = (W - (x1 - x0) * o) / 2
        dy = (H - (y1 - y0) * o) / 2
        for q in ken:
            c.create_line(*[v for p in q for v in (dx + (p[0] - x0) * o,
                                                   H - dy - (p[1] - y0) * o)],
                          fill="#222")

    def _secili_kompler(self):
        """Ağaçta seçili satırların komponentleri (düz ya da kademeli)."""
        kodlu = {}
        for k in self.komp or []:
            for a in (k["kod"][:40], k["ad"][:60]):
                if a:
                    kodlu.setdefault(a, []).append(k)
        out = []
        for s in self.ag.selection():
            v = self.ag.item(s, "values")
            if not v or str(v[2]).startswith(("KAYNAK DİKİŞLERİ", "▸ ")):
                continue            # özet satırı ya da montaj
            if v[4] == "kaynak" and not v[1]:
                # kaynak türü satırı: o türdeki bütün dikişler
                bul = [k for k in self.komp if k["sinif"] == "kaynak"
                       and self.M.kaynak_tipi(k["ad"])[:60] == v[2]]
            else:
                bul = kodlu.get(v[1], []) if v[1] else kodlu.get(v[2], [])
            for k in bul:
                if all(k is not x for x in out):
                    out.append(k)
        return out

    def sinif_degistir(self, yeni):
        """Seçilen komponentlerin sınıfını elle değiştirir ve kuralı
        SAKLAR: aynı adlı parça bundan sonra her modelde böyle sınıflanır."""
        if not self.komp:
            return
        sec = self._secili_kompler()
        if not sec:
            messagebox.showinfo("Sınıf", "Önce listeden satır seçin.\n\n"
                                "Kaynak dikişleri tek satırda toplandığı "
                                "için onları 'Üretim parçası' yapmak "
                                "isterseniz ağacı açıp alt satırdan seçin.")
            return
        ad = {"parca": "üretim parçası", "standart": "standart / satın alınan",
              "kaynak": "kaynak dikişi"}[yeni]
        benzer = self._sinif_uygula(sec, yeni)
        # Sınıf değişince BOM, poz ve dosya adları değişir: eski BOM
        # geçersizdir, yeniden çıkarılmalı.
        self.satirlar = []
        self._agac_doldur()
        self._acilim_doldur()
        self._ornek_adaylari()
        self._bitir()
        self._yaz(f"{len(sec)} komponent '{ad}' yapıldı (kural saklandı): "
                  + ", ".join(k["ad"][:30] for k in sec[:5])
                  + (f"; biçimce benzer {benzer} komponent de değişti" if benzer else ""))
        self.v_bom_ozet.set(f"{len(sec)} komponent '{ad}' yapıldı – "
                            "BOM'u yeniden çıkarın")

    def _sinif_uygula(self, sec, yeni, tip=None):
        """Sınıfı değiştirir ve kuralı saklar (ad + biçim imzası); biçimce
        benzer adsız / numaralı parçalar da değişir. Benzer sayısını döner."""
        kural = dict(self.M.ayar_oku().get("sinif_kurali") or {})
        for k in sec:
            k["sinif"] = yeni
            k["tip"] = tip if tip is not None else ("elle" if yeni == "standart" else "")
            kural[self.M.kural_anahtari(k["ad"], k)] = yeni
            # Öğrenme: parçanın BİÇİMİ de saklanır; adı bilgi taşımayan
            # benzerleri (başka ölçüdeki aynı aile) bundan sonra kendiliğinden
            # aynı sınıfa geçer.
            try:
                im = k.get("imza") or self.M.TN.bicim_imzasi(
                    self.kayit[k["indeks"][0]][1])
                if im:
                    k["imza"] = im
                    kural[self.M.sekil_anahtari(im)] = yeni
            except Exception:
                pass
            for a in ("geometri", "oneri", "isimsiz", "aday"):
                k.pop(a, None)
        self.M.ayar_yaz(sinif_kurali=kural)
        try:
            return self.M.benzerden_sinifla(self.kayit, self.komp, kural, self._yaz)
        except Exception:
            return 0

    # ------------------------------------------------ AI malzeme tanımlama
    def ai_sor(self):
        """Programın tanımlamasını AI'a KONTROL ETTİRİR (pf10_ai): önce
        yazıyla bütün parçalar, emin olunamayanlar resimle. Sonuç
        öneridir; kullanıcı onaylayınca uygulanır ve öğrenilir."""
        if not self._lisans_izin("ai"):
            return
        if not (self.M and self.komp):
            messagebox.showinfo("AI", "Önce modeli inceleyin."); return
        import pf10_ai as AI
        parcalar, baglam, oncelik = self.M.ai_girdisi(self.komp)
        if not parcalar:
            messagebox.showinfo("AI", "Kontrol edilecek parça yok (hepsi elle ya da "
                                "CAD'den kesin)."); return
        if not AI.hazir_mi():
            messagebox.showerror("AI", "AI için 'anthropic' paketi kurulu değil.\n\n"
                                 "Komut satırında:  pip install anthropic"); return
        ayar = self.M.ayar_oku()
        model = ayar.get("ai_model") or AI.MODEL
        anahtar = os.environ.get("ANTHROPIC_API_KEY") or ayar.get("ai_anahtar")
        if not anahtar:
            from tkinter import simpledialog
            anahtar = simpledialog.askstring(
                "AI anahtarı", "Anthropic API anahtarı (console.anthropic.com):\n"
                "Bu bilgisayardaki Pi3D ayar dosyasına saklanır.", show="*",
                parent=self)
            if not anahtar:
                return
            self.M.ayar_yaz(ai_anahtar=anahtar.strip())
        # kaba tahmin: ~3 karakter / token, parça başına ~70 çıktı token,
        # resim başına ~450 token (768x384); 1. turda emin olunamayanlar
        # için ayrıca %30 pay
        yazi = len(json.dumps(parcalar, ensure_ascii=False)) / 3.0 + 1200
        resim = int(len(oncelik) + 0.3 * len(parcalar))
        tahmin = AI.maliyet({"girdi": yazi + resim * 550, "cikti": 70 * (len(parcalar) + resim)
                             + 3000}, model)
        if not messagebox.askyesno(
                "AI ile kontrol",
                f"Program {len(parcalar)} parçayı tanımladı; AI bunları kontrol edecek.\n"
                f"Emin olamadıkları ve programın belirsiz bulduğu {len(oncelik)} parça "
                "için parçanın RESMİ de gönderilir.\n\n"
                "Gönderilen: ad, kod, adet, ölçü, programın bulguları, resim. "
                "CAD dosyası GÖNDERİLMEZ. Veri Anthropic'e gider: firmanızın izni "
                "olmalı.\n\n"
                f"Model: {model}\nTahmini maliyet: ≈ ${XL.tr(tahmin, 2, sade=False)} (işlem sonunda "
                "gerçek tutar günlüğe yazılır)\n\nDevam edilsin mi?"):
            return
        self._basla("AI kontrol ediyor…", "AI malzeme tanımlama")
        threading.Thread(target=self._ai_is,
                         args=(parcalar, baglam, oncelik, anahtar.strip(), model),
                         daemon=True).start()

    def _ai_is(self, parcalar, baglam, oncelik, anahtar, model):
        import pf10_ai as AI
        try:
            katalog = []
            try:
                import pf12_katalog as KT
                kl = self.M.katalog_klasoru()
                if kl:
                    katalog = KT.paftalar(kl, log=self._yaz)
                    self._yaz(f"standart ürün kataloğu: {len(katalog)} pafta referans olarak "
                              "gönderilecek")
            except Exception as ex:
                self._yaz(f"! katalog resimleri okunamadı: {ex}")
            sonuc, sayac = AI.kontrol_et(
                parcalar, baglam, goruntu=self.M.ai_goruntu(self.kayit, self.komp),
                oncelik=oncelik, anahtar=anahtar, model=model, log=self._yaz,
                katalog=katalog)
            self.kuyruk.put(("ai", (sonuc, sayac)))
        except AI.AIHatasi as ex:
            self.kuyruk.put(("hata", f"AI malzeme tanımlama:\n\n{ex}"))
        except Exception as ex:
            self.kuyruk.put(("hata", f"AI malzeme tanımlama:\n\n{type(ex).__name__}: {ex}"))

    def _ai_geldi(self, veri):
        import pf10_ai as AI
        sonuc, sayac = veri
        self._bitir()
        self.M.ai_isle(self.komp, sonuc)
        kontrol = {id(k) for k in self.M._kontrol_komp(self.komp)}
        # Düzeltme: AI emin (>= %80) ve sınıf farklı. Doğrulama: programın
        # belirsiz bulduğu parçada AI aynı sınıfı emin söylüyor.
        duzelt = [(self.komp[no], r) for no, r in sorted(sonuc.items())
                  if r["karar"] == "duzelt" and r["guven"] >= AI.EMIN
                  and r["sinif"] != self.komp[no]["sinif"]]
        dogrula = [(self.komp[no], r) for no, r in sorted(sonuc.items())
                   if id(self.komp[no]) in kontrol and r["karar"] == "dogru"
                   and r["guven"] >= AI.EMIN and r["sinif"] == self.komp[no]["sinif"]]
        belirsiz = [no for no, r in sonuc.items()
                    if r["karar"] == "belirsiz" or r["guven"] < AI.EMIN]
        self._agac_doldur()
        ozet = (f"AI: {len(sonuc)} parça kontrol edildi — {len(duzelt)} düzeltme önerisi, "
                f"{len(dogrula)} belirsiz parça doğrulandı, {len(belirsiz)} emin değil; "
                f"maliyet ≈ ${XL.tr(sayac['usd'], 2, sade=False)}")
        self._yaz(ozet)
        if not (duzelt or dogrula):
            messagebox.showinfo("AI", ozet + "\n\nUygulanacak öneri yok.")
            return
        satir = "\n".join(f"  • {k['ad'][:26]} x{k['adet']}: {k['sinif']} → {r['sinif']}"
                          + (f" ({r['tip']})" if r["tip"] else "")
                          + f" %{XL.tr(100 * r['guven'], 0, sade=False)}"
                          + (" [resimle]" if r.get("goruntu") else "")
                          for k, r in duzelt[:10])
        if not messagebox.askyesno(
                "AI önerileri",
                ozet + "\n\n"
                + (f"DÜZELTME ({len(duzelt)}):\n{satir}"
                   + ("\n  ..." if len(duzelt) > 10 else "") + "\n\n" if duzelt else "")
                + (f"Programın belirsiz bulup AI'ın doğruladığı: {len(dogrula)} parça\n"
                   if dogrula else "")
                + "\nUygulansın mı? (Evet: uygulanır ve program ÖĞRENİR; emin "
                  "olunmayanlar STANDART_KONTROL.xlsx'te kalır)"):
            return
        benzer = 0
        for k, r in duzelt + dogrula:
            benzer += self._sinif_uygula(
                [k], r["sinif"], tip=(r["tip"] + " (AI)") if r["sinif"] == "standart" else "")
        self.satirlar = []
        self._agac_doldur()
        self._acilim_doldur()
        self._ornek_adaylari()
        self._yaz(f"AI önerileri uygulandı: {len(duzelt) + len(dogrula)} parça"
                  + (f", biçimce benzer {benzer} parça da" if benzer else ""))
        self.v_bom_ozet.set("AI önerileri uygulandı – BOM'u yeniden çıkarın")

    def _malzeme_satirlari_guncelle(self, kodlar=None):
        """Malzeme değişince hesaplanmış BOM satırları YERİNDE güncellenir:
        malzeme adı, kaynağı, kg/adet, toplam kg (kütle = hacim x yoğunluk,
        hacim satırda zaten var). Ekrandaki liste, pafta anteti (malzeme /
        kütle), açınım ve kaynak adımları BOM yeniden çıkarılmadan da yeni
        malzemeyi görür; BOM.csv / .xlsx de yeniden yazılır. Eskiden satırlar
        siliniyor, ekran "varsayılan"a dönüyor, dosya eski kalıyordu."""
        if not (self.M and self.satirlar):
            return 0
        M, n = self.M, 0
        for r in self.satirlar:
            if r.get("sinif") != "parca":
                continue
            if kodlar is not None and r.get("kod") not in kodlar:
                continue
            k = next((x for x in self.komp or [] if x["kod"] == r.get("kod")), None)
            if k is None:
                continue
            m, kay = M.malzeme_ata(k, self.malzemeler, M.VARSAYILAN_MALZEME)
            if r.get("malzeme") == m:
                continue
            yog = M.yogunluk_kg_mm3(m)
            r["malzeme"], r["malzeme_ad"] = m, M.MALZEME[m][0]
            r["yogunluk_g_cm3"] = round(yog * 1e6, 3)
            r["malzeme_kaynak"] = {"data": "data'dan", "secim": "secim",
                                   "genel": "varsayilan"}[kay]
            v = r.get("hacim_mm3") or 0.0
            if v:
                r["kutle_kg"] = r["kg_adet"] = round(v * yog, 4)
                r["toplam_kg"] = round(v * yog * (r.get("adet") or 1), 4)
            n += 1
        on = (self.v_out.get() or "").strip()
        if n and on and os.path.isdir(on):
            try:
                bom = [r for r in self.satirlar if r["sinif"] != "kaynak"]
                M.bom_yaz(on, bom, self.satirlar)
                self._yaz(f"BOM.csv / BOM.xlsx yeniden yazıldı ({n} parçanın malzemesi değişti)")
            except Exception as ex:
                self._yaz(f"! BOM yeniden yazılamadı: {ex}")
        return n

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
        self._malzeme_satirlari_guncelle()
        self._agac_doldur()
        self._yaz(f"malzeme '{m}' {n} parçaya uygulandı")

    def malzeme_dosya(self):
        if not (self.M and self.komp):
            return
        y = filedialog.askopenfilename(
            title="Malzeme listesi  (kendi şablonumuz ya da CAD'in parça listesi)",
            filetypes=[("Malzeme listesi", "*.csv *.txt *.tsv *.xlsx *.xls *.htm *.html *.json"),
                       ("Tümü", "*.*")])
        if not y:
            return
        # CATIA'nın bölümlü Bill of Material kaydı: eşleştirme + malzeme
        try:
            if self.M.catia_bom_oku(y) is not None:
                self.catia_bom_esle(y)
                return
        except Exception:
            pass
        # CAD'in Made/Bought sütunu varsa (CATIA makrosu ya da doldurulmuş
        # STANDART_KONTROL.xlsx) sınıf da buradan alınır: tasarımcının
        # bilgisi tahminden doğrudur. Malzeme sütunu olmayan dosya yalnız
        # sınıf için okunur.
        try:
            harita = self.M.cad_kaynagi_oku(y)
        except Exception:
            harita = {}
        malzemeli = self.M.malzeme_sutunu_var(y)
        if not malzemeli and not harita:
            bas = self.M.tablo_basliklari(y)
            messagebox.showwarning(
                "Malzeme sütunu yok",
                f"{os.path.basename(y)} okundu ama içinde MALZEME sütunu yok"
                + (f".\nBulunan sütunlar: {', '.join(bas[:8])}" if bas else ".")
                + "\n\nCATIA'da: Analyze ▸ Bill of Material ▸ Define formats ▸ "
                "'Hidden Properties' listesinden Material'i (ve Source'u) seçip "
                "'>' ile görünür tarafa alın ▸ OK ▸ Save As ▸ Excel.\n\n"
                "Ayrıntı: Yardım ▸ Malzemeyi CAD'den al (adım adım).")
            self._yaz(f"! {os.path.basename(y)}: malzeme sütunu yok"
                      + (f" (sütunlar: {', '.join(bas[:8])})" if bas else ""))
            return
        if harita and not malzemeli:
            esl, bilinmeyen = {}, []
        else:
            try:
                esl, bilinmeyen = self.M.malzeme_dosya_oku(y)
            except Exception as ex:
                messagebox.showerror("Malzeme dosyası", str(ex)); return
        try:
            degisen = self.M.cad_kaynagiyla_sinifla(self.komp, harita, log=self._yaz)
        except Exception:
            degisen = 0
        if degisen:
            self._agac_doldur()
        if degisen:
            self._acilim_doldur()
            self._ornek_adaylari()
        n = 0
        for k in self.komp:
            if k["sinif"] != "parca":
                continue
            m, kay = self.M.malzeme_ata(k, esl, "", data_oncelik=False)
            if kay == "secim" and m:
                self.malzemeler[k["kod"]] = m
                n += 1
        self._malzeme_satirlari_guncelle()
        self._agac_doldur()
        self._malzeme_listesi_tazele()
        self._yaz(f"{os.path.basename(y)}: {len(esl)} kayıt okundu, {n} parça eşleşti")
        if bilinmeyen:
            self._yaz("! tanınmayan malzeme adı: " + ", ".join(bilinmeyen[:8]))
            messagebox.showwarning(
                "Tanınmayan malzeme",
                "Dosyadaki şu malzeme adları tanınmadı ve dosyada yoğunlukları "
                "da yok; bu parçalar varsayılan malzemede kalır:\n\n"
                + "\n".join(bilinmeyen[:15])
                + "\n\nÇözüm: dosyaya bir YOĞUNLUK sütunu ekleyin (ör. 7850 "
                "kg/m3 ya da 7,85 g/cm3) ya da adı tanınan bir adla değiştirin. "
                "Adım adım: Yardım > Malzemeyi CAD'den al.")

    def catia_bom_esle(self, yol=None):
        """CATIA Analyze > Bill of Material kaydını STEP BOM'uyla eşleştirir:
        her parça için CATIA adedi / STEP adedi / durum; BOM_ESLESTIRME
        dosyaları çıktı klasörüne; Material sütunu varsa malzeme de alınır."""
        if not self._lisans_izin("catia_bom"):
            return
        if not (self.M and self.komp):
            messagebox.showinfo("CATIA BOM", "Önce STEP inceleyin (Adım 1)."); return
        y = yol or filedialog.askopenfilename(
            title="CATIA Bill of Material kaydı  (Analyze ▸ Bill of Material ▸ Save As)",
            filetypes=[("CATIA BOM", "*.xls *.xlsx *.txt *.htm *.html *.csv"), ("Tümü", "*.*")])
        if not y:
            return
        cb = self.M.catia_bom_oku(y)
        if cb is None:
            messagebox.showwarning(
                "CATIA BOM", f"{os.path.basename(y)} CATIA'nın bölümlü Bill of Material "
                "kaydı değil ('Bill of Material:' bölümleri yok).\n\nCATIA'da: Analyze ▸ "
                "Bill of Material ▸ Save As ▸ Excel ya da Text. Düz malzeme listesi için "
                "'Malzeme listesi yükle' düğmesini kullanın.")
            return
        BE = self.M.BE
        s = BE.bom_eslestir(self.komp, cb)
        on = (self.v_out.get() or "").strip()
        yazildi = ""
        if on:
            try:
                BE.eslestirme_yaz(on, s, cb, XL)
                yazildi = os.path.join(on, "BOM_ESLESTIRME.xlsx")
            except Exception as ex:
                self._yaz(f"! BOM_ESLESTIRME yazılamadı: {ex}")
        for sat in BE.ozet_metni(s, cb).splitlines():
            self._yaz("CATIA BOM: " + sat)
        # malzeme: Material sütunu (ya da TraceParts malzeme grubu) varsa
        n = 0
        if s["esl"]:
            esl = {k: self.M.malzeme_yogunluklu(m, None) for k, m in s["esl"].items()}
            esl = {k: v for k, v in esl.items() if v}
            for k in self.komp:
                if k["sinif"] != "parca":
                    continue
                m, kay = self.M.malzeme_ata(k, esl, "", data_oncelik=False)
                if kay == "secim" and m:
                    self.malzemeler[k["kod"]] = m
                    n += 1
            if n:
                self._malzeme_satirlari_guncelle()
                self._agac_doldur()
                self._malzeme_listesi_tazele()
                self._yaz(f"CATIA BOM: {n} parçanın malzemesi CATIA'dan alındı")
        try:
            harita = BE.catia_kaynak_haritasi(cb)
            if harita and self.M.cad_kaynagiyla_sinifla(self.komp, harita, log=self._yaz):
                self._agac_doldur(); self._acilim_doldur(); self._ornek_adaylari()
        except Exception:
            pass
        self._catia_bom_pencere(s, cb, yazildi, n)

    def _catia_bom_pencere(self, s, cb, yazildi, n_mal):
        w = tk.Toplevel(self.master)
        w.title("CATIA BOM eşleştirme")
        w.geometry("1100x560")
        ttk.Label(w, text=self.M.BE.ozet_metni(s, cb)
                  + (f"\n{n_mal} parçanın malzemesi CATIA'dan alındı." if n_mal else "")
                  + (f"\nYazıldı: {yazildi}" if yazildi else
                     "\nÇıktı klasörü seçili değil: dosya yazılmadı (Adım 1'de klasör verin)."),
                  justify="left", padx=8, pady=6).pack(fill="x")
        kol = ("durum", "catia_part_no", "catia_adet", "step_adet", "step_ad", "catia_tanim", "malzeme")
        bas = ("durum", "CATIA parça no", "CATIA adet", "STEP adet", "STEP ad", "tanım", "malzeme")
        gen = (110, 260, 80, 80, 260, 180, 110)
        fr = ttk.Frame(w); fr.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        ag = ttk.Treeview(fr, columns=kol, show="headings")
        for k, b, g in zip(kol, bas, gen):
            ag.heading(k, text=b); ag.column(k, width=g, anchor="w")
        sb = ttk.Scrollbar(fr, orient="vertical", command=ag.yview)
        ag.configure(yscrollcommand=sb.set)
        ag.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        for r in s["satirlar"]:
            ag.insert("", "end", values=[r.get(k, "") for k in kol],
                      tags=(r["durum"].replace(" ", "_").replace("'", ""),))
        ag.tag_configure("adet_farklı", background="#ffe4b5")
        ag.tag_configure("CATIAda_yok", background="#ffd6d6")
        ag.tag_configure("STEPte_yok", background="#f0f0f0")
        ttk.Button(w, text="Kapat", command=w.destroy).pack(pady=(0, 8))

    def malzeme_sablon(self):
        if not (self.M and self.komp):
            messagebox.showinfo("Şablon", "Önce STEP inceleyin."); return
        y = filedialog.asksaveasfilename(
            title="malzeme şablonu", defaultextension=".xlsx", initialfile="malzeme.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
        if y:
            self.M.malzeme_sablonu(self.komp, y)
            self._yaz(f"şablon yazıldı: {y}")

    def _standart_kontrol(self):
        """KURAL: standart parça tanımı belirsizse BOM ve çizimden ÖNCE
        söylenir. Tasarımcı ya düzeltir (liste Excel'e yazılır, iş durur)
        ya da olduğu gibi kabul eder (kabul kayda geçer). Aynı liste bir
        kez kabul edildiyse tekrar sorulmaz. True: devam."""
        if not (self.M and self.komp) or not hasattr(self.M, "kontrol_listesi"):
            return True
        liste = self.M.kontrol_listesi(self.komp)
        if not liste:
            return True
        imza = tuple((r[0], r[1], r[2], r[3]) for r in liste)
        if getattr(self, "_kontrol_kabul", None) == imza:
            return True
        cvp = self._standart_karar_penceresi(liste)
        on = (self.v_out.get() or "").strip()
        if cvp is None:
            return False
        if cvp:
            kalan = self.M.kontrol_listesi(self.komp)
            self._kontrol_kabul = tuple((r[0], r[1], r[2], r[3]) for r in kalan)
            if on:
                IS.kontrol_kaydet(on, len(kalan), True)
            self._yaz(f"standart tanımı: {len(kalan)} belirsiz parça olduğu gibi kabul edildi")
            return True
        if not on:
            messagebox.showinfo("Standart parça tanımı", "Önce çıktı klasörünü seçin.")
            return False
        try:
            y = self.M.kontrol_yaz(on, self.komp)
            IS.kontrol_kaydet(on, len(liste), False)
        except Exception as ex:
            messagebox.showerror("Standart parça tanımı", f"Liste yazılamadı:\n{ex}")
            return False
        self._yaz(f"standart tanımı kontrol listesi yazıldı: {y}")
        klasor_ac(y)
        return False

    def _standart_karar_penceresi(self, liste):
        """BELİRSİZ PARÇALAR AYRI PENCEREDE (kullanıcı: "ürünleri ayrı listede
        farklı pencerede açsın, parça görseli de gelsin, seçtiğimde bakayım
        karar vereyim; adsız katıya ad verebileyim ya da eskisi gibi kalsın
        diyebileyim"): solda liste, sağda seçili parçanın izometrik resmi,
        ölçüsü, gerekçesi ve AD kutusu. Her parça için karar anında
        uygulanır: STANDART / ÜRETİM (sınıf kuralı saklanır, biçimce
        benzerleri de değişir), ad kutusu değiştiyse ad / kod düzeltilir
        (ad_kurali: biçim anahtarına göre saklanır, aynı model yeniden
        okununca uygulanır), OLDUĞU GİBİ KALSIN. Alt düğmeler: kalanları
        kabul et ve devam / Excel'e yaz ve dur / vazgeç.
        Döner: True devam, False dur (Excel), None vazgeç."""
        kod_k = {k["kod"]: k for k in self.komp}
        w = tk.Toplevel(self)
        w.title("Standart parça tanımı")
        w.transient(self.master)
        w.geometry("1120x600")
        sonuc = {"cvp": None, "degisen": 0, "ad": 0}
        ttk.Label(w, text=(f"{len(liste)} parçanın standart (satın alınan) mı üretim mi olduğu "
                           "modelden kesin anlaşılamadı. Satırı seçin, resmine bakın; sınıfını "
                           "düzeltin, adsız katıya ad verin ya da olduğu gibi bırakın."),
                  wraplength=1080, justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        pw = ttk.PanedWindow(w, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=10)
        sol = ttk.Frame(pw); pw.add(sol, weight=3)
        kol = ("durum", "kod", "ad", "adet", "olcu", "sinif", "karar")
        bas = ("durum", "kod", "ad", "adet", "ölçü", "şimdiki", "karar")
        gen = (175, 110, 210, 40, 110, 70, 110)
        ag = self._karar_listesi(sol, kol, bas, gen)
        satir_k, satir_r = {}, {}
        for r in liste:
            iid = ag.insert("", "end", values=(r[0], str(r[1])[:30], str(r[2])[:50], r[3], r[4], r[5], ""))
            satir_k[iid], satir_r[iid] = kod_k.get(r[1]), r
        sag = ttk.Frame(pw); pw.add(sag, weight=2)
        c, resim_goster = self._resim_paneli(w, sag)
        v_bilgi = tk.StringVar(value="listeden bir parça seçin")
        ttk.Label(sag, textvariable=v_bilgi, wraplength=370, justify="left").pack(anchor="w", padx=4)
        af = ttk.Frame(sag); af.pack(anchor="w", padx=4, pady=(6, 2), fill="x")
        ttk.Label(af, text="ad / kod:").pack(side="left")
        v_ad = tk.StringVar()
        ttk.Entry(af, textvariable=v_ad, width=42).pack(side="left", padx=(4, 0), fill="x", expand=True)
        bf = ttk.Frame(sag); bf.pack(anchor="w", padx=4, pady=4)
        self._standart_pencere = {"ag": ag, "satir_k": satir_k, "v_ad": v_ad, "sonuc": sonuc, "w": w}

        def secili():
            sel = ag.selection()
            return (sel[0], satir_k.get(sel[0])) if sel else (None, None)

        def secildi(_e=None):
            iid, k = secili()
            if not k:
                return
            r = satir_r[iid]
            v_bilgi.set(f"{k['kod']}\n{k['ad']}\nölçü: {r[4]}   adet: {r[3]}\n"
                        f"şimdiki sınıf: {r[5]}   öneri: {r[6] or '-'}\ngerekçe: {str(r[7])[:160]}")
            v_ad.set(k["ad"])
            resim_goster(k)

        def ad_uygula(k):
            """Ad kutusu değiştiyse ad / kod düzeltilir ve kural saklanır."""
            yeni = (v_ad.get() or "").strip()
            if not yeni or yeni == k["ad"]:
                return False
            kural = dict(self.M.ayar_oku().get("ad_kurali") or {})
            kural[self.M.kural_anahtari(k["ad"], k)] = yeni
            self.M.ayar_yaz(ad_kurali=kural)
            eski_kod, eski_ad = k["kod"], k["ad"]
            k["ad"] = yeni
            if not eski_kod or eski_kod == eski_ad or self.M.TN.isimsiz(eski_kod) \
                    or str(eski_kod).upper().startswith(("SOLID", "COMPOUND")):
                k["kod"] = yeni
            k.pop("isimsiz", None)
            sonuc["ad"] += 1
            self._yaz(f"ad düzeltildi: {eski_kod} -> {yeni} (kural saklandı)")
            return True

        def sonraki(iid):
            nxt = ag.next(iid)
            if nxt:
                ag.selection_set(nxt); ag.see(nxt)

        def karar(yeni):
            iid, k = secili()
            if not k:
                return
            adli = ad_uygula(k)
            if yeni:
                self._sinif_uygula([k], yeni)
                sonuc["degisen"] += 1
                etiket = "STANDART" if yeni == "standart" else "ÜRETİM"
                self._yaz(f"standart tanımı: {k['kod'][:40]} -> {etiket} (kural saklandı)")
            else:
                etiket = "olduğu gibi"
            ag.set(iid, "karar", etiket + (" + ad" if adli else ""))
            ag.set(iid, "sinif", k["sinif"]); ag.set(iid, "ad", k["ad"][:50]); ag.set(iid, "kod", k["kod"][:30])
            sonraki(iid)
        self._standart_pencere["karar"] = karar
        ttk.Button(bf, text="STANDART (satın alınan)", command=lambda: karar("standart")).pack(side="left")
        ttk.Button(bf, text="ÜRETİM parçası", command=lambda: karar("parca")).pack(side="left", padx=6)
        ttk.Button(bf, text="Olduğu gibi kalsın", command=lambda: karar(None)).pack(side="left")
        ttk.Label(sag, foreground="#555", wraplength=370, justify="left", text=(
            "Karar anında uygulanır ve kural olarak saklanır: biçimce benzer parçalar da değişir; "
            "ad düzeltmesi aynı model yeniden okununca da uygulanır.")).pack(anchor="w", padx=4)
        alt = ttk.Frame(w); alt.pack(fill="x", padx=10, pady=8)

        def bitir(cvp):
            sonuc["cvp"] = cvp
            w.destroy()
        ttk.Button(alt, text="Kalanları olduğu gibi kabul et ve DEVAM", command=lambda: bitir(True)).pack(side="left")
        ttk.Button(alt, text="Listeyi Excel'e yaz ve DUR", command=lambda: bitir(False)).pack(side="left", padx=8)
        ttk.Button(alt, text="Vazgeç", command=lambda: bitir(None)).pack(side="right")
        w.protocol("WM_DELETE_WINDOW", lambda: bitir(None))
        ag.bind("<<TreeviewSelect>>", secildi)
        if ag.get_children():
            ag.selection_set(ag.get_children()[0]); secildi()
        try:
            w.grab_set()
        except Exception:
            pass
        w.wait_window()
        self._standart_pencere = None
        if sonuc["degisen"] or sonuc["ad"]:
            # Sınıf / ad değişince BOM, poz ve dosya adları değişir: eski BOM geçersiz.
            self.satirlar = []
            self._agac_doldur(); self._acilim_doldur(); self._ornek_adaylari()
            self.v_bom_ozet.set(f"{sonuc['degisen']} sınıf, {sonuc['ad']} ad düzeltildi – BOM yeniden çıkarılacak")
        return sonuc["cvp"]

    # ------------------------------------------------------------ karar pencereleri: ortak
    # KURAL (kullanıcı): parça hakkında karar isteyen her soru (standart mı
    # üretim mi, ekstrüzyon profilin malzemesi ...) EVET / HAYIR kutusuyla
    # değil, AYNI TÜR PENCEREYLE sorulur: sorunlu parçaların listesi, ARAMA
    # kutusu (binlerce parçada bulunabilsin), seçilince parçanın resmi ve
    # bilgisi, parça başına karar. Ortak parçalar aşağıda.
    def _karar_listesi(self, ust, kol, bas, gen, yuk=20):
        """Arama kutulu liste: üstte 'ara' kutusu (kod / ad / her sütunda
        geçen metin; büyük-küçük harf aranmaz), altında kaydırmalı
        Treeview. Aramaya uymayan satırlar listeden kaldırılır (detach),
        kutu temizlenince sırası bozulmadan geri gelir."""
        ust_ = ttk.Frame(ust); ust_.pack(fill="x", pady=(0, 3))
        ttk.Label(ust_, text="Ara:").pack(side="left")
        v_ara = tk.StringVar()
        e = ttk.Entry(ust_, textvariable=v_ara, width=32)
        e.pack(side="left", padx=(4, 6))
        v_say = tk.StringVar(value="")
        ttk.Label(ust_, textvariable=v_say, foreground="#555").pack(side="left")
        cer = ttk.Frame(ust); cer.pack(fill="both", expand=True)
        ag = ttk.Treeview(cer, columns=kol, show="headings", height=yuk, selectmode="browse")
        for k_, b_, g_ in zip(kol, bas, gen):
            ag.heading(k_, text=b_); ag.column(k_, width=g_, anchor="w")
        sb = ttk.Scrollbar(cer, orient="vertical", command=ag.yview)
        ag.configure(yscrollcommand=sb.set)
        ag.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        tum = []                                  # ekleme sırasıyla bütün satırlar

        def suz(*_a):
            if not tum:
                tum.extend(ag.get_children())
            # Tüm satırlar geri takılır, sonra uymayanlar ayrılır: sıra korunur
            for i, iid in enumerate(tum):
                ag.reattach(iid, "", i)
            ara = self.M._tr_sade(v_ara.get()) if self.M else v_ara.get().lower()
            ara = (ara or "").strip()
            gor = len(tum)
            if ara:
                for iid in tum:
                    metin = " ".join(str(x) for x in ag.item(iid, "values"))
                    metin = self.M._tr_sade(metin) if self.M else metin.lower()
                    if ara not in metin:
                        ag.detach(iid); gor -= 1
            v_say.set(f"{gor} / {len(tum)} satır" if ara else f"{len(tum)} satır")
            kalan = ag.get_children()
            if kalan and not (ag.selection() and ag.selection()[0] in kalan):
                ag.selection_set(kalan[0]); ag.see(kalan[0])
        v_ara.trace_add("write", suz)
        ag.ara_kutusu, ag.v_ara, ag.suz = e, v_ara, suz
        ag.after(50, lambda: (not tum and tum.extend(ag.get_children()),
                              v_say.set(f"{len(tum)} satır")))
        return ag

    def _resim_paneli(self, w, sag):
        """Sağ panel: seçili parçanın izometrik resmi (arka planda çizilir,
        önbelleğe alınır). Döner (tuval, goster): goster(k) parçayı çizer."""
        c = tk.Canvas(sag, width=380, height=290, bg="white", highlightthickness=1,
                      highlightbackground="#bbb")
        c.pack(padx=4, pady=(4, 2), fill="both", expand=True)
        self._tuval_yeniden_ciz(c)
        c.bind("<Double-1>", lambda e: self.parca_resmi_penceresi(c))
        kuyruk_ = queue.Queue()
        istek = {"id": None}

        def goster(k):
            anahtar = id(k); istek["id"] = anahtar
            if anahtar in self._resim_onbellek:
                self._parca_resmi_ciz(self._resim_onbellek[anahtar], c)
                return
            c.delete("all")
            if not self.kayit:
                c.create_text(190, 145, text="model yüklü değil", fill="#888")
                return
            c.create_text(190, 145, text="çiziliyor…", fill="#888")
            sh = self.kayit[k["indeks"][0]][1]
            self._resim_isi_ver(anahtar, sh, lambda a, ken: kuyruk_.put((a, ken)))

        def bekle():
            try:
                while True:
                    anahtar, ken = kuyruk_.get_nowait()
                    self._resim_onbellek[anahtar] = ken
                    if anahtar == istek["id"]:
                        self._parca_resmi_ciz(ken, c)
            except queue.Empty:
                pass
            if w.winfo_exists():
                w.after(120, bekle)
        bekle()
        return c, goster

    def _malzeme_karar_penceresi(self, ek):
        """MALZEMESİ BELİRSİZ PROFİLLER AYRI PENCEREDE (kullanıcı: "hani ben
        değiştirebiliyordum, resim gösteriyordun; listede binlerce parça
        varsa nereden bulacağım, arama da yok; aynı standart penceresi
        gibi pencere aç, sorunlu parçaları listele, seçebileyim"): solda
        arama kutulu liste, sağda seçili parçanın resmi, kesiti, ölçüsü;
        malzeme kutusu (bütün malzeme tablosu) + ALÜMİNYUM / ÇELİK kısa
        yolları; "bu parçaya" ya da "kararsız kalanların hepsine" uygulanır.
        Karar anında malzemeler sözlüğüne yazılır (klasör ayarında saklanır,
        bir daha sorulmaz). Döner: True devam (hepsi kararlı), None vazgeç."""
        M = self.M
        w = tk.Toplevel(self)
        w.title("Ekstrüzyon profil malzemesi")
        w.transient(self.master)
        w.geometry("1120x600")
        sonuc = {"cvp": None, "karar": 0}
        ttk.Label(w, text=(f"{len(ek)} ekstrüzyon profilin malzemesi CAD'de tanımlı değil. Program "
                           "çelik ya da alüminyum varsaymaz: satırı seçin, resmine bakın, malzemesini "
                           "verin. Kararlar saklanır, bir daha sorulmaz."),
                  wraplength=1080, justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        pw = ttk.PanedWindow(w, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=10)
        sol = ttk.Frame(pw); pw.add(sol, weight=3)
        kol = ("kod", "ad", "adet", "kesit", "olcu", "karar")
        bas = ("kod", "ad", "adet", "kesit", "ölçü", "malzeme")
        gen = (120, 230, 40, 150, 110, 150)
        ag = self._karar_listesi(sol, kol, bas, gen)
        satir_k = {}

        def olcu(k):
            o = k.get("olc") or []
            return " x ".join(XL.tr(v, 1) for v in o[:3]) if o else ""

        def kesit(k):
            r = k.get("profil") or {}
            return str(r.get("kesit") or k.get("tip") or "ekstrüzyon")[:40]
        for k in ek:
            iid = ag.insert("", "end", values=(str(k["kod"])[:30], str(k["ad"])[:60], k.get("adet", 1),
                                               kesit(k), olcu(k), ""))
            satir_k[iid] = k
        sag = ttk.Frame(pw); pw.add(sag, weight=2)
        c, resim_goster = self._resim_paneli(w, sag)
        v_bilgi = tk.StringVar(value="listeden bir parça seçin")
        ttk.Label(sag, textvariable=v_bilgi, wraplength=370, justify="left").pack(anchor="w", padx=4)
        mf = ttk.Frame(sag); mf.pack(anchor="w", padx=4, pady=(8, 2), fill="x")
        ttk.Label(mf, text="malzeme:").pack(side="left")
        adlar = [f"{a} – {t} ({XL.tr(r)} g/cm³)" for a, (t, r) in M.MALZEME.items()]
        v_mal = tk.StringVar(value=next((a for a in adlar if a.startswith("aluminyum ")), adlar[0]))
        cb = ttk.Combobox(mf, textvariable=v_mal, values=adlar, state="readonly", width=40)
        cb.pack(side="left", padx=(4, 0), fill="x", expand=True)
        kf = ttk.Frame(sag); kf.pack(anchor="w", padx=4, pady=2)
        self._malzeme_pencere = {"ag": ag, "satir_k": satir_k, "v_mal": v_mal, "sonuc": sonuc, "w": w}

        def secili():
            sel = ag.selection()
            return (sel[0], satir_k.get(sel[0])) if sel else (None, None)

        def secildi(_e=None):
            iid, k = secili()
            if not k:
                return
            v_bilgi.set(f"{k['kod']}\n{k['ad']}\nkesit: {kesit(k)}   ölçü: {olcu(k)}   "
                        f"adet: {k.get('adet', 1)}\nşimdiki malzeme: {ag.set(iid, 'karar') or '(belirsiz)'}")
            resim_goster(k)

        def anahtar():
            return v_mal.get().split(" – ")[0].strip()

        def uygula(iid, k, m):
            self.malzemeler[M._tr_sade(k["kod"])] = m
            ag.set(iid, "karar", M.MALZEME[m][0])
            sonuc["karar"] += 1
            self._yaz(f"profil malzemesi: {k['kod'][:40]} -> {M.MALZEME[m][0]} (kullanıcı seçti)")

        def bu_parcaya(m=None):
            iid, k = secili()
            if not k:
                return
            uygula(iid, k, m or anahtar())
            secildi()
            nxt = ag.next(iid)
            if nxt:
                ag.selection_set(nxt); ag.see(nxt)

        def kalanlara(m=None):
            m = m or anahtar()
            for iid, k in satir_k.items():
                if not ag.set(iid, "karar"):
                    uygula(iid, k, m)
            secildi()
        self._malzeme_pencere.update(bu_parcaya=bu_parcaya, kalanlara=kalanlara)
        ttk.Button(kf, text="ALÜMİNYUM", command=lambda: bu_parcaya("aluminyum")).pack(side="left")
        ttk.Button(kf, text="ÇELİK", command=lambda: bu_parcaya("celik")).pack(side="left", padx=6)
        ttk.Button(kf, text="Kutudaki malzemeyi bu parçaya", command=lambda: bu_parcaya()).pack(side="left")
        kf2 = ttk.Frame(sag); kf2.pack(anchor="w", padx=4, pady=2)
        ttk.Button(kf2, text="Kutudaki malzemeyi KARARSIZ KALANLARIN hepsine",
                   command=lambda: kalanlara()).pack(side="left")
        ttk.Label(sag, foreground="#555", wraplength=370, justify="left", text=(
            "Karar anında uygulanır, çıktı klasörünün ayarında saklanır; malzeme 2. adımdaki "
            "listeden sonradan da değiştirilebilir.")).pack(anchor="w", padx=4, pady=(6, 0))
        alt = ttk.Frame(w); alt.pack(fill="x", padx=10, pady=8)

        def devam():
            kalan = [iid for iid in satir_k if not ag.set(iid, "karar")]
            if kalan:
                messagebox.showwarning("Malzeme", f"{len(kalan)} profilin malzemesi hâlâ belirsiz. "
                                       "Her birine malzeme verin ya da kutudaki malzemeyi kalanlara "
                                       "uygulayın.", parent=w)
                ag.selection_set(kalan[0]); ag.see(kalan[0]); secildi()
                return
            sonuc["cvp"] = True
            w.destroy()

        def vazgec():
            sonuc["cvp"] = None
            w.destroy()
        ttk.Button(alt, text="DEVAM", style="Bas.TButton", command=devam).pack(side="left", ipadx=10)
        ttk.Button(alt, text="Vazgeç (malzemeyi 2. adımda kendim veririm)", command=vazgec).pack(side="right")
        w.protocol("WM_DELETE_WINDOW", vazgec)
        ag.bind("<<TreeviewSelect>>", secildi)
        if ag.get_children():
            ag.selection_set(ag.get_children()[0]); secildi()
        try:
            w.grab_set()
        except Exception:
            pass
        w.wait_window()
        self._malzeme_pencere = None
        if sonuc["karar"]:
            self._malzeme_satirlari_guncelle()
        return sonuc["cvp"]

    def _profil_malzeme_sor(self):
        """EKSTRÜZYON profilin malzemesi CAD'den / dosyadan gelmiyorsa SORAR
        (program çelik ya da alüminyum varsaymaz - kullanıcı kararı):
        arama kutulu, resimli, parça başına kararlı pencere
        (_malzeme_karar_penceresi). Cevap o profillerin koduna yazılır,
        klasör ayarında saklanır: bir daha sorulmaz. True: devam."""
        if not (self.M and self.komp) or not hasattr(self.M, "malzemesi_sorulacak"):
            return True
        ek = self.M.malzemesi_sorulacak(self.komp, dict(self.malzemeler))
        if not ek:
            return True
        return bool(self._malzeme_karar_penceresi(ek))

    def bom_cikart(self):
        if not self._standart_kontrol():
            return
        if not self._profil_malzeme_sor():
            return
        self._basla("BOM çıkarılıyor…", "BOM çıkarma")
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
        self.v_bom_ozet.set(f"{len(sonuc['bom'])} poz, toplam {XL.tr(kg, 3, sade=False)} kg – BOM.csv yazıldı")
        # örnek parça adayları: en çok çeşit delik + radüs taşıyan önce
        self._ornek_adaylari()
        self._adim_ac(2)
        self._durum_ipucu = "BOM hazır – görünüş ve kesit ayarını yapın"
        self.v_durum.set(self._durum_ipucu)

    # ------------------------------------------------------------ 3 AYAR
    def gorunus_degisti(self, k=None):
        """Görünüş seçimi otomatik: yalnız açıklama yazılır."""
        self.v_gor_bilgi.set(
            "Program parçanın özelliklerine (delik, slot, kesik, tek duvar deliği, "
            "büküm) göre gereken görünüşleri 6'ya kadar kendisi seçer; bilgi "
            "eklemeyen ve ayna görünüşler elenir, sıkışan bölgeler detaya taşınır. "
            "Yerleşim 1. açı; adlar bakış yönünden (Chevalier s.49). Parça bazlı "
            "istek (görünüş, kesit, perspektif) aşağıdaki istisna satırında.")

    def ornek_uret(self):
        if not self.komp:
            return
        i = max(self.cb_ornek.current(), 0)
        r = self.ornek_adaylar[i] if self.ornek_adaylar else None
        if not r:
            messagebox.showinfo("Örnek", "Çizilecek parça yok."); return
        self._basla(f"örnek resim üretiliyor: {r['kod']}",
                    f"Örnek resim: {r['kod'][:30]}")
        threading.Thread(target=self._ornek_is, args=(r, self._is_girdisi()),
                         daemon=True).start()

    def _ornek_is(self, r, g):
        try:
            komp = [k for k in self.komp if k["kod"] == r["kod"] and k["sinif"] == "parca"]
            sonuc = self._calistir(g, asama=(2,), komp=komp, tablo_yok=True,
                                   poz_harita={x["kod"]: x["poz"]
                                               for x in self.ornek_adaylar})
            ciz = [x for x in sonuc["satirlar"] if x.get("dxf", "").endswith(".dxf")]
            if not ciz:
                raise RuntimeError("örnek resim üretilemedi")
            self.kuyruk.put(("ornek", (os.path.join(sonuc["dxf_klasor"], ciz[0]["dxf"]), ciz[0],
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
        self._durum_ipucu = "örnek hazır – inceleyip onaylayın"
        self.v_durum.set(self._durum_ipucu)
        threading.Thread(target=self._onizle_is, args=(yol,), daemon=True).start()

    def ornek_ac(self):
        if self.ornek_dxf:
            klasor_ac(self.ornek_dxf)

    # ------------------------------------------------------------ 4/5 tümü
    def tumunu_uret(self):
        if not self.komp:
            messagebox.showinfo(
                "Çizimler", "Çizim için model gerekir: 1. sayfada İNCELE "
                "deyin. (Pafta ve PDF için gerekmez.)")
            return
        if not self._standart_kontrol():
            return
        if not self._profil_malzeme_sor():
            return
        asama = [2] + ([3] if self.v_montaj.get() else [])
        eksik = bool(self.v_eksik.get())
        self._basla("çizimler üretiliyor…" if not eksik else
                    "eksik / eskimiş çizimler üretiliyor…",
                    "Eksik çizimler" if eksik else "Tüm çizimler")
        self._adim_ac(4)
        self.liste.delete(0, "end")
        threading.Thread(target=self._tumu_is,
                         args=(tuple(asama), self._is_girdisi(), eksik),
                         daemon=True).start()

    def _tumu_is(self, asama, g, eksik=False):
        try:
            self.kuyruk.put(("tumu", self._calistir(g, asama=(1,) + asama,
                                                   eksik=eksik)))
        except Exception:
            self.kuyruk.put(("hata", "Üretim sırasında hata:\n\n"
                             + traceback.format_exc(limit=4)))

    def _tumu_geldi(self, sonuc):
        self.satirlar = sonuc["satirlar"]
        self._bitir()
        self._agac_doldur()
        on = sonuc["klasor"]
        d = self._cikti_listesi()
        kg = sum((r.get("toplam_kg") or 0.0) for r in sonuc["bom"])
        at = sonuc.get("atlanan") or 0
        self.v_sonuc.set(f"{d} DXF, {len(sonuc['bom'])} poz, toplam {XL.tr(kg, 3, sade=False)} kg"
                         + (f"  –  {at} çizim güncel olduğu için yeniden "
                            "üretilmedi" if at else "") + f"\n{on}")
        self._durum_ipucu = "bitti – ZIP oluşturabilirsiniz"
        self.v_durum.set(self._durum_ipucu)

    def kaynak_resimleri_uret(self):
        """Kaynak resimleri (pf14_kaynak): ayrı iş, ilerlemeli, iptal edilebilir."""
        if not self._lisans_izin("kaynak"):
            return
        if not self.komp:
            messagebox.showinfo("Kaynak resimleri", "Önce 1. sayfada modeli inceleyin.")
            return
        n = sum(len(k["indeks"]) for k in self.komp if k.get("sinif") == "kaynak")
        if not n:
            messagebox.showinfo("Kaynak resimleri", "Modelde kaynak dikişi yok.")
            return
        on = (self.v_out.get() or "").strip()
        if not on:
            messagebox.showinfo("Kaynak resimleri", "Çıktı klasörü seçilmedi.")
            return
        self._basla(f"kaynak resimleri üretiliyor ({n} dikiş)…", "Kaynak resimleri")
        self.ilerleme.configure(mode="determinate", maximum=1, value=0)
        # poz numaraları BOM'dan; BOM çıkarılmadıysa komponent sırası
        sat = list(getattr(self, "satirlar", None) or [])
        if not sat:
            poz = 0
            for k in self.komp:
                if k.get("sinif") != "kaynak":
                    poz += 1
                    sat.append({"kod": k["kod"], "poz": poz})
        threading.Thread(target=self._kaynak_is, args=(on, sat), daemon=True).start()

    def _kaynak_is(self, on, sat):
        try:
            import pf14_kaynak as KR
            os.makedirs(on, exist_ok=True)
            y = KR.kaynak_resimleri(
                on, self.kayit, self.komp, self.agac, sat, log=self._yaz,
                iptal=lambda: self.iptal_istendi,
                ilerleme=lambda a, b: self.kuyruk.put(("ilerleme", (a, b))))
            self.kuyruk.put(("kaynak", y))
        except Exception:
            self.kuyruk.put(("hata", "Kaynak resimleri üretilirken hata:\n\n"
                             + traceback.format_exc(limit=4)))

    def _kaynak_geldi(self, yazilan):
        self._bitir()
        self._cikti_listesi()
        self.v_sonuc.set(f"{len(yazilan)} kaynak resmi (PDF)  –  "
                         f"{os.path.join(self.v_out.get(), 'KAYNAK')}")

    def _cikti_listesi(self):
        """5. sayfadaki liste: klasördeki çizimler, türüne göre klasörüyle
        (DXF/, ACINIM/, LZR/, PDF/) ve kökteki tablolar."""
        on = (self.v_out.get() or "").strip()
        self.liste.delete(0, "end")
        if not on or not os.path.isdir(on):
            return 0
        n = 0
        for tur in ("dxf", "acinim", "lazer", "pdf", "kaynak"):
            for y in IS.dosyalar(on, tur):
                self.liste.insert("end", os.path.relpath(y, on).replace("\\", "/"))
                n += tur == "dxf"
        for x in ("BOM.xlsx", "BOM.csv", "BOM.md", "BOM_AGAC.xlsx", "BOM_AGAC.csv",
                  "PROFIL.xlsx", "olculer.xlsx", "olculer.csv", "rapor.md"):
            if os.path.isfile(os.path.join(on, x)):
                self.liste.insert("end", x)
        if not self.v_sonuc.get():
            self.v_sonuc.set(f"{n} DXF (detay + montaj) klasörde\n{on}")
        self.b_zip.configure(state="normal" if self.liste.size() else "disabled")
        return n

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
        self._adim_ac(3)
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

    @staticmethod
    def _resmi_sigdir(png, gw, gh, oran=None):
        """PNG'yi gw x gh alana SIĞACAK biçimde (iki yönde de) ölçekler ya da
        verilen oranda büyütür; PhotoImage döner. Pillow varsa keskin
        (LANCZOS), yoksa tam sayı küçültme. Eskiden iki yönün KÜÇÜK
        katsayısı alınıyordu: geniş resim tuvalden taşıyor, ÖN görünüşün
        üstü ve ARKA'nın altı kesiliyordu (kullanıcı: "resim görülmüyor,
        nesini onaylayayım")."""
        try:
            from PIL import Image, ImageTk
            im = Image.open(png)
            if oran is None:
                oran = min(gw / max(im.width, 1), gh / max(im.height, 1))
            yeni = (max(1, int(im.width * oran)), max(1, int(im.height * oran)))
            if yeni != im.size:
                im = im.resize(yeni, Image.LANCZOS)
            return ImageTk.PhotoImage(im), oran
        except Exception:
            ham = tk.PhotoImage(file=png)
            if oran is None:
                k = max(1, max(-(-ham.width() // max(gw, 1)), -(-ham.height() // max(gh, 1))))
                return (ham.subsample(k, k) if k > 1 else ham), 1.0 / k
            if oran >= 1:
                z = max(1, int(round(oran)))
                return (ham.zoom(z, z) if z > 1 else ham), float(z)
            k = max(1, int(round(1.0 / oran)))
            return (ham.subsample(k, k) if k > 1 else ham), 1.0 / k

    def _onizleme_ciz(self):
        if not self.onizleme_png or not os.path.isfile(self.onizleme_png):
            return
        try:
            gw = max(self.tuval.winfo_width(), 1)
            gh = max(self.tuval.winfo_height(), 1)
            self.onizleme_resmi, _ = self._resmi_sigdir(self.onizleme_png, gw - 4, gh - 4)
            self.tuval.delete("all")
            self.tuval.create_image(gw // 2, gh // 2, image=self.onizleme_resmi)
        except Exception as ex:
            self.v_durum.set(f"önizleme çizilemedi: {ex}")

    def onizleme_penceresi(self, png=None, baslik=None):
        """ÖNİZLEME AYRI PENCEREDE, YAKINLAŞTIRMALI (kullanıcı: "sığmayan
        her durumda pencere yap, mümkün olan yerde genişlet"): ekranın
        %90'ı kadar pencere, kaydırma çubukları; Sığdır / 1:1 / + / −
        düğmeleri, Ctrl + tekerlek yakınlaştırır, tekerlek kaydırır, sol
        tuşla sürüklenir. Açılışta resim pencereye sığdırılır."""
        png = png or self.onizleme_png
        if not png or not os.path.isfile(png):
            messagebox.showinfo("Önizleme", "Henüz gösterilecek önizleme yok.")
            return None
        w = tk.Toplevel(self)
        w.title(baslik or ("Önizleme – " + (self.v_ornek_bilgi.get() if hasattr(self, "v_ornek_bilgi") else "")))
        try:
            sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
            gw, gh = int(sw * 0.9), int(sh * 0.88)
            w.geometry(f"{gw}x{gh}+{(sw - gw) // 2}+{max(0, (sh - gh) // 3)}")
        except Exception:
            pass
        ust = ttk.Frame(w, padding=(6, 4)); ust.pack(fill="x")
        cer = ttk.Frame(w); cer.pack(fill="both", expand=True)
        c = tk.Canvas(cer, bg="white", highlightthickness=0)
        sy = ttk.Scrollbar(cer, orient="vertical", command=c.yview)
        sx = ttk.Scrollbar(w, orient="horizontal", command=c.xview)
        c.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side="right", fill="y"); c.pack(side="left", fill="both", expand=True)
        sx.pack(fill="x")
        durum = {"oran": None, "resim": None, "png": png}
        v_oran = tk.StringVar(value="")

        def ciz(oran=None):
            gw_, gh_ = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
            durum["resim"], durum["oran"] = self._resmi_sigdir(png, gw_ - 2, gh_ - 2, oran)
            c.delete("all")
            iw, ih = durum["resim"].width(), durum["resim"].height()
            x = max((gw_ - iw) // 2, 0); y = max((gh_ - ih) // 2, 0)
            c.create_image(x, y, image=durum["resim"], anchor="nw")
            c.configure(scrollregion=(0, 0, max(iw, gw_), max(ih, gh_)))
            v_oran.set(f"%{durum['oran'] * 100:.0f}")

        def yakin(kat):
            o = (durum["oran"] or 1.0) * kat
            o = min(max(o, 0.05), 8.0)
            ciz(o)
        ttk.Button(ust, text="Sığdır", command=lambda: ciz(None)).pack(side="left")
        ttk.Button(ust, text="1:1", command=lambda: ciz(1.0)).pack(side="left", padx=4)
        ttk.Button(ust, text="＋", width=3, command=lambda: yakin(1.25)).pack(side="left")
        ttk.Button(ust, text="－", width=3, command=lambda: yakin(0.8)).pack(side="left", padx=4)
        ttk.Label(ust, textvariable=v_oran, width=6).pack(side="left")
        ttk.Label(ust, foreground="#555", text=(
            "Ctrl + tekerlek yakınlaştırır, tekerlek kaydırır, sol tuşla sürükleyin")).pack(side="left", padx=10)
        ttk.Button(ust, text="Kapat", command=w.destroy).pack(side="right")

        def teker(e):
            if e.state & 0x4:                     # Ctrl
                yakin(1.25 if (e.num == 4 or e.delta > 0) else 0.8)
            elif e.state & 0x1:                   # Shift: yatay
                c.xview_scroll(-1 if (e.num == 4 or e.delta > 0) else 1, "units")
            else:
                c.yview_scroll(-1 if (e.num == 4 or e.delta > 0) else 1, "units")
        for olay in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            c.bind(olay, teker)
        c.bind("<ButtonPress-1>", lambda e: c.scan_mark(e.x, e.y))
        c.bind("<B1-Motion>", lambda e: c.scan_dragto(e.x, e.y, gain=1))
        ilk = {"ok": False}

        def boyut(e):
            if not ilk["ok"]:
                ilk["ok"] = True
                ciz(None)
        c.bind("<Configure>", boyut)
        w.bind("<Escape>", lambda e: w.destroy())
        self._onizleme_pencere = {"w": w, "c": c, "durum": durum, "ciz": ciz, "yakin": yakin}
        return w


class MalzemeSihirbazi:
    """Malzemeyi CAD'den almak - dört adım.

      1 STEP'te ne var   açık modelde kaç parçanın malzemesi STEP'ten geldi
      2 CAD sistemi      SolidWorks, CATIA, NX, Creo, Inventor, Solid Edge...
      3 Parça listesi    o CAD'de malzeme sütunlu listeyi alma adımları;
                         varsa makroyu kaydetme
      4 Dosya            seçilen dosya ÖNİZLENİR (hangi parça hangi
                         malzemeyi alacak, hangisi eşleşmedi, hangi ad
                         tanınmadı), ancak sonra UYGULA ile işlenir.

    Metinler ve eşleştirme pf6_malzeme'dedir; burada yalnız pencere var."""
    ADIMLAR = ("1  STEP'te ne var", "2  CAD sistemi",
               "3  Parça listesini alın", "4  Dosyayı yükleyin")

    def __init__(self, u):
        import pf6_malzeme as S6
        self.u, self.S6 = u, S6
        self.adim = 0
        self.rapor = None
        self.w = w = tk.Toplevel(u.master)
        w.title("Malzemeyi CAD'den al")
        w.geometry("1000x660")
        w.minsize(860, 560)
        try:
            w.transient(u.master)
        except Exception:
            pass
        self.v_sis = tk.StringVar(value="solidworks")
        sol = ttk.Frame(w, padding=(12, 12, 6, 12))
        sol.pack(side="left", fill="y")
        ttk.Label(sol, text="Adımlar", style="Baslik.TLabel").pack(anchor="w",
                                                                    pady=(0, 8))
        self.adim_et = []
        for a in self.ADIMLAR:
            e = ttk.Label(sol, text=a, foreground="#777")
            e.pack(anchor="w", pady=3)
            self.adim_et.append(e)
        sag = ttk.Frame(w, padding=(6, 12, 12, 12))
        sag.pack(side="left", fill="both", expand=True)
        self.govde = ttk.Frame(sag)
        self.govde.pack(fill="both", expand=True)
        alt = ttk.Frame(sag)
        alt.pack(fill="x", pady=(10, 0))
        ttk.Button(alt, text="Kapat", command=w.destroy).pack(side="right")
        self.b_uygula = ttk.Button(alt, text="UYGULA  ✓", style="Bas.TButton",
                                   command=self.uygula, state="disabled")
        self.b_uygula.pack(side="right", padx=8, ipadx=10)
        self.b_ileri = ttk.Button(alt, text="İleri  ▸", command=self.ileri)
        self.b_ileri.pack(side="right", padx=4)
        self.b_geri = ttk.Button(alt, text="◂  Geri", command=self.geri)
        self.b_geri.pack(side="right", padx=4)
        self.goster()

    # ------------------------------------------------------------ gezinme
    def ileri(self):
        if self.adim < len(self.ADIMLAR) - 1:
            self.adim += 1
            self.goster()

    def geri(self):
        if self.adim > 0:
            self.adim -= 1
            self.goster()

    def goster(self):
        for c in self.govde.winfo_children():
            c.destroy()
        for i, e in enumerate(self.adim_et):
            e.configure(foreground="#000" if i == self.adim else "#777",
                        font=("Segoe UI", 10, "bold") if i == self.adim
                        else ("Segoe UI", 10))
        self.b_geri.configure(state="normal" if self.adim else "disabled")
        self.b_ileri.configure(state="normal" if self.adim < 3 else "disabled")
        self.b_uygula.configure(state="normal" if (
            self.adim == 3 and self.rapor and self.rapor["eslesen"]) else "disabled")
        (self._adim1, self._adim2, self._adim3, self._adim4)[self.adim]()

    def _baslik(self, t, aciklama=""):
        ttk.Label(self.govde, text=t, style="Baslik.TLabel").pack(anchor="w")
        if aciklama:
            ttk.Label(self.govde, text=aciklama, foreground="#555",
                      wraplength=720, justify="left").pack(anchor="w",
                                                           pady=(2, 8))

    def _metin(self, icerik, yukseklik=18):
        cer = ttk.Frame(self.govde)
        cer.pack(fill="both", expand=True)
        t = tk.Text(cer, wrap="word", height=yukseklik, font=("Segoe UI", 10),
                    relief="flat", padx=8, pady=6)
        k = ttk.Scrollbar(cer, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=k.set)
        t.insert("1.0", icerik)
        t.configure(state="disabled")
        t.pack(side="left", fill="both", expand=True)
        k.pack(side="right", fill="y")
        return t

    # ------------------------------------------------------------- adımlar
    def _adim1(self):
        u = self.u
        self._baslik("1 - STEP dosyasında malzeme var mı?",
                     "STEP malzeme adını ve yoğunluğunu taşıyabilir ama "
                     "CAD'lerin çoğu varsayılan ayarla yazmaz. Malzemesi "
                     "bilinmeyen parça ÇELİK sayılır ve kütlesi yanlış çıkar.")
        if not (u.M and u.komp):
            self._metin("Henüz model incelenmedi.\n\n1. adımda STEP dosyasını "
                        "seçip İNCELE deyin; bu sayfa o zaman kaç parçanın "
                        "malzemesinin STEP'ten geldiğini gösterir.\n\n"
                        "Yine de 'İleri' ile CAD sisteminizin adımlarını "
                        "okuyabilirsiniz.", 10)
            return
        r = self.S6.step_raporu(u.M, u.komp)
        sat = [f"Montajdaki parça sayısı:           {r['parca']}",
               f"Malzemesi STEP'ten gelen:          {len(r['stepten'])}",
               f"Malzemesi parça ADINDAN tanınan:   {r['ad_ipucu']}"
               "   (ör. adında 'S235', 'AlMg3' geçiyor)",
               f"Malzemesi BİLİNMEYEN:              {r['eksik']}"
               "   (varsayılan malzeme sayılır)", ""]
        if r["stepten"]:
            sat.append("STEP'ten gelenler (ilk 15):")
            for kod, ad, y in r["stepten"][:15]:
                sat.append(f"   {kod[:34]:34s}  {ad[:30]:30s}"
                           + (f"  {XL.tr(y)}" if y else ""))
            sat.append("")
        if r["eksik"] == 0:
            sat.append("Bütün parçaların malzemesi belli - bu sihirbaza gerek "
                       "yok.")
        else:
            sat.append(f"{r['eksik']} parçanın malzemesini CAD'inizin parça "
                       "listesinden almak için 'İleri'.")
        self._metin("\n".join(sat), 14)

    def _adim2(self):
        self._baslik("2 - Model hangi CAD'den geldi?",
                     "Seçtiğiniz sistem için bir sonraki sayfada adım adım "
                     "talimat çıkar.")
        cer = ttk.Frame(self.govde)
        cer.pack(anchor="w", pady=4)
        for s in self.S6.SISTEM:
            ttk.Radiobutton(cer, text=s["ad"], value=s["anahtar"],
                            variable=self.v_sis).pack(anchor="w", pady=3)

    def _adim3(self):
        s = self.S6.sistem(self.v_sis.get())
        self._baslik(f"3 - {s['ad']}: malzeme sütunlu parça listesini alın",
                     "Amaç her CAD'de aynı: 'parça no' ve 'malzeme' "
                     "(isteğe bağlı 'yoğunluk') sütunlu bir tablo - CSV, TXT "
                     "ya da Excel (.xlsx).")
        metin = self.S6.talimat_metni(s["anahtar"])
        self._metin(metin, 16)
        dugme = ttk.Frame(self.govde)
        dugme.pack(fill="x", pady=(8, 0))
        ttk.Button(dugme, text="Metni panoya kopyala",
                   command=lambda: (self.w.clipboard_clear(),
                                    self.w.clipboard_append(metin))
                   ).pack(side="left")
        if s.get("makro"):
            ttk.Button(dugme, text=f"Makroyu kaydet…  ({s['makro']})",
                       command=self.makro_kaydet).pack(side="left", padx=8)

    def makro_kaydet(self):
        kl = filedialog.askdirectory(title="Makronun kaydedileceği klasör",
                                     parent=self.w)
        if not kl:
            return
        y = self.S6.makro_yaz(self.v_sis.get(), kl)
        if y:
            self.u._yaz(f"makro kaydedildi: {y}")
            messagebox.showinfo("Makro", f"Kaydedildi:\n{y}\n\nNasıl "
                                "çalıştırılacağı bu sayfadaki talimatta.",
                                parent=self.w)
        else:
            messagebox.showwarning("Makro", "Makro dosyası bulunamadı "
                                   "(kurulum eksik olabilir).", parent=self.w)

    def _adim4(self):
        u = self.u
        self._baslik("4 - Dosyayı seçin, önizleyin, uygulayın",
                     "Dosya seçilince hiçbir şey değişmez: önce hangi parçanın "
                     "hangi malzemeyi alacağı gösterilir. Doğruysa UYGULA.")
        ust = ttk.Frame(self.govde)
        ust.pack(fill="x")
        ttk.Button(ust, text="Dosya seç…", command=self.dosya_sec).pack(
            side="left")
        self.v_ozet = tk.StringVar(value="" if self.rapor else
                                   "Henüz dosya seçilmedi.")
        ttk.Label(ust, textvariable=self.v_ozet, foreground="#333",
                  justify="left", wraplength=620).pack(side="left", padx=10)
        cer = ttk.Frame(self.govde)
        cer.pack(fill="both", expand=True, pady=(8, 0))
        sut = ("kod", "dosya", "yog", "pi3d", "durum")
        basl = {"kod": ("PARÇA NO", 130), "dosya": ("DOSYADA", 140),
                "yog": ("g/cm³", 60), "pi3d": ("PI3D MALZEMESİ", 210),
                "durum": ("DURUM", 200)}
        self.ag = ttk.Treeview(cer, columns=sut, show="headings", height=14)
        for c in sut:
            self.ag.heading(c, text=basl[c][0])
            # Toplam ~740 px: sihirbazın sağ bölmesine sığar; pencere
            # büyütülürse DURUM ve PI3D sütunları genişler.
            self.ag.column(c, width=basl[c][1], minwidth=50,
                           stretch=c in ("pi3d", "durum"),
                           anchor="center" if c == "yog" else "w")
        k = ttk.Scrollbar(cer, orient="vertical", command=self.ag.yview)
        self.ag.configure(yscrollcommand=k.set)
        self.ag.pack(side="left", fill="both", expand=True)
        k.pack(side="right", fill="y")
        self.ag.tag_configure("yok", foreground="#b00")
        self.ag.tag_configure("bos", foreground="#888")
        self.ag.tag_configure("cad", foreground="#036")
        if self.rapor:
            self._rapor_goster()
        if not (u.M and u.komp):
            self.v_ozet.set("Önce 1. adımda STEP'i inceleyin: eşleştirme "
                            "montajdaki parçalarla yapılır.")

    def dosya_sec(self):
        u = self.u
        if not (u.M and u.komp):
            messagebox.showinfo("Malzeme", "Önce STEP dosyasını inceleyin.",
                                parent=self.w)
            return
        y = filedialog.askopenfilename(
            title="CAD'in parça listesi", parent=self.w,
            filetypes=[("Parça listesi", "*.csv *.txt *.tsv *.xlsx *.xls *.htm *.html *.json"),
                       ("Tümü", "*.*")])
        if not y:
            return
        self.dosya_yukle(y)

    def dosya_yukle(self, y):
        try:
            self.rapor = self.S6.dosya_raporu(self.u.M, y, self.u.komp)
        except Exception as ex:
            self.rapor = None
            messagebox.showerror("Malzeme dosyası", str(ex), parent=self.w)
            return
        self.rapor["yol"] = y
        self._rapor_goster()
        self.b_uygula.configure(state="normal" if self.rapor["eslesen"]
                                else "disabled")

    def _rapor_goster(self):
        M, r = self.u.M, self.rapor
        self.ag.delete(*self.ag.get_children())
        kullanilmayan = {id(x) for x in r["kullanilmayan"]}
        for s in r["satir"]:
            if not s["anahtar"]:
                durum, etiket = "ad tanınmadı, yoğunluk yok", "yok"
            elif id(s) in kullanilmayan:
                durum, etiket = "montajda karşılığı yok", "bos"
            elif s["durum"] == "CAD yoğunluğuyla":
                durum, etiket = "eşleşti (CAD yoğunluğu)", "cad"
            else:
                durum, etiket = "eşleşti", ""
            pi3d = M.MALZEME[s["anahtar"]][0] if s["anahtar"] else "-"
            self.ag.insert("", "end", tags=(etiket,), values=(
                s["kod"], s["malzeme"] or "-",
                XL.tr(s["yogunluk"], 3) if s["yogunluk"] else "-", pi3d, durum))
        n_parca = (len(r["eslesen"]) + len(r["eslesmeyen"])
                   + len(r["adi_taninmayan"]))
        t = (f"{os.path.basename(r['yol'])}: {len(r['satir'])} satır.  "
             f"Montajdaki {n_parca} parçanın {len(r['eslesen'])}'i eşleşti")
        if r["eslesmeyen"]:
            t += (f"; {len(r['eslesmeyen'])} parça dosyada yok (malzemesi "
                  "değişmez)")
        if r["adi_taninmayan"]:
            t += (f"; {len(r['adi_taninmayan'])} parçanın malzeme adı "
                  "tanınmadı ve yoğunluğu yok - dosyaya yoğunluk sütunu "
                  "ekleyin ya da adı düzeltin")
        self.v_ozet.set(t + ".")

    def uygula(self):
        u, r = self.u, self.rapor
        if not r or not r["eslesen"]:
            return
        for k, m in r["eslesen"]:
            u.malzemeler[k["kod"]] = m
        u.satirlar = []
        u._agac_doldur()
        u._malzeme_listesi_tazele()
        u._yaz(f"malzeme ({os.path.basename(r['yol'])}): "
               f"{len(r['eslesen'])} parçaya uygulandı"
               + (f", {len(r['eslesmeyen'])} parça dosyada yok"
                  if r["eslesmeyen"] else ""))
        u.v_durum.set(f"malzeme: {len(r['eslesen'])} parçaya uygulandı - "
                      "BOM ÇIKART deyin")
        self.w.destroy()


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
