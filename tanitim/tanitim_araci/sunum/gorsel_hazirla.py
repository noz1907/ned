# -*- coding: utf-8 -*-
"""out/g klasöründeki logoları sunuma hazırlar (fon.js'ten SONRA çalıştırın).
  urun.png      -> urun_k.png (300 px; PowerPoint her slayta ayrı gömer, küçük olmalı)
  pivision.png  -> pivision_fon.png (2000 px filigran), pivision_k.png (1400 px)
  fon.png       -> fon.jpg (PowerPoint arka planı)"""
import os
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
g = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "g")
Image.open(f"{g}/urun.png").resize((300, 300), Image.LANCZOS).save(f"{g}/urun_k.png", optimize=True)
p = Image.open(f"{g}/pivision.png")
if p.getbbox():
    p = p.crop(p.getbbox())
a = p.copy(); a.thumbnail((2000, 2000)); a.save(f"{g}/pivision_fon.png")
b = p.copy(); b.thumbnail((1400, 1400)); b.save(f"{g}/pivision_k.png", optimize=True)
if os.path.isfile(f"{g}/fon.png"):
    Image.open(f"{g}/fon.png").convert("RGB").save(f"{g}/fon.jpg", quality=85)
print("hazır")
