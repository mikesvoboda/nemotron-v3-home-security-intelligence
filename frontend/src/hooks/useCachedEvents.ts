/**
 * useCachedEvents hook
 *
 * Provides offline caching for security events using IndexedDB.
 * Useful for PWA offline support to show recent events when network is unavailable.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const DB_NAME = 'nemotron-security';
const DB_VERSION = 1;
const STORE_NAME = 'cached-events';

export interface CachedEvent {
  /** Unique event identifier */
  id: string;
  /** Camera ID that captured the event */
  camera_id: string;
  /** Risk score (0-100) */
  risk_score: number;
  /** Risk level category */
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  /** Event summary text */
  summary: string;
  /** Event timestamp (ISO 8601) */
  timestamp: string;
  /** When the event was cached locally (ISO 8601) */
  cachedAt: string;
}

export interface UseCachedEventsReturn {
  /** Array of cached events (sorted by timestamp, newest first) */
  cachedEvents: CachedEvent[];
  /** Number of cached events */
  cachedCount: number;
  /** True when IndexedDB has been initialized */
  isInitialized: boolean;
  /** Error message if IndexedDB operations fail */
  error: string | null;
  /** Cache a new event */
  cacheEvent: (event: CachedEvent) => Promise<void>;
  /** Load all cached events from IndexedDB */
  loadCachedEvents: () => Promise<void>;
  /** Remove a specific cached event by ID */
  removeCachedEvent: (id: string) => Promise<void>;
  /** Clear all cached events */
  clearCache: () => Promise<void>;
}

/**
 * Open or create the IndexedDB database
 */
function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => {
      reject(new Error('Failed to open IndexedDB'));
    };

    request.onsuccess = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      // Create object store if it doesn't exist
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        store.createIndex('timestamp', 'timestamp', { unique: false });
        store.createIndex('camera_id', 'camera_id', { unique: false });
      }
    };
  });
}

/**
 * Hook to manage offline event caching using IndexedDB.
 *
 * @example
 * ```tsx
 * const { cachedEvents, cachedCount, cacheEvent, clearCache } = useCachedEvents();
 *
 * // Cache a new event when offline
 * const handleNewEvent = async (event) => {
 *   if (!navigator.onLine) {
 *     await cacheEvent({
 *       ...event,
 *       cachedAt: new Date().toISOString(),
 *     });
 *   }
 * };
 *
 * // Display cached events while offline
 * if (!navigator.onLine && cachedCount > 0) {
 *   return <CachedEventsList events={cachedEvents} />;
 * }
 * ```
 */
export function useCachedEvents(): UseCachedEventsReturn {
  const [cachedEvents, setCachedEvents] = useState<CachedEvent[]>([]);
  const [isInitialized, setIsInitialized] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dbRef = useRef<IDBDatabase | null>(null);

  // Initialize the database
  useEffect(() => {
    let isMounted = true;

    const initDB = async () => {
      try {
        const db = await openDatabase();
        if (isMounted) {
          dbRef.current = db;
          setIsInitialized(true);
        } else {
          db.close();
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Failed to initialize IndexedDB');
        }
      }
    };

    void initDB();

    return () => {
      isMounted = false;
      if (dbRef.current) {
        dbRef.current.close();
        dbRef.current = null;
      }
    };
  }, []);

  /**
   * Load all cached events from IndexedDB
   */
  const loadCachedEvents = useCallback(async (): Promise<void> => {
    const db = dbRef.current;
    if (!db) {
      return;
    }

    return new Promise((resolve, reject) => {
      try {
        const transaction = db.transaction(STORE_NAME, 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.getAll();

        request.onsuccess = () => {
          const events = request.result as CachedEvent[];
          // Sort by timestamp, newest first
          events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
          setCachedEvents(events);
          resolve();
        };

        request.onerror = () => {
          setError('Failed to load cached events');
          reject(new Error('Failed to load cached events'));
        };
      } catch (err) {
        setError('Failed to load cached events');
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    });
  }, []);

  /**
   * Cache a new event to IndexedDB
   */
  const cacheEvent = useCallback(async (event: CachedEvent): Promise<void> => {
    const db = dbRef.current;
    if (!db) {
      return;
    }

    return new Promise((resolve, reject) => {
      try {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.put(event);

        request.onsuccess = () => {
          // Update local state
          setCachedEvents((prev) => {
            const filtered = prev.filter((e) => e.id !== event.id);
            const updated = [event, ...filtered];
            // Sort by timestamp, newest first
            updated.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
            return updated;
          });
          resolve();
        };

        request.onerror = () => {
          setError('Failed to cache event');
          reject(new Error('Failed to cache event'));
        };
      } catch (err) {
        setError('Failed to cache event');
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    });
  }, []);

  /**
   * Remove a cached event by ID
   */
  const removeCachedEvent = useCallback(async (id: string): Promise<void> => {
    const db = dbRef.current;
    if (!db) {
      return;
    }

    return new Promise((resolve, reject) => {
      try {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.delete(id);

        request.onsuccess = () => {
          setCachedEvents((prev) => prev.filter((e) => e.id !== id));
          resolve();
        };

        request.onerror = () => {
          setError('Failed to remove cached event');
          reject(new Error('Failed to remove cached event'));
        };
      } catch (err) {
        setError('Failed to remove cached event');
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    });
  }, []);

  /**
   * Clear all cached events
   */
  const clearCache = useCallback(async (): Promise<void> => {
    const db = dbRef.current;
    if (!db) {
      return;
    }

    return new Promise((resolve, reject) => {
      try {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.clear();

        request.onsuccess = () => {
          setCachedEvents([]);
          resolve();
        };

        request.onerror = () => {
          setError('Failed to clear cache');
          reject(new Error('Failed to clear cache'));
        };
      } catch (err) {
        setError('Failed to clear cache');
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    });
  }, []);

  return {
    cachedEvents,
    cachedCount: cachedEvents.length,
    isInitialized,
    error,
    cacheEvent,
    loadCachedEvents,
    removeCachedEvent,
    clearCache,
  };
}
