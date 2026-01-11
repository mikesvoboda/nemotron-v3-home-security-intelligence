/**
 * NotificationPreferencesForm - Comprehensive notification preferences management form.
 *
 * Provides a unified interface for:
 * - Global notification enabled toggle
 * - Notification sound selection
 * - Risk level filter checkboxes (critical, high, medium, low)
 * - Quiet hours period management with validation
 *
 * Uses validateQuietHoursLabel() from utils/validation.ts for label validation.
 */
import { Card, Title, Text, Badge, Select, SelectItem, TextInput, Button } from '@tremor/react';
import {
  AlertCircle,
  Bell,
  Clock,
  Loader2,
  Moon,
  Plus,
  Trash2,
  Volume2,
  X,
} from 'lucide-react';
import { useState, useCallback, useMemo, type FormEvent } from 'react';

import {
  useGlobalNotificationPreferencesQuery,
  useQuietHoursPeriodsQuery,
  useNotificationPreferencesMutation,
} from '../../hooks/useNotificationPreferencesQuery';
import {
  NOTIFICATION_SOUNDS,
  RISK_LEVELS,
  DAYS_OF_WEEK,
  type NotificationSound,
  type RiskLevel,
  type DayOfWeek,
  type QuietHoursPeriod,
} from '../../types/notificationPreferences';
import { validateQuietHoursLabel } from '../../utils/validation';

// ============================================================================
// Props and Types
// ============================================================================

export interface NotificationPreferencesFormProps {
  className?: string;
}

interface FormErrors {
  label?: string;
  startTime?: string;
  endTime?: string;
  days?: string;
  general?: string;
}

// ============================================================================
// Helper Components
// ============================================================================

/**
 * Format time string from HH:MM:SS to HH:MM
 */
function formatTime(time: string): string {
  return time.slice(0, 5);
}

/**
 * Format days array to readable string
 */
function formatDays(days: DayOfWeek[]): string {
  if (days.length === 7) return 'Every day';
  if (days.length === 5 && !days.includes('saturday') && !days.includes('sunday')) {
    return 'Weekdays';
  }
  if (days.length === 2 && days.includes('saturday') && days.includes('sunday')) {
    return 'Weekends';
  }

  const dayLabels = DAYS_OF_WEEK.filter((d) => days.includes(d.value)).map((d) => d.short);
  return dayLabels.join(', ');
}

interface QuietPeriodRowProps {
  period: QuietHoursPeriod;
  onDelete: (periodId: string) => Promise<void>;
  isDeleting: boolean;
}

/**
 * Individual row for quiet hours period
 */
function QuietPeriodRow({ period, onDelete, isDeleting }: QuietPeriodRowProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleDelete = async () => {
    await onDelete(period.id);
    setConfirmDelete(false);
  };

  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-800 bg-[#121212] p-4">
      <div className="flex items-center gap-3">
        <Moon className="h-5 w-5 text-purple-400" />
        <div>
          <Text className="font-medium text-gray-300">{period.label}</Text>
          <div className="mt-1 flex items-center gap-2">
            <Badge color="purple" size="sm">
              {formatTime(period.start_time)} - {formatTime(period.end_time)}
            </Badge>
            <Text className="text-xs text-gray-500">{formatDays(period.days)}</Text>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {confirmDelete ? (
          <>
            <Text className="mr-2 text-sm text-red-400">Delete?</Text>
            <Button
              size="xs"
              variant="secondary"
              onClick={() => setConfirmDelete(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              size="xs"
              color="red"
              onClick={() => void handleDelete()}
              disabled={isDeleting}
            >
              {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Delete'}
            </Button>
          </>
        ) : (
          <Button
            size="xs"
            variant="secondary"
            onClick={() => setConfirmDelete(true)}
            className="text-red-400 hover:text-red-300"
            aria-label="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}

interface CreatePeriodFormProps {
  onSubmit: (label: string, startTime: string, endTime: string, days: DayOfWeek[]) => Promise<void>;
  onCancel: () => void;
  isSubmitting: boolean;
  mutationError: Error | null;
}

/**
 * Form for creating a new quiet hours period with validation
 */
function CreatePeriodForm({ onSubmit, onCancel, isSubmitting, mutationError }: CreatePeriodFormProps) {
  const [label, setLabel] = useState('');
  const [startTime, setStartTime] = useState('22:00');
  const [endTime, setEndTime] = useState('06:00');
  const [days, setDays] = useState<DayOfWeek[]>([
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday',
  ]);
  const [errors, setErrors] = useState<FormErrors>({});

  const toggleDay = (day: DayOfWeek) => {
    setDays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]));
  };

  const clearFieldError = (field: keyof FormErrors) => {
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

  const handleLabelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLabel(e.target.value);
    clearFieldError('label');
  };

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Validate label using the validation utility
    const labelValidation = validateQuietHoursLabel(label);
    if (!labelValidation.isValid) {
      newErrors.label = labelValidation.error;
    }

    // Validate times
    if (!startTime) {
      newErrors.startTime = 'Start time is required';
    }
    if (!endTime) {
      newErrors.endTime = 'End time is required';
    }
    if (startTime && endTime && startTime === endTime) {
      newErrors.endTime = 'Start time must be different from end time';
    }

    // Validate days
    if (days.length === 0) {
      newErrors.days = 'At least one day must be selected';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      // Convert HH:MM to HH:MM:SS
      await onSubmit(label.trim(), `${startTime}:00`, `${endTime}:00`, days);
    } catch (err) {
      setErrors({
        general: err instanceof Error ? err.message : 'Failed to create period',
      });
    }
  };

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
      data-testid="quiet-hours-form"
    >
      <div className="mb-4 flex items-center justify-between">
        <Text className="font-medium text-gray-300">New Quiet Hours Period</Text>
        <button
          type="button"
          onClick={onCancel}
          className="text-gray-400 hover:text-gray-300"
          aria-label="Close form"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {(errors.general || mutationError) && (
        <div className="mb-4 flex items-center gap-2 rounded border border-red-500/30 bg-red-500/10 p-2">
          <AlertCircle className="h-4 w-4 text-red-400" />
          <Text className="text-sm text-red-400">
            Failed to create: {errors.general || mutationError?.message}
          </Text>
        </div>
      )}

      <div className="space-y-4">
        {/* Label */}
        <div>
          <label htmlFor="quiet-hours-label" className="mb-1 block text-sm text-gray-400">
            Label
          </label>
          <TextInput
            id="quiet-hours-label"
            value={label}
            onChange={handleLabelChange}
            placeholder="e.g., Night Hours, Work Hours"
            maxLength={255}
            error={!!errors.label}
            errorMessage={errors.label}
          />
        </div>

        {/* Time Range */}
        <div className="flex gap-4">
          <div className="flex-1">
            <label htmlFor="quiet-hours-start" className="mb-1 block text-sm text-gray-400">
              Start Time
            </label>
            <input
              id="quiet-hours-start"
              type="time"
              value={startTime}
              onChange={(e) => {
                setStartTime(e.target.value);
                clearFieldError('startTime');
              }}
              className={`w-full rounded-lg border px-3 py-2 text-white focus:outline-none ${
                errors.startTime
                  ? 'border-red-500 bg-red-500/10 focus:border-red-500'
                  : 'border-gray-700 bg-gray-800 focus:border-[#76B900]'
              }`}
            />
            {errors.startTime && (
              <Text className="mt-1 text-sm text-red-400">{errors.startTime}</Text>
            )}
          </div>
          <div className="flex-1">
            <label htmlFor="quiet-hours-end" className="mb-1 block text-sm text-gray-400">
              End Time
            </label>
            <input
              id="quiet-hours-end"
              type="time"
              value={endTime}
              onChange={(e) => {
                setEndTime(e.target.value);
                clearFieldError('endTime');
              }}
              className={`w-full rounded-lg border px-3 py-2 text-white focus:outline-none ${
                errors.endTime
                  ? 'border-red-500 bg-red-500/10 focus:border-red-500'
                  : 'border-gray-700 bg-gray-800 focus:border-[#76B900]'
              }`}
            />
            {errors.endTime && (
              <Text className="mt-1 text-sm text-red-400">{errors.endTime}</Text>
            )}
          </div>
        </div>

        {/* Days Selection */}
        <div>
          <span className="mb-2 block text-sm text-gray-400">Active Days</span>
          <div className="flex flex-wrap gap-2">
            {DAYS_OF_WEEK.map((day) => {
              const isSelected = days.includes(day.value);
              return (
                <button
                  key={day.value}
                  type="button"
                  onClick={() => toggleDay(day.value)}
                  className={`rounded-lg border px-3 py-1.5 text-sm transition-all ${
                    isSelected
                      ? 'border-[#76B900] bg-[#76B900]/20 text-[#76B900]'
                      : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600'
                  }`}
                >
                  {day.short}
                </button>
              );
            })}
          </div>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() =>
                setDays([
                  'monday',
                  'tuesday',
                  'wednesday',
                  'thursday',
                  'friday',
                  'saturday',
                  'sunday',
                ])
              }
              className="text-xs text-gray-500 hover:text-gray-400"
            >
              All
            </button>
            <button
              type="button"
              onClick={() =>
                setDays(['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])
              }
              className="text-xs text-gray-500 hover:text-gray-400"
            >
              Weekdays
            </button>
            <button
              type="button"
              onClick={() => setDays(['saturday', 'sunday'])}
              className="text-xs text-gray-500 hover:text-gray-400"
            >
              Weekends
            </button>
            <button
              type="button"
              onClick={() => setDays([])}
              className="text-xs text-gray-500 hover:text-gray-400"
            >
              None
            </button>
          </div>
          {errors.days && (
            <Text className="mt-2 text-sm text-red-400">{errors.days}</Text>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={isSubmitting}
            className="bg-[#76B900] text-white hover:bg-[#8BD000]"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="mr-2 h-4 w-4" />
                Create Period
              </>
            )}
          </Button>
        </div>
      </div>
    </form>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * NotificationPreferencesForm provides a comprehensive interface for managing
 * notification preferences including global settings and quiet hours.
 */
export default function NotificationPreferencesForm({
  className,
}: NotificationPreferencesFormProps) {
  const { preferences, isLoading, error, refetch } = useGlobalNotificationPreferencesQuery();
  const {
    periods,
    isLoading: periodsLoading,
    error: periodsError,
    refetch: refetchPeriods,
  } = useQuietHoursPeriodsQuery();
  const {
    updateGlobalMutation,
    createQuietHoursMutation,
    deleteQuietHoursMutation,
  } = useNotificationPreferencesMutation();

  const [showCreateForm, setShowCreateForm] = useState(false);

  // Local state for optimistic updates
  const [localEnabled, setLocalEnabled] = useState<boolean | null>(null);
  const [localSound, setLocalSound] = useState<NotificationSound | null>(null);
  const [localRiskFilters, setLocalRiskFilters] = useState<RiskLevel[] | null>(null);

  // Effective values (local state overrides server state)
  const enabled = localEnabled ?? preferences?.enabled ?? true;
  const sound = localSound ?? (preferences?.sound as NotificationSound) ?? 'default';
  const riskFilters = useMemo<RiskLevel[]>(
    () => localRiskFilters ?? preferences?.risk_filters ?? [],
    [localRiskFilters, preferences?.risk_filters]
  );

  const isUpdating = updateGlobalMutation.isPending;

  // Handle enable toggle
  const handleToggle = useCallback(async () => {
    const newEnabled = !enabled;
    setLocalEnabled(newEnabled);
    try {
      await updateGlobalMutation.mutateAsync({ enabled: newEnabled });
      setLocalEnabled(null);
    } catch {
      setLocalEnabled(null);
    }
  }, [enabled, updateGlobalMutation]);

  // Handle sound change
  const handleSoundChange = useCallback(
    async (newSound: string) => {
      const soundValue = newSound as NotificationSound;
      setLocalSound(soundValue);
      try {
        await updateGlobalMutation.mutateAsync({ sound: soundValue });
        setLocalSound(null);
      } catch {
        setLocalSound(null);
      }
    },
    [updateGlobalMutation]
  );

  // Handle risk filter toggle
  const handleRiskFilterToggle = useCallback(
    async (level: RiskLevel) => {
      const newFilters = riskFilters.includes(level)
        ? riskFilters.filter((l) => l !== level)
        : [...riskFilters, level];
      setLocalRiskFilters(newFilters);
      try {
        await updateGlobalMutation.mutateAsync({ risk_filters: newFilters });
        setLocalRiskFilters(null);
      } catch {
        setLocalRiskFilters(null);
      }
    },
    [riskFilters, updateGlobalMutation]
  );

  // Handle quiet hours create
  const handleCreateQuietHours = useCallback(
    async (label: string, startTime: string, endTime: string, days: DayOfWeek[]) => {
      await createQuietHoursMutation.mutateAsync({
        label,
        start_time: startTime,
        end_time: endTime,
        days,
      });
      setShowCreateForm(false);
    },
    [createQuietHoursMutation]
  );

  // Handle quiet hours delete
  const handleDeleteQuietHours = useCallback(
    async (periodId: string) => {
      await deleteQuietHoursMutation.mutateAsync(periodId);
    },
    [deleteQuietHoursMutation]
  );

  // Determine loading state
  const showLoading = isLoading || periodsLoading;

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <Title className="mb-4 flex items-center gap-2 text-white">
        <Bell className="h-5 w-5 text-[#76B900]" />
        Notification Preferences
      </Title>

      <Text className="mb-6 text-sm text-gray-400">
        Configure how and when you receive notifications about security events.
      </Text>

      {/* Loading State */}
      {showLoading && (
        <div className="flex items-center justify-center py-8" data-testid="loading-spinner">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      )}

      {/* Error State */}
      {(error || periodsError) && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">{error?.message || periodsError?.message}</Text>
          <button
            onClick={() => {
              void refetch();
              void refetchPeriods();
            }}
            className="ml-auto text-sm text-red-400 underline hover:text-red-300"
          >
            Retry
          </button>
        </div>
      )}

      {/* Update Error */}
      {updateGlobalMutation.error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">
            Failed to update: {updateGlobalMutation.error.message}
          </Text>
        </div>
      )}

      {/* Main Form Content */}
      {!showLoading && preferences && (
        <div className="space-y-6">
          {/* Master Toggle */}
          <div className="flex items-center justify-between rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="flex items-center gap-3">
              <Bell className="h-5 w-5 text-gray-400" />
              <div>
                <Text className="font-medium text-gray-300">Enable Notifications</Text>
                <Text className="text-xs text-gray-500">
                  Master switch for all notification types
                </Text>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => void handleToggle()}
                disabled={isUpdating}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900 ${
                  enabled ? 'bg-[#76B900]' : 'bg-gray-600'
                } ${isUpdating ? 'cursor-not-allowed opacity-50' : ''}`}
                role="switch"
                aria-checked={enabled}
                aria-label="Enable notifications"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    enabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              <Badge color={enabled ? 'green' : 'gray'} size="sm">
                {enabled ? 'On' : 'Off'}
              </Badge>
            </div>
          </div>

          {/* Sound Selection */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-3 flex items-center gap-3">
              <Volume2 className="h-5 w-5 text-gray-400" />
              <div>
                <Text className="font-medium text-gray-300">Notification Sound</Text>
                <Text className="text-xs text-gray-500">
                  Choose the sound for notifications
                </Text>
              </div>
            </div>
            <Select
              value={sound}
              onValueChange={(value) => void handleSoundChange(value)}
              disabled={!enabled || isUpdating}
              className="mt-2"
            >
              {NOTIFICATION_SOUNDS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </Select>
          </div>

          {/* Risk Level Filters */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-3">
              <Text className="font-medium text-gray-300">Risk Level Filters</Text>
              <Text className="text-xs text-gray-500">
                Select which risk levels should trigger notifications
              </Text>
            </div>
            <div className="flex flex-wrap gap-2">
              {RISK_LEVELS.map((level) => {
                const isSelected = riskFilters.includes(level.value);
                const colorClasses: Record<string, string> = {
                  red: isSelected
                    ? 'border-red-500 bg-red-500/20 text-red-400'
                    : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600',
                  orange: isSelected
                    ? 'border-orange-500 bg-orange-500/20 text-orange-400'
                    : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600',
                  yellow: isSelected
                    ? 'border-yellow-500 bg-yellow-500/20 text-yellow-400'
                    : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600',
                  green: isSelected
                    ? 'border-green-500 bg-green-500/20 text-green-400'
                    : 'border-gray-700 bg-gray-800/50 text-gray-400 hover:border-gray-600',
                };
                return (
                  <button
                    key={level.value}
                    onClick={() => void handleRiskFilterToggle(level.value)}
                    disabled={!enabled || isUpdating}
                    className={`rounded-lg border px-4 py-2 text-sm font-medium transition-all ${
                      colorClasses[level.color]
                    } ${!enabled || isUpdating ? 'cursor-not-allowed opacity-50' : ''}`}
                  >
                    {level.label}
                  </button>
                );
              })}
            </div>
            {riskFilters.length === 0 && enabled && (
              <Text className="mt-2 text-xs text-yellow-400">
                Warning: No risk levels selected. You will not receive any notifications.
              </Text>
            )}
          </div>

          {/* Quiet Hours Section */}
          <div className="rounded-lg border border-gray-800 bg-[#121212] p-4">
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Clock className="h-5 w-5 text-[#76B900]" />
                <div>
                  <Text className="font-medium text-gray-300">Quiet Hours</Text>
                  <Text className="text-xs text-gray-500">
                    Configure time periods when notifications should be silenced
                  </Text>
                </div>
              </div>
              {!showCreateForm && (
                <Button
                  size="sm"
                  onClick={() => setShowCreateForm(true)}
                  className="bg-[#76B900] text-white hover:bg-[#8BD000]"
                >
                  <Plus className="mr-1 h-4 w-4" />
                  Add Period
                </Button>
              )}
            </div>

            {/* Create Form */}
            {showCreateForm && (
              <div className="mb-4">
                <CreatePeriodForm
                  onSubmit={handleCreateQuietHours}
                  onCancel={() => setShowCreateForm(false)}
                  isSubmitting={createQuietHoursMutation.isPending}
                  mutationError={createQuietHoursMutation.error}
                />
              </div>
            )}

            {/* Periods List */}
            {periods.length === 0 && !showCreateForm && (
              <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-6 text-center">
                <Moon className="mx-auto mb-2 h-8 w-8 text-gray-500" />
                <Text className="text-gray-400">No quiet hours configured</Text>
                <Text className="mt-1 text-xs text-gray-500">
                  Add a quiet hours period to silence notifications during specific times.
                </Text>
              </div>
            )}

            {periods.length > 0 && (
              <div className="space-y-3">
                {periods.map((period) => (
                  <QuietPeriodRow
                    key={period.id}
                    period={period}
                    onDelete={handleDeleteQuietHours}
                    isDeleting={deleteQuietHoursMutation.isPending}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Info note */}
          <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-3">
            <Text className="text-sm text-blue-400">
              <strong>Tip:</strong> Quiet hours support overnight periods (e.g., 22:00 to 06:00).
              Notifications will be silenced when the current time falls within any active period.
            </Text>
          </div>
        </div>
      )}
    </Card>
  );
}
