const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const [,, mod, cikti] = process.argv;
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + __dirname + '/out/Tanitim.html#kayit');
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(500);
  const bilgi = await p.evaluate(() => { const s=[...document.querySelectorAll('.slayt')].map(x=>+x.dataset.sure); return {s, T: window.TOPLAM}; });
  if (mod === 'onizle') {
    let t = 0;
    for (let i = 0; i < bilgi.s.length; i++) {
      await p.evaluate(tt => window.ciz(tt), t + bilgi.s[i] - 400);
      await p.screenshot({ path: `${cikti}/o_${String(i+1).padStart(2,'0')}.jpg`, quality: 80, type: 'jpeg' });
      t += bilgi.s[i];
    }
  } else if (mod === 'an') {  // belirli anlar: gecis ortasi vb.
    for (const t of process.argv.slice(4).map(Number)) {
      await p.evaluate(tt => window.ciz(tt), t);
      await p.screenshot({ path: `${cikti}/an_${t}.jpg`, quality: 80, type: 'jpeg' });
    }
  }
  await b.close();
})();
