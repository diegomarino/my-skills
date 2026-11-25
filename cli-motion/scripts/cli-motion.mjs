#!/usr/bin/env node
// cli-motion: terminal animations from a declarative YAML scene.
//
//   cli-motion render <scene.yaml> [-o out.svg] [--cast [file]]
//   cli-motion still  <scene.yaml> [--at <ms|end>] [-o out.svg]
//   cli-motion themes [--json]
//   cli-motion doctor [--install]

import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { SKILL_DIR, cacheState, ensureDeps, svgTermBin } from './lib/deps.mjs';
import { ffmpegInfo } from './lib/raster/ffmpeg.mjs';

const USAGE = `cli-motion: terminal animations from a YAML scene

Usage
  cli-motion render <scene.yaml> [-o out.svg] [--cast [file]]   animated SVG
  cli-motion still  <scene.yaml> [--at <ms|end>] [-o out.svg]   one frame as SVG
  cli-motion themes [--json]                                    list the 25 themes
  cli-motion doctor [--install]                                 check Node, ffmpeg, cache
  cli-motion fonts [--json]                                     list fonts, sizes, Nerd Font cache
  cli-motion preview [--fonts a,b|all] [--sizes 12,14] [--themes a,b|all] [--out sheet.png|sheet.html]
                                                                contact sheet: font × size × theme
  cli-motion export <scene.yaml> [--gif] [--mp4] [--scale 1|2|3] [--fps N] [--out dir]
                                                                GIF and/or MP4 (default: both; 2x, MP4 30 fps)

Options
  -o, --out <file>   output path (default: next to the scene)
  --cast [file]      also write the asciicast v2 (default: next to the output)
  --at <ms|end>      still: millisecond of the frame, or "end" (default)
  --gif / --mp4      export: formats to write (neither given = both; MP4 is skipped without ffmpeg)
  --scale <1|2|3>    export: pixel scale (default 2)
  --fps <n>          export: MP4 frame rate (default 30)
  --encoder <e>      export: GIF encoder auto | ffmpeg | js (default auto: ffmpeg when found)
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
      // a following path is the cast file, unless it is the scene (no scene yet, or a .yaml file)
      const n = argv[i + 1];
      args.flags.cast = n && !n.startsWith('-') && args._.length > 0 && !/\.ya?ml$/i.test(n) ? argv[++i] : true;
    } else if (a.startsWith('--cast=')) args.flags.cast = a.slice(7);
    else if (a === '--fonts') args.flags.fonts = next();
    else if (a === '--sizes') args.flags.sizes = next();
    else if (a === '--themes') args.flags.themes = next();
    else if (a === '--gif') args.flags.gif = true;
    else if (a === '--mp4') args.flags.mp4 = true;
    else if (a === '--scale') args.flags.scale = next();
    else if (a === '--fps') args.flags.fps = next();
    else if (a === '--encoder') args.flags.encoder = next();
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

/** Refuse to write beside a scene that lives inside the skill folder unless the caller chose the path. */
function guardOutput(path, explicit, flag) {
  const rel = relative(SKILL_DIR, path);
  if (!explicit && !rel.startsWith('..') && !isAbsolute(rel)) {
    throw new UsageError(`${path} is inside the skill folder (${SKILL_DIR}), where it would overwrite shipped files. Pass ${flag} <path outside the skill> (use ${flag} with the same path to regenerate a shipped example on purpose).`);
  }
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
  guardOutput(out, args.flags.out != null, '-o');
  const svg = still ? await svgLib.renderStill(build, args.flags.at ?? 'end') : await svgLib.renderAnimated(build);
  writeOut(out, svg);
  if (args.flags.cast) {
    const castPath = typeof args.flags.cast === 'string' ? resolve(args.flags.cast) : out.replace(/\.svg$/, '') + '.cast';
    writeOut(castPath, build.castText);
    console.error(`cli-motion: wrote ${castPath}`);
  }
  const kb = (Buffer.byteLength(svg) / 1024).toFixed(1);
  for (const e of build.bannerEffects ?? []) {
    console.error(`cli-motion: banner effect ${e.effect}: ${e.frames} distinct frames kept of ${e.requested} samples (${e.fps} fps × ${e.duration}s; repeated states merge) at ${e.where.replace(/^.*?: /, '')}`);
  }
  if (build.bannerEffects?.length) {
    const frames = build.bannerEffects.reduce((n, e) => n + e.frames, 0);
    console.error(`cli-motion: banner effects added ${frames} distinct frames; SVG is ${kb} KB. Lower fps or duration (or use a reveal effect) to shrink it.`);
  }
  console.log(`${out} (${kb} KB, ${build.duration.toFixed(1)}s, ${build.header.width}x${build.header.height} cells, ${build.style.theme})`);
}

async function cmdExport(args) {
  const [sceneFile] = args._;
  if (!sceneFile) throw new UsageError(`export needs a scene file\n\n${USAGE}`);
  const build = await loadBuild(sceneFile);
  const { exportScene } = await import('./lib/raster/index.mjs');
  const { ffmpegInfo } = await import('./lib/raster/ffmpeg.mjs');
  const explicit = args.flags.gif || args.flags.mp4;
  let gif = explicit ? !!args.flags.gif : true;
  let mp4 = explicit ? !!args.flags.mp4 : true;
  if (!explicit && !ffmpegInfo().ffmpeg) {
    mp4 = false;
    console.error('cli-motion: ffmpeg not found: skipping MP4 (writing the GIF with the pure-JS encoder)');
  }
  const outDir = resolve(args.flags.out ?? dirname(build.file));
  guardOutput(outDir, args.flags.out != null, '--out');
  const results = await exportScene(build, {
    gif, mp4, outDir, base: sceneBase(sceneFile), encoder: args.flags.encoder ?? 'auto',
    flags: { scale: args.flags.scale, fps: args.flags.fps },
    log: (m) => console.error(`cli-motion: ${m}`),
  });
  for (const r of results) {
    const kb = (statSync(r.file).size / 1024).toFixed(0);
    const what = r.format === 'mp4' ? `${r.frames} video frames at ${r.fps ?? 30} fps` : `${r.frames} GIF frames`;
    console.log(`${r.file} (${r.format}${r.encoder ? `, ${r.encoder}` : ''}, ${kb} KB, ${r.seconds.toFixed(2)}s, ${what}, ${r.unique} distinct images)`);
  }
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

/** Run the pinned svg-term on a one-event cast: proves the renderer starts, offline. */
function probeSvgTerm() {
  const dir = mkdtempSync(join(tmpdir(), 'cli-motion-doctor-'));
  try {
    const cast = join(dir, 'p.cast');
    writeFileSync(cast, `${JSON.stringify({ version: 2, width: 10, height: 2 })}\n${JSON.stringify([0.1, 'o', 'ok'])}\n`);
    const res = spawnSync(process.execPath, [svgTermBin(), '--in', cast, '--out', join(dir, 'p.svg'), '--padding', '0'], { encoding: 'utf8', timeout: 30000 });
    if (res.status !== 0) return { ok: false, detail: (res.stderr || res.stdout || res.error?.message || `exit ${res.status}`).trim().split('\n')[0] };
    return { ok: statSync(join(dir, 'p.svg')).size > 0, detail: 'svg-term-cli@2.1.1 rendered a test cast from the cache (no network used)' };
  } catch (err) {
    return { ok: false, detail: err.message };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function cmdDoctor(args) {
  const major = Number(process.versions.node.split('.')[0]);
  const rows = [];
  const ok = (label, detail) => rows.push(['ok  ', label, detail]);
  const warn = (label, detail) => rows.push(['warn', label, detail]);
  const bad = (label, detail) => rows.push(['FAIL', label, detail]);

  major >= 20 ? ok('node', `v${process.versions.node}`) : bad('node', `v${process.versions.node}: Node 20+ is required`);

  const ff = ffmpegInfo();
  ff.ffmpeg
    ? ok('ffmpeg', ff.ffmpeg)
    : warn('ffmpeg', 'not found: optional, only needed for MP4 export (GIF has a pure-JS fallback, with much larger files)');

  const npm = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['--version'], { encoding: 'utf8' });
  npm.status === 0 ? ok('npm', `v${npm.stdout.trim()} (only used to install the dependency cache)`) : warn('npm', 'not found: needed once to install dependencies into the cache');

  if (args.flags.install) {
    try {
      ensureDeps({ log: (m) => console.error(`cli-motion: ${m}`) });
    } catch (err) {
      bad('cache', err.message);
    }
  }
  const cache = cacheState();
  let renderer = false;
  if (cache.ready) {
    ok('cache', `${cache.dir} (dependencies installed)`);
    const probe = probeSvgTerm();
    probe.ok ? ok('svg-term', probe.detail) : bad('svg-term', `${probe.detail}. Run \`node scripts/cli-motion.mjs doctor --install\` (needs network once)`);
    renderer = probe.ok;
  } else {
    bad('cache', `${cache.dir} is empty: nothing can render yet. Run \`node scripts/cli-motion.mjs doctor --install\` (needs network once)`);
    bad('svg-term', 'not available until the cache is installed');
  }

  const formats = renderer
    ? [
      'verified here: animated svg, svg still, png preview',
      ff.ffmpeg && ff.libx264 ? 'mp4: yes (ffmpeg + libx264)' : ff.ffmpeg ? 'mp4: no (this ffmpeg lacks libx264)' : 'mp4: no (needs ffmpeg)',
      ff.ffmpeg ? 'gif: yes (ffmpeg, one global palette; --encoder js for pure JS)' : 'gif: yes (pure-JS gifenc, one global palette, larger files)',
    ]
    : ['nothing can be written until svg-term is available (see above)'];
  renderer ? ok('export', formats.join('; ')) : bad('export', formats.join('; '));

  for (const [level, label, detail] of rows) console.log(`${level}  ${label.padEnd(8)} ${detail}`);
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
    case 'export': return cmdExport(args);
    default:
      throw new UsageError(`unknown command "${command}"\n\n${USAGE}`);
  }
}

main().catch((err) => {
  const known = err instanceof UsageError || ['ConfigError', 'SceneError', 'StyleError', 'RenderError'].includes(err.name);
  console.error(`cli-motion: ${known ? err.message : err.stack}`);
  process.exit(known ? 1 : 2);
});
