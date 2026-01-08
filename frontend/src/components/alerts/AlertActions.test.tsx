import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AlertActions from './AlertActions';

import type { AlertActionsProps } from './AlertActions';

describe('AlertActions', () => {
  const mockOnSelectAll = vi.fn();
  const mockOnAcknowledgeSelected = vi.fn();
  const mockOnDismissSelected = vi.fn();
  const mockOnClearSelection = vi.fn();

  const defaultProps: AlertActionsProps = {
    selectedCount: 3,
    totalCount: 10,
    hasUnacknowledged: true,
    onSelectAll: mockOnSelectAll,
    onAcknowledgeSelected: mockOnAcknowledgeSelected,
    onDismissSelected: mockOnDismissSelected,
    onClearSelection: mockOnClearSelection,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('displays selection count', () => {
      render(<AlertActions {...defaultProps} />);

      expect(screen.getByText('3 selected')).toBeInTheDocument();
    });

    it('displays "Select All" button when not all selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={3} totalCount={10} />);

      expect(screen.getByRole('button', { name: /select all/i })).toBeInTheDocument();
    });

    it('displays "Clear Selection" button when some are selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={3} />);

      expect(screen.getByRole('button', { name: /clear selection/i })).toBeInTheDocument();
    });

    it('displays batch acknowledge button', () => {
      render(<AlertActions {...defaultProps} />);

      expect(screen.getByRole('button', { name: /acknowledge selected/i })).toBeInTheDocument();
    });

    it('displays batch dismiss button', () => {
      render(<AlertActions {...defaultProps} />);

      expect(screen.getByRole('button', { name: /dismiss selected/i })).toBeInTheDocument();
    });

    it('hides batch acknowledge button when no unacknowledged alerts', () => {
      render(<AlertActions {...defaultProps} hasUnacknowledged={false} />);

      expect(
        screen.queryByRole('button', { name: /acknowledge selected/i })
      ).not.toBeInTheDocument();
    });
  });

  describe('Select All Behavior', () => {
    it('calls onSelectAll when Select All button is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertActions {...defaultProps} selectedCount={3} totalCount={10} />);

      const selectAllBtn = screen.getByRole('button', { name: /select all/i });
      await user.click(selectAllBtn);

      expect(mockOnSelectAll).toHaveBeenCalledWith(true);
      expect(mockOnSelectAll).toHaveBeenCalledTimes(1);
    });

    it('shows "Deselect All" when all items are selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={10} totalCount={10} />);

      expect(screen.getByRole('button', { name: /deselect all/i })).toBeInTheDocument();
    });

    it('calls onSelectAll(false) when Deselect All is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertActions {...defaultProps} selectedCount={10} totalCount={10} />);

      const deselectAllBtn = screen.getByRole('button', { name: /deselect all/i });
      await user.click(deselectAllBtn);

      expect(mockOnSelectAll).toHaveBeenCalledWith(false);
    });
  });

  describe('Clear Selection', () => {
    it('calls onClearSelection when Clear Selection button is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertActions {...defaultProps} selectedCount={5} />);

      const clearBtn = screen.getByRole('button', { name: /clear selection/i });
      await user.click(clearBtn);

      expect(mockOnClearSelection).toHaveBeenCalledTimes(1);
    });

    it('does not show Clear Selection when nothing is selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={0} />);

      expect(
        screen.queryByRole('button', { name: /clear selection/i })
      ).not.toBeInTheDocument();
    });
  });

  describe('Batch Actions', () => {
    it('calls onAcknowledgeSelected when Acknowledge Selected is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertActions {...defaultProps} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge selected/i });
      await user.click(acknowledgeBtn);

      expect(mockOnAcknowledgeSelected).toHaveBeenCalledTimes(1);
    });

    it('calls onDismissSelected when Dismiss Selected is clicked', async () => {
      const user = userEvent.setup();
      render(<AlertActions {...defaultProps} />);

      const dismissBtn = screen.getByRole('button', { name: /dismiss selected/i });
      await user.click(dismissBtn);

      expect(mockOnDismissSelected).toHaveBeenCalledTimes(1);
    });

    it('hides batch actions when no items selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={0} />);

      // Batch action buttons are not rendered when nothing is selected
      expect(screen.queryByRole('button', { name: /acknowledge selected/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /dismiss selected/i })).not.toBeInTheDocument();
    });

    it('enables batch actions when items are selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={3} />);

      const acknowledgeBtn = screen.getByRole('button', { name: /acknowledge selected/i });
      const dismissBtn = screen.getByRole('button', { name: /dismiss selected/i });

      expect(acknowledgeBtn).not.toBeDisabled();
      expect(dismissBtn).not.toBeDisabled();
    });
  });

  describe('Empty State', () => {
    it('renders nothing when totalCount is 0', () => {
      const { container } = render(<AlertActions {...defaultProps} totalCount={0} />);

      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when selectedCount is 0 and totalCount is 0', () => {
      const { container } = render(
        <AlertActions {...defaultProps} selectedCount={0} totalCount={0} />
      );

      expect(container.firstChild).toBeNull();
    });
  });

  describe('Accessibility', () => {
    it('has proper button roles', () => {
      render(<AlertActions {...defaultProps} />);

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThanOrEqual(3);
    });

    it('has descriptive aria-labels', () => {
      render(<AlertActions {...defaultProps} />);

      expect(screen.getByRole('button', { name: /select all/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /acknowledge selected/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /dismiss selected/i })).toBeInTheDocument();
    });

    it('hides action buttons when no items are selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={0} />);

      // Batch actions are hidden when nothing is selected (not just disabled)
      expect(screen.queryByRole('button', { name: /dismiss selected/i })).not.toBeInTheDocument();
    });
  });

  describe('Count Display', () => {
    it('displays singular "1 selected" when one item selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={1} />);

      expect(screen.getByText('1 selected')).toBeInTheDocument();
    });

    it('displays plural "X selected" when multiple items selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={5} />);

      expect(screen.getByText('5 selected')).toBeInTheDocument();
    });

    it('does not display count when nothing selected', () => {
      render(<AlertActions {...defaultProps} selectedCount={0} />);

      expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
    });
  });
});
