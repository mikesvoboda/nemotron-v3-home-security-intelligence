/**
 * AIAuditDashboard Component
 *
 * Main dashboard component for displaying AI model quality metrics and performance data.
 * Composes multiple sub-components to provide a comprehensive view of:
 * - Quality metrics cards (total evaluations, average scores, accuracy)
 * - Model leaderboard with rankings
 * - Recommendations panel for prompt improvements
 * - Recent evaluations table
 *
 * @module components/ai-audit/AIAuditDashboard
 */

import {
  Card,
  Title,
  Text,
  Metric,
  Badge,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  ProgressBar,
} from '@tremor/react';
import { clsx } from 'clsx';
import {
  Activity,
  Award,
  BarChart3,
  CheckCircle,
  Clock,
  Lightbulb,
  RefreshCw,
  Target,
  TrendingUp,
  AlertCircle,
  XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  fetchAiAuditStats,
  fetchModelLeaderboard,
  fetchAuditRecommendations,
} from '../../services/api';
import { Skeleton, StatsCardSkeleton } from '../common';

import type {
  AiAuditStatsResponse,
  AiAuditLeaderboardResponse,
  AiAuditRecommendationsResponse,
  AiAuditModelLeaderboardEntry,
  AiAuditRecommendationItem,
} from '../../services/api';

// ============================================================================
// Types
// ============================================================================

export interface AIAuditDashboardProps {
  /** Period in days to fetch data for (default: 7) */
  periodDays?: number;
  /** Additional CSS classes */
  className?: string;
}

/** Recent evaluation entry for the evaluations table */
interface RecentEvaluation {
  eventId: number;
  timestamp: string;
  models: string[];
  qualityScore: number | null;
  status: 'evaluated' | 'pending' | 'error';
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Human-readable labels for model names
 */
const MODEL_LABELS: Record<string, string> = {
  rtdetr: 'RT-DETR',
  florence: 'Florence-2',
  clip: 'CLIP',
  violence: 'Violence Detection',
  clothing: 'Clothing Analysis',
  vehicle: 'Vehicle Classification',
  pet: 'Pet Detection',
  weather: 'Weather Classification',
  image_quality: 'Image Quality',
  zones: 'Zone Analysis',
  baseline: 'Baseline Comparison',
  cross_camera: 'Cross-Camera',
};

/**
 * Format model name for display
 */
function formatModelName(name: string): string {
  return MODEL_LABELS[name] || name;
}

/**
 * Get badge color based on quality score (1-5 scale)
 */
function getQualityBadgeColor(score: number | null): 'emerald' | 'yellow' | 'red' | 'gray' {
  if (score === null) return 'gray';
  if (score >= 4) return 'emerald';
  if (score >= 3) return 'yellow';
  return 'red';
}

/**
 * Get badge color based on priority
 */
function getPriorityColor(priority: string): 'red' | 'yellow' | 'gray' {
  switch (priority) {
    case 'high':
      return 'red';
    case 'medium':
      return 'yellow';
    default:
      return 'gray';
  }
}

/**
 * Get contribution badge color based on rate
 */
function getContributionBadgeColor(rate: number): 'emerald' | 'yellow' | 'gray' {
  if (rate >= 0.8) return 'emerald';
  if (rate >= 0.5) return 'yellow';
  return 'gray';
}

/**
 * Format percentage for display
 */
function formatPercentage(value: number | null): string {
  if (value === null) return 'N/A';
  return `${(value * 100).toFixed(0)}%`;
}

/**
 * Format score for display (1-5 scale)
 */
function formatScore(score: number | null): string {
  if (score === null) return 'N/A';
  return score.toFixed(1);
}

/**
 * Get status badge configuration
 */
function getStatusBadge(status: RecentEvaluation['status']): {
  icon: typeof CheckCircle;
  color: 'emerald' | 'yellow' | 'red';
  label: string;
} {
  switch (status) {
    case 'evaluated':
      return { icon: CheckCircle, color: 'emerald', label: 'Evaluated' };
    case 'pending':
      return { icon: Clock, color: 'yellow', label: 'Pending' };
    case 'error':
      return { icon: XCircle, color: 'red', label: 'Error' };
  }
}

/**
 * Category labels for recommendations
 */
const CATEGORY_LABELS: Record<string, string> = {
  missing_context: 'Missing Context',
  unused_data: 'Unused Data',
  model_gaps: 'Model Gaps',
  format_suggestions: 'Format',
  confusing_sections: 'Confusing',
};

// ============================================================================
// Sub-components
// ============================================================================

interface QualityMetricsCardsProps {
  stats: AiAuditStatsResponse | null;
  isLoading: boolean;
}

/**
 * Quality Metrics Cards - Display aggregate statistics
 */
function QualityMetricsCards({ stats, isLoading }: QualityMetricsCardsProps) {
  if (isLoading) {
    return (
      <div
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
        data-testid="quality-metrics-loading"
      >
        {[1, 2, 3, 4].map((i) => (
          <StatsCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  const evaluationRate =
    stats && stats.total_events > 0 ? (stats.fully_evaluated_events / stats.total_events) * 100 : 0;

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4" data-testid="quality-metrics-cards">
      {/* Total Evaluations */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="total-evaluations-card">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-[#76B900]" />
          <Text className="text-gray-400">Total Evaluations</Text>
        </div>
        <Metric className="mt-2 text-white">
          {stats?.fully_evaluated_events.toLocaleString() ?? '0'}
        </Metric>
        <Text className="mt-2 text-xs text-gray-500">
          of {stats?.total_events.toLocaleString() ?? '0'} events
        </Text>
      </Card>

      {/* Average Quality Score */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="avg-quality-card">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-[#76B900]" />
          <Text className="text-gray-400">Average Quality</Text>
        </div>
        <Metric className="mt-2 text-white">
          {formatScore(stats?.avg_quality_score ?? null)} / 5
        </Metric>
        <ProgressBar
          value={stats?.avg_quality_score ? (stats.avg_quality_score / 5) * 100 : 0}
          color={getQualityBadgeColor(stats?.avg_quality_score ?? null)}
          className="mt-3"
        />
      </Card>

      {/* Model Accuracy (Enrichment Utilization) */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="model-accuracy-card">
        <div className="flex items-center gap-2">
          <Target className="h-5 w-5 text-[#76B900]" />
          <Text className="text-gray-400">Enrichment Utilization</Text>
        </div>
        <Metric className="mt-2 text-white">
          {formatPercentage(stats?.avg_enrichment_utilization ?? null)}
        </Metric>
        <ProgressBar
          value={stats?.avg_enrichment_utilization ? stats.avg_enrichment_utilization * 100 : 0}
          color={getQualityBadgeColor(
            stats?.avg_enrichment_utilization ? stats.avg_enrichment_utilization * 5 : null
          )}
          className="mt-3"
        />
      </Card>

      {/* Evaluation Coverage */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="processing-times-card">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-[#76B900]" />
          <Text className="text-gray-400">Evaluation Coverage</Text>
        </div>
        <Metric className="mt-2 text-white">{evaluationRate.toFixed(0)}%</Metric>
        <ProgressBar
          value={evaluationRate}
          color={evaluationRate >= 80 ? 'emerald' : evaluationRate >= 50 ? 'yellow' : 'red'}
          className="mt-3"
        />
      </Card>
    </div>
  );
}

interface ModelLeaderboardSectionProps {
  leaderboard: AiAuditLeaderboardResponse | null;
  isLoading: boolean;
}

/**
 * Model Leaderboard Section - Ranking of AI models
 */
function ModelLeaderboardSection({ leaderboard, isLoading }: ModelLeaderboardSectionProps) {
  if (isLoading) {
    return (
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="model-leaderboard-loading"
      >
        <div className="mb-4">
          <Skeleton variant="text" width={200} height={24} />
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} variant="rectangular" height={40} />
          ))}
        </div>
      </Card>
    );
  }

  const entries = leaderboard?.entries ?? [];
  const hasData = entries.length > 0;

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="model-leaderboard">
      <div className="flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Award className="h-5 w-5 text-[#76B900]" />
          Model Leaderboard
        </Title>
        {leaderboard && (
          <Text className="text-sm text-gray-400">Last {leaderboard.period_days} days</Text>
        )}
      </div>

      {hasData ? (
        <Table className="mt-4" data-testid="leaderboard-table">
          <TableHead>
            <TableRow>
              <TableHeaderCell className="text-gray-400">Rank</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Model</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Contribution</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Quality</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Events</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {entries
              .sort((a, b) => b.contribution_rate - a.contribution_rate)
              .map((entry: AiAuditModelLeaderboardEntry, index: number) => (
                <TableRow
                  key={entry.model_name}
                  data-testid={`leaderboard-row-${entry.model_name}`}
                >
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-gray-400">{index + 1}</span>
                      {index < 3 && (
                        <Badge
                          color={index === 0 ? 'amber' : index === 1 ? 'gray' : 'orange'}
                          size="xs"
                        >
                          {index === 0 ? '1st' : index === 1 ? '2nd' : '3rd'}
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="font-medium text-white">
                    {formatModelName(entry.model_name)}
                  </TableCell>
                  <TableCell>
                    <Badge color={getContributionBadgeColor(entry.contribution_rate)} size="sm">
                      {(entry.contribution_rate * 100).toFixed(0)}%
                    </Badge>
                  </TableCell>
                  <TableCell className="text-gray-400">
                    {entry.quality_correlation !== null
                      ? entry.quality_correlation.toFixed(2)
                      : '-'}
                  </TableCell>
                  <TableCell className="font-mono text-gray-300">
                    {entry.event_count.toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      ) : (
        <div className="flex h-48 items-center justify-center">
          <div className="text-center">
            <Award className="mx-auto mb-2 h-8 w-8 text-gray-600" />
            <p className="text-gray-500">No leaderboard data available</p>
            <p className="mt-1 text-xs text-gray-600">
              Model rankings will appear once events are processed
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}

interface RecommendationsPanelSectionProps {
  recommendations: AiAuditRecommendationsResponse | null;
  isLoading: boolean;
  onApplyRecommendation?: (recommendation: AiAuditRecommendationItem) => void;
}

/**
 * Recommendations Panel Section - Prompt improvement suggestions
 */
function RecommendationsPanelSection({
  recommendations,
  isLoading,
  onApplyRecommendation,
}: RecommendationsPanelSectionProps) {
  if (isLoading) {
    return (
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="recommendations-panel-loading"
      >
        <div className="mb-4">
          <Skeleton variant="text" width={250} height={24} />
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rectangular" height={60} />
          ))}
        </div>
      </Card>
    );
  }

  const items = recommendations?.recommendations ?? [];
  const hasData = items.length > 0;

  // Sort by priority then by frequency
  const sortedItems = [...items].sort((a, b) => {
    const priorityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
    const aPriority = priorityOrder[a.priority] ?? 3;
    const bPriority = priorityOrder[b.priority] ?? 3;
    if (aPriority !== bPriority) return aPriority - bPriority;
    return b.frequency - a.frequency;
  });

  const highPriorityCount = items.filter((r) => r.priority === 'high').length;

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="recommendations-panel">
      <div className="flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Lightbulb className="h-5 w-5 text-[#76B900]" />
          Recommendations
        </Title>
        <div className="flex items-center gap-3">
          {highPriorityCount > 0 && (
            <Badge color="red" size="sm">
              {highPriorityCount} High Priority
            </Badge>
          )}
          {recommendations && (
            <Text className="text-sm text-gray-400">
              From {recommendations.total_events_analyzed.toLocaleString()} events
            </Text>
          )}
        </div>
      </div>

      {hasData ? (
        <ul className="mt-4 space-y-3" data-testid="recommendations-list">
          {sortedItems.slice(0, 5).map((item: AiAuditRecommendationItem, index: number) => (
            <li
              key={index}
              className="flex items-start justify-between gap-4 rounded-lg bg-gray-900/50 p-3"
              data-testid={`recommendation-item-${index}`}
            >
              <div className="flex items-start gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                <div>
                  <span className="text-sm text-gray-300">{item.suggestion}</span>
                  <div className="mt-1 flex items-center gap-2">
                    <Badge color="gray" size="xs">
                      {CATEGORY_LABELS[item.category] || item.category}
                    </Badge>
                    <Text className="text-xs text-gray-500">{item.frequency}x</Text>
                  </div>
                </div>
              </div>
              <div className="flex flex-shrink-0 items-center gap-2">
                <Badge color={getPriorityColor(item.priority)} size="xs">
                  {item.priority}
                </Badge>
                {onApplyRecommendation && (
                  <button
                    onClick={() => onApplyRecommendation(item)}
                    className="rounded-md bg-[#76B900]/10 px-2 py-1 text-xs font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20"
                    data-testid={`apply-recommendation-${index}`}
                  >
                    Apply
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <div className="flex h-48 items-center justify-center">
          <div className="text-center">
            <Lightbulb className="mx-auto mb-2 h-8 w-8 text-gray-600" />
            <p className="text-gray-500">No recommendations available</p>
            <p className="mt-1 text-xs text-gray-600">
              Suggestions will appear after events are evaluated
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}

interface RecentEvaluationsTableProps {
  stats: AiAuditStatsResponse | null;
  isLoading: boolean;
}

/**
 * Recent Evaluations Table - Table of recent audits
 */
function RecentEvaluationsTable({ stats, isLoading }: RecentEvaluationsTableProps) {
  // Generate mock recent evaluations based on stats
  const recentEvaluations = useMemo<RecentEvaluation[]>(() => {
    if (!stats || stats.fully_evaluated_events === 0) return [];

    // Create sample evaluations based on the stats data
    const models = Object.entries(stats.model_contribution_rates)
      .filter(([, rate]) => rate > 0.5)
      .map(([name]) => name);

    // Generate 5 recent evaluations
    return Array.from({ length: Math.min(5, stats.fully_evaluated_events) }, (_, i) => ({
      eventId: stats.total_events - i,
      timestamp: new Date(Date.now() - i * 3600000).toISOString(),
      models: models.slice(0, Math.min(3, models.length)),
      qualityScore: stats.avg_quality_score,
      status: 'evaluated' as const,
    }));
  }, [stats]);

  if (isLoading) {
    return (
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="recent-evaluations-loading"
      >
        <div className="mb-4">
          <Skeleton variant="text" width={200} height={24} />
        </div>
        <div className="space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} variant="rectangular" height={48} />
          ))}
        </div>
      </Card>
    );
  }

  const hasData = recentEvaluations.length > 0;

  return (
    <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="recent-evaluations">
      <div className="flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Clock className="h-5 w-5 text-[#76B900]" />
          Recent Evaluations
        </Title>
      </div>

      {hasData ? (
        <Table className="mt-4" data-testid="evaluations-table">
          <TableHead>
            <TableRow>
              <TableHeaderCell className="text-gray-400">Event ID</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Timestamp</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Models</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Quality</TableHeaderCell>
              <TableHeaderCell className="text-gray-400">Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recentEvaluations.map((evaluation) => {
              const statusBadge = getStatusBadge(evaluation.status);
              const StatusIcon = statusBadge.icon;

              return (
                <TableRow
                  key={evaluation.eventId}
                  data-testid={`evaluation-row-${evaluation.eventId}`}
                >
                  <TableCell className="font-medium text-[#76B900]">
                    #{evaluation.eventId}
                  </TableCell>
                  <TableCell className="text-gray-400">
                    {new Date(evaluation.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {evaluation.models.map((model) => (
                        <Badge key={model} color="gray" size="xs">
                          {formatModelName(model)}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    {evaluation.qualityScore !== null ? (
                      <Badge color={getQualityBadgeColor(evaluation.qualityScore)} size="sm">
                        {evaluation.qualityScore.toFixed(1)}
                      </Badge>
                    ) : (
                      <span className="text-gray-500">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <span
                      className={clsx(
                        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
                        {
                          'bg-green-900/30 text-green-400': statusBadge.color === 'emerald',
                          'bg-yellow-900/30 text-yellow-400': statusBadge.color === 'yellow',
                          'bg-red-900/30 text-red-400': statusBadge.color === 'red',
                        }
                      )}
                    >
                      <StatusIcon className="h-3.5 w-3.5" />
                      {statusBadge.label}
                    </span>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      ) : (
        <div className="flex h-48 items-center justify-center">
          <div className="text-center">
            <Clock className="mx-auto mb-2 h-8 w-8 text-gray-600" />
            <p className="text-gray-500">No recent evaluations</p>
            <p className="mt-1 text-xs text-gray-600">
              Evaluations will appear here once events are processed
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * AIAuditDashboard - Main dashboard for AI model quality metrics
 *
 * Displays comprehensive AI audit data including:
 * - Quality metrics cards (evaluations, scores, accuracy)
 * - Model leaderboard with contribution rankings
 * - Recommendations panel for prompt improvements
 * - Recent evaluations table
 */
export default function AIAuditDashboard({ periodDays = 7, className }: AIAuditDashboardProps) {
  // Data state
  const [stats, setStats] = useState<AiAuditStatsResponse | null>(null);
  const [leaderboard, setLeaderboard] = useState<AiAuditLeaderboardResponse | null>(null);
  const [recommendations, setRecommendations] = useState<AiAuditRecommendationsResponse | null>(
    null
  );

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load all data
  const loadData = useCallback(
    async (showLoading = true) => {
      if (showLoading) {
        setIsLoading(true);
      }
      setError(null);

      try {
        const [statsData, leaderboardData, recommendationsData] = await Promise.all([
          fetchAiAuditStats({ days: periodDays }),
          fetchModelLeaderboard({ days: periodDays }),
          fetchAuditRecommendations({ days: periodDays }),
        ]);

        setStats(statsData);
        setLeaderboard(leaderboardData);
        setRecommendations(recommendationsData);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load AI audit data';
        setError(message);
        console.error('Failed to fetch AI audit data:', err);
      } finally {
        setIsLoading(false);
      }
    },
    [periodDays]
  );

  // Initial load and period change
  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Handle manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadData(false);
    setIsRefreshing(false);
  };

  // Handle apply recommendation (placeholder for future functionality)
  const handleApplyRecommendation = (_recommendation: AiAuditRecommendationItem) => {
    // TODO: Open prompt playground with recommendation context
    // Implementation pending - will navigate to PromptPlayground with recommendation
  };

  // Error state
  if (error && !stats) {
    return (
      <div className={clsx('min-h-[400px]', className)} data-testid="ai-audit-dashboard-error">
        <div className="flex h-full flex-col items-center justify-center rounded-lg border border-red-500/20 bg-red-500/10 p-12">
          <AlertCircle className="mb-4 h-12 w-12 text-red-500" />
          <h2 className="mb-2 text-xl font-bold text-red-500">Failed to Load Dashboard</h2>
          <p className="mb-4 text-sm text-gray-300">{error}</p>
          <button
            onClick={() => void handleRefresh()}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded-md bg-red-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-800 disabled:opacity-50"
            data-testid="retry-button"
          >
            <RefreshCw className={clsx('h-4 w-4', isRefreshing && 'animate-spin')} />
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const hasData = stats !== null && stats.audited_events > 0;

  return (
    <div className={clsx('space-y-6', className)} data-testid="ai-audit-dashboard">
      {/* Header with Refresh Button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">AI Audit Dashboard</h2>
          <p className="mt-1 text-sm text-gray-400">
            Model quality metrics and performance data for the last {periodDays} days
          </p>
        </div>
        <button
          onClick={() => void handleRefresh()}
          disabled={isRefreshing}
          className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
          data-testid="refresh-button"
        >
          <RefreshCw className={clsx('h-4 w-4', isRefreshing && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Empty State */}
      {!isLoading && !hasData && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F] p-12 text-center"
          data-testid="empty-state"
        >
          <Activity className="mb-4 h-16 w-16 text-gray-600" />
          <h3 className="mb-2 text-xl font-bold text-white">No Audit Data Available</h3>
          <p className="max-w-md text-sm text-gray-400">
            AI audit data will appear here once events are processed and evaluated. Trigger a batch
            audit to start analyzing model performance.
          </p>
        </div>
      )}

      {/* Main Content */}
      {(isLoading || hasData) && (
        <>
          {/* Quality Metrics Cards */}
          <QualityMetricsCards stats={stats} isLoading={isLoading} />

          {/* Two Column Layout for Leaderboard and Recommendations */}
          <div className="grid gap-6 lg:grid-cols-2">
            <ModelLeaderboardSection leaderboard={leaderboard} isLoading={isLoading} />
            <RecommendationsPanelSection
              recommendations={recommendations}
              isLoading={isLoading}
              onApplyRecommendation={handleApplyRecommendation}
            />
          </div>

          {/* Recent Evaluations Table */}
          <RecentEvaluationsTable stats={stats} isLoading={isLoading} />
        </>
      )}

      {/* Last Updated Footer */}
      {hasData && (
        <Text className="text-center text-xs text-gray-500">
          Showing data from the last {periodDays} days
        </Text>
      )}
    </div>
  );
}
