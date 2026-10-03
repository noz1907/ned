# -*- coding: utf-8 -*-
"""AÇINIM PAFTASI: çok küçültme gereken resimde sayfa düzeni (kullanıcı:
"1. sayfa ön resim + tablo (seçilirse) + yan görünüş sağ ya da sol;
ölçüsüz resim ya da kalan görünüm 2. sayfa; her paftada, PDF'te ve DXF'te;
resimler A3'ün antet ve kenar dışındaki alanını en çok kaplar; 2. sayfa
ilk sayfayla aynı boyda").

Sentetik büyük bükümlü sac (1400 x 900, 14 büküm, büyük profil):
  - açınım DXF'inde bölüm işaretleri var (ON, TABLO, PROFIL, IZOMETRIK,
    BASLIK, OLCUSUZ),
  - pafta iki sayfa: 1. sayfada ölçülü açınım + tablo + profil, ölçüsüz
    açınım 1. sayfada YOK; 2. sayfada ölçüsüz açınım var,
  - iki sayfa aynı kâğıt boyunda,
  - tablo penceresi kendi ölçeğinde: tablo yazısı kâğıtta ana resmin
    yazısından büyük ve en az 2 mm,
  - tablo kapalıyken tablo bölümü yok.

    python test/acinim_pafta_denetimi.py
"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                      # noqa: E402
import pf3_olcu as M                                              # noqa: E402
import pf4_pafta as PF                                            # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def daire(cx, cy, r=4.0, n=16):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


boy, gen = 1400.0, 900.0
nb = 14
bk = [{"acinimda_bas_mm": 60.0 * (i + 1) - 2, "acinimda_son_mm": 60.0 * (i + 1) + 2,
       "aci_derece": 90.0 if i % 3 == 0 else 45.0, "r_ic": 2.0, "pay_mm": 4.0} for i in range(nb)]
# profil: büküm ekseni yönünden zikzak, ~ 800 mm boy
pc = [(0.0, 0.0)]
for i in range(nb + 1):
    pc.append((pc[-1][0] + (40.0 if i % 2 else 0.0), pc[-1][1] + 55.0))
profil = {"cizgi": [pc], "kanat": [(((pc[i][0] + pc[i + 1][0]) / 2, (pc[i][1] + pc[i + 1][1]) / 2), (1.0, 0.0))
                                   for i in range(len(pc) - 1)],
          "bukum": [pc[i] for i in range(1, len(pc) - 1)]}
r = {"acinim_genislik_mm": gen, "acinim_boy_mm": boy, "kalinlik_mm": 1.5,
     "kontur_dis": [[(0, 0), (boy, 0), (boy, gen), (0, gen)]],
     "kontur_delik": [daire(x, y) for x, y in ((40, 40), (40, 860), (1360, 40), (1360, 860), (700, 450))],
     "bukumler": bk, "bukum_sayisi": nb, "k_faktor": 0.4, "profil": profil,
     "izo": [[(0, 0), (700, 400)], [(700, 400), (700, 900)], [(0, 0), (0, 500)]]}
kl = tempfile.mkdtemp(prefix="pi3d_acp_")
yol = os.path.join(kl, "P01_SAC_acinim.dxf")
M.dxf_acilim(r, {"kod": "SAC", "ad": "SAC", "adet": 1, "poz": 1}, yol, {"acinim_tablo": True})
al = PF.gorunus_alanlari(ezdxf.readfile(yol))
dogru("bölüm işaretleri var", {"ON", "TABLO ACINIM", "PROFIL", "IZOMETRIK", "BASLIK", "OLCUSUZ"} <= set(al),
      sorted(al))
sonuc = PF.pafta_kur(yol, None, "A3")
d = ezdxf.readfile(yol)
sayfalar = [ly for ly in d.layouts if ly.name != "Model"]
adlar = sorted(ly.name for ly in sayfalar)
dogru("iki sayfa (PAFTA, PAFTA_2)", len(sayfalar) >= 2, adlar)


def pencereler(ly):
    out = []
    for v in ly.query("VIEWPORT"):
        if v.dxf.id == 1:
            continue                      # kâğıt uzayının kendi penceresi
        c = v.dxf.view_center_point
        olcek = float(v.dxf.height) / float(v.dxf.view_height) if v.dxf.view_height else 0.0
        out.append(((c[0], c[1]), olcek))
    return out


def icinde(p, k):
    return k[0] - 1e-3 <= p[0] <= k[2] + 1e-3 and k[1] - 1e-3 <= p[1] <= k[3] + 1e-3


s1 = next((ly for ly in sayfalar if ly.name == "PAFTA"), sayfalar[0])
s2 = [ly for ly in sayfalar if ly is not s1]
p1 = pencereler(s1)
p2 = [p for ly in s2 for p in pencereler(ly)]
bolum1 = {a for a in al for c, _o in p1 if icinde(c, al[a])}
bolum2 = {a for a in al for c, _o in p2 if icinde(c, al[a])}
dogru("1. sayfada ölçülü açınım, tablo ve profil", {"ON", "TABLO ACINIM", "PROFIL"} <= bolum1, sorted(bolum1))
dogru("ölçüsüz açınım 1. sayfada yok", "OLCUSUZ" not in bolum1, sorted(bolum1))
dogru("2. sayfada ölçüsüz açınım", "OLCUSUZ" in bolum2, sorted(bolum2))
ks = {tuple(round(v) for v in ly.get_paper_limits()[1]) for ly in sayfalar}
dogru("sayfalar aynı kâğıt boyunda", len(ks) == 1, ks)
o_on = next((o for c, o in p1 if icinde(c, al["ON"])), 0.0)
o_tb = next((o for c, o in p1 if icinde(c, al["TABLO ACINIM"])), 0.0)
h = min(12.0, max(2.0, min(gen, boy) / 30.0))
dogru("tablo kendi ölçeğinde (ana resimden büyük)", o_tb > o_on + 1e-9, (o_tb, o_on))
dogru("tablo yazısı kâğıtta en az 2 mm", h * o_tb >= 2.0 - 1e-6, round(h * o_tb, 2))
# tablo kapalı: tablo bölümü yok
y2 = os.path.join(kl, "P02_SAC_acinim.dxf")
M.dxf_acilim(r, {"kod": "SAC", "ad": "SAC", "adet": 1, "poz": 2}, y2, {"acinim_tablo": False})
dogru("tablo kapalıyken tablo bölümü yok", "TABLO ACINIM" not in PF.gorunus_alanlari(ezdxf.readfile(y2)))
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
