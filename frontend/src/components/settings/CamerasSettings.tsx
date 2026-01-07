import { Dialog, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import { AlertCircle, Camera as CameraIcon, Edit2, MapPin, Plus, Trash2, X } from 'lucide-react';
import { Fragment, useEffect, useState } from 'react';

import {
  createCamera,
  deleteCamera,
  fetchCameras,
  updateCamera,
  type Camera,
  type CameraCreate,
  type CameraUpdate,
} from '../../services/api';
import { ZoneEditor } from '../zones';

/** Valid camera status values matching backend CameraStatus enum */
type CameraStatusValue = 'online' | 'offline' | 'error' | 'unknown';

interface CameraFormData {
  name: string;
  folder_path: string;
  status?: CameraStatusValue;
}

interface CameraFormErrors {
  name?: string;
  folder_path?: string;
}

/**
 * CamerasSettings component for managing camera configurations
 * Features:
 * - List all cameras with status indicators
 * - Add new camera
 * - Edit existing camera
 * - Delete camera with confirmation
 */
export default function CamerasSettings() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
  const [submitting, setSubmitting] = useState(false);

  // Zone editor state
  const [zoneEditorCamera, setZoneEditorCamera] = useState<Camera | null>(null);

  // Load cameras on mount
  useEffect(() => {
    void loadCameras();
  }, []);

  const loadCameras = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchCameras();
      setCameras(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cameras');
    } finally {
      setLoading(false);
    }
  };

  const validateForm = (data: CameraFormData): CameraFormErrors => {
    const errors: CameraFormErrors = {};

    if (!data.name || data.name.trim().length < 2) {
      errors.name = 'Name must be at least 2 characters';
    }

    if (!data.folder_path || data.folder_path.trim().length === 0) {
      errors.folder_path = 'Folder path is required';
    } else if (!isValidPath(data.folder_path)) {
      errors.folder_path = 'Folder path must be a valid path format';
    }

    return errors;
  };

  const isValidPath = (path: string): boolean => {
    // Basic path validation - must start with / or contain path separators
    return /^[/.][a-zA-Z0-9_\-/.]+$/.test(path.trim());
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
    setIsDeleteModalOpen(true);
  };

  const handleCloseDeleteModal = () => {
    setIsDeleteModalOpen(false);
    setDeletingCamera(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const errors = validateForm(formData);
    if (Object.keys(errors).length > 0) {
      setFormErrors(errors);
      return;
    }

    setSubmitting(true);
    setFormErrors({});

    try {
      if (editingCamera) {
        // Update existing camera
        const updateData: CameraUpdate = {
          name: formData.name.trim(),
          folder_path: formData.folder_path.trim(),
          status: formData.status,
        };
        await updateCamera(editingCamera.id, updateData);
      } else {
        // Create new camera
        const createData: CameraCreate = {
          name: formData.name.trim(),
          folder_path: formData.folder_path.trim(),
          status: formData.status ?? 'online',
        };
        await createCamera(createData);
      }

      // Reload cameras and close modal
      await loadCameras();
      handleCloseModal();
    } catch (err) {
      setFormErrors({
        name: err instanceof Error ? err.message : 'Failed to save camera',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deletingCamera) return;

    setSubmitting(true);

    try {
      await deleteCamera(deletingCamera.id);
      await loadCameras();
      handleCloseDeleteModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete camera');
      handleCloseDeleteModal();
    } finally {
      setSubmitting(false);
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
                void loadCameras();
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
    <div className="space-y-6">
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

      {/* Cameras Table */}
      {cameras.length === 0 ? (
        <div className="rounded-lg border border-gray-800 bg-card p-8 text-center">
          <CameraIcon className="mx-auto h-12 w-12 text-gray-600" />
          <h3 className="mt-4 text-lg font-medium text-text-primary">No cameras configured</h3>
          <p className="mt-2 text-sm text-text-secondary">
            Get started by adding your first camera
          </p>
          <button
            onClick={handleOpenAddModal}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <Plus className="h-4 w-4" />
            Add Camera
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
              {cameras.map((camera) => (
                <tr key={camera.id} className="hover:bg-gray-900/50">
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
                    <span className={clsx('font-medium capitalize', getStatusColor(camera.status))}>
                      {camera.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-sm text-text-secondary">
                    {camera.last_seen_at ? new Date(camera.last_seen_at).toLocaleString() : 'Never'}
                  </td>
                  <td className="whitespace-nowrap px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => setZoneEditorCamera(camera)}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary"
                        aria-label={`Configure zones for ${camera.name}`}
                        title="Configure Zones"
                      >
                        <MapPin className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleOpenEditModal(camera)}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary"
                        aria-label={`Edit ${camera.name}`}
                        title="Edit Camera"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleOpenDeleteModal(camera)}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-red-500 focus:outline-none focus:ring-2 focus:ring-red-500"
                        aria-label={`Delete ${camera.name}`}
                        title="Delete Camera"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
                        value={formData.folder_path}
                        onChange={(e) => setFormData({ ...formData, folder_path: e.target.value })}
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
                        value={formData.status}
                        onChange={(e) => setFormData({ ...formData, status: e.target.value as CameraStatusValue })}
                        className="mt-1 block w-full rounded-lg border border-gray-800 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                      >
                        <option value="online">Online</option>
                        <option value="offline">Offline</option>
                        <option value="error">Error</option>
                      </select>
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
                        ? This action cannot be undone.
                      </p>
                    </div>
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
                      disabled={submitting}
                      className="rounded-lg bg-red-600 px-4 py-2 font-medium text-white transition-all hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-600 disabled:opacity-50"
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
    </div>
  );
}
