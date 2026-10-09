// feature-inventory-lib.mjs — read the feature inventory and the code it maps.
//
// Part of F2.2 (Feature inventory, docs/uplevel/20-frontend.md). The inventory
// at docs/reference/feature-inventory.md is what the owner rules from in R2, so
// src/__tests__/feature-inventory.test.ts checks it against the code rather than
// trusting it. This file holds the readers that gate needs:
//
// - `parseInventory` reads the markdown: every table whose header starts
//   `| id |` is feature rows; the table headed `| module | lane |` is the list of
//   modules serving no feature; the table headed `| request | function |` lists
//   client requests in exported functions nothing in production imports.
// - `appRoutes` reads the route paths `App.tsx` declares, joining nested child
//   routes onto their parent the way React Router does.
// - `reachableFiles` walks the import graph from an entry, following static
//   imports, re-exports and `import()` — the lazy routes are all `import()`.
// - `rowProblems`, `rowCites` and `callCovers` are the row rules, the cite
//   reader and the request matcher.
//
// Requests are not scanned here: the gate takes them from api-contract-lib.mjs's
// `scanClient`, so the inventory gate and the endpoint-contract gate cannot
// disagree about what the client sends.
import fs from 'node:fs';
import path from 'node:path';

import ts from 'typescript';

import { normalisePath } from './api-contract-lib.mjs';

/** The statuses a row may carry before F2.3 (README, "Vocabulary"). */
export const STATUSES = new Set(['unverified', 'half-built', 'leftover']);

/** A repo-relative `file.ext:line` cite, the evidence a half-built row needs. */
const CITE = /[\w./-]+\.[a-z]+:\d+/;

/** Split one markdown table line into trimmed cells; `\|` is a literal pipe. */
function cells(line) {
  const inner = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return inner.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, '|'));
}

/** The backticked spans of a cell, in order. */
function codeSpans(cell) {
  return [...cell.matchAll(/`([^`]+)`/g)].map((m) => m[1]);
}

/** `GET /api/x` or `WS /ws/x` spans of an API-calls cell. */
function apiCalls(cell) {
  return codeSpans(cell)
    .map((span) => span.match(/^(GET|POST|PUT|PATCH|DELETE|WS|SSE)\s+(\/\S*)$/))
    .filter(Boolean)
    .map((m) => ({ method: m[1], path: m[2] }));
}

/** Backticked route paths in a surface cell: `/`, `/settings/cameras`, `*`. */
function routes(cell) {
  return codeSpans(cell).filter((s) => s === '*' || /^\/[\w\-/]*$/.test(s));
}

/** Backticked repo-relative paths in a modules cell. */
function modules(cell) {
  return codeSpans(cell).filter((s) => /^[\w.-]+\/[\w./-]+\.\w+$/.test(s));
}

const ROW_KEYS = {
  id: 'id',
  surface: 'surface',
  action: 'action',
  'api calls': 'apiCalls',
  backend: 'backend',
  status: 'status',
  evidence: 'evidence',
  modules: 'modules',
  'real tier': 'realTier',
  ruling: 'ruling',
  priority: 'priority',
};

/** Read the inventory's feature rows and its list of modules serving no feature. */
export function parseInventory(markdown) {
  const rows = [];
  const noFeature = [];
  const noFeatureCalls = [];
  let header = null;
  for (const line of markdown.split('\n')) {
    if (!line.trim().startsWith('|')) {
      header = null;
      continue;
    }
    const c = cells(line);
    if (!header) {
      header = c.map((h) => h.toLowerCase());
      continue;
    }
    if (c.every((x) => /^:?-+:?$/.test(x))) continue;
    const get = (name) => c[header.indexOf(name)] ?? '';
    if (header[0] === 'id' && header.includes('status')) {
      const row = {};
      for (const [col, key] of Object.entries(ROW_KEYS)) row[key] = get(col);
      row.routes = routes(row.surface);
      row.apiCalls = apiCalls(row.apiCalls);
      row.modules = modules(row.modules);
      rows.push(row);
    } else if (header[0] === 'module' && header[1] === 'lane') {
      const [module] = codeSpans(get('module'));
      noFeature.push({ module: module ?? get('module'), lane: get('lane') });
    } else if (header[0] === 'request' && header[1] === 'function') {
      const [call] = apiCalls(get('request'));
      if (!call) continue;
      const [fn] = codeSpans(get('function'));
      const [file] = codeSpans(get('file'));
      noFeatureCalls.push({ ...call, fn: fn ?? '', file: file ?? '' });
    }
  }
  return { rows, noFeature, noFeatureCalls };
}

/** The string value of a JSX attribute, or null. */
function attr(element, name) {
  const opening = ts.isJsxElement(element) ? element.openingElement : element;
  for (const a of opening.attributes.properties) {
    if (!ts.isJsxAttribute(a) || a.name.getText() !== name) continue;
    if (!a.initializer) return true;
    if (ts.isStringLiteral(a.initializer)) return a.initializer.text;
  }
  return null;
}

function tagName(node) {
  if (ts.isJsxElement(node)) return node.openingElement.tagName.getText();
  if (ts.isJsxSelfClosingElement(node)) return node.tagName.getText();
  return null;
}

/**
 * The full paths of every `<Route>` in a source file.
 *
 * A child `<Route>` nested directly inside a parent `<Route>` is relative to it
 * (`/settings` + `cameras`), and an `index` route is its parent's path. A nested
 * `<Routes>` inside a `/*` route's `element` starts again from `/`, which is how
 * App.tsx mounts its layout. A `/*` route is a layout wrapper, not a page, so it
 * is not reported.
 */
export function appRoutes(source) {
  const sf = ts.createSourceFile('App.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const out = [];
  const join = (base, p) => (p.startsWith('/') || p === '*' ? p : `${base.replace(/\/$/, '')}/${p}`);
  const visit = (node, base) => {
    if (tagName(node) === 'Route') {
      const p = attr(node, 'path');
      const isIndex = attr(node, 'index') === true;
      const full = isIndex ? base : typeof p === 'string' ? join(base, p) : base;
      if (!full.endsWith('/*')) out.push(full);
      const opening = ts.isJsxElement(node) ? node.openingElement : node;
      // The element prop opens a fresh <Routes>, relative to the root.
      ts.forEachChild(opening, (child) => visit(child, ''));
      if (ts.isJsxElement(node)) for (const child of node.children) visit(child, full);
      return;
    }
    ts.forEachChild(node, (child) => visit(child, base));
  };
  visit(sf, '');
  return [...new Set(out)];
}

/**
 * Every file under `root` an `entry` reaches through imports.
 *
 * Follows `import`, `export … from` and `import()` (ts.preProcessFile reads all
 * three), resolving relative paths and tsconfig `paths` aliases. Packages and
 * non-TypeScript assets end the walk. Paths are root-relative with `/`.
 */
export function reachableFiles({ root, entry }) {
  const compilerOptions = {
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    module: ts.ModuleKind.ESNext,
    allowImportingTsExtensions: true,
    jsx: ts.JsxEmit.ReactJSX,
    baseUrl: root,
    paths: { '@/*': ['./src/*'] },
  };
  const host = ts.createCompilerHost(compilerOptions);
  const seen = new Set();
  const stack = [path.resolve(root, entry)];
  while (stack.length) {
    const file = stack.pop();
    const rel = path.relative(root, file).split(path.sep).join('/');
    if (seen.has(rel)) continue;
    seen.add(rel);
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: a file the TypeScript resolver found under root
    const info = ts.preProcessFile(fs.readFileSync(file, 'utf8'), true, true);
    for (const imp of info.importedFiles) {
      const { resolvedModule } = ts.resolveModuleName(imp.fileName, file, compilerOptions, host);
      if (!resolvedModule || resolvedModule.isExternalLibraryImport) continue;
      const target = resolvedModule.resolvedFileName;
      if (!/\.tsx?$/.test(target) || target.endsWith('.d.ts')) continue;
      if (path.relative(root, target).startsWith('..')) continue;
      stack.push(target);
    }
  }
  return seen;
}

/** What is wrong with one inventory row; empty when nothing is. */
export function rowProblems(row) {
  const problems = [];
  if (!STATUSES.has(row.status))
    problems.push(`${row.id}: status "${row.status}" is not unverified, half-built or leftover`);
  if (!row.evidence.trim()) problems.push(`${row.id}: no evidence`);
  else if (row.status === 'half-built' && !CITE.test(row.evidence))
    problems.push(`${row.id}: half-built evidence cites no file:line`);
  if (row.modules.length === 0) problems.push(`${row.id}: no modules`);
  return problems;
}

/** Repo-relative `path:line` (or `path:a-b`) cites under these roots. */
const REPO_CITE = /\b((?:backend|frontend|ai|docs|scripts|monitoring|docker|config)\/[\w./-]+\.\w+):(\d+)(?:-(\d+))?/g;

/**
 * The `path:line` cites in a row's backend and evidence cells.
 *
 * A range cites its last line, so a range that runs past the end of the file
 * fails the gate's existence check. Shorthand cites (`:44`, after a full cite of
 * the same file) are not read: they carry no path to check.
 */
export function rowCites(row) {
  const out = [];
  for (const cell of [row.backend ?? '', row.evidence ?? '']) {
    for (const m of cell.matchAll(REPO_CITE)) out.push({ file: m[1], line: Number(m[3] ?? m[2]) });
  }
  return out;
}

/**
 * Does an inventory API call account for a scanned client request?
 *
 * Paths compare after the contract scan's normalisation, so a parameter matches
 * by position whatever it is named. A WebSocket claim needs a `WS` call. A REST
 * claim whose verb the scan could not see (`method: null`) matches on path
 * alone; otherwise the verbs must agree (`SSE` is a `GET`).
 */
export function callCovers(call, claim) {
  if (normalisePath(call.path) !== normalisePath(claim.path)) return false;
  if (claim.kind === 'ws') return call.method === 'WS';
  if (call.method === 'WS') return false;
  if (!claim.method || !call.method) return true;
  const verb = call.method === 'SSE' ? 'GET' : call.method;
  return verb === claim.method;
}

/** Files a caller chain must not climb through: tests, mocks, stories. */
const NOT_PRODUCTION =
  /\.test\.tsx?$|\.stories\.tsx?$|\/__tests__\/|\/__mocks__\/|\/mocks\/|\/test\/|\/test-utils\//;

/**
 * Who calls a top-level function, up to the route that mounts it.
 *
 * Follows the TypeScript language service's `findReferences` from the function to
 * the top-level declaration enclosing each production reference, then from that
 * declaration in turn, until `src/App.tsx` or a page it lazy-loads. `App.tsx`
 * loads most pages with `lazy(() => import('./…'))`, which `findReferences` does
 * not follow, so reaching one of those files counts as mounted.
 *
 * `mounted: true` means a mounted module *references* the function, not that a
 * control fires it: a hook can build a mutation its only consumer never takes
 * (`useServiceMutations().startService`). Read the last hop before calling a
 * request live.
 */
export function callerChain({ root, file, name }) {
  const configPath = path.join(root, 'tsconfig.json');
  const parsed = ts.getParsedCommandLineOfConfigFile(configPath, {}, {
    ...ts.sys,
    onUnRecoverableConfigFileDiagnostic() {},
  });
  const fileNames = parsed.fileNames;
  const host = {
    getScriptFileNames: () => fileNames,
    getScriptVersion: () => '1',
    getScriptSnapshot: (f) =>
      // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: a file the TypeScript host asks for
      fs.existsSync(f) ? ts.ScriptSnapshot.fromString(fs.readFileSync(f, 'utf8')) : undefined,
    getCurrentDirectory: () => root,
    getCompilationSettings: () => parsed.options,
    getDefaultLibFileName: (o) => ts.getDefaultLibFilePath(o),
    fileExists: ts.sys.fileExists,
    readFile: ts.sys.readFile,
    readDirectory: ts.sys.readDirectory,
    directoryExists: ts.sys.directoryExists,
    getDirectories: ts.sys.getDirectories,
  };
  const service = ts.createLanguageService(host);
  const program = service.getProgram();

  const appFile = path.join(root, 'src/App.tsx');
  const routeFiles = new Set([appFile]);
  // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: root's own App.tsx
  if (fs.existsSync(appFile)) {
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: as above
    for (const m of fs.readFileSync(appFile, 'utf8').matchAll(/import\('(\.[^']+)'\)/g)) {
      routeFiles.add(path.resolve(root, 'src', `${m[1]}.tsx`));
    }
  }

  const declaration = (sf, wanted) => {
    for (const st of sf.statements) {
      if ((ts.isFunctionDeclaration(st) || ts.isClassDeclaration(st)) && st.name?.text === wanted)
        return st.name.getStart();
      if (ts.isVariableStatement(st))
        for (const d of st.declarationList.declarations)
          if (d.name.getText() === wanted) return d.name.getStart();
    }
    return -1;
  };
  const enclosing = (sf, pos) => {
    for (const st of sf.statements) {
      if (pos < st.getStart() || pos >= st.end) continue;
      if ((ts.isFunctionDeclaration(st) || ts.isClassDeclaration(st)) && st.name) return st.name.text;
      if (ts.isVariableStatement(st)) return st.declarationList.declarations[0].name.getText();
      return null;
    }
    return null;
  };

  const lines = [];
  const seen = new Set();
  let mounted = false;
  const walk = (absFile, symbol, depth) => {
    const sf = program.getSourceFile(absFile);
    const pos = sf ? declaration(sf, symbol) : -1;
    if (pos < 0) return;
    for (const group of service.findReferences(absFile, pos) ?? []) {
      for (const ref of group.references) {
        if (ref.isDefinition || NOT_PRODUCTION.test(ref.fileName)) continue;
        const refSf = program.getSourceFile(ref.fileName);
        const encl = refSf && enclosing(refSf, ref.textSpan.start);
        if (!encl) continue;
        const key = `${ref.fileName}#${encl}`;
        if (seen.has(key)) continue;
        seen.add(key);
        lines.push(`${'  '.repeat(depth)}${path.relative(root, ref.fileName)} :: ${encl}`);
        if (routeFiles.has(ref.fileName)) {
          mounted = true;
          continue;
        }
        walk(ref.fileName, encl, depth + 1);
      }
    }
  };
  walk(path.resolve(root, file), name, 0);
  return { mounted, lines };
}
