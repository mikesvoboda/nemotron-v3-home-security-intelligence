/**
 * AI Performance Page Components
 *
 * Components for displaying AI model metrics, latency statistics,
 * and pipeline health on the /ai page.
 */

export { default as AIPerformancePage } from './AIPerformancePage';
export { default as ModelStatusCards } from './ModelStatusCards';
export { default as LatencyPanel } from './LatencyPanel';
export { default as PipelineHealthPanel } from './PipelineHealthPanel';
export { default as InsightsCharts } from './InsightsCharts';

export type { ModelStatusCardsProps } from './ModelStatusCards';
export type { LatencyPanelProps } from './LatencyPanel';
export type { PipelineHealthPanelProps } from './PipelineHealthPanel';
export type { InsightsChartsProps } from './InsightsCharts';
