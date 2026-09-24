# -*- coding: utf-8 -*-
"""
Pi3D – PAFTA

1:1 çizilmiş DXF'leri standart bir A3 paftaya yerleştirir. Ve bunu
yaparken:

    MODEL UZAYINA ASLA DOKUNULMAZ.

Bu bir kural, tercih değil. 1:1 çizim gerçeğin kendisidir; ölçüsü,
konumu, hiçbir şeyi değişmez. Pafta, o çizime bir PENCEREDEN bakar
(paper space viewport). Ölçek pencerenin özelliğidir, geometrinin değil.
Dolayısıyla "1:10 bastım" demek çizimi küçülttüm demek değildir; aynı
1:1 çizime uzaktan bakmak demektir. AutoCAD'de Model sekmesine
geçtiğinizde her şeyi eskisi gibi, birebir ölçüsünde bulursunuz.

PAFTANIN YAPISI (A3, 420 x 297 mm)

    +--------------------------------------------------+
    |  15 mm pay                                       |
    |   +------------------------------------------+   |
    |   |                                          |   |
    |   |          ÇİZİM BURAYA                    |   |
    |   |                                          |   |
    |   |                          +---------------+   |
    |   |                          |  ANTET ALANI  |   |
    |   +--------------------------+  150 x 100 mm +   |
    |                                                  |
    +--------------------------------------------------+

Antet ÇİZİLMEZ. Her firmanın anteti başka; programın uyduracağı bir
şey değil. Sağ alt köşedeki 150 x 100 mm'lik kutu boş bırakılır ve
oraya ASLA çizim gelmez - firma kendi antetini oraya yapıştırır.

Çizim, antet kutusunun üstündeki ya da solundaki alanlardan hangisi
daha büyük ölçek veriyorsa oraya oturur.
"""
from __future__ import annotations
import os

import ezdxf
import ezdxf.bbox
import ezdxf.enums          # ezdxf sürümüne göre kendiliğinden gelmeyebilir

# ---------------------------------------------------------------- kâğıt
# Kâğıt YATAY ya da DİKEY olabilir; hangisi daha büyük ölçek veriyorsa o
# kullanılır. Önce yalnız yatay vardı: gerekçe, sac açınımlarının hep
# uzun olması ve antet kutusunun sağ alt köşede sabit durmasıydı. Ama
# uzun bir parça DİK duruyorsa (3000 mm boyunda bir profilin ön
# görünüşü) yatay kâğıtta 1:50'ye düşüyor ve resim neredeyse
# görünmüyordu; aynı parça dikey kâğıtta 1:20 çıkıyor. Kâğıdı parçaya
# uydurmak, parçayı kâğıda kurban etmekten iyidir.
#
# Dikey karşılıkların adı "-D" ekiyle yazılır: "A3" yatay, "A3-D"
# dikey. Böylece kâğıda bakan bütün işlevler (cerceve, antet_kutusu,
# cizim_alanlari, BOLGE...) tek bir sözlükten okumaya devam eder.
YON_EKI = "-D"

def _yon_ekle(d):
    """Her yatay kâğıdın dikey karşılığını da sözlüğe koyar."""
    for ad, (g, y) in list(d.items()):
        d[ad + YON_EKI] = (y, g)
    return d


KAGIT = _yon_ekle({
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
})
KAGIT_BOY = ("A4", "A3", "A2", "A1", "A0")     # yalnız boylar, yönsüz
KAGIT_SIRA = tuple(k for b in KAGIT_BOY for k in (b, b + YON_EKI))
VARSAYILAN_KAGIT = "A3"


def kagit_boyu(kagit):
    """Yön ekini atar: "A3-D" -> "A3"."""
    return kagit[:-len(YON_EKI)] if kagit.endswith(YON_EKI) else kagit


def dikey_mi(kagit):
    return kagit.endswith(YON_EKI)


def kagit_yonleri(kagit):
    """Bu boyun iki yönü: (yatay, dikey). Yön eki verilse de aynı."""
    b = kagit_boyu(kagit)
    return (b, b + YON_EKI)


def yon_adi(kagit):
    return "dikey" if dikey_mi(kagit) else "yatay"


def kagit_adi(kagit):
    """Kullanıcıya gösterilecek ad: "A3 yatay" / "A3 dikey"."""
    return f"{kagit_boyu(kagit)} {yon_adi(kagit)}"

KENAR = 15.0                 # çerçeve kâğıdın kenarından bu kadar içeride
DIS_PAY = 5.0                # ince dış çizgi kâğıdın kenarından
ANTET_EN, ANTET_BOY = 150.0, 100.0     # sağ alt köşede boş bırakılan kutu

# Bölge bölümleri (ISO 5457): rakamlar soldan sağa, harfler yukarıdan
# aşağıya. "B3'teki delik" demek için. Sütun ve satır sayısı çifttir.
BOLGE = {"A4": (6, 4), "A3": (8, 4), "A2": (12, 6),
         "A1": (16, 8), "A0": (24, 12)}
# Dikey kâğıtta sütun ve satır sayısı yer değiştirir: bölge kareleri
# yine kareye yakın kalsın.
BOLGE.update({a + YON_EKI: (y, x) for a, (x, y) in list(BOLGE.items())})
BOLGE_HARF = "ABCDEFGHIJKL"

GORUNUS_KATMAN = "PI3D_GORUNUS_ALANI"   # motorun bıraktığı görünüş yerleri
GORUNUS_APPID = "PI3D"
BASLIK_AD = "BASLIK"
IC_PAY = 12.0            # çerçevenin ve antet alanının resme uzaklığı
# Çerçevenin üstünde resim no/isim için ayrılan şerit. Yazıların
# gerçekten ihtiyacı kadar: 4,5 + 3,0 mm yazı + paylar. Bir mm fazlası
# ölçeği bir kademe düşürebiliyor (A3'te 1:2 yerine 1:5), o yüzden dar
# tutuluyor.
BASLIK_YAZI, BASLIK_ALT_YAZI = 4.5, 3.0
BASLIK_SERIT = 11.7          # sag ust baslik seridi: 0,8 + 4,5lik satir + 1,6 + 3,0luk satir,
                            # yaziların olculen tasmalariyla birlikte
# Görünüşler arasındaki aralık. EN_AZ bir tercih değil, alt sınırdır:
# yüksek tutmak bir kademe ölçek kaybettirebiliyor (A3'te 1:2 yerine
# 1:5, yani resim yarı yarıya küçülüyor). 8 mm iki görünüşü ayırmaya
# yeter; yer varsa zaten EN_COK'a kadar açılıyor.
ARA_EN_AZ = 10.0
ARA_EN_COK = 45.0        # ve en çok bu kadar; yoksa köşelere dağılırlar

HARF_ORAN = 0.62         # yazı genişliği ~ harf sayısı x yükseklik x bu
EN_AZ_YAZI_MM = 1.8      # kâğıtta bundan küçük yazı okunmaz (ISO 3098: 2,5)

# Teknik resimde kullanılan standart ölçekler (ISO 5455). Ara ölçek
# uydurulmaz: 1:7 diye bir resim olmaz.
KUCULTME = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
BUYUTME = (2, 5, 10)

KAT_CERCEVE = "PAFTA_CERCEVE"
KAT_ANTET = "PAFTA_ANTET_ALANI"
KAT_BILGI = "PAFTA_BILGI"
KAT_BOLGE = "PAFTA_BOLGE"


class PaftaYok(Exception):
    """Pafta kurulamadı; mesaj kullanıcıya gösterilir."""


# ------------------------------------------------------------ yardımcı
def _yazi_kutusu(e):
    """Bir yazının kapladığı yerin yaklaşık sınırı.

    DXF yazının genişliğini saklamaz; yazı tipine göre değişir. CAD'in
    txt/iso yazı tipinde harf ilerlemesi yaklaşık yüksekliğin 0,62'si
    kadardır. Amaç ölçü vermek değil, yazının kâğıt dışında kalmasını
    önlemek."""
    t = e.dxftype()
    try:
        if t == "MTEXT":
            h = float(e.dxf.char_height or 2.5)
            sat = (e.text or "").replace("\\P", "\n").split("\n")
            g = float(getattr(e.dxf, "width", 0) or 0)
            if g <= 0:
                g = HARF_ORAN * h * max((len(x) for x in sat), default=0)
            b = h * 1.6 * max(len(sat), 1)
            x, y = e.dxf.insert.x, e.dxf.insert.y
            # MTEXT dayanak noktası: 1-3 üst, 4-6 orta, 7-9 alt
            d = int(getattr(e.dxf, "attachment_point", 1) or 1)
            x -= {1: 0, 2: 0.5, 0: 0}.get((d - 1) % 3, 1.0) * g
            y -= {0: 1.0, 1: 0.5, 2: 0.0}.get((d - 1) // 3, 1.0) * b
            return (x, y, x + g, y + b)
        h = float(e.dxf.height or 2.5)
        m = e.dxf.text or ""
        g = HARF_ORAN * h * len(m) * float(getattr(e.dxf, "width", 1.0) or 1.0)
        yatay = int(getattr(e.dxf, "halign", 0) or 0)
        dusey = int(getattr(e.dxf, "valign", 0) or 0)
        p = e.dxf.align_point if yatay or dusey else e.dxf.insert
        x, y = p.x, p.y
        x -= {0: 0.0, 1: 0.5, 2: 1.0, 4: 0.5}.get(yatay, 0.0) * g
        y -= {0: 0.0, 1: 0.0, 2: 0.5, 3: 1.0}.get(dusey, 0.0) * h
        return (x, y, x + g, y + h)
    except Exception:
        return None


def _varlik_kutusu(uzay, yazi=True):
    """Bir uzaydaki çizimin sınırları (x0, y0, x1, y1) ya da None."""
    xs, ys = [], []

    def ekle(k):
        if k:
            xs.extend((k[0], k[2])); ys.extend((k[1], k[3]))

    for e in uzay:
        t = e.dxftype()
        try:
            if t == "LWPOLYLINE":
                for x, y, *_ in e.get_points():
                    xs.append(x); ys.append(y)
            elif t == "LINE":
                xs += [e.dxf.start.x, e.dxf.end.x]
                ys += [e.dxf.start.y, e.dxf.end.y]
            elif t in ("CIRCLE", "ARC"):
                c, r = e.dxf.center, e.dxf.radius
                xs += [c.x - r, c.x + r]; ys += [c.y - r, c.y + r]
            elif t in ("TEXT", "MTEXT"):
                if yazi:
                    ekle(_yazi_kutusu(e))
            elif t == "POINT":
                xs.append(e.dxf.location.x); ys.append(e.dxf.location.y)
        except Exception:
            continue
    if not xs:
        return None
    return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))


def cizim_kutusu(yol):
    """1:1 DXF'in model uzayındaki sınırları — HER ŞEY DAHİL.

    Yazı da, ölçü de resmin parçasıdır. Pencereyi yalnız geometriye göre
    açarsak bunlar kenardan kırpılır; ilk denemede tam da bu oldu:
    büküm tablosu yarıdan kesildi, sol taraftaki genişlik ölçüsü
    (parçanın 154 mm solunda duruyordu) resme hiç girmedi.

    Ölçüler DIMENSION varlığıdır ve çizgileri adsız bir BLOK içinde
    durur; elle gezerek bulunamaz. ezdxf'in kendi sınır hesabı blokları
    açar ve yazıyı yazı tipinden ölçer, o yüzden önce o denenir."""
    d = ezdxf.readfile(yol)
    try:
        k = ezdxf.bbox.extents(
            [e for e in d.modelspace() if e.dxf.layer != GORUNUS_KATMAN],
            fast=False)
        if k.has_data:
            return (float(k.extmin.x), float(k.extmin.y),
                    float(k.extmax.x), float(k.extmax.y))
    except Exception:
        pass                      # eski ezdxf ya da bozuk varlık: kabaca ölç
    k = _varlik_kutusu(d.modelspace())
    if not k:
        raise PaftaYok(f"{os.path.basename(yol)}: çizimde varlık yok.")
    return k


def gorunus_alanlari(d):
    """Motorun işaretlediği görünüş yerleri: {ad: (x0, y0, x1, y1)}.

    Yoksa boş sözlük döner - eski resimler ve elle çizilmiş DXF'ler
    tek pencereyle yerleşir."""
    a = {}
    for e in d.modelspace().query(f'LWPOLYLINE[layer=="{GORUNUS_KATMAN}"]'):
        try:
            x = e.get_xdata(GORUNUS_APPID)
        except Exception:
            continue
        ad = next((v for k, v in x if k == 1000), None)
        if not ad:
            continue
        p = [(q[0], q[1]) for q in e.get_points()]
        a[ad] = (min(q[0] for q in p), min(q[1] for q in p),
                 max(q[0] for q in p), max(q[1] for q in p))
    return a


def _kumele(araliklar, pay=1e-6):
    """Üst üste binen aralıkları gruplar, küçükten büyüğe sıralı döner.

    Görünüşler izdüşüm ızgarasındadır: aynı sütundakiler x'te örtüşür,
    aynı satırdakiler y'de. Örtüşmeye bakmak merkezleri yuvarlamaktan
    sağlamdır - görünüş boyları birbirinden çok farklı olabilir."""
    if not araliklar:
        return []
    sirali = sorted(araliklar, key=lambda t: t[0])
    grup = [[sirali[0][0], sirali[0][1], [sirali[0][2]]]]
    for a, b, ad in sirali[1:]:
        if a < grup[-1][1] - pay:
            grup[-1][1] = max(grup[-1][1], b)
            grup[-1][2].append(ad)
        else:
            grup.append([a, b, [ad]])
    return grup


def _kutu_uzakligi(k, b):
    """Bir varlık kutusunun bir görünüş kutusuna uzaklığı (içindeyse 0)."""
    dx = max(b[0] - k[2], k[0] - b[2], 0.0)
    dy = max(b[1] - k[3], k[1] - b[3], 0.0)
    return dx * dx + dy * dy


def _gorunus_kutulari(d, alanlar):
    """Her görünüşün GERÇEK sınırı: ona ait bütün çizgi, ölçü ve yazı.

    Motorun bıraktığı işaret yalnız görünüşün kendisini gösterir; ölçü
    çizgileri, etiketler, çap yazıları onun dışına taşar. Her varlık en
    yakın görünüşe verilir, sınır o varlıklardan çıkarılır. Hücrelerin
    GERÇEKTEN dar olması şart: görünüşler arasındaki büyük model
    boşlukları böyle dışarıda kalır ve kâğıtta yerlerine eşit aralıklar
    konur. Aynı kâğıtta daha büyük ölçek buradan çıkar.

    Hiçbir varlık dışarıda kalmaz: her biri bir görünüşe yazılır."""
    gor = {k: v for k, v in alanlar.items() if k != BASLIK_AD}
    if not gor:
        return {}
    bas = alanlar.get(BASLIK_AD)
    kutu = {k: list(v) for k, v in gor.items()}
    try:
        varlik = [e for e in d.modelspace() if e.dxf.layer != GORUNUS_KATMAN]
        kutular = ezdxf.bbox.multi_flat(varlik)
    except Exception:
        return {k: tuple(v) for k, v in kutu.items()}
    for k in kutular:
        if not k.has_data:
            continue
        b = (k.extmin.x, k.extmin.y, k.extmax.x, k.extmax.y)
        if bas and (b[0] >= bas[0] - 0.01 and b[1] >= bas[1] - 0.01
                    and b[2] <= bas[2] + 0.01 and b[3] <= bas[3] + 0.01):
            continue                    # başlık bloğunun parçası
        ad = min(gor, key=lambda a: _kutu_uzakligi(b, gor[a]))
        q = kutu[ad]
        q[0] = min(q[0], b[0]); q[1] = min(q[1], b[1])
        q[2] = max(q[2], b[2]); q[3] = max(q[3], b[3])
    return {k: tuple(v) for k, v in kutu.items()}


def _izgara(d, alanlar, kutu):
    """Görünüşleri satır/sütun ızgarasına oturtur.

    İzdüşüm ızgarası BOZULMAZ: aynı satırdaki görünüşler kâğıtta da aynı
    hizada, aynı sütundakiler aynı düşeyde kalır. Bunu sağlamak için bir
    satırdaki bütün hücreler o satırın ORTAK y aralığını, bir sütundaki
    hücreler ortak x aralığını kullanır; yoksa görünüşler birbirinden
    kayar ve resim teknik resim olmaktan çıkar.

    Döner: (sutun_gen, satir_boy, hucre) ya da None."""
    dar = _gorunus_kutulari(d, alanlar)
    if len(dar) < 2:
        return None
    sut = _kumele([(v[0], v[2], k) for k, v in dar.items()])
    sat = _kumele([(v[1], v[3], k) for k, v in dar.items()])
    if len(sut) < 2 and len(sat) < 2:
        return None                     # tek göz: dağıtılacak bir şey yok
    for g in (sut, sat):                # gruplar üst üste binmemeli
        for a, b in zip(g, g[1:]):
            if b[0] < a[1] - 1e-6:
                return None
    yerm = {}
    for j, g in enumerate(sut):
        for ad in g[2]:
            yerm.setdefault(ad, [0, 0])[0] = j
    for i, g in enumerate(sat):
        for ad in g[2]:
            yerm.setdefault(ad, [0, 0])[1] = i
    hucre = {ad: (j, i, (sut[j][0], sat[i][0], sut[j][1], sat[i][1]))
             for ad, (j, i) in yerm.items()}
    return ([g[1] - g[0] for g in sut], [g[1] - g[0] for g in sat], hucre)


def _pencere_temiz_mi(d, hucreler):
    """Her çizgi TAM OLARAK BİR pencerenin içinde mi?

    Bu denetim şart, çünkü bir pencere kendisine "ait" olanı değil,
    DİKDÖRTGENİNE DÜŞEN HER ŞEYİ gösterir. Bir yazı iki pencerenin
    sınırına denk gelirse ikisinde de, yarım yarım çıkar; hiçbirine
    düşmezse hiç çıkmaz. Montaj resminde tam bu oldu: başlık bloğu
    görünüş pencerelerinin sınırına denk geldi ve paftada hem doğru
    yerinde hem de görünüşlerin arasında parça parça göründü.

    Bir tane bile şüpheli varlık varsa çok pencereli yerleşimden
    vazgeçilir; tek pencere, bozuk resimden iyidir."""
    # Önce pencereler birbirinin üstüne binmesin: binerse ortak bölgedeki
    # çizgi İKİ kere basılır.
    for i in range(len(hucreler)):
        for j in range(i + 1, len(hucreler)):
            a, b = hucreler[i], hucreler[j]
            if (a[0] < b[2] - 0.02 and a[2] > b[0] + 0.02
                    and a[1] < b[3] - 0.02 and a[3] > b[1] + 0.02):
                return False
    try:
        varlik = [e for e in d.modelspace() if e.dxf.layer != GORUNUS_KATMAN]
        for k in ezdxf.bbox.multi_flat(varlik):
            if not k.has_data:
                continue
            b = (k.extmin.x, k.extmin.y, k.extmax.x, k.extmax.y)
            # Ölçüt tek: varlık TAM OLARAK BİR hücrenin içinde olmalı.
            # Hücreler birbiriyle çakışmadığı için "birden fazlasının
            # içinde" olamaz; hiçbirinin içinde değilse ya sınırı aşıyor
            # (iki pencerede yarım yarım çıkar) ya da hepsinin dışında
            # (hiç çıkmaz). İkisi de kabul edilemez.
            #
            # Pay şart: görünüşün tam kenarında duran sıfır genişlikli
            # çizgiler var (parçanın kenar konturu), onlar hücrenin
            # içinde sayılmalı.
            if sum(1 for c in hucreler
                   if b[0] >= c[0] - 0.02 and b[1] >= c[1] - 0.02
                   and b[2] <= c[2] + 0.02 and b[3] <= c[3] + 0.02) != 1:
                return False
    except Exception:
        return False
    return True


def en_kucuk_yazi(yol):
    """Çizimdeki en küçük yazının model uzayındaki yüksekliği (mm).

    Ölçekle çarpılınca kâğıtta kaç mm kalacağı çıkar. Uzun parçalar
    küçük ölçeğe düşer ve yazıları okunmaz hale gelir; kullanıcının
    bunu paftayı basmadan önce bilmesi gerekir."""
    d = ezdxf.readfile(yol)
    h = []
    for e in d.modelspace():
        try:
            if e.dxftype() == "TEXT":
                h.append(float(e.dxf.height))
            elif e.dxftype() == "MTEXT":
                h.append(float(e.dxf.char_height))
        except Exception:
            continue
    return min((v for v in h if v > 0), default=0.0)


def olcek_metni(o):
    """0.1 -> '1:10',  2 -> '2:1',  1 -> '1:1'"""
    if abs(o - 1.0) < 1e-9:
        return "1:1"
    if o < 1:
        return f"1:{round(1 / o)}"
    return f"{round(o)}:1"


def cerceve(kagit=VARSAYILAN_KAGIT, sablon=None):
    """Çerçevenin köşeleri (x0, y0, x1, y1).

    Firma anteti kullanılıyorsa çerçeve de ONUN çerçevesidir: antet ve
    çerçeve aynı çizimden gelir, ikisini ayırmak resmin kenar paylarını
    firmanınkinden farklı yapardı."""
    if kagit not in KAGIT:
        raise PaftaYok(f"Bilinmeyen kâğıt: {kagit}")
    g, y = KAGIT[kagit]
    if sablon is not None:
        return sablon.cerceve((g, y))
    return (KENAR, KENAR, g - KENAR, y - KENAR)


def antet_kutusu(kagit=VARSAYILAN_KAGIT, sablon=None):
    """Sağ alt köşede BOŞ bırakılan alan (x0, y0, x1, y1).

    Buraya asla resim gelmez; firma kendi antetini oraya yapıştırır.
    ÇİZİLMEZ - kendi çerçevesi olan bir anteti yapıştırınca iki çizgi
    üst üste binerdi. Alan yalnız hesapta vardır.

    Ölçüsü kâğıttan kâğıda değişmez: antet A3'te ne kadarsa A1'de de
    o kadardır. Yazı boyları kâğıtla büyümez."""
    if sablon is not None:
        return sablon.antet_kutusu(KAGIT[kagit])
    x0, y0, x1, y1 = cerceve(kagit)
    return (max(x0, x1 - ANTET_EN), y0, x1, min(y1, y0 + ANTET_BOY))


def cizim_alanlari(kagit=VARSAYILAN_KAGIT, sablon=None):
    """Çizimin oturabileceği iki dikdörtgen.

    Antet kutusu sağ alt köşeyi yediği için kalan boşluk L biçimindedir.
    Bir resim dikdörtgendir; L'ye iki türlü sığar: kutunun ÜSTÜNE tam
    genişlikte, ya da SOLUNA tam yükseklikte. Hangisi daha büyük ölçek
    veriyorsa o kullanılır.

    Alanlar çerçeveye ve antet alanına DAYANMAZ: her yönde IC_PAY
    kadar (12 mm) boşluk bırakılır. Çerçeveye yapışmış bir resim hem
    kötü görünür hem de baskıda kenara taşma riski taşır. Çerçevenin
    üstünde ayrıca BASLIK_SERIT kadar yer resim no ve isim içindir."""
    fx0, fy0, fx1, fy1 = cerceve(kagit, sablon)
    ax0, _, _, ay1 = antet_kutusu(kagit, sablon)
    p = IC_PAY
    # Resim no/isim, çerçevenin üstündeki İÇ PAYIN İÇİNE yazılır; o pay
    # zaten boştu. Ayrıca yer ayırmak gereksiz yere ölçek düşürüyordu -
    # A3'te 1:2 yerine 1:5, yani resim yarı yarıya küçülüyordu.
    # Firma anteti varsa resim no ve isim ANTETE yazılır; çerçevenin
    # üstünde ayrıca başlık şeridine gerek yoktur.
    ust = fy1 - (p if sablon is not None else max(p, BASLIK_SERIT + 1.0))
    return {"ust": (fx0 + p, ay1 + p, fx1 - p, ust),
            "sol": (fx0 + p, fy0 + p, ax0 - p, ust)}


def sigan_olcek(gx, gy, alan_g, alan_y, buyutme=False):
    """Çizimi alana sığdıran EN BÜYÜK standart ölçek. Sığmıyorsa None.

    Önce 1:1 denenir - teknik resimde tercih her zaman birebirdir.
    Sonra sırayla küçültülür. Büyütme İSTENMEDİKÇE yapılmaz: kimse
    küçük bir parçanın kendiliğinden 2:1 çizilmesini beklemez."""
    if alan_g <= 0 or alan_y <= 0:
        return None
    if gx <= alan_g and gy <= alan_y:
        if buyutme:
            for b in reversed(BUYUTME):
                if gx * b <= alan_g and gy * b <= alan_y:
                    return float(b)
        return 1.0
    for k in KUCULTME[1:]:
        if gx / k <= alan_g and gy / k <= alan_y:
            return 1.0 / k
    return None


def yerlesim(gx, gy, kagit=VARSAYILAN_KAGIT, buyutme=False, sablon=None):
    """Çizim bu kâğıda nasıl oturur.

    Döner: {"olcek":, "yer": "ust"/"sol", "alan": (x0,y0,x1,y1),
            "kagit": kullanılan kâğıt (yön ekiyle)}
    Sığmıyorsa None.

    Yön ekiyle bir kâğıt verilirse ("A3-D") yalnız o yön denenir.
    Yönsüz verilirse ("A3") İKİ YÖN DE denenir ve daha büyük ölçek
    veren seçilir; eşitse yatay kalır (teknik resimde alışılmış olan
    odur, ayrıca dosyalama kolaylığı).

    Firma anteti kullanılıyorsa yön aranmaz: antet yatay çizilmiştir,
    dikey karşılığı yoktur."""
    adaylar = ((kagit_yonleri(kagit) if not dikey_mi(kagit) else (kagit,))
               if sablon is None else (kagit_boyu(kagit),))
    en_iyi = None
    for kg in adaylar:
        for yer, a in cizim_alanlari(kg, sablon).items():
            o = sigan_olcek(gx, gy, a[2] - a[0], a[3] - a[1], buyutme)
            if o and (en_iyi is None or o > en_iyi["olcek"]):
                en_iyi = {"olcek": o, "yer": yer, "alan": a, "kagit": kg}
    return en_iyi


def kagit_sec(gx, gy, adaylar=KAGIT_BOY, en_az_olcek=1.0, sablon=None):
    """Çizimi istenen ölçekte alan EN KÜÇÜK kâğıt (yön ekiyle). Yoksa None."""
    for k in adaylar:
        y = yerlesim(gx, gy, k, sablon=sablon)
        if y and y["olcek"] >= en_az_olcek - 1e-9:
            return y.get("kagit", k)
    return None


# --------------------------------------------------------------- pafta
def cok_pencere_plani(d, kutu, alan_g, alan_y):
    """Görünüşleri kâğıda ORTADAN DIŞA, eşit aralıklarla dağıtan plan.

    Mantık: görünüşler resimde zaten izdüşüm ızgarasındadır (ÖN'ün solu
    SAĞ, sağı SOL, altı ÜST). O ızgara bozulmaz - bozulursa resim teknik
    resim olmaktan çıkar. Değişen yalnız ARALIKLAR: resimdeki büyük
    model boşlukları atılır, yerine kâğıtta eşit aralıklar konur ve
    öbek kâğıdın ortasına oturur.

    Dar ve uzun bir parçada da kural aynıdır; yalnız ölçek düşer ve
    aralık daralır. Dayanak noktası hiçbir zaman kenar değildir.

    Döner: {"olcek", "sutun", "satir", "hucre", "baslik", ...} ya da
    None (ızgara kurulamadıysa; o zaman tek pencere kullanılır)."""
    alanlar = gorunus_alanlari(d)
    iz = _izgara(d, alanlar, kutu)
    if not iz:
        return None
    sutun, satir, hucre = iz
    baslik = alanlar.get(BASLIK_AD)
    bg = (baslik[2] - baslik[0]) if baslik else 0.0
    bb = (baslik[3] - baslik[1]) if baslik else 0.0
    hepsi = [h[2] for h in hucre.values()] + ([baslik] if baslik else [])
    if not _pencere_temiz_mi(d, hepsi):
        return None

    ts, tr = sum(sutun), sum(satir)
    nj, ni = len(sutun), len(satir)
    olcek = None
    for k in KUCULTME:
        o = 1.0 / k
        gen = max(ts * o + (nj - 1) * ARA_EN_AZ, bg * o)
        boy = tr * o + (ni - 1) * ARA_EN_AZ + (bb * o + ARA_EN_AZ if baslik else 0)
        if gen <= alan_g + 1e-6 and boy <= alan_y + 1e-6:
            olcek = o
            break
    if not olcek:
        return None

    def _kis(v, alt, ust):
        return alt if v < alt else (ust if v > ust else v)

    ax = _kis((alan_g - ts * olcek) / (nj + 1), ARA_EN_AZ, ARA_EN_COK) if nj > 1 else 0.0
    kalan_y = alan_y - (bb * olcek + ARA_EN_AZ if baslik else 0)
    ay = _kis((kalan_y - tr * olcek) / (ni + 1), ARA_EN_AZ, ARA_EN_COK) if ni > 1 else 0.0
    obek_g = ts * olcek + (nj - 1) * ax
    obek_y = tr * olcek + (ni - 1) * ay
    return {"olcek": olcek, "sutun": sutun, "satir": satir, "hucre": hucre,
            "baslik": baslik, "ara_x": ax, "ara_y": ay,
            "obek": (max(obek_g, bg * olcek),
                     obek_y + (bb * olcek + ARA_EN_AZ if baslik else 0)),
            "gorunus_obek": (obek_g, obek_y), "baslik_olcu": (bg, bb)}


def _cok_pencere_ciz(pafta, plan, sol, alt):
    """Planı kâğıda koyar. (sol, alt) öbeğin sol alt köşesi."""
    o = plan["olcek"]
    og, oy = plan["gorunus_obek"]
    tg, ty = plan["obek"]
    bg, bb = plan["baslik_olcu"]
    say = 0
    if plan["baslik"]:
        x0, y0, x1, y1 = plan["baslik"]
        pafta.add_viewport(
            center=(sol + bg * o / 2.0, alt + ty - bb * o / 2.0),
            size=(bg * o, bb * o),
            view_center_point=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
            view_height=(y1 - y0))
        say += 1
    gsol = sol + (tg - og) / 2.0          # görünüş öbeği kendi içinde ortalı
    for _ad, (j, i, c) in plan["hucre"].items():
        gx = gsol + sum(plan["sutun"][:j]) * o + j * plan["ara_x"]
        gy = alt + sum(plan["satir"][:i]) * o + i * plan["ara_y"]
        w, hh = plan["sutun"][j] * o, plan["satir"][i] * o
        pafta.add_viewport(
            center=(gx + w / 2.0, gy + hh / 2.0), size=(w, hh),
            view_center_point=((c[0] + c[2]) / 2.0, (c[1] + c[3]) / 2.0),
            view_height=(c[3] - c[1]))
        say += 1
    return say


YAZI_STILI = "PI3D"
YAZI_FONTU = "arial.ttf"
YAZI_AILESI = "Arial"


def yazi_stili(d):
    """Pafta yazıları için Türkçe harf gösteren TrueType stil.

    Hazır "Standard" stili txt.shx kullanır; o SHX fontunda Ğ Ş İ Ç Ö Ü
    glifi yoktur ve AutoCAD bu harfleri "?" ya da boş kutu çizer. Dosya
    UTF-8'dir, eksik olan fonttur. pf3_olcu'nun ürettiği çizimlerde bu stil
    zaten vardır; dışarıdan gelen bir DXF'e pafta eklenirse burada kurulur."""
    try:
        if YAZI_STILI in d.styles:
            st = d.styles.get(YAZI_STILI)
        else:
            st = d.styles.add(YAZI_STILI, font=YAZI_FONTU)
        st.dxf.font = YAZI_FONTU
        try:
            st.set_extended_font_data(family=YAZI_AILESI,
                                      italic=False, bold=False)
        except Exception:
            pass
        return YAZI_STILI
    except Exception:
        return "Standard"


def turkce_duzelt(d):
    """Çizimdeki eski yazıları Türkçe gösteren stile taşır.

    Sorunun kaynağı dosyanın kodlaması DEĞİLDİR: DXF R2010 UTF-8'dir ve
    "Ğ" dosyaya gerçekten C4 9E olarak yazılır. AutoCAD yazıyı STİLİN font
    dosyasıyla çizer; hazır "Standard" stili txt.shx'tir ve o SHX fontta
    yalnızca ASCII glifleri vardır - Ğ Ş İ Ç Ö Ü yerine "?" ya da boş kutu
    çıkar.

    Yeni üretilen çizimler zaten PI3D stiliyle yazılıyor. Bu işlev, daha
    önce üretilmiş dosyalar için: SHX fontlu stildeki yazıları PI3D'ye
    çevirir, böylece STP'yi baştan okumaya gerek kalmaz. Yalnız yazı
    stili değişir, metin ve konum ellenmez.

    Döndürdüğü: değiştirilen varlık sayısı."""
    stil = yazi_stili(d)
    if stil != YAZI_STILI:
        return 0

    def _shx(ad):
        """Bu yazı stili SHX (Türkçe harfsiz) mi?"""
        try:
            st = d.styles.get(ad)
        except Exception:
            return False
        f = (st.dxf.font or "").strip().lower()
        return not f.endswith(".ttf") and not f.endswith(".otf")

    n = 0
    for uzay in [d.modelspace()] + [d.layout(a) for a in d.layout_names()
                                    if a != "Model"]:
        for e in uzay:
            t = e.dxftype()
            if t in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF"):
                if _shx(e.dxf.get("style", "Standard")):
                    e.dxf.style = stil
                    n += 1
            elif t == "DIMENSION":
                # Ölçü yazısının fontu stilden değil, ölçü stilinden
                # (dimtxsty) gelir; ölçü ayrıca çizildiği anda bloğa
                # dönüştüğü için blok içindeki MTEXT de düzeltilir.
                try:
                    if _shx(e.dxf.get("dimtxsty", "Standard")):
                        e.dxf.dimtxsty = stil
                        n += 1
                except Exception:
                    pass
    for blok in d.blocks:
        for e in blok:
            if (e.dxftype() in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF")
                    and _shx(e.dxf.get("style", "Standard"))):
                e.dxf.style = stil
                n += 1
    for ds in d.dimstyles:
        try:
            if _shx(ds.dxf.get("dimtxsty", "Standard")):
                ds.dxf.dimtxsty = stil
                n += 1
        except Exception:
            pass
    return n


def _pafta_cerceve_ciz(pafta, kagit, resim_no="", resim_adi="", bilgi="",
                       sablon=None, antet_degerleri=None):
    """Standart pafta çerçevesini çizer.

        - kâğıdın kenarında ince dış çizgi
        - 15 mm içeride kalın çizim çerçevesi
        - ikisinin arasında bölge şeridi: rakamlar ve harfler
        - kenar ortalarında katlama/ortalama işaretleri
        - SAĞ ÜST köşede resim no ve ismi

    Sağ alt köşedeki antet alanı ÇİZİLMEZ, yalnız boş bırakılır: kendi
    çerçevesi olan bir anteti oraya yapıştırınca iki çizgi üst üste
    binerdi.

    Her biri ayrı katmanda: istemediğinizi tek tıkla silersiniz."""
    d = pafta.doc
    for ad, renk in ((KAT_CERCEVE, 7), (KAT_BOLGE, 7), (KAT_BILGI, 7)):
        if ad not in d.layers:
            d.layers.add(ad, color=renk)
    kg, ky = KAGIT[kagit]
    fx0, fy0, fx1, fy1 = cerceve(kagit)

    def dikdortgen(x0, y0, x1, y1, kat, kalin):
        pafta.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                             close=True,
                             dxfattribs={"layer": kat, "lineweight": kalin})

    def cizgi(x0, y0, x1, y1, kat=KAT_BOLGE, kalin=13):
        pafta.add_line((x0, y0), (x1, y1),
                       dxfattribs={"layer": kat, "lineweight": kalin})

    stil = yazi_stili(pafta.doc)

    def yaz(x, y, m, h=3.5, kat=KAT_BOLGE):
        t = pafta.add_text(m, height=h, dxfattribs={"layer": kat,
                                                    "lineweight": 13,
                                                    "style": stil})
        t.set_placement((x, y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        return t

    if sablon is not None:
        # Firma anteti: çerçeve, bölge işaretleri, antet ve logo hepsi
        # firmanın kendi çiziminden gelir. Pi3D'nin sade çerçevesi
        # çizilmez - ikisi üst üste binerdi.
        sablon.ciz(pafta, (kg, ky), antet_degerleri or {}, stil=stil)
        return

    dikdortgen(DIS_PAY, DIS_PAY, kg - DIS_PAY, ky - DIS_PAY, KAT_CERCEVE, 13)
    dikdortgen(fx0, fy0, fx1, fy1, KAT_CERCEVE, 50)

    # --- bölge şeridi
    sut, sat = BOLGE.get(kagit, (8, 4))
    bs = (fx1 - fx0) / sut
    for i in range(sut):
        x = fx0 + i * bs
        if i:
            cizgi(x, DIS_PAY, x, fy0); cizgi(x, fy1, x, ky - DIS_PAY)
        yaz(x + bs / 2, (DIS_PAY + fy0) / 2, str(i + 1))
        yaz(x + bs / 2, (fy1 + ky - DIS_PAY) / 2, str(i + 1))
    bh = (fy1 - fy0) / sat
    for j in range(sat):
        y = fy1 - (j + 1) * bh                    # harfler yukarıdan aşağıya
        if j:
            cizgi(DIS_PAY, y + bh, fx0, y + bh)
            cizgi(fx1, y + bh, kg - DIS_PAY, y + bh)
        yaz((DIS_PAY + fx0) / 2, y + bh / 2, BOLGE_HARF[j])
        yaz((fx1 + kg - DIS_PAY) / 2, y + bh / 2, BOLGE_HARF[j])

    # --- kenar ortası işaretleri (katlarken hizalamak için)
    for x, y, dx, dy in ((kg / 2, fy0, 0, -1), (kg / 2, fy1, 0, 1),
                         (fx0, ky / 2, -1, 0), (fx1, ky / 2, 1, 0)):
        cizgi(x, y, x + dx * (KENAR - DIS_PAY), y + dy * (KENAR - DIS_PAY),
              KAT_CERCEVE, 50)

    # --- sağ üst köşe: resim no, ismi ve paftanın ölçeği.
    # Ölçek yazılmak ZORUNDA: model uzayı 1:1 olduğu için çizimin kendi
    # başlığında "olcek 1:1" yazar, kâğıtta ise 1:5 olabilir.
    sag = fx1 - 2.0

    def sagust_yaz(metin, h, kalin, ust):
        """Yazıyı sağa dayar ve ÜST kenarı tam `ust` hizasına gelecek
        şekilde koyar; kapladığı yerin ALT kenarını döndürür.

        Hesapla değil ÖLÇEREK: "09_020_000_03" gibi bir resim no'sunda
        alt çizgiler (_) taban çizgisinin ALTINA taşar, "Ğ" ve "Ö" ise
        harf boyunun ÜSTÜNE. Taban çizgisini yazı yüksekliğinden
        çıkararak yer ayırınca alt çizgiler bir alttaki satırın harfleri
        arasına giriyordu ve resim no da çerçeve çizgisine değiyordu."""
        t = pafta.add_text(str(metin), height=h,
                           dxfattribs={"layer": KAT_BILGI,
                                       "lineweight": kalin, "style": stil})
        t.set_placement((sag, ust - h),
                        align=ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT)
        try:
            k = ezdxf.bbox.extents([t], fast=False)
            kayma = ust - k.extmax.y          # ölçülen üst kenarı hizaya al
            if abs(kayma) > 1e-6:
                t.set_placement((sag, ust - h + kayma),
                                align=ezdxf.enums.TextEntityAlignment.BOTTOM_RIGHT)
                k = ezdxf.bbox.extents([t], fast=False)
            return float(k.extmin.y)
        except Exception:
            return ust - h

    # Üstte çerçeve çizgisinin yarı kalınlığı kadar (0,5 mm çizgi) pay
    # yeter; artan yer iki satır ARASINA verilir. Resim no'da alt çizgi
    # (09_020_000_03) çok olur, alttaki satıra yakın durması okumayı
    # zorlaştırıyordu. Toplam yükseklik değişmez: başlık şeridi yine
    # çizimin kendi iç payına yazılır, ölçek düşmez.
    y = fy1 - 0.8
    if resim_no:
        y = sagust_yaz(resim_no, BASLIK_YAZI, 35, y) - 1.6
    alt = "   ".join(x for x in (str(resim_adi or ""), bilgi) if x)
    if alt:
        sagust_yaz(alt, BASLIK_ALT_YAZI, 13, y)


def pafta_kur(kaynak_dxf, cikti_dxf=None, kagit=VARSAYILAN_KAGIT, olcek=None,
              buyutme=False, pafta_adi="PAFTA", bilgi=True, cok=True,
              resim_no=None, resim_adi=None, sablon=None, antet=None):
    """1:1 DXF'in KOPYASINA standart bir pafta ekler.

    kaynak_dxf : 1:1 çizim.
    cikti_dxf  : None ise pafta ÇİZİMİN KENDİ İÇİNE eklenir (önerilen).
                 Bir yol verilirse kopyaya eklenir, kaynak dosyaya
                 dokunulmaz.

                 NEDEN YERİNDE: pafta, model uzayına bir PENCEREDEN
                 bakar. Aynı dosyanın içindeyse, model uzayına sonradan
                 ölçü eklediğinizde ya da bir şey düzelttiğinizde pafta
                 da o anda güncellenir. Kopya tutulursa iki dosya
                 zamanla birbirinden ayrılır ve hangisinin doğru olduğu
                 belli olmaz.

                 MODEL UZAYI YİNE DEĞİŞMEZ: eklenen şey yalnız kâğıt
                 uzayıdır (layout). Program her yazımda model uzayının
                 varlık sayısını önce ve sonra karşılaştırır; bir tanesi
                 bile oynarsa dosya yazılmaz.
    kagit      : "A4".."A0". Yön eki verilmezse ("A3") YATAY ve DİKEY
                 ikisi de denenir, daha büyük ölçek veren seçilir;
                 "A3-D" denirse yalnız dikey kullanılır.
    olcek      : 1.0 / 0.1 gibi. None ise sığan en büyük standart ölçek.
    cok        : görünüşleri ayrı pencerelere alıp kâğıda ortadan dışa
                 eşit aralıklarla dağıt. Resimde görünüş işareti yoksa
                 ya da bölünemiyorsa kendiliğinden tek pencereye düşer.
    resim_no   : sağ üst köşeye (antetli paftada "Drawing No." kutusuna)
                 yazılır; verilmezse dosya adı kullanılır
    resim_adi  : resim no'nun altına (antetli paftada "Part Name")
    sablon     : pf5_antet.Sablon - firma anteti. Verilirse çerçeve,
                 bölge işaretleri ve antet firmanın çiziminden gelir.
    antet      : antet kutularına yazılacak değerler
                 {"malzeme":..., "kutle":..., "cizen":..., "tarih":...}

    Döner: {"olcek":, "olcek_metni":, "kagit":, "yer":, "olcu": (gx,gy),
            "alan": (g,y), "dosya":}
    """
    if kagit not in KAGIT:
        raise PaftaYok(f"Bilinmeyen kâğıt: {kagit}")
    istenen = kagit

    hedef_adi = cikti_dxf or kaynak_dxf
    d = ezdxf.readfile(kaynak_dxf)
    # Dosya nasılsa baştan yazılacak: eski çizimlerdeki SHX fontlu yazılar
    # da bu arada Türkçe gösteren stile taşınır (bkz. turkce_duzelt).
    duzeltilen = turkce_duzelt(d)
    msp = d.modelspace()
    once = len(list(msp))

    x0, y0, x1, y1 = cizim_kutusu(kaynak_dxf)
    gx, gy = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)

    # --- hangi YÖN? Yön eki verilmediyse ikisi de denenir ve daha
    # büyük ölçek veren kazanır. Uzun bir parça dik duruyorsa yatay
    # kâğıtta 1:50'ye düşüp okunmaz oluyordu; aynı parça dikey kâğıtta
    # 1:20 çıkıyor. Eşitlikte yatay kalır: adaylar sırası öyle.
    adaylar = ((kagit_yonleri(istenen) if not dikey_mi(istenen) else (istenen,))
               if sablon is None else (kagit_boyu(istenen),))

    # --- görünüşleri kâğıda eşit dağıtan plan (varsa)
    plan, kagit = None, adaylar[0]
    if cok and olcek is None:
        for kg_ad in adaylar:
            for ad, a in cizim_alanlari(kg_ad, sablon).items():
                p = cok_pencere_plani(d, (x0, y0, x1, y1),
                                      a[2] - a[0], a[3] - a[1])
                if p and (plan is None or p["olcek"] > plan["olcek"]):
                    p["yer"], p["alan"] = ad, a
                    plan, kagit = p, kg_ad

    # --- ölçek ve hangi boşluğa oturacağı
    if olcek is None:
        # Dağıtılmış plan tek pencereden daha büyük ölçek vermiyorsa
        # kullanılmaz: amaç resmi büyütmek.
        tek = yerlesim(gx, gy, istenen, buyutme, sablon)
        if plan and tek and tek["olcek"] > plan["olcek"]:
            plan = None
        if plan:
            olcek = plan["olcek"]
            yer = {"olcek": olcek, "yer": plan["yer"], "alan": plan["alan"]}
        else:
            yer = tek
            if not yer:
                raise PaftaYok(
                    f"{os.path.basename(kaynak_dxf)}: {gx:.0f}x{gy:.0f} mm "
                    f"çizim {kagit_boyu(istenen)} paftaya (yatay ya da "
                    f"dikey) standart bir ölçekle sığmıyor. "
                    "Daha büyük kâğıt seçin.")
            kagit = yer.get("kagit", adaylar[0])
            olcek = yer["olcek"]
    else:
        yer = None
        for kg_ad in adaylar:
            for ad, a in cizim_alanlari(kg_ad, sablon).items():
                if (gx * olcek <= a[2] - a[0] + 1e-6
                        and gy * olcek <= a[3] - a[1] + 1e-6):
                    yer, kagit = {"olcek": olcek, "yer": ad, "alan": a}, kg_ad
                    break
            if yer:
                break
        if not yer:
            # Ölçeği kullanıcı verdiyse de kâğıda sığmayan pafta yazılmaz:
            # taşan çizim, olmayan çizimden beterdir.
            raise PaftaYok(
                f"{os.path.basename(kaynak_dxf)}: {gx:.0f}x{gy:.0f} mm çizim "
                f"{olcek_metni(olcek)} ölçekte "
                f"{gx * olcek:.0f}x{gy * olcek:.0f} mm yer ister; {kagit} "
                f"paftada en büyük boşluk {_en_buyuk_alan_metni(kagit, sablon)}. "
                "Ölçeği küçültün ya da kâğıdı büyütün.")
    alan = yer["alan"]
    ag, ay = alan[2] - alan[0], alan[3] - alan[1]
    # Pencere tam çizim kadar olsun ve MÜMKÜN OLDUĞUNCA KÂĞIDIN
    # ORTASINDA dursun.
    #
    # Önce tam kâğıt ortası denenir; antet kutusuna değmiyorsa iş
    # bitmiştir. Değiyorsa, çizimin sığdığı HER boşluk için kâğıt
    # ortasına en yakın nokta bulunur ve bunların en yakını seçilir -
    # yalnız ölçeği veren boşluğa bakmak yetmez, ölçek aynıysa öbür
    # boşluk daha ortada olabilir. Böylece kısa parçalar kâğıdın bir
    # kenarına sıkışmaz, uzun olanlar da anteti ezmez.
    if plan:
        pg, py = plan["obek"]
    else:
        pg, py = max(gx * olcek, 1e-6), max(gy * olcek, 1e-6)
    pg, py = max(pg, 1e-6), max(py, 1e-6)
    fx0, fy0, fx1, fy1 = cerceve(kagit, sablon)
    ox, oy = (fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0
    kutu = antet_kutusu(kagit, sablon)

    def _uygun(cx, cy):
        """Bu merkezde duran çizim çerçevenin içinde, kenarlardan ve
        antet kutusundan IC_PAY kadar uzakta mı?"""
        r = (cx - pg / 2, cy - py / 2, cx + pg / 2, cy + py / 2)
        return (r[0] >= fx0 + IC_PAY - 1e-6 and r[1] >= fy0 + IC_PAY - 1e-6
                and r[2] <= fx1 - IC_PAY + 1e-6 and r[3] <= fy1 - IC_PAY + 1e-6
                and not (r[0] < kutu[2] + IC_PAY - 1e-6
                         and r[2] > kutu[0] - IC_PAY + 1e-6
                         and r[1] < kutu[3] + IC_PAY - 1e-6
                         and r[3] > kutu[1] - IC_PAY + 1e-6))

    def _kis(v, alt, ust):
        return alt if v < alt else (ust if v > ust else v)

    if _uygun(ox, oy):
        mx, my = ox, oy
    else:
        aday = []
        for a in cizim_alanlari(kagit, sablon).values():
            if pg > a[2] - a[0] + 1e-6 or py > a[3] - a[1] + 1e-6:
                continue
            cx = _kis(ox, a[0] + pg / 2, a[2] - pg / 2)
            cy = _kis(oy, a[1] + py / 2, a[3] - py / 2)
            if _uygun(cx, cy):
                aday.append(((cx - ox) ** 2 + (cy - oy) ** 2, cx, cy))
        if not aday:                     # olmamalı; olduysa pafta yazılmaz
            raise PaftaYok(
                f"{os.path.basename(kaynak_dxf)}: {olcek_metni(olcek)} "
                f"ölçekteki çizim {kagit} paftada antet alanını ezmeden "
                "yerleştirilemedi.")
        _, mx, my = min(aday)

    # --- paftayı kur
    try:
        d.layouts.delete(pafta_adi)
    except Exception:
        pass
    # Aynı resme ikinci kez pafta eklenebilmeli: kullanıcı bir ölçü
    # ekleyip "tekrar paftaya al" diyebilir. Eski pafta sekmesi silinir,
    # yenisi kurulur; MODEL UZAYINA DOKUNULMAZ, çizim 1:1 kalır.
    if pafta_adi in d.layout_names():
        try:
            d.layouts.delete(pafta_adi)
        except Exception:
            pass
    pafta = d.layouts.new(pafta_adi)
    kg, ky = KAGIT[kagit]              # seçilen yönün ölçüleri
    pafta.page_setup(size=(round(kg), round(ky)), margins=(0, 0, 0, 0),
                     units="mm", scale=16)   # 16 = 1 kâğıt birimi : 1 mm

    not_ = ""
    if bilgi:
        not_ = (f"{kagit_adi(kagit)}  ÖLÇEK {olcek_metni(olcek)}"
                + ("  (model 1:1)" if abs(olcek - 1) > 1e-9 else ""))
    no = resim_no if resim_no is not None else os.path.splitext(
        os.path.basename(kaynak_dxf))[0]
    # Sağ üst köşedeki yazılar çerçeveden taşmasın: kalan genişliğe kaç
    # harf sığıyorsa o kadar.
    kg2 = (kg - 2 * KENAR) - 4.0
    no = str(no)[:max(4, int(kg2 / (HARF_ORAN * BASLIK_YAZI)))]
    if resim_adi:
        sig = max(4, int(kg2 / (HARF_ORAN * BASLIK_ALT_YAZI)) - len(not_) - 3)
        resim_adi = str(resim_adi)[:sig]
    deger = None
    if sablon is not None:
        # Antet kutularına ne yazılacak. Ölçek ve dosya adı burada
        # bilinir; malzeme, kütle, çizen ve tarih çağırandan gelir.
        deger = dict(antet or {})
        deger.setdefault("olcek", olcek_metni(olcek))
        deger.setdefault("resim_no", no)
        deger.setdefault("parca_adi", resim_adi or "")
        deger.setdefault("dosya", os.path.basename(hedef_adi))
    _pafta_cerceve_ciz(pafta, kagit, no, resim_adi or "", not_,
                       sablon=sablon, antet_degerleri=deger)

    # --- pencere(ler): 1:1 çizime buradan bakılır
    if plan:
        pencere = _cok_pencere_ciz(pafta, plan, mx - pg / 2.0, my - py / 2.0)
    else:
        pafta.add_viewport(
            center=(mx, my), size=(pg, py),
            view_center_point=((x0 + x1) / 2.0, (y0 + y1) / 2.0),
            view_height=gy)
        pencere = 1

    # --- model uzayı bozulmadı mı? Bu kontrol pazarlık konusu değil.
    sonra = len(list(msp))
    if sonra != once:
        raise PaftaYok(
            f"İÇ HATA: model uzayı değişti ({once} -> {sonra}). "
            "Pafta yazılmadı, 1:1 çizim korundu.")

    d.set_modelspace_vport(height=max(gx, gy) * 1.1,
                           center=((x0 + x1) / 2.0, (y0 + y1) / 2.0))
    try:
        d.layouts.set_active_layout(pafta_adi)
    except Exception:
        pass
    hedef = hedef_adi
    os.makedirs(os.path.dirname(os.path.abspath(hedef)) or ".", exist_ok=True)
    if cikti_dxf:
        d.saveas(cikti_dxf)
    else:
        # Yerine yazarken ÖNCE geçici dosyaya: yazma yarıda kalırsa
        # (disk dolu, program kapandı) resim bozulmasın.
        gec = hedef + ".yeni"
        d.saveas(gec)
        os.replace(gec, hedef)
    yz = en_kucuk_yazi(kaynak_dxf) * olcek
    return {"olcek": olcek, "olcek_metni": olcek_metni(olcek), "kagit": kagit,
            "yer": yer["yer"], "olcu": (gx, gy), "alan": (ag, ay),
            "dosya": hedef, "yerinde": cikti_dxf is None,
            "yazi_duzeltildi": duzeltilen,
            "yazi_mm": round(yz, 2),
            "yazi_kucuk": 0 < yz < EN_AZ_YAZI_MM,
            "pencere": pencere, "dagitildi": bool(plan),
            "obek": (round(pg, 1), round(py, 1))}


def _en_buyuk_alan_metni(kagit, sablon=None):
    a = cizim_alanlari(kagit, sablon)
    return "  /  ".join(f"{(v[2] - v[0]):.0f}x{(v[3] - v[1]):.0f} mm"
                        for v in a.values())


# --------------------------------------------------------------- baskı
def pafta_olcusu(dxf_yolu, pafta_adi="PAFTA"):
    """Paftanın kâğıt ölçüsü (mm)."""
    d = ezdxf.readfile(dxf_yolu)
    lay = d.layout(pafta_adi)
    alt, ust = lay.get_paper_limits()
    g, y = float(ust.x - alt.x), float(ust.y - alt.y)
    if g < 1.0 or y < 1.0:
        g, y = float(lay.dxf.paper_width), float(lay.dxf.paper_height)
    return g, y


def bas(dxf_yolu, cikti, pafta_adi="PAFTA", siyah=True, dpi=300):
    """Paftayı PDF ya da PNG olarak basar.

    Bu işlev KENDİLİĞİNDEN ÇAĞRILMAZ. Kullanıcı "BAS" dediğinde çalışır.
    Kâğıda birebir oturur: A3 pafta, 420x297 mm PDF olur; yazıcıda
    'sayfaya sığdır' demeye gerek kalmaz, %100 basılır."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import (Configuration, ColorPolicy,
                                             BackgroundPolicy)

    d = ezdxf.readfile(dxf_yolu)
    try:
        lay = d.layout(pafta_adi)
    except Exception:
        raise PaftaYok(f"{os.path.basename(dxf_yolu)} içinde "
                       f"'{pafta_adi}' paftası yok.")
    kg, ky = pafta_olcusu(dxf_yolu, pafta_adi)
    if kg < 1 or ky < 1:
        kg, ky = KAGIT[VARSAYILAN_KAGIT]

    fig = plt.figure(figsize=(kg / 25.4, ky / 25.4), dpi=dpi)
    eksen = fig.add_axes([0, 0, 1, 1])
    eksen.set_axis_off()
    ayar = Configuration(
        color_policy=ColorPolicy.BLACK if siyah else ColorPolicy.COLOR,
        background_policy=BackgroundPolicy.WHITE,
        lineweight_scaling=1.0,
    )
    Frontend(RenderContext(d), MatplotlibBackend(eksen), config=ayar
             ).draw_layout(lay, finalize=False)
    eksen.set_xlim(0, kg)
    eksen.set_ylim(0, ky)
    eksen.set_aspect("equal")
    os.makedirs(os.path.dirname(os.path.abspath(cikti)) or ".", exist_ok=True)
    fig.savefig(cikti, dpi=dpi, facecolor="white")
    plt.close(fig)
    return cikti


# --------------------------------------------------------------- toplu
def kagit_plani(dosyalar, tercih=VARSAYILAN_KAGIT, sablon=None):
    """Hangi çizim seçilen kâğıda hangi ölçekte oturur.

    Hiçbir dosya yazmaz, sadece bakar. Kullanıcı "hangisi 1:1 çıkıyor,
    hangisi küçülecek" diye görmek ister."""
    birebir, olcekli, sigmayan, hata = [], [], [], []
    for y in dosyalar:
        try:
            x0, y0, x1, y1 = cizim_kutusu(y)
            gx, gy = x1 - x0, y1 - y0
        except Exception as e:
            hata.append((y, str(e)))
            continue
        # Yön ekli bir tercih gelmediyse iki yön de denenir; seçilen yön
        # kayda yazılır ki kullanıcı listede "A3 dikey" görsün.
        ye = yerlesim(gx, gy, tercih, sablon=sablon)
        kayit = {"dosya": y, "olcu": (gx, gy),
                 "kagit": (ye or {}).get("kagit", tercih),
                 "olcek": ye["olcek"] if ye else None,
                 "yer": ye["yer"] if ye else None}
        if not ye:
            kayit["birebir_kagit"] = kagit_sec(gx, gy, sablon=sablon)
            kayit["secenek"] = [(yerlesim(gx, gy, k, sablon=sablon)["kagit"],
                                 yerlesim(gx, gy, k, sablon=sablon)["olcek"])
                                for k in KAGIT_BOY
                                if yerlesim(gx, gy, k, sablon=sablon)]
            sigmayan.append(kayit)
        elif abs(ye["olcek"] - 1.0) < 1e-9:
            birebir.append(kayit)
        else:
            kayit["birebir_kagit"] = kagit_sec(gx, gy, sablon=sablon)
            kayit["daha_iyi"] = next(
                ((yerlesim(gx, gy, k, sablon=sablon)["kagit"],
                  yerlesim(gx, gy, k, sablon=sablon)["olcek"])
                 for k in KAGIT_BOY
                 if KAGIT[k][0] > KAGIT[kagit_boyu(tercih)][0]
                 and yerlesim(gx, gy, k, sablon=sablon)
                 and yerlesim(gx, gy, k, sablon=sablon)["olcek"] > ye["olcek"]),
                None)
            olcekli.append(kayit)
        try:
            kayit["yazi_mm"] = round(en_kucuk_yazi(y) * (kayit["olcek"] or 1), 2)
        except Exception:
            kayit["yazi_mm"] = 0.0
    return {"birebir": birebir, "olcekli": olcekli, "sigmayan": sigmayan,
            "hata": hata, "kagit": tercih}


def toplu_pafta(isler, cikti_klasor=None, resim_no=None, resim_adi=None,
                sablon=None, antet=None):
    """isler: [{"dosya":..., "kagit":"A3", "olcek": None}, ...]

    cikti_klasor None ise pafta ÇİZİMLERİN KENDİ İÇİNE eklenir; bir
    klasör verilirse kopyalarına eklenir."""
    if cikti_klasor:
        os.makedirs(cikti_klasor, exist_ok=True)
    yapilan, hata = [], []
    for it in isler:
        y = it["dosya"]
        ad = os.path.splitext(os.path.basename(y))[0]
        kagit = it.get("kagit", VARSAYILAN_KAGIT)
        try:
            cik = (os.path.join(cikti_klasor,
                                f"{ad}_{kagit.replace('-', '')}.dxf")
                   if cikti_klasor else None)
            r = pafta_kur(y, cik, kagit, olcek=it.get("olcek"),
                          resim_no=it.get("resim_no", resim_no),
                          resim_adi=it.get("resim_adi", resim_adi),
                          sablon=sablon,
                          antet=dict(antet or {}, **it.get("antet", {})))
            r["kaynak"] = y
            yapilan.append(r)
        except Exception as e:
            hata.append((y, str(e)))
    return {"yapilan": yapilan, "hata": hata}


# ----------------------------------------------------------------- CLI
def _cli():
    import argparse
    import glob as _glob
    a = argparse.ArgumentParser(
        description="Pi3D – 1:1 DXF'lere standart A3 pafta ekler. Pafta "
                    "resmin KENDİ dosyasına yazılır (Model sekmesi 1:1 "
                    "kalır); PDF istenirse PDF klasörüne ..._A3.pdf olarak "
                    "basılır.")
    a.add_argument("dxf", nargs="+", help="1:1 DXF dosyaları (joker olur)")
    a.add_argument("--kagit", default=VARSAYILAN_KAGIT,
                   choices=list(KAGIT_SIRA),
                   help="yön verilmezse (A3) yatay ve dikey denenir, "
                        "daha büyük ölçek veren seçilir; A3-D yalnız dikey")
    a.add_argument("--olcek", type=float, default=None,
                   help="1 / 0.1 gibi; verilmezse sığan en büyüğü")
    a.add_argument("--kopya", metavar="KLASOR", default=None,
                   help="paftayı dosyanın içine değil, bu klasördeki "
                        "kopyaya ekle (önerilmez: kopya ile asıl resim "
                        "zamanla ayrışır)")
    a.add_argument("--pdf-klasor", default="PDF",
                   help="--bas verildiğinde PDF'lerin yazılacağı klasör")
    a.add_argument("--plan", action="store_true",
                   help="hiçbir şey yazma, hangi ölçekte oturduğunu söyle")
    a.add_argument("--bas", action="store_true", help="PDF de üret")
    a.add_argument("--no", help="sağ üst köşeye yazılacak resim no "
                                "(verilmezse dosya adı)")
    a.add_argument("--ad", help="resim no'nun altına yazılacak isim")
    n = a.parse_args()

    dosya = []
    for d in n.dxf:
        dosya += sorted(_glob.glob(d)) if any(c in d for c in "*?[") else [d]
    if not dosya:
        a.error("DXF bulunamadı.")

    p = kagit_plani(dosya, n.kagit)
    for s in p["birebir"]:
        print(f"  {n.kagit}  1:1   {os.path.basename(s['dosya'])}"
              f"   ({s['olcu'][0]:.0f}x{s['olcu'][1]:.0f})")
    for s in p["olcekli"]:
        di = s.get("daha_iyi")
        ek = f"   [{di[0]} olsa {olcek_metni(di[1])}]" if di else ""
        if 0 < s.get("yazi_mm", 0) < EN_AZ_YAZI_MM:
            ek += f"   [DIKKAT yazilar kagitta {s['yazi_mm']:.1f} mm kaliyor]"
        print(f"  {n.kagit}  {olcek_metni(s['olcek'])}   "
              f"{os.path.basename(s['dosya'])}"
              f"   ({s['olcu'][0]:.0f}x{s['olcu'][1]:.0f}){ek}")
    for s in p["sigmayan"]:
        sec = ", ".join(f"{k} {olcek_metni(o)}" for k, o in s["secenek"][:4])
        print(f"  SIĞMADI  {os.path.basename(s['dosya'])}"
              f"   ({s['olcu'][0]:.0f}x{s['olcu'][1]:.0f})  ->  "
              + (sec or "hiçbir kâğıda sığmıyor"))
    for y, e in p["hata"]:
        print(f"  HATA  {os.path.basename(y)}: {e}")
    if n.plan:
        return

    isler = [{"dosya": s["dosya"], "kagit": n.kagit, "olcek": n.olcek}
             for s in p["birebir"] + p["olcekli"]]
    if n.olcek:                       # ölçeği elle veren sığmayanları da dener
        isler += [{"dosya": s["dosya"], "kagit": n.kagit, "olcek": n.olcek}
                  for s in p["sigmayan"]]
    r = toplu_pafta(isler, n.kopya, n.no, n.ad)
    print()
    if n.bas:
        os.makedirs(n.pdf_klasor, exist_ok=True)
    for it in r["yapilan"]:
        nere = "yazıldı " if n.kopya else "içine eklendi"
        print(f"  {nere}  {it['kagit']} {it['olcek_metni']}  "
              f"{os.path.basename(it['dosya'])}")
        if n.bas:
            ad = os.path.splitext(os.path.basename(it["dosya"]))[0]
            ek = str(it["kagit"]).replace("-", "")   # A3 yatay -> A3, dikey -> A3D
            print("           ",
                  bas(it["dosya"],
                      os.path.join(n.pdf_klasor, f"{ad}_{ek}.pdf")))
    for y, e in r["hata"]:
        print(f"  HATA  {os.path.basename(y)}: {e}")


if __name__ == "__main__":
    _cli()
