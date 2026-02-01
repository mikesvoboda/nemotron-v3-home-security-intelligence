import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import WebSocketHealthPanel from './WebSocketHealthPanel';
import * as api from '../../services/api';

import type { WebSocketHealthResponse } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchWebSocketHealth: vi.fn(),
  };
});

describe('WebSocketHealthPanel', () => {
  const mockHealthyResponse: WebSocketHealthResponse = {
    event_broadcaster: {
      state: 'closed',
      failure_count: 0,
      is_degraded: false,
      message: null,
    },
    system_broadcaster: {
      state: 'closed',
      failure_count: 0,
      is_degraded: false,
      message: null,
    },
    timestamp: '2026-01-30T10:00:00Z',
  };

  const mockDegradedResponse: WebSocketHealthResponse = {
    event_broadcaster: {
      state: 'open',
      failure_count: 3,
      is_degraded: true,
      message: 'Connection failed',
    },
    system_broadcaster: {
      state: 'closed',
      failure_count: 0,
      is_degraded: false,
      message: null,
    },
    timestamp: '2026-01-30T10:00:00Z',
  };

  const mockHalfOpenResponse: WebSocketHealthResponse = {
    event_broadcaster: {
      state: 'half_open',
      failure_count: 1,
      is_degraded: false,
      message: 'Testing recovery',
    },
    system_broadcaster: {
      state: 'closed',
      failure_count: 0,
      is_degraded: false,
      message: null,
    },
    timestamp: '2026-01-30T10:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(api.fetchWebSocketHealth).mockReturnValue(new Promise(() => {}));

    render(<WebSocketHealthPanel />);

    expect(screen.getByTestId('websocket-health-panel-loading')).toBeInTheDocument();
    expect(screen.getByText('WebSocket Health')).toBeInTheDocument();
  });

  it('renders healthy state correctly', async () => {
    vi.mocked(api.fetchWebSocketHealth).mockResolvedValue(mockHealthyResponse);

    render(<WebSocketHealthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('websocket-health-panel')).toBeInTheDocument();
    });

    // Check overall badge
    expect(screen.getByTestId('websocket-overall-badge')).toHaveTextContent('All Healthy');

    // Check broadcaster cards
    expect(screen.getByTestId('broadcaster-card-event')).toBeInTheDocument();
    expect(screen.getByTestId('broadcaster-card-system')).toBeInTheDocument();

    // Check status badges
    expect(screen.getByTestId('broadcaster-status-badge-event')).toHaveTextContent('Healthy');
    expect(screen.getByTestId('broadcaster-status-badge-system')).toHaveTextContent('Healthy');

    // Check descriptions
    expect(screen.getByText('Event Broadcaster')).toBeInTheDocument();
    expect(screen.getByText('System Broadcaster')).toBeInTheDocument();
    expect(screen.getByText('Handles real-time security event distribution')).toBeInTheDocument();
  });

  it('renders degraded state correctly', async () => {
    vi.mocked(api.fetchWebSocketHealth).mockResolvedValue(mockDegradedResponse);

    render(<WebSocketHealthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('websocket-health-panel')).toBeInTheDocument();
    });

    // Check overall badge shows issues
    expect(screen.getByTestId('websocket-overall-badge')).toHaveTextContent('Issues Detected');

    // Check event broadcaster shows open/failing state
    expect(screen.getByTestId('broadcaster-status-badge-event')).toHaveTextContent('Open (Failing)');
    expect(screen.getByTestId('broadcaster-degraded-badge-event')).toHaveTextContent('Degraded');

    // Check failure count is displayed
    expect(screen.getByText('3 consecutive failures')).toBeInTheDocument();

    // Check error message is displayed
    expect(screen.getByText('Connection failed')).toBeInTheDocument();

    // System broadcaster should still show healthy
    expect(screen.getByTestId('broadcaster-status-badge-system')).toHaveTextContent('Healthy');
  });

  it('renders half-open state correctly', async () => {
    vi.mocked(api.fetchWebSocketHealth).mockResolvedValue(mockHalfOpenResponse);

    render(<WebSocketHealthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('websocket-health-panel')).toBeInTheDocument();
    });

    // Check event broadcaster shows half-open/testing state
    expect(screen.getByTestId('broadcaster-status-badge-event')).toHaveTextContent('Testing');
    expect(screen.getByText('Testing recovery')).toBeInTheDocument();
  });

  it('renders error state when fetch fails', async () => {
    vi.mocked(api.fetchWebSocketHealth).mockRejectedValue(new Error('Network error'));

    render(<WebSocketHealthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('websocket-health-panel-error')).toBeInTheDocument();
    });

    expect(screen.getByText('Failed to load')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('handles refresh button click', async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchWebSocketHealth).mockResolvedValue(mockHealthyResponse);

    render(<WebSocketHealthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('websocket-health-panel')).toBeInTheDocument();
    });

    // Initial fetch
    expect(api.fetchWebSocketHealth).toHaveBeenCalledTimes(1);

    // Click refresh
    const refreshBtn = screen.getByTestId('websocket-refresh-btn');
    await user.click(refreshBtn);

    // Should trigger another fetch
    await waitFor(() => {
      expect(api.fetchWebSocketHealth).toHaveBeenCalledTimes(2);
    });
  });

  it('displays timestamp when available', async () => {
    vi.mocked(api.fetchWebSocketHealth).mockResolvedValue(mockHealthyResponse);

    render(<WebSocketHealthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('websocket-health-panel')).toBeInTheDocument();
    });

    expect(screen.getByTestId('websocket-last-updated')).toBeInTheDocument();
    expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
  });

  it('handles unavailable broadcaster status', async () => {
    const unavailableResponse: WebSocketHealthResponse = {
      event_broadcaster: null,
      system_broadcaster: null,
      timestamp: '2026-01-30T10:00:00Z',
    };

    vi.mocked(api.fetchWebSocketHealth).mockResolvedValue(unavailableResponse);

    render(<WebSocketHealthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('websocket-health-panel')).toBeInTheDocument();
    });

    // Should show unavailable state
    expect(screen.getByTestId('broadcaster-status-badge-event')).toHaveTextContent('Unavailable');
    expect(screen.getByTestId('broadcaster-status-badge-system')).toHaveTextContent('Unavailable');
  });

  it('applies custom className', async () => {
    vi.mocked(api.fetchWebSocketHealth).mockResolvedValue(mockHealthyResponse);

    render(<WebSocketHealthPanel className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByTestId('websocket-health-panel')).toBeInTheDocument();
    });

    const panel = screen.getByTestId('websocket-health-panel');
    expect(panel.className).toContain('custom-class');
  });

  it('uses custom data-testid', async () => {
    vi.mocked(api.fetchWebSocketHealth).mockResolvedValue(mockHealthyResponse);

    render(<WebSocketHealthPanel data-testid="custom-testid" />);

    await waitFor(() => {
      expect(screen.getByTestId('custom-testid')).toBeInTheDocument();
    });
  });

  it('displays single failure correctly', async () => {
    const singleFailureResponse: WebSocketHealthResponse = {
      event_broadcaster: {
        state: 'open',
        failure_count: 1,
        is_degraded: true,
        message: null,
      },
      system_broadcaster: {
        state: 'closed',
        failure_count: 0,
        is_degraded: false,
        message: null,
      },
      timestamp: '2026-01-30T10:00:00Z',
    };

    vi.mocked(api.fetchWebSocketHealth).mockResolvedValue(singleFailureResponse);

    render(<WebSocketHealthPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('websocket-health-panel')).toBeInTheDocument();
    });

    // Should display singular "failure" for count of 1
    expect(screen.getByText('1 consecutive failure')).toBeInTheDocument();
  });
});
