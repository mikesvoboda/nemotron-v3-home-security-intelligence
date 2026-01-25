/**
 * Tests for useDeferredFilter and useDeferredSearch hooks
 *
 * @module hooks/useDeferredFilter.test
 */

import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useDeferredFilter, useDeferredSearch } from './useDeferredFilter';

describe('useDeferredFilter', () => {
  // Sample data for testing
  const sampleItems = [
    { id: 1, name: 'Apple', category: 'fruit' },
    { id: 2, name: 'Banana', category: 'fruit' },
    { id: 3, name: 'Carrot', category: 'vegetable' },
    { id: 4, name: 'Date', category: 'fruit' },
    { id: 5, name: 'Eggplant', category: 'vegetable' },
  ];

  it('returns all items when filter is empty string', () => {
    const { result } = renderHook(() =>
      useDeferredFilter({
        items: sampleItems,
        filter: '',
        filterFn: (item, filter) => item.name.toLowerCase().includes(filter.toLowerCase()),
        skipDefer: true, // Skip defer for synchronous testing
      })
    );

    expect(result.current.filteredItems).toEqual(sampleItems);
    expect(result.current.filteredItems).toHaveLength(5);
  });

  it('returns all items when filter is null', () => {
    const { result } = renderHook(() =>
      useDeferredFilter({
        items: sampleItems,
        filter: null as unknown as string,
        filterFn: (item, filter) => item.name.toLowerCase().includes(filter?.toLowerCase() ?? ''),
        skipDefer: true,
      })
    );

    expect(result.current.filteredItems).toEqual(sampleItems);
  });

  it('filters items based on the filter function', () => {
    const { result } = renderHook(() =>
      useDeferredFilter({
        items: sampleItems,
        filter: 'a',
        filterFn: (item, filter) => item.name.toLowerCase().includes(filter.toLowerCase()),
        skipDefer: true,
      })
    );

    // Items containing 'a': Apple, Banana, Carrot, Date, Eggplant (all have 'a' except none here)
    // Actually: Apple (has a), Banana (has a), Carrot (has a), Date (has a), Eggplant (has a)
    expect(result.current.filteredItems).toHaveLength(5);
  });

  it('filters items with specific filter value', () => {
    const { result } = renderHook(() =>
      useDeferredFilter({
        items: sampleItems,
        filter: 'fruit',
        filterFn: (item, filter) => item.category === filter,
        skipDefer: true,
      })
    );

    expect(result.current.filteredItems).toHaveLength(3);
    expect(result.current.filteredItems.map((i) => i.name)).toEqual(['Apple', 'Banana', 'Date']);
  });

  it('returns empty array when no items match', () => {
    const { result } = renderHook(() =>
      useDeferredFilter({
        items: sampleItems,
        filter: 'xyz',
        filterFn: (item, filter) => item.name.toLowerCase().includes(filter.toLowerCase()),
        skipDefer: true,
      })
    );

    expect(result.current.filteredItems).toHaveLength(0);
  });

  it('updates filtered items when filter changes', () => {
    const { result, rerender } = renderHook(
      ({ filter }) =>
        useDeferredFilter({
          items: sampleItems,
          filter,
          filterFn: (item, f) => item.category === f,
          skipDefer: true,
        }),
      { initialProps: { filter: 'fruit' } }
    );

    expect(result.current.filteredItems).toHaveLength(3);

    rerender({ filter: 'vegetable' });

    expect(result.current.filteredItems).toHaveLength(2);
    expect(result.current.filteredItems.map((i) => i.name)).toEqual(['Carrot', 'Eggplant']);
  });

  it('updates filtered items when items change', () => {
    const initialItems = [{ id: 1, name: 'Apple', category: 'fruit' }];
    const updatedItems = [
      { id: 1, name: 'Apple', category: 'fruit' },
      { id: 2, name: 'Banana', category: 'fruit' },
    ];

    const { result, rerender } = renderHook(
      ({ items }) =>
        useDeferredFilter({
          items,
          filter: 'fruit',
          filterFn: (item, f) => item.category === f,
          skipDefer: true,
        }),
      { initialProps: { items: initialItems } }
    );

    expect(result.current.filteredItems).toHaveLength(1);

    rerender({ items: updatedItems });

    expect(result.current.filteredItems).toHaveLength(2);
  });

  it('respects deferThreshold for skipping defer on small lists', () => {
    const { result } = renderHook(() =>
      useDeferredFilter({
        items: sampleItems,
        filter: 'fruit',
        filterFn: (item, f) => item.category === f,
        deferThreshold: 10, // 5 items < 10 threshold, so no defer
      })
    );

    // Should work synchronously because list is below threshold
    expect(result.current.filteredItems).toHaveLength(3);
    expect(result.current.isStale).toBe(false);
  });

  it('handles complex filter objects', () => {
    interface ComplexFilter {
      category?: string;
      minId?: number;
    }

    const { result } = renderHook(() =>
      useDeferredFilter<(typeof sampleItems)[0], ComplexFilter>({
        items: sampleItems,
        filter: { category: 'fruit', minId: 2 },
        filterFn: (item, filter) => {
          if (filter.category && item.category !== filter.category) return false;
          if (filter.minId && item.id < filter.minId) return false;
          return true;
        },
        skipDefer: true,
      })
    );

    // Fruits with id >= 2: Banana (2), Date (4)
    expect(result.current.filteredItems).toHaveLength(2);
    expect(result.current.filteredItems.map((i) => i.name)).toEqual(['Banana', 'Date']);
  });
});

describe('useDeferredSearch', () => {
  const searchableItems = [
    { id: 1, title: 'React Hooks Guide', description: 'Learn about React hooks', author: 'John' },
    { id: 2, title: 'TypeScript Basics', description: 'Introduction to TS', author: 'Jane' },
    { id: 3, title: 'Advanced Patterns', description: 'React patterns for pros', author: 'John' },
    {
      id: 4,
      title: 'Testing Best Practices',
      description: 'How to test React apps',
      author: 'Bob',
    },
  ];

  it('returns all items when query is empty', () => {
    const { result } = renderHook(() =>
      useDeferredSearch({
        items: searchableItems,
        query: '',
        searchFields: (item) => [item.title, item.description, item.author],
        deferThreshold: 1000, // High threshold to skip defer
      })
    );

    expect(result.current.filteredItems).toHaveLength(4);
  });

  it('searches across multiple fields', () => {
    const { result } = renderHook(() =>
      useDeferredSearch({
        items: searchableItems,
        query: 'react',
        searchFields: (item) => [item.title, item.description, item.author],
        deferThreshold: 1000,
      })
    );

    // "React Hooks Guide", "Advanced Patterns" (description has "React"), "Testing Best Practices" (description has "React")
    expect(result.current.filteredItems.length).toBeGreaterThanOrEqual(1);
    expect(result.current.filteredItems.some((i) => i.title.toLowerCase().includes('react'))).toBe(
      true
    );
  });

  it('is case-insensitive by default', () => {
    const { result } = renderHook(() =>
      useDeferredSearch({
        items: searchableItems,
        query: 'REACT',
        searchFields: (item) => [item.title, item.description],
        deferThreshold: 1000,
      })
    );

    expect(result.current.filteredItems.length).toBeGreaterThanOrEqual(1);
  });

  it('supports case-sensitive search', () => {
    const { result } = renderHook(() =>
      useDeferredSearch({
        items: searchableItems,
        query: 'REACT', // Uppercase
        searchFields: (item) => [item.title, item.description],
        caseSensitive: true,
        deferThreshold: 1000,
      })
    );

    // No items have "REACT" in uppercase
    expect(result.current.filteredItems).toHaveLength(0);
  });

  it('handles null/undefined fields gracefully', () => {
    const itemsWithNulls = [
      { id: 1, title: 'Test', description: null },
      { id: 2, title: null, description: 'Some desc' },
      { id: 3, title: 'Another', description: undefined },
    ];

    const { result } = renderHook(() =>
      useDeferredSearch({
        items: itemsWithNulls,
        query: 'test',
        searchFields: (item) => [item.title, item.description as string | null],
        deferThreshold: 1000,
      })
    );

    expect(result.current.filteredItems).toHaveLength(1);
    expect(result.current.filteredItems[0].id).toBe(1);
  });

  it('searches by author name', () => {
    const { result } = renderHook(() =>
      useDeferredSearch({
        items: searchableItems,
        query: 'john',
        searchFields: (item) => [item.title, item.description, item.author],
        deferThreshold: 1000,
      })
    );

    // Items by John
    expect(result.current.filteredItems).toHaveLength(2);
    expect(result.current.filteredItems.every((i) => i.author === 'John')).toBe(true);
  });

  it('updates results when query changes', () => {
    const { result, rerender } = renderHook(
      ({ query }) =>
        useDeferredSearch({
          items: searchableItems,
          query,
          searchFields: (item) => [item.title, item.author],
          deferThreshold: 1000,
        }),
      { initialProps: { query: 'john' } }
    );

    expect(result.current.filteredItems).toHaveLength(2);

    rerender({ query: 'jane' });

    expect(result.current.filteredItems).toHaveLength(1);
    expect(result.current.filteredItems[0].author).toBe('Jane');
  });
});
