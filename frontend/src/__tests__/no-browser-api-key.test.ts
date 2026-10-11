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
 * Three legs, all plain filesystem scans of the checked-out tree. The code
 * scope is the whole frontend/ build scope — `src`, the build config, the
 * frontend's own scripts, `index.html` (Vite substitutes `%VITE_*%` there) —
 * because anything under frontend/ can reach the bundle, not just src/.
 *
 *  A. The env var's name must not appear in any CODE file (*.ts/*.tsx/*.js/
 *     *.cjs/*.mjs/*.html) under frontend/ — not as an env-object read, not in
 *     a fixture. Sub-check: no code file may access the env object through a
 *     BRACKET (a computed key) — the obfuscation shape that would let a name
 *     built from parts slip past the literal needle. The access shape itself
 *     is banned, not just the name; this file's own prose therefore spells
 *     the env object's name only through the assembled needle below, never
 *     contiguously followed by a bracket.
 *  A2. Docs may still NAME the removed variable (prose that tells an operator
 *     to unset it is useful prose), but may not carry its ASSIGNMENT form
 *     (`NAME=…` / `NAME: …`) — that is the copy-paste which re-arms the leak,
 *     and the ruling's threat model is an operator following the docs. Doc
 *     scope: every *.md under frontend/ and docs/ and scripts/, plus the
 *     loose *.md and .env* files at the repo root.
 *  B. Production sources (non-test paths, leg A's extension set) must not
 *     contain the WebSocket credential subprotocol prefix. Docs may NAME the
 *     form in prose; test files may reference it in negative assertions;
 *     production browser code may not — minting it is the leak.
 *
 * What still ships green (stated so nobody reads this file as the whole
 * defence): a key name assembled so dynamically that neither the name nor a
 * bracketed env access ever appears as text (character-code loops); values
 * fetched at runtime — no source scan can see those; backend/, which holds
 * keys legitimately; and docs in roots outside A2's list. The behavioural
 * pin — services/api.test.ts "sends NO credential header", asserting the
 * headers actually handed to fetch — is what catches a leak through a path
 * this scan cannot name.
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
/** The env-object member-access object, assembled so the bracket sub-check
 *  below — and this file's own prose — never carry the contiguous shape. */
const ENV_OBJECT = ['import', '.', 'meta', '.', 'env'].join('');

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FE_ROOT = path.resolve(__dirname, '..', '..'); // frontend/
const REPO_ROOT = path.resolve(FE_ROOT, '..');
/** Generated/vendored trees are not source: never walk them. */
const SKIP_DIRS = new Set(['node_modules', 'dist', 'coverage', '.vitest']);
/** Leg A's code extension set — everything Vite can build or inline. */
const CODE_EXT = /\.(ts|tsx|js|cjs|mjs|html)$/;

interface ScannedFile {
  path: string; // relative to the walk's root, for failure messages
  content: string;
}

function walk(dir: string, root: string, wanted: (name: string) => boolean): ScannedFile[] {
  const out: ScannedFile[] = [];
  // SAFE for this rule's purpose (user input reaching fs): the only arguments
  // ever passed are FE_ROOT/REPO_ROOT/docs/scripts or a path.join of those
  // with a directory name this same walk produced — a repo-relative tree
  // baked into the test. This guard runs in CI against the checked-out source,
  // so it reads the tree by design.
  /* eslint-disable security/detect-non-literal-fs-filename */
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walk(full, root, wanted));
    } else if (entry.isFile() && wanted(entry.name)) {
      // utf8-decoded only after the extension gate: docs/ carries images a
      // blanket decode would mangle (and slow the walk down for nothing).
      const relDir = path.relative(root, dir);
      out.push({
        path: relDir ? path.join(relDir, entry.name) : entry.name,
        content: fs.readFileSync(full, 'utf8'),
      });
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
  const isCode = (name: string) => CODE_EXT.test(name);
  const isMd = (name: string) => name.endsWith('.md');
  // .env example files are docs an operator copies from, so they get the
  // assignment ban too. They live at the repo root (frontend/ ships none).
  const isEnvExample = (name: string) => name.startsWith('.env');
  const feFiles = walk(FE_ROOT, FE_ROOT, (n) => isCode(n) || isMd(n));
  const codeFiles = feFiles.filter((f) => isCode(f.path));

  const docFiles: ScannedFile[] = [
    ...feFiles.filter((f) => isMd(f.path)),
    ...walk(path.join(REPO_ROOT, 'docs'), REPO_ROOT, isMd),
    ...walk(path.join(REPO_ROOT, 'scripts'), REPO_ROOT, isMd),
    // Repo-root loose files only (README.md, AGENTS.md, .env.example, …):
    // REPO_ROOT itself is never walked wholesale.
    ...fs
      .readdirSync(REPO_ROOT, { withFileTypes: true })
      .filter((e) => e.isFile() && (isMd(e.name) || isEnvExample(e.name)))
      .map((e) => ({
        path: e.name,
        // SAFE for the same reason walk() is: REPO_ROOT baked at authoring,
        // e.name produced by readdirSync of it — no user input in the path.
        /* eslint-disable-next-line security/detect-non-literal-fs-filename */
        content: fs.readFileSync(path.join(REPO_ROOT, e.name), 'utf8'),
      })),
  ];

  it('scans a real tree (anti-vacuity)', () => {
    // A path bug would silently make the legs vacuous-pass. Pin both walks.
    // Floors measured on this tree at authoring: 1,817 code files under
    // frontend/, 688 doc files (99 frontend .md + 570 docs/ + 12 scripts/ +
    // 7 repo-root loose: 5 .md + 2 .env*). Re-measure with the guard's own
    // walk if a scope changes — find/ls-files counts differ from readdirSync.
    expect(codeFiles.length).toBeGreaterThan(800);
    expect(docFiles.length).toBeGreaterThan(400);
    const code = codeFiles.map((f) => f.path.replace(/\\/g, '/'));
    // incl. this file: a guard that can read itself is a guard that works.
    for (const sentinel of [
      'src/services/api.ts',
      'src/config/env.ts',
      'vite.config.ts',
      'src/__tests__/no-browser-api-key.test.ts',
    ]) {
      expect(code).toContain(sentinel);
    }
    const docs = docFiles.map((f) => f.path.replace(/\\/g, '/'));
    // 'docs/…' because that walk is rooted at REPO_ROOT; 'README.md' because
    // root loose files are read by name — the two path bases differ by design.
    for (const sentinel of ['README.md', 'docs/operator/admin/api-keys.md']) {
      expect(docs).toContain(sentinel);
    }
  });

  it('leg A: no code file reads the baked key env var, or reads env by computed name', () => {
    const nameOffenders = codeFiles
      .filter((f) => f.content.includes(ENV_VAR_NAME))
      .map((f) => f.path.replace(/\\/g, '/'));
    expect(nameOffenders).toEqual([]);
    // The shape that hides a name from the needle above: the env object
    // accessed through a bracket (a computed key). Hand-rolled like
    // carriesAssignmentForm, against the assembled ENV_OBJECT — so neither
    // this scanner nor this file's prose contains the contiguous shape it
    // hunts. Banning the shape outright costs nothing today: no legit code
    // needs a dynamic env key, and a future need is a ruling-44 conversation.
    const accessesEnvByBracket = (text: string): boolean => {
      let from = 0;
      for (;;) {
        const at = text.indexOf(ENV_OBJECT, from);
        if (at === -1) return false;
        from = at + ENV_OBJECT.length;
        let i = from;
        while (/\s/.test(text[i] ?? '')) i++;
        if (text[i] === '[') return true;
      }
    };
    const computedOffenders = codeFiles
      .filter((f) => accessesEnvByBracket(f.content))
      .map((f) => f.path.replace(/\\/g, '/'));
    expect(computedOffenders).toEqual([]);
  });

  it('leg A2: no doc or env example recommends SETTING the baked key env var', () => {
    // Prose may NAME the removed variable to tell operators to unset it; docs
    // may not carry its assignment form (`NAME=…`, or `NAME: …` in an env
    // block) — the assignment form is the copy-paste that re-arms the leak.
    // Threat model: an operator following the docs. Plain string scanning, not
    // a RegExp: the env-var name is built by concatenation, and interpolating
    // it into a pattern would build a regex from a computed string.
    const offenders = docFiles
      .filter((f) => carriesAssignmentForm(f.content, ENV_VAR_NAME))
      .map((f) => f.path.replace(/\\/g, '/'));
    expect(offenders).toEqual([]);
  });

  it('leg B: no production source mints the credential subprotocol', () => {
    const offenders = codeFiles
      .filter((f) => !isTestSupport(f.path))
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
