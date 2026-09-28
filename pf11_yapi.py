# -*- coding: utf-8 -*-
"""YAPISAL TANIMA: bağlantı elemanını biçim kalıbıyla değil, YAPISAL
ÖĞELERİYLE tanır.

Cıvata, somun, pul tiplerinin sonu yok (altıköşe, imbus, torx, yıldız,
düz, bombe, mercimek, havşa, mantar, para, kare, flanşlı, kronlu,
kelebek, kapalı, manşon, kaynak somunu, T-somun, mapa...). Her birine
ayrı kalıp yazmak yerine parça ÖĞELERİNE ayrılır:

    gövde   eksen boyunca dolu, yuvarlak, sabit çaplı bölüm (şaft)
    baş     gövdenin bir ucunda ondan geniş bölüm
    delik   eksen boyunca boşluk (boydan boya ya da kör)
    lokma   başın ucundaki kör yuva: altıgen (imbus), lobut (torx),
            çarpı (yıldız), yarık (düz tornavida), kare
    tutma   anahtar yüzeyi: altıgen, kare, harici torx, tırtıl
    flanş   başın / somunun gövde tarafında yuvarlak geniş bölüm
    açık    bazı yönlerde malzeme yok: kanat, yarık (kronlu), göz (mapa),
            T baş, tırnak

Tip bu öğelerin BİRLEŞİMİNDEN çıkar:
    gövde + baş(+lokma)            -> cıvata / vida (baş ve lokma adıyla)
    delik + tutma, başsız, kısa    -> somun (flanş, yarık, kanat... ile)
    delik + iki eş merkezli halka  -> rulman (ölçüsü ISO 15 serileriyle)
    delik + ince halka             -> pul (dişli, yaylı, konik; düz/kare aday)
    gövde, başsız, diş modelli     -> saplama / dişli çubuk
    gövde, başsız, uçta lokma      -> setskur (başsız imbus)
    aynı çaplı bükülmüş çubuk      -> U / J cıvata, kanca (aday)

Ölçüm: eksen boyunca 60 kotta, eksenden 24 yöne (15°) ışın atılır. Her
kotta dış ve iç yarıçapın yöne göre değişimi Fourier ile çözülür: kaç
katlı simetri (2: yarık, 4: kare / çarpı, 6: altıgen / torx, 12+: tırtıl)
ve ne kadar (en büyük / en küçük). Diş ve tırtıl modellenmiş olsa da
öğeler değişmez.

Karar ilkesi: öğeler tanıdık bir bağlantı elemanı oranındaysa KARAR
(standart); tanıdık öğe var ama oran alışılmadıksa yalnız ADAY (kontrol
listesine). Emin olunmayana karar verilmez.
"""
from __future__ import annotations

import cmath
import math

import pf8_tani as TN

N_KOT = 60
N_YON = 24


# ------------------------------------------------------------ ölçüm
def tarama(t, n_kot=N_KOT, n_yon=N_YON):
    """Eksen Z'de, orijinden geçen katıyı tarar. Döner (H, kotlar);
    her kot: {"z", "ri": [..], "ro": [..], "ara": [..]} yön başına iç /
    dış yarıçap (malzeme yoksa None) ve malzeme aralığı sayısı."""
    from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
    from OCP.gp import gp_Lin, gp_Pnt, gp_Dir
    kb = TN._kutu(t)
    z0, z1 = kb[2], kb[5]
    R = 2.0 * max(abs(v) for v in (kb[0], kb[1], kb[3], kb[4])) + 1.0
    it = IntCurvesFace_ShapeIntersector()
    it.Load(t, 1e-6)
    kotlar = []
    for i in range(n_kot):
        z = z0 + (z1 - z0) * (i + 0.5) / n_kot
        ri, ro, ara, p0, tek = [], [], [], [], []
        for j in range(n_yon):
            a = 2 * math.pi * j / n_yon
            it.Perform(gp_Lin(gp_Pnt(0.0, 0.0, z), gp_Dir(math.cos(a), math.sin(a), 0.0)),
                       0.0, R)
            p = sorted(it.WParameter(k) for k in range(1, it.NbPnt() + 1))
            p = [x for q, x in enumerate(p) if q == 0 or x - p[q - 1] > 1e-6]
            if not p:
                ri.append(None)
                ro.append(None)
                ara.append(0)
                p0.append(None)
                tek.append(None)
                continue
            ic = len(p) % 2 == 1                     # eksen malzemenin içinde
            ri.append(0.0 if ic else p[0])
            ro.append(p[-1])
            ara.append((len(p) + (1 if ic else 0)) // 2)
            p0.append(p[0])
            tek.append(ic)
        # Bileşik katıda (rulman: halkalar + bilyeler) bir ışın iki katının
        # değme noktasından geçince kesişim sayısı tekleşir ve eksen
        # "malzeme içinde" sanılır. Karar ışınların ÇOĞUNLUĞUNA göre verilir.
        oy = [q for q in tek if q is not None]
        if oy:
            ic_cok = sum(oy) >= 0.5 * len(oy)
            ri = [None if q is None else (0.0 if ic_cok else q) for q in p0]
        kotlar.append({"z": z - z0, "ri": ri, "ro": ro, "ara": ara})
    return z1 - z0, kotlar


def harmonik(v):
    """Yöne göre değişen yarıçaptan (eşit aralıklı örnekler) baskın
    simetri katı ve en büyük / en küçük oranı: (k, oran). Değişim yoksa
    (0, 1)."""
    x = [q for q in v if q is not None]
    if len(x) < len(v) or not x or min(x) <= 0:
        return None
    oran = max(x) / min(x)
    if oran < 1.03:
        return 0, oran
    n = len(v)
    ort = sum(v) / n
    en_k, en_a = 0, 0.0
    for k in range(1, n // 2 + 1):
        a = abs(sum(v[j] * cmath.exp(-2j * math.pi * k * j / n) for j in range(n))) / n
        if a > en_a * 1.15:
            en_k, en_a = k, a
    return en_k, oran


def _etiket(v):
    """Bir kotun dış (ya da iç) biçimi."""
    h = harmonik(v)
    if h is None:
        return "acik"                                  # bazı yönlerde malzeme yok
    k, o = h
    if k == 0:
        return "yuvarlak"
    if k == 6 and 1.10 <= o <= 1.20:
        return "altigen"
    if k == 6 and o > 1.20:
        return "lobut"                                 # torx
    if k == 4 and 1.30 <= o <= 1.50:
        return "kare"
    if k == 4 and o > 1.50:
        return "carpi"                                 # yıldız (phillips)
    if k == 2:
        return "yarik"
    if k >= 8 and o < 1.15:
        return "tirtil"
    if k == 3:
        return "uc_cikinti"
    return f"k{k}"


def _cogunluk(lst):
    return max(set(lst), key=lst.count) if lst else None


def _m(v):
    return f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",")


# ------------------------------------------------------------ yapı
def yapi(sh, eksen=None):
    """Parçanın öğeleri (sözlük) ya da None (dönel eksen yok)."""
    if eksen is None:
        yz = TN._yuzler(sh)
        eksen = TN._ana_eksen(yz) or TN._simetri_ekseni(sh)
    if not eksen:
        return None
    t = TN._eksene_tasi(sh, *eksen)
    H, kot = tarama(t)
    if H <= 0:
        return None
    n = len(kot)
    for k in kot:
        dolu = [r for r in k["ro"] if r is not None]
        k["ro_max"] = max(dolu) if dolu else 0.0
        k["ro_min"] = min(dolu) if dolu else 0.0          # altıgende anahtar ağzı / 2
        k["dis"] = _etiket(k["ro"])
        k["dolu_eksen"] = all(r == 0.0 for r in k["ri"] if r is not None) and \
            any(r is not None for r in k["ri"])
        ic = [r for r in k["ri"] if r is not None]
        k["delik"] = bool(ic) and all(r > 0 for r in ic) and len(ic) == len(k["ri"])
        k["ic"] = _etiket(k["ri"]) if k["delik"] else None
        k["bos"] = sum(1 for r in k["ro"] if r is None) / len(k["ro"])
    return {"H": H, "kot": kot, "n": n, "eksen": eksen}


def _gövde(y):
    """En uzun dolu, yuvarlak (ya da tırtıl / diş), sabit çaplı kot dizisi:
    (bas, son, yaricap) ya da None."""
    kot, n = y["kot"], y["n"]
    en = None
    i = 0
    while i < n:
        if not (kot[i]["dolu_eksen"] and kot[i]["dis"] in ("yuvarlak", "tirtil")):
            i += 1
            continue
        j = i
        rs = []
        while j < n and kot[j]["dolu_eksen"] and kot[j]["dis"] in ("yuvarlak", "tirtil"):
            rs.append(kot[j]["ro_max"])
            j += 1
        med = sorted(rs)[len(rs) // 2]
        # uçlardaki pah / diş dibi kotlarını at, ortancadan %8 sapanları
        a, b = i, j
        while a < b and abs(kot[a]["ro_max"] - med) > 0.08 * med:
            a += 1
        while b > a and abs(kot[b - 1]["ro_max"] - med) > 0.08 * med:
            b -= 1
        if b - a > 0 and (en is None or b - a > en[1] - en[0]):
            en = (a, b, med)
        i = j
    return en


def _bas_profili(rs):
    """Başın gövdeden tepeye yarıçap dizisinden alt ve üst biçim."""
    m = max(rs)
    alt_konik = rs[0] < 0.8 * m
    ust_kubbe = rs[-1] < 0.8 * m
    return alt_konik, ust_kubbe


def _lokma(kotlar):
    """Baş ucundaki kör yuvanın tipi (kotlar tepeden gövdeye doğru)."""
    ic = [k["ic"] for k in kotlar if k["delik"] and k["ic"]]
    yarik = [k for k in kotlar if 0 < k["bos"] < 0.5 and not k["dolu_eksen"]]
    if len(yarik) >= 2 and not ic:
        return "düz (yarık)"
    if not ic:
        return None
    e = _cogunluk(ic)
    return {"altigen": "imbus (altıgen lokma)", "lobut": "torx", "carpi": "yıldız",
            "kare": "kare lokma", "yarik": "düz (yarık)",
            "yuvarlak": None}.get(e, None)


# Sabit bilyalı rulman ölçüleri (ISO 15): kod -> (iç Ø d, dış Ø D, genişlik B)
RULMAN = {}
for _kod, _d, _D, _B in (
        ("625", 5, 16, 5), ("626", 6, 19, 6), ("607", 7, 19, 6), ("608", 8, 22, 7),
        ("609", 9, 24, 7), ("6000", 10, 26, 8), ("6001", 12, 28, 8), ("6002", 15, 32, 9),
        ("6003", 17, 35, 10), ("6004", 20, 42, 12), ("6005", 25, 47, 12), ("6006", 30, 55, 13),
        ("6007", 35, 62, 14), ("6008", 40, 68, 15), ("6009", 45, 75, 16), ("6010", 50, 80, 16),
        ("6200", 10, 30, 9), ("6201", 12, 32, 10), ("6202", 15, 35, 11), ("6203", 17, 40, 12),
        ("6204", 20, 47, 14), ("6205", 25, 52, 15), ("6206", 30, 62, 16), ("6207", 35, 72, 17),
        ("6208", 40, 80, 18), ("6209", 45, 85, 19), ("6210", 50, 90, 20),
        ("6300", 10, 35, 11), ("6301", 12, 37, 12), ("6302", 15, 42, 13), ("6303", 17, 47, 14),
        ("6304", 20, 52, 15), ("6305", 25, 62, 17), ("6306", 30, 72, 19), ("6307", 35, 80, 21),
        ("6308", 40, 90, 23), ("6309", 45, 100, 25), ("6310", 50, 110, 27),
        ("6900", 10, 22, 6), ("6901", 12, 24, 6), ("6902", 15, 28, 7), ("6903", 17, 30, 7),
        ("6904", 20, 37, 9), ("6905", 25, 42, 9)):
    RULMAN[_kod] = (_d, _D, _B)


def _rulman(y):
    """Rulman: boydan boya delik ve eksenden dışarı giden ışın İKİ ya da
    daha çok malzeme bölgesi keser (iç halka - bilye / makara - dış
    halka). Burç, pul, somun tek bölgedir."""
    kot, n, H = y["kot"], y["n"], y["H"]
    if sum(k["delik"] for k in kot) < 0.9 * n:
        return None
    # İki halka HER yönde vardır: kotun bütün ışınları en az iki bölge
    # keser ve dış yuvarlaktır. (Çok delikli plakada yalnız bazı ışınlar
    # başka bir delikten geçip iki bölge görür: Dachplatte, Rollenplatte.)
    iki = [k for k in kot if k["bos"] == 0 and min(k["ara"]) >= 2 and k["dis"] == "yuvarlak"]
    if len(iki) < 0.6 * n:
        return None
    ri = sorted(min(r for r in k["ri"] if r is not None) for k in kot if k["delik"])
    ro = sorted(k["ro_max"] for k in kot)
    d, D = 2 * ri[len(ri) // 2], 2 * ro[n // 2]
    if H > 0.8 * D or D < 1.5 * d:
        return None
    kod = next((k_ for k_, (a, b, c) in RULMAN.items()
                if abs(a - d) <= 0.3 and abs(b - D) <= 0.5 and abs(c - H) <= 0.4), None)
    return ("standart", "rulman" + (f" ({kod} ölçüsünde)" if kod else ""),
            f"yapı: iki eş merkezli halka (ışının {max(max(k['ara']) for k in kot)} "
            f"bölgesi), iç Ø{_m(d)} x dış Ø{_m(D)} x {_m(H)}"
            + (f" = {kod} (ISO 15)" if kod else ""), True)


def yapisal_tani(sh, eksen=None):
    """(sinif, tip, gerekce, kesin) ya da None. kesin=False: yalnız aday."""
    try:
        y = yapi(sh, eksen)
    except Exception:
        return None
    if not y:
        return None
    return _rulman(y) or _baslı(y) or _somun(y) or _pul(y) or _basiz(y)


def _baslı(y):
    kot, n, H = y["kot"], y["n"], y["H"]
    g = _gövde(y)
    if not g:
        return None
    a, b, r = g
    d = 2 * r
    Lg = H * (b - a) / n
    if Lg < 1.0 * d or (b - a) < 0.3 * n:
        return None
    # baş: gövdenin bir ucunda kalan kotlar; öbür uçta yalnız pah olabilir
    alt, ust = list(range(0, a)), list(range(b, n))
    genis = lambda ks: [i for i in ks if (kot[i]["ro_max"] >= 1.25 * r or kot[i]["bos"] > 0)]
    adaylar = []
    for ks, uc in ((alt, "alt"), (ust, "ust")):
        if genis(ks):
            adaylar.append((ks, uc))
    if len(adaylar) != 1:
        return None                         # iki ucunda da baş (kademeli mil, makara)
    bas, uc = adaylar[0]
    diger = ust if uc == "alt" else alt
    if len(diger) > 0.12 * n:
        return None
    if uc == "alt":
        bas = bas[::-1]                     # gövdeden tepeye sırala
    Hb = H * len(bas) / n
    D = 2 * max(kot[i]["ro_max"] for i in bas)
    if not (1.25 * d <= D <= 3.5 * d) or Hb > 1.4 * d:
        return None
    # başın öğeleri
    etiket = [kot[i]["dis"] for i in bas]
    dis = _cogunluk([e for e in etiket if e != "yuvarlak"]) if \
        sum(e != "yuvarlak" for e in etiket) >= 0.3 * len(etiket) else "yuvarlak"
    # tepe tarafı kotlar (lokma arama): başın gövdeden uzak yarısı
    tepe = [kot[i] for i in bas[len(bas) // 3:]][::-1]
    lokma = _lokma(tepe)
    rs = [kot[i]["ro_max"] for i in bas]
    alt_konik, ust_kubbe = _bas_profili(rs)
    flans = False
    if dis in ("altigen", "kare", "lobut"):
        kose = max(kot[i]["ro_max"] for i in bas if kot[i]["dis"] == dis)
        flans = any(kot[i]["dis"] == "yuvarlak" and kot[i]["ro_max"] > 1.05 * kose
                    for i in bas[:max(1, len(bas) // 2)])
    acik = sum(kot[i]["bos"] > 0 for i in bas) >= 0.3 * len(bas)
    # adlandırma
    if acik and not lokma:
        ara4 = any(max(kot[i]["ara"]) >= 2 for i in bas)
        ad = "mapa (göz) başlı" if ara4 else "özel başlı (T / kanat)"
        kesin = False
    elif dis == "altigen":
        ad = "altıköşe flanşlı başlı" if flans else "altıköşe başlı"
        kesin = True
    elif dis == "kare":
        ad = "kare başlı"
        kesin = True
    elif dis == "lobut":
        ad = "harici torx başlı"
        kesin = True
    else:
        oran = Hb / d
        if alt_konik and ust_kubbe:
            ad = "mercimek başlı"
        elif alt_konik:
            ad = "havşa başlı"
        elif ust_kubbe:
            ad = "mantar başlı" if D >= 2.2 * d and oran <= 0.35 else "bombe başlı"
        elif oran < 0.35 and D >= 1.9 * d:
            ad = "para (geniş düz) başlı"
        elif oran >= 0.75:
            ad = "silindir başlı"
        else:
            ad = "alçak silindir başlı"
        # yuvarlak başta tanıdık oran + lokma ya da kubbe/havşa: kesin
        kesin = bool(lokma) or alt_konik or ust_kubbe
    tip = f"{ad} cıvata" + (f", {lokma}" if lokma else "")
    ger = (f"yapı: gövde Ø{_m(d)} x {_m(Lg)} + baş Ø{_m(D)} x {_m(Hb)}"
           + (f", baş dışı {dis}" if dis != "yuvarlak" else "")
           + (", flanş" if flans else "") + (f", lokma {lokma}" if lokma else "")
           + (", başta açık bölge" if acik else ""))
    return ("standart", tip, ger, kesin)


def _somun(y):
    kot, n, H = y["kot"], y["n"], y["H"]
    delikli = [k for k in kot if k["delik"]]
    if len(delikli) < 0.5 * n:
        return None
    ric = sorted(min(r for r in k["ri"]) for k in delikli)
    db = 2 * ric[len(ric) // 2]
    boydan = all(k["delik"] or k["bos"] > 0 for k in kot)
    if db <= 0 or H > 4.5 * db:            # manşon (uzatma) somun ~3 d
        return None
    if max(k["ro_max"] for k in kot) > 75:  # 150 mm'den büyük "somun" yok
        return None
    etiket = [k["dis"] for k in kot]
    tutma = [e for e in etiket if e in ("altigen", "kare", "lobut")]
    D = 2 * max(k["ro_max"] for k in kot)
    if not (1.3 * db <= D <= 4.0 * db):
        return None
    # Somun yüksekliği en az 0,45 d (ince somun 0,5 d); daha yassı delikli
    # altıgen / kare parça PLAKADIR (kaynaklı kasada 50x50x3 delikli
    # bağlantı braketi "kare somun" çıkıyordu).
    if H < 0.45 * db:
        return None
    # perçin somun: bir ucunda İNCE (boyun %15'i), gövdeden geniş flanş
    # (yuvarlak ya da altıgen - tente modelindeki 55RS865978'in flanşı
    # altıgen); gövde uzun (en az 1,3 delik çapı). Genişlik en küçük
    # yarıçapla (altıgende anahtar ağzı) karşılaştırılır.
    if H >= 1.3 * db:                   # flanşlı somun ~1 d: karışmaz
        for sira in (kot, kot[::-1]):
            govde = sira[max(1, n // 5):]
            rg = sorted(k["ro_min"] for k in govde)[len(govde) // 2]
            j = 0
            while j < 0.15 * n and sira[j]["ro_min"] > 1.06 * rg:
                j += 1
            ust = 1.02 * max(q["ro_max"] for q in sira[j + 2:])
            # gövde tek düzgün bölüm olmalı (kapalı somunun kubbesi değil)
            duz = sum(abs(k["ro_min"] - rg) <= 0.1 * rg for k in sira[j + 2:])
            if 1 <= j and all(k["ro_max"] <= ust for k in sira[j + 2:]) \
                    and duz >= 0.8 * len(sira[j + 2:]):
                # Flanşlı burç ve üretim flanşı da aynı yapıdadır. Perçin
                # somunu ayıran öğe: gövde altıgen / tırtıllı ya da delik
                # KADEMELİ (flanş tarafı geniş sıkışma bölgesi, uç dişli).
                gbic = _cogunluk([k["dis"] for k in govde])
                di = [min(r for r in k["ri"]) for k in sira if k["delik"]]
                kademeli = len(di) >= 4 and \
                    sorted(di[:len(di) // 3])[len(di) // 6] >= 1.08 * sorted(di[-(len(di) // 3):])[len(di) // 6]
                Df = 2 * max(k["ro_max"] for k in sira[:j])
                ger = (f"yapı: ince flanş Ø{_m(Df)} + gövde Ø{_m(2 * rg)} ({gbic}), "
                       f"delik Ø{_m(db)}" + (" kademeli" if kademeli else "")
                       + ("" if boydan else " (kapalı uçlu)"))
                if gbic != "yuvarlak" or kademeli:
                    return ("standart", "perçin somun", ger, True)
                if Df <= 1.7 * 2 * rg:
                    return ("standart", "perçin somun / flanşlı burç", ger, False)
                return None
    acik = [i for i, k in enumerate(kot) if k["bos"] > 0]
    tirtil = [e for e in etiket if e == "tirtil"]
    ozellik = []
    if len(tutma) >= 0.4 * n:
        dis = _cogunluk(tutma)
        ad = {"altigen": "altıköşe somun", "kare": "kare somun",
              "lobut": "torx somun"}[dis]
        kose = max(k["ro_max"] for k in kot if k["dis"] == dis)
        # uçlarda yuvarlak ve köşeden geniş: flanş
        uclar = kot[:n // 4] + kot[-(n // 4):]
        if any(k["dis"] in ("yuvarlak", "tirtil") and k["ro_max"] > 1.05 * kose for k in uclar):
            ad = ("tırtıllı flanşlı somun" if any(k["dis"] == "tirtil" for k in uclar)
                  else "flanşlı somun")
        if acik and max(acik) - min(acik) < 0.5 * n and (min(acik) > 0.5 * n or max(acik) < 0.5 * n):
            ad = "kronlu (taçlı) somun"
            ozellik.append("bir ucunda yarıklar")
        if not boydan:
            ad = "kapalı (kör) somun"
        elif H >= 1.6 * db:
            ad = "manşon (uzatma) somun"
        kesin = True
    elif acik and len(acik) >= 0.3 * n and max(max(k["ara"]) for k in kot) <= 2:
        ad = "kelebek somun" if any(k["ro_max"] > 1.8 * db for k in kot) else "özel somun"
        kesin = False
    elif len(tirtil) >= 0.4 * n:
        ad = "tırtıllı somun / burç"
        kesin = False
    else:
        return None
    ger = (f"yapı: delik Ø{_m(db)}{'' if boydan else ' (kör)'}, dış Ø{_m(D)}, "
           f"yükseklik {_m(H)}" + (", " + ", ".join(ozellik) if ozellik else ""))
    return ("standart", ad, ger, kesin)


def _cok_katli(e):
    """k8, k12... : 8 ve üstü katlı düzenli dizi (diş, tırtıl)."""
    return bool(e) and e.startswith("k") and e[1:].isdigit() and int(e[1:]) >= 8


def _pul(y):
    """Pul: boydan delikli İNCE halka. Tipini öğeler belirler: dış / iç
    diş (tırtıl), yarık (yaylı - grover), konik (belleville, havşa pulu),
    kare dış. Düz ve kare pul yapıca delikli plakaya / üretim pulu
    (distans) eşittir: yalnız aday."""
    kot, n, H = y["kot"], y["n"], y["H"]
    dk = [k for k in kot if k["delik"] or k["bos"] > 0]
    if len(dk) < 0.8 * n:
        return None
    ri = sorted(min(r for r in k["ri"] if r is not None) for k in kot
                if any(r is not None for r in k["ri"]))
    if not ri or ri[len(ri) // 2] <= 0:
        return None
    db = 2 * ri[len(ri) // 2]
    D = 2 * max(k["ro_max"] for k in kot)
    if not (H <= 0.35 * D and 1.3 * db <= D <= 5 * db) or D > 150:
        return None
    dis = _cogunluk([k["dis"] for k in kot])
    acik = [k for k in kot if k["bos"] > 0]
    # yaylı (grover): her kotta yalnız 1-2 yönde malzeme yok (yarık), gerisi
    # yuvarlak halka
    yarik = bool(acik) and len(acik) >= 0.5 * n and \
        all(sum(r is None for r in k["ro"]) <= 2 for k in acik)
    # dış biçim düzenli olmalı (yuvarlak, kare ya da çok katlı diş); delikli
    # sac plaka delik ekseninden bakınca düzensizdir (k2, k3, açık...)
    if not yarik and dis not in ("yuvarlak", "kare", "tirtil") and not _cok_katli(dis):
        return None
    ic = _cogunluk([k["ic"] for k in kot if k["ic"]])
    ro = [k["ro_max"] for k in kot]
    rn = [min(r for r in k["ri"] if r is not None) for k in kot
          if any(r is not None for r in k["ri"])]
    konik = (max(ro) - min(ro) > 0.12 * max(ro)) or (max(rn) - min(rn) > 0.15 * max(rn))
    if yarik:
        ad, kesin = "yaylı (grover) pul", True
    elif dis == "tirtil" or _cok_katli(dis):
        ad, kesin = "dış dişli (tırtıllı) pul", True
    elif ic == "tirtil" or _cok_katli(ic):
        ad, kesin = "iç dişli pul", True
    elif konik:
        ad, kesin = "konik (belleville / havşa) pul", True
    elif dis == "kare":
        ad, kesin = "kare pul", False
    else:
        ad, kesin = "düz pul", False
    return ("standart", ad, f"yapı: ince halka Ø{_m(D)} / Ø{_m(db)} x {_m(H)}", kesin)


def _basiz(y):
    """Başsız dolu çubuk: uçta lokma varsa setskur; yoksa karar yok
    (dişi modellenmişse saplama kararını tani() verir)."""
    kot, n, H = y["kot"], y["n"], y["H"]
    g = _gövde(y)
    if not g:
        return None
    a, b, r = g
    if (b - a) < 0.7 * n:
        return None
    for uclar in (kot[:n // 5], kot[-(n // 5):][::-1]):
        lok = _lokma(uclar)
        if lok and lok != "düz (yarık)":
            return ("standart", f"setskur (başsız), {lok}",
                    f"yapı: başsız gövde Ø{_m(2 * r)} x {_m(H)}, uçta {lok}", True)
    return None


# ------------------------------------------------------------ bükülmüş çubuk
def bukulmus_cubuk(sh):
    """Aynı çaplı bükülmüş çubuk (U / J cıvata, kanca, tel): yüzeyin çoğu
    aynı yarıçaplı silindir + tor. Döner (tip, gerekçe, dişli) ya da None."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Torus
    yz = TN._yuzler(sh)
    if not yz:
        return None
    top = sum(y["alan"] for y in yz)
    torlar = [y for y in yz if y["tip"] == "tor"]
    if not torlar:
        return None
    rr = []
    for y in torlar:
        s = BRepAdaptor_Surface(y["f"])
        if s.GetType() == GeomAbs_Torus:
            rr.append(s.Torus().MinorRadius())
    if not rr:
        return None
    r = sorted(rr)[len(rr) // 2]
    ayni = sum(y["alan"] for y in yz
               if (y["tip"] == "silindir" and abs(y["r"] - r) < 0.02 * r + 0.01)) \
        + sum(y["alan"] for y, q in zip(torlar, rr) if abs(q - r) < 0.02 * r + 0.01)
    serbest = sum(y["alan"] for y in yz if y["tip"] == "diger") / top
    if ayni < 0.6 * top or all(y["tip"] == "tor" for y in yz):
        return None                         # yalnız tor: o-ring
    return (f"bükülmüş Ø{_m(2 * r)} çubuk (U / J cıvata, kulp, kanca)",
            f"yapı: yüzeyin %{100 * ayni / top:.0f}'i aynı Ø{_m(2 * r)} silindir + büküm"
            + (f", uçlarda diş (%{100 * serbest:.0f})" if serbest >= 0.08 else ""),
            serbest >= 0.08)
