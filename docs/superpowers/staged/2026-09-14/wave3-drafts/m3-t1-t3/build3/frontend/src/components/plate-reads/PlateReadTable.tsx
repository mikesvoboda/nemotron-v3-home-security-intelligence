/**
 * PlateReadTable - Paginated table for displaying plate reads
 *
 * Displays plate read data in a sortable, paginated table with
 * search text highlighting and click handlers for detail view.
 *
 * @module components/plate-reads/PlateReadTable
 * @see frontend/src/types/plateRead.ts - Type definitions
 */

import { clsx } from 'clsx';
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Eye,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import { memo, useCallback, useMemo } from 'react';

import { VehicleMatchBadge } from './VehicleMatchBadge';
import { formatConfidence, getQualityLabel, getConfidenceLevel } from '../../types/plateRead';

import type { PlateRead } from '../../types/plateRead';

// ============================================================================
// Types
// ============================================================================

export interface PlateReadTableProps {
  /** Array of plate reads to display */
  plateReads: PlateRead[];
  /** Total number of plate reads (for pagination) */
  total: number;
  /** Current page number (1-indexed) */
  page: number;
  /** Number of items per page */
  pageSize: number;
  /** Called when page changes */
  onPageChange: (page: number) => void;
  /** Called when page size changes */
  onPageSizeChange?: (pageSize: number) => void;
  /** Called when a row is clicked */
  onRowClick?: (plateRead: PlateRead) => void;
  /** Search text to highlight in plate text column */
  searchText?: string;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Optional class name */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format a timestamp for display.
 */
function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
}

/**
 * Highlight matching text in a string.
 */
function highlightText(text: string, searchText: string): React.ReactNode {
  if (!searchText) {
    return text;
  }

  const lowerText = text.toLowerCase();
  const lowerSearch = searchText.toLowerCase();
  const index = lowerText.indexOf(lowerSearch);

  if (index === -1) {
    return text;
  }

  const before = text.slice(0, index);
  const match = text.slice(index, index + searchText.length);
  const after = text.slice(index + searchText.length);

  return (
    <>
      {before}
      <mark className="rounded bg-[#76B900]/30 px-0.5 text-white">{match}</mark>
      {after}
    </>
  );
}

/**
 * Get the CSS class for confidence level badge.
 */
function getConfidenceBadgeClass(confidence: number): string {
  const level = getConfidenceLevel(confidence);
  switch (level) {
    case 'high':
      return 'bg-green-500/20 text-green-400';
    case 'medium':
      return 'bg-yellow-500/20 text-yellow-400';
    case 'low':
      return 'bg-red-500/20 text-red-400';
  }
}

/**
 * Get the CSS class for quality label.
 */
function getQualityBadgeClass(score: number): string {
  const label = getQualityLabel(score);
  switch (label) {
    case 'Excellent':
      return 'bg-green-500/20 text-green-400';
    case 'Good':
      return 'bg-blue-500/20 text-blue-400';
    case 'Fair':
      return 'bg-yellow-500/20 text-yellow-400';
    case 'Poor':
      return 'bg-red-500/20 text-red-400';
  }
}

// ============================================================================
// Page Size Options
// ============================================================================

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

// ============================================================================
// Component
// ============================================================================

/**
 * PlateReadTable component for displaying plate reads in a paginated table.
 *
 * Features:
 * - Paginated display with configurable page size
 * - Search text highlighting in plate text column
 * - Confidence and quality score badges
 * - Enhanced/blurry indicators
 * - Row click handler for detail view
 * - Empty state handling
 * - Loading skeleton state
 *
 * @example
 * ```tsx
 * <PlateReadTable
 *   plateReads={data}
 *   total={100}
 *   page={1}
 *   pageSize={25}
 *   onPageChange={setPage}
 *   onRowClick={(read) => setSelectedRead(read)}
 *   searchText="ABC"
 * />
 * ```
 */
const PlateReadTable = memo(function PlateReadTable({
  plateReads,
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  onRowClick,
  searchText = '',
  isLoading = false,
  className,
}: PlateReadTableProps) {
  // Calculate pagination values
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  // Pagination handlers
  const handleFirstPage = useCallback(() => onPageChange(1), [onPageChange]);
  const handlePrevPage = useCallback(
    () => onPageChange(Math.max(1, page - 1)),
    [onPageChange, page]
  );
  const handleNextPage = useCallback(
    () => onPageChange(Math.min(totalPages, page + 1)),
    [onPageChange, page, totalPages]
  );
  const handleLastPage = useCallback(() => onPageChange(totalPages), [onPageChange, totalPages]);

  // Handle row click
  const handleRowClick = useCallback(
    (plateRead: PlateRead) => {
      if (onRowClick) {
        onRowClick(plateRead);
      }
    },
    [onRowClick]
  );

  // Handle row key down (for accessibility)
  const handleRowKeyDown = useCallback(
    (e: React.KeyboardEvent, plateRead: PlateRead) => {
      if ((e.key === 'Enter' || e.key === ' ') && onRowClick) {
        e.preventDefault();
        onRowClick(plateRead);
      }
    },
    [onRowClick]
  );

  // Loading skeleton rows
  const skeletonRows = useMemo(
    () =>
      Array.from({ length: pageSize }, (_, i) => (
        <tr key={`skeleton-${i}`} className="border-b border-gray-800">
          <td className="px-4 py-3">
            <div className="h-4 w-24 animate-pulse rounded bg-gray-700" />
          </td>
          <td className="px-4 py-3">
            <div className="h-4 w-20 animate-pulse rounded bg-gray-700" />
          </td>
          <td className="px-4 py-3">
            <div className="h-6 w-20 animate-pulse rounded bg-gray-700" />
          </td>
          <td className="px-4 py-3">
            <div className="h-5 w-16 animate-pulse rounded bg-gray-700" />
          </td>
          <td className="px-4 py-3">
            <div className="h-5 w-12 animate-pulse rounded bg-gray-700" />
          </td>
          <td className="px-4 py-3">
            <div className="h-5 w-14 animate-pulse rounded bg-gray-700" />
          </td>
          <td className="px-4 py-3">
            <div className="h-8 w-8 animate-pulse rounded bg-gray-700" />
          </td>
        </tr>
      )),
    [pageSize]
  );

  return (
    <div className={clsx('flex flex-col', className)}>
      {/* Table Container */}
      <div className="overflow-x-auto rounded-lg border border-gray-800">
        <table className="w-full text-left text-sm">
          {/* Table Header */}
          <thead className="bg-[#1A1A1A] text-xs uppercase text-gray-400">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">
                Timestamp
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Camera
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Plate Text
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Status
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Confidence
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Quality
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Actions
              </th>
            </tr>
          </thead>

          {/* Table Body */}
          <tbody className="divide-y divide-gray-800 bg-[#0D0D0D]">
            {isLoading ? (
              // Loading skeleton
              skeletonRows
            ) : plateReads.length === 0 ? (
              // Empty state
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center">
                  <AlertCircle className="mx-auto h-12 w-12 text-gray-600" />
                  <p className="mt-4 text-lg font-medium text-gray-400">No plate reads found</p>
                  <p className="mt-1 text-sm text-gray-500">
                    {searchText
                      ? `No plates matching "${searchText}"`
                      : 'Try adjusting your filters or check back later'}
                  </p>
                </td>
              </tr>
            ) : (
              // Data rows
              plateReads.map((plateRead) => (
                <tr
                  key={plateRead.id}
                  onClick={() => handleRowClick(plateRead)}
                  onKeyDown={(e) => handleRowKeyDown(e, plateRead)}
                  tabIndex={onRowClick ? 0 : undefined}
                  role={onRowClick ? 'button' : undefined}
                  className={clsx(
                    'transition-colors',
                    onRowClick &&
                      'cursor-pointer hover:bg-[#1A1A1A] focus:bg-[#1A1A1A] focus:outline-none focus:ring-1 focus:ring-inset focus:ring-[#76B900]'
                  )}
                >
                  {/* Timestamp */}
                  <td className="whitespace-nowrap px-4 py-3 text-gray-300">
                    {formatTimestamp(plateRead.timestamp)}
                  </td>

                  {/* Camera */}
                  <td className="px-4 py-3 text-gray-300">{plateRead.camera_id}</td>

                  {/* Plate Text */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-base font-semibold text-white">
                        {highlightText(plateRead.plate_text, searchText)}
                      </span>
                      {/* Enhancement indicator */}
                      {plateRead.is_enhanced && (
                        <Sparkles
                          className="h-4 w-4 text-blue-400"
                          aria-label="Low-light enhanced"
                        />
                      )}
                      {/* Blur indicator */}
                      {plateRead.is_blurry && (
                        <AlertCircle
                          className="h-4 w-4 text-yellow-400"
                          aria-label="Motion blur detected"
                        />
                      )}
                    </div>
                  </td>

                  {/* Vehicle Match Status */}
                  <td className="px-4 py-3">
                    <VehicleMatchBadge plateText={plateRead.plate_text} size="sm" />
                  </td>

                  {/* Confidence */}
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                        getConfidenceBadgeClass(plateRead.ocr_confidence)
                      )}
                    >
                      {formatConfidence(plateRead.ocr_confidence)}
                    </span>
                  </td>

                  {/* Quality */}
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                        getQualityBadgeClass(plateRead.image_quality_score)
                      )}
                    >
                      {getQualityLabel(plateRead.image_quality_score)}
                    </span>
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRowClick(plateRead);
                      }}
                      className={clsx(
                        'rounded-md p-2 text-gray-400 transition-colors',
                        'hover:bg-gray-700 hover:text-white',
                        'focus:outline-none focus:ring-1 focus:ring-[#76B900]'
                      )}
                      aria-label={`View details for plate ${plateRead.plate_text}`}
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {total > 0 && (
        <div className="mt-4 flex items-center justify-between">
          {/* Items info */}
          <div className="text-sm text-gray-400">
            Showing <span className="font-medium text-gray-200">{startItem}</span> to{' '}
            <span className="font-medium text-gray-200">{endItem}</span> of{' '}
            <span className="font-medium text-gray-200">{total}</span> results
          </div>

          {/* Pagination buttons and page size selector */}
          <div className="flex items-center gap-4">
            {/* Page size selector */}
            {onPageSizeChange && (
              <div className="flex items-center gap-2">
                <label htmlFor="plate-table-page-size" className="text-sm text-gray-400">
                  Per page:
                </label>
                <select
                  id="plate-table-page-size"
                  value={pageSize}
                  onChange={(e) => onPageSizeChange(Number(e.target.value))}
                  className={clsx(
                    'rounded-md border border-gray-700 bg-[#1A1A1A] px-2 py-1 text-sm text-white',
                    'focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]'
                  )}
                >
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Page navigation */}
            <div className="flex items-center gap-1">
              <button
                onClick={handleFirstPage}
                disabled={page === 1}
                className={clsx(
                  'rounded-md p-1.5 text-gray-400 transition-colors',
                  'hover:bg-gray-700 hover:text-white',
                  'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-gray-400'
                )}
                aria-label="First page"
              >
                <ChevronsLeft className="h-4 w-4" />
              </button>
              <button
                onClick={handlePrevPage}
                disabled={page === 1}
                className={clsx(
                  'rounded-md p-1.5 text-gray-400 transition-colors',
                  'hover:bg-gray-700 hover:text-white',
                  'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-gray-400'
                )}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              <span className="px-3 text-sm text-gray-300">
                Page <span className="font-medium text-white">{page}</span> of{' '}
                <span className="font-medium text-white">{totalPages}</span>
              </span>

              <button
                onClick={handleNextPage}
                disabled={page === totalPages}
                className={clsx(
                  'rounded-md p-1.5 text-gray-400 transition-colors',
                  'hover:bg-gray-700 hover:text-white',
                  'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-gray-400'
                )}
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
              <button
                onClick={handleLastPage}
                disabled={page === totalPages}
                className={clsx(
                  'rounded-md p-1.5 text-gray-400 transition-colors',
                  'hover:bg-gray-700 hover:text-white',
                  'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-gray-400'
                )}
                aria-label="Last page"
              >
                <ChevronsRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

export default PlateReadTable;
