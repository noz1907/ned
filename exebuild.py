# -*- coding: utf-8 -*-
"""Pi3D — EXE DERLEME ve PAKETLEME (PiProduct exebuild ile aynı düzen)
================================================================
    py exebuild.py            (tek sürüm; antet lisansa göre çalışma anında seçilir)
    py exebuild.py 1 --kurulum-yok

Adımlar:
  1. sürüm pf7_is.PI3D_SURUM'dan okunur (tek kaynak), version.json yazılır
  2. PyInstaller pi3d.spec  → dist\\Pi3D\\Pi3D.exe (+ _internal)
  3. dağıtım klasörü dist\\Pi3D_v<sürüm>\\Pi3D\\: exe klasörü + müşteri
     belgeleri (KULLANIM.md, SURUM.txt, OKUBENI.txt) + version.json
  4. BARİYER: pakette .py / .pyw / .spec / .pyc / __pycache__ / anahtar /
     lisans masası / firma CAD dosyası OLMAZ; bulunursa derleme DURUR
  5. MANIFEST.txt (SHA-256) + dist\\Pi3D_v<sürüm>.zip
  6. Inno Setup (ISCC) varsa installer\\Output\\Pi3D_Kurulum_v<sürüm>.exe

Müşteriye giden: kurulum .exe'si (ya da zip). Kaynak kod, lisans masası ve
özel anahtar hiçbir zaman pakete girmez.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

BD = os.path.dirname(os.path.abspath(__file__))
os.chdir(BD)
sys.path.insert(0, BD)

YASAK_UZANTI = (".py", ".pyw", ".pyc", ".pyo", ".spec", ".key", ".pkl",
                ".catpart", ".catproduct", ".stp", ".step", ".xls", ".xlsx")
YASAK_AD = ("__pycache__", "lisans_masasi", "keys", "pivision_private", ".git",
            "test", "tanitim", "ornek")
IZINLI_STP_KLASOR = ("STANDART_KATALOG",)      # katalog STEP'leri müşteriye gider


def surum():
    import pf7_is
    return pf7_is.PI3D_SURUM


def version_json(ver, tur):
    import datetime
    v = {"product": "Pi3D", "version": ver, "build": tur,
         "built": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
    with open("version.json", "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=2)
    return v


def sor_tur(argv):
    """TEK sürüm vardır. Antet derlemede değil ÇALIŞMA ANINDA, lisansa göre
    seçilir: deneme lisansında Pi3D / PiVision anteti; tam lisansta Yardım >
    Firma anteti ile verilen A3 antet DXF'i (ayara kaydedilir, değiştirilir).
    Eski "1 / 2" seçimi geriye uyumluluk için kabul edilir, yok sayılır."""
    if argv and argv[0] in ("1", "2"):
        print("  (not: 1 / 2 seçimi kalktı - antet lisansa göre çalışma anında seçilir)")
    return "1"


def pyinstaller(tur):
    ortam = dict(os.environ, PI3D_LOGO="0" if tur == "2" else "1")
    for k in ("build", os.path.join("dist", "Pi3D")):
        shutil.rmtree(k, ignore_errors=True)
    r = subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                        "pi3d.spec"], env=ortam)
    if r.returncode != 0:
        raise SystemExit("PyInstaller başarısız - yukarıdaki çıktıya bakın.")
    exe = os.path.join("dist", "Pi3D", "Pi3D.exe" if os.name == "nt" else "Pi3D")
    if not os.path.isfile(exe):
        raise SystemExit(f"Derleme çıktısı yok: {exe}")
    return exe


def dagitim(ver, tur):
    kok = os.path.join("dist", f"Pi3D_v{ver}")
    hedef = os.path.join(kok, "Pi3D")
    shutil.rmtree(kok, ignore_errors=True)
    shutil.copytree(os.path.join("dist", "Pi3D"), hedef)
    for d in ("KULLANIM.md", "SURUM.txt", "CATIA_MALZEME.md", "version.json"):
        if os.path.isfile(d):
            shutil.copy2(d, hedef)
    if os.path.isfile(os.path.join("logo", "pi3d.ico")) and tur == "1":
        shutil.copy2(os.path.join("logo", "pi3d.ico"), os.path.join(hedef, "Pi3D.ico"))
    with open(os.path.join(hedef, "OKUBENI.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(
            f"Pi3D v{ver} - PiVision\n"
            "==============================\n\n"
            "BASLATMA : Pi3D.exe (masaustu kisayolu kurulumla gelir)\n"
            "LISANS   : Program makineye kilitlidir. Yardim > Lisans ekranindaki\n"
            "           PI3D-XXXX-XXXX-XXXX makine kimligini PiVision'a gonderin;\n"
            "           gelen pi3d.lic dosyasini ayni ekrandan 'Lisans dosyasini yukle'\n"
            "           ile secin (ya da Pi3D.exe'nin yanina kopyalayin).\n"
            "DENEME   : deneme lisansi 8 farkli model isler; sonra tam lisans gerekir.\n"
            "KILAVUZ  : KULLANIM.md (programda F1), surum notlari SURUM.txt\n"
            "DESTEK   : PiVision - Industrial Smart Vision System\n")
    return kok, hedef


def bariyer(hedef):
    """5. bariyer: paketin içinde kaynak kod / anahtar / firma dosyası yok."""
    kacak = []
    for kok, dizinler, dosyalar in os.walk(hedef):
        rel = os.path.relpath(kok, hedef)
        for dz in list(dizinler):
            if dz.lower() in YASAK_AD:
                kacak.append(os.path.join(rel, dz) + os.sep)
                dizinler.remove(dz)
        for d in dosyalar:
            alt = d.lower()
            yol = os.path.join(rel, d)
            if alt.endswith((".stp", ".step")) and any(k in yol for k in IZINLI_STP_KLASOR):
                continue
            if alt.endswith(YASAK_UZANTI) or any(y in alt for y in ("pivision_private",)):
                kacak.append(yol)
    return kacak


def manifest(hedef, ver):
    satirlar = []
    for kok, _d, dosyalar in os.walk(hedef):
        for d in sorted(dosyalar):
            if d == "MANIFEST.txt":
                continue
            yol = os.path.join(kok, d)
            h = hashlib.sha256()
            with open(yol, "rb") as f:
                for p in iter(lambda: f.read(1 << 20), b""):
                    h.update(p)
            satirlar.append(f"{h.hexdigest()}  {os.path.relpath(yol, hedef).replace(os.sep, '/')}")
    with open(os.path.join(hedef, "MANIFEST.txt"), "w", encoding="utf-8") as f:
        f.write(f"Pi3D v{ver} - {len(satirlar)} dosya (SHA-256)\n" + "\n".join(satirlar) + "\n")
    return len(satirlar)


def zipla(kok, ver):
    zy = os.path.join("dist", f"Pi3D_v{ver}.zip")
    with zipfile.ZipFile(zy, "w", zipfile.ZIP_DEFLATED) as z:
        for k, _d, dosyalar in os.walk(kok):
            for d in dosyalar:
                yol = os.path.join(k, d)
                z.write(yol, os.path.relpath(yol, kok))
    return zy


def iscc():
    for p in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        for s in ("Inno Setup 6", "Inno Setup 5"):
            y = os.path.join(p, s, "ISCC.exe")
            if p and os.path.isfile(y):
                return y
    return None


def kurulum(ver, hedef):
    i = iscc()
    if not i:
        print("  Inno Setup bulunamadı (https://jrsoftware.org/isdl.php); kurulum .exe'si atlandı.")
        return None
    r = subprocess.run([i, os.path.join("installer", "Pi3D_Setup.iss"),
                        f"/DMyVer={ver}", f"/DMySrc={os.path.abspath(hedef)}"])
    if r.returncode != 0:
        raise SystemExit("Inno Setup derlemesi başarısız.")
    return os.path.join("installer", "Output", f"Pi3D_Kurulum_v{ver}.exe")


def main(argv):
    argv = list(argv)
    kurulum_yok = "--kurulum-yok" in argv
    argv = [a for a in argv if not a.startswith("--")]
    ver = surum()
    tur = sor_tur(argv)
    print(f"\n  Pi3D v{ver}  (tek sürüm: antet lisansa göre çalışma anında)\n")
    version_json(ver, "PI3D")
    print("  [1/5] PyInstaller...")
    pyinstaller(tur)
    print("  [2/5] dağıtım klasörü...")
    kok, hedef = dagitim(ver, tur)
    print("  [3/5] bariyer: kaynak kod / anahtar denetimi...")
    kacak = bariyer(hedef)
    if kacak:
        print("  DURDU - pakette olmaması gereken dosyalar:")
        for k in kacak[:40]:
            print("     ", k)
        raise SystemExit(1)
    print("  [4/5] manifest + zip...")
    n = manifest(hedef, ver)
    zy = zipla(kok, ver)
    print(f"        {n} dosya, {zy}")
    cik = None
    if not kurulum_yok:
        print("  [5/5] kurulum sihirbazı (Inno Setup)...")
        cik = kurulum(ver, hedef)
    print("\n  HAZIR")
    print(f"    klasör : {hedef}")
    print(f"    zip    : {zy}")
    if cik:
        print(f"    kurulum: {cik}   <- müşteriye giden TEK dosya")
    print("  Kaynak kod, lisans masası ve özel anahtar pakette YOK (bariyer geçti).")


if __name__ == "__main__":
    main(sys.argv[1:])
