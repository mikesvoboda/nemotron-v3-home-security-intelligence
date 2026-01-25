import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import EntitiesPage from './EntitiesPage';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchEntities: vi.fn(),
    fetchEntity: vi.fn(),
    fetchCameras: vi.fn(),
  };
});

// Mock IntersectionObserver for infinite scroll
class MockIntersectionObserver {
  callback: IntersectionObserverCallback;
  elements: Element[] = [];

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
  }

  observe(element: Element) {
    this.elements.push(element);
  }

  unobserve(element: Element) {
    this.elements = this.elements.filter((el) => el !== element);
  }

  disconnect() {
    this.elements = [];
  }
}

// @ts-expect-error - Mocking IntersectionObserver
global.IntersectionObserver = MockIntersectionObserver;

const mockFetchEntities = vi.mocked(api.fetchEntities);
const mockFetchEntity = vi.mocked(api.fetchEntity);
const mockFetchCameras = vi.mocked(api.fetchCameras);

// Create a fresh QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
    },
  });
}

// Helper to render with router and query client
const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{component}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe('EntitiesPage', () => {
  // Mock entity data
  const mockEntities: api.EntitySummary[] = [
    {
      id: 'entity-001',
      entity_type: 'person',
      first_seen: '2024-01-15T08:00:00Z',
      last_seen: '2024-01-15T10:00:00Z',
      appearance_count: 5,
      cameras_seen: ['front_door', 'back_yard'],
      thumbnail_url: 'https://example.com/thumb1.jpg',
    },
    {
      id: 'entity-002',
      entity_type: 'vehicle',
      first_seen: '2024-01-15T09:00:00Z',
      last_seen: '2024-01-15T09:30:00Z',
      appearance_count: 2,
      cameras_seen: ['driveway'],
      thumbnail_url: null,
    },
  ];

  const mockCameras: api.Camera[] = [
    {
      id: 'front_door',
      name: 'Front Door',
      folder_path: '/export/foscam/front_door',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
    {
      id: 'back_yard',
      name: 'Back Yard',
      folder_path: '/export/foscam/back_yard',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
  ];

  const mockEntityDetail: api.EntityDetail = {
    ...mockEntities[0],
    appearances: [
      {
        detection_id: 'det-001',
        camera_id: 'front_door',
        camera_name: 'Front Door',
        timestamp: '2024-01-15T10:00:00Z',
        thumbnail_url: 'https://example.com/thumb1.jpg',
        similarity_score: 0.95,
        attributes: {},
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Default successful response (NEM-2075: pagination envelope format)
    mockFetchEntities.mockResolvedValue({
      items: mockEntities,
      pagination: {
        total: mockEntities.length,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    });
    mockFetchEntity.mockResolvedValue(mockEntityDetail);
    mockFetchCameras.mockResolvedValue(mockCameras);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the page header with title and description', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      expect(screen.getByText('Entities')).toBeInTheDocument();
      expect(
        screen.getByText('Track and identify people and vehicles across your cameras')
      ).toBeInTheDocument();
    });

    it('displays loading state initially with skeleton loaders', () => {
      mockFetchEntities.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );
      renderWithProviders(<EntitiesPage />);

      expect(screen.getAllByTestId('entity-card-skeleton').length).toBeGreaterThan(0);
    });

    it('displays entity cards after loading', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Check for entity type badges
      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays error state when API fails', async () => {
      mockFetchEntities.mockRejectedValue(new Error('API Error'));

      renderWithProviders(<EntitiesPage />);

      // Wait for the query to fail (including any retries from TanStack Query)
      await waitFor(
        () => {
          expect(screen.getByText('API Error')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByText('Try Again')).toBeInTheDocument();
    });

    it('displays empty state when no entities', async () => {
      mockFetchEntities.mockResolvedValue({
        items: [],
        pagination: {
          total: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      });

      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.getByText('No Entities Tracked Yet')).toBeInTheDocument();
      });
    });

    it('displays enhanced empty state with "How it works" section', async () => {
      mockFetchEntities.mockResolvedValue({
        items: [],
        pagination: {
          total: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      });

      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.getByText('How it works')).toBeInTheDocument();
      });

      // Check for steps
      expect(screen.getByText(/Camera detects a person or vehicle/i)).toBeInTheDocument();
      expect(screen.getByText(/AI extracts visual features/i)).toBeInTheDocument();
    });

    it('displays CTA button in empty state', async () => {
      mockFetchEntities.mockResolvedValue({
        items: [],
        pagination: {
          total: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      });

      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        const ctaButton = screen.getByRole('link', { name: /View Detection Settings/i });
        expect(ctaButton).toBeInTheDocument();
        expect(ctaButton).toHaveAttribute('href', '/settings');
      });
    });
  });

  describe('Entity Type Filtering', () => {
    it('displays simpler empty state when filtered by person with no results', async () => {
      // First call returns data, subsequent calls return empty
      mockFetchEntities
        .mockResolvedValueOnce({
          items: mockEntities,
          pagination: { total: 2, limit: 50, offset: 0, has_more: false },
        })
        .mockResolvedValue({
          items: [],
          pagination: { total: 0, limit: 50, offset: 0, has_more: false },
        });

      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Click the Persons filter
      await user.click(screen.getByText('Persons'));

      await waitFor(() => {
        expect(screen.getByText('No Persons Found')).toBeInTheDocument();
      });

      // Should NOT show the full "How it works" section
      expect(screen.queryByText('How it works')).not.toBeInTheDocument();
    });

    it('displays simpler empty state when filtered by vehicle with no results', async () => {
      mockFetchEntities
        .mockResolvedValueOnce({
          items: mockEntities,
          pagination: { total: 2, limit: 50, offset: 0, has_more: false },
        })
        .mockResolvedValue({
          items: [],
          pagination: { total: 0, limit: 50, offset: 0, has_more: false },
        });

      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Click the Vehicles filter button (has aria-pressed attribute)
      const vehiclesFilterButton = screen.getByRole('button', {
        name: /Vehicles/i,
        pressed: false,
      });
      await user.click(vehiclesFilterButton);

      await waitFor(() => {
        expect(screen.getByText('No Vehicles Found')).toBeInTheDocument();
      });

      // Should NOT show the full "How it works" section
      expect(screen.queryByText('How it works')).not.toBeInTheDocument();
    });

    it('renders filter buttons for All, Persons, and Vehicles', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Check filter buttons exist (they have aria-pressed attribute)
      expect(screen.getByRole('button', { name: /All/i, pressed: true })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Persons/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Vehicles/i, pressed: false })).toBeInTheDocument();
    });

    it('filters entities when Persons button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Click the Persons filter
      await user.click(screen.getByText('Persons'));

      // API should be called with entity_type filter
      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalledWith(
          expect.objectContaining({ entity_type: 'person' })
        );
      });
    });

    it('filters entities when Vehicles button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Click the Vehicles filter button (has aria-pressed attribute)
      const vehiclesFilterButton = screen.getByRole('button', {
        name: /Vehicles/i,
        pressed: false,
      });
      await user.click(vehiclesFilterButton);

      // API should be called with entity_type filter
      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalledWith(
          expect.objectContaining({ entity_type: 'vehicle' })
        );
      });
    });
  });

  describe('Time Range Filtering', () => {
    it('renders time range dropdown with all options', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      const timeRangeSelect = screen.getByLabelText('Filter by time range');
      expect(timeRangeSelect).toBeInTheDocument();

      // Check all options are present
      expect(screen.getByRole('option', { name: 'All Time' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Last 1h' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Last 24h' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Last 7d' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Last 30d' })).toBeInTheDocument();
    });

    it('filters entities when time range is changed', async () => {
      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      const timeRangeSelect = screen.getByLabelText('Filter by time range');
      await user.selectOptions(timeRangeSelect, '24h');

      // API should be called with since parameter
      await waitFor(() => {
        const calls = mockFetchEntities.mock.calls;
        const lastCall = calls[calls.length - 1][0];
        expect(lastCall?.since).toBeDefined();
      });
    });
  });

  describe('Camera Filtering', () => {
    it('renders camera dropdown with all cameras', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      const cameraSelect = screen.getByLabelText('Filter by camera');
      expect(cameraSelect).toBeInTheDocument();

      // Check default option
      expect(screen.getByRole('option', { name: 'All Cameras' })).toBeInTheDocument();

      // Check camera options are present
      expect(screen.getByRole('option', { name: 'Front Door' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Back Yard' })).toBeInTheDocument();
    });

    it('filters entities when camera is selected', async () => {
      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      const cameraSelect = screen.getByLabelText('Filter by camera');
      await user.selectOptions(cameraSelect, 'front_door');

      // API should be called with camera_id filter
      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalledWith(
          expect.objectContaining({ camera_id: 'front_door' })
        );
      });
    });
  });

  describe('Clear Filters', () => {
    it('shows clear filters button when filters are applied and no results', async () => {
      mockFetchEntities
        .mockResolvedValueOnce({
          items: mockEntities,
          pagination: { total: 2, limit: 50, offset: 0, has_more: false },
        })
        .mockResolvedValue({
          items: [],
          pagination: { total: 0, limit: 50, offset: 0, has_more: false },
        });

      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Apply a filter
      await user.click(screen.getByText('Persons'));

      await waitFor(() => {
        expect(screen.getByText('No Persons Found')).toBeInTheDocument();
      });

      // Clear filters button should be present
      expect(screen.getByText('Clear Filters')).toBeInTheDocument();
    });
  });

  describe('Refresh functionality', () => {
    it('renders refresh button', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      expect(screen.getByLabelText('Refresh entities')).toBeInTheDocument();
    });

    it('reloads entities when refresh button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Get initial call count
      const initialCallCount = mockFetchEntities.mock.calls.length;

      // Click refresh
      await user.click(screen.getByLabelText('Refresh entities'));

      // API should be called again
      await waitFor(() => {
        expect(mockFetchEntities.mock.calls.length).toBeGreaterThan(initialCallCount);
      });
    });
  });

  describe('Entity detail modal', () => {
    it('opens modal when entity card is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Find and click the first entity card
      const entityCards = screen.getAllByRole('button');
      const entityCard = entityCards.find((btn) =>
        btn.getAttribute('aria-label')?.includes('View entity')
      );

      if (entityCard) {
        await user.click(entityCard);

        // API should fetch entity detail
        await waitFor(() => {
          expect(mockFetchEntity).toHaveBeenCalledWith('entity-001');
        });

        // Modal should open
        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });
      }
    });
  });

  describe('Stats display', () => {
    it('displays entity type counts', async () => {
      renderWithProviders(<EntitiesPage />);

      // Wait for stats to appear (more reliable than just waiting for loading to disappear)
      await waitFor(() => {
        expect(screen.getByText('1 person')).toBeInTheDocument();
      });

      // Both stats should be present
      expect(screen.getByText('1 person')).toBeInTheDocument();
      expect(screen.getByText('1 vehicle')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper heading hierarchy', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      const mainHeading = screen.getByRole('heading', { level: 1 });
      expect(mainHeading).toHaveTextContent('Entities');
    });

    it('filter buttons have aria-pressed attribute', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      const allButton = screen.getByText('All');
      expect(allButton).toHaveAttribute('aria-pressed', 'true');

      const personsButton = screen.getByText('Persons');
      expect(personsButton).toHaveAttribute('aria-pressed', 'false');
    });

    it('refresh button is accessible', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      const refreshButton = screen.getByLabelText('Refresh entities');
      expect(refreshButton).toBeInTheDocument();
    });

    it('time range filter has label', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      expect(screen.getByLabelText('Filter by time range')).toBeInTheDocument();
    });

    it('camera filter has label', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      expect(screen.getByLabelText('Filter by camera')).toBeInTheDocument();
    });
  });

  describe('Infinite Scroll', () => {
    it('renders infinite scroll sentinel when there are more entities', async () => {
      mockFetchEntities.mockResolvedValue({
        items: mockEntities,
        pagination: {
          total: 100,
          limit: 50,
          offset: 0,
          has_more: true,
          next_cursor: 'cursor_page2',
        },
      });

      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Should show the infinite scroll sentinel
      expect(screen.getByTestId('infinite-scroll-sentinel')).toBeInTheDocument();
    });

    it('shows end message when all entities are loaded', async () => {
      mockFetchEntities.mockResolvedValue({
        items: mockEntities,
        pagination: {
          total: 2,
          limit: 50,
          offset: 0,
          has_more: false,
          next_cursor: null,
        },
      });

      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Should show end message
      expect(screen.getByTestId('infinite-scroll-end')).toBeInTheDocument();
      expect(screen.getByText("You've seen all entities")).toBeInTheDocument();
    });

    it('shows entity count when more entities available', async () => {
      mockFetchEntities.mockResolvedValue({
        items: mockEntities,
        pagination: {
          total: 100,
          limit: 50,
          offset: 0,
          has_more: true,
          next_cursor: 'cursor_page2',
        },
      });

      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Should show count indicator when there are more entities
      expect(screen.getByText(/showing 2 of 100/i)).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies NVIDIA green accent color to icons', async () => {
      const { container } = renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Check for the NVIDIA green color class on text elements
      const greenElements = container.querySelectorAll('[class*="text-[#76B900]"]');
      expect(greenElements.length).toBeGreaterThan(0);
    });

    it('has dark theme background', async () => {
      const { container } = renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Check for the dark background class
      const darkBgElements = container.querySelectorAll('[class*="bg-[#1F1F1F]"]');
      expect(darkBgElements.length).toBeGreaterThan(0);
    });
  });

  describe('Entity Grouping', () => {
    it('groups entities into People and Vehicles sections', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Should render People group section
      expect(screen.getByTestId('entity-group-people')).toBeInTheDocument();
      expect(screen.getByTestId('entity-group-header-people')).toBeInTheDocument();

      // Should render Vehicles group section
      expect(screen.getByTestId('entity-group-vehicles')).toBeInTheDocument();
      expect(screen.getByTestId('entity-group-header-vehicles')).toBeInTheDocument();
    });

    it('displays correct count in each section header', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // People section should show count of 1
      expect(screen.getByTestId('entity-group-count-people')).toHaveTextContent('1');

      // Vehicles section should show count of 1
      expect(screen.getByTestId('entity-group-count-vehicles')).toHaveTextContent('1');
    });

    it('hides empty Unknown section when no unknown entities', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Unknown section should not be rendered when there are no unknown entities
      expect(screen.queryByTestId('entity-group-unknown')).not.toBeInTheDocument();
    });

    it('shows Unknown section collapsed by default when unknown entities exist', async () => {
      // Add an unknown entity type to the mock data
      const entitiesWithUnknown: api.EntitySummary[] = [
        ...mockEntities,
        {
          id: 'entity-003',
          entity_type: 'unknown_type',
          first_seen: '2024-01-15T07:00:00Z',
          last_seen: '2024-01-15T07:30:00Z',
          appearance_count: 1,
          cameras_seen: ['garage'],
          thumbnail_url: null,
        },
      ];

      mockFetchEntities.mockResolvedValue({
        items: entitiesWithUnknown,
        pagination: {
          total: entitiesWithUnknown.length,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      });

      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Unknown section should exist
      expect(screen.getByTestId('entity-group-unknown')).toBeInTheDocument();

      // Unknown section header should be present
      expect(screen.getByTestId('entity-group-header-unknown')).toBeInTheDocument();

      // Unknown section should be collapsed by default (content not visible)
      expect(screen.queryByTestId('entity-group-content-unknown')).not.toBeInTheDocument();

      // Should show collapsed icon
      expect(screen.getByTestId('collapse-icon-collapsed')).toBeInTheDocument();
    });

    it('expands Unknown section when header is clicked', async () => {
      // Add an unknown entity type to the mock data
      const entitiesWithUnknown: api.EntitySummary[] = [
        ...mockEntities,
        {
          id: 'entity-003',
          entity_type: 'unknown_type',
          first_seen: '2024-01-15T07:00:00Z',
          last_seen: '2024-01-15T07:30:00Z',
          appearance_count: 1,
          cameras_seen: ['garage'],
          thumbnail_url: null,
        },
      ];

      mockFetchEntities.mockResolvedValue({
        items: entitiesWithUnknown,
        pagination: {
          total: entitiesWithUnknown.length,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      });

      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // Click the Unknown section header to expand it
      await user.click(screen.getByTestId('entity-group-header-unknown'));

      // Unknown section content should now be visible
      await waitFor(() => {
        expect(screen.getByTestId('entity-group-content-unknown')).toBeInTheDocument();
      });
    });

    it('collapses People section when header is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // People section content should initially be visible (expanded by default)
      expect(screen.getByTestId('entity-group-content-people')).toBeInTheDocument();

      // Click the People section header to collapse it
      await user.click(screen.getByTestId('entity-group-header-people'));

      // People section content should now be hidden
      await waitFor(() => {
        expect(screen.queryByTestId('entity-group-content-people')).not.toBeInTheDocument();
      });
    });

    it('shows entity cards in the appropriate group sections', async () => {
      renderWithProviders(<EntitiesPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
      });

      // People section should contain entity cards
      const peopleSection = screen.getByTestId('entity-group-content-people');
      expect(peopleSection.querySelectorAll('[data-testid="entity-card"]').length).toBe(1);

      // Vehicles section should contain entity cards
      const vehiclesSection = screen.getByTestId('entity-group-content-vehicles');
      expect(vehiclesSection.querySelectorAll('[data-testid="entity-card"]').length).toBe(1);
    });
  });
});
