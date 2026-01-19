/**
 * Tests for useAnnounce hook.
 *
 * This test suite covers the standalone useAnnounce hook export,
 * verifying it correctly re-exports the context hook functionality.
 */
import { renderHook, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useAnnounce } from './useAnnounce';
import { AnnouncementProvider } from '../contexts/AnnouncementContext';

/**
 * Helper to create a wrapper component for renderHook.
 */
function createWrapper() {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <AnnouncementProvider>{children}</AnnouncementProvider>;
  };
}

describe('useAnnounce hook', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('should throw error when used outside AnnouncementProvider', () => {
    // Suppress console.error for expected error
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      renderHook(() => useAnnounce());
    }).toThrow('useAnnounce must be used within an AnnouncementProvider');

    consoleSpy.mockRestore();
  });

  it('should return announce function when used within AnnouncementProvider', () => {
    const { result } = renderHook(() => useAnnounce(), {
      wrapper: createWrapper(),
    });

    expect(result.current.announce).toBeDefined();
    expect(typeof result.current.announce).toBe('function');
  });

  it('should provide announce function that works correctly', () => {
    const { result } = renderHook(() => useAnnounce(), {
      wrapper: createWrapper(),
    });

    // Should not throw when calling announce
    expect(() => {
      act(() => {
        result.current.announce('Test announcement');
      });
    }).not.toThrow();

    // Advance timers to complete the announcement
    act(() => {
      vi.advanceTimersByTime(150);
    });
  });

  it('should accept politeness parameter', () => {
    const { result } = renderHook(() => useAnnounce(), {
      wrapper: createWrapper(),
    });

    expect(() => {
      act(() => {
        result.current.announce('Polite message', 'polite');
      });
    }).not.toThrow();

    expect(() => {
      act(() => {
        result.current.announce('Assertive message', 'assertive');
      });
    }).not.toThrow();

    act(() => {
      vi.advanceTimersByTime(150);
    });
  });

  it('should maintain stable function reference across renders', () => {
    const { result, rerender } = renderHook(() => useAnnounce(), {
      wrapper: createWrapper(),
    });

    const firstAnnounce = result.current.announce;

    rerender();

    expect(result.current.announce).toBe(firstAnnounce);
  });
});
