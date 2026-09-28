# -*- coding: utf-8 -*-
"""AI MALZEME TANIMLAMA AJANI (isteğe bağlı): programın tanımlamasını
Claude'a KONTROL ETTİRİR, gerekirse düzeltme önerir.

Akış
  1. Program kendi bildiği kadar tanımlar (ad, montaj ağacı, geometri
     ölçümü, profil, öğrenilmiş kurallar).
  2. AI 1. tur (yazı): her parçanın kararını, kararın kaynağını ve
     programın ölçtüğü bulguları okur; "doğru / düzelt / belirsiz" der.
  3. AI 2. tur (GÖRÜNTÜ): 1. turda emin olamadığı ve programın zaten
     belirsiz bulduğu parçaların gölgelendirilmiş resmi (iki görünüş +
     ölçü) gönderilir; resme bakıp yeniden karar verir.
  4. Sonuç ÖNERİDİR: kullanıcı onaylayınca uygulanır ve program onu
     öğrenir (biçim imzası); bir daha sorulmaz.

Gönderilenler: parça adı, kodu, adedi, ölçüleri, programın bulguları
ve (2. turda) parçanın resmi. CAD dosyası gönderilmez. Veri Anthropic'e
gider - firma izni gerekir. Kullanıcının elle verdiği ve CAD'in
Made/Bought ile söylediği sınıflar kesindir, AI'a sorulmaz.

Maliyet her çalışmada GERÇEK kullanımdan hesaplanıp yazılır.
Anahtar: ANTHROPIC_API_KEY ortam değişkeni ya da ayar dosyası
("ai_anahtar"). Kurulum: pip install anthropic
"""
from __future__ import annotations

import base64
import json

import pf9_excel as XL

MODEL = "claude-opus-5"
YAZI_PARTI = 60                     # 1. turda bir istekte en çok parça
GORUNTU_PARTI = 20                  # 2. turda bir istekte en çok resim
EMIN = 0.8                          # bunun altındaki güven "emin değil"
# $ / 1M token (girdi, çıktı) - maliyet hesabı için
FIYAT = {"claude-opus-5": (5.0, 25.0), "claude-opus-5-5": (4.0, 20.0),
         "claude-sonnet-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0),
         "claude-fable-5-1": (10.0, 50.0)}

SISTEM = """Bir makine imalat firmasında ürün ağacı (BOM) uzmanısın. Bir \
bilgisayar programı 3B CAD modelindeki her parçayı "standart" (satın alınan \
hazır ürün) ya da "parca" (firmada üretilen) diye sınıfladı. Senin işin bu \
sınıflamayı KONTROL etmek.

standart: cıvata, somun, pul, perçin, perçin somun, yay, rulman, pim, \
segman, kelepçe, conta, o-ring, lastik geçme, menteşe, kilit, tampon, \
kulp, teker, motor, sensör, kablo bağı vb. katalogdan alınan ürünler.
parca: sac, profil, boru kesimi, lama, işlenmiş parça, döküm, kaynaklı parça.

Her parça için:
- karar: "dogru" (programın sınıfı doğru), "duzelt" (yanlış; doğru sınıfı \
ver) ya da "belirsiz" (bu bilgiyle karar verilemez).
- sinif: parçanın DOĞRU sınıfı ("standart" ya da "parca"); belirsizse \
programın sınıfını yaz.
- tip: Türkçe kısa tip ("mercimek başlı cıvata M8", "perçin somun M6", \
"kare kutu profil 17x25x2"); bilinmiyorsa boş.
- guven: 0-1; emin değilsen düşük ver.
- gerekce: kısa Türkçe; "dogru" ise en çok 8 kelime.

Kurallar:
- Parça numarası biçimindeki adlar (FT108161, 55460006192) bilgi taşımaz; \
bulgulara, ölçülere, adede ve varsa RESME bak. Aynı modelde üretim \
parçalarının numaraları çoğunlukla ortak önekle başlar; farklı aileden \
numara tedarikçi parçası işaretidir ama tek başına kanıt değildir.
- "program ölçtü" ile başlayan bulgular ölçümdür, güvenilirdir.
- Emin değilsen "belirsiz" de; uydurma. Yanlış "standart" kararı parçanın \
resminin hiç çizilmemesine, yanlış "parca" kararı satın alınacak parçanın \
imalata gitmesine yol açar.
- Her parçayı "no" alanıyla döndür; eksik parça bırakma."""

SEMA = {
    "type": "object",
    "properties": {
        "parcalar": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "no": {"type": "integer"},
                    "karar": {"type": "string", "enum": ["dogru", "duzelt", "belirsiz"]},
                    "sinif": {"type": "string", "enum": ["standart", "parca"]},
                    "tip": {"type": "string"},
                    "guven": {"type": "number"},
                    "gerekce": {"type": "string"},
                },
                "required": ["no", "karar", "sinif", "tip", "guven", "gerekce"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["parcalar"],
    "additionalProperties": False,
}


class AIHatasi(Exception):
    """İleti kullanıcıya gösterilebilir."""


def hazir_mi():
    """anthropic paketi kurulu mu."""
    try:
        import anthropic                                         # noqa: F401
        return True
    except ImportError:
        return False


def _istemci(anahtar=None):
    import anthropic
    return anthropic.Anthropic(api_key=anahtar) if anahtar else anthropic.Anthropic()


def _sor(istemci, icerik, model):
    ist = dict(
        model=model,
        max_tokens=16000,
        system=SISTEM,
        output_config={"effort": "medium",
                       "format": {"type": "json_schema", "schema": SEMA}},
        messages=[{"role": "user", "content": icerik}],
    )
    try:
        # Güvenlik sınıflandırıcısı reddederse istek sunucuda uygun modelle
        # yeniden çalışır (fallbacks: "default").
        return istemci.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **ist)
    except TypeError:
        return istemci.messages.create(**ist)       # eski SDK: yedeksiz


def _cagir(istemci, icerik, model, nolar, sayac):
    try:
        import anthropic as A
    except ImportError:                  # sahte istemciyle deneme
        A = None
    try:
        r = _sor(istemci, icerik, model)
    except Exception as e:
        if A is None:
            raise
        if isinstance(e, A.AuthenticationError):
            raise AIHatasi("API anahtarı geçersiz. ANTHROPIC_API_KEY ortam "
                           "değişkenini ya da Pi3D'deki AI anahtarını kontrol edin.")
        if isinstance(e, A.PermissionDeniedError):
            raise AIHatasi("API anahtarının bu modele izni yok.")
        if isinstance(e, A.RateLimitError):
            raise AIHatasi("Kullanım sınırı aşıldı; biraz sonra yeniden deneyin.")
        if isinstance(e, A.APIConnectionError):
            raise AIHatasi("İnternete / Anthropic'e bağlanılamadı.")
        if isinstance(e, A.APIStatusError):
            raise AIHatasi(f"AI hatası ({e.status_code}): {e.message}")
        if isinstance(e, A.AnthropicError):
            raise AIHatasi(f"AI hatası: {e}")
        raise
    u = getattr(r, "usage", None)
    if u is not None:
        # önbellekten okunan girdi onda bir, önbelleğe yazılan 1,25 kat fiyat
        okunan = getattr(u, "cache_read_input_tokens", 0) or 0
        yazilan = getattr(u, "cache_creation_input_tokens", 0) or 0
        sayac["girdi"] += (getattr(u, "input_tokens", 0) or 0) + 0.1 * okunan + 1.25 * yazilan
        sayac["onbellek"] = sayac.get("onbellek", 0) + okunan
        sayac["cikti"] += getattr(u, "output_tokens", 0) or 0
    sayac["istek"] += 1
    if r.stop_reason == "refusal":
        raise AIHatasi("Model isteği reddetti.")
    if r.stop_reason == "max_tokens":
        raise AIHatasi("Yanıt yarıda kesildi (çok parça); daha az parçayla deneyin.")
    metin = next((b.text for b in r.content if b.type == "text"), "")
    try:
        veri = json.loads(metin)
    except ValueError:
        raise AIHatasi("AI yanıtı okunamadı.")
    out = {}
    for p in veri.get("parcalar", []):
        if p.get("no") in nolar and p.get("karar") in ("dogru", "duzelt", "belirsiz") \
                and p.get("sinif") in ("standart", "parca"):
            out[p["no"]] = {"karar": p["karar"], "sinif": p["sinif"],
                            "tip": str(p.get("tip") or ""),
                            "guven": max(0.0, min(1.0, float(p.get("guven") or 0))),
                            "gerekce": str(p.get("gerekce") or "")}
    return out


def maliyet(sayac, model=MODEL):
    fi, fo = FIYAT.get(model, FIYAT[MODEL])
    return round(sayac["girdi"] * fi / 1e6 + sayac["cikti"] * fo / 1e6, 4)


def _katalog_blogu(katalog):
    """Standart ürün kataloğu paftaları: her resimli istekte AYNI baştaki
    içerik -> önbelleğe alınır (sonraki isteklerde onda bir fiyatına)."""
    if not katalog:
        return []
    blok = [{"type": "text", "text":
             "STANDART ÜRÜN KATALOĞU: aşağıdaki resimlerin HEPSİ bu firmanın SATIN "
             "ALDIĞI standart / katalog ürünlerdir (adı olmasa da). Sac, lama, profil, "
             "üretim parçası bu katalogda yoktur. Bir parçanın resmi bunlardan birine "
             "YAPISAL olarak benziyorsa (aynı öğeler: baş + gövde, delik + anahtar "
             "yüzeyi, halka, yay...) standart olma olasılığı yüksektir; benzemiyorsa "
             "bu tek başına üretim parçası olduğunu göstermez."}]
    for png in katalog:
        blok.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/png",
            "data": base64.standard_b64encode(png).decode("ascii")}})
    blok[-1]["cache_control"] = {"type": "ephemeral"}
    return blok


def kontrol_et(parcalar, baglam=None, goruntu=None, oncelik=(), anahtar=None,
               model=MODEL, log=print, istemci=None, katalog=None):
    """parcalar: [{"no", "kod", "ad", "adet", "olcu_mm", "program_sinif",
    "program_tip", "karar_kaynagi", "bulgular"}]
    goruntu: no -> PNG baytları (None: görüntü turu yok)
    oncelik: programın zaten belirsiz bulduğu parçaların no'ları (2. turda
    her durumda resimle bakılır).
    katalog: standart ürün kataloğu paftaları (PNG baytları, pf12_katalog);
    2. turda her isteğin başına referans olarak eklenir (önbellekli).
    Döner: ({no: {"karar", "sinif", "tip", "guven", "gerekce", "goruntu"}},
            {"girdi", "cikti", "istek", "resim", "usd"})."""
    if istemci is None:
        if not hazir_mi():
            raise AIHatasi("AI için 'anthropic' paketi kurulu değil:\n"
                           "  pip install anthropic")
        istemci = _istemci(anahtar)
    sayac = {"girdi": 0, "cikti": 0, "istek": 0, "resim": 0, "onbellek": 0}
    sonuc = {}
    # ---- 1. tur: yazı, bütün parçalar
    for i in range(0, len(parcalar), YAZI_PARTI):
        parti = parcalar[i:i + YAZI_PARTI]
        log(f"AI 1. tur: {i + 1}-{i + len(parti)} / {len(parcalar)} parça kontrol ediliyor...")
        icerik = ("Model bağlamı ve parçalar (JSON):\n"
                  + json.dumps({"baglam": baglam or {}, "parcalar": parti},
                               ensure_ascii=False))
        for no, r in _cagir(istemci, icerik, model, {p["no"] for p in parti}, sayac).items():
            sonuc[no] = dict(r, goruntu=False)
    # ---- 2. tur: resim, emin olunmayanlar + programın belirsizleri
    if goruntu:
        onc = set(oncelik)
        ikinci = [p for p in parcalar
                  if p["no"] in onc or p["no"] not in sonuc
                  or sonuc[p["no"]]["karar"] == "belirsiz"
                  or sonuc[p["no"]]["guven"] < EMIN]
        for i in range(0, len(ikinci), GORUNTU_PARTI):
            parti = ikinci[i:i + GORUNTU_PARTI]
            icerik = _katalog_blogu(katalog) + [{"type": "text", "text":
                       "Bu parçalara RESİMLERİYLE birlikte yeniden bak. Model bağlamı:\n"
                       + json.dumps(baglam or {}, ensure_ascii=False)}]
            for p in parti:
                try:
                    png = goruntu(p["no"])
                except Exception:
                    png = None
                icerik.append({"type": "text", "text": "Parça: " + json.dumps(
                    dict(p, ai_ilk_tur=sonuc.get(p["no"])), ensure_ascii=False)})
                if png:
                    icerik.append({"type": "image", "source": {
                        "type": "base64", "media_type": "image/png",
                        "data": base64.standard_b64encode(png).decode("ascii")}})
                    sayac["resim"] += 1
            log(f"AI 2. tur (görüntü): {i + 1}-{i + len(parti)} / {len(ikinci)} parça...")
            for no, r in _cagir(istemci, icerik, model, {p["no"] for p in parti},
                                sayac).items():
                sonuc[no] = dict(r, goruntu=True)
    sayac["usd"] = maliyet(sayac, model)
    sayac["girdi"] = int(sayac["girdi"])
    def bin_(v):
        return XL.tr(v)
    log(f"AI: {sayac['istek']} istek, {sayac['resim']} resim, {bin_(sayac['girdi'])} girdi "
        f"(önbellek fiyatıyla) + {bin_(sayac['cikti'])} çıktı token ≈ "
        f"${sayac['usd']:.2f} ({model})")
    return sonuc, sayac
