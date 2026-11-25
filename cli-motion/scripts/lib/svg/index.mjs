// SVG pipeline: cast → svg-term (themed) → stabilise → fades/once → progress bar.

import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { svgTermBin } from '../deps.mjs';
import { fontFaceCss, fontInfo, FONT_FALLBACK_STACK, needsNerd, subsetFaces, textCodepoints } from '../fonts/index.mjs';
import { applyFrame } from './frame.mjs';
import { progressColours, progressMarkup } from './progress.mjs';
import { stabilizeSvgAnimation } from './stabilize.mjs';

export const SVG_TERM = 'svg-term-cli@2.1.1'; // pinned in scripts/package.json, run from the dependency cache

export class RenderError extends Error {
  constructor(message) {
    super(message);
    this.name = 'RenderError';
  }
}

/** Theme → Xresources profile, the format svg-term reads colours from. */
export function xresources(theme) {
  const t = theme.terminal;
  const lines = [
    `*.foreground: ${t.foreground}`,
    `*.background: ${t.background}`,
    `*.cursorColor: ${t.cursor ?? t.foreground}`,
    `*.colorBD: ${t.foreground}`,
    ...t.ansi.map((c, i) => `*.color${i}: ${c}`),
  ];
  return `${lines.join('\n')}\n`;
}

export function runSvgTerm({ castText, theme, style, at }) {
  const dir = mkdtempSync(join(tmpdir(), 'cli-motion-'));
  try {
    const cast = join(dir, 'in.cast');
    const profile = join(dir, 'theme.xres');
    const out = join(dir, 'out.svg');
    writeFileSync(cast, castText);
    writeFileSync(profile, xresources(theme));
    let bin;
    try {
      bin = svgTermBin();
    } catch (err) {
      throw new RenderError(err.message);
    }
    const args = [
      bin, '--in', cast, '--out', out, '--profile', profile, '--term', 'xresources',
      '--padding', '0', '--no-cursor',
    ];
    if (at != null) args.push('--at', String(at));
    const res = spawnSync(process.execPath, args, { encoding: 'utf8', timeout: 120000 });
    if (res.error || res.status !== 0) {
      const detail = (res.stderr || res.stdout || res.error?.message || '').trim();
      throw new RenderError(
        `svg-term failed (${SVG_TERM}, run from the dependency cache; no network needed). Run \`cli-motion doctor\` to check it.\n${detail}`,
      );
    }
    return readFileSync(out, 'utf8');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

/**
 * Fonts and window geometry for a bare svg-term SVG. Returns { faces, family, missing, wrap }
 * where wrap(bareSvg, progress) frames one SVG (animated or a single still frame) with the
 * embedded font, so raster export can frame many stills with one font subset.
 */
export async function prepareFraming(bare, build) {
  const { style, theme } = build;
  const info = fontInfo(style.font);
  const fontSize = Number(style.font_size);
  if (!(fontSize > 0)) throw new RenderError(`font_size must be a positive number, got "${style.font_size}"`);
  const title = style.window_title ?? build.name ?? '';
  const provisional = (nerdFamily) => `'${nerdFamily}',${FONT_FALLBACK_STACK}`;

  // First pass finds the glyphs in use (the title counts), then the fonts are subset to them.
  const probe = bare.replace(/<g font-family="[^"]*"/, '<g font-family="x"');
  const codepoints = textCodepoints(probe);
  for (const ch of String(title)) codepoints.add(ch.codePointAt(0));
  const nerd = style.font_nerd === true || (style.font_nerd === 'auto' && needsNerd(codepoints));
  const subset = await subsetFaces({ font: style.font, codepoints, nerd, log: (m) => console.error(`cli-motion: ${m}`) });
  const css = fontFaceCss(subset.faces);

  const wrap = (svgIn, progress = null, frameStyle = style) => {
    const { svg: framed, geometry } = applyFrame(svgIn, {
      style: frameStyle, theme, title, fontSize, advance: info.advance, fontFamily: provisional(subset.family), progress,
    });
    return { svg: framed.replace(/^<svg[^>]*>/, (open) => `${open}<style>${css}</style>`), geometry };
  };
  return { faces: subset.faces, family: subset.family, missing: subset.missing, wrap };
}

/** Frame + fonts around a bare svg-term SVG. Returns { svg, faces, family, missing }. */
async function finish(bare, build, { progress }) {
  const prepared = await prepareFraming(bare, build);
  return { svg: prepared.wrap(bare, progress).svg, faces: prepared.faces, family: prepared.family, missing: prepared.missing };
}

function warnMissing(missing, font) {
  if (missing.length) {
    const sample = missing.slice(0, 8).map((c) => String.fromCodePoint(c)).join(' ');
    console.error(`cli-motion: note: ${missing.length} glyph(s) are not in ${font} (${sample}); the viewer's own monospace font draws them. Use font_nerd: true for icons.`);
  }
}

/** Animated SVG for a built scene. */
export async function renderAnimated(build) {
  const { style, theme } = build;
  const once = style.playback === 'once';
  let bare = runSvgTerm({ castText: build.castText, theme, style });
  bare = stabilizeSvgAnimation(bare, { once, fades: build.fades, duration: build.duration });
  const progress = style.progress_bar
    ? (g) => {
      const { fill, track } = progressColours(style, theme);
      return progressMarkup({
        x: g.margin, y: g.margin, width: g.winW, windowHeight: g.winH,
        duration: build.duration, height: Number(style.progress_height), fill, track, once,
      });
    }
    : null;
  const out = await finish(bare, build, { progress });
  warnMissing(out.missing, style.font);
  return out.svg;
}

/** Still frame at `at` (ms) or 'end'; returns { svg, faces, family } (faces: for rasterisers). */
export async function renderStillFramed(build, at = 'end') {
  const ms = at === 'end' ? build.endMs : Number(at);
  if (!Number.isFinite(ms) || ms < 0) throw new RenderError(`--at must be milliseconds or "end", got "${at}"`);
  const bare = runSvgTerm({ castText: build.castText, theme: build.theme, style: build.style, at: ms });
  return finish(bare, build, { progress: null });
}

export async function renderStill(build, at = 'end') {
  const out = await renderStillFramed(build, at);
  warnMissing(out.missing, build.style.font);
  return out.svg;
}
