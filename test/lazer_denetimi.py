# -*- coding: utf-8 -*-
"""Lazer kesim resimleri (…_Lzr.dxf).

Bu dosyalar OKUNMAK için değil KESİLMEK için üretilir. CAM yazılımı
dosyadaki her çizgiyi kesim yolu sayabilir; resmin üstündeki bir yazı
ya da ölçü çizgisi sacın üstüne kesilir. Bu yüzden burada asıl
denetlenen şey, dosyada KONTURDAN BAŞKA HİÇBİR ŞEY OLMADIĞIDIR.

Ayrıca:
  - düz plakanın konturu doğru mu (ölçü, delik sayısı),
  - plaka olmayan bir parça reddediliyor mu (cepli/kademeli parçanın
    kesim konturu tek düzlemden çıkarılamaz),
  - dosya adı "_Lzr" ile bitiyor mu,
  - bu dosyalar paftaya/PDF'e girmiyor mu.
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
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse  # noqa: E402
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


def yakin(ad, olan, beklenen, pay=0.05):
    dogru(ad, abs(olan - beklenen) <= pay, f"{olan} != {beklenen} (±{pay})")


def plaka(gen=200.0, boy=100.0, t=5.0, delik=()):
    sh = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), gen, boy, t).Shape()
    for x, y, r in delik:
        d = BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)), r, t + 2).Shape()
        sh = BRepAlgoAPI_Cut(sh, d).Shape()
    return sh


def main():
    kl = tempfile.mkdtemp(prefix="lazer_denetim_")

    print("-- düz plakanın kesim konturu")
    sh = plaka(delik=[(40, 50, 5), (160, 50, 5), (100, 25, 8)])
    c = O.duz_sac_konturu(sh)
    yakin("kalınlık", c["kalinlik_mm"], 5.0)
    esit("dış kontur tek parça", len(c["kontur_dis"]), 1)
    esit("delik sayısı", len(c["kontur_delik"]), 3)
    yakin("en", c["olcu"][0], 200.0, 0.2)
    yakin("boy", c["olcu"][1], 100.0, 0.2)
    dogru("kontur sıfırdan başlıyor",
          min(p[0] for w in c["kontur_dis"] for p in w) >= -1e-6
          and min(p[1] for w in c["kontur_dis"] for p in w) >= -1e-6,
          "kontur eksi koordinatta")

    print("\n-- plaka olmayan parça reddediliyor")
    # Kademeli parça: hacim, alan x kalınlık ile tutmaz.
    kademe = BRepAlgoAPI_Fuse(
        plaka(200.0, 100.0, 5.0),
        BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 5), 80.0, 100.0, 20.0).Shape()).Shape()
    try:
        O.duz_sac_konturu(kademe)
        dogru("kademeli parça reddedildi", False, "kontur verdi")
    except O.AcilimYok as e:
        dogru("kademeli parça reddedildi", True)
        print("     sebep:", str(e).splitlines()[0][:70])
    try:
        O.duz_sac_konturu(BRepPrimAPI_MakeBox(
            gp_Pnt(0, 0, 0), 60.0, 50.0, 40.0).Shape())
        dogru("kalın blok reddedildi", False, "kontur verdi")
    except O.AcilimYok:
        dogru("kalın blok reddedildi", True)

    print("\n-- dosyada KONTURDAN BAŞKA bir şey yok")
    yol = os.path.join(kl, "P07_09_020_000_03_Plaka_Lzr.dxf")
    O.dxf_lazer(c["kontur_dis"], c["kontur_delik"], yol)
    d = ezdxf.readfile(yol)
    msp = list(d.modelspace())
    tipler = sorted({e.dxftype() for e in msp})
    esit("yalnız LWPOLYLINE var", tipler, ["LWPOLYLINE"])
    esit("kontur sayısı", len(msp), 4)          # 1 dış + 3 delik
    esit("hepsi tek katmanda",
         sorted({e.dxf.layer for e in msp}), [O.LAZER_KATMAN])
    dogru("hepsi kapalı çokgen", all(e.closed for e in msp),
          "açık kontur lazerde kesilmez")
    esit("pafta sekmesi yok",
         [a for a in d.layout_names() if a not in ("Model", "Layout1")], [])
    esit("hiç yazı yok",
         sum(1 for e in msp if e.dxftype() in ("TEXT", "MTEXT")), 0)
    esit("hiç ölçü yok",
         sum(1 for e in msp if e.dxftype() == "DIMENSION"), 0)
    # 1:1 olmalı: konturun ölçüsü parçanın ölçüsü
    k = ezdxf.bbox.extents(msp, fast=False)
    yakin("çizim 1:1", k.extmax.x - k.extmin.x, 200.0, 0.2)

    print("\n-- dosya adı")
    dogru("_Lzr ile bitiyor", yol.endswith("_Lzr.dxf"), yol)
    esit("detay resmiyle aynı kök",
         O.resim_dosyasi(7, "09.020.000.03", "Plaka", lazer=True),
         "P07_09_020_000_03_Plaka_Lzr.dxf")
    esit("detay resmi", O.resim_dosyasi(7, "09.020.000.03", "Plaka"),
         "P07_09_020_000_03_Plaka.dxf")

    print("\n-- pafta bu dosyaları almıyor")
    import pf4_pafta as P
    # Pafta listesi çıktı klasöründeki *.dxf'leri tarar; _Lzr elenmeli.
    gui = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "pf3_gui.py"), encoding="utf-8").read()
    dogru("7. adım _Lzr dosyalarını eliyor",
          'endswith("_Lzr.dxf")' in gui,
          "lazer resimleri pafta listesine giriyor")
    # Yine de biri elle verilse pafta kurulabilir mi - kurulmamalı
    # diye bir kural yok, ama PDF'e kendiliğinden GİRMEMELİ.
    p = P.kagit_plani([yol], "A3")
    dogru("tek başına verilirse yine de okunuyor",
          len(p["birebir"]) + len(p["olcekli"]) + len(p["sigmayan"]) == 1,
          "dosya okunamadı")

    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                         else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
