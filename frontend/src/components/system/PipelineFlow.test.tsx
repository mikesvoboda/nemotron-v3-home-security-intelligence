import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import PipelineFlow from './PipelineFlow';

import type { PipelineStage, WorkerStatus } from './PipelineFlow';

describe('PipelineFlow', () => {
  const createStage = (
    name: string,
    label: string,
    overrides: Partial<PipelineStage> = {}
  ): PipelineStage => ({
    name,
    label,
    health: 'healthy',
    ...overrides,
  });

  const defaultProps = {
    files: createStage('files', 'Files', { itemsPerMin: 12 }),
    detect: createStage('detect', 'Detect', { queueDepth: 0, avgLatency: '14ms', p95Latency: '43s' }),
    batch: createStage('batch', 'Batch', { pendingCount: 3 }),
    analyze: createStage('analyze', 'Analyze', { queueDepth: 0, avgLatency: '2.1s', p95Latency: '4.8s' }),
  };

  const mockWorkers: WorkerStatus[] = [
    { name: 'detection_worker', displayName: 'Detection Worker', running: true, abbreviation: 'Det' },
    { name: 'analysis_worker', displayName: 'Analysis Worker', running: true, abbreviation: 'Ana' },
    { name: 'batch_timeout_worker', displayName: 'Batch Timeout', running: true, abbreviation: 'Batch' },
    { name: 'cleanup_service', displayName: 'Cleanup Service', running: true, abbreviation: 'Clean' },
    { name: 'file_watcher', displayName: 'File Watcher', running: true, abbreviation: 'Watch' },
    { name: 'gpu_monitor', displayName: 'GPU Monitor', running: true, abbreviation: 'GPU' },
    { name: 'metrics_worker', displayName: 'Metrics Worker', running: true, abbreviation: 'Metr' },
    { name: 'system_broadcaster', displayName: 'System Broadcaster', running: true, abbreviation: 'Bcast' },
  ];

  describe('rendering', () => {
    it('renders the pipeline flow panel', () => {
      render(<PipelineFlow {...defaultProps} />);
      expect(screen.getByTestId('pipeline-flow-panel')).toBeInTheDocument();
    });

    it('renders the title', () => {
      render(<PipelineFlow {...defaultProps} />);
      expect(screen.getByText('Pipeline')).toBeInTheDocument();
    });

    it('renders all 4 pipeline stages', () => {
      render(<PipelineFlow {...defaultProps} />);

      expect(screen.getByTestId('stage-files')).toBeInTheDocument();
      expect(screen.getByTestId('stage-detect')).toBeInTheDocument();
      expect(screen.getByTestId('stage-batch')).toBeInTheDocument();
      expect(screen.getByTestId('stage-analyze')).toBeInTheDocument();
    });

    it('displays stage labels', () => {
      render(<PipelineFlow {...defaultProps} />);

      expect(screen.getByText('Files')).toBeInTheDocument();
      expect(screen.getByText('Detect')).toBeInTheDocument();
      expect(screen.getByText('Batch')).toBeInTheDocument();
      expect(screen.getByText('Analyze')).toBeInTheDocument();
    });
  });

  describe('stage metrics', () => {
    it('displays items per minute for files stage', () => {
      render(<PipelineFlow {...defaultProps} />);
      expect(screen.getByText('12/min')).toBeInTheDocument();
    });

    it('displays queue depth for detect stage', () => {
      render(<PipelineFlow {...defaultProps} />);
      // 'Queue: 0' appears for both detect and analyze stages when queue is 0
      expect(screen.getAllByText('Queue: 0').length).toBeGreaterThanOrEqual(1);
    });

    it('displays pending count for batch stage', () => {
      render(<PipelineFlow {...defaultProps} />);
      expect(screen.getByText('3 pending')).toBeInTheDocument();
    });

    it('displays average latency', () => {
      render(<PipelineFlow {...defaultProps} />);

      expect(screen.getByText('Avg: 14ms')).toBeInTheDocument();
      expect(screen.getByText('Avg: 2.1s')).toBeInTheDocument();
    });

    it('displays P95 latency', () => {
      render(<PipelineFlow {...defaultProps} />);

      expect(screen.getByText('P95: 43s')).toBeInTheDocument();
      expect(screen.getByText('P95: 4.8s')).toBeInTheDocument();
    });
  });

  describe('total latency', () => {
    it('renders total latency badge when provided', () => {
      render(
        <PipelineFlow
          {...defaultProps}
          totalLatency={{ avg: '16.1s', p95: '47.8s', p99: '102s' }}
        />
      );

      expect(screen.getByTestId('total-latency-badge')).toBeInTheDocument();
      expect(screen.getByText('Total: 16.1s avg')).toBeInTheDocument();
    });

    it('renders total latency summary with all values', () => {
      render(
        <PipelineFlow
          {...defaultProps}
          totalLatency={{ avg: '16.1s', p95: '47.8s', p99: '102s' }}
        />
      );

      const summary = screen.getByTestId('total-latency-summary');
      expect(summary).toHaveTextContent('16.1s');
      expect(summary).toHaveTextContent('47.8s');
      expect(summary).toHaveTextContent('102s');
    });

    it('does not render total latency when not provided', () => {
      render(<PipelineFlow {...defaultProps} />);
      expect(screen.queryByTestId('total-latency-badge')).not.toBeInTheDocument();
    });
  });

  describe('health states', () => {
    it('applies healthy styling to healthy stages', () => {
      render(<PipelineFlow {...defaultProps} />);

      const filesStage = screen.getByTestId('stage-files');
      expect(filesStage.className).toContain('bg-green');
    });

    it('applies degraded styling to degraded stages', () => {
      const props = {
        ...defaultProps,
        detect: createStage('detect', 'Detect', { health: 'degraded', queueDepth: 25 }),
      };

      render(<PipelineFlow {...props} />);

      const detectStage = screen.getByTestId('stage-detect');
      expect(detectStage.className).toContain('bg-yellow');
    });

    it('applies critical styling to critical stages', () => {
      const props = {
        ...defaultProps,
        analyze: createStage('analyze', 'Analyze', { health: 'critical', queueDepth: 100 }),
      };

      render(<PipelineFlow {...props} />);

      const analyzeStage = screen.getByTestId('stage-analyze');
      expect(analyzeStage.className).toContain('bg-red');
    });

    it('shows warning icon when any stage is degraded', () => {
      const props = {
        ...defaultProps,
        detect: createStage('detect', 'Detect', { health: 'degraded' }),
      };

      render(<PipelineFlow {...props} />);
      expect(screen.getByTestId('pipeline-warning-icon')).toBeInTheDocument();
    });

    it('shows warning icon when any stage is critical', () => {
      const props = {
        ...defaultProps,
        analyze: createStage('analyze', 'Analyze', { health: 'critical' }),
      };

      render(<PipelineFlow {...props} />);
      expect(screen.getByTestId('pipeline-warning-icon')).toBeInTheDocument();
    });

    it('does not show warning icon when all stages healthy', () => {
      render(<PipelineFlow {...defaultProps} />);
      expect(screen.queryByTestId('pipeline-warning-icon')).not.toBeInTheDocument();
    });
  });

  describe('worker grid', () => {
    it('renders worker grid when workers provided', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} />);
      expect(screen.getByTestId('worker-grid')).toBeInTheDocument();
    });

    it('does not render worker grid when no workers', () => {
      render(<PipelineFlow {...defaultProps} />);
      expect(screen.queryByTestId('worker-grid')).not.toBeInTheDocument();
    });

    it('displays worker count summary', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} />);
      expect(screen.getByTestId('workers-summary-badge')).toHaveTextContent('8/8 Running');
    });

    it('renders worker dots', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} />);

      expect(screen.getByTestId('worker-dot-detection_worker')).toBeInTheDocument();
      expect(screen.getByTestId('worker-dot-analysis_worker')).toBeInTheDocument();
    });

    it('shows correct worker abbreviations', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} />);

      expect(screen.getByText('Det')).toBeInTheDocument();
      expect(screen.getByText('Ana')).toBeInTheDocument();
      // 'Batch' appears twice (stage label and worker abbreviation), use getAllByText
      expect(screen.getAllByText('Batch').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('worker expansion', () => {
    it('worker details are collapsed by default', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} />);
      expect(screen.queryByTestId('worker-details')).not.toBeInTheDocument();
    });

    it('expands worker details when expand button clicked', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} />);

      fireEvent.click(screen.getByTestId('expand-workers-btn'));
      expect(screen.getByTestId('worker-details')).toBeInTheDocument();
    });

    it('collapses worker details when collapse button clicked', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} />);

      // Expand
      fireEvent.click(screen.getByTestId('expand-workers-btn'));
      expect(screen.getByTestId('worker-details')).toBeInTheDocument();

      // Collapse
      fireEvent.click(screen.getByTestId('expand-workers-btn'));
      expect(screen.queryByTestId('worker-details')).not.toBeInTheDocument();
    });

    it('respects workersDefaultExpanded prop', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} workersDefaultExpanded={true} />);
      expect(screen.getByTestId('worker-details')).toBeInTheDocument();
    });

    it('shows worker display names in expanded view', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} workersDefaultExpanded={true} />);

      expect(screen.getByText('Detection Worker')).toBeInTheDocument();
      expect(screen.getByText('Analysis Worker')).toBeInTheDocument();
    });
  });

  describe('worker status', () => {
    it('shows green dot for running workers', () => {
      render(<PipelineFlow {...defaultProps} workers={mockWorkers} />);

      const dot = screen.getByTestId('worker-dot-detection_worker').querySelector('div');
      expect(dot?.className).toContain('bg-green');
    });

    it('shows red dot for stopped workers', () => {
      const workersWithStopped = [
        ...mockWorkers.slice(0, -1),
        { name: 'stopped_worker', displayName: 'Stopped Worker', running: false, abbreviation: 'Stop' },
      ];

      render(<PipelineFlow {...defaultProps} workers={workersWithStopped} />);

      const dot = screen.getByTestId('worker-dot-stopped_worker').querySelector('div');
      expect(dot?.className).toContain('bg-red');
    });

    it('shows amber badge when not all workers running', () => {
      const workersWithStopped = [
        ...mockWorkers.slice(0, 7),
        { name: 'stopped_worker', displayName: 'Stopped Worker', running: false, abbreviation: 'Stop' },
      ];

      render(<PipelineFlow {...defaultProps} workers={workersWithStopped} />);

      expect(screen.getByTestId('workers-summary-badge')).toHaveTextContent('7/8 Running');
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<PipelineFlow {...defaultProps} className="custom-class" />);
      expect(screen.getByTestId('pipeline-flow-panel')).toHaveClass('custom-class');
    });
  });

  describe('full scenario', () => {
    it('renders correctly with all data', () => {
      render(
        <PipelineFlow
          files={createStage('files', 'Files', { itemsPerMin: 12, health: 'healthy' })}
          detect={createStage('detect', 'Detect', { queueDepth: 0, avgLatency: '14ms', p95Latency: '43s', health: 'healthy' })}
          batch={createStage('batch', 'Batch', { pendingCount: 3, health: 'healthy' })}
          analyze={createStage('analyze', 'Analyze', { queueDepth: 0, avgLatency: '2.1s', p95Latency: '4.8s', health: 'healthy' })}
          totalLatency={{ avg: '16.1s', p95: '47.8s', p99: '102s' }}
          workers={mockWorkers}
        />
      );

      // All sections should render
      expect(screen.getByTestId('pipeline-flow-panel')).toBeInTheDocument();
      expect(screen.getByTestId('pipeline-stages')).toBeInTheDocument();
      expect(screen.getByTestId('total-latency-summary')).toBeInTheDocument();
      expect(screen.getByTestId('worker-grid')).toBeInTheDocument();
    });
  });
});
