# -*- coding: utf-8 -*-
"""ÖRNEK: Pi3D tanıtım sunumu (kendi ürününüz için SLAYT listesini, ADIMLAR'ı ve
metinleri değiştirin; yapı aynı kalır).

Pi3D tanıtım sunumu: tek zaman çizelgesi -> HTML (canlı oynatma +
kare kare video kaydı). Slayt içerikleri SLAYT listesindedir; PowerPoint
de aynı listeden üretilir (pptx_uret.js, slaytlar.json)."""
import json, os, html
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
G = os.path.join(OUT, "g")


def boy(ad):
    return Image.open(os.path.join(G, ad)).size


# ---- ÜRÜNE GÖRE DEĞİŞTİRİLECEKLER ----------------------------------------
URUN = "Pi3D"                                   # ürün adı (bantta ve kapakta)
KAPAK = ["3D Modelden", "DXF, BOM, Açınım,", "PDF, Lazer Kesim."]   # 3 satır başlık
SLOGAN = "Analiz Ölçüm İşinizi Hızlandırır."    # sarı vurgu satırı
KAPANIS = ["Modeli verin.", "Resmi, açınımı, paftayı,", "lazeri Pi3D çıkarsın."]
KAPANIS_LISTE = "STEP · BOM · Detay resmi · Açınım · Pafta · PDF · Lazer"
# g/urun.png: ürün logosu (kare)   g/pivision.png: PiVision logosu (saydam)
# g/pivision_fon.png: filigran (≈2000 px)   diğerleri: ekran görüntüleri
# ---------------------------------------------------------------------------
ADIMLAR = ["VERİ", "BOM", "GÖRÜNÜŞ", "ÖRNEK", "ÇİZİMLER", "AÇINIM", "PAFTA", "LAZER"]

# vurgu: (x0, y0, x1, y1) görüntü pikseli; etiket: kutunun yanında yazı
SLAYT = [
    {"tip": "kapak", "sure": 8000},
    {"tip": "rakam", "sure": 10000,
     "ust": "GERÇEK BİR MONTAJ · KAYNAKLI KASA",
     "baslik": "Bir montaj. 23 dakika 40 saniye.",
     "alt": "1486 katı · 197 komponent · 145 kaynak dikişi ayrıldı",
     "rakamlar": [(159, "detay resmi", "DXF, ölçülü"), (106, "açınım", "kesim konturu"),
                  (245, "pafta", "A3, ölçekli"), (86, "lazer dosyası", "CAM'e hazır")],
     "not": "Elle resim başına yalnızca 15 dakika desek: 265 resim ≈ 66 saat."},
    {"tip": "adim", "adim": 1, "sure": 7500, "resim": "ekran_00.jpg", "yon": "sag",
     "baslik": "Modeli seçin, İNCELE deyin",
     "madde": ["STEP, IGES ve BREP okunur", "1486 katı 40 saniyede okundu; kopyalar birleşti",
               "Klasörde önceki çalışma varsa ne var, ne eksik yazar"],
     "sure_yazi": "Model okuma: 40 sn",
     "vurgu": [((686, 188, 934, 232), "tek tık")]},
    {"tip": "adim", "adim": 2, "sure": 8500, "resim": "ekran_01.jpg", "yon": "sol",
     "baslik": "Hiyerarşik BOM, malzeme ve kütle",
     "madde": ["Ana ürün ▸ alt montaj ▸ parça, kademe kademe",
               "Parça, standart eleman ve kaynak dikişini kendisi ayırır",
               "Kütle = hacim × yoğunluk; malzeme CAD'den alınabilir"],
     "sure_yazi": "BOM: 16 sn",
     "vurgu": [((531, 116, 649, 264), "sınıf"), ((13, 445, 714, 468), "145 dikiş parça sayılmadı")]},
    {"tip": "adim", "adim": 3, "sure": 7000, "resim": "ekran_02.jpg", "yon": "sag",
     "baslik": "Bir kez ayarlayın",
     "madde": ["En çok 4 görünüş, Avrupa yerleşimi", "İsterseniz A-A kesit ve gizli çizgi",
               "Ayarlar klasöre kaydedilir, bir daha girilmez"],
     "sure_yazi": "Ayar: bir kere",
     "vurgu": [((13, 128, 510, 240), "görünüşler"), ((512, 128, 790, 240), "kesit")]},
    {"tip": "adim", "adim": 4, "sure": 7500, "resim": "onizleme.jpg", "yon": "sol",
     "baslik": "Önce bir resim görün, sonra onaylayın",
     "madde": ["Yazılar gerçek boyutunda: çakışma varsa görürsünüz",
               "ÖN, SAĞ, SOL, ÜST ve ölçüleri", "ONAYLA: bütün çizimler üretilir"],
     "sure_yazi": "Örnek resim: saniyeler",
     "vurgu": [((260, 300, 1000, 440), "ölçülü görünüşler")]},
    {"tip": "adim", "adim": 5, "sure": 8500, "resim": "ekran_05.jpg", "yon": "sag",
     "baslik": "159 detay resmi, tek seferde",
     "madde": ["Her parçaya ölçülü DXF, 1:1", "Yalnız eksik ya da eskimiş olan üretilir",
               "Güncel çizime dokunmaz: ikinci tur 16 saniye"],
     "sure_yazi": "159 DXF: 9 dk 30 sn",
     "vurgu": [((13, 113, 428, 148), "159 DXF · 259,9 kg"), ((13, 410, 538, 434), "yalnız eksikler")]},
    {"tip": "adim", "adim": 5, "sure": 8000, "resim": "ekran_08.jpg", "yon": "sol",
     "baslik": "Ölçülü teknik resim",
     "madde": ["Ölçüler parçanın kendi XYZ çerçevesinden: datum A / B / C",
               "1992 konum ölçüsü 3D modelle doğrulandı: 0 hata",
               "Emin olmadığı ölçüyü resme yazmaz"],
     "sure_yazi": "Ölçer, tahmin etmez",
     "vurgu": [((425, 232, 800, 310), "datum A / C"), ((205, 215, 305, 330), "")]},
    {"tip": "adim", "adim": 6, "sure": 8500, "resim": "ekran_06.jpg", "yon": "sag",
     "baslik": "Bükümlü sacı kendisi bulur",
     "madde": ["113 bükümlü sac bulundu, hepsi seçili geldi",
               "Kesim konturu, büküm tablosu, K-faktörü",
               "Abkant mı rollform mu: sebebiyle söyler"],
     "sure_yazi": "106 açınım: 4 dk 21 sn",
     "vurgu": [((13, 414, 622, 435), "113 parça, kendiliğinden"), ((728, 158, 990, 396), "büküm sayısı")]},
    {"tip": "resim", "adim": 6, "sure": 7000, "resim": "acinim_resim.jpg",
     "baslik": "Açınım resmi: kesilecek sac",
     "alt": "Dış kontur, delikler ve kenar kesikleri gerçek yerinde; büküm çizgileri ve büküm tablosu üstünde."},
    {"tip": "adim", "adim": 7, "sure": 8000, "resim": "ekran_07.jpg", "yon": "sol",
     "baslik": "245 resim A3 paftaya",
     "madde": ["Kâğıt yönünü ve ölçeği program seçer",
               "Pafta resmin kendi dosyasına eklenir; 1:1 çizim bozulmaz",
               "Firma anteti varsa kendiliğinden doldurulur"],
     "sure_yazi": "245 pafta: 4 dk 03 sn",
     "vurgu": [((581, 201, 674, 427), "ölçek otomatik")]},
    {"tip": "adim", "adim": 7, "sure": 7000, "resim": "ekran_09.jpg", "yon": "sag",
     "baslik": "PDF: basılmaya hazır",
     "madde": ["PDF klasörüne ..._A3.pdf adıyla", "Kâğıt ölçüsü birebir: %100 basın",
               "Detay resmi ve açınım birlikte"],
     "sure_yazi": "PDF başına ≈ 4 sn",
     "vurgu": [((978, 12, 1226, 186), "önizleme")]},
    {"tip": "adim", "adim": 8, "sure": 7500, "resim": "ekran_13.jpg", "yon": "sol",
     "baslik": "Lazer kesim dosyaları",
     "madde": ["Yalnız kesim konturu: dış kontur + delikler, 1:1",
               "Yazı, ölçü, antet yok: CAM yazılımına doğrudan",
               "Kimliği dosya adında: poz + kod"],
     "sure_yazi": "86 lazer: 1 dk 11 sn",
     "vurgu": [((13, 50, 430, 76), "LAZER.csv"), ((13, 95, 430, 118), "_Lzr.dxf")]},
    {"tip": "klasor", "sure": 8000,
     "baslik": "Her şey yerli yerinde",
     "resimler": ["ekran_11.jpg", "ekran_12.jpg", "ekran_14.jpg"],
     "etiket": ["çıktı klasörü", "DXF/", "ACINIM/"],
     "alt": "DXF · ACINIM · LZR · PDF klasörleri; BOM, hiyerarşik BOM ve ölçü raporu kökte."},
    {"tip": "adim", "adim": 2, "sure": 7500, "resim": "ekran_16.jpg", "yon": "sag",
     "baslik": "BOM Excel'de",
     "madde": ["Poz, kod, ad, adet, malzeme", "Ölçü ve adet başına / toplam kütle",
               "Hangi DXF'in hangi poza ait olduğu"],
     "sure_yazi": "197 poz, 259,9 kg",
     "vurgu": [((750, 22, 880, 392), "kg")]},
    {"tip": "sure", "sure": 9000,
     "baslik": "Her işlem ölçülür, ekranda görünür",
     "resim": "ekran_10.jpg",
     "cubuk": [("Model okuma", 40), ("BOM", 16), ("Örnek resim", 106), ("159 detay resmi", 570),
               ("106 açınım", 261), ("Pafta planı", 97), ("245 pafta", 243), ("86 lazer", 71)],
     "toplam": "23 dk 40 sn"},
    {"tip": "guven", "sure": 9500,
     "baslik": "Ölçer, tahmin etmez.",
     "kart": [("1992", "konum ölçüsü", "3D modelle doğrulandı · 0 hata"),
              ("%0,47", "yanlış tanıma", "214 geometrik kararda 1"),
              ("0", "uydurma ölçü", "emin değilse resme yazmaz")],
     "ornek": [("COMPOUND", "→ somun", "6 yüz 60° · anahtar ağzı 13 · delik Ø6,9"),
               ("M10 KAYNAK SOMUNU", "→ standart", "dikiş değil, BOM'a girer"),
               ("K0 CIVATA LAMASI", "→ üretim parçası", "asıl isim sondadır")]},
    {"tip": "kapanis", "sure": 9000},
]


def e(t):
    return html.escape(t)


def adimlar(aktif):
    h = ['<div class="adimlar">']
    for i, a in enumerate(ADIMLAR, 1):
        h.append(f'<span class="{"aktif" if i == aktif else ("gecti" if aktif and i < aktif else "")}">'
                 f'<b>{i}</b>{a}</span>')
    h.append("</div>")
    return "".join(h)


def ust_bant(aktif=0):
    return ('<div class="bant"><img src="g/urun.png" class="bantlogo"><div><div class="bantad">' + e(URUN) + '</div>'
            '<div class="bantby">BY PIVISION</div></div></div>' + (adimlar(aktif) if aktif else ""))


def cerceve(ad, vurgu, x, y, gen, yon, t0=250):
    w, h = boy(ad)
    yuk = gen * h / w
    if yuk > 700:
        gen = gen * 700 / yuk; yuk = 700
    k = gen / w
    don = "6deg" if yon == "sag" else "-6deg"
    s = [f'<div class="cerceve a" data-a="{"kaysol" if yon == "sag" else "kaysag"}" data-t="{t0}" data-d="900" '
         f'style="left:{x}px;top:{y}px;width:{gen:.0f}px;height:{yuk:.0f}px;--don:{don}">'
         f'<img class="kb" src="g/{ad}" style="width:{gen:.0f}px;height:{yuk:.0f}px">']
    for j, ((x0, y0, x1, y1), et) in enumerate(vurgu):
        s.append(f'<div class="vurgu a" data-a="patla" data-t="{1700 + j * 900}" data-d="600" '
                 f'style="left:{x0 * k - 6:.0f}px;top:{y0 * k - 6:.0f}px;width:{(x1 - x0) * k + 12:.0f}px;'
                 f'height:{(y1 - y0) * k + 12:.0f}px">'
                 + (f'<span>{e(et)}</span>' if et else "") + "</div>")
    s.append("</div>")
    return "".join(s), gen, yuk


def slayt_html(i, sl):
    t = sl["tip"]
    if t == "kapak":
        return ('<div class="kapak">'
                '<img class="klogo a" data-a="patla" data-t="200" data-d="900" src="g/urun.png">'
                f'<div class="kad a" data-a="kaysag" data-t="700" data-d="800">{e(URUN)}</div>'
                '<div class="kby a" data-a="kaysag" data-t="900" data-d="800">BY PIVISION</div>'
                '<h1>' + "".join(f'<span class="a" data-a="kaysol" data-t="{1500 + j * 400}" data-d="700">{e(t)}</span>'
                                 for j, t in enumerate(KAPAK)) + '</h1>'
                f'<div class="ksari a" data-a="patla" data-t="3200" data-d="700">{e(SLOGAN)}</div>'
                '<img class="kpiv a" data-a="alt" data-t="4200" data-d="900" src="g/pivision.png">'
                '</div>')
    if t == "kapanis":
        return ('<div class="kapak kapanis">'
                '<img class="klogo a" data-a="patla" data-t="200" data-d="900" src="g/urun.png">'
                '<h1>' + "".join(f'<span class="a" data-a="kaysol" data-t="{900 + j * 500}" data-d="700">{e(t)}</span>'
                                 for j, t in enumerate(KAPANIS)) + '</h1>'
                f'<div class="ksari a" data-a="patla" data-t="2800" data-d="700">{e(SLOGAN)}</div>'
                f'<div class="kliste a" data-a="alt" data-t="3600" data-d="800">{e(KAPANIS_LISTE)}</div>'
                '<img class="kpiv2 a" data-a="patla" data-t="4400" data-d="1000" src="g/pivision.png">'
                '</div>')
    if t == "rakam":
        r = [ust_bant(), f'<div class="ust a" data-a="kaysol" data-t="200" data-d="700">{e(sl["ust"])}</div>',
             f'<h2 class="rb a" data-a="kaysol" data-t="450" data-d="800">{e(sl["baslik"])}</h2>',
             f'<div class="ralt a" data-a="kaysol" data-t="800" data-d="800">{e(sl["alt"])}</div><div class="rakamlar">']
        for j, (n, ad, a2) in enumerate(sl["rakamlar"]):
            r.append(f'<div class="rk a" data-a="patla" data-t="{1500 + j * 450}" data-d="600">'
                     f'<div class="sayi a" data-a="say" data-hedef="{n}" data-t="{1500 + j * 450}" data-d="1800">0</div>'
                     f'<div class="rad">{e(ad)}</div><div class="ra2">{e(a2)}</div></div>')
        r.append(f'</div><div class="rnot a" data-a="alt" data-t="4600" data-d="800">{e(sl["not"])}</div>')
        return "".join(r)
    if t == "adim":
        yon = sl["yon"]
        c, gen, yuk = cerceve(sl["resim"], sl["vurgu"], 70 if yon == "sol" else 700, 0, 1140, yon)
        top = 175 + (720 - yuk) / 2
        c = c.replace("top:0px", f"top:{top:.0f}px")
        tx = 1260 if yon == "sol" else 80
        m = [f'<div class="metin" style="left:{tx}px">',
             f'<div class="rozet a" data-a="patla" data-t="400" data-d="500">ADIM {sl["adim"]} · {ADIMLAR[sl["adim"] - 1]}</div>',
             f'<h2 class="a" data-a="{"kaysag" if yon == "sol" else "kaysol"}" data-t="600" data-d="700">{e(sl["baslik"])}</h2><ul>']
        for j, md in enumerate(sl["madde"]):
            m.append(f'<li class="a" data-a="{"kaysag" if yon == "sol" else "kaysol"}" data-t="{1200 + j * 450}" data-d="600">{e(md)}</li>')
        m.append(f'</ul><div class="sure a" data-a="patla" data-t="{1300 + len(sl["madde"]) * 450}" data-d="600">⏱ {e(sl["sure_yazi"])}</div></div>')
        return ust_bant(sl["adim"]) + c + "".join(m)
    if t == "resim":
        w, h = boy(sl["resim"])
        gen = 1760; yuk = gen * h / w
        return (ust_bant(sl["adim"]) +
                f'<h2 class="ortab a" data-a="kaysol" data-t="300" data-d="700">{e(sl["baslik"])}</h2>'
                f'<div class="cerceve duz a" data-a="yakin" data-t="700" data-d="1200" style="left:80px;top:{560 - yuk / 2:.0f}px;width:{gen}px;height:{yuk:.0f}px">'
                f'<img class="kb" src="g/{sl["resim"]}" style="width:{gen}px;height:{yuk:.0f}px"></div>'
                f'<div class="ortalt a" data-a="alt" data-t="2200" data-d="800">{e(sl["alt"])}</div>')
    if t == "klasor":
        r = [ust_bant(), f'<h2 class="ortab a" data-a="kaysol" data-t="300" data-d="700">{e(sl["baslik"])}</h2>']
        yer = [(80, 250, 900), (720, 330, 560), (1320, 300, 540)]
        for j, (ad, et) in enumerate(zip(sl["resimler"], sl["etiket"])):
            x, y, gen = yer[j]
            w, h = boy(ad); yuk = gen * h / w
            r.append(f'<div class="cerceve a" data-a="patla" data-t="{700 + j * 700}" data-d="700" '
                     f'style="left:{x}px;top:{y}px;width:{gen}px;height:{yuk:.0f}px;--don:0deg;z-index:{j + 2}">'
                     f'<img class="kb" src="g/{ad}" style="width:{gen}px;height:{yuk:.0f}px">'
                     f'<div class="etk">{e(et)}</div></div>')
        r.append(f'<div class="ortalt a" data-a="alt" data-t="3000" data-d="800" style="top:960px">{e(sl["alt"])}</div>')
        return "".join(r)
    if t == "sure":
        r = [ust_bant(), f'<h2 class="ortab a" data-a="kaysol" data-t="300" data-d="700">{e(sl["baslik"])}</h2>']
        w, h = boy(sl["resim"])
        r.append(f'<div class="cerceve a" data-a="kaysag" data-t="500" data-d="800" style="left:1480px;top:210px;width:330px;height:{330 * h / w:.0f}px;--don:-5deg">'
                 f'<img class="kb" src="g/{sl["resim"]}" style="width:330px;height:{330 * h / w:.0f}px"></div>')
        en = max(s for _, s in sl["cubuk"])
        r.append('<div class="cubuklar">')
        for j, (ad, s) in enumerate(sl["cubuk"]):
            dk = f"{s // 60} dk {s % 60:02d} sn" if s >= 60 else f"{s} sn"
            r.append(f'<div class="cs"><div class="cad">{e(ad)}</div><div class="cyol">'
                     f'<div class="cb a" data-a="uza" data-t="{1000 + j * 250}" data-d="900" style="width:{s / en * 100:.1f}%"></div></div>'
                     f'<div class="csu a" data-a="alt" data-t="{1400 + j * 250}" data-d="500">{dk}</div></div>')
        r.append(f'</div><div class="toplam a" data-a="patla" data-t="3600" data-d="700">TOPLAM <b>{e(sl["toplam"])}</b>'
                 '<span>ölçülen, ekrandaki süre paneli</span></div>')
        return "".join(r)
    if t == "guven":
        r = [ust_bant(), f'<h2 class="gb a" data-a="kaysol" data-t="300" data-d="800">{e(sl["baslik"])}</h2><div class="kartlar">']
        for j, (n, ad, a2) in enumerate(sl["kart"]):
            r.append(f'<div class="gk a" data-a="patla" data-t="{900 + j * 450}" data-d="600"><div class="gn">{e(n)}</div>'
                     f'<div class="gad">{e(ad)}</div><div class="ga2">{e(a2)}</div></div>')
        r.append('</div><div class="tanima"><div class="tbas a" data-a="alt" data-t="2600" data-d="600">Parça mı, standart mı, kaynak mı — adından, montaj ağacından, geometrisinden:</div>')
        for j, (ad, s, g) in enumerate(sl["ornek"]):
            r.append(f'<div class="tk a" data-a="kaysol" data-t="{3100 + j * 500}" data-d="600"><span class="tad">{e(ad)}</span>'
                     f'<span class="ts">{e(s)}</span><span class="tg">{e(g)}</span></div>')
        r.append("</div>")
        return "".join(r)
    raise ValueError(t)


CSS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sunum.css"), encoding="utf-8").read()
JS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "oynat.js"), encoding="utf-8").read()

govde = []
for i, sl in enumerate(SLAYT):
    govde.append(f'<section class="slayt s-{sl["tip"]}" data-sure="{sl["sure"]}">{slayt_html(i, sl)}'
                 f'<div class="no">{i + 1:02d} / {len(SLAYT)}</div></section>')
sayfa = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(URUN)} Tanıtım</title><link rel="stylesheet" href="font.css"><style>{CSS}</style></head>
<body><div id="sahne"><div class="fon"><div class="izgara"></div><img class="filigran" src="g/pivision_fon.png"></div>
{''.join(govde)}<div class="ilerleme"><div id="ilerleme"></div></div></div>
<script>{JS}</script></body></html>"""
open(os.path.join(OUT, "Tanitim.html"), "w", encoding="utf-8").write(sayfa)
json.dump({"slaytlar": SLAYT, "adimlar": ADIMLAR, "urun": URUN, "kapak": KAPAK,
           "slogan": SLOGAN, "kapanis": KAPANIS, "kapanis_liste": KAPANIS_LISTE,
           "boy": {a: boy(a) for a in os.listdir(G) if a.endswith((".jpg", ".png"))}},
          open(os.path.join(OUT, "slaytlar.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("toplam süre:", sum(s["sure"] for s in SLAYT) / 1000, "sn,", len(SLAYT), "slayt")
