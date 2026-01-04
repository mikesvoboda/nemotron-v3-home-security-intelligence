/**
 * AIPerformancePage - Dedicated page for AI model performance metrics
 *
 * Consolidates all AI-related information including:
 * - Model status cards (RT-DETRv2, Nemotron)
 * - Latency metrics with percentiles
 * - Pipeline health (queues, errors, DLQ)
 * - Detection/event throughput statistics
 *
 * This page provides a focused view of AI performance separate from
 * the general System monitoring page.
 */

import { Text, Callout } from '@tremor/react';
import { Brain, RefreshCw, AlertCircle, ExternalLink, BarChart2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import InsightsCharts from './InsightsCharts';
import LatencyPanel from './LatencyPanel';
import ModelStatusCards from './ModelStatusCards';
import PipelineHealthPanel from './PipelineHealthPanel';
import { useAIMetrics } from '../../hooks/useAIMetrics';
import { fetchConfig } from '../../services/api';

/**
 * AIPerformancePage - Main AI performance dashboard
 */
export default function AIPerformancePage() {
  const { data, isLoading, error, refresh } = useAIMetrics({
    pollingInterval: 5000,
    enablePolling: true,
  });

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [grafanaUrl, setGrafanaUrl] = useState<string>('http://localhost:3002');

  // Fetch Grafana URL from config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await fetchConfig();
        const configWithGrafana = config as typeof config & { grafana_url?: string };
        if (configWithGrafana.grafana_url) {
          setGrafanaUrl(configWithGrafana.grafana_url);
        }
      } catch (err) {
        console.error('Failed to fetch config:', err);
      }
    };
    void loadConfig();
  }, []);

  // Handle manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refresh();
    setIsRefreshing(false);
  };

  // Loading state
  if (isLoading && !data.lastUpdated) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="ai-performance-loading">
        <div className="mx-auto max-w-[1920px]">
          {/* Header skeleton */}
          <div className="mb-8">
            <div className="h-10 w-72 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800"></div>
          </div>

          {/* Grid skeleton */}
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="h-48 animate-pulse rounded-lg bg-gray-800"></div>
              <div className="h-48 animate-pulse rounded-lg bg-gray-800"></div>
            </div>
            <div className="h-64 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="h-64 animate-pulse rounded-lg bg-gray-800"></div>
          </div>
        </div>
      </div>
    );
  }

  // Error state (but still show data if we have it)
  const hasData = data.lastUpdated !== null;

  return (
    <div className="min-h-screen bg-[#121212] p-8" data-testid="ai-performance-page">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-8 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Brain className="h-8 w-8 text-[#76B900]" />
              <h1 className="text-4xl font-bold text-white">AI Performance</h1>
            </div>
            <p className="mt-2 text-sm text-gray-400">
              Real-time AI model metrics, latency statistics, and pipeline health
            </p>
          </div>

          {/* Refresh Button */}
          <button
            onClick={() => void handleRefresh()}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
            data-testid="refresh-button"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Grafana Link Banner */}
        <Callout
          title="Detailed Metrics Available"
          icon={BarChart2}
          color="blue"
          className="mb-6"
          data-testid="grafana-banner"
        >
          <span className="inline-flex flex-wrap items-center gap-2">
            <span>
              View detailed AI metrics, historical trends, and GPU utilization in Grafana.
            </span>
            <a
              href={`${grafanaUrl}/d/ai-performance`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
              data-testid="grafana-link"
            >
              Open Grafana
              <ExternalLink className="h-4 w-4" />
            </a>
          </span>
        </Callout>

        {/* Error Banner (if error but still have cached data) */}
        {error && hasData && (
          <Callout
            title="Update Failed"
            icon={AlertCircle}
            color="yellow"
            className="mb-6"
            data-testid="error-banner"
          >
            <span className="text-sm">
              {error}. Showing cached data from{' '}
              {data.lastUpdated ? new Date(data.lastUpdated).toLocaleTimeString() : 'earlier'}.
            </span>
          </Callout>
        )}

        {/* Error state (no cached data) */}
        {error && !hasData && (
          <div className="flex flex-col items-center justify-center rounded-lg border border-red-500/20 bg-red-500/10 p-12">
            <AlertCircle className="mb-4 h-12 w-12 text-red-500" />
            <h2 className="mb-2 text-xl font-bold text-red-500">Failed to Load AI Metrics</h2>
            <p className="mb-4 text-sm text-gray-300">{error}</p>
            <button
              onClick={() => void handleRefresh()}
              className="rounded-md bg-red-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Main Content */}
        {hasData && (
          <div className="space-y-6">
            {/* Model Status Cards */}
            <ModelStatusCards
              rtdetr={data.rtdetr}
              nemotron={data.nemotron}
              detectionLatency={data.detectionLatency}
              analysisLatency={data.analysisLatency}
            />

            {/* Latency Panel */}
            <LatencyPanel
              detectionLatency={data.detectionLatency}
              analysisLatency={data.analysisLatency}
              pipelineLatency={data.pipelineLatency}
            />

            {/* Pipeline Health Panel */}
            <PipelineHealthPanel
              detectionQueueDepth={data.detectionQueueDepth}
              analysisQueueDepth={data.analysisQueueDepth}
              totalDetections={data.totalDetections}
              totalEvents={data.totalEvents}
              pipelineErrors={data.pipelineErrors}
              queueOverflows={data.queueOverflows}
              dlqItems={data.dlqItems}
            />

            {/* Insights Charts */}
            <InsightsCharts
              totalDetections={data.totalDetections}
            />

            {/* Last Updated */}
            {data.lastUpdated && (
              <Text className="text-center text-xs text-gray-500">
                Last updated: {new Date(data.lastUpdated).toLocaleString()}
              </Text>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
