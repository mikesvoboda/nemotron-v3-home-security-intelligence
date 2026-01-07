/**
 * Tests for useCachedEvents hook
 * TDD: Tests for offline event caching using IndexedDB
 *
 * Uses fake-indexeddb for testing IndexedDB operations
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi } from 'vitest';
import 'fake-indexeddb/auto';

// Direct import to avoid barrel file memory issues
import { useCachedEvents, type CachedEvent } from './useCachedEvents';

describe('useCachedEvents', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    // Clear all IndexedDB databases before each test
    const deleteRequest = indexedDB.deleteDatabase('nemotron-security');
    await new Promise<void>((resolve) => {
      deleteRequest.onsuccess = () => resolve();
      deleteRequest.onerror = () => resolve();
      deleteRequest.onblocked = () => resolve();
    });
  });

  it('initializes with empty events array', async () => {
    const { result } = renderHook(() => useCachedEvents());

    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    expect(result.current.cachedEvents).toEqual([]);
    expect(result.current.cachedCount).toBe(0);
  });

  it('caches a new event', async () => {
    const { result } = renderHook(() => useCachedEvents());

    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    const event: CachedEvent = {
      id: 'event-1',
      camera_id: 'front_door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected at front door',
      timestamp: new Date().toISOString(),
      cachedAt: new Date().toISOString(),
    };

    await act(async () => {
      await result.current.cacheEvent(event);
    });

    expect(result.current.cachedEvents).toContainEqual(expect.objectContaining({ id: 'event-1' }));
    expect(result.current.cachedCount).toBe(1);
  });

  it('retrieves cached events after caching', async () => {
    const { result } = renderHook(() => useCachedEvents());

    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    // Cache an event first
    const event: CachedEvent = {
      id: 'existing-1',
      camera_id: 'backyard',
      risk_score: 50,
      risk_level: 'medium',
      summary: 'Motion detected',
      timestamp: new Date().toISOString(),
      cachedAt: new Date().toISOString(),
    };

    await act(async () => {
      await result.current.cacheEvent(event);
    });

    // Load cached events
    await act(async () => {
      await result.current.loadCachedEvents();
    });

    expect(result.current.cachedEvents).toHaveLength(1);
    expect(result.current.cachedEvents[0].id).toBe('existing-1');
  });

  it('removes a cached event by id', async () => {
    const { result } = renderHook(() => useCachedEvents());

    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    // Cache an event first
    const event: CachedEvent = {
      id: 'to-remove',
      camera_id: 'garage',
      risk_score: 30,
      risk_level: 'low',
      summary: 'Car detected',
      timestamp: new Date().toISOString(),
      cachedAt: new Date().toISOString(),
    };

    await act(async () => {
      await result.current.cacheEvent(event);
    });

    expect(result.current.cachedEvents).toHaveLength(1);

    // Remove the event
    await act(async () => {
      await result.current.removeCachedEvent('to-remove');
    });

    expect(result.current.cachedEvents).toHaveLength(0);
    expect(result.current.cachedCount).toBe(0);
  });

  it('clears all cached events', async () => {
    const { result } = renderHook(() => useCachedEvents());

    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    // Cache multiple events
    const event1: CachedEvent = {
      id: 'event-1',
      camera_id: 'front_door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected',
      timestamp: new Date().toISOString(),
      cachedAt: new Date().toISOString(),
    };

    const event2: CachedEvent = {
      id: 'event-2',
      camera_id: 'backyard',
      risk_score: 50,
      risk_level: 'medium',
      summary: 'Motion detected',
      timestamp: new Date().toISOString(),
      cachedAt: new Date().toISOString(),
    };

    await act(async () => {
      await result.current.cacheEvent(event1);
      await result.current.cacheEvent(event2);
    });

    expect(result.current.cachedCount).toBe(2);

    // Clear all events
    await act(async () => {
      await result.current.clearCache();
    });

    expect(result.current.cachedEvents).toHaveLength(0);
    expect(result.current.cachedCount).toBe(0);
  });

  it('tracks cache initialization status', async () => {
    const { result } = renderHook(() => useCachedEvents());

    // Wait for initialization
    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    expect(result.current.error).toBeNull();
  });

  it('provides cache size information', async () => {
    const { result } = renderHook(() => useCachedEvents());

    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    // Cache multiple events
    const events: CachedEvent[] = [
      {
        id: 'event-1',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected',
        timestamp: new Date().toISOString(),
        cachedAt: new Date().toISOString(),
      },
      {
        id: 'event-2',
        camera_id: 'backyard',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Motion detected',
        timestamp: new Date().toISOString(),
        cachedAt: new Date().toISOString(),
      },
    ];

    await act(async () => {
      for (const event of events) {
        await result.current.cacheEvent(event);
      }
    });

    expect(result.current.cachedCount).toBe(2);
  });

  it('sorts cached events by timestamp (newest first)', async () => {
    const { result } = renderHook(() => useCachedEvents());

    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    const oldEvent: CachedEvent = {
      id: 'old-event',
      camera_id: 'front_door',
      risk_score: 30,
      risk_level: 'low',
      summary: 'Old event',
      timestamp: '2024-01-01T10:00:00Z',
      cachedAt: '2024-01-01T10:00:00Z',
    };

    const newEvent: CachedEvent = {
      id: 'new-event',
      camera_id: 'backyard',
      risk_score: 80,
      risk_level: 'critical',
      summary: 'New event',
      timestamp: '2024-01-02T10:00:00Z',
      cachedAt: '2024-01-02T10:00:00Z',
    };

    // Cache old event first, then new event
    await act(async () => {
      await result.current.cacheEvent(oldEvent);
      await result.current.cacheEvent(newEvent);
    });

    // Should be sorted with newest first
    expect(result.current.cachedEvents[0].id).toBe('new-event');
    expect(result.current.cachedEvents[1].id).toBe('old-event');
  });

  it('updates existing event when caching with same id', async () => {
    const { result } = renderHook(() => useCachedEvents());

    await waitFor(() => {
      expect(result.current.isInitialized).toBe(true);
    });

    const originalEvent: CachedEvent = {
      id: 'event-1',
      camera_id: 'front_door',
      risk_score: 30,
      risk_level: 'low',
      summary: 'Original summary',
      timestamp: new Date().toISOString(),
      cachedAt: new Date().toISOString(),
    };

    await act(async () => {
      await result.current.cacheEvent(originalEvent);
    });

    expect(result.current.cachedCount).toBe(1);

    // Update with same ID
    const updatedEvent: CachedEvent = {
      ...originalEvent,
      risk_score: 90,
      risk_level: 'critical',
      summary: 'Updated summary',
    };

    await act(async () => {
      await result.current.cacheEvent(updatedEvent);
    });

    // Should still have only 1 event
    expect(result.current.cachedCount).toBe(1);
    expect(result.current.cachedEvents[0].summary).toBe('Updated summary');
    expect(result.current.cachedEvents[0].risk_score).toBe(90);
  });
});
