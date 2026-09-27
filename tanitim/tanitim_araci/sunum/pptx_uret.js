// Ürün tanıtım sunumu -> PowerPoint. İçerik slaytlar.json'dan (HTML ile aynı).
// Animasyon ve geçişler pptxgenjs'te yok: öğelere "anim_<tip>_<gecikme>" adı
// verilir, sonra slayt XML'ine geçiş + giriş animasyonları eklenir (animasyon.py).
const pptxgen = require('pptxgenjs');
const path = require('path');
const V = require(path.join(__dirname, 'out', 'slaytlar.json'));
const G = path.join(__dirname, 'out', 'g');
const P = v => v / 144;                         // 1920 px = 13.333 in
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = V.urun + ' Tanıtım';
pres.company = 'PiVision';
const F = 'Arial';
const BEYAZ = 'FFFFFF', SARI = 'F5C518', YESIL = '27C96B', GRI = '9FB3D8', ACIK = 'DBE4F5', LACI = '0B1A3D';

let sayac = 0;
const ad = (tip, t) => `anim_${tip}_${t}_${++sayac}`;
const golge = () => ({ type: 'outer', color: '000000', opacity: 0.45, blur: 18, offset: 8, angle: 90 });

function metin(s, txt, o) {
  s.addText(txt, Object.assign({ isTextBox: true, fontFace: F, color: BEYAZ, margin: 0, valign: 'top' }, o));
}
function bant(s, aktif) {
  s.addImage({ path: path.join(G, 'urun_k.png'), x: P(64), y: P(40), w: P(64), h: P(64), rounding: true });
  metin(s, V.urun, { x: P(144), y: P(44), w: P(200), h: P(34), fontSize: 16, bold: true });
  metin(s, 'BY PIVISION', { x: P(144), y: P(80), w: P(200), h: P(20), fontSize: 7, color: GRI, charSpacing: 1.5 });
  if (!aktif) return;
  let x = 1920 - 56;
  const gen = V.adimlar.map((a, i) => 30 + (String(i + 1) + ' ' + a).length * 11.5);
  const top = gen.reduce((a, b) => a + b, 0) + 8 * (gen.length - 1);
  x -= top;
  V.adimlar.forEach((a, i) => {
    const ak = i + 1 === aktif, ge = i + 1 < aktif;
    s.addText(`${i + 1} ${a}`, {
      isTextBox: true, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.13, x: P(x), y: P(52), w: P(gen[i]), h: P(34),
      fontFace: F, fontSize: 8, bold: true, align: 'center', valign: 'middle', margin: 0,
      color: ak ? '101828' : (ge ? 'B9C8E6' : '6F84B0'),
      fill: ak ? { color: SARI } : { color: '0C1B42', transparency: 100 },
      line: { color: ak ? SARI : (ge ? 'A0BEF0' : '4A5F8F'), width: 1 } });
    x += gen[i] + 8;
  });
}
function cerceve(s, ad_, x, y, gen, vurgu, anim) {
  const [w, h] = V.boy[ad_];
  let yuk = gen * h / w;
  if (yuk > 700) { gen = gen * 700 / yuk; yuk = 700; }
  const k = gen / w;
  s.addImage({ path: path.join(G, ad_), x: P(x), y: P(y), w: P(gen), h: P(yuk), shadow: golge(),
               objectName: ad(anim || 'uc', 200) });
  (vurgu || []).forEach(([[x0, y0, x1, y1], et], j) => {
    const t = 1500 + j * 900;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: P(x + x0 * k - 6), y: P(y + y0 * k - 6), w: P((x1 - x0) * k + 12),
      h: P((y1 - y0) * k + 12), rectRadius: 0.06, fill: { color: SARI, transparency: 90 }, line: { color: SARI, width: 3 },
      objectName: ad('patla', t) });
    if (et) s.addText(et, { isTextBox: true, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06,
      x: P(x + x0 * k - 10), y: P(y + y0 * k - 42), w: P(Math.max(80, et.length * 11 + 28)), h: P(32),
      fontFace: F, fontSize: 9, bold: true, color: '101828', fill: { color: SARI }, align: 'center', valign: 'middle', margin: 0,
      objectName: ad('patla', t + 150) });
  });
  return [gen, yuk];
}

V.slaytlar.forEach((sl, i) => {
  const s = pres.addSlide();
  s.background = { path: path.join(G, 'fon.jpg') };
  metin(s, `${String(i + 1).padStart(2, '0')} / ${V.slaytlar.length}`, { x: P(1760), y: P(1030), w: P(120), h: P(22), fontSize: 9, color: '7F93BD', align: 'right' });
  if (sl.tip === 'kapak' || sl.tip === 'kapanis') {
    const kap = sl.tip === 'kapak';
    s.addImage({ path: path.join(G, 'urun_k.png'), x: P(120), y: P(kap ? 150 : 190), w: P(kap ? 300 : 280), h: P(kap ? 300 : 280), rounding: false, objectName: ad('patla', 200) });
    if (kap) {
      metin(s, V.urun, { x: P(470), y: P(215), w: P(600), h: P(130), fontSize: 60, bold: true, objectName: ad('ucsag', 600) });
      metin(s, 'BY PIVISION', { x: P(478), y: P(355), w: P(500), h: P(40), fontSize: 13, color: GRI, charSpacing: 4, objectName: ad('ucsag', 800) });
      V.kapak.forEach((t, j) =>
        metin(s, t, { x: P(120), y: P(520 + j * 97), w: P(1100), h: P(100), fontSize: 46, bold: true, objectName: ad('uc', 1300 + j * 400) }));
      metin(s, V.slogan, { x: P(124), y: P(830), w: P(1200), h: P(70), fontSize: 25, bold: true, color: SARI, objectName: ad('patla', 2800) });
      s.addImage({ path: path.join(G, 'pivision_k.png'), x: P(1210), y: P(170), w: P(620), h: P(620 * 1079 / 3000), objectName: ad('alt', 3600) });
    } else {
      V.kapanis.forEach((t, j) =>
        metin(s, t, { x: P(470), y: P(190 + j * 84), w: P(1350), h: P(86), fontSize: 39, bold: true, objectName: ad('uc', 800 + j * 450) }));
      metin(s, V.slogan, { x: P(474), y: P(470), w: P(1300), h: P(60), fontSize: 23, bold: true, color: SARI, objectName: ad('patla', 2400) });
      metin(s, V.kapanis_liste, { x: P(474), y: P(560), w: P(1300), h: P(40), fontSize: 13, color: 'C9D5EA', objectName: ad('alt', 3000) });
      s.addImage({ path: path.join(G, 'pivision_k.png'), x: P(560), y: P(720), w: P(800), h: P(800 * 1079 / 3000), objectName: ad('patla', 3600) });
    }
    return;
  }
  bant(s, sl.adim || 0);
  if (sl.tip === 'rakam') {
    metin(s, sl.ust, { x: P(120), y: P(190), w: P(1400), h: P(34), fontSize: 11, bold: true, color: SARI, charSpacing: 2, objectName: ad('uc', 200) });
    metin(s, sl.baslik, { x: P(116), y: P(232), w: P(1700), h: P(100), fontSize: 38, bold: true, objectName: ad('uc', 450) });
    metin(s, sl.alt, { x: P(120), y: P(342), w: P(1600), h: P(44), fontSize: 14, color: 'C9D5EA', objectName: ad('uc', 800) });
    sl.rakamlar.forEach(([n, a, a2], j) => {
      const x = 120 + j * (1680 - 3 * 36) / 4 + j * 36, w = (1680 - 3 * 36) / 4;
      const t = 1300 + j * 450;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: P(x), y: P(450), w: P(w), h: P(270), rectRadius: 0.2,
        fill: { color: '17306A', transparency: 20 }, line: { color: '5A82DC', width: 1.5 }, shadow: golge(), objectName: ad('patla', t) });
      metin(s, String(n), { x: P(x + 30), y: P(482), w: P(w - 60), h: P(120), fontSize: 54, bold: true, objectName: ad('patla', t + 100) });
      metin(s, a, { x: P(x + 30), y: P(612), w: P(w - 60), h: P(42), fontSize: 15, bold: true, color: SARI, objectName: ad('patla', t + 100) });
      metin(s, a2, { x: P(x + 30), y: P(656), w: P(w - 60), h: P(32), fontSize: 10, color: GRI, objectName: ad('patla', t + 100) });
    });
    s.addText(sl.not, { isTextBox: true, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.12, x: P(120), y: P(830), w: P(1180), h: P(76),
      fontFace: F, fontSize: 15, color: BEYAZ, margin: [14, 14, 0, 0], valign: 'middle',
      fill: { color: SARI, transparency: 88 }, line: { color: SARI, width: 1.5 }, objectName: ad('alt', 4200) });
    return;
  }
  if (sl.tip === 'adim') {
    const sol = sl.yon === 'sol';
    const [w, h] = V.boy[sl.resim];
    let gen = 1140, yuk = gen * h / w; if (yuk > 700) { gen = gen * 700 / yuk; yuk = 700; }
    const y = 175 + (720 - yuk) / 2;
    cerceve(s, sl.resim, sol ? 70 : 700, y, 1140, sl.vurgu, sol ? 'uc' : 'ucsag');
    s.addNotes(`${sl.baslik}. ` + sl.madde.join('. ') + `. (${sl.sure_yazi})`);
    const tx = sol ? 1260 : 80, yon = sol ? 'ucsag' : 'uc';
    s.addText(`ADIM ${sl.adim} · ${V.adimlar[sl.adim - 1]}`, { isTextBox: true, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.14,
      x: P(tx), y: P(210), w: P(40 + (`ADIM ${sl.adim} · ${V.adimlar[sl.adim - 1]}`).length * 13.5), h: P(40),
      fontFace: F, fontSize: 9.5, bold: true, color: '101828', fill: { color: SARI }, align: 'center', valign: 'middle', margin: 0, charSpacing: 1,
      objectName: ad('patla', 400) });
    metin(s, sl.baslik, { x: P(tx), y: P(272), w: P(620), h: P(140), fontSize: 27, bold: true, valign: 'top', objectName: ad(yon, 600) });
    const md = sl.madde.map((m, j) => ({ text: m, options: { bullet: { code: '25CF', color: YESIL }, breakLine: j < sl.madde.length - 1, paraSpaceAfter: 12 } }));
    s.addText(md, { isTextBox: true, x: P(tx), y: P(432), w: P(600), h: P(290), fontFace: F, fontSize: 14, color: ACIK, margin: 0, valign: 'top',
      objectName: ad(yon, 1200) });
    s.addText('⏱ ' + sl.sure_yazi, { isTextBox: true, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.12, x: P(tx), y: P(735),
      w: P(Math.max(240, sl.sure_yazi.length * 17 + 80)), h: P(62), fontFace: F, fontSize: 14, bold: true, color: LACI, fill: { color: YESIL },
      align: 'center', valign: 'middle', margin: 0, objectName: ad('patla', 2800) });
    return;
  }
  if (sl.tip === 'resim') {
    const [w, h] = V.boy[sl.resim]; const gen = 1760, yuk = gen * h / w;
    metin(s, sl.baslik, { x: P(0), y: P(160), w: P(1920), h: P(80), fontSize: 29, bold: true, align: 'center', objectName: ad('uc', 300) });
    s.addImage({ path: path.join(G, sl.resim), x: P(80), y: P(560 - yuk / 2), w: P(gen), h: P(yuk), shadow: golge(), objectName: ad('patla', 700) });
    metin(s, sl.alt, { x: P(160), y: P(860), w: P(1600), h: P(90), fontSize: 14, color: ACIK, align: 'center', objectName: ad('alt', 2000) });
    return;
  }
  if (sl.tip === 'klasor') {
    metin(s, sl.baslik, { x: P(0), y: P(160), w: P(1920), h: P(80), fontSize: 29, bold: true, align: 'center', objectName: ad('uc', 300) });
    [[80, 250, 900], [720, 330, 560], [1320, 300, 540]].forEach(([x, y, gen], j) => {
      const [w, h] = V.boy[sl.resimler[j]]; const yuk = gen * h / w;
      s.addImage({ path: path.join(G, sl.resimler[j]), x: P(x), y: P(y), w: P(gen), h: P(yuk), shadow: golge(), objectName: ad('patla', 700 + j * 700) });
      s.addText(sl.etiket[j], { isTextBox: true, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: P(x + 14), y: P(y + yuk - 50),
        w: P(sl.etiket[j].length * 13 + 36), h: P(36), fontFace: F, fontSize: 10, bold: true, color: SARI, fill: { color: LACI },
        align: 'center', valign: 'middle', margin: 0, objectName: ad('patla', 800 + j * 700) });
    });
    metin(s, sl.alt, { x: P(160), y: P(960), w: P(1600), h: P(50), fontSize: 14, color: ACIK, align: 'center', objectName: ad('alt', 3000) });
    return;
  }
  if (sl.tip === 'sure') {
    metin(s, sl.baslik, { x: P(0), y: P(160), w: P(1920), h: P(80), fontSize: 29, bold: true, align: 'center', objectName: ad('uc', 300) });
    const [w, h] = V.boy[sl.resim];
    s.addImage({ path: path.join(G, sl.resim), x: P(1480), y: P(270), w: P(330), h: P(330 * h / w), shadow: golge(), objectName: ad('ucsag', 500) });
    const dk = v => v >= 60 ? `${Math.floor(v / 60)} dk ${String(v % 60).padStart(2, '0')} sn` : `${v} sn`;
    s.addChart(pres.charts.BAR, [{ name: 'Süre (dk)', labels: sl.cubuk.map(c => c[0]), values: sl.cubuk.map(c => Math.round(c[1] / 6) / 10) }], {
      x: P(100), y: P(270), w: P(1320), h: P(560), barDir: 'bar', catAxisOrientation: 'maxMin',
      chartColors: ['2F7BFF'], showValue: true, dataLabelPosition: 'outEnd', dataLabelColor: BEYAZ, dataLabelFontSize: 11,
      dataLabelFontBold: true, dataLabelFormatCode: '0.0" dk"', catAxisLabelColor: ACIK, catAxisLabelFontSize: 12, valAxisHidden: true,
      valGridLine: { style: 'none' }, catGridLine: { style: 'none' }, showLegend: false, barGapWidthPct: 45,
      catAxisLineShow: false, objectName: ad('alt', 900) });
    metin(s, [{ text: 'TOPLAM  ', options: { fontSize: 15, color: GRI } }, { text: sl.toplam, options: { fontSize: 32, bold: true, color: SARI } },
              { text: '   ölçülen, ekrandaki süre paneli', options: { fontSize: 11, color: GRI } }],
          { x: P(120), y: P(860), w: P(1300), h: P(80), valign: 'bottom', objectName: ad('patla', 2600) });
    s.addNotes('Ölçülen süreler (ekrandaki süre paneli): ' + sl.cubuk.map(c => `${c[0]} ${dk(c[1])}`).join(', ') + '. Toplam ' + sl.toplam + '.');
    return;
  }
  if (sl.tip === 'guven') {
    metin(s, sl.baslik, { x: P(120), y: P(165), w: P(1600), h: P(110), fontSize: 42, bold: true, color: SARI, objectName: ad('uc', 300) });
    const w = (1680 - 2 * 36) / 3;
    sl.kart.forEach(([n, a, a2], j) => {
      const x = 120 + j * (w + 36), t = 900 + j * 450;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: P(x), y: P(320), w: P(w), h: P(250), rectRadius: 0.2,
        fill: { color: '17306A', transparency: 20 }, line: { color: '5A82DC', width: 1.5 }, shadow: golge(), objectName: ad('patla', t) });
      metin(s, n, { x: P(x + 30), y: P(348), w: P(w - 60), h: P(105), fontSize: 46, bold: true, objectName: ad('patla', t + 100) });
      metin(s, a, { x: P(x + 30), y: P(462), w: P(w - 60), h: P(42), fontSize: 14, bold: true, color: SARI, objectName: ad('patla', t + 100) });
      metin(s, a2, { x: P(x + 30), y: P(506), w: P(w - 60), h: P(34), fontSize: 10.5, color: GRI, objectName: ad('patla', t + 100) });
    });
    metin(s, 'Parça mı, standart mı, kaynak mı — adından, montaj ağacından, geometrisinden:',
          { x: P(120), y: P(630), w: P(1680), h: P(40), fontSize: 12, color: 'C9D5EA', objectName: ad('alt', 2400) });
    sl.ornek.forEach(([a, b, c], j) => {
      const y = 680 + j * 76, t = 2900 + j * 500;
      s.addText([{ text: a, options: { color: GRI, bold: true, fontSize: 11 } }, { text: '    ' + b, options: { color: BEYAZ, bold: true, fontSize: 14 } },
                 { text: '    ' + c, options: { color: 'C9D5EA', fontSize: 10.5 } }],
        { isTextBox: true, shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.1, x: P(120), y: P(y), w: P(1680), h: P(62), fontFace: F,
          fill: { color: '0A1437', transparency: 30 }, line: { color: '3C5CAE', width: 1.5 }, margin: [14, 14, 0, 0], valign: 'middle',
          objectName: ad('uc', t) });
    });
  }
});

pres.writeFile({ fileName: path.join(__dirname, 'out', 'Tanitim_ham.pptx') }).then(f => console.log('yazıldı', f));
