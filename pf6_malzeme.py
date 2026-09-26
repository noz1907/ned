# -*- coding: utf-8 -*-
"""Pi3D - malzemeyi CAD'den almak: yardım metinleri, makrolar, eşleştirme.

Sorun: STEP geometriyi taşır, malzemeyi çoğu zaman TAŞIMAZ. AP214/AP242'de
malzeme adı ve yoğunluğu için alan vardır ama CAD'lerin çoğu varsayılan
ayarla doldurmaz (elimizdeki dört gerçek modelin - biri CATIA V5 - hiçbirinde
yok). Malzeme verilmezse her parça çelik sayılır ve kütle yanlış çıkar.

Üç yol, güvenilirlik sırasıyla:
  1. STEP'in kendisi    - malzeme yazılmışsa Pi3D kendisi okur (ad +
                           yoğunluk); 1. adımdan sonra kaçının geldiği yazar.
  2. CAD'in parça listesi - her CAD, parça no + malzeme (+ yoğunluk) sütunlu
                           bir tabloyu CSV / TXT / Excel olarak verebilir.
                           Kod gerekmez; en güvenilir yol budur.
  3. Makro              - çok montaj varsa: CAD içinde çalışıp malzeme.csv
                           yazar (CATIA, SolidWorks).

Bu modül arayüzden bağımsızdır: sihirbaz (pf3_gui) metinleri ve makroları
buradan alır, dosya eşleştirmesini buradan yaptırır.
"""
import os

# --------------------------------------------------------------- makrolar
SW_MAKRO_ADI = "pi3d_malzeme_sw.bas"
SW_MAKRO = r'''Attribute VB_Name = "Pi3DMalzeme"
' Pi3D - SolidWorks'ten malzeme listesi
'
' Acik montajin (ya da parcanin) her parcasi icin bir satir yazar:
'     parca no ; malzeme ; yogunluk (kg/m3)
' Dosya belgenin klasorune "malzeme.csv" adiyla yazilir.
'
' Kullanim: Araclar > Makro > Yeni  -> bos makroyu kaydedin; acilan VBA
' duzenleyicide Dosya > Dosya Iceri Aktar ile bu .bas dosyasini alin,
' "main" yordamini calistirin (F5). Ayrinti: Pi3D > Yardim.
'
' Parca no = parca DOSYASININ adi (uzantisiz). SolidWorks STEP'e parcalari
' bu adla yazar; Pi3D eslestirmeyi bununla yapar.
Option Explicit

Dim yazilan As Object

Sub main()
    Dim swApp As Object, doc As Object
    Set swApp = Application.SldWorks
    Set doc = swApp.ActiveDoc
    If doc Is Nothing Then
        MsgBox "Once montaji (ya da parcayi) acin.", vbExclamation, "Pi3D"
        Exit Sub
    End If
    Dim yol As String
    yol = doc.GetPathName
    If yol = "" Then
        MsgBox "Belge henuz kaydedilmemis; once kaydedin.", vbExclamation, "Pi3D"
        Exit Sub
    End If
    yol = Left(yol, InStrRev(yol, "\")) & "malzeme.csv"
    Set yazilan = CreateObject("Scripting.Dictionary")
    Dim f As Integer
    f = FreeFile
    Open yol For Output As #f
    Print #f, "Part Number;Material;Density (kg/m3)"
    Dim n As Long
    n = 0
    If doc.GetType = 2 Then                     ' montaj
        Dim comps As Variant, i As Long
        doc.ResolveAllLightWeightComponents False
        comps = doc.GetComponents(False)        ' butun kademeler
        If Not IsEmpty(comps) Then
            For i = 0 To UBound(comps)
                n = n + ParcaYaz(f, comps(i).GetModelDoc2, _
                                 comps(i).ReferencedConfiguration)
            Next i
        End If
    ElseIf doc.GetType = 1 Then                 ' tek parca
        n = ParcaYaz(f, doc, doc.ConfigurationManager.ActiveConfiguration.Name)
    End If
    Close #f
    MsgBox n & " parca yazildi:" & vbCrLf & yol & vbCrLf & vbCrLf & _
           "Pi3D'de: Yardim > Malzemeyi CAD'den al > 4. adim", _
           vbInformation, "Pi3D"
End Sub

Function ParcaYaz(f As Integer, m As Object, cfg As String) As Long
    ParcaYaz = 0
    If m Is Nothing Then Exit Function          ' bastirilmis bilesen
    If m.GetType <> 1 Then Exit Function        ' yalniz parcalar
    Dim ad As String
    ad = m.GetPathName
    ad = Mid(ad, InStrRev(ad, "\") + 1)
    If InStrRev(ad, ".") > 0 Then ad = Left(ad, InStrRev(ad, ".") - 1)
    If yazilan.Exists(ad & "|" & cfg) Then Exit Function
    yazilan.Add ad & "|" & cfg, 1
    Dim db As String, mal As String
    mal = m.GetMaterialPropertyName2(cfg, db)
    Dim yog As Double
    yog = 0
    On Error Resume Next
    Dim mp As Object
    Set mp = m.Extension.CreateMassProperty
    If Not mp Is Nothing Then yog = mp.Density  ' kg/m3
    On Error GoTo 0
    Print #f, Temiz(ad) & ";" & Temiz(mal) & ";" & _
              Replace(Format(yog, "0.0"), ",", ".")
    ParcaYaz = 1
End Function

Function Temiz(t As String) As String
    Temiz = Replace(Replace(t, ";", ","), vbTab, " ")
End Function
'''

CATIA_MAKRO_ADI = "catia_malzeme_cikar.CATScript"


def _catia_makro():
    """CATIA makrosu depoda ayrı dosyadır (kök klasör ya da exe'nin yanı)."""
    import sys
    for kl in (os.path.dirname(os.path.abspath(__file__)),
               os.path.dirname(sys.executable),
               getattr(sys, "_MEIPASS", "")):
        y = os.path.join(kl, CATIA_MAKRO_ADI)
        if kl and os.path.isfile(y):
            with open(y, "rb") as f:
                return f.read()
    return None


# ----------------------------------------------------------- CAD sistemleri
# Her sistem: ad, parça listesi (BOM) yolu adım adım, varsa makro.
# Menü adları CAD'in İngilizce arayüzüne göre yazıldı; Türkçe arayüzde
# karşılığı parantez içinde. Sürümden sürüme adlar değişebilir - AMAÇ her
# zaman aynıdır: "parça no + malzeme (+ yoğunluk)" sütunlu bir tablo.
SISTEM = [
    {"anahtar": "step", "ad": "STEP dosyasının kendisi",
     "adimlar": [
         "STEP AP214 / AP242, malzeme adını ve yoğunluğunu taşıyabilir. "
         "Taşıyorsa Pi3D kendisi okur; sizin bir şey yapmanız gerekmez.",
         "Bu sihirbazın 1. adımı, açık modelde kaç parçanın malzemesinin "
         "STEP'ten geldiğini gösterir. Hepsi geldiyse burada bitti.",
         "Gelmediyse: CAD'inizin STEP dışa aktarım seçeneklerinde "
         "'özellikler / malzeme / attributes' gibi bir kutucuk olup "
         "olmadığına bakın (sürüme göre adı ve varlığı değişir). Yoksa "
         "listeden kendi CAD'inizi seçip parça listesi yolunu kullanın.",
         "Parasolid, JT, IGES gibi biçimlerde malzeme standart bir alan "
         "değildir; o yolla gelmez."]},
    {"anahtar": "solidworks", "ad": "SolidWorks",
     "adimlar": [
         "Montajı açın.",
         "Insert ▸ Tables ▸ Bill of Materials  (Ekle ▸ Tablolar ▸ Malzeme "
         "Listesi). Tür olarak 'Parts only' (Yalnızca parçalar) seçin.",
         "Tabloda bir sütun başlığına sağ tıklayın ▸ Insert ▸ Column Right "
         "(Sağa sütun ekle). Sütun türü: Custom Property (Özel özellik), "
         "özellik: SW-Material.",
         "İsteğe bağlı ama önerilir: aynı şekilde bir sütun daha, özellik: "
         "SW-Density. Yoğunluk verilirse, adı tanınmayan malzemenin kütlesi "
         "de doğru çıkar.",
         "Tabloya sağ tıklayın ▸ Save As (Farklı kaydet) ▸ tür: CSV ya da "
         "Excel.",
         "Bu sihirbazın 4. adımında dosyayı seçin."],
     "makro": SW_MAKRO_ADI,
     "makro_adimlar": [
         "Toplu iş için makro: 'Makroyu kaydet' ile pi3d_malzeme_sw.bas "
         "dosyasını kaydedin.",
         "SolidWorks'te montaj açıkken: Tools ▸ Macro ▸ New (Araçlar ▸ "
         "Makro ▸ Yeni) - boş bir makro kaydedin; VBA düzenleyici açılır.",
         "VBA düzenleyicide File ▸ Import File (Dosya ▸ Dosya İçeri Aktar) "
         "ile pi3d_malzeme_sw.bas'ı alın, 'main' yordamını çalıştırın (F5).",
         "Montajın klasörüne malzeme.csv yazılır (parça no; malzeme; "
         "yoğunluk kg/m3). 4. adımda onu seçin.",
         "Not: makro bu makinede SolidWorks olmadan yazıldı; ilk "
         "kullanımda 4. adımdaki önizlemeyi kontrol edin."]},
    {"anahtar": "catia", "ad": "CATIA V5",
     "adimlar": [
         ".CATProduct açıkken: Analyze ▸ Bill of Material.",
         "Define formats ▸ Hidden Properties listesinden 'Material'i seçip "
         "'>' ile Displayed Properties tarafına alın. 'Part Number' görünür "
         "listede olmalı.",
         "OK ▸ Save As ▸ tür: Text (*.txt). ('Excel' seçeneği bazı "
         "kurulumlarda gerçek Excel değil sekmeli metin yazar; Pi3D ikisini "
         "de okur. Gerçek eski .xls ise Excel'de .xlsx ya da CSV olarak "
         "yeniden kaydedin.)",
         "Bu sihirbazın 4. adımında dosyayı seçin."],
     "makro": CATIA_MAKRO_ADI,
     "makro_adimlar": [
         "Toplu iş için makro: 'Makroyu kaydet' ile catia_malzeme_cikar."
         "CATScript dosyasını kaydedin.",
         ".CATProduct açıkken: Tools ▸ Macro ▸ Macros… ▸ Select an external "
         "file ile makroyu seçip Run.",
         "Ürün dosyasının yanına malzeme.csv yazılır. 4. adımda onu seçin."]},
    {"anahtar": "nx", "ad": "Siemens NX",
     "adimlar": [
         "Montajı açın, Assembly Navigator'ı (Montaj Gezgini) gösterin.",
         "Bir sütun başlığına sağ tıklayın ▸ Columns ▸ Configure: "
         "Attributes altından malzeme özniteliğini ekleyin. NX'te malzeme "
         "gövdeye atanır; özniteliğin adı sürüme ve firma şablonuna göre "
         "değişir ('Material' en yaygını).",
         "Gezgine sağ tıklayın ▸ Export to Spreadsheet: tablo Excel'de "
         "açılır. .xlsx olarak kaydedin.",
         "Sütun boş geliyorsa malzeme parça özniteliğine yazılmıyordur; "
         "o zaman firma şablonunuzdaki malzeme özniteliğini kullanın ya da "
         "tabloya bir 'Material' sütununu elle doldurun.",
         "Bu sihirbazın 4. adımında dosyayı seçin."]},
    {"anahtar": "creo", "ad": "PTC Creo",
     "adimlar": [
         "Montajı açın. Model Tree ▸ Settings ▸ Tree Columns: tür olarak "
         "'Model Params' seçip PTC_MATERIAL_NAME parametresini ekleyin.",
         "Tabloyu dışarı alın: bir çizimde 'repeat region' ile "
         "&asm.mbr.name ve &asm.mbr.PTC_MATERIAL_NAME sütunlu bir tablo "
         "kurup Save As Table ile CSV/TXT kaydedin - ya da Model Tree'yi "
         "Excel'e kopyalayıp .xlsx kaydedin. (Menü adları sürüme göre "
         "değişir; amaç: parça adı + malzeme sütunlu bir tablo.)",
         "Bu sihirbazın 4. adımında dosyayı seçin."]},
    {"anahtar": "inventor", "ad": "Autodesk Inventor",
     "adimlar": [
         "Montajı açın: Assemble ▸ Manage ▸ Bill of Materials (Montaj ▸ "
         "Yönet ▸ Malzeme Listesi).",
         "'Parts Only' (Yalnız parçalar) sekmesine geçin; kapalıysa sağ "
         "tıklayıp etkinleştirin. 'Material' sütunu varsayılan olarak "
         "vardır; yoksa Column Chooser'dan ekleyin.",
         "Export Bill of Materials (Malzeme listesini dışa aktar) ▸ tür: "
         "Excel (.xlsx) ya da CSV.",
         "Bu sihirbazın 4. adımında dosyayı seçin."]},
    {"anahtar": "solidedge", "ad": "Solid Edge",
     "adimlar": [
         "Montajın Draft'ında bir Parts List (Parça Listesi) oluşturun; "
         "Properties ▸ Columns'dan 'Material' sütununu ekleyin.",
         "Listeyi Excel'e aktarın (sağ tık ▸ kopyala / kaydet - sürüme "
         "göre) ve .xlsx ya da CSV olarak kaydedin.",
         "Bu sihirbazın 4. adımında dosyayı seçin."]},
    {"anahtar": "parasolid", "ad": "Parasolid (.x_t / .x_b) ve diğerleri",
     "adimlar": [
         "Pi3D Parasolid dosyasını doğrudan açamaz: OpenCascade, Parasolid "
         "çekirdeğini içermez. Malzeme de Parasolid'de standart bir alan "
         "değildir.",
         "Yol: aynı modeli kaynak CAD'den (SolidWorks, NX, Solid Edge...) "
         "STEP AP214/AP242 olarak verin; malzemeyi o CAD'in parça "
         "listesinden alın - listeden o CAD'i seçin.",
         "Hiçbir CAD'e erişiminiz yoksa: 2. adımdaki 'malzeme.csv yaz…' ile "
         "parça listesini şablon olarak alın, malzeme sütununu elle "
         "doldurun, burada yükleyin."]},
]

ORTAK_NOT = (
    "Tablonun biçimi serbesttir: Pi3D başlık satırından 'parça no' ve "
    "'malzeme' sütunlarını adlarından bulur (Part Number, Teilenummer, "
    "Kod...; Material, Werkstoff, Malzeme, SW-Material, PTC_MATERIAL_NAME...), "
    "ayırıcıyı (sekme ; ,) ve kodlamayı kendisi anlar. İsteğe bağlı "
    "yoğunluk sütunu (Density, Dichte, Yoğunluk; kg/m3 ya da g/cm3) "
    "verilirse, adı tanınmayan malzeme ÇELİK SAYILMAZ - kütle CAD'deki "
    "yoğunlukla hesaplanır.")


def sistem(anahtar):
    return next((s for s in SISTEM if s["anahtar"] == anahtar), None)


def talimat_metni(anahtar):
    """Bir CAD sistemi için düz metin talimat (kopyalanabilir)."""
    s = sistem(anahtar)
    if not s:
        return ""
    t = [s["ad"], "=" * len(s["ad"]), ""]
    t += [f"{i}. {a}" for i, a in enumerate(s["adimlar"], 1)]
    if s.get("makro_adimlar"):
        t += ["", "Makro ile (isteğe bağlı)", "-" * 24]
        t += [f"{i}. {a}" for i, a in enumerate(s["makro_adimlar"], 1)]
    if anahtar != "step":
        t += ["", ORTAK_NOT]
    return "\n".join(t)


def makro_yaz(anahtar, klasor):
    """Sistemin makrosunu klasöre yazar; yolunu döndürür (yoksa None)."""
    s = sistem(anahtar)
    if not s or not s.get("makro"):
        return None
    yol = os.path.join(klasor, s["makro"])
    if s["makro"] == SW_MAKRO_ADI:
        # VBA düzenleyicisi .bas'ı Windows satır sonuyla bekler.
        with open(yol, "w", encoding="cp1254", newline="\r\n") as f:
            f.write(SW_MAKRO)
        return yol
    if s["makro"] == CATIA_MAKRO_ADI:
        ham = _catia_makro()
        if ham is None:
            return None
        with open(yol, "wb") as f:
            f.write(ham)
        return yol
    return None


# -------------------------------------------------------------- raporlar
def step_raporu(M, komp):
    """Açık modelde malzemesi STEP'ten gelen parçalar.

    Döner: {"parca", "stepten": [(kod, malzeme adı, yoğunluk)], "eksik"}"""
    parca = [k for k in (komp or []) if k.get("sinif") == "parca"]
    gelen = []
    for k in parca:
        m, kay = M.malzeme_ata(k, {}, None)
        if kay == "data" and k.get("malzeme_data"):
            gelen.append((k.get("kod") or k.get("ad"),
                          str(k.get("malzeme_data")),
                          k.get("malzeme_yogunluk")))
    ad_ipucu = sum(1 for k in parca if M.malzeme_ata(k, {}, None)[1] == "data"
                   and not k.get("malzeme_data"))
    return {"parca": len(parca), "stepten": gelen, "ad_ipucu": ad_ipucu,
            "eksik": len(parca) - len(gelen) - ad_ipucu}


def dosya_raporu(M, yol, komp):
    """Malzeme dosyasının montajla eşleşmesi - UYGULAMADAN önce gösterilir.

    Döner: {
      "satir":    dosyanın satırları (M.malzeme_tablosu),
      "eslesen":  [(komponent, anahtar)],
      "eslesmeyen": [komponent]  - dosyada HİÇ olmayan parçalar,
      "adi_taninmayan": [komponent] - satırı var ama malzeme adı tanınmadı
                                   ve yoğunluğu yok,
      "kullanilmayan": [satır]   - montajda karşılığı olmayan satırlar,
      "taninmayan": [satır]      - adı tanınmayan ve yoğunluğu olmayan,
      "esl": eşleme sözlüğü (uygularken kullanılır)}
    Hata: M.MalzemeDosyaHatasi"""
    satir = M.malzeme_tablosu(yol)
    esl = {M._tr_sade(r["kod"]): r["anahtar"] for r in satir if r["anahtar"]}
    parca = [k for k in (komp or []) if k.get("sinif") == "parca"]

    def satirlari(k):
        """Parçanın dosyadaki satırları (malzeme_ata ile aynı kural:
        kod aynı ya da en az 5 harflik kod, parça kodu/adı içinde)."""
        ks, ads = M._tr_sade(k.get("kod")), M._tr_sade(k.get("ad"))
        out = []
        for r in satir:
            rk = M._tr_sade(r["kod"])
            if rk and (rk == ks or (len(rk) >= 5 and (rk in ks or rk in ads))):
                out.append(r)
        return out

    eslesen, eslesmeyen, adi_taninmayan, kullanilan = [], [], [], set()
    for k in parca:
        m, kay = M.malzeme_ata(k, esl, None, data_oncelik=False)
        rs = satirlari(k)
        kullanilan.update(id(r) for r in rs)
        if kay == "secim" and m:
            eslesen.append((k, m))
        elif rs:
            adi_taninmayan.append(k)   # satırı var, malzemesi çözülemedi
        else:
            eslesmeyen.append(k)       # dosyada hiç yok
    return {"satir": satir, "eslesen": eslesen, "eslesmeyen": eslesmeyen,
            "adi_taninmayan": adi_taninmayan,
            "kullanilmayan": [r for r in satir if id(r) not in kullanilan
                              and r["anahtar"]],
            "taninmayan": [r for r in satir if not r["anahtar"]],
            "esl": esl}
