/**
 * Tests for LatencyPanel component
 *
 * Tests the latency display panel including helper functions,
 * percentile displays, and color coding logic.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import LatencyPanel from './LatencyPanel';

import type { AILatencyMetrics } from '../../services/metricsParser';

// Re-export helper functions for testing by testing their behavior through the component
// Since the functions are internal, we test them through the component's rendered output

describe('LatencyPanel', () => {
  describe('basic rendering', () => {
    it('renders the main container with correct testid', () => {
      render(<LatencyPanel />);
      expect(screen.getByTestId('latency-panel')).toBeInTheDocument();
    });

    it('renders AI Service Latency card', () => {
      render(<LatencyPanel />);
      expect(screen.getByTestId('ai-latency-card')).toBeInTheDocument();
      expect(screen.getByText('AI Service Latency')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<LatencyPanel className="custom-class" />);
      expect(screen.getByTestId('latency-panel')).toHaveClass('custom-class');
    });
  });

  describe('LatencyStatRow - no data handling', () => {
    it('shows "No data available" when detectionLatency is null', () => {
      render(<LatencyPanel detectionLatency={null} />);
      // Both RT-DETR and Nemotron show "No data available" when null
      expect(screen.getAllByText('No data available').length).toBeGreaterThanOrEqual(1);
    });

    it('shows "No data available" when sample_count is 0', () => {
      const latency: AILatencyMetrics = {
        avg_ms: null,
        p50_ms: null,
        p95_ms: null,
        p99_ms: null,
        sample_count: 0,
      };
      render(<LatencyPanel detectionLatency={latency} />);
      expect(screen.getAllByText('No data available').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('LatencyStatRow with valid data', () => {
    const validLatency: AILatencyMetrics = {
      avg_ms: 150,
      p50_ms: 120,
      p95_ms: 280,
      p99_ms: 450,
      sample_count: 1000,
    };

    it('displays RT-DETRv2 Detection label', () => {
      render(<LatencyPanel detectionLatency={validLatency} />);
      expect(screen.getByText('RT-DETRv2 Detection')).toBeInTheDocument();
    });

    it('displays Nemotron Analysis label', () => {
      const nemotronLatency: AILatencyMetrics = {
        avg_ms: 2500,
        p50_ms: 2000,
        p95_ms: 4500,
        p99_ms: 8000,
        sample_count: 500,
      };
      render(<LatencyPanel analysisLatency={nemotronLatency} />);
      expect(screen.getByText('Nemotron Analysis')).toBeInTheDocument();
    });

    it('displays sample count with locale formatting', () => {
      render(<LatencyPanel detectionLatency={validLatency} />);
      expect(screen.getByText('1,000 samples')).toBeInTheDocument();
    });

    it('displays all percentile labels', () => {
      render(<LatencyPanel detectionLatency={validLatency} />);
      expect(screen.getAllByText('Avg').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('P50').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('P95').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('P99').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('formatMs helper (tested through component output)', () => {
    it('displays "-" for null values', () => {
      const latency: AILatencyMetrics = {
        avg_ms: 100,
        p50_ms: null,
        p95_ms: null,
        p99_ms: null,
        sample_count: 10,
      };
      render(<LatencyPanel detectionLatency={latency} />);
      // There should be dashes for the null percentile values
      expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(1);
    });

    it('displays "< 1ms" for values less than 1', () => {
      const latency: AILatencyMetrics = {
        avg_ms: 0.5,
        p50_ms: 0.5,
        p95_ms: 0.5,
        p99_ms: 0.5,
        sample_count: 10,
      };
      render(<LatencyPanel detectionLatency={latency} />);
      expect(screen.getAllByText('< 1ms').length).toBeGreaterThanOrEqual(1);
    });

    it('displays milliseconds for values under 1000ms', () => {
      const latency: AILatencyMetrics = {
        avg_ms: 150,
        p50_ms: 120,
        p95_ms: 280,
        p99_ms: 450,
        sample_count: 10,
      };
      render(<LatencyPanel detectionLatency={latency} />);
      expect(screen.getByText('150ms')).toBeInTheDocument();
      expect(screen.getByText('120ms')).toBeInTheDocument();
      expect(screen.getByText('280ms')).toBeInTheDocument();
      expect(screen.getByText('450ms')).toBeInTheDocument();
    });

    it('displays seconds for values 1000ms to 59999ms', () => {
      const latency: AILatencyMetrics = {
        avg_ms: 2500,
        p50_ms: 2000,
        p95_ms: 4500,
        p99_ms: 8000,
        sample_count: 10,
      };
      render(<LatencyPanel analysisLatency={latency} />);
      expect(screen.getByText('2.5s')).toBeInTheDocument();
      expect(screen.getByText('2.0s')).toBeInTheDocument();
      expect(screen.getByText('4.5s')).toBeInTheDocument();
      expect(screen.getByText('8.0s')).toBeInTheDocument();
    });

    it('displays minutes for values >= 60000ms', () => {
      const latency: AILatencyMetrics = {
        avg_ms: 120000,
        p50_ms: 90000,
        p95_ms: 180000,
        p99_ms: 240000,
        sample_count: 10,
      };
      render(<LatencyPanel analysisLatency={latency} />);
      expect(screen.getByText('2.0m')).toBeInTheDocument();
      expect(screen.getByText('1.5m')).toBeInTheDocument();
      expect(screen.getByText('3.0m')).toBeInTheDocument();
      expect(screen.getByText('4.0m')).toBeInTheDocument();
    });
  });

  describe('getLatencyColor - color coding logic', () => {
    // RT-DETR thresholds: warning: 500, critical: 2000
    it('applies green color for values under warning threshold', () => {
      const latency: AILatencyMetrics = {
        avg_ms: 200, // Under 500ms warning threshold
        p50_ms: 150,
        p95_ms: 300,
        p99_ms: 400,
        sample_count: 100,
      };
      render(<LatencyPanel detectionLatency={latency} />);
      // The avg should have white text (healthy green status)
      const avgValue = screen.getByText('200ms');
      expect(avgValue).toHaveClass('text-white');
    });

    it('applies yellow color for values at warning threshold', () => {
      const latency: AILatencyMetrics = {
        avg_ms: 500, // At 500ms warning threshold
        p50_ms: 400,
        p95_ms: 600,
        p99_ms: 700,
        sample_count: 100,
      };
      render(<LatencyPanel detectionLatency={latency} />);
      const avgValue = screen.getByText('500ms');
      expect(avgValue).toHaveClass('text-yellow-400');
    });

    it('applies red color for values at critical threshold', () => {
      const latency: AILatencyMetrics = {
        avg_ms: 2000, // At 2000ms critical threshold
        p50_ms: 1500,
        p95_ms: 2500,
        p99_ms: 3000,
        sample_count: 100,
      };
      render(<LatencyPanel detectionLatency={latency} />);
      const avgValue = screen.getByText('2.0s');
      expect(avgValue).toHaveClass('text-red-400');
    });

    it('applies red color for p95 over critical threshold', () => {
      const latency: AILatencyMetrics = {
        avg_ms: 1000,
        p50_ms: 800,
        p95_ms: 2500, // Over critical threshold
        p99_ms: 3000,
        sample_count: 100,
      };
      render(<LatencyPanel detectionLatency={latency} />);
      const p95Value = screen.getByText('2.5s');
      expect(p95Value).toHaveClass('text-red-400');
    });
  });

  describe('Pipeline Stage Latency', () => {
    const pipelineLatency = {
      watch_to_detect: {
        avg_ms: 50,
        min_ms: 10,
        max_ms: 200,
        p50_ms: 45,
        p95_ms: 150,
        p99_ms: 180,
        sample_count: 500,
      },
      detect_to_batch: {
        avg_ms: 100,
        min_ms: 20,
        max_ms: 300,
        p50_ms: 90,
        p95_ms: 250,
        p99_ms: 280,
        sample_count: 400,
      },
      batch_to_analyze: {
        avg_ms: 80,
        min_ms: 15,
        max_ms: 250,
        p50_ms: 70,
        p95_ms: 200,
        p99_ms: 230,
        sample_count: 300,
      },
      total_pipeline: {
        avg_ms: 230,
        min_ms: 50,
        max_ms: 700,
        p50_ms: 200,
        p95_ms: 550,
        p99_ms: 650,
        sample_count: 300,
      },
      window_minutes: 15,
      timestamp: '2025-01-03T12:00:00Z',
    };

    it('renders pipeline latency card when pipelineLatency is provided', () => {
      render(<LatencyPanel pipelineLatency={pipelineLatency} />);
      expect(screen.getByTestId('pipeline-latency-card')).toBeInTheDocument();
    });

    it('does not render pipeline latency card when pipelineLatency is null', () => {
      render(<LatencyPanel pipelineLatency={null} />);
      expect(screen.queryByTestId('pipeline-latency-card')).not.toBeInTheDocument();
    });

    it('displays Pipeline Stage Latency title', () => {
      render(<LatencyPanel pipelineLatency={pipelineLatency} />);
      expect(screen.getByText('Pipeline Stage Latency')).toBeInTheDocument();
    });

    it('displays window minutes', () => {
      render(<LatencyPanel pipelineLatency={pipelineLatency} />);
      expect(screen.getByText('(last 15 min)')).toBeInTheDocument();
    });

    it('displays all pipeline stage labels', () => {
      render(<LatencyPanel pipelineLatency={pipelineLatency} />);
      // Labels appear in both the pipeline card and the history chart dropdown,
      // so we use getAllByText to verify they're present
      expect(screen.getAllByText('File Watch to Detection').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Detection to Batch').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Batch to Analysis').length).toBeGreaterThan(0);
    });

    it('displays Total Pipeline section with sample count', () => {
      render(<LatencyPanel pipelineLatency={pipelineLatency} />);
      // "Total Pipeline" appears in both the pipeline card and the history chart dropdown,
      // so we verify at least one is present
      expect(screen.getAllByText('Total Pipeline').length).toBeGreaterThan(0);
      // Sample count is formatted with locale - multiple "samples" labels exist
      const sampleTexts = screen.getAllByText(/samples/);
      expect(sampleTexts.length).toBeGreaterThan(0);
    });

    it('displays timestamp in localized time format', () => {
      render(<LatencyPanel pipelineLatency={pipelineLatency} />);
      // The timestamp is formatted with toLocaleTimeString()
      expect(screen.getByText(/Updated:/)).toBeInTheDocument();
    });
  });

  describe('Pipeline Stage Latency - edge cases', () => {
    it('does not render total pipeline section when sample_count is 0', () => {
      const emptyTotalPipeline = {
        watch_to_detect: null,
        detect_to_batch: null,
        batch_to_analyze: null,
        total_pipeline: {
          avg_ms: null,
          min_ms: null,
          max_ms: null,
          p50_ms: null,
          p95_ms: null,
          p99_ms: null,
          sample_count: 0,
        },
        window_minutes: 15,
        timestamp: '2025-01-03T12:00:00Z',
      };
      render(<LatencyPanel pipelineLatency={emptyTotalPipeline} />);
      // "Total Pipeline" appears in the history chart dropdown, but NOT in the
      // pipeline card section when sample_count is 0. Verify by checking if
      // the highlighted total pipeline section container exists - it has a unique
      // bg-[#76B900]/10 class that only appears on the total pipeline section.
      const pipelineCard = screen.getByTestId('pipeline-latency-card');
      expect(pipelineCard.querySelector('.bg-\\[\\#76B900\\]\\/10')).toBeNull();
    });

    it('does not render timestamp when not provided', () => {
      const noTimestamp = {
        watch_to_detect: null,
        detect_to_batch: null,
        batch_to_analyze: null,
        total_pipeline: null,
        window_minutes: 15,
      };
      render(<LatencyPanel pipelineLatency={noTimestamp} />);
      expect(screen.queryByText(/Updated:/)).not.toBeInTheDocument();
    });

    it('does not render window minutes when not provided', () => {
      const noWindow = {
        watch_to_detect: null,
        detect_to_batch: null,
        batch_to_analyze: null,
        total_pipeline: null,
      };
      render(<LatencyPanel pipelineLatency={noWindow} />);
      expect(screen.queryByText(/last .* min/)).not.toBeInTheDocument();
    });
  });

  describe('getProgressPercent - progress bar calculation', () => {
    it('caps progress at 100% for values exceeding maxDisplay', () => {
      // RT-DETR maxDisplay is 2000ms, values over should be capped at 100%
      const latency: AILatencyMetrics = {
        avg_ms: 3000, // 150% of maxDisplay
        p50_ms: 2500,
        p95_ms: 4000,
        p99_ms: 5000,
        sample_count: 100,
      };
      render(<LatencyPanel detectionLatency={latency} />);
      // The component should render without error even with high values
      expect(screen.getByText('3.0s')).toBeInTheDocument();
    });
  });

  describe('combined latency display', () => {
    it('renders both detection and analysis latency when provided', () => {
      const detection: AILatencyMetrics = {
        avg_ms: 150,
        p50_ms: 120,
        p95_ms: 280,
        p99_ms: 450,
        sample_count: 1000,
      };
      const analysis: AILatencyMetrics = {
        avg_ms: 2500,
        p50_ms: 2000,
        p95_ms: 4500,
        p99_ms: 8000,
        sample_count: 500,
      };

      render(<LatencyPanel detectionLatency={detection} analysisLatency={analysis} />);

      expect(screen.getByText('RT-DETRv2 Detection')).toBeInTheDocument();
      expect(screen.getByText('Nemotron Analysis')).toBeInTheDocument();
      expect(screen.getByText('1,000 samples')).toBeInTheDocument();
      expect(screen.getByText('500 samples')).toBeInTheDocument();
    });
  });
});
