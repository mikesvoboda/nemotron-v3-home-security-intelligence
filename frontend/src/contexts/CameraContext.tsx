/**
 * CameraContext - Specialized context for camera state management.
 *
 * This context provides camera-specific data and operations, reducing
 * re-renders for components that only need camera data rather than
 * all system data.
 *
 * Benefits:
 * - Components using only camera data won't re-render when GPU/health updates
 * - Clear separation of concerns
 * - Optimized polling interval for camera data
 *
 * @module contexts/CameraContext
 */

import React, { createContext, useContext, useMemo, type ReactNode } from 'react';

import { useCamerasQuery } from '../hooks/useCamerasQuery';

import type { Camera } from '../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Camera data available through the context.
 */
export interface CameraContextData {
  /** List of all cameras, empty array if not loaded */
  cameras: Camera[];
  /** Map of camera IDs to camera names for efficient lookup */
  cameraNameMap: Map<string, string>;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Get camera by ID */
  getCameraById: (id: string) => Camera | undefined;
  /** Get camera name by ID with fallback */
  getCameraName: (id: string, fallback?: string) => string;
}

/**
 * Props for the CameraProvider component.
 */
export interface CameraProviderProps {
  children: ReactNode;
  /**
   * Polling interval for camera data in milliseconds.
   * @default 30000 (30 seconds)
   */
  pollingInterval?: number;
  /**
   * Whether to enable data fetching.
   * @default true
   */
  enabled?: boolean;
}

// ============================================================================
// Context
// ============================================================================

/**
 * Context for camera data. Do not use directly - use the useCameraContext hook.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const CameraContext = createContext<CameraContextData | null>(null);

CameraContext.displayName = 'CameraContext';

// ============================================================================
// Provider Component
// ============================================================================

/**
 * Provider component that fetches and manages camera data.
 *
 * This provider should be placed high in your component tree. It can be
 * used standalone or as part of the SystemDataProvider composition.
 */
export function CameraProvider({
  children,
  pollingInterval = 30_000,
  enabled = true,
}: CameraProviderProps): React.ReactElement {
  const { cameras, isLoading, isRefetching, error, refetch } = useCamerasQuery({
    enabled,
    refetchInterval: pollingInterval,
    staleTime: pollingInterval,
  });

  // Create memoized camera name lookup map
  const cameraNameMap = useMemo(() => {
    const map = new Map<string, string>();
    cameras.forEach((camera) => {
      map.set(camera.id, camera.name);
    });
    return map;
  }, [cameras]);

  // Helper to get camera by ID
  const getCameraById = useMemo(
    () => (id: string) => cameras.find((c) => c.id === id),
    [cameras]
  );

  // Helper to get camera name with fallback
  const getCameraName = useMemo(
    () =>
      (id: string, fallback = 'Unknown Camera') =>
        cameraNameMap.get(id) ?? fallback,
    [cameraNameMap]
  );

  // Memoized context value - only changes when camera data changes
  const value = useMemo<CameraContextData>(
    () => ({
      cameras,
      cameraNameMap,
      isLoading,
      isRefetching,
      error,
      refetch,
      getCameraById,
      getCameraName,
    }),
    [cameras, cameraNameMap, isLoading, isRefetching, error, refetch, getCameraById, getCameraName]
  );

  return <CameraContext.Provider value={value}>{children}</CameraContext.Provider>;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to access camera data from the CameraContext.
 *
 * Must be used within a CameraProvider. Throws an error if used outside
 * the provider to help catch usage errors early.
 *
 * @throws Error if used outside of CameraProvider
 *
 * @example
 * ```tsx
 * function CameraGrid() {
 *   const { cameras, isLoading, getCameraName } = useCameraContext();
 *
 *   if (isLoading) return <Spinner />;
 *
 *   return (
 *     <div>
 *       {cameras.map((camera) => (
 *         <CameraCard key={camera.id} camera={camera} />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useCameraContext(): CameraContextData {
  const context = useContext(CameraContext);
  if (!context) {
    throw new Error('useCameraContext must be used within a CameraProvider');
  }
  return context;
}

/**
 * Hook to optionally access camera data. Returns null if outside provider.
 *
 * Use this when the component may be rendered outside the provider context,
 * or when you want to handle the absence of context gracefully.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useCameraContextOptional(): CameraContextData | null {
  return useContext(CameraContext);
}

export default CameraProvider;
