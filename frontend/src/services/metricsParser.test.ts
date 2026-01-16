/**
 * Tests for the Prometheus metrics parser
 */

import { describe, expect, it } from 'vitest';

import {
  parseMetricLine,
  parseMetrics,
  extractHistogram,
  calculatePercentile,
  histogramToLatencyMetrics,
  getGaugeValue,
  getCountersByLabel,
  parseAIMetrics,
} from './metricsParser';

import type { ParsedMetric } from './metricsParser';

describe('metricsParser', () => {
  describe('parseMetricLine', () => {
    it('parses a simple gauge metric', () => {
      const result = parseMetricLine('hsi_detection_queue_depth 5.0');
      expect(result).toEqual({
        name: 'hsi_detection_queue_depth',
        labels: {},
        value: 5.0,
      });
    });

    it('parses a metric with labels', () => {
      const result = parseMetricLine(
        'hsi_stage_duration_seconds_bucket{stage="detect",le="0.1"} 45.0'
      );
      expect(result).toEqual({
        name: 'hsi_stage_duration_seconds_bucket',
        labels: { stage: 'detect', le: '0.1' },
        value: 45.0,
      });
    });

    it('parses +Inf as Infinity', () => {
      const result = parseMetricLine(
        'hsi_stage_duration_seconds_bucket{stage="detect",le="+Inf"} 100'
      );
      expect(result?.value).toBe(100);
      expect(result?.labels['le']).toBe('+Inf');
    });

    it('returns null for comment lines', () => {
      expect(parseMetricLine('# HELP hsi_detection_queue_depth Description')).toBeNull();
      expect(parseMetricLine('# TYPE hsi_detection_queue_depth gauge')).toBeNull();
    });

    it('returns null for empty lines', () => {
      expect(parseMetricLine('')).toBeNull();
      expect(parseMetricLine('   ')).toBeNull();
    });

    it('handles scientific notation', () => {
      const result = parseMetricLine('metric_name 1.5e-3');
      expect(result?.value).toBeCloseTo(0.0015);
    });

    it('handles negative values', () => {
      const result = parseMetricLine('metric_name -42.5');
      expect(result?.value).toBe(-42.5);
    });
  });

  describe('parseMetrics', () => {
    it('parses multiple metrics from text', () => {
      const text = `
# HELP hsi_detection_queue_depth Number of images waiting
# TYPE hsi_detection_queue_depth gauge
hsi_detection_queue_depth 5
# TYPE hsi_analysis_queue_depth gauge
hsi_analysis_queue_depth 3
      `;
      const results = parseMetrics(text);
      expect(results).toHaveLength(2);
      expect(results[0].name).toBe('hsi_detection_queue_depth');
      expect(results[0].value).toBe(5);
      expect(results[1].name).toBe('hsi_analysis_queue_depth');
      expect(results[1].value).toBe(3);
    });

    it('handles histogram metrics', () => {
      const text = `
hsi_stage_duration_seconds_bucket{stage="detect",le="0.1"} 45
hsi_stage_duration_seconds_bucket{stage="detect",le="0.5"} 90
hsi_stage_duration_seconds_bucket{stage="detect",le="+Inf"} 100
hsi_stage_duration_seconds_sum{stage="detect"} 25.5
hsi_stage_duration_seconds_count{stage="detect"} 100
      `;
      const results = parseMetrics(text);
      expect(results).toHaveLength(5);
    });
  });

  describe('extractHistogram', () => {
    const sampleHistogramText = `
hsi_stage_duration_seconds_bucket{stage="detect",le="0.1"} 45
hsi_stage_duration_seconds_bucket{stage="detect",le="0.5"} 90
hsi_stage_duration_seconds_bucket{stage="detect",le="1.0"} 95
hsi_stage_duration_seconds_bucket{stage="detect",le="+Inf"} 100
hsi_stage_duration_seconds_sum{stage="detect"} 25.5
hsi_stage_duration_seconds_count{stage="detect"} 100
hsi_stage_duration_seconds_bucket{stage="analyze",le="1.0"} 50
hsi_stage_duration_seconds_sum{stage="analyze"} 100.0
hsi_stage_duration_seconds_count{stage="analyze"} 50
    `;

    it('extracts histogram for a specific label', () => {
      const metrics = parseMetrics(sampleHistogramText);
      const histogram = extractHistogram(metrics, 'hsi_stage_duration_seconds', {
        stage: 'detect',
      });

      expect(histogram).not.toBeNull();
      expect(histogram!.count).toBe(100);
      expect(histogram!.sum).toBe(25.5);
      expect(histogram!.buckets).toHaveLength(4);
      expect(histogram!.buckets[0]).toEqual({ le: 0.1, count: 45 });
    });

    it('returns null when histogram not found', () => {
      const metrics = parseMetrics(sampleHistogramText);
      const histogram = extractHistogram(metrics, 'nonexistent_metric', {});
      expect(histogram).toBeNull();
    });

    it('filters by label correctly', () => {
      const metrics = parseMetrics(sampleHistogramText);
      const detectHistogram = extractHistogram(metrics, 'hsi_stage_duration_seconds', {
        stage: 'detect',
      });
      const analyzeHistogram = extractHistogram(metrics, 'hsi_stage_duration_seconds', {
        stage: 'analyze',
      });

      expect(detectHistogram!.count).toBe(100);
      expect(analyzeHistogram!.count).toBe(50);
    });
  });

  describe('calculatePercentile', () => {
    it('calculates percentiles from buckets', () => {
      const histogram = {
        buckets: [
          { le: 0.1, count: 50 },
          { le: 0.5, count: 90 },
          { le: 1.0, count: 100 },
        ],
        sum: 30,
        count: 100,
      };

      const p50 = calculatePercentile(histogram, 50);
      expect(p50).toBeCloseTo(0.1);

      const p90 = calculatePercentile(histogram, 90);
      expect(p90).toBeCloseTo(0.5);

      const p95 = calculatePercentile(histogram, 95);
      // Should interpolate between 0.5 and 1.0
      expect(p95).toBeGreaterThan(0.5);
      expect(p95).toBeLessThan(1.0);
    });

    it('returns null for empty histogram', () => {
      const histogram = {
        buckets: [],
        sum: 0,
        count: 0,
      };
      expect(calculatePercentile(histogram, 50)).toBeNull();
    });
  });

  describe('histogramToLatencyMetrics', () => {
    it('converts histogram to latency metrics in milliseconds', () => {
      const histogram = {
        buckets: [
          { le: 0.1, count: 50 },
          { le: 0.5, count: 95 },
          { le: 1.0, count: 100 },
        ],
        sum: 30,
        count: 100,
      };

      const metrics = histogramToLatencyMetrics(histogram);
      expect(metrics).not.toBeNull();
      expect(metrics!.avg_ms).toBe(300); // 30/100 * 1000
      expect(metrics!.sample_count).toBe(100);
      expect(metrics!.p50_ms).toBeCloseTo(100); // 0.1s * 1000
    });

    it('returns null for null histogram', () => {
      expect(histogramToLatencyMetrics(null)).toBeNull();
    });

    it('returns null for empty histogram', () => {
      expect(histogramToLatencyMetrics({ buckets: [], sum: 0, count: 0 })).toBeNull();
    });
  });

  describe('getGaugeValue', () => {
    it('returns gauge value when found', () => {
      const metrics = [
        { name: 'metric_a', labels: {}, value: 42 },
        { name: 'metric_b', labels: {}, value: 100 },
      ];
      expect(getGaugeValue(metrics, 'metric_a')).toBe(42);
    });

    it('returns 0 when not found', () => {
      const metrics = [{ name: 'metric_a', labels: {}, value: 42 }];
      expect(getGaugeValue(metrics, 'nonexistent')).toBe(0);
    });
  });

  describe('getCountersByLabel', () => {
    it('groups counters by label', () => {
      const metrics: ParsedMetric[] = [
        { name: 'errors_total', labels: { error_type: 'timeout' }, value: 5 },
        { name: 'errors_total', labels: { error_type: 'connection' }, value: 3 },
        { name: 'other_metric', labels: {}, value: 100 },
      ];

      const result = getCountersByLabel(metrics, 'errors_total', 'error_type');
      expect(result).toEqual({
        timeout: 5,
        connection: 3,
      });
    });

    it('returns empty object when no matches', () => {
      const metrics = [{ name: 'other_metric', labels: {}, value: 100 }];
      const result = getCountersByLabel(metrics, 'errors_total', 'error_type');
      expect(result).toEqual({});
    });
  });

  describe('parseAIMetrics', () => {
    it('parses a complete metrics response', () => {
      const text = `
# HELP hsi_detection_queue_depth Number of images waiting
# TYPE hsi_detection_queue_depth gauge
hsi_detection_queue_depth 5
hsi_analysis_queue_depth 3
hsi_detections_processed_total 1000
hsi_events_created_total 250
hsi_pipeline_errors_total{error_type="timeout"} 2
hsi_pipeline_errors_total{error_type="connection"} 1
hsi_ai_request_duration_seconds_bucket{service="rtdetr",le="0.1"} 80
hsi_ai_request_duration_seconds_bucket{service="rtdetr",le="0.5"} 95
hsi_ai_request_duration_seconds_bucket{service="rtdetr",le="+Inf"} 100
hsi_ai_request_duration_seconds_sum{service="rtdetr"} 20.5
hsi_ai_request_duration_seconds_count{service="rtdetr"} 100
      `;

      const result = parseAIMetrics(text);

      expect(result.detection_queue_depth).toBe(5);
      expect(result.analysis_queue_depth).toBe(3);
      expect(result.total_detections).toBe(1000);
      expect(result.total_events).toBe(250);
      expect(result.pipeline_errors).toEqual({
        timeout: 2,
        connection: 1,
      });
      expect(result.detection_latency).not.toBeNull();
      expect(result.detection_latency!.avg_ms).toBe(205); // 20.5/100 * 1000
      expect(result.timestamp).toBeTruthy();
    });

    it('handles empty metrics gracefully', () => {
      const result = parseAIMetrics('');

      expect(result.detection_queue_depth).toBe(0);
      expect(result.analysis_queue_depth).toBe(0);
      expect(result.total_detections).toBe(0);
      expect(result.total_events).toBe(0);
      expect(result.detection_latency).toBeNull();
      expect(result.analysis_latency).toBeNull();
    });
  });
});
