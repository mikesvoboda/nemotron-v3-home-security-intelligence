import { clsx } from 'clsx';
import { Outlet, useLocation } from 'react-router-dom';

import { hubForPath, tabForPath } from '../../config/surfaces';
import { DebugModeProvider } from '../../contexts/DebugModeContext';
import { FeatureErrorBoundary, SecureContextWarning } from '../common';
import HubTabBar, { useInLayoutHubTabBar } from '../layout/HubTabBar';

/**
 * SettingsPage component (F4.9 — docs/uplevel/4n-modes.md).
 *
 * Keeps its `<Outlet />` and providers (`DebugModeProvider`, `SecureContextWarning`);
 * its heading comes from `hubForPath`, its tab bar gives way to `HubTabBar`, and
 * its panel is labelled by `HubTabBar`'s active tab.
 */
export default function SettingsPage() {
  const location = useLocation();
  const inLayoutHubTabBar = useInLayoutHubTabBar();

  const resolved = tabForPath(location.pathname);
  const hub = resolved?.hub ?? hubForPath('/settings');
  const activeTabId = resolved?.tab.id ?? 'cameras';
  const activeTabTestId = resolved?.tab.testId ?? `settings-tab-${activeTabId}`;
  const heading = hub?.label ?? 'Settings';

  return (
    <DebugModeProvider>
      <div className="min-h-screen bg-[#121212] p-8" data-testid="settings-page">
        <div className="mx-auto max-w-[1920px]">
          {/* Header */}
          <div className="mb-8 flex items-start justify-between">
            <div>
              <h1 className="text-page-title">{heading}</h1>
              <p className="text-body-sm mt-2">Configure your security monitoring system</p>
            </div>
          </div>

          {/* Secure Context Warning - shown when not using HTTPS */}
          <SecureContextWarning className="mb-6" />

          {/* HubTabBar renders here when SettingsPage is mounted standalone in tests */}
          {!inLayoutHubTabBar && <HubTabBar className="mb-8 px-0 pt-0" />}

          {/* Content Panel */}
          <div
            id={`settings-panel-${activeTabId}`}
            role="tabpanel"
            aria-labelledby={activeTabTestId}
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

export function SettingsPageWithErrorBoundary() {
  return (
    <FeatureErrorBoundary
      feature="Settings"
      fallback={
        <div className="min-h-screen bg-[#121212] p-8">
          <div className="mx-auto max-w-[1920px]">
            <div className="mb-8">
              <h1 className="text-page-title">Settings</h1>
              <p className="text-body-sm mt-2">Configure your security monitoring system</p>
            </div>
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6">
              <h3 className="text-base font-semibold text-red-400">Unable to load Settings</h3>
              <p className="mt-1 text-sm text-gray-400">
                An error occurred while loading settings. Please try refreshing the page. Use the
                navigation menu to access other parts of the application.
              </p>
            </div>
          </div>
        </div>
      }
    >
      <SettingsPage />
    </FeatureErrorBoundary>
  );
}
