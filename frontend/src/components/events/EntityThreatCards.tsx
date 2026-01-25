/**
 * EntityThreatCards - Display entities identified in risk analysis (NEM-3601)
 *
 * Shows cards for each entity (person, vehicle, package, etc.) identified
 * by the LLM during risk analysis, with threat level indicators.
 */

import { clsx } from 'clsx';
import { Car, Package, User, HelpCircle } from 'lucide-react';

import { THREAT_LEVEL_CONFIG } from '../../types/risk-analysis';

import type { RiskEntity } from '../../types/risk-analysis';
import type { ReactNode } from 'react';

export interface EntityThreatCardsProps {
  /** List of entities from risk analysis */
  entities: RiskEntity[] | null | undefined;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Get icon for entity type
 */
function getEntityIcon(type: string): ReactNode {
  const iconClass = 'h-5 w-5';
  const normalizedType = type.toLowerCase();

  if (normalizedType.includes('person') || normalizedType.includes('individual')) {
    return <User className={iconClass} />;
  }
  if (normalizedType.includes('vehicle') || normalizedType.includes('car') || normalizedType.includes('truck')) {
    return <Car className={iconClass} />;
  }
  if (normalizedType.includes('package') || normalizedType.includes('box') || normalizedType.includes('delivery')) {
    return <Package className={iconClass} />;
  }

  return <HelpCircle className={iconClass} />;
}

/**
 * Get human-readable label for entity type
 */
function getEntityLabel(type: string): string {
  const normalizedType = type.toLowerCase().trim();

  // Capitalize first letter of each word
  return normalizedType
    .split(/[\s_-]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Single entity card component
 */
function EntityCard({ entity }: { entity: RiskEntity }) {
  const config = THREAT_LEVEL_CONFIG[entity.threat_level] || THREAT_LEVEL_CONFIG.low;

  return (
    <div
      data-testid="entity-card"
      className={clsx(
        'rounded-lg border p-3',
        config.bgColor,
        config.borderColor
      )}
    >
      <div className="flex items-start gap-3">
        <div className={clsx('flex-shrink-0', config.color)}>
          {getEntityIcon(entity.type)}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1">
            <h5 className="text-sm font-medium text-white">
              {getEntityLabel(entity.type)}
            </h5>
            <span
              className={clsx(
                'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                config.bgColor,
                config.color
              )}
            >
              {config.label}
            </span>
          </div>
          <p className="text-xs text-gray-300">{entity.description}</p>
        </div>
      </div>
    </div>
  );
}

/**
 * EntityThreatCards component
 *
 * Renders a grid of entity cards from risk analysis.
 * Returns null if no entities are provided.
 */
export default function EntityThreatCards({
  entities,
  className,
}: EntityThreatCardsProps) {
  // Don't render if no entities
  if (!entities || entities.length === 0) {
    return null;
  }

  return (
    <div
      data-testid="entity-threat-cards"
      className={clsx('space-y-3', className)}
    >
      <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-400">
        Identified Entities
      </h4>

      <div className="grid gap-2 sm:grid-cols-2">
        {entities.map((entity, index) => (
          <EntityCard key={`${entity.type}-${index}`} entity={entity} />
        ))}
      </div>
    </div>
  );
}
