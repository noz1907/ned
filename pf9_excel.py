# -*- coding: utf-8 -*-
"""EXCEL ÇIKTISI: tabloları gerçek .xlsx olarak yazar (ek kütüphane yok).

Neden: CSV'de rakam yazıdır, Excel onu bölgesel ayara göre YORUMLAR.
Türkçe Excel'de nokta binlik ayırıcıdır:
    CSV'deki 15.2243 kg  ->  Excel 152.243 (yüz elli iki bin!) gösterir
    CSV'deki poz 1.1     ->  Excel "1 Oca" tarihine çevirir
    UTF-8 Türkçe harf    ->  eski Excel'de "baÄŸlama" olur
.xlsx'te her hücrenin türü dosyada yazılıdır: sayı sayıdır, yazı
yazıdır; hiçbir Excel ayarı onu değiştiremez.

CSV'ler de Türkçe Excel'e göre yazılır (ondalık VİRGÜL, sütun ;),
ama önerilen dosya .xlsx'tir.
"""
from __future__ import annotations

import os
import re
import zipfile
from xml.sax.saxutils import escape

# Excel sütun adı: 0 -> A, 26 -> AA
def _sutun(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


_YASAK = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _hucre(ref, v, stil):
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        v = "evet" if v else "hayır"
    if isinstance(v, (int, float)):
        if v != v or v in (float("inf"), float("-inf")):
            return ""
        s = 2 if isinstance(v, float) and not float(v).is_integer() else 1
        return f'<c r="{ref}" s="{stil or s}"><v>{repr(v) if isinstance(v, float) else v}</v></c>'
    if isinstance(v, (list, tuple)):
        v = ", ".join(str(x) for x in v)
    t = escape(_YASAK.sub("", str(v)))
    return f'<c r="{ref}" t="inlineStr" s="{stil}"><is><t xml:space="preserve">{t}</t></is></c>'


def _sayfa(baslik, satirlar):
    gen = [len(str(b)) for b in baslik]
    for r in satirlar[:500]:
        for i, v in enumerate(r):
            if i < len(gen):
                gen[i] = max(gen[i], len(f"{v:.3f}" if isinstance(v, float) else str(v)))
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{min(max(g, 6) + 2, 60)}" '
                   f'customWidth="1"/>' for i, g in enumerate(gen))
    x = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
         '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
         'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
         f'<cols>{cols}</cols><sheetData>']
    x.append('<row r="1">' + "".join(_hucre(f"{_sutun(i)}1", b, 3)
                                     for i, b in enumerate(baslik)) + "</row>")
    for n, r in enumerate(satirlar, start=2):
        x.append(f'<row r="{n}">' + "".join(_hucre(f"{_sutun(i)}{n}", v, 0)
                                             for i, v in enumerate(r)) + "</row>")
    x.append("</sheetData>")
    if baslik:
        x.append(f'<autoFilter ref="A1:{_sutun(len(baslik) - 1)}{max(1, len(satirlar) + 1)}"/>')
    x.append("</worksheet>")
    return "".join(x)


_STIL = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
         '<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.000"/></numFmts>'
         '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
         '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
         '<fills count="3"><fill><patternFill patternType="none"/></fill>'
         '<fill><patternFill patternType="gray125"/></fill>'
         '<fill><patternFill patternType="solid"><fgColor rgb="FFD9E1F2"/>'
         '<bgColor indexed="64"/></patternFill></fill></fills>'
         '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
         '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
         '<cellXfs count="4">'
         '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
         '<xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
         '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
         '<xf numFmtId="49" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" '
         'applyFill="1" applyNumberFormat="1"/>'
         '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/>'
         '</cellStyles></styleSheet>')


def _suzgec_adlari(adlar, sayfalar):
    x = [f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
         f"'{escape(a)}'!$A$1:${_sutun(len(sayfalar[i][1]) - 1)}"
         f"${max(1, len(sayfalar[i][2]) + 1)}</definedName>"
         for i, a in enumerate(adlar) if sayfalar[i][1]]
    return f"<definedNames>{''.join(x)}</definedNames>" if x else ""


def xlsx_yaz(yol, sayfalar):
    """sayfalar: [(sayfa_adi, baslik_listesi, satir_listeleri)].
    Satır değerleri: int/float sayı olarak, geri kalanı yazı olarak."""
    adlar = []
    for ad, _b, _s in sayfalar:
        a = re.sub(r"[\[\]:*?/\\]", "_", str(ad))[:31] or "Sayfa"
        while a in adlar:
            a = a[:28] + f"_{len(adlar)}"
        adlar.append(a)
    n = len(sayfalar)
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          + "".join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" '
                    f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                    for i in range(n)) + "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
          + "".join(f'<sheet name="{escape(a)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>'
                    for i, a in enumerate(adlar))
          + "</sheets>"
          + _suzgec_adlari(adlar, sayfalar)
          + "</workbook>")
    wbr = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
           + "".join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
                     for i in range(n))
           + f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
           "</Relationships>")
    gecici = yol + ".yaziliyor"
    with zipfile.ZipFile(gecici, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wbr)
        z.writestr("xl/styles.xml", _STIL)
        for i, (_a, b, s) in enumerate(sayfalar):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", _sayfa(list(b), [list(r) for r in s]))
    # Excel'de açık dosyanın üstüne yazılamaz (Windows kilitler): o zaman
    # eski dosya kalır, yenisi yanına yazılır; iş durmaz.
    try:
        os.replace(gecici, yol)
        return yol
    except OSError:
        yedek = os.path.splitext(yol)[0] + "_yeni.xlsx"
        try:
            os.replace(gecici, yedek)
            return yedek
        except OSError:
            os.remove(gecici)
            raise


def sozlukten(alan, satirlar):
    """DictWriter satırlarını (alan sırasıyla) liste satırına çevirir."""
    return [[r.get(a, "") for a in alan] for r in satirlar]


# ------------------------------------------------------------ CSV
def tr_sayi(v):
    """CSV hücresi: ondalık sayıyı Türkçe Excel'in okuyacağı biçimde
    (virgül) yazar. Tam sayı ve yazı olduğu gibi kalır."""
    if isinstance(v, float) and not isinstance(v, bool):
        if v != v:
            return ""
        s = repr(v) if abs(v) >= 1e-4 or v == 0 else f"{v:.10f}".rstrip("0")
        if "e" in s:
            s = f"{v:.10f}".rstrip("0").rstrip(".")
        if s.endswith(".0"):
            s = s[:-2]
        return s.replace(".", ",")
    return v


def tr_satir(r):
    if isinstance(r, dict):
        return {k: tr_sayi(v) for k, v in r.items()}
    return [tr_sayi(v) for v in r]


# Sayı olması gereken sütunlar (adından). Kod, ad, dosya adı YAZI kalır:
# "001" kodunun başındaki sıfırlar kaybolmasın.
_SAYI_SUTUN = re.compile(r"(_mm\d?|_kg|_t|_g_cm3|adet|adedi|sayisi|faktor|^seviye|^poz)$")


def sayiya(sutun, v):
    """CSV'den okunan (ya da hesaptan gelen) değeri, sütun sayı sütunuysa
    sayıya çevirir. "15,22" ve "15.22" ikisi de 15.22 olur (eski sürümün
    noktalı CSV'si de okunur). Ağaç pozu "1.1" yazı kalır."""
    if not isinstance(v, str) or not _SAYI_SUTUN.search(str(sutun)):
        return v
    s = v.strip()
    if sutun == "poz" or sutun == "seviye":
        return int(s) if re.fullmatch(r"\d+", s) else v
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+[.,]\d+", s):
        return float(s.replace(",", "."))
    return v


def tablo_yaz(yol_csv, baslik, satirlar, sayfa=None):
    """Aynı tabloyu hem CSV (Türkçe Excel biçimi) hem .xlsx yazar.
    satirlar: liste satırları (baslik sırasıyla). .xlsx yolunu döner
    (yazılamadıysa None - CSV yine yazılmıştır)."""
    import csv
    with open(yol_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(baslik)
        for r in satirlar:
            w.writerow(tr_satir(list(r)))
    xs = [[sayiya(b, v) for b, v in zip(baslik, r)] for r in satirlar]
    try:
        return xlsx_yaz(os.path.splitext(yol_csv)[0] + ".xlsx",
                        [(sayfa or os.path.splitext(os.path.basename(yol_csv))[0],
                          baslik, xs)])
    except Exception:
        return None
