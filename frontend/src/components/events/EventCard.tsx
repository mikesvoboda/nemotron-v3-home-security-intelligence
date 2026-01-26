import {
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  Eye,
  Film,
  Loader2,
  Moon,
  RefreshCw,
  Timer,
  TrendingUp,
} from 'lucide-react';
import { memo, useCallback, useEffect, useState } from 'react';

import {
  calculateAverageConfidence,
  calculateMaxConfidence,
  formatConfidencePercent,
  getConfidenceBgColorClass,
  getConfidenceBorderColorClass,
  getConfidenceLabel,
  getConfidenceLevel,
  getConfidenceTextColorClass,
  sortDetectionsByConfidence,
} from '../../utils/confidence';
import { getRiskLevel } from '../../utils/risk';
import { getSeverityConfig } from '../../utils/severityColors';
import { formatDuration } from '../../utils/time';
import ObjectTypeBadge from '../common/ObjectTypeBadge';
import RiskBadge from '../common/RiskBadge';
import SnoozeBadge from '../common/SnoozeBadge';
import TruncatedText from '../common/TruncatedText';

export interface Detection {
  label: string;
  confidence: number;
  bbox?: { x: number; y: number; width: number; height: number };
}

export interface CollapsibleDetectionsProps {
  detections: Detection[];
  maxVisible?: number;
}

/**
 * CollapsibleDetections component displays detection badges with expand/collapse
 * functionality when there are more detections than maxVisible.
 */
export function CollapsibleDetections({ detections, maxVisible = 3 }: CollapsibleDetectionsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Sort detections by confidence (highest first)
  const sortedDetections = sortDetectionsByConfidence(detections);

  // Determine which detections to show
  const shouldCollapse = sortedDetections.length > maxVisible;
  const visibleDetections = isExpanded ? sortedDetections : sortedDetections.slice(0, maxVisible);
  const hiddenCount = sortedDetections.length - maxVisible;

  // Format confidence as percentage
  const formatConfidence = (confidence: number): string => {
    return `${Math.round(confidence * 100)}%`;
  };

  // Handle toggle click - prevent propagation to avoid card navigation
  const handleToggle = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setIsExpanded((prev) => !prev);
  }, []);

  // Handle keyboard interaction
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      e.stopPropagation();
      setIsExpanded((prev) => !prev);
    }
  }, []);

  return (
    <div
      className={`flex flex-wrap gap-2 ${shouldCollapse ? 'transition-all duration-300 ease-in-out' : ''}`}
      data-testid="collapsible-detections"
    >
      {visibleDetections.map((detection, index) => {
        const level = getConfidenceLevel(detection.confidence);
        const confidenceLabel = getConfidenceLabel(level);
        return (
          <div
            key={`${detection.label}-${index}`}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${getConfidenceBgColorClass(level)} ${getConfidenceBorderColorClass(level)}`}
            title={`${detection.label}: ${formatConfidence(detection.confidence)} - ${confidenceLabel}`}
          >
            <span className="font-medium text-white">{detection.label}</span>
            <span className={`font-semibold ${getConfidenceTextColorClass(level)}`}>
              {formatConfidence(detection.confidence)}
            </span>
          </div>
        );
      })}
      {shouldCollapse && (
        <button
          onClick={handleToggle}
          onKeyDown={handleKeyDown}
          className="flex items-center gap-1 rounded-full border border-gray-600 bg-gray-700/50 px-3 py-1 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-600/50"
          aria-expanded={isExpanded}
          aria-label={isExpanded ? 'Show fewer detections' : `Show ${hiddenCount} more detections`}
          data-testid="collapsible-detections-toggle"
        >
          {isExpanded ? (
            <>
              <span>Show less</span>
              <ChevronUp className="h-3 w-3" />
            </>
          ) : (
            <>
              <span>+{hiddenCount} more</span>
              <ChevronDown className="h-3 w-3" />
            </>
          )}
        </button>
      )}
    </div>
  );
}

export interface EventCardProps {
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  risk_label: string;
  summary: string;
  reasoning?: string;
  thumbnail_url?: string;
  detections: Detection[];
  started_at?: string;
  ended_at?: string | null;
  onViewDetails?: (eventId: string) => void;
  onClick?: (eventId: string) => void;
  /** Callback to snooze the event for a duration in seconds */
  onSnooze?: (eventId: string, seconds: number) => void;
  className?: string;
  /** When true, adds left margin to header to accommodate an overlaying checkbox */
  hasCheckboxOverlay?: boolean;
  /** ISO timestamp until which alerts for this event are snoozed (NEM-3640) */
  snooze_until?: string | null;
  /** Callback to generate/regenerate video clip for this event (NEM-3870) */
  onGenerateClip?: (eventId: string) => void;
  /** Callback to download the video clip (NEM-3870) */
  onDownloadClip?: (eventId: string) => void;
  /** Whether clip generation is in progress (NEM-3870) */
  isGeneratingClip?: boolean;
  /** URL of the generated clip if available (NEM-3870) */
  clipUrl?: string | null;
}

/**
 * EventCard component displays a single security event with thumbnail, detections, and AI analysis
 */
const EventCard = memo(function EventCard({
  id,
  timestamp,
  camera_name,
  risk_score,
  summary,
  reasoning,
  thumbnail_url,
  detections,
  started_at,
  ended_at,
  onViewDetails,
  onClick,
  onSnooze,
  className = '',
  hasCheckboxOverlay = false,
  snooze_until,
  onGenerateClip,
  onDownloadClip,
  isGeneratingClip = false,
  clipUrl,
}: EventCardProps) {
  const [showReasoning, setShowReasoning] = useState(false);
  const [showSnoozeMenu, setShowSnoozeMenu] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  // Detect prefers-reduced-motion preference
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);

    const handleChange = (e: MediaQueryListEvent) => {
      setPrefersReducedMotion(e.matches);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Get severity configuration for styling
  const severityConfig = getSeverityConfig(risk_score);

  // Handle snooze action
  const handleSnooze = (seconds: number) => {
    if (onSnooze) {
      onSnooze(id, seconds);
    }
    setShowSnoozeMenu(false);
  };

  // Convert ISO timestamp to readable format
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      // If within last hour, show "X minutes ago"
      if (diffMins < 60) {
        return diffMins <= 1 ? 'Just now' : `${diffMins} minutes ago`;
      }

      // If within last 24 hours, show "X hours ago"
      if (diffHours < 24) {
        return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
      }

      // If within last week, show "X days ago"
      if (diffDays < 7) {
        return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
      }

      // Otherwise show formatted date and time
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  // Get risk level from score
  const riskLevel = getRiskLevel(risk_score);

  // Get unique object types from detections
  const uniqueObjectTypes = Array.from(new Set(detections.map((d) => d.label.toLowerCase())));

  // Calculate aggregate confidence metrics
  const avgConfidence = calculateAverageConfidence(detections);
  const maxConfidence = calculateMaxConfidence(detections);

  // Build severity-based styling classes
  const getSeverityClasses = (): string => {
    const classes: string[] = [];

    // Enhanced background tints for better visibility
    if (severityConfig.level === 'critical') {
      classes.push('bg-red-950/40'); // Stronger critical background
    } else if (severityConfig.level === 'high') {
      classes.push('bg-orange-950/30'); // Stronger high background
    } else {
      classes.push(severityConfig.bgClass);
    }

    classes.push(severityConfig.borderClass);

    // Add glow effect for critical severity
    if (severityConfig.glowClass) {
      classes.push(severityConfig.glowClass);
    }

    // Add pulse animation for critical severity (respecting reduced motion preference)
    if (severityConfig.shouldPulse && !prefersReducedMotion) {
      classes.push(severityConfig.pulseClass);
    }

    return classes.join(' ');
  };

  // Determine border width based on severity
  const getBorderWidthClass = (): string => {
    if (severityConfig.level === 'critical') {
      return 'border-l-[6px]'; // Thicker border for critical
    } else if (severityConfig.level === 'high') {
      return 'border-l-[5px]'; // Slightly thicker for high
    }
    return 'border-l-4'; // Default for medium/low
  };

  // Handle card click - don't trigger if clicking on interactive elements
  const handleCardClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // Check if the click target is an interactive element (button, etc.)
    const target = e.target as HTMLElement;
    const isInteractive = target.closest('button') || target.closest('a');

    if (onClick && !isInteractive) {
      onClick(id);
    }
  };

  // Determine if card should have button role (for WCAG compliance)
  // Don't add role="button" when there are nested interactive elements (snooze, view details)
  // to avoid accessibility violations (WCAG nested-interactive).
  // The card can still be clicked to trigger onClick, but won't be announced as a button.
  const hasNestedInteractiveElements = !!onSnooze || !!onViewDetails;
  const hasButtonRole = !!onClick && !hasNestedInteractiveElements;
  const isClickable = !!onClick;

  // Keyboard handler for Enter/Space to click the card
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick?.(id);
    }
  };

  return (
    /* eslint-disable jsx-a11y/no-static-element-interactions, jsx-a11y/no-noninteractive-tabindex -- Card is accessible via nested buttons (View Details, Snooze) when they exist; role="button" intentionally omitted to avoid WCAG nested-interactive violation */
    <div
      className={`rounded-lg border border-gray-800 ${getBorderWidthClass()} shadow-lg transition-all hover:border-gray-700 ${getSeverityClasses()} ${isClickable ? 'cursor-pointer hover:bg-[#252525]' : ''} ${className}`}
      data-testid={`event-card-${id}`}
      data-severity={severityConfig.level}
      onClick={isClickable ? handleCardClick : undefined}
      onKeyDown={isClickable ? handleKeyDown : undefined}
      tabIndex={isClickable ? 0 : undefined}
      {...(hasButtonRole && {
        role: 'button',
        'aria-label': `View details for event from ${camera_name}`,
      })}
    >
      {/* Main Layout: Thumbnail on left, content on right */}
      <div className="flex gap-4 p-4">
        {/* Thumbnail Column (80x80 - larger for better visibility) */}
        <div className="flex-shrink-0">
          {thumbnail_url ? (
            <img
              src={thumbnail_url}
              alt={`${camera_name} at ${formatTimestamp(timestamp)}`}
              className="h-20 w-20 rounded-lg object-cover shadow-md"
            />
          ) : (
            <div className="flex h-20 w-20 items-center justify-center rounded-lg bg-gray-800 shadow-md">
              <Eye className="h-8 w-8 text-gray-600" />
            </div>
          )}
        </div>

        {/* Content Column */}
        <div className="min-w-0 flex-1">
          {/* Header Row: Camera name on left, timestamp on right */}
          <div
            className={`mb-2 flex items-start justify-between ${hasCheckboxOverlay ? 'ml-8' : ''}`}
          >
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-lg font-semibold text-white" title={camera_name}>
                {camera_name}
              </h3>
            </div>
            {/* Timestamp in top-right - more prominent position */}
            <div
              className="flex items-center gap-1.5 text-sm font-medium text-gray-300"
              data-testid="event-timestamp"
            >
              <Clock className="h-4 w-4" />
              <span>{formatTimestamp(timestamp)}</span>
            </div>
          </div>

          {/* Risk Badge, Duration, and Snooze Status Row */}
          <div className={`mb-3 flex items-center gap-3 ${hasCheckboxOverlay ? 'ml-8' : ''}`}>
            <RiskBadge level={riskLevel} score={risk_score} showScore={true} size="md" />
            {(started_at || ended_at !== undefined) && (
              <div className="flex items-center gap-1.5 text-sm text-gray-400">
                <Timer className="h-3.5 w-3.5" />
                <span>
                  {formatDuration(started_at || timestamp, ended_at ?? null)}
                </span>
              </div>
            )}
            {/* Snooze Badge (NEM-3640) */}
            <SnoozeBadge snoozeUntil={snooze_until} size="sm" />
          </div>

          {/* Object Type Badges */}
          {uniqueObjectTypes.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {uniqueObjectTypes.map((type) => (
                <ObjectTypeBadge key={type} type={type} size="sm" />
              ))}
            </div>
          )}

          {/* AI Summary - truncated to 2 lines for better scannability */}
          <div className="mb-3">
            <TruncatedText
              text={summary}
              maxLength={120}
              maxLines={2}
              showMoreLabel="Show more"
              showLessLabel="Show less"
              className="text-gray-200"
            />
          </div>

          {/* Detection List with Color-Coded Confidence */}
          {detections.length > 0 && (
            <div className="mb-3 rounded-md bg-black/30 p-3">
              <div className="mb-2 flex items-center justify-between">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Detections ({detections.length})
                </h4>
                {/* Aggregate Confidence Display */}
                {avgConfidence !== null && maxConfidence !== null && (
                  <div
                    className="flex items-center gap-2 text-xs"
                    title={`Average: ${formatConfidencePercent(avgConfidence)} | Max: ${formatConfidencePercent(maxConfidence)}`}
                  >
                    <TrendingUp className="h-3 w-3 text-text-secondary" aria-hidden="true" />
                    <span className="text-text-secondary">Avg:</span>
                    <span
                      className={`font-semibold ${getConfidenceTextColorClass(getConfidenceLevel(avgConfidence))}`}
                    >
                      {formatConfidencePercent(avgConfidence)}
                    </span>
                    <span className="text-text-muted">|</span>
                    <span className="text-text-secondary">Max:</span>
                    <span
                      className={`font-semibold ${getConfidenceTextColorClass(getConfidenceLevel(maxConfidence))}`}
                    >
                      {formatConfidencePercent(maxConfidence)}
                    </span>
                  </div>
                )}
              </div>
              <CollapsibleDetections detections={detections} maxVisible={3} />
            </div>
          )}

          {/* AI Reasoning (expandable) */}
          {reasoning && (
            <div className="mb-3">
              <button
                onClick={() => setShowReasoning(!showReasoning)}
                className="flex w-full items-center justify-between rounded-md bg-[#76B900]/10 px-3 py-2 text-left text-sm font-medium text-[#76B900] transition-colors hover:bg-[#76B900]/20"
                aria-expanded={showReasoning}
                aria-controls={`reasoning-${id}`}
              >
                <span>AI Reasoning</span>
                {showReasoning ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </button>
              {showReasoning && (
                <div
                  id={`reasoning-${id}`}
                  className="mt-2 rounded-md bg-black/20 p-3 text-sm leading-relaxed text-gray-300"
                >
                  {reasoning}
                </div>
              )}
            </div>
          )}

          {/* Action Buttons Row */}
          <div className="flex gap-2">
            {/* Snooze Dropdown */}
            {onSnooze && (
              <div className="relative">
                <button
                  onClick={() => setShowSnoozeMenu(!showSnoozeMenu)}
                  className="flex items-center gap-2 rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-gray-700"
                  aria-expanded={showSnoozeMenu}
                  aria-haspopup="true"
                  aria-label="Snooze event"
                >
                  <Moon className="h-4 w-4" />
                  Snooze
                  <ChevronDown
                    className={`h-3 w-3 transition-transform ${showSnoozeMenu ? 'rotate-180' : ''}`}
                  />
                </button>
                {showSnoozeMenu && (
                  <div className="absolute right-0 z-10 mt-1 w-40 rounded-md border border-gray-700 bg-gray-800 py-1 shadow-lg">
                    <button
                      onClick={() => handleSnooze(900)}
                      className="block w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-gray-700"
                    >
                      15 minutes
                    </button>
                    <button
                      onClick={() => handleSnooze(3600)}
                      className="block w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-gray-700"
                    >
                      1 hour
                    </button>
                    <button
                      onClick={() => handleSnooze(14400)}
                      className="block w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-gray-700"
                    >
                      4 hours
                    </button>
                    <button
                      onClick={() => handleSnooze(28800)}
                      className="block w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-gray-700"
                    >
                      8 hours
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Clip Generation Buttons (NEM-3870) */}
            {onGenerateClip && (
              <button
                onClick={() => onGenerateClip(id)}
                disabled={isGeneratingClip}
                className="flex items-center gap-2 rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={
                  isGeneratingClip
                    ? 'Generating clip...'
                    : clipUrl
                      ? 'Regenerate video clip'
                      : 'Generate video clip'
                }
              >
                {isGeneratingClip ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : clipUrl ? (
                  <>
                    <RefreshCw className="h-4 w-4" />
                    Regenerate
                  </>
                ) : (
                  <>
                    <Film className="h-4 w-4" />
                    Generate Clip
                  </>
                )}
              </button>
            )}

            {/* Download Clip Button - only shown when clip is available (NEM-3870) */}
            {clipUrl && onDownloadClip && (
              <button
                onClick={() => onDownloadClip(id)}
                disabled={isGeneratingClip}
                className="flex items-center gap-2 rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-medium text-gray-300 transition-colors hover:border-gray-600 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Download video clip"
              >
                <Download className="h-4 w-4" />
                Download
              </button>
            )}

            {/* View Details Button */}
            {onViewDetails && (
              <button
                onClick={() => onViewDetails(id)}
                className="flex flex-1 items-center justify-center gap-2 rounded-md bg-[#76B900] px-4 py-2 text-sm font-semibold text-black transition-all hover:bg-[#88d200] active:bg-[#68a000]"
                aria-label={`View details for event ${id}`}
              >
                <Eye className="h-4 w-4" />
                View Details
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

export default EventCard;
