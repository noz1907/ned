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
import pf9_excel as XL

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
    return XL.tr(v, 1)


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


# ------------------------------------------------------------ yay
# Yayın yapısal öğesi TEKRARLANAN KATMANDIR: sarım eksenine paralel bir
# ışın tel kesitini düzenli aralıklarla, her seferinde aynı kalınlıkta
# keser ve sarımın ortası boştur. Bunun "spir" (helis) olduğunu ışını
# eksen çevresinde 90° döndürerek ölçeriz: helisin tel kesitleri her 90°
# de ÇEYREK ADIM kayar; üst üste dizilmiş disk / sac paketinde kayma
# yoktur. Uçlar sarım dışına taşıyorsa türü uçlar söyler:
#   eksen boyunca halka / kanca  -> çekme yayı
#   yana (teğet) bacak           -> burulma yayı
#   uç yok, adım telden büyük    -> basma yayı (iki uç çapı farklı: konik)
# Dişi modellenmiş cıvata da ışında tekrar gösterir ama içi DOLUDUR.
YAY_IZGARA = 9
YAY_DOLU = 0.35             # gabari doluluğu bundan büyükse yay değil
YAY_DUZLEM = 0.30           # düzlem yüz alanı payı bundan büyükse yay değil
YAY_KATMAN = 5              # "katmanlı yay" adayı için en az katman


def _tekrar(p, en_az=3):
    """Işın kesişimlerinden malzeme aralıkları; içlerindeki EN UZUN düzenli
    dizi (eşit kalınlık, eşit adım) -> (kalınlık, adım, sayı, ilk), yoksa
    None. Uçtaki kapak / halka / bacak kesişimleri dizinin dışında kalır."""
    if len(p) < 2 * en_az or len(p) % 2:
        return None
    ara = [(p[i], p[i + 1]) for i in range(0, len(p), 2)]
    n = len(ara)
    en = None
    for i in range(n - en_az + 1):
        if en and n - i <= en[2]:
            break
        k0 = ara[i][1] - ara[i][0]
        a0 = ara[i + 1][0] - ara[i][0] if i + 1 < n else 0
        if k0 <= 0 or a0 <= k0 * 0.999:
            continue
        j = i + 1
        while (j < n and abs((ara[j][1] - ara[j][0]) - k0) <= 0.35 * k0
               and abs((ara[j][0] - ara[j - 1][0]) - a0) <= 0.25 * a0):
            j += 1
        if j - i >= en_az and (en is None or j - i > en[2]):
            kal = sorted(b - a for a, b in ara[i:j])[(j - i) // 2]
            adim = (ara[j - 1][0] - ara[i][0]) / (j - i - 1)
            en = (kal, adim, j - i, ara[i][0])
    return en


class _Ag:
    """Katının üçgen ağı (numpy) ve aynı çerçevedeki OCC kopyası. Eksene
    paralel ışın kesişimi ağ üzerinde yapılır: OCC'nin tam yüzey kesişimi
    helis (BSpline) yüzde ışın başına ~0,1 sn sürer, ağda ~1 ms."""

    def __init__(self, sh=None, ucg=None):
        import numpy as np
        self.u = ucg if ucg is not None else self._ag(sh)
        u = self.u
        self.xmin = u[:, :, 0].min(1)
        self.xmax = u[:, :, 0].max(1)
        self.ymin = u[:, :, 1].min(1)
        self.ymax = u[:, :, 1].max(1)
        self.zmin = u[:, :, 2].min(1)
        self.zmax = u[:, :, 2].max(1)
        m = u.mean(1)
        n = np.cross(u[:, 1] - u[:, 0], u[:, 2] - u[:, 0])
        self.merkez = m
        self.alan = 0.5 * np.sqrt((n * n).sum(1))

    def _sec(self, za, zb, r_en):
        import numpy as np
        m = np.ones(len(self.u), bool)
        if za is not None:
            m &= (self.merkez[:, 2] >= za) & (self.merkez[:, 2] <= zb)
        if r_en is not None:
            m &= np.hypot(self.merkez[:, 0], self.merkez[:, 1]) <= r_en
        return m

    def kutu(self, za=None, zb=None, r_en=None):
        """Sınır kutusu (ağ hassasiyetinde, BSpline şişmesi olmadan); za, zb:
        yalnız o kotlar arasındaki, r_en: yalnız eksene (Z) o kadar yakın
        üçgenlerin."""
        u = self.u[self._sec(za, zb, r_en)]
        if len(u) == 0:
            return None
        a, b = u.min((0, 1)), u.max((0, 1))
        return (a[0], a[1], a[2], b[0], b[1], b[2])

    def agirlik(self, za, zb, r_en=None):
        """za..zb kotlarındaki (ve eksene r_en'den yakın) yüzeyin (alan)
        ağırlık merkezi."""
        m = self._sec(za, zb, r_en)
        a = self.alan[m]
        if a.sum() <= 0:
            return None
        return tuple((self.merkez[m] * a[:, None]).sum(0) / a.sum())

    @staticmethod
    def _ag(sh):
        import numpy as np
        from OCP.BRep import BRep_Tool
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.TopAbs import TopAbs_FACE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopLoc import TopLoc_Location
        from OCP.TopoDS import TopoDS
        kb = _kutu(sh)
        B = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]) or 1.0
        BRepMesh_IncrementalMesh(sh, B / 300.0, False, 0.3, True)
        out = []
        ex = TopExp_Explorer(sh, TopAbs_FACE)
        while ex.More():
            f = TopoDS.Face_s(ex.Current())
            ex.Next()
            loc = TopLoc_Location()
            t = BRep_Tool.Triangulation_s(f, loc)
            if t is None:
                continue
            tr = loc.Transformation()
            pts = np.array([[q.X(), q.Y(), q.Z()] for q in
                            (t.Node(i).Transformed(tr) for i in range(1, t.NbNodes() + 1))])
            ic = np.array([t.Triangle(i).Get() for i in range(1, t.NbTriangles() + 1)]) - 1
            out.append(pts[ic])
        return np.concatenate(out) if out else np.zeros((0, 3, 3))

    def tasi(self, o, d):
        """Eksen Z olacak, eksen orijinden geçecek şekilde taşınmış kopya."""
        import numpy as np
        from OCP.gp import gp_Trsf, gp_Ax3, gp_Pnt, gp_Dir
        t = gp_Trsf()
        t.SetTransformation(gp_Ax3(gp_Pnt(*o), gp_Dir(*d)))
        M = np.array([[t.Value(i, j) for j in range(1, 5)] for i in range(1, 4)])
        return _Ag(ucg=self.u @ M[:, :3].T + M[:, 3])

    def kes(self, x, y, z0, z1):
        """(x, y)'den geçen, Z'ye paralel ışının z0..z1 arası kesişimleri."""
        import numpy as np
        m = (self.xmin <= x) & (self.xmax >= x) & (self.ymin <= y) & (self.ymax >= y)
        if not m.any():
            return []
        u = self.u[m]
        a, b, c = u[:, 0], u[:, 1], u[:, 2]
        d = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
        ok = np.abs(d) > 1e-18
        a, b, c, d = a[ok], b[ok], c[ok], d[ok]
        l1 = ((b[:, 0] - x) * (c[:, 1] - y) - (c[:, 0] - x) * (b[:, 1] - y)) / d
        l2 = ((c[:, 0] - x) * (a[:, 1] - y) - (a[:, 0] - x) * (c[:, 1] - y)) / d
        l3 = 1.0 - l1 - l2
        ic = (l1 >= -1e-12) & (l2 >= -1e-12) & (l3 >= -1e-12)
        z = l1[ic] * a[ic, 2] + l2[ic] * b[ic, 2] + l3[ic] * c[ic, 2]
        z = np.sort(z[(z >= z0) & (z <= z1)])
        out = []
        for v in z:                      # ortak kenardan geçen ışın: çift sayılmasın
            if not out or v - out[-1] > 1e-6:
                out.append(float(v))
        return out


def _isin(ag, x, y, z0, z1):
    return ag.kes(x, y, z0, z1)


def _kutu(sh):
    """Hassas sınır kutusu: helis / BSpline yüzde hızlı kutu kontrol
    noktalarını da kapsar ve çapı iki katına kadar şişirir."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    k = Bnd_Box()
    BRepBndLib.AddOptimal_s(sh, k, False, False)
    return k.Get()


def _tara(it, b):
    """z'ye paralel ışın ızgarası: en çok tekrar gösteren ışın."""
    en = None
    for i in range(YAY_IZGARA):
        for j in range(YAY_IZGARA):
            x = b[0] + (b[3] - b[0]) * (i + 0.5) / YAY_IZGARA
            y = b[1] + (b[4] - b[1]) * (j + 0.5) / YAY_IZGARA
            q = _isin(it, x, y, b[2] - 1.0, b[5] + 1.0)
            r = _tekrar(q)
            if r and (en is None or r[2] > en[0][2]):
                en = (r, (x, y), q)
    return en


def _cember(xy):
    """En küçük kareler çemberi (Kasa): (cx, cy, r) ya da None."""
    n = len(xy)
    if n < 3:
        return None
    sxx = sxy = syy = sx = sy = sxz = syz = sz = 0.0
    for x, y in xy:
        z = x * x + y * y
        sxx += x * x; sxy += x * y; syy += y * y; sx += x; sy += y
        sxz += x * z; syz += y * z; sz += z
    A = ((sxx, sxy, sx), (sxy, syy, sy), (sx, sy, n))
    B = (sxz, syz, sz)

    def det(M):
        return (M[0][0] * (M[1][1] * M[2][2] - M[1][2] * M[2][1])
                - M[0][1] * (M[1][0] * M[2][2] - M[1][2] * M[2][0])
                + M[0][2] * (M[1][0] * M[2][1] - M[1][1] * M[2][0]))
    D = det(A)
    if abs(D) < 1e-12:
        return None
    sol = []
    for k in range(3):
        M = [list(r_) for r_ in A]
        for i in range(3):
            M[i][k] = B[i]
        sol.append(det(M) / D)
    cx, cy = sol[0] / 2, sol[1] / 2
    r2 = sol[2] + cx * cx + cy * cy
    return (cx, cy, math.sqrt(r2)) if r2 > 0 else None


def _sarim(t, n_iz=25):
    """Sarımın halka bölgesi: sık ızgarada düzenli tekrar gösteren
    ışınlar. Bacak / halka / kanca ışında tek uzun kesişim verir, tekrar
    göstermez: kendiliğinden elenir. Noktalara çember oturtulur.
    Döner: dict(cx, cy, r_ic, r_dis, r_orta, za, zb, adim, kal, sayi) ya da None."""
    b = t.kutu()
    z0, z1 = b[2] - 1.0, b[5] + 1.0
    nok = []
    for i in range(n_iz):
        for j in range(n_iz):
            x = b[0] + (b[3] - b[0]) * (i + 0.5) / n_iz
            y = b[1] + (b[4] - b[1]) * (j + 0.5) / n_iz
            r = _tekrar(_isin(t, x, y, z0, z1))
            if r:
                nok.append((x, y, r))
    if len(nok) < 6:
        return None
    nmax = max(r[2] for _x, _y, r in nok)
    nok = [(x, y, r) for x, y, r in nok if r[2] >= max(3, 0.6 * nmax)]
    if len(nok) < 6:
        return None
    c = _cember([(x, y) for x, y, _r in nok])
    if not c:
        return None
    cx, cy, _rc = c
    n = len(nok)
    ds = sorted(math.hypot(x - cx, y - cy) for x, y, _r in nok)
    kal = sorted(r[0] for _x, _y, r in nok)[n // 2]
    adim = sorted(r[1] for _x, _y, r in nok)[n // 2]
    za = min(r[3] for _x, _y, r in nok)
    zb = max(r[3] + (r[2] - 1) * r[1] + r[0] for _x, _y, r in nok)
    return dict(cx=cx, cy=cy, r_ic=ds[0], r_dis=ds[-1], r_orta=ds[n // 2], za=za, zb=zb,
                adim=adim, kal=kal, sayi=nmax, n=n)


def _ekseni_duzelt(t, s):
    """Sarım ekseni: sarım TAM TURLUK dilimlere bölünür, her dilimde tele
    çember oturtulur; çember merkezleri eksen üzerindedir (eğik kesilen
    dilimde elipsin merkezi de). Merkezlerden geçen doğru eksendir. Asal
    atalet ekseni helisin ekseni değildir: kısa sarımda (boy ~ çap)
    belirsizdir, bacak / halka da onu eğer. Bacak yarıçap penceresinin
    dışında kalır. Döner: (eksene taşınmış t, eski kotlardaki yeni orijin)."""
    import numpy as np
    za, zb, adim = s["za"], s["zb"], s["adim"]
    t0 = t.tasi((s["cx"], s["cy"], 0.0), (0.0, 0.0, 1.0))
    r1, r2 = 0.5 * s["r_ic"], s["r_dis"] + 1.5 * s["kal"]
    rr = np.hypot(t0.merkez[:, 0], t0.merkez[:, 1])
    pencere = (rr >= r1) & (rr <= r2)
    mer = []
    z = za + adim
    while z + adim <= zb - adim + 1e-9:
        m = pencere & (t0.merkez[:, 2] >= z) & (t0.merkez[:, 2] <= z + adim)
        if m.sum() >= 12:
            c = _cember([(float(p[0]), float(p[1])) for p in t0.merkez[m]])
            if c:
                mer.append((c[0], c[1], z + adim / 2))
        z += adim
    if len(mer) < 2:
        return t0, 0.0
    Z = np.array([m_[2] for m_ in mer])
    X = np.array([m_[0] for m_ in mer])
    Y = np.array([m_[1] for m_ in mer])
    ax, bx = np.polyfit(Z, X, 1)
    ay, by = np.polyfit(Z, Y, 1)
    zo = float(Z.mean())
    d = np.array([ax, ay, 1.0])
    d /= np.linalg.norm(d)
    return (t0.tasi((float(ax * zo + bx), float(ay * zo + by), zo), tuple(float(v) for v in d)),
            zo)


def _dilim_spir(t, za, zb, adim, Do, r_en=None):
    """Eksene dik ince dilimlerde yüzeyin ağırlık merkezinin açısı: helisse
    kotla doğrusal döner, adım başına 360°. Döner: "sağ" / "sol" / None.
    Bütün boy taranır, en uzun tutarlı dizi (en az iki tur) aranır: uçtaki
    kapak / bacak diziyi kesebilir. Sık sarımda (adım ~ tel) dilim bütün
    çevreyi kapsar, açı anlamsızdır: orada ışın fazı ölçüsü geçerlidir."""
    kb = t.kutu(r_en=r_en)
    h = adim / 8
    n = min(int((kb[5] - kb[2]) / h), 400)
    if n < 16:
        return None
    nok = []
    for i in range(n):
        z = kb[2] + (i + 0.5) * h
        m = t.agirlik(z - h / 2, z + h / 2, r_en)
        nok.append(None if m is None or math.hypot(m[0], m[1]) < 0.2 * Do / 2
                   else math.atan2(m[1], m[0]))
    en = (0, 0)
    for yon in (1, -1):
        i = 0
        while i < n:
            j = i
            while (j + 1 < n and nok[j] is not None and nok[j + 1] is not None
                   and abs(((nok[j + 1] - nok[j] + math.pi) % (2 * math.pi) - math.pi)
                           - yon * math.pi / 4) < math.pi / 8):
                j += 1
            if j - i > abs(en[0]):
                en = (yon * (j - i), i)
            i = j + 1
    if abs(en[0]) < 16:                     # iki turdan az
        return None
    return "sağ" if en[0] > 0 else "sol"


def _yaricap_tara(it, R, z0, z1):
    """Eksenden (0, 0), 0 ve 45° yönlerinde 0..R yarıçaplarda eksene
    paralel ışınlar: en çok (eşitse en kalın) tekrar gösteren (sonuç, r, a).
    R bacak / halka dahil gabaridir; adım sık tutulur ki ince sarım
    kaçmasın."""
    en = None
    for a in (0.0, math.pi / 4):
        for k in range(1, 49):
            r = R * k / 48
            rr = _tekrar(_isin(it, r * math.cos(a), r * math.sin(a), z0, z1))
            if rr and (en is None or (rr[2], rr[0]) > (en[0][2], en[0][0])):
                en = (rr, r, a)
    return en


def _duzlem_payi(sh):
    """Yüzey alanının düzlem yüzlerdeki payı (0..1)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    top = duz = 0.0
    ex = TopExp_Explorer(sh, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face_s(ex.Current())
        ex.Next()
        g = GProp_GProps()
        BRepGProp.SurfaceProperties_s(f, g)
        top += g.Mass()
        if BRepAdaptor_Surface(f).GetType() == GeomAbs_Plane:
            duz += g.Mass()
    return duz / top if top > 0 else 1.0


def yay_olabilir(sh, V=None):
    """Hızlı ön süzgeç (ağ ölçülmeden): gabari doluluğu düşük ve yüzeyi
    çoğunlukla düzlem DEĞİL (helis, tor). Sac / lama / kutu burada elenir."""
    try:
        if V is None:
            from OCP.BRepGProp import BRepGProp
            from OCP.GProp import GProp_GProps
            g = GProp_GProps()
            BRepGProp.VolumeProperties_s(sh, g)
            V = g.Mass()
        kb = _kutu(sh)
        olc = sorted((kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]))
        if V <= 0 or olc[0] <= 0 or V / (olc[0] * olc[1] * olc[2]) > YAY_DOLU:
            return False
        return _duzlem_payi(sh) <= YAY_DUZLEM
    except Exception:
        return False


def yay(sh, V=None):
    """(sinif, tip, gerekce, kesin) ya da None. kesin=False: yalnız aday
    (katmanlı yay: disk / yaprak paketi, spiral yay)."""
    try:
        if not yay_olabilir(sh, V):
            return None
        return _yay(sh, V)
    except Exception:
        return None


def _yay(sh, V):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(sh, g)
    if V is None:
        V = g.Mass()
    kb = _kutu(sh)
    olc = sorted((kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]))
    if V <= 0 or olc[0] <= 0 or V / (olc[0] * olc[1] * olc[2]) > YAY_DOLU:
        return None                         # içi dolu: yay değil
    p = g.PrincipalProperties()
    c = g.CentreOfMass()
    en = None
    ag = _Ag(sh)
    if len(ag.u) == 0:
        return None
    for eks in (p.FirstAxisOfInertia(), p.SecondAxisOfInertia(), p.ThirdAxisOfInertia()):
        t = ag.tasi((c.X(), c.Y(), c.Z()), (eks.X(), eks.Y(), eks.Z()))
        b = t.kutu()
        e = _tara(t, b)
        if e and (en is None or e[0][2] > en[0][0][2]):
            en = (e, t, b)
    if not en:
        return None
    e, t, b = en
    (kal, adim, sayi, _ilk), _xy, q = e
    Dn = max(b[3] - b[0], b[4] - b[1])
    katman = ("standart", "katmanlı yay (disk / yaprak yay paketi, spiral yay)",
              f"yapı: {XL.tr(kal, 1)} kalınlıkta katman {sayi} kez düzenli tekrar "
              f"(adım {XL.tr(adim, 1)}), ölçü {XL.tr(Dn, 1)} x {XL.tr(b[5] - b[2], 1)}",
              False)
    if kal > 0.25 * (q[-1] - q[0] + kal):
        return None
    if sayi < YAY_KATMAN or adim > 4 * kal:
        # az katman (perçin, burç) ya da katmanlar birbirinden uzak (oluklu /
        # delikli sac): katmanlı yay adayı bile değil
        katman = None
    # --- sarım ekseni: önce ışınlarla halka bölgesi ve merkezi (bacak
    # elenir), sonra tam tur dilimlerinin ağırlık merkezleriyle eğim.
    # Asal eksen ve iki düzeltme turu aday çerçevedir; en çok sarım
    # tekrarı gören çerçeve seçilir.
    cerceve = []
    onceki = None
    for _tur in range(3):
        sr = _sarim(t)
        if sr:
            # eşit tekrarda düzeltilmiş (sonraki) çerçeve yeğlenir
            cerceve.append(((sr["sayi"], _tur, sr["n"]), t, sr))
        elif onceki:
            # eksen doğruyken konik yayda eksene paralel ışın her turu
            # başka çapta keser, tekrar görünmez: çerçeve yine adaydır
            # (dilim spir ölçüsü için), ölçüler önceki çerçeveden
            sr = dict(onceki, cx=0.0, cy=0.0)
            cerceve.append(((-1, _tur, 0), t, sr))
        else:
            break
        if sr["zb"] - sr["za"] < 3 * sr["adim"]:
            break
        t, zo = _ekseni_duzelt(t, sr)
        onceki = dict(sr, za=sr["za"] - zo, zb=sr["zb"] - zo)
    if not cerceve:
        return katman
    # en iyi tekrarın %80'ine yetişen EN SON düzeltilmiş çerçeve: eğik
    # çerçevede ışın uçta bir tur fazla sayabilir, sayı tek ölçü değil
    en_cok = max(c_[0][0] for c_ in cerceve)
    cerceve.sort(key=lambda c_: (c_[0][0] >= 0.8 * en_cok, c_[0][1], c_[0][2]), reverse=True)
    _k, t, sr = cerceve[0]
    # eksen orijine: sarım ölçüleri bundan sonra eksene göre
    t = t.tasi((sr["cx"], sr["cy"], 0.0), (0.0, 0.0, 1.0))
    za, zb, adim, kal = sr["za"], sr["zb"], sr["adim"], sr["kal"]
    r_en = sr["r_dis"] + 0.75 * kal          # sarım silindiri (bacak dışarıda)
    b = t.kutu()
    ob = t.kutu(za + adim, zb - adim, r_en) if zb - za > 3 * adim else t.kutu(r_en=r_en)
    if ob is None:
        return katman
    Do = 2 * max(-ob[0], ob[3], -ob[1], ob[4])
    it = t
    yuvarlak = abs((ob[3] - ob[0]) - (ob[4] - ob[1])) <= 0.15 * Do
    # ortası boş mu: uçlardan ~2 adım içeride (çekme yayının halkası sarım
    # ucunda ekseni keser)
    pay = 2 * adim + kal
    bos = not _isin(it, 0.0, 0.0, za + pay, zb - pay) if zb - za > 2 * pay + adim else True
    if not (yuvarlak and bos and Do > 3 * kal):
        return katman
    # --- spir denetimi 1: aynı yarıçapta 0, 90, 180, 270° ışınları; helisin
    # tel kesiti her 90°'de ÇEYREK ADIM kayar
    yon = None
    faz = []
    r0 = sr["r_orta"]
    ilk = None
    for k in range(4):
        a = k * math.pi / 2
        rr = _tekrar(_isin(it, r0 * math.cos(a), r0 * math.sin(a), za - adim, zb + adim), 2)
        if not rr or abs(rr[1] - adim) > 0.25 * adim:
            faz = []
            break
        ilk = rr[3] if ilk is None else ilk
        faz.append(((rr[3] - ilk) / adim) % 1.0)

    def yakin(f, h):
        return min(abs(f - h), 1 - abs(f - h)) <= 0.12
    if faz:
        if yakin(faz[2], 0.5) and yakin(faz[1], 0.25) and yakin(faz[3], 0.75):
            yon = "sağ"
        elif yakin(faz[2], 0.5) and yakin(faz[1], 0.75) and yakin(faz[3], 0.25):
            yon = "sol"
        elif all(yakin(f, 0.0) for f in faz):
            return katman                   # dönmeden aynı: disk yay paketi
    olcum = "tel kesiti her 90°'de çeyrek adım kayıyor"
    if yon is None:
        # --- spir denetimi 2: ince dilimlerde telin açısı kotla düzgün
        # döner, her adımda bir tur (konik yayda da geçerli); her aday
        # çerçevede denenir
        olcum = "tel açısı kotla düzgün dönüyor, adım başına bir tur"
        for _k, t2, s2 in cerceve:
            t2 = t2.tasi((s2["cx"], s2["cy"], 0.0), (0.0, 0.0, 1.0))
            yon = _dilim_spir(t2, s2["za"], s2["zb"], s2["adim"],
                              2 * s2["r_dis"] + s2["kal"])
            if yon:
                t, sr = t2, s2
                za, zb, adim, kal = sr["za"], sr["zb"], sr["adim"], sr["kal"]
                b = t.kutu()
                r_en = sr["r_dis"] + 0.75 * kal
                ob = (t.kutu(za + adim, zb - adim, r_en) if zb - za > 3 * adim
                      else t.kutu(r_en=r_en))
                Do = 2 * max(-ob[0], ob[3], -ob[1], ob[4]) if ob else Do
                break
    if yon is None:
        return None if faz else katman
    # --- uçlar: sarım dışına taşan malzeme
    eksen_tasma = max(za - b[2], b[5] - zb)
    yan_tasma = max(-b[0], b[3], -b[1], b[4]) - Do / 2
    olcu = (f"tel ~Ø{XL.tr(kal, 1)}, dış Ø{XL.tr(Do, 1)}, adım {XL.tr(adim, 1)}, "
            f"~{(zb - za) / adim:.0f} sarım, {yon} helis")
    if yan_tasma > 0.3 * Do:
        tip = "burulma yayı (bacaklı)"
        uc = f"uçlar yana {XL.tr(yan_tasma, 1)} taşıyor (bacak)"
    elif eksen_tasma > 0.3 * Do:
        tip = "çekme yayı (halkalı / kancalı)"
        uc = f"uçlar eksen boyunca {XL.tr(eksen_tasma, 1)} taşıyor (halka / kanca)"
    else:
        ka = t.kutu(za - kal, za + 1.5 * adim)
        ku = t.kutu(zb - 1.5 * adim, zb + kal)
        da = db = Do
        if ka and ku:
            da = 2 * max(-ka[0], ka[3], -ka[1], ka[4])
            db = 2 * max(-ku[0], ku[3], -ku[1], ku[4])
        if abs(da - db) > 0.2 * max(da, db):
            tip = "konik basma yayı"
            uc = f"uç çapları Ø{XL.tr(da, 1)} / Ø{XL.tr(db, 1)}"
        elif adim > 1.25 * kal:
            tip = "basma yayı"
            uc = "uçsuz, açık sarım"
        else:
            tip = "helis yay (sık sarım, uçsuz)"
            uc = "uçsuz, sık sarım"
    return ("standart", tip, f"yapı: spir ({olcum}); {olcu}; {uc}", True)
