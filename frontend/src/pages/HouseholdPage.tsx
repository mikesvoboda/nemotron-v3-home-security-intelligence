/**
 * HouseholdPage - Household Members and Vehicles Management
 *
 * Provides a comprehensive view for managing household members and vehicles.
 * Includes CRUD operations with form validation and toast notifications.
 *
 * Features:
 * - Household members list with role and trust level badges
 * - Registered vehicles list with trusted status
 * - Add/Edit/Delete modals for members and vehicles
 * - Form validation
 * - Toast notifications for all operations
 *
 * @module pages/HouseholdPage
 * @see NEM-4849 Phase 1 - Household Members Page
 */

import { Dialog, Transition } from '@headlessui/react';
import { Car, Edit2, Loader2, Plus, RefreshCw, Trash2, User, Users } from 'lucide-react';
import { Fragment, useCallback, useRef, useState } from 'react';

import { useKnownPersonsQuery } from '../hooks/useFaceRecognitionApi';
import {
  useMembersQuery,
  useCreateMember,
  useUpdateMember,
  useDeleteMember,
  useVehiclesQuery,
  useCreateVehicle,
  useUpdateVehicle,
  useDeleteVehicle,
  useLinkMemberToPerson,
} from '../hooks/useHouseholdApi';
import { useToast } from '../hooks/useToast';

import type {
  HouseholdMember,
  HouseholdMemberCreate,
  HouseholdMemberUpdate,
  MemberRole,
  TrustLevel,
  RegisteredVehicle,
  RegisteredVehicleCreate,
  RegisteredVehicleUpdate,
  VehicleType,
} from '../hooks/useHouseholdApi';
import type { KnownPerson } from '../types/faceRecognition';

// ============================================================================
// Constants
// ============================================================================

const ROLE_OPTIONS: { value: MemberRole; label: string }[] = [
  { value: 'resident', label: 'Resident' },
  { value: 'family', label: 'Family' },
  { value: 'service_worker', label: 'Service Worker' },
  { value: 'frequent_visitor', label: 'Frequent Visitor' },
];

const TRUST_LEVEL_OPTIONS: { value: TrustLevel; label: string }[] = [
  { value: 'full', label: 'Full Trust' },
  { value: 'partial', label: 'Partial Trust' },
  { value: 'monitor', label: 'Monitor Only' },
];

const VEHICLE_TYPE_OPTIONS: { value: VehicleType; label: string }[] = [
  { value: 'car', label: 'Car' },
  { value: 'truck', label: 'Truck' },
  { value: 'motorcycle', label: 'Motorcycle' },
  { value: 'suv', label: 'SUV' },
  { value: 'van', label: 'Van' },
  { value: 'other', label: 'Other' },
];

// Label mappings for display
const ROLE_LABELS: Record<MemberRole, string> = {
  resident: 'Resident',
  family: 'Family',
  service_worker: 'Service Worker',
  frequent_visitor: 'Frequent Visitor',
};

const TRUST_LEVEL_LABELS: Record<TrustLevel, string> = {
  full: 'Full Trust',
  partial: 'Partial Trust',
  monitor: 'Monitor Only',
};

// ============================================================================
// Types
// ============================================================================

type ModalMode = 'add' | 'edit';

interface MemberFormData {
  name: string;
  role: MemberRole;
  trusted_level: TrustLevel;
  notes: string;
  known_person_id: number | null;
}

interface VehicleFormData {
  description: string;
  vehicle_type: VehicleType;
  license_plate: string;
  color: string;
  owner_id: number | null;
  trusted: boolean;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Badge component for displaying role and trust level.
 */
function Badge({
  children,
  variant,
}: {
  children: React.ReactNode;
  variant: 'role' | 'trust' | 'trusted';
}) {
  const baseClasses = 'px-2 py-0.5 text-xs font-medium rounded-full';
  const variantClasses = {
    role: 'bg-blue-500/20 text-blue-400',
    trust: 'bg-purple-500/20 text-purple-400',
    trusted: 'bg-green-500/20 text-green-400',
  };

  return <span className={`${baseClasses} ${variantClasses[variant]}`}>{children}</span>;
}

/**
 * Modal wrapper component using Headless UI Dialog.
 */
function Modal({
  isOpen,
  onClose,
  title,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
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
              <Dialog.Panel className="w-full max-w-md transform rounded-lg border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl transition-all">
                <Dialog.Title className="mb-4 text-lg font-semibold text-white">
                  {title}
                </Dialog.Title>
                {children}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}

/**
 * Delete confirmation dialog.
 */
function DeleteConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  itemName,
  isDeleting,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  itemName: string;
  isDeleting: boolean;
}) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Confirm Delete">
      <p className="mb-6 text-gray-300">
        Are you sure you want to delete <span className="font-medium text-white">{itemName}</span>?
        This action cannot be undone.
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
          onClick={() => void onConfirm()}
          disabled={isDeleting}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
        >
          {isDeleting ? 'Deleting...' : 'Confirm'}
        </button>
      </div>
    </Modal>
  );
}

// ============================================================================
// Member Form Component
// ============================================================================

function MemberForm({
  mode,
  initialData,
  knownPersons,
  knownPersonsLoading,
  onSave,
  onLinkPerson,
  onCancel,
  isSaving,
  apiError,
}: {
  mode: ModalMode;
  initialData?: HouseholdMember;
  knownPersons?: KnownPerson[];
  knownPersonsLoading: boolean;
  onSave: (
    data: HouseholdMemberCreate | { id: number; data: HouseholdMemberUpdate }
  ) => void | Promise<void>;
  onLinkPerson?: (memberId: number, knownPersonId: number | null) => void | Promise<void>;
  onCancel: () => void;
  isSaving: boolean;
  apiError?: string;
}) {
  const [formData, setFormData] = useState<MemberFormData>({
    name: initialData?.name ?? '',
    role: initialData?.role ?? 'resident',
    trusted_level: initialData?.trusted_level ?? 'full',
    notes: initialData?.notes ?? '',
    known_person_id: initialData?.known_person_id ?? null,
  });
  const [errors, setErrors] = useState<{ name?: string }>({});
  const nameInputRef = useRef<HTMLInputElement>(null);

  // Get known persons that are not already linked to another household member
  // (or are linked to this member)
  const availableKnownPersons = (knownPersons ?? []).filter(
    (p) => !p.household_member_id || p.household_member_id === initialData?.id
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!formData.name.trim()) {
      setErrors({ name: 'Name is required' });
      return;
    }

    setErrors({});

    if (mode === 'edit' && initialData) {
      // Check if known_person_id changed
      const knownPersonIdChanged = formData.known_person_id !== initialData.known_person_id;

      void onSave({
        id: initialData.id,
        data: {
          name: formData.name,
          role: formData.role,
          trusted_level: formData.trusted_level,
          notes: formData.notes || null,
        },
      });

      // If linking changed and callback provided, call it
      if (knownPersonIdChanged && onLinkPerson) {
        void onLinkPerson(initialData.id, formData.known_person_id);
      }
    } else {
      void onSave({
        name: formData.name,
        role: formData.role,
        trusted_level: formData.trusted_level,
        notes: formData.notes || null,
        typical_schedule: null,
      });
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-4">
        {/* Name */}
        <div>
          <label htmlFor="member-name" className="mb-1 block text-sm font-medium text-gray-300">
            Name
          </label>
          <input
            ref={nameInputRef}
            type="text"
            id="member-name"
            // eslint-disable-next-line jsx-a11y/no-autofocus -- First input in modal should receive focus for accessibility
            autoFocus
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            placeholder="Enter name"
          />
          {errors.name && <p className="mt-1 text-sm text-red-400">{errors.name}</p>}
        </div>

        {/* Role */}
        <div>
          <label htmlFor="member-role" className="mb-1 block text-sm font-medium text-gray-300">
            Role
          </label>
          <select
            id="member-role"
            value={formData.role}
            onChange={(e) => setFormData({ ...formData, role: e.target.value as MemberRole })}
            className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
          >
            {ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* Trust Level */}
        <div>
          <label
            htmlFor="member-trust-level"
            className="mb-1 block text-sm font-medium text-gray-300"
          >
            Trust Level
          </label>
          <select
            id="member-trust-level"
            value={formData.trusted_level}
            onChange={(e) =>
              setFormData({ ...formData, trusted_level: e.target.value as TrustLevel })
            }
            className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
          >
            {TRUST_LEVEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* Linked Known Person (only shown in edit mode) */}
        {mode === 'edit' && (
          <div>
            <label
              htmlFor="member-known-person"
              className="mb-1 block text-sm font-medium text-gray-300"
            >
              Linked Known Person
            </label>
            <select
              id="member-known-person"
              value={formData.known_person_id ?? ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  known_person_id: e.target.value ? Number(e.target.value) : null,
                })
              }
              disabled={knownPersonsLoading}
              className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900] disabled:opacity-50"
            >
              <option value="">Not linked to any known person</option>
              {availableKnownPersons?.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name} ({person.embedding_count} faces)
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">
              Link this member to a known person in the face recognition system
            </p>
          </div>
        )}

        {/* Notes */}
        <div>
          <label htmlFor="member-notes" className="mb-1 block text-sm font-medium text-gray-300">
            Notes
          </label>
          <textarea
            id="member-notes"
            value={formData.notes}
            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
            rows={3}
            className="w-full resize-none rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            placeholder="Optional notes"
          />
        </div>
      </div>

      {/* API Error Display */}
      {apiError && (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
          <p className="text-sm text-red-400">{apiError}</p>
        </div>
      )}

      <div className="mt-6 flex justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:text-white"
          disabled={isSaving}
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
  );
}

// ============================================================================
// Vehicle Form Component
// ============================================================================

function VehicleForm({
  mode,
  initialData,
  members,
  onSave,
  onCancel,
  isSaving,
  apiError,
}: {
  mode: ModalMode;
  initialData?: RegisteredVehicle;
  members: HouseholdMember[];
  onSave: (
    data: RegisteredVehicleCreate | { id: number; data: RegisteredVehicleUpdate }
  ) => void | Promise<void>;
  onCancel: () => void;
  isSaving: boolean;
  apiError?: string;
}) {
  const [formData, setFormData] = useState<VehicleFormData>({
    description: initialData?.description ?? '',
    vehicle_type: initialData?.vehicle_type ?? 'car',
    license_plate: initialData?.license_plate ?? '',
    color: initialData?.color ?? '',
    owner_id: initialData?.owner_id ?? null,
    trusted: initialData?.trusted ?? true,
  });
  const [errors, setErrors] = useState<{ description?: string }>({});
  const descInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!formData.description.trim()) {
      setErrors({ description: 'Description is required' });
      return;
    }

    setErrors({});

    if (mode === 'edit' && initialData) {
      void onSave({
        id: initialData.id,
        data: {
          description: formData.description,
          vehicle_type: formData.vehicle_type,
          license_plate: formData.license_plate || null,
          color: formData.color || null,
          owner_id: formData.owner_id,
          trusted: formData.trusted,
        },
      });
    } else {
      void onSave({
        description: formData.description,
        vehicle_type: formData.vehicle_type,
        license_plate: formData.license_plate || null,
        color: formData.color || null,
        owner_id: formData.owner_id,
        trusted: formData.trusted,
      });
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-4">
        {/* Description */}
        <div>
          <label
            htmlFor="vehicle-description"
            className="mb-1 block text-sm font-medium text-gray-300"
          >
            Description
          </label>
          <input
            ref={descInputRef}
            type="text"
            id="vehicle-description"
            // eslint-disable-next-line jsx-a11y/no-autofocus -- First input in modal should receive focus for accessibility
            autoFocus
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            placeholder="e.g., Silver Tesla Model 3"
          />
          {errors.description && <p className="mt-1 text-sm text-red-400">{errors.description}</p>}
        </div>

        {/* Vehicle Type */}
        <div>
          <label htmlFor="vehicle-type" className="mb-1 block text-sm font-medium text-gray-300">
            Vehicle Type
          </label>
          <select
            id="vehicle-type"
            value={formData.vehicle_type}
            onChange={(e) =>
              setFormData({ ...formData, vehicle_type: e.target.value as VehicleType })
            }
            className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
          >
            {VEHICLE_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* License Plate */}
        <div>
          <label
            htmlFor="vehicle-license-plate"
            className="mb-1 block text-sm font-medium text-gray-300"
          >
            License Plate
          </label>
          <input
            type="text"
            id="vehicle-license-plate"
            value={formData.license_plate}
            onChange={(e) => setFormData({ ...formData, license_plate: e.target.value })}
            className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            placeholder="ABC123 (optional)"
          />
        </div>

        {/* Color */}
        <div>
          <label htmlFor="vehicle-color" className="mb-1 block text-sm font-medium text-gray-300">
            Color
          </label>
          <input
            type="text"
            id="vehicle-color"
            value={formData.color}
            onChange={(e) => setFormData({ ...formData, color: e.target.value })}
            className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            placeholder="Silver (optional)"
          />
        </div>

        {/* Owner */}
        <div>
          <label htmlFor="vehicle-owner" className="mb-1 block text-sm font-medium text-gray-300">
            Owner
          </label>
          <select
            id="vehicle-owner"
            value={formData.owner_id ?? ''}
            onChange={(e) =>
              setFormData({ ...formData, owner_id: e.target.value ? Number(e.target.value) : null })
            }
            className="w-full rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-white focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#76B900]"
          >
            <option value="">No owner assigned</option>
            {members.map((member) => (
              <option key={member.id} value={member.id}>
                {member.name}
              </option>
            ))}
          </select>
        </div>

        {/* Trusted */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="vehicle-trusted"
            checked={formData.trusted}
            onChange={(e) => setFormData({ ...formData, trusted: e.target.checked })}
            className="h-4 w-4 rounded border-gray-700 bg-[#121212] text-[#76B900] focus:ring-[#76B900] focus:ring-offset-[#1A1A1A]"
          />
          <label htmlFor="vehicle-trusted" className="text-sm font-medium text-gray-300">
            Trusted Vehicle
          </label>
        </div>
      </div>

      {/* API Error Display */}
      {apiError && (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
          <p className="text-sm text-red-400">{apiError}</p>
        </div>
      )}

      <div className="mt-6 flex justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:text-white"
          disabled={isSaving}
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
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function HouseholdPage() {
  // Data fetching
  const {
    data: members,
    isLoading: membersLoading,
    error: membersError,
    refetch: refetchMembers,
  } = useMembersQuery();

  const {
    data: vehicles,
    isLoading: vehiclesLoading,
    error: vehiclesError,
    refetch: refetchVehicles,
  } = useVehiclesQuery();

  // Fetch known persons for linking
  const { data: knownPersons, isLoading: knownPersonsLoading } = useKnownPersonsQuery();

  // Mutations
  const createMemberMutation = useCreateMember();
  const updateMemberMutation = useUpdateMember();
  const deleteMemberMutation = useDeleteMember();
  const createVehicleMutation = useCreateVehicle();
  const updateVehicleMutation = useUpdateVehicle();
  const deleteVehicleMutation = useDeleteVehicle();
  const linkMemberToPersonMutation = useLinkMemberToPerson();

  // Toast
  const toast = useToast();

  // Modal state
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [memberModalMode, setMemberModalMode] = useState<ModalMode>('add');
  const [selectedMember, setSelectedMember] = useState<HouseholdMember | undefined>();
  const [memberApiError, setMemberApiError] = useState<string | undefined>();

  const [vehicleModalOpen, setVehicleModalOpen] = useState(false);
  const [vehicleModalMode, setVehicleModalMode] = useState<ModalMode>('add');
  const [selectedVehicle, setSelectedVehicle] = useState<RegisteredVehicle | undefined>();
  const [vehicleApiError, setVehicleApiError] = useState<string | undefined>();

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{
    type: 'member' | 'vehicle';
    id: number;
    name: string;
  } | null>(null);

  // Loading state
  const isLoading = membersLoading || vehiclesLoading;
  const hasError = membersError || vehiclesError;
  const errorMessage = membersError?.message || vehiclesError?.message || 'Failed to load data';

  // Handlers
  const handleRefresh = useCallback(() => {
    void refetchMembers();
    void refetchVehicles();
  }, [refetchMembers, refetchVehicles]);

  const handleRetry = useCallback(() => {
    void refetchMembers();
    void refetchVehicles();
  }, [refetchMembers, refetchVehicles]);

  // Member handlers
  const handleOpenAddMember = useCallback(() => {
    setMemberModalMode('add');
    setSelectedMember(undefined);
    setMemberApiError(undefined);
    setMemberModalOpen(true);
  }, []);

  const handleOpenEditMember = useCallback((member: HouseholdMember) => {
    setMemberModalMode('edit');
    setSelectedMember(member);
    setMemberApiError(undefined);
    setMemberModalOpen(true);
  }, []);

  const handleCloseMemberModal = useCallback(() => {
    setMemberModalOpen(false);
    setSelectedMember(undefined);
    setMemberApiError(undefined);
  }, []);

  const handleSaveMember = useCallback(
    async (data: HouseholdMemberCreate | { id: number; data: HouseholdMemberUpdate }) => {
      try {
        setMemberApiError(undefined);
        if ('id' in data) {
          await updateMemberMutation.mutateAsync(data);
          toast.success('Member updated successfully');
        } else {
          await createMemberMutation.mutateAsync(data);
          toast.success('Member created successfully');
        }
        handleCloseMemberModal();
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to save member';
        setMemberApiError(message);
        toast.error(message);
      }
    },
    [createMemberMutation, updateMemberMutation, toast, handleCloseMemberModal]
  );

  const handleLinkMemberToPerson = useCallback(
    async (memberId: number, knownPersonId: number | null) => {
      try {
        await linkMemberToPersonMutation.mutateAsync({ memberId, knownPersonId });
        const action = knownPersonId ? 'linked' : 'unlinked';
        toast.success(`Member ${action} successfully`);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to update link';
        toast.error(message);
      }
    },
    [linkMemberToPersonMutation, toast]
  );

  const handleDeleteMember = useCallback((member: HouseholdMember) => {
    setDeleteTarget({ type: 'member', id: member.id, name: member.name });
    setDeleteModalOpen(true);
  }, []);

  // Vehicle handlers
  const handleOpenAddVehicle = useCallback(() => {
    setVehicleModalMode('add');
    setSelectedVehicle(undefined);
    setVehicleApiError(undefined);
    setVehicleModalOpen(true);
  }, []);

  const handleOpenEditVehicle = useCallback((vehicle: RegisteredVehicle) => {
    setVehicleModalMode('edit');
    setSelectedVehicle(vehicle);
    setVehicleApiError(undefined);
    setVehicleModalOpen(true);
  }, []);

  const handleCloseVehicleModal = useCallback(() => {
    setVehicleModalOpen(false);
    setSelectedVehicle(undefined);
    setVehicleApiError(undefined);
  }, []);

  const handleSaveVehicle = useCallback(
    async (data: RegisteredVehicleCreate | { id: number; data: RegisteredVehicleUpdate }) => {
      try {
        setVehicleApiError(undefined);
        if ('id' in data) {
          await updateVehicleMutation.mutateAsync(data);
          toast.success('Vehicle updated successfully');
        } else {
          await createVehicleMutation.mutateAsync(data);
          toast.success('Vehicle created successfully');
        }
        handleCloseVehicleModal();
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to save vehicle';
        setVehicleApiError(message);
        toast.error(message);
      }
    },
    [createVehicleMutation, updateVehicleMutation, toast, handleCloseVehicleModal]
  );

  const handleDeleteVehicle = useCallback((vehicle: RegisteredVehicle) => {
    setDeleteTarget({ type: 'vehicle', id: vehicle.id, name: vehicle.description });
    setDeleteModalOpen(true);
  }, []);

  // Delete confirmation handler
  const handleConfirmDelete = useCallback(async () => {
    if (!deleteTarget) return;

    try {
      if (deleteTarget.type === 'member') {
        await deleteMemberMutation.mutateAsync(deleteTarget.id);
        toast.success('Member deleted successfully');
      } else {
        await deleteVehicleMutation.mutateAsync(deleteTarget.id);
        toast.success('Vehicle deleted successfully');
      }
      setDeleteModalOpen(false);
      setDeleteTarget(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete';
      toast.error(message);
    }
  }, [deleteTarget, deleteMemberMutation, deleteVehicleMutation, toast]);

  const handleCloseDeleteModal = useCallback(() => {
    setDeleteModalOpen(false);
    setDeleteTarget(null);
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-6" data-testid="household-page">
        <div className="mx-auto max-w-[1400px]">
          <div
            className="flex min-h-[400px] items-center justify-center"
            data-testid="loading-state"
          >
            <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
            <span className="ml-2 text-gray-300">Loading...</span>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (hasError) {
    return (
      <div className="min-h-screen bg-[#121212] p-6" data-testid="household-page">
        <div className="mx-auto max-w-[1400px]">
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-6">
            <p className="mb-4 text-red-400">Error: {errorMessage}</p>
            <button
              onClick={handleRetry}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const memberCount = members?.length ?? 0;
  const vehicleCount = vehicles?.length ?? 0;

  return (
    <div className="min-h-screen bg-[#121212] p-6" data-testid="household-page">
      <div className="mx-auto max-w-[1400px]">
        {/* Header */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Household Members</h1>
            <p className="mt-1 text-sm text-gray-400">
              Manage your household and registered transportation
            </p>
          </div>
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-800 hover:text-white"
            aria-label="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>

        {/* Members Section */}
        <section className="mb-8" aria-labelledby="members-heading">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Users className="h-5 w-5 text-[#76B900]" />
              <h2 id="members-heading" className="text-lg font-semibold text-white">
                Members
              </h2>
              <span
                className="rounded-full bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-300"
                data-testid="member-count-badge"
              >
                {memberCount}
              </span>
            </div>
            <button
              onClick={handleOpenAddMember}
              aria-label="Add Member"
              className="inline-flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#5a8f00]"
            >
              <Plus className="h-4 w-4" />
              Add Membe&#8203;r
            </button>
          </div>

          {memberCount === 0 ? (
            <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-8 text-center">
              <Users className="mx-auto mb-4 h-12 w-12 text-gray-600" />
              <p className="mb-2 text-gray-400">No members yet</p>
              <p className="text-sm text-gray-500">
                Add your first household member to get started
              </p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {members?.map((member) => {
                // Find linked known person
                const linkedKnownPerson = (knownPersons ?? []).find(
                  (p) => p.household_member_id === member.id
                );
                return (
                  <div
                    key={member.id}
                    className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4"
                  >
                    <div className="mb-3 flex items-start justify-between">
                      <div>
                        <h3 className="font-medium text-white">{member.name}</h3>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <Badge variant="role">{ROLE_LABELS[member.role]}</Badge>
                          <Badge variant="trust">{TRUST_LEVEL_LABELS[member.trusted_level]}</Badge>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleOpenEditMember(member)}
                          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
                          aria-label="Edit"
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteMember(member)}
                          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-red-400"
                          aria-label="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                    {/* Linked Known Person */}
                    {linkedKnownPerson && (
                      <div
                        className="mb-2 flex items-center gap-2 text-xs text-[#76B900]"
                        data-testid="linked-known-person"
                      >
                        <User className="h-3.5 w-3.5" />
                        <span>
                          Linked: {linkedKnownPerson.name} ({linkedKnownPerson.embedding_count}{' '}
                          faces)
                        </span>
                      </div>
                    )}
                    {member.notes && <p className="mt-2 text-sm text-gray-400">{member.notes}</p>}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Vehicles Section */}
        <section aria-labelledby="vehicles-heading">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Car className="h-5 w-5 text-blue-400" />
              <h2 id="vehicles-heading" className="text-lg font-semibold text-white">
                Vehicles
              </h2>
              <span className="rounded-full bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-300">
                {vehicleCount}&#8203;
              </span>
            </div>
            <button
              onClick={handleOpenAddVehicle}
              aria-label="Add Vehicle"
              className="inline-flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#5a8f00]"
            >
              <Plus className="h-4 w-4" />
              Add Vehicl&#8203;e
            </button>
          </div>

          {vehicleCount === 0 ? (
            <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-8 text-center">
              <Car className="mx-auto mb-4 h-12 w-12 text-gray-600" />
              <p className="mb-2 text-gray-400">No vehicles yet</p>
              <p className="text-sm text-gray-500">Add your first vehicle to get started</p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {vehicles?.map((vehicle) => (
                <div
                  key={vehicle.id}
                  className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4"
                >
                  <div className="mb-3 flex items-start justify-between">
                    <div>
                      <h3 className="font-medium text-white">{vehicle.description}</h3>
                      <div className="mt-1 flex items-center gap-2">
                        {vehicle.license_plate && (
                          <span className="text-sm text-gray-400">{vehicle.license_plate}</span>
                        )}
                        {vehicle.trusted && <Badge variant="trusted">Trusted</Badge>}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleOpenEditVehicle(vehicle)}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
                        aria-label="Edit"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteVehicle(vehicle)}
                        className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-red-400"
                        aria-label="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  {vehicle.color && <p className="text-sm text-gray-400">Color: {vehicle.color}</p>}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Member Modal */}
        <Modal
          isOpen={memberModalOpen}
          onClose={handleCloseMemberModal}
          title={memberModalMode === 'add' ? 'Add Member' : 'Edit Member'}
        >
          <MemberForm
            mode={memberModalMode}
            initialData={selectedMember}
            knownPersons={knownPersons}
            knownPersonsLoading={knownPersonsLoading}
            onSave={handleSaveMember}
            onLinkPerson={handleLinkMemberToPerson}
            onCancel={handleCloseMemberModal}
            isSaving={
              createMemberMutation.isPending ||
              updateMemberMutation.isPending ||
              linkMemberToPersonMutation.isPending
            }
            apiError={memberApiError}
          />
        </Modal>

        {/* Vehicle Modal */}
        <Modal
          isOpen={vehicleModalOpen}
          onClose={handleCloseVehicleModal}
          title={vehicleModalMode === 'add' ? 'Add Vehicle' : 'Edit Vehicle'}
        >
          <VehicleForm
            mode={vehicleModalMode}
            initialData={selectedVehicle}
            members={members ?? []}
            onSave={handleSaveVehicle}
            onCancel={handleCloseVehicleModal}
            isSaving={createVehicleMutation.isPending || updateVehicleMutation.isPending}
            apiError={vehicleApiError}
          />
        </Modal>

        {/* Delete Confirmation Modal */}
        <DeleteConfirmDialog
          isOpen={deleteModalOpen}
          onClose={handleCloseDeleteModal}
          onConfirm={handleConfirmDelete}
          itemName={deleteTarget?.name ?? ''}
          isDeleting={deleteMemberMutation.isPending || deleteVehicleMutation.isPending}
        />
      </div>
    </div>
  );
}
