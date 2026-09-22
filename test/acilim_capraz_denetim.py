# -*- coding: utf-8 -*-
"""Acinim hesabi: her bukumlu parca icin bagimsiz hacim capraz denetimi.
   acinim alani x kalinlik  ==  parcanin hacmi + deliklerin hacmi
   Delikleri bilmedigimiz icin acinim hacmi >= parca hacmi olmali ve
   fark, deliklerin makul payini asmamali."""
import os, sys, math, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as M

if len(sys.argv) < 2:
    print("kullanim: python test/acilim_capraz_denetim.py <model.stp>")
    sys.exit(2)
step = sys.argv[1]
kayit, komp, agac = M.step_komponentleri(step, {}, log=lambda *a, **k: None)
print(f"{len(komp)} komponent\n")
bas = ("kod/ad", "kalinlik", "acinim GxB", "bukum", "acinim hacim",
       "parca hacim", "fark")
print(f"{bas[0]:34s} {bas[1]:>8s} {bas[2]:>20s} {bas[3]:>5s} "
      f"{bas[4]:>12s} {bas[5]:>12s} {bas[6]:>8s}")
print("-" * 110)
for k in komp:
    sh = kayit[k["indeks"][0]][1]
    ad = (k.get("kod") or k.get("ad") or "?")[:34]
    try:
        r = M.sac_acilim(sh)
    except M.AcilimYok as e:
        print(f"{ad:34s}   -> {str(e).splitlines()[0][:66]}")
        continue
    except Exception as e:
        print(f"{ad:34s}   !! {type(e).__name__}: {str(e)[:56]}")
        continue
    hac = r["acinim_genislik_mm"] * r["acinim_boy_mm"] * r["kalinlik_mm"]
    gercek = k["hacim_mm3"]
    fark = 100.0 * (hac - gercek) / gercek
    isaret = "" if -3 <= fark < 30 else "  <-- BAK"
    print(f"{ad:34s} {r['kalinlik_mm']:8.2f} "
          f"{r['acinim_genislik_mm']:9.2f} x{r['acinim_boy_mm']:8.1f} "
          f"{r['bukum_sayisi']:5d} {hac:12.0f} {gercek:12.0f} "
          f"{fark:+7.1f}%{isaret}")
