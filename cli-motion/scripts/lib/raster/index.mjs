// Raster export: stabilised frames → standalone still SVGs → resvg → GIF / MP4.
//
//  1. svg-term makes the animated reel; `reelStates` splits it into stationary states, each
//     with its exact visible interval.
//  2. buildTimeline turns states + fades + progress samples into frames (whole ms).
//  3. every frame becomes a standalone SVG: window frame, embedded font, outer background,
//     the progress bar at that moment (and a blend of two states during a fade).
//  4. @resvg/resvg-js rasterises each distinct SVG once, at an integer scale: the same
//     rasteriser, the same integer positions, the same pixels for the same state.
//  5. identical consecutive frames are merged (their durations add up), then encoded:
//     MP4 via ffmpeg concat, GIF via ffmpeg (one palette, no dithering) or gifenc.

import { createHash } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { dep } from '../deps.mjs';
import { hexToRgb } from '../scene/style.mjs';
import { parseDuration } from '../scene/index.mjs';
import { prepareFraming, RenderError, runSvgTerm } from '../svg/index.mjs';
import { progressColours, progressStaticMarkup } from '../svg/progress.mjs';
import { reelStates } from '../svg/stabilize.mjs';
import { ffmpegInfo, runFfmpeg } from './ffmpeg.mjs';
import { addHistogram, encodeGif, globalPalette, patchGifDelays } from './gif.mjs';
import { buildTimeline, snapDurations } from './timeline.mjs';

export { buildTimeline, snapDurations };

const sha = (data) => createHash('sha1').update(data).digest('hex');

/** Opaque outer colour for GIF/MP4: the configured one, else a neutral that suits the theme. */
export function outerBackground(style, theme) {
  if (style.window_background) return style.window_background;
  const [r, g, b] = hexToRgb(theme.terminal.background);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 140 ? '#ffffff' : '#0d1117';
}

export function exportOptions(style, flags = {}) {
  const num = (v, what) => {
    const n = Number(v);
    if (!Number.isFinite(n)) throw new RenderError(`${what} must be a number, got "${v}"`);
    return n;
  };
  const scale = num(flags.scale ?? style.scale, '--scale');
  if (![1, 2, 3].includes(scale)) throw new RenderError(`--scale must be 1, 2 or 3 (integer scales keep text pixel-aligned), got ${scale}`);
  const fps = num(flags.fps ?? style.mp4_fps, '--fps');
  if (!(fps >= 1 && fps <= 120)) throw new RenderError(`--fps must be between 1 and 120, got ${fps}`);
  const gifFps = num(style.gif_fps, 'gif_fps');
  const dither = style.gif_dither === true ? 'bayer' : style.gif_dither;
  if (dither !== false && dither !== 'bayer') {
    throw new RenderError(`gif_dither must be false (default) or bayer; error-diffusion dithering is refused because it shimmers between frames, got ${JSON.stringify(style.gif_dither)}`);
  }
  return {
    scale, fps, gifFps, dither,
    gifProgressStep: parseDuration(style.gif_progress_step, 'gif_progress_step'),
  };
}

/** Rasteriser bound to one font set; keeps the TTFs in a temp dir until close(). */
export function makeRasteriser(faces, scale) {
  const { Resvg } = dep('@resvg/resvg-js');
  const dir = mkdtempSync(join(tmpdir(), 'cli-motion-raster-'));
  const fontFiles = faces.map((f, i) => {
    const file = join(dir, `${i}-${f.family.replace(/\W+/g, '')}-${f.weight}.ttf`);
    writeFileSync(file, f.sfnt);
    return file;
  });
  return {
    render(svg) {
      const r = new Resvg(svg, {
        font: { loadSystemFonts: false, fontFiles, defaultFontFamily: faces[0]?.family ?? 'JetBrains Mono' },
        fitTo: { mode: 'zoom', value: scale },
      }).render();
      return { rgba: Buffer.from(r.pixels), width: r.width, height: r.height, png: () => r.asPng() };
    },
    close: () => rmSync(dir, { recursive: true, force: true }),
  };
}

/** Everything shared by the formats: states, framing, a per-frame SVG factory. */
export async function prepareExport(build, { log = () => {} } = {}) {
  const style = { ...build.style, window_background: outerBackground(build.style, build.theme) };
  const bare = runSvgTerm({ castText: build.castText, theme: build.theme, style });
  const { total, states, compose } = reelStates(bare);
  const prepared = await prepareFraming(bare, build);
  if (prepared.missing.length) log(`note: ${prepared.missing.length} glyph(s) are not in ${style.font}; export uses only the embedded font, so they may be blank`);
  const { fill, track } = progressColours(style, build.theme);
  const barHeight = Number(style.progress_height);

  const frameSvg = (f) => {
    const a = f.base != null ? states[f.base].markup : states[f.state].markup;
    const markup = f.base != null
      ? `<g opacity="${(1 - f.alpha).toFixed(4)}">${a}</g><g opacity="${f.alpha.toFixed(4)}">${states[f.state].markup}</g>`
      : a;
    const progress = f.progress == null ? null : (g) => progressStaticMarkup({
      x: g.margin, y: g.margin, width: g.winW, windowHeight: g.winH, fraction: f.progress, height: barHeight, fill, track,
    });
    return prepared.wrap(compose(markup), progress, style).svg;
  };
  return { style, total, states, faces: prepared.faces, frameSvg, background: style.window_background };
}

/** Frames of one format: snapped durations, svg per frame (cached by key). */
function planFrames(prep, build, { progressStep, fadeFps, unit, minUnits }) {
  const style = prep.style;
  const timeline = buildTimeline({
    states: prep.states, fades: build.fades, total: prep.total, fadeFps,
    progressStep: style.progress_bar ? progressStep : null,
  });
  return snapDurations(timeline, unit, minUnits).map(({ index, units }) => ({
    frame: timeline[index], units, key: JSON.stringify([timeline[index].state, timeline[index].base, timeline[index].alpha, timeline[index].progress]),
  }));
}

/** Rasterise the plan, merging pixel-identical consecutive frames. Calls visit(unique) per kept frame. */
function rasterPlan(prep, plan, raster, keepRgba) {
  const svgByKey = new Map();
  const pixelsByKey = new Map();
  const merged = [];
  for (const item of plan) {
    let px = pixelsByKey.get(item.key);
    if (!px) {
      if (!svgByKey.has(item.key)) svgByKey.set(item.key, prep.frameSvg(item.frame));
      const img = raster.render(svgByKey.get(item.key));
      px = { hash: sha(img.rgba), width: img.width, height: img.height, rgba: keepRgba ? img.rgba : null, png: keepRgba ? null : img.png(), key: item.key };
      pixelsByKey.set(item.key, px);
    }
    const prev = merged.at(-1);
    if (prev && prev.px.hash === px.hash) prev.units += item.units;
    else merged.push({ px, units: item.units, frame: item.frame });
  }
  return { merged, unique: new Map([...pixelsByKey.values()].map((p) => [p.hash, p])) };
}

function evenPad(bg) {
  return `pad=ceil(iw/2)*2:ceil(ih/2)*2:color=${bg.replace('#', '0x')}`;
}

async function exportMp4(build, prep, opts, raster, outFile, tmp) {
  const info = ffmpegInfo();
  if (!info.ffmpeg) throw new RenderError('MP4 export needs ffmpeg (not found on PATH). Install ffmpeg, or export --gif only.');
  if (!info.libx264) throw new RenderError('this ffmpeg has no libx264 encoder; install a full ffmpeg build for MP4 export.');
  const plan = planFrames(prep, build, { progressStep: 1 / opts.fps, fadeFps: opts.fps, unit: 1, minUnits: 1 });
  const { merged, unique } = rasterPlan(prep, plan, raster, false);
  const dir = join(tmp, 'mp4');
  mkdirSync(dir);
  const names = new Map();
  let n = 0;
  for (const [hash, px] of unique) {
    const name = `f${String(n++).padStart(5, '0')}.png`;
    writeFileSync(join(dir, name), px.png);
    names.set(hash, name);
  }
  const lines = merged.map((m) => `file '${names.get(m.px.hash)}'\nduration ${(m.units / 1000).toFixed(3)}`);
  lines.push(`file '${names.get(merged.at(-1).px.hash)}'`);
  writeFileSync(join(dir, 'list.txt'), `${lines.join('\n')}\n`);
  const vf = [
    `fps=${opts.fps}`, evenPad(prep.background),
    'scale=out_color_matrix=bt709:out_range=tv', 'format=yuv420p',
  ].join(',');
  const res = runFfmpeg([
    '-f', 'concat', '-safe', '0', '-i', join(dir, 'list.txt'), '-vf', vf,
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-tune', 'animation',
    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
    '-movflags', '+faststart', '-an', outFile,
  ]);
  if (!res.ok) throw new RenderError(`ffmpeg failed while writing the MP4:\n${res.detail}`);
  return { frames: merged.length, unique: unique.size, seconds: merged.reduce((s, m) => s + m.units, 0) / 1000 };
}

async function exportGif(build, prep, opts, raster, outFile, tmp, encoder, log) {
  const info = ffmpegInfo();
  const useFfmpeg = encoder === 'ffmpeg' || (encoder === 'auto' && info.ffmpeg);
  if (useFfmpeg && !info.ffmpeg) throw new RenderError('--encoder ffmpeg needs ffmpeg on PATH');
  const once = build.style.playback === 'once';
  // GIF delays are centiseconds and browsers treat anything under 2 cs as 10 cs: snap to 10 ms, never below 20 ms
  const plan = planFrames(prep, build, {
    progressStep: opts.gifProgressStep, fadeFps: opts.gifFps, unit: 10, minUnits: 2,
  });

  if (useFfmpeg) {
    const { merged, unique } = rasterPlan(prep, plan, raster, false);
    const dir = join(tmp, 'gif');
    mkdirSync(dir);
    const names = new Map();
    let n = 0;
    for (const [hash, px] of unique) {
      const name = `f${String(n++).padStart(5, '0')}.png`;
      writeFileSync(join(dir, name), px.png);
      names.set(hash, name);
    }
    // uniform 1 s per frame here: ffmpeg only chooses the palette and maps pixels (see patchGifDelays)
    // passthrough, not cfr: cfr would repeat every 1 s frame to fill the output frame rate, and
    // the surplus copies would then be cut off along with the real frames
    const lines = merged.map((m) => `file '${names.get(m.px.hash)}'\nduration 1`);
    lines.push(`file '${names.get(merged.at(-1).px.hash)}'`);
    writeFileSync(join(dir, 'list.txt'), `${lines.join('\n')}\n`);
    const dither = opts.dither === 'bayer' ? 'dither=bayer:bayer_scale=3' : 'dither=none';
    const graph = `[0:v]split[a][b];[a]palettegen=stats_mode=full:max_colors=256[p];[b][p]paletteuse=${dither}:diff_mode=rectangle`;
    const raw = join(dir, 'raw.gif');
    const args = ['-f', 'concat', '-safe', '0', '-i', join(dir, 'list.txt'), '-filter_complex', graph, '-loop', once ? '-1' : '0'];
    // `-fps_mode` replaced `-vsync` in ffmpeg 5.1: try the new flag, fall back for older builds
    let res = runFfmpeg([...args, '-fps_mode', 'passthrough', raw]);
    if (!res.ok && /Unrecognized option 'fps_mode'/.test(res.detail)) res = runFfmpeg([...args, '-vsync', 'passthrough', raw]);
    if (!res.ok) throw new RenderError(`ffmpeg failed while writing the GIF:\n${res.detail}`);
    writeFileSync(outFile, patchGifDelays(readFileSync(raw), merged.map((m) => m.units)));
    return { frames: merged.length, unique: unique.size, seconds: merged.reduce((s, m) => s + m.units, 0) / 100, encoder: 'ffmpeg' };
  }

  if (opts.dither === 'bayer') log('note: ordered (bayer) dithering needs ffmpeg; the pure-JS GIF uses none');
  // pass 1: render every distinct frame once, collect the colours of the whole animation
  const histogram = new Map();
  let { merged, unique } = rasterPlan(prep, plan, raster, true);
  for (const px of unique.values()) addHistogram(histogram, px.rgba);
  const { palette, exact } = globalPalette(histogram);
  // pass 2: map every frame onto that one palette (no dithering) and write
  async function* frames() {
    for (const m of merged) yield { rgba: m.px.rgba, width: m.px.width, height: m.px.height, delayMs: m.units * 10 };
  }
  const bytes = await encodeGif(frames(), palette, { loop: !once });
  writeFileSync(outFile, bytes);
  log(`gif palette: ${exact ? `${palette.length} colours (exact)` : '256 colours (median cut over all frames)'}`);
  return { frames: merged.length, unique: unique.size, seconds: merged.reduce((s, m) => s + m.units, 0) / 100, encoder: 'gifenc' };
}

/**
 * Export a built scene. formats: { gif, mp4 }. Returns [{ format, file, ... }].
 */
export async function exportScene(build, { gif, mp4, outDir, base, flags = {}, encoder = 'auto', log = () => {} }) {
  const opts = exportOptions(build.style, flags);
  if (!['auto', 'ffmpeg', 'js'].includes(encoder)) throw new RenderError(`--encoder must be auto, ffmpeg or js, got "${encoder}"`);
  mkdirSync(outDir, { recursive: true });
  const prep = await prepareExport(build, { log });
  const raster = makeRasteriser(prep.faces, opts.scale);
  const tmp = mkdtempSync(join(tmpdir(), 'cli-motion-export-'));
  const results = [];
  try {
    if (mp4) {
      const file = join(outDir, `${base}.mp4`);
      results.push({ format: 'mp4', file, ...(await exportMp4(build, prep, opts, raster, file, tmp)) });
    }
    if (gif) {
      const file = join(outDir, `${base}.gif`);
      results.push({ format: 'gif', file, ...(await exportGif(build, prep, opts, raster, file, tmp, encoder === 'js' ? 'js' : encoder, log)) });
    }
  } finally {
    raster.close();
    rmSync(tmp, { recursive: true, force: true });
  }
  return results;
}
