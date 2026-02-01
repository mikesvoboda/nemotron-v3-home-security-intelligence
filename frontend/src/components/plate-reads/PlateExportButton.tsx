/**
 * PlateExportButton Component
 *
 * Export button for plate reads data with CSV support.
 * Follows the pattern from ExportButton.tsx but tailored for plate reads.
 *
 * @see frontend/src/components/ExportButton.tsx - Similar pattern
 * @see frontend/src/services/plateReadsApi.ts - API client
 * @see frontend/src/types/plateRead.ts - Type definitions
 */

import { useCallback, useState } from 'react';

import { logger } from '../../services/logger';
import { fetchPlateReads } from '../../services/plateReadsApi';
import Button from '../common/Button';

import type { PlateRead, PlateReadFilters } from '../../types/plateRead';

// ============================================================================
// Types
// ============================================================================

export interface PlateExportButtonProps {
  /** Current filter parameters for the export */
  filters: PlateReadFilters;
  /** Total count of records matching the current filters */
  totalCount: number;
  /** Whether the button should be disabled */
  disabled?: boolean;
  /** Button variant */
  variant?: 'primary' | 'secondary' | 'outline';
  /** Button size */
  size?: 'sm' | 'md' | 'lg';
  /** Additional CSS classes */
  className?: string;
}

type ExportFormat = 'csv';

interface ExportState {
  status: 'idle' | 'exporting' | 'completed' | 'failed';
  progress: number;
  error?: string;
  downloadUrl?: string;
  recordCount?: number;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * CSV column headers for plate reads export.
 */
const CSV_HEADERS = [
  'timestamp',
  'camera_id',
  'plate_text',
  'detection_confidence',
  'ocr_confidence',
  'image_quality_score',
  'is_enhanced',
  'is_blurry',
] as const;

/**
 * Escape a value for CSV format.
 * Wraps in quotes if contains comma, quote, or newline.
 */
function escapeCSV(value: string | number | boolean): string {
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/**
 * Convert a plate read to a CSV row.
 */
function plateReadToCSVRow(read: PlateRead): string {
  const values = [
    read.timestamp,
    read.camera_id,
    read.plate_text,
    read.detection_confidence,
    read.ocr_confidence,
    read.image_quality_score,
    read.is_enhanced,
    read.is_blurry,
  ];
  return values.map(escapeCSV).join(',');
}

/**
 * Generate CSV content from plate reads.
 */
function generateCSV(reads: PlateRead[]): string {
  const headerRow = CSV_HEADERS.join(',');
  const dataRows = reads.map(plateReadToCSVRow);
  return [headerRow, ...dataRows].join('\n');
}

/**
 * Trigger a download of the CSV content.
 */
function downloadCSV(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.style.display = 'none';

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  // Clean up the URL object
  setTimeout(() => URL.revokeObjectURL(url), 100);
}

/**
 * Generate a filename for the export.
 */
function generateFilename(format: ExportFormat): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  return `plate-reads-${timestamp}.${format}`;
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * PlateExportButton provides export functionality for plate reads data.
 *
 * Features:
 * - Export filtered results as CSV
 * - Progress indicator during export
 * - Disabled when no results to export
 * - Downloads file directly to browser
 */
export function PlateExportButton({
  filters,
  totalCount,
  disabled = false,
  variant = 'secondary',
  size = 'md',
  className = '',
}: PlateExportButtonProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [exportState, setExportState] = useState<ExportState>({
    status: 'idle',
    progress: 0,
  });

  const hasResults = totalCount > 0;
  const isExporting = exportState.status === 'exporting';

  /**
   * Fetch all plate reads matching the filters and generate export.
   */
  const handleExport = useCallback(
    async (format: ExportFormat) => {
      setIsMenuOpen(false);
      setExportState({ status: 'exporting', progress: 0 });

      try {
        logger.info('Starting plate reads export', { format, totalCount, filters });

        // Fetch all matching records (paginated)
        const allReads: PlateRead[] = [];
        const batchSize = 100;
        let currentPage = 1;
        let hasMore = true;

        while (hasMore) {
          const response = await fetchPlateReads({
            ...filters,
            page: currentPage,
            page_size: batchSize,
          });

          allReads.push(...response.plate_reads);

          const progress = Math.min(
            Math.round((allReads.length / totalCount) * 100),
            99
          );
          setExportState({ status: 'exporting', progress });

          hasMore = allReads.length < response.total;
          currentPage++;

          // Safety check to prevent infinite loops
          if (currentPage > 1000) {
            logger.warn('Export pagination limit reached', { currentPage });
            break;
          }
        }

        // Generate and download the file
        if (format === 'csv') {
          const csvContent = generateCSV(allReads);
          const filename = generateFilename(format);
          downloadCSV(csvContent, filename);
        }

        setExportState({
          status: 'completed',
          progress: 100,
          recordCount: allReads.length,
        });

        logger.info('Plate reads export completed', {
          format,
          recordCount: allReads.length,
        });

        // Reset after a delay
        setTimeout(() => {
          setExportState({ status: 'idle', progress: 0 });
        }, 3000);
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Export failed';
        logger.error('Plate reads export failed', { error: errorMessage });

        setExportState({
          status: 'failed',
          progress: 0,
          error: errorMessage,
        });
      }
    },
    [filters, totalCount]
  );

  /**
   * Reset to idle state.
   */
  const handleReset = useCallback(() => {
    setExportState({ status: 'idle', progress: 0 });
  }, []);

  // Render exporting state
  if (isExporting) {
    return (
      <div className={`flex items-center gap-3 ${className}`} data-testid="export-progress">
        <div className="min-w-[200px] flex-1">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-sm text-gray-400">Exporting...</span>
            <span className="text-sm font-medium text-white">
              {exportState.progress}%
            </span>
          </div>
          <div className="h-2.5 w-full rounded-full bg-gray-700">
            <div
              className="h-2.5 rounded-full bg-blue-600 transition-all duration-300"
              style={{ width: `${exportState.progress}%` }}
              role="progressbar"
              aria-valuenow={exportState.progress}
              aria-valuemin={0}
              aria-valuemax={100}
              data-testid="export-progress-bar"
            />
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleReset}
          aria-label="Cancel export"
          data-testid="cancel-export-button"
        >
          Cancel
        </Button>
      </div>
    );
  }

  // Render completed state
  if (exportState.status === 'completed') {
    return (
      <div className={`flex items-center gap-3 ${className}`} data-testid="export-completed">
        <div className="flex items-center gap-2 text-green-400">
          <svg
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          <span className="text-sm">
            Export complete
            {exportState.recordCount !== undefined && (
              <span className="ml-1 text-gray-400">
                ({exportState.recordCount} records)
              </span>
            )}
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleReset}
          data-testid="new-export-button"
        >
          New Export
        </Button>
      </div>
    );
  }

  // Render failed state
  if (exportState.status === 'failed') {
    return (
      <div className={`flex items-center gap-3 ${className}`} data-testid="export-failed">
        <div className="flex items-center gap-2 text-red-400">
          <svg
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
          <span className="text-sm">
            Export failed
            {exportState.error && (
              <span className="ml-1 text-gray-400">({exportState.error})</span>
            )}
          </span>
        </div>
        <Button
          variant="secondary"
          size={size}
          onClick={handleReset}
          data-testid="retry-export-button"
        >
          Try Again
        </Button>
      </div>
    );
  }

  // Render default state with dropdown
  return (
    <div className={`relative ${className}`}>
      <Button
        variant={variant}
        size={size}
        onClick={() => setIsMenuOpen(!isMenuOpen)}
        disabled={disabled || !hasResults}
        rightIcon={
          <svg
            className={`h-4 w-4 transition-transform ${isMenuOpen ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        }
        aria-expanded={isMenuOpen}
        aria-haspopup="menu"
        data-testid="export-button"
      >
        Export
      </Button>

      {isMenuOpen && (
        <>
          {/* Backdrop to close menu */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsMenuOpen(false)}
            aria-hidden="true"
            data-testid="export-menu-backdrop"
          />

          {/* Dropdown menu */}
          <div
            className="absolute right-0 z-20 mt-2 w-48 rounded-md bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5"
            role="menu"
            aria-orientation="vertical"
            data-testid="export-menu"
          >
            <div className="py-1">
              <button
                type="button"
                className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-gray-200 hover:bg-gray-700"
                onClick={() => void handleExport('csv')}
                role="menuitem"
                data-testid="export-csv-option"
              >
                <svg
                  className="h-4 w-4 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                Export as CSV
                {hasResults && (
                  <span className="ml-auto text-xs text-gray-500">
                    {totalCount} records
                  </span>
                )}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default PlateExportButton;
