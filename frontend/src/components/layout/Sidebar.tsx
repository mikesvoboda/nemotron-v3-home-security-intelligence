import { ChevronDown, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

import { NavGroup, navGroups, STORAGE_KEY } from './sidebarNav';
import { useViewport } from '../../hooks/useIsMobile';
import { useSidebarContext } from '../../hooks/useSidebarContext';
import IconButton from '../common/IconButton';

/** Storage key for sidebar collapsed state */
const COLLAPSED_STORAGE_KEY = 'sidebar-collapsed-state';

/** Helper to load expansion state from localStorage */
function loadExpansionState(): Record<string, boolean> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return JSON.parse(stored) as Record<string, boolean>;
    }
  } catch {
    // Ignore parse errors
  }
  return {};
}

/** Helper to save expansion state to localStorage */
function saveExpansionState(state: Record<string, boolean>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage errors
  }
}

interface NavGroupComponentProps {
  group: NavGroup;
  isExpanded: boolean;
  onToggle: () => void;
  onNavClick: () => void;
  /** Whether sidebar is in collapsed (icon-only) mode */
  isCollapsed?: boolean;
}

function NavGroupComponent({
  group,
  isExpanded,
  onToggle,
  onNavClick,
  isCollapsed = false,
}: NavGroupComponentProps) {
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onToggle();
      }
    },
    [onToggle]
  );

  // In collapsed mode, show only icons without group headers
  if (isCollapsed) {
    return (
      <div className="mb-2 space-y-1" data-testid={`nav-group-${group.id}`}>
        {group.items.map((item) => {
          const Icon = item.icon;

          return (
            <NavLink
              key={item.id}
              to={item.path}
              end={item.path === '/'}
              onClick={onNavClick}
              data-tour={item.dataTour}
              title={item.label}
              className={({ isActive }: { isActive: boolean }) =>
                `group relative flex h-11 w-11 items-center justify-center rounded-lg transition-colors duration-200 ${
                  isActive
                    ? 'bg-[#76B900] text-black'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
              {/* Tooltip on hover */}
              <span className="pointer-events-none absolute left-full z-50 ml-2 whitespace-nowrap rounded-md bg-gray-800 px-2 py-1 text-sm text-white opacity-0 shadow-lg transition-opacity duration-200 group-hover:opacity-100">
                {item.label}
              </span>
              {item.badge && (
                <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-yellow-500 text-[10px] font-bold text-black">
                  !
                </span>
              )}
            </NavLink>
          );
        })}
      </div>
    );
  }

  return (
    <div className="mb-2" data-testid={`nav-group-${group.id}`}>
      {/* Group header */}
      <button
        type="button"
        onClick={onToggle}
        onKeyDown={handleKeyDown}
        className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wider text-gray-400 transition-colors duration-200 hover:bg-gray-800 hover:text-gray-300"
        aria-expanded={isExpanded}
        aria-controls={`nav-group-content-${group.id}`}
        data-testid={`nav-group-header-${group.id}`}
      >
        <span>{group.label}</span>
        <ChevronDown
          className={`h-4 w-4 transition-transform duration-200 ${isExpanded ? 'rotate-0' : '-rotate-90'}`}
          aria-hidden="true"
        />
      </button>

      {/* Group items with animation */}
      <div
        id={`nav-group-content-${group.id}`}
        role="region"
        aria-labelledby={`nav-group-header-${group.id}`}
        className={`overflow-hidden transition-all duration-200 ease-in-out ${
          isExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
        }`}
        data-testid={`nav-group-content-${group.id}`}
      >
        <div className="mt-1 space-y-1 pl-2">
          {group.items.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.id}
                to={item.path}
                end={item.path === '/'}
                onClick={onNavClick}
                data-tour={item.dataTour}
                className={({ isActive }: { isActive: boolean }) =>
                  `flex w-full items-center gap-3 rounded-lg px-4 py-2.5 transition-colors duration-200 ${
                    isActive
                      ? 'bg-[#76B900] font-semibold text-black'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  } `
                }
              >
                <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
                <span className="flex-1 text-left">{item.label}</span>
                {item.badge && (
                  <span className="rounded bg-yellow-500 px-2 py-0.5 text-xs font-medium text-black">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** Load collapsed state from localStorage */
function loadCollapsedState(): boolean {
  try {
    const stored = localStorage.getItem(COLLAPSED_STORAGE_KEY);
    if (stored !== null) {
      return JSON.parse(stored) as boolean;
    }
  } catch {
    // Ignore parse errors
  }
  return false;
}

/** Save collapsed state to localStorage */
function saveCollapsedState(collapsed: boolean): void {
  try {
    localStorage.setItem(COLLAPSED_STORAGE_KEY, JSON.stringify(collapsed));
  } catch {
    // Ignore storage errors
  }
}

export interface SidebarProps {
  /** Force collapsed mode (overrides auto-collapse for tablet) */
  forceCollapsed?: boolean;
}

export default function Sidebar({ forceCollapsed }: SidebarProps = {}) {
  const { isMobileMenuOpen, setMobileMenuOpen } = useSidebarContext();
  const location = useLocation();
  const { isTablet, isDesktop, breakpoint } = useViewport();

  // Initialize collapsed state from localStorage (only for desktop)
  // Tablets automatically use collapsed mode
  const [userCollapsed, setUserCollapsed] = useState<boolean>(() => loadCollapsedState());

  // Determine if sidebar should be collapsed:
  // - On tablet: always collapsed (unless expanded via hover)
  // - On desktop: based on user preference
  const isCollapsed = forceCollapsed ?? (isTablet || (isDesktop && userCollapsed));

  // State for hover expansion on collapsed sidebar
  const [isHovered, setIsHovered] = useState(false);

  // Initialize expansion state from localStorage or defaults
  const [expansionState, setExpansionState] = useState<Record<string, boolean>>(() => {
    const stored = loadExpansionState();
    const initial: Record<string, boolean> = {};
    navGroups.forEach((group) => {
      initial[group.id] = stored[group.id] ?? group.defaultExpanded;
    });
    return initial;
  });

  // Auto-expand group when navigating to a route within it
  useEffect(() => {
    const currentPath = location.pathname;
    navGroups.forEach((group) => {
      const hasActiveRoute = group.items.some((item) => {
        if (item.path === '/') {
          return currentPath === '/';
        }
        return currentPath === item.path || currentPath.startsWith(item.path + '/');
      });
      if (hasActiveRoute && !expansionState[group.id]) {
        setExpansionState((prev) => {
          const next = { ...prev, [group.id]: true };
          saveExpansionState(next);
          return next;
        });
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Intentionally exclude expansionState to avoid infinite loops
  }, [location.pathname]);

  const handleToggleGroup = useCallback((groupId: string) => {
    setExpansionState((prev) => {
      const next = { ...prev, [groupId]: !prev[groupId] };
      saveExpansionState(next);
      return next;
    });
  }, []);

  const handleNavClick = useCallback(() => {
    // Close mobile menu when a link is clicked
    setMobileMenuOpen(false);
    // Also collapse hover expansion
    setIsHovered(false);
  }, [setMobileMenuOpen]);

  const handleToggleCollapsed = useCallback(() => {
    const newCollapsed = !userCollapsed;
    setUserCollapsed(newCollapsed);
    saveCollapsedState(newCollapsed);
  }, [userCollapsed]);

  // Determine display state: fully collapsed or expanded
  const showExpanded = !isCollapsed || isHovered;

  // [r130f] F-017: below Tailwind `md` this aside is a DRAWER, not a rail:
  // `-translate-x-full` parks it off-canvas until `isMobileMenuOpen`. Translation
  // moves it visually but NOT out of the sequential focus order, so now that the
  // component mounts at every width (Layout.tsx) a closed drawer at 375px still
  // exposed 34 tabbable links and a "Close menu" button by Tab stop #5.
  //
  // `inert` is what off-canvas means to a keyboard. Measured here at 375px, not
  // assumed: with the attribute absent, `link.focus()` lands and Tab reaches
  // `close-menu-button`; with it present, `link.focus()` is a no-op
  // (activeElement stays put) and the 10-stop Tab walk has no `SIDEBAR:` entry at
  // all, while the same probe after opening the drawer reads focusable again.
  // The ATTRIBUTED-STATE check is `hasAttribute('inert')`, and React renders
  // `inert={true}` as the empty string — so `getAttribute` would compare against
  // '' and a flip to `inert=""`-vs-`inert="true"` would look like a change.
  //
  // What is NOT claimed: Chromium's ariaSnapshot still enumerates the whole
  // subtree in both states (80 lines closed, 80 open), so this comment does not
  // assert a11y-tree removal on this evidence — only focusability.
  //
  // The width test is `breakpoint === 'sm'`, which is `width < BREAKPOINTS.md`
  // (useViewport.ts:62 — the returned 'sm' bucket, not `isMobile`, which is
  // `< BREAKPOINTS.sm` = 640, useViewport.ts:124). That is deliberately the SAME
  // 768 the hamburger's `md:hidden` and the drawer's own `md:translate-x-0` use,
  // because the condition must match when the aside is a drawer, not when the app
  // calls the viewport "mobile": at 700px the hamburger shows, the drawer opens,
  // and it must be interactive. Keying on `isMobile` would have inerted a drawer
  // the user could see and had just asked for, between 640 and 768.
  const drawerIsOffCanvas = breakpoint === 'sm' && !isMobileMenuOpen;

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex transform flex-col border-r border-gray-800 bg-[#1A1A1A] transition-all duration-300 ease-in-out md:relative md:translate-x-0 ${
        isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
      } ${showExpanded ? 'w-64' : 'w-16'}`}
      data-testid="sidebar"
      data-collapsed={isCollapsed && !isHovered}
      inert={drawerIsOffCanvas}
      onMouseEnter={() => isCollapsed && setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Mobile close button */}
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-4 md:hidden">
        <span className="text-lg font-semibold text-white">Menu</span>
        <IconButton
          icon={<X />}
          aria-label="Close menu"
          onClick={() => setMobileMenuOpen(false)}
          variant="ghost"
          size="md"
          data-testid="close-menu-button"
        />
      </div>

      {/* Desktop collapse toggle */}
      {isDesktop && (
        <div className="hidden border-b border-gray-800 md:flex md:items-center md:justify-end md:px-2 md:py-2">
          <IconButton
            icon={showExpanded ? <ChevronLeft /> : <ChevronRight />}
            aria-label={showExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
            onClick={handleToggleCollapsed}
            variant="ghost"
            size="sm"
            data-testid="collapse-sidebar-button"
          />
        </div>
      )}

      {/* Navigation */}
      <nav
        id="main-navigation"
        tabIndex={-1}
        className={`flex-1 overflow-y-auto focus:outline-none ${showExpanded ? 'p-4' : 'p-2'}`}
        aria-label="Main navigation"
      >
        {navGroups.map((group) => (
          <NavGroupComponent
            key={group.id}
            group={group}
            isExpanded={expansionState[group.id]}
            onToggle={() => handleToggleGroup(group.id)}
            onNavClick={handleNavClick}
            isCollapsed={!showExpanded}
          />
        ))}
      </nav>
    </aside>
  );
}
