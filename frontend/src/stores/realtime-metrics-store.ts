/**
 * Real-time Metrics State Management Store (NEM-3403, NEM-3426)
 *
 * Provides central state management for high-frequency real-time metrics
 * received via WebSocket. Uses advanced Zustand patterns to optimize
 * performance and prevent unnecessary re-renders:
 *
 * - subscribeWithSelector for fine-grained component subscriptions
 * - Transient update batching for rapid WebSocket events
 * - Immer for clean immutable updates
 *
 * Designed for metrics that update frequently (e.g., GPU stats, pipeline metrics)
 * where minimizing re-renders is critical for UI performance.
 */

import { useShallow } from 'zustand/react/shallow';

import {
  createImmerSelectorStore,
  createTransientSlice,
  createWebSocketEventHandler,
  type Draft,
  type ImmerSetState,
  type TransientSlice,
} from './middleware';

// ============================================================================
// Types
// ============================================================================

/**
 * GPU metrics from the monitoring system.
 */
export interface GPUMetrics {
  /** GPU utilization percentage (0-100) */
  utilization: number;
  /** Memory used in bytes */
  memoryUsed: number;
  /** Total GPU memory in bytes */
  memoryTotal: number;
  /** Memory utilization percentage (0-100) */
  memoryUtilization: number;
  /** GPU temperature in Celsius */
  temperature: number;
  /** Power draw in watts */
  powerDraw: number;
  /** Power limit in watts */
  powerLimit: number;
}

/**
 * Pipeline performance metrics.
 */
export interface PipelineMetrics {
  /** Detection queue depth */
  detectionQueueDepth: number;
  /** Analysis queue depth */
  analysisQueueDepth: number;
  /** Current throughput (items/second) */
  throughput: number;
  /** Average latency in milliseconds */
  averageLatency: number;
  /** P95 latency in milliseconds */
  p95Latency: number;
  /** P99 latency in milliseconds */
  p99Latency: number;
  /** Error rate (0-1) */
  errorRate: number;
}

/**
 * Inference metrics from AI models.
 */
export interface InferenceMetrics {
  /** RT-DETR model latency in milliseconds */
  rtdetrLatency: number;
  /** RT-DETR inference count */
  rtdetrInferenceCount: number;
  /** Nemotron model latency in milliseconds */
  nemotronLatency: number;
  /** Nemotron inference count */
  nemotronInferenceCount: number;
  /** Batch size currently in use */
  currentBatchSize: number;
}

/**
 * Real-time metrics store state and actions.
 */
export interface RealtimeMetricsState {
  /** Transient GPU metrics - updates frequently */
  gpu: TransientSlice<GPUMetrics>;
  /** Transient pipeline metrics - updates frequently */
  pipeline: TransientSlice<PipelineMetrics>;
  /** Transient inference metrics - updates frequently */
  inference: TransientSlice<InferenceMetrics>;

  // Actions
  /** Update GPU metrics (batched internally) */
  updateGPU: (metrics: Partial<GPUMetrics>) => void;
  /** Update pipeline metrics (batched internally) */
  updatePipeline: (metrics: Partial<PipelineMetrics>) => void;
  /** Update inference metrics (batched internally) */
  updateInference: (metrics: Partial<InferenceMetrics>) => void;
  /** Reset all metrics to initial values */
  clear: () => void;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Initial GPU metrics.
 */
const INITIAL_GPU_METRICS: GPUMetrics = {
  utilization: 0,
  memoryUsed: 0,
  memoryTotal: 0,
  memoryUtilization: 0,
  temperature: 0,
  powerDraw: 0,
  powerLimit: 0,
};

/**
 * Initial pipeline metrics.
 */
const INITIAL_PIPELINE_METRICS: PipelineMetrics = {
  detectionQueueDepth: 0,
  analysisQueueDepth: 0,
  throughput: 0,
  averageLatency: 0,
  p95Latency: 0,
  p99Latency: 0,
  errorRate: 0,
};

/**
 * Initial inference metrics.
 */
const INITIAL_INFERENCE_METRICS: InferenceMetrics = {
  rtdetrLatency: 0,
  rtdetrInferenceCount: 0,
  nemotronLatency: 0,
  nemotronInferenceCount: 0,
  currentBatchSize: 0,
};

// ============================================================================
// Store
// ============================================================================

/**
 * Zustand store for real-time metrics with optimized high-frequency updates.
 *
 * Features:
 * - Transient slices for frequently updating data
 * - subscribeWithSelector for fine-grained component subscriptions
 * - Batched updates to prevent render thrashing
 * - Immer for clean state updates
 *
 * @example
 * ```tsx
 * import { useRealtimeMetricsStore } from '@/stores/realtime-metrics-store';
 *
 * // Subscribe only to GPU utilization - won't re-render on temperature changes
 * const gpuUtil = useRealtimeMetricsStore((state) => state.gpu.data.utilization);
 *
 * // Subscribe to multiple metrics with shallow comparison
 * const { queueDepth, throughput } = useRealtimeMetricsStore(
 *   (state) => ({
 *     queueDepth: state.pipeline.data.detectionQueueDepth,
 *     throughput: state.pipeline.data.throughput,
 *   }),
 *   shallow
 * );
 *
 * // Subscribe to changes programmatically
 * const unsubscribe = useRealtimeMetricsStore.subscribe(
 *   (state) => state.gpu.data.temperature,
 *   (temp, prevTemp) => {
 *     if (temp > 85 && prevTemp <= 85) {
 *       showTemperatureWarning();
 *     }
 *   }
 * );
 * ```
 */
export const useRealtimeMetricsStore = createImmerSelectorStore<RealtimeMetricsState>(
  (set: ImmerSetState<RealtimeMetricsState>) => ({
    gpu: createTransientSlice(INITIAL_GPU_METRICS),
    pipeline: createTransientSlice(INITIAL_PIPELINE_METRICS),
    inference: createTransientSlice(INITIAL_INFERENCE_METRICS),

    updateGPU: (metrics: Partial<GPUMetrics>) => {
      set((state: Draft<RealtimeMetricsState>) => {
        Object.assign(state.gpu.data, metrics);
        state.gpu.lastUpdated = Date.now();
      });
    },

    updatePipeline: (metrics: Partial<PipelineMetrics>) => {
      set((state: Draft<RealtimeMetricsState>) => {
        Object.assign(state.pipeline.data, metrics);
        state.pipeline.lastUpdated = Date.now();
      });
    },

    updateInference: (metrics: Partial<InferenceMetrics>) => {
      set((state: Draft<RealtimeMetricsState>) => {
        Object.assign(state.inference.data, metrics);
        state.inference.lastUpdated = Date.now();
      });
    },

    clear: () => {
      set((state: Draft<RealtimeMetricsState>) => {
        state.gpu = createTransientSlice(INITIAL_GPU_METRICS);
        state.pipeline = createTransientSlice(INITIAL_PIPELINE_METRICS);
        state.inference = createTransientSlice(INITIAL_INFERENCE_METRICS);
      });
    },
  }),
  { name: 'realtime-metrics-store' }
);

// ============================================================================
// WebSocket Event Handlers
// ============================================================================

/**
 * Type for GPU stats WebSocket event payload.
 */
export interface GPUStatsEventPayload {
  gpu_utilization: number;
  memory_used: number;
  memory_total: number;
  memory_utilization: number;
  temperature: number;
  power_draw: number;
  power_limit: number;
}

/**
 * Type for pipeline metrics WebSocket event payload.
 */
export interface PipelineMetricsEventPayload {
  detection_queue_depth: number;
  analysis_queue_depth: number;
  throughput: number;
  average_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  error_rate: number;
}

/**
 * Type for inference metrics WebSocket event payload.
 */
export interface InferenceMetricsEventPayload {
  rtdetr_latency_ms: number;
  rtdetr_inference_count: number;
  nemotron_latency_ms: number;
  nemotron_inference_count: number;
  current_batch_size: number;
}

/**
 * Batched handler for GPU stats WebSocket events.
 *
 * Transforms snake_case WebSocket payload to camelCase state and
 * batches rapid updates (100ms window) to prevent render thrashing.
 *
 * @example
 * ```typescript
 * // In WebSocket event handler
 * websocket.on('gpu_stats', handleGPUStatsEvent);
 * ```
 */
export const handleGPUStatsEvent = createWebSocketEventHandler<
  RealtimeMetricsState,
  GPUStatsEventPayload
>(
  useRealtimeMetricsStore.setState as (
    partial:
      | Partial<RealtimeMetricsState>
      | ((state: RealtimeMetricsState) => Partial<RealtimeMetricsState>)
  ) => void,
  (event) => ({
    gpu: {
      data: {
        ...useRealtimeMetricsStore.getState().gpu.data,
        utilization: event.gpu_utilization,
        memoryUsed: event.memory_used,
        memoryTotal: event.memory_total,
        memoryUtilization: event.memory_utilization,
        temperature: event.temperature,
        powerDraw: event.power_draw,
        powerLimit: event.power_limit,
      },
      lastUpdated: Date.now(),
    },
  }),
  { batchMs: 100, maxBatchSize: 5 }
);

/**
 * Batched handler for pipeline metrics WebSocket events.
 */
export const handlePipelineMetricsEvent = createWebSocketEventHandler<
  RealtimeMetricsState,
  PipelineMetricsEventPayload
>(
  useRealtimeMetricsStore.setState as (
    partial:
      | Partial<RealtimeMetricsState>
      | ((state: RealtimeMetricsState) => Partial<RealtimeMetricsState>)
  ) => void,
  (event) => ({
    pipeline: {
      data: {
        ...useRealtimeMetricsStore.getState().pipeline.data,
        detectionQueueDepth: event.detection_queue_depth,
        analysisQueueDepth: event.analysis_queue_depth,
        throughput: event.throughput,
        averageLatency: event.average_latency_ms,
        p95Latency: event.p95_latency_ms,
        p99Latency: event.p99_latency_ms,
        errorRate: event.error_rate,
      },
      lastUpdated: Date.now(),
    },
  }),
  { batchMs: 100, maxBatchSize: 5 }
);

/**
 * Batched handler for inference metrics WebSocket events.
 */
export const handleInferenceMetricsEvent = createWebSocketEventHandler<
  RealtimeMetricsState,
  InferenceMetricsEventPayload
>(
  useRealtimeMetricsStore.setState as (
    partial:
      | Partial<RealtimeMetricsState>
      | ((state: RealtimeMetricsState) => Partial<RealtimeMetricsState>)
  ) => void,
  (event) => ({
    inference: {
      data: {
        ...useRealtimeMetricsStore.getState().inference.data,
        rtdetrLatency: event.rtdetr_latency_ms,
        rtdetrInferenceCount: event.rtdetr_inference_count,
        nemotronLatency: event.nemotron_latency_ms,
        nemotronInferenceCount: event.nemotron_inference_count,
        currentBatchSize: event.current_batch_size,
      },
      lastUpdated: Date.now(),
    },
  }),
  { batchMs: 100, maxBatchSize: 5 }
);

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for GPU utilization percentage.
 */
export const selectGPUUtilization = (state: RealtimeMetricsState): number => {
  return state.gpu.data.utilization;
};

/**
 * Selector for GPU memory utilization percentage.
 */
export const selectGPUMemoryUtilization = (state: RealtimeMetricsState): number => {
  return state.gpu.data.memoryUtilization;
};

/**
 * Selector for GPU temperature.
 */
export const selectGPUTemperature = (state: RealtimeMetricsState): number => {
  return state.gpu.data.temperature;
};

/**
 * Selector for pipeline throughput.
 */
export const selectPipelineThroughput = (state: RealtimeMetricsState): number => {
  return state.pipeline.data.throughput;
};

/**
 * Selector for total queue depth (detection + analysis).
 */
export const selectTotalQueueDepth = (state: RealtimeMetricsState): number => {
  return state.pipeline.data.detectionQueueDepth + state.pipeline.data.analysisQueueDepth;
};

/**
 * Selector for pipeline error rate.
 */
export const selectPipelineErrorRate = (state: RealtimeMetricsState): number => {
  return state.pipeline.data.errorRate;
};

/**
 * Selector for combined model latency (RT-DETR + Nemotron).
 */
export const selectCombinedModelLatency = (state: RealtimeMetricsState): number => {
  return state.inference.data.rtdetrLatency + state.inference.data.nemotronLatency;
};

/**
 * Selector for GPU health status based on utilization and temperature.
 */
export const selectGPUHealthStatus = (
  state: RealtimeMetricsState
): 'healthy' | 'warning' | 'critical' => {
  const { utilization, temperature, memoryUtilization } = state.gpu.data;

  // Critical: Very high temperature or memory
  if (temperature >= 90 || memoryUtilization >= 95) {
    return 'critical';
  }

  // Warning: High utilization, temperature, or memory
  if (utilization >= 90 || temperature >= 80 || memoryUtilization >= 85) {
    return 'warning';
  }

  return 'healthy';
};

/**
 * Selector for pipeline health status based on queue depth and error rate.
 */
export const selectPipelineHealthStatus = (
  state: RealtimeMetricsState
): 'healthy' | 'warning' | 'critical' => {
  const { detectionQueueDepth, analysisQueueDepth, errorRate } = state.pipeline.data;
  const totalQueueDepth = detectionQueueDepth + analysisQueueDepth;

  // Critical: High error rate or extremely backed up
  if (errorRate >= 0.1 || totalQueueDepth >= 100) {
    return 'critical';
  }

  // Warning: Elevated error rate or queue building
  if (errorRate >= 0.05 || totalQueueDepth >= 50) {
    return 'warning';
  }

  return 'healthy';
};

// ============================================================================
// Shallow Hooks for Selective Subscriptions (NEM-3790)
// ============================================================================

/**
 * Hook to select GPU metrics data with shallow equality.
 *
 * @example
 * ```tsx
 * const { utilization, temperature, memoryUtilization } = useGPUMetrics();
 * ```
 */
export function useGPUMetrics() {
  return useRealtimeMetricsStore(
    useShallow((state) => state.gpu.data)
  );
}

/**
 * Hook to select pipeline metrics data with shallow equality.
 *
 * @example
 * ```tsx
 * const { throughput, errorRate, detectionQueueDepth } = usePipelineMetrics();
 * ```
 */
export function usePipelineMetrics() {
  return useRealtimeMetricsStore(
    useShallow((state) => state.pipeline.data)
  );
}

/**
 * Hook to select inference metrics data with shallow equality.
 *
 * @example
 * ```tsx
 * const { rtdetrLatency, nemotronLatency } = useInferenceMetrics();
 * ```
 */
export function useInferenceMetrics() {
  return useRealtimeMetricsStore(
    useShallow((state) => state.inference.data)
  );
}

/**
 * Hook to select realtime metrics actions only.
 * Actions are stable references and don't cause re-renders.
 *
 * @example
 * ```tsx
 * const { updateGPU, updatePipeline, clear } = useRealtimeMetricsActions();
 * ```
 */
export function useRealtimeMetricsActions() {
  return useRealtimeMetricsStore(
    useShallow((state) => ({
      updateGPU: state.updateGPU,
      updatePipeline: state.updatePipeline,
      updateInference: state.updateInference,
      clear: state.clear,
    }))
  );
}
