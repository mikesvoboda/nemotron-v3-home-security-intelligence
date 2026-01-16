import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import AuditFilters from './AuditFilters';

import type { AuditFilterParams } from './AuditFilters';

describe('AuditFilters', () => {
  const mockAvailableActions = ['event_reviewed', 'camera_created', 'settings_updated'];
  const mockAvailableResourceTypes = ['event', 'camera', 'settings'];
  const mockAvailableActors = ['admin', 'system', 'api'];

  describe('Rendering', () => {
    it('renders filter toggle button', () => {
      const handleFilterChange = vi.fn();
      render(<AuditFilters onFilterChange={handleFilterChange} />);

      expect(screen.getByText('Show Filters')).toBeInTheDocument();
    });

    it('renders help text', () => {
      const handleFilterChange = vi.fn();
      render(<AuditFilters onFilterChange={handleFilterChange} />);

      expect(
        screen.getByText('Filter by action, resource, actor, status, or date range')
      ).toBeInTheDocument();
    });

    it('hides filter options initially', () => {
      const handleFilterChange = vi.fn();
      render(<AuditFilters onFilterChange={handleFilterChange} />);

      expect(screen.queryByLabelText('Action')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Resource Type')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Actor')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Status')).not.toBeInTheDocument();
    });

    it('shows filter options when toggle is clicked', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      expect(screen.getByLabelText('Action')).toBeInTheDocument();
      expect(screen.getByLabelText('Resource Type')).toBeInTheDocument();
      expect(screen.getByLabelText('Actor')).toBeInTheDocument();
      expect(screen.getByLabelText('Status')).toBeInTheDocument();
      expect(screen.getByLabelText('Start Date')).toBeInTheDocument();
      expect(screen.getByLabelText('End Date')).toBeInTheDocument();
    });

    it('changes button text when filters are shown', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      expect(screen.getByText('Hide Filters')).toBeInTheDocument();
      expect(screen.queryByText('Show Filters')).not.toBeInTheDocument();
    });

    it('applies custom className', () => {
      const handleFilterChange = vi.fn();
      const { container } = render(
        <AuditFilters onFilterChange={handleFilterChange} className="custom-class" />
      );

      const wrapper = container.querySelector('.custom-class');
      expect(wrapper).toBeInTheDocument();
    });
  });

  describe('Action Filter', () => {
    it('displays available action options', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters onFilterChange={handleFilterChange} availableActions={mockAvailableActions} />
      );

      await user.click(screen.getByText('Show Filters'));

      const actionSelect = screen.getByLabelText('Action');
      const options = Array.from(actionSelect.querySelectorAll('option'));
      const optionTexts = options.map((opt) => opt.textContent);

      expect(optionTexts).toContain('All Actions');
      expect(optionTexts).toContain('Event Reviewed');
      expect(optionTexts).toContain('Camera Created');
      expect(optionTexts).toContain('Settings Updated');
    });

    it('calls onFilterChange when action is selected', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters onFilterChange={handleFilterChange} availableActions={mockAvailableActions} />
      );

      await user.click(screen.getByText('Show Filters'));

      const actionSelect = screen.getByLabelText('Action');
      await user.selectOptions(actionSelect, 'event_reviewed');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ action: 'event_reviewed' })
        );
      });
    });

    it('clears action filter when All Actions is selected', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters onFilterChange={handleFilterChange} availableActions={mockAvailableActions} />
      );

      await user.click(screen.getByText('Show Filters'));

      const actionSelect = screen.getByLabelText('Action');
      await user.selectOptions(actionSelect, 'event_reviewed');

      handleFilterChange.mockClear();

      await user.selectOptions(actionSelect, '');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.not.objectContaining({ action: expect.anything() })
        );
      });
    });

    it('handles empty action list', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} availableActions={[]} />);

      await user.click(screen.getByText('Show Filters'));

      const actionSelect = screen.getByLabelText('Action');
      const options = Array.from(actionSelect.querySelectorAll('option'));

      expect(options).toHaveLength(1);
      expect(options[0].textContent).toBe('All Actions');
    });
  });

  describe('Resource Type Filter', () => {
    it('displays available resource type options', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters
          onFilterChange={handleFilterChange}
          availableResourceTypes={mockAvailableResourceTypes}
        />
      );

      await user.click(screen.getByText('Show Filters'));

      const resourceSelect = screen.getByLabelText('Resource Type');
      const options = Array.from(resourceSelect.querySelectorAll('option'));
      const optionTexts = options.map((opt) => opt.textContent);

      expect(optionTexts).toContain('All Resources');
      expect(optionTexts).toContain('event');
      expect(optionTexts).toContain('camera');
      expect(optionTexts).toContain('settings');
    });

    it('calls onFilterChange when resource type is selected', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters
          onFilterChange={handleFilterChange}
          availableResourceTypes={mockAvailableResourceTypes}
        />
      );

      await user.click(screen.getByText('Show Filters'));

      const resourceSelect = screen.getByLabelText('Resource Type');
      await user.selectOptions(resourceSelect, 'camera');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ resourceType: 'camera' })
        );
      });
    });
  });

  describe('Actor Filter', () => {
    it('displays available actor options', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters onFilterChange={handleFilterChange} availableActors={mockAvailableActors} />
      );

      await user.click(screen.getByText('Show Filters'));

      const actorSelect = screen.getByLabelText('Actor');
      const options = Array.from(actorSelect.querySelectorAll('option'));
      const optionTexts = options.map((opt) => opt.textContent);

      expect(optionTexts).toContain('All Actors');
      expect(optionTexts).toContain('admin');
      expect(optionTexts).toContain('system');
      expect(optionTexts).toContain('api');
    });

    it('calls onFilterChange when actor is selected', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters onFilterChange={handleFilterChange} availableActors={mockAvailableActors} />
      );

      await user.click(screen.getByText('Show Filters'));

      const actorSelect = screen.getByLabelText('Actor');
      await user.selectOptions(actorSelect, 'system');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ actor: 'system' })
        );
      });
    });
  });

  describe('Status Filter', () => {
    it('displays status options', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const statusSelect = screen.getByLabelText('Status');
      const options = Array.from(statusSelect.querySelectorAll('option'));
      const optionTexts = options.map((opt) => opt.textContent);

      expect(optionTexts).toContain('All Statuses');
      expect(optionTexts).toContain('Success');
      expect(optionTexts).toContain('Failure');
    });

    it('calls onFilterChange when status is selected', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'failure');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'failure' })
        );
      });
    });
  });

  describe('Date Filters', () => {
    it('calls onFilterChange when start date is set', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const startDateInput = screen.getByLabelText('Start Date');
      await user.type(startDateInput, '2024-01-01');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ startDate: '2024-01-01' })
        );
      });
    });

    it('calls onFilterChange when end date is set', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const endDateInput = screen.getByLabelText('End Date');
      await user.type(endDateInput, '2024-01-31');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ endDate: '2024-01-31' })
        );
      });
    });

    it('allows setting both start and end dates', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const startDateInput = screen.getByLabelText('Start Date');
      const endDateInput = screen.getByLabelText('End Date');

      await user.type(startDateInput, '2024-01-01');
      await user.type(endDateInput, '2024-01-31');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({
            startDate: '2024-01-01',
            endDate: '2024-01-31',
          })
        );
      });
    });
  });

  describe('Clear All Filters', () => {
    it('displays Clear All Filters button when filters are shown', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      expect(screen.getByText('Clear All Filters')).toBeInTheDocument();
    });

    it('button is disabled when no filters are active', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const clearButton = screen.getByText('Clear All Filters');
      expect(clearButton).toBeDisabled();
    });

    it('button is enabled when filters are active', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'success');

      await waitFor(() => {
        const clearButton = screen.getByText('Clear All Filters');
        expect(clearButton).not.toBeDisabled();
      });
    });

    it('clears all filters when clicked', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters
          onFilterChange={handleFilterChange}
          availableActions={mockAvailableActions}
          availableActors={mockAvailableActors}
        />
      );

      await user.click(screen.getByText('Show Filters'));

      // Apply multiple filters
      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'success');

      const actionSelect = screen.getByLabelText('Action');
      await user.selectOptions(actionSelect, 'event_reviewed');

      // Clear all filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(statusSelect).toHaveValue('');
        expect(actionSelect).toHaveValue('');
      });

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith({});
      });
    });
  });

  describe('Active Filter Indicator', () => {
    it('does not show Active badge when no filters are active', () => {
      const handleFilterChange = vi.fn();
      render(<AuditFilters onFilterChange={handleFilterChange} />);

      expect(screen.queryByText('Active')).not.toBeInTheDocument();
    });

    it('shows Active badge when status filter is active', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'success');

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument();
      });
    });

    it('shows Active badge when date filter is active', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const startDateInput = screen.getByLabelText('Start Date');
      await user.type(startDateInput, '2024-01-01');

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument();
      });
    });

    it('hides Active badge when all filters are cleared', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      // Apply filter
      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'success');

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument();
      });

      // Clear filter
      await user.selectOptions(statusSelect, '');

      await waitFor(() => {
        expect(screen.queryByText('Active')).not.toBeInTheDocument();
      });
    });
  });

  describe('Controlled Filters', () => {
    it('syncs with controlled filters from parent', async () => {
      const handleFilterChange = vi.fn();

      const controlledFilters: AuditFilterParams = {
        status: 'success',
        action: 'event_reviewed',
      };

      render(
        <AuditFilters
          onFilterChange={handleFilterChange}
          controlledFilters={controlledFilters}
          availableActions={mockAvailableActions}
        />
      );

      // Filters should auto-expand when controlled filters have active values
      await waitFor(() => {
        expect(screen.getByLabelText('Status')).toBeInTheDocument();
      });

      const statusSelect = screen.getByLabelText('Status');
      const actionSelect = screen.getByLabelText('Action');

      expect(statusSelect).toHaveValue('success');
      expect(actionSelect).toHaveValue('event_reviewed');
    });

    it('auto-expands filters when controlled filters are set', async () => {
      const handleFilterChange = vi.fn();

      const controlledFilters: AuditFilterParams = {
        status: 'failure',
      };

      render(
        <AuditFilters onFilterChange={handleFilterChange} controlledFilters={controlledFilters} />
      );

      // Should auto-expand when controlled filters have values
      await waitFor(() => {
        expect(screen.getByLabelText('Status')).toBeInTheDocument();
      });
    });

    it('updates when controlled filters change', async () => {
      const handleFilterChange = vi.fn();

      const { rerender } = render(
        <AuditFilters
          onFilterChange={handleFilterChange}
          controlledFilters={{ status: 'success' }}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText('Status')).toHaveValue('success');
      });

      // Rerender with different controlled filters
      rerender(
        <AuditFilters
          onFilterChange={handleFilterChange}
          controlledFilters={{ status: 'failure' }}
        />
      );

      await waitFor(() => {
        expect(screen.getByLabelText('Status')).toHaveValue('failure');
      });
    });
  });

  describe('Multiple Filter Combinations', () => {
    it('combines action and status filters', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters onFilterChange={handleFilterChange} availableActions={mockAvailableActions} />
      );

      await user.click(screen.getByText('Show Filters'));

      const actionSelect = screen.getByLabelText('Action');
      await user.selectOptions(actionSelect, 'event_reviewed');

      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'success');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({
            action: 'event_reviewed',
            status: 'success',
          })
        );
      });
    });

    it('combines all filter types', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(
        <AuditFilters
          onFilterChange={handleFilterChange}
          availableActions={mockAvailableActions}
          availableResourceTypes={mockAvailableResourceTypes}
          availableActors={mockAvailableActors}
        />
      );

      await user.click(screen.getByText('Show Filters'));

      // Apply all filters
      const actionSelect = screen.getByLabelText('Action');
      await user.selectOptions(actionSelect, 'event_reviewed');

      const resourceSelect = screen.getByLabelText('Resource Type');
      await user.selectOptions(resourceSelect, 'event');

      const actorSelect = screen.getByLabelText('Actor');
      await user.selectOptions(actorSelect, 'admin');

      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'success');

      const startDateInput = screen.getByLabelText('Start Date');
      await user.type(startDateInput, '2024-01-01');

      const endDateInput = screen.getByLabelText('End Date');
      await user.type(endDateInput, '2024-01-31');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({
            action: 'event_reviewed',
            resourceType: 'event',
            actor: 'admin',
            status: 'success',
            startDate: '2024-01-01',
            endDate: '2024-01-31',
          })
        );
      });
    });
  });

  describe('Custom Styling', () => {
    it('uses NVIDIA dark theme colors', () => {
      const handleFilterChange = vi.fn();
      const { container } = render(<AuditFilters onFilterChange={handleFilterChange} />);

      const filterPanel = container.querySelector('.bg-\\[\\#1F1F1F\\]');
      expect(filterPanel).toBeInTheDocument();
    });

    it('uses green accent color for toggle button', () => {
      const handleFilterChange = vi.fn();
      const { container } = render(<AuditFilters onFilterChange={handleFilterChange} />);

      const toggleButton = container.querySelector('.text-\\[\\#76B900\\]');
      expect(toggleButton).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has aria-expanded attribute on toggle button', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      const toggleButton = screen.getByText('Show Filters').closest('button');
      expect(toggleButton).toHaveAttribute('aria-expanded', 'false');

      await user.click(toggleButton!);

      expect(toggleButton).toHaveAttribute('aria-expanded', 'true');
    });

    it('has properly labeled form inputs', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<AuditFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      // All inputs should have associated labels
      expect(screen.getByLabelText('Action')).toBeInTheDocument();
      expect(screen.getByLabelText('Resource Type')).toBeInTheDocument();
      expect(screen.getByLabelText('Actor')).toBeInTheDocument();
      expect(screen.getByLabelText('Status')).toBeInTheDocument();
      expect(screen.getByLabelText('Start Date')).toBeInTheDocument();
      expect(screen.getByLabelText('End Date')).toBeInTheDocument();
    });
  });
});
