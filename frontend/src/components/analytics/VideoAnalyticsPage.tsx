/**
 * VideoAnalyticsPage - Video analytics dashboard via Grafana
 *
 * Embeds the Video Analytics dashboard for:
 * - Detection trends and patterns
 * - Object distribution analysis
 * - Risk score visualization
 * - Camera performance metrics
 */

import { Video, RefreshCw, ExternalLink, AlertCircle } from 'lucide-react';
import { useEffect, useState, useRef, useCallback } from 'react';

import { fetchConfig } from '../../services/api';
import { resolveGrafanaUrl } from '../../utils/grafanaUrl';

export default function VideoAnalyticsPage() {
  const [grafanaUrl, setGrafanaUrl] = useState<string>('/grafana');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Fetch Grafana URL from config
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

  // Handle refresh
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    if (iframeRef.current) {
      const currentSrc = iframeRef.current.src;
      iframeRef.current.src = '';
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

  // Construct Grafana Dashboard URL (Video Analytics dashboard)
  const getDashboardUrl = () => {
    return `${grafanaUrl}/d/video-analytics/video-analytics?orgId=1&kiosk=1&theme=dark&refresh=30s`;
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="video-analytics-loading">
        <div className="mx-auto max-w-[1920px]">
          <div className="mb-8">
            <div className="h-10 w-72 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800"></div>
          </div>
          <div className="h-[calc(100vh-200px)] animate-pulse rounded-lg bg-gray-800"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212]" data-testid="video-analytics-page">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-gray-800 px-8 py-4">
        <div className="flex items-center gap-3">
          <Video className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-page-title">Video Analytics</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* Open in Grafana */}
          <a
            href={`${grafanaUrl}/d/video-analytics/video-analytics?orgId=1&theme=dark`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="video-analytics-external-link"
          >
            <ExternalLink className="h-4 w-4" />
            Open in Grafana
          </a>

          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
            data-testid="video-analytics-refresh-button"
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
          data-testid="video-analytics-error"
        >
          <AlertCircle className="h-5 w-5 text-yellow-500" />
          <span className="text-sm text-yellow-200">{error}</span>
        </div>
      )}

      {/* Grafana Dashboard iframe */}
      <iframe
        ref={iframeRef}
        src={getDashboardUrl()}
        className="h-[calc(100vh-73px)] w-full border-0"
        title="Video Analytics"
        data-testid="video-analytics-iframe"
      />
    </div>
  );
}
