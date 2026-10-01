# -*- coding: utf-8 -*-
"""CATIA'nın BÖLÜMLÜ Bill of Material kaydı doğru çözülüyor ve STEP
BOM'uyla doğru eşleşiyor mu?

Gerçek kusur (Karluna, CATIA V5 R17 kaydı, 264 satır): her alt montaj için
ayrı "Bill of Material: X" bölümü, her bölümün kendi başlık satırı ve
sonda "Recapitulation of" özeti var. Eski okuyucu dosyayı tek tablo
sanıp özet bölümündeki TraceParts sütunlarını kod / malzeme diye okudu:
109 satırdan 3'ü, ikisi başlık satırı ("TraceParts.PartVersion" ->
"oberflaeche"). Yanlış sonuç.

Denetlenen:
  1. Bölümler, özet, "Different parts / Total parts" sayıları, Material
     sütununun varlığı.
  2. Parça başına TOPLAM adet: özetten; özet yoksa montaj ağacından
     çarpılarak - ikisi aynı çıkmalı.
  3. Eşleştirme: parça no, nomenclature (STEP dosya adı), ".CATPart.28" /
     ".1.1" ekleri, "Copy (1) of"; aynı STEP kaydına düşen sağ / sol
     profil tek öbek (adetler toplanır); adet farkı, STEP'te yok,
     CATIA'da yok; alt montaj eksik sayılmaz.
  4. Malzeme: Material sütunu varsa kod -> malzeme; yoksa TraceParts
     malzeme grubu; hiçbiri yoksa malzeme_tablosu açık hata verir,
     başlık satırı asla kod sanılmaz.
  5. Rapor dosyaları (BOM_ESLESTIRME.csv / .md) yazılıyor.

    python test/catia_bom_denetimi.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as O                                            # noqa: E402
import pf15_bom_esle as BE                                      # noqa: E402

HATA = []


def kontrol(ad, sart, ek=""):
    if sart:
        print(f"  tamam {ad}")
    else:
        print(f"  HATA  {ad}  {ek}")
        HATA.append(ad)


BAS = ("Source\tNumber\tDefinition\tProduct Description\tSource\t"
       "Default Representation Source\tName\tOwner\tmaterialgruppe\t"
       "Quantity\tPart Number\tType\tNomenclature\tRevision")
BAS_MAL = BAS.replace("Revision", "Revision\tMaterial")


def satir(part_no, owner, adet, tip, nomen="", dosya="", kaynak="Unknown", grup="",
          mal=None, ad=None):
    r = [kaynak, " ", " ", " ", kaynak,
         f"\\\\SUNUCU\\PROJE\\{dosya or part_no}.CATPart" if tip == "Part" else " ",
         ad or f"{part_no}.1", owner, grup, str(adet), part_no, tip, nomen, " "]
    if mal is not None:
        r.append(mal)
    return "\t".join(r)


def dosya_yaz(malzemeli=False, ozetli=True, gruplu=True):
    b = BAS_MAL if malzemeli else BAS
    g = "Steel" if gruplu else ""

    def s(*a, **k):
        if malzemeli and "mal" not in k:
            k["mal"] = ""
        return satir(*a, **k)
    L = ["Thursday, 01 October 2026 08:47:26", "",
         "Bill of Material: ANA_MONTAJ", b,
         s("ALT_GRUP", "ANA_MONTAJ", 2, "Assembly"),
         s("KAPAK", "ANA_MONTAJ", 1, "Part", mal="Steel" if malzemeli else None),
         s("KAUCUK_SILTE_3mm", "ANA_MONTAJ", 2, "Part", mal="Rubber" if malzemeli else None),
         s("PROFIL_SOL", "ANA_MONTAJ", 1, "Part", nomen="ALP0043-01-01-01.stp",
           dosya="ALP0043-01-01-01"),
         s("PROFIL_SAG", "ANA_MONTAJ", 1, "Part", nomen="ALP0043-01-01-01.stp",
           dosya="Symmetry of ALP0043-01-01-01"),
         "",
         "Bill of Material: ALT_GRUP", b,
         s("ARA_KROS", "ALT_GRUP.1", 3, "Part", kaynak="Made",
           mal="Aluminium" if malzemeli else None),
         s("Copy (1) of SAC_8", "ALT_GRUP.1", 1, "Part", ad="SAC_8.1.1",
           dosya="Copy (1) of SAC_8"),
         s("505602001", "ALT_GRUP.1", 4, "Part", nomen="DIN125_M10_PUL", kaynak="Bought",
           grup=g, dosya="10_00_0125_0105a_013_M10"),
         s("KAPAK", "ALT_GRUP.1", 1, "Part", mal="Steel" if malzemeli else None),
         ""]
    if ozetli:
        L += ["Recapitulation of: ANA_MONTAJ", "Different parts: 7", "Total parts: 22", "",
              "Type\t" + b,
              "Part\t" + s("KAPAK", "KAPAK.CATPart", 3, "Part", ad="KAPAK",
                           mal="Steel" if malzemeli else None),
              "Part\t" + s("KAUCUK_SILTE_3mm", "KAUCUK_SILTE_3mm.CATPart", 2, "Part",
                           ad="KAUCUK_SILTE_3mm", mal="Rubber" if malzemeli else None),
              "Part\t" + s("PROFIL_SOL", "ALP0043-01-01-01.CATPart", 1, "Part",
                           nomen="ALP0043-01-01-01.stp", ad="PROFIL_SOL"),
              "Part\t" + s("PROFIL_SAG", "Symmetry of ALP0043-01-01-01.CATPart", 1, "Part",
                           nomen="ALP0043-01-01-01.stp", ad="PROFIL_SAG"),
              "Part\t" + s("ARA_KROS", "ARA_KROS.CATPart", 6, "Part", kaynak="Made",
                           ad="ARA_KROS", mal="Aluminium" if malzemeli else None),
              "Part\t" + s("Copy (1) of SAC_8", "Copy (1) of SAC_8.CATPart", 2, "Part",
                           ad="Copy (1) of SAC_8"),
              "Part\t" + s("505602001", "10_00_0125_0105a_013_M10.CATPart", 8, "Part",
                           nomen="DIN125_M10_PUL", kaynak="Bought", grup=g,
                           ad="505602001")]
    d = tempfile.mkdtemp(prefix="pi3d_catia_")
    y = os.path.join(d, "catia_bom.txt")
    with open(y, "w", encoding="cp1254", newline="\r\n") as f:
        f.write("\n".join(L) + "\n")
    return y, d


KOMP = [
    {"ad": "KAPAK", "kod": "KAPAK", "adet": 3, "sinif": "parca"},
    {"ad": "KAUCUK_SILTE_3mm", "kod": "KAUCUK_SILTE_3mm", "adet": 2, "sinif": "parca"},
    {"ad": "ALP0043-01-01-01.stp", "kod": "ALP0043-01-01-01.stp", "adet": 2, "sinif": "standart"},
    {"ad": "ARA_KROS", "kod": "ARA_KROS", "adet": 5, "sinif": "parca"},        # CATIA 6
    {"ad": "Copy (1) of SAC_8.CATPart.28", "kod": "Copy (1) of SAC_8.CATPart.28", "adet": 2,
     "sinif": "parca"},
    {"ad": "DIN125_M10_PUL", "kod": "DIN125", "adet": 8, "sinif": "standart"},
    {"ad": "EKSTRA_SAC", "kod": "EKSTRA_SAC", "adet": 1, "sinif": "parca"},    # CATIA'da yok
    {"ad": "K12 dikiş", "kod": "K12", "adet": 4, "sinif": "kaynak"},           # sayılmaz
]


def dene_cozum():
    print("1) bölümlü dosya çözümü")
    y, _d = dosya_yaz()
    cb = O.catia_bom_oku(y)
    kontrol("CATIA BOM tanındı", cb is not None)
    kontrol("montaj adı", cb["montaj"] == "ANA_MONTAJ", cb["montaj"])
    kontrol("2 bölüm", len(cb["bolumler"]) == 2, len(cb["bolumler"]))
    kontrol("özet 7 satır", len(cb["ozet"]) == 7, len(cb["ozet"]))
    kontrol("farklı / toplam", (cb["farkli"], cb["toplam"]) == (7, 22), (cb["farkli"], cb["toplam"]))
    kontrol("Material sütunu yok", cb["malzeme_sutunu"] is False)
    t = cb["toplamlar"]
    kontrol("özet toplamı: KAPAK 3, ARA_KROS 6, pul 8",
            (t.get("kapak"), t.get("ara kros"), t.get("505602001")) == (3, 6, 8), t)
    cb2 = dict(cb, ozet=[])
    t2 = BE._toplamlar(cb2)
    kontrol("ağaçtan çarpım özetle aynı (alt grup x2)", t2 == t,
            {k: (t.get(k), t2.get(k)) for k in set(t) | set(t2) if t.get(k) != t2.get(k)})
    y2, _d = dosya_yaz(ozetli=False)
    cb3 = O.catia_bom_oku(y2)
    kontrol("özetsiz dosyada toplamlar ağaçtan", cb3["toplamlar"] == t)
    kontrol("Made / Bought okundu", BE.catia_kaynak_haritasi(cb) == {"ara_kros": "parca", "505602001": "standart"},
            BE.catia_kaynak_haritasi(cb))
    return y


def dene_eslestirme(y):
    print("2) eşleştirme")
    cb = O.catia_bom_oku(y)
    s = BE.bom_eslestir(KOMP, cb)
    d = {r["catia_part_no"] or r["step_ad"]: r for r in s["satirlar"]}
    kontrol("KAPAK eşleşti (3 = 3)", d["KAPAK"]["durum"] == "eşleşti")
    kontrol("ARA_KROS adet farklı (5 / 6)", d["ARA_KROS"]["durum"] == "adet farklı"
            and d["ARA_KROS"]["step_adet"] == 5 and d["ARA_KROS"]["catia_adet"] == 6)
    pr = next((r for k, r in d.items() if "PROFIL" in k), None)
    kontrol("sağ / sol profil tek öbek, nomenclature ile (2 = 1 + 1)",
            pr is not None and pr["durum"] == "eşleşti" and pr["catia_adet"] == 2
            and "PROFIL_SOL" in pr["catia_part_no"] and "PROFIL_SAG" in pr["catia_part_no"],
            pr)
    kontrol(".CATPart.28 eki ile Copy (1) of SAC_8 eşleşti",
            d.get("Copy (1) of SAC_8", {}).get("durum") == "eşleşti")
    kontrol("pul nomenclature ile eşleşti, malzeme grubu Steel",
            d["505602001"]["durum"] == "eşleşti" and d["505602001"]["malzeme"] == "Steel")
    kontrol("EKSTRA_SAC CATIA'da yok", d["EKSTRA_SAC"]["durum"] == "CATIA'da yok")
    kontrol("alt montaj eksik sayılmadı", "ALT_GRUP" not in d)
    kontrol("kaynak dikişi sayılmadı", "K12 dikiş" not in d and s["ozet"]["step_komponent"] == 7)
    o = s["ozet"]
    kontrol("özet sayıları", (o["eşleşti"], o["adet farklı"], o["STEP'te yok"], o["CATIA'da yok"]) == (5, 1, 0, 1), o)
    kontrol("malzeme eşlemesi yalnız gruplu puldan", s["esl"] == {"din125": "Steel"}, s["esl"])
    on = tempfile.mkdtemp(prefix="pi3d_catia_cikti_")
    BE.eslestirme_yaz(on, s, cb)
    kontrol("BOM_ESLESTIRME.csv / .md yazıldı",
            os.path.isfile(os.path.join(on, "BOM_ESLESTIRME.csv"))
            and "adet farklı" in open(os.path.join(on, "BOM_ESLESTIRME.md"), encoding="utf-8").read())


def dene_malzeme():
    print("3) malzeme")
    y0, _d = dosya_yaz(malzemeli=False, gruplu=False)
    try:
        O.malzeme_tablosu(y0)
        kontrol("Material sütunu yoksa açık hata", False, "hata verilmedi")
    except O.MalzemeDosyaHatasi as ex:
        kontrol("Material sütunu yoksa açık hata (CATIA ipucu)",
                "MALZEME sütunu yok" in str(ex) and "Define formats" in str(ex), str(ex)[:80])
    kontrol("malzeme_sutunu_var: Material ve malzeme grubu yoksa False",
            O.malzeme_sutunu_var(y0) is False)
    y, _d = dosya_yaz(malzemeli=False)
    kontrol("malzeme_sutunu_var: TraceParts malzeme grubu varsa True",
            O.malzeme_sutunu_var(y) is True)
    tab0 = O.malzeme_tablosu(y)
    kontrol("yalnız gruplu pul malzeme aldı (Steel), başlık / öbür parça yok",
            {r["kod"] for r in tab0} == {"505602001", "DIN125_M10_PUL", "505602001.CATPart"}
            and all(r["anahtar"] == "celik" for r in tab0), [(r["kod"], r["anahtar"]) for r in tab0])
    y2, _d = dosya_yaz(malzemeli=True)
    cb = O.catia_bom_oku(y2)
    kontrol("Material sütunu tanındı", cb["malzeme_sutunu"] is True)
    tab = O.malzeme_tablosu(y2)
    kodlar = {r["kod"]: r["anahtar"] for r in tab}
    kontrol("başlık satırı kod sanılmadı",
            not any(k.lower().startswith(("source", "type", "traceparts")) for k in kodlar), list(kodlar)[:6])
    kontrol("KAPAK -> çelik, KAUCUK -> kauçuk, ARA_KROS -> alüminyum",
            kodlar.get("KAPAK") == "celik" and kodlar.get("ARA_KROS") == "aluminyum"
            and (kodlar.get("KAUCUK_SILTE_3mm") or "").startswith("kaucuk"), kodlar)
    esl, bilinmeyen = O.malzeme_dosya_oku(y2)
    kontrol("malzeme_dosya_oku eşlemesi", esl.get("kapak") == "celik" and esl.get("ara_kros") == "aluminyum", esl)
    m, kay = O.malzeme_ata({"kod": "ARA_KROS", "ad": "ARA_KROS"}, esl, "celik", data_oncelik=False)
    kontrol("malzeme_ata: ARA_KROS alüminyum (seçim)", (m, kay) == ("aluminyum", "secim"), (m, kay))


if __name__ == "__main__":
    y = dene_cozum()
    dene_eslestirme(y)
    dene_malzeme()
    print()
    if HATA:
        print(f"SONUC: {len(HATA)} HATA: " + ", ".join(HATA))
        sys.exit(1)
    print("SONUC: TUM DENETIMLER GECTI")
