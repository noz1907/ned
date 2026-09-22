# Denetim betikleri

Bunlar "çalışıyor mu" değil, **doğru mu** diye bakar. Her biri sonucu
programdan bağımsız bir ölçüyle karşılaştırır.

| betik | ne denetler | nasıl çalıştırılır |
|-------|-------------|--------------------|
| `test_gizli_cizgi.py` | Görünen çizgiyle çakışan gizli çizgi çizilmiyor, çakışmayan bölüm çiziliyor. Parça orijinden metrelerce uzaktayken de aynı sonuç çıkıyor. | `python test/test_gizli_cizgi.py` |
| `dxf_gizli_denetle.py` | Üretilmiş bir DXF'te görünen kenarın üstünde kalan gizli çizgi var mı. Doğrusu: 0,00 mm. | `python test/dxf_gizli_denetle.py cikti/*.dxf` |
| `acilim_capraz_denetim.py` | Açınım ölçüsü doğru mu: açınım alanı × sac kalınlığı, parçanın gerçek hacmiyle karşılaştırılır. Fark yalnız deliklerin payı kadar olmalı (0 – %30). | `python test/acilim_capraz_denetim.py model.stp` |
| `gui_sayfa_kurulum.py` | tkinter kurulu olmayan makinede bile arayüzün altı sayfası hatasız kuruluyor mu. | `python test/gui_sayfa_kurulum.py` |

`test_gizli_cizgi.py` ve `gui_sayfa_kurulum.py` hata varsa 1 ile çıkar,
sürekli entegrasyona konabilir. Diğer ikisi sayı basar; sayıya siz bakarsınız.
