/**
 * Prometheus Metrics Parser
 *
 * Parses Prometheus text exposition format and extracts metric values.
 * Used to parse the /api/metrics endpoint response for AI performance metrics.
 *
 * Metric format examples:
 *   # HELP hsi_detection_queue_depth Number of images waiting in detection queue
 *   # TYPE hsi_detection_queue_depth gauge
 *   hsi_detection_queue_depth 5.0
 *
 *   # TYPE hsi_stage_duration_seconds histogram
 *   hsi_stage_duration_seconds_bucket{stage="detect",le="0.1"} 45.0
 *   hsi_stage_duration_seconds_sum{stage="detect"} 12.5
 *   hsi_stage_duration_seconds_count{stage="detect"} 100.0
 */

/**
 * Represents a single parsed metric with its name, labels, and value.
 */
export interface ParsedMetric {
  /** Full metric name (e.g., "hsi_stage_duration_seconds_bucket") */
  name: string;
  /** Labels as key-value pairs (e.g., { stage: "detect", le: "0.1" }) */
  labels: Record<string, string>;
  /** Numeric value of the metric */
  value: number;
}

/**
 * Histogram bucket data structure
 */
export interface HistogramBucket {
  /** Upper bound of the bucket (le label) */
  le: number;
  /** Cumulative count for this bucket */
  count: number;
}

/**
 * Parsed histogram metric with buckets, sum, and count
 */
export interface ParsedHistogram {
  /** Histogram buckets sorted by le value */
  buckets: HistogramBucket[];
  /** Sum of all observed values */
  sum: number;
  /** Total count of observations */
  count: number;
}

/**
 * AI latency metrics extracted from Prometheus histograms
 */
export interface AILatencyMetrics {
  /** Average latency in milliseconds */
  avg_ms: number | null;
  /** Median (p50) latency in milliseconds */
  p50_ms: number | null;
  /** 95th percentile latency in milliseconds */
  p95_ms: number | null;
  /** 99th percentile latency in milliseconds */
  p99_ms: number | null;
  /** Total number of observations */
  sample_count: number;
}

/**
 * Detection class distribution data
 */
export interface DetectionClassCount {
  /** Object class name (e.g., "person", "vehicle") */
  class_name: string;
  /** Count of detections for this class */
  count: number;
}

/**
 * Complete AI metrics parsed from Prometheus endpoint
 */
export interface AIMetrics {
  /** RT-DETR detection latency metrics */
  detection_latency: AILatencyMetrics | null;
  /** Nemotron analysis latency metrics */
  analysis_latency: AILatencyMetrics | null;
  /** Total detections processed counter */
  total_detections: number;
  /** Total events created counter */
  total_events: number;
  /** Detection queue depth */
  detection_queue_depth: number;
  /** Analysis queue depth */
  analysis_queue_depth: number;
  /** Pipeline errors by type */
  pipeline_errors: Record<string, number>;
  /** Queue overflow counts by queue */
  queue_overflows: Record<string, number>;
  /** Items moved to DLQ by queue */
  dlq_items: Record<string, number>;
  /** Raw timestamp of when metrics were fetched */
  timestamp: string;
}

/**
 * Parse a single line of Prometheus text format.
 * Returns null for comment lines, empty lines, or malformed lines.
 *
 * @param line - A single line from Prometheus exposition format
 * @returns ParsedMetric or null
 */
export function parseMetricLine(line: string): ParsedMetric | null {
  // Skip comments and empty lines
  const trimmedLine = line.trim();
  if (!trimmedLine || trimmedLine.startsWith('#')) {
    return null;
  }

  // Match metric name, optional labels, and value
  // Format: metric_name{label1="value1",label2="value2"} 123.45
  // Or: metric_name 123.45
  // Security note: This regex parses Prometheus text format which has a well-defined,
  // constrained syntax. The input is from our own backend /api/metrics endpoint.
  // eslint-disable-next-line security/detect-unsafe-regex
  const regex = /^([a-zA-Z_:][a-zA-Z0-9_:]*)\s*(?:\{([^}]*)\})?\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[+-]?Inf|NaN)$/;
  const match = trimmedLine.match(regex);

  if (!match) {
    return null;
  }

  const [, name, labelsStr, valueStr] = match;

  // Parse labels if present
  const labels: Record<string, string> = {};
  if (labelsStr) {
    // Match label="value" pairs, handling escaped quotes
    const labelRegex = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"/g;
    let labelMatch;
    while ((labelMatch = labelRegex.exec(labelsStr)) !== null) {
      const [, key, value] = labelMatch;
      // Unescape the value
      labels[key] = value.replace(/\\(.)/g, '$1');
    }
  }

  // Parse value
  let value: number;
  if (valueStr === '+Inf' || valueStr === 'Inf') {
    value = Infinity;
  } else if (valueStr === '-Inf') {
    value = -Infinity;
  } else if (valueStr === 'NaN') {
    value = NaN;
  } else {
    value = parseFloat(valueStr);
  }

  return { name, labels, value };
}

/**
 * Parse all metrics from Prometheus text format.
 *
 * @param text - Full Prometheus exposition format text
 * @returns Array of parsed metrics
 */
export function parseMetrics(text: string): ParsedMetric[] {
  const lines = text.split('\n');
  const metrics: ParsedMetric[] = [];

  for (const line of lines) {
    const parsed = parseMetricLine(line);
    if (parsed) {
      metrics.push(parsed);
    }
  }

  return metrics;
}

/**
 * Extract histogram data for a given metric base name and label filter.
 *
 * @param metrics - Array of parsed metrics
 * @param baseName - Base name of the histogram (e.g., "hsi_stage_duration_seconds")
 * @param labelFilter - Labels to filter by (e.g., { stage: "detect" })
 * @returns ParsedHistogram or null if not found
 */
export function extractHistogram(
  metrics: ParsedMetric[],
  baseName: string,
  labelFilter: Record<string, string> = {}
): ParsedHistogram | null {
  const buckets: HistogramBucket[] = [];
  let sum: number | null = null;
  let count: number | null = null;

  for (const metric of metrics) {
    // Check if this metric matches the base name and filter
    const matchesFilter = Object.entries(labelFilter).every(
      ([key, value]) => metric.labels[key] === value
    );

    if (!matchesFilter) continue;

    if (metric.name === `${baseName}_bucket`) {
      const le = metric.labels['le'];
      if (le !== undefined) {
        const leValue = le === '+Inf' ? Infinity : parseFloat(le);
        buckets.push({ le: leValue, count: metric.value });
      }
    } else if (metric.name === `${baseName}_sum`) {
      sum = metric.value;
    } else if (metric.name === `${baseName}_count`) {
      count = metric.value;
    }
  }

  if (buckets.length === 0 || sum === null || count === null) {
    return null;
  }

  // Sort buckets by le value
  buckets.sort((a, b) => a.le - b.le);

  return { buckets, sum, count };
}

/**
 * Calculate percentile from histogram buckets using linear interpolation.
 *
 * @param histogram - Parsed histogram data
 * @param percentile - Percentile to calculate (0-100)
 * @returns Estimated value at the given percentile
 */
export function calculatePercentile(histogram: ParsedHistogram, percentile: number): number | null {
  if (histogram.count === 0) {
    return null;
  }

  const targetCount = (percentile / 100) * histogram.count;

  // Find the bucket containing the target count
  let prevBucket: HistogramBucket | null = null;
  for (const bucket of histogram.buckets) {
    if (bucket.count >= targetCount) {
      if (prevBucket === null) {
        // First bucket contains the target
        // Assume linear distribution from 0 to bucket.le
        return (targetCount / bucket.count) * bucket.le;
      }

      // Linear interpolation between buckets
      const countRange = bucket.count - prevBucket.count;
      if (countRange === 0) {
        return prevBucket.le;
      }

      const fraction = (targetCount - prevBucket.count) / countRange;
      return prevBucket.le + fraction * (bucket.le - prevBucket.le);
    }
    prevBucket = bucket;
  }

  // Target is beyond all buckets (shouldn't happen with +Inf bucket)
  return histogram.sum / histogram.count;
}

/**
 * Convert histogram to latency metrics with percentiles.
 * Converts from seconds to milliseconds.
 *
 * @param histogram - Parsed histogram data
 * @returns AILatencyMetrics with percentiles in milliseconds
 */
export function histogramToLatencyMetrics(histogram: ParsedHistogram | null): AILatencyMetrics | null {
  if (!histogram || histogram.count === 0) {
    return null;
  }

  const avg = (histogram.sum / histogram.count) * 1000; // Convert to ms
  const p50 = calculatePercentile(histogram, 50);
  const p95 = calculatePercentile(histogram, 95);
  const p99 = calculatePercentile(histogram, 99);

  return {
    avg_ms: avg,
    p50_ms: p50 !== null ? p50 * 1000 : null,
    p95_ms: p95 !== null ? p95 * 1000 : null,
    p99_ms: p99 !== null ? p99 * 1000 : null,
    sample_count: histogram.count,
  };
}

/**
 * Get a gauge value by name.
 *
 * @param metrics - Array of parsed metrics
 * @param name - Metric name
 * @returns Metric value or 0 if not found
 */
export function getGaugeValue(metrics: ParsedMetric[], name: string): number {
  const metric = metrics.find((m) => m.name === name);
  return metric?.value ?? 0;
}

/**
 * Get counter values grouped by a label.
 *
 * @param metrics - Array of parsed metrics
 * @param name - Metric name
 * @param labelKey - Label key to group by
 * @returns Record of label values to counter values
 */
export function getCountersByLabel(
  metrics: ParsedMetric[],
  name: string,
  labelKey: string
): Record<string, number> {
  const result: Record<string, number> = {};

  for (const metric of metrics) {
    if (metric.name === name && metric.labels[labelKey]) {
      result[metric.labels[labelKey]] = metric.value;
    }
  }

  return result;
}

/**
 * Parse complete AI metrics from Prometheus text format.
 *
 * @param text - Prometheus exposition format text
 * @returns Complete AI metrics object
 */
export function parseAIMetrics(text: string): AIMetrics {
  const metrics = parseMetrics(text);

  // Extract histograms for AI services
  const detectHistogram = extractHistogram(metrics, 'hsi_ai_request_duration_seconds', {
    service: 'rtdetr',
  });
  const analyzeHistogram = extractHistogram(metrics, 'hsi_ai_request_duration_seconds', {
    service: 'nemotron',
  });

  // Also try stage duration histograms as fallback
  const detectStageHistogram = extractHistogram(metrics, 'hsi_stage_duration_seconds', {
    stage: 'detect',
  });
  const analyzeStageHistogram = extractHistogram(metrics, 'hsi_stage_duration_seconds', {
    stage: 'analyze',
  });

  return {
    detection_latency:
      histogramToLatencyMetrics(detectHistogram) || histogramToLatencyMetrics(detectStageHistogram),
    analysis_latency:
      histogramToLatencyMetrics(analyzeHistogram) || histogramToLatencyMetrics(analyzeStageHistogram),
    total_detections: getGaugeValue(metrics, 'hsi_detections_processed_total'),
    total_events: getGaugeValue(metrics, 'hsi_events_created_total'),
    detection_queue_depth: getGaugeValue(metrics, 'hsi_detection_queue_depth'),
    analysis_queue_depth: getGaugeValue(metrics, 'hsi_analysis_queue_depth'),
    pipeline_errors: getCountersByLabel(metrics, 'hsi_pipeline_errors_total', 'error_type'),
    queue_overflows: getCountersByLabel(metrics, 'hsi_queue_overflow_total', 'queue_name'),
    dlq_items: getCountersByLabel(metrics, 'hsi_queue_items_moved_to_dlq_total', 'queue_name'),
    timestamp: new Date().toISOString(),
  };
}

/**
 * Fetch and parse AI metrics from the /api/metrics endpoint.
 *
 * @returns Parsed AI metrics
 */
export async function fetchAIMetrics(): Promise<AIMetrics> {
  const response = await fetch('/api/metrics');
  if (!response.ok) {
    throw new Error(`Failed to fetch metrics: ${response.status} ${response.statusText}`);
  }

  const text = await response.text();
  return parseAIMetrics(text);
}
