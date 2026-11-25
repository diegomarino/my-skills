import assert from 'node:assert/strict';
import { join } from 'node:path';
import { test } from 'node:test';
import { loadScene, tmpProject } from './helpers.mjs';

const { EFFECT_NAMES, EFFECT_DEFAULTS } = await import('../scripts/lib/scene/effects.mjs');

const load = (yaml) => {
  const dir = tmpProject({ 'a.scene.yaml': yaml });
  return loadScene(join(dir, 'a.scene.yaml'));
};
const scene = (title, extra = '') => `style: { width: 60, final_hold: 1s${extra} }\nscenes:\n  - title: ${title}\n`;
const strip = (s) => s.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '');

test('seeded effects are deterministic and the seed changes them', () => {
  for (const effect of ['decrypt', 'glitch', 'rainbow']) {
    const y = scene(`{ banner: "hi", font: small, effect: ${effect} }`);
    assert.equal(load(y).castText, load(y).castText, effect);
  }
  const a = load(scene('{ banner: "hi", font: small, effect: decrypt }')).castText;
  const b = load(scene('{ banner: "hi", font: small, effect: decrypt }', ', seed: 7')).castText;
  assert.notEqual(a, b);
});

test('frame count follows fps × duration', () => {
  const b = load(scene('{ banner: "hi", font: small, effect: rainbow, fps: 10, duration: 2s }'));
  assert.equal(b.bannerEffects[0].requested, 20);
  assert.equal(b.bannerEffects[0].frames, 20);
  // identical neighbouring frames are merged, so the emitted count can only be lower
  const c = load(scene('{ banner: "hi", font: small, effect: pulse, fps: 5, duration: 1s }'));
  assert.equal(c.bannerEffects[0].requested, 5);
  assert.ok(c.bannerEffects[0].frames <= 5);
  // the clock still covers the whole duration
  const t = c.events.filter((e) => e[2] !== '\x1b[0m').map((e) => e[0]);
  assert.ok(Math.abs(t.at(-1) - t[0] - 1) < 0.01);
});

test('colour effects default to a low fps; fps and duration come from the config layers', () => {
  assert.ok(['rainbow', 'gradient-sweep', 'pulse'].every((e) => EFFECT_DEFAULTS[e].fps <= 12));
  const b = load(scene('{ banner: "hi", font: small, effect: rainbow }'));
  assert.equal(b.bannerEffects[0].fps, 12);
  const c = load(scene('{ banner: "hi", font: small }', ', banner_effect: pulse, banner_effect_fps: 4, banner_effect_duration: 1s'));
  assert.equal(c.bannerEffects[0].effect, 'pulse');
  assert.equal(c.bannerEffects[0].frames, 4);
});

test('unknown effect fails with the valid names; bad fps / direction too', () => {
  assert.throws(() => load(scene('{ banner: "hi", effect: sparkle }')), (e) => /unknown banner effect "sparkle"/.test(e.message)
    && EFFECT_NAMES.every((n) => e.message.includes(n)));
  assert.throws(() => load(scene('{ banner: "hi", effect: wipe, fps: 500 }')), /fps must be between 1 and 60/);
  assert.throws(() => load(scene('{ banner: "hi", effect: slide, direction: up }')), /Valid directions: left, right, top, bottom/);
  assert.throws(() => load(scene('{ banner: "hi" }', ', banner_effect: nope')), /unknown banner effect "nope"/);
});

test('final frame equals the static banner, for every effect', () => {
  const staticB = load(scene('{ banner: "hi", font: small }'));
  const rowCount = strip(staticB.events[0][2]).length ? staticB.rows - 1 : 0;
  const staticRows = staticB.events.slice(0, rowCount).map((e) => e[2]).join('').replaceAll('\x1b[2K', '');
  for (const effect of EFFECT_NAMES) {
    const b = load(scene(`{ banner: "hi", font: small, effect: ${effect} }`));
    const frames = b.events.filter((e) => e[2] !== '\x1b[0m');
    const last = frames.at(-1)[2];
    // same rows, same colours: the last frame redraws the static rows byte for byte
    assert.equal(last.replace(/^\x1b\[\d+A\r/, '').replaceAll('\x1b[2K', ''), staticRows, effect);
  }
});

test('cfonts gradient banners animate too, and the final frame keeps the gradient', () => {
  const plain = load(scene('{ banner: "ab", font: block, gradient: ["#ff0000", "#0000ff"] }'));
  const fx = load(scene('{ banner: "ab", font: block, gradient: ["#ff0000", "#0000ff"], effect: wipe }'));
  const last = fx.events.filter((e) => e[2] !== '\x1b[0m').at(-1)[2];
  assert.ok(last.includes(plain.events[0][2].split('\r\n')[0].replaceAll('\x1b[2K', '')));
});

test('animation redraws in place: first frame advances rows, later ones move up', () => {
  const b = load(scene('{ banner: "hi", font: small, effect: wipe }'));
  const rows = b.events[0][2].split('\r\n').length - 1;
  assert.ok(b.events[1][2].startsWith(`\x1b[${rows}A\r`));
  assert.equal(b.rows, rows + 1); // the banner rows plus the cursor row
});

test('a banner step with a multi-line block animates too', () => {
  const b = load('style: { width: 40, final_hold: 1s }\nsteps:\n  - banner: { block: "ab\\ncd", effect: lines, fps: 10, duration: 0.5s, align: left }\n');
  assert.equal(b.bannerEffects[0].effect, 'lines');
  assert.ok(strip(b.events.filter((e) => e[2] !== '\x1b[0m').at(-1)[2]).includes('ab'));
});

test('no effect: the banner is the plain static output', () => {
  const b = load(scene('{ banner: "hi", font: small }'));
  assert.deepEqual(b.bannerEffects, []);
  assert.ok(!b.castText.includes('\\u001b[2K'));
});
