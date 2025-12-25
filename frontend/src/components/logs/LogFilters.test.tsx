import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import LogFilters from './LogFilters';

describe('LogFilters', () => {
  const mockCameras = [
    { id: 'camera-1', name: 'Front Door' },
    { id: 'camera-2', name: 'Back Yard' },
    { id: 'camera-3', name: 'Garage' },
  ];

  describe('Rendering', () => {
    it('renders filter toggle button', () => {
      const handleFilterChange = vi.fn();
      render(<LogFilters onFilterChange={handleFilterChange} />);

      expect(screen.getByText('Show Filters')).toBeInTheDocument();
    });

    it('renders search input', () => {
      const handleFilterChange = vi.fn();
      render(<LogFilters onFilterChange={handleFilterChange} />);

      expect(screen.getByPlaceholderText('Search log messages...')).toBeInTheDocument();
    });

    it('hides filter options initially', () => {
      const handleFilterChange = vi.fn();
      render(<LogFilters onFilterChange={handleFilterChange} />);

      expect(screen.queryByLabelText('Log Level')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Component')).not.toBeInTheDocument();
    });

    it('shows filter options when toggle is clicked', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      expect(screen.getByLabelText('Log Level')).toBeInTheDocument();
      expect(screen.getByLabelText('Component')).toBeInTheDocument();
      expect(screen.getByLabelText('Camera')).toBeInTheDocument();
      expect(screen.getByLabelText('Start Date')).toBeInTheDocument();
      expect(screen.getByLabelText('End Date')).toBeInTheDocument();
    });

    it('changes button text when filters are shown', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      expect(screen.getByText('Hide Filters')).toBeInTheDocument();
      expect(screen.queryByText('Show Filters')).not.toBeInTheDocument();
    });
  });

  describe('Log Level Filter', () => {
    it('displays all log level options', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const levelSelect = screen.getByLabelText('Log Level');
      expect(levelSelect).toBeInTheDocument();

      const options = Array.from(levelSelect.querySelectorAll('option'));
      const optionTexts = options.map((opt) => opt.textContent);

      expect(optionTexts).toContain('All Levels');
      expect(optionTexts).toContain('DEBUG');
      expect(optionTexts).toContain('INFO');
      expect(optionTexts).toContain('WARNING');
      expect(optionTexts).toContain('ERROR');
      expect(optionTexts).toContain('CRITICAL');
    });

    it('calls onFilterChange when level is selected', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ level: 'ERROR' })
        );
      });
    });

    it('clears level filter when All Levels is selected', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ level: 'ERROR' })
        );
      });

      handleFilterChange.mockClear();

      await user.selectOptions(levelSelect, '');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.not.objectContaining({ level: expect.anything() })
        );
      });
    });
  });

  describe('Component Filter', () => {
    it('displays common component options', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const componentSelect = screen.getByLabelText('Component');
      const options = Array.from(componentSelect.querySelectorAll('option'));
      const optionTexts = options.map((opt) => opt.textContent);

      expect(optionTexts).toContain('All Components');
      expect(optionTexts).toContain('frontend');
      expect(optionTexts).toContain('api');
      expect(optionTexts).toContain('detector');
      expect(optionTexts).toContain('file_watcher');
    });

    it('calls onFilterChange when component is selected', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const componentSelect = screen.getByLabelText('Component');
      await user.selectOptions(componentSelect, 'api');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ component: 'api' })
        );
      });
    });
  });

  describe('Camera Filter', () => {
    it('displays camera options', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} cameras={mockCameras} />);

      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      const options = Array.from(cameraSelect.querySelectorAll('option'));
      const optionTexts = options.map((opt) => opt.textContent);

      expect(optionTexts).toContain('All Cameras');
      expect(optionTexts).toContain('Front Door');
      expect(optionTexts).toContain('Back Yard');
      expect(optionTexts).toContain('Garage');
    });

    it('calls onFilterChange when camera is selected', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} cameras={mockCameras} />);

      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ camera: 'camera-1' })
        );
      });
    });

    it('handles empty camera list', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} cameras={[]} />);

      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      const options = Array.from(cameraSelect.querySelectorAll('option'));

      expect(options).toHaveLength(1);
      expect(options[0].textContent).toBe('All Cameras');
    });
  });

  describe('Date Filters', () => {
    it('calls onFilterChange when start date is set', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

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

      render(<LogFilters onFilterChange={handleFilterChange} />);

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

      render(<LogFilters onFilterChange={handleFilterChange} />);

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

  describe('Search', () => {
    it('calls onFilterChange when search query is entered', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      const searchInput = screen.getByPlaceholderText('Search log messages...');
      await user.type(searchInput, 'error');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({ search: 'error' })
        );
      });
    });

    it('displays clear button when search has text', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      expect(screen.queryByLabelText('Clear search')).not.toBeInTheDocument();

      const searchInput = screen.getByPlaceholderText('Search log messages...');
      await user.type(searchInput, 'error');

      expect(screen.getByLabelText('Clear search')).toBeInTheDocument();
    });

    it('clears search when clear button is clicked', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      const searchInput = screen.getByPlaceholderText('Search log messages...');
      await user.type(searchInput, 'error');

      const clearButton = screen.getByLabelText('Clear search');
      await user.click(clearButton);

      expect(searchInput).toHaveValue('');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.not.objectContaining({ search: expect.anything() })
        );
      });
    });
  });

  describe('Clear All Filters', () => {
    it('displays Clear All Filters button when filters are shown', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      expect(screen.getByText('Clear All Filters')).toBeInTheDocument();
    });

    it('button is disabled when no filters are active', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const clearButton = screen.getByText('Clear All Filters');
      expect(clearButton).toBeDisabled();
    });

    it('button is enabled when filters are active', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      await waitFor(() => {
        const clearButton = screen.getByText('Clear All Filters');
        expect(clearButton).not.toBeDisabled();
      });
    });

    it('clears all filters when clicked', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      // Apply multiple filters
      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      const componentSelect = screen.getByLabelText('Component');
      await user.selectOptions(componentSelect, 'api');

      const searchInput = screen.getByPlaceholderText('Search log messages...');
      await user.type(searchInput, 'failed');

      // Clear all filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(levelSelect).toHaveValue('');
        expect(componentSelect).toHaveValue('');
        expect(searchInput).toHaveValue('');
      });

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith({});
      });
    });
  });

  describe('Active Filter Indicator', () => {
    it('does not show Active badge when no filters are active', () => {
      const handleFilterChange = vi.fn();
      render(<LogFilters onFilterChange={handleFilterChange} />);

      expect(screen.queryByText('Active')).not.toBeInTheDocument();
    });

    it('shows Active badge when level filter is active', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument();
      });
    });

    it('shows Active badge when search is active', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      const searchInput = screen.getByPlaceholderText('Search log messages...');
      await user.type(searchInput, 'error');

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument();
      });
    });

    it('shows Active badge when any filter is active', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

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

      render(<LogFilters onFilterChange={handleFilterChange} />);

      // Apply filter
      const searchInput = screen.getByPlaceholderText('Search log messages...');
      await user.type(searchInput, 'error');

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument();
      });

      // Clear search
      const clearButton = screen.getByLabelText('Clear search');
      await user.click(clearButton);

      await waitFor(() => {
        expect(screen.queryByText('Active')).not.toBeInTheDocument();
      });
    });
  });

  describe('Custom Styling', () => {
    it('applies custom className', () => {
      const handleFilterChange = vi.fn();
      const { container } = render(
        <LogFilters onFilterChange={handleFilterChange} className="custom-class" />
      );

      const wrapper = container.querySelector('.custom-class');
      expect(wrapper).toBeInTheDocument();
    });

    it('uses NVIDIA dark theme colors', () => {
      const handleFilterChange = vi.fn();
      const { container } = render(<LogFilters onFilterChange={handleFilterChange} />);

      const filterPanel = container.querySelector('.bg-\\[\\#1F1F1F\\]');
      expect(filterPanel).toBeInTheDocument();
    });
  });

  describe('Multiple Filter Combinations', () => {
    it('combines level and component filters', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} />);

      await user.click(screen.getByText('Show Filters'));

      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      const componentSelect = screen.getByLabelText('Component');
      await user.selectOptions(componentSelect, 'api');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({
            level: 'ERROR',
            component: 'api',
          })
        );
      });
    });

    it('combines all filter types', async () => {
      const handleFilterChange = vi.fn();
      const user = userEvent.setup();

      render(<LogFilters onFilterChange={handleFilterChange} cameras={mockCameras} />);

      await user.click(screen.getByText('Show Filters'));

      // Apply all filters
      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      const componentSelect = screen.getByLabelText('Component');
      await user.selectOptions(componentSelect, 'api');

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      const startDateInput = screen.getByLabelText('Start Date');
      await user.type(startDateInput, '2024-01-01');

      const endDateInput = screen.getByLabelText('End Date');
      await user.type(endDateInput, '2024-01-31');

      const searchInput = screen.getByPlaceholderText('Search log messages...');
      await user.type(searchInput, 'failed');

      await waitFor(() => {
        expect(handleFilterChange).toHaveBeenCalledWith(
          expect.objectContaining({
            level: 'ERROR',
            component: 'api',
            camera: 'camera-1',
            startDate: '2024-01-01',
            endDate: '2024-01-31',
            search: 'failed',
          })
        );
      });
    });
  });
});
