import { useState, useCallback, useEffect } from 'react';

import type { SearchFilters } from '../components/search/SearchBar';

/**
 * Represents a saved search configuration
 */
export interface SavedSearch {
  /** Unique identifier for the saved search */
  id: string;
  /** User-defined name for the saved search */
  name: string;
  /** The search query string */
  query: string;
  /** Applied filters */
  filters: SearchFilters;
  /** ISO timestamp when the search was saved */
  createdAt: string;
}

/**
 * Return type for the loadSearch function
 */
export interface LoadedSearch {
  query: string;
  filters: SearchFilters;
}

/**
 * Return type for the useSavedSearches hook
 */
export interface UseSavedSearchesReturn {
  /** List of saved searches, newest first */
  savedSearches: SavedSearch[];
  /** Save a new search */
  saveSearch: (name: string, query: string, filters: SearchFilters) => void;
  /** Delete a saved search by ID */
  deleteSearch: (id: string) => void;
  /** Load a saved search by ID, returns query and filters or null if not found */
  loadSearch: (id: string) => LoadedSearch | null;
  /** Clear all saved searches */
  clearAll: () => void;
}

/** LocalStorage key for saved searches */
const STORAGE_KEY = 'hsi_saved_searches';

/** Maximum number of saved searches to keep */
const MAX_SAVED_SEARCHES = 10;

/**
 * Generate a unique ID for saved searches
 */
const generateId = (): string => {
  return `search-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
};

/**
 * Type guard to validate a SavedSearch object
 */
const isSavedSearch = (item: unknown): item is SavedSearch => {
  if (typeof item !== 'object' || item === null) return false;
  const obj = item as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    typeof obj.name === 'string' &&
    typeof obj.query === 'string' &&
    typeof obj.filters === 'object' &&
    typeof obj.createdAt === 'string'
  );
};

/**
 * Safely read saved searches from localStorage
 */
const readFromStorage = (): SavedSearch[] => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];
    const parsed: unknown = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];
    // Filter to only valid SavedSearch objects
    return parsed.filter(isSavedSearch);
  } catch {
    return [];
  }
};

/**
 * Safely write saved searches to localStorage
 */
const writeToStorage = (searches: SavedSearch[]): void => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(searches));
  } catch {
    // Silently fail if localStorage is unavailable or quota exceeded
    console.warn('Failed to save searches to localStorage');
  }
};

/**
 * Custom hook for managing saved searches in localStorage.
 *
 * Features:
 * - Persists searches to localStorage (key: hsi_saved_searches)
 * - Limits to 10 most recent searches
 * - Provides CRUD operations for saved searches
 * - Handles localStorage errors gracefully
 *
 * @example
 * ```tsx
 * const { savedSearches, saveSearch, deleteSearch, loadSearch, clearAll } = useSavedSearches();
 *
 * // Save a new search
 * saveSearch('High Risk Events', 'suspicious person', { severity: 'high' });
 *
 * // Load a saved search
 * const search = loadSearch('search-123');
 * if (search) {
 *   setQuery(search.query);
 *   setFilters(search.filters);
 * }
 *
 * // Delete a saved search
 * deleteSearch('search-123');
 *
 * // Clear all saved searches
 * clearAll();
 * ```
 */
export function useSavedSearches(): UseSavedSearchesReturn {
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>(() => {
    return readFromStorage();
  });

  // Sync state with localStorage changes from other tabs
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        setSavedSearches(readFromStorage());
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const saveSearch = useCallback((name: string, query: string, filters: SearchFilters) => {
    const newSearch: SavedSearch = {
      id: generateId(),
      name,
      query,
      filters,
      createdAt: new Date().toISOString(),
    };

    setSavedSearches((prev) => {
      // Add new search at the beginning, limit to MAX_SAVED_SEARCHES
      const updated = [newSearch, ...prev].slice(0, MAX_SAVED_SEARCHES);
      writeToStorage(updated);
      return updated;
    });
  }, []);

  const deleteSearch = useCallback((id: string) => {
    setSavedSearches((prev) => {
      const updated = prev.filter((s) => s.id !== id);
      writeToStorage(updated);
      return updated;
    });
  }, []);

  const loadSearch = useCallback(
    (id: string): LoadedSearch | null => {
      const search = savedSearches.find((s) => s.id === id);
      if (!search) return null;
      return {
        query: search.query,
        filters: search.filters,
      };
    },
    [savedSearches]
  );

  const clearAll = useCallback(() => {
    setSavedSearches([]);
    writeToStorage([]);
  }, []);

  return {
    savedSearches,
    saveSearch,
    deleteSearch,
    loadSearch,
    clearAll,
  };
}
