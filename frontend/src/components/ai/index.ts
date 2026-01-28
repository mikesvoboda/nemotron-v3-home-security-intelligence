/**
 * AI Performance Page Components
 *
 * Components for displaying AI model metrics, latency statistics,
 * and pipeline health on the /ai page.
 */

export { default as AIPerformancePage } from './AIPerformancePage';
export { default as AIServicesPage } from './AIServicesPage';
export { default as ModelStatusCards } from './ModelStatusCards';
export { default as LatencyPanel } from './LatencyPanel';
export { default as PipelineHealthPanel } from './PipelineHealthPanel';
export { default as InsightsCharts } from './InsightsCharts';
export { default as ModelZooSection } from './ModelZooSection';

export type { ModelStatusCardsProps } from './ModelStatusCards';
export type { LatencyPanelProps } from './LatencyPanel';
export type { PipelineHealthPanelProps } from './PipelineHealthPanel';
export type { InsightsChartsProps } from './InsightsCharts';
export type { ModelZooSectionProps } from './ModelZooSection';

/**
 * AI Audit Dashboard Components
 *
 * Components for displaying AI model audit metrics, quality scores,
 * model leaderboard, and prompt improvement recommendations.
 */

export { default as AIAuditPage } from './AIAuditPage';
export { default as BatchAuditModal } from './BatchAuditModal';
export { default as ModelContributionChart } from './ModelContributionChart';
export { default as QualityScoreTrends } from './QualityScoreTrends';
export { default as ModelLeaderboard } from './ModelLeaderboard';
export { default as RecommendationsPanel } from './RecommendationsPanel';
export { default as SuggestionDiffView } from './SuggestionDiffView';
export { default as SuggestionExplanation } from './SuggestionExplanation';
export { default as PromptABTest } from './PromptABTest';
export { default as ABTestStats, calculateStats } from './ABTestStats';

export type { BatchAuditModalProps } from './BatchAuditModal';
export type { ModelContributionChartProps } from './ModelContributionChart';
export type { QualityScoreTrendsProps } from './QualityScoreTrends';
export type { ModelLeaderboardProps } from './ModelLeaderboard';
export type { RecommendationsPanelProps } from './RecommendationsPanel';
export type { SuggestionDiffViewProps, DiffLine } from './SuggestionDiffView';
export type { SuggestionExplanationProps } from './SuggestionExplanation';
export type { PromptABTestProps } from './PromptABTest';
export type { ABTestStatsProps, AggregateStats } from './ABTestStats';
