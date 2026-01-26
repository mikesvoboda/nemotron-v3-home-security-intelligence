/**
 * Hook for accessing EventAudit self-evaluation improvements
 *
 * This module provides a convenience hook that wraps useAIAuditEventQuery
 * and exposes structured access to self-evaluation critique and improvement data.
 *
 * @see types/aiAuditImprovements.ts for type definitions
 * @see hooks/useAIAuditQueries.ts for the underlying query hook
 * @module hooks/useEventAuditImprovements
 */

import { useMemo } from 'react';

import { useAIAuditEventQuery, type UseAIAuditEventQueryOptions } from './useAIAuditQueries';
import {
  type ImprovementCategory,
  type ImprovementItem,
  type ImprovementsSummary,
  type ConsistencyCheck,
  type SelfEvaluation,
  type ProcessedSelfEvaluation,
  createImprovementsSummary,
  createConsistencyCheck,
  determineEvaluationQuality,
} from '../types/aiAuditImprovements';

import type { PromptImprovements } from '../types/aiAudit';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for the useEventAuditImprovements hook.
 * Extends UseAIAuditEventQueryOptions with same configuration options.
 */
export type UseEventAuditImprovementsOptions = UseAIAuditEventQueryOptions;

/**
 * Return type for the useEventAuditImprovements hook.
 */
export interface UseEventAuditImprovementsReturn {
  /** Whether the query is currently loading */
  isLoading: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Whether audit data is available */
  hasAuditData: boolean;
  /** Raw self-evaluation data */
  selfEvaluation: SelfEvaluation | null;
  /** Processed self-evaluation with computed summaries */
  processed: ProcessedSelfEvaluation | null;
  /** Improvements summary with counts and flattened items */
  improvements: ImprovementsSummary | null;
  /** Self-evaluation critique text */
  critique: string | null;
  /** Consistency check results */
  consistency: ConsistencyCheck | null;
  /** Whether the audit is fully evaluated */
  isFullyEvaluated: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;

  // Convenience methods
  /** Get improvements for a specific category */
  getImprovementsByCategory: (category: ImprovementCategory) => string[];
  /** Get all improvements sorted by priority (categories with more items first) */
  getHighPriorityImprovements: () => ImprovementItem[];
  /** Check if a specific category has any improvements */
  hasCategoryImprovements: (category: ImprovementCategory) => boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Create empty improvements object with all categories as empty arrays.
 */
function createEmptyImprovements(): PromptImprovements {
  return {
    missing_context: [],
    confusing_sections: [],
    unused_data: [],
    format_suggestions: [],
    model_gaps: [],
  };
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook to access EventAudit self-evaluation improvements with structured helpers.
 *
 * This hook wraps useAIAuditEventQuery and provides:
 * - Structured access to self-evaluation critique and improvements
 * - Computed summaries and counts
 * - Convenience methods for filtering and accessing improvement data
 * - Consistency check results with pass/fail determination
 *
 * @param eventId - The event ID to fetch audit data for, or undefined to disable
 * @param options - Configuration options (same as useAIAuditEventQuery)
 * @returns Structured self-evaluation data and helper methods
 *
 * @example
 * ```tsx
 * function EventImprovementsPanel({ eventId }: { eventId: number }) {
 *   const {
 *     isLoading,
 *     error,
 *     hasAuditData,
 *     critique,
 *     improvements,
 *     consistency,
 *     isFullyEvaluated,
 *     getImprovementsByCategory,
 *   } = useEventAuditImprovements(eventId);
 *
 *   if (isLoading) return <Spinner />;
 *   if (error) return <Error message={error.message} />;
 *   if (!hasAuditData) return <NoData />;
 *
 *   return (
 *     <div>
 *       {critique && (
 *         <section>
 *           <h3>Self-Critique</h3>
 *           <p>{critique}</p>
 *         </section>
 *       )}
 *
 *       {improvements?.hasImprovements && (
 *         <section>
 *           <h3>Improvements ({improvements.totalCount})</h3>
 *           <ul>
 *             {getImprovementsByCategory('missing_context').map((item, i) => (
 *               <li key={i}>{item}</li>
 *             ))}
 *           </ul>
 *         </section>
 *       )}
 *
 *       {consistency && (
 *         <section>
 *           <h3>Consistency Check</h3>
 *           <p>Status: {consistency.passed ? 'Passed' : 'Failed'}</p>
 *           {consistency.diff !== null && (
 *             <p>Score Difference: {consistency.diff}</p>
 *           )}
 *         </section>
 *       )}
 *     </div>
 *   );
 * }
 * ```
 */
export function useEventAuditImprovements(
  eventId: number | undefined,
  options: UseEventAuditImprovementsOptions = {}
): UseEventAuditImprovementsReturn {
  const { data: audit, isLoading, error, refetch } = useAIAuditEventQuery(eventId, options);

  // Memoize the processed data to avoid recomputing on every render
  const processedData = useMemo(() => {
    if (!audit) {
      return null;
    }

    const improvements = audit.improvements ?? createEmptyImprovements();
    const consistency = createConsistencyCheck(
      audit.consistency_risk_score,
      audit.consistency_diff
    );
    const improvementsSummary = createImprovementsSummary(improvements);
    const evaluationQuality = determineEvaluationQuality(
      audit.is_fully_evaluated,
      audit.consistency_diff
    );

    const selfEvaluation: SelfEvaluation = {
      critique: audit.self_eval_critique,
      improvements,
      consistency,
      isFullyEvaluated: audit.is_fully_evaluated,
    };

    const processed: ProcessedSelfEvaluation = {
      ...selfEvaluation,
      improvementsSummary,
      evaluationQuality,
    };

    return {
      selfEvaluation,
      processed,
      improvementsSummary,
      consistency,
    };
  }, [audit]);

  // Convenience method: get improvements for a specific category
  const getImprovementsByCategory = useMemo(
    () => (category: ImprovementCategory): string[] => {
      if (!audit?.improvements) return [];
      return audit.improvements[category] ?? [];
    },
    [audit?.improvements]
  );

  // Convenience method: get high priority improvements (categories with most items first)
  const getHighPriorityImprovements = useMemo(
    () => (): ImprovementItem[] => {
      if (!processedData?.improvementsSummary) return [];

      // Sort items by category count (most items in category = higher priority)
      const { items, countByCategory } = processedData.improvementsSummary;
      return [...items].sort((a, b) => {
        const countA = countByCategory[a.category];
        const countB = countByCategory[b.category];
        return countB - countA;
      });
    },
    [processedData?.improvementsSummary]
  );

  // Convenience method: check if a category has improvements
  const hasCategoryImprovements = useMemo(
    () => (category: ImprovementCategory): boolean => {
      if (!audit?.improvements) return false;
      const items = audit.improvements[category];
      return items !== undefined && items.length > 0;
    },
    [audit?.improvements]
  );

  return {
    isLoading,
    error,
    hasAuditData: audit !== undefined,
    selfEvaluation: processedData?.selfEvaluation ?? null,
    processed: processedData?.processed ?? null,
    improvements: processedData?.improvementsSummary ?? null,
    critique: audit?.self_eval_critique ?? null,
    consistency: processedData?.consistency ?? null,
    isFullyEvaluated: audit?.is_fully_evaluated ?? false,
    refetch,
    getImprovementsByCategory,
    getHighPriorityImprovements,
    hasCategoryImprovements,
  };
}

// Re-export types for convenience
export type {
  ImprovementCategory,
  ImprovementItem,
  ImprovementsSummary,
  ConsistencyCheck,
  SelfEvaluation,
  ProcessedSelfEvaluation,
};

// Re-export constants for convenience
export { IMPROVEMENT_CATEGORIES, CONSISTENCY_THRESHOLD } from '../types/aiAuditImprovements';
