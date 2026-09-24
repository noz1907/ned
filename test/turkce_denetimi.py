# -*- coding: utf-8 -*-
"""Türkçe harf denetimi: Ğ Ş İ Ç Ö Ü çizimde doğru görünüyor mu?

Sorun kodlama değildir. DXF R2010 dosyası UTF-8'dir ve "Ğ" dosyaya
gerçekten iki bayt (C4 9E) olarak yazılır - bunu aşağıda ölçüyoruz.
Kusur FONTTADIR: AutoCAD yazıyı STİLİN font dosyasıyla çizer ve hazır
"Standard" stili txt.shx'i gösterir. txt.shx bir SHX vektör fontudur,
içinde yalnızca ASCII glifleri vardır; Ğ Ş İ Ç Ö Ü karakterinin çizimi
yoktur, ekranda "?" ya da boş kutu çıkar.

Bu yüzden burada ÜÇ şey denetlenir:
  1. Dosya gerçekten UTF-8 ve harfler bozulmadan geri okunuyor mu,
  2. Bütün yazılar (ölçü yazıları dâhil) TrueType bir stile bağlı mı,
  3. Daha ÖNCE üretilmiş, Standard/txt stilli bir dosya pafta eklenirken
     kendiliğinden düzeliyor mu (turkce_duzelt).

Bu makinede AutoCAD fontları kurulu olmadığı için glifin ekrana
çizilişi ölçülemez; ölçülebilen, dosyanın hangi fontu istediğidir.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf                                                 # noqa: E402
import pf3_olcu as O                                         # noqa: E402
import pf4_pafta as P                                        # noqa: E402

HATA = []
METIN = "ĞÜŞİÖÇ ğüşıöç AÇINIM BÜKÜM KALINLIK Ø12 45°"


def dogru(ad, kosul, neden=""):
    if kosul:
        print(f"  tamam {ad}")
    else:
        print(f"  HATA  {ad}: {neden}")
        HATA.append(ad)


def esit(ad, olan, beklenen):
    dogru(ad, olan == beklenen, f"{olan!r} != {beklenen!r}")


def _ttf(d, stil):
    """Bu yazı stili Türkçe harfi olan bir TrueType font mu istiyor?"""
    try:
        f = (d.styles.get(stil).dxf.font or "").lower()
    except Exception:
        return False
    return f.endswith(".ttf") or f.endswith(".otf")


def _yazi_stilleri(d):
    """Çizimdeki bütün yazıların kullandığı stil adları."""
    ad = set()
    uzaylar = [d.modelspace()] + [d.layout(a) for a in d.layout_names()
                                  if a != "Model"]
    for uzay in uzaylar:
        for e in uzay:
            if e.dxftype() in ("TEXT", "MTEXT", "ATTRIB"):
                ad.add(e.dxf.get("style", "Standard"))
            elif e.dxftype() == "DIMENSION":
                for v in e.virtual_entities():
                    if v.dxftype() in ("TEXT", "MTEXT"):
                        ad.add(v.dxf.get("style", "Standard"))
    return ad


def yeni_cizim(yol):
    """Motorun ürettiği gibi bir çizim: yazı + ölçü."""
    d = O.dxf_kur()
    m = d.modelspace()
    m.add_lwpolyline([(0, 0), (170, 0), (170, 100), (0, 100)], close=True,
                     dxfattribs={"layer": "KONTUR"})
    O._yaz(m, METIN, 2, 105, 5.0)
    O.olcu_stili(d, 3.5)
    m.add_linear_dim(base=(0, -18), p1=(0, 0), p2=(170, 0),
                     dimstyle=O.OLCU_STILI).render()
    d.saveas(yol)


def eski_cizim(yol):
    """Eski sürümün ürettiği gibi: her şey Standard/txt."""
    d = ezdxf.new("R2010", setup=False)
    m = d.modelspace()
    m.add_lwpolyline([(0, 0), (150, 0), (150, 90), (0, 90)], close=True)
    m.add_text(METIN, height=5).set_placement((2, 95))
    st = d.dimstyles.add("PF_MM")
    st.dxf.dimlfac, st.dxf.dimtxt = 1.0, 3.0
    m.add_linear_dim(base=(0, -15), p1=(0, 0), p2=(150, 0),
                     dimstyle="PF_MM").render()
    d.saveas(yol)


def main():
    kl = tempfile.mkdtemp(prefix="pi3d_tr_")
    yeni = os.path.join(kl, "yeni.dxf")
    eski = os.path.join(kl, "eski.dxf")

    print("-- dosyanin kodlamasi")
    yeni_cizim(yeni)
    ham = open(yeni, "rb").read()
    try:
        ham.decode("utf-8")
        dogru("dosya bastan sona UTF-8", True)
    except UnicodeDecodeError as e:
        dogru("dosya bastan sona UTF-8", False, str(e))
    dogru("G harfi dosyada iki bayt (C4 9E)", b"\xc4\x9e" in ham,
          "UTF-8 karsiligi bulunamadi")
    d = ezdxf.readfile(yeni)
    t = d.modelspace().query("TEXT").first
    esit("metin bozulmadan geri okundu", t.dxf.text, METIN)

    print("\n-- yeni cizimin yazi fontu")
    dogru(f"{O.YAZI_STILI} stili var", O.YAZI_STILI in d.styles, "stil yok")
    st = d.styles.get(O.YAZI_STILI)
    dogru("TrueType font isteniyor",
          str(st.dxf.font).lower().endswith(".ttf"), f"font={st.dxf.font}")
    try:
        aile = st.get_extended_font_data()[0]
    except Exception as e:
        aile = f"okunamadi: {e}"
    dogru("font ailesi de yazili (XDATA)", aile == O.YAZI_AILESI, str(aile))
    stiller = _yazi_stilleri(d)
    dogru("butun yazilar TrueType stilde",
          all(_ttf(d, a) for a in stiller), f"stiller={sorted(stiller)}")
    esit("olcu yazisinin stili",
         d.dimstyles.get(O.OLCU_STILI).dxf.get("dimtxsty", ""), O.YAZI_STILI)
    dogru("hazir Standard stili ellenmedi",
          str(d.styles.get("Standard").dxf.font).lower() == "txt",
          "Standard degistirilmis: bu cizim baska dosyaya INSERT edilince "
          "oranin kendi yazilarini da degistirir")

    print("\n-- eski cizim pafta eklenirken duzeliyor mu")
    eski_cizim(eski)
    once = _yazi_stilleri(ezdxf.readfile(eski))
    dogru("once SHX stildeydi", not any(_ttf(ezdxf.readfile(eski), a)
                                        for a in once), f"stiller={once}")
    r = P.pafta_kur(eski, None, "A3", resim_no="ESKİ-1", resim_adi="ŞABLON ÖĞE")
    dogru("duzeltilen yazi sayisi bildirildi", r.get("yazi_duzeltildi", 0) > 0,
          str(r.get("yazi_duzeltildi")))
    q = ezdxf.readfile(eski)
    sonra = _yazi_stilleri(q)
    dogru("simdi hepsi TrueType stilde",
          all(_ttf(q, a) for a in sonra), f"stiller={sorted(sonra)}")
    esit("metin yine bozulmadi", q.modelspace().query("TEXT").first.dxf.text,
         METIN)

    print("\n-- paftanin kendi yazilari")
    pf = q.layout("PAFTA")
    pyazi = [e for e in pf if e.dxftype() == "TEXT"]
    dogru("paftada yazi var", bool(pyazi), "hic yazi yok")
    dogru("pafta yazilari da TrueType",
          all(_ttf(q, e.dxf.get("style", "Standard")) for e in pyazi),
          str({e.dxf.get("style", "Standard") for e in pyazi}))
    esit("Turkce resim no bozulmadan yazildi",
         any("ESKİ-1" == e.dxf.text for e in pyazi), True)

    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                         else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
