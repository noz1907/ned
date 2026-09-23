# -*- coding: utf-8 -*-
"""ANTET/PAFTA denetimi.

En önemlisi ilk madde: pafta eklemek 1:1 çizimi DEĞİŞTİRMEMELİDİR.
Bu dosya onu dosyanın baytından ve model uzayının geometrisinden
ayrı ayrı doğrular. Kalanı ölçek/kâğıt seçimi ve alan doldurma.
"""
import hashlib
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                  # noqa: E402
import pf4_pafta as P                                         # noqa: E402

hata = []


def esit(ad, olan, beklenen):
    if olan != beklenen:
        hata.append(f"{ad}: {olan!r} bekleniyordu {beklenen!r}")
        print(f"  HATA  {ad}: {olan!r} != {beklenen!r}")
    else:
        print(f"  tamam {ad}: {olan!r}")


def dogru(ad, kosul, aciklama=""):
    if kosul:
        print(f"  tamam {ad}")
    else:
        hata.append(f"{ad}: {aciklama}")
        print(f"  HATA  {ad}: {aciklama}")


def ornek_cizim(yol, gen, boy, delik=3):
    d = ezdxf.new(setup=True)
    d.header["$INSUNITS"] = 4
    m = d.modelspace()
    m.add_lwpolyline([(0, 0), (gen, 0), (gen, boy), (0, boy)], close=True)
    for i in range(delik):
        m.add_circle((gen * (i + 1) / (delik + 1), boy / 2), 5)
    m.add_text("1:1 CIZIM").set_placement((0, boy + 10))
    d.saveas(yol)
    return yol


def model_parmak_izi(yol):
    """Model uzayındaki geometrinin özeti. Bir koordinat bile oynasa
    değişir."""
    d = ezdxf.readfile(yol)
    p = []
    for e in d.modelspace():
        t = e.dxftype()
        if t == "LWPOLYLINE":
            p.append(("L", tuple(tuple(round(v, 9) for v in q)
                                 for q in e.get_points("xy"))))
        elif t == "LINE":
            p.append(("C", round(e.dxf.start.x, 9), round(e.dxf.start.y, 9),
                      round(e.dxf.end.x, 9), round(e.dxf.end.y, 9)))
        elif t in ("CIRCLE", "ARC"):
            p.append((t, round(e.dxf.center.x, 9), round(e.dxf.center.y, 9),
                      round(e.dxf.radius, 9)))
        elif t in ("TEXT", "MTEXT"):
            p.append(("Y", e.text if t == "MTEXT" else e.dxf.text))
    return hashlib.sha256(repr(sorted(map(repr, p))).encode()).hexdigest()


kl = tempfile.mkdtemp(prefix="pafta_denetim_")
try:
    antet = P.ornek_antet(os.path.join(kl, "ANTET_A3.dxf"), "A3", "DENEME A.Ş.")

    print("\n-- antet okundu mu")
    b = P.antet_incele(antet)
    esit("antet kâğıdı", b["kagit"], "A3")
    esit("tanınmayan alan", b["bilinmeyen"], [])
    dogru("CIZIM_ALANI var", b["cizim_alani"] is not None, "dikdörtgen yok")
    dogru("alanlar bulundu", len(b["alanlar"]) >= 15,
          f"yalnız {len(b['alanlar'])} alan")

    print("\n-- ölçek seçimi")
    esit("100x100 -> 400x214 alan", P.sigan_olcek(100, 100, 400, 214), 1.0)
    esit("1860x238", P.sigan_olcek(1860, 238, 400, 214), 1 / 5)
    esit("2480x233", P.sigan_olcek(2480, 233, 400, 214), 1 / 10)
    esit("hiç sığmaz", P.sigan_olcek(9e5, 9e5, 400, 214), None)
    esit("ölçek metni 1:10", P.olcek_metni(0.1), "1:10")
    esit("ölçek metni 1:1", P.olcek_metni(1.0), "1:1")
    esit("ölçek metni 2:1", P.olcek_metni(2.0), "2:1")
    dogru("ara ölçek üretilmez",
          P.sigan_olcek(1200, 100, 400, 214) in (1 / 5, 1 / 10),
          "standart dışı ölçek seçildi")

    print("\n-- kâğıt seçimi")
    al = P.antet_alanlari(b)
    esit("küçük parça A4", P.kagit_sec(200, 120, ("A4", "A3"), antet_alani=al), "A4")
    esit("orta parça A3", P.kagit_sec(350, 200, ("A4", "A3"), antet_alani=al), "A3")
    esit("uzun parça sığmaz",
         P.kagit_sec(1860, 238, ("A4", "A3"), antet_alani=al), None)

    print("\n-- 1:1 ÇİZİME DOKUNULMADI MI  (en önemli madde)")
    kck = ornek_cizim(os.path.join(kl, "kucuk.dxf"), 250.0, 140.0)
    uzn = ornek_cizim(os.path.join(kl, "uzun.dxf"), 1860.0, 238.0, delik=9)
    for yol, kagit in ((kck, "A4"), (uzn, "A2")):
        ad = os.path.basename(yol)
        bayt = hashlib.sha256(open(yol, "rb").read()).hexdigest()
        izi = model_parmak_izi(yol)
        cik = os.path.join(kl, "CIK", ad)
        r = P.pafta_kur(yol, antet, kagit,
                        {"KOD": "TEST-1", "AD": "DENEME PARÇASI",
                         "MALZEME": "S235JR", "CIZEN": "denetim"}, cik)
        esit(f"{ad}: kaynak dosya baytı",
             hashlib.sha256(open(yol, "rb").read()).hexdigest(), bayt)
        esit(f"{ad}: kopyanın model uzayı", model_parmak_izi(cik), izi)
        d = ezdxf.readfile(cik)
        pf = d.layout("PAFTA")
        esit(f"{ad}: kâğıt", P.pafta_olcusu(cik), P.KAGIT[kagit])
        vp = [e for e in pf if e.dxftype() == "VIEWPORT"
              and e.dxf.id != 1]
        esit(f"{ad}: pencere sayısı", len(vp), 1)
        v = vp[0]
        esit(f"{ad}: pencere ölçeği",
             round(v.dxf.height / v.dxf.view_height, 6), round(r["olcek"], 6))
        kalan = [e for e in pf if e.dxftype() in ("TEXT", "MTEXT")
                 and "<<" in (e.text if e.dxftype() == "MTEXT" else e.dxf.text)]
        esit(f"{ad}: doldurulmamış alan", len(kalan), 0)
        yazi = " ".join(e.text if e.dxftype() == "MTEXT" else e.dxf.text
                        for e in pf if e.dxftype() in ("TEXT", "MTEXT"))
        dogru(f"{ad}: kod antete yazıldı", "TEST-1" in yazi, yazi[:120])
        dogru(f"{ad}: ölçek antete yazıldı", r["olcek_metni"] in yazi, yazi[:120])
        dogru(f"{ad}: yardımcı dikdörtgen silindi",
              not any(e.dxf.layer.upper() == P.CIZIM_KATMAN for e in pf),
              "CIZIM_ALANI paftada kaldı")

    print("\n-- sığmayan kâğıt reddediliyor mu")
    try:
        P.pafta_kur(uzn, antet, "A4", {}, os.path.join(kl, "olmaz.dxf"),
                    olcek=1.0)
        hata.append("A4'e 1:1 sığmayan çizim kabul edildi")
        print("  HATA  1:1 sığmayan çizim A4'e yerleşti")
    except Exception as ex:
        print(f"  tamam reddedildi: {str(ex)[:70]}")
        dogru("uygun dosya yazılmadı",
              not os.path.exists(os.path.join(kl, "olmaz.dxf")),
              "hatalı pafta yine de yazıldı")

    print("\n-- antetsiz pafta")
    cik = os.path.join(kl, "antetsiz.dxf")
    r = P.pafta_kur(kck, None, "A4", {}, cik)
    esit("antetsiz ölçek", r["olcek"], 1.0)
    esit("antetsiz model uzayı", model_parmak_izi(cik), model_parmak_izi(kck))

    print("\n-- baskı")
    pdf = P.bas(os.path.join(kl, "CIK", "kucuk.dxf"),
                os.path.join(kl, "kucuk.pdf"), dpi=72)
    dogru("PDF üretildi", os.path.getsize(pdf) > 5000,
          f"{os.path.getsize(pdf)} bayt")

    print("\n-- kâğıda özel antet")
    ozel = os.path.join(kl, "ANTET_A3_A1.dxf")
    P.ornek_antet(ozel, "A1", "A1 ANTETİ")
    esit("A1 için özel antet",
         os.path.basename(P.antet_sec(os.path.join(kl, "ANTET_A3.dxf"), "A1")),
         "ANTET_A3_A1.dxf")
    esit("A2 için genel antet",
         os.path.basename(P.antet_sec(os.path.join(kl, "ANTET_A3.dxf"), "A2")),
         "ANTET_A3.dxf")
finally:
    shutil.rmtree(kl, ignore_errors=True)

print("\nSONUC:", "TUM DENETIMLER GECTI" if not hata
      else f"{len(hata)} HATA\n  " + "\n  ".join(hata))
sys.exit(1 if hata else 0)
