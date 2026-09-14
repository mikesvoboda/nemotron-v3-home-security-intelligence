/**
 * Tests for useBulkSelection hook
 * NEM-3615: Add bulk actions to EventTimeline and EntitiesPage
 */

import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useBulkSelection } from './useBulkSelection';

// Test data types
interface TestItem {
  id: number;
  name: string;
}

// Helper to create test items
const createTestItems = (count: number): TestItem[] => {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    name: `Item ${i + 1}`,
  }));
};

describe('useBulkSelection', () => {
  describe('basic selection', () => {
    it('should initialize with empty selection', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      expect(result.current.selectedCount).toBe(0);
      expect(result.current.selectedIds.size).toBe(0);
      expect(result.current.isAllSelected).toBe(false);
      expect(result.current.isPartiallySelected).toBe(false);
    });

    it('should select a single item', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      const item = { id: 1, name: 'Test' };

      act(() => {
        result.current.select(item);
      });

      expect(result.current.selectedCount).toBe(1);
      expect(result.current.isSelected(item)).toBe(true);
    });

    it('should deselect a single item', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      const item = { id: 1, name: 'Test' };

      act(() => {
        result.current.select(item);
        result.current.deselect(item);
      });

      expect(result.current.selectedCount).toBe(0);
      expect(result.current.isSelected(item)).toBe(false);
    });

    it('should toggle selection', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      const item = { id: 1, name: 'Test' };

      // Toggle on
      act(() => {
        result.current.toggleSelection(item);
      });
      expect(result.current.isSelected(item)).toBe(true);

      // Toggle off
      act(() => {
        result.current.toggleSelection(item);
      });
      expect(result.current.isSelected(item)).toBe(false);
    });
  });

  describe('select all / deselect all', () => {
    it('should select all items', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      const items = createTestItems(5);

      act(() => {
        result.current.selectAll(items);
      });

      expect(result.current.selectedCount).toBe(5);
      expect(result.current.isAllSelected).toBe(true);
      items.forEach((item) => {
        expect(result.current.isSelected(item)).toBe(true);
      });
    });

    it('should deselect all items', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      const items = createTestItems(5);

      act(() => {
        result.current.selectAll(items);
        result.current.deselectAll();
      });

      expect(result.current.selectedCount).toBe(0);
      expect(result.current.isAllSelected).toBe(false);
    });

    it('should toggle select all', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      const items = createTestItems(3);

      // First toggle: select all
      act(() => {
        result.current.toggleSelectAll(items);
      });
      expect(result.current.isAllSelected).toBe(true);

      // Second toggle: deselect all
      act(() => {
        result.current.toggleSelectAll(items);
      });
      expect(result.current.selectedCount).toBe(0);
    });
  });

  describe('partial selection', () => {
    it('should detect partial selection', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      const items = createTestItems(5);

      // Select only some items
      act(() => {
        result.current.selectAll(items); // First set visible items
        result.current.deselectAll();
        result.current.select(items[0]);
        result.current.select(items[1]);
      });

      expect(result.current.isPartiallySelected).toBe(true);
      expect(result.current.isAllSelected).toBe(false);
    });
  });

  describe('max selection', () => {
    it('should respect max selection limit', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
          maxSelection: 2,
        })
      );

      const items = createTestItems(5);

      act(() => {
        result.current.select(items[0]);
        result.current.select(items[1]);
        result.current.select(items[2]); // Should be ignored
      });

      expect(result.current.selectedCount).toBe(2);
      expect(result.current.isSelected(items[0])).toBe(true);
      expect(result.current.isSelected(items[1])).toBe(true);
      expect(result.current.isSelected(items[2])).toBe(false);
    });

    it('should respect max selection in selectAll', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
          maxSelection: 3,
        })
      );

      const items = createTestItems(10);

      act(() => {
        result.current.selectAll(items);
      });

      expect(result.current.selectedCount).toBe(3);
    });
  });

  describe('selection change callback', () => {
    it('should call onSelectionChange when selection changes', () => {
      const onSelectionChange = vi.fn();

      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
          onSelectionChange,
        })
      );

      const item = { id: 1, name: 'Test' };

      act(() => {
        result.current.select(item);
      });

      // Should be called with the updated selection
      expect(onSelectionChange).toHaveBeenCalled();
      const lastCall = onSelectionChange.mock.calls[onSelectionChange.mock.calls.length - 1];
      expect(lastCall[0].has(1)).toBe(true);
    });
  });

  describe('getSelectedIds', () => {
    it('should return array of selected IDs', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      const items = createTestItems(3);

      act(() => {
        result.current.select(items[0]);
        result.current.select(items[2]);
      });

      const selectedIds = result.current.getSelectedIds();
      expect(selectedIds).toHaveLength(2);
      expect(selectedIds).toContain(1);
      expect(selectedIds).toContain(3);
    });
  });

  describe('clear selection', () => {
    it('should clear selection when clearSelection is called', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
        })
      );

      const items = createTestItems(3);

      act(() => {
        result.current.selectAll(items);
        result.current.clearSelection();
      });

      expect(result.current.selectedCount).toBe(0);
    });

    it('should preserve selection with persistAcrossPagination', () => {
      const { result } = renderHook(() =>
        useBulkSelection<TestItem>({
          getId: (item) => item.id,
          persistAcrossPagination: true,
        })
      );

      const items = createTestItems(3);

      act(() => {
        result.current.selectAll(items);
        result.current.clearSelection();
      });

      // Selection should be preserved
      expect(result.current.selectedCount).toBe(3);
    });
  });

  describe('string IDs', () => {
    interface StringIdItem {
      id: string;
      name: string;
    }

    it('should work with string IDs', () => {
      const { result } = renderHook(() =>
        useBulkSelection<StringIdItem>({
          getId: (item) => item.id,
        })
      );

      const item = { id: 'abc-123', name: 'Test' };

      act(() => {
        result.current.select(item);
      });

      expect(result.current.isSelected(item)).toBe(true);
      expect(result.current.getSelectedIds()).toContain('abc-123');
    });
  });
});
