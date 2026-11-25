// Banner effects: pure JS, seeded, no dependencies.
//
// A banner is a grid of cells ({ ch, fg, at }): fg is #rrggbb or null (terminal foreground),
// at the SGR attribute params ('' or '1' for bold). An effect turns the grid into a list of
// frames (each a list of rendered row strings). The LAST frame is always the static banner.

export const EFFECT_NAMES = ['type', 'wipe', 'lines', 'slide', 'rainbow', 'gradient-sweep', 'pulse', 'decrypt', 'glitch'];

/** Default duration (s) and frames per second per effect. Colour effects repaint every cell, so their fps is low. */
export const EFFECT_DEFAULTS = {
  type: { duration: 1.2, fps: 20 },
  wipe: { duration: 0.8, fps: 20 },
  lines: { duration: 0.8, fps: 10 },
  slide: { duration: 0.7, fps: 20 },
  rainbow: { duration: 2.4, fps: 12 },
  'gradient-sweep': { duration: 2.4, fps: 12 },
  pulse: { duration: 1.6, fps: 12 },
  decrypt: { duration: 1.4, fps: 12 },
  glitch: { duration: 1.2, fps: 12 },
};

export const SLIDE_DIRECTIONS = ['left', 'right', 'top', 'bottom'];
const NOISE_GLYPHS = '!<>-_\\/[]{}=+*^?#%&01';
const BLANK = Object.freeze({ ch: ' ', fg: null, at: '' });

export class EffectError extends Error {
  constructor(message) {
    super(message);
    this.name = 'EffectError';
  }
}

/** Seeded LCG (same constants as the cast's): identical input → identical frames. */
export function makeRng(seed) {
  let s = (Number(seed) >>> 0) & 0x7fffffff;
  const next = () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
  next();
  return next;
}

export function hashSeed(text) {
  let h = 2166136261;
  for (const ch of String(text)) h = Math.imul(h ^ ch.codePointAt(0), 16777619);
  return h >>> 0;
}

// ── colour helpers ──────────────────────────────────────────────────────────

const toRgb = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const toHex = (rgb) => `#${rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('')}`;
export const mix = (a, b, t) => {
  const [x, y] = [toRgb(a), toRgb(b)];
  return toHex(x.map((v, i) => v + (y[i] - v) * t));
};

function hsl(h, s, l) {
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return toHex([f(0) * 255, f(8) * 255, f(4) * 255]);
}

const frac = (x) => x - Math.floor(x);

/** Sample a looping palette at u in [0,1): blends neighbouring colours. */
function samplePalette(colours, u) {
  const loop = [...colours, colours[0]];
  const x = frac(u) * (loop.length - 1);
  const i = Math.min(Math.floor(x), loop.length - 2);
  return mix(loop[i], loop[i + 1], x - i);
}

// ── rendering ───────────────────────────────────────────────────────────────

const RESET = '\x1b[0m';

export function sgrFor(cell) {
  const params = [cell.at, cell.fg ? `38;2;${toRgb(cell.fg).join(';')}` : ''].filter(Boolean);
  return params.length ? `\x1b[${params.join(';')}m` : '';
}

/** Cells → one row string. Spaces take the surrounding colour run; trailing blanks are trimmed. */
export function renderRow(cells) {
  let end = cells.length;
  while (end > 0 && cells[end - 1].ch === ' ') end--;
  let out = '';
  let key = '';
  for (let i = 0; i < end; i++) {
    const c = cells[i];
    if (c.ch !== ' ') {
      const k = `${c.at}|${c.fg ?? ''}`;
      if (k !== key) {
        out += (key ? RESET : '') + sgrFor(c);
        key = k;
      }
    }
    out += c.ch;
  }
  return out + (key ? RESET : '');
}

const cloneRow = (row) => row.map((c) => ({ ...c }));
const blankRow = (w) => Array.from({ length: w }, () => BLANK);
const isInk = (c) => c.ch !== ' ';

// ── effects ─────────────────────────────────────────────────────────────────

/** Column ranges of ink; used to find letter boundaries for `type`. */
function inkSegments(rows, width) {
  const segs = [];
  let start = -1;
  for (let x = 0; x <= width; x++) {
    const ink = x < width && rows.some((r) => r[x] && isInk(r[x]));
    if (ink && start < 0) start = x;
    if (!ink && start >= 0) {
      segs.push([start, x]);
      start = -1;
    }
  }
  return segs;
}

/**
 * Frames for one effect.
 * @param {object} p
 * @param {string} p.effect      one of EFFECT_NAMES
 * @param {object[][]} p.rows    cells, each row `width` wide (left padding included)
 * @param {number} p.width       terminal width
 * @param {number} p.left        first banner column; p.bannerWidth its width
 * @param {number} p.count       number of frames (>= 2); the last is the static banner
 * @param {number} p.letters     characters in the banner text (for `type`)
 * @param {object} p.palette     { colours: [hex...], noise: hex, noiseColours: [hex...], background: hex }
 */
export function effectFrames({ effect, rows, width, left, bannerWidth, count, letters, palette, direction = 'left', cycles = 1, seed }) {
  if (!EFFECT_NAMES.includes(effect)) {
    throw new EffectError(`unknown banner effect "${effect}". Valid effects: ${EFFECT_NAMES.join(', ')}`);
  }
  const rand = makeRng(seed);
  const n = Math.max(2, count);
  const last = n - 1;
  const frames = [];
  const height = rows.length;
  const inkAt = (c) => isInk(c);
  const mapRows = (fn) => rows.map((row, y) => row.map((c, x) => fn(c, x, y)));

  for (let i = 0; i < n; i++) {
    const p = i / last; // 0 … 1, the last frame is progress 1
    let grid;
    if (i === last) {
      grid = rows.map(cloneRow);
    } else if (effect === 'type') {
      const segs = inkSegments(rows, width);
      const k = Math.max(1, letters);
      const reveal = Math.floor(p * (k + 1)); // letters shown, 0 … k
      const upTo = Math.min(reveal, k);
      const edge = segs.length === k
        ? (upTo === 0 ? left : segs[upTo - 1][1])
        : left + Math.round((bannerWidth * upTo) / k);
      grid = mapRows((c, x) => (x < edge ? c : BLANK));
    } else if (effect === 'wipe') {
      const edge = left + Math.floor(p * bannerWidth);
      grid = mapRows((c, x) => (x < edge ? c : BLANK));
    } else if (effect === 'lines') {
      const shownRows = Math.floor(p * (height + 1));
      grid = mapRows((c, x, y) => (y < shownRows ? c : BLANK));
    } else if (effect === 'slide') {
      const e = 1 - (1 - p) ** 3; // ease-out cubic
      const rem = 1 - e;
      if (direction === 'left' || direction === 'right') {
        const shift = direction === 'left'
          ? -Math.round(rem * (left + bannerWidth))
          : Math.round(rem * (width - left));
        grid = rows.map((row) => {
          const out = blankRow(width);
          row.forEach((c, x) => {
            const nx = x + shift;
            if (nx >= 0 && nx < width) out[nx] = c;
          });
          return out;
        });
      } else {
        const shift = Math.round(rem * height) * (direction === 'top' ? -1 : 1);
        grid = rows.map((row, y) => {
          const src = y - shift;
          return src >= 0 && src < height ? cloneRow(rows[src]) : blankRow(width);
        });
      }
    } else if (effect === 'rainbow') {
      const phase = (i / n) * cycles;
      grid = mapRows((c, x) => (inkAt(c) ? { ...c, fg: hsl(frac((x - left) / Math.max(1, bannerWidth) * 0.9 + phase) * 360, 0.85, 0.62) } : c));
    } else if (effect === 'gradient-sweep') {
      const phase = (i / n) * cycles;
      grid = mapRows((c, x) => (inkAt(c) ? { ...c, fg: samplePalette(palette.colours, (x - left) / Math.max(1, bannerWidth) - phase) } : c));
    } else if (effect === 'pulse') {
      const k = Math.sin(Math.PI * (i / n) * cycles) ** 2; // 0 at the start, back to 0 per cycle
      const fade = 0.65 * k;
      grid = mapRows((c) => (inkAt(c) ? { ...c, fg: mix(c.fg ?? palette.foreground, palette.background, fade) } : c));
    } else if (effect === 'decrypt') {
      grid = mapRows((c, x, y) => {
        if (!inkAt(c)) return c;
        const settle = ((x - left) / Math.max(1, bannerWidth)) * 0.6 + hashUnit(seed, x, y) * 0.4;
        if (p >= settle) return c;
        const glyph = NOISE_GLYPHS[Math.floor(rand() * NOISE_GLYPHS.length)];
        return { ch: glyph, fg: palette.noise, at: '' };
      });
    } else if (effect === 'glitch') {
      grid = rows.map(cloneRow);
      if (rand() < 0.55) {
        const bands = 1 + Math.floor(rand() * 2);
        for (let b = 0; b < bands; b++) {
          const y0 = Math.floor(rand() * height);
          const h = 1 + Math.floor(rand() * Math.min(3, height));
          const dx = (rand() < 0.5 ? -1 : 1) * (1 + Math.floor(rand() * 3));
          for (let y = y0; y < Math.min(height, y0 + h); y++) {
            const shifted = blankRow(width);
            grid[y].forEach((c, x) => {
              const nx = x + dx;
              if (nx >= 0 && nx < width) shifted[nx] = c;
            });
            grid[y] = shifted;
          }
        }
        grid = grid.map((row) => row.map((c) => (inkAt(c) && rand() < 0.08
          ? { ...c, fg: palette.noiseColours[Math.floor(rand() * palette.noiseColours.length)] }
          : c)));
      }
    }
    frames.push(grid.map(renderRow));
  }
  return frames;
}

// Stable per-cell randomness for decrypt (independent of frame order).
function hashUnit(seed, x, y) {
  return makeRng(hashSeed(`${seed}:${x}:${y}`))();
}
