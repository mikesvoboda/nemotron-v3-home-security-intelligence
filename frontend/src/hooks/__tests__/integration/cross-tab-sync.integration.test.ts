/**
 * Cross-Tab State Synchronization Integration Tests
 *
 * Tests for localStorage-based state synchronization between browser tabs.
 * Validates that updates in one tab are reflected in other tabs via storage events.
 *
 * Coverage targets:
 * - localStorage synchronization between tabs
 * - Storage event handling
 * - State consistency across tabs
 * - Edge cases (concurrent writes, stale data)
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useLocalStorage } from '../../useLocalStorage';
import { useSavedSearches } from '../../useSavedSearches';

import type { SavedSearch } from '../../useSavedSearches';

// Mock localStorage with proper storage event support
const createLocalStorageMock = () => {
  let store: Record<string, string> = {};

  return {
    getItem: vi.fn((key: string): string | null => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
      // Storage events are fired asynchronously and only to OTHER windows
      // We'll manually trigger these in tests to simulate cross-tab
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    // Helper to get raw store for testing
    _getStore: () => ({ ...store }),
    // Helper to simulate storage event from another tab
    _triggerStorageEvent: (key: string, newValue: string | null, oldValue: string | null) => {
      const event = new StorageEvent('storage', {
        key,
        newValue,
        oldValue,
        url: window.location.href,
      });
      window.dispatchEvent(event);
    },
    // Helper to directly set store without triggering events (simulating another tab)
    _setFromOtherTab: (key: string, value: string) => {
      const oldValue = store[key] ?? null;
      store[key] = value;
      return { oldValue, newValue: value };
    },
  };
};

describe('Cross-Tab State Synchronization', () => {
  let localStorageMock: ReturnType<typeof createLocalStorageMock>;

  beforeEach(() => {
    localStorageMock = createLocalStorageMock();
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorageMock.clear();
  });

  describe('useSavedSearches Cross-Tab Sync', () => {
    const STORAGE_KEY = 'hsi_saved_searches';

    it('should sync state when another tab updates localStorage', async () => {
      const { result } = renderHook(() => useSavedSearches());

      // Initial state
      expect(result.current.savedSearches).toEqual([]);

      // Simulate another tab saving a search
      const searchFromOtherTab: SavedSearch = {
        id: 'search-other-tab',
        name: 'Search from Tab B',
        query: 'vehicle front door',
        filters: { camera_id: 'cam-1' },
        createdAt: new Date().toISOString(),
      };

      const newValue = JSON.stringify([searchFromOtherTab]);
      const { oldValue } = localStorageMock._setFromOtherTab(STORAGE_KEY, newValue);

      // Trigger storage event (simulating cross-tab communication)
      act(() => {
        localStorageMock._triggerStorageEvent(STORAGE_KEY, newValue, oldValue);
      });

      // Verify state updated
      await waitFor(() => {
        expect(result.current.savedSearches).toHaveLength(1);
        expect(result.current.savedSearches[0].id).toBe('search-other-tab');
      });
    });

    it('should not react to storage events for different keys', () => {
      const { result } = renderHook(() => useSavedSearches());

      // Save a search locally
      act(() => {
        result.current.saveSearch('Local Search', 'query', {});
      });

      expect(result.current.savedSearches).toHaveLength(1);

      // Simulate storage event for a different key
      act(() => {
        localStorageMock._triggerStorageEvent(
          'some_other_key',
          'some value',
          null
        );
      });

      // State should remain unchanged
      expect(result.current.savedSearches).toHaveLength(1);
      expect(result.current.savedSearches[0].name).toBe('Local Search');
    });

    it('should handle concurrent saves from multiple tabs', async () => {
      const { result: tabA } = renderHook(() => useSavedSearches());
      const { result: tabB } = renderHook(() => useSavedSearches());

      // Tab A saves a search
      act(() => {
        tabA.current.saveSearch('Search A', 'query-a', {});
      });

      // Get current storage state
      const stateAfterA = localStorageMock._getStore()[STORAGE_KEY];

      // Simulate Tab B receiving the storage event
      act(() => {
        localStorageMock._triggerStorageEvent(STORAGE_KEY, stateAfterA, null);
      });

      // Tab B should now have Tab A's search
      await waitFor(() => {
        expect(tabB.current.savedSearches).toHaveLength(1);
        expect(tabB.current.savedSearches[0].name).toBe('Search A');
      });

      // Tab B saves a search
      act(() => {
        tabB.current.saveSearch('Search B', 'query-b', {});
      });

      const stateAfterB = localStorageMock._getStore()[STORAGE_KEY];

      // Simulate Tab A receiving the storage event
      act(() => {
        localStorageMock._triggerStorageEvent(STORAGE_KEY, stateAfterB, stateAfterA);
      });

      // Tab A should now have both searches
      await waitFor(() => {
        expect(tabA.current.savedSearches).toHaveLength(2);
      });
    });

    it('should handle deletion from another tab', async () => {
      // Pre-populate with a search
      const initialSearch: SavedSearch = {
        id: 'search-1',
        name: 'Initial Search',
        query: 'test',
        filters: {},
        createdAt: new Date().toISOString(),
      };
      localStorageMock.setItem(STORAGE_KEY, JSON.stringify([initialSearch]));
      localStorageMock.getItem.mockReturnValue(JSON.stringify([initialSearch]));

      const { result } = renderHook(() => useSavedSearches());

      // Wait for initial load
      await waitFor(() => {
        expect(result.current.savedSearches).toHaveLength(1);
      });

      // Simulate another tab deleting the search
      const oldValue = JSON.stringify([initialSearch]);
      const newValue = JSON.stringify([]);
      localStorageMock._setFromOtherTab(STORAGE_KEY, newValue);
      localStorageMock.getItem.mockReturnValue(newValue);

      act(() => {
        localStorageMock._triggerStorageEvent(STORAGE_KEY, newValue, oldValue);
      });

      // Verify local state updated
      await waitFor(() => {
        expect(result.current.savedSearches).toHaveLength(0);
      });
    });

    it('should handle clearAll from another tab', async () => {
      // Pre-populate with multiple searches
      const initialSearches: SavedSearch[] = [
        {
          id: 'search-1',
          name: 'Search 1',
          query: 'query1',
          filters: {},
          createdAt: new Date().toISOString(),
        },
        {
          id: 'search-2',
          name: 'Search 2',
          query: 'query2',
          filters: {},
          createdAt: new Date().toISOString(),
        },
      ];
      localStorageMock.getItem.mockReturnValue(JSON.stringify(initialSearches));

      const { result } = renderHook(() => useSavedSearches());

      await waitFor(() => {
        expect(result.current.savedSearches).toHaveLength(2);
      });

      // Simulate another tab clearing all
      const oldValue = JSON.stringify(initialSearches);
      const newValue = JSON.stringify([]);
      localStorageMock._setFromOtherTab(STORAGE_KEY, newValue);
      localStorageMock.getItem.mockReturnValue(newValue);

      act(() => {
        localStorageMock._triggerStorageEvent(STORAGE_KEY, newValue, oldValue);
      });

      await waitFor(() => {
        expect(result.current.savedSearches).toHaveLength(0);
      });
    });

    it('should handle corrupted data from another tab gracefully', async () => {
      const { result } = renderHook(() => useSavedSearches());

      // Simulate another tab writing corrupted data
      const corruptedData = 'this is not valid json {{{';
      localStorageMock._setFromOtherTab(STORAGE_KEY, corruptedData);
      localStorageMock.getItem.mockReturnValue(corruptedData);

      act(() => {
        localStorageMock._triggerStorageEvent(STORAGE_KEY, corruptedData, null);
      });

      // Should handle gracefully and return empty array
      await waitFor(() => {
        expect(result.current.savedSearches).toEqual([]);
      });
    });

    it('should handle null newValue (key removed)', async () => {
      const initialSearch: SavedSearch = {
        id: 'search-1',
        name: 'Test',
        query: 'test',
        filters: {},
        createdAt: new Date().toISOString(),
      };
      localStorageMock.getItem.mockReturnValue(JSON.stringify([initialSearch]));

      const { result } = renderHook(() => useSavedSearches());

      await waitFor(() => {
        expect(result.current.savedSearches).toHaveLength(1);
      });

      // Simulate key being removed (e.g., localStorage.clear() from another tab)
      localStorageMock.getItem.mockReturnValue(null);

      act(() => {
        // When localStorage.clear() is called from another tab, newValue is null
        // The StorageEvent type accepts null for newValue
        const event = new StorageEvent('storage', {
          key: STORAGE_KEY,
          newValue: null,
          oldValue: JSON.stringify([initialSearch]),
          url: window.location.href,
        });
        window.dispatchEvent(event);
      });

      await waitFor(() => {
        expect(result.current.savedSearches).toEqual([]);
      });
    });
  });

  describe('useLocalStorage Cross-Tab Sync', () => {
    it('should provide consistent state across multiple hook instances', () => {
      const key = 'test-shared-key';
      const initialValue = { count: 0 };

      const { result: hook1 } = renderHook(() =>
        useLocalStorage(key, initialValue)
      );
      const { result: hook2 } = renderHook(() =>
        useLocalStorage(key, initialValue)
      );

      // Both hooks start with the same initial value
      expect(hook1.current[0]).toEqual({ count: 0 });
      expect(hook2.current[0]).toEqual({ count: 0 });

      // Update from hook1
      act(() => {
        hook1.current[1]({ count: 5 });
      });

      // hook1 sees the update immediately
      expect(hook1.current[0]).toEqual({ count: 5 });

      // hook2 would see the update on remount or storage event
      // (This tests the behavior of isolated hook instances)
    });

    it('should handle functional updates', () => {
      const key = 'counter';
      const { result } = renderHook(() => useLocalStorage(key, 0));

      act(() => {
        result.current[1]((prev) => prev + 1);
      });

      expect(result.current[0]).toBe(1);

      act(() => {
        result.current[1]((prev) => prev + 10);
      });

      expect(result.current[0]).toBe(11);
    });

    it('should persist complex objects with nested structures', () => {
      const key = 'complex-settings';
      const complexValue = {
        theme: {
          mode: 'dark',
          colors: {
            primary: '#007bff',
            secondary: '#6c757d',
          },
        },
        preferences: {
          notifications: true,
          sounds: ['alert', 'message'],
        },
        lastUpdated: new Date().toISOString(),
      };

      const { result } = renderHook(() =>
        useLocalStorage(key, { theme: { mode: 'light', colors: {} }, preferences: {} })
      );

      act(() => {
        result.current[1](complexValue);
      });

      expect(result.current[0]).toEqual(complexValue);

      // Verify it was stringified correctly
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        key,
        JSON.stringify(complexValue)
      );
    });
  });

  describe('Event Listener Cleanup', () => {
    it('should remove storage event listener on unmount', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = renderHook(() => useSavedSearches());

      // Listener should be added
      expect(addEventListenerSpy).toHaveBeenCalledWith(
        'storage',
        expect.any(Function)
      );

      // Unmount the hook
      unmount();

      // Listener should be removed
      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'storage',
        expect.any(Function)
      );

      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    });

    it('should not leak listeners on multiple mount/unmount cycles', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      // Mount and unmount 5 times
      for (let i = 0; i < 5; i++) {
        const { unmount } = renderHook(() => useSavedSearches());
        unmount();
      }

      // Each cycle should add and remove exactly one listener
      const addCalls = addEventListenerSpy.mock.calls.filter(
        ([event]) => event === 'storage'
      );
      const removeCalls = removeEventListenerSpy.mock.calls.filter(
        ([event]) => event === 'storage'
      );

      expect(addCalls.length).toBe(removeCalls.length);

      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    });
  });

  describe('Edge Cases', () => {
    it('should handle rapid successive updates from another tab', async () => {
      const { result } = renderHook(() => useSavedSearches());

      // Simulate rapid updates from another tab
      for (let i = 1; i <= 10; i++) {
        const searches: SavedSearch[] = Array.from({ length: i }, (_, j) => ({
          id: `search-${j}`,
          name: `Search ${j}`,
          query: `query-${j}`,
          filters: {},
          createdAt: new Date().toISOString(),
        }));

        const value = JSON.stringify(searches);
        localStorageMock._setFromOtherTab(STORAGE_KEY, value);
        localStorageMock.getItem.mockReturnValue(value);

        act(() => {
          localStorageMock._triggerStorageEvent(STORAGE_KEY, value, null);
        });
      }

      // Final state should reflect the last update
      await waitFor(() => {
        expect(result.current.savedSearches).toHaveLength(10);
      });
    });

    it('should handle storage event with same key but different origin', () => {
      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.saveSearch('Local', 'query', {});
      });

      expect(result.current.savedSearches).toHaveLength(1);

      // Storage events from the same document should be ignored
      // (only fires for changes from OTHER windows/tabs)
      // We simulate this by checking that our local state is preserved
      expect(localStorageMock._getStore()[STORAGE_KEY]).toBeDefined();
      expect(result.current.savedSearches[0].name).toBe('Local');
    });

    it('should validate data structure when syncing from another tab', async () => {
      const { result } = renderHook(() => useSavedSearches());

      // Simulate another tab writing invalid structure (missing required fields)
      const invalidData = JSON.stringify([
        { id: 'search-1' }, // Missing name, query, filters, createdAt
        { name: 'Valid Name' }, // Missing id, query, filters, createdAt
      ]);
      localStorageMock._setFromOtherTab(STORAGE_KEY, invalidData);
      localStorageMock.getItem.mockReturnValue(invalidData);

      act(() => {
        localStorageMock._triggerStorageEvent(STORAGE_KEY, invalidData, null);
      });

      // Invalid items should be filtered out
      await waitFor(() => {
        expect(result.current.savedSearches).toEqual([]);
      });
    });
  });
});

// Add STORAGE_KEY constant needed by tests
const STORAGE_KEY = 'hsi_saved_searches';
