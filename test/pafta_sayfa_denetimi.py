# -*- coding: utf-8 -*-
"""ANTETTE SAYFA "n / toplam" (kullanıcı: "1-2 ya da daha çok sayfaysa
antette 1/2 gibi sayfa kısmı var, değil mi"). Sentetik belge: PAFTA ve
PAFTA_2 sayfalarında "sayfa 1" / "sayfa 2" yazıları; _sayfa_sayisini_yaz
sonrası "sayfa 1 / 2" ve "sayfa 2 / 2"; başka yazı değişmez; ikinci
çağrı yeniden eklemez.

    python test/pafta_sayfa_denetimi.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                      # noqa: E402
import pf4_pafta as PF                                            # noqa: E402

HATA = []
d = ezdxf.new()
p1 = d.layouts.new("PAFTA"); p2 = d.layouts.new("PAFTA_2"); baska = d.layouts.new("KAYNAK")
p1.add_text("A3 yatay  ·  sayfa 1")
p1.add_text("A3 yatay  ÖLÇEK 1:7")
p2.add_text("A3 yatay  sayfa 2  ÖLÇEK 1:8")
p2.add_mtext("A3 yatay  ·  sayfa 2")
baska.add_text("sayfa 1")
n = PF._sayfa_sayisini_yaz(d, "PAFTA", 2)
m1 = [e.dxf.text for e in p1.query("TEXT")]
m2 = [e.dxf.text for e in p2.query("TEXT")] + [e.text for e in p2.query("MTEXT")]
print(n, m1, m2)
if n != 3:
    HATA.append(f"3 yazı değişmeliydi, {n} değişti")
if "A3 yatay  ·  sayfa 1 / 2" not in m1 or "A3 yatay  ÖLÇEK 1:7" not in m1:
    HATA.append(f"1. sayfa yanlış: {m1}")
if "A3 yatay  sayfa 2 / 2  ÖLÇEK 1:8" not in m2 or "A3 yatay  ·  sayfa 2 / 2" not in m2:
    HATA.append(f"2. sayfa yanlış: {m2}")
if [e.dxf.text for e in baska.query("TEXT")] != ["sayfa 1"]:
    HATA.append("pafta dışı sayfa değiştirildi")
if PF._sayfa_sayisini_yaz(d, "PAFTA", 2) != 0:
    HATA.append("ikinci çağrı yeniden değiştirdi")
if HATA:
    print("\nHATA:"); [print(" ", h) for h in HATA]
    sys.exit(1)
print("\nSONUC: sayfa numarasi dogru")
