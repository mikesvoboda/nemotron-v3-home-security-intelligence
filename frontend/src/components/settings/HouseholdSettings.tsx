/**
 * HouseholdSettings - Household organization management component
 *
 * Provides UI for managing:
 * - Household name (edit capability)
 * - Household members (CRUD operations)
 * - Registered vehicles (CRUD operations)
 * - Link to Property Management
 *
 * Phase 7.1: Create HouseholdSettings component (NEM-3134)
 * Part of the Orphaned Infrastructure Integration epic (NEM-3113).
 *
 * @see docs/plans/2026-01-20-orphaned-infrastructure-integration-design.md
 */

import { Dialog, Transition } from '@headlessui/react';
import { Card, Title, Text, Button, TextInput, Select, SelectItem, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Building2,
  Car,
  Check,
  ChevronRight,
  Edit2,
  Home,
  Loader2,
  Plus,
  Trash2,
  User,
  Users,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  useHouseholdApi,
  type HouseholdMember,
  type HouseholdMemberCreate,
  type HouseholdMemberUpdate,
  type RegisteredVehicle,
  type RegisteredVehicleCreate,
  type RegisteredVehicleUpdate,
  type MemberRole,
  type TrustLevel,
  type VehicleType,
} from '../../hooks/useHouseholdApi';
import { useToast } from '../../hooks/useToast';

// ============================================================================
// Constants
// ============================================================================

const MEMBER_ROLES: { value: MemberRole; label: string }[] = [
  { value: 'resident', label: 'Resident' },
  { value: 'family', label: 'Family' },
  { value: 'service_worker', label: 'Service Worker' },
  { value: 'frequent_visitor', label: 'Frequent Visitor' },
];

const TRUST_LEVELS: { value: TrustLevel; label: string; description: string }[] = [
  { value: 'full', label: 'Full Trust', description: 'Never trigger alerts' },
  { value: 'partial', label: 'Partial Trust', description: 'Reduced alert severity' },
  { value: 'monitor', label: 'Monitor', description: 'Log activity, no suppression' },
];

const VEHICLE_TYPES: { value: VehicleType; label: string }[] = [
  { value: 'car', label: 'Car' },
  { value: 'suv', label: 'SUV' },
  { value: 'truck', label: 'Truck' },
  { value: 'van', label: 'Van' },
  { value: 'motorcycle', label: 'Motorcycle' },
  { value: 'other', label: 'Other' },
];

// ============================================================================
// Component Types
// ============================================================================

export interface HouseholdSettingsProps {
  /** Optional className for styling */
  className?: string;
}

interface MemberFormData {
  name: string;
  role: MemberRole;
  trusted_level: TrustLevel;
  notes: string;
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
 * Loading skeleton for list items.
 */
function ListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="flex h-16 animate-pulse items-center justify-between rounded-lg border border-gray-700 bg-[#121212] p-4"
        >
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-full bg-gray-700" />
            <div className="space-y-2">
              <div className="h-4 w-32 rounded bg-gray-700" />
              <div className="h-3 w-24 rounded bg-gray-700" />
            </div>
          </div>
          <div className="flex gap-2">
            <div className="h-8 w-16 rounded bg-gray-700" />
            <div className="h-8 w-16 rounded bg-gray-700" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Error state display.
 */
function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-500/5 p-6">
      <AlertTriangle className="mb-2 h-8 w-8 text-red-400" />
      <Text className="mb-2 text-red-400">{message}</Text>
      {onRetry && (
        <Button size="xs" variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

/**
 * Empty state display.
 */
function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-gray-700 bg-[#121212] p-8">
      <Icon className="mb-3 h-10 w-10 text-gray-500" />
      <Text className="mb-1 font-medium text-gray-300">{title}</Text>
      <Text className="mb-4 text-center text-sm text-gray-500">{description}</Text>
      {action}
    </div>
  );
}

/**
 * Trust level badge with appropriate styling.
 */
function TrustBadge({ level }: { level: TrustLevel }) {
  const colorMap: Record<TrustLevel, 'green' | 'yellow' | 'gray'> = {
    full: 'green',
    partial: 'yellow',
    monitor: 'gray',
  };
  const labelMap: Record<TrustLevel, string> = {
    full: 'Full Trust',
    partial: 'Partial',
    monitor: 'Monitor',
  };
  return (
    <Badge color={colorMap[level]} size="sm">
      {labelMap[level]}
    </Badge>
  );
}

/**
 * Role badge with appropriate styling.
 */
function RoleBadge({ role }: { role: MemberRole }) {
  const labelMap: Record<MemberRole, string> = {
    resident: 'Resident',
    family: 'Family',
    service_worker: 'Service',
    frequent_visitor: 'Visitor',
  };
  return (
    <Badge color="blue" size="sm">
      {labelMap[role]}
    </Badge>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * HouseholdSettings component for managing household organization.
 *
 * Features:
 * - Display and edit household name
 * - List, create, edit, and delete household members
 * - List, create, edit, and delete registered vehicles
 * - Navigation to Property Management
 */
export default function HouseholdSettings({ className }: HouseholdSettingsProps) {
  const toast = useToast();
  const {
    members,
    membersLoading,
    membersError,
    createMember,
    updateMember,
    deleteMember,
    vehicles,
    vehiclesLoading,
    vehiclesError,
    createVehicle,
    updateVehicle,
    deleteVehicle,
    households,
    householdsLoading,
    updateHousehold,
  } = useHouseholdApi();

  // State for household name editing
  const [isEditingHouseholdName, setIsEditingHouseholdName] = useState(false);
  const [householdNameInput, setHouseholdNameInput] = useState('');

  // State for member modal
  const [memberModalOpen, setMemberModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<HouseholdMember | null>(null);
  const [memberForm, setMemberForm] = useState<MemberFormData>({
    name: '',
    role: 'resident',
    trusted_level: 'full',
    notes: '',
  });

  // State for vehicle modal
  const [vehicleModalOpen, setVehicleModalOpen] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<RegisteredVehicle | null>(null);
  const [vehicleForm, setVehicleForm] = useState<VehicleFormData>({
    description: '',
    vehicle_type: 'car',
    license_plate: '',
    color: '',
    owner_id: null,
    trusted: true,
  });

  // State for delete confirmations
  const [deletingMemberId, setDeletingMemberId] = useState<number | null>(null);
  const [deletingVehicleId, setDeletingVehicleId] = useState<number | null>(null);

  // Get the first household (single-user system)
  const household = households?.items?.[0];

  // ============================================================================
  // Handlers - Household Name
  // ============================================================================

  const handleStartEditHouseholdName = useCallback(() => {
    setHouseholdNameInput(household?.name ?? '');
    setIsEditingHouseholdName(true);
  }, [household?.name]);

  const handleSaveHouseholdName = useCallback(async () => {
    if (!household || !householdNameInput.trim()) return;

    try {
      await updateHousehold.mutateAsync({
        id: household.id,
        data: { name: householdNameInput.trim() },
      });
      toast.success('Household name updated');
      setIsEditingHouseholdName(false);
    } catch (error) {
      toast.error('Failed to update household name', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [household, householdNameInput, updateHousehold, toast]);

  const handleCancelEditHouseholdName = useCallback(() => {
    setIsEditingHouseholdName(false);
    setHouseholdNameInput('');
  }, []);

  // ============================================================================
  // Handlers - Members
  // ============================================================================

  const handleOpenMemberModal = useCallback((member?: HouseholdMember) => {
    if (member) {
      setEditingMember(member);
      setMemberForm({
        name: member.name,
        role: member.role,
        trusted_level: member.trusted_level,
        notes: member.notes ?? '',
      });
    } else {
      setEditingMember(null);
      setMemberForm({
        name: '',
        role: 'resident',
        trusted_level: 'full',
        notes: '',
      });
    }
    setMemberModalOpen(true);
  }, []);

  const handleCloseMemberModal = useCallback(() => {
    setMemberModalOpen(false);
    setEditingMember(null);
    setMemberForm({
      name: '',
      role: 'resident',
      trusted_level: 'full',
      notes: '',
    });
  }, []);

  const handleSaveMember = useCallback(async () => {
    if (!memberForm.name.trim()) {
      toast.error('Name is required');
      return;
    }

    try {
      if (editingMember) {
        const updateData: HouseholdMemberUpdate = {
          name: memberForm.name.trim(),
          role: memberForm.role,
          trusted_level: memberForm.trusted_level,
          notes: memberForm.notes.trim() || null,
        };
        await updateMember.mutateAsync({ id: editingMember.id, data: updateData });
        toast.success('Member updated');
      } else {
        const createData: HouseholdMemberCreate = {
          name: memberForm.name.trim(),
          role: memberForm.role,
          trusted_level: memberForm.trusted_level,
          notes: memberForm.notes.trim() || null,
        };
        await createMember.mutateAsync(createData);
        toast.success('Member added');
      }
      handleCloseMemberModal();
    } catch (error) {
      toast.error(editingMember ? 'Failed to update member' : 'Failed to add member', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [memberForm, editingMember, createMember, updateMember, toast, handleCloseMemberModal]);

  const handleDeleteMember = useCallback(
    async (id: number) => {
      try {
        await deleteMember.mutateAsync(id);
        toast.success('Member deleted');
        setDeletingMemberId(null);
      } catch (error) {
        toast.error('Failed to delete member', {
          description: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    },
    [deleteMember, toast]
  );

  // ============================================================================
  // Handlers - Vehicles
  // ============================================================================

  const handleOpenVehicleModal = useCallback((vehicle?: RegisteredVehicle) => {
    if (vehicle) {
      setEditingVehicle(vehicle);
      setVehicleForm({
        description: vehicle.description,
        vehicle_type: vehicle.vehicle_type,
        license_plate: vehicle.license_plate ?? '',
        color: vehicle.color ?? '',
        owner_id: vehicle.owner_id ?? null,
        trusted: vehicle.trusted,
      });
    } else {
      setEditingVehicle(null);
      setVehicleForm({
        description: '',
        vehicle_type: 'car',
        license_plate: '',
        color: '',
        owner_id: null,
        trusted: true,
      });
    }
    setVehicleModalOpen(true);
  }, []);

  const handleCloseVehicleModal = useCallback(() => {
    setVehicleModalOpen(false);
    setEditingVehicle(null);
    setVehicleForm({
      description: '',
      vehicle_type: 'car',
      license_plate: '',
      color: '',
      owner_id: null,
      trusted: true,
    });
  }, []);

  const handleSaveVehicle = useCallback(async () => {
    if (!vehicleForm.description.trim()) {
      toast.error('Description is required');
      return;
    }

    try {
      if (editingVehicle) {
        const updateData: RegisteredVehicleUpdate = {
          description: vehicleForm.description.trim(),
          vehicle_type: vehicleForm.vehicle_type,
          license_plate: vehicleForm.license_plate.trim() || null,
          color: vehicleForm.color.trim() || null,
          owner_id: vehicleForm.owner_id,
          trusted: vehicleForm.trusted,
        };
        await updateVehicle.mutateAsync({ id: editingVehicle.id, data: updateData });
        toast.success('Vehicle updated');
      } else {
        const createData: RegisteredVehicleCreate = {
          description: vehicleForm.description.trim(),
          vehicle_type: vehicleForm.vehicle_type,
          license_plate: vehicleForm.license_plate.trim() || null,
          color: vehicleForm.color.trim() || null,
          owner_id: vehicleForm.owner_id,
          trusted: vehicleForm.trusted,
        };
        await createVehicle.mutateAsync(createData);
        toast.success('Vehicle added');
      }
      handleCloseVehicleModal();
    } catch (error) {
      toast.error(editingVehicle ? 'Failed to update vehicle' : 'Failed to add vehicle', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [vehicleForm, editingVehicle, createVehicle, updateVehicle, toast, handleCloseVehicleModal]);

  const handleDeleteVehicle = useCallback(
    async (id: number) => {
      try {
        await deleteVehicle.mutateAsync(id);
        toast.success('Vehicle deleted');
        setDeletingVehicleId(null);
      } catch (error) {
        toast.error('Failed to delete vehicle', {
          description: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    },
    [deleteVehicle, toast]
  );

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div className={clsx('space-y-6', className)} data-testid="household-settings">
      {/* Household Name Section */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="household-name-section">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#76B900]/20">
              <Home className="h-5 w-5 text-[#76B900]" />
            </div>
            <div>
              {householdsLoading ? (
                <div className="h-6 w-40 animate-pulse rounded bg-gray-700" />
              ) : isEditingHouseholdName ? (
                <div className="flex items-center gap-2">
                  <TextInput
                    value={householdNameInput}
                    onChange={(e) => setHouseholdNameInput(e.target.value)}
                    placeholder="Household name"
                    className="w-60"
                    data-testid="household-name-input"
                  />
                  <Button
                    size="xs"
                    onClick={() => void handleSaveHouseholdName()}
                    disabled={updateHousehold.isPending || !householdNameInput.trim()}
                    className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
                    data-testid="household-name-save"
                  >
                    {updateHousehold.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={handleCancelEditHouseholdName}
                    disabled={updateHousehold.isPending}
                    data-testid="household-name-cancel"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <Title className="text-white">{household?.name ?? 'My Household'}</Title>
              )}
              <Text className="text-sm text-gray-400">Household Organization</Text>
            </div>
          </div>
          {!isEditingHouseholdName && !householdsLoading && (
            <Button
              size="xs"
              variant="secondary"
              onClick={handleStartEditHouseholdName}
              className="flex items-center gap-1"
              data-testid="household-name-edit"
            >
              <Edit2 className="h-3 w-3" />
              Edit
            </Button>
          )}
        </div>
      </Card>

      {/* Members Section */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="members-section">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5 text-[#76B900]" />
            <Title className="text-white">Members</Title>
            {members && members.length > 0 && (
              <Badge color="gray" size="sm">
                {members.length}
              </Badge>
            )}
          </div>
          <Button
            size="xs"
            onClick={() => handleOpenMemberModal()}
            className="flex items-center gap-1 bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
            data-testid="add-member-btn"
          >
            <Plus className="h-3 w-3" />
            Add
          </Button>
        </div>

        {membersLoading ? (
          <ListSkeleton count={2} />
        ) : membersError ? (
          <ErrorState message="Failed to load members" />
        ) : members && members.length > 0 ? (
          <div className="space-y-2" data-testid="members-list">
            {members.map((member) => (
              <div
                key={member.id}
                className="flex items-center justify-between rounded-lg border border-gray-700 bg-[#121212] p-4"
                data-testid={`member-${member.id}`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-500/20">
                    <User className="h-4 w-4 text-blue-400" />
                  </div>
                  <div>
                    <Text className="font-medium text-white">{member.name}</Text>
                    <div className="mt-1 flex items-center gap-2">
                      <RoleBadge role={member.role} />
                      <TrustBadge level={member.trusted_level} />
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => handleOpenMemberModal(member)}
                    data-testid={`edit-member-${member.id}`}
                  >
                    <Edit2 className="h-3 w-3" />
                  </Button>
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => setDeletingMemberId(member.id)}
                    className="text-red-400 hover:text-red-300"
                    data-testid={`delete-member-${member.id}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Users}
            title="No members yet"
            description="Add household members to help suppress alerts for recognized people."
            action={
              <Button
                size="xs"
                onClick={() => handleOpenMemberModal()}
                className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
              >
                <Plus className="mr-1 h-3 w-3" />
                Add Member
              </Button>
            }
          />
        )}
      </Card>

      {/* Vehicles Section */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="vehicles-section">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Car className="h-5 w-5 text-[#76B900]" />
            <Title className="text-white">Vehicles</Title>
            {vehicles && vehicles.length > 0 && (
              <Badge color="gray" size="sm">
                {vehicles.length}
              </Badge>
            )}
          </div>
          <Button
            size="xs"
            onClick={() => handleOpenVehicleModal()}
            className="flex items-center gap-1 bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
            data-testid="add-vehicle-btn"
          >
            <Plus className="h-3 w-3" />
            Add
          </Button>
        </div>

        {vehiclesLoading ? (
          <ListSkeleton count={2} />
        ) : vehiclesError ? (
          <ErrorState message="Failed to load vehicles" />
        ) : vehicles && vehicles.length > 0 ? (
          <div className="space-y-2" data-testid="vehicles-list">
            {vehicles.map((vehicle) => (
              <div
                key={vehicle.id}
                className="flex items-center justify-between rounded-lg border border-gray-700 bg-[#121212] p-4"
                data-testid={`vehicle-${vehicle.id}`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-500/20">
                    <Car className="h-4 w-4 text-amber-400" />
                  </div>
                  <div>
                    <Text className="font-medium text-white">{vehicle.description}</Text>
                    <div className="mt-1 flex items-center gap-2">
                      {vehicle.license_plate && (
                        <Badge color="gray" size="sm">
                          {vehicle.license_plate}
                        </Badge>
                      )}
                      {vehicle.trusted && (
                        <Badge color="green" size="sm">
                          Trusted
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => handleOpenVehicleModal(vehicle)}
                    data-testid={`edit-vehicle-${vehicle.id}`}
                  >
                    <Edit2 className="h-3 w-3" />
                  </Button>
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => setDeletingVehicleId(vehicle.id)}
                    className="text-red-400 hover:text-red-300"
                    data-testid={`delete-vehicle-${vehicle.id}`}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Car}
            title="No vehicles yet"
            description="Register vehicles to help suppress alerts for recognized cars."
            action={
              <Button
                size="xs"
                onClick={() => handleOpenVehicleModal()}
                className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
              >
                <Plus className="mr-1 h-3 w-3" />
                Add Vehicle
              </Button>
            }
          />
        )}
      </Card>

      {/* Properties Section */}
      <Card className="border-gray-800 bg-[#1A1A1A] shadow-lg" data-testid="properties-section">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-[#76B900]" />
            <Title className="text-white">Properties</Title>
          </div>
          <Link
            to="/settings/properties"
            className="flex items-center gap-1 rounded-lg border border-gray-700 bg-[#121212] px-3 py-2 text-sm text-gray-300 transition-colors hover:border-[#76B900] hover:text-white"
            data-testid="manage-properties-link"
          >
            Manage
            <ChevronRight className="h-4 w-4" />
          </Link>
        </div>
        <Text className="mt-2 text-sm text-gray-400">
          Organize your cameras by property and area for better management and notifications.
        </Text>
      </Card>

      {/* Member Modal */}
      <Transition appear show={memberModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseMemberModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/70" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-200"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-150"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel
                  className="w-full max-w-md rounded-xl border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl"
                  data-testid="member-modal"
                >
                  <Dialog.Title className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                    <User className="h-5 w-5 text-[#76B900]" />
                    {editingMember ? 'Edit Member' : 'Add Member'}
                  </Dialog.Title>

                  <div className="space-y-4">
                    <div>
                      {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                      <label className="mb-1 block text-sm text-gray-400">Name *</label>
                      <TextInput
                        value={memberForm.name}
                        onChange={(e) => setMemberForm((f) => ({ ...f, name: e.target.value }))}
                        placeholder="John Doe"
                        data-testid="member-name-input"
                      />
                    </div>

                    <div>
                      {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                      <label className="mb-1 block text-sm text-gray-400">Role *</label>
                      <Select
                        value={memberForm.role}
                        onValueChange={(v) => setMemberForm((f) => ({ ...f, role: v as MemberRole }))}
                        data-testid="member-role-select"
                      >
                        {MEMBER_ROLES.map((role) => (
                          <SelectItem key={role.value} value={role.value}>
                            {role.label}
                          </SelectItem>
                        ))}
                      </Select>
                    </div>

                    <div>
                      {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                      <label className="mb-1 block text-sm text-gray-400">Trust Level *</label>
                      <Select
                        value={memberForm.trusted_level}
                        onValueChange={(v) =>
                          setMemberForm((f) => ({ ...f, trusted_level: v as TrustLevel }))
                        }
                        data-testid="member-trust-select"
                      >
                        {TRUST_LEVELS.map((level) => (
                          <SelectItem key={level.value} value={level.value}>
                            {level.label} - {level.description}
                          </SelectItem>
                        ))}
                      </Select>
                    </div>

                    <div>
                      {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                      <label className="mb-1 block text-sm text-gray-400">Notes</label>
                      <TextInput
                        value={memberForm.notes}
                        onChange={(e) => setMemberForm((f) => ({ ...f, notes: e.target.value }))}
                        placeholder="Additional notes..."
                        data-testid="member-notes-input"
                      />
                    </div>
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <Button
                      variant="secondary"
                      onClick={handleCloseMemberModal}
                      disabled={createMember.isPending || updateMember.isPending}
                      data-testid="member-modal-cancel"
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() => void handleSaveMember()}
                      disabled={createMember.isPending || updateMember.isPending}
                      className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
                      data-testid="member-modal-save"
                    >
                      {createMember.isPending || updateMember.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Saving...
                        </>
                      ) : editingMember ? (
                        'Update'
                      ) : (
                        'Add'
                      )}
                    </Button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Vehicle Modal */}
      <Transition appear show={vehicleModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseVehicleModal}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/70" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-200"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-150"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel
                  className="w-full max-w-md rounded-xl border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl"
                  data-testid="vehicle-modal"
                >
                  <Dialog.Title className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                    <Car className="h-5 w-5 text-[#76B900]" />
                    {editingVehicle ? 'Edit Vehicle' : 'Add Vehicle'}
                  </Dialog.Title>

                  <div className="space-y-4">
                    <div>
                      {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                      <label className="mb-1 block text-sm text-gray-400">Description *</label>
                      <TextInput
                        value={vehicleForm.description}
                        onChange={(e) =>
                          setVehicleForm((f) => ({ ...f, description: e.target.value }))
                        }
                        placeholder="Silver Tesla Model 3"
                        data-testid="vehicle-description-input"
                      />
                    </div>

                    <div>
                      {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                      <label className="mb-1 block text-sm text-gray-400">Vehicle Type *</label>
                      <Select
                        value={vehicleForm.vehicle_type}
                        onValueChange={(v) =>
                          setVehicleForm((f) => ({ ...f, vehicle_type: v as VehicleType }))
                        }
                        data-testid="vehicle-type-select"
                      >
                        {VEHICLE_TYPES.map((type) => (
                          <SelectItem key={type.value} value={type.value}>
                            {type.label}
                          </SelectItem>
                        ))}
                      </Select>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label className="mb-1 block text-sm text-gray-400">License Plate</label>
                        <TextInput
                          value={vehicleForm.license_plate}
                          onChange={(e) =>
                            setVehicleForm((f) => ({ ...f, license_plate: e.target.value }))
                          }
                          placeholder="ABC 123"
                          data-testid="vehicle-plate-input"
                        />
                      </div>
                      <div>
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label className="mb-1 block text-sm text-gray-400">Color</label>
                        <TextInput
                          value={vehicleForm.color}
                          onChange={(e) => setVehicleForm((f) => ({ ...f, color: e.target.value }))}
                          placeholder="Silver"
                          data-testid="vehicle-color-input"
                        />
                      </div>
                    </div>

                    {members && members.length > 0 && (
                      <div>
                        {/* eslint-disable-next-line jsx-a11y/label-has-associated-control */}
                        <label className="mb-1 block text-sm text-gray-400">Owner</label>
                        <Select
                          value={vehicleForm.owner_id?.toString() ?? ''}
                          onValueChange={(v) =>
                            setVehicleForm((f) => ({ ...f, owner_id: v ? parseInt(v, 10) : null }))
                          }
                          data-testid="vehicle-owner-select"
                        >
                          <SelectItem value="">No owner assigned</SelectItem>
                          {members.map((member) => (
                            <SelectItem key={member.id} value={member.id.toString()}>
                              {member.name}
                            </SelectItem>
                          ))}
                        </Select>
                      </div>
                    )}

                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="vehicle-trusted"
                        checked={vehicleForm.trusted}
                        onChange={(e) =>
                          setVehicleForm((f) => ({ ...f, trusted: e.target.checked }))
                        }
                        className="h-4 w-4 rounded border-gray-600 bg-[#121212] text-[#76B900] focus:ring-[#76B900]"
                        data-testid="vehicle-trusted-checkbox"
                      />
                      <label htmlFor="vehicle-trusted" className="text-sm text-gray-300">
                        Trusted vehicle (suppress alerts)
                      </label>
                    </div>
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <Button
                      variant="secondary"
                      onClick={handleCloseVehicleModal}
                      disabled={createVehicle.isPending || updateVehicle.isPending}
                      data-testid="vehicle-modal-cancel"
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() => void handleSaveVehicle()}
                      disabled={createVehicle.isPending || updateVehicle.isPending}
                      className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
                      data-testid="vehicle-modal-save"
                    >
                      {createVehicle.isPending || updateVehicle.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Saving...
                        </>
                      ) : editingVehicle ? (
                        'Update'
                      ) : (
                        'Add'
                      )}
                    </Button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Delete Member Confirmation Modal */}
      <Transition appear show={deletingMemberId !== null} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setDeletingMemberId(null)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/70" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-200"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-150"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel
                  className="w-full max-w-sm rounded-xl border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl"
                  data-testid="delete-member-modal"
                >
                  <Dialog.Title className="mb-2 flex items-center gap-2 text-lg font-semibold text-white">
                    <AlertTriangle className="h-5 w-5 text-red-400" />
                    Delete Member
                  </Dialog.Title>
                  <Text className="mb-6 text-gray-400">
                    Are you sure you want to delete this member? This action cannot be undone.
                  </Text>
                  <div className="flex justify-end gap-3">
                    <Button
                      variant="secondary"
                      onClick={() => setDeletingMemberId(null)}
                      disabled={deleteMember.isPending}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() => deletingMemberId && void handleDeleteMember(deletingMemberId)}
                      disabled={deleteMember.isPending}
                      className="bg-red-600 text-white hover:bg-red-700"
                      data-testid="confirm-delete-member"
                    >
                      {deleteMember.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Deleting...
                        </>
                      ) : (
                        'Delete'
                      )}
                    </Button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Delete Vehicle Confirmation Modal */}
      <Transition appear show={deletingVehicleId !== null} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setDeletingVehicleId(null)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/70" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-200"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-150"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel
                  className="w-full max-w-sm rounded-xl border border-gray-700 bg-[#1A1A1A] p-6 shadow-xl"
                  data-testid="delete-vehicle-modal"
                >
                  <Dialog.Title className="mb-2 flex items-center gap-2 text-lg font-semibold text-white">
                    <AlertTriangle className="h-5 w-5 text-red-400" />
                    Delete Vehicle
                  </Dialog.Title>
                  <Text className="mb-6 text-gray-400">
                    Are you sure you want to delete this vehicle? This action cannot be undone.
                  </Text>
                  <div className="flex justify-end gap-3">
                    <Button
                      variant="secondary"
                      onClick={() => setDeletingVehicleId(null)}
                      disabled={deleteVehicle.isPending}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() =>
                        deletingVehicleId && void handleDeleteVehicle(deletingVehicleId)
                      }
                      disabled={deleteVehicle.isPending}
                      className="bg-red-600 text-white hover:bg-red-700"
                      data-testid="confirm-delete-vehicle"
                    >
                      {deleteVehicle.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Deleting...
                        </>
                      ) : (
                        'Delete'
                      )}
                    </Button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  );
}
