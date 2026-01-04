import { clsx } from 'clsx';
import { Calendar, Clock, Plus, Trash2 } from 'lucide-react';

/** Day of the week type */
export type DayOfWeek = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';

/** Schedule entry interface */
export interface Schedule {
  id: string;
  days: DayOfWeek[];
  startTime: string; // "HH:MM" format
  endTime: string; // "HH:MM" format
}

/** Props for the ScheduleSelector component */
export interface ScheduleSelectorProps {
  /** Array of schedule entries */
  schedules: Schedule[];
  /** Callback when schedules change */
  onChange: (schedules: Schedule[]) => void;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/** Days of the week configuration */
const DAYS_OF_WEEK: { value: DayOfWeek; label: string }[] = [
  { value: 'mon', label: 'Mon' },
  { value: 'tue', label: 'Tue' },
  { value: 'wed', label: 'Wed' },
  { value: 'thu', label: 'Thu' },
  { value: 'fri', label: 'Fri' },
  { value: 'sat', label: 'Sat' },
  { value: 'sun', label: 'Sun' },
];

/**
 * Generate a unique ID for a new schedule
 */
function generateScheduleId(): string {
  return `schedule-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * ScheduleSelector component for configuring time-based schedules
 *
 * Features:
 * - Multi-select for days of the week
 * - Start and end time pickers
 * - Support for multiple schedule entries
 * - Add/remove schedule functionality
 * - Disabled state support
 */
export default function ScheduleSelector({
  schedules,
  onChange,
  disabled = false,
  className,
}: ScheduleSelectorProps) {
  /**
   * Add a new empty schedule
   */
  const handleAddSchedule = () => {
    if (disabled) return;

    const newSchedule: Schedule = {
      id: generateScheduleId(),
      days: [],
      startTime: '00:00',
      endTime: '23:59',
    };

    onChange([...schedules, newSchedule]);
  };

  /**
   * Remove a schedule by ID
   */
  const handleRemoveSchedule = (scheduleId: string) => {
    if (disabled) return;

    onChange(schedules.filter((s) => s.id !== scheduleId));
  };

  /**
   * Toggle a day selection for a specific schedule
   */
  const handleToggleDay = (scheduleId: string, day: DayOfWeek) => {
    if (disabled) return;

    onChange(
      schedules.map((schedule) => {
        if (schedule.id !== scheduleId) return schedule;

        const newDays = schedule.days.includes(day)
          ? schedule.days.filter((d) => d !== day)
          : [...schedule.days, day];

        return { ...schedule, days: newDays };
      })
    );
  };

  /**
   * Update the start time for a specific schedule
   */
  const handleStartTimeChange = (scheduleId: string, startTime: string) => {
    if (disabled) return;

    onChange(
      schedules.map((schedule) =>
        schedule.id === scheduleId ? { ...schedule, startTime } : schedule
      )
    );
  };

  /**
   * Update the end time for a specific schedule
   */
  const handleEndTimeChange = (scheduleId: string, endTime: string) => {
    if (disabled) return;

    onChange(
      schedules.map((schedule) =>
        schedule.id === scheduleId ? { ...schedule, endTime } : schedule
      )
    );
  };

  return (
    <div data-testid="schedule-selector" className={clsx('space-y-4', className)}>
      {schedules.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-700 bg-card/50 p-6 text-center">
          <Calendar className="mx-auto h-8 w-8 text-gray-500" />
          <p className="mt-2 text-sm text-text-secondary">No schedules configured</p>
          <p className="mt-1 text-xs text-gray-500">
            Add a schedule to define when this rule should be active
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {schedules.map((schedule, index) => (
            <div
              key={schedule.id}
              data-testid="schedule-entry"
              className="rounded-lg border border-gray-800 bg-card p-4"
            >
              {/* Schedule Header */}
              <div className="mb-4 flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm font-medium text-text-primary">
                  <Calendar className="h-4 w-4 text-primary" />
                  Schedule {index + 1}
                </span>
                <button
                  type="button"
                  onClick={() => handleRemoveSchedule(schedule.id)}
                  disabled={disabled}
                  className="rounded p-1.5 text-gray-400 transition-colors hover:bg-gray-800 hover:text-red-500 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label="Remove schedule"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>

              {/* Days Selection */}
              <div className="mb-4">
                <span className="mb-2 block text-xs font-medium text-text-secondary">
                  Days of Week
                </span>
                <div className="flex flex-wrap gap-2">
                  {DAYS_OF_WEEK.map((day) => {
                    const isSelected = schedule.days.includes(day.value);
                    return (
                      <button
                        key={day.value}
                        type="button"
                        onClick={() => handleToggleDay(schedule.id, day.value)}
                        disabled={disabled}
                        className={clsx(
                          'rounded px-3 py-1.5 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-card disabled:cursor-not-allowed disabled:opacity-50',
                          isSelected
                            ? 'bg-primary text-gray-900'
                            : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                        )}
                        aria-pressed={isSelected}
                      >
                        {day.label}
                      </button>
                    );
                  })}
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  Leave empty for all days
                </p>
              </div>

              {/* Time Range */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label
                    htmlFor={`start-time-${schedule.id}`}
                    className="mb-1 block text-xs font-medium text-text-secondary"
                  >
                    <Clock className="mr-1 inline-block h-3 w-3" />
                    Start Time
                  </label>
                  <input
                    type="time"
                    id={`start-time-${schedule.id}`}
                    value={schedule.startTime}
                    onChange={(e) => handleStartTimeChange(schedule.id, e.target.value)}
                    disabled={disabled}
                    className="block w-full rounded-lg border border-gray-800 bg-background px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </div>
                <div>
                  <label
                    htmlFor={`end-time-${schedule.id}`}
                    className="mb-1 block text-xs font-medium text-text-secondary"
                  >
                    <Clock className="mr-1 inline-block h-3 w-3" />
                    End Time
                  </label>
                  <input
                    type="time"
                    id={`end-time-${schedule.id}`}
                    value={schedule.endTime}
                    onChange={(e) => handleEndTimeChange(schedule.id, e.target.value)}
                    disabled={disabled}
                    className="block w-full rounded-lg border border-gray-800 bg-background px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Schedule Button */}
      <button
        type="button"
        onClick={handleAddSchedule}
        disabled={disabled}
        className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-gray-700 bg-card/50 px-4 py-3 text-sm font-medium text-text-secondary transition-colors hover:border-primary hover:bg-card hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="Add schedule"
      >
        <Plus className="h-4 w-4" />
        Add Schedule
      </button>
    </div>
  );
}
