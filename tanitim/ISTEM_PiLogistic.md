# PiLogistic tanıtım görseli, slogan ve animasyonlu sunum

Sen bu depodaki **PiLogistic** (by PiVision) programı için çalışıyorsun. Önce depoyu incele: hangi ekranlar/sekmeler var, her biri ne yapıyor, program hangi süreleri/rakamları ölçüp gösteriyor. Aşağıdaki bilgiler başlangıç; koddan doğrula, yanlışsa düzelt.

**Ürün:** Lojistik yönetimi — tekliften tahsilata. Teklif, maliyet, onay, sefer, takip ve fatura tek zincirde. Kur teklif anında donar, marj korunur, kilometre taşını insan onaylar. Hiçbir rakam uydurulmaz.
**Bilinen özellikler:** İç istek → kişisel ekran → teklif talebi → maliyetlendirme → fiyat teklifi → sefer planlama → sevkiyat → faturalama → finans; **PiAgent** yapay zekâ (teklifi hazırlar, sapmayı gerekçesiyle önerir; fiyatı hesaplamaz, karar insanda); KPI canlı gösterge; Telegram canlı konum; ORS kamyon rotası; izlilik (her onay/ret/düzeltme kim·ne zaman·neden kayıtta); marj koruması (maliyetin altındaki teklif kaydedilmez, politika marjının altı GM'e gider); "uydurmaz" (kur/katsayı/km yoksa hesap durur ve sebebini söyler).
**Logolar:** ekte PiLogistic logosu ve PiVision logosu (saydam PNG — fon/filigran olacak).
**Slogan (görselde bu kullanılacak):** «Hızlı Teklif. Akıllı Fiyat. Anlık Yönetim.» — sarı vurgu satırı için bana 2-3 öneri de sun.
**Adımlar (çipler için, koddaki sıraya göre düzelt):** 1 TALEP · 2 MALİYET · 3 TEKLİF · 4 ONAY · 5 SEFER · 6 TAKİP · 7 FATURA · 8 FİNANS
**Güven slaytı için ölçülecekler:** marj altı teklif engeli, izlilik kaydı, PiAgent önerilerinin gerekçesi — hepsi gerçek bir örnek kayıtla gösterilsin.

## Ne istiyorum (Pi3D için yapılanın aynısı)

**1. Tanıtım görseli** — 1920×1080 PNG ve 4K (3840×2160) PNG
- Koyu lacivert zemin (radyal geçiş + ince ızgara), solda: ürün logosu + ürün adı + "BY PIVISION"; yeşil noktalı sarı üst satır; 3 satır büyük beyaz başlık + altında sarı vurgu satırı (SLOGAN); 2-3 satırlık açıklama.
- Sağda: programın **gerçek ekranları** hafif perspektifle eğik, üstlerinde beyaz çerçeveli hap etiketler ("BOM · MONTAJ AĞACI" gibi); sağ altta bir özellik kartı: 3 gerçek örnek + sarı şeritte ölçülmüş bir doğruluk/süre cümlesi.
- En altta 5 sütunlu şerit: 4 özellik (büyük harf başlık + 2 satır) + ürün tanımı.
- Arka planda silik (≈%10) ürüne ait bir çizim/ekran izi.

**2. Slogan** — 5 slogan önerisi yaz; görselde benim verdiğim sloganı kullan (aşağıda).

**3. Animasyonlu tanıtım sunumu** — seyreden kişi programın ne yaptığını ve ne kadar zaman kazandırdığını anlamalı:
- ≈18 slayt, ≈2,5 dakika, kendiliğinden akar ve başa döner. Üç biçim: **MP4 video** (1920×1080, 30 kare/sn), **PowerPoint** (düzenlenebilir yazılar, geçişler, giriş animasyonları, kendiliğinden ilerleme, konuşmacı notları), **HTML** (tarayıcıda; ok tuşları/boşluk/tıklama; zip + OKU.txt).
- Fon: **PiVision logosu** (saydam PNG) büyük ve silik filigran (%5), yavaşça kayar; her slaytta sol üstte ürün logosu + ad + "BY PIVISION"; sağ üstte adım çipleri (1 … 8), o anki adım sarı.
- Slaytlar: kapak (logo patlayarak, başlık satırları kayarak, sarı slogan patlayarak, PiVision logosu) → "gerçek bir iş, şu kadar sürede" rakam slaytı (4 kart, rakamlar 0'dan sayarak) → her işlev için bir **adım slaytı** (eğik ekran görüntüsü yandan uçar, yavaş yakınlaşır; önemli yerler **sarı vurgu kutusuyla patlayarak** işaretlenir ve yanında sarı etiket; sağda/solda rozet "ADIM n · AD", başlık, 3 madde tek tek gelir, yeşil süre çipi "⏱ …") → çıktılar/klasör slaytı (3 ekran üst üste patlar) → işlem süreleri çubuk grafiği + toplam → güven slaytı (3 büyük istatistik kartı + 3 örnek satırı) → kapanış (logolar + slogan).
- Geçişler sırayla değişsin: kayma, patlama (büyüyerek), yukarı kayma, yakınlaşma.

## Nasıl (Pi3D'de denenmiş yol — ekteki `tanitim_araci.zip`)

Ekteki paketi aç, önce `OKU.md`'yi oku ve **aynı araçları kullan** (sıfırdan yazma):
`sunum/uret.py` (slayt listesi → HTML; tek zaman çizelgesi, `ciz(t)` ile kare kare çizilebilir), `sunum.css`, `oynat.js`, `kare.js` (önizleme kareleri), `video.js` (Playwright ile kare kare + ffmpeg/libx264), `fon.js` + `gorsel_hazirla.py`, `pptx_uret.js` (pptxgenjs) + `animasyon.py` (PowerPoint'e geçiş ve giriş animasyonu XML'i ekler), `afis/afis.html` (afiş şablonu).
Yalnız `uret.py` başındaki URUN / KAPAK / SLOGAN / KAPANIS / ADIMLAR / SLAYT içeriğini ve `afis.html` metin/görsellerini bu ürüne göre değiştir. Vurgu kutuları görüntünün piksel koordinatıyla verilir: her ekranı açıp gerçekten önemli yeri (buton, sütun, özet satırı) ölç.
`OKU.md`'deki **Tuzaklar** bölümünü uygula: yerel yazı tipi, başsız Chrome'da 1920×1300 açıp kırpma, pptxgenjs'te punto = px/2 ve margin sırası [sol, sağ, alt, üst], küçük logo/JPG fon (yoksa PowerPoint 34 MB olur), video crf 27 ile 30 MB altına, LibreOffice Impress kurulumu.

## Kurallar

- **Her rakam ölçülmüş olmalı**: programın kendi süre paneli/günlüğü/test çıktısı ya da benim ekran görüntülerimdeki değerler. Uydurma rakam yok. Karşılaştırma varsayımsa öyle yaz ("elle … desek").
- **Ekranlar gerçek olsun**: ekteki ekran görüntülerimi kullan; eksik ekran varsa programı gerçek (örnek) veriyle çalıştırıp kendin al (xvfb + `import -window root`). Uydurma arayüz çizme.
- Müşteriye ait logo/antet/isim görünmesin; görünüyorsa kırp ve bana söyle.
- Ekranlarda **hata** görürsen (bozuk Türkçe karakter, yanlış değer…) vitrine koyma; en sonda bana listele.
- Tüm metinler Türkçe; her ekranın **ne işe yaradığı** ve **ne kadar zaman kazandırdığı** yazsın.
- **Kalite kontrol:** her slaytın son hâlini ve geçiş ortasını kareye alıp bak; PowerPoint'i `validate.py` ile doğrula ve LibreOffice ile görüntüye çevirip taşma/üst üste binme kontrol et; videodan birkaç kare çıkarıp animasyonu doğrula.
- Teslim: afiş (1920×1080 + 4K), MP4, PPTX, HTML zip — **her dosya 30 MB altında** — ve 5 slogan önerisi. Bitince tek mesajda özetle: ne yaptın, hangi rakam nereden geldi, gördüğün hatalar.
