/**
 * Tests for ProfilingPanel component
 *
 * The ProfilingPanel displays:
 * - Status (Idle or Profiling with elapsed time)
 * - Start/Stop profiling buttons
 * - Results table with top functions by CPU time
 * - Download button for .prof file
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import ProfilingPanel from './ProfilingPanel';
import * as useProfileQueryModule from '../../hooks/useProfileQuery';
import * as useProfilingMutationsModule from '../../hooks/useProfilingMutations';
import { createQueryClient } from '../../services/queryClient';

// Mock the hooks
vi.mock('../../hooks/useProfileQuery');
vi.mock('../../hooks/useProfilingMutations');

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('ProfilingPanel', () => {
  let queryClient: QueryClient;

  const mockUseProfileQuery = vi.mocked(useProfileQueryModule.useProfileQuery);
  const mockUseStartProfilingMutation = vi.mocked(
    useProfilingMutationsModule.useStartProfilingMutation
  );
  const mockUseStopProfilingMutation = vi.mocked(
    useProfilingMutationsModule.useStopProfilingMutation
  );
  const mockUseDownloadProfileMutation = vi.mocked(
    useProfilingMutationsModule.useDownloadProfileMutation
  );

  const mockStartFn = vi.fn();
  const mockStopFn = vi.fn();
  const mockDownloadFn = vi.fn();
  const mockRefetchFn = vi.fn();
  const mockResetFn = vi.fn();

  const defaultQueryReturn = {
    data: undefined,
    isLoading: false,
    isRefetching: false,
    isProfiling: false,
    elapsedSeconds: null,
    results: null,
    error: null,
    refetch: mockRefetchFn,
  };

  const defaultStartMutationReturn = {
    start: mockStartFn,
    isPending: false,
    error: null,
    reset: mockResetFn,
  };

  const defaultStopMutationReturn = {
    stop: mockStopFn,
    results: undefined,
    isPending: false,
    error: null,
    reset: mockResetFn,
  };

  const defaultDownloadMutationReturn = {
    download: mockDownloadFn,
    isPending: false,
    error: null,
    reset: mockResetFn,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();

    // Set up default mock returns
    mockUseProfileQuery.mockReturnValue(defaultQueryReturn);
    mockUseStartProfilingMutation.mockReturnValue(defaultStartMutationReturn);
    mockUseStopProfilingMutation.mockReturnValue(defaultStopMutationReturn);
    mockUseDownloadProfileMutation.mockReturnValue(defaultDownloadMutationReturn);
  });

  afterEach(() => {
    queryClient.clear();
  });

  describe('loading state', () => {
    it('displays loading state when fetching profile status', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isLoading: true,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('profiling-panel-loading')).toBeInTheDocument();
    });
  });

  describe('idle state', () => {
    it('displays Idle status when not profiling', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/idle/i)).toBeInTheDocument();
    });

    it('displays Start Profiling button when idle', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /start profiling/i })).toBeInTheDocument();
    });

    it('calls start mutation when Start Profiling is clicked', async () => {
      const user = userEvent.setup();
      mockStartFn.mockResolvedValue({});

      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /start profiling/i }));

      expect(mockStartFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('profiling state', () => {
    it('displays Profiling status when profiling is active', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: true,
        elapsedSeconds: 32,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      // Look for the status text specifically (not the title or button)
      expect(screen.getByText(/Profiling\.\.\./)).toBeInTheDocument();
    });

    it('displays elapsed time when profiling', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: true,
        elapsedSeconds: 32,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/32s/)).toBeInTheDocument();
    });

    it('displays Stop Profiling button when profiling', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: true,
        elapsedSeconds: 32,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /stop profiling/i })).toBeInTheDocument();
    });

    it('calls stop mutation when Stop Profiling is clicked', async () => {
      const user = userEvent.setup();
      mockStopFn.mockResolvedValue({});

      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: true,
        elapsedSeconds: 32,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /stop profiling/i }));

      expect(mockStopFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('results display', () => {
    const mockResults = {
      total_time: 45.0,
      top_functions: [
        {
          function_name: 'process_image',
          call_count: 1500,
          total_time: 15.5,
          cumulative_time: 20.3,
          percentage: 34.5,
        },
        {
          function_name: 'detect_objects',
          call_count: 1200,
          total_time: 10.2,
          cumulative_time: 12.1,
          percentage: 22.7,
        },
      ],
    };

    it('displays results table when results are available', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
        results: mockResults,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    it('displays function names in results table', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
        results: mockResults,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText('process_image')).toBeInTheDocument();
      expect(screen.getByText('detect_objects')).toBeInTheDocument();
    });

    it('displays call counts in results table', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
        results: mockResults,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText('1500')).toBeInTheDocument();
      expect(screen.getByText('1200')).toBeInTheDocument();
    });

    it('displays time values in results table', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
        results: mockResults,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/15\.5/)).toBeInTheDocument();
    });

    it('displays percentage with visual bar', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
        results: mockResults,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/34\.5%/)).toBeInTheDocument();
      // Check for progress bar by querying for Tremor ProgressBar component
      // Tremor renders progress bars with a specific class structure
      const progressBarContainers = document.querySelectorAll('[class*="tremor-ProgressBar"]');
      expect(progressBarContainers.length).toBeGreaterThan(0);
    });

    it('displays Download Profile button when results are available', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
        results: mockResults,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /download.*\.prof/i })).toBeInTheDocument();
    });

    it('calls download mutation when Download is clicked', async () => {
      const user = userEvent.setup();
      mockDownloadFn.mockResolvedValue(new Blob());

      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
        results: mockResults,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /download.*\.prof/i }));

      expect(mockDownloadFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('loading states during operations', () => {
    it('disables Start button while starting', () => {
      mockUseStartProfilingMutation.mockReturnValue({
        ...defaultStartMutationReturn,
        isPending: true,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      const startButton = screen.getByRole('button', { name: /start/i });
      expect(startButton).toBeDisabled();
    });

    it('disables Stop button while stopping', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: true,
        elapsedSeconds: 32,
      });

      mockUseStopProfilingMutation.mockReturnValue({
        ...defaultStopMutationReturn,
        isPending: true,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      const stopButton = screen.getByRole('button', { name: /stop/i });
      expect(stopButton).toBeDisabled();
    });

    it('disables Download button while downloading', () => {
      const mockResults = {
        total_time: 45.0,
        top_functions: [
          {
            function_name: 'test_func',
            call_count: 100,
            total_time: 10.0,
            cumulative_time: 10.0,
            percentage: 50.0,
          },
        ],
      };

      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: false,
        results: mockResults,
      });

      mockUseDownloadProfileMutation.mockReturnValue({
        ...defaultDownloadMutationReturn,
        isPending: true,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      const downloadButton = screen.getByRole('button', { name: /download/i });
      expect(downloadButton).toBeDisabled();
    });
  });

  describe('error handling', () => {
    it('displays error message when query fails', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        error: new Error('Failed to fetch profile status'),
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/failed to fetch profile status/i)).toBeInTheDocument();
    });

    it('displays error message when start fails', () => {
      mockUseStartProfilingMutation.mockReturnValue({
        ...defaultStartMutationReturn,
        error: new Error('Failed to start profiling'),
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/failed to start profiling/i)).toBeInTheDocument();
    });

    it('displays error message when stop fails', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: true,
        elapsedSeconds: 32,
      });

      mockUseStopProfilingMutation.mockReturnValue({
        ...defaultStopMutationReturn,
        error: new Error('Failed to stop profiling'),
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/failed to stop profiling/i)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible panel with data-testid', () => {
      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('profiling-panel')).toBeInTheDocument();
    });

    it('has accessible status indicator', () => {
      mockUseProfileQuery.mockReturnValue({
        ...defaultQueryReturn,
        isProfiling: true,
        elapsedSeconds: 32,
      });

      render(<ProfilingPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('profiling-status')).toBeInTheDocument();
    });
  });
});
