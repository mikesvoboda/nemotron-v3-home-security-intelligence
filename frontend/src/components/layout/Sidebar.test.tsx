import { screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import Sidebar, { COLLAPSED_STORAGE_KEY } from './Sidebar';
import { ADVANCED_HUBS, EASY_HUBS, HUBS, type ViewMode } from '../../config/surfaces';
import { createNavigationFixture, renderWithNavigation } from '../../test-utils';

import type { ViewportInfo } from '../../hooks/useViewport';

const mockSetMobileMenuOpen = vi.fn();
const menuState = vi.hoisted(() => ({ current: false }));

vi.mock('../../hooks/useSidebarContext', () => ({
  useSidebarContext: () => ({
    isMobileMenuOpen: menuState.current,
    setMobileMenuOpen: mockSetMobileMenuOpen,
    toggleMobileMenu: vi.fn(),
  }),
}));

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

const renderWithRouter = (initialEntries: string[] = ['/'], mode: ViewMode = 'easy') => {
  return renderWithNavigation(<Sidebar />, {
    initialEntries,
    mode,
    withSidebarContext: false,
  });
};

describe('Sidebar', () => {
  beforeEach(() => {
    localStorage.clear();
    mockSetMobileMenuOpen.mockClear();
    menuState.current = false;
    viewportState.current = createNavigationFixture().desktopViewport;
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders without crashing', () => {
    renderWithRouter();
    expect(screen.getByRole('complementary')).toBeInTheDocument();
  });

  it('renders the five Easy hubs in Easy mode and hides the AI Blueprint hubs', () => {
    renderWithRouter(['/'], 'easy');
    for (const hub of EASY_HUBS) {
      expect(screen.getByTestId(`sidebar-hub-${hub.id}`)).toBeInTheDocument();
      expect(screen.getByText(hub.label)).toBeInTheDocument();
    }
    expect(screen.queryByTestId('sidebar-advanced-divider')).not.toBeInTheDocument();
    for (const hub of ADVANCED_HUBS) {
      expect(screen.queryByTestId(`sidebar-hub-${hub.id}`)).not.toBeInTheDocument();
    }
  });

  it('renders all nine hubs and the AI Blueprint divider in Advanced mode', () => {
    renderWithRouter(['/'], 'advanced');
    expect(screen.getByTestId('sidebar-advanced-divider')).toHaveTextContent('AI Blueprint');
    for (const hub of HUBS) {
      expect(screen.getByTestId(`sidebar-hub-${hub.id}`)).toBeInTheDocument();
      expect(screen.getByText(hub.label)).toBeInTheDocument();
    }
  });

  it('highlights the active hub based on current route', () => {
    renderWithRouter(['/timeline'], 'easy');
    const timelineHub = screen.getByTestId('sidebar-hub-timeline-search');
    expect(timelineHub).toHaveClass('bg-[#76B900]');
    expect(timelineHub).toHaveAttribute('aria-current', 'page');

    const dashboardHub = screen.getByTestId('sidebar-hub-dashboard');
    expect(dashboardHub).not.toHaveClass('bg-[#76B900]');
    expect(dashboardHub).not.toHaveAttribute('aria-current');
  });

  it('highlights the owning hub for secondary tabs (e.g. /settings/rules -> Alerts & Rules)', () => {
    renderWithRouter(['/settings/rules'], 'easy');
    expect(screen.getByTestId('sidebar-hub-alerts-rules')).toHaveClass('bg-[#76B900]');
    expect(screen.getByTestId('sidebar-hub-settings')).not.toHaveClass('bg-[#76B900]');
  });

  it('highlights no sidebar item when viewing an Advanced URL in Easy mode', () => {
    renderWithRouter(['/operations'], 'easy');
    for (const hub of EASY_HUBS) {
      expect(screen.getByTestId(`sidebar-hub-${hub.id}`)).not.toHaveClass('bg-[#76B900]');
      expect(screen.getByTestId(`sidebar-hub-${hub.id}`)).not.toHaveAttribute('aria-current');
    }
  });

  it('renders tour targets on Timeline & Search and Settings hubs', () => {
    renderWithRouter(['/'], 'easy');
    expect(screen.getByTestId('sidebar-hub-timeline-search')).toHaveAttribute(
      'data-tour',
      'timeline-link'
    );
    expect(screen.getByTestId('sidebar-hub-settings')).toHaveAttribute(
      'data-tour',
      'settings-link'
    );
  });

  it('links each hub to its primary tab path', () => {
    renderWithRouter(['/'], 'advanced');
    expect(screen.getByTestId('sidebar-hub-dashboard')).toHaveAttribute('href', '/');
    expect(screen.getByTestId('sidebar-hub-timeline-search')).toHaveAttribute('href', '/timeline');
    expect(screen.getByTestId('sidebar-hub-alerts-rules')).toHaveAttribute('href', '/alerts');
    expect(screen.getByTestId('sidebar-hub-household')).toHaveAttribute('href', '/household');
    expect(screen.getByTestId('sidebar-hub-settings')).toHaveAttribute('href', '/settings/cameras');
    expect(screen.getByTestId('sidebar-hub-ai-workbench')).toHaveAttribute('href', '/ai-audit');
    expect(screen.getByTestId('sidebar-hub-gpu-models')).toHaveAttribute('href', '/ai');
    expect(screen.getByTestId('sidebar-hub-entities-reid')).toHaveAttribute('href', '/entities');
    expect(screen.getByTestId('sidebar-hub-operations-monitoring')).toHaveAttribute(
      'href',
      '/operations'
    );
  });

  describe('mobile responsiveness', () => {
    it('has data-testid for sidebar and close menu button with ModeSwitch', () => {
      renderWithRouter();
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
      expect(screen.getByTestId('close-menu-button')).toBeInTheDocument();
      expect(screen.getByTestId('mode-switch')).toBeInTheDocument();
    });

    it('calls setMobileMenuOpen when close button or hub link is clicked', () => {
      renderWithRouter();
      fireEvent.click(screen.getByTestId('close-menu-button'));
      expect(mockSetMobileMenuOpen).toHaveBeenCalledWith(false);

      mockSetMobileMenuOpen.mockClear();
      fireEvent.click(screen.getByTestId('sidebar-hub-timeline-search'));
      expect(mockSetMobileMenuOpen).toHaveBeenCalledWith(false);
    });

    it('is hidden by default on mobile (-translate-x-full)', () => {
      renderWithRouter();
      const sidebar = screen.getByTestId('sidebar');
      expect(sidebar).toHaveClass('-translate-x-full');
      expect(sidebar).toHaveClass('md:translate-x-0');
    });

    describe('drawer inertness (F-017)', () => {
      it('is inert below md while closed', () => {
        viewportState.current = {
          isMobile: true,
          isTablet: false,
          isDesktop: false,
          width: 375,
          breakpoint: 'sm',
        };
        menuState.current = false;
        renderWithRouter();
        expect(screen.getByTestId('sidebar')).toHaveAttribute('inert');
      });

      it('is inert in the 640–767 band while closed — the band `isMobile` would miss', () => {
        viewportState.current = {
          isMobile: false,
          isTablet: false,
          isDesktop: false,
          width: 700,
          breakpoint: 'sm',
        };
        menuState.current = false;
        renderWithRouter();
        expect(screen.getByTestId('sidebar')).toHaveAttribute('inert');
      });

      it('is NOT inert in that same band once the drawer opens', () => {
        viewportState.current = {
          isMobile: false,
          isTablet: false,
          isDesktop: false,
          width: 700,
          breakpoint: 'sm',
        };
        menuState.current = true;
        renderWithRouter();
        expect(screen.getByTestId('sidebar')).not.toHaveAttribute('inert');
      });

      it('is NOT inert as the desktop rail', () => {
        renderWithRouter();
        expect(screen.getByTestId('sidebar')).not.toHaveAttribute('inert');
      });

      it('becomes interactive the moment the drawer opens', () => {
        viewportState.current = {
          isMobile: true,
          isTablet: false,
          isDesktop: false,
          width: 375,
          breakpoint: 'sm',
        };
        menuState.current = false;
        const { rerender } = renderWithRouter();
        expect(screen.getByTestId('sidebar')).toHaveAttribute('inert');

        menuState.current = true;
        rerender(<Sidebar />);
        expect(screen.getByTestId('sidebar')).not.toHaveAttribute('inert');
      });
    });
  });

  describe('collapsed state persistence', () => {
    it('toggles collapsed state and persists to localStorage', () => {
      renderWithRouter();
      const sidebar = screen.getByTestId('sidebar');
      expect(sidebar).toHaveAttribute('data-collapsed', 'false');

      fireEvent.click(screen.getByTestId('collapse-sidebar-button'));
      expect(sidebar).toHaveAttribute('data-collapsed', 'true');
      expect(localStorage.getItem(COLLAPSED_STORAGE_KEY)).toBe('true');
    });

    it('restores collapsed state from localStorage on mount and expands on hover', () => {
      localStorage.setItem(COLLAPSED_STORAGE_KEY, 'true');
      renderWithRouter();
      const sidebar = screen.getByTestId('sidebar');
      expect(sidebar).toHaveAttribute('data-collapsed', 'true');
      expect(sidebar).toHaveClass('w-16');

      fireEvent.mouseEnter(sidebar);
      expect(sidebar).toHaveAttribute('data-collapsed', 'false');
      expect(sidebar).toHaveClass('w-64');

      fireEvent.mouseLeave(sidebar);
      expect(sidebar).toHaveAttribute('data-collapsed', 'true');
      expect(sidebar).toHaveClass('w-16');
    });
  });
});
