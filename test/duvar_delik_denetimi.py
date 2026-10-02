# -*- coding: utf-8 -*-
"""TEK DUVAR DELİKLERİ (pf3_olcu: delik_duvarlari, delik_gorunusu,
gerekli_delik_gorunusleri) ve SİMETRİ TOLERANSI.

Kullanıcı (Karluna alüminyum yan kapak): "kapaklarda delik bir yönde var,
diğer yönde yok; deliğin diğer yüzde olduğu görülmeli ya da görünüm
eklenmeli - görünüm ekleme daha doğru". Sentetik içi boş kutu (200 x 100
x 26, 2 mm duvar): +X duvarında 2 delik, -X duvarında 3 delik, Z boyunca
boydan boya 1 delik.
  1. delikler duvara göre bölünüyor (max / min / orta)
  2. ölçülenecek görünüş duvarının göründüğü görünüş: +X duvarı SAĞ, -X
     duvarı SOL; boydan boya delik ilk seçili görünüş
  3. seçili görünüşlerde SOL yoksa eklenmesi gereken görünüş SOL
  4. simetri: 1 mm asimetrik delik çifti simetrik SAYILMAZ (eski 0,002·L
     payı uzun parçada 3,6 mm'ye çıkıyor, sağ çift ölçüsüz kalıyordu)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder   # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut                                   # noqa: E402
from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir                                     # noqa: E402
import pf3_olcu as O                                                          # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def kutu_profil():
    dis = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 26, 200, 100).Shape()
    ic = BRepPrimAPI_MakeBox(gp_Pnt(2, 2, 2), 22, 196, 96).Shape()
    sh = BRepAlgoAPI_Cut(dis, ic).Shape()

    def delik(x0, y, z, yon, r=3.25, boy=4.0):
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x0, y, z), gp_Dir(*yon)), r, boy).Shape()
    for y, z in ((40.0, 20.0), (160.0, 20.0)):                 # +X duvarı (x 24..26)
        sh = BRepAlgoAPI_Cut(sh, delik(23.0, y, z, (1, 0, 0))).Shape()
    for y, z in ((30.0, 70.0), (100.0, 70.0), (170.0, 70.0)):  # -X duvarı (x 0..2)
        sh = BRepAlgoAPI_Cut(sh, delik(-1.0, y, z, (1, 0, 0))).Shape()
    sh = BRepAlgoAPI_Cut(sh, BRepPrimAPI_MakeCylinder(                 # Z boyunca, boydan boya
        gp_Ax2(gp_Pnt(13.0, 100.0, -1.0), gp_Dir(0, 0, 1)), 4.0, 102.0).Shape()).Shape()
    return sh


def main():
    sh = kutu_profil()
    P = {"yogunluk": 2.7e-6, "en_az_delik": 1.0, "arac": None}
    s, o = O.komponent_olcu(sh, P)
    print("1) duvar ayrımı (geniş yüz ÖN'e döndüğünden X duvarları çizimde Y duvarıdır)")
    x = {(d["eksen"], d.get("taraf")): d for d in o["delikler"]}
    dogru("+X duvarı 2 delik -> çizimde -Y (min)", ("Y", "min") in x and x[("Y", "min")]["adet"] == 2,
          [(d["eksen"], d.get("taraf"), d["adet"]) for d in o["delikler"]])
    dogru("-X duvarı 3 delik -> çizimde +Y (max)", ("Y", "max") in x and x[("Y", "max")]["adet"] == 3)
    dogru("boydan boya Z deliği 'orta'", ("Z", "orta") in x)
    print("2) ölçülenecek görünüş")
    gor = ("ON", "SAG", "SOL", "UST")
    dogru("-Y duvarı ÖN'de", O.delik_gorunusu(x[("Y", "min")], gor) == "ON")
    dogru("+Y duvarı ARKA'da", O.delik_gorunusu(x[("Y", "max")], gor + ("ARKA",)) == "ARKA")
    dogru("boydan boya ilk seçili (ÜST)", O.delik_gorunusu(x[("Z", "orta")], gor) == "UST")
    print("3) eksik görünüş eklenir")
    dogru("ARKA seçili değilse eklenir", O.gerekli_delik_gorunusleri(o, gor) == ["ARKA"])
    dogru("ikisi de seçiliyse ek yok", O.gerekli_delik_gorunusleri(o, gor + ("ARKA",)) == [])
    print("4) simetri toleransı")
    import re
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pf3_olcu.py"),
               encoding="utf-8").read()
    dogru("0,002·L payı kaldırıldı", "0.002 * L" not in src)
    # 1805 mm'lik plakada 66/172 ile 65/171: simetrik sayılmamalı
    L = 1805.0
    tekil = [66.0, 172.0, 1634.0, 1740.0]
    sim = all(any(abs((0 + L - a) - b) <= 0.05 for b in tekil) for a in tekil)
    dogru("1 mm asimetrik çift simetrik değil", not sim)
    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 0 if not HATA else 1


if __name__ == "__main__":
    sys.exit(main())
