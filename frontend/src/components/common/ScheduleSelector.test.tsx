import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import ScheduleSelector from './ScheduleSelector';

import type { AlertRuleSchedule } from '../../services/api';

describe('ScheduleSelector', () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock Intl.DateTimeFormat to return consistent timezone
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(() => ({
      resolvedOptions: () => ({ timeZone: 'America/New_York' }),
      format: () => '',
      formatToParts: () => [],
      formatRange: () => '',
      formatRangeToParts: () => [],
    } as unknown as Intl.DateTimeFormat));
  });

  describe('Initial Rendering', () => {
    it('renders with null value (schedule disabled)', () => {
      render(<ScheduleSelector value={null} onChange={mockOnChange} />);

      expect(screen.getByTestId('schedule-selector')).toBeInTheDocument();
      expect(screen.getByText('Schedule')).toBeInTheDocument();
      expect(screen.getByTestId('schedule-toggle')).toBeInTheDocument();
      // Content should not be visible when schedule is disabled
      expect(screen.queryByTestId('schedule-content')).not.toBeInTheDocument();
    });

    it('renders with schedule value (schedule enabled)', () => {
      const schedule: AlertRuleSchedule = {
        days: ['monday', 'wednesday', 'friday'],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'America/New_York',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      expect(screen.getByTestId('schedule-content')).toBeInTheDocument();
      expect(screen.getByLabelText('Start time')).toHaveValue('09:00');
      expect(screen.getByLabelText('End time')).toHaveValue('17:00');
    });

    it('displays selected days correctly', () => {
      const schedule: AlertRuleSchedule = {
        days: ['monday', 'wednesday'],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      // Monday and Wednesday should be selected
      const monButton = screen.getByRole('button', { name: 'Mon' });
      const wedButton = screen.getByRole('button', { name: 'Wed' });
      const friButton = screen.getByRole('button', { name: 'Fri' });

      expect(monButton).toHaveClass('bg-primary');
      expect(wedButton).toHaveClass('bg-primary');
      expect(friButton).not.toHaveClass('bg-primary');
    });
  });

  describe('Schedule Toggle', () => {
    it('enables schedule when toggle is clicked', async () => {
      const user = userEvent.setup();
      render(<ScheduleSelector value={null} onChange={mockOnChange} />);

      const toggle = screen.getByTestId('schedule-toggle');
      await user.click(toggle);

      expect(screen.getByTestId('schedule-content')).toBeInTheDocument();
      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        timezone: 'America/New_York',
      }));
    });

    it('disables schedule when toggle is clicked on enabled schedule', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: ['monday'],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const toggle = screen.getByTestId('schedule-toggle');
      await user.click(toggle);

      expect(mockOnChange).toHaveBeenCalledWith(null);
    });

    it('has correct aria-label when enabled', () => {
      const schedule: AlertRuleSchedule = {
        days: null,
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      expect(screen.getByLabelText('Schedule: enabled')).toBeInTheDocument();
    });

    it('has correct aria-label when disabled', () => {
      render(<ScheduleSelector value={null} onChange={mockOnChange} />);

      expect(screen.getByLabelText('Schedule: disabled')).toBeInTheDocument();
    });
  });

  describe('Day Selection', () => {
    it('selects a day when clicked', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const monButton = screen.getByRole('button', { name: 'Mon' });
      await user.click(monButton);

      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        days: ['monday'],
      }));
    });

    it('deselects a day when clicked again', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: ['monday', 'tuesday'],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const monButton = screen.getByRole('button', { name: 'Mon' });
      await user.click(monButton);

      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        days: ['tuesday'],
      }));
    });

    it('renders all seven days of the week', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      expect(screen.getByRole('button', { name: 'Mon' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Tue' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Wed' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Thu' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Fri' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Sat' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Sun' })).toBeInTheDocument();
    });
  });

  describe('Quick Day Options', () => {
    it('selects all days (clears selection) when "All Days" is clicked', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: ['monday', 'tuesday'],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const allDaysButton = screen.getByRole('button', { name: 'All Days' });
      await user.click(allDaysButton);

      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        days: null, // Empty array is converted to null
      }));
    });

    it('selects weekdays when "Weekdays" is clicked', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const weekdaysButton = screen.getByRole('button', { name: 'Weekdays' });
      await user.click(weekdaysButton);

      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
      }));
    });

    it('selects weekends when "Weekends" is clicked', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const weekendsButton = screen.getByRole('button', { name: 'Weekends' });
      await user.click(weekendsButton);

      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        days: ['saturday', 'sunday'],
      }));
    });

    it('highlights "Weekdays" button when weekdays are selected', () => {
      const schedule: AlertRuleSchedule = {
        days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const weekdaysButton = screen.getByRole('button', { name: 'Weekdays' });
      expect(weekdaysButton).toHaveClass('bg-primary');
    });

    it('highlights "Weekends" button when weekends are selected', () => {
      const schedule: AlertRuleSchedule = {
        days: ['saturday', 'sunday'],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const weekendsButton = screen.getByRole('button', { name: 'Weekends' });
      expect(weekendsButton).toHaveClass('bg-primary');
    });

    it('highlights "All Days" button when no days are selected', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const allDaysButton = screen.getByRole('button', { name: 'All Days' });
      expect(allDaysButton).toHaveClass('bg-primary');
    });
  });

  describe('Time Selection', () => {
    it('updates start time when changed', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const startTimeInput = screen.getByLabelText('Start time');
      await user.clear(startTimeInput);
      await user.type(startTimeInput, '10:30');

      expect(mockOnChange).toHaveBeenLastCalledWith(expect.objectContaining({
        start_time: '10:30',
      }));
    });

    it('updates end time when changed', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const endTimeInput = screen.getByLabelText('End time');
      await user.clear(endTimeInput);
      await user.type(endTimeInput, '18:00');

      expect(mockOnChange).toHaveBeenLastCalledWith(expect.objectContaining({
        end_time: '18:00',
      }));
    });

    it('supports overnight schedules (22:00-06:00)', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '22:00',
        end_time: '06:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      expect(screen.getByLabelText('Start time')).toHaveValue('22:00');
      expect(screen.getByLabelText('End time')).toHaveValue('06:00');
      // Should show helper text about overnight support
      expect(screen.getByText(/overnight schedules/i)).toBeInTheDocument();
    });

    it('sets all day (00:00-23:59) when "All Day" is clicked', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const allDayButton = screen.getByRole('button', { name: 'All Day' });
      await user.click(allDayButton);

      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        start_time: '00:00',
        end_time: '23:59',
      }));
    });

    it('highlights "All Day" button when times are 00:00-23:59', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '00:00',
        end_time: '23:59',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const allDayButton = screen.getByRole('button', { name: 'All Day' });
      expect(allDayButton).toHaveClass('bg-primary');
    });
  });

  describe('Timezone Selection', () => {
    it('displays common timezone options', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const timezoneSelect = screen.getByLabelText('Timezone');
      expect(timezoneSelect).toBeInTheDocument();

      // Check some timezone options exist
      expect(within(timezoneSelect).getByText('UTC')).toBeInTheDocument();
      expect(within(timezoneSelect).getByText(/Eastern/)).toBeInTheDocument();
      expect(within(timezoneSelect).getByText(/Pacific/)).toBeInTheDocument();
    });

    it('updates timezone when changed', async () => {
      const user = userEvent.setup();
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const timezoneSelect = screen.getByLabelText('Timezone');
      await user.selectOptions(timezoneSelect, 'America/Los_Angeles');

      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        timezone: 'America/Los_Angeles',
      }));
    });

    it('defaults to browser timezone when no timezone specified', async () => {
      // This test relies on the mocked Intl.DateTimeFormat above
      const user = userEvent.setup();
      render(<ScheduleSelector value={null} onChange={mockOnChange} />);

      // Enable schedule
      const toggle = screen.getByTestId('schedule-toggle');
      await user.click(toggle);

      // The onChange should be called with the browser timezone
      expect(mockOnChange).toHaveBeenCalledWith(expect.objectContaining({
        timezone: 'America/New_York',
      }));
    });
  });

  describe('Disabled State', () => {
    it('disables toggle when disabled prop is true', () => {
      render(<ScheduleSelector value={null} onChange={mockOnChange} disabled />);

      const toggle = screen.getByTestId('schedule-toggle');
      expect(toggle).toHaveClass('opacity-50', 'cursor-not-allowed');
    });

    it('disables all inputs when disabled prop is true', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} disabled />);

      expect(screen.getByLabelText('Start time')).toBeDisabled();
      expect(screen.getByLabelText('End time')).toBeDisabled();
      expect(screen.getByLabelText('Timezone')).toBeDisabled();
    });

    it('disables day buttons when disabled prop is true', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} disabled />);

      const monButton = screen.getByRole('button', { name: 'Mon' });
      expect(monButton).toHaveClass('opacity-50', 'cursor-not-allowed');
    });

    it('disables quick option buttons when disabled prop is true', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} disabled />);

      const allDaysButton = screen.getByRole('button', { name: 'All Days' });
      const weekdaysButton = screen.getByRole('button', { name: 'Weekdays' });
      const allDayButton = screen.getByRole('button', { name: 'All Day' });

      expect(allDaysButton).toHaveClass('opacity-50', 'cursor-not-allowed');
      expect(weekdaysButton).toHaveClass('opacity-50', 'cursor-not-allowed');
      expect(allDayButton).toHaveClass('opacity-50', 'cursor-not-allowed');
    });
  });

  describe('Accessibility', () => {
    it('has proper role group for days of week', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      expect(screen.getByRole('group', { name: 'Days of week' })).toBeInTheDocument();
    });

    it('has aria-pressed on day buttons', () => {
      const schedule: AlertRuleSchedule = {
        days: ['monday'],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const monButton = screen.getByRole('button', { name: 'Mon' });
      const tueButton = screen.getByRole('button', { name: 'Tue' });

      expect(monButton).toHaveAttribute('aria-pressed', 'true');
      expect(tueButton).toHaveAttribute('aria-pressed', 'false');
    });

    it('has aria-pressed on quick option buttons', () => {
      const schedule: AlertRuleSchedule = {
        days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      const weekdaysButton = screen.getByRole('button', { name: 'Weekdays' });
      expect(weekdaysButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('has labels for time inputs', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      expect(screen.getByLabelText('Start time')).toBeInTheDocument();
      expect(screen.getByLabelText('End time')).toBeInTheDocument();
      expect(screen.getByLabelText('Timezone')).toBeInTheDocument();
    });
  });

  describe('Custom className', () => {
    it('applies custom className to container', () => {
      render(
        <ScheduleSelector value={null} onChange={mockOnChange} className="custom-class" />
      );

      expect(screen.getByTestId('schedule-selector')).toHaveClass('custom-class');
    });
  });

  describe('Helper Text', () => {
    it('shows helper text for empty days', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '09:00',
        end_time: '17:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      expect(screen.getByText('Leave empty for all days')).toBeInTheDocument();
    });

    it('shows helper text for overnight schedules', () => {
      const schedule: AlertRuleSchedule = {
        days: [],
        start_time: '22:00',
        end_time: '06:00',
        timezone: 'UTC',
      };

      render(<ScheduleSelector value={schedule} onChange={mockOnChange} />);

      expect(screen.getByText(/overnight schedules/i)).toBeInTheDocument();
    });
  });
});
