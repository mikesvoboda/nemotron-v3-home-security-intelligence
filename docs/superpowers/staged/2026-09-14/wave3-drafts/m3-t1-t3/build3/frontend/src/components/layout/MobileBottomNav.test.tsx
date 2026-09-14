import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';

import MobileBottomNav from './MobileBottomNav';

// Mock useIsMobile hook
vi.mock('../../hooks/useIsMobile', () => ({
  useIsMobile: () => true,
}));

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', async () => {
  const actual = await vi.importActual<typeof import('framer-motion')>('framer-motion');
  return {
    ...actual,
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    motion: {
      div: ({
        children,
        className,
        'data-testid': testId,
        role,
        'aria-modal': ariaModal,
        'aria-labelledby': ariaLabelledby,
        'aria-describedby': ariaDescribedby,
        tabIndex,
      }: {
        children: React.ReactNode;
        className?: string;
        'data-testid'?: string;
        role?: string;
        'aria-modal'?: boolean;
        'aria-labelledby'?: string;
        'aria-describedby'?: string;
        tabIndex?: number;
      }) => (
        <div
          className={className}
          data-testid={testId}
          role={role}
          aria-modal={ariaModal}
          aria-labelledby={ariaLabelledby}
          aria-describedby={ariaDescribedby}
          tabIndex={tabIndex}
        >
          {children}
        </div>
      ),
    },
    useReducedMotion: () => false,
  };
});

describe('MobileBottomNav', () => {
  const renderWithRouter = (ui: React.ReactElement) => {
    return render(<BrowserRouter>{ui}</BrowserRouter>);
  };

  describe('Primary Navigation', () => {
    it('renders navigation bar with primary icons', () => {
      renderWithRouter(<MobileBottomNav />);

      // Check for navigation container
      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toBeInTheDocument();

      // Check for primary navigation links
      expect(screen.getByLabelText(/go to dashboard/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/go to timeline/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/go to alerts/i)).toBeInTheDocument();
    });

    it('renders More menu button', () => {
      renderWithRouter(<MobileBottomNav />);

      const moreButton = screen.getByTestId('mobile-nav-more-button');
      expect(moreButton).toBeInTheDocument();
      expect(moreButton).toHaveAttribute('aria-label', 'Open more navigation options');
    });

    it('applies safe area inset padding', () => {
      renderWithRouter(<MobileBottomNav />);

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toHaveClass('pb-safe');
    });

    it('has fixed positioning with correct height', () => {
      renderWithRouter(<MobileBottomNav />);

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toHaveClass('fixed');
      expect(nav).toHaveClass('bottom-0');
      expect(nav).toHaveClass('h-14'); // 56px = 14 * 4
    });

    it('displays notification badge when count is provided', () => {
      renderWithRouter(<MobileBottomNav notificationCount={5} />);

      const badge = screen.getByText('5');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveClass('bg-red-500'); // Badge styling
    });

    it('does not display notification badge when count is 0', () => {
      renderWithRouter(<MobileBottomNav notificationCount={0} />);

      const badge = screen.queryByText('0');
      expect(badge).not.toBeInTheDocument();
    });

    it('displays 9+ for notification counts over 9', () => {
      renderWithRouter(<MobileBottomNav notificationCount={15} />);

      const badge = screen.getByText('9+');
      expect(badge).toBeInTheDocument();
    });

    it('applies active styling to current route', () => {
      renderWithRouter(<MobileBottomNav />);

      // Dashboard link should be active on root path
      const dashboardLink = screen.getByLabelText(/go to dashboard/i);
      expect(dashboardLink).toHaveClass('text-[#76B900]');
    });

    it('has minimum touch target size of 44px', () => {
      renderWithRouter(<MobileBottomNav />);

      const links = screen.getAllByRole('link');
      links.forEach((link) => {
        // Check that link has minimum height/width classes
        const hasMinHeight = link.className.includes('h-11') || link.className.includes('min-h-');
        expect(hasMinHeight).toBe(true);
      });
    });

    it('includes proper ARIA labels for accessibility', () => {
      renderWithRouter(<MobileBottomNav />);

      expect(screen.getByLabelText(/go to dashboard/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/go to timeline/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/go to alerts/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/open more navigation options/i)).toBeInTheDocument();
    });

    it('renders with proper z-index for overlay', () => {
      renderWithRouter(<MobileBottomNav />);

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toHaveClass('z-50');
    });

    it('has background with border styling', () => {
      renderWithRouter(<MobileBottomNav />);

      const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
      expect(nav).toHaveClass('bg-[#1A1A1A]');
      expect(nav).toHaveClass('border-t');
      expect(nav).toHaveClass('border-gray-800');
    });
  });

  describe('More Menu', () => {
    it('opens More menu when button is clicked', async () => {
      const user = userEvent.setup();
      renderWithRouter(<MobileBottomNav />);

      const moreButton = screen.getByTestId('mobile-nav-more-button');
      await user.click(moreButton);

      // Check that the bottom sheet opens with navigation groups
      await waitFor(() => {
        expect(screen.getByTestId('mobile-nav-more-menu')).toBeInTheDocument();
      });
    });

    it('shows navigation groups in More menu', async () => {
      const user = userEvent.setup();
      renderWithRouter(<MobileBottomNav />);

      const moreButton = screen.getByTestId('mobile-nav-more-button');
      await user.click(moreButton);

      await waitFor(() => {
        // Check for navigation groups (Monitoring may not have items if all are in primary)
        // Analytics, Operations, and Admin should have items
        expect(screen.getByTestId('mobile-nav-group-analytics')).toBeInTheDocument();
        expect(screen.getByTestId('mobile-nav-group-operations')).toBeInTheDocument();
        expect(screen.getByTestId('mobile-nav-group-admin')).toBeInTheDocument();
      });
    });

    it('shows Settings in More menu', async () => {
      const user = userEvent.setup();
      renderWithRouter(<MobileBottomNav />);

      const moreButton = screen.getByTestId('mobile-nav-more-button');
      await user.click(moreButton);

      await waitFor(() => {
        expect(screen.getByTestId('mobile-nav-item-settings')).toBeInTheDocument();
      });
    });

    it('shows Entities in More menu (from Monitoring group)', async () => {
      const user = userEvent.setup();
      renderWithRouter(<MobileBottomNav />);

      const moreButton = screen.getByTestId('mobile-nav-more-button');
      await user.click(moreButton);

      await waitFor(() => {
        expect(screen.getByTestId('mobile-nav-item-entities')).toBeInTheDocument();
      });
    });

    it('shows Analytics items in More menu', async () => {
      const user = userEvent.setup();
      renderWithRouter(<MobileBottomNav />);

      const moreButton = screen.getByTestId('mobile-nav-more-button');
      await user.click(moreButton);

      await waitFor(() => {
        expect(screen.getByTestId('mobile-nav-item-analytics')).toBeInTheDocument();
        expect(screen.getByTestId('mobile-nav-item-ai')).toBeInTheDocument();
      });
    });

    it('shows Operations items in More menu', async () => {
      const user = userEvent.setup();
      renderWithRouter(<MobileBottomNav />);

      const moreButton = screen.getByTestId('mobile-nav-more-button');
      await user.click(moreButton);

      await waitFor(() => {
        expect(screen.getByTestId('mobile-nav-item-jobs')).toBeInTheDocument();
        expect(screen.getByTestId('mobile-nav-item-operations')).toBeInTheDocument();
        expect(screen.getByTestId('mobile-nav-item-logs')).toBeInTheDocument();
      });
    });

    it('More menu items have minimum touch target size', async () => {
      const user = userEvent.setup();
      renderWithRouter(<MobileBottomNav />);

      const moreButton = screen.getByTestId('mobile-nav-more-button');
      await user.click(moreButton);

      await waitFor(() => {
        const settingsItem = screen.getByTestId('mobile-nav-item-settings');
        expect(settingsItem).toHaveClass('min-h-[44px]');
      });
    });

    it('More button has correct aria-expanded state', async () => {
      const user = userEvent.setup();
      renderWithRouter(<MobileBottomNav />);

      const moreButton = screen.getByTestId('mobile-nav-more-button');

      // Initially closed
      expect(moreButton).toHaveAttribute('aria-expanded', 'false');

      // After clicking, should be open
      await user.click(moreButton);

      await waitFor(() => {
        expect(moreButton).toHaveAttribute('aria-expanded', 'true');
      });
    });
  });
});
