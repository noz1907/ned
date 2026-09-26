import mss
import numpy as np
import cv2
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import tempfile
import shutil
import time
import os
import sys


def varsayilan_klasor():
    """Var olan ilk masaüstü klasörünü döndürür (OneDrive / Türkçe Windows dahil)."""
    ev = os.path.expanduser("~")
    adaylar = [
        os.path.join(os.environ.get("OneDrive", ""), "Desktop") if os.environ.get("OneDrive") else "",
        os.path.join(ev, "Desktop"),
        os.path.join(ev, "OneDrive", "Desktop"),
        os.path.join(ev, "Masaüstü"),
    ]
    for yol in adaylar:
        if yol and os.path.isdir(yol):
            return yol
    return ev


def ascii_klasor(klasor):
    """OpenCV, Windows'ta Türkçe karakter (ü, ş, ı...) içeren yollara yazamaz.
    Yazılabilir, sadece ASCII karakterli bir klasör yolu döndürür."""
    if klasor.isascii():
        return klasor
    if sys.platform == "win32":
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(klasor, buf, 1024) and buf.value.isascii():
            return buf.value
    for aday in (tempfile.gettempdir(), os.environ.get("PUBLIC", ""), "C:\\Users\\Public"):
        if aday and aday.isascii() and os.path.isdir(aday):
            return aday
    return klasor


class EkranKayitProgrami:
    def __init__(self, root):
        self.root = root
        self.root.title("2K Ekran Kayıt Programı")
        self.root.geometry("450x300")
        self.root.resizable(False, False)

        self.kayit_aktif = False
        self.kayit_thread = None
        self.hata_mesaji = None
        self.kayit_yolu = None

        # Arayüz Değişkenleri
        self.dosya_adi = tk.StringVar(value="kayit")
        self.klasor_yolu = tk.StringVar(value=varsayilan_klasor())
        self.format_secimi = tk.StringVar(value="mp4")

        self.arayuz_olustur()
        self.root.protocol("WM_DELETE_WINDOW", self.kapat)

    def arayuz_olustur(self):
        # Dosya Adı
        tk.Label(self.root, text="Dosya Adı:").pack(pady=(10, 0))
        tk.Entry(self.root, textvariable=self.dosya_adi, width=40).pack(pady=5)

        # Klasör Seçimi
        tk.Label(self.root, text="Kayıt Klasörü:").pack()
        klasor_frame = tk.Frame(self.root)
        klasor_frame.pack(pady=5)
        tk.Entry(klasor_frame, textvariable=self.klasor_yolu, width=30).pack(side=tk.LEFT)
        tk.Button(klasor_frame, text="Seç", command=self.klasor_sec, width=5).pack(side=tk.LEFT, padx=5)

        # Format Seçimi
        tk.Label(self.root, text="Video Formatı:").pack()
        format_frame = tk.Frame(self.root)
        format_frame.pack(pady=5)
        tk.Radiobutton(format_frame, text="MP4", variable=self.format_secimi, value="mp4").pack(side=tk.LEFT)
        tk.Radiobutton(format_frame, text="AVI", variable=self.format_secimi, value="avi").pack(side=tk.LEFT)
        tk.Radiobutton(format_frame, text="MOV", variable=self.format_secimi, value="mov").pack(side=tk.LEFT)

        # Çözünürlük Bilgisi
        tk.Label(self.root, text="Çözünürlük: 2K (2560x1440)", fg="blue").pack(pady=5)

        # Butonlar
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=20)
        self.btn_baslat = tk.Button(btn_frame, text="● KAYDI BAŞLAT", bg="green", fg="white", width=15, command=self.kaydi_baslat)
        self.btn_baslat.pack(side=tk.LEFT, padx=10)

        self.btn_durdur = tk.Button(btn_frame, text="■ KAYDI DURDUR", bg="red", fg="white", width=15, command=self.kaydi_durdur, state=tk.DISABLED)
        self.btn_durdur.pack(side=tk.LEFT, padx=10)

    def klasor_sec(self):
        yol = filedialog.askdirectory()
        if yol:
            self.klasor_yolu.set(yol)

    def kaydi_baslat(self):
        dosya_adi = self.dosya_adi.get().strip()
        klasor = self.klasor_yolu.get().strip()
        if not dosya_adi:
            messagebox.showerror("Hata", "Lütfen bir dosya adı girin!")
            return
        if not os.path.isdir(klasor):
            messagebox.showerror("Hata", f"Klasör bulunamadı:\n{klasor}")
            return

        # Tk değişkenleri sadece ana thread'de okunur, kayıt thread'ine değer olarak verilir
        fmt = self.format_secimi.get()
        self.kayit_yolu = os.path.join(klasor, f"{dosya_adi}.{fmt}")
        self.hata_mesaji = None
        self.kayit_aktif = True
        self.btn_baslat.config(state=tk.DISABLED)
        self.btn_durdur.config(state=tk.NORMAL)

        # Kayıt işlemini arka planda (thread) başlat
        self.kayit_thread = threading.Thread(target=self.ekrani_kaydet, args=(self.kayit_yolu, fmt), daemon=True)
        self.kayit_thread.start()
        self.root.after(200, self.kayit_kontrol)

    def kaydi_durdur(self):
        self.kayit_aktif = False
        self.btn_durdur.config(state=tk.DISABLED)

    def kayit_kontrol(self):
        # Thread bitene (dosya tamamen yazılana) kadar bekle, sonra sonucu göster
        if self.kayit_thread.is_alive():
            self.root.after(200, self.kayit_kontrol)
            return
        self.kayit_aktif = False
        self.btn_baslat.config(state=tk.NORMAL)
        self.btn_durdur.config(state=tk.DISABLED)
        if self.hata_mesaji:
            messagebox.showerror("Hata", self.hata_mesaji)
        else:
            messagebox.showinfo("Bilgi", f"Kayıt tamamlandı:\n{self.kayit_yolu}")

    def kapat(self):
        if self.kayit_thread and self.kayit_thread.is_alive():
            self.kayit_aktif = False
            self.kayit_thread.join(timeout=10)
        self.root.destroy()

    def ekrani_kaydet(self, tam_yol, fmt):
        # Bu fonksiyon arka plan thread'inde çalışır: burada tkinter çağrısı YAPILMAZ.
        try:
            self._kaydet(tam_yol, fmt)
        except Exception as e:
            self.hata_mesaji = f"Kayıt sırasında hata oluştu:\n{e}"

    def _kaydet(self, tam_yol, fmt):
        # 2K Çözünürlük Ayarları
        TARGET_WIDTH = 2560
        TARGET_HEIGHT = 1440
        FPS = 30.0  # Saniyedeki kare sayısı

        # OpenCV Codec Ayarları (Formatlara göre)
        codecler = {"mp4": ["mp4v"], "mov": ["mp4v"], "avi": ["XVID", "MJPG"]}[fmt]

        # Önce ASCII bir geçici dosyaya yaz, bitince asıl yere taşı
        gecici_yol = os.path.join(ascii_klasor(os.path.dirname(tam_yol)),
                                  f"_ekran_kayit_{int(time.time())}.{fmt}")

        out = None
        for codec in codecler:
            out = cv2.VideoWriter(gecici_yol, cv2.VideoWriter_fourcc(*codec), FPS, (TARGET_WIDTH, TARGET_HEIGHT))
            if out.isOpened():
                break
            out.release()
            out = None
        if out is None:
            self.hata_mesaji = "Video dosyası oluşturulamadı. Formatı veya klasör izinlerini kontrol edin."
            return

        try:
            # mss nesnesi, kullanıldığı thread içinde oluşturulmalı
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Ana ekran ([0] tüm ekranların birleşimidir)

                baslangic = time.time()
                yazilan_kare = 0
                while self.kayit_aktif:
                    # Ekran görüntüsü al, BGRA'dan BGR'ye çevir (OpenCV için)
                    img = np.array(sct.grab(monitor))
                    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                    # Görüntüyü 2K (2560x1440) boyutuna ölçekle
                    if img_bgr.shape[1] != TARGET_WIDTH or img_bgr.shape[0] != TARGET_HEIGHT:
                        img_bgr = cv2.resize(img_bgr, (TARGET_WIDTH, TARGET_HEIGHT))

                    # Bilgisayar 30 FPS yakalayamazsa video hızlı oynamasın diye
                    # geçen gerçek süreye göre gerektiği kadar kare yaz
                    hedef_kare = int((time.time() - baslangic) * FPS) + 1
                    while yazilan_kare < hedef_kare:
                        out.write(img_bgr)
                        yazilan_kare += 1

                    # FPS'i sabitlemek için bekle
                    sonraki = baslangic + yazilan_kare / FPS
                    bekle = sonraki - time.time()
                    if bekle > 0:
                        time.sleep(bekle)
        finally:
            # İşlem bittiğinde dosyayı serbest bırak
            out.release()

        shutil.move(gecici_yol, tam_yol)


if __name__ == "__main__":
    root = tk.Tk()
    app = EkranKayitProgrami(root)
    root.mainloop()
