# -*- coding: utf-8 -*-
"""Arayuzde CAGRILAN ama TANIMLANMAYAN yontem var mi?

Bu tam olarak sahada cikan hatayi yakalar: _motor_geldi icinde
self._kfaktoru_tazele() cagrisi vardi ama yontemin kendisi yoktu.
AttributeError kuyruk dongusunu olduruyor, motor isini bitiriyor ama
sonucu kimse almiyordu; ekranda "STEP okunuyor" yazili kaliyordu.

tkinter gerektirmez, saf kaynak kodu incelemesidir.
"""
import ast, os, sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def denetle(yol):
    agac = ast.parse(open(yol, encoding="utf-8").read(), yol)
    hata = []
    for sinif in [d for d in ast.walk(agac) if isinstance(d, ast.ClassDef)]:
        tanim = {d.name for d in sinif.body
                 if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef))}
        # Miras alinan siniflarin yontemleri burada gorunmez; bilinenleri
        # ekle ki yanlis alarm cikmasin.
        tanim |= {"pack", "grid", "place", "after", "after_cancel", "bind",
                  "configure", "winfo_width", "winfo_height", "update",
                  "update_idletasks", "destroy", "quit", "columnconfigure",
                  "rowconfigure", "master", "focus_set", "clipboard_clear",
                  "clipboard_append", "register", "nametowidget",
                  # tk.Canvas'tan gelenler
                  "delete", "create_text", "create_line", "create_polygon",
                  "create_oval", "create_rectangle", "create_image",
                  "coords", "itemconfig", "bbox", "canvasx", "canvasy",
                  # tk.Tk / Toplevel'den gelenler
                  "title", "geometry", "minsize", "maxsize", "iconbitmap",
                  "protocol", "resizable", "attributes", "state",
                  "mainloop", "withdraw", "deiconify", "wm_title"}
        # Kendine atanan alanlar da yontem gibi cagrilabilir (callback).
        for d in ast.walk(sinif):
            if isinstance(d, ast.Attribute) and isinstance(d.ctx, ast.Store) \
               and isinstance(d.value, ast.Name) and d.value.id == "self":
                tanim.add(d.attr)
        for d in ast.walk(sinif):
            if not isinstance(d, ast.Call):
                continue
            f = d.func
            if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                    and f.value.id == "self"):
                continue
            if f.attr not in tanim:
                hata.append((sinif.name, f.attr, f.lineno))
    return hata


tum = []
for ad in ("pf3_gui.py", "pf_gui.py"):
    y = os.path.join(KOK, ad)
    if not os.path.isfile(y):
        continue
    h = denetle(y)
    print(f"{ad:14s} {'TAMAM' if not h else 'HATA'}  "
          f"({len(h)} tanimsiz cagri)")
    for sinif, adi, satir in h:
        print(f"    {ad}:{satir}  {sinif}.{adi}()  -> boyle bir yontem yok")
    tum += h
print("\nSONUC:", "tum cagrilarin karsiligi var" if not tum else "TANIMSIZ CAGRI VAR")
sys.exit(1 if tum else 0)
