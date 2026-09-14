/**
 * useOptimisticState - React 19 useOptimistic hook utilities (NEM-3355)
 *
 * This module provides utilities for using React 19's native `useOptimistic` hook
 * for instant UI feedback on user actions. Unlike TanStack Query's optimistic
 * mutations (which manage server state), this hook manages local optimistic state
 * that reverts automatically after the action completes.
 *
 * Key differences from TanStack Query optimistic updates:
 * - React primitive: No external library dependency
 * - Synchronous: Updates are immediate, no async handling needed
 * - Auto-revert: State automatically reverts when the action settles
 * - Composable: Can be combined with any async operation
 *
 * @module hooks/useOptimisticState
 * @see https://react.dev/reference/react/useOptimistic
 */

import { useOptimistic, useTransition, useCallback } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Optimistic update function type
 */
export type OptimisticUpdateFn<TState, TAction> = (
  currentState: TState,
  optimisticValue: TAction
) => TState;

/**
 * Result from useOptimisticToggle
 */
export interface UseOptimisticToggleReturn {
  /** Current optimistic value */
  optimisticValue: boolean;
  /** Whether an action is pending */
  isPending: boolean;
  /** Toggle with optimistic feedback */
  toggle: (action: () => Promise<void>) => void;
  /** Set to specific value with optimistic feedback */
  setOptimistic: (value: boolean, action: () => Promise<void>) => void;
}

/**
 * Result from useOptimisticList
 */
export interface UseOptimisticListReturn<T> {
  /** Current optimistic list */
  optimisticItems: T[];
  /** Whether an action is pending */
  isPending: boolean;
  /** Add item with optimistic feedback */
  addItem: (item: T, action: () => Promise<void>) => void;
  /** Remove item with optimistic feedback */
  removeItem: (predicate: (item: T) => boolean, action: () => Promise<void>) => void;
  /** Update item with optimistic feedback */
  updateItem: (
    predicate: (item: T) => boolean,
    update: Partial<T>,
    action: () => Promise<void>
  ) => void;
}

/**
 * Result from useOptimisticValue
 */
export interface UseOptimisticValueReturn<T> {
  /** Current optimistic value */
  optimisticValue: T;
  /** Whether an action is pending */
  isPending: boolean;
  /** Update value with optimistic feedback */
  updateValue: (newValue: T, action: () => Promise<void>) => void;
  /** Partially update value (for objects) with optimistic feedback */
  updatePartial: (partial: Partial<T>, action: () => Promise<void>) => void;
}

/**
 * Options for useOptimisticAction
 */
export interface UseOptimisticActionOptions<TState, TAction> {
  /** Initial/current state */
  state: TState;
  /** Function to compute optimistic state from action */
  updateFn: OptimisticUpdateFn<TState, TAction>;
  /** Optional callback on action success */
  onSuccess?: () => void;
  /** Optional callback on action error */
  onError?: (error: Error) => void;
}

/**
 * Result from useOptimisticAction
 */
export interface UseOptimisticActionReturn<TState, TAction> {
  /** Current optimistic state */
  optimisticState: TState;
  /** Whether an action is pending */
  isPending: boolean;
  /** Execute action with optimistic update */
  execute: (optimisticValue: TAction, action: () => Promise<void>) => void;
}

// ============================================================================
// useOptimisticToggle - Boolean toggle with optimistic feedback
// ============================================================================

/**
 * Hook for optimistic boolean toggle state.
 *
 * Provides instant UI feedback for toggle actions (switches, checkboxes)
 * that revert automatically if the action fails.
 *
 * @param currentValue - The current server-side boolean value
 * @returns Toggle utilities with optimistic state
 *
 * @example
 * ```tsx
 * function CameraToggle({ camera }: { camera: Camera }) {
 *   const { mutateAsync } = useCameraMutation();
 *   const { optimisticValue, isPending, toggle } = useOptimisticToggle(camera.enabled);
 *
 *   return (
 *     <Switch
 *       checked={optimisticValue}
 *       disabled={isPending}
 *       onChange={() => toggle(async () => {
 *         await mutateAsync({ id: camera.id, enabled: !camera.enabled });
 *       })}
 *     />
 *   );
 * }
 * ```
 */
export function useOptimisticToggle(currentValue: boolean): UseOptimisticToggleReturn {
  const [optimisticValue, setOptimisticValue] = useOptimistic(
    currentValue,
    (_current: boolean, newValue: boolean) => newValue
  );
  const [isPending, startTransition] = useTransition();

  const toggle = useCallback(
    (action: () => Promise<void>) => {
      startTransition(async () => {
        setOptimisticValue(!optimisticValue);
        await action();
      });
    },
    [optimisticValue, setOptimisticValue]
  );

  const setOptimistic = useCallback(
    (value: boolean, action: () => Promise<void>) => {
      startTransition(async () => {
        setOptimisticValue(value);
        await action();
      });
    },
    [setOptimisticValue]
  );

  return {
    optimisticValue,
    isPending,
    toggle,
    setOptimistic,
  };
}

// ============================================================================
// useOptimisticList - List operations with optimistic feedback
// ============================================================================

/**
 * Hook for optimistic list state management.
 *
 * Provides instant UI feedback for list operations (add, remove, update)
 * that revert automatically if the action fails.
 *
 * @param currentItems - The current server-side list
 * @returns List manipulation utilities with optimistic state
 *
 * @example
 * ```tsx
 * function QuietHoursList({ periods }: { periods: QuietHoursPeriod[] }) {
 *   const { createPeriod, deletePeriod } = useQuietHoursMutations();
 *   const { optimisticItems, addItem, removeItem } = useOptimisticList(periods);
 *
 *   const handleAdd = (newPeriod: QuietHoursPeriod) => {
 *     addItem(newPeriod, async () => {
 *       await createPeriod.mutateAsync(newPeriod);
 *     });
 *   };
 *
 *   const handleDelete = (id: string) => {
 *     removeItem(
 *       item => item.id === id,
 *       async () => { await deletePeriod.mutateAsync(id); }
 *     );
 *   };
 *
 *   return (
 *     <ul>
 *       {optimisticItems.map(period => (
 *         <li key={period.id}>{period.label}</li>
 *       ))}
 *     </ul>
 *   );
 * }
 * ```
 */
export function useOptimisticList<T>(currentItems: T[]): UseOptimisticListReturn<T> {
  type ListAction =
    | { type: 'add'; item: T }
    | { type: 'remove'; predicate: (item: T) => boolean }
    | { type: 'update'; predicate: (item: T) => boolean; update: Partial<T> };

  const [optimisticItems, setOptimisticItems] = useOptimistic(
    currentItems,
    (current: T[], action: ListAction) => {
      switch (action.type) {
        case 'add':
          return [...current, action.item];
        case 'remove':
          return current.filter((item) => !action.predicate(item));
        case 'update':
          return current.map((item) =>
            action.predicate(item) ? { ...item, ...action.update } : item
          );
        default:
          return current;
      }
    }
  );

  const [isPending, startTransition] = useTransition();

  const addItem = useCallback(
    (item: T, action: () => Promise<void>) => {
      startTransition(async () => {
        setOptimisticItems({ type: 'add', item });
        await action();
      });
    },
    [setOptimisticItems]
  );

  const removeItem = useCallback(
    (predicate: (item: T) => boolean, action: () => Promise<void>) => {
      startTransition(async () => {
        setOptimisticItems({ type: 'remove', predicate });
        await action();
      });
    },
    [setOptimisticItems]
  );

  const updateItem = useCallback(
    (predicate: (item: T) => boolean, update: Partial<T>, action: () => Promise<void>) => {
      startTransition(async () => {
        setOptimisticItems({ type: 'update', predicate, update });
        await action();
      });
    },
    [setOptimisticItems]
  );

  return {
    optimisticItems,
    isPending,
    addItem,
    removeItem,
    updateItem,
  };
}

// ============================================================================
// useOptimisticValue - Generic value with optimistic feedback
// ============================================================================

/**
 * Hook for optimistic value state management.
 *
 * Provides instant UI feedback for value changes that revert
 * automatically if the action fails.
 *
 * @param currentValue - The current server-side value
 * @returns Value manipulation utilities with optimistic state
 *
 * @example
 * ```tsx
 * function SettingsForm({ settings }: { settings: Settings }) {
 *   const { mutateAsync } = useSettingsMutation();
 *   const { optimisticValue, updatePartial } = useOptimisticValue(settings);
 *
 *   const handleChange = (field: keyof Settings, value: unknown) => {
 *     updatePartial(
 *       { [field]: value },
 *       async () => { await mutateAsync({ [field]: value }); }
 *     );
 *   };
 *
 *   return <input value={optimisticValue.name} onChange={...} />;
 * }
 * ```
 */
export function useOptimisticValue<T>(currentValue: T): UseOptimisticValueReturn<T> {
  type ValueAction = { type: 'set'; value: T } | { type: 'partial'; partial: Partial<T> };

  const [optimisticValue, setOptimisticValue] = useOptimistic(
    currentValue,
    (current: T, action: ValueAction) => {
      switch (action.type) {
        case 'set':
          return action.value;
        case 'partial':
          return { ...current, ...action.partial };
        default:
          return current;
      }
    }
  );

  const [isPending, startTransition] = useTransition();

  const updateValue = useCallback(
    (newValue: T, action: () => Promise<void>) => {
      startTransition(async () => {
        setOptimisticValue({ type: 'set', value: newValue });
        await action();
      });
    },
    [setOptimisticValue]
  );

  const updatePartial = useCallback(
    (partial: Partial<T>, action: () => Promise<void>) => {
      startTransition(async () => {
        setOptimisticValue({ type: 'partial', partial });
        await action();
      });
    },
    [setOptimisticValue]
  );

  return {
    optimisticValue,
    isPending,
    updateValue,
    updatePartial,
  };
}

// ============================================================================
// useOptimisticAction - Generic optimistic action executor
// ============================================================================

/**
 * Hook for generic optimistic actions with custom update logic.
 *
 * Provides a flexible way to execute async actions with optimistic
 * state updates using a custom reducer function.
 *
 * @param options - Configuration options
 * @returns Action executor with optimistic state
 *
 * @example
 * ```tsx
 * function Counter({ count, onIncrement }: Props) {
 *   const { optimisticState, isPending, execute } = useOptimisticAction({
 *     state: count,
 *     updateFn: (current, delta) => current + delta,
 *   });
 *
 *   return (
 *     <button
 *       onClick={() => execute(1, onIncrement)}
 *       disabled={isPending}
 *     >
 *       Count: {optimisticState}
 *     </button>
 *   );
 * }
 * ```
 */
export function useOptimisticAction<TState, TAction>(
  options: UseOptimisticActionOptions<TState, TAction>
): UseOptimisticActionReturn<TState, TAction> {
  const { state, updateFn, onSuccess, onError } = options;

  const [optimisticState, setOptimisticState] = useOptimistic(state, updateFn);
  const [isPending, startTransition] = useTransition();

  const execute = useCallback(
    (optimisticValue: TAction, action: () => Promise<void>) => {
      startTransition(async () => {
        setOptimisticState(optimisticValue);
        try {
          await action();
          onSuccess?.();
        } catch (error) {
          onError?.(error instanceof Error ? error : new Error(String(error)));
        }
      });
    },
    [setOptimisticState, onSuccess, onError]
  );

  return {
    optimisticState,
    isPending,
    execute,
  };
}

// ============================================================================
// createOptimisticReducer - Helper for creating optimistic reducers
// ============================================================================

/**
 * Creates a type-safe optimistic reducer for complex state updates.
 *
 * @param handlers - Object mapping action types to handlers
 * @returns Reducer function for useOptimistic
 *
 * @example
 * ```tsx
 * const cartReducer = createOptimisticReducer<CartState, CartAction>({
 *   addItem: (state, { item }) => ({
 *     ...state,
 *     items: [...state.items, item],
 *   }),
 *   removeItem: (state, { itemId }) => ({
 *     ...state,
 *     items: state.items.filter(i => i.id !== itemId),
 *   }),
 *   updateQuantity: (state, { itemId, quantity }) => ({
 *     ...state,
 *     items: state.items.map(i =>
 *       i.id === itemId ? { ...i, quantity } : i
 *     ),
 *   }),
 * });
 * ```
 */
export function createOptimisticReducer<TState, TAction extends { type: string }>(handlers: {
  [K in TAction['type']]: (state: TState, action: Extract<TAction, { type: K }>) => TState;
}): OptimisticUpdateFn<TState, TAction> {
  return (state: TState, action: TAction): TState => {
    const handler = handlers[action.type as TAction['type']];
    // @ts-expect-error - TypeScript can't narrow the action type here
    return handler ? handler(state, action) : state;
  };
}
