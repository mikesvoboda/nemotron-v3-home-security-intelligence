/**
 * Unit tests for functional pipeline utilities.
 *
 * These utilities provide composable data transformation functions
 * for event filtering, sorting, and processing.
 *
 * @see pipeline.ts
 */
import { describe, it, expect } from 'vitest';

import {
  pipe,
  filterByQuery,
  sortByDate,
  sortByRisk,
  take,
  skip,
  identity,
  type Transform,
} from './pipeline';

// Test data types
interface TestEvent {
  id: number;
  summary?: string;
  started_at: string;
  risk_score?: number;
}

// Sample test data
const createTestEvents = (): TestEvent[] => [
  {
    id: 1,
    summary: 'Person detected at front door',
    started_at: '2024-01-15T10:00:00Z',
    risk_score: 75,
  },
  { id: 2, summary: 'Vehicle in driveway', started_at: '2024-01-15T09:00:00Z', risk_score: 30 },
  { id: 3, summary: 'Animal movement in yard', started_at: '2024-01-15T11:00:00Z', risk_score: 10 },
  {
    id: 4,
    summary: 'Package delivery detected',
    started_at: '2024-01-15T08:00:00Z',
    risk_score: 45,
  },
  { id: 5, started_at: '2024-01-15T12:00:00Z', risk_score: 60 }, // No summary
];

describe('pipe', () => {
  it('returns identity function when no transforms are provided', () => {
    const events = createTestEvents();
    const result = pipe<TestEvent>()(events);
    expect(result).toEqual(events);
  });

  it('applies a single transform', () => {
    const events = createTestEvents();
    const double: Transform<TestEvent> = (items) => [...items, ...items];
    const result = pipe(double)(events);
    expect(result).toHaveLength(10);
  });

  it('applies multiple transforms in order', () => {
    const events = createTestEvents();
    const addOne: Transform<TestEvent> = (items) => [
      ...items,
      { id: 999, started_at: '2024-01-15T00:00:00Z' },
    ];
    const filterById: Transform<TestEvent> = (items) => items.filter((e) => e.id > 3);

    // Order matters: addOne first, then filter
    const result = pipe(addOne, filterById)(events);
    expect(result.map((e) => e.id)).toEqual([4, 5, 999]);
  });

  it('preserves immutability of original array', () => {
    const events = createTestEvents();
    const originalLength = events.length;
    const addItem: Transform<TestEvent> = (items) => [
      ...items,
      { id: 100, started_at: '2024-01-01T00:00:00Z' },
    ];

    pipe(addItem)(events);
    expect(events).toHaveLength(originalLength);
  });

  it('handles empty arrays', () => {
    const result = pipe<TestEvent>(filterByQuery('test'))([]);
    expect(result).toEqual([]);
  });
});

describe('filterByQuery', () => {
  it('returns all events when query is empty', () => {
    const events = createTestEvents();
    const result = filterByQuery<TestEvent>('')(events);
    expect(result).toHaveLength(5);
  });

  it('filters events by summary content (case-insensitive)', () => {
    const events = createTestEvents();
    const result = filterByQuery<TestEvent>('person')(events);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
  });

  it('handles uppercase query', () => {
    const events = createTestEvents();
    const result = filterByQuery<TestEvent>('VEHICLE')(events);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(2);
  });

  it('handles mixed case in both query and content', () => {
    const events = createTestEvents();
    const result = filterByQuery<TestEvent>('Front Door')(events);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
  });

  it('excludes events without summary when searching', () => {
    const events = createTestEvents();
    const result = filterByQuery<TestEvent>('detected')(events);
    // Events 1 and 4 have 'detected' in summary, event 5 has no summary
    expect(result).toHaveLength(2);
    expect(result.map((e) => e.id)).toEqual([1, 4]);
  });

  it('includes events without summary when query is empty', () => {
    const events = createTestEvents();
    const result = filterByQuery<TestEvent>('')(events);
    expect(result.some((e) => e.id === 5)).toBe(true);
  });

  it('returns empty array when no matches found', () => {
    const events = createTestEvents();
    const result = filterByQuery<TestEvent>('nonexistent')(events);
    expect(result).toHaveLength(0);
  });

  it('handles whitespace-only query as empty', () => {
    const events = createTestEvents();
    const result = filterByQuery<TestEvent>('   ')(events);
    expect(result).toHaveLength(5);
  });
});

describe('sortByDate', () => {
  it('sorts events by date in descending order (newest first)', () => {
    const events = createTestEvents();
    const result = sortByDate<TestEvent>('desc')(events);

    expect(result[0].id).toBe(5); // 12:00
    expect(result[1].id).toBe(3); // 11:00
    expect(result[2].id).toBe(1); // 10:00
    expect(result[3].id).toBe(2); // 09:00
    expect(result[4].id).toBe(4); // 08:00
  });

  it('sorts events by date in ascending order (oldest first)', () => {
    const events = createTestEvents();
    const result = sortByDate<TestEvent>('asc')(events);

    expect(result[0].id).toBe(4); // 08:00
    expect(result[1].id).toBe(2); // 09:00
    expect(result[2].id).toBe(1); // 10:00
    expect(result[3].id).toBe(3); // 11:00
    expect(result[4].id).toBe(5); // 12:00
  });

  it('does not mutate the original array', () => {
    const events = createTestEvents();
    const firstId = events[0].id;
    sortByDate<TestEvent>('desc')(events);
    expect(events[0].id).toBe(firstId);
  });

  it('handles single element array', () => {
    const events = [{ id: 1, started_at: '2024-01-15T10:00:00Z' }];
    const result = sortByDate<{ id: number; started_at: string }>('desc')(events);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(1);
  });

  it('handles empty array', () => {
    const result = sortByDate<TestEvent>('desc')([]);
    expect(result).toEqual([]);
  });

  it('maintains stable sort for equal timestamps', () => {
    const events = [
      { id: 1, started_at: '2024-01-15T10:00:00Z' },
      { id: 2, started_at: '2024-01-15T10:00:00Z' },
      { id: 3, started_at: '2024-01-15T10:00:00Z' },
    ];
    const result = sortByDate<{ id: number; started_at: string }>('desc')(events);
    // Original order should be preserved for equal timestamps
    expect(result.map((e) => e.id)).toEqual([1, 2, 3]);
  });
});

describe('sortByRisk', () => {
  it('sorts events by risk score in descending order (highest first)', () => {
    const events = createTestEvents();
    const result = sortByRisk<TestEvent>('desc')(events);

    expect(result[0].id).toBe(1); // 75
    expect(result[1].id).toBe(5); // 60
    expect(result[2].id).toBe(4); // 45
    expect(result[3].id).toBe(2); // 30
    expect(result[4].id).toBe(3); // 10
  });

  it('sorts events by risk score in ascending order (lowest first)', () => {
    const events = createTestEvents();
    const result = sortByRisk<TestEvent>('asc')(events);

    expect(result[0].id).toBe(3); // 10
    expect(result[1].id).toBe(2); // 30
    expect(result[2].id).toBe(4); // 45
    expect(result[3].id).toBe(5); // 60
    expect(result[4].id).toBe(1); // 75
  });

  it('treats undefined risk_score as 0', () => {
    const events = [
      { id: 1, started_at: '2024-01-15T10:00:00Z', risk_score: 50 },
      { id: 2, started_at: '2024-01-15T10:00:00Z' }, // undefined risk_score
      { id: 3, started_at: '2024-01-15T10:00:00Z', risk_score: 25 },
    ];
    type EventWithOptionalRisk = { id: number; started_at: string; risk_score?: number };
    const result = sortByRisk<EventWithOptionalRisk>('asc')(events);

    expect(result[0].id).toBe(2); // undefined = 0
    expect(result[1].id).toBe(3); // 25
    expect(result[2].id).toBe(1); // 50
  });

  it('treats null risk_score as 0', () => {
    const events = [
      { id: 1, started_at: '2024-01-15T10:00:00Z', risk_score: 50 },
      { id: 2, started_at: '2024-01-15T10:00:00Z', risk_score: null as unknown as number },
      { id: 3, started_at: '2024-01-15T10:00:00Z', risk_score: 25 },
    ];
    type EventWithNullableRisk = { id: number; started_at: string; risk_score?: number | null };
    const result = sortByRisk<EventWithNullableRisk>('asc')(events);

    expect(result[0].id).toBe(2); // null = 0
    expect(result[1].id).toBe(3); // 25
    expect(result[2].id).toBe(1); // 50
  });

  it('does not mutate the original array', () => {
    const events = createTestEvents();
    const firstId = events[0].id;
    sortByRisk<TestEvent>('desc')(events);
    expect(events[0].id).toBe(firstId);
  });

  it('handles empty array', () => {
    const result = sortByRisk<TestEvent>('desc')([]);
    expect(result).toEqual([]);
  });
});

describe('take', () => {
  it('returns first n items', () => {
    const events = createTestEvents();
    const result = take<TestEvent>(3)(events);
    expect(result).toHaveLength(3);
    expect(result.map((e) => e.id)).toEqual([1, 2, 3]);
  });

  it('returns all items when n exceeds array length', () => {
    const events = createTestEvents();
    const result = take<TestEvent>(10)(events);
    expect(result).toHaveLength(5);
  });

  it('returns empty array when n is 0', () => {
    const events = createTestEvents();
    const result = take<TestEvent>(0)(events);
    expect(result).toHaveLength(0);
  });

  it('handles empty array', () => {
    const result = take<TestEvent>(5)([]);
    expect(result).toEqual([]);
  });
});

describe('skip', () => {
  it('skips first n items', () => {
    const events = createTestEvents();
    const result = skip<TestEvent>(2)(events);
    expect(result).toHaveLength(3);
    expect(result.map((e) => e.id)).toEqual([3, 4, 5]);
  });

  it('returns empty array when n exceeds array length', () => {
    const events = createTestEvents();
    const result = skip<TestEvent>(10)(events);
    expect(result).toHaveLength(0);
  });

  it('returns all items when n is 0', () => {
    const events = createTestEvents();
    const result = skip<TestEvent>(0)(events);
    expect(result).toHaveLength(5);
  });

  it('handles empty array', () => {
    const result = skip<TestEvent>(5)([]);
    expect(result).toEqual([]);
  });
});

describe('identity', () => {
  it('returns the input array unchanged', () => {
    const events = createTestEvents();
    const result = identity(events);
    expect(result).toEqual(events);
    expect(result).toBe(events); // Same reference
  });

  it('handles empty array', () => {
    const result = identity([]);
    expect(result).toEqual([]);
  });
});

describe('pipeline composition', () => {
  it('combines filter and sort', () => {
    const events = createTestEvents();
    const result = pipe<TestEvent>(
      filterByQuery<TestEvent>('detected'),
      sortByRisk<TestEvent>('desc')
    )(events);

    expect(result).toHaveLength(2);
    expect(result[0].id).toBe(1); // Person detected, risk 75
    expect(result[1].id).toBe(4); // Package delivery detected, risk 45
  });

  it('combines sort, skip, and take for pagination', () => {
    const events = createTestEvents();
    const result = pipe<TestEvent>(
      sortByDate<TestEvent>('desc'),
      skip<TestEvent>(1),
      take<TestEvent>(2)
    )(events);

    expect(result).toHaveLength(2);
    // After sorting desc: [5, 3, 1, 2, 4]
    // After skip(1): [3, 1, 2, 4]
    // After take(2): [3, 1]
    expect(result.map((e) => e.id)).toEqual([3, 1]);
  });

  it('combines all operations in a realistic use case', () => {
    const events = createTestEvents();

    // Search for events, sort by risk, paginate
    const result = pipe<TestEvent>(
      filterByQuery<TestEvent>(''), // No filter
      sortByRisk<TestEvent>('desc'), // Highest risk first
      skip<TestEvent>(0), // Page 1
      take<TestEvent>(3) // 3 per page
    )(events);

    expect(result).toHaveLength(3);
    expect(result[0].risk_score).toBe(75);
    expect(result[1].risk_score).toBe(60);
    expect(result[2].risk_score).toBe(45);
  });

  it('handles conditional transforms in pipeline', () => {
    const events = createTestEvents();
    const searchQuery = 'vehicle';
    const shouldSort = true;

    // Conditionally apply transforms
    const result = pipe<TestEvent>(
      searchQuery ? filterByQuery<TestEvent>(searchQuery) : identity,
      shouldSort ? sortByDate<TestEvent>('desc') : identity
    )(events);

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe(2);
  });
});

describe('type safety', () => {
  it('works with custom event types', () => {
    interface CustomEvent {
      id: string;
      summary?: string;
      started_at: string;
      risk_score?: number;
      customField: boolean;
    }

    const customEvents: CustomEvent[] = [
      {
        id: 'a',
        summary: 'Test A',
        started_at: '2024-01-15T10:00:00Z',
        risk_score: 50,
        customField: true,
      },
      {
        id: 'b',
        summary: 'Test B',
        started_at: '2024-01-15T09:00:00Z',
        risk_score: 75,
        customField: false,
      },
    ];

    const result = pipe<CustomEvent>(
      filterByQuery<CustomEvent>('Test'),
      sortByRisk<CustomEvent>('desc')
    )(customEvents);

    expect(result).toHaveLength(2);
    expect(result[0].id).toBe('b');
    expect(result[0].customField).toBe(false);
  });

  it('maintains type inference through pipeline', () => {
    const events = createTestEvents();
    const result = pipe<TestEvent>(
      filterByQuery<TestEvent>('person'),
      sortByDate<TestEvent>('desc'),
      take<TestEvent>(1)
    )(events);

    // TypeScript should infer result as TestEvent[]
    // This test verifies the type is preserved
    expect(result[0].started_at).toBeDefined();
  });
});
