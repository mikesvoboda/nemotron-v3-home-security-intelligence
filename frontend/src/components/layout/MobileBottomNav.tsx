/**
 * MobileBottomNav - Fixed bottom navigation for mobile devices (F4.9).
 *
 * Keeps Dashboard, Timeline, Alerts, and More in the bottom bar; the More
 * bottom sheet renders ModeSwitch followed by the remaining hubs for the
 * active view mode.
 */

import { clsx } from 'clsx';
import { Home, Clock, Bell, MoreHorizontal, ChevronRight } from 'lucide-react';
import { useCallback, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';

import ModeSwitch from './ModeSwitch';
import { ADVANCED_HUBS, EASY_HUBS, hubForPath, type Hub } from '../../config/surfaces';
import { useViewMode } from '../../contexts/ViewModeContext';
import BottomSheet from '../common/BottomSheet';

export interface MobileBottomNavProps {
  /** Number of unread notifications to display as badge (optional) */
  notificationCount?: number;
}

interface PrimaryNavItem {
  id: string;
  hubId: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  path: string;
  showBadge?: boolean;
}

/** Primary nav items shown directly in the bottom bar */
const primaryNavItems: PrimaryNavItem[] = [
  { id: 'dashboard', hubId: 'dashboard', label: 'Dashboard', icon: Home, path: '/' },
  {
    id: 'timeline',
    hubId: 'timeline-search',
    label: 'Timeline',
    icon: Clock,
    path: '/timeline',
  },
  {
    id: 'alerts',
    hubId: 'alerts-rules',
    label: 'Alerts',
    icon: Bell,
    path: '/alerts',
    showBadge: true,
  },
];

const primaryHubIds = new Set(primaryNavItems.map((item) => item.hubId));

export default function MobileBottomNav({ notificationCount = 0 }: MobileBottomNavProps) {
  const [isMoreMenuOpen, setIsMoreMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { mode } = useViewMode();

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

  const activeHub = hubForPath(location.pathname);

  const remainingEasyHubs = EASY_HUBS.filter((hub) => !primaryHubIds.has(hub.id));
  const remainingAdvancedHubs = mode === 'advanced' ? ADVANCED_HUBS : [];
  const moreHubs: readonly Hub[] = [...remainingEasyHubs, ...remainingAdvancedHubs];

  const isMoreMenuActive = Boolean(activeHub && moreHubs.some((h) => h.id === activeHub.id));

  return (
    <>
      <nav
        className="fixed bottom-0 left-0 right-0 z-50 h-14 border-t border-gray-800 bg-[#1A1A1A] pb-safe"
        role="navigation"
        aria-label="Mobile navigation"
      >
        <div className="flex h-full items-center justify-around">
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

      <BottomSheet
        isOpen={isMoreMenuOpen}
        onClose={handleCloseMoreMenu}
        title="Navigation"
        height="half"
        aria-labelledby="more-menu-title"
      >
        <div className="space-y-4" data-testid="mobile-nav-more-menu">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              View Mode
            </span>
            <ModeSwitch />
          </div>

          <div className="space-y-1">
            {remainingEasyHubs.map((hub) => {
              const Icon = hub.icon;
              const isActive = activeHub?.id === hub.id;
              const targetPath = hub.tabs[0]?.path ?? '/';

              return (
                <button
                  key={hub.id}
                  onClick={() => handleNavigate(targetPath)}
                  className={clsx(
                    'flex w-full items-center gap-3 rounded-lg px-3 py-3 transition-colors',
                    'min-h-[44px]',
                    isActive
                      ? 'bg-[#76B900] font-semibold text-black'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  )}
                  aria-current={isActive ? 'page' : undefined}
                  data-testid={`mobile-nav-item-${hub.id}`}
                >
                  <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
                  <span className="flex-1 text-left">{hub.label}</span>
                  <ChevronRight
                    className={clsx('h-4 w-4', isActive ? 'text-black/50' : 'text-gray-500')}
                    aria-hidden="true"
                  />
                </button>
              );
            })}

            {remainingAdvancedHubs.length > 0 && (
              <>
                <div className="my-2 border-t border-gray-800 px-1 pt-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                  AI Blueprint
                </div>
                {remainingAdvancedHubs.map((hub) => {
                  const Icon = hub.icon;
                  const isActive = activeHub?.id === hub.id;
                  const targetPath = hub.tabs[0]?.path ?? '/';

                  return (
                    <button
                      key={hub.id}
                      onClick={() => handleNavigate(targetPath)}
                      className={clsx(
                        'flex w-full items-center gap-3 rounded-lg px-3 py-3 transition-colors',
                        'min-h-[44px]',
                        isActive
                          ? 'bg-[#76B900] font-semibold text-black'
                          : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                      )}
                      aria-current={isActive ? 'page' : undefined}
                      data-testid={`mobile-nav-item-${hub.id}`}
                    >
                      <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
                      <span className="flex-1 text-left">{hub.label}</span>
                      <ChevronRight
                        className={clsx('h-4 w-4', isActive ? 'text-black/50' : 'text-gray-500')}
                        aria-hidden="true"
                      />
                    </button>
                  );
                })}
              </>
            )}
          </div>
        </div>
      </BottomSheet>
    </>
  );
}
