import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
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

// ── colour does not depend on the caller's terminal ────────────────────────────────────────

const GRADIENT_SCENE = 'style: { width: 70, final_hold: 1s, typing_jitter: 0 }\nscenes:\n  - title: { banner: "ab", font: block, gradient: ["#ff0000", "#0000ff"] }\n';

/** Build the scene in a child with a hostile colour environment; returns the cast text. */
function castInEnv(env) {
  const dir = tmpProject({ 'a.scene.yaml': GRADIENT_SCENE });
  const script = `import { loadScene } from ${JSON.stringify(new URL('../scripts/lib/scene/index.mjs', import.meta.url).href)};
    process.stdout.write(Buffer.from((await loadScene(${JSON.stringify(join(dir, 'a.scene.yaml'))})).castText).toString('base64'));`;
  const res = spawnSync(process.execPath, ['--input-type=module', '-e', script], {
    env: { PATH: process.env.PATH, HOME: process.env.HOME, CLI_MOTION_CACHE: process.env.CLI_MOTION_CACHE ?? '', XDG_CACHE_HOME: process.env.XDG_CACHE_HOME ?? '', ...env },
    stdio: ['ignore', 'pipe', 'pipe'], // no TTY
    encoding: 'utf8',
  });
  assert.equal(res.status, 0, res.stderr);
  return Buffer.from(res.stdout, 'base64').toString('utf8');
}

test('gradient banner colours survive a headless shell (no TTY, no TERM/COLORTERM, NO_COLOR, FORCE_COLOR=0)', () => {
  const stripped = castInEnv({});
  const hostile = castInEnv({ NO_COLOR: '1', TERM: 'dumb', COLORTERM: '', FORCE_COLOR: '0' });
  const truecolor = castInEnv({ TERM: 'xterm-256color', COLORTERM: 'truecolor', FORCE_COLOR: '3' });
  const count = (t) => (t.match(/\\u001b\[38;2;\d+;\d+;\d+m/g) ?? []).length;
  assert.ok(count(stripped) >= 10, `stripped env kept ${count(stripped)} truecolor sequences`);
  assert.equal(stripped, hostile, 'cast is byte-identical under NO_COLOR/TERM=dumb');
  assert.equal(stripped, truecolor, 'cast is byte-identical under a truecolor terminal');
});

test('gradient presets: gradient: rainbow works; unknown names list the presets', () => {
  const b = load('style: { width: 70, final_hold: 1s }\nscenes:\n  - title: { banner: "ab", font: block, gradient: rainbow }\n');
  const colours = new Set(text(b).match(/\x1b\[38;2;\d+;\d+;\d+m/g));
  assert.ok(colours.size >= 5, `rainbow produced ${colours.size} colours`);
  load('style: { width: 70, final_hold: 1s, banner_gradient: [vice] }\nscenes:\n  - title: { banner: "ab", font: block }\n');
  assert.throws(() => load('scenes:\n  - title: { banner: "a", gradient: nope }\n'), /unknown gradient preset "nope".*rainbow/);
});

test('a bare `- clear` step is accepted, as the docs show', () => {
  const b = load('style: { width: 40, final_hold: 1s }\nsteps:\n  - output: hi\n  - clear\n  - output: bye\n');
  assert.ok(text(b).includes('\x1b[2J') || text(b).includes('\x1b[H'), 'screen is cleared');
});
