import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useRateLimit } from './useRateLimit';
import { RateLimitProvider } from '../contexts/RateLimitContext';

import type { ReactNode } from 'react';

describe('useRateLimit', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <RateLimitProvider>{children}</RateLimitProvider>
  );

  it('throws outside provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => {
      renderHook(() => useRateLimit('/x'));
    }).toThrow();
    spy.mockRestore();
  });

  it('returns undefined for untracked', () => {
    const { result } = renderHook(() => useRateLimit('/x'), { wrapper });
    expect(result.current.rateLimit).toBeUndefined();
  });

  it('updates rate limit', () => {
    const { result } = renderHook(() => useRateLimit('/x'), { wrapper });
    act(() => {
      result.current.update({ limit: 10, remaining: 5, resetAt: new Date() });
    });
    expect(result.current.remaining).toBe(5);
  });

  it('sets isLimited', () => {
    const { result } = renderHook(() => useRateLimit('/x'), { wrapper });
    act(() => {
      result.current.update({ limit: 10, remaining: 0, resetAt: new Date() });
    });
    expect(result.current.isLimited).toBe(true);
  });

  it('clears', () => {
    const { result } = renderHook(() => useRateLimit('/x'), { wrapper });
    act(() => {
      result.current.update({ limit: 10, remaining: 5, resetAt: new Date() });
    });
    act(() => {
      result.current.clear();
    });
    expect(result.current.rateLimit).toBeUndefined();
  });

  it('stable callbacks', () => {
    const { result, rerender } = renderHook(() => useRateLimit('/x'), {
      wrapper,
    });
    const u = result.current.update;
    rerender();
    expect(result.current.update).toBe(u);
  });
});
