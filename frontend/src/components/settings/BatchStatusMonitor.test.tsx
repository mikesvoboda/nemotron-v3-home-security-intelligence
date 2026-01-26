/**
 * Tests for BatchStatusMonitor component
 *
 * @see NEM-3872 - Batch Status Monitoring
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import BatchStatusMonitor from './BatchStatusMonitor';
import * as useBatchAggregatorStatusModule from '../../hooks/useBatchAggregatorStatus';

import type { HealthIndicator } from '../../hooks/useBatchAggregatorStatus';

// Mock the hook
vi.mock('../../hooks/useBatchAggregatorStatus', () => ({
  useBatchAggregatorStatus: vi.fn(),
}));

const mockUseBatchAggregatorStatus = vi.mocked(useBatchAggregatorStatusModule.useBatchAggregatorStatus);

describe('BatchStatusMonitor', () => {
  const defaultMockReturn = {
    isLoading: false,
    error: null,
    activeBatchCount: 3,
    batches: [],
    averageBatchAge: 45,
    totalDetectionCount: 16,
    batchWindowSeconds: 90,
    idleTimeoutSeconds: 30,
    healthIndicator: 'green' as HealthIndicator,
    refetch: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseBatchAggregatorStatus.mockReturnValue(defaultMockReturn);
  });

  describe('rendering', () => {
    it('renders the component with title', () => {
      render(<BatchStatusMonitor />);

      expect(screen.getByText('Batch Status')).toBeInTheDocument();
    });

    it('is collapsed by default', () => {
      render(<BatchStatusMonitor />);

      // Details panel should not be visible initially
      expect(screen.queryByText('Active Batches')).not.toBeInTheDocument();
    });

    it('shows summary in collapsed state', () => {
      render(<BatchStatusMonitor />);

      // Summary should show batch count and health
      expect(screen.getByText('3 active')).toBeInTheDocument();
    });
  });

  describe('expand/collapse behavior', () => {
    it('expands when clicked', () => {
      render(<BatchStatusMonitor />);

      const header = screen.getByText('Batch Status').closest('button');
      fireEvent.click(header!);

      // Details should now be visible
      expect(screen.getByText('Active Batches')).toBeInTheDocument();
    });

    it('collapses when clicked again', () => {
      render(<BatchStatusMonitor />);

      const header = screen.getByText('Batch Status').closest('button');
      fireEvent.click(header!); // Expand
      fireEvent.click(header!); // Collapse

      // Details should be hidden again
      expect(screen.queryByText('Active Batches')).not.toBeInTheDocument();
    });

    it('passes enabled=false to hook when collapsed', () => {
      render(<BatchStatusMonitor />);

      expect(mockUseBatchAggregatorStatus).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: false })
      );
    });

    it('passes enabled=true to hook when expanded', () => {
      render(<BatchStatusMonitor />);

      // Initial render should have enabled=false
      expect(mockUseBatchAggregatorStatus).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: false })
      );

      const header = screen.getByText('Batch Status').closest('button');
      fireEvent.click(header!);

      // After click, the component re-renders with enabled=true
      expect(mockUseBatchAggregatorStatus).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: true })
      );
    });
  });

  describe('data display', () => {
    it('displays active batch count', () => {
      render(<BatchStatusMonitor />);

      const header = screen.getByText('Batch Status').closest('button');
      fireEvent.click(header!);

      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('Active Batches')).toBeInTheDocument();
    });

    it('displays average batch age', () => {
      render(<BatchStatusMonitor />);

      const header = screen.getByText('Batch Status').closest('button');
      fireEvent.click(header!);

      expect(screen.getByText('45s')).toBeInTheDocument();
      expect(screen.getByText('Avg Age')).toBeInTheDocument();
    });

    it('displays total detection count', () => {
      render(<BatchStatusMonitor />);

      const header = screen.getByText('Batch Status').closest('button');
      fireEvent.click(header!);

      expect(screen.getByText('16')).toBeInTheDocument();
      expect(screen.getByText('Detections')).toBeInTheDocument();
    });

    it('displays configured batch window', () => {
      render(<BatchStatusMonitor />);

      const header = screen.getByText('Batch Status').closest('button');
      fireEvent.click(header!);

      // Look for the Window label - value is shown separately
      expect(screen.getByText('Window')).toBeInTheDocument();
      // The value 90s appears in multiple places (stats and progress bar), so check the label exists
      const windowLabels = screen.getAllByText('90s');
      expect(windowLabels.length).toBeGreaterThan(0);
    });
  });

  describe('health indicators', () => {
    it('displays green health indicator', () => {
      mockUseBatchAggregatorStatus.mockReturnValue({
        ...defaultMockReturn,
        healthIndicator: 'green',
      });

      render(<BatchStatusMonitor />);

      // Look for green health indicator class or text
      const healthIndicator = screen.getByTestId('batch-health-indicator');
      expect(healthIndicator).toHaveClass('bg-green-500');
    });

    it('displays yellow health indicator', () => {
      mockUseBatchAggregatorStatus.mockReturnValue({
        ...defaultMockReturn,
        healthIndicator: 'yellow',
      });

      render(<BatchStatusMonitor />);

      const healthIndicator = screen.getByTestId('batch-health-indicator');
      expect(healthIndicator).toHaveClass('bg-yellow-500');
    });

    it('displays red health indicator', () => {
      mockUseBatchAggregatorStatus.mockReturnValue({
        ...defaultMockReturn,
        healthIndicator: 'red',
      });

      render(<BatchStatusMonitor />);

      const healthIndicator = screen.getByTestId('batch-health-indicator');
      expect(healthIndicator).toHaveClass('bg-red-500');
    });
  });

  describe('loading state', () => {
    it('shows loading indicator when loading', () => {
      mockUseBatchAggregatorStatus.mockReturnValue({
        ...defaultMockReturn,
        isLoading: true,
      });

      render(<BatchStatusMonitor />);

      const header = screen.getByText('Batch Status').closest('button');
      fireEvent.click(header!);

      expect(screen.getByTestId('batch-status-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('displays error message when error occurs', () => {
      mockUseBatchAggregatorStatus.mockReturnValue({
        ...defaultMockReturn,
        error: 'Failed to fetch batch status',
      });

      render(<BatchStatusMonitor />);

      const header = screen.getByText('Batch Status').closest('button');
      fireEvent.click(header!);

      expect(screen.getByText('Failed to fetch batch status')).toBeInTheDocument();
    });
  });

  describe('zero state', () => {
    it('displays zero batches gracefully', () => {
      mockUseBatchAggregatorStatus.mockReturnValue({
        ...defaultMockReturn,
        activeBatchCount: 0,
        averageBatchAge: 0,
        totalDetectionCount: 0,
      });

      render(<BatchStatusMonitor />);

      expect(screen.getByText('0 active')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<BatchStatusMonitor className="custom-class" />);

      const container = screen.getByTestId('batch-status-monitor');
      expect(container).toHaveClass('custom-class');
    });
  });
});
