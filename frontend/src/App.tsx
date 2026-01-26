import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { lazy, Suspense, useMemo } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

import {
  AmbientStatusProvider,
  ChunkLoadErrorBoundary,
  ErrorBoundary,
  NavigationTracker,
  PageTransition,
  ProductTour,
  RateLimitIndicator,
  RouteLoadingFallback,
  ToastProvider,
} from './components/common';
import Layout from './components/layout/Layout';
import { InstallPrompt } from './components/pwa';
import RetryingIndicator from './components/RetryingIndicator';
import { AnnouncementProvider, ThemeProvider } from './contexts';
import { queryClient } from './services/queryClient';
import {
  createQueryPersister,
  shouldDehydrateQueryCompat,
  PERSISTENCE_MAX_AGE,
} from './services/queryPersistence';

// Lazy-loaded page components for code splitting
// Each page will be loaded as a separate chunk only when navigated to

// Dashboard is loaded eagerly since it's the landing page
// but we still use lazy to maintain consistent patterns
const DashboardPage = lazy(() => import('./components/dashboard/DashboardPage'));

// Event-related pages
const EventTimeline = lazy(() => import('./components/events/EventTimeline'));

// Analytics page
const AnalyticsPage = lazy(() =>
  import('./components/analytics').then((module) => ({ default: module.AnalyticsPage }))
);

// Jobs page
const JobsPage = lazy(() =>
  import('./components/jobs').then((module) => ({ default: module.JobsPage }))
);

// Alert management
const AlertsPage = lazy(() => import('./components/alerts/AlertsPage'));

// Entity tracking
const EntitiesPage = lazy(() => import('./components/entities/EntitiesPage'));

// Logs viewer (Grafana-embedded dashboard)
const LogsPage = lazy(() => import('./components/logs/LogsPage'));

// Audit log
const AuditLogPage = lazy(() =>
  import('./components/audit').then((module) => ({ default: module.AuditLogPage }))
);

// AI performance monitoring
const AIPerformancePage = lazy(() =>
  import('./components/ai').then((module) => ({ default: module.AIPerformancePage }))
);

// AI audit page
const AIAuditPage = lazy(() =>
  import('./components/ai').then((module) => ({ default: module.AIAuditPage }))
);

// Pyroscope profiling
const PyroscopePage = lazy(() =>
  import('./components/pyroscope').then((module) => ({ default: module.PyroscopePage }))
);

// Operations (formerly System Monitoring)
const OperationsPage = lazy(() =>
  import('./components/system').then((module) => ({ default: module.SystemMonitoringPage }))
);

// Tracing
const TracingPage = lazy(() =>
  import('./components/tracing').then((module) => ({ default: module.TracingPage }))
);

// Settings
const SettingsPage = lazy(() => import('./components/settings/SettingsPage'));

// Trash (soft-deleted events)
const TrashPage = lazy(() => import('./pages/TrashPage'));

// Notification Preferences (standalone page)
const NotificationPreferencesPage = lazy(() => import('./pages/NotificationPreferencesPage'));

// Data Management (exports/backups)
const DataManagementPage = lazy(() => import('./pages/DataManagementPage'));

// Zone Intelligence Dashboard
const ZonesPage = lazy(() => import('./pages/ZonesPage'));

// GPU Settings Page
const GpuSettingsPage = lazy(() => import('./pages/GpuSettingsPage'));

// Webhooks Page
const WebhooksPage = lazy(() => import('./pages/WebhooksPage'));

// Scheduled Reports Page
const ScheduledReportsPage = lazy(() => import('./pages/ScheduledReportsPage'));

/**
 * Get persist options for query client.
 * Creates persister only once and memoizes the options.
 * Falls back to regular QueryClientProvider if localStorage unavailable.
 *
 * @see NEM-3363 - Query persistence for offline/cold-start
 */
function usePersistOptions() {
  return useMemo(() => {
    const persister = createQueryPersister();
    if (!persister) {
      return null;
    }
    return {
      persister,
      maxAge: PERSISTENCE_MAX_AGE,
      dehydrateOptions: {
        shouldDehydrateQuery: shouldDehydrateQueryCompat,
      },
    };
  }, []);
}

export default function App() {
  const persistOptions = usePersistOptions();

  // Render function for the app content (shared between both providers)
  const appContent = (
    <ThemeProvider defaultMode="dark">
      <ToastProvider>
        <AnnouncementProvider>
          <BrowserRouter>
            {/* Track navigation between routes for analytics */}
            <NavigationTracker />
            <ErrorBoundary
              title="Application Error"
              description="The application encountered an unexpected error. Please try again or refresh the page."
            >
              {/* Ambient status provider for visual/audio status awareness */}
              <AmbientStatusProvider>
                <Layout>
                  <ChunkLoadErrorBoundary>
                    <Suspense fallback={<RouteLoadingFallback />}>
                      <PageTransition>
                        <Routes>
                          <Route path="/" element={<DashboardPage />} />
                          <Route path="/timeline" element={<EventTimeline />} />
                          <Route path="/analytics" element={<AnalyticsPage />} />
                          <Route path="/jobs" element={<JobsPage />} />
                          <Route path="/alerts" element={<AlertsPage />} />
                          <Route path="/entities" element={<EntitiesPage />} />
                          <Route path="/logs" element={<LogsPage />} />
                          <Route path="/audit" element={<AuditLogPage />} />
                          <Route path="/ai" element={<AIPerformancePage />} />
                          <Route path="/ai-audit" element={<AIAuditPage />} />
                          <Route path="/pyroscope" element={<PyroscopePage />} />
                          <Route path="/operations" element={<OperationsPage />} />
                          <Route path="/tracing" element={<TracingPage />} />
                          <Route path="/settings" element={<SettingsPage />} />
                          <Route path="/notifications" element={<NotificationPreferencesPage />} />
                          <Route path="/trash" element={<TrashPage />} />
                          <Route path="/data" element={<DataManagementPage />} />
                          <Route path="/zones" element={<ZonesPage />} />
                          <Route path="/settings/gpu" element={<GpuSettingsPage />} />
                          <Route path="/webhooks" element={<WebhooksPage />} />
<<<<<<< HEAD
                          <Route path="/scheduled-reports" element={<ScheduledReportsPage />} />
=======
>>>>>>> 81b4a3e2c (feat: implement backup/restore and webhook management systems (NEM-3566, NEM-3624))
                        </Routes>
                      </PageTransition>
                    </Suspense>
                  </ChunkLoadErrorBoundary>
                </Layout>
              </AmbientStatusProvider>
            </ErrorBoundary>
            {/* Interactive product tour for first-time users */}
            <ProductTour />
          </BrowserRouter>
          {/* Rate limit indicator - fixed position overlay */}
          <RateLimitIndicator />
          {/* Retrying indicator - shows when rate limited AND requests in flight */}
          <RetryingIndicator />
          {/* PWA install prompt - shows after engagement criteria met */}
          <InstallPrompt />
        </AnnouncementProvider>
        {/* React Query DevTools - only shown in development */}
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
      </ToastProvider>
    </ThemeProvider>
  );

  // Use PersistQueryClientProvider if persister is available, otherwise fallback
  // This enables instant page loads from cached data (NEM-3363)
  if (persistOptions) {
    return (
      <PersistQueryClientProvider client={queryClient} persistOptions={persistOptions}>
        {appContent}
      </PersistQueryClientProvider>
    );
  }

  // Fallback to regular QueryClientProvider (e.g., SSR, private browsing)
  return <QueryClientProvider client={queryClient}>{appContent}</QueryClientProvider>;
}
