// Asciicast v2 builder: virtual clock, seeded jitter, cursor drawing, screen-size tracking.

import { RESET, colourParam, hexToRgb } from './style.mjs';

const BLINK_PERIOD = 0.53;

const strip = (s) => s.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '');

export class Cast {
  constructor({ width, seed, title, theme, cursor = 'hidden', blink = false }) {
    this.width = width;
    this.title = title;
    this.t = 0;
    this.events = [];
    this.fades = [];
    this.seed = seed;
    this.row = 0;
    this.col = 0;
    this.maxRow = 0;
    this.cursorMode = cursor;
    this.blink = blink;
    this.cursorActive = false;
    this.cursorShown = false;
    const rgb = hexToRgb(theme.terminal.cursor ?? theme.terminal.foreground);
    this.cursorColour = `38;2;${rgb[0]};${rgb[1]};${rgb[2]}`;
    this.cursorBg = colourParam(theme.terminal.cursor ?? theme.terminal.foreground, 'bg', theme);
  }

  /** Seeded LCG (same constants as gh-delta): identical scene + seed → identical timing. */
  rand() {
    this.seed = (this.seed * 1103515245 + 12345) & 0x7fffffff;
    return this.seed / 0x7fffffff;
  }

  setCursor({ mode, blink }) {
    this.cursorMode = mode;
    this.blink = blink;
  }

  get cursorEnabled() {
    return this.cursorMode !== 'hidden';
  }

  #drawSeq() {
    const glyph = { block: ' ', bar: '▏', underline: '▁' }[this.cursorMode];
    const paint = this.cursorMode === 'block' ? `\x1b[${this.cursorBg}m` : `\x1b[${this.cursorColour}m`;
    return `${paint}${glyph}${RESET}\b`;
  }

  #track(data) {
    const text = strip(data);
    if (/\x1b\[2J/.test(data)) {
      this.row = 0;
      this.col = 0;
    }
    for (const ch of text) {
      if (ch === '\r') this.col = 0;
      else if (ch === '\n') {
        this.row++;
        this.col = 0;
      } else if (ch === '\b') this.col = Math.max(0, this.col - 1);
      else if (ch < ' ') continue;
      else {
        if (this.col >= this.width) {
          this.row++;
          this.col = 0;
        }
        this.col++;
      }
      this.maxRow = Math.max(this.maxRow, this.row);
    }
  }

  /** Advance the clock by dt, then write data (`track: false` for in-place redraws that do not move the row count). The cursor (if any) follows the text. */
  out(data, dt = 0, { track = true } = {}) {
    this.t += dt;
    let s = '';
    if (this.cursorShown) s += `${RESET} \b`;
    s += data;
    if (track) this.#track(data);
    this.cursorShown = false;
    if (this.cursorActive && this.cursorEnabled) {
      s += this.#drawSeq();
      this.cursorShown = true;
    }
    this.events.push([Number(this.t.toFixed(3)), 'o', s]);
    return this;
  }

  /** Let time pass; a blinking cursor toggles while idle. */
  wait(dt) {
    if (!(this.blink && this.cursorActive && this.cursorEnabled)) {
      this.t += dt;
      return this;
    }
    let rem = dt;
    while (rem > 1e-9) {
      const step = Math.min(BLINK_PERIOD, rem);
      this.t += step;
      rem -= step;
      if (rem > 1e-9 || step === BLINK_PERIOD) {
        this.events.push([Number(this.t.toFixed(3)), 'o', this.cursorShown ? `${RESET} \b` : this.#drawSeq()]);
        this.cursorShown = !this.cursorShown;
      }
    }
    return this;
  }

  /** Show or hide the idle cursor (hidden while output streams). */
  setCursorActive(active) {
    this.cursorActive = active;
    if (!active && this.cursorShown) {
      this.events.push([Number(this.t.toFixed(3)), 'o', `${RESET} \b`]);
      this.cursorShown = false;
    }
  }

  get duration() {
    return this.events.length ? this.events[this.events.length - 1][0] : 0;
  }

  header(height) {
    return {
      version: 2,
      width: this.width,
      height,
      title: this.title,
      env: { SHELL: '/bin/zsh', TERM: 'xterm-256color' },
    };
  }

  /** Rows needed so nothing scrolls off. */
  autoHeight() {
    return Math.max(this.maxRow + 1, 3);
  }

  serialize(height) {
    return [this.header(height), ...this.events].map((row) => JSON.stringify(row)).join('\n') + '\n';
  }
}
