/**
 * AIPerformancePage - Grafana dashboard embed for AI performance metrics
 *
 * Displays the consolidated HSI Grafana dashboard in kiosk mode, providing:
 * - Real-time AI model metrics
 * - Historical trends
 * - GPU utilization
 * - Pipeline health monitoring
 *
 * All detailed metrics are rendered by Grafana for consistency with
 * other monitoring dashboards and reduced frontend complexity.
 */

import { Brain, RefreshCw, ExternalLink, AlertCircle } from 'lucide-react';
import { useEffect, useState, useRef, useCallback } from 'react';

import ModelZooSection from './ModelZooSection';
import { fetchConfig } from '../../services/api';
import { resolveGrafanaUrl } from '../../utils/grafanaUrl';

/**
 * AIPerformancePage - Grafana iframe embed for AI metrics
 */
export default function AIPerformancePage() {
  const [grafanaUrl, setGrafanaUrl] = useState<string>('/grafana');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

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
  const dashboardUrl = `${grafanaUrl}/d/ai-services/ai-services?orgId=1&kiosk=1&theme=dark&refresh=30s`;

  return (
    <div
      className="min-h-screen bg-[#121212]"
      data-testid={isLoading ? 'ai-performance-loading' : 'ai-performance-page'}
    >
      {/* Header - Always visible */}
      <div className="flex items-start justify-between border-b border-gray-800 px-8 py-4">
        <div className="flex items-center gap-3">
          <Brain className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-page-title">AI Performance</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* External Grafana Link */}
          <a
            href={`${grafanaUrl}/d/ai-services/ai-services?orgId=1`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="grafana-external-link"
          >
            <ExternalLink className="h-4 w-4" />
            Open in Grafana
          </a>

          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing || isLoading}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
            data-testid="ai-performance-refresh-button"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          className="mx-8 mt-4 flex items-center gap-3 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-4"
          data-testid="ai-performance-error"
        >
          <AlertCircle className="h-5 w-5 text-yellow-500" />
          <span className="text-sm text-yellow-200">{error}</span>
        </div>
      )}

      {/* Scrollable content area */}
      <div className="h-[calc(100vh-73px)] overflow-y-auto">
        {isLoading ? (
          /* Loading skeleton for content */
          <div className="p-8">
            <div className="h-[calc(100vh-200px)] animate-pulse rounded-lg bg-gray-800"></div>
          </div>
        ) : (
          <>
            {/* Model Zoo Section */}
            <ModelZooSection className="p-8" data-testid="ai-performance-model-zoo" />

            {/* Grafana iframe */}
            <div className="px-8 pb-8">
              <iframe
                ref={iframeRef}
                src={dashboardUrl}
                className="h-[600px] w-full rounded-lg border border-gray-800"
                title="AI Performance Dashboard"
                data-testid="grafana-iframe"
                onError={handleIframeError}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
