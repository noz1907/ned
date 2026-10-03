# -*- coding: utf-8 -*-
"""AÇINIM ARAÇ YÖNÜNDE (kural 17; kullanıcı: "parçalar doğru yönde olacak;
ölçerek değil, araç konumunda hangi yöndeyse; alt ve üst karışmamalı;
arka görüntü aynı, sadece tersi olur").

Sentetik açınım sonucu (r) ile acinim_arac_yonu / acinim_cevir /
profil_araca_oturt sınanır (model gerekmez; R = çizim çerçevesine dönüşüm):
  1. Dikey panel, düzlemin +Y'si araçta AŞAĞI bakıyor -> Y çevrilir:
     kontur, delik, büküm yerleri, büküm sırası (B1 yine alt kenarda),
     profil etiket sırası (K1 yine alt kenardaki kanat) birlikte.
  2. Aynı panel +Y yukarı bakıyorsa dokunulmaz.
  3. Tavan sacı (yatay, küçük dikey dudaklı) ÜST görünüş gibi okunur,
     dudaklar onu dikey yapmaz.
  4. Büküm ekseni görünüşün sağına ters bakıyorsa X çevrilir (ayna).
  5. Profil resmi büküm ekseni yönünden bakan detay görünüşü gibi döner
     (eksen X -> SAĞ) ve "üstü üstte" kalır.

    python test/acinim_yon_denetimi.py
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as M                                              # noqa: E402

HATA = []
I3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


L, H = 1000.0, 300.0
taban = {
    "acinim_boy_mm": L, "acinim_genislik_mm": H, "kalinlik_mm": 2.0,
    "kontur_dis": [[(0, 0), (L, 0), (L, H), (0, H)]],
    "kontur_delik": [[(100, 250), (110, 250), (110, 260), (100, 260)]],   # üst kenara yakın delik
    "bukumler": [{"acinimda_bas_mm": 48.0, "acinimda_son_mm": 52.0, "aci_derece": 90.0, "r_ic": 2.0},
                 {"acinimda_bas_mm": 198.0, "acinimda_son_mm": 202.0, "aci_derece": 45.0, "r_ic": 2.0}],
    "profil": {"cizgi": [[(0, 0), (10, 0)]], "kanat": [((1, 0), (0, 1)), ((5, 0), (0, 1)), ((9, 0), (0, 1))],
               "bukum": [(2, 0), (7, 0)]},
}

# 1. dikey panel (normal Y), düzlem +Y araçta aşağı (-Z); büküm ekseni X
r = copy.deepcopy(taban)
r["duz_yon"] = {"x": (1, 0, 0), "px": (0, 1, 0), "py": (0, 0, 1),
                "duvar": [(250000.0, (0, 0, -1), (0, 1, 0)), (20000.0, (0, 1, 0), (0, 0, 1))]}
fx, fy, gad = M.acinim_arac_yonu(r, I3)
dogru("dikey panel aşağı bakıyor: Y çevrilir, X kalır, görünüş ÖN", (fx, fy, gad) == (False, True, "ON"),
      (fx, fy, gad))
M.acinim_cevir(r, fx, fy)
dogru("delik alta indi (y 250 -> 40..50)", min(p[1] for p in r["kontur_delik"][0]) == 40.0,
      r["kontur_delik"][0])
bk = r["bukumler"]
dogru("büküm yerleri çevrildi ve sıralı (B1 alt kenarda)",
      [(b["acinimda_bas_mm"], b["acinimda_son_mm"]) for b in bk] == [(98.0, 102.0), (248.0, 252.0)],
      [(b["acinimda_bas_mm"], b["acinimda_son_mm"]) for b in bk])
dogru("B1 artık 45° büküm (eski B2)", bk[0]["aci_derece"] == 45.0)
dogru("profil kanat sırası ters (K1 alt kenardaki kanat)",
      [p for p, _n in r["profil"]["kanat"]] == [(9, 0), (5, 0), (1, 0)], r["profil"]["kanat"])
dogru("abkant kanat ölçüleri yeni sırayla", len(M.kanat_dis_olculeri(r)) == 3)

# 2. aynı panel yukarı bakıyor: dokunulmaz
r2 = copy.deepcopy(taban)
r2["duz_yon"] = {"x": (1, 0, 0), "px": (0, 1, 0), "py": (0, 0, 1),
                 "duvar": [(250000.0, (0, 0, 1), (0, 1, 0))]}
dogru("yukarı bakan panel çevrilmez", M.acinim_arac_yonu(r2, I3)[:2] == (False, False))

# 3. tavan sacı: büyük yatay duvarlar + küçük dikey dudaklar (dudak aşağı bakıyor)
r3 = copy.deepcopy(taban)
r3["duz_yon"] = {"x": (1, 0, 0), "px": (0, 1, 0), "py": (0, 0, 1),
                 "duvar": [(400000.0, (0, 1, 0), (0, 0, 1)), (30000.0, (0, 0, -1), (0, 1, 0)),
                           (30000.0, (0, 0, -1), (0, -1, 0))]}
fx, fy, gad = M.acinim_arac_yonu(r3, I3)
dogru("tavan sacı ÜST görünüş gibi, dudaklar yüzünden çevrilmez", (fx, fy, gad) == (False, False, "UST"),
      (fx, fy, gad))

# 4. büküm ekseni -X: ayna (X çevrilir)
r4 = copy.deepcopy(taban)
r4["duz_yon"] = {"x": (-1, 0, 0), "px": (0, 1, 0), "py": (0, 0, 1),
                 "duvar": [(250000.0, (0, 0, 1), (0, 1, 0))]}
fx, fy, gad = M.acinim_arac_yonu(r4, I3)
dogru("eksen görünüşün sağına ters: X çevrilir", (fx, fy) == (True, False), (fx, fy))
M.acinim_cevir(r4, fx, fy)
dogru("X aynası: delik sağa geçti", max(p[0] for p in r4["kontur_delik"][0]) == 900.0, r4["kontur_delik"][0])

# 5. profil: eksen X -> SAĞ görünüş; profil 2B'sinin +y'si araçta yukarı (Z)
r5 = copy.deepcopy(taban)
r5["duz_yon"] = {"x": (1, 0, 0), "px": (0, 1, 0), "py": (0, 0, 1), "duvar": [(1.0, (0, 0, 1), (0, 1, 0))]}
r5["profil"] = {"cizgi": [[(0, 0), (0, 70)], [(0, 70), (89, 70)]], "kanat": [((0, 35), (-1, 0))],
                "bukum": [(0, 70)]}
M.profil_araca_oturt(r5, I3)
pr = r5["profil"]
dogru("profil SAĞ görünüş gibi", pr.get("gorunus") == "SAG", pr.get("gorunus"))
dogru("profilde dik kanat yine dik ve üstte yatay kanat (üstü üstte)",
      pr["cizgi"][0] == [(0, 0), (0, 70)] and pr["cizgi"][1][1][1] == 70, pr["cizgi"])
# aynı profil ama 2B +y'si araçta aşağı: dönünce yine üstü üstte
r6 = copy.deepcopy(r5)
r6["profil"] = {"cizgi": [[(0, 0), (0, 70)]], "kanat": [], "bukum": []}
r6["duz_yon"] = dict(r5["duz_yon"], py=(0, 0, -1))
M.profil_araca_oturt(r6, I3)
dogru("2B +y aşağı bakıyorsa profil ters çevrilir", r6["profil"]["cizgi"][0] == [(0, 0), (0, -70)],
      r6["profil"]["cizgi"])

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
