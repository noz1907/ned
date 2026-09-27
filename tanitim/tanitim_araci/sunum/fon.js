const { chromium } = require('/opt/node22/lib/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + __dirname + '/out/Tanitim.html#kayit');
  await p.evaluate(() => { document.querySelectorAll('.slayt,.ilerleme').forEach(x => x.style.display = 'none');
    document.querySelector('.filigran').style.transform = 'none'; });
  await p.screenshot({ path: __dirname + '/out/g/fon.png' });
  await b.close();
})();
