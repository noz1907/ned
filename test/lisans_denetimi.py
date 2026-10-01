# -*- coding: utf-8 -*-
"""Pi3D lisans (pf17_lisans): imza, makine, deneme veri sayısı, süre, saat.
Geçici anahtar çiftiyle çalışır; gerçek özel anahtar depoda yoktur.
    python test/lisans_denetimi.py
"""
import datetime
import json
import os
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
TMP = tempfile.mkdtemp(prefix="pi3d_lisans_")
os.environ["LOCALAPPDATA"] = TMP          # deneme.json ve pi3d.lic buraya
os.environ.pop("PROGRAMDATA", None)
import pf17_lisans as L                                            # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives import serialization           # noqa: E402

HATA = []


def kontrol(ad, sart, ek=""):
    print(("  tamam " if sart else "  HATA  ") + ad + ("" if sart else f"  {ek}"))
    if not sart:
        HATA.append(ad)


priv = Ed25519PrivateKey.generate()
L.PUBLIC_KEY_HEX = priv.public_key().public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
M = L.makine_kimligi()


def lic(**ek):
    d = {"type": "LISANSLI", "customer": "DENEME A.Ş.", "machine_id": M, "product": "Pi3D",
         "license_tier": "Tam", "moduller": L.PAKET_TAM, "features": ["base"],
         "issued": "2026-10-01"}
    d.update(ek)
    d["signature"] = priv.sign(L.canonical_payload(d)).hex()
    return d


def model(ad, icerik):
    y = os.path.join(TMP, ad)
    with open(y, "wb") as f:
        f.write(icerik)
    return y


print("1) makine kimliği ve imza")
kontrol("kimlik biçimi PI3D-XXXX-XXXX-XXXX", M.startswith("PI3D-") and len(M) == 19, M)
kontrol("kimlik kararlı", L.makine_kimligi() == M)
d = L.dogrula(lic(), kayit=False)
kontrol("geçerli lisans kabul", d["gecerli"], d["sebep"])
kontrol("modüller okundu", d["moduller"] == set(L.PAKET_TAM))
bozuk = lic(); bozuk["customer"] = "BAŞKASI"
kontrol("kurcalanmış dosya red", not L.dogrula(bozuk, kayit=False)["gecerli"])
kontrol("başka makine red", "başka bir makine" in L.dogrula(lic(machine_id="PI3D-0000-0000-0000"), kayit=False)["sebep"])
kontrol("PiProduct lisansı red", not L.dogrula(lic(product="PiProduct"), kayit=False)["gecerli"])
kontrol("süresi dolmuş red", "süresi dolmuş" in L.dogrula(lic(expiry="2020-01-01"), kayit=False)["sebep"])
kontrol("tarihli geçerli", L.dogrula(lic(expiry="2099-01-01"), kayit=False)["kalan_gun"] > 0)
# saf python doğrulama da aynı sonucu versin
d0 = lic()
kontrol("saf Python Ed25519 aynı sonuç", L._ed25519_dogrula_saf(
    bytes.fromhex(L.PUBLIC_KEY_HEX), bytes.fromhex(d0["signature"]), L.canonical_payload(d0)))

print("2) dosyadan yükleme ve kurma")
yol = os.path.join(TMP, "gelen.lic")
json.dump(lic(), open(yol, "w", encoding="utf-8"))
du = L.kur(yol)
kontrol("kur: geçerli", du["gecerli"], du["sebep"])
kontrol("kur: LOCALAPPDATA\\Pi3D\\pi3d.lic yazıldı", os.path.isfile(os.path.join(TMP, "Pi3D", "pi3d.lic")))
kontrol("modul_acik", L.modul_acik(du, "acinim") and not L.modul_acik(du, "yok"))
try:
    L.kur(yol[:-4] + "_bozuk.lic")
    kontrol("olmayan dosya hata verir", False)
except Exception:
    kontrol("olmayan dosya hata verir", True)

print("3) deneme: 8 farklı model, sonra kilit")
json.dump(lic(type="DENEME", license_tier="Deneme", trial_data=8),
          open(os.path.join(TMP, "Pi3D", "pi3d.lic"), "w", encoding="utf-8"))
try:
    os.remove(L._kayit_yolu())
except OSError:
    pass
du = L.yukle()
kontrol("deneme geçerli", du["gecerli"] and du["tip"] == "DENEME", du["sebep"])
kontrol("başlangıç 0 / 8", du["veri_kullanilan"] == 0 and du["veri_limit"] == 8)
izinler = []
for i in range(8):
    izin, n, lim = L.veri_izni(du, model(f"m{i}.stp", b"model %d" % i))
    izinler.append(izin)
kontrol("8 model işlendi", all(izinler) and n == 8, (izinler, n))
izin, n, lim = L.veri_izni(du, model("m3.stp", b"model 3"))
kontrol("aynı model yeniden: sayılmaz", izin and n == 8)
izin, n, lim = L.veri_izni(du, model("m9.stp", b"model 9"))
kontrol("9. model KİLİT", not izin and n == 8, (izin, n))
du2 = L.yukle()
kontrol("özette 8 / 8", "8 / 8" in L.ozet(du2), L.ozet(du2))
# kayıt kurcalanırsa deneme biter
k = json.load(open(L._kayit_yolu()))
k["veri"] = k["veri"][:2]
json.dump(k, open(L._kayit_yolu(), "w"))
du3 = L.yukle()
kontrol("kurcalanan deneme kaydı: kilit", not du3["gecerli"] and "kurcalan" in du3["sebep"], du3["sebep"])
# tam lisansa geçiş: deneme sayacı etkilemez
json.dump(lic(), open(os.path.join(TMP, "Pi3D", "pi3d.lic"), "w", encoding="utf-8"))
du4 = L.yukle()
kontrol("tam lisans: deneme sayacından bağımsız", du4["gecerli"] and L.veri_izni(du4, model("m9.stp", b"x"))[0])

print("4) sistem saati geri")
json.dump(lic(), open(os.path.join(TMP, "Pi3D", "pi3d.lic"), "w", encoding="utf-8"))
try:
    os.remove(L._kayit_yolu())
except OSError:
    pass
L.yukle(bugun=datetime.date(2030, 6, 1))
du5 = L.yukle(bugun=datetime.date(2030, 5, 20))
kontrol("saat 12 gün geri: kilit", not du5["gecerli"] and "saati" in du5["sebep"], du5["sebep"])
du6 = L.yukle(bugun=datetime.date(2030, 6, 2))
kontrol("saat ileri: geçerli", du6["gecerli"])

print()
if HATA:
    print(f"SONUC: {len(HATA)} HATA: " + ", ".join(HATA))
    sys.exit(1)
print("SONUC: TUM DENETIMLER GECTI")
