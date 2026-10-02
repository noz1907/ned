# -*- coding: utf-8 -*-
"""ARAÇ YÖNÜ ve KULLANIM YÖNÜNDE ÇİZİM (pf3_olcu: arac_cercevesi,
eksene_oturt, cizim_cercevesi, arac_yonu_oner, gorunus_adi).

Kullanıcı: "parça kesinlikle kullanım yönünde olmalı; araç yönü bizim için
önemli; ön panel baş aşağı konulmuş". Burada denetlenen:
  1. araç çerçevesi: önü -X, üstü +Z olan araçta model X -> çizim +Y,
     model Y -> çizim -X, Z -> Z (sağ el kuralı; ÖN görünüşün gözü -Y'de)
  2. eksende duran parçaya dokunulmaz (birim); 10° eğik parça en yakın
     eksene en küçük açıyla oturur (kutu eksenlere paralel olur), ters
     çevrilmez
  3. dik duran panel (kalınlık X boyunca, 1365 x 787) çizim çerçevesinde
     ÖN görünüşte büyük yüzüyle, üstü üstte: kalınlık çizim Y'sinde
  4. araç yönü önerisi: adında ÖN / ARKA geçen parçalardan
  5. SAĞ / SOL adları araç modunda takas; ayar imzası araç yönünü içerir
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox                 # noqa: E402
from OCP.gp import gp_Pnt, gp_Trsf, gp_Ax1, gp_Dir             # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform         # noqa: E402
import pf3_olcu as O                                            # noqa: E402
import pf7_is as IS                                             # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def kutu(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def dondur_z(sh, derece):
    tr = gp_Trsf()
    tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.radians(derece))
    return BRepBuilderAPI_Transform(sh, tr, True).Shape()


def main():
    print("1) araç çerçevesi")
    R = O.arac_cercevesi({"on": "-X", "ust": "+Z"})
    dogru("matris", R == [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], R)
    dogru("ön ile üst aynı eksen -> None", O.arac_cercevesi({"on": "+Z", "ust": "+Z"}) is None)
    dogru("yok / boş -> None", O.arac_cercevesi({"on": "yok"}) is None and O.arac_cercevesi(None) is None)
    R2 = O.arac_cercevesi({"on": "-Y", "ust": "+Z"})
    dogru("Pi3D'nin kendi çerçevesi (-Y önü) birimdir", R2 == O.BIRIM3, R2)

    print("2) eksene oturtma")
    duz = kutu(0, 0, 0, 200, 100, 3)
    dogru("eksende duran plaka: birim", O.eksene_oturt(duz) is O.BIRIM3)
    egik = dondur_z(duz, 10.0)
    R3 = O.eksene_oturt(egik)
    s3 = O.donustur(egik, R3)
    k = O.kutu(s3)
    L, W, T = k[3] - k[0], k[4] - k[1], k[5] - k[2]
    dogru("10° eğik plaka eksene oturdu (kutu 200 x 100 x 3)",
          abs(L - 200) < 0.05 and abs(W - 100) < 0.05 and abs(T - 3) < 0.01, (L, W, T))
    dogru("döndürme en küçük açıyla (ters çevrilmedi: det +1, X ekseni X'e yakın)",
          R3[0][0] > 0.98 and R3[2][2] > 0.999, R3)
    # 3° içindeki sapma: dokunulmaz
    az = dondur_z(duz, 1.5)
    dogru("1,5° sapma eksende sayılır (birim)", O.eksene_oturt(az) is O.BIRIM3)

    print("3) dik panel çizim çerçevesinde")
    panel = kutu(-1948, -1459, 397, 54, 1365, 787)      # Karluna UST_SAC gibi
    s, R = O.cizim_cercevesi(panel, {"on": "-X", "ust": "+Z"})
    k = O.kutu(s)
    dogru("kalınlık çizim Y'sinde (ÖN görünüş büyük yüzü gösterir)",
          abs((k[4] - k[1]) - 54) < 0.01 and abs((k[3] - k[0]) - 1365) < 0.01
          and abs((k[5] - k[2]) - 787) < 0.01, [round(v, 1) for v in k])
    dogru("orijine taşındı", all(abs(v) < 1e-6 for v in k[:3]))
    o_s, o = O.komponent_olcu(panel, {"yogunluk": 7.85e-6, "en_az_delik": 1.0,
                                      "arac": {"on": "-X", "ust": "+Z"}})
    dogru("BOM gabarisi kendi ekseninde: 1365 x 787 x 54",
          (o["boy_mm"], o["en_mm"], o["kalinlik_mm"]) == (1365.0, 787.0, 54.0),
          (o["boy_mm"], o["en_mm"], o["kalinlik_mm"]))
    # araç yönü yoksa model eksenleri olduğu gibi (yatırılmaz)
    s0, _ = O.cizim_cercevesi(panel, None)
    k0 = O.kutu(s0)
    dogru("araç yönü yokken model eksenleri: kalınlık X'te kalır",
          abs((k0[3] - k0[0]) - 54) < 0.01, [round(v, 1) for v in k0])

    print("4) araç yönü önerisi")
    kayit = [("a", kutu(-2000, -1500, 0, 100, 1400, 50)), ("b", kutu(-100, -1500, 0, 100, 1400, 50)),
             ("c", kutu(-1500, -1500, 0, 1000, 100, 50)), ("d", kutu(-1500, -200, 0, 1000, 100, 50))]
    komp = [{"ad": "TELEVRE_SACI_ON", "kod": "ON1", "sinif": "parca", "indeks": [0]},
            {"ad": "TELEVRE_SACI_ARKA", "kod": "AR1", "sinif": "parca", "indeks": [1]},
            {"ad": "KAPAK_SOL", "kod": "SOL1", "sinif": "parca", "indeks": [2]},
            {"ad": "KAPAK_SAG", "kod": "SAG1", "sinif": "parca", "indeks": [3]}]
    on = O.arac_yonu_oner(kayit, komp)
    dogru("ön = -X, üst = +Z (ÖN parça X'in küçük ucunda, SAĞ +Y'de)",
          on["on"] == "-X" and on["ust"] == "+Z", on)
    komp2 = [dict(k_, ad=k_["ad"].replace("_ON", "_X").replace("_ARKA", "_Y")) for k_ in komp]
    dogru("ad kanıtı yoksa 'yok'", O.arac_yonu_oner(kayit, komp2)["on"] == "yok")

    print("5) adlar ve ayar")
    O.ARAC_MODU["acik"] = True
    dogru("araç modunda SAG anahtarı SOL yazar", O.gorunus_adi("SAG") == "SOL" and O.gorunus_adi("SOL") == "SAĞ")
    O.ARAC_MODU["acik"] = False
    dogru("araç modu kapalı: SAĞ", O.gorunus_adi("SAG") == "SAĞ")
    a1 = IS.cizim_ayari({"gorunusler": ["ON"], "arac": {"on": "-X", "ust": "+Z"}})
    a2 = IS.cizim_ayari({"gorunusler": ["ON"], "arac": None})
    dogru("çizim ayarı araç yönünü taşır (eksik üretim yeniden çizer)",
          a1 != a2 and a1["arac"] == {"on": "-X", "ust": "+Z"} and a2["arac"] is None)
    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 0 if not HATA else 1


if __name__ == "__main__":
    sys.exit(main())
