/**
 * QualityScoreTrends - Displays AI quality score metrics
 *
 * Shows quality score metrics as stat cards with visual progress indicators.
 * Includes average quality score, consistency rate, and enrichment utilization.
 */

import { Card, Title, Metric, Text, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import { TrendingUp, CheckCircle, Gauge } from 'lucide-react';

export interface QualityScoreTrendsProps {
  /** Average quality score (1-5 scale) */
  avgQualityScore: number | null;
  /** Average consistency rate (1-5 scale) */
  avgConsistencyRate: number | null;
  /** Average enrichment utilization (0-1 scale) */
  avgEnrichmentUtilization: number | null;
  /** Total events processed */
  totalEvents: number;
  /** Fully evaluated events */
  fullyEvaluatedEvents: number;
  /** Additional CSS classes */
  className?: string;
}

/** Tremor color type */
type TremorColor = 'emerald' | 'yellow' | 'red' | 'gray';

/**
 * Get color class based on score (1-5 scale)
 */
function getScoreColor(score: number | null): TremorColor {
  if (score === null) return 'gray';
  if (score >= 4) return 'emerald';
  if (score >= 3) return 'yellow';
  return 'red';
}

/**
 * Format score for display
 */
function formatScore(score: number | null, scale: number = 5): string {
  if (score === null) return 'N/A';
  return `${score.toFixed(1)} / ${scale}`;
}

/**
 * Get enrichment utilization color
 */
function getEnrichmentColor(value: number | null): TremorColor {
  if (value === null) return 'gray';
  if (value >= 0.7) return 'emerald';
  if (value >= 0.5) return 'yellow';
  return 'red';
}

/**
 * Get evaluation coverage color
 */
function getCoverageColor(rate: number): TremorColor {
  if (rate >= 80) return 'emerald';
  if (rate >= 50) return 'yellow';
  return 'red';
}

/**
 * Calculate percentage for progress bar
 */
function getProgressPercent(value: number | null, max: number = 5): number {
  if (value === null) return 0;
  return (value / max) * 100;
}

/**
 * QualityScoreTrends - Quality metrics visualization
 */
export default function QualityScoreTrends({
  avgQualityScore,
  avgConsistencyRate,
  avgEnrichmentUtilization,
  totalEvents,
  fullyEvaluatedEvents,
  className,
}: QualityScoreTrendsProps) {
  const evaluationRate = totalEvents > 0 ? (fullyEvaluatedEvents / totalEvents) * 100 : 0;

  return (
    <div
      className={clsx('grid gap-4 md:grid-cols-2 lg:grid-cols-4', className)}
      data-testid="quality-score-trends"
    >
      {/* Average Quality Score */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="quality-score-card">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-[#76B900]" />
          <Text className="text-gray-400">Average Quality</Text>
        </div>
        <Metric className="mt-2 text-white">{formatScore(avgQualityScore)}</Metric>
        <ProgressBar
          value={getProgressPercent(avgQualityScore)}
          color={getScoreColor(avgQualityScore)}
          className="mt-3"
        />
        <Text className="mt-2 text-xs text-gray-500">
          Based on {fullyEvaluatedEvents.toLocaleString()} evaluated events
        </Text>
      </Card>

      {/* Consistency Rate */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="consistency-rate-card">
        <div className="flex items-center gap-2">
          <CheckCircle className="h-5 w-5 text-[#76B900]" />
          <Text className="text-gray-400">Consistency Rate</Text>
        </div>
        <Metric className="mt-2 text-white">{formatScore(avgConsistencyRate)}</Metric>
        <ProgressBar
          value={getProgressPercent(avgConsistencyRate)}
          color={getScoreColor(avgConsistencyRate)}
          className="mt-3"
        />
        <Text className="mt-2 text-xs text-gray-500">Risk score consistency on re-evaluation</Text>
      </Card>

      {/* Enrichment Utilization */}
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="enrichment-utilization-card"
      >
        <div className="flex items-center gap-2">
          <Gauge className="h-5 w-5 text-[#76B900]" />
          <Text className="text-gray-400">Enrichment Utilization</Text>
        </div>
        <Metric className="mt-2 text-white">
          {avgEnrichmentUtilization !== null
            ? `${(avgEnrichmentUtilization * 100).toFixed(0)}%`
            : 'N/A'}
        </Metric>
        <ProgressBar
          value={avgEnrichmentUtilization !== null ? avgEnrichmentUtilization * 100 : 0}
          color={getEnrichmentColor(avgEnrichmentUtilization)}
          className="mt-3"
        />
        <Text className="mt-2 text-xs text-gray-500">Percentage of AI models contributing</Text>
      </Card>

      {/* Evaluation Coverage */}
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="evaluation-coverage-card"
      >
        <div className="flex items-center gap-2">
          <Title className="text-gray-400">Evaluation Coverage</Title>
        </div>
        <Metric className="mt-2 text-white">{evaluationRate.toFixed(0)}%</Metric>
        <ProgressBar
          value={evaluationRate}
          color={getCoverageColor(evaluationRate)}
          className="mt-3"
        />
        <Text className="mt-2 text-xs text-gray-500">
          {fullyEvaluatedEvents.toLocaleString()} of {totalEvents.toLocaleString()} events evaluated
        </Text>
      </Card>
    </div>
  );
}
