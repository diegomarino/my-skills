// First-run dependency bootstrap.
//
// The skill folder is read-only at runtime (the installer hashes it), so runtime
// dependencies are installed with `npm ci` into
//   ${CLI_MOTION_CACHE | XDG_CACHE_HOME | ~/.cache}/cli-motion/<lock-hash>/
// from the pinned package.json + package-lock.json that ship with the skill.
// Nothing global, nothing inside the skill folder.

import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const SCRIPTS_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');
export const SKILL_DIR = join(SCRIPTS_DIR, '..');

export function cacheRoot(env = process.env) {
  const base = env.CLI_MOTION_CACHE
    ? env.CLI_MOTION_CACHE
    : join(env.XDG_CACHE_HOME || join(homedir(), '.cache'), 'cli-motion');
  return base;
}

export function lockHash() {
  const lock = readFileSync(join(SCRIPTS_DIR, 'package-lock.json'));
  const pkg = readFileSync(join(SCRIPTS_DIR, 'package.json'));
  return createHash('sha256').update(pkg).update(lock).digest('hex').slice(0, 12);
}

export function cacheDir(env = process.env) {
  return join(cacheRoot(env), lockHash());
}

export function cacheState(env = process.env) {
  const dir = cacheDir(env);
  return { dir, ready: existsSync(join(dir, '.ready')) };
}

let requireFromCache = null;

/** Install dependencies if the cache for this lockfile is missing. Idempotent. */
export function ensureDeps({ env = process.env, log = () => {} } = {}) {
  const { dir, ready } = cacheState(env);
  if (!ready) {
    log(`first run: installing dependencies into ${dir} (needs network, one time)`);
    const tmp = `${dir}.tmp-${process.pid}`;
    rmSync(tmp, { recursive: true, force: true });
    mkdirSync(tmp, { recursive: true });
    copyFileSync(join(SCRIPTS_DIR, 'package.json'), join(tmp, 'package.json'));
    copyFileSync(join(SCRIPTS_DIR, 'package-lock.json'), join(tmp, 'package-lock.json'));
    const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
    const res = spawnSync(npm, ['ci', '--omit=dev', '--no-audit', '--no-fund', '--loglevel=error'], {
      cwd: tmp,
      encoding: 'utf8',
      env,
    });
    if (res.status !== 0) {
      rmSync(tmp, { recursive: true, force: true });
      throw new Error(
        `dependency install failed (npm ci exit ${res.status}). Check network access and run \`cli-motion doctor\`.\n${(res.stderr || res.stdout || '').trim()}`,
      );
    }
    writeFileSync(join(tmp, '.ready'), `${new Date(0).toISOString()}\n`);
    try {
      renameSync(tmp, dir);
    } catch (err) {
      // another process won the race: its install is as good as ours
      rmSync(tmp, { recursive: true, force: true });
      if (!existsSync(join(dir, '.ready'))) throw err;
    }
  }
  requireFromCache = createRequire(join(dir, 'package.json'));
  return dir;
}

/** Load an installed runtime dependency (CommonJS entry; works for yaml, figlet). */
export function dep(name) {
  if (!requireFromCache) ensureDeps();
  return requireFromCache(name);
}

/** Absolute path of the pinned svg-term CLI inside the dependency cache (installs the cache if needed). */
export function svgTermBin(opts) {
  const dir = ensureDeps(opts);
  const pkgFile = join(dir, 'node_modules', 'svg-term-cli', 'package.json');
  if (!existsSync(pkgFile)) {
    throw new Error(
      `svg-term-cli is missing from the dependency cache ${dir}. Run \`cli-motion doctor --install\` (needs network once); delete the folder first if it persists.`,
    );
  }
  const bin = JSON.parse(readFileSync(pkgFile, 'utf8')).bin;
  return join(dir, 'node_modules', 'svg-term-cli', typeof bin === 'string' ? bin : bin['svg-term']);
}
