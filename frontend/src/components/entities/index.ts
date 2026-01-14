/**
 * Entity tracking components for re-identification across cameras.
 */
export { default as EntitiesPage } from './EntitiesPage';
export { default as EntityCard } from './EntityCard';
export { default as EntityDetailModal } from './EntityDetailModal';
export { default as EntityTimeline } from './EntityTimeline';
export { default as EntityStatsCard } from './EntityStatsCard';
export { default as ReidHistoryPanel } from './ReidHistoryPanel';

// Re-export types
export type { EntityCardProps } from './EntityCard';
export type { EntityDetailModalProps } from './EntityDetailModal';
export type { EntityTimelineProps, EntityAppearance } from './EntityTimeline';
export type { EntityStatsCardProps } from './EntityStatsCard';
export type { ReidHistoryPanelProps } from './ReidHistoryPanel';
