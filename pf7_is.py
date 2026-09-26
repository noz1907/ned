# -*- coding: utf-8 -*-
"""Çıktı klasörünün düzeni ve İŞ DURUMU: hangi çizim hangi ayarla, ne
zaman üretildi; hangi işlem ne kadar sürdü.

Neden var: kullanıcı işi tek oturumda bitirmek zorunda değildir. BOM'u
ve çizimleri çıkarıp programı kapatabilir; ertesi gün yalnız PDF'leri,
yalnız açınımları ya da yalnız lazer resimlerini ister. Ya da bir adımı
(ör. pafta) yeniden yapmak ister. Her şeyi baştan almak saatler sürer.

Bu modül OpenCascade GEREKTİRMEZ: arayüz, hesap motoru yüklenmeden ya
da STEP okunmadan önce de klasörü okuyup "neler var" diyebilir.

Klasör düzeni (kök = kullanıcının seçtiği çıktı klasörü):

    BOM.csv, BOM.md, BOM_AGAC.*, olculer.*, rapor.md   tablolar (kök)
    DXF/      detay resimleri ve 00_MONTAJ.dxf (paftası içlerinde)
    ACINIM/   ..._acinim.dxf + ACINIM.csv
    LZR/      ..._Lzr.dxf + LAZER.csv (lazer kesim; paftaya alınmaz)
    PDF/      basılan paftalar
    pi3d_is.json   iş durumu (bu modül yazar)

Eski sürümler her şeyi köke yazıyordu; o klasörler de okunur (dosyanın
türü adından anlaşılır: _acinim.dxf, _Lzr.dxf, diğerleri detay).

GÜVENLİK KURALI: "zaten var" denip bir çizim ATLANACAKSA, o çizimin
AYNI model dosyasıyla (içerik özeti) ve AYNI ayarlarla üretildiği
kayıtlı olmalıdır. Kayıt yoksa ya da tutmuyorsa çizim yeniden üretilir:
eski bir resmi yeni diye vermek, hiç vermemekten kötüdür.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import threading
import time

ALT_KLASOR = {"dxf": "DXF", "acinim": "ACINIM", "lazer": "LZR", "pdf": "PDF"}
DURUM_DOSYASI = "pi3d_is.json"
# Çizim kodu değişince eski resimler "eskimiş" sayılsın diye imzaya
# girer. Ölçülendirme / görünüş kuralı değiştiğinde artırılır.
CIZIM_SURUMU = "2026.09.26"

_kilit = threading.RLock()
_ozet_onbellek = {}


# ------------------------------------------------------------ klasörler
def alt_klasor(on, tur, olustur=False):
    """Çıktı klasörünün altındaki tür klasörü (DXF, ACINIM, LZR, PDF)."""
    yol = os.path.join(on, ALT_KLASOR[tur])
    if olustur:
        os.makedirs(yol, exist_ok=True)
    return yol


def dosya_turu(ad):
    """DXF dosyasının türü, ADINDAN: 'acinim' | 'lazer' | 'dxf'."""
    a = os.path.basename(ad).lower()
    if a.endswith("_lzr.dxf"):
        return "lazer"
    if a.endswith("_acinim.dxf"):
        return "acinim"
    return "dxf"


def dosyalar(on, tur):
    """Bir türün çıktı dosyaları (tam yol, sıralı).

    Önce kendi klasörüne, sonra - eski sürümlerle üretilmiş klasörler
    için - köke bakılır. Aynı ad iki yerde varsa klasördeki alınır."""
    if not on or not os.path.isdir(on):
        return []
    uz = ".pdf" if tur == "pdf" else ".dxf"
    bulunan = {}
    k = alt_klasor(on, tur)
    if os.path.isdir(k):
        for a in os.listdir(k):
            if a.lower().endswith(uz) and (tur == "pdf" or dosya_turu(a) == tur):
                bulunan[a] = os.path.join(k, a)
    if tur != "pdf":
        for a in os.listdir(on):
            y = os.path.join(on, a)
            if (a.lower().endswith(".dxf") and os.path.isfile(y)
                    and dosya_turu(a) == tur and a not in bulunan):
                bulunan[a] = y
    return [bulunan[a] for a in sorted(bulunan)]


def dosya_bul(on, ad):
    """Adı bilinen bir çıktı dosyasının yeri (tür klasörü ya da kök)."""
    if not ad:
        return None
    tur = "pdf" if ad.lower().endswith(".pdf") else dosya_turu(ad)
    for y in (os.path.join(alt_klasor(on, tur), ad), os.path.join(on, ad)):
        if os.path.isfile(y):
            return y
    return None


# ------------------------------------------------------------ özetler
def dosya_ozeti(yol):
    """Model dosyasının İÇERİK özeti (sha1). Dosya kopyalansa ya da
    tarihi değişse de aynı kalır; içerik değişirse değişir.
    30 MB'lık STEP ~0,1 s; (yol, boy, tarih) ile önbelleklenir."""
    if not yol or not os.path.isfile(yol):
        return ""
    st = os.stat(yol)
    an = (os.path.abspath(yol), st.st_size, int(st.st_mtime))
    if an in _ozet_onbellek:
        return _ozet_onbellek[an]
    h = hashlib.sha1()
    with open(yol, "rb") as f:
        for par in iter(lambda: f.read(1 << 20), b""):
            h.update(par)
    oz = h.hexdigest()
    _ozet_onbellek[an] = oz
    return oz


def imza(*parca):
    """Bir çizimin kimliği: model özeti + onu etkileyen her ayar."""
    ham = json.dumps([CIZIM_SURUMU] + list(parca), sort_keys=True,
                     ensure_ascii=True, default=str)
    return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:16]


def cizim_ayari(P):
    """P'nin çizimi değiştiren kısmı (yoğunluk ayrıca parçaya göre girer)."""
    P = P or {}
    return {"gizli": bool(P.get("gizli")),
            "en_az_delik": float(P.get("en_az_delik") or 0.0),
            "gorunusler": list(P.get("gorunusler") or []),
            "kesit": bool(P.get("kesit"))}


# ------------------------------------------------------------ durum dosyası
def _bos():
    return {"surum": 1, "step": "", "step_ozet": "", "ayar": {},
            "dxf": {}, "acinim": {}, "lazer": {}, "islemler": []}


def durum_oku(on):
    """pi3d_is.json; yoksa ya da bozuksa boş durum (hata vermez)."""
    d = _bos()
    y = os.path.join(on or "", DURUM_DOSYASI)
    if on and os.path.isfile(y):
        try:
            with open(y, encoding="utf-8") as f:
                ok = json.load(f)
            if isinstance(ok, dict):
                for a, v in ok.items():
                    if a in d and type(v) is type(d[a]):
                        d[a] = v
        except Exception:
            pass
    return d


def durum_guncelle(on, degistir):
    """Oku - değiştir - yaz; iş parçacıkları arasında kilitli.
    Önce geçici dosyaya yazılır: yarım kalan yazım dosyayı bozmasın."""
    if not on:
        return None
    with _kilit:
        os.makedirs(on, exist_ok=True)
        d = durum_oku(on)
        degistir(d)
        y = os.path.join(on, DURUM_DOSYASI)
        g = y + ".yaz"
        with open(g, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(g, y)
        return d


def model_kaydet(on, step):
    oz = dosya_ozeti(step)

    def _d(d):
        d["step"] = os.path.abspath(step) if step else ""
        d["step_ozet"] = oz
    durum_guncelle(on, _d)
    return oz


def ayar_kaydet(on, **ayar):
    durum_guncelle(on, lambda d: d["ayar"].update(ayar))


def cizim_kaydet(on, tur, anahtar, **bilgi):
    """tur: 'dxf' (anahtar = dosya adı) | 'acinim' | 'lazer' (anahtar = kod)."""
    bilgi.setdefault("tarih", time.strftime("%Y-%m-%d %H:%M:%S"))
    durum_guncelle(on, lambda d: d[tur].__setitem__(anahtar, bilgi))


def islem_kaydet(on, ad, sure, sonuc="tamam"):
    def _d(d):
        d["islemler"].append({"ad": ad, "sure": round(float(sure), 1),
                              "sonuc": sonuc,
                              "tarih": time.strftime("%Y-%m-%d %H:%M:%S")})
        d["islemler"] = d["islemler"][-500:]
    durum_guncelle(on, _d)


def guncel_mi(on, dosya_adi, beklenen_imza, durum=None):
    """Çizim klasörde var VE kayıtlı imzası beklenenle aynı mı?"""
    d = durum or durum_oku(on)
    k = d["dxf"].get(dosya_adi)
    return bool(k and k.get("imza") == beklenen_imza
                and dosya_bul(on, dosya_adi))


def eskiyi_kaldir(on, tur, kod, yeni_ad, log=print):
    """Aynı parçanın ESKİ adla üretilmiş açınım/lazer dosyası varsa
    (poz numarası kaymış) <tür klasörü>/ESKI'ye taşır; silmez."""
    r = durum_oku(on)[tur].get(kod) or {}
    eski = r.get("dxf")
    if not eski or eski == yeni_ad:
        return False
    k = alt_klasor(on, tur)
    y = os.path.join(k, eski)
    if not os.path.isfile(y):
        return False
    os.makedirs(os.path.join(k, "ESKI"), exist_ok=True)
    os.replace(y, os.path.join(k, "ESKI", eski))
    log(f"  {eski}: poz değişmiş, eski dosya {ALT_KLASOR[tur]}/ESKI'ye taşındı")
    return True


def onceden_uretilmis(on, tur, kod, step_ozet, **ayni):
    """Bu parçanın açınımı/lazeri AYNI modelden (ve verilen ayarlarla,
    ör. k_faktor) üretilmiş ve dosyası duruyor mu?"""
    r = durum_oku(on)[tur].get(kod) or {}
    return bool(step_ozet and r.get("step_ozet") == step_ozet
                and all(r.get(a) == v for a, v in ayni.items())
                and r.get("dxf")
                and os.path.isfile(os.path.join(alt_klasor(on, tur), r["dxf"])))


# ------------------------------------------------------------ tablolar
def csv_birlestir(yol, baslik, yeni, denenen, klasor, kod_sutun="kod",
                  dxf_sutun="dxf"):
    """ACINIM.csv / LAZER.csv: yeni satırları eskilerle BİRLEŞTİRİR.

    Eskiden her üretim tabloyu sıfırdan yazıyordu: 5 parçanın açınımı
    çıkmış klasörde 2 parçayı yeniden açınca tablo 2 satıra iniyordu.
    Şimdi: bu turda DENENEN kodların eski satırları atılır (yenisi
    gelir ya da artık yapılamıyordur), dosyası silinmiş satırlar atılır,
    kalanlar korunur."""
    eski = []
    if os.path.isfile(yol):
        try:
            with open(yol, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f, delimiter=";"):
                    if r.get(kod_sutun) in denenen:
                        continue
                    if r.get(dxf_sutun) and not os.path.isfile(
                            os.path.join(klasor, r[dxf_sutun])):
                        continue
                    eski.append([r.get(c, "") for c in baslik])
        except Exception:
            eski = []

    def _sira(s):
        try:
            return (0, int(str(s[0]).strip() or 0), str(s[1]))
        except ValueError:
            return (1, 0, str(s[1]))
    hepsi = sorted(eski + [list(s) for s in yeni], key=_sira)
    with open(yol, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(baslik)
        w.writerows(hepsi)
    return len(hepsi)


def hata_birlestir(yol, hata, denenen):
    """..._yapilamayanlar.txt: bu turda denenmeyen parçaların eski
    kayıtları korunur; denenip başaranlar listeden düşer."""
    bloklar = []
    if os.path.isfile(yol):
        try:
            ham = open(yol, encoding="utf-8").read()
            for b in ham.split("\n\n"):
                if b.strip():
                    ad = b.strip("\n").splitlines()[0].strip()
                    if ad not in denenen:
                        bloklar.append(b.strip("\n"))
        except Exception:
            bloklar = []
    for ad, m in hata:
        bloklar.append(f"{ad}\n    " + m.replace("\n", "\n    "))
    if not bloklar:
        if os.path.isfile(yol):
            os.remove(yol)
        return 0
    with open(yol, "w", encoding="utf-8") as f:
        f.write("\n\n".join(bloklar) + "\n\n")
    return len(bloklar)


# ------------------------------------------------------------ klasör raporu
def pafta_var_mi(yol, pafta_adi="PAFTA"):
    """DXF'in içinde pafta sekmesi var mı? Yalnız dosyanın başındaki
    düzen (layout) adlarına bakmak için ezdxf ile hızlı okunur."""
    try:
        import ezdxf
        return pafta_adi in ezdxf.readfile(yol).layout_names()
    except Exception:
        return False


def cikti_durumu(on, step=None):
    """Klasörde ne var? Arayüzün 1. sayfasında gösterilir.

    Döner: {bom, bom_tarih, dxf, montaj, acinim, lazer, pdf, durum,
            ayni_model (None: bilinmiyor), step}"""
    d = durum_oku(on)
    r = {"bom": os.path.isfile(os.path.join(on, "BOM.csv")),
         "bom_tarih": "", "durum": d, "step": d.get("step") or ""}
    if r["bom"]:
        r["bom_tarih"] = time.strftime(
            "%d.%m.%Y %H:%M", time.localtime(os.path.getmtime(
                os.path.join(on, "BOM.csv"))))
    dx = dosyalar(on, "dxf")
    r["montaj"] = sum(1 for y in dx if "montaj" in os.path.basename(y).lower())
    r["dxf"] = len(dx) - r["montaj"]
    r["acinim"] = len(dosyalar(on, "acinim"))
    r["lazer"] = len(dosyalar(on, "lazer"))
    r["pdf"] = len(dosyalar(on, "pdf"))
    # Model aynı mı: klasörün genel kaydına değil, ÇİZİMLERİN KENDİ
    # kayıtlarına bakılır (her çizim hangi model özetiyle üretildiğini
    # taşır). Yeni bir model okununca genel kayıt değişir; eski çizimler
    # yine eski modelin çizimidir.
    r["ayni_model"] = None
    kayitli = {v.get("step_ozet") for t in ("dxf", "acinim", "lazer")
               for v in d[t].values() if v.get("step_ozet")}
    if step and kayitli:
        r["ayni_model"] = dosya_ozeti(step) in kayitli
    return r


def durum_metni(r):
    """cikti_durumu() sonucunu insan diliyle yazar."""
    if not any((r["bom"], r["dxf"], r["montaj"], r["acinim"], r["lazer"],
                r["pdf"])):
        return "Bu klasörde önceki bir çalışma yok."
    v = lambda b: "var" if b else "yok"                     # noqa: E731
    L = ["Bu klasörde önceki çalışma bulundu:",
         f"  BOM ................ {v(r['bom'])}"
         + (f"  ({r['bom_tarih']})" if r["bom_tarih"] else ""),
         f"  detay resmi (DXF) .. {r['dxf']}",
         f"  montaj resmi ....... {v(r['montaj'])}",
         f"  açınım ............. {r['acinim']}",
         f"  lazer (LZR) ........ {r['lazer']}",
         f"  PDF ................ {r['pdf']}"]
    if r["ayni_model"] is True:
        L.append("Model dosyası AYNI: üretilmiş çizimler geçerli, yalnız "
                 "eksikler üretilebilir.")
    elif r["ayni_model"] is False:
        L.append("DİKKAT: model dosyası o çizimler üretildikten sonra "
                 "DEĞİŞMİŞ. Eski çizimler atlanmaz, yeniden üretilir.")
    elif r["bom"] or r["dxf"]:
        L.append("Çizimlerin hangi modelden ve hangi ayarla üretildiği "
                 "kayıtlı değil (eski sürüm): eksik üretimde hepsi yeniden "
                 "üretilir. Pafta ve PDF doğrudan yapılabilir.")
    return "\n".join(L)


def sure_metni(s):
    s = int(round(float(s or 0)))
    if s < 60:
        return f"{s} sn"
    if s < 3600:
        return f"{s // 60} dk {s % 60:02d} sn"
    return f"{s // 3600} sa {(s % 3600) // 60:02d} dk"
