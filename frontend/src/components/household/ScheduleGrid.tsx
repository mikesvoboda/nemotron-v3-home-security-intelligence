/**
 * ScheduleGrid - Weekly schedule editor component
 *
 * A 7x24 grid for editing member access schedules.
 * Each cell represents one hour of one day of the week.
 * Users can click to toggle individual cells or drag to select multiple.
 *
 * @module components/household/ScheduleGrid
 * @see NEM-4858 Phase 3 - Schedule Management
 */

import { useCallback, useState, useRef } from 'react';

import type { WeeklySchedule, DayOfWeek } from '../../hooks/useHouseholdApi';

// ============================================================================
// Constants
// ============================================================================

const DAYS: DayOfWeek[] = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
];

const DAY_LABELS: Record<DayOfWeek, string> = {
  monday: 'Mon',
  tuesday: 'Tue',
  wednesday: 'Wed',
  thursday: 'Thu',
  friday: 'Fri',
  saturday: 'Sat',
  sunday: 'Sun',
};

const HOURS = Array.from({ length: 24 }, (_, i) => i);

// ============================================================================
// Types
// ============================================================================

interface ScheduleGridProps {
  schedule: WeeklySchedule;
  onChange: (schedule: WeeklySchedule) => void;
  disabled?: boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format hour for display (e.g., "9am", "3pm", "12pm").
 */
function formatHour(hour: number): string {
  if (hour === 0) return '12am';
  if (hour === 12) return '12pm';
  if (hour < 12) return `${hour}am`;
  return `${hour - 12}pm`;
}

/**
 * Check if an hour is allowed in the schedule.
 */
function isHourAllowed(schedule: WeeklySchedule, day: DayOfWeek, hour: number): boolean {
  return schedule[day].includes(hour);
}

/**
 * Create an empty schedule (no hours allowed).
 */
// eslint-disable-next-line react-refresh/only-export-components -- Schedule factory function
export function createEmptySchedule(): WeeklySchedule {
  return {
    monday: [],
    tuesday: [],
    wednesday: [],
    thursday: [],
    friday: [],
    saturday: [],
    sunday: [],
  };
}

/**
 * Create a full schedule (all hours allowed).
 */
// eslint-disable-next-line react-refresh/only-export-components -- Schedule factory function
export function createFullSchedule(): WeeklySchedule {
  const allHours = HOURS.slice();
  return {
    monday: [...allHours],
    tuesday: [...allHours],
    wednesday: [...allHours],
    thursday: [...allHours],
    friday: [...allHours],
    saturday: [...allHours],
    sunday: [...allHours],
  };
}

/**
 * Create a business hours schedule (9am-5pm weekdays).
 */
// eslint-disable-next-line react-refresh/only-export-components -- Schedule factory function
export function createBusinessHoursSchedule(): WeeklySchedule {
  const businessHours = [9, 10, 11, 12, 13, 14, 15, 16, 17];
  return {
    monday: [...businessHours],
    tuesday: [...businessHours],
    wednesday: [...businessHours],
    thursday: [...businessHours],
    friday: [...businessHours],
    saturday: [],
    sunday: [],
  };
}

// ============================================================================
// Component
// ============================================================================

export default function ScheduleGrid({
  schedule,
  onChange,
  disabled = false,
}: ScheduleGridProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [dragValue, setDragValue] = useState(false);
  const gridRef = useRef<HTMLDivElement>(null);

  /**
   * Toggle a single cell.
   */
  const toggleCell = useCallback(
    (day: DayOfWeek, hour: number, forceValue?: boolean) => {
      if (disabled) return;

      const currentlyAllowed = isHourAllowed(schedule, day, hour);
      const newValue = forceValue !== undefined ? forceValue : !currentlyAllowed;

      const newSchedule = { ...schedule };
      if (newValue && !currentlyAllowed) {
        // Add hour
        newSchedule[day] = [...schedule[day], hour].sort((a, b) => a - b);
      } else if (!newValue && currentlyAllowed) {
        // Remove hour
        newSchedule[day] = schedule[day].filter((h) => h !== hour);
      }

      onChange(newSchedule);
    },
    [schedule, onChange, disabled]
  );

  /**
   * Handle mouse down on a cell.
   */
  const handleMouseDown = useCallback(
    (day: DayOfWeek, hour: number) => {
      if (disabled) return;
      setIsDragging(true);
      const currentlyAllowed = isHourAllowed(schedule, day, hour);
      setDragValue(!currentlyAllowed);
      toggleCell(day, hour, !currentlyAllowed);
    },
    [disabled, schedule, toggleCell]
  );

  /**
   * Handle mouse enter on a cell during drag.
   */
  const handleMouseEnter = useCallback(
    (day: DayOfWeek, hour: number) => {
      if (!isDragging || disabled) return;
      toggleCell(day, hour, dragValue);
    },
    [isDragging, disabled, dragValue, toggleCell]
  );

  /**
   * Handle mouse up to end drag.
   */
  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  /**
   * Toggle all hours for a day.
   */
  const toggleDay = useCallback(
    (day: DayOfWeek) => {
      if (disabled) return;
      const allAllowed = schedule[day].length === 24;
      const newSchedule = { ...schedule };
      newSchedule[day] = allAllowed ? [] : HOURS.slice();
      onChange(newSchedule);
    },
    [schedule, onChange, disabled]
  );

  /**
   * Toggle all days for an hour.
   */
  const toggleHour = useCallback(
    (hour: number) => {
      if (disabled) return;
      const allAllowed = DAYS.every((day) => schedule[day].includes(hour));
      const newSchedule = { ...schedule };
      for (const day of DAYS) {
        if (allAllowed) {
          // Remove hour from all days
          newSchedule[day] = schedule[day].filter((h) => h !== hour);
        } else {
          // Add hour to all days
          if (!schedule[day].includes(hour)) {
            newSchedule[day] = [...schedule[day], hour].sort((a, b) => a - b);
          }
        }
      }
      onChange(newSchedule);
    },
    [schedule, onChange, disabled]
  );

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- Mouse handlers for drag selection
    <div
      ref={gridRef}
      className="select-none"
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Header row with hour labels */}
      <div className="flex">
        {/* Empty corner cell */}
        <div className="w-12 h-6 flex-shrink-0" />
        {/* Hour headers */}
        <div className="flex-1 flex">
          {HOURS.map((hour) => (
            <button
              key={hour}
              type="button"
              onClick={() => toggleHour(hour)}
              disabled={disabled}
              className="flex-1 h-6 text-[9px] text-gray-400 hover:text-white hover:bg-[#76B900]/20 transition-colors disabled:hover:bg-transparent disabled:text-gray-600"
              title={`Toggle ${formatHour(hour)} for all days`}
            >
              {hour % 3 === 0 ? formatHour(hour) : ''}
            </button>
          ))}
        </div>
      </div>

      {/* Day rows */}
      {DAYS.map((day) => (
        <div key={day} className="flex">
          {/* Day label */}
          <button
            type="button"
            onClick={() => toggleDay(day)}
            disabled={disabled}
            className="w-12 h-6 text-xs text-gray-400 hover:text-white hover:bg-[#76B900]/20 transition-colors text-left pl-1 disabled:hover:bg-transparent disabled:text-gray-600"
            title={`Toggle all hours for ${DAY_LABELS[day]}`}
          >
            {DAY_LABELS[day]}
          </button>
          {/* Hour cells */}
          <div className="flex-1 flex">
            {HOURS.map((hour) => {
              const allowed = isHourAllowed(schedule, day, hour);
              return (
                <button
                  key={hour}
                  type="button"
                  onMouseDown={() => handleMouseDown(day, hour)}
                  onMouseEnter={() => handleMouseEnter(day, hour)}
                  disabled={disabled}
                  className={`flex-1 h-6 border border-gray-800 transition-colors ${
                    allowed
                      ? 'bg-[#76B900] hover:bg-[#5a8f00]'
                      : 'bg-[#1A1A1A] hover:bg-gray-700'
                  } ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
                  title={`${DAY_LABELS[day]} ${formatHour(hour)}: ${allowed ? 'Allowed' : 'Not allowed'}`}
                  aria-label={`${DAY_LABELS[day]} ${formatHour(hour)}`}
                  aria-pressed={allowed}
                />
              );
            })}
          </div>
        </div>
      ))}

      {/* Legend and quick actions */}
      <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-[#76B900] rounded" />
            <span>Allowed</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-[#1A1A1A] border border-gray-700 rounded" />
            <span>Not allowed</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onChange(createEmptySchedule())}
            disabled={disabled}
            className="px-2 py-1 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
          >
            Clear All
          </button>
          <button
            type="button"
            onClick={() => onChange(createFullSchedule())}
            disabled={disabled}
            className="px-2 py-1 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
          >
            Allow All
          </button>
          <button
            type="button"
            onClick={() => onChange(createBusinessHoursSchedule())}
            disabled={disabled}
            className="px-2 py-1 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
          >
            Business Hours
          </button>
        </div>
      </div>
    </div>
  );
}
