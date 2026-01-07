/**
 * Tests for ToastContext.
 *
 * This test suite covers the ToastContext provider and useToast hook,
 * including toast creation, dismissal, auto-dismiss functionality,
 * and stacking behavior.
 */
import { act, renderHook } from '@testing-library/react';
import { type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  DEFAULT_TOAST_DURATION,
  MAX_TOASTS,
  ToastProvider,
  useToast,
  type ToastProviderProps,
} from './ToastContext';

/**
 * Helper to create a wrapper component for renderHook.
 */
function createWrapper(props: Partial<ToastProviderProps> = {}) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <ToastProvider {...props}>{children}</ToastProvider>;
  };
}

describe('ToastContext', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  describe('useToast hook', () => {
    it('should throw error when used outside ToastProvider', () => {
      // Suppress console.error for expected error
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        renderHook(() => useToast());
      }).toThrow('useToast must be used within a ToastProvider');

      consoleSpy.mockRestore();
    });

    it('should return context methods when used within ToastProvider', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      expect(result.current.showToast).toBeDefined();
      expect(result.current.dismissToast).toBeDefined();
      expect(result.current.toasts).toEqual([]);
      expect(typeof result.current.showToast).toBe('function');
      expect(typeof result.current.dismissToast).toBe('function');
    });

    it('should initialize with empty toasts array', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      expect(result.current.toasts).toHaveLength(0);
    });
  });

  describe('showToast', () => {
    it('should add a success toast', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.showToast('Success message', 'success');
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe('Success message');
      expect(result.current.toasts[0].type).toBe('success');
    });

    it('should add an error toast', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.showToast('Error message', 'error');
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe('Error message');
      expect(result.current.toasts[0].type).toBe('error');
    });

    it('should add an info toast', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.showToast('Info message', 'info');
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe('Info message');
      expect(result.current.toasts[0].type).toBe('info');
    });

    it('should return unique toast ID', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      let id1: string = '';
      let id2: string = '';

      act(() => {
        id1 = result.current.showToast('First toast', 'success');
        id2 = result.current.showToast('Second toast', 'success');
      });

      expect(id1).toBeTruthy();
      expect(id2).toBeTruthy();
      expect(id1).not.toBe(id2);
      expect(id1).toMatch(/^toast-/);
      expect(id2).toMatch(/^toast-/);
    });

    it('should set createdAt timestamp', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      const beforeTime = Date.now();

      act(() => {
        result.current.showToast('Test toast', 'info');
      });

      const afterTime = Date.now();

      expect(result.current.toasts[0].createdAt).toBeGreaterThanOrEqual(beforeTime);
      expect(result.current.toasts[0].createdAt).toBeLessThanOrEqual(afterTime);
    });

    it('should stack multiple toasts', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.showToast('First', 'success');
        result.current.showToast('Second', 'error');
        result.current.showToast('Third', 'info');
      });

      expect(result.current.toasts).toHaveLength(3);
      expect(result.current.toasts[0].message).toBe('First');
      expect(result.current.toasts[1].message).toBe('Second');
      expect(result.current.toasts[2].message).toBe('Third');
    });
  });

  describe('dismissToast', () => {
    it('should remove toast by ID', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      let toastId: string = '';

      act(() => {
        toastId = result.current.showToast('Dismissable toast', 'success');
      });

      expect(result.current.toasts).toHaveLength(1);

      act(() => {
        result.current.dismissToast(toastId);
      });

      expect(result.current.toasts).toHaveLength(0);
    });

    it('should only remove the specified toast', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      let id1: string = '';
      let id2: string = '';
      let id3: string = '';

      act(() => {
        id1 = result.current.showToast('First', 'success');
        id2 = result.current.showToast('Second', 'error');
        id3 = result.current.showToast('Third', 'info');
      });

      expect(result.current.toasts).toHaveLength(3);

      act(() => {
        result.current.dismissToast(id2);
      });

      expect(result.current.toasts).toHaveLength(2);
      expect(result.current.toasts.find((t) => t.id === id1)).toBeDefined();
      expect(result.current.toasts.find((t) => t.id === id2)).toBeUndefined();
      expect(result.current.toasts.find((t) => t.id === id3)).toBeDefined();
    });

    it('should handle dismissing non-existent toast gracefully', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.showToast('Existing toast', 'success');
      });

      expect(result.current.toasts).toHaveLength(1);

      act(() => {
        result.current.dismissToast('non-existent-id');
      });

      expect(result.current.toasts).toHaveLength(1);
    });

    it('should handle dismissing from empty toasts array', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      expect(result.current.toasts).toHaveLength(0);

      act(() => {
        result.current.dismissToast('any-id');
      });

      expect(result.current.toasts).toHaveLength(0);
    });
  });

  describe('auto-dismiss', () => {
    it('should auto-dismiss toast after default duration', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.showToast('Auto-dismiss toast', 'success');
      });

      expect(result.current.toasts).toHaveLength(1);

      // Fast-forward past the default duration
      act(() => {
        vi.advanceTimersByTime(DEFAULT_TOAST_DURATION + 100);
      });

      expect(result.current.toasts).toHaveLength(0);
    });

    it('should auto-dismiss toast after custom duration', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      const customDuration = 2000;

      act(() => {
        result.current.showToast('Custom duration toast', 'success', customDuration);
      });

      expect(result.current.toasts).toHaveLength(1);

      // Should still be visible before custom duration
      act(() => {
        vi.advanceTimersByTime(customDuration - 100);
      });

      expect(result.current.toasts).toHaveLength(1);

      // Should be dismissed after custom duration
      act(() => {
        vi.advanceTimersByTime(200);
      });

      expect(result.current.toasts).toHaveLength(0);
    });

    it('should respect custom defaultDuration from provider', () => {
      const customDefault = 3000;
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper({ defaultDuration: customDefault }),
      });

      act(() => {
        result.current.showToast('Provider default toast', 'success');
      });

      expect(result.current.toasts).toHaveLength(1);

      // Should still be visible before custom default
      act(() => {
        vi.advanceTimersByTime(customDefault - 100);
      });

      expect(result.current.toasts).toHaveLength(1);

      // Should be dismissed after custom default
      act(() => {
        vi.advanceTimersByTime(200);
      });

      expect(result.current.toasts).toHaveLength(0);
    });

    it('should not auto-dismiss when duration is 0', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.showToast('Persistent toast', 'success', 0);
      });

      expect(result.current.toasts).toHaveLength(1);

      // Fast-forward a long time
      act(() => {
        vi.advanceTimersByTime(100000);
      });

      // Should still be visible
      expect(result.current.toasts).toHaveLength(1);
    });

    it('should handle multiple toasts with different durations', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.showToast('Short duration', 'success', 1000);
        result.current.showToast('Medium duration', 'info', 3000);
        result.current.showToast('Long duration', 'error', 5000);
      });

      expect(result.current.toasts).toHaveLength(3);

      // After 1.1s, first toast should be gone
      act(() => {
        vi.advanceTimersByTime(1100);
      });

      expect(result.current.toasts).toHaveLength(2);
      expect(result.current.toasts.map((t) => t.message)).toEqual([
        'Medium duration',
        'Long duration',
      ]);

      // After 3.1s total, second toast should be gone
      act(() => {
        vi.advanceTimersByTime(2000);
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe('Long duration');

      // After 5.1s total, all should be gone
      act(() => {
        vi.advanceTimersByTime(2000);
      });

      expect(result.current.toasts).toHaveLength(0);
    });

    it('should still auto-dismiss even if manually dismissed first', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      let toastId: string = '';

      act(() => {
        toastId = result.current.showToast('Test toast', 'success', 5000);
      });

      expect(result.current.toasts).toHaveLength(1);

      // Manually dismiss before timeout
      act(() => {
        result.current.dismissToast(toastId);
      });

      expect(result.current.toasts).toHaveLength(0);

      // Let the auto-dismiss timer fire - should not cause issues
      act(() => {
        vi.advanceTimersByTime(6000);
      });

      expect(result.current.toasts).toHaveLength(0);
    });
  });

  describe('max toasts limit', () => {
    it('should respect default MAX_TOASTS limit', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      // Add more toasts than the limit
      act(() => {
        for (let i = 0; i < MAX_TOASTS + 3; i++) {
          result.current.showToast(`Toast ${i}`, 'info');
        }
      });

      expect(result.current.toasts).toHaveLength(MAX_TOASTS);
    });

    it('should remove oldest toast when limit exceeded', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper({ maxToasts: 3 }),
      });

      act(() => {
        result.current.showToast('First', 'success');
        result.current.showToast('Second', 'error');
        result.current.showToast('Third', 'info');
      });

      expect(result.current.toasts).toHaveLength(3);
      expect(result.current.toasts.map((t) => t.message)).toEqual([
        'First',
        'Second',
        'Third',
      ]);

      act(() => {
        result.current.showToast('Fourth', 'success');
      });

      expect(result.current.toasts).toHaveLength(3);
      expect(result.current.toasts.map((t) => t.message)).toEqual([
        'Second',
        'Third',
        'Fourth',
      ]);
    });

    it('should respect custom maxToasts from provider', () => {
      const customMax = 2;
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper({ maxToasts: customMax }),
      });

      act(() => {
        result.current.showToast('First', 'success');
        result.current.showToast('Second', 'error');
        result.current.showToast('Third', 'info');
      });

      expect(result.current.toasts).toHaveLength(customMax);
      expect(result.current.toasts.map((t) => t.message)).toEqual(['Second', 'Third']);
    });

    it('should handle maxToasts of 1', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper({ maxToasts: 1 }),
      });

      act(() => {
        result.current.showToast('First', 'success');
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe('First');

      act(() => {
        result.current.showToast('Second', 'error');
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe('Second');
    });
  });

  describe('callback stability', () => {
    it('should maintain showToast reference stability', () => {
      const { result, rerender } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      const firstShowToast = result.current.showToast;

      rerender();

      expect(result.current.showToast).toBe(firstShowToast);
    });

    it('should maintain dismissToast reference stability', () => {
      const { result, rerender } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      const firstDismissToast = result.current.dismissToast;

      rerender();

      expect(result.current.dismissToast).toBe(firstDismissToast);
    });
  });

  describe('edge cases', () => {
    it('should handle empty message', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.showToast('', 'info');
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe('');
    });

    it('should handle very long message', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      const longMessage = 'A'.repeat(1000);

      act(() => {
        result.current.showToast(longMessage, 'info');
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe(longMessage);
    });

    it('should handle special characters in message', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      const specialMessage = '<script>alert("xss")</script> & "quotes" \'single\' `backticks`';

      act(() => {
        result.current.showToast(specialMessage, 'info');
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe(specialMessage);
    });

    it('should handle unicode characters in message', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      const unicodeMessage = 'Hello World! Success!';

      act(() => {
        result.current.showToast(unicodeMessage, 'success');
      });

      expect(result.current.toasts).toHaveLength(1);
      expect(result.current.toasts[0].message).toBe(unicodeMessage);
    });

    it('should handle rapid sequential toasts', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper({ maxToasts: 100 }),
      });

      act(() => {
        for (let i = 0; i < 50; i++) {
          result.current.showToast(`Toast ${i}`, 'info');
        }
      });

      expect(result.current.toasts).toHaveLength(50);
      expect(result.current.toasts[0].message).toBe('Toast 0');
      expect(result.current.toasts[49].message).toBe('Toast 49');
    });

    it('should generate unique IDs even for identical toasts', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      const ids: string[] = [];

      act(() => {
        for (let i = 0; i < 10; i++) {
          ids.push(result.current.showToast('Same message', 'success'));
        }
      });

      const uniqueIds = new Set(ids);
      expect(uniqueIds.size).toBe(10);
    });
  });

  describe('provider props', () => {
    it('should use default values when no props provided', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      // Add max + 1 toasts to verify default maxToasts
      act(() => {
        for (let i = 0; i < MAX_TOASTS + 1; i++) {
          result.current.showToast(`Toast ${i}`, 'info');
        }
      });

      expect(result.current.toasts).toHaveLength(MAX_TOASTS);
    });

    it('should render children correctly', () => {
      const { result } = renderHook(() => useToast(), {
        wrapper: createWrapper(),
      });

      // If we get here, children rendered correctly
      expect(result.current).toBeDefined();
    });
  });

  describe('constants', () => {
    it('should export DEFAULT_TOAST_DURATION', () => {
      expect(DEFAULT_TOAST_DURATION).toBe(5000);
    });

    it('should export MAX_TOASTS', () => {
      expect(MAX_TOASTS).toBe(5);
    });
  });
});
