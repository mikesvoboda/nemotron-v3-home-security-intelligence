/**
 * OrphanCleanupPanel - Advanced orphan file cleanup interface with configurable parameters
 *
 * Provides a comprehensive UI for managing orphaned file cleanup:
 * - min_age_hours slider (1-720 hours) - minimum age before deletion
 * - max_delete_gb slider (0.1-100 GB) - maximum bytes to delete per run
 * - Preview button (dry_run=true) - shows what would be deleted
 * - Clean Up button (dry_run=false) - performs actual deletion with confirmation
 * - Results display - files scanned, orphans found, deleted, bytes freed
 * - Progress indicator during cleanup operations
 *
 * @see NEM-3568 Admin Cleanup Endpoints Frontend UI
 * @see backend/api/routes/admin.py - Backend implementation
 */

import { clsx } from 'clsx';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Eye,
  HardDrive,
  Loader2,
  Search,
  Trash2,
  XCircle,
} from 'lucide-react';
import { useCallback, useState } from 'react';

import {
  useOrphanCleanupMutation,
  type OrphanCleanupResponse,
} from '../../hooks/useAdminMutations';
import { useToast } from '../../hooks/useToast';
import ConfirmDialog from '../jobs/ConfirmDialog';

// =============================================================================
// Types
// =============================================================================

export interface OrphanCleanupPanelProps {
  /** Optional className for styling */
  className?: string;
}

interface CleanupParams {
  /** Minimum age in hours before a file can be deleted (1-720) */
  minAgeHours: number;
  /** Maximum gigabytes to delete in one run (0.1-100) */
  maxDeleteGb: number;
}

// =============================================================================
// Constants
// =============================================================================

const DEFAULT_MIN_AGE_HOURS = 24;
const MIN_AGE_HOURS_MIN = 1;
const MIN_AGE_HOURS_MAX = 720;

const DEFAULT_MAX_DELETE_GB = 10;
const MAX_DELETE_GB_MIN = 0.1;
const MAX_DELETE_GB_MAX = 100;

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Format hours into a human-readable duration string.
 */
function formatHours(hours: number): string {
  if (hours < 24) {
    return `${hours} hour${hours !== 1 ? 's' : ''}`;
  }
  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  if (remainingHours === 0) {
    return `${days} day${days !== 1 ? 's' : ''}`;
  }
  return `${days}d ${remainingHours}h`;
}

/**
 * Format bytes into a human-readable size string.
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(value < 10 ? 2 : 1)} ${units[i]}`;
}

// =============================================================================
// Subcomponents
// =============================================================================

interface SliderInputProps {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  formatValue: (value: number) => string;
  icon: React.ReactNode;
  disabled?: boolean;
  testId: string;
}

function SliderInput({
  id,
  label,
  value,
  min,
  max,
  step,
  onChange,
  formatValue,
  icon,
  disabled,
  testId,
}: SliderInputProps) {
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = parseFloat(e.target.value);
      if (!isNaN(newValue)) {
        onChange(newValue);
      }
    },
    [onChange]
  );

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="flex items-center gap-2 text-sm font-medium text-gray-300">
          {icon}
          {label}
        </label>
        <span className="text-sm font-medium text-white" data-testid={`${testId}-value`}>
          {formatValue(value)}
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={handleChange}
        disabled={disabled}
        className={clsx(
          'h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700',
          '[&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4',
          '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full',
          '[&::-webkit-slider-thumb]:bg-[#76B900] [&::-webkit-slider-thumb]:shadow-md',
          '[&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4',
          '[&::-moz-range-thumb]:appearance-none [&::-moz-range-thumb]:rounded-full',
          '[&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-[#76B900]',
          '[&::-moz-range-thumb]:shadow-md',
          'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]',
          disabled && 'cursor-not-allowed opacity-50'
        )}
        data-testid={testId}
        aria-label={label}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-valuetext={formatValue(value)}
      />
      <div className="flex justify-between text-xs text-gray-500">
        <span>{formatValue(min)}</span>
        <span>{formatValue(max)}</span>
      </div>
    </div>
  );
}

interface ResultsDisplayProps {
  result: OrphanCleanupResponse;
  isDryRun: boolean;
}

function ResultsDisplay({ result, isDryRun }: ResultsDisplayProps) {
  const hasFailures = result.failed_count > 0;

  return (
    <div
      className={clsx(
        'mt-4 rounded-lg border p-4',
        isDryRun ? 'border-blue-500/30 bg-blue-500/10' : 'border-green-500/30 bg-green-500/10'
      )}
      data-testid="orphan-cleanup-results"
    >
      <div className="mb-3 flex items-center gap-2">
        {isDryRun ? (
          <>
            <Eye className="h-4 w-4 text-blue-400" />
            <span className="font-medium text-blue-400">Preview Results</span>
          </>
        ) : hasFailures ? (
          <>
            <AlertTriangle className="h-4 w-4 text-yellow-400" />
            <span className="font-medium text-yellow-400">Cleanup Completed with Warnings</span>
          </>
        ) : (
          <>
            <CheckCircle className="h-4 w-4 text-green-400" />
            <span className="font-medium text-green-400">Cleanup Completed</span>
          </>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
        <div>
          <div className="text-gray-500">Files Scanned</div>
          <div className="font-medium text-white" data-testid="result-scanned-files">
            {result.scanned_files.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-gray-500">Orphans Found</div>
          <div className="font-medium text-white" data-testid="result-orphaned-files">
            {result.orphaned_files.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-gray-500">{isDryRun ? 'Would Delete' : 'Deleted'}</div>
          <div className="font-medium text-white" data-testid="result-deleted-files">
            {result.deleted_files.toLocaleString()} files
          </div>
        </div>
        <div>
          <div className="text-gray-500">{isDryRun ? 'Would Free' : 'Space Freed'}</div>
          <div className="font-medium text-white" data-testid="result-deleted-bytes">
            {result.deleted_bytes_formatted || formatBytes(result.deleted_bytes)}
          </div>
        </div>
      </div>

      {/* Additional stats */}
      <div className="mt-3 flex flex-wrap gap-4 border-t border-gray-700 pt-3 text-xs text-gray-400">
        <div>
          Duration: <span className="text-gray-300">{result.duration_seconds.toFixed(2)}s</span>
        </div>
        {result.skipped_young > 0 && (
          <div>
            Skipped (too young):{' '}
            <span className="text-gray-300">{result.skipped_young.toLocaleString()}</span>
          </div>
        )}
        {result.skipped_size_limit > 0 && (
          <div>
            Skipped (size limit):{' '}
            <span className="text-gray-300">{result.skipped_size_limit.toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* Failed deletions */}
      {hasFailures && (
        <div className="mt-3 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm text-red-400">
            <XCircle className="h-4 w-4" />
            <span className="font-medium">Failed Deletions: {result.failed_count}</span>
          </div>
          {result.failed_deletions.length > 0 && (
            <div className="max-h-24 overflow-y-auto text-xs text-red-300">
              {result.failed_deletions.slice(0, 5).map((path, i) => (
                <div key={i} className="truncate">
                  {path}
                </div>
              ))}
              {result.failed_deletions.length > 5 && (
                <div className="mt-1 text-red-400">
                  ...and {result.failed_deletions.length - 5} more
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

/**
 * OrphanCleanupPanel provides a comprehensive interface for managing orphaned file cleanup.
 */
export default function OrphanCleanupPanel({ className }: OrphanCleanupPanelProps) {
  const toast = useToast();
  const orphanCleanup = useOrphanCleanupMutation();

  // Cleanup parameters
  const [params, setParams] = useState<CleanupParams>({
    minAgeHours: DEFAULT_MIN_AGE_HOURS,
    maxDeleteGb: DEFAULT_MAX_DELETE_GB,
  });

  // Result state
  const [result, setResult] = useState<OrphanCleanupResponse | null>(null);
  const [lastRunWasDryRun, setLastRunWasDryRun] = useState(true);

  // Confirmation dialog state
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  // Run preview (dry_run=true)
  const handlePreview = useCallback(async () => {
    try {
      const response = await orphanCleanup.mutateAsync({
        dry_run: true,
        min_age_hours: params.minAgeHours,
        max_delete_gb: params.maxDeleteGb,
      });
      setResult(response);
      setLastRunWasDryRun(true);
      toast.info('Preview completed', {
        description: `Found ${response.orphaned_files} orphaned files (${response.deleted_bytes_formatted || formatBytes(response.deleted_bytes)})`,
      });
    } catch (error) {
      toast.error('Preview failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [orphanCleanup, params, toast]);

  // Run actual cleanup (dry_run=false)
  const handleCleanup = useCallback(async () => {
    try {
      const response = await orphanCleanup.mutateAsync({
        dry_run: false,
        min_age_hours: params.minAgeHours,
        max_delete_gb: params.maxDeleteGb,
      });
      setResult(response);
      setLastRunWasDryRun(false);
      setShowConfirmDialog(false);

      if (response.deleted_files > 0) {
        toast.success('Cleanup completed', {
          description: `Deleted ${response.deleted_files} files, freed ${response.deleted_bytes_formatted || formatBytes(response.deleted_bytes)}`,
        });
      } else {
        toast.info('No files deleted', {
          description: 'No orphaned files matched the cleanup criteria',
        });
      }
    } catch (error) {
      toast.error('Cleanup failed', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
      setShowConfirmDialog(false);
    }
  }, [orphanCleanup, params, toast]);

  const isRunning = orphanCleanup.isPending;

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-[#1A1A1A] p-6', className)}
      data-testid="orphan-cleanup-panel"
    >
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <Trash2 className="h-5 w-5 text-amber-400" />
          <h3 className="text-lg font-semibold text-white">Orphan File Cleanup</h3>
        </div>
        <p className="mt-1 text-sm text-gray-400">
          Scan and remove files that are no longer referenced in the database. Use Preview to see
          what would be deleted before running actual cleanup.
        </p>
      </div>

      {/* Parameter Controls */}
      <div className="space-y-6">
        {/* Min Age Hours Slider */}
        <SliderInput
          id="min-age-hours"
          label="Minimum File Age"
          value={params.minAgeHours}
          min={MIN_AGE_HOURS_MIN}
          max={MIN_AGE_HOURS_MAX}
          step={1}
          onChange={(value) => setParams((p) => ({ ...p, minAgeHours: value }))}
          formatValue={formatHours}
          icon={<Clock className="h-4 w-4 text-gray-400" />}
          disabled={isRunning}
          testId="min-age-hours-slider"
        />

        {/* Max Delete GB Slider */}
        <SliderInput
          id="max-delete-gb"
          label="Maximum Deletion Size"
          value={params.maxDeleteGb}
          min={MAX_DELETE_GB_MIN}
          max={MAX_DELETE_GB_MAX}
          step={0.1}
          onChange={(value) =>
            setParams((p) => ({ ...p, maxDeleteGb: Math.round(value * 10) / 10 }))
          }
          formatValue={(v) => `${v.toFixed(1)} GB`}
          icon={<HardDrive className="h-4 w-4 text-gray-400" />}
          disabled={isRunning}
          testId="max-delete-gb-slider"
        />
      </div>

      {/* Action Buttons */}
      <div className="mt-6 flex gap-3">
        {/* Preview Button */}
        <button
          onClick={() => void handlePreview()}
          disabled={isRunning}
          className={clsx(
            'flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
            'border border-blue-500/30 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
            isRunning && 'cursor-not-allowed opacity-50'
          )}
          data-testid="btn-preview-cleanup"
        >
          {isRunning && lastRunWasDryRun ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Scanning...
            </>
          ) : (
            <>
              <Search className="h-4 w-4" />
              Preview
            </>
          )}
        </button>

        {/* Clean Up Button */}
        <button
          onClick={() => setShowConfirmDialog(true)}
          disabled={isRunning}
          className={clsx(
            'flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
            'bg-amber-600 text-white hover:bg-amber-700',
            'focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
            isRunning && 'cursor-not-allowed opacity-50'
          )}
          data-testid="btn-run-cleanup"
        >
          {isRunning && !lastRunWasDryRun ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Cleaning...
            </>
          ) : (
            <>
              <Trash2 className="h-4 w-4" />
              Clean Up
            </>
          )}
        </button>
      </div>

      {/* Results Display */}
      {result && <ResultsDisplay result={result} isDryRun={lastRunWasDryRun} />}

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showConfirmDialog}
        title="Confirm Orphan Cleanup"
        description={`This will permanently delete orphaned files older than ${formatHours(params.minAgeHours)}, up to ${params.maxDeleteGb.toFixed(1)} GB. This action cannot be undone.${result && lastRunWasDryRun ? ` Preview showed ${result.deleted_files} files (${result.deleted_bytes_formatted || formatBytes(result.deleted_bytes)}) would be deleted.` : ' We recommend running Preview first.'}`}
        confirmLabel="Delete Files"
        loadingText="Deleting..."
        variant="danger"
        isLoading={isRunning}
        onConfirm={() => void handleCleanup()}
        onCancel={() => setShowConfirmDialog(false)}
      />
    </div>
  );
}
