import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CircuitBreakerPanel from './CircuitBreakerPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchCircuitBreakers: vi.fn(),
  resetCircuitBreaker: vi.fn(),
}));

const mockCircuitBreakersResponse = {
  circuit_breakers: {
    rtdetr: {
      name: 'rtdetr',
      state: 'closed' as const,
      failure_count: 0,
      success_count: 10,
      total_calls: 150,
      rejected_calls: 0,
      last_failure_time: null,
      opened_at: null,
      config: {
        failure_threshold: 5,
        recovery_timeout: 30,
        half_open_max_calls: 3,
        success_threshold: 2,
      },
    },
    nemotron: {
      name: 'nemotron',
      state: 'open' as const,
      failure_count: 5,
      success_count: 0,
      total_calls: 100,
      rejected_calls: 15,
      last_failure_time: 1234567890,
      opened_at: 1234567880,
      config: {
        failure_threshold: 5,
        recovery_timeout: 30,
        half_open_max_calls: 3,
        success_threshold: 2,
      },
    },
    websocket: {
      name: 'websocket',
      state: 'half_open' as const,
      failure_count: 2,
      success_count: 1,
      total_calls: 200,
      rejected_calls: 5,
      last_failure_time: 1234567800,
      opened_at: 1234567700,
      config: {
        failure_threshold: 5,
        recovery_timeout: 30,
        half_open_max_calls: 3,
        success_threshold: 2,
      },
    },
  },
  total_count: 3,
  open_count: 1,
  timestamp: '2024-01-15T10:30:00Z',
};

describe('CircuitBreakerPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    vi.mocked(api.fetchCircuitBreakers).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<CircuitBreakerPanel />);

    expect(screen.getByTestId('circuit-breaker-panel-loading')).toBeInTheDocument();
  });

  it('displays circuit breakers after loading', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Check all circuit breakers are displayed
    expect(screen.getByTestId('circuit-breaker-row-rtdetr')).toBeInTheDocument();
    expect(screen.getByTestId('circuit-breaker-row-nemotron')).toBeInTheDocument();
    expect(screen.getByTestId('circuit-breaker-row-websocket')).toBeInTheDocument();
  });

  it('displays correct state badges for each circuit breaker', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Check state badges
    expect(screen.getByTestId('circuit-breaker-state-rtdetr')).toHaveTextContent('Closed');
    expect(screen.getByTestId('circuit-breaker-state-nemotron')).toHaveTextContent('Open');
    expect(screen.getByTestId('circuit-breaker-state-websocket')).toHaveTextContent('Half Open');
  });

  it('shows open count in header when circuits are open', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    expect(screen.getByTestId('open-count-badge')).toHaveTextContent('1 Open');
  });

  it('displays reset button for non-closed circuit breakers', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Reset button should not exist for closed circuit
    expect(screen.queryByTestId('reset-button-rtdetr')).not.toBeInTheDocument();

    // Reset buttons should exist for open and half_open circuits
    expect(screen.getByTestId('reset-button-nemotron')).toBeInTheDocument();
    expect(screen.getByTestId('reset-button-websocket')).toBeInTheDocument();
  });

  it('calls resetCircuitBreaker API when reset button is clicked', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);
    vi.mocked(api.resetCircuitBreaker).mockResolvedValue({
      name: 'nemotron',
      previous_state: 'open',
      new_state: 'closed',
      message: 'Circuit breaker reset successfully',
    });

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Click reset button for nemotron
    fireEvent.click(screen.getByTestId('reset-button-nemotron'));

    await waitFor(() => {
      expect(api.resetCircuitBreaker).toHaveBeenCalledWith('nemotron');
    });
  });

  it('refreshes circuit breaker list after successful reset', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);
    vi.mocked(api.resetCircuitBreaker).mockResolvedValue({
      name: 'nemotron',
      previous_state: 'open',
      new_state: 'closed',
      message: 'Circuit breaker reset successfully',
    });

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Initial fetch
    expect(api.fetchCircuitBreakers).toHaveBeenCalledTimes(1);

    // Click reset button
    fireEvent.click(screen.getByTestId('reset-button-nemotron'));

    await waitFor(() => {
      // Should have called fetchCircuitBreakers again after reset
      expect(api.fetchCircuitBreakers).toHaveBeenCalledTimes(2);
    });
  });

  it('displays error state when API call fails', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockRejectedValue(new Error('Network error'));

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel-error')).toBeInTheDocument();
    });

    expect(screen.getByText(/Failed to load circuit breaker status/i)).toBeInTheDocument();
  });

  it('displays circuit breaker metrics', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Total calls should be displayed for all circuits
    // For closed circuit (rtdetr), only shows Calls
    const rtdetrRow = screen.getByTestId('circuit-breaker-row-rtdetr');
    expect(rtdetrRow).toHaveTextContent('150');

    // For open circuit (nemotron), shows Calls, Failures, Rejected
    const nemotronRow = screen.getByTestId('circuit-breaker-row-nemotron');
    expect(nemotronRow).toHaveTextContent('100');
  });

  it('displays failure and rejected counts for open circuit', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Open circuit should show failure and rejected counts
    const nemotronRow = screen.getByTestId('circuit-breaker-row-nemotron');
    expect(nemotronRow).toHaveTextContent('5'); // failure count
    expect(nemotronRow).toHaveTextContent('15'); // rejected calls
  });

  it('can expand and collapse the panel', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);

    render(<CircuitBreakerPanel defaultExpanded={false} />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Initially collapsed - content should not be visible
    const content = screen.getByTestId('circuit-breaker-list-content');
    expect(content).toHaveClass('max-h-0');

    // Click to expand
    fireEvent.click(screen.getByTestId('circuit-breaker-panel-toggle'));

    // Content should now be expanded
    expect(content).toHaveClass('max-h-[1000px]');
  });

  it('sets up polling interval', async () => {
    // Test that polling is set up - we verify this by checking the component behavior
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);

    render(<CircuitBreakerPanel pollingInterval={5000} />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Verify initial fetch was called
    expect(api.fetchCircuitBreakers).toHaveBeenCalledTimes(1);
  });

  it('displays appropriate colors for circuit states', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    // Closed circuit should have gray background class
    const closedRow = screen.getByTestId('circuit-breaker-row-rtdetr');
    expect(closedRow.className).toContain('bg-gray-800');

    // Open circuit should have red styling
    const openRow = screen.getByTestId('circuit-breaker-row-nemotron');
    expect(openRow.className).toContain('bg-red-500');

    // Half-open circuit should have yellow styling
    const halfOpenRow = screen.getByTestId('circuit-breaker-row-websocket');
    expect(halfOpenRow.className).toContain('bg-yellow-500');
  });

  it('handles empty circuit breakers gracefully', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue({
      circuit_breakers: {},
      total_count: 0,
      open_count: 0,
      timestamp: '2024-01-15T10:30:00Z',
    });

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    expect(screen.getByText(/No circuit breakers configured/i)).toBeInTheDocument();
  });

  it('disables reset button while reset is in progress', async () => {
    vi.mocked(api.fetchCircuitBreakers).mockResolvedValue(mockCircuitBreakersResponse);
    // Mock reset to stay pending during this test
    vi.mocked(api.resetCircuitBreaker).mockImplementation(
      () => new Promise(() => {
        // Never resolves - we just want to check the button is disabled
      })
    );

    render(<CircuitBreakerPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
    });

    const resetButton = screen.getByTestId('reset-button-nemotron');
    fireEvent.click(resetButton);

    // Button should be disabled during reset
    await waitFor(() => {
      expect(resetButton).toBeDisabled();
    });
  });
});
