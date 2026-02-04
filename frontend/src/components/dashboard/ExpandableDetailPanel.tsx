/**
 * ExpandableDetailPanel - Modal panel showing detailed summary with timeline and export options.
 *
 * Displays when a user clicks "View Full Summary" on a summary card.
 * Features:
 * - Full narrative description
 * - Timeline view of events
 * - Export options (JSON, CSV, PDF)
 * - Links to individual event details
 * - Keyboard accessible (Escape to close)
 * - Smooth slide-in animation
 *
 * Related Linear issues: NEM-5425, NEM-5426, NEM-5427
 */

import clsx from 'clsx';
import { format, formatDistanceToNow, parseISO } from 'date-fns';
import {
  X,
  Clock,
  Calendar,
  ExternalLink,
  FileJson,
  FileSpreadsheet,
  FileText,
  AlertCircle,
  MapPin,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import type { ExportFormat, SummaryDetail, TimelineEvent } from '@/types/summary';

// Risk level color mapping
const RISK_LEVEL_COLORS: Record<string, string> = {
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
};

/**
 * Props for the ExpandableDetailPanel component.
 */
export interface ExpandableDetailPanelProps {
  /** The detailed summary data to display */
  detail: SummaryDetail;
  /** Whether the panel is open */
  isOpen: boolean;
  /** Callback when the panel should close */
  onClose: () => void;
  /** Callback when export is requested */
  onExport?: (summaryId: number, format: ExportFormat) => void;
  /** Whether an export is in progress */
  isExporting?: boolean;
  /** Current export format being processed */
  exportFormat?: ExportFormat;
  /** Additional CSS class name */
  className?: string;
}

/**
 * Check if user prefers reduced motion.
 */
function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Timeline event row component.
 */
function TimelineEventRow({ event, index }: { event: TimelineEvent; index: number }) {
  const riskColorClass = event.riskLevel
    ? RISK_LEVEL_COLORS[event.riskLevel] || RISK_LEVEL_COLORS.low
    : 'bg-gray-500/20 text-gray-400 border-gray-500/30';

  const formattedTime = event.timestamp
    ? format(parseISO(event.timestamp), 'h:mm:ss a')
    : 'Unknown time';

  return (
    <div
      className="relative flex items-start gap-4 pb-6"
      data-testid={`timeline-event-${event.eventId}`}
    >
      {/* Timeline connector line */}
      {index > 0 && (
        <div
          className="absolute left-3 top-0 h-full w-px -translate-x-1/2 bg-gray-700"
          aria-hidden="true"
        />
      )}

      {/* Timeline dot */}
      <div
        className={clsx(
          'relative z-10 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border',
          riskColorClass
        )}
        aria-hidden="true"
      >
        <div className="h-2 w-2 rounded-full bg-current" />
      </div>

      {/* Event content */}
      <div className="flex-1 pt-0.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-gray-200">{event.cameraName}</span>
          <span className="text-xs text-gray-500">{formattedTime}</span>
          {event.riskLevel && (
            <span
              className={clsx(
                'rounded-full border px-2 py-0.5 text-xs font-medium capitalize',
                riskColorClass
              )}
              data-testid={`risk-badge-${event.eventId}`}
            >
              {event.riskLevel}
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-gray-400">{event.summary}</p>
        {event.eventUrl && (
          <a
            href={event.eventUrl}
            className="mt-2 inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
            data-testid={`event-link-${event.eventId}`}
            tabIndex={0}
          >
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
            View event details
          </a>
        )}
      </div>
    </div>
  );
}

/**
 * Export button component.
 */
function ExportButton({
  format: _format,
  label,
  icon: Icon,
  onClick,
  isLoading,
  testId,
}: {
  format: ExportFormat;
  label: string;
  icon: typeof FileJson;
  onClick: () => void;
  isLoading: boolean;
  testId: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isLoading}
      className={clsx(
        'flex items-center gap-2 rounded-lg border border-gray-700 px-3 py-2 text-sm',
        'transition-colors hover:border-gray-600 hover:bg-gray-800/50',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2',
        'focus-visible:ring-offset-gray-900',
        isLoading && 'cursor-not-allowed opacity-50'
      )}
      data-testid={testId}
    >
      <Icon className="h-4 w-4 text-gray-400" aria-hidden="true" />
      <span className="text-gray-300">{isLoading ? 'Exporting...' : label}</span>
    </button>
  );
}

/**
 * ExpandableDetailPanel component.
 */
export function ExpandableDetailPanel({
  detail,
  isOpen,
  onClose,
  onExport,
  isExporting = false,
  exportFormat,
  className,
}: ExpandableDetailPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [reducedMotion, setReducedMotion] = useState(false);

  // Check for reduced motion preference
  useEffect(() => {
    setReducedMotion(prefersReducedMotion());

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handleChange = (e: MediaQueryListEvent) => {
      setReducedMotion(e.matches);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Focus management - focus close button when opened
  useEffect(() => {
    if (isOpen && closeButtonRef.current) {
      closeButtonRef.current.focus();
    }
  }, [isOpen]);

  // Handle Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Handle overlay click
  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [onClose]
  );

  // Handle export
  const handleExport = useCallback(
    (format: ExportFormat) => {
      if (onExport) {
        onExport(detail.id, format);
      }
    },
    [onExport, detail.id]
  );

  if (!isOpen) {
    return null;
  }

  const isHourly = detail.summaryType === 'hourly';
  const TypeIcon = isHourly ? Clock : Calendar;
  const typeLabel = isHourly ? 'Hourly Summary' : 'Daily Summary';

  // Format time window
  const windowStart = detail.windowStart ? format(parseISO(detail.windowStart), 'MMM d, h:mm a') : '';
  const windowEnd = detail.windowEnd ? format(parseISO(detail.windowEnd), 'h:mm a') : '';
  const generatedAgo = detail.generatedAt
    ? formatDistanceToNow(parseISO(detail.generatedAt), { addSuffix: true })
    : '';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      data-testid="detail-panel-overlay"
      onClick={handleOverlayClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          handleOverlayClick(e as unknown as React.MouseEvent);
        }
      }}
      role="button"
      tabIndex={-1}
      aria-label="Close dialog"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="detail-panel-title"
        className={clsx(
          'relative max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-xl border border-gray-700 bg-gray-900 shadow-2xl',
          !reducedMotion && 'animate-slide-in',
          className
        )}
        data-testid="expandable-detail-panel"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-700 px-6 py-4">
          <div className="flex items-center gap-3">
            <TypeIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
            <h2 id="detail-panel-title" className="text-lg font-semibold text-gray-100">
              {typeLabel}
            </h2>
            <span className="rounded-full bg-gray-800 px-2 py-0.5 text-xs text-gray-400">
              {detail.eventCount} {detail.eventCount === 1 ? 'event' : 'events'}
            </span>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200"
            aria-label="Close detail panel"
            data-testid="detail-panel-close"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="max-h-[calc(90vh-8rem)] overflow-y-auto px-6 py-4">
          {/* Narrative section */}
          <section className="mb-6">
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-500">
              Summary
            </h3>
            <div
              className="rounded-lg bg-gray-800/50 p-4 text-gray-300 leading-relaxed"
              data-testid="detail-narrative"
            >
              {detail.content}
            </div>

            {/* Metadata */}
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-gray-500">
              {detail.focusAreas && detail.focusAreas.length > 0 && (
                <div className="flex items-center gap-1">
                  <MapPin className="h-4 w-4" aria-hidden="true" />
                  <span>{detail.focusAreas.join(', ')}</span>
                </div>
              )}
              {detail.maxRiskScore !== undefined && (
                <div className="flex items-center gap-1">
                  <AlertCircle className="h-4 w-4" aria-hidden="true" />
                  <span>Max risk: {detail.maxRiskScore}</span>
                </div>
              )}
              <div className="flex items-center gap-1" data-testid="detail-time-window">
                <Clock className="h-4 w-4" aria-hidden="true" />
                <span>
                  {windowStart} - {windowEnd}
                </span>
              </div>
              <span className="text-gray-600">Generated {generatedAgo}</span>
            </div>
          </section>

          {/* Timeline section */}
          <section className="mb-6">
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-500">
              Timeline
            </h3>
            {detail.timeline.length > 0 ? (
              <div className="relative pl-2">
                {detail.timeline.map((event, index) => (
                  <TimelineEventRow key={event.eventId} event={event} index={index} />
                ))}
              </div>
            ) : (
              <div className="rounded-lg bg-gray-800/50 p-4 text-center text-gray-500">
                No events to display
              </div>
            )}
          </section>

          {/* Export section */}
          <section>
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-gray-500">
              Export
            </h3>
            <div className="flex flex-wrap gap-3">
              <ExportButton
                format="json"
                label="JSON"
                icon={FileJson}
                onClick={() => handleExport('json')}
                isLoading={isExporting && exportFormat === 'json'}
                testId="export-json-btn"
              />
              <ExportButton
                format="csv"
                label="CSV"
                icon={FileSpreadsheet}
                onClick={() => handleExport('csv')}
                isLoading={isExporting && exportFormat === 'csv'}
                testId="export-csv-btn"
              />
              <ExportButton
                format="pdf"
                label="PDF"
                icon={FileText}
                onClick={() => handleExport('pdf')}
                isLoading={isExporting && exportFormat === 'pdf'}
                testId="export-pdf-btn"
              />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default ExpandableDetailPanel;
