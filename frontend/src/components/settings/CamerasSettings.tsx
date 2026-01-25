import { Dialog, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Camera as CameraIcon,
  Edit2,
  MapPin,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  X,
} from 'lucide-react';
import { Fragment, useState } from 'react';

import {
  useCamerasQuery,
  useCameraMutation,
  useDeletedCamerasQuery,
  useRestoreCameraMutation,
} from '../../hooks';
import {
  cameraFormSchema,
  CAMERA_NAME_CONSTRAINTS,
  CAMERA_FOLDER_PATH_CONSTRAINTS,
  CAMERA_STATUS_VALUES,
  type CameraStatusValue,
} from '../../schemas/camera';
import { formatRelativeTime, isTimestampStale } from '../../utils/time';
import CameraBaselinePanel from '../analytics/CameraBaselinePanel';
import SceneChangePanel from '../analytics/SceneChangePanel';
import IconButton from '../common/IconButton';
import { ZoneEditor } from '../zones';

import type { Camera, CameraCreate, CameraUpdate } from '../../services/api';

interface CameraFormData {
  name: string;
  folder_path: string;
  status: CameraStatusValue;
}

interface CameraFormErrors {
  name?: string;
  folder_path?: string;
  status?: string;
}

/**
 * CamerasSettings component for managing camera configurations
 * Features:
 * - List all cameras with status indicators
 * - Add new camera
 * - Edit existing camera
 * - Delete camera with confirmation (soft delete with restore)
 * - View and restore deleted cameras (trash view)
 */
export default function CamerasSettings() {
  // React Query hooks for data fetching and mutations
  const { cameras, isLoading, error: queryError, refetch } = useCamerasQuery();
  const { createMutation, updateMutation, deleteMutation } = useCameraMutation();

  // Deleted cameras hooks (soft delete feature - NEM-3643)
  const { deletedCameras, isLoading: isLoadingDeleted } = useDeletedCamerasQuery();
  const { restoreMutation } = useRestoreCameraMutation();

  // Modal and form state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [deletingCamera, setDeletingCamera] = useState<Camera | null>(null);
  const [formData, setFormData] = useState<CameraFormData>({
    name: '',
    folder_path: '',
    status: 'online',
  });
  const [formErrors, setFormErrors] = useState<CameraFormErrors>({});
  const [searchQuery, setSearchQuery] = useState('');

  // Delete confirmation state (type camera name to confirm)
  const [deleteConfirmInput, setDeleteConfirmInput] = useState('');

  // Show deleted cameras toggle (trash view)
  const [showDeletedCameras, setShowDeletedCameras] = useState(false);

  // Zone editor state
  const [zoneEditorCamera, setZoneEditorCamera] = useState<Camera | null>(null);

  // Scene change panel state
  const [sceneChangeCamera, setSceneChangeCamera] = useState<Camera | null>(null);

  // Baseline panel state
  const [baselineCamera, setBaselineCamera] = useState<Camera | null>(null);

  // Local error state for mutations (to display after modal closes)
  const [mutationError, setMutationError] = useState<string | null>(null);

  // Derive loading/error states from query and mutations
  const loading = isLoading;
  const error = queryError?.message ?? mutationError;
  const submitting =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
    restoreMutation.isPending;

  // Check if delete confirmation matches camera name
  const isDeleteConfirmed = deletingCamera?.name === deleteConfirmInput;

  // Filter cameras based on search query
  const filteredCameras = cameras.filter((camera) =>
    camera.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const validateForm = (data: CameraFormData): CameraFormErrors => {
    const errors: CameraFormErrors = {};

    // Validate using Zod schema (aligned with backend Pydantic schema)
    const result = cameraFormSchema.safeParse(data);
    if (!result.success) {
      for (const issue of result.error.issues) {
        const field = issue.path[0] as keyof CameraFormErrors;
        if (field && !errors[field]) {
          errors[field] = issue.message;
        }
      }
    }

    return errors;
  };

  const handleOpenAddModal = () => {
    setEditingCamera(null);
    setFormData({ name: '', folder_path: '', status: 'online' });
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (camera: Camera) => {
    setEditingCamera(camera);
    setFormData({
      name: camera.name,
      folder_path: camera.folder_path,
      status: camera.status,
    });
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingCamera(null);
    setFormData({ name: '', folder_path: '', status: 'online' });
    setFormErrors({});
  };

  const handleOpenDeleteModal = (camera: Camera) => {
    setDeletingCamera(camera);
    setDeleteConfirmInput('');
    setIsDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    setIsDeleteModalOpen(false);
    setDeletingCamera(null);
    setDeleteConfirmInput('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const errors = validateForm(formData);
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setFormErrors({});

    try {
      if (editingCamera) {
        // Update existing camera
        const updateData: CameraUpdate = {
          name: formData.name.trim(),
          folder_path: formData.folder_path.trim(),
          status: formData.status,
        };
        await updateMutation.mutateAsync({ id: editingCamera.id, data: updateData });
      } else {
        // Create new camera
        const createData: CameraCreate = {
          name: formData.name.trim(),
          folder_path: formData.folder_path.trim(),
          status: formData.status ?? 'online',
        };
        await createMutation.mutateAsync(createData);
      }

      // Cache is automatically invalidated by the mutation
      handleCloseModal();
    } catch (err) {
      setFormErrors({
        name: err instanceof Error ? err.message : 'Failed to save camera',
      });
    }
  };

  const handleDelete = async () => {
    if (!deletingCamera || !isDeleteConfirmed) return;

    try {
      await deleteMutation.mutateAsync(deletingCamera.id);
      // Cache is automatically invalidated by the mutation
      handleCloseDeleteModal();
    } catch (err) {
      // Set the error to display in the main error section
      setMutationError(err instanceof Error ? err.message : 'Failed to delete camera');
      handleCloseDeleteModal();
    }
  };

  const handleRestore = async (camera: Camera) => {
    try {
      await restoreMutation.mutateAsync(camera.id);
      // Cache is automatically invalidated by the mutation
    } catch (err) {
      setMutationError(err instanceof Error ? err.message : 'Failed to restore camera');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'online':
        return 'text-green-500';
      case 'offline':
        return 'text-gray-500';
      case 'error':
        return 'text-red-500';
      default:
        return 'text-gray-400';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-text-secondary">Loading cameras...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div>
            <h3 className="font-semibold text-red-500">Error loading cameras</h3>
            <p className="mt-1 text-sm text-red-400">{error}</p>
            <button
              onClick={() => {
                void refetch();
              }}
              className="mt-2 text-sm font-medium text-red-500 hover:text-red-400"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="settings-cameras">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Cameras</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Manage your security camera configurations
          </p>
        </div>
        <button
          onClick={handleOpenAddModal}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
        >
          <Plus className="h-4 w-4" />
          Add Camera
        </button>
      </div>

      {/* Search Bar */}
      {cameras.length > 0 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search cameras by name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-gray-800 bg-card py-2 pl-10 pr-4 text-text-primary placeholder-gray-500 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      )}

      {/* Cameras Table */}
      {cameras.length === 0 ? (
        <div className="rounded-lg border border-gray-800 bg-card p-8 text-center">
          <CameraIcon className="mx-auto h-12 w-12 text-gray-600" />
          <h3 className="mt-4 text-lg font-medium text-text-primary">No cameras configured</h3>
          <p className="mt-2 text-sm text-text-secondary">
            Add your first camera to start monitoring. Each camera should point to a folder where
            images are uploaded via FTP.
          </p>
          <button
            onClick={handleOpenAddModal}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <Plus className="h-4 w-4" />
            Add Camera
          </button>
        </div>
      ) : filteredCameras.length === 0 ? (
        <div className="rounded-lg border border-gray-800 bg-card p-8 text-center">
          <Search className="mx-auto h-12 w-12 text-gray-600" />
          <h3 className="mt-4 text-lg font-medium text-text-primary">No cameras found</h3>
          <p className="mt-2 text-sm text-text-secondary">
            No cameras match &quot;{searchQuery}&quot;. Try a different search term.
          </p>
          <button
            onClick={() => setSearchQuery('')}
            className="mt-4 rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700"
          >
            Clear Search
          </button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-800">
          <table className="w-full">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Folder Path
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Last Seen
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-text-secondary">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 bg-card">
              {filteredCameras.map((camera) => {
                const lastSeenAt = camera.last_seen_at ?? null;
                // NEM-3519: Display appropriate last seen text based on both timestamp and status
                // - If timestamp exists: show relative time
                // - If no timestamp: show status-appropriate message
                const getLastSeenText = (): string => {
                  if (lastSeenAt) {
                    return formatRelativeTime(lastSeenAt);
                  }
                  // No timestamp - show appropriate message based on camera status
                  switch (camera.status) {
                    case 'online':
                      // Online but no timestamp is unusual - camera might be newly active
                      return 'Recently active';
                    case 'offline':
                      return 'Never connected';
                    case 'error':
                      return 'No data available';
                    default:
                      return 'Awaiting first image';
                  }
                };
                const lastSeenText = getLastSeenText();
                const isStale = isTimestampStale(lastSeenAt);

                return (
                  <tr
                    key={camera.id}
                    className="cursor-pointer transition-colors hover:bg-[#76B900]/5"
                  >
                    <td className="whitespace-nowrap px-6 py-4">
                      <div className="flex items-center gap-3">
                        <CameraIcon className="h-5 w-5 text-gray-400" />
                        <span className="font-medium text-text-primary">{camera.name}</span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <span className="font-mono text-sm text-text-secondary">
                        {camera.folder_path}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span
                          className={clsx(
                            'h-2.5 w-2.5 rounded-full',
                            camera.status === 'online'
                              ? 'bg-green-500'
                              : camera.status === 'error'
                                ? 'bg-red-500'
                                : 'bg-gray-500'
                          )}
                          aria-hidden="true"
                          data-testid={`camera-status-indicator-${camera.id}`}
                        />
                        <span
                          className={clsx('font-medium capitalize', getStatusColor(camera.status))}
                        >
                          {camera.status}
                        </span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm">
                      <span
                        className={clsx(
                          isStale && lastSeenAt ? 'text-yellow-500' : 'text-text-secondary'
                        )}
                        title={
                          lastSeenAt
                            ? new Date(lastSeenAt).toLocaleString()
                            : 'Camera has not sent any images yet'
                        }
                      >
                        {lastSeenText}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <IconButton
                          icon={<AlertTriangle />}
                          aria-label={`View scene changes for ${camera.name}`}
                          onClick={() => setSceneChangeCamera(camera)}
                          variant="ghost"
                          size="md"
                          tooltip="Scene change detection"
                          data-testid={`scene-change-${camera.id}`}
                        />
                        <IconButton
                          icon={<Activity />}
                          aria-label={`View activity baseline for ${camera.name}`}
                          onClick={() => setBaselineCamera(camera)}
                          variant="ghost"
                          size="md"
                          tooltip="Activity baseline"
                          data-testid={`baseline-${camera.id}`}
                        />
                        <IconButton
                          icon={<MapPin />}
                          aria-label={`Configure zones for ${camera.name}`}
                          onClick={() => setZoneEditorCamera(camera)}
                          variant="ghost"
                          size="md"
                          tooltip="Configure detection zones"
                        />
                        <IconButton
                          icon={<Edit2 />}
                          aria-label={`Edit ${camera.name}`}
                          onClick={() => handleOpenEditModal(camera)}
                          variant="ghost"
                          size="md"
                          tooltip="Edit camera settings"
                          data-testid={`edit-camera-${camera.id}`}
                        />
                        <IconButton
                          icon={<Trash2 />}
                          aria-label={`Delete ${camera.name}`}
                          onClick={() => handleOpenDeleteModal(camera)}
                          variant="ghost"
                          size="md"
                          tooltip="Delete camera"
                          className="hover:!text-red-500 focus-visible:!ring-red-500"
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Show Deleted Cameras Toggle */}
      {(deletedCameras.length > 0 || showDeletedCameras) && (
        <div className="border-t border-gray-800 pt-6">
          <button
            onClick={() => setShowDeletedCameras(!showDeletedCameras)}
            className="inline-flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
            data-testid="show-deleted-toggle"
          >
            <Trash2 className="h-4 w-4" />
            {showDeletedCameras ? 'Hide deleted cameras' : 'Show deleted cameras'}
            {deletedCameras.length > 0 && (
              <span className="ml-1 rounded-full bg-gray-800 px-2 py-0.5 text-xs">
                {deletedCameras.length}
              </span>
            )}
          </button>
        </div>
      )}

      {/* Deleted Cameras Section (Trash View) */}
      {showDeletedCameras && (
        <div className="space-y-4" data-testid="deleted-cameras-section">
          <div className="flex items-center gap-2">
            <Trash2 className="h-5 w-5 text-gray-400" />
            <h3 className="text-lg font-semibold text-text-primary">Deleted Cameras</h3>
          </div>

          {isLoadingDeleted ? (
            <div className="flex items-center justify-center py-8">
              <div className="text-text-secondary">Loading deleted cameras...</div>
            </div>
          ) : deletedCameras.length === 0 ? (
            <div className="rounded-lg border border-gray-800 bg-card p-6 text-center">
              <Trash2 className="mx-auto h-10 w-10 text-gray-600" />
              <p className="mt-3 text-sm text-text-secondary">No deleted cameras</p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-gray-800">
              <table className="w-full">
                <thead className="bg-gray-900">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-secondary">
                      Folder Path
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-text-secondary">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800 bg-card">
                  {deletedCameras.map((camera) => (
                    <tr
                      key={camera.id}
                      className="opacity-60"
                      data-testid={`deleted-camera-row-${camera.id}`}
                    >
                      <td className="whitespace-nowrap px-6 py-4">
                        <div className="flex items-center gap-3">
                          <CameraIcon className="h-5 w-5 text-gray-500" />
                          <span className="font-medium text-text-secondary line-through">
                            {camera.name}
                          </span>
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4">
                        <span className="font-mono text-sm text-text-secondary line-through">
                          {camera.folder_path}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-6 py-4 text-right">
                        <IconButton
                          icon={<RotateCcw />}
                          aria-label={`Restore ${camera.name}`}
                          onClick={() => {
                            void handleRestore(camera);
                          }}
                          variant="ghost"
                          size="md"
                          tooltip="Restore camera"
                          disabled={restoreMutation.isPending}
                          className="hover:!text-green-500 focus-visible:!ring-green-500"
                          data-testid={`restore-camera-${camera.id}`}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Add/Edit Camera Modal */}
      <Transition appear show={isModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseModal}>
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
                      {editingCamera ? 'Edit Camera' : 'Add Camera'}
                    </Dialog.Title>
                    <button
                      onClick={handleCloseModal}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary focus:outline-none"
                      aria-label="Close modal"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  <form
                    onSubmit={(e) => {
                      void handleSubmit(e);
                    }}
                    className="mt-6 space-y-4"
                  >
                    {/* Name Input */}
                    <div>
                      <label htmlFor="name" className="block text-sm font-medium text-text-primary">
                        Camera Name
                      </label>
                      <input
                        type="text"
                        id="name"
                        data-testid="camera-name-input"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        maxLength={CAMERA_NAME_CONSTRAINTS.maxLength}
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

                    {/* Folder Path Input */}
                    <div>
                      <label
                        htmlFor="folder_path"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Folder Path
                      </label>
                      <input
                        type="text"
                        id="folder_path"
                        data-testid="camera-folder-path-input"
                        value={formData.folder_path}
                        onChange={(e) => setFormData({ ...formData, folder_path: e.target.value })}
                        maxLength={CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength}
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-card px-3 py-2 font-mono text-sm text-text-primary focus:outline-none focus:ring-2',
                          formErrors.folder_path
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-800 focus:border-primary focus:ring-primary'
                        )}
                        placeholder="/export/foscam/front_door"
                      />
                      {formErrors.folder_path && (
                        <p className="mt-1 text-sm text-red-500">{formErrors.folder_path}</p>
                      )}
                    </div>

                    {/* Status Select */}
                    <div>
                      <label
                        htmlFor="status"
                        className="block text-sm font-medium text-text-primary"
                      >
                        Status
                      </label>
                      <select
                        id="status"
                        data-testid="camera-status-select"
                        value={formData.status}
                        onChange={(e) =>
                          setFormData({ ...formData, status: e.target.value as CameraStatusValue })
                        }
                        className={clsx(
                          'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                          formErrors.status
                            ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                            : 'border-gray-800 focus:border-primary focus:ring-primary'
                        )}
                      >
                        {CAMERA_STATUS_VALUES.map((status) => (
                          <option key={status} value={status}>
                            {status.charAt(0).toUpperCase() + status.slice(1)}
                          </option>
                        ))}
                      </select>
                      {formErrors.status && (
                        <p className="mt-1 text-sm text-red-500">{formErrors.status}</p>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex justify-end gap-3 pt-4">
                      <button
                        type="button"
                        onClick={handleCloseModal}
                        disabled={submitting}
                        className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={submitting}
                        data-testid="save-settings"
                        className="rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
                      >
                        {submitting ? 'Saving...' : editingCamera ? 'Update' : 'Add Camera'}
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
                        Delete Camera
                      </Dialog.Title>
                      <p className="mt-2 text-sm text-text-secondary">
                        Are you sure you want to delete{' '}
                        <span className="font-medium text-text-primary">
                          {deletingCamera?.name}
                        </span>
                        ?
                      </p>
                    </div>
                  </div>

                  {/* Warning about related data */}
                  <div className="mt-4 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-3">
                    <div className="flex gap-2 text-sm text-yellow-300">
                      <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-medium">This will affect related data</p>
                        <ul className="mt-1 list-disc pl-4 text-yellow-300/80">
                          <li>All detections from this camera will be hidden</li>
                          <li>Events associated with this camera will be affected</li>
                          <li>Zone configurations will be preserved</li>
                        </ul>
                        <p className="mt-2">
                          The camera can be restored from the &quot;Show deleted cameras&quot; section.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Type to confirm */}
                  <div className="mt-4">
                    <label
                      htmlFor="delete-confirm"
                      className="block text-sm font-medium text-text-primary"
                    >
                      Type{' '}
                      <span className="font-mono text-red-400">{deletingCamera?.name}</span>{' '}
                      to confirm
                    </label>
                    <input
                      type="text"
                      id="delete-confirm"
                      data-testid="delete-confirm-input"
                      value={deleteConfirmInput}
                      onChange={(e) => setDeleteConfirmInput(e.target.value)}
                      className="mt-1 block w-full rounded-lg border border-gray-800 bg-card px-3 py-2 text-text-primary focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500"
                      placeholder={deletingCamera?.name}
                      autoComplete="off"
                    />
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleCloseDeleteModal}
                      disabled={submitting}
                      className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        void handleDelete();
                      }}
                      disabled={submitting || !isDeleteConfirmed}
                      data-testid="confirm-delete-button"
                      className="rounded-lg bg-red-700 px-4 py-2 font-medium text-white transition-all hover:bg-red-800 focus:outline-none focus:ring-2 focus:ring-red-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {submitting ? 'Deleting...' : 'Delete Camera'}
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Zone Editor Modal */}
      {zoneEditorCamera && (
        <ZoneEditor
          camera={zoneEditorCamera}
          isOpen={Boolean(zoneEditorCamera)}
          onClose={() => setZoneEditorCamera(null)}
        />
      )}

      {/* Scene Change Panel Modal */}
      <Transition appear show={Boolean(sceneChangeCamera)} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setSceneChangeCamera(null)}>
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
                <Dialog.Panel className="w-full max-w-2xl transform overflow-hidden rounded-lg border border-gray-800 bg-panel p-6 shadow-dark-xl transition-all">
                  <div className="mb-4 flex items-center justify-between">
                    <Dialog.Title className="text-xl font-bold text-text-primary">
                      Scene Change Detection
                    </Dialog.Title>
                    <button
                      onClick={() => setSceneChangeCamera(null)}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary focus:outline-none"
                      aria-label="Close modal"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  {sceneChangeCamera && (
                    <SceneChangePanel
                      cameraId={sceneChangeCamera.id}
                      cameraName={sceneChangeCamera.name}
                    />
                  )}
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Activity Baseline Panel Modal */}
      <Transition appear show={Boolean(baselineCamera)} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setBaselineCamera(null)}>
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
                <Dialog.Panel className="w-full max-w-4xl transform overflow-hidden rounded-lg border border-gray-800 bg-panel p-6 shadow-dark-xl transition-all">
                  <div className="mb-4 flex items-center justify-between">
                    <Dialog.Title className="text-xl font-bold text-text-primary">
                      Activity Baseline
                    </Dialog.Title>
                    <button
                      onClick={() => setBaselineCamera(null)}
                      className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-800 hover:text-text-primary focus:outline-none"
                      aria-label="Close modal"
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>

                  {baselineCamera && (
                    <CameraBaselinePanel
                      cameraId={baselineCamera.id}
                      cameraName={baselineCamera.name}
                    />
                  )}
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  );
}
