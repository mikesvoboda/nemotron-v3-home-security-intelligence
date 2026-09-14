import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CircuitBreakerPanel from './CircuitBreakerPanel';

import type {
  CircuitBreakerStateEnum,
  CircuitBreakerStatusResponse,
  CircuitBreakersResponse,
} from '../../types/generated';

// Mock data generators
function createMockCircuitBreaker(
  name: string,
  state: CircuitBreakerStateEnum,
  failureCount: number = 0
): CircuitBreakerStatusResponse {
  return {
    name,
    state,
    failure_count: failureCount,
    success_count: state === 'closed' ? 10 : 0,
    total_calls: 100,
    rejected_calls: state === 'open' ? 5 : 0,
    last_failure_time: failureCount > 0 ? 12345.678 : null,
    opened_at: state === 'open' ? 12340.0 : null,
    config: {
      failure_threshold: 5,
      recovery_timeout: 60,
      half_open_max_calls: 3,
      success_threshold: 2,
    },
  };
}

function createMockCircuitBreakersResponse(
  breakers: Record<string, CircuitBreakerStatusResponse>
): CircuitBreakersResponse {
  const openCount = Object.values(breakers).filter((b) => b.state === 'open').length;
  return {
    circuit_breakers: breakers,
    total_count: Object.keys(breakers).length,
    open_count: openCount,
    timestamp: '2025-01-01T12:00:00Z',
  };
}

// Mock circuit breakers data
const mockAllClosed: CircuitBreakersResponse = createMockCircuitBreakersResponse({
  rtdetr_detection: createMockCircuitBreaker('rtdetr_detection', 'closed'),
  nemotron_analysis: createMockCircuitBreaker('nemotron_analysis', 'closed'),
});

const mockOneOpen: CircuitBreakersResponse = createMockCircuitBreakersResponse({
  rtdetr_detection: createMockCircuitBreaker('rtdetr_detection', 'closed'),
  nemotron_analysis: createMockCircuitBreaker('nemotron_analysis', 'open', 5),
});

const mockOneHalfOpen: CircuitBreakersResponse = createMockCircuitBreakersResponse({
  rtdetr_detection: createMockCircuitBreaker('rtdetr_detection', 'half_open', 3),
  nemotron_analysis: createMockCircuitBreaker('nemotron_analysis', 'closed'),
});

const mockMixedStates: CircuitBreakersResponse = createMockCircuitBreakersResponse({
  rtdetr_detection: createMockCircuitBreaker('rtdetr_detection', 'open', 5),
  nemotron_analysis: createMockCircuitBreaker('nemotron_analysis', 'half_open', 2),
  florence_vision: createMockCircuitBreaker('florence_vision', 'closed'),
});

describe('CircuitBreakerPanel', () => {
  const mockOnReset = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the component with title', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('circuit-breaker-panel')).toBeInTheDocument();
      expect(screen.getByText('Circuit Breakers')).toBeInTheDocument();
    });

    it('renders all circuit breakers', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('circuit-breaker-rtdetr_detection')).toBeInTheDocument();
      expect(screen.getByTestId('circuit-breaker-nemotron_analysis')).toBeInTheDocument();
    });

    it('displays circuit breaker names', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByText('rtdetr_detection')).toBeInTheDocument();
      expect(screen.getByText('nemotron_analysis')).toBeInTheDocument();
    });
  });

  describe('state display', () => {
    it('displays green badge for CLOSED state', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      const rtdetrStatus = screen.getByTestId('circuit-breaker-status-rtdetr_detection');
      expect(rtdetrStatus).toHaveTextContent('closed');
    });

    it('displays red badge for OPEN state', () => {
      render(
        <CircuitBreakerPanel
          data={mockOneOpen}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      const nemotronStatus = screen.getByTestId('circuit-breaker-status-nemotron_analysis');
      expect(nemotronStatus).toHaveTextContent('open');
    });

    it('displays yellow badge for HALF_OPEN state', () => {
      render(
        <CircuitBreakerPanel
          data={mockOneHalfOpen}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      const rtdetrStatus = screen.getByTestId('circuit-breaker-status-rtdetr_detection');
      expect(rtdetrStatus).toHaveTextContent('half_open');
    });
  });

  describe('failure count display', () => {
    it('displays failure count when greater than zero', () => {
      render(
        <CircuitBreakerPanel
          data={mockOneOpen}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('failure-count-nemotron_analysis')).toHaveTextContent('5');
    });

    it('displays zero failure count for healthy breakers', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('failure-count-rtdetr_detection')).toHaveTextContent('0');
    });
  });

  describe('last failure time display', () => {
    it('displays last failure time when available', () => {
      render(
        <CircuitBreakerPanel
          data={mockOneOpen}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      // Should show some formatted time
      expect(screen.getByTestId('last-failure-nemotron_analysis')).toBeInTheDocument();
    });

    it('displays N/A when no failure time', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('last-failure-rtdetr_detection')).toHaveTextContent('N/A');
    });
  });

  describe('configuration display', () => {
    it('displays failure threshold', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      // Should show threshold in the config section
      expect(screen.getByTestId('config-rtdetr_detection')).toHaveTextContent('5');
    });

    it('displays recovery timeout', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      // Should show timeout in seconds
      expect(screen.getByTestId('config-rtdetr_detection')).toHaveTextContent('60');
    });
  });

  describe('reset button', () => {
    it('shows reset button for OPEN state breakers', () => {
      render(
        <CircuitBreakerPanel
          data={mockOneOpen}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('reset-button-nemotron_analysis')).toBeInTheDocument();
    });

    it('shows reset button for HALF_OPEN state breakers', () => {
      render(
        <CircuitBreakerPanel
          data={mockOneHalfOpen}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('reset-button-rtdetr_detection')).toBeInTheDocument();
    });

    it('does not show reset button for CLOSED state breakers', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.queryByTestId('reset-button-rtdetr_detection')).not.toBeInTheDocument();
      expect(screen.queryByTestId('reset-button-nemotron_analysis')).not.toBeInTheDocument();
    });

    it('calls onReset when reset button is clicked', async () => {
      render(
        <CircuitBreakerPanel
          data={mockOneOpen}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      const resetButton = screen.getByTestId('reset-button-nemotron_analysis');
      fireEvent.click(resetButton);

      await waitFor(() => {
        expect(mockOnReset).toHaveBeenCalledWith('nemotron_analysis');
      });
    });

    it('calls onReset with correct name for each breaker', () => {
      render(
        <CircuitBreakerPanel
          data={mockMixedStates}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      const rtdetrResetButton = screen.getByTestId('reset-button-rtdetr_detection');
      const nemotronResetButton = screen.getByTestId('reset-button-nemotron_analysis');

      fireEvent.click(rtdetrResetButton);
      expect(mockOnReset).toHaveBeenCalledWith('rtdetr_detection');

      fireEvent.click(nemotronResetButton);
      expect(mockOnReset).toHaveBeenCalledWith('nemotron_analysis');
    });
  });

  describe('summary statistics', () => {
    it('displays correct count when all breakers are healthy', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('circuit-breaker-summary')).toHaveTextContent('2/2 Healthy');
    });

    it('displays correct count when some breakers are unhealthy', () => {
      render(
        <CircuitBreakerPanel
          data={mockOneOpen}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('circuit-breaker-summary')).toHaveTextContent('1/2 Healthy');
    });

    it('displays correct count with mixed states', () => {
      render(
        <CircuitBreakerPanel
          data={mockMixedStates}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('circuit-breaker-summary')).toHaveTextContent('1/3 Healthy');
    });
  });

  describe('loading state', () => {
    it('displays loading skeleton when loading is true', () => {
      render(<CircuitBreakerPanel data={null} loading={true} error={null} onReset={mockOnReset} />);

      expect(screen.getByTestId('circuit-breaker-panel-loading')).toBeInTheDocument();
    });

    it('does not display breakers when loading', () => {
      render(<CircuitBreakerPanel data={null} loading={true} error={null} onReset={mockOnReset} />);

      expect(screen.queryByTestId('circuit-breaker-rtdetr_detection')).not.toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('displays error message when error is present', () => {
      render(
        <CircuitBreakerPanel
          data={null}
          loading={false}
          error="Failed to fetch circuit breakers"
          onReset={mockOnReset}
        />
      );

      expect(screen.getByTestId('circuit-breaker-panel-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to fetch circuit breakers/i)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('displays message when no circuit breakers are available', () => {
      const emptyData = createMockCircuitBreakersResponse({});

      render(
        <CircuitBreakerPanel data={emptyData} loading={false} error={null} onReset={mockOnReset} />
      );

      expect(screen.getByText(/No circuit breakers/i)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has proper aria attributes on reset buttons', () => {
      render(
        <CircuitBreakerPanel
          data={mockOneOpen}
          loading={false}
          error={null}
          onReset={mockOnReset}
        />
      );

      const resetButton = screen.getByTestId('reset-button-nemotron_analysis');
      expect(resetButton).toHaveAttribute('aria-label');
    });
  });

  describe('debug mode', () => {
    const mockWebSocketStatus = {
      event_broadcaster: {
        connection_count: 5,
        is_listening: true,
        is_degraded: false,
        circuit_state: 'CLOSED',
        channel_name: 'events',
      },
      system_broadcaster: {
        connection_count: 3,
        is_listening: true,
        is_degraded: false,
        circuit_state: 'CLOSED',
        channel_name: null,
      },
    };

    it('does not render debug section when debugMode is false', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={false}
        />
      );

      expect(screen.queryByTestId('websocket-debug-section')).not.toBeInTheDocument();
      expect(screen.queryByText('DEBUG')).not.toBeInTheDocument();
    });

    it('renders debug section when debugMode is true', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketStatus={mockWebSocketStatus}
        />
      );

      expect(screen.getByTestId('websocket-debug-section')).toBeInTheDocument();
    });

    it('displays DEBUG badge when debugMode is true', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketStatus={mockWebSocketStatus}
        />
      );

      expect(screen.getByText('DEBUG')).toBeInTheDocument();
    });

    it('renders WebSocket broadcaster status when provided', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketStatus={mockWebSocketStatus}
        />
      );

      expect(screen.getByText('Event Broadcaster')).toBeInTheDocument();
      expect(screen.getByText('System Broadcaster')).toBeInTheDocument();
    });

    it('displays connection counts for each broadcaster', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketStatus={mockWebSocketStatus}
        />
      );

      // Event broadcaster has 5 connections, system has 3, total 8
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('8 connections')).toBeInTheDocument();
    });

    it('displays circuit state for each broadcaster', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketStatus={mockWebSocketStatus}
        />
      );

      // Should show CLOSED state badges
      const closedBadges = screen.getAllByText('CLOSED');
      expect(closedBadges.length).toBeGreaterThanOrEqual(2);
    });

    it('shows degraded status when broadcaster is degraded', () => {
      const degradedStatus = {
        ...mockWebSocketStatus,
        event_broadcaster: {
          ...mockWebSocketStatus.event_broadcaster,
          is_degraded: true,
        },
      };

      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketStatus={degradedStatus}
        />
      );

      expect(screen.getByText('Degraded')).toBeInTheDocument();
    });

    it('shows loading state when webSocketLoading is true', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketLoading={true}
        />
      );

      expect(screen.getByTestId('websocket-debug-loading')).toBeInTheDocument();
    });

    it('shows error state when webSocketError is provided', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketError="Failed to fetch WebSocket status"
        />
      );

      expect(screen.getByText('Failed to fetch WebSocket status')).toBeInTheDocument();
    });

    it('shows no status message when webSocketStatus is null', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketStatus={null}
        />
      );

      expect(screen.getByText('No WebSocket status available')).toBeInTheDocument();
    });

    it('displays channel name when available', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketStatus={mockWebSocketStatus}
        />
      );

      expect(screen.getByText('events')).toBeInTheDocument();
    });

    it('applies orange accent styling to debug section', () => {
      render(
        <CircuitBreakerPanel
          data={mockAllClosed}
          loading={false}
          error={null}
          onReset={mockOnReset}
          debugMode={true}
          webSocketStatus={mockWebSocketStatus}
        />
      );

      const debugSection = screen.getByTestId('websocket-debug-section');
      expect(debugSection.className).toContain('border-orange-500');
    });
  });
});
