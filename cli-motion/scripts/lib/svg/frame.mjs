// Window frame, drawn by us instead of svg-term's `--window`.
//
// svg-term is run with `--padding 0` and no window, so it yields a bare terminal: a root
// <rect> and one nested <svg> holding the (stabilised) frames. This post-processor
// rebuilds the page around that terminal:
//
//   <svg>                                  root, sized to window + shadow margin
//     <defs> shadow filter, window clipPath
//     [outer background rect]              window_background (GIF/MP4 need an opaque edge)
//     [shadow rect + feGaussianBlur]       window_shadow
//     <g clip-path>                        everything inside the rounded window
//       window background, title bar, three dots, title, terminal, progress bar
//     </g>
//     hairline border                      keeps light themes visible on white pages
//
// Why this works inside <img> on GitHub: only plain shapes, a filter and a clipPath, no
// scripts, no external references, no foreignObject. The progress bar lives INSIDE the
// clipped group, so it follows the rounded corners.
//
// Layout stays on whole pixels (the terminal is placed with x/y, never a transform) so the
// glyph anti-aliasing is identical in every frame.

import { mixHex } from './progress.mjs';

export const BAR_HEIGHT = 36;
export const SHADOW_MARGIN = 36;
export const OUTER_MARGIN = 16;
const UNIT = 1.002; // svg-term's advance of one column, in its own units

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const n2 = (n) => String(Number(n.toFixed(2)));

/** Geometry of the frame for a terminal of `termW` x `termH` px. */
export function frameGeometry(style, termW, termH) {
  const variant = style.window;
  const bar = variant === 'chrome' ? BAR_HEIGHT : 0;
  const pad = Number(style.padding);
  const shadow = variant !== 'none' && style.window_shadow !== false;
  const margin = variant === 'none' ? 0 : shadow ? SHADOW_MARGIN : style.window_background ? OUTER_MARGIN : 0;
  const radius = variant === 'none' ? 0 : Math.max(0, Number(style.window_radius));
  const winW = Math.ceil(termW) + 2 * pad;
  const winH = bar + Math.ceil(termH) + 2 * pad;
  return {
    variant, bar, pad, shadow, margin, radius, winW, winH,
    width: winW + 2 * margin, height: winH + 2 * margin,
  };
}

/**
 * Wrap a bare svg-term SVG (made with --padding 0) in the window frame.
 * `progress` is an optional function (geometry) → markup placed inside the clipped window.
 */
export function applyFrame(svg, { style, theme, title = '', fontFamily, fontSize, advance, progress = null }) {
  const root = svg.match(/^<svg[^>]*>/);
  const closeAt = svg.lastIndexOf('</svg>');
  if (!root || closeAt < 0) throw new Error('unsupported svg-term output: no root <svg>');
  let body = svg.slice(root[0].length, closeAt);
  body = body.replace(/^<rect[^>]*class="a"[^>]*\/>/, '');
  const innerOpen = body.match(/^<svg\b[^>]*>/);
  if (!innerOpen) throw new Error('unsupported svg-term output: no terminal <svg>');
  const vb = innerOpen[0].match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  if (!vb) throw new Error('unsupported svg-term output: no viewBox on the terminal');

  // Scale so one column is exactly advance × font-size px wide.
  const factor = (advance * fontSize) / UNIT;
  const termW = Number(vb[1]) * factor;
  const termH = Number(vb[2]) * factor;
  const g = frameGeometry(style, termW, termH);

  const x = g.margin + g.pad;
  const y = g.margin + g.bar + g.pad;
  const newOpen = innerOpen[0]
    .replace(/\swidth="[\d.]+"/, ` width="${n2(termW)}"`)
    .replace(/\sheight="[\d.]+"/, ` height="${n2(termH)}"`)
    .replace(/\sx="[\d.%]+"/, '')
    .replace(/\sy="[\d.%]+"/, '')
    .replace(/^<svg/, `<svg x="${x}" y="${y}"`);
  body = newOpen + body.slice(innerOpen[0].length);
  body = body.replace(
    /<g font-family="[^"]*" font-size="[\d.]+">/,
    `<g font-family="${esc(fontFamily)}" font-size="${n2(fontSize / factor)}">`,
  );

  const bg = theme.terminal.background;
  const fg = theme.terminal.foreground;
  const m = g.margin;
  const r = g.radius;
  const parts = [];
  const defs = [];
  if (g.variant !== 'none') {
    defs.push(`<clipPath id="cm-clip"><rect x="${m}" y="${m}" width="${g.winW}" height="${g.winH}" rx="${r}" ry="${r}"/></clipPath>`);
  }
  if (g.shadow) {
    defs.push('<filter id="cm-shadow" x="-30%" y="-30%" width="160%" height="170%" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="10"/></filter>');
  }
  if (defs.length) parts.push(`<defs>${defs.join('')}</defs>`);
  if (style.window_background) parts.push(`<rect width="${g.width}" height="${g.height}" fill="${style.window_background}"/>`);
  if (g.shadow) {
    parts.push(`<rect x="${m + 4}" y="${m + 10}" width="${g.winW - 8}" height="${g.winH - 6}" rx="${r + 2}" ry="${r + 2}" fill="#000" fill-opacity="0.5" filter="url(#cm-shadow)"/>`);
  }
  const clip = g.variant === 'none' ? '' : ' clip-path="url(#cm-clip)"';
  const win = [`<rect x="${m}" y="${m}" width="${g.winW}" height="${g.winH}" fill="${bg}"/>`];
  if (g.bar) {
    const barBg = mixHex(bg, fg, 0.07);
    win.push(`<rect x="${m}" y="${m}" width="${g.winW}" height="${g.bar}" fill="${barBg}"/>`);
    win.push(`<rect x="${m}" y="${m + g.bar - 1}" width="${g.winW}" height="1" fill="${mixHex(bg, fg, 0.12)}"/>`);
    const cy = m + g.bar / 2;
    ['#ff5f58', '#ffbd2e', '#18c132'].forEach((c, i) => {
      win.push(`<circle cx="${m + 20 + i * 20}" cy="${cy}" r="6" fill="${c}"/>`);
    });
    if (title) {
      win.push(
        `<text x="${m + g.winW / 2}" y="${cy + 4.5}" text-anchor="middle" font-family="${esc(fontFamily)}" font-size="13" `
        + `fill="${mixHex(fg, bg, 0.45)}">${esc(title)}</text>`,
      );
    }
  }
  win.push(body);
  if (progress) win.push(progress(g));
  parts.push(`<g${clip}>${win.join('')}</g>`);
  if (g.variant !== 'none') {
    parts.push(
      `<rect x="${m + 0.5}" y="${m + 0.5}" width="${g.winW - 1}" height="${g.winH - 1}" rx="${Math.max(0, r - 0.5)}" ry="${Math.max(0, r - 0.5)}" `
      + `fill="none" stroke="${mixHex(bg, fg, 0.18)}" stroke-width="1"/>`,
    );
  }
  const head = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${g.width}" height="${g.height}" viewBox="0 0 ${g.width} ${g.height}">`;
  return { svg: `${head}${parts.join('')}</svg>`, geometry: g };
}
