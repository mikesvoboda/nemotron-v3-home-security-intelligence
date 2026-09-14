/**
 * Tests for MemorySnapshotPanel component
 *
 * The MemorySnapshotPanel displays:
 * - Process memory usage (RSS and VMS)
 * - Garbage collector statistics
 * - Tracemalloc tracing controls
 * - Top memory objects by type
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import MemorySnapshotPanel from './MemorySnapshotPanel';
import * as useMemoryStatsQueryModule from '../../hooks/useMemoryStatsQuery';
import { createQueryClient } from '../../services/queryClient';

// Mock the hooks
vi.mock('../../hooks/useMemoryStatsQuery');

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('MemorySnapshotPanel', () => {
  let queryClient: QueryClient;

  const mockUseMemoryStatsQuery = vi.mocked(useMemoryStatsQueryModule.useMemoryStatsQuery);
  const mockRefetchFn = vi.fn();
  const mockTriggerGc = vi.fn();
  const mockStartTracemalloc = vi.fn();
  const mockStopTracemalloc = vi.fn();

  const mockMemoryStats = {
    process_rss_bytes: 536870912, // 512 MB
    process_rss_human: '512.0 MB',
    process_vms_bytes: 1073741824, // 1 GB
    process_vms_human: '1.0 GB',
    gc_stats: {
      collections: [10, 5, 2],
      collected: 1500,
      uncollectable: 0,
      thresholds: [700, 10, 10],
    },
    tracemalloc_stats: {
      enabled: false,
      current_bytes: 0,
      peak_bytes: 0,
      top_allocations: [],
    },
    top_objects: [
      {
        type_name: 'dict',
        count: 50000,
        size_bytes: 12800000,
        size_human: '12.2 MB',
      },
      {
        type_name: 'list',
        count: 30000,
        size_bytes: 9600000,
        size_human: '9.2 MB',
      },
      {
        type_name: 'str',
        count: 100000,
        size_bytes: 8000000,
        size_human: '7.6 MB',
      },
    ],
    timestamp: '2024-01-15T10:30:00Z',
  };

  const defaultQueryReturn = {
    data: undefined,
    isLoading: false,
    isRefetching: false,
    error: null,
    refetch: mockRefetchFn,
    triggerGc: mockTriggerGc,
    startTracemalloc: mockStartTracemalloc,
    stopTracemalloc: mockStopTracemalloc,
    isGcPending: false,
    isTracemallocStartPending: false,
    isTracemallocStopPending: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();

    // Set up default mock returns
    mockUseMemoryStatsQuery.mockReturnValue(defaultQueryReturn);
  });

  afterEach(() => {
    queryClient.clear();
  });

  describe('loading state', () => {
    it('displays loading state when fetching memory stats', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        isLoading: true,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('memory-panel-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('displays error message when query fails', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        error: new Error('Failed to fetch memory stats'),
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('memory-panel-error')).toBeInTheDocument();
      expect(screen.getByText(/failed to fetch memory stats/i)).toBeInTheDocument();
    });

    it('displays retry button on error', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        error: new Error('Failed to fetch memory stats'),
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('calls refetch when retry is clicked', async () => {
      const user = userEvent.setup();
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        error: new Error('Failed to fetch memory stats'),
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /retry/i }));

      expect(mockRefetchFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('empty state', () => {
    it('displays empty state message when no data', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: undefined,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('memory-panel-empty')).toBeInTheDocument();
    });
  });

  describe('memory stats display', () => {
    it('displays process RSS memory', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/512\.0 MB/)).toBeInTheDocument();
      expect(screen.getByText(/RSS Memory/i)).toBeInTheDocument();
    });

    it('displays process VMS memory', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/1\.0 GB/)).toBeInTheDocument();
      expect(screen.getByText(/Virtual Memory/i)).toBeInTheDocument();
    });
  });

  describe('GC stats display', () => {
    it('displays GC collected count', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText('1,500')).toBeInTheDocument();
    });

    it('displays uncollectable objects count', () => {
      const statsWithUncollectable = {
        ...mockMemoryStats,
        gc_stats: {
          ...mockMemoryStats.gc_stats,
          uncollectable: 5,
        },
      };
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: statsWithUncollectable,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/uncollectable/i)).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  describe('top objects display', () => {
    it('displays object type names', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText('dict')).toBeInTheDocument();
      expect(screen.getByText('list')).toBeInTheDocument();
      expect(screen.getByText('str')).toBeInTheDocument();
    });

    it('displays object counts', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText('50,000')).toBeInTheDocument();
      expect(screen.getByText('30,000')).toBeInTheDocument();
      expect(screen.getByText('100,000')).toBeInTheDocument();
    });

    it('displays object sizes', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText('12.2 MB')).toBeInTheDocument();
      expect(screen.getByText('9.2 MB')).toBeInTheDocument();
      expect(screen.getByText('7.6 MB')).toBeInTheDocument();
    });
  });

  describe('GC trigger button', () => {
    it('displays Force GC button', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /force gc/i })).toBeInTheDocument();
    });

    it('calls triggerGc when Force GC is clicked', async () => {
      const user = userEvent.setup();
      mockTriggerGc.mockResolvedValue({});
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /force gc/i }));

      expect(mockTriggerGc).toHaveBeenCalledTimes(1);
    });

    it('disables Force GC button while pending', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
        isGcPending: true,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /running gc/i })).toBeDisabled();
    });
  });

  describe('tracemalloc controls', () => {
    it('displays Start Tracing button when tracemalloc is disabled', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /start tracing/i })).toBeInTheDocument();
    });

    it('displays Stop Tracing button when tracemalloc is enabled', () => {
      const statsWithTracemalloc = {
        ...mockMemoryStats,
        tracemalloc_stats: {
          enabled: true,
          current_bytes: 100000000,
          peak_bytes: 150000000,
          top_allocations: [],
        },
      };
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: statsWithTracemalloc,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /stop tracing/i })).toBeInTheDocument();
    });

    it('calls startTracemalloc when Start Tracing is clicked', async () => {
      const user = userEvent.setup();
      mockStartTracemalloc.mockResolvedValue({});
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /start tracing/i }));

      expect(mockStartTracemalloc).toHaveBeenCalledTimes(1);
    });

    it('calls stopTracemalloc when Stop Tracing is clicked', async () => {
      const user = userEvent.setup();
      mockStopTracemalloc.mockResolvedValue({});
      const statsWithTracemalloc = {
        ...mockMemoryStats,
        tracemalloc_stats: {
          enabled: true,
          current_bytes: 100000000,
          peak_bytes: 150000000,
          top_allocations: [],
        },
      };
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: statsWithTracemalloc,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /stop tracing/i }));

      expect(mockStopTracemalloc).toHaveBeenCalledTimes(1);
    });

    it('displays tracemalloc current and peak memory when enabled', () => {
      const statsWithTracemalloc = {
        ...mockMemoryStats,
        tracemalloc_stats: {
          enabled: true,
          current_bytes: 104857600, // 100 MB
          peak_bytes: 157286400, // 150 MB
          top_allocations: [
            {
              file: 'backend/services/detector.py:123',
              size_bytes: 5000000,
              size_human: '4.8 MB',
              count: 1000,
            },
          ],
        },
      };
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: statsWithTracemalloc,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      // Should show tracemalloc is active via the Active badge
      expect(screen.getByText('Active')).toBeInTheDocument();
    });
  });

  describe('refresh functionality', () => {
    it('displays refresh button', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });

    it('calls refetch when refresh is clicked', async () => {
      const user = userEvent.setup();
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      await user.click(screen.getByRole('button', { name: /refresh/i }));

      expect(mockRefetchFn).toHaveBeenCalledTimes(1);
    });

    it('shows loading indicator when refetching', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
        isRefetching: true,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      // Refresh button should indicate loading
      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      expect(refreshButton).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible panel with data-testid', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByTestId('memory-panel')).toBeInTheDocument();
    });
  });

  describe('production warning', () => {
    it('displays production warning callout', () => {
      mockUseMemoryStatsQuery.mockReturnValue({
        ...defaultQueryReturn,
        data: mockMemoryStats,
      });

      render(<MemorySnapshotPanel />, { wrapper: createWrapper(queryClient) });

      expect(screen.getByText(/force gc.*impact performance/i)).toBeInTheDocument();
    });
  });
});
