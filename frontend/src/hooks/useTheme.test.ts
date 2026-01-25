/**
 * Tests for useTheme hook
 *
 * Verifies that the hook re-exports correctly from ThemeContext.
 *
 * @see NEM-3609
 */

import { describe, expect, it } from 'vitest';

import {
  useTheme,
  useThemeOptional,
  type ThemeContextValue,
  type ThemeMode,
  type ResolvedTheme,
} from './useTheme';

describe('useTheme hook exports', () => {
  it('exports useTheme function', () => {
    expect(useTheme).toBeDefined();
    expect(typeof useTheme).toBe('function');
  });

  it('exports useThemeOptional function', () => {
    expect(useThemeOptional).toBeDefined();
    expect(typeof useThemeOptional).toBe('function');
  });

  it('exports ThemeContextValue type', () => {
    // Type-level test - TypeScript compiler will fail if type is not exported
    const typeCheck: ThemeContextValue = {
      mode: 'dark',
      resolvedTheme: 'dark',
      isDark: true,
      setMode: () => {},
      toggle: () => {},
    };
    expect(typeCheck.mode).toBe('dark');
  });

  it('exports ThemeMode type', () => {
    // Type-level test
    const modes: ThemeMode[] = ['light', 'dark', 'system'];
    expect(modes).toHaveLength(3);
  });

  it('exports ResolvedTheme type', () => {
    // Type-level test
    const themes: ResolvedTheme[] = ['light', 'dark'];
    expect(themes).toHaveLength(2);
  });
});
