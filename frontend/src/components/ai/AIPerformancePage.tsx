/**
 * AIPerformancePage - Dedicated page for AI model performance metrics
 *
 * Consolidates all AI-related information including:
 * - Summary row with 5 key indicators (RT-DETRv2, Nemotron, Queues, Throughput, Errors)
 * - Pipeline Performance section with latency charts and distribution panels
 * - AI Models section with Model Zoo grid, contribution rates, and leaderboard
 * - Recent Activity section with detections table
 *
 * Layout follows the design spec in docs/plans/2026-01-04-ai-performance-page-redesign.md
 *
 * This page provides a focused view of AI performance separate from
 * the general System monitoring page.
 */

import { Text, Callout, Title } from '@tremor/react';
import { Brain, RefreshCw, AlertCircle, ExternalLink, BarChart2, TrendingUp, Boxes } from 'lucide-react';
import { useEffect, useState, useCallback, useRef } from 'react';

import InsightsCharts from './InsightsCharts';
import LatencyPanel from './LatencyPanel';
import ModelContributionChart from './ModelContributionChart';
import ModelLeaderboard from './ModelLeaderboard';
import ModelZooSection from './ModelZooSection';
import PipelineHealthPanel from './PipelineHealthPanel';
import { useAIMetrics } from '../../hooks/useAIMetrics';
import {
  fetchConfig,
  fetchAiAuditStats,
  fetchModelLeaderboard,
} from '../../services/api';
import AIPerformanceSummaryRow from '../ai-performance/AIPerformanceSummaryRow';

import type {
  AiAuditStatsResponse,
  AiAuditLeaderboardResponse,
} from '../../services/api';
import type { SectionRefs, IndicatorType } from '../ai-performance/AIPerformanceSummaryRow';

/**
 * Calculate total errors from pipeline errors, queue overflows, and DLQ items
 */
function calculateTotalErrors(
  pipelineErrors: Record<string, number>,
  queueOverflows: Record<string, number>,
  dlqItems: Record<string, number>
): number {
  const pipelineTotal = Object.values(pipelineErrors).reduce((sum, count) => sum + count, 0);
  const overflowTotal = Object.values(queueOverflows).reduce((sum, count) => sum + count, 0);
  const dlqTotal = Object.values(dlqItems).reduce((sum, count) => sum + count, 0);
  return pipelineTotal + overflowTotal + dlqTotal;
}

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

  // Model Zoo data state
  const [auditStats, setAuditStats] = useState<AiAuditStatsResponse | null>(null);
  const [leaderboard, setLeaderboard] = useState<AiAuditLeaderboardResponse | null>(null);

  // Section refs for scroll-to behavior from Summary Row
  const pipelinePerformanceRef = useRef<HTMLElement>(null);
  const aiModelsRef = useRef<HTMLElement>(null);
  const queuesRef = useRef<HTMLElement>(null);
  const errorsRef = useRef<HTMLElement>(null);

  // Build section refs object for Summary Row
  const sectionRefs: SectionRefs = {
    rtdetr: pipelinePerformanceRef,
    nemotron: pipelinePerformanceRef,
    queues: queuesRef,
    throughput: pipelinePerformanceRef,
    errors: errorsRef,
  };

  // Handle indicator click for analytics tracking
  const handleIndicatorClick = useCallback((_indicator: IndicatorType) => {
    // Could add analytics tracking here in the future
  }, []);

  // Load Model Zoo data (contribution rates and leaderboard)
  const loadModelZooData = useCallback(async () => {
    try {
      const [statsData, leaderboardData] = await Promise.all([
        fetchAiAuditStats({ days: 7 }),
        fetchModelLeaderboard({ days: 7 }),
      ]);
      setAuditStats(statsData);
      setLeaderboard(leaderboardData);
    } catch (err) {
      console.error('Failed to fetch Model Zoo data:', err);
    }
  }, []);

  // Fetch Grafana URL from config and Model Zoo data
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
    void loadModelZooData();
  }, [loadModelZooData]);

  // Handle manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await Promise.all([refresh(), loadModelZooData()]);
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
          <div className="space-y-8">
            {/* ============================================================
                SUMMARY ROW - Key Indicators (5 cards above the fold)
                Click any indicator to scroll to relevant section
                ============================================================ */}
            <AIPerformanceSummaryRow
              rtdetr={data.rtdetr}
              nemotron={data.nemotron}
              detectionLatency={data.detectionLatency}
              analysisLatency={data.analysisLatency}
              detectionQueueDepth={data.detectionQueueDepth}
              analysisQueueDepth={data.analysisQueueDepth}
              totalDetections={data.totalDetections}
              totalEvents={data.totalEvents}
              totalErrors={calculateTotalErrors(data.pipelineErrors, data.queueOverflows, data.dlqItems)}
              sectionRefs={sectionRefs}
              onIndicatorClick={handleIndicatorClick}
            />

            {/* ============================================================
                PIPELINE PERFORMANCE SECTION
                - Latency Over Time (full width)
                - Detection Class Distribution + Risk Score Distribution
                ============================================================ */}
            <section
              ref={pipelinePerformanceRef as React.RefObject<HTMLDivElement>}
              data-testid="pipeline-performance-section"
              aria-labelledby="pipeline-performance-heading"
            >
              <div className="mb-4 flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-[#76B900]" />
                <Title id="pipeline-performance-heading" className="text-white">
                  Pipeline Performance
                </Title>
              </div>

              <div className="space-y-6">
                {/* Latency Panel - Full width */}
                <LatencyPanel
                  detectionLatency={data.detectionLatency}
                  analysisLatency={data.analysisLatency}
                  pipelineLatency={data.pipelineLatency}
                />

                {/* Distribution Charts - Two columns */}
                <InsightsCharts
                  detectionsByClass={data.detectionsByClass}
                  totalDetections={data.totalDetections}
                />
              </div>
            </section>

            {/* ============================================================
                AI MODELS SECTION
                - Model Zoo Grid (active models with Show All toggle)
                - Model Contribution Rates + Model Leaderboard
                ============================================================ */}
            <section
              ref={aiModelsRef as React.RefObject<HTMLDivElement>}
              data-testid="ai-models-section"
              aria-labelledby="ai-models-heading"
            >
              <div className="mb-4 flex items-center gap-2">
                <Boxes className="h-5 w-5 text-[#76B900]" />
                <Title id="ai-models-heading" className="text-white">
                  AI Models
                </Title>
              </div>

              <div className="space-y-6">
                {/* Model Zoo Grid - Shows active/loading models, expandable to all 18 */}
                <ModelZooSection />

                {/* Model Zoo Analytics - Contribution Rates + Leaderboard */}
                <div data-testid="model-zoo-analytics-section" className="grid gap-6 lg:grid-cols-2">
                  {/* Model Contribution Chart */}
                  {auditStats && (
                    <ModelContributionChart contributionRates={auditStats.model_contribution_rates} />
                  )}

                  {/* Model Leaderboard */}
                  {leaderboard && (
                    <ModelLeaderboard
                      entries={leaderboard.entries}
                      periodDays={leaderboard.period_days}
                    />
                  )}
                </div>
              </div>
            </section>

            {/* ============================================================
                QUEUE & ERROR HEALTH SECTION
                - Queue Depths (Detection, Analysis, DLQ)
                - Throughput Statistics
                - Pipeline Errors
                ============================================================ */}
            <section
              ref={queuesRef as React.RefObject<HTMLDivElement>}
              data-testid="queue-health-section"
              aria-labelledby="queue-health-heading"
            >
              <PipelineHealthPanel
                detectionQueueDepth={data.detectionQueueDepth}
                analysisQueueDepth={data.analysisQueueDepth}
                totalDetections={data.totalDetections}
                totalEvents={data.totalEvents}
                pipelineErrors={data.pipelineErrors}
                queueOverflows={data.queueOverflows}
                dlqItems={data.dlqItems}
              />
            </section>

            {/* Hidden error ref target (errors shown in PipelineHealthPanel) */}
            <div ref={errorsRef as React.RefObject<HTMLDivElement>} className="sr-only" aria-hidden="true" />

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
