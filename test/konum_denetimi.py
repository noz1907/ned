# -*- coding: utf-8 -*-
"""Konum ölçüleri: deliklerin kenardan yeri.

Önce resimde YALNIZ gabari ölçüsü vardı (görünüş başına 2 tane) ve
Ø/R boyutları. Deliğin nerede olduğunu söyleyen tek bir ölçü yoktu:
atölye "2480 x 120 sacta 124 delik Ø6,8" biliyordu ama deliklerin
yerini bilmiyordu.

Zincir kuralı (kullanıcının verdiği): kenardan ilk deliğe, sonra
dizinin adımı, sonra son delikten öbür kenara. 124 deliğin her birine
20 mm yazmak resmi okunmaz yapar ve hiçbir şey eklemez.

Denetlenen:
  1. Dizi tanınıyor mu ve "123 x 20" diye tek ölçüye iniyor mu,
  2. zincir kenardan başlayıp kenarda bitiyor mu,
  3. dağınık delikler tek tek ölçülüyor mu,
  4. gabari ölçüsü EN DIŞARIDA mı (küçük ölçüler içeride),
  5. hiçbir yazı bir başkasının ya da konturun üstüne binmiyor mu.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                   # noqa: E402
import ezdxf.bbox                                              # noqa: E402
import pf3_olcu as O                                           # noqa: E402

from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox,              # noqa: E402
                             BRepPrimAPI_MakeCylinder)
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut                    # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt                      # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    if kosul:
        print(f"  tamam {ad}")
    else:
        print(f"  HATA  {ad}: {neden}")
        HATA.append(ad)


def esit(ad, olan, beklenen):
    dogru(ad, olan == beklenen, f"{olan!r} != {beklenen!r}")


def plaka(gen, boy, t, delik):
    sh = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), gen, boy, t).Shape()
    for x, y, r in delik:
        sh = BRepAlgoAPI_Cut(sh, BRepPrimAPI_MakeCylinder(
            gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)), r, t + 2).Shape()).Shape()
    return sh


def olcu_degerleri(yol):
    d = ezdxf.readfile(yol)
    out = []
    for e in d.modelspace():
        if e.dxftype() != "DIMENSION":
            continue
        t = (e.dxf.get("text", "") or "").strip()
        try:
            v = round(float(e.get_measurement()), 2)
        except Exception:
            v = None
        out.append((t if t not in ("", "<>") else None, v))
    return out


def subprocess_run(yol):
    import subprocess
    r = subprocess.run([sys.executable,
                        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "cizim_cakisma_denetimi.py"), yol],
                       capture_output=True, text=True)
    return r.stdout


def main():
    kl = tempfile.mkdtemp(prefix="konum_denetim_")
    P = {"gizli": False, "en_az_delik": 1.0, "yogunluk": O.RHO,
         "gorunusler": ("UST",), "kesit": False}

    print("-- dizi: 10 mm'den başlayan, 20 mm adımlı 11 delik")
    sh = plaka(220.0, 60.0, 5.0,
               [(10.0 + 20.0 * i, 30.0, 3.4) for i in range(11)])
    s2, o = O.komponent_olcu(sh, P)
    ham = {"UST": O._kenar_kutusu(O.hlr(s2, *O.GORUNUS["UST"], gizli=False))}
    pl = O.konum_plani(o, ("UST",), ham, 4.0)
    y = pl["UST"]["yatay"]
    print("     yatay zincir:",
          [(round(r["a"], 1), round(r["b"], 1), r["metin"]) for r in y])
    # Sıra ÖLÇÜ BOYUNA göredir (kısa içeride); içeriğe göre aranır.
    esit("zincir üç parça", len(y), 3)
    diz = [r for r in y if r["metin"]]
    kenar = sorted(r for r in (abs(r["b"] - r["a"]) for r in y))
    esit("ortadaki dizi", [r["metin"] for r in diz], ["10 x 20"])
    dogru("kenardan başlıyor",
          any(abs(r["a"] - 0.0) < 0.2 and abs(r["b"] - 10.0) < 0.2 for r in y),
          str([(round(r["a"], 1), round(r["b"], 1)) for r in y]))
    dogru("kenarda bitiyor",
          any(abs(r["b"] - 220.0) < 0.2 and abs(r["a"] - 210.0) < 0.2
              for r in y),
          str([(round(r["a"], 1), round(r["b"], 1)) for r in y]))
    dogru("hiçbir ölçü 20 diye tek tek yazılmamış",
          sum(1 for r in y if r["metin"] is None and
              abs((r["b"] - r["a"]) - 20.0) < 0.2) == 0,
          "adım tek tek yazılmış")

    print("\n-- dağınık delikler DATUMDAN ölçülüyor (zincir DEĞİL)")
    sh2 = plaka(120.0, 80.0, 5.0, [(15.0, 20.0, 3.0), (47.0, 60.0, 3.0),
                                   (95.0, 35.0, 3.0)])
    s3, o2 = O.komponent_olcu(sh2, P)
    ham2 = {"UST": O._kenar_kutusu(O.hlr(s3, *O.GORUNUS["UST"], gizli=False))}
    pl2 = O.konum_plani(o2, ("UST",), ham2, 4.0)
    yx = pl2["UST"]["yatay"]
    print("     yatay:", [(round(r["a"], 1), round(r["b"], 1)) for r in yx])
    # Delikler x = 15, 47, 95; plaka 0..120. Her ölçü AYNI kenardan
    # (x=0) başlamalı - zincir kurulmamalı. Zincirde 15, 32, 48 diye
    # ara farklar çıkardı ve 47'yi bulmak için toplamak gerekirdi.
    esit("hepsi aynı datumdan", sorted({round(r["a"], 1) for r in yx}), [0.0])
    esit("ölçülen konumlar",
         sorted(round(r["b"], 1) for r in yx), [15.0, 47.0, 95.0])
    dogru("hiçbiri dizi sayılmadı",
          all(r["metin"] is None for r in yx), "dizi bulundu")
    dy = pl2["UST"]["dusey"]
    esit("düşeyde de tek datum", sorted({round(r["a"], 1) for r in dy}), [0.0])

    print("\n-- simetri: ayna çiftleri iki kez ölçülmez")
    # 175 x 100 plaka, delikler 10 / 13,2 / 161,8 / 165'te (ayna).
    sim = plaka(175.0, 100.0, 5.0,
                [(10.0, 15.0, 5.1), (10.0, 45.0, 5.1),
                 (165.0, 15.0, 5.1), (165.0, 45.0, 5.1),
                 (13.25, 90.0, 4.05), (161.75, 90.0, 4.05)])
    s5, o5 = O.komponent_olcu(sim, P)
    ham5 = {"UST": O._kenar_kutusu(O.hlr(s5, *O.GORUNUS["UST"], gizli=False))}
    pl5 = O.konum_plani(o5, ("UST",), ham5, 4.0)
    ux = sorted(round(r["b"] - r["a"], 2) for r in pl5["UST"]["yatay"])
    print("     yatay ölçüler:", ux, " simetri:",
          pl5["UST"]["yatay_simetrik"])
    dogru("simetri bulundu", pl5["UST"]["yatay_simetrik"], "bulunamadı")
    esit("yalnız iki delik konumu", ux, [10.0, 13.25])
    dogru("161,8 ve 165 tekrar ölçülmedi",
          not any(abs(v - 161.75) < 0.2 or abs(v - 165.0) < 0.2 for v in ux),
          str(ux))
    # Düşeyde simetri YOK (15 / 45 / 90): hepsi ölçülmeli.
    dy5 = sorted(round(r["b"] - r["a"], 2) for r in pl5["UST"]["dusey"])
    dogru("simetrik olmayan yön kısaltılmadı",
          not pl5["UST"]["dusey_simetrik"] and len(dy5) >= 3, str(dy5))
    # Simetri işareti resimde görünmeli.
    yol5 = os.path.join(kl, "P05_SIM.dxf")
    O.dxf_komponent(s5, o5, {"poz": 5, "kod": "SIM", "ad": "Simetrik plaka",
                             "adet": 1, "malzeme_ad": "Celik"}, yol5, P)
    d5 = ezdxf.readfile(yol5)
    eks = [e for e in d5.modelspace()
           if e.dxftype() == "LINE" and e.dxf.layer == "EKSEN"]
    dogru("simetri ekseni ve işareti çizildi", len(eks) >= 5,
          f"{len(eks)} eksen çizgisi")

    print("\n-- köşe pahı mı, eğik kesim mi")
    # 45°'lik pah: köşesi kesilmiş plaka.
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut as _Cut
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec
    # 5 x 5 köşe kırma - gerçek parçalardaki ölçü (175x100 plakada da
    # 5x5). Plakaya göre küçük olması pahın tanımının parçasıdır.
    pg = BRepBuilderAPI_MakePolygon(gp_Pnt(115, 80, -1), gp_Pnt(120, 80, -1),
                                    gp_Pnt(120, 75, -1), True).Wire()
    kama = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(pg).Face(),
                                 gp_Vec(0, 0, 7)).Shape()
    pah = _Cut(plaka(120.0, 80.0, 5.0, []), kama).Shape()
    ke = O.hlr(pah, *O.GORUNUS["UST"], gizli=False)
    cp = O.capraz_kenarlar(ke)
    print("     bulunan:", [(round(t["aci"], 1), round(t["uz"], 1)) for t in cp])
    dogru("45 derecelik pah bulundu",
          any(abs(t["aci"] - 135.0) < 1.0 or abs(t["aci"] - 45.0) < 1.0
              for t in cp), str([round(t["aci"], 1) for t in cp]))
    dogru("boyu doğru (5√2 = 7,07)",
          any(abs(t["uz"] - 7.07) < 0.2 for t in cp),
          str([round(t["uz"], 1) for t in cp]))
    # Köşeyi kesiyor ve iki ucu da dik iki kenara dayanıyor: PAHTIR.
    dogru("köşe kırma diye tanındı", all(t["pah"] for t in cp),
          str([(round(t["aci"], 1), t["pah"]) for t in cp]))
    dogru("bacakları 5 x 5",
          any(abs(t["bacak"][0] - 5.0) < 0.2 and abs(t["bacak"][1] - 5.0) < 0.2
              for t in cp), str([t["bacak"] for t in cp]))

    # Köşe kırma OLMAYAN eğik kesim: bir ucu serbest.
    # Bacakları EŞİT DEĞİL (50 x 25): köşeden geçse de köşe kırma değil,
    # parçanın biçimidir.
    pg2 = BRepBuilderAPI_MakePolygon(gp_Pnt(40, 80, -1), gp_Pnt(90, 80, -1),
                                     gp_Pnt(40, 55, -1), True).Wire()
    kama2 = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(pg2).Face(),
                                  gp_Vec(0, 0, 7)).Shape()
    egik = _Cut(plaka(120.0, 80.0, 5.0, []), kama2).Shape()
    cp2 = O.capraz_kenarlar(O.hlr(egik, *O.GORUNUS["UST"], gizli=False))
    print("     eğik kesim:", [(round(t["aci"], 1), t["pah"]) for t in cp2])
    dogru("eğik kesim pah sayılmadı",
          cp2 and not any(t["pah"] for t in cp2),
          str([(round(t["aci"], 1), t["pah"]) for t in cp2]))
    ham3 = {"UST": O._kenar_kutusu(O.hlr(egik, *O.GORUNUS["UST"], gizli=False))}
    pl3 = O.konum_plani(o2, ("UST",), ham3, 4.0,
                        {"UST": O.hlr(egik, *O.GORUNUS["UST"], gizli=False)})
    ux = sorted(round(r["b"], 1) for r in pl3["UST"]["yatay"])
    print("     eğik kesimin uçları (yatay):", ux)
    dogru("eğik kesimin uçları kenardan ölçülüyor",
          any(abs(v - 40.0) < 0.5 for v in ux)
          and any(abs(v - 90.0) < 0.5 for v in ux), str(ux))
    # Büyük 45'lik bir kesim de pah sayılmamalı.
    pg3 = BRepBuilderAPI_MakePolygon(gp_Pnt(60, 80, -1), gp_Pnt(120, 80, -1),
                                     gp_Pnt(120, 20, -1), True).Wire()
    buyuk = _Cut(plaka(120.0, 80.0, 5.0, []),
                 BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(pg3).Face(),
                                       gp_Vec(0, 0, 7)).Shape()).Shape()
    cp3 = O.capraz_kenarlar(O.hlr(buyuk, *O.GORUNUS["UST"], gizli=False))
    print("     büyük 45 kesim:", [(round(t["aci"], 1), t["bacak"], t["pah"])
                                   for t in cp3])
    dogru("büyük 45 kesim pah sayılmadı",
          cp3 and not any(t["pah"] for t in cp3),
          str([(round(t["aci"], 1), t["pah"]) for t in cp3]))
    dogru("yatay ve düşey kenarlar çapraz sayılmadı",
          all(min(abs(t["aci"]), abs(t["aci"] - 90), abs(t["aci"] - 180)) > 1.0
              for t in cp), "eksene paralel kenar geldi")

    print("\n-- resim: gabari en dışarıda, çakışma yok")
    yol = os.path.join(kl, "P01_DENEME.dxf")
    O.dxf_komponent(s2, o, {"poz": 1, "kod": "DENEME", "ad": "Dizi plaka",
                            "adet": 1, "malzeme_ad": "Celik"}, yol, P)
    d = ezdxf.readfile(yol)
    olc = olcu_degerleri(yol)
    print("     ölçüler:", olc)
    dogru("'10 x 20' resme girdi",
          any(t == "10 x 20" for t, _v in olc), str(olc))
    dogru("gabari 220 var", any(v == 220.0 for _t, v in olc), str(olc))
    dogru("kenar payları var",
          sum(1 for _t, v in olc if v == 10.0) >= 2, str(olc))

    # Gabari ölçüsü, konum ölçülerinin DIŞINDA olmalı.
    gab = alt = None
    for e in d.modelspace():
        if e.dxftype() != "DIMENSION":
            continue
        try:
            v = round(float(e.get_measurement()), 2)
        except Exception:
            continue
        k = ezdxf.bbox.extents([e], fast=True)
        if not k.has_data:
            continue
        if v == 220.0:
            gab = k.extmin.y
        elif (e.dxf.get("text", "") or "") == "10 x 20":
            alt = k.extmin.y
    dogru("gabari konum ölçüsünün dışında",
          gab is not None and alt is not None and gab < alt,
          f"gabari y={gab}, zincir y={alt}")

    print("\n-- çakışma")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import cizim_cakisma_denetimi as C
    n = C.resmi_denetle(yol) if hasattr(C, "resmi_denetle") else None
    if n is None:
        import subprocess
        r = subprocess.run([sys.executable,
                            os.path.join(os.path.dirname(
                                os.path.abspath(__file__)),
                                "cizim_cakisma_denetimi.py"), yol],
                           capture_output=True, text=True)
        dogru("çakışma yok", "CAKISMA YOK" in r.stdout,
              r.stdout.strip().splitlines()[-1] if r.stdout else "?")
    else:
        dogru("çakışma yok", n == 0, str(n))

    print("\n-- pah notu: ok ucunda \"5 x 5\", açı YOK")
    yol4 = os.path.join(kl, "P04_PAH.dxf")
    s4, o4 = O.komponent_olcu(pah, P)
    O.dxf_komponent(s4, o4, {"poz": 4, "kod": "PAH", "ad": "Pahlı plaka",
                             "adet": 1, "malzeme_ad": "Celik"}, yol4, P)
    d4 = ezdxf.readfile(yol4)
    yazi = [e.dxf.text for e in d4.modelspace() if e.dxftype() == "TEXT"]
    pah = [t for t in yazi if " x " in t and "KALINLIK" not in t]
    print("     pah notu:", pah)
    dogru("pah notu resme girdi", bool(pah), str(yazi))
    dogru("bacak ölçüsü yazıyor (5 x 5)",
          any("5 x 5" in t for t in pah), str(pah))
    # Pahın AÇISI ve hipotenüsü verilmez: keskin köşe kalmasın diye
    # kırılmış bir köşenin ölçüsü iki bacağıdır.
    dogru("pahın açısı yazılmadı",
          not any("%%d" in t for t in yazi), str(yazi))
    dogru("pah notu kılavuzla bağlı",
          sum(1 for e in d4.modelspace()
              if e.dxftype() == "LINE" and e.dxf.layer == "OLCU") >= len(pah),
          "kılavuz çizgisi yok")

    print("\n-- kapalı kontur: düzlemsel yüz dolaşımı")
    kare = {"GORUNEN": [[(0, 0), (10, 0)], [(10, 0), (10, 5)],
                        [(10, 5), (0, 5)], [(0, 5), (0, 0)]], "GIZLI": []}
    esit("kare iki halka verir (biri artı biri eksi)",
         sorted(round(O._cokgen_alani(q), 1) for q in O.halkalar(kare)),
         [-50.0, 50.0])
    esit("kareden dış hat çıkıyor",
         round(O._cokgen_alani(O.dis_kontur(kare)), 1), 50.0)
    # HLR aynı kenarı iki kez verir; kopya dış hattı yutuyordu.
    kopya = {"GORUNEN": kare["GORUNEN"] + [[(0, 0), (10, 0)]], "GIZLI": []}
    esit("kopya kenar dış hattı bozmuyor",
         round(O._cokgen_alani(O.dis_kontur(kopya)), 1), 50.0)
    # Havada biten siluet çizgisi de bozuyordu. (Parçanın içinde kalır:
    # görünür bir kenar siluetin dışına çıkamaz.) Biri köşeye bağlı,
    # biri tamamen boşta.
    asili = {"GORUNEN": kare["GORUNEN"] + [[(10, 5), (6, 3)],
                                          [(2, 1), (3, 4)]], "GIZLI": []}
    esit("asılı kenar dış hattı bozmuyor",
         round(O._cokgen_alani(O.dis_kontur(asili)), 1), 50.0)
    # Dört kenara değmeyen halka dış hat sayılmaz.
    kucuk = {"GORUNEN": [[(0, 0), (1, 0)], [(1, 0), (1, 1)],
                         [(1, 1), (0, 1)], [(0, 1), (0, 0)],
                         [(9, 9), (9.2, 9)]], "GIZLI": []}
    esit("görünüşü doldurmayan halka dış hat sayılmadı",
         O.dis_kontur(kucuk), None)

    print("\n-- girinti: çentiğin yeri ve derinliği")
    # 120 x 80 plakanın alt kenarından 30..50 arası 15 mm çentik.
    # (50..70 OLMAZ: 50 + 70 = 120, çentik ortada kalır ve simetri
    # kuralı ikinci ucu haklı olarak atar - o ayrıca sınanıyor.)
    duz = plaka(120.0, 80.0, 5.0, [])
    esit("düz plakada girinti yok",
         O.kontur_ozellikleri([(0, 0), (120, 0), (120, 80), (0, 80)],
                              (0.0, 0.0, 120.0, 80.0)), [])
    # Derinlik TAM olmalı, kutucuktan değil konturdan: dik eğimde
    # kutucuk hatası 2 mm'yi buluyordu (17,67 yerine 15,73).
    def oz_(dis, k):
        return [(r["a"], r["b"], r["derinlik"], r["ic"])
                for r in O.kontur_ozellikleri(dis, k)]
    kt = (0.0, 0.0, 120.0, 80.0)
    esit("V çentik: 40..60, derinlik tam 25",
         oz_([(0, 0), (40, 0), (50, 25), (60, 0), (120, 0), (120, 80),
              (0, 80)], kt), [(40, 60, 25.0, True)])
    esit("kırlangıç: ağız 40..60, derinlik tam 20",
         oz_([(0, 0), (40, 0), (35, 20), (65, 20), (60, 0), (120, 0),
              (120, 80), (0, 80)], kt), [(40, 60, 20.0, True)])
    # Köşe kesiği iki kenarda da girinti olarak çıkar; bacaklarını
    # iki konum verir, derinlik YAZILMAZ (ikinci kez olurdu).
    ks = O.kontur_ozellikleri([(0, 0), (195, 0), (195, 43.67), (177.33, 50),
                               (0, 50)], (0.0, 0.0, 195.0, 50.0))
    esit("köşe kesiğinin bacakları tam",
         sorted((r["taraf"], r["a"], r["b"]) for r in ks),
         [("sag", 43.67, 50), ("ust", 177.33, 195)])
    esit("köşe kesiğine derinlik yazılmaz",
         [r["derinlik"] for r in ks], [None, None])
    # Ağzı R2 ile yuvarlatılmış çentik: kontur kenardan TEĞET noktasında
    # (28 ve 52) ayrılır; ölçü sanal keskin köşeye (30 ve 50) verilir.
    yuv = [(0, 0), (28, 0), (29.414, 0.586), (30, 2), (30, 15), (50, 15),
           (50, 2), (50.586, 0.586), (52, 0), (120, 0), (120, 80), (0, 80)]
    duz_ = [True, False, False, True, True, True, False, False,
            True, True, True, True]
    esit("yuvarlak ağız: sanal köşe 30..50, derinlik 15",
         [(r["a"], r["b"], r["derinlik"]) for r in
          O.kontur_ozellikleri(yuv, kt, duz=duz_)], [(30, 50, 15.0)])
    esit("yay bilgisi yoksa teğet noktası (28..52)",
         [(r["a"], r["b"]) for r in O.kontur_ozellikleri(yuv, kt)],
         [(28, 52)])
    centikli = BRepAlgoAPI_Cut(duz, BRepPrimAPI_MakeBox(
        gp_Pnt(30.0, -1.0, -1.0), 20.0, 16.0, 7.0).Shape()).Shape()
    s7, o7 = O.komponent_olcu(centikli, P)
    ken7 = O.hlr(s7, *O.GORUNUS["UST"], gizli=False)
    kb7 = O._kenar_kutusu(ken7)
    oz = O.gorunus_ozellikleri(ken7, kb7)
    print("     girinti:", [(r["taraf"], round(r["a"], 1), round(r["b"], 1),
                             round(r["derinlik"], 1)) for r in oz])
    esit("tek girinti bulundu", len(oz), 1)
    if oz:
        r = oz[0]
        esit("çentik alt kenarda", r["taraf"], "alt")
        # TAM değer: kutucuk çözünürlüğü değil, gerçek köşe.
        dogru("çentik tam 30..50 arasında",
              abs(r["a"] - 30.0) < 0.01 and abs(r["b"] - 50.0) < 0.01,
              f"{r['a']:.1f}..{r['b']:.1f}")
        dogru("çentik tam 15 mm derin", abs(r["derinlik"] - 15.0) < 0.01,
              f"{r['derinlik']:.1f}")

    # Aynısı GERÇEK katıyla: çentiğin ağız kenarları R2 yuvarlatılmış;
    # HLR'den gelen yayın doğru/yay ayrımı kenar_tani'den.
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line
    fl = BRepFilletAPI_MakeFillet(centikli)
    ex = TopExp_Explorer(centikli, TopAbs_EDGE)
    while ex.More():
        e = TopoDS.Edge_s(ex.Current())
        c = BRepAdaptor_Curve(e)
        if c.GetType() == GeomAbs_Line:
            a_, b_ = c.Value(c.FirstParameter()), c.Value(c.LastParameter())
            if (abs(a_.X() - b_.X()) < 1e-6 and abs(a_.Y() - b_.Y()) < 1e-6
                    and abs(a_.Y()) < 1e-6 and min(abs(a_.X() - 30.0),
                                                   abs(a_.X() - 50.0)) < 1e-6):
                fl.Add(2.0, e)
        ex.Next()
    fl.Build()
    s10, o10 = O.komponent_olcu(fl.Shape(), P)
    ken10 = O.hlr(s10, *O.GORUNUS["UST"], gizli=False)
    oz10 = O.gorunus_ozellikleri(ken10, O._kenar_kutusu(ken10))
    print("     R2 ağızlı çentik:", [(round(r["a"], 3), round(r["b"], 3),
                                      r["derinlik"]) for r in oz10])
    dogru("R2 ağızlı katı: sanal köşe tam 30..50, derinlik 15",
          len(oz10) == 1 and abs(oz10[0]["a"] - 30.0) < 1e-3
          and abs(oz10[0]["b"] - 50.0) < 1e-3
          and oz10[0]["derinlik"] is not None
          and abs(oz10[0]["derinlik"] - 15.0) < 1e-3, str(oz10))

    print("\n-- çentiğin konumu ve derinliği resme giriyor mu")
    yol7 = os.path.join(kl, "P07_CENTIK.dxf")
    P7 = dict(P); P7["gorunusler"] = ("UST",)
    O.dxf_komponent(s7, o7, {"poz": 7, "kod": "CENTIK", "ad": "Çentikli plaka",
                             "adet": 1, "malzeme_ad": "Celik"}, yol7, P7)
    deg = [v for _t, v in olcu_degerleri(yol7) if v is not None]
    print("     ölçüler:", sorted(deg))
    dogru("çentiğin başı (30) ölçülmüş",
          any(abs(v - 30.0) < 0.01 for v in deg), str(sorted(deg)))
    dogru("çentiğin sonu (50) ölçülmüş",
          any(abs(v - 50.0) < 0.01 for v in deg), str(sorted(deg)))
    dogru("çentiğin derinliği (15) ölçülmüş",
          any(abs(v - 15.0) < 0.01 for v in deg), str(sorted(deg)))

    # Ortadaki çentik: iki ucu ayna görüntüsü, yalnız biri ölçülür.
    orta = BRepAlgoAPI_Cut(duz, BRepPrimAPI_MakeBox(
        gp_Pnt(50.0, -1.0, -1.0), 20.0, 16.0, 7.0).Shape()).Shape()
    s8, o8 = O.komponent_olcu(orta, P)
    ken8 = {"UST": O.hlr(s8, *O.GORUNUS["UST"], gizli=False)}
    pl8 = O.konum_plani(o8, ("UST",), {"UST": O._kenar_kutusu(ken8["UST"])},
                        4.0, ken8)
    y8 = sorted(round(abs(r["b"] - r["a"]), 2) for r in pl8["UST"]["yatay"])
    print("     ortadaki çentik, yatay konum:", y8)
    esit("ortadaki çentikte yalnız 50 ölçülür", y8, [50.0])
    dogru("ortadaki çentik simetrik işaretlendi",
          pl8["UST"]["yatay_simetrik"], "simetri işareti yok")
    r7 = subprocess_run(yol7)
    dogru("çentikli resimde çakışma yok", "CAKISMA YOK" in r7,
          r7.strip().splitlines()[-1] if r7 else "?")

    print("\n-- kenarın ucuna dayanan basamak; ayna görünüş")
    # 120 x 80 plakanın sağ alt köşesinden 30 x 20 basamak: girinti
    # 90..120. 90 konumdur; 120 gabaridir, konum diye tekrar yazılmaz.
    basamak = BRepAlgoAPI_Cut(duz, BRepPrimAPI_MakeBox(
        gp_Pnt(90.0, -1.0, -1.0), 31.0, 21.0, 7.0).Shape()).Shape()
    s9, o9 = O.komponent_olcu(basamak, P)
    ken9 = {g: O.hlr(s9, *O.GORUNUS[g], gizli=False) for g in ("UST", "ALT")}
    ham9 = {g: O._kenar_kutusu(k) for g, k in ken9.items()}
    pl9 = O.konum_plani(o9, ("UST", "ALT"), ham9, 4.0, ken9)
    y9 = sorted(round(abs(r["b"] - r["a"]), 2) for r in pl9["UST"]["yatay"])
    print("     basamak, yatay konum:", y9)
    dogru("basamağın başı (90) ölçülmüş", 90.0 in y9, str(y9))
    dogru("gabari (120) konum diye tekrar yazılmamış", 120.0 not in y9, str(y9))
    # ÜST ile ALT aynı dış hattı gösterir; girinti yalnız birinde.
    esit("girinti yalnız ÜST'te", [g for g in ("UST", "ALT")
                                   if pl9.get(g, {}).get("ozellik")], ["UST"])

    print("\n-- iç pencere (yuva): kenara açılmayan girinti")
    # 120 x 80 plakada 20 x 10 dikdörtgen pencere (30..50, 40..50) ve
    # bir Ø8 delik. Pencere konum ister; delik pencere SAYILMAZ (o 3B'den
    # delik olarak ölçülüyor), dış kutuya değen halka da sayılmaz.
    pen = BRepAlgoAPI_Cut(plaka(120.0, 80.0, 5.0, [(90.0, 20.0, 4.0)]),
                          BRepPrimAPI_MakeBox(gp_Pnt(30.0, 40.0, -1.0),
                                              20.0, 10.0, 7.0).Shape()).Shape()
    s11, o11 = O.komponent_olcu(pen, P)
    ken11 = O.hlr(s11, *O.GORUNUS["UST"], gizli=False)
    pe = O.ic_pencereler(ken11, O._kenar_kutusu(ken11))
    print("     pencere:", [r["kutu"] for r in pe])
    esit("tek pencere, tam kutusu", [r["kutu"] for r in pe],
         [(30.0, 40.0, 50.0, 50.0)])
    pl11 = O.konum_plani(o11, ("UST",), {"UST": O._kenar_kutusu(ken11)},
                         4.0, {"UST": ken11})
    y11 = sorted(round(abs(r["b"] - r["a"]), 2) for r in pl11["UST"]["yatay"])
    d11 = sorted(round(abs(r["b"] - r["a"]), 2) for r in pl11["UST"]["dusey"])
    print("     yatay:", y11, " düşey:", d11)
    dogru("pencerenin iki yatay kenarı (30, 50) ölçülmüş",
          30.0 in y11 and 50.0 in y11, str(y11))
    dogru("pencerenin iki düşey kenarı (40, 50) ölçülmüş",
          40.0 in d11 and 50.0 in d11, str(d11))
    dogru("delik de yerinde (90 / 20)", 90.0 in y11 and 20.0 in d11,
          f"{y11} {d11}")

    print("\n-- eğri siluet: her eğik çizgi kesim değildir")
    import math
    # 20 kenarlı çokgen = aslında bir EĞRİ. Kenarlarının her birine
    # konum ölçüsü vermek resmi okunmaz yapar ve hiçbiri gerçek bir
    # kesimi göstermez; program ölçü vermemeyi seçmeli.
    n, r = 20, 50.0
    kose = [(r * math.cos(2 * math.pi * i / n),
             r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    egri = {"GORUNEN": [[kose[i], kose[(i + 1) % n]] for i in range(n)],
            "GIZLI": []}
    kutu_egri = (-r, -r, r, r)
    esit("eğri siluete kesim konumu verilmedi",
         O.kesim_uclari(egri, kutu_egri), [])
    # Denetim: üç uzun eğik kesim ölçülmeli.
    uc = {"GORUNEN": [[(0.0, 0.0), (40.0, 40.0)],
                      [(60.0, 0.0), (100.0, 35.0)],
                      [(20.0, 90.0), (70.0, 60.0)]], "GIZLI": []}
    esit("gerçek eğik kesimler ölçülüyor",
         len(O.kesim_uclari(uc, (0.0, 0.0, 100.0, 100.0))), 6)
    # Gürültü kapısı: görünüşün %10'undan kısa eğik sayılmaz.
    kisa = {"GORUNEN": [[(0.0, 0.0), (3.0, 3.0)]], "GIZLI": []}
    esit("kısa eğik gürültü sayıldı",
         O.kesim_uclari(kisa, (0.0, 0.0, 100.0, 100.0)), [])

    print("\n-- datum: parçanın kendi XYZ çerçevesi, her görünüşte AYNI")
    # En geniş yüzey birincil datum (A) olmalı: 200 x 100 x 10'luk
    # plakada Z'ye dik yüzey 200 x 100'dür, öbürleri daha küçük.
    esit("A en geniş yüzeyde", O.datum_cercevesi(200.0, 100.0, 10.0)[2], "A")
    esit("C en dar yüzeyde", O.datum_cercevesi(200.0, 100.0, 10.0)[0], "C")
    # Ekseni ters çevrilen görünüşte sıfır KARŞI uçtadır.
    esit("ÜST düşey datum alt uçta", O.datum_ucu("UST", "dusey"), 0)
    esit("ALT düşey datum üst uçta", O.datum_ucu("ALT", "dusey"), 1)
    esit("ÖN yatay datum sol uçta", O.datum_ucu("ON", "yatay"), 0)
    esit("ARKA yatay datum sağ uçta", O.datum_ucu("ARKA", "yatay"), 1)

    # ASIL SINAMA: aynı deliğin konumu ÜST'te ne yazıyorsa ALT'ta da
    # onu yazmalı. ALT'a öbür taraftan bakılır, izdüşüm -Y'dir; datum
    # görmezden gelinirse 25 yerine 75 çıkar ve resim kendiyle çelişir.
    sh6 = plaka(200.0, 100.0, 10.0, [(30.0, 25.0, 5.0)])
    s6, o6 = O.komponent_olcu(sh6, P)
    ham6 = {g: O._kenar_kutusu(O.hlr(s6, *O.GORUNUS[g], gizli=False))
            for g in ("UST", "ALT")}
    pl6 = O.konum_plani(o6, ("UST", "ALT"), ham6, 4.0)
    for g in ("UST", "ALT"):
        boy = {yon: sorted(round(abs(r["b"] - r["a"]), 1)
                           for r in pl6[g][yon])
               for yon in ("yatay", "dusey")}
        print(f"     {g}: {boy}")
        esit(f"{g} yatay konum 30", boy["yatay"], [30.0])
        esit(f"{g} düşey konum 25", boy["dusey"], [25.0])

    print("\n-- datum simgeleri resimde bir kez")
    yol6 = os.path.join(kl, "P06_DATUM.dxf")
    P6 = dict(P); P6["gorunusler"] = ("ON", "SAG", "SOL", "UST")
    O.dxf_komponent(s6, o6, {"poz": 6, "kod": "DATUM", "ad": "Datum plaka",
                             "adet": 1, "malzeme_ad": "Celik"}, yol6, P6)
    d6 = ezdxf.readfile(yol6)
    harf = sorted(e.dxf.text for e in d6.modelspace()
                  if e.dxftype() == "TEXT" and e.dxf.layer == "OLCU"
                  and e.dxf.text in ("A", "B", "C"))
    ucgen = sum(1 for e in d6.modelspace()
                if e.dxftype() == "SOLID" and e.dxf.layer == "OLCU")
    print("     datum harfleri:", harf, " üçgen:", ucgen)
    esit("üç datum, her biri bir kez", harf, ["A", "B", "C"])
    esit("her harfe bir üçgen", ucgen, 3)

    import subprocess
    r6 = subprocess.run([sys.executable,
                         os.path.join(os.path.dirname(
                             os.path.abspath(__file__)),
                             "cizim_cakisma_denetimi.py"), yol6],
                        capture_output=True, text=True)
    dogru("datumlu resimde çakışma yok", "CAKISMA YOK" in r6.stdout,
          r6.stdout.strip().splitlines()[-1] if r6.stdout else "?")

    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                         else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
