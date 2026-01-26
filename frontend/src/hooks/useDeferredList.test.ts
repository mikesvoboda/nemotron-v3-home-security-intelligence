/**
 * Tests for useDeferredList hook
 *
 * @module hooks/useDeferredList.test
 */

import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useDeferredList } from './useDeferredList';

describe('useDeferredList', () => {
  // Sample data for testing
  const generateItems = (count: number) =>
    Array.from({ length: count }, (_, i) => ({
      id: i + 1,
      name: `Item ${i + 1}`,
      value: Math.random() * 100,
    }));

  describe('basic functionality', () => {
    it('returns all items when list is small (below threshold)', () => {
      const items = generateItems(10);

      const { result } = renderHook(() =>
        useDeferredList({
          items,
          deferThreshold: 50,
        })
      );

      expect(result.current.deferredItems).toEqual(items);
      expect(result.current.displayCount).toBe(10);
      expect(result.current.totalCount).toBe(10);
      expect(result.current.isStale).toBe(false);
    });

    it('returns items immediately when skipDefer is true', () => {
      const items = generateItems(100);

      const { result } = renderHook(() =>
        useDeferredList({
          items,
          skipDefer: true,
        })
      );

      expect(result.current.deferredItems).toEqual(items);
      expect(result.current.isStale).toBe(false);
    });

    it('uses default threshold of 50', () => {
      const smallList = generateItems(30);

      const { result: smallResult } = renderHook(() =>
        useDeferredList({
          items: smallList,
        })
      );

      // Small list should not be deferred
      expect(smallResult.current.deferredItems).toEqual(smallList);
      expect(smallResult.current.isStale).toBe(false);
    });

    it('handles empty list', () => {
      const { result } = renderHook(() =>
        useDeferredList({
          items: [],
        })
      );

      expect(result.current.deferredItems).toEqual([]);
      expect(result.current.displayCount).toBe(0);
      expect(result.current.totalCount).toBe(0);
      expect(result.current.isStale).toBe(false);
    });
  });

  describe('threshold behavior', () => {
    it('does not defer when items count equals threshold - 1', () => {
      const items = generateItems(49);

      const { result } = renderHook(() =>
        useDeferredList({
          items,
          deferThreshold: 50,
        })
      );

      expect(result.current.deferredItems).toEqual(items);
      expect(result.current.isStale).toBe(false);
    });

    it('starts deferring when items count equals threshold', () => {
      const items = generateItems(50);

      const { result } = renderHook(() =>
        useDeferredList({
          items,
          deferThreshold: 50,
        })
      );

      // Initially, deferred items should match items (synchronous on first render)
      expect(result.current.deferredItems).toHaveLength(50);
    });

    it('respects custom threshold', () => {
      const items = generateItems(25);

      const { result } = renderHook(() =>
        useDeferredList({
          items,
          deferThreshold: 20,
        })
      );

      // With threshold of 20, 25 items should trigger deferring
      expect(result.current.deferredItems).toHaveLength(25);
    });
  });

  describe('updates', () => {
    it('updates deferred items when items change', () => {
      const initialItems = generateItems(10);
      const updatedItems = generateItems(15);

      const { result, rerender } = renderHook(
        ({ items }) =>
          useDeferredList({
            items,
            deferThreshold: 50,
          }),
        { initialProps: { items: initialItems } }
      );

      expect(result.current.deferredItems).toHaveLength(10);

      rerender({ items: updatedItems });

      expect(result.current.deferredItems).toHaveLength(15);
      expect(result.current.totalCount).toBe(15);
    });

    it('maintains item order', () => {
      const items = [
        { id: 3, name: 'C' },
        { id: 1, name: 'A' },
        { id: 2, name: 'B' },
      ];

      const { result } = renderHook(() =>
        useDeferredList({
          items,
          skipDefer: true,
        })
      );

      expect(result.current.deferredItems).toEqual([
        { id: 3, name: 'C' },
        { id: 1, name: 'A' },
        { id: 2, name: 'B' },
      ]);
    });
  });

  describe('type safety', () => {
    it('preserves item types', () => {
      interface CustomItem {
        id: number;
        metadata: {
          category: string;
          priority: number;
        };
      }

      const items: CustomItem[] = [
        { id: 1, metadata: { category: 'A', priority: 1 } },
        { id: 2, metadata: { category: 'B', priority: 2 } },
      ];

      const { result } = renderHook(() =>
        useDeferredList<CustomItem>({
          items,
          skipDefer: true,
        })
      );

      // Type should be preserved
      const firstItem = result.current.deferredItems[0];
      expect(firstItem.metadata.category).toBe('A');
      expect(firstItem.metadata.priority).toBe(1);
    });
  });

  describe('count tracking', () => {
    it('tracks display count and total count', () => {
      const items = generateItems(30);

      const { result } = renderHook(() =>
        useDeferredList({
          items,
          deferThreshold: 50, // Below threshold
        })
      );

      expect(result.current.displayCount).toBe(30);
      expect(result.current.totalCount).toBe(30);
    });

    it('updates counts when items change', () => {
      const initialItems = generateItems(20);

      const { result, rerender } = renderHook(
        ({ items }) =>
          useDeferredList({
            items,
            skipDefer: true,
          }),
        { initialProps: { items: initialItems } }
      );

      expect(result.current.displayCount).toBe(20);

      const newItems = generateItems(40);
      rerender({ items: newItems });

      expect(result.current.displayCount).toBe(40);
      expect(result.current.totalCount).toBe(40);
    });
  });
});
