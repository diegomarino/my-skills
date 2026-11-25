// Scene engine: a declarative YAML scene → an asciicast v2 stream.

import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { dep } from '../deps.mjs';
import {
  ASSETS_DIR, ConfigError, applySceneStyle, checkKeys, loadTheme, parseYaml, resolveStyle,
} from '../config/index.mjs';
import { fontInfo } from '../fonts/index.mjs';
import { Cast } from './cast.mjs';
import { RESET, StyleError, renderMarkup, sgr } from './style.mjs';

export class SceneError extends Error {
  constructor(message) {
    super(message);
    this.name = 'SceneError';
  }
}

const TOP_KEYS = ['name', 'style', 'scenes', 'steps'];
const SCENE_KEYS = ['title', 'steps', 'transition', 'hold', 'style'];
const TITLE_KEYS = ['banner', 'font', 'subtitle', 'align', 'style', 'engine', 'gradient'];
export const CFONTS_FONTS = ['block', 'simple', 'simpleBlock', 'simple3d', '3d', 'chrome', 'huge', 'shade', 'slick', 'grid', 'pallet', 'tiny', 'console'];
const COMMON = ['speed', 'hold'];
const ACTIONS = {
  type: ['text', 'enter', 'prompt', 'bold', 'style'],
  command: ['text'],
  output: ['text', 'delay', 'instant', 'style'],
  comment: ['text', 'typed'],
  pause: [],
  spinner: ['text', 'for', 'preset', 'done', 'style'],
  run: ['text', 'show', 'timeout', 'cwd', 'env', 'show_command', 'allow_failure', 'delay', 'instant'],
  clear: [],
  prompt: [],
};

/** "1.5s" | "800ms" | 2 → seconds. */
export function parseDuration(value, where = 'duration') {
  if (typeof value === 'number' && Number.isFinite(value) && value >= 0) return value;
  const m = /^\s*(\d+(?:\.\d+)?)\s*(ms|s|m)?\s*$/.exec(String(value));
  if (!m) throw new SceneError(`${where}: invalid duration ${JSON.stringify(value)} (use 1.5s, 800ms or seconds)`);
  const n = Number(m[1]);
  return m[2] === 'ms' ? n / 1000 : m[2] === 'm' ? n * 60 : n;
}

const readJson = (file) => JSON.parse(readFileSync(join(ASSETS_DIR, file), 'utf8'));

/** Normalise one step into { action, text, opts }. */
function normaliseStep(step, where) {
  if (step == null || typeof step !== 'object' || Array.isArray(step)) {
    throw new SceneError(`${where}: a step is a map like \`- command: "ls"\``);
  }
  const actions = Object.keys(step).filter((k) => k in ACTIONS);
  if (actions.length !== 1) {
    throw new SceneError(
      `${where}: a step needs exactly one action (${Object.keys(ACTIONS).join(', ')}); found ${actions.length ? actions.join(' + ') : `keys ${Object.keys(step).join(', ') || '(none)'}`}`,
    );
  }
  const action = actions[0];
  const { [action]: value, ...siblings } = step;
  let opts = { ...siblings };
  let text;
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    opts = { ...value, ...siblings };
    text = opts.text;
    if (action === 'pause') text = opts.for ?? opts.text;
  } else text = value;
  const allowed = [...ACTIONS[action], ...COMMON];
  for (const key of Object.keys(opts)) {
    if (!allowed.includes(key)) {
      throw new SceneError(`${where}: unknown option "${key}" for \`${action}\`. Valid options: ${allowed.join(', ')}`);
    }
  }
  return { action, text, opts };
}

export function parseSceneDocument(text, file = 'scene') {
  const doc = parseYaml(text, file);
  if (doc === null || typeof doc !== 'object' || Array.isArray(doc)) {
    throw new SceneError(`${file}: a scene file is a YAML map with \`scenes:\` (or \`steps:\`)`);
  }
  for (const key of Object.keys(doc)) {
    if (!TOP_KEYS.includes(key)) {
      throw new SceneError(`${file}: unknown top-level key "${key}". Valid keys: ${TOP_KEYS.join(', ')}`);
    }
  }
  if (doc.scenes && doc.steps) throw new SceneError(`${file}: use either \`scenes:\` or \`steps:\`, not both`);
  const scenes = doc.scenes ?? (doc.steps ? [{ steps: doc.steps }] : null);
  if (!Array.isArray(scenes) || scenes.length === 0) {
    throw new SceneError(`${file}: no scenes. Add \`scenes:\` (a list) or \`steps:\``);
  }
  scenes.forEach((scene, i) => {
    if (scene == null || typeof scene !== 'object' || Array.isArray(scene)) {
      throw new SceneError(`${file}: scenes[${i}] must be a map with \`steps:\` and/or \`title:\``);
    }
    for (const key of Object.keys(scene)) {
      if (!SCENE_KEYS.includes(key)) {
        throw new SceneError(`${file}: scenes[${i}]: unknown key "${key}". Valid keys: ${SCENE_KEYS.join(', ')}`);
      }
    }
    if (scene.steps != null && !Array.isArray(scene.steps)) {
      throw new SceneError(`${file}: scenes[${i}].steps must be a list`);
    }
    if (!scene.title && !(scene.steps?.length)) {
      throw new SceneError(`${file}: scenes[${i}] is empty: give it \`steps:\` or a \`title:\``);
    }
  });
  return { name: doc.name, style: doc.style, scenes };
}

class Director {
  constructor({ style, theme, cast, baseDir, file }) {
    this.base = style;
    this.theme = theme;
    this.cast = cast;
    this.baseDir = baseDir;
    this.file = file;
    this.style = style;
    this.speed = 1;
  }

  get s() {
    return this.style;
  }

  /** Scale a duration by global and per-step speed. */
  d(seconds) {
    return seconds / (Number(this.style.speed) * this.speed);
  }

  markup(text, base = '') {
    try {
      return renderMarkup(text, { styles: this.style.styles, theme: this.theme, base });
    } catch (err) {
      if (err instanceof StyleError) throw new SceneError(`${this.where}: ${err.message}`);
      throw err;
    }
  }

  sgr(spec) {
    try {
      return sgr(spec, this.theme);
    } catch (err) {
      if (err instanceof StyleError) throw new SceneError(`${this.where}: ${err.message}`);
      throw err;
    }
  }

  promptText() {
    const s = this.style;
    const presets = ['simple', 'dollar', 'path', 'git', 'template', 'powerline'];
    if (!presets.includes(s.prompt)) {
      throw new SceneError(`${this.where}: unknown prompt "${s.prompt}". Valid prompts: ${presets.join(', ')}`);
    }
    const preset = readJson(`prompts/${s.prompt}.json`);
    const fields = {
      cwd: s.prompt_cwd, branch: s.prompt_branch, user: s.prompt_user, host: s.prompt_host,
      time: s.prompt_time, status: s.prompt_status,
    };
    const fill = (template) => template.replace(/\{(\w+)\}/g, (all, name) => {
      if (!(name in fields)) {
        throw new SceneError(`${this.where}: unknown prompt field {${name}}. Valid fields: ${Object.keys(fields).join(', ')}`);
      }
      return String(fields[name]);
    });
    if (preset.requires === 'nerd-font') {
      if (s.font_nerd === false) {
        throw new SceneError(`${this.where}: prompt: powerline needs the Nerd Font variant; remove \`font_nerd: false\` or pick prompt: git.`);
      }
      return this.powerline(preset, fill);
    }
    const filled = fill(preset.template ?? s.prompt_template);
    return this.markup(filled);
  }

  /** oh-my-posh-like segments: coloured blocks joined by powerline arrows (U+E0B0). */
  powerline(preset, fill) {
    const segs = preset.segments;
    let out = '';
    segs.forEach((seg, i) => {
      out += `${this.sgr(`fg:${seg.fg} bg:${seg.bg}`)}${fill(seg.text)}`;
      const next = segs[i + 1];
      out += next
        ? `${this.sgr(`fg:${seg.bg} bg:${next.bg}`)}${preset.separator}`
        : `${RESET}${this.sgr(`fg:${seg.bg}`)}${preset.separator}${RESET} `;
    });
    return out;
  }

  showPrompt() {
    this.cast.out(this.promptText(), this.d(this.style.prompt_delay));
    this.cast.setCursorActive(true);
  }

  typeChars(text, spec) {
    const { cast } = this;
    const open = this.sgr(spec);
    const perChar = cast.cursorEnabled; // the cursor redraw resets attributes, so re-assert them
    if (!perChar && open) cast.out(open);
    for (const ch of text) {
      const dt = this.d(Number(this.style.typing_delay) + cast.rand() * Number(this.style.typing_jitter));
      cast.out(perChar ? open + ch : ch, dt);
    }
    if (open) cast.out(RESET);
  }

  enter() {
    this.cast.setCursorActive(false);
    this.cast.out('\r\n', this.d(this.style.enter_delay));
  }

  /** Prompt + typed command (+ continuation prompts for extra lines) + Enter. */
  typeCommand(text) {
    this.showPrompt();
    const lines = String(text).split('\n');
    lines.forEach((line, i) => {
      if (i > 0) {
        this.cast.setCursorActive(false);
        this.cast.out('\r\n', this.d(this.style.enter_delay));
        this.cast.out(this.markup('[continuation]> [/]'));
        this.cast.setCursorActive(true);
      }
      this.typeChars(line, this.style.typed_style);
    });
    this.enter();
  }

  /** Emit a multi-line block; each line is one reveal step. */
  block(text, { delay, instant = false, base = '' } = {}) {
    const body = this.markup(String(text).replace(/\r?\n$/, '').replace(/\r\n/g, '\n'), base);
    const lines = body.split('\n');
    const dt = this.d(delay ?? Number(this.style.line_delay));
    this.cast.setCursorActive(false);
    if (instant) this.cast.out(lines.join('\r\n') + '\r\n', dt);
    else lines.forEach((line) => this.cast.out(`${line}\r\n`, dt));
  }

  clearScreen() {
    this.cast.setCursorActive(false);
    this.cast.out('\x1b[2J\x1b[H');
  }

  banner(title) {
    const figlet = dep('figlet');
    const spec = typeof title === 'string' ? { banner: title } : title;
    checkKeysScene(spec, TITLE_KEYS, `${this.where} title`);
    if (!spec.banner) throw new SceneError(`${this.where}: title needs a \`banner:\` text`);
    const gradient = spec.gradient ?? this.style.banner_gradient;
    const engine = spec.engine ?? (gradient ? 'cfonts' : 'figlet');
    if (!['figlet', 'cfonts'].includes(engine)) {
      throw new SceneError(`${this.where}: unknown banner engine "${engine}". Valid engines: figlet, cfonts`);
    }
    let lines;
    if (engine === 'cfonts') lines = this.cfontsLines(spec, gradient);
    else {
      const font = spec.font ?? this.style.banner_font;
      let art;
      try {
        art = figlet.textSync(String(spec.banner), { font, width: 500, whitespaceBreak: false });
      } catch (err) {
        throw new SceneError(`${this.where}: figlet font "${font}" failed: ${String(err.message ?? err).split('\n')[0]}. List fonts with: node -e "console.log(require('figlet').fontsSync().join(' '))"`);
      }
      lines = art.replace(/\s+$/, '').split('\n');
    }
    const visible = (l) => l.replace(/\x1b\[[0-9;]*m/g, '').length;
    const widest = Math.max(...lines.map(visible));
    if (widest > this.cast.width) {
      throw new SceneError(`${this.where}: banner is ${widest} columns wide but the terminal is ${this.cast.width}. Use a shorter text, a smaller banner font (e.g. small, mini; cfonts: tiny, simple) or a wider \`width\`.`);
    }
    const align = spec.align ?? 'center';
    const pad = (w) => (align === 'center' ? ' '.repeat(Math.floor((this.cast.width - w) / 2)) : '');
    const styleSpec = this.style.styles[spec.style] ?? spec.style ?? this.style.styles[this.style.banner_style] ?? this.style.banner_style;
    const open = engine === 'cfonts' ? '' : this.sgr(styleSpec);
    this.cast.setCursorActive(false);
    for (const line of lines) this.cast.out(`${pad(widest)}${open}${line}${RESET}\r\n`, this.d(this.style.line_delay * 1.6));
    if (spec.subtitle) {
      this.cast.out('\r\n', this.d(0.1));
      const sub = String(spec.subtitle);
      this.cast.out(`${pad(sub.length)}${this.markup(sub, this.style.comment_style)}\r\n`, this.d(0.3));
    }
  }

  /** cfonts block letters with a colour gradient; returns lines that carry their own SGR. */
  cfontsLines(spec, gradient) {
    const font = spec.font ?? 'block';
    if (!CFONTS_FONTS.includes(font)) {
      throw new SceneError(`${this.where}: unknown cfonts font "${font}". Valid cfonts fonts: ${CFONTS_FONTS.join(', ')}`);
    }
    const colours = (Array.isArray(gradient) ? gradient : [gradient])
      .map((c) => (c == null ? null : this.hex(String(c))));
    if (colours.length < 2) {
      throw new SceneError(`${this.where}: a gradient needs at least two colours, e.g. gradient: ["#ff6ac1", "#57c7ff"] or [accent, accent2]`);
    }
    const { render } = dep('cfonts');
    const out = render(String(spec.banner), {
      font, gradient: colours, space: false, env: 'node', maxLength: String(this.cast.width), letterSpacing: 1,
    });
    if (!out) throw new SceneError(`${this.where}: cfonts could not render the banner "${spec.banner}"`);
    const lines = out.string.replace(/\r/g, '').split('\n');
    const blank = (l) => !l.replace(/\x1b\[[0-9;]*m/g, '').trim();
    while (lines.length && blank(lines[0])) lines.shift();
    while (lines.length && blank(lines.at(-1))) lines.pop();
    return lines.map((l) => l.replace(/\s+$/, ''));
  }

  /** Colour spec (#rrggbb | theme colour | ansi name) → #rrggbb. */
  hex(spec) {
    if (spec.startsWith('#')) return spec;
    const t = this.theme;
    const base = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'];
    const bright = spec.startsWith('bright-');
    const idx = base.indexOf(bright ? spec.slice(7) : spec);
    if (idx >= 0) return t.terminal.ansi[idx + (bright ? 8 : 0)];
    if (['foreground', 'background', 'cursor'].includes(spec)) return t.terminal[spec];
    if (t.accents?.[spec]) return t.accents[spec];
    throw new SceneError(`${this.where}: unknown colour "${spec}" in gradient. Use #rrggbb, a theme colour (accent, accent2, success, warning, error, info) or an ANSI name`);
  }

  spinner(text, opts) {
    const presets = readJson('spinners.json');
    const name = opts.preset ?? this.style.spinner;
    const preset = presets[name];
    if (!preset) throw new SceneError(`${this.where}: unknown spinner "${name}". Valid spinners: ${Object.keys(presets).join(', ')}`);
    const total = this.d(parseDuration(opts.for ?? 1.5, `${this.where} for`));
    const interval = this.d(preset.interval);
    const frames = Math.max(1, Math.round(total / interval));
    const styleSpec = opts.style ?? this.style.spinner_style;
    const open = this.sgr(this.style.styles[styleSpec] ?? styleSpec);
    const label = text ? ` ${this.markup(String(text))}` : '';
    this.cast.setCursorActive(false);
    for (let i = 0; i < frames; i++) {
      let glyph;
      if (preset.kind === 'progress') {
        const p = (i + 1) / frames;
        const filled = Math.round(p * preset.width);
        glyph = `[${preset.fill.repeat(filled)}${preset.empty.repeat(preset.width - filled)}] ${String(Math.round(p * 100)).padStart(3)}%`;
      } else glyph = preset.frames[i % preset.frames.length];
      this.cast.out(`\r\x1b[2K${open}${glyph}${RESET}${label}`, total / frames);
    }
    this.cast.out('\r\x1b[2K');
    if (opts.done != null) this.cast.out(`${this.markup(String(opts.done))}\r\n`, this.d(0.05));
  }

  run(command, opts) {
    if (!command) throw new SceneError(`${this.where}: \`run\` needs a command`);
    const timeout = parseDuration(opts.timeout ?? 30, `${this.where} timeout`) * 1000;
    const cwd = resolve(this.baseDir, opts.cwd ?? '.');
    const res = spawnSync('sh', ['-c', command], {
      cwd,
      timeout,
      encoding: 'utf8',
      maxBuffer: 16 * 1024 * 1024,
      env: {
        ...process.env,
        ...(opts.env ?? {}),
        FORCE_COLOR: '1', CLICOLOR_FORCE: '1', TERM: 'xterm-256color', COLUMNS: String(this.cast.width),
      },
    });
    if (res.error?.code === 'ETIMEDOUT') {
      throw new SceneError(`${this.where}: \`run: ${command}\` timed out after ${timeout / 1000}s. Raise it with \`timeout: 60s\`.`);
    }
    if (res.error) throw new SceneError(`${this.where}: could not run \`${command}\`: ${res.error.message}`);
    if (res.status !== 0 && !opts.allow_failure) {
      const tail = `${res.stdout ?? ''}${res.stderr ?? ''}`.trim().split('\n').slice(-5).join('\n');
      throw new SceneError(`${this.where}: \`run: ${command}\` exited with ${res.status}. Add \`allow_failure: true\` to show failing output.\n${tail}`);
    }
    if (opts.show_command !== false) this.typeCommand(opts.show ?? command);
    const captured = `${res.stdout ?? ''}${res.stderr ?? ''}`.replace(/\r?\n/g, '\n').replace(/\n$/, '');
    if (captured) {
      this.cast.setCursorActive(false);
      const lines = captured.split('\n');
      const dt = this.d(opts.delay != null ? parseDuration(opts.delay) : Number(this.style.line_delay));
      if (opts.instant) this.cast.out(lines.join('\r\n') + '\r\n', dt);
      else lines.forEach((l) => this.cast.out(`${l}\r\n`, dt));
    }
  }

  step(step, where) {
    this.where = where;
    const { action, text, opts } = normaliseStep(step, where);
    this.speed = opts.speed == null ? 1 : Number(opts.speed);
    if (!(this.speed > 0)) throw new SceneError(`${where}: speed must be a positive number`);
    const need = () => {
      if (text == null || text === '') throw new SceneError(`${where}: \`${action}\` needs text`);
      return String(text);
    };
    switch (action) {
      case 'command':
        this.typeCommand(need());
        break;
      case 'type': {
        if (opts.prompt) this.showPrompt();
        else this.cast.setCursorActive(true);
        const spec = opts.style ? this.style.styles[opts.style] ?? opts.style : opts.bold === false ? this.style.typed_style.replace(/\bbold\b/, '').trim() : this.style.typed_style;
        this.typeChars(need(), spec);
        if (opts.enter) this.enter();
        break;
      }
      case 'output': {
        const base = opts.style ? this.style.styles[opts.style] ?? opts.style : this.style.output_style;
        this.block(need(), { delay: opts.delay != null ? parseDuration(opts.delay) : undefined, instant: opts.instant, base });
        break;
      }
      case 'comment': {
        const line = this.markup(need(), this.style.comment_style);
        this.cast.setCursorActive(false);
        if (opts.typed) {
          this.showPrompt();
          this.typeChars(String(text), this.style.comment_style);
          this.enter();
        } else this.cast.out(`${line}\r\n`, this.d(0.4));
        break;
      }
      case 'pause':
        this.cast.wait(this.d(parseDuration(text, `${where} pause`)));
        break;
      case 'spinner':
        this.spinner(text, opts);
        break;
      case 'run':
        this.run(String(text ?? ''), opts);
        break;
      case 'clear':
        this.clearScreen();
        break;
      case 'prompt':
        this.showPrompt();
        break;
      default:
    }
    if (opts.hold != null) this.cast.wait(this.d(parseDuration(opts.hold, `${where} hold`)));
    this.speed = 1;
  }
}

function checkKeysScene(obj, allowed, where) {
  for (const key of Object.keys(obj ?? {})) {
    if (!allowed.includes(key)) throw new SceneError(`${where}: unknown key "${key}". Valid keys: ${allowed.join(', ')}`);
  }
}

/**
 * Build the cast for a parsed scene document.
 * Returns { castText, header, events, duration, fades, endMs, theme, style, projectConfig }.
 */
export function buildCast(doc, { style, theme, baseDir = process.cwd(), file = 'scene' }) {
  const cast = new Cast({
    width: Number(style.width),
    seed: Number(style.seed),
    title: doc.name ?? 'cli-motion',
    theme,
    cursor: style.cursor,
    blink: style.cursor_blink,
  });
  const director = new Director({ style, theme, cast, baseDir, file });
  const last = doc.scenes.length - 1;

  doc.scenes.forEach((scene, i) => {
    const where = `${file}: scenes[${i}]`;
    let sceneStyle;
    try {
      sceneStyle = applySceneStyle(style, scene.style, `${where}.style`);
    } catch (err) {
      if (err instanceof ConfigError) throw new SceneError(err.message);
      throw err;
    }
    director.style = sceneStyle;
    director.where = where;
    cast.setCursor({ mode: sceneStyle.cursor, blink: sceneStyle.cursor_blink });

    if (i > 0) {
      const transition = scene.transition ?? sceneStyle.transition;
      if (!['cut', 'clear', 'fade'].includes(transition)) {
        throw new SceneError(`${where}: invalid transition "${transition}". Valid transitions: cut, clear, fade`);
      }
      if (transition === 'clear') {
        director.typeCommand('clear');
        cast.wait(director.d(0.25));
        director.clearScreen();
      } else if (transition === 'fade') {
        const dur = director.d(parseDuration(sceneStyle.transition_duration, 'transition_duration'));
        director.clearScreen();
        cast.fades.push({ at: cast.t, duration: dur });
        cast.wait(dur);
      } else director.clearScreen();
    }

    if (scene.title) director.banner(scene.title);
    (scene.steps ?? []).forEach((step, j) => director.step(step, `${where}.steps[${j}]`));
    cast.setCursorActive(false);

    if (i < last) {
      const hold = scene.hold ?? (scene.steps?.length ? sceneStyle.scene_hold : 2);
      cast.wait(director.d(parseDuration(hold, `${where} hold`)));
    } else if (scene.hold != null) cast.wait(director.d(parseDuration(scene.hold, `${where} hold`)));
  });

  // Final hold: svg-term derives its loop length from the LAST event, so a bare
  // wait would be lost. Emit a no-op event after the hold to materialise it.
  cast.out(RESET, parseDuration(style.final_hold, 'final_hold'));

  const height = style.height === 'auto' ? cast.autoHeight() : Number(style.height);
  if (!(height > 0)) throw new SceneError(`${file}: height must be a number of rows or "auto"`);
  return {
    castText: cast.serialize(height),
    header: cast.header(height),
    events: cast.events,
    duration: cast.duration,
    fades: cast.fades,
    endMs: Math.max(0, Math.floor(cast.duration * 1000) - 100),
    rows: height,
    theme,
    style,
  };
}

/** Load a scene file and resolve its configuration layers. */
export function loadScene(sceneFile, { projectConfigPath } = {}) {
  const file = resolve(sceneFile);
  const baseDir = dirname(file);
  const text = readFileSync(file, 'utf8');
  const doc = parseSceneDocument(text, sceneFile);
  const { style, projectConfig } = resolveStyle({
    sceneDir: baseDir, sceneStyle: doc.style, projectConfigPath, sceneFile,
  });
  const theme = loadTheme(style.theme);
  try {
    fontInfo(style.font);
  } catch (err) {
    throw new SceneError(`${sceneFile}: ${err.message}`);
  }
  const result = buildCast(doc, { style, theme, baseDir, file: sceneFile });
  return { ...result, projectConfig, file, baseDir, name: doc.name };
}
