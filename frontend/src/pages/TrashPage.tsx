/**
 * TrashPage - Page component for viewing and managing soft-deleted events
 *
 * Features:
 * - Lists all soft-deleted events
 * - Restore events back to active state
 * - Permanently delete events
 * - Shows empty state when trash is empty
 * - 30-day auto-deletion notice
 * - Bulk selection and actions (restore/delete multiple)
 * - Empty Trash functionality
 *
 * @module pages/TrashPage
 */

import { AlertCircle, AlertTriangle, Info, RotateCcw, Trash2, X } from 'lucide-react';
import { useCallback, useState } from 'react';

import Button from '../components/common/Button';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import DeletedEventCard from '../components/events/DeletedEventCard';
import ConfirmDialog from '../components/jobs/ConfirmDialog';
import {
  useDeletedEventsQuery,
  useRestoreEventMutation,
  usePermanentDeleteMutation,
} from '../hooks/useTrashQuery';

// ============================================================================
// Types
// ============================================================================

type DeleteConfirmationType = 'single' | 'selected' | 'all';

interface DeleteConfirmationState {
  isOpen: boolean;
  type: DeleteConfirmationType;
  eventId?: number;
  count: number;
}

// ============================================================================
// BulkActionBar Component
// ============================================================================

interface BulkActionBarProps {
  selectedCount: number;
  onRestoreSelected: () => void;
  onDeleteSelected: () => void;
  onClearSelection: () => void;
  isRestoring: boolean;
  isDeleting: boolean;
}

/**
 * BulkActionBar displays when items are selected, showing action buttons.
 */
function BulkActionBar({
  selectedCount,
  onRestoreSelected,
  onDeleteSelected,
  onClearSelection,
  isRestoring,
  isDeleting,
}: BulkActionBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div
      className="mb-4 flex items-center justify-between rounded-lg border border-primary/30 bg-primary/10 p-3"
      data-testid="bulk-action-bar"
    >
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium text-white">
          {selectedCount} {selectedCount === 1 ? 'event' : 'events'} selected
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline-primary"
            size="sm"
            leftIcon={<RotateCcw className="h-4 w-4" />}
            onClick={onRestoreSelected}
            isLoading={isRestoring}
            disabled={isDeleting}
            data-testid="restore-selected-button"
          >
            Restore Selected
          </Button>
          <Button
            variant="danger"
            size="sm"
            leftIcon={<Trash2 className="h-4 w-4" />}
            onClick={onDeleteSelected}
            disabled={isRestoring || isDeleting}
            data-testid="delete-selected-button"
          >
            Delete Selected
          </Button>
        </div>
      </div>
      <Button
        variant="ghost"
        size="sm"
        leftIcon={<X className="h-4 w-4" />}
        onClick={onClearSelection}
        disabled={isRestoring || isDeleting}
        data-testid="clear-selection-button"
      >
        Clear
      </Button>
    </div>
  );
}

// ============================================================================
// DeleteConfirmationModal Component
// ============================================================================

interface DeleteConfirmationModalProps {
  isOpen: boolean;
  type: DeleteConfirmationType;
  count: number;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading: boolean;
}

/**
 * DeleteConfirmationModal shows a warning before permanent deletion.
 */
function DeleteConfirmationModal({
  isOpen,
  type,
  count,
  onConfirm,
  onCancel,
  isLoading,
}: DeleteConfirmationModalProps) {
  const getTitle = () => {
    if (type === 'all') {
      return `Empty Trash? (${count} ${count === 1 ? 'event' : 'events'})`;
    }
    if (type === 'selected') {
      return `Permanently Delete ${count} ${count === 1 ? 'Event' : 'Events'}?`;
    }
    return 'Permanently Delete Event?';
  };

  const getDescription = () => {
    if (type === 'all') {
      return 'This will permanently delete all events in the trash. This action cannot be undone and all associated data will be removed forever.';
    }
    if (type === 'selected') {
      return `This will permanently delete the ${count} selected ${count === 1 ? 'event' : 'events'}. This action cannot be undone and all associated data will be removed forever.`;
    }
    return 'This event will be permanently deleted. This action cannot be undone and all associated data will be removed forever.';
  };

  return (
    <ConfirmDialog
      isOpen={isOpen}
      title={getTitle()}
      description={getDescription()}
      confirmLabel="Delete Forever"
      cancelLabel="Cancel"
      variant="danger"
      isLoading={isLoading}
      loadingText="Deleting..."
      onConfirm={onConfirm}
      onCancel={onCancel}
    />
  );
}

// ============================================================================
// TrashPage Component
// ============================================================================

/**
 * TrashPage displays soft-deleted events with options to restore or permanently delete them.
 */
export default function TrashPage() {
  const { deletedEvents, isLoading, error, isEmpty, refetch } = useDeletedEventsQuery();
  const restoreMutation = useRestoreEventMutation();
  const permanentDeleteMutation = usePermanentDeleteMutation();

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Delete confirmation modal state
  const [deleteConfirmation, setDeleteConfirmation] = useState<DeleteConfirmationState>({
    isOpen: false,
    type: 'single',
    count: 0,
  });

  // Bulk operation state
  const [isBulkRestoring, setIsBulkRestoring] = useState(false);
  const [isBulkDeleting, setIsBulkDeleting] = useState(false);
  const [bulkError, setBulkError] = useState<string | null>(null);

  // ============================================================================
  // Selection handlers
  // ============================================================================

  const handleSelectionChange = useCallback((eventId: number, selected: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (selected) {
        next.add(eventId);
      } else {
        next.delete(eventId);
      }
      return next;
    });
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelectedIds(new Set(deletedEvents.map((e) => e.id)));
  }, [deletedEvents]);

  // ============================================================================
  // Individual event handlers
  // ============================================================================

  const handleRestore = useCallback(
    (eventId: number) => {
      restoreMutation.mutate(eventId);
      // Remove from selection after restore
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    },
    [restoreMutation]
  );

  const handlePermanentDelete = useCallback(
    (eventId: number) => {
      permanentDeleteMutation.mutate(eventId);
      // Remove from selection after delete
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    },
    [permanentDeleteMutation]
  );

  // ============================================================================
  // Bulk operation handlers
  // ============================================================================

  const handleRestoreSelected = useCallback(async () => {
    if (selectedIds.size === 0) return;

    setIsBulkRestoring(true);
    setBulkError(null);

    try {
      const promises = Array.from(selectedIds).map((id) => restoreMutation.mutateAsync(id));
      await Promise.all(promises);
      setSelectedIds(new Set());
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : 'Failed to restore some events');
    } finally {
      setIsBulkRestoring(false);
    }
  }, [selectedIds, restoreMutation]);

  const handleDeleteSelectedClick = useCallback(() => {
    if (selectedIds.size === 0) return;

    setDeleteConfirmation({
      isOpen: true,
      type: 'selected',
      count: selectedIds.size,
    });
  }, [selectedIds.size]);

  const handleEmptyTrashClick = useCallback(() => {
    setDeleteConfirmation({
      isOpen: true,
      type: 'all',
      count: deletedEvents.length,
    });
  }, [deletedEvents.length]);

  const handleConfirmDelete = useCallback(async () => {
    setIsBulkDeleting(true);
    setBulkError(null);

    try {
      let idsToDelete: number[];

      if (deleteConfirmation.type === 'all') {
        idsToDelete = deletedEvents.map((e) => e.id);
      } else if (deleteConfirmation.type === 'selected') {
        idsToDelete = Array.from(selectedIds);
      } else {
        idsToDelete = deleteConfirmation.eventId ? [deleteConfirmation.eventId] : [];
      }

      const promises = idsToDelete.map((id) => permanentDeleteMutation.mutateAsync(id));
      await Promise.all(promises);

      setSelectedIds(new Set());
      setDeleteConfirmation({ isOpen: false, type: 'single', count: 0 });
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : 'Failed to delete some events');
    } finally {
      setIsBulkDeleting(false);
    }
  }, [deleteConfirmation, deletedEvents, selectedIds, permanentDeleteMutation]);

  const handleCancelDelete = useCallback(() => {
    setDeleteConfirmation({ isOpen: false, type: 'single', count: 0 });
  }, []);

  // ============================================================================
  // Render states
  // ============================================================================

  // Loading state
  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium">Failed to load deleted events</span>
          </div>
          <p className="mt-2 text-sm text-red-300">{error.message}</p>
          <button
            onClick={() => void refetch()}
            className="mt-3 rounded bg-red-500/20 px-3 py-1 text-sm text-red-300 hover:bg-red-500/30"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (isEmpty) {
    return (
      <div className="p-6">
        <EmptyState
          icon={Trash2}
          title="Trash is empty"
          description="Deleted events will appear here. You can restore them within 30 days before they are permanently removed."
          variant="muted"
        />
      </div>
    );
  }

  const allSelected = selectedIds.size === deletedEvents.length && deletedEvents.length > 0;

  return (
    <div className="p-6">
      {/* Delete Confirmation Modal */}
      <DeleteConfirmationModal
        isOpen={deleteConfirmation.isOpen}
        type={deleteConfirmation.type}
        count={deleteConfirmation.count}
        onConfirm={() => void handleConfirmDelete()}
        onCancel={handleCancelDelete}
        isLoading={isBulkDeleting}
      />

      {/* Page Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Trash</h1>
          <p className="mt-1 text-text-secondary">
            Review and manage deleted events. Restore or permanently delete them.
          </p>
        </div>
        <Button
          variant="danger"
          size="sm"
          leftIcon={<AlertTriangle className="h-4 w-4" />}
          onClick={handleEmptyTrashClick}
          disabled={isBulkRestoring || isBulkDeleting}
          data-testid="empty-trash-button"
        >
          Empty Trash
        </Button>
      </div>

      {/* Auto-deletion Notice */}
      <div className="mb-6 flex items-start gap-3 rounded-lg border border-blue-500/20 bg-blue-500/10 p-4">
        <Info className="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-400" />
        <div>
          <p className="font-medium text-blue-300">Automatic cleanup</p>
          <p className="mt-1 text-sm text-blue-200/80">
            Events in trash are automatically deleted after 30 days. Restore important events before
            they are permanently removed.
          </p>
        </div>
      </div>

      {/* Mutation Errors */}
      {(restoreMutation.error || permanentDeleteMutation.error || bulkError) && (
        <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium">Action failed</span>
          </div>
          <p className="mt-2 text-sm text-red-300">
            {bulkError || restoreMutation.error?.message || permanentDeleteMutation.error?.message}
          </p>
        </div>
      )}

      {/* Bulk Action Bar */}
      <BulkActionBar
        selectedCount={selectedIds.size}
        onRestoreSelected={() => void handleRestoreSelected()}
        onDeleteSelected={handleDeleteSelectedClick}
        onClearSelection={handleClearSelection}
        isRestoring={isBulkRestoring}
        isDeleting={isBulkDeleting}
      />

      {/* Events Count and Select All */}
      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm text-text-secondary">
          {deletedEvents.length} {deletedEvents.length === 1 ? 'event' : 'events'} in trash
        </div>
        <button
          onClick={allSelected ? handleClearSelection : handleSelectAll}
          className="text-sm text-primary hover:text-primary/80"
          data-testid="select-all-button"
        >
          {allSelected ? 'Deselect All' : 'Select All'}
        </button>
      </div>

      {/* Events List */}
      <div className="space-y-4">
        {deletedEvents.map((event) => (
          <DeletedEventCard
            key={event.id}
            event={event}
            onRestore={handleRestore}
            onPermanentDelete={handlePermanentDelete}
            isRestoring={restoreMutation.isPending}
            isDeleting={permanentDeleteMutation.isPending}
            showSelection={true}
            isSelected={selectedIds.has(event.id)}
            onSelectionChange={handleSelectionChange}
          />
        ))}
      </div>
    </div>
  );
}
