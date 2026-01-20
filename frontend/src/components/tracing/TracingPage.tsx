/**
 * TracingPage - Distributed tracing dashboard via Grafana/Jaeger
 *
 * Embeds Grafana's Explore view with Jaeger datasource for:
 * - Trace search and visualization
 * - Service dependency graphs
 * - Trace comparison (split view)
 * - Correlation to metrics
 */

import { Activity, RefreshCw, ExternalLink, AlertCircle, SplitSquareHorizontal } from 'lucide-react';
import { useEffect, useState, useRef, useCallback } from 'react';

import { fetchConfig } from '../../services/api';
import { resolveGrafanaUrl } from '../../utils/grafanaUrl';

export default function TracingPage() {
  const [grafanaUrl, setGrafanaUrl] = useState<string>('/grafana');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [viewMode, setViewMode] = useState<'search' | 'dependencies'>('search');
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

  // Construct Grafana Explore URL
  const getExploreUrl = () => {
    const baseParams = 'orgId=1&kiosk=1&theme=dark';
    const jaegerQuery = encodeURIComponent(JSON.stringify({
      datasource: 'Jaeger',
      queries: [{
        refId: 'A',
        queryType: viewMode === 'search' ? 'search' : 'dependencyGraph',
        service: 'nemotron-backend'
      }]
    }));
    return `${grafanaUrl}/explore?${baseParams}&left=${jaegerQuery}`;
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="tracing-loading">
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
    <div className="min-h-screen bg-[#121212]" data-testid="tracing-page">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-gray-800 px-8 py-4">
        <div className="flex items-center gap-3">
          <Activity className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-page-title">Distributed Tracing</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div className="flex rounded-lg bg-gray-800 p-1">
            <button
              onClick={() => setViewMode('search')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === 'search'
                  ? 'bg-[#76B900] text-black'
                  : 'text-gray-400 hover:text-white'
              }`}
              data-testid="view-mode-search"
            >
              Trace Search
            </button>
            <button
              onClick={() => setViewMode('dependencies')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === 'dependencies'
                  ? 'bg-[#76B900] text-black'
                  : 'text-gray-400 hover:text-white'
              }`}
              data-testid="view-mode-dependencies"
            >
              Service Map
            </button>
          </div>

          {/* Compare Traces */}
          <a
            href={`${grafanaUrl}/explore?orgId=1&theme=dark&split=true`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="compare-traces-link"
          >
            <SplitSquareHorizontal className="h-4 w-4" />
            Compare Traces
          </a>

          {/* Open Jaeger */}
          <a
            href="http://localhost:16686"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="jaeger-external-link"
          >
            <ExternalLink className="h-4 w-4" />
            Open Jaeger
          </a>

          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
            data-testid="tracing-refresh-button"
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
          data-testid="tracing-error"
        >
          <AlertCircle className="h-5 w-5 text-yellow-500" />
          <span className="text-sm text-yellow-200">{error}</span>
        </div>
      )}

      {/* Grafana iframe */}
      <iframe
        ref={iframeRef}
        src={getExploreUrl()}
        className="h-[calc(100vh-73px)] w-full border-0"
        title="Distributed Tracing"
        data-testid="tracing-iframe"
      />
    </div>
  );
}
