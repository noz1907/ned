# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller tarifi - Pi3D'u tek klasorluk calistirilabilir hale getirir.

    pyinstaller pi3d.spec

Cikti:  dist/Pi3D/Pi3D.exe   (Windows)
        dist/Pi3D/Pi3D       (Linux/macOS)

LOGOLU MU LOGOSUZ MU
    Varsayilan logoludur. Logosuz surum icin derlemeden once:

        set PI3D_LOGO=0        (Windows)
        export PI3D_LOGO=0     (Linux/macOS)

    Logolu surumde logolar EXE'NIN ICINE GOMULUDUR (pi3d_logo.py):
    yanindaki klasorden silinemez, degistirilemez. logo/ klasoru de
    pakete konur ama program once gomulu olani kullanir.
    Logosuz surumde gomulu modul ve logo klasoru pakete hic girmez,
    exe'nin kendi ikonu da olmaz; basliktaki serit yalnizca "Pi3D"
    yazar.

Neden onedir (tek klasor), onefile degil:
OpenCascade kutuphanesi ~700 MB. Tek dosyaya sikistirilirsa program her
acilista bunu gecici klasore acar; acilis 1-2 dakika surer ve disk iki kat
yer kaplar. Tek klasor surumu aninda acilir.
"""
import os

from PyInstaller.utils.hooks import collect_all, collect_data_files

# PI3D_LOGO=0 / yok / hayir  -> logosuz "FIRMA" surumu.
#
# Iki surum vardir ve birbirinin yerine gecer:
#   1 = PI3D   Pi3D + PiVision logolari gomulu, FIRMA ANTETI YOK
#   2 = FIRMA  Pi3D logolari yok, bunun yerine antet/ klasorundeki
#              firma anteti pakete girer ve paftalarda kullanilir
# Firmanin kendi anteti varken Pi3D'nin logosunu da basmak dogru
# degildir: resim firmanindir.
LOGOLU = os.environ.get("PI3D_LOGO", "1").strip().lower() not in (
    "0", "yok", "hayir", "hayır", "no", "false", "off")
ANTETLI = not LOGOLU
if ANTETLI and not os.path.isdir("antet"):
    ANTETLI = False
    print("pi3d.spec: antet/ klasoru yok - program antetsiz calisacak.")
print(f"pi3d.spec: {'PI3D (logolu, antetsiz)' if LOGOLU else 'FIRMA (antetli)'}"
      f" surum derleniyor (PI3D_LOGO={os.environ.get('PI3D_LOGO', '1')})")

# OCP (OpenCascade) saf .pyd + yanindaki DLL'lerdir; PyInstaller bunlari
# kendiliginden bulamaz, hepsini acikca toplamak gerekir.
#
# on_error="ignore" NEDEN:
# OCP'de her modulun icinde kendi adiyla bir sinif vardir; ornegin
# OCP/TopoDS/__init__.py icinde "TopoDS" adinda bir ad bulunur.
# PyInstaller alt modulleri gezerken bunu da bir alt modul sanip
# "OCP.TopoDS.TopoDS" diye import etmeye calisir ve
#   ModuleNotFoundError: No module named 'OCP.TopoDS.OCP'
# uyarisini basar. Uyaridir, hata degil: toplama devam eder, OCP.TopoDS
# dahil 321 modulun hepsi pakete girer. on_error="ignore" yalnizca bu
# yaniltici satiri susturur, toplanan dosyalari DEGISTIRMEZ.
# include_py_files=False: collect_all varsayilani paketlerin .py
# kaynaklarini da VERI olarak kopyaliyordu (_internal/ezdxf/*.py,
# _internal/OCP/*.py - 666 dosya). Moduller zaten derlenmis olarak PYZ'de;
# pakette hicbir .py bulunmaz (exebuild.py bariyeri bunu denetler).
ocp_bin, ocp_data, ocp_gizli = collect_all("OCP", include_py_files=False, on_error="ignore")
ezdxf_bin, ezdxf_data, ezdxf_gizli = collect_all("ezdxf", include_py_files=False, on_error="ignore")
# AI kontrolü (pf10_ai) isteğe bağlıdır: 'anthropic' paketi derleyen
# makinede kuruluysa exe'ye girer, değilse program AI'sız çalışır.
# pf10_ai onu yalnız bir fonksiyonun İÇİNDE import eder; PyInstaller
# kendiliğinden göremez.
try:
    import anthropic  # noqa: F401
    AI_GIZLI = ["anthropic"]
except ImportError:
    AI_GIZLI = []

a = Analysis(
    ["pf3_gui.py"],
    pathex=["."],
    binaries=ocp_bin + ezdxf_bin,
    # Logolu surumde logo/ klasoru de pakete girer (exe'de sys._MEIPASS
    # altinda ayni adla acilir), ama program once pi3d_logo icindeki
    # gomulu kopyayi kullanir.
    datas=ocp_data + ezdxf_data + collect_data_files("matplotlib")
          + ([("logo/*", "logo")] if LOGOLU else [])
          + ([("antet/*", "antet")] if ANTETLI else [])
          # Yardim menusu ve malzeme sihirbazi bunlari arar: CATIA makrosu
          # (sihirbaz "Makroyu kaydet" ile kullaniciya verir), kullanim
          # kilavuzu (F1) ve surum notu (Hakkinda).
          + [(d, ".") for d in ("catia_malzeme_cikar.CATScript",
                                "KULLANIM.md", "SURUM.txt")
             if os.path.isfile(d)]
          # Standart urun katalogu: ilk calismada exe'nin yanina kopyalanir,
          # kullanici STEP ve resim ekler.
          + [(os.path.join(k, "*"), k.replace("\\", "/")) for k, _d, f in
             os.walk("STANDART_KATALOG") if f],
    # matplotlib arka uclarini ADIYLA yukler (fig.savefig bir .pdf
    # gorunce backend_pdf'i calisma aninda import eder), bu yuzden
    # PyInstaller onlari kendiliginden bulamaz. Yalniz backend_agg
    # yaziliydi; exe'de PDF basimi
    #   No module named 'matplotlib.backends.backend_pdf'
    # diye patliyordu.
    #
    # Arka uclarin HEPSI toplanmaz (collect_submodules): o liste Qt,
    # GTK ve wx arka uclarini da getiriyor, onlar da PyQt/PyGObject
    # suruklemeye calisir. Programin kullandigi UC tanesi yeter -
    # ekrana Agg, PDF'e backend_pdf, PNG'ye yine Agg.
    hiddenimports=ocp_gizli + ezdxf_gizli + [
        "pf3_olcu", "pf4_pafta", "pf5_antet", "pf6_malzeme", "pf7_is", "pf8_tani", "pf9_excel",
        "pf10_ai", "pf11_yapi", "pf12_katalog", "pf13_aile", "pf14_kaynak", "pf15_bom_esle", "pf16_acinim3",
        "pf1_referans", "pf17_lisans",
        # lisans imzasi: cryptography varsa onunla (Rust baglamasi
        # PyInstaller'in goremedigi bir yoldan yuklenir), yoksa pf17'nin saf
        # Python Ed25519 dogrulamasi devreye girer
        "cryptography.hazmat.primitives.asymmetric.ed25519",
        "cryptography.hazmat.bindings._rust",
        "matplotlib.backends.backend_agg",
        "matplotlib.backends.backend_pdf",
        "matplotlib.backends.backend_svg",
    ] + AI_GIZLI + (["pi3d_logo"] if LOGOLU else []),
    hookspath=[],
    runtime_hooks=[],
    # Programin kullanmadigi agir paketler disarida kalsin.
    excludes=["vtk", "trame", "casadi", "numba", "llvmlite", "scipy",
              "pandas", "sklearn", "tensorflow", "cv2", "IPython",
              "notebook", "PyQt5", "PySide2", "PySide6", "wx"]
             + ([] if LOGOLU else ["pi3d_logo"]),
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Pi3D",
    # Pencereli program: arkada siyah konsol acilmasin.
    # EXE hic acilmazsa burayi True yapip yeniden derleyin; baslangic
    # hatasi konsola yazilir ve sebebi gorunur.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    # Gorev cubugunda ve dosya gezgininde gorunen ikon.
    icon=("logo/pi3d.ico" if LOGOLU else None),
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="Pi3D",
)
