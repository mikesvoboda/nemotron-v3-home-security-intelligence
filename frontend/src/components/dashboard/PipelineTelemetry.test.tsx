import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PipelineTelemetry from './PipelineTelemetry';
import * as api from '../../services/api';

// Mock the API functions
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchPipelineLatency: vi.fn(),
    fetchTelemetry: vi.fn(),
  };
});

// Mock ResizeObserver for Tremor charts
beforeEach(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

const mockLatencyResponse = {
  watch_to_detect: {
    avg_ms: 50.5,
    min_ms: 20,
    max_ms: 200,
    p50_ms: 45,
    p95_ms: 150,
    p99_ms: 180,
    sample_count: 100,
  },
  detect_to_batch: {
    avg_ms: 500,
    min_ms: 100,
    max_ms: 2000,
    p50_ms: 400,
    p95_ms: 1500,
    p99_ms: 1800,
    sample_count: 100,
  },
  batch_to_analyze: {
    avg_ms: 5000,
    min_ms: 1000,
    max_ms: 20000,
    p50_ms: 4000,
    p95_ms: 15000,
    p99_ms: 18000,
    sample_count: 50,
  },
  total_pipeline: {
    avg_ms: 5550.5,
    min_ms: 1120,
    max_ms: 22200,
    p50_ms: 4445,
    p95_ms: 16650,
    p99_ms: 19980,
    sample_count: 50,
  },
  window_minutes: 60,
  timestamp: '2025-01-15T10:30:00Z',
};

const mockTelemetryResponse = {
  queues: {
    detection_queue: 3,
    analysis_queue: 1,
  },
  latencies: {
    watch: { avg_ms: 50 },
    detect: { avg_ms: 500 },
    batch: { avg_ms: 5000 },
    analyze: { avg_ms: 10000 },
  },
  timestamp: '2025-01-15T10:30:00Z',
};

describe('PipelineTelemetry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchPipelineLatency as ReturnType<typeof vi.fn>).mockResolvedValue(mockLatencyResponse);
    (api.fetchTelemetry as ReturnType<typeof vi.fn>).mockResolvedValue(mockTelemetryResponse);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially then shows content', async () => {
    render(<PipelineTelemetry pollingInterval={0} />);

    // Wait for data to load and show title
    await waitFor(() => {
      expect(screen.getByText('Pipeline Telemetry')).toBeInTheDocument();
    });
  });

  it('fetches data on mount with custom window', async () => {
    render(<PipelineTelemetry windowMinutes={30} pollingInterval={0} />);

    await waitFor(() => {
      expect(api.fetchPipelineLatency).toHaveBeenCalledWith(30);
      expect(api.fetchTelemetry).toHaveBeenCalled();
    });
  });

  it('displays queue depths in Queue Depths tab', async () => {
    render(<PipelineTelemetry pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('detection-queue-depth')).toBeInTheDocument();
    });

    expect(screen.getByText('Detection Queue')).toBeInTheDocument();
    expect(screen.getByText('Analysis Queue')).toBeInTheDocument();
  });

  it('displays error state when API fails', async () => {
    (api.fetchPipelineLatency as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

    render(<PipelineTelemetry pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('telemetry-error')).toBeInTheDocument();
    });

    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('allows switching between tabs', async () => {
    const user = userEvent.setup();
    render(<PipelineTelemetry pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Queue Depths')).toBeInTheDocument();
    });

    // Click on Stage Latencies tab
    await user.click(screen.getByText('Stage Latencies'));

    // Should show latency data
    await waitFor(() => {
      expect(screen.getByText('File to Detection')).toBeInTheDocument();
    });
  });

  it('displays stage latency cards in Stage Latencies tab', async () => {
    const user = userEvent.setup();
    render(<PipelineTelemetry pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Stage Latencies')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Stage Latencies'));

    await waitFor(() => {
      expect(screen.getByTestId('stage-card-watch_to_detect')).toBeInTheDocument();
      expect(screen.getByTestId('stage-card-detect_to_batch')).toBeInTheDocument();
      expect(screen.getByTestId('stage-card-batch_to_analyze')).toBeInTheDocument();
      expect(screen.getByTestId('stage-card-total_pipeline')).toBeInTheDocument();
    });
  });

  it('displays percentile values', async () => {
    const user = userEvent.setup();
    render(<PipelineTelemetry pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Stage Latencies')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Stage Latencies'));

    await waitFor(() => {
      // Check for P50, P95, P99 labels (multiple instances)
      expect(screen.getAllByText('P50').length).toBeGreaterThan(0);
      expect(screen.getAllByText('P95').length).toBeGreaterThan(0);
      expect(screen.getAllByText('P99').length).toBeGreaterThan(0);
    });
  });

  it('handles refresh button click', async () => {
    const user = userEvent.setup();
    render(<PipelineTelemetry pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByLabelText('Refresh telemetry')).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText('Refresh telemetry'));

    // Should have been called again
    await waitFor(() => {
      expect(api.fetchPipelineLatency).toHaveBeenCalledTimes(2);
    });
  });

  it('applies custom className', async () => {
    render(<PipelineTelemetry className="custom-class" pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('pipeline-telemetry')).toHaveClass('custom-class');
    });
  });

  it('displays window minutes in Stage Latencies tab', async () => {
    const user = userEvent.setup();
    render(<PipelineTelemetry windowMinutes={120} pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Stage Latencies')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Stage Latencies'));

    await waitFor(() => {
      expect(screen.getByText(/last 120 minutes/)).toBeInTheDocument();
    });
  });
});
