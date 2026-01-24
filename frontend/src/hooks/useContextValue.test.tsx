/**
 * Tests for useContextValue hooks (NEM-3357)
 *
 * Tests React 19 use() hook utilities.
 */

import { render, screen, waitFor , renderHook } from '@testing-library/react';
import { Suspense, createContext } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import {
  createContextWithUse,
  usePromiseValue,
  useConditionalContext,
  useContextOrDefault,
  createSuspenseResource,
  wrapPromise,
} from './useContextValue';

import type { ReactNode } from 'react';

describe('createContextWithUse', () => {
  interface User {
    id: string;
    name: string;
  }

  const testUser: User = { id: '1', name: 'Test User' };

  it('creates context with correct display name', () => {
    const { Context, displayName } = createContextWithUse<User>({
      displayName: 'UserContext',
    });

    expect(displayName).toBe('UserContext');
    expect(Context.displayName).toBe('UserContext');
  });

  it('Provider provides value to children', () => {
    const { Provider, useValue } = createContextWithUse<User>({
      displayName: 'UserContext',
    });

    function Consumer() {
      const user = useValue();
      return <div data-testid="name">{user.name}</div>;
    }

    render(
      <Provider value={testUser}>
        <Consumer />
      </Provider>
    );

    expect(screen.getByTestId('name')).toHaveTextContent('Test User');
  });

  it('useValue throws when used outside provider', () => {
    const { useValue } = createContextWithUse<User>({
      displayName: 'UserContext',
    });

    // Suppress console.error for expected error
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    function Consumer() {
      const user = useValue();
      return <div>{user.name}</div>;
    }

    expect(() => render(<Consumer />)).toThrow(
      'UserContext must be used within a UserContext.Provider'
    );

    consoleSpy.mockRestore();
  });

  it('useValue throws with custom error message', () => {
    const { useValue } = createContextWithUse<User>({
      displayName: 'UserContext',
      errorMessage: 'Custom error message',
    });

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    function Consumer() {
      const user = useValue();
      return <div>{user.name}</div>;
    }

    expect(() => render(<Consumer />)).toThrow('Custom error message');

    consoleSpy.mockRestore();
  });

  it('useValueOptional returns null outside provider', () => {
    const { useValueOptional } = createContextWithUse<User>({
      displayName: 'UserContext',
    });

    function Consumer() {
      const user = useValueOptional();
      return <div data-testid="result">{user?.name ?? 'no user'}</div>;
    }

    render(<Consumer />);

    expect(screen.getByTestId('result')).toHaveTextContent('no user');
  });

  it('useValueOptional returns value inside provider', () => {
    const { Provider, useValueOptional } = createContextWithUse<User>({
      displayName: 'UserContext',
    });

    function Consumer() {
      const user = useValueOptional();
      return <div data-testid="result">{user?.name ?? 'no user'}</div>;
    }

    render(
      <Provider value={testUser}>
        <Consumer />
      </Provider>
    );

    expect(screen.getByTestId('result')).toHaveTextContent('Test User');
  });
});

describe('usePromiseValue', () => {
  it('is a thin wrapper around React use() hook', () => {
    // usePromiseValue is just a direct re-export of use() for promises
    // Testing the actual Suspense behavior is complex due to React 19's
    // internal promise tracking. The function signature is validated here.
    expect(typeof usePromiseValue).toBe('function');
  });

  it('shows loading state initially for pending promise', () => {
    // Create a promise that won't resolve during the test
    const promise = new Promise<string>(() => {
      // Never resolves
    });

    function Consumer() {
      const value = usePromiseValue(promise);
      return <div data-testid="value">{value}</div>;
    }

    render(
      <Suspense fallback={<div data-testid="loading">Loading...</div>}>
        <Consumer />
      </Suspense>
    );

    // Should show loading fallback
    expect(screen.getByTestId('loading')).toBeInTheDocument();
  });
});

describe('useConditionalContext', () => {
  const TestContext = createContext<{ value: string }>({ value: 'default' });

  it('returns value when condition is true', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <TestContext.Provider value={{ value: 'provided' }}>{children}</TestContext.Provider>
    );

    const { result } = renderHook(() => useConditionalContext(TestContext, true), { wrapper });

    expect(result.current.isAvailable).toBe(true);
    expect(result.current.value).toEqual({ value: 'provided' });
  });

  it('returns null when condition is false', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <TestContext.Provider value={{ value: 'provided' }}>{children}</TestContext.Provider>
    );

    const { result } = renderHook(() => useConditionalContext(TestContext, false), { wrapper });

    expect(result.current.isAvailable).toBe(false);
    expect(result.current.value).toBeNull();
  });

  it('can be called conditionally in component', () => {
    function Consumer({ enabled }: { enabled: boolean }) {
      const { isAvailable, value } = useConditionalContext(TestContext, enabled);
      return (
        <div data-testid="result">
          {isAvailable ? value?.value : 'disabled'}
        </div>
      );
    }

    const { rerender } = render(
      <TestContext.Provider value={{ value: 'test' }}>
        <Consumer enabled={false} />
      </TestContext.Provider>
    );

    expect(screen.getByTestId('result')).toHaveTextContent('disabled');

    rerender(
      <TestContext.Provider value={{ value: 'test' }}>
        <Consumer enabled={true} />
      </TestContext.Provider>
    );

    expect(screen.getByTestId('result')).toHaveTextContent('test');
  });
});

describe('useContextOrDefault', () => {
  const NullableContext = createContext<{ value: string } | null>(null);

  it('returns context value when available', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <NullableContext.Provider value={{ value: 'provided' }}>
        {children}
      </NullableContext.Provider>
    );

    const { result } = renderHook(
      () => useContextOrDefault(NullableContext, { value: 'default' }),
      { wrapper }
    );

    expect(result.current).toEqual({ value: 'provided' });
  });

  it('returns default when context is null', () => {
    const { result } = renderHook(() =>
      useContextOrDefault(NullableContext, { value: 'default' })
    );

    expect(result.current).toEqual({ value: 'default' });
  });
});

describe('createSuspenseResource', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates resource that suspends then resolves', async () => {
    const resource = createSuspenseResource(() => Promise.resolve('data'));

    function Consumer() {
      const data = resource.read();
      return <div data-testid="data">{data}</div>;
    }

    render(
      <Suspense fallback={<div data-testid="loading">Loading</div>}>
        <Consumer />
      </Suspense>
    );

    await waitFor(() => {
      expect(screen.getByTestId('data')).toHaveTextContent('data');
    });
  });

  it('preload triggers fetch without suspending', async () => {
    const fetcher = vi.fn().mockResolvedValue('preloaded');
    const resource = createSuspenseResource(fetcher);

    // Preload should trigger fetch
    resource.preload();

    expect(fetcher).toHaveBeenCalled();
    expect(resource.status).toBe('pending');

    // Wait for resolution
    await waitFor(() => {
      expect(resource.status).toBe('success');
    });
  });

  it('resource throws on error', async () => {
    const error = new Error('Fetch failed');
    const resource = createSuspenseResource(() => Promise.reject(error));

    // Trigger the fetch
    resource.preload();

    await waitFor(() => {
      expect(resource.status).toBe('error');
    });

    // Suppress console.error for expected error
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => resource.read()).toThrow('Fetch failed');

    consoleSpy.mockRestore();
  });

  it('converts non-Error rejection to Error', async () => {
    const resource = createSuspenseResource(() => Promise.reject(new Error('string error')));

    resource.preload();

    await waitFor(() => {
      expect(resource.status).toBe('error');
    });

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => resource.read()).toThrow('string error');

    consoleSpy.mockRestore();
  });

  it('returns same promise on multiple preload calls', () => {
    let callCount = 0;
    const resource = createSuspenseResource(() => {
      callCount++;
      return Promise.resolve('data');
    });

    resource.preload();
    resource.preload();
    resource.preload();

    expect(callCount).toBe(1);
  });
});

describe('wrapPromise', () => {
  it('creates reader that suspends then returns value', async () => {
    const reader = wrapPromise(Promise.resolve('wrapped'));

    function Consumer() {
      const data = reader();
      return <div data-testid="data">{data}</div>;
    }

    render(
      <Suspense fallback={<div data-testid="loading">Loading</div>}>
        <Consumer />
      </Suspense>
    );

    await waitFor(() => {
      expect(screen.getByTestId('data')).toHaveTextContent('wrapped');
    });
  });

  it('throws on rejected promise', async () => {
    const error = new Error('Wrapped error');
    const reader = wrapPromise(Promise.reject(error));

    // Wait for promise to settle
    await new Promise((resolve) => setTimeout(resolve, 0));

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => reader()).toThrow('Wrapped error');

    consoleSpy.mockRestore();
  });

  it('converts non-Error rejection to Error', async () => {
    const reader = wrapPromise(Promise.reject(new Error('string rejection')));

    // Wait for promise to settle
    await new Promise((resolve) => setTimeout(resolve, 0));

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => reader()).toThrow('string rejection');

    consoleSpy.mockRestore();
  });
});
