"""CATIA parça listesi (Bill of Material) ile STEP BOM'unun eşleştirilmesi.

CATIA V5'in Analyze > Bill of Material > Save As (Excel / Text) kaydı TEK
tablo değildir: her alt montaj için ayrı bir "Bill of Material: <montaj>"
bölümü, her bölümün kendi başlık satırı ve sonda "Recapitulation of:
<montaj>" (parça başına TOPLAM adet) bölümü vardır. Eski okuyucu bu
dosyayı tek tablo sanıp ilk gördüğü "Number" / "Steel" sütunlarını kod ve
malzeme diye okuyordu (Karluna: 109 satırdan 3'ü, ikisi başlık satırı) -
yanlış sonuç.

Burada dosya bölüm bölüm çözülür, parça başına toplam adet özet
bölümünden (yoksa montaj ağacından çarpılarak) bulunur ve STEP'ten
çıkan komponent listesiyle ad / parça no / nomenclature / dosya adı
üzerinden eşleştirilir. Sonuç: her parça için CATIA adedi, STEP adedi,
durum ("eşleşti", "adet farklı", "STEP'te yok", "CATIA'da yok") ve
CATIA'daki malzeme (Material sütunu görünür yapılmışsa; TraceParts
"materialgruppe" alanı standart elemanlarda malzeme grubunu verir).

Firma dosyası depoya girmez; buradaki örnekler uydurmadır (bkz.
test/catia_bom_denetimi.py)."""
from __future__ import annotations
import os
import re

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
BOLUM_ON = ("bill of material:", "recapitulation of:", "nomenclature:",
            "récapitulatif", "recapitulatif")
MAL_SUTUN = ("material", "malzeme", "werkstoff", "matiere", "matière",
             "material name", "sw-material")
MAL_GRUP = ("materialgruppe", "material group", "materyal grubu")
_SATIN = r"bought|\bbuy|purchas|sat[ıi]n|kaufteil|zukauf|achat|fremdteil"
_URET = r"\bmade\b|\bmake\b|[uü]retim|imalat|eigenfertig|eigenteil|fabriqu"


def _sade(t):
    """Eşleştirme anahtarı: Türkçe harfler düzleşir, küçük harf, '_' ve
    boşluk tek boşluk olur."""
    t = (t or "").strip().translate(_TR).lower()
    return re.sub(r"[\s_]+", " ", t).strip()


def _n(t):
    return _sade(t).replace(" ", "")


def _kod(t):
    """pf3_olcu._tr_sade ile aynı anahtar (malzeme eşlemesi için)."""
    return (t or "").strip().translate(_TR).lower()


def catia_bom_mu(satirlar):
    """Satır listesi CATIA'nın bölümlü Bill of Material kaydı mı?"""
    for sat in satirlar[:60]:
        ilk = _sade(sat[0] if sat else "")
        if any(ilk.startswith(b) for b in BOLUM_ON):
            return True
    return False


def _baslik_mi(sat):
    s = [_n(h) for h in sat]
    return "quantity" in s and ("partnumber" in s or "number" in s or "name" in s)


def _sayi(v):
    try:
        return int(round(float(str(v).replace(",", ".").strip() or 0)))
    except ValueError:
        return 0


def _hucre(cift, *adlar):
    """Başlık adına göre ilk DOLU hücre (aynı ad iki kez olabilir: 'Source')."""
    for ad in adlar:
        for h, v in cift:
            if h == ad and str(v).strip():
                return str(v).strip()
    return ""


def _temiz(v):
    return "" if _sade(v) in ("", "none", "bilinmeyen", "unknown", "herhangi") else v


def catia_bom_coz(satirlar):
    """Bölümlü CATIA BOM satırlarını çözer.

    Döner: {"montaj", "bolumler": [{"ad", "satirlar": [satır]}], "ozet": [satır],
            "farkli", "toplam", "malzeme_sutunu", "toplamlar": {anahtar: adet}}
    satır: {"part_no", "ad", "ust", "adet", "tip", "kaynak", "tanim", "dosya",
            "malzeme", "malzeme_grubu", "revizyon", "bolum", "ozet"}"""
    out = {"montaj": "", "bolumler": [], "ozet": [], "farkli": None, "toplam": None,
           "malzeme_sutunu": False}
    bolum, basl, ozet_mi = None, None, False
    for sat in satirlar:
        sat = [str(h) for h in sat]
        ilk = sat[0].strip() if sat else ""
        ilk_s = _sade(ilk)
        if any(ilk_s.startswith(b) for b in BOLUM_ON):
            ad = ilk.split(":", 1)[1].strip() if ":" in ilk else ilk
            ozet_mi = ilk_s.startswith(("recapitulation", "récapitulatif", "recapitulatif"))
            if ozet_mi:
                bolum = {"ad": ad, "satirlar": out["ozet"]}
            else:
                bolum = {"ad": ad, "satirlar": []}
                out["bolumler"].append(bolum)
                out["montaj"] = out["montaj"] or ad
            # başlık satırı bölümün altında yeniden gelir; gelmezse (bazı
            # kayıtlarda özet bölümü başlıksız) öncekisi sürer
            continue
        m = re.match(r"(different parts|total parts)\s*:\s*(\d+)", ilk_s)
        if m:
            out["farkli" if m.group(1).startswith("different") else "toplam"] = int(m.group(2))
            continue
        if not any(h.strip() for h in sat):
            continue
        if _baslik_mi(sat):
            basl = [_n(h) for h in sat]
            if any(h in basl for h in (_n(x) for x in MAL_SUTUN)):
                out["malzeme_sutunu"] = True
            continue
        if bolum is None or basl is None:
            continue
        cift = list(zip(basl, sat))
        part_no = _hucre(cift, "partnumber") or _hucre(cift, "name")
        if not part_no:
            continue
        ad = _hucre(cift, "name")
        dosya = os.path.basename(_hucre(cift, "defaultrepresentationsource").replace("\\", "/"))
        kay = ""
        for h, v in cift:
            if h == "source":
                vs = _sade(v)
                if re.search(_SATIN, vs):
                    kay = "standart"
                elif re.search(_URET, vs):
                    kay = "parca"
        mal = ""
        for h in (_n(x) for x in MAL_SUTUN):
            mal = mal or _temiz(_hucre(cift, h))
        grup = ""
        for h in (_n(x) for x in MAL_GRUP):
            grup = grup or _temiz(_hucre(cift, h))
        r = {"part_no": part_no, "ad": ad, "ust": _hucre(cift, "owner"),
             "adet": _sayi(_hucre(cift, "quantity")),
             "tip": _hucre(cift, "type") or ("Part" if dosya.lower().endswith(".catpart") else ""),
             "kaynak": kay,
             "tanim": _temiz(_hucre(cift, "nomenclature")) or _temiz(_hucre(cift, "definition")),
             "dosya": dosya, "malzeme": mal, "malzeme_grubu": grup,
             "revizyon": _temiz(_hucre(cift, "revision")),
             "bolum": bolum["ad"], "ozet": ozet_mi}
        bolum["satirlar"].append(r)
    out["toplamlar"] = _toplamlar(out)
    return out


def anahtarlar(metin):
    """Bir adın eşleştirme anahtarları: olduğu gibi, uzantısız, örnek
    numarasız (".1", ".1.1", ".CATPart.28")."""
    out = []
    t = _sade(metin)
    if not t:
        return out

    def ekle(x):
        x = x.strip()
        if x and x not in out:
            out.append(x)
    ekle(t)
    u = re.sub(r"\.(catpart|catproduct|stp|step|igs|iges)(\.\d+)?$", "", t)
    ekle(u)
    # örnek numarası: sondaki ".N" (bir ya da iki kez)
    v = u
    for _ in range(2):
        v2 = re.sub(r"\.\d+$", "", v)
        if v2 == v:
            break
        v = v2
        ekle(v)
    return out


def _satir_anahtarlari(r):
    out = []
    for m in (r.get("part_no"), r.get("tanim"), r.get("ad"), r.get("dosya")):
        for a in anahtarlar(m):
            if a not in out:
                out.append(a)
    return out


def _toplamlar(cb):
    """Parça no -> montajdaki TOPLAM adet. Özet bölümü varsa odur; yoksa
    bölümler ağaç gibi gezilip alt montaj adetleriyle çarpılır."""
    if cb["ozet"]:
        t = {}
        for r in cb["ozet"]:
            t[_sade(r["part_no"])] = t.get(_sade(r["part_no"]), 0) + r["adet"]
        return t
    bol = {_sade(b["ad"]): b for b in cb["bolumler"]}
    kat = {}

    def carpan(ad, derin=0):
        if ad in kat:
            return kat[ad]
        if derin > 30 or not cb["bolumler"] or ad == _sade(cb["bolumler"][0]["ad"]):
            return 1
        c = 0
        for b in cb["bolumler"]:
            for r in b["satirlar"]:
                if _sade(r["part_no"]) == ad:
                    c += r["adet"] * carpan(_sade(b["ad"]), derin + 1)
        kat[ad] = c or 1
        return kat[ad]
    t = {}
    for b in cb["bolumler"]:
        for r in b["satirlar"]:
            if _sade(r["part_no"]) in bol and r["tip"].lower() != "part":
                continue                 # alt montaj: kendi bölümü sayar
            a = _sade(r["part_no"])
            t[a] = t.get(a, 0) + r["adet"] * carpan(_sade(b["ad"]))
    return t


def catia_parcalari(cb):
    """Parça no başına tek kayıt (özetten; yoksa bölümlerden), toplam
    adetle. Alt montajlar (Assembly) ayrı listede."""
    gor, parca, montaj = {}, [], []
    # önce özet (toplam adetli), sonra bölümler (özette olmayanlar)
    kaynak = list(cb["ozet"]) + [r for b in cb["bolumler"] for r in b["satirlar"]]
    for r in kaynak:
        a = _sade(r["part_no"])
        if a in gor:
            # aynı parça başka bölümde: boş alanları tamamla
            for k in ("tanim", "malzeme", "malzeme_grubu", "kaynak", "dosya", "revizyon"):
                if not gor[a].get(k) and r.get(k):
                    gor[a][k] = r[k]
            continue
        k = dict(r)
        k["toplam"] = cb["toplamlar"].get(a, r["adet"])
        gor[a] = k
        (montaj if (k["tip"].lower() == "assembly" or
                    any(_sade(b["ad"]) == a for b in cb["bolumler"])) else parca).append(k)
    return parca, montaj


def bom_eslestir(komp, cb):
    """STEP komponentleri (pf3_olcu komp: ad, kod, adet, sinif) ile CATIA
    BOM'u eşleştirir.

    Eşleşme: parça no / nomenclature / örnek adı / dosya adı anahtarlarından
    biri STEP'in adı ya da koduyla aynı; olmazsa biri öbürünü içeriyor (en
    az 6 karakter). Aynı STEP kaydına birden çok CATIA parçası düşebilir
    (sağ / sol profil aynı STEP dosyasından, aynı nomenclature): bunlar
    tek ÖBEK olur, adetleri toplanıp karşılaştırılır.
    Döner: {"satirlar": [...], "ozet": {...}, "esl": {kod: malzeme}}"""
    parca, montaj = catia_parcalari(cb)
    cat = parca + montaj
    cat_key = [(_satir_anahtarlari(r), r) for r in cat]
    # birleşik bul: cat satırı -> öbek no
    obek = list(range(len(cat)))

    def kok(i):
        while obek[i] != i:
            obek[i] = obek[obek[i]]
            i = obek[i]
        return i
    step_es = {}                       # id(komp) -> cat indeksleri
    satirlar = []
    for k in komp:
        if k.get("sinif") == "kaynak":
            continue
        sk = [a for m in (k.get("ad"), k.get("kod")) for a in anahtarlar(m)]
        hit = [i for i, (keys, _r) in enumerate(cat_key) if any(a in keys for a in sk)]
        if not hit:
            hit = [i for i, (keys, _r) in enumerate(cat_key)
                   if any(len(a) >= 6 and len(b) >= 6 and (a in b or b in a)
                          for a in sk for b in keys)]
        if not hit:
            satirlar.append({"durum": "CATIA'da yok", "catia_part_no": "", "catia_tanim": "",
                             "catia_tip": "", "catia_adet": "", "step_ad": k["ad"],
                             "step_kod": k["kod"], "step_adet": k["adet"],
                             "step_sinif": k.get("sinif", ""), "malzeme": "", "kaynak": ""})
            continue
        step_es[id(k)] = (k, hit)
        for i in hit[1:]:
            obek[kok(i)] = kok(hit[0])
    gruplar = {}
    for i in range(len(cat)):
        gruplar.setdefault(kok(i), []).append(i)
    esl = {}
    for _g, idx in gruplar.items():
        rs = [cat[i] for i in idx]
        ks = [k for k, hit in step_es.values() if any(i in idx for i in hit)]
        mal = next((r["malzeme"] or r["malzeme_grubu"] for r in rs
                    if r["malzeme"] or r["malzeme_grubu"]), "")
        if not ks:
            if all(r in montaj for r in rs):
                continue                 # alt montaj: STEP'te katı olarak yok, normal
            for r in rs:
                if r in montaj:
                    continue
                satirlar.append({"durum": "STEP'te yok", "catia_part_no": r["part_no"],
                                 "catia_tanim": r["tanim"], "catia_tip": r["tip"],
                                 "catia_adet": r["toplam"], "step_ad": "", "step_kod": "",
                                 "step_adet": "", "step_sinif": "",
                                 "malzeme": r["malzeme"] or r["malzeme_grubu"],
                                 "kaynak": r["kaynak"]})
            continue
        ct = sum(r["toplam"] for r in rs)
        st = sum(k["adet"] for k in ks)
        satirlar.append({"durum": "eşleşti" if st == ct else "adet farklı",
                         "catia_part_no": " | ".join(r["part_no"] for r in rs),
                         "catia_tanim": " | ".join(dict.fromkeys(r["tanim"] for r in rs if r["tanim"])),
                         "catia_tip": " | ".join(dict.fromkeys(r["tip"] for r in rs if r["tip"])),
                         "catia_adet": ct,
                         "step_ad": " | ".join(k["ad"] for k in ks),
                         "step_kod": " | ".join(dict.fromkeys(k["kod"] for k in ks)),
                         "step_adet": st,
                         "step_sinif": " | ".join(dict.fromkeys(k.get("sinif", "") for k in ks)),
                         "malzeme": mal,
                         "kaynak": " | ".join(dict.fromkeys(r["kaynak"] for r in rs if r["kaynak"]))})
        if mal:
            for k in ks:
                esl[_kod(k["kod"])] = mal
    sira = {"adet farklı": 0, "CATIA'da yok": 1, "STEP'te yok": 2, "eşleşti": 3}
    satirlar.sort(key=lambda s: (sira[s["durum"]], str(s["catia_part_no"] or s["step_ad"])))
    ozet = {d: sum(1 for s in satirlar if s["durum"] == d) for d in sira}
    ozet["catia_parca"] = len(parca)
    ozet["catia_montaj"] = len(montaj)
    ozet["step_komponent"] = sum(1 for k in komp if k.get("sinif") != "kaynak")
    ozet["malzeme_sutunu"] = cb["malzeme_sutunu"]
    return {"satirlar": satirlar, "ozet": ozet, "esl": esl}


def ozet_metni(s, cb=None):
    o = s["ozet"]
    L = [f"CATIA BOM{(' (' + cb['montaj'] + ')') if cb and cb.get('montaj') else ''}: "
         f"{o['catia_parca']} parça, {o['catia_montaj']} alt montaj"
         + (f", toplam {cb['toplam']} adet" if cb and cb.get("toplam") else ""),
         f"STEP: {o['step_komponent']} komponent",
         "eşleşti {}, adet farklı {}, STEP'te yok {}, CATIA'da yok {}".format(
             o["eşleşti"], o["adet farklı"], o["STEP'te yok"], o["CATIA'da yok"])]
    if not o.get("malzeme_sutunu"):
        L.append("Dosyada Material sütunu yok: CATIA'da Define formats > Material'i "
                 "görünür yapıp yeniden kaydedin (standart elemanlarda TraceParts "
                 "malzeme grubu varsa o alındı).")
    return "\n".join(L)


ALAN = ["durum", "catia_part_no", "catia_adet", "step_adet", "step_ad", "step_kod",
        "step_sinif", "catia_tanim", "catia_tip", "malzeme", "kaynak"]


def eslestirme_yaz(on, s, cb=None, XL=None):
    """BOM_ESLESTIRME.csv / .xlsx / .md"""
    os.makedirs(on, exist_ok=True)
    if XL is not None:
        XL.tablo_yaz(os.path.join(on, "BOM_ESLESTIRME.csv"), ALAN,
                     XL.sozlukten(ALAN, s["satirlar"]), "BOM_ESLESTIRME")
    else:
        import csv
        with open(os.path.join(on, "BOM_ESLESTIRME.csv"), "w", newline="",
                  encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(ALAN)
            for r in s["satirlar"]:
                w.writerow([r.get(a, "") for a in ALAN])
    L = ["# BOM eşleştirme – CATIA parça listesi ile STEP\n", ozet_metni(s, cb), "",
         "| durum | CATIA parça no | CATIA adet | STEP adet | STEP ad | tanım | malzeme |",
         "|-------|----------------|-----------:|----------:|---------|-------|---------|"]
    for r in s["satirlar"]:
        L.append(f"| {r['durum']} | {str(r['catia_part_no'])[:40]} | {r['catia_adet']} | "
                 f"{r['step_adet']} | {str(r['step_ad'])[:40]} | {str(r['catia_tanim'])[:30]} | "
                 f"{r['malzeme'] or '-'} |")
    open(os.path.join(on, "BOM_ESLESTIRME.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    return os.path.join(on, "BOM_ESLESTIRME.csv")


def catia_malzeme_satirlari(cb):
    """Malzeme tablosu satırları (pf3_olcu.malzeme_tablosu biçimine girdi):
    [(kod, malzeme)] - Material sütunu; yoksa TraceParts malzeme grubu."""
    parca, montaj = catia_parcalari(cb)
    out = []
    for r in parca + montaj:
        m = r["malzeme"] or r["malzeme_grubu"]
        if m:
            out.append((r["part_no"], m))
            for ek in (r["tanim"], r["dosya"]):
                if ek and _sade(ek) != _sade(r["part_no"]):
                    out.append((ek, m))
    return out


def catia_kaynak_haritasi(cb):
    """Source (Made / Bought) dolu olan satırlar: kod -> "standart" | "parca"."""
    out = {}
    parca, montaj = catia_parcalari(cb)
    for r in parca + montaj:
        if r["kaynak"]:
            out[_kod(r["part_no"])] = r["kaynak"]
    return out
