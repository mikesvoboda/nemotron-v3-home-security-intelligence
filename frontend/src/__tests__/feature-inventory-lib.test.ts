/**
 * Unit tests for scripts/feature-inventory-lib.mjs, the reader behind the F2.2
 * feature-inventory gate (src/__tests__/feature-inventory.test.ts).
 *
 * Each block feeds the library a small source tree or a small inventory and
 * asserts what it reads back, so a regression in the reader shows up here with a
 * readable fixture rather than as a confusing coverage diff in the gate. The
 * library is loaded through a computed `import()` for the same reason the
 * endpoint-contract test gives: tsconfig has no `allowJs`, so a static import of
 * an `.mjs` would fail `npm run typecheck`.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

import { afterEach, beforeAll, describe, expect, it } from 'vitest';

interface ApiCall {
  method: string | null;
  path: string;
}

interface Row {
  id: string;
  surface: string;
  routes: string[];
  action: string;
  apiCalls: ApiCall[];
  backend: string;
  status: string;
  evidence: string;
  modules: string[];
  realTier: string;
  ruling: string;
  priority: string;
}

interface NoFeatureModule {
  module: string;
  lane: string;
}

interface Inventory {
  rows: Row[];
  noFeature: NoFeatureModule[];
}

interface Lib {
  parseInventory: (markdown: string) => Inventory;
  appRoutes: (source: string) => string[];
  reachableFiles: (options: { root: string; entry: string }) => Set<string>;
  rowProblems: (row: Row) => string[];
  callCovers: (call: ApiCall, claim: { kind: string; method: string | null; path: string }) => boolean;
}

let lib: Lib;

beforeAll(async () => {
  const libUrl = pathToFileURL(
    path.resolve(process.cwd(), 'scripts/feature-inventory-lib.mjs')
  ).href;
  lib = (await import(libUrl)) as Lib;
});

const tmpDirs: string[] = [];

function tree(files: Record<string, string>) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'feature-inventory-'));
  tmpDirs.push(root);
  for (const [rel, body] of Object.entries(files)) {
    const p = path.join(root, rel);
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: path under this test's own mkdtemp
    fs.mkdirSync(path.dirname(p), { recursive: true });
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- SAFE: path under this test's own mkdtemp
    fs.writeFileSync(p, body);
  }
  return root;
}

afterEach(() => {
  while (tmpDirs.length) fs.rmSync(tmpDirs.pop()!, { recursive: true, force: true });
});

const HEADER =
  '| id | surface | action | API calls | backend | status | evidence | modules | real tier | ruling | priority |\n' +
  '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n';

describe('parseInventory', () => {
  it('reads every row of every feature table, with its routes and API calls', () => {
    const md =
      '# Feature inventory\n\n## Dashboard\n\n' +
      HEADER +
      '| F-001 | Dashboard `/` | view stats | `GET /api/events/stats`<br>`WS /ws/events` | `events.py:10` | unverified | renders on load | `src/pages/A.tsx`, `backend/api/routes/events.py` | — | | |\n' +
      '\n## Settings\n\n' +
      HEADER +
      '| F-002 | Cameras `/settings/cameras` | list | `GET /api/cameras/{camera_id}` | — | half-built | `x.py:4` returns `[]` | `src/B.tsx` | — | | |\n';
    const inv = lib.parseInventory(md);
    expect(inv.rows.map((r) => r.id)).toEqual(['F-001', 'F-002']);
    expect(inv.rows[0].routes).toEqual(['/']);
    expect(inv.rows[1].routes).toEqual(['/settings/cameras']);
    expect(inv.rows[0].apiCalls).toEqual([
      { method: 'GET', path: '/api/events/stats' },
      { method: 'WS', path: '/ws/events' },
    ]);
    expect(inv.rows[0].modules).toEqual(['src/pages/A.tsx', 'backend/api/routes/events.py']);
    expect(inv.rows[1].status).toBe('half-built');
  });

  it('reads the modules-serving-no-feature table separately from feature rows', () => {
    const md =
      HEADER +
      '| F-001 | A `/` | a | — | — | unverified | ok | `src/A.tsx` | — | | |\n\n' +
      '## Modules serving no feature\n\n' +
      '| module | lane | lines | last meaningful commit | notes |\n| --- | --- | --- | --- | --- |\n' +
      '| `src/dead/X.tsx` | frontend | 10 | abc1234 | unreachable |\n';
    const inv = lib.parseInventory(md);
    expect(inv.rows).toHaveLength(1);
    expect(inv.noFeature).toEqual([{ module: 'src/dead/X.tsx', lane: 'frontend' }]);
  });

  it('does not split a cell on a pipe escaped inside backticks', () => {
    const md =
      HEADER +
      '| F-001 | A `/` | filter `a\\|b` | — | — | unverified | ok | `src/A.tsx` | — | | |\n';
    const inv = lib.parseInventory(md);
    expect(inv.rows[0].action).toBe('filter `a|b`');
    expect(inv.rows[0].status).toBe('unverified');
  });
});

describe('appRoutes', () => {
  it('joins nested child routes onto their parent and resolves index routes', () => {
    const src = `
      export default function App() {
        return (
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/*" element={
              <Layout>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/settings" element={<Settings />}>
                    <Route index element={<Navigate to="cameras" />} />
                    <Route path="cameras" element={<Cameras />} />
                  </Route>
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Layout>
            } />
          </Routes>
        );
      }`;
    expect(lib.appRoutes(src).sort()).toEqual(
      ['*', '/', '/login', '/settings', '/settings/cameras'].sort()
    );
  });
});

describe('reachableFiles', () => {
  it('follows static, dynamic, re-export and alias imports, and nothing else', () => {
    const root = tree({
      'src/main.tsx': "import App from './App';\nimport './styles.css';\n",
      'src/App.tsx':
        "import { a } from '@/lib/a';\nconst Lazy = lazy(() => import('./pages/Lazy'));\nexport default a;\n",
      'src/lib/a.ts': "export { b as a } from './b';\n",
      'src/lib/b.ts': 'export const b = 1;\n',
      'src/pages/Lazy.tsx': 'export default 1;\n',
      'src/dead/Dead.tsx': "import { b } from '../lib/b';\nexport default b;\n",
    });
    const reached = lib.reachableFiles({ root, entry: 'src/main.tsx' });
    expect([...reached].sort()).toEqual(
      ['src/App.tsx', 'src/lib/a.ts', 'src/lib/b.ts', 'src/main.tsx', 'src/pages/Lazy.tsx'].sort()
    );
  });
});

describe('rowProblems', () => {
  const base: Row = {
    id: 'F-001',
    surface: 'A `/`',
    routes: ['/'],
    action: 'a',
    apiCalls: [],
    backend: '—',
    status: 'unverified',
    evidence: 'renders',
    modules: ['src/A.tsx'],
    realTier: '—',
    ruling: '',
    priority: '',
  };

  it('accepts a complete row', () => {
    expect(lib.rowProblems(base)).toEqual([]);
  });

  it('rejects an unknown status', () => {
    expect(lib.rowProblems({ ...base, status: 'works?' })).toEqual([
      'F-001: status "works?" is not unverified, half-built or leftover',
    ]);
  });

  it('demands a file:line cite for a half-built row', () => {
    expect(lib.rowProblems({ ...base, status: 'half-built', evidence: 'the backend is a stub' })).toEqual([
      'F-001: half-built evidence cites no file:line',
    ]);
    expect(
      lib.rowProblems({ ...base, status: 'half-built', evidence: '`backend/x.py:12` returns `[]`' })
    ).toEqual([]);
  });

  it('rejects empty evidence and a row with no modules', () => {
    expect(lib.rowProblems({ ...base, evidence: '', modules: [] })).toEqual([
      'F-001: no evidence',
      'F-001: no modules',
    ]);
  });
});

describe('callCovers', () => {
  it('matches a path parameter by position, whatever its name', () => {
    expect(
      lib.callCovers(
        { method: 'GET', path: '/api/cameras/{camera_id}' },
        { kind: 'rest', method: 'GET', path: '/api/cameras/{}' }
      )
    ).toBe(true);
  });

  it('requires the verb when the claim knows it', () => {
    expect(
      lib.callCovers(
        { method: 'GET', path: '/api/zones/{id}' },
        { kind: 'rest', method: 'DELETE', path: '/api/zones/{}' }
      )
    ).toBe(false);
  });

  it('matches a claim with an opaque verb on path alone', () => {
    expect(
      lib.callCovers(
        { method: 'PATCH', path: '/api/zones/{id}' },
        { kind: 'rest', method: null, path: '/api/zones/{}' }
      )
    ).toBe(true);
  });

  it('matches a WebSocket claim only with a WS call', () => {
    expect(
      lib.callCovers({ method: 'WS', path: '/ws/events' }, { kind: 'ws', method: null, path: '/ws/events' })
    ).toBe(true);
    expect(
      lib.callCovers({ method: 'GET', path: '/ws/events' }, { kind: 'ws', method: null, path: '/ws/events' })
    ).toBe(false);
  });
});
