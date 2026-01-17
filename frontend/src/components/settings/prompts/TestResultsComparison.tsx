/**
 * TestResultsComparison - Side-by-side comparison of A/B test results
 *
 * Displays results from testing the current vs modified prompt configuration,
 * showing risk scores, inference time, and other metrics.
 *
 * @see NEM-2698 - Implement prompt A/B testing UI with real inference comparison
 */

import { Card, Badge, ProgressBar } from '@tremor/react';
import { ArrowUp, ArrowDown, Minus, Clock, Zap } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

/**
 * Test result data for a single configuration
 */
export interface TestResult {
  /** Risk score computed by the AI model (0-100) */
  riskScore: number;
  /** Risk level string (low, medium, high, critical) */
  riskLevel: string;
  /** AI model reasoning text */
  reasoning?: string;
  /** Brief summary */
  summary?: string;
  /** Processing time in milliseconds */
  processingTimeMs: number;
  /** Tokens used in the request */
  tokensUsed?: number;
}

export interface TestResultsComparisonProps {
  /** Result from the current/baseline configuration */
  currentResult: TestResult | null;
  /** Result from the modified configuration */
  modifiedResult: TestResult | null;
  /** Current config version number */
  currentVersion?: number;
  /** Whether results are still loading */
  isLoading?: boolean;
  /** Error message if test failed */
  error?: string | null;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get badge color for risk level
 */
function getRiskBadgeColor(riskLevel: string): 'gray' | 'green' | 'yellow' | 'orange' | 'red' {
  switch (riskLevel?.toLowerCase()) {
    case 'low':
      return 'green';
    case 'medium':
      return 'yellow';
    case 'high':
      return 'orange';
    case 'critical':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Get progress bar color for risk score
 */
function getRiskProgressColor(score: number): 'green' | 'yellow' | 'orange' | 'red' {
  if (score < 25) return 'green';
  if (score < 50) return 'yellow';
  if (score < 75) return 'orange';
  return 'red';
}

/**
 * Format milliseconds for display
 */
function formatTime(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ============================================================================
// Sub-Components
// ============================================================================

interface ResultCardProps {
  title: string;
  result: TestResult | null;
  isLoading?: boolean;
  variant: 'current' | 'modified';
}

function ResultCard({ title, result, isLoading = false, variant }: ResultCardProps) {
  const borderColor = variant === 'current' ? 'border-gray-600' : 'border-blue-600';
  const headerBg = variant === 'current' ? 'bg-gray-800' : 'bg-blue-900/30';

  if (isLoading) {
    return (
      <Card className={`border ${borderColor} bg-gray-900/50`}>
        <div className={`-m-6 mb-4 p-3 ${headerBg}`}>
          <h4 className="text-sm font-medium text-white">{title}</h4>
        </div>
        <div className="flex h-40 items-center justify-center">
          <div className="text-center text-gray-400">
            <div className="mx-auto mb-2 h-6 w-6 animate-spin rounded-full border-2 border-gray-600 border-t-blue-500" />
            Running inference...
          </div>
        </div>
      </Card>
    );
  }

  if (!result) {
    return (
      <Card className={`border ${borderColor} bg-gray-900/50`}>
        <div className={`-m-6 mb-4 p-3 ${headerBg}`}>
          <h4 className="text-sm font-medium text-white">{title}</h4>
        </div>
        <div className="flex h-40 items-center justify-center text-gray-400">
          No results yet
        </div>
      </Card>
    );
  }

  return (
    <Card className={`border ${borderColor} bg-gray-900/50`} data-testid={`result-card-${variant}`}>
      <div className={`-m-6 mb-4 p-3 ${headerBg}`}>
        <h4 className="text-sm font-medium text-white">{title}</h4>
      </div>

      {/* Risk Score */}
      <div className="mb-4">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-sm text-gray-400">Risk Score</span>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold text-white">{result.riskScore}</span>
            <Badge color={getRiskBadgeColor(result.riskLevel)} size="sm">
              {result.riskLevel.charAt(0).toUpperCase() + result.riskLevel.slice(1)}
            </Badge>
          </div>
        </div>
        <ProgressBar
          value={result.riskScore}
          color={getRiskProgressColor(result.riskScore)}
          className="mt-2"
        />
      </div>

      {/* Metrics */}
      <div className="mb-4 flex gap-4 text-sm">
        <div className="flex items-center gap-1 text-gray-400">
          <Clock className="h-4 w-4" />
          {formatTime(result.processingTimeMs)}
        </div>
        {result.tokensUsed !== undefined && result.tokensUsed > 0 && (
          <div className="flex items-center gap-1 text-gray-400">
            <Zap className="h-4 w-4" />
            {result.tokensUsed} tokens
          </div>
        )}
      </div>

      {/* Summary */}
      {result.summary && (
        <div className="mb-3">
          <h5 className="mb-1 text-xs font-medium uppercase text-gray-500">Summary</h5>
          <p className="text-sm text-gray-300">{result.summary}</p>
        </div>
      )}

      {/* Reasoning (collapsed by default, could expand) */}
      {result.reasoning && (
        <div>
          <h5 className="mb-1 text-xs font-medium uppercase text-gray-500">Reasoning</h5>
          <p className="line-clamp-3 text-sm text-gray-400">{result.reasoning}</p>
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Component
// ============================================================================

/**
 * Side-by-side comparison of A/B test results.
 *
 * Shows current config results vs modified config results with
 * delta indicators for key metrics.
 *
 * @example
 * ```tsx
 * <TestResultsComparison
 *   currentResult={currentResult}
 *   modifiedResult={modifiedResult}
 *   currentVersion={3}
 * />
 * ```
 */
export default function TestResultsComparison({
  currentResult,
  modifiedResult,
  currentVersion,
  isLoading = false,
  error = null,
}: TestResultsComparisonProps) {
  // Calculate delta if both results are available
  const scoreDelta =
    currentResult && modifiedResult
      ? modifiedResult.riskScore - currentResult.riskScore
      : null;

  const timeDelta =
    currentResult && modifiedResult
      ? modifiedResult.processingTimeMs - currentResult.processingTimeMs
      : null;

  return (
    <div className="space-y-4" data-testid="test-results-comparison">
      {/* Error State */}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-900/20 p-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Results Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        <ResultCard
          title={`Current Config${currentVersion ? ` (v${currentVersion})` : ''}`}
          result={currentResult}
          isLoading={isLoading}
          variant="current"
        />
        <ResultCard
          title="Modified Config"
          result={modifiedResult}
          isLoading={isLoading}
          variant="modified"
        />
      </div>

      {/* Delta Summary */}
      {scoreDelta !== null && timeDelta !== null && (
        <Card className="border-gray-700 bg-gray-900/50" data-testid="delta-summary">
          <h4 className="mb-3 text-sm font-medium text-white">Comparison Summary</h4>
          <div className="flex flex-wrap gap-6">
            {/* Risk Score Delta */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Risk Score:</span>
              <div className="flex items-center gap-1">
                {scoreDelta > 0 ? (
                  <>
                    <ArrowUp className="h-4 w-4 text-red-400" />
                    <span className="font-medium text-red-400">+{scoreDelta}</span>
                  </>
                ) : scoreDelta < 0 ? (
                  <>
                    <ArrowDown className="h-4 w-4 text-green-400" />
                    <span className="font-medium text-green-400">{scoreDelta}</span>
                  </>
                ) : (
                  <>
                    <Minus className="h-4 w-4 text-gray-400" />
                    <span className="font-medium text-gray-400">No change</span>
                  </>
                )}
              </div>
            </div>

            {/* Processing Time Delta */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Inference Time:</span>
              <div className="flex items-center gap-1">
                {timeDelta > 100 ? (
                  <>
                    <ArrowUp className="h-4 w-4 text-yellow-400" />
                    <span className="font-medium text-yellow-400">+{formatTime(timeDelta)}</span>
                  </>
                ) : timeDelta < -100 ? (
                  <>
                    <ArrowDown className="h-4 w-4 text-green-400" />
                    <span className="font-medium text-green-400">{formatTime(Math.abs(timeDelta))}</span>
                  </>
                ) : (
                  <>
                    <Minus className="h-4 w-4 text-gray-400" />
                    <span className="font-medium text-gray-400">Similar</span>
                  </>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
