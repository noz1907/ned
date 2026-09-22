"""
Pi3D – DXF -> 3D STEP DÖNÜŞTÜRÜCÜ
======================================
Parça ya da fikstür fark etmeksizin, bir DXF'i 3B katıya çevirip STEP yazar.

Üç çalışma kipi vardır, dosyaya bakarak kendisi seçer:

  1. DOGRUDAN   DXF zaten 3B taşıyorsa (3DFACE / MESH / POLYFACE / Z'si değişen
                polyline) kabuk kurulur, katıya kapatılır.
  2. EKSTRUZYON Tek bir 2B bölge varsa (sac açınımı, plaka konturu) verilen
                kalınlıkta şişirilir.   --kalinlik 15
  3. KESISIM    Hizalı 2+ ortografik görünüş varsa (ÖN/ÜST/SAĞ ...) her görünüş
                kendi ekseni boyunca prizmaya çevrilir ve prizmalar kesiştirilir
                (görsel kabuk). Prizmatik parçalarda sonuç birebir doğrudur.

    python pfd_dxf2stp.py cizim.dxf                    # kipi kendi seçer
    python pfd_dxf2stp.py cizim.dxf --liste            # bölge/görünüş raporu
    python pfd_dxf2stp.py cizim.dxf --kalinlik 15      # ekstrüzyon kipini zorla
    python pfd_dxf2stp.py cizim.dxf --bolge 2 --gorunus "ON=XZ,SAG=YZ,ALT=XY"

Çıktılar:  <o>.step / <o>.stp, <o>_kontrol.png (ne anladığını gösterir), <o>.json
"""
from __future__ import annotations
import argparse, json, math, os, re, sys, time
from collections import Counter, defaultdict

import ezdxf
from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import polygonize, unary_union

# ---------------------------------------------------------------- ayarlar
VARSAYILAN = dict(
    yay_bolme=48,          # daire/yay kaç doğru parçasına bölünsün
    kaynastir=0.02,        # bu mesafeden yakın uç noktalar aynı sayılır (mm)
    min_alan=1.0,          # bundan küçük poligonlar atılır (mm²)
    kume_hucre=None,       # bölge kümeleme hücre boyu (None = otomatik)
    hiza_tol=0.02,         # görünüş hizalama toleransı (bölge boyuna oran)
    uzun_oran=0.90,        # hem eni hem boyu bu oranı aşan atom sayfa çerçevesidir
    sayfa_orani=0.40,      # çizim alanının bu oranından büyük yüz sayfa sayılır, atılır
    gizli_kat=r"GIZLI|GİZLİ|HIDDEN|DASHED|KESIK",   # gizli çizgi katmanları
    delik="ic",            # "ic": dışa değmeyen kapalı bölgeler delik sayılır, "yok": doldur
    min_segment=4,         # bir bölge en az bu kadar segment içermeli
    etiket_grup=True,      # aynı renk + aynı görünüş yazısı = tek görünüş
    gorunus_bosluk=3.0,    # görünüş boşluğu, çizimin tipik görünüş aralığının bu katını aşamaz
)

# görünüş adı -> (yatay eksen, dikey eksen) ; 3B eksenler X=0, Y=1, Z=2
GORUNUS_EKSEN = {
    "ON":   (0, 2), "ÖN": (0, 2), "FRONT": (0, 2),
    "ARKA": (0, 2), "BACK": (0, 2),
    "UST":  (0, 1), "ÜST": (0, 1), "TOP": (0, 1),
    "ALT":  (0, 1), "BOTTOM": (0, 1), "PLAN": (0, 1),
    "SAG":  (1, 2), "SAĞ": (1, 2), "RIGHT": (1, 2),
    "SOL":  (1, 2), "LEFT": (1, 2),
    "YAN":  (1, 2), "SIDE": (1, 2),
}
# görünüşün baktığı eksen (prizmanın süpürüleceği yön)
GORUNUS_NORMAL = {(0, 2): 1, (0, 1): 2, (1, 2): 0}


def _tr(s):
    """Türkçe harfleri sadeleştirip büyütür (etiket eşlemesi için)."""
    d = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iISSgGuUoOcC")
    return s.translate(d).upper().strip()


# ================================================================ 1. OKUMA
class Cizim:
    """DXF'ten toplanan sadeleştirilmiş geometri."""

    def __init__(self, yol, P):
        self.yol, self.P = yol, P
        self.segment = []      # ((x0,y0,z0),(x1,y1,z1), katman)
        self.atom = []         # {"seg": [...], "kat": str, "kutu": (x0,y0,x1,y1)}
        self.uc3b = []         # 3B yüzler: [(p0,p1,p2[,p3]), katman]
        self.metin = []        # (yazi, x, y)
        self.uc_bulundu = False
        self._oku()

    # ---------- varlık dönüştürücüler
    def _yay(self, c, r, a0, a1, n):
        if a1 < a0:
            a1 += 360.0
        return [(c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)), c[2])
                for a in [a0 + (a1 - a0) * i / n for i in range(n + 1)]]

    def _renk(self, e):
        """Varlığın renk anahtarı: gerçek renk varsa o, yoksa ACI (katmandan çözülür).

        Çizimlerde her parça çoğu kez ayrı renkle çizilir; bu, hangi görünüşün
        hangi parçaya ait olduğunu söyleyen en güvenilir bilgidir."""
        tc = getattr(e.dxf, "true_color", None)
        if tc is not None:
            return ("T", int(tc))
        c = e.dxf.color
        if c in (256, None):                      # BYLAYER
            c = self.kat_renk.get(e.dxf.layer, 7)
        elif c == 0:                              # BYBLOCK
            c = 7
        return ("A", int(c))

    def _ekle_zincir(self, pts, kat):
        """Bir DXF varlığını segment zincirine çevirir ve tek ATOM olarak saklar.

        Atom = bölünmez çizim nesnesi. Kümeleme atomlar üzerinden yapılır;
        böylece ölçek, çizimin dış ölçüsünden bağımsız kalır."""
        yeni = []
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) > 1e-9 or abs(a[1] - b[1]) > 1e-9 or abs(a[2] - b[2]) > 1e-9:
                s = (a, b, kat)
                self.segment.append(s); yeni.append(s)
        if yeni:
            xs = [p[0] for a, b, _ in yeni for p in (a, b)]
            ys = [p[1] for a, b, _ in yeni for p in (a, b)]
            self.atom.append({"seg": yeni, "kat": kat, "renk": self._son_renk,
                              "kutu": (min(xs), min(ys), max(xs), max(ys))})

    def _varlik(self, e, dh=None):
        t = e.dxftype()
        kat = e.dxf.layer
        n = self.P["yay_bolme"]
        try:
            self._son_renk = self._renk(e)
        except Exception:
            self._son_renk = ("A", 7)
        try:
            if t == "LINE":
                s, k = e.dxf.start, e.dxf.end
                self._ekle_zincir([(s.x, s.y, s.z), (k.x, k.y, k.z)], kat)
            elif t == "LWPOLYLINE":
                z = float(e.dxf.elevation or 0.0)
                p = [(a, b, z) for a, b in e.get_points("xy")]
                if e.closed and len(p) > 2:
                    p = p + [p[0]]
                self._ekle_zincir(p, kat)
            elif t == "POLYLINE":
                if e.is_poly_face_mesh or e.is_polygon_mesh:
                    for f in e.faces() if e.is_poly_face_mesh else []:
                        v = [(q.dxf.location.x, q.dxf.location.y, q.dxf.location.z) for q in f]
                        if len(v) >= 3:
                            self.uc3b.append((v[:4], kat)); self.uc_bulundu = True
                    return
                p = [(v.dxf.location.x, v.dxf.location.y, v.dxf.location.z) for v in e.vertices]
                if e.is_closed and len(p) > 2:
                    p = p + [p[0]]
                self._ekle_zincir(p, kat)
            elif t == "CIRCLE":
                c = e.dxf.center
                self._ekle_zincir(self._yay((c.x, c.y, c.z), e.dxf.radius, 0, 360, n), kat)
            elif t == "ARC":
                c = e.dxf.center
                self._ekle_zincir(self._yay((c.x, c.y, c.z), e.dxf.radius,
                                            e.dxf.start_angle, e.dxf.end_angle, n), kat)
            elif t == "ELLIPSE":
                p = [(q.x, q.y, q.z) for q in e.flattening(0.05)]
                self._ekle_zincir(p, kat)
            elif t == "SPLINE":
                p = [(q.x, q.y, q.z) for q in e.flattening(0.05)]
                self._ekle_zincir(p, kat)
            elif t == "3DFACE":
                v = [(e.dxf.vtx0.x, e.dxf.vtx0.y, e.dxf.vtx0.z),
                     (e.dxf.vtx1.x, e.dxf.vtx1.y, e.dxf.vtx1.z),
                     (e.dxf.vtx2.x, e.dxf.vtx2.y, e.dxf.vtx2.z),
                     (e.dxf.vtx3.x, e.dxf.vtx3.y, e.dxf.vtx3.z)]
                if math.dist(v[2], v[3]) < 1e-9:
                    v = v[:3]
                self.uc3b.append((v, kat)); self.uc_bulundu = True
            elif t == "MESH":
                mb = e.get_data()
                vt = [tuple(q) for q in mb.vertices]
                for f in mb.faces:
                    if len(f) >= 3:
                        self.uc3b.append(([vt[i] for i in f[:4]], kat)); self.uc_bulundu = True
            elif t in ("TEXT", "MTEXT"):
                p = e.dxf.insert
                yazi = e.dxf.text if t == "TEXT" else e.text
                self.metin.append((str(yazi), p.x, p.y))
        except Exception:
            pass

    def _oku(self):
        d = ezdxf.readfile(self.yol)
        self.dxfversion = d.dxfversion
        self.kat_renk = {l.dxf.name: l.dxf.color for l in d.layers}
        self._son_renk = ("A", 7)
        msp = d.modelspace()
        for e in msp:
            self._varlik(e)
        # blokları yerinde patlat (iç içe INSERT'ler dahil)
        for ins in msp.query("INSERT"):
            try:
                for e in ins.virtual_entities():
                    if e.dxftype() == "INSERT":
                        for e2 in e.virtual_entities():
                            self._varlik(e2)
                    else:
                        self._varlik(e)
            except Exception:
                pass
        # 3B mi? z değerleri değişiyorsa evet
        zs = set()
        for a, b, _ in self.segment:
            zs.add(round(a[2], 4)); zs.add(round(b[2], 4))
            if len(zs) > 3:
                break
        self.z_degisken = len(zs) > 1
        self.uc_bulundu = self.uc_bulundu or bool(self.uc3b)

    # ---------- yardımcılar
    def kutu(self, segler=None):
        s = segler if segler is not None else self.segment
        if not s:
            return None
        xs = [p[0] for a, b, _ in s for p in (a, b)]
        ys = [p[1] for a, b, _ in s for p in (a, b)]
        return min(xs), min(ys), max(xs), max(ys)

    def ozet(self):
        return {"dosya": os.path.basename(self.yol), "surum": self.dxfversion,
                "segment": len(self.segment), "3b_yuz": len(self.uc3b),
                "z_degisken": self.z_degisken,
                "katman": dict(Counter(k for _, _, k in self.segment).most_common(12)),
                "metin": [t[0] for t in self.metin][:20]}


# ================================================================ 2. BÖLGE
def cerceve_ayikla(atomlar, oran):
    """Sayfa çerçevesi ayıklanır.

    Çerçeve, çizimin HEM enini HEM boyunu kaplayan atomdur. Yalnız uzunluğa
    bakmak yanlıştır: uzun bir parçanın kenarı da uzundur, o parçanın kendisidir.
    """
    xs = [k for a in atomlar for k in (a["kutu"][0], a["kutu"][2])]
    ys = [k for a in atomlar for k in (a["kutu"][1], a["kutu"][3])]
    GX, GY = max(xs) - min(xs), max(ys) - min(ys)
    kal, atil = [], []
    for a in atomlar:
        k = a["kutu"]
        cerceve = (k[2] - k[0]) > oran * GX and (k[3] - k[1]) > oran * GY
        (atil if cerceve else kal).append(a)
    return kal, atil


def kutu_kumele(atomlar, pay=0.0):
    """Atomları SINIR KUTUSU ÖRTÜŞMESİNE göre kümeler; atom indeksleri döner.

    Tek kural: kutuları kesişen (paya kadar yaklaşan) atomlar aynı nesnedir.
    Birleşim-bulma geçişliliği tek geçişte hallettiği için tur gerekmez.
    Ölçekten bağımsızdır: yan yana duran ayrı görünüşlerin kutuları kesişmez,
    bir görünüşün kopuk gizli-çizgi parçalarının kutuları ise kesişir.
    Izgara yalnız hızlandırmadır, sonucu değiştirmez."""
    n = len(atomlar)
    if n == 0:
        return []
    kutular = [a["kutu"] for a in atomlar]
    boy = sorted(max(k[2] - k[0], k[3] - k[1]) for k in kutular)
    h = max(boy[len(boy) // 2], boy[-1] / 2000.0, 1e-9)
    kova = defaultdict(list)
    for i, k in enumerate(kutular):
        gx0, gx1 = int(math.floor((k[0] - pay) / h)), int(math.floor((k[2] + pay) / h))
        gy0, gy1 = int(math.floor((k[1] - pay) / h)), int(math.floor((k[3] + pay) / h))
        if (gx1 - gx0 + 1) * (gy1 - gy0 + 1) > 4000:
            adim_x = max(1, (gx1 - gx0) // 60)
            adim_y = max(1, (gy1 - gy0) // 60)
        else:
            adim_x = adim_y = 1
        for gx in range(gx0, gx1 + 1, adim_x):
            for gy in range(gy0, gy1 + 1, adim_y):
                kova[(gx, gy)].append(i)
    ebeveyn = list(range(n))

    def kok(x):
        while ebeveyn[x] != x:
            ebeveyn[x] = ebeveyn[ebeveyn[x]]; x = ebeveyn[x]
        return x

    for lst in kova.values():
        for ai in range(len(lst)):
            a = lst[ai]; ka = kutular[a]
            for bi in range(ai + 1, len(lst)):
                b = lst[bi]; kb = kutular[b]
                if (ka[2] + pay < kb[0] or kb[2] + pay < ka[0]
                        or ka[3] + pay < kb[1] or kb[3] + pay < ka[1]):
                    continue
                ra, rb = kok(a), kok(b)
                if ra != rb:
                    ebeveyn[ra] = rb
    gr = defaultdict(list)
    for i in range(n):
        gr[kok(i)].append(i)
    return sorted(gr.values(), key=lambda v: -len(v))


def yuzle_renk(ciz, P):
    """Her rengi AYRI polygonize eder: renk = parça kimliği.

    Böylece üst üste çizilmiş parçalar birbirine karışmaz ve bir görünüşün
    hangi parçaya ait olduğu tahmin edilmek zorunda kalmaz."""
    atom, cerceve = cerceve_ayikla(ciz.atom, P["uzun_oran"])
    if not atom:
        atom, cerceve = ciz.atom, []
    gz = re.compile(P["gizli_kat"], re.I)
    k = P["kaynastir"]
    gruplar = defaultdict(list)
    for a in atom:
        if gz.search(a["kat"]):
            continue
        gruplar[a.get("renk", ("A", 7))].append(a)
    cikti = {}
    for renk, lst in gruplar.items():
        cizgi = []
        for a in lst:
            for p, q, _ in a["seg"]:
                p2 = (round(p[0] / k) * k, round(p[1] / k) * k)
                q2 = (round(q[0] / k) * k, round(q[1] / k) * k)
                if p2 != q2:
                    cizgi.append(LineString([p2, q2]))
        if not cizgi:
            continue
        yuz = [p for p in polygonize(unary_union(cizgi)) if p.area >= P["min_alan"]]
        yuz = grup_cercevesi_at(yuz, P)
        if yuz:
            cikti[renk] = (yuz, lst)
    return cikti, cerceve


def yuzle(ciz, P):
    """Çizimin TAMAMINI bir kerede kapalı yüzlere çevirir.

    Tek tek çizgileri kümelemek yerine önce yüzleri çıkarmak, ince çizgili
    (seyrek) çizimlerde de sağlam çalışır: bir görünüşün yüzleri birbirine
    değer, ayrı görünüşlerinki değmez."""
    atom, cerceve = cerceve_ayikla(ciz.atom, P["uzun_oran"])
    if not atom:
        atom, cerceve = ciz.atom, []
    k = P["kaynastir"]
    gz = re.compile(P["gizli_kat"], re.I)
    cizgi = []
    for a in atom:
        if gz.search(a["kat"]):
            continue                      # gizli çizgi kontur oluşturmaz
        for p, q, _ in a["seg"]:
            p2 = (round(p[0] / k) * k, round(p[1] / k) * k)
            q2 = (round(q[0] / k) * k, round(q[1] / k) * k)
            if p2 != q2:
                cizgi.append(LineString([p2, q2]))
    if not cizgi:
        return [], cerceve, atom
    birlesik = unary_union(cizgi)
    yuzler = [p for p in polygonize(birlesik) if p.area >= P["min_alan"]]
    # sayfa büyüklüğünde bir yüz oluştuysa (çerçeve içi boşluk) at
    if yuzler:
        xs = [v for p in yuzler for v in (p.bounds[0], p.bounds[2])]
        ys = [v for p in yuzler for v in (p.bounds[1], p.bounds[3])]
        sayfa = max(xs) - min(xs), max(ys) - min(ys)
        esik = P["sayfa_orani"] * sayfa[0] * sayfa[1]
        yuzler = [p for p in yuzler if p.area < esik] or yuzler
    yuzler = grup_cercevesi_at(yuzler, P)
    return yuzler, cerceve, atom


def grup_cercevesi_at(yuzler, P):
    """Görünüş kümesini kutulayan dikdörtgen çerçeveleri ayıklar.

    Çizimlerde parça grupları çoğu kez ince bir dikdörtgenle çerçevelenir.
    Bu dikdörtgen bir parça değildir; bırakılırsa içindeki görünüşlerle
    birleşip yanlış nesne üretir. Ölçüt: dikdörtgen olacak (alanı kutusuna
    eşit) ve içinde, sınırına değmeyen en az iki yüz bulunacak."""
    from shapely.strtree import STRtree
    if len(yuzler) < 3:
        return yuzler
    agac = STRtree(yuzler)
    at = set()
    for i, p in enumerate(yuzler):
        b = p.bounds
        kutu_alan = (b[2] - b[0]) * (b[3] - b[1])
        # DIŞ halkası dikdörtgen mi? (içi görünüşlerle delinmiş olabilir)
        dis_alan = Polygon(p.exterior).area if len(p.exterior.coords) > 3 else 0.0
        if kutu_alan <= 0 or dis_alan < 0.98 * kutu_alan:
            continue                       # dikdörtgen değil
        ic = 0
        for j in agac.query(p):
            j = int(j)
            if j == i or j in at:
                continue
            q = yuzler[j]
            if (q.area < dis_alan and q.within(Polygon(p.exterior))
                    and not q.exterior.intersects(p.exterior)):
                ic += 1
                if ic >= 2:
                    break
        if ic >= 2:
            at.add(i)
    return [p for i, p in enumerate(yuzler) if i not in at] if at else yuzler


def poligon_kumele(yuzler):
    """Birbirine değen yüzleri kümeler (STRtree ile hızlandırılmış)."""
    from shapely.strtree import STRtree
    n = len(yuzler)
    if n == 0:
        return []
    agac = STRtree(yuzler)
    ebeveyn = list(range(n))

    def kok(x):
        while ebeveyn[x] != x:
            ebeveyn[x] = ebeveyn[ebeveyn[x]]; x = ebeveyn[x]
        return x

    for i, p in enumerate(yuzler):
        for j in agac.query(p):
            j = int(j)
            if j <= i:
                continue
            if p.intersects(yuzler[j]):
                ra, rb = kok(i), kok(j)
                if ra != rb:
                    ebeveyn[ra] = rb
    gr = defaultdict(list)
    for i in range(n):
        gr[kok(i)].append(i)
    return sorted(gr.values(), key=lambda v: -sum(yuzler[i].area for i in v))


class Bolge:
    """Çizimin bir nesnesi: tek bir görünüş ya da tek bir parça konturu."""

    def __init__(self, no, poligonlar, metinler, atomlar=None, renk=None):
        self.no = no
        self.renk = renk
        self.poligon = list(poligonlar)
        self.atom = atomlar or []
        self.segment = [s for a in self.atom for s in a["seg"]]
        self.katman = Counter(a["kat"] for a in self.atom)
        x0 = min(p.bounds[0] for p in self.poligon)
        y0 = min(p.bounds[1] for p in self.poligon)
        x1 = max(p.bounds[2] for p in self.poligon)
        y1 = max(p.bounds[3] for p in self.poligon)
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.g, self.y = x1 - x0, y1 - y0
        self.merkez = ((x0 + x1) / 2, (y0 + y1) / 2)
        self.etiket = self._etiket(metinler)
        self._alan = None

    def _etiket(self, metinler):
        """Bölgenin yakınındaki görünüş adını bulur (ON, UST, SAG ...)."""
        en, mesafe = None, 1e18
        for yazi, mx, my in metinler:
            ad = _tr(yazi)
            if ad not in GORUNUS_EKSEN:
                continue
            dx = max(self.x0 - mx, 0, mx - self.x1)
            dy = max(self.y0 - my, 0, my - self.y1)
            m = math.hypot(dx, dy)
            if m < mesafe and m < 0.9 * max(self.g, self.y):
                en, mesafe = ad, m
        return en

    def poligonla(self, P=None):
        return self.poligon

    def dolu_alan(self, P=None):
        """Görünüşün dolu alanı; içteki kapalı bölgeler delik olarak korunur.

        Kural: dış sınıra değmeyen kapalı bölge deliktir (P["delik"]=="ic").
        Böylece üstten görülen bir delik, o görünüşün prizmasından çıkar."""
        if self._alan is not None:
            return self._alan
        if not self.poligon:
            return None
        dolu = unary_union(self.poligon)
        P = P or {}
        if P.get("delik", "ic") == "ic":
            parcalar = list(dolu.geoms) if dolu.geom_type == "MultiPolygon" else [dolu]
            kalan = []
            for pr in parcalar:
                dis = pr.exterior
                ic = [p for p in self.poligon
                      if p.within(pr) and not p.exterior.intersects(dis)]
                self.delik_sayisi = len(ic)
                kalan.append(pr.difference(unary_union(ic)) if ic else pr)
            dolu = unary_union(kalan)
        self._alan = dolu
        return dolu

    def ozet(self, P=None):
        a = self.dolu_alan()
        return {"no": self.no, "renk": list(self.renk) if self.renk else None,
                "etiket": self.etiket, "segment": len(self.segment),
                "x": [round(self.x0, 2), round(self.x1, 2)],
                "y": [round(self.y0, 2), round(self.y1, 2)],
                "genislik": round(self.g, 2), "yukseklik": round(self.y, 2),
                "yuz": len(self.poligon), "alan": round(a.area, 1) if a else 0.0,
                "katman": dict(self.katman)}


def kapsanan_birlestir(bolgeler, pay=0.5):
    """Kutusu bir başkasının içinde kalan bölgeleri ona katar.

    Bir görünüşün içindeki delik çemberleri, iç konturlar ve kopuk ayrıntılar
    ayrı bölge gibi görünür; oysa aynı görünüşün parçasıdır. Ayrı bir görünüş
    başka bir görünüşün kutusunun içinde durmaz."""
    if len(bolgeler) < 2:
        return bolgeler
    sira = sorted(bolgeler, key=lambda b: -(b.g * b.y))
    kalan, yutulan = [], set()
    for i, b in enumerate(sira):
        if id(b) in yutulan:
            continue
        katilan = []
        for c in sira[i + 1:]:
            if id(c) in yutulan:
                continue
            if (c.x0 >= b.x0 - pay and c.x1 <= b.x1 + pay
                    and c.y0 >= b.y0 - pay and c.y1 <= b.y1 + pay):
                katilan.append(c); yutulan.add(id(c))
        if katilan:
            b.poligon = b.poligon + [p for c in katilan for p in c.poligon]
            b.atom = b.atom + [a for c in katilan for a in c.atom]
            b.segment = [s for a in b.atom for s in a["seg"]]
            b._alan = None
        kalan.append(b)
    for i, b in enumerate(kalan, 1):
        b.no = i
    return kalan


def _yakin_obek(lst):
    """Aralarındaki boşluk kendi ölçülerinden küçük olan bölgeleri öbekler,
    en büyük öbeği döndürür."""
    if len(lst) < 2:
        return lst
    n = len(lst)
    ebeveyn = list(range(n))

    def kok(x):
        while ebeveyn[x] != x:
            ebeveyn[x] = ebeveyn[ebeveyn[x]]; x = ebeveyn[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            a, b = lst[i], lst[j]
            dx = max(b.x0 - a.x1, a.x0 - b.x1, 0.0)
            dy = max(b.y0 - a.y1, a.y0 - b.y1, 0.0)
            olcek = max(a.g, a.y, b.g, b.y)
            if math.hypot(dx, dy) <= 0.5 * olcek:
                ra, rb = kok(i), kok(j)
                if ra != rb:
                    ebeveyn[ra] = rb
    gr = defaultdict(list)
    for i in range(n):
        gr[kok(i)].append(lst[i])
    return max(gr.values(), key=lambda v: sum(b.g * b.y for b in v))


def etikete_gore_birlestir(bolgeler, metinler):
    """Aynı renkteki ve aynı GÖRÜNÜŞ YAZISININ altındaki bölgeleri birleştirir.

    Kesit görünüşlerinde malzeme kopuk olabilir (C profilin yandan görünüşü iki
    ayrı şerittir); bunlar ayrı görünüş değil, aynı görünüşün parçalarıdır.
    Çizimdeki ON/ÜST/SAĞ yazıları hangi bölgenin hangi görünüşe ait olduğunu
    söyler; en yakın yazıya göre gruplanır."""
    etiketler = [(_tr(t[0]), t[1], t[2]) for t in metinler if _tr(t[0]) in GORUNUS_EKSEN]
    if not etiketler:
        return bolgeler
    grup = defaultdict(list)
    for b in bolgeler:
        cx, cy = b.merkez
        ad, _, _ = min(etiketler, key=lambda t: math.hypot(t[1] - cx, t[2] - cy))
        grup[(b.renk, ad)].append(b)
    yeni = []
    for (renk, ad), lst in grup.items():
        # Aynı renk bir görünüşte birkaç kez geçebilir (aynı parçanın iki
        # kopyası). Yakın duranlar tek görünüşün parçasıdır, uzak duranlar
        # ayrı kopyadır: en büyük öbek alınır.
        lst = _yakin_obek(lst)
        ana = max(lst, key=lambda b: b.g * b.y)
        if len(lst) > 1:
            ana.poligon = [p for b in lst for p in b.poligon]
            ana.atom = [a for b in lst for a in b.atom]
            ana.segment = [s for a in ana.atom for s in a["seg"]]
            ana._alan = None
            xs = [v for b in lst for v in (b.x0, b.x1)]
            ys = [v for b in lst for v in (b.y0, b.y1)]
            ana.x0, ana.x1, ana.y0, ana.y1 = min(xs), max(xs), min(ys), max(ys)
            ana.g, ana.y = ana.x1 - ana.x0, ana.y1 - ana.y0
            ana.merkez = ((ana.x0 + ana.x1) / 2, (ana.y0 + ana.y1) / 2)
        ana.etiket = ad
        yeni.append(ana)
    for i, b in enumerate(sorted(yeni, key=lambda b: -(b.g * b.y)), 1):
        b.no = i
    return sorted(yeni, key=lambda b: -(b.g * b.y))


def bolgele_renk(ciz, P):
    """Renge göre bölgeleme: her renk kendi içinde görünüşlere ayrılır."""
    renk_yuz, cerceve = yuzle_renk(ciz, P)
    bolgeler = []
    for renk, (yuzler, atomlar) in sorted(renk_yuz.items(),
                                          key=lambda t: -sum(p.area for p in t[1][0])):
        kume = poligon_kumele(yuzler)
        kutular = []
        for kk in kume:
            xs = [v for i in kk for v in (yuzler[i].bounds[0], yuzler[i].bounds[2])]
            ys = [v for i in kk for v in (yuzler[i].bounds[1], yuzler[i].bounds[3])]
            kutular.append((min(xs), min(ys), max(xs), max(ys)))
        atom_kume = defaultdict(list)
        for a in atomlar:
            kb0 = a["kutu"]
            cx, cy = (kb0[0] + kb0[2]) / 2, (kb0[1] + kb0[3]) / 2
            for gi, kb in enumerate(kutular):
                if kb[0] - 1e-6 <= cx <= kb[2] + 1e-6 and kb[1] - 1e-6 <= cy <= kb[3] + 1e-6:
                    atom_kume[gi].append(a); break
        bu_renk = []
        for gi, kk in enumerate(kume):
            b = Bolge(len(bu_renk) + 1, [yuzler[i] for i in kk], ciz.metin,
                      atom_kume.get(gi), renk)
            if b.g > 1e-9 and b.y > 1e-9:
                bu_renk.append(b)
        bolgeler += kapsanan_birlestir(bu_renk)
    if P.get("etiket_grup", True):
        bolgeler = etikete_gore_birlestir(bolgeler, ciz.metin)
    for i, b in enumerate(bolgeler, 1):
        b.no = i
    return bolgeler, cerceve, None


def bolgele(ciz, P):
    """Çizimi nesnelere ayırır: her nesne bir görünüş ya da bir parça konturu."""
    yuzler, cerceve, atom = yuzle(ciz, P)
    if not yuzler:
        return [], cerceve, None
    kume = poligon_kumele(yuzler)
    # atomları, kutusu hangi kümeye düşüyorsa ona ilişkilendir (rapor için)
    kutular = []
    for kk in kume:
        xs = [v for i in kk for v in (yuzler[i].bounds[0], yuzler[i].bounds[2])]
        ys = [v for i in kk for v in (yuzler[i].bounds[1], yuzler[i].bounds[3])]
        kutular.append((min(xs), min(ys), max(xs), max(ys)))
    atom_kume = defaultdict(list)
    for a in atom:
        k = a["kutu"]
        cx, cy = (k[0] + k[2]) / 2, (k[1] + k[3]) / 2
        for gi, kb in enumerate(kutular):
            if kb[0] - 1e-6 <= cx <= kb[2] + 1e-6 and kb[1] - 1e-6 <= cy <= kb[3] + 1e-6:
                atom_kume[gi].append(a); break
    bolgeler = []
    for gi, kk in enumerate(kume):
        b = Bolge(len(bolgeler) + 1, [yuzler[i] for i in kk], ciz.metin, atom_kume.get(gi))
        if b.g > 1e-9 and b.y > 1e-9:
            bolgeler.append(b)
    return bolgeler, cerceve, None


# ============================================================ 3. GÖRÜNÜŞ EŞLEME
def _ortusme(a0, a1, b0, b1):
    """İki aralığın örtüşme oranı (küçük olana göre)."""
    o = min(a1, b1) - max(a0, b0)
    k = min(a1 - a0, b1 - b0)
    return o / k if k > 1e-9 else 0.0


def _daire_mi(b, tol=0.06):
    """Bölgenin dolu alanı tek bir daire mi? (bir görünüşün tamamı daireyse
    o görünüş dönel bir yüzeyin karşıdan görünüşüdür)."""
    if abs(b.g - b.y) > tol * max(b.g, b.y):
        return False
    a = b.dolu_alan()
    if a is None or a.geom_type != "Polygon" or a.interiors:
        return False
    daire_alan = math.pi * 0.25 * b.g * b.y
    return abs(a.area - daire_alan) <= tol * daire_alan


def nesne_esle_renk(bolgeler, P):
    """Renk kipi: aynı RENK = aynı parça. Görünüş rolleri yazılardan gelir.

    Geometrik tahmine hiç gerek kalmaz; hangi görünüşün hangi parçaya ait
    olduğunu çizimin kendisi (renk) söyler."""
    grup = defaultdict(list)
    for b in bolgeler:
        grup[b.renk].append(b)
    nesneler = []
    for renk, lst in sorted(grup.items(), key=lambda t: -sum(b.g * b.y for b in t[1])):
        n = Nesne(len(nesneler) + 1, lst, [])
        for b in lst:
            if b.etiket in GORUNUS_EKSEN:
                n.rol[b.no] = b.etiket
        nesneler.append(n)
    return nesneler


def nesne_esle(bolgeler, P):
    """Aynı cismin farklı görünüşlerini tek NESNE altında toplar.

    Ortografik çizimde bir cismin görünüşleri hizalıdır:
      - aynı SATIRDA duranlar aynı yüksekliği paylaşır  (ön - yan)
      - aynı SÜTUNDA duranlar aynı genişliği paylaşır   (ön - üst)
    Bu iki hizadan birini sağlayan ve ölçüsü tutan bölgeler eşlenir.
    """
    tol = P["hiza_tol"]
    n = len(bolgeler)
    ebeveyn = list(range(n))

    def kok(x):
        while ebeveyn[x] != x:
            ebeveyn[x] = ebeveyn[ebeveyn[x]]; x = ebeveyn[x]
        return x

    maks_bosluk = P.get("gorunus_bosluk", 1.5)
    aday = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = bolgeler[i], bolgeler[j]
            if a.renk is not None and b.renk is not None and a.renk != b.renk:
                continue                   # ayrı renk = ayrı parça
            # satır hizası: Y aralıkları örtüşür ve yükseklikler eşit
            satir = (_ortusme(a.y0, a.y1, b.y0, b.y1) > 0.9
                     and abs(a.y - b.y) <= tol * max(a.y, b.y))
            # sütun hizası: X aralıkları örtüşür ve genişlikler eşit
            sutun = (_ortusme(a.x0, a.x1, b.x0, b.x1) > 0.9
                     and abs(a.g - b.g) <= tol * max(a.g, b.g))
            if not (satir or sutun):
                continue
            # aynı yerde üst üste duran iki bölge görünüş çifti değildir
            if _ortusme(a.x0, a.x1, b.x0, b.x1) > 0.5 and _ortusme(a.y0, a.y1, b.y0, b.y1) > 0.5:
                continue
            # İKİ GÖRÜNÜŞ DE DAİRE İSE bunlar aynı cismin iki görünüşü olamaz:
            # dönel bir cisim yandan dikdörtgen görünür. Aynı yuvarlak öğenin
            # iki kopyasıdır (cıvata başı, pim vb.).
            if _daire_mi(a) and _daire_mi(b):
                continue
            # KOMŞULUK: görünüşler yan yana durur. Aradaki boşluk, küçük olanın
            # ölçüsünün katından büyükse bunlar aynı cismin görünüşü değildir.
            if satir:
                bosluk = max(b.x0 - a.x1, a.x0 - b.x1)
                olcek = min(a.g, b.g)
            else:
                bosluk = max(b.y0 - a.y1, a.y0 - b.y1)
                olcek = min(a.y, b.y)
            aday.append((max(bosluk, 0.0), i, j, "satir" if satir else "sutun", olcek))

    # BOŞLUK EŞİĞİ çizimin kendi görünüş aralığından türetilir: her bölgenin
    # en yakın hizalı komşusuna olan uzaklığının ortancası, bu çizimde bir
    # cismin görünüşleri arasındaki tipik boşluktur.
    if aday:
        enyakin = {}
        for bosluk, i, j, yon, olcek in aday:
            enyakin[i] = min(enyakin.get(i, 1e18), bosluk)
            enyakin[j] = min(enyakin.get(j, 1e18), bosluk)
        dizi = sorted(enyakin.values())
        tipik = dizi[len(dizi) // 2] if dizi else 0.0
        esik = max(maks_bosluk * max(tipik, 1e-9), 1e-9)
        aday = [t for t in aday if t[0] <= esik]
    aday = [(t[0], t[1], t[2], t[3]) for t in aday]

    # ARADA BAŞKASI VAR MI: iki görünüş arasında üçüncü bir bölge duruyorsa
    # bunlar komşu değildir, bağ kurulmaz.
    def arada_var(i, j, yon):
        a, b = bolgeler[i], bolgeler[j]
        if yon == "satir":
            l, r = (a, b) if a.x1 <= b.x0 else (b, a)
            for k in range(n):
                if k in (i, j):
                    continue
                c = bolgeler[k]
                if (c.x0 > l.x1 + 1e-9 and c.x1 < r.x0 - 1e-9
                        and _ortusme(c.y0, c.y1, l.y0, l.y1) > 0.3):
                    return True
        else:
            l, r = (a, b) if a.y1 <= b.y0 else (b, a)
            for k in range(n):
                if k in (i, j):
                    continue
                c = bolgeler[k]
                if (c.y0 > l.y1 + 1e-9 and c.y1 < r.y0 - 1e-9
                        and _ortusme(c.x0, c.x1, l.x0, l.x1) > 0.3):
                    return True
        return False

    baglar = []
    kullanilan = defaultdict(set)      # bölge -> bağlandığı yönler
    for bosluk, i, j, yon in sorted(aday):
        if yon in kullanilan[i] or yon in kullanilan[j]:
            continue                   # bir cismin her yönde tek komşusu olur
        if arada_var(i, j, yon):
            continue
        baglar.append((i, j, yon))
        kullanilan[i].add(yon); kullanilan[j].add(yon)
        ra, rb = kok(i), kok(j)
        if ra != rb:
            ebeveyn[ra] = rb
    gr = defaultdict(list)
    for i in range(n):
        gr[kok(i)].append(i)
    nesneler = []
    for kk in sorted(gr.values(), key=lambda v: -sum(bolgeler[i].g * bolgeler[i].y for i in v)):
        nesneler.append(Nesne(len(nesneler) + 1, [bolgeler[i] for i in kk],
                              [t for t in baglar if t[0] in kk and t[1] in kk]))
    return nesneler


class Nesne:
    """Bir fiziksel cisim ve onu gösteren görünüşler."""

    def __init__(self, no, gorunusler, baglar):
        self.no = no
        self.gorunus = sorted(gorunusler, key=lambda b: -(b.g * b.y))
        self.bag = baglar
        self.rol = {}          # bölge no -> "ON" / "UST" / "SAG"
        self.olcu = None       # (W, D, H)
        self.kati = None
        self.not_ = []

    @property
    def etiketler(self):
        return [b.etiket for b in self.gorunus]

    def rolle(self):
        """Her görünüşe bir rol verir: etiket varsa ondan, yoksa hizadan."""
        g = self.gorunus
        for b in g:
            if b.no not in self.rol and b.etiket in GORUNUS_EKSEN:
                self.rol[b.no] = b.etiket
        if len(self.rol) == len(g):
            return self.rol
        for b in g:
            if b.etiket in GORUNUS_EKSEN:
                self.rol[b.no] = b.etiket
        if len(self.rol) == len(g):
            return self.rol
        if len(g) == 1:
            self.rol[g[0].no] = self.rol.get(g[0].no, "ON")
            return self.rol
        # etiketsiz: en büyüğü ÖN kabul et, satır komşusu SAĞ, sütun komşusu ÜST
        ana = g[0]
        self.rol.setdefault(ana.no, "ON")
        for b in g[1:]:
            if b.no in self.rol:
                continue
            satir = _ortusme(ana.y0, ana.y1, b.y0, b.y1) > 0.9
            self.rol[b.no] = "SAG" if satir else "UST"
        # aynı rol iki kez verilmişse: ana görünüş dışındakileri hizaya göre düzelt
        sayim = Counter(self.rol.values())
        if any(v > 1 for v in sayim.values()):
            kalan = [r for r in ("ON", "SAG", "UST") if sayim.get(r, 0) == 0]
            for b in g[1:]:
                if sayim[self.rol[b.no]] > 1 and kalan:
                    sayim[self.rol[b.no]] -= 1
                    self.rol[b.no] = kalan.pop(0)
                    sayim[self.rol[b.no]] += 1
                    self.not_.append(f"görünüş {b.no}: rol çakıştı, {self.rol[b.no]} atandı")
            hala = Counter(self.rol.values())
            for b in g[1:]:
                if hala[self.rol[b.no]] > 1:
                    hala[self.rol[b.no]] -= 1
                    self.rol.pop(b.no)
                    self.not_.append(f"görünüş {b.no}: rol belirsiz, kullanılmadı")
        return self.rol

    def ozet(self):
        return {"no": self.no, "gorunus": len(self.gorunus),
                "roller": {b.no: self.rol.get(b.no) for b in self.gorunus},
                "olcu": [round(v, 2) for v in self.olcu] if self.olcu else None,
                "kutular": [[round(b.g, 2), round(b.y, 2)] for b in self.gorunus],
                "not": self.not_}


# ============================================================ 4. 3B KURMA
import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
from OCP.TopoDS import TopoDS_Shape

# rol -> (yatay eksen, dikey eksen, normal eksen, yatay ayna, dikey ayna)
ROL_HARITA = {
    "ON":   (0, 2, 1, False, False),
    "ARKA": (0, 2, 1, True,  False),
    "UST":  (0, 1, 2, False, False),
    "ALT":  (0, 1, 2, False, True),
    "SAG":  (1, 2, 0, True,  False),
    "SOL":  (1, 2, 0, False, False),
    "YAN":  (1, 2, 0, True,  False),
}
ROL_HARITA["ÖN"] = ROL_HARITA["ON"]
ROL_HARITA["ÜST"] = ROL_HARITA["UST"]
ROL_HARITA["SAĞ"] = ROL_HARITA["SAG"]
for _a, _b in (("FRONT", "ON"), ("BACK", "ARKA"), ("TOP", "UST"), ("BOTTOM", "ALT"),
               ("PLAN", "UST"), ("RIGHT", "SAG"), ("LEFT", "SOL"), ("SIDE", "SAG")):
    ROL_HARITA[_a] = ROL_HARITA[_b]


def olculer(nesne, P):
    """Görünüşlerden cismin (W, D, H) ölçülerini çıkarır ve tutarlılığı sınar."""
    W = D = H = None
    catisma = []
    for b in nesne.gorunus:
        rol = nesne.rol.get(b.no)
        if rol not in ROL_HARITA:
            continue
        he, ve, ne_, _, _ = ROL_HARITA[rol]
        for eks, boy in ((he, b.g), (ve, b.y)):
            ad = "WDH"[eks]
            mevcut = {"W": W, "D": D, "H": H}[ad]
            if mevcut is None:
                if ad == "W": W = boy
                elif ad == "D": D = boy
                else: H = boy
            elif abs(mevcut - boy) > P["hiza_tol"] * max(mevcut, boy):
                catisma.append(f"{ad}: {mevcut:.2f} / {boy:.2f} ({rol})")
    nesne.not_ += [f"ölçü çatışması {c}" for c in catisma]
    return W, D, H


def _wire(pts3):
    mp = BRepBuilderAPI_MakePolygon()
    for p in pts3:
        mp.Add(cq.Vector(*p).toPnt())
    mp.Close()
    return cq.Wire(mp.Wire())


def poligon_yuz(poly, rol, ofs, olcu, sabit):
    """shapely poligonunu, rolün tanımladığı düzlemde 3B yüze çevirir."""
    he, ve, ne_, ayna_h, ayna_v = ROL_HARITA[rol]
    W, D, H = olcu
    boy_h = (W, D, H)[he]
    boy_v = (W, D, H)[ve]

    def don(u, v):
        u -= ofs[0]; v -= ofs[1]
        if ayna_h and boy_h:
            u = boy_h - u
        if ayna_v and boy_v:
            v = boy_v - v
        p = [0.0, 0.0, 0.0]
        p[he] = u; p[ve] = v; p[ne_] = sabit
        return tuple(p)

    dis = _wire([don(x, y) for x, y in list(poly.exterior.coords)[:-1]])
    ic = [_wire([don(x, y) for x, y in list(r.coords)[:-1]]) for r in poly.interiors]
    return cq.Face.makeFromWires(dis, ic)


def nesne_kur(nesne, P, kalinlik=None):
    """Nesnenin görünüşlerinden 3B katıyı kurar (prizma kesişimi)."""
    nesne.rolle()
    W, D, H = olculer(nesne, P)
    if kalinlik:
        if D is None: D = kalinlik
        if W is None: W = kalinlik
        if H is None: H = kalinlik
    olcu = (W, D, H)
    if any(v is None for v in olcu):
        eksik = [a for a, v in zip("WDH", olcu) if v is None]
        nesne.not_.append(f"eksik ölçü {eksik}: --kalinlik verin")
        return None
    nesne.olcu = olcu

    prizmalar = []
    for b in nesne.gorunus:
        rol = nesne.rol.get(b.no)
        if rol not in ROL_HARITA:
            continue
        alan = b.dolu_alan(P)
        if alan is None or alan.is_empty:
            continue
        he, ve, ne_, _, _ = ROL_HARITA[rol]
        boy_n = olcu[ne_]
        pay = 0.05 * boy_n + 1.0
        poller = list(alan.geoms) if alan.geom_type == "MultiPolygon" else [alan]
        parcalar = []
        for pg in poller:
            if pg.area < P["min_alan"]:
                continue
            try:
                yuz = poligon_yuz(pg, rol, (b.x0, b.y0), olcu, -pay)
                yon = [0.0, 0.0, 0.0]; yon[ne_] = boy_n + 2 * pay
                parcalar.append(cq.Solid.extrudeLinear(yuz, cq.Vector(*yon)))
            except Exception as ex:
                nesne.not_.append(f"{rol}: yüz kurulamadı ({ex})"[:120])
        if parcalar:
            pr = parcalar[0]
            for q in parcalar[1:]:
                pr = pr.fuse(q)
            prizmalar.append((rol, pr))
    if not prizmalar:
        nesne.not_.append("hiç kapalı bölge bulunamadı")
        return None
    nesne.prizma_rol = [r for r, _ in prizmalar]
    kati = prizmalar[0][1]
    for rol, pr in prizmalar[1:]:
        try:
            c = BRepAlgoAPI_Common(kati.wrapped, pr.wrapped); c.Build()
            if not c.IsDone():
                nesne.not_.append(f"{rol}: kesişim alınamadı")
                continue
            kati = cq.Shape.cast(c.Shape())
        except Exception as ex:
            nesne.not_.append(f"{rol}: kesişim hatası ({ex})"[:120])
    try:
        kati = kati.clean()
    except Exception:
        pass
    katilar = kati.Solids() if hasattr(kati, "Solids") else []
    if not katilar:
        nesne.not_.append("kesişim boş çıktı")
        return None
    nesne.kati = kati
    nesne.hacim = sum(s.Volume() for s in katilar)
    nesne.kati_sayisi = len(katilar)
    return kati


# ============================================================ 5. ÇIKTI
def step_yaz(nesneler, yol, ad="DXF_DONUSUM"):
    assy = cq.Assembly(name=ad)
    n = 0
    for nes in nesneler:
        if nes.kati is None:
            continue
        rk = nes.gorunus[0].renk if nes.gorunus and nes.gorunus[0].renk else None
        etk = ("R%s%s" % rk if rk else "") + "_" + ("_".join(x for x in nes.etiketler if x) or "NESNE")
        assy.add(nes.kati, name=re.sub(r"[^\w]", "_", f"N{nes.no:03d}{etk}")[:60],
                 color=cq.Color(0.6, 0.65, 0.7))
        n += 1
    if n == 0:
        return 0
    assy.save(yol, "STEP")
    return n


def kontrol_png(ciz, bolgeler, nesneler, yol):
    """Programın ne anladığını gösterir: bölgeler, roller, kurulan katılar."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection
        from matplotlib.patches import Polygon as MPoly
    except Exception:
        return False
    fig, axs = plt.subplots(1, 2, figsize=(22, 11))
    ax = axs[0]
    segs = [[(a[0], a[1]), (b[0], b[1])] for a, b, _ in ciz.segment]
    ax.add_collection(LineCollection(segs, colors="#ccc", linewidths=0.3))
    renkler = plt.cm.tab20.colors
    for i, b in enumerate(bolgeler):
        c = renkler[i % len(renkler)]
        al = b.dolu_alan()
        if al is not None:
            for pg in (list(al.geoms) if al.geom_type == "MultiPolygon" else [al]):
                ax.add_patch(MPoly(list(pg.exterior.coords), closed=True, fc=c, ec=c, alpha=0.45))
                for r in pg.interiors:
                    ax.add_patch(MPoly(list(r.coords), closed=True, fc="white", ec=c, alpha=0.9))
        ax.text(b.merkez[0], b.y1, f"#{b.no} {b.etiket or ''}", fontsize=7, color=c, ha="center")
    ax.set_aspect("equal"); ax.autoscale(); ax.set_title("bölgeler ve dolu alanlar", fontsize=10)
    ax.grid(True, lw=.2, alpha=.4); ax.tick_params(labelsize=7)

    ax = axs[1]
    satir = []
    for nes in nesneler[:40]:
        r = ", ".join(f"{b.no}:{nes.rol.get(b.no) or '?'}" for b in nes.gorunus)
        o = f"{nes.olcu[0]:.1f}x{nes.olcu[1]:.1f}x{nes.olcu[2]:.1f}" if nes.olcu else "-"
        durum = "katı OK" if nes.kati is not None else "KURULAMADI"
        satir.append(f"N{nes.no:03d}  görünüş[{r}]  ölçü {o}  {durum}"
                     + (f"  ({nes.not_[0]})" if nes.not_ else ""))
    ax.axis("off")
    ax.text(0.01, 0.99, "NESNELER\n" + "\n".join(satir[:40]), va="top", ha="left",
            fontsize=8, family="monospace", transform=ax.transAxes)
    fig.suptitle(f"{os.path.basename(ciz.yol)} – DXF'ten ne anlaşıldı", fontsize=12)
    fig.tight_layout(); fig.savefig(yol, dpi=100); plt.close(fig)
    return True


# ============================================================ CLI
def main():
    ap = argparse.ArgumentParser(description="DXF -> 3D STEP dönüştürücü")
    ap.add_argument("dxf")
    ap.add_argument("-o", "--out", help="çıktı ön eki (varsayılan: dxf adı)")
    ap.add_argument("--liste", action="store_true", help="yalnız bölge/nesne raporu")
    ap.add_argument("--kalinlik", type=float, help="tek görünüşlü nesneler için kalınlık")
    ap.add_argument("--renk", choices=["auto", "evet", "hayir"], default="auto",
                    help="renk = parça kimliği (her renk ayrı parça). auto: 3+ renk varsa aç")
    ap.add_argument("--delik", choices=["ic", "yok"], default="ic",
                    help="ic: içteki kapalı bölgeler delik; yok: doldur")
    ap.add_argument("--pencere", help="yalnız bu kutu: x0,y0,x1,y1")
    ap.add_argument("--en-az-alan", type=float, default=1.0, help="bundan küçük yüzler atılır")
    ap.add_argument("--en-az-nesne", type=float, default=0.0,
                    help="bundan küçük nesneler (kutu alanı) atlanır")
    ap.add_argument("--param", help="JSON: varsayılanların üzerine yazılır")
    a = ap.parse_args()

    P = dict(VARSAYILAN)
    P["delik"] = a.delik
    P["min_alan"] = a.en_az_alan
    if a.param:
        P.update(json.load(open(a.param, encoding="utf-8")))
    t0 = time.time()
    ciz = Cizim(a.dxf, P)
    print(f"{a.dxf}: {len(ciz.atom)} nesne, {len(ciz.segment)} segment, "
          f"3B yüz {len(ciz.uc3b)}, z değişken {ciz.z_degisken}  [{time.time()-t0:.1f}s]")
    if a.pencere:
        x0, y0, x1, y1 = [float(v) for v in a.pencere.split(",")]
        ciz.atom = [q for q in ciz.atom
                    if x0 <= (q["kutu"][0] + q["kutu"][2]) / 2 <= x1
                    and y0 <= (q["kutu"][1] + q["kutu"][3]) / 2 <= y1]
        ciz.segment = [s for q in ciz.atom for s in q["seg"]]
        print(f"  pencere sonrası: {len(ciz.atom)} nesne")

    renkler = Counter(a.get("renk") for a in ciz.atom)
    renk_kip = a.renk == "evet" or (a.renk == "auto" and len(renkler) >= 3)
    if renk_kip:
        print(f"  renk kipi: {len(renkler)} renk -> " +
              ", ".join(f"{k[0]}{k[1]}:{v}" for k, v in renkler.most_common(8)))
        bolgeler, cerceve, _ = bolgele_renk(ciz, P)
    else:
        bolgeler, cerceve, _ = bolgele(ciz, P)
    print(f"{len(bolgeler)} bölge, {len(cerceve)} çerçeve atomu  [{time.time()-t0:.1f}s]")
    if a.en_az_nesne > 0:
        bolgeler = [b for b in bolgeler if b.g * b.y >= a.en_az_nesne]
        for i, b in enumerate(bolgeler, 1):
            b.no = i
        print(f"  büyüklük süzgeci sonrası: {len(bolgeler)} bölge")

    nesneler = (nesne_esle_renk(bolgeler, P) if renk_kip and a.renk != "hayir"
                else nesne_esle(bolgeler, P))
    print(f"{len(nesneler)} nesne  [{time.time()-t0:.1f}s]")
    if a.liste:
        for b in bolgeler[:60]:
            print("   bölge", json.dumps(b.ozet(P), ensure_ascii=False))
        for n in nesneler[:60]:
            n.rolle()
            print("   nesne", json.dumps(n.ozet(), ensure_ascii=False, default=float))
        return

    on = a.out or os.path.splitext(a.dxf)[0]
    kuruldu = 0
    for nes in nesneler:
        try:
            if nesne_kur(nes, P, a.kalinlik) is not None:
                kuruldu += 1
        except Exception as ex:
            nes.not_.append(f"hata: {ex}"[:150])
    print(f"{kuruldu}/{len(nesneler)} nesne katıya çevrildi  [{time.time()-t0:.1f}s]")

    n = step_yaz(nesneler, on + ".step")
    if n:
        import shutil
        shutil.copyfile(on + ".step", on + ".stp")
        print(f"  {on}.step  ve  {on}.stp   ({n} katı)")
    js = {"dxf": a.dxf, "bolge": [b.ozet(P) for b in bolgeler],
          "nesne": [n2.ozet() for n2 in nesneler],
          "kuruldu": kuruldu, "param": {k: v for k, v in P.items()}}
    json.dump(js, open(on + ".json", "w", encoding="utf-8"), ensure_ascii=False,
              indent=1, default=float)
    print(f"  {on}.json")
    if kontrol_png(ciz, bolgeler, nesneler, on + "_kontrol.png"):
        print(f"  {on}_kontrol.png")
    print(f"bitti [{time.time()-t0:.1f}s]")


if __name__ == "__main__":
    main()
