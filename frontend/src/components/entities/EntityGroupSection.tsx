import { ChevronDown, ChevronRight, type LucideIcon } from 'lucide-react';
import { memo, useState } from 'react';

import EntityCard, { getActivityTier } from './EntityCard';

import type { TrustStatus } from '../../services/api';

/**
 * Entity data needed for rendering EntityCard within a group section
 * Note: trust_status is typed as string to accommodate API response flexibility,
 * but will be normalized to TrustStatus by getEntityTrustStatus callback
 */
export interface GroupedEntity {
  id: string;
  entity_type: string;
  first_seen: string;
  last_seen: string;
  appearance_count: number;
  cameras_seen?: string[];
  thumbnail_url?: string | null;
  trust_status?: string | null;
}

export interface EntityGroupSectionProps {
  /** Title displayed in the section header */
  title: string;
  /** Icon component to display next to the title */
  icon: LucideIcon;
  /** Array of entities to display in this section */
  entities: GroupedEntity[];
  /** Whether the section is collapsed by default */
  defaultCollapsed?: boolean;
  /** Callback when an entity card is clicked */
  onEntityClick?: (entityId: string) => void;
  /** Function to get the effective trust status for an entity */
  getEntityTrustStatus?: (
    entityId: string,
    apiTrustStatus: string | null | undefined
  ) => TrustStatus | null;
  /** Optional className for additional styling */
  className?: string;
}

/**
 * EntityGroupSection component - Collapsible section displaying a group of entities
 *
 * Features:
 * - Collapsible header with icon, title, and entity count
 * - Grid layout for entity cards when expanded
 * - Configurable default collapsed state
 * - Keyboard accessible toggle
 */
const EntityGroupSection = memo(function EntityGroupSection({
  title,
  icon: Icon,
  entities,
  defaultCollapsed = false,
  onEntityClick,
  getEntityTrustStatus,
  className = '',
}: EntityGroupSectionProps) {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  // Don't render if no entities
  if (entities.length === 0) {
    return null;
  }

  const toggleCollapse = () => {
    setIsCollapsed((prev) => !prev);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleCollapse();
    }
  };

  return (
    <div
      className={`mb-6 ${className}`}
      data-testid={`entity-group-${title.toLowerCase().replace(/\s+/g, '-')}`}
    >
      {/* Section Header */}
      <button
        onClick={toggleCollapse}
        onKeyDown={handleKeyDown}
        className="mb-4 flex w-full items-center gap-3 rounded-lg bg-[#1F1F1F] px-4 py-3 text-left transition-colors hover:bg-[#252525]"
        aria-expanded={!isCollapsed}
        aria-controls={`entity-group-content-${title.toLowerCase().replace(/\s+/g, '-')}`}
        data-testid={`entity-group-header-${title.toLowerCase().replace(/\s+/g, '-')}`}
      >
        {/* Collapse/Expand Indicator */}
        {isCollapsed ? (
          <ChevronRight className="h-5 w-5 text-gray-400" data-testid="collapse-icon-collapsed" />
        ) : (
          <ChevronDown className="h-5 w-5 text-gray-400" data-testid="collapse-icon-expanded" />
        )}

        {/* Section Icon */}
        <Icon className="h-5 w-5 text-[#76B900]" />

        {/* Section Title */}
        <span className="text-lg font-semibold text-white">{title}</span>

        {/* Entity Count Badge */}
        <span
          className="rounded-full bg-[#76B900]/20 px-2.5 py-0.5 text-sm font-medium text-[#76B900]"
          data-testid={`entity-group-count-${title.toLowerCase().replace(/\s+/g, '-')}`}
        >
          {entities.length}
        </span>
      </button>

      {/* Section Content - Entity Grid */}
      {!isCollapsed && (
        <div
          id={`entity-group-content-${title.toLowerCase().replace(/\s+/g, '-')}`}
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
          data-testid={`entity-group-content-${title.toLowerCase().replace(/\s+/g, '-')}`}
        >
          {entities.map((entity) => (
            <EntityCard
              key={entity.id}
              id={entity.id}
              entity_type={entity.entity_type}
              first_seen={entity.first_seen}
              last_seen={entity.last_seen}
              appearance_count={entity.appearance_count}
              cameras_seen={entity.cameras_seen}
              thumbnail_url={entity.thumbnail_url}
              trust_status={
                getEntityTrustStatus
                  ? getEntityTrustStatus(entity.id, entity.trust_status)
                  : (entity.trust_status as TrustStatus | null | undefined)
              }
              activity_tier={getActivityTier(entity.appearance_count, entity.last_seen)}
              onClick={onEntityClick}
            />
          ))}
        </div>
      )}
    </div>
  );
});

export default EntityGroupSection;
