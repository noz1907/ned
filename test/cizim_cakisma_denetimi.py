# -*- coding: utf-8 -*-
"""Resimde yazı çakışması var mı?

İki soruyu sorar:
  1. İki yazı üst üste biniyor mu? (ölçü rakamı + delik yazısı vb.)
  2. Bir yazı parçanın konturunun üstüne binmiş mi?

Doğrusu ikisinde de SIFIR. Yazının kâğıtta kapladığı yer ölçü stiline
ve yazı tipine bağlıdır; hesapla bulunmaz, ÖLÇÜLÜR. Bu betik de öyle
yapar: DXF'i açar, her yazının gerçek sınırını çıkarır, karşılaştırır.

Ölçü blokları adsız BLOK içindedir; içlerindeki yazılar da açılıp
sayılır, yoksa asıl çakışmalar gözden kaçar.

    python test/cizim_cakisma_denetimi.py cikti/*.dxf
    python test/cizim_cakisma_denetimi.py cikti          (klasör de olur)
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                  # noqa: E402
import ezdxf.bbox                                             # noqa: E402

KONTUR = ("LWPOLYLINE", "LINE", "CIRCLE", "ARC")


def parcalar(e, sapma=0.2):
    """Bir konturu düz parçalara böler: [((x0,y0),(x1,y1)), ...].

    SINIR KUTUSU YETMEZ. Uzun ve ince bir çokgenin kutusu bütün
    görünüşü kaplar; o kutunun içinde duran her yazı "konturun üstünde"
    sayılır - ki doğru değildir, aradaki boşlukta durabilir. Gerçek
    soru, yazının GERÇEK BİR ÇİZGİYE değip değmediğidir."""
    try:
        t = e.dxftype()
        if t == "LINE":
            p = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif t == "LWPOLYLINE":
            p = [(x, y) for x, y in e.get_points("xy")]
            if e.closed and len(p) > 2:
                p.append(p[0])
        else:                                   # CIRCLE / ARC
            p = [(q.x, q.y) for q in e.flattening(sapma)]
    except Exception:
        return []
    return list(zip(p, p[1:]))


def _parca_kutuda(a, b, k):
    """(a,b) doğru parçası k dikdörtgenine değiyor mu? (Liang-Barsky)"""
    x0, y0 = a
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - k[0]), (dx, k[2] - x0),
                 (-dy, y0 - k[1]), (dy, k[3] - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return False
                t0 = max(t0, r)
            else:
                if r < t0:
                    return False
                t1 = min(t1, r)
    return t0 <= t1


def yazilar(msp):
    """Resimdeki bütün yazılar: serbest yazılar + ölçülerin içindekiler."""
    cik = []
    for e in msp:
        t = e.dxftype()
        if t in ("TEXT", "MTEXT"):
            cik.append((e, e.text if t == "MTEXT" else e.dxf.text))
        elif t == "DIMENSION":
            try:
                for v in e.virtual_entities():
                    if v.dxftype() in ("TEXT", "MTEXT"):
                        cik.append(
                            (v, v.text if v.dxftype() == "MTEXT" else v.dxf.text))
            except Exception:
                pass
    return cik


def kutu(e):
    try:
        k = ezdxf.bbox.extents([e], fast=False)
    except Exception:
        return None
    return None if not k.has_data else (k.extmin.x, k.extmin.y,
                                        k.extmax.x, k.extmax.y)


def kesisir(a, b, pay=0.0):
    return (a[0] < b[2] - pay and a[2] > b[0] + pay
            and a[1] < b[3] - pay and a[3] > b[1] + pay)


def denetle(yol):
    d = ezdxf.readfile(yol)
    msp = d.modelspace()
    yz = [(k, m) for k, m in ((kutu(e), m) for e, m in yazilar(msp)) if k]
    ikili = []
    for i in range(len(yz)):
        for j in range(i + 1, len(yz)):
            if kesisir(yz[i][0], yz[j][0]):
                ikili.append((yz[i][1][:22], yz[j][1][:22]))
    kont = [p for e in msp
            if e.dxf.layer == "GORUNEN" and e.dxftype() in KONTUR
            for p in parcalar(e)]
    ustunde = [m for k, m in yz
               if any(_parca_kutuda(a, b, k) for a, b in kont)]
    return ikili, ustunde, len(yz)


def kendini_dene():
    """Denetimin kendisi doğru mu?

    Bu denetim bir kere YANILDI: konturu sınır kutusuyla karşılaştırıyordu
    ve uzun ince bir çokgenin kutusu bütün görünüşü kapladığı için
    içindeki her yazıyı "konturun üstünde" sayıyordu. Gerçek montajda
    bildirdiği 3 çakışmanın 2'si bu yüzden uydurmaydı. Yanılan bir
    denetim, olmayandan kötüdür; o yüzden artık kendini sınıyor."""
    import tempfile
    hata = []
    kl = tempfile.mkdtemp(prefix="cakisma_kendi_")
    try:
        # (1) U biçimli kontur; yazı U'nun BOŞLUĞUNDA duruyor.
        # Sınır kutusu yazıyı kapsar ama hiçbir çizgiye değmez.
        y1 = os.path.join(kl, "bos.dxf")
        d = ezdxf.new(setup=True)
        m = d.modelspace()
        m.add_lwpolyline([(0, 0), (100, 0), (100, 200), (80, 200),
                          (80, 20), (20, 20), (20, 200), (0, 200)],
                         close=True, dxfattribs={"layer": "GORUNEN"})
        # Yazı gerçekten boşluğa sığmalı: yazının kapladığı yer
        # harf sayısı x yükseklik x 0,6 DEĞİLDİR, yazı tipine göre
        # daha geniştir - bu kurgu da bir kere ona takıldı.
        m.add_text("BOS", height=8,
                   dxfattribs={"layer": "YAZI"}).set_placement((35, 100))
        d.saveas(y1)
        ikili, ustunde, n = denetle(y1)
        if ustunde:
            hata.append(f"boşluktaki yazı konturda sanıldı: {ustunde}")
        if n != 1:
            hata.append(f"yazı sayılamadı: {n}")
        # (2) Yazı gerçekten bir çizginin üstünde.
        y2 = os.path.join(kl, "uzerinde.dxf")
        d = ezdxf.new(setup=True)
        m = d.modelspace()
        m.add_line((0, 100), (200, 100), dxfattribs={"layer": "GORUNEN"})
        m.add_text("USTUNDE", height=8,
                   dxfattribs={"layer": "YAZI"}).set_placement((50, 96))
        d.saveas(y2)
        ikili, ustunde, n = denetle(y2)
        if not ustunde:
            hata.append("çizginin üstündeki yazı yakalanamadı")
        # (3) İki yazı üst üste
        y3 = os.path.join(kl, "ikili.dxf")
        d = ezdxf.new(setup=True)
        m = d.modelspace()
        m.add_text("BIRINCI", height=8,
                   dxfattribs={"layer": "YAZI"}).set_placement((0, 0))
        m.add_text("IKINCI", height=8,
                   dxfattribs={"layer": "YAZI"}).set_placement((5, 2))
        d.saveas(y3)
        ikili, ustunde, n = denetle(y3)
        if not ikili:
            hata.append("üst üste binen iki yazı yakalanamadı")
    finally:
        import shutil
        shutil.rmtree(kl, ignore_errors=True)
    for h in hata:
        print("  HATA ", h)
    if not hata:
        print("  tamam boşluktaki yazı temiz sayıldı")
        print("  tamam çizgi üstündeki yazı yakalandı")
        print("  tamam üst üste binen yazılar yakalandı")
    print("SONUC:", "DENETIM DOGRU CALISIYOR" if not hata
          else f"{len(hata)} HATA")
    return 1 if hata else 0


def main(argv):
    if argv and argv[0] in ("--kendini-dene", "-k"):
        return kendini_dene()
    dosya = []
    for a in argv or ["cikti"]:
        if os.path.isdir(a):
            dosya += sorted(glob.glob(os.path.join(a, "*.dxf")))
        elif any(c in a for c in "*?["):
            dosya += sorted(glob.glob(a))
        else:
            dosya.append(a)
    if not dosya:
        print("DXF bulunamadi.")
        return 1
    ty = tk = tn = 0
    for f in dosya:
        try:
            ikili, ustunde, n = denetle(f)
        except Exception as ex:
            print(f"  {os.path.basename(f):32s} OKUNAMADI: {ex}")
            continue
        ty += len(ikili); tk += len(ustunde); tn += n
        durum = "tamam" if not ikili and not ustunde else "HATA "
        print(f"  {durum} {os.path.basename(f):34s} {n:4d} yazi")
        for a, b in ikili[:4]:
            print(f"          yazi-yazi:   {a!r} x {b!r}")
        for m in ustunde[:4]:
            print(f"          konturda:    {m!r}")
    print(f"\n{len(dosya)} resim, {tn} yazi")
    print(f"  yazi-yazi cakismasi : {ty}")
    print(f"  kontur ustunde yazi : {tk}")
    print("SONUC:", "CAKISMA YOK" if not (ty or tk) else f"{ty + tk} CAKISMA")
    return 1 if (ty or tk) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
