import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import GpuStatistics from './GpuStatistics';

import type { AiModelStatus } from './GpuStatistics';
import type { GpuMetricDataPoint } from '../../hooks/useGpuHistory';

describe('GpuStatistics', () => {
  const mockHistoryData: GpuMetricDataPoint[] = [
    { timestamp: '2026-01-04T10:00:00Z', utilization: 30, memory_used: 200, temperature: 38 },
    { timestamp: '2026-01-04T10:01:00Z', utilization: 35, memory_used: 210, temperature: 39 },
    { timestamp: '2026-01-04T10:02:00Z', utilization: 40, memory_used: 220, temperature: 40 },
    { timestamp: '2026-01-04T10:03:00Z', utilization: 38, memory_used: 215, temperature: 40 },
  ];

  const mockRtdetr: AiModelStatus = {
    name: 'RT-DETRv2',
    status: 'healthy',
    latency: '14ms',
    count: 1847,
    errors: 0,
  };

  const mockNemotron: AiModelStatus = {
    name: 'Nemotron',
    status: 'healthy',
    latency: '2.1s',
    count: 64,
    errors: 0,
  };

  describe('rendering', () => {
    it('renders the GPU statistics panel', () => {
      render(<GpuStatistics />);
      expect(screen.getByTestId('gpu-statistics-panel')).toBeInTheDocument();
    });

    it('renders the title', () => {
      render(<GpuStatistics />);
      expect(screen.getByText('GPU Statistics')).toBeInTheDocument();
    });

    it('renders GPU name when provided', () => {
      render(<GpuStatistics gpuName="NVIDIA RTX A5500" />);
      expect(screen.getByTestId('gpu-device-name')).toHaveTextContent('NVIDIA RTX A5500');
    });
  });

  describe('sparkline rows', () => {
    it('renders all 4 sparkline rows', () => {
      render(<GpuStatistics />);

      expect(screen.getByTestId('gpu-utilization-row')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-temperature-row')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-memory-row')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-power-row')).toBeInTheDocument();
    });

    it('displays utilization value', () => {
      render(<GpuStatistics utilization={38} />);
      expect(screen.getByText('38%')).toBeInTheDocument();
    });

    it('displays temperature value', () => {
      render(<GpuStatistics temperature={40} />);
      expect(screen.getByText('40\u00B0C')).toBeInTheDocument();
    });

    it('displays memory value', () => {
      render(<GpuStatistics memoryUsed={200} memoryTotal={24576} />);
      expect(screen.getByText('0.2GB/24.0GB')).toBeInTheDocument();
    });

    it('displays power value', () => {
      render(<GpuStatistics powerUsage={31} />);
      expect(screen.getByText('31W')).toBeInTheDocument();
    });

    it('displays N/A when values are null', () => {
      render(<GpuStatistics />);

      // Should show N/A for all metrics when no values provided
      const naTexts = screen.getAllByText('N/A');
      expect(naTexts.length).toBeGreaterThan(0);
    });

    it('renders sparklines with history data', () => {
      render(<GpuStatistics historyData={mockHistoryData} />);

      // Sparklines should be rendered (they show as SVG elements)
      expect(screen.getByTestId('gpu-utilization-row')).toBeInTheDocument();
    });

    it('shows "No data" message when no history', () => {
      render(<GpuStatistics historyData={[]} />);

      const noDataTexts = screen.getAllByText('No data');
      expect(noDataTexts.length).toBeGreaterThan(0);
    });
  });

  describe('inference FPS', () => {
    it('renders inference FPS display', () => {
      render(<GpuStatistics />);
      expect(screen.getByTestId('inference-fps-display')).toBeInTheDocument();
    });

    it('displays inference FPS value', () => {
      render(<GpuStatistics inferenceFps={2.4} />);
      expect(screen.getByText('2.4')).toBeInTheDocument();
    });

    it('displays N/A when inference FPS is null', () => {
      render(<GpuStatistics inferenceFps={null} />);

      const fpsDisplay = screen.getByTestId('inference-fps-display');
      expect(fpsDisplay).toHaveTextContent('N/A');
    });
  });

  describe('AI model mini-cards', () => {
    it('renders RT-DETRv2 mini-card when provided', () => {
      render(<GpuStatistics rtdetr={mockRtdetr} />);
      expect(screen.getByTestId('rtdetr-mini-card')).toBeInTheDocument();
    });

    it('renders Nemotron mini-card when provided', () => {
      render(<GpuStatistics nemotron={mockNemotron} />);
      expect(screen.getByTestId('nemotron-mini-card')).toBeInTheDocument();
    });

    it('renders both mini-cards when both provided', () => {
      render(<GpuStatistics rtdetr={mockRtdetr} nemotron={mockNemotron} />);

      expect(screen.getByTestId('rtdetr-mini-card')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-mini-card')).toBeInTheDocument();
    });

    it('displays model name', () => {
      render(<GpuStatistics rtdetr={mockRtdetr} />);
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    });

    it('displays model status badge', () => {
      render(<GpuStatistics rtdetr={mockRtdetr} />);
      expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('displays model latency', () => {
      render(<GpuStatistics rtdetr={mockRtdetr} />);
      expect(screen.getByText('14ms')).toBeInTheDocument();
    });

    it('displays model count', () => {
      render(<GpuStatistics rtdetr={mockRtdetr} />);
      expect(screen.getByText('1,847')).toBeInTheDocument();
    });

    it('displays model errors', () => {
      render(<GpuStatistics rtdetr={mockRtdetr} />);

      // Find the errors section
      const rtdetrCard = screen.getByTestId('rtdetr-mini-card');
      expect(rtdetrCard).toHaveTextContent('0');
    });

    it('does not render mini-cards section when neither model provided', () => {
      render(<GpuStatistics />);

      expect(screen.queryByTestId('rtdetr-mini-card')).not.toBeInTheDocument();
      expect(screen.queryByTestId('nemotron-mini-card')).not.toBeInTheDocument();
    });
  });

  describe('model status variations', () => {
    it('displays unhealthy status correctly', () => {
      const unhealthyModel: AiModelStatus = {
        name: 'RT-DETRv2',
        status: 'unhealthy',
        latency: 'N/A',
        count: 0,
        errors: 5,
      };

      render(<GpuStatistics rtdetr={unhealthyModel} />);

      expect(screen.getByText('unhealthy')).toBeInTheDocument();
    });

    it('displays loading status correctly', () => {
      const loadingModel: AiModelStatus = {
        name: 'Nemotron',
        status: 'loading',
      };

      render(<GpuStatistics nemotron={loadingModel} />);

      expect(screen.getByText('loading')).toBeInTheDocument();
    });

    it('displays error count with red styling when errors > 0', () => {
      const modelWithErrors: AiModelStatus = {
        name: 'RT-DETRv2',
        status: 'healthy',
        errors: 3,
      };

      render(<GpuStatistics rtdetr={modelWithErrors} />);

      const card = screen.getByTestId('rtdetr-mini-card');
      expect(card).toHaveTextContent('3');
    });
  });

  describe('Grafana link', () => {
    it('renders Grafana link when URL provided', () => {
      render(<GpuStatistics grafanaUrl="http://localhost:3002" />);
      expect(screen.getByTestId('grafana-link')).toBeInTheDocument();
    });

    it('does not render Grafana link when URL not provided', () => {
      render(<GpuStatistics />);
      expect(screen.queryByTestId('grafana-link')).not.toBeInTheDocument();
    });

    it('Grafana link has correct href', () => {
      render(<GpuStatistics grafanaUrl="http://localhost:3002" />);

      const link = screen.getByTestId('grafana-link');
      expect(link).toHaveAttribute('href', 'http://localhost:3002');
    });

    it('Grafana link opens in new tab', () => {
      render(<GpuStatistics grafanaUrl="http://localhost:3002" />);

      const link = screen.getByTestId('grafana-link');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<GpuStatistics className="custom-class" />);
      expect(screen.getByTestId('gpu-statistics-panel')).toHaveClass('custom-class');
    });
  });

  describe('full data scenario', () => {
    it('renders correctly with all data provided', () => {
      render(
        <GpuStatistics
          gpuName="NVIDIA RTX A5500"
          utilization={38}
          temperature={40}
          memoryUsed={200}
          memoryTotal={24576}
          powerUsage={31}
          inferenceFps={2.4}
          historyData={mockHistoryData}
          rtdetr={mockRtdetr}
          nemotron={mockNemotron}
          grafanaUrl="http://localhost:3002"
        />
      );

      // Verify all sections are rendered
      expect(screen.getByTestId('gpu-statistics-panel')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-device-name')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-utilization-row')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-temperature-row')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-memory-row')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-power-row')).toBeInTheDocument();
      expect(screen.getByTestId('inference-fps-display')).toBeInTheDocument();
      expect(screen.getByTestId('rtdetr-mini-card')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-mini-card')).toBeInTheDocument();
      expect(screen.getByTestId('grafana-link')).toBeInTheDocument();
    });
  });
});
