/**
 * Tests for Auto-Selectors Utility (NEM-3787)
 */

import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { create } from 'zustand';
import { devtools, persist, createJSONStorage } from 'zustand/middleware';

import { createSelectors, type ExtractState, type SelectorKeys } from './createSelectors';

// ============================================================================
// Test Interfaces
// ============================================================================

interface TestState {
  count: number;
  name: string;
  items: string[];
  nested: { value: number };
  increment: () => void;
  setName: (name: string) => void;
  addItem: (item: string) => void;
  setNestedValue: (value: number) => void;
}

interface EventState {
  events: Array<{ id: string; name: string }>;
  filters: { riskLevel: string | null; camera: string | null };
  selectedEventId: string | null;
  setFilters: (filters: EventState['filters']) => void;
  setSelectedEventId: (id: string | null) => void;
}

// ============================================================================
// Helper to create test stores
// ============================================================================

function createTestStore() {
  return create<TestState>()((set) => ({
    count: 0,
    name: 'initial',
    items: [],
    nested: { value: 0 },
    increment: () => set((state) => ({ count: state.count + 1 })),
    setName: (name) => set({ name }),
    addItem: (item) => set((state) => ({ items: [...state.items, item] })),
    setNestedValue: (value) => set({ nested: { value } }),
  }));
}

function createEventStore() {
  return create<EventState>()((set) => ({
    events: [],
    filters: { riskLevel: null, camera: null },
    selectedEventId: null,
    setFilters: (filters) => set({ filters }),
    setSelectedEventId: (id) => set({ selectedEventId: id }),
  }));
}

// ============================================================================
// createSelectors Tests
// ============================================================================

describe('createSelectors', () => {
  describe('selector creation', () => {
    it('creates selectors for all state properties', () => {
      const useTestStore = createSelectors(createTestStore());

      expect(useTestStore.use).toBeDefined();
      expect(typeof useTestStore.use.count).toBe('function');
      expect(typeof useTestStore.use.name).toBe('function');
      expect(typeof useTestStore.use.items).toBe('function');
      expect(typeof useTestStore.use.nested).toBe('function');
      expect(typeof useTestStore.use.increment).toBe('function');
      expect(typeof useTestStore.use.setName).toBe('function');
      expect(typeof useTestStore.use.addItem).toBe('function');
      expect(typeof useTestStore.use.setNestedValue).toBe('function');
    });

    it('preserves original store functionality', () => {
      const useTestStore = createSelectors(createTestStore());

      // Traditional usage still works
      const state = useTestStore.getState();
      expect(state.count).toBe(0);
      expect(state.name).toBe('initial');

      // setState still works
      useTestStore.setState({ count: 5 });
      expect(useTestStore.getState().count).toBe(5);

      // subscribe still works
      const callback = vi.fn();
      const unsubscribe = useTestStore.subscribe(callback);
      useTestStore.setState({ count: 10 });
      expect(callback).toHaveBeenCalled();
      unsubscribe();
    });
  });

  describe('selector hooks', () => {
    it('returns correct initial values via selectors', () => {
      const useTestStore = createSelectors(createTestStore());

      const { result: countResult } = renderHook(() => useTestStore.use.count());
      const { result: nameResult } = renderHook(() => useTestStore.use.name());
      const { result: itemsResult } = renderHook(() => useTestStore.use.items());
      const { result: nestedResult } = renderHook(() => useTestStore.use.nested());

      expect(countResult.current).toBe(0);
      expect(nameResult.current).toBe('initial');
      expect(itemsResult.current).toEqual([]);
      expect(nestedResult.current).toEqual({ value: 0 });
    });

    it('updates selected values when state changes', () => {
      const useTestStore = createSelectors(createTestStore());
      const { result: countResult } = renderHook(() => useTestStore.use.count());

      expect(countResult.current).toBe(0);

      act(() => {
        useTestStore.getState().increment();
      });

      expect(countResult.current).toBe(1);
    });

    it('returns action functions via selectors', () => {
      const useTestStore = createSelectors(createTestStore());
      const { result: incrementResult } = renderHook(() => useTestStore.use.increment());
      const { result: setNameResult } = renderHook(() => useTestStore.use.setName());

      expect(typeof incrementResult.current).toBe('function');
      expect(typeof setNameResult.current).toBe('function');

      // Actions should work
      act(() => {
        incrementResult.current();
      });

      expect(useTestStore.getState().count).toBe(1);
    });
  });

  describe('re-render optimization', () => {
    it('only triggers re-render when selected property changes', () => {
      const useTestStore = createSelectors(createTestStore());
      const countRenderCount = vi.fn();
      const nameRenderCount = vi.fn();

      const { result: countResult } = renderHook(() => {
        countRenderCount();
        return useTestStore.use.count();
      });

      const { result: nameResult } = renderHook(() => {
        nameRenderCount();
        return useTestStore.use.name();
      });

      // Initial render
      expect(countRenderCount).toHaveBeenCalledTimes(1);
      expect(nameRenderCount).toHaveBeenCalledTimes(1);

      // Update count - only count selector should re-render
      act(() => {
        useTestStore.getState().increment();
      });

      expect(countResult.current).toBe(1);
      expect(countRenderCount).toHaveBeenCalledTimes(2);
      expect(nameRenderCount).toHaveBeenCalledTimes(1); // No re-render for name

      // Update name - only name selector should re-render
      act(() => {
        useTestStore.getState().setName('updated');
      });

      expect(nameResult.current).toBe('updated');
      expect(countRenderCount).toHaveBeenCalledTimes(2); // No re-render for count
      expect(nameRenderCount).toHaveBeenCalledTimes(2);
    });

    it('does not re-render when unrelated state changes', () => {
      const useTestStore = createSelectors(createTestStore());
      const itemsRenderCount = vi.fn();

      renderHook(() => {
        itemsRenderCount();
        return useTestStore.use.items();
      });

      expect(itemsRenderCount).toHaveBeenCalledTimes(1);

      // Update count - items should not re-render
      act(() => {
        useTestStore.getState().increment();
        useTestStore.getState().increment();
        useTestStore.getState().setName('test');
      });

      expect(itemsRenderCount).toHaveBeenCalledTimes(1);

      // Update items - should re-render
      act(() => {
        useTestStore.getState().addItem('new item');
      });

      expect(itemsRenderCount).toHaveBeenCalledTimes(2);
    });
  });

  describe('complex state scenarios', () => {
    it('handles array state correctly', () => {
      const useEventStore = createSelectors(createEventStore());
      const { result } = renderHook(() => useEventStore.use.events());

      expect(result.current).toEqual([]);

      act(() => {
        useEventStore.setState({
          events: [
            { id: '1', name: 'Event 1' },
            { id: '2', name: 'Event 2' },
          ],
        });
      });

      expect(result.current).toHaveLength(2);
      expect(result.current[0].id).toBe('1');
    });

    it('handles nested object state correctly', () => {
      const useEventStore = createSelectors(createEventStore());
      const { result } = renderHook(() => useEventStore.use.filters());

      expect(result.current).toEqual({ riskLevel: null, camera: null });

      act(() => {
        useEventStore.getState().setFilters({ riskLevel: 'high', camera: 'cam1' });
      });

      expect(result.current).toEqual({ riskLevel: 'high', camera: 'cam1' });
    });

    it('handles nullable state correctly', () => {
      const useEventStore = createSelectors(createEventStore());
      const { result } = renderHook(() => useEventStore.use.selectedEventId());

      expect(result.current).toBeNull();

      act(() => {
        useEventStore.getState().setSelectedEventId('event-123');
      });

      expect(result.current).toBe('event-123');

      act(() => {
        useEventStore.getState().setSelectedEventId(null);
      });

      expect(result.current).toBeNull();
    });
  });

  describe('type safety', () => {
    it('provides correct types for ExtractState', () => {
      const _useTestStore = createSelectors(createTestStore());

      // This is a compile-time test - if it compiles, types are correct
      type State = ExtractState<typeof _useTestStore>;

      // Type assertions (these would fail to compile if types were wrong)
      const _count: State['count'] = 0;
      const _name: State['name'] = 'test';
      const _items: State['items'] = [];
      const _nested: State['nested'] = { value: 0 };

      expect(_count).toBe(0);
      expect(_name).toBe('test');
      expect(_items).toEqual([]);
      expect(_nested).toEqual({ value: 0 });
    });

    it('provides correct types for SelectorKeys', () => {
      const _useTestStore = createSelectors(createTestStore());

      // This is a compile-time test
      type Keys = SelectorKeys<typeof _useTestStore>;

      // These should all be valid keys
      const validKeys: Keys[] = [
        'count',
        'name',
        'items',
        'nested',
        'increment',
        'setName',
        'addItem',
        'setNestedValue',
      ];

      expect(validKeys).toHaveLength(8);
    });
  });

  describe('edge cases', () => {
    it('handles empty initial state', () => {
      const useEmptyStore = createSelectors(create<{ value?: string }>()(() => ({})));

      expect(useEmptyStore.use).toBeDefined();
      // Should handle undefined values - use.value is undefined when value property doesn't exist
      expect(useEmptyStore.use.value).toBeUndefined();
    });

    it('handles stores with only actions', () => {
      interface ActionsOnlyState {
        doSomething: () => void;
        doSomethingElse: (value: number) => void;
      }

      const useActionsStore = createSelectors(
        create<ActionsOnlyState>()(() => ({
          doSomething: vi.fn(),
          doSomethingElse: vi.fn(),
        }))
      );

      expect(typeof useActionsStore.use.doSomething).toBe('function');
      expect(typeof useActionsStore.use.doSomethingElse).toBe('function');

      const { result } = renderHook(() => useActionsStore.use.doSomething());
      expect(typeof result.current).toBe('function');
    });

    it('handles rapid state updates', () => {
      const useTestStore = createSelectors(createTestStore());
      const renderCount = vi.fn();

      const { result } = renderHook(() => {
        renderCount();
        return useTestStore.use.count();
      });

      expect(renderCount).toHaveBeenCalledTimes(1);

      // Rapid updates in a single act()
      act(() => {
        for (let i = 0; i < 10; i++) {
          useTestStore.getState().increment();
        }
      });

      expect(result.current).toBe(10);
      // React batches updates, so render count should be minimal
      expect(renderCount.mock.calls.length).toBeLessThanOrEqual(3);
    });

    it('works with multiple components using same selector', () => {
      const useTestStore = createSelectors(createTestStore());
      const { result: result1 } = renderHook(() => useTestStore.use.count());
      const { result: result2 } = renderHook(() => useTestStore.use.count());

      expect(result1.current).toBe(0);
      expect(result2.current).toBe(0);

      act(() => {
        useTestStore.getState().increment();
      });

      // Both should update
      expect(result1.current).toBe(1);
      expect(result2.current).toBe(1);
    });
  });
});

// ============================================================================
// Integration with other middleware
// ============================================================================

describe('createSelectors integration', () => {
  it('works with devtools middleware', () => {
    interface State {
      value: number;
      setValue: (v: number) => void;
    }

    const useStoreBase = create<State>()(
      devtools(
        (set) => ({
          value: 0,
          setValue: (v: number) => set({ value: v }),
        }),
        { name: 'test-store', enabled: false }
      )
    );

    const useStore = createSelectors(useStoreBase);

    const { result } = renderHook(() => useStore.use.value());
    expect(result.current).toBe(0);

    act(() => {
      useStore.getState().setValue(42);
    });

    expect(result.current).toBe(42);
  });

  it('works with persist middleware', () => {
    interface State {
      theme: string;
      setTheme: (t: string) => void;
    }

    // Mock localStorage
    const mockStorage: Record<string, string> = {};
    const storageMock = {
      getItem: (key: string) => mockStorage[key] || null,
      setItem: (key: string, value: string) => {
        mockStorage[key] = value;
      },
      removeItem: (key: string) => {
        delete mockStorage[key];
      },
    };

    const useStoreBase = create<State>()(
      persist(
        (set) => ({
          theme: 'dark',
          setTheme: (t: string) => set({ theme: t }),
        }),
        {
          name: 'test-persist',
          storage: createJSONStorage(() => storageMock),
        }
      )
    );

    const useStore = createSelectors(useStoreBase);

    const { result } = renderHook(() => useStore.use.theme());
    expect(result.current).toBe('dark');

    act(() => {
      useStore.getState().setTheme('light');
    });

    expect(result.current).toBe('light');
  });
});
