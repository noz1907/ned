# -*- coding: utf-8 -*-
"""STANDART PARÇA AİLELERİ: segman, yaylı pim, kama, konik pim, gres nipeli.

Cıvata / somun / pul / rulman / yay dışında kalan, makine imalatında sık
satın alınan küçük standart parçalar. Her aile YAPISINDAN tanınır, adı
olmasa da:

  segman (DIN 471 mil, DIN 472 delik)
      DÜZ parça (kalınlık s, çapın en çok %12'si), kesiti AÇIK HALKA
      (merkez boş, malzeme çevrede, bir yerde boşluk), boşluğun iki
      yanında iki küçük DELİK (kulak). Delikler halkanın dışındaysa mil
      segmanı, içindeyse delik segmanı.
  E-segman (DIN 6799)
      düz, açık halka, DELİKSİZ, ağzı geniş (60 - 150°), küçük (en çok
      Ø50) ve kalınlığı standart seride; Ø60'a kadar yalnız aday (C
      biçimli lazer kesim sac da olabilir), daha büyüğü hiç sayılmaz.
  yaylı (yarıklı) pim (ISO 8752 ağır / ISO 13337 hafif)
      ince cidarlı TÜP, boydan boya YARIK: tüpün orta kesiti açık halka,
      et kalınlığı çapın %7 - 30'u, yarık 3 - 60°.
  paralel kama (DIN 6885 A)
      iki eş YARIM SİLİNDİR uç (R = b/2) + düz yanlar; b x h çifti DIN 6885
      tablosuna tam oturur. B tipi (düz uçlu kutu) lama ile aynı biçimdir:
      yalnız ADAY ("kama olabilir").
  konik pim (ISO 2339 / DIN 1)
      baskın KONİ yüzü, koniklik 1:50 (yarım açı 0,573°).
  gres nipeli (DIN 71412 A)
      KÜRE baş + ALTIKÖŞE (anahtar ağzı 7 / 9 / 11) + eksenel ince delik,
      toplam boy en çok 30 mm.

Sayılar DIN / ISO tablolarından. Belirsizlikte KARAR YOK (yalnız aday):
yanlış "standart" demek, "bilmiyorum" demekten pahalıdır.
"""
from __future__ import annotations

import math

import pf8_tani as TN
import pf9_excel as XL

# DIN 6885 A/B paralel kama: (b, h) çiftleri
KAMA_BH = ((2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (8, 7), (10, 8), (12, 8), (14, 9),
           (16, 10), (18, 11), (20, 12), (22, 14), (25, 14), (28, 16), (32, 18),
           (36, 20), (40, 22), (45, 25), (50, 28))
# segman kalınlık serisi (DIN 471 / 472 / 6799)
SEGMAN_S = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.75, 2.0,
            2.5, 3.0, 3.5, 4.0)
# gres nipeli anahtar ağzı (DIN 71412): M6 -> 7, M8x1 -> 9, M10x1 / R1/8 -> 11
NIPEL_SW = (7.0, 9.0, 11.0)
KONIK_PIM_ACI = math.degrees(math.atan(1 / 100.0))   # 1:50 çapta -> 0,573°
# ISO 8735 / DIN 7979 çekmeli (iç dişli) silindirik pim: d -> iç diş M
CEKMELI_PIM_M = {6: 4, 8: 5, 10: 6, 12: 6, 16: 8, 20: 10}


def _m(v, n=1):
    return XL.tr(v, n)


def _delik(y):
    """Silindir yüzü içbükey mi (DELİK): normal yüzün KENDİ eksenine doğru.
    (TN._ice_bakar ekseni Z'de, orijinde varsayar: dünya çerçevesinde
    döndürülmüş parçada yanılır.)"""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp_Face
    from OCP.gp import gp_Pnt, gp_Vec
    s = BRepAdaptor_Surface(y["f"])
    u = 0.5 * (s.FirstUParameter() + s.LastUParameter())
    v = 0.5 * (s.FirstVParameter() + s.LastVParameter())
    p, n = gp_Pnt(), gp_Vec()
    BRepGProp_Face(y["f"]).Normal(u, v, p, n)
    w = TN._fark((p.X(), p.Y(), p.Z()), y["o"])
    k = TN._nokta(w, y["d"])
    radyal = tuple(w[i] - k * y["d"][i] for i in range(3))
    return TN._nokta(radyal, (n.X(), n.Y(), n.Z())) < 0


def aile_tani(sh, yz=None):
    """(sinif, tip, gerekce, kesin) ya da None. Sıra: segman, yaylı pim,
    kama, konik pim, gres nipeli."""
    try:
        yz = yz if yz is not None else TN._yuzler(sh)
        if not yz:
            return None
        for f in (segman, yayli_pim, kama, konik_pim, gres_nipeli):
            try:
                r = f(sh, yz)
            except Exception:
                r = None
            if r:
                return r
    except Exception:
        return None
    return None


# ------------------------------------------------------------ açık halka
def _malzeme(loops, q):
    """q noktası malzemede mi (kesit tellerinin derinlik çiftliği)."""
    n = 0
    for p, _a, _d, _w in loops:
        if TN._icinde(q, p):
            n += 1
    return n % 2 == 1


def _acik_halka(loops, R):
    """Kesit (tel listesi, merkez orijinde değil) açık halka mı. R: kaba
    dış yarıçap. Döner: dict(cx, cy, kapsam, bosluk, bosluk_orta, rin, rout,
    et, delikler=[(x, y, r)]) ya da None."""
    from pf11_yapi import _cember
    if not loops:
        return None
    dis = max(loops, key=lambda t: t[1])
    c = _cember(dis[0])
    if not c:
        return None
    cx, cy, _r = c
    if _malzeme(loops, (cx, cy)):
        return None                         # merkez dolu: halka değil
    N, M = 180, 28
    ort = []

    def sinir(r0, r1, ic_mi):
        # malzeme sınırı: r0 ve r1 arasında ikiye bölme (6 adım)
        for _ in range(6):
            rm_ = 0.5 * (r0 + r1)
            if _malzeme(loops, (cx + rm_ * ca, cy + rm_ * sa)) == ic_mi:
                r1 = rm_
            else:
                r0 = rm_
        return 0.5 * (r0 + r1)
    adim = 1.6 * R / M
    for i in range(N):
        a = 2 * math.pi * i / N
        ca, sa = math.cos(a), math.sin(a)
        ic = dis_ = None
        for k in range(1, M + 1):
            r = adim * k
            if _malzeme(loops, (cx + r * ca, cy + r * sa)):
                ic = r if ic is None else ic
                dis_ = r
            elif ic is not None:
                break
        if ic is not None:
            ic = sinir(ic - adim, ic, True)
            dis_ = sinir(dis_ + adim, dis_, True)
        ort.append((ic, dis_))
    dolu = [o[0] is not None for o in ort]
    kapsam = 360.0 * sum(dolu) / N
    # en uzun boşluk (çembersel)
    en = bas = 0
    for i in range(N):
        if not dolu[i]:
            j = 0
            while j < N and not dolu[(i + j) % N]:
                j += 1
            if j > en:
                en, bas = j, i
    bosluk = 360.0 * en / N
    orta = 360.0 * (bas + en / 2) / N % 360.0
    # boşluğun ±45° yakını (kulaklar) dışındaki iç / dış sınırlar
    uzak = [o for i, o in enumerate(ort) if o[0] is not None and
            abs(((360.0 * i / N - orta + 180.0) % 360.0) - 180.0) > bosluk / 2 + 45]
    if not uzak:
        return None
    ets = sorted(o[1] - o[0] for o in uzak)
    rins = sorted(o[0] for o in uzak)
    routs = sorted(o[1] for o in uzak)
    delik = []
    for p, a, d, _w in loops:
        if d % 2 == 1 and not TN._icinde((cx, cy), p):
            P = TN._cevre(p)
            if P > 0 and 4 * math.pi * a / (P * P) > 0.85 and a < math.pi * (0.35 * R) ** 2:
                x = sum(t[0] for t in p) / len(p)
                y = sum(t[1] for t in p) / len(p)
                delik.append((x, y, math.sqrt(a / math.pi)))
    tum = [o[1] for o in ort if o[1] is not None]
    return dict(cx=cx, cy=cy, kapsam=kapsam, bosluk=bosluk, bosluk_orta=orta,
                rin=rins[len(rins) // 2], rout=routs[len(routs) // 2],
                rin_yay=rins[-1] - rins[0], rout_yay=routs[-1] - routs[0],
                rout_min=routs[0], rout_max=max(tum), et=ets[len(ets) // 2], delikler=delik)


def _eksen_kesiti(sh, o, d, oran=0.5):
    """Katıyı (o, d) eksenine taşır; boyunun `oran` kotundaki kesit."""
    t = TN._eksene_tasi(sh, o, d)
    kb = TN._kutu(t)
    z = kb[2] + oran * (kb[5] - kb[2])
    loops, _net, _bolge = TN._kesit(t, z)
    return t, kb, loops


# ------------------------------------------------------------ segman
def _duz(yz):
    """Parça düz levha mı: en büyük düzlem yüzün normali n, kalınlık s
    (karşı düzleme uzaklık). Döner (n, p, s) ya da None."""
    duz = [y for y in yz if y["tip"] == "duz"]
    if len(duz) < 2:
        return None
    a = max(duz, key=lambda y: y["alan"])
    n = a["n"]
    s = None
    for y in duz:
        if y is a or not TN._paralel(y["n"], n):
            continue
        k = abs(TN._nokta(TN._fark(y["p"], a["p"]), n))
        if k > 1e-6 and y["alan"] > 0.6 * a["alan"]:
            s = k if s is None else min(s, k)
    if s is None:
        return None
    # geri kalan yüzler n'e paralel eksenli / dik normalli (kalıp kesim yanaklar)
    yan = sum(y["alan"] for y in yz
              if (y["tip"] == "duz" and (TN._paralel(y["n"], n) or TN._dik(y["n"], n)))
              or (y["tip"] == "silindir" and TN._paralel(y["d"], n)))
    if yan < 0.9 * sum(y["alan"] for y in yz):
        return None
    return n, a["p"], s


def segman(sh, yz):
    d = _duz(yz)
    if not d:
        return None
    n, p, s = d
    kb = TN._kutu(sh)
    D = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2])
    if s > 0.12 * D or D > 400:
        return None
    t, tk, loops = _eksen_kesiti(sh, p, n)
    R = 0.5 * max(tk[3] - tk[0], tk[4] - tk[1])
    h = _acik_halka(loops, R)
    if not h or h["kapsam"] < 180 or h["bosluk"] < 3:
        return None
    seride = any(abs(s - v) <= 0.03 for v in SEGMAN_S)
    del_ = h["delikler"]
    if len(del_) == 2:
        # iki delik boşluğa simetrik: açıları boşluğun iki yanında
        acilar = []
        for x, y, _r in del_:
            a = math.degrees(math.atan2(y - h["cy"], x - h["cx"])) % 360.0
            acilar.append(((a - h["bosluk_orta"] + 180.0) % 360.0) - 180.0)
        if acilar[0] * acilar[1] >= 0 or abs(abs(acilar[0]) - abs(acilar[1])) > 12:
            return None
        # mil / delik: eş merkezli (sabit yarıçaplı) kenar milde İÇ, delikte
        # DIŞ kenardır (öbür kenar eksantrik: halka boşluğa doğru incelir).
        # Kenar belirsizse kulak deliklerinin yeri (milde halkanın dış
        # yarısı, delikte iç yarısı); delik halkanın yanlış tarafındaysa karar yok
        rd = [math.hypot(x - h["cx"], y - h["cy"]) for x, y, _r in del_]
        rm = 0.5 * (h["rin"] + h["rout"])
        if h["rin_yay"] < 0.5 * h["rout_yay"]:
            kenar = "mil"
        elif h["rout_yay"] < 0.5 * h["rin_yay"]:
            kenar = "delik"
        else:
            kenar = None
        if kenar is None:
            kenar = "mil" if min(rd) > rm else "delik" if max(rd) < rm else None
        # açık çelişki: kulak deliği halkanın yanlış tarafında
        if kenar is None or (kenar == "mil" and max(rd) < h["rin"]) or \
                (kenar == "delik" and min(rd) > h["rout"]):
            return None
        if kenar == "mil":
            tip, dis_ic = "mil segmanı (DIN 471)", f"iç Ø{_m(2 * h['rin'])}"
        else:
            tip, dis_ic = "delik segmanı (DIN 472)", f"dış Ø{_m(2 * h['rout'])}"
        return ("standart", tip,
                f"yapı: düz açık halka (s={_m(s, 2)}), boşluk {h['bosluk']:.0f}°, iki kulak "
                f"deliği Ø{_m(2 * del_[0][2])} boşluğa simetrik; {dis_ic}"
                + ("" if seride else "; kalınlık standart seride değil"), True)
    if not del_ and 60 <= h["bosluk"] <= 150 and D <= 60:
        kesin = seride and D <= 50 and s <= 3
        return ("standart", "E-segman (DIN 6799)",
                f"yapı: düz açık halka (s={_m(s, 2)}), deliksiz, ağız {h['bosluk']:.0f}°, "
                f"dış Ø{_m(2 * h['rout_max'])}"
                + ("" if kesin else " - büyük / seri dışı: C biçimli sac da olabilir"), kesin)
    return None


# ------------------------------------------------------------ yaylı pim
def yayli_pim(sh, yz):
    sil = [y for y in yz if y["tip"] == "silindir"]
    if not sil:
        return None
    a = max(sil, key=lambda y: y["alan"])
    t, tk, loops = _eksen_kesiti(sh, a["o"], a["d"])
    L = tk[5] - tk[2]
    D = max(tk[3] - tk[0], tk[4] - tk[1])
    if D > 50 or L < 1.5 * D:
        return None
    h = _acik_halka(loops, D / 2)
    if not h or h["kapsam"] < 270 or not (3 <= h["bosluk"] <= 60) or h["delikler"]:
        return None
    d = 2 * h["rout"]
    s = h["rout"] - h["rin"]
    if not (0.07 * d <= s <= 0.3 * d) or h["rout_max"] - h["rout_min"] > 0.08 * d:
        return None
    # uçlar pahlı (dış): eksene paralel koni yüzleri
    pah = sum(1 for y in yz if y["tip"] == "koni" and TN._paralel(y["d"], a["d"]))
    tip = ("yaylı pim (ISO 8752 / DIN 1481, ağır tip)" if s >= 0.15 * d
           else "yaylı pim (ISO 13337 / DIN 7346, hafif tip)")
    return ("standart", tip,
            f"yapı: ince cidarlı tüp, boydan boya yarık ({h['bosluk']:.0f}°); Ø{_m(d)} x "
            f"{_m(L)}, et {_m(s, 2)}" + (", uçları pahlı" if pah >= 2 else ""), True)


# ------------------------------------------------------------ kama
def _kama_bh(b, h):
    for bb, hh in KAMA_BH:
        if abs(b - bb) <= 0.05 + 0.01 * bb and abs(h - hh) <= 0.05 + 0.01 * hh:
            return bb, hh
    return None


def kama(sh, yz):
    top = sum(y["alan"] for y in yz)
    sil = [y for y in yz if y["tip"] == "silindir" and not _delik(y)]
    kb = TN._kutu(sh)
    # silindir yüzleri eksenine göre gruplanır (birleştirme yüzü bölebilir)
    grup = []
    for y in sil:
        for g in grup:
            if TN._paralel(g["d"], y["d"]) and abs(g["r"] - y["r"]) < 1e-3 and \
                    TN._eksene_uzak(y["o"], g["o"], g["d"]) < 1e-3:
                break
        else:
            grup.append(y)
    if len(grup) == 2 and abs(grup[0]["r"] - grup[1]["r"]) < 1e-3 and \
            TN._paralel(grup[0]["d"], grup[1]["d"]):
        # A tipi: iki eş yarım silindir uç
        R, dz = grup[0]["r"], grup[0]["d"]
        ara = TN._eksene_uzak(grup[1]["o"], grup[0]["o"], dz)
        duz = [y for y in yz if y["tip"] == "duz"]
        ust = [y for y in duz if TN._paralel(y["n"], dz)]
        if len(ust) < 2 or ara <= 0:
            return None
        h = max(abs(TN._nokta(TN._fark(u["p"], ust[0]["p"]), dz)) for u in ust)
        pay = (sum(y["alan"] for y in sil) + sum(y["alan"] for y in duz)) / top
        bh = _kama_bh(2 * R, h)
        if bh and pay > 0.97:
            L = ara + 2 * R
            return ("standart", "paralel kama (DIN 6885 A)",
                    f"yapı: iki eş yarım silindir uç (R {_m(R, 2)}) + düz yanlar; "
                    f"b x h x L = {bh[0]} x {bh[1]} x {_m(L)} (DIN 6885 tablosunda)", True)
        return None
    # B tipi: düz kutu - lama ile aynı biçim: yalnız aday
    if all(y["tip"] == "duz" for y in yz) and len(yz) == 6:
        o = sorted((kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2]))
        bh = _kama_bh(o[1], o[0])
        if bh and o[2] >= 1.5 * o[1] and o[2] <= 20 * o[1]:
            return ("standart", "paralel kama (DIN 6885 B)",
                    f"yapı: düz uçlu kutu, b x h = {bh[0]} x {bh[1]} DIN 6885 tablosunda; "
                    f"L {_m(o[2])} - lama da olabilir", False)
    return None


# ------------------------------------------------------------ konik pim
def konik_pim(sh, yz):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    top = sum(y["alan"] for y in yz)
    kon = [y for y in yz if y["tip"] == "koni"]
    if not kon:
        return None
    a = max(kon, key=lambda y: y["alan"])
    if a["alan"] < 0.7 * top:
        return None
    aci = abs(math.degrees(BRepAdaptor_Surface(a["f"]).Cone().SemiAngle()))
    if abs(aci - KONIK_PIM_ACI) > 0.08:
        return None
    t = TN._eksene_tasi(sh, a["o"], a["d"])
    kb = TN._kutu(t)
    L = kb[5] - kb[2]
    D = max(kb[3] - kb[0], kb[4] - kb[1])
    if D > 50 or L < 2 * D:
        return None
    d = D - L / 50.0                       # küçük uç çapı
    return ("standart", "konik pim (ISO 2339 / DIN 1)",
            f"yapı: koni yüzü, koniklik 1:50 (yarım açı {aci:.3f}°); küçük uç Ø{_m(d)} x "
            f"{_m(L)}".replace(".", ","), True)


# ------------------------------------------------------------ gres nipeli
def gres_nipeli(sh, yz):
    kb = TN._kutu(sh)
    B = max(kb[3] - kb[0], kb[4] - kb[1], kb[5] - kb[2])
    if B > 30:
        return None
    kure = [y for y in yz if y["tip"] == "kure" and 1.8 <= y["r"] <= 4.5]
    e = TN._ana_eksen(yz)
    if not kure or not e:
        return None
    o, d = e
    if min(TN._eksene_uzak(k["c"], o, d) for k in kure) > 0.1:
        return None
    # altıköşe: eksene paralel düzlem yüzler; karşılıklı çiftlerin aralığı
    yan = [y for y in yz if y["tip"] == "duz" and TN._dik(y["n"], d)]
    if len(yan) < 6:
        return None
    ara = []
    for i, u in enumerate(yan):
        for v in yan[i + 1:]:
            if TN._paralel(u["n"], v["n"]):
                ara.append(abs(TN._nokta(TN._fark(v["p"], u["p"]), u["n"])))
    sw = [s for s in NIPEL_SW if sum(1 for a in ara if abs(a - s) <= 0.2) >= 3]
    if not sw:
        return None
    delik = [y for y in yz if y["tip"] == "silindir" and _delik(y) and y["r"] <= 1.8
             and TN._paralel(y["d"], d) and TN._eksene_uzak(y["o"], o, d) < 0.1]
    if not delik:
        return None
    return ("standart", "gres nipeli (DIN 71412 A)",
            f"yapı: küre baş Ø{_m(2 * kure[0]['r'])} + altıköşe SW{sw[0]:g} + eksenel "
            f"yağ deliği Ø{_m(2 * delik[0]['r'])}; boy {_m(B)}", True)


# ------------------------------------------------------------ pim tipi
def pim_tipi(sh, yz=None):
    """"pim" kararı verilmiş dolu silindirin TİPİ: bir ucunda eş eksenli
    KÖR delik varsa çekmeli (iç dişli) pim (ISO 8735 / DIN 7979; delik
    çapı dişin çekirdek ya da anma çapı), yoksa silindirik pim (ISO 2338
    / 8734 - merkezleme pimi). Döner (tip, gerekce) ya da None."""
    yz = yz if yz is not None else TN._yuzler(sh)
    sil = [y for y in yz if y["tip"] == "silindir"]
    dis = [y for y in sil if not _delik(y)]
    if not dis:
        return None
    a = max(dis, key=lambda y: y["alan"])
    d = 2 * a["r"]
    t = TN._eksene_tasi(sh, a["o"], a["d"])
    kb = TN._kutu(t)
    L = kb[5] - kb[2]
    delik = [y for y in sil if _delik(y) and TN._paralel(y["d"], a["d"])
             and TN._eksene_uzak(y["o"], a["o"], a["d"]) < 0.05]
    if not delik:
        return ("silindirik pim (ISO 2338 / 8734)",
                f"dolu silindir Ø{_m(d, 2)} x {_m(L)}, deliksiz")
    h = min(delik, key=lambda y: y["r"])
    # kör mü: delik yüzeyinin eksen boyunca uzunluğu boydan kısa
    derin = TN._kutu(TN._eksene_tasi(h["f"], a["o"], a["d"]))
    dz = derin[5] - derin[2]
    if dz >= 0.9 * L:
        return None                         # boydan boya delik: burç / boru
    dn = min(CEKMELI_PIM_M, key=lambda k: abs(k - d))
    M = CEKMELI_PIM_M[dn]
    dh = 2 * h["r"]
    if abs(d - dn) <= 0.05 and 0.75 * M <= dh <= 1.02 * M:
        return ("çekmeli (iç dişli) pim (ISO 8735 / DIN 7979)",
                f"dolu silindir Ø{_m(d, 2)} x {_m(L)}, bir ucunda iç diş M{M} "
                f"(kör delik Ø{_m(dh, 2)} x {_m(dz)})")
    return None
