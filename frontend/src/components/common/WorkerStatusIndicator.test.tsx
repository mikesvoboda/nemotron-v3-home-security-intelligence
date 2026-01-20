import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';

import WorkerStatusIndicator from './WorkerStatusIndicator';
import { useWorkerStatusStore } from '../../stores/worker-status-store';

describe('WorkerStatusIndicator', () => {
  beforeEach(() => {
    // Reset store state before each test
    useWorkerStatusStore.getState().clear();
  });

  afterEach(() => {
    vi.clearAllMocks();
    useWorkerStatusStore.getState().clear();
  });

  it('renders without crashing', () => {
    render(<WorkerStatusIndicator />);

    expect(screen.getByTestId('worker-status-indicator')).toBeInTheDocument();
  });

  it('shows unknown status when no workers are tracked', () => {
    render(<WorkerStatusIndicator />);

    expect(screen.getByText('Unknown')).toBeInTheDocument();
    expect(screen.getByTestId('worker-status-dot')).toHaveClass('bg-gray-500');
  });

  it('shows healthy status when all workers are running', () => {
    // Add running workers to the store
    const { handleWorkerStarted } = useWorkerStatusStore.getState();
    handleWorkerStarted({
      worker_name: 'detection-worker-1',
      worker_type: 'detection',
      timestamp: new Date().toISOString(),
    });
    handleWorkerStarted({
      worker_name: 'analysis-worker-1',
      worker_type: 'analysis',
      timestamp: new Date().toISOString(),
    });

    render(<WorkerStatusIndicator />);

    expect(screen.getByText('Healthy')).toBeInTheDocument();
    expect(screen.getByTestId('worker-status-dot')).toHaveClass('bg-emerald-500');
  });

  it('shows warning status when some workers are stopped', () => {
    const { handleWorkerStarted, handleWorkerStopped } = useWorkerStatusStore.getState();

    // Start two workers
    handleWorkerStarted({
      worker_name: 'detection-worker-1',
      worker_type: 'detection',
      timestamp: new Date().toISOString(),
    });
    handleWorkerStarted({
      worker_name: 'analysis-worker-1',
      worker_type: 'analysis',
      timestamp: new Date().toISOString(),
    });

    // Stop one
    handleWorkerStopped({
      worker_name: 'analysis-worker-1',
      worker_type: 'analysis',
      timestamp: new Date().toISOString(),
    });

    render(<WorkerStatusIndicator />);

    expect(screen.getByText('Warning')).toBeInTheDocument();
    expect(screen.getByTestId('worker-status-dot')).toHaveClass('bg-yellow-500');
  });

  it('shows error status when any worker has error', () => {
    const { handleWorkerStarted, handleWorkerError } = useWorkerStatusStore.getState();

    handleWorkerStarted({
      worker_name: 'detection-worker-1',
      worker_type: 'detection',
      timestamp: new Date().toISOString(),
    });
    handleWorkerError({
      worker_name: 'analysis-worker-1',
      worker_type: 'analysis',
      error: 'Connection failed',
      timestamp: new Date().toISOString(),
      recoverable: true,
    });

    render(<WorkerStatusIndicator />);

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByTestId('worker-status-dot')).toHaveClass('bg-red-500');
  });

  it('has correct aria attributes', () => {
    render(<WorkerStatusIndicator />);

    const indicator = screen.getByTestId('worker-status-indicator');
    expect(indicator).toHaveAttribute('role', 'button');
    expect(indicator).toHaveAttribute('tabIndex', '0');
    expect(indicator).toHaveAttribute('aria-haspopup', 'true');
    expect(indicator).toHaveAttribute('aria-expanded', 'false');
  });

  describe('Dropdown', () => {
    it('shows dropdown on mouse enter', () => {
      const { handleWorkerStarted } = useWorkerStatusStore.getState();
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      render(<WorkerStatusIndicator />);

      const indicator = screen.getByTestId('worker-status-indicator');

      // Dropdown should not be visible initially
      expect(screen.queryByTestId('worker-status-dropdown')).not.toBeInTheDocument();

      // Hover to show dropdown
      fireEvent.mouseEnter(indicator);

      expect(screen.getByTestId('worker-status-dropdown')).toBeInTheDocument();
      expect(screen.getByText('Pipeline Workers')).toBeInTheDocument();
    });

    it('shows dropdown on focus', () => {
      const { handleWorkerStarted } = useWorkerStatusStore.getState();
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      render(<WorkerStatusIndicator />);

      const indicator = screen.getByTestId('worker-status-indicator');

      fireEvent.focus(indicator);

      expect(screen.getByTestId('worker-status-dropdown')).toBeInTheDocument();
    });

    it('hides dropdown on mouse leave after delay', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });

      const { handleWorkerStarted } = useWorkerStatusStore.getState();
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      render(<WorkerStatusIndicator />);

      const indicator = screen.getByTestId('worker-status-indicator');

      // Show dropdown
      fireEvent.mouseEnter(indicator);
      expect(screen.getByTestId('worker-status-dropdown')).toBeInTheDocument();

      // Mouse leave
      fireEvent.mouseLeave(indicator);

      // Still visible immediately
      expect(screen.getByTestId('worker-status-dropdown')).toBeInTheDocument();

      // After delay, should be hidden
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      expect(screen.queryByTestId('worker-status-dropdown')).not.toBeInTheDocument();

      vi.useRealTimers();
    });

    it('displays worker details in dropdown', () => {
      const { handleWorkerStarted, handleWorkerStopped, handleWorkerError } =
        useWorkerStatusStore.getState();

      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });
      handleWorkerStopped({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      });
      handleWorkerError({
        worker_name: 'metrics-worker-1',
        worker_type: 'metrics',
        error: 'Failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      });

      render(<WorkerStatusIndicator />);

      const indicator = screen.getByTestId('worker-status-indicator');
      fireEvent.mouseEnter(indicator);

      // Check worker names are displayed
      expect(screen.getByText('detection-worker-1')).toBeInTheDocument();
      expect(screen.getByText('analysis-worker-1')).toBeInTheDocument();
      expect(screen.getByText('metrics-worker-1')).toBeInTheDocument();

      // Check status indicators
      expect(screen.getByTestId('worker-indicator-detection-worker-1')).toHaveClass('bg-emerald-500');
      expect(screen.getByTestId('worker-indicator-analysis-worker-1')).toHaveClass('bg-gray-500');
      expect(screen.getByTestId('worker-indicator-metrics-worker-1')).toHaveClass('bg-red-500');
    });

    it('shows error warning in dropdown when hasError', () => {
      const { handleWorkerError } = useWorkerStatusStore.getState();
      handleWorkerError({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Connection failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      });

      render(<WorkerStatusIndicator />);

      const indicator = screen.getByTestId('worker-status-indicator');
      fireEvent.mouseEnter(indicator);

      expect(screen.getByText('Some workers have errors')).toBeInTheDocument();
    });

    it('shows warning in dropdown when hasWarning (no errors)', () => {
      const { handleWorkerStarted, handleWorkerStopped } = useWorkerStatusStore.getState();

      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });
      handleWorkerStopped({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      });

      render(<WorkerStatusIndicator />);

      const indicator = screen.getByTestId('worker-status-indicator');
      fireEvent.mouseEnter(indicator);

      expect(screen.getByText('Some workers are stopped or restarting')).toBeInTheDocument();
    });

    it('shows empty state when no workers', () => {
      render(<WorkerStatusIndicator />);

      const indicator = screen.getByTestId('worker-status-indicator');
      fireEvent.mouseEnter(indicator);

      expect(screen.getByText('No workers detected yet')).toBeInTheDocument();
    });

    it('shows worker count in dropdown', () => {
      const { handleWorkerStarted, handleWorkerStopped } = useWorkerStatusStore.getState();

      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });
      handleWorkerStarted({
        worker_name: 'analysis-worker-1',
        worker_type: 'analysis',
        timestamp: new Date().toISOString(),
      });
      handleWorkerStopped({
        worker_name: 'metrics-worker-1',
        worker_type: 'metrics',
        timestamp: new Date().toISOString(),
      });

      render(<WorkerStatusIndicator />);

      const indicator = screen.getByTestId('worker-status-indicator');
      fireEvent.mouseEnter(indicator);

      expect(screen.getByText('2 of 3 running')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies custom className', () => {
      render(<WorkerStatusIndicator className="custom-class" />);

      expect(screen.getByTestId('worker-status-indicator')).toHaveClass('custom-class');
    });

    it('pulses status dot when healthy', () => {
      const { handleWorkerStarted } = useWorkerStatusStore.getState();
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      render(<WorkerStatusIndicator />);

      expect(screen.getByTestId('worker-status-dot')).toHaveClass('animate-pulse');
    });

    it('does not pulse status dot when error', () => {
      const { handleWorkerError } = useWorkerStatusStore.getState();
      handleWorkerError({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        error: 'Failed',
        timestamp: new Date().toISOString(),
        recoverable: true,
      });

      render(<WorkerStatusIndicator />);

      expect(screen.getByTestId('worker-status-dot')).not.toHaveClass('animate-pulse');
    });

    it('does not pulse status dot when unknown', () => {
      render(<WorkerStatusIndicator />);

      expect(screen.getByTestId('worker-status-dot')).not.toHaveClass('animate-pulse');
    });
  });

  describe('Compact mode', () => {
    it('renders only dot in compact mode', () => {
      const { handleWorkerStarted } = useWorkerStatusStore.getState();
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      render(<WorkerStatusIndicator compact />);

      expect(screen.getByTestId('worker-status-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('worker-status-dot')).toBeInTheDocument();
      // Should not have the icon or label in compact mode
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
  });

  describe('Label visibility', () => {
    it('shows label by default', () => {
      const { handleWorkerStarted } = useWorkerStatusStore.getState();
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      render(<WorkerStatusIndicator />);

      expect(screen.getByText('Pipeline:')).toBeInTheDocument();
      expect(screen.getByText('Healthy')).toBeInTheDocument();
      expect(screen.getByText('(1/1)')).toBeInTheDocument();
    });

    it('hides label when showLabel is false', () => {
      const { handleWorkerStarted } = useWorkerStatusStore.getState();
      handleWorkerStarted({
        worker_name: 'detection-worker-1',
        worker_type: 'detection',
        timestamp: new Date().toISOString(),
      });

      render(<WorkerStatusIndicator showLabel={false} />);

      expect(screen.queryByText('Pipeline:')).not.toBeInTheDocument();
      // The status dot should still be visible
      expect(screen.getByTestId('worker-status-dot')).toBeInTheDocument();
    });
  });
});
