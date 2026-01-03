/**
 * Tests for AIPerformancePage component
 */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import AIPerformancePage from './AIPerformancePage';

// Mock the useAIMetrics hook
const mockRefresh = vi.fn();

vi.mock('../../hooks/useAIMetrics', () => ({
  useAIMetrics: vi.fn(() => ({
    data: {
      rtdetr: { name: 'RT-DETRv2', status: 'healthy' },
      nemotron: { name: 'Nemotron', status: 'healthy' },
      detectionLatency: { avg_ms: 150, p50_ms: 120, p95_ms: 280, p99_ms: 450, sample_count: 1000 },
      analysisLatency: { avg_ms: 2500, p50_ms: 2000, p95_ms: 4500, p99_ms: 8000, sample_count: 500 },
      pipelineLatency: null,
      totalDetections: 50000,
      totalEvents: 12500,
      detectionQueueDepth: 5,
      analysisQueueDepth: 2,
      pipelineErrors: {},
      queueOverflows: {},
      dlqItems: {},
      lastUpdated: new Date().toISOString(),
    },
    isLoading: false,
    error: null,
    refresh: mockRefresh,
  })),
  default: vi.fn(() => ({
    data: {
      rtdetr: { name: 'RT-DETRv2', status: 'healthy' },
      nemotron: { name: 'Nemotron', status: 'healthy' },
      detectionLatency: null,
      analysisLatency: null,
      pipelineLatency: null,
      totalDetections: 0,
      totalEvents: 0,
      detectionQueueDepth: 0,
      analysisQueueDepth: 0,
      pipelineErrors: {},
      queueOverflows: {},
      dlqItems: {},
      lastUpdated: null,
    },
    isLoading: false,
    error: null,
    refresh: mockRefresh,
  })),
}));

// Mock the fetchConfig and fetchEventStats APIs
vi.mock('../../services/api', () => ({
  fetchConfig: vi.fn(() => Promise.resolve({ grafana_url: 'http://localhost:3002' })),
  fetchEventStats: vi.fn(() =>
    Promise.resolve({
      total_events: 100,
      events_by_risk_level: {
        critical: 5,
        high: 15,
        medium: 30,
        low: 50,
      },
      events_by_camera: [],
    })
  ),
}));

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <AIPerformancePage />
    </MemoryRouter>
  );
};

describe('AIPerformancePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page title', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByText('AI Performance')).toBeInTheDocument();
    });
  });

  it('renders the page description', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(
        screen.getByText(/Real-time AI model metrics, latency statistics, and pipeline health/)
      ).toBeInTheDocument();
    });
  });

  it('renders the refresh button', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
    });
  });

  it('renders the Grafana link banner', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('grafana-banner')).toBeInTheDocument();
    });
  });

  it('renders the model status cards', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('model-status-cards')).toBeInTheDocument();
    });
  });

  it('renders RT-DETRv2 status card', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('rtdetr-status-card')).toBeInTheDocument();
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    });
  });

  it('renders Nemotron status card', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('nemotron-status-card')).toBeInTheDocument();
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });
  });

  it('renders latency panel', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('latency-panel')).toBeInTheDocument();
    });
  });

  it('renders pipeline health panel', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('pipeline-health-panel')).toBeInTheDocument();
    });
  });

  it('has correct data-testid for the page', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('ai-performance-page')).toBeInTheDocument();
    });
  });
});

describe('AIPerformancePage structure', () => {
  it('renders throughput statistics in pipeline health panel', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('throughput-card')).toBeInTheDocument();
    });
  });

  it('renders queue depths card', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('queue-depths-card')).toBeInTheDocument();
    });
  });
});
