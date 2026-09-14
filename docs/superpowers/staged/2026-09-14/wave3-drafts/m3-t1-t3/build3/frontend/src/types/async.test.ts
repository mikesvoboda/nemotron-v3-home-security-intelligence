/**
 * Tests for Async State Management Types
 */

import { describe, it, expect, vi } from 'vitest';

import {
  idle,
  loading,
  failure,
  success,
  isIdle,
  isLoading,
  isError,
  isSuccess,
  hasData,
  getData,
  getError,
  mapData,
  matchState,
  refreshing,
  isRefreshing,
  paginatedSuccess,
  createAsyncHookReturn,
  type AsyncState,
  type RefreshableState,
  type PaginatedData,
} from './async';

// ============================================================================
// Test Data Types
// ============================================================================

interface User {
  id: number;
  name: string;
}

interface Event {
  id: number;
  title: string;
  risk_score: number;
}

// ============================================================================
// Factory Function Tests
// ============================================================================

describe('Async State Factory Functions', () => {
  describe('idle', () => {
    it('creates an idle state', () => {
      const state = idle<User>();
      expect(state.status).toBe('idle');
    });

    it('creates an idle state with correct type', () => {
      const state: AsyncState<User> = idle();
      expect(state.status).toBe('idle');
    });
  });

  describe('loading', () => {
    it('creates a loading state without previous data', () => {
      const state = loading<User>();
      expect(state.status).toBe('loading');
      expect('previousData' in state).toBe(false);
    });

    it('creates a loading state with previous data', () => {
      const previousUser: User = { id: 1, name: 'John' };
      const state = loading(previousUser);
      expect(state.status).toBe('loading');
      if (state.status === 'loading') {
        expect(state.previousData).toEqual(previousUser);
      }
    });

    it('creates a loading state with undefined previous data (explicit)', () => {
      const state = loading(undefined);
      expect(state.status).toBe('loading');
    });
  });

  describe('failure', () => {
    it('creates an error state from Error object', () => {
      const error = new Error('Network error');
      const state = failure<User>(error);
      expect(state.status).toBe('error');
      if (state.status === 'error') {
        expect(state.error).toBe(error);
        expect(state.error.message).toBe('Network error');
      }
    });

    it('creates an error state from string', () => {
      const state = failure<User>('Something went wrong');
      expect(state.status).toBe('error');
      if (state.status === 'error') {
        expect(state.error.message).toBe('Something went wrong');
      }
    });

    it('creates an error state from unknown error', () => {
      const state = failure<User>(null);
      expect(state.status).toBe('error');
      if (state.status === 'error') {
        expect(state.error.message).toBe('Unknown error');
      }
    });

    it('includes retry function when provided', () => {
      const retry = vi.fn();
      const state = failure<User>('Error', retry);
      expect(state.status).toBe('error');
      if (state.status === 'error') {
        expect(state.retry).toBe(retry);
      }
    });
  });

  describe('success', () => {
    it('creates a success state with data', () => {
      const user: User = { id: 1, name: 'John' };
      const state = success(user);
      expect(state.status).toBe('success');
      if (state.status === 'success') {
        expect(state.data).toEqual(user);
      }
    });

    it('creates a success state with fetchedAt timestamp', () => {
      const user: User = { id: 1, name: 'John' };
      const timestamp = new Date();
      const state = success(user, timestamp);
      expect(state.status).toBe('success');
      if (state.status === 'success') {
        expect(state.fetchedAt).toBe(timestamp);
      }
    });
  });
});

// ============================================================================
// Type Guard Tests
// ============================================================================

describe('Async State Type Guards', () => {
  const idleState = idle<User>();
  const loadingState = loading<User>();
  const loadingWithData = loading({ id: 1, name: 'John' });
  const errorState = failure<User>('Error');
  const successState = success({ id: 1, name: 'John' });

  describe('isIdle', () => {
    it('returns true for idle state', () => {
      expect(isIdle(idleState)).toBe(true);
    });

    it('returns false for other states', () => {
      expect(isIdle(loadingState)).toBe(false);
      expect(isIdle(errorState)).toBe(false);
      expect(isIdle(successState)).toBe(false);
    });
  });

  describe('isLoading', () => {
    it('returns true for loading state', () => {
      expect(isLoading(loadingState)).toBe(true);
      expect(isLoading(loadingWithData)).toBe(true);
    });

    it('returns false for other states', () => {
      expect(isLoading(idleState)).toBe(false);
      expect(isLoading(errorState)).toBe(false);
      expect(isLoading(successState)).toBe(false);
    });
  });

  describe('isError', () => {
    it('returns true for error state', () => {
      expect(isError(errorState)).toBe(true);
    });

    it('returns false for other states', () => {
      expect(isError(idleState)).toBe(false);
      expect(isError(loadingState)).toBe(false);
      expect(isError(successState)).toBe(false);
    });
  });

  describe('isSuccess', () => {
    it('returns true for success state', () => {
      expect(isSuccess(successState)).toBe(true);
    });

    it('returns false for other states', () => {
      expect(isSuccess(idleState)).toBe(false);
      expect(isSuccess(loadingState)).toBe(false);
      expect(isSuccess(errorState)).toBe(false);
    });
  });

  describe('hasData', () => {
    it('returns true for success state', () => {
      expect(hasData(successState)).toBe(true);
    });

    it('returns true for loading state with previous data', () => {
      expect(hasData(loadingWithData)).toBe(true);
    });

    it('returns false for loading state without previous data', () => {
      expect(hasData(loadingState)).toBe(false);
    });

    it('returns false for idle and error states', () => {
      expect(hasData(idleState)).toBe(false);
      expect(hasData(errorState)).toBe(false);
    });
  });
});

// ============================================================================
// Utility Function Tests
// ============================================================================

describe('Async State Utility Functions', () => {
  describe('getData', () => {
    it('returns data from success state', () => {
      const user: User = { id: 1, name: 'John' };
      const state = success(user);
      expect(getData(state)).toEqual(user);
    });

    it('returns previous data from loading state', () => {
      const user: User = { id: 1, name: 'John' };
      const state = loading(user);
      expect(getData(state)).toEqual(user);
    });

    it('returns undefined for loading state without previous data', () => {
      const state = loading<User>();
      expect(getData(state)).toBeUndefined();
    });

    it('returns undefined for idle and error states', () => {
      expect(getData(idle<User>())).toBeUndefined();
      expect(getData(failure<User>('Error'))).toBeUndefined();
    });
  });

  describe('getError', () => {
    it('returns error from error state', () => {
      const error = new Error('Test error');
      const state = failure<User>(error);
      expect(getError(state)).toBe(error);
    });

    it('returns undefined for non-error states', () => {
      expect(getError(idle<User>())).toBeUndefined();
      expect(getError(loading<User>())).toBeUndefined();
      expect(getError(success({ id: 1, name: 'John' }))).toBeUndefined();
    });
  });

  describe('mapData', () => {
    it('maps data in success state', () => {
      const state = success({ id: 1, name: 'John' });
      const mapped = mapData(state, (user) => user.name);

      expect(isSuccess(mapped)).toBe(true);
      if (isSuccess(mapped)) {
        expect(mapped.data).toBe('John');
      }
    });

    it('preserves fetchedAt in success state', () => {
      const timestamp = new Date();
      const state = success({ id: 1, name: 'John' }, timestamp);
      const mapped = mapData(state, (user) => user.name);

      if (isSuccess(mapped)) {
        expect(mapped.fetchedAt).toBe(timestamp);
      }
    });

    it('maps previous data in loading state', () => {
      const state = loading({ id: 1, name: 'John' });
      const mapped = mapData(state, (user) => user.name);

      expect(isLoading(mapped)).toBe(true);
      if (isLoading(mapped)) {
        expect(mapped.previousData).toBe('John');
      }
    });

    it('returns idle state unchanged', () => {
      const state = idle<User>();
      const mapped = mapData(state, (user) => user.name);
      expect(mapped.status).toBe('idle');
    });

    it('returns error state unchanged', () => {
      const error = new Error('Test');
      const state = failure<User>(error);
      const mapped = mapData(state, (user) => user.name);

      expect(isError(mapped)).toBe(true);
      if (isError(mapped)) {
        expect(mapped.error).toBe(error);
      }
    });
  });

  describe('matchState', () => {
    it('calls idle handler for idle state', () => {
      const result = matchState(idle<User>(), {
        idle: () => 'idle',
        loading: () => 'loading',
        error: () => 'error',
        success: () => 'success',
      });
      expect(result).toBe('idle');
    });

    it('calls loading handler with previous data', () => {
      const user: User = { id: 1, name: 'John' };
      const result = matchState(loading(user), {
        idle: () => null,
        loading: (prev) => prev?.name ?? 'loading',
        error: () => null,
        success: () => null,
      });
      expect(result).toBe('John');
    });

    it('calls loading handler without previous data', () => {
      const result = matchState(loading<User>(), {
        idle: () => null,
        loading: (prev) => prev?.name ?? 'no data',
        error: () => null,
        success: () => null,
      });
      expect(result).toBe('no data');
    });

    it('calls error handler with error and retry', () => {
      const retry = vi.fn();
      const state = failure<User>('Test error', retry);
      const result = matchState(state, {
        idle: () => ({
          error: null as string | null,
          retry: undefined as (() => void) | undefined,
        }),
        loading: () => ({
          error: null as string | null,
          retry: undefined as (() => void) | undefined,
        }),
        error: (err, r) => ({ error: err.message, retry: r }),
        success: () => ({
          error: null as string | null,
          retry: undefined as (() => void) | undefined,
        }),
      });
      expect(result.error).toBe('Test error');
      expect(result.retry).toBe(retry);
    });

    it('calls success handler with data and timestamp', () => {
      const timestamp = new Date();
      const user: User = { id: 1, name: 'John' };
      const state = success(user, timestamp);

      const result = matchState(state, {
        idle: () => ({ data: null as User | null, time: undefined as Date | undefined }),
        loading: () => ({ data: null as User | null, time: undefined as Date | undefined }),
        error: () => ({ data: null as User | null, time: undefined as Date | undefined }),
        success: (data, fetchedAt) => ({ data, time: fetchedAt }),
      });

      expect(result.data).toEqual(user);
      expect(result.time).toBe(timestamp);
    });

    it('works with JSX-like returns', () => {
      const state = success({ id: 1, name: 'John' });
      const result = matchState(state, {
        idle: () => '<EmptyState />',
        loading: () => '<Spinner />',
        error: () => '<ErrorMessage />',
        success: (data) => `<UserCard name="${data.name}" />`,
      });
      expect(result).toBe('<UserCard name="John" />');
    });
  });
});

// ============================================================================
// Refreshable State Tests
// ============================================================================

describe('Refreshable State', () => {
  describe('refreshing', () => {
    it('creates a refreshing state with data', () => {
      const user: User = { id: 1, name: 'John' };
      const state = refreshing(user);
      expect(state.status).toBe('refreshing');
      expect(state.data).toEqual(user);
    });

    it('creates a refreshing state with timestamp', () => {
      const user: User = { id: 1, name: 'John' };
      const timestamp = new Date();
      const state = refreshing(user, timestamp);
      expect(state.fetchedAt).toBe(timestamp);
    });
  });

  describe('isRefreshing', () => {
    it('returns true for refreshing state', () => {
      const state: RefreshableState<User> = refreshing({ id: 1, name: 'John' });
      expect(isRefreshing(state)).toBe(true);
    });

    it('returns false for other states', () => {
      expect(isRefreshing(idle<User>())).toBe(false);
      expect(isRefreshing(loading<User>())).toBe(false);
      expect(isRefreshing(failure<User>('Error'))).toBe(false);
      expect(isRefreshing(success({ id: 1, name: 'John' }))).toBe(false);
    });
  });
});

// ============================================================================
// Paginated State Tests
// ============================================================================

describe('Paginated State', () => {
  describe('paginatedSuccess', () => {
    it('creates a paginated success state', () => {
      const events: Event[] = [
        { id: 1, title: 'Event 1', risk_score: 50 },
        { id: 2, title: 'Event 2', risk_score: 75 },
      ];

      const state = paginatedSuccess(events, 100, 0, 20);

      expect(isSuccess(state)).toBe(true);
      if (isSuccess(state)) {
        const data: PaginatedData<Event> = state.data;
        expect(data.items).toEqual(events);
        expect(data.total).toBe(100);
        expect(data.page).toBe(0);
        expect(data.pageSize).toBe(20);
        expect(data.hasMore).toBe(true);
      }
    });

    it('calculates hasMore correctly', () => {
      // Page 0, 20 per page, 100 total = has more
      let state = paginatedSuccess([], 100, 0, 20);
      if (isSuccess(state)) {
        expect(state.data.hasMore).toBe(true);
      }

      // Page 4 (last page), 20 per page, 100 total = no more
      state = paginatedSuccess([], 100, 4, 20);
      if (isSuccess(state)) {
        expect(state.data.hasMore).toBe(false);
      }

      // Exactly fills last page
      state = paginatedSuccess([], 40, 1, 20);
      if (isSuccess(state)) {
        expect(state.data.hasMore).toBe(false);
      }
    });
  });
});

// ============================================================================
// Hook Return Type Tests
// ============================================================================

describe('createAsyncHookReturn', () => {
  it('creates a hook return value with state and refetch', () => {
    const refetch = vi.fn();
    const state = success({ id: 1, name: 'John' });
    const hookReturn = createAsyncHookReturn(state, refetch);

    expect(hookReturn.status).toBe('success');
    expect(hookReturn.refetch).toBe(refetch);
    if (hookReturn.status === 'success') {
      expect(hookReturn.data).toEqual({ id: 1, name: 'John' });
    }
  });

  it('works with all state types', () => {
    const refetch = vi.fn();

    const idleReturn = createAsyncHookReturn(idle<User>(), refetch);
    expect(idleReturn.status).toBe('idle');
    expect(idleReturn.refetch).toBe(refetch);

    const loadingReturn = createAsyncHookReturn(loading<User>(), refetch);
    expect(loadingReturn.status).toBe('loading');

    const errorReturn = createAsyncHookReturn(failure<User>('Error'), refetch);
    expect(errorReturn.status).toBe('error');
  });
});

// ============================================================================
// Type Inference Tests (Compile-time Verification)
// ============================================================================

describe('Type Inference', () => {
  it('narrows type correctly in switch statement', () => {
    function processState(state: AsyncState<User>): string {
      switch (state.status) {
        case 'idle':
          return 'No data';
        case 'loading':
          // TypeScript knows state.previousData is User | undefined
          return state.previousData?.name ?? 'Loading...';
        case 'error':
          // TypeScript knows state.error is Error
          return `Error: ${state.error.message}`;
        case 'success':
          // TypeScript knows state.data is User
          return `User: ${state.data.name}`;
      }
    }

    expect(processState(idle())).toBe('No data');
    expect(processState(loading({ id: 1, name: 'John' }))).toBe('John');
    expect(processState(loading())).toBe('Loading...');
    expect(processState(failure('Network error'))).toBe('Error: Network error');
    expect(processState(success({ id: 1, name: 'Jane' }))).toBe('User: Jane');
  });

  it('works with complex data types', () => {
    type EventList = Event[];
    const events: EventList = [
      { id: 1, title: 'Event 1', risk_score: 50 },
      { id: 2, title: 'Event 2', risk_score: 75 },
    ];

    const state = success(events);

    if (isSuccess(state)) {
      // TypeScript knows state.data is Event[]
      const highRisk = state.data.filter((e) => e.risk_score > 60);
      expect(highRisk).toHaveLength(1);
      expect(highRisk[0].title).toBe('Event 2');
    }
  });
});
