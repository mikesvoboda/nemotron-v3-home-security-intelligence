/**
 * Tests for test utilities.
 *
 * This ensures our custom testing utilities work correctly.
 */

import { useQuery } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { renderWithProviders, createWrapper, createTestQueryClient } from './utils';

// ============================================================================
// Test Component
// ============================================================================

function TestComponent({ text = 'Hello World' }: { text?: string }) {
  return <div>{text}</div>;
}

// ============================================================================
// Tests
// ============================================================================

describe('renderWithProviders', () => {
  it('renders component successfully', () => {
    const { getByText } = renderWithProviders(<TestComponent />);
    expect(getByText('Hello World')).toBeInTheDocument();
  });

  it('passes props to component', () => {
    const { getByText } = renderWithProviders(<TestComponent text="Custom Text" />);
    expect(getByText('Custom Text')).toBeInTheDocument();
  });

  it('provides QueryClient to components', () => {
    function QueryComponent() {
      const query = useQuery({
        queryKey: ['test'],
        queryFn: () => Promise.resolve({ data: 'test' }),
      });

      return <div>{query.isLoading ? 'Loading' : 'Loaded'}</div>;
    }

    const { getByText } = renderWithProviders(<QueryComponent />);
    expect(getByText(/loading|loaded/i)).toBeInTheDocument();
  });
});

describe('createWrapper', () => {
  it('creates wrapper function', () => {
    const wrapper = createWrapper();
    expect(typeof wrapper).toBe('function');
  });

  it('works with renderHook', async () => {
    const wrapper = createWrapper();

    const { result } = renderHook(
      () =>
        useQuery({
          queryKey: ['test'],
          queryFn: () => Promise.resolve('data'),
        }),
      { wrapper }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toBe('data');
  });

  it('accepts custom queryClientOptions', async () => {
    const wrapper = createWrapper({
      defaultOptions: {
        queries: {
          retry: 3, // Override default (0)
        },
      },
    });

    const { result } = renderHook(
      () =>
        useQuery({
          queryKey: ['test'],
          queryFn: () => Promise.resolve('data'),
        }),
      { wrapper }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toBe('data');
  });
});

describe('createTestQueryClient', () => {
  it('creates QueryClient instance', () => {
    const queryClient = createTestQueryClient();
    expect(queryClient).toBeDefined();
    expect(typeof queryClient.clear).toBe('function');
  });

  it('has retry disabled by default', () => {
    const queryClient = createTestQueryClient();
    const options = queryClient.getDefaultOptions();
    expect(options.queries?.retry).toBe(false);
  });

  it('has refetchOnWindowFocus disabled', () => {
    const queryClient = createTestQueryClient();
    const options = queryClient.getDefaultOptions();
    expect(options.queries?.refetchOnWindowFocus).toBe(false);
  });

  it('has zero cache time', () => {
    const queryClient = createTestQueryClient();
    const options = queryClient.getDefaultOptions();
    expect(options.queries?.gcTime).toBe(0);
    expect(options.queries?.staleTime).toBe(0);
  });

  it('accepts custom options', () => {
    const queryClient = createTestQueryClient({
      defaultOptions: {
        queries: {
          retry: 5,
        },
      },
    });
    const options = queryClient.getDefaultOptions();
    expect(options.queries?.retry).toBe(5);
  });
});
