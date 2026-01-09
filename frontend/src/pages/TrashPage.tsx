/**
 * TrashPage - Page component for viewing and managing soft-deleted events
 *
 * Features:
 * - Lists all soft-deleted events
 * - Restore events back to active state
 * - Permanently delete events
 * - Shows empty state when trash is empty
 * - 30-day auto-deletion notice
 *
 * @module pages/TrashPage
 */

import { AlertCircle, Info, Trash2 } from 'lucide-react';

import DeletedEventCard from '../components/events/DeletedEventCard';
import EmptyState from '../components/common/EmptyState';
import LoadingSpinner from '../components/common/LoadingSpinner';
import {
  useDeletedEventsQuery,
  useRestoreEventMutation,
  usePermanentDeleteMutation,
} from '../hooks/useTrashQuery';

/**
 * TrashPage displays soft-deleted events with options to restore or permanently delete them.
 */
export default function TrashPage() {
  const { deletedEvents, isLoading, error, isEmpty, refetch } = useDeletedEventsQuery();
  const restoreMutation = useRestoreEventMutation();
  const permanentDeleteMutation = usePermanentDeleteMutation();

  const handleRestore = async (eventId: number) => {
    try {
      await restoreMutation.mutateAsync(eventId);
    } catch {
      // Error is already tracked in mutation state
    }
  };

  const handlePermanentDelete = async (eventId: number) => {
    try {
      await permanentDeleteMutation.mutateAsync(eventId);
    } catch {
      // Error is already tracked in mutation state
    }
  };

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
            onClick={() => refetch()}
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

  return (
    <div className="p-6">
      {/* Page Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Trash</h1>
        <p className="mt-1 text-text-secondary">
          Review and manage deleted events. Restore or permanently delete them.
        </p>
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
      {(restoreMutation.error || permanentDeleteMutation.error) && (
        <div className="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-5 w-5" />
            <span className="font-medium">Action failed</span>
          </div>
          <p className="mt-2 text-sm text-red-300">
            {restoreMutation.error?.message || permanentDeleteMutation.error?.message}
          </p>
        </div>
      )}

      {/* Events Count */}
      <div className="mb-4 text-sm text-text-secondary">
        {deletedEvents.length} {deletedEvents.length === 1 ? 'event' : 'events'} in trash
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
          />
        ))}
      </div>
    </div>
  );
}
