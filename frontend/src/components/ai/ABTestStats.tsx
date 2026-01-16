/**
 * ABTestStats - Aggregate statistics display for A/B test results
 *
 * Displays aggregate statistics after running multiple A/B tests including:
 * - Improvement/regression/neutral percentages with progress bars
 * - Average score change
 * - Recommendation based on results
 *
 * Features:
 * - Color-coded segments (green for improvement, red for regression, gray for neutral)
 * - Recommendation logic based on test count and improvement rate
 * - NVIDIA green (#76B900) theme styling
 *
 * @see NEM-1256 - Phase 4.3 Implementation
 */

import { Card } from '@tremor/react';
import { clsx } from 'clsx';
import { ArrowDown, ArrowUp, Minus, TrendingDown, TrendingUp } from 'lucide-react';

import type { ABTestResult } from '../../services/api';
import type React from 'react';

// ============================================================================
// Types
// ============================================================================

export interface ABTestStatsProps {
  /** Array of A/B test results to analyze */
  results: ABTestResult[];
  /** Additional CSS classes */
  className?: string;
}

export interface AggregateStats {
  /** Total number of tests run */
  totalTests: number;
  /** Average score difference (modified - original) */
  avgScoreDelta: number;
  /** Percentage of tests where B scored lower (improvement: scoreDelta < -5) */
  improvementRate: number;
  /** Percentage of tests where B scored higher (regression: scoreDelta > 5) */
  regressionRate: number;
  /** Percentage of tests within +/-5 points (neutral) */
  neutralRate: number;
  /** Average score from original (A) prompt */
  avgOriginalScore: number;
  /** Average score from modified (B) prompt */
  avgModifiedScore: number;
  /** Percentage of tests matching majority direction */
  consistency: number;
}

// ============================================================================
// Statistics Calculation
// ============================================================================

/**
 * Calculate aggregate statistics from A/B test results
 *
 * @param results - Array of ABTestResult objects
 * @returns AggregateStats with computed metrics
 */
// eslint-disable-next-line react-refresh/only-export-components
export function calculateStats(results: ABTestResult[]): AggregateStats {
  if (results.length === 0) {
    return {
      totalTests: 0,
      avgScoreDelta: 0,
      improvementRate: 0,
      regressionRate: 0,
      neutralRate: 0,
      avgOriginalScore: 0,
      avgModifiedScore: 0,
      consistency: 0,
    };
  }

  const totalTests = results.length;

  // Calculate average scores
  const avgOriginalScore =
    results.reduce((sum, r) => sum + r.originalResult.riskScore, 0) / totalTests;
  const avgModifiedScore =
    results.reduce((sum, r) => sum + r.modifiedResult.riskScore, 0) / totalTests;

  // Calculate average delta
  const avgScoreDelta = results.reduce((sum, r) => sum + r.scoreDelta, 0) / totalTests;

  // Count by category
  // improvementRate: % where scoreDelta < -5
  // regressionRate: % where scoreDelta > 5
  // neutralRate: % where |scoreDelta| <= 5
  let improvements = 0;
  let regressions = 0;
  let neutrals = 0;

  for (const result of results) {
    if (result.scoreDelta < -5) {
      improvements++;
    } else if (result.scoreDelta > 5) {
      regressions++;
    } else {
      neutrals++;
    }
  }

  const improvementRate = (improvements / totalTests) * 100;
  const regressionRate = (regressions / totalTests) * 100;
  const neutralRate = (neutrals / totalTests) * 100;

  // Calculate consistency: % of tests matching majority direction
  const maxCount = Math.max(improvements, regressions, neutrals);
  const consistency = (maxCount / totalTests) * 100;

  return {
    totalTests,
    avgScoreDelta,
    improvementRate,
    regressionRate,
    neutralRate,
    avgOriginalScore,
    avgModifiedScore,
    consistency,
  };
}

// ============================================================================
// Recommendation Logic
// ============================================================================

/**
 * Generate recommendation text based on statistics
 *
 * @param stats - Calculated aggregate statistics
 * @returns Recommendation string
 */
function getRecommendation(stats: AggregateStats): string {
  // Not enough tests
  if (stats.totalTests < 3) {
    return 'Run more tests for a reliable recommendation';
  }

  // Strong improvement with high consistency
  if (stats.improvementRate >= 60 && stats.consistency >= 70) {
    return 'Modified prompt (B) reduces false alarms - recommended';
  }

  // Strong regression
  if (stats.regressionRate >= 60) {
    return 'Modified prompt (B) increases scores - not recommended';
  }

  // Mixed results
  return 'Results are mixed - consider testing on more events';
}

// ============================================================================
// Sub-components
// ============================================================================

interface StatBarProps {
  /** Label for the stat */
  label: string;
  /** Percentage value (0-100) */
  value: number;
  /** Color class for the bar */
  colorClass: string;
  /** Test ID for the bar */
  testId: string;
  /** Icon component */
  Icon: typeof ArrowDown;
}

/**
 * StatBar - Single stat row with label, percentage, and colored bar
 */
function StatBar({ label, value, colorClass, testId, Icon }: StatBarProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 text-gray-400">
          <Icon className="h-4 w-4" />
          {label}
        </span>
        <span className="font-medium text-white">{Math.round(value)}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-gray-800">
        <div
          className={clsx('h-2 rounded-full transition-all', colorClass)}
          style={{ width: `${value}%` }}
          data-testid={testId}
        />
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ABTestStats - Aggregate statistics display for A/B test results
 */
export default function ABTestStats({ results, className }: ABTestStatsProps): React.ReactElement {
  const stats = calculateStats(results);
  const recommendation = getRecommendation(stats);

  // Format average delta with sign
  const formattedDelta =
    stats.avgScoreDelta >= 0
      ? `+${Math.round(stats.avgScoreDelta)}`
      : `${Math.round(stats.avgScoreDelta)}`;

  // Determine delta color
  const deltaColorClass =
    stats.avgScoreDelta < -5
      ? 'text-green-400'
      : stats.avgScoreDelta > 5
        ? 'text-red-400'
        : 'text-gray-400';

  // Determine recommendation styling
  const isPositiveRecommendation =
    recommendation.includes('recommended') && !recommendation.includes('not recommended');
  const isNegativeRecommendation = recommendation.includes('not recommended');

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="ab-test-stats"
    >
      {/* Header */}
      <div className="mb-4 border-b border-gray-800 pb-4">
        <h3 className="text-lg font-semibold text-white">Test Statistics</h3>
        <p className="mt-1 text-sm text-gray-400">
          {stats.totalTests} test{stats.totalTests !== 1 ? 's' : ''} completed
        </p>
      </div>

      {/* Main Stats */}
      <div className="space-y-4">
        {/* Average Score Change */}
        <div className="flex items-center justify-between rounded-lg border border-gray-700 bg-black/30 p-4">
          <div className="flex items-center gap-3">
            {stats.avgScoreDelta < -5 ? (
              <TrendingDown className="h-6 w-6 text-green-400" />
            ) : stats.avgScoreDelta > 5 ? (
              <TrendingUp className="h-6 w-6 text-red-400" />
            ) : (
              <Minus className="h-6 w-6 text-gray-400" />
            )}
            <div>
              <div className="text-sm text-gray-400">Average Score Change</div>
              <div className={clsx('text-2xl font-bold', deltaColorClass)}>{formattedDelta}</div>
            </div>
          </div>
        </div>

        {/* Rate Breakdown */}
        <div className="space-y-3">
          <StatBar
            label="Improvement"
            value={stats.improvementRate}
            colorClass="bg-green-500"
            testId="improvement-bar"
            Icon={ArrowDown}
          />
          <StatBar
            label="Regression"
            value={stats.regressionRate}
            colorClass="bg-red-500"
            testId="regression-bar"
            Icon={ArrowUp}
          />
          <StatBar
            label="Neutral"
            value={stats.neutralRate}
            colorClass="bg-gray-500"
            testId="neutral-bar"
            Icon={Minus}
          />
        </div>

        {/* Consistency */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-400">Consistency</span>
          <span className="font-medium text-white">{Math.round(stats.consistency)}%</span>
        </div>

        {/* Recommendation */}
        <div
          className={clsx(
            'mt-4 rounded-lg border p-4',
            isPositiveRecommendation
              ? 'border-green-800 bg-green-900/20'
              : isNegativeRecommendation
                ? 'border-red-800 bg-red-900/20'
                : 'border-gray-700 bg-gray-800/50'
          )}
        >
          <div className="text-sm font-medium text-gray-300">Recommendation</div>
          <div
            className={clsx(
              'mt-1 text-sm',
              isPositiveRecommendation
                ? 'text-green-400'
                : isNegativeRecommendation
                  ? 'text-red-400'
                  : 'text-gray-400'
            )}
          >
            {recommendation}
          </div>
        </div>
      </div>
    </Card>
  );
}
