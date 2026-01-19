import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

import {
  AmbientStatusProvider,
  ChunkLoadErrorBoundary,
  ErrorBoundary,
  PageTransition,
  ProductTour,
  RateLimitIndicator,
  RouteLoadingFallback,
  ToastProvider,
} from './components/common';
import Layout from './components/layout/Layout';
import RetryingIndicator from './components/RetryingIndicator';
import { AnnouncementProvider, RateLimitProvider } from './contexts';
import { queryClient } from './services/queryClient';

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

// Logs viewer
const LogsDashboard = lazy(() => import('./components/logs/LogsDashboard'));

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

// Operations (formerly System Monitoring)
const OperationsPage = lazy(() =>
  import('./components/system').then((module) => ({ default: module.SystemMonitoringPage }))
);

// Settings
const SettingsPage = lazy(() => import('./components/settings/SettingsPage'));

// Trash (soft-deleted events)
const TrashPage = lazy(() => import('./pages/TrashPage'));

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AnnouncementProvider>
          <RateLimitProvider>
            <BrowserRouter>
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
                            <Route path="/logs" element={<LogsDashboard />} />
                            <Route path="/audit" element={<AuditLogPage />} />
                            <Route path="/ai" element={<AIPerformancePage />} />
                            <Route path="/ai-audit" element={<AIAuditPage />} />
                            <Route path="/operations" element={<OperationsPage />} />
                            <Route path="/settings" element={<SettingsPage />} />
                            <Route path="/trash" element={<TrashPage />} />
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
          </RateLimitProvider>
        </AnnouncementProvider>
        {/* React Query DevTools - only shown in development */}
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
      </ToastProvider>
    </QueryClientProvider>
  );
}
