# Tanıtım aracı — afiş + animasyonlu sunum (MP4, PowerPoint, HTML)

Pi3D için yapıldı, her ürüne uyar. Tek bir zaman çizelgesinden üç çıktı:

| çıktı | ne |
|-------|----|
| `afis/afis.html` → PNG | 1920×1080 ve 4K tanıtım görseli |
| `sunum/out/Tanitim.html` | tarayıcıda kendiliğinden akan sunum (ok tuşları, boşluk, tıklama) |
| `sunum/out/Tanitim.mp4` | aynı sunumun videosu (30 kare/sn, 1920×1080) |
| `sunum/out/Tanitim.pptx` | düzenlenebilir PowerPoint: geçişler + giriş animasyonları + kendiliğinden ilerleme |

## Kurulum (bir kere)

```bash
pip install pillow imageio-ffmpeg pymupdf defusedxml lxml
cd sunum && npm install pptxgenjs          # önceden kuruluysa gerekmez
# video kaydı için Playwright + Chromium (Claude Code ortamında hazır:
#   /opt/node22/lib/node_modules/playwright, /opt/pw-browsers/chromium-*)
# PowerPoint'i görüntüye çevirip kontrol etmek için:
apt-get install -y libreoffice-impress
```

`kare.js`, `video.js`, `fon.js` içindeki `chromium-1194` yolu ortama göre değişebilir:
`ls /opt/pw-browsers` ile bakın.

## Adımlar

1. **Gerçek ekran görüntüleri.** Programı gerçek veriyle çalıştırın (xvfb +
   `import -window root -crop ...` ya da kullanıcının gönderdiği ekranlar).
   `sunum/out/g/` klasörüne koyun. Logolar:
   `g/urun.png` (ürün logosu, kare), `g/pivision.png` (PiVision, saydam PNG).
2. **İçerik:** `sunum/uret.py` başındaki `URUN`, `KAPAK`, `SLOGAN`, `KAPANIS`,
   `KAPANIS_LISTE`, `ADIMLAR` ve `SLAYT` listesi. Slayt tipleri:
   `kapak`, `rakam` (sayarak artan 4 rakam), `adim` (ekran + sarı vurgu kutuları +
   rozet + başlık + 3 madde + yeşil süre çipi), `resim`, `klasor` (3 ekran üst üste),
   `sure` (işlem süreleri çubuk grafiği), `guven` (3 istatistik kartı + 3 örnek),
   `kapanis`. Vurgu kutusu = görüntünün **piksel** koordinatı `(x0, y0, x1, y1)`.
3. `cd sunum && cp ../afis/font.css ../afis/*.woff2 out/ && python3 uret.py`
4. **Kontrol:** `mkdir -p qa && node kare.js onizle $PWD/qa` → her slaytın son hâli.
   Geçiş anı: `node kare.js an $PWD/qa 8300 26000` (ms).
5. **PowerPoint:**
   ```bash
   node fon.js && python3 gorsel_hazirla.py
   node pptx_uret.js && python3 animasyon.py out/Tanitim_ham.pptx out/Tanitim.pptx
   python3 <pptx-skill>/scripts/office/validate.py out/Tanitim.pptx
   ```
6. **Video:**
   ```bash
   export FFMPEG=$(python3 -c "import imageio_ffmpeg as f;print(f.get_ffmpeg_exe())")
   node video.js out/Tanitim_ham.mp4                       # ~8 dk, arka planda çalıştırın
   $FFMPEG -y -i out/Tanitim_ham.mp4 -c:v libx264 -preset slow -crf 27 \
           -pix_fmt yuv420p -movflags +faststart out/Tanitim.mp4   # 30 MB altına
   ```
7. **HTML paketi:** `out/Tanitim.html` + `out/g/` + yazı tipleri + bir OKU.txt → zip.
8. **Afiş:** `afis/afis.html` içindeki görselleri ve metinleri değiştirin, sonra
   ```bash
   chrome --headless=new --no-sandbox --hide-scrollbars --window-size=1920,1300 \
          --force-device-scale-factor=1 --virtual-time-budget=5000 \
          --screenshot=ham.png file://$PWD/afis.html     # sonra 1920x1080'e kırpın
   # 4K: --force-device-scale-factor=2, 3840x2160'a kırpın
   ```

## Tuzaklar (Pi3D'de yaşandı, tekrar yaşamayın)

- **Yazı tipi:** başsız Chrome proxy yüzünden Google Fonts'u indiremiyor
  (SSL hatası, sessizce yedek yazı tipine düşüyor). Yazı tipleri yerel: `font.css` + woff2.
- **Başsız Chrome ekran görüntüsü:** `--window-size=1920,1080` verince görüntü alanı
  daha kısa çıkıyor, alt kısım beyaz kalıyor. 1920×1300 açıp 1080'e kırpın.
- **pptxgenjs birimleri:** 1920 px = 13,333 inç → `in = px / 144`; yazı boyu
  **punto = px / 2**. HTML'deki px değerini punto diye yazarsanız her şey taşar.
- **pptxgenjs `margin` dizisi sırası [sol, sağ, alt, üst]** (beklenmedik). Yatay
  iç boşluk için `[14, 14, 0, 0]`; yoksa yazı kutunun dibine kayar.
- **pptxgenjs aynı resmi her slayta ayrı gömer.** Logo 1024 px ve fon PNG iken dosya
  34 MB oldu. `gorsel_hazirla.py` logoyu 300 px'e, fonu JPG'ye indirir (7 MB).
- **Gönderim sınırı 30 MB:** video önce crf 20 ile yazılır, sonra crf 27 ile
  sıkıştırılır (146 sn → 17 MB).
- **LibreOffice "source file could not be loaded":** dosya bozuk değil, Impress
  kurulu değildir → `apt-get install libreoffice-impress`.
- **Bekleme döngüsünde `pgrep -f`** kendi komut satırını da yakalar, döngü bitmez.
- **Müşterinin logosu/anteti** olan çizimleri antetsiz kırpın; başka firmanın logosu
  tanıtımda görünmesin.
- PowerPoint animasyonu: öğe adı `anim_<tip>_<gecikme ms>_<n>`; tipler `uc`
  (soldan uçar), `ucsag`, `alt`, `patla` (ortadan büyür), diğerleri solma.
  `animasyon.py` geçişi (`push`, `zoom`, `fade`, `cover`) ve `advTm` (kendiliğinden
  ilerleme) ekler; XML şema doğrulamasından geçer.

## İçerik ilkeleri

- **Her rakam ölçülmüş olmalı** (programın kendi süre paneli, günlüğü, test çıktısı).
  Varsayım varsa açıkça öyle yazılır: "Elle resim başına 15 dk desek: … ≈ 66 saat".
- Ekran görüntülerinde **hata** görürseniz vitrine koymayın; kullanıcıya bildirin.
- Metinler Türkçe; her ekranın **ne işe yaradığı** ve **ne kadar zaman kazandırdığı**
  yazılır.
