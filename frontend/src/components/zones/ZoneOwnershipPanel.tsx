/**
 * ZoneOwnershipPanel - Zone ownership and access control management
 *
 * Displays and allows editing of:
 * - Zone owner (household member with full trust)
 * - Allowed members (partial trust)
 * - Allowed vehicles (partial trust)
 * - Access schedules (cron-based time rules)
 *
 * Phase 2.2: Create ZoneOwnershipPanel component (NEM-3191)
 * Part of the Zone Intelligence System epic (NEM-3186).
 */

import { Dialog, Transition } from '@headlessui/react';
import { Card, Title, Text, Button, Badge, TextInput, Select, SelectItem } from '@tremor/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Calendar,
  Car,
  Check,
  Clock,
  Crown,
  Edit2,
  Loader2,
  Plus,
  Shield,
  Trash2,
  User,
  Users,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useState } from 'react';

import {
  useMembersQuery,
  useVehiclesQuery,
  type HouseholdMember,
  type RegisteredVehicle,
  type TrustLevel,
} from '../../hooks/useHouseholdApi';
import { useToast } from '../../hooks/useToast';
import {
  useZoneHouseholdConfig,
  type AccessSchedule,
  type ZoneHouseholdConfigCreate,
} from '../../hooks/useZoneHouseholdConfig';

// ============================================================================
// Types
// ============================================================================

export interface ZoneOwnershipPanelProps {
  /** Zone ID to manage ownership for */
  zoneId: string;
  /** Zone name for display */
  zoneName?: string;
  /** Optional className for styling */
  className?: string;
  /** Whether the panel is in edit mode */
  editable?: boolean;
  /** Compact mode for sidebar display */
  compact?: boolean;
}

interface ScheduleFormData {
  member_ids: number[];
  cron_expression: string;
  description: string;
}

// ============================================================================
// Constants
// ============================================================================

const TRUST_LEVEL_INFO: Record<
  TrustLevel | 'full_owner',
  { label: string; color: 'green' | 'yellow' | 'gray' }
> = {
  full_owner: { label: 'Owner', color: 'green' },
  full: { label: 'Full Trust', color: 'green' },
  partial: { label: 'Partial', color: 'yellow' },
  monitor: { label: 'Monitor', color: 'gray' },
};

const COMMON_SCHEDULES = [
  { label: 'Weekdays 9am-5pm', cron: '0 9-17 * * 1-5' },
  { label: 'Weekends all day', cron: '* * * * 0,6' },
  { label: 'Every day 8am-6pm', cron: '0 8-18 * * *' },
  { label: 'Mornings (6am-12pm)', cron: '0 6-12 * * *' },
  { label: 'Evenings (5pm-10pm)', cron: '0 17-22 * * *' },
];

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Loading skeleton for the panel.
 */
function PanelSkeleton({ compact }: { compact?: boolean }) {
  return (
    <div className={clsx('space-y-4', compact && 'space-y-2')}>
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 animate-pulse rounded-full bg-gray-700" />
        <div className="space-y-2">
          <div className="h-4 w-32 animate-pulse rounded bg-gray-700" />
          <div className="h-3 w-24 animate-pulse rounded bg-gray-700" />
        </div>
      </div>
      <div className="h-px bg-gray-700" />
      <div className="space-y-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <div
            key={i}
            className="flex h-12 animate-pulse items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 p-2"
          >
            <div className="h-8 w-8 rounded-full bg-gray-700" />
            <div className="h-4 w-20 rounded bg-gray-700" />
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Error state display.
 */
function ErrorState({
  message,
  onRetry,
  compact,
}: {
  message: string;
  onRetry?: () => void;
  compact?: boolean;
}) {
  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center rounded-lg border border-red-500/30 bg-red-500/5',
        compact ? 'p-4' : 'p-6'
      )}
    >
      <AlertTriangle className={clsx('text-red-400', compact ? 'mb-1 h-5 w-5' : 'mb-2 h-8 w-8')} />
      <Text className={clsx('text-red-400', compact && 'text-sm')}>{message}</Text>
      {onRetry && (
        <Button size="xs" variant="secondary" onClick={onRetry} className="mt-2">
          Retry
        </Button>
      )}
    </div>
  );
}

/**
 * Empty state when no config exists.
 */
function EmptyState({ onConfigure, compact }: { onConfigure?: () => void; compact?: boolean }) {
  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center rounded-lg border border-gray-700 bg-gray-800/30',
        compact ? 'p-4' : 'p-6'
      )}
      data-testid="empty-state"
    >
      <Shield className={clsx('text-gray-500', compact ? 'mb-2 h-6 w-6' : 'mb-3 h-8 w-8')} />
      <Text className={clsx('font-medium text-gray-300', compact && 'text-sm')}>
        No ownership configured
      </Text>
      <Text
        className={clsx('text-center text-gray-500', compact ? 'mb-3 text-xs' : 'mb-4 text-sm')}
      >
        Set an owner and allowed members for this zone.
      </Text>
      {onConfigure && (
        <Button
          size="xs"
          onClick={onConfigure}
          className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
          data-testid="configure-btn"
        >
          <Plus className="mr-1 h-3 w-3" />
          Configure
        </Button>
      )}
    </div>
  );
}

/**
 * Member avatar with name and trust badge.
 */
function MemberAvatar({
  member,
  trustLevel,
  isOwner,
  compact,
  onRemove,
}: {
  member: HouseholdMember;
  trustLevel?: TrustLevel;
  isOwner?: boolean;
  compact?: boolean;
  onRemove?: () => void;
}) {
  const info = isOwner
    ? TRUST_LEVEL_INFO.full_owner
    : trustLevel
      ? TRUST_LEVEL_INFO[trustLevel]
      : TRUST_LEVEL_INFO.partial;

  return (
    <div
      className={clsx(
        'group flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 transition-colors hover:border-gray-600',
        compact ? 'p-2' : 'p-3'
      )}
      data-testid={`member-${member.id}`}
    >
      <div
        className={clsx(
          'flex items-center justify-center rounded-full',
          isOwner ? 'bg-[#76B900]/20' : 'bg-blue-500/20',
          compact ? 'h-7 w-7' : 'h-9 w-9'
        )}
      >
        {isOwner ? (
          <Crown className={clsx('text-[#76B900]', compact ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
        ) : (
          <User className={clsx('text-blue-400', compact ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <Text className={clsx('truncate font-medium text-white', compact && 'text-sm')}>
          {member.name}
        </Text>
        {!compact && (
          <Badge color={info.color} size="xs">
            {info.label}
          </Badge>
        )}
      </div>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="rounded p-1 text-gray-500 opacity-0 transition-opacity hover:bg-gray-700 hover:text-red-400 group-hover:opacity-100"
          title="Remove"
          data-testid={`remove-member-${member.id}`}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

/**
 * Vehicle card with trust badge.
 */
function VehicleCard({
  vehicle,
  compact,
  onRemove,
}: {
  vehicle: RegisteredVehicle;
  compact?: boolean;
  onRemove?: () => void;
}) {
  return (
    <div
      className={clsx(
        'group flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800/50 transition-colors hover:border-gray-600',
        compact ? 'p-2' : 'p-3'
      )}
      data-testid={`vehicle-${vehicle.id}`}
    >
      <div
        className={clsx(
          'flex items-center justify-center rounded-full bg-amber-500/20',
          compact ? 'h-7 w-7' : 'h-9 w-9'
        )}
      >
        <Car className={clsx('text-amber-400', compact ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
      </div>
      <div className="min-w-0 flex-1">
        <Text className={clsx('truncate font-medium text-white', compact && 'text-sm')}>
          {vehicle.description}
        </Text>
        {!compact && vehicle.license_plate && (
          <Badge color="gray" size="xs">
            {vehicle.license_plate}
          </Badge>
        )}
      </div>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="rounded p-1 text-gray-500 opacity-0 transition-opacity hover:bg-gray-700 hover:text-red-400 group-hover:opacity-100"
          title="Remove"
          data-testid={`remove-vehicle-${vehicle.id}`}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

/**
 * Access schedule display.
 */
function ScheduleCard({
  schedule,
  members,
  compact,
  onEdit,
  onRemove,
}: {
  schedule: AccessSchedule;
  members: HouseholdMember[];
  compact?: boolean;
  onEdit?: () => void;
  onRemove?: () => void;
}) {
  const scheduledMembers = members.filter((m) => schedule.member_ids.includes(m.id));

  return (
    <div
      className={clsx(
        'group rounded-lg border border-gray-700 bg-gray-800/50 transition-colors hover:border-gray-600',
        compact ? 'p-2' : 'p-3'
      )}
      data-testid="schedule-card"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Clock className={clsx('text-purple-400', compact ? 'h-4 w-4' : 'h-5 w-5')} />
          <div>
            <Text className={clsx('font-medium text-white', compact && 'text-sm')}>
              {schedule.description || 'Scheduled Access'}
            </Text>
            <Text className={clsx('font-mono text-gray-400', compact ? 'text-xs' : 'text-sm')}>
              {schedule.cron_expression}
            </Text>
          </div>
        </div>
        {(onEdit || onRemove) && (
          <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            {onEdit && (
              <button
                type="button"
                onClick={onEdit}
                className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-white"
                title="Edit"
                data-testid="edit-schedule"
              >
                <Edit2 className="h-3.5 w-3.5" />
              </button>
            )}
            {onRemove && (
              <button
                type="button"
                onClick={onRemove}
                className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-red-400"
                title="Remove"
                data-testid="remove-schedule"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        )}
      </div>
      {scheduledMembers.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {scheduledMembers.map((member) => (
            <Badge key={member.id} color="blue" size="xs">
              {member.name}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneOwnershipPanel component for managing zone access control.
 *
 * Features:
 * - Display zone owner with crown icon
 * - List of allowed members with trust levels
 * - List of allowed vehicles
 * - Access schedules with cron expressions
 * - Edit mode for modifying configuration
 * - Compact mode for sidebar display
 */
export default function ZoneOwnershipPanel({
  zoneId,
  zoneName,
  className,
  editable = false,
  compact = false,
}: ZoneOwnershipPanelProps) {
  const toast = useToast();

  // API hooks
  const { config, isLoading, isError, error, refetch, upsertConfig, patchConfig, deleteConfig } =
    useZoneHouseholdConfig(zoneId);

  const { data: members = [], isLoading: membersLoading } = useMembersQuery();
  const { data: vehicles = [], isLoading: vehiclesLoading } = useVehiclesQuery();

  // Modal states
  const [isConfigureModalOpen, setIsConfigureModalOpen] = useState(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [editingScheduleIndex, setEditingScheduleIndex] = useState<number | null>(null);
  const [scheduleForm, setScheduleForm] = useState<ScheduleFormData>({
    member_ids: [],
    cron_expression: '',
    description: '',
  });

  // Configure modal form state
  const [configForm, setConfigForm] = useState<ZoneHouseholdConfigCreate>({
    owner_id: null,
    allowed_member_ids: [],
    allowed_vehicle_ids: [],
    access_schedules: [],
  });

  // Get referenced entities
  const owner = config?.owner_id ? members.find((m) => m.id === config.owner_id) : null;
  const allowedMembers = members.filter((m) => config?.allowed_member_ids?.includes(m.id));
  const allowedVehicles = vehicles.filter((v) => config?.allowed_vehicle_ids?.includes(v.id));

  // ============================================================================
  // Handlers
  // ============================================================================

  const handleOpenConfigureModal = useCallback(() => {
    setConfigForm({
      owner_id: config?.owner_id ?? null,
      allowed_member_ids: config?.allowed_member_ids ?? [],
      allowed_vehicle_ids: config?.allowed_vehicle_ids ?? [],
      access_schedules: config?.access_schedules ?? [],
    });
    setIsConfigureModalOpen(true);
  }, [config]);

  const handleCloseConfigureModal = useCallback(() => {
    setIsConfigureModalOpen(false);
  }, []);

  const handleSaveConfig = useCallback(async () => {
    try {
      await upsertConfig.mutateAsync({ zoneId, data: configForm });
      toast.success('Zone ownership updated');
      handleCloseConfigureModal();
    } catch (err) {
      toast.error('Failed to update zone ownership', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, [zoneId, configForm, upsertConfig, toast, handleCloseConfigureModal]);

  const handleRemoveMember = useCallback(
    async (memberId: number) => {
      if (!config) return;
      const newMemberIds = config.allowed_member_ids.filter((id) => id !== memberId);
      try {
        await patchConfig.mutateAsync({
          zoneId,
          data: { allowed_member_ids: newMemberIds },
        });
        toast.success('Member removed from zone');
      } catch (err) {
        toast.error('Failed to remove member', {
          description: err instanceof Error ? err.message : 'Unknown error',
        });
      }
    },
    [zoneId, config, patchConfig, toast]
  );

  const handleRemoveVehicle = useCallback(
    async (vehicleId: number) => {
      if (!config) return;
      const newVehicleIds = config.allowed_vehicle_ids.filter((id) => id !== vehicleId);
      try {
        await patchConfig.mutateAsync({
          zoneId,
          data: { allowed_vehicle_ids: newVehicleIds },
        });
        toast.success('Vehicle removed from zone');
      } catch (err) {
        toast.error('Failed to remove vehicle', {
          description: err instanceof Error ? err.message : 'Unknown error',
        });
      }
    },
    [zoneId, config, patchConfig, toast]
  );

  const handleOpenScheduleModal = useCallback(
    (index?: number) => {
      if (index !== undefined && config?.access_schedules[index]) {
        const schedule = config.access_schedules[index];
        setScheduleForm({
          member_ids: schedule.member_ids,
          cron_expression: schedule.cron_expression,
          description: schedule.description ?? '',
        });
        setEditingScheduleIndex(index);
      } else {
        setScheduleForm({
          member_ids: [],
          cron_expression: '',
          description: '',
        });
        setEditingScheduleIndex(null);
      }
      setIsScheduleModalOpen(true);
    },
    [config]
  );

  const handleCloseScheduleModal = useCallback(() => {
    setIsScheduleModalOpen(false);
    setEditingScheduleIndex(null);
    setScheduleForm({
      member_ids: [],
      cron_expression: '',
      description: '',
    });
  }, []);

  const handleSaveSchedule = useCallback(async () => {
    if (!scheduleForm.member_ids.length || !scheduleForm.cron_expression) {
      toast.error('Please select members and enter a schedule');
      return;
    }

    const newSchedule: AccessSchedule = {
      member_ids: scheduleForm.member_ids,
      cron_expression: scheduleForm.cron_expression,
      description: scheduleForm.description || null,
    };

    let newSchedules: AccessSchedule[];
    if (editingScheduleIndex !== null && config) {
      newSchedules = [...config.access_schedules];
      newSchedules[editingScheduleIndex] = newSchedule;
    } else {
      newSchedules = [...(config?.access_schedules ?? []), newSchedule];
    }

    try {
      await patchConfig.mutateAsync({
        zoneId,
        data: { access_schedules: newSchedules },
      });
      toast.success(editingScheduleIndex !== null ? 'Schedule updated' : 'Schedule added');
      handleCloseScheduleModal();
    } catch (err) {
      toast.error('Failed to save schedule', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, [
    zoneId,
    scheduleForm,
    editingScheduleIndex,
    config,
    patchConfig,
    toast,
    handleCloseScheduleModal,
  ]);

  const handleRemoveSchedule = useCallback(
    async (index: number) => {
      if (!config) return;
      const newSchedules = config.access_schedules.filter((_, i) => i !== index);
      try {
        await patchConfig.mutateAsync({
          zoneId,
          data: { access_schedules: newSchedules },
        });
        toast.success('Schedule removed');
      } catch (err) {
        toast.error('Failed to remove schedule', {
          description: err instanceof Error ? err.message : 'Unknown error',
        });
      }
    },
    [zoneId, config, patchConfig, toast]
  );

  const handleClearOwner = useCallback(async () => {
    if (!config) return;
    try {
      await patchConfig.mutateAsync({
        zoneId,
        data: { owner_id: null },
      });
      toast.success('Owner removed');
    } catch (err) {
      toast.error('Failed to remove owner', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, [zoneId, config, patchConfig, toast]);

  const handleDeleteConfig = useCallback(async () => {
    try {
      await deleteConfig.mutateAsync(zoneId);
      toast.success('Zone ownership configuration deleted');
    } catch (err) {
      toast.error('Failed to delete configuration', {
        description: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, [zoneId, deleteConfig, toast]);

  // ============================================================================
  // Render
  // ============================================================================

  if (isLoading || membersLoading || vehiclesLoading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="zone-ownership-panel"
      >
        <PanelSkeleton compact={compact} />
      </Card>
    );
  }

  if (isError) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="zone-ownership-panel"
      >
        <ErrorState
          message={error?.message ?? 'Failed to load ownership config'}
          onRetry={() => void refetch()}
          compact={compact}
        />
      </Card>
    );
  }

  const hasNoConfig = !config;

  return (
    <>
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="zone-ownership-panel"
      >
        {/* Header */}
        <div className={clsx('flex items-center justify-between', compact ? 'mb-3' : 'mb-4')}>
          <div className="flex items-center gap-2">
            <Shield className={clsx('text-[#76B900]', compact ? 'h-4 w-4' : 'h-5 w-5')} />
            <Title className={clsx('text-white', compact && 'text-sm')}>
              {zoneName ? `${zoneName} Access` : 'Zone Access'}
            </Title>
          </div>
          {editable && config && (
            <Button
              size="xs"
              variant="secondary"
              onClick={handleOpenConfigureModal}
              className="flex items-center gap-1"
              data-testid="edit-config-btn"
            >
              <Edit2 className="h-3 w-3" />
              {!compact && 'Edit'}
            </Button>
          )}
        </div>

        {hasNoConfig ? (
          <EmptyState
            onConfigure={editable ? handleOpenConfigureModal : undefined}
            compact={compact}
          />
        ) : (
          <div className={clsx('space-y-4', compact && 'space-y-3')}>
            {/* Owner Section */}
            <div>
              <div className="mb-2 flex items-center gap-1">
                <Crown className={clsx('text-[#76B900]', compact ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
                <Text className={clsx('font-medium text-gray-300', compact && 'text-sm')}>
                  Owner
                </Text>
              </div>
              {owner ? (
                <MemberAvatar
                  member={owner}
                  isOwner
                  compact={compact}
                  onRemove={editable ? () => void handleClearOwner() : undefined}
                />
              ) : (
                <Text className={clsx('italic text-gray-500', compact && 'text-sm')}>
                  No owner assigned
                </Text>
              )}
            </div>

            {/* Allowed Members Section */}
            {(allowedMembers.length > 0 || editable) && (
              <div>
                <div className="mb-2 flex items-center gap-1">
                  <Users className={clsx('text-blue-400', compact ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
                  <Text className={clsx('font-medium text-gray-300', compact && 'text-sm')}>
                    Allowed Members
                  </Text>
                  {allowedMembers.length > 0 && (
                    <Badge color="gray" size="xs">
                      {allowedMembers.length}
                    </Badge>
                  )}
                </div>
                {allowedMembers.length > 0 ? (
                  <div className="space-y-2">
                    {allowedMembers.map((member) => (
                      <MemberAvatar
                        key={member.id}
                        member={member}
                        trustLevel={member.trusted_level}
                        compact={compact}
                        onRemove={editable ? () => void handleRemoveMember(member.id) : undefined}
                      />
                    ))}
                  </div>
                ) : (
                  <Text className={clsx('italic text-gray-500', compact && 'text-sm')}>
                    No additional members allowed
                  </Text>
                )}
              </div>
            )}

            {/* Allowed Vehicles Section */}
            {(allowedVehicles.length > 0 || editable) && (
              <div>
                <div className="mb-2 flex items-center gap-1">
                  <Car className={clsx('text-amber-400', compact ? 'h-3.5 w-3.5' : 'h-4 w-4')} />
                  <Text className={clsx('font-medium text-gray-300', compact && 'text-sm')}>
                    Allowed Vehicles
                  </Text>
                  {allowedVehicles.length > 0 && (
                    <Badge color="gray" size="xs">
                      {allowedVehicles.length}
                    </Badge>
                  )}
                </div>
                {allowedVehicles.length > 0 ? (
                  <div className="space-y-2">
                    {allowedVehicles.map((vehicle) => (
                      <VehicleCard
                        key={vehicle.id}
                        vehicle={vehicle}
                        compact={compact}
                        onRemove={editable ? () => void handleRemoveVehicle(vehicle.id) : undefined}
                      />
                    ))}
                  </div>
                ) : (
                  <Text className={clsx('italic text-gray-500', compact && 'text-sm')}>
                    No vehicles allowed
                  </Text>
                )}
              </div>
            )}

            {/* Access Schedules Section */}
            {(config.access_schedules.length > 0 || editable) && (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <div className="flex items-center gap-1">
                    <Calendar
                      className={clsx('text-purple-400', compact ? 'h-3.5 w-3.5' : 'h-4 w-4')}
                    />
                    <Text className={clsx('font-medium text-gray-300', compact && 'text-sm')}>
                      Access Schedules
                    </Text>
                    {config.access_schedules.length > 0 && (
                      <Badge color="gray" size="xs">
                        {config.access_schedules.length}
                      </Badge>
                    )}
                  </div>
                  {editable && (
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => handleOpenScheduleModal()}
                      className="flex items-center gap-1"
                      data-testid="add-schedule-btn"
                    >
                      <Plus className="h-3 w-3" />
                      {!compact && 'Add'}
                    </Button>
                  )}
                </div>
                {config.access_schedules.length > 0 ? (
                  <div className="space-y-2">
                    {config.access_schedules.map((schedule, index) => (
                      <ScheduleCard
                        key={index}
                        schedule={schedule}
                        members={members}
                        compact={compact}
                        onEdit={editable ? () => handleOpenScheduleModal(index) : undefined}
                        onRemove={editable ? () => void handleRemoveSchedule(index) : undefined}
                      />
                    ))}
                  </div>
                ) : (
                  <Text className={clsx('italic text-gray-500', compact && 'text-sm')}>
                    No scheduled access rules
                  </Text>
                )}
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Configure Modal */}
      <Transition appear show={isConfigureModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseConfigureModal}>
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
                  data-testid="configure-modal"
                >
                  <Dialog.Title className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                    <Shield className="h-5 w-5 text-[#76B900]" />
                    Configure Zone Access
                  </Dialog.Title>

                  <div className="space-y-4">
                    {/* Owner Selection */}
                    <div>
                      <span className="mb-1 block text-sm text-gray-400">Zone Owner</span>
                      <Select
                        value={configForm.owner_id?.toString() ?? ''}
                        onValueChange={(v) =>
                          setConfigForm((f) => ({
                            ...f,
                            owner_id: v ? parseInt(v, 10) : null,
                          }))
                        }
                        data-testid="owner-select"
                      >
                        <SelectItem value="">No owner</SelectItem>
                        {members.map((member) => (
                          <SelectItem key={member.id} value={member.id.toString()}>
                            {member.name}
                          </SelectItem>
                        ))}
                      </Select>
                      <Text className="mt-1 text-xs text-gray-500">
                        The owner has full trust and never triggers alerts.
                      </Text>
                    </div>

                    {/* Allowed Members Selection */}
                    <div>
                      <span className="mb-1 block text-sm text-gray-400">Allowed Members</span>
                      <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-gray-700 bg-[#121212] p-2">
                        {members.map((member) => (
                          <label
                            key={member.id}
                            className="flex items-center gap-2 rounded p-1 hover:bg-gray-800"
                          >
                            <input
                              type="checkbox"
                              checked={configForm.allowed_member_ids?.includes(member.id) ?? false}
                              onChange={(e) => {
                                setConfigForm((f) => ({
                                  ...f,
                                  allowed_member_ids: e.target.checked
                                    ? [...(f.allowed_member_ids ?? []), member.id]
                                    : (f.allowed_member_ids ?? []).filter((id) => id !== member.id),
                                }));
                              }}
                              className="h-4 w-4 rounded border-gray-600 bg-[#121212] text-[#76B900] focus:ring-[#76B900]"
                              data-testid={`member-checkbox-${member.id}`}
                            />
                            <span className="text-sm text-gray-300">{member.name}</span>
                          </label>
                        ))}
                        {members.length === 0 && (
                          <Text className="py-2 text-center text-sm text-gray-500">
                            No household members available
                          </Text>
                        )}
                      </div>
                    </div>

                    {/* Allowed Vehicles Selection */}
                    <div>
                      <span className="mb-1 block text-sm text-gray-400">Allowed Vehicles</span>
                      <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-gray-700 bg-[#121212] p-2">
                        {vehicles.map((vehicle) => (
                          <label
                            key={vehicle.id}
                            className="flex items-center gap-2 rounded p-1 hover:bg-gray-800"
                          >
                            <input
                              type="checkbox"
                              checked={
                                configForm.allowed_vehicle_ids?.includes(vehicle.id) ?? false
                              }
                              onChange={(e) => {
                                setConfigForm((f) => ({
                                  ...f,
                                  allowed_vehicle_ids: e.target.checked
                                    ? [...(f.allowed_vehicle_ids ?? []), vehicle.id]
                                    : (f.allowed_vehicle_ids ?? []).filter(
                                        (id) => id !== vehicle.id
                                      ),
                                }));
                              }}
                              className="h-4 w-4 rounded border-gray-600 bg-[#121212] text-[#76B900] focus:ring-[#76B900]"
                              data-testid={`vehicle-checkbox-${vehicle.id}`}
                            />
                            <span className="text-sm text-gray-300">{vehicle.description}</span>
                          </label>
                        ))}
                        {vehicles.length === 0 && (
                          <Text className="py-2 text-center text-sm text-gray-500">
                            No registered vehicles available
                          </Text>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="mt-6 flex justify-between">
                    {config && (
                      <Button
                        variant="secondary"
                        onClick={() => {
                          handleCloseConfigureModal();
                          void handleDeleteConfig();
                        }}
                        className="text-red-400 hover:text-red-300"
                        data-testid="delete-config-btn"
                      >
                        <Trash2 className="mr-1 h-4 w-4" />
                        Delete
                      </Button>
                    )}
                    <div className="flex gap-3">
                      <Button
                        variant="secondary"
                        onClick={handleCloseConfigureModal}
                        disabled={upsertConfig.isPending}
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={() => void handleSaveConfig()}
                        disabled={upsertConfig.isPending}
                        className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
                        data-testid="save-config-btn"
                      >
                        {upsertConfig.isPending ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          <>
                            <Check className="mr-1 h-4 w-4" />
                            Save
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Schedule Modal */}
      <Transition appear show={isScheduleModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={handleCloseScheduleModal}>
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
                  data-testid="schedule-modal"
                >
                  <Dialog.Title className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                    <Clock className="h-5 w-5 text-purple-400" />
                    {editingScheduleIndex !== null ? 'Edit Schedule' : 'Add Schedule'}
                  </Dialog.Title>

                  <div className="space-y-4">
                    {/* Description */}
                    <div>
                      <span className="mb-1 block text-sm text-gray-400">Description</span>
                      <TextInput
                        value={scheduleForm.description}
                        onChange={(e) =>
                          setScheduleForm((f) => ({ ...f, description: e.target.value }))
                        }
                        placeholder="e.g., Business hours access"
                        data-testid="schedule-description-input"
                      />
                    </div>

                    {/* Cron Expression */}
                    <div>
                      <span className="mb-1 block text-sm text-gray-400">Schedule (Cron)</span>
                      <TextInput
                        value={scheduleForm.cron_expression}
                        onChange={(e) =>
                          setScheduleForm((f) => ({ ...f, cron_expression: e.target.value }))
                        }
                        placeholder="0 9-17 * * 1-5"
                        className="font-mono"
                        data-testid="schedule-cron-input"
                      />
                      <div className="mt-2 flex flex-wrap gap-1">
                        {COMMON_SCHEDULES.map((preset) => (
                          <button
                            key={preset.cron}
                            type="button"
                            onClick={() =>
                              setScheduleForm((f) => ({
                                ...f,
                                cron_expression: preset.cron,
                                description: f.description || preset.label,
                              }))
                            }
                            className="rounded-full border border-gray-700 bg-gray-800/50 px-2 py-0.5 text-xs text-gray-400 transition-colors hover:border-[#76B900] hover:text-white"
                          >
                            {preset.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Members Selection */}
                    <div>
                      <span className="mb-1 block text-sm text-gray-400">Apply to Members</span>
                      <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-gray-700 bg-[#121212] p-2">
                        {members.map((member) => (
                          <label
                            key={member.id}
                            className="flex items-center gap-2 rounded p-1 hover:bg-gray-800"
                          >
                            <input
                              type="checkbox"
                              checked={scheduleForm.member_ids.includes(member.id)}
                              onChange={(e) => {
                                setScheduleForm((f) => ({
                                  ...f,
                                  member_ids: e.target.checked
                                    ? [...f.member_ids, member.id]
                                    : f.member_ids.filter((id) => id !== member.id),
                                }));
                              }}
                              className="h-4 w-4 rounded border-gray-600 bg-[#121212] text-[#76B900] focus:ring-[#76B900]"
                              data-testid={`schedule-member-checkbox-${member.id}`}
                            />
                            <span className="text-sm text-gray-300">{member.name}</span>
                          </label>
                        ))}
                        {members.length === 0 && (
                          <Text className="py-2 text-center text-sm text-gray-500">
                            No household members available
                          </Text>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="mt-6 flex justify-end gap-3">
                    <Button
                      variant="secondary"
                      onClick={handleCloseScheduleModal}
                      disabled={patchConfig.isPending}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() => void handleSaveSchedule()}
                      disabled={
                        patchConfig.isPending ||
                        !scheduleForm.member_ids.length ||
                        !scheduleForm.cron_expression
                      }
                      className="bg-[#76B900] text-gray-950 hover:bg-[#5c8f00]"
                      data-testid="save-schedule-btn"
                    >
                      {patchConfig.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Check className="mr-1 h-4 w-4" />
                          Save
                        </>
                      )}
                    </Button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </>
  );
}
