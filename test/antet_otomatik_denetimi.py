# -*- coding: utf-8 -*-
"""Firma anteti OTOMATİK TANIM (pf5_antet.otomatik_tanim) ve lisans / antet
kuralı.

Kullanıcı: "Lisans alınınca antet DXF'i A3 olarak istensin, analiz edilip
ayar olarak kaydedilsin; deneme sürümünde kesinlikle PiVision anteti."

Burada sentetik bir A3 antet DXF'i (çerçeve + sağ altta kutu ızgarası +
TEXT etiketler) üretilir ve denetlenir:
  1. kâğıt A3, çerçeve ve antet bloğu ölçülerek bulunuyor mu
  2. kutular ve etiketler okunuyor, alanlar anahtar kelimeden öneriliyor mu
     (Part Name, Drawing No, Material, Weight, Scale, Drawn/Checked +
     Date/Name sütunları, FILE)
  3. şablon geçici klasöre kuruluyor, Sablon ile paftaya basılıyor,
     değerler doğru kutulara giriyor mu
  4. lisans kuralı: DENEME ise firma anteti izinsiz, Pi3D anteti zorunlu;
     TAM ise izinli
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                  # noqa: E402
import pf5_antet as A                                         # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def sentetik_antet(yol):
    """A3 yatay: dış kenar 0..420 x 0..297, iç çerçeve 10 mm içeride,
    sağ altta 180 x 60 antet; kutular ve etiketler."""
    d = ezdxf.new("R2010", setup=True)
    m = d.modelspace()

    def kutu(x0, y0, x1, y1):
        m.add_line((x0, y0), (x1, y0)); m.add_line((x1, y0), (x1, y1))
        m.add_line((x1, y1), (x0, y1)); m.add_line((x0, y1), (x0, y0))

    def yaz(t, x, y, h=2.5):
        m.add_text(t, height=h).set_placement((x, y))
    kutu(0, 0, 420, 297)              # kâğıt kenarı
    kutu(10, 10, 410, 287)            # iç çerçeve
    ax0, ay0, ax1, ay1 = 230, 10, 410, 70
    kutu(ax0, ay0, ax1, ay1)
    # satırlar: y 70-55 başlık alanı; 55-45 malzeme/kütle; 45-35 ölçek/resim no; 35-10 çizen tablosu
    m.add_line((ax0, 55), (ax1, 55)); m.add_line((ax0, 45), (ax1, 45)); m.add_line((ax0, 35), (ax1, 35))
    m.add_line((320, 10), (320, 70))                       # orta düşey
    m.add_line((365, 45), (365, 55))                       # malzeme | kütle
    m.add_line((365, 35), (365, 45))                       # ölçek | resim no
    yaz("Part Name :", 322, 60); yaz("Material :", 322, 48); yaz("Weight :", 367, 48)
    yaz("Scale :", 322, 38); yaz("Drawing No. :", 367, 38)
    # sol: çizen tablosu (Date | Name başlıkları, Drawn / Checked satırları), FILE
    m.add_line((ax0, 30), (320, 30)); m.add_line((ax0, 25), (320, 25)); m.add_line((ax0, 20), (320, 20))
    m.add_line((260, 20), (260, 35)); m.add_line((290, 20), (290, 35))
    yaz("Date", 263, 31, 2.0); yaz("Name", 293, 31, 2.0)
    yaz("Drawn", 232, 26, 2.0); yaz("Checked", 232, 21, 2.0)
    yaz("FILE :", 232, 13, 2.0)
    m.add_line((ax0, 55), (320, 55))
    yaz("FIRMA LOGO", 240, 60, 4.0)
    d.saveas(yol)


def main():
    tmp = tempfile.mkdtemp(prefix="pi3d_antet_oto_")
    dxf = os.path.join(tmp, "firma_antet_A3.dxf")
    sentetik_antet(dxf)
    print("1) otomatik tanım")
    t = A.otomatik_tanim(dxf, log=lambda s: print("   " + s))
    dogru("kâğıt A3", t["kagit_ad"] == "A3", t["kagit_ad"])
    dogru("iç çerçeve 10 mm içeride",
          all(abs(a - b) < 0.6 for a, b in zip(t["cerceve"], (10, 10, 410, 287))), t["cerceve"])
    dogru("antet bloğu sağ altta 180 x 60",
          all(abs(a - b) < 1.0 for a, b in zip(t["antet"], (230, 10, 410, 70))), t["antet"])
    dogru("kutular bulundu (>= 10)", len(t["hucreler"]) >= 10, len(t["hucreler"]))
    et = t["etiketler"]; hc = t["hucreler"]; o = t["oneri"]

    def kutu_metni(alan):
        i = o.get(alan)
        return et[i] if i is not None else None
    print("   öneri:", {k: (round(hc[i][0]), round(hc[i][1]), et[i]) for k, i in o.items()})
    dogru("parça adı -> Part Name kutusu", "Part Name" in (kutu_metni("parca_adi") or ""), kutu_metni("parca_adi"))
    dogru("resim no -> Drawing No kutusu", "Drawing" in (kutu_metni("resim_no") or ""), kutu_metni("resim_no"))
    dogru("malzeme", "Material" in (kutu_metni("malzeme") or ""))
    dogru("kütle", "Weight" in (kutu_metni("kutle") or ""))
    dogru("ölçek", "Scale" in (kutu_metni("olcek") or ""))
    dogru("dosya", "FILE" in (kutu_metni("dosya") or ""))
    # Drawn satırı: Date ve Name sütunlarındaki BOŞ kutular
    ct, cz = o.get("cizen_tarih"), o.get("cizen")
    dogru("çizen tarih: Drawn satırı, Date sütunu (boş kutu)",
          ct is not None and not et[ct] and 260 <= hc[ct][0] <= 261 and 25 <= hc[ct][1] <= 26,
          (ct, hc[ct] if ct is not None else None))
    dogru("çizen: Drawn satırı, Name sütunu (boş kutu)",
          cz is not None and not et[cz] and 290 <= hc[cz][0] <= 291 and 25 <= hc[cz][1] <= 26,
          (cz, hc[cz] if cz is not None else None))
    ot, oz = o.get("onay_tarih"), o.get("onaylayan")
    dogru("onay tarih / onaylayan: Checked satırı",
          ot is not None and oz is not None and 20 <= hc[ot][1] <= 21 and 20 <= hc[oz][1] <= 21,
          (ot, oz))
    png = os.path.join(tmp, "onizleme.png")
    A.tanim_onizleme_png(t, png, o)
    dogru("önizleme PNG yazıldı", os.path.isfile(png) and os.path.getsize(png) > 1000)

    print("2) şablon kurma (geçici klasör) ve paftaya basma")
    import pf3_olcu as O
    eski_ayar = O.AYAR_DOSYA
    O.AYAR_DOSYA = os.path.join(tmp, "ayar.json")
    try:
        sb = A.sablon_kur(t, o, log=lambda s: print("   " + s), klasor=os.path.join(tmp, "antet"))
        dogru("şablon dosyaları", os.path.isfile(sb.kok + ".dxf") and os.path.isfile(sb.kok + ".json"))
        ay = json.load(open(O.AYAR_DOSYA, encoding="utf-8"))
        dogru("ayara kaydedildi", ay.get("antet_sablon") == sb.kok, ay.get("antet_sablon"))
        dogru("ayarlı şablon okunuyor", A.ayarli_sablon() is not None)
        dogru("kâğıt A3 ölçek 1", abs(sb.olcek((420, 297)) - 1.0) < 1e-9)
        # paftaya bas: boş bir DXF'e PAFTA düzeni (lisans TAM sayılır;
        # DENEME'de şablon yok sayılırdı, o kural 3. bölümde denetlenir)
        import pf4_pafta as PF
        A._LISANS["d"] = {"gecerli": True, "paket": "TAM"}
        ciz = os.path.join(tmp, "parca.dxf")
        d = O.dxf_kur(); d.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)
        O._yaz(d.modelspace(), "ÖRNEK", 2, 55, 4.0); d.saveas(ciz)
        r = PF.pafta_kur(ciz, None, "A3", resim_no="RES-001", resim_adi="ÖRNEK PARÇA",
                         sablon=sb, antet={"malzeme": "S235JR", "kutle": "1,25 kg",
                                           "cizen": "A.B", "cizen_tarih": "02.10.2026"})
        d2 = ezdxf.readfile(r["dosya"])
        lay = d2.layouts.get("PAFTA")
        yazilar = [e.dxf.text for e in lay.query("TEXT")]
        dogru("resim no antet kutusunda", "RES-001" in yazilar, yazilar[:12])
        dogru("parça adı", "ÖRNEK PARÇA" in yazilar)
        dogru("çizen", "A.B" in yazilar)
        dogru("blok referansı (firma anteti) var", any(e.dxftype() == "INSERT" for e in lay))
        A.sablon_kaldir()
        dogru("kaldırılınca ayar boş", A.ayarli_sablon() is None)
    finally:
        O.AYAR_DOSYA = eski_ayar

    print("3) lisans kuralı")
    dogru("DENEME: firma anteti izinsiz", not A.firma_anteti_izinli({"gecerli": True, "paket": "DENEME"}))
    dogru("lisans yok: izinsiz", not A.firma_anteti_izinli({"gecerli": False, "paket": "TAM"}))
    dogru("TAM: izinli", A.firma_anteti_izinli({"gecerli": True, "paket": "TAM"}))
    dogru("A_LISANS: izinli", A.firma_anteti_izinli({"gecerli": True, "paket": "A_LISANS"}))
    import pf4_pafta as PF
    A._LISANS["d"] = {"gecerli": True, "paket": "DENEME"}
    dogru("DENEME'de Pi3D anteti zorunlu (antet_pi3d: 0 olsa da)", PF.pi3d_antet_acik(0) is True)
    A._LISANS["d"] = {"gecerli": True, "paket": "TAM"}
    dogru("TAM'da antet_pi3d: 0 saygı görür", PF.pi3d_antet_acik(0) is False)
    A._LISANS.clear()
    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 0 if not HATA else 1


if __name__ == "__main__":
    sys.exit(main())
