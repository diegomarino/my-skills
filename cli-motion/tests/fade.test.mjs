// Fade = a real cross-fade in every format: at the middle of the fade the outgoing text is
// visible at partial strength, in the SVG (frozen at that instant and rasterised by resvg),
// in the GIF and in the MP4 (decoded with ffmpeg).

import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { loadScene, svg, tmpProject } from './helpers.mjs';

const raster = await import('../scripts/lib/raster/index.mjs');
const { ffmpegInfo } = await import('../scripts/lib/raster/ffmpeg.mjs');
const { fadeBoundary } = await import('../scripts/lib/fades.mjs');
const { buildTimeline } = raster;

const FADE = 0.8;
const SCENE = `
name: fade
style: { width: 40, final_hold: 1s, typing_jitter: 0, progress_bar: false, window_background: "#202020", transition_duration: ${FADE}s }
scenes:
  - steps:
      - command: "echo OLD TEXT"
      - output: "[accent]OLD OLD OLD OLD OLD[/]"
      - pause: 1s
  - transition: fade
    steps:
      - pause: 2s
`;

const build = () => loadScene(join(tmpProject({ 'a.scene.yaml': SCENE }), 'a.scene.yaml'));

// ── a tiny CSS-animation evaluator: freeze the animated SVG at time t ───────────────────────

function freezeSvg(svgText, t) {
  const keyframes = new Map();
  for (const m of svgText.matchAll(/@keyframes ([\w-]+)\{((?:[^{}]|\{[^{}]*\})*)\}/g)) {
    const stops = [];
    for (const s of m[2].matchAll(/([\d.%,]+)\{([^}]*)\}/g)) {
      const props = Object.fromEntries(s[2].split(';').filter(Boolean).map((d) => d.split(':')));
      for (const pct of s[1].split(',')) stops.push({ at: parseFloat(pct), props });
    }
    keyframes.set(m[1], stops.sort((a, b) => a.at - b.at));
  }
  const valueAt = (stops, prop, p, smooth) => {
    const own = stops.filter((s) => prop in s.props);
    if (!own.length) return null;
    let i = -1;
    own.forEach((s, k) => { if (s.at <= p) i = k; });
    if (i < 0) return own[0].props[prop];
    if (!smooth || i === own.length - 1) return own[i].props[prop];
    const a = own[i];
    const b = own[i + 1];
    if (b.at === a.at) return b.props[prop];
    return String(Number(a.props[prop]) + ((Number(b.props[prop]) - Number(a.props[prop])) * (p - a.at)) / (b.at - a.at));
  };
  return svgText.replace(/<svg style="([^"]*animation:[^"]*)">/g, (_, style) => {
    const anim = style.match(/animation:(.*)$/)[1].split(',');
    const out = { visibility: 'hidden', opacity: '1' };
    for (const a of anim) {
      const [name, dur, timing] = a.trim().split(/\s+/);
      const p = ((t % parseFloat(dur)) / parseFloat(dur)) * 100;
      const stops = keyframes.get(name);
      const vis = valueAt(stops, 'visibility', p, false);
      if (vis) out.visibility = vis;
      const op = valueAt(stops, 'opacity', p, timing === 'linear');
      if (op != null) out.opacity = op;
    }
    return `<svg style="${out.visibility === 'hidden' ? 'display:none' : `opacity:${out.opacity}`}">`;
  });
}

/** Sum of per-pixel colour distance between two same-size RGBA/RGB buffers. */
function ink(a, b, channels) {
  let sum = 0;
  for (let i = 0; i < a.length; i += channels) {
    sum += Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]);
  }
  return sum;
}

function assertMidFade(label, before, mid, blank, channels) {
  const full = ink(before, blank, channels);
  const part = ink(mid, blank, channels);
  assert.ok(full > 5000, `${label}: the outgoing screen has visible text (ink ${full})`);
  const ratio = part / full;
  assert.ok(ratio > 0.25 && ratio < 0.75, `${label}: old text at partial strength mid-fade, ratio ${ratio.toFixed(2)} (1 = cut late, 0 = cut early)`);
}

test('SVG: the outgoing frame fades out, stationary (no translate), the old text is half-strength mid-fade', async () => {
  const b = build();
  const fade = b.fades[0];
  assert.equal(fade.duration, FADE);
  const animated = await svg.renderAnimated(b);
  assert.ok(!/translate/.test(animated.replace(/<style>@font-face[\s\S]*?<\/style>/, '')), 'frames stay stationary');
  const prep = await raster.prepareExport(b);
  const r = raster.makeRasteriser(prep.faces, 1);
  try {
    const at = (t) => r.render(freezeSvg(animated, t)).rgba;
    const before = at(fade.at - 0.1);
    const mid = at(fade.at + fade.duration / 2);
    const blank = at(fade.at + fade.duration + 0.3);
    assertMidFade('svg', before, mid, blank, 4);
  } finally { r.close(); }
});

test('timeline: the fade starts on svg-term\'s boundary even when it is a few ms before the cast marker', () => {
  // svg-term put the clear at 7.010 s; the cast marks it at 7.012 s
  const states = [{ start: 0, end: 7.010 }, { start: 7.010, end: 9 }];
  const tl = buildTimeline({ states, fades: [{ at: 7.012, duration: 0.8 }], total: 9, fadeFps: 15 });
  const blended = tl.filter((f) => f.alpha != null);
  assert.ok(blended.length >= 10);
  assert.ok(blended.every((f) => f.base === 0 && f.state === 1), 'blends the populated state 0 into the cleared state 1');
  assert.equal(fadeBoundary([0, 7.010], 7.012), 1);
  assert.equal(fadeBoundary([0, 7.015], 7.012), 1);
  assert.equal(fadeBoundary([0, 6.5], 7.012), -1);
});

/** Decode the frame on screen at `t` seconds as rgb24 (resampled to 50 fps, frame = floor(t*50)). */
function frameAt(file, t) {
  const probe = JSON.parse(spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=width,height', '-of', 'json', file], { encoding: 'utf8' }).stdout).streams[0];
  const res = spawnSync('ffmpeg', ['-v', 'error', '-i', file, '-vf', 'fps=50', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], { maxBuffer: 1 << 30 });
  assert.equal(res.status, 0, String(res.stderr));
  const size = probe.width * probe.height * 3;
  const i = Math.floor(t * 50);
  assert.ok((i + 1) * size <= res.stdout.length, 'frame inside the file');
  return res.stdout.subarray(i * size, (i + 1) * size);
}

for (const [format, ok] of [['gif', ffmpegInfo().ffmpeg], ['mp4', ffmpegInfo().ffmpeg && ffmpegInfo().libx264]]) {
  test(`${format.toUpperCase()}: old text is at partial strength mid-fade, not already gone`, { skip: !ok }, async () => {
    const b = build();
    const fade = b.fades[0];
    const dir = mkdtempSync(join(tmpdir(), 'cli-motion-fade-'));
    const [out] = await raster.exportScene(b, { gif: format === 'gif', mp4: format === 'mp4', outDir: dir, base: 'f', encoder: format === 'gif' ? 'ffmpeg' : 'auto', flags: { scale: 1, fps: 30 } });
    const before = frameAt(out.file, fade.at - 0.1);
    const mid = frameAt(out.file, fade.at + fade.duration / 2);
    const blank = frameAt(out.file, fade.at + fade.duration + 0.3);
    assertMidFade(format, before, mid, blank, 3);
  });
}
