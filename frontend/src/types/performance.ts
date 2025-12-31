/**
 * Performance metrics type definitions for the System Performance Dashboard.
 *
 * These types are used by the frontend components to display performance alerts,
 * AI model metrics, and other system monitoring data.
 *
 * @see docs/plans/2025-12-31-system-performance-design.md
 */

/**
 * Performance alert for threshold breaches.
 * Alerts are computed server-side and included in WebSocket messages.
 */
export interface PerformanceAlert {
  /** Alert severity level */
  severity: 'warning' | 'critical';
  /** Metric name that triggered the alert (e.g., 'gpu_temperature', 'redis_memory') */
  metric: string;
  /** Current value of the metric */
  value: number;
  /** Threshold that was breached */
  threshold: number;
  /** Human-readable alert message */
  message: string;
}

/**
 * RT-DETRv2 object detection model metrics.
 */
export interface AiModelMetrics {
  /** Model status (e.g., 'healthy', 'unhealthy', 'loading') */
  status: string;
  /** VRAM usage in GB */
  vram_gb: number;
  /** Model name/variant (e.g., 'rtdetr_r50vd_coco_o365') */
  model: string;
  /** CUDA device (e.g., 'cuda:0') */
  device: string;
}

/**
 * Nemotron LLM model metrics.
 */
export interface NemotronMetrics {
  /** Model status (e.g., 'healthy', 'unhealthy', 'loading') */
  status: string;
  /** Number of active inference slots */
  slots_active: number;
  /** Total number of inference slots */
  slots_total: number;
  /** Context window size in tokens */
  context_size: number;
}

/**
 * Time range options for historical metrics.
 * Maps to resolution: 5m=5s, 15m=15s, 60m=1min
 */
export type TimeRange = '5m' | '15m' | '60m';
