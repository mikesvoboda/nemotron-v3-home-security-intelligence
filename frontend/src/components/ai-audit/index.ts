/**
 * AI Audit Components Barrel Export
 *
 * This file exports all components related to AI audit functionality.
 */

export { default as AIAuditDashboard } from './AIAuditDashboard';
export type { AIAuditDashboardProps } from './AIAuditDashboard';

export { default as AuditProgressBar } from './AuditProgressBar';
export type { AuditProgressBarProps } from './AuditProgressBar';

export { default as AuditResultsTable } from './AuditResultsTable';
export type { AuditResultsTableProps, AuditResult } from './AuditResultsTable';

export { default as ModelContributionChart } from './ModelContributionChart';
export type { ModelContributionChartProps, ModelContribution } from './ModelContributionChart';

export { default as PromptVersionHistory } from './PromptVersionHistory';
export type { PromptVersionHistoryProps } from './PromptVersionHistory';

// Re-export PromptPlayground from ai/ directory for use in ai-audit context
// The PromptPlayground component provides A/B testing, prompt editing, and version management
export { default as PromptPlayground } from '../ai/PromptPlayground';
export type { PromptPlaygroundProps } from '../ai/PromptPlayground';

// Re-export related A/B testing components
export { default as PromptABTest } from '../ai/PromptABTest';
export type { PromptABTestProps } from '../ai/PromptABTest';

export { default as ABTestStats, calculateStats } from '../ai/ABTestStats';
export type { ABTestStatsProps, AggregateStats } from '../ai/ABTestStats';

export { default as SuggestionDiffView } from '../ai/SuggestionDiffView';
export type { SuggestionDiffViewProps, DiffLine } from '../ai/SuggestionDiffView';

export { default as SuggestionExplanation } from '../ai/SuggestionExplanation';
export type { SuggestionExplanationProps } from '../ai/SuggestionExplanation';
