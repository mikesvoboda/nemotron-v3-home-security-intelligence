/**
 * AnalyticsPage - Grafana dashboard embed for analytics metrics
 *
 * Displays the HSI Analytics Grafana dashboard in kiosk mode, providing:
 * - Detection trends and statistics
 * - Risk analysis and distribution
 * - Camera activity metrics
 * - Activity patterns and baselines
 *
 * Native view includes:
 * - Camera uptime metrics
 * - Pipeline latency monitoring
 * - Event patterns and insights visualization (NEM-3618)
 * - Hourly/daily summaries (NEM-3595)
 *
 * All detailed metrics are rendered by Grafana for consistency with
 * other monitoring dashboards and reduced frontend complexity.
 */

import { BarChart3, RefreshCw, ExternalLink, AlertCircle, AlertTriangle } from 'lucide-react';
import { useEffect, useState, useRef, useCallback, useMemo } from 'react';

import CameraUptimeCard from './CameraUptimeCard';
import PipelineLatencyPanel from './PipelineLatencyPanel';
import RiskHistoryCard from './RiskHistoryCard';
import RiskScoreDistributionCard from './RiskScoreDistributionCard';
import RiskScoreTrendCard from './RiskScoreTrendCard';
import InsightsCharts from '../ai/InsightsCharts';
import { SummaryCards } from '../dashboard/SummaryCards';
import { useCameraAnalytics } from '../../hooks/useCameraAnalytics';
import { fetchConfig } from '../../services/api';
import { useSummaries } from '../../hooks/useSummaries';
import { resolveGrafanaUrl } from '../../utils/grafanaUrl';
import { FeatureErrorBoundary } from '../common/FeatureErrorBoundary';

/** View mode for analytics display */
type ViewMode = 'grafana' | 'native';

/**
 * AnalyticsPage - Grafana iframe embed for analytics metrics
 */
export default function AnalyticsPage() {
  const [grafanaUrl, setGrafanaUrl] = useState<string>('/grafana');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('grafana');
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Fetch summaries for insights display (NEM-3595)
  const {
    hourly: hourlySummary,
    daily: dailySummary,
    isLoading: summariesLoading,
    error: summariesError,
    refetch: refetchSummaries,
  } = useSummaries();


  // Fetch Grafana URL from config and resolve for remote access
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await fetchConfig();
        const configWithGrafana = config as typeof config & { grafana_url?: string };
        if (configWithGrafana.grafana_url) {
          const resolvedUrl = resolveGrafanaUrl(configWithGrafana.grafana_url);
          setGrafanaUrl(resolvedUrl);
        }
        setIsLoading(false);
      } catch (err) {
        console.error('Failed to fetch config:', err);
        setError('Failed to load configuration. Using default Grafana URL.');
        setIsLoading(false);
      }
    };
    void loadConfig();
  }, []);

  // Handle refresh by reloading the iframe
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    if (iframeRef.current) {
      // Reload iframe by resetting src
      const currentSrc = iframeRef.current.src;
      iframeRef.current.src = '';
      // Use setTimeout to ensure the src change takes effect
      setTimeout(() => {
        if (iframeRef.current) {
          iframeRef.current.src = currentSrc;
        }
        setIsRefreshing(false);
      }, 100);
    } else {
      setIsRefreshing(false);
    }
  }, []);

  // Handle iframe load error
  const handleIframeError = () => {
    setError('Failed to load Grafana dashboard. Please check if Grafana is running.');
  };

  // Grafana dashboard URL with kiosk mode, dark theme, and auto-refresh
  const dashboardUrl = `${grafanaUrl}/d/hsi-analytics?orgId=1&kiosk=1&theme=dark&refresh=30s`;

  // Calculate date range for CameraUptimeCard (last 7 days)
  const dateRange = useMemo(() => {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - 7);
    return {
      startDate: startDate.toISOString().split('T')[0],
      endDate: endDate.toISOString().split('T')[0],
    };
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="analytics-loading">
        <div className="mx-auto max-w-[1920px]">
          {/* Header skeleton */}
          <div className="mb-8">
            <div className="h-10 w-72 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800"></div>
          </div>

          {/* Dashboard skeleton */}
          <div className="h-[calc(100vh-200px)] animate-pulse rounded-lg bg-gray-800"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212]" data-testid="analytics-page">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-gray-800 px-8 py-4">
        <div className="flex items-center gap-3">
          <BarChart3 className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-page-title">Analytics</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div
            className="flex overflow-hidden rounded-lg border border-gray-700"
            data-testid="view-mode-toggle"
          >
            <button
              onClick={() => setViewMode('grafana')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                viewMode === 'grafana'
                  ? 'bg-[#76B900] text-black'
                  : 'bg-gray-800 text-white hover:bg-gray-700'
              }`}
              data-testid="view-mode-grafana"
            >
              Grafana
            </button>
            <button
              onClick={() => setViewMode('native')}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                viewMode === 'native'
                  ? 'bg-[#76B900] text-black'
                  : 'bg-gray-800 text-white hover:bg-gray-700'
              }`}
              data-testid="view-mode-native"
            >
              Native
            </button>
          </div>

          {/* External Grafana Link - only show in Grafana view */}
          {viewMode === 'grafana' && (
            <a
              href={`${grafanaUrl}/d/hsi-analytics?orgId=1`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
              data-testid="grafana-external-link"
            >
              <ExternalLink className="h-4 w-4" />
              Open in Grafana
            </a>
          )}

          {/* Refresh Button - only show in Grafana view */}
          {viewMode === 'grafana' && (
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
              data-testid="analytics-refresh-button"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          )}
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          className="mx-8 mt-4 flex items-center gap-3 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-4"
          data-testid="analytics-error"
        >
          <AlertCircle className="h-5 w-5 text-yellow-500" />
          <span className="text-sm text-yellow-200">{error}</span>
        </div>
      )}

      {/* Grafana iframe - only show in Grafana view */}
      {viewMode === 'grafana' && (
        <iframe
          ref={iframeRef}
          src={dashboardUrl}
          className="h-[calc(100vh-73px)] w-full border-0"
          title="Analytics Dashboard"
          data-testid="grafana-iframe"
          onError={handleIframeError}
        />
      )}

      {/* Native analytics components */}
      {viewMode === 'native' && (
        <div className="p-6" data-testid="native-analytics-view">
          {/* Summary Cards Section - Hourly/Daily summaries (NEM-3595) */}
          <div className="mb-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Event Summaries</h2>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <SummaryCards
                hourly={hourlySummary}
                daily={dailySummary}
                isLoading={summariesLoading}
                error={summariesError}
                onRetry={() => void refetchSummaries()}
              />
            </div>
          </div>

          {/* Analytics cards grid */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
            {/* Camera-specific detection analytics */}
            <CameraAnalyticsDetail
              totalDetections={totalDetections}
              detectionsByClass={detectionsByClass}
              averageConfidence={averageConfidence}
              isLoading={isLoadingStats}
              error={statsError}
              cameraName={selectedCamera?.name}
            />
            <DetectionTrendsCard dateRange={dateRange} />
            <RiskHistoryCard dateRange={dateRange} />
            <ObjectDistributionCard dateRange={dateRange} />
            <CameraUptimeCard dateRange={dateRange} />
            <RiskScoreDistributionCard dateRange={dateRange} />
            <RiskScoreTrendCard dateRange={dateRange} />
          </div>

          {/* Insights Charts Section - Event Patterns Visualization (NEM-3618) */}
          <div className="mb-6 mt-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Event Patterns & Insights</h2>
            <InsightsCharts data-testid="insights-charts" />
          </div>

          {/* Infrastructure Metrics */}
          <h2 className="mb-4 text-lg font-semibold text-white">Infrastructure Metrics</h2>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <CameraUptimeCard dateRange={dateRange} />
            <PipelineLatencyPanel refreshInterval={30000} />
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * AnalyticsPage with FeatureErrorBoundary wrapper.
 *
 * Wraps the AnalyticsPage component in a FeatureErrorBoundary to prevent
 * errors in the Analytics page from crashing the entire application.
 */
function AnalyticsPageWithErrorBoundary() {
  return (
    <FeatureErrorBoundary
      feature="Analytics"
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center bg-[#121212] p-8">
          <AlertTriangle className="mb-4 h-12 w-12 text-red-400" />
          <h3 className="mb-2 text-lg font-semibold text-red-400">Analytics Unavailable</h3>
          <p className="max-w-md text-center text-sm text-gray-400">
            Unable to load analytics dashboard. Please refresh the page or try again later. Other
            parts of the application should still work.
          </p>
        </div>
      }
    >
      <AnalyticsPage />
    </FeatureErrorBoundary>
  );
}

export { AnalyticsPageWithErrorBoundary };
