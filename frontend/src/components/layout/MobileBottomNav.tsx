/**
 * MobileBottomNav - Fixed bottom navigation for mobile devices
 *
 * Displays primary navigation icons at bottom of screen for mobile viewports.
 * Includes safe area inset padding for iOS notch/home indicator support.
 */

import { Home, Clock, Bell, Settings } from 'lucide-react';
import { NavLink } from 'react-router-dom';

export interface MobileBottomNavProps {
  /** Number of unread notifications to display as badge (optional) */
  notificationCount?: number;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  path: string;
  showBadge?: boolean;
}

export default function MobileBottomNav({ notificationCount = 0 }: MobileBottomNavProps) {
  const navItems: NavItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: Home, path: '/' },
    { id: 'timeline', label: 'Timeline', icon: Clock, path: '/timeline' },
    { id: 'alerts', label: 'Alerts', icon: Bell, path: '/alerts', showBadge: true },
    { id: 'settings', label: 'Settings', icon: Settings, path: '/settings' },
  ];

  const formatBadgeCount = (count: number): string => {
    return count > 9 ? '9+' : count.toString();
  };

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 h-14 border-t border-gray-800 bg-[#1A1A1A] pb-safe"
      role="navigation"
      aria-label="Mobile navigation"
    >
      <div className="flex h-full items-center justify-around">
        {navItems.map((item) => {
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
      </div>
    </nav>
  );
}
