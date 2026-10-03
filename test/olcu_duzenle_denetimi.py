# -*- coding: utf-8 -*-
"""ÖLÇÜ DÜZENLEME (model gerekmez): numaralı ölçüler, tolerans değiştir /
sil (referans ölçü), genele dön, ölçüyü sil; değer DEĞİŞMEZ.

Sentetik resim: 3 ölçü tolerans_isle ile numaralanır, DXF'e yazılır.
Denetim: olcu_listesi numaraları okur; olcu_duzenle 1 numaraya ±0,1
(resme "±0,1" etiketi), 2 numaranın toleransını siler (rakam "(...)"),
3 numarayı siler (ölçü ve kılavuzu gider); değerler aynı kalır; kimlikle
kalıcı kayıt döner; yeniden çizimde (tolerans_isle) aynı kayıt uygulanır;
genele dönünce etiket / parantez kalkar.

    python test/olcu_duzenle_denetimi.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                      # noqa: E402
import pf3_olcu as M                                              # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


h = 10.0
gk = {"ON": (0.0, 0.0, 1800.0, 500.0)}
kay = {"ON": (0.0, 0.0)}
o = {"boy_mm": 1800.0, "en_mm": 500.0, "kalinlik_mm": 2.0, "sac_kalinlik_mm": 2.0}
k = {"tip": "düz sac", "kod": "T"}
kplan = {"ON": {"datum": {"yatay": 0.0, "dusey": 0.0}}}


def resim(P):
    doc = M.dxf_kur(); msp = doc.modelspace(); M.olcu_stili(doc, h)
    msp.add_lwpolyline([(0, 0), (1800, 0), (1800, 500), (0, 500)], close=True, dxfattribs={"layer": "GORUNEN"})
    for p1, p2, base in (((0, 500), (400, 500), (0, 530)), ((400, 500), (900, 500), (0, 530)),
                         ((0, 0), (1800, 0), (0, -40))):
        d = msp.add_linear_dim(base=base, p1=p1, p2=p2, dimstyle=M.OLCU_STILI, dxfattribs={"layer": "OLCU"})
        d.render()
    liste, _n, _u = M.tolerans_isle(msp, o, k, P, gk, kay, [], kplan, h, {}, False)
    M.tolerans_etiketleri(msp, liste, h)
    return doc, liste


kl = tempfile.mkdtemp(prefix="pi3d_od_")
yol = os.path.join(kl, "t.dxf")
doc, liste = resim({})
doc.saveas(yol)
ol = M.olcu_listesi(yol)
dogru("3 numaralı ölçü okundu", [x["no"] for x in ol] == [1, 2, 3], [(x["no"], x["deger"]) for x in ol])
deg = {x["no"]: x["deger"] for x in ol}
kayit = M.olcu_duzenle(yol, sil=[3], ref=[2], tol={1: 0.1}, log=lambda *_: None)
ol2 = M.olcu_listesi(yol)
d2 = ezdxf.readfile(yol)
yazi = [e.dxf.text for e in d2.modelspace().query("TEXT")]
dims = {e.dxf.handle: e for e in d2.modelspace().query("DIMENSION")}
dogru("3 numara silindi", [x["no"] for x in ol2] == [1, 2], [x["no"] for x in ol2])
dogru("değerler değişmedi", all(abs(x["deger"] - deg[x["no"]]) < 1e-9 for x in ol2))
dogru("1 numaraya ±0,1 yazıldı", "±0,1" in yazi and next(x for x in ol2 if x["no"] == 1)["tol"] == 0.1, yazi)
x2 = next(x for x in ol2 if x["no"] == 2)
dogru("2 numara referans ölçü (parantez)", x2["ref"] and str(dims[x2["handle"]].dxf.text).startswith("("),
      dims[x2["handle"]].dxf.text)
dogru("kalıcı kayıt kimlikle", len(kayit["sil"]) == 1 and len(kayit["olcu"]) == 2
      and "ref" in kayit["olcu"].values(), kayit)
# genele dön
M.olcu_duzenle(yol, genel=[1, 2], log=lambda *_: None)
ol3 = M.olcu_listesi(yol)
d3 = ezdxf.readfile(yol)
dogru("genele dönünce ± etiketi kalktı", not [e for e in d3.modelspace().query("TEXT") if e.dxf.text.startswith("±")])
x2 = next(x for x in ol3 if x["no"] == 2)
dogru("genele dönünce parantez kalktı", not str(d3.entitydb.get(x2["handle"]).dxf.text).startswith("("))
# yeniden çizimde kalıcı kayıt uygulanır
doc4, liste4 = resim({"tolerans": {"olcu": kayit["olcu"], "sil": kayit["sil"]}})
y4 = os.path.join(kl, "t4.dxf"); doc4.saveas(y4)
ol4 = M.olcu_listesi(y4)
dogru("yeniden çizim: silinen ölçü yok", len(ol4) == 2, [(x["no"], x["deger"]) for x in ol4])
dogru("yeniden çizim: ±0,1 ve referans uygulandı",
      any(x["tol"] == 0.1 and x["ozel"] for x in ol4) and any(x["ref"] for x in ol4), ol4)
print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(0 if not HATA else 1)
