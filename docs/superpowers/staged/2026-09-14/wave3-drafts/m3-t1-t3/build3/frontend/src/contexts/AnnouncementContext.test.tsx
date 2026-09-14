/**
 * Tests for AnnouncementContext.
 *
 * This test suite covers the AnnouncementContext provider and useAnnounce hook,
 * including announcement creation, politeness levels, message clearing for
 * repeated announcements, and proper LiveRegion rendering.
 */
import { act, render, renderHook, screen } from '@testing-library/react';
import { type ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  AnnouncementProvider,
  useAnnounce,
  type AnnouncementProviderProps,
} from './AnnouncementContext';

/**
 * Helper to create a wrapper component for renderHook.
 */
function createWrapper(props: Partial<AnnouncementProviderProps> = {}) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <AnnouncementProvider {...props}>{children}</AnnouncementProvider>;
  };
}

describe('AnnouncementContext', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  describe('useAnnounce hook', () => {
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
  });

  describe('AnnouncementProvider', () => {
    it('should render children correctly', () => {
      render(
        <AnnouncementProvider>
          <div data-testid="child">Child content</div>
        </AnnouncementProvider>
      );

      expect(screen.getByTestId('child')).toBeInTheDocument();
    });

    it('should render LiveRegion component', () => {
      render(
        <AnnouncementProvider>
          <div>Content</div>
        </AnnouncementProvider>
      );

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('should render LiveRegion with sr-only class', () => {
      render(
        <AnnouncementProvider>
          <div>Content</div>
        </AnnouncementProvider>
      );

      expect(screen.getByRole('status')).toHaveClass('sr-only');
    });
  });

  describe('announce function', () => {
    it('should announce a message with polite politeness by default', () => {
      const { result } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.announce('Test announcement');
      });

      // Advance timer past the clearing delay
      act(() => {
        vi.advanceTimersByTime(150);
      });

      const region = screen.getByRole('status');
      expect(region).toHaveAttribute('aria-live', 'polite');
      expect(region).toHaveTextContent('Test announcement');
    });

    it('should announce a message with assertive politeness', () => {
      const { result } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.announce('Urgent message', 'assertive');
      });

      act(() => {
        vi.advanceTimersByTime(150);
      });

      const region = screen.getByRole('status');
      expect(region).toHaveAttribute('aria-live', 'assertive');
      expect(region).toHaveTextContent('Urgent message');
    });

    it('should clear message before setting new message for repeated announcements', () => {
      const { result } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      // First announcement
      act(() => {
        result.current.announce('First message');
      });

      act(() => {
        vi.advanceTimersByTime(150);
      });

      expect(screen.getByRole('status')).toHaveTextContent('First message');

      // Same message repeated - should clear first then set
      act(() => {
        result.current.announce('First message');
      });

      // Message should be empty immediately after calling announce
      expect(screen.getByRole('status')).toHaveTextContent('');

      // After timeout, message should appear again
      act(() => {
        vi.advanceTimersByTime(150);
      });

      expect(screen.getByRole('status')).toHaveTextContent('First message');
    });

    it('should handle sequential different announcements', () => {
      const { result } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.announce('First');
      });

      act(() => {
        vi.advanceTimersByTime(150);
      });

      expect(screen.getByRole('status')).toHaveTextContent('First');

      act(() => {
        result.current.announce('Second');
      });

      // Initially empty during clear
      expect(screen.getByRole('status')).toHaveTextContent('');

      act(() => {
        vi.advanceTimersByTime(150);
      });

      expect(screen.getByRole('status')).toHaveTextContent('Second');
    });

    it('should handle empty message', () => {
      const { result } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.announce('');
      });

      act(() => {
        vi.advanceTimersByTime(150);
      });

      expect(screen.getByRole('status')).toHaveTextContent('');
    });

    it('should handle special characters in message', () => {
      const { result } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      const specialMessage = '<script>alert("xss")</script> & "quotes"';

      act(() => {
        result.current.announce(specialMessage);
      });

      act(() => {
        vi.advanceTimersByTime(150);
      });

      expect(screen.getByRole('status')).toHaveTextContent(specialMessage);
    });

    it('should handle unicode characters in message', () => {
      const { result } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      const unicodeMessage = 'Success! Operation complete';

      act(() => {
        result.current.announce(unicodeMessage);
      });

      act(() => {
        vi.advanceTimersByTime(150);
      });

      expect(screen.getByRole('status')).toHaveTextContent(unicodeMessage);
    });

    it('should switch politeness level correctly', () => {
      const { result } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      // Polite first
      act(() => {
        result.current.announce('Polite message', 'polite');
      });

      act(() => {
        vi.advanceTimersByTime(150);
      });

      expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');

      // Then assertive
      act(() => {
        result.current.announce('Assertive message', 'assertive');
      });

      act(() => {
        vi.advanceTimersByTime(150);
      });

      expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'assertive');
    });
  });

  describe('callback stability', () => {
    it('should maintain announce function reference stability', () => {
      const { result, rerender } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      const firstAnnounce = result.current.announce;

      rerender();

      expect(result.current.announce).toBe(firstAnnounce);
    });
  });

  describe('LiveRegion ARIA attributes', () => {
    it('should have aria-atomic="true"', () => {
      render(
        <AnnouncementProvider>
          <div>Content</div>
        </AnnouncementProvider>
      );

      expect(screen.getByRole('status')).toHaveAttribute('aria-atomic', 'true');
    });
  });

  describe('rapid announcements', () => {
    it('should handle rapid sequential announcements', () => {
      const { result } = renderHook(() => useAnnounce(), {
        wrapper: createWrapper(),
      });

      // Fire multiple announcements rapidly
      act(() => {
        result.current.announce('First');
        result.current.announce('Second');
        result.current.announce('Third');
      });

      // Only the last announcement should persist after all timers
      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(screen.getByRole('status')).toHaveTextContent('Third');
    });
  });
});
