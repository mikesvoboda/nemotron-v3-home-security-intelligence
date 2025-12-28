import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import Sidebar from './Sidebar';

// Helper to render with router
const renderWithRouter = (initialEntries: string[] = ['/']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Sidebar />
    </MemoryRouter>
  );
};

describe('Sidebar', () => {
  it('renders without crashing', () => {
    renderWithRouter();
    expect(screen.getByRole('complementary')).toBeInTheDocument();
  });

  it('renders all navigation items', () => {
    renderWithRouter();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Timeline')).toBeInTheDocument();
    expect(screen.getByText('Entities')).toBeInTheDocument();
    expect(screen.getByText('Alerts')).toBeInTheDocument();
    expect(screen.getByText('Logs')).toBeInTheDocument();
    expect(screen.getByText('System')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('highlights the active navigation item based on current route', () => {
    renderWithRouter(['/']);
    const dashboardLink = screen.getByRole('link', { name: /dashboard/i });
    expect(dashboardLink).toHaveClass('bg-[#76B900]', 'text-black', 'font-semibold');
  });

  it('does not highlight inactive navigation items', () => {
    renderWithRouter(['/']);
    const timelineLink = screen.getByRole('link', { name: /timeline/i });
    expect(timelineLink).toHaveClass('text-gray-300');
    expect(timelineLink).not.toHaveClass('bg-[#76B900]');
  });

  it('navigation items are links with correct hrefs', () => {
    renderWithRouter();
    expect(screen.getByRole('link', { name: /dashboard/i })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: /timeline/i })).toHaveAttribute('href', '/timeline');
    expect(screen.getByRole('link', { name: /system/i })).toHaveAttribute('href', '/system');
    expect(screen.getByRole('link', { name: /settings/i })).toHaveAttribute('href', '/settings');
  });

  it('displays WIP badge on Entities item', () => {
    renderWithRouter();
    expect(screen.getByText('WIP')).toBeInTheDocument();
  });

  it('WIP badge has correct styling', () => {
    renderWithRouter();
    const wipBadge = screen.getByText('WIP');
    expect(wipBadge).toHaveClass(
      'px-2',
      'py-0.5',
      'text-xs',
      'font-medium',
      'bg-yellow-500',
      'text-black',
      'rounded'
    );
  });

  it('renders icons for all navigation items', () => {
    renderWithRouter();
    const links = screen.getAllByRole('link');

    // Each link should have an icon (lucide-react icons render as SVG)
    links.forEach((link) => {
      const svg = link.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  it('has correct sidebar styling', () => {
    renderWithRouter();
    const sidebar = screen.getByRole('complementary');
    expect(sidebar).toHaveClass('w-64', 'bg-[#1A1A1A]', 'border-r', 'border-gray-800');
  });

  it('navigation links have full width', () => {
    renderWithRouter();
    const links = screen.getAllByRole('link');

    links.forEach((link) => {
      expect(link).toHaveClass('w-full');
    });
  });

  it('highlights different items based on route', () => {
    // Test with timeline route
    renderWithRouter(['/timeline']);

    const dashboardLink = screen.getByRole('link', { name: /dashboard/i });
    const timelineLink = screen.getByRole('link', { name: /timeline/i });

    expect(dashboardLink).not.toHaveClass('bg-[#76B900]');
    expect(timelineLink).toHaveClass('bg-[#76B900]');
  });

  it('highlights settings when on settings route', () => {
    renderWithRouter(['/settings']);

    const settingsLink = screen.getByRole('link', { name: /settings/i });
    expect(settingsLink).toHaveClass('bg-[#76B900]');
  });

  it('renders all 7 navigation items', () => {
    renderWithRouter();
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(7);
  });

  it('navigation items have transition classes for smooth hover', () => {
    renderWithRouter();
    const links = screen.getAllByRole('link');

    links.forEach((link) => {
      expect(link).toHaveClass('transition-colors', 'duration-200');
    });
  });

  it('inactive items have hover classes', () => {
    renderWithRouter(['/']);
    const timelineLink = screen.getByRole('link', { name: /timeline/i });
    expect(timelineLink).toHaveClass('hover:bg-gray-800', 'hover:text-white');
  });
});
