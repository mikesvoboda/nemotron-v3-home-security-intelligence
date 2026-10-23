import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useCallback, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import ModeSwitch from './ModeSwitch';
import { ADVANCED_HUBS, EASY_HUBS, hubForPath, type Hub } from '../../config/surfaces';
import { useViewMode } from '../../contexts/ViewModeContext';
import { useViewport } from '../../hooks/useIsMobile';
import { useSidebarContext } from '../../hooks/useSidebarContext';
import IconButton from '../common/IconButton';

/** Storage key for sidebar collapsed state */
export const COLLAPSED_STORAGE_KEY = 'sidebar-collapsed-state';

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

interface HubItemProps {
  hub: Hub;
  isActive: boolean;
  onNavClick: () => void;
  isCollapsed: boolean;
}

function HubItem({ hub, isActive, onNavClick, isCollapsed }: HubItemProps) {
  const Icon = hub.icon;
  const targetPath = hub.tabs[0]?.path ?? '/';

  if (isCollapsed) {
    return (
      <Link
        to={targetPath}
        onClick={onNavClick}
        data-tour={hub.dataTour}
        data-testid={`sidebar-hub-${hub.id}`}
        aria-current={isActive ? 'page' : undefined}
        title={hub.label}
        className={`group relative flex h-11 w-11 items-center justify-center rounded-lg transition-colors duration-200 ${
          isActive ? 'bg-[#76B900] text-black' : 'text-gray-300 hover:bg-gray-800 hover:text-white'
        }`}
      >
        <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
        <span className="pointer-events-none absolute left-full z-50 ml-2 whitespace-nowrap rounded-md bg-gray-800 px-2 py-1 text-sm text-white opacity-0 shadow-lg transition-opacity duration-200 group-hover:opacity-100">
          {hub.label}
        </span>
      </Link>
    );
  }

  return (
    <Link
      to={targetPath}
      onClick={onNavClick}
      data-tour={hub.dataTour}
      data-testid={`sidebar-hub-${hub.id}`}
      aria-current={isActive ? 'page' : undefined}
      className={`flex w-full items-center gap-3 rounded-lg px-4 py-2.5 transition-colors duration-200 ${
        isActive
          ? 'bg-[#76B900] font-semibold text-black'
          : 'text-gray-300 hover:bg-gray-800 hover:text-white'
      }`}
    >
      <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
      <span className="flex-1 text-left">{hub.label}</span>
    </Link>
  );
}

export interface SidebarProps {
  /** Force collapsed mode (overrides auto-collapse for tablet) */
  forceCollapsed?: boolean;
}

export default function Sidebar({ forceCollapsed }: SidebarProps = {}) {
  const { isMobileMenuOpen, setMobileMenuOpen } = useSidebarContext();
  const location = useLocation();
  const { isTablet, isDesktop, breakpoint } = useViewport();
  const { mode } = useViewMode();

  const [userCollapsed, setUserCollapsed] = useState<boolean>(() => loadCollapsedState());
  const isCollapsed = forceCollapsed ?? (isTablet || (isDesktop && userCollapsed));
  const [isHovered, setIsHovered] = useState(false);

  const activeHub = hubForPath(location.pathname);

  const handleNavClick = useCallback(() => {
    setMobileMenuOpen(false);
    setIsHovered(false);
  }, [setMobileMenuOpen]);

  const handleToggleCollapsed = useCallback(() => {
    const newCollapsed = !userCollapsed;
    setUserCollapsed(newCollapsed);
    saveCollapsedState(newCollapsed);
  }, [userCollapsed]);

  const showExpanded = !isCollapsed || isHovered;
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
      {/* Mobile close button and mode switch */}
      <div className="flex flex-col gap-3 border-b border-gray-800 px-4 py-4 md:hidden">
        <div className="flex items-center justify-between">
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
        <ModeSwitch className="self-start" />
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
        className={`flex-1 space-y-1 overflow-y-auto focus:outline-none ${showExpanded ? 'p-4' : 'p-2'}`}
        aria-label="Main navigation"
      >
        {EASY_HUBS.map((hub) => (
          <HubItem
            key={hub.id}
            hub={hub}
            isActive={activeHub?.id === hub.id}
            onNavClick={handleNavClick}
            isCollapsed={!showExpanded}
          />
        ))}

        {mode === 'advanced' && (
          <>
            {showExpanded ? (
              <div
                className="my-3 border-t border-gray-800 px-4 pt-3 text-xs font-semibold uppercase tracking-wider text-gray-500"
                data-testid="sidebar-advanced-divider"
              >
                AI Blueprint
              </div>
            ) : (
              <div
                className="my-2 border-t border-gray-800"
                data-testid="sidebar-advanced-divider"
                aria-hidden="true"
              />
            )}
            {ADVANCED_HUBS.map((hub) => (
              <HubItem
                key={hub.id}
                hub={hub}
                isActive={activeHub?.id === hub.id}
                onNavClick={handleNavClick}
                isCollapsed={!showExpanded}
              />
            ))}
          </>
        )}
      </nav>
    </aside>
  );
}
