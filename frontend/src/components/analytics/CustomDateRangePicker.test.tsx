/**
 * Tests for CustomDateRangePicker component
 *
 * Inline date pickers for selecting a custom date range.
 *
 * @see NEM-2702
 */

import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CustomDateRangePicker from './CustomDateRangePicker';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

describe('CustomDateRangePicker', () => {
  const mockOnApply = vi.fn();
  const mockOnCancel = vi.fn();

  const defaultProps = {
    initialStartDate: new Date('2026-01-01T00:00:00.000Z'),
    initialEndDate: new Date('2026-01-15T00:00:00.000Z'),
    onApply: mockOnApply,
    onCancel: mockOnCancel,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the date picker with test id', () => {
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    expect(screen.getByTestId('custom-date-picker')).toBeInTheDocument();
  });

  it('displays start date input with initial value', () => {
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    const startInput = screen.getByLabelText(/start date/i);
    expect(startInput).toBeInTheDocument();
    expect(startInput).toHaveValue('2026-01-01');
  });

  it('displays end date input with initial value', () => {
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    const endInput = screen.getByLabelText(/end date/i);
    expect(endInput).toBeInTheDocument();
    expect(endInput).toHaveValue('2026-01-15');
  });

  it('displays Apply and Cancel buttons', () => {
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    expect(screen.getByRole('button', { name: /apply/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('calls onCancel when Cancel button is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    expect(mockOnCancel).toHaveBeenCalled();
  });

  it('calls onApply with dates when Apply button is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    const applyButton = screen.getByRole('button', { name: /apply/i });
    await user.click(applyButton);

    expect(mockOnApply).toHaveBeenCalledWith(
      expect.any(Date),
      expect.any(Date)
    );
  });

  it('allows changing start date', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    const startInput = screen.getByLabelText(/start date/i);
    await user.clear(startInput);
    await user.type(startInput, '2026-02-01');

    expect(startInput).toHaveValue('2026-02-01');
  });

  it('allows changing end date', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    const endInput = screen.getByLabelText(/end date/i);
    await user.clear(endInput);
    await user.type(endInput, '2026-02-28');

    expect(endInput).toHaveValue('2026-02-28');
  });

  it('passes updated dates to onApply', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    const startInput = screen.getByLabelText(/start date/i);
    const endInput = screen.getByLabelText(/end date/i);

    await user.clear(startInput);
    await user.type(startInput, '2026-03-01');

    await user.clear(endInput);
    await user.type(endInput, '2026-03-31');

    const applyButton = screen.getByRole('button', { name: /apply/i });
    await user.click(applyButton);

    expect(mockOnApply).toHaveBeenCalled();
    const [startDate, endDate] = mockOnApply.mock.calls[0];
    expect(startDate.toISOString().split('T')[0]).toBe('2026-03-01');
    expect(endDate.toISOString().split('T')[0]).toBe('2026-03-31');
  });

  it('shows validation error when start date is after end date', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    const startInput = screen.getByLabelText(/start date/i);
    await user.clear(startInput);
    await user.type(startInput, '2026-12-31');

    // End date is 2026-01-15, which is before start date

    const applyButton = screen.getByRole('button', { name: /apply/i });
    await user.click(applyButton);

    await waitFor(() => {
      expect(screen.getByText(/start date must be before end date/i)).toBeInTheDocument();
    });

    // Should not call onApply with invalid range
    expect(mockOnApply).not.toHaveBeenCalled();
  });

  it('disables Apply button when dates are invalid', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

    const startInput = screen.getByLabelText(/start date/i);
    await user.clear(startInput);
    // Leave start date empty

    const applyButton = screen.getByRole('button', { name: /apply/i });
    expect(applyButton).toBeDisabled();
  });

  it('handles null initial dates gracefully', () => {
    renderWithProviders(
      <CustomDateRangePicker
        {...defaultProps}
        initialStartDate={null}
        initialEndDate={null}
      />
    );

    const startInput = screen.getByLabelText(/start date/i);
    const endInput = screen.getByLabelText(/end date/i);

    expect(startInput).toHaveValue('');
    expect(endInput).toHaveValue('');
  });

  describe('accessibility', () => {
    it('has proper labels for inputs', () => {
      renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

      expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
    });

    it('inputs have proper type="date"', () => {
      renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

      const startInput = screen.getByLabelText(/start date/i);
      const endInput = screen.getByLabelText(/end date/i);

      expect(startInput).toHaveAttribute('type', 'date');
      expect(endInput).toHaveAttribute('type', 'date');
    });

    it('error message has proper role', async () => {
      const user = userEvent.setup();
      renderWithProviders(<CustomDateRangePicker {...defaultProps} />);

      const startInput = screen.getByLabelText(/start date/i);
      await user.clear(startInput);
      await user.type(startInput, '2026-12-31');

      const applyButton = screen.getByRole('button', { name: /apply/i });
      await user.click(applyButton);

      await waitFor(() => {
        const errorMessage = screen.getByRole('alert');
        expect(errorMessage).toBeInTheDocument();
      });
    });
  });
});
