/**
 * EventAuditDetail Component
 *
 * Drill-down component showing AI pipeline audit details for a single event.
 * Displays quality scores, model contributions, self-critique, and improvement suggestions.
 *
 * @see frontend/src/services/auditApi.ts - API client for fetching audit data
 */

import {
  AlertCircle,
  CheckCircle,
  Lightbulb,
  MessageSquare,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  fetchEventAudit,
  triggerEvaluation,
  type EventAudit,
  AuditApiError,
} from '../../services/auditApi';

// ============================================================================
// Types
// ============================================================================

export interface EventAuditDetailProps {
  /** The event ID to fetch audit details for */
  eventId: number;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * List of AI models that can contribute to event analysis.
 */
const models = [
  { name: 'RT-DETR', key: 'rtdetr' },
  { name: 'Florence', key: 'florence' },
  { name: 'CLIP', key: 'clip' },
  { name: 'Violence', key: 'violence' },
  { name: 'Clothing', key: 'clothing' },
  { name: 'Vehicle', key: 'vehicle' },
  { name: 'Pet', key: 'pet' },
  { name: 'Weather', key: 'weather' },
  { name: 'Quality', key: 'image_quality' },
  { name: 'Zones', key: 'zones' },
  { name: 'Baseline', key: 'baseline' },
  { name: 'Cross-cam', key: 'cross_camera' },
] as const;

// ============================================================================
// Helper Components
// ============================================================================

interface ScoreBarProps {
  /** Label for the score */
  label: string;
  /** Score value (1-5) or null if not evaluated */
  score: number | null;
  /** Whether to highlight this score */
  highlight?: boolean;
}

/**
 * Visual bar showing a score out of 5 with color coding.
 * - Green: score >= 4
 * - Yellow: score >= 3
 * - Red: score < 3
 */
function ScoreBar({ label, score, highlight = false }: ScoreBarProps) {
  // Determine color based on score
  const getScoreColor = (value: number | null): string => {
    if (value === null) return 'bg-gray-700';
    if (value >= 4) return 'bg-green-500';
    if (value >= 3) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  // Calculate percentage width
  const getWidthPercent = (value: number | null): number => {
    if (value === null) return 0;
    return (value / 5) * 100;
  };

  const scoreColor = getScoreColor(score);
  const widthPercent = getWidthPercent(score);

  return (
    <div className={`rounded-lg p-3 ${highlight ? 'bg-[#76B900]/10' : 'bg-black/20'}`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm text-gray-300">{label}</span>
        <span
          className={`font-mono text-sm font-semibold ${
            score === null ? 'text-gray-500' : 'text-white'
          }`}
        >
          {score !== null ? `${score.toFixed(1)} / 5` : 'N/A'}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-800">
        <div
          className={`h-full rounded-full transition-all duration-300 ${scoreColor}`}
          style={{ width: `${widthPercent}%` }}
        />
      </div>
    </div>
  );
}

interface ImprovementListProps {
  /** Section label */
  label: string;
  /** List of improvement items */
  items: string[];
}

/**
 * Simple list display for improvement suggestions.
 */
function ImprovementList({ label, items }: ImprovementListProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-gray-800 bg-black/20 p-4">
      <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-400">
        <Lightbulb className="h-4 w-4" />
        {label}
      </h4>
      <ul className="space-y-2">
        {items.map((item, index) => (
          <li key={index} className="flex items-start gap-2 text-sm text-gray-300">
            <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * EventAuditDetail displays comprehensive AI pipeline audit information for a single event.
 *
 * Features:
 * - Quality Scores Section: Visual bars for each score (1-5)
 * - Model Contributions Section: Checklist of which models contributed
 * - Self-Critique Section: Text display of critique
 * - Improvements Section: Lists of suggestions
 * - Actions: "Run Evaluation" / "Re-run Evaluation" button
 */
export default function EventAuditDetail({ eventId }: EventAuditDetailProps) {
  const [audit, setAudit] = useState<EventAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load audit on mount and when eventId changes
  useEffect(() => {
    let mounted = true;

    async function loadAudit() {
      setLoading(true);
      setError(null);

      try {
        const data = await fetchEventAudit(eventId);
        if (mounted) {
          setAudit(data);
        }
      } catch (err) {
        if (mounted) {
          if (err instanceof AuditApiError) {
            if (err.status === 404) {
              setError('No audit record found for this event.');
            } else {
              setError(err.message);
            }
          } else {
            setError('Failed to load audit data.');
          }
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void loadAudit();

    return () => {
      mounted = false;
    };
  }, [eventId]);

  // Handle evaluate button click
  const handleEvaluate = async () => {
    setEvaluating(true);
    setError(null);

    try {
      const force = audit?.is_fully_evaluated ?? false;
      const data = await triggerEvaluation(eventId, force);
      setAudit(data);
    } catch (err) {
      if (err instanceof AuditApiError) {
        setError(err.message);
      } else {
        setError('Failed to run evaluation.');
      }
    } finally {
      setEvaluating(false);
    }
  };

  // Render loading state
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-3 text-gray-400">Loading audit data...</span>
        </div>
      </div>
    );
  }

  // Render error state
  if (error && !audit) {
    return (
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
        <div className="flex flex-col items-center justify-center py-8">
          <AlertCircle className="h-12 w-12 text-red-400" />
          <p className="mt-3 text-gray-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Render content when audit is loaded
  if (!audit) {
    return null;
  }

  // Count contributing models
  const contributingModels = models.filter(
    (m) => audit.contributions[m.key as keyof typeof audit.contributions]
  ).length;

  // Determine button label
  const buttonLabel = audit.is_fully_evaluated ? 'Re-run Evaluation' : 'Run Evaluation';

  return (
    <div className="space-y-6">
      {/* Error banner (for evaluation errors) */}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-900/20 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Header with event info and action button */}
      <div className="flex items-center justify-between rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Event #{audit.event_id} Audit</h3>
          <p className="text-sm text-gray-400">
            Audited: {new Date(audit.audited_at).toLocaleString()}
          </p>
          <div className="mt-2 flex items-center gap-4 text-sm text-gray-400">
            <span>
              Prompt:{' '}
              <span className="font-mono text-gray-300">
                {audit.prompt_length.toLocaleString()}
              </span>{' '}
              chars
            </span>
            <span>
              Tokens:{' '}
              <span className="font-mono text-gray-300">
                ~{audit.prompt_token_estimate.toLocaleString()}
              </span>
            </span>
            <span>
              Utilization:{' '}
              <span className="font-mono text-[#76B900]">
                {(audit.enrichment_utilization * 100).toFixed(0)}%
              </span>
            </span>
          </div>
        </div>
        <button
          onClick={() => void handleEvaluate()}
          disabled={evaluating}
          className={`flex items-center gap-2 rounded-lg px-4 py-2 font-semibold transition-colors ${
            evaluating
              ? 'cursor-not-allowed bg-gray-700 text-gray-400'
              : 'bg-[#76B900] text-black hover:bg-[#8ACE00]'
          }`}
        >
          <RefreshCw className={`h-4 w-4 ${evaluating ? 'animate-spin' : ''}`} />
          {evaluating ? 'Evaluating...' : buttonLabel}
        </button>
      </div>

      {/* Quality Scores Section */}
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
        <h4 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-400">
          Quality Scores
        </h4>
        {!audit.is_fully_evaluated ? (
          <p className="py-4 text-center text-sm text-gray-500">
            Run evaluation to see quality scores
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <ScoreBar label="Context Usage" score={audit.scores.context_usage} />
            <ScoreBar label="Reasoning Coherence" score={audit.scores.reasoning_coherence} />
            <ScoreBar label="Risk Justification" score={audit.scores.risk_justification} />
            <ScoreBar label="Consistency" score={audit.scores.consistency} />
            <ScoreBar label="Overall" score={audit.scores.overall} highlight />
            {audit.consistency_diff !== null && (
              <div className="rounded-lg bg-black/20 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm text-gray-300">Consistency Check</span>
                  <span
                    className={`font-mono text-sm font-semibold ${
                      Math.abs(audit.consistency_diff) <= 10
                        ? 'text-green-400'
                        : Math.abs(audit.consistency_diff) <= 20
                          ? 'text-yellow-400'
                          : 'text-red-400'
                    }`}
                  >
                    {audit.consistency_diff > 0 ? '+' : ''}
                    {audit.consistency_diff.toFixed(0)} pts
                  </span>
                </div>
                <p className="text-xs text-gray-500">
                  Re-evaluated risk: {audit.consistency_risk_score?.toFixed(0) ?? 'N/A'}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Model Contributions Section */}
      <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
        <h4 className="mb-4 flex items-center justify-between text-sm font-semibold uppercase tracking-wide text-gray-400">
          <span>Model Contributions</span>
          <span className="font-mono text-[#76B900]">
            {contributingModels} / {models.length}
          </span>
        </h4>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {models.map((model) => {
            const contributed = audit.contributions[model.key as keyof typeof audit.contributions];
            return (
              <div
                key={model.key}
                className={`flex items-center gap-2 rounded-lg p-2 ${
                  contributed ? 'bg-[#76B900]/10' : 'bg-black/20'
                }`}
              >
                {contributed ? (
                  <CheckCircle className="h-4 w-4 text-[#76B900]" />
                ) : (
                  <XCircle className="h-4 w-4 text-gray-600" />
                )}
                <span className={`text-sm ${contributed ? 'text-white' : 'text-gray-500'}`}>
                  {model.name}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Self-Critique Section */}
      {audit.is_fully_evaluated && audit.self_eval_critique && (
        <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
          <h4 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-400">
            <MessageSquare className="h-4 w-4" />
            Self-Critique
          </h4>
          <div className="rounded-lg bg-[#76B900]/10 p-4">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-300">
              {audit.self_eval_critique}
            </p>
          </div>
        </div>
      )}

      {/* Improvements Section */}
      {audit.is_fully_evaluated && (
        <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-4">
          <h4 className="mb-4 text-sm font-semibold uppercase tracking-wide text-gray-400">
            Improvement Suggestions
          </h4>
          {audit.improvements.missing_context.length === 0 &&
          audit.improvements.confusing_sections.length === 0 &&
          audit.improvements.unused_data.length === 0 &&
          audit.improvements.format_suggestions.length === 0 &&
          audit.improvements.model_gaps.length === 0 ? (
            <p className="py-4 text-center text-sm text-gray-500">
              No improvement suggestions available
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <ImprovementList label="Missing Context" items={audit.improvements.missing_context} />
              <ImprovementList
                label="Confusing Sections"
                items={audit.improvements.confusing_sections}
              />
              <ImprovementList label="Unused Data" items={audit.improvements.unused_data} />
              <ImprovementList
                label="Format Suggestions"
                items={audit.improvements.format_suggestions}
              />
              <ImprovementList label="Model Gaps" items={audit.improvements.model_gaps} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
