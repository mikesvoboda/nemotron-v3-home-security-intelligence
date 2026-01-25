/**
 * ZoneAccessSettings - Zone-based access control configuration UI
 *
 * Provides a complete interface for managing zone-household access control:
 * - Zone selector dropdown
 * - Owner assignment
 * - Member multi-select for allowed_member_ids
 * - Vehicle multi-select for allowed_vehicle_ids
 * - Access schedule editor
 *
 * Part of NEM-3608: Zone-Household Access Control UI
 *
 * @module components/settings/ZoneAccessSettings
 */

import { Dialog, Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import {
  AlertTriangle,
  Car,
  Check,
  ChevronDown,
  Loader2,
  MapPin,
  Shield,
  User,
  Users,
  X,
} from 'lucide-react';
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';

import AccessScheduleEditor from './AccessScheduleEditor';
import { ErrorState } from '../common';
import { useHouseholdApi, type HouseholdMember, type RegisteredVehicle } from '../../hooks/useHouseholdApi';
import { useToast } from '../../hooks/useToast';
import {
  useZoneHouseholdConfig,
  type ZoneHouseholdConfigCreate,
} from '../../hooks/useZoneHouseholdConfig';

import type { Zone } from '../../services/api';

// ============================================================================
// Types
// ============================================================================

export interface ZoneAccessSettingsProps {
  /** List of available zones to configure */
  zones: Zone[];
  /** Whether zones are loading */
  zonesLoading?: boolean;
  /** Zone loading error message */
  zonesError?: string | null;
  /** Callback to retry loading zones */
  onRetryZones?: () => void;
  /** Optional className for styling */
  className?: string;
}

interface SelectedEntities {
  ownerId: number | null;
  memberIds: number[];
  vehicleIds: number[];
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Loading skeleton for the zone access settings.
 */
function LoadingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-10 w-full rounded-lg bg-gray-700" />
      <div className="h-24 w-full rounded-lg bg-gray-700" />
      <div className="h-24 w-full rounded-lg bg-gray-700" />
    </div>
  );
}

/**
 * Empty state for when no zones are available.
 */
function EmptyZonesState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-gray-700 bg-[#121212] p-8">
      <MapPin className="mb-3 h-10 w-10 text-gray-500" />
      <p className="mb-1 font-medium text-gray-300">No Zones Available</p>
      <p className="text-center text-sm text-gray-500">
        Create zones on your cameras to configure access control.
      </p>
    </div>
  );
}

/**
 * Multi-select chip for members or vehicles.
 */
function SelectionChip({
  label,
  selected,
  onClick,
  disabled,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm transition-colors',
        selected
          ? 'bg-[#76B900] text-gray-900'
          : 'bg-gray-700 text-gray-300 hover:bg-gray-600',
        disabled && 'cursor-not-allowed opacity-50'
      )}
    >
      {selected && <Check className="h-3 w-3" />}
      {label}
    </button>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZoneAccessSettings component for managing zone-based access control.
 *
 * Features:
 * - Zone selector dropdown
 * - Owner assignment (single select)
 * - Member access control (multi-select)
 * - Vehicle access control (multi-select)
 * - Access schedules (with simplified CRON editor)
 */
export default function ZoneAccessSettings({
  zones,
  zonesLoading = false,
  zonesError = null,
  onRetryZones,
  className,
}: ZoneAccessSettingsProps) {
  const toast = useToast();

  // Selected zone state
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [isZoneDropdownOpen, setIsZoneDropdownOpen] = useState(false);

  // Confirmation modal state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Household data
  const {
    members,
    membersLoading,
    membersError,
    refetchMembers,
    vehicles,
    vehiclesLoading,
    vehiclesError,
    refetchVehicles,
  } = useHouseholdApi();

  // Zone household config
  const zoneConfig = useZoneHouseholdConfig(selectedZoneId ?? '');

  // Local form state
  const [localConfig, setLocalConfig] = useState<SelectedEntities>({
    ownerId: null,
    memberIds: [],
    vehicleIds: [],
  });
  const [localSchedules, setLocalSchedules] = useState<
    { member_ids: number[]; cron_expression: string; description?: string | null }[]
  >([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Get selected zone
  const selectedZone = useMemo(
    () => zones.find((z) => z.id === selectedZoneId),
    [zones, selectedZoneId]
  );

  // Sync local state with fetched config
  useEffect(() => {
    if (zoneConfig.config) {
      setLocalConfig({
        ownerId: zoneConfig.config.owner_id,
        memberIds: zoneConfig.config.allowed_member_ids ?? [],
        vehicleIds: zoneConfig.config.allowed_vehicle_ids ?? [],
      });
      setLocalSchedules(zoneConfig.config.access_schedules ?? []);
      setHasUnsavedChanges(false);
    } else if (!zoneConfig.isLoading && selectedZoneId) {
      // Reset to defaults when no config exists
      setLocalConfig({ ownerId: null, memberIds: [], vehicleIds: [] });
      setLocalSchedules([]);
      setHasUnsavedChanges(false);
    }
  }, [zoneConfig.config, zoneConfig.isLoading, selectedZoneId]);

  // Handlers
  const handleZoneSelect = useCallback((zoneId: string) => {
    setSelectedZoneId(zoneId);
    setIsZoneDropdownOpen(false);
    setHasUnsavedChanges(false);
  }, []);

  const handleOwnerChange = useCallback((memberId: number | null) => {
    setLocalConfig((prev) => ({ ...prev, ownerId: memberId }));
    setHasUnsavedChanges(true);
  }, []);

  const handleMemberToggle = useCallback((memberId: number) => {
    setLocalConfig((prev) => ({
      ...prev,
      memberIds: prev.memberIds.includes(memberId)
        ? prev.memberIds.filter((id) => id !== memberId)
        : [...prev.memberIds, memberId],
    }));
    setHasUnsavedChanges(true);
  }, []);

  const handleVehicleToggle = useCallback((vehicleId: number) => {
    setLocalConfig((prev) => ({
      ...prev,
      vehicleIds: prev.vehicleIds.includes(vehicleId)
        ? prev.vehicleIds.filter((id) => id !== vehicleId)
        : [...prev.vehicleIds, vehicleId],
    }));
    setHasUnsavedChanges(true);
  }, []);

  const handleSchedulesChange = useCallback(
    (schedules: { member_ids: number[]; cron_expression: string; description?: string | null }[]) => {
      setLocalSchedules(schedules);
      setHasUnsavedChanges(true);
    },
    []
  );

  const handleSave = useCallback(async () => {
    if (!selectedZoneId) return;

    const configData: ZoneHouseholdConfigCreate = {
      owner_id: localConfig.ownerId,
      allowed_member_ids: localConfig.memberIds,
      allowed_vehicle_ids: localConfig.vehicleIds,
      access_schedules: localSchedules,
    };

    try {
      await zoneConfig.upsertConfig.mutateAsync({
        zoneId: selectedZoneId,
        data: configData,
      });
      toast.success('Access settings saved');
      setHasUnsavedChanges(false);
    } catch (error) {
      toast.error('Failed to save access settings', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [selectedZoneId, localConfig, localSchedules, zoneConfig.upsertConfig, toast]);

  const handleClearConfig = useCallback(async () => {
    if (!selectedZoneId) return;

    try {
      await zoneConfig.clearConfig();
      toast.success('Access settings cleared');
      setShowDeleteConfirm(false);
      setHasUnsavedChanges(false);
    } catch (error) {
      toast.error('Failed to clear access settings', {
        description: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [selectedZoneId, zoneConfig, toast]);

  const handleReset = useCallback(() => {
    if (zoneConfig.config) {
      setLocalConfig({
        ownerId: zoneConfig.config.owner_id,
        memberIds: zoneConfig.config.allowed_member_ids ?? [],
        vehicleIds: zoneConfig.config.allowed_vehicle_ids ?? [],
      });
      setLocalSchedules(zoneConfig.config.access_schedules ?? []);
    } else {
      setLocalConfig({ ownerId: null, memberIds: [], vehicleIds: [] });
      setLocalSchedules([]);
    }
    setHasUnsavedChanges(false);
  }, [zoneConfig.config]);

  // Loading states
  const isLoading = zonesLoading || membersLoading || vehiclesLoading;
  const isSaving = zoneConfig.upsertConfig.isPending || zoneConfig.deleteConfig.isPending;

  // Error handling
  if (zonesError) {
    return (
      <div className={className}>
        <ErrorState
          title="Failed to load zones"
          message={zonesError}
          onRetry={onRetryZones}
          variant="compact"
        />
      </div>
    );
  }

  if (membersError || vehiclesError) {
    const errorMsg = membersError || vehiclesError;
    return (
      <div className={className}>
        <ErrorState
          title="Failed to load household data"
          message={errorMsg ?? 'Unknown error'}
          onRetry={() => {
            if (membersError) void refetchMembers();
            if (vehiclesError) void refetchVehicles();
          }}
          variant="compact"
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className={className}>
        <LoadingSkeleton />
      </div>
    );
  }

  if (zones.length === 0) {
    return (
      <div className={className}>
        <EmptyZonesState />
      </div>
    );
  }

  return (
    <div className={clsx('space-y-6', className)} data-testid="zone-access-settings">
      {/* Zone Selector */}
      <div className="relative">
        <label className="mb-2 block text-sm font-medium text-gray-300">
          Select Zone
        </label>
        <button
          type="button"
          onClick={() => setIsZoneDropdownOpen(!isZoneDropdownOpen)}
          className="flex w-full items-center justify-between rounded-lg border border-gray-700 bg-[#121212] px-4 py-3 text-left transition-colors hover:border-gray-600"
          data-testid="zone-selector"
        >
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-[#76B900]" />
            <span className="text-white">
              {selectedZone?.name ?? 'Select a zone...'}
            </span>
          </div>
          <ChevronDown
            className={clsx(
              'h-4 w-4 text-gray-400 transition-transform',
              isZoneDropdownOpen && 'rotate-180'
            )}
          />
        </button>

        {/* Dropdown */}
        {isZoneDropdownOpen && (
          <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-700 bg-[#1A1A1A] py-1 shadow-xl">
            {zones.map((zone) => (
              <button
                key={zone.id}
                type="button"
                onClick={() => handleZoneSelect(zone.id)}
                className={clsx(
                  'flex w-full items-center gap-2 px-4 py-2 text-left transition-colors hover:bg-gray-700',
                  zone.id === selectedZoneId && 'bg-gray-700'
                )}
              >
                <MapPin className="h-4 w-4 text-gray-400" />
                <span className="text-white">{zone.name}</span>
                {zone.id === selectedZoneId && (
                  <Check className="ml-auto h-4 w-4 text-[#76B900]" />
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Configuration Panel (shown when zone is selected) */}
      {selectedZoneId && (
        <>
          {/* Loading state for zone config */}
          {zoneConfig.isLoading ? (
            <LoadingSkeleton />
          ) : zoneConfig.isError ? (
            <ErrorState
              title="Failed to load zone configuration"
              message={zoneConfig.error?.message ?? 'Unknown error'}
              onRetry={() => void zoneConfig.refetch()}
              variant="compact"
            />
          ) : (
            <>
              {/* Owner Assignment */}
              <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Shield className="h-5 w-5 text-[#76B900]" />
                  <h3 className="font-semibold text-white">Zone Owner</h3>
                </div>
                <p className="mb-3 text-sm text-gray-400">
                  The owner has full access and can manage this zone&apos;s settings.
                </p>
                <div className="flex flex-wrap gap-2">
                  <SelectionChip
                    label="No Owner"
                    selected={localConfig.ownerId === null}
                    onClick={() => handleOwnerChange(null)}
                    disabled={isSaving}
                  />
                  {(members ?? []).map((member: HouseholdMember) => (
                    <SelectionChip
                      key={member.id}
                      label={member.name}
                      selected={localConfig.ownerId === member.id}
                      onClick={() => handleOwnerChange(member.id)}
                      disabled={isSaving}
                    />
                  ))}
                </div>
              </div>

              {/* Allowed Members */}
              <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Users className="h-5 w-5 text-[#76B900]" />
                  <h3 className="font-semibold text-white">Allowed Members</h3>
                </div>
                <p className="mb-3 text-sm text-gray-400">
                  Members who have access to this zone (trust levels apply).
                </p>
                {(members ?? []).length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No household members configured. Add members in Household Settings.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {(members ?? []).map((member: HouseholdMember) => (
                      <SelectionChip
                        key={member.id}
                        label={member.name}
                        selected={localConfig.memberIds.includes(member.id)}
                        onClick={() => handleMemberToggle(member.id)}
                        disabled={isSaving}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Allowed Vehicles */}
              <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Car className="h-5 w-5 text-[#76B900]" />
                  <h3 className="font-semibold text-white">Allowed Vehicles</h3>
                </div>
                <p className="mb-3 text-sm text-gray-400">
                  Vehicles that won&apos;t trigger alerts in this zone.
                </p>
                {(vehicles ?? []).length === 0 ? (
                  <p className="text-sm text-gray-500">
                    No vehicles registered. Add vehicles in Household Settings.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {(vehicles ?? []).map((vehicle: RegisteredVehicle) => (
                      <SelectionChip
                        key={vehicle.id}
                        label={vehicle.description}
                        selected={localConfig.vehicleIds.includes(vehicle.id)}
                        onClick={() => handleVehicleToggle(vehicle.id)}
                        disabled={isSaving}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Access Schedules */}
              <div className="rounded-lg border border-gray-700 bg-[#1A1A1A] p-4">
                <div className="mb-3 flex items-center gap-2">
                  <User className="h-5 w-5 text-[#76B900]" />
                  <h3 className="font-semibold text-white">Access Schedules</h3>
                </div>
                <p className="mb-3 text-sm text-gray-400">
                  Configure time-based access for specific members.
                </p>
                <AccessScheduleEditor
                  schedules={localSchedules}
                  onChange={handleSchedulesChange}
                  members={members ?? []}
                  disabled={isSaving}
                />
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(true)}
                  disabled={isSaving || !zoneConfig.config}
                  className={clsx(
                    'flex items-center gap-2 rounded-lg border border-red-800 px-4 py-2 text-sm text-red-400 transition-colors hover:bg-red-900/20',
                    (isSaving || !zoneConfig.config) && 'cursor-not-allowed opacity-50'
                  )}
                >
                  <X className="h-4 w-4" />
                  Clear All Settings
                </button>

                <div className="flex gap-3">
                  {hasUnsavedChanges && (
                    <button
                      type="button"
                      onClick={handleReset}
                      disabled={isSaving}
                      className={clsx(
                        'rounded-lg border border-gray-600 px-4 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-700',
                        isSaving && 'cursor-not-allowed opacity-50'
                      )}
                    >
                      Reset
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleSave()}
                    disabled={isSaving || !hasUnsavedChanges}
                    className={clsx(
                      'flex items-center gap-2 rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-gray-900 transition-colors hover:bg-[#8AD000]',
                      (isSaving || !hasUnsavedChanges) && 'cursor-not-allowed opacity-50'
                    )}
                    data-testid="save-zone-config-btn"
                  >
                    {isSaving ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Check className="h-4 w-4" />
                        Save Changes
                      </>
                    )}
                  </button>
                </div>
              </div>
            </>
          )}
        </>
      )}

      {/* Delete Confirmation Modal */}
      <Transition appear show={showDeleteConfirm} as={Fragment}>
        <Dialog
          as="div"
          className="relative z-50"
          onClose={() => setShowDeleteConfirm(false)}
        >
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
                  data-testid="delete-config-modal"
                >
                  <Dialog.Title className="mb-2 flex items-center gap-2 text-lg font-semibold text-white">
                    <AlertTriangle className="h-5 w-5 text-red-400" />
                    Clear Access Settings
                  </Dialog.Title>
                  <p className="mb-6 text-gray-400">
                    Are you sure you want to clear all access settings for{' '}
                    <span className="font-medium text-white">
                      {selectedZone?.name}
                    </span>
                    ? This action cannot be undone.
                  </p>
                  <div className="flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={() => setShowDeleteConfirm(false)}
                      disabled={isSaving}
                      className="rounded-lg border border-gray-600 px-4 py-2 text-gray-300 transition-colors hover:bg-gray-700"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleClearConfig()}
                      disabled={isSaving}
                      className={clsx(
                        'flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-white transition-colors hover:bg-red-700',
                        isSaving && 'cursor-not-allowed opacity-50'
                      )}
                      data-testid="confirm-delete-config"
                    >
                      {isSaving ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Clearing...
                        </>
                      ) : (
                        'Clear Settings'
                      )}
                    </button>
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
