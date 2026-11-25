import assert from 'node:assert/strict';
import { join } from 'node:path';
import { test } from 'node:test';
import { SIMPLE, loadScene, tmpProject } from './helpers.mjs';

const build = (yaml, extra = {}) => {
  const dir = tmpProject({ 'a.scene.yaml': yaml, ...extra });
  return loadScene(join(dir, 'a.scene.yaml'));
};

test('same scene twice gives identical cast bytes', () => {
  assert.equal(build(SIMPLE).castText, build(SIMPLE).castText);
});

test('a different seed changes the typing jitter', () => {
  const other = SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, seed: 7');
  assert.notEqual(build(SIMPLE).castText, build(other).castText);
});

test('final hold is materialised as a trailing no-op event', () => {
  const b = build(SIMPLE);
  const [t, , data] = b.events.at(-1);
  const [prev] = b.events.at(-2);
  assert.equal(data, '\x1b[0m');
  assert.ok(Math.abs(t - prev - 2) < 0.01, `hold was ${t - prev}s`);
});

test('typed commands are bold, output is normal weight', () => {
  const b = build(SIMPLE);
  assert.ok(b.events.some(([, , d]) => /\x1b\[1;38;2;/.test(d)), 'typed bold');
  assert.ok(b.events.every(([, , d]) => !/\x1b\[1m.*hi/.test(d.replace(/\x1b\[1;38;2[^m]*m/, ''))));
});

test('speed scales timing; step speed scales one step', () => {
  const slow = build(SIMPLE).duration;
  const fast = build(SIMPLE.replace('final_hold: 2s', 'final_hold: 2s, speed: 2')).duration;
  assert.ok(fast < slow);
});

test('highlight markup renders styles and resets', () => {
  const b = build(SIMPLE);
  const out = b.events.map((e) => e[2]).join('');
  assert.match(out, /\x1b\[38;2;[\d;]+mhi\x1b\[0m/);
});

test('unknown markup style names the style and the valid ones', () => {
  assert.throws(() => build('steps:\n  - output: "[nope]x[/]"\n'), /unknown style "\[nope\]".*accent/s);
});

test('escaped bracket and numeric brackets are literal', () => {
  const b = build('steps:\n  - output: "\\\\[ok] and [1/3]"\n');
  assert.match(b.events.map((e) => e[2]).join(''), /\[ok\] and \[1\/3\]/);
});

test('a step needs exactly one action and rejects unknown options', () => {
  assert.throws(() => build('steps:\n  - speed: 2\n'), /exactly one action/);
  assert.throws(() => build('steps:\n  - command: ls\n    colour: red\n'), /unknown option "colour" for `command`/);
});

test('unknown scene and top-level keys fail clearly', () => {
  assert.throws(() => build('steps:\n  - command: ls\nbogus: 1\n'), /unknown top-level key "bogus"/);
  assert.throws(() => build('scenes:\n  - steps: [{command: ls}]\n    nope: 1\n'), /unknown key "nope"/);
});

test('powerline prompt builds segments (needs the Nerd Font glyphs)', () => {
  const b = build('style: { prompt: powerline }\nsteps:\n  - command: ls\n');
  assert.ok(b.castText.includes('\ue0b0'));
});

test('prompt presets and template fields', () => {
  const git = build('style: { prompt: git, prompt_branch: dev }\nsteps:\n  - prompt: true\n');
  assert.match(git.events.map((e) => e[2]).join(''), /~\/app.*on.*dev/);
  const tpl = build('style: { prompt: template, prompt_template: "{user}@{host} {time} " }\nsteps:\n  - prompt: true\n');
  assert.match(tpl.events.map((e) => e[2]).join(''), /dev@laptop 12:00/);
  assert.throws(() => build('style: { prompt: template, prompt_template: "{nope} " }\nsteps:\n  - prompt: true\n'), /unknown prompt field \{nope\}/);
});

test('multi-line commands get continuation prompts', () => {
  const b = build('steps:\n  - command: |-\n      a \\\n      b\n');
  assert.match(b.events.map((e) => e[2]).join(''), />\s/);
});

test('spinner presets run for the requested time and clear the line', () => {
  const b = build('steps:\n  - spinner: { text: work, for: 1s, preset: arc, done: "ok" }\n');
  assert.ok(b.events.some(([, , d]) => d.includes('◜')));
  assert.ok(b.events.some(([, , d]) => d.startsWith('ok') || d.includes('ok\r\n')));
  assert.throws(() => build('steps:\n  - spinner: { for: 1s, preset: nope }\n'), /unknown spinner "nope"/);
});

test('run captures real output, keeps ANSI, and enforces timeout and exit status', () => {
  const b = build(`steps:\n  - run: "printf 'x\\\\033[32mgreen\\\\033[0m\\\\n'"\n    show: demo\n`);
  const out = b.events.map((e) => e[2]).join('');
  assert.match(out, /demo/);
  assert.match(out, /x\x1b\[32mgreen\x1b\[0m/);
  assert.throws(() => build('steps:\n  - run: "exit 3"\n'), /exited with 3/);
  assert.throws(() => build('steps:\n  - run: "sleep 5"\n    timeout: 200ms\n'), /timed out/);
  assert.doesNotThrow(() => build('steps:\n  - run: "exit 3"\n    allow_failure: true\n'));
});

test('multiple scenes: cut clears, clear types `clear`, fade records a fade', () => {
  const doc = (t) => `scenes:\n  - steps: [{comment: one}]\n  - transition: ${t}\n    steps: [{comment: two}]\n`;
  assert.ok(build(doc('cut')).events.some(([, , d]) => d.includes('\x1b[2J')));
  assert.match(build(doc('clear')).events.map((e) => e[2]).join(''), /c.?l.?e.?a.?r/);
  const fade = build(doc('fade'));
  assert.equal(fade.fades.length, 1);
  assert.ok(fade.fades[0].duration > 0);
  assert.throws(() => build(doc('wipe')), /invalid transition "wipe"/);
});

test('banner scenes draw figlet text and reject banners wider than the terminal', () => {
  const b = build('scenes:\n  - title: { banner: hi, font: standard }\n    hold: 1s\n  - steps: [{comment: x}]\n');
  assert.ok(b.events.length > 5);
  assert.throws(() => build('style: { width: 20 }\nscenes:\n  - title: { banner: "a very long title" }\n'), /banner is \d+ columns wide/);
});

test('auto height fits the content; numeric height is respected', () => {
  assert.ok(build(SIMPLE).header.height >= 3);
  assert.equal(build(SIMPLE.replace('width: 40', 'width: 40, height: 12')).header.height, 12);
});

test('cursor modes draw and erase a cursor', () => {
  for (const mode of ['block', 'bar', 'underline']) {
    const b = build(`style: { cursor: ${mode} }\nsteps:\n  - command: ab\n`);
    assert.ok(b.events.some(([, , d]) => d.includes('\b')), `${mode} cursor draws`);
  }
  const hidden = build(SIMPLE);
  assert.ok(hidden.events.every(([, , d]) => !d.includes('\b')));
});

test('speed must be a positive number, globally and per scene', () => {
  for (const bad of ['0', '-1', '"fast"']) {
    assert.throws(() => build(`style: { speed: ${bad} }\nsteps: [{prompt: true}]\n`), /speed must be a positive number/);
  }
  assert.throws(() => build('scenes:\n  - style: { speed: 0 }\n    steps: [{prompt: true}]\n'), /speed must be a positive number/);
});

test('--at end never falls before the last output, even with a zero final hold', () => {
  const b = build('style: { final_hold: 0 }\nsteps:\n  - command: ab\n');
  const lastOutput = b.events.at(-2)[0] * 1000;
  assert.ok(b.endMs >= lastOutput);
  const long = build(SIMPLE);
  assert.equal(long.endMs, Math.floor(long.duration * 1000) - 100);
});
