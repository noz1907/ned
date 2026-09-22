# -*- coding: utf-8 -*-
"""Acinim dogru mu? Iki bagimsiz olcuyle denetlenir:

  1) Duzlemdeki alan x sac kalinligi == parcanin gercek hacmi
     (bukum payinin K-faktorunden gelen kucuk farki hesaba katilarak).
     Bu, acma haritasinin dogrulugunu olcer: bir duvar eksik kalirsa
     alan kucuk, bir parca iki kere binerse buyuk cikar.

  2) Kesitten cikan acinim genisligi == yuzeyden acilan konturun
     genisligi. Iki ayri yontem, ayni sayiyi vermek zorunda.

Kullanim:  python test/acilim_capraz_denetim.py model.stp
"""
import os, sys, math, traceback

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import pf3_olcu as M

if len(sys.argv) < 2:
    print("kullanim: python test/acilim_capraz_denetim.py <model.stp>")
    sys.exit(2)
step = sys.argv[1]
kayit, komp, agac = M.step_komponentleri(step, {}, log=lambda *a, **k: None)
print(f"{len(komp)} komponent\n")
print(f"{'kod / ad':32s} {'kalinlik':>8s} {'acinim G x B':>20s} {'buk':>4s} "
      f"{'delik':>6s} {'kontur':>7s} {'hacim farki':>12s}")
print("-" * 100)
say = {"kesim": 0, "blank": 0, "yok": 0}
for k in komp:
    sh = kayit[k["indeks"][0]][1]
    ad = (k.get("kod") or k.get("ad") or "?")[:32]
    try:
        r = M.sac_acilim(sh, k)
    except M.AcilimYok as e:
        say["yok"] += 1
        print(f"{ad:32s}   -> {str(e).splitlines()[0][:60]}")
        continue
    except Exception as e:
        say["yok"] += 1
        print(f"{ad:32s}   !! {type(e).__name__}: {str(e)[:52]}")
        continue
    kesim = bool(r.get("kontur_dis"))
    say["kesim" if kesim else "blank"] += 1
    if kesim:
        hac = r["acinim_alan_mm2"] * r["kalinlik_mm"]
        fark = f"{100 * (hac - k['hacim_mm3']) / k['hacim_mm3']:+6.2f}%"
    else:
        fark = "    -"
    print(f"{ad:32s} {r['kalinlik_mm']:8.2f} "
          f"{r['acinim_genislik_mm']:9.2f} x{r['acinim_boy_mm']:8.1f} "
          f"{r['bukum_sayisi']:4d} {r.get('delik_adedi', 0):6d} "
          f"{'KESIM' if kesim else 'blank':>7s} {fark:>12s}")
    if not kesim and r.get("kontur_notu"):
        print(f"{'':34s}{r['kontur_notu'][:64]}")
print(f"\n{say['kesim']} parca kesim konturuyla, {say['blank']} parca yalniz "
      f"blank olcusuyle, {say['yok']} parca acilamadi.")
print("Kesim konturu verilen parcalarda hacim farki %3'un altinda olmali;")
print("ustunde olsaydi program konturu zaten vermezdi.")
