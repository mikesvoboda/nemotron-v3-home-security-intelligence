import { Switch } from '@headlessui/react';
import { clsx } from 'clsx';
import { Calendar, Clock, Globe } from 'lucide-react';
import { useEffect, useState } from 'react';

import type { AlertRuleSchedule } from '../../services/api';

// Days of the week configuration
const DAYS_OF_WEEK = [
  { value: 'monday', label: 'Mon' },
  { value: 'tuesday', label: 'Tue' },
  { value: 'wednesday', label: 'Wed' },
  { value: 'thursday', label: 'Thu' },
  { value: 'friday', label: 'Fri' },
  { value: 'saturday', label: 'Sat' },
  { value: 'sunday', label: 'Sun' },
] as const;

// Weekday and weekend day values
const WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'];
const WEEKENDS = ['saturday', 'sunday'];

// Common timezone options
const TIMEZONE_OPTIONS = [
  { value: 'UTC', label: 'UTC' },
  { value: 'America/New_York', label: 'Eastern (America/New_York)' },
  { value: 'America/Chicago', label: 'Central (America/Chicago)' },
  { value: 'America/Denver', label: 'Mountain (America/Denver)' },
  { value: 'America/Los_Angeles', label: 'Pacific (America/Los_Angeles)' },
  { value: 'Europe/London', label: 'London (Europe/London)' },
  { value: 'Europe/Paris', label: 'Paris (Europe/Paris)' },
  { value: 'Asia/Tokyo', label: 'Tokyo (Asia/Tokyo)' },
];

export interface ScheduleSelectorProps {
  /** Current schedule value, null if no schedule (always active) */
  value: AlertRuleSchedule | null;
  /** Callback when schedule changes */
  onChange: (schedule: AlertRuleSchedule | null) => void;
  /** Whether the schedule section is disabled */
  disabled?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * ScheduleSelector component for configuring time-based schedules
 *
 * Features:
 * - Enable/disable schedule toggle
 * - Day of week checkboxes (Mon-Sun)
 * - Start time picker
 * - End time picker
 * - Timezone selector (auto-detect default)
 * - 'All Day' quick option
 * - 'Weekdays/Weekends' quick options
 *
 * Supports overnight schedules (e.g., 22:00-06:00)
 */
export default function ScheduleSelector({
  value,
  onChange,
  disabled = false,
  className,
}: ScheduleSelectorProps) {
  // Track whether schedule is enabled
  const [scheduleEnabled, setScheduleEnabled] = useState(value !== null);

  // Internal state for schedule configuration
  const [selectedDays, setSelectedDays] = useState<string[]>(value?.days || []);
  const [startTime, setStartTime] = useState(value?.start_time || '22:00');
  const [endTime, setEndTime] = useState(value?.end_time || '06:00');
  const [timezone, setTimezone] = useState(
    value?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  );

  // Sync internal state with prop value
  useEffect(() => {
    if (value) {
      setScheduleEnabled(true);
      setSelectedDays(value.days || []);
      setStartTime(value.start_time || '22:00');
      setEndTime(value.end_time || '06:00');
      setTimezone(value.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
    } else {
      setScheduleEnabled(false);
    }
  }, [value]);

  // Build and emit schedule when internal state changes
  const emitSchedule = (
    enabled: boolean,
    days: string[],
    start: string,
    end: string,
    tz: string
  ) => {
    if (!enabled) {
      onChange(null);
      return;
    }

    const schedule: AlertRuleSchedule = {
      days: days.length > 0 ? days : null,
      start_time: start || null,
      end_time: end || null,
      timezone: tz,
    };
    onChange(schedule);
  };

  // Handle schedule enable/disable toggle
  const handleToggleSchedule = (enabled: boolean) => {
    setScheduleEnabled(enabled);
    emitSchedule(enabled, selectedDays, startTime, endTime, timezone);
  };

  // Handle day selection
  const handleDayToggle = (day: string) => {
    const newDays = selectedDays.includes(day)
      ? selectedDays.filter((d) => d !== day)
      : [...selectedDays, day];
    setSelectedDays(newDays);
    emitSchedule(scheduleEnabled, newDays, startTime, endTime, timezone);
  };

  // Handle time changes
  const handleStartTimeChange = (time: string) => {
    setStartTime(time);
    emitSchedule(scheduleEnabled, selectedDays, time, endTime, timezone);
  };

  const handleEndTimeChange = (time: string) => {
    setEndTime(time);
    emitSchedule(scheduleEnabled, selectedDays, startTime, time, timezone);
  };

  // Handle timezone change
  const handleTimezoneChange = (tz: string) => {
    setTimezone(tz);
    emitSchedule(scheduleEnabled, selectedDays, startTime, endTime, tz);
  };

  // Quick option: Select all days (clear selection = all days)
  const handleAllDays = () => {
    setSelectedDays([]);
    emitSchedule(scheduleEnabled, [], startTime, endTime, timezone);
  };

  // Quick option: Select weekdays only
  const handleWeekdays = () => {
    setSelectedDays([...WEEKDAYS]);
    emitSchedule(scheduleEnabled, [...WEEKDAYS], startTime, endTime, timezone);
  };

  // Quick option: Select weekends only
  const handleWeekends = () => {
    setSelectedDays([...WEEKENDS]);
    emitSchedule(scheduleEnabled, [...WEEKENDS], startTime, endTime, timezone);
  };

  // Quick option: All day (clear time restriction)
  const handleAllDay = () => {
    setStartTime('00:00');
    setEndTime('23:59');
    emitSchedule(scheduleEnabled, selectedDays, '00:00', '23:59', timezone);
  };

  // Check if quick options are currently active
  const isAllDaysSelected = selectedDays.length === 0;
  const isWeekdaysSelected =
    selectedDays.length === 5 && WEEKDAYS.every((d) => selectedDays.includes(d));
  const isWeekendsSelected =
    selectedDays.length === 2 && WEEKENDS.every((d) => selectedDays.includes(d));
  const isAllDaySelected = startTime === '00:00' && endTime === '23:59';

  return (
    <div className={clsx('space-y-4', className)} data-testid="schedule-selector">
      {/* Header with enable toggle */}
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Calendar className="h-4 w-4 text-primary" />
          Schedule
        </h3>
        <Switch
          checked={scheduleEnabled}
          onChange={handleToggleSchedule}
          disabled={disabled}
          aria-label={`Schedule: ${scheduleEnabled ? 'enabled' : 'disabled'}`}
          data-testid="schedule-toggle"
          className={clsx(
            'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-panel',
            scheduleEnabled ? 'bg-primary' : 'bg-gray-600',
            disabled && 'cursor-not-allowed opacity-50'
          )}
        >
          <span
            className={clsx(
              'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
              scheduleEnabled ? 'translate-x-6' : 'translate-x-1'
            )}
          />
        </Switch>
      </div>

      {/* Schedule content (shown when enabled) */}
      {scheduleEnabled && (
        <div className="space-y-4 pl-6" data-testid="schedule-content">
          {/* Quick day options */}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleAllDays}
              disabled={disabled}
              aria-pressed={isAllDaysSelected}
              className={clsx(
                'rounded px-2 py-1 text-xs font-medium transition-colors',
                isAllDaysSelected
                  ? 'bg-primary text-gray-900'
                  : 'bg-gray-700 text-text-secondary hover:bg-gray-600',
                disabled && 'cursor-not-allowed opacity-50'
              )}
            >
              All Days
            </button>
            <button
              type="button"
              onClick={handleWeekdays}
              disabled={disabled}
              aria-pressed={isWeekdaysSelected}
              className={clsx(
                'rounded px-2 py-1 text-xs font-medium transition-colors',
                isWeekdaysSelected
                  ? 'bg-primary text-gray-900'
                  : 'bg-gray-700 text-text-secondary hover:bg-gray-600',
                disabled && 'cursor-not-allowed opacity-50'
              )}
            >
              Weekdays
            </button>
            <button
              type="button"
              onClick={handleWeekends}
              disabled={disabled}
              aria-pressed={isWeekendsSelected}
              className={clsx(
                'rounded px-2 py-1 text-xs font-medium transition-colors',
                isWeekendsSelected
                  ? 'bg-primary text-gray-900'
                  : 'bg-gray-700 text-text-secondary hover:bg-gray-600',
                disabled && 'cursor-not-allowed opacity-50'
              )}
            >
              Weekends
            </button>
          </div>

          {/* Day of week buttons */}
          <div>
            <span className="block text-sm font-medium text-text-primary">Days</span>
            <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Days of week">
              {DAYS_OF_WEEK.map((day) => (
                <button
                  key={day.value}
                  type="button"
                  onClick={() => handleDayToggle(day.value)}
                  disabled={disabled}
                  aria-pressed={selectedDays.includes(day.value)}
                  className={clsx(
                    'rounded px-3 py-1.5 text-sm font-medium transition-colors',
                    selectedDays.includes(day.value)
                      ? 'bg-primary text-gray-900'
                      : 'bg-gray-700 text-text-secondary hover:bg-gray-600',
                    disabled && 'cursor-not-allowed opacity-50'
                  )}
                >
                  {day.label}
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-text-secondary">
              Leave empty for all days
            </p>
          </div>

          {/* Time selection */}
          <div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-sm font-medium text-text-primary">
                <Clock className="h-4 w-4 text-primary" />
                Time Range
              </span>
              <button
                type="button"
                onClick={handleAllDay}
                disabled={disabled}
                aria-pressed={isAllDaySelected}
                className={clsx(
                  'rounded px-2 py-1 text-xs font-medium transition-colors',
                  isAllDaySelected
                    ? 'bg-primary text-gray-900'
                    : 'bg-gray-700 text-text-secondary hover:bg-gray-600',
                  disabled && 'cursor-not-allowed opacity-50'
                )}
              >
                All Day
              </button>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="start_time" className="block text-xs text-text-secondary">
                  Start Time
                </label>
                <input
                  type="time"
                  id="start_time"
                  value={startTime}
                  onChange={(e) => handleStartTimeChange(e.target.value)}
                  disabled={disabled}
                  aria-label="Start time"
                  className={clsx(
                    'mt-1 block w-full rounded-lg border border-gray-800 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary',
                    disabled && 'cursor-not-allowed opacity-50'
                  )}
                />
              </div>
              <div>
                <label htmlFor="end_time" className="block text-xs text-text-secondary">
                  End Time
                </label>
                <input
                  type="time"
                  id="end_time"
                  value={endTime}
                  onChange={(e) => handleEndTimeChange(e.target.value)}
                  disabled={disabled}
                  aria-label="End time"
                  className={clsx(
                    'mt-1 block w-full rounded-lg border border-gray-800 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary',
                    disabled && 'cursor-not-allowed opacity-50'
                  )}
                />
              </div>
            </div>
            <p className="mt-1 text-xs text-text-secondary">
              Supports overnight schedules (e.g., 22:00-06:00)
            </p>
          </div>

          {/* Timezone selector */}
          <div>
            <label
              htmlFor="timezone"
              className="flex items-center gap-2 text-sm font-medium text-text-primary"
            >
              <Globe className="h-4 w-4 text-primary" />
              Timezone
            </label>
            <select
              id="timezone"
              value={timezone}
              onChange={(e) => handleTimezoneChange(e.target.value)}
              disabled={disabled}
              aria-label="Timezone"
              className={clsx(
                'mt-1 block w-full rounded-lg border border-gray-800 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary',
                disabled && 'cursor-not-allowed opacity-50'
              )}
            >
              {TIMEZONE_OPTIONS.map((tz) => (
                <option key={tz.value} value={tz.value}>
                  {tz.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}
