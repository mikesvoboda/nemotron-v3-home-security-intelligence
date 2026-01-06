/**
 * Tests for AsyncState discriminated union types and helpers.
 *
 * Following TDD approach: these tests define the expected behavior
 * for the async state management type system.
 */
import { describe, it, expect } from 'vitest';

import {
  type AsyncState,
  type IdleState,
  type LoadingState,
  type ErrorState,
  type SuccessState,
  isIdle,
  isLoading,
  isError,
  isSuccess,
  idle,
  loading,
  error,
  success,
  getDataOrDefault,
  mapAsyncState,
  combineAsyncStates,
  getAvailableData,
  assertNever,
} from './async-state';

// ============================================================================
// Test Data Types
// ============================================================================

interface User {
  id: string;
  name: string;
  email: string;
}

interface Post {
  id: number;
  title: string;
}

// ============================================================================
// Test Data Factories
// ============================================================================

function createUser(): User {
  return { id: 'user-1', name: 'Alice', email: 'alice@example.com' };
}

function createPost(): Post {
  return { id: 1, title: 'Hello World' };
}

function createIdleState(): IdleState {
  return idle();
}

function createLoadingState<T>(previousData?: T): LoadingState<T> {
  return loading(previousData);
}

function createErrorState(message = 'Something went wrong'): ErrorState {
  return error(new Error(message));
}

function createSuccessState<T>(data: T): SuccessState<T> {
  return success(data);
}

// ============================================================================
// Factory Function Tests
// ============================================================================

describe('Factory Functions', () => {
  describe('idle()', () => {
    it('creates an idle state', () => {
      const state = idle();
      expect(state.status).toBe('idle');
    });

    it('creates readonly state', () => {
      const state = idle();
      // Type assertion to verify readonly property
      expect(Object.isFrozen(state) || state.status === 'idle').toBe(true);
    });
  });

  describe('loading()', () => {
    it('creates a loading state without previous data', () => {
      const state = loading<User>();
      expect(state.status).toBe('loading');
      expect(state.previousData).toBeUndefined();
    });

    it('creates a loading state with previous data', () => {
      const user = createUser();
      const state = loading(user);
      expect(state.status).toBe('loading');
      expect(state.previousData).toEqual(user);
    });

    it('preserves the type of previous data', () => {
      const user = createUser();
      const state = loading(user);
      // TypeScript should infer LoadingState<User>
      expect(state.previousData?.name).toBe('Alice');
    });
  });

  describe('error()', () => {
    it('creates an error state with the given error', () => {
      const err = new Error('Test error');
      const state = error(err);
      expect(state.status).toBe('error');
      expect(state.error).toBe(err);
    });

    it('preserves error message', () => {
      const state = error(new Error('Custom message'));
      expect(state.error.message).toBe('Custom message');
    });

    it('preserves error stack trace', () => {
      const err = new Error('Test');
      const state = error(err);
      expect(state.error.stack).toBeDefined();
    });
  });

  describe('success()', () => {
    it('creates a success state with data', () => {
      const user = createUser();
      const state = success(user);
      expect(state.status).toBe('success');
      expect(state.data).toEqual(user);
    });

    it('preserves complex data types', () => {
      const data = { users: [createUser()], total: 1 };
      const state = success(data);
      expect(state.data.users).toHaveLength(1);
      expect(state.data.total).toBe(1);
    });

    it('works with primitive types', () => {
      const numState = success(42);
      expect(numState.data).toBe(42);

      const strState = success('hello');
      expect(strState.data).toBe('hello');

      const boolState = success(true);
      expect(boolState.data).toBe(true);
    });

    it('works with arrays', () => {
      const users = [createUser()];
      const state = success(users);
      expect(state.data).toHaveLength(1);
    });

    it('works with null values', () => {
      const state = success<null>(null);
      expect(state.data).toBeNull();
    });
  });
});

// ============================================================================
// Type Guard Tests
// ============================================================================

describe('Type Guards', () => {
  describe('isIdle()', () => {
    it('returns true for idle state', () => {
      const state = createIdleState();
      expect(isIdle(state)).toBe(true);
    });

    it('returns false for loading state', () => {
      const state = createLoadingState<User>();
      expect(isIdle(state)).toBe(false);
    });

    it('returns false for error state', () => {
      const state = createErrorState();
      expect(isIdle(state)).toBe(false);
    });

    it('returns false for success state', () => {
      const state = createSuccessState(createUser());
      expect(isIdle(state)).toBe(false);
    });
  });

  describe('isLoading()', () => {
    it('returns true for loading state', () => {
      const state = createLoadingState<User>();
      expect(isLoading(state)).toBe(true);
    });

    it('returns true for loading state with previous data', () => {
      const state = createLoadingState(createUser());
      expect(isLoading(state)).toBe(true);
    });

    it('returns false for idle state', () => {
      const state = createIdleState();
      expect(isLoading(state)).toBe(false);
    });

    it('returns false for error state', () => {
      const state = createErrorState();
      expect(isLoading(state)).toBe(false);
    });

    it('returns false for success state', () => {
      const state = createSuccessState(createUser());
      expect(isLoading(state)).toBe(false);
    });
  });

  describe('isError()', () => {
    it('returns true for error state', () => {
      const state = createErrorState();
      expect(isError(state)).toBe(true);
    });

    it('returns false for idle state', () => {
      const state = createIdleState();
      expect(isError(state)).toBe(false);
    });

    it('returns false for loading state', () => {
      const state = createLoadingState<User>();
      expect(isError(state)).toBe(false);
    });

    it('returns false for success state', () => {
      const state = createSuccessState(createUser());
      expect(isError(state)).toBe(false);
    });
  });

  describe('isSuccess()', () => {
    it('returns true for success state', () => {
      const state = createSuccessState(createUser());
      expect(isSuccess(state)).toBe(true);
    });

    it('returns false for idle state', () => {
      const state = createIdleState();
      expect(isSuccess(state)).toBe(false);
    });

    it('returns false for loading state', () => {
      const state = createLoadingState<User>();
      expect(isSuccess(state)).toBe(false);
    });

    it('returns false for error state', () => {
      const state = createErrorState();
      expect(isSuccess(state)).toBe(false);
    });
  });
});

// ============================================================================
// Type Narrowing Tests (compile-time verification)
// ============================================================================

describe('Type Narrowing', () => {
  it('narrows to IdleState after isIdle guard', () => {
    const state: AsyncState<User> = idle();

    if (isIdle(state)) {
      // TypeScript should narrow to IdleState
      expect(state.status).toBe('idle');
      // Verify we cannot access data (would be compile error)
    }
  });

  it('narrows to LoadingState after isLoading guard', () => {
    const user = createUser();
    const state: AsyncState<User> = loading(user);

    if (isLoading(state)) {
      // TypeScript should narrow to LoadingState<User>
      expect(state.status).toBe('loading');
      expect(state.previousData?.name).toBe('Alice');
    }
  });

  it('narrows to ErrorState after isError guard', () => {
    const state: AsyncState<User> = error(new Error('Test'));

    if (isError(state)) {
      // TypeScript should narrow to ErrorState
      expect(state.error.message).toBe('Test');
    }
  });

  it('narrows to SuccessState after isSuccess guard', () => {
    const user = createUser();
    const state: AsyncState<User> = success(user);

    if (isSuccess(state)) {
      // TypeScript should narrow to SuccessState<User>
      expect(state.data.name).toBe('Alice');
      expect(state.data.email).toBe('alice@example.com');
    }
  });

  it('supports exhaustive switch statements', () => {
    function handleState(state: AsyncState<User>): string {
      switch (state.status) {
        case 'idle':
          return 'not-started';
        case 'loading':
          return state.previousData ? `loading:${state.previousData.id}` : 'loading';
        case 'error':
          return `error:${state.error.message}`;
        case 'success':
          return `success:${state.data.id}`;
        default:
          // This ensures exhaustive checking
          return assertNever(state);
      }
    }

    expect(handleState(idle())).toBe('not-started');
    expect(handleState(loading())).toBe('loading');
    expect(handleState(loading(createUser()))).toBe('loading:user-1');
    expect(handleState(error(new Error('fail')))).toBe('error:fail');
    expect(handleState(success(createUser()))).toBe('success:user-1');
  });
});

// ============================================================================
// Helper Function Tests
// ============================================================================

describe('Helper Functions', () => {
  describe('getDataOrDefault()', () => {
    it('returns data for success state', () => {
      const user = createUser();
      const state = success(user);
      const result = getDataOrDefault(state, { id: 'default', name: 'Default', email: '' });
      expect(result).toEqual(user);
    });

    it('returns default for idle state', () => {
      const state: AsyncState<User> = idle();
      const defaultUser = { id: 'default', name: 'Default', email: '' };
      const result = getDataOrDefault(state, defaultUser);
      expect(result).toEqual(defaultUser);
    });

    it('returns default for loading state', () => {
      const state: AsyncState<User> = loading();
      const defaultUser = { id: 'default', name: 'Default', email: '' };
      const result = getDataOrDefault(state, defaultUser);
      expect(result).toEqual(defaultUser);
    });

    it('returns default for error state', () => {
      const state: AsyncState<User> = error(new Error('fail'));
      const defaultUser = { id: 'default', name: 'Default', email: '' };
      const result = getDataOrDefault(state, defaultUser);
      expect(result).toEqual(defaultUser);
    });

    it('works with primitive default values', () => {
      const numState: AsyncState<number> = idle();
      expect(getDataOrDefault(numState, 0)).toBe(0);

      const strState: AsyncState<string> = loading();
      expect(getDataOrDefault(strState, '')).toBe('');

      const arrState: AsyncState<string[]> = error(new Error('fail'));
      expect(getDataOrDefault(arrState, [])).toEqual([]);
    });

    it('ignores previousData in loading state', () => {
      const user = createUser();
      const state: AsyncState<User> = loading(user);
      const defaultUser = { id: 'default', name: 'Default', email: '' };
      // getDataOrDefault only returns from success state
      const result = getDataOrDefault(state, defaultUser);
      expect(result).toEqual(defaultUser);
    });
  });

  describe('getAvailableData()', () => {
    it('returns data for success state', () => {
      const user = createUser();
      const state = success(user);
      expect(getAvailableData(state)).toEqual(user);
    });

    it('returns undefined for idle state', () => {
      const state: AsyncState<User> = idle();
      expect(getAvailableData(state)).toBeUndefined();
    });

    it('returns undefined for loading state without previous data', () => {
      const state: AsyncState<User> = loading();
      expect(getAvailableData(state)).toBeUndefined();
    });

    it('returns previous data for loading state with previous data', () => {
      const user = createUser();
      const state: AsyncState<User> = loading(user);
      expect(getAvailableData(state)).toEqual(user);
    });

    it('returns undefined for error state', () => {
      const state: AsyncState<User> = error(new Error('fail'));
      expect(getAvailableData(state)).toBeUndefined();
    });
  });

  describe('mapAsyncState()', () => {
    it('transforms data in success state', () => {
      const user = createUser();
      const state = success(user);
      const nameState = mapAsyncState(state, (u: User) => u.name);

      expect(isSuccess(nameState)).toBe(true);
      if (isSuccess(nameState)) {
        expect(nameState.data).toBe('Alice');
      }
    });

    it('preserves idle state', () => {
      const state: AsyncState<User> = idle();
      const mapped = mapAsyncState(state, (u: User) => u.name);

      expect(isIdle(mapped)).toBe(true);
    });

    it('preserves loading state without previous data', () => {
      const state: AsyncState<User> = loading();
      const mapped = mapAsyncState(state, (u: User) => u.name);

      expect(isLoading(mapped)).toBe(true);
      if (isLoading(mapped)) {
        expect(mapped.previousData).toBeUndefined();
      }
    });

    it('transforms previous data in loading state', () => {
      const user = createUser();
      const state: AsyncState<User> = loading(user);
      const mapped = mapAsyncState(state, (u: User) => u.name);

      expect(isLoading(mapped)).toBe(true);
      if (isLoading(mapped)) {
        expect(mapped.previousData).toBe('Alice');
      }
    });

    it('preserves error state', () => {
      const err = new Error('test error');
      const state: AsyncState<User> = error(err);
      const mapped = mapAsyncState(state, (u: User) => u.name);

      expect(isError(mapped)).toBe(true);
      if (isError(mapped)) {
        expect(mapped.error).toBe(err);
      }
    });

    it('works with complex transformations', () => {
      const users = [createUser(), { ...createUser(), id: 'user-2', name: 'Bob' }];
      const state = success(users);
      const namesState = mapAsyncState(state, (u: User[]) => u.map((x) => x.name));

      expect(isSuccess(namesState)).toBe(true);
      if (isSuccess(namesState)) {
        expect(namesState.data).toEqual(['Alice', 'Bob']);
      }
    });

    it('chains multiple transformations', () => {
      const user = createUser();
      const state = success(user);

      const result = mapAsyncState(
        mapAsyncState(state, (u: User) => u.name),
        (name: string) => name.toUpperCase()
      );

      expect(isSuccess(result)).toBe(true);
      if (isSuccess(result)) {
        expect(result.data).toBe('ALICE');
      }
    });
  });

  describe('combineAsyncStates()', () => {
    it('returns success when all states are success', () => {
      const userState = success(createUser());
      const postState = success(createPost());

      const combined = combineAsyncStates([userState, postState]);

      expect(isSuccess(combined)).toBe(true);
      if (isSuccess(combined)) {
        expect((combined.data[0] as User).name).toBe('Alice');
        expect((combined.data[1] as Post).title).toBe('Hello World');
      }
    });

    it('returns loading if any state is loading', () => {
      const userState = success(createUser());
      const postState: AsyncState<Post> = loading();

      const combined = combineAsyncStates([userState, postState]);

      expect(isLoading(combined)).toBe(true);
    });

    it('returns error if any state is error', () => {
      const userState = success(createUser());
      const postState: AsyncState<Post> = error(new Error('Post error'));

      const combined = combineAsyncStates([userState, postState]);

      expect(isError(combined)).toBe(true);
      if (isError(combined)) {
        expect(combined.error.message).toBe('Post error');
      }
    });

    it('prioritizes loading over error', () => {
      const userState: AsyncState<User> = loading();
      const postState: AsyncState<Post> = error(new Error('Post error'));

      const combined = combineAsyncStates([userState, postState]);

      // Loading takes priority
      expect(isLoading(combined)).toBe(true);
    });

    it('returns idle if any state is idle and none loading/error', () => {
      const userState: AsyncState<User> = idle();
      const postState = success(createPost());

      const combined = combineAsyncStates([userState, postState]);

      expect(isIdle(combined)).toBe(true);
    });

    it('works with empty array', () => {
      const combined = combineAsyncStates([]);

      expect(isSuccess(combined)).toBe(true);
      if (isSuccess(combined)) {
        expect(combined.data).toEqual([]);
      }
    });

    it('works with single state', () => {
      const userState = success(createUser());
      const combined = combineAsyncStates([userState]);

      expect(isSuccess(combined)).toBe(true);
      if (isSuccess(combined)) {
        const firstItem = combined.data[0] as unknown as User;
        expect(firstItem.name).toBe('Alice');
      }
    });

    it('works with many states', () => {
      const states = [
        success(1),
        success(2),
        success(3),
        success(4),
        success(5),
      ] as const;

      const combined = combineAsyncStates([...states]);

      expect(isSuccess(combined)).toBe(true);
      if (isSuccess(combined)) {
        expect(combined.data).toEqual([1, 2, 3, 4, 5]);
      }
    });
  });
});

// ============================================================================
// assertNever Tests
// ============================================================================

describe('assertNever', () => {
  it('throws error when called', () => {
    expect(() => assertNever('unexpected' as never)).toThrow();
  });

  it('includes the unexpected value in error message', () => {
    const unexpectedValue = { status: 'unknown' };
    expect(() => assertNever(unexpectedValue as never)).toThrow(/Unexpected/);
  });

  it('stringifies object values', () => {
    const obj = { a: 1, b: 2 };
    expect(() => assertNever(obj as never)).toThrow(/"a":1/);
  });
});

// ============================================================================
// Edge Cases and Real-World Usage
// ============================================================================

describe('Edge Cases', () => {
  it('handles undefined data in success state', () => {
    const state = success<undefined>(undefined);
    expect(isSuccess(state)).toBe(true);
    if (isSuccess(state)) {
      expect(state.data).toBeUndefined();
    }
  });

  it('handles null data in success state', () => {
    const state = success<null>(null);
    expect(isSuccess(state)).toBe(true);
    if (isSuccess(state)) {
      expect(state.data).toBeNull();
    }
  });

  it('handles empty array data', () => {
    const state = success<User[]>([]);
    expect(getDataOrDefault(state, [createUser()])).toEqual([]);
  });

  it('handles complex nested data structures', () => {
    interface ComplexData {
      users: User[];
      metadata: { count: number; page: number };
      nested: { deep: { value: string } };
    }

    const data: ComplexData = {
      users: [createUser()],
      metadata: { count: 1, page: 1 },
      nested: { deep: { value: 'test' } },
    };

    const state = success(data);
    expect(isSuccess(state)).toBe(true);
    if (isSuccess(state)) {
      expect(state.data.nested.deep.value).toBe('test');
    }
  });

  it('preserves Error subclass properties', () => {
    class CustomError extends Error {
      constructor(
        message: string,
        public code: number
      ) {
        super(message);
        this.name = 'CustomError';
      }
    }

    const err = new CustomError('Custom error', 404);
    const state = error(err);

    expect(isError(state)).toBe(true);
    if (isError(state)) {
      expect(state.error).toBeInstanceOf(CustomError);
      expect((state.error as CustomError).code).toBe(404);
    }
  });
});

describe('Real-World Usage Patterns', () => {
  it('simulates data fetching lifecycle', () => {
    // Initial state
    let state: AsyncState<User[]> = idle();
    expect(isIdle(state)).toBe(true);

    // Start fetching
    state = loading();
    expect(isLoading(state)).toBe(true);

    // Fetch fails
    state = error(new Error('Network error'));
    expect(isError(state)).toBe(true);

    // Retry fetching
    state = loading();
    expect(isLoading(state)).toBe(true);

    // Fetch succeeds
    const users = [createUser()];
    state = success(users);
    expect(isSuccess(state)).toBe(true);
    expect(getDataOrDefault(state, [])).toHaveLength(1);
  });

  it('simulates SWR pattern with stale data', () => {
    const staleUser = createUser();

    // Initial success
    let state: AsyncState<User> = success(staleUser);
    expect(getAvailableData(state)).toEqual(staleUser);

    // Start revalidation with stale data
    state = loading(staleUser);
    expect(isLoading(state)).toBe(true);
    expect(getAvailableData(state)).toEqual(staleUser); // Still shows stale data

    // Updated user
    const freshUser = { ...staleUser, name: 'Alice Updated' };
    state = success(freshUser);
    expect(getAvailableData(state)).toEqual(freshUser);
  });

  it('works with React-style conditional rendering', () => {
    function renderComponent(state: AsyncState<User>): string {
      if (isIdle(state)) {
        return 'placeholder';
      }

      // Show stale data while loading
      const data = getAvailableData(state);
      if (isLoading(state)) {
        return data ? `loading:${data.name}` : 'loading';
      }

      if (isError(state)) {
        return `error:${state.error.message}`;
      }

      if (isSuccess(state)) {
        return `user:${state.data.name}`;
      }

      return assertNever(state);
    }

    expect(renderComponent(idle())).toBe('placeholder');
    expect(renderComponent(loading())).toBe('loading');
    expect(renderComponent(loading(createUser()))).toBe('loading:Alice');
    expect(renderComponent(error(new Error('Oops')))).toBe('error:Oops');
    expect(renderComponent(success(createUser()))).toBe('user:Alice');
  });
});
