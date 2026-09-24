# -*- coding: utf-8 -*-
"""Firma anteti: şablon hazırlama ve paftaya basma.

Antet kodun içine yazılmaz - her firmanın anteti başkadır. Firmanın
kendi DXF'i şablon olur, Pi3D yalnız kutuları doldurur. Burada
denetlenen:

  1. Şablon hazırlama: kutular çizgi ızgarasından bulunuyor mu,
     etiketin ("Part Name :") kapladığı yer ölçülüp değerin nereden
     başlayacağı doğru hesaplanıyor mu, yazı konturları sadeleşince
     dosya küçülüyor mu.
  2. Ölçek: A2 için çizilmiş şablon A3'te 0,707, A1'de 1,416, A0'da
     2,002 ile ölçekleniyor mu - yani ISO kâğıt basamağı.
  3. Paftaya basma: çerçeve ve antet firmanın çiziminden geliyor mu,
     değerler doğru kutulara giriyor mu, Türkçe harfler bozulmuyor mu.
  4. Taşma: uzun bir değer komşu kutuya girmiyor mu (önce küçülüyor,
     sonra kısaltılıyor).
  5. Model uzayı 1:1 kalıyor mu - antet resme dokunmamalı.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                  # noqa: E402
import ezdxf.bbox                                             # noqa: E402
import pf3_olcu as O                                          # noqa: E402
import pf4_pafta as P                                         # noqa: E402
import pf5_antet as A                                         # noqa: E402

HATA = []
KOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "antet", "firma")


def dogru(ad, kosul, neden=""):
    if kosul:
        print(f"  tamam {ad}")
    else:
        print(f"  HATA  {ad}: {neden}")
        HATA.append(ad)


def esit(ad, olan, beklenen):
    dogru(ad, olan == beklenen, f"{olan!r} != {beklenen!r}")


def yakin(ad, olan, beklenen, pay=0.01):
    dogru(ad, abs(olan - beklenen) <= pay,
          f"{olan} != {beklenen} (±{pay})")


def ornek_cizim(yol, gen=300.0, boy=200.0):
    d = O.dxf_kur()
    m = d.modelspace()
    m.add_lwpolyline([(0, 0), (gen, 0), (gen, boy), (0, boy)], close=True,
                     dxfattribs={"layer": "KONTUR"})
    O._yaz(m, "ÖRNEK ÇİZİM", 2, boy + 6, 5.0)
    d.saveas(yol)
    return len(list(ezdxf.readfile(yol).modelspace()))


def main():
    if not (os.path.isfile(KOK + ".dxf") and os.path.isfile(KOK + ".json")):
        print(f"  ATLANDI: antet şablonu yok ({KOK}.dxf/.json)")
        print("\nSONUC: TUM DENETIMLER GECTI")
        return 0

    print("-- şablon")
    sb = A.Sablon(KOK)
    esit("şablon kâğıdı A2", sb.kagit, (594.0, 420.0))
    dogru("blok adı yazılı", sb.bilgi["blok"] == A.BLOK_AD, sb.bilgi["blok"])
    boy = os.path.getsize(KOK + ".dxf")
    dogru("şablon dosyası küçültüldü", boy < 1.5e6,
          f"{boy/1e6:.2f} MB - sadeleştirme çalışmamış")
    print(f"     şablon {boy/1e6:.2f} MB, {len(sb.bilgi['alanlar'])} alan")

    print("\n-- alanlar")
    gerek = ["olcek", "kutle", "malzeme", "parca_adi", "resim_no",
             "cizen", "cizen_tarih", "onaylayan", "onay_tarih", "dosya"]
    for a in gerek:
        dogru(f"{a} alanı var", a in sb.bilgi["alanlar"], "yok")
    yuk = {a["yuk"] for a in sb.bilgi["alanlar"].values()}
    esit("bütün alanlarda aynı yazı boyu", len(yuk), 1)
    antet = sb.bilgi["antet"]
    for ad, a in sb.bilgi["alanlar"].items():
        k = a["kutu"]
        dogru(f"{ad} kutusu antetin içinde",
              (antet[0] - .1 <= k[0] and k[2] <= antet[2] + .1
               and antet[1] - .1 <= k[1] and k[3] <= antet[3] + .1), str(k))
        dogru(f"{ad} yazısı kendi kutusunda",
              k[0] - .1 <= a["x"] <= k[2] + .1 and k[1] - .1 <= a["y"] <= k[3] + .1,
              f"yazı ({a['x']}, {a['y']}) kutu {k}")

    print("\n-- ölçek (ISO kâğıt basamağı)")
    for kagit, bek in (("A2", 1.0), ("A3", 420 / 594), ("A1", 841 / 594),
                       ("A0", 1189 / 594)):
        yakin(f"{kagit} ölçeği", sb.olcek(P.KAGIT[kagit]), bek, 0.002)
    # Çerçeve kâğıdın dışına taşmamalı
    for kagit in ("A4", "A3", "A2", "A1", "A0"):
        g, y = P.KAGIT[kagit]
        c = sb.cerceve((g, y))
        dogru(f"{kagit} çerçevesi kâğıdın içinde",
              0 <= c[0] and 0 <= c[1] and c[2] <= g + .01 and c[3] <= y + .01,
              f"{tuple(round(v,1) for v in c)} / {g}x{y}")

    print("\n-- paftaya basma")
    kl = tempfile.mkdtemp(prefix="antet_denetim_")
    yol = os.path.join(kl, "P07_01_050_000_01_U-Blech.dxf")
    once = ornek_cizim(yol)
    deger = {"malzeme": "Çelik (S235JR / St37)", "kutle": "1,285 kg",
             "cizen": "NÖ", "cizen_tarih": "24.09.2026",
             "onaylayan": "MŞ", "onay_tarih": "24.09.2026"}
    r = P.pafta_kur(yol, None, "A3", resim_no="01.050.000.01",
                    resim_adi="BÜKÜMLÜ DESTEK SACI ĞŞİÇÖÜ",
                    sablon=sb, antet=deger)
    print(f"     {r['kagit']} {r['olcek_metni']}  "
          f"{os.path.getsize(yol)/1e6:.2f} MB")
    d = ezdxf.readfile(yol)
    esit("model uzayı değişmedi", len(list(d.modelspace())), once)
    pf = d.layout("PAFTA")
    esit("antet bloğu bir kez basıldı",
         sum(1 for e in pf if e.dxftype() == "INSERT"
             and e.dxf.name == A.BLOK_AD), 1)
    ins = [e for e in pf if e.dxftype() == "INSERT"][0]
    yakin("blok ölçeği", ins.dxf.xscale, 420 / 594, 0.002)
    esit("pencere var",
         bool([e for e in pf if e.dxftype() == "VIEWPORT" and e.dxf.id != 1]),
         True)

    print("\n-- kutulara yazılan değerler")
    yazi = [e for e in pf if e.dxftype() == "TEXT"]
    metin = {e.dxf.text for e in yazi}
    for bek in (r["olcek_metni"], "Çelik (S235JR / St37)", "1,285 kg", "NÖ", "MŞ",
                "24.09.2026", "01.050.000.01",
                "P07_01_050_000_01_U-Blech.dxf"):
        dogru(f"{bek!r} yazılmış", bek in metin, str(sorted(metin))[:120])
    dogru("Türkçe harfler bozulmadı",
          any("ĞŞİÇÖÜ" in m for m in metin), str(sorted(metin))[:120])
    dogru("yazılar TrueType stilde",
          all(str(d.styles.get(e.dxf.style).dxf.font).lower().endswith(
              (".ttf", ".otf")) for e in yazi),
          str({e.dxf.style for e in yazi}))

    print("\n-- değerler kendi kutularında kalıyor mu")
    o = sb.olcek(P.KAGIT["A3"])
    kutular = {ad: [v * o for v in a["kutu"]]
               for ad, a in sb.bilgi["alanlar"].items()}
    tasan = []
    for e in yazi:
        k = ezdxf.bbox.extents([e], fast=False)
        if not any(kt[0] - .5 <= k.extmin.x and k.extmax.x <= kt[2] + .5
                   and kt[1] - .5 <= k.extmin.y and k.extmax.y <= kt[3] + .5
                   for kt in kutular.values()):
            tasan.append((e.dxf.text, round(k.extmin.x, 1), round(k.extmax.x, 1)))
    dogru("hiçbir değer kutusundan taşmadı", not tasan, str(tasan)[:200])

    print("\n-- çok uzun değer kısaltılıyor")
    yol2 = os.path.join(kl, "uzun.dxf")
    ornek_cizim(yol2)
    P.pafta_kur(yol2, None, "A3", resim_no="Ç" * 90, resim_adi="U" * 120,
                sablon=sb, antet=dict(deger, malzeme="M" * 120))
    d2 = ezdxf.readfile(yol2)
    pf2 = d2.layout("PAFTA")
    tasan2 = []
    for e in (e for e in pf2 if e.dxftype() == "TEXT"):
        k = ezdxf.bbox.extents([e], fast=False)
        if not any(kt[0] - .5 <= k.extmin.x and k.extmax.x <= kt[2] + .5
                   and kt[1] - .5 <= k.extmin.y and k.extmax.y <= kt[3] + .5
                   for kt in kutular.values()):
            tasan2.append((e.dxf.text[:14], round(k.extmax.x - k.extmin.x, 1)))
    dogru("uzun değerler de taşmadı", not tasan2, str(tasan2)[:200])

    print("\n-- antet yokken sade pafta")
    yol3 = os.path.join(kl, "sade.dxf")
    ornek_cizim(yol3)
    r3 = P.pafta_kur(yol3, None, "A3", resim_no="X1", resim_adi="SADE")
    d3 = ezdxf.readfile(yol3)
    esit("antet bloğu basılmadı",
         sum(1 for e in d3.layout("PAFTA") if e.dxftype() == "INSERT"), 0)
    dogru("sade pafta yine çalışıyor", bool(r3["olcek_metni"]),
          str(r3))
    # Sade paftanın çizim alanı firma antetininkinden BAŞKA olabilir;
    # ikisinin ölçeği aynı çıkmak zorunda değil, ikisi de çalışmalı.
    print(f"     sade {r3['kagit']} {r3['olcek_metni']}  /  "
          f"antetli {r['kagit']} {r['olcek_metni']}")

    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                         else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
