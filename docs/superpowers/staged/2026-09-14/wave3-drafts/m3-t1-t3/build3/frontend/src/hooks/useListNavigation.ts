/**
 * useListNavigation - j/k style list navigation
 *
 * Provides keyboard navigation for lists:
 * - j/ArrowDown: Move down (increase index)
 * - k/ArrowUp: Move up (decrease index)
 * - Home: Jump to first item
 * - End: Jump to last item
 * - Enter: Select current item
 *
 * Automatically ignores shortcuts when typing in input fields.
 */

import { useCallback, useEffect, useState, useRef } from 'react';

/**
 * Options for the useListNavigation hook
 */
export interface UseListNavigationOptions {
  /** Total number of items in the list */
  itemCount: number;
  /** Initial selected index (default: 0) */
  initialIndex?: number;
  /** Whether to wrap around at list boundaries (default: false) */
  wrap?: boolean;
  /** Callback when Enter is pressed on a selected item */
  onSelect?: (index: number) => void;
  /** Whether keyboard navigation is enabled (default: true) */
  enabled?: boolean;
}

/**
 * Return type for the useListNavigation hook
 */
export interface UseListNavigationReturn {
  /** Currently selected index (-1 if list is empty) */
  selectedIndex: number;
  /** Set the selected index programmatically */
  setSelectedIndex: (index: number) => void;
  /** Reset selection to initial index */
  resetSelection: () => void;
}

/**
 * Check if the event target is an editable element
 */
function isEditableElement(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) {
    return false;
  }

  const tagName = target.tagName.toLowerCase();
  if (tagName === 'input' || tagName === 'textarea') {
    return true;
  }

  if (target.contentEditable === 'true') {
    return true;
  }

  return false;
}

/**
 * Clamp a value between min and max
 */
function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Hook providing keyboard navigation for lists
 *
 * @param options - Configuration options
 * @returns Object containing navigation state and controls
 */
export function useListNavigation(options: UseListNavigationOptions): UseListNavigationReturn {
  const { itemCount, initialIndex = 0, wrap = false, onSelect, enabled = true } = options;

  // Calculate the initial index based on itemCount
  const getValidIndex = useCallback(
    (index: number): number => {
      if (itemCount === 0) return -1;
      return clamp(index, 0, itemCount - 1);
    },
    [itemCount]
  );

  const [selectedIndex, setSelectedIndexState] = useState(() => getValidIndex(initialIndex));

  // Store initial index for reset
  const initialIndexRef = useRef(initialIndex);

  // Store callbacks in refs to avoid stale closures
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  // Adjust index when itemCount changes
  useEffect(() => {
    setSelectedIndexState((current) => getValidIndex(current));
  }, [itemCount, getValidIndex]);

  const setSelectedIndex = useCallback(
    (index: number) => {
      setSelectedIndexState(getValidIndex(index));
    },
    [getValidIndex]
  );

  const resetSelection = useCallback(() => {
    setSelectedIndexState(getValidIndex(initialIndexRef.current));
  }, [getValidIndex]);

  const moveUp = useCallback(() => {
    if (itemCount === 0) return;

    setSelectedIndexState((current) => {
      if (current <= 0) {
        return wrap ? itemCount - 1 : 0;
      }
      return current - 1;
    });
  }, [itemCount, wrap]);

  const moveDown = useCallback(() => {
    if (itemCount === 0) return;

    setSelectedIndexState((current) => {
      if (current >= itemCount - 1) {
        return wrap ? 0 : itemCount - 1;
      }
      return current + 1;
    });
  }, [itemCount, wrap]);

  const jumpToFirst = useCallback(() => {
    if (itemCount === 0) return;
    setSelectedIndexState(0);
  }, [itemCount]);

  const jumpToLast = useCallback(() => {
    if (itemCount === 0) return;
    setSelectedIndexState(itemCount - 1);
  }, [itemCount]);

  const selectCurrent = useCallback(() => {
    if (selectedIndex >= 0) {
      onSelectRef.current?.(selectedIndex);
    }
  }, [selectedIndex]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) {
        return;
      }

      // Ignore when typing in input fields
      if (isEditableElement(event.target)) {
        return;
      }

      const { key } = event;

      switch (key) {
        case 'j':
        case 'ArrowDown':
          event.preventDefault();
          moveDown();
          break;

        case 'k':
        case 'ArrowUp':
          event.preventDefault();
          moveUp();
          break;

        case 'Home':
          event.preventDefault();
          jumpToFirst();
          break;

        case 'End':
          event.preventDefault();
          jumpToLast();
          break;

        case 'Enter':
          event.preventDefault();
          selectCurrent();
          break;
      }
    },
    [enabled, moveDown, moveUp, jumpToFirst, jumpToLast, selectCurrent]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);

  return {
    selectedIndex,
    setSelectedIndex,
    resetSelection,
  };
}

export default useListNavigation;
