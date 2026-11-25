#!/usr/bin/env node
// cli-motion: terminal animations from a declarative YAML scene.
//
//   cli-motion render <scene.yaml> [-o out.svg] [--cast [file]]
//   cli-motion still  <scene.yaml> [--at <ms|end>] [-o out.svg]
//   cli-motion themes [--json]
//   cli-motion doctor [--install]

import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { cacheState, ensureDeps } from './lib/deps.mjs';

const USAGE = `cli-motion: terminal animations from a YAML scene

Usage
  cli-motion render <scene.yaml> [-o out.svg] [--cast [file]]   animated SVG
  cli-motion still  <scene.yaml> [--at <ms|end>] [-o out.svg]   one frame as SVG
  cli-motion themes [--json]                                    list the 25 themes
  cli-motion doctor [--install]                                 check Node, ffmpeg, cache
  cli-motion fonts [--json]                                     list fonts, sizes, Nerd Font cache
  cli-motion preview [--fonts a,b|all] [--sizes 12,14] [--themes a,b|all] [--out sheet.png|sheet.html]
                                                                contact sheet: font × size × theme
  cli-motion export                                             arrives in a later release

Options
  -o, --out <file>   output path (default: next to the scene)
  --cast [file]      also write the asciicast v2 (default: next to the output)
  --at <ms|end>      still: millisecond of the frame, or "end" (default)
  -h, --help
`;

function parseArgs(argv) {
  const args = { _: [], flags: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) throw new UsageError(`${a} needs a value`);
      return argv[++i];
    };
    if (a === '-o' || a === '--out') args.flags.out = next();
    else if (a === '--at') args.flags.at = next();
    else if (a === '--cast') {
      args.flags.cast = argv[i + 1] && !argv[i + 1].startsWith('-') && /\.cast$/.test(argv[i + 1]) ? argv[++i] : true;
    } else if (a === '--fonts') args.flags.fonts = next();
    else if (a === '--sizes') args.flags.sizes = next();
    else if (a === '--themes') args.flags.themes = next();
    else if (a === '--json') args.flags.json = true;
    else if (a === '--install') args.flags.install = true;
    else if (a === '-h' || a === '--help') args.flags.help = true;
    else if (a.startsWith('-')) throw new UsageError(`unknown option ${a}\n\n${USAGE}`);
    else args._.push(a);
  }
  return args;
}

class UsageError extends Error {}

const sceneBase = (file) => basename(file).replace(/\.scene\.ya?ml$|\.ya?ml$/i, '');

async function loadBuild(sceneFile) {
  ensureDeps({ log: (m) => console.error(`cli-motion: ${m}`) });
  const { loadScene } = await import('./lib/scene/index.mjs');
  return loadScene(sceneFile);
}

function writeOut(path, data) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, data);
}

async function cmdRender(args, still) {
  const [sceneFile] = args._;
  if (!sceneFile) throw new UsageError(`${still ? 'still' : 'render'} needs a scene file\n\n${USAGE}`);
  const build = await loadBuild(sceneFile);
  const svgLib = await import('./lib/svg/index.mjs');
  const dir = dirname(build.file);
  const out = resolve(args.flags.out ?? join(dir, `${sceneBase(sceneFile)}${still ? '.still' : ''}.svg`));
  const svg = still ? await svgLib.renderStill(build, args.flags.at ?? 'end') : await svgLib.renderAnimated(build);
  writeOut(out, svg);
  if (args.flags.cast) {
    const castPath = typeof args.flags.cast === 'string' ? resolve(args.flags.cast) : out.replace(/\.svg$/, '') + '.cast';
    writeOut(castPath, build.castText);
    console.error(`cli-motion: wrote ${castPath}`);
  }
  const kb = (Buffer.byteLength(svg) / 1024).toFixed(1);
  console.log(`${out} (${kb} KB, ${build.duration.toFixed(1)}s, ${build.header.width}x${build.header.height} cells, ${build.style.theme})`);
}

async function cmdThemes(args) {
  const { listThemes } = await import('./lib/config/index.mjs');
  const themes = listThemes();
  if (args.flags.json) {
    console.log(JSON.stringify(themes.map(({ id, name, appearance, license }) => ({ id, name, appearance, license })), null, 2));
    return;
  }
  const width = Math.max(...themes.map((t) => t.id.length));
  for (const t of themes) console.log(`${t.id.padEnd(width)}  ${t.appearance.padEnd(5)}  ${t.name}`);
}

async function cmdFonts(args) {
  ensureDeps({ log: (m) => console.error(`cli-motion: ${m}`) });
  const { listFonts, nerdCacheDir } = await import('./lib/fonts/index.mjs');
  const fonts = listFonts();
  if (args.flags.json) {
    console.log(JSON.stringify(fonts, null, 2));
    return;
  }
  const width = Math.max(...fonts.map((f) => f.name.length));
  for (const f of fonts) {
    console.log(`${f.name.padEnd(width)}${f.name === 'JetBrains Mono' ? '  (default)' : '           '}  ${f.package}  nerd: ${f.nerd} [${f.nerdCached ? 'cached' : 'downloads on first use'}]`);
  }
  console.log(`\nfont_size: any number of px (default 14). Nerd Fonts cache: ${nerdCacheDir()}`);
}

async function cmdPreview(args) {
  ensureDeps({ log: (m) => console.error(`cli-motion: ${m}`) });
  const { PREVIEW_DEFAULTS, buildCells, parseList, sheetHtml, sheetPng } = await import('./lib/preview/index.mjs');
  const { FONT_NAMES, fontInfo } = await import('./lib/fonts/index.mjs');
  const { listThemes, loadTheme } = await import('./lib/config/index.mjs');
  const fonts = parseList(args.flags.fonts, FONT_NAMES, 'fonts') ?? PREVIEW_DEFAULTS.fonts;
  const sizes = (parseList(args.flags.sizes, [], 'sizes') ?? PREVIEW_DEFAULTS.sizes).map((v) => {
    if (!(Number(v) > 0)) throw new UsageError(`--sizes: "${v}" is not a size in px`);
    return Number(v);
  });
  const themes = parseList(args.flags.themes, listThemes().map((t) => t.id), 'themes') ?? PREVIEW_DEFAULTS.themes;
  fonts.forEach((f) => fontInfo(f));
  themes.forEach((t) => loadTheme(t));
  const out = resolve(args.flags.out ?? 'cli-motion-preview.png');
  const cells = await buildCells({ fonts, sizes, themes });
  if (/\.html?$/i.test(out)) writeOut(out, sheetHtml(cells));
  else if (/\.png$/i.test(out)) writeOut(out, await sheetPng(cells, { cols: Math.min(themes.length, 3) }));
  else throw new UsageError(`--out must end in .png or .html, got "${out}"`);
  console.log(`${out} (${cells.length} cells: ${fonts.length} fonts × ${sizes.length} sizes × ${themes.length} themes)`);
}

function cmdDoctor(args) {
  const major = Number(process.versions.node.split('.')[0]);
  const rows = [];
  const ok = (label, detail) => rows.push(['ok  ', label, detail]);
  const warn = (label, detail) => rows.push(['warn', label, detail]);
  const bad = (label, detail) => rows.push(['FAIL', label, detail]);

  major >= 20 ? ok('node', `v${process.versions.node}`) : bad('node', `v${process.versions.node}: Node 20+ is required`);

  const ff = spawnSync('ffmpeg', ['-version'], { encoding: 'utf8' });
  ff.status === 0
    ? ok('ffmpeg', ff.stdout.split('\n')[0])
    : warn('ffmpeg', 'not found: optional, only needed for MP4 export (GIF has a pure-JS fallback)');

  const npx = spawnSync(process.platform === 'win32' ? 'npx.cmd' : 'npx', ['--version'], { encoding: 'utf8' });
  npx.status === 0 ? ok('npx', `v${npx.stdout.trim()} (runs the pinned svg-term-cli@2.1.1)`) : bad('npx', 'not found: install Node with npm');

  if (args.flags.install) {
    try {
      ensureDeps({ log: (m) => console.error(`cli-motion: ${m}`) });
    } catch (err) {
      bad('cache', err.message);
    }
  }
  const cache = cacheState();
  cache.ready
    ? ok('cache', `${cache.dir} (dependencies installed)`)
    : warn('cache', `${cache.dir} (empty: installs on first render, or run \`cli-motion doctor --install\`; needs network once)`);

  for (const [level, label, detail] of rows) console.log(`${level}  ${label.padEnd(7)} ${detail}`);
  if (rows.some((r) => r[0] === 'FAIL')) process.exitCode = 1;
}

async function main() {
  const [command, ...rest] = process.argv.slice(2);
  if (!command || command === '-h' || command === '--help' || command === 'help') {
    console.log(USAGE);
    return;
  }
  const args = parseArgs(rest);
  if (args.flags.help) {
    console.log(USAGE);
    return;
  }
  switch (command) {
    case 'render': return cmdRender(args, false);
    case 'still': return cmdRender(args, true);
    case 'themes': return cmdThemes(args);
    case 'doctor': return cmdDoctor(args);
    case 'fonts': return cmdFonts(args);
    case 'preview': return cmdPreview(args);
    case 'export':
      throw new UsageError('`export` is implemented in a later release of cli-motion');
    default:
      throw new UsageError(`unknown command "${command}"\n\n${USAGE}`);
  }
}

main().catch((err) => {
  const known = err instanceof UsageError || ['ConfigError', 'SceneError', 'StyleError', 'RenderError'].includes(err.name);
  console.error(`cli-motion: ${known ? err.message : err.stack}`);
  process.exit(known ? 1 : 2);
});
