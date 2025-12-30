import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CircuitBreakerPanel from './CircuitBreakerPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchCircuitBreakers: vi.fn(),
  resetCircuitBreaker: vi.fn(),
}));

const mockFetchCircuitBreakers = vi.mocked(api.fetchCircuitBreakers);
const mockResetCircuitBreaker = vi.mocked(api.resetCircuitBreaker);

describe('CircuitBreakerPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    mockFetchCircuitBreakers.mockImplementation(() => new Promise(() => {}));

    render(<CircuitBreakerPanel />);

    expect(screen.getByTestId('circuit-breaker-panel-loading')).toBeInTheDocument();
    expect(screen.getByText('Circuit Breakers')).toBeInTheDocument();
  });

  it('renders empty state when no circuit breakers registered', async () => {
    mockFetchCircuitBreakers.mockResolvedValue({
      circuit_breakers: {},
      total_count: 0,
      open_count: 0,
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel-empty')).toBeInTheDocument();
    });
    expect(screen.getByText('No circuit breakers registered yet')).toBeInTheDocument();
  });

  it('renders circuit breakers in closed state', async () => {
    mockFetchCircuitBreakers.mockResolvedValue({
      circuit_breakers: {
        rtdetr: {
          name: 'rtdetr',
          state: 'closed',
          failure_count: 0,
          success_count: 0,
          total_calls: 100,
          rejected_calls: 0,
          last_failure_time: null,
          opened_at: null,
          config: {
            failure_threshold: 5,
            recovery_timeout: 30.0,
            half_open_max_calls: 3,
            success_threshold: 2,
          },
        },
      },
      total_count: 1,
      open_count: 0,
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    expect(screen.getByTestId('circuit-breaker-row-rtdetr')).toBeInTheDocument();
    expect(screen.getByTestId('state-badge-rtdetr')).toHaveTextContent('Closed');
    expect(screen.getByText('1/1 Healthy')).toBeInTheDocument();
  });

  it('renders circuit breakers in open state with reset button', async () => {
    mockFetchCircuitBreakers.mockResolvedValue({
      circuit_breakers: {
        rtdetr: {
          name: 'rtdetr',
          state: 'open',
          failure_count: 5,
          success_count: 0,
          total_calls: 100,
          rejected_calls: 25,
          last_failure_time: 12345.0,
          opened_at: 12340.0,
          config: {
            failure_threshold: 5,
            recovery_timeout: 30.0,
            half_open_max_calls: 3,
            success_threshold: 2,
          },
        },
      },
      total_count: 1,
      open_count: 1,
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    expect(screen.getByTestId('state-badge-rtdetr')).toHaveTextContent('Open');
    expect(screen.getByTestId('open-count-badge')).toHaveTextContent('1 Open');
    expect(screen.getByTestId('reset-button-rtdetr')).toBeInTheDocument();
  });

  it('renders circuit breakers in half-open state', async () => {
    mockFetchCircuitBreakers.mockResolvedValue({
      circuit_breakers: {
        rtdetr: {
          name: 'rtdetr',
          state: 'half_open',
          failure_count: 0,
          success_count: 1,
          total_calls: 101,
          rejected_calls: 25,
          last_failure_time: 12345.0,
          opened_at: 12340.0,
          config: {
            failure_threshold: 5,
            recovery_timeout: 30.0,
            half_open_max_calls: 3,
            success_threshold: 2,
          },
        },
      },
      total_count: 1,
      open_count: 0,
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    expect(screen.getByTestId('state-badge-rtdetr')).toHaveTextContent('Half-Open');
    expect(screen.getByTestId('half-open-count-badge')).toHaveTextContent('1 Half-Open');
  });

  it('handles reset button click', async () => {
    mockFetchCircuitBreakers.mockResolvedValue({
      circuit_breakers: {
        rtdetr: {
          name: 'rtdetr',
          state: 'open',
          failure_count: 5,
          success_count: 0,
          total_calls: 100,
          rejected_calls: 25,
          last_failure_time: 12345.0,
          opened_at: 12340.0,
          config: {
            failure_threshold: 5,
            recovery_timeout: 30.0,
            half_open_max_calls: 3,
            success_threshold: 2,
          },
        },
      },
      total_count: 1,
      open_count: 1,
      timestamp: '2025-12-30T10:30:00Z',
    });

    mockResetCircuitBreaker.mockResolvedValue({
      name: 'rtdetr',
      previous_state: 'open',
      new_state: 'closed',
      message: 'Circuit breaker rtdetr reset successfully from open to closed',
    });

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('reset-button-rtdetr')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('reset-button-rtdetr'));

    await waitFor(() => {
      expect(mockResetCircuitBreaker).toHaveBeenCalledWith('rtdetr');
    });
  });

  it('renders error state when fetch fails', async () => {
    mockFetchCircuitBreakers.mockRejectedValue(new Error('Network error'));

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel-error')).toBeInTheDocument();
    });

    expect(screen.getByText('Failed to load circuit breaker status')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('calls onStatusChange when status updates', async () => {
    const onStatusChange = vi.fn();

    mockFetchCircuitBreakers.mockResolvedValue({
      circuit_breakers: {
        rtdetr: {
          name: 'rtdetr',
          state: 'closed',
          failure_count: 0,
          success_count: 0,
          total_calls: 100,
          rejected_calls: 0,
          last_failure_time: null,
          opened_at: null,
          config: {
            failure_threshold: 5,
            recovery_timeout: 30.0,
            half_open_max_calls: 3,
            success_threshold: 2,
          },
        },
      },
      total_count: 1,
      open_count: 0,
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CircuitBreakerPanel onStatusChange={onStatusChange} />);

    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalledWith([
        expect.objectContaining({ name: 'rtdetr', state: 'closed' }),
      ]);
    });
  });

  it('displays metrics for circuit breakers', async () => {
    mockFetchCircuitBreakers.mockResolvedValue({
      circuit_breakers: {
        rtdetr: {
          name: 'rtdetr',
          state: 'closed',
          failure_count: 2,
          success_count: 0,
          total_calls: 1500,
          rejected_calls: 0,
          last_failure_time: null,
          opened_at: null,
          config: {
            failure_threshold: 5,
            recovery_timeout: 30.0,
            half_open_max_calls: 3,
            success_threshold: 2,
          },
        },
      },
      total_count: 1,
      open_count: 0,
      timestamp: '2025-12-30T10:30:00Z',
    });

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    expect(screen.getByText(/Failures:/)).toBeInTheDocument();
    expect(screen.getByText(/Total calls:/)).toBeInTheDocument();
    expect(screen.getByText('1,500')).toBeInTheDocument();
  });
});
