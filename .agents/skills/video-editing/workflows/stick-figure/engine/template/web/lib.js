// ---------- core helpers ----------
const W = 1080, H = 1920, FPS = 30;
const INK = '#221c22';
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const inv = (a, b, v) => clamp((v - a) / (b - a));
const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const easeOut = t => 1 - Math.pow(1 - t, 3);
const easeIn = t => t * t * t;
const backOut = t => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
const elastic = t => t === 0 ? 0 : t === 1 ? 1 : Math.pow(2, -10 * t) * Math.sin((t * 10 - .75) * (2 * Math.PI) / 3) + 1;
const TAU = Math.PI * 2;

// keyframes: [[t, v], ...] (v number or array), easing per segment
function kf(t, keys, fn = ease) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, v0] = keys[i], [t1, v1] = keys[i + 1];
    if (t <= t1) {
      const e = (keys[i + 1][2] || fn)(inv(t0, t1, t));
      if (Array.isArray(v0)) return v0.map((x, j) => lerp(x, v1[j], e));
      return lerp(v0, v1, e);
    }
  }
  return keys[keys.length - 1][1];
}
// deterministic pseudo random
function rng(seed) { let s = seed >>> 0 || 1; return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 100000) / 100000; }; }
function shake(t, amp, freq = 1, seed = 0) {
  return [amp * (Math.sin(t * 13.1 * freq + seed) * .6 + Math.sin(t * 7.3 * freq + 1.3 + seed) * .4),
          amp * (Math.sin(t * 11.7 * freq + 2.1 + seed) * .6 + Math.sin(t * 5.9 * freq + .4 + seed) * .4)];
}

// ---------- drawing primitives ----------
function path(ctx, pts, close = true) {
  ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  if (close) ctx.closePath();
}
function rrect(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.roundRect(x, y, w, h, r);
}
function fillStroke(ctx, fill, lw = 6, stroke = INK) {
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (lw > 0) { ctx.lineWidth = lw; ctx.strokeStyle = stroke; ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.stroke(); }
}
function circle(ctx, x, y, r) { ctx.beginPath(); ctx.arc(x, y, Math.max(0.01, r), 0, TAU); }
function ellipse(ctx, x, y, rx, ry, rot = 0) { ctx.beginPath(); ctx.ellipse(x, y, Math.max(.01, rx), Math.max(.01, ry), rot, 0, TAU); }
function line(ctx, x1, y1, x2, y2, lw, col = INK) {
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
  ctx.lineWidth = lw; ctx.strokeStyle = col; ctx.lineCap = 'round'; ctx.stroke();
}
function shadeShape(ctx, drawPath, side = 1, amt = .16, w = .45, bbox) {
  // darken one side of a shape (cel shading)
  ctx.save(); drawPath(); ctx.clip();
  const [x, y, bw, bh] = bbox;
  ctx.fillStyle = `rgba(30,10,40,${amt})`;
  if (side > 0) ctx.fillRect(x + bw * (1 - w), y, bw * w + 2, bh); else ctx.fillRect(x - 2, y, bw * w, bh);
  ctx.restore();
}
function cloudShape(ctx, x, y, s, seed = 1) {
  const r = rng(seed); ctx.beginPath();
  const bumps = [[-1.1, .15, .45], [-.55, -.2, .62], [.1, -.38, .72], [.75, -.12, .55], [1.2, .18, .4]];
  bumps.forEach(([bx, by, br]) => { const k = .85 + r() * .3; ctx.moveTo(x + (bx + br * k) * s, y + by * s); ctx.arc(x + bx * s, y + by * s, br * k * s, 0, TAU); });
  ctx.rect(x - 1.3 * s, y + .05 * s, 2.6 * s, .4 * s);
}
function drawCloud(ctx, x, y, s, seed = 1, alpha = 1) {
  ctx.save(); ctx.globalAlpha = alpha;
  // outline pass
  cloudShape(ctx, x, y, s, seed); ctx.lineWidth = Math.max(3, s * .05); ctx.strokeStyle = 'rgba(70,120,170,.55)'; ctx.stroke();
  cloudShape(ctx, x, y, s, seed); ctx.fillStyle = '#ffffff'; ctx.fill();
  ctx.save(); cloudShape(ctx, x, y, s, seed); ctx.clip();
  ctx.fillStyle = '#d6e8f7'; ctx.fillRect(x - 1.5 * s, y + .12 * s, 3 * s, .5 * s);
  ctx.restore(); ctx.restore();
}
// cartoon puff (smoke / dust)
function puff(ctx, x, y, r, t, col = '#f3efe6', seed = 3, alpha = 1) {
  if (alpha <= 0) return;
  const R = rng(seed); ctx.save(); ctx.globalAlpha = alpha;
  const blobs = [];
  for (let i = 0; i < 6; i++) { const a = R() * TAU; const d = r * (.3 + R() * .5); blobs.push([x + Math.cos(a) * d, y + Math.sin(a) * d * .7, r * (.35 + R() * .3)]); }
  ctx.beginPath(); blobs.forEach(b => { ctx.moveTo(b[0] + b[2], b[1]); ctx.arc(b[0], b[1], b[2], 0, TAU); });
  ctx.lineWidth = r * .12; ctx.strokeStyle = INK; ctx.stroke();
  ctx.beginPath(); blobs.forEach(b => { ctx.moveTo(b[0] + b[2], b[1]); ctx.arc(b[0], b[1], b[2], 0, TAU); }); ctx.fillStyle = col; ctx.fill();
  ctx.beginPath(); blobs.forEach(b => { ctx.moveTo(b[0] + b[2] * .6, b[1] - b[2] * .25); ctx.arc(b[0] - b[2] * .1, b[1] - b[2] * .25, b[2] * .5, 0, TAU); });
  ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.fill();
  ctx.restore();
}
// comic impact star
function burst(ctx, x, y, r, n = 11, fill = '#ffd23a', seed = 5, inner = .55) {
  const R = rng(seed); const pts = [];
  for (let i = 0; i < n * 2; i++) { const a = i / (n * 2) * TAU; const rr = i % 2 ? r * inner * (.85 + R() * .3) : r * (.8 + R() * .4); pts.push([x + Math.cos(a) * rr, y + Math.sin(a) * rr]); }
  path(ctx, pts); fillStroke(ctx, fill, r * .07);
}
function star5(ctx, x, y, r, rot = 0, fill = '#ffe14d') {
  const pts = []; for (let i = 0; i < 10; i++) { const a = rot - Math.PI / 2 + i * Math.PI / 5; const rr = i % 2 ? r * .45 : r; pts.push([x + Math.cos(a) * rr, y + Math.sin(a) * rr]); }
  path(ctx, pts); fillStroke(ctx, fill, r * .18);
}
function sweat(ctx, x, y, s, a = 1) {
  ctx.save(); ctx.globalAlpha = a; ctx.beginPath();
  ctx.moveTo(x, y - s); ctx.quadraticCurveTo(x + s * .7, y, x, y + s * .55); ctx.quadraticCurveTo(x - s * .7, y, x, y - s);
  fillStroke(ctx, '#8fd8ff', s * .16); circle(ctx, x - s * .12, y + s * .05, s * .14); ctx.fillStyle = '#fff'; ctx.fill(); ctx.restore();
}
function text(ctx, str, x, y, size, fill = '#fff', stroke = INK, sw = 0, font = 'Poppins', weight = 700, align = 'center') {
  ctx.font = `${weight} ${size}px ${font}`; ctx.textAlign = align; ctx.textBaseline = 'middle';
  if (sw) { ctx.lineWidth = sw; ctx.strokeStyle = stroke; ctx.lineJoin = 'round'; ctx.strokeText(str, x, y); }
  ctx.fillStyle = fill; ctx.fillText(str, x, y);
}
