# -*- coding: utf-8 -*-
"""Büküm yöntemi denetimi: abkant mı, rollform mu?

Karar fiziğe dayanır: abkantta parça bir V kalıbın ağzına oturur. Kanat
kalıbın ağzını tutamayacak kadar kısaysa parça kalıbın içine düşer;
iç yarıçap kalınlığın belli bir oranının altına inerse sac çatlar. Bu
betik, sınırın iki yanında doğru karar verildiğini ve sınırların
ayarlanabilir olduğunu doğrular.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as M                                          # noqa: E402

hata = []


def esit(ad, olan, beklenen):
    if olan != beklenen:
        hata.append(f"{ad}: {olan!r} bekleniyordu {beklenen!r}")
        print(f"  HATA  {ad}: {olan!r} != {beklenen!r}")
    else:
        print(f"  tamam {ad}: {olan!r}")


def yontem(t, kanatlar, yaricaplar, boy=500.0):
    return M.bukum_yontemi(t, kanatlar, yaricaplar, [1.57] * len(yaricaplar),
                           boy)["yontem"]


print("\n-- büküm yoksa")
esit("düz sac", yontem(3.0, [50.0], []), "düz sac")

print("\n-- rahat abkant parçası")
esit("kanat 9xt, r 1.4xt", yontem(2.5, [22.5, 60.0, 22.5], [3.5, 3.5]),
     "abkant")

print("\n-- kanat sınırı  (varsayılan 4 x kalınlık)")
esit("kanat 4.1xt geçer", yontem(3.0, [12.3, 90.0], [3.0]), "abkant")
esit("kanat 3.9xt geçmez", yontem(3.0, [11.7, 90.0], [3.0]), "rollform")

print("\n-- yarıçap sınırı  (varsayılan 0.6 x kalınlık)")
esit("r 0.7xt geçer", yontem(3.0, [40.0, 90.0], [2.1]), "abkant")
esit("r 0.5xt geçmez", yontem(3.0, [40.0, 90.0], [1.5]), "rollform")

print("\n-- gerçek parçalardan ölçülen değerler")
esit("01.051.000.01 (kanat 9.0xt, r 1.40xt)",
     yontem(2.5, [22.5, 75.0, 22.5], [3.5, 3.5, 3.5, 3.5], 2480), "abkant")
esit("09.025.000.02 Teleskop (kanat 0.27xt, r 0.50xt)",
     yontem(3.0, [0.81, 91.0, 0.81], [1.5] * 10, 1940), "rollform")
esit("01.050.000.01 U-Blech (kanat 0.84xt, r 0.17xt)",
     yontem(3.0, [2.51, 60.0], [0.5, 3.0] * 4, 483), "rollform")

print("\n-- geniş yarıçap silindir bükümüdür")
esit("r 25xt", yontem(2.0, [200.0, 200.0], [50.0]), "silindir bükümü")

print("\n-- sebep yazılıyor mu")
r = M.bukum_yontemi(3.0, [0.8, 90.0], [1.5], [1.57], 1940)
for kelime in ("kanat", "yarıçap", "0.8", "0.50"):
    if kelime not in r["neden"]:
        hata.append(f"sebepte '{kelime}' yok")
        print(f"  HATA  sebepte {kelime!r} geçmiyor: {r['neden'][:70]}")
    else:
        print(f"  tamam sebep {kelime!r} diyor")
esit("ölçü sonuçta var", r["en_kisa_kanat_t"], 0.27)

print("\n-- sınırlar ayarlanabiliyor mu")
eski = M.ayar_oku().get("abkant_en_az_kanat")
try:
    M.ayar_yaz(abkant_en_az_kanat=0.2)
    esit("gevşetilmiş sınırla abkant",
         yontem(3.0, [0.8, 90.0], [3.0]), "abkant")
finally:
    M.ayar_yaz(abkant_en_az_kanat=eski if eski else M.ABKANT_EN_AZ_KANAT)
esit("sınır geri alındı", yontem(3.0, [0.8, 90.0], [3.0]), "rollform")

print("\nSONUC:", "TUM DENETIMLER GECTI" if not hata
      else f"{len(hata)} HATA\n  " + "\n  ".join(hata))
sys.exit(1 if hata else 0)
