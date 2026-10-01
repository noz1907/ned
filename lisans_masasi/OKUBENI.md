# Pi3D Lisans Masası (PiVision içi — müşteriye GİTMEZ)

Pi3D lisansları PiProduct ile **aynı özel anahtarla** (`keys/pivision_private.key`,
PiProduct Key Manager'ın anahtarı) imzalanır. Üründeki açık anahtar
`pf17_lisans.PUBLIC_KEY_HEX` = `cf58062f…c2b29675` (keys/public_key.txt).

## Akış
1. Müşteri Pi3D'yi kurar, **Yardım > Lisans** ekranındaki `PI3D-XXXX-XXXX-XXXX`
   makine kimliğini gönderir.
2. Lisans masası:
   ```
   set PIVISION_KEYS=C:\PiVision_KeyManager\keys
   py lisans_masasi\pi3d_lisans_cli.py --imzala --paket DENEME --firma "FIRMA" --makine PI3D-... --cikti pi3d.lic
   py lisans_masasi\pi3d_lisans_cli.py --imzala --paket TAM    --firma "FIRMA" --makine PI3D-... --cikti pi3d.lic
   ```
3. Müşteri `pi3d.lic` dosyasını Pi3D'de **Yardım > Lisans > Lisans dosyasını yükle**
   ile seçer (ya da `Pi3D.exe`'nin yanına kopyalar).

## Paketler
| paket | kapsam | sınır |
|---|---|---|
| DENEME | bütün modüller | **8 farklı model** (STEP); 9. model kilitlenir. `--veri` ile değişir, `--gun` ile gün sınırı eklenir |
| TAM | bütün modüller | süresiz; `--sure YYYY-AA-GG` ile tarihli |
| A_LISANS | açınım + pafta + lazer | isteğe bağlı |

Deneme sayacı müşterinin bilgisayarında `%LOCALAPPDATA%\Pi3D\deneme.json`
dosyasındadır (imza + makine ile HMAC'li; silinir / kurcalanırsa deneme biter).
Yeni bir deneme ancak yeni bir imzayla (yeni .lic) başlar.

## Key Manager ile üretmek
PiProduct Key Manager makine kodunu `PIPR-` ile başlatıyor; Pi3D kodu `PI3D-`
ile başlar. Key Manager'dan üretmek için `app/core/licensing.py` içindeki
`validate()`'te `PIPR-` denetimine `PI3D-` eklenir ve `product: "Pi3D"` alanı
yazılır; aksi hâlde bu CLI kullanılır (aynı anahtar, aynı imza).

Bu klasör ve `keys/` paket / kurulum dosyasına girmez (exebuild.py bariyeri).
