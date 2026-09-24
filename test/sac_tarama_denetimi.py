# -*- coding: utf-8 -*-
"""Sac taraması: program bükümlü parçaları KENDİSİ buluyor mu?

Neden ayrı bir tarama var: açınım hesabı parçayı döndürüp kesit alır,
parça başına 15-30 saniye sürer. Bir montajda yüzlerce komponent olur;
hepsine açınım denemek saatler sürer, kullanıcıya da "hangileri sac?"
diye sormak doğru değildir - bunu ölçüden program bilir.

sac_taramasi yalnız SİLİNDİRİK YÜZEYLERE bakar: bükümün iç ve dış
silindiri aynı eksendedir ve aralarındaki fark sac kalınlığıdır.
Delikte böyle bir çift yoktur, köşe yuvarlatmasının ekseni sac yüzüne
diktir. Parça başına ~20 ms.

Burada bilerek kurulmuş katılar kullanılır; cevabın ne olması gerektiği
geometriden bellidir. Gerçek montajdaki doğruluk ayrıca ölçüldü:
16 parçanın 7'si bükümlü çıktı, açınımı gerçekten olan 5 parçanın
hepsi bu 7'nin içindeydi - HİÇBİRİ KAÇMADI.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as M                                          # noqa: E402

from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox,             # noqa: E402
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


def kutu(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def silindir(r, boy):
    """X ekseni boyunca, orijinden başlayan silindir."""
    return BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), r, boy).Shape()


def bukumlu_sac(r_ic=3.0, t=2.0, boy=300.0, kanat=100.0):
    """Tek bükümlü L sac: çeyrek boru + iki düz kanat.

    Çeyrek boru X ekseni çevresinde, y>0 z>0 çeyreğinde durur. Kanatlar
    bükümün teğetinden devam eder: biri -Z'ye, öbürü -Y'ye."""
    r_dis = r_ic + t
    boru = BRepAlgoAPI_Cut(silindir(r_dis, boy), silindir(r_ic, boy)).Shape()
    ceyrek = BRepAlgoAPI_Cut(
        boru, BRepAlgoAPI_Cut(
            kutu(-1, -r_dis - 1, -r_dis - 1, boy + 2,
                 2 * r_dis + 2, 2 * r_dis + 2),
            kutu(0, 0, 0, boy, r_dis, r_dis)).Shape()).Shape()
    kanat_a = kutu(0, r_ic, -kanat, boy, t, kanat)
    kanat_b = kutu(0, -kanat, r_ic, boy, kanat, t)
    return BRepAlgoAPI_Fuse(
        BRepAlgoAPI_Fuse(ceyrek, kanat_a).Shape(), kanat_b).Shape()


def main():
    print("-- bükümlü sac (çeyrek büküm + iki kanat)")
    sh = bukumlu_sac()
    r = M.sac_taramasi(sh)
    print("     ", r)
    esit("bükümlü sac diye bulundu", r["tip"], "bukumlu sac")
    dogru("sac sayıldı", r["sac"])
    esit("kalınlık ölçüldü", r["kalinlik_mm"], 2.0)
    esit("büküm sayıldı", r["bukum_sayisi"], 1)
    esit("büküm ekseni paralel", r["eksen_paralel"], True)

    print("\n-- düz plaka (bükümü yok)")
    r = M.sac_taramasi(kutu(0, 0, 0, 200, 100, 3))
    print("     ", r)
    esit("düz sac diye bulundu", r["tip"], "duz sac")
    esit("kalınlık ölçüldü", r["kalinlik_mm"], 3.0)
    esit("büküm yok", r["bukum_sayisi"], 0)
    dogru("açınımı kendisi olduğu yazıyor", "açınımı kendisidir" in r["neden"],
          r["neden"])

    print("\n-- delikli düz plaka: delik büküm sanılmamalı")
    p = BRepAlgoAPI_Cut(
        kutu(0, 0, 0, 200, 100, 3),
        BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(60, 50, -1), gp_Dir(0, 0, 1)), 5.0, 5.0).Shape()
    ).Shape()
    r = M.sac_taramasi(p)
    print("     ", r)
    esit("delik büküm sayılmadı", r["tip"], "duz sac")
    esit("büküm sayısı sıfır", r["bukum_sayisi"], 0)

    print("\n-- kalın blok: sac değil")
    r = M.sac_taramasi(kutu(0, 0, 0, 60, 50, 40))
    print("     ", r)
    esit("sac değil", r["tip"], "sac degil")
    dogru("sac sayılmadı", not r["sac"])

    print("\n-- kalın cidarlı, küçük parça: radüsü var ama sac değil")
    # Cidar 12 mm, parçanın en büyük ölçüsü 40 mm. Silindir çifti
    # bulunur ama gabari kalınlığa göre küçüktür: freze parçasıdır.
    r = M.sac_taramasi(bukumlu_sac(r_ic=3.0, t=12.0, boy=40.0, kanat=20.0))
    print("     ", r)
    esit("kalın cidar sac sayılmadı", r["tip"], "sac degil")
    dogru("sebebi yazılı", bool(r["neden"]), "sebep boş")

    print("\n-- tarama ucuz mu (açınım hesabına göre)")
    import time
    sh = bukumlu_sac()
    t0 = time.time()
    for _ in range(5):
        M.sac_taramasi(sh)
    tara = (time.time() - t0) / 5
    t0 = time.time()
    try:
        M.sac_acilim(sh)
        ac = time.time() - t0
    except Exception:
        ac = time.time() - t0
    print(f"      tarama {tara * 1000:.0f} ms   açınım {ac * 1000:.0f} ms")
    dogru("tarama açınımdan hızlı", tara < ac,
          f"tarama {tara:.3f}s, açınım {ac:.3f}s")

    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                         else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
