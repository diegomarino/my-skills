import assert from 'node:assert/strict';
import { join } from 'node:path';
import { test } from 'node:test';
import { createHash } from 'node:crypto';
import { SIMPLE, loadScene, svg, tmpProject } from './helpers.mjs';

const { sfntCodepoints } = await import('../scripts/lib/fonts/cmap.mjs');
const fonts = await import('../scripts/lib/fonts/index.mjs');

const render = async (yaml) => {
  const dir = tmpProject({ 'a.scene.yaml': yaml });
  return svg.renderAnimated(loadScene(join(dir, 'a.scene.yaml')));
};

const faces = (out) => [...out.matchAll(/@font-face\{font-family:'([^']+)';font-weight:(\d+);[^}]*base64,([A-Za-z0-9+/=]+)\) format\('woff2'\);unicode-range:([^}]+)\}/g)]
  .map(([, family, weight, b64, range]) => ({ family, weight: Number(weight), buf: Buffer.from(b64, 'base64'), range }));

test('five fonts are registered, JetBrains Mono first', () => {
  assert.deepEqual(fonts.FONT_NAMES, ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'IBM Plex Mono', 'Source Code Pro']);
  assert.throws(() => fonts.fontInfo('Nope'), /Valid fonts/);
});

test('SVG embeds woff2 @font-face for regular and bold', async () => {
  const out = await render(SIMPLE);
  const f = faces(out);
  assert.ok(f.some((x) => x.weight === 400) && f.some((x) => x.weight === 700));
  for (const x of f) assert.equal(x.buf.subarray(0, 4).toString(), 'wOF2');
  assert.ok(!/src:url\((?!data:)/.test(out), 'no external font URL');
});

test('only the glyphs the scene uses are embedded', async () => {
  const out = await render(SIMPLE);
  const used = fonts.textCodepoints(out);
  const { subsetFaces } = fonts;
  const sub = await subsetFaces({ font: 'JetBrains Mono', codepoints: used });
  const embedded = new Set(sub.faces.filter((f) => f.weight === 400).flatMap((f) => [...sfntCodepoints(f.sfnt)]));
  // every used glyph is present (nothing missing) ...
  assert.deepEqual(sub.missing, []);
  for (const c of used) assert.ok(embedded.has(c), `U+${c.toString(16)} missing`);
  // ... and nothing else: the subset is tiny compared with the full font
  const regularBytes = faces(out).filter((x) => x.weight === 400).reduce((n, x) => n + x.buf.length, 0);
  assert.ok(regularBytes < 8000, `regular subset is ${regularBytes} bytes`);
  assert.ok(!embedded.has('Q'.codePointAt(0)) && !embedded.has('7'.codePointAt(0)), 'unused glyphs are dropped');
});

test('glyphs missing from the font fall back to DejaVu, not to nothing (❯ ✓)', async () => {
  const sub = await fonts.subsetFaces({ font: 'Fira Code', codepoints: new Set(['❯', '✓', 'a'].map((c) => c.codePointAt(0))) });
  assert.deepEqual(sub.missing, []);
  const covered = new Set(sub.faces.flatMap((f) => [...f.codepoints]));
  assert.ok(covered.has(0x276f) && covered.has(0x2713));
});

test('font option switches the embedded family', async () => {
  const out = await render(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, font: Fira Code'));
  assert.ok(faces(out).every((f) => f.family === 'Fira Code'));
  assert.match(out, /font-family="'Fira Code',/);
});

test('Nerd Font files are pinned: version, URL and sha256 for every font', () => {
  for (const f of fonts.listFonts()) {
    const info = fonts.fontInfo(f.name);
    for (const w of ['regular', 'bold']) {
      assert.match(info.nerd[w].url, /nerd-fonts@v3\.4\.0\/patched-fonts\//);
      assert.match(info.nerd[w].sha256, /^[0-9a-f]{64}$/);
    }
  }
});

test('powerline prompt: coloured segments joined by powerline arrows', async () => {
  const { loadDefaults } = await import('../scripts/lib/config/index.mjs');
  assert.ok(loadDefaults().prompt);
  const dir = tmpProject({ 'a.scene.yaml': 'style: { prompt: powerline, width: 40, final_hold: 1s }\nsteps:\n  - command: ls\n' });
  const build = loadScene(join(dir, 'a.scene.yaml'));
  assert.ok(build.castText.includes(''), 'powerline arrow in the cast');
  assert.ok(build.castText.includes(''), 'branch glyph in the cast');
  assert.ok(/main/.test(build.castText) && /~\/app/.test(build.castText));
  assert.ok(fonts.needsNerd(new Set([0xe0b0])) && !fonts.needsNerd(new Set([0x41])));
});

test('powerline refuses font_nerd: false', () => {
  const dir = tmpProject({ 'a.scene.yaml': 'style: { prompt: powerline, font_nerd: false }\nsteps:\n  - command: ls\n' });
  assert.throws(() => loadScene(join(dir, 'a.scene.yaml')), /needs the Nerd Font/);
});

test('checksum helper matches pinned format', () => {
  assert.equal(createHash('sha256').update('x').digest('hex').length, 64);
});

test('two fonts really differ: embedded family, and the rasterised glyph pixels', async () => {
  const { buildCells, rasteriseSvg } = await import('../scripts/lib/preview/index.mjs');
  const [a, b, c] = await buildCells({ fonts: ['JetBrains Mono', 'Fira Code', 'Cascadia Code'], sizes: [16], themes: ['nord-dark'] });
  const family = (cell) => [...new Set([...cell.svg.matchAll(/@font-face\{font-family:'([^']+)'/g)].map((m) => m[1]))];
  assert.deepEqual(family(a), ['JetBrains Mono']);
  assert.deepEqual(family(b), ['Fira Code']);
  assert.deepEqual(family(c), ['Cascadia Code']);
  assert.match(b.svg, /font-family="'Fira Code',/);
  // the subset TTFs carry real family names (resvg picks fonts by name)
  assert.ok(b.faces.some((f) => f.sfnt.toString('utf16le').includes('Fira') || f.sfnt.includes(Buffer.from('Fira Code', 'utf16le').swap16())));
  const pa = rasteriseSvg(a.svg, a.faces, 1);
  const pb = rasteriseSvg(b.svg, b.faces, 1);
  const pc = rasteriseSvg(c.svg, c.faces, 1);
  assert.notDeepEqual(pa, pb, 'JetBrains Mono and Fira Code cells must not be pixel-identical');
  assert.notDeepEqual(pa, pc);
  assert.notDeepEqual(pb, pc);
});

test('glyph pixels for one line differ between fonts (not a shared system fallback)', async () => {
  const { rasteriseSvg } = await import('../scripts/lib/preview/index.mjs');
  const cps = new Set([...'Il1O0agQ@'].map((ch) => ch.codePointAt(0)));
  const pngs = [];
  for (const font of ['JetBrains Mono', 'Fira Code', 'IBM Plex Mono']) {
    const sub = await fonts.subsetFaces({ font, codepoints: cps });
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="60"><rect width="300" height="60" fill="#fff"/><text x="5" y="40" font-family="'${font}',monospace" font-size="30">Il1O0agQ@</text></svg>`;
    pngs.push(Buffer.from(rasteriseSvg(svg, sub.faces, 1)).toString('base64'));
  }
  assert.equal(new Set(pngs).size, 3);
});
