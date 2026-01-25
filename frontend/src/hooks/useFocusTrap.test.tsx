/**
 * Tests for useFocusTrap hook
 *
 * This hook provides focus trapping for modals and dialogs.
 * - Traps focus within a container element
 * - Returns focus to trigger element on close
 * - Handles Tab and Shift+Tab for cycling through focusable elements
 *
 * Note: Some focus tests are simplified due to jsdom limitations with
 * requestAnimationFrame and focus timing.
 */

import { render, screen, act, renderHook } from '@testing-library/react';
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';

import { useFocusTrap } from './useFocusTrap';

/**
 * Test component that uses useFocusTrap properly with a ref attached to the DOM
 */
function TestModal({
  isActive,
  onEscape,
  returnFocusOnDeactivate = true,
}: {
  isActive: boolean;
  onEscape?: () => void;
  returnFocusOnDeactivate?: boolean;
}) {
  const { containerRef } = useFocusTrap<HTMLDivElement>({
    isActive,
    onEscape,
    returnFocusOnDeactivate,
  });

  if (!isActive) return null;

  return (
    <div ref={containerRef} data-testid="modal-container">
      <button data-testid="button-1">Button 1</button>
      <input data-testid="input-1" type="text" />
      <a href="https://example.com" data-testid="link-1">
        Link 1
      </a>
      <button data-testid="button-2">Button 2</button>
      <button data-testid="close-button">Close</button>
    </div>
  );
}

describe('useFocusTrap', () => {
  beforeEach(() => {
    // Clear any focus
    (document.activeElement as HTMLElement)?.blur?.();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const simulateKeyPress = (key: string, shiftKey = false) => {
    const event = new KeyboardEvent('keydown', {
      key,
      shiftKey,
      bubbles: true,
    });
    document.dispatchEvent(event);
    return event;
  };

  describe('initialization', () => {
    it('returns a ref to attach to the container', () => {
      const { result } = renderHook(() => useFocusTrap({ isActive: true }));

      expect(result.current.containerRef).toBeDefined();
      expect(result.current.containerRef.current).toBeNull();
    });

    it('renders modal container when isActive is true', () => {
      render(<TestModal isActive={true} />);

      expect(screen.getByTestId('modal-container')).toBeInTheDocument();
    });

    it('does not render when isActive is false', () => {
      render(<TestModal isActive={false} />);

      expect(screen.queryByTestId('modal-container')).not.toBeInTheDocument();
    });
  });

  describe('focus cycling with Tab', () => {
    it('wraps focus from last to first element with Tab', () => {
      render(<TestModal isActive={true} />);

      // Focus the last element manually
      const closeButton = screen.getByTestId('close-button');
      closeButton.focus();
      expect(document.activeElement).toBe(closeButton);

      // Tab from last element should wrap to first
      act(() => {
        simulateKeyPress('Tab');
      });

      const firstButton = screen.getByTestId('button-1');
      expect(document.activeElement).toBe(firstButton);
    });

    it('keeps focus within container during Tab', () => {
      render(<TestModal isActive={true} />);

      // Focus a middle element
      const input1 = screen.getByTestId('input-1');
      input1.focus();

      act(() => {
        simulateKeyPress('Tab');
      });

      // Focus should still be in container
      expect(screen.getByTestId('modal-container').contains(document.activeElement)).toBe(true);
    });
  });

  describe('focus cycling with Shift+Tab', () => {
    it('wraps focus from first to last element with Shift+Tab', () => {
      render(<TestModal isActive={true} />);

      // Focus the first element
      const button1 = screen.getByTestId('button-1');
      button1.focus();
      expect(document.activeElement).toBe(button1);

      // Shift+Tab from first element should wrap to last
      act(() => {
        simulateKeyPress('Tab', true);
      });

      const closeButton = screen.getByTestId('close-button');
      expect(document.activeElement).toBe(closeButton);
    });

    it('keeps focus within container during Shift+Tab', () => {
      render(<TestModal isActive={true} />);

      // Focus a middle element
      const input1 = screen.getByTestId('input-1');
      input1.focus();

      act(() => {
        simulateKeyPress('Tab', true);
      });

      // Focus should still be in container
      expect(screen.getByTestId('modal-container').contains(document.activeElement)).toBe(true);
    });
  });

  describe('escape key handling', () => {
    it('calls onEscape when Escape key is pressed', () => {
      const onEscape = vi.fn();
      render(<TestModal isActive={true} onEscape={onEscape} />);

      act(() => {
        simulateKeyPress('Escape');
      });

      expect(onEscape).toHaveBeenCalledTimes(1);
    });

    it('does not throw when onEscape is not provided', () => {
      render(<TestModal isActive={true} />);

      // Should not throw
      expect(() => {
        act(() => {
          simulateKeyPress('Escape');
        });
      }).not.toThrow();
    });
  });

  describe('empty container handling', () => {
    it('handles container with no focusable elements gracefully', () => {
      function EmptyModal({ isActive }: { isActive: boolean }) {
        const { containerRef } = useFocusTrap<HTMLDivElement>({ isActive });

        if (!isActive) return null;

        return (
          <div ref={containerRef} data-testid="empty-modal">
            <p>No focusable elements here</p>
          </div>
        );
      }

      // Should not throw
      expect(() => {
        render(<EmptyModal isActive={true} />);
      }).not.toThrow();

      // Tab should be prevented but not cause errors
      act(() => {
        simulateKeyPress('Tab');
      });
    });
  });

  describe('cleanup', () => {
    it('removes event listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');

      const { unmount } = render(<TestModal isActive={true} />);
      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
    });

    it('removes event listener when deactivated', () => {
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener');

      const { rerender } = render(<TestModal isActive={true} />);
      rerender(<TestModal isActive={false} />);

      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
    });
  });
});
