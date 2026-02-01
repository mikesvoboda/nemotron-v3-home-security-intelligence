/**
 * BulkEnrollmentModal - Modal for bulk face enrollment workflow
 *
 * Features:
 * - Multi-file upload interface with drag & drop
 * - Batch processing with progress indicator
 * - Per-image quality validation with preview
 * - Summary report of successful/failed enrollments
 * - Option to associate all with same person or create new person
 *
 * @module components/face-recognition/BulkEnrollmentModal
 * @see NEM-4954 - Bulk Enrollment Workflow
 */

import { Dialog, Listbox, Transition } from '@headlessui/react';
import {
  AlertCircle,
  Check,
  CheckCircle,
  ChevronDown,
  Home,
  Loader2,
  Upload,
  X,
  XCircle,
} from 'lucide-react';
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';

import {
  useKnownPersonsQuery,
  useBulkEnrollFaces,
  useCreateKnownPerson,
} from '../../hooks/useFaceRecognitionApi';
import { useToast } from '../../hooks/useToast';

import type { KnownPerson, BulkEnrollmentImageResult } from '../../types/faceRecognition';

// ============================================================================
// Types
// ============================================================================

export interface BulkEnrollmentModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
}

type EnrollMode = 'existing' | 'new';
type EnrollmentState = 'selecting' | 'processing' | 'complete';

interface FilePreview {
  file: File;
  previewUrl: string;
}

/** Maximum files per upload */
const MAX_FILES = 10;

/** Maximum embeddings per person */
const MAX_EMBEDDINGS = 10;

/** Accepted file types */
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/jpg'];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format file size for display.
 */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Validate file type.
 */
function isValidFileType(file: File): boolean {
  return ACCEPTED_TYPES.includes(file.type);
}

// ============================================================================
// Component
// ============================================================================

export default function BulkEnrollmentModal({
  isOpen,
  onClose,
}: BulkEnrollmentModalProps) {
  // Form state
  const [mode, setMode] = useState<EnrollMode>('existing');
  const [selectedPersonId, setSelectedPersonId] = useState<number | null>(null);
  const [newPersonName, setNewPersonName] = useState('');
  const [isHouseholdMember, setIsHouseholdMember] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [files, setFiles] = useState<FilePreview[]>([]);
  const [enrollmentState, setEnrollmentState] = useState<EnrollmentState>('selecting');
  const [results, setResults] = useState<BulkEnrollmentImageResult[]>([]);
  const [processingProgress, setProcessingProgress] = useState(0);

  // Data fetching
  const personsQuery = useKnownPersonsQuery();
  const bulkEnrollMutation = useBulkEnrollFaces();
  const createPersonMutation = useCreateKnownPerson();

  // Toast notifications
  const toast = useToast();

  // Determine if any mutation is pending
  const isPending = bulkEnrollMutation.isPending || createPersonMutation.isPending;

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
  const selectedAtMax = selectedPerson && selectedPerson.embedding_count >= MAX_EMBEDDINGS;
  const remainingSlots = selectedPerson
    ? MAX_EMBEDDINGS - selectedPerson.embedding_count
    : MAX_EMBEDDINGS;

  const canEnroll = useMemo(() => {
    if (files.length === 0) return false;
    if (isPending) return false;

    if (mode === 'existing') {
      return selectedPersonId !== null && !selectedAtMax;
    } else {
      return newPersonName.trim().length > 0;
    }
  }, [files.length, isPending, mode, selectedPersonId, selectedAtMax, newPersonName]);

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) {
      setMode('existing');
      setSelectedPersonId(null);
      setNewPersonName('');
      setIsHouseholdMember(false);
      setSearchQuery('');
      // Revoke object URLs to prevent memory leaks
      files.forEach((f) => URL.revokeObjectURL(f.previewUrl));
      setFiles([]);
      setEnrollmentState('selecting');
      setResults([]);
      setProcessingProgress(0);
    }
  }, [isOpen, files]);

  // Handle file selection
  const handleFileChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles) return;

    const newFiles: FilePreview[] = [];
    const errors: string[] = [];

    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i];

      if (!isValidFileType(file)) {
        errors.push(`${file.name}: Invalid file type. Only JPEG/PNG allowed.`);
        continue;
      }

      if (newFiles.length + files.length >= MAX_FILES) {
        errors.push(`Maximum ${MAX_FILES} files allowed.`);
        break;
      }

      newFiles.push({
        file,
        previewUrl: URL.createObjectURL(file),
      });
    }

    if (errors.length > 0) {
      toast.warning(errors.join(' '));
    }

    setFiles((prev) => [...prev, ...newFiles]);

    // Reset the input
    event.target.value = '';
  }, [files.length, toast]);

  // Handle drag and drop
  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();

    const droppedFiles = event.dataTransfer.files;
    if (!droppedFiles) return;

    const newFiles: FilePreview[] = [];
    const errors: string[] = [];

    for (let i = 0; i < droppedFiles.length; i++) {
      const file = droppedFiles[i];

      if (!isValidFileType(file)) {
        errors.push(`${file.name}: Invalid file type. Only JPEG/PNG allowed.`);
        continue;
      }

      if (newFiles.length + files.length >= MAX_FILES) {
        errors.push(`Maximum ${MAX_FILES} files allowed.`);
        break;
      }

      newFiles.push({
        file,
        previewUrl: URL.createObjectURL(file),
      });
    }

    if (errors.length > 0) {
      toast.warning(errors.join(' '));
    }

    setFiles((prev) => [...prev, ...newFiles]);
  }, [files.length, toast]);

  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
  }, []);

  // Remove a file
  const removeFile = useCallback((index: number) => {
    setFiles((prev) => {
      const newFiles = [...prev];
      URL.revokeObjectURL(newFiles[index].previewUrl);
      newFiles.splice(index, 1);
      return newFiles;
    });
  }, []);

  // Handle enrollment
  const handleEnroll = useCallback(async () => {
    if (!canEnroll) return;

    setEnrollmentState('processing');
    setProcessingProgress(0);

    try {
      // Start progress animation
      const progressInterval = setInterval(() => {
        setProcessingProgress((prev) => Math.min(prev + 5, 90));
      }, 100);

      const response = await bulkEnrollMutation.mutateAsync({
        images: files.map((f) => f.file),
        person_id: mode === 'existing' ? selectedPersonId ?? undefined : undefined,
        new_person_name: mode === 'new' ? newPersonName.trim() : undefined,
        is_household_member: mode === 'new' ? isHouseholdMember : undefined,
      });

      clearInterval(progressInterval);
      setProcessingProgress(100);

      setResults(response.results);
      setEnrollmentState('complete');

      if (response.successful === response.total_images) {
        toast.success(`All ${response.successful} faces enrolled successfully!`);
      } else if (response.successful > 0) {
        toast.warning(
          `Enrolled ${response.successful} of ${response.total_images} faces. ${response.failed} failed.`
        );
      } else {
        toast.error(`All ${response.failed} enrollments failed.`);
      }
    } catch (error) {
      setEnrollmentState('selecting');
      const message = error instanceof Error ? error.message : 'An error occurred';
      toast.error(`Bulk enrollment failed: ${message}`);
    }
  }, [
    canEnroll,
    files,
    mode,
    selectedPersonId,
    newPersonName,
    isHouseholdMember,
    bulkEnrollMutation,
    toast,
  ]);

  // Handle person selection
  const handlePersonSelect = useCallback((person: KnownPerson | null) => {
    setSelectedPersonId(person?.id ?? null);
    setSearchQuery('');
  }, []);

  // Handle close with cleanup
  const handleClose = useCallback(() => {
    if (isPending) return;
    onClose();
  }, [isPending, onClose]);

  // Summary stats
  const successCount = results.filter((r) => r.success).length;
  const failCount = results.filter((r) => !r.success).length;

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={handleClose}>
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
              <Dialog.Panel className="w-full max-w-2xl transform rounded-lg bg-[#1A1A1A] border border-gray-700 p-6 shadow-xl transition-all">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                  <Dialog.Title className="text-lg font-semibold text-white">
                    {enrollmentState === 'complete' ? 'Enrollment Results' : 'Bulk Face Enrollment'}
                  </Dialog.Title>
                  <button
                    type="button"
                    onClick={handleClose}
                    disabled={isPending}
                    className="p-1 text-gray-400 hover:text-white transition-colors disabled:opacity-50"
                    aria-label="Close modal"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Processing State */}
                {enrollmentState === 'processing' && (
                  <div className="space-y-6">
                    <div className="flex flex-col items-center justify-center py-12">
                      <Loader2 className="h-12 w-12 animate-spin text-[#76B900] mb-4" />
                      <p className="text-white text-lg font-medium">Processing images...</p>
                      <p className="text-gray-400 text-sm mt-2">
                        Validating faces and extracting embeddings
                      </p>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full">
                      <div className="flex justify-between text-sm text-gray-400 mb-2">
                        <span>Progress</span>
                        <span>{processingProgress}%</span>
                      </div>
                      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#76B900] transition-all duration-300"
                          style={{ width: `${processingProgress}%` }}
                          data-testid="progress-bar"
                        />
                      </div>
                    </div>
                  </div>
                )}

                {/* Complete State */}
                {enrollmentState === 'complete' && (
                  <div className="space-y-6">
                    {/* Summary Cards */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
                        <div className="flex items-center gap-2">
                          <CheckCircle className="h-5 w-5 text-green-400" />
                          <span className="text-green-400 font-medium">Successful</span>
                        </div>
                        <p className="text-2xl font-bold text-white mt-2" data-testid="success-count">
                          {successCount}
                        </p>
                      </div>
                      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                        <div className="flex items-center gap-2">
                          <XCircle className="h-5 w-5 text-red-400" />
                          <span className="text-red-400 font-medium">Failed</span>
                        </div>
                        <p className="text-2xl font-bold text-white mt-2" data-testid="fail-count">
                          {failCount}
                        </p>
                      </div>
                    </div>

                    {/* Results List */}
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      <p className="text-sm font-medium text-gray-300">Results by image:</p>
                      {results.map((result, index) => (
                        <div
                          key={index}
                          className={`flex items-center justify-between p-3 rounded-lg ${
                            result.success
                              ? 'bg-green-500/5 border border-green-500/20'
                              : 'bg-red-500/5 border border-red-500/20'
                          }`}
                          data-testid={`result-item-${index}`}
                        >
                          <div className="flex items-center gap-3">
                            {result.success ? (
                              <CheckCircle className="h-4 w-4 text-green-400 flex-shrink-0" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                            )}
                            <span className="text-white text-sm truncate max-w-[200px]">
                              {result.filename}
                            </span>
                          </div>
                          <div className="text-right">
                            {result.success ? (
                              <span className="text-green-400 text-sm">
                                Quality: {result.quality_score?.toFixed(2)}
                              </span>
                            ) : (
                              <span className="text-red-400 text-sm truncate max-w-[200px]">
                                {result.error}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Close Button */}
                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={handleClose}
                        className="px-6 py-2 text-sm font-medium bg-[#76B900] hover:bg-[#5a8f00] text-white rounded-lg transition-colors"
                      >
                        Done
                      </button>
                    </div>
                  </div>
                )}

                {/* Selecting State */}
                {enrollmentState === 'selecting' && (
                  <>
                    {/* File Upload Area */}
                    <div className="mb-6">
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Face Images ({files.length}/{MAX_FILES})
                      </label>
                      <div
                        className="border-2 border-dashed border-gray-600 rounded-lg p-6 text-center cursor-pointer hover:border-[#76B900] transition-colors"
                        onDrop={handleDrop}
                        onDragOver={handleDragOver}
                        onClick={() => document.getElementById('file-input')?.click()}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            document.getElementById('file-input')?.click();
                          }
                        }}
                        role="button"
                        tabIndex={0}
                        aria-label="Drop files or click to upload"
                        data-testid="drop-zone"
                      >
                        <Upload className="h-8 w-8 mx-auto text-gray-400 mb-2" />
                        <p className="text-gray-300">
                          Drag & drop images here, or click to select
                        </p>
                        <p className="text-gray-500 text-sm mt-1">
                          JPEG or PNG, max {MAX_FILES} files
                        </p>
                        <input
                          id="file-input"
                          type="file"
                          multiple
                          accept="image/jpeg,image/png,image/jpg"
                          onChange={handleFileChange}
                          className="hidden"
                          disabled={isPending || files.length >= MAX_FILES}
                          data-testid="file-input"
                        />
                      </div>
                    </div>

                    {/* File Previews */}
                    {files.length > 0 && (
                      <div className="mb-6">
                        <div className="grid grid-cols-5 gap-2">
                          {files.map((filePreview, index) => (
                            <div
                              key={index}
                              className="relative group"
                              data-testid={`file-preview-${index}`}
                            >
                              <img
                                src={filePreview.previewUrl}
                                alt={filePreview.file.name}
                                className="w-full h-20 object-cover rounded-lg border border-gray-700"
                              />
                              <button
                                type="button"
                                onClick={() => removeFile(index)}
                                className="absolute -top-2 -right-2 p-1 bg-red-500 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                                aria-label={`Remove ${filePreview.file.name}`}
                              >
                                <X className="h-3 w-3" />
                              </button>
                              <p className="text-xs text-gray-400 truncate mt-1 text-center">
                                {formatFileSize(filePreview.file.size)}
                              </p>
                            </div>
                          ))}
                        </div>
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
                                          const slots = MAX_EMBEDDINGS - person.embedding_count;
                                          return (
                                            <Listbox.Option
                                              key={person.id}
                                              value={person}
                                              disabled={atMax}
                                              className={({ active, disabled }) =>
                                                `cursor-pointer select-none relative py-2 pl-10 pr-4 ${
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
                                                      <span
                                                        className={`text-xs ${
                                                          atMax ? 'text-red-400' : 'text-gray-500'
                                                        }`}
                                                      >
                                                        {atMax
                                                          ? 'Max reached'
                                                          : `${slots} slots left`}
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

                        {selectedPerson && (
                          <div className="mt-2 flex items-center gap-2 text-sm">
                            {selectedAtMax ? (
                              <span className="text-red-400 flex items-center gap-1">
                                <AlertCircle className="h-4 w-4" />
                                This person has reached the maximum of {MAX_EMBEDDINGS} face
                                embeddings.
                              </span>
                            ) : (
                              <span className="text-gray-400">
                                Can enroll up to {remainingSlots} more{' '}
                                {remainingSlots === 1 ? 'face' : 'faces'}
                              </span>
                            )}
                          </div>
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

                    {/* Warnings */}
                    {files.length > remainingSlots && mode === 'existing' && selectedPerson && (
                      <div className="mb-6 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
                        <p className="text-sm text-yellow-400 flex items-center gap-2">
                          <AlertCircle className="h-4 w-4" />
                          Only {remainingSlots} of {files.length} images will be enrolled (limit
                          reached).
                        </p>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex justify-end gap-3">
                      <button
                        type="button"
                        onClick={handleClose}
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
                        data-testid="enroll-button"
                      >
                        {isPending && (
                          <Loader2 className="h-4 w-4 animate-spin" data-testid="loading-spinner" />
                        )}
                        {isPending
                          ? 'Processing...'
                          : `Enroll ${files.length} ${files.length === 1 ? 'Face' : 'Faces'}`}
                      </button>
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
