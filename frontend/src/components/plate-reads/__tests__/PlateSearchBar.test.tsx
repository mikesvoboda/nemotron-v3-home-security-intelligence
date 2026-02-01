/**
 * @fileoverview Tests for PlateSearchBar component.
 *
 * Tests the search bar functionality including text input,
 * exact match toggle, and advanced filters panel.
 */
import { screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { renderWithProviders } from '../../../test-utils/renderWithProviders';
import PlateSearchBar from '../PlateSearchBar';

import type { PlateSearchFilters } from '../PlateSearchBar';

// Mock the useCamerasQuery hook
vi.mock('../../../hooks/useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(() => ({
    cameras: [
      { id: 'cam-1', name: 'Front Door', status: 'online' },
      { id: 'cam-2', name: 'Back Yard', status: 'online' },
    ],
    isLoading: false,
    error: null,
  })),
}));

describe('PlateSearchBar', () => {
  const defaultProps = {
    searchText: '',
    onSearchTextChange: vi.fn(),
    exactMatch: false,
    onExactMatchChange: vi.fn(),
    filters: {} as PlateSearchFilters,
    onFiltersChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Search Input', () => {
    it('renders search input with placeholder', () => {
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      expect(
        screen.getByPlaceholderText('Search plate text (e.g., ABC123, XYZ)...')
      ).toBeInTheDocument();
    });

    it('renders custom placeholder', () => {
      renderWithProviders(
        <PlateSearchBar {...defaultProps} placeholder="Custom placeholder" />
      );

      expect(screen.getByPlaceholderText('Custom placeholder')).toBeInTheDocument();
    });

    it('displays current search text value', () => {
      renderWithProviders(<PlateSearchBar {...defaultProps} searchText="ABC123" />);

      expect(screen.getByDisplayValue('ABC123')).toBeInTheDocument();
    });

    it('calls onSearchTextChange when typing', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      const input = screen.getByLabelText('Search plate text');
      await user.type(input, 'XYZ');

      // Controlled input: each keystroke triggers onChange with the character typed
      // Since searchText prop stays empty, input value is always empty + new char
      expect(defaultProps.onSearchTextChange).toHaveBeenCalledTimes(3);
      expect(defaultProps.onSearchTextChange).toHaveBeenNthCalledWith(1, 'X');
      expect(defaultProps.onSearchTextChange).toHaveBeenNthCalledWith(2, 'Y');
      expect(defaultProps.onSearchTextChange).toHaveBeenNthCalledWith(3, 'Z');
    });

    it('clears search text when clear button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} searchText="ABC123" />);

      const clearButton = screen.getByLabelText('Clear search');
      await user.click(clearButton);

      expect(defaultProps.onSearchTextChange).toHaveBeenCalledWith('');
    });

    it('hides clear button when search text is empty', () => {
      renderWithProviders(<PlateSearchBar {...defaultProps} searchText="" />);

      expect(screen.queryByLabelText('Clear search')).not.toBeInTheDocument();
    });

    it('clears search text when Escape key is pressed', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} searchText="ABC" />);

      const input = screen.getByLabelText('Search plate text');
      await user.click(input);
      await user.keyboard('{Escape}');

      expect(defaultProps.onSearchTextChange).toHaveBeenCalledWith('');
    });

    it('disables input when isSearching is true', () => {
      renderWithProviders(<PlateSearchBar {...defaultProps} isSearching={true} />);

      expect(screen.getByLabelText('Search plate text')).toBeDisabled();
    });
  });

  describe('Exact Match Toggle', () => {
    it('renders exact match checkbox', () => {
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      expect(screen.getByText('Exact match')).toBeInTheDocument();
      expect(screen.getByRole('checkbox')).toBeInTheDocument();
    });

    it('displays checked state based on exactMatch prop', () => {
      renderWithProviders(<PlateSearchBar {...defaultProps} exactMatch={true} />);

      expect(screen.getByRole('checkbox')).toBeChecked();
    });

    it('calls onExactMatchChange when toggled', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} exactMatch={false} />);

      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);

      expect(defaultProps.onExactMatchChange).toHaveBeenCalledWith(true);
    });
  });

  describe('Filters Toggle Button', () => {
    it('renders filters toggle button', () => {
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      expect(screen.getByLabelText('Toggle advanced filters')).toBeInTheDocument();
      expect(screen.getByText('Filters')).toBeInTheDocument();
    });

    it('shows Active badge when filters are active', () => {
      renderWithProviders(
        <PlateSearchBar
          {...defaultProps}
          filters={{ camera_id: 'cam-1' }}
        />
      );

      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    it('shows Active badge when search text is present', () => {
      renderWithProviders(
        <PlateSearchBar {...defaultProps} searchText="ABC" />
      );

      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    it('toggles advanced filters panel on click', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      // Panel should not be visible initially
      expect(screen.queryByText('Camera')).not.toBeInTheDocument();

      // Click to expand
      const toggleButton = screen.getByLabelText('Toggle advanced filters');
      await user.click(toggleButton);

      // Panel should now be visible
      expect(screen.getByText('Camera')).toBeInTheDocument();

      // Click to collapse
      await user.click(toggleButton);

      // Panel should be hidden again
      expect(screen.queryByLabelText('plate-search-camera')).not.toBeInTheDocument();
    });
  });

  describe('Advanced Filters Panel', () => {
    it('renders camera dropdown with options', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      // Expand filters
      await user.click(screen.getByLabelText('Toggle advanced filters'));

      expect(screen.getByLabelText('Camera')).toBeInTheDocument();
      expect(screen.getByText('All Cameras')).toBeInTheDocument();
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Back Yard')).toBeInTheDocument();
    });

    it('calls onFiltersChange when camera is selected', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      // Expand filters
      await user.click(screen.getByLabelText('Toggle advanced filters'));

      // Select a camera
      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'cam-1');

      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({
        camera_id: 'cam-1',
      });
    });

    it('renders date range picker', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      // Expand filters
      await user.click(screen.getByLabelText('Toggle advanced filters'));

      expect(screen.getByText('Date Range')).toBeInTheDocument();
      expect(screen.getByLabelText('From')).toBeInTheDocument();
      expect(screen.getByLabelText('To')).toBeInTheDocument();
    });

    it('renders confidence threshold slider', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      // Expand filters
      await user.click(screen.getByLabelText('Toggle advanced filters'));

      expect(screen.getByText(/Min\. Confidence/)).toBeInTheDocument();
      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    it('calls onFiltersChange when confidence slider changes', () => {
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      // Expand filters
      fireEvent.click(screen.getByLabelText('Toggle advanced filters'));

      // Change slider value
      const slider = screen.getByRole('slider');
      fireEvent.change(slider, { target: { value: '0.8' } });

      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({
        min_confidence: 0.8,
      });
    });

    it('renders clear all filters button', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      // Expand filters
      await user.click(screen.getByLabelText('Toggle advanced filters'));

      expect(screen.getByText('Clear All Filters')).toBeInTheDocument();
    });

    it('clears all filters when clear button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(
        <PlateSearchBar
          {...defaultProps}
          searchText="ABC"
          exactMatch={true}
          filters={{ camera_id: 'cam-1', min_confidence: 0.8 }}
        />
      );

      // Expand filters
      await user.click(screen.getByLabelText('Toggle advanced filters'));

      // Click clear
      await user.click(screen.getByText('Clear All Filters'));

      expect(defaultProps.onSearchTextChange).toHaveBeenCalledWith('');
      expect(defaultProps.onExactMatchChange).toHaveBeenCalledWith(false);
      expect(defaultProps.onFiltersChange).toHaveBeenCalledWith({});
    });

    it('disables clear button when no filters are active', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      // Expand filters
      await user.click(screen.getByLabelText('Toggle advanced filters'));

      expect(screen.getByText('Clear All Filters')).toBeDisabled();
    });
  });

  describe('Accessibility', () => {
    it('has proper aria-expanded state for filters toggle', async () => {
      const user = userEvent.setup();
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      const toggle = screen.getByLabelText('Toggle advanced filters');

      expect(toggle).toHaveAttribute('aria-expanded', 'false');

      await user.click(toggle);

      expect(toggle).toHaveAttribute('aria-expanded', 'true');
    });

    it('has proper aria-label on search input', () => {
      renderWithProviders(<PlateSearchBar {...defaultProps} />);

      expect(screen.getByLabelText('Search plate text')).toBeInTheDocument();
    });
  });
});
