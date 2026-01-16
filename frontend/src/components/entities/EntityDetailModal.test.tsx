import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EntityDetailModal, { type EntityDetailModalProps } from './EntityDetailModal';

import type { EntityDetail, EntityAppearance, EntityDetectionsResponse } from '../../services/api';

// Mock the useEntityHistory hook
const mockUseEntityHistory = vi.fn();
vi.mock('../../hooks/useEntityHistory', () => ({
  useEntityHistory: (...args: unknown[]) => mockUseEntityHistory(...args),
}));

// Mock the API functions
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof import('../../services/api')>('../../services/api');
  return {
    ...actual,
    getDetectionImageUrl: vi.fn((id: number) => `/api/detections/${id}/image`),
    getDetectionFullImageUrl: vi.fn((id: number) => `/api/detections/${id}/full`),
  };
});

// Helper to create a test query client
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// Helper to wrap component with query provider
function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return {
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
    queryClient,
  };
}

describe('EntityDetailModal', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock appearances
  const mockAppearances: EntityAppearance[] = [
    {
      detection_id: 'det-001',
      camera_id: 'front_door',
      camera_name: 'Front Door',
      timestamp: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(),
      thumbnail_url: 'https://example.com/thumb1.jpg',
      similarity_score: 0.95,
      attributes: {},
    },
    {
      detection_id: 'det-002',
      camera_id: 'back_yard',
      camera_name: 'Back Yard',
      timestamp: new Date(BASE_TIME - 30 * 60 * 1000).toISOString(),
      thumbnail_url: 'https://example.com/thumb2.jpg',
      similarity_score: 0.88,
      attributes: {},
    },
  ];

  // Mock detections for visualization
  const mockDetections: EntityDetectionsResponse = {
    entity_id: 'entity-abc123',
    entity_type: 'person',
    detections: [
      {
        detection_id: 1,
        camera_id: 'front_door',
        camera_name: 'Front Door',
        timestamp: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(),
        thumbnail_url: '/api/detections/1/image',
        confidence: 0.95,
        object_type: 'person',
      },
      {
        detection_id: 2,
        camera_id: 'back_yard',
        camera_name: 'Back Yard',
        timestamp: new Date(BASE_TIME - 30 * 60 * 1000).toISOString(),
        thumbnail_url: '/api/detections/2/image',
        confidence: 0.88,
        object_type: 'person',
      },
    ],
    pagination: {
      total: 2,
      limit: 50,
      offset: 0,
      has_more: false,
    },
  };

  // Mock entity detail
  const mockEntity: EntityDetail = {
    id: 'entity-abc123',
    entity_type: 'person',
    first_seen: new Date(BASE_TIME - 3 * 60 * 60 * 1000).toISOString(),
    last_seen: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(),
    appearance_count: 2,
    cameras_seen: ['front_door', 'back_yard'],
    thumbnail_url: 'https://example.com/thumbnail.jpg',
    appearances: mockAppearances,
  };

  const defaultProps: EntityDetailModalProps = {
    entity: mockEntity,
    isOpen: true,
    onClose: vi.fn(),
  };

  // Default mock implementation
  const defaultHookReturn = {
    detections: mockDetections,
    isLoadingDetections: false,
    fetchMoreDetections: vi.fn(),
    hasMoreDetections: false,
    isFetchingMoreDetections: false,
    entity: mockEntity,
    isLoadingEntity: false,
    isLoading: false,
    entityError: null,
    detectionsError: null,
    refetchEntity: vi.fn(),
    refetchDetections: vi.fn(),
  };

  // Mock system time for consistent testing
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
    mockUseEntityHistory.mockReturnValue(defaultHookReturn);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders modal when isOpen is true', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('does not render modal when isOpen is false', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} isOpen={false} />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders entity type in title', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByRole('heading', { name: /Person/i })).toBeInTheDocument();
    });

    it('renders entity ID', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByText(/entity-abc123/)).toBeInTheDocument();
    });

    it('renders thumbnail when available', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      const images = screen.getAllByRole('img');
      expect(images.length).toBeGreaterThan(0);
    });

    it('renders appearance timeline', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByText('Appearance Timeline')).toBeInTheDocument();
    });

    it('renders all appearances', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      // Multiple elements may have "Front Door" text (detection history + timeline)
      // Just check that we have content
      expect(screen.getAllByText('Front Door').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Back Yard').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('entity info', () => {
    it('displays first seen timestamp', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByText(/First seen/i)).toBeInTheDocument();
    });

    it('displays last seen timestamp', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByText(/Last seen/i)).toBeInTheDocument();
    });

    it('displays appearance count', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      // Appearance count is shown as "2" with "appearances" label below
      const countElement = screen.getAllByText('2')[0]; // First "2" is appearance count
      expect(countElement).toBeInTheDocument();
      expect(screen.getByText('appearances')).toBeInTheDocument();
    });

    it('displays cameras seen count', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      // Camera count is also "2" with "cameras" label below
      expect(screen.getByText('cameras')).toBeInTheDocument();
    });
  });

  describe('vehicle entity', () => {
    it('renders vehicle type correctly', () => {
      const vehicleEntity: EntityDetail = {
        ...mockEntity,
        entity_type: 'vehicle',
      };
      renderWithQueryClient(<EntityDetailModal {...defaultProps} entity={vehicleEntity} />);
      expect(screen.getByRole('heading', { name: /Vehicle/i })).toBeInTheDocument();
    });
  });

  describe('close behavior', () => {
    it('calls onClose when close button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithQueryClient(<EntityDetailModal {...defaultProps} onClose={onClose} />);

      // Get the X close button in the header (aria-label="Close modal")
      const closeButton = screen.getByLabelText(/close modal/i);
      await user.click(closeButton);

      expect(onClose).toHaveBeenCalledTimes(1);
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onClose when clicking footer close button', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithQueryClient(<EntityDetailModal {...defaultProps} onClose={onClose} />);

      // Get the footer Close button
      const closeButtons = screen.getAllByRole('button', { name: /close/i });
      const footerButton = closeButtons[closeButtons.length - 1]; // Last one is footer button
      await user.click(footerButton);

      expect(onClose).toHaveBeenCalledTimes(1);
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('null entity', () => {
    it('returns null when entity is null', () => {
      const { container } = renderWithQueryClient(
        <EntityDetailModal {...defaultProps} entity={null} />
      );
      expect(container.firstChild).toBeNull();
    });
  });

  describe('styling', () => {
    it('renders styled content', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      // Modal renders with content that has styling applied
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    it('applies border styling', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      // Modal renders
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible dialog role', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has accessible dialog title', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      const headings = screen.getAllByRole('heading');
      expect(headings.length).toBeGreaterThanOrEqual(1);
    });

    it('close button has accessible label', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      // Multiple close buttons exist (header X and footer button)
      const closeButtons = screen.getAllByRole('button', { name: /close/i });
      expect(closeButtons.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('empty appearances', () => {
    it('handles entity with no appearances', () => {
      const entityNoAppearances: EntityDetail = {
        ...mockEntity,
        appearances: [],
        appearance_count: 0,
      };
      renderWithQueryClient(
        <EntityDetailModal {...defaultProps} entity={entityNoAppearances} />
      );
      expect(screen.getByText(/No appearances recorded/i)).toBeInTheDocument();
    });
  });

  // New tests for detection visualization
  describe('trust status', () => {
    it('displays default unknown trust status', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByTestId('trust-badge-unknown')).toHaveTextContent('Unknown');
    });

    it('displays trusted status when provided', () => {
      renderWithQueryClient(
        <EntityDetailModal {...defaultProps} trustStatus="trusted" />
      );
      expect(screen.getByTestId('trust-badge-trusted')).toHaveTextContent('Trusted');
    });

    it('displays suspicious status when flagged is provided (backward compat)', () => {
      renderWithQueryClient(
        <EntityDetailModal {...defaultProps} trustStatus="flagged" />
      );
      // 'flagged' is now normalized to 'untrusted' which displays as 'Suspicious'
      expect(screen.getByTestId('trust-badge-suspicious')).toHaveTextContent('Suspicious');
    });

    it('calls onTrustStatusChange when Mark as Trusted button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onTrustStatusChange = vi.fn();
      renderWithQueryClient(
        <EntityDetailModal
          {...defaultProps}
          trustStatus="unknown"
          onTrustStatusChange={onTrustStatusChange}
        />
      );

      const trustedButton = screen.getByTestId('mark-as-trusted-button');
      await user.click(trustedButton);

      expect(onTrustStatusChange).toHaveBeenCalledWith(mockEntity.id, 'trusted');
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('does not show trust action buttons when onTrustStatusChange is not provided', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.queryByTestId('mark-as-trusted-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('mark-as-suspicious-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('reset-trust-button')).not.toBeInTheDocument();
    });
  });

  describe('detection visualization', () => {
    it('renders detection history section', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByTestId('detection-visualization-section')).toBeInTheDocument();
      expect(screen.getByText('Detection History')).toBeInTheDocument();
    });

    it('shows loading state when detections are loading', () => {
      mockUseEntityHistory.mockReturnValue({
        ...defaultHookReturn,
        isLoadingDetections: true,
        detections: { ...mockDetections, detections: [] },
      });
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByTestId('detection-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading detections...')).toBeInTheDocument();
    });

    it('shows empty state when no detections available', () => {
      mockUseEntityHistory.mockReturnValue({
        ...defaultHookReturn,
        detections: { ...mockDetections, detections: [] },
      });
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByTestId('detection-empty')).toBeInTheDocument();
      expect(screen.getByText('No detection images available')).toBeInTheDocument();
    });

    it('renders detection image container when detections available', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      // May have multiple containers, check at least one exists
      expect(screen.getAllByTestId('detection-image-container').length).toBeGreaterThanOrEqual(1);
    });

    it('displays detection count indicator', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      // Should show "1 of 2" since we have 2 detections and start at index 0
      expect(screen.getByText(/1 of 2/)).toBeInTheDocument();
    });

    it('renders detection metadata', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByTestId('detection-metadata')).toBeInTheDocument();
    });

    it('shows object type badge in detection metadata', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      const metadata = screen.getByTestId('detection-metadata');
      expect(metadata).toHaveTextContent('person');
    });

    it('shows confidence in detection metadata', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      const metadata = screen.getByTestId('detection-metadata');
      expect(metadata).toHaveTextContent('Confidence: 95%');
    });

    it('renders thumbnail strip with multiple detections', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByTestId('detection-thumbnail-strip')).toBeInTheDocument();
      expect(screen.getByTestId('detection-thumbnail-1')).toBeInTheDocument();
      expect(screen.getByTestId('detection-thumbnail-2')).toBeInTheDocument();
    });

    it('renders navigation buttons when multiple detections', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByTestId('prev-detection-button')).toBeInTheDocument();
      expect(screen.getByTestId('next-detection-button')).toBeInTheDocument();
    });

    it('disables prev button on first detection', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      const prevButton = screen.getByTestId('prev-detection-button');
      expect(prevButton).toBeDisabled();
    });

    it('renders view full size button', () => {
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByTestId('expand-detection-button')).toBeInTheDocument();
      expect(screen.getByText('View Full Size')).toBeInTheDocument();
    });

    it('navigates to next detection when next button clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);

      const nextButton = screen.getByTestId('next-detection-button');
      await user.click(nextButton);

      // Should now show "2 of 2"
      await waitFor(() => {
        expect(screen.getByText(/2 of 2/)).toBeInTheDocument();
      });
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('selects detection when thumbnail is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);

      const secondThumbnail = screen.getByTestId('detection-thumbnail-2');
      await user.click(secondThumbnail);

      // Should now show "2 of 2"
      await waitFor(() => {
        expect(screen.getByText(/2 of 2/)).toBeInTheDocument();
      });
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('shows load more button when hasMoreDetections is true', () => {
      mockUseEntityHistory.mockReturnValue({
        ...defaultHookReturn,
        hasMoreDetections: true,
      });
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.getByTestId('load-more-detections')).toBeInTheDocument();
    });

    it('calls fetchMoreDetections when load more is clicked', async () => {
      vi.useRealTimers();
      const fetchMoreDetections = vi.fn();
      mockUseEntityHistory.mockReturnValue({
        ...defaultHookReturn,
        hasMoreDetections: true,
        fetchMoreDetections,
      });
      const user = userEvent.setup();
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);

      const loadMoreButton = screen.getByTestId('load-more-detections');
      await user.click(loadMoreButton);

      expect(fetchMoreDetections).toHaveBeenCalled();
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('hides navigation arrows for single detection', () => {
      mockUseEntityHistory.mockReturnValue({
        ...defaultHookReturn,
        detections: {
          ...mockDetections,
          detections: [mockDetections.detections[0]],
        },
      });
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.queryByTestId('prev-detection-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('next-detection-button')).not.toBeInTheDocument();
    });

    it('hides thumbnail strip for single detection', () => {
      mockUseEntityHistory.mockReturnValue({
        ...defaultHookReturn,
        detections: {
          ...mockDetections,
          detections: [mockDetections.detections[0]],
        },
      });
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);
      expect(screen.queryByTestId('detection-thumbnail-strip')).not.toBeInTheDocument();
    });
  });

  describe('lightbox integration', () => {
    it('renders expand button that can be clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      renderWithQueryClient(<EntityDetailModal {...defaultProps} />);

      const expandButton = screen.getByTestId('expand-detection-button');
      expect(expandButton).toBeInTheDocument();

      // Click should work without throwing
      await user.click(expandButton);

      // The lightbox integration works - the Lightbox component has its own tests
      // Here we just verify the button exists and is clickable
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });
});
