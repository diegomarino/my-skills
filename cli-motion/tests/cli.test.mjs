// CLI behaviour: doctor and render without the network, safe output paths, typo hints, export stats.

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { EXAMPLES, ROOT, tmpProject } from './helpers.mjs';

const CLI = join(ROOT, 'scripts', 'cli-motion.mjs');
const { cacheDir } = await import('../scripts/lib/deps.mjs');
const { ffmpegInfo } = await import('../scripts/lib/raster/ffmpeg.mjs');

const run = (args, env = {}) => spawnSync(process.execPath, [CLI, ...args], {
  encoding: 'utf8', env: { ...process.env, ...env },
});

// no registry reachable and no npm/npx on PATH: a populated cache must be enough
const OFFLINE = { npm_config_registry: 'http://127.0.0.1:9/', npm_config_offline: 'true', PATH: '/nonexistent' };

test('doctor verifies that svg-term runs from the cache, without network, npm or npx', () => {
  const res = run(['doctor'], OFFLINE);
  assert.match(res.stdout, /ok\s+svg-term\s+svg-term-cli@2\.1\.1 rendered a test cast from the cache/);
  assert.match(res.stdout, /verified here: animated svg/);
});

test('render with a populated cache never touches the registry (offline, no npx on PATH)', () => {
  const out = join(mkdtempSync(join(tmpdir(), 'cli-motion-off-')), 'q.svg');
  const res = run(['render', join(EXAMPLES, 'quick-demo.scene.yaml'), '-o', out], OFFLINE);
  assert.equal(res.status, 0, res.stderr);
  assert.equal(readFileSync(out, 'utf8'), readFileSync(join(EXAMPLES, 'quick-demo.svg'), 'utf8'), 'same bytes as the shipped example');
});

test('doctor fails clearly, with the recovery command, when svg-term is not available', () => {
  const empty = mkdtempSync(join(tmpdir(), 'cli-motion-empty-'));
  const res = run(['doctor'], { CLI_MOTION_CACHE: empty });
  assert.equal(res.status, 1);
  assert.match(res.stdout, /FAIL\s+svg-term/);
  assert.match(res.stdout, /doctor --install/);
  assert.doesNotMatch(res.stdout, /ok\s+export/, 'no "ready" line while the renderer is missing');
});

test('a cache without svg-term gives an error that names the fix, not an npm error', () => {
  const fake = mkdtempSync(join(tmpdir(), 'cli-motion-fake-'));
  const target = join(fake, cacheDir().split('/').pop());
  mkdirSync(join(target, 'node_modules'), { recursive: true });
  writeFileSync(join(target, '.ready'), '');
  const res = run(['doctor'], { CLI_MOTION_CACHE: fake });
  assert.equal(res.status, 1);
  assert.match(res.stdout, /FAIL\s+svg-term\s+svg-term-cli is missing from the dependency cache.*doctor --install/);
});

test('render, still and export refuse to write into the skill folder unless the path is explicit', () => {
  const scene = join(EXAMPLES, 'quick-demo.scene.yaml');
  const before = readFileSync(join(EXAMPLES, 'quick-demo.svg'), 'utf8');
  for (const args of [['render', scene], ['still', scene], ['export', scene, '--gif']]) {
    const res = run(args);
    assert.equal(res.status, 1, `${args[0]} should refuse`);
    assert.match(res.stderr, /inside the skill folder.*overwrite shipped files.*(-o|--out)/);
  }
  assert.equal(readFileSync(join(EXAMPLES, 'quick-demo.svg'), 'utf8'), before, 'nothing was overwritten');
  const out = mkdtempSync(join(tmpdir(), 'cli-motion-safe-'));
  assert.equal(run(['render', scene, '-o', join(out, 'x.svg')]).status, 0);
});

test('an unknown option suggests the nearest valid one', () => {
  const scene = join(tmpProject({ 'a.scene.yaml': 'style: { widht: 40 }\nsteps:\n  - output: hi\n' }), 'a.scene.yaml');
  const res = run(['render', scene, '-o', join(tmpdir(), 'x.svg')]);
  assert.equal(res.status, 1);
  assert.match(res.stderr, /unknown option "widht"\. Did you mean "width"\?/);
  const scene2 = join(tmpProject({ 'b.scene.yaml': 'style: { them: nord }\nsteps:\n  - output: hi\n' }), 'b.scene.yaml');
  assert.match(run(['render', scene2, '-o', join(tmpdir(), 'x.svg')]).stderr, /Did you mean "theme"\?/);
});

test('export stats describe the file: MP4 frames match ffprobe and the length is within a frame of the cast', { skip: !(ffmpegInfo().ffmpeg && ffmpegInfo().libx264) }, () => {
  const dir = tmpProject({ 'a.scene.yaml': 'style: { width: 40, final_hold: 1s, typing_jitter: 0 }\nsteps:\n  - command: "echo hi"\n  - output: "[accent]hi[/]"\n' });
  const out = mkdtempSync(join(tmpdir(), 'cli-motion-stats-'));
  const res = run(['export', join(dir, 'a.scene.yaml'), '--mp4', '--scale', '1', '--out', out]);
  assert.equal(res.status, 0, res.stderr);
  const probe = JSON.parse(spawnSync('ffprobe', ['-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames,duration', '-of', 'json', join(out, 'a.mp4')], { encoding: 'utf8' }).stdout).streams[0];
  const reported = Number(/(\d+) video frames at 30 fps/.exec(res.stdout)?.[1]);
  assert.equal(reported, Number(probe.nb_read_frames), 'reported frame count is the encoded one');
  const seconds = Number(/, ([\d.]+)s,/.exec(res.stdout)[1]);
  assert.ok(Math.abs(Number(probe.duration) - seconds) < 1 / 30 + 1e-6, `ffprobe ${probe.duration}s vs reported ${seconds}s`);
});
