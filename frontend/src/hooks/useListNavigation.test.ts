/**
 * Tests for useListNavigation hook
 *
 * This hook provides j/k navigation for lists (like Vim).
 * Also supports Home/End for jumping to first/last items.
 */

import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';

import { useListNavigation } from './useListNavigation';

describe('useListNavigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const simulateKeyPress = (key: string, options: Partial<KeyboardEventInit> = {}) => {
    const event = new KeyboardEvent('keydown', {
      key,
      bubbles: true,
      ...options,
    });
    document.dispatchEvent(event);
  };

  describe('j/k navigation', () => {
    it('moves down (increases index) when j is pressed', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 5 }));

      expect(result.current.selectedIndex).toBe(0);

      act(() => {
        simulateKeyPress('j');
      });

      expect(result.current.selectedIndex).toBe(1);
    });

    it('moves up (decreases index) when k is pressed', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 5, initialIndex: 2 }));

      expect(result.current.selectedIndex).toBe(2);

      act(() => {
        simulateKeyPress('k');
      });

      expect(result.current.selectedIndex).toBe(1);
    });

    it('does not go below 0 when k is pressed at the beginning', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 5 }));

      expect(result.current.selectedIndex).toBe(0);

      act(() => {
        simulateKeyPress('k');
      });

      expect(result.current.selectedIndex).toBe(0);
    });

    it('does not go above itemCount - 1 when j is pressed at the end', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 5, initialIndex: 4 }));

      expect(result.current.selectedIndex).toBe(4);

      act(() => {
        simulateKeyPress('j');
      });

      expect(result.current.selectedIndex).toBe(4);
    });

    it('supports wrapping when wrap option is true', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 3, wrap: true }));

      // At beginning, go up wraps to end
      act(() => {
        simulateKeyPress('k');
      });

      expect(result.current.selectedIndex).toBe(2);

      // At end, go down wraps to beginning
      act(() => {
        simulateKeyPress('j');
      });

      expect(result.current.selectedIndex).toBe(0);
    });
  });

  describe('Arrow key navigation', () => {
    it('moves down when ArrowDown is pressed', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 5 }));

      act(() => {
        simulateKeyPress('ArrowDown');
      });

      expect(result.current.selectedIndex).toBe(1);
    });

    it('moves up when ArrowUp is pressed', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 5, initialIndex: 2 }));

      act(() => {
        simulateKeyPress('ArrowUp');
      });

      expect(result.current.selectedIndex).toBe(1);
    });
  });

  describe('Home/End navigation', () => {
    it('jumps to first item when Home is pressed', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 10, initialIndex: 5 }));

      act(() => {
        simulateKeyPress('Home');
      });

      expect(result.current.selectedIndex).toBe(0);
    });

    it('jumps to last item when End is pressed', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 10, initialIndex: 0 }));

      act(() => {
        simulateKeyPress('End');
      });

      expect(result.current.selectedIndex).toBe(9);
    });
  });

  describe('Enter key selection', () => {
    it('calls onSelect when Enter is pressed', () => {
      const onSelect = vi.fn();
      renderHook(() => useListNavigation({ itemCount: 5, onSelect }));

      act(() => {
        simulateKeyPress('j'); // Move to index 1
      });

      act(() => {
        simulateKeyPress('Enter');
      });

      expect(onSelect).toHaveBeenCalledWith(1);
    });

    it('does not call onSelect when callback is not provided', () => {
      // Should not throw when Enter is pressed without onSelect callback
      renderHook(() => useListNavigation({ itemCount: 5 }));

      act(() => {
        simulateKeyPress('Enter');
      });
    });
  });

  describe('input field handling', () => {
    it('does not navigate when typing in an input field', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 5 }));

      const input = document.createElement('input');
      document.body.appendChild(input);
      input.focus();

      const event = new KeyboardEvent('keydown', {
        key: 'j',
        bubbles: true,
      });
      Object.defineProperty(event, 'target', { value: input });
      document.dispatchEvent(event);

      expect(result.current.selectedIndex).toBe(0);

      document.body.removeChild(input);
    });
  });

  describe('enabled option', () => {
    it('does not respond to keys when disabled', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 5, enabled: false }));

      act(() => {
        simulateKeyPress('j');
      });

      expect(result.current.selectedIndex).toBe(0);
    });

    it('resumes responding when re-enabled', () => {
      const { result, rerender } = renderHook(
        ({ enabled }) => useListNavigation({ itemCount: 5, enabled }),
        { initialProps: { enabled: false } }
      );

      act(() => {
        simulateKeyPress('j');
      });
      expect(result.current.selectedIndex).toBe(0);

      rerender({ enabled: true });

      act(() => {
        simulateKeyPress('j');
      });
      expect(result.current.selectedIndex).toBe(1);
    });
  });

  describe('programmatic control', () => {
    it('provides setSelectedIndex for programmatic control', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 10 }));

      act(() => {
        result.current.setSelectedIndex(5);
      });

      expect(result.current.selectedIndex).toBe(5);
    });

    it('clamps programmatic index to valid range', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 5 }));

      act(() => {
        result.current.setSelectedIndex(100);
      });

      expect(result.current.selectedIndex).toBe(4);

      act(() => {
        result.current.setSelectedIndex(-10);
      });

      expect(result.current.selectedIndex).toBe(0);
    });
  });

  describe('itemCount changes', () => {
    it('adjusts selectedIndex when itemCount decreases below current index', () => {
      const { result, rerender } = renderHook(
        ({ itemCount }) => useListNavigation({ itemCount, initialIndex: 5 }),
        { initialProps: { itemCount: 10 } }
      );

      expect(result.current.selectedIndex).toBe(5);

      rerender({ itemCount: 3 });

      // Index should be clamped to max valid index (2)
      expect(result.current.selectedIndex).toBe(2);
    });

    it('handles empty list (itemCount = 0)', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 0 }));

      expect(result.current.selectedIndex).toBe(-1);

      // Should not change on navigation attempts
      act(() => {
        simulateKeyPress('j');
      });

      expect(result.current.selectedIndex).toBe(-1);
    });
  });

  describe('cleanup', () => {
    it('removes event listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');

      const { unmount } = renderHook(() => useListNavigation({ itemCount: 5 }));
      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
    });
  });

  describe('resetSelection', () => {
    it('provides resetSelection to return to initialIndex', () => {
      const { result } = renderHook(() => useListNavigation({ itemCount: 10, initialIndex: 3 }));

      act(() => {
        result.current.setSelectedIndex(7);
      });
      expect(result.current.selectedIndex).toBe(7);

      act(() => {
        result.current.resetSelection();
      });
      expect(result.current.selectedIndex).toBe(3);
    });
  });
});
