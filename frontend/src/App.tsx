import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { lazy, Suspense, useMemo } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import { ProtectedRoute } from './components/auth';
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
import { AnnouncementProvider, AuthProvider, ThemeProvider } from './contexts';
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

// AI Services (Grafana dashboard)
const AIServicesPage = lazy(() =>
  import('./components/ai').then((module) => ({ default: module.AIServicesPage }))
);

// Video Analytics (Grafana dashboard)
const VideoAnalyticsPage = lazy(() =>
  import('./components/analytics').then((module) => ({ default: module.VideoAnalyticsPage }))
);

// Operations Dashboard (Grafana dashboard)
const OperationsDashboardPage = lazy(() =>
  import('./components/operations').then((module) => ({ default: module.OperationsDashboardPage }))
);

// GPU Metrics (Grafana dashboard)
const GpuMetricsPage = lazy(() =>
  import('./components/operations').then((module) => ({ default: module.GpuMetricsPage }))
);

// Request Profiling (Grafana dashboard)
const RequestProfilingPage = lazy(() =>
  import('./components/operations').then((module) => ({ default: module.RequestProfilingPage }))
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

// Settings (uses nested routes for sub-sections - NEM-4938)
const SettingsPage = lazy(() => import('./components/settings/SettingsPage'));

// Settings sub-pages (lazy loaded for code splitting)
const CamerasSettings = lazy(() => import('./components/settings/CamerasSettings'));
const AlertRulesSettings = lazy(() => import('./components/settings/AlertRulesSettings'));
const ProcessingSettings = lazy(() => import('./components/settings/ProcessingSettings'));
const NotificationSettings = lazy(() => import('./components/settings/NotificationSettings'));
const AmbientStatusSettings = lazy(() => import('./components/settings/AmbientStatusSettings'));
const CalibrationPanel = lazy(() => import('./components/settings/CalibrationPanel'));
const AccessControlSettings = lazy(() => import('./components/settings/AccessControlSettings'));
const PromptManagementPage = lazy(() =>
  import('./components/settings/prompts').then((m) => ({ default: m.PromptManagementPage }))
);
const FileOperationsPanel = lazy(() => import('./components/system/FileOperationsPanel'));
const AIModelsTab = lazy(() => import('./components/settings/AIModelsTab'));
const AdminSettings = lazy(() => import('./components/settings/AdminSettings'));

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

// Plate Reads Page (License Plate Recognition)
const PlateReadsPage = lazy(() =>
  import('./components/plate-reads').then((m) => ({ default: m.PlateReadsPage }))
);

// Household Members Page
const HouseholdPage = lazy(() => import('./pages/HouseholdPage'));

// Face Recognition Page
const FaceRecognitionPage = lazy(() => import('./pages/FaceRecognitionPage'));

// Heatmaps Visualization Page
const HeatmapsPage = lazy(() => import('./pages/HeatmapsPage'));

// Scene Changes History Page
const SceneChangesPage = lazy(() => import('./pages/SceneChangesPage'));

// Tracks Visualization Page
const TracksPage = lazy(() => import('./pages/TracksPage'));

// Re-ID Dashboard (NEM-5024 Phase 8)
const ReIDDashboard = lazy(() =>
  import('./components/reid').then((m) => ({ default: m.ReIDDashboard }))
);

// 404 Not Found Page (NEM-4925)
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

// Auth pages (NEM-5322)
const LoginPage = lazy(() => import('./pages/LoginPage'));
const SetupPage = lazy(() =>
  import('./components/auth').then((m) => ({ default: m.SetupPage }))
);

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
          <AuthProvider>
            <BrowserRouter>
              {/* Track navigation between routes for analytics */}
              <NavigationTracker />
              <ErrorBoundary
                title="Application Error"
                description="The application encountered an unexpected error. Please try again or refresh the page."
              >
                {/* Auth routes - outside main layout (NEM-5322) */}
                <Routes>
                  <Route
                    path="/login"
                    element={
                      <Suspense fallback={<RouteLoadingFallback />}>
                        <LoginPage />
                      </Suspense>
                    }
                  />
                  <Route
                    path="/setup"
                    element={
                      <Suspense fallback={<RouteLoadingFallback />}>
                        <SetupPage />
                      </Suspense>
                    }
                  />
                  {/* Main app routes with layout - protected by auth (NEM-5322) */}
                  <Route
                    path="/*"
                    element={
                      <ProtectedRoute>
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
                                  <Route path="/ai-services" element={<AIServicesPage />} />
                                  <Route path="/video-analytics" element={<VideoAnalyticsPage />} />
                                  <Route path="/pyroscope" element={<PyroscopePage />} />
                                  <Route path="/operations" element={<OperationsPage />} />
                                  <Route path="/operations-dashboard" element={<OperationsDashboardPage />} />
                                  <Route path="/gpu-metrics" element={<GpuMetricsPage />} />
                                  <Route path="/request-profiling" element={<RequestProfilingPage />} />
                                  <Route path="/tracing" element={<TracingPage />} />
                                  {/* Settings page with nested sub-routes (NEM-4938) */}
                                  <Route path="/settings" element={<SettingsPage />}>
                                    {/* Default redirect to cameras */}
                                    <Route index element={<Navigate to="cameras" replace />} />
                                    <Route path="cameras" element={<CamerasSettings />} />
                                    <Route path="rules" element={<AlertRulesSettings />} />
                                    <Route path="processing" element={<ProcessingSettings />} />
                                    <Route path="notifications" element={<NotificationSettings />} />
                                    <Route path="ambient" element={<AmbientStatusSettings />} />
                                    <Route path="calibration" element={<CalibrationPanel />} />
                                    <Route path="access" element={<AccessControlSettings />} />
                                    <Route path="prompts" element={<PromptManagementPage />} />
                                    <Route path="storage" element={<FileOperationsPanel />} />
                                    <Route path="ai-models" element={<AIModelsTab />} />
                                    <Route path="admin" element={<AdminSettings />} />
                                    <Route path="gpu" element={<GpuSettingsPage />} />
                                  </Route>
                                  <Route path="/notifications" element={<NotificationPreferencesPage />} />
                                  <Route path="/trash" element={<TrashPage />} />
                                  <Route path="/data" element={<DataManagementPage />} />
                                  <Route path="/zones" element={<ZonesPage />} />
                                  <Route path="/webhooks" element={<WebhooksPage />} />
                                  <Route path="/scheduled-reports" element={<ScheduledReportsPage />} />
                                  <Route path="/plate-reads" element={<PlateReadsPage />} />
                                  <Route path="/household" element={<HouseholdPage />} />
                                  <Route path="/face-recognition" element={<FaceRecognitionPage />} />
                                  <Route path="/heatmaps" element={<HeatmapsPage />} />
                                  <Route path="/scene-changes" element={<SceneChangesPage />} />
                                  <Route path="/tracks" element={<TracksPage />} />
                                  <Route path="/reid" element={<ReIDDashboard />} />
                                  {/* Catch-all route for 404 Not Found (NEM-4925) */}
                                  <Route path="*" element={<NotFoundPage />} />
                                </Routes>
                                </PageTransition>
                              </Suspense>
                            </ChunkLoadErrorBoundary>
                          </Layout>
                        </AmbientStatusProvider>
                      </ProtectedRoute>
                    }
                  />
                </Routes>
              </ErrorBoundary>
              {/* Interactive product tour for first-time users */}
              <ProductTour />
            </BrowserRouter>
          </AuthProvider>
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
