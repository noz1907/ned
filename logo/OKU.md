# Logolar

Programın kullandığı bütün görseller burada. Değiştirmek isterseniz aynı
adla, aynı ölçüde yenisini koymanız yeter; kodda değişiklik gerekmez.

## Uygulama ikonu — `pi3d.*`

Kaynak: 1254 × 1254 çizim. Köşelerdeki beyaz zemin **saydama** çevrildi,
kenar yumuşatmasında beyazla karışan pikseller geri çözüldü; böylece ikon
her zemin üzerinde temiz duruyor.

| dosya | ölçü | nerede kullanılır |
|-------|------|-------------------|
| `pi3d.ico` | 16/24/32/48/64/128/256 birlikte | `.exe` ikonu, Windows pencere ve görev çubuğu |
| `pi3d_1024.png` | 1024 × 1024 | mağaza / baskı |
| `pi3d_512.png` … `pi3d_16.png` | 512, 256, 128, 72, 64, 48, 32, 24, 16 | Windows dışı pencere ikonu, kısayol, belge |

Windows'ta tek dosyada bütün boyutların olması şart: görev çubuğu 32'yi,
masaüstü 48'i, dosya gezgini 256'yı ister. Tek boyut konursa Windows
kendisi küçültür ve ikon bulanık çıkar.

## Şirket logosu — `pivision_*`

| dosya | ölçü | nerede kullanılır |
|-------|------|-------------------|
| `pivision_64.png` | 200 × 64 | arayüzün üst şeridi |
| `pivision_56.png` | 175 × 56 | yedek |
| `pivision_44.png` | 138 × 44 | dar pencere / yedek |
| `pivision_32.png` | 100 × 32 | küçük yerler |
| `pivision_beyaz.png` | 751 × 240 | ana kaynak, saydam zemin |
| `pivision_afis.png` | 818 × 291 | zeminiyle birlikte, belgeler için |

`pivision_beyaz.png` **beyaz ve saydam zeminlidir**: markanın içindeki π
de saydam bırakıldı, yani koyu bir zemine konduğunda aslındaki gibi
görünür. Üst şeritte uygulama ikonu `pi3d_72.png` (72 × 72) ile duruyor.
Arayüzdeki şeridin zemini `#0b2340` seçildi, logonun kendi
zeminiyle aynı tonda.

## Logo olmazsa

Program logosuz da çalışır: dosya bulunamazsa pencere varsayılan ikonla
açılır, üst şeritte resim yerine "PiVision" yazısı görünür. Hiçbir hata
vermez.
