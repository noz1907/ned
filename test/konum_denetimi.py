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
    # Sıra ÖLÇÜ BOYUNA göredir (kısa içeride); içeriğe göre aranır.
    esit("zincir üç parça", len(y), 3)
    diz = [r for r in y if r["metin"]]
    kenar = sorted(r for r in (abs(r["b"] - r["a"]) for r in y))
    esit("ortadaki dizi", [r["metin"] for r in diz], ["10 x 20"])
    dogru("kenardan başlıyor",
          any(abs(r["a"] - 0.0) < 0.2 and abs(r["b"] - 10.0) < 0.2 for r in y),
          str([(round(r["a"], 1), round(r["b"], 1)) for r in y]))
    dogru("kenarda bitiyor",
          any(abs(r["b"] - 220.0) < 0.2 and abs(r["a"] - 210.0) < 0.2
              for r in y),
          str([(round(r["a"], 1), round(r["b"], 1)) for r in y]))
    dogru("hiçbir ölçü 20 diye tek tek yazılmamış",
          sum(1 for r in y if r["metin"] is None and
              abs((r["b"] - r["a"]) - 20.0) < 0.2) == 0,
          "adım tek tek yazılmış")

    print("\n-- dağınık delikler DATUMDAN ölçülüyor (zincir DEĞİL)")
    sh2 = plaka(120.0, 80.0, 5.0, [(15.0, 20.0, 3.0), (47.0, 60.0, 3.0),
                                   (95.0, 35.0, 3.0)])
    s3, o2 = O.komponent_olcu(sh2, P)
    ham2 = {"UST": O._kenar_kutusu(O.hlr(s3, *O.GORUNUS["UST"], gizli=False))}
    pl2 = O.konum_plani(o2, ("UST",), ham2, 4.0)
    yx = pl2["UST"]["yatay"]
    print("     yatay:", [(round(r["a"], 1), round(r["b"], 1)) for r in yx])
    # Delikler x = 15, 47, 95; plaka 0..120. Her ölçü AYNI kenardan
    # (x=0) başlamalı - zincir kurulmamalı. Zincirde 15, 32, 48 diye
    # ara farklar çıkardı ve 47'yi bulmak için toplamak gerekirdi.
    esit("hepsi aynı datumdan", sorted({round(r["a"], 1) for r in yx}), [0.0])
    esit("ölçülen konumlar",
         sorted(round(r["b"], 1) for r in yx), [15.0, 47.0, 95.0])
    dogru("hiçbiri dizi sayılmadı",
          all(r["metin"] is None for r in yx), "dizi bulundu")
    dy = pl2["UST"]["dusey"]
    esit("düşeyde de tek datum", sorted({round(r["a"], 1) for r in dy}), [0.0])

    print("\n-- çapraz (pahlı) kenarlar")
    # 45°'lik pah: köşesi kesilmiş plaka.
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut as _Cut
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec
    pg = BRepBuilderAPI_MakePolygon(gp_Pnt(100, 80, -1), gp_Pnt(120, 80, -1),
                                    gp_Pnt(120, 60, -1), True).Wire()
    kama = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(pg).Face(),
                                 gp_Vec(0, 0, 7)).Shape()
    pah = _Cut(plaka(120.0, 80.0, 5.0, []), kama).Shape()
    ke = O.hlr(pah, *O.GORUNUS["UST"], gizli=False)
    cp = O.capraz_kenarlar(ke)
    print("     bulunan:", [(round(t["aci"], 1), round(t["uz"], 1)) for t in cp])
    dogru("45 derecelik pah bulundu",
          any(abs(t["aci"] - 135.0) < 1.0 or abs(t["aci"] - 45.0) < 1.0
              for t in cp), str([round(t["aci"], 1) for t in cp]))
    dogru("boyu doğru (20√2 = 28,3)",
          any(abs(t["uz"] - 28.28) < 0.3 for t in cp),
          str([round(t["uz"], 1) for t in cp]))
    dogru("yatay ve düşey kenarlar çapraz sayılmadı",
          all(min(abs(t["aci"]), abs(t["aci"] - 90), abs(t["aci"] - 180)) > 1.0
              for t in cp), "eksene paralel kenar geldi")

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

    print("\n-- açı yazısı makul hassasiyette")
    yol4 = os.path.join(kl, "P04_PAH.dxf")
    s4, o4 = O.komponent_olcu(pah, P)
    O.dxf_komponent(s4, o4, {"poz": 4, "kod": "PAH", "ad": "Pahlı plaka",
                             "adet": 1, "malzeme_ad": "Celik"}, yol4, P)
    d4 = ezdxf.readfile(yol4)
    aci = [e.dxf.text for e in d4.modelspace()
           if e.dxftype() == "TEXT" and "%%d" in (e.dxf.text or "")]
    print("     açı yazıları:", aci)
    dogru("açı resme girdi", bool(aci), "açı yazılmamış")
    dogru("aşırı hassasiyet yok",
          all(len(t.replace("%%d", "").split(".")[-1]) <= 1
              for t in aci if "." in t), str(aci))
    dogru("açı kılavuzla bağlı",
          sum(1 for e in d4.modelspace()
              if e.dxftype() == "LINE" and e.dxf.layer == "OLCU") >= len(aci),
          "kılavuz çizgisi yok")

    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                         else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
