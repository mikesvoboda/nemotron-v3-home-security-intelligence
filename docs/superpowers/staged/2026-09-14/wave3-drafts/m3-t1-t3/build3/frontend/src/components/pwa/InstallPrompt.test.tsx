/**
 * Tests for InstallPrompt component
 *
 * PWA install prompt that captures the beforeinstallprompt event
 * and displays a custom install banner after engagement criteria are met.
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import InstallPrompt from './InstallPrompt';

// ============================================================================
// Types
// ============================================================================

/**
 * Mock BeforeInstallPromptEvent for testing
 */
interface MockBeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Create a mock BeforeInstallPromptEvent
 */
function createMockBeforeInstallPromptEvent(
  outcome: 'accepted' | 'dismissed' = 'accepted'
): MockBeforeInstallPromptEvent {
  const event = new Event('beforeinstallprompt', {
    bubbles: true,
    cancelable: true,
  }) as MockBeforeInstallPromptEvent;

  event.prompt = vi.fn().mockResolvedValue(undefined);
  event.userChoice = Promise.resolve({ outcome, platform: 'web' });

  return event;
}

/**
 * Dispatch beforeinstallprompt event on window
 */
function dispatchBeforeInstallPromptEvent(
  outcome: 'accepted' | 'dismissed' = 'accepted'
): MockBeforeInstallPromptEvent {
  const event = createMockBeforeInstallPromptEvent(outcome);
  window.dispatchEvent(event);
  return event;
}

/**
 * Helper to flush all promises in the microtask queue
 */
async function flushPromises(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
  });
}

// ============================================================================
// Tests
// ============================================================================

describe('InstallPrompt', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  describe('rendering', () => {
    it('renders nothing initially when no event captured', () => {
      const { container } = render(<InstallPrompt />);
      expect(container).toBeEmptyDOMElement();
    });

    it('renders nothing if no beforeinstallprompt event is fired', () => {
      render(<InstallPrompt />);
      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });

    it('renders nothing even with event if engagement criteria not met', () => {
      render(<InstallPrompt minVisits={2} minTimeOnSite={30000} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });
  });

  describe('engagement criteria - visits', () => {
    it('shows banner after minimum visits is reached', () => {
      // Set up previous visits
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.getByTestId('install-prompt')).toBeInTheDocument();
    });

    it('increments visit count on mount', () => {
      expect(localStorage.getItem('pwa-visit-count')).toBeNull();

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      expect(localStorage.getItem('pwa-visit-count')).toBe('1');
    });

    it('does not show banner if visits below threshold', () => {
      localStorage.setItem('pwa-visit-count', '1');

      render(<InstallPrompt minVisits={3} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });
  });

  describe('engagement criteria - time on site', () => {
    it('shows banner after minimum time on site', () => {
      render(<InstallPrompt minVisits={0} minTimeOnSite={30000} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      // Banner should not show initially
      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();

      // Advance time past threshold
      act(() => {
        vi.advanceTimersByTime(31000);
      });

      expect(screen.getByTestId('install-prompt')).toBeInTheDocument();
    });

    it('does not show banner before time threshold', () => {
      render(<InstallPrompt minVisits={0} minTimeOnSite={30000} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      act(() => {
        vi.advanceTimersByTime(10000);
      });

      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });
  });

  describe('combined engagement criteria', () => {
    it('shows banner when both criteria are met', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={30000} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      // Not shown yet - time not met
      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(31000);
      });

      expect(screen.getByTestId('install-prompt')).toBeInTheDocument();
    });
  });

  describe('dismissal behavior', () => {
    it('hides banner when dismiss button is clicked', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.getByTestId('install-prompt')).toBeInTheDocument();

      // Use the "Not now" text button specifically
      const dismissButton = screen.getByRole('button', { name: /^not now$/i });
      fireEvent.click(dismissButton);

      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });

    it('stores dismissal in localStorage', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      // Use the "Not now" text button specifically
      const dismissButton = screen.getByRole('button', { name: /^not now$/i });
      fireEvent.click(dismissButton);

      expect(localStorage.getItem('pwa-install-dismissed')).toBeTruthy();
    });

    it('does not show banner if previously dismissed', () => {
      localStorage.setItem('pwa-visit-count', '2');
      localStorage.setItem('pwa-install-dismissed', Date.now().toString());

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });

    it('shows banner again after dismissal cooldown period', () => {
      localStorage.setItem('pwa-visit-count', '2');
      // Set dismissal to 8 days ago
      const eightDaysAgo = Date.now() - 8 * 24 * 60 * 60 * 1000;
      localStorage.setItem('pwa-install-dismissed', eightDaysAgo.toString());

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} dismissCooldownDays={7} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.getByTestId('install-prompt')).toBeInTheDocument();
    });
  });

  describe('installation flow', () => {
    it('calls prompt() when install button is clicked', async () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      const mockEvent = createMockBeforeInstallPromptEvent('accepted');
      act(() => {
        window.dispatchEvent(mockEvent);
      });

      const installButton = screen.getByRole('button', { name: /^install$/i });

      await act(async () => {
        fireEvent.click(installButton);
        await flushPromises();
      });

      expect(mockEvent.prompt).toHaveBeenCalled();
    });

    it('stores installed state on successful installation', async () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent('accepted');
      });

      const installButton = screen.getByRole('button', { name: /^install$/i });

      await act(async () => {
        fireEvent.click(installButton);
        await flushPromises();
      });

      expect(localStorage.getItem('pwa-installed')).toBe('true');
    });

    it('hides banner after successful installation', async () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent('accepted');
      });

      const installButton = screen.getByRole('button', { name: /^install$/i });

      await act(async () => {
        fireEvent.click(installButton);
        await flushPromises();
      });

      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });

    it('hides banner if user dismisses native prompt', async () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent('dismissed');
      });

      const installButton = screen.getByRole('button', { name: /^install$/i });

      await act(async () => {
        fireEvent.click(installButton);
        await flushPromises();
      });

      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });

    it('does not store installed state on dismissed installation', async () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent('dismissed');
      });

      const installButton = screen.getByRole('button', { name: /^install$/i });

      await act(async () => {
        fireEvent.click(installButton);
        await flushPromises();
      });

      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
      expect(localStorage.getItem('pwa-installed')).toBeNull();
    });
  });

  describe('already installed behavior', () => {
    it('does not show banner if already installed', () => {
      localStorage.setItem('pwa-visit-count', '2');
      localStorage.setItem('pwa-installed', 'true');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });
  });

  describe('content display', () => {
    it('displays app name in banner', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.getByText(/security dashboard/i)).toBeInTheDocument();
    });

    it('displays app benefits', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.getByText(/quick access|offline/i)).toBeInTheDocument();
    });

    it('displays install button', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      expect(screen.getByRole('button', { name: /install/i })).toBeInTheDocument();
    });

    it('displays dismiss button', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      // Check for "Not now" button specifically
      expect(screen.getByRole('button', { name: /^not now$/i })).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has proper ARIA role', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      const banner = screen.getByTestId('install-prompt');
      expect(banner).toHaveAttribute('role', 'dialog');
    });

    it('has accessible name via aria-labelledby', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      const banner = screen.getByTestId('install-prompt');
      expect(banner).toHaveAttribute('aria-labelledby');
    });

    it('icon has aria-hidden for screen readers', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      const icon = screen.getByTestId('install-prompt-icon');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('styling', () => {
    it('applies fixed positioning', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      const banner = screen.getByTestId('install-prompt');
      expect(banner).toHaveClass('fixed');
    });

    it('applies custom className', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} minTimeOnSite={0} className="custom-class" />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      const banner = screen.getByTestId('install-prompt');
      expect(banner).toHaveClass('custom-class');
    });
  });

  describe('event cleanup', () => {
    it('cleans up event listener on unmount', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = render(<InstallPrompt />);
      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'beforeinstallprompt',
        expect.any(Function)
      );

      removeEventListenerSpy.mockRestore();
    });
  });

  describe('default props', () => {
    it('uses default minVisits of 2', () => {
      // With 0 previous visits, after increment we have 1 visit
      // Default threshold is 2, so banner should NOT show
      localStorage.setItem('pwa-visit-count', '0');

      render(<InstallPrompt minTimeOnSite={0} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      // Should not show with only 1 visit (default threshold is 2)
      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();
    });

    it('uses default minTimeOnSite of 30000ms', () => {
      localStorage.setItem('pwa-visit-count', '2');

      render(<InstallPrompt minVisits={2} />);

      act(() => {
        dispatchBeforeInstallPromptEvent();
      });

      // Should not show immediately (default time is 30s)
      expect(screen.queryByTestId('install-prompt')).not.toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(31000);
      });

      expect(screen.getByTestId('install-prompt')).toBeInTheDocument();
    });
  });
});
