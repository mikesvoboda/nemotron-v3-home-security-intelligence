import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import type { SavedSearch } from '../../hooks/useSavedSearches';
import type { Camera } from '../../services/api';

// Use vi.hoisted to properly hoist mock variables before vi.mock runs
const {
  mockSaveSearch,
  mockDeleteSearch,
  mockLoadSearch,
  mockClearAll,
  getMockSavedSearches,
  setMockSavedSearches,
} = vi.hoisted(() => {
  let savedSearches: SavedSearch[] = [];
  return {
    mockSaveSearch: vi.fn(),
    mockDeleteSearch: vi.fn(),
    mockLoadSearch: vi.fn(),
    mockClearAll: vi.fn(),
    getMockSavedSearches: () => savedSearches,
    setMockSavedSearches: (searches: SavedSearch[]) => {
      savedSearches = searches;
    },
  };
});

// Mock the useSavedSearches hook to prevent localStorage/storage event listener issues
vi.mock('../../hooks/useSavedSearches', () => ({
  useSavedSearches: () => ({
    savedSearches: getMockSavedSearches(),
    saveSearch: mockSaveSearch,
    deleteSearch: mockDeleteSearch,
    loadSearch: mockLoadSearch,
    clearAll: mockClearAll,
  }),
}));

// Import after mock is set up (must come after vi.mock)
// eslint-disable-next-line import/order
import SearchBar from './SearchBar';

describe('SearchBar', () => {
  const mockOnQueryChange = vi.fn();
  const mockOnSearch = vi.fn();

  const mockCameras: Camera[] = [
    {
      id: 'front_door',
      name: 'Front Door',
      folder_path: '/export/foscam/front_door',
      status: 'online' as const,
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'back_yard',
      name: 'Back Yard',
      folder_path: '/export/foscam/back_yard',
      status: 'online' as const,
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'garage',
      name: 'Garage',
      folder_path: '/export/foscam/garage',
      status: 'offline' as const,
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: null,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    setMockSavedSearches([]);

    // Mock document event listeners to prevent jsdom issues with mousedown events
    // that cause tests to hang due to improper cleanup in jsdom environment.
    // Using vi.spyOn ensures proper cleanup through vitest's mock lifecycle.
    vi.spyOn(document, 'addEventListener').mockImplementation(() => {});
    vi.spyOn(document, 'removeEventListener').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    cleanup();
  });

  describe('Basic rendering', () => {
    it('renders the search input', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.getByRole('textbox', { name: /search events/i })).toBeInTheDocument();
    });

    it('renders with custom placeholder', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          placeholder="Find suspicious activity..."
        />
      );
      expect(screen.getByPlaceholderText('Find suspicious activity...')).toBeInTheDocument();
    });

    it('renders the search button', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.getByRole('button', { name: /^search$/i })).toBeInTheDocument();
    });

    it('renders the filters button', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.getByRole('button', { name: /toggle advanced filters/i })).toBeInTheDocument();
    });

    it('displays current query value', () => {
      render(
        <SearchBar
          query="suspicious person"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
        />
      );
      expect(screen.getByDisplayValue('suspicious person')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          className="custom-class"
        />
      );
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Search input behavior', () => {
    it('calls onQueryChange when input changes', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.change(input, { target: { value: 'test' } });
      expect(mockOnQueryChange).toHaveBeenCalledWith('test');
    });

    it('submits search on Enter key', () => {
      render(
        <SearchBar
          query="person detected"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
        />
      );
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(mockOnSearch).toHaveBeenCalledWith('person detected', expect.any(Object));
    });

    it('clears query on Escape key', () => {
      render(
        <SearchBar query="person" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'Escape' });
      expect(mockOnQueryChange).toHaveBeenCalledWith('');
    });

    it('does not submit empty query', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(mockOnSearch).not.toHaveBeenCalled();
    });

    it('trims query before submitting', () => {
      render(
        <SearchBar
          query="  person detected  "
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
        />
      );
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(mockOnSearch).toHaveBeenCalledWith('person detected', expect.any(Object));
    });

    it('does not submit whitespace-only query', () => {
      render(<SearchBar query="   " onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(mockOnSearch).not.toHaveBeenCalled();
    });
  });

  describe('Search button', () => {
    it('submits search when clicked', () => {
      render(
        <SearchBar query="vehicle" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      fireEvent.click(searchButton);
      expect(mockOnSearch).toHaveBeenCalledWith('vehicle', expect.any(Object));
    });

    it('is disabled when query is empty', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      expect(searchButton).toBeDisabled();
    });

    it('is disabled when isSearching is true', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          isSearching={true}
        />
      );
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      expect(searchButton).toBeDisabled();
    });

    it('shows loading state when isSearching is true', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          isSearching={true}
        />
      );
      expect(screen.getByText('Searching...')).toBeInTheDocument();
    });
  });

  describe('Clear button', () => {
    it('shows clear button when query has content', () => {
      render(
        <SearchBar query="something" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument();
    });

    it('hides clear button when query is empty', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.queryByRole('button', { name: /clear search/i })).not.toBeInTheDocument();
    });

    it('clears query when clear button is clicked', () => {
      render(
        <SearchBar query="something" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      const clearButton = screen.getByRole('button', { name: /clear search/i });
      fireEvent.click(clearButton);
      expect(mockOnQueryChange).toHaveBeenCalledWith('');
    });
  });

  // SKIP: These tests hang in jsdom due to document.addEventListener('mousedown', ...) cleanup issues.
  // The component's useEffect adds event listeners when dropdowns/panels open, which causes
  // vitest worker to hang after running multiple tests. Tests pass individually but hang when
  // run together with the full test suite. This is a vitest + jsdom + React 19 compatibility issue.
  // See: NEM-1419, commits 9b936bd2, f0d88ea0 for history.
  describe.skip('Advanced filters panel', () => {
    it('expands filters panel when toggle button is clicked', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={mockCameras}
        />
      );

      expect(screen.queryByLabelText('Camera')).not.toBeInTheDocument();

      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      fireEvent.click(filtersButton);

      expect(screen.getByLabelText('Camera')).toBeInTheDocument();
      expect(filtersButton).toHaveAttribute('aria-expanded', 'true');
    });

    it('shows all filter options when expanded', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={mockCameras}
        />
      );

      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      fireEvent.click(filtersButton);

      expect(screen.getByLabelText('Camera')).toBeInTheDocument();
      expect(screen.getByLabelText('Severity')).toBeInTheDocument();
      expect(screen.getByLabelText('Object Type')).toBeInTheDocument();
      expect(screen.getByLabelText('Status')).toBeInTheDocument();
      expect(screen.getByLabelText('Start Date')).toBeInTheDocument();
      expect(screen.getByLabelText('End Date')).toBeInTheDocument();
    });

    it('populates camera dropdown with provided cameras', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={mockCameras}
        />
      );

      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      fireEvent.click(filtersButton);

      expect(screen.getByRole('option', { name: 'All Cameras' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Front Door' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Back Yard' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Garage' })).toBeInTheDocument();
    });

    it('updates filter values when selections are made', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={mockCameras}
        />
      );

      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      fireEvent.click(filtersButton);

      const cameraSelect = screen.getByLabelText('Camera');
      fireEvent.change(cameraSelect, { target: { value: 'front_door' } });
      expect(cameraSelect).toHaveValue('front_door');

      const severitySelect = screen.getByLabelText('Severity');
      fireEvent.change(severitySelect, { target: { value: 'high' } });
      expect(severitySelect).toHaveValue('high');
    });

    it('includes filters in search submission', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={mockCameras}
        />
      );

      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      fireEvent.click(filtersButton);

      fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'front_door' } });
      fireEvent.change(screen.getByLabelText('Severity'), { target: { value: 'high' } });

      const searchButton = screen.getByRole('button', { name: /^search$/i });
      fireEvent.click(searchButton);

      expect(mockOnSearch).toHaveBeenCalledWith('test', {
        camera_id: 'front_door',
        severity: 'high',
      });
    });

    it('shows Active badge when filters are applied', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={mockCameras}
        />
      );

      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      fireEvent.click(filtersButton);

      fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'front_door' } });

      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    it('clears all filters when Clear All button is clicked', () => {
      render(
        <SearchBar
          query="test query"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={mockCameras}
        />
      );

      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      fireEvent.click(filtersButton);

      fireEvent.change(screen.getByLabelText('Camera'), { target: { value: 'front_door' } });

      const clearButton = screen.getByRole('button', { name: /clear all/i });
      fireEvent.click(clearButton);

      expect(mockOnQueryChange).toHaveBeenCalledWith('');
      expect(screen.getByLabelText('Camera')).toHaveValue('');
    });

    it('uses initial filters when provided', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={mockCameras}
          initialFilters={{
            camera_id: 'back_yard',
            severity: 'critical',
          }}
        />
      );

      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      fireEvent.click(filtersButton);

      expect(screen.getByLabelText('Camera')).toHaveValue('back_yard');
      expect(screen.getByLabelText('Severity')).toHaveValue('critical');
    });
  });

  // SKIP: These tests hang due to jsdom mousedown event listener cleanup issues (see above comment)
  describe.skip('Query syntax help', () => {
    it('shows help button', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.getByRole('button', { name: /show search syntax help/i })).toBeInTheDocument();
    });

    it('toggles help tooltip when help button is clicked', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      const helpButton = screen.getByRole('button', { name: /show search syntax help/i });
      expect(helpButton).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(helpButton);

      expect(screen.getByText('Search Syntax')).toBeInTheDocument();
      expect(helpButton).toHaveAttribute('aria-expanded', 'true');
    });

    it('displays query syntax examples in help tooltip', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      const helpButton = screen.getByRole('button', { name: /show search syntax help/i });
      fireEvent.click(helpButton);

      expect(screen.getByText('person vehicle')).toBeInTheDocument();
      expect(screen.getByText('"suspicious person"')).toBeInTheDocument();
      expect(screen.getByText('person OR animal')).toBeInTheDocument();
      expect(screen.getByText('person NOT cat')).toBeInTheDocument();
    });
  });

  // SKIP: These tests hang due to jsdom mousedown event listener cleanup issues (see above comment)
  describe.skip('Save search functionality', () => {
    it('shows save button when query has content', () => {
      render(
        <SearchBar query="test query" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );

      expect(screen.getByRole('button', { name: /save search/i })).toBeInTheDocument();
    });

    it('hides save button when query is empty', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      expect(screen.queryByRole('button', { name: /save search/i })).not.toBeInTheDocument();
    });

    it('opens save modal when save button is clicked', () => {
      render(
        <SearchBar query="test query" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );

      const saveButton = screen.getByRole('button', { name: /save search/i });
      fireEvent.click(saveButton);

      expect(screen.getByText('Save Search')).toBeInTheDocument();
    });

    it('saves search with name when confirmed', () => {
      render(
        <SearchBar
          query="my test query"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
        />
      );

      const saveButton = screen.getByRole('button', { name: /save search/i });
      fireEvent.click(saveButton);

      const nameInput = screen.getByLabelText('Search name');
      fireEvent.change(nameInput, { target: { value: 'My Saved Search' } });

      const confirmButton = screen.getByRole('button', { name: /^save$/i });
      fireEvent.click(confirmButton);

      expect(mockSaveSearch).toHaveBeenCalledWith('My Saved Search', 'my test query', {});
    });

    it('saves search on Enter key in name input', () => {
      render(
        <SearchBar query="test query" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );

      const saveButton = screen.getByRole('button', { name: /save search/i });
      fireEvent.click(saveButton);

      const nameInput = screen.getByLabelText('Search name');
      fireEvent.change(nameInput, { target: { value: 'Quick Save' } });
      fireEvent.keyDown(nameInput, { key: 'Enter' });

      expect(mockSaveSearch).toHaveBeenCalledWith('Quick Save', 'test query', {});
    });

    it('disables Save button when name is empty', () => {
      render(
        <SearchBar query="test query" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );

      const saveButton = screen.getByRole('button', { name: /save search/i });
      fireEvent.click(saveButton);

      const confirmButton = screen.getByRole('button', { name: /^save$/i });
      expect(confirmButton).toBeDisabled();
    });
  });

  // SKIP: These tests hang due to jsdom mousedown event listener cleanup issues (see above comment)
  describe.skip('Saved searches', () => {
    it('renders saved searches button', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      expect(screen.getByLabelText('Saved searches')).toBeInTheDocument();
    });

    it('shows count badge when there are saved searches', () => {
      setMockSavedSearches([
        {
          id: '1',
          name: 'Test',
          query: 'test',
          filters: {},
          createdAt: '2024-01-01T00:00:00Z',
        },
        {
          id: '2',
          name: 'Another',
          query: 'another',
          filters: {},
          createdAt: '2024-01-01T00:00:00Z',
        },
      ]);

      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('opens saved searches dropdown when clicked', () => {
      setMockSavedSearches([
        {
          id: '1',
          name: 'My Search',
          query: 'test query',
          filters: {},
          createdAt: '2024-01-01T00:00:00Z',
        },
      ]);

      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      const savedSearchesButton = screen.getByLabelText('Saved searches');
      fireEvent.click(savedSearchesButton);

      expect(screen.getByText('My Search')).toBeInTheDocument();
    });

    it('shows empty state when no saved searches', () => {
      setMockSavedSearches([]);

      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      const savedSearchesButton = screen.getByLabelText('Saved searches');
      fireEvent.click(savedSearchesButton);

      expect(screen.getByText('No saved searches yet.')).toBeInTheDocument();
    });

    it('loads saved search when clicked', () => {
      setMockSavedSearches([
        {
          id: 'search-1',
          name: 'High Risk Events',
          query: 'suspicious activity',
          filters: { severity: 'high' },
          createdAt: '2024-01-01T00:00:00Z',
        },
      ]);
      mockLoadSearch.mockReturnValue({
        query: 'suspicious activity',
        filters: { severity: 'high' },
      });

      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      const savedSearchesButton = screen.getByLabelText('Saved searches');
      fireEvent.click(savedSearchesButton);

      const searchItem = screen.getByText('High Risk Events');
      fireEvent.click(searchItem);

      expect(mockLoadSearch).toHaveBeenCalledWith('search-1');
      expect(mockOnQueryChange).toHaveBeenCalledWith('suspicious activity');
    });

    it('deletes saved search when delete button is clicked', () => {
      setMockSavedSearches([
        {
          id: 'search-to-delete',
          name: 'Delete Me',
          query: 'test',
          filters: {},
          createdAt: '2024-01-01T00:00:00Z',
        },
      ]);

      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      const savedSearchesButton = screen.getByLabelText('Saved searches');
      fireEvent.click(savedSearchesButton);

      const deleteButton = screen.getByRole('button', { name: /delete saved search/i });
      fireEvent.click(deleteButton);

      expect(mockDeleteSearch).toHaveBeenCalledWith('search-to-delete');
    });

    it('shows filter count for saved searches with multiple filters', () => {
      setMockSavedSearches([
        {
          id: '1',
          name: 'Filtered Search',
          query: 'test',
          filters: { camera_id: 'front_door', severity: 'high' },
          createdAt: '2024-01-01T00:00:00Z',
        },
      ]);

      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);

      const savedSearchesButton = screen.getByLabelText('Saved searches');
      fireEvent.click(savedSearchesButton);

      expect(screen.getByText('+ 2 filters')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has accessible search input', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const input = screen.getByRole('textbox', { name: /search events/i });
      expect(input).toHaveAttribute('aria-label', 'Search events');
    });

    it('has accessible filter toggle button', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      expect(filtersButton).toHaveAttribute('aria-expanded');
    });

    it('has accessible help button', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const helpButton = screen.getByRole('button', { name: /show search syntax help/i });
      expect(helpButton).toHaveAttribute('aria-label');
      expect(helpButton).toHaveAttribute('aria-expanded');
    });

    it('has accessible saved searches button', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const savedSearchesButton = screen.getByLabelText('Saved searches');
      expect(savedSearchesButton).toHaveAttribute('aria-label');
      expect(savedSearchesButton).toHaveAttribute('aria-expanded');
    });

    it('disables input when isSearching is true', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          isSearching={true}
        />
      );
      const input = screen.getByRole('textbox', { name: /search events/i });
      expect(input).toBeDisabled();
    });
  });

  describe('Props handling', () => {
    it('uses initialFilters prop', () => {
      const initialFilters = {
        camera_id: 'front_door',
        severity: 'high',
        start_date: '2024-01-01',
      };
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          initialFilters={initialFilters}
        />
      );
      // Component should render without errors
      expect(screen.getByRole('textbox', { name: /search events/i })).toBeInTheDocument();
    });

    it('renders with cameras prop', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={mockCameras}
        />
      );
      expect(screen.getByRole('textbox', { name: /search events/i })).toBeInTheDocument();
    });

    it('renders with empty cameras array', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={[]}
        />
      );
      expect(screen.getByRole('textbox', { name: /search events/i })).toBeInTheDocument();
    });
  });

  describe('Edge cases', () => {
    it('handles whitespace-only query submission', () => {
      render(<SearchBar query="   " onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      fireEvent.click(searchButton);
      // Should not call onSearch for whitespace-only query
      expect(mockOnSearch).not.toHaveBeenCalled();
    });

    it('handles Enter key on whitespace-only query', () => {
      render(<SearchBar query="   " onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(mockOnSearch).not.toHaveBeenCalled();
    });

    it('handles special characters in query', () => {
      const specialQuery = 'test@#$%^&*()';
      render(
        <SearchBar query={specialQuery} onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(mockOnSearch).toHaveBeenCalledWith(specialQuery, expect.any(Object));
    });

    it('handles very long query strings', () => {
      const longQuery = 'a'.repeat(1000);
      render(
        <SearchBar query={longQuery} onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      const input = screen.getByRole('textbox', { name: /search events/i });
      expect(input).toHaveValue(longQuery);
    });

    it('handles query with leading/trailing whitespace', () => {
      render(
        <SearchBar
          query="  test query  "
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
        />
      );
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      fireEvent.click(searchButton);
      // Should trim before calling onSearch
      expect(mockOnSearch).toHaveBeenCalledWith('test query', expect.any(Object));
    });

    it('handles rapid consecutive searches', () => {
      render(<SearchBar query="test" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      fireEvent.click(searchButton);
      fireEvent.click(searchButton);
      fireEvent.click(searchButton);
      expect(mockOnSearch).toHaveBeenCalledTimes(3);
    });

    it('handles keyboard events other than Enter and Escape', () => {
      render(<SearchBar query="test" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'a' });
      fireEvent.keyDown(input, { key: 'Tab' });
      fireEvent.keyDown(input, { key: 'Shift' });
      // Should not trigger any action
      expect(mockOnSearch).not.toHaveBeenCalled();
      expect(mockOnQueryChange).not.toHaveBeenCalled();
    });
  });

  describe('Button states', () => {
    it('search button is enabled with non-empty query', () => {
      render(<SearchBar query="test" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      expect(searchButton).not.toBeDisabled();
    });

    it('search button shows correct icon when not searching', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          isSearching={false}
        />
      );
      expect(screen.getByText('Search')).toBeInTheDocument();
    });

    it('does not show clear button when query is empty', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.queryByRole('button', { name: /clear search/i })).not.toBeInTheDocument();
    });

    it('shows clear button when query has whitespace', () => {
      render(<SearchBar query=" " onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument();
    });
  });

  describe('Filter state management', () => {
    it('submits search with empty filters object by default', () => {
      render(<SearchBar query="test" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      fireEvent.click(searchButton);
      expect(mockOnSearch).toHaveBeenCalledWith('test', {});
    });

    it('handles undefined initialFilters', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          initialFilters={undefined}
        />
      );
      expect(screen.getByRole('textbox', { name: /search events/i })).toBeInTheDocument();
    });
  });

  describe('Component lifecycle', () => {
    it('renders correctly on mount', () => {
      const { container } = render(
        <SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      expect(container.firstChild).toBeInTheDocument();
    });

    it('displays correct initial query value', () => {
      render(
        <SearchBar
          query="initial query"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
        />
      );
      expect(screen.getByDisplayValue('initial query')).toBeInTheDocument();
    });

    it('respects isSearching false state', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          isSearching={false}
        />
      );
      expect(screen.getByText('Search')).toBeInTheDocument();
    });
  });

  describe('Saved searches integration', () => {
    it('displays saved searches count when available', () => {
      setMockSavedSearches([
        { id: '1', name: 'Test 1', query: 'test1', filters: {}, createdAt: '2024-01-01T00:00:00Z' },
        { id: '2', name: 'Test 2', query: 'test2', filters: {}, createdAt: '2024-01-01T00:00:00Z' },
        { id: '3', name: 'Test 3', query: 'test3', filters: {}, createdAt: '2024-01-01T00:00:00Z' },
      ]);
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('does not display count badge when no saved searches', () => {
      setMockSavedSearches([]);
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      // The saved searches button should still exist but no count badge
      expect(screen.getByLabelText('Saved searches')).toBeInTheDocument();
    });

    it('renders without save button when query is empty', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.queryByRole('button', { name: /save search/i })).not.toBeInTheDocument();
    });

    it('renders with save button when query has content', () => {
      render(
        <SearchBar query="my search" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      expect(screen.getByRole('button', { name: /save search/i })).toBeInTheDocument();
    });
  });

  describe('Filter button styling', () => {
    it('shows active state when filters button is collapsed but no filters active', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const filtersButton = screen.getByRole('button', { name: /toggle advanced filters/i });
      expect(filtersButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('does not show Active badge when no filters are set', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.queryByText('Active')).not.toBeInTheDocument();
    });
  });

  describe('Component initialization', () => {
    it('initializes with default props', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.getByRole('textbox')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^search$/i })).toBeInTheDocument();
    });

    it('uses custom placeholder when provided', () => {
      const customPlaceholder = 'Search for events here...';
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          placeholder={customPlaceholder}
        />
      );
      expect(screen.getByPlaceholderText(customPlaceholder)).toBeInTheDocument();
    });

    it('handles undefined cameras gracefully', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={undefined}
        />
      );
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('handles empty cameras array', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          cameras={[]}
        />
      );
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });
  });

  describe('Query handling', () => {
    it('displays provided query value', () => {
      const testQuery = 'test search query';
      render(
        <SearchBar query={testQuery} onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      expect(screen.getByDisplayValue(testQuery)).toBeInTheDocument();
    });

    it('handles whitespace-only query as empty', () => {
      render(<SearchBar query="   " onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      expect(searchButton).toBeDisabled();
    });

    it('enables search button with valid query', () => {
      render(
        <SearchBar query="valid query" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      const searchButton = screen.getByRole('button', { name: /^search$/i });
      expect(searchButton).not.toBeDisabled();
    });
  });

  describe('Search button states', () => {
    it('shows default search button when not searching', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          isSearching={false}
        />
      );
      expect(screen.getByText('Search')).toBeInTheDocument();
      expect(screen.queryByText('Searching...')).not.toBeInTheDocument();
    });

    it('disables input during search', () => {
      render(
        <SearchBar
          query="test"
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          isSearching={true}
        />
      );
      expect(screen.getByRole('textbox', { name: /search events/i })).toBeDisabled();
    });
  });

  describe('Keyboard shortcuts', () => {
    it('does not submit on Enter with whitespace-only query', () => {
      render(<SearchBar query="   " onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(mockOnSearch).not.toHaveBeenCalled();
    });

    it('ignores other keys', () => {
      render(<SearchBar query="test" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      const input = screen.getByRole('textbox', { name: /search events/i });
      fireEvent.keyDown(input, { key: 'a' });
      fireEvent.keyDown(input, { key: 'Tab' });
      expect(mockOnSearch).not.toHaveBeenCalled();
    });
  });

  describe('Filter button states', () => {
    it('shows Active badge when initial filters provided', () => {
      render(
        <SearchBar
          query=""
          onQueryChange={mockOnQueryChange}
          onSearch={mockOnSearch}
          initialFilters={{ severity: 'high' }}
        />
      );
      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    it('does not show Active badge without filters', () => {
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.queryByText('Active')).not.toBeInTheDocument();
    });
  });

  describe('Saved searches count badge', () => {
    it('shows count badge with saved searches', () => {
      setMockSavedSearches([
        { id: '1', name: 'Search 1', query: 'q1', filters: {}, createdAt: '2024-01-01T00:00:00Z' },
        { id: '2', name: 'Search 2', query: 'q2', filters: {}, createdAt: '2024-01-01T00:00:00Z' },
        { id: '3', name: 'Search 3', query: 'q3', filters: {}, createdAt: '2024-01-01T00:00:00Z' },
      ]);
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('does not show count badge without saved searches', () => {
      setMockSavedSearches([]);
      render(<SearchBar query="" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      // Badge element should not exist when count is 0
      expect(screen.queryByText('0')).not.toBeInTheDocument();
    });
  });

  describe('Save button visibility', () => {
    it('hides save button with whitespace-only query', () => {
      render(<SearchBar query="   " onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />);
      expect(screen.queryByRole('button', { name: /save search/i })).not.toBeInTheDocument();
    });

    it('shows save button with valid query', () => {
      render(
        <SearchBar query="valid query" onQueryChange={mockOnQueryChange} onSearch={mockOnSearch} />
      );
      expect(screen.getByRole('button', { name: /save search/i })).toBeInTheDocument();
    });
  });
});
