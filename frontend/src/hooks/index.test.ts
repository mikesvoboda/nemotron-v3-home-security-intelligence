/**
 * Tests for the hooks barrel export (frontend/src/hooks/index.ts).
 *
 * Mirrors the stores/index.test.ts precedent: the coverage gate requires a
 * test beside any changed hooks/*.ts, and a barrel's job is exactly the
 * property this checks — that named exports survive renames and that the
 * F1.2 verdict-engine additions are reachable from 'src/hooks' (the import
 * site Layout.tsx uses). Focused on the additions plus a smoke assertion
 * that the barrel itself evaluates; the hooks' behavior is covered by their
 * own .test files.
 */

import { describe, expect, it } from 'vitest';

import * as hooks from './index';

describe('hooks/index', () => {
  it('evaluates and exports the full hook surface', () => {
    expect(Object.keys(hooks).length).toBeGreaterThan(50);
  });

  describe('verdict-engine status exports (F1.2)', () => {
    it('exports the hook as both named and default', () => {
      expect(typeof hooks.useVerdictEngineStatus).toBe('function');
      expect(hooks.useVerdictEngineStatusDefault).toBe(hooks.useVerdictEngineStatus);
    });
  });
});
