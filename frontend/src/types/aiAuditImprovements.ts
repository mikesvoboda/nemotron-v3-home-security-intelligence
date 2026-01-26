/**
 * TypeScript types and utilities for AI Audit self-evaluation improvements
 *
 * This module provides typed interfaces for the self-evaluation critique and
 * improvement data exposed by the EventAudit model, along with helper functions
 * for processing and displaying this data.
 *
 * @see backend/models/event_audit.py for source of truth
 * @see backend/api/schemas/ai_audit.py for API schema definitions
 * @module types/aiAuditImprovements
 */

import type { PromptImprovements } from './aiAudit';

// ============================================================================
// Constants
// ============================================================================

/**
 * Threshold for consistency check pass/fail determination.
 * If consistency_diff exceeds this value, the check is considered failed.
 */
export const CONSISTENCY_THRESHOLD = 10;

/**
 * Categories of improvements that can be suggested.
 */
export type ImprovementCategory =
  | 'missing_context'
  | 'confusing_sections'
  | 'unused_data'
  | 'format_suggestions'
  | 'model_gaps';

/**
 * All improvement categories in display order.
 */
export const IMPROVEMENT_CATEGORIES: readonly ImprovementCategory[] = [
  'missing_context',
  'confusing_sections',
  'unused_data',
  'format_suggestions',
  'model_gaps',
] as const;

/**
 * Human-readable labels for improvement categories.
 */
export const CATEGORY_LABELS: Record<ImprovementCategory, string> = {
  missing_context: 'Missing Context',
  confusing_sections: 'Confusing Sections',
  unused_data: 'Unused Data',
  format_suggestions: 'Format Suggestions',
  model_gaps: 'Model Gaps',
};

/**
 * Descriptions for each improvement category.
 */
export const CATEGORY_DESCRIPTIONS: Record<ImprovementCategory, string> = {
  missing_context: 'Context that was missing from the prompt',
  confusing_sections: 'Sections of the prompt that were confusing or unclear',
  unused_data: 'Data that was provided but not utilized',
  format_suggestions: 'Suggestions for improving the prompt format',
  model_gaps: 'Gaps in model coverage or capabilities',
};

// ============================================================================
// Interfaces
// ============================================================================

/**
 * A single improvement item with its category.
 */
export interface ImprovementItem {
  /** The category this improvement belongs to */
  category: ImprovementCategory;
  /** The improvement suggestion text */
  suggestion: string;
  /** Human-readable description of the category */
  categoryDescription: string;
}

/**
 * Consistency check results from self-evaluation.
 */
export interface ConsistencyCheck {
  /** Risk score from re-evaluation */
  riskScore: number | null;
  /** Difference between original and re-evaluated risk scores */
  diff: number | null;
  /** Whether the consistency check passed (diff <= CONSISTENCY_THRESHOLD) */
  passed: boolean;
}

/**
 * Summary of all improvements with counts.
 */
export interface ImprovementsSummary {
  /** Total count of all improvements */
  totalCount: number;
  /** Count of improvements by category */
  countByCategory: Record<ImprovementCategory, number>;
  /** Whether any improvements exist */
  hasImprovements: boolean;
  /** All improvement items flattened */
  items: ImprovementItem[];
}

/**
 * Self-evaluation data extracted from an EventAudit.
 */
export interface SelfEvaluation {
  /** Text critique from self-evaluation */
  critique: string | null;
  /** Prompt improvement suggestions */
  improvements: PromptImprovements;
  /** Consistency check results */
  consistency: ConsistencyCheck;
  /** Whether the audit is fully evaluated */
  isFullyEvaluated: boolean;
}

/**
 * Processed self-evaluation data with computed summaries.
 */
export interface ProcessedSelfEvaluation extends SelfEvaluation {
  /** Processed improvements summary */
  improvementsSummary: ImprovementsSummary;
  /** Evaluation quality indicator */
  evaluationQuality: 'good' | 'needs_improvement' | 'not_evaluated';
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Check if any improvements exist in the PromptImprovements object.
 *
 * @param improvements - The improvements object to check
 * @returns True if any category has at least one improvement
 *
 * @example
 * ```ts
 * const hasAny = hasAnyImprovements(audit.improvements);
 * if (hasAny) {
 *   // Show improvements section
 * }
 * ```
 */
export function hasAnyImprovements(improvements: PromptImprovements): boolean {
  return IMPROVEMENT_CATEGORIES.some(
    (category) => improvements[category] && improvements[category].length > 0
  );
}

/**
 * Count the total number of improvements across all categories.
 *
 * @param improvements - The improvements object to count
 * @returns Total count of all improvements
 *
 * @example
 * ```ts
 * const total = countTotalImprovements(audit.improvements);
 * console.log(`${total} improvements found`);
 * ```
 */
export function countTotalImprovements(improvements: PromptImprovements): number {
  return IMPROVEMENT_CATEGORIES.reduce((sum, category) => {
    return sum + (improvements[category]?.length ?? 0);
  }, 0);
}

/**
 * Get the count of improvements for each category.
 *
 * @param improvements - The improvements object to analyze
 * @returns Record mapping each category to its count
 *
 * @example
 * ```ts
 * const counts = getImprovementCounts(audit.improvements);
 * console.log(`Missing context: ${counts.missing_context}`);
 * ```
 */
export function getImprovementCounts(
  improvements: PromptImprovements
): Record<ImprovementCategory, number> {
  return IMPROVEMENT_CATEGORIES.reduce(
    (counts, category) => {
      counts[category] = improvements[category]?.length ?? 0;
      return counts;
    },
    {} as Record<ImprovementCategory, number>
  );
}

/**
 * Flatten all improvements into a single array with category information.
 *
 * @param improvements - The improvements object to flatten
 * @returns Array of improvement items with their categories
 *
 * @example
 * ```ts
 * const items = flattenImprovements(audit.improvements);
 * items.forEach(item => {
 *   console.log(`[${item.category}] ${item.suggestion}`);
 * });
 * ```
 */
export function flattenImprovements(improvements: PromptImprovements): ImprovementItem[] {
  const items: ImprovementItem[] = [];

  for (const category of IMPROVEMENT_CATEGORIES) {
    const suggestions = improvements[category];
    if (suggestions && suggestions.length > 0) {
      for (const suggestion of suggestions) {
        items.push({
          category,
          suggestion,
          categoryDescription: CATEGORY_DESCRIPTIONS[category],
        });
      }
    }
  }

  return items;
}

/**
 * Create a complete summary of improvements.
 *
 * @param improvements - The improvements object to summarize
 * @returns Complete summary with counts and flattened items
 *
 * @example
 * ```ts
 * const summary = createImprovementsSummary(audit.improvements);
 * if (summary.hasImprovements) {
 *   console.log(`Found ${summary.totalCount} improvements`);
 *   console.log(`Missing context: ${summary.countByCategory.missing_context}`);
 * }
 * ```
 */
export function createImprovementsSummary(improvements: PromptImprovements): ImprovementsSummary {
  const items = flattenImprovements(improvements);
  const countByCategory = getImprovementCounts(improvements);
  const totalCount = items.length;

  return {
    totalCount,
    countByCategory,
    hasImprovements: totalCount > 0,
    items,
  };
}

/**
 * Determine the evaluation quality based on evaluation status and consistency.
 *
 * @param isFullyEvaluated - Whether the audit is fully evaluated
 * @param consistencyDiff - The consistency diff value (can be null)
 * @returns Quality indicator: 'good', 'needs_improvement', or 'not_evaluated'
 *
 * @example
 * ```ts
 * const quality = determineEvaluationQuality(audit.is_fully_evaluated, audit.consistency_diff);
 * if (quality === 'good') {
 *   // Show green indicator
 * }
 * ```
 */
export function determineEvaluationQuality(
  isFullyEvaluated: boolean,
  consistencyDiff: number | null
): 'good' | 'needs_improvement' | 'not_evaluated' {
  if (!isFullyEvaluated) {
    return 'not_evaluated';
  }

  if (consistencyDiff !== null && Math.abs(consistencyDiff) > CONSISTENCY_THRESHOLD) {
    return 'needs_improvement';
  }

  return 'good';
}

/**
 * Create a ConsistencyCheck object from raw audit data.
 *
 * @param consistencyRiskScore - The re-evaluated risk score
 * @param consistencyDiff - The difference from original score
 * @returns ConsistencyCheck object with pass/fail determination
 *
 * @example
 * ```ts
 * const consistency = createConsistencyCheck(
 *   audit.consistency_risk_score,
 *   audit.consistency_diff
 * );
 * if (!consistency.passed) {
 *   console.log('Consistency check failed');
 * }
 * ```
 */
export function createConsistencyCheck(
  consistencyRiskScore: number | null,
  consistencyDiff: number | null
): ConsistencyCheck {
  const passed =
    consistencyDiff === null || Math.abs(consistencyDiff) <= CONSISTENCY_THRESHOLD;

  return {
    riskScore: consistencyRiskScore,
    diff: consistencyDiff,
    passed,
  };
}

/**
 * Get the label for a given improvement category.
 *
 * @param category - The improvement category
 * @returns Human-readable label for the category
 *
 * @example
 * ```ts
 * const label = getCategoryLabel('missing_context');
 * // Returns: 'Missing Context'
 * ```
 */
export function getCategoryLabel(category: ImprovementCategory): string {
  return CATEGORY_LABELS[category];
}

/**
 * Get the description for a given improvement category.
 *
 * @param category - The improvement category
 * @returns Description of what the category represents
 *
 * @example
 * ```ts
 * const description = getCategoryDescription('missing_context');
 * // Returns: 'Context that was missing from the prompt'
 * ```
 */
export function getCategoryDescription(category: ImprovementCategory): string {
  return CATEGORY_DESCRIPTIONS[category];
}
