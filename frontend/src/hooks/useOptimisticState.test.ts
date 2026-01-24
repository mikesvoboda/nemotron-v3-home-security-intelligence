/**
 * Tests for useOptimisticState hooks (NEM-3355)
 *
 * Tests React 19 useOptimistic-based utilities.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import {
  useOptimisticToggle,
  useOptimisticList,
  useOptimisticValue,
  useOptimisticAction,
  createOptimisticReducer,
} from './useOptimisticState';

describe('useOptimisticToggle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns initial value', () => {
    const { result } = renderHook(() => useOptimisticToggle(false));
    expect(result.current.optimisticValue).toBe(false);
    expect(result.current.isPending).toBe(false);
  });

  it('returns true when initial value is true', () => {
    const { result } = renderHook(() => useOptimisticToggle(true));
    expect(result.current.optimisticValue).toBe(true);
  });

  it('toggle updates optimistically', () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useOptimisticToggle(false));

    act(() => {
      result.current.toggle(action);
    });

    // Optimistic update should be immediate
    expect(result.current.optimisticValue).toBe(true);
    expect(action).toHaveBeenCalled();
  });

  it('setOptimistic sets specific value', () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useOptimisticToggle(false));

    act(() => {
      result.current.setOptimistic(true, action);
    });

    expect(result.current.optimisticValue).toBe(true);
    expect(action).toHaveBeenCalled();
  });

  it('updates when current value changes', () => {
    const { result, rerender } = renderHook(({ value }) => useOptimisticToggle(value), {
      initialProps: { value: false },
    });

    expect(result.current.optimisticValue).toBe(false);

    rerender({ value: true });
    expect(result.current.optimisticValue).toBe(true);
  });
});

describe('useOptimisticList', () => {
  interface Item {
    id: string;
    name: string;
  }

  const initialItems: Item[] = [
    { id: '1', name: 'Item 1' },
    { id: '2', name: 'Item 2' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns initial items', () => {
    const { result } = renderHook(() => useOptimisticList(initialItems));
    expect(result.current.optimisticItems).toEqual(initialItems);
    expect(result.current.isPending).toBe(false);
  });

  it('addItem adds item optimistically', () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useOptimisticList(initialItems));

    const newItem = { id: '3', name: 'Item 3' };

    act(() => {
      result.current.addItem(newItem, action);
    });

    expect(result.current.optimisticItems).toHaveLength(3);
    expect(result.current.optimisticItems[2]).toEqual(newItem);
    expect(action).toHaveBeenCalled();
  });

  it('removeItem removes item optimistically', () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useOptimisticList(initialItems));

    act(() => {
      result.current.removeItem((item) => item.id === '1', action);
    });

    expect(result.current.optimisticItems).toHaveLength(1);
    expect(result.current.optimisticItems[0].id).toBe('2');
    expect(action).toHaveBeenCalled();
  });

  it('updateItem updates item optimistically', () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useOptimisticList(initialItems));

    act(() => {
      result.current.updateItem((item) => item.id === '1', { name: 'Updated' }, action);
    });

    expect(result.current.optimisticItems[0].name).toBe('Updated');
    expect(result.current.optimisticItems[1].name).toBe('Item 2');
    expect(action).toHaveBeenCalled();
  });

  it('updates when items prop changes', () => {
    const { result, rerender } = renderHook(({ items }) => useOptimisticList(items), {
      initialProps: { items: initialItems },
    });

    expect(result.current.optimisticItems).toHaveLength(2);

    const newItems = [...initialItems, { id: '3', name: 'Item 3' }];
    rerender({ items: newItems });

    expect(result.current.optimisticItems).toHaveLength(3);
  });
});

describe('useOptimisticValue', () => {
  interface Settings {
    theme: string;
    notifications: boolean;
  }

  const initialSettings: Settings = {
    theme: 'light',
    notifications: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns initial value', () => {
    const { result } = renderHook(() => useOptimisticValue(initialSettings));
    expect(result.current.optimisticValue).toEqual(initialSettings);
    expect(result.current.isPending).toBe(false);
  });

  it('updateValue replaces value optimistically', () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useOptimisticValue(initialSettings));

    const newSettings: Settings = { theme: 'dark', notifications: false };

    act(() => {
      result.current.updateValue(newSettings, action);
    });

    expect(result.current.optimisticValue).toEqual(newSettings);
    expect(action).toHaveBeenCalled();
  });

  it('updatePartial merges partial update optimistically', () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useOptimisticValue(initialSettings));

    act(() => {
      result.current.updatePartial({ theme: 'dark' }, action);
    });

    expect(result.current.optimisticValue).toEqual({
      theme: 'dark',
      notifications: true,
    });
    expect(action).toHaveBeenCalled();
  });

  it('works with primitive values', () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useOptimisticValue(42));

    act(() => {
      result.current.updateValue(100, action);
    });

    expect(result.current.optimisticValue).toBe(100);
  });
});

describe('useOptimisticAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns initial state', () => {
    const { result } = renderHook(() =>
      useOptimisticAction({
        state: 0,
        updateFn: (current, delta: number) => current + delta,
      })
    );

    expect(result.current.optimisticState).toBe(0);
    expect(result.current.isPending).toBe(false);
  });

  it('execute applies optimistic update', () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() =>
      useOptimisticAction({
        state: 0,
        updateFn: (current, delta: number) => current + delta,
      })
    );

    act(() => {
      result.current.execute(5, action);
    });

    expect(result.current.optimisticState).toBe(5);
    expect(action).toHaveBeenCalled();
  });

  it('calls onSuccess callback on successful action', async () => {
    const action = vi.fn().mockResolvedValue(undefined);
    const onSuccess = vi.fn();
    const { result } = renderHook(() =>
      useOptimisticAction({
        state: 0,
        updateFn: (current, delta: number) => current + delta,
        onSuccess,
      })
    );

    await act(async () => {
      result.current.execute(5, action);
      await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    });
  });

  it('calls onError callback on failed action', async () => {
    const error = new Error('Test error');
    const action = vi.fn().mockRejectedValue(error);
    const onError = vi.fn();
    const { result } = renderHook(() =>
      useOptimisticAction({
        state: 0,
        updateFn: (current, delta: number) => current + delta,
        onError,
      })
    );

    await act(async () => {
      result.current.execute(5, action);
      await waitFor(() => expect(onError).toHaveBeenCalledWith(error));
    });
  });

  it('converts non-Error to Error in onError', async () => {
    const action = vi.fn().mockRejectedValue('string error');
    const onError = vi.fn();
    const { result } = renderHook(() =>
      useOptimisticAction({
        state: 0,
        updateFn: (current, delta: number) => current + delta,
        onError,
      })
    );

    await act(async () => {
      result.current.execute(5, action);
      await waitFor(() => {
        expect(onError).toHaveBeenCalled();
        expect(onError.mock.calls[0][0]).toBeInstanceOf(Error);
      });
    });
  });
});

describe('createOptimisticReducer', () => {
  type CartAction =
    | { type: 'addItem'; item: { id: string; quantity: number } }
    | { type: 'removeItem'; itemId: string }
    | { type: 'updateQuantity'; itemId: string; quantity: number };

  interface CartState {
    items: Array<{ id: string; quantity: number }>;
    total: number;
  }

  const initialCart: CartState = {
    items: [{ id: '1', quantity: 1 }],
    total: 10,
  };

  it('creates a working reducer', () => {
    const reducer = createOptimisticReducer<CartState, CartAction>({
      addItem: (state, action) => ({
        ...state,
        items: [...state.items, action.item],
      }),
      removeItem: (state, action) => ({
        ...state,
        items: state.items.filter((i) => i.id !== action.itemId),
      }),
      updateQuantity: (state, action) => ({
        ...state,
        items: state.items.map((i) =>
          i.id === action.itemId ? { ...i, quantity: action.quantity } : i
        ),
      }),
    });

    // Test addItem
    const afterAdd = reducer(initialCart, {
      type: 'addItem',
      item: { id: '2', quantity: 2 },
    });
    expect(afterAdd.items).toHaveLength(2);

    // Test removeItem
    const afterRemove = reducer(initialCart, {
      type: 'removeItem',
      itemId: '1',
    });
    expect(afterRemove.items).toHaveLength(0);

    // Test updateQuantity
    const afterUpdate = reducer(initialCart, {
      type: 'updateQuantity',
      itemId: '1',
      quantity: 5,
    });
    expect(afterUpdate.items[0].quantity).toBe(5);
  });

  it('returns unchanged state for unknown action type', () => {
    const reducer = createOptimisticReducer<CartState, CartAction>({
      addItem: (state) => state,
      removeItem: (state) => state,
      updateQuantity: (state) => state,
    });

    // @ts-expect-error - Testing unknown action
    const result = reducer(initialCart, { type: 'unknown' });
    expect(result).toBe(initialCart);
  });
});
