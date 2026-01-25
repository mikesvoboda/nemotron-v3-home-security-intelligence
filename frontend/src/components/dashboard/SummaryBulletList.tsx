/**
 * Summary Bullet List Component
 *
 * Displays a list of bullet points with icons and severity-based coloring.
 * Used in SummaryCards to show structured summary information.
 *
 * @see NEM-2923
 */

import { AlertTriangle, Clock, Cloud, Eye, MapPin } from 'lucide-react';

import type { BulletPointIcon, SummaryBulletPoint } from '@/types/summary';
import type { LucideIcon } from 'lucide-react';

import { getSeverityConfig, type SeverityLevel } from '@/utils/severityCalculator';

// ============================================================================
// Constants
// ============================================================================

/**
 * Map icon type strings to lucide-react icons.
 */
const ICON_MAP: Record<BulletPointIcon, LucideIcon> = {
  alert: AlertTriangle,
  location: MapPin,
  pattern: Eye,
  time: Clock,
  weather: Cloud,
};

/**
 * Default icon used if the icon type is not recognized.
 */
const DEFAULT_ICON = Eye;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get the severity level from a numeric score.
 *
 * @param score - Severity score (0-100)
 * @returns SeverityLevel
 */
function getSeverityLevelFromScore(score: number): SeverityLevel {
  if (score >= 80) return 'critical';
  if (score >= 60) return 'high';
  if (score >= 40) return 'medium';
  if (score >= 20) return 'low';
  return 'clear';
}

/**
 * Get text color class based on severity score.
 *
 * @param severity - Optional severity score (0-100)
 * @returns Tailwind text color class
 */
function getTextColorClass(severity?: number): string {
  if (severity === undefined) {
    return 'text-gray-300';
  }

  const level = getSeverityLevelFromScore(severity);
  const config = getSeverityConfig(level);

  // Map borderColor to text color classes
  switch (config.color) {
    case 'red':
      return 'text-red-400';
    case 'orange':
      return 'text-orange-400';
    case 'yellow':
      return 'text-yellow-400';
    case 'green':
      return 'text-green-400';
    case 'emerald':
      return 'text-emerald-400';
    default:
      return 'text-gray-300';
  }
}

/**
 * Get icon color class based on severity score.
 *
 * @param severity - Optional severity score (0-100)
 * @returns Tailwind text color class for icons
 */
function getIconColorClass(severity?: number): string {
  if (severity === undefined) {
    return 'text-gray-500';
  }

  const level = getSeverityLevelFromScore(severity);
  const config = getSeverityConfig(level);

  switch (config.color) {
    case 'red':
      return 'text-red-500';
    case 'orange':
      return 'text-orange-500';
    case 'yellow':
      return 'text-yellow-500';
    case 'green':
      return 'text-green-500';
    case 'emerald':
      return 'text-emerald-500';
    default:
      return 'text-gray-500';
  }
}

// ============================================================================
// Component Props
// ============================================================================

export interface SummaryBulletListProps {
  /** Array of bullet points to display */
  bullets: SummaryBulletPoint[];

  /** Maximum number of items to display (default: 4) */
  maxItems?: number;

  /** Test ID prefix for the list */
  testIdPrefix?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Renders a list of bullet points with icons and severity-based styling.
 *
 * @example
 * ```tsx
 * const bullets = [
 *   { icon: 'alert', text: 'Critical event detected', severity: 85 },
 *   { icon: 'location', text: 'Front door camera' },
 *   { icon: 'time', text: '2:15 PM - 3:00 PM' },
 * ];
 *
 * <SummaryBulletList bullets={bullets} maxItems={4} />
 * ```
 */
export function SummaryBulletList({
  bullets,
  maxItems = 4,
  testIdPrefix = 'summary-bullet',
}: SummaryBulletListProps) {
  // Limit the number of displayed bullets
  const displayedBullets = bullets.slice(0, maxItems);
  const remainingCount = bullets.length - maxItems;

  return (
    <ul
      className="space-y-2"
      data-testid={`${testIdPrefix}-list`}
      aria-label="Summary bullet points"
    >
      {displayedBullets.map((bullet, index) => {
        const IconComponent = ICON_MAP[bullet.icon] || DEFAULT_ICON;
        const textColorClass = getTextColorClass(bullet.severity);
        const iconColorClass = getIconColorClass(bullet.severity);

        return (
          <li
            key={`${bullet.icon}-${index}`}
            className="flex items-start gap-2"
            data-testid={`${testIdPrefix}-item-${index}`}
            data-severity={bullet.severity}
          >
            <IconComponent
              className={`mt-0.5 h-4 w-4 flex-shrink-0 ${iconColorClass}`}
              aria-hidden="true"
            />
            <span className={`text-sm leading-relaxed ${textColorClass}`}>{bullet.text}</span>
          </li>
        );
      })}

      {remainingCount > 0 && (
        <li
          className="flex items-center gap-2 text-sm text-gray-500"
          data-testid={`${testIdPrefix}-overflow`}
        >
          <span className="w-4" /> {/* Spacer for alignment */}
          <span>+{remainingCount} more</span>
        </li>
      )}
    </ul>
  );
}

export default SummaryBulletList;
