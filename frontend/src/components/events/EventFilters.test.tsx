import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import EventFilters from './EventFilters';

import type { EventFiltersProps, FilterState } from './EventFilters';

describe('EventFilters', () => {
  const mockOnFilterChange = vi.fn();

  const defaultProps: EventFiltersProps = {
    filters: {},
    onFilterChange: mockOnFilterChange,
  };

  const mockCameras = [
    { id: 'front_door', name: 'Front Door' },
    { id: 'back_yard', name: 'Back Yard' },
    { id: 'garage', name: 'Garage' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders filter group with accessible label', () => {
      render(<EventFilters {...defaultProps} />);

      expect(screen.getByRole('group', { name: /event filters/i })).toBeInTheDocument();
    });

    it('renders all filter dropdowns', () => {
      render(<EventFilters {...defaultProps} />);

      expect(screen.getByLabelText(/risk level/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/camera/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/object type/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/status/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
    });

    it('renders camera options when cameras provided', () => {
      render(<EventFilters {...defaultProps} cameras={mockCameras} />);

      const cameraSelect = screen.getByLabelText(/camera/i);
      expect(cameraSelect).toBeInTheDocument();

      expect(screen.getByRole('option', { name: 'All Cameras' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Front Door' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Back Yard' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Garage' })).toBeInTheDocument();
    });

    it('renders risk level options', () => {
      render(<EventFilters {...defaultProps} />);

      expect(screen.getByRole('option', { name: 'All Risks' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Critical' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'High' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Medium' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Low' })).toBeInTheDocument();
    });

    it('renders object type options', () => {
      render(<EventFilters {...defaultProps} />);

      expect(screen.getByRole('option', { name: 'All Objects' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Person' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Vehicle' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Animal' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Package' })).toBeInTheDocument();
    });

    it('renders status options', () => {
      render(<EventFilters {...defaultProps} />);

      expect(screen.getByRole('option', { name: 'All Status' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Unreviewed' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Reviewed' })).toBeInTheDocument();
    });

    it('displays current filter values', () => {
      const filters: FilterState = {
        riskLevel: 'high',
        cameraId: 'front_door',
        objectType: 'person',
        reviewed: false,
        startDate: '2024-01-01',
        endDate: '2024-01-31',
      };

      render(<EventFilters {...defaultProps} filters={filters} cameras={mockCameras} />);

      expect(screen.getByLabelText(/risk level/i)).toHaveValue('high');
      expect(screen.getByLabelText(/camera/i)).toHaveValue('front_door');
      expect(screen.getByLabelText(/object type/i)).toHaveValue('person');
      expect(screen.getByLabelText(/status/i)).toHaveValue('false');
      expect(screen.getByLabelText(/start date/i)).toHaveValue('2024-01-01');
      expect(screen.getByLabelText(/end date/i)).toHaveValue('2024-01-31');
    });

    it('applies custom className', () => {
      const { container } = render(<EventFilters {...defaultProps} className="custom-class" />);

      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Filter interactions with useTransition', () => {
    it('calls onFilterChange when risk level changes', async () => {
      const user = userEvent.setup();
      render(<EventFilters {...defaultProps} />);

      const riskSelect = screen.getByLabelText(/risk level/i);
      await user.selectOptions(riskSelect, 'critical');

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith({ riskLevel: 'critical' });
      });
    });

    it('calls onFilterChange when camera changes', async () => {
      const user = userEvent.setup();
      render(<EventFilters {...defaultProps} cameras={mockCameras} />);

      const cameraSelect = screen.getByLabelText(/camera/i);
      await user.selectOptions(cameraSelect, 'front_door');

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith({ cameraId: 'front_door' });
      });
    });

    it('calls onFilterChange when object type changes', async () => {
      const user = userEvent.setup();
      render(<EventFilters {...defaultProps} />);

      const objectSelect = screen.getByLabelText(/object type/i);
      await user.selectOptions(objectSelect, 'vehicle');

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith({ objectType: 'vehicle' });
      });
    });

    it('calls onFilterChange when status changes to reviewed', async () => {
      const user = userEvent.setup();
      render(<EventFilters {...defaultProps} />);

      const statusSelect = screen.getByLabelText(/status/i);
      await user.selectOptions(statusSelect, 'true');

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith({ reviewed: true });
      });
    });

    it('calls onFilterChange when status changes to unreviewed', async () => {
      const user = userEvent.setup();
      render(<EventFilters {...defaultProps} />);

      const statusSelect = screen.getByLabelText(/status/i);
      await user.selectOptions(statusSelect, 'false');

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith({ reviewed: false });
      });
    });

    it('calls onFilterChange when start date changes', () => {
      render(<EventFilters {...defaultProps} />);

      const startDateInput = screen.getByLabelText(/start date/i);
      fireEvent.change(startDateInput, { target: { value: '2024-01-15' } });

      // Use waitFor to handle the transition
      expect(mockOnFilterChange).toHaveBeenCalled();
    });

    it('calls onFilterChange when end date changes', () => {
      render(<EventFilters {...defaultProps} />);

      const endDateInput = screen.getByLabelText(/end date/i);
      fireEvent.change(endDateInput, { target: { value: '2024-01-31' } });

      expect(mockOnFilterChange).toHaveBeenCalled();
    });

    it('preserves existing filters when adding new filter', async () => {
      const user = userEvent.setup();
      const existingFilters: FilterState = {
        riskLevel: 'high',
      };

      render(<EventFilters {...defaultProps} filters={existingFilters} cameras={mockCameras} />);

      const cameraSelect = screen.getByLabelText(/camera/i);
      await user.selectOptions(cameraSelect, 'front_door');

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith({
          riskLevel: 'high',
          cameraId: 'front_door',
        });
      });
    });

    it('removes filter when selecting empty option', async () => {
      const user = userEvent.setup();
      const existingFilters: FilterState = {
        riskLevel: 'high',
        cameraId: 'front_door',
      };

      render(<EventFilters {...defaultProps} filters={existingFilters} cameras={mockCameras} />);

      const riskSelect = screen.getByLabelText(/risk level/i);
      await user.selectOptions(riskSelect, '');

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith({ cameraId: 'front_door' });
      });
    });
  });

  describe('Clear all filters', () => {
    it('does not show Clear All button when no filters active', () => {
      render(<EventFilters {...defaultProps} />);

      expect(screen.queryByRole('button', { name: /clear all/i })).not.toBeInTheDocument();
    });

    it('shows Clear All button when filters are active', () => {
      const filters: FilterState = { riskLevel: 'high' };
      render(<EventFilters {...defaultProps} filters={filters} />);

      expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
    });

    it('clears all filters when Clear All is clicked', async () => {
      const user = userEvent.setup();
      const filters: FilterState = {
        riskLevel: 'high',
        cameraId: 'front_door',
        objectType: 'person',
      };

      render(<EventFilters {...defaultProps} filters={filters} cameras={mockCameras} />);

      const clearButton = screen.getByRole('button', { name: /clear all/i });
      await user.click(clearButton);

      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalledWith({});
      });
    });

    it('shows Clear All for date filters', () => {
      const filters: FilterState = { startDate: '2024-01-01' };
      render(<EventFilters {...defaultProps} filters={filters} />);

      expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
    });

    it('shows Clear All for reviewed filter', () => {
      const filters: FilterState = { reviewed: false };
      render(<EventFilters {...defaultProps} filters={filters} />);

      expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
    });
  });

  describe('useTransition loading indicator', () => {
    // Note: Testing the isPending state is challenging in unit tests because
    // useTransition's pending state is often resolved before assertions can run.
    // These tests verify the component handles the loading state gracefully.

    it('renders without loading indicator initially', () => {
      render(<EventFilters {...defaultProps} />);

      expect(screen.queryByTestId('filter-loading-indicator')).not.toBeInTheDocument();
    });

    it('all selects remain interactive', async () => {
      const user = userEvent.setup();
      render(<EventFilters {...defaultProps} cameras={mockCameras} />);

      // Verify selects are not disabled
      expect(screen.getByLabelText(/risk level/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/camera/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/object type/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/status/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/start date/i)).not.toBeDisabled();
      expect(screen.getByLabelText(/end date/i)).not.toBeDisabled();

      // Rapid filter changes should still be handled
      const riskSelect = screen.getByLabelText(/risk level/i);
      await user.selectOptions(riskSelect, 'critical');
      await user.selectOptions(riskSelect, 'high');
      await user.selectOptions(riskSelect, 'medium');

      // All changes should be processed
      expect(mockOnFilterChange).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has proper labels for all form controls', () => {
      render(<EventFilters {...defaultProps} cameras={mockCameras} />);

      // All inputs should have associated labels
      expect(screen.getByLabelText(/risk level/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/camera/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/object type/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/status/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
    });

    it('has accessible Clear All button', () => {
      const filters: FilterState = { riskLevel: 'high' };
      render(<EventFilters {...defaultProps} filters={filters} />);

      const clearButton = screen.getByRole('button', { name: /clear all/i });
      expect(clearButton).toHaveAttribute('aria-label', 'Clear all filters');
    });

    it('has proper role for filter group', () => {
      render(<EventFilters {...defaultProps} />);

      expect(screen.getByRole('group', { name: /event filters/i })).toBeInTheDocument();
    });
  });

  describe('Edge cases', () => {
    it('handles empty cameras array', () => {
      render(<EventFilters {...defaultProps} cameras={[]} />);

      const cameraSelect = screen.getByLabelText(/camera/i);
      expect(cameraSelect).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'All Cameras' })).toBeInTheDocument();
    });

    it('handles undefined cameras', () => {
      render(<EventFilters {...defaultProps} cameras={undefined} />);

      const cameraSelect = screen.getByLabelText(/camera/i);
      expect(cameraSelect).toBeInTheDocument();
    });

    it('handles filters with undefined values', () => {
      const filters: FilterState = {
        riskLevel: undefined,
        cameraId: undefined,
      };
      render(<EventFilters {...defaultProps} filters={filters} />);

      expect(screen.getByLabelText(/risk level/i)).toHaveValue('');
      expect(screen.getByLabelText(/camera/i)).toHaveValue('');
    });

    it('handles rapid consecutive filter changes', async () => {
      const user = userEvent.setup();
      render(<EventFilters {...defaultProps} />);

      const riskSelect = screen.getByLabelText(/risk level/i);

      // Simulate rapid changes
      await user.selectOptions(riskSelect, 'critical');
      await user.selectOptions(riskSelect, 'high');
      await user.selectOptions(riskSelect, 'medium');
      await user.selectOptions(riskSelect, 'low');

      // All changes should be captured (batched by React 19's useTransition)
      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalled();
      });
    });
  });
});
