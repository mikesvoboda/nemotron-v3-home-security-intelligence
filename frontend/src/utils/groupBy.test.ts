import { describe, expect, it, vi } from 'vitest';

import { countBy, groupBy } from './groupBy';

describe('groupBy', () => {
  describe('basic functionality', () => {
    it('groups items by string key', () => {
      const items = [
        { id: 1, category: 'a' },
        { id: 2, category: 'b' },
        { id: 3, category: 'a' },
      ];

      const result = groupBy(items, (item) => item.category);

      expect(result).toEqual({
        a: [
          { id: 1, category: 'a' },
          { id: 3, category: 'a' },
        ],
        b: [{ id: 2, category: 'b' }],
      });
    });

    it('groups items by numeric key', () => {
      const items = [
        { name: 'alice', age: 30 },
        { name: 'bob', age: 25 },
        { name: 'charlie', age: 30 },
      ];

      const result = groupBy(items, (item) => item.age);

      expect(result).toEqual({
        25: [{ name: 'bob', age: 25 }],
        30: [
          { name: 'alice', age: 30 },
          { name: 'charlie', age: 30 },
        ],
      });
    });

    it('returns empty object for empty array', () => {
      const result = groupBy([], (item: { key: string }) => item.key);

      expect(result).toEqual({});
    });

    it('handles single item array', () => {
      const items = [{ id: 1, type: 'test' }];

      const result = groupBy(items, (item) => item.type);

      expect(result).toEqual({
        test: [{ id: 1, type: 'test' }],
      });
    });

    it('handles all items in same group', () => {
      const items = [
        { id: 1, status: 'active' },
        { id: 2, status: 'active' },
        { id: 3, status: 'active' },
      ];

      const result = groupBy(items, (item) => item.status);

      expect(result).toEqual({
        active: [
          { id: 1, status: 'active' },
          { id: 2, status: 'active' },
          { id: 3, status: 'active' },
        ],
      });
    });

    it('handles each item in unique group', () => {
      const items = [
        { id: 1, key: 'a' },
        { id: 2, key: 'b' },
        { id: 3, key: 'c' },
      ];

      const result = groupBy(items, (item) => item.key);

      expect(result).toEqual({
        a: [{ id: 1, key: 'a' }],
        b: [{ id: 2, key: 'b' }],
        c: [{ id: 3, key: 'c' }],
      });
    });
  });

  describe('with computed keys', () => {
    it('groups by computed boolean condition', () => {
      const items = [
        { value: 10 },
        { value: 25 },
        { value: 5 },
        { value: 30 },
      ];

      const result = groupBy(items, (item) => (item.value >= 20 ? 'high' : 'low'));

      expect(result).toEqual({
        low: [{ value: 10 }, { value: 5 }],
        high: [{ value: 25 }, { value: 30 }],
      });
    });

    it('groups risk events by risk level', () => {
      // Real-world use case for this codebase
      const events = [
        { id: 1, risk_score: 90, risk_level: 'critical' },
        { id: 2, risk_score: 45, risk_level: 'medium' },
        { id: 3, risk_score: 75, risk_level: 'high' },
        { id: 4, risk_score: 15, risk_level: 'low' },
        { id: 5, risk_score: 88, risk_level: 'critical' },
      ];

      const result = groupBy(events, (event) => event.risk_level);

      expect(result.critical).toHaveLength(2);
      expect(result.high).toHaveLength(1);
      expect(result.medium).toHaveLength(1);
      expect(result.low).toHaveLength(1);
    });
  });

  describe('native Object.groupBy detection', () => {
    // Each test saves/restores Object.groupBy to avoid leaking mocks across shards
    it('uses fallback when Object.groupBy is not available', () => {
      const originalGroupBy = (Object as { groupBy?: unknown }).groupBy;
      try {
        // Remove native to test fallback
        if ('groupBy' in Object) {
          delete (Object as { groupBy?: unknown }).groupBy;
        }

        // Ensure native is not available
        expect('groupBy' in Object).toBe(false);

        const items = [
          { id: 1, type: 'a' },
          { id: 2, type: 'b' },
        ];

        const result = groupBy(items, (item) => item.type);

        expect(result).toEqual({
          a: [{ id: 1, type: 'a' }],
          b: [{ id: 2, type: 'b' }],
        });
      } finally {
        // Restore original groupBy
        if (originalGroupBy !== undefined) {
          (Object as { groupBy?: unknown }).groupBy = originalGroupBy;
        }
      }
    });

    it('uses native Object.groupBy when available', () => {
      const originalGroupBy = (Object as { groupBy?: unknown }).groupBy;
      try {
        // Mock native Object.groupBy
        const mockGroupBy = vi.fn().mockReturnValue({ a: [{ id: 1 }] });
        (Object as { groupBy?: unknown }).groupBy = mockGroupBy;

        const items = [{ id: 1, type: 'a' }];
        const keySelector = (item: { id: number; type: string }) => item.type;

        groupBy(items, keySelector);

        expect(mockGroupBy).toHaveBeenCalledWith(items, keySelector);
      } finally {
        // Restore original groupBy
        if (originalGroupBy !== undefined) {
          (Object as { groupBy?: unknown }).groupBy = originalGroupBy;
        } else if ('groupBy' in Object) {
          delete (Object as { groupBy?: unknown }).groupBy;
        }
      }
    });

    it('returns native result when Object.groupBy is available', () => {
      const originalGroupBy = (Object as { groupBy?: unknown }).groupBy;
      try {
        // Mock native Object.groupBy with specific return value
        const nativeResult = { native: [{ id: 1 }] };
        (Object as { groupBy?: unknown }).groupBy = vi.fn().mockReturnValue(nativeResult);

        const items = [{ id: 1, type: 'native' }];
        const result = groupBy(items, (item) => item.type);

        expect(result).toBe(nativeResult);
      } finally {
        // Restore original groupBy
        if (originalGroupBy !== undefined) {
          (Object as { groupBy?: unknown }).groupBy = originalGroupBy;
        } else if ('groupBy' in Object) {
          delete (Object as { groupBy?: unknown }).groupBy;
        }
      }
    });
  });

  describe('type safety', () => {
    it('preserves item types in grouped arrays', () => {
      interface User {
        id: number;
        name: string;
        role: 'admin' | 'user';
      }

      const users: User[] = [
        { id: 1, name: 'Alice', role: 'admin' },
        { id: 2, name: 'Bob', role: 'user' },
      ];

      const result = groupBy(users, (user) => user.role);

      // Type assertion: each group should contain User[]
      const admins = result.admin;
      if (admins) {
        expect(admins[0].name).toBe('Alice');
      }
    });

    it('handles symbol keys', () => {
      const sym1 = Symbol('group1');
      const sym2 = Symbol('group2');

      const items = [
        { id: 1, group: sym1 },
        { id: 2, group: sym2 },
        { id: 3, group: sym1 },
      ];

      const result = groupBy(items, (item) => item.group);

      expect(result[sym1]).toHaveLength(2);
      expect(result[sym2]).toHaveLength(1);
    });
  });
});

describe('countBy', () => {
  describe('basic functionality', () => {
    it('counts items by string key', () => {
      const items = [
        { id: 1, category: 'a' },
        { id: 2, category: 'b' },
        { id: 3, category: 'a' },
        { id: 4, category: 'a' },
      ];

      const result = countBy(items, (item) => item.category);

      expect(result).toEqual({
        a: 3,
        b: 1,
      });
    });

    it('returns empty object for empty array', () => {
      const result = countBy([], (item: { key: string }) => item.key);

      expect(result).toEqual({});
    });

    it('counts risk levels correctly', () => {
      // Real-world use case: counting events by risk level
      const events = [
        { id: 1, risk_level: 'critical' },
        { id: 2, risk_level: 'critical' },
        { id: 3, risk_level: 'high' },
        { id: 4, risk_level: 'medium' },
        { id: 5, risk_level: 'low' },
        { id: 6, risk_level: 'low' },
        { id: 7, risk_level: 'low' },
      ];

      const result = countBy(events, (event) => event.risk_level);

      expect(result).toEqual({
        critical: 2,
        high: 1,
        medium: 1,
        low: 3,
      });
    });
  });

  describe('with computed keys', () => {
    it('counts by computed boolean condition', () => {
      const items = [
        { value: 10 },
        { value: 25 },
        { value: 5 },
        { value: 30 },
        { value: 15 },
      ];

      const result = countBy(items, (item) => (item.value >= 20 ? 'high' : 'low'));

      expect(result).toEqual({
        low: 3,
        high: 2,
      });
    });

    it('counts by derived risk level from score', () => {
      // Simulates the EventTimeline use case
      const getRiskLevel = (score: number): string => {
        if (score <= 29) return 'low';
        if (score <= 59) return 'medium';
        if (score <= 84) return 'high';
        return 'critical';
      };

      const events = [
        { id: 1, risk_score: 90 }, // critical
        { id: 2, risk_score: 45 }, // medium
        { id: 3, risk_score: 75 }, // high
        { id: 4, risk_score: 15 }, // low
        { id: 5, risk_score: 88 }, // critical
        { id: 6, risk_score: 25 }, // low
      ];

      const result = countBy(events, (event) => getRiskLevel(event.risk_score));

      expect(result).toEqual({
        critical: 2,
        high: 1,
        medium: 1,
        low: 2,
      });
    });
  });
});
