/**
 * AccessScheduleEditor - Component for editing zone access schedules
 *
 * Provides a user-friendly UI for creating CRON-based access schedules
 * without requiring users to know CRON syntax.
 *
 * Features:
 * - Member multi-select
 * - Time range picker (start/end time)
 * - Day of week selector
 * - Description field
 * - CRON expression generation/parsing
 *
 * Part of NEM-3608: Zone-Household Access Control UI
 *
 * @module components/settings/AccessScheduleEditor
 */

import { clsx } from 'clsx';
import { Clock, Plus, Trash2, Users } from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';

import type { AccessSchedule } from '../../hooks/useZoneHouseholdConfig';
import type { HouseholdMember } from '../../hooks/useHouseholdApi';

// ============================================================================
// Types
// ============================================================================

export interface AccessScheduleEditorProps {
  /** Current access schedules */
  schedules: AccessSchedule[];
  /** Callback when schedules change */
  onChange: (schedules: AccessSchedule[]) => void;
  /** Available household members for selection */
  members: HouseholdMember[];
  /** Whether the editor is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

interface ScheduleFormData {
  memberIds: number[];
  startTime: string;
  endTime: string;
  days: string[];
  description: string;
}

// ============================================================================
// Constants
// ============================================================================

const DAYS_OF_WEEK = [
  { value: '1', label: 'Mon', full: 'Monday' },
  { value: '2', label: 'Tue', full: 'Tuesday' },
  { value: '3', label: 'Wed', full: 'Wednesday' },
  { value: '4', label: 'Thu', full: 'Thursday' },
  { value: '5', label: 'Fri', full: 'Friday' },
  { value: '6', label: 'Sat', full: 'Saturday' },
  { value: '0', label: 'Sun', full: 'Sunday' },
];

const QUICK_PRESETS = [
  { label: 'Weekdays', days: ['1', '2', '3', '4', '5'] },
  { label: 'Weekends', days: ['0', '6'] },
  { label: 'All Days', days: ['0', '1', '2', '3', '4', '5', '6'] },
];

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Generate a CRON expression from schedule form data.
 * Format: minute hour * * day_of_week
 *
 * Example: "0 9-17 * * 1-5" = 9am-5pm on weekdays
 */
function generateCronExpression(
  startTime: string,
  endTime: string,
  days: string[]
): string {
  const [startHour] = startTime.split(':').map(Number);
  const [endHour] = endTime.split(':').map(Number);

  // Build hour range
  const hourPart = startHour === endHour ? `${startHour}` : `${startHour}-${endHour}`;

  // Build day part
  const sortedDays = [...days].sort((a, b) => Number(a) - Number(b));
  const dayPart = sortedDays.length === 7 ? '*' : sortedDays.join(',');

  return `0 ${hourPart} * * ${dayPart}`;
}

/**
 * Parse a CRON expression into schedule form data.
 * Returns null if the expression cannot be parsed.
 */
function parseCronExpression(
  cron: string
): { startTime: string; endTime: string; days: string[] } | null {
  try {
    const parts = cron.split(' ');
    if (parts.length < 5) return null;

    const [, hourPart, , , dayPart] = parts;

    // Parse hours
    let startHour = 0;
    let endHour = 23;

    if (hourPart.includes('-')) {
      const [start, end] = hourPart.split('-').map(Number);
      startHour = start;
      endHour = end;
    } else if (hourPart !== '*') {
      startHour = endHour = Number(hourPart);
    }

    // Parse days
    let days: string[];
    if (dayPart === '*') {
      days = ['0', '1', '2', '3', '4', '5', '6'];
    } else {
      days = dayPart.split(',');
    }

    return {
      startTime: `${String(startHour).padStart(2, '0')}:00`,
      endTime: `${String(endHour).padStart(2, '0')}:00`,
      days,
    };
  } catch {
    return null;
  }
}

/**
 * Convert AccessSchedule to form data.
 */
function scheduleToFormData(schedule: AccessSchedule): ScheduleFormData {
  const parsed = parseCronExpression(schedule.cron_expression);

  return {
    memberIds: schedule.member_ids,
    startTime: parsed?.startTime ?? '09:00',
    endTime: parsed?.endTime ?? '17:00',
    days: parsed?.days ?? ['1', '2', '3', '4', '5'],
    description: schedule.description ?? '',
  };
}

/**
 * Convert form data to AccessSchedule.
 */
function formDataToSchedule(formData: ScheduleFormData): AccessSchedule {
  return {
    member_ids: formData.memberIds,
    cron_expression: generateCronExpression(
      formData.startTime,
      formData.endTime,
      formData.days
    ),
    description: formData.description || null,
  };
}

// ============================================================================
// Sub-components
// ============================================================================

interface ScheduleItemProps {
  schedule: AccessSchedule;
  members: HouseholdMember[];
  onEdit: () => void;
  onDelete: () => void;
  disabled?: boolean;
}

function ScheduleItem({
  schedule,
  members,
  onEdit,
  onDelete,
  disabled,
}: ScheduleItemProps) {
  const memberNames = useMemo(() => {
    return schedule.member_ids
      .map((id) => members.find((m) => m.id === id)?.name ?? `Member #${id}`)
      .join(', ');
  }, [schedule.member_ids, members]);

  const parsed = parseCronExpression(schedule.cron_expression);
  const timeDisplay = parsed
    ? `${parsed.startTime} - ${parsed.endTime}`
    : schedule.cron_expression;

  const dayDisplay = useMemo(() => {
    if (!parsed) return '';
    if (parsed.days.length === 7) return 'Every day';
    if (
      parsed.days.length === 5 &&
      ['1', '2', '3', '4', '5'].every((d) => parsed.days.includes(d))
    ) {
      return 'Weekdays';
    }
    if (
      parsed.days.length === 2 &&
      ['0', '6'].every((d) => parsed.days.includes(d))
    ) {
      return 'Weekends';
    }
    return parsed.days
      .map((d) => DAYS_OF_WEEK.find((day) => day.value === d)?.label ?? d)
      .join(', ');
  }, [parsed]);

  return (
    <div
      className="flex items-center justify-between rounded-lg border border-gray-700 bg-[#121212] p-3"
      data-testid="schedule-item"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 shrink-0 text-[#76B900]" />
          <span className="truncate text-sm font-medium text-white">
            {memberNames}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-2 text-xs text-gray-400">
          <Clock className="h-3 w-3 shrink-0" />
          <span>{timeDisplay}</span>
          <span className="text-gray-600">|</span>
          <span>{dayDisplay}</span>
        </div>
        {schedule.description && (
          <p className="mt-1 truncate text-xs text-gray-500">
            {schedule.description}
          </p>
        )}
      </div>
      <div className="ml-4 flex shrink-0 items-center gap-2">
        <button
          type="button"
          onClick={onEdit}
          disabled={disabled}
          className={clsx(
            'rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white',
            disabled && 'cursor-not-allowed opacity-50'
          )}
          aria-label="Edit schedule"
        >
          <Clock className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={disabled}
          className={clsx(
            'rounded p-1.5 text-gray-400 transition-colors hover:bg-red-900/50 hover:text-red-400',
            disabled && 'cursor-not-allowed opacity-50'
          )}
          aria-label="Delete schedule"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

interface ScheduleFormProps {
  initialData?: ScheduleFormData;
  members: HouseholdMember[];
  onSave: (data: ScheduleFormData) => void;
  onCancel: () => void;
  disabled?: boolean;
}

function ScheduleForm({
  initialData,
  members,
  onSave,
  onCancel,
  disabled,
}: ScheduleFormProps) {
  const [formData, setFormData] = useState<ScheduleFormData>(
    initialData ?? {
      memberIds: [],
      startTime: '09:00',
      endTime: '17:00',
      days: ['1', '2', '3', '4', '5'],
      description: '',
    }
  );

  const handleMemberToggle = (memberId: number) => {
    setFormData((prev) => ({
      ...prev,
      memberIds: prev.memberIds.includes(memberId)
        ? prev.memberIds.filter((id) => id !== memberId)
        : [...prev.memberIds, memberId],
    }));
  };

  const handleDayToggle = (day: string) => {
    setFormData((prev) => ({
      ...prev,
      days: prev.days.includes(day)
        ? prev.days.filter((d) => d !== day)
        : [...prev.days, day],
    }));
  };

  const handlePresetClick = (days: string[]) => {
    setFormData((prev) => ({ ...prev, days }));
  };

  const handleSave = () => {
    if (formData.memberIds.length === 0 || formData.days.length === 0) {
      return;
    }
    onSave(formData);
  };

  const isValid = formData.memberIds.length > 0 && formData.days.length > 0;

  return (
    <div
      className="rounded-lg border border-gray-700 bg-[#121212] p-4"
      data-testid="schedule-form"
    >
      {/* Member Selection */}
      <div className="mb-4">
        <label className="mb-2 block text-sm font-medium text-gray-300">
          Members
        </label>
        <div className="flex flex-wrap gap-2">
          {members.map((member) => (
            <button
              key={member.id}
              type="button"
              onClick={() => handleMemberToggle(member.id)}
              disabled={disabled}
              className={clsx(
                'rounded-full px-3 py-1 text-sm transition-colors',
                formData.memberIds.includes(member.id)
                  ? 'bg-[#76B900] text-gray-900'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600',
                disabled && 'cursor-not-allowed opacity-50'
              )}
            >
              {member.name}
            </button>
          ))}
        </div>
        {members.length === 0 && (
          <p className="text-sm text-gray-500">No members available</p>
        )}
      </div>

      {/* Time Range */}
      <div className="mb-4">
        <label className="mb-2 block text-sm font-medium text-gray-300">
          Time Range
        </label>
        <div className="flex items-center gap-4">
          <div>
            <label htmlFor="start-time" className="sr-only">
              Start time
            </label>
            <input
              type="time"
              id="start-time"
              value={formData.startTime}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, startTime: e.target.value }))
              }
              disabled={disabled}
              className={clsx(
                'rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
                disabled && 'cursor-not-allowed opacity-50'
              )}
            />
          </div>
          <span className="text-gray-500">to</span>
          <div>
            <label htmlFor="end-time" className="sr-only">
              End time
            </label>
            <input
              type="time"
              id="end-time"
              value={formData.endTime}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, endTime: e.target.value }))
              }
              disabled={disabled}
              className={clsx(
                'rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
                disabled && 'cursor-not-allowed opacity-50'
              )}
            />
          </div>
        </div>
      </div>

      {/* Day Selection */}
      <div className="mb-4">
        <div className="mb-2 flex items-center justify-between">
          <label className="text-sm font-medium text-gray-300">Days</label>
          <div className="flex gap-2">
            {QUICK_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => handlePresetClick(preset.days)}
                disabled={disabled}
                className={clsx(
                  'rounded px-2 py-0.5 text-xs transition-colors',
                  JSON.stringify(formData.days.sort()) ===
                    JSON.stringify(preset.days.sort())
                    ? 'bg-[#76B900] text-gray-900'
                    : 'bg-gray-700 text-gray-400 hover:bg-gray-600',
                  disabled && 'cursor-not-allowed opacity-50'
                )}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {DAYS_OF_WEEK.map((day) => (
            <button
              key={day.value}
              type="button"
              onClick={() => handleDayToggle(day.value)}
              disabled={disabled}
              className={clsx(
                'rounded px-3 py-1.5 text-sm font-medium transition-colors',
                formData.days.includes(day.value)
                  ? 'bg-[#76B900] text-gray-900'
                  : 'bg-gray-700 text-gray-400 hover:bg-gray-600',
                disabled && 'cursor-not-allowed opacity-50'
              )}
              title={day.full}
            >
              {day.label}
            </button>
          ))}
        </div>
      </div>

      {/* Description */}
      <div className="mb-4">
        <label
          htmlFor="schedule-description"
          className="mb-2 block text-sm font-medium text-gray-300"
        >
          Description (optional)
        </label>
        <input
          type="text"
          id="schedule-description"
          value={formData.description}
          onChange={(e) =>
            setFormData((prev) => ({ ...prev, description: e.target.value }))
          }
          placeholder="e.g., Service workers during business hours"
          disabled={disabled}
          className={clsx(
            'w-full rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white placeholder-gray-500 focus:border-[#76B900] focus:outline-none focus:ring-1 focus:ring-[#76B900]',
            disabled && 'cursor-not-allowed opacity-50'
          )}
        />
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={disabled}
          className={clsx(
            'rounded-lg border border-gray-600 px-4 py-2 text-sm text-gray-300 transition-colors hover:bg-gray-700',
            disabled && 'cursor-not-allowed opacity-50'
          )}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={disabled || !isValid}
          className={clsx(
            'rounded-lg bg-[#76B900] px-4 py-2 text-sm font-medium text-gray-900 transition-colors hover:bg-[#8AD000]',
            (disabled || !isValid) && 'cursor-not-allowed opacity-50'
          )}
        >
          Save Schedule
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * AccessScheduleEditor component for managing zone access schedules.
 *
 * Provides a user-friendly interface for creating and editing CRON-based
 * access schedules without requiring users to understand CRON syntax.
 */
export default function AccessScheduleEditor({
  schedules,
  onChange,
  members,
  disabled = false,
  className,
}: AccessScheduleEditorProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const handleAddSchedule = useCallback(
    (formData: ScheduleFormData) => {
      const newSchedule = formDataToSchedule(formData);
      onChange([...schedules, newSchedule]);
      setIsAdding(false);
    },
    [schedules, onChange]
  );

  const handleEditSchedule = useCallback(
    (index: number, formData: ScheduleFormData) => {
      const updatedSchedules = [...schedules];
      updatedSchedules[index] = formDataToSchedule(formData);
      onChange(updatedSchedules);
      setEditingIndex(null);
    },
    [schedules, onChange]
  );

  const handleDeleteSchedule = useCallback(
    (index: number) => {
      onChange(schedules.filter((_, i) => i !== index));
    },
    [schedules, onChange]
  );

  return (
    <div className={clsx('space-y-3', className)} data-testid="access-schedule-editor">
      {/* Existing Schedules */}
      {schedules.map((schedule, index) => (
        <div key={index}>
          {editingIndex === index ? (
            <ScheduleForm
              initialData={scheduleToFormData(schedule)}
              members={members}
              onSave={(data) => handleEditSchedule(index, data)}
              onCancel={() => setEditingIndex(null)}
              disabled={disabled}
            />
          ) : (
            <ScheduleItem
              schedule={schedule}
              members={members}
              onEdit={() => setEditingIndex(index)}
              onDelete={() => handleDeleteSchedule(index)}
              disabled={disabled}
            />
          )}
        </div>
      ))}

      {/* Add New Schedule */}
      {isAdding ? (
        <ScheduleForm
          members={members}
          onSave={handleAddSchedule}
          onCancel={() => setIsAdding(false)}
          disabled={disabled}
        />
      ) : (
        <button
          type="button"
          onClick={() => setIsAdding(true)}
          disabled={disabled || members.length === 0}
          className={clsx(
            'flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-gray-600 py-3 text-sm text-gray-400 transition-colors hover:border-[#76B900] hover:text-[#76B900]',
            (disabled || members.length === 0) && 'cursor-not-allowed opacity-50'
          )}
          data-testid="add-schedule-btn"
        >
          <Plus className="h-4 w-4" />
          Add Access Schedule
        </button>
      )}
    </div>
  );
}
