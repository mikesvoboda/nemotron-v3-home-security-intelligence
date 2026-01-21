import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import Sidebar from './Sidebar';
import { navGroups, navItems, STORAGE_KEY } from './sidebarNav';

// Mock the useSidebarContext hook
const mockSetMobileMenuOpen = vi.fn();

vi.mock('../../hooks/useSidebarContext', () => ({
  useSidebarContext: () => ({
    isMobileMenuOpen: false,
    setMobileMenuOpen: mockSetMobileMenuOpen,
    toggleMobileMenu: vi.fn(),
  }),
}));

// Helper to render with router
const renderWithRouter = (initialEntries: string[] = ['/']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Sidebar />
    </MemoryRouter>
  );
};

describe('Sidebar', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    mockSetMobileMenuOpen.mockClear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders without crashing', () => {
    renderWithRouter();
    expect(screen.getByRole('complementary')).toBeInTheDocument();
  });

  it('renders all navigation groups', () => {
    renderWithRouter();
    expect(screen.getByTestId('nav-group-monitoring')).toBeInTheDocument();
    expect(screen.getByTestId('nav-group-analytics')).toBeInTheDocument();
    expect(screen.getByTestId('nav-group-operations')).toBeInTheDocument();
    expect(screen.getByTestId('nav-group-admin')).toBeInTheDocument();
  });

  it('renders group headers with correct labels', () => {
    renderWithRouter();
    expect(screen.getByText('MONITORING')).toBeInTheDocument();
    expect(screen.getByText('ANALYTICS')).toBeInTheDocument();
    expect(screen.getByText('OPERATIONS')).toBeInTheDocument();
    expect(screen.getByText('ADMIN')).toBeInTheDocument();
  });

  it('renders all navigation items within groups', () => {
    renderWithRouter();
    // Monitoring items
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Timeline')).toBeInTheDocument();
    expect(screen.getByText('Entities')).toBeInTheDocument();
    expect(screen.getByText('Alerts')).toBeInTheDocument();
    // Analytics items
    expect(screen.getByText('Analytics')).toBeInTheDocument();
    expect(screen.getByText('AI Audit')).toBeInTheDocument();
    expect(screen.getByText('AI Performance')).toBeInTheDocument();
    // Operations items (renamed)
    expect(screen.getByText('Jobs')).toBeInTheDocument();
    expect(screen.getByText('Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Logs')).toBeInTheDocument();
    // Admin items
    expect(screen.getByText('Audit Log')).toBeInTheDocument();
    expect(screen.getByText('Trash')).toBeInTheDocument();
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
    expect(screen.getByRole('link', { name: /settings/i })).toHaveAttribute('href', '/settings');
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
    expect(sidebar).toHaveClass('w-64', 'bg-[#1A1A1A]', 'border-r', 'border-gray-800', 'fixed');
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

  it('renders all 15 navigation items', () => {
    renderWithRouter();
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(16);
  });

  it('jobs link has correct href', () => {
    renderWithRouter();
    expect(screen.getByRole('link', { name: /jobs/i })).toHaveAttribute('href', '/jobs');
  });

  it('audit log link has correct href', () => {
    renderWithRouter();
    expect(screen.getByRole('link', { name: /audit log/i })).toHaveAttribute('href', '/audit');
  });

  it('AI audit link has correct href', () => {
    renderWithRouter();
    expect(screen.getByRole('link', { name: /AI Audit/i })).toHaveAttribute('href', '/ai-audit');
  });

  it('data management link has correct href', () => {
    renderWithRouter();
    expect(screen.getByRole('link', { name: /Data Management/i })).toHaveAttribute('href', '/data');
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

  describe('mobile responsiveness', () => {
    it('has data-testid for sidebar', () => {
      renderWithRouter();
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    });

    it('has close menu button for mobile', () => {
      renderWithRouter();
      expect(screen.getByTestId('close-menu-button')).toBeInTheDocument();
      expect(screen.getByLabelText('Close menu')).toBeInTheDocument();
    });

    it('calls setMobileMenuOpen when close button is clicked', () => {
      renderWithRouter();
      const closeButton = screen.getByTestId('close-menu-button');
      fireEvent.click(closeButton);
      expect(mockSetMobileMenuOpen).toHaveBeenCalledWith(false);
    });

    it('closes menu when nav link is clicked', () => {
      renderWithRouter();
      const timelineLink = screen.getByRole('link', { name: /timeline/i });
      fireEvent.click(timelineLink);
      expect(mockSetMobileMenuOpen).toHaveBeenCalledWith(false);
    });

    it('has responsive transform classes', () => {
      renderWithRouter();
      const sidebar = screen.getByTestId('sidebar');
      expect(sidebar).toHaveClass('transform', 'transition-transform', 'duration-300');
      expect(sidebar).toHaveClass('md:relative', 'md:translate-x-0');
    });

    it('is hidden by default on mobile (translate-x-full)', () => {
      renderWithRouter();
      const sidebar = screen.getByTestId('sidebar');
      expect(sidebar).toHaveClass('-translate-x-full');
    });
  });

  describe('collapsible groups', () => {
    it('monitoring and analytics groups are expanded by default', () => {
      renderWithRouter();
      const monitoringHeader = screen.getByTestId('nav-group-header-monitoring');
      const analyticsHeader = screen.getByTestId('nav-group-header-analytics');

      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'true');
      expect(analyticsHeader).toHaveAttribute('aria-expanded', 'true');
    });

    it('operations and admin groups are collapsed by default', () => {
      renderWithRouter();
      const operationsHeader = screen.getByTestId('nav-group-header-operations');
      const adminHeader = screen.getByTestId('nav-group-header-admin');

      expect(operationsHeader).toHaveAttribute('aria-expanded', 'false');
      expect(adminHeader).toHaveAttribute('aria-expanded', 'false');
    });

    it('clicking group header toggles expansion', () => {
      renderWithRouter();
      const monitoringHeader = screen.getByTestId('nav-group-header-monitoring');

      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'true');

      fireEvent.click(monitoringHeader);
      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(monitoringHeader);
      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'true');
    });

    it('group content has proper aria attributes', () => {
      renderWithRouter();
      const monitoringContent = screen.getByTestId('nav-group-content-monitoring');

      expect(monitoringContent).toHaveAttribute('role', 'region');
      expect(monitoringContent).toHaveAttribute('id', 'nav-group-content-monitoring');
    });

    it('group header controls the content region', () => {
      renderWithRouter();
      const monitoringHeader = screen.getByTestId('nav-group-header-monitoring');

      expect(monitoringHeader).toHaveAttribute('aria-controls', 'nav-group-content-monitoring');
    });
  });

  describe('localStorage persistence', () => {
    it('saves expansion state to localStorage when toggling', () => {
      renderWithRouter();
      const monitoringHeader = screen.getByTestId('nav-group-header-monitoring');

      fireEvent.click(monitoringHeader);

      const stored = localStorage.getItem(STORAGE_KEY);
      expect(stored).toBeTruthy();
      const parsed = JSON.parse(stored!);
      expect(parsed.monitoring).toBe(false);
    });

    it('loads expansion state from localStorage on mount', () => {
      // Pre-set localStorage
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ monitoring: false, analytics: false, operations: true, admin: true })
      );

      // Use a route that doesn't trigger auto-expand for the test groups
      // Note: monitoring will still expand because '/' triggers auto-expand for dashboard
      renderWithRouter(['/ai-audit']);

      const monitoringHeader = screen.getByTestId('nav-group-header-monitoring');
      const analyticsHeader = screen.getByTestId('nav-group-header-analytics');
      const operationsHeader = screen.getByTestId('nav-group-header-operations');
      const adminHeader = screen.getByTestId('nav-group-header-admin');

      // Monitoring stays collapsed because ai-audit is not in monitoring group
      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'false');
      // Analytics auto-expands because ai-audit is in the analytics group
      expect(analyticsHeader).toHaveAttribute('aria-expanded', 'true');
      // Operations and admin load from localStorage
      expect(operationsHeader).toHaveAttribute('aria-expanded', 'true');
      expect(adminHeader).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('auto-expand on route', () => {
    it('expands admin group when navigating to settings', () => {
      // Admin group is collapsed by default
      renderWithRouter(['/settings']);

      const adminHeader = screen.getByTestId('nav-group-header-admin');
      expect(adminHeader).toHaveAttribute('aria-expanded', 'true');
    });

    it('expands operations group when navigating to jobs', () => {
      renderWithRouter(['/jobs']);

      const operationsHeader = screen.getByTestId('nav-group-header-operations');
      expect(operationsHeader).toHaveAttribute('aria-expanded', 'true');
    });

    it('expands operations group when navigating to logs', () => {
      renderWithRouter(['/logs']);

      const operationsHeader = screen.getByTestId('nav-group-header-operations');
      expect(operationsHeader).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('keyboard navigation', () => {
    it('toggles group on Enter key', () => {
      renderWithRouter();
      const monitoringHeader = screen.getByTestId('nav-group-header-monitoring');

      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'true');

      fireEvent.keyDown(monitoringHeader, { key: 'Enter' });
      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'false');
    });

    it('toggles group on Space key', () => {
      renderWithRouter();
      const monitoringHeader = screen.getByTestId('nav-group-header-monitoring');

      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'true');

      fireEvent.keyDown(monitoringHeader, { key: ' ' });
      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'false');
    });

    it('does not toggle on other keys', () => {
      renderWithRouter();
      const monitoringHeader = screen.getByTestId('nav-group-header-monitoring');

      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'true');

      fireEvent.keyDown(monitoringHeader, { key: 'Tab' });
      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'true');

      fireEvent.keyDown(monitoringHeader, { key: 'a' });
      expect(monitoringHeader).toHaveAttribute('aria-expanded', 'true');
    });

    it('group headers are focusable buttons', () => {
      renderWithRouter();
      const monitoringHeader = screen.getByTestId('nav-group-header-monitoring');

      expect(monitoringHeader.tagName).toBe('BUTTON');
      expect(monitoringHeader).toHaveAttribute('type', 'button');
    });
  });

  describe('exported values', () => {
    it('exports navGroups with correct structure', () => {
      expect(navGroups).toHaveLength(4);
      expect(navGroups[0].id).toBe('monitoring');
      expect(navGroups[1].id).toBe('analytics');
      expect(navGroups[2].id).toBe('operations');
      expect(navGroups[3].id).toBe('admin');
    });

    it('exports navItems as flattened list of all items', () => {
      expect(navItems).toHaveLength(16);
      expect(navItems.some((item) => item.id === 'dashboard')).toBe(true);
      expect(navItems.some((item) => item.id === 'settings')).toBe(true);
      expect(navItems.some((item) => item.id === 'data')).toBe(true);
    });

    it('exports STORAGE_KEY constant', () => {
      expect(STORAGE_KEY).toBe('sidebar-expansion-state');
    });
  });
});
