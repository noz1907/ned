# Denetim betikleri

Bunlar "çalışıyor mu" değil, **doğru mu** diye bakar. Her biri sonucu
programdan bağımsız bir ölçüyle karşılaştırır.

| betik | ne denetler | nasıl çalıştırılır |
|-------|-------------|--------------------|
| `test_gizli_cizgi.py` | Görünen çizgiyle çakışan gizli çizgi çizilmiyor, çakışmayan bölüm çiziliyor. Parça orijinden metrelerce uzaktayken de aynı sonuç çıkıyor. | `python test/test_gizli_cizgi.py` |
| `dxf_gizli_denetle.py` | Üretilmiş bir DXF'te görünen kenarın üstünde kalan gizli çizgi var mı. Doğrusu: 0,00 mm. | `python test/dxf_gizli_denetle.py cikti/*.dxf` |
| `acilim_capraz_denetim.py` | Açınım doğru mu: (1) düzlemdeki alan × sac kalınlığı = parçanın gerçek hacmi, (2) kesitten çıkan genişlik = yüzeyden açılan konturun genişliği. Kesim konturu verilen parçalarda hacim farkı %3'ün altında olmalı. | `python test/acilim_capraz_denetim.py model.stp` |
| `pafta_denetimi.py` | **1:1 çizim pafta eklenince değişiyor mu** (kaynak dosyanın baytı, model uzayının parmak izi ve **ölçü değerleri** ayrı ayrı karşılaştırılır — 1860 mm'lik parça 1:10 paftada da 1860 ölçülmeli), **sağ alt köşedeki 150×100 mm antet alanına çizim girmiyor mu**, kenardan 15 mm pay korunuyor mu, ölçek standart merdivenden mi seçiliyor, sığmayan pafta reddediliyor mu, PDF çıkıyor mu. | `python test/pafta_denetimi.py` |
| `cizim_cakisma_denetimi.py` | Üretilmiş resimlerde **yazı yazının üstüne binmiş mi**, **yazı konturun üstüne binmiş mi**. Yazının kapladığı yer hesapla değil ÖLÇÜLEREK bulunur; ölçü blokları da açılıp içlerindeki yazı sayılır. Kontur denetimi **sınır kutusuyla değil, gerçek çizgi parçalarıyla** yapılır: uzun ince bir çokgenin kutusu bütün görünüşü kaplar ve içindeki her yazıyı yanlışlıkla "konturun üstünde" gösterir. Doğrusu ikisinde de sıfır. | `python test/cizim_cakisma_denetimi.py cikti`<br>Kendini sınar: `--kendini-dene` |
| `yontem_denetimi.py` | **Şerit genişliği** kapıları (prizmatik mi, alan × boy = hacim mi) ve parçanın abkantta bükülüp bükülemeyeceği doğru saptanıyor mu: kanat ve yarıçap sınırlarının iki yanı, gerçek parçalardan ölçülmüş değerler, sebebin yazılması ve sınırların ayarlanabilmesi. | `python test/yontem_denetimi.py` |
| `logo_denetimi.py` | Gömülü logolar `logo/` klasöründekilerle birebir aynı mı, gömülü modül yoksa klasöre düşüyor mu, ikisi de yoksa program çökmeden logosuz çalışıyor mu. | `python test/logo_denetimi.py` |
| `gui_pafta_denetimi.py` | 7. adım (PAFTA) **baştan sona**: klasör seç → Listeyi tazele → Tümünü seç → PAFTAYA AL → BAS. Paftanın ayrı bir kopyaya değil **resmin kendi dosyasına** yazıldığı, aynı dosya ikinci kez paftaya alınınca sekmelerin birikmediği, PDF'lerin `PDF` klasörüne `..._A3.pdf` adıyla çıktığı ve A4/A3/A2/A1/A0'ın hepsinin çalıştığı doğrulanır. İş parçacıkları sırayla çalıştırılır, tkinter gerekmez. | `python test/gui_pafta_denetimi.py` |
| `antet_denetimi.py` | **Firma anteti.** Şablon hazırlama (kutular çizgi ızgarasından bulunuyor mu, etiketin kapladığı yer ölçülüp değerin başlangıcı doğru hesaplanıyor mu, dosya sadeleşince küçülüyor mu), ölçek (A2 şablonu A3'te 0,707 / A1'de 1,416 / A0'da 2,002), paftaya basma (değerler doğru kutulara giriyor mu, Türkçe harfler bozuluyor mu, model uzayı 1:1 kalıyor mu) ve taşma (120 harflik bir malzeme adı komşu kutuya girmiyor mu). `antet/` klasörü yoksa atlanır. | `python test/antet_denetimi.py` |
| `sac_tarama_denetimi.py` | **Bükümlü parçaları program kendisi buluyor mu.** Bilerek kurulmuş katılarla: çeyrek büküm + iki kanattan L sac (bulunmalı), düz plaka (büküm yok), delikli plaka (delik büküm sanılmamalı), kalın blok ve kalın cidarlı küçük parça (sac değil). Taramanın açınım hesabından hızlı olduğu da ölçülür. | `python test/sac_tarama_denetimi.py` |
| `turkce_denetimi.py` | **Ğ Ş İ Ç Ö Ü** çizimde düzgün görünüyor mu. Dosyanın gerçekten UTF-8 olduğu ölçülür (sorun kodlamada değildir), sonra bütün yazıların — ölçü rakamları dâhil — SHX değil **TrueType** bir stile bağlı olduğu denetlenir; hazır `Standard` stiline dokunulmadığı da. Ayrıca eski sürümün ürettiği `Standard`/`txt` stilli bir dosyanın pafta eklenirken kendiliğinden düzeldiği sınanır. | `python test/turkce_denetimi.py` |
| `gui_sayfa_kurulum.py` | tkinter kurulu olmayan makinede bile arayüzün bütün sayfaları hatasız kuruluyor mu (sayfa sayısı kodda kaç ise o kadar). | `python test/gui_sayfa_kurulum.py` |
| `gui_cagri_denetimi.py` | Arayüzde çağrılan ama **tanımlanmayan** yöntem var mı. Sahada çıkan donma hatasını tam olarak bu yakalar. tkinter gerekmez. | `python test/gui_cagri_denetimi.py` |
| `gui_dongu_denetimi.py` | İş bitince sonuç ekrana gerçekten geliyor mu; arayüz donuyor mu. Sahte motorla, tkinter + X ekranı ister. | `xvfb-run -a python3 test/gui_dongu_denetimi.py` |

`test_gizli_cizgi.py`, `pafta_denetimi.py`, `logo_denetimi.py`,
`gui_sayfa_kurulum.py`, `gui_cagri_denetimi.py` ve `gui_dongu_denetimi.py`
hata varsa 1 ile çıkar, sürekli entegrasyona
konabilir (`gui_dongu_denetimi.py` ekran yoksa "atlandı" deyip 0 döner).
Diğer ikisi sayı basar; sayıya siz bakarsınız.

Hepsini bir arada:

```
python test/test_gizli_cizgi.py && python test/pafta_denetimi.py && \
python test/logo_denetimi.py && python test/gui_sayfa_kurulum.py && \
python test/gui_cagri_denetimi.py && python test/gui_dongu_denetimi.py
```
