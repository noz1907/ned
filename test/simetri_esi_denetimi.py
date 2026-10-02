# -*- coding: utf-8 -*-
"""SİMETRİK EŞ DENETİMİ: "Symmetry of X" adlı parça X'in aynası mı?

  1. Ad çözümü: "Symmetry of KAPAK.2" -> ("kapak", eş); "KAPAK_1" -> ("kapak", asıl).
  2. Gerçek ayna (delikli levha, X aynası): fark yok.
  3. Bir deliği 3 mm kaymış "ayna": fark var (delik aralıkları).
  4. Deliği eksik "ayna": fark var (delik adedi).

    python test/simetri_esi_denetimi.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder   # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut                                   # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform                       # noqa: E402
from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir, gp_Trsf, gp_Ax2 as _A              # noqa: E402
import pf3_olcu as O                                                          # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def levha(delikler):
    sh = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 300, 200, 3).Shape()
    for x, y in delikler:
        sh = BRepAlgoAPI_Cut(sh, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)), 4.5, 5).Shape()).Shape()
    return sh


def ayna_x(sh):
    """X aynası. Ayna dönüşümü yüz yönlerini ters çevirir (determinant -1);
    STEP'ten gelen simetrik parçada bu olmaz, sentetik katıda Reversed ile
    düzeltilir."""
    tr = gp_Trsf(); tr.SetMirror(_A(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)))
    return BRepBuilderAPI_Transform(sh, tr, True).Shape().Reversed()


def olc(sh):
    P = {"yogunluk": 7.85e-6, "en_az_delik": 1.0, "arac": None}
    return O.komponent_olcu(sh, P)[1]


def main():
    print("1) ad çözümü")
    dogru("Symmetry of KAPAK.2 -> kapak, kapak, eş", O.simetri_anahtari("Symmetry of KAPAK.2") == ("kapak", "kapak", True),
          O.simetri_anahtari("Symmetry of KAPAK.2"))
    dogru("KAPAK_1 -> kapak_1, kapak, asıl", O.simetri_anahtari("KAPAK_1") == ("kapak_1", "kapak", False), O.simetri_anahtari("KAPAK_1"))
    dogru("Symmetry of PROFILI_10 -> profili_10 (indeks korunur)",
          O.simetri_anahtari("Symmetry of K0 TRIM BAGLANTI PROFILI_10")[0] == "k0 trim baglanti profili_10")
    dogru("YAN SAC SIMETRI -> yan sac, eş", O.simetri_anahtari("YAN SAC SIMETRI")[1:] == ("yan sac", True),
          O.simetri_anahtari("YAN SAC SIMETRI"))
    print("1b) aday seçimi")
    from collections import defaultdict
    og, ta = {}, defaultdict(set)
    for ad in ("K0 X_1", "Symmetry of K0 X_1", "K0 X_3", "YAN KAPAK", "K0 Y_5", "K0 Y_5.1"):
        tam, temel, es = O.simetri_anahtari(ad)
        og.setdefault(tam, []).append(({"ad": ad}, ad, es)); ta[temel].add(tam)
    def aday(ad):
        tam, temel, es = O.simetri_anahtari(ad)
        return [c[1] for c in O.simetri_adaylari(og, ta, tam, temel, es)]
    dogru("Symmetry of K0 X_3 -> K0 X_3 (aynı indeks)", aday("Symmetry of K0 X_3") == ["K0 X_3"], aday("Symmetry of K0 X_3"))
    dogru("Symmetry of K0 X_2 -> aday yok (farklı indeks eşleşmez)", aday("Symmetry of K0 X_2") == [], aday("Symmetry of K0 X_2"))
    dogru("Symmetry of YAN KAPAK_1 -> YAN KAPAK (indekssiz asıl)", aday("Symmetry of YAN KAPAK_1") == ["YAN KAPAK"], aday("Symmetry of YAN KAPAK_1"))
    dogru("Symmetry of K0 Y_5 -> iki aday (5 ve 5.1)", sorted(aday("Symmetry of K0 Y_5")) == ["K0 Y_5", "K0 Y_5.1"], aday("Symmetry of K0 Y_5"))
    print("2) gerçek ayna")
    d = [(30, 30), (30, 170), (270, 30), (120, 100)]
    o1 = olc(levha(d))
    o2 = olc(ayna_x(levha(d)))
    f = O.simetri_farklari(o1, o2)
    dogru("gerçek aynada fark yok", not f, f)
    print("3) kaymış delik")
    o3 = olc(ayna_x(levha([(30, 30), (30, 170), (270, 30), (123, 100)])))
    f3 = O.simetri_farklari(o1, o3)
    dogru("3 mm kaymış delik: fark var", any("aralık" in t for t in f3), f3)
    print("4) eksik delik")
    o4 = olc(ayna_x(levha(d[:3])))
    f4 = O.simetri_farklari(o1, o4)
    dogru("eksik delik: fark var (adet + hacim olabilir)", any("adedi" in t for t in f4), f4)
    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 0 if not HATA else 1


if __name__ == "__main__":
    sys.exit(main())
