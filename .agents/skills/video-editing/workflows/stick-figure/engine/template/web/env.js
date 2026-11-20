// ---------- environment & props ----------
function hex2rgb(h) { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function mix(a, b, t) { const A = hex2rgb(a), B = hex2rgb(b); return `rgb(${A.map((v, i) => Math.round(lerp(v, B[i], t))).join(',')})`; }

function applyCam(ctx, cam, depth = 1) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const z = 1 + (cam.z - 1) * depth;
  ctx.translate(W / 2, H / 2); ctx.rotate((cam.r || 0) * depth); ctx.scale(z, z);
  ctx.translate(-(540 + (cam.x - 540) * depth), -(960 + (cam.y - 960) * depth));
}
function drawSky(ctx, top = '#3ea6ee', bot = '#c9ecfb', y0 = -400, y1 = 1100) {
  const g = ctx.createLinearGradient(0, y0, 0, y1); g.addColorStop(0, top); g.addColorStop(1, bot);
  ctx.fillStyle = g; ctx.fillRect(-2000, y0 - 2000, 5080, y1 - y0 + 4000);
}
function drawSun(ctx, x, y, r, t, power = 1) {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const g = ctx.createRadialGradient(x, y, r * .2, x, y, r * 4.5);
  g.addColorStop(0, `rgba(255,250,210,${.9 * power})`); g.addColorStop(.25, `rgba(255,230,150,${.35 * power})`); g.addColorStop(1, 'rgba(255,220,150,0)');
  ctx.fillStyle = g; ctx.fillRect(x - r * 5, y - r * 5, r * 10, r * 10);
  // rays
  ctx.translate(x, y); ctx.rotate(t * .15);
  for (let i = 0; i < 12; i++) { ctx.rotate(TAU / 12); ctx.beginPath(); ctx.moveTo(-r * .18, r * 1.2); ctx.lineTo(r * .18, r * 1.2); ctx.lineTo(0, r * (2.6 + (i % 2) * .8)); ctx.closePath(); ctx.fillStyle = `rgba(255,240,170,${.22 * power})`; ctx.fill(); }
  ctx.restore();
  circle(ctx, x, y, r); ctx.fillStyle = '#fffbe6'; ctx.fill();
  circle(ctx, x, y, r * .82); ctx.fillStyle = '#fff6c4'; ctx.fill();
}
function pillar(ctx, x, base, w, h, seed, haze = 0, sky = '#bfe6f8') {
  const R = rng(seed); const top = base - h;
  const pts = [];
  const n = 7;
  for (let i = 0; i <= n; i++) pts.push([x - w / 2 + (R() - .5) * w * .12 - Math.sin(i / n * Math.PI) * w * .04, top + h * i / n]);
  const rpts = [];
  for (let i = n; i >= 0; i--) rpts.push([x + w / 2 + (R() - .5) * w * .12 + Math.sin(i / n * Math.PI) * w * .03, top + h * i / n]);
  const shape = () => { ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); pts.forEach(p => ctx.lineTo(...p)); rpts.forEach(p => ctx.lineTo(...p)); ctx.closePath(); };
  const light = mix('#f7d39e', sky, haze), mid = mix('#e9a971', sky, haze), dark = mix('#c97c55', sky, haze);
  shape(); ctx.fillStyle = light; ctx.fill();
  ctx.save(); shape(); ctx.clip();
  ctx.fillStyle = mid; ctx.fillRect(x + w * .05, top, w, h);
  ctx.fillStyle = dark; ctx.fillRect(x + w * .3, top, w, h);
  // strata
  ctx.strokeStyle = mix('#a86f4e', sky, haze); ctx.lineWidth = Math.max(1.5, w * .025);
  for (let i = 1; i < 9; i++) { const yy = top + h * (i / 9) + (R() - .5) * 10; ctx.beginPath(); ctx.moveTo(x - w, yy); ctx.quadraticCurveTo(x, yy + (R() - .5) * 18, x + w, yy + 4); ctx.stroke(); }
  // vines
  ctx.strokeStyle = mix('#4c9a52', sky, haze); ctx.lineWidth = Math.max(2, w * .05);
  for (let i = 0; i < 3; i++) { const vx = x - w / 2 + R() * w; ctx.beginPath(); ctx.moveTo(vx, top); ctx.quadraticCurveTo(vx + (R() - .5) * 20, top + h * .2, vx + (R() - .5) * 10, top + h * (.15 + R() * .3)); ctx.stroke(); }
  ctx.restore();
  shape(); ctx.lineWidth = Math.max(2, w * .03); ctx.strokeStyle = mix('#6b3f2e', sky, haze * .9); ctx.stroke();
  // green top
  const gr = () => { ctx.beginPath(); for (let i = 0; i < 6; i++) { const bx = x - w * .55 + i * w * .22, br = w * (.18 + R() * .1); ctx.moveTo(bx + br, top + 4); ctx.arc(bx, top + 2 - br * .3, br, 0, TAU); } };
  const R2 = rng(seed + 9); const saved = R;
  ctx.save();
  const blobs = []; for (let i = 0; i < 6; i++) blobs.push([x - w * .55 + i * w * .22, top - w * .02 - R2() * w * .08, w * (.16 + R2() * .1)]);
  ctx.beginPath(); blobs.forEach(b => { ctx.moveTo(b[0] + b[2], b[1]); ctx.arc(b[0], b[1], b[2], 0, TAU); });
  ctx.lineWidth = Math.max(2, w * .03); ctx.strokeStyle = mix('#245e33', sky, haze); ctx.stroke();
  ctx.fillStyle = mix('#4fae5c', sky, haze); ctx.fill();
  ctx.beginPath(); blobs.forEach(b => { ctx.moveTo(b[0] + b[2] * .6, b[1] - b[2] * .2); ctx.arc(b[0] - b[2] * .15, b[1] - b[2] * .25, b[2] * .55, 0, TAU); });
  ctx.fillStyle = mix('#7fd06e', sky, haze); ctx.fill();
  ctx.restore();
}
function drawPillars(ctx, base, set = 'A', haze = 0) {
  const sets = {
    A: [[80, 210, 560, 1, .55], [300, 150, 420, 2, .65], [930, 230, 640, 3, .5], [700, 120, 360, 4, .7], [1150, 160, 480, 5, .6], [-120, 170, 470, 6, .6]],
    B: [[160, 260, 700, 11, .45], [520, 140, 380, 12, .7], [860, 200, 560, 13, .55], [-60, 150, 420, 14, .62], [1180, 220, 520, 15, .55]],
  };
  const list = sets[set].slice().sort((a, b) => b[4] - a[4]);
  for (const [x, w, h, seed, hz] of list) pillar(ctx, x, base + 30, w, h, seed, clamp((hz - .42) * 1.1 + haze));
}
function drawSea(ctx, horizon, t, depthTo = 2600, palette = ['#7fd3e0', '#18a3c0', '#0d7fa6']) {
  const g = ctx.createLinearGradient(0, horizon, 0, horizon + 900);
  g.addColorStop(0, palette[0]); g.addColorStop(.25, palette[1]); g.addColorStop(1, palette[2]);
  ctx.fillStyle = g; ctx.fillRect(-2000, horizon, 5080, depthTo);
  // wave dashes
  const R = rng(42);
  ctx.strokeStyle = 'rgba(210,250,255,.55)'; ctx.lineCap = 'round';
  for (let i = 0; i < 90; i++) {
    const d = R(); const y = horizon + 10 + d * d * 900; const sc = .3 + d * 1.6;
    const x = ((R() * 2400 + t * 12 * sc) % 2400) - 650;
    ctx.lineWidth = 2 + sc * 3; ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + 22 * sc, y - 6 * sc, x + 44 * sc, y); ctx.stroke();
  }
  // horizon line glow
  ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.fillRect(-2000, horizon - 2, 5080, 5);
}
function drawShip(ctx, x, y, s, t, o = {}) {
  ctx.save(); ctx.translate(x, y + Math.sin(t * 1.6 + (o.ph || 0)) * 4 * s); ctx.rotate(Math.sin(t * 1.2 + (o.ph || 0)) * .015); ctx.scale(s * (o.flip || 1), s);
  const hull = o.hull || '#7d3a22', stripe = o.stripe || '#e2b04a', lw = 5, sail = o.sail || '#f4ead4';
  // masts
  const masts = [[-150, -470], [20, -560], [170, -430]];
  for (const [mx, top] of masts) { rrect(ctx, mx - 8, top, 16, -top, 4); fillStroke(ctx, '#8a5530', lw); }
  // bow jib
  ctx.beginPath(); ctx.moveTo(185, -420); ctx.lineTo(360, -120); ctx.quadraticCurveTo(250, -140, 190, -150); ctx.closePath(); fillStroke(ctx, sail, lw);
  // square sails, billowing
  for (const [mx, top] of masts) {
    const sails = [[top + 30, 150, 120], [top + 165, 190, 150]];
    for (const [sy, sw, sh] of sails) {
      rrect(ctx, mx - sw / 2 - 10, sy - 8, sw + 20, 12, 5); fillStroke(ctx, '#7a4a2a', 4);
      ctx.beginPath(); ctx.moveTo(mx - sw / 2, sy); ctx.lineTo(mx + sw / 2, sy); ctx.quadraticCurveTo(mx + sw / 2 + 28, sy + sh * .55, mx + sw / 2 + 6, sy + sh); ctx.quadraticCurveTo(mx, sy + sh + 16, mx - sw / 2 - 6, sy + sh); ctx.quadraticCurveTo(mx - sw / 2 + 22, sy + sh * .55, mx - sw / 2, sy); ctx.closePath();
      fillStroke(ctx, sail, lw);
      ctx.save(); ctx.clip(); ctx.fillStyle = 'rgba(150,100,50,.18)'; ctx.fillRect(mx + sw * .1, sy - 10, sw, sh + 30); ctx.strokeStyle = 'rgba(150,100,50,.3)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(mx - sw * .2, sy); ctx.quadraticCurveTo(mx - sw * .1, sy + sh * .5, mx - sw * .2, sy + sh); ctx.stroke(); ctx.restore();
    }
  }
  // flag
  const fy = -610, fx = 20;
  ctx.beginPath(); ctx.moveTo(fx + 8, fy); for (let i = 0; i <= 6; i++) ctx.lineTo(fx + 8 + i * 16, fy + Math.sin(t * 6 + i) * 6); ctx.lineTo(fx + 104, fy + 60); for (let i = 6; i >= 0; i--) ctx.lineTo(fx + 8 + i * 16, fy + 60 + Math.sin(t * 6 + i) * 6); ctx.closePath();
  fillStroke(ctx, o.flag || '#1b1820', lw);
  if (o.skull) { circle(ctx, fx + 56, fy + 25, 13); ctx.fillStyle = '#f2efe6'; ctx.fill(); line(ctx, fx + 38, fy + 44, fx + 74, fy + 48, 6, '#f2efe6'); line(ctx, fx + 38, fy + 48, fx + 74, fy + 42, 6, '#f2efe6'); }
  // hull with raised stern castle
  ctx.beginPath(); ctx.moveTo(-330, -150); ctx.lineTo(-200, -150); ctx.lineTo(-190, -95); ctx.lineTo(260, -95); ctx.quadraticCurveTo(330, -110, 370, -160); ctx.lineTo(345, -40); ctx.quadraticCurveTo(290, 45, 170, 50); ctx.lineTo(-230, 50); ctx.quadraticCurveTo(-310, 30, -335, -60); ctx.closePath();
  fillStroke(ctx, hull, lw);
  ctx.save(); ctx.clip();
  ctx.fillStyle = 'rgba(255,230,180,.15)'; ctx.fillRect(-400, -160, 800, 40);
  ctx.fillStyle = stripe; ctx.fillRect(-400, -45, 800, 16);
  ctx.fillStyle = '#25140f'; for (let i = 0; i < 8; i++) { rrect(ctx, -200 + i * 55, -78, 26, 22, 4); ctx.fill(); }
  ctx.fillStyle = 'rgba(255,230,140,.8)'; for (let i = 0; i < 2; i++) { rrect(ctx, -300 + i * 50, -135, 26, 28, 4); ctx.fill(); }
  ctx.fillStyle = 'rgba(0,0,0,.25)'; ctx.fillRect(-400, 10, 800, 50); ctx.restore();
  // rail
  line(ctx, -190, -95, 270, -95, 8, '#c88b52');
  // water foam
  ctx.fillStyle = 'rgba(255,255,255,.75)'; ellipse(ctx, 0, 50, 360, 12); ctx.fill();
  ctx.restore();
}
// deck floor in perspective. returns geometry helper
function deckGeom(back, vx = 540, vy = -900) { return { back, vx, vy }; }
function drawDeckFloor(ctx, back, vx = 540, vy = -1100, x0 = -600, x1 = 1680, bottom = 2400, tint = 0) {
  const g = ctx.createLinearGradient(0, back, 0, bottom);
  g.addColorStop(0, mix('#b8763f', '#1a0f12', tint)); g.addColorStop(1, mix('#d89a5a', '#1a0f12', tint));
  ctx.fillStyle = g; ctx.fillRect(x0, back, x1 - x0, bottom - back);
  // planks: lines from vanishing point
  ctx.strokeStyle = mix('#7a4521', '#000000', tint * .8); ctx.lineWidth = 4;
  const n = 26;
  for (let i = 0; i <= n; i++) {
    const bx = -1600 + i * (4300 / n);
    const k = (back - vy) / (bottom - vy); const tx = vx + (bx - vx) * k;
    ctx.beginPath(); ctx.moveTo(tx, back); ctx.lineTo(bx, bottom); ctx.stroke();
    // alternate plank tint
    if (i % 3 === 0 && i < n) {
      const bx2 = -1600 + (i + 1) * (4300 / n), tx2 = vx + (bx2 - vx) * k;
      path(ctx, [[tx, back], [tx2, back], [bx2, bottom], [bx, bottom]]); ctx.fillStyle = 'rgba(255,220,170,.07)'; ctx.fill();
    }
  }
  // seams across
  ctx.lineWidth = 2.5;
  for (let j = 1; j < 14; j++) { const y = back + Math.pow(j / 14, 1.7) * (bottom - back); ctx.beginPath(); for (let i = 0; i < 9; i++) { const xx = -600 + i * 300 + (j % 2) * 150; ctx.moveTo(xx, y); ctx.lineTo(xx, y + 6 + j * 2); } ctx.stroke(); }
  ctx.fillStyle = 'rgba(60,30,10,.25)'; ctx.fillRect(x0, back, x1 - x0, 14);
}
function drawBulwark(ctx, back, h = 150, x0 = -600, x1 = 1680, col = '#a9412c') {
  rrect(ctx, x0, back - h, x1 - x0, h + 10, 0); fillStroke(ctx, col, 5);
  ctx.fillStyle = 'rgba(60,10,10,.25)'; ctx.fillRect(x0, back - h * .45, x1 - x0, 6);
  for (let x = x0 + 40; x < x1; x += 160) { rrect(ctx, x, back - h - 6, 26, h + 10, 4); fillStroke(ctx, '#8a3423', 4); }
  rrect(ctx, x0, back - h - 26, x1 - x0, 30, 8); fillStroke(ctx, '#c88b52', 5);
  ctx.fillStyle = 'rgba(255,255,255,.25)'; ctx.fillRect(x0, back - h - 22, x1 - x0, 6);
}
function drawBarrel(ctx, x, y, s, tint = 0) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  const body = () => { ctx.beginPath(); ctx.moveTo(-50, -150); ctx.quadraticCurveTo(-68, -75, -50, 0); ctx.lineTo(50, 0); ctx.quadraticCurveTo(68, -75, 50, -150); ctx.closePath(); };
  body(); ctx.fillStyle = mix('#c07a3d', '#120a0c', tint); ctx.fill();
  ctx.save(); body(); ctx.clip();
  ctx.strokeStyle = mix('#8a4f24', '#000', tint); ctx.lineWidth = 3; for (let i = -3; i <= 3; i++) { ctx.beginPath(); ctx.moveTo(i * 15, -160); ctx.quadraticCurveTo(i * 20, -75, i * 15, 10); ctx.stroke(); }
  ctx.fillStyle = mix('#3f3a3c', '#000', tint); ctx.fillRect(-80, -128, 160, 12); ctx.fillRect(-80, -34, 160, 12);
  ctx.fillStyle = 'rgba(40,10,10,.25)'; ctx.fillRect(15, -160, 70, 170);
  ctx.fillStyle = 'rgba(255,230,190,.18)'; ctx.fillRect(-40, -160, 18, 170);
  ctx.restore(); body(); fillStroke(ctx, null, 5);
  ellipse(ctx, 0, -150, 50, 13); fillStroke(ctx, mix('#d9995a', '#120a0c', tint), 5);
  ctx.restore();
}
function drawCrate(ctx, x, y, w, h, tint = 0, label) {
  rrect(ctx, x - w / 2, y - h, w, h, 6); fillStroke(ctx, mix('#c28a4e', '#120a0c', tint), 5);
  ctx.save(); rrect(ctx, x - w / 2, y - h, w, h, 6); ctx.clip();
  ctx.strokeStyle = mix('#8a5a2c', '#000', tint); ctx.lineWidth = 3; for (let i = 1; i < 4; i++) line(ctx, x - w / 2, y - h + i * h / 4, x + w / 2, y - h + i * h / 4, 3, mix('#8a5a2c', '#000', tint));
  ctx.fillStyle = 'rgba(40,10,10,.2)'; ctx.fillRect(x + w * .2, y - h, w, h); ctx.restore();
  rrect(ctx, x - w / 2 - 4, y - h - 4, w + 8, 18, 4); fillStroke(ctx, mix('#9a6232', '#120a0c', tint), 4);
  rrect(ctx, x - w / 2 - 4, y - 16, w + 8, 18, 4); fillStroke(ctx, mix('#9a6232', '#120a0c', tint), 4);
  if (label) text(ctx, label, x, y - h / 2, h * .2, mix('#5a2e16', '#000', tint), null, 0, 'Lora', 700);
}
function drawCannon(ctx, x, y, s, ang = -.08, flip = 1, tint = 0) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s * flip, s);
  // carriage
  path(ctx, [[-120, -10], [110, -10], [90, -90], [-40, -110], [-120, -80]]); fillStroke(ctx, mix('#b9462f', '#100a0c', tint), 5);
  ctx.save(); ctx.rotate(ang); ctx.translate(0, -120);
  ctx.beginPath(); ctx.moveTo(-150, -38); ctx.lineTo(230, -26); ctx.lineTo(240, -32); ctx.lineTo(250, -32); ctx.lineTo(250, 32); ctx.lineTo(240, 32); ctx.lineTo(230, 26); ctx.lineTo(-150, 38); ctx.quadraticCurveTo(-190, 0, -150, -38); ctx.closePath();
  fillStroke(ctx, mix('#555b66', '#08080a', tint), 5);
  ctx.fillStyle = 'rgba(255,255,255,.25)'; ctx.fillRect(-140, -26, 360, 9);
  ctx.fillStyle = 'rgba(0,0,0,.25)'; ctx.fillRect(-140, 10, 370, 18);
  for (const bx of [-90, 40, 170]) { rrect(ctx, bx, -40, 14, 80, 4); fillStroke(ctx, mix('#454a54', '#08080a', tint), 4); }
  ctx.restore();
  for (const wx of [-80, 70]) { circle(ctx, wx, -12, 34); fillStroke(ctx, mix('#8b3a26', '#100a0c', tint), 5); circle(ctx, wx, -12, 10); fillStroke(ctx, '#3a3034', 4); }
  ctx.restore();
}
function drawMast(ctx, x, top, bottom, w = 60) {
  rrect(ctx, x - w / 2, top, w, bottom - top, 10); fillStroke(ctx, '#b47a43', 5);
  ctx.save(); rrect(ctx, x - w / 2, top, w, bottom - top, 10); ctx.clip(); ctx.fillStyle = 'rgba(60,20,0,.25)'; ctx.fillRect(x + w * .1, top, w, bottom - top); ctx.fillStyle = 'rgba(255,240,200,.25)'; ctx.fillRect(x - w * .3, top, w * .15, bottom - top); ctx.restore();
  for (let y = top + 200; y < bottom - 100; y += 380) { rrect(ctx, x - w / 2 - 8, y, w + 16, 22, 6); fillStroke(ctx, '#5a4a48', 4); }
}
function drawRigging(ctx, x0, y0, x1, y1, rungs = 10, w = 120) {
  ctx.strokeStyle = '#6d5236'; ctx.lineWidth = 6; ctx.lineCap = 'round';
  line(ctx, x0 - w / 2, y0, x1 - w / 4, y1, 6, '#5d4630'); line(ctx, x0 + w / 2, y0, x1 + w / 4, y1, 6, '#5d4630');
  for (let i = 1; i < rungs; i++) { const t = i / rungs; line(ctx, lerp(x0 - w / 2, x1 - w / 4, t), lerp(y0, y1, t), lerp(x0 + w / 2, x1 + w / 4, t), lerp(y0, y1, t), 4, '#5d4630'); }
}
function drawSailCorner(ctx, x, y, w, h, t) {
  ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + w, y + Math.sin(t) * 6); ctx.quadraticCurveTo(x + w * .6 + Math.sin(t * 1.3) * 10, y + h * .6, x, y + h); ctx.closePath();
  fillStroke(ctx, '#f1e5c9', 6); ctx.save(); ctx.clip(); ctx.fillStyle = 'rgba(150,110,60,.18)'; ctx.fillRect(x + w * .4, y, w, h); ctx.restore();
}
function drawHatch(ctx, cx, cy, w, h, depthCol = '#0b0709') {
  // perspective trapezoid hole: top edge narrower
  const tl = [cx - w * .42, cy - h / 2], tr = [cx + w * .42, cy - h / 2], br = [cx + w / 2, cy + h / 2], bl = [cx - w / 2, cy + h / 2];
  path(ctx, [[tl[0] - 22, tl[1] - 14], [tr[0] + 22, tr[1] - 14], [br[0] + 28, br[1] + 18], [bl[0] - 28, bl[1] + 18]]); fillStroke(ctx, '#8a5428', 5);
  path(ctx, [tl, tr, br, bl]); fillStroke(ctx, depthCol, 5);
  // inner wall hint
  path(ctx, [tl, tr, [tr[0] - 4, tl[1] + h * .3], [tl[0] + 4, tl[1] + h * .3]]); ctx.fillStyle = '#3a2216'; ctx.fill();
  // ladder top
  line(ctx, cx - 40, tl[1] + h * .3, cx - 46, br[1], 8, '#5a3a22'); line(ctx, cx + 40, tl[1] + h * .3, cx + 46, br[1], 8, '#5a3a22');
  return { tl, tr, br, bl, front: br[1] };
}
function drawPan(ctx, x, y, s, ang, tint = 0) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(ang); ctx.scale(s, s);
  rrect(ctx, -8, -170, 16, 120, 6); fillStroke(ctx, mix('#6a3d22', '#000', tint), 5);
  ellipse(ctx, 0, -230, 70, 72); fillStroke(ctx, mix('#3d4048', '#000', tint), 6);
  ellipse(ctx, 0, -232, 52, 54); ctx.fillStyle = mix('#5a5f6a', '#000', tint); ctx.fill();
  ellipse(ctx, -16, -250, 14, 22, .4); ctx.fillStyle = `rgba(255,255,255,${.35 * (1 - tint)})`; ctx.fill();
  ctx.restore();
}
function drawLantern(ctx, x, y, s, lit = 0, t = 0) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  line(ctx, 0, -120, 0, -60, 4);
  if (lit > 0) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const g = ctx.createRadialGradient(0, 0, 10, 0, 0, 520); const fl = .9 + Math.sin(t * 23) * .05 + Math.sin(t * 9) * .05;
    g.addColorStop(0, `rgba(255,190,90,${.55 * lit * fl})`); g.addColorStop(.4, `rgba(255,140,50,${.18 * lit * fl})`); g.addColorStop(1, 'rgba(255,120,40,0)');
    ctx.fillStyle = g; ctx.fillRect(-600, -600, 1200, 1200); ctx.restore();
  }
  ctx.beginPath(); ctx.moveTo(-26, -60); ctx.lineTo(26, -60); ctx.lineTo(36, 40); ctx.lineTo(-36, 40); ctx.closePath(); fillStroke(ctx, lit > 0 ? mix('#5a4a2a', '#ffcf6a', lit) : '#2c2a2e', 5);
  if (lit > 0) { ellipse(ctx, 0, 6, 10, 18); ctx.fillStyle = '#fff3c0'; ctx.fill(); }
  rrect(ctx, -40, -76, 80, 18, 6); fillStroke(ctx, '#3b3236', 4); rrect(ctx, -44, 36, 88, 16, 6); fillStroke(ctx, '#3b3236', 4);
  line(ctx, -30, -58, -36, 38, 4); line(ctx, 30, -58, 36, 38, 4); line(ctx, 0, -58, 0, 38, 3);
  ctx.restore();
}
function drawBelowDeck(ctx, tint = 0, lightX = 540, t = 0) {
  // back wall
  const wall = mix('#7a4a2c', '#08060a', tint), floor = mix('#5e3a22', '#08060a', tint);
  ctx.fillStyle = wall; ctx.fillRect(-800, -600, 2700, 2000);
  ctx.strokeStyle = mix('#4a2a18', '#000', tint); ctx.lineWidth = 4;
  for (let y = -560; y < 1400; y += 70) line(ctx, -800, y, 1900, y, 4, mix('#4a2a18', '#000', tint));
  // ribs
  for (let x = -700; x < 1900; x += 330) { rrect(ctx, x, -600, 58, 2000, 0); fillStroke(ctx, mix('#5a3420', '#060406', tint), 5); }
  // ceiling beams
  rrect(ctx, -800, -40, 2700, 70, 0); fillStroke(ctx, mix('#4e2c1a', '#060406', tint), 5);
  // floor
  ctx.fillStyle = floor; ctx.fillRect(-800, 1330, 2700, 1400);
  for (let i = 0; i < 30; i++) { const bx = -1600 + i * 170; line(ctx, 540 + (bx - 540) * .3, 1330, bx, 2600, 4, mix('#3e2414', '#000', tint)); }
  ctx.fillStyle = 'rgba(0,0,0,.3)'; ctx.fillRect(-800, 1330, 2700, 20);
}
function darkness(ctx, a, col = '#050407') { if (a <= 0) return; ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = clamp(a); ctx.fillStyle = col; ctx.fillRect(0, 0, W, H); ctx.restore(); }
function lightShaft(ctx, x0, y0, wTop, wBot, len, a) {
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  const g = ctx.createLinearGradient(0, y0, 0, y0 + len); g.addColorStop(0, `rgba(255,236,190,${.5 * a})`); g.addColorStop(1, 'rgba(255,230,180,0)');
  path(ctx, [[x0 - wTop / 2, y0], [x0 + wTop / 2, y0], [x0 + wBot / 2, y0 + len], [x0 - wBot / 2, y0 + len]]); ctx.fillStyle = g; ctx.fill();
  ctx.restore();
}
