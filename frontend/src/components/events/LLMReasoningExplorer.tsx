/**
 * LLMReasoningExplorer - Displays LLM reasoning process from LLMInteraction table
 *
 * Part of NEM-5024: Hidden Backend Exposure - Phase 9
 *
 * Features:
 * - Display <think> blocks with expandable reasoning steps
 * - Show enrichment sources that fed into analysis
 * - Highlight key factors in risk determination
 * - Debug mode for prompt inspection
 * - Truncation indicator showing what context was dropped
 */

import { clsx } from 'clsx';
import {
  AlertTriangle,
  Brain,
  Bug,
  ChevronDown,
  ChevronUp,
  Database,
  Eye,
  Lightbulb,
  RefreshCw,
  Scissors,
  Shield,
  User,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { fetchLLMReasoning, LLMReasoningApiError } from '../../services/llmReasoningApi';

import type {
  LLMReasoningResponse,
  ReasoningStep,
  EnrichmentSource,
  TruncationInfo,
  HouseholdMatch,
} from '../../types/llmReasoning';

// =============================================================================
// Types
// =============================================================================

export interface LLMReasoningExplorerProps {
  /** Event ID to fetch reasoning for */
  eventId: number;
  /** Optional CSS class name */
  className?: string;
  /** Default expanded state for reasoning steps */
  defaultExpanded?: boolean;
}

// =============================================================================
// Sub-components
// =============================================================================

interface ReasoningStepCardProps {
  step: ReasoningStep;
  isExpanded: boolean;
}

function ReasoningStepCard({ step, isExpanded }: ReasoningStepCardProps) {
  const confidenceColors: Record<string, string> = {
    high: 'text-green-400 bg-green-400/10',
    medium: 'text-yellow-400 bg-yellow-400/10',
    low: 'text-red-400 bg-red-400/10',
  };

  return (
    <div
      className={clsx(
        'rounded-lg border border-gray-800 bg-black/20 p-4 transition-all',
        isExpanded ? 'mb-3' : 'mb-2'
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#76B900]/20 text-xs font-bold text-[#76B900]">
          {step.stepNumber}
        </div>
        <div className="flex-1">
          <p className="text-sm leading-relaxed text-gray-300">{step.content}</p>

          {isExpanded && (
            <div className="mt-3 space-y-2">
              {/* Key Factors */}
              {step.keyFactors.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {step.keyFactors.map((factor, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center rounded-full bg-[#76B900]/10 px-2 py-0.5 text-xs text-[#76B900]"
                    >
                      {factor}
                    </span>
                  ))}
                </div>
              )}

              {/* Confidence Indicator */}
              {step.confidenceIndicator && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Confidence:</span>
                  <span
                    className={clsx(
                      'rounded-full px-2 py-0.5 text-xs font-medium capitalize',
                      confidenceColors[step.confidenceIndicator] ?? 'text-gray-400 bg-gray-400/10'
                    )}
                  >
                    {step.confidenceIndicator}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface EnrichmentSourceCardProps {
  source: EnrichmentSource;
}

function EnrichmentSourceCard({ source }: EnrichmentSourceCardProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border p-3',
        source.populated
          ? 'border-[#76B900]/30 bg-[#76B900]/5'
          : 'border-gray-800 bg-black/20 opacity-60'
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database
            className={clsx('h-4 w-4', source.populated ? 'text-[#76B900]' : 'text-gray-500')}
          />
          <span className={clsx('text-sm font-medium', source.populated ? 'text-white' : 'text-gray-500')}>
            {source.name}
          </span>
        </div>
        {source.populated && (
          <span className="text-xs text-gray-400">{source.fieldCount} fields</span>
        )}
      </div>
      {source.populated && source.sampleFields.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {source.sampleFields.map((field, idx) => (
            <span key={idx} className="rounded bg-black/30 px-1.5 py-0.5 text-xs text-gray-400">
              {field}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

interface TruncationWarningProps {
  truncationInfo: TruncationInfo;
}

function TruncationWarning({ truncationInfo }: TruncationWarningProps) {
  if (!truncationInfo.wasTruncated) {
    return null;
  }

  return (
    <div className="rounded-lg border border-yellow-600/30 bg-yellow-600/10 p-4">
      <div className="flex items-start gap-3">
        <Scissors className="h-5 w-5 flex-shrink-0 text-yellow-500" />
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-yellow-400">Context Truncated</h4>
          {truncationInfo.truncationReason && (
            <p className="mt-1 text-xs text-yellow-300/70">{truncationInfo.truncationReason}</p>
          )}
          {truncationInfo.originalLength && truncationInfo.truncatedLength && (
            <p className="mt-1 text-xs text-gray-400">
              Reduced from {truncationInfo.originalLength.toLocaleString()} to{' '}
              {truncationInfo.truncatedLength.toLocaleString()} tokens
            </p>
          )}
          {truncationInfo.droppedSections.length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-gray-400">Dropped sections:</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {truncationInfo.droppedSections.map((section, idx) => (
                  <span
                    key={idx}
                    className="rounded bg-yellow-600/20 px-1.5 py-0.5 text-xs text-yellow-400"
                  >
                    {section}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface HouseholdMatchCardProps {
  match: HouseholdMatch;
}

function HouseholdMatchCard({ match }: HouseholdMatchCardProps) {
  const similarityPercent = Math.round(match.similarityScore * 100);

  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-800 bg-black/20 p-3">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#76B900]/20">
          <User className="h-4 w-4 text-[#76B900]" />
        </div>
        <div>
          <p className="text-sm font-medium text-white">
            {match.entityName ?? `Unknown ${match.entityType}`}
          </p>
          <p className="text-xs text-gray-400">
            {match.entityType} {match.matchMethod && `via ${match.matchMethod}`}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className="text-sm font-bold text-[#76B900]">{similarityPercent}%</p>
        <p className="text-xs text-gray-500">match</p>
      </div>
    </div>
  );
}

interface DebugInfoPanelProps {
  rawResponse: string;
  debugInfo: LLMReasoningResponse['debugInfo'];
}

function DebugInfoPanel({ rawResponse, debugInfo }: DebugInfoPanelProps) {
  const [showRaw, setShowRaw] = useState(false);

  return (
    <div className="space-y-4 rounded-lg border border-purple-600/30 bg-purple-600/5 p-4">
      <div className="flex items-center gap-2">
        <Bug className="h-4 w-4 text-purple-400" />
        <h4 className="text-sm font-semibold text-purple-400">Debug Information</h4>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        {debugInfo.promptLength !== undefined && (
          <div>
            <p className="text-gray-500">Prompt Length</p>
            <p className="font-mono text-white">{debugInfo.promptLength.toLocaleString()} chars</p>
          </div>
        )}
        {debugInfo.enrichmentSnapshotKeys && (
          <div>
            <p className="text-gray-500">Enrichment Keys</p>
            <p className="font-mono text-white">{debugInfo.enrichmentSnapshotKeys.length} sources</p>
          </div>
        )}
        {debugInfo.hasTruncationLog !== undefined && (
          <div>
            <p className="text-gray-500">Has Truncation Log</p>
            <p className="font-mono text-white">{debugInfo.hasTruncationLog ? 'Yes' : 'No'}</p>
          </div>
        )}
        {debugInfo.hasHouseholdMatches !== undefined && (
          <div>
            <p className="text-gray-500">Has Household Matches</p>
            <p className="font-mono text-white">{debugInfo.hasHouseholdMatches ? 'Yes' : 'No'}</p>
          </div>
        )}
      </div>

      {/* Raw Response Toggle */}
      <div>
        <button
          type="button"
          onClick={() => setShowRaw(!showRaw)}
          className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300"
        >
          {showRaw ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {showRaw ? 'Hide' : 'Show'} Raw Response
        </button>
        {showRaw && (
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-black/50 p-3 text-xs text-gray-300">
            {rawResponse}
          </pre>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

/**
 * LLMReasoningExplorer displays the AI reasoning process for an event.
 *
 * Shows:
 * - Parsed <think> blocks with expandable reasoning steps
 * - Key observations and risk factors identified
 * - Enrichment sources that contributed data
 * - Truncation warnings when context was dropped
 * - Household matches with similarity scores
 * - Debug mode for prompt inspection
 */
export default function LLMReasoningExplorer({
  eventId,
  className,
  defaultExpanded = false,
}: LLMReasoningExplorerProps) {
  const [data, setData] = useState<LLMReasoningResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [debugMode, setDebugMode] = useState(false);

  const loadData = useCallback(async (includeDebug: boolean) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetchLLMReasoning(eventId, includeDebug);
      setData(response);
    } catch (err) {
      if (err instanceof LLMReasoningApiError) {
        setError(err.message);
      } else {
        setError('Failed to load LLM reasoning data');
      }
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  // Initial load
  useEffect(() => {
    void loadData(debugMode);
  }, [eventId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Refetch when debug mode changes
  const handleDebugToggle = useCallback(() => {
    const newDebugMode = !debugMode;
    setDebugMode(newDebugMode);
    void loadData(newDebugMode);
  }, [debugMode, loadData]);

  const handleRetry = useCallback(() => {
    void loadData(debugMode);
  }, [debugMode, loadData]);

  // Loading state
  if (loading) {
    return (
      <div className={clsx('rounded-lg border border-gray-800 bg-[#1F1F1F] p-6', className)}>
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
          <span className="ml-3 text-gray-400">Loading LLM reasoning data...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={clsx('rounded-lg border border-gray-800 bg-[#1F1F1F] p-6', className)}>
        <div className="flex flex-col items-center justify-center py-8">
          <AlertTriangle className="h-10 w-10 text-yellow-500" />
          <p className="mt-3 text-gray-400">{error}</p>
          <button
            onClick={handleRetry}
            className="mt-4 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            aria-label="Retry loading"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const { thinkBlock, enrichmentSources, truncationInfo, householdMatches, debugInfo, rawResponse } = data;

  const populatedSources = enrichmentSources.filter((s) => s.populated);
  const unpopulatedSources = enrichmentSources.filter((s) => !s.populated);

  return (
    <div className={clsx('space-y-6', className)} data-testid="llm-reasoning-explorer">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-[#76B900]" />
          <h3 className="text-lg font-semibold text-white">
            LLM Reasoning Explorer
          </h3>
        </div>
        <button
          onClick={handleDebugToggle}
          className={clsx(
            'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
            debugMode
              ? 'bg-purple-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          )}
          aria-label={debugMode ? 'Disable debug mode' : 'Enable debug mode'}
        >
          <Bug className="h-3.5 w-3.5" />
          Debug {debugMode ? 'ON' : 'OFF'}
        </button>
      </div>

      {/* Truncation Warning */}
      <TruncationWarning truncationInfo={truncationInfo} />

      {/* Reasoning Steps Section */}
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex w-full items-center justify-between text-left"
          aria-expanded={isExpanded}
          aria-controls="reasoning-steps-content"
          aria-label={isExpanded ? 'Collapse reasoning steps' : 'Expand reasoning steps'}
        >
          <div className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-[#76B900]" />
            <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
              Reasoning Steps ({thinkBlock.reasoningSteps.length})
            </h4>
          </div>
          {isExpanded ? (
            <ChevronUp className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-400" />
          )}
        </button>

        {isExpanded && thinkBlock.reasoningSteps.length > 0 && (
          <div className="mt-4 space-y-3" id="reasoning-steps-content" data-testid="reasoning-steps-expanded">
            {thinkBlock.reasoningSteps.map((step) => (
              <ReasoningStepCard key={step.stepNumber} step={step} isExpanded={isExpanded} />
            ))}
          </div>
        )}

        {isExpanded && thinkBlock.reasoningSteps.length === 0 && (
          <p className="mt-4 text-center text-sm text-gray-500">
            No structured reasoning steps available
          </p>
        )}
      </div>

      {/* Key Observations */}
      {thinkBlock.keyObservations.length > 0 && (
        <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Eye className="h-4 w-4 text-[#76B900]" />
            <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
              Key Observations
            </h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {thinkBlock.keyObservations.map((obs, idx) => (
              <span
                key={idx}
                className="rounded-full bg-[#76B900]/10 px-3 py-1 text-sm text-[#76B900]"
              >
                {obs}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Risk Factors Mentioned */}
      {thinkBlock.riskFactorsMentioned.length > 0 && (
        <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
          <div className="mb-3 flex items-center gap-2">
            <Shield className="h-4 w-4 text-yellow-500" />
            <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
              Risk Factors Mentioned
            </h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {thinkBlock.riskFactorsMentioned.map((factor, idx) => (
              <span
                key={idx}
                className="rounded-full bg-yellow-500/10 px-3 py-1 text-sm text-yellow-400"
              >
                {factor}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Enrichment Sources */}
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-[#76B900]" />
            <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
              Enrichment Sources
            </h4>
          </div>
          <span className="text-xs text-gray-500">
            {populatedSources.length}/{enrichmentSources.length} active
          </span>
        </div>

        {populatedSources.length > 0 && (
          <div className="mb-4">
            <p className="mb-2 text-xs text-gray-500">Active Sources</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {populatedSources.map((source, idx) => (
                <EnrichmentSourceCard key={idx} source={source} />
              ))}
            </div>
          </div>
        )}

        {unpopulatedSources.length > 0 && (
          <div>
            <p className="mb-2 text-xs text-gray-500">Inactive Sources</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {unpopulatedSources.map((source, idx) => (
                <EnrichmentSourceCard key={idx} source={source} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Household Matches */}
      {householdMatches.length > 0 && (
        <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
          <div className="mb-4 flex items-center gap-2">
            <User className="h-4 w-4 text-[#76B900]" />
            <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
              Household Matches
            </h4>
          </div>
          <div className="space-y-2">
            {householdMatches.map((match, idx) => (
              <HouseholdMatchCard key={idx} match={match} />
            ))}
          </div>
        </div>
      )}

      {/* Debug Info Panel */}
      {debugMode && <DebugInfoPanel rawResponse={rawResponse} debugInfo={debugInfo} />}
    </div>
  );
}
