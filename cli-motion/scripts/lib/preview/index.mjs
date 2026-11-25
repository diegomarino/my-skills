// `cli-motion preview`: a contact sheet of one mini scene across font × size × theme.
//
// Every cell is a real render (same pipeline as `render`: frame, embedded font subset),
// labelled with the exact option values, so someone can say "#07, that one" and paste the
// three lines under it into `style:`. PNG goes through @resvg/resvg-js, which needs the font
// as TTF bytes (it ignores @font-face), so the cells' subset faces are handed to it.

import { dep } from '../deps.mjs';
import { loadDefaults, loadTheme } from '../config/index.mjs';
import { FONT_NAMES, subsetFaces } from '../fonts/index.mjs';
import { buildCast, parseSceneDocument } from '../scene/index.mjs';
import { renderStillFramed } from '../svg/index.mjs';

export const PREVIEW_DEFAULTS = {
  fonts: FONT_NAMES,
  sizes: [16],
  themes: ['catppuccin-mocha', 'tokyonight-night', 'solarized-light'],
};

// Chosen so the fonts differ visibly: ligatures (=> != -> <= ===), confusable letters
// (Il1 O0 rn m, agQ), bold and muted. No glyphs that every font borrows from DejaVu
// (❯ ✓ ● → box drawing): they would look identical in every cell.
const MINI_SCENE = `
style: { prompt: dollar }
steps:
  - command: "git diff --stat  # Il1 O0o agQ"
  - output: |
      a => b   x != y   i -> j   n <= m   a === b
      [strong]Il1O0 agQ rn m[/] regular [muted]{ } [ ] ( ) ~ @ & #[/]
      [accent]const[/] total = items.map(x => x.n) // 9g 6b
`;

export function parseList(value, all, what) {
  if (value == null) return null;
  if (value === 'all') return all;
  const items = String(value).split(',').map((v) => v.trim()).filter(Boolean);
  if (!items.length) throw new Error(`--${what} needs at least one value`);
  return items;
}

export async function buildCells({ fonts, sizes, themes }) {
  const cells = [];
  let n = 0;
  for (const font of fonts) {
    for (const size of sizes) {
      for (const themeId of themes) {
        const theme = loadTheme(themeId);
        const style = {
          ...loadDefaults(), theme: themeId, font, font_size: size, width: 46, final_hold: '1s',
          progress_bar: false, window_title: `${font} ${size}`,
        };
        const doc = parseSceneDocument(MINI_SCENE, 'preview scene');
        const build = buildCast(doc, { style: { ...style, ...doc.style }, theme, file: 'preview scene' });
        const framed = await renderStillFramed({ ...build, name: undefined }, 'end');
        const svg = framed.svg;
        const w = Number(svg.match(/<svg[^>]*\swidth="([\d.]+)"/)[1]);
        const h = Number(svg.match(/<svg[^>]*\sheight="([\d.]+)"/)[1]);
        n += 1;
        cells.push({
          n, font, size, theme: themeId, svg, faces: framed.faces, width: w, height: h,
          label: [`#${String(n).padStart(2, '0')}`, `font: ${font}`, `font_size: ${size}`, `theme: ${themeId}`],
        });
      }
    }
  }
  return cells;
}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export function sheetHtml(cells) {
  const items = cells.map((c) => {
    const src = `data:image/svg+xml;base64,${Buffer.from(c.svg).toString('base64')}`;
    return `<figure><img src="${src}" width="${c.width}" height="${c.height}" alt="${esc(c.label.join(', '))}">`
      + `<figcaption><b>${esc(c.label[0])}</b><code>${c.label.slice(1).map(esc).join('<br>')}</code></figcaption></figure>`;
  }).join('\n');
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>cli-motion preview</title>
<style>
:root{color-scheme:light dark;--bg:#f4f4f5;--fg:#18181b;--mut:#52525b}
@media (prefers-color-scheme:dark){:root{--bg:#131316;--fg:#f4f4f5;--mut:#a1a1aa}}
body{margin:0;padding:20px 16px 40px;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif}
h1{font-size:18px;margin:0 0 4px}p{margin:0 0 20px;color:var(--mut)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,${Math.max(...cells.map((c) => c.width))}px),1fr));gap:24px 20px}
figure{margin:0}img{max-width:100%;height:auto;display:block}
figcaption{margin-top:6px;display:flex;gap:10px;align-items:flex-start}
code{font:13px/1.35 ui-monospace,Menlo,monospace;color:var(--mut)}b{font-size:13px}
</style></head><body>
<h1>cli-motion preview</h1><p>${cells.length} combinations. Pick one by its number and copy the three lines under it into <code>style:</code>.</p>
<div class="grid">
${items}
</div></body></html>
`;
}

/** Sheet as one SVG whose cells are pre-rendered PNGs (resvg), plus the label font. */
export async function sheetPng(cells, { cols = 3 } = {}) {
  const { Resvg } = dep('@resvg/resvg-js');
  const gap = 28;
  const labelH = 50;
  const margin = 32;
  const SCALE = 2;
  const rasterise = (svg, faces, extra = {}) => {
    const buffers = [...faces.map((f) => f.sfnt), ...(extra.buffers ?? [])];
    const r = new Resvg(svg, {
      font: { loadSystemFonts: false, fontBuffers: buffers, defaultFontFamily: faces[0]?.family ?? 'JetBrains Mono' },
      fitTo: { mode: 'zoom', value: extra.zoom ?? SCALE },
    });
    return r.render().asPng();
  };

  const colW = [];
  const rows = Math.ceil(cells.length / cols);
  cells.forEach((c, i) => { colW[i % cols] = Math.max(colW[i % cols] ?? 0, c.width); });
  const rowH = Array.from({ length: rows }, (_, r) => Math.max(...cells.slice(r * cols, r * cols + cols).map((c) => c.height)) + labelH);
  const totalW = margin * 2 + colW.reduce((a, b) => a + b, 0) + gap * (cols - 1);
  const totalH = margin * 2 + rowH.reduce((a, b) => a + b, 0) + gap * (rows - 1) + 30;

  const labelChars = new Set(cells.flatMap((c) => [...c.label.join('')].map((ch) => ch.codePointAt(0))));
  'cli-motion preview'.split('').forEach((ch) => labelChars.add(ch.codePointAt(0)));
  const labelFont = await subsetFaces({ font: 'JetBrains Mono', codepoints: labelChars });

  const parts = [];
  cells.forEach((c, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = margin + colW.slice(0, col).reduce((a, b) => a + b, 0) + gap * col;
    const y = margin + 30 + rowH.slice(0, row).reduce((a, b) => a + b, 0) + gap * row;
    const png = rasterise(c.svg, c.faces);
    parts.push(`<image x="${x}" y="${y}" width="${c.width}" height="${c.height}" href="data:image/png;base64,${Buffer.from(png).toString('base64')}"/>`);
    const ty = y + c.height - 8;
    parts.push(`<text x="${x}" y="${ty}" font-size="13" font-weight="700" fill="#f4f4f5">${esc(c.label[0])}</text>`);
    c.label.slice(1).forEach((line, k) => {
      parts.push(`<text x="${x + 38}" y="${ty + k * 15}" font-size="12" fill="#a1a1aa">${esc(line)}</text>`);
    });
  });
  const sheet = `<svg xmlns="http://www.w3.org/2000/svg" width="${totalW}" height="${totalH}" viewBox="0 0 ${totalW} ${totalH}" font-family="JetBrains Mono">`
    + `<rect width="${totalW}" height="${totalH}" fill="#131316"/>`
    + `<text x="${margin}" y="${margin + 4}" font-size="15" font-weight="700" fill="#f4f4f5">cli-motion preview</text>`
    + parts.join('') + '</svg>';
  return Buffer.from(rasterise(sheet, labelFont.faces));
}
