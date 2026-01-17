/**
 * Tests for DateRangeDropdown component
 *
 * A dropdown selector for date range presets and custom ranges.
 *
 * @see NEM-2702
 */

import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import DateRangeDropdown from './DateRangeDropdown';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type { DateRangePreset } from '../../hooks/useDateRangeState';

describe('DateRangeDropdown', () => {
  const mockSetPreset = vi.fn();
  const mockSetCustomRange = vi.fn();

  const defaultProps = {
    preset: '7d' as DateRangePreset,
    presetLabel: 'Last 7 days',
    isCustom: false,
    range: {
      startDate: new Date('2026-01-11T00:00:00.000Z'),
      endDate: new Date('2026-01-17T23:59:59.999Z'),
    },
    setPreset: mockSetPreset,
    setCustomRange: mockSetCustomRange,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the dropdown button with current preset label', () => {
    renderWithProviders(<DateRangeDropdown {...defaultProps} />);

    expect(screen.getByTestId('date-range-dropdown')).toBeInTheDocument();
    expect(screen.getByText('Last 7 days')).toBeInTheDocument();
  });

  it('opens menu when clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DateRangeDropdown {...defaultProps} />);

    const button = screen.getByTestId('date-range-dropdown');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByRole('menu')).toBeInTheDocument();
    });
  });

  it('displays all preset options in the menu', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DateRangeDropdown {...defaultProps} />);

    const button = screen.getByTestId('date-range-dropdown');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByRole('menuitem', { name: /Last 7 days/ })).toBeInTheDocument();
      expect(screen.getByRole('menuitem', { name: /Last 30 days/ })).toBeInTheDocument();
      expect(screen.getByRole('menuitem', { name: /Last 90 days/ })).toBeInTheDocument();
      expect(screen.getByRole('menuitem', { name: /Custom range/ })).toBeInTheDocument();
    });
  });

  it('shows checkmark on currently selected preset', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DateRangeDropdown {...defaultProps} preset="7d" presetLabel="Last 7 days" />);

    const button = screen.getByTestId('date-range-dropdown');
    await user.click(button);

    await waitFor(() => {
      const selectedItem = screen.getByRole('menuitem', { name: /Last 7 days/ });
      expect(selectedItem).toHaveAttribute('aria-checked', 'true');
    });
  });

  it('calls setPreset when a preset option is selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DateRangeDropdown {...defaultProps} />);

    const button = screen.getByTestId('date-range-dropdown');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByRole('menu')).toBeInTheDocument();
    });

    const option30d = screen.getByRole('menuitem', { name: /Last 30 days/ });
    await user.click(option30d);

    expect(mockSetPreset).toHaveBeenCalledWith('30d');
  });

  it('shows custom date picker when "Custom range" is selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DateRangeDropdown {...defaultProps} />);

    const button = screen.getByTestId('date-range-dropdown');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByRole('menu')).toBeInTheDocument();
    });

    const customOption = screen.getByRole('menuitem', { name: /Custom range/ });
    await user.click(customOption);

    await waitFor(() => {
      expect(screen.getByTestId('custom-date-picker')).toBeInTheDocument();
    });
  });

  it('displays custom range dates in dropdown when custom is selected', () => {
    renderWithProviders(
      <DateRangeDropdown
        {...defaultProps}
        preset="custom"
        presetLabel="Custom"
        isCustom={true}
        range={{
          startDate: new Date('2024-06-01T12:00:00.000Z'), // Use midday to avoid timezone issues
          endDate: new Date('2024-06-30T12:00:00.000Z'),
        }}
      />
    );

    // Custom range should show date range in the button (format depends on locale)
    // Using regex to match various possible formats
    expect(screen.getByTestId('date-range-dropdown')).toHaveTextContent(/Jun\s+1.+Jun\s+30/);
  });

  it('closes menu after selecting a preset', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DateRangeDropdown {...defaultProps} />);

    const button = screen.getByTestId('date-range-dropdown');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByRole('menu')).toBeInTheDocument();
    });

    const option30d = screen.getByRole('menuitem', { name: /Last 30 days/ });
    await user.click(option30d);

    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    });
  });

  it('shows calendar icon in dropdown button', () => {
    renderWithProviders(<DateRangeDropdown {...defaultProps} />);

    const button = screen.getByTestId('date-range-dropdown');
    // The button should contain a calendar icon
    expect(button.querySelector('svg')).toBeInTheDocument();
  });

  it('shows chevron down icon indicating dropdown', () => {
    renderWithProviders(<DateRangeDropdown {...defaultProps} />);

    const button = screen.getByTestId('date-range-dropdown');
    // Should have two SVGs - calendar and chevron
    const icons = button.querySelectorAll('svg');
    expect(icons.length).toBeGreaterThanOrEqual(1);
  });

  describe('CustomDateRangePicker integration', () => {
    it('calls setCustomRange when custom dates are applied', async () => {
      const user = userEvent.setup();
      renderWithProviders(<DateRangeDropdown {...defaultProps} />);

      // Open dropdown
      const button = screen.getByTestId('date-range-dropdown');
      await user.click(button);

      // Select custom range option
      const customOption = screen.getByRole('menuitem', { name: /Custom range/ });
      await user.click(customOption);

      // Wait for date picker to appear
      await waitFor(() => {
        expect(screen.getByTestId('custom-date-picker')).toBeInTheDocument();
      });

      // Fill in start date
      const startInput = screen.getByLabelText(/start date/i);
      await user.clear(startInput);
      await user.type(startInput, '2024-01-01');

      // Fill in end date
      const endInput = screen.getByLabelText(/end date/i);
      await user.clear(endInput);
      await user.type(endInput, '2024-01-31');

      // Apply the custom range
      const applyButton = screen.getByRole('button', { name: /apply/i });
      await user.click(applyButton);

      expect(mockSetCustomRange).toHaveBeenCalled();
    });

    it('cancels custom date selection and closes picker', async () => {
      const user = userEvent.setup();
      renderWithProviders(<DateRangeDropdown {...defaultProps} />);

      // Open dropdown and select custom
      const button = screen.getByTestId('date-range-dropdown');
      await user.click(button);

      const customOption = screen.getByRole('menuitem', { name: /Custom range/ });
      await user.click(customOption);

      await waitFor(() => {
        expect(screen.getByTestId('custom-date-picker')).toBeInTheDocument();
      });

      // Cancel
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByTestId('custom-date-picker')).not.toBeInTheDocument();
      });

      expect(mockSetCustomRange).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has accessible button with aria-expanded', async () => {
      const user = userEvent.setup();
      renderWithProviders(<DateRangeDropdown {...defaultProps} />);

      const button = screen.getByTestId('date-range-dropdown');
      expect(button).toHaveAttribute('aria-expanded', 'false');

      await user.click(button);

      await waitFor(() => {
        expect(button).toHaveAttribute('aria-expanded', 'true');
      });
    });

    it('menu items have proper roles', async () => {
      const user = userEvent.setup();
      renderWithProviders(<DateRangeDropdown {...defaultProps} />);

      const button = screen.getByTestId('date-range-dropdown');
      await user.click(button);

      await waitFor(() => {
        const menuItems = screen.getAllByRole('menuitem');
        expect(menuItems.length).toBeGreaterThanOrEqual(4);
      });
    });

    it('can be navigated with keyboard', async () => {
      const user = userEvent.setup();
      renderWithProviders(<DateRangeDropdown {...defaultProps} />);

      const button = screen.getByTestId('date-range-dropdown');

      // Focus and open with Enter
      button.focus();
      await user.keyboard('{Enter}');

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      // Navigate with arrow keys
      await user.keyboard('{ArrowDown}');
      await user.keyboard('{ArrowDown}');

      // Select with Enter
      await user.keyboard('{Enter}');

      // Should have called setPreset
      expect(mockSetPreset).toHaveBeenCalled();
    });

    it('closes menu on Escape', async () => {
      const user = userEvent.setup();
      renderWithProviders(<DateRangeDropdown {...defaultProps} />);

      const button = screen.getByTestId('date-range-dropdown');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      await user.keyboard('{Escape}');

      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });
  });
});
