import assert from 'node:assert/strict';
import { join } from 'node:path';
import { test } from 'node:test';
import { EXAMPLES, SIMPLE, loadScene, svg, tmpProject } from './helpers.mjs';

const render = async (yaml, fn = svg.renderAnimated) => {
  const dir = tmpProject({ 'a.scene.yaml': yaml });
  return fn(loadScene(join(dir, 'a.scene.yaml')));
};

test('same scene twice gives identical SVG bytes', async () => {
  assert.equal(await render(SIMPLE), await render(SIMPLE));
});

test('no translateX is left: frames are stationary and toggled by visibility', async () => {
  const out = await render(SIMPLE);
  assert.ok(!out.includes('translateX'));
  assert.match(out, /visibility:hidden;animation:overlay-0 [\d.]+s step-end infinite/);
  assert.ok(!/<svg x="\d+">/.test(out));
});

test('progress bar is on by default, uses SMIL, and off removes it', async () => {
  const on = await render(SIMPLE);
  assert.match(on, /<animate attributeName="width" values="0;\d+"/);
  const off = await render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, progress_bar: false'));
  assert.ok(!off.includes('<animate'));
  assert.ok(!off.includes('width="0"'));
});

test('progress bar colour and height are configurable', async () => {
  const out = await render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, progress_color: "#ff0000", progress_height: 6'));
  assert.match(out, /height="6" fill="#ff0000"/);
});

test('theme colours reach the SVG', async () => {
  const out = await render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, theme: nord-dark'));
  assert.match(out, /#2e3440/i);
});

test('the final hold is part of the animation length', async () => {
  const out = await render(SIMPLE);
  const dur = Number(out.match(/overlay-0 ([\d.]+)s/)[1]);
  assert.ok(dur > 2, `duration ${dur}`);
});

test('once: plays a single time and holds the last frame; no restart', async () => {
  const out = await render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, playback: once'));
  assert.ok(!out.includes('infinite'));
  assert.match(out, /step-end 1 forwards/);
  assert.match(out, /repeatCount="1" fill="freeze"/);
  const lastName = [...out.matchAll(/@keyframes (overlay-\d+)\{/g)].at(-1)[1];
  const css = out.match(new RegExp(`@keyframes ${lastName}\\{.*?\\}\\}`))[0];
  assert.ok(css.endsWith('100%{visibility:visible}}'), css);
});

test('fade: cross-fade, the old frame ramps out while the next scene ramps in', async () => {
  const out = await render('scenes:\n  - steps: [{comment: one}]\n  - transition: fade\n    steps: [{command: x}]\n');
  assert.match(out, /@keyframes fade-\d+\{0%\{opacity:0\}[\d.]+%\{opacity:0\}[\d.]+%\{opacity:1\}100%\{opacity:1\}\}/, 'incoming ramps in');
  assert.match(out, /@keyframes fade-\d+\{0%\{opacity:1\}[\d.]+%\{opacity:1\}[\d.]+%\{opacity:0\}100%\{opacity:0\}\}/, 'outgoing ramps out');
  // pixel-level proof lives in fade.test.mjs
  assert.ok(!out.includes('translateX'));
});

test('still: a single frame, no animation, final frame by default', async () => {
  const out = await render(SIMPLE, svg.renderStill);
  assert.ok(!out.includes('@keyframes'));
  assert.ok(out.includes('hi'));
  const early = await render(SIMPLE, (b) => svg.renderStill(b, 0));
  assert.ok(!early.includes('hi</text>') || early.length < out.length);
  await assert.rejects(() => render(SIMPLE, (b) => svg.renderStill(b, 'later')), /--at must be/);
});

test('the shipped examples render', async () => {
  for (const f of ['quick-demo.scene.yaml', 'multi-scene.scene.yaml']) {
    const out = await svg.renderAnimated(loadScene(join(EXAMPLES, f)));
    assert.ok(out.startsWith('<svg') && !out.includes('translateX'), f);
  }
});
