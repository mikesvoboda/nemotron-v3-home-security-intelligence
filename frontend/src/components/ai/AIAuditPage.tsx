/**
 * AIAuditPage - Dashboard for AI quality metrics and recommendations
 *
 * Provides a tabbed interface for:
 * - Dashboard: Quality score metrics and trends
 * - Prompt Playground: Edit and test AI prompts
 * - Batch Audit: Trigger batch processing
 * - Version History: View and restore prompt versions
 *
 * Note: Model contribution rates and leaderboard are now on the AI Performance page
 */

import { Tab } from '@headlessui/react';
import { Text, Callout, Select, SelectItem } from '@tremor/react';
import { clsx } from 'clsx';
import {
  AlertCircle,
  Calendar,
  ClipboardCheck,
  History,
  LayoutDashboard,
  Play,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { Fragment, useEffect, useState, useCallback } from 'react';

import BatchAuditModal from './BatchAuditModal';
import PromptPlayground from './PromptPlayground';
import { ChartSkeleton, StatsCardSkeleton, Skeleton } from '../common';
import QualityScoreTrends from './QualityScoreTrends';
import RecommendationsPanel from './RecommendationsPanel';
import {
  fetchAiAuditStats,
  fetchAuditRecommendations,
} from '../../services/api';
import { ModelContributionChart, PromptVersionHistory } from '../ai-audit';

import type {
  AiAuditStatsResponse,
  AiAuditRecommendationsResponse,
  AiAuditRecommendationItem,
} from '../../services/api';
import type { BatchAuditResponse } from '../../services/auditApi';
import type { ModelContribution } from '../ai-audit';

/**
 * Format model names for display
 */
function formatModelName(name: string): string {
  const nameMap: Record<string, string> = {
    rtdetr: 'RT-DETRv2',
    florence: 'Florence-2',
    clip: 'X-CLIP',
    violence: 'Violence Detection',
    clothing: 'Clothing Analysis',
    vehicle: 'Vehicle Detection',
    pet: 'Pet Detection',
    weather: 'Weather Analysis',
    image_quality: 'Image Quality',
    zones: 'Zone Analysis',
    baseline: 'Baseline Comparison',
    cross_camera: 'Cross-Camera',
  };
  return nameMap[name] || name;
}

/**
 * Tab configuration
 */
const TABS = [
  {
    id: 'dashboard',
    name: 'Dashboard',
    icon: LayoutDashboard,
  },
  {
    id: 'playground',
    name: 'Prompt Playground',
    icon: Sparkles,
  },
  {
    id: 'batch',
    name: 'Batch Audit',
    icon: Play,
  },
  {
    id: 'history',
    name: 'Version History',
    icon: History,
  },
] as const;

/**
 * AIAuditPage - Main AI audit dashboard with tabbed interface
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
  const [selectedTabIndex, setSelectedTabIndex] = useState(0);

  // Batch audit modal state
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [batchSuccess, setBatchSuccess] = useState<string | null>(null);

  // Prompt playground state
  const [isPlaygroundOpen, setIsPlaygroundOpen] = useState(false);
  const [selectedRecommendation, setSelectedRecommendation] = useState<AiAuditRecommendationItem | null>(null);

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

  // Handle recommendation explore click
  const handleExploreRecommendation = (recommendation: AiAuditRecommendationItem) => {
    setSelectedRecommendation(recommendation);
    setIsPlaygroundOpen(true);
  };

  // Handle playground open
  const handleOpenPlayground = () => {
    setSelectedRecommendation(null);
    setIsPlaygroundOpen(true);
  };

  // Handle playground close
  const handleClosePlayground = () => {
    setIsPlaygroundOpen(false);
    setSelectedRecommendation(null);
  };

  // Handle tab change
  const handleTabChange = (index: number) => {
    setSelectedTabIndex(index);
  };

  // Loading state with skeleton loaders
  if (isLoading && !stats) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="ai-audit-loading">
        <div className="mx-auto max-w-[1920px]">
          {/* Header skeleton */}
          <div className="mb-8">
            <div className="flex items-center gap-3 mb-2">
              <Skeleton variant="circular" width={32} height={32} />
              <Skeleton variant="text" width={288} height={40} />
            </div>
            <Skeleton variant="text" width={384} height={20} />
          </div>

          {/* Quality Score Metrics skeleton */}
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {[1, 2, 3, 4].map((i) => (
                <StatsCardSkeleton key={i} />
              ))}
            </div>

            {/* Charts skeleton */}
            <div className="grid gap-4 lg:grid-cols-2">
              <ChartSkeleton height={320} />
              <ChartSkeleton height={320} />
            </div>

            {/* Recommendations Panel skeleton */}
            <div className="rounded-lg border border-gray-800 bg-[#1F1F1F] p-6">
              <Skeleton variant="text" width={200} height={24} className="mb-4" />
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-start gap-4 p-4 rounded-lg bg-gray-800/30">
                    <Skeleton variant="circular" width={40} height={40} />
                    <div className="flex-1 space-y-2">
                      <Skeleton variant="text" width="80%" height={20} />
                      <Skeleton variant="text" width="60%" height={16} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
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
              className="rounded-md bg-red-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-800"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const hasData = stats !== null && stats.audited_events > 0;

  // Transform model contribution rates to ModelContribution format
  const modelContributions: ModelContribution[] = stats
    ? Object.entries(stats.model_contribution_rates).map(([modelName, rate]) => ({
        modelName: formatModelName(modelName),
        rate,
        eventCount: Math.round(rate * stats.audited_events),
      }))
    : [];

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

            {/* Refresh Button */}
            <button
              onClick={() => void handleRefresh()}
              disabled={isRefreshing}
              className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
              data-testid="ai-audit-refresh-button"
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

        {/* Main Content - No Data State */}
        {!hasData && (
          <div className="flex flex-col items-center justify-center rounded-lg border border-gray-800 bg-[#1F1F1F] p-12 text-center">
            <ClipboardCheck className="mb-4 h-16 w-16 text-gray-600" />
            <h2 className="mb-2 text-2xl font-bold text-white">No Events Have Been Audited Yet</h2>
            <p className="mb-6 max-w-md text-sm text-gray-400">
              Start by triggering a batch audit to evaluate your AI pipeline&apos;s performance.
              The audit will analyze model contributions, quality scores, and provide prompt
              improvement recommendations.
            </p>
            <button
              onClick={() => setIsBatchModalOpen(true)}
              className="flex items-center gap-2 rounded-lg bg-[#76B900] px-6 py-3 text-sm font-semibold text-black transition-colors hover:bg-[#8ACE00]"
            >
              <Play className="h-5 w-5" />
              Trigger Batch Audit
            </button>
          </div>
        )}

        {/* Main Content - Tabbed Interface */}
        {hasData && stats && (
          <Tab.Group selectedIndex={selectedTabIndex} onChange={handleTabChange}>
            {/* Tab List */}
            <Tab.List
              className="mb-6 flex space-x-1 rounded-lg border border-gray-800 bg-[#1A1A1A] p-1"
              data-testid="ai-audit-tabs"
            >
              {TABS.map((tab) => {
                const Icon = tab.icon;
                return (
                  <Tab key={tab.id} as={Fragment}>
                    {({ selected }) => (
                      <button
                        className={clsx(
                          'flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-200',
                          'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                          selected
                            ? 'bg-[#76B900] text-gray-950 shadow-md'
                            : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                        )}
                        data-testid={`tab-${tab.id}`}
                      >
                        <Icon className="h-4 w-4" aria-hidden="true" />
                        <span>{tab.name}</span>
                      </button>
                    )}
                  </Tab>
                );
              })}
            </Tab.List>

            {/* Tab Panels */}
            <Tab.Panels>
              {/* Dashboard Tab */}
              <Tab.Panel
                className="focus:outline-none"
                data-testid="tab-panel-dashboard"
              >
                <div className="space-y-6">
                  {/* Quality Score Metrics */}
                  <QualityScoreTrends
                    avgQualityScore={stats.avg_quality_score}
                    avgConsistencyRate={stats.avg_consistency_rate}
                    avgEnrichmentUtilization={stats.avg_enrichment_utilization}
                    totalEvents={stats.total_events}
                    fullyEvaluatedEvents={stats.fully_evaluated_events}
                  />

                  {/* Model Contribution Breakdown */}
                  {modelContributions.length > 0 && (
                    <ModelContributionChart contributions={modelContributions} />
                  )}

                  {/* Recommendations Panel (full width) */}
                  {recommendations && (
                    <RecommendationsPanel
                      recommendations={recommendations.recommendations}
                      totalEventsAnalyzed={recommendations.total_events_analyzed}
                      onExploreRecommendation={handleExploreRecommendation}
                    />
                  )}

                  {/* Last Updated */}
                  <Text className="text-center text-xs text-gray-500">
                    Showing data from the last {periodDays} days
                  </Text>
                </div>
              </Tab.Panel>

              {/* Prompt Playground Tab */}
              <Tab.Panel
                className="focus:outline-none"
                data-testid="tab-panel-playground"
              >
                <div className="rounded-lg border border-gray-800 bg-[#1A1A1A] p-8">
                  <div className="mx-auto max-w-2xl text-center">
                    <Sparkles className="mx-auto mb-4 h-16 w-16 text-[#76B900]" />
                    <h2 className="mb-4 text-2xl font-bold text-white">Prompt Playground</h2>
                    <p className="mb-6 text-gray-400">
                      Edit, test, and refine AI model prompts. Experiment with different configurations,
                      run A/B tests against real events, and save successful changes.
                    </p>
                    <button
                      onClick={handleOpenPlayground}
                      className="flex items-center gap-2 mx-auto rounded-lg bg-[#76B900] px-6 py-3 text-sm font-semibold text-black transition-colors hover:bg-[#8ACE00]"
                      data-testid="open-playground-button"
                    >
                      <Sparkles className="h-5 w-5" />
                      Open Prompt Playground
                    </button>

                    {/* Feature Highlights */}
                    <div className="mt-8 grid gap-4 sm:grid-cols-3 text-left">
                      <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                        <h3 className="font-semibold text-white mb-2">Model Editors</h3>
                        <p className="text-sm text-gray-400">
                          Edit prompts for Nemotron, Florence-2, YOLO-World, X-CLIP, and Fashion-CLIP models.
                        </p>
                      </div>
                      <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                        <h3 className="font-semibold text-white mb-2">A/B Testing</h3>
                        <p className="text-sm text-gray-400">
                          Test modified prompts against real events and compare results before saving.
                        </p>
                      </div>
                      <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                        <h3 className="font-semibold text-white mb-2">Import/Export</h3>
                        <p className="text-sm text-gray-400">
                          Export configurations for backup or import from other instances.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </Tab.Panel>

              {/* Batch Audit Tab */}
              <Tab.Panel
                className="focus:outline-none"
                data-testid="tab-panel-batch"
              >
                <div className="rounded-lg border border-gray-800 bg-[#1A1A1A] p-8">
                  <div className="mx-auto max-w-2xl text-center">
                    <Play className="mx-auto mb-4 h-16 w-16 text-[#76B900]" />
                    <h2 className="mb-4 text-2xl font-bold text-white">Batch Audit Processing</h2>
                    <p className="mb-6 text-gray-400">
                      Queue multiple events for AI self-evaluation. Configure the limit, minimum
                      risk score filter, and whether to re-evaluate already processed events.
                    </p>
                    <button
                      onClick={() => setIsBatchModalOpen(true)}
                      className="flex items-center gap-2 mx-auto rounded-lg bg-[#76B900] px-6 py-3 text-sm font-semibold text-black transition-colors hover:bg-[#8ACE00]"
                      data-testid="trigger-batch-audit-button"
                    >
                      <Play className="h-5 w-5" />
                      Trigger Batch Audit
                    </button>

                    {/* Recent Batch Stats */}
                    <div className="mt-8 grid gap-4 sm:grid-cols-3">
                      <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                        <p className="text-2xl font-bold text-white">
                          {stats.total_events.toLocaleString()}
                        </p>
                        <p className="text-sm text-gray-400">Total Events</p>
                      </div>
                      <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                        <p className="text-2xl font-bold text-white">
                          {stats.audited_events.toLocaleString()}
                        </p>
                        <p className="text-sm text-gray-400">Audited Events</p>
                      </div>
                      <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                        <p className="text-2xl font-bold text-white">
                          {stats.fully_evaluated_events.toLocaleString()}
                        </p>
                        <p className="text-sm text-gray-400">Fully Evaluated</p>
                      </div>
                    </div>
                  </div>
                </div>
              </Tab.Panel>

              {/* Version History Tab */}
              <Tab.Panel
                className="focus:outline-none"
                data-testid="tab-panel-history"
              >
                <PromptVersionHistory periodDays={periodDays} />
              </Tab.Panel>
            </Tab.Panels>
          </Tab.Group>
        )}
      </div>

      {/* Batch Audit Modal */}
      <BatchAuditModal
        isOpen={isBatchModalOpen}
        onClose={() => setIsBatchModalOpen(false)}
        onSuccess={handleBatchAuditSuccess}
      />

      {/* Prompt Playground Slide-out Panel */}
      <PromptPlayground
        isOpen={isPlaygroundOpen}
        onClose={handleClosePlayground}
        recommendation={selectedRecommendation}
      />
    </div>
  );
}
