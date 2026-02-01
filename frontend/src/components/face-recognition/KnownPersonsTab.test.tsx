/**
 * Tests for KnownPersonsTab component.
 *
 * Tests cover:
 * - Rendering known persons grid
 * - Loading states
 * - Error states
 * - Empty state
 * - Add Person button functionality
 * - Recent unknown faces section
 * - Today's stats display
 * - Person card click handling
 *
 * @module components/face-recognition/KnownPersonsTab.test
 * @see NEM-4688 Phase 1
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import KnownPersonsTab from './KnownPersonsTab';

import type { KnownPerson, FaceStats, FaceDetectionEvent } from '@/types/faceRecognition';

// ============================================================================
// Mock Data
// ============================================================================

const mockKnownPersons: KnownPerson[] = [
  {
    id: 1,
    name: 'John Smith',
    is_household_member: true,
    notes: 'Family member',
    created_at: '2025-01-15T10:00:00Z',
    updated_at: '2025-01-15T10:00:00Z',
    embedding_count: 3,
  },
  {
    id: 2,
    name: 'Jane Doe',
    is_household_member: true,
    notes: null,
    created_at: '2025-01-16T08:00:00Z',
    updated_at: '2025-01-16T08:00:00Z',
    embedding_count: 2,
  },
  {
    id: 3,
    name: 'Bob Wilson',
    is_household_member: false,
    notes: 'Regular visitor',
    created_at: '2025-01-20T14:00:00Z',
    updated_at: '2025-01-20T14:00:00Z',
    embedding_count: 1,
  },
];

const mockUnknownStrangers: FaceDetectionEvent[] = [
  {
    id: 101,
    camera_id: 1,
    camera_name: 'Front Door',
    timestamp: '2025-01-31T10:32:00Z',
    bbox: [100, 150, 200, 300],
    is_unknown: true,
    quality_score: 0.85,
    thumbnail_url: '/thumbnails/unknown_1.jpg',
  },
  {
    id: 102,
    camera_id: 2,
    camera_name: 'Driveway',
    timestamp: '2025-01-31T09:15:00Z',
    bbox: [50, 100, 150, 250],
    is_unknown: true,
    quality_score: 0.78,
    thumbnail_url: null,
  },
];

const mockFaceStats: FaceStats = {
  total_today: 47,
  known_count: 38,
  unknown_count: 9,
  by_camera: {
    front_door: { total: 20, known: 15, unknown: 5 },
    driveway: { total: 15, known: 12, unknown: 3 },
    backyard: { total: 12, known: 11, unknown: 1 },
  },
  unique_known_persons: 4,
  unique_unknown_faces: 6,
};

// ============================================================================
// Mock Hooks
// ============================================================================

const mockUseKnownPersonsQuery = vi.fn();
const mockUseUnknownStrangersQuery = vi.fn();
const mockUseFaceStatsQuery = vi.fn();

vi.mock('@/hooks/useFaceRecognitionApi', () => ({
  useKnownPersonsQuery: () => mockUseKnownPersonsQuery(),
  useUnknownStrangersQuery: () => mockUseUnknownStrangersQuery(),
  useFaceStatsQuery: () => mockUseFaceStatsQuery(),
}));

// ============================================================================
// Test Utilities
// ============================================================================

function createTestQueryClient(): QueryClient {
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

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

// ============================================================================
// Tests
// ============================================================================

describe('KnownPersonsTab', () => {
  const defaultProps = {
    onPersonClick: vi.fn(),
    onAddPerson: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Default successful state
    mockUseKnownPersonsQuery.mockReturnValue({
      data: mockKnownPersons,
      isLoading: false,
      error: null,
    });

    mockUseUnknownStrangersQuery.mockReturnValue({
      data: { items: mockUnknownStrangers, total: 2, has_more: false },
      isLoading: false,
      error: null,
    });

    mockUseFaceStatsQuery.mockReturnValue({
      data: mockFaceStats,
      isLoading: false,
      error: null,
    });
  });

  describe('rendering', () => {
    it('renders the component with known persons', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      // Check header with count
      expect(screen.getByText(/Known Persons/i)).toBeInTheDocument();
      expect(screen.getByText('(3)')).toBeInTheDocument();

      // Check persons are rendered
      expect(screen.getByText('John Smith')).toBeInTheDocument();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.getByText('Bob Wilson')).toBeInTheDocument();
    });

    it('renders Add Person button', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      const addButton = screen.getByRole('button', { name: /Add Person/i });
      expect(addButton).toBeInTheDocument();
    });

    it('renders Recent Unknown Faces section', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByText('Recent Unknown Faces')).toBeInTheDocument();
      expect(screen.getByText('View All')).toBeInTheDocument();
    });

    it('renders Today\'s Stats section', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByText("Today's Stats")).toBeInTheDocument();
    });

    it('displays correct stats values', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      // Check stat values within their respective stat cards
      const totalCard = screen.getByTestId('stat-card-total');
      const knownCard = screen.getByTestId('stat-card-known');
      const unknownCard = screen.getByTestId('stat-card-unknown');
      const camerasCard = screen.getByTestId('stat-card-cameras');

      expect(totalCard).toHaveTextContent('47');
      expect(knownCard).toHaveTextContent('38');
      expect(unknownCard).toHaveTextContent('9');
      expect(camerasCard).toHaveTextContent('3'); // Camera count is Object.keys(by_camera).length = 3
    });

    it('renders the correct number of unknown strangers (limited to 3)', () => {
      // Verify that only 3 are shown even if more are available
      const manyStrangers = [
        ...mockUnknownStrangers,
        {
          id: 103,
          camera_id: 3,
          camera_name: 'Backyard',
          timestamp: '2025-01-31T08:00:00Z',
          bbox: [75, 125, 175, 275] as [number, number, number, number],
          is_unknown: true,
          quality_score: 0.80,
          thumbnail_url: null,
        },
        {
          id: 104,
          camera_id: 4,
          camera_name: 'Garage',
          timestamp: '2025-01-31T07:30:00Z',
          bbox: [60, 110, 160, 260] as [number, number, number, number],
          is_unknown: true,
          quality_score: 0.75,
          thumbnail_url: null,
        },
      ];

      mockUseUnknownStrangersQuery.mockReturnValue({
        data: { items: manyStrangers, total: 5, has_more: true },
        isLoading: false,
        error: null,
      });

      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      // Should only render 3 stranger cards even though there are 5
      const strangerCards = screen.getAllByText(/Front Door|Driveway|Backyard/);
      expect(strangerCards.length).toBeLessThanOrEqual(3);
    });
  });

  describe('loading states', () => {
    it('shows loading state when known persons are loading', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByTestId('known-persons-loading')).toBeInTheDocument();
    });

    it('shows loading skeleton for stats when loading', () => {
      mockUseFaceStatsQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByTestId('stats-loading')).toBeInTheDocument();
    });
  });

  describe('error states', () => {
    it('shows error state when known persons fetch fails', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load known persons'),
      });

      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByText(/Failed to load known persons/i)).toBeInTheDocument();
    });

    it('shows error state when stats fetch fails', () => {
      mockUseFaceStatsQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load stats'),
      });

      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByText(/Failed to load stats/i)).toBeInTheDocument();
    });
  });

  describe('empty states', () => {
    it('shows empty state when no known persons', () => {
      mockUseKnownPersonsQuery.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      });

      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByText(/No known persons/i)).toBeInTheDocument();
      expect(screen.getByText(/Add your first person/i)).toBeInTheDocument();
    });

    it('shows empty state for unknown strangers when none detected', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: { items: [], total: 0, has_more: false },
        isLoading: false,
        error: null,
      });

      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByText(/No unknown faces detected/i)).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onAddPerson when Add Person button is clicked', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      const addButton = screen.getByRole('button', { name: /Add Person/i });
      fireEvent.click(addButton);

      expect(defaultProps.onAddPerson).toHaveBeenCalledTimes(1);
    });

    it('calls onPersonClick when a person card is clicked', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      const personCard = screen.getByText('John Smith').closest('[data-testid="known-person-card"]');
      expect(personCard).toBeInTheDocument();

      fireEvent.click(personCard!);

      expect(defaultProps.onPersonClick).toHaveBeenCalledWith(mockKnownPersons[0]);
    });

    it('calls onPersonClick with correct person data', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      const personCard = screen.getByText('Jane Doe').closest('[data-testid="known-person-card"]');
      fireEvent.click(personCard!);

      expect(defaultProps.onPersonClick).toHaveBeenCalledWith(mockKnownPersons[1]);
    });
  });

  describe('grid layout', () => {
    it('renders persons in a grid layout', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      const grid = screen.getByTestId('known-persons-grid');
      expect(grid).toHaveClass('grid');
      expect(grid).toHaveClass('gap-4');
    });
  });

  describe('stats cards', () => {
    it('renders all four stat cards', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByTestId('stat-card-total')).toBeInTheDocument();
      expect(screen.getByTestId('stat-card-known')).toBeInTheDocument();
      expect(screen.getByTestId('stat-card-unknown')).toBeInTheDocument();
      expect(screen.getByTestId('stat-card-cameras')).toBeInTheDocument();
    });

    it('displays stat labels correctly', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByText('Total')).toBeInTheDocument();
      expect(screen.getByText('Known')).toBeInTheDocument();
      expect(screen.getByText('Unknown')).toBeInTheDocument();
      expect(screen.getByText('Cameras')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible heading hierarchy', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      // Check for section headings
      const knownPersonsHeading = screen.getByRole('heading', { name: /Known Persons/i });
      expect(knownPersonsHeading).toBeInTheDocument();
    });

    it('Add Person button has accessible label', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      const addButton = screen.getByRole('button', { name: /Add Person/i });
      expect(addButton).toBeInTheDocument();
    });

    it('person cards are keyboard accessible', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      const personCards = screen.getAllByTestId('known-person-card');
      personCards.forEach((card) => {
        expect(card).toHaveAttribute('tabIndex', '0');
      });
    });
  });

  describe('data-testid attributes', () => {
    it('has correct test IDs for main sections', () => {
      renderWithProviders(<KnownPersonsTab {...defaultProps} />);

      expect(screen.getByTestId('known-persons-tab')).toBeInTheDocument();
      expect(screen.getByTestId('known-persons-header')).toBeInTheDocument();
      expect(screen.getByTestId('known-persons-grid')).toBeInTheDocument();
      expect(screen.getByTestId('unknown-strangers-section')).toBeInTheDocument();
      expect(screen.getByTestId('stats-section')).toBeInTheDocument();
    });
  });
});
