/**
 * IdentifyPersonModal - Modal to identify an unknown face as a known person
 *
 * Features:
 * - Face preview image from the unknown event
 * - Event metadata display (camera name, timestamp)
 * - Searchable grid of known persons with radio selection
 * - Optional checkbox to enroll the face (quality >= 0.7)
 * - Toast notifications on success/error
 * - Loading states during API call
 *
 * @module components/face-recognition/IdentifyPersonModal
 * @see NEM-4688 Phase 2 - Face Recognition UI
 */

import { Dialog, Transition } from '@headlessui/react';
import { Loader2, Search, X } from 'lucide-react';
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';

import { useKnownPersonsQuery, useIdentifyFace } from '../../hooks/useFaceRecognitionApi';
import { useToast } from '../../hooks/useToast';

import type { KnownPerson, IdentifyFaceResponse } from '../../hooks/useFaceRecognitionApi';

// ============================================================================
// Types
// ============================================================================

export interface IdentifyPersonModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** ID of the face event to identify */
  eventId: number;
  /** URL to the face preview image */
  facePreviewUrl?: string;
  /** Quality score of the face (0-1) */
  qualityScore: number;
  /** Name of the camera that captured the face */
  cameraName: string;
  /** ISO timestamp when the face was detected */
  timestamp: string;
}

// ============================================================================
// Constants
// ============================================================================

/** Minimum quality score to allow face enrollment */
const MIN_ENROLLMENT_QUALITY = 0.7;

/** Quality threshold for auto-checking enrollment checkbox */
const AUTO_ENROLL_QUALITY = 0.8;

/** Placeholder image when no face preview URL is provided */
const PLACEHOLDER_FACE_IMAGE = '/placeholder-face.png';

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format ISO timestamp for display.
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return isoString;
  }
}

/**
 * Filter persons by search query.
 */
function filterPersonsBySearch(persons: KnownPerson[], searchQuery: string): KnownPerson[] {
  if (!searchQuery.trim()) {
    return persons;
  }
  const query = searchQuery.toLowerCase().trim();
  return persons.filter((person) => person.name.toLowerCase().includes(query));
}

// ============================================================================
// Component
// ============================================================================

export default function IdentifyPersonModal({
  isOpen,
  onClose,
  eventId,
  facePreviewUrl,
  qualityScore,
  cameraName,
  timestamp,
}: IdentifyPersonModalProps) {
  // Form state
  const [selectedPersonId, setSelectedPersonId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [enrollFace, setEnrollFace] = useState(qualityScore >= AUTO_ENROLL_QUALITY);

  // Data fetching
  const knownPersonsQuery = useKnownPersonsQuery();
  const identifyMutation = useIdentifyFace();
  const toast = useToast();

  // Filtered persons based on search
  const filteredPersons = useMemo(() => {
    const persons = knownPersonsQuery.data ?? [];
    return filterPersonsBySearch(persons, searchQuery);
  }, [knownPersonsQuery.data, searchQuery]);

  // Find selected person
  const selectedPerson = useMemo(
    () => knownPersonsQuery.data?.find((p) => p.id === selectedPersonId) ?? null,
    [knownPersonsQuery.data, selectedPersonId]
  );

  // Whether enrollment option should be shown
  const showEnrollmentOption = qualityScore >= MIN_ENROLLMENT_QUALITY;

  // Validation
  const canSubmit = selectedPersonId !== null && !identifyMutation.isPending;

  // Reset form when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedPersonId(null);
      setSearchQuery('');
      setEnrollFace(qualityScore >= AUTO_ENROLL_QUALITY);
    }
  }, [isOpen, qualityScore]);

  // Handle form submission
  const handleSubmit = useCallback(() => {
    if (!selectedPersonId) return;

    identifyMutation.mutate(
      {
        eventId,
        knownPersonId: selectedPersonId,
        createEmbedding: showEnrollmentOption && enrollFace,
      },
      {
        onSuccess: (data: IdentifyFaceResponse) => {
          const personName = selectedPerson?.name ?? 'Unknown';
          if (data.created_embedding) {
            toast.success(`Face identified as ${personName} and enrolled`, {
              description: 'A new face embedding has been added.',
            });
          } else {
            toast.success(`Face identified as ${personName}`, {
              description: 'The face event has been linked.',
            });
          }
          onClose();
        },
        onError: (error: Error) => {
          toast.error(error.message || 'Failed to identify face', {
            description: 'Please try again.',
          });
        },
      }
    );
  }, [
    eventId,
    selectedPersonId,
    selectedPerson,
    showEnrollmentOption,
    enrollFace,
    identifyMutation,
    toast,
    onClose,
  ]);

  // Handle cancel
  const handleCancel = useCallback(() => {
    onClose();
  }, [onClose]);

  // Handle search clear
  const handleClearSearch = useCallback(() => {
    setSearchQuery('');
  }, []);

  // Handle person selection
  const handlePersonSelect = useCallback((personId: number) => {
    setSelectedPersonId(personId);
  }, []);

  const previewUrl = facePreviewUrl || PLACEHOLDER_FACE_IMAGE;

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog
        as="div"
        className="relative z-50"
        onClose={onClose}
        aria-labelledby="identify-person-modal-title"
      >
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
              <Dialog.Panel className="w-full max-w-lg transform rounded-lg bg-[#1A1A1A] border border-gray-700 p-6 shadow-xl transition-all">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                  <Dialog.Title
                    id="identify-person-modal-title"
                    className="text-lg font-semibold text-white"
                  >
                    Identify Person
                  </Dialog.Title>
                  <button
                    type="button"
                    onClick={handleCancel}
                    disabled={identifyMutation.isPending}
                    aria-label="Close"
                    className="p-1 text-gray-400 hover:text-white transition-colors disabled:opacity-50"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Face Preview and Event Info */}
                <div className="mb-6 flex items-start gap-4">
                  <img
                    src={previewUrl}
                    alt="Face preview"
                    className="w-24 h-24 object-cover rounded-lg border border-gray-700"
                  />
                  <div className="text-sm text-gray-300 space-y-1">
                    <div>Unknown face detected at:</div>
                    <div>
                      Camera: <span className="text-white">{cameraName}</span>
                    </div>
                    <div>
                      Time: <span className="text-white">{formatTimestamp(timestamp)}</span>
                    </div>
                  </div>
                </div>

                {/* Person Selection Section */}
                <div className="mb-4">
                  <span
                    id="person-selection-label"
                    className="block text-sm font-medium text-gray-300 mb-2"
                  >
                    Select matching person:
                  </span>

                  {/* Search Input */}
                  <div className="relative mb-3">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search persons..."
                      disabled={identifyMutation.isPending}
                      aria-label="Search persons"
                      className="w-full pl-10 pr-10 py-2 bg-[#121212] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:border-transparent disabled:opacity-50"
                    />
                    {searchQuery && (
                      <button
                        type="button"
                        onClick={handleClearSearch}
                        disabled={identifyMutation.isPending}
                        aria-label="Clear search"
                        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-white transition-colors disabled:opacity-50"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>

                  {/* Loading state */}
                  {knownPersonsQuery.isLoading && (
                    <div className="text-gray-400 text-sm py-4 text-center">Loading persons...</div>
                  )}

                  {/* Error state */}
                  {knownPersonsQuery.isError && (
                    <div className="text-red-400 text-sm py-4 text-center">
                      {knownPersonsQuery.error instanceof Error
                        ? knownPersonsQuery.error.message
                        : 'Failed to load known persons'}
                    </div>
                  )}

                  {/* Empty state - no known persons exist */}
                  {!knownPersonsQuery.isLoading &&
                    !knownPersonsQuery.isError &&
                    (knownPersonsQuery.data?.length ?? 0) === 0 && (
                      <div className="text-gray-400 text-sm py-4 text-center">
                        No known persons. Add a person first before identifying faces.
                      </div>
                    )}

                  {/* Empty state - no search results */}
                  {!knownPersonsQuery.isLoading &&
                    !knownPersonsQuery.isError &&
                    (knownPersonsQuery.data?.length ?? 0) > 0 &&
                    filteredPersons.length === 0 && (
                      <div className="text-gray-400 text-sm py-4 text-center">
                        No persons found matching &quot;{searchQuery}&quot;
                      </div>
                    )}

                  {/* Person Grid */}
                  {!knownPersonsQuery.isLoading &&
                    !knownPersonsQuery.isError &&
                    filteredPersons.length > 0 && (
                      <div
                        role="radiogroup"
                        aria-labelledby="person-selection-label"
                        aria-label="Select matching person"
                        className="grid grid-cols-4 gap-3 max-h-48 overflow-y-auto p-1"
                      >
                        {filteredPersons.map((person) => (
                          <PersonCard
                            key={person.id}
                            person={person}
                            isSelected={selectedPersonId === person.id}
                            onSelect={handlePersonSelect}
                            disabled={identifyMutation.isPending}
                          />
                        ))}
                      </div>
                    )}
                </div>

                {/* Enrollment Checkbox */}
                {showEnrollmentOption && (
                  <div className="mb-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={enrollFace}
                        onChange={(e) => setEnrollFace(e.target.checked)}
                        disabled={identifyMutation.isPending}
                        aria-label="Also enroll this face"
                        className="w-4 h-4 rounded border-gray-600 bg-[#121212] text-[#76B900] focus:ring-[#76B900] focus:ring-offset-0 disabled:opacity-50"
                      />
                      <span className="text-sm text-gray-300">
                        Also enroll this face (quality: {qualityScore.toFixed(2)})
                      </span>
                    </label>
                  </div>
                )}

                {/* Actions */}
                <div className="flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={handleCancel}
                    disabled={identifyMutation.isPending}
                    className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={!canSubmit}
                    className="px-4 py-2 text-sm font-medium bg-[#76B900] hover:bg-[#5a8f00] text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    {identifyMutation.isPending && (
                      <Loader2 className="h-4 w-4 animate-spin" data-testid="loading-spinner" />
                    )}
                    {identifyMutation.isPending ? 'Identifying...' : 'Identify'}
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

// ============================================================================
// Sub-Components
// ============================================================================

interface PersonCardProps {
  person: KnownPerson;
  isSelected: boolean;
  onSelect: (id: number) => void;
  disabled: boolean;
}

/**
 * Person card with radio button selection.
 */
function PersonCard({ person, isSelected, onSelect, disabled }: PersonCardProps) {
  const handleClick = useCallback(() => {
    if (!disabled) {
      onSelect(person.id);
    }
  }, [person.id, onSelect, disabled]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
        e.preventDefault();
        onSelect(person.id);
      }
    },
    [person.id, onSelect, disabled]
  );

  return (
    <div
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="radio"
      aria-checked={isSelected}
      aria-label={person.name}
      tabIndex={disabled ? -1 : 0}
      className={`
        flex flex-col items-center p-2 rounded-lg border cursor-pointer transition-colors
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${
          isSelected
            ? 'border-[#76B900] bg-[#76B900]/10'
            : 'border-gray-700 hover:border-gray-600 bg-[#121212]'
        }
      `}
    >
      {/* Person Avatar/Initial */}
      <div className="w-12 h-12 rounded-full bg-gray-700 flex items-center justify-center text-lg font-medium text-white mb-1">
        {person.name.charAt(0).toUpperCase()}
      </div>

      {/* Person Name */}
      <span className="text-xs text-center text-white truncate w-full">{person.name}</span>

      {/* Selection Indicator */}
      <div
        className={`
          w-4 h-4 rounded-full border-2 mt-1 flex items-center justify-center
          ${isSelected ? 'border-[#76B900] bg-[#76B900]' : 'border-gray-500'}
        `}
      >
        {isSelected && <div className="w-2 h-2 rounded-full bg-white" />}
      </div>
    </div>
  );
}
