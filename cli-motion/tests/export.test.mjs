import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { loadScene, tmpProject } from './helpers.mjs';

const raster = await import('../scripts/lib/raster/index.mjs');
const { ffmpegInfo } = await import('../scripts/lib/raster/ffmpeg.mjs');

const SCENE = `
name: demo
style: { width: 36, final_hold: 1s, typing_jitter: 0 }
scenes:
  - steps:
      - command: "echo hi"
      - output: "[accent]hi[/]"
  - transition: fade
    steps:
      - output: "second scene"
`;

const build = (yaml = SCENE) => {
  const dir = tmpProject({ 'a.scene.yaml': yaml });
  return loadScene(join(dir, 'a.scene.yaml'));
};
const outDir = () => mkdtempSync(join(tmpdir(), 'cli-motion-out-'));

/** Minimal GIF reader: global/local colour tables, delays, loop extension, frame count. */
function readGif(buf) {
  assert.equal(buf.toString('latin1', 0, 6), 'GIF89a');
  const flags = buf[10];
  let p = 13;
  const info = { width: buf.readUInt16LE(6), height: buf.readUInt16LE(8), globalTable: !!(flags & 0x80), localTables: 0, delays: [], loop: null };
  if (info.globalTable) p += 3 * (1 << ((flags & 7) + 1));
  const skipSub = () => { while (buf[p] !== 0) p += buf[p] + 1; p++; };
  while (p < buf.length && buf[p] !== 0x3b) {
    if (buf[p] === 0x21) {
      const label = buf[p + 1];
      if (label === 0xf9) info.delays.push(buf.readUInt16LE(p + 4) * 10);
      if (label === 0xff && buf.toString('latin1', p + 3, p + 14) === 'NETSCAPE2.0') info.loop = buf.readUInt16LE(p + 16);
      p += 2; skipSub();
    } else if (buf[p] === 0x2c) {
      const f = buf[p + 9];
      p += 10;
      if (f & 0x80) { info.localTables++; p += 3 * (1 << ((f & 7) + 1)); }
      p++; skipSub();
    } else throw new Error(`bad GIF block 0x${buf[p].toString(16)} at ${p}`);
  }
  return info;
}

test('timeline covers the cast exactly and snaps without drift', () => {
  const states = [{ start: 0, end: 0.013 }, { start: 0.013, end: 0.5 }, { start: 0.5, end: 2 }];
  const tl = raster.buildTimeline({ states, total: 2, fadeFps: 15, progressStep: 0.5 });
  assert.equal(tl[0].start, 0);
  assert.equal(tl.at(-1).end, 2000);
  tl.slice(1).forEach((f, i) => assert.equal(f.start, tl[i].end));
  const snapped = raster.snapDurations(tl, 10, 2);
  assert.ok(snapped.every((s) => s.units >= 2));
  assert.equal(snapped.reduce((n, s) => n + s.units, 0), 200);
});

test('a fade becomes blended frames over the previous state', () => {
  const states = [{ start: 0, end: 1 }, { start: 1, end: 3 }];
  const tl = raster.buildTimeline({ states, fades: [{ at: 1, duration: 0.4 }], total: 3, fadeFps: 15 });
  const blended = tl.filter((f) => f.alpha != null);
  assert.equal(blended.length, 6);
  assert.ok(blended.every((f) => f.base === 0 && f.state === 1 && f.alpha > 0 && f.alpha < 1));
  assert.ok(blended.every((f, i) => i === 0 || f.alpha > blended[i - 1].alpha));
});

test('two identical stationary frames give identical pixels; only the bar differs between progress steps', async () => {
  const b = build();
  const prep = await raster.prepareExport(b);
  const r = raster.makeRasteriser(prep.faces, 2);
  try {
    const f = (progress) => ({ state: 1, base: null, alpha: null, progress });
    const a1 = r.render(prep.frameSvg(f(0.25)));
    const a2 = r.render(prep.frameSvg(f(0.25)));
    assert.ok(a1.rgba.equals(a2.rgba), 'same state, same bar: identical pixels');
    const c = r.render(prep.frameSvg(f(0.5)));
    assert.equal(c.width, a1.width);
    // everything above the bar (4 px × scale 2, plus the 1 px border) is untouched by the bar
    const rowBytes = a1.width * 4;
    const barRows = (4 + 2 + 36) * 2; // generous: shadow margin below the window
    const upto = (a1.height - barRows) * rowBytes;
    assert.ok(a1.rgba.subarray(0, upto).equals(c.rgba.subarray(0, upto)), 'text pixels do not move with the bar');
    assert.ok(!a1.rgba.equals(c.rgba), 'the bar did move');
  } finally {
    r.close();
  }
});

test('window corners are painted on the outer background, never transparent', async () => {
  const b = build(SCENE.replace('typing_jitter: 0', 'typing_jitter: 0, window_background: "#ff00ff"'));
  const prep = await raster.prepareExport(b);
  assert.equal(prep.background, '#ff00ff');
  const r = raster.makeRasteriser(prep.faces, 1);
  try {
    const img = r.render(prep.frameSvg({ state: 0, base: null, alpha: null, progress: 0 }));
    assert.deepEqual([...img.rgba.subarray(0, 4)], [255, 0, 255, 255]);
    for (let i = 3; i < img.rgba.length; i += 4) assert.equal(img.rgba[i], 255);
  } finally {
    r.close();
  }
});

test('GIF without ffmpeg (gifenc): one global palette, loops, duration matches the cast', async () => {
  const b = build();
  const dir = outDir();
  const [gif] = await raster.exportScene(b, { gif: true, mp4: false, outDir: dir, base: 'demo', encoder: 'js' });
  const info = readGif(readFileSync(gif.file));
  assert.equal(gif.encoder, 'gifenc');
  assert.ok(info.globalTable, 'has a global colour table');
  assert.equal(info.localTables, 0, 'no per-frame palettes');
  assert.equal(info.loop, 0, 'loops forever');
  assert.ok(info.delays.every((d) => d >= 20), 'no frame shorter than 20 ms');
  const total = info.delays.reduce((n, d) => n + d, 0) / 1000;
  assert.ok(Math.abs(total - b.duration) <= 0.02, `gif ${total}s vs cast ${b.duration}s`);
  assert.equal(info.width % 2, 0);
});

test('playback: once maps to a GIF without the loop extension', async () => {
  const b = build(SCENE.replace('typing_jitter: 0', 'typing_jitter: 0, playback: once'));
  const [gif] = await raster.exportScene(b, { gif: true, mp4: false, outDir: outDir(), base: 'demo', encoder: 'js' });
  assert.equal(readGif(readFileSync(gif.file)).loop, null);
});

test('identical consecutive frames are merged, not re-encoded', async () => {
  const noBar = build(SCENE.replace('typing_jitter: 0', 'typing_jitter: 0, progress_bar: false'));
  const withBar = build();
  const run = async (b) => (await raster.exportScene(b, { gif: true, mp4: false, outDir: outDir(), base: 'd', encoder: 'js' }))[0];
  const a = await run(noBar);
  const c = await run(withBar);
  assert.ok(a.frames < c.frames, 'without the bar, holds collapse into single frames');
  assert.ok(Math.abs(a.seconds - c.seconds) <= 0.02);
});

test('GIF through ffmpeg: global palette, no local tables', { skip: !ffmpegInfo().ffmpeg }, async () => {
  const b = build();
  const [gif] = await raster.exportScene(b, { gif: true, mp4: false, outDir: outDir(), base: 'demo', encoder: 'ffmpeg' });
  const info = readGif(readFileSync(gif.file));
  assert.ok(info.globalTable);
  assert.equal(info.localTables, 0);
  const total = info.delays.reduce((n, d) => n + d, 0) / 1000;
  assert.ok(Math.abs(total - b.duration) <= 0.05, `gif ${total}s vs cast ${b.duration}s`);
});

test('MP4: even dimensions, yuv420p, duration within one frame of the cast', { skip: !(ffmpegInfo().ffmpeg && ffmpegInfo().libx264) }, async () => {
  const b = build();
  const [mp4] = await raster.exportScene(b, { gif: false, mp4: true, outDir: outDir(), base: 'demo', flags: { scale: 1, fps: 30 } });
  assert.ok(existsSync(mp4.file));
  const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=width,height,pix_fmt,duration', '-of', 'json', mp4.file], { encoding: 'utf8' });
  const s = JSON.parse(probe.stdout).streams[0];
  assert.equal(s.width % 2, 0);
  assert.equal(s.height % 2, 0);
  assert.equal(s.pix_fmt, 'yuv420p');
  assert.ok(Math.abs(Number(s.duration) - b.duration) <= 1 / 30 + 0.001, `mp4 ${s.duration}s vs cast ${b.duration}s`);
});

test('invalid options fail with a clear message', () => {
  const { style } = build();
  assert.throws(() => raster.exportOptions(style, { scale: '4' }), /--scale must be 1, 2 or 3/);
  assert.throws(() => raster.exportOptions({ ...style, gif_dither: 'floyd_steinberg' }), /error-diffusion/);
});
