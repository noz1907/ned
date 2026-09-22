"""
Pi3D Maker – ARAYÜZ (ADIM 1: Referans belirleme)
======================================================
    py pf_gui.py

Ek kurulum gerekmez. tkinter Python ile birlikte gelir, 3B görüntü
saf Python ile çizilir (VTK veya başka görüntüleyici gerekmez).

Kullanım akışı
    1. "STEP Aç" ile dosyayı seç
    2. Soldaki listeden grup/parça seç   -> 3B önizlemede turuncu olur
    3. "Analiz Et" -> 6 yön puanlanır, tabloda çıkar
    4. Tablodan bir yön seç -> 3 nokta hesaplanır, önizlemede kırmızı toplar
    5. "ONAYLA" -> referans JSON yazılır
Fare: sol tuş sürükle = döndür, tekerlek = yakınlaş, sağ tuş sürükle = kaydır
"""
import json, math, os, queue, sys, threading, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pf1_referans as E          # hesap motoru
import cadquery as cq

RENK_ARKA = "#20242b"
RENK_PASIF = "#6b7686"
RENK_SECILI = "#e08a2e"
RENK_NOKTA = "#e33"
RENK_OK = "#39c66d"


# ============================================================ 3B görüntüleyici
class Gorunum(tk.Canvas):
    """Saf Python 3B önizleme: üçgenleştirme + ressam algoritması."""

    def __init__(self, usta, **kw):
        super().__init__(usta, bg=RENK_ARKA, highlightthickness=0, **kw)
        self.ucgenler = []          # (p0,p1,p2, renk_temel)
        self.teller = []            # bağlam için tel kafes
        self.noktalar = []          # (x,y,z)
        self.ok = None              # (baslangic, bitis)
        self.merkez = (0, 0, 0)
        self.olcek = 1.0
        self.yaw, self.pitch = -0.9, -0.5
        self.kaydir = [0, 0]
        self._son = None
        self.bind("<B1-Motion>", self._dondur)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_son", None))
        self.bind("<B3-Motion>", self._tasi)
        self.bind("<ButtonRelease-3>", lambda e: setattr(self, "_son", None))
        self.bind("<MouseWheel>", self._zoom)
        self.bind("<Configure>", lambda e: self.ciz())

    # ---------- veri
    def yukle(self, katilar, secili_idx, hedef_ucgen=6000):
        """Seçili katılar gölgeli üçgen olarak, seçili olmayanlar hafif tel kafes
        sınır kutusu olarak çizilir. Tkinter tuvali sınırlı olduğu için üçgen
        sayısı bütçeye göre otomatik seyreltilir."""
        self.ucgenler = []
        self.teller = []
        kutu = [1e18, 1e18, 1e18, -1e18, -1e18, -1e18]
        for sh, secili in katilar:
            try:
                bb = cq.Shape(sh).BoundingBox()
            except Exception:
                continue
            kutu[0] = min(kutu[0], bb.xmin); kutu[1] = min(kutu[1], bb.ymin)
            kutu[2] = min(kutu[2], bb.zmin); kutu[3] = max(kutu[3], bb.xmax)
            kutu[4] = max(kutu[4], bb.ymax); kutu[5] = max(kutu[5], bb.zmax)
        d = max(kutu[3] - kutu[0], kutu[4] - kutu[1], kutu[5] - kutu[2], 1.0)
        self.merkez = ((kutu[0] + kutu[3]) / 2, (kutu[1] + kutu[4]) / 2,
                       (kutu[2] + kutu[5]) / 2)
        secililer = [sh for sh, sec in katilar if sec]
        digerleri = [sh for sh, sec in katilar if not sec]
        if not secililer:                     # hiçbir şey seçili değilse hepsini kaba göster
            secililer, digerleri = [k[0] for k in katilar][:40], []

        tol = max(d / 200.0, 0.4)
        for _ in range(4):                    # bütçeye girene kadar kabalaştır
            uc = []
            for sh in secililer:
                try:
                    v, t = cq.Shape(sh).tessellate(tol, 0.6)
                except Exception:
                    continue
                for a, b, c in t:
                    uc.append(((v[a].x, v[a].y, v[a].z), (v[b].x, v[b].y, v[b].z),
                               (v[c].x, v[c].y, v[c].z), RENK_SECILI))
            if len(uc) <= hedef_ucgen:
                break
            tol *= 2.2
        if len(uc) > hedef_ucgen:
            uc = uc[::len(uc) // hedef_ucgen + 1]
        self.ucgenler = uc

        for sh in digerleri:                  # bağlam: sadece sınır kutusu teli
            try:
                b = cq.Shape(sh).BoundingBox()
            except Exception:
                continue
            k = [(b.xmin, b.ymin, b.zmin), (b.xmax, b.ymin, b.zmin),
                 (b.xmax, b.ymax, b.zmin), (b.xmin, b.ymax, b.zmin),
                 (b.xmin, b.ymin, b.zmax), (b.xmax, b.ymin, b.zmax),
                 (b.xmax, b.ymax, b.zmax), (b.xmin, b.ymax, b.zmax)]
            for i, j in ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),
                         (0,4),(1,5),(2,6),(3,7)):
                self.teller.append((k[i], k[j]))
        self.olcek = 1.0
        self.kaydir = [0, 0]
        self._d = d
        self.ciz()

    # ---------- etkileşim
    def _dondur(self, e):
        if self._son:
            self.yaw += (e.x - self._son[0]) * 0.01
            self.pitch += (e.y - self._son[1]) * 0.01
            self.pitch = max(-1.55, min(1.55, self.pitch))
            self.ciz()
        self._son = (e.x, e.y)

    def _tasi(self, e):
        if self._son:
            self.kaydir[0] += e.x - self._son[0]
            self.kaydir[1] += e.y - self._son[1]
            self.ciz()
        self._son = (e.x, e.y)

    def _zoom(self, e):
        self.olcek *= 1.15 if e.delta > 0 else 1 / 1.15
        self.ciz()

    # ---------- izdüşüm
    def _yansit(self, p):
        x = p[0] - self.merkez[0]; y = p[1] - self.merkez[1]; z = p[2] - self.merkez[2]
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        x, y = x * cy - y * sy, x * sy + y * cy
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        y, z = y * cp - z * sp, y * sp + z * cp
        return x, y, z

    def ciz(self):
        self.delete("all")
        if not self.ucgenler:
            self.create_text(self.winfo_width() / 2, self.winfo_height() / 2,
                             text="STEP dosyası açın", fill="#8a94a6", font=("Segoe UI", 12))
            return
        w, h = self.winfo_width(), self.winfo_height()
        k = min(w, h) / (getattr(self, "_d", 1) * 1.25) * self.olcek
        ox, oy = w / 2 + self.kaydir[0], h / 2 + self.kaydir[1]
        isik = (0.35, -0.55, 0.76)
        liste = []
        for p0, p1, p2, temel in self.ucgenler:
            a, b, c = self._yansit(p0), self._yansit(p1), self._yansit(p2)
            ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
            vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            nn = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
            sh = abs(nx / nn * isik[0] + ny / nn * isik[1] + nz / nn * isik[2])
            liste.append(((a[1] + b[1] + c[1]) / 3, a, b, c, temel, 0.35 + 0.65 * sh))
        for a, b in getattr(self, "teller", []):
            p = self._yansit(a); q = self._yansit(b)
            self.create_line(ox + p[0] * k, oy - p[2] * k,
                             ox + q[0] * k, oy - q[2] * k, fill="#39414f")
        liste.sort(key=lambda t: -t[0])
        for _, a, b, c, temel, sh in liste:
            r = int(temel[1:3], 16); g = int(temel[3:5], 16); bl = int(temel[5:7], 16)
            renk = f"#{int(r*sh):02x}{int(g*sh):02x}{int(bl*sh):02x}"
            self.create_polygon(ox + a[0] * k, oy - a[2] * k,
                                ox + b[0] * k, oy - b[2] * k,
                                ox + c[0] * k, oy - c[2] * k,
                                fill=renk, outline="")
        for p in self.noktalar:
            q = self._yansit(p)
            x, y = ox + q[0] * k, oy - q[2] * k
            self.create_oval(x - 6, y - 6, x + 6, y + 6, fill=RENK_NOKTA, outline="white")
        if self.ok:
            a, b = self._yansit(self.ok[0]), self._yansit(self.ok[1])
            self.create_line(ox + a[0] * k, oy - a[2] * k, ox + b[0] * k, oy - b[2] * k,
                             fill=RENK_OK, width=3, arrow=tk.LAST)


# ============================================================ uygulama
class Uygulama(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pi3D Maker – Adım 1: Referans Belirleme")
        self.geometry("1380x820")
        self.kayit, self.gruplar, self.temaslar = [], [], []
        self.secim, self.puanlar, self.uc = None, [], []
        self.taban = None
        self.kuyruk = queue.Queue()
        self._arayuz()
        self.after(120, self._kuyruk_isle)

    def _arayuz(self):
        ust = ttk.Frame(self, padding=6); ust.pack(fill="x")
        ttk.Button(ust, text="STEP Aç", command=self.dosya_ac).pack(side="left")
        self.yol_lbl = ttk.Label(ust, text="dosya seçilmedi")
        self.yol_lbl.pack(side="left", padx=10)

        orta = ttk.Frame(self); orta.pack(fill="both", expand=True)

        sol = ttk.Frame(orta, padding=4); sol.pack(side="left", fill="y")
        ttk.Label(sol, text="1) Parça / grup seç", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.liste = ttk.Treeview(sol, columns=("k", "kg"), show="tree headings", height=26)
        self.liste.heading("#0", text="grup / parça")
        self.liste.heading("k", text="katı"); self.liste.heading("kg", text="kg")
        self.liste.column("#0", width=300); self.liste.column("k", width=45, anchor="e")
        self.liste.column("kg", width=65, anchor="e")
        self.liste.pack(fill="y", expand=True)
        self.liste.bind("<<TreeviewSelect>>", self.secim_degisti)

        self.gor = Gorunum(orta, width=620)
        self.gor.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        sag = ttk.Frame(orta, padding=4, width=380); sag.pack(side="left", fill="y")
        sag.pack_propagate(False)
        ttk.Label(sag, text="2) Yönlendirme", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.analiz_btn = ttk.Button(sag, text="Analiz Et", command=self.analiz, state="disabled")
        self.analiz_btn.pack(anchor="w", pady=3)
        self.yon_tv = ttk.Treeview(sag, columns=("p", "e", "o", "h"), show="headings", height=7)
        for c, t, w in (("p", "puan", 55), ("e", "iç erişim", 75),
                        ("o", "oturma mm²", 90), ("h", "yük. mm", 70)):
            self.yon_tv.heading(c, text=t); self.yon_tv.column(c, width=w, anchor="e")
        self.yon_tv.pack(fill="x", pady=3)
        self.yon_tv.bind("<<TreeviewSelect>>", self.yon_secildi)

        ttk.Label(sag, text="3) Konumlandırma noktaları",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        self.nokta_tv = ttk.Treeview(sag, columns=("x", "y", "z"), show="headings", height=5)
        for c in ("x", "y", "z"):
            self.nokta_tv.heading(c, text=c.upper()); self.nokta_tv.column(c, width=100, anchor="e")
        self.nokta_tv.pack(fill="x", pady=3)
        self.bilgi = ttk.Label(sag, text="", justify="left", wraplength=360)
        self.bilgi.pack(anchor="w", pady=6)
        self.onay_btn = ttk.Button(sag, text="ONAYLA ve JSON yaz",
                                   command=self.onayla, state="disabled")
        self.onay_btn.pack(anchor="w", pady=6)

        self.durum = ttk.Label(self, text="hazır", relief="sunken", anchor="w")
        self.durum.pack(fill="x", side="bottom")

    # ---------- yardımcı
    def _is(self, fn, bitince):
        def calis():
            try:
                self.kuyruk.put((bitince, fn()))
            except Exception:
                self.kuyruk.put(("hata", traceback.format_exc()))
        threading.Thread(target=calis, daemon=True).start()

    def _kuyruk_isle(self):
        try:
            while True:
                etiket, veri = self.kuyruk.get_nowait()
                if etiket == "hata":
                    self.durum.config(text="hata")
                    messagebox.showerror("Hata", veri[-1500:])
                else:
                    etiket(veri)
        except queue.Empty:
            pass
        self.after(120, self._kuyruk_isle)

    # ---------- olaylar
    def dosya_ac(self):
        yol = filedialog.askopenfilename(
            title="STEP dosyası", filetypes=[("STEP", "*.stp *.step *.STP *.STEP"), ("hepsi", "*.*")])
        if not yol:
            return
        self.yol = yol
        self.yol_lbl.config(text=os.path.basename(yol))
        self.durum.config(text="okunuyor ve gruplanıyor... (büyük dosyada 1-2 dk sürebilir)")
        self._is(lambda: self._oku(yol), self._okundu)

    def _oku(self, yol):
        kayit = E.step_oku(yol)
        gruplar, temaslar, _ = E.temas_grupla(kayit)
        return kayit, gruplar, temaslar

    def _okundu(self, veri):
        self.kayit, self.gruplar, self.temaslar = veri
        self.liste.delete(*self.liste.get_children())
        import re
        from collections import Counter
        for gi, uy in enumerate(self.gruplar, 1):
            kg = sum(E.hacim(self.kayit[i][1]) for i in uy) * E.RHO
            adlar = Counter(re.sub(r"[-_]?\d+$", "", self.kayit[i][0]) for i in uy)
            etiket = f"G{gi:02d}  " + ", ".join(n[:26] for n, _ in adlar.most_common(2))
            ust = self.liste.insert("", "end", iid=f"G{gi}", text=etiket,
                                    values=(len(uy), f"{kg:.2f}"))
            for i in uy[:60]:
                self.liste.insert(ust, "end", iid=f"P{i}",
                                  text="   " + self.kayit[i][0][:40],
                                  values=(1, f"{E.hacim(self.kayit[i][1])*E.RHO:.3f}"))
        self.durum.config(text=f"{len(self.kayit)} katı, {len(self.gruplar)} grup – listeden seçin")
        self.gor.yukle([(sd, False) for _, sd in self.kayit], None)

    def secim_degisti(self, _=None):
        s = self.liste.selection()
        if not s:
            return
        iid = s[0]
        if iid.startswith("G"):
            gi = int(iid[1:]) - 1
            self.secim = ("grup", f"G{gi+1:02d}", self.gruplar[gi])
        else:
            i = int(iid[1:])
            self.secim = ("parca", self.kayit[i][0], [i])
        uy = set(self.secim[2])
        self.gor.noktalar = []; self.gor.ok = None
        self.gor.yukle([(sd, i in uy) for i, (_, sd) in enumerate(self.kayit)], uy)
        kg = sum(E.hacim(self.kayit[i][1]) for i in self.secim[2]) * E.RHO
        self.durum.config(text=f"seçili: {self.secim[1]} – {len(self.secim[2])} katı, {kg:.2f} kg")
        self.analiz_btn.config(state="normal")
        self.onay_btn.config(state="disabled")
        self.yon_tv.delete(*self.yon_tv.get_children())
        self.nokta_tv.delete(*self.nokta_tv.get_children())

    def analiz(self):
        if not self.secim:
            return
        self.analiz_btn.config(state="disabled")
        self.durum.config(text="6 yön için erişim hesaplanıyor...")
        uy = self.secim[2]
        self._is(lambda: E.yon_puanla(self.kayit, uy, self.temaslar), self._analiz_bitti)

    def _analiz_bitti(self, veri):
        self.puanlar, self.ic = veri
        self.yon_tv.delete(*self.yon_tv.get_children())
        for s in self.puanlar:
            self.yon_tv.insert("", "end", iid=s["yon"],
                               values=(f"{s['puan']:.3f}", f"%{s['erisim_orani']*100:.1f}",
                                       f"{s['oturma_mm2']:.0f}", f"{s['yukseklik_mm']:.0f}"))
            self.yon_tv.item(s["yon"], text=s["yon"])
        self.yon_tv.heading("#0", text="yön")
        self.analiz_btn.config(state="normal")
        self.durum.config(text="yön tablosu hazır – bir satır seçin")
        if self.puanlar:
            self.yon_tv.selection_set(self.puanlar[0]["yon"])

    def yon_secildi(self, _=None):
        s = self.yon_tv.selection()
        if not s or not self.secim:
            return
        yon = s[0]
        sec = next(x for x in self.puanlar if x["yon"] == yon)
        self.sec_yon = sec
        self.durum.config(text=f"{yon} için 3 nokta aranıyor...")
        uy = self.secim[2]
        def hesapla():
            er = E.Erisim([self.kayit[i][1] for i in uy])
            return E.uc_nokta(self.kayit, uy, sec["u"], er, self.ic)
        self._is(hesapla, self._nokta_bitti)

    def _nokta_bitti(self, veri):
        self.taban, self.uc = veri
        self.nokta_tv.delete(*self.nokta_tv.get_children())
        for i, p in enumerate(self.uc, 1):
            self.nokta_tv.insert("", "end", values=(f"{p[0]:.2f}", f"{p[1]:.2f}", f"{p[2]:.2f}"))
        self.gor.noktalar = list(self.uc)
        if self.taban:
            c = self.taban["c"]; u = self.sec_yon["u"]
            d = getattr(self.gor, "_d", 100) * 0.35
            self.gor.ok = ((c[0], c[1], c[2]),
                           (c[0] + u[0] * d, c[1] + u[1] * d, c[2] + u[2] * d))
        self.gor.ciz()
        if self.taban and len(self.uc) == 3:
            a = math.dist(self.uc[0], self.uc[1]); b = math.dist(self.uc[1], self.uc[2])
            c2 = math.dist(self.uc[0], self.uc[2]); sp = (a + b + c2) / 2
            alan = math.sqrt(max(sp * (sp - a) * (sp - b) * (sp - c2), 0))
            self.bilgi.config(
                text=f"Oturma yüzeyi {self.taban['alan']:.0f} mm², "
                     f"normal {tuple(round(v,2) for v in self.taban['n'])}\n"
                     f"Üçgen kenarları {a:.0f} / {b:.0f} / {c2:.0f} mm, alan {alan:.0f} mm²\n"
                     f"Yeşil ok = yukarı yönü, kırmızı toplar = dayama noktaları")
            self.onay_btn.config(state="normal")
            self.durum.config(text="onayınızı bekliyor")
        else:
            self.bilgi.config(text="Bu yönde 3 nokta bulunamadı, başka yön seçin.")
            self.onay_btn.config(state="disabled")
            self.durum.config(text="3 nokta bulunamadı")

    def onayla(self):
        yol = filedialog.asksaveasfilename(defaultextension=".json",
                                           initialfile=f"referans_{self.secim[1]}.json",
                                           filetypes=[("JSON", "*.json")])
        if not yol:
            return
        kg = sum(E.hacim(self.kayit[i][1]) for i in self.secim[2]) * E.RHO
        json.dump({"dosya": os.path.basename(self.yol), "secim": self.secim[1],
                   "kati_sayisi": len(self.secim[2]), "agirlik_kg": round(kg, 3),
                   "parcalar": [self.kayit[i][0] for i in self.secim[2]],
                   "yon_siralamasi": self.puanlar, "secilen_yon": self.sec_yon["yon"],
                   "datum_A": {"alan_mm2": round(self.taban["alan"], 1),
                               "normal": [round(v, 4) for v in self.taban["n"]],
                               "merkez": [round(v, 2) for v in self.taban["c"]]},
                   "uc_nokta": [[round(v, 2) for v in p] for p in self.uc],
                   "onay": True},
                  open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        self.durum.config(text=f"onaylandı -> {os.path.basename(yol)}")
        messagebox.showinfo("Onaylandı", f"Referans kaydedildi:\n{yol}")


if __name__ == "__main__":
    Uygulama().mainloop()
