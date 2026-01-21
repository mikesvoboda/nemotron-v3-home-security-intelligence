/**
 * Tests for CircuitBreakerDebugPanel component
 *
 * The CircuitBreakerDebugPanel displays:
 * - All circuit breaker states with detailed info
 * - Failure/success counts and timestamps
 * - Configuration details
 * - Manual reset controls
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import CircuitBreakerDebugPanel from './CircuitBreakerDebugPanel';
import * as useCircuitBreakerDebugQueryModule from '../../hooks/useCircuitBreakerDebugQuery';
import { createQueryClient } from '../../services/queryClient';

// Mock the hooks
vi.mock('../../hooks/useCircuitBreakerDebugQuery');

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('CircuitBreakerDebugPanel', () => {
  let queryClient: QueryClient;

  const mockUseCircuitBreakerDebugQuery = vi.mocked(
    useCircuitBreakerDebugQueryModule.useCircuitBreakerDebugQuery
  );
  const mockRefetchFn = vi.fn();
  const mockResetBreakerFn = vi.fn();

  const mockCircuitBreakers = {
    circuit_breakers: {
      rtdetr_detection: {
        name: 'rtdetr_detection',
        state: 'closed' as const,
        failure_count: 0,
        success_count: 10,
        last_failure_time: null,
        config: {
          failure_threshold: 5,
          recovery_timeout: 60,
          half_open_max_calls: 3,
        },
      },
      nemotron_analysis: {
        name: 'nemotron_analysis',
        state: 'open' as const,
        failure_count: 5,
        success_count: 0,
        last_failure_time: 12345.678,
        config: {
          failure_threshold: 5,
          recovery_timeout: 60,
          half_open_max_calls: 3,
        },
      },
      florence_vision: {
        name: 'florence_vision',
        state: 'half_open' as const,
        failure_count: 3,
        success_count: 1,
        last_failure_time: 12340.0,
        config: {
          failure_threshold: 5,
          recovery_timeout: 60,
          half_open_max_calls: 3,
        },
      },
    },
    timestamp: '2024-01-15T10:30:00Z',
  };

  const defaultQueryReturn = {
    data: undefined,
    isLoading: false,
    isRefetching: false,
    error: null,
    refetch: mockRefetchFn,
    resetBreaker: mockResetBreakerFn,
    isResetPending: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();

    // Set up default mock returns
    mockUseCircuitBreakerDebugQuery.mockReturnValue(defaultQueryReturn);
  });

  afterEach(() => {
    queryClient.clear();
  });

  describe('loading state', () => {
    it('displays loading state when fetching circuit breakers', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        isLoading: true,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('circuit-breaker-debug-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('displays error message when query fails', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        error: new Error('Failed to fetch circuit breakers'),
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('circuit-breaker-debug-error')).toBeInTheDocument();
      expect(screen.getByText(/failed to fetch circuit breakers/i)).toBeInTheDocument();
    });

    it('displays retry button on error', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        error: new Error('Failed to fetch circuit breakers'),
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('calls refetch when retry is clicked', async () => {
      const user = userEvent.setup();
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        error: new Error('Failed to fetch circuit breakers'),
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /retry/i }));

      expect(mockRefetchFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('empty state', () => {
    it('displays empty state when no circuit breakers', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: { circuit_breakers: {}, timestamp: '2024-01-15T10:30:00Z' },
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/no circuit breakers registered/i)).toBeInTheDocument();
    });
  });

  describe('circuit breaker display', () => {
    it('displays circuit breaker names', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText('rtdetr_detection')).toBeInTheDocument();
      expect(screen.getByText('nemotron_analysis')).toBeInTheDocument();
      expect(screen.getByText('florence_vision')).toBeInTheDocument();
    });

    it('displays circuit breaker states with badges', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText('closed')).toBeInTheDocument();
      expect(screen.getByText('open')).toBeInTheDocument();
      expect(screen.getByText('half_open')).toBeInTheDocument();
    });

    it('displays failure counts', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      // Check for failure count display (multiple breakers have Failures labels)
      const failuresLabels = screen.getAllByText(/Failures/i);
      expect(failuresLabels.length).toBeGreaterThan(0);
    });
  });

  describe('summary badge', () => {
    it('displays healthy summary when all closed', () => {
      const allClosedData = {
        circuit_breakers: {
          rtdetr: {
            name: 'rtdetr',
            state: 'closed' as const,
            failure_count: 0,
            success_count: 10,
            last_failure_time: null,
            config: {
              failure_threshold: 5,
              recovery_timeout: 60,
              half_open_max_calls: 3,
            },
          },
        },
        timestamp: '2024-01-15T10:30:00Z',
      };

      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: allClosedData,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/1\/1 healthy/i)).toBeInTheDocument();
    });

    it('displays unhealthy summary when breakers are open', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/1\/3 healthy/i)).toBeInTheDocument();
    });
  });

  describe('reset functionality', () => {
    it('displays reset button for non-closed breakers', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      // Should have reset buttons for open and half_open breakers
      const resetButtons = screen.getAllByRole('button', { name: /reset/i });
      expect(resetButtons.length).toBeGreaterThanOrEqual(2); // open and half_open
    });

    it('calls resetBreaker when reset is clicked', async () => {
      const user = userEvent.setup();
      mockResetBreakerFn.mockResolvedValue({});
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      // Click the first reset button (could be for either open or half_open)
      const resetButtons = screen.getAllByRole('button', { name: /reset/i });
      await user.click(resetButtons[0]);

      expect(mockResetBreakerFn).toHaveBeenCalled();
    });

    it('does not show reset button for closed breakers', () => {
      const closedOnlyData = {
        circuit_breakers: {
          rtdetr: {
            name: 'rtdetr',
            state: 'closed' as const,
            failure_count: 0,
            success_count: 10,
            last_failure_time: null,
            config: {
              failure_threshold: 5,
              recovery_timeout: 60,
              half_open_max_calls: 3,
            },
          },
        },
        timestamp: '2024-01-15T10:30:00Z',
      };

      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: closedOnlyData,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      // Find the breaker row and verify no reset button exists within it
      const breakerRow = screen.getByTestId('circuit-breaker-row-rtdetr');
      // Query within the row for reset buttons
      const resetButtonInRow = breakerRow.querySelector('button[aria-label*="Reset"]');
      expect(resetButtonInRow).toBeNull();
    });
  });

  describe('refresh functionality', () => {
    it('displays refresh button', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });

    it('calls refetch when refresh is clicked', async () => {
      const user = userEvent.setup();
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /refresh/i }));

      expect(mockRefetchFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('configuration details', () => {
    it('displays threshold configuration', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      // Check for configuration display (multiple breakers have these labels)
      const thresholdLabels = screen.getAllByText(/Threshold/i);
      expect(thresholdLabels.length).toBeGreaterThan(0);
      const timeoutLabels = screen.getAllByText(/Timeout/i);
      expect(timeoutLabels.length).toBeGreaterThan(0);
    });
  });

  describe('accessibility', () => {
    it('has accessible panel with data-testid', () => {
      mockUseCircuitBreakerDebugQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockCircuitBreakers,
      });

      render(<CircuitBreakerDebugPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('circuit-breaker-debug-panel')).toBeInTheDocument();
    });
  });
});
