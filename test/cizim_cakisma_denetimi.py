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
    kont = [k for k in (kutu(e) for e in msp
                        if e.dxf.layer == "GORUNEN" and e.dxftype() in KONTUR)
            if k]
    ustunde = [m for k, m in yz if any(kesisir(k, c) for c in kont)]
    return ikili, ustunde, len(yz)


def main(argv):
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
