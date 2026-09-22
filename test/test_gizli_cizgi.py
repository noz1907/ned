# -*- coding: utf-8 -*-
"""gorunus_ciz'in gizli-cizgi elemesi: gorunenle cakisan gizli parca
cizilmemeli, cakismayan bolum cizilmeli."""
import os, sys, math, ezdxf
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as M

e = 1e-15
def dene(ad, gorunen, gizli, bekle):
    d = ezdxf.new("R2010", setup=False); M.dxf_kur(d); msp = d.modelspace()
    M.gorunus_ciz(msp, {"GORUNEN": gorunen, "GIZLI": gizli}, 0, 0, "ON",
                  olcu2=False)
    kalan = []
    for p in msp.query("LWPOLYLINE"):
        if p.dxf.layer != "GIZLI": continue
        n = [(x, y) for x, y, *_ in p.get_points()]
        kalan.append(sum(math.dist(n[i], n[i+1]) for i in range(len(n)-1)))
    top = round(sum(kalan), 2)
    ok = "TAMAM" if abs(top - bekle) < 0.06 else "HATA "
    print(f"{ok} {ad:52s} kalan gizli uzunluk {top:7.2f}  beklenen {bekle:7.2f}")
    return ok == "TAMAM"

t = []
# 1) Tam dikey kenar, gizli ters yonde ve x'te 1e-15 gurultulu: tamamen elenmeli
t.append(dene("dikey kenar, gizli ters yonde ornekli",
              [[(5.0, 0.0), (5.0 + e, 38.0)]],
              [[(5.0, 38.0), (5.0 - e, 0.0)]], 0.0))
# 2) Ayni ama gurultu diger isaretle
t.append(dene("dikey kenar, gurultu ters isaretli",
              [[(5.0, 0.0), (5.0 - e, 38.0)]],
              [[(5.0, 38.0), (5.0 + e, 0.0)]], 0.0))
# 3) Tam yatay kenar
t.append(dene("yatay kenar, gizli ters yonde ornekli",
              [[(0.0, 7.0), (40.0, 7.0 + e)]],
              [[(40.0, 7.0), (0.0, 7.0 - e)]], 0.0))
# 4) Egik kenar
t.append(dene("egik kenar (37 derece)",
              [[(0.0, 0.0), (40.0, 30.0)]],
              [[(40.0, 30.0), (0.0, 0.0)]], 0.0))
# 5) Gizli daha uzun: yalniz cakisan bolum kesilmeli, 10 mm kalmali
t.append(dene("gizli daha uzun, yalniz cakisan bolum kesilir",
              [[(5.0, 0.0), (5.0, 30.0)]],
              [[(5.0, 0.0), (5.0, 40.0)]], 10.0))
# 6) Gizli ortadan cakisiyor: iki ucu da kalmali (5 + 5)
t.append(dene("gizli ortadan cakisiyor, iki uc kalir",
              [[(5.0, 10.0), (5.0, 30.0)]],
              [[(5.0, 5.0), (5.0, 35.0)]], 10.0))
# 7) Farkli doguda gercek gizli cizgi: dokunulmamali
t.append(dene("ayri yerdeki gercek gizli cizgi korunur",
              [[(5.0, 0.0), (5.0, 30.0)]],
              [[(12.0, 0.0), (12.0, 30.0)]], 30.0))
# 8) 0.12 mm'den az kaymis: ayni doğru sayilir, elenir
t.append(dene("0.05 mm kaymis gizli, ayni dogru sayilir",
              [[(5.0, 0.0), (5.0, 30.0)]],
              [[(5.05, 0.0), (5.05, 30.0)]], 0.0))
# 9) 0.5 mm kaymis: ayri cizgi, korunur
t.append(dene("0.5 mm kaymis gizli, ayri cizgi korunur",
              [[(5.0, 0.0), (5.0, 30.0)]],
              [[(5.5, 0.0), (5.5, 30.0)]], 30.0))
# 10) Cok parcali gorunen kenar tek uzun gizliyi tamamen ortmeli
t.append(dene("parca parca gorunen, tek uzun gizliyi tumden orter",
              [[(5.0, y), (5.0, y + 3.0)] for y in range(0, 30, 3)],
              [[(5.0, 30.0), (5.0, 0.0)]], 0.0))
# 11) Parca orijinden 4000 mm uzakta: olculer parcanin kendi arasinda
#     alinmazsa yarim derecelik ornekleme farki dik uzakligi kaydirir
U = 4000.0
t.append(dene("orijinden 4 m uzakta, hafif egik kenar",
              [[(U + 0.0, U + 0.0), (U + 0.5, U + 30.0)]],
              [[(U + 0.5, U + 30.0), (U + 0.0, U + 0.0)]], 0.0))
# 12) Ayni uzaklikta, kenar iki tarafta farkli noktalanmis
t.append(dene("orijinden uzakta, farkli noktalanmis kenar",
              [[(U, U), (U + 0.25, U + 15.0), (U + 0.5, U + 30.0)]],
              [[(U + 0.5, U + 30.0), (U + 0.1, U + 6.0), (U, U)]], 0.0))
print("\nSONUC:", "hepsi tamam" if all(t) else "BASARISIZ")
sys.exit(0 if all(t) else 1)
