# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller tarifi - PiFikstur'u tek klasorluk calistirilabilir hale getirir.

    pyinstaller pifikstur.spec

Cikti:  dist/PiFikstur/PiFikstur.exe   (Windows)
        dist/PiFikstur/PiFikstur       (Linux/macOS)

Neden onedir (tek klasor), onefile degil:
OpenCascade kutuphanesi ~700 MB. Tek dosyaya sikistirilirsa program her
acilista bunu gecici klasore acar; acilis 1-2 dakika surer ve disk iki kat
yer kaplar. Tek klasor surumu aninda acilir.
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files

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
ocp_bin, ocp_data, ocp_gizli = collect_all("OCP", on_error="ignore")
ezdxf_bin, ezdxf_data, ezdxf_gizli = collect_all("ezdxf", on_error="ignore")

a = Analysis(
    ["pf3_gui.py"],
    pathex=["."],
    binaries=ocp_bin + ezdxf_bin,
    datas=ocp_data + ezdxf_data + collect_data_files("matplotlib"),
    hiddenimports=ocp_gizli + ezdxf_gizli + [
        "pf3_olcu", "pf1_referans",
        "matplotlib.backends.backend_agg",
    ],
    hookspath=[],
    runtime_hooks=[],
    # Programin kullanmadigi agir paketler disarida kalsin.
    excludes=["vtk", "trame", "casadi", "numba", "llvmlite", "scipy",
              "pandas", "sklearn", "tensorflow", "cv2", "IPython",
              "notebook", "PyQt5", "PySide2", "PySide6", "wx"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="PiFikstur",
    # Pencereli program: arkada siyah konsol acilmasin.
    # EXE hic acilmazsa burayi True yapip yeniden derleyin; baslangic
    # hatasi konsola yazilir ve sebebi gorunur.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="PiFikstur",
)
