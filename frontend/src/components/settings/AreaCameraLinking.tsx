/**
 * AreaCameraLinking - Visual interface for linking cameras to areas.
 *
 * This component provides a UI for managing many-to-many relationships
 * between cameras and areas. A camera can be linked to multiple areas,
 * and an area can have multiple cameras.
 *
 * Features:
 * - Display all cameras with checkbox selection
 * - Display all areas grouped by property
 * - Link/unlink cameras to areas
 * - Visual feedback during operations
 *
 * @see NEM-3136 - Phase 7.3: Create AreaCameraLinking component
 */

import { clsx } from 'clsx';
import {
  AlertCircle,
  Camera,
  Check,
  ChevronDown,
  ChevronRight,
  Home,
  Link as LinkIcon,
  Loader2,
  MapPin,
  Unlink,
} from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import { useCamerasQuery } from '../../hooks/useCamerasQuery';
import {
  usePropertiesQuery,
  useAreasQuery,
  useAreaCamerasQuery,
  useAreaMutations,
  type AreaResponse,
  type PropertyResponse,
} from '../../hooks/usePropertyQueries';

import type { Camera as CameraType } from '../../services/api';

// =============================================================================
// Types
// =============================================================================

interface AreaCameraLinkingProps {
  /** Optional household ID to filter properties. Defaults to 1 for single-household deployments. */
  householdId?: number;
  /** Additional CSS classes */
  className?: string;
}

// Note: AreaWithCameras and PropertyWithAreas types reserved for future use
// when we support fetching cameras for multiple areas simultaneously

// =============================================================================
// Component
// =============================================================================

/**
 * AreaCameraLinking component for managing camera-to-area assignments.
 *
 * Displays a two-panel layout:
 * - Left panel: All available cameras with selection checkboxes
 * - Right panel: Areas grouped by property with linked cameras displayed
 *
 * Users can select cameras and link them to areas, or unlink cameras from areas.
 */
export default function AreaCameraLinking({ householdId = 1, className }: AreaCameraLinkingProps) {
  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const [selectedCameraIds, setSelectedCameraIds] = useState<Set<string>>(new Set());
  const [expandedPropertyIds, setExpandedPropertyIds] = useState<Set<number>>(new Set());
  const [selectedAreaId, setSelectedAreaId] = useState<number | null>(null);
  const [operationInProgress, setOperationInProgress] = useState<{
    areaId: number;
    cameraId?: string;
    operation: 'link' | 'unlink';
  } | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [operationSuccess, setOperationSuccess] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Data Fetching
  // ---------------------------------------------------------------------------
  const { cameras, isLoading: isLoadingCameras, error: camerasError } = useCamerasQuery();
  const {
    properties,
    isLoading: isLoadingProperties,
    error: propertiesError,
  } = usePropertiesQuery({
    householdId,
  });

  // Get areas for each property (we need to handle multiple properties)
  // For simplicity, we'll use the first property if available
  const firstPropertyId = properties[0]?.id ?? 0;
  const {
    areas,
    isLoading: isLoadingAreas,
    error: areasError,
  } = useAreasQuery({
    propertyId: firstPropertyId,
    enabled: firstPropertyId > 0,
  });

  // Get cameras linked to the selected area
  const {
    cameras: linkedCameras,
    isLoading: isLoadingAreaCameras,
    refetch: refetchAreaCameras,
  } = useAreaCamerasQuery({
    areaId: selectedAreaId ?? 0,
    enabled: selectedAreaId !== null && selectedAreaId > 0,
  });

  const { linkCamera, unlinkCamera } = useAreaMutations();

  // ---------------------------------------------------------------------------
  // Derived State
  // ---------------------------------------------------------------------------

  // Set of camera IDs currently linked to the selected area
  const linkedCameraIds = useMemo(() => new Set(linkedCameras.map((c) => c.id)), [linkedCameras]);

  // Cameras that are selected but not yet linked to the selected area
  const camerasToLink = useMemo(() => {
    if (selectedAreaId === null) return [];
    return [...selectedCameraIds].filter((id) => !linkedCameraIds.has(id));
  }, [selectedCameraIds, linkedCameraIds, selectedAreaId]);

  // Loading state
  const isLoading = isLoadingCameras || isLoadingProperties;

  // Error state
  const error = camerasError ?? propertiesError ?? areasError;

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const toggleCameraSelection = useCallback((cameraId: string) => {
    setSelectedCameraIds((prev) => {
      const next = new Set(prev);
      if (next.has(cameraId)) {
        next.delete(cameraId);
      } else {
        next.add(cameraId);
      }
      return next;
    });
  }, []);

  const selectAllCameras = useCallback(() => {
    setSelectedCameraIds(new Set(cameras.map((c) => c.id)));
  }, [cameras]);

  const deselectAllCameras = useCallback(() => {
    setSelectedCameraIds(new Set());
  }, []);

  const togglePropertyExpanded = useCallback((propertyId: number) => {
    setExpandedPropertyIds((prev) => {
      const next = new Set(prev);
      if (next.has(propertyId)) {
        next.delete(propertyId);
      } else {
        next.add(propertyId);
      }
      return next;
    });
  }, []);

  const handleSelectArea = useCallback((areaId: number) => {
    setSelectedAreaId(areaId);
    setOperationError(null);
    setOperationSuccess(null);
  }, []);

  const clearMessages = useCallback(() => {
    setOperationError(null);
    setOperationSuccess(null);
  }, []);

  const handleLinkSelectedCameras = useCallback(async () => {
    if (selectedAreaId === null || camerasToLink.length === 0) return;

    clearMessages();

    for (const cameraId of camerasToLink) {
      setOperationInProgress({ areaId: selectedAreaId, cameraId, operation: 'link' });
      try {
        await linkCamera.mutateAsync({ areaId: selectedAreaId, cameraId });
      } catch (err) {
        setOperationError(err instanceof Error ? err.message : `Failed to link camera ${cameraId}`);
        setOperationInProgress(null);
        return;
      }
    }

    setOperationInProgress(null);
    setSelectedCameraIds(new Set());
    setOperationSuccess(`Linked ${camerasToLink.length} camera(s) to area`);
    void refetchAreaCameras();
  }, [selectedAreaId, camerasToLink, linkCamera, refetchAreaCameras, clearMessages]);

  const handleUnlinkCamera = useCallback(
    async (areaId: number, cameraId: string) => {
      clearMessages();
      setOperationInProgress({ areaId, cameraId, operation: 'unlink' });

      try {
        await unlinkCamera.mutateAsync({ areaId, cameraId });
        setOperationSuccess(`Unlinked camera from area`);
        void refetchAreaCameras();
      } catch (err) {
        setOperationError(err instanceof Error ? err.message : `Failed to unlink camera`);
      } finally {
        setOperationInProgress(null);
      }
    },
    [unlinkCamera, refetchAreaCameras, clearMessages]
  );

  // ---------------------------------------------------------------------------
  // Render Helpers
  // ---------------------------------------------------------------------------

  const renderCameraItem = (camera: CameraType) => {
    const isSelected = selectedCameraIds.has(camera.id);
    const isLinked = linkedCameraIds.has(camera.id);
    const isUnlinking =
      operationInProgress?.areaId === selectedAreaId &&
      operationInProgress?.cameraId === camera.id &&
      operationInProgress?.operation === 'unlink';

    return (
      <div
        key={camera.id}
        data-testid={`camera-item-${camera.id}`}
        className={clsx(
          'flex items-center justify-between rounded-lg border p-3 transition-colors',
          isSelected
            ? 'border-primary bg-primary/10'
            : isLinked
              ? 'border-green-500/50 bg-green-500/5'
              : 'border-gray-700 bg-card hover:border-gray-600'
        )}
      >
        <label className="flex flex-1 cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => toggleCameraSelection(camera.id)}
            disabled={isLinked}
            className="h-4 w-4 rounded border-gray-600 bg-gray-800 text-primary focus:ring-primary focus:ring-offset-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid={`camera-checkbox-${camera.id}`}
          />
          <Camera className="h-4 w-4 text-gray-400" />
          <div className="flex flex-col">
            <span className="text-sm font-medium text-text-primary">{camera.name}</span>
            <span className="text-xs text-gray-500">{camera.folder_path}</span>
          </div>
        </label>
        <div className="flex items-center gap-2">
          {isLinked && selectedAreaId !== null && (
            <button
              onClick={() => void handleUnlinkCamera(selectedAreaId, camera.id)}
              disabled={isUnlinking}
              className={clsx(
                'rounded-md p-1.5 transition-colors',
                isUnlinking
                  ? 'cursor-not-allowed opacity-50'
                  : 'text-gray-400 hover:bg-gray-700 hover:text-red-400'
              )}
              title="Unlink from area"
              data-testid={`unlink-camera-${camera.id}`}
            >
              {isUnlinking ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Unlink className="h-4 w-4" />
              )}
            </button>
          )}
          {isLinked && (
            <span
              className="flex items-center gap-1 text-xs text-green-500"
              data-testid={`linked-indicator-${camera.id}`}
            >
              <Check className="h-3 w-3" />
              Linked
            </span>
          )}
          <span
            className={clsx(
              'h-2 w-2 rounded-full',
              camera.status === 'online'
                ? 'bg-green-500'
                : camera.status === 'error'
                  ? 'bg-red-500'
                  : 'bg-gray-500'
            )}
            title={camera.status}
          />
        </div>
      </div>
    );
  };

  const renderAreaItem = (area: AreaResponse) => {
    const isSelected = selectedAreaId === area.id;

    return (
      <button
        key={area.id}
        onClick={() => handleSelectArea(area.id)}
        data-testid={`area-item-${area.id}`}
        className={clsx(
          'flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors',
          isSelected
            ? 'border-primary bg-primary/10'
            : 'border-gray-700 bg-card hover:border-gray-600'
        )}
      >
        <div
          className="h-3 w-3 rounded-full"
          style={{ backgroundColor: area.color }}
          aria-hidden="true"
        />
        <div className="flex flex-1 flex-col">
          <span className="text-sm font-medium text-text-primary">{area.name}</span>
          {area.description && <span className="text-xs text-gray-500">{area.description}</span>}
        </div>
        {isSelected && <Check className="h-4 w-4 text-primary" />}
      </button>
    );
  };

  const renderProperty = (property: PropertyResponse, propertyAreas: AreaResponse[]) => {
    const isExpanded = expandedPropertyIds.has(property.id);
    const hasAreas = propertyAreas.length > 0;

    return (
      <div key={property.id} data-testid={`property-item-${property.id}`}>
        <button
          onClick={() => togglePropertyExpanded(property.id)}
          className="flex w-full items-center gap-2 rounded-lg p-2 text-left transition-colors hover:bg-gray-800"
          data-testid={`property-toggle-${property.id}`}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-400" />
          )}
          <Home className="h-4 w-4 text-primary" />
          <span className="flex-1 text-sm font-medium text-text-primary">{property.name}</span>
          <span className="text-xs text-gray-500">
            {propertyAreas.length} area{propertyAreas.length !== 1 ? 's' : ''}
          </span>
        </button>

        {isExpanded && (
          <div className="ml-6 mt-2 space-y-2">
            {hasAreas ? (
              propertyAreas.map((area) => renderAreaItem(area))
            ) : (
              <p className="py-2 text-sm text-gray-500">No areas configured</p>
            )}
          </div>
        )}
      </div>
    );
  };

  // ---------------------------------------------------------------------------
  // Loading State
  // ---------------------------------------------------------------------------

  if (isLoading) {
    return (
      <div
        className={clsx('flex items-center justify-center py-12', className)}
        data-testid="area-camera-linking-loading"
      >
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-3 text-text-secondary">Loading...</span>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Error State
  // ---------------------------------------------------------------------------

  if (error) {
    return (
      <div
        className={clsx('rounded-lg border border-red-500/20 bg-red-500/10 p-4', className)}
        data-testid="area-camera-linking-error"
      >
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div>
            <h3 className="font-semibold text-red-500">Error loading data</h3>
            <p className="mt-1 text-sm text-red-400">{error.message}</p>
          </div>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Main Render
  // ---------------------------------------------------------------------------

  return (
    <div className={clsx('space-y-6', className)} data-testid="area-camera-linking">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-text-primary">Link Cameras to Areas</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Select cameras and assign them to areas. A camera can be linked to multiple areas.
        </p>
      </div>

      {/* Operation Feedback */}
      {operationError && (
        <div
          className="rounded-lg border border-red-500/30 bg-red-500/10 p-3"
          data-testid="operation-error"
        >
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-red-500" />
            <span className="text-sm text-red-500">{operationError}</span>
          </div>
        </div>
      )}

      {operationSuccess && (
        <div
          className="rounded-lg border border-green-500/30 bg-green-500/10 p-3"
          data-testid="operation-success"
        >
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-green-500" />
            <span className="text-sm text-green-500">{operationSuccess}</span>
          </div>
        </div>
      )}

      {/* Main Content - Two Panel Layout */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left Panel - Cameras */}
        <div className="rounded-lg border border-gray-800 bg-panel p-4">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Camera className="h-5 w-5 text-primary" />
              <h3 className="text-lg font-semibold text-text-primary">Available Cameras</h3>
            </div>
            <div className="flex gap-2">
              <button
                onClick={selectAllCameras}
                className="text-xs text-primary hover:underline"
                data-testid="select-all-cameras"
              >
                Select All
              </button>
              <span className="text-gray-600">|</span>
              <button
                onClick={deselectAllCameras}
                className="text-xs text-gray-400 hover:underline"
                data-testid="deselect-all-cameras"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="space-y-2">
            {cameras.length === 0 ? (
              <div className="py-8 text-center">
                <Camera className="mx-auto h-12 w-12 text-gray-600" />
                <p className="mt-2 text-sm text-gray-500">No cameras configured</p>
              </div>
            ) : (
              cameras.map(renderCameraItem)
            )}
          </div>

          {/* Link Button */}
          {selectedAreaId !== null && camerasToLink.length > 0 && (
            <div className="mt-4 border-t border-gray-800 pt-4">
              <button
                onClick={() => void handleLinkSelectedCameras()}
                disabled={operationInProgress !== null}
                className={clsx(
                  'flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2 font-medium transition-all',
                  operationInProgress
                    ? 'cursor-not-allowed bg-gray-700 text-gray-400'
                    : 'bg-primary text-gray-900 hover:bg-primary/90 hover:shadow-nvidia-glow'
                )}
                data-testid="link-selected-cameras"
              >
                {operationInProgress?.operation === 'link' ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Linking...
                  </>
                ) : (
                  <>
                    <LinkIcon className="h-4 w-4" />
                    Link {camerasToLink.length} Camera{camerasToLink.length !== 1 ? 's' : ''} to
                    Area
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Right Panel - Areas */}
        <div className="rounded-lg border border-gray-800 bg-panel p-4">
          <div className="mb-4 flex items-center gap-2">
            <MapPin className="h-5 w-5 text-primary" />
            <h3 className="text-lg font-semibold text-text-primary">Areas</h3>
          </div>

          <div className="space-y-2">
            {properties.length === 0 ? (
              <div className="py-8 text-center">
                <Home className="mx-auto h-12 w-12 text-gray-600" />
                <p className="mt-2 text-sm text-gray-500">No properties configured</p>
              </div>
            ) : (
              <>
                {properties.map((property) => {
                  // Filter areas for this property
                  const propertyAreas = areas.filter((a) => a.property_id === property.id);
                  return renderProperty(property, propertyAreas);
                })}

                {/* Show loading indicator for areas */}
                {isLoadingAreas && (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                    <span className="ml-2 text-sm text-gray-400">Loading areas...</span>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Selected Area Details */}
          {selectedAreaId !== null && (
            <div className="mt-4 border-t border-gray-800 pt-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-text-secondary">
                  Selected Area: {areas.find((a) => a.id === selectedAreaId)?.name ?? 'Unknown'}
                </span>
                <span className="text-xs text-gray-500">
                  {isLoadingAreaCameras ? (
                    <Loader2 className="inline h-3 w-3 animate-spin" />
                  ) : (
                    `${linkedCameras.length} camera${linkedCameras.length !== 1 ? 's' : ''} linked`
                  )}
                </span>
              </div>

              {/* List of linked cameras for selected area */}
              {linkedCameras.length > 0 && (
                <div className="mt-3 space-y-1">
                  {linkedCameras.map((camera) => (
                    <div
                      key={camera.id}
                      className="flex items-center justify-between rounded bg-gray-800/50 px-2 py-1"
                      data-testid={`area-linked-camera-${camera.id}`}
                    >
                      <div className="flex items-center gap-2">
                        <Camera className="h-3 w-3 text-gray-400" />
                        <span className="text-xs text-gray-300">{camera.name}</span>
                      </div>
                      <button
                        onClick={() => void handleUnlinkCamera(selectedAreaId, camera.id)}
                        disabled={
                          operationInProgress?.areaId === selectedAreaId &&
                          operationInProgress?.cameraId === camera.id
                        }
                        className="rounded p-1 text-gray-500 hover:bg-gray-700 hover:text-red-400"
                        title="Unlink camera"
                      >
                        <Unlink className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
