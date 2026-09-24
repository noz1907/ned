# -*- coding: utf-8 -*-
"""Konum ölçüleri: deliklerin kenardan yeri.

Önce resimde YALNIZ gabari ölçüsü vardı (görünüş başına 2 tane) ve
Ø/R boyutları. Deliğin nerede olduğunu söyleyen tek bir ölçü yoktu:
atölye "2480 x 120 sacta 124 delik Ø6,8" biliyordu ama deliklerin
yerini bilmiyordu.

Zincir kuralı (kullanıcının verdiği): kenardan ilk deliğe, sonra
dizinin adımı, sonra son delikten öbür kenara. 124 deliğin her birine
20 mm yazmak resmi okunmaz yapar ve hiçbir şey eklemez.

Denetlenen:
  1. Dizi tanınıyor mu ve "123 x 20" diye tek ölçüye iniyor mu,
  2. zincir kenardan başlayıp kenarda bitiyor mu,
  3. dağınık delikler tek tek ölçülüyor mu,
  4. gabari ölçüsü EN DIŞARIDA mı (küçük ölçüler içeride),
  5. hiçbir yazı bir başkasının ya da konturun üstüne binmiyor mu.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                   # noqa: E402
import ezdxf.bbox                                              # noqa: E402
import pf3_olcu as O                                           # noqa: E402

from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox,              # noqa: E402
                             BRepPrimAPI_MakeCylinder)
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut                    # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt                      # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    if kosul:
        print(f"  tamam {ad}")
    else:
        print(f"  HATA  {ad}: {neden}")
        HATA.append(ad)


def esit(ad, olan, beklenen):
    dogru(ad, olan == beklenen, f"{olan!r} != {beklenen!r}")


def plaka(gen, boy, t, delik):
    sh = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), gen, boy, t).Shape()
    for x, y, r in delik:
        sh = BRepAlgoAPI_Cut(sh, BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)), r, t + 2).Shape()).Shape()
    return sh


def olcu_degerleri(yol):
    d = ezdxf.readfile(yol)
    out = []
    for e in d.modelspace():
        if e.dxftype() != "DIMENSION":
            continue
        t = (e.dxf.get("text", "") or "").strip()
        try:
            v = round(float(e.get_measurement()), 2)
        except Exception:
            v = None
        out.append((t if t not in ("", "<>") else None, v))
    return out


def main():
    kl = tempfile.mkdtemp(prefix="konum_denetim_")
    P = {"gizli": False, "en_az_delik": 1.0, "yogunluk": O.RHO,
         "gorunusler": ("UST",), "kesit": False}

    print("-- dizi: 10 mm'den başlayan, 20 mm adımlı 11 delik")
    sh = plaka(220.0, 60.0, 5.0,
               [(10.0 + 20.0 * i, 30.0, 3.4) for i in range(11)])
    s2, o = O.komponent_olcu(sh, P)
    ham = {"UST": O._kenar_kutusu(O.hlr(s2, *O.GORUNUS["UST"], gizli=False))}
    pl = O.konum_plani(o, ("UST",), ham, 4.0)
    y = pl["UST"]["yatay"]
    print("     yatay zincir:",
          [(round(r["a"], 1), round(r["b"], 1), r["metin"]) for r in y])
    esit("zincir üç parça", len(y), 3)
    dogru("kenardan başlıyor", abs(y[0]["b"] - y[0]["a"] - 10.0) < 0.2,
          f"{y[0]}")
    esit("ortadaki dizi", y[1]["metin"], "10 x 20")
    dogru("kenarda bitiyor", abs(y[2]["b"] - y[2]["a"] - 10.0) < 0.2,
          f"{y[2]}")
    dogru("hiçbir ölçü 20 diye tek tek yazılmamış",
          sum(1 for r in y if r["metin"] is None and
              abs((r["b"] - r["a"]) - 20.0) < 0.2) == 0,
          "adım tek tek yazılmış")

    print("\n-- dağınık delikler tek tek ölçülüyor")
    sh2 = plaka(120.0, 80.0, 5.0, [(15.0, 20.0, 3.0), (47.0, 60.0, 3.0),
                                   (95.0, 35.0, 3.0)])
    s3, o2 = O.komponent_olcu(sh2, P)
    ham2 = {"UST": O._kenar_kutusu(O.hlr(s3, *O.GORUNUS["UST"], gizli=False))}
    pl2 = O.konum_plani(o2, ("UST",), ham2, 4.0)
    esit("yatay zincirde 4 aralık", len(pl2["UST"]["yatay"]), 4)
    esit("düşey zincirde 4 aralık", len(pl2["UST"]["dusey"]), 4)
    dogru("hiçbiri dizi sayılmadı",
          all(r["metin"] is None for r in pl2["UST"]["yatay"]), "dizi bulundu")

    print("\n-- resim: gabari en dışarıda, çakışma yok")
    yol = os.path.join(kl, "P01_DENEME.dxf")
    O.dxf_komponent(s2, o, {"poz": 1, "kod": "DENEME", "ad": "Dizi plaka",
                            "adet": 1, "malzeme_ad": "Celik"}, yol, P)
    d = ezdxf.readfile(yol)
    olc = olcu_degerleri(yol)
    print("     ölçüler:", olc)
    dogru("'10 x 20' resme girdi",
          any(t == "10 x 20" for t, _v in olc), str(olc))
    dogru("gabari 220 var", any(v == 220.0 for _t, v in olc), str(olc))
    dogru("kenar payları var",
          sum(1 for _t, v in olc if v == 10.0) >= 2, str(olc))

    # Gabari ölçüsü, konum ölçülerinin DIŞINDA olmalı.
    gab = alt = None
    for e in d.modelspace():
        if e.dxftype() != "DIMENSION":
            continue
        try:
            v = round(float(e.get_measurement()), 2)
        except Exception:
            continue
        k = ezdxf.bbox.extents([e], fast=True)
        if not k.has_data:
            continue
        if v == 220.0:
            gab = k.extmin.y
        elif (e.dxf.get("text", "") or "") == "10 x 20":
            alt = k.extmin.y
    dogru("gabari konum ölçüsünün dışında",
          gab is not None and alt is not None and gab < alt,
          f"gabari y={gab}, zincir y={alt}")

    print("\n-- çakışma")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import cizim_cakisma_denetimi as C
    n = C.resmi_denetle(yol) if hasattr(C, "resmi_denetle") else None
    if n is None:
        import subprocess
        r = subprocess.run([sys.executable,
                            os.path.join(os.path.dirname(
                                os.path.abspath(__file__)),
                                "cizim_cakisma_denetimi.py"), yol],
                           capture_output=True, text=True)
        dogru("çakışma yok", "CAKISMA YOK" in r.stdout,
              r.stdout.strip().splitlines()[-1] if r.stdout else "?")
    else:
        dogru("çakışma yok", n == 0, str(n))

    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                         else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
