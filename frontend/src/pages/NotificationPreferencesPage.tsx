/**
 * NotificationPreferencesPage - Dedicated page for notification preferences management
 *
 * This page provides a standalone view for managing all notification settings including:
 * - Global notification enable/disable
 * - Per-camera notification toggles with risk thresholds
 * - Quiet hours configuration
 * - Notification sound preferences
 * - Risk level filters for notification triggers
 * - Email and webhook channel configuration status
 *
 * The same functionality is available in the Settings page under the NOTIFICATIONS tab,
 * but this dedicated page provides direct access via /notifications route.
 *
 * @module pages/NotificationPreferencesPage
 * @see NEM-3172 - Create Notification Preferences page
 */

import { AlertTriangle, ArrowLeft, Bell } from 'lucide-react';
import { Link } from 'react-router-dom';

import { FeatureErrorBoundary } from '../components/common';
import NotificationSettings from '../components/settings/NotificationSettings';

/**
 * NotificationPreferencesPage displays the full notification settings interface
 * as a standalone page.
 */
export default function NotificationPreferencesPage() {
  return (
    <div
      className="min-h-screen bg-[#121212] p-6 md:p-8"
      data-testid="notification-preferences-page"
    >
      <div className="mx-auto max-w-4xl">
        {/* Page Header */}
        <div className="mb-6">
          <Link
            to="/settings"
            className="mb-4 inline-flex items-center gap-2 text-sm text-gray-400 transition-colors hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Settings
          </Link>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#76B900]/20">
              <Bell className="h-5 w-5 text-[#76B900]" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Notification Preferences</h1>
              <p className="mt-1 text-sm text-gray-400">
                Manage how and when you receive security alerts
              </p>
            </div>
          </div>
        </div>

        {/* Notification Settings Component */}
        <NotificationSettings />
      </div>
    </div>
  );
}

/**
 * NotificationPreferencesPage with FeatureErrorBoundary wrapper.
 *
 * Wraps the NotificationPreferencesPage component in a FeatureErrorBoundary to prevent
 * errors from crashing the entire application. Navigation should remain functional
 * even if notification settings fail to load.
 */
function NotificationPreferencesPageWithErrorBoundary() {
  return (
    <FeatureErrorBoundary
      feature="Notification Preferences"
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center bg-[#121212] p-8">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">
            Notification Preferences Unavailable
          </h3>
          <p className="max-w-md text-center text-sm text-gray-400">
            Unable to load notification preferences. Please refresh the page or try again later. You
            can also access notification settings from the Settings page.
          </p>
          <Link
            to="/settings"
            className="mt-4 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-gray-950 transition-colors hover:bg-[#8ED000]"
          >
            Go to Settings
          </Link>
        </div>
      }
    >
      <NotificationPreferencesPage />
    </FeatureErrorBoundary>
  );
}

export { NotificationPreferencesPageWithErrorBoundary };
