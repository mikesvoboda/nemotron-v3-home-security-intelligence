/**
 * AIAuditPage - Dashboard for AI quality metrics and recommendations
 *
 * Displays aggregate statistics from the AI pipeline audit system including:
 * - Quality score metrics and trends
 * - Prompt improvement recommendations
 *
 * Note: Model contribution rates and leaderboard are now on the AI Performance page
 */

import { Text, Callout, Select, SelectItem } from '@tremor/react';
import { ClipboardCheck, RefreshCw, AlertCircle, Calendar, Play } from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import BatchAuditModal from './BatchAuditModal';
import QualityScoreTrends from './QualityScoreTrends';
import RecommendationsPanel from './RecommendationsPanel';
import {
  fetchAiAuditStats,
  fetchAuditRecommendations,
} from '../../services/api';

import type {
  AiAuditStatsResponse,
  AiAuditRecommendationsResponse,
} from '../../services/api';
import type { BatchAuditResponse } from '../../services/auditApi';

/**
 * AIAuditPage - Main AI audit dashboard
 */
export default function AIAuditPage() {
  // Data state
  const [stats, setStats] = useState<AiAuditStatsResponse | null>(null);
  const [recommendations, setRecommendations] = useState<AiAuditRecommendationsResponse | null>(
    null
  );

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [periodDays, setPeriodDays] = useState(7);

  // Batch audit modal state
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [batchSuccess, setBatchSuccess] = useState<string | null>(null);

  // Load data
  const loadData = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);

    try {
      const [statsData, recommendationsData] = await Promise.all([
        fetchAiAuditStats({ days: periodDays }),
        fetchAuditRecommendations({ days: periodDays }),
      ]);

      setStats(statsData);
      setRecommendations(recommendationsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load AI audit data');
      console.error('Failed to fetch AI audit data:', err);
    } finally {
      setIsLoading(false);
    }
  }, [periodDays]);

  // Initial load and period change
  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Handle manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadData(false);
    setIsRefreshing(false);
  };

  // Handle period change
  const handlePeriodChange = (value: string) => {
    setPeriodDays(parseInt(value, 10));
  };

  // Handle batch audit success
  const handleBatchAuditSuccess = (response: BatchAuditResponse) => {
    setBatchSuccess(`Queued ${response.queued_count} events for evaluation`);
    // Auto-dismiss success message after 5 seconds
    setTimeout(() => setBatchSuccess(null), 5000);
    // Refresh data to show updated stats
    void loadData(false);
  };

  // Loading state
  if (isLoading && !stats) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="ai-audit-loading">
        <div className="mx-auto max-w-[1920px]">
          {/* Header skeleton */}
          <div className="mb-8">
            <div className="h-10 w-72 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800"></div>
          </div>

          {/* Grid skeleton */}
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-32 animate-pulse rounded-lg bg-gray-800"></div>
              ))}
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="h-80 animate-pulse rounded-lg bg-gray-800"></div>
              <div className="h-80 animate-pulse rounded-lg bg-gray-800"></div>
            </div>
            <div className="h-64 animate-pulse rounded-lg bg-gray-800"></div>
          </div>
        </div>
      </div>
    );
  }

  // Error state (no cached data)
  if (error && !stats) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="ai-audit-error">
        <div className="mx-auto max-w-[1920px]">
          <div className="flex flex-col items-center justify-center rounded-lg border border-red-500/20 bg-red-500/10 p-12">
            <AlertCircle className="mb-4 h-12 w-12 text-red-500" />
            <h2 className="mb-2 text-xl font-bold text-red-500">Failed to Load AI Audit Data</h2>
            <p className="mb-4 text-sm text-gray-300">{error}</p>
            <button
              onClick={() => void handleRefresh()}
              className="rounded-md bg-red-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const hasData = stats !== null;

  return (
    <div className="min-h-screen bg-[#121212] p-8" data-testid="ai-audit-page">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <ClipboardCheck className="h-8 w-8 text-[#76B900]" />
              <h1 className="text-4xl font-bold text-white">AI Audit Dashboard</h1>
            </div>
            <p className="mt-2 text-sm text-gray-400">
              Model contribution rates, quality metrics, and prompt improvement recommendations
            </p>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-3">
            {/* Period Selector */}
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-gray-400" />
              <Select
                value={String(periodDays)}
                onValueChange={handlePeriodChange}
                className="w-32"
                data-testid="period-selector"
              >
                <SelectItem value="1">Last 24h</SelectItem>
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="14">Last 14 days</SelectItem>
                <SelectItem value="30">Last 30 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
              </Select>
            </div>

            {/* Trigger Batch Audit Button */}
            <button
              onClick={() => setIsBatchModalOpen(true)}
              className="flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-[#8ACE00]"
              data-testid="trigger-batch-audit-button"
            >
              <Play className="h-4 w-4" />
              Trigger Batch Audit
            </button>

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
        </div>

        {/* Error Banner (if error but still have cached data) */}
        {error && hasData && (
          <Callout
            title="Update Failed"
            icon={AlertCircle}
            color="yellow"
            className="mb-6"
            data-testid="error-banner"
          >
            <span className="text-sm">{error}. Showing cached data.</span>
          </Callout>
        )}

        {/* Success Banner (for batch audit) */}
        {batchSuccess && (
          <Callout
            title="Batch Audit Started"
            icon={Play}
            color="green"
            className="mb-6"
            data-testid="batch-success-banner"
          >
            <span className="text-sm">{batchSuccess}</span>
          </Callout>
        )}

        {/* Main Content */}
        {hasData && (
          <div className="space-y-6">
            {/* Quality Score Metrics */}
            <QualityScoreTrends
              avgQualityScore={stats.avg_quality_score}
              avgConsistencyRate={stats.avg_consistency_rate}
              avgEnrichmentUtilization={stats.avg_enrichment_utilization}
              totalEvents={stats.total_events}
              fullyEvaluatedEvents={stats.fully_evaluated_events}
            />

            {/* Recommendations Panel (full width) */}
            {recommendations && (
              <RecommendationsPanel
                recommendations={recommendations.recommendations}
                totalEventsAnalyzed={recommendations.total_events_analyzed}
              />
            )}

            {/* Last Updated */}
            <Text className="text-center text-xs text-gray-500">
              Showing data from the last {periodDays} days
            </Text>
          </div>
        )}
      </div>

      {/* Batch Audit Modal */}
      <BatchAuditModal
        isOpen={isBatchModalOpen}
        onClose={() => setIsBatchModalOpen(false)}
        onSuccess={handleBatchAuditSuccess}
      />
    </div>
  );
}
