/**
 * QuietHoursScheduler component displays and manages quiet hours periods.
 * - Create new quiet hours periods
 * - View existing periods
 * - Delete periods
 */
import { Card, Title, Text, Badge, Button, TextInput } from '@tremor/react';
import { AlertCircle, Clock, Loader2, Moon, Plus, Trash2, X } from 'lucide-react';
import { useState, useCallback } from 'react';

import {
  useQuietHoursPeriodsQuery,
  useNotificationPreferencesMutation,
} from '../../hooks/useNotificationPreferencesQuery';
import {
  DAYS_OF_WEEK,
  type DayOfWeek,
  type QuietHoursPeriod,
} from '../../types/notificationPreferences';

export interface QuietHoursSchedulerProps {
  className?: string;
}

interface QuietPeriodRowProps {
  period: QuietHoursPeriod;
  onDelete: (periodId: string) => Promise<void>;
  isDeleting: boolean;
}

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
            <Button size="xs" color="red" onClick={() => void handleDelete()} disabled={isDeleting}>
              {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Delete'}
            </Button>
          </>
        ) : (
          <Button
            size="xs"
            variant="secondary"
            onClick={() => setConfirmDelete(true)}
            className="text-red-400 hover:text-red-300"
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
}

/**
 * Form for creating a new quiet hours period
 */
function CreatePeriodForm({ onSubmit, onCancel, isSubmitting }: CreatePeriodFormProps) {
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
  const [error, setError] = useState<string | null>(null);

  const toggleDay = (day: DayOfWeek) => {
    setDays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!label.trim()) {
      setError('Label is required');
      return;
    }
    if (!startTime || !endTime) {
      setError('Start and end times are required');
      return;
    }
    if (days.length === 0) {
      setError('At least one day must be selected');
      return;
    }
    if (startTime === endTime) {
      setError('Start time must be different from end time');
      return;
    }

    try {
      // Convert HH:MM to HH:MM:SS
      await onSubmit(label.trim(), `${startTime}:00`, `${endTime}:00`, days);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create period');
    }
  };

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
    >
      <div className="mb-4 flex items-center justify-between">
        <Text className="font-medium text-gray-300">New Quiet Hours Period</Text>
        <button type="button" onClick={onCancel} className="text-gray-400 hover:text-gray-300">
          <X className="h-5 w-5" />
        </button>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded border border-red-500/30 bg-red-500/10 p-2">
          <AlertCircle className="h-4 w-4 text-red-400" />
          <Text className="text-sm text-red-400">{error}</Text>
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
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g., Night Hours, Work Hours"
            maxLength={255}
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
              onChange={(e) => setStartTime(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-[#76B900] focus:outline-none"
            />
          </div>
          <div className="flex-1">
            <label htmlFor="quiet-hours-end" className="mb-1 block text-sm text-gray-400">
              End Time
            </label>
            <input
              id="quiet-hours-end"
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-[#76B900] focus:outline-none"
            />
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
              onClick={() => setDays(['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])}
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

/**
 * QuietHoursScheduler displays and manages quiet hours periods.
 *
 * Features:
 * - View all quiet hours periods
 * - Create new periods with label, time range, and day selection
 * - Delete existing periods
 * - Supports overnight periods (e.g., 22:00 - 06:00)
 */
export default function QuietHoursScheduler({ className }: QuietHoursSchedulerProps) {
  const { periods, isLoading, error, refetch } = useQuietHoursPeriodsQuery();
  const { createQuietHoursMutation, deleteQuietHoursMutation } =
    useNotificationPreferencesMutation();
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Handle create
  const handleCreate = useCallback(
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

  // Handle delete
  const handleDelete = useCallback(
    async (periodId: string) => {
      await deleteQuietHoursMutation.mutateAsync(periodId);
    },
    [deleteQuietHoursMutation]
  );

  return (
    <Card className={`border-gray-800 bg-[#1A1A1A] shadow-lg ${className || ''}`}>
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Clock className="h-5 w-5 text-[#76B900]" />
          Quiet Hours
        </Title>
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

      <Text className="mb-4 text-sm text-gray-400">
        Configure time periods when notifications should be silenced. Useful for sleep hours or work
        hours when you do not want to be disturbed.
      </Text>

      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      )}

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">{error.message}</Text>
          <button
            onClick={() => void refetch()}
            className="ml-auto text-sm text-red-400 underline hover:text-red-300"
          >
            Retry
          </button>
        </div>
      )}

      {createQuietHoursMutation.error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">
            Failed to create: {createQuietHoursMutation.error.message}
          </Text>
        </div>
      )}

      {deleteQuietHoursMutation.error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
          <Text className="text-red-400">
            Failed to delete: {deleteQuietHoursMutation.error.message}
          </Text>
        </div>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="mb-4">
          <CreatePeriodForm
            onSubmit={handleCreate}
            onCancel={() => setShowCreateForm(false)}
            isSubmitting={createQuietHoursMutation.isPending}
          />
        </div>
      )}

      {/* Periods List */}
      {!isLoading && periods.length === 0 && !showCreateForm && (
        <div className="rounded-lg border border-gray-700 bg-gray-800/30 p-6 text-center">
          <Moon className="mx-auto mb-2 h-8 w-8 text-gray-500" />
          <Text className="text-gray-400">No quiet hours configured</Text>
          <Text className="mt-1 text-xs text-gray-500">
            Add a quiet hours period to silence notifications during specific times.
          </Text>
        </div>
      )}

      {!isLoading && periods.length > 0 && (
        <div className="space-y-3">
          {periods.map((period) => (
            <QuietPeriodRow
              key={period.id}
              period={period}
              onDelete={handleDelete}
              isDeleting={deleteQuietHoursMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Info note */}
      <div className="mt-4 rounded-lg border border-blue-500/30 bg-blue-500/10 p-3">
        <Text className="text-sm text-blue-400">
          <strong>Tip:</strong> Quiet hours support overnight periods (e.g., 22:00 to 06:00).
          Notifications will be silenced when the current time falls within any active period.
        </Text>
      </div>
    </Card>
  );
}
