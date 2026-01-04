/**
 * useAIMetrics Hook
 *
 * Fetches AI performance metrics from multiple endpoints and combines them
 * into a unified state for the AI Performance page.
 *
 * Data sources:
 * - /api/metrics - Prometheus metrics (parsed for latency histograms)
 * - /api/system/telemetry - Queue depths and basic latency stats
 * - /api/system/health - AI service health status
 * - /api/system/pipeline-latency - Detailed pipeline latency percentiles
 * - /api/dlq/stats - Dead letter queue counts (actual current DLQ depth)
 */

import { useState, useEffect, useCallback, useRef } from 'react';

import { fetchTelemetry, fetchHealth, fetchDlqStats, type TelemetryResponse, type HealthResponse, type DLQStatsResponse } from '../services/api';
import { fetchAIMetrics, type AIMetrics, type AILatencyMetrics } from '../services/metricsParser';

/**
 * Pipeline latency response from /api/system/pipeline-latency
 */
interface PipelineLatencyResponse {
  watch_to_detect: PipelineStageLatency | null;
  detect_to_batch: PipelineStageLatency | null;
  batch_to_analyze: PipelineStageLatency | null;
  total_pipeline: PipelineStageLatency | null;
  window_minutes: number;
  timestamp: string;
}

interface PipelineStageLatency {
  avg_ms: number | null;
  min_ms: number | null;
  max_ms: number | null;
  p50_ms: number | null;
  p95_ms: number | null;
  p99_ms: number | null;
  sample_count: number;
}

/**
 * AI model status information
 */
export interface AIModelStatus {
  /** Model name (e.g., "RT-DETRv2", "Nemotron") */
  name: string;
  /** Health status */
  status: 'healthy' | 'unhealthy' | 'degraded' | 'unknown';
  /** Status message from health check */
  message?: string;
  /** Additional details */
  details?: Record<string, string>;
}

/**
 * Combined AI performance metrics state
 */
export interface AIPerformanceState {
  /** RT-DETR model status */
  rtdetr: AIModelStatus;
  /** Nemotron model status */
  nemotron: AIModelStatus;
  /** RT-DETR detection latency metrics */
  detectionLatency: AILatencyMetrics | null;
  /** Nemotron analysis latency metrics */
  analysisLatency: AILatencyMetrics | null;
  /** Pipeline stage latencies */
  pipelineLatency: PipelineLatencyResponse | null;
  /** Total detections processed */
  totalDetections: number;
  /** Total events created */
  totalEvents: number;
  /** Detection queue depth */
  detectionQueueDepth: number;
  /** Analysis queue depth */
  analysisQueueDepth: number;
  /** Pipeline errors by type */
  pipelineErrors: Record<string, number>;
  /** Queue overflow counts */
  queueOverflows: Record<string, number>;
  /** Items in DLQ by queue */
  dlqItems: Record<string, number>;
  /** Last update timestamp */
  lastUpdated: string | null;
}

/**
 * Hook return type
 */
export interface UseAIMetricsResult {
  /** Current AI performance metrics */
  data: AIPerformanceState;
  /** Loading state */
  isLoading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Manually trigger a refresh */
  refresh: () => Promise<void>;
}

/**
 * Hook options
 */
export interface UseAIMetricsOptions {
  /** Polling interval in milliseconds (default: 5000) */
  pollingInterval?: number;
  /** Whether to enable polling (default: true) */
  enablePolling?: boolean;
}

/**
 * Default initial state
 */
const initialState: AIPerformanceState = {
  rtdetr: { name: 'RT-DETRv2', status: 'unknown' },
  nemotron: { name: 'Nemotron', status: 'unknown' },
  detectionLatency: null,
  analysisLatency: null,
  pipelineLatency: null,
  totalDetections: 0,
  totalEvents: 0,
  detectionQueueDepth: 0,
  analysisQueueDepth: 0,
  pipelineErrors: {},
  queueOverflows: {},
  dlqItems: {},
  lastUpdated: null,
};

/**
 * Fetch pipeline latency from the API
 */
async function fetchPipelineLatency(windowMinutes: number = 60): Promise<PipelineLatencyResponse> {
  const response = await fetch(`/api/system/pipeline-latency?window_minutes=${windowMinutes}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch pipeline latency: ${response.status}`);
  }
  return response.json() as Promise<PipelineLatencyResponse>;
}

/**
 * Extract AI model statuses from health response
 */
function extractAIStatuses(health: HealthResponse | null): {
  rtdetr: AIModelStatus;
  nemotron: AIModelStatus;
} {
  const aiService = health?.services?.ai;

  // Default unknown status
  const defaultRtdetr: AIModelStatus = { name: 'RT-DETRv2', status: 'unknown' };
  const defaultNemotron: AIModelStatus = { name: 'Nemotron', status: 'unknown' };

  if (!aiService) {
    return { rtdetr: defaultRtdetr, nemotron: defaultNemotron };
  }

  // Extract individual service statuses from details
  const details = aiService.details as Record<string, string> | undefined;

  const rtdetrStatus = details?.rtdetr ?? 'unknown';
  const nemotronStatus = details?.nemotron ?? 'unknown';

  return {
    rtdetr: {
      name: 'RT-DETRv2',
      status: rtdetrStatus === 'healthy' ? 'healthy' : rtdetrStatus === 'unknown' ? 'unknown' : 'unhealthy',
      message: rtdetrStatus !== 'healthy' && rtdetrStatus !== 'unknown' ? rtdetrStatus : undefined,
    },
    nemotron: {
      name: 'Nemotron',
      status: nemotronStatus === 'healthy' ? 'healthy' : nemotronStatus === 'unknown' ? 'unknown' : 'unhealthy',
      message: nemotronStatus !== 'healthy' && nemotronStatus !== 'unknown' ? nemotronStatus : undefined,
    },
  };
}

/**
 * useAIMetrics - Hook for fetching and managing AI performance metrics
 *
 * Combines data from multiple API endpoints into a unified state:
 * - Prometheus metrics for detailed histograms
 * - Telemetry API for queue depths
 * - Health API for service status
 * - Pipeline latency API for stage timings
 *
 * @param options - Configuration options
 * @returns AI metrics state, loading/error status, and refresh function
 *
 * @example
 * ```tsx
 * const { data, isLoading, error, refresh } = useAIMetrics({
 *   pollingInterval: 5000,
 * });
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error} />;
 *
 * return <AIPerformanceDashboard metrics={data} />;
 * ```
 */
export function useAIMetrics(options: UseAIMetricsOptions = {}): UseAIMetricsResult {
  const { pollingInterval = 5000, enablePolling = true } = options;

  const [data, setData] = useState<AIPerformanceState>(initialState);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track if component is mounted to avoid state updates after unmount
  const mountedRef = useRef(true);

  /**
   * Fetch all metrics and combine into state
   */
  const fetchAllMetrics = useCallback(async () => {
    try {
      // Fetch all data sources in parallel
      const [metricsResult, telemetryResult, healthResult, pipelineResult, dlqStatsResult] = await Promise.allSettled([
        fetchAIMetrics(),
        fetchTelemetry(),
        fetchHealth(),
        fetchPipelineLatency(60),
        fetchDlqStats(),
      ]);

      if (!mountedRef.current) return;

      // Extract successful results with fallbacks
      const metrics: AIMetrics | null =
        metricsResult.status === 'fulfilled' ? metricsResult.value : null;
      const telemetry: TelemetryResponse | null =
        telemetryResult.status === 'fulfilled' ? telemetryResult.value : null;
      const health: HealthResponse | null =
        healthResult.status === 'fulfilled' ? healthResult.value : null;
      const pipelineLatency: PipelineLatencyResponse | null =
        pipelineResult.status === 'fulfilled' ? pipelineResult.value : null;
      const dlqStats: DLQStatsResponse | null =
        dlqStatsResult.status === 'fulfilled' ? dlqStatsResult.value : null;

      // Extract AI model statuses
      const { rtdetr, nemotron } = extractAIStatuses(health);

      // Build DLQ items from API stats (preferred) or fall back to Prometheus metrics
      // The DLQ stats API returns the actual current count, while Prometheus metrics
      // track cumulative "items moved to DLQ" which is less accurate for current state
      let dlqItems: Record<string, number>;
      if (dlqStats && (dlqStats.detection_queue_count > 0 || dlqStats.analysis_queue_count > 0 || dlqStats.total_count > 0)) {
        dlqItems = {};
        if (dlqStats.detection_queue_count > 0) {
          dlqItems['dlq:detection_queue'] = dlqStats.detection_queue_count;
        }
        if (dlqStats.analysis_queue_count > 0) {
          dlqItems['dlq:analysis_queue'] = dlqStats.analysis_queue_count;
        }
      } else {
        // Fall back to Prometheus metrics if DLQ stats API failed or returned zeros
        dlqItems = metrics?.dlq_items ?? {};
      }

      // Combine all metrics into state
      setData({
        rtdetr,
        nemotron,
        detectionLatency: metrics?.detection_latency ?? null,
        analysisLatency: metrics?.analysis_latency ?? null,
        pipelineLatency,
        totalDetections: metrics?.total_detections ?? 0,
        totalEvents: metrics?.total_events ?? 0,
        detectionQueueDepth: telemetry?.queues?.detection_queue ?? metrics?.detection_queue_depth ?? 0,
        analysisQueueDepth: telemetry?.queues?.analysis_queue ?? metrics?.analysis_queue_depth ?? 0,
        pipelineErrors: metrics?.pipeline_errors ?? {},
        queueOverflows: metrics?.queue_overflows ?? {},
        dlqItems,
        lastUpdated: new Date().toISOString(),
      });

      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;

      const message = err instanceof Error ? err.message : 'Failed to fetch AI metrics';
      setError(message);
      console.error('Error fetching AI metrics:', err);
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  /**
   * Manual refresh function
   */
  const refresh = useCallback(async () => {
    setIsLoading(true);
    await fetchAllMetrics();
  }, [fetchAllMetrics]);

  // Initial fetch and polling setup
  useEffect(() => {
    mountedRef.current = true;

    // Initial fetch
    void fetchAllMetrics();

    // Set up polling if enabled
    let intervalId: ReturnType<typeof setInterval> | null = null;
    if (enablePolling && pollingInterval > 0) {
      intervalId = setInterval(() => {
        void fetchAllMetrics();
      }, pollingInterval);
    }

    return () => {
      mountedRef.current = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [fetchAllMetrics, enablePolling, pollingInterval]);

  return { data, isLoading, error, refresh };
}

export default useAIMetrics;
