/**
 * React hook for detector configuration management.
 *
 * Provides state management and API integration for:
 * - Listing available detectors
 * - Getting/switching active detector
 * - Polling for health status
 *
 * @see frontend/src/services/detectorApi.ts - API client
 * @see backend/api/routes/detector.py - Backend implementation
 */

import { useCallback, useEffect, useState } from 'react';

import {
  type DetectorHealth,
  type DetectorInfo,
  type DetectorListResponse,
  type SwitchDetectorResponse,
  checkDetectorHealth,
  listDetectors,
  switchDetector,
} from '../services/detectorApi';

// ============================================================================
// Types
// ============================================================================

export interface UseDetectorConfigOptions {
  /** Whether to automatically fetch detectors on mount */
  autoFetch?: boolean;
  /** Polling interval in milliseconds (0 to disable) */
  pollingInterval?: number;
  /** Whether to include health status when fetching */
  includeHealth?: boolean;
}

export interface UseDetectorConfigResult {
  /** List of available detectors */
  detectors: DetectorInfo[];
  /** Currently active detector type */
  activeDetector: string | null;
  /** Whether data is being loaded */
  isLoading: boolean;
  /** Whether a switch operation is in progress */
  isSwitching: boolean;
  /** Error message if any */
  error: string | null;
  /** Refresh the detector list */
  refresh: () => Promise<void>;
  /** Switch to a different detector */
  switchTo: (detectorType: string, force?: boolean) => Promise<SwitchDetectorResponse>;
  /** Check health of a specific detector */
  checkHealth: (detectorType: string) => Promise<DetectorHealth>;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for managing detector configuration.
 *
 * @param options - Configuration options
 * @returns Detector state and actions
 *
 * @example
 * ```tsx
 * function DetectorSettings() {
 *   const {
 *     detectors,
 *     activeDetector,
 *     isLoading,
 *     isSwitching,
 *     error,
 *     switchTo,
 *   } = useDetectorConfig({ pollingInterval: 30000 });
 *
 *   const handleSwitch = async (type: string) => {
 *     try {
 *       await switchTo(type);
 *     } catch (e) {
 *       console.error('Switch failed:', e);
 *     }
 *   };
 *
 *   return (
 *     <select
 *       value={activeDetector || ''}
 *       onChange={(e) => handleSwitch(e.target.value)}
 *       disabled={isLoading || isSwitching}
 *     >
 *       {detectors.filter(d => d.enabled).map(d => (
 *         <option key={d.detector_type} value={d.detector_type}>
 *           {d.display_name}
 *         </option>
 *       ))}
 *     </select>
 *   );
 * }
 * ```
 */
export function useDetectorConfig(
  options: UseDetectorConfigOptions = {}
): UseDetectorConfigResult {
  const { autoFetch = true, pollingInterval = 0, includeHealth = false } = options;

  const [detectors, setDetectors] = useState<DetectorInfo[]>([]);
  const [activeDetector, setActiveDetector] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Fetch the list of detectors from the API.
   */
  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response: DetectorListResponse = await listDetectors(includeHealth);
      setDetectors(response.detectors);
      setActiveDetector(response.active_detector);
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to fetch detectors';
      setError(message);
      console.error('Failed to fetch detectors:', e);
    } finally {
      setIsLoading(false);
    }
  }, [includeHealth]);

  /**
   * Switch to a different detector.
   */
  const switchTo = useCallback(
    async (detectorType: string, force: boolean = false): Promise<SwitchDetectorResponse> => {
      setIsSwitching(true);
      setError(null);

      try {
        const response = await switchDetector({ detector_type: detectorType, force });
        setActiveDetector(response.detector_type);

        // Update the is_active flag in the detectors list
        setDetectors((prev) =>
          prev.map((d) => ({
            ...d,
            is_active: d.detector_type === response.detector_type,
          }))
        );

        return response;
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to switch detector';
        setError(message);
        throw e;
      } finally {
        setIsSwitching(false);
      }
    },
    []
  );

  /**
   * Check health of a specific detector.
   */
  const checkHealth = useCallback(
    async (detectorType: string): Promise<DetectorHealth> => {
      return checkDetectorHealth(detectorType);
    },
    []
  );

  // Initial fetch on mount
  useEffect(() => {
    if (autoFetch) {
      void refresh();
    }
  }, [autoFetch, refresh]);

  // Set up polling if enabled
  useEffect(() => {
    if (pollingInterval > 0) {
      const intervalId = setInterval(() => void refresh(), pollingInterval);
      return () => clearInterval(intervalId);
    }
  }, [pollingInterval, refresh]);

  return {
    detectors,
    activeDetector,
    isLoading,
    isSwitching,
    error,
    refresh,
    switchTo,
    checkHealth,
  };
}

export default useDetectorConfig;
