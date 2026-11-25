// SVG pipeline: cast → svg-term (themed) → stabilise → fades/once → progress bar.

import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { addProgressBar, progressColours } from './progress.mjs';
import { stabilizeSvgAnimation } from './stabilize.mjs';

export const SVG_TERM = 'svg-term-cli@2.1.1';

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

function runSvgTerm({ castText, theme, style, at }) {
  const dir = mkdtempSync(join(tmpdir(), 'cli-motion-'));
  try {
    const cast = join(dir, 'in.cast');
    const profile = join(dir, 'theme.xres');
    const out = join(dir, 'out.svg');
    writeFileSync(cast, castText);
    writeFileSync(profile, xresources(theme));
    const args = [
      '-y', SVG_TERM, '--in', cast, '--out', out, '--profile', profile, '--term', 'xresources',
      '--padding', String(style.padding), '--no-cursor',
    ];
    if (style.window === 'chrome') args.push('--window');
    if (at != null) args.push('--at', String(at));
    const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
    const res = spawnSync(npx, args, { encoding: 'utf8', env: { ...process.env, npm_config_loglevel: 'error' } });
    if (res.error || res.status !== 0) {
      const detail = (res.stderr || res.stdout || res.error?.message || '').split('\n')
        .filter((l) => l && !/^npm (warn|notice)/.test(l)).join('\n');
      throw new RenderError(
        `svg-term failed (${SVG_TERM} via npx; needs Node and network on first run).\n${detail}`,
      );
    }
    return readFileSync(out, 'utf8');
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

/** Animated SVG for a built scene. */
export function renderAnimated(build) {
  const { style, theme } = build;
  const once = style.playback === 'once';
  let svg = runSvgTerm({ castText: build.castText, theme, style });
  svg = stabilizeSvgAnimation(svg, { once, fades: build.fades, duration: build.duration });
  if (style.progress_bar) {
    const { fill, track } = progressColours(style, theme);
    svg = addProgressBar(svg, {
      duration: build.duration, height: Number(style.progress_height), fill, track, once,
    });
  }
  return svg;
}

/** Still frame at `at` (ms) or 'end' (the final frame, nothing scrolled off). */
export function renderStill(build, at = 'end') {
  const ms = at === 'end' ? build.endMs : Number(at);
  if (!Number.isFinite(ms) || ms < 0) throw new RenderError(`--at must be milliseconds or "end", got "${at}"`);
  return runSvgTerm({ castText: build.castText, theme: build.theme, style: build.style, at: ms });
}
