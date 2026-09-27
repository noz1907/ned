# -*- coding: utf-8 -*-
"""pptxgenjs çıktısına geçiş + giriş animasyonu ekler.
Öğe adı: anim_<tip>_<gecikme ms>_<n>. Slayt süresi slaytlar.json'dan
(advTm: sunumda kendiliğinden ilerler; tıklayınca da geçer)."""
import json, re, sys, zipfile, os
ham, cikti = sys.argv[1], sys.argv[2]
V = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "slaytlar.json"), encoding="utf-8"))
GECIS = ['<p:push dir="l"/>', '<p:zoom/>', '<p:push dir="u"/>', '<p:fade/>', '<p:cover dir="l"/>']
SAHIP = {"uc": ("2", "8", "0-#ppt_w/2", "#ppt_x", "#ppt_y", "#ppt_y"),
         "ucsag": ("2", "2", "1+#ppt_w/2", "#ppt_x", "#ppt_y", "#ppt_y"),
         "alt": ("2", "4", "#ppt_x", "#ppt_x", "1+#ppt_h/2", "#ppt_y")}


class Sayac:
    n = 4
    def __call__(self):
        Sayac.n += 1
        return Sayac.n


def gorun(i, spid):
    return (f'<p:set><p:cBhvr><p:cTn id="{i()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
            f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>'
            f'</p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>')


def anim(i, spid, ad, a, b, dur):
    va = f'<p:fltVal val="{a}"/>' if a in ("0",) else f'<p:strVal val="{a}"/>'
    return (f'<p:anim calcmode="lin" valueType="num"><p:cBhvr additive="base"><p:cTn id="{i()}" dur="{dur}" fill="hold"/>'
            f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl><p:attrNameLst><p:attrName>{ad}</p:attrName></p:attrNameLst></p:cBhvr>'
            f'<p:tavLst><p:tav tm="0"><p:val>{va}</p:val></p:tav><p:tav tm="100000"><p:val><p:strVal val="{b}"/></p:val></p:tav>'
            f'</p:tavLst></p:anim>')


def efekt(i, spid, tip, gecikme):
    if tip == "patla":
        ic = (gorun(i, spid) + anim(i, spid, "ppt_w", "0", "#ppt_w", 550) + anim(i, spid, "ppt_h", "0", "#ppt_h", 550)
              + f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{i()}" dur="550"/>'
                f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>')
        pid, sub = "53", "16"
    elif tip in SAHIP:
        pid, sub, x0, x1, y0, y1 = SAHIP[tip]
        ic = gorun(i, spid) + anim(i, spid, "ppt_x", x0, x1, 650) + anim(i, spid, "ppt_y", y0, y1, 650)
    else:
        pid, sub = "10", "0"
        ic = (gorun(i, spid) + f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{i()}" dur="500"/>'
              f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:animEffect>')
    return (f'<p:par><p:cTn id="{i()}" presetID="{pid}" presetClass="entr" presetSubtype="{sub}" fill="hold" nodeType="withEffect">'
            f'<p:stCondLst><p:cond delay="{gecikme}"/></p:stCondLst><p:childTnLst>{ic}</p:childTnLst></p:cTn></p:par>')


def zamanlama(ogeler):
    i = Sayac(); Sayac.n = 4
    ef = "".join(efekt(i, spid, tip, t) for spid, tip, t in ogeler)
    return ('<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
            '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
            '<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond>'
            '</p:stCondLst><p:childTnLst><p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            + ef +
            '</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>'
            '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
            '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>'
            '</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>')


zin = zipfile.ZipFile(ham)
zout = zipfile.ZipFile(cikti, "w", zipfile.ZIP_DEFLATED)
toplam = 0
for it in zin.infolist():
    veri = zin.read(it.filename)
    m = re.match(r"ppt/slides/slide(\d+)\.xml$", it.filename)
    if m:
        n = int(m.group(1)); sl = V["slaytlar"][n - 1]
        x = veri.decode("utf-8")
        ogeler = []
        for spid, ad in re.findall(r'<p:cNvPr id="(\d+)" name="(anim_[^"]+)"', x):
            _, tip, t, _k = ad.split("_")
            ogeler.append((spid, tip, int(t)))
        ogeler.sort(key=lambda o: o[2])
        toplam += len(ogeler)
        gecis = (f'<p:transition spd="slow" advTm="{sl["sure"]}">{GECIS[(n - 1) % len(GECIS)]}</p:transition>'
                 if n > 1 else f'<p:transition spd="slow" advTm="{sl["sure"]}"><p:fade/></p:transition>')
        ek = gecis + (zamanlama(ogeler) if ogeler else "")
        x = x.replace("</p:clrMapOvr>", "</p:clrMapOvr>" + ek, 1) if "</p:clrMapOvr>" in x else x.replace("</p:sld>", ek + "</p:sld>")
        veri = x.encode("utf-8")
    zout.writestr(it, veri)
zout.close()
print("animasyonlu öğe:", toplam)
