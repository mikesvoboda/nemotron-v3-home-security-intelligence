/**
 * Trends Types
 *
 * Types for the trend comparison sparklines feature (NEM-5406/5407/5408/5409).
 *
 * The trends API provides time-bucketed event metrics with rolling 24-hour
 * baseline comparisons for dashboard sparkline visualization.
 *
 * @see backend/api/schemas/trends.py - Backend Pydantic schemas
 */

// ============================================================================
// Enums
// ============================================================================

/**
 * Type of trend view.
 */
export type TrendType = 'hourly' | 'daily';

// ============================================================================
// API Response Types (snake_case from backend)
// ============================================================================

/**
 * Backend API response for a single trend metric (snake_case).
 * @internal
 */
export interface BackendTrendMetric {
  /** Array of metric values for each time bucket */
  values: number[];
  /** Rolling 24-hour average baseline */
  baseline: number;
  /** Percentage deviation from baseline */
  deviation_pct: number;
}

/**
 * Backend API response for trends endpoint (snake_case).
 * @internal
 */
export interface BackendTrendsResponse {
  /** Event count per time bucket */
  event_count: BackendTrendMetric;
  /** Average risk score per time bucket */
  avg_risk: BackendTrendMetric;
  /** High-risk event count per time bucket */
  high_risk_count: BackendTrendMetric;
}

// ============================================================================
// Frontend Types (camelCase)
// ============================================================================

/**
 * A single trend metric with baseline comparison.
 */
export interface TrendMetric {
  /** Array of metric values for each time bucket (for sparkline display) */
  values: number[];

  /** Rolling 24-hour average baseline for comparison */
  baseline: number;

  /** Percentage deviation from baseline (positive = above, negative = below) */
  deviationPct: number;
}

/**
 * Trends data for dashboard sparkline visualization.
 */
export interface TrendsData {
  /** Event count per time bucket with baseline comparison */
  eventCount: TrendMetric;

  /** Average risk score per time bucket with baseline comparison */
  avgRisk: TrendMetric;

  /** High-risk event count (>= 70) per time bucket with baseline comparison */
  highRiskCount: TrendMetric;
}

// ============================================================================
// Component Props Types
// ============================================================================

/**
 * Props for the TrendSparklines component.
 */
export interface TrendSparklinesProps {
  /** Trends data, or null if loading/unavailable */
  data: TrendsData | null;

  /** Whether trends are currently loading */
  isLoading?: boolean;

  /** Error if fetch failed */
  error?: Error | null;

  /** Callback to retry loading after error */
  onRetry?: () => void;

  /** Additional CSS classes */
  className?: string;

  /** Render in compact mode (smaller dimensions) */
  compact?: boolean;
}

// ============================================================================
// Hook Types
// ============================================================================

/**
 * Return type for useTrends hook.
 */
export interface UseTrendsResult {
  /** Trends data */
  data: TrendsData | null;

  /** Whether data is being fetched */
  isLoading: boolean;

  /** Error if fetch failed */
  error: Error | null;

  /** Manually trigger a refetch */
  refetch: () => Promise<void>;
}

// ============================================================================
// Transformer Functions
// ============================================================================

/**
 * Transform backend trend metric to frontend format.
 *
 * @param backend - Backend trend metric (snake_case)
 * @returns Frontend trend metric (camelCase)
 */
export function transformTrendMetric(backend: BackendTrendMetric): TrendMetric {
  return {
    values: backend.values,
    baseline: backend.baseline,
    deviationPct: backend.deviation_pct,
  };
}

/**
 * Transform backend trends response to frontend format.
 *
 * @param backend - Backend trends response (snake_case)
 * @returns Frontend trends data (camelCase)
 */
export function transformTrendsResponse(backend: BackendTrendsResponse): TrendsData {
  return {
    eventCount: transformTrendMetric(backend.event_count),
    avgRisk: transformTrendMetric(backend.avg_risk),
    highRiskCount: transformTrendMetric(backend.high_risk_count),
  };
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for TrendMetric objects.
 *
 * @example
 * ```ts
 * if (isTrendMetric(data)) {
 *   console.log(data.values);
 * }
 * ```
 */
export function isTrendMetric(obj: unknown): obj is TrendMetric {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'values' in obj &&
    'baseline' in obj &&
    'deviationPct' in obj &&
    Array.isArray((obj as TrendMetric).values)
  );
}

/**
 * Type guard for TrendsData objects.
 *
 * @example
 * ```ts
 * if (isTrendsData(data)) {
 *   console.log(data.eventCount);
 * }
 * ```
 */
export function isTrendsData(obj: unknown): obj is TrendsData {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'eventCount' in obj &&
    'avgRisk' in obj &&
    'highRiskCount' in obj &&
    isTrendMetric((obj as TrendsData).eventCount) &&
    isTrendMetric((obj as TrendsData).avgRisk) &&
    isTrendMetric((obj as TrendsData).highRiskCount)
  );
}
