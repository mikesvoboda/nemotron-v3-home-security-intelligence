/**
 * TrashPage - Displays soft-deleted cameras and events for recovery
 *
 * Features:
 * - Lists soft-deleted cameras and events
 * - Shows deleted_at timestamp for each item
 * - Allows restoring individual items
 * - Confirmation dialog before restore
 * - Toast notifications for success/error
 * - Empty state when no deleted items
 * - Loading and error states
 */

import { Tab } from '@headlessui/react';
import { clsx } from 'clsx';
import { format } from 'date-fns';
import {
  AlertTriangle,
  Camera,
  Calendar,
  RefreshCw,
  RotateCcw,
  Trash2,
} from 'lucide-react';
import { Fragment, useCallback, useState } from 'react';

import { useToast } from '../../hooks/useToast';
import {
  fetchDeletedItems,
  restoreCamera,
  restoreEvent,
  type DeletedCamera,
  type DeletedEvent,
  type TrashListResponse,
} from '../../services/api';
import { AnimatedModal, EmptyState } from '../common';

import type { LucideIcon } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

type RestoreType = 'camera' | 'event';

interface RestoreConfirmation {
  type: RestoreType;
  id: string | number;
  name: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format the deleted_at timestamp for display
 */
function formatDeletedAt(deletedAt: string): string {
  try {
    return format(new Date(deletedAt), 'MMM d, yyyy h:mm a');
  } catch {
    return deletedAt;
  }
}

/**
 * Calculate time since deletion
 */
function getTimeSinceDeleted(deletedAt: string): string {
  try {
    const deleted = new Date(deletedAt);
    const now = new Date();
    const diffMs = now.getTime() - deleted.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));

    if (diffDays > 0) {
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } else if (diffHours > 0) {
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else if (diffMinutes > 0) {
      return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
    }
    return 'Just now';
  } catch {
    return '';
  }
}

// ============================================================================
// Sub-components
// ============================================================================

interface DeletedCameraRowProps {
  camera: DeletedCamera;
  onRestore: (camera: DeletedCamera) => void;
  isRestoring: boolean;
}

function DeletedCameraRow({ camera, onRestore, isRestoring }: DeletedCameraRowProps) {
  return (
    <tr className="border-b border-gray-800 hover:bg-gray-800/50" data-testid={`deleted-camera-${camera.id}`}>
      <td className="whitespace-nowrap px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-800">
            <Camera className="h-5 w-5 text-gray-400" aria-hidden="true" />
          </div>
          <div>
            <div className="font-medium text-white">{camera.name}</div>
            <div className="text-sm text-gray-400">{camera.id}</div>
          </div>
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-400">
        {camera.folder_path}
      </td>
      <td className="whitespace-nowrap px-4 py-3">
        <div className="text-sm text-gray-400">
          {formatDeletedAt(camera.deleted_at)}
        </div>
        <div className="text-xs text-gray-500">
          {getTimeSinceDeleted(camera.deleted_at)}
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-right">
        <button
          onClick={() => onRestore(camera)}
          disabled={isRestoring}
          className={clsx(
            'inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
            'bg-[#76B900] text-black hover:bg-[#88d200]',
            'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]',
            isRestoring && 'cursor-not-allowed opacity-50'
          )}
          data-testid={`restore-camera-${camera.id}`}
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Restore
        </button>
      </td>
    </tr>
  );
}

interface DeletedEventRowProps {
  event: DeletedEvent;
  onRestore: (event: DeletedEvent) => void;
  isRestoring: boolean;
}

function DeletedEventRow({ event, onRestore, isRestoring }: DeletedEventRowProps) {
  return (
    <tr className="border-b border-gray-800 hover:bg-gray-800/50" data-testid={`deleted-event-${event.id}`}>
      <td className="whitespace-nowrap px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-800">
            <Calendar className="h-5 w-5 text-gray-400" aria-hidden="true" />
          </div>
          <div>
            <div className="font-medium text-white">Event #{event.id}</div>
            <div className="text-sm text-gray-400">{event.camera_id}</div>
          </div>
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="max-w-xs truncate text-sm text-gray-400">
          {event.summary || 'No summary available'}
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3">
        <span
          className={clsx(
            'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
            {
              'bg-green-500/10 text-green-400': event.risk_level === 'low',
              'bg-yellow-500/10 text-yellow-400': event.risk_level === 'medium',
              'bg-red-500/10 text-red-400': event.risk_level === 'high' || event.risk_level === 'critical',
            }
          )}
        >
          {event.risk_level || 'unknown'}
        </span>
      </td>
      <td className="whitespace-nowrap px-4 py-3">
        <div className="text-sm text-gray-400">
          {formatDeletedAt(event.deleted_at)}
        </div>
        <div className="text-xs text-gray-500">
          {getTimeSinceDeleted(event.deleted_at)}
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-right">
        <button
          onClick={() => onRestore(event)}
          disabled={isRestoring}
          className={clsx(
            'inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
            'bg-[#76B900] text-black hover:bg-[#88d200]',
            'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]',
            isRestoring && 'cursor-not-allowed opacity-50'
          )}
          data-testid={`restore-event-${event.id}`}
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Restore
        </button>
      </td>
    </tr>
  );
}

interface ConfirmRestoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  confirmation: RestoreConfirmation | null;
  isRestoring: boolean;
}

function ConfirmRestoreModal({
  isOpen,
  onClose,
  onConfirm,
  confirmation,
  isRestoring,
}: ConfirmRestoreModalProps) {
  return (
    <AnimatedModal
      isOpen={isOpen}
      onClose={onClose}
      size="sm"
      aria-labelledby="restore-modal-title"
      aria-describedby="restore-modal-description"
    >
      <div className="p-6">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#76B900]/10">
            <RotateCcw className="h-6 w-6 text-[#76B900]" aria-hidden="true" />
          </div>
          <h2 id="restore-modal-title" className="text-lg font-semibold text-white">
            Restore {confirmation?.type === 'camera' ? 'Camera' : 'Event'}
          </h2>
        </div>

        <p id="restore-modal-description" className="mb-6 text-sm text-gray-400">
          Are you sure you want to restore <span className="font-medium text-white">{confirmation?.name}</span>?
          This will move it back to the active list.
        </p>

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isRestoring}
            className={clsx(
              'rounded-lg border border-gray-700 bg-transparent px-4 py-2 text-sm font-medium text-gray-300',
              'transition-colors hover:border-gray-600 hover:bg-gray-800',
              'focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900',
              isRestoring && 'cursor-not-allowed opacity-50'
            )}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isRestoring}
            className={clsx(
              'inline-flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-black',
              'transition-colors hover:bg-[#88d200]',
              'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900',
              isRestoring && 'cursor-not-allowed opacity-50'
            )}
            data-testid="confirm-restore-button"
          >
            {isRestoring ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
                Restoring...
              </>
            ) : (
              <>
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                Restore
              </>
            )}
          </button>
        </div>
      </div>
    </AnimatedModal>
  );
}

// ============================================================================
// Tab Components
// ============================================================================

interface TabConfig {
  id: string;
  name: string;
  icon: LucideIcon;
  count: number;
}

// ============================================================================
// Main Component
// ============================================================================

export default function TrashPage() {
  // State
  const [data, setData] = useState<TrashListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRestoring, setIsRestoring] = useState(false);
  const [confirmation, setConfirmation] = useState<RestoreConfirmation | null>(null);

  // Hooks
  const toast = useToast();

  // Fetch deleted items on mount
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchDeletedItems();
      setData(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load deleted items';
      setError(message);
      toast.error('Failed to load deleted items', { description: message });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  // Fetch on mount
  useState(() => {
    void fetchData();
  });

  // Handle restore camera
  const handleRestoreCamera = useCallback((camera: DeletedCamera) => {
    setConfirmation({
      type: 'camera',
      id: camera.id,
      name: camera.name,
    });
  }, []);

  // Handle restore event
  const handleRestoreEvent = useCallback((event: DeletedEvent) => {
    setConfirmation({
      type: 'event',
      id: event.id,
      name: `Event #${event.id}`,
    });
  }, []);

  // Confirm restore
  const handleConfirmRestore = useCallback(async () => {
    if (!confirmation) return;

    setIsRestoring(true);

    try {
      if (confirmation.type === 'camera') {
        await restoreCamera(confirmation.id as string);
        toast.success(`Camera "${confirmation.name}" restored successfully`);
      } else {
        await restoreEvent(confirmation.id as number);
        toast.success(`Event #${confirmation.id} restored successfully`);
      }

      // Refresh the list
      await fetchData();
      setConfirmation(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to restore item';
      toast.error('Failed to restore', { description: message });
    } finally {
      setIsRestoring(false);
    }
  }, [confirmation, fetchData, toast]);

  // Close confirmation modal
  const handleCloseConfirmation = useCallback(() => {
    if (!isRestoring) {
      setConfirmation(null);
    }
  }, [isRestoring]);

  // Tab configuration
  const tabs: TabConfig[] = [
    {
      id: 'cameras',
      name: 'CAMERAS',
      icon: Camera,
      count: data?.camera_count ?? 0,
    },
    {
      id: 'events',
      name: 'EVENTS',
      icon: Calendar,
      count: data?.event_count ?? 0,
    },
  ];

  // Render loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="trash-page-loading">
        <div className="mx-auto max-w-[1920px]">
          <div className="mb-8">
            <div className="h-8 w-32 animate-pulse rounded bg-gray-800" />
            <div className="mt-2 h-4 w-64 animate-pulse rounded bg-gray-800" />
          </div>
          <div className="rounded-lg border border-gray-800 bg-[#1A1A1A] p-6">
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 animate-pulse rounded bg-gray-800" />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="trash-page-error">
        <div className="mx-auto max-w-[1920px]">
          <EmptyState
            icon={AlertTriangle}
            title="Error Loading Trash"
            description={error}
            variant="warning"
            actions={[
              {
                label: 'Retry',
                onClick: () => void fetchData(),
                variant: 'primary',
              },
            ]}
          />
        </div>
      </div>
    );
  }

  const totalItems = (data?.camera_count ?? 0) + (data?.event_count ?? 0);

  return (
    <div className="min-h-screen bg-[#121212] p-8" data-testid="trash-page">
      <div className="mx-auto max-w-[1920px]">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <Trash2 className="h-8 w-8 text-gray-400" aria-hidden="true" />
            <h1 className="text-page-title">Trash</h1>
          </div>
          <p className="text-body-sm mt-2">
            View and restore soft-deleted cameras and events. Items in trash can be restored at any time.
          </p>
        </div>

        {/* Empty State */}
        {totalItems === 0 && (
          <div className="rounded-lg border border-gray-800 bg-[#1A1A1A]">
            <EmptyState
              icon={Trash2}
              title="Trash is Empty"
              description="There are no deleted cameras or events to display. Deleted items will appear here for recovery."
              variant="muted"
              size="lg"
            />
          </div>
        )}

        {/* Tabs */}
        {totalItems > 0 && (
          <Tab.Group>
            <Tab.List className="mb-6 flex space-x-2 rounded-lg border border-gray-800 bg-[#1A1A1A] p-1">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <Tab key={tab.id} as={Fragment}>
                    {({ selected }) => (
                      <button
                        className={clsx(
                          'flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-medium transition-all duration-200',
                          'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
                          selected
                            ? 'bg-[#76B900] text-gray-950 shadow-md'
                            : 'text-gray-200 hover:bg-gray-800 hover:text-white'
                        )}
                        data-selected={selected}
                        data-testid={`tab-${tab.id}`}
                      >
                        <Icon className="h-5 w-5" aria-hidden="true" />
                        <span>{tab.name}</span>
                        <span
                          className={clsx(
                            'ml-1 rounded-full px-2 py-0.5 text-xs font-semibold',
                            selected ? 'bg-black/20 text-gray-900' : 'bg-gray-700 text-gray-300'
                          )}
                        >
                          {tab.count}
                        </span>
                      </button>
                    )}
                  </Tab>
                );
              })}
            </Tab.List>

            <Tab.Panels>
              {/* Cameras Panel */}
              <Tab.Panel
                className={clsx(
                  'rounded-lg border border-gray-800 bg-[#1A1A1A]',
                  'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]'
                )}
                data-testid="cameras-panel"
              >
                {(data?.cameras?.length ?? 0) === 0 ? (
                  <EmptyState
                    icon={Camera}
                    title="No Deleted Cameras"
                    description="There are no deleted cameras to restore."
                    variant="muted"
                    size="sm"
                  />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full">
                      <thead>
                        <tr className="border-b border-gray-800">
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                            Camera
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                            Folder Path
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                            Deleted
                          </th>
                          <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-400">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {data?.cameras?.map((camera) => (
                          <DeletedCameraRow
                            key={camera.id}
                            camera={camera}
                            onRestore={handleRestoreCamera}
                            isRestoring={isRestoring}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Tab.Panel>

              {/* Events Panel */}
              <Tab.Panel
                className={clsx(
                  'rounded-lg border border-gray-800 bg-[#1A1A1A]',
                  'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#121212]'
                )}
                data-testid="events-panel"
              >
                {(data?.events?.length ?? 0) === 0 ? (
                  <EmptyState
                    icon={Calendar}
                    title="No Deleted Events"
                    description="There are no deleted events to restore."
                    variant="muted"
                    size="sm"
                  />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full">
                      <thead>
                        <tr className="border-b border-gray-800">
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                            Event
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                            Summary
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                            Risk Level
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-400">
                            Deleted
                          </th>
                          <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-400">
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {data?.events?.map((event) => (
                          <DeletedEventRow
                            key={event.id}
                            event={event}
                            onRestore={handleRestoreEvent}
                            isRestoring={isRestoring}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Tab.Panel>
            </Tab.Panels>
          </Tab.Group>
        )}

        {/* Confirmation Modal */}
        <ConfirmRestoreModal
          isOpen={confirmation !== null}
          onClose={handleCloseConfirmation}
          onConfirm={() => void handleConfirmRestore()}
          confirmation={confirmation}
          isRestoring={isRestoring}
        />
      </div>
    </div>
  );
}
