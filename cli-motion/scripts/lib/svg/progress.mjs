// Playback progress bar along the bottom edge of an animated SVG.
//
// SMIL <animate> grows a fill rect from 0 to full width over the cast duration. SMIL
// works when the SVG is embedded as an <img>, as GitHub renders READMEs, where CSS
// from the page cannot reach it. The SVG stays text, so diffs stay reviewable.
//
// The bar is drawn inside the window's clipped group (see frame.mjs), so it follows the
// rounded corners of the frame.

import { hexToRgb } from '../scene/style.mjs';

export function mixHex(a, b, amount) {
  const [r1, g1, b1] = hexToRgb(a);
  const [r2, g2, b2] = hexToRgb(b);
  const mix = (x, y) => Math.round(x + (y - x) * amount).toString(16).padStart(2, '0');
  return `#${mix(r1, r2)}${mix(g1, g2)}${mix(b1, b2)}`;
}

export function progressColours(style, theme) {
  const fill = style.progress_color ?? theme.accents.accent ?? theme.terminal.foreground;
  const track = style.progress_track ?? mixHex(theme.terminal.background, theme.terminal.foreground, 0.12);
  return { fill, track };
}

/** Markup of the bar for a window at (x, y) of `width` x `windowHeight`; clip it with the window. */
export function progressMarkup({ x, y, width, windowHeight, duration, height, fill, track, once = false }) {
  const top = y + windowHeight - height;
  const repeat = once ? 'repeatCount="1" fill="freeze"' : 'repeatCount="indefinite"';
  return (
    `<rect x="${x}" y="${top}" width="${width}" height="${height}" fill="${track}"/>` +
    `<rect x="${x}" y="${top}" width="0" height="${height}" fill="${fill}">` +
    `<animate attributeName="width" values="0;${width}" dur="${duration}s" ${repeat} calcMode="linear"/>` +
    `</rect>`
  );
}
