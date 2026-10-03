# -*- coding: utf-8 -*-
"""ÇİZGİ KALINLIĞI: ana gövde (GORUNEN) ölçü çizgisinden bir tık kalın.

Kullanıcı: "ana gövde çizgisi bir tık daha koyu ve kalın olsun, ölçü
çizgileriyle karışıyor". ISO 128 çizgi grubu kalın : ince = 2 : 1 →
GORUNEN 0,18 mm; OLCU, GIZLI, EKSEN, TARAMA, YAZI 0,09 mm. Lazer kesim
DXF'inin KESIM katmanı 0,09 kalır (kesim makinesi için çizgi kalınlığının
anlamı yok, eski haliyle kalsın).

    python test/cizgi_kalinlik_denetimi.py [DXF dosyaları...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                      # noqa: E402
import pf3_olcu as M                                              # noqa: E402

HATA = []


def denetle(ad, d):
    kal = {l.dxf.name: l.dxf.lineweight for l in d.layers}
    if kal.get("GORUNEN") != M.KONTUR_KAL or M.KONTUR_KAL <= M.CIZGI_KAL:
        HATA.append(f"{ad}: GORUNEN {kal.get('GORUNEN')} (beklenen {M.KONTUR_KAL} > {M.CIZGI_KAL})")
    for k in ("OLCU", "GIZLI", "EKSEN", "TARAMA", "YAZI"):
        if k in kal and kal[k] != M.CIZGI_KAL:
            HATA.append(f"{ad}: {k} {kal[k]} (beklenen {M.CIZGI_KAL})")
    if "KESIM" in kal and kal["KESIM"] != M.CIZGI_KAL:
        HATA.append(f"{ad}: KESIM {kal['KESIM']} (lazer, beklenen {M.CIZGI_KAL})")
    print(f"  {ad}: " + ", ".join(f"{k} {v}" for k, v in sorted(kal.items())
                                   if k in ("GORUNEN", "OLCU", "GIZLI", "EKSEN", "TARAMA", "YAZI", "KESIM")))


d = M.dxf_kur()
denetle("yeni çizim (dxf_kur)", d)
if M.KONTUR_KAL != 18 or M.CIZGI_KAL != 9:
    HATA.append(f"sabitler: KONTUR_KAL {M.KONTUR_KAL} / CIZGI_KAL {M.CIZGI_KAL} (beklenen 18 / 9)")
for y in sys.argv[1:]:
    try:
        denetle(os.path.basename(y), ezdxf.readfile(y))
    except Exception as ex:
        HATA.append(f"{y}: okunamadı {ex}")
if HATA:
    print("\nHATA:"); [print(" ", h) for h in HATA]
    sys.exit(1)
print("\nSONUC: cizgi kalinliklari dogru")
