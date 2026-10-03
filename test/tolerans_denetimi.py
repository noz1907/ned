# -*- coding: utf-8 -*-
"""TOLERANS MOTORU (CLAUDE.md 26, OLCULENDIRME 11).

Kullanıcı tablosu: boy referanstan uzaklığa göre merdiven (CNC <= 1 m 0,3;
<= 1,5 m 0,5; üstü 0,8 toplam; konvansiyonel +0,15); pres delik konumu
0,4; abkant 1; rollform 0,8; delik çapı 0,4; iç kesim 0,6; açı 1° (ince
sacda 1,5°). ISO 2768 sınıfı seçilirse ISO tablosu. Denetim: bantlar;
süreç tahmini (bükümlü sac -> lazer + abkant, talaşlı -> CNC); sentetik
çizimde ölçülere tolerans atanması, zincir birikimi uyarısı, parça bazlı
özel toleransın resme "±" olarak yazılması.

    python test/tolerans_denetimi.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as M                                              # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


B = M.tolerans_bandi
dogru("CNC 800 mm -> 0,3", B("boy", "cnc", 800) == 0.3, B("boy", "cnc", 800))
dogru("CNC 1200 mm -> 0,5", B("boy", "cnc", 1200) == 0.5)
dogru("CNC 3000 mm -> 0,8", B("boy", "cnc", 3000) == 0.8)
dogru("konvansiyonel 800 -> 0,45", abs(B("boy", "konvansiyonel", 800) - 0.45) < 1e-9)
dogru("pres delik konumu 0,4", B("konum", "pres", 1500) == 0.4)
dogru("abkant kanat 1", B("konum", "abkant", 100) == 1.0)
dogru("rollform 0,8", B("konum", "rollform", 100) == 0.8)
dogru("lazer boy 2 m -> 1,5", B("boy", "lazer", 2000) == 1.5)
dogru("delik çapı 0,4", B("delik_cap", "lazer") == 0.4)
dogru("iç kesim 0,6", B("ic_kesim", "lazer") == 0.6)
dogru("açı 1° (t 2)", B("aci", "abkant", 100, t=2.0) == 1.0)
dogru("açı 1,5° (t 1)", B("aci", "abkant", 100, t=1.0) == 1.5)
dogru("ISO 2768-m 500 mm -> ±0,8 (bant 1,6)", B("boy", "cnc", 500, sinif="iso2768-m") == 1.6)
dogru("ISO 2768-f 50 mm -> ±0,15 (bant 0,3)", B("boy", "cnc", 50, sinif="iso2768-f") == 0.3)

s = M.surec_tahmini({"sac_kalinlik_mm": 1.5}, {"tip": "bükümlü sac"}, True, {})
dogru("bükümlü sac: kesim lazer, konum pres, kanat abkant",
      (s["boy"], s["konum"], s["kanat"]) == ("lazer", "pres", "abkant"), s)
s = M.surec_tahmini({}, {"tip": ""}, False, {})
dogru("talaşlı: CNC", s["boy"] == "cnc", s)

# sentetik çizim: 3 halkalı zincir + gabari, pres
h = 10.0
doc = M.dxf_kur(); msp = doc.modelspace(); M.olcu_stili(doc, h)
gk = {"ON": (0.0, 0.0, 1800.0, 500.0)}
kay = {"ON": (0.0, 0.0)}


def lin(p1, p2, base):
    d = msp.add_linear_dim(base=base, p1=p1, p2=p2, dimstyle=M.OLCU_STILI, dxfattribs={"layer": "OLCU"})
    d.render()


lin((0, 500), (400, 500), (0, 530))
lin((400, 500), (900, 500), (0, 530))
lin((900, 500), (1600, 500), (0, 530))
lin((0, 0), (1800, 0), (0, -40))                     # gabari
o = {"boy_mm": 1800.0, "en_mm": 500.0, "kalinlik_mm": 2.0, "sac_kalinlik_mm": 2.0}
k = {"tip": "düz sac", "kod": "T"}
kplan = {"ON": {"datum": {"yatay": 0.0, "dusey": 0.0}}}
liste, notlar, uyari = M.tolerans_isle(msp, o, k, {}, gk, kay, [], kplan, h, {}, False)
print("   ", [(x["tur"], x["deger"], x["bant"], x.get("birikim")) for x in liste])
dogru("4 ölçüye tolerans atandı", len(liste) == 4, len(liste))
gab = [x for x in liste if x["tur"] == "gabari"]
dogru("gabari 1800: lazer boy 1,5 bant", gab and gab[0]["bant"] == 1.5, gab)
zin = sorted([x for x in liste if x["tur"] == "konum"], key=lambda x: x["uclar"][0])
dogru("zincirde son halkanın birikimi 3 x 0,4 = 1,2", zin and abs(zin[-1].get("birikim", 0) - 1.2) < 1e-6,
      [x.get("birikim") for x in zin])
dogru("birikim uyarısı (> 0,4)", uyari >= 1 and zin[-1].get("uyari"), uyari)
dogru("genel tolerans notu", notlar and notlar[0].startswith("GENEL TOLERANS"), notlar)

# parça bazlı özel ±: zincirin ilk halkası ±0,1
kim = zin[0]["id"]
doc2 = M.dxf_kur(); msp2 = doc2.modelspace(); M.olcu_stili(doc2, h)
msp = msp2
lin((0, 500), (400, 500), (0, 530))
lin((400, 500), (900, 500), (0, 530))
liste2, _n, _u = M.tolerans_isle(msp2, o, k, {"tolerans": {"olcu": {kim: 0.1}}}, gk, kay, [], kplan, h, {}, False)
oz = [x for x in liste2 if x["ozel"]]
dogru("özel tolerans atandı (±0,1)", oz and oz[0]["tol"] == 0.1, oz)
n = M.tolerans_etiketleri(msp2, liste2, h)
yazi = [e.dxf.text for e in msp2.query("TEXT") if e.dxf.text.startswith("±")]
dogru("resme ±0,1 yazıldı", n == 1 and "±0,1" in yazi, (n, yazi))
liste3, n3, _ = M.tolerans_isle(msp2, o, k, {"tolerans": {"sinif": "iso2768-m"}}, gk, kay, [], kplan, h, {}, False)
dogru("ISO sınıfı notu", "ISO" in n3[0].upper(), n3)

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
