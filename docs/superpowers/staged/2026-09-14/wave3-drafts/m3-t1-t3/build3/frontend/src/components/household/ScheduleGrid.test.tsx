import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import ScheduleGrid, {
  createEmptySchedule,
  createFullSchedule,
  createBusinessHoursSchedule,
} from './ScheduleGrid';

import type { WeeklySchedule } from '../../hooks/useHouseholdApi';

describe('ScheduleGrid', () => {
  const mockEmptySchedule: WeeklySchedule = {
    monday: [],
    tuesday: [],
    wednesday: [],
    thursday: [],
    friday: [],
    saturday: [],
    sunday: [],
  };

  const mockPartialSchedule: WeeklySchedule = {
    monday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    tuesday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    wednesday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    thursday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    friday: [9, 10, 11, 12, 13, 14, 15, 16, 17],
    saturday: [],
    sunday: [],
  };

  describe('Rendering', () => {
    it('renders the grid with all day labels', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      expect(screen.getByText('Mon')).toBeInTheDocument();
      expect(screen.getByText('Tue')).toBeInTheDocument();
      expect(screen.getByText('Wed')).toBeInTheDocument();
      expect(screen.getByText('Thu')).toBeInTheDocument();
      expect(screen.getByText('Fri')).toBeInTheDocument();
      expect(screen.getByText('Sat')).toBeInTheDocument();
      expect(screen.getByText('Sun')).toBeInTheDocument();
    });

    it('renders hour labels', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      // Every 3rd hour is labeled
      expect(screen.getByText('12am')).toBeInTheDocument();
      expect(screen.getByText('3am')).toBeInTheDocument();
      expect(screen.getByText('6am')).toBeInTheDocument();
      expect(screen.getByText('9am')).toBeInTheDocument();
      expect(screen.getByText('12pm')).toBeInTheDocument();
      expect(screen.getByText('3pm')).toBeInTheDocument();
      expect(screen.getByText('6pm')).toBeInTheDocument();
      expect(screen.getByText('9pm')).toBeInTheDocument();
    });

    it('renders cells for all 168 hour slots (7 days x 24 hours)', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      // Count all hour cells (they have aria-pressed attribute)
      const allHourCells = screen.getAllByRole('button', { pressed: false });
      // 7 days x 24 hours = 168 cells (all not pressed since empty schedule)
      expect(allHourCells.length).toBeGreaterThanOrEqual(168);
    });

    it('shows allowed cells in green', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockPartialSchedule} onChange={onChange} />);

      const mondayNineAm = screen.getByRole('button', { name: 'Mon 9am' });
      expect(mondayNineAm).toHaveClass('bg-[#76B900]');
    });

    it('shows not allowed cells in dark', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      const mondayNineAm = screen.getByRole('button', { name: 'Mon 9am' });
      expect(mondayNineAm).toHaveClass('bg-[#1A1A1A]');
    });

    it('renders legend', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      expect(screen.getByText('Allowed')).toBeInTheDocument();
      expect(screen.getByText('Not allowed')).toBeInTheDocument();
    });

    it('renders quick action buttons', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      expect(screen.getByRole('button', { name: 'Clear All' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Allow All' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Business Hours' })).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    it('toggles a cell when clicked', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      const mondayNineAm = screen.getByRole('button', { name: 'Mon 9am' });
      await user.click(mondayNineAm);

      expect(onChange).toHaveBeenCalledWith({
        ...mockEmptySchedule,
        monday: [9],
      });
    });

    it('removes hour when clicking an allowed cell', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockPartialSchedule} onChange={onChange} />);

      const mondayNineAm = screen.getByRole('button', { name: 'Mon 9am' });
      await user.click(mondayNineAm);

      expect(onChange).toHaveBeenCalledWith({
        ...mockPartialSchedule,
        monday: [10, 11, 12, 13, 14, 15, 16, 17],
      });
    });

    it('toggles all hours for a day when day label is clicked', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      // Find the Mon button (day label)
      const mondayLabel = screen.getByText('Mon');
      await user.click(mondayLabel);

      expect(onChange).toHaveBeenCalledWith({
        ...mockEmptySchedule,
        monday: Array.from({ length: 24 }, (_, i) => i),
      });
    });

    it('clears all hours for a day when all are allowed', async () => {
      const user = userEvent.setup();
      const fullMonday: WeeklySchedule = {
        ...mockEmptySchedule,
        monday: Array.from({ length: 24 }, (_, i) => i),
      };
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={fullMonday} onChange={onChange} />);

      // Find the Mon button (day label)
      const mondayLabel = screen.getByText('Mon');
      await user.click(mondayLabel);

      expect(onChange).toHaveBeenCalledWith({
        ...fullMonday,
        monday: [],
      });
    });

    it('Clear All button clears entire schedule', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockPartialSchedule} onChange={onChange} />);

      const clearAllButton = screen.getByRole('button', { name: 'Clear All' });
      await user.click(clearAllButton);

      expect(onChange).toHaveBeenCalledWith(createEmptySchedule());
    });

    it('Allow All button allows entire schedule', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      const allowAllButton = screen.getByRole('button', { name: 'Allow All' });
      await user.click(allowAllButton);

      expect(onChange).toHaveBeenCalledWith(createFullSchedule());
    });

    it('Business Hours button sets business hours schedule', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      const businessHoursButton = screen.getByRole('button', { name: 'Business Hours' });
      await user.click(businessHoursButton);

      expect(onChange).toHaveBeenCalledWith(createBusinessHoursSchedule());
    });
  });

  describe('Disabled state', () => {
    it('does not allow interaction when disabled', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} disabled />);

      const mondayNineAm = screen.getByRole('button', { name: 'Mon 9am' });
      await user.click(mondayNineAm);

      expect(onChange).not.toHaveBeenCalled();
    });

    it('disables quick action buttons when disabled', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} disabled />);

      expect(screen.getByRole('button', { name: 'Clear All' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Allow All' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Business Hours' })).toBeDisabled();
    });
  });

  describe('Accessibility', () => {
    it('cells have aria-pressed attribute', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockPartialSchedule} onChange={onChange} />);

      const allowedCell = screen.getByRole('button', { name: 'Mon 9am' });
      const notAllowedCell = screen.getByRole('button', { name: 'Sat 9am' });

      expect(allowedCell).toHaveAttribute('aria-pressed', 'true');
      expect(notAllowedCell).toHaveAttribute('aria-pressed', 'false');
    });

    it('cells have descriptive aria-labels', () => {
      const onChange = vi.fn();
      render(<ScheduleGrid schedule={mockEmptySchedule} onChange={onChange} />);

      expect(screen.getByRole('button', { name: 'Mon 9am' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Tue 12pm' })).toBeInTheDocument();
    });
  });

  describe('Helper functions', () => {
    it('createEmptySchedule returns schedule with no hours', () => {
      const schedule = createEmptySchedule();
      expect(schedule.monday).toHaveLength(0);
      expect(schedule.tuesday).toHaveLength(0);
      expect(schedule.wednesday).toHaveLength(0);
      expect(schedule.thursday).toHaveLength(0);
      expect(schedule.friday).toHaveLength(0);
      expect(schedule.saturday).toHaveLength(0);
      expect(schedule.sunday).toHaveLength(0);
    });

    it('createFullSchedule returns schedule with all hours', () => {
      const schedule = createFullSchedule();
      expect(schedule.monday).toHaveLength(24);
      expect(schedule.tuesday).toHaveLength(24);
      expect(schedule.wednesday).toHaveLength(24);
      expect(schedule.thursday).toHaveLength(24);
      expect(schedule.friday).toHaveLength(24);
      expect(schedule.saturday).toHaveLength(24);
      expect(schedule.sunday).toHaveLength(24);
    });

    it('createBusinessHoursSchedule returns weekday business hours', () => {
      const schedule = createBusinessHoursSchedule();
      expect(schedule.monday).toEqual([9, 10, 11, 12, 13, 14, 15, 16, 17]);
      expect(schedule.friday).toEqual([9, 10, 11, 12, 13, 14, 15, 16, 17]);
      expect(schedule.saturday).toHaveLength(0);
      expect(schedule.sunday).toHaveLength(0);
    });
  });
});
