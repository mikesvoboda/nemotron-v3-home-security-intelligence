/**
 * Entity tracking components for re-identification across cameras.
 */
export { default as EntitiesPage } from './EntitiesPage';
export { default as EntityCard } from './EntityCard';
export { default as EntityDetailModal } from './EntityDetailModal';
export { default as EntityTimeline } from './EntityTimeline';

// Re-export types
export type { EntityCardProps } from './EntityCard';
export type { EntityDetailModalProps } from './EntityDetailModal';
export type { EntityTimelineProps, EntityAppearance } from './EntityTimeline';
