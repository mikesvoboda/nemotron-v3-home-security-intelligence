/**
 * Timeline data hook for timeline scrubber (NEM-2932)
 * Provides bucketed event counts for timeline visualization.
 *
 * Uses React Query for data fetching with caching and background updates.
 * Transforms backend response (risk scores) to frontend format (severity levels).
 */

import { useQuery } from '@tanstack/react-query';

import type {
  ZoomLevel,
  TimelineBucket,
  Severity,
} from '../components/events/TimelineScrubber';

// API response types
interface TimelineBucketAPIResponse {
  timestamp: string;
  event_count: number;
  max_risk_score: number;
}

interface TimelineSummaryAPIResponse {
  buckets: TimelineBucketAPIResponse[];
  total_events: number;
  start_date: string;
  end_date: string;
}

export interface UseTimelineDataOptions {
  /** Zoom level for bucketing (hour, day, week) */
  zoomLevel: ZoomLevel;
  /** Start date filter */
  startDate?: string;
  /** End date filter */
  endDate?: string;
  /** Camera ID filter */
  cameraId?: string;
  /** Whether the hook is enabled */
  enabled?: boolean;
}

export interface UseTimelineDataReturn {
  /** Bucketed event data */
  buckets: TimelineBucket[];
  /** Total events in the range */
  totalEvents: number;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  isError: boolean;
  /** Error object if any */
  error: Error | null;
  /** Refetch function */
  refetch: () => void;
}

/**
 * Convert a risk score (0-100) to a severity level.
 * Thresholds:
 * - 0-29: low
 * - 30-59: medium
 * - 60-84: high
 * - 85-100: critical
 */
function riskScoreToSeverity(riskScore: number): Severity {
  if (riskScore >= 85) return 'critical';
  if (riskScore >= 60) return 'high';
  if (riskScore >= 30) return 'medium';
  return 'low';
}

/**
 * Transform API response to frontend format.
 */
function transformBuckets(apiBuckets: TimelineBucketAPIResponse[]): TimelineBucket[] {
  return apiBuckets.map((bucket) => ({
    timestamp: bucket.timestamp,
    eventCount: bucket.event_count,
    maxSeverity: riskScoreToSeverity(bucket.max_risk_score),
  }));
}

/**
 * Fetch timeline summary data from the API.
 */
async function fetchTimelineData(
  zoomLevel: ZoomLevel,
  startDate?: string,
  endDate?: string,
  cameraId?: string
): Promise<TimelineSummaryAPIResponse> {
  const params = new URLSearchParams();
  params.set('bucket_size', zoomLevel);

  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  if (cameraId) params.set('camera_id', cameraId);

  const response = await fetch(`/api/events/timeline-summary?${params.toString()}`);

  if (!response.ok) {
    throw new Error(`Failed to fetch timeline data: ${response.statusText}`);
  }

  return response.json() as Promise<TimelineSummaryAPIResponse>;
}

/**
 * Hook to fetch timeline data for the timeline scrubber visualization.
 * Returns bucketed event counts based on the specified zoom level.
 */
export function useTimelineData(options: UseTimelineDataOptions): UseTimelineDataReturn {
  const { zoomLevel, startDate, endDate, cameraId, enabled = true } = options;

  const query = useQuery({
    queryKey: ['timeline-summary', zoomLevel, startDate, endDate, cameraId],
    queryFn: () => fetchTimelineData(zoomLevel, startDate, endDate, cameraId),
    enabled,
    staleTime: 30 * 1000, // Consider data fresh for 30 seconds
    refetchInterval: 60 * 1000, // Refetch every minute in background
  });

  // Transform data when available
  const buckets = query.data ? transformBuckets(query.data.buckets) : [];
  const totalEvents = query.data?.total_events ?? 0;

  return {
    buckets,
    totalEvents,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: () => void query.refetch(),
  };
}

/**
 * Generate mock timeline data for testing/development.
 * Creates realistic-looking bucketed data based on zoom level.
 */
export function generateMockTimelineData(
  zoomLevel: ZoomLevel,
  startDate?: string,
  endDate?: string
): TimelineBucket[] {
  const buckets: TimelineBucket[] = [];
  const now = new Date();

  // Determine bucket count and duration based on zoom level
  let bucketCount: number;
  let bucketDurationMs: number;

  switch (zoomLevel) {
    case 'hour':
      bucketCount = 12; // 5 min each = 1 hour
      bucketDurationMs = 5 * 60 * 1000;
      break;
    case 'day':
      bucketCount = 24; // 1 hour each = 24 hours
      bucketDurationMs = 60 * 60 * 1000;
      break;
    case 'week':
      bucketCount = 7; // 1 day each = 7 days
      bucketDurationMs = 24 * 60 * 60 * 1000;
      break;
    default:
      bucketCount = 24;
      bucketDurationMs = 60 * 60 * 1000;
  }

  // Calculate time range
  const effectiveEndDate = endDate ? new Date(endDate) : now;
  const effectiveStartDate = startDate
    ? new Date(startDate)
    : new Date(effectiveEndDate.getTime() - bucketCount * bucketDurationMs);

  // Generate buckets
  let currentTime = effectiveStartDate.getTime();
  const endTime = effectiveEndDate.getTime();

  while (currentTime <= endTime) {
    // Generate random but realistic-looking data
    const eventCount = Math.floor(Math.random() * 20);
    const riskScore = Math.floor(Math.random() * 100);

    buckets.push({
      timestamp: new Date(currentTime).toISOString(),
      eventCount,
      maxSeverity: riskScoreToSeverity(riskScore),
    });

    currentTime += bucketDurationMs;
  }

  return buckets;
}
