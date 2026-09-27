const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const { spawn } = require('child_process');
(async () => {
  const FPS = 30, cikti = process.argv[2];
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + __dirname + '/out/Tanitim.html#kayit');
  await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(800);
  const T = await p.evaluate(() => window.TOPLAM);
  const ff = spawn(process.env.FFMPEG || 'ffmpeg', ['-y','-f','image2pipe','-framerate',String(FPS),'-c:v','mjpeg','-i','-',
    '-c:v','libx264','-preset','slow','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart', cikti], { stdio: ['pipe','ignore','inherit'] });
  const N = Math.ceil(T / 1000 * FPS);
  for (let k = 0; k < N; k++) {
    await p.evaluate(t => window.ciz(t), k * 1000 / FPS);
    const buf = await p.screenshot({ type: 'jpeg', quality: 94 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (k % 300 === 0) console.log('kare', k, '/', N);
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); await b.close(); console.log('bitti', cikti);
})();
