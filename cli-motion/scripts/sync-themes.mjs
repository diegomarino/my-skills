#!/usr/bin/env node
// Regenerate assets/themes/*.json from a tui-design checkout.
//
//   node scripts/sync-themes.mjs [--from <tui-design dir>] [--check]
//
// Copies each theme's terminal block (background, foreground, cursor, 16 ANSI
// colours) with its license and sources, and resolves the accent tokens cli-motion
// uses for highlights and the progress bar. --check exits 1 if assets are stale.

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, '..', 'assets', 'themes');

function parseArgs(argv) {
  const args = { from: join(HERE, '..', '..', 'tui-design'), check: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--from') args.from = resolve(argv[++i]);
    else if (argv[i] === '--check') args.check = true;
    else throw new Error(`unknown argument ${argv[i]}\nusage: sync-themes.mjs [--from <tui-design dir>] [--check]`);
  }
  return args;
}

function themesDir(from) {
  for (const candidate of [join(from, 'references', 'themes'), join(from, 'themes'), from]) {
    if (existsSync(join(candidate, '_tokens.json'))) return candidate;
  }
  throw new Error(`no tui-design themes found under ${from} (expected references/themes/_tokens.json)`);
}

const resolveColor = (theme, ref) =>
  /^#/.test(ref ?? '') ? ref : theme.palette?.[ref] ?? null;

export function convert(theme) {
  const t = theme.tokens ?? {};
  const accents = {
    accent: resolveColor(theme, t['accent.primary']),
    accent2: resolveColor(theme, t['accent.secondary']),
    success: resolveColor(theme, t['status.success']),
    warning: resolveColor(theme, t['status.warning']),
    error: resolveColor(theme, t['status.error']),
    info: resolveColor(theme, t['status.info']),
  };
  return {
    id: theme.id,
    name: theme.name,
    appearance: theme.appearance,
    license: theme.license,
    sources: theme.sources,
    terminal: theme.terminal,
    accents,
  };
}

const args = parseArgs(process.argv.slice(2));
const dir = themesDir(args.from);
const files = readdirSync(dir).filter((f) => f.endsWith('.json') && !f.startsWith('_')).sort();
mkdirSync(OUT, { recursive: true });
let stale = 0;
for (const file of files) {
  const theme = convert(JSON.parse(readFileSync(join(dir, file), 'utf8')));
  const text = `${JSON.stringify(theme, null, 2)}\n`;
  const target = join(OUT, file);
  if (args.check) {
    if (!existsSync(target) || readFileSync(target, 'utf8') !== text) {
      stale++;
      console.error(`stale: ${file}`);
    }
  } else {
    writeFileSync(target, text);
  }
}
console.log(args.check ? `${files.length - stale}/${files.length} themes up to date` : `wrote ${files.length} themes to ${OUT}`);
if (stale) process.exit(1);
