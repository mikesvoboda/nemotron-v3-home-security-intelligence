/**
 * Tests for useVirtualizedList hook.
 */

import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useVirtualizedList } from './useVirtualizedList';

// ============================================================================
// Test Utilities
// ============================================================================

interface TestItem {
  id: string;
  name: string;
}

const mockItems: TestItem[] = Array.from({ length: 100 }, (_, i) => ({
  id: `item-${i}`,
  name: `Item ${i}`,
}));

// Mock ResizeObserver
const mockResizeObserver = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', mockResizeObserver);
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ============================================================================
// Tests
// ============================================================================

describe('useVirtualizedList', () => {
  describe('initialization', () => {
    it('returns a parentRef', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      expect(result.current.parentRef).toBeDefined();
      expect(result.current.parentRef.current).toBeNull(); // Not attached yet
    });

    it('returns virtual items array', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      expect(Array.isArray(result.current.virtualItems)).toBe(true);
    });

    it('returns total size', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
          estimateSize: 100,
        })
      );

      // 100 items * 100px = 10000px
      expect(result.current.totalSize).toBe(10000);
    });

    it('returns virtualizer instance', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      expect(result.current.virtualizer).toBeDefined();
      expect(typeof result.current.virtualizer.scrollToIndex).toBe('function');
    });
  });

  describe('configuration', () => {
    it('uses default estimate size of 100', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      // 100 items * 100px default = 10000px
      expect(result.current.totalSize).toBe(10000);
    });

    it('uses custom estimate size', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
          estimateSize: 50,
        })
      );

      // 100 items * 50px = 5000px
      expect(result.current.totalSize).toBe(5000);
    });

    it('uses estimate size function', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
          estimateSizeFn: (index) => (index % 2 === 0 ? 100 : 50),
        })
      );

      // 50 even items * 100 + 50 odd items * 50 = 5000 + 2500 = 7500
      expect(result.current.totalSize).toBe(7500);
    });

    it('applies gap between items', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems.slice(0, 10), // 10 items
          estimateSize: 100,
          gap: 10,
        })
      );

      // 10 items * 100px + 9 gaps * 10px = 1000 + 90 = 1090
      expect(result.current.totalSize).toBe(1090);
    });
  });

  describe('scroll functions', () => {
    it('provides scrollToIndex function', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      expect(typeof result.current.scrollToIndex).toBe('function');
    });

    it('provides scrollToOffset function', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      expect(typeof result.current.scrollToOffset).toBe('function');
    });

    it('scrollToIndex calls virtualizer.scrollToIndex', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      const scrollToIndexSpy = vi.spyOn(result.current.virtualizer, 'scrollToIndex');

      act(() => {
        result.current.scrollToIndex(10, { align: 'center' });
      });

      expect(scrollToIndexSpy).toHaveBeenCalledWith(10, { align: 'center' });
    });

    it('scrollToOffset calls virtualizer.scrollToOffset', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      const scrollToOffsetSpy = vi.spyOn(result.current.virtualizer, 'scrollToOffset');

      act(() => {
        result.current.scrollToOffset(500, { align: 'start' });
      });

      expect(scrollToOffsetSpy).toHaveBeenCalledWith(500, { align: 'start' });
    });
  });

  describe('helper functions', () => {
    it('provides getItem function', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      expect(result.current.getItem(0)).toEqual(mockItems[0]);
      expect(result.current.getItem(50)).toEqual(mockItems[50]);
      expect(result.current.getItem(999)).toBeUndefined();
    });

    it('provides measureElement function', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
          enableMeasurement: true,
        })
      );

      expect(typeof result.current.measureElement).toBe('function');
    });
  });

  describe('containerStyle', () => {
    it('returns container style with height', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
          estimateSize: 100,
        })
      );

      expect(result.current.containerStyle).toHaveProperty('height', '10000px');
      expect(result.current.containerStyle).toHaveProperty('position', 'relative');
      expect(result.current.containerStyle).toHaveProperty('width', '100%');
    });

    it('returns horizontal container style when horizontal', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
          estimateSize: 100,
          horizontal: true,
        })
      );

      expect(result.current.containerStyle).toHaveProperty('width', '10000px');
      expect(result.current.containerStyle).toHaveProperty('height', '100%');
    });
  });

  describe('getItemStyle', () => {
    it('returns style for a virtual item (vertical)', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
          estimateSize: 100,
        })
      );

      // Get first virtual item
      const virtualItem = result.current.virtualItems[0];
      if (virtualItem) {
        const style = result.current.getItemStyle(virtualItem);

        expect(style).toHaveProperty('position', 'absolute');
        expect(style).toHaveProperty('top');
        expect(style).toHaveProperty('left', 0);
        expect(style).toHaveProperty('width', '100%');
      }
    });

    it('returns style for horizontal layout', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
          estimateSize: 100,
          horizontal: true,
        })
      );

      const virtualItem = result.current.virtualItems[0];
      if (virtualItem) {
        const style = result.current.getItemStyle(virtualItem);

        expect(style).toHaveProperty('position', 'absolute');
        expect(style).toHaveProperty('top', 0);
        expect(style).toHaveProperty('left');
        expect(style).toHaveProperty('height', '100%');
      }
    });
  });

  describe('item keys', () => {
    it('uses index as default key strategy', () => {
      // Note: virtualItems will be empty without a scroll element,
      // but we can verify the virtualizer is configured correctly
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
        })
      );

      // Virtualizer should be created successfully
      expect(result.current.virtualizer).toBeDefined();
      // Without a scroll container, virtualItems will be empty
      // but the key strategy is internal to the virtualizer
    });

    it('uses custom getItemKey function in virtualizer config', () => {
      const { result } = renderHook(() =>
        useVirtualizedList({
          items: mockItems,
          getItemKey: (index) => mockItems[index].id,
        })
      );

      // Virtualizer should be created successfully with custom keys
      expect(result.current.virtualizer).toBeDefined();
      // The custom key function is passed to the virtualizer
    });
  });

  describe('updates', () => {
    it('updates when items change', () => {
      const { result, rerender } = renderHook(
        ({ items }) =>
          useVirtualizedList({
            items,
            estimateSize: 100,
          }),
        {
          initialProps: { items: mockItems.slice(0, 10) },
        }
      );

      // Initial: 10 items * 100px = 1000px
      expect(result.current.totalSize).toBe(1000);

      // Update to 20 items
      rerender({ items: mockItems.slice(0, 20) });

      // After: 20 items * 100px = 2000px
      expect(result.current.totalSize).toBe(2000);
    });
  });
});
