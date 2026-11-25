import assert from 'node:assert/strict';
import { join } from 'node:path';
import { test } from 'node:test';
import { loadScene, tmpProject } from './helpers.mjs';

const load = (yaml) => {
  const dir = tmpProject({ 'a.scene.yaml': yaml });
  return loadScene(join(dir, 'a.scene.yaml'));
};
const text = (build) => build.events.map((e) => e[2]).join('');

test('title: figlet banner in the default font, drawn inside the terminal', () => {
  const b = load('style: { width: 70, final_hold: 1s }\nscenes:\n  - title: { banner: "hi" }\n    steps: [{comment: x}]\n');
  assert.ok(text(b).includes('|_|'), 'figlet standard art');
});

test('title: figlet font option', () => {
  const standard = text(load('style: { width: 70, final_hold: 1s }\nscenes:\n  - title: { banner: "hi" }\n'));
  const small = text(load('style: { width: 70, final_hold: 1s }\nscenes:\n  - title: { banner: "hi", font: small }\n'));
  assert.notEqual(standard, small);
});

test('title: gradient switches to cfonts with truecolor per glyph', () => {
  const b = load('style: { width: 70, final_hold: 1s }\nscenes:\n  - title: { banner: "ab", font: block, gradient: ["#ff0000", "#0000ff"] }\n');
  const t = text(b);
  assert.ok(/\x1b\[38;2;255;0;\d+m/.test(t) || /\x1b\[38;2;\d+;0;\d+m/.test(t), 'gradient colour sequences');
  assert.ok(t.includes('█'));
});

test('gradient accepts theme colour names; one colour or an unknown font is an error', () => {
  load('style: { width: 70, final_hold: 1s }\nscenes:\n  - title: { banner: "a", gradient: [accent, accent2] }\n');
  assert.throws(() => load('scenes:\n  - title: { banner: "a", gradient: ["#fff"] }\n'), /at least two colours/);
  assert.throws(() => load('scenes:\n  - title: { banner: "a", gradient: [accent, accent2], font: nope }\n'), /unknown cfonts font "nope"/);
});

test('banner wider than the terminal fails with advice', () => {
  assert.throws(() => load('style: { width: 20 }\nscenes:\n  - title: { banner: "too wide to fit" }\n'), /columns wide/);
});
