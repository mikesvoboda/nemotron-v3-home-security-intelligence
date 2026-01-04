import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ScheduleSelector from './ScheduleSelector';

import type { Schedule, ScheduleSelectorProps } from './ScheduleSelector';

describe('ScheduleSelector', () => {
  const mockOnChange = vi.fn();

  const defaultProps: ScheduleSelectorProps = {
    schedules: [],
    onChange: mockOnChange,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Empty State', () => {
    it('renders add schedule button when no schedules exist', () => {
      render(<ScheduleSelector {...defaultProps} />);

      expect(screen.getByRole('button', { name: /add schedule/i })).toBeInTheDocument();
    });

    it('displays informative message when no schedules configured', () => {
      render(<ScheduleSelector {...defaultProps} />);

      expect(screen.getByText(/no schedules configured/i)).toBeInTheDocument();
    });
  });

  describe('Adding Schedules', () => {
    it('adds a new schedule when add button is clicked', async () => {
      const user = userEvent.setup();
      render(<ScheduleSelector {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /add schedule/i }));

      expect(mockOnChange).toHaveBeenCalledTimes(1);
      const newSchedules = mockOnChange.mock.calls[0][0];
      expect(newSchedules).toHaveLength(1);
      expect(newSchedules[0]).toMatchObject({
        days: [],
        startTime: '00:00',
        endTime: '23:59',
      });
      expect(newSchedules[0].id).toBeDefined();
    });

    it('generates unique IDs for new schedules', async () => {
      const user = userEvent.setup();
      let currentSchedules: Schedule[] = [];

      const { rerender } = render(
        <ScheduleSelector
          schedules={currentSchedules}
          onChange={(schedules) => {
            currentSchedules = schedules;
            mockOnChange(schedules);
          }}
        />
      );

      await user.click(screen.getByRole('button', { name: /add schedule/i }));

      rerender(
        <ScheduleSelector
          schedules={currentSchedules}
          onChange={(schedules) => {
            currentSchedules = schedules;
            mockOnChange(schedules);
          }}
        />
      );

      await user.click(screen.getByRole('button', { name: /add schedule/i }));

      const firstId = mockOnChange.mock.calls[0][0][0].id;
      const secondId = mockOnChange.mock.calls[1][0][1].id;
      expect(firstId).not.toEqual(secondId);
    });
  });

  describe('Removing Schedules', () => {
    const existingSchedules: Schedule[] = [
      { id: 'schedule-1', days: ['mon', 'tue'], startTime: '09:00', endTime: '17:00' },
      { id: 'schedule-2', days: ['sat', 'sun'], startTime: '10:00', endTime: '18:00' },
    ];

    it('removes a schedule when delete button is clicked', async () => {
      const user = userEvent.setup();
      render(<ScheduleSelector schedules={existingSchedules} onChange={mockOnChange} />);

      const removeButtons = screen.getAllByRole('button', { name: /remove schedule/i });
      await user.click(removeButtons[0]);

      expect(mockOnChange).toHaveBeenCalledTimes(1);
      const updatedSchedules = mockOnChange.mock.calls[0][0];
      expect(updatedSchedules).toHaveLength(1);
      expect(updatedSchedules[0].id).toBe('schedule-2');
    });

    it('removes correct schedule when multiple exist', async () => {
      const user = userEvent.setup();
      render(<ScheduleSelector schedules={existingSchedules} onChange={mockOnChange} />);

      const removeButtons = screen.getAllByRole('button', { name: /remove schedule/i });
      await user.click(removeButtons[1]); // Click second remove button

      expect(mockOnChange).toHaveBeenCalledWith([existingSchedules[0]]);
    });
  });

  describe('Day Selection', () => {
    const scheduleWithDays: Schedule[] = [
      { id: 'schedule-1', days: ['mon', 'wed', 'fri'], startTime: '09:00', endTime: '17:00' },
    ];

    it('displays all seven days of the week', () => {
      render(<ScheduleSelector schedules={scheduleWithDays} onChange={mockOnChange} />);

      expect(screen.getByRole('button', { name: /mon/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /tue/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /wed/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /thu/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /fri/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sat/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sun/i })).toBeInTheDocument();
    });

    it('highlights selected days', () => {
      render(<ScheduleSelector schedules={scheduleWithDays} onChange={mockOnChange} />);

      const monButton = screen.getByRole('button', { name: /^mon$/i });
      const wedButton = screen.getByRole('button', { name: /^wed$/i });
      const friButton = screen.getByRole('button', { name: /^fri$/i });
      const tueButton = screen.getByRole('button', { name: /^tue$/i });

      expect(monButton).toHaveClass('bg-primary');
      expect(wedButton).toHaveClass('bg-primary');
      expect(friButton).toHaveClass('bg-primary');
      expect(tueButton).not.toHaveClass('bg-primary');
    });

    it('toggles day selection on click', async () => {
      const user = userEvent.setup();
      render(<ScheduleSelector schedules={scheduleWithDays} onChange={mockOnChange} />);

      // Add Tuesday
      const tueButton = screen.getByRole('button', { name: /^tue$/i });
      await user.click(tueButton);

      expect(mockOnChange).toHaveBeenCalledWith([
        {
          id: 'schedule-1',
          days: ['mon', 'wed', 'fri', 'tue'],
          startTime: '09:00',
          endTime: '17:00',
        },
      ]);
    });

    it('removes day when already selected', async () => {
      const user = userEvent.setup();
      render(<ScheduleSelector schedules={scheduleWithDays} onChange={mockOnChange} />);

      // Remove Monday
      const monButton = screen.getByRole('button', { name: /^mon$/i });
      await user.click(monButton);

      expect(mockOnChange).toHaveBeenCalledWith([
        {
          id: 'schedule-1',
          days: ['wed', 'fri'],
          startTime: '09:00',
          endTime: '17:00',
        },
      ]);
    });
  });

  describe('Time Selection', () => {
    const scheduleWithTimes: Schedule[] = [
      { id: 'schedule-1', days: ['mon'], startTime: '09:00', endTime: '17:00' },
    ];

    it('displays start and end time inputs', () => {
      render(<ScheduleSelector schedules={scheduleWithTimes} onChange={mockOnChange} />);

      expect(screen.getByLabelText(/start time/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/end time/i)).toBeInTheDocument();
    });

    it('shows correct initial time values', () => {
      render(<ScheduleSelector schedules={scheduleWithTimes} onChange={mockOnChange} />);

      const startTimeInput = screen.getByLabelText(/start time/i);
      const endTimeInput = screen.getByLabelText(/end time/i);

      expect((startTimeInput as HTMLInputElement).value).toBe('09:00');
      expect((endTimeInput as HTMLInputElement).value).toBe('17:00');
    });

    it('updates start time on change', async () => {
      render(<ScheduleSelector schedules={scheduleWithTimes} onChange={mockOnChange} />);

      const startTimeInput = screen.getByLabelText(/start time/i);

      // Use fireEvent.change for time inputs as userEvent doesn't handle them well
      startTimeInput.focus();
      await userEvent.clear(startTimeInput);
      // Directly fire the change event with a new value
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set?.call(
        startTimeInput,
        '08:30'
      );
      startTimeInput.dispatchEvent(new Event('change', { bubbles: true }));

      // Check that onChange was called with the updated start time
      expect(mockOnChange).toHaveBeenCalled();
      const lastCall = mockOnChange.mock.calls[mockOnChange.mock.calls.length - 1][0];
      expect(lastCall[0].startTime).toBe('08:30');
    });

    it('updates end time on change', async () => {
      render(<ScheduleSelector schedules={scheduleWithTimes} onChange={mockOnChange} />);

      const endTimeInput = screen.getByLabelText(/end time/i);

      // Use fireEvent.change for time inputs as userEvent doesn't handle them well
      endTimeInput.focus();
      await userEvent.clear(endTimeInput);
      // Directly fire the change event with a new value
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set?.call(
        endTimeInput,
        '18:30'
      );
      endTimeInput.dispatchEvent(new Event('change', { bubbles: true }));

      // Check that onChange was called with the updated end time
      expect(mockOnChange).toHaveBeenCalled();
      const lastCall = mockOnChange.mock.calls[mockOnChange.mock.calls.length - 1][0];
      expect(lastCall[0].endTime).toBe('18:30');
    });
  });

  describe('Multiple Schedules', () => {
    const multipleSchedules: Schedule[] = [
      { id: 'weekday', days: ['mon', 'tue', 'wed', 'thu', 'fri'], startTime: '09:00', endTime: '17:00' },
      { id: 'weekend', days: ['sat', 'sun'], startTime: '10:00', endTime: '16:00' },
    ];

    it('renders all schedules', () => {
      render(<ScheduleSelector schedules={multipleSchedules} onChange={mockOnChange} />);

      // Should have two schedule sections
      const startTimeInputs = screen.getAllByLabelText(/start time/i);
      const endTimeInputs = screen.getAllByLabelText(/end time/i);

      expect(startTimeInputs).toHaveLength(2);
      expect(endTimeInputs).toHaveLength(2);
    });

    it('displays schedule numbers/labels', () => {
      render(<ScheduleSelector schedules={multipleSchedules} onChange={mockOnChange} />);

      expect(screen.getByText(/schedule 1/i)).toBeInTheDocument();
      expect(screen.getByText(/schedule 2/i)).toBeInTheDocument();
    });

    it('updates correct schedule when editing', async () => {
      const user = userEvent.setup();
      render(<ScheduleSelector schedules={multipleSchedules} onChange={mockOnChange} />);

      // Get the second schedule's inputs using data-testid or container
      const scheduleContainers = screen.getAllByTestId('schedule-entry');
      const secondSchedule = scheduleContainers[1];
      const satButton = within(secondSchedule).getByRole('button', { name: /^sat$/i });

      await user.click(satButton);

      const lastCall = mockOnChange.mock.calls[mockOnChange.mock.calls.length - 1][0];
      // First schedule should be unchanged
      expect(lastCall[0]).toEqual(multipleSchedules[0]);
      // Second schedule should have sat removed
      expect(lastCall[1].days).toEqual(['sun']);
    });
  });

  describe('Disabled State', () => {
    const existingSchedule: Schedule[] = [
      { id: 'schedule-1', days: ['mon'], startTime: '09:00', endTime: '17:00' },
    ];

    it('disables all inputs when disabled prop is true', () => {
      render(<ScheduleSelector schedules={existingSchedule} onChange={mockOnChange} disabled />);

      expect(screen.getByLabelText(/start time/i)).toBeDisabled();
      expect(screen.getByLabelText(/end time/i)).toBeDisabled();
      expect(screen.getByRole('button', { name: /add schedule/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /remove schedule/i })).toBeDisabled();
    });

    it('disables day selection buttons when disabled', () => {
      render(<ScheduleSelector schedules={existingSchedule} onChange={mockOnChange} disabled />);

      const dayButtons = screen.getAllByRole('button', { name: /^(mon|tue|wed|thu|fri|sat|sun)$/i });
      dayButtons.forEach((button) => {
        expect(button).toBeDisabled();
      });
    });

    it('does not call onChange when disabled and interacted with', async () => {
      const user = userEvent.setup();
      render(<ScheduleSelector schedules={existingSchedule} onChange={mockOnChange} disabled />);

      // Try to add a schedule
      const addButton = screen.getByRole('button', { name: /add schedule/i });
      await user.click(addButton);

      expect(mockOnChange).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    const existingSchedule: Schedule[] = [
      { id: 'schedule-1', days: ['mon', 'tue'], startTime: '09:00', endTime: '17:00' },
    ];

    it('has proper aria-labels for day buttons', () => {
      render(<ScheduleSelector schedules={existingSchedule} onChange={mockOnChange} />);

      // Day buttons should be accessible
      expect(screen.getByRole('button', { name: /mon/i })).toBeInTheDocument();
    });

    it('has proper labels for time inputs', () => {
      render(<ScheduleSelector schedules={existingSchedule} onChange={mockOnChange} />);

      // Time inputs should have associated labels
      const startInput = screen.getByLabelText(/start time/i);
      const endInput = screen.getByLabelText(/end time/i);

      expect(startInput).toHaveAttribute('type', 'time');
      expect(endInput).toHaveAttribute('type', 'time');
    });

    it('has descriptive aria-label for remove button', () => {
      render(<ScheduleSelector schedules={existingSchedule} onChange={mockOnChange} />);

      expect(screen.getByRole('button', { name: /remove schedule/i })).toBeInTheDocument();
    });

    it('has descriptive aria-label for add button', () => {
      render(<ScheduleSelector schedules={existingSchedule} onChange={mockOnChange} />);

      expect(screen.getByRole('button', { name: /add schedule/i })).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies custom className', () => {
      render(
        <ScheduleSelector
          schedules={[]}
          onChange={mockOnChange}
          className="custom-test-class"
        />
      );

      const container = screen.getByTestId('schedule-selector');
      expect(container).toHaveClass('custom-test-class');
    });

    it('renders with default NVIDIA dark theme styling', () => {
      const existingSchedule: Schedule[] = [
        { id: 'schedule-1', days: ['mon'], startTime: '09:00', endTime: '17:00' },
      ];

      render(<ScheduleSelector schedules={existingSchedule} onChange={mockOnChange} />);

      // Check that schedule entries have dark theme classes
      const scheduleEntry = screen.getByTestId('schedule-entry');
      expect(scheduleEntry).toHaveClass('bg-card');
    });
  });

  describe('Edge Cases', () => {
    it('handles empty days array', () => {
      const scheduleWithNoDays: Schedule[] = [
        { id: 'schedule-1', days: [], startTime: '09:00', endTime: '17:00' },
      ];

      render(<ScheduleSelector schedules={scheduleWithNoDays} onChange={mockOnChange} />);

      // All day buttons should not be selected
      const dayButtons = screen.getAllByRole('button', { name: /^(mon|tue|wed|thu|fri|sat|sun)$/i });
      dayButtons.forEach((button) => {
        expect(button).not.toHaveClass('bg-primary');
      });
    });

    it('handles all days selected', () => {
      const scheduleWithAllDays: Schedule[] = [
        { id: 'schedule-1', days: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'], startTime: '00:00', endTime: '23:59' },
      ];

      render(<ScheduleSelector schedules={scheduleWithAllDays} onChange={mockOnChange} />);

      // All day buttons should be selected
      const dayButtons = screen.getAllByRole('button', { name: /^(mon|tue|wed|thu|fri|sat|sun)$/i });
      dayButtons.forEach((button) => {
        expect(button).toHaveClass('bg-primary');
      });
    });

    it('handles overnight schedules (end time before start time)', () => {
      const overnightSchedule: Schedule[] = [
        { id: 'schedule-1', days: ['mon'], startTime: '22:00', endTime: '06:00' },
      ];

      render(<ScheduleSelector schedules={overnightSchedule} onChange={mockOnChange} />);

      const startTimeInput = screen.getByLabelText(/start time/i);
      const endTimeInput = screen.getByLabelText(/end time/i);

      expect((startTimeInput as HTMLInputElement).value).toBe('22:00');
      expect((endTimeInput as HTMLInputElement).value).toBe('06:00');
    });
  });
});
