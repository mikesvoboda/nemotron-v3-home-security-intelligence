/**
 * Tests for AccessScheduleEditor component
 *
 * @see NEM-3608 Zone-Household Access Control UI
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AccessScheduleEditor from './AccessScheduleEditor';

import type { AccessSchedule } from '../../hooks/useZoneHouseholdConfig';
import type { HouseholdMember } from '../../hooks/useHouseholdApi';

// Test data
const mockMembers: HouseholdMember[] = [
  {
    id: 1,
    name: 'John Doe',
    role: 'resident',
    trusted_level: 'full',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Jane Smith',
    role: 'service_worker',
    trusted_level: 'partial',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

const mockSchedules: AccessSchedule[] = [
  {
    member_ids: [1],
    cron_expression: '0 9-17 * * 1,2,3,4,5',
    description: 'Weekday business hours',
  },
];

describe('AccessScheduleEditor', () => {
  const defaultProps = {
    schedules: [],
    onChange: vi.fn(),
    members: mockMembers,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state with add button', () => {
    render(<AccessScheduleEditor {...defaultProps} />);

    expect(screen.getByTestId('access-schedule-editor')).toBeInTheDocument();
    expect(screen.getByTestId('add-schedule-btn')).toBeInTheDocument();
    expect(screen.getByText('Add Access Schedule')).toBeInTheDocument();
  });

  it('displays existing schedules', () => {
    render(
      <AccessScheduleEditor
        {...defaultProps}
        schedules={mockSchedules}
      />
    );

    expect(screen.getByTestId('schedule-item')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Weekday business hours')).toBeInTheDocument();
  });

  it('opens schedule form when add button is clicked', async () => {
    const user = userEvent.setup();

    render(<AccessScheduleEditor {...defaultProps} />);

    await user.click(screen.getByTestId('add-schedule-btn'));

    expect(screen.getByTestId('schedule-form')).toBeInTheDocument();
    expect(screen.getByText('Members')).toBeInTheDocument();
    expect(screen.getByText('Time Range')).toBeInTheDocument();
    expect(screen.getByText('Days')).toBeInTheDocument();
  });

  it('allows selecting members in the form', async () => {
    const user = userEvent.setup();

    render(<AccessScheduleEditor {...defaultProps} />);

    await user.click(screen.getByTestId('add-schedule-btn'));

    // Click on John Doe to select
    const form = screen.getByTestId('schedule-form');
    const johnDoeBtn = within(form).getByText('John Doe');
    await user.click(johnDoeBtn);

    // Button should appear selected (has the green background class)
    expect(johnDoeBtn.className).toContain('bg-[#76B900]');
  });

  it('allows selecting days using quick presets', async () => {
    const user = userEvent.setup();

    render(<AccessScheduleEditor {...defaultProps} />);

    await user.click(screen.getByTestId('add-schedule-btn'));

    // Click weekdays preset
    await user.click(screen.getByText('Weekdays'));

    // All weekday buttons should be selected
    const monBtn = screen.getByRole('button', { name: 'Mon' });
    const satBtn = screen.getByRole('button', { name: 'Sat' });

    expect(monBtn.className).toContain('bg-[#76B900]');
    expect(satBtn.className).not.toContain('bg-[#76B900]');
  });

  it('calls onChange when schedule is saved', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<AccessScheduleEditor {...defaultProps} onChange={onChange} />);

    await user.click(screen.getByTestId('add-schedule-btn'));

    // Select a member
    const form = screen.getByTestId('schedule-form');
    await user.click(within(form).getByText('John Doe'));

    // Days are pre-selected to weekdays by default

    // Save the schedule
    await user.click(screen.getByText('Save Schedule'));

    expect(onChange).toHaveBeenCalled();
    const newSchedules = onChange.mock.calls[0][0];
    expect(newSchedules).toHaveLength(1);
    expect(newSchedules[0].member_ids).toContain(1);
    expect(newSchedules[0].cron_expression).toBeDefined();
  });

  it('validates that members are selected before saving', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<AccessScheduleEditor {...defaultProps} onChange={onChange} />);

    await user.click(screen.getByTestId('add-schedule-btn'));

    // Try to save without selecting members
    const saveButton = screen.getByText('Save Schedule');

    // Button should be disabled
    expect(saveButton).toBeDisabled();

    // onChange should not have been called
    expect(onChange).not.toHaveBeenCalled();
  });

  it('validates that days are selected before saving', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<AccessScheduleEditor {...defaultProps} onChange={onChange} />);

    await user.click(screen.getByTestId('add-schedule-btn'));

    // Select a member
    const form = screen.getByTestId('schedule-form');
    await user.click(within(form).getByText('John Doe'));

    // Deselect all days (they're pre-selected as weekdays)
    const monBtn = screen.getByRole('button', { name: 'Mon' });
    const tueBtn = screen.getByRole('button', { name: 'Tue' });
    const wedBtn = screen.getByRole('button', { name: 'Wed' });
    const thuBtn = screen.getByRole('button', { name: 'Thu' });
    const friBtn = screen.getByRole('button', { name: 'Fri' });

    await user.click(monBtn);
    await user.click(tueBtn);
    await user.click(wedBtn);
    await user.click(thuBtn);
    await user.click(friBtn);

    // Button should be disabled
    const saveButton = screen.getByText('Save Schedule');
    expect(saveButton).toBeDisabled();
  });

  it('allows canceling schedule creation', async () => {
    const user = userEvent.setup();

    render(<AccessScheduleEditor {...defaultProps} />);

    await user.click(screen.getByTestId('add-schedule-btn'));
    expect(screen.getByTestId('schedule-form')).toBeInTheDocument();

    await user.click(screen.getByText('Cancel'));

    expect(screen.queryByTestId('schedule-form')).not.toBeInTheDocument();
    expect(screen.getByTestId('add-schedule-btn')).toBeInTheDocument();
  });

  it('allows editing existing schedule', async () => {
    const user = userEvent.setup();

    render(
      <AccessScheduleEditor
        {...defaultProps}
        schedules={mockSchedules}
      />
    );

    // Click edit button on schedule item
    const editBtn = screen.getByRole('button', { name: 'Edit schedule' });
    await user.click(editBtn);

    // Form should appear with pre-filled data
    expect(screen.getByTestId('schedule-form')).toBeInTheDocument();
  });

  it('allows deleting schedule', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <AccessScheduleEditor
        {...defaultProps}
        schedules={mockSchedules}
        onChange={onChange}
      />
    );

    // Click delete button on schedule item
    const deleteBtn = screen.getByRole('button', { name: 'Delete schedule' });
    await user.click(deleteBtn);

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('disables add button when no members available', () => {
    render(
      <AccessScheduleEditor
        {...defaultProps}
        members={[]}
      />
    );

    expect(screen.getByTestId('add-schedule-btn')).toBeDisabled();
  });

  it('displays time range correctly', () => {
    render(
      <AccessScheduleEditor
        {...defaultProps}
        schedules={mockSchedules}
      />
    );

    // Should show parsed time range
    expect(screen.getByText('09:00 - 17:00')).toBeInTheDocument();
  });

  it('displays day labels correctly for weekdays', () => {
    render(
      <AccessScheduleEditor
        {...defaultProps}
        schedules={mockSchedules}
      />
    );

    expect(screen.getByText('Weekdays')).toBeInTheDocument();
  });

  it('allows entering description', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<AccessScheduleEditor {...defaultProps} onChange={onChange} />);

    await user.click(screen.getByTestId('add-schedule-btn'));

    // Select a member first
    const form = screen.getByTestId('schedule-form');
    await user.click(within(form).getByText('John Doe'));

    // Enter description
    const descInput = screen.getByPlaceholderText('e.g., Service workers during business hours');
    await user.type(descInput, 'Test schedule description');

    // Save
    await user.click(screen.getByText('Save Schedule'));

    expect(onChange).toHaveBeenCalled();
    const newSchedules = onChange.mock.calls[0][0];
    expect(newSchedules[0].description).toBe('Test schedule description');
  });

  it('disables all interactions when disabled prop is true', async () => {
    render(
      <AccessScheduleEditor
        {...defaultProps}
        schedules={mockSchedules}
        disabled={true}
      />
    );

    const addBtn = screen.getByTestId('add-schedule-btn');
    expect(addBtn).toBeDisabled();

    const editBtn = screen.getByRole('button', { name: 'Edit schedule' });
    expect(editBtn).toBeDisabled();

    const deleteBtn = screen.getByRole('button', { name: 'Delete schedule' });
    expect(deleteBtn).toBeDisabled();
  });
});
