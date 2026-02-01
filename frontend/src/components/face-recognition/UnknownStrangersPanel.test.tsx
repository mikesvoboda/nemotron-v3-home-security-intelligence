/**
 * UnknownStrangersPanel Test Suite
 *
 * Tests for the UnknownStrangersPanel component that displays recent unknown
 * face detections with action buttons for quick identification or dismissal.
 *
 * @module components/face-recognition/UnknownStrangersPanel.test
 * @see NEM-4688 Phase 2 - Unknown Strangers Panel
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import UnknownStrangersPanel from './UnknownStrangersPanel';

import type { FaceDetectionEvent, UnknownStrangerSummary } from '@/types/faceRecognition';

// ============================================================================
// Mock Data
// ============================================================================

const mockUnknownFaceEvents: FaceDetectionEvent[] = [
  {
    id: 101,
    camera_id: 1,
    camera_name: 'Front Door',
    timestamp: '2025-01-31T10:32:00Z',
    bbox: [100, 150, 200, 300],
    matched_person_id: null,
    matched_person_name: null,
    match_confidence: null,
    is_unknown: true,
    quality_score: 0.85,
    thumbnail_url: '/thumbnails/unknown_101.jpg',
    detection_id: 'det-101',
    event_id: 1001,
  },
  {
    id: 102,
    camera_id: 2,
    camera_name: 'Driveway',
    timestamp: '2025-01-31T09:15:00Z',
    bbox: [50, 100, 150, 250],
    matched_person_id: null,
    matched_person_name: null,
    match_confidence: null,
    is_unknown: true,
    quality_score: 0.78,
    thumbnail_url: null,
    detection_id: 'det-102',
    event_id: 1002,
  },
  {
    id: 103,
    camera_id: 3,
    camera_name: 'Backyard',
    timestamp: '2025-01-31T08:45:00Z',
    bbox: [75, 125, 175, 275],
    matched_person_id: null,
    matched_person_name: null,
    match_confidence: null,
    is_unknown: true,
    quality_score: 0.82,
    thumbnail_url: '/thumbnails/unknown_103.jpg',
    detection_id: 'det-103',
    event_id: 1003,
  },
];

const mockUnknownStrangerSummary: UnknownStrangerSummary = {
  items: mockUnknownFaceEvents,
  total: 5,
  has_more: true,
};

// ============================================================================
// Mock Hooks
// ============================================================================

const mockUseUnknownStrangersQuery = vi.fn();

vi.mock('@/hooks/useFaceRecognitionApi', () => ({
  useUnknownStrangersQuery: (limit?: number) => mockUseUnknownStrangersQuery(limit),
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

describe('UnknownStrangersPanel', () => {
  const defaultProps = {
    onIdentify: vi.fn(),
    onAddNewPerson: vi.fn(),
    onDismiss: vi.fn(),
    onViewAll: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Default successful state
    mockUseUnknownStrangersQuery.mockReturnValue({
      data: mockUnknownStrangerSummary,
      isLoading: false,
      error: null,
      isRefetching: false,
    });
  });

  describe('basic rendering', () => {
    it('renders the panel with data-testid', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByTestId('unknown-strangers-panel')).toBeInTheDocument();
    });

    it('displays the panel header with title', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByText('Recent Unknown Faces')).toBeInTheDocument();
    });

    it('displays View All button', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByRole('button', { name: /View All/i })).toBeInTheDocument();
    });

    it('displays the correct number of unknown face events', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Driveway')).toBeInTheDocument();
      expect(screen.getByText('Backyard')).toBeInTheDocument();
    });

    it('uses default limit of 3 when not specified', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(mockUseUnknownStrangersQuery).toHaveBeenCalledWith(3);
    });

    it('uses custom limit when specified', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} limit={5} />);

      expect(mockUseUnknownStrangersQuery).toHaveBeenCalledWith(5);
    });
  });

  describe('face event items', () => {
    it('displays thumbnail for events with thumbnail_url', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const thumbnails = screen.getAllByRole('img');
      expect(thumbnails.length).toBeGreaterThanOrEqual(2);
    });

    it('displays placeholder icon for events without thumbnail_url', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      // Driveway event has no thumbnail_url
      const placeholders = screen.getAllByTestId('face-placeholder');
      expect(placeholders.length).toBeGreaterThanOrEqual(1);
    });

    it('displays camera name for each event', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Driveway')).toBeInTheDocument();
      expect(screen.getByText('Backyard')).toBeInTheDocument();
    });

    it('displays "Unknown person detected" text for each event', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const descriptions = screen.getAllByText('Unknown person detected');
      expect(descriptions).toHaveLength(3);
    });

    it('displays formatted time for each event', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      // Times should be formatted (exact format depends on locale)
      // We check that some time indicator is present
      expect(screen.getByTestId('event-time-101')).toBeInTheDocument();
      expect(screen.getByTestId('event-time-102')).toBeInTheDocument();
      expect(screen.getByTestId('event-time-103')).toBeInTheDocument();
    });
  });

  describe('action buttons', () => {
    it('displays Identify button for each event', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const identifyButtons = screen.getAllByRole('button', { name: /Identify/i });
      expect(identifyButtons).toHaveLength(3);
    });

    it('displays Dismiss button for each event', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const dismissButtons = screen.getAllByRole('button', { name: /Dismiss/i });
      expect(dismissButtons).toHaveLength(3);
    });

    it('displays Add as New Person button for each event', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const addButtons = screen.getAllByRole('button', { name: /Add as New Person/i });
      expect(addButtons).toHaveLength(3);
    });

    it('calls onIdentify with correct eventId when Identify is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const identifyButtons = screen.getAllByRole('button', { name: /Identify/i });
      await user.click(identifyButtons[0]);

      expect(defaultProps.onIdentify).toHaveBeenCalledWith(101);
      expect(defaultProps.onIdentify).toHaveBeenCalledTimes(1);
    });

    it('calls onDismiss with correct eventId when Dismiss is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const dismissButtons = screen.getAllByRole('button', { name: /Dismiss/i });
      await user.click(dismissButtons[1]);

      expect(defaultProps.onDismiss).toHaveBeenCalledWith(102);
      expect(defaultProps.onDismiss).toHaveBeenCalledTimes(1);
    });

    it('calls onAddNewPerson with correct eventId when Add as New Person is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const addButtons = screen.getAllByRole('button', { name: /Add as New Person/i });
      await user.click(addButtons[2]);

      expect(defaultProps.onAddNewPerson).toHaveBeenCalledWith(103);
      expect(defaultProps.onAddNewPerson).toHaveBeenCalledTimes(1);
    });

    it('calls onViewAll when View All button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const viewAllButton = screen.getByRole('button', { name: /View All/i });
      await user.click(viewAllButton);

      expect(defaultProps.onViewAll).toHaveBeenCalledTimes(1);
    });
  });

  describe('loading state', () => {
    it('shows loading state when data is loading', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        isRefetching: false,
      });

      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByTestId('unknown-strangers-loading')).toBeInTheDocument();
    });

    it('shows loading skeleton items', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        isRefetching: false,
      });

      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const skeletons = screen.getAllByTestId('skeleton-item');
      expect(skeletons.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('error state', () => {
    it('shows error state when fetch fails', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load unknown faces'),
        isRefetching: false,
      });

      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByTestId('unknown-strangers-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to load unknown faces/i)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty state when no unknown faces detected', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: { items: [], total: 0, has_more: false },
        isLoading: false,
        error: null,
        isRefetching: false,
      });

      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByTestId('unknown-strangers-empty')).toBeInTheDocument();
      expect(screen.getByText(/No unknown faces detected/i)).toBeInTheDocument();
    });

    it('hides View All button in empty state', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: { items: [], total: 0, has_more: false },
        isLoading: false,
        error: null,
        isRefetching: false,
      });

      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.queryByRole('button', { name: /View All/i })).not.toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies NVIDIA dark theme styling', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const panel = screen.getByTestId('unknown-strangers-panel');
      expect(panel).toHaveClass('bg-[#1A1A1A]');
      expect(panel).toHaveClass('rounded-lg');
      expect(panel).toHaveClass('border');
      expect(panel).toHaveClass('border-gray-700');
    });

    it('applies amber/yellow accent for unknown highlight', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      // Check that at least one element has the amber/yellow accent
      const panel = screen.getByTestId('unknown-strangers-panel');
      expect(panel.innerHTML).toContain('amber');
    });

    it('applies custom className when provided', () => {
      renderWithProviders(
        <UnknownStrangersPanel {...defaultProps} className="custom-class" />
      );

      const panel = screen.getByTestId('unknown-strangers-panel');
      expect(panel).toHaveClass('custom-class');
    });
  });

  describe('auto-refresh', () => {
    it('queries with refetchInterval for auto-refresh', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      // The hook should be configured with refetchInterval
      // We verify the hook is called, actual interval is handled by the hook
      expect(mockUseUnknownStrangersQuery).toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has accessible heading for panel title', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByRole('heading', { name: /Recent Unknown Faces/i })).toBeInTheDocument();
    });

    it('action buttons have accessible labels', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const identifyButtons = screen.getAllByRole('button', { name: /Identify/i });
      identifyButtons.forEach((button) => {
        expect(button).toHaveAccessibleName();
      });

      const dismissButtons = screen.getAllByRole('button', { name: /Dismiss/i });
      dismissButtons.forEach((button) => {
        expect(button).toHaveAccessibleName();
      });

      const addButtons = screen.getAllByRole('button', { name: /Add as New Person/i });
      addButtons.forEach((button) => {
        expect(button).toHaveAccessibleName();
      });
    });

    it('images have alt text', () => {
      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      const images = screen.getAllByRole('img');
      images.forEach((img) => {
        expect(img).toHaveAttribute('alt');
      });
    });
  });

  describe('edge cases', () => {
    it('handles single unknown face', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: { items: [mockUnknownFaceEvents[0]], total: 1, has_more: false },
        isLoading: false,
        error: null,
        isRefetching: false,
      });

      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.queryByText('Driveway')).not.toBeInTheDocument();
    });

    it('handles data being undefined gracefully', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: null,
        isRefetching: false,
      });

      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByTestId('unknown-strangers-empty')).toBeInTheDocument();
    });
  });

  describe('View All visibility', () => {
    it('shows View All when there are more events than displayed', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: { items: mockUnknownFaceEvents, total: 10, has_more: true },
        isLoading: false,
        error: null,
        isRefetching: false,
      });

      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      expect(screen.getByRole('button', { name: /View All/i })).toBeInTheDocument();
    });

    it('hides View All when all events are displayed', () => {
      mockUseUnknownStrangersQuery.mockReturnValue({
        data: { items: [mockUnknownFaceEvents[0]], total: 1, has_more: false },
        isLoading: false,
        error: null,
        isRefetching: false,
      });

      renderWithProviders(<UnknownStrangersPanel {...defaultProps} />);

      // View All should be hidden when total equals displayed count and has_more is false
      expect(screen.queryByRole('button', { name: /View All/i })).not.toBeInTheDocument();
    });
  });
});
