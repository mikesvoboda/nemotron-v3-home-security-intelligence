/**
 * EnrollFaceModal - Modal for enrolling a face from a detection event
 *
 * Features:
 * - Display face preview/thumbnail from detection
 * - Show quality score with visual indicator
 * - Quality warnings: block < 0.7, warn 0.7-0.8, green >= 0.8
 * - Two modes: add to existing person OR create new person
 * - Person selector dropdown (searchable)
 * - New person form with name and household checkbox
 * - Max 10 embeddings per person enforcement
 * - Toast notification on success/error
 *
 * @module components/face-recognition/EnrollFaceModal
 * @see NEM-4688 Phase 2 - Face Enrollment Modal
 */

import { Dialog, Listbox, Transition } from '@headlessui/react';
import { Check, ChevronDown, Home, Loader2, X } from 'lucide-react';
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';

import {
  useKnownPersonsQuery,
  useEnrollFace,
  useCreateKnownPerson,
} from '../../hooks/useFaceRecognitionApi';
import { useToast } from '../../hooks/useToast';

import type { KnownPerson } from '../../types/faceRecognition';

// ============================================================================
// Types
// ============================================================================

export interface EnrollFaceModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** ID of the detection to enroll from */
  detectionId: string;
  /** URL to the face preview image */
  facePreviewUrl?: string;
  /** Quality score of the detected face (0-1) */
  qualityScore: number;
  /** Name of the camera that captured the detection */
  cameraName: string;
  /** ISO timestamp of the detection */
  timestamp?: string;
}

type EnrollMode = 'existing' | 'new';

/** Maximum embeddings allowed per person */
const MAX_EMBEDDINGS = 10;

/** Quality threshold for blocking enrollment */
const QUALITY_BLOCK_THRESHOLD = 0.7;

/** Quality threshold for warning */
const QUALITY_WARN_THRESHOLD = 0.8;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format timestamp for display.
 */
function formatTimestamp(timestamp: string | undefined): string {
  if (!timestamp) return 'Unknown time';
  try {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return 'Unknown time';
  }
}

/**
 * Get quality indicator color class.
 */
function getQualityColorClass(score: number): string {
  if (score >= QUALITY_WARN_THRESHOLD) return 'bg-green-500';
  if (score >= QUALITY_BLOCK_THRESHOLD) return 'bg-yellow-500';
  return 'bg-red-500';
}

/**
 * Get quality label text.
 */
function getQualityLabel(score: number): string {
  if (score >= QUALITY_WARN_THRESHOLD) return 'Good';
  if (score >= QUALITY_BLOCK_THRESHOLD) return 'Fair';
  return 'Poor';
}

/**
 * Check if enrollment is blocked due to quality.
 */
function isQualityBlocked(score: number): boolean {
  return score < QUALITY_BLOCK_THRESHOLD;
}

/**
 * Check if quality warning should be shown.
 */
function shouldShowQualityWarning(score: number): boolean {
  return score >= QUALITY_BLOCK_THRESHOLD && score < QUALITY_WARN_THRESHOLD;
}

// ============================================================================
// Component
// ============================================================================

export default function EnrollFaceModal({
  isOpen,
  onClose,
  detectionId,
  facePreviewUrl,
  qualityScore,
  cameraName,
  timestamp,
}: EnrollFaceModalProps) {
  // Form state
  const [mode, setMode] = useState<EnrollMode>('existing');
  const [selectedPersonId, setSelectedPersonId] = useState<number | null>(null);
  const [newPersonName, setNewPersonName] = useState('');
  const [isHouseholdMember, setIsHouseholdMember] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Data fetching
  const personsQuery = useKnownPersonsQuery();
  const enrollMutation = useEnrollFace();
  const createPersonMutation = useCreateKnownPerson();

  // Toast notifications
  const toast = useToast();

  // Determine if any mutation is pending
  const isPending = enrollMutation.isPending || createPersonMutation.isPending;

  // Filter persons by search query
  const filteredPersons = useMemo(() => {
    const persons = personsQuery.data ?? [];
    if (!searchQuery.trim()) return persons;
    const query = searchQuery.toLowerCase();
    return persons.filter((person) => person.name.toLowerCase().includes(query));
  }, [personsQuery.data, searchQuery]);

  // Find selected person
  const selectedPerson = useMemo(() => {
    if (!personsQuery.data || selectedPersonId === null) return null;
    return personsQuery.data.find((p) => p.id === selectedPersonId) ?? null;
  }, [personsQuery.data, selectedPersonId]);

  // Validation
  const qualityBlocked = isQualityBlocked(qualityScore);
  const showQualityWarning = shouldShowQualityWarning(qualityScore);
  const selectedAtMax = selectedPerson && selectedPerson.embedding_count >= MAX_EMBEDDINGS;

  const canEnroll = useMemo(() => {
    if (qualityBlocked) return false;
    if (isPending) return false;

    if (mode === 'existing') {
      return selectedPersonId !== null && !selectedAtMax;
    } else {
      return newPersonName.trim().length > 0;
    }
  }, [qualityBlocked, isPending, mode, selectedPersonId, selectedAtMax, newPersonName]);

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setMode('existing');
      setSelectedPersonId(null);
      setNewPersonName('');
      setIsHouseholdMember(false);
      setSearchQuery('');
    }
  }, [isOpen]);

  // Handle enrollment
  const handleEnroll = useCallback(async () => {
    if (!canEnroll) return;

    try {
      let personId = selectedPersonId;

      // If creating new person, do that first
      if (mode === 'new') {
        const newPerson = await createPersonMutation.mutateAsync({
          name: newPersonName.trim(),
          is_household_member: isHouseholdMember,
        });
        personId = newPerson.id;
      }

      if (personId === null) return;

      // Enroll the face
      await enrollMutation.mutateAsync({
        personId,
        detectionId,
      });

      const personName = mode === 'new' ? newPersonName.trim() : selectedPerson?.name ?? 'person';
      toast.success(`Face enrolled for ${personName}`, {
        description: 'The face has been added to the person\'s recognition profile.',
      });

      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'An error occurred';
      toast.error(`Enrollment failed: ${message}`, {
        description: 'Please try again or contact support if the issue persists.',
      });
    }
  }, [
    canEnroll,
    mode,
    selectedPersonId,
    selectedPerson,
    newPersonName,
    isHouseholdMember,
    detectionId,
    createPersonMutation,
    enrollMutation,
    toast,
    onClose,
  ]);

  // Handle person selection
  const handlePersonSelect = useCallback((person: KnownPerson | null) => {
    setSelectedPersonId(person?.id ?? null);
    setSearchQuery('');
  }, []);

  // Calculate progress bar width
  const progressWidth = Math.min(100, Math.max(0, qualityScore * 100));

  const imageUrl = facePreviewUrl || '/placeholder-face.png';

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
              <Dialog.Panel className="w-full max-w-lg transform rounded-lg bg-[#1A1A1A] border border-gray-700 p-6 shadow-xl transition-all">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                  <Dialog.Title className="text-lg font-semibold text-white">
                    Enroll Face
                  </Dialog.Title>
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="p-1 text-gray-400 hover:text-white transition-colors disabled:opacity-50"
                    aria-label="Close modal"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Face Preview and Info */}
                <div className="flex gap-6 mb-6">
                  {/* Face Preview */}
                  <div className="flex-shrink-0">
                    <img
                      src={imageUrl}
                      alt="Face preview"
                      className="w-24 h-24 object-cover rounded-lg border border-gray-700"
                    />
                  </div>

                  {/* Quality and Detection Info */}
                  <div className="flex-1 space-y-3">
                    {/* Quality Score */}
                    <div>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-gray-400">Quality Score:</span>
                        <span className="text-white font-medium">{qualityScore.toFixed(2)}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                          <div
                            data-testid="quality-progress-bar"
                            className={`h-full transition-all ${getQualityColorClass(qualityScore)}`}
                            style={{ width: `${progressWidth}%` }}
                          />
                        </div>
                        <div
                          data-testid="quality-indicator"
                          className={`w-3 h-3 rounded-full ${getQualityColorClass(qualityScore)}`}
                          aria-label={`Quality: ${getQualityLabel(qualityScore)}`}
                        />
                        <span className="text-sm text-gray-300">{getQualityLabel(qualityScore)}</span>
                      </div>
                    </div>

                    {/* Camera */}
                    <div className="flex items-center text-sm">
                      <span className="text-gray-400 w-16">Camera:</span>
                      <span className="text-white">{cameraName}</span>
                    </div>

                    {/* Time */}
                    <div className="flex items-center text-sm">
                      <span className="text-gray-400 w-16">Time:</span>
                      <span className="text-white">{formatTimestamp(timestamp)}</span>
                    </div>
                  </div>
                </div>

                {/* Quality Warnings */}
                {qualityBlocked && (
                  <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                    <p className="text-sm text-red-400">
                      Quality too low (below 0.7). Face cannot be enrolled.
                    </p>
                  </div>
                )}

                {showQualityWarning && (
                  <div className="mb-6 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
                    <p className="text-sm text-yellow-400">
                      Quality is below 0.8 - recognition may be less accurate.
                    </p>
                  </div>
                )}

                {/* Mode Selection */}
                <fieldset className="mb-6" disabled={isPending}>
                  <legend className="sr-only">Enrollment mode</legend>
                  <div className="space-y-3">
                    {/* Existing Person */}
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="radio"
                        name="enroll-mode"
                        value="existing"
                        checked={mode === 'existing'}
                        onChange={() => setMode('existing')}
                        disabled={isPending}
                        className="w-4 h-4 text-[#76B900] bg-[#121212] border-gray-600 focus:ring-[#76B900] focus:ring-offset-[#1A1A1A]"
                        aria-label="Add to existing person"
                      />
                      <span className="text-white">Add to existing person</span>
                    </label>

                    {/* Create New Person */}
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="radio"
                        name="enroll-mode"
                        value="new"
                        checked={mode === 'new'}
                        onChange={() => setMode('new')}
                        disabled={isPending}
                        className="w-4 h-4 text-[#76B900] bg-[#121212] border-gray-600 focus:ring-[#76B900] focus:ring-offset-[#1A1A1A]"
                        aria-label="Create new person"
                      />
                      <span className="text-white">Create new person</span>
                    </label>
                  </div>
                </fieldset>

                {/* Existing Person Selector */}
                {mode === 'existing' && (
                  <div className="mb-6">
                    {personsQuery.isLoading && (
                      <div className="text-gray-400 text-sm">Loading persons...</div>
                    )}

                    {personsQuery.isError && (
                      <div className="text-red-400 text-sm">
                        {personsQuery.error instanceof Error
                          ? personsQuery.error.message
                          : 'Failed to load persons'}
                      </div>
                    )}

                    {!personsQuery.isLoading && !personsQuery.isError && (
                      <>
                        {(personsQuery.data?.length ?? 0) === 0 ? (
                          <div className="text-gray-400 text-sm">
                            No known persons available. Create a new person instead.
                          </div>
                        ) : (
                          <Listbox
                            value={selectedPerson}
                            onChange={handlePersonSelect}
                            disabled={isPending}
                          >
                            <Listbox.Label className="block text-sm font-medium text-gray-300 mb-1">
                              Select Person
                            </Listbox.Label>
                            <div className="relative">
                              <Listbox.Button
                                aria-label="Select Person"
                                className="w-full px-3 py-2 bg-[#121212] border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:border-transparent disabled:opacity-50 text-left flex items-center justify-between"
                              >
                                <span className={selectedPerson ? 'text-white' : 'text-gray-500'}>
                                  {selectedPerson?.name ?? '-- Select a person --'}
                                </span>
                                <ChevronDown className="h-4 w-4 text-gray-400" />
                              </Listbox.Button>

                              <Transition
                                as={Fragment}
                                leave="transition ease-in duration-100"
                                leaveFrom="opacity-100"
                                leaveTo="opacity-0"
                              >
                                <Listbox.Options className="absolute z-10 mt-1 w-full bg-[#1A1A1A] border border-gray-700 rounded-lg shadow-lg max-h-60 overflow-auto focus:outline-none">
                                  {/* Search Input */}
                                  <div className="p-2 border-b border-gray-700">
                                    <input
                                      type="text"
                                      value={searchQuery}
                                      onChange={(e) => setSearchQuery(e.target.value)}
                                      placeholder="Search persons..."
                                      className="w-full px-2 py-1 text-sm bg-[#121212] border border-gray-600 rounded text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-[#76B900]"
                                      onClick={(e) => e.stopPropagation()}
                                    />
                                  </div>

                                  {filteredPersons.length === 0 ? (
                                    <div className="py-2 px-3 text-sm text-gray-500">
                                      No matching persons found
                                    </div>
                                  ) : (
                                    filteredPersons.map((person) => {
                                      const atMax = person.embedding_count >= MAX_EMBEDDINGS;
                                      return (
                                        <Listbox.Option
                                          key={person.id}
                                          value={person}
                                          disabled={atMax}
                                          className={({ active, disabled }) =>
                                            `cursor-pointer select-none relative py-2 pl-10 pr-4 truncate ${
                                              disabled
                                                ? 'opacity-50 cursor-not-allowed text-gray-500'
                                                : active
                                                  ? 'bg-[#76B900]/20 text-white'
                                                  : 'text-gray-300'
                                            }`
                                          }
                                        >
                                          {({ selected }) => (
                                            <>
                                              <div className="flex items-center justify-between">
                                                <span
                                                  className={`block truncate ${
                                                    selected ? 'font-medium' : 'font-normal'
                                                  }`}
                                                >
                                                  {person.name}
                                                </span>
                                                <div className="flex items-center gap-2 ml-2">
                                                  {person.is_household_member && (
                                                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-[#76B900]/20 text-[#76B900]">
                                                      <Home className="h-3 w-3" />
                                                      Household
                                                    </span>
                                                  )}
                                                  <span className={`text-xs ${atMax ? 'text-red-400' : 'text-gray-500'}`}>
                                                    {atMax ? 'Max reached' : `${person.embedding_count} ${person.embedding_count === 1 ? 'face' : 'faces'}`}
                                                  </span>
                                                </div>
                                              </div>
                                              {selected && (
                                                <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-[#76B900]">
                                                  <Check className="h-4 w-4" />
                                                </span>
                                              )}
                                            </>
                                          )}
                                        </Listbox.Option>
                                      );
                                    })
                                  )}
                                </Listbox.Options>
                              </Transition>
                            </div>
                          </Listbox>
                        )}
                      </>
                    )}

                    {selectedAtMax && (
                      <p className="mt-2 text-xs text-red-400">
                        This person has reached the maximum of {MAX_EMBEDDINGS} face embeddings.
                      </p>
                    )}
                  </div>
                )}

                {/* New Person Form */}
                {mode === 'new' && (
                  <div className="mb-6 space-y-4">
                    {/* Name Input */}
                    <div>
                      <label
                        htmlFor="person-name"
                        className="block text-sm font-medium text-gray-300 mb-1"
                      >
                        Name
                      </label>
                      <input
                        type="text"
                        id="person-name"
                        value={newPersonName}
                        onChange={(e) => setNewPersonName(e.target.value)}
                        disabled={isPending}
                        placeholder="Enter person's name"
                        className="w-full px-3 py-2 bg-[#121212] border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:border-transparent disabled:opacity-50"
                      />
                    </div>

                    {/* Household Checkbox */}
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isHouseholdMember}
                        onChange={(e) => setIsHouseholdMember(e.target.checked)}
                        disabled={isPending}
                        className="w-4 h-4 text-[#76B900] bg-[#121212] border-gray-600 rounded focus:ring-[#76B900] focus:ring-offset-[#1A1A1A]"
                        aria-label="Is household member"
                      />
                      <span className="text-white text-sm">Is household member</span>
                    </label>
                  </div>
                )}

                {/* Actions */}
                <div className="flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    disabled={isPending}
                    className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleEnroll()}
                    disabled={!canEnroll}
                    className="px-4 py-2 text-sm font-medium bg-[#76B900] hover:bg-[#5a8f00] text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                  >
                    {isPending && (
                      <Loader2 className="h-4 w-4 animate-spin" data-testid="loading-spinner" />
                    )}
                    {isPending ? 'Enrolling...' : 'Enroll Face'}
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
