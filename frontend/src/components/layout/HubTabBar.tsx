/**
 * HubTabBar — Renders the tab bar for the active hub (F4.9 — docs/uplevel/4n-modes.md).
 *
 * Supports horizontal overflow scrolling with left/right scroll buttons and
 * ARIA tablist/tab attributes so SettingsPage and every hub's pages share one
 * tab bar implementation.
 */

import { clsx } from 'clsx';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

import { tabForPath } from '../../config/surfaces';

/**
 * Context used by Layout so a nested SettingsPage knows Layout already rendered
 * HubTabBar, while standalone SettingsPage renders in unit tests still mount
 * HubTabBar.
 */
export const LayoutHubTabBarContext = createContext<boolean>(false);

export function useInLayoutHubTabBar(): boolean {
  return useContext(LayoutHubTabBarContext);
}

export interface HubTabBarProps {
  className?: string;
}

export default function HubTabBar({ className }: HubTabBarProps) {
  const location = useLocation();
  const resolved = tabForPath(location.pathname);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollLeft, scrollWidth, clientWidth } = container;
    setCanScrollLeft(scrollLeft > 2);
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 2);
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    updateScrollState();
    container.addEventListener('scroll', updateScrollState);

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(updateScrollState);
      resizeObserver.observe(container);
    }

    return () => {
      container.removeEventListener('scroll', updateScrollState);
      resizeObserver?.disconnect();
    };
  }, [updateScrollState, resolved?.hub.id]);

  if (!resolved) {
    return null;
  }

  const { hub, tab: activeTab } = resolved;

  const scroll = (direction: 'left' | 'right') => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const scrollAmount = 200;
    const newScrollLeft =
      direction === 'left'
        ? container.scrollLeft - scrollAmount
        : container.scrollLeft + scrollAmount;

    container.scrollTo({
      left: newScrollLeft,
      behavior: 'smooth',
    });
  };

  return (
    <div className={clsx('relative px-4 pt-3', className)} data-testid="scrollable-tab-container">
      {canScrollLeft && (
        <>
          <div
            className="pointer-events-none absolute left-4 top-3 z-10 h-[calc(100%-0.75rem)] w-12 bg-gradient-to-r from-[#1A1A1A] to-transparent"
            aria-hidden="true"
          />
          <button
            type="button"
            onClick={() => scroll('left')}
            className="absolute left-5 top-1/2 z-20 -translate-y-1/2 rounded-full bg-[#76B900] p-1.5 text-gray-950 shadow-lg transition-all hover:bg-[#8AD000] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]"
            aria-label="Scroll tabs left"
            data-testid="scroll-left-button"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        </>
      )}

      <div
        ref={scrollContainerRef}
        className="scrollbar-thin scrollbar-track-transparent scrollbar-thumb-gray-700 hover:scrollbar-thumb-gray-600 overflow-x-auto"
      >
        <div
          role="tablist"
          aria-label={`${hub.label} sections`}
          data-testid="hub-tab-bar"
          className="flex min-w-max space-x-2 rounded-lg border border-gray-800 bg-[#1A1A1A] p-1"
        >
          {hub.tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = tab.id === activeTab.id;
            return (
              <NavLink
                key={tab.path}
                id={tab.testId}
                to={tab.path}
                end={Boolean(tab.exact || tab.path === '/')}
                role="tab"
                aria-selected={isActive}
                aria-controls={`settings-panel-${tab.id}`}
                title={tab.description ?? tab.label}
                data-testid={tab.testId}
                className={clsx(
                  'flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-200',
                  'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                  isActive
                    ? 'bg-[#76B900] text-gray-950 shadow-md'
                    : 'text-gray-200 hover:bg-gray-800 hover:text-white'
                )}
              >
                {Icon && <Icon className="h-4 w-4" aria-hidden="true" />}
                <span>{tab.label}</span>
              </NavLink>
            );
          })}
        </div>
      </div>

      {canScrollRight && (
        <>
          <div
            className="pointer-events-none absolute right-4 top-3 z-10 h-[calc(100%-0.75rem)] w-12 bg-gradient-to-l from-[#1A1A1A] to-transparent"
            aria-hidden="true"
          />
          <button
            type="button"
            onClick={() => scroll('right')}
            className="absolute right-5 top-1/2 z-20 -translate-y-1/2 rounded-full bg-[#76B900] p-1.5 text-gray-950 shadow-lg transition-all hover:bg-[#8AD000] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]"
            aria-label="Scroll tabs right"
            data-testid="scroll-right-button"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </>
      )}
    </div>
  );
}
