/**
 * ViewModeContext — Per-browser Easy / Advanced view mode (F4.9 — docs/uplevel/4n-modes.md).
 *
 * Wraps `useLocalStorage<'easy' | 'advanced'>('ui-mode', 'easy')`. A missing or
 * unknown value reads as `'easy'`. Calling `useViewMode()` outside a provider
 * returns `{ mode: 'easy', setMode: () => {} }` so components render in tests
 * without requiring a provider wrapper.
 */

import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';

import { useLocalStorage } from '../hooks/useLocalStorage';

import type { ViewMode } from '../config/surfaces';

export const UI_MODE_STORAGE_KEY = 'ui-mode';

export interface ViewModeContextValue {
  mode: ViewMode;
  setMode: (mode: ViewMode) => void;
}

const DEFAULT_CONTEXT_VALUE: ViewModeContextValue = {
  mode: 'easy',
  setMode: () => {},
};

export const ViewModeContext = createContext<ViewModeContextValue>(DEFAULT_CONTEXT_VALUE);

export interface ViewModeProviderProps {
  children: ReactNode;
  defaultMode?: ViewMode;
}

export function ViewModeProvider({ children, defaultMode = 'easy' }: ViewModeProviderProps) {
  const [rawMode, setStoredMode] = useLocalStorage<ViewMode>(UI_MODE_STORAGE_KEY, defaultMode);
  const mode: ViewMode = rawMode === 'advanced' ? 'advanced' : 'easy';

  const setMode = useCallback(
    (nextMode: ViewMode) => {
      setStoredMode(nextMode === 'advanced' ? 'advanced' : 'easy');
    },
    [setStoredMode]
  );

  const value = useMemo<ViewModeContextValue>(() => ({ mode, setMode }), [mode, setMode]);

  return <ViewModeContext.Provider value={value}>{children}</ViewModeContext.Provider>;
}

export function useViewMode(): ViewModeContextValue {
  return useContext(ViewModeContext);
}
