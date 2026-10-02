"""SANAL tanıtım / test modeli: kaynaklı konsol montajı (hiçbir firmanın verisi değil).
Kullanım: python test/sanal_tanitim_modeli.py [çıktı klasörü]  ->  SANAL_KONSOL_MONTAJI.stp
Sonra:    python pf3_olcu.py <klasör>/SANAL_KONSOL_MONTAJI.stp -o <klasör>/cikti --acinim OTO --kaynak-resmi --malzeme celik
Parçalar: taban plakası (düz sac), 2 L braket (bükümlü), çok yönlü bükümlü
kutu braket (3B açınım), dik sac, somunlar; kaynak dikişleri üçgen prizma."""
import cadquery as cq, os, math
import sys
D = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
os.makedirs(D, exist_ok=True)

def ucgen(a, b, c, uzunluk, yon):
    """Kaynak dikişi: a-b-c üçgen kesit (düzlemde), yon ekseni boyunca uzunluk."""
    pl = {"x": "YZ", "y": "XZ", "z": "XY"}[yon]
    w = cq.Workplane(pl).polyline([a, b, c]).close().extrude(uzunluk)
    return w

# ---- taban plakası 320 x 200 x 6, 4 delik Ø11, 2 slot
taban = (cq.Workplane("XY").box(320, 200, 6, centered=(False, False, False))
         .faces(">Z").workplane()
         .pushPoints([(25, 25), (295, 25), (25, 175), (295, 175)]).hole(11)
         .faces(">Z").workplane().pushPoints([(160, 40), (160, 160)]).slot2D(40, 12, 0).cutThruAll())

# ---- L braket (3 mm, iç R 3): taban kanadı 120x60, dik kanat 120x90, 2 delik
def l_braket(t=3.0, r=3.0, boy=120.0, k1=60.0, k2=90.0):
    """Daha sade kurulum: XY düz kanat (y 0..k1-r-t), bükümden sonra Z'ye dik kanat."""
    duz = cq.Workplane("XY").box(boy, k1 - r - t, t, centered=(False, False, False))
    # büküm: eksen X, merkez (y = k1-r-t, z = r+t)
    halka = (cq.Workplane("YZ").center(k1 - r - t, r + t).circle(r + t).circle(r).extrude(boy))
    ceyrek = halka.intersect(cq.Workplane("YZ").center(k1 - r - t + (r + t) / 2.0, (r + t) / 2.0)
                             .rect(r + t, r + t).extrude(boy))
    dik = cq.Workplane("XY").box(boy, t, k2 - r - t, centered=(False, False, False)).translate((0, k1 - t, r + t))
    sh = duz.union(ceyrek).union(dik)
    sh = sh.faces(">Y").workplane(centerOption="CenterOfBoundBox").pushPoints([(-35, 15), (35, 15)]).hole(9)
    sh = sh.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints([(-40, 0), (40, 0)]).hole(11)
    return sh

brk = l_braket()
bb = brk.val().BoundingBox()
brk_sol = brk.translate((40, 6 - 0, 6))               # plakanın üstüne, y=6'dan başlar
brk_sag = brk.mirror("XZ").translate((40, 200 - 6 + 0, 6))  # karşı kenar (y=194'e aynalı)

# ---- çok yönlü bükümlü kutu braket (3B açınım): gövde + X kanadı + Y kanadı
def kutu_braket(t=2.0, r=3.0, W=90.0, L=110.0, h1=40.0, h2=35.0):
    gov = cq.Workplane("XY").box(L, W, t, centered=(False, False, False))
    # kanat 1: x=L ucunda yukarı (eksen Y)
    h1k = (cq.Workplane("XZ").center(L, t + r).circle(r + t).circle(r).extrude(-(W - h2 - r - t))
           .intersect(cq.Workplane("XZ").center(L + (r + t) / 2.0, t + r - (r + t) / 2.0).rect(r + t, r + t).extrude(-(W - h2 - r - t))))
    k1 = cq.Workplane("XY").box(t, W - h2 - r - t, h1, centered=(False, False, False)).translate((L + r, 0, t + r))
    # kanat 2: y=W ucunda yukarı (eksen X)
    h2k = (cq.Workplane("YZ").center(W, t + r).circle(r + t).circle(r).extrude(L - r - t)
           .intersect(cq.Workplane("YZ").center(W + (r + t) / 2.0, t + r - (r + t) / 2.0).rect(r + t, r + t).extrude(L - r - t)))
    k2 = cq.Workplane("XY").box(L - r - t, t, h2, centered=(False, False, False)).translate((0, W + r, t + r))
    sh = gov.union(h1k).union(k1).union(h2k).union(k2)
    sh = sh.faces("<Z").workplane(centerOption="CenterOfBoundBox").pushPoints([(-25, -15), (25, -15)]).hole(9)
    sh = sh.faces(">X").workplane(centerOption="CenterOfBoundBox").pushPoints([(0, 5)]).slot2D(24, 9, 90).cutThruAll()
    return sh
kb = kutu_braket().translate((100, 50, 6))

# ---- dik sac 4 mm: 140 x 100, iki delik; plakanın arka kenarına kaynaklı
dik = (cq.Workplane("XZ").box(140, 100, 4, centered=(False, False, False))
       .faces(">Y").workplane(centerOption="CenterOfBoundBox").pushPoints([(-40, 20), (40, 20)]).hole(13))
dik = dik.translate((30, 6, 6))      # XZ box: y -4..0 -> translate y=6 -> plaka iç kenarı? y 2..6
dik = dik.translate((0, 190, 0))     # arka kenar y=192..196
# ---- somunlar M10 (altıgen 17 AF, 8 mm, delik 10)
def somun():
    return (cq.Workplane("XY").polygon(6, 17 / math.cos(math.pi / 6)).extrude(8)
            .faces(">Z").workplane().hole(10))
somunlar = [somun().translate((x, y, 6)) for x, y in ((25, 25), (295, 25), (25, 175), (295, 175))]

# ---- kaynak dikişleri (köşe kaynağı, a = 3/√2 ≈ 2,1): üçgen prizmalar
kay = []
# L braket sol: dik kanat dış yüzü y = 6+ (k1-t) + t = 6+60 = 66? dik kanat y 6+57..6+60 -> dış yüz y=66; plaka üstü z=6; kaynak plaka-braket birleşimi: braket düz kanadı plakaya oturuyor (z=6..9); kenar y=6
# dikiş: braketin düz kanadının dış kenarı (y=6) boyunca - 3x3 üçgen, x boyunca 40..160 ortasında 60 mm
kay.append(ucgen((6, 6), (6 - 3, 6), (6, 9), 60, "x").translate((70, 0, 0)))          # sol braket, y=6 kenarı
kay.append(ucgen((194, 6), (197, 6), (194, 9), 60, "x").translate((70, 0, 0)))        # sağ braket, y=194 kenarı
# kutu braket: gövde kenarı x=100 (y 50..140) ve y=50 (x 100..210) - 2 dikiş
kay.append(ucgen((100, 6), (97, 6), (100, 9), 60, "y").translate((0, 65, 0)))
kay.append(ucgen((50, 6), (47, 6), (50, 9), 70, "x").translate((120, 0, 0)))
# dik sac: ön yüzü y=192, plaka üstü z=6, x 30..170 -> iki dikiş 40 mm
kay.append(ucgen((192, 6), (189, 6), (192, 9), 40, "x").translate((40, 0, 0)))
kay.append(ucgen((192, 6), (189, 6), (192, 9), 40, "x").translate((120, 0, 0)))

asm = cq.Assembly(name="SANAL_KONSOL_MONTAJI")
kg = cq.Assembly(name="KONSOL_KAYNAKLI_GRUP")
kg.add(taban, name="TABAN_PLAKASI_320x200x6", color=cq.Color(0.6, 0.65, 0.7))
kg.add(brk_sol, name="L_BRAKET_SOL_t3", color=cq.Color(0.55, 0.6, 0.7))
kg.add(brk_sag, name="L_BRAKET_SAG_t3", color=cq.Color(0.55, 0.6, 0.7))
kg.add(kb, name="KUTU_BRAKET_t2", color=cq.Color(0.5, 0.6, 0.75))
kg.add(dik, name="DIK_SAC_140x100x4", color=cq.Color(0.6, 0.6, 0.65))
for i, k in enumerate(kay, 1):
    kg.add(k, name=f"KAYNAK_DIKISI_{i}", color=cq.Color(0.9, 0.3, 0.2))
asm.add(kg)
som = somun()
for i, (x, y) in enumerate(((25, 25), (295, 25), (25, 175), (295, 175)), 1):
    asm.add(cq.Assembly(som, name="SOMUN_M10", color=cq.Color(0.4, 0.4, 0.45)), name=f"SOMUN_M10.{i}", loc=cq.Location(cq.Vector(x, y, 6)))
yol = os.path.join(D, "SANAL_KONSOL_MONTAJI.stp")
asm.save(yol, "STEP")
print("yazıldı", yol, os.path.getsize(yol) // 1024, "KB")
