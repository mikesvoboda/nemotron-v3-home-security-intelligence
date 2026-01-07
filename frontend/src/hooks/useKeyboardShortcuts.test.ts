/**
 * Tests for useKeyboardShortcuts hook
 *
 * This hook provides global keyboard navigation shortcuts for the application.
 * Supports single-key shortcuts (like 'j' for next) and chord shortcuts (like 'g d' for go to dashboard).
 */

import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, beforeEach, vi, afterEach } from 'vitest';

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

import { useKeyboardShortcuts } from './useKeyboardShortcuts';

describe('useKeyboardShortcuts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
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

  describe('single-key navigation shortcuts', () => {
    it('does not navigate when typing in an input field', () => {
      renderHook(() => useKeyboardShortcuts());

      // Simulate typing in an input
      const input = document.createElement('input');
      document.body.appendChild(input);
      input.focus();

      const event = new KeyboardEvent('keydown', {
        key: 'g',
        bubbles: true,
      });
      Object.defineProperty(event, 'target', { value: input });
      document.dispatchEvent(event);

      expect(mockNavigate).not.toHaveBeenCalled();

      document.body.removeChild(input);
    });

    it('does not navigate when typing in a textarea', () => {
      renderHook(() => useKeyboardShortcuts());

      const textarea = document.createElement('textarea');
      document.body.appendChild(textarea);
      textarea.focus();

      const event = new KeyboardEvent('keydown', {
        key: 'g',
        bubbles: true,
      });
      Object.defineProperty(event, 'target', { value: textarea });
      document.dispatchEvent(event);

      expect(mockNavigate).not.toHaveBeenCalled();

      document.body.removeChild(textarea);
    });

    it('does not navigate when typing in a contenteditable element', () => {
      renderHook(() => useKeyboardShortcuts());

      const div = document.createElement('div');
      div.contentEditable = 'true';
      document.body.appendChild(div);
      div.focus();

      const event = new KeyboardEvent('keydown', {
        key: 'g',
        bubbles: true,
      });
      Object.defineProperty(event, 'target', { value: div });
      document.dispatchEvent(event);

      expect(mockNavigate).not.toHaveBeenCalled();

      document.body.removeChild(div);
    });
  });

  describe('chord shortcuts (g + key)', () => {
    it('navigates to dashboard with g d', () => {
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('d');
      });

      expect(mockNavigate).toHaveBeenCalledWith('/');
    });

    it('navigates to timeline with g t', () => {
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('t');
      });

      expect(mockNavigate).toHaveBeenCalledWith('/timeline');
    });

    it('navigates to analytics with g a', () => {
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('a');
      });

      expect(mockNavigate).toHaveBeenCalledWith('/analytics');
    });

    it('navigates to alerts with g l', () => {
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('l');
      });

      expect(mockNavigate).toHaveBeenCalledWith('/alerts');
    });

    it('navigates to entities with g e', () => {
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('e');
      });

      expect(mockNavigate).toHaveBeenCalledWith('/entities');
    });

    it('navigates to logs with g o', () => {
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('o');
      });

      expect(mockNavigate).toHaveBeenCalledWith('/logs');
    });

    it('navigates to system monitoring with g s', () => {
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('s');
      });

      expect(mockNavigate).toHaveBeenCalledWith('/system');
    });

    it('navigates to settings with g ,', () => {
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress(',');
      });

      expect(mockNavigate).toHaveBeenCalledWith('/settings');
    });

    it('resets chord after timeout', () => {
      const { result } = renderHook(() => useKeyboardShortcuts());

      // Start the chord with 'g'
      act(() => {
        simulateKeyPress('g');
      });

      // Verify chord is pending
      expect(result.current.isPendingChord).toBe(true);

      // Wait for chord timeout (1000ms) and trigger state update
      act(() => {
        vi.advanceTimersByTime(1001);
      });

      // Verify chord is no longer pending
      expect(result.current.isPendingChord).toBe(false);

      // Clear mock calls before testing the navigation
      mockNavigate.mockClear();

      // Now press 'd' - should not navigate because chord timed out
      act(() => {
        simulateKeyPress('d');
      });

      // Should not navigate because chord timed out (d alone starts no chord)
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('resets chord when invalid second key is pressed', () => {
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('x'); // Invalid chord
      });

      expect(mockNavigate).not.toHaveBeenCalled();

      // Now try a new chord
      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('d');
      });

      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  describe('help modal shortcut', () => {
    it('calls onOpenHelp when ? is pressed', () => {
      const onOpenHelp = vi.fn();
      renderHook(() => useKeyboardShortcuts({ onOpenHelp }));

      act(() => {
        simulateKeyPress('?');
      });

      expect(onOpenHelp).toHaveBeenCalledTimes(1);
    });

    it('does not call onOpenHelp when not provided', () => {
      // Should not throw
      renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('?');
      });
    });
  });

  describe('command palette shortcut', () => {
    it('calls onOpenCommandPalette when Cmd+K is pressed on Mac', () => {
      const onOpenCommandPalette = vi.fn();
      renderHook(() => useKeyboardShortcuts({ onOpenCommandPalette }));

      act(() => {
        simulateKeyPress('k', { metaKey: true });
      });

      expect(onOpenCommandPalette).toHaveBeenCalledTimes(1);
    });

    it('calls onOpenCommandPalette when Ctrl+K is pressed on Windows/Linux', () => {
      const onOpenCommandPalette = vi.fn();
      renderHook(() => useKeyboardShortcuts({ onOpenCommandPalette }));

      act(() => {
        simulateKeyPress('k', { ctrlKey: true });
      });

      expect(onOpenCommandPalette).toHaveBeenCalledTimes(1);
    });

    it('does not call onOpenCommandPalette when K is pressed without modifier', () => {
      const onOpenCommandPalette = vi.fn();
      renderHook(() => useKeyboardShortcuts({ onOpenCommandPalette }));

      act(() => {
        simulateKeyPress('k');
      });

      expect(onOpenCommandPalette).not.toHaveBeenCalled();
    });
  });

  describe('escape shortcut', () => {
    it('calls onEscape when Escape is pressed', () => {
      const onEscape = vi.fn();
      renderHook(() => useKeyboardShortcuts({ onEscape }));

      act(() => {
        simulateKeyPress('Escape');
      });

      expect(onEscape).toHaveBeenCalledTimes(1);
    });
  });

  describe('cleanup', () => {
    it('removes event listeners on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');

      const { unmount } = renderHook(() => useKeyboardShortcuts());
      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
    });
  });

  describe('disabled state', () => {
    it('does not respond to shortcuts when disabled', () => {
      const onOpenHelp = vi.fn();
      renderHook(() => useKeyboardShortcuts({ onOpenHelp, enabled: false }));

      act(() => {
        simulateKeyPress('?');
      });

      expect(onOpenHelp).not.toHaveBeenCalled();
    });

    it('resumes responding when re-enabled', () => {
      const onOpenHelp = vi.fn();
      const { rerender } = renderHook(
        ({ enabled }) => useKeyboardShortcuts({ onOpenHelp, enabled }),
        { initialProps: { enabled: false } }
      );

      act(() => {
        simulateKeyPress('?');
      });
      expect(onOpenHelp).not.toHaveBeenCalled();

      rerender({ enabled: true });

      act(() => {
        simulateKeyPress('?');
      });
      expect(onOpenHelp).toHaveBeenCalledTimes(1);
    });
  });

  describe('pending chord state', () => {
    it('returns isPendingChord true when g is pressed', () => {
      const { result } = renderHook(() => useKeyboardShortcuts());

      expect(result.current.isPendingChord).toBe(false);

      act(() => {
        simulateKeyPress('g');
      });

      expect(result.current.isPendingChord).toBe(true);
    });

    it('returns isPendingChord false after chord is completed', () => {
      const { result } = renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      act(() => {
        simulateKeyPress('d');
      });

      expect(result.current.isPendingChord).toBe(false);
    });

    it('returns isPendingChord false after timeout', () => {
      const { result } = renderHook(() => useKeyboardShortcuts());

      act(() => {
        simulateKeyPress('g');
      });

      expect(result.current.isPendingChord).toBe(true);

      // Advance past chord timeout and flush state updates
      act(() => {
        vi.advanceTimersByTime(1001);
      });

      expect(result.current.isPendingChord).toBe(false);
    });
  });
});
