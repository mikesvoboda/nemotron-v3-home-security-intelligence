/**
 * SeverityContext - Context provider for severity thresholds and risk level classification.
 *
 * This context provides app-wide access to severity configuration fetched from the backend.
 * It wraps the useSeverityConfig hook to provide a consistent interface and prevent
 * prop drilling for components that need to classify risk scores.
 *
 * Benefits:
 * - Single source of truth for severity thresholds across the app
 * - Automatic fallback to default thresholds when API unavailable
 * - getRiskLevel function uses dynamic thresholds from backend
 * - Reduces re-renders compared to prop drilling
 *
 * @module contexts/SeverityContext
 */

import React, { createContext, useContext, useMemo, type ReactNode } from 'react';

import { useSeverityConfig } from '../hooks/useSeverityConfig';
import {
  DEFAULT_SEVERITY_DEFINITIONS,
  DEFAULT_SEVERITY_THRESHOLDS,
} from '../types/severity';

import type { SeverityDefinition, SeverityLevel, SeverityThresholds } from '../types/severity';

// ============================================================================
// Types
// ============================================================================

/**
 * Severity data available through the context.
 */
export interface SeverityContextData {
  /** Current severity thresholds (falls back to defaults if not loaded) */
  thresholds: SeverityThresholds;
  /** Severity definitions with labels, colors, and descriptions */
  definitions: SeverityDefinition[];
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /**
   * Convert a risk score to a risk level using the current thresholds.
   * This function respects dynamically configured thresholds from the backend.
   * @param score - Risk score between 0-100
   * @returns The risk level ('low', 'medium', 'high', or 'critical')
   * @throws Error if score is outside 0-100 range
   */
  getRiskLevel: (score: number) => SeverityLevel;
  /**
   * Get the definition for a specific severity level.
   * @param level - The severity level to look up
   * @returns The severity definition, or undefined if not found
   */
  getDefinition: (level: SeverityLevel) => SeverityDefinition | undefined;
  /**
   * Get the color for a specific severity level.
   * @param level - The severity level
   * @returns Hex color code for the level
   */
  getColor: (level: SeverityLevel) => string;
}

/**
 * Props for the SeverityProvider component.
 */
export interface SeverityProviderProps {
  children: ReactNode;
  /**
   * Whether to enable data fetching.
   * @default true
   */
  enabled?: boolean;
}

// ============================================================================
// Context
// ============================================================================

/**
 * Context for severity data. Do not use directly - use the useSeverity hook.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const SeverityContext = createContext<SeverityContextData | null>(null);

SeverityContext.displayName = 'SeverityContext';

// ============================================================================
// Provider Component
// ============================================================================

/**
 * Provider component that fetches and manages severity configuration.
 *
 * This provider should be placed high in your component tree, typically
 * inside the QueryClientProvider. It fetches severity thresholds from
 * the backend and provides them to all descendant components.
 *
 * @example
 * ```tsx
 * // In App.tsx or main.tsx
 * import { SeverityProvider } from './contexts/SeverityContext';
 *
 * function App() {
 *   return (
 *     <QueryClientProvider client={queryClient}>
 *       <SeverityProvider>
 *         <YourApp />
 *       </SeverityProvider>
 *     </QueryClientProvider>
 *   );
 * }
 * ```
 */
export function SeverityProvider({
  children,
  enabled = true,
}: SeverityProviderProps): React.ReactElement {
  const {
    thresholds,
    definitions,
    isLoading,
    isRefetching,
    error,
    refetch,
    getRiskLevel,
  } = useSeverityConfig({ enabled });

  // Helper to get definition by level
  const getDefinition = useMemo(
    () => (level: SeverityLevel): SeverityDefinition | undefined => {
      return definitions.find((def) => def.severity === level);
    },
    [definitions]
  );

  // Helper to get color by level
  const getColor = useMemo(
    () => (level: SeverityLevel): string => {
      const definition = definitions.find((def) => def.severity === level);
      return definition?.color ?? '#6b7280'; // gray-500 fallback
    },
    [definitions]
  );

  // Memoized context value - only changes when severity data changes
  const value = useMemo<SeverityContextData>(
    () => ({
      thresholds,
      definitions,
      isLoading,
      isRefetching,
      error,
      refetch,
      getRiskLevel,
      getDefinition,
      getColor,
    }),
    [
      thresholds,
      definitions,
      isLoading,
      isRefetching,
      error,
      refetch,
      getRiskLevel,
      getDefinition,
      getColor,
    ]
  );

  return <SeverityContext.Provider value={value}>{children}</SeverityContext.Provider>;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to access severity data from the SeverityContext.
 *
 * Must be used within a SeverityProvider. Throws an error if used outside
 * the provider to help catch usage errors early.
 *
 * @throws Error if used outside of SeverityProvider
 *
 * @example
 * ```tsx
 * function EventCard({ risk_score }: { risk_score: number }) {
 *   const { getRiskLevel, getColor } = useSeverity();
 *   const level = getRiskLevel(risk_score);
 *   const color = getColor(level);
 *
 *   return (
 *     <div style={{ borderColor: color }}>
 *       Risk: {level}
 *     </div>
 *   );
 * }
 * ```
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useSeverity(): SeverityContextData {
  const context = useContext(SeverityContext);
  if (!context) {
    throw new Error('useSeverity must be used within a SeverityProvider');
  }
  return context;
}

/**
 * Hook to optionally access severity data. Returns null if outside provider.
 *
 * Use this when the component may be rendered outside the provider context,
 * or when you want to handle the absence of context gracefully.
 *
 * @example
 * ```tsx
 * function OptionalRiskBadge({ score }: { score: number }) {
 *   const severity = useSeverityOptional();
 *
 *   // Fall back to static behavior if no context
 *   if (!severity) {
 *     return <span>Score: {score}</span>;
 *   }
 *
 *   const level = severity.getRiskLevel(score);
 *   return <span>{level}</span>;
 * }
 * ```
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useSeverityOptional(): SeverityContextData | null {
  return useContext(SeverityContext);
}

/**
 * Default severity context value for use in tests or when rendering
 * outside the provider with known fallback behavior.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const DEFAULT_SEVERITY_CONTEXT: SeverityContextData = {
  thresholds: DEFAULT_SEVERITY_THRESHOLDS,
  definitions: DEFAULT_SEVERITY_DEFINITIONS,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: () => Promise.resolve(undefined),
  getRiskLevel: (score: number): SeverityLevel => {
    if (score < 0 || score > 100) {
      throw new Error('Risk score must be between 0 and 100');
    }
    if (score <= DEFAULT_SEVERITY_THRESHOLDS.low_max) return 'low';
    if (score <= DEFAULT_SEVERITY_THRESHOLDS.medium_max) return 'medium';
    if (score <= DEFAULT_SEVERITY_THRESHOLDS.high_max) return 'high';
    return 'critical';
  },
  getDefinition: (level: SeverityLevel) =>
    DEFAULT_SEVERITY_DEFINITIONS.find((def) => def.severity === level),
  getColor: (level: SeverityLevel) =>
    DEFAULT_SEVERITY_DEFINITIONS.find((def) => def.severity === level)?.color ?? '#6b7280',
};

export default SeverityProvider;
