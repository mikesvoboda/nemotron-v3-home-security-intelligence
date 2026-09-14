import { render, screen, fireEvent } from '@testing-library/react';
import { beforeEach, describe, it, expect, vi } from 'vitest';

import BulkActionBar from './BulkActionBar';

describe('BulkActionBar', () => {
  const defaultProps = {
    selectedCount: 5,
    totalCount: 10,
    onSelectAll: vi.fn(),
    onClearSelection: vi.fn(),
    onDismissSelected: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders when alerts are selected', () => {
      render(<BulkActionBar {...defaultProps} />);
      expect(screen.getByText('5 selected')).toBeInTheDocument();
    });

    it('does not render when no alerts are selected', () => {
      const { container } = render(<BulkActionBar {...defaultProps} selectedCount={0} />);
      expect(container.firstChild).toBeNull();
    });

    it('shows "Select all" button when not all are selected', () => {
      render(<BulkActionBar {...defaultProps} />);
      expect(screen.getByText('Select all 10')).toBeInTheDocument();
    });

    it('hides "Select all" button when all are selected', () => {
      render(<BulkActionBar {...defaultProps} selectedCount={10} />);
      expect(screen.queryByText(/Select all/)).not.toBeInTheDocument();
    });

    it('displays Clear button', () => {
      render(<BulkActionBar {...defaultProps} />);
      expect(screen.getByText('Clear')).toBeInTheDocument();
    });

    it('displays Dismiss Selected button', () => {
      render(<BulkActionBar {...defaultProps} />);
      expect(screen.getByText('Dismiss Selected')).toBeInTheDocument();
    });
  });

  describe('actions', () => {
    it('calls onSelectAll when Select all button is clicked', () => {
      render(<BulkActionBar {...defaultProps} />);
      fireEvent.click(screen.getByText('Select all 10'));
      expect(defaultProps.onSelectAll).toHaveBeenCalledTimes(1);
    });

    it('calls onClearSelection when Clear button is clicked', () => {
      render(<BulkActionBar {...defaultProps} />);
      fireEvent.click(screen.getByText('Clear'));
      expect(defaultProps.onClearSelection).toHaveBeenCalledTimes(1);
    });

    it('calls onDismissSelected when Dismiss Selected button is clicked', () => {
      render(<BulkActionBar {...defaultProps} />);
      fireEvent.click(screen.getByText('Dismiss Selected'));
      expect(defaultProps.onDismissSelected).toHaveBeenCalledTimes(1);
    });
  });

  describe('processing state', () => {
    it('shows loading state when isProcessing is true', () => {
      render(<BulkActionBar {...defaultProps} isProcessing={true} />);
      expect(screen.getByText('Dismissing...')).toBeInTheDocument();
    });

    it('disables buttons when isProcessing is true', () => {
      render(<BulkActionBar {...defaultProps} isProcessing={true} />);
      expect(screen.getByRole('button', { name: /Clear/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /Dismiss/i })).toBeDisabled();
    });

    it('disables Select all button when isProcessing is true', () => {
      render(<BulkActionBar {...defaultProps} isProcessing={true} />);
      expect(screen.getByRole('button', { name: /Select all/i })).toBeDisabled();
    });
  });

  describe('accessibility', () => {
    it('has appropriate role for toolbar', () => {
      render(<BulkActionBar {...defaultProps} />);
      expect(screen.getByRole('toolbar')).toBeInTheDocument();
    });

    it('has accessible label for toolbar', () => {
      render(<BulkActionBar {...defaultProps} />);
      expect(screen.getByRole('toolbar')).toHaveAccessibleName('Bulk actions for selected alerts');
    });

    it('has accessible labels for buttons', () => {
      render(<BulkActionBar {...defaultProps} />);
      expect(screen.getByRole('button', { name: /Select all 10 alerts/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Clear selection/i })).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /Dismiss 5 selected alerts/i })
      ).toBeInTheDocument();
    });
  });
});
