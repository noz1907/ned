# -*- coding: utf-8 -*-
"""Logoları koda gömer: logo/ klasöründen pi3d_logo.py üretir.

NEDEN: exe'nin yanındaki logo klasörü silinebilir, değiştirilebilir.
Gömülen logo exe'nin içindedir; silmek için exe'yi silmek gerekir.

NE ZAMAN ÇALIŞTIRILIR: logo dosyalarını değiştirdiğinizde. Üretilen
pi3d_logo.py depoya konur; her derlemede yeniden üretmeye gerek yoktur.

    python logo_gom.py

Programın ekranda kullandığı dosyalar gömülür (aşağıdaki liste).
512 ve 1024 piksellik büyük resimler gömülmez: ekranda kullanılmıyorlar,
boşuna yer tutarlar.
"""
import base64
import os
import sys

KLASOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo")
CIKTI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pi3d_logo.py")

# Arayüzün gerçekten yüklediği dosyalar.
GOMULECEK = ["pi3d.ico", "pi3d_72.png", "pi3d_64.png", "pi3d_48.png",
             "pi3d_32.png", "pi3d_16.png",
             "pivision_64.png", "pivision_56.png", "pivision_44.png"]

BASLIK = '''# -*- coding: utf-8 -*-
"""Gömülü logolar. ELLE DÜZENLEMEYİN — logo_gom.py üretir.

Buradaki resimler programın içindedir; klasörden silinemezler.
Logosuz sürüm derlemek için bu dosyayı derlemeye katmayın
(pi3d.spec, PI3D_LOGO=0).
"""

LOGO = {
'''


def main():
    if not os.path.isdir(KLASOR):
        print(f"logo klasörü yok: {KLASOR}")
        return 1
    p = [BASLIK]
    top = 0
    for ad in GOMULECEK:
        y = os.path.join(KLASOR, ad)
        if not os.path.isfile(y):
            print(f"  atlandı (yok): {ad}")
            continue
        ham = open(y, "rb").read()
        b64 = base64.b64encode(ham).decode("ascii")
        top += len(ham)
        p.append(f'    "{ad}":\n        "')
        p.append('"\n        "'.join(b64[i:i + 96]
                                     for i in range(0, len(b64), 96)))
        p.append('",\n')
        print(f"  gömüldü: {ad:22s} {len(ham) // 1024:4d} KB")
    p.append("}\n")
    with open(CIKTI, "w", encoding="utf-8") as f:
        f.write("".join(p))
    print(f"\n{CIKTI}  ({os.path.getsize(CIKTI) // 1024} KB, "
          f"{top // 1024} KB resim)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
