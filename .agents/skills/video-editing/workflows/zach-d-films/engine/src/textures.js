import * as THREE from 'three';

// Deterministic RNG so every render is identical
export function rng(seed = 1) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function canvas(w, h = w) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return [c, c.getContext('2d')];
}

function tex(c, { repeat = [1, 1], srgb = false } = {}) {
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat[0], repeat[1]);
  t.anisotropy = 8;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// Smudgy / scratched steel: used as roughness + color variation
export function steelTextures(seed = 3) {
  const r = rng(seed);
  const S = 1024;
  const [c, g] = canvas(S);
  g.fillStyle = '#8a8a8a'; g.fillRect(0, 0, S, S);
  // blotches
  for (let i = 0; i < 260; i++) {
    const x = r() * S, y = r() * S, rad = 20 + r() * 120;
    const gr = g.createRadialGradient(x, y, 0, x, y, rad);
    const v = r() < 0.5 ? 40 : 200;
    gr.addColorStop(0, `rgba(${v},${v},${v},${0.06 + r() * 0.1})`);
    gr.addColorStop(1, `rgba(${v},${v},${v},0)`);
    g.fillStyle = gr; g.fillRect(x - rad, y - rad, rad * 2, rad * 2);
  }
  // fine scratches
  for (let i = 0; i < 1400; i++) {
    const x = r() * S, y = r() * S, a = r() * Math.PI, l = 4 + r() * 40;
    g.strokeStyle = `rgba(${r() < .5 ? 230 : 30},${r() < .5 ? 230 : 30},${r() < .5 ? 230 : 30},${0.08 + r() * 0.18})`;
    g.lineWidth = 0.6 + r() * 0.8;
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke();
  }
  // pits / dents
  for (let i = 0; i < 500; i++) {
    g.fillStyle = `rgba(20,20,20,${0.1 + r() * 0.3})`;
    g.beginPath(); g.arc(r() * S, r() * S, 0.5 + r() * 2.2, 0, 7); g.fill();
  }
  const rough = tex(c);
  // color map: same image remapped lighter
  const [c2, g2] = canvas(S);
  g2.drawImage(c, 0, 0);
  g2.globalCompositeOperation = 'screen';
  g2.fillStyle = 'rgba(150,150,155,1)'; g2.fillRect(0, 0, S, S);
  const color = tex(c2, { srgb: true });
  return { rough, color };
}

// Chainmail: rows of interlinked rings. Returns color, metalness/alpha and bump maps.
export function chainmailTextures(repeat = [10, 10]) {
  const S = 512, N = 8; // rings per tile row
  const step = S / N;
  const [c, g] = canvas(S);
  const [b, gb] = canvas(S);
  g.fillStyle = '#0b0b0c'; g.fillRect(0, 0, S, S);
  gb.fillStyle = '#000'; gb.fillRect(0, 0, S, S);
  const rows = N * 2;
  const rowH = S / rows;
  for (let row = -1; row <= rows + 1; row++) {
    for (let col = -1; col <= N + 1; col++) {
      const x = col * step + (row % 2 ? step / 2 : 0);
      const y = row * rowH;
      const tilt = row % 2 ? 0.45 : -0.45;
      for (const [ctx, isBump] of [[g, false], [gb, true]]) {
        ctx.save(); ctx.translate(x, y); ctx.rotate(tilt);
        // outer shading ring
        ctx.lineWidth = step * 0.17;
        if (isBump) {
          ctx.strokeStyle = '#fff';
        } else {
          const gr = ctx.createLinearGradient(-step * .4, -step * .3, step * .4, step * .3);
          gr.addColorStop(0, '#f2f2f2'); gr.addColorStop(.45, '#9a9a9e'); gr.addColorStop(1, '#4a4a4e');
          ctx.strokeStyle = gr;
        }
        ctx.beginPath(); ctx.ellipse(0, 0, step * 0.42, step * 0.3, 0, 0, Math.PI * 2); ctx.stroke();
        if (isBump) { ctx.lineWidth = step * 0.06; ctx.strokeStyle = '#888'; ctx.stroke(); }
        ctx.restore();
      }
    }
  }
  const color = tex(c, { repeat, srgb: true });
  const bump = tex(b, { repeat });
  return { color, bump };
}

export function woodTexture(seed = 7) {
  const r = rng(seed);
  const [c, g] = canvas(256, 1024);
  g.fillStyle = '#9a6b3f'; g.fillRect(0, 0, 256, 1024);
  for (let i = 0; i < 90; i++) {
    const x = r() * 256;
    g.strokeStyle = `rgba(${r() < .5 ? 70 : 170},${r() < .5 ? 45 : 120},${r() < .5 ? 20 : 70},${0.15 + r() * 0.3})`;
    g.lineWidth = 1 + r() * 4;
    g.beginPath(); g.moveTo(x, 0);
    for (let y = 0; y <= 1024; y += 64) g.lineTo(x + Math.sin(y * 0.01 + i) * 6, y);
    g.stroke();
  }
  return tex(c, { srgb: true });
}

export function fabricTexture(seed = 11) {
  const r = rng(seed);
  const [c, g] = canvas(256);
  g.fillStyle = '#808080'; g.fillRect(0, 0, 256, 256);
  for (let y = 0; y < 256; y += 2) for (let x = 0; x < 256; x += 2) {
    const v = 110 + ((x + y) % 4 ? 20 : -20) + r() * 30;
    g.fillStyle = `rgb(${v},${v},${v})`; g.fillRect(x, y, 2, 2);
  }
  return tex(c, { repeat: [6, 6] });
}

export function skinTexture(seed = 5) {
  const r = rng(seed);
  const [c, g] = canvas(256);
  g.fillStyle = '#808080'; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 3000; i++) {
    const v = 100 + r() * 60;
    g.fillStyle = `rgba(${v},${v},${v},0.5)`;
    g.fillRect(r() * 256, r() * 256, 1 + r() * 2, 1 + r() * 2);
  }
  return tex(c, { repeat: [3, 3] });
}

// soft radial sprite used for flashes, glows and sparks
export function glowTexture(inner = 'rgba(255,255,255,1)', outer = 'rgba(255,255,255,0)') {
  const [c, g] = canvas(128);
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, inner); gr.addColorStop(0.25, inner.replace(/[\d.]+\)$/, '0.6)')); gr.addColorStop(1, outer);
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
