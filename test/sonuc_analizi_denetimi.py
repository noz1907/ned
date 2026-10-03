# -*- coding: utf-8 -*-
"""SONUÇ ANALİZİ DÖNGÜSÜ (CLAUDE.md 25): çizim kâğıt ölçeğinde ölçülür,
sorun varsa kurala göre yeniden çizilir, en iyi tur dosyada kalır.

Sahte çizim fonksiyonu: yazı boyu çarpanı (yazi_kat) arttıkça kâğıttaki
rakam büyür. Denetim: 1) rakam küçükken döngü yeniden çizer ve kararı
yazar; 2) sorunsuz turda durur; 3) kazanç yoksa boşa tur atmaz; 4) en
iyi tur dosyaya geri konur; 5) pafta_kur(yalniz_plan=True) dosyaya
yazmaz.

    python test/sonuc_analizi_denetimi.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as M                                              # noqa: E402
import pf4_pafta as PF                                            # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


kl = tempfile.mkdtemp(prefix="pi3d_sa_")
yol = os.path.join(kl, "t.dxf")
cizilen = []


def ciz_(P):
    """Kâğıtta rakam = 2,0 * yazi_kat mm olsun diye sahte ölçüm."""
    cizilen.append(round(float(P.get("yazi_kat") or 1.0), 3))
    with open(yol, "w") as f:
        f.write(str(cizilen[-1]))
    M.SON_RAPOR["yazi_h"] = 10.0
    M.SON_RAPOR["detay_sayisi"] = 0


def olcum_rakam(fn):
    def f(dxf_yol, kagit, h):
        kat = float(open(dxf_yol).read())
        return {"olcek": 0.2, "olcek_metni": "1:5", "kagit": "A3", "yazi_mm": round(fn(kat), 2),
                "en_kucuk_yazi_mm": 1.5, "yigilma": 0, "sayfa2": False, "dagitildi": True}
    return f


# 1) rakam 2,0 -> büyütülür, ikinci turda 2,5'i geçer
ciz_({})
M.kagit_olcumu = olcum_rakam(lambda kat: 2.0 * kat)
tur = M.sonuc_analizi_dongusu(ciz_, yol, {}, log=lambda *_: None)
dogru("küçük rakam: 2 tur, 2. tur kabul", len(tur) == 2 and tur[-1]["karar"] == "kabul", tur)
dogru("1. tur kararı yazı büyütme", "yeniden çiz" in tur[0]["karar"], tur[0])
dogru("dosyada son (kabul) tur", float(open(yol).read()) == cizilen[-1])

# 2) baştan sorunsuz: tek tur
cizilen.clear(); ciz_({})
M.kagit_olcumu = olcum_rakam(lambda kat: 3.0)
tur = M.sonuc_analizi_dongusu(ciz_, yol, {}, log=lambda *_: None)
dogru("sorunsuz: tek tur, yeniden çizim yok", len(tur) == 1 and len(cizilen) == 1, (tur, cizilen))

# 3) büyütmek kazandırmıyor (ölçek düşüyor): 2. turda durur, 1. tur geri konur
cizilen.clear(); ciz_({})
M.kagit_olcumu = olcum_rakam(lambda kat: 2.2 / kat)
tur = M.sonuc_analizi_dongusu(ciz_, yol, {}, log=lambda *_: None)
dogru("kazanç yok: 2 turda durdu", len(tur) == 2 and "kazandırmadı" in tur[-1]["karar"], tur)
dogru("en iyi tur (1.) seçildi ve dosyaya geri kondu",
      tur[0].get("secildi") and float(open(yol).read()) == cizilen[0], (tur, open(yol).read()))
dogru("geçici kopyalar silindi", not [a for a in os.listdir(kl) if ".tur" in a], os.listdir(kl))

# 4) kuru pafta: dosyaya yazmaz
import ezdxf                                                      # noqa: E402
d = ezdxf.new(); msp = d.modelspace()
msp.add_lwpolyline([(0, 0), (500, 0), (500, 300), (0, 300)], close=True)
msp.add_text("12,5", dxfattribs={"height": 5.0}).set_placement((10, 10))
y2 = os.path.join(kl, "kuru.dxf"); d.saveas(y2)
once = os.path.getmtime(y2), os.path.getsize(y2)
r = PF.pafta_kur(y2, None, "A3", yalniz_plan=True)
dogru("kuru pafta: ölçek ve kâğıt yazısı döndü", r.get("olcek") and "yazi_mm" in r, r)
dogru("kuru pafta: dosya değişmedi", (os.path.getmtime(y2), os.path.getsize(y2)) == once)
dogru("kuru pafta: PAFTA sekmesi açılmadı", "PAFTA" not in ezdxf.readfile(y2).layout_names())

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
