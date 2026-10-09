/**
 * Ruling 44 guard: no API key in the browser bundle.
 *
 * Vite writes `VITE_*` values into the built JavaScript at BUILD time, so any
 * read of the browser-baked API-key env var ships the secret to everyone who can
 * load the UI — and the UI has to be served, since the login page lives in it.
 * That undoes the deny-by-default auth of D10/OD-12 for any deployment built
 * with the variable set. Browsers authenticate ONLY through the cookie login;
 * API keys are for non-browser clients (the X-API-Key header, or the scripted
 * WebSocket subprotocol form — prose here, never minted in browser code).
 *
 * Two legs, both plain filesystem scans of the checked-out tree:
 *
 *  A. The env var's name (the VITE_-prefixed key variable) must not appear
 *     anywhere under frontend/src — not as an `import.meta.env` read, not in a
 *     test fixture, not in an AGENTS.md example re-recommending it.
 *  B. Production sources (*.ts / *.tsx outside test directories) must not
 *     contain the WebSocket credential subprotocol prefix. Docs may NAME the
 *     form in prose; test files may reference it in negative assertions;
 *     production browser code may not — minting it is the leak.
 *
 * The needles are built by concatenation so this file never contains the
 * literals it bans — a guard that must exempt itself is a guard with a hole.
 */
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

import { describe, expect, it } from 'vitest';

/** The banned env-var name, assembled so this file passes its own leg A. */
const ENV_VAR_NAME = ['VITE', 'API', 'KEY'].join('_');
/** The banned credential subprotocol prefix, assembled for the same reason. */
const SUBPROTOCOL_PREFIX = ['api-key', '.'].join('');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC_ROOT = path.resolve(__dirname, '..'); // frontend/src

interface ScannedFile {
  path: string; // repo-relative-ish, for failure messages
  content: string;
}

function walk(dir: string): ScannedFile[] {
  const out: ScannedFile[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walk(full));
    } else if (entry.isFile() && fs.statSync(full).isFile()) {
      out.push({ path: path.relative(SRC_ROOT, full), content: fs.readFileSync(full, 'utf8') });
    }
  }
  return out;
}

/** Test-support paths may reference the credential form to assert its ABSENCE. */
function isTestSupport(path: string): boolean {
  return /(^|\/)(__tests__|__mocks__)(\/|$)/.test(path) || /\.test\.tsx?$/.test(path);
}

describe('ruling 44: no API key in the browser bundle', () => {
  const files = walk(SRC_ROOT);

  it('scans a real tree (anti-vacuity)', () => {
    // A path bug would silently make both legs vacuous-pass. Pin the walk.
    expect(files.length).toBeGreaterThan(400);
    const paths = files.map((f) => f.path.replace(/\\/g, '/'));
    for (const sentinel of ['services/api.ts', 'config/env.ts', 'AGENTS.md']) {
      expect(paths).toContain(sentinel);
    }
  });

  it('leg A: no code file reads the baked key env var', () => {
    const offenders = files
      .filter((f) => /\.(ts|tsx|js|cjs|mjs)$/.test(f.path))
      .filter((f) => f.content.includes(ENV_VAR_NAME))
      .map((f) => f.path.replace(/\\/g, '/'));
    expect(offenders).toEqual([]);
  });

  it('leg A2: no doc recommends SETTING the baked key env var', () => {
    // Prose may NAME the removed variable to tell operators to unset it; docs
    // may not carry its assignment form (`NAME=…`, or backticked `NAME: …` in
    // an env block) — the assignment form is the copy-paste that re-arms the
    // leak. Threat model: an operator following the docs.
    const assignment = new RegExp(`${ENV_VAR_NAME}\\s*[=:]`, 'm');
    const offenders = files
      .filter((f) => /\.md$/.test(f.path))
      .filter((f) => assignment.test(f.content))
      .map((f) => f.path.replace(/\\/g, '/'));
    expect(offenders).toEqual([]);
  });

  it('leg B: no production source mints the credential subprotocol', () => {
    const offenders = files
      .filter((f) => !isTestSupport(f.path))
      .filter((f) => /\.(ts|tsx)$/.test(f.path))
      .filter((f) => f.content.includes(SUBPROTOCOL_PREFIX))
      .map((f) => f.path.replace(/\\/g, '/'));
    expect(offenders).toEqual([]);
  });
});
