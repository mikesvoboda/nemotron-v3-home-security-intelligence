/**
 * PromptABTest - Split-view A/B testing component for prompt comparison
 *
 * Displays a side-by-side comparison of two prompts (original A vs modified B)
 * showing test results on real events with delta indicators.
 *
 * Features:
 * - Side-by-side panels for original and modified prompts
 * - Color-coded delta indicators (green for improvement, red for regression)
 * - Run on random events or promote B as default
 * - Loading state with disabled buttons
 * - NVIDIA green (#76B900) theme styling
 *
 * @see NEM-1254 - Implementation task
 */

import { Card } from '@tremor/react';
import { clsx } from 'clsx';
import { ChevronDown, ChevronUp, Loader2, Minus, Play, Sparkles } from 'lucide-react';
import { useState } from 'react';

import type { ABTestResult } from '../../services/api';

// ============================================================================
// Types
// ============================================================================

export interface PromptABTestProps {
  /** The original (A) prompt */
  originalPrompt: string;
  /** The modified (B) prompt */
  modifiedPrompt: string;
  /** Test results for completed tests */
  results: ABTestResult[];
  /** Whether a test is currently running */
  isRunning: boolean;
  /** Callback to run test on specific event */
  onRunTest: (eventId: number) => void;
  /** Callback to run test on N random events */
  onRunRandomTests: (count: number) => void;
  /** Callback to promote B as new default */
  onPromoteB: () => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Sub-components
// ============================================================================

interface ResultPanelProps {
  /** Panel label (A or B) */
  label: string;
  /** Risk score (0-100) */
  riskScore: number;
  /** Risk level (low, medium, high, critical) */
  riskLevel: string;
  /** LLM reasoning text */
  reasoning: string;
  /** Processing time in milliseconds */
  processingTimeMs: number;
}

/**
 * ResultPanel - Shows risk score with color coding, risk level badge, expandable reasoning
 */
function ResultPanel({ label, riskScore, riskLevel, reasoning, processingTimeMs }: ResultPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Get color based on risk level
  const getRiskColor = () => {
    switch (riskLevel.toLowerCase()) {
      case 'critical':
        return 'text-red-400 bg-red-900/30 border-red-800';
      case 'high':
        return 'text-orange-400 bg-orange-900/30 border-orange-800';
      case 'medium':
        return 'text-yellow-400 bg-yellow-900/30 border-yellow-800';
      case 'low':
      default:
        return 'text-green-400 bg-green-900/30 border-green-800';
    }
  };

  return (
    <div className="space-y-3">
      {/* Risk Score */}
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-gray-400">Risk Score:</span>
        <span className="text-2xl font-bold text-white">{riskScore}</span>
      </div>

      {/* Risk Level Badge */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-400">Level:</span>
        <span
          className={clsx(
            'rounded-full border px-3 py-1 text-sm font-medium',
            getRiskColor()
          )}
        >
          {riskLevel}
        </span>
      </div>

      {/* Processing Time */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Processing:</span>
        <span>{processingTimeMs}ms</span>
      </div>

      {/* Expandable Reasoning */}
      <div className="border-t border-gray-700 pt-2">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex w-full items-center justify-between text-sm text-gray-400 hover:text-white"
          aria-expanded={isExpanded}
          aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${label} reasoning`}
        >
          <span>Reasoning</span>
          {isExpanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>
        {isExpanded && (
          <p className="mt-2 text-sm text-gray-300">{reasoning}</p>
        )}
      </div>
    </div>
  );
}

interface DeltaIndicatorProps {
  /** Score difference: modified - original */
  delta: number;
}

/**
 * DeltaIndicator - Shows score difference with color coding
 * - Green if B is lower (improvement - less false alarms)
 * - Red if B is higher (regression - more false alarms)
 * - Gray/neutral if within +/-5
 */
function DeltaIndicator({ delta }: DeltaIndicatorProps) {
  // Determine styling based on delta value
  const getDeltaStyle = () => {
    if (delta <= -5) {
      // B is lower - improvement (green)
      return {
        bgClass: 'bg-green-900/30 border-green-800',
        textClass: 'text-green-400',
        Icon: ChevronDown,
        label: 'B is less alarming',
      };
    } else if (delta >= 5) {
      // B is higher - regression (red)
      return {
        bgClass: 'bg-red-900/30 border-red-800',
        textClass: 'text-red-400',
        Icon: ChevronUp,
        label: 'B is more alarming',
      };
    } else {
      // Within threshold - neutral (gray)
      return {
        bgClass: 'bg-gray-800/50 border-gray-700',
        textClass: 'text-gray-400',
        Icon: Minus,
        label: 'No significant difference',
      };
    }
  };

  const style = getDeltaStyle();
  const formattedDelta = delta >= 0 ? `+${delta}` : `${delta}`;

  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg border p-3',
        style.bgClass
      )}
      data-testid="delta-indicator"
    >
      <div className="flex items-center gap-2">
        <style.Icon className={clsx('h-5 w-5', style.textClass)} />
        <span className={clsx('text-sm font-medium', style.textClass)}>
          Score Delta: {formattedDelta}
        </span>
      </div>
      <span className="text-xs text-gray-500">({style.label})</span>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * PromptABTest - Split-view A/B testing interface
 */
export default function PromptABTest({
  originalPrompt: _originalPrompt,
  modifiedPrompt: _modifiedPrompt,
  results,
  isRunning,
  onRunTest: _onRunTest,
  onRunRandomTests,
  onPromoteB,
  className,
}: PromptABTestProps) {
  // Note: originalPrompt, modifiedPrompt, and onRunTest are included in the interface
  // for full A/B testing functionality but not currently displayed/used in this view.
  // They will be used when adding prompt preview panels and single-event test buttons.
  void _originalPrompt;
  void _modifiedPrompt;
  void _onRunTest;
  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="prompt-ab-test"
    >
      {/* Header */}
      <div className="mb-6 flex items-center justify-between border-b border-gray-800 pb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">
            A/B Test: Compare prompts on real events
          </h3>
          <p className="mt-1 text-sm text-gray-400">
            Test your modified prompt against real events to see how it affects risk scoring
          </p>
        </div>

        {/* Loading Spinner */}
        {isRunning && (
          <div data-testid="loading-spinner">
            <Loader2 className="h-6 w-6 animate-spin text-[#76B900]" />
          </div>
        )}
      </div>

      {/* Split Panels */}
      <div className="mb-6 grid gap-4 md:grid-cols-2">
        {/* Original (A) Panel */}
        <div
          className="rounded-lg border border-gray-700 bg-black/30 p-4"
          data-testid="panel-original"
          aria-label="Original prompt (A) results"
        >
          <h4 className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gray-700 text-xs">
              A
            </span>
            Original (A)
          </h4>

          {results.length > 0 ? (
            results.map((result) => (
              <div key={result.eventId} className="mb-4 last:mb-0">
                <div className="mb-2 text-xs text-gray-500">
                  Event #{result.eventId}
                </div>
                <ResultPanel
                  label="A"
                  riskScore={result.originalResult.riskScore}
                  riskLevel={result.originalResult.riskLevel}
                  reasoning={result.originalResult.reasoning}
                  processingTimeMs={result.originalResult.processingTimeMs}
                />
              </div>
            ))
          ) : (
            <div className="flex h-32 items-center justify-center text-sm text-gray-500">
              Run a test to see results
            </div>
          )}
        </div>

        {/* Modified (B) Panel */}
        <div
          className="rounded-lg border border-[#76B900]/30 bg-[#76B900]/5 p-4"
          data-testid="panel-modified"
          aria-label="Modified prompt (B) results"
        >
          <h4 className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#76B900] text-xs text-black">
              B
            </span>
            Modified (B)
          </h4>

          {results.length > 0 ? (
            results.map((result) => (
              <div key={result.eventId} className="mb-4 last:mb-0">
                <div className="mb-2 text-xs text-gray-500">
                  Event #{result.eventId}
                </div>
                <ResultPanel
                  label="B"
                  riskScore={result.modifiedResult.riskScore}
                  riskLevel={result.modifiedResult.riskLevel}
                  reasoning={result.modifiedResult.reasoning}
                  processingTimeMs={result.modifiedResult.processingTimeMs}
                />
              </div>
            ))
          ) : (
            <div className="flex h-32 items-center justify-center text-sm text-gray-500">
              Run a test to see results
            </div>
          )}
        </div>
      </div>

      {/* Delta Indicators for each result */}
      {results.length > 0 && (
        <div className="mb-6 space-y-2">
          {results.map((result) => (
            <DeltaIndicator key={result.eventId} delta={result.scoreDelta} />
          ))}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-3 border-t border-gray-800 pt-4">
        <button
          onClick={() => onRunRandomTests(5)}
          disabled={isRunning}
          className="flex items-center gap-2 rounded-lg bg-gray-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Run on 5 Random Events"
        >
          <Play className="h-4 w-4" />
          Run on 5 Random Events
        </button>

        <button
          onClick={onPromoteB}
          disabled={isRunning}
          className="flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-[#8ACE00] disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Promote B as Default"
        >
          <Sparkles className="h-4 w-4" />
          Promote B as Default
        </button>
      </div>
    </Card>
  );
}
