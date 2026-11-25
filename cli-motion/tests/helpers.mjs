import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ensureDeps } from '../scripts/lib/deps.mjs';

ensureDeps();

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
export const EXAMPLES = join(ROOT, 'examples');

export const { loadScene } = await import('../scripts/lib/scene/index.mjs');
export const svg = await import('../scripts/lib/svg/index.mjs');
export const config = await import('../scripts/lib/config/index.mjs');

/** Write files ({ relative path: text }) into a fresh temp dir; returns the dir. */
export function tmpProject(files) {
  const dir = mkdtempSync(join(tmpdir(), 'cli-motion-test-'));
  for (const [rel, text] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), text);
  }
  return dir;
}

export const SIMPLE = `
style: { width: 40, final_hold: 2s }
steps:
  - command: "echo hi"
  - output: "[accent]hi[/]"
`;
