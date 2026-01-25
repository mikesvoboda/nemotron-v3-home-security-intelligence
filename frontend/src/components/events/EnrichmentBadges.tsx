/**
 * EnrichmentBadges - Compact badges showing enrichment status on EventCard
 *
 * Displays small, clickable badges that indicate what AI enrichment data is available
 * for an event. These badges provide a quick overview without requiring users to open
 * the full EventDetailModal.
 *
 * Badge types:
 * - Face count: Shows number of faces detected
 * - License plate: Indicates license plate was read
 * - Violence score: Shows threat level if > 50%
 * - Pet type: Shows pet type if detected
 * - Vehicle: Indicates vehicle detected
 * - Person: Indicates person attributes detected
 * - Pose alerts: Shows security alerts from pose analysis
 */

import { clsx } from 'clsx';
import {
  AlertTriangle,
  Car,
  CreditCard,
  Dog,
  Loader2,
  Sparkles,
  User,
  Activity,
} from 'lucide-react';

import type { EnrichmentData } from '../../types/enrichment';

/**
 * Summary of enrichment data for badge display.
 * This is a simplified view of the full EnrichmentData for compact display.
 */
export interface EnrichmentSummary {
  /** Number of faces detected */
  faceCount?: number;
  /** Whether a license plate was detected */
  hasLicensePlate?: boolean;
  /** Violence/threat score (0-1) */
  violenceScore?: number;
  /** Pet type if detected (e.g., 'dog', 'cat') */
  petType?: string;
  /** Whether a vehicle was detected */
  hasVehicle?: boolean;
  /** Whether person attributes were detected */
  hasPerson?: boolean;
  /** Number of pose security alerts */
  poseAlertCount?: number;
}

export interface EnrichmentBadgesProps {
  /** Enrichment summary data to display */
  enrichmentSummary?: EnrichmentSummary | null;
  /** Full enrichment data (alternative to summary) */
  enrichmentData?: EnrichmentData | null;
  /** Whether enrichment is currently being processed */
  isEnrichmentPending?: boolean;
  /** Callback when badges are clicked to expand full EnrichmentPanel */
  onExpandEnrichment?: () => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Convert full EnrichmentData to EnrichmentSummary for badge display.
 */
// eslint-disable-next-line react-refresh/only-export-components -- utility function used by EventCard
export function enrichmentDataToSummary(data: EnrichmentData | null | undefined): EnrichmentSummary {
  if (!data) return {};

  const summary: EnrichmentSummary = {};

  // Vehicle detection
  if (data.vehicle) {
    summary.hasVehicle = true;
  }

  // License plate detection
  if (data.license_plate) {
    summary.hasLicensePlate = true;
  }

  // Pet detection
  if (data.pet) {
    summary.petType = data.pet.type;
  }

  // Person detection
  if (data.person) {
    summary.hasPerson = true;
  }

  // Pose analysis with security alerts
  if (data.pose) {
    // Use alerts array, but fall back to security_alerts if alerts is empty
    const alerts = data.pose.alerts?.length ? data.pose.alerts : (data.pose.security_alerts ?? []);
    if (alerts.length > 0) {
      summary.poseAlertCount = alerts.length;
    }
  }

  return summary;
}

/**
 * Check if there is any enrichment data to display.
 */
function hasAnyEnrichment(summary: EnrichmentSummary | null | undefined): boolean {
  if (!summary) return false;
  return !!(
    summary.faceCount ||
    summary.hasLicensePlate ||
    (summary.violenceScore && summary.violenceScore > 0.5) ||
    summary.petType ||
    summary.hasVehicle ||
    summary.hasPerson ||
    summary.poseAlertCount
  );
}

/**
 * Badge component for individual enrichment indicators.
 */
interface BadgeProps {
  icon: React.ReactNode;
  label: string;
  variant?: 'info' | 'warning' | 'alert' | 'default';
  onClick?: () => void;
}

function Badge({ icon, label, variant = 'default', onClick }: BadgeProps) {
  const variantClasses = {
    info: 'bg-blue-500/20 border-blue-500/40 text-blue-400',
    warning: 'bg-yellow-500/20 border-yellow-500/40 text-yellow-400',
    alert: 'bg-red-500/20 border-red-500/40 text-red-400',
    default: 'bg-gray-500/20 border-gray-500/40 text-gray-400',
  };

  const hoverClasses = onClick
    ? 'cursor-pointer hover:bg-opacity-30 hover:border-opacity-60 transition-colors'
    : '';

  return (
    /* eslint-disable-next-line jsx-a11y/no-static-element-interactions -- When onClick is provided, role="button", tabIndex, and keyboard handlers are added for accessibility */
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
        variantClasses[variant],
        hoverClasses
      )}
      onClick={(e) => {
        if (onClick) {
          e.stopPropagation();
          onClick();
        }
      }}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                onClick();
              }
            }
          : undefined
      }
      data-testid={`enrichment-badge-${label.toLowerCase().replace(/\s+/g, '-')}`}
    >
      {icon}
      {label}
    </span>
  );
}

/**
 * EnrichmentBadges - Displays compact enrichment status badges
 */
export default function EnrichmentBadges({
  enrichmentSummary,
  enrichmentData,
  isEnrichmentPending = false,
  onExpandEnrichment,
  className,
}: EnrichmentBadgesProps) {
  // Convert full enrichment data to summary if provided
  const summary = enrichmentSummary ?? enrichmentDataToSummary(enrichmentData);

  // Show loading state while enrichment is pending
  if (isEnrichmentPending) {
    return (
      <div
        className={clsx('flex flex-wrap gap-1.5', className)}
        data-testid="enrichment-badges-pending"
      >
        <Badge
          icon={<Loader2 className="h-3 w-3 animate-spin" />}
          label="Enriching..."
          variant="default"
        />
      </div>
    );
  }

  // Don't render anything if there's no enrichment data
  if (!hasAnyEnrichment(summary)) {
    return null;
  }

  const badges: React.ReactNode[] = [];

  // Pose alerts badge (highest priority - security relevant)
  if (summary.poseAlertCount && summary.poseAlertCount > 0) {
    badges.push(
      <Badge
        key="pose-alerts"
        icon={<Activity className="h-3 w-3" />}
        label={`${summary.poseAlertCount} Alert${summary.poseAlertCount > 1 ? 's' : ''}`}
        variant="alert"
        onClick={onExpandEnrichment}
      />
    );
  }

  // Violence score badge (high priority - security relevant)
  if (summary.violenceScore && summary.violenceScore > 0.5) {
    const percent = Math.round(summary.violenceScore * 100);
    badges.push(
      <Badge
        key="violence"
        icon={<AlertTriangle className="h-3 w-3" />}
        label={`Threat ${percent}%`}
        variant="alert"
        onClick={onExpandEnrichment}
      />
    );
  }

  // Face count badge
  if (summary.faceCount && summary.faceCount > 0) {
    badges.push(
      <Badge
        key="faces"
        icon={<User className="h-3 w-3" />}
        label={`${summary.faceCount} Face${summary.faceCount > 1 ? 's' : ''}`}
        variant="info"
        onClick={onExpandEnrichment}
      />
    );
  }

  // License plate badge
  if (summary.hasLicensePlate) {
    badges.push(
      <Badge
        key="license-plate"
        icon={<CreditCard className="h-3 w-3" />}
        label="Plate"
        variant="info"
        onClick={onExpandEnrichment}
      />
    );
  }

  // Vehicle badge
  if (summary.hasVehicle) {
    badges.push(
      <Badge
        key="vehicle"
        icon={<Car className="h-3 w-3" />}
        label="Vehicle"
        variant="info"
        onClick={onExpandEnrichment}
      />
    );
  }

  // Pet badge
  if (summary.petType) {
    badges.push(
      <Badge
        key="pet"
        icon={<Dog className="h-3 w-3" />}
        label={summary.petType.charAt(0).toUpperCase() + summary.petType.slice(1)}
        variant="info"
        onClick={onExpandEnrichment}
      />
    );
  }

  // Person badge (only show if no other person-related badges)
  if (summary.hasPerson && !summary.faceCount && !summary.poseAlertCount) {
    badges.push(
      <Badge
        key="person"
        icon={<User className="h-3 w-3" />}
        label="Person"
        variant="info"
        onClick={onExpandEnrichment}
      />
    );
  }

  // If there are badges but the user can expand to see more
  if (badges.length > 0 && onExpandEnrichment) {
    badges.push(
      <Badge
        key="view-details"
        icon={<Sparkles className="h-3 w-3" />}
        label="Details"
        variant="default"
        onClick={onExpandEnrichment}
      />
    );
  }

  return (
    <div className={clsx('flex flex-wrap gap-1.5', className)} data-testid="enrichment-badges">
      {badges}
    </div>
  );
}
