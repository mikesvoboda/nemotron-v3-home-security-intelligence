/**
 * Tests for ModelStatusCards component
 *
 * Tests the model status display including helper functions,
 * status badges, and latency formatting.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ModelStatusCards from './ModelStatusCards';

import type { AIModelStatus } from '../../hooks/useAIMetrics';
import type { AILatencyMetrics } from '../../services/metricsParser';

// Default healthy model statuses for testing
const healthyRtdetr: AIModelStatus = {
  name: 'RT-DETRv2',
  status: 'healthy',
  message: 'Model loaded and ready',
};

const healthyNemotron: AIModelStatus = {
  name: 'Nemotron',
  status: 'healthy',
  message: 'Model loaded and ready',
};

describe('ModelStatusCards', () => {
  describe('basic rendering', () => {
    it('renders the main container with correct testid', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      expect(screen.getByTestId('model-status-cards')).toBeInTheDocument();
    });

    it('renders both RT-DETRv2 and Nemotron cards', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      expect(screen.getByTestId('rtdetr-status-card')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-status-card')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(
        <ModelStatusCards
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          className="custom-class"
        />
      );
      expect(screen.getByTestId('model-status-cards')).toHaveClass('custom-class');
    });
  });

  describe('RT-DETRv2 card content', () => {
    it('displays RT-DETRv2 title', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    });

    it('displays Object Detection description', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      expect(screen.getByText('Object Detection')).toBeInTheDocument();
    });

    it('displays RT-DETRv2 model info', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      expect(screen.getByText('Real-Time Detection Transformer v2')).toBeInTheDocument();
      expect(screen.getByText('COCO + Objects365 pre-trained')).toBeInTheDocument();
    });

    it('displays status message when provided', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      expect(screen.getAllByText('Model loaded and ready').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Nemotron card content', () => {
    it('displays Nemotron title', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });

    it('displays Risk Analysis LLM description', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      expect(screen.getByText('Risk Analysis LLM')).toBeInTheDocument();
    });

    it('displays Nemotron model info', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      expect(screen.getByText('NVIDIA Nemotron Mini 4B Instruct')).toBeInTheDocument();
      expect(screen.getByText('via llama.cpp inference server')).toBeInTheDocument();
    });
  });

  describe('getStatusColor - status badge colors', () => {
    it('displays green badge for healthy status', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      const rtdetrBadge = screen.getByTestId('rtdetr-badge');
      expect(rtdetrBadge).toHaveTextContent('healthy');
    });

    it('displays yellow badge for degraded status', () => {
      const degradedRtdetr: AIModelStatus = {
        name: 'RT-DETRv2',
        status: 'degraded',
        message: 'High latency detected',
      };
      render(<ModelStatusCards rtdetr={degradedRtdetr} nemotron={healthyNemotron} />);
      const rtdetrBadge = screen.getByTestId('rtdetr-badge');
      expect(rtdetrBadge).toHaveTextContent('degraded');
    });

    it('displays red badge for unhealthy status', () => {
      const unhealthyNemotron: AIModelStatus = {
        name: 'Nemotron',
        status: 'unhealthy',
        message: 'Model not responding',
      };
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={unhealthyNemotron} />);
      const nemotronBadge = screen.getByTestId('nemotron-badge');
      expect(nemotronBadge).toHaveTextContent('unhealthy');
    });

    it('displays gray badge for unknown status', () => {
      const unknownRtdetr: AIModelStatus = {
        name: 'RT-DETRv2',
        status: 'unknown',
      };
      render(<ModelStatusCards rtdetr={unknownRtdetr} nemotron={healthyNemotron} />);
      const rtdetrBadge = screen.getByTestId('rtdetr-badge');
      expect(rtdetrBadge).toHaveTextContent('unknown');
    });
  });

  describe('StatusIcon - status icons', () => {
    it('renders CheckCircle icon for healthy status', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      // Check that a green check icon is rendered
      const rtdetrCard = screen.getByTestId('rtdetr-status-card');
      const svg = rtdetrCard.querySelector('svg.text-green-500');
      expect(svg).toBeInTheDocument();
    });

    it('renders AlertTriangle icon for degraded status', () => {
      const degradedRtdetr: AIModelStatus = {
        name: 'RT-DETRv2',
        status: 'degraded',
        message: 'High latency detected',
      };
      render(<ModelStatusCards rtdetr={degradedRtdetr} nemotron={healthyNemotron} />);
      const rtdetrCard = screen.getByTestId('rtdetr-status-card');
      const svg = rtdetrCard.querySelector('svg.text-yellow-500');
      expect(svg).toBeInTheDocument();
    });

    it('renders XCircle icon for unhealthy status', () => {
      const unhealthyNemotron: AIModelStatus = {
        name: 'Nemotron',
        status: 'unhealthy',
        message: 'Model not responding',
      };
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={unhealthyNemotron} />);
      const nemotronCard = screen.getByTestId('nemotron-status-card');
      const svg = nemotronCard.querySelector('svg.text-red-500');
      expect(svg).toBeInTheDocument();
    });

    it('renders HelpCircle icon for unknown status', () => {
      const unknownRtdetr: AIModelStatus = {
        name: 'RT-DETRv2',
        status: 'unknown',
      };
      render(<ModelStatusCards rtdetr={unknownRtdetr} nemotron={healthyNemotron} />);
      const rtdetrCard = screen.getByTestId('rtdetr-status-card');
      const svg = rtdetrCard.querySelector('svg.text-gray-500');
      expect(svg).toBeInTheDocument();
    });
  });

  describe('formatLatency helper (tested through component output)', () => {
    const detectionLatency: AILatencyMetrics = {
      avg_ms: 150,
      p50_ms: 120,
      p95_ms: 280,
      p99_ms: 450,
      sample_count: 1000,
    };

    it('displays latency stats when detectionLatency is provided', () => {
      render(
        <ModelStatusCards
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={detectionLatency}
        />
      );
      expect(screen.getByText('Inference Latency')).toBeInTheDocument();
    });

    it('displays formatted milliseconds for latency values', () => {
      render(
        <ModelStatusCards
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={detectionLatency}
        />
      );
      expect(screen.getByText('150ms')).toBeInTheDocument();
      expect(screen.getByText('280ms')).toBeInTheDocument();
      expect(screen.getByText('450ms')).toBeInTheDocument();
    });

    it('displays sample count with locale formatting', () => {
      render(
        <ModelStatusCards
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={detectionLatency}
        />
      );
      expect(screen.getByText('1,000 samples')).toBeInTheDocument();
    });

    it('displays "N/A" for null latency values', () => {
      const nullLatency: AILatencyMetrics = {
        avg_ms: null,
        p50_ms: null,
        p95_ms: null,
        p99_ms: null,
        sample_count: 0,
      };
      render(
        <ModelStatusCards
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={nullLatency}
        />
      );
      // N/A should be displayed for null values
      expect(screen.getAllByText('N/A').length).toBeGreaterThanOrEqual(1);
    });

    it('displays "< 1ms" for latency values less than 1', () => {
      const subMsLatency: AILatencyMetrics = {
        avg_ms: 0.5,
        p50_ms: 0.3,
        p95_ms: 0.8,
        p99_ms: 0.9,
        sample_count: 100,
      };
      render(
        <ModelStatusCards
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={subMsLatency}
        />
      );
      expect(screen.getAllByText('< 1ms').length).toBeGreaterThanOrEqual(1);
    });

    it('displays seconds for latency values >= 1000ms', () => {
      const analysisLatency: AILatencyMetrics = {
        avg_ms: 2500,
        p50_ms: 2000,
        p95_ms: 4500,
        p99_ms: 8000,
        sample_count: 500,
      };
      render(
        <ModelStatusCards
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          analysisLatency={analysisLatency}
        />
      );
      expect(screen.getByText('2.50s')).toBeInTheDocument();
      expect(screen.getByText('4.50s')).toBeInTheDocument();
      expect(screen.getByText('8.00s')).toBeInTheDocument();
    });
  });

  describe('latency display visibility', () => {
    it('does not display latency section when detectionLatency is not provided', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      const rtdetrCard = screen.getByTestId('rtdetr-status-card');
      expect(rtdetrCard.querySelector(':scope > div > div:nth-child(2)')).not.toHaveTextContent(
        'Inference Latency'
      );
    });

    it('does not display latency section when analysisLatency is not provided', () => {
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={healthyNemotron} />);
      const nemotronCard = screen.getByTestId('nemotron-status-card');
      expect(nemotronCard).not.toHaveTextContent('Inference Latency');
    });

    it('does not display sample count when sample_count is 0', () => {
      const zeroSampleLatency: AILatencyMetrics = {
        avg_ms: 100,
        p50_ms: 80,
        p95_ms: 150,
        p99_ms: 200,
        sample_count: 0,
      };
      render(
        <ModelStatusCards
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={zeroSampleLatency}
        />
      );
      expect(screen.queryByText('0 samples')).not.toBeInTheDocument();
    });
  });

  describe('message display', () => {
    it('displays message when provided for rtdetr', () => {
      const rtdetrWithMessage: AIModelStatus = {
        name: 'RT-DETRv2',
        status: 'healthy',
        message: 'Custom status message',
      };
      render(<ModelStatusCards rtdetr={rtdetrWithMessage} nemotron={healthyNemotron} />);
      expect(screen.getByText('Custom status message')).toBeInTheDocument();
    });

    it('does not display message when not provided', () => {
      const rtdetrNoMessage: AIModelStatus = {
        name: 'RT-DETRv2',
        status: 'healthy',
      };
      const nemotronNoMessage: AIModelStatus = {
        name: 'Nemotron',
        status: 'healthy',
      };
      render(<ModelStatusCards rtdetr={rtdetrNoMessage} nemotron={nemotronNoMessage} />);
      expect(screen.queryByText('Model loaded and ready')).not.toBeInTheDocument();
    });
  });

  describe('both models with different statuses', () => {
    it('renders correctly when rtdetr is healthy and nemotron is degraded', () => {
      const degradedNemotron: AIModelStatus = {
        name: 'Nemotron',
        status: 'degraded',
        message: 'High latency warning',
      };
      render(<ModelStatusCards rtdetr={healthyRtdetr} nemotron={degradedNemotron} />);

      const rtdetrBadge = screen.getByTestId('rtdetr-badge');
      const nemotronBadge = screen.getByTestId('nemotron-badge');

      expect(rtdetrBadge).toHaveTextContent('healthy');
      expect(nemotronBadge).toHaveTextContent('degraded');
    });

    it('renders correctly when both models are unhealthy', () => {
      const unhealthyRtdetr: AIModelStatus = {
        name: 'RT-DETRv2',
        status: 'unhealthy',
        message: 'Connection failed',
      };
      const unhealthyNemotron: AIModelStatus = {
        name: 'Nemotron',
        status: 'unhealthy',
        message: 'Model crashed',
      };
      render(<ModelStatusCards rtdetr={unhealthyRtdetr} nemotron={unhealthyNemotron} />);

      expect(screen.getByText('Connection failed')).toBeInTheDocument();
      expect(screen.getByText('Model crashed')).toBeInTheDocument();
    });
  });

  describe('combined latency display', () => {
    it('displays both detection and analysis latency when provided', () => {
      const detectionLatency: AILatencyMetrics = {
        avg_ms: 150,
        p50_ms: 120,
        p95_ms: 280,
        p99_ms: 450,
        sample_count: 1000,
      };
      const analysisLatency: AILatencyMetrics = {
        avg_ms: 2500,
        p50_ms: 2000,
        p95_ms: 4500,
        p99_ms: 8000,
        sample_count: 500,
      };

      render(
        <ModelStatusCards
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={detectionLatency}
          analysisLatency={analysisLatency}
        />
      );

      // Check both latency sections are rendered
      expect(screen.getAllByText('Inference Latency').length).toBe(2);
      expect(screen.getByText('1,000 samples')).toBeInTheDocument();
      expect(screen.getByText('500 samples')).toBeInTheDocument();
    });
  });
});
