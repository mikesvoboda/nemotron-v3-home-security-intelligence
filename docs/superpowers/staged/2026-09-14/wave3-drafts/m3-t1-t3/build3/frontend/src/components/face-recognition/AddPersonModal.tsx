/**
 * AddPersonModal - Modal for adding or editing a known person
 *
 * A modal dialog that provides a form for creating or editing known persons
 * in the face recognition system. Supports both add and edit modes.
 *
 * Features:
 * - Form fields: Name (required), Is Household Member (checkbox), Notes (optional)
 * - Form validation with error messages
 * - Uses Headless UI Dialog for accessibility
 * - Toast notifications on success/error
 * - Loading state during save operation
 *
 * @module components/face-recognition/AddPersonModal
 * @see NEM-4688 Phase 1 - Create Add/Edit Person Modal
 */

import { Dialog, Transition } from '@headlessui/react';
import { Fragment, useCallback, useEffect, useState } from 'react';

import { useCreateKnownPerson, useUpdateKnownPerson } from '../../hooks/useKnownPersonsApi';
import { useToast } from '../../hooks/useToast';

import type { KnownPerson } from '../../types/faceRecognition';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the AddPersonModal component.
 */
export interface AddPersonModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** If provided, edit mode is enabled with this person's data */
  editPerson?: KnownPerson;
}

/**
 * Form data structure for the person form.
 */
interface PersonFormData {
  name: string;
  is_household_member: boolean;
  notes: string;
}

/**
 * Form validation errors.
 */
interface FormErrors {
  name?: string;
}

// ============================================================================
// Initial Form Data
// ============================================================================

const getInitialFormData = (editPerson?: KnownPerson): PersonFormData => ({
  name: editPerson?.name ?? '',
  is_household_member: editPerson?.is_household_member ?? false,
  notes: editPerson?.notes ?? '',
});

// ============================================================================
// Component
// ============================================================================

/**
 * Modal for adding or editing a known person.
 */
export default function AddPersonModal({
  isOpen,
  onClose,
  editPerson,
}: AddPersonModalProps): React.ReactElement {
  // ==========================================================================
  // State
  // ==========================================================================

  const [formData, setFormData] = useState<PersonFormData>(getInitialFormData(editPerson));
  const [errors, setErrors] = useState<FormErrors>({});

  // ==========================================================================
  // Hooks
  // ==========================================================================

  const toast = useToast();
  const createMutation = useCreateKnownPerson();
  const updateMutation = useUpdateKnownPerson();

  const isEditMode = !!editPerson;
  const isSaving = createMutation.isPending || updateMutation.isPending;

  // ==========================================================================
  // Effects
  // ==========================================================================

  // Reset form when modal opens/closes or editPerson changes
  useEffect(() => {
    if (isOpen) {
      setFormData(getInitialFormData(editPerson));
      setErrors({});
    }
  }, [isOpen, editPerson]);

  // ==========================================================================
  // Handlers
  // ==========================================================================

  const handleNameChange = useCallback((value: string) => {
    setFormData((prev) => ({ ...prev, name: value }));
    // Clear error when user starts typing
    if (value.trim()) {
      setErrors((prev) => ({ ...prev, name: undefined }));
    }
  }, []);

  const handleHouseholdMemberChange = useCallback((checked: boolean) => {
    setFormData((prev) => ({ ...prev, is_household_member: checked }));
  }, []);

  const handleNotesChange = useCallback((value: string) => {
    setFormData((prev) => ({ ...prev, notes: value }));
  }, []);

  const validateForm = useCallback((): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData.name]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!validateForm()) {
        return;
      }

      try {
        if (isEditMode && editPerson) {
          await updateMutation.mutateAsync({
            id: editPerson.id,
            data: {
              name: formData.name,
              is_household_member: formData.is_household_member,
              notes: formData.notes || null,
            },
          });
          toast.success('Person updated successfully');
        } else {
          await createMutation.mutateAsync({
            name: formData.name,
            is_household_member: formData.is_household_member,
            notes: formData.notes || null,
          });
          toast.success('Person created successfully');
        }
        onClose();
      } catch (error) {
        const message = error instanceof Error ? error.message : 'An error occurred';
        toast.error(message);
      }
    },
    [validateForm, isEditMode, editPerson, formData, updateMutation, createMutation, toast, onClose]
  );

  const handleCancel = useCallback(() => {
    onClose();
  }, [onClose]);

  // ==========================================================================
  // Render
  // ==========================================================================

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        {/* Backdrop */}
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

        {/* Modal Container */}
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
              <Dialog.Panel className="w-full max-w-md transform rounded-lg border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl transition-all">
                {/* Title */}
                <Dialog.Title className="mb-4 text-lg font-semibold text-white">
                  {isEditMode ? 'Edit Person' : 'Add Person'}
                </Dialog.Title>

                {/* Form */}
                <form onSubmit={(e) => void handleSubmit(e)}>
                  <div className="space-y-4">
                    {/* Name Field */}
                    <div>
                      <label
                        htmlFor="person-name"
                        className="mb-1 block text-sm font-medium text-gray-300"
                      >
                        Name
                      </label>
                      <input
                        type="text"
                        id="person-name"
                        // eslint-disable-next-line jsx-a11y/no-autofocus -- First input in modal should receive focus for accessibility
                        autoFocus
                        value={formData.name}
                        onChange={(e) => handleNameChange(e.target.value)}
                        className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
                        placeholder="Enter name"
                      />
                      {errors.name && <p className="mt-1 text-sm text-red-400">{errors.name}</p>}
                    </div>

                    {/* Household Member Checkbox */}
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="person-household-member"
                        checked={formData.is_household_member}
                        onChange={(e) => handleHouseholdMemberChange(e.target.checked)}
                        className="h-4 w-4 rounded border-gray-700 bg-[#121212] text-[#76B900] focus:ring-[#76B900] focus:ring-offset-[#1A1A1A]"
                      />
                      <label
                        htmlFor="person-household-member"
                        className="text-sm font-medium text-gray-300"
                      >
                        Household Member
                      </label>
                    </div>

                    {/* Notes Field */}
                    <div>
                      <label
                        htmlFor="person-notes"
                        className="mb-1 block text-sm font-medium text-gray-300"
                      >
                        Notes
                      </label>
                      <textarea
                        id="person-notes"
                        value={formData.notes}
                        onChange={(e) => handleNotesChange(e.target.value)}
                        rows={3}
                        className="w-full resize-none rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
                        placeholder="Optional notes"
                      />
                    </div>
                  </div>

                  {/* Buttons */}
                  <div className="mt-6 flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={handleCancel}
                      disabled={isSaving}
                      className="px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:text-white disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSaving}
                      className="rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#5a8f00] disabled:opacity-50"
                    >
                      {isSaving ? 'Saving...' : 'Save'}
                    </button>
                  </div>
                </form>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
