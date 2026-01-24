/**
 * Tests for Query Persistence Configuration (NEM-3363)
 *
 * These tests verify the query persistence functionality for offline/cold-start
 * performance improvements using TanStack Query's persist-query-client plugin.
 */
import { QueryClient } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  PERSISTENCE_STORAGE_KEY,
  PERSISTENCE_MAX_AGE,
  PERSISTABLE_QUERY_KEY_PREFIXES,
  createQueryPersister,
  shouldDehydrateQuery,
  setupQueryPersistence,
  clearPersistedCache,
  getPersistedCacheSize,
  hasPersistedCache,
  type DehydrateQueryLike,
} from './queryPersistence';

// ============================================================================
// Test Helpers
// ============================================================================

/**
 * Creates a mock Query object for testing shouldDehydrateQuery
 */
function createMockQuery(
  queryKey: readonly unknown[],
  status: 'pending' | 'error' | 'success' = 'success',
  data: unknown = { test: 'data' }
): DehydrateQueryLike {
  return {
    queryKey,
    state: {
      status,
      data: status === 'success' ? data : undefined,
    },
  };
}

// ============================================================================
// Constants Tests
// ============================================================================

describe('queryPersistence constants', () => {
  describe('PERSISTENCE_STORAGE_KEY', () => {
    it('has the correct storage key value', () => {
      expect(PERSISTENCE_STORAGE_KEY).toBe('security-dashboard-cache');
    });
  });

  describe('PERSISTENCE_MAX_AGE', () => {
    it('equals 24 hours in milliseconds', () => {
      const twentyFourHoursMs = 1000 * 60 * 60 * 24;
      expect(PERSISTENCE_MAX_AGE).toBe(twentyFourHoursMs);
    });

    it('is greater than 0', () => {
      expect(PERSISTENCE_MAX_AGE).toBeGreaterThan(0);
    });
  });

  describe('PERSISTABLE_QUERY_KEY_PREFIXES', () => {
    it('includes cameras prefix', () => {
      expect(PERSISTABLE_QUERY_KEY_PREFIXES).toContain('cameras');
    });

    it('includes system.config prefix', () => {
      const hasSystemConfig = PERSISTABLE_QUERY_KEY_PREFIXES.some(
        (prefix) =>
          Array.isArray(prefix) && prefix[0] === 'system' && prefix[1] === 'config'
      );
      expect(hasSystemConfig).toBe(true);
    });

    it('includes gpus prefix', () => {
      expect(PERSISTABLE_QUERY_KEY_PREFIXES).toContain('gpus');
    });

    it('includes alerts.rules prefix', () => {
      const hasAlertsRules = PERSISTABLE_QUERY_KEY_PREFIXES.some(
        (prefix) =>
          Array.isArray(prefix) && prefix[0] === 'alerts' && prefix[1] === 'rules'
      );
      expect(hasAlertsRules).toBe(true);
    });
  });
});

// ============================================================================
// shouldDehydrateQuery Tests
// ============================================================================

describe('shouldDehydrateQuery', () => {
  describe('query state filtering', () => {
    it('returns true for successful queries with data', () => {
      const query = createMockQuery(['cameras'], 'success', [{ id: 'cam-1' }]);
      expect(shouldDehydrateQuery(query)).toBe(true);
    });

    it('returns false for pending queries', () => {
      const query = createMockQuery(['cameras'], 'pending');
      expect(shouldDehydrateQuery(query)).toBe(false);
    });

    it('returns false for error queries', () => {
      const query = createMockQuery(['cameras'], 'error');
      expect(shouldDehydrateQuery(query)).toBe(false);
    });

    it('returns false for successful queries with undefined data', () => {
      const query: DehydrateQueryLike = {
        queryKey: ['cameras'],
        state: {
          status: 'success',
          data: undefined,
        },
      };
      expect(shouldDehydrateQuery(query)).toBe(false);
    });
  });

  describe('query key prefix matching', () => {
    describe('cameras prefix', () => {
      it('persists cameras list query', () => {
        const query = createMockQuery(['cameras', 'list']);
        expect(shouldDehydrateQuery(query)).toBe(true);
      });

      it('persists cameras detail query', () => {
        const query = createMockQuery(['cameras', 'detail', 'cam-1']);
        expect(shouldDehydrateQuery(query)).toBe(true);
      });

      it('persists cameras all query', () => {
        const query = createMockQuery(['cameras']);
        expect(shouldDehydrateQuery(query)).toBe(true);
      });
    });

    describe('system.config prefix', () => {
      it('persists system config query', () => {
        const query = createMockQuery(['system', 'config']);
        expect(shouldDehydrateQuery(query)).toBe(true);
      });

      it('does NOT persist system health query (not in prefix list)', () => {
        const query = createMockQuery(['system', 'health']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist system gpu query (real-time data)', () => {
        const query = createMockQuery(['system', 'gpu']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist system stats query (real-time data)', () => {
        const query = createMockQuery(['system', 'stats']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });
    });

    describe('gpus prefix', () => {
      it('persists gpus list query', () => {
        const query = createMockQuery(['gpus', 'list']);
        expect(shouldDehydrateQuery(query)).toBe(true);
      });

      it('persists gpus detail query', () => {
        const query = createMockQuery(['gpus', 'detail', 'gpu-0']);
        expect(shouldDehydrateQuery(query)).toBe(true);
      });
    });

    describe('alerts.rules prefix', () => {
      it('persists alerts rules list query', () => {
        const query = createMockQuery(['alerts', 'rules', 'list']);
        expect(shouldDehydrateQuery(query)).toBe(true);
      });

      it('persists alerts rules detail query', () => {
        const query = createMockQuery(['alerts', 'rules', { enabled: true }]);
        expect(shouldDehydrateQuery(query)).toBe(true);
      });

      it('does NOT persist alerts base query (without rules)', () => {
        const query = createMockQuery(['alerts']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist alerts all query', () => {
        const query = createMockQuery(['alerts', 'all']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });
    });

    describe('non-persistable queries (real-time data)', () => {
      it('does NOT persist events queries', () => {
        const query = createMockQuery(['events', 'list']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist detections queries', () => {
        const query = createMockQuery(['detections', 'list']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist ai metrics queries', () => {
        const query = createMockQuery(['ai', 'metrics']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist logs queries', () => {
        const query = createMockQuery(['logs', 'list']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist auditLogs queries', () => {
        const query = createMockQuery(['auditLogs', 'list']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist jobs queries', () => {
        const query = createMockQuery(['jobs', 'list']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist entities queries', () => {
        const query = createMockQuery(['entities', 'list']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist analytics queries', () => {
        const query = createMockQuery(['analytics', 'cameraUptime']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist notifications queries', () => {
        const query = createMockQuery(['notifications', 'config']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist debug queries', () => {
        const query = createMockQuery(['debug', 'profile']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist summaries queries', () => {
        const query = createMockQuery(['summaries', 'latest']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist hierarchy queries', () => {
        const query = createMockQuery(['hierarchy', 'households']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });

      it('does NOT persist dlq queries', () => {
        const query = createMockQuery(['dlq', 'stats']);
        expect(shouldDehydrateQuery(query)).toBe(false);
      });
    });
  });
});

// ============================================================================
// createQueryPersister Tests
// ============================================================================

describe('createQueryPersister', () => {
  let originalLocalStorage: Storage;

  beforeEach(() => {
    // Save original localStorage
    originalLocalStorage = window.localStorage;
  });

  afterEach(() => {
    // Restore localStorage
    Object.defineProperty(window, 'localStorage', {
      value: originalLocalStorage,
      writable: true,
    });
    // Clear test data
    try {
      window.localStorage.removeItem(PERSISTENCE_STORAGE_KEY);
      window.localStorage.removeItem('__storage_test__');
    } catch {
      // Ignore cleanup errors
    }
  });

  it('creates a persister when localStorage is available', () => {
    const persister = createQueryPersister();
    expect(persister).toBeDefined();
    expect(persister).not.toBeNull();
  });

  it('returns undefined when localStorage is not available', () => {
    // Mock window.localStorage as undefined
    Object.defineProperty(window, 'localStorage', {
      value: undefined,
      writable: true,
    });

    const persister = createQueryPersister();
    expect(persister).toBeUndefined();
  });

  it('returns undefined when localStorage throws on access', () => {
    // Mock localStorage that throws on setItem (e.g., quota exceeded)
    const mockStorage = {
      setItem: vi.fn(() => {
        throw new Error('QuotaExceededError');
      }),
      getItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(),
    };

    Object.defineProperty(window, 'localStorage', {
      value: mockStorage,
      writable: true,
    });

    const persister = createQueryPersister();
    expect(persister).toBeUndefined();
  });
});

// ============================================================================
// Storage Utility Tests
// ============================================================================

describe('clearPersistedCache', () => {
  beforeEach(() => {
    // Clear any existing data
    try {
      window.localStorage.removeItem(PERSISTENCE_STORAGE_KEY);
    } catch {
      // Ignore
    }
  });

  it('removes the persisted cache from localStorage', () => {
    // Set some data
    window.localStorage.setItem(PERSISTENCE_STORAGE_KEY, JSON.stringify({ test: 'data' }));
    expect(window.localStorage.getItem(PERSISTENCE_STORAGE_KEY)).not.toBeNull();

    // Clear it
    clearPersistedCache();

    // Verify it's gone
    expect(window.localStorage.getItem(PERSISTENCE_STORAGE_KEY)).toBeNull();
  });

  it('does not throw when cache does not exist', () => {
    expect(() => clearPersistedCache()).not.toThrow();
  });

  it('handles errors gracefully (e.g., private browsing)', () => {
    const originalLocalStorage = window.localStorage;

    // Mock localStorage that throws
    Object.defineProperty(window, 'localStorage', {
      value: {
        removeItem: () => {
          throw new Error('Access denied');
        },
      },
      writable: true,
    });

    expect(() => clearPersistedCache()).not.toThrow();

    // Restore
    Object.defineProperty(window, 'localStorage', {
      value: originalLocalStorage,
      writable: true,
    });
  });
});

describe('getPersistedCacheSize', () => {
  beforeEach(() => {
    try {
      window.localStorage.removeItem(PERSISTENCE_STORAGE_KEY);
    } catch {
      // Ignore
    }
  });

  it('returns 0 when cache does not exist', () => {
    expect(getPersistedCacheSize()).toBe(0);
  });

  it('returns the size in bytes when cache exists', () => {
    const testData = JSON.stringify({ cameras: [{ id: 'cam-1', name: 'Camera 1' }] });
    window.localStorage.setItem(PERSISTENCE_STORAGE_KEY, testData);

    const size = getPersistedCacheSize();
    expect(size).toBeGreaterThan(0);
    // Size should match the blob size of the data
    expect(size).toBe(new Blob([testData]).size);
  });

  it('returns 0 when localStorage is not available', () => {
    const originalLocalStorage = window.localStorage;

    Object.defineProperty(window, 'localStorage', {
      value: undefined,
      writable: true,
    });

    expect(getPersistedCacheSize()).toBe(0);

    Object.defineProperty(window, 'localStorage', {
      value: originalLocalStorage,
      writable: true,
    });
  });

  it('handles errors gracefully', () => {
    const originalLocalStorage = window.localStorage;

    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: () => {
          throw new Error('Access denied');
        },
      },
      writable: true,
    });

    expect(getPersistedCacheSize()).toBe(0);

    Object.defineProperty(window, 'localStorage', {
      value: originalLocalStorage,
      writable: true,
    });
  });
});

describe('hasPersistedCache', () => {
  beforeEach(() => {
    try {
      window.localStorage.removeItem(PERSISTENCE_STORAGE_KEY);
    } catch {
      // Ignore
    }
  });

  it('returns false when cache does not exist', () => {
    expect(hasPersistedCache()).toBe(false);
  });

  it('returns false when cache is empty string', () => {
    window.localStorage.setItem(PERSISTENCE_STORAGE_KEY, '');
    expect(hasPersistedCache()).toBe(false);
  });

  it('returns true when cache exists and has content', () => {
    window.localStorage.setItem(PERSISTENCE_STORAGE_KEY, JSON.stringify({ test: 'data' }));
    expect(hasPersistedCache()).toBe(true);
  });

  it('returns false when localStorage is not available', () => {
    const originalLocalStorage = window.localStorage;

    Object.defineProperty(window, 'localStorage', {
      value: undefined,
      writable: true,
    });

    expect(hasPersistedCache()).toBe(false);

    Object.defineProperty(window, 'localStorage', {
      value: originalLocalStorage,
      writable: true,
    });
  });

  it('handles errors gracefully', () => {
    const originalLocalStorage = window.localStorage;

    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: () => {
          throw new Error('Access denied');
        },
      },
      writable: true,
    });

    expect(hasPersistedCache()).toBe(false);

    Object.defineProperty(window, 'localStorage', {
      value: originalLocalStorage,
      writable: true,
    });
  });
});

// ============================================================================
// setupQueryPersistence Tests
// ============================================================================

describe('setupQueryPersistence', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    // Clear localStorage before each test
    try {
      window.localStorage.removeItem(PERSISTENCE_STORAGE_KEY);
    } catch {
      // Ignore
    }
  });

  afterEach(() => {
    queryClient.clear();
    try {
      window.localStorage.removeItem(PERSISTENCE_STORAGE_KEY);
    } catch {
      // Ignore
    }
  });

  it('returns a cleanup function when localStorage is available', () => {
    const cleanup = setupQueryPersistence(queryClient);
    expect(typeof cleanup).toBe('function');
    cleanup?.();
  });

  it('returns undefined when localStorage is not available', () => {
    const originalLocalStorage = window.localStorage;

    Object.defineProperty(window, 'localStorage', {
      value: undefined,
      writable: true,
    });

    const cleanup = setupQueryPersistence(queryClient);
    expect(cleanup).toBeUndefined();

    Object.defineProperty(window, 'localStorage', {
      value: originalLocalStorage,
      writable: true,
    });
  });

  it('accepts custom maxAge option', () => {
    const customMaxAge = 1000 * 60 * 60; // 1 hour
    const cleanup = setupQueryPersistence(queryClient, { maxAge: customMaxAge });
    expect(typeof cleanup).toBe('function');
    cleanup?.();
  });

  it('accepts custom dehydrateFilter option', () => {
    const customFilter = (query: DehydrateQueryLike) => {
      return query.queryKey[0] === 'custom';
    };
    const cleanup = setupQueryPersistence(queryClient, { dehydrateFilter: customFilter });
    expect(typeof cleanup).toBe('function');
    cleanup?.();
  });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('queryPersistence integration', () => {
  describe('prefix matching edge cases', () => {
    it('matches exact string prefix', () => {
      const camerasQuery = createMockQuery(['cameras']);
      const gpusQuery = createMockQuery(['gpus']);

      expect(shouldDehydrateQuery(camerasQuery)).toBe(true);
      expect(shouldDehydrateQuery(gpusQuery)).toBe(true);
    });

    it('matches array prefix with exact elements', () => {
      const systemConfigQuery = createMockQuery(['system', 'config']);
      const alertsRulesQuery = createMockQuery(['alerts', 'rules']);

      expect(shouldDehydrateQuery(systemConfigQuery)).toBe(true);
      expect(shouldDehydrateQuery(alertsRulesQuery)).toBe(true);
    });

    it('does not match partial array prefix', () => {
      // 'system' alone should not match ['system', 'config']
      const systemOnlyQuery = createMockQuery(['system']);
      expect(shouldDehydrateQuery(systemOnlyQuery)).toBe(false);

      // 'alerts' alone should not match ['alerts', 'rules']
      const alertsOnlyQuery = createMockQuery(['alerts']);
      expect(shouldDehydrateQuery(alertsOnlyQuery)).toBe(false);
    });

    it('does not match different array prefix', () => {
      // ['system', 'health'] should not match ['system', 'config']
      const systemHealthQuery = createMockQuery(['system', 'health']);
      expect(shouldDehydrateQuery(systemHealthQuery)).toBe(false);

      // ['alerts', 'all'] should not match ['alerts', 'rules']
      const alertsAllQuery = createMockQuery(['alerts', 'all']);
      expect(shouldDehydrateQuery(alertsAllQuery)).toBe(false);
    });

    it('matches longer keys that start with prefix', () => {
      // ['cameras', 'list', { filters: {} }] should match 'cameras'
      const camerasListQuery = createMockQuery(['cameras', 'list', { filters: {} }]);
      expect(shouldDehydrateQuery(camerasListQuery)).toBe(true);

      // ['system', 'config', 'extra'] should match ['system', 'config']
      const systemConfigExtraQuery = createMockQuery(['system', 'config', 'extra']);
      expect(shouldDehydrateQuery(systemConfigExtraQuery)).toBe(true);
    });
  });
});
