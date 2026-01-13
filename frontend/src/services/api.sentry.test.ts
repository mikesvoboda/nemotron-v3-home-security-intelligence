/**
 * Tests for API Sentry breadcrumb integration.
 *
 * These tests verify that the API client properly adds Sentry breadcrumbs
 * for HTTP requests and errors.
 */
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchCameras, fetchHealth, ApiError } from './api';
import * as sentryModule from './sentry';
import { server } from '../mocks/server';

// Mock the Sentry module
vi.mock('./sentry', () => ({
  addApiBreadcrumb: vi.fn(),
  isSentryEnabled: vi.fn(() => true),
}));

describe('API Sentry Breadcrumbs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Ensure Sentry is enabled for all tests (reset to default mock behavior)
    vi.mocked(sentryModule.isSentryEnabled).mockReturnValue(true);
  });

  afterEach(() => {
    server.resetHandlers();
    // Explicitly restore Sentry mock to prevent leakage
    vi.mocked(sentryModule.isSentryEnabled).mockRestore();
    // Clear any pending timers from retry logic
    vi.clearAllTimers();
    // Ensure real timers are restored
    vi.useRealTimers();
  });

  describe('successful requests', () => {
    it('adds a breadcrumb for successful GET requests', async () => {
      // Mock successful response
      server.use(
        http.get('*/api/cameras', () => {
          return HttpResponse.json({
            cameras: [
              {
                id: 'cam-1',
                name: 'Front Door',
                folder_path: '/export/foscam/front-door',
                status: 'online',
                created_at: '2025-01-01T00:00:00Z',
              },
            ],
            count: 1,
            limit: 50,
            offset: 0,
          });
        })
      );

      await fetchCameras();

      expect(sentryModule.addApiBreadcrumb).toHaveBeenCalledWith(
        'GET',
        expect.stringContaining('/api/cameras'),
        200,
        expect.any(Number)
      );
    });

    it('includes request duration in breadcrumb', async () => {
      server.use(
        http.get('*/api/system/health', () => {
          return HttpResponse.json({
            status: 'healthy',
            database: 'connected',
            redis: 'connected',
            workers: { running: true, count: 2 },
          });
        })
      );

      await fetchHealth();

      expect(sentryModule.addApiBreadcrumb).toHaveBeenCalledWith(
        'GET',
        expect.stringContaining('/api/system/health'),
        200,
        expect.any(Number)
      );

      // Verify duration is a positive number
      const [, , , duration] = vi.mocked(sentryModule.addApiBreadcrumb).mock.calls[0];
      expect(duration).toBeGreaterThanOrEqual(0);
    });
  });

  describe('failed requests', () => {
    it('adds a breadcrumb for failed requests with 4xx status', async () => {
      server.use(
        http.get('*/api/cameras', () => {
          return HttpResponse.json(
            { detail: 'Not found' },
            { status: 404 }
          );
        })
      );

      await expect(fetchCameras()).rejects.toThrow(ApiError);

      expect(sentryModule.addApiBreadcrumb).toHaveBeenCalledWith(
        'GET',
        expect.stringContaining('/api/cameras'),
        404,
        expect.any(Number)
      );
    });

    it('adds a breadcrumb for failed requests with 5xx status', async () => {
      server.use(
        http.get('*/api/system/health', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      // Use fake timers to skip retry delays
      vi.useFakeTimers();

      try {
        // Start the request and immediately advance timers
        const promise = expect(fetchHealth()).rejects.toThrow(ApiError);

        // Fast-forward through all retry delays
        await vi.runAllTimersAsync();

        // Wait for the final rejection
        await promise;

        // The request may be retried, so check the last call
        const calls = vi.mocked(sentryModule.addApiBreadcrumb).mock.calls;
        const lastCall = calls[calls.length - 1];
        expect(lastCall[0]).toBe('GET');
        expect(lastCall[1]).toContain('/api/system/health');
        expect(lastCall[2]).toBe(500);
      } finally {
        // Restore real timers
        vi.useRealTimers();
      }
    });
  });

  describe('when Sentry is disabled', () => {
    it('does not add breadcrumbs when Sentry is disabled', async () => {
      vi.mocked(sentryModule.isSentryEnabled).mockReturnValue(false);

      server.use(
        http.get('*/api/cameras', () => {
          return HttpResponse.json({
            cameras: [],
            count: 0,
            limit: 50,
            offset: 0,
          });
        })
      );

      await fetchCameras();

      expect(sentryModule.addApiBreadcrumb).not.toHaveBeenCalled();
    });
  });
});
