// Text styles: SGR escape generation and the [name]…[/] highlight markup.

export class StyleError extends Error {
  constructor(message) {
    super(message);
    this.name = 'StyleError';
  }
}

const BASIC = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'];
const ATTRS = { bold: '1', dim: '2', italic: '3', underline: '4' };
const THEME_COLOURS = ['foreground', 'background', 'cursor', 'accent', 'accent2', 'success', 'warning', 'error', 'info'];

export const ESC = '\x1b[';
export const RESET = `${ESC}0m`;

export function hexToRgb(hex) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex ?? '');
  if (!m) throw new StyleError(`invalid colour "${hex}" (expected #rrggbb)`);
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** SGR parameter for a colour spec; `kind` is 'fg' or 'bg'. */
export function colourParam(spec, kind, theme) {
  const base = kind === 'fg' ? 30 : 40;
  const bright = spec.startsWith('bright-');
  const name = bright ? spec.slice(7) : spec;
  const idx = BASIC.indexOf(name);
  if (idx >= 0) return String(base + idx + (bright ? 60 : 0));
  if (spec.startsWith('#')) {
    const [r, g, b] = hexToRgb(spec);
    return `${kind === 'fg' ? 38 : 48};2;${r};${g};${b}`;
  }
  if (THEME_COLOURS.includes(spec)) {
    const t = theme ?? {};
    const hex = spec === 'foreground' || spec === 'background' || spec === 'cursor'
      ? t.terminal?.[spec]
      : t.accents?.[spec];
    if (!hex) throw new StyleError(`theme "${t.id}" has no colour "${spec}"`);
    const [r, g, b] = hexToRgb(hex);
    return `${kind === 'fg' ? 38 : 48};2;${r};${g};${b}`;
  }
  throw new StyleError(
    `unknown colour "${spec}". Use ${BASIC.join(' ')} (optionally bright-…), #rrggbb, or ${THEME_COLOURS.join(' ')}`,
  );
}

/** Parse "bold fg:accent bg:#222222" into SGR parameters (array of strings). */
export function styleParams(spec, theme) {
  const params = [];
  for (const token of String(spec ?? '').split(/\s+/).filter(Boolean)) {
    if (ATTRS[token]) params.push(ATTRS[token]);
    else if (token.startsWith('fg:')) params.push(colourParam(token.slice(3), 'fg', theme));
    else if (token.startsWith('bg:')) params.push(colourParam(token.slice(3), 'bg', theme));
    else {
      throw new StyleError(
        `unknown style token "${token}" in "${spec}". Use bold dim italic underline fg:<colour> bg:<colour>`,
      );
    }
  }
  return params;
}

export function sgr(spec, theme) {
  const params = styleParams(spec, theme);
  return params.length ? `${ESC}${params.join(';')}m` : '';
}

const isInlineStyle = (text) => {
  const tokens = text.split(/\s+/).filter(Boolean);
  return tokens.length > 0 && tokens.every((t) => ATTRS[t] || /^(fg|bg):/.test(t));
};

/**
 * Turn `[name]text[/]` markup into SGR escapes.
 * `name` is a named style or inline tokens (`[bold fg:red]`). `\[` is a literal bracket.
 * After each `[/]` the base style and the still-open styles are re-applied.
 */
export function renderMarkup(text, { styles, theme, base = '' }) {
  const stack = [];
  const baseSgr = sgr(base, theme);
  const restore = () => RESET + baseSgr + stack.join('');
  let out = baseSgr;
  const re = /\\\[|\[([^\][\n]*)\]/g;
  let last = 0;
  let m;
  while ((m = re.exec(text))) {
    out += text.slice(last, m.index);
    last = re.lastIndex;
    if (m[0] === '\\[') {
      out += '[';
      continue;
    }
    const tag = m[1];
    if (tag === '/') {
      if (!stack.length) throw new StyleError(`"[/]" with no open style in: ${JSON.stringify(text.slice(0, 60))}`);
      stack.pop();
      out += restore();
    } else if (Object.hasOwn(styles, tag)) {
      const s = sgr(styles[tag], theme);
      stack.push(s);
      out += s;
    } else if (isInlineStyle(tag)) {
      const s = sgr(tag, theme);
      stack.push(s);
      out += s;
    } else if (/^[A-Za-z][\w-]*$/.test(tag)) {
      throw new StyleError(
        `unknown style "[${tag}]". Defined styles: ${Object.keys(styles).sort().join(', ')}. Write a literal bracket as \\[${tag}]`,
      );
    } else {
      out += m[0]; // e.g. [1/3] is ordinary text
    }
  }
  out += text.slice(last);
  if (stack.length) out += RESET;
  else if (baseSgr) out += RESET;
  return out;
}
