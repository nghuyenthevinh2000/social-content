import * as THREE from 'three';

export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = t => { t = clamp(t); return t * t * (3 - 2 * t); };
export const easeOut = t => 1 - (1 - clamp(t)) ** 3;
export const easeIn = t => clamp(t) ** 3;
export const easeInOut = t => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2; };
export const range = (t, a, b) => clamp((t - a) / (b - a));

// keyframes: [[time, value(number|array)], ...]
export function kf(t, keys, ease = smooth) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, v0] = keys[i], [t1, v1] = keys[i + 1];
    if (t <= t1) {
      const k = ease((t - t0) / (t1 - t0));
      return Array.isArray(v0) ? v0.map((x, j) => lerp(x, v1[j], k)) : lerp(v0, v1, k);
    }
  }
  return keys[keys.length - 1][1];
}

export const V = (x, y, z) => new THREE.Vector3(x, y, z);

export function cam(fov = 35) {
  const c = new THREE.PerspectiveCamera(fov, 720 / 1280, 0.005, 300);
  return c;
}
export function place(c, pos, look, roll = 0) {
  c.position.set(...pos);
  c.up.set(Math.sin(roll), Math.cos(roll), 0);
  c.lookAt(...look);
}
// subtle handheld drift
export function shake(t, amp = 1, seed = 0) {
  const f = (a, b, c) => Math.sin(t * a + seed) * 0.5 + Math.sin(t * b + seed * 2.3) * 0.3 + Math.sin(t * c + seed * 4.1) * 0.2;
  return [f(1.3, 2.9, 5.1) * 0.006 * amp, f(1.7, 3.3, 4.7) * 0.006 * amp, f(0.9, 2.1, 6.3) * 0.004 * amp];
}

// ---- IK helpers ----
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _pq = new THREE.Quaternion();
const _x = new THREE.Vector3(), _y = new THREE.Vector3(), _z = new THREE.Vector3();
// orient group so local -Y points along dir (world), local +Z as close as possible to hint (world)
export function aimNegY(group, dir, hint) {
  _y.copy(dir).normalize().negate();
  _z.copy(hint).addScaledVector(_y, -hint.dot(_y));
  if (_z.lengthSq() < 1e-8) _z.set(0, 0, 1).addScaledVector(_y, -_y.z);
  _z.normalize();
  _x.crossVectors(_y, _z).normalize();
  _m.makeBasis(_x, _y, _z);
  _q.setFromRotationMatrix(_m);
  group.parent.getWorldQuaternion(_pq);
  group.quaternion.copy(_pq.invert().multiply(_q));
  group.updateMatrixWorld(true);
}

// two-bone arm IK: target is the fist centre (world). pole = where the elbow should point. hint = desired fist +Z (world)
export function ikArm(h, side, target, pole, hint, a = 0.3, b = 0.335) {
  const sh = h.j[side + 'Sh'], el = h.j[side + 'El'], wr = h.j[side + 'Wr'];
  h.root.updateMatrixWorld(true);
  const S = sh.getWorldPosition(new THREE.Vector3());
  const D = target.clone().sub(S);
  const d = Math.min(D.length(), a + b - 1e-3);
  const dir = D.normalize();
  const cosA = clamp((a * a + d * d - b * b) / (2 * a * d), -1, 1);
  const sinA = Math.sqrt(1 - cosA * cosA);
  const p = pole.clone().sub(S); p.addScaledVector(dir, -p.dot(dir)).normalize();
  const E = S.clone().addScaledVector(dir, a * cosA).addScaledVector(p, a * sinA);
  aimNegY(sh, E.clone().sub(S), hint);
  const T = S.clone().addScaledVector(dir, d);
  aimNegY(el, T.clone().sub(E), hint);
  wr.rotation.set(0, 0, 0); wr.updateMatrixWorld(true);
}
