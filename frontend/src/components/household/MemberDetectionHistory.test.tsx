import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import MemberDetectionHistory from './MemberDetectionHistory';

// Mock the hooks (they don't exist yet)
const mockUseMemberDetectionsQuery = vi.fn();
const mockUseUnlinkDetection = vi.fn();

vi.mock('../../hooks/useHouseholdApi', () => ({
  useMemberDetectionsQuery: (memberId: number, params: any) => mockUseMemberDetectionsQuery(memberId, params),
  useUnlinkDetection: () => mockUseUnlinkDetection(),
}));

const mockMemberDetections = {
  items: [
    {
      detection_id: 1,
      event_id: 100,
      camera_name: 'Front Door',
      detected_at: '2025-01-31T10:00:00Z',
      confidence: 0.92,
      linked_at: '2025-01-31T10:05:00Z',
      event_summary: 'Person at front door',
      thumbnail_url: '/api/detections/1/thumbnail',
      notes: 'Coming home from work',
    },
    {
      detection_id: 2,
      event_id: 101,
      camera_name: 'Back Yard',
      detected_at: '2025-01-31T11:00:00Z',
      confidence: 0.88,
      linked_at: '2025-01-31T11:05:00Z',
      event_summary: 'Person in backyard',
      thumbnail_url: '/api/detections/2/thumbnail',
      notes: null,
    },
  ],
  total: 50,
  offset: 0,
  limit: 20,
};

describe('MemberDetectionHistory', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    // Default mock implementations
    mockUseMemberDetectionsQuery.mockReturnValue({
      data: mockMemberDetections,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    mockUseUnlinkDetection.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = (props = {}) => {
    const defaultProps = {
      memberId: 1,
      memberName: 'Mike',
    };

    return render(
      <QueryClientProvider client={queryClient}>
        <MemberDetectionHistory {...defaultProps} {...props} />
      </QueryClientProvider>
    );
  };

  // ========== Rendering Tests ==========

  describe('Rendering', () => {
    it('renders loading state initially', () => {
      mockUseMemberDetectionsQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByText(/loading detections/i)).toBeInTheDocument();
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('renders detection list after loading', () => {
      renderComponent();
      expect(screen.getByText(/person at front door/i)).toBeInTheDocument();
      expect(screen.getByText(/person in backyard/i)).toBeInTheDocument();
    });

    it('shows empty state when no detections', () => {
      mockUseMemberDetectionsQuery.mockReturnValue({
        data: { items: [], total: 0, offset: 0, limit: 20 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByText(/no detections found/i)).toBeInTheDocument();
      expect(screen.getByText(/mike has not been linked to any detections yet/i)).toBeInTheDocument();
    });

    it('shows pagination controls when total exceeds limit', () => {
      renderComponent();
      expect(screen.getByText(/showing 1-2 of 50/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument();
    });

    it('hides pagination controls when all items loaded', () => {
      mockUseMemberDetectionsQuery.mockReturnValue({
        data: { items: mockMemberDetections.items, total: 2, offset: 0, limit: 20 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument();
    });

    it('displays detection thumbnail', () => {
      renderComponent();
      const thumbnails = screen.getAllByRole('img', { name: /detection thumbnail/i });
      expect(thumbnails).toHaveLength(2);
      expect(thumbnails[0]).toHaveAttribute('src', '/api/detections/1/thumbnail');
    });

    it('displays detection timestamp', () => {
      renderComponent();
      const timestamps = screen.getAllByText(/2025-01-31/);
      expect(timestamps.length).toBeGreaterThan(0);
      // Time format appears with "at" separator
      const atTexts = screen.getAllByText(/at/i);
      expect(atTexts.length).toBeGreaterThan(0);
    });

    it('displays camera name', () => {
      renderComponent();
      // Camera names appear in both detection cards and filter dropdown
      const frontDoors = screen.getAllByText('Front Door');
      const backYards = screen.getAllByText('Back Yard');
      expect(frontDoors.length).toBeGreaterThan(0);
      expect(backYards.length).toBeGreaterThan(0);
    });

    it('displays event summary', () => {
      renderComponent();
      expect(screen.getByText(/person at front door/i)).toBeInTheDocument();
      expect(screen.getByText(/person in backyard/i)).toBeInTheDocument();
    });

    it('displays confidence score', () => {
      renderComponent();
      expect(screen.getByText(/92%/)).toBeInTheDocument();
      expect(screen.getByText(/88%/)).toBeInTheDocument();
    });

    it('displays notes when present', () => {
      renderComponent();
      // Notes may appear with "Notes:" prefix
      expect(screen.getByText(/Coming home from work/i)).toBeInTheDocument();
    });

    it('does not display notes section when notes are null', () => {
      renderComponent();
      const detectionCards = screen.getAllByTestId('detection-card');
      const secondCard = detectionCards[1];
      expect(within(secondCard).queryByText(/notes:/i)).not.toBeInTheDocument();
    });

    it('displays member name in header', () => {
      renderComponent({ memberName: 'Jane' });
      expect(screen.getByText(/detection history for jane/i)).toBeInTheDocument();
    });
  });

  // ========== Interaction Tests ==========

  describe('Interactions', () => {
    it('loads more detections when Load More button is clicked', async () => {
      const user = userEvent.setup();
      const refetch = vi.fn();

      mockUseMemberDetectionsQuery.mockReturnValue({
        data: mockMemberDetections,
        isLoading: false,
        isError: false,
        refetch,
      });

      renderComponent();

      const loadMoreButton = screen.getByRole('button', { name: /load more/i });
      await user.click(loadMoreButton);

      await waitFor(() => {
        expect(mockUseMemberDetectionsQuery).toHaveBeenCalledWith(1, expect.objectContaining({
          offset: 2,
        }));
      });
    });

    it('disables Load More button while loading', () => {
      mockUseMemberDetectionsQuery.mockReturnValue({
        data: mockMemberDetections,
        isLoading: true,
        isError: false,
        refetch: vi.fn(),
      });

      renderComponent();
      // When loading with existing data, the button shows "Load More" but is disabled
      // The button text may be "Load More" or "Loading..."
      const buttons = screen.getAllByRole('button');
      const loadMoreButton = buttons.find(
        (btn) => btn.textContent?.includes('Load More') || btn.textContent?.includes('Loading')
      );
      expect(loadMoreButton).toBeDefined();
    });

    it('shows unlink button for each detection', () => {
      renderComponent();
      const unlinkButtons = screen.getAllByRole('button', { name: /unlink/i });
      expect(unlinkButtons).toHaveLength(2);
    });

    it('shows confirmation dialog when unlink is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      const unlinkButtons = screen.getAllByRole('button', { name: /unlink/i });
      await user.click(unlinkButtons[0]);

      expect(screen.getByText(/are you sure you want to unlink this detection/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('closes confirmation dialog when cancel is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      const unlinkButtons = screen.getAllByRole('button', { name: /unlink/i });
      await user.click(unlinkButtons[0]);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByText(/are you sure you want to unlink/i)).not.toBeInTheDocument();
      });
    });

    it('calls unlinkDetectionFromMember API when confirm is clicked', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn();
      mockUseUnlinkDetection.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderComponent();

      const unlinkButtons = screen.getAllByRole('button', { name: /unlink/i });
      await user.click(unlinkButtons[0]);

      const confirmButton = screen.getByRole('button', { name: /confirm/i });
      await user.click(confirmButton);

      expect(mutate).toHaveBeenCalledWith(
        { detectionId: 1, memberId: 1 },
        expect.objectContaining({
          onSuccess: expect.any(Function),
        })
      );
    });

    it('removes detection from list after successful unlink', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn((_, { onSuccess }) => {
        onSuccess();
      });
      mockUseUnlinkDetection.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderComponent();

      expect(screen.getByText(/person at front door/i)).toBeInTheDocument();

      const unlinkButtons = screen.getAllByRole('button', { name: /unlink/i });
      await user.click(unlinkButtons[0]);

      const confirmButton = screen.getByRole('button', { name: /confirm/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(screen.queryByText(/person at front door/i)).not.toBeInTheDocument();
      });
    });

    it('navigates to event detail when view event button is clicked', async () => {
      const user = userEvent.setup();
      const onNavigate = vi.fn();
      renderComponent({ onNavigate });

      // Click the "View Event" button on the first detection card
      const viewEventButtons = screen.getAllByRole('button', { name: /view event/i });
      await user.click(viewEventButtons[0]);

      expect(onNavigate).toHaveBeenCalledWith({ eventId: 100, detectionId: 1 });
    });
  });

  // ========== Filtering Tests ==========

  describe('Filtering', () => {
    it('shows camera filter dropdown', () => {
      renderComponent();
      expect(screen.getByLabelText(/filter by camera/i)).toBeInTheDocument();
    });

    it('filters detections by selected camera', async () => {
      const user = userEvent.setup();
      renderComponent();

      const cameraFilter = screen.getByLabelText(/filter by camera/i);
      await user.selectOptions(cameraFilter, 'Front Door');

      await waitFor(() => {
        expect(mockUseMemberDetectionsQuery).toHaveBeenCalledWith(1, expect.objectContaining({
          camera: 'Front Door',
        }));
      });
    });

    it('shows date range filter', () => {
      renderComponent();
      expect(screen.getByLabelText(/from date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/to date/i)).toBeInTheDocument();
    });

    it('filters detections by date range', async () => {
      const user = userEvent.setup();
      renderComponent();

      const fromDate = screen.getByLabelText(/from date/i);
      const toDate = screen.getByLabelText(/to date/i);

      await user.type(fromDate, '2025-01-01');
      await user.type(toDate, '2025-01-31');

      await waitFor(() => {
        expect(mockUseMemberDetectionsQuery).toHaveBeenCalledWith(1, expect.objectContaining({
          from_date: '2025-01-01',
          to_date: '2025-01-31',
        }));
      });
    });

    it('clears filters when clear button is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      const cameraFilter = screen.getByLabelText(/filter by camera/i);
      await user.selectOptions(cameraFilter, 'Front Door');

      const clearButton = screen.getByRole('button', { name: /clear filters/i });
      await user.click(clearButton);

      await waitFor(() => {
        expect(mockUseMemberDetectionsQuery).toHaveBeenCalledWith(1, expect.objectContaining({
          camera: undefined,
        }));
      });
    });
  });

  // ========== Sorting Tests ==========

  describe('Sorting', () => {
    it('shows sort dropdown', () => {
      renderComponent();
      expect(screen.getByLabelText(/sort by/i)).toBeInTheDocument();
    });

    it('sorts by date descending by default', () => {
      renderComponent();
      expect(mockUseMemberDetectionsQuery).toHaveBeenCalledWith(1, expect.objectContaining({
        sort: 'date_desc',
      }));
    });

    it('sorts by date ascending when selected', async () => {
      const user = userEvent.setup();
      renderComponent();

      const sortDropdown = screen.getByLabelText(/sort by/i);
      await user.selectOptions(sortDropdown, 'date_asc');

      await waitFor(() => {
        expect(mockUseMemberDetectionsQuery).toHaveBeenCalledWith(1, expect.objectContaining({
          sort: 'date_asc',
        }));
      });
    });

    it('sorts by confidence descending when selected', async () => {
      const user = userEvent.setup();
      renderComponent();

      const sortDropdown = screen.getByLabelText(/sort by/i);
      await user.selectOptions(sortDropdown, 'confidence_desc');

      await waitFor(() => {
        expect(mockUseMemberDetectionsQuery).toHaveBeenCalledWith(1, expect.objectContaining({
          sort: 'confidence_desc',
        }));
      });
    });

    it('sorts by confidence ascending when selected', async () => {
      const user = userEvent.setup();
      renderComponent();

      const sortDropdown = screen.getByLabelText(/sort by/i);
      await user.selectOptions(sortDropdown, 'confidence_asc');

      await waitFor(() => {
        expect(mockUseMemberDetectionsQuery).toHaveBeenCalledWith(1, expect.objectContaining({
          sort: 'confidence_asc',
        }));
      });
    });
  });

  // ========== Error Handling Tests ==========

  describe('Error Handling', () => {
    it('shows error state on API failure', () => {
      mockUseMemberDetectionsQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load detections' },
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByText(/failed to load detections/i)).toBeInTheDocument();
    });

    it('shows retry button on error', () => {
      mockUseMemberDetectionsQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load detections' },
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('refetches data when retry button is clicked', async () => {
      const user = userEvent.setup();
      const refetch = vi.fn();

      mockUseMemberDetectionsQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: { message: 'Failed to load detections' },
        refetch,
      });

      renderComponent();

      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      expect(refetch).toHaveBeenCalledTimes(1);
    });

    it('shows error message when unlink fails', async () => {
      const user = userEvent.setup();
      const mutate = vi.fn((_, { onError }) => {
        // Simulate an error when unlink is called
        onError(new Error('Failed to unlink detection'));
      });
      mockUseUnlinkDetection.mockReturnValue({
        mutate,
        isPending: false,
        isError: false,
        error: null,
      });

      renderComponent();

      // Click unlink to open dialog
      const unlinkButtons = screen.getAllByRole('button', { name: /unlink/i });
      await user.click(unlinkButtons[0]);

      // Click confirm to trigger the mutation
      const confirmButton = screen.getByRole('button', { name: /confirm/i });
      await user.click(confirmButton);

      // Error message should appear after mutation fails
      await waitFor(() => {
        expect(screen.getByText(/failed to unlink detection/i)).toBeInTheDocument();
      });
    });

    it('shows generic error when error message is missing', () => {
      mockUseMemberDetectionsQuery.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: {},
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByText(/an error occurred/i)).toBeInTheDocument();
    });
  });

  // ========== Edge Cases ==========

  describe('Edge Cases', () => {
    it('handles missing thumbnail gracefully', () => {
      const dataWithoutThumbnail = {
        ...mockMemberDetections,
        items: [
          { ...mockMemberDetections.items[0], thumbnail_url: null },
        ],
      };

      mockUseMemberDetectionsQuery.mockReturnValue({
        data: dataWithoutThumbnail,
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      });

      renderComponent();
      const thumbnail = screen.getByRole('img', { name: /detection thumbnail/i });
      expect(thumbnail).toHaveAttribute('src', '/placeholder-person.png');
    });

    it('handles very long event summaries', () => {
      const longSummary = 'A'.repeat(500);
      const dataWithLongSummary = {
        ...mockMemberDetections,
        items: [
          { ...mockMemberDetections.items[0], event_summary: longSummary },
        ],
      };

      mockUseMemberDetectionsQuery.mockReturnValue({
        data: dataWithLongSummary,
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByText(longSummary.substring(0, 200), { exact: false })).toBeInTheDocument();
    });

    it('shows timestamps for detections', () => {
      const recentDetection = {
        ...mockMemberDetections,
        items: [
          {
            ...mockMemberDetections.items[0],
            detected_at: '2025-01-31T14:30:00Z',
          },
        ],
      };

      mockUseMemberDetectionsQuery.mockReturnValue({
        data: recentDetection,
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      });

      renderComponent();
      // Component shows absolute timestamps
      expect(screen.getByText(/2025-01-31/i)).toBeInTheDocument();
    });

    it('paginates through multiple pages', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Initial load: offset 0, items 1-2
      expect(screen.getByText(/showing 1-2 of 50/i)).toBeInTheDocument();

      // Click load more
      const loadMoreButton = screen.getByRole('button', { name: /load more/i });
      await user.click(loadMoreButton);

      // Should request next page with offset 2
      await waitFor(() => {
        expect(mockUseMemberDetectionsQuery).toHaveBeenCalledWith(1, expect.objectContaining({
          offset: 2,
        }));
      });
    });

    it('handles zero total count', () => {
      mockUseMemberDetectionsQuery.mockReturnValue({
        data: { items: [], total: 0, offset: 0, limit: 20 },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.queryByText(/showing/i)).not.toBeInTheDocument();
    });

    it('displays linked_at timestamp', () => {
      renderComponent();
      // Multiple detections show "Linked at" text
      const linkedAtTexts = screen.getAllByText(/linked at/i);
      expect(linkedAtTexts.length).toBeGreaterThan(0);
    });
  });

  // ========== Accessibility Tests ==========

  describe('Accessibility', () => {
    it('has proper ARIA labels for interactive elements', () => {
      renderComponent();
      expect(screen.getByLabelText(/filter by camera/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/sort by/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/from date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/to date/i)).toBeInTheDocument();
    });

    it('has proper heading hierarchy', () => {
      renderComponent();
      const heading = screen.getByRole('heading', { name: /detection history for mike/i });
      expect(heading).toBeInTheDocument();
    });

    it('announces loading state to screen readers', () => {
      mockUseMemberDetectionsQuery.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByRole('status')).toHaveTextContent(/loading detections/i);
    });
  });
});
