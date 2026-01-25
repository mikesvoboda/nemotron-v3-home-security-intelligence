/* eslint-disable react-refresh/only-export-components */
/**
 * DebugModeContext - React context for sharing debug mode state
 *
 * Provides debug mode state to child components without prop drilling.
 * The context tracks:
 * - debugMode: whether debug mode is currently active
 * - setDebugMode: function to toggle debug mode
 * - isDebugAvailable: whether the backend has debug enabled
 *
 * When isDebugAvailable is false, debugMode will always be false regardless
 * of localStorage state.
 *
 * @module contexts/DebugModeContext
 */

import { createContext, useContext, useMemo, type ReactNode } from 'react';

import { useLocalStorage } from '../hooks/useLocalStorage';
import { useSystemConfigQuery } from '../hooks/useSystemConfigQuery';

/**
 * Shape of the debug mode context value
 */
export interface DebugModeContextValue {
  /** Whether debug mode is currently active */
  debugMode: boolean;
  /** Function to update debug mode state */
  setDebugMode: (enabled: boolean) => void;
  /** Whether debug mode is available (backend has DEBUG=true) */
  isDebugAvailable: boolean;
}

/**
 * The React context for debug mode
 */
export const DebugModeContext = createContext<DebugModeContextValue | null>(null);

/**
 * Props for DebugModeProvider
 */
export interface DebugModeProviderProps {
  /** Child components that will have access to the debug mode context */
  children: ReactNode;
}

/**
 * Provider component for debug mode state
 *
 * Wraps child components and provides debug mode state via context.
 * Uses localStorage for persistence and the system config query
 * to determine if debug mode is available.
 *
 * @example
 * ```tsx
 * // In your app root or page component:
 * <DebugModeProvider>
 *   <SystemMonitoringPage />
 * </DebugModeProvider>
 * ```
 */
export function DebugModeProvider({ children }: DebugModeProviderProps) {
  const { debugEnabled, isLoading } = useSystemConfigQuery();
  const [storedDebugMode, setStoredDebugMode] = useLocalStorage('system-debug-mode', false);

  // Determine if debug is available (backend has it enabled and not loading)
  const isDebugAvailable = !isLoading && debugEnabled;

  // Debug mode is only active if it's available AND the user has it toggled on
  // When not available, always return false
  const debugMode = isDebugAvailable && storedDebugMode;

  const value = useMemo<DebugModeContextValue>(
    () => ({
      debugMode,
      setDebugMode: setStoredDebugMode,
      isDebugAvailable,
    }),
    [debugMode, setStoredDebugMode, isDebugAvailable]
  );

  return <DebugModeContext.Provider value={value}>{children}</DebugModeContext.Provider>;
}

/**
 * Hook to access debug mode context
 *
 * Must be used within a DebugModeProvider.
 *
 * @throws Error if used outside of DebugModeProvider
 * @returns Debug mode context value
 *
 * @example
 * ```tsx
 * function MyDebugPanel() {
 *   const { debugMode, isDebugAvailable } = useDebugMode();
 *
 *   if (!debugMode) return null;
 *
 *   return <div>Debug information here...</div>;
 * }
 * ```
 */
export function useDebugMode(): DebugModeContextValue {
  const context = useContext(DebugModeContext);

  if (!context) {
    throw new Error('useDebugMode must be used within a DebugModeProvider');
  }

  return context;
}
