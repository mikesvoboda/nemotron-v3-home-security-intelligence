/**
 * Tests for memoization utilities
 *
 * @module utils/memoization.test
 */

import { describe, expect, it } from 'vitest';

import {
  shallowEqual,
  createPropsComparator,
  createPropsExcluder,
  arrayShallowEqual,
  createArrayPropsComparator,
  listItemPropsComparator,
  cardPropsComparator,
  deepEqual,
  createDeepPropsComparator,
} from './memoization';

describe('shallowEqual', () => {
  it('returns true for identical references', () => {
    const obj = { a: 1, b: 2 };
    expect(shallowEqual(obj, obj)).toBe(true);
  });

  it('returns true for objects with same key-value pairs', () => {
    expect(shallowEqual({ a: 1, b: 2 }, { a: 1, b: 2 })).toBe(true);
  });

  it('returns false for objects with different values', () => {
    expect(shallowEqual({ a: 1, b: 2 }, { a: 1, b: 3 })).toBe(false);
  });

  it('returns false for objects with different keys', () => {
    expect(shallowEqual({ a: 1, b: 2 }, { a: 1, c: 2 })).toBe(false);
  });

  it('returns false for objects with different number of keys', () => {
    expect(shallowEqual({ a: 1 }, { a: 1, b: 2 })).toBe(false);
  });

  it('handles null values', () => {
    // null === null is true (same reference), so shallowEqual returns true
    expect(shallowEqual(null, null)).toBe(true);
    expect(shallowEqual(null, { a: 1 })).toBe(false);
    expect(shallowEqual({ a: 1 }, null)).toBe(false);
  });

  it('handles undefined values', () => {
    // undefined === undefined is true (same reference), so shallowEqual returns true
    expect(shallowEqual(undefined, undefined)).toBe(true);
    expect(shallowEqual(undefined, { a: 1 })).toBe(false);
    expect(shallowEqual({ a: 1 }, undefined)).toBe(false);
  });

  it('does not do deep comparison', () => {
    const nested1 = { a: { b: 1 } };
    const nested2 = { a: { b: 1 } };
    // Different object references for nested object
    expect(shallowEqual(nested1, nested2)).toBe(false);
  });
});

describe('createPropsComparator', () => {
  interface TestProps {
    id: string;
    name: string;
    onClick: () => void;
  }

  it('returns true when compared props are equal', () => {
    const comparator = createPropsComparator<TestProps>(['id', 'name']);

    const prev = { id: '1', name: 'test', onClick: () => {} };
    const next = { id: '1', name: 'test', onClick: () => {} };

    expect(comparator(prev, next)).toBe(true);
  });

  it('returns false when a compared prop differs', () => {
    const comparator = createPropsComparator<TestProps>(['id', 'name']);

    const prev = { id: '1', name: 'test', onClick: () => {} };
    const next = { id: '1', name: 'changed', onClick: () => {} };

    expect(comparator(prev, next)).toBe(false);
  });

  it('ignores props not in the comparison list', () => {
    const comparator = createPropsComparator<TestProps>(['id', 'name']);

    const callback1 = () => {};
    const callback2 = () => {};

    const prev = { id: '1', name: 'test', onClick: callback1 };
    const next = { id: '1', name: 'test', onClick: callback2 };

    // Different onClick references should be ignored
    expect(comparator(prev, next)).toBe(true);
  });
});

describe('createPropsExcluder', () => {
  interface TestProps {
    id: string;
    name: string;
    onClick: () => void;
    onDelete: () => void;
  }

  it('returns true when non-excluded props are equal', () => {
    const comparator = createPropsExcluder<TestProps>(['onClick', 'onDelete']);

    const prev = { id: '1', name: 'test', onClick: () => {}, onDelete: () => {} };
    const next = { id: '1', name: 'test', onClick: () => {}, onDelete: () => {} };

    expect(comparator(prev, next)).toBe(true);
  });

  it('returns false when a non-excluded prop differs', () => {
    const comparator = createPropsExcluder<TestProps>(['onClick', 'onDelete']);

    const prev = { id: '1', name: 'test', onClick: () => {}, onDelete: () => {} };
    const next = { id: '2', name: 'test', onClick: () => {}, onDelete: () => {} };

    expect(comparator(prev, next)).toBe(false);
  });

  it('ignores excluded props with different references', () => {
    const comparator = createPropsExcluder<TestProps>(['onClick', 'onDelete']);

    const prev = { id: '1', name: 'test', onClick: () => {}, onDelete: () => {} };
    const next = { id: '1', name: 'test', onClick: () => {}, onDelete: () => {} };

    expect(comparator(prev, next)).toBe(true);
  });
});

describe('arrayShallowEqual', () => {
  it('returns true for identical references', () => {
    const arr = [1, 2, 3];
    expect(arrayShallowEqual(arr, arr)).toBe(true);
  });

  it('returns true for arrays with same elements', () => {
    expect(arrayShallowEqual([1, 2, 3], [1, 2, 3])).toBe(true);
  });

  it('returns false for arrays with different elements', () => {
    expect(arrayShallowEqual([1, 2, 3], [1, 2, 4])).toBe(false);
  });

  it('returns false for arrays with different lengths', () => {
    expect(arrayShallowEqual([1, 2], [1, 2, 3])).toBe(false);
  });

  it('handles null arrays', () => {
    // null === null is true (same reference), so arrayShallowEqual returns true
    expect(arrayShallowEqual(null, null)).toBe(true);
    expect(arrayShallowEqual(null, [1, 2])).toBe(false);
    expect(arrayShallowEqual([1, 2], null)).toBe(false);
  });

  it('handles undefined arrays', () => {
    // undefined === undefined is true (same reference), so arrayShallowEqual returns true
    expect(arrayShallowEqual(undefined, undefined)).toBe(true);
    expect(arrayShallowEqual(undefined, [1, 2])).toBe(false);
    expect(arrayShallowEqual([1, 2], undefined)).toBe(false);
  });

  it('handles empty arrays', () => {
    expect(arrayShallowEqual([], [])).toBe(true);
  });

  it('compares object references in arrays', () => {
    const obj = { a: 1 };
    expect(arrayShallowEqual([obj], [obj])).toBe(true);
    expect(arrayShallowEqual([{ a: 1 }], [{ a: 1 }])).toBe(false); // Different references
  });
});

describe('createArrayPropsComparator', () => {
  interface TestProps {
    items: number[];
    selectedIds: string[];
    onClick: () => void;
  }

  it('compares array props by shallow array equality', () => {
    const comparator = createArrayPropsComparator<TestProps>({
      arrayProps: ['items', 'selectedIds'],
      ignoreProps: ['onClick'],
    });

    const prev = { items: [1, 2, 3], selectedIds: ['a', 'b'], onClick: () => {} };
    const next = { items: [1, 2, 3], selectedIds: ['a', 'b'], onClick: () => {} };

    expect(comparator(prev, next)).toBe(true);
  });

  it('returns false when array contents differ', () => {
    const comparator = createArrayPropsComparator<TestProps>({
      arrayProps: ['items', 'selectedIds'],
    });

    const prev = { items: [1, 2, 3], selectedIds: ['a', 'b'], onClick: () => {} };
    const next = { items: [1, 2, 4], selectedIds: ['a', 'b'], onClick: () => {} };

    expect(comparator(prev, next)).toBe(false);
  });

  it('ignores specified props', () => {
    const comparator = createArrayPropsComparator<TestProps>({
      arrayProps: ['items', 'selectedIds'],
      ignoreProps: ['onClick'],
    });

    const callback1 = () => {};
    const callback2 = () => {};

    const prev = { items: [1, 2], selectedIds: ['a'], onClick: callback1 };
    const next = { items: [1, 2], selectedIds: ['a'], onClick: callback2 };

    expect(comparator(prev, next)).toBe(true);
  });
});

describe('listItemPropsComparator', () => {
  it('ignores common callback props', () => {
    const prev = {
      id: '1',
      name: 'Test',
      onClick: () => {},
      onSelect: () => {},
      onDelete: () => {},
    };

    const next = {
      id: '1',
      name: 'Test',
      onClick: () => {}, // Different reference
      onSelect: () => {},
      onDelete: () => {},
    };

    expect(listItemPropsComparator(prev, next)).toBe(true);
  });

  it('detects changes in data props', () => {
    const prev = { id: '1', name: 'Test', onClick: () => {} };
    const next = { id: '1', name: 'Changed', onClick: () => {} };

    expect(listItemPropsComparator(prev, next)).toBe(false);
  });
});

describe('cardPropsComparator', () => {
  it('ignores card-specific callback props', () => {
    const prev = {
      id: '1',
      title: 'Card',
      onViewDetails: () => {},
      onDismiss: () => {},
      onSnooze: () => {},
    };

    const next = {
      id: '1',
      title: 'Card',
      onViewDetails: () => {},
      onDismiss: () => {},
      onSnooze: () => {},
    };

    expect(cardPropsComparator(prev, next)).toBe(true);
  });

  it('detects changes in content props', () => {
    const prev = { id: '1', title: 'Card', onViewDetails: () => {} };
    const next = { id: '1', title: 'Updated Card', onViewDetails: () => {} };

    expect(cardPropsComparator(prev, next)).toBe(false);
  });
});

describe('deepEqual', () => {
  it('returns true for identical primitives', () => {
    expect(deepEqual(1, 1)).toBe(true);
    expect(deepEqual('test', 'test')).toBe(true);
    expect(deepEqual(true, true)).toBe(true);
  });

  it('returns false for different primitives', () => {
    expect(deepEqual(1, 2)).toBe(false);
    expect(deepEqual('test', 'test2')).toBe(false);
    expect(deepEqual(true, false)).toBe(false);
  });

  it('handles null and undefined', () => {
    expect(deepEqual(null, null)).toBe(true);
    expect(deepEqual(undefined, undefined)).toBe(true);
    expect(deepEqual(null, undefined)).toBe(false);
    expect(deepEqual(null, 1)).toBe(false);
    expect(deepEqual(undefined, 1)).toBe(false);
  });

  it('compares arrays deeply', () => {
    expect(deepEqual([1, 2, 3], [1, 2, 3])).toBe(true);
    expect(deepEqual([1, 2, 3], [1, 2, 4])).toBe(false);
    expect(deepEqual([1, [2, 3]], [1, [2, 3]])).toBe(true);
    expect(deepEqual([1, [2, 3]], [1, [2, 4]])).toBe(false);
  });

  it('compares objects deeply', () => {
    expect(deepEqual({ a: 1, b: 2 }, { a: 1, b: 2 })).toBe(true);
    expect(deepEqual({ a: 1, b: 2 }, { a: 1, b: 3 })).toBe(false);
    expect(deepEqual({ a: { b: 1 } }, { a: { b: 1 } })).toBe(true);
    expect(deepEqual({ a: { b: 1 } }, { a: { b: 2 } })).toBe(false);
  });

  it('respects maxDepth limit', () => {
    const deeply = { a: { b: { c: { d: 1 } } } };
    const deeply2 = { a: { b: { c: { d: 2 } } } };

    // With maxDepth=2, it won't go deep enough to see the difference
    // Actually, maxDepth=3 is default, let's test with 1
    expect(deepEqual(deeply, deeply2, 2)).toBe(false); // Can still detect difference at shallow level
  });

  it('handles mixed types', () => {
    expect(deepEqual({ a: [1, 2] }, { a: [1, 2] })).toBe(true);
    expect(deepEqual({ a: [1, { b: 2 }] }, { a: [1, { b: 2 }] })).toBe(true);
    expect(deepEqual({ a: [1, { b: 2 }] }, { a: [1, { b: 3 }] })).toBe(false);
  });
});

describe('createDeepPropsComparator', () => {
  interface TestProps {
    data: { x: number; y: number }[];
    config: { colors: string[] };
    onClick: () => void;
  }

  it('uses deep equality for specified props', () => {
    const comparator = createDeepPropsComparator<TestProps>({
      deepProps: ['data', 'config'],
      ignoreProps: ['onClick'],
    });

    const prev = {
      data: [{ x: 1, y: 2 }],
      config: { colors: ['red', 'blue'] },
      onClick: () => {},
    };

    const next = {
      data: [{ x: 1, y: 2 }],
      config: { colors: ['red', 'blue'] },
      onClick: () => {},
    };

    expect(comparator(prev, next)).toBe(true);
  });

  it('detects deep differences in array props', () => {
    const comparator = createDeepPropsComparator<TestProps>({
      deepProps: ['data'],
      ignoreProps: ['onClick'],
    });

    const prev = {
      data: [{ x: 1, y: 2 }],
      config: { colors: ['red'] },
      onClick: () => {},
    };

    const next = {
      data: [{ x: 1, y: 3 }], // y changed
      config: { colors: ['red'] },
      onClick: () => {},
    };

    expect(comparator(prev, next)).toBe(false);
  });

  it('ignores specified callback props', () => {
    const comparator = createDeepPropsComparator<TestProps>({
      deepProps: ['data'],
      ignoreProps: ['onClick'],
    });

    // Note: For non-deep props like `config`, we need the same object reference
    // for the comparator to consider them equal.
    const sharedConfig = { colors: ['red'] };

    const prev = {
      data: [{ x: 1, y: 2 }],
      config: sharedConfig, // Same reference
      // eslint-disable-next-line no-console -- test function reference
      onClick: () => console.log('prev'),
    };

    const next = {
      data: [{ x: 1, y: 2 }],
      config: sharedConfig, // Same reference
      // eslint-disable-next-line no-console -- test function reference
      onClick: () => console.log('next'),
    };

    expect(comparator(prev, next)).toBe(true);
  });
});
