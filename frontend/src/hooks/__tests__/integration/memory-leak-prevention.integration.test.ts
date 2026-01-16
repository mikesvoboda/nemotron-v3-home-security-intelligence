/**
 * Memory Leak Prevention Integration Tests
 *
 * Tests for verifying proper cleanup of event listeners, subscriptions,
 * and resources to prevent memory leaks.
 *
 * Coverage targets:
 * - Event listener cleanup on unmount
 * - WebSocket subscription cleanup
 * - Timer/interval cleanup
 * - Ref cleanup patterns
 * - Subscription deduplication
 */

/* eslint-disable @typescript-eslint/unbound-method */
// Disabled for test file - common pattern when asserting on mock method calls

import { renderHook, waitFor, act } from '@testing-library/react';
import * as React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach, Mock } from 'vitest';

import * as api from '../.././../services/api';
import { useEventStream } from '../../useEventStream';
import { useKeyboardShortcuts } from '../../useKeyboardShortcuts';
import { useLocalStorage } from '../../useLocalStorage';
import { useNetworkStatus } from '../../useNetworkStatus';
import { usePolling } from '../../usePolling';
import { useSavedSearches } from '../../useSavedSearches';
import {
  webSocketManager,
  resetSubscriberCounter,
  generateSubscriberId,
  type Subscriber,
} from '../../webSocketManager';

// Helper wrapper that provides Router context for hooks that need navigation
const RouterWrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(MemoryRouter, null, children);

// Mock API
vi.mock('../../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return {
    ...actual,
    buildWebSocketOptions: vi.fn(() => ({
      url: 'ws://localhost:8000/ws/events',
      protocols: [],
    })),
  };
});

// Mock the webSocketManager
vi.mock('../../webSocketManager', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../webSocketManager')>();
  return {
    ...actual,
    webSocketManager: {
      subscribe: vi.fn(),
      send: vi.fn(),
      getConnectionState: vi.fn(),
      getSubscriberCount: vi.fn(),
      hasConnection: vi.fn(),
      reconnect: vi.fn(),
      clearAll: vi.fn(),
      reset: vi.fn(),
    },
  };
});

describe('Memory Leak Prevention', () => {
  let mockUnsubscribe: Mock;
  let lastSubscriber: Subscriber | null = null;
  let subscriberCount = 0;

  beforeEach(() => {
    vi.clearAllMocks();
    resetSubscriberCounter();
    mockUnsubscribe = vi.fn();
    lastSubscriber = null;
    subscriberCount = 0;

    (webSocketManager.subscribe as Mock).mockImplementation(
      (_url: string, subscriber: Subscriber) => {
        lastSubscriber = subscriber;
        subscriberCount++;
        setTimeout(() => {
          subscriber.onOpen?.();
        }, 0);
        return () => {
          subscriberCount--;
          mockUnsubscribe();
        };
      }
    );

    (webSocketManager.send as Mock).mockReturnValue(true);

    (webSocketManager.getConnectionState as Mock).mockReturnValue({
      isConnected: true,
      reconnectCount: 0,
      hasExhaustedRetries: false,
      lastHeartbeat: null,
    });

    (webSocketManager.getSubscriberCount as Mock).mockImplementation(() => subscriberCount);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('WebSocket Subscription Cleanup', () => {
    it('should clean up WebSocket subscription on unmount', async () => {
      const { unmount } = renderHook(() => useEventStream());

      // Wait for connection
      await waitFor(() => {
        expect(webSocketManager.subscribe).toHaveBeenCalled();
      });

      expect(subscriberCount).toBe(1);

      // Unmount
      unmount();

      // Unsubscribe should have been called
      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(subscriberCount).toBe(0);
    });

    it('should track subscriber count correctly with multiple instances', async () => {
      const { unmount: unmount1 } = renderHook(() => useEventStream());
      const { unmount: unmount2 } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(webSocketManager.subscribe).toHaveBeenCalledTimes(2);
      });

      expect(subscriberCount).toBe(2);

      // Unmount first subscriber
      unmount1();
      expect(subscriberCount).toBe(1);

      // Unmount second subscriber
      unmount2();
      expect(subscriberCount).toBe(0);
    });

    it('should not leak subscriptions on rapid mount/unmount', () => {
      // Rapidly mount and unmount
      for (let i = 0; i < 10; i++) {
        const { unmount } = renderHook(() => useEventStream());
        unmount();
      }

      // All unsubscribes should have been called
      expect(mockUnsubscribe).toHaveBeenCalledTimes(10);
      expect(subscriberCount).toBe(0);
    });

    it('should generate unique subscriber IDs', () => {
      resetSubscriberCounter();

      const id1 = generateSubscriberId();
      const id2 = generateSubscriberId();
      const id3 = generateSubscriberId();

      expect(id1).not.toBe(id2);
      expect(id2).not.toBe(id3);
      expect(id1).not.toBe(id3);

      // IDs should have predictable format
      expect(id1).toMatch(/^ws-sub-\d+-\d+$/);
    });
  });

  describe('Event Listener Cleanup', () => {
    it('should remove storage event listeners on unmount', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = renderHook(() => useSavedSearches());

      const storageAddCalls = addEventListenerSpy.mock.calls.filter(
        ([event]) => event === 'storage'
      );
      expect(storageAddCalls.length).toBeGreaterThan(0);

      unmount();

      const storageRemoveCalls = removeEventListenerSpy.mock.calls.filter(
        ([event]) => event === 'storage'
      );
      expect(storageRemoveCalls.length).toBe(storageAddCalls.length);

      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    });

    it('should remove network status listeners on unmount', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = renderHook(() => useNetworkStatus());

      unmount();

      // Should have added and removed online/offline listeners
      const onlineAddCalls = addEventListenerSpy.mock.calls.filter(([event]) => event === 'online');
      const offlineAddCalls = addEventListenerSpy.mock.calls.filter(
        ([event]) => event === 'offline'
      );
      const onlineRemoveCalls = removeEventListenerSpy.mock.calls.filter(
        ([event]) => event === 'online'
      );
      const offlineRemoveCalls = removeEventListenerSpy.mock.calls.filter(
        ([event]) => event === 'offline'
      );

      expect(onlineAddCalls.length).toBe(onlineRemoveCalls.length);
      expect(offlineAddCalls.length).toBe(offlineRemoveCalls.length);

      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    });

    it('should remove keyboard event listeners on unmount', () => {
      const addEventListenerSpy = vi.spyOn(document, 'addEventListener');
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');

      // useKeyboardShortcuts uses useNavigate, so we need Router context
      const { unmount } = renderHook(
        () =>
          useKeyboardShortcuts({
            onOpenHelp: vi.fn(),
            onOpenCommandPalette: vi.fn(),
          }),
        { wrapper: RouterWrapper }
      );

      const keydownAddCalls = addEventListenerSpy.mock.calls.filter(
        ([event]) => event === 'keydown'
      );
      expect(keydownAddCalls.length).toBeGreaterThan(0);

      unmount();

      const keydownRemoveCalls = removeEventListenerSpy.mock.calls.filter(
        ([event]) => event === 'keydown'
      );
      expect(keydownRemoveCalls.length).toBe(keydownAddCalls.length);

      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    });
  });

  describe('Timer and Interval Cleanup', () => {
    it('should clear polling interval on unmount', async () => {
      const fetcher = vi.fn().mockResolvedValue({ data: 'test' });

      const { unmount } = renderHook(() =>
        usePolling({
          fetcher,
          interval: 1000,
          enabled: true,
        })
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // Clear the mock to track future calls
      fetcher.mockClear();

      // Unmount
      unmount();

      // Wait and verify no more fetches happen
      await new Promise((r) => setTimeout(r, 1500));
      expect(fetcher).not.toHaveBeenCalled();
    });

    it('should not leak intervals on rapid enable/disable', async () => {
      const fetcher = vi.fn().mockResolvedValue({ data: 'test' });

      const { rerender, unmount } = renderHook(
        ({ enabled }) =>
          usePolling({
            fetcher,
            interval: 100,
            enabled,
          }),
        { initialProps: { enabled: true } }
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalled();
      });

      // Rapidly toggle enabled
      for (let i = 0; i < 10; i++) {
        rerender({ enabled: false });
        rerender({ enabled: true });
      }

      // Clean unmount
      fetcher.mockClear();
      unmount();

      // Verify no more fetches after unmount
      await new Promise((r) => setTimeout(r, 500));
      expect(fetcher).not.toHaveBeenCalled();
    });
  });

  describe('State Updates After Unmount', () => {
    it('should not update state after WebSocket hook unmounts', async () => {
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { unmount } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(webSocketManager.subscribe).toHaveBeenCalled();
      });

      // Unmount the hook
      unmount();

      // Try to send a message after unmount
      // This should not cause any errors or warnings about state updates
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-after-unmount',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 50,
            risk_level: 'medium',
            summary: 'After unmount',
            timestamp: new Date().toISOString(),
          },
        });
      });

      // Should not have React "Can't perform state update on unmounted component" warning
      const reactWarnings = consoleWarnSpy.mock.calls.filter(
        ([msg]) => typeof msg === 'string' && msg.includes('unmounted')
      );
      expect(reactWarnings).toHaveLength(0);

      consoleWarnSpy.mockRestore();
      consoleErrorSpy.mockRestore();
    });

    it('should handle component remount correctly', async () => {
      // First mount
      const { result: result1, unmount: unmount1 } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result1.current.isConnected).toBe(true);
      });

      // Send an event
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-1',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 50,
            risk_level: 'medium',
            summary: 'First mount',
            timestamp: new Date().toISOString(),
          },
        });
      });

      await waitFor(() => {
        expect(result1.current.events).toHaveLength(1);
      });

      // Unmount
      unmount1();

      // Remount
      const { result: result2 } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result2.current.isConnected).toBe(true);
      });

      // New mount should start fresh (no events from previous mount)
      expect(result2.current.events).toHaveLength(0);
    });
  });

  describe('Ref Cleanup Patterns', () => {
    it('should track mounted state to prevent updates after unmount', async () => {
      // The useEventStream hook uses isMountedRef internally
      // This test verifies the pattern works correctly

      const { result, unmount } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Send event while mounted
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-1',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 50,
            risk_level: 'medium',
            summary: 'While mounted',
            timestamp: new Date().toISOString(),
          },
        });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
      });

      // Unmount
      unmount();

      // The hook's isMountedRef should now be false
      // Any future messages should be ignored (verified by no state update errors)
    });

    it('should clear seen event IDs on clearEvents', async () => {
      const { result } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Send event
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-1',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 50,
            risk_level: 'medium',
            summary: 'Test',
            timestamp: new Date().toISOString(),
          },
        });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
      });

      // Clear events
      act(() => {
        result.current.clearEvents();
      });

      expect(result.current.events).toHaveLength(0);

      // Same event ID should now be accepted again (seenIdsRef was cleared)
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-1',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 60,
            risk_level: 'medium',
            summary: 'Resent',
            timestamp: new Date().toISOString(),
          },
        });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
      });
    });
  });

  describe('Subscription Deduplication', () => {
    it('should deduplicate event IDs to prevent memory growth', async () => {
      const { result } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Send the same event 100 times
      for (let i = 0; i < 100; i++) {
        act(() => {
          lastSubscriber?.onMessage?.({
            type: 'event',
            data: {
              id: 'duplicate-event',
              event_id: 1,
              camera_id: 'cam-1',
              camera_name: 'Front Door',
              risk_score: 50,
              risk_level: 'medium',
              summary: 'Duplicate',
              timestamp: new Date().toISOString(),
            },
          });
        });
      }

      // Should only have 1 event due to deduplication
      expect(result.current.events).toHaveLength(1);
    });

    it('should bound seenEventIds set when events are evicted from buffer', async () => {
      const { result } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Send 150 unique events (buffer limit is 100)
      for (let i = 1; i <= 150; i++) {
        act(() => {
          lastSubscriber?.onMessage?.({
            type: 'event',
            data: {
              id: `event-${i}`,
              event_id: i,
              camera_id: 'cam-1',
              camera_name: 'Front Door',
              risk_score: 50,
              risk_level: 'medium',
              summary: `Event ${i}`,
              timestamp: new Date().toISOString(),
            },
          });
        });
      }

      // Buffer should be limited to 100
      expect(result.current.events).toHaveLength(100);

      // The events 1-50 were evicted, so their IDs should have been removed from seenIds
      // If we send event-1 again, it should be accepted
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-1',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 75,
            risk_level: 'high',
            summary: 'Resent event 1',
            timestamp: new Date().toISOString(),
          },
        });
      });

      // Should be at the front of the buffer (most recent)
      expect(result.current.events[0].id).toBe('event-1');
      // Buffer should still be limited to 100
      expect(result.current.events).toHaveLength(100);
    });
  });

  describe('localStorage Cleanup', () => {
    it('should handle localStorage errors without throwing', () => {
      const originalLocalStorage = window.localStorage;

      // Mock localStorage to throw
      const mockStorage = {
        getItem: () => {
          throw new Error('Storage quota exceeded');
        },
        setItem: () => {
          throw new Error('Storage quota exceeded');
        },
        removeItem: vi.fn(),
        clear: vi.fn(),
        length: 0,
        key: () => null,
      };

      Object.defineProperty(window, 'localStorage', {
        value: mockStorage,
        configurable: true,
      });

      // Should not throw
      expect(() => {
        const { result, unmount } = renderHook(() => useLocalStorage('test-key', 'default'));

        // Should fallback to default value
        expect(result.current[0]).toBe('default');

        // Setting should also not throw
        act(() => {
          result.current[1]('new value');
        });

        unmount();
      }).not.toThrow();

      // Restore
      Object.defineProperty(window, 'localStorage', {
        value: originalLocalStorage,
        configurable: true,
      });
    });
  });
});
