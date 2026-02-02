import { clsx } from 'clsx';
import { AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { DebugModeProvider } from '../../contexts/DebugModeContext';
import { FeatureErrorBoundary, SecureContextWarning } from '../common';
import { settingsTabs } from './settingsTabsConfig';

/**
 * ScrollableNavList component that handles horizontal nav overflow
 *
 * Features:
 * - Horizontal scrolling when nav items overflow the container
 * - Left/right scroll indicators (chevron buttons) when content is clipped
 * - Fade shadows to indicate scrollable content
 * - Keyboard-accessible scroll buttons
 * - Smooth scroll animation
 *
 * @see NEM-3520 - Fix Settings page tab overflow
 * @see NEM-4938 - Convert to nested sub-routes
 */
interface ScrollableNavListProps {
  children: React.ReactNode;
}

function ScrollableNavList({ children }: ScrollableNavListProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollLeft, scrollWidth, clientWidth } = container;
    // Use a small threshold (2px) to account for rounding errors
    setCanScrollLeft(scrollLeft > 2);
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 2);
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    // Initial check
    updateScrollState();

    // Check on scroll
    container.addEventListener('scroll', updateScrollState);

    // Check on resize
    const resizeObserver = new ResizeObserver(updateScrollState);
    resizeObserver.observe(container);

    return () => {
      container.removeEventListener('scroll', updateScrollState);
      resizeObserver.disconnect();
    };
  }, [updateScrollState]);

  const scroll = (direction: 'left' | 'right') => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const scrollAmount = 200; // pixels to scroll
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
    <div className="relative mb-8" data-testid="scrollable-tab-container">
      {/* Left scroll indicator */}
      {canScrollLeft && (
        <>
          {/* Fade shadow */}
          <div
            className="pointer-events-none absolute left-0 top-0 z-10 h-full w-12 bg-gradient-to-r from-[#1A1A1A] to-transparent"
            aria-hidden="true"
          />
          {/* Scroll button */}
          <button
            type="button"
            onClick={() => scroll('left')}
            className="absolute left-1 top-1/2 z-20 -translate-y-1/2 rounded-full bg-[#76B900] p-1.5 text-gray-950 shadow-lg transition-all hover:bg-[#8AD000] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]"
            aria-label="Scroll tabs left"
            data-testid="scroll-left-button"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        </>
      )}

      {/* Scrollable nav container */}
      <div
        ref={scrollContainerRef}
        className="scrollbar-thin scrollbar-track-transparent scrollbar-thumb-gray-700 hover:scrollbar-thumb-gray-600 overflow-x-auto"
      >
        <div
          role="tablist"
          aria-label="Settings sections"
          className="flex min-w-max space-x-2 rounded-lg border border-gray-800 bg-[#1A1A1A] p-1"
        >
          {children}
        </div>
      </div>

      {/* Right scroll indicator */}
      {canScrollRight && (
        <>
          {/* Fade shadow */}
          <div
            className="pointer-events-none absolute right-0 top-0 z-10 h-full w-12 bg-gradient-to-l from-[#1A1A1A] to-transparent"
            aria-hidden="true"
          />
          {/* Scroll button */}
          <button
            type="button"
            onClick={() => scroll('right')}
            className="absolute right-1 top-1/2 z-20 -translate-y-1/2 rounded-full bg-[#76B900] p-1.5 text-gray-950 shadow-lg transition-all hover:bg-[#8AD000] focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]"
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

/**
 * SettingsPage component with route-based navigation
 *
 * Contains eleven settings sections accessible via nested routes:
 * - /settings/cameras: Camera configuration and management
 * - /settings/rules: Alert rules configuration
 * - /settings/processing: Event processing settings
 * - /settings/notifications: Email and webhook notification settings
 * - /settings/ambient: Ambient status awareness settings
 * - /settings/calibration: AI risk sensitivity and feedback calibration
 * - /settings/access: Household members, vehicles, and zone-based access control
 * - /settings/prompts: AI prompt template management and version history
 * - /settings/storage: Disk storage usage and file cleanup operations
 * - /settings/ai-models: Core AI models (RT-DETRv2, Nemotron) and Model Zoo status
 * - /settings/admin: Feature toggles, system config, maintenance actions, dev tools
 *
 * Note: Analytics functionality is available on the dedicated Analytics page (/analytics)
 *
 * Features:
 * - Route-based navigation with URL persistence
 * - NavLink active state styling
 * - NVIDIA dark theme styling
 * - Icons for each settings category
 * - Responsive layout
 * - Keyboard navigation support
 *
 * @see NEM-2356 - Add CalibrationPanel to Settings page
 * @see NEM-2388 - Add FileOperationsPanel to Settings page
 * @see NEM-3084 - Add AI MODELS tab integrating AIModelsSettings and ModelZooSection
 * @see NEM-3138 - Add ADMIN tab for AdminSettings component
 * @see NEM-3608 - Add ACCESS tab for zone-household access control
 * @see NEM-4938 - Convert to nested sub-routes
 */
export default function SettingsPage() {
  const location = useLocation();

  // Determine the active tab based on current path
  const activeTabId =
    settingsTabs.find((tab) => location.pathname === tab.path)?.id ?? 'cameras';

  return (
    <DebugModeProvider>
      <div className="min-h-screen bg-[#121212] p-8" data-testid="settings-page">
        <div className="mx-auto max-w-[1920px]">
          {/* Header */}
          <div className="mb-8 flex items-start justify-between">
            <div>
              <h1 className="text-page-title">Settings</h1>
              <p className="text-body-sm mt-2">Configure your security monitoring system</p>
            </div>
          </div>

          {/* Secure Context Warning - shown when not using HTTPS */}
          <SecureContextWarning className="mb-6" />

          {/* Navigation Tabs */}
          <ScrollableNavList>
            {settingsTabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = tab.id === activeTabId;
              return (
                <NavLink
                  key={tab.id}
                  to={tab.path}
                  role="tab"
                  aria-selected={isActive}
                  aria-controls={`settings-panel-${tab.id}`}
                  title={tab.description}
                  className={clsx(
                    'flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-4 py-3 text-sm font-medium transition-all duration-200',
                    'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                    isActive
                      ? 'bg-[#76B900] text-gray-950 shadow-md'
                      : 'text-gray-200 hover:bg-gray-800 hover:text-white'
                  )}
                  data-testid={`settings-tab-${tab.id}`}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                  <span>{tab.name}</span>
                </NavLink>
              );
            })}
          </ScrollableNavList>

          {/* Content Panel */}
          <div
            id={`settings-panel-${activeTabId}`}
            role="tabpanel"
            aria-labelledby={`settings-tab-${activeTabId}`}
            className={clsx(
              'rounded-lg border border-gray-800 bg-[#1A1A1A] p-6',
              'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]'
            )}
            data-testid="settings-content-panel"
          >
            <Outlet />
          </div>
        </div>
      </div>
    </DebugModeProvider>
  );
}

/**
 * SettingsPage with FeatureErrorBoundary wrapper.
 *
 * Wraps the SettingsPage component in a FeatureErrorBoundary to prevent
 * errors in the Settings page from crashing the entire application.
 * The navigation should remain functional even if settings fails to load.
 */
function SettingsPageWithErrorBoundary() {
  return (
    <FeatureErrorBoundary
      feature="Settings"
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center bg-[#121212] p-8">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">Settings Unavailable</h3>
          <p className="max-w-md text-center text-sm text-gray-400">
            Unable to load settings. Please refresh the page or try again later. You can still
            navigate to other sections using the sidebar.
          </p>
        </div>
      }
    >
      <SettingsPage />
    </FeatureErrorBoundary>
  );
}

export { SettingsPageWithErrorBoundary };
