/**
 * useTheme - Hook for accessing theme context
 *
 * Re-exports the useTheme hook from ThemeContext for convenience.
 * This allows importing from hooks directory following project conventions.
 *
 * @module hooks/useTheme
 * @see NEM-3609
 */

export { useTheme, useThemeOptional } from '../contexts/ThemeContext';
export type { ThemeContextValue, ThemeMode, ResolvedTheme } from '../contexts/ThemeContext';
