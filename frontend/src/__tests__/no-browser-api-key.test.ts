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
 * Three legs, all plain filesystem scans of the checked-out tree:
 *
 *  A. The env var's name (the VITE_-prefixed key variable) must not appear in
 *     any CODE file under frontend/src — not as an `import.meta.env` read, not
 *     in a test fixture.
 *  A2. Docs may still NAME the removed variable (prose that tells an operator
 *     to unset it is useful prose), but may not carry its ASSIGNMENT form
 *     (`NAME=…` / `NAME: …`) — that is the copy-paste which re-arms the leak,
 *     and the ruling's threat model is an operator following the docs.
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
  // SAFE for this rule's purpose (user input reaching fs): the only argument
  // ever passed is SRC_ROOT or a path.join of it with a directory name this
  // same walk produced — a repo-relative tree baked into the test. This guard
  // runs in CI against the checked-out source, so it reads the tree by design.
  /* eslint-disable security/detect-non-literal-fs-filename */
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walk(full));
    } else if (entry.isFile() && fs.statSync(full).isFile()) {
      out.push({ path: path.relative(SRC_ROOT, full), content: fs.readFileSync(full, 'utf8') });
    }
  }
  /* eslint-enable security/detect-non-literal-fs-filename */
  return out;
}

/** Test-support paths may reference the credential form to assert its ABSENCE. */
function isTestSupport(path: string): boolean {
  return /(^|\/)(__tests__|__mocks__)(\/|$)/.test(path) || /\.test\.tsx?$/.test(path);
}

/**
 * Does this doc text carry `NAME` in its ASSIGNMENT form — `NAME=`, `NAME =`,
 * `NAME:` (as an env block writes it) — rather than merely naming it in prose?
 * Hand-rolled instead of `new RegExp(name + '\\s*[=:]')` so the guard never
 * builds a pattern out of a computed string.
 */
function carriesAssignmentForm(text: string, name: string): boolean {
  let from = 0;
  for (;;) {
    const at = text.indexOf(name, from);
    if (at === -1) return false;
    from = at + name.length;
    let i = from;
    while (/\s/.test(text[i] ?? '')) i++;
    if (text[i] === '=' || text[i] === ':') return true;
  }
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
    // may not carry its assignment form (`NAME=…`, or `NAME: …` in an env
    // block) — the assignment form is the copy-paste that re-arms the leak.
    // Threat model: an operator following the docs. Plain string scanning, not
    // a RegExp: the env-var name is built by concatenation, and interpolating
    // it into a pattern would build a regex from a computed string.
    const offenders = files
      .filter((f) => /\.md$/.test(f.path))
      .filter((f) => carriesAssignmentForm(f.content, ENV_VAR_NAME))
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

  // A third leg — "no production source mentions the credential HEADER" — was
  // tried and rejected as the wrong instrument: 24 legitimate mentions survive
  // in types/generated/api.ts (describing the header the BACKEND accepts), in
  // WebhookForm's placeholder and RecordingDetailModal's REDACTION list, and in
  // the comments that explain the ruling. The behavioural pin lives instead in
  // services/api.test.ts ("sends NO credential header"), which asserts on the
  // headers actually handed to fetch — a header set from anywhere trips that,
  // and prose cannot trip it spuriously.
});
