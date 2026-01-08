import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertFilters from './AlertFilters';

import type { AlertFiltersProps } from './AlertFilters';

describe('AlertFilters', () => {
  const mockOnFilterChange = vi.fn();

  const defaultProps: AlertFiltersProps = {
    activeFilter: 'all',
    onFilterChange: mockOnFilterChange,
    counts: {
      all: 25,
      critical: 5,
      high: 8,
      medium: 7,
      unread: 15,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders all filter buttons', () => {
      render(<AlertFilters {...defaultProps} />);

      // Buttons use aria-label for accessible names
      expect(screen.getByRole('button', { name: /filter by all alerts/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by critical severity/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by high severity/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by medium severity/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /filter by unread alerts/i })).toBeInTheDocument();
    });

    it('displays counts for each filter', () => {
      render(<AlertFilters {...defaultProps} />);

      // Check that counts are displayed
      expect(screen.getByText('25')).toBeInTheDocument(); // All
      expect(screen.getByText('5')).toBeInTheDocument(); // Critical
      expect(screen.getByText('8')).toBeInTheDocument(); // High
      expect(screen.getByText('7')).toBeInTheDocument(); // Medium
      expect(screen.getByText('15')).toBeInTheDocument(); // Unread
    });

    it('highlights the active filter button', () => {
      render(<AlertFilters {...defaultProps} activeFilter="critical" />);

      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      const allBtn = screen.getByRole('button', { name: /filter by all alerts/i });

      // Active filter should have highlighted styling
      expect(criticalBtn).toHaveClass(/bg-red/);
      // Inactive filters should not have highlighted styling
      expect(allBtn).not.toHaveClass(/bg-red/);
    });

    it('applies correct color for critical filter when active', () => {
      render(<AlertFilters {...defaultProps} activeFilter="critical" />);

      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      expect(criticalBtn).toHaveClass(/bg-red/);
    });

    it('applies correct color for high filter when active', () => {
      render(<AlertFilters {...defaultProps} activeFilter="high" />);

      const highBtn = screen.getByRole('button', { name: /filter by high severity/i });
      expect(highBtn).toHaveClass(/bg-orange/);
    });

    it('applies correct color for medium filter when active', () => {
      render(<AlertFilters {...defaultProps} activeFilter="medium" />);

      const mediumBtn = screen.getByRole('button', { name: /filter by medium severity/i });
      expect(mediumBtn).toHaveClass(/bg-yellow/);
    });
  });

  describe('Interactions', () => {
    it('calls onFilterChange with "all" when All button is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertFilters {...defaultProps} activeFilter="critical" />);

      const allBtn = screen.getByRole('button', { name: /filter by all alerts/i });
      await user.click(allBtn);

      expect(mockOnFilterChange).toHaveBeenCalledWith('all');
      expect(mockOnFilterChange).toHaveBeenCalledTimes(1);
    });

    it('calls onFilterChange with "critical" when Critical button is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertFilters {...defaultProps} />);

      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      await user.click(criticalBtn);

      expect(mockOnFilterChange).toHaveBeenCalledWith('critical');
    });

    it('calls onFilterChange with "high" when High button is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertFilters {...defaultProps} />);

      const highBtn = screen.getByRole('button', { name: /filter by high severity/i });
      await user.click(highBtn);

      expect(mockOnFilterChange).toHaveBeenCalledWith('high');
    });

    it('calls onFilterChange with "medium" when Medium button is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertFilters {...defaultProps} />);

      const mediumBtn = screen.getByRole('button', { name: /filter by medium severity/i });
      await user.click(mediumBtn);

      expect(mockOnFilterChange).toHaveBeenCalledWith('medium');
    });

    it('calls onFilterChange with "unread" when Unread Only button is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertFilters {...defaultProps} />);

      const unreadBtn = screen.getByRole('button', { name: /filter by unread alerts/i });
      await user.click(unreadBtn);

      expect(mockOnFilterChange).toHaveBeenCalledWith('unread');
    });

    it('does not call onFilterChange when clicking the already active filter', async () => {
      const user = userEvent.setup();
      render(<AlertFilters {...defaultProps} activeFilter="all" />);

      const allBtn = screen.getByRole('button', { name: /filter by all alerts/i });
      await user.click(allBtn);

      // Should not call handler when clicking active filter
      expect(mockOnFilterChange).not.toHaveBeenCalled();
    });
  });

  describe('Zero Counts', () => {
    it('displays zero count when no alerts in category', () => {
      render(
        <AlertFilters
          {...defaultProps}
          counts={{ all: 5, critical: 0, high: 3, medium: 2, unread: 5 }}
        />
      );

      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('disables button when count is zero', () => {
      render(
        <AlertFilters
          {...defaultProps}
          counts={{ all: 5, critical: 0, high: 3, medium: 2, unread: 5 }}
        />
      );

      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      expect(criticalBtn).toBeDisabled();
    });

    it('does not call onFilterChange for disabled buttons', async () => {
      const user = userEvent.setup();
      render(
        <AlertFilters
          {...defaultProps}
          counts={{ all: 5, critical: 0, high: 3, medium: 2, unread: 5 }}
        />
      );

      const criticalBtn = screen.getByRole('button', { name: /filter by critical severity/i });
      await user.click(criticalBtn);

      expect(mockOnFilterChange).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has proper button roles', () => {
      render(<AlertFilters {...defaultProps} />);

      const buttons = screen.getAllByRole('button');
      expect(buttons).toHaveLength(5);
    });

    it('has aria-pressed attribute for active filter', () => {
      render(<AlertFilters {...defaultProps} activeFilter="high" />);

      const highBtn = screen.getByRole('button', { name: /filter by high severity/i });
      expect(highBtn).toHaveAttribute('aria-pressed', 'true');
    });

    it('has aria-pressed false for inactive filters', () => {
      render(<AlertFilters {...defaultProps} activeFilter="high" />);

      const allBtn = screen.getByRole('button', { name: /filter by all alerts/i });
      expect(allBtn).toHaveAttribute('aria-pressed', 'false');
    });

    it('has descriptive aria-label for filter buttons', () => {
      render(<AlertFilters {...defaultProps} />);

      expect(screen.getByRole('button', { name: /filter by all alerts/i })).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /filter by critical severity/i })
      ).toBeInTheDocument();
    });
  });
});
