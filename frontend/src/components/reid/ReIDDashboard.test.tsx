/**
 * Tests for ReIDDashboard - Cross-camera entity matching visualization
 *
 * NEM-5024 Phase 8: Re-ID Dashboard
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ReIDDashboard from './ReIDDashboard';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchEntities: vi.fn(),
    fetchEntity: vi.fn(),
    fetchEntityHistory: vi.fn(),
    fetchCameras: vi.fn(),
    fetchReidSimilar: vi.fn(),
  };
});

// Mock IntersectionObserver for any infinite scroll or lazy loading
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
const mockFetchEntityHistory = vi.mocked(api.fetchEntityHistory);
const mockFetchCameras = vi.mocked(api.fetchCameras);
const mockFetchReidSimilar = vi.mocked(api.fetchReidSimilar);

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

/**
 * Extended EntitySummary type for testing with household member info.
 * In production, this would come from backend API extensions.
 */
interface TestEntitySummary extends api.EntitySummary {
  household_member_id?: number;
  household_member_name?: string;
}

describe('ReIDDashboard', () => {
  // Mock entity data - note: household_member fields are extended for testing
  // In the real component, these would be handled differently
  const mockEntities: TestEntitySummary[] = [
    {
      id: 'entity-001',
      entity_type: 'person',
      first_seen: '2024-01-15T08:00:00Z',
      last_seen: '2024-01-15T10:00:00Z',
      appearance_count: 5,
      cameras_seen: ['front_door', 'back_yard', 'garage'],
      thumbnail_url: 'https://example.com/thumb1.jpg',
    },
    {
      id: 'entity-002',
      entity_type: 'vehicle',
      first_seen: '2024-01-15T09:00:00Z',
      last_seen: '2024-01-15T09:30:00Z',
      appearance_count: 2,
      cameras_seen: ['driveway', 'front_door'],
      thumbnail_url: null,
    },
    {
      id: 'entity-003',
      entity_type: 'person',
      first_seen: '2024-01-15T07:00:00Z',
      last_seen: '2024-01-15T11:00:00Z',
      appearance_count: 8,
      cameras_seen: ['front_door', 'living_room', 'kitchen'],
      thumbnail_url: 'https://example.com/thumb3.jpg',
      household_member_id: 1,
      household_member_name: 'John Doe',
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
      ingestion_mode: 'ftp',
      motion_sensitivity: 0.5,
    },
    {
      id: 'back_yard',
      name: 'Back Yard',
      folder_path: '/export/foscam/back_yard',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
      ingestion_mode: 'ftp',
      motion_sensitivity: 0.5,
    },
    {
      id: 'garage',
      name: 'Garage',
      folder_path: '/export/foscam/garage',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
      ingestion_mode: 'ftp',
      motion_sensitivity: 0.5,
    },
  ];

  const mockEntityDetail: api.EntityDetail = {
    id: mockEntities[0].id,
    entity_type: mockEntities[0].entity_type,
    first_seen: mockEntities[0].first_seen,
    last_seen: mockEntities[0].last_seen,
    appearance_count: mockEntities[0].appearance_count,
    cameras_seen: mockEntities[0].cameras_seen,
    thumbnail_url: mockEntities[0].thumbnail_url,
    appearances: [
      {
        detection_id: 'det-001',
        camera_id: 'front_door',
        camera_name: 'Front Door',
        timestamp: '2024-01-15T08:00:00Z',
        thumbnail_url: 'https://example.com/thumb1.jpg',
        similarity_score: 1.0,
        attributes: {},
      },
      {
        detection_id: 'det-002',
        camera_id: 'back_yard',
        camera_name: 'Back Yard',
        timestamp: '2024-01-15T09:00:00Z',
        thumbnail_url: 'https://example.com/thumb2.jpg',
        similarity_score: 0.95,
        attributes: {},
      },
      {
        detection_id: 'det-003',
        camera_id: 'garage',
        camera_name: 'Garage',
        timestamp: '2024-01-15T10:00:00Z',
        thumbnail_url: 'https://example.com/thumb3.jpg',
        similarity_score: 0.92,
        attributes: {},
      },
    ],
  };

  const mockEntityHistory: api.EntityHistoryResponse = {
    entity_id: 'entity-001',
    entity_type: 'person',
    appearances: mockEntityDetail.appearances ?? [],
    count: 3,
  };

  const mockSimilarEntities = {
    matches: [
      {
        entity_id: 'entity-003',
        entity_type: 'person',
        camera_id: 'front_door',
        timestamp: '2024-01-15T07:30:00Z',
        detection_id: 'det-010',
        similarity: 0.91,
        time_gap_seconds: 1800,
        source: 'postgresql',
        thumbnail_url: 'https://example.com/similar1.jpg',
        attributes: {},
      },
    ],
    total_matches: 1,
    threshold: 0.85,
    entity_type: 'person',
    include_historical: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Default successful responses
    // Cast mockEntities to api.EntitySummary[] since TestEntitySummary extends it
    mockFetchEntities.mockResolvedValue({
      items: mockEntities as unknown as api.EntitySummary[],
      pagination: {
        total: mockEntities.length,
        limit: 50,
        offset: 0,
        has_more: false,
      },
    });
    mockFetchEntity.mockResolvedValue(mockEntityDetail);
    mockFetchEntityHistory.mockResolvedValue(mockEntityHistory);
    mockFetchCameras.mockResolvedValue(mockCameras);
    mockFetchReidSimilar.mockResolvedValue(mockSimilarEntities);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the page header with title and description', async () => {
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      expect(screen.getByText('Re-Identification Dashboard')).toBeInTheDocument();
      expect(
        screen.getByText(/Track entity movements across cameras/)
      ).toBeInTheDocument();
    });

    it('displays loading state initially', () => {
      mockFetchEntities.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );
      renderWithProviders(<ReIDDashboard />);

      // Multiple skeletons are rendered during loading
      expect(screen.getAllByTestId('reid-loading-skeleton').length).toBeGreaterThan(0);
    });

    it('displays entity list after loading', async () => {
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      // Should show entities with cross-camera appearances
      expect(screen.getByText(/entity-001/i)).toBeInTheDocument();
    });

    it('displays error state when API fails', async () => {
      mockFetchEntities.mockRejectedValue(new Error('API Error'));

      renderWithProviders(<ReIDDashboard />);

      await waitFor(
        () => {
          expect(screen.getByText('API Error')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByText('Try Again')).toBeInTheDocument();
    });

    it('displays empty state when no entities with cross-camera appearances', async () => {
      mockFetchEntities.mockResolvedValue({
        items: [],
        pagination: {
          total: 0,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      });

      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.getByText(/No Cross-Camera Matches/i)).toBeInTheDocument();
      });
    });
  });

  describe('Cross-Camera Entity List', () => {
    it('shows entities seen on multiple cameras', async () => {
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      // Entity with 3 cameras should be visible
      const entityCard = screen.getByTestId('reid-entity-card-entity-001');
      expect(entityCard).toBeInTheDocument();
      expect(within(entityCard).getByText(/3 cameras/i)).toBeInTheDocument();
    });

    it('displays camera journey badges for each entity', async () => {
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      const entityCard = screen.getByTestId('reid-entity-card-entity-001');
      // Should show camera names in journey
      expect(within(entityCard).getByText(/Front Door/)).toBeInTheDocument();
    });

    it('highlights entities linked to household members', async () => {
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      // Entity-003 is linked to John Doe
      const linkedEntityCard = screen.getByTestId('reid-entity-card-entity-003');
      expect(within(linkedEntityCard).getByText('John Doe')).toBeInTheDocument();
      expect(within(linkedEntityCard).getByTestId('household-link-badge')).toBeInTheDocument();
    });
  });

  describe('Entity Selection and Detail View', () => {
    it('shows entity detail panel when entity is selected', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      // Click on entity card
      await user.click(screen.getByTestId('reid-entity-card-entity-001'));

      // Should show detail panel
      await waitFor(() => {
        expect(screen.getByTestId('reid-detail-panel')).toBeInTheDocument();
      });
    });

    it('displays camera journey timeline in detail view', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      await user.click(screen.getByTestId('reid-entity-card-entity-001'));

      await waitFor(() => {
        expect(screen.getByTestId('camera-journey-timeline')).toBeInTheDocument();
      });

      // Should show journey path: Front Door -> Back Yard -> Garage
      const timeline = screen.getByTestId('camera-journey-timeline');
      expect(within(timeline).getByText('Front Door')).toBeInTheDocument();
      expect(within(timeline).getByText('Back Yard')).toBeInTheDocument();
      expect(within(timeline).getByText('Garage')).toBeInTheDocument();
    });

    it('displays similarity scores for each appearance', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      await user.click(screen.getByTestId('reid-entity-card-entity-001'));

      await waitFor(() => {
        expect(screen.getByTestId('reid-detail-panel')).toBeInTheDocument();
      });

      // Should show similarity scores
      expect(screen.getByText('100%')).toBeInTheDocument(); // First detection
      expect(screen.getByText('95%')).toBeInTheDocument(); // Second detection
      expect(screen.getByText('92%')).toBeInTheDocument(); // Third detection
    });
  });

  describe('Camera Journey Visualization', () => {
    it('renders camera journey diagram', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      await user.click(screen.getByTestId('reid-entity-card-entity-001'));

      await waitFor(() => {
        expect(screen.getByTestId('camera-journey-diagram')).toBeInTheDocument();
      });
    });

    it('shows time spent at each camera location', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      await user.click(screen.getByTestId('reid-entity-card-entity-001'));

      await waitFor(() => {
        expect(screen.getByTestId('camera-journey-diagram')).toBeInTheDocument();
      });

      // Should show duration information (2h total from 8:00 to 10:00)
      const diagram = screen.getByTestId('camera-journey-diagram');
      expect(within(diagram).getByText(/Duration:/)).toBeInTheDocument();
    });
  });

  describe('Household Member Linking', () => {
    it('shows link to household page for matched entities', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      await user.click(screen.getByTestId('reid-entity-card-entity-003'));

      await waitFor(() => {
        expect(screen.getByTestId('reid-detail-panel')).toBeInTheDocument();
      });

      // Should have link to household member
      const householdLink = screen.getByRole('link', { name: /John Doe/i });
      expect(householdLink).toHaveAttribute('href', '/household');
    });

    it('shows "Unknown" indicator for unmatched entities', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      await user.click(screen.getByTestId('reid-entity-card-entity-001'));

      await waitFor(() => {
        expect(screen.getByTestId('reid-detail-panel')).toBeInTheDocument();
      });

      // Entity-001 is not linked to household member
      expect(screen.getByText('Unknown Person')).toBeInTheDocument();
    });
  });

  describe('Filtering', () => {
    it('filters by entity type', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      // Click persons filter
      await user.click(screen.getByRole('button', { name: /Persons/i }));

      await waitFor(() => {
        expect(mockFetchEntities).toHaveBeenCalledWith(
          expect.objectContaining({ entity_type: 'person' })
        );
      });
    });

    it('filters by minimum cameras seen', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      // Change minimum cameras filter
      const minCamerasSelect = screen.getByLabelText('Minimum cameras');
      await user.selectOptions(minCamerasSelect, '3');

      // Should filter out entities with fewer cameras
      await waitFor(() => {
        expect(screen.queryByTestId('reid-entity-card-entity-002')).not.toBeInTheDocument();
      });
    });
  });

  describe('Refresh Functionality', () => {
    it('refreshes data when refresh button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      const initialCallCount = mockFetchEntities.mock.calls.length;

      await user.click(screen.getByLabelText('Refresh data'));

      await waitFor(() => {
        expect(mockFetchEntities.mock.calls.length).toBeGreaterThan(initialCallCount);
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper heading hierarchy', async () => {
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      const mainHeading = screen.getByRole('heading', { level: 1 });
      expect(mainHeading).toHaveTextContent('Re-Identification Dashboard');
    });

    it('entity cards are keyboard accessible', async () => {
      const user = userEvent.setup();
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      const entityCard = screen.getByTestId('reid-entity-card-entity-001');
      entityCard.focus();

      await user.keyboard('{Enter}');

      await waitFor(() => {
        expect(screen.getByTestId('reid-detail-panel')).toBeInTheDocument();
      });
    });

    it('filter buttons have aria-pressed attribute', async () => {
      renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      const allButton = screen.getByRole('button', { name: /All/i });
      expect(allButton).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('Styling', () => {
    it('applies NVIDIA green accent color', async () => {
      const { container } = renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      const greenElements = container.querySelectorAll('[class*="text-[#76B900]"]');
      expect(greenElements.length).toBeGreaterThan(0);
    });

    it('uses dark theme background', async () => {
      const { container } = renderWithProviders(<ReIDDashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('reid-loading-skeleton')).not.toBeInTheDocument();
      });

      const darkBgElements = container.querySelectorAll('[class*="bg-[#1F1F1F]"]');
      expect(darkBgElements.length).toBeGreaterThan(0);
    });
  });
});
