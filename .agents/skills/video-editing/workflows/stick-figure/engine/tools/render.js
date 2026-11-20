// run from a reel folder: node <engine>/tools/render.js stills 1.5,3.2 | segments 0,4,8 | video out.mp4
// (Playwright comes from kit/node_modules: make.sh sets NODE_PATH, or set it yourself)
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
(async () => {
  const mode = process.argv[2];
  const browser = await chromium.launch({ ...(process.env.CHROME ? { executablePath: process.env.CHROME } : {}), args: ['--allow-file-access-from-files'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('console', m => console.log('[page]', m.text()));
  page.on('pageerror', e => console.log('[err]', e.message));
  await page.goto('file://' + process.cwd() + '/web/index.html');
  await page.evaluate(async () => { await document.fonts.load('700 40px Poppins'); await document.fonts.load('700 40px Lora'); await document.fonts.load('600 40px Lora'); });
  const total = await page.evaluate(() => window.TOTAL_FRAMES);
  if (mode === 'stills') {
    const times = process.argv[3].split(',').map(Number);
    fs.mkdirSync('stills', { recursive: true });
    for (const t of times) {
      const d = await page.evaluate(f => { renderFrame(f); return grab(.9); }, Math.round(t * 30));
      fs.writeFileSync(`stills/s_${t.toFixed(2)}.jpg`, Buffer.from(d.split(',')[1], 'base64'));
    }
  } else if (mode === 'segments') {
    // node render.js segments i,j,k  -> renders those shot indices to seg/shot_XX.mp4
    const ids = process.argv[3].split(',').map(Number);
    const shots = await page.evaluate(() => window.SHOT_SPANS || SHOTS.map(s => [s.start, s.end]));
    fs.mkdirSync('seg', { recursive: true });
    for (const id of ids) {
      const f0 = Math.round(shots[id][0] * 30), f1 = id === shots.length - 1 ? total : Math.round(shots[id][1] * 30);
      const tmp = `seg/shot_${String(id).padStart(2, '0')}.part.mp4`, fin = tmp.replace('.part', '');
      const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', '30', tmp], { stdio: ['pipe', 'inherit', 'inherit'] });
      for (let f = f0; f < f1; f++) {
        const d = await page.evaluate(f => { renderFrame(f); return grab(.95); }, f);
        if (!ff.stdin.write(Buffer.from(d.split(',')[1], 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
      }
      ff.stdin.end(); const code = await new Promise(r => ff.on('close', r));
      if (code === 0) fs.renameSync(tmp, fin); else console.log('ffmpeg failed', id);
      console.log('done shot', id, f1 - f0, 'frames');
    }
  } else {
    const outF = process.argv[3] || 'out_silent.mp4';
    const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', '30', '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', outF], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    for (let f = 0; f < total; f++) {
      const d = await page.evaluate(f => { renderFrame(f); return grab(.95); }, f);
      if (!ff.stdin.write(Buffer.from(d.split(',')[1], 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 100 === 0) console.log(`frame ${f}/${total} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
  }
  await browser.close();
})();
