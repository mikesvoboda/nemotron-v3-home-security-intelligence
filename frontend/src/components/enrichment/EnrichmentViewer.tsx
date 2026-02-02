/**
 * EnrichmentViewer - Multi-variant viewer for AI enrichment data
 *
 * Displays enrichment data in multiple formats:
 * - full: Accordion-based expandable sections (default)
 * - compact: Badge display for inline use
 * - modal: All sections expanded for detailed view
 *
 * Features:
 * - Automatic section hiding for empty data
 * - Security alert highlighting with auto-expand
 * - Controlled and uncontrolled expansion states
 * - Keyboard accessible with ARIA labels
 * - Loading and error states with refresh capability
 *
 * @see docs/plans/2026-02-01-platform-enhancement-strategy-design.md
 */

import { clsx } from 'clsx';
import {
  Activity,
  AlertTriangle,
  Car,
  ChevronDown,
  Cloud,
  CreditCard,
  Dog,
  ImageIcon,
  RefreshCw,
  User,
} from 'lucide-react';
import { useCallback, useId, useMemo, useState } from 'react';

import { hasAnyEnrichment } from '../../types/enrichment';
import { formatConfidencePercent } from '../../utils/confidence';

import type { EnrichmentData } from '../../types/enrichment';

// ============================================================================
// Types
// ============================================================================

export interface EnrichmentViewerProps {
  /** Enrichment data to display */
  enrichmentData?: EnrichmentData | null;
  /** Display variant */
  variant?: 'full' | 'compact' | 'modal';
  /** Controlled expanded sections (section ids) */
  expandedSections?: string[];
  /** Callback when a section is toggled */
  onSectionToggle?: (section: string, expanded: boolean) => void;
  /** Callback when an entity value is clicked */
  onEntityClick?: (type: string, value: string) => void;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Error message to display */
  error?: string;
  /** Callback to refresh data */
  onRefresh?: () => void;
  /** Additional CSS classes */
  className?: string;
}

type SectionId =
  | 'vehicle'
  | 'pet'
  | 'person'
  | 'pose'
  | 'license-plate'
  | 'weather'
  | 'image-quality';

interface SectionConfig {
  id: SectionId;
  title: string;
  icon: React.ReactNode;
  hasData: (data: EnrichmentData) => boolean;
  hasAlerts?: (data: EnrichmentData) => boolean;
  render: (
    data: EnrichmentData,
    onEntityClick?: (type: string, value: string) => void
  ) => React.ReactNode;
}

// ============================================================================
// Section Configurations
// ============================================================================

const sectionConfigs: SectionConfig[] = [
  {
    id: 'vehicle',
    title: 'Vehicle',
    icon: <Car className="h-4 w-4" />,
    hasData: (data) => !!data.vehicle,
    render: (data) => {
      const vehicle = data.vehicle;
      if (!vehicle) return null;
      return (
        <div className="space-y-2">
          <DetailRow label="Type" value={vehicle.type} />
          <DetailRow label="Color" value={vehicle.color} />
          {vehicle.damage && vehicle.damage.length > 0 && (
            <DetailRow
              label="Damage"
              value={
                <div className="flex flex-wrap gap-1">
                  {vehicle.damage.map((d, i) => (
                    <span
                      key={i}
                      className="rounded bg-red-500/20 px-1.5 py-0.5 text-xs text-red-400"
                    >
                      {d}
                    </span>
                  ))}
                </div>
              }
            />
          )}
          {vehicle.commercial && (
            <div className="pt-1">
              <span className="inline-flex items-center rounded-md border border-blue-500/40 bg-blue-500/20 px-2 py-0.5 text-xs font-medium text-blue-400">
                Commercial Vehicle
              </span>
            </div>
          )}
          <DetailRow
            label="Confidence"
            value={formatConfidencePercent(vehicle.confidence)}
          />
        </div>
      );
    },
  },
  {
    id: 'pet',
    title: 'Pet',
    icon: <Dog className="h-4 w-4" />,
    hasData: (data) => !!data.pet,
    render: (data) => {
      const pet = data.pet;
      if (!pet) return null;
      return (
        <div className="space-y-2">
          <DetailRow label="Type" value={pet.type} />
          {pet.breed && <DetailRow label="Breed" value={pet.breed} />}
          <DetailRow
            label="Confidence"
            value={formatConfidencePercent(pet.confidence)}
          />
        </div>
      );
    },
  },
  {
    id: 'person',
    title: 'Person',
    icon: <User className="h-4 w-4" />,
    hasData: (data) => !!data.person,
    render: (data) => {
      const person = data.person;
      if (!person) return null;
      return (
        <div className="space-y-2">
          {person.clothing && (
            <DetailRow label="Clothing" value={person.clothing} />
          )}
          {person.action && <DetailRow label="Action" value={person.action} />}
          {person.carrying && (
            <DetailRow label="Carrying" value={person.carrying} />
          )}
          {person.suspicious_attire && (
            <div className="pt-1">
              <span className="inline-flex items-center gap-1 rounded-md border border-yellow-500/40 bg-yellow-500/20 px-2 py-0.5 text-xs font-medium text-yellow-400">
                <AlertTriangle className="h-3 w-3" />
                Suspicious Attire
              </span>
            </div>
          )}
          <DetailRow
            label="Confidence"
            value={formatConfidencePercent(person.confidence)}
          />
        </div>
      );
    },
  },
  {
    id: 'pose',
    title: 'Pose Analysis',
    icon: <Activity className="h-4 w-4" />,
    hasData: (data) => !!data.pose,
    hasAlerts: (data) => !!(data.pose && data.pose.alerts.length > 0),
    render: (data) => {
      const pose = data.pose;
      if (!pose) return null;
      const hasAlerts = pose.alerts.length > 0;
      return (
        <div className="space-y-3">
          <DetailRow label="Posture" value={pose.posture} />
          <DetailRow
            label="Keypoints"
            value={`${pose.keypoint_count ?? pose.keypoints.length} / 17`}
          />
          {hasAlerts && (
            <div
              className="mt-2 space-y-2 rounded-lg border border-red-500 bg-red-500/10 p-3"
              data-testid="pose-security-alerts"
            >
              <span className="text-xs font-semibold uppercase tracking-wide text-red-400">
                Security Alerts
              </span>
              <div className="space-y-1">
                {pose.alerts.map((alert) => (
                  <div
                    key={alert}
                    className="flex items-center gap-2 text-sm text-red-300"
                    data-testid={`security-alert-${alert}`}
                  >
                    <AlertTriangle className="h-3 w-3" />
                    <span className="capitalize">{alert.replace('_', ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <DetailRow
            label="Confidence"
            value={formatConfidencePercent(pose.confidence ?? 0)}
          />
        </div>
      );
    },
  },
  {
    id: 'license-plate',
    title: 'License Plate',
    icon: <CreditCard className="h-4 w-4" />,
    hasData: (data) => !!data.license_plate,
    render: (data, onEntityClick) => {
      const plate = data.license_plate;
      if (!plate) return null;
      return (
        <div className="space-y-2">
          <DetailRow
            label="Plate"
            value={
              <button
                type="button"
                className="font-mono text-sm text-white hover:text-blue-400 hover:underline"
                onClick={() => onEntityClick?.('license_plate', plate.text)}
              >
                {plate.text}
              </button>
            }
          />
          <DetailRow
            label="Confidence"
            value={formatConfidencePercent(plate.confidence)}
          />
        </div>
      );
    },
  },
  {
    id: 'weather',
    title: 'Weather',
    icon: <Cloud className="h-4 w-4" />,
    hasData: (data) => !!data.weather,
    render: (data) => {
      const weather = data.weather;
      if (!weather) return null;
      return (
        <div className="space-y-2">
          <DetailRow label="Condition" value={weather.condition} />
          <DetailRow
            label="Confidence"
            value={formatConfidencePercent(weather.confidence)}
          />
        </div>
      );
    },
  },
  {
    id: 'image-quality',
    title: 'Image Quality',
    icon: <ImageIcon className="h-4 w-4" />,
    hasData: (data) => !!data.image_quality,
    render: (data) => {
      const quality = data.image_quality;
      if (!quality) return null;
      return (
        <div className="space-y-2">
          <DetailRow
            label="Score"
            value={formatConfidencePercent(quality.score)}
          />
          {quality.issues.length > 0 && (
            <DetailRow
              label="Issues"
              value={
                <div className="flex flex-wrap gap-1">
                  {quality.issues.map((issue, i) => (
                    <span
                      key={i}
                      className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-xs text-yellow-400"
                    >
                      {issue}
                    </span>
                  ))}
                </div>
              }
            />
          )}
        </div>
      );
    },
  },
];

// ============================================================================
// Helper Components
// ============================================================================

function DetailRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-2 py-1">
      <span className="text-sm text-gray-400">{label}</span>
      <span className="text-right text-sm text-gray-200">{value}</span>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div
      className="animate-pulse space-y-3 p-4"
      data-testid="enrichment-viewer-skeleton"
    >
      <div className="h-4 w-48 rounded bg-gray-700" />
      <div className="space-y-2">
        <div className="h-10 rounded bg-gray-700" />
        <div className="h-10 rounded bg-gray-700" />
        <div className="h-10 rounded bg-gray-700" />
      </div>
      <p className="text-center text-sm text-gray-400">
        Loading enrichment data...
      </p>
    </div>
  );
}

function ErrorState({
  error,
  onRefresh,
}: {
  error: string;
  onRefresh?: () => void;
}) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 p-6"
      data-testid="enrichment-viewer-error"
    >
      <AlertTriangle className="h-8 w-8 text-red-400" />
      <p className="text-center text-sm text-red-400">{error}</p>
      {onRefresh && (
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex items-center gap-2 rounded-md border border-gray-600 bg-gray-800 px-3 py-1.5 text-sm text-gray-200 hover:bg-gray-700"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      )}
    </div>
  );
}

// ============================================================================
// Accordion Section Component
// ============================================================================

interface AccordionSectionProps {
  id: SectionId;
  title: string;
  icon: React.ReactNode;
  isExpanded: boolean;
  hasAlerts: boolean;
  alertCount?: number;
  onToggle: () => void;
  children: React.ReactNode;
  contentId: string;
}

function AccordionSection({
  id,
  title,
  icon,
  isExpanded,
  hasAlerts,
  alertCount,
  onToggle,
  children,
  contentId,
}: AccordionSectionProps) {
  const buttonId = `${contentId}-button`;

  return (
    <div
      data-testid={`enrichment-section-${id}`}
      data-expanded={isExpanded ? 'true' : 'false'}
      className="border-b border-gray-800 last:border-b-0"
    >
      <button
        type="button"
        id={buttonId}
        aria-expanded={isExpanded}
        aria-controls={contentId}
        onClick={onToggle}
        className={clsx(
          'flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-gray-800/50',
          hasAlerts && 'bg-red-900/20'
        )}
        data-testid={`enrichment-header-${id}`}
      >
        <div className="flex items-center gap-2">
          <span className={clsx(hasAlerts ? 'text-red-400' : 'text-[#76B900]')}>
            {icon}
          </span>
          <span className="font-medium text-white">{title}</span>
          {hasAlerts && alertCount && alertCount > 0 && (
            <span className="rounded-full bg-red-500 px-2 py-0.5 text-xs font-semibold text-white">
              {alertCount} Alerts
            </span>
          )}
        </div>
        <ChevronDown
          className={clsx(
            'h-4 w-4 text-gray-400 transition-transform',
            isExpanded && 'rotate-180'
          )}
        />
      </button>
      <div
        id={contentId}
        role="region"
        aria-labelledby={buttonId}
        className={clsx(
          'overflow-hidden transition-all',
          isExpanded ? 'max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'
        )}
      >
        <div className="bg-black/20 px-4 py-3">{children}</div>
      </div>
    </div>
  );
}

// ============================================================================
// Compact Badge Component
// ============================================================================

interface CompactBadgeProps {
  id: SectionId;
  title: string;
  icon: React.ReactNode;
  hasAlerts?: boolean;
}

function CompactBadge({ id, title, icon, hasAlerts }: CompactBadgeProps) {
  return (
    <span
      data-testid={`enrichment-badge-${id}`}
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium',
        hasAlerts
          ? 'border-red-500/40 bg-red-500/20 text-red-400'
          : 'border-gray-500/40 bg-gray-500/20 text-gray-300'
      )}
    >
      {icon}
      {title}
    </span>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function EnrichmentViewer({
  enrichmentData,
  variant = 'full',
  expandedSections: controlledExpandedSections,
  onSectionToggle,
  onEntityClick,
  isLoading = false,
  error,
  onRefresh,
  className,
}: EnrichmentViewerProps) {
  const uniqueId = useId();

  // Calculate which sections have alerts (for auto-expand)
  const sectionsWithAlerts = useMemo(() => {
    if (!enrichmentData) return new Set<SectionId>();
    const alertSections = new Set<SectionId>();
    for (const config of sectionConfigs) {
      if (config.hasAlerts?.(enrichmentData)) {
        alertSections.add(config.id);
      }
    }
    return alertSections;
  }, [enrichmentData]);

  // Internal state for uncontrolled mode
  const [internalExpanded, setInternalExpanded] = useState<Set<SectionId>>(
    () => new Set(sectionsWithAlerts)
  );

  // Determine which sections are expanded
  const expandedSet = useMemo(() => {
    if (variant === 'modal') {
      // Modal variant: all sections expanded
      return new Set(sectionConfigs.map((c) => c.id));
    }
    if (controlledExpandedSections !== undefined) {
      // Controlled mode
      return new Set(controlledExpandedSections as SectionId[]);
    }
    // Uncontrolled mode - include sections with alerts
    return new Set([...internalExpanded, ...sectionsWithAlerts]);
  }, [controlledExpandedSections, internalExpanded, sectionsWithAlerts, variant]);

  // Toggle handler
  const handleToggle = useCallback(
    (sectionId: SectionId) => {
      const newExpanded = !expandedSet.has(sectionId);

      if (onSectionToggle) {
        onSectionToggle(sectionId, newExpanded);
      }

      if (controlledExpandedSections === undefined) {
        // Uncontrolled mode - update internal state
        setInternalExpanded((prev) => {
          const next = new Set(prev);
          if (newExpanded) {
            next.add(sectionId);
          } else {
            next.delete(sectionId);
          }
          return next;
        });
      }
    },
    [expandedSet, onSectionToggle, controlledExpandedSections]
  );

  // Loading state
  if (isLoading) {
    return <LoadingSkeleton />;
  }

  // Error state
  if (error) {
    return <ErrorState error={error} onRefresh={onRefresh} />;
  }

  // No data state
  if (!enrichmentData || !hasAnyEnrichment(enrichmentData)) {
    return null;
  }

  // Filter to sections that have data
  const activeSections = sectionConfigs.filter((config) =>
    config.hasData(enrichmentData)
  );

  // Compact variant - badge display
  if (variant === 'compact') {
    return (
      <div
        data-testid="enrichment-viewer-compact"
        className={clsx('flex flex-wrap gap-2', className)}
      >
        {activeSections.map((config) => (
          <CompactBadge
            key={config.id}
            id={config.id}
            title={config.title}
            icon={config.icon}
            hasAlerts={config.hasAlerts?.(enrichmentData)}
          />
        ))}
      </div>
    );
  }

  // Full or Modal variant - accordion display
  const testId = variant === 'modal' ? 'enrichment-viewer-modal' : 'enrichment-viewer-full';

  return (
    <div
      data-testid={testId}
      className={clsx(
        'rounded-lg border border-gray-800 bg-black/20',
        className
      )}
    >
      {activeSections.map((config) => {
        const hasAlerts = config.hasAlerts?.(enrichmentData) ?? false;
        const alertCount =
          hasAlerts && enrichmentData.pose
            ? enrichmentData.pose.alerts.length
            : 0;

        return (
          <AccordionSection
            key={config.id}
            id={config.id}
            title={config.title}
            icon={config.icon}
            isExpanded={expandedSet.has(config.id)}
            hasAlerts={hasAlerts}
            alertCount={alertCount}
            onToggle={() => handleToggle(config.id)}
            contentId={`${uniqueId}-${config.id}`}
          >
            {config.render(enrichmentData, onEntityClick)}
          </AccordionSection>
        );
      })}
    </div>
  );
}
