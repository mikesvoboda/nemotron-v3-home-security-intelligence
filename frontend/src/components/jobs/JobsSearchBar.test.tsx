import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import JobsSearchBar, {
  type JobsSearchBarProps,
  JOB_STATUSES,
  JOB_TYPES,
} from './JobsSearchBar';

// Wrap component with MemoryRouter for useSearchParams
function renderWithRouter(
  props: JobsSearchBarProps,
  initialEntries: string[] = ['/jobs']
) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <JobsSearchBar {...props} />
    </MemoryRouter>
  );
}

describe('JobsSearchBar', () => {
  const mockOnSearchChange = vi.fn();
  const mockOnStatusChange = vi.fn();
  const mockOnTypeChange = vi.fn();
  const mockOnClear = vi.fn();

  const defaultProps: JobsSearchBarProps = {
    query: '',
    status: undefined,
    type: undefined,
    onSearchChange: mockOnSearchChange,
    onStatusChange: mockOnStatusChange,
    onTypeChange: mockOnTypeChange,
    onClear: mockOnClear,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  describe('Basic rendering', () => {
    it('renders the search input', () => {
      renderWithRouter(defaultProps);
      expect(screen.getByPlaceholderText(/search jobs/i)).toBeInTheDocument();
    });

    it('renders the status dropdown', () => {
      renderWithRouter(defaultProps);
      expect(screen.getByLabelText(/status/i)).toBeInTheDocument();
    });

    it('renders the type dropdown', () => {
      renderWithRouter(defaultProps);
      expect(screen.getByLabelText(/type/i)).toBeInTheDocument();
    });

    it('renders the search icon', () => {
      renderWithRouter(defaultProps);
      expect(screen.getByTestId('search-icon')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = renderWithRouter({
        ...defaultProps,
        className: 'custom-class',
      });
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Search input behavior', () => {
    it('displays current query value', () => {
      renderWithRouter({ ...defaultProps, query: 'export job' });
      expect(screen.getByDisplayValue('export job')).toBeInTheDocument();
    });

    it('calls onSearchChange when typing', () => {
      renderWithRouter(defaultProps);
      const input = screen.getByPlaceholderText(/search jobs/i);
      fireEvent.change(input, { target: { value: 'test' } });
      expect(mockOnSearchChange).toHaveBeenCalledWith('test');
    });

    it('shows clear button when query has content', () => {
      renderWithRouter({ ...defaultProps, query: 'something' });
      expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument();
    });

    it('hides clear button when query is empty', () => {
      renderWithRouter(defaultProps);
      expect(screen.queryByRole('button', { name: /clear search/i })).not.toBeInTheDocument();
    });

    it('clears search when clear button is clicked', () => {
      renderWithRouter({ ...defaultProps, query: 'something' });
      const clearButton = screen.getByRole('button', { name: /clear search/i });
      fireEvent.click(clearButton);
      expect(mockOnClear).toHaveBeenCalled();
    });
  });

  describe('Status dropdown', () => {
    it('displays "All" when no status is selected', () => {
      renderWithRouter(defaultProps);
      const statusSelect = screen.getByLabelText(/status/i);
      expect(statusSelect).toHaveValue('');
    });

    it('displays selected status', () => {
      renderWithRouter({ ...defaultProps, status: 'failed' });
      const statusSelect = screen.getByLabelText(/status/i);
      expect(statusSelect).toHaveValue('failed');
    });

    it('calls onStatusChange when status is selected', () => {
      renderWithRouter(defaultProps);
      const statusSelect = screen.getByLabelText(/status/i);
      fireEvent.change(statusSelect, { target: { value: 'failed' } });
      expect(mockOnStatusChange).toHaveBeenCalledWith('failed');
    });

    it('calls onStatusChange with undefined when "All" is selected', () => {
      renderWithRouter({ ...defaultProps, status: 'failed' });
      const statusSelect = screen.getByLabelText(/status/i);
      fireEvent.change(statusSelect, { target: { value: '' } });
      expect(mockOnStatusChange).toHaveBeenCalledWith(undefined);
    });

    it('renders all status options', () => {
      renderWithRouter(defaultProps);
      const statusSelect = screen.getByLabelText(/status/i);
      JOB_STATUSES.forEach((status) => {
        const options = statusSelect.querySelectorAll('option');
        const hasOption = Array.from(options).some(
          (opt) => opt.textContent === status.label && opt.getAttribute('value') === status.value
        );
        expect(hasOption).toBe(true);
      });
    });
  });

  describe('Type dropdown', () => {
    it('displays "All" when no type is selected', () => {
      renderWithRouter(defaultProps);
      const typeSelect = screen.getByLabelText(/type/i);
      expect(typeSelect).toHaveValue('');
    });

    it('displays selected type', () => {
      renderWithRouter({ ...defaultProps, type: 'export' });
      const typeSelect = screen.getByLabelText(/type/i);
      expect(typeSelect).toHaveValue('export');
    });

    it('calls onTypeChange when type is selected', () => {
      renderWithRouter(defaultProps);
      const typeSelect = screen.getByLabelText(/type/i);
      fireEvent.change(typeSelect, { target: { value: 'batch_audit' } });
      expect(mockOnTypeChange).toHaveBeenCalledWith('batch_audit');
    });

    it('calls onTypeChange with undefined when "All" is selected', () => {
      renderWithRouter({ ...defaultProps, type: 'export' });
      const typeSelect = screen.getByLabelText(/type/i);
      fireEvent.change(typeSelect, { target: { value: '' } });
      expect(mockOnTypeChange).toHaveBeenCalledWith(undefined);
    });

    it('renders all type options', () => {
      renderWithRouter(defaultProps);
      const typeSelect = screen.getByLabelText(/type/i);
      JOB_TYPES.forEach((type) => {
        const options = typeSelect.querySelectorAll('option');
        const hasOption = Array.from(options).some(
          (opt) => opt.textContent === type.label && opt.getAttribute('value') === type.value
        );
        expect(hasOption).toBe(true);
      });
    });
  });

  describe('Keyboard shortcuts', () => {
    it('clears search when Escape is pressed', () => {
      renderWithRouter({ ...defaultProps, query: 'test' });
      const input = screen.getByPlaceholderText(/search jobs/i);
      fireEvent.keyDown(input, { key: 'Escape' });
      expect(mockOnClear).toHaveBeenCalled();
    });
  });

  describe('Filter indicator', () => {
    it('shows active filters indicator when filters are applied', () => {
      renderWithRouter({ ...defaultProps, status: 'failed' });
      expect(screen.getByTestId('active-filters-indicator')).toBeInTheDocument();
    });

    it('shows active filters indicator when type is applied', () => {
      renderWithRouter({ ...defaultProps, type: 'export' });
      expect(screen.getByTestId('active-filters-indicator')).toBeInTheDocument();
    });

    it('shows active filters indicator when query is applied', () => {
      renderWithRouter({ ...defaultProps, query: 'test' });
      expect(screen.getByTestId('active-filters-indicator')).toBeInTheDocument();
    });

    it('does not show active filters indicator when no filters', () => {
      renderWithRouter(defaultProps);
      expect(screen.queryByTestId('active-filters-indicator')).not.toBeInTheDocument();
    });
  });

  describe('Clear all button', () => {
    it('shows clear all button when filters are active', () => {
      renderWithRouter({ ...defaultProps, status: 'failed', query: 'test' });
      expect(screen.getByRole('button', { name: /clear all/i })).toBeInTheDocument();
    });

    it('clears all filters when clear all is clicked', () => {
      renderWithRouter({ ...defaultProps, status: 'failed', query: 'test' });
      const clearAllButton = screen.getByRole('button', { name: /clear all/i });
      fireEvent.click(clearAllButton);
      expect(mockOnClear).toHaveBeenCalled();
    });

    it('hides clear all button when no filters', () => {
      renderWithRouter(defaultProps);
      expect(screen.queryByRole('button', { name: /clear all/i })).not.toBeInTheDocument();
    });
  });

  describe('Disabled state', () => {
    it('disables search input when isLoading is true', () => {
      renderWithRouter({ ...defaultProps, isLoading: true });
      expect(screen.getByPlaceholderText(/search jobs/i)).toBeDisabled();
    });

    it('disables status dropdown when isLoading is true', () => {
      renderWithRouter({ ...defaultProps, isLoading: true });
      expect(screen.getByLabelText(/status/i)).toBeDisabled();
    });

    it('disables type dropdown when isLoading is true', () => {
      renderWithRouter({ ...defaultProps, isLoading: true });
      expect(screen.getByLabelText(/type/i)).toBeDisabled();
    });
  });

  describe('Accessibility', () => {
    it('has accessible search input', () => {
      renderWithRouter(defaultProps);
      const input = screen.getByPlaceholderText(/search jobs/i);
      expect(input).toHaveAttribute('type', 'text');
    });

    it('has accessible status dropdown with label', () => {
      renderWithRouter(defaultProps);
      expect(screen.getByLabelText(/status/i)).toBeInTheDocument();
    });

    it('has accessible type dropdown with label', () => {
      renderWithRouter(defaultProps);
      expect(screen.getByLabelText(/type/i)).toBeInTheDocument();
    });

    it('has accessible clear button', () => {
      renderWithRouter({ ...defaultProps, query: 'test' });
      expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument();
    });
  });

  describe('Results count', () => {
    it('displays results count when provided', () => {
      renderWithRouter({ ...defaultProps, totalCount: 150 });
      expect(screen.getByText(/150 jobs/i)).toBeInTheDocument();
    });

    it('displays singular "job" for count of 1', () => {
      renderWithRouter({ ...defaultProps, totalCount: 1 });
      expect(screen.getByText(/1 job\b/i)).toBeInTheDocument();
    });

    it('does not display results count when not provided', () => {
      renderWithRouter(defaultProps);
      expect(screen.queryByText(/jobs/i)).not.toBeInTheDocument();
    });
  });
});
