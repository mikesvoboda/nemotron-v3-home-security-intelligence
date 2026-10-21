import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import Sidebar from './Sidebar';
import { navGroups, navItems, STORAGE_KEY } from './sidebarNav';

import type { ViewportInfo } from '../../hooks/useViewport';

// Mock the useSidebarContext hook
const mockSetMobileMenuOpen = vi.fn();
const menuState = vi.hoisted(() => ({ current: false }));

vi.mock('../../hooks/useSidebarContext', () => ({
  useSidebarContext: () => ({
    isMobileMenuOpen: menuState.current,
    setMobileMenuOpen: mockSetMobileMenuOpen,
    toggleMobileMenu: vi.fn(),
  }),
}));

// Mock the useViewport hook. `viewport` is hoisted-mutable rather than a fixed
// literal because the [r130f] F-017 drawer gate reads `breakpoint` (NOT isMobile):
// with a constant 'lg' the inert behaviour is invisible to this tier, and this tier
// is the only one CI runs without a live stack. Tests that care assign it.
const viewportState = vi.hoisted((): { current: ViewportInfo } => ({
  current: {
    isMobile: false,
    isTablet: false,
    isDesktop: true,
    width: 1200,
    breakpoint: 'lg',
  },
}));

vi.mock('../../hooks/useIsMobile', () => ({
  useViewport: () => viewportState.current,
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
    // Both mocked hooks read live objects, so a test that flips them must not
    // leak into the next one.
    menuState.current = false;
    viewportState.current = {
      isMobile: false,
      isTablet: false,
      isDesktop: true,
      width: 1200,
      breakpoint: 'lg',
    };
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
    // Monitoring items - use getAllByText for Dashboard since it appears twice
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Timeline')).toBeInTheDocument();
    expect(screen.getByText('Entities')).toBeInTheDocument();
    expect(screen.getByText('Alerts')).toBeInTheDocument();
    // Analytics items
    expect(screen.getByText('Analytics')).toBeInTheDocument();
    expect(screen.getByText('AI Audit')).toBeInTheDocument();
    expect(screen.getByText('AI Performance')).toBeInTheDocument();
    expect(screen.getByText('Heatmaps')).toBeInTheDocument();
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
    // Use href to distinguish between Dashboard (/) and Operations Dashboard (/operations-dashboard)
    const dashboardLinks = screen.getAllByRole('link', { name: /^dashboard$/i });
    const mainDashboardLink = dashboardLinks.find((link) => link.getAttribute('href') === '/');
    expect(mainDashboardLink).toHaveClass('bg-[#76B900]', 'text-black', 'font-semibold');
  });

  it('does not highlight inactive navigation items', () => {
    renderWithRouter(['/']);
    const timelineLink = screen.getByRole('link', { name: /timeline/i });
    expect(timelineLink).toHaveClass('text-gray-300');
    expect(timelineLink).not.toHaveClass('bg-[#76B900]');
  });

  it('navigation items are links with correct hrefs', () => {
    renderWithRouter();
    // Use getAllByRole since there are multiple "Dashboard" links
    const dashboardLinks = screen.getAllByRole('link', { name: /^dashboard$/i });
    const mainDashboardLink = dashboardLinks.find((link) => link.getAttribute('href') === '/');
    expect(mainDashboardLink).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: /timeline/i })).toHaveAttribute('href', '/timeline');
    // Use exact match for settings since there's also GPU Settings (/settings/gpu)
    expect(screen.getByRole('link', { name: /^settings$/i })).toHaveAttribute('href', '/settings');
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

    // Use getAllByRole since there are multiple "Dashboard" links
    const dashboardLinks = screen.getAllByRole('link', { name: /^dashboard$/i });
    const mainDashboardLink = dashboardLinks.find((link) => link.getAttribute('href') === '/');
    const timelineLink = screen.getByRole('link', { name: /timeline/i });

    expect(mainDashboardLink).not.toHaveClass('bg-[#76B900]');
    expect(timelineLink).toHaveClass('bg-[#76B900]');
  });

  it('highlights settings when on settings route', () => {
    renderWithRouter(['/settings']);

    // Use exact match to avoid conflict with GPU Settings (/settings/gpu)
    const settingsLink = screen.getByRole('link', { name: /^settings$/i });
    expect(settingsLink).toHaveClass('bg-[#76B900]');
  });

  it('renders all navigation items', () => {
    renderWithRouter();
    const links = screen.getAllByRole('link');
    // 4 monitoring + 14 analytics + 8 operations + 7 admin = 33 items
    expect(links).toHaveLength(33);
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
      // Updated to use transition-all for smooth width + transform animations (NEM-3610)
      expect(sidebar).toHaveClass('transform', 'transition-all', 'duration-300');
      expect(sidebar).toHaveClass('md:relative', 'md:translate-x-0');
    });

    it('is hidden by default on mobile (translate-x-full)', () => {
      renderWithRouter();
      const sidebar = screen.getByTestId('sidebar');
      expect(sidebar).toHaveClass('-translate-x-full');
    });

    // [r130f] F-017. The Sidebar is now mounted at every width (Layout's `!isMobile`
    // gate is gone, because that gate unmounted the very drawer the hamburger opens),
    // which leaves a NEW property to own: below `md` the drawer is hidden by a
    // TRANSFORM, and a transform does not remove a subtree from the sequential focus
    // order — measured at 375px, a closed drawer still exposed 34 tabbable links.
    // `inert` is what off-canvas means to a keyboard.
    //
    // Scope of this tier, stated honestly: jsdom parses `inert` but does not ENFORCE
    // it (no focus prevention, no a11y-tree removal), so what these tests can prove
    // is the component's own decision — WHICH states set the attribute. That
    // decision has three branches and the third is the one that would break the app:
    // keying on `isMobile` (< 640) instead of `breakpoint === 'sm'` (< 768) would
    // inert a drawer the user can see and has just opened, in the 640–767 band. What
    // the browser DOES with the attribute is pinned in the golden tier, where a real
    // engine answers `focus()` and Tab.
    describe('drawer inertness (F-017)', () => {
      const setViewport = (over: Partial<typeof viewportState.current>) => {
        viewportState.current = { ...viewportState.current, ...over };
      };

      it('is inert below md while closed', () => {
        setViewport({ breakpoint: 'sm', isMobile: true, isDesktop: false, width: 375 });
        renderWithRouter();
        expect(screen.getByTestId('sidebar')).toHaveAttribute('inert');
      });

      it('is inert in the 640–767 band while closed — the band `isMobile` would miss', () => {
        // THE discriminating width, and the mock must be the combination the hook
        // ACTUALLY produces there or the test proves nothing: getBreakpoint is
        // `>= 768 ? 'md' : 'sm'` (useViewport.ts:57-62), so 700 yields
        // breakpoint 'sm' with isMobile FALSE (`< BREAKPOINTS.sm` = 640, :124) and
        // isTablet TRUE. That is the whole trap: `isMobile` says "not a phone" while
        // Tailwind's `md` (the hamburger's hiding, the drawer's own md:translate-x-0)
        // still says "drawer". Keyed on isMobile, this closed drawer stays tabbable
        // and the golden spec's 700px leg fails; this test is the CI-runs-anyway
        // version of that same trap.
        setViewport({
          breakpoint: 'sm',
          isMobile: false,
          isTablet: true,
          isDesktop: false,
          width: 700,
        });
        renderWithRouter();
        expect(screen.getByTestId('sidebar')).toHaveAttribute('inert');
      });

      it('is NOT inert in that same band once the drawer opens', () => {
        setViewport({
          breakpoint: 'sm',
          isMobile: false,
          isTablet: true,
          isDesktop: false,
          width: 700,
        });
        menuState.current = true;
        renderWithRouter();
        expect(screen.getByTestId('sidebar')).not.toHaveAttribute('inert');
      });

      it('is NOT inert as the desktop rail, even though isMobile is false there too', () => {
        // The other half of the same mistake: the rail must never be inert, or the
        // app has no navigation.
        renderWithRouter();
        expect(screen.getByTestId('sidebar')).not.toHaveAttribute('inert');
      });

      it('becomes interactive the moment the drawer opens', () => {
        setViewport({ breakpoint: 'sm', isMobile: true, isDesktop: false, width: 375 });
        menuState.current = true;
        renderWithRouter();
        expect(screen.getByTestId('sidebar')).not.toHaveAttribute('inert');
      });
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
      // 4 monitoring + 14 analytics + 8 operations + 7 admin = 33 items
      expect(navItems).toHaveLength(33);
      expect(navItems.some((item) => item.id === 'dashboard')).toBe(true);
      expect(navItems.some((item) => item.id === 'settings')).toBe(true);
      expect(navItems.some((item) => item.id === 'data')).toBe(true);
      expect(navItems.some((item) => item.id === 'gpu-settings')).toBe(true);
      expect(navItems.some((item) => item.id === 'scene-changes')).toBe(true);
    });

    it('exports STORAGE_KEY constant', () => {
      expect(STORAGE_KEY).toBe('sidebar-expansion-state');
    });
  });
});
