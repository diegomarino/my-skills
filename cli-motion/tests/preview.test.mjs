import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { ROOT } from './helpers.mjs';

const CLI = join(ROOT, 'scripts', 'cli-motion.mjs');
const run = (...args) => spawnSync('node', [CLI, ...args], { encoding: 'utf8' });

test('preview PNG: a valid PNG with one cell per font × size × theme', () => {
  const dir = mkdtempSync(join(tmpdir(), 'cm-preview-'));
  const out = join(dir, 'sheet.png');
  const res = run('preview', '--fonts', 'JetBrains Mono,Fira Code', '--sizes', '12,14', '--themes', 'nord-dark', '--out', out);
  assert.equal(res.status, 0, res.stderr);
  assert.match(res.stdout, /4 cells: 2 fonts × 2 sizes × 1 themes/);
  const png = readFileSync(out);
  assert.equal(png.subarray(1, 4).toString(), 'PNG');
  assert.ok(png.length > 20000);
});

test('preview HTML: every cell labelled with its exact option values', () => {
  const dir = mkdtempSync(join(tmpdir(), 'cm-preview-'));
  const out = join(dir, 'sheet.html');
  const res = run('preview', '--fonts', 'Source Code Pro', '--sizes', '13,17', '--themes', 'nord-dark,dracula-classic', '--out', out);
  assert.equal(res.status, 0, res.stderr);
  const html = readFileSync(out, 'utf8');
  assert.equal((html.match(/<figure>/g) ?? []).length, 4);
  for (const label of ['font: Source Code Pro', 'font_size: 13', 'font_size: 17', 'theme: nord-dark', 'theme: dracula-classic', '#04']) {
    assert.ok(html.includes(label), label);
  }
  assert.equal(readFileSync(out, 'utf8'), html);
});

test('preview rejects bad input with the valid values', () => {
  assert.match(run('preview', '--fonts', 'Nope', '--out', '/tmp/x.png').stderr, /unknown font "Nope"/);
  assert.match(run('preview', '--out', '/tmp/x.gif').stderr, /\.png or \.html/);
  assert.match(run('preview', '--sizes', 'big', '--out', '/tmp/x.png').stderr, /not a size/);
});

test('fonts lists the five fonts', () => {
  const res = run('fonts');
  assert.equal(res.status, 0, res.stderr);
  for (const f of ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'IBM Plex Mono', 'Source Code Pro']) assert.ok(res.stdout.includes(f), f);
  assert.ok(JSON.parse(run('fonts', '--json').stdout).length === 5);
});

test('preview output is deterministic', () => {
  const dir = mkdtempSync(join(tmpdir(), 'cm-preview-'));
  const a = join(dir, 'a.html');
  const b = join(dir, 'b.html');
  run('preview', '--fonts', 'Fira Code', '--themes', 'nord-dark', '--out', a);
  run('preview', '--fonts', 'Fira Code', '--themes', 'nord-dark', '--out', b);
  assert.equal(readFileSync(a, 'utf8'), readFileSync(b, 'utf8'));
  writeFileSync(join(dir, 'ok'), '');
});
