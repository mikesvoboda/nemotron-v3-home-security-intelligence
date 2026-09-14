/**
 * useBulkSelection - Generic hook for managing multi-select state across different components
 *
 * This hook provides a reusable pattern for bulk selection functionality
 * that can be used in EventTimeline, EntitiesPage, and other list views.
 *
 * Features:
 * - Toggle individual item selection
 * - Select all / deselect all
 * - Range selection with shift+click
 * - Keyboard shortcuts (Cmd/Ctrl+A for select all, Escape to clear)
 * - Persists selection across pagination (optional)
 *
 * @module hooks/useBulkSelection
 * NEM-3615: Add bulk actions to EventTimeline and EntitiesPage
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

/**
 * Configuration options for useBulkSelection hook
 */
export interface UseBulkSelectionOptions<T> {
  /** Function to get the unique ID from an item */
  getId: (item: T) => number | string;
  /** Maximum number of items that can be selected (default: unlimited) */
  maxSelection?: number;
  /** Whether to persist selection across pagination changes (default: false) */
  persistAcrossPagination?: boolean;
  /** Callback when selection changes */
  onSelectionChange?: (selectedIds: Set<number | string>) => void;
  /** Enable keyboard shortcuts (default: true) */
  enableKeyboardShortcuts?: boolean;
}

/**
 * Return type for useBulkSelection hook
 */
export interface UseBulkSelectionReturn<T> {
  /** Set of currently selected item IDs */
  selectedIds: Set<number | string>;
  /** Number of items currently selected */
  selectedCount: number;
  /** Whether all visible items are selected */
  isAllSelected: boolean;
  /** Whether some but not all visible items are selected */
  isPartiallySelected: boolean;
  /** Check if a specific item is selected */
  isSelected: (item: T) => boolean;
  /** Toggle selection for a single item */
  toggleSelection: (item: T, event?: React.MouseEvent) => void;
  /** Select a single item */
  select: (item: T) => void;
  /** Deselect a single item */
  deselect: (item: T) => void;
  /** Select all visible items */
  selectAll: (items: T[]) => void;
  /** Deselect all items */
  deselectAll: () => void;
  /** Toggle select all / deselect all */
  toggleSelectAll: (items: T[]) => void;
  /** Select a range of items (for shift+click) */
  selectRange: (items: T[], fromItem: T, toItem: T) => void;
  /** Clear selection when items change (e.g., pagination) */
  clearSelection: () => void;
  /** Get array of selected IDs */
  getSelectedIds: () => (number | string)[];
}

/**
 * Generic hook for managing multi-select state.
 *
 * @param options - Configuration options
 * @returns Selection state and functions
 *
 * @example
 * ```tsx
 * function EventList({ events }: { events: Event[] }) {
 *   const {
 *     selectedIds,
 *     isSelected,
 *     toggleSelection,
 *     selectAll,
 *     deselectAll,
 *     isAllSelected,
 *   } = useBulkSelection({
 *     getId: (event) => event.id,
 *     onSelectionChange: (ids) => console.log('Selected:', ids.size),
 *   });
 *
 *   return (
 *     <>
 *       <button onClick={() => isAllSelected ? deselectAll() : selectAll(events)}>
 *         {isAllSelected ? 'Deselect All' : 'Select All'}
 *       </button>
 *       {events.map((event) => (
 *         <EventCard
 *           key={event.id}
 *           event={event}
 *           selected={isSelected(event)}
 *           onSelect={() => toggleSelection(event)}
 *         />
 *       ))}
 *     </>
 *   );
 * }
 * ```
 */
export function useBulkSelection<T>(
  options: UseBulkSelectionOptions<T>
): UseBulkSelectionReturn<T> {
  const {
    getId,
    maxSelection,
    persistAcrossPagination = false,
    onSelectionChange,
    enableKeyboardShortcuts = true,
  } = options;

  // Track selected IDs
  const [selectedIds, setSelectedIds] = useState<Set<number | string>>(new Set());

  // Track last selected item for range selection
  const [lastSelectedItem, setLastSelectedItem] = useState<T | null>(null);

  // Track visible items for select all calculations
  const [visibleItems, setVisibleItems] = useState<T[]>([]);

  // Computed values
  const selectedCount = selectedIds.size;

  const isAllSelected = useMemo(() => {
    if (visibleItems.length === 0) return false;
    return visibleItems.every((item) => selectedIds.has(getId(item)));
  }, [selectedIds, visibleItems, getId]);

  const isPartiallySelected = useMemo(() => {
    if (visibleItems.length === 0) return false;
    const selectedVisible = visibleItems.filter((item) => selectedIds.has(getId(item)));
    return selectedVisible.length > 0 && selectedVisible.length < visibleItems.length;
  }, [selectedIds, visibleItems, getId]);

  // Notify on selection change
  useEffect(() => {
    onSelectionChange?.(selectedIds);
  }, [selectedIds, onSelectionChange]);

  // Check if item is selected
  const isSelected = useCallback(
    (item: T): boolean => {
      return selectedIds.has(getId(item));
    },
    [selectedIds, getId]
  );

  // Select a single item
  const select = useCallback(
    (item: T): void => {
      const id = getId(item);
      setSelectedIds((prev) => {
        if (maxSelection && prev.size >= maxSelection && !prev.has(id)) {
          return prev; // Don't add if at max
        }
        const next = new Set(prev);
        next.add(id);
        return next;
      });
      setLastSelectedItem(item);
    },
    [getId, maxSelection]
  );

  // Deselect a single item
  const deselect = useCallback(
    (item: T): void => {
      const id = getId(item);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    },
    [getId]
  );

  // Toggle selection for a single item
  const toggleSelection = useCallback(
    (item: T, event?: React.MouseEvent): void => {
      const id = getId(item);

      // Handle shift+click for range selection
      if (event?.shiftKey && lastSelectedItem && visibleItems.length > 0) {
        const fromIndex = visibleItems.findIndex((i) => getId(i) === getId(lastSelectedItem));
        const toIndex = visibleItems.findIndex((i) => getId(i) === id);

        if (fromIndex !== -1 && toIndex !== -1) {
          const start = Math.min(fromIndex, toIndex);
          const end = Math.max(fromIndex, toIndex);
          const rangeItems = visibleItems.slice(start, end + 1);

          setSelectedIds((prev) => {
            const next = new Set(prev);
            rangeItems.forEach((rangeItem) => {
              const rangeId = getId(rangeItem);
              if (!maxSelection || next.size < maxSelection || next.has(rangeId)) {
                next.add(rangeId);
              }
            });
            return next;
          });
          return;
        }
      }

      // Regular toggle
      if (selectedIds.has(id)) {
        deselect(item);
      } else {
        select(item);
      }
    },
    [getId, selectedIds, deselect, select, lastSelectedItem, visibleItems, maxSelection]
  );

  // Select all visible items
  const selectAll = useCallback(
    (items: T[]): void => {
      setVisibleItems(items);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        items.forEach((item) => {
          const id = getId(item);
          if (!maxSelection || next.size < maxSelection) {
            next.add(id);
          }
        });
        return next;
      });
    },
    [getId, maxSelection]
  );

  // Deselect all items
  const deselectAll = useCallback((): void => {
    setSelectedIds(new Set());
    setLastSelectedItem(null);
  }, []);

  // Toggle select all / deselect all
  const toggleSelectAll = useCallback(
    (items: T[]): void => {
      setVisibleItems(items);
      if (isAllSelected) {
        deselectAll();
      } else {
        selectAll(items);
      }
    },
    [isAllSelected, selectAll, deselectAll]
  );

  // Select a range of items (for programmatic range selection)
  const selectRange = useCallback(
    (items: T[], fromItem: T, toItem: T): void => {
      const fromIndex = items.findIndex((i) => getId(i) === getId(fromItem));
      const toIndex = items.findIndex((i) => getId(i) === getId(toItem));

      if (fromIndex === -1 || toIndex === -1) return;

      const start = Math.min(fromIndex, toIndex);
      const end = Math.max(fromIndex, toIndex);
      const rangeItems = items.slice(start, end + 1);

      setSelectedIds((prev) => {
        const next = new Set(prev);
        rangeItems.forEach((item) => {
          const id = getId(item);
          if (!maxSelection || next.size < maxSelection) {
            next.add(id);
          }
        });
        return next;
      });
    },
    [getId, maxSelection]
  );

  // Clear selection (useful for pagination changes)
  const clearSelection = useCallback((): void => {
    if (!persistAcrossPagination) {
      setSelectedIds(new Set());
      setLastSelectedItem(null);
    }
  }, [persistAcrossPagination]);

  // Get array of selected IDs
  const getSelectedIds = useCallback((): (number | string)[] => {
    return Array.from(selectedIds);
  }, [selectedIds]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!enableKeyboardShortcuts) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      // Cmd/Ctrl+A to select all (only if input/textarea not focused)
      if (
        (event.metaKey || event.ctrlKey) &&
        event.key === 'a' &&
        !['INPUT', 'TEXTAREA'].includes((event.target as Element).tagName)
      ) {
        event.preventDefault();
        if (visibleItems.length > 0) {
          selectAll(visibleItems);
        }
      }

      // Escape to clear selection
      if (event.key === 'Escape' && selectedIds.size > 0) {
        deselectAll();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [enableKeyboardShortcuts, visibleItems, selectedIds, selectAll, deselectAll]);

  // Effect to track visible items - call this from component
  useEffect(() => {
    // Clear selection on unmount if not persisting
    return () => {
      if (!persistAcrossPagination) {
        setSelectedIds(new Set());
      }
    };
  }, [persistAcrossPagination]);

  return {
    selectedIds,
    selectedCount,
    isAllSelected,
    isPartiallySelected,
    isSelected,
    toggleSelection,
    select,
    deselect,
    selectAll,
    deselectAll,
    toggleSelectAll,
    selectRange,
    clearSelection,
    getSelectedIds,
  };
}

export default useBulkSelection;
