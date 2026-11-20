// Usage:
//   node render.mjs stills 0.5,3,7.2 out_dir      -> PNG stills
//   node render.mjs video out.mp4 [fps] [from] [to] -> frames piped to ffmpeg (no audio)
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const ROOT = path.dirname(new URL(import.meta.url).pathname);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.woff2': 'font/woff2', '.m4a': 'audio/mp4' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  fs.readFile(p, (e, d) => { if (e) { res.writeHead(404); res.end(); return; } res.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' }); res.end(d); });
}).listen(0);
const port = server.address().port;

// GL=swiftshader forces software WebGL (slow, but works on machines without a usable GPU)
const GL = process.env.GL === 'swiftshader' ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] : ['--enable-gpu'];
const browser = await chromium.launch({ args: [...GL, '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: 720, height: 1280 } });
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text()); });
page.on('pageerror', e => console.log('[pageerror]', e.message));
await page.goto(`http://localhost:${port}/index.html?render=1`);
await page.waitForFunction(() => window.renderAt && window.ready);
await page.evaluate(() => window.ready);
const shot = () => page.screenshot({ clip: { x: 0, y: 0, width: 720, height: 1280 }, type: 'png' });

const [mode, a, b, c, d, e] = process.argv.slice(2);
if (mode === 'stills') {
  fs.mkdirSync(b, { recursive: true });
  for (const t of a.split(',').map(Number)) {
    const t0 = Date.now();
    await page.evaluate(t => window.renderAt(t), t);
    fs.writeFileSync(path.join(b, `t_${t.toFixed(2)}.png`), await shot());
    console.log('still', t, Date.now() - t0, 'ms');
  }
} else {
  const fps = Number(b || 30), dur = await page.evaluate(() => window.DURATION);
  const from = Number(c || 0), to = Math.min(Number(d || dur), dur);
  const n0 = Math.round(from * fps), n1 = Math.floor(to * fps);
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', a], { stdio: ['pipe', 'inherit', 'inherit'] });
  const T0 = Date.now();
  for (let n = n0; n < n1; n++) {
    await page.evaluate(t => window.renderAt(t), n / fps);
    const buf = await shot();
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (n % 30 === 0) console.log(`frame ${n}/${n1} ${((Date.now() - T0) / (n - n0 + 1)).toFixed(0)} ms/frame`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
}
await browser.close();
server.close();
