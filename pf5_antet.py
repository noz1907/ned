# -*- coding: utf-8 -*-
"""Pi3D – firma anteti (yazı alanlı başlık bloğu).

NİÇİN AYRI BİR ŞABLON DOSYASI

Her firmanın anteti başkadır: kutuları, sırası, dili, logosu. Programın
uyduracağı bir şey değildir. Bu yüzden antet KODA GÖMÜLMEZ; firmanın
kendi DXF'i şablon olarak alınır, Pi3D yalnız İÇİNİ DOLDURUR.

Şablon iki dosyadır:

  <ad>.dxf   firmanın anteti; tek bir blok (PI3D_ANTET) hâlinde,
             çerçevesi ve bölge işaretleriyle birlikte
  <ad>.json  hangi kutuya ne yazılacağı: kutu köşeleri, yazının
             başlayacağı nokta ve yüksekliği - hepsi ÖLÇÜLMÜŞ değerler

İkisini de `sablon_hazirla()` üretir: firmadan gelen DXF'i okur, yazı
konturlarını sadeleştirir (dosya 11 MB'tan 0,5 MB'a iner; 0,03 mm
tolerans kâğıtta görünmez), kutuları çizgi ızgarasından çıkarır ve
etiketlerin ("Part Name :") kapladığı yeri ölçüp değerin nereden
başlayacağını hesaplar.

ÖLÇEK

Şablon hangi kâğıt için çizildiyse (burada A2, 594x420) o kâğıdın
ölçüsü JSON'a yazılır. Başka bir kâğıda basılırken şablonun TAMAMI -
çerçeve, bölge işaretleri, antet, logo - tek bir oranla ölçeklenir.
A2'den A3'e oran 420/594 = 0,707; A1'e 1,416; A0'a 2,002. Yani antet
kâğıtla birlikte büyüyüp küçülür, sayfadaki oranı hiç değişmez.

Çizimin kendisi bundan etkilenmez: model uzayı yine 1:1'dir.
"""
from __future__ import annotations

import json
import math
import os

import ezdxf
import ezdxf.bbox

BLOK_AD = "PI3D_ANTET"
KATMAN = "PAFTA_ANTET"
SADE_TOL = 0.03          # yazı konturu sadeleştirme toleransı (mm)
YAZI_PAY = 1.2           # etiketle değer arasındaki boşluk (mm)
EN_AZ_YAZI = 1.5         # değeri bundan küçültmeyiz; sığmazsa kısaltılır


class AntetYok(Exception):
    """Antet şablonu kullanılamadı; mesaj kullanıcıya gösterilir."""


# --------------------------------------------------------- sadeleştirme
def _sadelestir(p, tol):
    """Douglas-Peucker: kontur üzerindeki gereksiz noktaları atar.

    Patlatılmış yazılar aşırı noktalıdır - bu antette 980 konturda
    68 323 nokta vardı. 0,03 mm toleransla 15 bine iner, dosya 1,8
    MB'tan 0,53 MB'a düşer. Tolerans kâğıtta görünmez: A3'e ölçek
    0,707 olduğu için sapma 0,02 mm'de kalır, çizgi kalınlığının
    onda biri."""
    if len(p) < 3:
        return p

    def rec(a, b):
        if b <= a + 1:
            return []
        x0, y0 = p[a]
        x1, y1 = p[b]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        en, ei = -1.0, a
        for i in range(a + 1, b):
            x, y = p[i]
            d = (abs(dy * x - dx * y + x1 * y0 - y1 * x0) / L if L > 1e-12
                 else math.hypot(x - x0, y - y0))
            if d > en:
                en, ei = d, i
        if en <= tol:
            return []
        return rec(a, ei) + [ei] + rec(ei, b)

    idx = [0] + rec(0, len(p) - 1) + [len(p) - 1]
    return [p[i] for i in idx]


# ------------------------------------------------------- çizgi ızgarası
def _izgara(msp, kutu_):
    """Antet bölgesindeki yatay ve düşey çizgileri toplar.

    Her hat için parçaların BİRLEŞİMİ tutulur: bir tablo çizgisi
    dosyada birkaç ayrı LINE olarak durabilir, kutunun kenarı kapalı
    mı diye bakarken bunları tek aralık saymak gerekir."""
    x0, y0, x1, y1 = kutu_
    Y, X = {}, {}

    def ekle(tab, k, a, b, tol=0.7):
        for key in tab:
            if abs(key - k) < tol:
                tab[key].append((a, b))
                return
        tab[k] = [(a, b)]

    for e in msp:
        if e.dxftype() != "LINE":
            continue
        a, b = e.dxf.start, e.dxf.end
        if abs(a.y - b.y) < 0.3 and abs(a.x - b.x) > 3 and y0 - 1 <= a.y <= y1 + 1:
            ekle(Y, a.y, min(a.x, b.x), max(a.x, b.x))
        elif abs(a.x - b.x) < 0.3 and abs(a.y - b.y) > 3 and x0 - 1 <= a.x <= x1 + 1:
            ekle(X, a.x, min(a.y, b.y), max(a.y, b.y))

    def birlestir(segs, pay=0.8):
        segs = sorted(segs)
        out = [list(segs[0])]
        for s, e in segs[1:]:
            if s <= out[-1][1] + pay:
                out[-1][1] = max(out[-1][1], e)
            else:
                out.append([s, e])
        return out

    return ({k: birlestir(v) for k, v in Y.items()},
            {k: birlestir(v) for k, v in X.items()})


def _kapsar(tab, k, a, b, tol=0.7):
    for key in tab:
        if abs(key - k) < tol:
            for s, e in tab[key]:
                if s <= a + 0.8 and e >= b - 0.8:
                    return True
    return False


def hucreler(msp, kutu_, en_az_en=6.0, en_az_boy=3.5):
    """Antetin kapalı kutularını (dört kenarı da çizgili) bulur.

    İç içe olanlardan yalnız EN KÜÇÜĞÜ alınır: "Scale" kutusunu
    çevreleyen büyük dikdörtgen de kapalıdır ama yazı küçük kutuya
    girer."""
    Y, X = _izgara(msp, kutu_)
    ys, xs = sorted(Y), sorted(X)
    ham = []
    for i in range(len(xs)):
        for i2 in range(i + 1, len(xs)):
            for j in range(len(ys)):
                for j2 in range(j + 1, len(ys)):
                    a, b, c, d = xs[i], ys[j], xs[i2], ys[j2]
                    if c - a < en_az_en or d - b < en_az_boy:
                        continue
                    if (_kapsar(Y, b, a, c) and _kapsar(Y, d, a, c)
                            and _kapsar(X, a, b, d) and _kapsar(X, c, b, d)):
                        ham.append((a, b, c, d))
    return [h for h in ham
            if not any(g != h and g[0] >= h[0] - .1 and g[1] >= h[1] - .1
                       and g[2] <= h[2] + .1 and g[3] <= h[3] + .1 for g in ham)]


def _icindeki_yazi(msp, h, pay=0.3):
    """Kutunun içindeki ETİKET geometrisinin sınırı.

    "Scale :" gibi etiketler kutunun içinde durur; değer onun sağına
    yazılmalı. Etiketin nerede bittiğini tahmin etmiyoruz, çiziminden
    ölçüyoruz. Kutunun kenar çizgileri sayılmaz (LINE'lar atlanır)."""
    x0, y0, x1, y1 = h
    kx0 = ky0 = float("inf")
    kx1 = ky1 = float("-inf")
    for e in msp:
        if e.dxftype() in ("LINE", "INSERT"):
            continue
        try:
            k = ezdxf.bbox.extents([e], fast=True)
        except Exception:
            continue
        if (k.extmin.x >= x0 + pay and k.extmax.x <= x1 - pay
                and k.extmin.y >= y0 + pay and k.extmax.y <= y1 - pay):
            kx0 = min(kx0, k.extmin.x); ky0 = min(ky0, k.extmin.y)
            kx1 = max(kx1, k.extmax.x); ky1 = max(ky1, k.extmax.y)
    if kx0 == float("inf"):
        return None
    return (kx0, ky0, kx1, ky1)


# ------------------------------------------------------ şablon hazırlama
def sablon_hazirla(kaynak_dxf, cikti_kok, kagit, cerceve, antet, alanlar,
                   ad=None, tol=SADE_TOL, log=print):
    """Firmanın antet DXF'ini Pi3D şablonuna çevirir.

    kaynak_dxf : firmadan gelen çizim (çerçeve + antet, çoğu zaman
                 yazıları patlatılmış hâlde)
    cikti_kok  : yazılacak dosyaların uzantısız yolu (<kok>.dxf/.json)
    kagit      : şablonun çizildiği kâğıt ölçüsü (g, y) mm
    cerceve    : iç çerçeve (x0, y0, x1, y1) - resimler bunun içine girer
    antet      : antet bloğunun sınırı (x0, y0, x1, y1)
    alanlar    : {"alan_adi": (x, y)} - her alan için O KUTUNUN İÇİNDEN
                 bir nokta. Kutunun kendisi çizgi ızgarasından bulunur.

    Değerin nereye yazılacağı TAHMİN EDİLMEZ, ÖLÇÜLÜR: kutudaki etiket
    geometrisinin ("Part Name :") sınırı bulunur, değer onun sağından
    başlar ve etiketle aynı yükseklikte olur. Kutu boşsa (Drawn/Date
    gibi) değer kutunun ortasına gelir."""
    d = ezdxf.readfile(kaynak_dxf)
    msp = d.modelspace()

    # --- kutular ve alanlar
    hc = hucreler(msp, antet)
    log(f"  antette {len(hc)} kapalı kutu bulundu")
    cikan, yukseklikler = {}, []
    for alan, (px, py) in alanlar.items():
        uy = [h for h in hc if h[0] <= px <= h[2] and h[1] <= py <= h[3]]
        if not uy:
            raise AntetYok(f"{alan!r} için ({px}, {py}) noktasını içeren "
                           "kapalı bir kutu bulunamadı.")
        h = min(uy, key=lambda k: (k[2] - k[0]) * (k[3] - k[1]))
        et = _icindeki_yazi(msp, h)
        if et:
            x = et[2] + YAZI_PAY              # etiketin sağından başla
            y, yuk = et[1], et[3] - et[1]
        else:
            x, yuk = h[0] + YAZI_PAY, None    # boş kutu: ortala
            y = None
        cikan[alan] = {"kutu": [round(v, 2) for v in h],
                       "x": round(x, 2) if x is not None else None,
                       "y": round(y, 2) if y is not None else None,
                       "yuk": round(yuk, 2) if yuk else None,
                       "etiketli": bool(et)}
        if yuk:
            yukseklikler.append(yuk)
    # Bütün alanlarda AYNI yazı boyu kullanılır. Etiketin ölçülen
    # yüksekliği alana göre değişiyor - "Weight :" ve "Drawing No. :"
    # içindeki "g" taban çizgisinin altına sarkıyor, "Scale :" ise
    # sarkmıyor. Her alanı kendi etiketinin boyuyla yazsaydık antette
    # 2,0 ile 3,2 mm arası karışık yazılar çıkardı. Ortanca alınır:
    # aykırı ölçümlerden etkilenmez.
    ortak = (sorted(yukseklikler)[len(yukseklikler) // 2]
             if yukseklikler else 2.5)
    for alan, a in cikan.items():
        a["yuk"] = round(ortak, 2)
        if a["y"] is None:
            h = a["kutu"]
            a["y"] = round((h[1] + h[3]) / 2 - a["yuk"] / 2, 2)
            a["x"] = round((h[0] + h[2]) / 2, 2)
            a["ortala"] = True
        log(f"    {alan:14s} kutu={a['kutu']}  yazı=({a['x']}, {a['y']}) "
            f"h={a['yuk']}" + ("  [ortalı]" if a.get("ortala") else ""))

    # --- geometri: tek blok, sadeleştirilmiş
    t = ezdxf.new("R2010", setup=False)
    if KATMAN not in t.layers:
        t.layers.add(KATMAN, color=7)
    blk = t.blocks.new(BLOK_AD)
    n, nv, atlanan = 0, 0, {}
    for e in msp:
        tip = e.dxftype()
        try:
            if tip == "POLYLINE":
                p = [(round(v.dxf.location.x, 3), round(v.dxf.location.y, 3))
                     for v in e.vertices]
                p = _sadelestir(p, tol)
                if len(p) < 2:
                    continue
                nv += len(p)
                blk.add_lwpolyline(p, close=bool(e.is_closed),
                                   dxfattribs={"layer": KATMAN})
            elif tip in ("LINE", "LWPOLYLINE", "SOLID", "CIRCLE", "ARC",
                         "ELLIPSE", "SPLINE", "HATCH", "POINT", "TEXT", "MTEXT"):
                # Okunabilir etiketler ("Part Name :") de şablona girer;
                # yazı stili hedefte yoksa kurulur (yoksa DXF açılmaz).
                if tip in ("TEXT", "MTEXT"):
                    st = e.dxf.get("style", "Standard") or "Standard"
                    if st not in t.styles:
                        try:
                            t.styles.add(st, font="arial.ttf")
                        except Exception:
                            e.dxf.style = "Standard"
                y = blk.add_foreign_entity(e, copy=True)
                if y is not None:
                    y.dxf.layer = KATMAN
                else:                      # ezdxf sürümüne göre None döner
                    blk[-1].dxf.layer = KATMAN
            else:
                atlanan[tip] = atlanan.get(tip, 0) + 1
                continue
            n += 1
        except Exception:
            atlanan[tip] = atlanan.get(tip, 0) + 1
    log(f"  {n} varlık kopyalandı ({nv} kontur noktası)"
        + (f", atlanan: {atlanan}" if atlanan else ""))

    dxf_yol = cikti_kok + ".dxf"
    t.saveas(dxf_yol)
    bilgi = {
        "ad": ad or os.path.basename(cikti_kok),
        "kaynak": os.path.basename(kaynak_dxf),
        "blok": BLOK_AD,
        "kagit": [round(v, 2) for v in kagit],
        "cerceve": [round(v, 2) for v in cerceve],
        "antet": [round(v, 2) for v in antet],
        "alanlar": cikan,
    }
    with open(cikti_kok + ".json", "w", encoding="utf-8") as f:
        json.dump(bilgi, f, ensure_ascii=False, indent=2)
    log(f"  {os.path.basename(dxf_yol)}  "
        f"{os.path.getsize(dxf_yol) / 1e6:.2f} MB")
    return bilgi


# ------------------------------------------------------------ kullanım
class Sablon:
    """Hazırlanmış bir antet şablonu: geometri + alan haritası."""

    def __init__(self, kok):
        """kok: uzantısız yol; <kok>.dxf ve <kok>.json okunur."""
        self.kok = kok
        j, x = kok + ".json", kok + ".dxf"
        if not (os.path.isfile(j) and os.path.isfile(x)):
            raise AntetYok(f"Antet şablonu eksik: {j} ve {x} gerekli.")
        with open(j, encoding="utf-8") as f:
            self.bilgi = json.load(f)
        self._doc = None

    # Şablon DXF'i bir kez okunur: her resimde yeniden açmak, 150
    # parçalık bir montajda dakikalarca sürerdi.
    @property
    def doc(self):
        if self._doc is None:
            self._doc = ezdxf.readfile(self.kok + ".dxf")
        return self._doc

    @property
    def kagit(self):
        return tuple(self.bilgi["kagit"])

    def olcek(self, kagit_olcusu):
        """Şablonu hedef kâğıda oturtan oran.

        Şablon A2 (594x420) için çizildiyse A3'te 420/594 = 0,707,
        A1'de 1,416, A0'da 2,002 olur - yani ISO'nun kendi kâğıt
        basamağı. En küçük oran alınır ki hiçbir yönde taşmasın."""
        sg, sy = self.kagit
        hg, hy = kagit_olcusu
        return min(hg / sg, hy / sy)

    def cerceve(self, kagit_olcusu):
        """Hedef kâğıtta iç çerçevenin köşeleri (mm)."""
        o = self.olcek(kagit_olcusu)
        return tuple(v * o for v in self.bilgi["cerceve"])

    def antet_kutusu(self, kagit_olcusu):
        o = self.olcek(kagit_olcusu)
        return tuple(v * o for v in self.bilgi["antet"])

    def ciz(self, pafta, kagit_olcusu, degerler=None, stil="Standard"):
        """Anteti kâğıda çizer ve alanları doldurur.

        Geometri tek bir blok referansıyla girer: blok tanımı dosyada
        BİR kez durur, ölçek INSERT'ün üstündedir. Böylece antet
        büyüyüp küçülürken dosya büyümez."""
        d = pafta.doc
        o = self.olcek(kagit_olcusu)
        blok = self.bilgi["blok"]
        if blok not in d.blocks:
            kaynak = self.doc.blocks.get(blok)
            if kaynak is None:
                raise AntetYok(f"Şablonda {blok!r} bloğu yok.")
            if KATMAN not in d.layers:
                d.layers.add(KATMAN, color=7)
            yeni = d.blocks.new(blok)
            for e in kaynak:
                try:
                    yeni.add_foreign_entity(e, copy=True)
                except Exception:
                    pass
        pafta.add_blockref(blok, (0, 0),
                           dxfattribs={"xscale": o, "yscale": o,
                                       "layer": KATMAN})
        for alan, deger in (degerler or {}).items():
            a = self.bilgi["alanlar"].get(alan)
            if not a or deger in (None, ""):
                continue
            self._yaz(pafta, a, str(deger), o, stil)

    def _yaz(self, pafta, a, metin, o, stil):
        """Bir alanı doldurur; sığmıyorsa önce küçültür, sonra kısaltır.

        Kutunun genişliği bellidir; yazının genişliği DXF'te saklanmaz,
        fonta göre değişir. Bu yüzden yazılıp ÖLÇÜLÜR: taşıyorsa
        yükseklik düşürülür, EN_AZ_YAZI'ya inince de metin kısaltılır.
        Taşan bir yazı komşu kutuyu okunmaz yapar."""
        kutu_ = a["kutu"]
        h = a["yuk"] * o
        x, y = a["x"] * o, a["y"] * o
        sag = (kutu_[2] - YAZI_PAY) * o
        genislik = max(sag - x, 1.0)
        if a.get("ortala"):
            genislik = max((kutu_[2] - kutu_[0] - 2 * YAZI_PAY) * o, 1.0)

        def koy(m, yuk):
            t = pafta.add_text(m, height=yuk,
                               dxfattribs={"layer": KATMAN, "style": stil})
            if a.get("ortala"):
                t.set_placement((x, y),
                                align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
            else:
                t.set_placement((x, y))
            return t

        t = koy(metin, h)
        for _ in range(8):
            try:
                k = ezdxf.bbox.extents([t], fast=False)
            except Exception:
                return t
            en = k.extmax.x - k.extmin.x
            if en <= genislik:
                return t
            if h > EN_AZ_YAZI * o:
                h = max(h * 0.85, EN_AZ_YAZI * o)
            elif len(metin) > 4:
                # Harf harf kısaltmak yakınsamıyordu: 120 harflik bir
                # malzeme adı 6 turda ancak 12 harf kaybediyor, kalanı
                # komşu kutuya taşıyordu. ÖLÇÜLEN genişlikten orantıyla
                # kaç harfin sığdığı bir adımda bulunur.
                n = max(3, min(len(metin) - 1,
                               int(len(metin) * genislik / en) - 1))
                metin = metin[:n] + "…"
            else:
                return t
            pafta.delete_entity(t)
            t = koy(metin, h)
        return t


def sablon_bul(*klasorler):
    """İlk bulunan antet şablonunu döndürür; yoksa None.

    Antet ZORUNLU DEĞİLDİR: şablon yoksa Pi3D kendi sade paftasını
    çizer (sağ alt köşe boş kalır). Böylece programı antetsiz de
    kullanabilirsiniz."""
    for k in klasorler:
        if not k or not os.path.isdir(k):
            continue
        for a in sorted(os.listdir(k)):
            if a.endswith(".json"):
                kok = os.path.join(k, a[:-5])
                if os.path.isfile(kok + ".dxf"):
                    try:
                        return Sablon(kok)
                    except Exception:
                        continue
    return None


# ----------------------------------------------------------------- CLI
ALAN_ACIKLAMA = {
    "olcek": "paftanın ölçeği (Scale)",
    "kutle": "parçanın kütlesi (Weight)",
    "malzeme": "malzeme (Material)",
    "parca_adi": "parçanın adı (Part Name)",
    "resim_no": "çizim numarası (Drawing No)",
    "cizen": "çizen kişi (Drawn / Name)",
    "cizen_tarih": "çizim tarihi (Drawn / Date)",
    "onaylayan": "onaylayan kişi (Checked / Name)",
    "onay_tarih": "onay tarihi (Checked / Date)",
    "dosya": "dosya adı (FILE)",
}


def _cli():
    import argparse
    a = argparse.ArgumentParser(
        description="Pi3D – firmanın antet DXF'ini şablona çevirir.",
        epilog="Önce --incele ile kutuların koordinatlarını görün, sonra "
               "tanım dosyasını doldurup --kur deyin.")
    a.add_argument("dxf", help="firmanın çerçeve + antet çizimi")
    a.add_argument("--incele", action="store_true",
                   help="antetteki kapalı kutuları listele, hiçbir şey yazma")
    a.add_argument("--antet", help="antetin sınırı: x0,y0,x1,y1 (mm)")
    a.add_argument("--tanim", help="alan haritası (JSON); --kur için gerekli")
    a.add_argument("--cikti", help="şablonun yazılacağı yer, uzantısız "
                                   "(ör. antet/firma)")
    a.add_argument("--tol", type=float, default=SADE_TOL,
                   help=f"kontur sadeleştirme toleransı mm (varsayılan {SADE_TOL})")
    n = a.parse_args()

    if n.incele:
        if not n.antet:
            a.error("--incele için --antet x0,y0,x1,y1 gerekli. "
                    "Antetin sınırını CAD'de ölçün.")
        kutu_ = tuple(float(v) for v in n.antet.replace(";", ",").split(","))
        d = ezdxf.readfile(n.dxf)
        hc = hucreler(d.modelspace(), kutu_)
        hc.sort(key=lambda h: (-h[3], h[0]))
        print(f"{len(hc)} kapalı kutu:")
        for i, h in enumerate(hc):
            print(f"  #{i:3d}  x[{h[0]:8.2f},{h[2]:8.2f}]  "
                  f"y[{h[1]:7.2f},{h[3]:7.2f}]   "
                  f"orta=({(h[0]+h[2])/2:.1f},{(h[1]+h[3])/2:.1f})   "
                  f"{h[2]-h[0]:6.1f} x {h[3]-h[1]:5.1f} mm")
        print("\nTanım dosyasına her alan için KUTUNUN ORTASINI yazın.")
        print("Alanlar: " + ", ".join(f"{k} ({v})"
                                      for k, v in ALAN_ACIKLAMA.items()))
        return

    if not (n.tanim and n.cikti):
        a.error("şablon kurmak için --tanim ve --cikti gerekli "
                "(önce --incele ile kutulara bakın).")
    with open(n.tanim, encoding="utf-8") as f:
        t = json.load(f)
    bilinmeyen = set(t.get("alanlar", {})) - set(ALAN_ACIKLAMA)
    if bilinmeyen:
        print(f"! bilinmeyen alan(lar): {sorted(bilinmeyen)} - program "
              "bunları doldurmaz, yine de şablona yazılır.")
    os.makedirs(os.path.dirname(os.path.abspath(n.cikti)) or ".",
                exist_ok=True)
    sablon_hazirla(n.dxf, n.cikti,
                   kagit=tuple(t["kagit"]), cerceve=tuple(t["cerceve"]),
                   antet=tuple(t["antet"]),
                   alanlar={k: tuple(v) for k, v in t["alanlar"].items()},
                   ad=t.get("ad"), tol=n.tol)
    print(f"tamam: {n.cikti}.dxf ve {n.cikti}.json")


if __name__ == "__main__":
    _cli()


# ================================================================ otomatik tanım
# Kullanıcı: "Lisans alınması durumunda antet DXF A3 olarak istensin, o DXF
# analiz edilecek ve ayar olarak kaydedilecek; bu ayar zaman içinde
# değiştirilebilir olmalı." Burada firmanın antet DXF'i ÖLÇÜLEREK
# çözülür: kâğıt, çerçeve, antet bloğu, kapalı kutular ve kutulardaki
# etiketler. Etiket okunabiliyorsa (TEXT / MTEXT) alan adı anahtar
# kelimeden önerilir; patlatılmış (kontur) yazıda öneri yapılamaz,
# kullanıcı kutuyu seçer. Hiçbir şey tahmin edilip sessizce yazılmaz:
# eşleme tablosu kullanıcıya gösterilir, o onaylar.
ISO_KAGIT = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A2": (594.0, 420.0),
             "A1": (841.0, 594.0), "A0": (1189.0, 841.0)}
ANAHTAR_KELIME = [
    ("resim_no", ("drawing no", "drawing number", "dwg no", "dwg. no", "resim no",
                  "cizim no", "zeichnungsnr", "zeichnungs nr", "zeichnungsnummer",
                  "drawing nr", "no de plan")),
    ("parca_adi", ("part name", "parca adi", "parca ismi", "benennung",
                   "bezeichnung", "tanim", "description", "designation",
                   "title", "part")),
    ("malzeme", ("material", "malzeme", "werkstoff", "matiere", "matériau")),
    ("kutle", ("weight", "kutle", "agirlik", "gewicht", "mass", "masse", "poids")),
    ("olcek", ("scale", "olcek", "massstab", "masstab", "echelle", "maßstab")),
    ("dosya", ("file", "dosya", "datei", "fichier")),
    ("cizen", ("drawn", "cizen", "gezeichnet", "dessine", "dessiné", "drawn by")),
    ("onaylayan", ("checked", "approved", "onay", "kontrol", "gepruft", "geprüft",
                   "verifie", "vérifié", "appr")),
]
TARIH_KELIME = ("date", "tarih", "datum")
AD_KELIME = ("name", "ad", "isim", "adi")

_TR_ASCII = str.maketrans("ıİşŞğĞüÜöÖçÇâÂîÎûÛ", "iissgguuooccaaiiuu")


def _sade(t):
    return (t or "").translate(_TR_ASCII).lower().strip()


def kagit_tahmini(w, h):
    """Ölçülen sınır hangi ISO kâğıdı (yüzde 3 payla); değilse ölçünün kendisi."""
    for ad, (g, y) in ISO_KAGIT.items():
        for a, b in ((g, y), (y, g)):
            if abs(w - a) <= 0.03 * a and abs(h - b) <= 0.03 * b:
                return ad, (a, b)
    return None, (round(w, 2), round(h, 2))


def _uzun_hatlar(msp, sinir, oran=0.6):
    """Sınırın yüzde `oran`ından uzun yatay / düşey hatlar (çerçeve adayı)."""
    x0, y0, x1, y1 = sinir
    Y, X = _izgara(msp, sinir)
    W, H = x1 - x0, y1 - y0
    ys = sorted(k for k, segs in Y.items() if max(e - s for s, e in segs) >= oran * W)
    xs = sorted(k for k, segs in X.items() if max(e - s for s, e in segs) >= oran * H)
    return ys, xs


def _cerceve_bul(msp, sinir):
    """Dış sınır ve iç çerçeve: en dıştaki uzun hat çifti kâğıt kenarı ya
    da dış çizgi, bir içerideki (5-30 mm) çift iç çerçevedir. Tek çift
    varsa o çerçevedir."""
    ys, xs = _uzun_hatlar(msp, sinir)
    if len(ys) < 2 or len(xs) < 2:
        raise AntetYok("Çerçeve bulunamadı: antet DXF'inde kâğıdı çevreleyen "
                       "yatay ve düşey uzun çizgiler yok.")
    dis = (xs[0], ys[0], xs[-1], ys[-1])

    def ic(liste, dis_a, dis_b):
        a = next((v for v in liste if 4.0 <= v - dis_a <= 35.0), dis_a)
        b = next((v for v in reversed(liste) if 4.0 <= dis_b - v <= 35.0), dis_b)
        return a, b
    cx0, cx1 = ic(xs, dis[0], dis[2])
    cy0, cy1 = ic(ys, dis[1], dis[3])
    return dis, (cx0, cy0, cx1, cy1)


def _antet_bul(msp, cerceve):
    """Antet bloğu: çerçevenin alt yarısındaki KISA çizgilerin (çerçeveden
    kısa) sınırı; çizgiler çerçeve hatlarına oturtulur."""
    x0, y0, x1, y1 = cerceve
    W, H = x1 - x0, y1 - y0
    kx0 = ky0 = float("inf"); kx1 = ky1 = float("-inf")
    say = 0
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        a, b = e.dxf.start, e.dxf.end
        yatay = abs(a.y - b.y) < 0.3 and 2.0 < abs(a.x - b.x) < 0.9 * W
        dusey = abs(a.x - b.x) < 0.3 and 2.0 < abs(a.y - b.y) < 0.6 * H
        if not (yatay or dusey):
            continue
        # çerçevenin içinde ve alt yarısında
        ya, yb = min(a.y, b.y), max(a.y, b.y)
        xa, xb = min(a.x, b.x), max(a.x, b.x)
        if xa < x0 - 0.5 or xb > x1 + 0.5 or ya < y0 - 0.5 or yb > y0 + 0.5 * H:
            continue
        kx0, kx1 = min(kx0, xa), max(kx1, xb)
        ky0, ky1 = min(ky0, ya), max(ky1, yb)
        say += 1
    if say < 4:
        raise AntetYok("Antet bloğu bulunamadı: çerçevenin alt yarısında kutu "
                       "çizgileri yok. Antet sağ alt köşede, çizgilerle çizilmiş "
                       "olmalı (blok ise CAD'de patlatın).")
    # kenarları çerçeveye yapıştır (antet çoğu zaman çerçeveye dayanır)
    if abs(kx1 - x1) < 2.0: kx1 = x1
    if abs(ky0 - y0) < 2.0: ky0 = y0
    if abs(kx0 - x0) < 2.0: kx0 = x0
    return (kx0, ky0, kx1, ky1)


def _hucre_etiketleri(msp, hc):
    """Her kutunun içindeki okunabilir yazı (TEXT / MTEXT / ATTDEF)."""
    out = [""] * len(hc)
    for e in msp:
        t = e.dxftype()
        if t == "TEXT":
            m, p = e.dxf.text, e.dxf.insert
        elif t == "MTEXT":
            m, p = e.plain_text(), e.dxf.insert
        elif t == "ATTDEF":
            m, p = (e.dxf.prompt or e.dxf.tag or ""), e.dxf.insert
        else:
            continue
        m = (m or "").strip()
        if not m:
            continue
        try:
            k = ezdxf.bbox.extents([e], fast=True)
            cx, cy = (k.extmin.x + k.extmax.x) / 2, (k.extmin.y + k.extmax.y) / 2
        except Exception:
            cx, cy = p.x, p.y
        for i, h in enumerate(hc):
            if h[0] <= cx <= h[2] and h[1] <= cy <= h[3]:
                out[i] = (out[i] + " " + m).strip()
                break
    return out


def alan_oner(hc, etiketler):
    """Etiketlerden alan önerisi: {alan: kutu indeksi}. Tarih / ad sütunları
    Drawn / Checked satırlarına göre çözülür. Emin olunmayan hiçbir şey
    atanmaz; kullanıcı tabloda tamamlar."""
    sade = [_sade(e) for e in etiketler]
    es = {}
    for i, m in enumerate(sade):
        if not m:
            continue
        for alan, kelimeler in ANAHTAR_KELIME:
            if alan in es:
                continue
            if any(k in m for k in kelimeler):
                # "drawing" ile "drawn" karışmasın: tam kelime araması
                es[alan] = i
                break

    def ayni_satir(a, b):
        ya, yb = (a[1] + a[3]) / 2, (b[1] + b[3]) / 2
        return abs(ya - yb) < 0.6 * min(a[3] - a[1], b[3] - b[1])

    def ustunde(ust, alt_):
        # ust kutusu alt_'ın tam üstünde mi (x çakışık, y daha büyük)
        return (ust[1] >= alt_[3] - 0.5 and min(ust[2], alt_[2]) - max(ust[0], alt_[0]) > 2.0
                and ust[1] - alt_[3] < 3 * (alt_[3] - alt_[1]))
    tarih_h = [i for i, m in enumerate(sade) if any(k == m or k in m.split() for k in TARIH_KELIME)]
    ad_h = [i for i, m in enumerate(sade) if m in AD_KELIME or m.split()[:1] == ["name"]]
    for alan, tarih_alan in (("cizen", "cizen_tarih"), ("onaylayan", "onay_tarih")):
        i = es.get(alan)
        if i is None:
            continue
        satir = [j for j in range(len(hc)) if j != i and ayni_satir(hc[j], hc[i])
                 and hc[j][0] >= hc[i][2] - 0.5]
        satir.sort(key=lambda j: hc[j][0])
        bos = [j for j in satir if not sade[j]]
        # aynı satırda "Date" etiketli kutu: değer onun sağına (etiketli kutu)
        t_ayni = [j for j in satir if j in tarih_h]
        if t_ayni:
            es[tarih_alan] = t_ayni[0]
            bos = [j for j in bos if j != t_ayni[0]]
        if bos:
            # başlık sütunlarına göre: üstündeki "Date" / "Name"
            tarih_j = next((j for j in bos if any(ustunde(hc[t], hc[j]) for t in tarih_h)), None)
            ad_j = next((j for j in bos if any(ustunde(hc[t], hc[j]) for t in ad_h)), None)
            if tarih_alan not in es and tarih_j is not None:
                es[tarih_alan] = tarih_j
            if ad_j is not None:
                es[alan] = ad_j
            elif tarih_j is None and tarih_alan not in es and len(bos) >= 2:
                es[tarih_alan], es[alan] = bos[0], bos[1]
            elif tarih_j is None and tarih_alan not in es and len(bos) == 1:
                es[alan] = bos[0]
            elif ad_j is None and len([j for j in bos if j != es.get(tarih_alan)]) >= 1:
                es[alan] = [j for j in bos if j != es.get(tarih_alan)][0]
        # değilse: değer etiketin sağına, aynı kutuya (es[alan] = i kalır)
    return es


def otomatik_tanim(kaynak_dxf, log=print):
    """Firmanın antet DXF'ini ölçerek çözer. Döner:
      {"kagit_ad", "kagit", "dis", "cerceve", "antet", "hucreler",
       "etiketler", "oneri": {alan: kutu indeksi}, "notlar": [...]}"""
    d = ezdxf.readfile(kaynak_dxf)
    msp = d.modelspace()
    try:
        ext = ezdxf.bbox.extents(msp, fast=True)
    except Exception as ex:
        raise AntetYok(f"DXF okunamadı: {ex}")
    if ext is None or not ext.has_data:
        raise AntetYok("DXF boş.")
    sinir = (ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y)
    dis, cerceve = _cerceve_bul(msp, sinir)
    kad, kagit = kagit_tahmini(dis[2] - dis[0], dis[3] - dis[1])
    notlar = []
    if kad is None:
        # dış çizgi kâğıt değilse çizimin sınırına bak
        kad2, kagit2 = kagit_tahmini(sinir[2] - sinir[0], sinir[3] - sinir[1])
        if kad2:
            kad, kagit = kad2, kagit2
        else:
            notlar.append(f"kâğıt ISO ölçüsü değil: {kagit[0]} x {kagit[1]} mm ölçüldü")
    antet = _antet_bul(msp, cerceve)
    hc = hucreler(msp, antet)
    hc.sort(key=lambda h: (-h[3], h[0]))
    if not hc:
        raise AntetYok("Antette kapalı kutu bulunamadı (dört kenarı çizgili kutu yok).")
    etiket = _hucre_etiketleri(msp, hc)
    oneri = alan_oner(hc, etiket)
    if not any(etiket):
        notlar.append("kutularda okunabilir yazı yok (yazılar patlatılmış): "
                      "alanları tablodan elle seçin")
    log(f"  kâğıt {kad or '?'} {kagit[0]} x {kagit[1]}, çerçeve {tuple(round(v, 1) for v in cerceve)}, "
        f"antet {tuple(round(v, 1) for v in antet)}, {len(hc)} kutu, "
        f"{sum(1 for e in etiket if e)} etiket, {len(oneri)} alan önerisi")
    # çizim sınırı kâğıttan taşıyorsa (dış kenar yoksa) kâğıdı dış çizgi say
    return {"kaynak": kaynak_dxf, "kagit_ad": kad, "kagit": kagit, "dis": dis,
            "cerceve": cerceve, "antet": antet, "hucreler": hc,
            "etiketler": etiket, "oneri": oneri, "notlar": notlar}


def tanim_onizleme_png(tanim, png, secim=None, dpi=110):
    """Antet bölgesinin resmi: kutular numaralı, atanmış alanlar yeşil."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    from ezdxf.addons.drawing.config import Configuration, ColorPolicy, BackgroundPolicy
    d = ezdxf.readfile(tanim["kaynak"])
    msp = d.modelspace()
    x0, y0, x1, y1 = tanim["antet"]
    pay = 3.0
    w, h = (x1 - x0 + 2 * pay), (y1 - y0 + 2 * pay)
    fig = plt.figure(figsize=(min(16, 0.055 * w + 2), min(9, 0.055 * h + 1.5)), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    Frontend(RenderContext(d), MatplotlibBackend(ax),
             config=Configuration(background_policy=BackgroundPolicy.WHITE,
                                  color_policy=ColorPolicy.BLACK, min_lineweight=0.2)
             ).draw_layout(msp, finalize=False)
    secim = secim or {}
    ters = {}
    for alan, i in secim.items():
        ters.setdefault(i, []).append(alan)
    for i, hcell in enumerate(tanim["hucreler"]):
        a, b, c, e = hcell
        renk = "#1a7f37" if i in ters else "#1d6fd1"
        ax.add_patch(Rectangle((a, b), c - a, e - b, fill=bool(i in ters),
                               alpha=0.18 if i in ters else 1.0, color=renk, lw=0.8))
        ax.text(a + 0.6, e - 0.6, f"{i}" + (" " + ",".join(ters[i]) if i in ters else ""),
                fontsize=6, color=renk, va="top", ha="left", weight="bold")
    ax.set_xlim(x0 - pay, x1 + pay); ax.set_ylim(y0 - pay, y1 + pay); ax.set_aspect("equal")
    fig.savefig(png, facecolor="white"); plt.close(fig)
    return png


# ------------------------------------------------------------ ayar / lisans
def sablon_klasoru():
    """Firma anteti şablonunun KALICI yeri (kullanıcı verisi: LOCALAPPDATA\\Pi3D\\antet).
    Exe yeniden derlenmez; şablon buradan okunur, buradan değiştirilir."""
    try:
        import pf17_lisans as L
        kok = L._veri_klasoru()
    except Exception:
        kok = os.path.join(os.path.expanduser("~"), ".config", "Pi3D")
    d = os.path.join(kok, "antet")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def sablon_kur(tanim, secim, ad=None, log=print, klasor=None):
    """Onaylanmış eşlemeyle şablonu üretir, kalıcı klasöre yazar ve ayara
    kaydeder. secim: {alan: kutu indeksi}. Döner: Sablon."""
    alanlar = {}
    for alan, i in (secim or {}).items():
        if alan not in ALAN_ACIKLAMA or i is None or not (0 <= i < len(tanim["hucreler"])):
            continue
        h = tanim["hucreler"][i]
        alanlar[alan] = ((h[0] + h[2]) / 2.0, (h[1] + h[3]) / 2.0)
    if not alanlar:
        raise AntetYok("Hiç alan seçilmedi: en azından parça adı ve resim no kutusunu seçin.")
    kl = klasor or sablon_klasoru()
    os.makedirs(kl, exist_ok=True)
    kok = os.path.join(kl, "firma")
    ad = ad or (f"Firma anteti ({tanim.get('kagit_ad') or 'özel kâğıt'})")
    sablon_hazirla(tanim["kaynak"], kok, kagit=tuple(tanim["kagit"]),
                   cerceve=tuple(tanim["cerceve"]), antet=tuple(tanim["antet"]),
                   alanlar=alanlar, ad=ad, log=log)
    import time
    try:
        import pf3_olcu
        pf3_olcu.ayar_yaz(antet_sablon=kok, antet_ad=ad,
                          antet_kaynak=os.path.basename(tanim["kaynak"]),
                          antet_tarih=time.strftime("%d.%m.%Y %H:%M"))
    except Exception as ex:
        log(f"! antet ayarı yazılamadı: {ex}")
    return Sablon(kok)


def sablon_kaldir():
    """Ayardaki firma antetini kapatır (dosyalar durur; yeniden seçilebilir)."""
    try:
        import pf3_olcu
        pf3_olcu.ayar_yaz(antet_sablon="", antet_ad="", antet_kaynak="", antet_tarih="")
        return True
    except Exception:
        return False


def ayarli_sablon():
    """Ayara kaydedilmiş firma anteti; yoksa None."""
    try:
        import pf3_olcu
        kok = pf3_olcu.ayar_oku().get("antet_sablon") or ""
    except Exception:
        return None
    if not kok:
        return None
    try:
        return Sablon(kok)
    except Exception:
        return None


def ayarli_sablon_bilgi():
    try:
        import pf3_olcu
        a = pf3_olcu.ayar_oku()
    except Exception:
        return {}
    return {k: a.get(k, "") for k in ("antet_sablon", "antet_ad", "antet_kaynak", "antet_tarih")}


_LISANS = {}


def lisans_durumu(yenile=False):
    """Lisans (pf17) bir kez okunur; pafta / kaynak resmi her sayfada sormasın."""
    if yenile or "d" not in _LISANS:
        try:
            import pf17_lisans as L
            _LISANS["d"] = L.yukle()
        except Exception:
            _LISANS["d"] = {"gecerli": False, "paket": ""}
    return _LISANS["d"]


def firma_anteti_izinli(durum=None):
    """Firma anteti yalnız GEÇERLİ ve DENEME olmayan lisansta. Deneme
    sürümünde her çıktı Pi3D / PiVision antetlidir (kullanıcı kararı)."""
    d = durum if durum is not None else lisans_durumu()
    try:
        return bool(d.get("gecerli")) and str(d.get("paket") or "").upper() != "DENEME"
    except Exception:
        return False


def deneme_mi(durum=None):
    return not firma_anteti_izinli(durum)
