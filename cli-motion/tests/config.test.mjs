import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';
import { ROOT, config, loadScene, tmpProject } from './helpers.mjs';

test('defaults.yaml documents every option and the themes are all present', () => {
  const keys = config.validKeys();
  for (const k of ['theme', 'font', 'window', 'prompt', 'cursor', 'speed', 'playback', 'progress_bar', 'transition', 'spinner', 'banner_font', 'scale', 'mp4_fps', 'gif_dither']) {
    assert.ok(keys.includes(k), k);
  }
  assert.equal(config.listThemes().length, 25);
  for (const f of readdirSync(join(ROOT, 'assets', 'themes'))) {
    const t = JSON.parse(readFileSync(join(ROOT, 'assets', 'themes', f), 'utf8'));
    assert.ok(t.license && t.sources && t.terminal.ansi.length === 16, f);
  }
});

test('layers merge: defaults < project < scene style < scene style block', () => {
  const dir = tmpProject({
    'cli-motion.yaml': 'theme: nord-dark\nprompt: dollar\nspeed: 3\nstyles: { mine: "fg:red" }\n',
    'sub/a.scene.yaml': [
      'style: { prompt: path, styles: { other: "bold" } }',
      'scenes:',
      '  - steps: [{prompt: true}]',
      '    style: { speed: 5 }',
      '  - steps: [{prompt: true}]',
    ].join('\n'),
  });
  const { style } = config.resolveStyle({
    sceneDir: join(dir, 'sub'),
    sceneStyle: { prompt: 'path', styles: { other: 'bold' } },
  });
  assert.equal(style.theme, 'nord-dark'); // project beats default
  assert.equal(style.prompt, 'path'); // scene beats project
  assert.equal(style.speed, 3); // project beats default
  assert.equal(style.width, 80); // untouched default
  assert.ok(style.styles.mine && style.styles.other && style.styles.accent, 'styles merge key by key');

  const b = loadScene(join(dir, 'sub', 'a.scene.yaml'));
  assert.equal(b.style.theme, 'nord-dark');
  assert.equal(b.projectConfig, join(dir, 'cli-motion.yaml'));
  const [first, second] = b.events.filter(([, , d]) => d.includes('~/app'));
  assert.ok(first && second);
  assert.ok(second[0] - first[0] > 0);
});

test('unknown keys fail naming the key and the valid ones, in every layer', () => {
  const dir = tmpProject({ 'cli-motion.yaml': 'colour: red\n', 'a.scene.yaml': 'steps: [{prompt: true}]\n' });
  assert.throws(() => loadScene(join(dir, 'a.scene.yaml')), /cli-motion\.yaml: unknown option "colour".*Valid options:.*theme/s);

  const d2 = tmpProject({ 'a.scene.yaml': 'style: { tehme: nord-dark }\nsteps: [{prompt: true}]\n' });
  assert.throws(() => loadScene(join(d2, 'a.scene.yaml')), /style: unknown option "tehme".*Valid options/s);

  const d3 = tmpProject({ 'a.scene.yaml': 'scenes:\n  - style: { bogus: 1 }\n    steps: [{prompt: true}]\n' });
  assert.throws(() => loadScene(join(d3, 'a.scene.yaml')), /scenes\[0\]\.style: unknown option "bogus"/);
});

test('global-only options cannot be set per scene', () => {
  const d = tmpProject({ 'a.scene.yaml': 'scenes:\n  - style: { theme: nord-dark }\n    steps: [{prompt: true}]\n' });
  assert.throws(() => loadScene(join(d, 'a.scene.yaml')), /unknown option "theme"/);
});

test('invalid enum values and unknown themes are rejected', () => {
  const d = tmpProject({ 'a.scene.yaml': 'style: { cursor: blob }\nsteps: [{prompt: true}]\n' });
  assert.throws(() => loadScene(join(d, 'a.scene.yaml')), /invalid cursor "blob".*hidden, block, bar, underline/);
  const d2 = tmpProject({ 'a.scene.yaml': 'style: { theme: nope }\nsteps: [{prompt: true}]\n' });
  assert.throws(() => loadScene(join(d2, 'a.scene.yaml')), /unknown theme "nope"/);
});
