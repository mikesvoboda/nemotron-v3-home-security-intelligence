/**
 * ThreatDetectionBanner - Prominent banner for weapon/threat detection alerts
 *
 * Displays a highly visible banner when weapons or dangerous objects are detected
 * by the AI pipeline. Uses critical severity visual treatment with animation for
 * maximum visibility.
 *
 * NEM-5024: Phase 4 - Threat Detection Surfacing
 *
 * @example
 * ```tsx
 * <ThreatDetectionBanner
 *   threatSummary={threatSummary}
 *   onViewEvent={(eventId) => navigateToEvent(eventId)}
 *   onDismiss={() => setDismissed(true)}
 * />
 * ```
 */

import { clsx } from 'clsx';
import { AlertOctagon, AlertTriangle, AlertCircle, Info, Eye, X, Camera } from 'lucide-react';
import { forwardRef } from 'react';

import {
  THREAT_SEVERITY_CONFIG,
  getThreatTypeLabel,
  type ThreatSummary,
  type ThreatSeverity,
} from '../../types/threat';

// ============================================================================
// Types
// ============================================================================

export interface ThreatDetectionBannerProps {
  /** Summary of active threat detections */
  threatSummary: ThreatSummary | null | undefined;

  /** Called when the banner is clicked */
  onClick?: () => void;

  /** Called when the "View" button is clicked with the event ID */
  onViewEvent?: (eventId: number) => void;

  /** Called when the dismiss button is clicked */
  onDismiss?: () => void;

  /** Whether to show confidence percentage */
  showConfidence?: boolean;

  /** Whether to use compact layout */
  compact?: boolean;

  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get the appropriate icon component for a severity level.
 */
function SeverityIcon({ severity, className }: { severity: ThreatSeverity; className?: string }) {
  const iconClass = clsx('h-6 w-6', className);

  switch (severity) {
    case 'critical':
      return <AlertOctagon className={iconClass} aria-hidden="true" />;
    case 'high':
      return <AlertTriangle className={iconClass} aria-hidden="true" />;
    case 'medium':
      return <AlertCircle className={iconClass} aria-hidden="true" />;
    case 'low':
    default:
      return <Info className={iconClass} aria-hidden="true" />;
  }
}

/**
 * Format threat types for display.
 */
function formatThreatTypes(threatTypes: string[]): string {
  if (threatTypes.length === 0) return 'Unknown Threat';
  if (threatTypes.length === 1) return getThreatTypeLabel(threatTypes[0]);
  return threatTypes.map(getThreatTypeLabel).join(', ');
}

/**
 * Format camera info for display.
 */
function formatCameraInfo(cameras: string[]): string {
  if (cameras.length === 0) return '';
  if (cameras.length === 1) return cameras[0];
  return `${cameras.length} cameras`;
}

// ============================================================================
// Component
// ============================================================================

/**
 * ThreatDetectionBanner - Displays prominent alert when threats are detected
 *
 * Features:
 * - Critical severity visual treatment (red background, pulsing animation)
 * - Shows threat type (Firearm, Knife, etc.)
 * - Shows affected cameras
 * - Quick-access button to view the event
 * - Accessible with proper ARIA attributes
 */
const ThreatDetectionBanner = forwardRef<HTMLDivElement, ThreatDetectionBannerProps>(
  function ThreatDetectionBanner(
    {
      threatSummary,
      onClick,
      onViewEvent,
      onDismiss,
      showConfidence = false,
      compact = false,
      className,
    },
    ref
  ) {
    // Don't render if no active threats
    if (!threatSummary?.hasActiveThreats || threatSummary.totalThreats === 0) {
      return null;
    }

    const { maxSeverity, totalThreats, threatTypes, affectedCameras, latestThreat } = threatSummary;
    const severity = maxSeverity ?? 'high';
    const config = THREAT_SEVERITY_CONFIG[severity];

    // Determine ARIA live politeness based on severity
    const ariaLive = severity === 'critical' ? 'assertive' : 'polite';

    // Build main message
    const threatLabel = totalThreats === 1 ? 'threat' : 'threats';
    const threatTypesText = formatThreatTypes(threatTypes);
    const cameraText = formatCameraInfo(affectedCameras);

    // Confidence display for single threat
    const confidenceText =
      showConfidence && latestThreat
        ? `${Math.round(latestThreat.confidence * 100)}%`
        : null;

    // Handle banner click
    const handleBannerClick = () => {
      if (onClick) {
        onClick();
      }
    };

    // Handle keyboard interaction
    const handleKeyDown = (e: React.KeyboardEvent) => {
      if ((e.key === 'Enter' || e.key === ' ') && onClick) {
        e.preventDefault();
        onClick();
      }
    };

    // Handle view button click
    const handleViewClick = (e: React.MouseEvent) => {
      e.stopPropagation();
      if (onViewEvent && latestThreat?.event_id) {
        onViewEvent(latestThreat.event_id);
      }
    };

    // Handle dismiss click
    const handleDismissClick = (e: React.MouseEvent) => {
      e.stopPropagation();
      if (onDismiss) {
        onDismiss();
      }
    };

    return (
      // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- role="button" with proper keyboard handling
      <div
        ref={ref}
        role={onClick ? 'button' : 'alert'}
        aria-live={ariaLive}
        data-testid="threat-detection-banner"
        className={clsx(
          // Base styles
          'flex items-center justify-between gap-4 rounded-lg border-2',
          // Padding based on compact mode
          compact ? 'px-3 py-2' : 'px-4 py-3',
          // Severity-based colors
          config.bgColor,
          config.borderColor,
          // Animation for critical/high severity
          config.animationClass,
          // Interactive styles when onClick provided
          onClick && [
            'cursor-pointer',
            'transition-all duration-200',
            'hover:brightness-110',
            'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#121212]',
            severity === 'critical' && 'focus:ring-red-500',
            severity === 'high' && 'focus:ring-orange-500',
            severity === 'medium' && 'focus:ring-yellow-500',
            severity === 'low' && 'focus:ring-gray-500',
          ],
          className
        )}
        onClick={handleBannerClick}
        onKeyDown={onClick ? handleKeyDown : undefined}
        tabIndex={onClick ? 0 : undefined}
      >
        {/* Left side: Icon and message */}
        <div className="flex items-center gap-3">
          {/* Severity icon */}
          <div className={clsx('flex-shrink-0', config.textColor)}>
            <SeverityIcon severity={severity} />
          </div>

          {/* Message content */}
          <div className="flex flex-col gap-0.5">
            {/* Header line */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className={clsx('font-bold uppercase tracking-wide', config.textColor)}>
                THREAT DETECTED
              </span>
              {totalThreats > 1 && (
                <span className={clsx('text-sm font-medium', config.textColor)}>
                  ({totalThreats} {threatLabel})
                </span>
              )}
            </div>

            {/* Details line */}
            <div className="flex items-center gap-2 text-sm text-gray-300 flex-wrap">
              {/* Threat type */}
              <span className="font-medium">{threatTypesText}</span>

              {/* Confidence */}
              {confidenceText && (
                <>
                  <span className="text-gray-500">|</span>
                  <span className="text-gray-400">{confidenceText} confidence</span>
                </>
              )}

              {/* Camera info */}
              {cameraText && (
                <>
                  <span className="text-gray-500">|</span>
                  <span className="flex items-center gap-1 text-gray-400">
                    <Camera className="h-3 w-3" aria-hidden="true" />
                    {cameraText}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Right side: Action buttons */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* View Event button */}
          {onViewEvent && latestThreat?.event_id && (
            <button
              type="button"
              onClick={handleViewClick}
              className={clsx(
                'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5',
                'text-sm font-medium transition-colors',
                severity === 'critical' && 'bg-red-600 text-white hover:bg-red-500',
                severity === 'high' && 'bg-orange-600 text-white hover:bg-orange-500',
                severity === 'medium' && 'bg-yellow-600 text-gray-900 hover:bg-yellow-500',
                severity === 'low' && 'bg-gray-600 text-white hover:bg-gray-500'
              )}
              aria-label="View threat event"
            >
              <Eye className="h-4 w-4" aria-hidden="true" />
              View
            </button>
          )}

          {/* Dismiss button */}
          {onDismiss && (
            <button
              type="button"
              onClick={handleDismissClick}
              className={clsx(
                'rounded-md p-1.5 transition-colors',
                'text-gray-400 hover:bg-gray-700 hover:text-white',
                'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#121212]',
                severity === 'critical' && 'focus:ring-red-500',
                severity === 'high' && 'focus:ring-orange-500',
                severity === 'medium' && 'focus:ring-yellow-500',
                severity === 'low' && 'focus:ring-gray-500'
              )}
              aria-label="Dismiss threat notification"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    );
  }
);

export default ThreatDetectionBanner;
