/**
 * Storage Status State Management Store
 *
 * Provides central state management for disk storage status across frontend components.
 * Uses Zustand for reactive state management, allowing the Header and FileOperationsPanel
 * to share storage warning state.
 */

import { create } from 'zustand';

// ============================================================================
// Types
// ============================================================================

/**
 * Storage status information from the API.
 */
export interface StorageStatus {
  /** Disk usage percentage (0-100) */
  usagePercent: number;
  /** Disk used in bytes */
  usedBytes: number;
  /** Disk total in bytes */
  totalBytes: number;
  /** Disk free in bytes */
  freeBytes: number;
  /** Timestamp of last update */
  lastUpdated: Date | null;
}

/**
 * Storage status store state and actions.
 */
export interface StorageStatusState {
  /** Current storage status, null if not yet fetched */
  status: StorageStatus | null;
  /** Whether disk usage is critical (>= 90%) */
  isCritical: boolean;
  /** Whether disk usage is high (>= 85%) */
  isHigh: boolean;
  /** Update storage status with new information */
  update: (usagePercent: number, usedBytes: number, totalBytes: number, freeBytes: number) => void;
  /** Clear all storage status state */
  clear: () => void;
}

// ============================================================================
// Constants
// ============================================================================

/** Threshold for critical disk usage warning (90%) */
export const CRITICAL_USAGE_THRESHOLD = 90;

/** Threshold for high disk usage warning (85%) */
export const HIGH_USAGE_THRESHOLD = 85;

// ============================================================================
// Store
// ============================================================================

/**
 * Zustand store for storage status state management.
 *
 * Features:
 * - Tracks current disk usage from storage API responses
 * - Provides `isCritical` flag when usage >= 90%
 * - Provides `isHigh` flag when usage >= 85%
 * - Shared between FileOperationsPanel and Header
 *
 * @example
 * ```tsx
 * import { useStorageStatusStore } from '@/stores/storage-status-store';
 *
 * // In FileOperationsPanel after fetching storage stats
 * const { update } = useStorageStatusStore();
 * update(stats.disk_usage_percent, stats.disk_used_bytes, stats.disk_total_bytes, stats.disk_free_bytes);
 *
 * // In Header to show warning
 * const { isCritical, status } = useStorageStatusStore();
 * if (isCritical) {
 *   return <StorageWarning usagePercent={status.usagePercent} />;
 * }
 * ```
 */
export const useStorageStatusStore = create<StorageStatusState>((set) => ({
  status: null,
  isCritical: false,
  isHigh: false,

  update: (usagePercent: number, usedBytes: number, totalBytes: number, freeBytes: number) => {
    set({
      status: {
        usagePercent,
        usedBytes,
        totalBytes,
        freeBytes,
        lastUpdated: new Date(),
      },
      isCritical: usagePercent >= CRITICAL_USAGE_THRESHOLD,
      isHigh: usagePercent >= HIGH_USAGE_THRESHOLD,
    });
  },

  clear: () => {
    set({
      status: null,
      isCritical: false,
      isHigh: false,
    });
  },
}));

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for formatted disk usage string (e.g., "450 GB / 1 TB").
 */
export const selectFormattedUsage = (state: StorageStatusState): string | null => {
  if (!state.status) {
    return null;
  }
  const { usedBytes, totalBytes } = state.status;
  return `${formatBytes(usedBytes)} / ${formatBytes(totalBytes)}`;
};

/**
 * Helper function to format bytes to human readable string.
 */
function formatBytes(bytes: number, decimals: number = 1): string {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}
