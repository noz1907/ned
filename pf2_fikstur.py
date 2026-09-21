"""
PiFikstur Maker – ADIM 2 : FİKSTÜR TASARIMI (kaynak fikstürü)
==============================================================
Amaç: ADIM 1'de seçilen grup için (referans JSON) 3-2-1 prensibine göre
konumlandırma elemanları, klempler ve taban plakası olan bir kaynak
fikstürü üretmek; parçayla çakışma / temas / kaynak erişimi kontrolü
yapmak ve STEP + DXF + JSON + rapor olarak yazmak.

    python pf2_fikstur.py parca.stp --referans referans_G03.json
    python pf2_fikstur.py parca.stp --grup G03 --yon +Y
    python pf2_fikstur.py G03.step  --yon +Y            # yalnız grubu içeren STEP
    python pf2_fikstur.py parca.stp --sec "0,/DESTEK_SACi/,G03" --yon=-Y   # P1 + G03 birleşimi

Çıktılar (-o ön eki, varsayılan fikstur_<grup>):
    <o>.step   fikstür + parça montajı (adlandırılmış parçalar)
    <o>.dxf    üst / ön / yan görünüşler (HLR, GORUNEN-GIZLI katmanları) + liste
    <o>.json   eleman koordinatları, kontrol sonuçları, malzeme listesi
    <o>.md     okunabilir rapor
    <o>.png    2B ön izleme (tam boy, kapak ucu ve itme klempi yakın plan)

Fikstür koordinat sistemi: +Z yukarı, +X parça boyu, taban plakası üst
yüzü Z=0. Parça, seçilen "yukarı" yönü +Z olacak şekilde döndürülür.

Bu modül ÖNERİR; ölçüler PARAM sözlüğünden değiştirilebilir.
"""
from __future__ import annotations
import argparse, json, math, os, re, sys, time
from collections import Counter

import cadquery as cq
from OCP.gp import gp_Pnt, gp_Dir, gp_Trsf, gp_Ax1, gp_Ax2, gp_Vec, gp_Quaternion, gp_Mat
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_IN, TopAbs_ON
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_TangentialDeflection

import pf1_referans as E

RHO = 7.85e-6          # kg/mm3 çelik
YONLER = E.YONLER

# ============================================================ PARAMETRELER
PARAM = dict(
    taban_kalinlik=15.0,        # taban plakası (S355) kalınlığı
    taban_pay_x=150.0,          # parça başı ile taban kenarı arası (itme klempi yeri)
    taban_pay_y=60.0,           # en dış eleman ile taban kenarı arası
    taban_pay_x_son=60.0,       # yuva bloğu ile taban ucu arası
    iskelet_profil=(60.0, 40.0, 3.0),   # taban altı kutu profil (g x y x et)
    montaj_delik=13.0,          # M12 için Ø13 taban montaj delikleri
    dayama_yuk=40.0,            # datum A dayama yüksekliği (taban üstünden)
    dayama_boy=60.0,            # dayama X boyu
    dayama_pay=6.0,             # dayama, web düz kısmından bu kadar içeride
    dayama_adim_max=500.0,      # dayamalar arası en büyük mesafe
    dayama_temas_oran=0.85,     # dayama üst yüzü ile parçanın gerçek temas oranı
    kaynak_pay=60.0,            # kaynak dikişine bu kadar yaklaşan eleman olmasın
    yan_dayama_kal=30.0,        # datum B blok kalınlığı (Y)
    yan_dayama_boy=40.0,        # datum B blok boyu (X)
    yan_dayama_ust_pay=1.5,     # yan dayama üstü parça üstünden bu kadar aşağıda
    yuva_et=40.0,               # kapak yuvası arka duvar kalınlığı
    yuva_kulak=20.0,            # kapak yuvası yan kulak kalınlığı
    yuva_ust_pay=5.0,           # yuva, kapak üstünden bu kadar yukarı
    catal_bosluk=1.5,           # çatal uç dayamasının iç içe parçaya bıraktığı boşluk
    kaynak_yan_pay=20.0,        # dikişin Y yanından bu kadar uzakta eleman olabilir
    torc_konisi=60.0,           # torç erişim konisinin yarı açısı (derece)
    kopru_ayak=(24.0, 10.0),    # köprü ayak (X boyu, kalınlık)
    lastik=(12.0, 6.0),         # köprü ayak lastik takozu (çap, yükseklik)
    klemp_dikey_std_h=75.0,     # dikey klempin standart kol alt yüksekliği (GH-201-B sınıfı)
    klemp_yatay_std_h=30.0,     # yatay klempin standart mil ekseni yüksekliği (GH-304-CM sınıfı)
    montaj_pay=40.0,            # montaj modunda arayüz çevresinde bırakılacak el/takım payı
    mil_capi=16.0,
    ayak_capi=20.0,
)


# ============================================================ yardımcılar
def kutu(sh):
    return cq.Shape(sh).BoundingBox() if not isinstance(sh, cq.Shape) else sh.BoundingBox()


def hacim(sh):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(sh, g); return g.Mass()


def alan(sh):
    g = GProp_GProps(); BRepGProp.SurfaceProperties_s(sh, g); return g.Mass()


def mesafe(a, b):
    d = BRepExtrema_DistShapeShape(a, b)
    return d.Value() if d.IsDone() else 1e9


def ortak_hacim(a, b):
    """İki katının kesişim hacmi (çakışma kontrolü)."""
    try:
        c = BRepAlgoAPI_Common(a, b); c.Build()
        if not c.IsDone():
            return 0.0
        return hacim(c.Shape())
    except Exception:
        return 0.0


def kaynak_mi(ad):
    return re.search(r"naht|kaynak|weld|seam|diki", ad, re.I) is not None


def cerceve(u):
    """Seçilen 'yukarı' yön vektörünü +Z'ye, boy eksenini +X'e taşıyan dönüşüm."""
    u = tuple(u)
    return u


def dondur(sd, R, t=(0, 0, 0)):
    tr = gp_Trsf()
    m = gp_Mat(*[R[i][j] for i in range(3) for j in range(3)])
    tr.SetValues(R[0][0], R[0][1], R[0][2], t[0],
                 R[1][0], R[1][1], R[1][2], t[1],
                 R[2][0], R[2][1], R[2][2], t[2])
    return BRepBuilderAPI_Transform(sd, tr, True).Shape()


def rotasyon_matrisi(u, boy_ekseni):
    """Satırlar = fikstür eksenlerinin parça eksenlerindeki ifadesi.
    fikstür Z = u, fikstür X = boy ekseni, fikstür Y = Z x X."""
    z = u
    x = boy_ekseni
    y = (z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0])
    return [list(x), list(y), list(z)]


def kutu_cq(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def kutu_delikli(x0, x1, y0, y1, z0, z1, delikler, cap):
    w = kutu_cq(x0, x1, y0, y1, z0, z1)
    if delikler:
        w = (w.faces(">Z").workplane(origin=(0, 0, z1))
             .pushPoints([(px, py) for px, py in delikler]).hole(cap))
    return w


# ============================================================ parça yükleme
def sec_coz(kayit, gruplar, ifade):
    """Seçim ifadesini katı indeksi kümesine çevirir.

    Virgülle ayrılmış jetonlar:
        G03        grup no
        12         katı indeksi (0 tabanlı, --liste çıktısındaki no)
        /regex/    adı eşleşen tüm katılar  (ör. /DESTEK_SACi/)
    """
    uyeler = []
    for jeton in [t.strip() for t in ifade.split(",") if t.strip()]:
        if jeton.startswith("/") and jeton.endswith("/") and len(jeton) > 2:
            kal = re.compile(jeton[1:-1], re.I)
            bul = [i for i, (ad, _) in enumerate(kayit) if kal.search(ad)]
            if not bul:
                sys.exit(f"HATA: {jeton} hiçbir parça adıyla eşleşmedi")
            uyeler += bul
        elif re.fullmatch(r"[Gg]\d+", jeton):
            gi = int(jeton[1:]) - 1
            if not (0 <= gi < len(gruplar)):
                sys.exit(f"HATA: {jeton} yok, G01..G{len(gruplar):02d}")
            uyeler += list(gruplar[gi])
        elif re.fullmatch(r"\d+", jeton):
            i = int(jeton)
            if not (0 <= i < len(kayit)):
                sys.exit(f"HATA: katı {i} yok, 0..{len(kayit)-1}")
            uyeler.append(i)
        else:
            sys.exit(f"HATA: seçim jetonu anlaşılmadı: {jeton}")
    return sorted(set(uyeler))


def grup_yukle(step, grup=None, parca=None, referans=None, sec=None):
    kayit = E.step_oku(step)
    if sec is None and grup is None and parca is None and referans:
        grup = referans.get("secim")
    if sec is None and grup is None and parca is None:
        return kayit, list(range(len(kayit))), os.path.splitext(os.path.basename(step))[0]
    gruplar, temaslar, _ = E.temas_grupla(kayit)
    if sec:
        uyeler = sec_coz(kayit, gruplar, sec)
        ad = re.sub(r"[^\w+]+", "_", sec.replace(",", "+").replace("/", "")).strip("_")[:40]
        return kayit, uyeler, ad.upper()
    if grup:
        gi = int(re.sub(r"\D", "", grup)) - 1
        if not (0 <= gi < len(gruplar)):
            sys.exit(f"HATA: {grup} yok, 1..{len(gruplar)}")
        return kayit, gruplar[gi], grup.upper()
    return kayit, [parca - 1], f"P{parca}"


def yon_sec(kayit, uyeler, yon, referans):
    if yon:
        return yon.upper()
    if referans and referans.get("secilen_yon"):
        return referans["secilen_yon"].upper()
    _, temaslar, _ = E.temas_grupla(kayit)
    puan, _ = E.yon_puanla(kayit, uyeler, temaslar)
    return puan[0]["yon"]


# ============================================================ parça analizi
class Parca:
    """Fikstür koordinatlarına taşınmış grup + sınıflandırma."""

    def __init__(self, kayit, uyeler, yon, P):
        self.yon = yon
        u = YONLER[yon]
        # boy ekseni: u'ya dik iki eksenden kutusu uzun olan
        b = E.kutu_birlesik([kayit[i][1] for i in uyeler])
        boylar = {0: b[3] - b[0], 1: b[4] - b[1], 2: b[5] - b[2]}
        k = max(range(3), key=lambda t: abs(u[t]))
        bx = max((t for t in range(3) if t != k), key=lambda t: boylar[t])
        ex = [0, 0, 0]; ex[bx] = 1
        self.R = rotasyon_matrisi(u, tuple(ex))
        ham = [(kayit[i][0], dondur(kayit[i][1], self.R)) for i in uyeler]

        # sınıflandırma: ad ile (Kehlnaht/kaynak/weld) ya da ad yoksa hacimle
        # (ana gövdenin %1'inden küçük katılar dikiş sayılır)
        en_buyuk = max(hacim(s) for _, s in ham)
        adsiz = lambda a: re.match(r"(Open CASCADE|SOLID_|\?$)", a) is not None

        def dikis(a, s):
            return kaynak_mi(a) or (adsiz(a) and hacim(s) < 0.01 * en_buyuk)
        self.kaynaklar = [(a, s) for a, s in ham if dikis(a, s)]
        digerleri = [(a, s) for a, s in ham if not dikis(a, s)]
        digerleri.sort(key=lambda t: -hacim(t[1]))
        self.ana_ad, ana = digerleri[0]
        self.ekler = digerleri[1:]

        # öteleme: ana gövde altı = dayama yüksekliği, parça başı = pay, Y merkez = 0
        bb = kutu(ana)
        self.dx = P["taban_pay_x"] - bb.xmin
        self.dz = P["dayama_yuk"] - bb.zmin
        # Y merkezi: ana gövde alt yüzünün merkezi
        self.dy = -(bb.ymin + bb.ymax) / 2
        t = (self.dx, self.dy, self.dz)
        I = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        self.ana = dondur(ana, I, t)
        self.ekler = [(a, dondur(s, I, t)) for a, s in self.ekler]
        self.kaynaklar = [(a, dondur(s, I, t)) for a, s in self.kaynaklar]
        self.hepsi = [(self.ana_ad, self.ana)] + self.ekler + self.kaynaklar
        self.kutu = kutu(self.ana)
        # ek parçaları ayır: ana gövdenin içinden geçen (iç içe) / ucuna oturan plaka
        self.ic_ice, self.uc_plaka = [], []
        for a, s in self.ekler:
            eb = kutu(s)
            ortak = max(0.0, min(eb.xmax, self.kutu.xmax) - max(eb.xmin, self.kutu.xmin))
            (self.ic_ice if ortak > 0.2 * max(eb.xlen, 1e-9) else self.uc_plaka).append((a, s))
        self.kutu_hepsi = kutu(cq.Compound.makeCompound([cq.Shape.cast(s) for _, s in self.hepsi]))
        self.duz, self.sil = E.yuzey_bilgi(self.ana)
        self.kg = sum(hacim(s) for _, s in self.hepsi) * RHO

    def parca_noktasi(self, p_fikstur):
        """Fikstür -> orijinal parça koordinatı (rapor için)."""
        x, y, z = p_fikstur[0] - self.dx, p_fikstur[1] - self.dy, p_fikstur[2] - self.dz
        R = self.R
        return tuple(round(R[0][i] * x + R[1][i] * y + R[2][i] * z, 2) for i in range(3))

    # --- yüzey seçimleri
    def alt_yuz(self):
        """Datum A: ana gövdenin en alttaki, -Z bakan en büyük düz yüzü."""
        ad = [d for d in self.duz if d["n"][2] < -0.98 and abs(d["c"][2] - self.kutu.zmin) < 0.5]
        return max(ad, key=lambda d: d["alan"])

    def ust_yuzler(self):
        """+Z bakan, en üstte olan düz yüzler (klemp basma yerleri)."""
        return [d for d in self.duz if d["n"][2] > 0.98 and abs(d["c"][2] - self.kutu.zmax) < 0.5]

    def kaynak_bolgeleri(self):
        return [kutu(s) for _, s in self.kaynaklar]


# ============================================================ fikstür elemanları
class Eleman:
    def __init__(self, ad, tip, govde, malzeme="S355JR", not_="", hedef=None, temas_yonu=None):
        self.ad, self.tip, self.govde, self.malzeme, self.not_ = ad, tip, govde, malzeme, not_
        self.hedef = hedef            # temas etmesi gereken parça katısı
        self.temas_yonu = temas_yonu  # rapor için
        self.kontrol = {}

    @property
    def sekil(self):
        return self.govde.val().wrapped if isinstance(self.govde, cq.Workplane) else self.govde.wrapped

    def kutu(self):
        return kutu(self.sekil)

    def kg(self):
        return hacim(self.sekil) * RHO


def klemp_dikey(ad, x, y_govde, yon, z_taban, z_bas, kopru_y, ayak_y, P, hedef, eksen="Y"):
    """Dikey (aşağı basan) mafsallı klemp zarf modeli + köprü ayak.
    yon=+1: kol +Y'ye uzanır. Kol ucu (x, kopru_y). Ayaklar ayak_y listesindeki Y'lerde.
    eksen="X": aynı klemp, basma noktası etrafında -90° döndürülür; kol +Y yerine +X
    yönünden gelir (gövde X = x + (y_govde - kopru_y))."""
    ka, kk = P["kopru_ayak"]; lc, lh = P["lastik"]
    z_lastik = z_bas                         # lastik altı parça üstüne oturur
    z_kopru = z_lastik + lh
    z_kol_alt = z_kopru + kk + 20            # mil boyu 20
    yuk = max(0.0, z_kol_alt - z_taban - P["klemp_dikey_std_h"])
    parcalar = []
    # yükseltici
    if yuk > 0:
        parcalar.append(kutu_cq(x - 25, x + 25, y_govde - 45, y_govde + 45, z_taban, z_taban + yuk))
    zb = z_taban + yuk
    # taban plakası 45x85x6 (4 delik)
    parcalar.append(kutu_delikli(x - 22.5, x + 22.5, y_govde - 42.5, y_govde + 42.5, zb, zb + 6,
                                 [(x - 15, y_govde - 32), (x + 15, y_govde - 32),
                                  (x - 15, y_govde + 32), (x + 15, y_govde + 32)], 6.6))
    # gövde
    parcalar.append(kutu_cq(x - 15, x + 15, y_govde - 20, y_govde + 20, zb + 6, z_kol_alt + 8))
    # kol
    y_uc = kopru_y + yon * 10
    ya, yb = sorted((y_govde, y_uc))
    parcalar.append(kutu_cq(x - 10, x + 10, ya, yb, z_kol_alt, z_kol_alt + 8))
    # mil
    parcalar.append(cq.Workplane("XY").circle(4).extrude(z_kol_alt - z_kopru - kk)
                    .translate((x, kopru_y, z_kopru + kk)))
    # kulp (geriye ve yukarı)
    yk0, yk1 = sorted((y_govde, y_govde - yon * 45))
    parcalar.append(kutu_cq(x - 7, x + 7, yk0, yk1, z_kol_alt + 8, z_kol_alt + 22))
    parcalar.append(kutu_cq(x - 7, x + 7, y_govde - yon * 45 - 7, y_govde - yon * 45 + 7,
                            z_kol_alt + 8, z_kol_alt + 90))
    if len(ayak_y) >= 2:
        # köprü ayak + lastik takozlar
        ymin, ymax = min(ayak_y) - 12, max(ayak_y) + 12
        parcalar.append(kutu_cq(x - ka / 2, x + ka / 2, ymin, ymax, z_kopru, z_kopru + kk))
        for yy in ayak_y:
            parcalar.append(cq.Workplane("XY").circle(lc / 2).extrude(lh).translate((x, yy, z_lastik)))
        malz = "GH-201-B sınıfı + köprü ayak (St)"
    else:
        # tek mafsallı lastik ayak (Ø16)
        parcalar.append(cq.Workplane("XY").circle(8).extrude(kk + lh).translate((x, ayak_y[0], z_lastik)))
        malz = "GH-201-B sınıfı, mafsallı lastik ayak"
    govde = parcalar[0]
    for p in parcalar[1:]:
        govde = govde.union(p)
    basma = [(x, yy, z_bas) for yy in ayak_y]
    if eksen == "X":
        govde = govde.rotate((x, kopru_y, 0), (x, kopru_y, 1), -90)
        basma = [(x + (yy - kopru_y), kopru_y, z_bas) for yy in ayak_y]
    e = Eleman(ad, "klemp_dikey", govde, malz,
               f"basma Z={z_bas:.1f}, ayaklar Y={[round(v,1) for v in ayak_y]}, "
               f"yükseltici {yuk:.0f} mm, kol {'+X' if eksen == 'X' else '+Y'} yönünden", hedef, "-Z")
    e.basma = basma
    return e


def klemp_yatay(ad, x, y_govde, yon, z_taban, z_eksen, y_bas, P, hedef, ayak=None):
    """Yatay itme-çekme klemp zarf modeli. yon=+1: mil +Y'ye iter. Ayak ucu y_bas'ta.
    ayak=(boy_x, boy_z, kal) verilirse dairesel yerine plaka ayak."""
    yuk = max(0.0, z_eksen - z_taban - P["klemp_yatay_std_h"])
    parcalar = []
    if yuk > 0:
        parcalar.append(kutu_cq(x - 25, x + 25, y_govde - 40, y_govde + 40, z_taban, z_taban + yuk))
    zb = z_taban + yuk
    parcalar.append(kutu_delikli(x - 20, x + 20, y_govde - 35, y_govde + 35, zb, zb + 8,
                                 [(x - 13, y_govde - 26), (x + 13, y_govde - 26),
                                  (x - 13, y_govde + 26), (x + 13, y_govde + 26)], 6.6))
    parcalar.append(kutu_cq(x - 16, x + 16, y_govde - 28, y_govde + 28, zb + 8, z_eksen + 18))
    # mil: gövde önünden ayağa
    y_on = y_govde + yon * 28
    ak = ayak[2] if ayak else 8.0
    y_ayak_arka = y_bas - yon * ak
    L = abs(y_ayak_arka - y_on)
    mil = cq.Workplane("XZ").circle(P["mil_capi"] / 2).extrude(-L if yon > 0 else L)
    parcalar.append(mil.translate((x, y_on, z_eksen)))
    if ayak:
        bx, bz, _ = ayak
        ya, yb = sorted((y_ayak_arka, y_bas))
        parcalar.append(kutu_cq(x - bx / 2, x + bx / 2, ya, yb, z_eksen - bz / 2, z_eksen + bz / 2))
    else:
        ya, yb = sorted((y_ayak_arka, y_bas))
        parcalar.append(cq.Workplane("XZ").circle(P["ayak_capi"] / 2).extrude(-(yb - ya) if yon > 0 else (yb - ya))
                        .translate((x, ya if yon > 0 else yb, z_eksen)))
    # kulp
    parcalar.append(kutu_cq(x - 7, x + 7, y_govde - yon * 40 - 7 if yon > 0 else y_govde + 40 - 7,
                            y_govde - yon * 40 + 7 if yon > 0 else y_govde + 40 + 7,
                            z_eksen + 18, z_eksen + 110))
    govde = parcalar[0]
    for p in parcalar[1:]:
        govde = govde.union(p)
    e = Eleman(ad, "klemp_yatay", govde, "GH-304-CM sınıfı (St)",
               f"mil ekseni Z={z_eksen:.1f}, itme yönü {'+' if yon > 0 else '-'}Y, "
               f"yükseltici {yuk:.0f} mm", hedef, ("+Y" if yon > 0 else "-Y"))
    e.basma = [(x, y_bas, z_eksen)]
    return e


def _ic_mi(cls, x, y, z):
    cls.Perform(gp_Pnt(x, y, z), 1e-7)
    return cls.State() in (TopAbs_IN, TopAbs_ON)


def _ust_z(cls, x, y, z_ust, z_alt, adim=0.4):
    """(x,y) dikeyinde katının üst yüzeyinin z'si (yoksa None).

    Kaba tarama + ikiye bölme ile 0,01 mm'ye kadar netleştirilir; klemp ayağı
    yüzeyin içine gömülmesin diye şart."""
    t = z_ust
    while t >= z_alt:
        if _ic_mi(cls, x, y, t):
            lo, hi = t, min(t + adim, z_ust)       # lo içeride, hi dışarıda
            for _ in range(7):
                orta = (lo + hi) / 2
                if _ic_mi(cls, x, y, orta):
                    lo = orta
                else:
                    hi = orta
            return hi
        t -= adim
    return None


def _yan_y(cls, x, z, y_bas, y_son, adim=0.4):
    """(x,z) yatayında katının -Y yönündeki ilk yüzeyinin y'si (yoksa None)."""
    t = y_bas
    while t <= y_son:
        if _ic_mi(cls, x, t, z):
            lo, hi = t, max(t - adim, y_bas)      # lo içeride, hi dışarıda
            for _ in range(7):
                orta = (lo + hi) / 2
                if _ic_mi(cls, x, orta, z):
                    lo = orta
                else:
                    hi = orta
            return hi
        t += adim
    return None


def _yuzey_y(cls, x, z, hb, taraf, adim=0.4):
    """(x,z) kesitinde katının -Y (taraf=-1) / +Y (taraf=+1) yüzeyinin y'si."""
    derinlik = 0.6 * (hb.ymax - hb.ymin)
    if taraf < 0:
        return _yan_y(cls, x, z, hb.ymin - 0.5, hb.ymin + derinlik, adim)
    t = hb.ymax + 0.5
    while t >= hb.ymax - derinlik:
        if _ic_mi(cls, x, t, z):
            lo, hi = t, t + adim
            for _ in range(7):
                orta = (lo + hi) / 2
                if _ic_mi(cls, x, orta, z):
                    lo = orta
                else:
                    hi = orta
            return hi
        t -= adim
    return None


def yuzey_siniri(hedef, x0, x1, z0, z1, taraf, hb):
    """Verilen X/Z penceresinde katının -Y (taraf=-1) / +Y (+1) en uç yüzeyi.

    Boolean kesişimin sınır kutusundan okunur: nokta örneklemesinin kaçırdığı
    eğri ve kademeli kenarlarda da kesin sonuç verir. Malzeme yoksa None."""
    dilim = kutu_cq(x0, x1, hb.ymin - 5, hb.ymax + 5, z0, z1)
    try:
        c = BRepAlgoAPI_Common(hedef, dilim.val().wrapped); c.Build()
        if not c.IsDone():
            return None
        k = kutu(c.Shape())
        if k.xlen <= 0 or hacim(c.Shape()) < 1e-6 and k.ylen <= 0:
            return None
        return k.ymin if taraf < 0 else k.ymax
    except Exception:
        return None


def yan_temas(cls, hb, x, z_aday, taraf=-1, genislik=40.0, yukseklik=20.0,
              hedef_sekil=None, engel_sekil=None,
              kaydir_x=(0, 30, -30, 60, -60, 100, -100, 150, -150, 200, -200)):
    """Katının yan yüzeyine dayanacak bloğun konumu: (x, z, y) ya da None.

    Önce x çevresinde ve birkaç kesit yüksekliğinde yüzey aranır; bulununca
    bloğun ayak izinin tamamı taranır ve en DIŞARIDAKİ değer alınır, böylece
    blok eğri/kademeli yüzeye gömülmez."""
    for dx in kaydir_x:
        xx = x + dx
        if not (hb.xmin + 2 < xx < hb.xmax - 2):
            continue
        for z in z_aday:
            if _yuzey_y(cls, xx, z, hb, taraf) is None:
                continue
            x0, x1 = xx - genislik / 2, xx + genislik / 2
            z0, z1 = z - yukseklik / 2, z + yukseklik / 2
            v = yuzey_siniri(hedef_sekil, x0, x1, z0, z1, taraf, hb)
            if v is None:
                continue
            if engel_sekil is not None:
                # o pencerede en dışta ana gövde olmalı; başka parça taşıyorsa kaydır
                ve = yuzey_siniri(engel_sekil, x0, x1, z0, z1, taraf, hb)
                if ve is not None and (ve < v - 0.3 if taraf < 0 else ve > v + 0.3):
                    continue
            return xx, z, v
    return None


def basma_yeri(hedef, x, ayak_y, kaynak_kutulari=(), r=6.0, derinlik=8.0,
               kaydir_x=(0, 25, -25, 50, -50, 75, -75, 110, -110, 150, -150,
                         200, -200, 260, -260, 330, -330, 400, -400),
               kaydir_y=(0, 7, -7, 14, -14, 21, -21)):
    """Klemp ayağının gerçekten dolu malzemeye bastığı (x, ayak_y'leri, z) konumu.

    Delik/slot/çentik üstüne denk gelen ayakları kaydırarak çözer; dikiş
    kutularının üstüne basmaz. Bulamazsa None."""
    hb = kutu(hedef)
    cls = BRepClass3d_SolidClassifier(hedef)
    for dx in kaydir_x:
        xx = x + dx
        if not (hb.xmin + 2 < xx < hb.xmax - 2):
            continue
        for dy in kaydir_y:
            ys = [y + dy for y in ayak_y]
            if any(kb.xmin - 8 < xx < kb.xmax + 8 and kb.ymin - 8 < y < kb.ymax + 8
                   for kb in kaynak_kutulari for y in ys):
                continue
            zs, iyi = [], True
            for y in ys:
                zz = []
                for px, py in ((xx, y), (xx + r, y), (xx - r, y), (xx, y + r), (xx, y - r)):
                    v = _ust_z(cls, px, py, hb.zmax + 0.2, hb.zmax - derinlik)
                    if v is None:
                        iyi = False; break
                    zz.append(v)
                if not iyi:
                    break
                zs.append(max(zz))
            if iyi and zs and max(zs) - min(zs) < 0.6:
                return xx, ys, max(zs)
    return None


def temas_alani(yuz_f, sekil):
    """Bir düz yüz ile başka bir şeklin (blok) kesişim alanı."""
    try:
        c = BRepAlgoAPI_Common(yuz_f, sekil); c.Build()
        if not c.IsDone():
            return 0.0
        return alan(c.Shape())
    except Exception:
        return 0.0


# ============================================================ tasarım
def tasarla(pc: Parca, P, onay=None):
    """Fikstür elemanlarını üret.

    onay: kullanıcı onayından gelen istasyon X konumları ({"istasyon": {...}}).
    Verilirse dayama/klemp konumları hesaplanmaz, onaylanan değerler kullanılır."""
    el = []           # Eleman listesi
    bilgi = {}
    ist = dict((onay or {}).get("istasyon", {}))
    T = P["taban_kalinlik"]
    z0 = 0.0          # taban üstü
    bb = pc.kutu
    taban = pc.alt_yuz()
    fb = kutu(taban["f"])
    # datum A düz genişliği (Y), pay düşülmüş
    ay0, ay1 = fb.ymin + P["dayama_pay"], fb.ymax - P["dayama_pay"]
    if ay1 - ay0 > 80:            # çok geniş web: 80 mm dayama yeter
        m = (ay0 + ay1) / 2; ay0, ay1 = m - 40, m + 40
    bilgi["datum_A"] = {"alan_mm2": round(taban["alan"], 1), "z": round(bb.zmin, 2),
                        "y_araligi": [round(ay0, 1), round(ay1, 1)]}
    bilgi["uyari"] = []
    if ay1 - ay0 < 20:
        bilgi["uyari"].append(f"Datum A oturma yüzü dar ({ay1-ay0:.1f} mm): bu yön için dayama "
                              f"kararsız, başka yön (--yon) deneyin.")

    # ---- yasak bölgeler (X): kaynak dikişleri ± pay, ekler ± pay
    yasak = []
    for kb in pc.kaynak_bolgeleri():
        yasak.append((kb.xmin - P["kaynak_pay"], kb.xmax + P["kaynak_pay"]))
    for _, s in pc.uc_plaka:
        eb = kutu(s); yasak.append((eb.xmin - 20, eb.xmax + 20))

    def serbest(x, yarim):
        return all(x + yarim <= a or x - yarim >= b for a, b in yasak)

    # ---- datum A dayamaları
    # dayama boyu parçaya göre: kısa parçada bloklar üst üste binmesin
    D = min(P["dayama_boy"], max(15.0, (fb.xmax - fb.xmin) * 0.28))
    xa, xb = fb.xmin + 8 + D / 2, fb.xmax - D / 2
    if xb <= xa:                                   # çok kısa yüz: tek dayama
        xa = xb = (fb.xmin + fb.xmax) / 2
    # yasak bölgelerin dışında kalan en uzun aralık
    for a, b in yasak:
        if a <= xb <= b or (a < xb and b > xb):
            xb = min(xb, a - D / 2)
        if a <= xa <= b:
            xa = max(xa, b + D / 2)
    if ist.get("DAYAMA_A"):
        xs = [float(v) for v in ist["DAYAMA_A"]]
        kaydirmalar = (0,)                      # onaylanan konum aynen kullanılır
    else:
        n = max(1, math.ceil((xb - xa) / P["dayama_adim_max"]) + 1)
        n = min(n, max(1, int((xb - xa) / (D + 5)) + 1))   # bloklar çakışmasın
        xs = [(xa + xb) / 2] if n < 2 else [xa + (xb - xa) * i / (n - 1) for i in range(n)]
        kaydirmalar = (0, 20, -20, 40, -40, 60, -60, 80, -80, 100, -100)
    dayamalar = []
    for i, x in enumerate(xs, 1):
        # web boşluklarına (delik/slot) denk gelirse kaydır
        secilen = None
        for kay in kaydirmalar:
            xx = x + kay
            if not serbest(xx, D / 2) or xx - D / 2 < fb.xmin or xx + D / 2 > fb.xmax:
                continue
            blok = kutu_cq(xx - D / 2, xx + D / 2, ay0, ay1, z0, bb.zmin)
            ta = temas_alani(taban["f"], blok.val().wrapped)
            if ta >= P["dayama_temas_oran"] * D * (ay1 - ay0):
                secilen = (xx, ta); break
        if secilen is None:
            secilen = (x, 0.0)
        xx, ta = secilen
        blok = kutu_delikli(xx - D / 2, xx + D / 2, ay0, ay1, z0, bb.zmin,
                            [(xx, ay0 + 15), (xx, ay1 - 15)], 6.8)
        e = Eleman(f"DAYAMA_A_{i:02d}", "dayama_A", blok, "C45 sertleştirilmiş",
                   f"temas alanı {ta:.0f} mm² ({ta/(D*(ay1-ay0))*100:.0f} %)", pc.ana, "+Z")
        e.temas_mm2 = ta
        e.basma = [(xx, (ay0 + ay1) / 2, bb.zmin)]
        dayamalar.append(e)
    el += dayamalar
    dx_list = [d.basma[0][0] for d in dayamalar]

    # ---- datum B yan dayamaları (-Y tarafı), 2 adet: 2. ve sondan 2. dayama hizasında
    ib = [1, len(dayamalar) - 2] if len(dayamalar) >= 4 else [0, len(dayamalar) - 1]
    if ist.get("DAYAMA_B"):
        xb_list = [float(v) for v in ist["DAYAMA_B"]]
    elif len(dayamalar) >= 2:
        xb_list = [dx_list[i] for i in sorted(set(ib))]
    else:                                    # tek dayama: yan dayamaları yüzeye yay
        xb_list = [fb.xmin + 0.3 * (fb.xmax - fb.xmin), fb.xmin + 0.7 * (fb.xmax - fb.xmin)]
    L = P["yan_dayama_boy"]; K = P["yan_dayama_kal"]
    if len(xb_list) > 1 and abs(xb_list[1] - xb_list[0]) < L + 5:
        xb_list = [sum(xb_list) / len(xb_list)]      # sığmıyorsa tek yan dayama
    zt = bb.zmax - P["yan_dayama_ust_pay"]
    cls_ana = BRepClass3d_SolidClassifier(pc.ana)
    tum_parca = cq.Compound.makeCompound([cq.Shape.cast(s) for _, s in pc.hepsi]).wrapped
    z_aday = [bb.zmin + f * (zt - bb.zmin) for f in (0.5, 0.65, 0.35, 0.8, 0.2)]
    yan, xb_gercek = [], []
    for j, x in enumerate(xb_list, 1):
        bul = yan_temas(cls_ana, bb, x, z_aday, -1, genislik=L, yukseklik=zt - bb.zmin,
                        hedef_sekil=pc.ana, engel_sekil=tum_parca)
        if bul is None:
            bilgi["uyari"].append(f"DAYAMA_B_{j:02d}: X={x:.0f} çevresinde -Y yüzeyi bulunamadı")
            continue
        xx, zz, yb = bul
        zt_y = min(zt, zz + (zt - bb.zmin) / 2)
        blok = kutu_delikli(xx - L / 2, xx + L / 2, yb - K, yb, z0, zt_y,
                            [(xx, yb - K / 2)], 6.8)
        e = Eleman(f"DAYAMA_B_{j:02d}", "dayama_B", blok, "C45 sertleştirilmiş",
                   f"temas yüzü Y={yb:.2f}, Z {bb.zmin:.1f}..{zt_y:.1f}", pc.ana, "+Y")
        e.basma = [(xx, yb, zz)]
        yan.append(e); xb_gercek.append(xx)
    el += yan
    if xb_gercek:
        xb_list = xb_gercek

    # ---- iç içe parça (ana gövdenin içinden geçen): çatal uç dayaması + taşan uç desteği
    ic_el, catal = [], []
    for k, (ad, s) in enumerate(pc.ic_ice, 1):
        eb = kutu(s)
        yon = +1 if eb.xmax > bb.xmax + 30 else (-1 if eb.xmin < bb.xmin - 30 else 0)
        if yon == 0:
            continue                       # tümüyle içeride: ana gövde zaten konumluyor
        x_uc = bb.xmax if yon > 0 else bb.xmin         # ana gövdenin uç yüzü (datum C)
        x_dis = eb.xmax if yon > 0 else eb.xmin        # taşan parçanın serbest ucu
        W, pay = P["yuva_et"], P["catal_bosluk"]
        cx0, cx1 = (x_uc, x_uc + W) if yon > 0 else (x_uc - W, x_uc)
        blok = kutu_cq(cx0, cx1, bb.ymin - P["yuva_kulak"], bb.ymax + P["yuva_kulak"], z0, bb.zmax)
        blok = blok.cut(kutu_cq(cx0 - 1, cx1 + 1, eb.ymin - pay, eb.ymax + pay,
                                eb.zmin - pay, bb.zmax + 20))      # üstten açık çatal ağzı
        e = Eleman(f"DAYAMA_C_{k:02d}", "dayama_C", blok, "S355JR",
                   f"ana gövde uç yüzü X={x_uc:.2f}; {ad[:24]} üstten açık çataldan geçer "
                   f"(boşluk {pay:.1f} mm)", pc.ana, "-X" if yon > 0 else "+X")
        e.basma = [(x_uc, (bb.ymin + bb.ymax) / 2, bb.zmin + 2)]
        ic_el.append(e); catal.append((e, yon, x_uc, ad, s, eb))
        # taşan ucun altına dayama (parçanın kendi alt yüzü hizasında)
        L = P["dayama_boy"]; boy = abs(x_dis - x_uc)
        n_t = max(1, int(boy / P["dayama_adim_max"]))
        for j in range(n_t):
            xx = x_uc + yon * boy * (j + 0.6) / (n_t + 0.15)
            dblok = kutu_delikli(xx - L / 2, xx + L / 2, eb.ymin + 3, eb.ymax - 3, z0, eb.zmin,
                                 [(xx, eb.ymin + 15), (xx, eb.ymax - 15)], 6.8)
            e2 = Eleman(f"DAYAMA_A_UC_{k:02d}{chr(97 + j)}", "dayama_A", dblok,
                        "C45 sertleştirilmiş",
                        f"{ad[:24]} taşan ucu, üst yüz Z={eb.zmin:.2f}", s, "+Z")
            e2.basma = [(xx, (eb.ymin + eb.ymax) / 2, eb.zmin)]
            ic_el.append(e2)
    el += ic_el

    # ---- uç plakaları: dikişsiz Y bantlarında datum C postu (+ plaka altı raf)
    yuvalar = []
    for k, (ad, s) in enumerate(pc.uc_plaka, 1):
        eb = kutu(s)
        sag = eb.xmax >= bb.xmax - 1
        x_yuz = eb.xmin if sag else eb.xmax            # postun dayandığı iç yüz
        m = P["kaynak_yan_pay"]
        ky = [(kb.ymin, kb.ymax) for kb in pc.kaynak_bolgeleri()
              if kb.xmin < eb.xmax + 10 and kb.xmax > eb.xmin - 10]
        bantlar = []
        if ky:
            y_alt, y_ust = min(a for a, _ in ky), max(b for _, b in ky)
            if eb.ymin < y_alt - m - 12:
                bantlar.append((eb.ymin, y_alt - m))
            if eb.ymax > y_ust + m + 12:
                bantlar.append((y_ust + m, eb.ymax))
        if not bantlar:
            bantlar = [(eb.ymin, eb.ymin + 30), (eb.ymax - 30, eb.ymax)]
        W = P["yuva_et"]
        px0, px1 = (x_yuz - W, x_yuz) if sag else (x_yuz, x_yuz + W)
        tan_k = math.tan(math.radians(P["torc_konisi"]))
        for j, (y0, y1) in enumerate(bantlar, 1):
            # post üstü, en yakın dikişin torç konisini kesmesin
            z_ust = eb.zmax
            for kb in pc.kaynak_bolgeleri():
                if kb.xmax < eb.xmin - 30 or kb.xmin > eb.xmax + 30:
                    continue
                if y0 >= kb.ymax:
                    bosluk = y0 - kb.ymax
                elif y1 <= kb.ymin:
                    bosluk = kb.ymin - y1
                else:
                    bosluk = 0.0
                z_ust = min(z_ust, (kb.zmin + kb.zmax) / 2 + bosluk / tan_k)
            z_ust = max(z_ust, min(eb.zmax, eb.zmin + 12))
            blok = kutu_cq(px0, px1, y0, y1, z0, z_ust)
            if eb.zmin > z0 + 0.5:                     # plakanın altına raf
                rx0, rx1 = sorted((eb.xmin, eb.xmax))
                blok = blok.union(kutu_cq(rx0, rx1, y0, y1, z0, eb.zmin))
            blok = blok.faces(">Z").workplane(origin=(0, 0, z_ust)).pushPoints(
                [((px0 + px1) / 2, (y0 + y1) / 2)]).hole(6.8)
            e = Eleman(f"DAYAMA_C_PLAKA_{k:02d}{chr(96 + j)}", "yuva_C", blok, "S355JR",
                       f"{ad[:24]}: iç yüz X={x_yuz:.2f}, Y {y0:.1f}..{y1:.1f}, "
                       f"raf Z={eb.zmin:.2f}, üst Z={z_ust:.1f} (torç konisi)",
                       s, "+X" if sag else "-X")
            e.basma = [(x_yuz, (y0 + y1) / 2, (eb.zmin + eb.zmax) / 2)]
            e.ek_kutu = eb; e.sag = sag
            yuvalar.append(e)
    el += yuvalar

    # ---- klempler
    klempler = []
    ust = pc.ust_yuzler()
    ayak_y = sorted(set(round(d["c"][1], 1) for d in ust))
    if len(ayak_y) > 2:                      # en dıştaki ikisi
        ayak_y = [ayak_y[0], ayak_y[-1]]
    if len(ayak_y) == 1:
        ayak_y = [ayak_y[0] - 15, ayak_y[0] + 15]
    kopru_y = sum(ayak_y) / 2
    # dikey klempler: ana gövde üstüne, yan dayama olmayan istasyonlarda
    idx_dikey = [i for i in range(len(dayamalar)) if i not in ib]
    if len(idx_dikey) > 3:
        idx_dikey = [idx_dikey[0], idx_dikey[len(idx_dikey) // 2], idx_dikey[-1]]
    xd_list = ([float(v) for v in ist["KLEMP_DIKEY"]] if ist.get("KLEMP_DIKEY")
               else [dx_list[i] for i in idx_dikey])
    kes = {"kaydir_x": (0,), "kaydir_y": (0,)} if ist.get("KLEMP_DIKEY") else {}
    y_govde = bb.ymin - P["yan_dayama_kal"] - 45 - 10
    kk_kutu = pc.kaynak_bolgeleri()
    for j, xs_d in enumerate(xd_list, 1):
        yer = basma_yeri(pc.ana, xs_d, ayak_y, kk_kutu, **kes)
        if yer is None:
            bilgi["uyari"].append(f"KLEMP_DIKEY_{j:02d}: X={xs_d:.0f} çevresinde dolu "
                                  f"basma yeri bulunamadı, klemp konulmadı")
            continue
        xx, ys, zb = yer
        klempler.append(klemp_dikey(f"KLEMP_DIKEY_{j:02d}", xx, y_govde, +1, z0, zb,
                                    sum(ys) / len(ys), ys, P, pc.ana))
    # yatay klempler: yan dayama karşısı (+Y tarafı), alt köşeye yakın basar
    z_yan = bb.zmin + 5
    xy_list = [float(v) for v in ist["KLEMP_YATAY"]] if ist.get("KLEMP_YATAY") else list(xb_list)
    for j, x in enumerate(xy_list, 1):
        bul = yan_temas(cls_ana, bb, x, [z_yan] + z_aday, +1, hedef_sekil=pc.ana,
                        engel_sekil=tum_parca,
                        genislik=P["ayak_capi"], yukseklik=P["ayak_capi"])
        if bul is None:
            bilgi["uyari"].append(f"KLEMP_YATAY_{j:02d}: X={x:.0f} çevresinde +Y yüzeyi bulunamadı")
            continue
        xx, zz, yu = bul
        klempler.append(klemp_yatay(f"KLEMP_YATAY_{j:02d}", xx, yu + 28 + 60, -1, z0, zz,
                                    yu, P, pc.ana))
    # ana gövdeyi çatal dayamaya iten eksenel klemp (serbest uçtan)
    for e_c, yon, x_uc, ad, s, eb in catal:
        x_itme = bb.xmin if yon > 0 else bb.xmax
        klempler.append(klemp_itme(f"KLEMP_ITME_{len(klempler)+1:02d}", x_itme, yon, z0,
                                   (bb.zmin + bb.zmax) / 2, bb.ylen + 10, bb.zlen + 6, P, pc.ana,
                                   y_merkez=(bb.ymin + bb.ymax) / 2))
        # taşan ucun üstüne dikey klemp (dikişsiz bölge: plakadan ve gövdeden uzak)
        eb2 = kutu(s)
        x_dis = eb2.xmax if yon > 0 else eb2.xmin
        xk = x_uc + yon * abs(x_dis - x_uc) * 0.45
        ust2 = [d for d in E.yuzey_bilgi(s)[0]
                if d["n"][2] > 0.98 and abs(d["c"][2] - eb2.zmax) < 0.5]
        if ust2:
            uk = kutu(max(ust2, key=lambda d: d["alan"])["f"])
            yk = [uk.ymin + 0.25 * uk.ylen, uk.ymax - 0.25 * uk.ylen]
        else:
            yk = [eb2.ymin + 0.3 * eb2.ylen, eb2.ymax - 0.3 * eb2.ylen]
        yer = basma_yeri(s, xk, yk, kk_kutu)
        if yer is None:
            bilgi["uyari"].append(f"{ad[:24]} taşan ucunda dolu basma yeri bulunamadı, "
                                  f"dikey klemp konulmadı")
        else:
            xx, ys, zb = yer
            klempler.append(klemp_dikey(f"KLEMP_DIKEY_UC_{len(klempler)+1:02d}", xx,
                                        eb2.ymin - P["yan_dayama_kal"] - 45 - 10, +1, z0, zb,
                                        sum(ys) / len(ys), ys, P, s))
    # uç plakasını postlarına iten eksenel klemp (her plaka için bir adet)
    gorulen = []
    for v in yuvalar:
        if any(h is v.hedef for h in gorulen):
            continue
        gorulen.append(v.hedef)
        eb = v.ek_kutu
        x_itme = eb.xmax if v.sag else eb.xmin
        klempler.append(klemp_itme(f"KLEMP_ITME_{len(klempler)+1:02d}", x_itme, -1 if v.sag else +1,
                                   z0, (eb.zmin + eb.zmax) / 2, eb.ylen + 6, eb.zlen + 4, P,
                                   v.hedef, y_merkez=(eb.ymin + eb.ymax) / 2))
    el += klempler

    # ---- taban plakası + iskelet
    kb = [e.kutu() for e in el]
    xmin = min(k.xmin for k in kb) - 40
    xmax = max(k.xmax for k in kb) + P["taban_pay_x_son"]
    ymin = min(k.ymin for k in kb) - P["taban_pay_y"]
    ymax = max(k.ymax for k in kb) + P["taban_pay_y"]
    xmin = min(xmin, 0.0)
    ymax = max(ymax, -ymin); ymin = -ymax          # simetrik plaka
    xmin = math.floor(xmin / 10) * 10; xmax = math.ceil(xmax / 10) * 10
    ymin = math.floor(ymin / 10) * 10; ymax = -ymin
    delik = [(xmin + 40, ymin + 40), (xmax - 40, ymin + 40), (xmin + 40, ymax - 40), (xmax - 40, ymax - 40),
             ((xmin + xmax) / 2, ymin + 40), ((xmin + xmax) / 2, ymax - 40)]
    plaka = kutu_delikli(xmin, xmax, ymin, ymax, -T, 0, delik, P["montaj_delik"])
    el.append(Eleman("TABAN_PLAKA", "taban", plaka, "S355JR",
                     f"{xmax-xmin:.0f} x {ymax-ymin:.0f} x {T:.0f} mm, 6 x Ø{P['montaj_delik']:.0f} montaj deliği"))
    g, h, et = P["iskelet_profil"]
    for j, yy in enumerate((ymin + 60, ymax - 60), 1):
        pr = kutu_cq(xmin + 20, xmax - 20, yy - g / 2, yy + g / 2, -T - h, -T)
        pr = pr.cut(kutu_cq(xmin + 20 - 1, xmax - 20 + 1, yy - g / 2 + et, yy + g / 2 - et, -T - h + et, -T - et))
        el.append(Eleman(f"ISKELET_BOY_{j:02d}", "iskelet", pr, "S235JR kutu profil",
                         f"{g:.0f}x{h:.0f}x{et:.0f} - L={xmax-xmin-40:.0f}"))
    for j, xx in enumerate((xmin + 120, (xmin + xmax) / 2, xmax - 120), 1):
        pr = kutu_cq(xx - g / 2, xx + g / 2, ymin + 60 + g / 2, ymax - 60 - g / 2, -T - h, -T)
        pr = pr.cut(kutu_cq(xx - g / 2 + et, xx + g / 2 - et, ymin + 60 + g / 2 - 1, ymax - 60 - g / 2 + 1, -T - h + et, -T - et))
        el.append(Eleman(f"ISKELET_EN_{j:02d}", "iskelet", pr, "S235JR kutu profil",
                         f"{g:.0f}x{h:.0f}x{et:.0f} - L={ymax-ymin-120-g:.0f}"))
    bilgi["taban"] = {"x": [xmin, xmax], "y": [ymin, ymax], "kalinlik": T}
    bilgi["dayama_x"] = [round(v, 1) for v in dx_list]
    bilgi["istasyon"] = {
        "DAYAMA_A": [round(v, 1) for v in dx_list],
        "DAYAMA_B": [round(v, 1) for v in xb_list],
        "KLEMP_DIKEY": [round(e.basma[0][0], 1) for e in klempler if e.tip == "klemp_dikey"],
        "KLEMP_YATAY": [round(v, 1) for v in xy_list],
    }
    return el, bilgi


def klemp_itme(ad, x_uc, yon, z_taban, z_eksen, ayak_y_boy, ayak_z_boy, P, hedef, y_merkez=0.0):
    """Eksenel itme klempi: parça ucunu datum C'ye (yuva duvarı) iter. Plaka ayaklı."""
    ak = 8.0
    yuk = max(0.0, z_eksen - z_taban - P["klemp_yatay_std_h"])
    x_ayak0 = x_uc - yon * ak
    x_on = x_uc - yon * (ak + 70)          # mil boyu 70
    x_g = x_on - yon * 28                  # gövde ön yüzü
    parcalar = []
    xa, xb = sorted((x_g - yon * 56, x_g))
    ym = y_merkez
    if yuk > 0:
        parcalar.append(kutu_cq(xa - 12, xb + 12, ym - 40, ym + 40, z_taban, z_taban + yuk))
    zb = z_taban + yuk
    parcalar.append(kutu_delikli(xa - 7, xb + 7, ym - 35, ym + 35, zb, zb + 8,
                                 [(xa, ym - 26), (xb, ym - 26), (xa, ym + 26), (xb, ym + 26)], 6.6))
    parcalar.append(kutu_cq(xa, xb, ym - 28, ym + 28, zb + 8, z_eksen + 18))
    xm0, xm1 = sorted((x_on, x_ayak0))
    parcalar.append(cq.Workplane("YZ").circle(P["mil_capi"] / 2).extrude(xm1 - xm0).translate((xm0, ym, z_eksen)))
    xk0, xk1 = sorted((x_ayak0, x_uc))
    parcalar.append(kutu_cq(xk0, xk1, ym - ayak_y_boy / 2, ym + ayak_y_boy / 2, z_eksen - ayak_z_boy / 2, z_eksen + ayak_z_boy / 2))
    # kulp
    xh = xa - 40 if yon > 0 else xb + 40
    parcalar.append(kutu_cq(xh - 7, xh + 7, ym - 7, ym + 7, z_eksen + 18, z_eksen + 110))
    govde = parcalar[0]
    for p in parcalar[1:]:
        govde = govde.union(p)
    e = Eleman(ad, "klemp_itme", govde, "GH-304-CM sınıfı (St) + plaka ayak",
               f"mil ekseni Z={z_eksen:.1f}, itme yönü {'+' if yon > 0 else '-'}X, "
               f"plaka ayak {ayak_y_boy:.0f}x{ayak_z_boy:.0f}, yükseltici {yuk:.0f} mm", hedef,
               "+X" if yon > 0 else "-X")
    e.basma = [(x_uc, y_merkez, z_eksen)]
    return e


# ============================================================ kontroller
def kontrol_et(pc: Parca, el, P, bilgi=None):
    bilgi = bilgi or {}
    rapor = {"cakisma": [], "temas": [], "kaynak_erisim": [], "ozet": {}}
    parca_sekiller = [(a, s) for a, s in pc.hepsi]
    fik = [e for e in el]
    # 1) çakışma: fikstür elemanı x parça katısı
    kotu = 0
    for e in fik:
        ek = e.kutu()
        for a, s in parca_sekiller:
            sb = kutu(s)
            if (ek.xmax < sb.xmin - 0.5 or ek.xmin > sb.xmax + 0.5 or ek.ymax < sb.ymin - 0.5
                    or ek.ymin > sb.ymax + 0.5 or ek.zmax < sb.zmin - 0.5 or ek.zmin > sb.zmax + 0.5):
                continue
            v = ortak_hacim(e.sekil, s)
            if v > 0.5:
                kotu += 1
                rapor["cakisma"].append({"eleman": e.ad, "parca": a, "hacim_mm3": round(v, 1)})
    # 2) fikstür elemanları birbirine çakışıyor mu (klemp/dayama)
    for i in range(len(fik)):
        for j in range(i + 1, len(fik)):
            a, b = fik[i], fik[j]
            if a.tip in ("taban", "iskelet") or b.tip in ("taban", "iskelet"):
                continue
            ka, kb = a.kutu(), b.kutu()
            if (ka.xmax < kb.xmin or ka.xmin > kb.xmax or ka.ymax < kb.ymin or ka.ymin > kb.ymax
                    or ka.zmax < kb.zmin or ka.zmin > kb.zmax):
                continue
            v = ortak_hacim(a.sekil, b.sekil)
            if v > 0.5:
                kotu += 1
                rapor["cakisma"].append({"eleman": a.ad, "parca": b.ad, "hacim_mm3": round(v, 1)})
    # 3) temas: konumlandırıcı ve klemp ayakları hedef parçaya değiyor mu
    for e in fik:
        if e.hedef is None:
            continue
        d = mesafe(e.sekil, e.hedef)
        e.kontrol["mesafe_mm"] = round(d, 3)
        rapor["temas"].append({"eleman": e.ad, "tip": e.tip, "mesafe_mm": round(d, 3),
                               "ok": d < 0.05})
    # 4) kaynak erişimi: dikiş merkezinden yukarı koni içinde fikstür elemanına çarpmadan çıkış
    cls = [(e.kutu(), BRepClass3d_SolidClassifier(e.sekil)) for e in fik]
    cls_parca = [(kutu(s), BRepClass3d_SolidClassifier(s)) for a, s in pc.hepsi
                 if not any(s is k for _, k in pc.kaynaklar)]
    yonler = [(0, 0, 1)]
    for a in (30, 45, 60):
        r = math.radians(a)
        for b in range(0, 360, 45):
            t = math.radians(b)
            yonler.append((math.sin(r) * math.cos(t), math.sin(r) * math.sin(t), math.cos(r)))
    L = 600.0

    def acik(p, u, siniflar):
        # ince sac (3 mm) kaçmasın diye yakında sık, uzakta seyrek örnekleme
        for t in [0.5 * i for i in range(2, 25)] + [15, 20, 30, 45, 60, 100, 160, 250, 400, L]:
            qx, qy, qz = p[0] + u[0] * t, p[1] + u[1] * t, p[2] + u[2] * t
            q = None
            for kb, c in siniflar:
                if not (kb.xmin - 1 < qx < kb.xmax + 1 and kb.ymin - 1 < qy < kb.ymax + 1
                        and kb.zmin - 1 < qz < kb.zmax + 1):
                    continue                      # kutu dışındaysa katı testine hiç girme
                if q is None:
                    q = gp_Pnt(qx, qy, qz)
                c.Perform(q, 1e-7)
                if c.State() in (TopAbs_IN, TopAbs_ON):
                    return False
        return True

    # ölçüt: fikstür tek başına yönlerin yarısını kapatmamalı VE parçanın kendi
    # gölgesinden arta kalan erişimin en az yarısını korumalı (torç, +Z etrafında
    # 60° koni içinde girebilmeli). Parçanın kendi gölgesi fikstürün kusuru
    # değildir; rapora ayrıca yazılır.
    hedefler = []
    for a, s in pc.kaynaklar:
        g = GProp_GProps(); BRepGProp.VolumeProperties_s(s, g); c = g.CentreOfMass()
        hedefler.append((a, (c.X(), c.Y(), c.Z()))) 
    if not hedefler:
        # montaj fikstürü: dikiş yok, parçaların birbirine değdiği yerlerde
        # (arayüz) el/takım erişimi kontrol edilir
        katilar = [(a, s) for a, s in pc.hepsi]
        for i in range(len(katilar)):
            for j in range(i + 1, len(katilar)):
                (a1, s1), (a2, s2) = katilar[i], katilar[j]
                d = BRepExtrema_DistShapeShape(s1, s2)
                if not d.IsDone() or d.Value() > 1.0:
                    continue
                q = d.PointOnShape1(1)
                hedefler.append((f"arayüz {a1[:18]} / {a2[:18]}", (q.X(), q.Y(), q.Z())))
    for a, p in hedefler:
        n_f = sum(1 for u in yonler if acik(p, u, cls))
        n_p = sum(1 for u in yonler if acik(p, u, cls_parca))
        n_t = sum(1 for u in yonler if acik(p, u, cls + cls_parca))
        rapor["kaynak_erisim"].append({"kaynak": a, "merkez": [round(v, 1) for v in p],
                                       "acik_yon_fikstur": n_f, "acik_yon_parca": n_p,
                                       "acik_yon_toplam": n_t, "toplam_yon": len(yonler),
                                       "ok": n_f >= len(yonler) * 0.5 and n_t >= 1
                                             and n_t >= 0.5 * n_p})
    rapor["ozet"] = {
        "cakisma_sayisi": len(rapor["cakisma"]),
        "temas_hatali": [t["eleman"] for t in rapor["temas"] if not t["ok"]],
        "kaynak_erisim_hatali": [k["kaynak"] for k in rapor["kaynak_erisim"] if not k["ok"]],
    }
    rapor["ozet"]["uyari"] = list(bilgi.get("uyari", []))
    rapor["ozet"]["gecti"] = (rapor["ozet"]["cakisma_sayisi"] == 0 and not rapor["ozet"]["temas_hatali"]
                              and not rapor["ozet"]["kaynak_erisim_hatali"] and not rapor["ozet"]["uyari"])
    return rapor


# ============================================================ çıktılar
RENK = {"taban": (0.55, 0.55, 0.58), "iskelet": (0.45, 0.45, 0.5), "dayama_A": (0.85, 0.15, 0.15),
        "dayama_B": (0.85, 0.45, 0.1), "yuva_C": (0.8, 0.65, 0.1), "klemp_dikey": (0.15, 0.45, 0.85),
        "klemp_yatay": (0.15, 0.6, 0.8), "klemp_itme": (0.2, 0.7, 0.6), "parca": (0.75, 0.75, 0.75),
        "kaynak": (0.95, 0.85, 0.2)}


def step_yaz(pc, el, yol, grup_ad):
    assy = cq.Assembly(name=f"FIKSTUR_{grup_ad}")
    fk = cq.Assembly(name="FIKSTUR")
    for e in el:
        fk.add(cq.Shape.cast(e.sekil), name=e.ad, color=cq.Color(*RENK.get(e.tip, (0.6, 0.6, 0.6))))
    assy.add(fk, name="FIKSTUR")
    pa = cq.Assembly(name=f"PARCA_{grup_ad}")
    sayac = Counter()
    for a, s in pc.hepsi:
        sayac[a] += 1
        ad = re.sub(r"[^\w\-. ]", "_", a)[:60]
        if sayac[a] > 1:
            ad += f"_{sayac[a]}"
        renk = RENK["kaynak"] if kaynak_mi(a) else RENK["parca"]
        pa.add(cq.Shape.cast(s), name=ad, color=cq.Color(*renk))
    assy.add(pa, name=f"PARCA_{grup_ad}")
    assy.save(yol, "STEP")


# Görünüşler: HLR projektöründe Ax2'nin Z ekseni SAHNEDEN GÖZE doğrudur.
# UST: göz +Z'de; ON: göz -Y'de (bakış +Y); YAN: göz +X'te (kapak ucundan bakış -X)
GORUNUSLER = {"UST": ((0, 0, 1), (1, 0, 0)), "ON": ((0, -1, 0), (1, 0, 0)), "YAN": ((1, 0, 0), (0, 1, 0))}


def hlr_kenarlar(sekil, yon, x_ref, y_ref=None):
    """Şeklin verilen bakış yönünde görünen / gizli / teğet kenarlarını 2B poligon listesi olarak döndür."""
    algo = HLRBRep_Algo(); algo.Add(sekil)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*yon), gp_Dir(*x_ref))))
    algo.Update(); algo.Hide()
    hs = HLRBRep_HLRToShape(algo)
    out = {"GORUNEN": [], "GIZLI": [], "TEGET": []}
    for kat, sh in (("GORUNEN", hs.VCompound()), ("GORUNEN", hs.OutLineVCompound()),
                    ("TEGET", hs.Rg1LineVCompound()), ("GIZLI", hs.HCompound()),
                    ("GIZLI", hs.OutLineHCompound())):
        if sh.IsNull():
            continue
        ex = TopExp_Explorer(sh, TopAbs_EDGE)
        while ex.More():
            e = TopoDS.Edge_s(ex.Current())
            c = BRepAdaptor_Curve(e)
            d = GCPnts_TangentialDeflection(c, 0.1, 0.3)
            pts = [c.Value(d.Parameter(i)) for i in range(1, d.NbPoints() + 1)]
            out[kat].append([(p.X(), p.Y()) for p in pts])
            ex.Next()
    return out


def dxf_yaz(pc, el, yol, grup_ad, bilgi, rapor, hizli=False):
    import ezdxf
    doc = ezdxf.new("R2010")
    for kat, renk in (("GORUNEN", 7), ("GIZLI", 8), ("TEGET", 9), ("YAZI", 3), ("SINIR", 1),
                      ("OLCU", 4), ("REFERANS", 6)):
        doc.layers.add(kat, color=renk)
    if "GIZLI" in doc.linetypes or True:
        try:
            doc.linetypes.add("DASHED2", pattern=[3.0, 2.0, -1.0])
            doc.layers.get("GIZLI").dxf.linetype = "DASHED2"
        except Exception:
            pass
    msp = doc.modelspace()
    fik = cq.Compound.makeCompound([cq.Shape.cast(e.sekil) for e in el])
    if hizli:
        prc = cq.Compound.makeCompound([cq.Shape.cast(kutu_cq(*[
            getattr(kutu(s), k) for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")]).val().wrapped)
            for _, s in pc.hepsi])
    else:
        prc = cq.Compound.makeCompound([cq.Shape.cast(s) for _, s in pc.hepsi])
    hep = cq.Compound.makeCompound([fik, prc])
    tb = bilgi["taban"]
    L = tb["x"][1] - tb["x"][0]; W = tb["y"][1] - tb["y"][0]
    H = pc.kutu_hepsi.zmax + 140
    # görünüşler: ÜST (bakış -Z), ÖN (bakış +Y), YAN (bakış -X)
    gor = [("UST", (0, 0)), ("ON", (0, -(W + 200))), ("YAN", (L + 200, -(W + 200)))]
    for ad, (ox, oy) in gor:
        yon, xr = GORUNUSLER[ad]
        kenarlar = hlr_kenarlar(hep.wrapped, yon, xr)
        for kat, poli in kenarlar.items():
            for pl in poli:
                if len(pl) < 2:
                    continue
                msp.add_lwpolyline([(x + ox, y + oy) for x, y in pl], dxfattribs={"layer": kat})
        msp.add_text(ad, dxfattribs={"layer": "YAZI", "height": 25}).set_placement((ox + (tb["x"][0] if ad != "YAN" else tb["y"][0]), oy + (tb["y"][1] + 40 if ad == "UST" else 260)))
    # ölçüler (üst görünüşte dayama X konumları, taban boyutu)
    y_olcu = tb["y"][0] - 60
    msp.add_linear_dim(base=(tb["x"][0], y_olcu - 60), p1=(tb["x"][0], tb["y"][0]), p2=(tb["x"][1], tb["y"][0]),
                       dxfattribs={"layer": "OLCU"}).render()
    for x in bilgi["dayama_x"]:
        msp.add_linear_dim(base=(tb["x"][0], y_olcu), p1=(tb["x"][0], tb["y"][0]), p2=(x, tb["y"][0]),
                           dxfattribs={"layer": "OLCU"}).render()
    # eleman etiketleri
    for e in el:
        if e.tip in ("taban", "iskelet"):
            continue
        k = e.kutu()
        msp.add_text(e.ad, dxfattribs={"layer": "YAZI", "height": 8}).set_placement(((k.xmin + k.xmax) / 2, k.ymax + 4))
    # referans / temas noktaları (üst görünüşte, onay JSON'u ile aynı numaralar)
    no = 0
    for e in el:
        for p in getattr(e, "basma", []):
            no += 1
            msp.add_circle((p[0], p[1]), 4, dxfattribs={"layer": "REFERANS"})
            msp.add_text(f"{no}", dxfattribs={"layer": "REFERANS", "height": 7}).set_placement((p[0] + 5, p[1] + 5))
    # liste
    x0, y0 = tb["x"][0], -(W + 200) - 400
    msp.add_text(f"{grup_ad} KAYNAK FIKSTURU  olcek 1:1  (+Z yukari, +X parca boyu)  "
                 f"parca {pc.kg:.2f} kg  yon {pc.yon}",
                 dxfattribs={"layer": "YAZI", "height": 14}).set_placement((x0, y0))
    for i, e in enumerate(el, 1):
        k = e.kutu()
        msp.add_text(f"{i:2d}  {e.ad:24s} {k.xlen:7.1f} x {k.ylen:7.1f} x {k.zlen:6.1f}  {e.kg():6.2f} kg  {e.malzeme}",
                     dxfattribs={"layer": "YAZI", "height": 9}).set_placement((x0, y0 - 18 * i))
    y0 -= 18 * (len(el) + 2)
    msp.add_text("KONTROL: " + ("GECTI" if rapor["ozet"]["gecti"] else "HATA VAR - rapora bak"),
                 dxfattribs={"layer": "YAZI", "height": 12}).set_placement((x0, y0))
    msp.add_lwpolyline([(tb["x"][0] - 100, y0 - 60), (tb["x"][1] + 700, y0 - 60), (tb["x"][1] + 700, tb["y"][1] + 100),
                        (tb["x"][0] - 100, tb["y"][1] + 100)], close=True, dxfattribs={"layer": "SINIR"})
    doc.saveas(yol)


def png_yaz(pc, el, yol, grup_ad, hizli=False):
    """2B izdüşümlü ön izleme: üst + ön görünüş (tam boy) ve kapak ucu yakın plan."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection
    except Exception:
        return False
    fik = cq.Compound.makeCompound([cq.Shape.cast(e.sekil) for e in el])
    prc = cq.Compound.makeCompound([cq.Shape.cast(s) for _, s in pc.hepsi])
    hep = cq.Compound.makeCompound([fik, prc]).wrapped
    gor = {"UST (bakis -Z)": GORUNUSLER["UST"], "ON (bakis +Y)": GORUNUSLER["ON"],
           "YAN (bakis -X, kapak ucu)": GORUNUSLER["YAN"]}
    kenar = {ad: hlr_kenarlar(hep, y, x) for ad, (y, x) in gor.items()}
    renk = {"GORUNEN": ("#1a1a1a", 0.7), "GIZLI": ("#9a9a9a", 0.4), "TEGET": ("#6a8fbf", 0.4)}
    tb = el[[e.tip for e in el].index("taban")].kutu()
    xe = pc.kutu_hepsi.xmax                 # montajın serbest ucu (uç plakası dahil)

    def ciz(ax, ad, xlim=None, ylim=None):
        for kat, poli in kenar[ad].items():
            c, w = renk[kat]
            segs = [[(x, y) for x, y in pl] for pl in poli if len(pl) > 1]
            ax.add_collection(LineCollection(segs, colors=c, linewidths=w))
        ax.set_aspect("equal"); ax.autoscale()
        if xlim: ax.set_xlim(*xlim)
        if ylim: ax.set_ylim(*ylim)
        ax.set_title(ad, fontsize=9); ax.tick_params(labelsize=7); ax.grid(True, lw=0.3, alpha=0.5)

    fig, axs = plt.subplots(2, 1, figsize=(20, 9))
    ciz(axs[0], "UST (bakis -Z)")
    ciz(axs[1], "ON (bakis +Y)")
    fig.suptitle(f"FIKSTUR {grup_ad} – {pc.yon} yukari – tam boy", fontsize=11)
    fig.tight_layout(); fig.savefig(yol, dpi=110); plt.close(fig)

    fig, axs = plt.subplots(1, 3, figsize=(20, 7))
    ciz(axs[0], "UST (bakis -Z)", (xe - 320, xe + 140), (tb.ymin - 20, tb.ymax + 20))
    ciz(axs[1], "ON (bakis +Y)", (xe - 320, xe + 140), (-80, 220))
    ciz(axs[2], "YAN (bakis -X, kapak ucu)", (tb.ymin - 20, tb.ymax + 20), (-80, 220))
    fig.suptitle(f"FIKSTUR {grup_ad} – kapak yuvasi / kaynak bolgesi yakin plan", fontsize=11)
    fig.tight_layout(); fig.savefig(yol.replace(".png", "_yuva.png"), dpi=110); plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(16, 6))
    xd = pc.kutu.xmin + 60
    ciz(axs[0], "UST (bakis -Z)", (tb.xmin - 20, xd + 700), (tb.ymin - 20, tb.ymax + 20))
    ciz(axs[1], "ON (bakis +Y)", (tb.xmin - 20, xd + 700), (-80, 220))
    fig.suptitle(f"FIKSTUR {grup_ad} – itme klempi / ilk dayamalar yakin plan", fontsize=11)
    fig.tight_layout(); fig.savefig(yol.replace(".png", "_bas.png"), dpi=110); plt.close(fig)

    kb = pc.kaynak_bolgeleri()
    if kb:
        xk = sorted(k.xmin for k in kb)[len(kb) // 2]
        fig, axs = plt.subplots(1, 2, figsize=(16, 6))
        ciz(axs[0], "UST (bakis -Z)", (xk - 260, xk + 260), (tb.ymin - 20, tb.ymax + 20))
        ciz(axs[1], "ON (bakis +Y)", (xk - 260, xk + 260), (-80, 220))
        fig.suptitle(f"FIKSTUR {grup_ad} – kaynak istasyonu X={xk:.0f} yakin plan", fontsize=11)
        fig.tight_layout(); fig.savefig(yol.replace(".png", "_kaynak.png"), dpi=110); plt.close(fig)
    return True


ONAY_ACIKLAMA = [
    "PiFikstur onay paketi - XYZ referans noktalari.",
    "Bu dosyayi inceleyin, gerekirse 'istasyon' altindaki X konumlarini duzenleyin,",
    "'onay' degerini true yapin ve su sekilde tekrar calistirin:",
    "    python pf2_fikstur.py <step> --sec \"...\" --onay <bu_dosya>",
    "istasyon: her eleman turunun parca boyunca (fikstur X ekseni) konumlari, mm.",
    "noktalar: her temas noktasinin hem fikstur hem de orijinal parca koordinati.",
    "_onay.png dosyasinda ayni noktalar parca uzerinde numarali olarak isaretlidir.",
]


def onay_yaz(pc, el, bilgi, rapor, on, grup_ad, kaynak_dosya):
    """Kullanıcı onayı için düzenlenebilir JSON + parça üzerinde işaretli PNG."""
    noktalar = []
    for i, e in enumerate(el, 1):
        for p in getattr(e, "basma", []):
            noktalar.append({"no": len(noktalar) + 1, "eleman": e.ad, "tip": e.tip,
                             "yon": e.temas_yonu,
                             "fikstur_xyz": [round(v, 2) for v in p],
                             "parca_xyz": list(pc.parca_noktasi(p))})
    js = {"_aciklama": ONAY_ACIKLAMA,
          "dosya": kaynak_dosya, "secim": grup_ad, "yon": pc.yon,
          "onay": False,
          "datum": {
              "A": f"Z ekseni - ana gövde alt yüzü, dayama üstü Z={bilgi['datum_A']['z']}",
              "B": "Y ekseni - -Y yan yüz (DAYAMA_B)",
              "C": "X ekseni - " + ", ".join(e.ad for e in el if e.tip in ("dayama_C", "yuva_C"))},
          "istasyon": bilgi.get("istasyon", {}),
          "noktalar": noktalar,
          "donusum": {"rotasyon": pc.R, "oteleme": [round(pc.dx, 3), round(pc.dy, 3), round(pc.dz, 3)],
                      "aciklama": "fikstur_xyz = R * parca_xyz + oteleme"},
          "uyari": bilgi.get("uyari", []),
          "kontrol_ozeti": rapor["ozet"]}
    json.dump(js, open(on + "_onay.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return onay_png(pc, noktalar, on + "_onay.png", grup_ad)


def onay_png(pc, noktalar, yol, grup_ad):
    """Parçayı tek başına çizip önerilen referans/temas noktalarını numaralar."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection
    except Exception:
        return False
    prc = cq.Compound.makeCompound([cq.Shape.cast(s) for _, s in pc.hepsi]).wrapped
    kenar = {ad: hlr_kenarlar(prc, *GORUNUSLER[ad]) for ad in ("UST", "ON")}
    renk = {"GORUNEN": ("#1a1a1a", 0.7), "GIZLI": ("#b0b0b0", 0.35), "TEGET": ("#6a8fbf", 0.35)}
    tip_renk = {"dayama_A": "#d62728", "dayama_B": "#ff7f0e", "dayama_C": "#8c564b",
                "yuva_C": "#bcbd22", "klemp_dikey": "#1f77b4", "klemp_yatay": "#17becf",
                "klemp_itme": "#2ca02c"}
    fig, axs = plt.subplots(2, 1, figsize=(20, 10))
    for ax, ad, (i1, i2) in ((axs[0], "UST", (0, 1)), (axs[1], "ON", (0, 2))):
        for kat, poli in kenar[ad].items():
            c, w = renk[kat]
            ax.add_collection(LineCollection([[(x, y) for x, y in pl] for pl in poli if len(pl) > 1],
                                             colors=c, linewidths=w))
        for n in noktalar:
            p = n["fikstur_xyz"]
            x, y = p[i1], p[i2] * (1 if ad == "ON" else 1)
            ax.plot(x, y, "o", ms=7, mfc=tip_renk.get(n["tip"], "#666"), mec="white", mew=0.8, zorder=5)
            ax.annotate(str(n["no"]), (x, y), textcoords="offset points", xytext=(6, 6),
                        fontsize=7, color=tip_renk.get(n["tip"], "#666"), zorder=6)
        ax.set_aspect("equal"); ax.autoscale(); ax.grid(True, lw=0.3, alpha=0.5)
        ax.set_title(f"{ad} - referans / temas noktalari", fontsize=9); ax.tick_params(labelsize=7)
    etiket = sorted({(n["tip"], tip_renk.get(n["tip"], "#666")) for n in noktalar})
    axs[0].legend(handles=[plt.Line2D([], [], marker="o", ls="", mfc=c, mec="white", label=t)
                           for t, c in etiket], fontsize=7, ncol=len(etiket), loc="upper right")
    fig.suptitle(f"{grup_ad} - ONAY: XYZ referans noktalari ({pc.yon} yukari). "
                 f"Numaralar _onay.json icindeki 'noktalar' listesiyle ayni.", fontsize=11)
    fig.tight_layout(); fig.savefig(yol, dpi=110); plt.close(fig)
    return True


def rapor_yaz(pc, el, bilgi, rapor, yol, grup_ad, args):
    L = []
    L.append(f"# {grup_ad} kaynak fikstürü – tasarım raporu\n")
    L.append(f"Kaynak dosya: `{args.step}`  |  yön: **{pc.yon}** yukarı  |  parça: {pc.kg:.2f} kg, "
             f"{len(pc.hepsi)} katı ({len(pc.kaynaklar)} kaynak dikişi)\n")
    L.append("Fikstür koordinatları: +Z yukarı, +X parça boyu, taban plakası üst yüzü Z=0.\n")
    k = pc.kutu_hepsi
    L.append(f"Parça zarfı (fikstürde): X {k.xmin:.1f}..{k.xmax:.1f}, Y {k.ymin:.1f}..{k.ymax:.1f}, Z {k.zmin:.1f}..{k.zmax:.1f}\n")
    L.append("## Konumlandırma (3-2-1)\n")
    L.append(f"- **Datum A (Z, 3+ nokta):** ana gövde alt yüzü, alan {bilgi['datum_A']['alan_mm2']:.0f} mm², "
             f"dayama üstü Z={bilgi['datum_A']['z']:.2f}; dayama X konumları: {bilgi['dayama_x']}")
    L.append(f"- **Datum B (Y, 2 nokta):** -Y yan yüz, yan dayamalar DAYAMA_B_01/02")
    cc = [e for e in el if e.tip in ("dayama_C", "yuva_C")]
    if cc:
        L.append("- **Datum C (X, 1 nokta):** " + "; ".join(f"{e.ad} ({e.not_})" for e in cc)
                 + ". Parçalar eksenel itme klempleriyle bu dayamalara bastırılır.\n")
    else:
        L.append("- **Datum C (X):** ayrı eksenel dayama gerekmedi.\n")
    if pc.ic_ice:
        L.append("İç içe geçen parçalar: " + ", ".join(a[:34] for a, _ in pc.ic_ice)
                 + ". Bunlar ana gövdenin içine oturduğu için Y ve Z yönünde ana gövde "
                   "tarafından konumlanır; fikstür yalnız eksenel konumu ve taşan ucu tutar.\n")
    L.append("## Elemanlar\n")
    L.append("| # | ad | tip | boyut (X×Y×Z) | kg | malzeme | not |")
    L.append("|---|----|-----|---------------|----|---------|-----|")
    for i, e in enumerate(el, 1):
        kb = e.kutu()
        L.append(f"| {i} | {e.ad} | {e.tip} | {kb.xlen:.0f}×{kb.ylen:.0f}×{kb.zlen:.0f} | {e.kg():.2f} | {e.malzeme} | {e.not_} |")
    L.append(f"\nFikstür toplam: **{sum(e.kg() for e in el):.1f} kg**\n")
    L.append("## Temas / basma noktaları (fikstür → parça koordinatı)\n")
    for e in el:
        for p in getattr(e, "basma", []):
            q = pc.parca_noktasi(p)
            L.append(f"- {e.ad}: F({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f}) → P{q}")
    for u in bilgi.get("uyari", []):
        L.append(f"\n> **UYARI:** {u}")
    L.append("\n## Kontroller\n")
    oz = rapor["ozet"]
    L.append(f"- Çakışma (fikstür–parça, fikstür–fikstür): {oz['cakisma_sayisi']} adet"
             + ("" if not rapor["cakisma"] else "  ← " + "; ".join(f"{c['eleman']}×{c['parca']} {c['hacim_mm3']} mm³" for c in rapor["cakisma"])))
    for t in rapor["temas"]:
        L.append(f"- Temas {t['eleman']}: {t['mesafe_mm']} mm {'✓' if t['ok'] else '✗'}")
    for kk in rapor["kaynak_erisim"]:
        L.append(f"- Kaynak erişimi {kk['kaynak']} @F{tuple(kk['merkez'])}: yalnız fikstür {kk['acik_yon_fikstur']}/{kk['toplam_yon']}, "
                 f"yalnız parça {kk['acik_yon_parca']}/{kk['toplam_yon']}, birlikte {kk['acik_yon_toplam']}/{kk['toplam_yon']} "
                 f"yön açık (60° koni) {'✓' if kk['ok'] else '✗'}")
    L.append(f"\n**SONUÇ: {'GEÇTİ' if oz['gecti'] else 'HATA VAR'}**\n")
    L.append("## Notlar\n")
    L.append("- Klempler zarf modelidir (GH-201-B / GH-304-CM sınıfı); üretimde tedarikçi modeliyle değiştirilir.")
    L.append("- Dayamalar altından M8 ile taban plakasına bağlanır (taban Ø9 delik, dayama M8 diş).")
    L.append("- Kapak yuvası -Y kulağı datumdur; +Y tarafı yatay klemple itilir (plaka genişlik toleransı).")
    L.append("- Kaynak dikişlerine 60 mm'den yakın eleman yerleştirilmemiştir; torç kanal içine üstten girer.")
    open(yol, "w", encoding="utf-8").write("\n".join(L) + "\n")


# ============================================================ CLI
def main():
    ap = argparse.ArgumentParser(description="ADIM 2 – fikstür tasarımı")
    ap.add_argument("step")
    ap.add_argument("--referans", help="ADIM 1 çıktısı JSON (grup ve yön buradan alınır)")
    ap.add_argument("--grup"); ap.add_argument("--parca", type=int)
    ap.add_argument("--sec", help='çoklu seçim: "G03,0,/DESTEK_SACi/" (grup, katı no, ad regexi)')
    ap.add_argument("--onay", help="onaylanmış <o>_onay.json; istasyon X konumları buradan alınır")
    ap.add_argument("--mod", choices=["kaynak", "montaj"], default="kaynak",
                    help="kaynak: dikişlere torç erişimi; montaj: arayüzlere takım erişimi")
    ap.add_argument("--yon", help="+X -X +Y -Y +Z -Z (yukarı)")
    ap.add_argument("-o", "--out", help="çıktı ön eki")
    ap.add_argument("--hizli", action="store_true", help="DXF'te parçayı kutu olarak çiz")
    ap.add_argument("--png", action="store_true", help="izometrik PNG üret")
    ap.add_argument("--param", help="JSON: PARAM üzerine yazılacak değerler")
    a = ap.parse_args()
    P = dict(PARAM)
    if a.param:
        P.update(json.load(open(a.param, encoding="utf-8")))
    ref = json.load(open(a.referans, encoding="utf-8")) if a.referans else None
    onay = json.load(open(a.onay, encoding="utf-8")) if a.onay else None
    if a.mod == "montaj":
        P["kaynak_pay"] = P.get("montaj_pay", 40.0)

    t0 = time.time()
    kayit, uyeler, grup_ad = grup_yukle(a.step, a.grup, a.parca, ref, a.sec)
    yon = yon_sec(kayit, uyeler, a.yon, onay or ref)
    if onay:
        print(f"onay dosyası: {a.onay}  (onay={onay.get('onay')}, "
              f"{sum(len(v) for v in onay.get('istasyon', {}).values())} istasyon)")
    print(f"{a.step}: {len(kayit)} katı, seçim {grup_ad} ({len(uyeler)} katı), yön {yon}  [{time.time()-t0:.0f}s]")
    pc = Parca(kayit, uyeler, yon, P)
    print(f"ana gövde: {pc.ana_ad}; ekler: {[a_ for a_, _ in pc.ekler]}; kaynak: {len(pc.kaynaklar)}")
    k = pc.kutu_hepsi
    print(f"parça zarfı: X {k.xmin:.1f}..{k.xmax:.1f}  Y {k.ymin:.1f}..{k.ymax:.1f}  Z {k.zmin:.1f}..{k.zmax:.1f}")

    el, bilgi = tasarla(pc, P, onay)
    print(f"{len(el)} eleman tasarlandı  [{time.time()-t0:.0f}s]")
    rapor = kontrol_et(pc, el, P, bilgi)
    oz = rapor["ozet"]
    print(f"kontrol: çakışma {oz['cakisma_sayisi']}, temas hatası {oz['temas_hatali']}, "
          f"kaynak erişim hatası {oz['kaynak_erisim_hatali']}, uyarı {oz['uyari']}  -> {'GEÇTİ' if oz['gecti'] else 'HATA'}")

    on = a.out or f"fikstur_{grup_ad}"
    step_yaz(pc, el, on + ".step", grup_ad); print(f"  {on}.step")
    js = {"dosya": a.step, "secim": grup_ad, "yon": yon, "parca_kg": round(pc.kg, 3),
          "rotasyon": pc.R, "oteleme": [pc.dx, pc.dy, pc.dz], "bilgi": bilgi,
          "elemanlar": [{"ad": e.ad, "tip": e.tip, "malzeme": e.malzeme, "not": e.not_, "kg": round(e.kg(), 3),
                         "kutu": [round(getattr(e.kutu(), kk), 2) for kk in ("xmin", "ymin", "zmin", "xmax", "ymax", "zmax")],
                         "basma": [[round(v, 2) for v in p] for p in getattr(e, "basma", [])]} for e in el],
          "kontrol": rapor, "param": P}
    json.dump(js, open(on + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(f"  {on}.json")
    rapor_yaz(pc, el, bilgi, rapor, on + ".md", grup_ad, a); print(f"  {on}.md")
    onay_yaz(pc, el, bilgi, rapor, on, grup_ad, a.step)
    print(f"  {on}_onay.json  ve  {on}_onay.png   <- XYZ referans onayı için")
    dxf_yaz(pc, el, on + ".dxf", grup_ad, bilgi, rapor, a.hizli); print(f"  {on}.dxf")
    if a.png and png_yaz(pc, el, on + ".png", grup_ad, a.hizli):
        print(f"  {on}.png")
    print(f"bitti [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
