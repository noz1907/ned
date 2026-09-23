# -*- coding: utf-8 -*-
"""PAFTA denetimi.

İki madde pazarlık konusu değil, ikisi de burada ayrı ayrı doğrulanır:

  1. Pafta eklemek 1:1 çizimi DEĞİŞTİRMEZ. (Kaynak dosyanın baytı ve
     kopyanın model uzayının parmak izi karşılaştırılır. Parmak izine
     ÖLÇÜ DEĞERLERİ de girer: 1860 mm'lik bir parça 1:10 paftada da
     1860 ölçülmelidir - ölçek pencerenin işidir, rakamın değil.)
  2. Sağ alt köşedeki 150x100 mm antet alanına ASLA çizim girmez.
     (Pencerenin dikdörtgeni ile antet kutusu kesişmemeli.)

Kalanı: kenar payı, ölçek merdiveni, kâğıdın her zaman yatay olması,
sığmayanın reddedilmesi ve baskı.
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


def ornek_cizim(yol, gen, boy, delik=3, yazi=True):
    d = ezdxf.new(setup=True)
    d.header["$INSUNITS"] = 4
    d.header["$DIMLFAC"] = 1
    m = d.modelspace()
    m.add_lwpolyline([(0, 0), (gen, 0), (gen, boy), (0, boy)], close=True)
    for i in range(delik):
        m.add_circle((gen * (i + 1) / (delik + 1), boy / 2), min(5, boy / 8))
    m.add_linear_dim(base=(0, -boy / 5), p1=(0, 0), p2=(gen, 0)).render()
    m.add_linear_dim(base=(-gen / 10, 0), p1=(0, 0), p2=(0, boy),
                     angle=90).render()
    if yazi:
        m.add_text("1:1 CIZIM", height=max(boy / 30, 2)).set_placement(
            (0, boy + boy / 20))
    d.saveas(yol)
    return yol


def olculer(yol):
    """Model uzayındaki ölçü değerleri."""
    d = ezdxf.readfile(yol)
    v = []
    for e in d.modelspace():
        if e.dxftype() == "DIMENSION":
            try:
                v.append(round(e.get_measurement(), 4))
            except Exception:
                pass
    return sorted(v)


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
        elif t == "DIMENSION":
            try:
                p.append(("O", round(e.get_measurement(), 9), e.dxf.text))
            except Exception:
                p.append(("O", "okunamadi", e.dxf.text))
    # Ölçü çarpanı: 1 değilse CAD ölçüleri çarpar, rakamlar yalan söyler.
    p.append(("DIMLFAC", d.header.get("$DIMLFAC", 1.0)))
    p.append(("INSUNITS", d.header.get("$INSUNITS", 0)))
    return hashlib.sha256(repr(sorted(map(repr, p))).encode()).hexdigest()


def pencere(dxf_yolu, pafta_adi="PAFTA"):
    """Paftadaki çizim penceresinin kâğıt üstündeki dikdörtgeni."""
    d = ezdxf.readfile(dxf_yolu)
    lay = d.layout(pafta_adi)
    v = [e for e in lay if e.dxftype() == "VIEWPORT" and e.dxf.id != 1]
    if len(v) != 1:
        return None
    v = v[0]
    cx, cy = v.dxf.center.x, v.dxf.center.y
    g, y = v.dxf.width, v.dxf.height
    return (cx - g / 2, cy - y / 2, cx + g / 2, cy + y / 2)


def kesisir(a, b, pay=1e-6):
    return (a[0] < b[2] - pay and a[2] > b[0] + pay
            and a[1] < b[3] - pay and a[3] > b[1] + pay)


kl = tempfile.mkdtemp(prefix="pafta_denetim_")
try:
    print("\n-- kâğıt her zaman yatay")
    for k, (g, y) in P.KAGIT.items():
        dogru(f"{k} yatay", g > y, f"{g}x{y}")
    esit("A3 ölçüsü", P.KAGIT["A3"], (420.0, 297.0))
    esit("varsayılan kâğıt", P.VARSAYILAN_KAGIT, "A3")

    print("\n-- çerçeve ve antet alanı")
    esit("A3 çerçevesi", P.cerceve("A3"), (15.0, 15.0, 405.0, 282.0))
    esit("A3 antet kutusu", P.antet_kutusu("A3"), (255.0, 15.0, 405.0, 115.0))
    ak = P.antet_kutusu("A3")
    esit("antet eni", ak[2] - ak[0], 150.0)
    esit("antet boyu", ak[3] - ak[1], 100.0)
    a = P.cizim_alanlari("A3")
    esit("üstteki boşluk", (a["ust"][2] - a["ust"][0], a["ust"][3] - a["ust"][1]),
         (390.0, 167.0))
    esit("soldaki boşluk", (a["sol"][2] - a["sol"][0], a["sol"][3] - a["sol"][1]),
         (240.0, 267.0))
    for ad, r in a.items():
        dogru(f"{ad} boşluğu antete girmiyor", not kesisir(r, ak), str(r))

    print("\n-- ölçek merdiveni")
    esit("küçük parça 1:1", P.yerlesim(200, 150, "A3")["olcek"], 1.0)
    esit("yüksek parça sola oturur", P.yerlesim(200, 260, "A3")["yer"], "sol")
    esit("uzun parça üste oturur", P.yerlesim(1860, 238, "A3")["yer"], "ust")
    esit("1860x238 A3", P.yerlesim(1860, 238, "A3")["olcek"], 1 / 5)
    esit("2480x233 A3", P.yerlesim(2480, 233, "A3")["olcek"], 1 / 10)
    esit("kendiliğinden büyütme yok", P.yerlesim(20, 15, "A3")["olcek"], 1.0)
    esit("ölçek metni 1:10", P.olcek_metni(0.1), "1:10")
    esit("ölçek metni 1:1", P.olcek_metni(1.0), "1:1")
    dogru("ara ölçek üretilmez",
          all(abs(1 / P.yerlesim(g, 100, "A3")["olcek"]) in P.KUCULTME
              for g in (400, 700, 1500, 3000)), "standart dışı ölçek")
    esit("çok büyük parça", P.yerlesim(9e5, 9e5, "A3"), None)

    print("\n-- 1:1 ÇİZİME DOKUNULMADI MI  (1. madde)")
    ornekler = [("kucuk.dxf", 250.0, 140.0, "A3"),
                ("uzun.dxf", 1860.0, 238.0, "A3"),
                ("yuksek.dxf", 180.0, 255.0, "A3"),
                ("dev.dxf", 2480.0, 233.0, "A2")]
    for ad, g, b, kagit in ornekler:
        yol = ornek_cizim(os.path.join(kl, ad), g, b, delik=5)
        bayt = hashlib.sha256(open(yol, "rb").read()).hexdigest()
        izi = model_parmak_izi(yol)
        cik = os.path.join(kl, "CIK", ad)
        r = P.pafta_kur(yol, cik, kagit)
        esit(f"{ad}: kaynak dosya baytı",
             hashlib.sha256(open(yol, "rb").read()).hexdigest(), bayt)
        esit(f"{ad}: kopyanın model uzayı", model_parmak_izi(cik), izi)
        esit(f"{ad}: kâğıt", P.pafta_olcusu(cik), P.KAGIT[kagit])
        o1, o2 = olculer(yol), olculer(cik)
        dogru(f"{ad}: çizimde ölçü var", len(o1) >= 2, f"{len(o1)} ölçü")
        esit(f"{ad}: ölçü değerleri 1:1 kaldı", o2, o1)
        dogru(f"{ad}: gerçek boy okunuyor",
              any(abs(v - g) < 0.01 for v in o2),
              f"{g} mm parçada ölçüler {o2}")
        esit(f"{ad}: DIMLFAC",
             ezdxf.readfile(cik).header.get("$DIMLFAC", 1.0), 1.0)

        print(f"     -- {ad}: antet alanı korundu mu  (2. madde)")
        p = pencere(cik)
        dogru(f"{ad}: tek pencere", p is not None, "pencere sayısı 1 değil")
        if p:
            dogru(f"{ad}: antet alanına girmiyor",
                  not kesisir(p, P.antet_kutusu(kagit)),
                  f"pencere {tuple(round(v) for v in p)} antet "
                  f"{P.antet_kutusu(kagit)} ile kesişiyor")
            kg, ky = P.KAGIT[kagit]
            dogru(f"{ad}: kenardan 15 mm uzak",
                  (p[0] >= P.KENAR - 1e-6 and p[1] >= P.KENAR - 1e-6
                   and p[2] <= kg - P.KENAR + 1e-6
                   and p[3] <= ky - P.KENAR + 1e-6),
                  f"pencere {tuple(round(v, 1) for v in p)}")
            esit(f"{ad}: pencere eni = çizim x ölçek",
                 round(p[2] - p[0], 3), round(r["olcu"][0] * r["olcek"], 3))
        d = ezdxf.readfile(cik)
        pf = d.layout("PAFTA")
        vp = [e for e in pf if e.dxftype() == "VIEWPORT" and e.dxf.id != 1][0]
        esit(f"{ad}: pencere ölçeği",
             round(vp.dxf.height / vp.dxf.view_height, 6), round(r["olcek"], 6))

    print("\n-- sığmayan reddediliyor mu")
    uzn = os.path.join(kl, "uzun.dxf")
    for olcek, aciklama in ((1.0, "1:1 A3'e"), (0.5, "1:2 A3'e")):
        try:
            P.pafta_kur(uzn, os.path.join(kl, "olmaz.dxf"), "A3", olcek=olcek)
            hata.append(f"{aciklama} sığmayan çizim kabul edildi")
            print(f"  HATA  {aciklama} sığmayan çizim yerleşti")
        except P.PaftaYok as ex:
            print(f"  tamam {aciklama} reddedildi: {str(ex)[:60]}…")
    dogru("reddedilen dosya yazılmadı",
          not os.path.exists(os.path.join(kl, "olmaz.dxf")),
          "hatalı pafta yine de yazıldı")
    try:
        P.pafta_kur(uzn, os.path.join(kl, "x.dxf"), "A6")
        hata.append("bilinmeyen kâğıt kabul edildi")
    except P.PaftaYok:
        print("  tamam bilinmeyen kâğıt reddedildi")

    print("\n-- yazılar kırpılmıyor mu")
    y2 = ornek_cizim(os.path.join(kl, "yazili.dxf"), 300.0, 100.0)
    d = ezdxf.readfile(y2)
    m = d.modelspace()
    m.add_text("SAGA TASAN COK UZUN BIR NOT SATIRI", height=8).set_placement(
        (300, 50))
    d.saveas(y2)
    k = P.cizim_kutusu(y2)
    dogru("yazı sınıra katıldı", k[2] > 300.0 + 50,
          f"sınır {k[2]:.0f}, geometri 300'de bitiyor")

    print("\n-- baskı")
    pdf = P.bas(os.path.join(kl, "CIK", "kucuk.dxf"),
                os.path.join(kl, "kucuk.pdf"), dpi=72)
    dogru("PDF üretildi", os.path.getsize(pdf) > 5000,
          f"{os.path.getsize(pdf)} bayt")

    print("\n-- pafta içeriği")
    d = ezdxf.readfile(os.path.join(kl, "CIK", "kucuk.dxf"))
    pf = d.layout("PAFTA")
    kat = {e.dxf.layer for e in pf}
    for k in (P.KAT_CERCEVE, P.KAT_ANTET, P.KAT_BOLGE):
        dogru(f"{k} katmanı var", k in kat, f"katmanlar: {sorted(kat)}")
    harf = {e.dxf.text for e in pf if e.dxftype() == "TEXT"}
    dogru("bölge rakamları var", {"1", "8"} <= harf, str(sorted(harf))[:80])
    dogru("bölge harfleri var", {"A", "D"} <= harf, str(sorted(harf))[:80])
finally:
    shutil.rmtree(kl, ignore_errors=True)

print("\nSONUC:", "TUM DENETIMLER GECTI" if not hata
      else f"{len(hata)} HATA\n  " + "\n  ".join(hata))
sys.exit(1 if hata else 0)
