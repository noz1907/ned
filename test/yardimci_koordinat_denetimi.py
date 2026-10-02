# -*- coding: utf-8 -*-
"""YARDIMCI GÖRÜNÜŞ (eğik yüz) ve DELİK KOORDİNAT TABLOSU denetimi.

  1. Tabana 30° eğik kanat (2 delik, ekseni kanada dik): esas görünüşlerde
     eğik delikler konumsuz kalırdı; YARDIMCI A görünüşü çizilir, iki delik
     kanadın sol / alt kenarından ölçülenir, kanadın gerçek boyu verilir,
     esas görünüşte bakış oku + harf.
  2. 30 delikli levha: ÜST görünüşünde konum ölçüsü yerine TABLO (NO, X, Y,
     Ø; sıfır görünüşün sol alt köşesi); 8 delikli levhada tablo YOK
     (kullanıcı: "4 delik ya da dağınık 3-4'lük gruplarda hayır").
  3. Çakışma 0.

    python test/yardimci_koordinat_denetimi.py
"""
import math, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder   # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse                 # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform                       # noqa: E402
from OCP.gp import gp_Pnt, gp_Ax1, gp_Ax2, gp_Dir, gp_Trsf                    # noqa: E402
import ezdxf                                                                  # noqa: E402
import pf3_olcu as O                                                          # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def egik_kanatli():
    taban = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 200, 120, 3).Shape()
    kanat = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 200, 3, 80).Shape()
    # kanat Y=120 kenarında, X ekseni etrafında 30° dışa yatık (normal eğik)
    tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)), -math.radians(30))
    kanat = BRepBuilderAPI_Transform(kanat, tr, True).Shape()
    tr2 = gp_Trsf(); tr2.SetTranslation(gp_Pnt(0, 0, 0), gp_Pnt(0, 117, 0))
    kanat = BRepBuilderAPI_Transform(kanat, tr2, True).Shape()
    op = BRepAlgoAPI_Fuse(taban, kanat); op.Build(); sh = op.Shape()
    # kanada dik iki delik: eksen = kanadın (programın bulduğu) normali
    k = O.kutu(sh)
    km = O.egik_yuzler(sh, k[3] - k[0], k[4] - k[1], k[5] - k[2], 4.0, ince=6.0)[0]
    n, m = km["n"], km["merkez"]
    for dx_ in (-40.0, 40.0):
        c = (m[0] + dx_ - n[0] * 5, m[1] - n[1] * 5, m[2] - n[2] * 5)
        sil = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*c), gp_Dir(*n)), 4.0, 10.0).Shape()
        sh = BRepAlgoAPI_Cut(sh, sil).Shape()
    return sh


def delikli_levha(n_x, n_y):
    sh = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 400, 300, 3).Shape()
    for i in range(n_x):
        for j in range(n_y):
            c = gp_Pnt(40 + i * 320.0 / max(n_x - 1, 1), 40 + j * 220.0 / max(n_y - 1, 1), -1)
            sh = BRepAlgoAPI_Cut(sh, BRepPrimAPI_MakeCylinder(gp_Ax2(c, gp_Dir(0, 0, 1)), 4.5, 5.0).Shape()).Shape()
    return sh


def ciz(sh, kl, ad):
    P = {"yogunluk": 7.85e-6, "en_az_delik": 1.0, "arac": None, "gorunusler": [], "kesit": False,
         "gizli": True, "perspektif": True}
    s2, o = O.komponent_olcu(sh, P)
    yol = os.path.join(kl, ad + ".dxf")
    O.dxf_komponent(s2, o, {"kod": ad, "ad": ad, "adet": 1, "poz": 1, "malzeme_ad": "Çelik"}, yol, P)
    lay = ezdxf.readfile(yol).modelspace()
    alanlar = {}
    for e in lay.query("LWPOLYLINE"):
        if e.dxf.layer == O.GORUNUS_KATMAN:
            a = next((v for k, v in e.get_xdata(O.GORUNUS_APPID) if k == 1000), None)
            p = list(e.get_points("xy"))
            alanlar[a] = (min(q[0] for q in p), min(q[1] for q in p), max(q[0] for q in p), max(q[1] for q in p))
    yazilar = [t.dxf.text for t in lay.query("TEXT")]
    return o, alanlar, yazilar, lay, yol


def main():
    kl = tempfile.mkdtemp(prefix="pi3d_yk_")
    print("1) eğik kanat -> yardımcı görünüş")
    sh = egik_kanatli()
    o, al, yz, lay, yol1 = ciz(sh, kl, "EGIK_KANAT")
    egik = [d for d in o["delikler"] if d["eksen"] == "eğik"]
    dogru("iki eğik delik tanındı (yön saklı)", egik and egik[0]["adet"] == 2 and egik[0].get("yonler"),
          [(d["eksen"], d["adet"]) for d in o["delikler"]])
    yard = [a for a in al if a.startswith("YARDIMCI")]
    dogru("YARDIMCI görünüş var", len(yard) == 1, sorted(al))
    dogru("etiket: 'YARDIMCI GÖRÜNÜŞ D' ve '2x Ø8'",
          any(t.startswith("YARDIMCI GÖRÜNÜŞ") for t in yz) and any("2x Ø8" in t for t in yz), yz[:12])
    if yard:
        kt = al[yard[0]]
        dims = [e for e in lay.query("DIMENSION") if kt[0] - 1 <= e.dxf.defpoint.x <= kt[2] + 1 and kt[1] - 1 <= e.dxf.defpoint.y <= kt[3] + 1]
        dogru("yardımcı görünüşte en az 5 ölçü (2 X konum + gabari, 1 Y konum + gabari)", len(dims) >= 5, len(dims))
    oklar = [e for e in lay.query("SOLID")]
    dogru("esas görünüşte bakış oku çizildi", len(oklar) >= 1, len(oklar))
    print("2) koordinat tablosu")
    o2, al2, yz2, lay2, yol2 = ciz(delikli_levha(6, 5), kl, "LEVHA_30")
    tablo = [a for a in al2 if a.startswith("TABLO")]
    dogru("30 delikli levhada TABLO var", len(tablo) == 1, sorted(al2))
    dogru("tablo başlığı delik sayısını yazıyor", any("DELİK TABLOSU" in t and "30 delik" in t for t in yz2), [t for t in yz2 if "TABLO" in t])
    dogru("tabloda 30 satır (NO 1..30)", all(str(i) in yz2 for i in (1, 15, 30)))
    o3, al3, yz3, lay3, yol3 = ciz(delikli_levha(4, 2), kl, "LEVHA_8")
    dogru("8 delikli levhada tablo yok (normal ölçü)", not any(a.startswith("TABLO") for a in al3), sorted(al3))
    print("3) çakışma")
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "cizim_cakisma_denetimi.py"), kl],
                       capture_output=True, text=True)
    dogru("çakışma 0", "CAKISMA YOK" in r.stdout, r.stdout[-400:])
    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    print("klasör:", kl)
    return 0 if not HATA else 1


if __name__ == "__main__":
    sys.exit(main())
