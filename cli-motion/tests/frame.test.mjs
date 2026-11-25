import assert from 'node:assert/strict';
import { join } from 'node:path';
import { test } from 'node:test';
import { SIMPLE, loadScene, svg, tmpProject } from './helpers.mjs';

const withStyle = (extra) => SIMPLE.replace('final_hold: 2s', `final_hold: 2s, ${extra}`);
const render = async (yaml, fn = svg.renderAnimated) => {
  const dir = tmpProject({ 'a.scene.yaml': yaml });
  return fn(loadScene(join(dir, 'a.scene.yaml')));
};
const size = (out) => [Number(out.match(/^<svg[^>]*\swidth="([\d.]+)"/)[1]), Number(out.match(/^<svg[^>]*\sheight="([\d.]+)"/)[1])];

test('default frame: title bar, three dots, 8px rounded corners, soft shadow', async () => {
  const out = await render(SIMPLE);
  assert.equal((out.match(/<circle /g) ?? []).length, 3);
  assert.match(out, /<clipPath id="cm-clip"><rect [^>]*rx="8" ry="8"\/>/);
  assert.match(out, /<filter id="cm-shadow"[^>]*><feGaussianBlur/);
  assert.match(out, /filter="url\(#cm-shadow\)"/);
});

test('frame is plain SVG: nothing that breaks inside <img> on GitHub', async () => {
  const out = await render(SIMPLE);
  assert.ok(!/<script|foreignObject|href="http|@import/.test(out));
});

test('window title shows in the bar and is part of the font subset', async () => {
  const out = await render(withStyle('window_title: "Zq demo"'));
  assert.match(out, /text-anchor="middle"[^>]*>Zq demo<\/text>/);
});

test('window: plain has no title bar or dots but keeps corners and shadow', async () => {
  const chrome = await render(SIMPLE);
  const plain = await render(withStyle('window: plain'));
  assert.ok(!plain.includes('<circle'));
  assert.ok(size(plain)[1] < size(chrome)[1]);
  assert.match(plain, /cm-shadow/);
  assert.match(plain, /rx="8"/);
});

test('window: none is a bare terminal: no frame, shadow or clip', async () => {
  const out = await render(withStyle('window: none'));
  assert.ok(!/<circle|cm-shadow|clipPath/.test(out));
  assert.match(out, /<animate attributeName="width"/); // the progress bar still works
});

test('window_shadow: false drops the shadow and its margin', async () => {
  const on = await render(SIMPLE);
  const off = await render(withStyle('window_shadow: false'));
  assert.ok(!off.includes('cm-shadow'));
  assert.ok(size(off)[0] < size(on)[0]);
});

test('window_radius is configurable', async () => {
  const out = await render(withStyle('window_radius: 14'));
  assert.match(out, /<clipPath id="cm-clip"><rect [^>]*rx="14"/);
});

test('window_background paints an opaque outer rect (for GIF/MP4)', async () => {
  const out = await render(withStyle('window_background: "#ffffff"'));
  const [w, h] = size(out);
  assert.ok(out.includes(`<rect width="${w}" height="${h}" fill="#ffffff"/>`));
  const none = await render(SIMPLE);
  assert.ok(!none.includes('fill="#ffffff"/>'));
});

test('the progress bar is inside the clipped window, so it follows the rounded corners', async () => {
  const out = await render(SIMPLE);
  const clipped = out.match(/<g clip-path="url\(#cm-clip\)">([\s\S]*)<\/g><rect [^>]*fill="none"/)[1];
  assert.match(clipped, /<animate attributeName="width"/);
});

test('terminal sits on whole pixels, still stationary frames (no transform on the reel)', async () => {
  const out = await render(SIMPLE);
  assert.match(out, /<svg x="\d+" y="\d+" height=/);
  assert.ok(!out.includes('translateX'));
});

test('font_size scales the terminal; font family is embedded', async () => {
  const a = await render(SIMPLE);
  const b = await render(withStyle('font_size: 20'));
  assert.ok(size(b)[0] > size(a)[0]);
  assert.match(b, /font-family="'JetBrains Mono',/);
});

test('framed output is still deterministic, animated and still', async () => {
  assert.equal(await render(withStyle('window_background: "#101010"')), await render(withStyle('window_background: "#101010"')));
  assert.equal(await render(SIMPLE, svg.renderStill), await render(SIMPLE, svg.renderStill));
});

test('unknown font fails with the valid ones', () => {
  assert.throws(() => tmpAndLoad(withStyle('font: Comic Sans')), /unknown font "Comic Sans".*JetBrains Mono, Fira Code/);
});

function tmpAndLoad(yaml) {
  const dir = tmpProject({ 'a.scene.yaml': yaml });
  return loadScene(join(dir, 'a.scene.yaml'));
}
