# -*- coding: utf-8 -*-
"""AI malzeme tanımlama ajanı (pf10_ai), SAHTE istemciyle (ağ, anahtar
ve 'anthropic' paketi gerekmez).

Denetlenen:
  - 1. tur: bütün parçalar YAZIYLA gidiyor; elle / CAD'den kesin
    sınıflar ve kaynak dikişleri gitmiyor; CAD dosyası / geometri yok
  - 2. tur: yalnız 1. turda emin olunamayanlar + programın belirsiz
    bulduğu parçalar RESİMLE gidiyor
  - yanıt şemaya uymayan / listede olmayan parça yok sayılıyor, güven 0-1
  - maliyet gerçek kullanım (usage) üzerinden hesaplanıyor
  - ret (refusal) ve yarım yanıt anlaşılır hatayla bitiyor
  - eski SDK ('fallbacks' bilinmiyor) sıradan çağrıya düşüyor
  - parça resmi üretiliyor (OpenCascade varsa)

    python3 test/ai_denetimi.py
"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf10_ai as AI                                             # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


class Yanit:
    def __init__(self, veri, stop="end_turn", girdi=1000, cikti=200):
        self.stop_reason = stop
        self.content = [types.SimpleNamespace(type="text", text=json.dumps(veri))]
        self.usage = types.SimpleNamespace(input_tokens=girdi, output_tokens=cikti,
                                           cache_read_input_tokens=0,
                                           cache_creation_input_tokens=0)


class Sahte:
    """Claude yerine: 1. turda halkaya 'belirsiz', resimli turda 'düzelt'."""
    def __init__(self, eski_sdk=False, stop="end_turn"):
        self.istekler, self.stop = [], stop
        m = types.SimpleNamespace(create=self._create)
        self.messages = m
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(
            create=self._eski if eski_sdk else self._create))

    def _eski(self, **kw):
        if "fallbacks" in kw:
            raise TypeError("unexpected keyword argument 'fallbacks'")
        return self._create(**kw)

    def _create(self, **kw):
        self.istekler.append(kw)
        icerik = kw["messages"][0]["content"]
        resimli = isinstance(icerik, list)
        if resimli:
            parcalar = [json.loads(b["text"][len("Parça: "):]) for b in icerik
                        if b["type"] == "text" and b["text"].startswith("Parça: ")]
        else:
            parcalar = json.loads(icerik.split("\n", 1)[1])["parcalar"]
        out = []
        for p in parcalar:
            if p["ad"] == "55460008672":
                out.append({"no": p["no"], "karar": "duzelt" if resimli else "belirsiz",
                            "sinif": "standart", "tip": "lastik geçme" if resimli else "",
                            "guven": 0.9 if resimli else 0.4, "gerekce": "resim"})
            else:
                out.append({"no": p["no"], "karar": "dogru", "sinif": p["program_sinif"],
                            "tip": "", "guven": 1.7, "gerekce": "tamam"})
        out.append({"no": 999, "karar": "dogru", "sinif": "parca", "tip": "", "guven": 1,
                    "gerekce": "listede yok"})
        return Yanit({"parcalar": out}, self.stop, 5000 if resimli else 2000, 300)


P = [{"no": 0, "kod": "FT108161", "ad": "FT108161", "adet": 41, "olcu_mm": [19, 19, 24.5],
      "program_sinif": "standart", "program_tip": "civata (geometri)",
      "karar_kaynagi": "geometri ölçümü", "bulgular": ["program ölçtü: cıvata"]},
     {"no": 3, "kod": "55460008672", "ad": "55460008672", "adet": 6, "olcu_mm": [9, 27, 27],
      "program_sinif": "parca", "program_tip": "", "karar_kaynagi": "yok",
      "bulgular": ["program ölçtü (işaret): dönel küçük parça"]},
     {"no": 5, "kod": "55460006192", "ad": "55460006192", "adet": 5,
      "olcu_mm": [17, 25, 1385], "program_sinif": "parca",
      "program_tip": "kutu profil 17x25x2", "karar_kaynagi": "kesit ölçümü",
      "bulgular": []}]
resimler = []


def goruntu(no):
    resimler.append(no)
    return b"\x89PNG sahte"


print("-- iki tur")
s = Sahte()
sonuc, say = AI.kontrol_et(P, {"komponent_sayisi": 3}, goruntu=goruntu, oncelik=[0],
                           istemci=s, log=lambda t: None)
dogru("1. tur tek istek, 3 parça yazıyla", isinstance(s.istekler[0]["messages"][0]["content"], str)
      and len(json.loads(s.istekler[0]["messages"][0]["content"].split("\n", 1)[1])["parcalar"]) == 3)
dogru("2. turda resim yalnız belirsiz (halka) + programın belirsizi (cıvata)",
      sorted(resimler) == [0, 3], str(resimler))
dogru("halka resimle düzeltildi", sonuc[3]["karar"] == "duzelt" and sonuc[3]["sinif"] == "standart"
      and sonuc[3]["goruntu"] is True, str(sonuc.get(3)))
dogru("profil 1. turda doğrulandı, resim gitmedi", sonuc[5]["karar"] == "dogru"
      and sonuc[5]["goruntu"] is False)
dogru("güven 0-1'e kırpıldı", sonuc[5]["guven"] == 1.0)
dogru("listede olmayan parça yok sayıldı", 999 not in sonuc)
dogru("yapılandırılmış çıktı + effort + yedek model",
      s.istekler[0]["output_config"]["format"]["type"] == "json_schema"
      and s.istekler[0]["fallbacks"] == "default")
dogru("maliyet usage'dan (Opus 5: 2000+5000 girdi, 600 çıktı)",
      say["girdi"] == 7000 and say["cikti"] == 600 and say["resim"] == 2
      and abs(say["usd"] - (7000 * 5 + 600 * 25) / 1e6) < 1e-9, str(say))
metin = json.dumps(s.istekler[0], default=str)
dogru("CAD dosyası / geometri gönderilmiyor", ".stp" not in metin and "brep" not in metin.lower())

print("\n-- resimsiz (görüntü turu kapalı)")
sonuc, say = AI.kontrol_et(P, goruntu=None, istemci=Sahte(), log=lambda t: None)
dogru("tek tur, resim yok", say["istek"] == 1 and say["resim"] == 0
      and sonuc[3]["karar"] == "belirsiz")

print("\n-- eski SDK ve hatalar")
sonuc, say = AI.kontrol_et(P, istemci=Sahte(eski_sdk=True), log=lambda t: None)
dogru("fallbacks bilinmiyorsa sıradan çağrı", len(sonuc) == 3)
for stop, ad in (("refusal", "ret"), ("max_tokens", "yarım yanıt")):
    try:
        AI.kontrol_et(P, istemci=Sahte(stop=stop), log=lambda t: None)
        dogru(f"{ad} hata veriyor", False)
    except AI.AIHatasi as ex:
        dogru(f"{ad}: anlaşılır hata", bool(str(ex)), str(ex))

print("\n-- parça resmi")
try:
    import pf8_tani as T
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    png = T.parca_png(BRepPrimAPI_MakeCylinder(5, 20).Shape(), boyut=384)
    dogru("PNG üretildi (768x384)", png[:4] == b"\x89PNG" and len(png) > 2000)
except ImportError:
    print("  atlandı: OpenCascade yok")

print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                     else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
sys.exit(1 if HATA else 0)
