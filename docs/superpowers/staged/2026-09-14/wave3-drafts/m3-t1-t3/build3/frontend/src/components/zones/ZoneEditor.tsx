/**
 * ZoneEditor - Enhanced zone configuration modal with intelligence integration (NEM-3200)
 *
 * Modal component for managing camera zones with integrated intelligence features.
 *
 * Features:
 * - View existing zones overlaid on camera snapshot
 * - Draw new rectangle or polygon zones
 * - Edit zone properties (name, type, color, etc.)
 * - Delete zones with confirmation
 * - Enable/disable zones
 * - Tabbed sidebar with Draw, Configure, and Analytics panels
 * - Zone intelligence integration (status, ownership, heatmaps)
 *
 * Part of Phase 5.1: Enhanced Zone Editor Integration.
 *
 * @module components/zones/ZoneEditor
 */

import { Dialog, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import { AlertCircle, MapPin, PenTool, Plus, Square, X } from 'lucide-react';
import { Fragment, useCallback, useEffect, useState } from 'react';

import ZoneCanvas, { type Point } from './ZoneCanvas';
import ZoneEditorSidebar, { type SidebarTab } from './ZoneEditorSidebar';
import ZoneForm, { type ZoneFormData } from './ZoneForm';
import {
  createZone,
  deleteZone,
  fetchZones,
  getCameraSnapshotUrl,
  updateZone,
  type Camera,
  type Zone,
  type ZoneCreate,
  type ZoneShape,
  type ZoneUpdate,
} from '../../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Legacy props interface for backward compatibility.
 */
export interface ZoneEditorLegacyProps {
  /** Camera to configure zones for */
  camera: Camera;
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal is closed */
  onClose: () => void;
}

/**
 * Enhanced props interface with zone intelligence features.
 */
export interface ZoneEditorEnhancedProps {
  /** Camera ID for zone context */
  cameraId: string;
  /** Initially selected zone ID */
  selectedZoneId?: string;
  /** Callback when a zone is selected */
  onZoneSelect?: (zoneId: string) => void;
  /** Initial editor mode/tab */
  mode?: 'draw' | 'configure' | 'analytics';
}

/**
 * Combined props interface supporting both legacy and enhanced usage.
 */
export type ZoneEditorProps = ZoneEditorLegacyProps & Partial<ZoneEditorEnhancedProps>;

type EditorMode = 'view' | 'draw' | 'edit' | 'create';

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneEditor modal for managing camera zones.
 *
 * Features:
 * - View existing zones overlaid on camera snapshot
 * - Draw new rectangle or polygon zones
 * - Edit zone properties (name, type, color, etc.)
 * - Delete zones with confirmation
 * - Enable/disable zones
 * - Tabbed sidebar with intelligence integration (NEM-3200)
 *
 * @param props - Component props
 * @returns Rendered modal component
 */
export default function ZoneEditor({
  camera,
  isOpen,
  onClose,
  cameraId: propCameraId,
  selectedZoneId: propSelectedZoneId,
  onZoneSelect,
  mode: propMode,
}: ZoneEditorProps) {
  // Use camera.id if provided, otherwise fall back to cameraId prop
  const effectiveCameraId = camera?.id ?? propCameraId ?? '';

  // Data state
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [mode, setMode] = useState<EditorMode>('view');
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(propSelectedZoneId ?? null);
  const [editingZone, setEditingZone] = useState<Zone | null>(null);
  const [deletingZone, setDeletingZone] = useState<Zone | null>(null);

  // Sidebar state
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>(propMode ?? 'draw');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [useSidebar] = useState(true); // Can be toggled for classic view

  // Drawing state
  const [drawShape, setDrawShape] = useState<ZoneShape>('rectangle');
  const [drawColor, setDrawColor] = useState('#3B82F6');
  const [pendingCoordinates, setPendingCoordinates] = useState<Point[] | null>(null);

  // Form state
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Sync selectedZoneId with prop if provided
  useEffect(() => {
    if (propSelectedZoneId !== undefined) {
      setSelectedZoneId(propSelectedZoneId);
    }
  }, [propSelectedZoneId]);

  // ============================================================================
  // Data Loading
  // ============================================================================

  const loadZones = useCallback(async () => {
    if (!effectiveCameraId) return;

    try {
      setLoading(true);
      setError(null);
      const response = await fetchZones(effectiveCameraId);
      setZones(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load zones');
    } finally {
      setLoading(false);
    }
  }, [effectiveCameraId]);

  // Load zones when modal opens
  useEffect(() => {
    if (isOpen && effectiveCameraId) {
      void loadZones();
    }
  }, [isOpen, effectiveCameraId, loadZones]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setMode('view');
      setSelectedZoneId(propSelectedZoneId ?? null);
      setEditingZone(null);
      setDeletingZone(null);
      setPendingCoordinates(null);
    }
  }, [isOpen, propSelectedZoneId]);

  // ============================================================================
  // Event Handlers
  // ============================================================================

  // Handle drawing completion
  const handleDrawComplete = useCallback((coordinates: Point[]) => {
    setPendingCoordinates(coordinates);
    setMode('create');
  }, []);

  // Handle drawing cancellation
  const handleDrawCancel = useCallback(() => {
    setMode('view');
    setPendingCoordinates(null);
  }, []);

  // Handle zone form submission (create or edit)
  const handleFormSubmit = async (formData: ZoneFormData) => {
    setIsSubmitting(true);
    setError(null);

    try {
      if (editingZone) {
        // Update existing zone
        const updateData: ZoneUpdate = {
          name: formData.name,
          zone_type: formData.zone_type,
          color: formData.color,
          enabled: formData.enabled,
          priority: formData.priority,
        };
        await updateZone(effectiveCameraId, editingZone.id, updateData);
      } else if (pendingCoordinates) {
        // Create new zone
        const createData: ZoneCreate = {
          name: formData.name,
          zone_type: formData.zone_type,
          coordinates: pendingCoordinates,
          shape: drawShape,
          color: formData.color,
          enabled: formData.enabled,
          priority: formData.priority,
        };
        await createZone(effectiveCameraId, createData);
      }

      await loadZones();
      setMode('view');
      setEditingZone(null);
      setPendingCoordinates(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save zone');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle form cancellation
  const handleFormCancel = () => {
    setMode('view');
    setEditingZone(null);
    setPendingCoordinates(null);
  };

  // Handle zone deletion
  const handleDelete = async () => {
    if (!deletingZone) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await deleteZone(effectiveCameraId, deletingZone.id);
      await loadZones();
      setDeletingZone(null);
      if (selectedZoneId === deletingZone.id) {
        setSelectedZoneId(null);
        onZoneSelect?.('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete zone');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle toggle enabled
  const handleToggleEnabled = async (zone: Zone) => {
    setError(null);

    try {
      await updateZone(effectiveCameraId, zone.id, { enabled: !zone.enabled });
      await loadZones();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update zone');
    }
  };

  // Handle zone edit
  const handleEdit = (zone: Zone) => {
    setEditingZone(zone);
    setMode('edit');
  };

  // Handle zone selection
  const handleZoneClick = (zoneId: string) => {
    if (mode === 'view') {
      const newZoneId = zoneId === selectedZoneId ? null : zoneId;
      setSelectedZoneId(newZoneId);
      onZoneSelect?.(newZoneId ?? '');
    }
  };

  // Handle zone selection from sidebar
  const handleSidebarZoneSelect = (zoneId: string) => {
    setSelectedZoneId(zoneId || null);
    onZoneSelect?.(zoneId);
  };

  // ============================================================================
  // Render Helpers
  // ============================================================================

  const renderDrawingToolbar = () => {
    if (mode !== 'view') return null;

    return (
      <div className="mb-4 flex items-center gap-2">
        <button
          onClick={() => {
            setDrawShape('rectangle');
            setMode('draw');
          }}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-gray-900 transition-all hover:bg-primary-400 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <Plus className="h-4 w-4" />
          <Square className="h-4 w-4" />
          Rectangle
        </button>
        <button
          onClick={() => {
            setDrawShape('polygon');
            setMode('draw');
          }}
          className="inline-flex items-center gap-2 rounded-lg border border-gray-600 bg-gray-800 px-3 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <Plus className="h-4 w-4" />
          <PenTool className="h-4 w-4" />
          Polygon
        </button>
      </div>
    );
  };

  const renderDrawingIndicator = () => {
    if (mode !== 'draw') return null;

    return (
      <div className="mb-4 flex items-center justify-between rounded-lg border border-primary/50 bg-primary/10 px-4 py-2">
        <div className="flex items-center gap-2">
          {drawShape === 'rectangle' ? (
            <Square className="h-4 w-4 text-primary" />
          ) : (
            <PenTool className="h-4 w-4 text-primary" />
          )}
          <span className="text-sm text-primary">Drawing {drawShape}...</span>
        </div>
        <button
          onClick={handleDrawCancel}
          className="text-sm text-gray-400 hover:text-text-primary"
        >
          Cancel
        </button>
      </div>
    );
  };

  const renderClassicSidebar = () => (
    <div className="w-80 shrink-0">
      {mode === 'view' && (
        <>
          <h3 className="mb-4 text-lg font-semibold text-text-primary">Zones ({zones.length})</h3>
          <ZoneEditorSidebar
            cameraId={effectiveCameraId}
            zones={zones}
            selectedZoneId={selectedZoneId}
            activeTab={sidebarTab}
            collapsed={sidebarCollapsed}
            onZoneSelect={handleSidebarZoneSelect}
            onZoneEdit={handleEdit}
            onZoneDelete={setDeletingZone}
            onZoneToggleEnabled={(zone) => void handleToggleEnabled(zone)}
            onTabChange={setSidebarTab}
            onCollapseChange={setSidebarCollapsed}
          />
        </>
      )}

      {(mode === 'create' || mode === 'edit') && (
        <>
          <h3 className="mb-4 text-lg font-semibold text-text-primary">
            {mode === 'create' ? 'New Zone' : 'Edit Zone'}
          </h3>
          <ZoneForm
            initialData={
              editingZone
                ? {
                    name: editingZone.name,
                    zone_type: editingZone.zone_type,
                    shape: editingZone.shape,
                    color: editingZone.color,
                    enabled: editingZone.enabled,
                    priority: editingZone.priority,
                  }
                : { color: drawColor, shape: drawShape }
            }
            onSubmit={(data) => void handleFormSubmit(data)}
            onCancel={handleFormCancel}
            isSubmitting={isSubmitting}
            submitText={mode === 'create' ? 'Create Zone' : 'Update Zone'}
            apiError={error}
            onClearApiError={() => setError(null)}
          />
        </>
      )}

      {mode === 'draw' && (
        <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
          <h3 className="mb-2 font-medium text-text-primary">Drawing Mode</h3>
          <p className="text-sm text-text-secondary">
            {drawShape === 'rectangle'
              ? 'Click and drag on the camera view to draw a rectangle zone.'
              : 'Click on the camera view to add polygon points. Double-click to complete the shape.'}
          </p>
          <fieldset className="mt-4">
            <legend className="block text-sm font-medium text-text-primary">Zone Color</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'].map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => setDrawColor(color)}
                  className={clsx(
                    'h-6 w-6 rounded-full border-2 transition-all',
                    drawColor === color
                      ? 'border-white ring-2 ring-primary ring-offset-2 ring-offset-gray-800'
                      : 'border-transparent hover:border-gray-400'
                  )}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </fieldset>
        </div>
      )}
    </div>
  );

  // ============================================================================
  // Main Render
  // ============================================================================

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel
                className={clsx(
                  'w-full transform overflow-hidden rounded-lg border border-gray-700 bg-panel shadow-dark-xl transition-all',
                  useSidebar && !sidebarCollapsed ? 'max-w-6xl' : 'max-w-5xl'
                )}
              >
                {/* Header */}
                <div className="flex items-center justify-between border-b border-gray-700 px-6 py-4">
                  <div className="flex items-center gap-3">
                    <MapPin className="h-5 w-5 text-primary" />
                    <Dialog.Title className="text-xl font-bold text-text-primary">
                      Zone Configuration - {camera?.name ?? 'Camera'}
                    </Dialog.Title>
                  </div>
                  <button
                    onClick={onClose}
                    className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-text-primary focus:outline-none"
                    data-testid="close-modal-btn"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Error display */}
                {error && (
                  <div className="mx-6 mt-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2">
                    <AlertCircle className="h-4 w-4 text-red-500" />
                    <span className="text-sm text-red-400">{error}</span>
                    <button
                      onClick={() => setError(null)}
                      className="ml-auto text-red-400 hover:text-red-300"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                )}

                {/* Content */}
                <div className="flex">
                  {/* Left panel: Canvas */}
                  <div className="flex-1 p-6">
                    {renderDrawingToolbar()}
                    {renderDrawingIndicator()}

                    {loading ? (
                      <div className="flex h-96 items-center justify-center rounded-lg border border-gray-700 bg-gray-800">
                        <span className="text-text-secondary">Loading zones...</span>
                      </div>
                    ) : (
                      <ZoneCanvas
                        snapshotUrl={getCameraSnapshotUrl(effectiveCameraId)}
                        zones={zones}
                        selectedZoneId={selectedZoneId}
                        isDrawing={mode === 'draw'}
                        drawShape={drawShape}
                        drawColor={drawColor}
                        onZoneClick={handleZoneClick}
                        onDrawComplete={handleDrawComplete}
                        onDrawCancel={handleDrawCancel}
                      />
                    )}
                  </div>

                  {/* Right panel: Form, drawing mode, or sidebar */}
                  {mode === 'create' || mode === 'edit' ? (
                    <div className="w-80 shrink-0 border-l border-gray-700 bg-[#1A1A1A] p-4">
                      <h3 className="mb-4 text-lg font-semibold text-text-primary">
                        {mode === 'create' ? 'New Zone' : 'Edit Zone'}
                      </h3>
                      <ZoneForm
                        initialData={
                          editingZone
                            ? {
                                name: editingZone.name,
                                zone_type: editingZone.zone_type,
                                shape: editingZone.shape,
                                color: editingZone.color,
                                enabled: editingZone.enabled,
                                priority: editingZone.priority,
                              }
                            : { color: drawColor, shape: drawShape }
                        }
                        onSubmit={(data) => void handleFormSubmit(data)}
                        onCancel={handleFormCancel}
                        isSubmitting={isSubmitting}
                        submitText={mode === 'create' ? 'Create Zone' : 'Update Zone'}
                        apiError={error}
                        onClearApiError={() => setError(null)}
                      />
                    </div>
                  ) : mode === 'draw' ? (
                    <div className="w-80 shrink-0 border-l border-gray-700 bg-[#1A1A1A] p-4">
                      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
                        <h3 className="mb-2 font-medium text-text-primary">Drawing Mode</h3>
                        <p className="text-sm text-text-secondary">
                          {drawShape === 'rectangle'
                            ? 'Click and drag on the camera view to draw a rectangle zone.'
                            : 'Click on the camera view to add polygon points. Double-click to complete the shape.'}
                        </p>
                        <fieldset className="mt-4">
                          <legend className="block text-sm font-medium text-text-primary">
                            Zone Color
                          </legend>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'].map(
                              (color) => (
                                <button
                                  key={color}
                                  type="button"
                                  onClick={() => setDrawColor(color)}
                                  className={clsx(
                                    'h-6 w-6 rounded-full border-2 transition-all',
                                    drawColor === color
                                      ? 'border-white ring-2 ring-primary ring-offset-2 ring-offset-gray-800'
                                      : 'border-transparent hover:border-gray-400'
                                  )}
                                  style={{ backgroundColor: color }}
                                />
                              )
                            )}
                          </div>
                        </fieldset>
                      </div>
                    </div>
                  ) : useSidebar ? (
                    <ZoneEditorSidebar
                      cameraId={effectiveCameraId}
                      zones={zones}
                      selectedZoneId={selectedZoneId}
                      activeTab={sidebarTab}
                      collapsed={sidebarCollapsed}
                      onZoneSelect={handleSidebarZoneSelect}
                      onZoneEdit={handleEdit}
                      onZoneDelete={setDeletingZone}
                      onZoneToggleEnabled={(zone) => void handleToggleEnabled(zone)}
                      onTabChange={setSidebarTab}
                      onCollapseChange={setSidebarCollapsed}
                    />
                  ) : (
                    renderClassicSidebar()
                  )}
                </div>

                {/* Delete confirmation */}
                {deletingZone && (
                  <div className="border-t border-gray-700 bg-red-500/5 px-6 py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <AlertCircle className="h-5 w-5 text-red-500" />
                        <span className="text-text-primary">
                          Delete zone &quot;{deletingZone.name}&quot;? This action cannot be undone.
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setDeletingZone(null)}
                          disabled={isSubmitting}
                          className="rounded-lg border border-gray-600 px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-gray-700 focus:outline-none disabled:opacity-50"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => void handleDelete()}
                          disabled={isSubmitting}
                          className="rounded-lg bg-red-700 px-3 py-1.5 text-sm font-medium text-white transition-all hover:bg-red-800 focus:outline-none disabled:opacity-50"
                        >
                          {isSubmitting ? 'Deleting...' : 'Delete'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
