/**
 * ABTestStats - Tests for aggregate statistics display for A/B test results
 *
 * @see NEM-1256 - Phase 4.3 Implementation
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ABTestStats, { calculateStats } from './ABTestStats';

import type { ABTestResult } from '../../services/api';


// ============================================================================
// Test Data Factories
// ============================================================================

/**
 * Create a mock ABTestResult for testing
 */
function createMockResult(overrides: Partial<ABTestResult> = {}): ABTestResult {
  return {
    eventId: 1,
    originalResult: {
      riskScore: 50,
      riskLevel: 'medium',
      reasoning: 'Original reasoning',
      processingTimeMs: 100,
    },
    modifiedResult: {
      riskScore: 40,
      riskLevel: 'low',
      reasoning: 'Modified reasoning',
      processingTimeMs: 120,
    },
    scoreDelta: -10,
    ...overrides,
  };
}

// ============================================================================
// calculateStats Tests
// ============================================================================

describe('calculateStats', () => {
  it('returns zeros for empty array', () => {
    const stats = calculateStats([]);

    expect(stats.totalTests).toBe(0);
    expect(stats.avgScoreDelta).toBe(0);
    expect(stats.improvementRate).toBe(0);
    expect(stats.regressionRate).toBe(0);
    expect(stats.neutralRate).toBe(0);
    expect(stats.avgOriginalScore).toBe(0);
    expect(stats.avgModifiedScore).toBe(0);
    expect(stats.consistency).toBe(0);
  });

  it('computes correct avgScoreDelta', () => {
    const results = [
      createMockResult({ scoreDelta: -10 }),
      createMockResult({ scoreDelta: -20 }),
      createMockResult({ scoreDelta: 5 }),
    ];

    const stats = calculateStats(results);

    // Average of -10, -20, 5 = -25/3 = -8.33...
    expect(stats.avgScoreDelta).toBeCloseTo(-8.33, 1);
  });

  it('computes correct improvementRate', () => {
    // improvementRate: % where scoreDelta < -5
    const results = [
      createMockResult({ scoreDelta: -10 }), // improvement (< -5)
      createMockResult({ scoreDelta: -20 }), // improvement (< -5)
      createMockResult({ scoreDelta: 0 }), // neutral
      createMockResult({ scoreDelta: 10 }), // regression
    ];

    const stats = calculateStats(results);

    // 2 out of 4 are improvements = 50%
    expect(stats.improvementRate).toBe(50);
  });

  it('computes correct consistency', () => {
    // consistency: % of tests matching majority direction
    // Direction: improvement (delta < -5), regression (delta > 5), neutral (|delta| <= 5)
    const results = [
      createMockResult({ scoreDelta: -10 }), // improvement
      createMockResult({ scoreDelta: -15 }), // improvement
      createMockResult({ scoreDelta: -8 }), // improvement (majority)
      createMockResult({ scoreDelta: 0 }), // neutral
      createMockResult({ scoreDelta: 10 }), // regression
    ];

    const stats = calculateStats(results);

    // Majority is improvement (3/5), so consistency = 3/5 = 60%
    expect(stats.consistency).toBe(60);
  });
});

// ============================================================================
// ABTestStats Component Tests
// ============================================================================

describe('ABTestStats', () => {
  it('renders improvement/regression/neutral percentages', () => {
    const results = [
      createMockResult({ scoreDelta: -10 }), // improvement
      createMockResult({ scoreDelta: 10 }), // regression
      createMockResult({ scoreDelta: 0 }), // neutral
      createMockResult({ scoreDelta: -8 }), // improvement
    ];

    render(<ABTestStats results={results} />);

    // 2/4 = 50% improvement, 1/4 = 25% regression, 1/4 = 25% neutral
    // Use getAllByText since 50% appears twice (improvement and consistency)
    const fiftyPercent = screen.getAllByText(/50%/);
    expect(fiftyPercent.length).toBeGreaterThan(0);
    // 25% appears twice (regression and neutral)
    const twentyFivePercent = screen.getAllByText(/25%/);
    expect(twentyFivePercent.length).toBe(2);
    // Labels should be present
    expect(screen.getByText(/improvement/i)).toBeInTheDocument();
    expect(screen.getByText(/regression/i)).toBeInTheDocument();
    expect(screen.getByText(/neutral/i)).toBeInTheDocument();
  });

  it('shows average score change', () => {
    const results = [
      createMockResult({ scoreDelta: -10 }),
      createMockResult({ scoreDelta: -20 }),
    ];

    render(<ABTestStats results={results} />);

    // Average is -15
    expect(screen.getByText(/-15/)).toBeInTheDocument();
  });

  it('displays recommendation based on results', () => {
    // Test recommendation with good improvement rate
    const results = [
      createMockResult({ scoreDelta: -10 }),
      createMockResult({ scoreDelta: -15 }),
      createMockResult({ scoreDelta: -12 }),
      createMockResult({ scoreDelta: -8 }),
      createMockResult({ scoreDelta: -20 }),
    ];

    render(<ABTestStats results={results} />);

    // 100% improvement rate with high consistency should show positive recommendation
    expect(screen.getByText(/modified prompt.*reduces false alarms.*recommended/i)).toBeInTheDocument();
  });

  it('handles single result gracefully', () => {
    const results = [createMockResult({ scoreDelta: -10 })];

    render(<ABTestStats results={results} />);

    // Should show "Run more tests" recommendation
    expect(screen.getByText(/run more tests/i)).toBeInTheDocument();
  });

  it('colors improvement green, regression red', () => {
    const results = [
      createMockResult({ scoreDelta: -10 }), // improvement
      createMockResult({ scoreDelta: 10 }), // regression
    ];

    render(<ABTestStats results={results} />);

    // Find elements with appropriate colors
    const improvementElement = screen.getByTestId('improvement-bar');
    const regressionElement = screen.getByTestId('regression-bar');

    // Check for green styling on improvement
    expect(improvementElement).toHaveClass('bg-green-500');
    // Check for red styling on regression
    expect(regressionElement).toHaveClass('bg-red-500');
  });
});
