// Fonts: JetBrains Mono (default), Fira Code, Cascadia Code, IBM Plex Mono, Source Code Pro.
//
// - The regular fonts come from @fontsource (pinned in package-lock.json). Only the glyphs a
//   SVG really uses are kept (subset-font), for regular and bold, and embedded as woff2
//   base64 @font-face, so the SVG renders the same everywhere.
// - fontsource has no ❯ ✓ ● or braille, so DejaVu Sans Mono and Cascadia's braille subset
//   are tried next, glyph by glyph, before the browser's own fallback.
// - The Nerd Font variant (powerline / icons) is downloaded once into
//   ${cache}/fonts/ when a scene needs it; the URL is pinned to a nerd-fonts tag and every
//   file is checked against a sha256.

import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { dep, cacheDir, cacheRoot } from '../deps.mjs';
import { ASSETS_DIR, ConfigError } from '../config/index.mjs';
import { sfntCodepoints } from './cmap.mjs';

export const FONT_FALLBACK_STACK = "'DejaVu Sans Mono','Menlo','Consolas',monospace";
const registry = JSON.parse(readFileSync(join(ASSETS_DIR, 'fonts.json'), 'utf8'));

export const FONT_NAMES = Object.keys(registry.fonts);

export function fontInfo(name) {
  const info = registry.fonts[name];
  if (!info) throw new ConfigError(`unknown font "${name}". Valid fonts: ${FONT_NAMES.join(', ')}`);
  return { name, ...info };
}

export const nerdCacheDir = (env = process.env) => join(cacheRoot(env), 'fonts', registry.nerd_fonts_version);

export function nerdFilePath(name, weight, env = process.env) {
  const f = fontInfo(name).nerd[weight];
  return join(nerdCacheDir(env), `${createHash('sha256').update(f.url).digest('hex').slice(0, 8)}-${f.url.split('/').pop()}`);
}

export function listFonts(env = process.env) {
  return FONT_NAMES.map((name) => {
    const info = fontInfo(name);
    const cached = ['regular', 'bold'].every((w) => existsSync(nerdFilePath(name, w, env)));
    return { name, package: `@fontsource/${info.package}`, advance: info.advance, nerd: info.nerd.family, nerdCached: cached };
  });
}

/** Download (once) and verify the Nerd Font files for `name`. Returns { regular, bold } buffers. */
export async function ensureNerdFont(name, { env = process.env, log = () => {} } = {}) {
  const info = fontInfo(name);
  const out = {};
  for (const weight of ['regular', 'bold']) {
    const spec = info.nerd[weight];
    const file = nerdFilePath(name, weight, env);
    if (!existsSync(file)) {
      log(`downloading ${info.nerd.family} ${weight} (one time, into ${nerdCacheDir(env)})`);
      let res;
      try {
        res = await fetch(spec.url);
      } catch (err) {
        throw new ConfigError(`could not download the Nerd Font ${spec.url}: ${err.message}. Needs network once; or use a prompt without powerline glyphs.`);
      }
      if (!res.ok) throw new ConfigError(`could not download the Nerd Font (${res.status}) from ${spec.url}`);
      const buf = Buffer.from(await res.arrayBuffer());
      const sum = createHash('sha256').update(buf).digest('hex');
      if (sum !== spec.sha256) {
        throw new ConfigError(`Nerd Font checksum mismatch for ${spec.url}: expected ${spec.sha256}, got ${sum}. Refusing to use it.`);
      }
      mkdirSync(nerdCacheDir(env), { recursive: true });
      const tmp = `${file}.tmp-${process.pid}`;
      writeFileSync(tmp, buf);
      renameSync(tmp, file);
    }
    const buf = readFileSync(file);
    if (createHash('sha256').update(buf).digest('hex') !== spec.sha256) {
      throw new ConfigError(`cached Nerd Font ${file} fails its checksum: delete it and run again.`);
    }
    out[weight] = buf;
  }
  return out;
}

const WEIGHTS = { regular: 400, bold: 700 };

/** Source files (woff2 buffers) of a @fontsource package for one weight, latin first. */
function fontsourceFiles(pkg, weight) {
  const dir = join(cacheDir(), 'node_modules', '@fontsource', pkg, 'files');
  if (!existsSync(dir)) return [];
  const suffix = `-${WEIGHTS[weight]}-normal.woff2`;
  return readdirSync(dir)
    .filter((f) => f.endsWith(suffix))
    .sort((a, b) => Number(b.includes('-latin-') && !b.includes('ext')) - Number(a.includes('-latin-') && !a.includes('ext')) || a.localeCompare(b))
    .map((f) => ({ id: f, buf: readFileSync(join(dir, f)) }));
}

const toRanges = (cps) => {
  const sorted = [...cps].sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i < sorted.length; ) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++;
    const hex = (n) => n.toString(16).toUpperCase();
    out.push(i === j ? `U+${hex(sorted[i])}` : `U+${hex(sorted[i])}-${hex(sorted[j])}`);
    i = j + 1;
  }
  return out.join(',');
};

/**
 * Subset the font for `codepoints`. Returns
 *   { family, faces: [{ weight, family, woff2, sfnt, codepoints }], missing: [codepoint] }
 * Each face holds only glyphs that were used and that its source file really contains.
 */
export async function subsetFaces({ font, codepoints, nerd = false, env = process.env, log = () => {} }) {
  const subsetFont = dep('subset-font');
  const info = fontInfo(font);
  const family = nerd ? info.nerd.family : font;
  const faces = [];
  const missing = new Set();
  const nerdBufs = nerd ? await ensureNerdFont(font, { env, log }) : null;
  for (const weight of ['regular', 'bold']) {
    let remaining = new Set(codepoints);
    const sources = [
      ...(nerd ? [{ id: `nerd-${weight}`, buf: nerdBufs[weight] }] : []),
      ...fontsourceFiles(info.package, weight),
      ...registry.fallback.flatMap((pkg) => fontsourceFiles(pkg, weight)),
    ];
    for (const src of sources) {
      if (remaining.size === 0) break;
      const text = String.fromCodePoint(...remaining);
      const sfnt = await subsetFont(src.buf, text, { targetFormat: 'sfnt' });
      const present = new Set([...sfntCodepoints(sfnt)].filter((c) => remaining.has(c)));
      if (present.size === 0) continue;
      const only = String.fromCodePoint(...present);
      const woff2 = await subsetFont(src.buf, only, { targetFormat: 'woff2' });
      faces.push({
        weight: WEIGHTS[weight], family, woff2, sfnt: await subsetFont(src.buf, only, { targetFormat: 'sfnt' }), codepoints: present, source: src.id,
      });
      for (const c of present) remaining.delete(c);
    }
    for (const c of remaining) missing.add(c);
  }
  return { family, faces, missing: [...missing].sort((a, b) => a - b) };
}

export function fontFaceCss(faces) {
  return faces
    .map((f) => `@font-face{font-family:'${f.family}';font-weight:${f.weight};font-style:normal;`
      + `src:url(data:font/woff2;base64,${f.woff2.toString('base64')}) format('woff2');unicode-range:${toRanges(f.codepoints)}}`)
    .join('');
}

const PUA = (c) => (c >= 0xe000 && c <= 0xf8ff) || c >= 0xf0000;
export const needsNerd = (codepoints) => [...codepoints].some(PUA);

/** Distinct printable code points of every <text> run in an SVG. */
export function textCodepoints(svg) {
  const set = new Set();
  const decode = (s) => s
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, '&');
  for (const m of svg.matchAll(/<text\b[^>]*>([^<]*)<\/text>/g)) {
    for (const ch of decode(m[1])) {
      const c = ch.codePointAt(0);
      if (c >= 0x20) set.add(c);
    }
  }
  return set;
}
