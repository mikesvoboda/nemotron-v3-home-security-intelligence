/**
 * useLocalStorage - Hook for persisting state in localStorage
 *
 * Provides a useState-like API with automatic persistence to localStorage.
 * Handles SSR safely by checking for window availability.
 *
 * Instances that share a `key` share a value. This is the part that F-020
 * used to get wrong, and it has TWO separate reasons, which is why the fix is
 * in this file rather than in one component:
 *
 * 1. The browser will not tell us. A `storage` event fires only at OTHER
 *    documents — never at the one that called `setItem` — so a second
 *    `useLocalStorage('same-key')` mounted in the SAME tab is never notified
 *    by the platform. `useSavedSearches` already subscribes to `storage` for
 *    the cross-TAB half; that subscription is useless for same-tab siblings.
 *    So writes are announced here, through the module-level registry below.
 * 2. Each instance used to keep its own copy as the source of truth: the
 *    `useState` initializer read the jar once, and `setValue` computed
 *    functional updates from that instance's own `storedValue` closure. A
 *    sibling's write was therefore not merely late — a functional update
 *    could be computed from a value the sibling had already replaced.
 *
 * Now the jar is the single source of truth: a notification re-reads it, and
 * functional updates read the instance's CURRENT value through a ref instead
 * of a captured one. Same-tab and cross-tab converge without a remount.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Live notifiers per storage key, so a write in this document can announce
 * itself to the sibling hook instances that the browser stays silent about.
 * Module-level (not component state) because the set of subscribers spans
 * every component tree in the tab.
 */
type Notifier = () => void;
const subscribers = new Map<string, Set<Notifier>>();

function subscribe(key: string, notify: Notifier): () => void {
  let set = subscribers.get(key);
  if (!set) {
    set = new Set();
    subscribers.set(key, set);
  }
  set.add(notify);
  return () => {
    set?.delete(notify);
    if (set?.size === 0) subscribers.delete(key);
  };
}

/** Tell every subscriber for `key` except the writer to re-read the jar. */
function announce(key: string, from: Notifier): void {
  const set = subscribers.get(key);
  if (!set) return;
  for (const notify of set) {
    if (notify !== from) notify();
  }
}

/**
 * Custom hook that persists state in localStorage
 *
 * @param key - The localStorage key to use
 * @param initialValue - The initial value if no stored value exists
 * @returns A tuple of [value, setValue] similar to useState
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((prevValue: T) => T)) => void] {
  // Get stored value or use initial value.
  //
  // `initialValue` is held in a ref rather than listed as a dependency: a
  // caller that passes a fresh literal (`useLocalStorage(k, { n: 0 })`) would
  // otherwise change this callback's identity on every render, which re-runs
  // the subscription effect below every render — a re-subscribe plus a state
  // write per render. The ref is read at call time, so a later `key` change
  // still sees the current `initialValue`.
  const initialValueRef = useRef(initialValue);
  initialValueRef.current = initialValue;

  const readValue = useCallback((): T => {
    // Check if we're in a browser environment
    if (typeof window === 'undefined') {
      return initialValueRef.current;
    }

    try {
      const item = window.localStorage.getItem(key);
      return item ? (JSON.parse(item) as T) : initialValueRef.current;
    } catch (error) {
      console.warn(`Error reading localStorage key "${key}":`, error);
      return initialValueRef.current;
    }
  }, [key]);

  // State to store our value
  const [storedValue, setStoredValue] = useState<T>(readValue);

  // The jar re-read, pushed into this instance's state. Used for our own
  // writes' siblings, for `storage`, and for the mount sync.
  const reread = useCallback(() => {
    setStoredValue(readValue());
  }, [readValue]);

  // This instance's identity in the registry. Stable, so `announce` can skip
  // it and let the writer keep the state it already set.
  const notifySelf = useRef<Notifier>(reread);
  notifySelf.current = reread;
  const notifier = useRef<Notifier>(() => notifySelf.current());

  // Keep this instance honest: register with the shared registry, sync to the
  // jar as it stands at mount (covers anything written between render and
  // effect), and follow OTHER documents on the same key.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const unsubscribe = subscribe(key, notifier.current);
    reread();
    const onStorage = (event: StorageEvent) => {
      // `key === null` is a clear() from another document: re-read everything.
      if (event.key === null || event.key === key) reread();
    };
    window.addEventListener('storage', onStorage);
    return () => {
      unsubscribe();
      window.removeEventListener('storage', onStorage);
    };
  }, [key, reread]);

  // Current value for functional updates, so a write is applied to what the
  // jar holds NOW rather than to this instance's captured copy.
  const valueRef = useRef(storedValue);
  valueRef.current = storedValue;

  // Return a wrapped version of useState's setter function that persists to
  // localStorage and announces the change to sibling instances in this tab.
  const setValue = useCallback(
    (value: T | ((prevValue: T) => T)) => {
      try {
        // Same API as useState. `instanceof Function` narrows the union itself;
        // eslint rejects an assertion layered on top of it.
        const valueToStore = value instanceof Function ? value(valueRef.current) : value;

        // Save to state
        setStoredValue(valueToStore);
        // ...and keep the ref authoritative for an immediately-following
        // functional update, before the re-render lands.
        valueRef.current = valueToStore;

        // Save to localStorage
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(key, JSON.stringify(valueToStore));
        }

        // The browser fires `storage` at other DOCUMENTS only; this tab's own
        // sibling instances get told here (file header).
        announce(key, notifier.current);
      } catch (error) {
        console.warn(`Error setting localStorage key "${key}":`, error);
      }
    },
    [key]
  );

  return [storedValue, setValue];
}

export default useLocalStorage;
