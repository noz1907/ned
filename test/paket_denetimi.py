# -*- coding: utf-8 -*-
"""Paketleme denetimleri: exe'de patlayan, kaynakta patlamayan şeyler.

Buradaki üç kusur da yalnız DERLENMİŞ sürümde görülüyordu; kaynaktan
çalışırken hiçbiri belli olmuyordu:

  1. matplotlib arka ucunu ADIYLA, çalışma anında yükler: fig.savefig
     bir ".pdf" görünce backend_pdf'i import eder. PyInstaller statik
     tarama yaptığı için bunu göremez; spec'te yalnız backend_agg
     yazılıydı ve exe'de her PDF
       No module named 'matplotlib.backends.backend_pdf'
     veriyordu.
  2. Antet şablonu exe içinde sys._MEIPASS altındadır. Kod onun BİR
     ÜSTÜNE bakıyordu; gömülü antet hiç bulunamıyor, 7. adımda tarih /
     çizen / onaylayan kutuları hiç açılmıyordu.
  3. "İptal ile durdurabilirsiniz" yazısı 90 saniye sonra çıkıyordu
     ama İptal düğmesi yalnız 5. sayfadaydı: 6 ve 7. adımda ortada
     basılacak bir şey yoktu.

Ayrıca spec'in Qt/GTK/wx arka uçlarını sürüklemediği denetlenir - onlar
PyQt kurmaya kalkar ve paketi şişirir.
"""
import os
import re
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

HATA = []


def dogru(ad, kosul, neden=""):
    if kosul:
        print(f"  tamam {ad}")
    else:
        print(f"  HATA  {ad}: {neden}")
        HATA.append(ad)


def oku(ad):
    with open(os.path.join(KOK, ad), encoding="utf-8") as f:
        return f.read()


def main():
    print("-- matplotlib arka uçları (PDF)")
    spec = oku("pi3d.spec")
    for m in ("backend_agg", "backend_pdf"):
        dogru(f"{m} spec'te yazılı", f'"matplotlib.backends.{m}"' in spec,
              "PyInstaller bunu kendiliğinden bulamaz")
    # Yorum satırında adı geçebilir; aranan GERÇEK ÇAĞRIDIR.
    dogru("Qt/GTK/wx arka uçları toplanmıyor",
          re.search(r"^[^#\n]*collect_submodules\s*\(", spec, re.M) is None,
          "collect_submodules Qt ve GTK arka uçlarını da getirir")
    import matplotlib.backends.backend_pdf              # noqa: F401
    dogru("backend_pdf bu ortamda var", True)

    # Gerçekten PDF basılabiliyor mu: DXF -> pafta -> PDF
    import tempfile
    import pf3_olcu as O
    import pf4_pafta as P
    kl = tempfile.mkdtemp(prefix="paket_denetim_")
    yol = os.path.join(kl, "P01_DENEME.dxf")
    d = O.dxf_kur()
    d.modelspace().add_lwpolyline([(0, 0), (200, 0), (200, 120), (0, 120)],
                                  close=True, dxfattribs={"layer": "KONTUR"})
    d.saveas(yol)
    P.pafta_kur(yol, None, "A3", resim_no="X1", resim_adi="DENEME")
    pdf = P.bas(yol, os.path.join(kl, "P01_DENEME_A3.pdf"))
    dogru("PDF gerçekten üretildi",
          os.path.isfile(pdf) and os.path.getsize(pdf) > 1000,
          f"{pdf} yok ya da boş")
    with open(pdf, "rb") as f:
        dogru("PDF başlığı doğru", f.read(5) == b"%PDF-", "PDF değil")

    print("\n-- antet şablonunun aranması")
    gui = oku("pf3_gui.py")
    dogru("exe'de _MEIPASS'in KENDİSİNE bakılıyor",
          "os.path.join(sys._MEIPASS" in gui,
          "dirname(_MEIPASS) bir üst klasördür, gömülü antet orada değil")
    dogru("exe'nin yanına da bakılıyor",
          "os.path.dirname(os.path.abspath(sys.executable))" in gui,
          "kullanıcı anteti exe'nin yanına koyabilmeli")
    dogru("antet exe'ye gömülüyor", '("antet/*", "antet")' in spec,
          "FIRMA sürümünde antet pakete girmeli")
    # Şablon varsa gerçekten bulunmalı
    if os.path.isdir(os.path.join(KOK, "antet")):
        import pf5_antet as PA
        sb = PA.sablon_bul(os.path.join(KOK, "antet"))
        dogru("antet/ klasöründeki şablon bulunuyor", sb is not None,
              "sablon_bul None döndü")
        if sb is not None:
            for a in ("cizen", "onaylayan", "cizen_tarih", "onay_tarih"):
                dogru(f"{a} alanı şablonda var", a in sb.bilgi["alanlar"],
                      "kullanıcıdan sorulan alan eksik")

    print("\n-- İptal düğmesi")
    dogru("İptal ortak durum çubuğunda",
          "_durum_cubugu" in gui and "def _durum_cubugu" in gui,
          "düğme hâlâ tek bir sayfada")
    # Düğme, sayfalar kurulmadan ÖNCE var olmalı
    i_cubuk = gui.index("self._durum_cubugu()")
    i_sayfa = gui.index("self._sayfa1()")
    dogru("düğme sayfalardan önce kuruluyor", i_cubuk < i_sayfa,
          "_basla sayfa kurulurken düğmeyi bulamayabilir")
    dogru("5. sayfada ikinci bir İptal kalmadı",
          gui.count('command=self.iptal') == 1,
          "iki İptal düğmesi var")
    # İşler iptali dinliyor mu
    for fn in ("_pafta_is", "_bas_is", "_tarama_is"):
        g = gui[gui.index(f"def {fn}("):]
        g = g[:g.index("\n    def ", 5)]
        dogru(f"{fn} iptali dinliyor", "iptal_istendi" in g,
              "kullanıcı İPTAL deyince durmaz")
    pafta = oku("pf4_pafta.py")
    dogru("kagit_plani iptali dinliyor",
          re.search(r"def kagit_plani\(.*dur=None", pafta) is not None,
          "uzun listede İPTAL işlemez")
    dogru("uzun iş mesajı hâlâ İptal'den söz ediyor",
          "İptal ile durdurabilirsiniz" in gui,
          "mesaj kalkmışsa bu denetim güncellenmeli")

    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                         else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
