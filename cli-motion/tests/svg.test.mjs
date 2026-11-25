import assert from 'node:assert/strict';
import { join } from 'node:path';
import { test } from 'node:test';
import { EXAMPLES, SIMPLE, loadScene, svg, tmpProject } from './helpers.mjs';

const render = (yaml, fn = svg.renderAnimated) => {
  const dir = tmpProject({ 'a.scene.yaml': yaml });
  return fn(loadScene(join(dir, 'a.scene.yaml')));
};

test('same scene twice gives identical SVG bytes', () => {
  assert.equal(render(SIMPLE), render(SIMPLE));
});

test('no translateX is left: frames are stationary and toggled by visibility', () => {
  const out = render(SIMPLE);
  assert.ok(!out.includes('translateX'));
  assert.match(out, /visibility:hidden;animation:overlay-0 [\d.]+s step-end infinite/);
  assert.ok(!/<svg x="\d+">/.test(out));
});

test('progress bar is on by default, uses SMIL, and off removes it', () => {
  const on = render(SIMPLE);
  assert.match(on, /<animate attributeName="width" values="0;\d+"/);
  const off = render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, progress_bar: false'));
  assert.ok(!off.includes('<animate'));
  assert.ok(!off.includes('cm-clip'));
});

test('progress bar colour and height are configurable', () => {
  const out = render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, progress_color: "#ff0000", progress_height: 6'));
  assert.match(out, /height="6" fill="#ff0000"/);
});

test('theme colours reach the SVG', () => {
  const out = render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, theme: nord-dark'));
  assert.match(out, /#2e3440/i);
});

test('the final hold is part of the animation length', () => {
  const out = render(SIMPLE);
  const dur = Number(out.match(/overlay-0 ([\d.]+)s/)[1]);
  assert.ok(dur > 2, `duration ${dur}`);
});

test('once: plays a single time and holds the last frame; no restart', () => {
  const out = render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, playback: once'));
  assert.ok(!out.includes('infinite'));
  assert.match(out, /step-end 1 forwards/);
  assert.match(out, /repeatCount="1" fill="freeze"/);
  const lastName = [...out.matchAll(/@keyframes (overlay-\d+)\{/g)].at(-1)[1];
  const css = out.match(new RegExp(`@keyframes ${lastName}\\{.*?\\}\\}`))[0];
  assert.ok(css.endsWith('100%{visibility:visible}}'), css);
});

test('fade: an opacity ramp on the next scene while the old frame stays painted', () => {
  const out = render('scenes:\n  - steps: [{comment: one}]\n  - transition: fade\n    steps: [{command: x}]\n');
  assert.match(out, /@keyframes fade-\d+\{0%,[\d.]+%\{opacity:0\}[\d.]+%\{opacity:1\}100%\{opacity:1\}\}/);
  assert.ok(!out.includes('translateX'));
});

test('still: a single frame, no animation, final frame by default', () => {
  const out = render(SIMPLE, svg.renderStill);
  assert.ok(!out.includes('@keyframes'));
  assert.ok(out.includes('hi'));
  const early = render(SIMPLE, (b) => svg.renderStill(b, 0));
  assert.ok(!early.includes('hi</text>') || early.length < out.length);
  assert.throws(() => render(SIMPLE, (b) => svg.renderStill(b, 'later')), /--at must be/);
});

test('the shipped examples render', () => {
  for (const f of ['quick-demo.scene.yaml', 'multi-scene.scene.yaml']) {
    const out = svg.renderAnimated(loadScene(join(EXAMPLES, f)));
    assert.ok(out.startsWith('<svg') && !out.includes('translateX'), f);
  }
});

test('progress bar is clipped to the window shape (same rx/ry as the background)', () => {
  const out = render(SIMPLE);
  const rx = out.match(/<rect width="[\d.]+" height="[\d.]+" rx="([\d.]+)" ry="[\d.]+" class="a"\/>/)[1];
  assert.match(out, new RegExp(`<clipPath id="cm-clip"><rect [^>]*rx="${rx}" ry="${rx}"/></clipPath><g clip-path="url\\(#cm-clip\\)">`));
  // svg-term draws the same rounded background rect for window: none, so the clip must follow it too.
  const bare = render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, window: none'));
  const bareRx = bare.match(/<rect width="[\d.]+" height="[\d.]+" rx="([\d.]+)" ry="[\d.]+" class="a"\/>/)[1];
  assert.match(bare, new RegExp(`<clipPath id="cm-clip"><rect [^>]*rx="${bareRx}"`));
});
