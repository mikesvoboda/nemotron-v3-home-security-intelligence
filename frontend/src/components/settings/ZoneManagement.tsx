import { Dialog, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertCircle,
  Edit2,
  Eye,
  EyeOff,
  MapPin,
  Pencil,
  Plus,
  Trash2,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useEffect, useState } from 'react';

import ZoneEditor from './ZoneEditor';
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
  type ZoneType,
  type ZoneUpdate,
} from '../../services/api';

export interface ZoneManagementProps {
  /** Camera to manage zones for */
  camera: Camera;
  /** Called when management is closed */
  onClose: () => void;
}

// Zone type options for select
const ZONE_TYPE_OPTIONS: { value: ZoneType; label: string }[] = [
  { value: 'entry_point', label: 'Entry Point' },
  { value: 'driveway', label: 'Driveway' },
  { value: 'sidewalk', label: 'Sidewalk' },
  { value: 'yard', label: 'Yard' },
  { value: 'other', label: 'Other' },
];

// Default zone colors
const DEFAULT_ZONE_COLORS = [
  '#ef4444', // red
  '#3b82f6', // blue
  '#f59e0b', // amber
  '#10b981', // green
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#06b6d4', // cyan
];

interface ZoneFormData {
  name: string;
  zone_type: ZoneType;
  color: string;
  enabled: boolean;
  priority: number;
  coordinates: number[][];
  shape: ZoneShape;
}

interface ZoneFormErrors {
  name?: string;
  coordinates?: string;
}

/**
 * ZoneManagement - Full UI for managing camera zones
 *
 * Features:
 * - Visual zone editor for drawing/editing zones
 * - List of existing zones with enable/disable toggle
 * - Create, edit, and delete zones
 * - Zone type and color configuration
 */
export default function ZoneManagement({ camera, onClose }: ZoneManagementProps) {
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [editorMode, setEditorMode] = useState<'view' | 'draw' | 'edit'>('view');
  const [drawShape, setDrawShape] = useState<ZoneShape>('rectangle');
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [editingZone, setEditingZone] = useState<Zone | null>(null);
  const [deletingZone, setDeletingZone] = useState<Zone | null>(null);
  const [formData, setFormData] = useState<ZoneFormData>({
    name: '',
    zone_type: 'other',
    color: DEFAULT_ZONE_COLORS[0],
    enabled: true,
    priority: 0,
    coordinates: [],
    shape: 'rectangle',
  });
  const [formErrors, setFormErrors] = useState<ZoneFormErrors>({});
  const [submitting, setSubmitting] = useState(false);

  const loadZones = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchZones(camera.id);
      setZones(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load zones');
    } finally {
      setLoading(false);
    }
  }, [camera.id]);

  // Load zones on mount
  useEffect(() => {
    void loadZones();
  }, [loadZones]);

  const validateForm = (data: ZoneFormData): ZoneFormErrors => {
    const errors: ZoneFormErrors = {};

    if (!data.name || data.name.trim().length < 1) {
      errors.name = 'Name is required';
    }

    if (!data.coordinates || data.coordinates.length < 3) {
      errors.coordinates = 'Zone must have at least 3 points';
    }

    return errors;
  };

  // Handle zone creation from editor
  const handleZoneCreate = useCallback((coordinates: number[][], shape: ZoneShape) => {
    setFormData({
      name: '',
      zone_type: 'other',
      color: DEFAULT_ZONE_COLORS[Math.floor(Math.random() * DEFAULT_ZONE_COLORS.length)],
      enabled: true,
      priority: 0,
      coordinates,
      shape,
    });
    setFormErrors({});
    setEditingZone(null);
    setIsFormModalOpen(true);
    setEditorMode('view');
  }, []);

  // Handle zone coordinate update from editor
  const handleZoneUpdate = useCallback(
    async (zoneId: string, coordinates: number[][]) => {
      try {
        await updateZone(camera.id, zoneId, { coordinates });
        await loadZones();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update zone');
      }
    },
    [camera.id, loadZones]
  );

  // Handle zone selection
  const handleZoneSelect = useCallback((zoneId: string | null) => {
    setSelectedZoneId(zoneId);
    if (zoneId === null) {
      setEditorMode('view');
    }
  }, []);

  // Open edit modal for zone
  const handleEditZone = (zone: Zone) => {
    setEditingZone(zone);
    setFormData({
      name: zone.name,
      zone_type: zone.zone_type,
      color: zone.color,
      enabled: zone.enabled,
      priority: zone.priority,
      coordinates: zone.coordinates,
      shape: zone.shape,
    });
    setFormErrors({});
    setIsFormModalOpen(true);
  };

  // Open delete confirmation modal
  const handleDeleteZone = (zone: Zone) => {
    setDeletingZone(zone);
    setIsDeleteModalOpen(true);
  };

  // Toggle zone enabled state
  const handleToggleEnabled = async (zone: Zone) => {
    try {
      await updateZone(camera.id, zone.id, { enabled: !zone.enabled });
      await loadZones();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update zone');
    }
  };

  // Close form modal
  const handleCloseFormModal = () => {
    setIsFormModalOpen(false);
    setEditingZone(null);
    setFormData({
      name: '',
      zone_type: 'other',
      color: DEFAULT_ZONE_COLORS[0],
      enabled: true,
      priority: 0,
      coordinates: [],
      shape: 'rectangle',
    });
    setFormErrors({});
  };

  // Close delete modal
  const handleCloseDeleteModal = () => {
    setIsDeleteModalOpen(false);
    setDeletingZone(null);
  };

  // Submit zone form (create or update)
  const handleSubmitForm = async (e: React.FormEvent) => {
    e.preventDefault();

    const errors = validateForm(formData);
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setSubmitting(true);
    setFormErrors({});

    try {
      if (editingZone) {
        // Update existing zone
        const updateData: ZoneUpdate = {
          name: formData.name.trim(),
          zone_type: formData.zone_type,
          color: formData.color,
          enabled: formData.enabled,
          priority: formData.priority,
        };
        await updateZone(camera.id, editingZone.id, updateData);
      } else {
        // Create new zone
        const createData: ZoneCreate = {
          name: formData.name.trim(),
          zone_type: formData.zone_type,
          color: formData.color,
          enabled: formData.enabled,
          priority: formData.priority,
          coordinates: formData.coordinates,
          shape: formData.shape,
        };
        await createZone(camera.id, createData);
      }

      await loadZones();
      handleCloseFormModal();
    } catch (err) {
      setFormErrors({
        name: err instanceof Error ? err.message : 'Failed to save zone',
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Confirm zone deletion
  const handleConfirmDelete = async () => {
    if (!deletingZone) return;

    setSubmitting(true);

    try {
      await deleteZone(camera.id, deletingZone.id);
      await loadZones();
      handleCloseDeleteModal();
      if (selectedZoneId === deletingZone.id) {
        setSelectedZoneId(null);
        setEditorMode('view');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete zone');
      handleCloseDeleteModal();
    } finally {
      setSubmitting(false);
    }
  };

  // Start draw mode
  const handleStartDraw = (shape: ZoneShape) => {
    setDrawShape(shape);
    setEditorMode('draw');
    setSelectedZoneId(null);
  };

  // Start edit mode for selected zone
  const handleStartEdit = () => {
    if (selectedZoneId) {
      setEditorMode('edit');
    }
  };

  // Cancel current mode
  const handleCancelMode = () => {
    setEditorMode('view');
  };

  return (
    <div className="flex h-[80vh] max-h-[900px] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 p-4">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Zone Management</h2>
          <p className="text-sm text-text-secondary">
            Camera: <span className="font-medium text-text-primary">{camera.name}</span>
          </p>
        </div>
        <button
          onClick={onClose}
          className="rounded p-2 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary"
          aria-label="Close zone management"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Zone editor (left side) */}
        <div className="flex flex-1 flex-col border-r border-gray-800 p-4">
          {/* Toolbar */}
          <div className="mb-4 flex items-center gap-2">
            <button
              onClick={() => handleStartDraw('rectangle')}
              disabled={editorMode === 'draw'}
              className={clsx(
                'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                editorMode === 'draw' && drawShape === 'rectangle'
                  ? 'bg-primary text-gray-900'
                  : 'bg-gray-800 text-text-primary hover:bg-gray-700'
              )}
            >
              <Plus className="h-4 w-4" />
              Rectangle
            </button>
            <button
              onClick={() => handleStartDraw('polygon')}
              disabled={editorMode === 'draw'}
              className={clsx(
                'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                editorMode === 'draw' && drawShape === 'polygon'
                  ? 'bg-primary text-gray-900'
                  : 'bg-gray-800 text-text-primary hover:bg-gray-700'
              )}
            >
              <Plus className="h-4 w-4" />
              Polygon
            </button>
            {selectedZoneId && editorMode !== 'edit' && (
              <button
                onClick={handleStartEdit}
                className="flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500"
              >
                <Pencil className="h-4 w-4" />
                Edit Points
              </button>
            )}
            {editorMode !== 'view' && (
              <button
                onClick={handleCancelMode}
                className="flex items-center gap-2 rounded-lg bg-gray-700 px-3 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-gray-600"
              >
                Cancel
              </button>
            )}
          </div>

          {/* Zone editor */}
          <div className="flex-1">
            <ZoneEditor
              imageUrl={getCameraSnapshotUrl(camera.id)}
              zones={zones}
              selectedZoneId={selectedZoneId ?? undefined}
              onZoneSelect={handleZoneSelect}
              onZoneUpdate={handleZoneUpdate}
              onZoneCreate={handleZoneCreate}
              mode={editorMode}
              drawShape={drawShape}
              className="h-full w-full"
            />
          </div>
        </div>

        {/* Zone list (right side) */}
        <div className="flex w-80 flex-col overflow-hidden">
          <div className="border-b border-gray-800 p-4">
            <h3 className="font-semibold text-text-primary">Zones ({zones.length})</h3>
          </div>

          {loading ? (
            <div className="flex flex-1 items-center justify-center">
              <span className="text-text-secondary">Loading zones...</span>
            </div>
          ) : error ? (
            <div className="p-4">
              <div className="flex items-start gap-2 rounded bg-red-500/10 p-3 text-red-400">
                <AlertCircle className="h-5 w-5 flex-shrink-0" />
                <div>
                  <p className="text-sm">{error}</p>
                  <button
                    onClick={() => void loadZones()}
                    className="mt-1 text-xs underline hover:no-underline"
                  >
                    Try again
                  </button>
                </div>
              </div>
            </div>
          ) : zones.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center p-4 text-center">
              <MapPin className="h-12 w-12 text-gray-600" />
              <p className="mt-2 text-text-secondary">No zones defined</p>
              <p className="text-sm text-text-muted">
                Click &quot;Rectangle&quot; or &quot;Polygon&quot; to add a zone
              </p>
            </div>
          ) : (
            <div className="flex-1 space-y-2 overflow-y-auto p-4">
              {zones.map((zone) => (
                <div
                  key={zone.id}
                  className={clsx(
                    'rounded-lg border p-3 transition-colors',
                    selectedZoneId === zone.id
                      ? 'border-primary bg-primary/10'
                      : 'border-gray-800 bg-gray-900/50 hover:border-gray-700'
                  )}
                >
                  <div className="flex items-start justify-between">
                    <button
                      type="button"
                      className="flex-1 cursor-pointer text-left"
                      onClick={() => handleZoneSelect(zone.id)}
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: zone.color }}
                        />
                        <span
                          className={clsx(
                            'font-medium',
                            zone.enabled ? 'text-text-primary' : 'text-text-muted'
                          )}
                        >
                          {zone.name}
                        </span>
                      </div>
                      <p className="mt-1 text-xs capitalize text-text-secondary">
                        {zone.zone_type.replace('_', ' ')} - {zone.shape}
                      </p>
                    </button>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => void handleToggleEnabled(zone)}
                        className={clsx(
                          'rounded p-1.5 transition-colors',
                          zone.enabled
                            ? 'text-green-500 hover:bg-green-500/10'
                            : 'text-gray-500 hover:bg-gray-800'
                        )}
                        title={zone.enabled ? 'Disable zone' : 'Enable zone'}
                      >
                        {zone.enabled ? (
                          <Eye className="h-4 w-4" />
                        ) : (
                          <EyeOff className="h-4 w-4" />
                        )}
                      </button>
                      <button
                        onClick={() => handleEditZone(zone)}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-primary"
                        title="Edit zone"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteZone(zone)}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-red-500"
                        title="Delete zone"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Zone Form Modal */}
      <Transition appear show={isFormModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseFormModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
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
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg border border-gray-800 bg-panel p-6 shadow-dark-xl transition-all">
                  <div className="flex items-center justify-between">
                    <Dialog.Title className="text-xl font-bold text-text-primary">
                      {editingZone ? 'Edit Zone' : 'Create Zone'}
                    </Dialog.Title>
                    <button
                      onClick={handleCloseFormModal}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  <form onSubmit={(e) => void handleSubmitForm(e)} className="mt-6 space-y-4">
                    {/* Name */}
                    <div>
                      <label htmlFor="zone-name" className="block text-sm font-medium text-text-primary">
                        Zone Name
                      </label>
                      <input
                        type="text"
                        id="zone-name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                          formErrors.name
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-800 focus:border-primary focus:ring-primary'
                        )}
                        placeholder="Front Door"
                      />
                      {formErrors.name && (
                        <p className="mt-1 text-sm text-red-500">{formErrors.name}</p>
                      )}
                    </div>

                    {/* Zone Type */}
                    <div>
                      <label htmlFor="zone-type" className="block text-sm font-medium text-text-primary">
                        Zone Type
                      </label>
                      <select
                        id="zone-type"
                        value={formData.zone_type}
                        onChange={(e) =>
                          setFormData({ ...formData, zone_type: e.target.value as ZoneType })
                        }
                        className="mt-1 block w-full rounded-lg border border-gray-800 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                      >
                        {ZONE_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Color */}
                    <div>
                      <span className="block text-sm font-medium text-text-primary">
                        Zone Color
                      </span>
                      <div className="mt-2 flex gap-2" role="group" aria-label="Zone color selection">
                        {DEFAULT_ZONE_COLORS.map((color) => (
                          <button
                            key={color}
                            type="button"
                            onClick={() => setFormData({ ...formData, color })}
                            className={clsx(
                              'h-8 w-8 rounded-full border-2 transition-all',
                              formData.color === color
                                ? 'border-white scale-110'
                                : 'border-transparent hover:scale-105'
                            )}
                            style={{ backgroundColor: color }}
                          />
                        ))}
                      </div>
                    </div>

                    {/* Priority */}
                    <div>
                      <label htmlFor="zone-priority" className="block text-sm font-medium text-text-primary">
                        Priority (0-100)
                      </label>
                      <input
                        type="number"
                        id="zone-priority"
                        min={0}
                        max={100}
                        value={formData.priority}
                        onChange={(e) =>
                          setFormData({ ...formData, priority: parseInt(e.target.value) || 0 })
                        }
                        className="mt-1 block w-full rounded-lg border border-gray-800 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                      />
                      <p className="mt-1 text-xs text-text-secondary">
                        Higher priority zones take precedence for overlapping detections
                      </p>
                    </div>

                    {/* Enabled */}
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        id="zone-enabled"
                        checked={formData.enabled}
                        onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                        className="h-4 w-4 rounded border-gray-800 bg-card text-primary focus:ring-primary"
                      />
                      <label htmlFor="zone-enabled" className="text-sm text-text-primary">
                        Zone is enabled
                      </label>
                    </div>

                    {/* Coordinates error */}
                    {formErrors.coordinates && (
                      <p className="text-sm text-red-500">{formErrors.coordinates}</p>
                    )}

                    {/* Actions */}
                    <div className="flex justify-end gap-3 pt-4">
                      <button
                        type="button"
                        onClick={handleCloseFormModal}
                        disabled={submitting}
                        className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={submitting}
                        className="rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 disabled:opacity-50"
                      >
                        {submitting ? 'Saving...' : editingZone ? 'Update Zone' : 'Create Zone'}
                      </button>
                    </div>
                  </form>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Delete Confirmation Modal */}
      <Transition appear show={isDeleteModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseDeleteModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
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
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-lg border border-gray-800 bg-panel p-6 shadow-dark-xl transition-all">
                  <div className="flex items-start gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
                      <AlertCircle className="h-6 w-6 text-red-500" />
                    </div>
                    <div className="flex-1">
                      <Dialog.Title className="text-lg font-semibold text-text-primary">
                        Delete Zone
                      </Dialog.Title>
                      <p className="mt-2 text-sm text-text-secondary">
                        Are you sure you want to delete{' '}
                        <span className="font-medium text-text-primary">
                          {deletingZone?.name}
                        </span>
                        ? This action cannot be undone.
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleCloseDeleteModal}
                      disabled={submitting}
                      className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleConfirmDelete()}
                      disabled={submitting}
                      className="rounded-lg bg-red-500 px-4 py-2 font-medium text-white transition-all hover:bg-red-600 disabled:opacity-50"
                    >
                      {submitting ? 'Deleting...' : 'Delete Zone'}
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  );
}
