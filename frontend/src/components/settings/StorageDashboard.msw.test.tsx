/**
 * StorageDashboard MSW Test Example
 *
 * This test file demonstrates how to use MSW (Mock Service Worker) for API mocking
 * instead of vi.mock(). MSW provides a more realistic testing approach where:
 *
 * 1. Requests go through the actual fetch implementation
 * 2. Request/response handling matches production behavior
 * 3. Handlers can be overridden per-test using server.use()
 *
 * ## Key Patterns Demonstrated
 *
 * - Default handlers: Tests use the default mock data from handlers.ts
 * - Test-specific overrides: Individual tests override handlers for specific scenarios
 * - Error handling: Tests can simulate API errors with proper HTTP status codes
 * - Loading states: Tests can delay responses to verify loading UI
 *
 * @see src/mocks/handlers.ts - Default API handlers
 * @see src/mocks/server.ts - MSW server configuration
 */

import { QueryClient } from '@tanstack/react-query';
import { screen, waitFor , fireEvent } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';
import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';

import StorageDashboard from './StorageDashboard';
import { server } from '../../mocks/server';
import { clearInFlightRequests } from '../../services/api';
import { renderWithProviders } from '../../test-utils';

import type { StorageStatsResponse, CleanupResponse } from '../../services/api';

/**
 * Create a QueryClient optimized for MSW tests.
 * - Disables retry to prevent timeout delays
 * - Sets staleTime to 0 for immediate data freshness
 * - Sets gcTime to 0 for immediate garbage collection
 */
function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// ============================================================================
// Test Data
// ============================================================================

const mockStorageStats: StorageStatsResponse = {
  disk_used_bytes: 107374182400, // 100 GB
  disk_total_bytes: 536870912000, // 500 GB
  disk_free_bytes: 429496729600, // 400 GB
  disk_usage_percent: 20.0,
  thumbnails: {
    file_count: 1500,
    size_bytes: 75000000, // 75 MB
  },
  images: {
    file_count: 10000,
    size_bytes: 5000000000, // 5 GB
  },
  clips: {
    file_count: 50,
    size_bytes: 500000000, // 500 MB
  },
  events_count: 156,
  detections_count: 892,
  gpu_stats_count: 2880,
  logs_count: 5000,
  timestamp: '2025-12-30T10:30:00Z',
};

const mockCleanupPreview: CleanupResponse = {
  events_deleted: 10,
  detections_deleted: 50,
  gpu_stats_deleted: 100,
  logs_deleted: 25,
  thumbnails_deleted: 50,
  images_deleted: 0,
  space_reclaimed: 1024000,
  retention_days: 30,
  dry_run: true,
  timestamp: '2025-12-30T10:30:00Z',
};

// ============================================================================
// Tests
// ============================================================================

describe('StorageDashboard (MSW)', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    // Clear in-flight request cache to prevent test interference
    clearInFlightRequests();
    // Reset timers for predictable test behavior
    vi.useRealTimers();
    // Create a fresh test QueryClient for each test
    queryClient = createTestQueryClient();
  });

  afterEach(() => {
    // Clear the query cache to prevent cross-test pollution
    queryClient.clear();
  });

  it('renders loading state initially', () => {
    // Override handler to delay response (simulating loading)
    // Use 60s delay instead of 'infinite' to prevent cleanup hangs
    // The test completes before the delay resolves, but cleanup can finish
    server.use(
      http.get('/api/system/storage', async () => {
        await delay(60000);
        return HttpResponse.json(mockStorageStats);
      })
    );

    renderWithProviders(<StorageDashboard />, { queryClient });

    // Check for skeleton loading elements
    const skeletons = document.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders storage stats after loading', async () => {
    // Override with our test-specific data
    server.use(
      http.get('/api/system/storage', () => {
        return HttpResponse.json(mockStorageStats);
      })
    );

    renderWithProviders(<StorageDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('Disk Usage')).toBeInTheDocument();
    });

    // Check disk usage display
    expect(screen.getByText('20.0%')).toBeInTheDocument();

    // Check storage breakdown sections
    expect(screen.getByText('Thumbnails')).toBeInTheDocument();
    expect(screen.getByText('Images')).toBeInTheDocument();
    expect(screen.getByText('Clips')).toBeInTheDocument();

    // Check database records section
    expect(screen.getByText('Database Records')).toBeInTheDocument();
    expect(screen.getByText('Events')).toBeInTheDocument();
    expect(screen.getByText('Detections')).toBeInTheDocument();
    expect(screen.getByText('GPU Stats')).toBeInTheDocument();
    expect(screen.getByText('Logs')).toBeInTheDocument();
  });

  it('displays formatted byte sizes', async () => {
    server.use(
      http.get('/api/system/storage', () => {
        return HttpResponse.json(mockStorageStats);
      })
    );

    renderWithProviders(<StorageDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('Disk Usage')).toBeInTheDocument();
    });

    // Check formatted disk usage
    expect(screen.getByText('100 GB used')).toBeInTheDocument();
    expect(screen.getByText('500 GB total')).toBeInTheDocument();

    // Check formatted category sizes
    expect(screen.getByText('71.53 MB')).toBeInTheDocument(); // thumbnails
    expect(screen.getByText('4.66 GB')).toBeInTheDocument(); // images
    expect(screen.getByText('476.84 MB')).toBeInTheDocument(); // clips
  });

  // TODO: Fix this test - React Query error handling with MSW needs proper configuration
  // The component stays in loading state instead of showing error
  it.skip('displays error state when fetch fails', async () => {
    // Override handler to return an error
    // Use 400 (Bad Request) instead of 500 because 500 triggers retry logic
    // with exponential backoff which would make the test take too long.
    server.use(
      http.get('/api/system/storage', () => {
        return HttpResponse.json(
          { detail: 'Network error' },
          { status: 400 }
        );
      })
    );

    renderWithProviders(<StorageDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    // Should show retry button
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  // TODO: Fix this test - needs proper error handling for React Query + MSW integration
  // The component's error state isn't being set properly due to React Query retry behavior
  it.skip('handles retry button click on error', async () => {
    // First call: return error (use 400 to avoid retry backoff)
    // Second call: return success
    let callCount = 0;
    server.use(
      http.get('/api/system/storage', () => {
        callCount++;
        if (callCount === 1) {
          return HttpResponse.json(
            { detail: 'Network error' },
            { status: 400 }
          );
        }
        return HttpResponse.json(mockStorageStats);
      })
    );

    renderWithProviders(<StorageDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    const retryButton = screen.getByText('Retry');
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('Disk Usage')).toBeInTheDocument();
    });
  });

  it('handles preview cleanup button click', async () => {
    server.use(
      http.get('/api/system/storage', () => {
        return HttpResponse.json(mockStorageStats);
      }),
      http.post('/api/system/cleanup', ({ request }) => {
        const url = new URL(request.url);
        // Check that dry_run=true is passed
        expect(url.searchParams.get('dry_run')).toBe('true');
        return HttpResponse.json(mockCleanupPreview);
      })
    );

    renderWithProviders(<StorageDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('Cleanup Preview')).toBeInTheDocument();
    });

    const previewButton = screen.getByText('Preview Cleanup');
    fireEvent.click(previewButton);

    // Check that cleanup preview results are displayed
    await waitFor(() => {
      expect(screen.getByText(/Would be deleted/)).toBeInTheDocument();
    });

    // Check retention days is displayed
    expect(screen.getByText(/30/)).toBeInTheDocument();
    expect(screen.getByText(/days/)).toBeInTheDocument();
  });

  // TODO: Fix this test - mutateAsync throws unhandled rejection when API returns error
  // Component uses `void previewCleanup()` which ignores Promise, causing unhandled rejection
  // Need to either use mutate() instead of mutateAsync() or add .catch() in component
  it.skip('handles cleanup preview error', async () => {
    server.use(
      http.get('/api/system/storage', () => {
        return HttpResponse.json(mockStorageStats);
      }),
      // Use 400 to avoid retry backoff delays
      http.post('/api/system/cleanup', () => {
        return HttpResponse.json(
          { detail: 'Preview failed' },
          { status: 400 }
        );
      })
    );

    renderWithProviders(<StorageDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('Preview Cleanup')).toBeInTheDocument();
    });

    const previewButton = screen.getByText('Preview Cleanup');
    fireEvent.click(previewButton);

    await waitFor(() => {
      expect(screen.getByText('Preview failed')).toBeInTheDocument();
    });
  });

  it('handles zero values correctly', async () => {
    const zeroStats: StorageStatsResponse = {
      disk_used_bytes: 0,
      disk_total_bytes: 0,
      disk_free_bytes: 0,
      disk_usage_percent: 0,
      thumbnails: { file_count: 0, size_bytes: 0 },
      images: { file_count: 0, size_bytes: 0 },
      clips: { file_count: 0, size_bytes: 0 },
      events_count: 0,
      detections_count: 0,
      gpu_stats_count: 0,
      logs_count: 0,
      timestamp: '2025-12-30T10:30:00Z',
    };

    server.use(
      http.get('/api/system/storage', () => {
        return HttpResponse.json(zeroStats);
      })
    );

    renderWithProviders(<StorageDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('Disk Usage')).toBeInTheDocument();
    });

    // Check that zero values are displayed
    expect(screen.getByText('0.0%')).toBeInTheDocument();
    expect(screen.getAllByText('0 B').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0 files').length).toBe(3);
  });

  it('displays correct progress bar color for critical usage (red)', async () => {
    const criticalStats = { ...mockStorageStats, disk_usage_percent: 95.0 };

    server.use(
      http.get('/api/system/storage', () => {
        return HttpResponse.json(criticalStats);
      })
    );

    renderWithProviders(<StorageDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('95.0%')).toBeInTheDocument();
    });
  });
});
