/**
 * MobileBottomNav - Fixed bottom navigation for mobile devices
 *
 * Displays primary navigation icons at bottom of screen for mobile viewports.
 * Includes safe area inset padding for iOS notch/home indicator support.
 * Features a "More" menu to access additional navigation routes not shown
 * in the primary bottom bar.
 */

import { clsx } from 'clsx';
import { Home, Clock, Bell, MoreHorizontal, ChevronRight } from 'lucide-react';
import { useCallback, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';

import { navGroups } from './sidebarNav';
import BottomSheet from '../common/BottomSheet';

export interface MobileBottomNavProps {
  /** Number of unread notifications to display as badge (optional) */
  notificationCount?: number;
}

interface PrimaryNavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  path: string;
  showBadge?: boolean;
}

/** Primary nav items shown directly in the bottom bar */
const primaryNavItems: PrimaryNavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: Home, path: '/' },
  { id: 'timeline', label: 'Timeline', icon: Clock, path: '/timeline' },
  { id: 'alerts', label: 'Alerts', icon: Bell, path: '/alerts', showBadge: true },
];

/** IDs of items shown in the primary nav - used to filter out from "More" menu */
const primaryNavIds = new Set(primaryNavItems.map((item) => item.id));

export default function MobileBottomNav({ notificationCount = 0 }: MobileBottomNavProps) {
  const [isMoreMenuOpen, setIsMoreMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const formatBadgeCount = (count: number): string => {
    return count > 9 ? '9+' : count.toString();
  };

  const handleOpenMoreMenu = useCallback(() => {
    setIsMoreMenuOpen(true);
  }, []);

  const handleCloseMoreMenu = useCallback(() => {
    setIsMoreMenuOpen(false);
  }, []);

  const handleNavigate = useCallback(
    (path: string) => {
      void navigate(path);
      setIsMoreMenuOpen(false);
    },
    [navigate]
  );

  /** Check if a path is currently active */
  const isPathActive = useCallback(
    (path: string) => {
      if (path === '/') {
        return location.pathname === '/';
      }
      return location.pathname === path || location.pathname.startsWith(path + '/');
    },
    [location.pathname]
  );

  /** Check if any route in the "More" menu is currently active */
  const isMoreMenuActive = navGroups.some((group) =>
    group.items.some((item) => !primaryNavIds.has(item.id) && isPathActive(item.path))
  );

  return (
    <>
      <nav
        className="fixed bottom-0 left-0 right-0 z-50 h-14 border-t border-gray-800 bg-[#1A1A1A] pb-safe"
        role="navigation"
        aria-label="Mobile navigation"
      >
        <div className="flex h-full items-center justify-around">
          {/* Primary navigation items */}
          {primaryNavItems.map((item) => {
            const Icon = item.icon;
            const showBadge = item.showBadge && notificationCount > 0;

            return (
              <NavLink
                key={item.id}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `relative flex h-11 min-h-[44px] w-11 min-w-[44px] items-center justify-center rounded-lg transition-colors ${
                    isActive ? 'text-[#76B900]' : 'text-gray-400 hover:text-white'
                  }`
                }
                aria-label={`Go to ${item.label}`}
              >
                <Icon className="h-6 w-6" />
                {showBadge && (
                  <span
                    className="absolute right-0 top-0 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1.5 text-xs font-bold text-white"
                    aria-label={`${notificationCount} unread notifications`}
                  >
                    {formatBadgeCount(notificationCount)}
                  </span>
                )}
              </NavLink>
            );
          })}

          {/* More menu button */}
          <button
            onClick={handleOpenMoreMenu}
            className={clsx(
              'relative flex h-11 min-h-[44px] w-11 min-w-[44px] items-center justify-center rounded-lg transition-colors',
              isMoreMenuActive ? 'text-[#76B900]' : 'text-gray-400 hover:text-white'
            )}
            aria-label="Open more navigation options"
            aria-expanded={isMoreMenuOpen}
            aria-haspopup="dialog"
            data-testid="mobile-nav-more-button"
          >
            <MoreHorizontal className="h-6 w-6" />
          </button>
        </div>
      </nav>

      {/* More menu bottom sheet */}
      <BottomSheet
        isOpen={isMoreMenuOpen}
        onClose={handleCloseMoreMenu}
        title="Navigation"
        height="half"
        aria-labelledby="more-menu-title"
      >
        <div className="space-y-4" data-testid="mobile-nav-more-menu">
          {navGroups.map((group) => {
            // Filter out items already in the primary nav
            const additionalItems = group.items.filter((item) => !primaryNavIds.has(item.id));

            // Skip groups with no additional items
            if (additionalItems.length === 0) {
              return null;
            }

            return (
              <div key={group.id} data-testid={`mobile-nav-group-${group.id}`}>
                {/* Group label */}
                <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-gray-400">
                  {group.label}
                </div>

                {/* Group items */}
                <div className="space-y-1">
                  {additionalItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = isPathActive(item.path);

                    return (
                      <button
                        key={item.id}
                        onClick={() => handleNavigate(item.path)}
                        className={clsx(
                          'flex w-full items-center gap-3 rounded-lg px-3 py-3 transition-colors',
                          'min-h-[44px]', // Touch target size
                          isActive
                            ? 'bg-[#76B900] font-semibold text-black'
                            : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                        )}
                        aria-current={isActive ? 'page' : undefined}
                        data-testid={`mobile-nav-item-${item.id}`}
                      >
                        <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
                        <span className="flex-1 text-left">{item.label}</span>
                        {item.badge && (
                          <span className="rounded bg-yellow-500 px-2 py-0.5 text-xs font-medium text-black">
                            {item.badge}
                          </span>
                        )}
                        <ChevronRight
                          className={clsx('h-4 w-4', isActive ? 'text-black/50' : 'text-gray-500')}
                          aria-hidden="true"
                        />
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </BottomSheet>
    </>
  );
}
