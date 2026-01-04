/**
 * useSavedSearches hook tests.
 *
 * Tests localStorage-based saved searches functionality for the Advanced Search UI.
 */
import { renderHook, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';

import { useSavedSearches } from './useSavedSearches';

import type { SavedSearch } from './useSavedSearches';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

describe('useSavedSearches', () => {
  const STORAGE_KEY = 'hsi_saved_searches';

  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.clear();
  });

  afterEach(() => {
    localStorageMock.clear();
  });

  describe('initialization', () => {
    it('returns empty array when localStorage is empty', () => {
      const { result } = renderHook(() => useSavedSearches());

      expect(result.current.savedSearches).toEqual([]);
    });

    it('loads saved searches from localStorage on mount', () => {
      const existingSearches: SavedSearch[] = [
        {
          id: 'search-1',
          name: 'High Risk Events',
          query: 'suspicious person',
          filters: { severity: 'high' },
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches));

      const { result } = renderHook(() => useSavedSearches());

      expect(result.current.savedSearches).toEqual(existingSearches);
      expect(localStorageMock.getItem).toHaveBeenCalledWith(STORAGE_KEY);
    });

    it('handles invalid JSON in localStorage gracefully', () => {
      localStorageMock.getItem.mockReturnValueOnce('invalid json');

      const { result } = renderHook(() => useSavedSearches());

      expect(result.current.savedSearches).toEqual([]);
    });

    it('handles localStorage access errors gracefully', () => {
      localStorageMock.getItem.mockImplementationOnce(() => {
        throw new Error('Storage access denied');
      });

      const { result } = renderHook(() => useSavedSearches());

      expect(result.current.savedSearches).toEqual([]);
    });
  });

  describe('saveSearch', () => {
    it('saves a new search with query and filters', () => {
      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.saveSearch('My Search', 'suspicious person', { severity: 'high' });
      });

      expect(result.current.savedSearches).toHaveLength(1);
      expect(result.current.savedSearches[0].name).toBe('My Search');
      expect(result.current.savedSearches[0].query).toBe('suspicious person');
      expect(result.current.savedSearches[0].filters).toEqual({ severity: 'high' });
      expect(result.current.savedSearches[0].id).toBeDefined();
      expect(result.current.savedSearches[0].createdAt).toBeDefined();
    });

    it('persists saved search to localStorage', () => {
      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.saveSearch('Test Search', 'vehicle', {});
      });

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        STORAGE_KEY,
        expect.stringContaining('Test Search')
      );
    });

    it('adds new searches to the beginning of the list', () => {
      const existingSearches: SavedSearch[] = [
        {
          id: 'search-1',
          name: 'Old Search',
          query: 'old query',
          filters: {},
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches));

      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.saveSearch('New Search', 'new query', {});
      });

      expect(result.current.savedSearches).toHaveLength(2);
      expect(result.current.savedSearches[0].name).toBe('New Search');
      expect(result.current.savedSearches[1].name).toBe('Old Search');
    });

    it('limits saved searches to 10 items', () => {
      const existingSearches: SavedSearch[] = Array.from({ length: 10 }, (_, i) => ({
        id: `search-${i}`,
        name: `Search ${i}`,
        query: `query ${i}`,
        filters: {},
        createdAt: new Date(2025, 0, i + 1).toISOString(),
      }));
      localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches));

      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.saveSearch('New Search', 'new query', {});
      });

      expect(result.current.savedSearches).toHaveLength(10);
      expect(result.current.savedSearches[0].name).toBe('New Search');
      // The last search in the list (Search 9) should be removed as it's pushed out
      expect(result.current.savedSearches.find((s) => s.name === 'Search 9')).toBeUndefined();
      // Search 0 should still exist (it's now at index 1)
      expect(result.current.savedSearches.find((s) => s.name === 'Search 0')).toBeDefined();
    });

    it('saves search with empty filters', () => {
      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.saveSearch('Simple Search', 'query only', {});
      });

      expect(result.current.savedSearches[0].filters).toEqual({});
    });

    it('generates unique IDs for each saved search', () => {
      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.saveSearch('Search 1', 'query 1', {});
      });

      act(() => {
        result.current.saveSearch('Search 2', 'query 2', {});
      });

      expect(result.current.savedSearches[0].id).not.toBe(result.current.savedSearches[1].id);
    });

    it('handles localStorage write errors gracefully', () => {
      localStorageMock.setItem.mockImplementationOnce(() => {
        throw new Error('QuotaExceeded');
      });

      const { result } = renderHook(() => useSavedSearches());

      // Should not throw
      act(() => {
        result.current.saveSearch('Test', 'query', {});
      });

      // State should still be updated even if localStorage fails
      expect(result.current.savedSearches).toHaveLength(1);
    });
  });

  describe('deleteSearch', () => {
    it('removes a saved search by ID', () => {
      const existingSearches: SavedSearch[] = [
        {
          id: 'search-1',
          name: 'Search 1',
          query: 'query 1',
          filters: {},
          createdAt: '2025-01-01T00:00:00Z',
        },
        {
          id: 'search-2',
          name: 'Search 2',
          query: 'query 2',
          filters: {},
          createdAt: '2025-01-02T00:00:00Z',
        },
      ];
      localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches));

      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.deleteSearch('search-1');
      });

      expect(result.current.savedSearches).toHaveLength(1);
      expect(result.current.savedSearches[0].id).toBe('search-2');
    });

    it('updates localStorage after deletion', () => {
      const existingSearches: SavedSearch[] = [
        {
          id: 'search-1',
          name: 'Search 1',
          query: 'query 1',
          filters: {},
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches));

      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.deleteSearch('search-1');
      });

      expect(localStorageMock.setItem).toHaveBeenCalledWith(STORAGE_KEY, '[]');
    });

    it('does nothing when deleting non-existent ID', () => {
      const existingSearches: SavedSearch[] = [
        {
          id: 'search-1',
          name: 'Search 1',
          query: 'query 1',
          filters: {},
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches));

      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.deleteSearch('non-existent-id');
      });

      expect(result.current.savedSearches).toHaveLength(1);
    });
  });

  describe('loadSearch', () => {
    it('returns the search data for a given ID', () => {
      const existingSearches: SavedSearch[] = [
        {
          id: 'search-1',
          name: 'High Risk',
          query: 'suspicious person',
          filters: { severity: 'high', camera_id: 'cam-1' },
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches));

      const { result } = renderHook(() => useSavedSearches());

      const loaded = result.current.loadSearch('search-1');

      expect(loaded).toEqual({
        query: 'suspicious person',
        filters: { severity: 'high', camera_id: 'cam-1' },
      });
    });

    it('returns null for non-existent ID', () => {
      const { result } = renderHook(() => useSavedSearches());

      const loaded = result.current.loadSearch('non-existent');

      expect(loaded).toBeNull();
    });
  });

  describe('clearAll', () => {
    it('removes all saved searches', () => {
      const existingSearches: SavedSearch[] = [
        {
          id: 'search-1',
          name: 'Search 1',
          query: 'query 1',
          filters: {},
          createdAt: '2025-01-01T00:00:00Z',
        },
        {
          id: 'search-2',
          name: 'Search 2',
          query: 'query 2',
          filters: {},
          createdAt: '2025-01-02T00:00:00Z',
        },
      ];
      localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches));

      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.clearAll();
      });

      expect(result.current.savedSearches).toEqual([]);
    });

    it('updates localStorage to empty array after clearing', () => {
      const existingSearches: SavedSearch[] = [
        {
          id: 'search-1',
          name: 'Search 1',
          query: 'query 1',
          filters: {},
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      localStorageMock.getItem.mockReturnValueOnce(JSON.stringify(existingSearches));

      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.clearAll();
      });

      expect(localStorageMock.setItem).toHaveBeenCalledWith(STORAGE_KEY, '[]');
    });
  });

  describe('filter serialization', () => {
    it('preserves all filter properties when saving and loading', () => {
      const complexFilters = {
        camera_id: 'cam-1',
        start_date: '2025-01-01',
        end_date: '2025-12-31',
        severity: 'high,critical',
        object_type: 'person',
        reviewed: false,
      };

      const { result } = renderHook(() => useSavedSearches());

      act(() => {
        result.current.saveSearch('Complex Search', 'complex query', complexFilters);
      });

      const loaded = result.current.loadSearch(result.current.savedSearches[0].id);

      expect(loaded?.filters).toEqual(complexFilters);
    });
  });
});
