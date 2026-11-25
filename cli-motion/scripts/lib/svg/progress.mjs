// Playback progress bar along the bottom edge of an animated SVG.
//
// SMIL <animate> grows a fill rect from 0 to full width over the cast duration. SMIL
// works when the SVG is embedded as an <img>, as GitHub renders READMEs, where CSS
// from the page cannot reach it. The SVG stays text, so diffs stay reviewable.

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

export function addProgressBar(svg, { duration, height, fill, track, once = false }) {
  const root = svg.match(/<svg[^>]*\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"/);
  if (!root) throw new Error('could not read width/height from the SVG root');
  const width = Number(root[1]);
  const total = Number(root[2]);
  const y = (total - height).toFixed(2);
  const radius = svg.match(/<rect width="[\d.]+" height="[\d.]+" rx="([\d.]+)"/)?.[1];
  const clip = radius
    ? `<clipPath id="cm-clip"><rect width="${width}" height="${total}" rx="${radius}" ry="${radius}"/></clipPath>`
    : '';
  const repeat = once ? 'repeatCount="1" fill="freeze"' : 'repeatCount="indefinite"';
  const bar =
    clip +
    `<g${clip ? ' clip-path="url(#cm-clip)"' : ''}>` +
    `<rect x="0" y="${y}" width="${width}" height="${height}" fill="${track}"/>` +
    `<rect x="0" y="${y}" width="0" height="${height}" fill="${fill}">` +
    `<animate attributeName="width" values="0;${width}" dur="${duration}s" ${repeat} calcMode="linear"/>` +
    `</rect></g>`;
  const out = svg.replace(/<\/svg>\s*$/, `${bar}</svg>`);
  if (out === svg) throw new Error('could not find the closing </svg> to inject before');
  return out;
}
