/**
 * TimelineScrubber component (NEM-2932)
 * Provides a visual timeline for navigating events.
 *
 * Features:
 * - Bar chart visualization of events per time bucket
 * - Color-coded severity indicators (NVIDIA green #76B900 for low)
 * - Click-to-navigate to specific time periods
 * - Zoom controls (hour/day/week view)
 * - Current viewport indicator
 * - Keyboard accessible
 * - Dark theme consistent with existing UI
 */

import { useCallback, useMemo, useRef, useState } from 'react';

// Severity level type
export type Severity = 'low' | 'medium' | 'high' | 'critical';

// Zoom level for timeline granularity
export type ZoomLevel = 'hour' | 'day' | 'week';

// Single bucket in the timeline
export interface TimelineBucket {
  timestamp: string;
  eventCount: number;
  maxSeverity: Severity;
}

// Time range for selection/viewport
export interface TimeRange {
  startDate: string;
  endDate: string;
}

// Props for the TimelineScrubber component
export interface TimelineScrubberProps {
  /** Bucketed event data to display */
  buckets: TimelineBucket[];
  /** Callback when user selects a time range */
  onTimeRangeChange: (range: TimeRange) => void;
  /** Current zoom level */
  zoomLevel: ZoomLevel;
  /** Callback when zoom level changes */
  onZoomChange?: (level: ZoomLevel) => void;
  /** Current viewport range to highlight */
  currentRange?: TimeRange;
  /** Loading state */
  isLoading?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// Severity color mapping - NVIDIA green (#76B900) for low severity
const SEVERITY_COLORS: Record<Severity, string> = {
  low: 'bg-green-500', // NVIDIA green approximation in Tailwind
  medium: 'bg-yellow-500',
  high: 'bg-orange-500',
  critical: 'bg-red-500',
};

/**
 * Loading skeleton for the timeline scrubber
 */
function TimelineScrubberSkeleton() {
  return (
    <div
      data-testid="timeline-scrubber-skeleton"
      className="h-32 animate-pulse rounded-lg border border-gray-800 bg-[#1F1F1F] p-4"
    >
      <div className="flex h-full items-end gap-1">
        {Array.from({ length: 24 }, (_, i) => (
          <div
            key={i}
            className="flex-1 rounded-t bg-gray-700"
            style={{ height: `${Math.random() * 60 + 20}%` }}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Zoom control buttons
 */
function ZoomControls({
  zoomLevel,
  onZoomChange,
}: {
  zoomLevel: ZoomLevel;
  onZoomChange?: (level: ZoomLevel) => void;
}) {
  const levels: ZoomLevel[] = ['hour', 'day', 'week'];

  return (
    <div
      role="group"
      aria-label="Zoom controls"
      className="flex gap-1 rounded-md border border-gray-700 bg-[#1A1A1A] p-1"
    >
      {levels.map((level) => (
        <button
          key={level}
          onClick={() => onZoomChange?.(level)}
          className={`rounded px-3 py-1 text-xs font-medium capitalize transition-colors ${
            zoomLevel === level
              ? 'bg-[#76B900] text-black'
              : 'text-gray-400 hover:bg-gray-700 hover:text-white'
          }`}
          aria-pressed={zoomLevel === level}
        >
          {level}
        </button>
      ))}
    </div>
  );
}

/**
 * Tooltip component for bar hover
 */
function Tooltip({
  bucket,
  position,
  zoomLevel,
}: {
  bucket: TimelineBucket;
  position: { x: number; y: number };
  zoomLevel: ZoomLevel;
}) {
  const formattedTime = useMemo(() => {
    const date = new Date(bucket.timestamp);
    if (zoomLevel === 'hour') {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (zoomLevel === 'day') {
      return date.toLocaleTimeString([], { hour: 'numeric', hour12: true });
    } else {
      return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
    }
  }, [bucket.timestamp, zoomLevel]);

  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-50 rounded-md border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-sm shadow-lg"
      style={{
        left: position.x,
        top: position.y - 60,
        transform: 'translateX(-50%)',
      }}
    >
      <div className="font-medium text-white">{formattedTime}</div>
      <div className="text-gray-400">
        {bucket.eventCount} event{bucket.eventCount !== 1 ? 's' : ''}
      </div>
      <div className="capitalize text-gray-400">Max severity: {bucket.maxSeverity}</div>
    </div>
  );
}

/**
 * Single bar in the timeline chart
 */
function TimelineBar({
  bucket,
  index,
  maxCount,
  isSelected,
  onClick,
  onHover,
}: {
  bucket: TimelineBucket;
  index: number;
  maxCount: number;
  isSelected: boolean;
  onClick: () => void;
  onHover: (event: React.MouseEvent | null) => void;
}) {
  // Calculate bar height (min 4px for zero events, max 100%)
  const heightPercent = maxCount > 0 ? Math.max(4, (bucket.eventCount / maxCount) * 100) : 4;

  return (
    <button
      data-testid="timeline-bar"
      data-severity={bucket.maxSeverity}
      data-bucket-index={index}
      className={`relative flex-1 rounded-t transition-all hover:opacity-80 ${
        SEVERITY_COLORS[bucket.maxSeverity]
      } ${isSelected ? 'ring-2 ring-white ring-offset-1 ring-offset-[#1F1F1F]' : ''}`}
      style={{ height: `${heightPercent}%` }}
      onClick={onClick}
      onMouseEnter={onHover}
      onMouseLeave={() => onHover(null)}
      aria-label={`${bucket.eventCount} events at ${new Date(bucket.timestamp).toLocaleString()}, ${bucket.maxSeverity} severity`}
    />
  );
}

/**
 * Format time label based on zoom level
 */
function formatTimeLabel(timestamp: string, zoomLevel: ZoomLevel): string {
  const date = new Date(timestamp);
  if (zoomLevel === 'hour') {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } else if (zoomLevel === 'day') {
    const hours = date.getHours();
    const suffix = hours >= 12 ? 'PM' : 'AM';
    const hour = hours % 12 || 12;
    return `${hour} ${suffix}`;
  } else {
    return date.toLocaleDateString([], { weekday: 'short' });
  }
}

/**
 * TimelineScrubber displays a visual timeline of event activity
 * allowing users to navigate and filter by time periods.
 */
export default function TimelineScrubber({
  buckets,
  onTimeRangeChange,
  zoomLevel,
  onZoomChange,
  currentRange,
  isLoading = false,
  className = '',
}: TimelineScrubberProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredBucket, setHoveredBucket] = useState<{
    bucket: TimelineBucket;
    position: { x: number; y: number };
  } | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartIndex, setDragStartIndex] = useState<number | null>(null);

  // Calculate max event count for scaling bars
  const maxCount = useMemo(() => {
    return Math.max(...buckets.map((b) => b.eventCount), 1);
  }, [buckets]);

  // Calculate total events
  const totalEvents = useMemo(() => {
    return buckets.reduce((sum, b) => sum + b.eventCount, 0);
  }, [buckets]);

  // Calculate time range span
  const timeRangeText = useMemo(() => {
    if (buckets.length < 2) return '';
    const first = new Date(buckets[0].timestamp);
    const last = new Date(buckets[buckets.length - 1].timestamp);
    const diffMs = last.getTime() - first.getTime();
    const diffHours = Math.round(diffMs / (1000 * 60 * 60));
    if (diffHours < 24) {
      return `${diffHours} hour${diffHours !== 1 ? 's' : ''}`;
    }
    const diffDays = Math.round(diffHours / 24);
    return `${diffDays} day${diffDays !== 1 ? 's' : ''}`;
  }, [buckets]);

  // Generate time labels (show every nth bucket for readability)
  const timeLabels = useMemo(() => {
    if (buckets.length === 0) return [];
    const labelInterval = Math.max(1, Math.floor(buckets.length / 6));
    const labels: { index: number; label: string }[] = [];
    for (let i = 0; i < buckets.length; i += labelInterval) {
      labels.push({
        index: i,
        label: formatTimeLabel(buckets[i].timestamp, zoomLevel),
      });
    }
    return labels;
  }, [buckets, zoomLevel]);

  // Calculate viewport indicator position
  const viewportPosition = useMemo(() => {
    if (!currentRange || buckets.length === 0) return null;

    const rangeStart = new Date(currentRange.startDate).getTime();
    const rangeEnd = new Date(currentRange.endDate).getTime();
    const timelineStart = new Date(buckets[0].timestamp).getTime();
    const timelineEnd = new Date(buckets[buckets.length - 1].timestamp).getTime();
    const timelineSpan = timelineEnd - timelineStart;

    if (timelineSpan === 0) return null;

    const leftPercent = ((rangeStart - timelineStart) / timelineSpan) * 100;
    const widthPercent = ((rangeEnd - rangeStart) / timelineSpan) * 100;

    return {
      left: Math.max(0, Math.min(100, leftPercent)),
      width: Math.max(1, Math.min(100 - leftPercent, widthPercent)),
    };
  }, [currentRange, buckets]);

  // Handle bar click
  const handleBarClick = useCallback(
    (index: number) => {
      if (buckets[index]) {
        const bucket = buckets[index];
        // Calculate time range for this bucket
        const startDate = bucket.timestamp;
        // Estimate end date based on zoom level
        const bucketDuration =
          zoomLevel === 'hour' ? 5 * 60 * 1000 : zoomLevel === 'day' ? 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
        const endDate = new Date(new Date(startDate).getTime() + bucketDuration).toISOString();

        setSelectedIndex(index);
        onTimeRangeChange({ startDate, endDate });
      }
    },
    [buckets, zoomLevel, onTimeRangeChange]
  );

  // Handle bar hover
  const handleBarHover = useCallback(
    (index: number, event: React.MouseEvent | null) => {
      if (event && buckets[index]) {
        const rect = event.currentTarget.getBoundingClientRect();
        setHoveredBucket({
          bucket: buckets[index],
          position: {
            x: rect.left + rect.width / 2,
            y: rect.top,
          },
        });
      } else {
        setHoveredBucket(null);
      }
    },
    [buckets]
  );

  // Handle drag selection
  const handleMouseDown = useCallback(
    (event: React.MouseEvent) => {
      if (!containerRef.current || buckets.length === 0) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const index = Math.floor((x / rect.width) * buckets.length);

      setIsDragging(true);
      setDragStartIndex(index);
    },
    [buckets.length]
  );

  const handleMouseMove = useCallback(
    (event: React.MouseEvent) => {
      if (!isDragging || !containerRef.current || dragStartIndex === null) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const currentIndex = Math.floor((x / rect.width) * buckets.length);

      // Visual feedback could be added here
      void currentIndex;
    },
    [isDragging, dragStartIndex, buckets.length]
  );

  const handleMouseUp = useCallback(
    (event: React.MouseEvent) => {
      if (!isDragging || !containerRef.current || dragStartIndex === null) return;

      const rect = containerRef.current.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const endIndex = Math.min(Math.max(0, Math.floor((x / rect.width) * buckets.length)), buckets.length - 1);

      const startIndex = Math.min(dragStartIndex, endIndex);
      const finalEndIndex = Math.max(dragStartIndex, endIndex);

      if (startIndex !== finalEndIndex && buckets[startIndex] && buckets[finalEndIndex]) {
        const startDate = buckets[startIndex].timestamp;
        const bucketDuration =
          zoomLevel === 'hour' ? 5 * 60 * 1000 : zoomLevel === 'day' ? 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
        const endDate = new Date(
          new Date(buckets[finalEndIndex].timestamp).getTime() + bucketDuration
        ).toISOString();

        onTimeRangeChange({ startDate, endDate });
      }

      setIsDragging(false);
      setDragStartIndex(null);
    },
    [isDragging, dragStartIndex, buckets, zoomLevel, onTimeRangeChange]
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (buckets.length === 0) return;

      let newIndex = selectedIndex;

      switch (event.key) {
        case 'ArrowLeft':
          newIndex = Math.max(0, selectedIndex - 1);
          break;
        case 'ArrowRight':
          newIndex = Math.min(buckets.length - 1, selectedIndex + 1);
          break;
        case 'Home':
          newIndex = 0;
          break;
        case 'End':
          newIndex = buckets.length - 1;
          break;
        case 'Enter':
        case ' ':
          handleBarClick(selectedIndex);
          event.preventDefault();
          return;
        default:
          return;
      }

      if (newIndex !== selectedIndex) {
        setSelectedIndex(newIndex);
        handleBarClick(newIndex);
        event.preventDefault();
      }
    },
    [buckets.length, selectedIndex, handleBarClick]
  );

  // Show loading skeleton
  if (isLoading) {
    return <TimelineScrubberSkeleton />;
  }

  // Show empty state
  if (buckets.length === 0) {
    return (
      <div
        data-testid="timeline-scrubber"
        className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
      >
        <p className="text-center text-sm text-gray-400">No events in selected range</p>
      </div>
    );
  }

  return (
    <div
      data-testid="timeline-scrubber"
      className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 ${className}`}
    >
      {/* Header with zoom controls and stats */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <ZoomControls zoomLevel={zoomLevel} onZoomChange={onZoomChange} />
          <span className="text-sm text-gray-400">
            {totalEvents} event{totalEvents !== 1 ? 's' : ''} in {timeRangeText}
          </span>
        </div>
      </div>

      {/* Timeline bars container */}
      <div
        role="slider"
        aria-label="Timeline scrubber"
        aria-valuemin={0}
        aria-valuemax={buckets.length - 1}
        aria-valuenow={selectedIndex}
        tabIndex={0}
        ref={containerRef}
        data-testid="timeline-bars-container"
        className="relative h-16 cursor-pointer"
        onKeyDown={handleKeyDown}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          if (isDragging) {
            setIsDragging(false);
            setDragStartIndex(null);
          }
        }}
      >
        {/* Bars */}
        <div className="flex h-full items-end gap-px">
          {buckets.map((bucket, index) => (
            <TimelineBar
              key={bucket.timestamp}
              bucket={bucket}
              index={index}
              maxCount={maxCount}
              isSelected={index === selectedIndex}
              onClick={() => handleBarClick(index)}
              onHover={(event) => handleBarHover(index, event)}
            />
          ))}
        </div>

        {/* Viewport indicator */}
        {viewportPosition && (
          <div
            data-testid="viewport-indicator"
            className="pointer-events-none absolute bottom-0 top-0 border-2 border-[#76B900] bg-[#76B900]/10"
            style={{
              left: `${viewportPosition.left}%`,
              width: `${viewportPosition.width}%`,
            }}
          />
        )}
      </div>

      {/* Time labels */}
      <div className="mt-2 flex justify-between">
        {timeLabels.map(({ index, label }) => (
          <span
            key={index}
            data-testid="time-label"
            className="text-xs text-gray-400"
            style={{
              position: 'relative',
              left: `${(index / (buckets.length - 1)) * 100}%`,
              transform: 'translateX(-50%)',
            }}
          >
            {label}
          </span>
        ))}
      </div>

      {/* Tooltip */}
      {hoveredBucket && (
        <Tooltip
          bucket={hoveredBucket.bucket}
          position={hoveredBucket.position}
          zoomLevel={zoomLevel}
        />
      )}
    </div>
  );
}
