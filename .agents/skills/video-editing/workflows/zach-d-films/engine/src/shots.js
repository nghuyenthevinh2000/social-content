import * as THREE from 'three';
import { makeHuman, standArmor } from './human.js';
import { gunArm, bullet, sword, shield, mace, arrow, bow, stand, glowSprite, sparks, streak, rippleOverlay } from './props.js';
import { materials } from './materials.js';
import { kf, lerp, smooth, easeOut, easeIn, easeInOut, range, clamp, V, cam, place, shake, ikArm } from './anim.js';

export const DURATION = 29.49;

// [start, text, end?]
export const CAPTIONS = [
  [0.0, 'If you shot'], [0.8, 'a bullet'], [1.4, 'at ancient armor'], [2.6, 'some people think'],
  [3.9, 'it could actually'], [4.7, 'stop the impact'], [6.1, 'But armor'], [6.7, 'like chain mail'],
  [7.9, 'was designed'], [8.6, 'to block'], [9.3, 'slashing swords'], [10.7, 'And plate armor'],
  [11.7, 'was even better'], [12.7, 'at deflecting'], [13.4, 'strikes'], [14.1, 'by spreading'],
  [14.9, 'the blunt force'], [15.9, 'across more area'], [17.3, 'lessening'], [18.0, 'its impact'],
  [18.9, 'But these materials'], [20.2, "weren't"], [20.5, 'very good'], [21.3, 'at stopping'],
  [22.0, 'arrows'], [22.7, 'which had'], [23.3, 'enough energy'], [24.2, 'to enter'], [24.8, 'the armor'],
  [25.4, 'So a bullet'], [26.3, 'would have'], [26.7, 'no trouble'], [27.5, 'going'], [28.0, 'right through', 28.8],
];
// [fadeInStart, fullStart, fullEnd, fadeOutEnd] to black
export const FADES = [[6.02, 6.2, 6.3, 6.46]];

const toWorld = (obj, v) => obj.localToWorld(v.clone());
function surfaceHit(scene, target, from, to) {
  scene.updateMatrixWorld(true);
  const rc = new THREE.Raycaster(from, to.clone().sub(from).normalize(), 0, 10);
  const hits = rc.intersectObject(target, false);
  if (!hits.length) return { point: to.clone(), normal: from.clone().sub(to).normalize() };
  const n = hits[0].face.normal.clone().transformDirection(target.matrixWorld);
  return { point: hits[0].point, normal: n };
}
function idle(t, k = 1) { return Math.sin(t * 1.6) * 0.012 * k; }

// relaxed standing pose
const STAND = {
  lSh: [0.05, 0, 0.16], rSh: [0.05, 0, -0.16], lEl: [-0.25, 0, 0], rEl: [-0.25, 0, 0],
  lHip: [0, 0, 0.07], rHip: [0, 0, -0.07], lAn: [0, 0, -0.07], rAn: [0, 0, 0.07],
};
function standPose(h, t, extra = {}) {
  const p = { ...STAND, ...extra };
  p.chest = [idle(t) + (extra.chest?.[0] || 0), extra.chest?.[1] || 0, extra.chest?.[2] || 0];
  h.setPose(p);
}

// ============ SHOT 1: gun fires at man in steel vest ============
function shot1({ makeStage }) {
  const scene = makeStage({ shadowSize: 2.5 });
  const man = makeHuman('vest'); man.root.rotation.y = -0.55; scene.add(man.root);
  const arm = gunArm(); scene.add(arm);
  const target = V(0.03, 1.36, 0.12);
  const gunPos = V(-0.5, 1.29, 1.15);
  arm.position.copy(gunPos);
  const dir = target.clone().sub(gunPos).normalize();
  arm.rotation.y = -Math.atan2(dir.z, dir.x); arm.rotation.z = Math.asin(dir.y);
  const flash = glowSprite(0xff7a8a, 0.12); scene.add(flash);
  const flash2 = glowSprite(0xffe0a0, 0.05); scene.add(flash2);
  const light = new THREE.PointLight(0xff9a70, 0, 2); scene.add(light);
  const b = bullet(1); scene.add(b);
  const bglow = glowSprite(0xff8a40, 0.03); scene.add(bglow);
  const c = cam(38);
  return {
    scene, camera: c,
    update(t) {
      standPose(man, t + 3, { neck: [0.05, -0.25, 0], head: [-0.02, -0.15, 0] });
      man.setMouth(0);
      scene.updateMatrixWorld(true);
      const muzzle = arm.localToWorld(arm.muzzle.clone());
      const f = t < 0.16 ? 1 - t / 0.16 : 0;
      flash.position.copy(muzzle).addScaledVector(dir, 0.03); flash.scale.setScalar(0.06 + 0.12 * f); flash.material.opacity = f;
      flash2.position.copy(muzzle).addScaledVector(dir, 0.01); flash2.scale.setScalar(0.08 * f + 0.001); flash2.material.opacity = f;
      light.position.copy(muzzle); light.intensity = 6 * f;
      // recoil
      arm.position.copy(gunPos).addScaledVector(dir, -0.02 * f);
      // slow-motion bullet
      const d = 0.12 + t * 0.2;
      b.position.copy(muzzle).addScaledVector(dir, d);
      b.quaternion.setFromUnitVectors(V(0, 1, 0), dir);
      b.scale.setScalar(1.2);
      bglow.position.copy(b.position); bglow.material.opacity = 0.35;
      const k = easeInOut(range(t, 0.15, 2.42));
      const p = [lerp(-0.8, -0.05, k), lerp(1.36, 1.52, k), lerp(2.3, 1.45, k)];
      const l = [lerp(-0.12, 0.0, k), lerp(1.31, 1.47, k), lerp(0.3, 0.05, k)];
      const s = shake(t, 0.6);
      place(c, [p[0] + s[0], p[1] + s[1], p[2]], l);
      return { dof: { focus: c.position.distanceTo(V(0, 1.45, 0.1)), aperture: 0.004, maxblur: 0.008 }, bloom: 0.6 };
    },
  };
}

// ============ SHOT 2: slow-mo bullet into the vest, flattens ============
function shot2({ makeStage }) {
  const scene = makeStage({ shadowSize: 1.5 });
  const man = makeHuman('vest'); man.root.rotation.y = -0.55; scene.add(man.root);
  standPose(man, 3, { neck: [0.05, -0.25, 0], head: [-0.02, -0.15, 0] });
  const from = V(-0.95, 1.33, 0.55), aim = V(0.03, 1.33, 0.12);
  const hit = surfaceHit(scene, man.armor.plate, from, aim);
  const dir = aim.clone().sub(from).normalize();
  const b = bullet(1); scene.add(b);
  const glow = glowSprite(0xff7a30, 0.05); scene.add(glow);
  const sp = sparks(120, { speed: 0.25, spread: 1.6, gravity: -0.4, life: 0.9, size: 0.0022, dir: hit.normal, seed: 3, color: [1, 0.45, 0.12] });
  sp.position.copy(hit.point); scene.add(sp);
  const puff = glowSprite(0xffb070, 0.01); puff.position.copy(hit.point).addScaledVector(hit.normal, 0.004); scene.add(puff);
  const light = new THREE.PointLight(0xff8040, 0, 0.5); light.position.copy(hit.point).addScaledVector(hit.normal, 0.03); scene.add(light);
  const c = cam(30);
  const TI = 2.95; // impact time (local)
  const side = new THREE.Vector3().crossVectors(dir, V(0, 1, 0)).normalize();
  return {
    scene, camera: c,
    update(t) {
      const before = Math.max(0, TI - t);
      const travel = before * 0.13;
      const squash = easeOut(range(t, TI, TI + 0.45));
      b.position.copy(hit.point).addScaledVector(dir, -travel - 0.0185 * (1 - squash * 0.4)).addScaledVector(dir, 0.004 * squash);
      b.quaternion.setFromUnitVectors(V(0, 1, 0), dir);
      b.morphTargetInfluences[0] = squash;
      b.material.emissiveIntensity = 0.4 + squash * 0.9;
      glow.position.copy(b.position).addScaledVector(dir, 0.012);
      glow.scale.setScalar(0.03 + squash * 0.03); glow.material.opacity = 0.2 + squash * 0.3;
      const it = t - TI;
      sp.update(it);
      puff.scale.setScalar(it > 0 ? 0.015 + it * 0.05 : 0.001); puff.material.opacity = it > 0 ? Math.max(0, 0.5 - it * 1.0) : 0;
      light.intensity = it > 0 ? 0.8 * Math.exp(-it * 2) : 0;
      // camera tracks the bullet from the side, drifting closer
      const k = range(t, 0, TI + 0.8);
      const dist = lerp(0.17, 0.11, easeInOut(k));
      const back = lerp(0.03, -0.01, k);
      const focusP = b.position.clone();
      const cp = focusP.clone().addScaledVector(side, dist * 0.75).addScaledVector(dir, -dist * 0.7 - back).add(V(0, lerp(0.015, 0.006, k), 0));
      const look = focusP.clone().addScaledVector(dir, lerp(0.05, 0.012, k));
      const s = shake(t, 0.15);
      place(c, [cp.x + s[0] * 0.2, cp.y + s[1] * 0.2, cp.z], [look.x, look.y, look.z]);
      return { dof: { focus: c.position.distanceTo(focusP), aperture: 0.06, maxblur: 0.022 }, bloom: 0.55 };
    },
  };
}

// ============ SHOT 3: knight swings sword at chain-mail man ============
function handsOnHips(h) {
  for (const [s, k] of [[1, 'l'], [-1, 'r']]) {
    h.root.updateMatrixWorld(true);
    const T = h.root.localToWorld(V(s * 0.21, 0.98, 0.03));
    const P = h.root.localToWorld(V(s * 0.75, 1.15, -0.25));
    const hint = h.root.localToWorld(V(-s, 0, 0)).sub(h.root.getWorldPosition(V(0, 0, 0)));
    ikArm(h, k, T, P, hint);
  }
}
function shot3({ makeStage }) {
  const scene = makeStage({ shadowSize: 3.5, sunDir: [-2, 6, 5] });
  const man = makeHuman('chainmail'); man.root.position.set(-0.22, 0, 0); scene.add(man.root);
  const kn = makeHuman('knight'); kn.root.position.set(0.36, 0, 1.0); kn.root.rotation.y = Math.PI + 0.5; scene.add(kn.root);
  const sw = sword(); kn.j.rWr.add(sw); sw.position.set(0, -0.07, 0.0); sw.rotation.x = Math.PI / 2;
  const sh = shield(); kn.j.chest.add(sh); sh.position.set(0.24, -0.08, 0.24); sh.rotation.set(0.08, 0.55, 0.05); sh.scale.setScalar(0.88);
  const c = cam(40);
  return {
    scene, camera: c,
    update(t) {
      man.setPose({ ...STAND, chest: [idle(t), 0, 0], neck: [0, -0.1, 0], lHip: [0, 0, 0.12], rHip: [0, 0, -0.12], lAn: [0, 0, -0.12], rAn: [0, 0, 0.12] });
      handsOnHips(man);
      // knight: lunge + overhead diagonal swing (hit ~t=1.75)
      const sw1 = easeIn(range(t, 0.9, 1.75));
      const back = smooth(range(t, 0, 0.9));
      kn.setPose({
        pelvis: [0, 0, 0], drop: -0.04 - 0.05 * sw1,
        spine: [0.1 + sw1 * 0.15, lerp(-0.25, 0.35, sw1) - back * 0.1, 0], chest: [0.05, lerp(-0.2, 0.3, sw1), 0],
        neck: [0.1, 0.2, 0], head: [0.05, 0.1, 0],
        lSh: [-0.35, 0.1, 0.2], lEl: [-1.35, 0, 0],
        lHip: [-0.45, 0, 0.12], lKn: [0.5, 0, 0], lAn: [-0.05, 0, 0],
        rHip: [0.35, 0, -0.1], rKn: [0.25, 0, 0], rAn: [-0.25, 0, 0],
      });
      kn.root.updateMatrixWorld(true);
      // sword hand path (knight local), blade direction hint (world)
      const H = kf(t, [[0, [-0.25, 1.75, -0.15]], [0.9, [-0.32, 1.95, -0.25]], [1.75, [0.05, 1.25, 0.55]], [2.5, [0.18, 1.05, 0.5]]], easeInOut);
      const B = kf(t, [[0, [0.3, 0.6, -1]], [0.9, [0.4, 0.2, -1]], [1.75, [0.75, -0.25, 0.6]], [2.5, [0.85, -0.4, 0.3]]], easeInOut);
      const T = kn.root.localToWorld(V(...H));
      const hint = V(...B).applyQuaternion(kn.root.quaternion);
      ikArm(kn, 'r', T, kn.root.localToWorld(V(-0.7, 1.0, -0.6)), hint);
      const k = easeInOut(range(t, 0, 2.5));
      place(c, [lerp(-0.2, -0.12, k), lerp(1.0, 1.05, k), lerp(3.9, 3.5, k)], [0.03, 1.1, 0.4]);
      return { dof: { focus: 3.2, aperture: 0.0015, maxblur: 0.006 } };
    },
  };
}

// ============ SHOT 4: blade scrapes across chain mail, sparks ============
function shot4({ makeStage }) {
  const scene = makeStage({ shadowSize: 1.2, sunDir: [-2, 5, 5] });
  const man = makeHuman('chainmail'); scene.add(man.root);
  const sw = sword(); scene.add(sw);
  const spA = sparks(70, { speed: 1.4, spread: 1.2, gravity: -5, life: 0.5, size: 0.012, seed: 21, dir: V(0.6, 0.4, 1) });
  const spB = sparks(70, { speed: 1.6, spread: 1.3, gravity: -5, life: 0.6, size: 0.012, seed: 33, dir: V(0.4, 0.5, 1) });
  scene.add(spA, spB);
  const c = cam(34);
  return {
    scene, camera: c,
    update(t) {
      man.setPose({ ...STAND, chest: [idle(t), 0, 0], neck: [0.05, 0.35, 0], head: [0.05, 0.25, 0] });
      handsOnHips(man);
      // blade comes in from the right, scraping right-to-left across the chest
      const k = easeOut(range(t, 0.0, 1.6));
      const x = lerp(0.62, -0.05, k);
      const y = lerp(1.33, 1.24, k);
      const surfZ = 0.205;
      sw.position.set(x + 0.52, y + 0.06, surfZ + 0.02);
      sw.rotation.set(0.0, -0.18, Math.PI / 2 + 0.12);
      // contact point near the blade's mid
      const contact = V(x + 0.05, y + 0.02, surfZ);
      if (t < 1.0) { spA.position.copy(contact); }
      if (t < 1.25) { spB.position.copy(contact); }
      spA.update(t - 0.95); spB.update(t - 1.2);
      const kk = easeInOut(range(t, 0, 1.95));
      place(c, [lerp(-0.22, -0.16, kk), lerp(1.6, 1.58, kk), lerp(1.3, 1.08, kk)], [0.03, 1.47, 0.05]);
      return { dof: { focus: c.position.distanceTo(V(0.03, 1.3, 0.2)), aperture: 0.012, maxblur: 0.012 }, bloom: 0.5 };
    },
  };
}

// ============ SHOT 5: plate armor, mace slams into chest ============
const MACE_PIVOT = V(0.72, 1.42, 0.5);
function plateScene(makeStage, opts = {}) {
  const scene = makeStage({ shadowSize: 2, ...opts });
  const man = makeHuman('plate'); scene.add(man.root);
  standPose(man, 0);
  const hit = surfaceHit(scene, man.armor.plate, V(0.6, 1.36, 0.9), V(0.06, 1.32, 0.0));
  return { scene, man, hit };
}
function shot5({ makeStage }) {
  const { scene, man, hit } = plateScene(makeStage);
  const piv = new THREE.Group(); piv.position.copy(MACE_PIVOT); scene.add(piv);
  const mc = mace(); mc.rotation.z = Math.PI / 2; mc.position.x = -0.25; piv.add(mc);
  const rp = rippleOverlay(man.armor.plate);
  const c = cam(34);
  // yaw so that the mace head reaches the hit point
  const d = hit.point.clone().sub(MACE_PIVOT);
  const yawHit = Math.atan2(d.z, -d.x);
  const reach = Math.hypot(d.x, d.z) - 0.25 - 0.53 - 0.08;
  mc.position.x = -0.25 - reach;
  const TH = 1.9;
  return {
    scene, camera: c,
    update(t) {
      const it = t - TH;
      const recoil = it > 0 ? Math.sin(Math.min(it, 0.5) / 0.5 * Math.PI * 0.5) : 0;
      const look = smooth(range(t, 0.6, 1.4));
      standPose(man, t, {
        spine: [-0.1 * recoil, 0.08 * recoil, 0], chest: [-0.12 * recoil, 0.15 * recoil, 0],
        neck: [-0.25 * recoil, lerp(0, 0.45, look) - 0.2 * recoil, 0], head: [-0.2 * recoil, 0.15 * look, 0],
        lSh: [0.05 - 0.3 * recoil, 0, 0.16 + 0.25 * recoil], rSh: [0.05 - 0.2 * recoil, 0, -0.16 - 0.2 * recoil],
      });
      man.setMouth(it > 0 ? smooth(range(it, 0.05, 0.35)) * 0.9 : 0);
      // swing: wind-up behind, accelerate in, bounce back a little
      const sw = it < 0 ? easeIn(range(t, 0.5, TH)) : 1 - 0.18 * Math.sin(Math.min(it, 0.6) / 0.6 * Math.PI * 0.6);
      piv.rotation.set(0, yawHit - 1.75 * (1 - sw), 0.12 * (1 - sw));
      rp.material.uniforms.uCenter.value.copy(man.armor.plate.worldToLocal(hit.point.clone()));
      rp.material.uniforms.uAmp.value = it > 0 ? Math.min(1, it * 6) : 0;
      rp.material.uniforms.uRadius.value = it > 0 ? 0.02 + easeOut(range(it, 0, 1.5)) * 0.07 : 0;
      rp.material.uniforms.uSpot.value = 0.03; rp.material.uniforms.uTime.value = t;
      const k = easeInOut(range(t, 0, 2.32));
      const s = shake(t, it > 0 ? 3 * Math.exp(-it * 3) + 0.6 : 0.6, 3);
      place(c, [lerp(-0.72, -0.6, k) + s[0], lerp(1.55, 1.5, k) + s[1], lerp(1.3, 1.12, k)], [0.1, lerp(1.42, 1.38, k), 0]);
      return { dof: { focus: c.position.distanceTo(V(0, 1.4, 0.1)), aperture: 0.004, maxblur: 0.01 }, bloom: 0.45 };
    },
  };
}

// ============ SHOT 6: red force ripple spreading across the breastplate ============
function shot6({ makeStage }) {
  const { scene, man, hit } = plateScene(makeStage, { sunDir: [-3, 5, 5] });
  const rp = rippleOverlay(man.armor.plate);
  const c = cam(32);
  return {
    scene, camera: c,
    update(t) {
      standPose(man, t, { neck: [-0.1, 0.3, 0], head: [-0.1, 0.1, 0] });
      const u = rp.material.uniforms;
      u.uCenter.value.copy(man.armor.plate.worldToLocal(hit.point.clone()));
      u.uRadius.value = 0.06 + easeOut(range(t, 0, 4.6)) * 0.5;
      u.uAmp.value = 1 - 0.55 * smooth(range(t, 5.0, 6.4));
      u.uTime.value = t * 0.75;
      u.uRings.value = 380;
      u.uSpot.value = 0.05;
      u.uSpotAmp.value = 0.8;
      u.uBlot.value = 0.75 * smooth(range(t, 2.2, 4.0)) * (1 - 0.6 * smooth(range(t, 5.4, 6.4)));
      const k = easeInOut(range(t, 0, 6.45));
      const ang = lerp(-0.42, -0.18, k);
      const R = lerp(1.05, 0.88, k);
      const s = shake(t, 0.5, 7);
      place(c, [Math.sin(ang) * R + 0.05 + s[0], lerp(1.44, 1.4, k) + s[1], Math.cos(ang) * R], [0.04, 1.33, 0.05]);
      return { dof: { focus: c.position.distanceTo(hit.point), aperture: 0.008, maxblur: 0.01 }, bloom: 0.5 };
    },
  };
}

// ============ SHOT 7: archer draws and looses ============
function shot7({ makeStage }) {
  const scene = makeStage({ shadowSize: 6, sunDir: [-3, 6, 3] });
  const man = makeHuman('plate'); man.root.position.set(0.1, 0, -0.4); scene.add(man.root);
  const aDir = V(0.371, 0, -0.928);
  const ar = makeHuman('archer'); ar.root.position.set(0.1 - aDir.x * 5.2, 0, -0.4 - aDir.z * 5.2); ar.root.rotation.y = Math.atan2(aDir.x, aDir.z) - 0.25; scene.add(ar.root);
  const AP = ar.root.position;
  const bw = bow(); ar.j.lWr.add(bw); bw.position.set(0, -0.065, 0); bw.rotation.set(Math.PI / 2, 0, 0.12);
  const arw = arrow(); scene.add(arw);
  const c = cam(52);
  const TR = 1.6; // release
  const chestTarget = V(0.18, 1.42, -0.2);
  let relPos = null, relDir = null;
  return {
    scene, camera: c,
    update(t) {
      if (t >= TR && !relPos) this.update(TR - 1e-3);   // a render can start after the release: work out where the arrow left the bow
      standPose(man, t + 1);
      const draw = t < TR ? easeInOut(range(t, 0.05, 1.25)) : Math.max(0, 1 - (t - TR) / 0.06);
      ar.setPose({
        lHip: [0.05, 0, 0.12], rHip: [-0.05, 0, -0.1], lKn: [0.05, 0, 0], rKn: [0.05, 0, 0],
        spine: [0, -0.15, 0], chest: [0, -0.35, -0.04], neck: [0.05, 0.4, 0], head: [0.1, 0.12, 0.05],
        lSh: [-1.48, 0, 0.12], lEl: [-0.08, 0, 0], drop: -0.02,
      });
      bw.update(draw);
      ar.root.updateMatrixWorld(true);
      const nock = bw.localToWorld(bw.nock.clone());
      const handT = t < TR ? nock.clone() : nock.clone().add(V(0.05, 0.02, 0.12).multiplyScalar(Math.min(1, (t - TR) * 3)));
      ikArm(ar, 'r', handT.add(V(0, -0.02, 0)), ar.root.localToWorld(V(-0.4, 1.45, -0.6)), V(0, 0, -1).applyQuaternion(ar.root.quaternion));
      // arrow
      if (t < TR) {
        const tip = bw.localToWorld(V(0, 0.035, 0.16)).clone();
        const tail = nock.clone();
        const dir = tip.clone().sub(tail).normalize();
        arw.position.copy(tail).addScaledVector(dir, 0.78);
        arw.quaternion.setFromUnitVectors(V(0, 0, 1), dir);
        relPos = arw.position.clone(); relDir = chestTarget.clone().sub(relPos).normalize();
      } else {
        const p = relPos.clone().addScaledVector(relDir, (t - TR) * 22);
        if (p.distanceTo(relPos) > chestTarget.distanceTo(relPos)) p.copy(chestTarget);
        arw.position.copy(p); arw.quaternion.setFromUnitVectors(V(0, 0, 1), relDir);
      }
      const k = easeInOut(range(t, 0, 2.4));
      const pan = smooth(range(t, TR - 0.1, TR + 0.7));
      const cp = [AP.x + lerp(0.38, 0.5, k) + 0.25 * pan, 1.38, AP.z + lerp(1.65, 1.4, k)];
      const yaw = lerp(0.03, 0.2, pan);
      place(c, cp, [cp[0] + Math.sin(yaw) * 3, lerp(1.22, 1.15, pan), cp[2] - Math.cos(yaw) * 3]);
      return { dof: { focus: lerp(1.6, 5.6, pan), aperture: 0.0022, maxblur: 0.007 } };
    },
  };
}

// ============ SHOT 8: arrow punches into the plate, he screams ============
function shot8({ makeStage }) {
  const scene = makeStage({ shadowSize: 2 });
  const man = makeHuman('plate'); scene.add(man.root);
  standPose(man, 0);
  const from = V(1.1, 1.22, 2.6), aim = V(0.08, 1.42, 0.0);
  const hit = surfaceHit(scene, man.armor.plate, from, aim);
  const dir = aim.clone().sub(from).normalize();
  const arw = arrow(); scene.add(arw);
  const rp = rippleOverlay(man.armor.plate);
  const sp = sparks(40, { speed: 0.9, spread: 1.3, gravity: -4, life: 0.4, size: 0.01, seed: 41, dir: hit.normal });
  sp.position.copy(hit.point); scene.add(sp);
  const c = cam(34);
  const TH = 0.12;
  return {
    scene, camera: c,
    update(t) {
      const it = t - TH;
      const pain = smooth(range(t, 0.3, 1.1));
      const sh = Math.sin(t * 23) * 0.02 * pain;
      standPose(man, t, {
        spine: [-0.06 * pain, 0, 0], chest: [-0.08 * pain + sh * 0.3, 0.12 * pain, 0],
        neck: [-0.2 * pain, 0.1 * pain + sh, 0], head: [-0.25 * pain, 0.1 * pain, sh * 0.5],
        lSh: [0.05, 0, 0.16 + 0.15 * pain], rSh: [0.05 - 0.4 * pain, 0, -0.25 - 0.2 * pain], rEl: [-0.25 - 0.9 * pain, 0, 0],
      });
      man.setMouth(pain * (0.85 + 0.1 * Math.sin(t * 9)));
      // arrow flies in, then creeps deeper ("enough energy to enter")
      const depth = it < 0 ? it * 20 : 0.012 + easeOut(range(it, 0, 3.2)) * 0.05;
      const wob = it > 0 ? Math.sin(it * 38) * 0.05 * Math.exp(-it * 5) : 0;
      arw.position.copy(hit.point).addScaledVector(dir, depth);
      const d2 = dir.clone().add(V(wob, wob * 0.6, 0)).normalize();
      arw.quaternion.setFromUnitVectors(V(0, 0, 1), d2);
      sp.update(it);
      const u = rp.material.uniforms;
      u.uCenter.value.copy(man.armor.plate.worldToLocal(hit.point.clone()));
      u.uAmp.value = it > 0 ? 0.55 + 0.35 * smooth(range(it, 0, 2.5)) : 0;
      u.uRadius.value = 0.05 + 0.05 * smooth(range(it, 0, 3));
      u.uRings.value = 0.0; u.uSpot.value = 0.03 + 0.025 * smooth(range(it, 0, 3)); u.uSpotAmp.value = 1.0; u.uTime.value = t;
      const k = easeInOut(range(t, 0, 3.55));
      const s = shake(t, 1 + 2 * pain, 11);
      place(c, [lerp(-0.22, -0.16, k) + s[0], lerp(1.64, 1.62, k) + s[1], lerp(1.12, 0.92, k)], [0.05, 1.5, 0]);
      return { dof: { focus: c.position.distanceTo(V(0, 1.55, 0.08)), aperture: 0.005, maxblur: 0.01 }, bloom: 0.45 };
    },
  };
}

// ============ SHOT 9: bullet tears through plate, then chain mail ============
function shot9({ makeStage }) {
  const scene = makeStage({ shadowSize: 3, sunDir: [-2, 6, 4] });
  const yaw = -0.95;
  const mk = (kind, x) => {
    const st = stand(); st.position.set(x, 0, 0); st.rotation.y = yaw; scene.add(st);
    const a = standArmor(kind); a.group.position.y = 0.93; st.add(a.group);
    return a;
  };
  const plate = mk('plate', 0), mail = mk('mail', 1.15);
  scene.updateMatrixWorld(true);
  const Y = 1.3;
  const P0 = V(-2.2, Y, 0.05), P1 = V(2.8, Y, 0.05);
  const dir = P1.clone().sub(P0).normalize();
  const hP = surfaceHit(scene, plate.target, P0, V(0, Y, 0.05));
  const hM = surfaceHit(scene, mail.target, P0.clone().setX(0.7), V(1.15, Y, 0.05));
  const b = bullet(1.6); scene.add(b);
  b.quaternion.setFromUnitVectors(V(0, 1, 0), dir);
  const bg = glowSprite(0xff8a40, 0.04); scene.add(bg);
  const tr = streak(); scene.add(tr);
  const rP = rippleOverlay(plate.target), rM = rippleOverlay(mail.target);
  const spP = sparks(60, { speed: 0.8, spread: 1.2, gravity: -3, life: 0.6, size: 0.012, seed: 51, dir: hP.normal });
  spP.position.copy(hP.point); scene.add(spP);
  const spM = sparks(40, { speed: 0.6, spread: 1.2, gravity: -3, life: 0.6, size: 0.01, seed: 52, dir: hM.normal });
  spM.position.copy(hM.point); scene.add(spM);
  const c = cam(34);
  const tP = 1.05, tM = 2.55;
  const xAt = (t) => kf(t, [[0, -1.0], [tP, hP.point.x], [tM, hM.point.x], [4.1, 3.0]], x => x);
  return {
    scene, camera: c,
    update(t) {
      const x = xAt(t);
      b.position.copy(P0).addScaledVector(dir, (x - P0.x) / dir.x);
      bg.position.copy(b.position); bg.material.opacity = 0.4;
      const start = P0.clone().addScaledVector(dir, (Math.max(-2.2, x - 2.5) - P0.x) / dir.x);
      tr.set(start, b.position, 0.0022, t < 3.2 ? 0.55 : 0.4);
      for (const [r, tt, h, spot] of [[rP, tP, hP, 0.04], [rM, tM, hM, 0.035]]) {
        const it = t - tt, u = r.material.uniforms;
        u.uCenter.value.copy(r.parent.worldToLocal(h.point.clone()));
        u.uAmp.value = it > 0 ? Math.min(1, it * 8) * (1 - 0.4 * smooth(range(it, 0.6, 2))) : 0;
        u.uRadius.value = it > 0 ? 0.03 + easeOut(range(it, 0, 1)) * 0.09 : 0;
        u.uSpot.value = spot; u.uSpotAmp.value = 1.2; u.uRings.value = 220; u.uTime.value = t;
      }
      spP.update(t - tP); spM.update(t - tM);
      let dof;
      c.fov = 34;
      if (t < 0.6) { // tight on the bullet, motion blurred feel
        const p = b.position;
        place(c, [p.x - 0.05, p.y + 0.02, p.z + 0.14], [p.x + 0.04, p.y, p.z]);
        dof = { focus: 0.15, aperture: 0.08, maxblur: 0.02 };
      } else if (t < 3.2) { // plate stand, then pan right to the mail
        c.fov = 34;
        const k = easeInOut(range(t, 1.5, 2.4));
        const px = lerp(-0.42, 0.85, k), lx = lerp(0.05, 1.2, k);
        place(c, [px, 1.42, lerp(1.0, 1.05, k)], [lx, 1.3, -0.05]);
        dof = { focus: lerp(1.05, 1.05, k), aperture: 0.004, maxblur: 0.008 };
      } else { // wide reveal of both stands
        const k = easeOut(range(t, 3.2, 4.1));
        c.fov = 44;
        place(c, [lerp(-0.55, -0.85, k), lerp(1.15, 1.2, k), lerp(3.2, 3.8, k)], [0.55, 0.95, 0]);
        dof = { focus: 3, aperture: 0.0015, maxblur: 0.006 };
      }
      return { dof, bloom: 0.5 };
    },
  };
}

export const SHOTS = [
  { start: 0.0, end: 2.42, build: shot1 },
  { start: 2.42, end: 6.25, build: shot2 },
  { start: 6.25, end: 8.75, build: shot3 },
  { start: 8.75, end: 10.68, build: shot4 },
  { start: 10.68, end: 13.0, build: shot5 },
  { start: 13.0, end: 19.45, build: shot6 },
  { start: 19.45, end: 21.85, build: shot7 },
  { start: 21.85, end: 25.4, build: shot8 },
  { start: 25.4, end: DURATION + 1, build: shot9 },
];
