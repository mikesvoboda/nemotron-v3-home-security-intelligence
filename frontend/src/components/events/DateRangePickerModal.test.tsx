import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import DateRangePickerModal, { type DateRangePickerModalProps } from './DateRangePickerModal';

describe('DateRangePickerModal', () => {
  const defaultProps: DateRangePickerModalProps = {
    isOpen: true,
    onClose: vi.fn(),
    onApply: vi.fn(),
  };

  // Fixed date for consistent testing
  const MOCK_DATE = new Date('2024-01-15T12:00:00Z');

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(MOCK_DATE);
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('rendering', () => {
    it('renders modal when isOpen is true', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByTestId('date-range-picker-modal')).toBeInTheDocument();
    });

    it('does not render modal when isOpen is false', () => {
      render(<DateRangePickerModal {...defaultProps} isOpen={false} />);
      expect(screen.queryByTestId('date-range-picker-modal')).not.toBeInTheDocument();
    });

    it('renders modal title', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByText('Select Date Range')).toBeInTheDocument();
    });

    it('renders close button', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByTestId('date-range-picker-close')).toBeInTheDocument();
    });

    it('renders start date input', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByTestId('start-date-input')).toBeInTheDocument();
    });

    it('renders end date input', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByTestId('end-date-input')).toBeInTheDocument();
    });

    it('renders cancel button', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByTestId('date-range-cancel')).toBeInTheDocument();
    });

    it('renders apply button', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByTestId('date-range-apply')).toBeInTheDocument();
    });
  });

  describe('preset buttons', () => {
    it('renders Today preset button', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByTestId('preset-today')).toBeInTheDocument();
    });

    it('renders Last 7 days preset button', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByTestId('preset-last-7-days')).toBeInTheDocument();
    });

    it('renders Last 30 days preset button', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByTestId('preset-last-30-days')).toBeInTheDocument();
    });

    it('fills in dates when Today preset is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<DateRangePickerModal {...defaultProps} />);

      const todayButton = screen.getByTestId('preset-today');
      await user.click(todayButton);

      const startInput = screen.getByTestId('start-date-input');
      const endInput = screen.getByTestId('end-date-input');

      // Both should be today's date
      expect((startInput as HTMLInputElement).value).toBeTruthy();
      expect((endInput as HTMLInputElement).value).toBeTruthy();
      expect((startInput as HTMLInputElement).value).toBe((endInput as HTMLInputElement).value);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('fills in dates when Last 7 days preset is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<DateRangePickerModal {...defaultProps} />);

      const preset7Days = screen.getByTestId('preset-last-7-days');
      await user.click(preset7Days);

      const startInput = screen.getByTestId('start-date-input');
      const endInput = screen.getByTestId('end-date-input');

      const startValue = (startInput as HTMLInputElement).value;
      const endValue = (endInput as HTMLInputElement).value;
      expect(startValue).toBeTruthy();
      expect(endValue).toBeTruthy();
      // Start date should be before end date
      expect(new Date(startValue).getTime()).toBeLessThan(new Date(endValue).getTime());

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('fills in dates when Last 30 days preset is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<DateRangePickerModal {...defaultProps} />);

      const preset30Days = screen.getByTestId('preset-last-30-days');
      await user.click(preset30Days);

      const startInput = screen.getByTestId('start-date-input');
      const endInput = screen.getByTestId('end-date-input');

      const startValue = (startInput as HTMLInputElement).value;
      const endValue = (endInput as HTMLInputElement).value;
      expect(startValue).toBeTruthy();
      expect(endValue).toBeTruthy();
      // Start date should be before end date
      expect(new Date(startValue).getTime()).toBeLessThan(new Date(endValue).getTime());

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });
  });

  describe('initial values', () => {
    it('populates start date input with initialStartDate', () => {
      render(
        <DateRangePickerModal {...defaultProps} initialStartDate="2024-01-01" />
      );
      const startInput = screen.getByTestId('start-date-input');
      expect((startInput as HTMLInputElement).value).toBe('2024-01-01');
    });

    it('populates end date input with initialEndDate', () => {
      render(
        <DateRangePickerModal {...defaultProps} initialEndDate="2024-01-15" />
      );
      const endInput = screen.getByTestId('end-date-input');
      expect((endInput as HTMLInputElement).value).toBe('2024-01-15');
    });

    it('populates both inputs when both initial values provided', () => {
      render(
        <DateRangePickerModal
          {...defaultProps}
          initialStartDate="2024-01-01"
          initialEndDate="2024-01-15"
        />
      );
      const startInput = screen.getByTestId('start-date-input');
      const endInput = screen.getByTestId('end-date-input');
      expect((startInput as HTMLInputElement).value).toBe('2024-01-01');
      expect((endInput as HTMLInputElement).value).toBe('2024-01-15');
    });
  });

  describe('close functionality', () => {
    it('calls onClose when close button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<DateRangePickerModal {...defaultProps} onClose={onClose} />);

      await user.click(screen.getByTestId('date-range-picker-close'));
      expect(onClose).toHaveBeenCalledTimes(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('calls onClose when cancel button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<DateRangePickerModal {...defaultProps} onClose={onClose} />);

      await user.click(screen.getByTestId('date-range-cancel'));
      expect(onClose).toHaveBeenCalledTimes(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('calls onClose when backdrop is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<DateRangePickerModal {...defaultProps} onClose={onClose} />);

      const backdrop = screen.getByTestId('date-range-picker-modal');
      await user.click(backdrop);
      expect(onClose).toHaveBeenCalledTimes(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('does not close when clicking inside the modal content', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<DateRangePickerModal {...defaultProps} onClose={onClose} />);

      // Click on the modal title (inside the content)
      await user.click(screen.getByText('Select Date Range'));
      expect(onClose).not.toHaveBeenCalled();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('closes when Escape key is pressed', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<DateRangePickerModal {...defaultProps} onClose={onClose} />);

      await user.keyboard('{Escape}');
      expect(onClose).toHaveBeenCalledTimes(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });
  });

  describe('apply functionality', () => {
    it('calls onApply with selected dates when apply button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onApply = vi.fn();
      render(
        <DateRangePickerModal
          {...defaultProps}
          onApply={onApply}
          initialStartDate="2024-01-01"
          initialEndDate="2024-01-15"
        />
      );

      await user.click(screen.getByTestId('date-range-apply'));
      expect(onApply).toHaveBeenCalledWith('2024-01-01', '2024-01-15');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('calls onClose after applying', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onApply = vi.fn();
      const onClose = vi.fn();
      render(
        <DateRangePickerModal
          {...defaultProps}
          onApply={onApply}
          onClose={onClose}
          initialStartDate="2024-01-01"
          initialEndDate="2024-01-15"
        />
      );

      await user.click(screen.getByTestId('date-range-apply'));
      expect(onClose).toHaveBeenCalledTimes(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('apply button is disabled when no dates are selected', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      const applyButton = screen.getByTestId('date-range-apply');
      expect(applyButton).toBeDisabled();
    });

    it('apply button is disabled when only start date is selected', () => {
      render(
        <DateRangePickerModal {...defaultProps} initialStartDate="2024-01-01" />
      );
      const applyButton = screen.getByTestId('date-range-apply');
      expect(applyButton).toBeDisabled();
    });

    it('apply button is disabled when only end date is selected', () => {
      render(
        <DateRangePickerModal {...defaultProps} initialEndDate="2024-01-15" />
      );
      const applyButton = screen.getByTestId('date-range-apply');
      expect(applyButton).toBeDisabled();
    });

    it('apply button is enabled when both dates are selected', () => {
      render(
        <DateRangePickerModal
          {...defaultProps}
          initialStartDate="2024-01-01"
          initialEndDate="2024-01-15"
        />
      );
      const applyButton = screen.getByTestId('date-range-apply');
      expect(applyButton).not.toBeDisabled();
    });
  });

  describe('validation', () => {
    it('shows error when end date is before start date', () => {
      render(
        <DateRangePickerModal
          {...defaultProps}
          initialStartDate="2024-01-15"
          initialEndDate="2024-01-01"
        />
      );
      expect(screen.getByTestId('date-range-error')).toBeInTheDocument();
      expect(screen.getByText('End date cannot be before start date')).toBeInTheDocument();
    });

    it('disables apply button when validation fails', () => {
      render(
        <DateRangePickerModal
          {...defaultProps}
          initialStartDate="2024-01-15"
          initialEndDate="2024-01-01"
        />
      );
      const applyButton = screen.getByTestId('date-range-apply');
      expect(applyButton).toBeDisabled();
    });

    it('no error shown when end date equals start date', () => {
      render(
        <DateRangePickerModal
          {...defaultProps}
          initialStartDate="2024-01-15"
          initialEndDate="2024-01-15"
        />
      );
      expect(screen.queryByTestId('date-range-error')).not.toBeInTheDocument();
    });

    it('no error shown when end date is after start date', () => {
      render(
        <DateRangePickerModal
          {...defaultProps}
          initialStartDate="2024-01-01"
          initialEndDate="2024-01-15"
        />
      );
      expect(screen.queryByTestId('date-range-error')).not.toBeInTheDocument();
    });

    it('error clears when dates are corrected', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(
        <DateRangePickerModal
          {...defaultProps}
          initialStartDate="2024-01-15"
          initialEndDate="2024-01-01"
        />
      );

      // Error should be shown initially
      expect(screen.getByTestId('date-range-error')).toBeInTheDocument();

      // Change end date to be after start date
      const endInput = screen.getByTestId('end-date-input');
      await user.clear(endInput);
      await user.type(endInput, '2024-01-20');

      // Error should be gone
      expect(screen.queryByTestId('date-range-error')).not.toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });
  });

  describe('date input changes', () => {
    it('updates start date when input changes', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<DateRangePickerModal {...defaultProps} />);

      const startInput = screen.getByTestId('start-date-input');
      await user.type(startInput, '2024-01-01');

      expect((startInput as HTMLInputElement).value).toBe('2024-01-01');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('updates end date when input changes', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<DateRangePickerModal {...defaultProps} />);

      const endInput = screen.getByTestId('end-date-input');
      await user.type(endInput, '2024-01-15');

      expect((endInput as HTMLInputElement).value).toBe('2024-01-15');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(MOCK_DATE);
    });

    it('end date input has min attribute set to start date', () => {
      render(
        <DateRangePickerModal {...defaultProps} initialStartDate="2024-01-05" />
      );
      const endInput = screen.getByTestId('end-date-input');
      expect((endInput as HTMLInputElement).min).toBe('2024-01-05');
    });
  });

  describe('accessibility', () => {
    it('has role dialog', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has aria-modal attribute', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      const modal = screen.getByRole('dialog');
      expect(modal).toHaveAttribute('aria-modal', 'true');
    });

    it('has aria-labelledby pointing to title', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      const modal = screen.getByRole('dialog');
      expect(modal).toHaveAttribute('aria-labelledby', 'date-range-picker-title');
    });

    it('close button has accessible label', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      const closeButton = screen.getByTestId('date-range-picker-close');
      expect(closeButton).toHaveAttribute('aria-label', 'Close date range picker');
    });

    it('date inputs have associated labels', () => {
      render(<DateRangePickerModal {...defaultProps} />);
      expect(screen.getByLabelText('Start Date')).toBeInTheDocument();
      expect(screen.getByLabelText('End Date')).toBeInTheDocument();
    });

    it('error message has role alert', () => {
      render(
        <DateRangePickerModal
          {...defaultProps}
          initialStartDate="2024-01-15"
          initialEndDate="2024-01-01"
        />
      );
      const error = screen.getByTestId('date-range-error');
      expect(error).toHaveAttribute('role', 'alert');
    });
  });

  describe('state reset', () => {
    it('resets state when modal reopens', () => {
      const { rerender } = render(
        <DateRangePickerModal
          {...defaultProps}
          isOpen={true}
          initialStartDate="2024-01-01"
          initialEndDate="2024-01-15"
        />
      );

      // Close modal
      rerender(
        <DateRangePickerModal
          {...defaultProps}
          isOpen={false}
          initialStartDate="2024-02-01"
          initialEndDate="2024-02-15"
        />
      );

      // Reopen modal with new initial dates
      rerender(
        <DateRangePickerModal
          {...defaultProps}
          isOpen={true}
          initialStartDate="2024-02-01"
          initialEndDate="2024-02-15"
        />
      );

      const startInput = screen.getByTestId('start-date-input');
      const endInput = screen.getByTestId('end-date-input');

      expect((startInput as HTMLInputElement).value).toBe('2024-02-01');
      expect((endInput as HTMLInputElement).value).toBe('2024-02-15');
    });
  });
});
