import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import PipelineFlowVisualization from './PipelineFlowVisualization';

import type {
  BackgroundWorkerStatus,
  PipelineFlowVisualizationProps,
  PipelineStageData,
} from './PipelineFlowVisualization';

describe('PipelineFlowVisualization', () => {
  // Default mock data
  const defaultStages: PipelineStageData[] = [
    {
      id: 'files',
      name: 'Files',
      icon: 'folder',
      metrics: {
        throughput: '12/min',
      },
    },
    {
      id: 'detect',
      name: 'Detect',
      icon: 'search',
      metrics: {
        queueDepth: 0,
        avgLatency: 14000,
        p95Latency: 43000,
      },
    },
    {
      id: 'batch',
      name: 'Batch',
      icon: 'package',
      metrics: {
        pending: 3,
      },
    },
    {
      id: 'analyze',
      name: 'Analyze',
      icon: 'brain',
      metrics: {
        queueDepth: 0,
        avgLatency: 2100,
        p95Latency: 4800,
      },
    },
  ];

  const defaultWorkers: BackgroundWorkerStatus[] = [
    { id: 'detection_worker', name: 'Det', status: 'running' },
    { id: 'analysis_worker', name: 'Ana', status: 'running' },
    { id: 'batch_timeout_worker', name: 'Batch', status: 'running' },
    { id: 'cleanup_service', name: 'Clean', status: 'running' },
    { id: 'file_watcher', name: 'Watch', status: 'running' },
    { id: 'gpu_monitor', name: 'GPU', status: 'running' },
    { id: 'metrics_worker', name: 'Metr', status: 'running' },
    { id: 'system_broadcaster', name: 'Bcast', status: 'running' },
  ];

  const defaultProps: PipelineFlowVisualizationProps = {
    stages: defaultStages,
    workers: defaultWorkers,
    totalLatency: {
      avg: 16100,
      p95: 47800,
      p99: 102000,
    },
  };

  describe('rendering', () => {
    it('renders the pipeline flow visualization', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      expect(screen.getByTestId('pipeline-flow-visualization')).toBeInTheDocument();
    });

    it('renders all pipeline stages', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      expect(screen.getByTestId('stage-files')).toBeInTheDocument();
      expect(screen.getByTestId('stage-detect')).toBeInTheDocument();
      expect(screen.getByTestId('stage-batch')).toBeInTheDocument();
      expect(screen.getByTestId('stage-analyze')).toBeInTheDocument();
    });

    it('renders stage names', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      expect(screen.getByText('Files')).toBeInTheDocument();
      expect(screen.getByText('Detect')).toBeInTheDocument();
      expect(screen.getByText('Batch')).toBeInTheDocument();
      expect(screen.getByText('Analyze')).toBeInTheDocument();
    });

    it('renders flow arrows between stages', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const arrows = screen.getAllByTestId(/^arrow-/);
      expect(arrows).toHaveLength(3); // 4 stages = 3 arrows between them
    });

    it('renders total pipeline latency', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      expect(screen.getByTestId('total-pipeline-latency')).toBeInTheDocument();
      expect(screen.getByText(/16\.1s avg/)).toBeInTheDocument();
      expect(screen.getByText(/47\.8s p95/)).toBeInTheDocument();
      expect(screen.getByText(/102s p99/)).toBeInTheDocument();
    });
  });

  describe('stage metrics display', () => {
    it('displays throughput for files stage', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const filesStage = screen.getByTestId('stage-files');
      expect(within(filesStage).getByText('12/min')).toBeInTheDocument();
    });

    it('displays queue depth for detect stage', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const detectStage = screen.getByTestId('stage-detect');
      expect(within(detectStage).getByText(/Queue: 0/)).toBeInTheDocument();
    });

    it('displays latency metrics for detect stage', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const detectStage = screen.getByTestId('stage-detect');
      expect(within(detectStage).getByText(/Avg: 14s/)).toBeInTheDocument();
    });

    it('displays pending count for batch stage', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const batchStage = screen.getByTestId('stage-batch');
      expect(within(batchStage).getByText('3 pending')).toBeInTheDocument();
    });

    it('displays queue depth and latency for analyze stage', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const analyzeStage = screen.getByTestId('stage-analyze');
      expect(within(analyzeStage).getByText(/Queue: 0/)).toBeInTheDocument();
      expect(within(analyzeStage).getByText(/Avg: 2\.1s/)).toBeInTheDocument();
    });
  });

  describe('health status coloring', () => {
    it('shows green styling for healthy stage (queue 0-10, latency < 2x baseline)', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const detectStage = screen.getByTestId('stage-detect');
      // Green border class
      expect(detectStage.className).toMatch(/border-green|border-emerald/);
    });

    it('shows yellow styling for degraded stage (queue 11-50)', () => {
      const degradedStages: PipelineStageData[] = [
        ...defaultStages.slice(0, 1),
        {
          ...defaultStages[1],
          metrics: {
            queueDepth: 25,
            avgLatency: 14000,
            p95Latency: 43000,
          },
        },
        ...defaultStages.slice(2),
      ];

      render(<PipelineFlowVisualization {...defaultProps} stages={degradedStages} />);

      const detectStage = screen.getByTestId('stage-detect');
      expect(detectStage.className).toMatch(/border-yellow|border-amber/);
    });

    it('shows red styling for critical stage (queue > 50)', () => {
      const criticalStages: PipelineStageData[] = [
        ...defaultStages.slice(0, 1),
        {
          ...defaultStages[1],
          metrics: {
            queueDepth: 75,
            avgLatency: 14000,
            p95Latency: 43000,
          },
        },
        ...defaultStages.slice(2),
      ];

      render(<PipelineFlowVisualization {...defaultProps} stages={criticalStages} />);

      const detectStage = screen.getByTestId('stage-detect');
      expect(detectStage.className).toMatch(/border-red/);
    });

    it('shows yellow styling for high latency (2-5x baseline)', () => {
      const highLatencyStages: PipelineStageData[] = [
        ...defaultStages.slice(0, 1),
        {
          ...defaultStages[1],
          metrics: {
            queueDepth: 0,
            avgLatency: 40000, // ~3x baseline of 14s
            p95Latency: 100000,
          },
        },
        ...defaultStages.slice(2),
      ];

      render(
        <PipelineFlowVisualization
          {...defaultProps}
          stages={highLatencyStages}
          baselineLatencies={{ detect: 14000, analyze: 2100 }}
        />
      );

      const detectStage = screen.getByTestId('stage-detect');
      expect(detectStage.className).toMatch(/border-yellow|border-amber/);
    });

    it('shows red styling for very high latency (> 5x baseline)', () => {
      const veryHighLatencyStages: PipelineStageData[] = [
        ...defaultStages.slice(0, 1),
        {
          ...defaultStages[1],
          metrics: {
            queueDepth: 0,
            avgLatency: 100000, // ~7x baseline of 14s
            p95Latency: 200000,
          },
        },
        ...defaultStages.slice(2),
      ];

      render(
        <PipelineFlowVisualization
          {...defaultProps}
          stages={veryHighLatencyStages}
          baselineLatencies={{ detect: 14000, analyze: 2100 }}
        />
      );

      const detectStage = screen.getByTestId('stage-detect');
      expect(detectStage.className).toMatch(/border-red/);
    });
  });

  describe('background workers grid', () => {
    it('renders workers section', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      expect(screen.getByTestId('workers-grid')).toBeInTheDocument();
      expect(screen.getByText('Background Workers')).toBeInTheDocument();
    });

    it('displays running count badge', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      expect(screen.getByTestId('workers-count-badge')).toHaveTextContent('8/8 Running');
    });

    it('renders all 8 worker status dots', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const workerDots = screen.getAllByTestId(/^worker-dot-/);
      expect(workerDots).toHaveLength(8);
    });

    it('shows green dot for running workers', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const detectionWorkerDot = screen.getByTestId('worker-dot-detection_worker');
      expect(detectionWorkerDot.className).toMatch(/bg-green|bg-emerald/);
    });

    it('shows red dot for stopped workers', () => {
      const workersWithStopped: BackgroundWorkerStatus[] = [
        ...defaultWorkers.slice(0, 5),
        { id: 'gpu_monitor', name: 'GPU', status: 'stopped' },
        ...defaultWorkers.slice(6),
      ];

      render(<PipelineFlowVisualization {...defaultProps} workers={workersWithStopped} />);

      const gpuWorkerDot = screen.getByTestId('worker-dot-gpu_monitor');
      expect(gpuWorkerDot.className).toMatch(/bg-red/);
    });

    it('shows yellow dot for degraded workers', () => {
      const workersWithDegraded: BackgroundWorkerStatus[] = [
        ...defaultWorkers.slice(0, 5),
        { id: 'gpu_monitor', name: 'GPU', status: 'degraded' },
        ...defaultWorkers.slice(6),
      ];

      render(<PipelineFlowVisualization {...defaultProps} workers={workersWithDegraded} />);

      const gpuWorkerDot = screen.getByTestId('worker-dot-gpu_monitor');
      expect(gpuWorkerDot.className).toMatch(/bg-yellow|bg-amber/);
    });

    it('shows worker abbreviations', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      expect(screen.getByText('Det')).toBeInTheDocument();
      expect(screen.getByText('Ana')).toBeInTheDocument();
      expect(screen.getByText('Batch')).toBeInTheDocument();
    });

    it('updates count badge when some workers stopped', () => {
      const workersWithStopped: BackgroundWorkerStatus[] = [
        ...defaultWorkers.slice(0, 5),
        { id: 'gpu_monitor', name: 'GPU', status: 'stopped' },
        { id: 'metrics_worker', name: 'Metr', status: 'stopped' },
        defaultWorkers[7],
      ];

      render(<PipelineFlowVisualization {...defaultProps} workers={workersWithStopped} />);

      expect(screen.getByTestId('workers-count-badge')).toHaveTextContent('6/8 Running');
    });
  });

  describe('expand/collapse workers details', () => {
    it('renders expand details button', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      expect(screen.getByTestId('expand-workers-button')).toBeInTheDocument();
      expect(screen.getByText('Expand Details')).toBeInTheDocument();
    });

    it('expands worker details when button is clicked', async () => {
      const user = userEvent.setup();
      render(<PipelineFlowVisualization {...defaultProps} />);

      // Details should be hidden initially
      expect(screen.queryByTestId('workers-expanded-list')).not.toBeInTheDocument();

      // Click expand button
      await user.click(screen.getByTestId('expand-workers-button'));

      // Details should now be visible
      expect(screen.getByTestId('workers-expanded-list')).toBeInTheDocument();
    });

    it('collapses worker details when button is clicked again', async () => {
      const user = userEvent.setup();
      render(<PipelineFlowVisualization {...defaultProps} />);

      // Click expand
      await user.click(screen.getByTestId('expand-workers-button'));
      expect(screen.getByTestId('workers-expanded-list')).toBeInTheDocument();

      // Click collapse
      await user.click(screen.getByTestId('expand-workers-button'));
      expect(screen.queryByTestId('workers-expanded-list')).not.toBeInTheDocument();
    });
  });

  describe('formatting', () => {
    it('formats milliseconds correctly for small values', () => {
      const stagesWithSmallLatency: PipelineStageData[] = [
        defaultStages[0],
        {
          ...defaultStages[1],
          metrics: {
            queueDepth: 0,
            avgLatency: 500,
            p95Latency: 800,
          },
        },
        defaultStages[2],
        defaultStages[3],
      ];

      render(<PipelineFlowVisualization {...defaultProps} stages={stagesWithSmallLatency} />);

      const detectStage = screen.getByTestId('stage-detect');
      expect(within(detectStage).getByText(/Avg: 500ms/)).toBeInTheDocument();
    });

    it('formats seconds correctly for large values', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const detectStage = screen.getByTestId('stage-detect');
      expect(within(detectStage).getByText(/Avg: 14s/)).toBeInTheDocument();
    });

    it('handles null/undefined metrics gracefully', () => {
      const stagesWithNullMetrics: PipelineStageData[] = [
        defaultStages[0],
        {
          id: 'detect',
          name: 'Detect',
          icon: 'search',
          metrics: {
            queueDepth: undefined,
            avgLatency: null,
            p95Latency: null,
          },
        },
        defaultStages[2],
        defaultStages[3],
      ];

      render(<PipelineFlowVisualization {...defaultProps} stages={stagesWithNullMetrics} />);

      expect(screen.getByTestId('stage-detect')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<PipelineFlowVisualization {...defaultProps} className="custom-class" />);

      const container = screen.getByTestId('pipeline-flow-visualization');
      expect(container.className).toContain('custom-class');
    });

    it('has dark theme styling', () => {
      render(<PipelineFlowVisualization {...defaultProps} />);

      const container = screen.getByTestId('pipeline-flow-visualization');
      expect(container.className).toContain('bg-[#1A1A1A]');
    });
  });

  describe('responsive behavior', () => {
    it('renders properly with minimal stages', () => {
      const minimalStages: PipelineStageData[] = [defaultStages[0], defaultStages[1]];

      render(<PipelineFlowVisualization {...defaultProps} stages={minimalStages} />);

      expect(screen.getByTestId('stage-files')).toBeInTheDocument();
      expect(screen.getByTestId('stage-detect')).toBeInTheDocument();
      expect(screen.getAllByTestId(/^arrow-/)).toHaveLength(1);
    });

    it('renders properly with no workers', () => {
      render(<PipelineFlowVisualization {...defaultProps} workers={[]} />);

      expect(screen.getByTestId('workers-count-badge')).toHaveTextContent('0/0 Running');
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when isLoading is true', () => {
      render(<PipelineFlowVisualization {...defaultProps} isLoading={true} />);

      expect(screen.getByTestId('pipeline-flow-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error message when error is provided', () => {
      render(
        <PipelineFlowVisualization {...defaultProps} error="Failed to load pipeline data" />
      );

      expect(screen.getByTestId('pipeline-flow-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load pipeline data')).toBeInTheDocument();
    });
  });
});
