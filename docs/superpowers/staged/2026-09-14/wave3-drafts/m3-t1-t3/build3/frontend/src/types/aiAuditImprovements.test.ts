/**
 * Tests for AI Audit Improvements type utilities
 *
 * @see types/aiAuditImprovements.ts
 */

import { describe, it, expect } from 'vitest';

import {
  CONSISTENCY_THRESHOLD,
  IMPROVEMENT_CATEGORIES,
  CATEGORY_LABELS,
  CATEGORY_DESCRIPTIONS,
  hasAnyImprovements,
  countTotalImprovements,
  getImprovementCounts,
  flattenImprovements,
  createImprovementsSummary,
  determineEvaluationQuality,
  createConsistencyCheck,
  getCategoryLabel,
  getCategoryDescription,
} from './aiAuditImprovements';

import type { PromptImprovements } from './aiAudit';

// ============================================================================
// Test Data Factories
// ============================================================================

function createEmptyImprovements(): PromptImprovements {
  return {
    missing_context: [],
    confusing_sections: [],
    unused_data: [],
    format_suggestions: [],
    model_gaps: [],
  };
}

function createSampleImprovements(): PromptImprovements {
  return {
    missing_context: ['Context item 1', 'Context item 2'],
    confusing_sections: ['Section 1'],
    unused_data: [],
    format_suggestions: ['Format suggestion 1', 'Format suggestion 2', 'Format suggestion 3'],
    model_gaps: ['Gap 1'],
  };
}

// ============================================================================
// Constants Tests
// ============================================================================

describe('Constants', () => {
  describe('CONSISTENCY_THRESHOLD', () => {
    it('should be defined as 10', () => {
      expect(CONSISTENCY_THRESHOLD).toBe(10);
    });
  });

  describe('IMPROVEMENT_CATEGORIES', () => {
    it('should contain all five categories', () => {
      expect(IMPROVEMENT_CATEGORIES).toHaveLength(5);
      expect(IMPROVEMENT_CATEGORIES).toContain('missing_context');
      expect(IMPROVEMENT_CATEGORIES).toContain('confusing_sections');
      expect(IMPROVEMENT_CATEGORIES).toContain('unused_data');
      expect(IMPROVEMENT_CATEGORIES).toContain('format_suggestions');
      expect(IMPROVEMENT_CATEGORIES).toContain('model_gaps');
    });
  });

  describe('CATEGORY_LABELS', () => {
    it('should have labels for all categories', () => {
      for (const category of IMPROVEMENT_CATEGORIES) {
        expect(CATEGORY_LABELS[category]).toBeDefined();
        expect(typeof CATEGORY_LABELS[category]).toBe('string');
      }
    });

    it('should have human-readable labels', () => {
      expect(CATEGORY_LABELS.missing_context).toBe('Missing Context');
      expect(CATEGORY_LABELS.confusing_sections).toBe('Confusing Sections');
    });
  });

  describe('CATEGORY_DESCRIPTIONS', () => {
    it('should have descriptions for all categories', () => {
      for (const category of IMPROVEMENT_CATEGORIES) {
        expect(CATEGORY_DESCRIPTIONS[category]).toBeDefined();
        expect(typeof CATEGORY_DESCRIPTIONS[category]).toBe('string');
      }
    });

    it('should have meaningful descriptions', () => {
      expect(CATEGORY_DESCRIPTIONS.missing_context.toLowerCase()).toContain('context');
      expect(CATEGORY_DESCRIPTIONS.model_gaps.toLowerCase()).toContain('gap');
    });
  });
});

// ============================================================================
// Helper Function Tests
// ============================================================================

describe('hasAnyImprovements', () => {
  it('should return false for empty improvements', () => {
    const improvements = createEmptyImprovements();
    expect(hasAnyImprovements(improvements)).toBe(false);
  });

  it('should return true when any category has improvements', () => {
    const improvements = createEmptyImprovements();
    improvements.missing_context = ['Item 1'];
    expect(hasAnyImprovements(improvements)).toBe(true);
  });

  it('should return true for sample improvements', () => {
    const improvements = createSampleImprovements();
    expect(hasAnyImprovements(improvements)).toBe(true);
  });
});

describe('countTotalImprovements', () => {
  it('should return 0 for empty improvements', () => {
    const improvements = createEmptyImprovements();
    expect(countTotalImprovements(improvements)).toBe(0);
  });

  it('should count all improvements across categories', () => {
    const improvements = createSampleImprovements();
    // 2 + 1 + 0 + 3 + 1 = 7
    expect(countTotalImprovements(improvements)).toBe(7);
  });

  it('should handle single category with items', () => {
    const improvements = createEmptyImprovements();
    improvements.model_gaps = ['Gap 1', 'Gap 2', 'Gap 3'];
    expect(countTotalImprovements(improvements)).toBe(3);
  });
});

describe('getImprovementCounts', () => {
  it('should return zero counts for empty improvements', () => {
    const improvements = createEmptyImprovements();
    const counts = getImprovementCounts(improvements);

    for (const category of IMPROVEMENT_CATEGORIES) {
      expect(counts[category]).toBe(0);
    }
  });

  it('should return correct counts for each category', () => {
    const improvements = createSampleImprovements();
    const counts = getImprovementCounts(improvements);

    expect(counts.missing_context).toBe(2);
    expect(counts.confusing_sections).toBe(1);
    expect(counts.unused_data).toBe(0);
    expect(counts.format_suggestions).toBe(3);
    expect(counts.model_gaps).toBe(1);
  });
});

describe('flattenImprovements', () => {
  it('should return empty array for empty improvements', () => {
    const improvements = createEmptyImprovements();
    const items = flattenImprovements(improvements);
    expect(items).toHaveLength(0);
  });

  it('should flatten all improvements into array', () => {
    const improvements = createSampleImprovements();
    const items = flattenImprovements(improvements);

    // Should have 7 total items
    expect(items).toHaveLength(7);
  });

  it('should include category and description for each item', () => {
    const improvements = createEmptyImprovements();
    improvements.missing_context = ['Test item'];
    const items = flattenImprovements(improvements);

    expect(items).toHaveLength(1);
    expect(items[0].category).toBe('missing_context');
    expect(items[0].suggestion).toBe('Test item');
    expect(items[0].categoryDescription).toBe(CATEGORY_DESCRIPTIONS.missing_context);
  });

  it('should preserve order by category', () => {
    const improvements = createSampleImprovements();
    const items = flattenImprovements(improvements);

    // First items should be from missing_context (first in IMPROVEMENT_CATEGORIES)
    expect(items[0].category).toBe('missing_context');
    expect(items[1].category).toBe('missing_context');
    expect(items[2].category).toBe('confusing_sections');
  });
});

describe('createImprovementsSummary', () => {
  it('should create summary for empty improvements', () => {
    const improvements = createEmptyImprovements();
    const summary = createImprovementsSummary(improvements);

    expect(summary.totalCount).toBe(0);
    expect(summary.hasImprovements).toBe(false);
    expect(summary.items).toHaveLength(0);
  });

  it('should create complete summary for sample improvements', () => {
    const improvements = createSampleImprovements();
    const summary = createImprovementsSummary(improvements);

    expect(summary.totalCount).toBe(7);
    expect(summary.hasImprovements).toBe(true);
    expect(summary.items).toHaveLength(7);
    expect(summary.countByCategory.missing_context).toBe(2);
    expect(summary.countByCategory.format_suggestions).toBe(3);
  });
});

describe('determineEvaluationQuality', () => {
  it('should return not_evaluated when not fully evaluated', () => {
    expect(determineEvaluationQuality(false, null)).toBe('not_evaluated');
    expect(determineEvaluationQuality(false, 0)).toBe('not_evaluated');
    expect(determineEvaluationQuality(false, 5)).toBe('not_evaluated');
  });

  it('should return good when fully evaluated with small diff', () => {
    expect(determineEvaluationQuality(true, null)).toBe('good');
    expect(determineEvaluationQuality(true, 0)).toBe('good');
    expect(determineEvaluationQuality(true, 5)).toBe('good');
    expect(determineEvaluationQuality(true, CONSISTENCY_THRESHOLD)).toBe('good');
  });

  it('should return needs_improvement when diff exceeds threshold', () => {
    expect(determineEvaluationQuality(true, CONSISTENCY_THRESHOLD + 1)).toBe('needs_improvement');
    expect(determineEvaluationQuality(true, 20)).toBe('needs_improvement');
    expect(determineEvaluationQuality(true, -15)).toBe('needs_improvement');
  });
});

describe('createConsistencyCheck', () => {
  it('should create check with null values', () => {
    const check = createConsistencyCheck(null, null);

    expect(check.riskScore).toBeNull();
    expect(check.diff).toBeNull();
    expect(check.passed).toBe(true); // null diff = passed
  });

  it('should create check with passing diff', () => {
    const check = createConsistencyCheck(75, 5);

    expect(check.riskScore).toBe(75);
    expect(check.diff).toBe(5);
    expect(check.passed).toBe(true);
  });

  it('should create check with failing diff', () => {
    const check = createConsistencyCheck(80, 15);

    expect(check.riskScore).toBe(80);
    expect(check.diff).toBe(15);
    expect(check.passed).toBe(false);
  });

  it('should handle negative diff values', () => {
    const check = createConsistencyCheck(70, -12);

    expect(check.diff).toBe(-12);
    expect(check.passed).toBe(false); // abs(-12) > 10
  });

  it('should pass at exactly threshold', () => {
    const check = createConsistencyCheck(75, CONSISTENCY_THRESHOLD);

    expect(check.passed).toBe(true);
  });
});

describe('getCategoryLabel', () => {
  it('should return correct labels', () => {
    expect(getCategoryLabel('missing_context')).toBe('Missing Context');
    expect(getCategoryLabel('model_gaps')).toBe('Model Gaps');
  });
});

describe('getCategoryDescription', () => {
  it('should return correct descriptions', () => {
    const desc = getCategoryDescription('missing_context');
    expect(desc).toBe('Context that was missing from the prompt');
  });
});
