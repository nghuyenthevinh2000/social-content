// ---------- characters ----------
const YOU = { cols: PAL.red, hat: 'bandana', hatCol: '#d8312b', dotCol: '#fff' };
const PATCH = { cols: PAL.yellow, hat: 'bandana', hatCol: '#6c43c0', dotCol: '#fff' };
const SAILOR = { cols: PAL.blue, hat: 'sailor', belt: false };
const C = (base, extra) => Object.assign({}, base, extra);
const walkLegs = (t, sp = 9, amp = .55) => ({ L: [Math.sin(t * sp) * amp + .05, -Math.max(0, Math.sin(t * sp + 1)) * .7], R: [-Math.sin(t * sp) * amp + .05, -Math.max(0, -Math.sin(t * sp + 1)) * .7] });
const walkArms = (t, sp = 9, amp = .6) => ({ L: [.3 - Math.sin(t * sp) * amp, -.3], R: [.3 + Math.sin(t * sp) * amp, -.3] });
const handheld = (t, a = 4) => shake(t * .35, a, 1, 2);

// deck background (sky, sea, pillars, bulwark, floor)
function deckBG(ctx, t, cam, o = {}) {
  applyCam(ctx, cam, .08); drawSky(ctx, o.skyTop, o.skyBot);
  if (o.sun) { applyCam(ctx, cam, .1); drawSun(ctx, o.sun[0], o.sun[1], o.sun[2], t, o.sunPow || 1); }
  applyCam(ctx, cam, .14);
  drawCloud(ctx, 160 + t * 6, 260, 120, 1); drawCloud(ctx, 760 + t * 4, 150, 90, 2); drawCloud(ctx, 1050 + t * 5, 420, 70, 3, .9); drawCloud(ctx, -100 + t * 5, 520, 80, 4, .9);
  applyCam(ctx, cam, .3); drawPillars(ctx, o.horizon || 760, o.set || 'A');
  applyCam(ctx, cam, .45); drawSea(ctx, o.horizon || 760, t);
  if (o.farShip) { drawShip(ctx, o.farShip[0], (o.horizon || 760) + 40, o.farShip[1], t, { skull: true, flag: '#1b1820', hull: '#3d2a2a', ph: 1 }); }
  applyCam(ctx, cam, 1);
  drawBulwark(ctx, o.back || 1000, o.wallH || 140);
  drawDeckFloor(ctx, o.back || 1000, o.vx || 540);
}
function caribbeanHeat(ctx, a) { if (a <= 0) return; ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'screen'; const g = ctx.createRadialGradient(900, 200, 50, 900, 200, 1500); g.addColorStop(0, `rgba(255,220,120,${.55 * a})`); g.addColorStop(1, `rgba(255,170,60,${.12 * a})`); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); ctx.restore(); }

const SHOTS = [];
// A — hook: patch lifted, eye is fine
SHOTS.push({ start: 0, end: 3.8, tr: 'whip', draw(ctx, lt, t) {
  const hh = handheld(t, 3);
  const cam = { x: 540 + hh[0], y: 900 + hh[1] - lt * 10, z: 1 + lt * .035, r: Math.sin(t * .5) * .006 };
  ctx.save(); ctx.filter = 'blur(5px)'; deckBG(ctx, t, cam, { sun: [900, 160, 70], sunPow: .7 });
  applyCam(ctx, cam, 1); drawBarrel(ctx, 140, 1260, 1.6); drawCannon(ctx, 980, 1240, 1.2, -.05, -1);
  drawStick(ctx, C(YOU, { x: 260, y: 1180, s: 330, face: { eyes: 'normal', look: [.6, 0], mouth: 'smile' }, arms: { L: [.3, -.1], R: [2.4, .4] } }));
  ctx.restore();
  applyCam(ctx, cam, 1);
  const lift = kf(lt, [[2.82, 0], [3.12, 1, backOut]]);
  const reach = kf(lt, [[2.5, 0], [2.85, 1]]);
  const handTgt = [lerp(-.33, -.09, reach), lerp(-.42, -.8 - lift * .1, reach)];
  const blink = (lt > 1.2 && lt < 1.32) ? 1 : 0;
  drawStick(ctx, C(PATCH, {
    x: 540, y: 2050, s: 1500, bob: Math.sin(t * 3) * .004, headTilt: Math.sin(t * 1.6) * .03 + (lt > 3.1 ? -.06 : 0),
    patch: { pos: -1, lift }, armLen: 1.2,
    arms: { L: reach > 0 ? { ik: handTgt, bend: -1 } : [.25, -.1], R: [.95, -2.1] },
    face: { eyes: 'normal', look: lt > 3.15 ? [0, 0] : [0, 0], blink, mouth: lt > 3.0 ? 'grin' : 'smirk', browOne: lt > 3.0 ? -1 : (lt > .4 ? 1 : 0), browAng: 0 }, shadow: false,
  }));
  // reveal sparkle on the healthy eye
  const sa = kf(lt, [[3.05, 0], [3.2, 1], [3.6, 0]]);
  sparkle(ctx, 540 - .072 * 1500 + 70, 2050 - .77 * 1500 - 60, 70 * sa, sa);
} });
// B — wide seascape: boarding under the sun
SHOTS.push({ start: 3.8, end: 5.45, tr: 'whip', draw(ctx, lt, t) {
  const hh = handheld(t, 3);
  const cam = { x: 540 + hh[0] + lt * 25, y: 820 + hh[1], z: 1.0 + lt * .06, r: 0 };
  applyCam(ctx, cam, .08); drawSky(ctx, '#4aaeea', '#fbe9c4', -300, 950);
  applyCam(ctx, cam, .1); drawSun(ctx, 820, 330, 95, t, 1.3);
  applyCam(ctx, cam, .15); drawCloud(ctx, 150, 420, 110, 5); drawCloud(ctx, 1000, 560, 80, 6);
  applyCam(ctx, cam, .3); drawPillars(ctx, 930, 'B');
  applyCam(ctx, cam, .55); drawSea(ctx, 930, t);
  applyCam(ctx, cam, 1);
  drawShip(ctx, 850, 1250, .9, t, { flag: '#2a63c8', hull: '#9a5428', ph: 2, flip: -1 });
  drawShip(ctx, 280, 1420, 1.1, t, { skull: true, flag: '#1b1820', hull: '#3b2a2c', stripe: '#c9a14a', sail: '#e9dfc9', ph: 0 });
  // grapple ropes + tiny swinging pirate
  for (let i = 0; i < 3; i++) line(ctx, 420 + i * 60, 1300 - i * 6, 640 + i * 50, 1170 - i * 4, 4, '#4a3424');
  const th = kf(lt, [[0, -.7], [1.6, .55]]);
  const px = 560, py = 760, L = 330; const hx = px + Math.sin(th) * L, hy = py + Math.cos(th) * L;
  line(ctx, px, py, hx, hy, 3, '#4a3424');
  drawStick(ctx, C(YOU, { x: hx, y: hy + 62, s: 70, shadow: false, arms: { L: [.3, -.2], R: { ik: [(0) / 70 * 0 + .02, -.95] } }, legs: { L: [.6, -.9], R: [.4, -.8] }, face: { eyes: 'wide', mouth: 'grin' } }));
  const foam = 1;
  
  caribbeanHeat(ctx, .35);
} });
// C — swing onto the deck, squint at the sun
SHOTS.push({ start: 5.45, end: 8.2, tr: 'whip', draw(ctx, lt, t) {
  const land = .82;
  const p = clamp(lt / land);
  const bx = kf(lt, [[0, -260], [land, 600]], x => x), by = kf(lt, [[0, 900], [land * .55, 1180, easeOut], [land, 1640, easeIn]], x => x);
  const hh = handheld(t, 4);
  const cam = { x: lerp(330, 560, ease(clamp(lt / 1.1))) + hh[0], y: lerp(1150, 1200, ease(clamp(lt / 1.2))) + hh[1], z: kf(lt, [[0, 1.0], [1.0, 1.05], [2.75, 1.22]]), r: 0 };
  deckBG(ctx, t, cam, { sun: [900, 210, 90], sunPow: 1.25, farShip: [-150, .55] });
  applyCam(ctx, cam, 1);
  drawMast(ctx, 160, -900, 1060, 70); drawRigging(ctx, 330, 1000, 200, 200, 9, 110);
  drawBarrel(ctx, 960, 1180, 1.05); drawBarrel(ctx, 860, 1230, 1.1);
  drawCrate(ctx, 1040, 1300, 180, 150, 0, 'TEA');
  // rope
  const pivot = [520, -700];
  const flying = lt < land;
  const hand = [bx + 70, by - 560];
  if (flying) line(ctx, pivot[0], pivot[1], hand[0], hand[1], 7, '#6a4a2c');
  else { const sw = Math.sin((lt - land) * 5) * Math.exp(-(lt - land) * 2) * 120; line(ctx, pivot[0], pivot[1], 520 + 180 + sw, 1000, 7, '#6a4a2c'); }
  const sq = flying ? 1 : kf(lt, [[land, .82], [land + .25, 1, backOut]]);
  const squint = lt > 1.15;
  const handOverEyes = kf(lt, [[1.05, 0], [1.35, 1]]);
  drawStick(ctx, C(YOU, {
    x: bx, y: by, s: 600, squash: sq, lean: flying ? .2 : Math.sin(t * 2) * .02,
    arms: flying ? { L: [.6, -.3], R: { ik: [(hand[0] - bx) / 600, (hand[1] - by) / 600] } }
      : (handOverEyes > 0 ? { L: [.35, -.15], R: { ik: [lerp(.3, .03, handOverEyes), lerp(-.5, -.9, handOverEyes)], bend: -1 } } : POSE.idle.arms),
    armLen: 1.15,
    legs: flying ? { L: [.9, -1.2], R: [.6, -1.0] } : { L: [.18, -.05], R: [.18, -.05] },
    face: squint ? { eyes: 'squint', mouth: 'teeth', browAng: .3 } : { eyes: 'wide', mouth: flying ? 'grin' : 'o', look: [.3, -.3] },
    headTilt: squint ? -.12 : 0,
  }));
  if (!flying) { const pa = kf(lt, [[land, 1], [land + .5, 0]]); puff(ctx, bx - 160, by - 20, 70 * (1 + (lt - land)), t, '#efe3cf', 3, pa); puff(ctx, bx + 160, by - 20, 70 * (1 + (lt - land)), t, '#efe3cf', 4, pa); }
  if (squint) { const sa = clamp((lt - 1.4) * 3); sweat(ctx, bx + 150, by - 560 + (lt - 1.4) * 60, 34, sa); sweat(ctx, bx - 160, by - 520 + (lt - 1.7) * 50, 26, clamp((lt - 1.7) * 3)); }
  caribbeanHeat(ctx, .45 + (squint ? .25 + Math.sin(t * 6) * .05 : 0));
} });
// D — crew panics and hides below deck
function hatchFall(ctx, ch, x0, y0, jumpT, lt, hatch, extra) {
  // run from x0 to hatch center then jump in
  const runDur = .45; const hx = hatch.cx + clamp((x0 - hatch.cx) * .3, -110, 110);
  const tp = lt - jumpT;
  let x = x0, y = y0, legs, arms = POSE.handsUp.arms, lean = 0;
  if (tp < -runDur) { legs = { L: [Math.sin(lt * 30) * .15 + .2, -.1], R: [-Math.sin(lt * 30) * .15 + .2, -.1] }; y = y0 - Math.abs(Math.sin(lt * 15)) * 40; }
  else if (tp < 0) { const k = (tp + runDur) / runDur; x = lerp(x0, hx, k); y = lerp(y0, hatch.cy - 10, k) - Math.abs(Math.sin(lt * 18)) * 30; legs = walkLegs(lt, 22, .7); arms = { L: [2.6 + Math.sin(lt * 22) * .3, .2], R: [2.6 - Math.sin(lt * 22) * .3, .2] }; lean = (hx - x0) > 0 ? .15 : -.15; }
  else { x = hx; y = hatch.cy - 10 - 110 * Math.sin(Math.min(tp, .35) / .35 * Math.PI / 2) + Math.max(0, tp - .35) * Math.max(0, tp - .35) * 9000 * 0 + (tp > .35 ? (tp - .35) * (tp - .35) * 7000 : 0) - (tp < .35 ? 0 : 0); legs = { L: [.5, -.9], R: [.5, -.9] }; arms = POSE.handsUp.arms; }
  if (tp > .35) y = hatch.cy - 120 + (tp - .35) * (tp - .35) * 12000;
  const inHole = tp > 0.2;
  ctx.save();
  if (inHole) { ctx.beginPath(); ctx.rect(-3000, -3000, 7000, 3000 + hatch.front); ctx.clip(); }
  if (y - 800 < hatch.front + 40) drawStick(ctx, C(ch, Object.assign({ x, y, legs, arms, lean, shadow: !inHole }, extra)));
  ctx.restore();
}
SHOTS.push({ start: 8.2, end: 10.6, tr: 'cut', draw(ctx, lt, t) {
  const hh = handheld(t, 4);
  const cam = { x: 540 + hh[0], y: 1150 + hh[1], z: kf(lt, [[0, 1.0], [2.4, 1.1]]), r: .0 };
  deckBG(ctx, t, cam, { sun: [880, 160, 70], back: 860, wallH: 130, horizon: 640 });
  applyCam(ctx, cam, 1);
  drawMast(ctx, 920, -900, 920, 66);
  drawBarrel(ctx, 110, 1080, 1.0); drawBarrel(ctx, 230, 1120, 1.05);
  const hatch = { cx: 540, cy: 1420, w: 420, h: 170 }; const g = drawHatch(ctx, hatch.cx, hatch.cy, hatch.w, hatch.h); hatch.front = g.front;
  const panic = lt > .25;
  const crew = [[230, 1500, 1.05, 'L'], [860, 1460, 1.38, 'R'], [690, 1750, 1.7, 'R']];
  // pre-panic idle faces
  for (const [x0, y0, jt, side] of crew) {
    const face = panic ? { eyes: 'wide', mouth: 'teeth', browAng: -.35, browUp: 1 } : { eyes: 'normal', mouth: 'smile', look: [side === 'L' ? .8 : -.8, 0] };
    if (!panic) drawStick(ctx, C(SAILOR, { x: x0, y: y0, s: 470, face, arms: POSE.idle.arms }));
    else hatchFall(ctx, SAILOR, x0, y0, jt, lt, hatch, { s: 470, face });
  }
  // the pirate shows up at the edge
  drawStick(ctx, C(YOU, { x: kf(lt, [[0, -250], [.7, 120]]), y: 1830, s: 700, face: { eyes: 'normal', mouth: 'grin', look: [1, 0], browAng: .3 }, arms: { L: [.4, -.2], R: [1.9, -.6] },
    prop: (c, k, h, a, side) => { if (k === 'R') { c.save(); c.translate(h[0], h[1]); c.rotate(-side * 2.6); rrect(c, -.012, -.33, .024, .32, .01); fillStroke(c, '#d8dde6', .012); rrect(c, -.04, -.02, .08, .02, .01); fillStroke(c, '#e2b84a', .01); c.restore(); } } }));
  if (panic) { for (const [x0, y0, jt] of crew) if (lt < jt - .2) sweat(ctx, x0 + 120, y0 - 470, 26, 1); }
  if (lt > .25 && lt < .8) { text(ctx, '!', 230, 920, 120, '#ffe14d', INK, 14, 'Poppins', 700); text(ctx, '!', 860, 880, 120, '#ffe14d', INK, 14, 'Poppins', 700); }
} });
// E — you jump in after them
SHOTS.push({ start: 10.6, end: 12.45, tr: 'cut', draw(ctx, lt, t) {
  const hh = handheld(t, 4);
  const cam = { x: 540 + hh[0], y: 1250 + hh[1] + kf(lt, [[.4, 0], [1.4, 120]]), z: kf(lt, [[0, 1.15], [1.85, 1.35]]), r: 0 };
  deckBG(ctx, t, cam, { sun: [880, 160, 70], back: 860, wallH: 130, horizon: 640 });
  applyCam(ctx, cam, 1);
  drawMast(ctx, 920, -900, 920, 66); drawBarrel(ctx, 110, 1080, 1.0); drawBarrel(ctx, 230, 1120, 1.05);
  const hatch = { cx: 540, cy: 1420, w: 420, h: 170 }; const g = drawHatch(ctx, hatch.cx, hatch.cy, hatch.w, hatch.h); hatch.front = g.front;
  // you: run in from right, determined face, jump at 0.45
  const jt = .62;
  hatchFall(ctx, YOU, 980, 1650, jt, lt, hatch, { s: 560, face: lt < jt ? { eyes: 'normal', mouth: 'grin', browAng: .35, look: [-.6, .3] } : { eyes: 'wide', mouth: 'o', browUp: 1 }, flip: 1 });
  if (lt > jt + .55) { const a = clamp((lt - jt - .55) * 3) * clamp((1.85 - lt) * 4); puff(ctx, 540, 1400, 90, t, '#e7d6bc', 9, a * .9); }
} });
// F — black: only his eyes
SHOTS.push({ start: 12.45, end: 13.9, tr: 'whip', draw(ctx, lt, t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = '#050407'; ctx.fillRect(0, 0, W, H);
  const hh = handheld(t, 3);
  const cam = { x: 540 + hh[0], y: 960 + hh[1], z: 1 + lt * .06, r: 0 };
  applyCam(ctx, cam, 1);
  const look = kf(lt, [[0, [0, 0]], [.25, [-1, 0]], [.6, [-1, 0]], [.75, [1, 0]], [1.1, [1, 0]], [1.25, [0, .2]]], ease);
  const blink = (lt > .1 && lt < .2) || (lt > 1.3 && lt < 1.4) ? 1 : 0;
  drawStick(ctx, C(YOU, { x: 540, y: 960 + .765 * 2400, s: 2400, sil: '#09070b', eyesGlow: true, face: { eyes: 'normal', look, blink, pupil: .25 }, shadow: false }));
  const sa = clamp((lt - .5) * 3); sweat(ctx, 540 + 330, 760 + (lt - .5) * 50, 50, sa * .9);
} });
// G — explainer: pupil + 25 minutes
SHOTS.push({ start: 13.9, end: 18.45, tr: 'cut', draw(ctx, lt, t) {
  const dark = kf(lt, [[1.45, 0], [2.0, 1]]);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const g = ctx.createRadialGradient(540, 900, 50, 540, 900, 1300);
  g.addColorStop(0, mix('#fff2b0', '#1d2a55', dark)); g.addColorStop(.5, mix('#ffc94d', '#121a3a', dark)); g.addColorStop(1, mix('#f08a2a', '#070a18', dark));
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  // rays in sun phase
  if (dark < 1) { ctx.save(); ctx.globalAlpha = 1 - dark; ctx.translate(540, 980); ctx.rotate(t * .2); for (let i = 0; i < 16; i++) { ctx.rotate(TAU / 16); path(ctx, [[-60, 300], [60, 300], [0, 1500]]); ctx.fillStyle = 'rgba(255,255,255,.18)'; ctx.fill(); } ctx.restore(); }
  else { const R = rng(3); for (let i = 0; i < 40; i++) { circle(ctx, R() * W, R() * 1300, 2 + R() * 3); ctx.fillStyle = `rgba(200,220,255,${.3 + .3 * Math.sin(t * 3 + i)})`; ctx.fill(); } }
  const hh = handheld(t, 3);
  const cam = { x: 540 + hh[0], y: 960 + hh[1], z: kf(lt, [[0, 1.12], [.5, 1.0, easeOut], [4.5, 1.06]]), r: 0 };
  applyCam(ctx, cam, 1);
  // big eye
  const ex = 540, ey = 1010, rx = 360, ry = 250;
  const lid = kf(lt, [[0, .45], [1.6, .45], [2.1, .05]]);
  const eyeShape = () => { ctx.beginPath(); ctx.moveTo(ex - rx, ey); ctx.quadraticCurveTo(ex, ey - ry * 1.55 * (1 - lid * .6), ex + rx, ey); ctx.quadraticCurveTo(ex, ey + ry * 1.55 * (1 - lid * .4), ex - rx, ey); ctx.closePath(); };
  eyeShape(); fillStroke(ctx, '#fbf8f2', 12);
  ctx.save(); eyeShape(); ctx.clip();
  ellipse(ctx, ex, ey + 40, rx, ry, 0); ctx.fillStyle = 'rgba(150,140,170,.15)';
  const ir = 190;
  circle(ctx, ex, ey, ir); fillStroke(ctx, '#3e9bb0', 10);
  ctx.strokeStyle = 'rgba(20,70,90,.5)'; ctx.lineWidth = 6; for (let i = 0; i < 28; i++) { const a = i / 28 * TAU; line(ctx, ex + Math.cos(a) * 60, ey + Math.sin(a) * 60, ex + Math.cos(a) * 175, ey + Math.sin(a) * 175, 5, 'rgba(20,70,90,.45)'); }
  circle(ctx, ex, ey, ir * .98); ctx.lineWidth = 16; ctx.strokeStyle = 'rgba(20,50,70,.35)'; ctx.stroke();
  const pr = lt < 1.9 ? 34 + Math.sin(t * 12) * 2 : lerp(34, 150, easeOut(clamp((lt - 1.9) / 2.4)));
  circle(ctx, ex, ey, pr); ctx.fillStyle = '#0d0b12'; ctx.fill();
  circle(ctx, ex - 70, ey - 70, 34); ctx.fillStyle = 'rgba(255,255,255,.9)'; ctx.fill();
  circle(ctx, ex + 50, ey + 60, 14); ctx.fillStyle = 'rgba(255,255,255,.7)'; ctx.fill();
  // lid shadow
  ctx.fillStyle = 'rgba(80,60,90,.18)'; ctx.fillRect(ex - rx, ey - ry * 2, rx * 2, ry * .9 + lid * 150);
  ctx.restore();
  eyeShape(); fillStroke(ctx, null, 12);
  // lashes
  for (let i = 0; i < 5; i++) { const k = (i + 1) / 6; const lx = lerp(ex - rx, ex + rx, k); const ly = ey - ry * 1.55 * (1 - lid * .6) * (1 - Math.pow(2 * k - 1, 2)) * .5 - 4; line(ctx, lx, ly, lx + (k - .5) * 50, ly - 50, 12); }
  // pupil arrows in dark phase
  if (lt > 2.0 && lt < 4.2) { const a = clamp((lt - 2) * 3) * clamp((4.2 - lt) * 3); ctx.save(); ctx.globalAlpha = a; for (const sd of [-1, 1]) { const ax = ex + sd * (pr + 40); line(ctx, ax, ey, ax + sd * 70, ey, 10, '#ffe14d'); path(ctx, [[ax + sd * 95, ey], [ax + sd * 60, ey - 25], [ax + sd * 60, ey + 25]]); fillStroke(ctx, '#ffe14d', 0); } ctx.restore(); }
  // sun icon / pocket watch
  const cx = 540, cy = 470, cr = 165;
  const watchIn = kf(lt, [[1.7, 0], [2.1, 1, backOut]]);
  const sunIn = 1 - kf(lt, [[1.4, 0], [1.7, 1]]);
  if (sunIn > 0) { ctx.save(); ctx.translate(cx, cy); ctx.scale(sunIn, sunIn); circle(ctx, 0, 0, 110); fillStroke(ctx, '#fff3a6', 12); for (let i = 0; i < 10; i++) { const a = i / 10 * TAU + t; line(ctx, Math.cos(a) * 140, Math.sin(a) * 140, Math.cos(a) * 190, Math.sin(a) * 190, 14, INK); line(ctx, Math.cos(a) * 140, Math.sin(a) * 140, Math.cos(a) * 190, Math.sin(a) * 190, 6, '#fff3a6'); } ctx.restore(); }
  if (watchIn > 0) {
    ctx.save(); ctx.translate(cx, cy); ctx.scale(watchIn, watchIn); ctx.rotate(Math.sin(t * 3) * .04);
    circle(ctx, 0, -cr - 24, 28); fillStroke(ctx, '#e8c04a', 10); rrect(ctx, -22, -cr - 14, 44, 26, 6); fillStroke(ctx, '#e8c04a', 8);
    circle(ctx, 0, 0, cr); fillStroke(ctx, '#e8c04a', 12); circle(ctx, 0, 0, cr * .84); fillStroke(ctx, '#fbf6e8', 8);
    // filled wedge of elapsed time
    const el = easeOut(clamp((lt - 2.0) / .9)) * 25 / 60;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.arc(0, 0, cr * .78, -Math.PI / 2, -Math.PI / 2 + el * TAU); ctx.closePath(); ctx.fillStyle = 'rgba(70,120,230,.35)'; ctx.fill();
    for (let i = 0; i < 12; i++) { const a = i / 12 * TAU; line(ctx, Math.sin(a) * cr * .7, -Math.cos(a) * cr * .7, Math.sin(a) * cr * .78, -Math.cos(a) * cr * .78, 7); }
    const ma = -Math.PI / 2 + el * TAU; line(ctx, 0, 0, Math.cos(ma) * cr * .66, Math.sin(ma) * cr * .66, 12);
    line(ctx, 0, 0, Math.cos(-Math.PI / 2 + el * TAU / 12) * cr * .4, Math.sin(-Math.PI / 2 + el * TAU / 12) * cr * .4, 14);
    circle(ctx, 0, 0, 14); ctx.fillStyle = INK; ctx.fill();
    ctx.restore();
    const n = Math.round(easeOut(clamp((lt - 2.0) / .9)) * 25);
    const pop = 1 + .25 * Math.max(0, 1 - Math.abs(lt - 2.9) * 6);
    ctx.save(); ctx.translate(cx + 270, cy + 40); ctx.scale(pop * watchIn, pop * watchIn); ctx.rotate(.06);
    text(ctx, `${n} MIN`, 0, 0, 92, '#ffe14d', INK, 18, 'Poppins', 700); ctx.restore();
  }
} });
// H — smacked in the dark
SHOTS.push({ start: 18.45, end: 21.65, tr: 'whip', draw(ctx, lt, t) {
  const hit1 = 1.36, hit2 = 2.5;
  const sh1 = Math.max(0, 1 - (lt - hit1) * 4) * (lt > hit1 ? 1 : 0), sh2 = Math.max(0, 1 - (lt - hit2) * 4) * (lt > hit2 ? 1 : 0);
  const hk = shake(t * 3, 30 * (sh1 + sh2), 3);
  const hh = handheld(t, 3);
  const cam = { x: 540 + hh[0] + hk[0], y: 1080 + hh[1] + hk[1], z: kf(lt, [[0, 1.45], [3.2, 1.62]]), r: (sh1 - sh2) * .03 };
  applyCam(ctx, cam, 1);
  drawBelowDeck(ctx, .965); ctx.save(); ctx.setTransform(1,0,0,1,0,0); ctx.fillStyle = 'rgba(20,30,70,.25)'; ctx.fillRect(0,0,W,H); ctx.restore();
  const flash = Math.max(0, 1 - (lt - hit1) * 6) * (lt > hit1 ? 1 : 0) + Math.max(0, 1 - (lt - hit2) * 6) * (lt > hit2 ? 1 : 0);
  const silC = mix('#0c0a0e', '#5a4636', flash * .8);
  // sneaking sailors
  const s1 = kf(lt, [[0, -60], [1.0, 250]]), s2 = kf(lt, [[1.4, 1150], [2.3, 830]]);
  const swing1 = kf(lt, [[1.0, 2.9], [1.22, 2.95], [hit1, 1.25, easeIn], [hit1 + .3, 1.1]]);
  const swing2 = kf(lt, [[2.1, 2.9], [2.35, 2.95], [hit2, 1.25, easeIn], [hit2 + .3, 1.1]]);
  const pan = (sw) => (c, k, h, a, side) => { if (k === 'R') drawPan(c, h[0], h[1], .0017, side * (Math.PI - a), .9 - flash * .4); };
  drawStick(ctx, C(SAILOR, { x: s1, y: 1600, s: 620, sil: silC, eyesGlow: false, arms: { L: [.4, -.2], R: [swing1, -.2] }, propBehind: pan(swing1) }));
  drawStick(ctx, C(SAILOR, { x: s2, y: 1600, s: 620, flip: -1, sil: silC, eyesGlow: false, arms: { L: [.4, -.2], R: [swing2, -.2] }, propBehind: pan(swing2) }));
  // our hero (only eyes)
  const dazed = lt > hit2 ? 'spiral' : lt > hit1 ? 'x' : 'normal';
  const look = kf(lt, [[0, [0, 0]], [.4, [.9, 0]], [.8, [-.9, 0]], [1.2, [0, 0]]]);
  const tilt = lt > hit2 ? Math.sin(t * 5) * .2 : lt > hit1 ? .25 : 0;
  drawStick(ctx, C(YOU, { x: 540, y: 1620, s: 700, sil: silC, eyesGlow: true, headTilt: tilt, face: { eyes: dazed, look, pupil: .3, t }, arms: { L: [.5, -.4], R: [.5, -.4] } }));
  // impacts
  for (const [ht, bx] of [[hit1, 345], [hit2, 735]]) {
    const k = lt - ht; if (k > 0 && k < .5) { const sc = backOut(clamp(k / .12)) * (1 - clamp((k - .3) / .2)); ctx.save(); ctx.translate(bx, 860); ctx.scale(sc * .62, sc * .62); burst(ctx, 0, 0, 230, 12, '#ffd23a', 7 + ht * 10); burst(ctx, 0, 0, 120, 10, '#fff6c4', 9); text(ctx, 'BONK!', 0, 0, 96, '#e0392f', INK, 16, 'Poppins', 700); ctx.restore(); }
  }
  if (lt > hit2 + .1) { for (let i = 0; i < 3; i++) { const a = t * 5 + i * TAU / 3; star5(ctx, 540 + Math.cos(a) * 190, 960 + Math.sin(a) * 45, 32, t * 3, '#ffe14d'); } }
  if (flash > 0) { ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = `rgba(255,240,200,${flash * .35})`; ctx.fillRect(0, 0, W, H); ctx.restore(); }
} });
// I — buddy drops in, flips the patch
SHOTS.push({ start: 21.65, end: 25.1, tr: 'cut', draw(ctx, lt, t) {
  const land = .55;
  const hh = handheld(t, 3);
  const flipT = 1.92;
  const cam = { x: 540 + hh[0], y: kf(lt, [[0, 1000], [1.2, 1080]]) + hh[1], z: kf(lt, [[0, 1.0], [1.25, 1.75], [3.45, 1.95]]), r: 0 };
  applyCam(ctx, cam, 1);
  drawBelowDeck(ctx, .9);
  drawBarrel(ctx, 140, 1420, 1.3, .85); drawCrate(ctx, 930, 1430, 260, 220, .85);
  lightShaft(ctx, 540, -100, 380, 700, 1700, 1.3);
  const y = lt < land ? kf(lt, [[0, 300], [land, 1450, easeIn]]) : 1450;
  const sq = lt < land ? 1.05 : kf(lt, [[land, .85], [land + .25, 1, backOut]]);
  const pos = kf(lt, [[flipT, -1], [flipT + .3, 1, backOut]]);
  const reach = kf(lt, [[flipT - .3, 0], [flipT, 1], [flipT + .35, 1], [flipT + .6, 0]]);
  const handT = [lerp(-.3, lerp(-.09, .09, clamp((pos + 1) / 2)), reach), lerp(-.42, -.8, reach)];
  drawStick(ctx, C(PATCH, {
    x: 540, y, s: 620, squash: sq, patch: { pos, lift: 0 }, armLen: 1.2,
    arms: lt < land ? { L: [2.7, .2], R: [2.7, .2] } : { L: reach > 0 ? { ik: handT, bend: -1 } : [.3, -.1], R: [.9, -2.1] },
    legs: lt < land ? { L: [.15, -.3], R: [.15, -.3] } : { L: [.18, -.05], R: [.18, -.05] },
    face: { eyes: 'normal', pupil: lt > flipT ? .82 : .45, mouth: lt > flipT + .2 ? 'grin' : 'smirk', browAng: .25, look: [0, 0] },
  }));
  // shine on revealed eye
  const ga = kf(lt, [[flipT + .15, 0], [flipT + .3, 1], [flipT + .9, 0]]);
  sparkle(ctx, 540 - .072 * 620 - 30, 1450 - .77 * 620 - 40, 60 * ga, ga);
  
} });
// J — he can see everything
SHOTS.push({ start: 25.1, end: 28.95, tr: 'whip', draw(ctx, lt, t) {
  const hh = handheld(t, 3);
  const cam = { x: 540 + hh[0] + lt * 8, y: 1000 + hh[1], z: kf(lt, [[0, 1.08], [3.85, 1.0]]), r: 0 };
  applyCam(ctx, cam, 1);
  drawBelowDeck(ctx, .25);
  drawLantern(ctx, 300, 300, 1.1, 0, t);
  drawCrate(ctx, 120, 1450, 260, 230, .1, 'RUM');
  const seen = lt > 2.95;
  const sf = seen ? { eyes: 'wide', mouth: 'teeth', browUp: 1, browAng: -.3 } : { eyes: 'normal', mouth: 'smirk', browAng: .3, look: [-.4, 0] };
  const sx = [[340, 1380], [700, 1360], [940, 1420]];
  sx.forEach(([x, y], i) => {
    const pop = seen ? kf(lt, [[2.95, 0], [3.1, 60]], easeOut) : 0;
    drawStick(ctx, C(SAILOR, { x, y: y - pop, s: 520, face: sf, arms: seen ? POSE.handsUp.arms : { L: [.4, -.3], R: [2.6, .3] }, propBehind: (c, k, h, a, side) => { if (k === 'R') drawPan(c, h[0], h[1], .0017, side * (Math.PI - a), 0); } }));
  });
  drawBarrel(ctx, 300, 1640, 1.55); drawBarrel(ctx, 700, 1640, 1.55); drawBarrel(ctx, 1000, 1690, 1.5);
  // knocked out hero on the floor
  ctx.save(); ctx.translate(560, 1850); ctx.rotate(-Math.PI / 2 + .1);
  drawStick(ctx, C(YOU, { x: 0, y: 0, s: 420, shadow: false, face: { eyes: 'spiral', mouth: 'o', t }, arms: { L: [1.4, .3], R: [1.6, .2] }, legs: { L: [.4, 0], R: [.2, 0] } }));
  ctx.restore();
  if (seen) { const sa = clamp((lt - 3.0) * 4); [[340, 1380], [700, 1360], [940, 1420]].forEach(([x, y]) => sweat(ctx, x + 110, y - 470, 26, sa)); }
  // dark-adapted vision reveal
  const r = kf(lt, [[.25, 0], [3.0, 1500, easeIn]]);
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalCompositeOperation = 'multiply'; ctx.fillStyle = mix('#ffffff', '#8ba6d6', clamp(1 - (lt - 3.1) * 2)); ctx.fillRect(0, 0, W, H);
  ctx.globalCompositeOperation = 'source-over';
  const g = ctx.createRadialGradient(540, 1000, Math.max(1, r), 540, 1000, r + 260);
  g.addColorStop(0, 'rgba(5,4,7,0)'); g.addColorStop(1, 'rgba(5,4,7,.96)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  // iris ring
  if (r > 10 && r < 1400) { circle(ctx, 540, 1000, r + 20); ctx.lineWidth = 10; ctx.strokeStyle = `rgba(120,200,255,${.35 * (1 - r / 1400)})`; ctx.stroke(); }
  ctx.restore();
} });
// K — tested: plausible stamp
SHOTS.push({ start: 28.95, end: 32.25, tr: 'whip', draw(ctx, lt, t) {
  const st = 2.6; const k = lt - st;
  const sh = k > 0 ? Math.max(0, 1 - k * 3.5) : 0; const hk = shake(t * 3, 26 * sh, 3);
  const hh = handheld(t, 3);
  const cam = { x: 540 + hh[0] + hk[0], y: 960 + hh[1] + hk[1], z: kf(lt, [[0, 1.08], [3.3, 1.0]]), r: -.02 + lt * .006 };
  applyCam(ctx, cam, 1);
  // table
  ctx.fillStyle = '#7a4527'; ctx.fillRect(-500, -500, 2100, 2900);
  for (let y = -500; y < 2400; y += 190) { line(ctx, -500, y, 1600, y + 20, 6, '#5e321b'); }
  // paper
  ctx.save(); ctx.translate(540, 850); ctx.rotate(-.04); ctx.scale(.92, .92);
  ctx.fillStyle = 'rgba(0,0,0,.3)'; ctx.fillRect(-400, -560, 820, 1140);
  rrect(ctx, -420, -580, 820, 1140, 14); fillStroke(ctx, '#f5ead2', 8);
  text(ctx, 'EYE PATCH', 0, -470, 104, '#4a2614', null, 0, 'Lora', 700);
  text(ctx, 'THEORY', 0, -360, 104, '#4a2614', null, 0, 'Lora', 700);
  line(ctx, -300, -290, 300, -290, 6, '#4a2614');
  // doodle head with patch
  ctx.save(); ctx.translate(-10, -60); circle(ctx, 0, 0, 120); fillStroke(ctx, '#fffaf0', 8); ellipse(ctx, -45, -5, 34, 30); ctx.fillStyle = '#2a2026'; ctx.fill(); line(ctx, -120, -40, 120, -50, 6, '#2a2026'); circle(ctx, 45, -5, 26); fillStroke(ctx, '#fff', 6); circle(ctx, 45, -5, 16); ctx.fillStyle = '#2a2026'; ctx.fill(); ctx.beginPath(); ctx.arc(0, 50, 34, .3, Math.PI - .3); ctx.lineWidth = 7; ctx.strokeStyle = '#2a2026'; ctx.stroke(); ctx.restore();
  const items = ['Patch on in the sun', 'Run into the dark', 'Flip the patch'];
  items.forEach((s, i) => {
    const y = 170 + i * 110; rrect(ctx, -330, y - 32, 64, 64, 8); fillStroke(ctx, '#fffaf0', 6);
    text(ctx, s, -235, y, 54, '#4a2614', null, 0, 'Lora', 600, 'left');
    const ck = kf(lt, [[.9 + i * .35, 0], [1.1 + i * .35, 1, backOut]]);
    if (ck > 0) { ctx.save(); ctx.translate(-298, y); ctx.scale(ck, ck); ctx.beginPath(); ctx.moveTo(-26, 0); ctx.lineTo(-6, 22); ctx.lineTo(34, -34); ctx.lineWidth = 14; ctx.strokeStyle = '#2f9a4a'; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.stroke(); ctx.restore(); }
  });
  // stamp ink
  if (k > 0) {
    ctx.save(); ctx.translate(20, -20); ctx.rotate(-.22);
    const sc = k < .08 ? 1.15 - k : 1;
    ctx.scale(sc, sc);
    ctx.globalAlpha = .92;
    rrect(ctx, -380, -105, 760, 210, 24); ctx.lineWidth = 22; ctx.strokeStyle = '#d42a2a'; ctx.stroke();
    rrect(ctx, -350, -78, 700, 156, 14); ctx.lineWidth = 7; ctx.stroke();
    text(ctx, 'PLAUSIBLE', 0, 8, 128, '#d42a2a', null, 0, 'Poppins', 700);
    // rough ink texture
    ctx.globalCompositeOperation = 'destination-out'; const R = rng(77);
    for (let i = 0; i < 70; i++) { circle(ctx, -380 + R() * 760, -105 + R() * 210, 1.5 + R() * 3.5); ctx.fill(); }
    ctx.restore();
  }
  ctx.restore();
  // the stamp tool + arm
  const sy = k < 0 ? kf(lt, [[st - .55, -700], [st - .2, -160], [st, 540, easeIn]]) : kf(k, [[0, 540], [.12, 540], [.5, -900, easeIn]]);
  const sx = 560; const sy0 = -130;
  ctx.save(); ctx.translate(sx, sy + sy0); ctx.rotate(-.22);
  line(ctx, 60, -330, 300, -1400, 30, INK); circle(ctx, 40, -300, 40); ctx.fillStyle = INK; ctx.fill();
  rrect(ctx, -40, -330, 80, 200, 30); fillStroke(ctx, '#9a5a2a', 8);
  rrect(ctx, -240, -140, 480, 90, 16); fillStroke(ctx, '#b8733a', 8);
  rrect(ctx, -250, -60, 500, 60, 10); fillStroke(ctx, '#c03030', 8);
  ctx.restore();
  if (k > 0 && k < .6) { const a = 1 - k / .6; puff(ctx, 140, 1000, 90 + k * 160, t, '#f2e6cc', 21, a); puff(ctx, 980, 700, 80 + k * 160, t, '#f2e6cc', 22, a); }
} });
// L — finale: only one who could see
SHOTS.push({ start: 32.25, end: 37.4, tr: 'cut', draw(ctx, lt, t) {
  const hh = handheld(t, 3);
  const cam = { x: 540 + hh[0], y: kf(lt, [[0, 1000], [2.4, 1170]]) + hh[1], z: kf(lt, [[0, 1.6], [2.4, 1.0], [5.2, 1.05]]), r: 0 };
  applyCam(ctx, cam, 1);
  drawBelowDeck(ctx, .55);
  drawBarrel(ctx, 70, 1360, 1.2, .35); drawCrate(ctx, 1040, 1350, 220, 190, .35, 'RUM');
  // tied sailors bundle (right)
  for (const [x, i] of [[720, 0], [835, 1], [950, 2]]) {
    drawStick(ctx, C(SAILOR, { x, y: 1560, s: 400, face: { eyes: i === 1 ? 'half' : 'normal', mouth: 'frown', browAng: -.3, look: [-.8, 0] }, legs: { L: [1.5, -.2], R: [1.3, -.2] }, arms: { L: [.15, 0], R: [.15, 0] }, squash: .82 }));
  }
  rrect(ctx, 630, 1350, 420, 30, 14); fillStroke(ctx, '#c79a5a', 6); rrect(ctx, 630, 1405, 420, 28, 14); fillStroke(ctx, '#c79a5a', 6);

  // chest + patch hero
  drawChest(ctx, 480, 1480, 1.15, 1);
  // hero on the floor, dazed (left)
  ctx.save(); ctx.translate(40, 1720); ctx.rotate(Math.PI / 2 - .08);
  drawStick(ctx, C(YOU, { x: 0, y: 0, s: 380, flip: -1, shadow: false, face: { eyes: 'spiral', mouth: 'o', t }, arms: { L: [1.4, .3], R: [1.7, .2] }, legs: { L: [.4, 0], R: [.25, 0] } }));
  ctx.restore();
  for (let i = 0; i < 3; i++) { const a = t * 4 + i * TAU / 3; star5(ctx, 330 + Math.cos(a) * 80, 1700 + Math.sin(a) * 22, 22, t * 3); }
  const wink = lt > 3.9 && lt < 4.6;
  const handPatch = kf(lt, [[2.9, 0], [3.2, 1], [3.6, 1], [3.9, 0]]);
  drawStick(ctx, C(PATCH, {
    x: 480, y: 1310, s: 560, patch: { pos: 1, lift: 0 }, armLen: 1.2,
    arms: { L: handPatch > 0 ? { ik: [lerp(-.3, .05, handPatch), lerp(-.3, -.8, handPatch)], bend: -1 } : [.9, -2.1], R: [2.6, .25] },
    prop: (c, k, h) => { if (k === 'R') drawLantern(c, h[0], h[1] + .08, .0019, 1, t); },
    face: { eyes: 'normal', eyesL: wink ? 'happy' : undefined, pupil: .75, mouth: 'grin', browAng: .2, browOne: -1 },
    headTilt: Math.sin(t * 2) * .04,
  }));
  ctx.save(); ctx.globalCompositeOperation = 'lighter'; const g = ctx.createRadialGradient(600, 720, 20, 600, 720, 950); g.addColorStop(0, 'rgba(255,170,70,.32)'); g.addColorStop(1, 'rgba(255,120,40,0)'); ctx.fillStyle = g; ctx.fillRect(-400, -200, 1900, 2400); ctx.restore();
  const sa = kf(lt, [[3.9, 0], [4.05, 1], [4.6, 0]]);
  sparkle(ctx, 480 - .072 * 560 - 40, 1310 - .77 * 560 - 50, 55 * sa, sa);
} });
