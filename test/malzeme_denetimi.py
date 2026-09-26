# -*- coding: utf-8 -*-
"""Malzeme CAD'den doğru geliyor mu?

Denetlenen (her biri gerçek bir kusurun tekrarı):
  1. STEP'e yazılmış malzeme OKUNUYOR mu. Eski okuyucu parça etiketini
     malzeme etiketi yerine veriyordu: 'AISI 304', 7,93 yazılı STEP'ten
     None çıkıyordu. Yoğunluk da taşınıyor mu.
  2. CAD parça listeleri: SolidWorks (SW-Material, SW-Density kg/m^3),
     Inventor (ilk sütun "Item" - sıra no'su kod SANILMAMALI), CATIA
     (sekmeli, Windows Türkçe kodlama - "Çelik" bozulmamalı), Almanca
     (Sachnummer / Werkstoff / Dichte "7,85 g/cm³"), tırnaklı CSV
     ("Steel, AISI 1020"), Excel .xlsx.
  3. Eski Excel (.xls) anlaşılır bir hatayla reddediliyor mu.
  4. Adı tanınmayan ama yoğunluğu verilen malzeme ÇELİĞE DÜŞMÜYOR mu:
     CAD'in yoğunluğuyla özel malzeme olmalı, kütle ondan hesaplanmalı.
  5. Yoğunluk birimleri: kg/m3, g/cm3, kg/mm3, lb/in3, birimsiz.

    python test/malzeme_denetimi.py
"""
import io
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pf3_olcu as O                                            # noqa: E402
import pf1_referans as E                                        # noqa: E402

HATA = []


def dogru(ad, kosul, neden=""):
    print(f"  {'tamam' if kosul else 'HATA '} {ad}" + ("" if kosul else f": {neden}"))
    if not kosul:
        HATA.append(ad)


def esit(ad, olan, beklenen):
    dogru(ad, olan == beklenen, f"{olan!r} != {beklenen!r}")


def yaz(kl, ad, icerik, kod="utf-8"):
    yol = os.path.join(kl, ad)
    with open(yol, "wb") as f:
        f.write(icerik if isinstance(icerik, bytes) else icerik.encode(kod))
    return yol


def xlsx(satirlar):
    """En küçük geçerli .xlsx (ortak dizgili) - openpyxl gerekmez."""
    ortak, idx = [], {}
    def si(t):
        if t not in idx:
            idx[t] = len(ortak); ortak.append(t)
        return idx[t]
    sat_xml = []
    for r, satir in enumerate(satirlar, 1):
        hucre = "".join(
            f'<c r="{chr(65 + c)}{r}" t="s"><v>{si(str(v))}</v></c>'
            for c, v in enumerate(satir))
        sat_xml.append(f'<row r="{r}">{hucre}</row>')
    m = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rr = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns='
                   '"http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{m}" xmlns:r="{rr}">'
                   '<sheets><sheet name="BOM" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/relationships"><Relationship Id="rId1" Type="w" '
                   'Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{m}">' + "".join(
            f"<si><t>{t}</t></si>" for t in ortak) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml",
                   f'<worksheet xmlns="{m}"><sheetData>{"".join(sat_xml)}'
                   '</sheetData></worksheet>')
    return b.getvalue()


def main():
    kl = tempfile.mkdtemp(prefix="malzeme_denetim_")

    print("-- 1. STEP'e yazılmış malzeme okunuyor mu")
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.TDocStd import TDocStd_Document
    from OCP.TCollection import TCollection_ExtendedString, TCollection_HAsciiString
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.TDataStd import TDataStd_Name
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("d"))
    app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    mt = XCAFDoc_DocumentTool.MaterialTool_s(doc.Main())
    H = TCollection_HAsciiString
    for i, (ad, mal, yog) in enumerate((("PASLANMAZ-1", "AISI 304", 7.93),
                                        ("HARDOX-2", "Hardox 450", 7850.0),
                                        ("ALU-3", "AlMg4.5Mn", 2.66))):
        lab = st.AddShape(BRepPrimAPI_MakeBox(10 + i, 20, 30).Shape(), False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(ad))
        mt.SetMaterial(lab, mt.AddMaterial(H(mal), H(""), yog, H("density"),
                                           H("POSITIVE_RATIO_MEASURE")))
    w = STEPCAFControl_Writer()
    w.SetMaterialMode(True)
    w.Transfer(doc, STEPControl_AsIs)
    step = os.path.join(kl, "malzemeli.stp")
    w.Write(step)
    kayit = E.step_oku(step, malzeme=True)
    okunan = {a: (str(m), getattr(m, "yogunluk", None)) for a, _k, m in kayit}
    print("     okunan:", okunan)
    esit("AISI 304 ve yoğunluğu okundu", okunan.get("PASLANMAZ-1"),
         ("AISI 304", 7.93))
    komp = O.komponentle(kayit, {})
    ata = {k["ad"]: O.malzeme_ata(k, {}, O.VARSAYILAN_MALZEME)
           for k in komp}
    print("     atanan:", {a: (m, O.MALZEME[m][1], kay) for a, (m, kay) in ata.items()})
    esit("AISI 304 -> paslanmaz (data)", ata["PASLANMAZ-1"], ("paslanmaz", "data"))
    # Hardox aşınma çeliğidir; yoğunluğu 7850 kg/m3 = 7,85 g/cm3.
    esit("Hardox 450 (7850 kg/m3) -> çelik (data)", ata["HARDOX-2"],
         ("celik", "data"))
    esit("AlMg4.5Mn (2,66) -> alüminyum (tablo 2,70, %2 içinde)",
         ata["ALU-3"], ("aluminyum", "data"))

    print("\n-- 2. CAD parça listeleri")
    sw = yaz(kl, "sw_bom.csv",
             "ITEM NO.,PART NUMBER,DESCRIPTION,SW-Material,SW-Density,QTY.\n"
             "1,09.020.000.03,Rollenplatte,AISI 1020,7900.00 kg/m^3,1\n"
             "2,01.050.000.01,U-Blech,\"Alloy Steel, 4340\",7850,2\n"
             "3,06.001.001.34,Keil,Hardox 400,7.85 g/cm^3,1\n")
    esl, bil = O.malzeme_dosya_oku(sw)
    print("     SolidWorks:", esl, bil)
    esit("SW: AISI 1020 -> çelik", esl.get("09.020.000.03"), "celik")
    esit("SW: tırnaklı 'Alloy Steel, 4340' -> çelik", esl.get("01.050.000.01"), "celik")
    esit("SW: Hardox 400 (7,85 g/cm^3) -> çelik", esl.get("06.001.001.34"), "celik")
    # Ad TANINIR ama CAD'deki yoğunluk tablodakinden farklıysa CAD'inki
    # esas alınır: "Steel" 7,70 -> çelik adıyla ama 7,70'lik özel malzeme.
    ay = yaz(kl, "ayri.csv", "kod;malzeme;density\nAY-1;Steel;7500\n")
    e2, _ = O.malzeme_dosya_oku(ay)
    dogru("tanınan ad + %4 farklı yoğunluk: CAD yoğunluğu (7,50) esas",
          abs(O.MALZEME[e2["ay-1"]][1] - 7.50) < 1e-6, str(e2))

    inv = yaz(kl, "inventor.txt",
              "Item\tQty\tPart Number\tDescription\tMaterial\n"
              "1\t2\tPLAKA-100\tTaban\tAluminum 6061\n"
              "2\t4\tMIL-20\tMil\tStainless Steel\n")
    esl, bil = O.malzeme_dosya_oku(inv)
    print("     Inventor:", esl, bil)
    esit("Inventor: kod sütunu 'Part Number' (Item değil)",
         sorted(esl), ["mil-20", "plaka-100"])
    esit("Inventor: Aluminum 6061 -> alüminyum", esl.get("plaka-100"), "aluminyum")

    catia = yaz(kl, "catia.txt",
                "Part Number\tNomenclature\tMaterial\tQuantity\n"
                "01.050.000.14\tFührungsschale\tÇelik\t1\n"
                "01.050.000.15\tFührungsschale\tPirinç\t1\n", kod="cp1254")
    esl, bil = O.malzeme_dosya_oku(catia)
    print("     CATIA (cp1254):", esl, bil)
    esit("CATIA: Windows Türkçe 'Çelik' bozulmadan", esl.get("01.050.000.14"), "celik")
    esit("CATIA: 'Pirinç'", esl.get("01.050.000.15"), "pirinc")

    de = yaz(kl, "stueckliste.csv",
             "Pos;Sachnummer;Benennung;Werkstoff;Dichte\n"
             "1;4711-01;Welle;Sonderstahl X;7,85 g/cm³\n"
             "3;4711-03;Platte;1.0038;\n"
             "2;4711-02;Lager;CuSn8;8,8\n")
    esl, bil = O.malzeme_dosya_oku(de)
    print("     Almanca:", esl, bil)
    esit("DE: malzeme no 1.0038 (S235JR) -> çelik", esl.get("4711-03"), "celik")
    dogru("DE: 'Sonderstahl X' tanınmaz ama Dichte 7,85 ile özel malzeme",
          (esl.get("4711-01") or "").startswith("cad:")
          and abs(O.MALZEME[esl["4711-01"]][1] - 7.85) < 1e-6, str(esl))
    esit("DE: CuSn8 (8,8) -> bronz", esl.get("4711-02"), "bronz")

    xl = yaz(kl, "bom.xlsx", xlsx([["Part Number", "Material", "Density"],
                                   ["XL-1", "Steel", "7850"],
                                   ["XL-2", "Unobtainium", ""],
                                   ["XL-3", "Brass", "8.5"]]))
    esl, bil = O.malzeme_dosya_oku(xl)
    print("     Excel .xlsx:", esl, bil)
    esit("XLSX: Steel -> çelik", esl.get("xl-1"), "celik")
    esit("XLSX: Brass -> pirinç", esl.get("xl-3"), "pirinc")
    esit("XLSX: yoğunluksuz tanınmayan ad raporlanıyor", bil, ["Unobtainium"])

    print("\n-- 3. eski Excel (.xls)")
    xls = yaz(kl, "eski.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 64)
    try:
        O.malzeme_dosya_oku(xls)
        dogru("eski .xls reddedildi", False, "hata çıkmadı")
    except O.MalzemeDosyaHatasi as ex:
        dogru("eski .xls anlaşılır hatayla reddedildi", ".xlsx" in str(ex), str(ex))

    print("\n-- 4. tanınmayan ad + yoğunluk çeliğe DÜŞMÜYOR")
    k = {"kod": "4711-01", "ad": "Welle", "sinif": "parca"}
    esl, _ = O.malzeme_dosya_oku(de)
    m, kay = O.malzeme_ata(k, esl, O.VARSAYILAN_MALZEME)
    esit("eşlemeden geldi", kay, "secim")
    k2 = {"kod": "AL-9", "ad": "x", "sinif": "parca"}
    al = yaz(kl, "al.csv", "kod;malzeme;yoğunluk\nAL-9;Sonderlegierung X;2700 kg/m3\n")
    esl, _ = O.malzeme_dosya_oku(al)
    m, kay = O.malzeme_ata(k2, esl, O.VARSAYILAN_MALZEME)
    dogru("bilinmeyen alaşım 2,70 g/cm³ ile (çelik 7,85 DEĞİL)",
          abs(O.MALZEME[m][1] - 2.70) < 1e-6, f"{m} {O.MALZEME.get(m)}")

    print("\n-- 5. yoğunluk birimleri")
    for hucre, baslik, bek in (("7850", "", 7.85), ("7,85", "", 7.85),
                               ("7850 kg/m^3", "", 7.85), ("7.85", "g/cm3", 7.85),
                               ("7.85e-06", "kg/mm^3", 7.85),
                               ("0.2836", "lb/in^3", 7.85), ("2700", "Density (kg/m3)", 2.7),
                               ("abc", "", None), ("99999", "", None)):
        v = O._yogunluk_coz(hucre, baslik)
        dogru(f"'{hucre}' [{baslik}] -> {bek}",
              (v is None and bek is None) or (v is not None and bek is not None
                                              and abs(v - bek) < 0.01), str(v))

    print("\nSONUC: " + ("TUM DENETIMLER GECTI" if not HATA
                         else f"{len(HATA)} DENETIM KALDI: " + ", ".join(HATA)))
    return 1 if HATA else 0


if __name__ == "__main__":
    sys.exit(main())
