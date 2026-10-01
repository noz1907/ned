# -*- coding: utf-8 -*-
"""3B GENEL AÇINIM (pf16_acinim3): büküm eksenleri paralel olmayan sac.

Gerçek kusur: Karluna SOL_DIKME tek sac - 533 mm'lik şapka profili ile
768 mm'lik eğik kanal arasında 5° kırma, alt kanalın büküm eksenleri
üsttekilerden 8,6° dönük. 2B açınım (büküm ekseni Z'ye döndürülüp kesit)
kesim konturunu veremiyordu; CATIA'nın kendi açınımı 1312,8 x 287,4 mm.
3B yöntem 1312,84 x 287,48 verdi (firma modeli depoda değil; burada
sentetik parçalarla denetlenir).

Denetlenen:
  1. Tek yönde bükülmüş U profil: 3B açınım 2B ile aynı (boy, genişlik,
     alan, delik) - gerileme yok.
  2. İKİ YÖNDE bükülmüş parça (gövde + x ekseninde kanat + y ekseninde
     kanat): 3B açınım kurulur, alan = düz alanlar + büküm payları,
     büküm çizgileri birbirine DİK, hacim denetimi tutar.
  3. sac_acilim sarmalayıcısı: 2B "eksenler paralel değil" deyince 3B
     devreye girer, sonuçta cok_yonlu ve kontur var; kanat_dis_olculeri
     çok yönlüde boş.

    python test/acinim3_denetimi.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as O                                            # noqa: E402
import pf16_acinim3 as A3                                       # noqa: E402

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut   # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt                       # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sac_tarama_denetimi import bukumlu_sac                     # noqa: E402

HATA = []


def kontrol(ad, sart, ek=""):
    if sart:
        print(f"  tamam {ad}")
    else:
        print(f"  HATA  {ad}  {ek}")
        HATA.append(ad)


def _fuse(a, b):
    op = BRepAlgoAPI_Fuse(a, b); op.Build(); return op.Shape()


def _cut(a, b):
    op = BRepAlgoAPI_Cut(a, b); op.Build(); return op.Shape()


def _ceyrek(merkez, eksen, r_ic, t, boy, dx, dy):
    """Çeyrek halka (büküm): eksen boyunca boy, iç yarıçap r_ic, kalınlık t.
    (dx, dy): hangi çeyrek (eksene dik düzlemde)."""
    ax = gp_Ax2(gp_Pnt(*merkez), gp_Dir(*eksen))
    dis = BRepPrimAPI_MakeCylinder(ax, r_ic + t, boy).Shape()
    ic = BRepPrimAPI_MakeCylinder(ax, r_ic, boy).Shape()
    halka = _cut(dis, ic)
    R = r_ic + t + 1.0
    # çeyreği seç: eksen yönüne göre kutu
    if eksen == (1.0, 0.0, 0.0):
        kutu = BRepPrimAPI_MakeBox(gp_Pnt(merkez[0] - 1, merkez[1] + (0 if dy > 0 else -R),
                                          merkez[2] + (0 if dx > 0 else -R)),
                                   boy + 2, R, R).Shape()
    else:   # (0,1,0)
        kutu = BRepPrimAPI_MakeBox(gp_Pnt(merkez[0] + (0 if dx > 0 else -R), merkez[1] - 1,
                                          merkez[2] + (0 if dy > 0 else -R)),
                                   R, boy + 2, R).Shape()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    op = BRepAlgoAPI_Common(halka, kutu); op.Build(); return op.Shape()


def iki_yonlu_sac(t=2.0, r=3.0, W=80.0, L=120.0, h1=30.0, h2=25.0):
    """Gövde W x L (XY düzlemi, z 0..t); x=L kenarından YUKARI bükülmüş
    h1 kanat (büküm ekseni Y); y=W kenarından yukarı bükülmüş h2 kanat
    (büküm ekseni X). İki büküm ekseni birbirine dik."""
    govde = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), L, W, t).Shape()
    # kanat 1: x=L ucunda, büküm ekseni Y; büküm merkezi (L, *, t + r) ... iç yarıçap r
    # büküm: eksen Y, merkez (L, 0, t + r)  -> çeyrek halka x>L? Hayır: sac üst
    # yüzeyi z=t'de biter; büküm iç yüzeyi r, dışı r+t; merkez (L, y, t + r).
    b1 = _ceyrek((L, 0.0, t + r), (0.0, 1.0, 0.0), r, t, W - h2 - r - t, dx=1, dy=-1)
    k1 = BRepPrimAPI_MakeBox(gp_Pnt(L + r, 0, t + r), t, W - h2 - r - t, h1).Shape()
    # kanat 2: y=W ucunda, büküm ekseni X; merkez (x, W, t + r)
    b2 = _ceyrek((0.0, W, t + r), (1.0, 0.0, 0.0), r, t, L - r - t, dx=1, dy=-1)
    k2 = BRepPrimAPI_MakeBox(gp_Pnt(0, W + r, t + r), L - r - t, t, h2).Shape()
    sh = govde
    for p in (b1, k1, b2, k2):
        sh = _fuse(sh, p)
    return sh


def dene_tek_yon():
    print("1) tek yönlü U profil: 3B = 2B")
    sh = bukumlu_sac()
    hac = O.hacim(sh)
    a2 = O._sac_acilim_2b(sh, {"hacim_mm3": hac}, k_faktor=0.4)
    tr = O.sac_taramasi(sh)
    a3 = A3.acilim3(sh, tr["kalinlik_mm"], 0.4, O, hacim=hac)
    kontrol("boy aynı", abs(a2["acinim_boy_mm"] - a3["acinim_boy_mm"]) < 0.05,
            (a2["acinim_boy_mm"], a3["acinim_boy_mm"]))
    kontrol("genişlik aynı", abs(a2["acinim_genislik_mm"] - a3["acinim_genislik_mm"]) < 0.05,
            (a2["acinim_genislik_mm"], a3["acinim_genislik_mm"]))
    kontrol("alan aynı (%0,2)", abs(a2["acinim_alan_mm2"] - a3["acinim_alan_mm2"]) < 0.002 * a2["acinim_alan_mm2"],
            (a2["acinim_alan_mm2"], a3["acinim_alan_mm2"]))
    kontrol("delik sayısı aynı", a2["delik_adedi"] == a3["delik_adedi"], (a2["delik_adedi"], a3["delik_adedi"]))
    kontrol("büküm sayısı aynı", a2["bukum_sayisi"] == a3["bukum_sayisi"])


def dene_iki_yon():
    print("2) iki yönde bükülmüş parça")
    t, r, W, L, h1, h2 = 2.0, 3.0, 80.0, 120.0, 30.0, 25.0
    sh = iki_yonlu_sac(t, r, W, L, h1, h2)
    hac = O.hacim(sh)
    tr = O.sac_taramasi(sh)
    kontrol("tarama: bükümlü sac, eksenler paralel değil",
            tr["tip"] == "bukumlu sac" and tr["eksen_paralel"] is False, tr)
    try:
        O._sac_acilim_2b(sh, {"hacim_mm3": hac}, k_faktor=0.4)
        kontrol("2B yöntem bu parçayı açmıyor", False, "açtı")
    except O.AcilimYok:
        kontrol("2B yöntem bu parçayı açmıyor (beklenen)", True)
    a3 = A3.acilim3(sh, t, 0.4, O, hacim=hac)
    pay = math.pi / 2 * (r + 0.4 * t)
    L1, L2 = W - h2 - r - t, L - r - t
    bekl_alan = (L * W + L1 * h1 + L2 * h2 + L1 * pay + L2 * pay)
    kontrol("alan = düzler + büküm payları", abs(a3["acinim_alan_mm2"] - bekl_alan) < 0.5,
            (a3["acinim_alan_mm2"], round(bekl_alan, 1)))
    kontrol("2 büküm", a3["bukum_sayisi"] == 2)
    yon = []
    for b in a3["bukumler"]:
        (x1, y1), (x2, y2) = b["cizgi"]
        yon.append(math.atan2(y2 - y1, x2 - x1))
    fark = abs(math.degrees(yon[0] - yon[1])) % 180
    kontrol("büküm çizgileri birbirine dik", abs(fark - 90) < 0.5, fark)
    kontrol("açılar 90, pay doğru", all(abs(b["aci_derece"] - 90) < 0.1 and abs(b["pay_mm"] - pay) < 0.01
                                       for b in a3["bukumler"]), a3["bukumler"])
    gab = sorted((a3["acinim_boy_mm"], a3["acinim_genislik_mm"]))
    bekl = sorted((L + pay + h1, W + pay + h2))
    kontrol("gabari = gövde + pay + kanat", all(abs(a - b) < 0.05 for a, b in zip(gab, bekl)), (gab, bekl))
    kontrol("cok_yonlu işareti", a3.get("cok_yonlu") is True)
    print("3) sac_acilim sarmalayıcı")
    r_ = O.sac_acilim(sh, {"hacim_mm3": hac}, k_faktor=0.4)
    kontrol("sarmalayıcı 3B'ye düştü, kontur var", r_.get("cok_yonlu") and r_.get("kontur_dis"))
    kontrol("kontur notu çok yönlü", "ÇOK YÖNLÜ" in (r_.get("kontur_notu") or ""))
    kontrol("kanat_dis_olculeri çok yönlüde boş", O.kanat_dis_olculeri(r_) == [])
    kontrol("izo var", bool(r_.get("izo")))


if __name__ == "__main__":
    dene_tek_yon()
    dene_iki_yon()
    print()
    if HATA:
        print(f"SONUC: {len(HATA)} HATA: " + ", ".join(HATA))
        sys.exit(1)
    print("SONUC: TUM DENETIMLER GECTI")
