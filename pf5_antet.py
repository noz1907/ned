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
                         "ELLIPSE", "SPLINE", "HATCH", "POINT"):
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
