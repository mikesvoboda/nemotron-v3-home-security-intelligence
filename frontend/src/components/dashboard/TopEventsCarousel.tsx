/**
 * TopEventsCarousel - Horizontal carousel of highest-risk events
 *
 * Displays thumbnails of the top N events by risk score, with:
 * - Horizontal scrolling with navigation arrows
 * - Framer Motion animations
 * - Expand/collapse to show more events
 * - Lazy loading images
 * - Accessibility support (keyboard nav, ARIA labels)
 * - Placeholder for missing thumbnails
 *
 * NEM-5412/5413/5414/5415: Feature 6 - Top Events Preview Carousel
 *
 * @module components/dashboard/TopEventsCarousel
 */

import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { ChevronLeft, ChevronRight, AlertTriangle, ImageOff } from 'lucide-react';
import { useCallback, useMemo, useRef, useState, useEffect } from 'react';

import { fetchEvents } from '../../services/api';
import { getRiskLevel } from '../../utils/risk';
import RiskBadge from '../common/RiskBadge';

import type { Event } from '../../types/generated';

// ============================================================================
// Types
// ============================================================================

export interface TopEventsCarouselProps {
  /**
   * Number of thumbnails to show initially
   * @default 5
   */
  count?: number;

  /**
   * Number of thumbnails to show when expanded
   * @default 10
   */
  expandedCount?: number;

  /**
   * Callback when a thumbnail is clicked
   */
  onEventClick?: (eventId: number) => void;

  /**
   * Custom title for the carousel header
   * @default "Top Events"
   */
  title?: string;

  /**
   * Additional CSS classes
   */
  className?: string;
}

// ============================================================================
// Query Keys
// ============================================================================

export const topEventsQueryKeys = {
  all: ['events', 'top'] as const,
  list: (count: number) => [...topEventsQueryKeys.all, { count }] as const,
};

// ============================================================================
// Component
// ============================================================================

/**
 * TopEventsCarousel displays a horizontal scrollable carousel of the highest-risk events.
 * Events are sorted by risk_score in descending order.
 */
export default function TopEventsCarousel({
  count = 5,
  expandedCount = 10,
  onEventClick,
  title = 'Top Events',
  className = '',
}: TopEventsCarouselProps) {
  const prefersReducedMotion = useReducedMotion();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Fetch events sorted by risk_score descending
  // We fetch more than needed to support expand functionality
  const maxCount = Math.max(count, expandedCount);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: topEventsQueryKeys.list(maxCount),
    queryFn: () =>
      fetchEvents({
        limit: maxCount,
        // Note: The API should sort by risk_score desc by default for this use case
        // If not, we'll sort client-side
      }),
    staleTime: 30000, // 30 seconds
    retry: 1,
  });

  // Sort events by risk_score (highest first) and slice to display count
  const displayEvents = useMemo(() => {
    if (!data?.items) return [];

    // Sort by risk_score descending
    const sorted = [...data.items].sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0));

    // Return count based on expanded state
    const displayCount = isExpanded ? expandedCount : count;
    return sorted.slice(0, displayCount);
  }, [data?.items, count, expandedCount, isExpanded]);

  // Total available events (for determining if expand is possible)
  const totalAvailable = useMemo(() => {
    if (!data?.items) return 0;
    return Math.min(data.items.length, expandedCount);
  }, [data?.items, expandedCount]);

  // Determine if expand button should be shown
  const canExpand = totalAvailable > count;

  // Update scroll button states
  const updateScrollState = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    setCanScrollLeft(container.scrollLeft > 0);
    setCanScrollRight(container.scrollLeft < container.scrollWidth - container.clientWidth - 1);
  }, []);

  // Set up scroll event listener
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    updateScrollState();
    container.addEventListener('scroll', updateScrollState);
    window.addEventListener('resize', updateScrollState);

    return () => {
      container.removeEventListener('scroll', updateScrollState);
      window.removeEventListener('resize', updateScrollState);
    };
  }, [updateScrollState, displayEvents]);

  // Scroll handlers
  const scrollLeft = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    container.scrollBy({ left: -200, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
  }, [prefersReducedMotion]);

  const scrollRight = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    container.scrollBy({ left: 200, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
  }, [prefersReducedMotion]);

  // Handle thumbnail click
  const handleThumbnailClick = useCallback(
    (eventId: number) => {
      onEventClick?.(eventId);
    },
    [onEventClick]
  );

  // Handle keyboard navigation on thumbnails
  const handleThumbnailKeyDown = useCallback(
    (e: React.KeyboardEvent, eventId: number) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onEventClick?.(eventId);
      }
    },
    [onEventClick]
  );

  // Toggle expand/collapse
  const handleToggleExpand = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  // Animation variants
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: prefersReducedMotion ? 0 : 0.05,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, scale: 0.9 },
    visible: {
      opacity: 1,
      scale: 1,
      transition: { duration: prefersReducedMotion ? 0 : 0.2 },
    },
    exit: {
      opacity: 0,
      scale: 0.9,
      transition: { duration: prefersReducedMotion ? 0 : 0.15 },
    },
  };

  // Build class names
  const carouselClasses = [
    'relative',
    'rounded-lg',
    'border',
    'border-gray-800',
    'bg-[#1A1A1A]',
    'p-4',
    prefersReducedMotion ? 'motion-reduce' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={carouselClasses}
      data-testid="top-events-carousel"
      role="region"
      aria-label="Top risk events"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        {canExpand && (
          <button
            onClick={handleToggleExpand}
            className="text-sm font-medium text-[#76B900] hover:text-[#88d200] transition-colors"
            aria-expanded={isExpanded}
          >
            {isExpanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div
          className="flex items-center justify-center py-8"
          data-testid="top-events-loading"
          aria-busy="true"
        >
          <div className="flex items-center gap-2 text-gray-400">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-gray-600 border-t-[#76B900]" />
            <span>Loading top events...</span>
          </div>
        </div>
      )}

      {/* Error State */}
      {isError && (
        <div
          className="flex flex-col items-center justify-center py-8 text-red-400"
          data-testid="top-events-error"
        >
          <AlertTriangle className="mb-2 h-8 w-8" />
          <p className="text-sm">Failed to load events</p>
          {error instanceof Error && (
            <p className="mt-1 text-xs text-gray-500">{error.message}</p>
          )}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !isError && displayEvents.length === 0 && (
        <div
          className="flex flex-col items-center justify-center py-8 text-gray-400"
          data-testid="top-events-empty"
        >
          <ImageOff className="mb-2 h-8 w-8" />
          <p className="text-sm">No high-risk events found</p>
        </div>
      )}

      {/* Carousel Content */}
      {!isLoading && !isError && displayEvents.length > 0 && (
        <div className="relative">
          {/* Left Navigation Arrow */}
          <button
            onClick={scrollLeft}
            disabled={!canScrollLeft}
            className="absolute left-0 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/70 p-2 text-white transition-all hover:bg-black/90 disabled:cursor-not-allowed disabled:opacity-30"
            aria-label="Scroll left"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>

          {/* Right Navigation Arrow */}
          <button
            onClick={scrollRight}
            disabled={!canScrollRight}
            className="absolute right-0 top-1/2 z-10 -translate-y-1/2 rounded-full bg-black/70 p-2 text-white transition-all hover:bg-black/90 disabled:cursor-not-allowed disabled:opacity-30"
            aria-label="Scroll right"
          >
            <ChevronRight className="h-5 w-5" />
          </button>

          {/* Scrollable Container */}
          <div
            ref={scrollContainerRef}
            className="mx-8 flex gap-3 overflow-x-auto scroll-smooth scrollbar-hide"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            <AnimatePresence mode="popLayout">
              <motion.div
                className="flex gap-3"
                variants={containerVariants}
                initial="hidden"
                animate="visible"
              >
                {displayEvents.map((event) => (
                  <EventThumbnail
                    key={event.id}
                    event={event}
                    onClick={handleThumbnailClick}
                    onKeyDown={handleThumbnailKeyDown}
                    variants={itemVariants}
                    prefersReducedMotion={prefersReducedMotion ?? false}
                  />
                ))}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Event Thumbnail Sub-component
// ============================================================================

interface EventThumbnailProps {
  event: Event;
  onClick: (eventId: number) => void;
  onKeyDown: (e: React.KeyboardEvent, eventId: number) => void;
  variants: {
    hidden: { opacity: number; scale: number };
    visible: { opacity: number; scale: number; transition: { duration: number } };
    exit: { opacity: number; scale: number; transition: { duration: number } };
  };
  prefersReducedMotion: boolean;
}

function EventThumbnail({
  event,
  onClick,
  onKeyDown,
  variants,
  prefersReducedMotion,
}: EventThumbnailProps) {
  const [imageError, setImageError] = useState(false);
  const eventId = typeof event.id === 'number' ? event.id : parseInt(String(event.id), 10);
  const riskScore = event.risk_score ?? 0;
  const riskLevel = getRiskLevel(riskScore);
  // Use camera_id as display name - the Event type doesn't include camera_name
  const cameraName = event.camera_id ?? 'Unknown Camera';

  const hasThumbnail = event.thumbnail_url && !imageError;

  // Determine risk-based border color
  const borderColorClass =
    riskLevel === 'critical'
      ? 'border-red-500'
      : riskLevel === 'high'
        ? 'border-orange-500'
        : riskLevel === 'medium'
          ? 'border-yellow-500'
          : 'border-gray-600';

  return (
    <motion.div
      className={`relative flex-shrink-0 cursor-pointer overflow-hidden rounded-lg border-2 ${borderColorClass} transition-all hover:scale-105 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]`}
      style={{ width: 120, height: 90 }}
      onClick={() => onClick(eventId)}
      onKeyDown={(e) => onKeyDown(e, eventId)}
      tabIndex={0}
      role="button"
      aria-label={`Event from ${cameraName}, risk score ${riskScore}`}
      data-testid={`top-event-thumbnail-${eventId}`}
      variants={prefersReducedMotion ? undefined : variants}
      layout={!prefersReducedMotion}
    >
      {hasThumbnail ? (
        <img
          src={event.thumbnail_url ?? ''}
          alt={`${cameraName} event`}
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setImageError(true)}
        />
      ) : (
        <div
          className="flex h-full w-full items-center justify-center bg-gray-800"
          data-testid={`top-event-placeholder-${eventId}`}
        >
          <ImageOff className="h-6 w-6 text-gray-500" />
        </div>
      )}

      {/* Risk Score Badge */}
      <div className="absolute bottom-1 right-1">
        <RiskBadge level={riskLevel} score={riskScore} showScore={true} size="sm" />
      </div>

      {/* Camera Name Overlay */}
      <div className="absolute left-0 right-0 top-0 bg-gradient-to-b from-black/70 to-transparent px-2 py-1">
        <p className="truncate text-xs font-medium text-white">{cameraName}</p>
      </div>
    </motion.div>
  );
}
