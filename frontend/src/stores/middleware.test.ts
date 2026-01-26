/**
 * Tests for Zustand Middleware Utilities (NEM-3402, NEM-3403, NEM-3426)
 */

import { act } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createImmerStore,
  createImmerSelectorStore,
  createImmerDevtoolsStore,
  createTransientBatcher,
  createTransientSlice,
  createShallowSelector,
  shallowEqual,
  createWebSocketEventHandler,
  createDebouncedUpdater,
  applyImmerUpdate,
  createImmerAction,
  safeReadCurrent,
  createComputedSelector,
  combineImmerUpdates,
  type TransientSlice,
} from './middleware';

// ============================================================================
// Test Interfaces
// ============================================================================

interface NestedState {
  nested: {
    deep: {
      value: number;
      items: string[];
    };
  };
  counter: number;
  setDeepValue: (value: number) => void;
  addItem: (item: string) => void;
  increment: () => void;
}

interface MetricsState {
  metrics: {
    cpu: number;
    gpu: number;
    memory: number;
  };
  lastUpdated: number;
  updateMetric: (key: 'cpu' | 'gpu' | 'memory', value: number) => void;
}

// ============================================================================
// createImmerStore Tests
// ============================================================================

describe('createImmerStore', () => {
  it('creates a store with Immer mutations', () => {
    const useStore = createImmerStore<NestedState>((set) => ({
      nested: { deep: { value: 0, items: [] } },
      counter: 0,
      setDeepValue: (value) =>
        set((state) => {
          state.nested.deep.value = value;
        }),
      addItem: (item) =>
        set((state) => {
          state.nested.deep.items.push(item);
        }),
      increment: () =>
        set((state) => {
          state.counter += 1;
        }),
    }));

    // Get initial state
    expect(useStore.getState().nested.deep.value).toBe(0);
    expect(useStore.getState().counter).toBe(0);

    // Test deep mutation
    act(() => {
      useStore.getState().setDeepValue(42);
    });
    expect(useStore.getState().nested.deep.value).toBe(42);

    // Test array mutation
    act(() => {
      useStore.getState().addItem('test');
    });
    expect(useStore.getState().nested.deep.items).toEqual(['test']);

    // Test simple mutation
    act(() => {
      useStore.getState().increment();
    });
    expect(useStore.getState().counter).toBe(1);
  });

  it('maintains immutability - previous state unchanged', () => {
    const useStore = createImmerStore<NestedState>((set) => ({
      nested: { deep: { value: 0, items: [] } },
      counter: 0,
      setDeepValue: (value) =>
        set((state) => {
          state.nested.deep.value = value;
        }),
      addItem: (item) =>
        set((state) => {
          state.nested.deep.items.push(item);
        }),
      increment: () =>
        set((state) => {
          state.counter += 1;
        }),
    }));

    const initialState = useStore.getState();
    const initialNested = initialState.nested;

    act(() => {
      useStore.getState().setDeepValue(100);
    });

    const newState = useStore.getState();

    // States should be different references
    expect(newState).not.toBe(initialState);
    expect(newState.nested).not.toBe(initialNested);

    // But original object should be unchanged
    expect(initialNested.deep.value).toBe(0);
    expect(newState.nested.deep.value).toBe(100);
  });

  it('handles partial state updates without Immer', () => {
    const useStore = createImmerStore<{ count: number; name: string }>((_set) => ({
      count: 0,
      name: 'test',
    }));

    // Direct partial update (not using Immer function)
    act(() => {
      useStore.setState({ count: 5 });
    });

    const state = useStore.getState();
    expect(state.count).toBe(5);
    expect(state.name).toBe('test'); // Unchanged
  });
});

// ============================================================================
// createImmerSelectorStore Tests
// ============================================================================

describe('createImmerSelectorStore', () => {
  it('creates store with both Immer and selector capabilities', () => {
    const useStore = createImmerSelectorStore<MetricsState>((set) => ({
      metrics: { cpu: 0, gpu: 0, memory: 0 },
      lastUpdated: 0,
      updateMetric: (key, value) =>
        set((state) => {
          state.metrics[key] = value;
          state.lastUpdated = Date.now();
        }),
    }));

    // Test Immer mutation
    act(() => {
      useStore.getState().updateMetric('cpu', 50);
    });

    expect(useStore.getState().metrics.cpu).toBe(50);
    expect(useStore.getState().metrics.gpu).toBe(0); // Unchanged
  });

  it('supports subscribeWithSelector for fine-grained subscriptions', () => {
    const useStore = createImmerSelectorStore<MetricsState>((set) => ({
      metrics: { cpu: 0, gpu: 0, memory: 0 },
      lastUpdated: 0,
      updateMetric: (key, value) =>
        set((state) => {
          state.metrics[key] = value;
          state.lastUpdated = Date.now();
        }),
    }));

    const cpuCallback = vi.fn();
    const gpuCallback = vi.fn();

    // Subscribe to specific metrics using subscribeWithSelector overload
    const unsubCpu = (useStore.subscribe as any)(
      (state: MetricsState) => state.metrics.cpu,
      cpuCallback
    );
    const unsubGpu = (useStore.subscribe as any)(
      (state: MetricsState) => state.metrics.gpu,
      gpuCallback
    );

    // Update CPU - only CPU callback should fire
    act(() => {
      useStore.getState().updateMetric('cpu', 75);
    });

    expect(cpuCallback).toHaveBeenCalledTimes(1);
    expect(cpuCallback).toHaveBeenCalledWith(75, 0);
    expect(gpuCallback).not.toHaveBeenCalled();

    // Update GPU - only GPU callback should fire
    act(() => {
      useStore.getState().updateMetric('gpu', 80);
    });

    expect(cpuCallback).toHaveBeenCalledTimes(1); // Still 1
    expect(gpuCallback).toHaveBeenCalledTimes(1);
    expect(gpuCallback).toHaveBeenCalledWith(80, 0);

    // Cleanup
    unsubCpu();
    unsubGpu();
  });

  it('supports custom equality function in subscriptions', () => {
    interface ArrayState {
      items: number[];
      addItem: (item: number) => void;
    }

    const useStore = createImmerSelectorStore<ArrayState>((set) => ({
      items: [1, 2, 3],
      addItem: (item) =>
        set((state) => {
          state.items.push(item);
        }),
    }));

    const callback = vi.fn();

    // Subscribe with custom equality (array length)
    const unsub = (useStore.subscribe as any)((state: ArrayState) => state.items.length, callback, {
      equalityFn: (a: number, b: number) => a === b,
    });

    // Add item - should trigger
    act(() => {
      useStore.getState().addItem(4);
    });

    expect(callback).toHaveBeenCalledTimes(1);

    unsub();
  });
});

// ============================================================================
// DevTools Integration Tests (NEM-3785)
// ============================================================================

describe('DevTools middleware integration', () => {
  it('createImmerStore accepts devtools options', () => {
    const useStore = createImmerStore<NestedState>(
      (set) => ({
        nested: { deep: { value: 0, items: [] } },
        counter: 0,
        setDeepValue: (value) =>
          set((state) => {
            state.nested.deep.value = value;
          }),
        addItem: (item) =>
          set((state) => {
            state.nested.deep.items.push(item);
          }),
        increment: () =>
          set((state) => {
            state.counter += 1;
          }),
      }),
      { name: 'test-immer-store' }
    );

    // Store should be functional with devtools
    expect(useStore.getState().counter).toBe(0);

    act(() => {
      useStore.getState().increment();
    });

    expect(useStore.getState().counter).toBe(1);
  });

  it('createImmerSelectorStore accepts devtools options', () => {
    const useStore = createImmerSelectorStore<MetricsState>(
      (set) => ({
        metrics: { cpu: 0, gpu: 0, memory: 0 },
        lastUpdated: 0,
        updateMetric: (key, value) =>
          set((state) => {
            state.metrics[key] = value;
            state.lastUpdated = Date.now();
          }),
      }),
      { name: 'test-metrics-store' }
    );

    // Store should be functional with devtools
    expect(useStore.getState().metrics.cpu).toBe(0);

    act(() => {
      useStore.getState().updateMetric('cpu', 75);
    });

    expect(useStore.getState().metrics.cpu).toBe(75);
  });

  it('devtools can be explicitly disabled', () => {
    const useStore = createImmerStore<{ count: number }>(
      () => ({
        count: 0,
      }),
      { name: 'disabled-devtools-store', enabled: false }
    );

    // Store should still work with devtools disabled
    expect(useStore.getState().count).toBe(0);
  });
});

// ============================================================================
// createTransientBatcher Tests
// ============================================================================

describe('createTransientBatcher', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('batches rapid updates within batch window', () => {
    interface State {
      value: number;
    }

    const setState = vi.fn();
    const batcher = createTransientBatcher<State>(setState, { batchMs: 100 });

    // Fire multiple updates rapidly
    batcher(() => ({ value: 1 }));
    batcher(() => ({ value: 2 }));
    batcher(() => ({ value: 3 }));

    // Should not have called setState yet
    expect(setState).not.toHaveBeenCalled();

    // Advance time past batch window
    act(() => {
      vi.advanceTimersByTime(100);
    });

    // Now setState should be called once
    expect(setState).toHaveBeenCalledTimes(1);
  });

  it('flushes immediately when max batch size reached', () => {
    interface State {
      value: number;
    }

    const setState = vi.fn();
    const batcher = createTransientBatcher<State>(setState, {
      batchMs: 1000,
      maxBatchSize: 3,
    });

    // Fire updates up to max batch size
    batcher(() => ({ value: 1 }));
    batcher(() => ({ value: 2 }));

    // Should not flush yet
    expect(setState).not.toHaveBeenCalled();

    // Third update should trigger immediate flush
    batcher(() => ({ value: 3 }));

    expect(setState).toHaveBeenCalledTimes(1);
  });

  it('combines multiple updates into single state update', () => {
    interface State {
      a: number;
      b: number;
      c: number;
    }

    let lastUpdate: Partial<State> | null = null;
    const setState = vi.fn((partial: Partial<State> | ((state: State) => Partial<State>)) => {
      if (typeof partial === 'function') {
        lastUpdate = partial({ a: 0, b: 0, c: 0 });
      } else {
        lastUpdate = partial;
      }
    });

    const batcher = createTransientBatcher<State>(setState, { batchMs: 50 });

    batcher(() => ({ a: 1 }));
    batcher(() => ({ b: 2 }));
    batcher(() => ({ c: 3 }));

    act(() => {
      vi.advanceTimersByTime(50);
    });

    expect(lastUpdate).toEqual({ a: 1, b: 2, c: 3 });
  });
});

// ============================================================================
// createTransientSlice Tests
// ============================================================================

describe('createTransientSlice', () => {
  it('creates a transient slice with initial data', () => {
    interface GPUMetrics {
      utilization: number;
      memory: number;
    }

    const slice = createTransientSlice<GPUMetrics>({
      utilization: 0,
      memory: 0,
    });

    expect(slice.data).toEqual({ utilization: 0, memory: 0 });
    expect(slice.lastUpdated).toBeGreaterThan(0);
  });

  it('can be used in Immer store', () => {
    interface State {
      transient: TransientSlice<{ value: number }>;
      updateTransient: (value: number) => void;
    }

    const useStore = createImmerStore<State>((set) => ({
      transient: createTransientSlice({ value: 0 }),
      updateTransient: (value) =>
        set((state) => {
          state.transient.data.value = value;
          state.transient.lastUpdated = Date.now();
        }),
    }));

    expect(useStore.getState().transient.data.value).toBe(0);

    act(() => {
      useStore.getState().updateTransient(100);
    });

    expect(useStore.getState().transient.data.value).toBe(100);
  });
});

// ============================================================================
// Selector Utilities Tests
// ============================================================================

describe('createShallowSelector', () => {
  it('returns the selector function unchanged', () => {
    const selector = (state: { a: number; b: number }) => ({
      a: state.a,
    });

    const shallowSelector = createShallowSelector(selector);

    expect(shallowSelector).toBe(selector);
  });
});

describe('shallowEqual', () => {
  it('returns true for identical primitives', () => {
    expect(shallowEqual(1, 1)).toBe(true);
    expect(shallowEqual('test', 'test')).toBe(true);
    expect(shallowEqual(true, true)).toBe(true);
  });

  it('returns false for different primitives', () => {
    expect(shallowEqual(1, 2)).toBe(false);
    expect(shallowEqual('a', 'b')).toBe(false);
  });

  it('returns true for shallowly equal objects', () => {
    expect(shallowEqual({ a: 1, b: 2 }, { a: 1, b: 2 })).toBe(true);
  });

  it('returns false for objects with different values', () => {
    expect(shallowEqual({ a: 1 }, { a: 2 })).toBe(false);
  });

  it('returns true for shallowly equal arrays', () => {
    expect(shallowEqual([1, 2, 3], [1, 2, 3])).toBe(true);
  });

  it('returns false for arrays with different values', () => {
    expect(shallowEqual([1, 2], [1, 3])).toBe(false);
  });
});

// ============================================================================
// WebSocket Event Utilities Tests
// ============================================================================

describe('createWebSocketEventHandler', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('transforms and batches WebSocket events', () => {
    interface State {
      gpuUtilization: number;
      memoryUsed: number;
    }

    interface GPUEvent {
      gpu_utilization: number;
      memory_used: number;
    }

    const setState = vi.fn();
    const handler = createWebSocketEventHandler<State, GPUEvent>(
      setState,
      (event) => ({
        gpuUtilization: event.gpu_utilization,
        memoryUsed: event.memory_used,
      }),
      { batchMs: 100 }
    );

    // Simulate rapid events
    handler({ gpu_utilization: 50, memory_used: 1000 });
    handler({ gpu_utilization: 55, memory_used: 1100 });
    handler({ gpu_utilization: 60, memory_used: 1200 });

    // Should not have called setState yet
    expect(setState).not.toHaveBeenCalled();

    // Advance time
    act(() => {
      vi.advanceTimersByTime(100);
    });

    // Should batch all updates
    expect(setState).toHaveBeenCalledTimes(1);
  });
});

describe('createDebouncedUpdater', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('debounces rapid updates to the last value', () => {
    interface State {
      query: string;
    }

    const setState = vi.fn();
    const debouncedUpdate = createDebouncedUpdater<State>(setState, 200);

    // Rapid updates
    debouncedUpdate({ query: 'h' });
    debouncedUpdate({ query: 'he' });
    debouncedUpdate({ query: 'hel' });
    debouncedUpdate({ query: 'hell' });
    debouncedUpdate({ query: 'hello' });

    // Should not have called setState yet
    expect(setState).not.toHaveBeenCalled();

    // Advance time past debounce window
    act(() => {
      vi.advanceTimersByTime(200);
    });

    // Should only call with final value
    expect(setState).toHaveBeenCalledTimes(1);
    expect(setState).toHaveBeenCalledWith({ query: 'hello' });
  });

  it('resets debounce timer on new updates', () => {
    interface State {
      value: number;
    }

    const setState = vi.fn();
    const debouncedUpdate = createDebouncedUpdater<State>(setState, 100);

    debouncedUpdate({ value: 1 });

    // Advance 50ms
    act(() => {
      vi.advanceTimersByTime(50);
    });

    // New update should reset timer
    debouncedUpdate({ value: 2 });

    // Advance another 50ms (100ms total since first update)
    act(() => {
      vi.advanceTimersByTime(50);
    });

    // Should not have fired yet (timer reset)
    expect(setState).not.toHaveBeenCalled();

    // Advance remaining 50ms
    act(() => {
      vi.advanceTimersByTime(50);
    });

    // Now should fire with last value
    expect(setState).toHaveBeenCalledTimes(1);
    expect(setState).toHaveBeenCalledWith({ value: 2 });
  });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('middleware integration', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('combines Immer, selectors, and transient updates', () => {
    interface GPUMetrics {
      utilization: number;
      memory: number;
      temperature: number;
    }

    interface State {
      transient: TransientSlice<GPUMetrics>;
      alertThreshold: number;
      updateGPU: (metrics: Partial<GPUMetrics>) => void;
      setThreshold: (threshold: number) => void;
    }

    const useStore = createImmerSelectorStore<State>((set) => ({
      transient: createTransientSlice({ utilization: 0, memory: 0, temperature: 0 }),
      alertThreshold: 90,
      updateGPU: (metrics) =>
        set((state) => {
          Object.assign(state.transient.data, metrics);
          state.transient.lastUpdated = Date.now();
        }),
      setThreshold: (threshold) =>
        set((state) => {
          state.alertThreshold = threshold;
        }),
    }));

    // Track subscription calls
    const utilizationCallback = vi.fn();
    const thresholdCallback = vi.fn();

    // Subscribe to specific parts using subscribeWithSelector overload
    const unsubUtil = (useStore.subscribe as any)(
      (state: State) => state.transient.data.utilization,
      utilizationCallback
    );
    const unsubThresh = (useStore.subscribe as any)(
      (state: State) => state.alertThreshold,
      thresholdCallback
    );

    // Update GPU - should only trigger utilization callback
    act(() => {
      useStore.getState().updateGPU({ utilization: 75 });
    });

    expect(utilizationCallback).toHaveBeenCalledWith(75, 0);
    expect(thresholdCallback).not.toHaveBeenCalled();

    // Update threshold - should only trigger threshold callback
    act(() => {
      useStore.getState().setThreshold(85);
    });

    expect(utilizationCallback).toHaveBeenCalledTimes(1); // Still 1
    expect(thresholdCallback).toHaveBeenCalledWith(85, 90);

    // Cleanup
    unsubUtil();
    unsubThresh();
  });
});

// ============================================================================
// Advanced Immer Utilities Tests (NEM-3788)
// ============================================================================

describe('createImmerDevtoolsStore', () => {
  it('creates a store with Immer support', () => {
    interface State {
      items: string[];
      addItem: (item: string) => void;
    }

    const useStore = createImmerDevtoolsStore<State>(
      (set) => ({
        items: [],
        addItem: (item) =>
          set((draft) => {
            draft.items.push(item);
          }),
      }),
      { name: 'test-store', devtools: false }
    );

    expect(useStore.getState().items).toEqual([]);

    act(() => {
      useStore.getState().addItem('test');
    });

    expect(useStore.getState().items).toEqual(['test']);
  });

  it('creates a store with selector support', () => {
    interface State {
      count: number;
      increment: () => void;
    }

    const useStore = createImmerDevtoolsStore<State>(
      (set) => ({
        count: 0,
        increment: () =>
          set((draft) => {
            draft.count += 1;
          }),
      }),
      { withSelector: true, devtools: false }
    );

    const callback = vi.fn();
    const unsub = (useStore.subscribe as any)((state: State) => state.count, callback);

    act(() => {
      useStore.getState().increment();
    });

    expect(callback).toHaveBeenCalledWith(1, 0);

    unsub();
  });
});

describe('applyImmerUpdate', () => {
  it('applies immutable updates using Immer', () => {
    interface State {
      nested: { value: number };
    }

    const state: State = { nested: { value: 1 } };
    const newState = applyImmerUpdate(state, (draft) => {
      draft.nested.value = 2;
    });

    // Original should be unchanged
    expect(state.nested.value).toBe(1);
    // New state should have update
    expect(newState.nested.value).toBe(2);
    // Should be different references
    expect(newState).not.toBe(state);
    expect(newState.nested).not.toBe(state.nested);
  });
});

describe('createImmerAction', () => {
  it('creates a reusable action function', () => {
    interface TodoState {
      todos: { id: string; done: boolean }[];
    }

    const toggleTodo = createImmerAction<TodoState, [id: string]>((draft, id) => {
      const todo = draft.todos.find((t) => t.id === id);
      if (todo) todo.done = !todo.done;
    });

    const state: TodoState = { todos: [{ id: '1', done: false }] };
    const newState = applyImmerUpdate(state, (draft) => toggleTodo(draft, '1'));

    expect(newState.todos[0].done).toBe(true);
    expect(state.todos[0].done).toBe(false);
  });
});

describe('safeReadCurrent', () => {
  it('returns the value for non-draft objects', () => {
    const obj = { value: 1 };
    expect(safeReadCurrent(obj)).toBe(obj);
  });

  it('returns primitives as-is', () => {
    expect(safeReadCurrent(42)).toBe(42);
    expect(safeReadCurrent('test')).toBe('test');
  });
});

describe('createComputedSelector', () => {
  it('memoizes selector results', () => {
    interface State {
      items: number[];
    }

    const computeFn = vi.fn((state: State) => state.items.filter((n) => n > 5));
    const selector = createComputedSelector(computeFn);

    const state1: State = { items: [1, 6, 3, 8] };

    // First call
    const result1 = selector(state1);
    expect(result1).toEqual([6, 8]);
    expect(computeFn).toHaveBeenCalledTimes(1);

    // Same state - should use cached result
    const result2 = selector(state1);
    expect(result2).toBe(result1);
    expect(computeFn).toHaveBeenCalledTimes(1);

    // Different state - should recompute
    const state2: State = { items: [1, 6, 3, 8, 10] };
    const result3 = selector(state2);
    expect(result3).toEqual([6, 8, 10]);
    expect(computeFn).toHaveBeenCalledTimes(2);
  });
});

describe('combineImmerUpdates', () => {
  it('combines multiple updates into one', () => {
    interface State {
      a: number;
      b: number;
      c: number;
    }

    const state: State = { a: 0, b: 0, c: 0 };

    const combined = combineImmerUpdates<State>(
      (draft) => {
        draft.a = 1;
      },
      (draft) => {
        draft.b = 2;
      },
      (draft) => {
        draft.c = 3;
      }
    );

    const newState = applyImmerUpdate(state, combined);

    expect(newState).toEqual({ a: 1, b: 2, c: 3 });
    expect(state).toEqual({ a: 0, b: 0, c: 0 });
  });

  it('applies updates in order', () => {
    interface State {
      value: number;
    }

    const state: State = { value: 0 };

    const combined = combineImmerUpdates<State>(
      (draft) => {
        draft.value = 1;
      },
      (draft) => {
        draft.value = draft.value + 10;
      },
      (draft) => {
        draft.value = draft.value * 2;
      }
    );

    const newState = applyImmerUpdate(state, combined);

    // (0 -> 1) -> (1 + 10 = 11) -> (11 * 2 = 22)
    expect(newState.value).toBe(22);
  });
});
