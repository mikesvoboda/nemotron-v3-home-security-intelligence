import { render, screen, act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { RateLimitProvider, useRateLimitContext } from './RateLimitContext';

describe('RateLimitContext', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <RateLimitProvider>{children}</RateLimitProvider>
  );

  it('throws error when used outside provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => {
      renderHook(() => useRateLimitContext());
    }).toThrow('useRateLimitContext must be used within a RateLimitProvider');
    spy.mockRestore();
  });

  it('returns context value within provider', () => {
    const { result } = renderHook(() => useRateLimitContext(), { wrapper });
    expect(result.current.rateLimits).toEqual({});
  });

  it('renders children', () => {
    render(
      <RateLimitProvider>
        <div data-testid="child">x</div>
      </RateLimitProvider>
    );
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('updates rate limit', () => {
    const { result } = renderHook(() => useRateLimitContext(), { wrapper });
    act(() => {
      result.current.updateRateLimit('/api/events', {
        limit: 100,
        remaining: 50,
        resetAt: new Date(),
      });
    });
    expect(result.current.rateLimits['/api/events'].remaining).toBe(50);
  });

  it('sets isLimited when remaining is 0', () => {
    const { result } = renderHook(() => useRateLimitContext(), { wrapper });
    act(() => {
      result.current.updateRateLimit('/api/events', {
        limit: 100,
        remaining: 0,
        resetAt: new Date(),
      });
    });
    expect(result.current.rateLimits['/api/events'].isLimited).toBe(true);
  });

  it('clears rate limit', () => {
    const { result } = renderHook(() => useRateLimitContext(), { wrapper });
    act(() => {
      result.current.updateRateLimit('/api/events', {
        limit: 100,
        remaining: 50,
        resetAt: new Date(),
      });
    });
    act(() => {
      result.current.clearRateLimit('/api/events');
    });
    expect(result.current.rateLimits['/api/events']).toBeUndefined();
  });

  it('clears all rate limits', () => {
    const { result } = renderHook(() => useRateLimitContext(), { wrapper });
    act(() => {
      result.current.updateRateLimit('/api/a', {
        limit: 1,
        remaining: 0,
        resetAt: new Date(),
      });
      result.current.updateRateLimit('/api/b', {
        limit: 2,
        remaining: 1,
        resetAt: new Date(),
      });
    });
    act(() => {
      result.current.clearAllRateLimits();
    });
    expect(result.current.rateLimits).toEqual({});
  });

  it('isEndpointLimited works', () => {
    const { result } = renderHook(() => useRateLimitContext(), { wrapper });
    expect(result.current.isEndpointLimited('/x')).toBe(false);
    act(() => {
      result.current.updateRateLimit('/x', {
        limit: 1,
        remaining: 0,
        resetAt: new Date(),
      });
    });
    expect(result.current.isEndpointLimited('/x')).toBe(true);
  });

  it('isAnyEndpointLimited works', () => {
    const { result } = renderHook(() => useRateLimitContext(), { wrapper });
    expect(result.current.isAnyEndpointLimited()).toBe(false);
    act(() => {
      result.current.updateRateLimit('/x', {
        limit: 1,
        remaining: 0,
        resetAt: new Date(),
      });
    });
    expect(result.current.isAnyEndpointLimited()).toBe(true);
  });

  it('getLimitedEndpoints works', () => {
    const { result } = renderHook(() => useRateLimitContext(), { wrapper });
    act(() => {
      result.current.updateRateLimit('/a', {
        limit: 1,
        remaining: 0,
        resetAt: new Date(),
      });
      result.current.updateRateLimit('/b', {
        limit: 1,
        remaining: 1,
        resetAt: new Date(),
      });
    });
    expect(result.current.getLimitedEndpoints()).toEqual(['/a']);
  });
});
