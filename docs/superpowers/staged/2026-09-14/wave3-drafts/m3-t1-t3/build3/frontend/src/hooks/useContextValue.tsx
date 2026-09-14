/**
 * useContextValue - React 19 use() hook utilities (NEM-3357)
 *
 * This module provides utilities for React 19's `use()` hook, which can:
 * - Read context values (replacing useContext in many cases)
 * - Resolve promises directly in components
 * - Be called conditionally (unlike other hooks)
 *
 * Key benefits over useContext:
 * - Can be called conditionally
 * - Works with promises for data fetching
 * - Integrates with Suspense boundaries
 *
 * @module hooks/useContextValue
 * @see https://react.dev/reference/react/use
 */

import { use, createContext, type Context, ReactNode } from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Factory result for context with use() hook
 */
export interface ContextWithUse<T> {
  /** The React context */
  Context: Context<T | null>;
  /** Provider component */
  Provider: React.FC<{ value: T; children: ReactNode }>;
  /** Hook using React 19's use() - throws if no provider */
  useValue: () => T;
  /** Hook using React 19's use() - returns null if no provider */
  useValueOptional: () => T | null;
  /** Display name for DevTools */
  displayName: string;
}

/**
 * Options for createContextWithUse
 */
export interface CreateContextWithUseOptions {
  /** Display name for React DevTools */
  displayName: string;
  /** Custom error message when used outside provider */
  errorMessage?: string;
}

/**
 * Result from usePromise
 */
export interface UsePromiseResult<T> {
  /** Resolved data (suspends while loading) */
  data: T;
}

/**
 * Result from useConditionalContext
 */
export interface UseConditionalContextResult<T> {
  /** Whether the context is available */
  isAvailable: boolean;
  /** The context value (null if not available) */
  value: T | null;
}

// ============================================================================
// createContextWithUse - Factory for context with use() hook
// ============================================================================

/**
 * Creates a context with React 19's use() hook for reading values.
 *
 * This factory creates a context that can be read using the new `use()` hook,
 * which allows conditional context reading (something useContext can't do).
 *
 * @param options - Configuration options
 * @returns Context, Provider, and hooks
 *
 * @example
 * ```tsx
 * // Create the context
 * const { Context, Provider, useValue } = createContextWithUse<User>({
 *   displayName: 'UserContext',
 * });
 *
 * // Use in provider
 * function App() {
 *   return (
 *     <Provider value={currentUser}>
 *       <UserProfile />
 *     </Provider>
 *   );
 * }
 *
 * // Use in component - can be conditional!
 * function UserProfile() {
 *   const user = useValue(); // Uses use() internally
 *   return <div>{user.name}</div>;
 * }
 *
 * // Conditional usage (not possible with useContext)
 * function MaybeUserInfo({ showUser }: { showUser: boolean }) {
 *   if (!showUser) return null;
 *   const user = useValue(); // OK! use() can be conditional
 *   return <div>{user.name}</div>;
 * }
 * ```
 */
export function createContextWithUse<T>(options: CreateContextWithUseOptions): ContextWithUse<T> {
  const { displayName, errorMessage } = options;

  const Context = createContext<T | null>(null);
  Context.displayName = displayName;

  const Provider: React.FC<{ value: T; children: ReactNode }> = ({ value, children }) => {
    return <Context.Provider value={value}>{children}</Context.Provider>;
  };
  Provider.displayName = `${displayName}.Provider`;

  const useValue = (): T => {
    const value = use(Context);
    if (value === null) {
      throw new Error(
        errorMessage ?? `${displayName} must be used within a ${displayName}.Provider`
      );
    }
    return value;
  };

  const useValueOptional = (): T | null => {
    return use(Context);
  };

  return {
    Context,
    Provider,
    useValue,
    useValueOptional,
    displayName,
  };
}

// ============================================================================
// usePromiseValue - Read promise value with Suspense
// ============================================================================

/**
 * Reads a promise value using React 19's use() hook.
 *
 * This suspends the component until the promise resolves.
 * Must be used within a Suspense boundary.
 *
 * @param promise - Promise to resolve
 * @returns The resolved value
 *
 * @example
 * ```tsx
 * async function fetchUser(id: string): Promise<User> {
 *   const response = await fetch(`/api/users/${id}`);
 *   return response.json();
 * }
 *
 * function UserProfile({ userId }: { userId: string }) {
 *   // Create promise outside component or memoize it
 *   const userPromise = useMemo(() => fetchUser(userId), [userId]);
 *
 *   // This suspends until the promise resolves
 *   const user = usePromiseValue(userPromise);
 *
 *   return <div>{user.name}</div>;
 * }
 *
 * // Wrap with Suspense
 * function App() {
 *   return (
 *     <Suspense fallback={<Loading />}>
 *       <UserProfile userId="123" />
 *     </Suspense>
 *   );
 * }
 * ```
 */
export function usePromiseValue<T>(promise: Promise<T>): T {
  return use(promise);
}

// ============================================================================
// useConditionalContext - Conditionally read context
// ============================================================================

/**
 * Conditionally reads a context value using React 19's use() hook.
 *
 * Unlike useContext, this can be called conditionally based on a flag.
 * Returns null and isAvailable=false when condition is false.
 *
 * @param context - React context to read
 * @param condition - Whether to read the context
 * @returns Object with value and availability flag
 *
 * @example
 * ```tsx
 * function FeatureComponent({ enabled }: { enabled: boolean }) {
 *   // Can conditionally read context - not possible with useContext!
 *   const { isAvailable, value } = useConditionalContext(FeatureContext, enabled);
 *
 *   if (!isAvailable) {
 *     return <div>Feature disabled</div>;
 *   }
 *
 *   return <div>Feature value: {value.setting}</div>;
 * }
 * ```
 */
export function useConditionalContext<T>(
  context: Context<T>,
  condition: boolean
): UseConditionalContextResult<T> {
  if (!condition) {
    return { isAvailable: false, value: null };
  }

  // use() can be called conditionally - this is the key benefit!
  const value = use(context);
  return { isAvailable: true, value };
}

// ============================================================================
// useContextOrDefault - Read context with fallback
// ============================================================================

/**
 * Reads a context value with a fallback default.
 *
 * Uses React 19's use() hook internally, returning the default
 * value if the context value is null/undefined.
 *
 * @param context - React context to read
 * @param defaultValue - Fallback value if context is null
 * @returns Context value or default
 *
 * @example
 * ```tsx
 * const ThemeContext = createContext<Theme | null>(null);
 *
 * function ThemedButton() {
 *   // Returns defaultTheme if no provider above
 *   const theme = useContextOrDefault(ThemeContext, defaultTheme);
 *   return <button style={{ color: theme.primaryColor }}>Click</button>;
 * }
 * ```
 */
export function useContextOrDefault<T>(context: Context<T | null>, defaultValue: T): T {
  const value = use(context);
  return value ?? defaultValue;
}

// ============================================================================
// createSuspenseResource - Create a resource for Suspense
// ============================================================================

/**
 * Status of a suspense resource
 */
type ResourceStatus = 'pending' | 'success' | 'error';

/**
 * A suspense-compatible resource
 */
export interface SuspenseResource<T> {
  /** Read the resource value (suspends if pending, throws if error) */
  read: () => T;
  /** Current status */
  status: ResourceStatus;
  /** Preload the resource */
  preload: () => void;
}

/**
 * Creates a suspense-compatible resource from a promise factory.
 *
 * This is useful for data fetching patterns where you want to
 * trigger loading before render and read data during render.
 *
 * @param promiseFactory - Function that returns the data promise
 * @returns Suspense resource
 *
 * @example
 * ```tsx
 * // Create resource outside component
 * const userResource = createSuspenseResource(() => fetchUser('123'));
 *
 * // Preload before navigation
 * userResource.preload();
 *
 * // Use in component
 * function UserProfile() {
 *   const user = userResource.read(); // Suspends until loaded
 *   return <div>{user.name}</div>;
 * }
 * ```
 */
export function createSuspenseResource<T>(promiseFactory: () => Promise<T>): SuspenseResource<T> {
  let status: ResourceStatus = 'pending';
  let result: T;
  let error: Error;
  let promise: Promise<void> | null = null;

  const load = (): Promise<void> => {
    if (promise) return promise;

    promise = promiseFactory()
      .then((data) => {
        status = 'success';
        result = data;
      })
      .catch((e) => {
        status = 'error';
        error = e instanceof Error ? e : new Error(String(e));
      });

    return promise;
  };

  return {
    read: (): T => {
      switch (status) {
        case 'pending':
          // eslint-disable-next-line @typescript-eslint/only-throw-error
          throw load();
        case 'error':
          throw error;
        case 'success':
          return result;
      }
    },
    get status() {
      return status;
    },
    preload: () => {
      void load();
    },
  };
}

// ============================================================================
// wrapPromise - Simple promise wrapper for Suspense
// ============================================================================

/**
 * Wraps a promise for use with React Suspense.
 *
 * This is a simpler version of createSuspenseResource for one-off use cases.
 *
 * @param promise - Promise to wrap
 * @returns Function that reads the promise value (suspends if pending)
 *
 * @example
 * ```tsx
 * // Wrap a promise
 * const readUser = wrapPromise(fetchUser('123'));
 *
 * function UserProfile() {
 *   const user = readUser(); // Suspends until resolved
 *   return <div>{user.name}</div>;
 * }
 * ```
 */
export function wrapPromise<T>(promise: Promise<T>): () => T {
  let status: 'pending' | 'success' | 'error' = 'pending';
  let result: T;
  let error: Error;

  const suspender = promise
    .then((data) => {
      status = 'success';
      result = data;
    })
    .catch((e) => {
      status = 'error';
      error = e instanceof Error ? e : new Error(String(e));
    });

  return (): T => {
    switch (status) {
      case 'pending':
        // eslint-disable-next-line @typescript-eslint/only-throw-error
        throw suspender;
      case 'error':
        throw error;
      case 'success':
        return result;
    }
  };
}
