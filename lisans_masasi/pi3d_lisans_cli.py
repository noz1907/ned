# -*- coding: utf-8 -*-
"""Pi3D LİSANS MASASI (yalnız PiVision; MÜŞTERİYE GİTMEZ)
================================================================
PiProduct Key Manager ile AYNI özel anahtarı (keys/pivision_private.key)
ve aynı kanonik imza düzenini kullanır; Pi3D için .lic üretir / doğrular.

  python lisans_masasi/pi3d_lisans_cli.py --anahtar
  python lisans_masasi/pi3d_lisans_cli.py --imzala --paket DENEME --firma "NEVPA" \\
         --makine PI3D-1234-5678-9ABC --cikti pi3d.lic          (8 model)
  python lisans_masasi/pi3d_lisans_cli.py --imzala --paket TAM --firma "NEVPA" \\
         --makine PI3D-1234-5678-9ABC [--sure 2027-12-31] --cikti pi3d.lic
  python lisans_masasi/pi3d_lisans_cli.py --dogrula pi3d.lic
  python lisans_masasi/pi3d_lisans_cli.py --makine-kimligi     (bu bilgisayarın)

Anahtar klasörü: --keys <klasör> ya da PIVISION_KEYS ortam değişkeni ya da
bu dosyanın yanındaki keys/ (pivision_private.key + public_key.txt).

Paketler: DENEME (8 farklı model, bütün modüller) → TAM (süresiz, bütün
modüller; --sure ile tarihli). A_LISANS (açınım + pafta + lazer) isteğe bağlı.
"""
import argparse
import datetime
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import pf17_lisans as L                                        # noqa: E402


def keys_klasoru(a):
    for k in (a.keys, os.environ.get("PIVISION_KEYS"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")):
        if k and os.path.isfile(os.path.join(k, "pivision_private.key")):
            return k
    return None


def ozel_anahtar(klasor):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    ham = open(os.path.join(klasor, "pivision_private.key"), encoding="utf-8").read().strip()
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(ham))


def acik_hex(priv):
    from cryptography.hazmat.primitives import serialization
    return priv.public_key().public_bytes(serialization.Encoding.Raw,
                                          serialization.PublicFormat.Raw).hex()


def kur(paket, firma, makine, sure="", veri=None, gun=None):
    paket = (paket or "").upper().replace("-", "_")
    if paket not in L.PAKETLER:
        raise SystemExit("Paket DENEME | A_LISANS | TAM olmalı.")
    makine = (makine or "").strip().upper()
    if not makine.startswith(L.ON_EK) or len(makine) != 19:
        raise SystemExit("Makine kimliği PI3D-XXXX-XXXX-XXXX biçiminde olmalı "
                         "(müşterinin Yardım > Lisans ekranından).")
    if not (firma or "").strip():
        raise SystemExit("Firma adı boş olamaz.")
    ad, moduller = L.PAKETLER[paket]
    lic = {"type": "DENEME" if paket == "DENEME" else "LISANSLI",
           "customer": firma.strip(), "machine_id": makine, "product": L.URUN,
           "license_tier": ad, "moduller": list(moduller), "features": ["base"],
           "issued": datetime.date.today().isoformat()}
    if paket == "DENEME":
        lic["trial_data"] = int(veri or L.DENEME_DATA)
        if gun:
            lic["trial_days"] = int(gun)
    if sure:
        datetime.datetime.strptime(sure, "%Y-%m-%d")
        lic["expiry"] = sure
    return lic


def main():
    ap = argparse.ArgumentParser(description="Pi3D lisans masası (PiVision içi)")
    ap.add_argument("--keys", help="pivision_private.key klasörü")
    ap.add_argument("--anahtar", action="store_true", help="açık anahtar ve ürünle tutarlılık")
    ap.add_argument("--makine-kimligi", action="store_true", help="bu bilgisayarın PI3D-… kodu")
    ap.add_argument("--imzala", action="store_true")
    ap.add_argument("--dogrula", metavar="LIC")
    ap.add_argument("--paket", default="TAM", help="DENEME | A_LISANS | TAM")
    ap.add_argument("--firma", default="")
    ap.add_argument("--makine", default="")
    ap.add_argument("--sure", default="", metavar="YYYY-AA-GG", help="bitiş; boş = süresiz")
    ap.add_argument("--veri", type=int, default=None, help=f"DENEME: model sayısı (varsayılan {L.DENEME_DATA})")
    ap.add_argument("--gun", type=int, default=None, help="DENEME: ek gün sınırı (isteğe bağlı)")
    ap.add_argument("--cikti", default="pi3d.lic")
    a = ap.parse_args()

    if a.makine_kimligi:
        print(L.makine_kimligi())
        return 0
    if a.dogrula:
        veri = L.oku(a.dogrula)
        d = L.dogrula(veri, makine=str(veri.get("machine_id", "")).upper(), kayit=False)
        print("GEÇERLİ (imza ve alanlar)" if d["gecerli"] else "GEÇERSİZ: " + d["sebep"])
        print(json.dumps({k: v for k, v in veri.items() if k != "signature"},
                         ensure_ascii=False, indent=2))
        return 0 if d["gecerli"] else 1
    kl = keys_klasoru(a)
    if kl is None:
        print("HATA: özel anahtar bulunamadı (--keys <klasör> ya da PIVISION_KEYS).")
        return 2
    priv = ozel_anahtar(kl)
    pub = acik_hex(priv)
    if a.anahtar:
        print("Açık anahtar      :", pub)
        print("Üründeki (pf17)   :", L.PUBLIC_KEY_HEX)
        print("Tutarlı           :", "EVET" if pub == L.PUBLIC_KEY_HEX else "HAYIR - üretilen lisanslar reddedilir!")
        return 0 if pub == L.PUBLIC_KEY_HEX else 1
    if a.imzala:
        if pub != L.PUBLIC_KEY_HEX:
            print("HATA: bu özel anahtar üründeki açık anahtarla eşleşmiyor; lisans reddedilirdi.")
            return 1
        lic = kur(a.paket, a.firma, a.makine, a.sure, a.veri, a.gun)
        lic["signature"] = priv.sign(L.canonical_payload(lic)).hex()
        with open(a.cikti, "w", encoding="utf-8") as f:
            json.dump(lic, f, ensure_ascii=False, indent=2)
        geri = L.oku(a.cikti)
        d = L.dogrula(geri, makine=lic["machine_id"], kayit=False)
        if not d["gecerli"]:
            os.remove(a.cikti)
            print("HATA: yazılan dosya doğrulanamadı, silindi:", d["sebep"])
            return 1
        print(f"YAZILDI ve DOĞRULANDI: {a.cikti}")
        print(f"  {lic['type']} · {lic['license_tier']} · {lic['customer']} · {lic['machine_id']}")
        if lic["type"] == "DENEME":
            print(f"  deneme: {lic['trial_data']} farklı model" + (f", {lic['trial_days']} gün" if lic.get("trial_days") else ""))
        print("  bitiş:", lic.get("expiry", "SÜRESİZ"))
        print("Müşteri dosyayı Pi3D'de Yardım > Lisans > 'Lisans dosyasını yükle' ile seçer "
              "ya da Pi3D.exe'nin yanına pi3d.lic adıyla kopyalar.")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
