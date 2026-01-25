/* eslint-disable react-refresh/only-export-components */
/**
 * ThemeContext - React context for theme state management
 *
 * Provides theme state to child components without prop drilling.
 * The context supports 3 modes: light, dark, and system (auto).
 *
 * Features:
 * - Detects system color scheme preference via `prefers-color-scheme`
 * - Persists preference in localStorage
 * - Applies dark class to document element for Tailwind dark mode
 *
 * @module contexts/ThemeContext
 * @see NEM-3609
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from 'react';

import { useLocalStorage } from '../hooks/useLocalStorage';

/**
 * Available theme modes
 */
export type ThemeMode = 'light' | 'dark' | 'system';

/**
 * Resolved theme (the actual theme being displayed)
 */
export type ResolvedTheme = 'light' | 'dark';

/**
 * Shape of the theme context value
 */
export interface ThemeContextValue {
  /** Current theme mode setting (light, dark, or system) */
  mode: ThemeMode;
  /** The resolved theme based on mode and system preference */
  resolvedTheme: ResolvedTheme;
  /** Whether dark mode is active */
  isDark: boolean;
  /** Function to set theme mode */
  setMode: (mode: ThemeMode) => void;
  /** Toggle between light and dark (ignoring system) */
  toggle: () => void;
}

/**
 * The React context for theme
 */
export const ThemeContext = createContext<ThemeContextValue | null>(null);

/**
 * Props for ThemeProvider
 */
export interface ThemeProviderProps {
  /** Child components that will have access to the theme context */
  children: ReactNode;
  /** Default theme mode if not stored */
  defaultMode?: ThemeMode;
  /** Storage key for localStorage persistence */
  storageKey?: string;
}

/** Default storage key for theme preference */
export const THEME_STORAGE_KEY = 'theme-mode';

/**
 * Hook to detect system color scheme preference
 */
function useSystemTheme(): ResolvedTheme {
  // Check system preference on initial render (SSR-safe)
  const getSystemTheme = useCallback((): ResolvedTheme => {
    if (typeof window === 'undefined') {
      return 'dark'; // Default to dark for SSR
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }, []);

  // Store initial system preference
  const systemTheme = useMemo(getSystemTheme, [getSystemTheme]);

  return systemTheme;
}

/**
 * Apply theme class to document element
 */
function applyThemeToDocument(resolvedTheme: ResolvedTheme): void {
  if (typeof window === 'undefined') return;

  const root = document.documentElement;
  if (resolvedTheme === 'dark') {
    root.classList.add('dark');
    root.classList.remove('light');
  } else {
    root.classList.add('light');
    root.classList.remove('dark');
  }
  // Update color-scheme for browser UI elements
  root.style.colorScheme = resolvedTheme;
}

/**
 * Provider component for theme state
 *
 * Wraps child components and provides theme state via context.
 * Uses localStorage for persistence and listens to system
 * color scheme preference changes.
 *
 * @example
 * ```tsx
 * // In your app root:
 * <ThemeProvider>
 *   <App />
 * </ThemeProvider>
 * ```
 */
export function ThemeProvider({
  children,
  defaultMode = 'dark',
  storageKey = THEME_STORAGE_KEY,
}: ThemeProviderProps) {
  const [mode, setModeRaw] = useLocalStorage<ThemeMode>(storageKey, defaultMode);
  const systemTheme = useSystemTheme();

  // Resolve the actual theme based on mode
  const resolvedTheme: ResolvedTheme = useMemo(() => {
    if (mode === 'system') {
      return systemTheme;
    }
    return mode;
  }, [mode, systemTheme]);

  const isDark = resolvedTheme === 'dark';

  // Apply theme class to document when resolved theme changes
  useEffect(() => {
    applyThemeToDocument(resolvedTheme);
  }, [resolvedTheme]);

  // Listen for system preference changes when in system mode
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = (e: MediaQueryListEvent) => {
      if (mode === 'system') {
        applyThemeToDocument(e.matches ? 'dark' : 'light');
      }
    };

    // Modern browsers use addEventListener
    mediaQuery.addEventListener('change', handleChange);

    return () => {
      mediaQuery.removeEventListener('change', handleChange);
    };
  }, [mode]);

  // Wrapper to validate theme mode
  const setMode = useCallback(
    (newMode: ThemeMode) => {
      if (newMode === 'light' || newMode === 'dark' || newMode === 'system') {
        setModeRaw(newMode);
      }
    },
    [setModeRaw]
  );

  // Toggle between light and dark (explicit toggle ignores system)
  const toggle = useCallback(() => {
    setModeRaw(isDark ? 'light' : 'dark');
  }, [isDark, setModeRaw]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      mode,
      resolvedTheme,
      isDark,
      setMode,
      toggle,
    }),
    [mode, resolvedTheme, isDark, setMode, toggle]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

/**
 * Hook to access theme context
 *
 * Must be used within a ThemeProvider.
 *
 * @throws Error if used outside of ThemeProvider
 * @returns Theme context value
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { isDark, toggle, mode, setMode } = useTheme();
 *
 *   return (
 *     <button onClick={toggle}>
 *       Current: {isDark ? 'Dark' : 'Light'}
 *     </button>
 *   );
 * }
 * ```
 */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }

  return context;
}

/**
 * Optional hook to access theme context
 *
 * Returns null if used outside of ThemeProvider instead of throwing.
 * Useful for components that may or may not be wrapped in a provider.
 *
 * @returns Theme context value or null
 */
export function useThemeOptional(): ThemeContextValue | null {
  return useContext(ThemeContext);
}
