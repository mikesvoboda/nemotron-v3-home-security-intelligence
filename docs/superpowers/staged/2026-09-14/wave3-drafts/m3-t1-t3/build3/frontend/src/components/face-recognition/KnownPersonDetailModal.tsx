/**
 * KnownPersonDetailModal - Modal for viewing and managing a known person's details
 *
 * Displays comprehensive information about a known person including:
 * - Primary photo and basic details
 * - Face embeddings gallery with quality scores
 * - Recent appearances timeline
 * - Actions to edit, delete, or enroll new faces
 *
 * @module components/face-recognition/KnownPersonDetailModal
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 * @see NEM-4688 Phase 1 - Create Known Person Detail Modal
 */

import { Dialog, Transition } from '@headlessui/react';
import { Edit2, Loader2, Plus, Trash2, User, X, Clock, MapPin } from 'lucide-react';
import { Fragment, useCallback, useState } from 'react';

import {
  useKnownPersonQuery,
  usePersonEmbeddingsQuery,
  usePersonAppearancesQuery,
  useDeleteEmbedding,
  useUpdateKnownPerson,
} from '../../hooks/useFaceRecognitionApi';
import { useMembersQuery } from '../../hooks/useHouseholdApi';
import { useToast } from '../../hooks/useToast';

import type { HouseholdMember } from '../../hooks/useHouseholdApi';
import type { KnownPerson, FaceEmbedding } from '../../types/faceRecognition';

// ============================================================================
// Types
// ============================================================================

export interface KnownPersonDetailModalProps {
  /** ID of the person to display, or null if no person selected */
  personId: number | null;
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Callback when edit button is clicked */
  onEdit: (person: KnownPerson) => void;
  /** Callback when delete button is clicked */
  onDelete: (person: KnownPerson) => void;
  /** Callback when "Add from Event" button is clicked */
  onEnrollFace: (personId: number) => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format a date string to a human-readable format.
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Format a timestamp to show time.
 */
function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

/**
 * Format a timestamp to show relative date and time.
 */
function formatAppearanceTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  const time = formatTime(dateString);

  if (diffDays === 0) {
    return `Today ${time}`;
  } else if (diffDays === 1) {
    return `Yesterday ${time}`;
  } else {
    return `${formatDate(dateString)} ${time}`;
  }
}

/**
 * Get quality class based on score.
 */
function getQualityClass(score: number): string {
  if (score >= 0.8) return 'quality-high';
  if (score >= 0.7) return 'quality-medium';
  return 'quality-low';
}

/**
 * Get quality color classes based on score.
 */
function getQualityColorClasses(score: number): string {
  if (score >= 0.8) return 'bg-green-500/20 text-green-400 border-green-500/30';
  if (score >= 0.7) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
  return 'bg-red-500/20 text-red-400 border-red-500/30';
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Delete confirmation dialog for embeddings.
 */
function DeleteEmbeddingConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  isDeleting,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isDeleting: boolean;
}) {
  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-[60]" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50" />
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
              <Dialog.Panel className="w-full max-w-sm transform rounded-lg border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl transition-all">
                <Dialog.Title className="mb-4 text-lg font-semibold text-white">
                  Confirm Delete
                </Dialog.Title>
                <p className="mb-6 text-gray-300">
                  Are you sure you want to delete this face embedding? This action cannot be undone.
                </p>
                <div className="flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:text-white"
                    disabled={isDeleting}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={onConfirm}
                    disabled={isDeleting}
                    className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                  >
                    {isDeleting ? 'Deleting...' : 'Confirm'}
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}

/**
 * Face embedding card component.
 */
function EmbeddingCard({
  embedding,
  onDelete,
}: {
  embedding: FaceEmbedding;
  onDelete: () => void;
}) {
  const qualityClass = getQualityClass(embedding.quality_score);
  const qualityColorClasses = getQualityColorClasses(embedding.quality_score);

  return (
    <div
      data-testid={`embedding-card-${embedding.id}`}
      className={`relative overflow-hidden rounded-lg border bg-[#252525] ${qualityClass} ${qualityColorClasses.includes('green') ? 'border-green-500/30' : qualityColorClasses.includes('yellow') ? 'border-yellow-500/30' : 'border-red-500/30'}`}
    >
      <div className="flex aspect-square items-center justify-center bg-gray-800">
        {embedding.source_image_path ? (
          <img
            src={embedding.source_image_path}
            alt={`Face embedding ${embedding.id}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <User className="h-12 w-12 text-gray-600" />
        )}
      </div>
      <div className="p-2 text-center">
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${qualityColorClasses}`}>
          {embedding.quality_score.toFixed(2)}
        </span>
      </div>
      <button
        onClick={onDelete}
        className="absolute right-1 top-1 rounded bg-black/50 p-1 transition-colors hover:bg-red-600"
        aria-label="Delete embedding"
      >
        <X className="h-3 w-3 text-white" />
      </button>
    </div>
  );
}

/**
 * Face embeddings gallery component.
 */
function FaceEmbeddingsGallery({
  embeddings,
  isLoading,
  personId,
  onEnrollFace,
}: {
  embeddings: FaceEmbedding[] | undefined;
  isLoading: boolean;
  personId: number;
  onEnrollFace: () => void;
}) {
  const toast = useToast();
  const deleteEmbeddingMutation = useDeleteEmbedding();
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [embeddingToDelete, setEmbeddingToDelete] = useState<FaceEmbedding | null>(null);

  const handleDeleteClick = useCallback((embedding: FaceEmbedding) => {
    setEmbeddingToDelete(embedding);
    setDeleteConfirmOpen(true);
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!embeddingToDelete) return;

    try {
      await deleteEmbeddingMutation.mutateAsync({
        personId,
        embeddingId: embeddingToDelete.id,
      });
      toast.success('Face embedding deleted successfully');
      setDeleteConfirmOpen(false);
      setEmbeddingToDelete(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete embedding';
      toast.error(message);
    }
  }, [embeddingToDelete, personId, deleteEmbeddingMutation, toast]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteConfirmOpen(false);
    setEmbeddingToDelete(null);
  }, []);

  if (isLoading) {
    return (
      <div data-testid="embeddings-loading" className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-[#76B900]" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">
          Face Embeddings ({embeddings?.length ?? 0})
        </h3>
        <button
          onClick={onEnrollFace}
          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-[#76B900] transition-colors hover:text-[#8fd000]"
        >
          <Plus className="h-3 w-3" />
          Add from Event
        </button>
      </div>

      <div data-testid="face-embeddings-gallery">
        {!embeddings || embeddings.length === 0 ? (
          <div className="py-6 text-center text-sm text-gray-500">
            No face embeddings yet. Add one from a detection event.
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {embeddings.map((embedding) => (
              <EmbeddingCard
                key={embedding.id}
                embedding={embedding}
                onDelete={() => handleDeleteClick(embedding)}
              />
            ))}
          </div>
        )}
      </div>

      <DeleteEmbeddingConfirmDialog
        isOpen={deleteConfirmOpen}
        onClose={handleDeleteCancel}
        onConfirm={() => void handleDeleteConfirm()}
        isDeleting={deleteEmbeddingMutation.isPending}
      />
    </div>
  );
}

/**
 * Appearance timeline item component.
 */
function AppearanceItem({
  appearance,
  index,
}: {
  appearance: {
    timestamp: string;
    camera_name: string;
    confidence: number;
  };
  index: number;
}) {
  const confidencePercent = Math.round(appearance.confidence * 100);

  return (
    <div
      data-testid={`appearance-item-${index}`}
      className="flex items-center gap-3 border-b border-gray-700/50 py-2 last:border-0"
    >
      <div className="h-2 w-2 flex-shrink-0 rounded-full bg-[#76B900]" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm">
          <Clock className="h-3 w-3 text-gray-500" />
          <span className="text-gray-300">{formatAppearanceTime(appearance.timestamp)}</span>
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-gray-500">
          <MapPin className="h-3 w-3" />
          <span>{appearance.camera_name}</span>
        </div>
      </div>
      <div className="text-sm font-medium text-gray-400">{confidencePercent}%</div>
    </div>
  );
}

/**
 * Recent appearances timeline component.
 */
function AppearancesTimeline({
  appearances,
  isLoading,
}: {
  appearances:
    | Array<{
        timestamp: string;
        camera_name: string;
        confidence: number;
      }>
    | undefined;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div data-testid="appearances-loading" className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-[#76B900]" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-300">Recent Appearances</h3>

      <div data-testid="appearances-timeline">
        {!appearances || appearances.length === 0 ? (
          <div className="py-6 text-center text-sm text-gray-500">
            No recent appearances recorded.
          </div>
        ) : (
          <div className="space-y-1">
            {appearances.slice(0, 5).map((appearance, index) => (
              <AppearanceItem key={index} appearance={appearance} index={index} />
            ))}
          </div>
        )}
      </div>

      {appearances && appearances.length > 0 && (
        <button className="w-full py-2 text-center text-xs text-[#76B900] transition-colors hover:text-[#8fd000]">
          View Full Timeline
        </button>
      )}
    </div>
  );
}

/**
 * Household member linking selector component.
 */
function HouseholdMemberSelector({
  person,
  members,
  membersLoading,
  onLink,
  isLinking,
}: {
  person: KnownPerson;
  members: HouseholdMember[] | undefined;
  membersLoading: boolean;
  onLink: (householdMemberId: number | null) => void;
  isLinking: boolean;
}) {
  const currentMemberId = person.household_member_id;
  const linkedMember = members?.find((m) => m.id === currentMemberId);

  // Get members that are not already linked to another known person
  // (a member can only be linked to one known person at a time)
  const availableMembers = members?.filter(
    (m) => m.known_person_id === null || m.known_person_id === person.id
  );

  return (
    <div className="space-y-2" data-testid="household-member-selector">
      <label htmlFor="household-member-link" className="text-sm text-gray-500">
        Link to Household Member
      </label>
      <div className="flex items-center gap-2">
        <select
          id="household-member-link"
          value={currentMemberId ?? ''}
          onChange={(e) => {
            const value = e.target.value;
            onLink(value ? Number(value) : null);
          }}
          disabled={membersLoading || isLinking}
          className="flex-1 rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-sm text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900] disabled:opacity-50"
        >
          <option value="">Not linked</option>
          {availableMembers?.map((member) => (
            <option key={member.id} value={member.id}>
              {member.name}
            </option>
          ))}
        </select>
        {isLinking && <Loader2 className="h-4 w-4 animate-spin text-[#76B900]" />}
      </div>
      {linkedMember && (
        <p className="text-xs text-gray-500">
          Linked to: <span className="text-[#76B900]">{linkedMember.name}</span> (
          {linkedMember.role})
        </p>
      )}
    </div>
  );
}

/**
 * Primary photo display component.
 */
function PrimaryPhoto({ embeddings }: { embeddings: FaceEmbedding[] | undefined }) {
  // Get the highest quality embedding as the primary photo
  const primaryEmbedding = embeddings?.reduce<FaceEmbedding | null>((best, current) => {
    if (!best || current.quality_score > best.quality_score) {
      return current;
    }
    return best;
  }, null);

  return (
    <div
      data-testid="primary-photo"
      className="h-24 w-24 flex-shrink-0 overflow-hidden rounded-lg border border-gray-700 bg-gray-800"
    >
      {primaryEmbedding?.source_image_path ? (
        <img
          src={primaryEmbedding.source_image_path}
          alt="Person face"
          className="h-full w-full object-cover"
        />
      ) : (
        <div
          data-testid="photo-placeholder"
          className="flex h-full w-full items-center justify-center"
        >
          <User className="h-12 w-12 text-gray-600" />
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * Modal for viewing and managing a known person's details.
 *
 * Displays:
 * - Person name and details (role, trust level, household link)
 * - Primary photo
 * - Face embeddings gallery with quality scores and delete functionality
 * - Recent appearances timeline
 *
 * @example
 * ```tsx
 * <KnownPersonDetailModal
 *   personId={selectedPersonId}
 *   isOpen={isModalOpen}
 *   onClose={() => setIsModalOpen(false)}
 *   onEdit={(person) => openEditModal(person)}
 *   onDelete={(person) => confirmDelete(person)}
 *   onEnrollFace={(personId) => openEnrollModal(personId)}
 * />
 * ```
 */
export default function KnownPersonDetailModal({
  personId,
  isOpen,
  onClose,
  onEdit,
  onDelete,
  onEnrollFace,
}: KnownPersonDetailModalProps) {
  // Don't render if no person selected
  const shouldRender = isOpen && personId !== null;

  const toast = useToast();

  // Fetch person data
  const {
    data: person,
    isLoading: personLoading,
    error: personError,
  } = useKnownPersonQuery(personId);

  // Fetch embeddings
  const { data: embeddings, isLoading: embeddingsLoading } = usePersonEmbeddingsQuery(personId);

  // Fetch appearances (limit to 5 for the modal)
  const { data: appearancesResponse, isLoading: appearancesLoading } = usePersonAppearancesQuery(
    personId,
    { limit: 5 }
  );

  // Fetch household members for linking
  const { data: members, isLoading: membersLoading } = useMembersQuery();

  // Update known person mutation for linking
  const updateKnownPersonMutation = useUpdateKnownPerson();

  const handleEdit = useCallback(() => {
    if (person) {
      onEdit(person);
    }
  }, [person, onEdit]);

  const handleDelete = useCallback(() => {
    if (person) {
      onDelete(person);
    }
  }, [person, onDelete]);

  const handleEnrollFace = useCallback(() => {
    if (personId !== null) {
      onEnrollFace(personId);
    }
  }, [personId, onEnrollFace]);

  const handleLinkToHouseholdMember = useCallback(
    async (householdMemberId: number | null) => {
      if (!person) return;

      try {
        await updateKnownPersonMutation.mutateAsync({
          id: person.id,
          data: {
            household_member_id: householdMemberId,
            is_household_member: householdMemberId !== null,
          },
        });
        const action = householdMemberId ? 'linked to' : 'unlinked from';
        toast.success(`Known person ${action} household member successfully`);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to update link';
        toast.error(message);
      }
    },
    [person, updateKnownPersonMutation, toast]
  );

  if (!shouldRender) {
    return null;
  }

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
          <div className="fixed inset-0 bg-black/50" />
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
              <Dialog.Panel className="w-full max-w-lg transform rounded-lg border border-gray-700 bg-[#1A1A1A] shadow-xl transition-all">
                {/* Loading State */}
                {personLoading && (
                  <div
                    data-testid="person-detail-loading"
                    className="flex items-center justify-center py-16"
                  >
                    <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
                  </div>
                )}

                {/* Error State */}
                {personError && (
                  <div className="p-6">
                    <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4">
                      <p className="text-sm text-red-400">{personError.message}</p>
                    </div>
                    <div className="mt-4 flex justify-end">
                      <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:text-white"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                )}

                {/* Content */}
                {person && !personLoading && !personError && (
                  <>
                    {/* Header */}
                    <div className="flex items-center justify-between border-b border-gray-700 p-4">
                      <Dialog.Title as="h2" className="text-lg font-semibold text-white">
                        {person.name}
                      </Dialog.Title>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={handleEdit}
                          className="rounded p-2 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
                          aria-label="Edit"
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={handleDelete}
                          className="rounded p-2 text-gray-400 transition-colors hover:bg-gray-700 hover:text-red-400"
                          aria-label="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={onClose}
                          className="rounded p-2 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
                          aria-label="Close"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </div>

                    {/* Body */}
                    <div className="space-y-6 p-4">
                      {/* Person Details */}
                      <div className="flex gap-4">
                        <PrimaryPhoto embeddings={embeddings} />
                        <div className="flex-1 space-y-2">
                          <div className="text-sm">
                            <span className="text-gray-500">Name: </span>
                            <span className="text-white">{person.name}</span>
                          </div>
                          <div className="text-sm">
                            <span className="text-gray-500">Linked Household: </span>
                            <span className="text-white">
                              {person.is_household_member
                                ? (members?.find((m) => m.id === person.household_member_id)
                                    ?.name ?? 'Yes')
                                : 'No'}
                            </span>
                          </div>
                          {person.is_household_member && (
                            <div className="text-sm">
                              <span className="text-gray-500">Trust Level: </span>
                              <span className="text-white">
                                {members?.find((m) => m.id === person.household_member_id)
                                  ?.trusted_level === 'full'
                                  ? 'Full'
                                  : members?.find((m) => m.id === person.household_member_id)
                                        ?.trusted_level === 'partial'
                                    ? 'Partial'
                                    : 'Monitor'}
                              </span>
                            </div>
                          )}
                          <div className="text-sm">
                            <span className="text-gray-500">Created: </span>
                            <span className="text-white">{formatDate(person.created_at)}</span>
                          </div>
                          {person.notes && (
                            <div className="text-sm">
                              <span className="text-gray-500">Notes: </span>
                              <span className="text-gray-300">{person.notes}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Household Member Linking */}
                      <HouseholdMemberSelector
                        person={person}
                        members={members}
                        membersLoading={membersLoading}
                        onLink={(id) => void handleLinkToHouseholdMember(id)}
                        isLinking={updateKnownPersonMutation.isPending}
                      />

                      {/* Face Embeddings Gallery */}
                      <FaceEmbeddingsGallery
                        embeddings={embeddings}
                        isLoading={embeddingsLoading}
                        personId={personId}
                        onEnrollFace={handleEnrollFace}
                      />

                      {/* Recent Appearances */}
                      <AppearancesTimeline
                        appearances={appearancesResponse?.appearances}
                        isLoading={appearancesLoading}
                      />
                    </div>
                  </>
                )}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
