# -*- coding: utf-8 -*-
"""Pi3D LİSANS (makine bazlı, imzalı .lic) - ürün tarafı.

PiProduct ile aynı düzen: PiVision Lisans Masası (Key Manager) bir
`.lic` dosyası üretir, Ed25519 ile imzalar; ürün dosyayı AÇIK anahtarla
doğrular ve makine kimliğiyle karşılaştırır. Özel anahtar üründe YOKTUR.

  * Makine kimliği: PI3D-XXXX-XXXX-XXXX (Windows MachineGuid + bilgisayar
    adı + kullanıcı SID'siz; yoksa MAC) - Yardım > Lisans ekranında görünür,
    müşteri bu kodu Lisans Masası'na gönderir.
  * Lisans dosyası: pi3d.lic - exe'nin yanında, %PROGRAMDATA%\\Pi3D\\ ya da
    %LOCALAPPDATA%\\Pi3D\\ (program "Lisans dosyasını yükle" ile oraya
    kopyalar). İlk bulunan geçerli dosya kullanılır.
  * .lic şeması (imzalanan alanlar, Key Manager ile aynı kanonik JSON):
      type          LISANSLI | DENEME
      customer      firma
      machine_id    PI3D-XXXX-XXXX-XXXX
      product       "Pi3D"                 (Pi3D Lisans Masası yazar; yoksa kabul)
      license_tier  "Deneme" | "A Lisans" | "Tam"
      moduller      [acinim, pafta, lazer, kaynak, catia_bom, ai]
      features      ["base"]
      issued        YYYY-AA-GG
      trial_data    DENEME'de kaç FARKLI model (STEP) işlenebileceği (8)
      trial_days    DENEME'de gün sayısı (isteğe bağlı; ilk açılıştan)
      expiry        YYYY-AA-GG (yoksa süresiz)
      signature     Ed25519(canonical(payload)) hex - imzaya dahil değil
  * DENEME = VERİ SAYISI (kullanıcı kararı: "8 data deneme, sonra full
    lisans"): deneme lisansıyla en çok 8 FARKLI model (STEP) işlenir; aynı
    modeli yeniden açmak sayılmaz (dosya özetiyle tanınır). İşlenen
    modeller deneme.json'da tutulur (imza + makine ile HMAC'li; kurcalanırsa
    deneme biter). İsteğe bağlı gün sınırı da (trial_days) ilk açılıştan
    sayılır. Sistem saati geri alınırsa (son açılıştan 1 günden çok geri)
    lisans o gün kilitlenir.
  * Doğrulama 'cryptography' varsa onunla, yoksa saf Python Ed25519 ile
    (RFC 8032) yapılır - exe'de ek bağımlılık şart değil.
  * Modül kapısı: lisansta olmayan modül çalışmaz; temel akış (BOM,
    görünüş, detay resmi) her lisansta açıktır.
"""
from __future__ import annotations
import datetime
import hashlib
import hmac
import json
import os
import platform
import sys
import uuid

URUN = "Pi3D"
ON_EK = "PI3D-"
LISANS_DOSYA = "pi3d.lic"
#: PiVision açık anahtarı (Key Manager keys/public_key.txt ile BİREBİR aynı).
#: Değişirse eski bütün lisanslar geçersiz olur.
PUBLIC_KEY_HEX = "cf58062f7a99cef60a0fb004debee147ba83846c57e7fc12aad6e22dc2b29675"

MODULLER = {"acinim": "Açınım (bükümlü sac)", "pafta": "Pafta ve PDF",
            "lazer": "Lazer kesim dosyaları", "kaynak": "Kaynak resmi",
            "catia_bom": "CATIA BOM eşleştirme", "ai": "AI kontrol"}
PAKET_DENEME = list(MODULLER)
PAKET_A = ["acinim", "pafta", "lazer"]
PAKET_TAM = list(MODULLER)
PAKETLER = {"DENEME": ("Deneme", PAKET_DENEME), "A_LISANS": ("A Lisans", PAKET_A),
            "TAM": ("Tam", PAKET_TAM)}
DENEME_DATA = 8            # deneme lisansıyla işlenebilen farklı model sayısı
DENEME_GUN = 0             # 0 = gün sınırı yok (yalnız veri sayısı)
SAAT_GERI_GUN = 1          # son açılıştan bu kadar günden çok geri saat = kurcalama


# ------------------------------------------------------------ makine kimliği
def _ham_kimlik():
    parcalar = []
    if sys.platform.startswith("win"):
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                               0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            parcalar.append(str(winreg.QueryValueEx(k, "MachineGuid")[0]))
        except Exception:
            pass
    else:
        for y in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                with open(y) as f:
                    parcalar.append(f.read().strip())
                break
            except Exception:
                continue
    if not parcalar:
        parcalar.append(f"{uuid.getnode():012x}")
    parcalar.append(platform.node().strip().lower())
    return "|".join(p for p in parcalar if p)


def makine_kimligi():
    """PI3D-XXXX-XXXX-XXXX: donanım kimliğinin SHA-256 özeti (12 hex)."""
    h = hashlib.sha256(("Pi3D|" + _ham_kimlik()).encode("utf-8")).hexdigest().upper()
    return ON_EK + "-".join(h[i:i + 4] for i in (0, 4, 8))


# ------------------------------------------------------------ yollar
def _veri_klasoru():
    kok = (os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CONFIG_HOME")
           or os.path.join(os.path.expanduser("~"), ".config"))
    d = os.path.join(kok, "Pi3D")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.expanduser("~")
    return d


def program_klasoru():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def lisans_yollari():
    """Aranan sıra: exe'nin yanı, PROGRAMDATA, LOCALAPPDATA."""
    yollar = [os.path.join(program_klasoru(), LISANS_DOSYA)]
    pd = os.environ.get("PROGRAMDATA")
    if pd:
        yollar.append(os.path.join(pd, "Pi3D", LISANS_DOSYA))
    yollar.append(os.path.join(_veri_klasoru(), LISANS_DOSYA))
    return yollar


# ------------------------------------------------------------ imza
def canonical_payload(data):
    """Key Manager licensing.canonical_payload ile BİREBİR aynı."""
    payload = json.dumps({k: v for k, v in sorted(data.items()) if k != "signature"},
                         ensure_ascii=False, sort_keys=True)
    return payload.encode("utf-8")


def _ed25519_dogrula_saf(pub, sig, msg):
    """RFC 8032 Ed25519 doğrulama, saf Python (yalnız doğrulama; yavaş ama
    tek sefer çalışır). cryptography paketi yoksa kullanılır."""
    q = 2 ** 255 - 19
    L = 2 ** 252 + 27742317777372353535851937790883648493
    d = (-121665 * pow(121666, q - 2, q)) % q
    I = pow(2, (q - 1) // 4, q)

    def H(m):
        return hashlib.sha512(m).digest()

    def inv(x):
        return pow(x, q - 2, q)

    def xrecover(y):
        xx = (y * y - 1) * inv(d * y * y + 1)
        x = pow(xx, (q + 3) // 8, q)
        if (x * x - xx) % q != 0:
            x = (x * I) % q
        if x % 2 != 0:
            x = q - x
        return x

    def edwards_add(P, Q):
        x1, y1, z1, t1 = P
        x2, y2, z2, t2 = Q
        a = (y1 - x1) * (y2 - x2) % q
        b = (y1 + x1) * (y2 + x2) % q
        c = t1 * 2 * d * t2 % q
        dd = z1 * 2 * z2 % q
        e, f, g, h = b - a, dd - c, dd + c, b + a
        return (e * f % q, g * h % q, f * g % q, e * h % q)

    def scalarmult(P, e):
        Q = (0, 1, 1, 0)
        while e > 0:
            if e & 1:
                Q = edwards_add(Q, P)
            P = edwards_add(P, P)
            e >>= 1
        return Q

    def decodepoint(s):
        y = int.from_bytes(s, "little") & ((1 << 255) - 1)
        x = xrecover(y)
        if x & 1 != (s[31] >> 7):
            x = q - x
        P = (x, y, 1, (x * y) % q)
        if (-x * x + y * y - 1 - d * x * x * y * y) % q != 0:
            raise ValueError("nokta eğride değil")
        return P

    def encodepoint(P):
        x, y, z, _t = P
        zi = inv(z)
        x, y = (x * zi) % q, (y * zi) % q
        return (y | ((x & 1) << 255)).to_bytes(32, "little")

    if len(sig) != 64 or len(pub) != 32:
        return False
    Bx = xrecover(4 * inv(5) % q)
    B = (Bx, 4 * inv(5) % q, 1, (Bx * (4 * inv(5) % q)) % q)
    try:
        A = decodepoint(pub)
        R = decodepoint(sig[:32])
    except Exception:
        return False
    S = int.from_bytes(sig[32:], "little")
    if S >= L:
        return False
    h = int.from_bytes(H(sig[:32] + pub + msg), "little") % L
    sol = scalarmult(B, S)
    sag = edwards_add(R, scalarmult(A, h))
    return encodepoint(sol) == encodepoint(sag)


def imza_dogrula(sig_hex, payload, pub_hex=None):
    pub_hex = pub_hex or PUBLIC_KEY_HEX
    try:
        sig = bytes.fromhex(sig_hex or "")
        pub = bytes.fromhex(pub_hex)
    except ValueError:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        try:
            Ed25519PublicKey.from_public_bytes(pub).verify(sig, payload)
            return True
        except (InvalidSignature, ValueError):
            return False
    except Exception:
        return _ed25519_dogrula_saf(pub, sig, payload)


# ------------------------------------------------------------ deneme / saat kaydı
def _kayit_yolu():
    return os.path.join(_veri_klasoru(), "deneme.json")


def _kayit_mac(veri_imza, makine, icerik):
    anahtar = (veri_imza + "|" + makine).encode("utf-8")
    return hmac.new(anahtar, icerik.encode("utf-8"), hashlib.sha256).hexdigest()


def _kayit_oku(veri_imza, makine):
    try:
        with open(_kayit_yolu(), encoding="utf-8") as f:
            k = json.load(f)
        k.setdefault("veri", [])
        icerik = json.dumps({a: k[a] for a in ("imza", "ilk", "son", "veri")}, sort_keys=True)
        if k.get("imza") != veri_imza[:16] or not hmac.compare_digest(
                k.get("mac", ""), _kayit_mac(veri_imza, makine, icerik)):
            return None
        return k
    except Exception:
        return None


def _kayit_yaz(veri_imza, makine, ilk, son, veri=None):
    k = {"imza": veri_imza[:16], "ilk": ilk, "son": son, "veri": list(veri or [])}
    icerik = json.dumps(k, sort_keys=True)
    k["mac"] = _kayit_mac(veri_imza, makine, icerik)
    try:
        with open(_kayit_yolu(), "w", encoding="utf-8") as f:
            json.dump(k, f)
    except Exception:
        pass


# ------------------------------------------------------------ doğrulama
def dogrula(veri, makine=None, bugun=None, kayit=True):
    """Bir .lic sözlüğünü denetler. Döner:
    {gecerli, sebep, tip, paket, moduller(set), kalan_gun (None=süresiz),
     bitis, firma}"""
    bugun = bugun or datetime.date.today()
    makine = makine or makine_kimligi()
    out = {"gecerli": False, "sebep": "", "tip": str(veri.get("type", "")).upper(),
           "paket": veri.get("license_tier", ""), "moduller": set(),
           "kalan_gun": None, "bitis": "", "firma": veri.get("customer", "")}
    if not isinstance(veri, dict) or not veri.get("signature"):
        out["sebep"] = "Lisans dosyası boş ya da imzasız."
        return out
    if not imza_dogrula(veri.get("signature", ""), canonical_payload(veri)):
        out["sebep"] = ("İmza GEÇERSİZ: dosya kurcalanmış ya da başka bir anahtarla "
                        "imzalanmış.")
        return out
    if str(veri.get("product", URUN)) != URUN:
        out["sebep"] = f"Bu lisans {veri.get('product')} içindir, Pi3D için değil."
        return out
    mid = str(veri.get("machine_id", "")).strip().upper()
    if not mid.startswith(ON_EK):
        out["sebep"] = "Lisans Pi3D makine kimliği (PI3D-…) taşımıyor."
        return out
    if mid != makine:
        out["sebep"] = (f"Lisans başka bir makine için: {mid}. Bu bilgisayarın "
                        f"kimliği: {makine}.")
        return out
    if out["tip"] not in ("LISANSLI", "DENEME"):
        out["sebep"] = f"Bilinmeyen lisans tipi: {out['tip']}"
        return out
    out["moduller"] = {str(m).strip().lower() for m in (veri.get("moduller") or [])}
    exp = veri.get("expiry")
    if exp:
        try:
            bitis = datetime.datetime.strptime(exp, "%Y-%m-%d").date()
        except ValueError:
            out["sebep"] = f"Bitiş tarihi okunamadı: {exp}"
            return out
        out["bitis"] = exp
        out["kalan_gun"] = (bitis - bugun).days
        if bitis < bugun:
            out["sebep"] = f"Lisansın süresi dolmuş ({exp})."
            return out
    imza = str(veri.get("signature", ""))
    out["_imza"] = imza
    if kayit:
        k = _kayit_oku(imza, makine)
        if k is None:
            k = {"ilk": bugun.isoformat(), "son": bugun.isoformat()}
            if os.path.exists(_kayit_yolu()) and out["tip"] == "DENEME":
                # kayıt var ama bu lisansa / makineye ait değil ya da bozuk:
                # deneme kaydı silinip yeniden başlatılamaz
                try:
                    with open(_kayit_yolu(), encoding="utf-8") as f:
                        eski = json.load(f)
                    if eski.get("imza") == imza[:16]:
                        out["sebep"] = "Deneme kaydı kurcalanmış; deneme sona erdi."
                        return out
                except Exception:
                    pass
        try:
            son = datetime.date.fromisoformat(k["son"])
            if (son - bugun).days > SAAT_GERI_GUN:
                out["sebep"] = (f"Sistem saati geri alınmış (son açılış {k['son']}). "
                                "Saati düzeltin.")
                return out
        except Exception:
            pass
        k.setdefault("veri", [])
        if out["tip"] == "DENEME":
            limit = int(veri.get("trial_data") or DENEME_DATA)
            out["veri_limit"] = limit
            out["veri_kullanilan"] = len(k["veri"])
            out["veri_kalan"] = max(0, limit - len(k["veri"]))
            gun = int(veri.get("trial_days") or DENEME_GUN)
            if gun > 0:
                try:
                    ilk = datetime.date.fromisoformat(k["ilk"])
                except Exception:
                    ilk = bugun
                kalan = gun - (bugun - ilk).days
                out["kalan_gun"] = kalan if out["kalan_gun"] is None else min(out["kalan_gun"], kalan)
                out["bitis"] = (ilk + datetime.timedelta(days=gun)).isoformat()
                if kalan < 0:
                    out["sebep"] = f"Deneme süresi ({gun} gün) doldu: ilk açılış {k['ilk']}."
                    _kayit_yaz(imza, makine, k["ilk"], max(k["son"], bugun.isoformat()), k["veri"])
                    return out
        _kayit_yaz(imza, makine, k["ilk"], max(k.get("son", ""), bugun.isoformat()), k["veri"])
    out["gecerli"] = True
    return out


def _dosya_ozeti(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()[:20]


def veri_izni(durum, yol, kaydet=True):
    """DENEME lisansında yeni bir modelin işlenmesine izin var mı?
    Aynı dosya (içerik özeti) yeniden açılınca sayılmaz. Döner:
    (izin, kullanilan, limit). LISANSLI'da her zaman (True, 0, 0).
    kaydet=False: yalnız sorar, listeye eklemez."""
    if not durum or not durum.get("gecerli"):
        return False, 0, 0
    if durum.get("tip") != "DENEME":
        return True, 0, 0
    imza = str((durum.get("_imza") or ""))
    makine = durum.get("makine") or makine_kimligi()
    k = _kayit_oku(imza, makine)
    if k is None:
        return False, 0, int(durum.get("veri_limit") or DENEME_DATA)
    limit = int(durum.get("veri_limit") or DENEME_DATA)
    try:
        oz = _dosya_ozeti(yol)
    except Exception:
        oz = hashlib.sha256(os.path.abspath(yol).encode("utf-8")).hexdigest()[:20]
    if oz in k["veri"]:
        return True, len(k["veri"]), limit
    if len(k["veri"]) >= limit:
        return False, len(k["veri"]), limit
    if kaydet:
        k["veri"].append(oz)
        _kayit_yaz(imza, makine, k["ilk"], k["son"], k["veri"])
    return True, len(k["veri"]), limit


def oku(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def yukle(bugun=None):
    """Bütün aday yollardaki lisansları dener; ilk geçerliyi döner.
    Hiçbiri geçerli değilse en anlamlı sebep (dosya bulunduysa onun sebebi)."""
    makine = makine_kimligi()
    durum = {"gecerli": False, "sebep": "Lisans dosyası (pi3d.lic) bulunamadı.",
             "dosya": "", "makine": makine, "moduller": set(), "tip": "", "paket": "",
             "kalan_gun": None, "bitis": "", "firma": ""}
    for y in lisans_yollari():
        if not os.path.isfile(y):
            continue
        try:
            veri = oku(y)
        except Exception as e:
            durum.update(sebep=f"{y}: okunamadı ({e})", dosya=y)
            continue
        d = dogrula(veri, makine, bugun)
        d["dosya"] = y
        d["makine"] = makine
        if d["gecerli"]:
            return d
        durum.update(d)
    return durum


def kur(kaynak_yol):
    """Kullanıcının seçtiği .lic dosyasını doğrulayıp program verisine
    kopyalar (LOCALAPPDATA\\Pi3D\\pi3d.lic). Döner: yukle() sonucu."""
    veri = oku(kaynak_yol)
    d = dogrula(veri, kayit=False)
    if not d["gecerli"]:
        raise ValueError(d["sebep"])
    hedef = os.path.join(_veri_klasoru(), LISANS_DOSYA)
    with open(hedef, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    return yukle()


def modul_acik(durum, modul):
    return bool(durum and durum.get("gecerli") and modul in durum.get("moduller", ()))


def ozet(durum):
    if not durum.get("gecerli"):
        return f"LİSANS YOK - {durum.get('sebep', '')}"
    kalan = durum.get("kalan_gun")
    sure = ("süresiz" if kalan is None else
            f"{kalan} gün kaldı (bitiş {durum.get('bitis', '')})")
    if durum.get("tip") == "DENEME":
        sure = (f"deneme: {durum.get('veri_kullanilan', 0)} / {durum.get('veri_limit', DENEME_DATA)} "
                f"model işlendi" + ("" if kalan is None else f", {sure}"))
    mod = ", ".join(MODULLER.get(m, m) for m in sorted(durum.get("moduller", ())))
    return (f"{durum.get('tip', '')} · {durum.get('paket', '')} · {durum.get('firma', '')} · "
            f"{sure}\nModüller: {mod or '— (yalnız temel)'}")


if __name__ == "__main__":
    print("Makine kimliği:", makine_kimligi())
    d = yukle()
    print(ozet(d))
    print("Aranan yollar:", *lisans_yollari(), sep="\n  ")
