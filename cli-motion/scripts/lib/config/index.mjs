// Configuration: merges the four layers and rejects unknown keys.
//
//   1. assets/defaults.yaml        2. cli-motion.yaml (found upward from the scene)
//   3. the scene's `style:`        4. a scene's own `style:` (scene-scoped keys only)

import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { dep, SKILL_DIR } from '../deps.mjs';

export const ASSETS_DIR = join(SKILL_DIR, 'assets');
export const PROJECT_CONFIG_NAME = 'cli-motion.yaml';

/** Keys a single scene may override. Everything else is fixed for the whole render. */
export const SCENE_SCOPED = new Set([
  'prompt', 'prompt_template', 'prompt_cwd', 'prompt_branch', 'prompt_user', 'prompt_host',
  'prompt_time', 'prompt_status', 'cursor', 'cursor_blink', 'typed_style', 'output_style',
  'comment_style', 'styles', 'speed', 'typing_delay', 'typing_jitter', 'enter_delay',
  'prompt_delay', 'line_delay', 'scene_hold', 'spinner', 'spinner_style', 'banner_font',
  'banner_style', 'banner_gradient', 'banner_effect', 'banner_effect_duration', 'banner_effect_fps',
  'banner_effect_direction', 'banner_effect_cycles', 'transition', 'transition_duration',
]);

const ENUMS = {
  window: ['chrome', 'plain', 'none'],
  cursor: ['hidden', 'block', 'bar', 'underline'],
  playback: ['loop', 'once'],
  font_nerd: ['auto', true, false],
  transition: ['cut', 'clear', 'fade'],
};

export class ConfigError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ConfigError';
  }
}

export function parseYaml(text, where) {
  const YAML = dep('yaml');
  try {
    return YAML.parse(text) ?? {};
  } catch (err) {
    throw new ConfigError(`${where}: invalid YAML: ${err.message}`);
  }
}

let defaultsCache = null;
export function loadDefaults() {
  if (!defaultsCache) {
    const file = join(ASSETS_DIR, 'defaults.yaml');
    defaultsCache = parseYaml(readFileSync(file, 'utf8'), file);
  }
  return structuredClone(defaultsCache);
}

export function validKeys() {
  return Object.keys(loadDefaults());
}

/** Closest valid name to a typo, or null: ` Did you mean "theme"?` */
export function didYouMean(key, allowed) {
  const dist = (a, b) => {
    const row = Array.from({ length: b.length + 1 }, (_, j) => j);
    for (let i = 1; i <= a.length; i++) {
      let prev = row[0];
      row[0] = i;
      for (let j = 1; j <= b.length; j++) {
        const tmp = row[j];
        row[j] = Math.min(row[j] + 1, row[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1));
        prev = tmp;
      }
    }
    return row[b.length];
  };
  let best = null;
  let bestD = Infinity;
  for (const name of allowed) {
    const d = dist(String(key).toLowerCase(), String(name).toLowerCase());
    if (d < bestD) { best = name; bestD = d; }
  }
  return best != null && bestD <= Math.max(2, Math.floor(String(key).length / 3)) ? ` Did you mean "${best}"?` : '';
}

/** Fail on keys that are not options, naming the key and listing the valid ones. */
export function checkKeys(layer, where, allowed = validKeys()) {
  if (layer == null) return;
  if (typeof layer !== 'object' || Array.isArray(layer)) {
    throw new ConfigError(`${where}: expected a map of options, got ${Array.isArray(layer) ? 'a list' : typeof layer}`);
  }
  for (const key of Object.keys(layer)) {
    if (!allowed.includes(key)) {
      throw new ConfigError(
        `${where}: unknown option "${key}".${didYouMean(key, allowed)} Valid options: ${[...allowed].sort().join(', ')}`,
      );
    }
  }
}

function checkValues(style, where) {
  for (const [key, values] of Object.entries(ENUMS)) {
    if (key in style && !values.includes(style[key])) {
      throw new ConfigError(`${where}: invalid ${key} "${style[key]}". Valid values: ${values.join(', ')}`);
    }
  }
  if (style.styles != null && (typeof style.styles !== 'object' || Array.isArray(style.styles))) {
    throw new ConfigError(`${where}: "styles" must be a map of name: style`);
  }
}

/** Layer `over` onto `base`; `styles` merges key by key, everything else replaces. */
export function mergeLayer(base, over) {
  const out = { ...base };
  for (const [key, value] of Object.entries(over ?? {})) {
    out[key] = key === 'styles' ? { ...(base.styles ?? {}), ...(value ?? {}) } : value;
  }
  return out;
}

/** Find cli-motion.yaml in `startDir` or any parent. */
export function findProjectConfig(startDir) {
  let dir = resolve(startDir);
  for (;;) {
    const candidate = join(dir, PROJECT_CONFIG_NAME);
    if (existsSync(candidate)) return candidate;
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

/**
 * Resolve layers 1-3: defaults < project config < the scene's `style:`.
 * Returns { style, projectConfig }.
 */
export function resolveStyle({ sceneDir, sceneStyle, projectConfigPath, sceneFile = 'scene file' }) {
  let style = loadDefaults();
  const projectPath = projectConfigPath === undefined ? findProjectConfig(sceneDir) : projectConfigPath;
  if (projectPath) {
    const project = parseYaml(readFileSync(projectPath, 'utf8'), projectPath);
    checkKeys(project, projectPath);
    checkValues(project, projectPath);
    style = mergeLayer(style, project);
  }
  checkKeys(sceneStyle, `${sceneFile}: style`);
  checkValues(sceneStyle ?? {}, `${sceneFile}: style`);
  style = mergeLayer(style, sceneStyle);
  return { style, projectConfig: projectPath };
}

/** Layer 4a: a scene's `style:` block. Only scene-scoped keys are allowed. */
export function applySceneStyle(style, sceneStyle, where) {
  if (sceneStyle == null) return style;
  checkKeys(sceneStyle, where, [...SCENE_SCOPED]);
  checkValues(sceneStyle, where);
  return mergeLayer(style, sceneStyle);
}

// ── themes ──────────────────────────────────────────────────────────────────

export function listThemes() {
  const dir = join(ASSETS_DIR, 'themes');
  return readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .sort()
    .map((f) => JSON.parse(readFileSync(join(dir, f), 'utf8')));
}

export function loadTheme(id) {
  const file = join(ASSETS_DIR, 'themes', `${id}.json`);
  if (!existsSync(file)) {
    const ids = listThemes().map((t) => t.id);
    throw new ConfigError(`unknown theme "${id}". Valid themes: ${ids.join(', ')}`);
  }
  return JSON.parse(readFileSync(file, 'utf8'));
}
