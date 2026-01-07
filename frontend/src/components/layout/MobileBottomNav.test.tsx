import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';

import MobileBottomNav from './MobileBottomNav';

// Mock useIsMobile hook
vi.mock('../../hooks/useIsMobile', () => ({
  useIsMobile: () => true,
}));

describe('MobileBottomNav', () => {
  const renderWithRouter = (ui: React.ReactElement) => {
    return render(<BrowserRouter>{ui}</BrowserRouter>);
  };

  it('renders navigation bar with all icons', () => {
    renderWithRouter(<MobileBottomNav />);

    // Check for navigation container
    const nav = screen.getByRole('navigation', { name: /mobile navigation/i });
    expect(nav).toBeInTheDocument();

    // Check for all navigation links
    expect(screen.getByLabelText(/go to dashboard/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/go to timeline/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/go to alerts/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/go to settings/i)).toBeInTheDocument();
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
    expect(screen.getByLabelText(/go to settings/i)).toBeInTheDocument();
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
