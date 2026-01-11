import { QueryClient } from '@tanstack/react-query';
import { describe, it, expect } from 'vitest';

import {
  createQueryClient,
  queryClient,
  queryKeys,
  DEFAULT_STALE_TIME,
  REALTIME_STALE_TIME,
  STATIC_STALE_TIME,
} from './queryClient';

describe('queryClient configuration', () => {
  describe('constants', () => {
    it('exports DEFAULT_STALE_TIME as 30 seconds', () => {
      expect(DEFAULT_STALE_TIME).toBe(30 * 1000);
    });

    it('exports REALTIME_STALE_TIME as 5 seconds', () => {
      expect(REALTIME_STALE_TIME).toBe(5 * 1000);
    });

    it('exports STATIC_STALE_TIME as 5 minutes', () => {
      expect(STATIC_STALE_TIME).toBe(5 * 60 * 1000);
    });
  });

  describe('queryKeys', () => {
    it('defines cameras key factory', () => {
      expect(queryKeys.cameras.all).toEqual(['cameras']);
      expect(queryKeys.cameras.list()).toEqual(['cameras', 'list']);
      expect(queryKeys.cameras.detail('camera-1')).toEqual(['cameras', 'detail', 'camera-1']);
    });

    it('defines events key factory', () => {
      expect(queryKeys.events.all).toEqual(['events']);
      expect(queryKeys.events.list({ camera_id: 'cam-1' })).toEqual([
        'events',
        'list',
        { camera_id: 'cam-1' },
      ]);
      expect(queryKeys.events.detail(123)).toEqual(['events', 'detail', 123]);
      expect(queryKeys.events.stats()).toEqual(['events', 'stats']);
    });

    it('defines system key factory', () => {
      expect(queryKeys.system.health).toEqual(['system', 'health']);
      expect(queryKeys.system.gpu).toEqual(['system', 'gpu']);
      expect(queryKeys.system.config).toEqual(['system', 'config']);
      expect(queryKeys.system.stats).toEqual(['system', 'stats']);
      expect(queryKeys.system.storage).toEqual(['system', 'storage']);
    });

    it('defines ai key factory', () => {
      expect(queryKeys.ai.metrics).toEqual(['ai', 'metrics']);
      expect(queryKeys.ai.modelZoo).toEqual(['ai', 'modelZoo']);
      expect(queryKeys.ai.audit.stats()).toEqual(['ai', 'audit', 'stats']);
      expect(queryKeys.ai.audit.leaderboard()).toEqual(['ai', 'audit', 'leaderboard']);
    });

    it('defines detections key factory', () => {
      expect(queryKeys.detections.forEvent(123)).toEqual(['detections', 'event', 123]);
      expect(queryKeys.detections.enrichment(456)).toEqual(['detections', 'enrichment', 456]);
      expect(queryKeys.detections.stats).toEqual(['detections', 'stats']);
    });
  });

  describe('createQueryClient', () => {
    it('creates a new QueryClient instance', () => {
      const client = createQueryClient();
      expect(client).toBeInstanceOf(QueryClient);
    });

    it('configures default staleTime', () => {
      const client = createQueryClient();
      const options = client.getDefaultOptions();
      expect(options.queries?.staleTime).toBe(DEFAULT_STALE_TIME);
    });

    it('disables window focus refetch for offline-first behavior', () => {
      const client = createQueryClient();
      const options = client.getDefaultOptions();
      expect(options.queries?.refetchOnWindowFocus).toBe(false);
    });

    it('configures smart retry based on error type (function)', () => {
      const client = createQueryClient();
      const options = client.getDefaultOptions();
      // Retry is now a function (shouldRetryQuery) for smart error-based retry
      expect(typeof options.queries?.retry).toBe('function');
    });

    it('configures gcTime (garbage collection time)', () => {
      const client = createQueryClient();
      const options = client.getDefaultOptions();
      // Default gcTime should be 5 minutes (300000ms)
      expect(options.queries?.gcTime).toBe(5 * 60 * 1000);
    });

    it('enables refetch on reconnect', () => {
      const client = createQueryClient();
      const options = client.getDefaultOptions();
      expect(options.queries?.refetchOnReconnect).toBe(true);
    });
  });

  describe('queryClient singleton', () => {
    it('exports a singleton QueryClient instance', () => {
      expect(queryClient).toBeInstanceOf(QueryClient);
    });

    it('singleton has correct default options', () => {
      const options = queryClient.getDefaultOptions();
      expect(options.queries?.staleTime).toBe(DEFAULT_STALE_TIME);
      // Retry is now a function for smart error-based retry
      expect(typeof options.queries?.retry).toBe('function');
    });
  });

  describe('mutation defaults', () => {
    it('configures conservative mutation retry (timeout-only via function)', () => {
      const client = createQueryClient();
      const options = client.getDefaultOptions();
      // Mutation retry is now a function (shouldRetryMutation) that only retries timeouts
      // to prevent duplicate side effects for other transient errors
      expect(typeof options.mutations?.retry).toBe('function');
    });
  });
});

describe('query key structure', () => {
  it('uses consistent hierarchical structure', () => {
    // All keys should follow [entity, action?, params?] pattern
    const camerasList = queryKeys.cameras.list();
    expect(camerasList[0]).toBe('cameras');
    expect(camerasList[1]).toBe('list');

    const eventDetail = queryKeys.events.detail(1);
    expect(eventDetail[0]).toBe('events');
    expect(eventDetail[1]).toBe('detail');
    expect(eventDetail[2]).toBe(1);
  });

  it('allows cache invalidation by prefix', () => {
    // Using queryKeys.cameras.all should invalidate all camera queries
    const allCamerasKey = queryKeys.cameras.all;
    const listKey = queryKeys.cameras.list();
    const detailKey = queryKeys.cameras.detail('cam-1');

    // All camera keys should start with ['cameras']
    expect(listKey.slice(0, 1)).toEqual(allCamerasKey);
    expect(detailKey.slice(0, 1)).toEqual(allCamerasKey);
  });
});
