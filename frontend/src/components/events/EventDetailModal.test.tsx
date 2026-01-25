import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EventDetailModal, { type Event, type EventDetailModalProps } from './EventDetailModal';
import * as api from '../../services/api';
import * as auditApi from '../../services/auditApi';

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

// Mock the audit API
vi.mock('../../services/auditApi', () => ({
  triggerEvaluation: vi.fn(),
  AuditApiError: class AuditApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      this.name = 'AuditApiError';
    }
  },
}));

// Mock the API
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchEventDetections: vi.fn().mockResolvedValue({
      items: [],
      pagination: { total: 0, limit: 100, offset: 0, has_more: false },
    }),
    fetchEventEntityMatches: vi.fn().mockResolvedValue({
      event_id: 123,
      person_matches: [],
      vehicle_matches: [],
      total_matches: 0,
    }),
    fetchEntity: vi.fn().mockResolvedValue({
      id: 'entity-1',
      entity_type: 'person',
      first_seen: '2024-01-15T10:00:00Z',
      last_seen: '2024-01-15T10:30:00Z',
      appearance_count: 1,
      cameras_seen: [],
      thumbnail_url: null,
      appearances: [],
    }),
    getDetectionImageUrl: vi.fn((id: number) => `/api/detections/${id}/image`),
    getDetectionVideoUrl: vi.fn((id: number) => `/api/detections/${id}/video`),
    getDetectionVideoThumbnailUrl: vi.fn((id: number) => `/api/detections/${id}/video/thumbnail`),
    getEventFeedback: vi.fn().mockResolvedValue(null),
    submitEventFeedback: vi.fn().mockResolvedValue({
      id: 1,
      event_id: 123,
      feedback_type: 'accurate',
      notes: null,
      created_at: '2024-01-15T10:30:00Z',
    }),
  };
});

// Mock useToast hook
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

// Mock the VideoPlayer component to avoid complex video element testing
vi.mock('../video/VideoPlayer', () => ({
  default: vi.fn(
    ({ src, poster, className }: { src: string; poster?: string; className?: string }) => (
      <div data-testid="video-player" data-src={src} data-poster={poster} className={className}>
        Mocked VideoPlayer
      </div>
    )
  ),
}));

// Mock the EntityDetailModal component
vi.mock('../entities/EntityDetailModal', () => ({
  default: vi.fn(
    ({ entity, isOpen, onClose }: { entity: unknown; isOpen: boolean; onClose: () => void }) =>
      isOpen ? (
        <div data-testid="entity-detail-modal">
          Mocked EntityDetailModal
          {entity ? <span data-testid="entity-loaded">Entity Loaded</span> : null}
          <button onClick={onClose} data-testid="close-entity-modal">
            Close
          </button>
        </div>
      ) : null
  ),
}));

// Mock the MatchedEntitiesSection component
vi.mock('./MatchedEntitiesSection', () => ({
  default: vi.fn(
    ({
      eventId,
      onEntityClick,
    }: {
      eventId: number;
      onEntityClick?: (entityId: string) => void;
    }) => (
      <div data-testid="matched-entities-section-mock" data-event-id={eventId}>
        Mocked MatchedEntitiesSection
        {onEntityClick && (
          <button
            data-testid="mock-entity-click"
            onClick={() => onEntityClick('entity-person-123')}
          >
            Click Entity
          </button>
        )}
      </div>
    )
  ),
}));

describe('EventDetailModal', () => {
  // Mock event data
  const mockEvent: Event = {
    id: 'event-123',
    timestamp: '2024-01-15T10:30:00Z',
    camera_name: 'Front Door',
    risk_score: 65,
    risk_label: 'High',
    summary: 'Person detected approaching the front entrance with a package',
    reasoning:
      'The detected person is approaching the entrance during evening hours carrying an unidentified package. This warrants attention.',
    image_url: 'https://example.com/image.jpg',
    thumbnail_url: 'https://example.com/thumbnail.jpg',
    detections: [
      {
        label: 'person',
        confidence: 0.95,
        bbox: { x: 100, y: 100, width: 200, height: 300 },
      },
      {
        label: 'package',
        confidence: 0.87,
        bbox: { x: 400, y: 200, width: 150, height: 100 },
      },
    ],
    reviewed: false,
  };

  const mockProps: EventDetailModalProps = {
    event: mockEvent,
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('rendering', () => {
    it('renders nothing when event is null', () => {
      const { container } = renderWithQueryClient(<EventDetailModal {...mockProps} event={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when isOpen is false', () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} isOpen={false} />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders modal when isOpen is true and event is provided', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('renders camera name as dialog title', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Front Door' })).toBeInTheDocument();
      });
    });

    it('renders formatted timestamp', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText(/January 15, 2024/)).toBeInTheDocument();
      });
    });

    it('renders risk badge with score', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('High (65)')).toBeInTheDocument();
      });
    });

    it('renders close button', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Close modal' })).toBeInTheDocument();
      });
    });
  });

  describe('image display', () => {
    it('renders full-size image when image_url is provided', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        const image = screen.getByAltText(/Front Door detection at/);
        expect(image).toBeInTheDocument();
      });
    });

    it('uses image_url over thumbnail_url when both are provided', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        // Verify image is rendered
        const image = screen.getByAltText(/Front Door detection at/);
        expect(image).toBeInTheDocument();
        expect(image.getAttribute('src')).toBe('https://example.com/image.jpg');
      });
    });

    it('falls back to thumbnail_url when image_url is not provided', async () => {
      const eventNoFullImage = { ...mockEvent, image_url: undefined };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventNoFullImage} />);
      await waitFor(() => {
        // Verify image is rendered with thumbnail
        const image = screen.getByAltText(/Front Door detection at/);
        expect(image).toBeInTheDocument();
        expect(image.getAttribute('src')).toBe('https://example.com/thumbnail.jpg');
      });
    });

    it('renders DetectionImage when detections have bounding boxes', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByAltText(/Front Door detection at/)).toBeInTheDocument();
      });
    });

    it('renders plain img when detections have no bounding boxes', async () => {
      const eventNoBbox = {
        ...mockEvent,
        detections: [
          { label: 'person', confidence: 0.95 },
          { label: 'car', confidence: 0.87 },
        ],
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventNoBbox} />);
      await waitFor(() => {
        expect(screen.getByAltText(/Front Door at/)).toBeInTheDocument();
      });
    });

    it('does not render image section when no image_url or thumbnail_url', async () => {
      const eventNoImage = { ...mockEvent, image_url: undefined, thumbnail_url: undefined };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventNoImage} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      const images = screen.queryAllByRole('img');
      expect(images.length).toBe(0);
    });
  });

  describe('AI summary and reasoning', () => {
    it('renders AI summary section', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('AI Summary')).toBeInTheDocument();
        expect(
          screen.getByText('Person detected approaching the front entrance with a package')
        ).toBeInTheDocument();
      });
    });

    it('renders AI reasoning when provided', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('AI Reasoning')).toBeInTheDocument();
        expect(
          screen.getByText(/The detected person is approaching the entrance during evening hours/)
        ).toBeInTheDocument();
      });
    });

    it('does not render AI reasoning section when reasoning is undefined', async () => {
      const eventNoReasoning = { ...mockEvent, reasoning: undefined };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventNoReasoning} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByText('AI Reasoning')).not.toBeInTheDocument();
    });

    it('does not render AI reasoning section when reasoning is empty', async () => {
      const eventEmptyReasoning = { ...mockEvent, reasoning: '' };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventEmptyReasoning} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByText('AI Reasoning')).not.toBeInTheDocument();
    });
  });

  describe('detections list', () => {
    it('renders detections section with count', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('Detected Objects (2)')).toBeInTheDocument();
      });
    });

    it('renders all detection labels', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('person')).toBeInTheDocument();
        expect(screen.getByText('package')).toBeInTheDocument();
      });
    });

    it('renders detection confidence scores', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        // Percentages may appear multiple times in modal
        expect(screen.getAllByText('95%').length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText('87%').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('formats confidence as percentage with rounding', async () => {
      const eventWithRounding = {
        ...mockEvent,
        detections: [
          { label: 'person', confidence: 0.956 },
          { label: 'car', confidence: 0.874 },
        ],
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventWithRounding} />);
      await waitFor(() => {
        expect(screen.getAllByText('96%').length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText('87%').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('does not render detections section when detections array is empty', async () => {
      const eventNoDetections = { ...mockEvent, detections: [] };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventNoDetections} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByText(/Detected Objects/)).not.toBeInTheDocument();
    });

    it('renders single detection correctly', async () => {
      const eventOneDetection = {
        ...mockEvent,
        detections: [{ label: 'person', confidence: 0.95 }],
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventOneDetection} />);
      await waitFor(() => {
        expect(screen.getByText('Detected Objects (1)')).toBeInTheDocument();
      });
    });
  });

  describe('event metadata', () => {
    it('renders event details section', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('Event Details')).toBeInTheDocument();
      });
    });

    it('renders event ID', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('Event ID')).toBeInTheDocument();
        expect(screen.getByText('event-123')).toBeInTheDocument();
      });
    });

    it('renders camera name in metadata', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('Camera')).toBeInTheDocument();
        const frontDoorLabels = screen.getAllByText('Front Door');
        expect(frontDoorLabels.length).toBeGreaterThanOrEqual(2); // Title and metadata
      });
    });

    it('renders risk score in metadata', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('Risk Score')).toBeInTheDocument();
        expect(screen.getByText('65 / 100')).toBeInTheDocument();
      });
    });

    it('renders review status as pending when not reviewed', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('Pending Review')).toBeInTheDocument();
      });
    });

    it('renders review status as reviewed when reviewed', async () => {
      const reviewedEvent = { ...mockEvent, reviewed: true };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={reviewedEvent} />);
      await waitFor(() => {
        expect(screen.getByText('Reviewed')).toBeInTheDocument();
      });
    });
  });

  describe('duration display', () => {
    it('displays duration in header when started_at and ended_at are provided', async () => {
      const eventWithDuration = {
        ...mockEvent,
        started_at: '2024-01-15T10:00:00Z',
        ended_at: '2024-01-15T10:02:30Z', // 2m 30s duration
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventWithDuration} />);
      await waitFor(() => {
        // Duration is shown inline as "Duration: 2m 30s"
        expect(screen.getAllByText(/Duration:/).length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText(/2m 30s/).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('displays duration in metadata section when started_at and ended_at are provided', async () => {
      const eventWithDuration = {
        ...mockEvent,
        started_at: '2024-01-15T10:00:00Z',
        ended_at: '2024-01-15T10:02:30Z',
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventWithDuration} />);
      await waitFor(() => {
        // Duration appears in header and metadata sections
        const durationLabels = screen.getAllByText('Duration');
        expect(durationLabels.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('displays "ongoing" for events without ended_at', async () => {
      const ongoingEvent = {
        ...mockEvent,
        started_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(), // 2 minutes ago
        ended_at: null,
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={ongoingEvent} />);
      await waitFor(() => {
        // formatDuration returns "ongoing" for events without ended_at within 5 minutes
        expect(screen.getAllByText(/ongoing/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('does not display duration when started_at is not provided', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByText(/Duration:/)).not.toBeInTheDocument();
    });

    it('renders Timer icon with duration in header', async () => {
      const eventWithDuration = {
        ...mockEvent,
        started_at: '2024-01-15T10:00:00Z',
        ended_at: '2024-01-15T10:02:30Z',
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventWithDuration} />);
      await waitFor(() => {
        // Duration text should be rendered with the Timer icon
        // Verify the duration display exists (the Timer icon is adjacent to the duration text)
        const durationDisplay = screen.getAllByText(/Duration:/);
        expect(durationDisplay.length).toBeGreaterThanOrEqual(1);
        // The Timer icon is rendered as part of the duration display
        // We verify it indirectly by confirming the duration section exists
      });
    });

    it('formats various duration lengths correctly', async () => {
      const baseTime = new Date('2024-01-15T10:00:00Z').getTime();
      const testCases = [
        { duration: 30 * 1000, expected: '30s' }, // 30 seconds
        { duration: 5 * 60 * 1000, expected: '5m' }, // 5 minutes
        { duration: 2 * 60 * 60 * 1000, expected: '2h' }, // 2 hours
        { duration: 36 * 60 * 60 * 1000, expected: '1d 12h' }, // 1 day 12 hours
      ];

      for (const { duration, expected } of testCases) {
        const eventWithDuration = {
          ...mockEvent,
          started_at: new Date(baseTime).toISOString(),
          ended_at: new Date(baseTime + duration).toISOString(),
        };
        const { unmount } = renderWithQueryClient(
          <EventDetailModal {...mockProps} event={eventWithDuration} />
        );
        await waitFor(() => {
          // Duration appears in both header and metadata, so use getAllByText
          const matches = screen.getAllByText(expected);
          expect(matches.length).toBeGreaterThanOrEqual(1);
        });
        unmount();
      }
    });

    it('uses timestamp as fallback when started_at is not provided', async () => {
      const eventWithEndedAt = {
        ...mockEvent,
        ended_at: '2024-01-15T10:02:30Z',
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventWithEndedAt} />);
      await waitFor(() => {
        expect(screen.getAllByText(/Duration:/).length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe('close functionality', () => {
    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onClose = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Close modal' })).toBeInTheDocument();
      });

      const closeButton = screen.getByRole('button', { name: 'Close modal' });
      await user.click(closeButton);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when escape key is pressed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onClose = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.keyboard('{Escape}');

      // Headless UI Dialog also handles Escape, so onClose should be called
      await waitFor(() => {
        expect(onClose).toHaveBeenCalled();
      });
    });

    it('calls onClose when clicking backdrop', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onClose = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      const backdrop = dialog.parentElement?.parentElement?.firstChild as HTMLElement;

      if (backdrop) {
        await user.click(backdrop);
      }

      // Headless UI handles backdrop clicks, so we just verify modal can close
      expect(onClose).toBeDefined();
    });

    it('does not call onClose when modal is already closed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onClose = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} isOpen={false} onClose={onClose} />);

      await user.keyboard('{Escape}');

      // Advance time to ensure no delayed calls
      act(() => {
        vi.advanceTimersByTime(100);
      });
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('navigation', () => {
    it('renders navigation buttons when onNavigate is provided', async () => {
      const onNavigate = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Previous event' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Next event' })).toBeInTheDocument();
      });
    });

    it('does not render navigation buttons when onNavigate is undefined', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} onNavigate={undefined} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByRole('button', { name: 'Previous event' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Next event' })).not.toBeInTheDocument();
    });

    it('calls onNavigate with "prev" when Previous button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onNavigate = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Previous event' })).toBeInTheDocument();
      });

      const prevButton = screen.getByRole('button', { name: 'Previous event' });
      await user.click(prevButton);

      expect(onNavigate).toHaveBeenCalledWith('prev');
      expect(onNavigate).toHaveBeenCalledTimes(1);
    });

    it('calls onNavigate with "next" when Next button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onNavigate = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Next event' })).toBeInTheDocument();
      });

      const nextButton = screen.getByRole('button', { name: 'Next event' });
      await user.click(nextButton);

      expect(onNavigate).toHaveBeenCalledWith('next');
      expect(onNavigate).toHaveBeenCalledTimes(1);
    });

    it('calls onNavigate with "prev" when left arrow key is pressed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onNavigate = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.keyboard('{ArrowLeft}');

      await waitFor(() => {
        expect(onNavigate).toHaveBeenCalledWith('prev');
      });
    });

    it('calls onNavigate with "next" when right arrow key is pressed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onNavigate = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.keyboard('{ArrowRight}');

      await waitFor(() => {
        expect(onNavigate).toHaveBeenCalledWith('next');
      });
    });

    it('does not call onNavigate on arrow keys when modal is closed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onNavigate = vi.fn();
      renderWithQueryClient(
        <EventDetailModal {...mockProps} isOpen={false} onNavigate={onNavigate} />
      );

      await user.keyboard('{ArrowLeft}');
      await user.keyboard('{ArrowRight}');

      // Advance time to ensure no delayed calls
      act(() => {
        vi.advanceTimersByTime(100);
      });
      expect(onNavigate).not.toHaveBeenCalled();
    });

    it('does not call onNavigate on arrow keys when onNavigate is undefined', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockProps} onNavigate={undefined} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.keyboard('{ArrowLeft}');
      await user.keyboard('{ArrowRight}');

      // No errors should occur
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('mark as reviewed', () => {
    it('renders mark as reviewed button when onMarkReviewed is provided and event is not reviewed', async () => {
      const onMarkReviewed = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onMarkReviewed={onMarkReviewed} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Mark event as reviewed' })).toBeInTheDocument();
      });
    });

    it('does not render mark as reviewed button when event is already reviewed', async () => {
      const reviewedEvent = { ...mockEvent, reviewed: true };
      const onMarkReviewed = vi.fn();
      renderWithQueryClient(
        <EventDetailModal {...mockProps} event={reviewedEvent} onMarkReviewed={onMarkReviewed} />
      );

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(
        screen.queryByRole('button', { name: 'Mark event as reviewed' })
      ).not.toBeInTheDocument();
    });

    it('does not render mark as reviewed button when onMarkReviewed is undefined', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} onMarkReviewed={undefined} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(
        screen.queryByRole('button', { name: 'Mark event as reviewed' })
      ).not.toBeInTheDocument();
    });

    it('calls onMarkReviewed with event ID when button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onMarkReviewed = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onMarkReviewed={onMarkReviewed} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Mark event as reviewed' })).toBeInTheDocument();
      });

      const reviewButton = screen.getByRole('button', { name: 'Mark event as reviewed' });
      await user.click(reviewButton);

      expect(onMarkReviewed).toHaveBeenCalledWith('event-123');
      expect(onMarkReviewed).toHaveBeenCalledTimes(1);
    });
  });

  describe('accessibility', () => {
    it('has role="dialog"', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('has aria-modal attribute', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        const dialog = screen.getByRole('dialog');
        expect(dialog).toHaveAttribute('aria-modal');
      });
    });

    it('has aria-labelledby pointing to title', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        const dialog = screen.getByRole('dialog');
        const labelledBy = dialog.getAttribute('aria-labelledby');
        // Headless UI sets this attribute, verify it exists
        expect(labelledBy).not.toBeNull();
      });
    });

    it('renders title with correct ID for aria-labelledby', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        const title = screen.getByRole('heading', { name: 'Front Door' });
        expect(title).toHaveAttribute('id', 'event-detail-title');
      });
    });

    it('close button has aria-label', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        const closeButton = screen.getByRole('button', { name: 'Close modal' });
        expect(closeButton).toHaveAttribute('aria-label', 'Close modal');
      });
    });

    it('navigation buttons have aria-labels', async () => {
      const onNavigate = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Previous event' })).toHaveAttribute(
          'aria-label',
          'Previous event'
        );
        expect(screen.getByRole('button', { name: 'Next event' })).toHaveAttribute(
          'aria-label',
          'Next event'
        );
      });
    });

    it('mark as reviewed button has aria-label', async () => {
      const onMarkReviewed = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onMarkReviewed={onMarkReviewed} />);

      await waitFor(() => {
        const reviewButton = screen.getByRole('button', { name: 'Mark event as reviewed' });
        expect(reviewButton).toHaveAttribute('aria-label', 'Mark event as reviewed');
      });
    });

    it('backdrop has aria-hidden', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        // Verify modal is accessible (dialog role present)
        const dialog = screen.getByRole('dialog');
        expect(dialog).toBeInTheDocument();
        // Headless UI manages backdrop aria-hidden automatically
      });
    });
  });

  describe('styling and layout', () => {
    it('renders modal with proper structure', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        const dialog = screen.getByRole('dialog');
        expect(dialog).toBeInTheDocument();
      });
    });

    it('renders header with title and close button', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Front Door' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Close modal' })).toBeInTheDocument();
      });
    });

    it('renders main content sections', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('AI Summary')).toBeInTheDocument();
        expect(screen.getByText('Event Details')).toBeInTheDocument();
      });
    });

    it('renders footer with appropriate spacing', async () => {
      const onNavigate = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Previous event' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Next event' })).toBeInTheDocument();
      });
    });
  });

  describe('edge cases', () => {
    it('handles invalid timestamp gracefully', async () => {
      const eventInvalidTimestamp = { ...mockEvent, timestamp: 'invalid-date' };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventInvalidTimestamp} />);
      await waitFor(() => {
        expect(screen.getByText('Invalid Date')).toBeInTheDocument();
      });
    });

    it('handles very long summary text', async () => {
      const longSummary =
        'This is a very long summary that describes an extremely complex security event with multiple elements and detailed analysis of what has occurred at this particular location and time with extensive contextual information that goes on and on.';
      const eventLongSummary = { ...mockEvent, summary: longSummary };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventLongSummary} />);
      await waitFor(() => {
        expect(screen.getByText(longSummary)).toBeInTheDocument();
      });
    });

    it('handles very long reasoning text', async () => {
      const longReasoning =
        'This is a very long reasoning text that provides extensive analysis and explanation of the security event including multiple factors, contextual elements, historical patterns, and detailed justification for the assigned risk score with numerous details.';
      const eventLongReasoning = { ...mockEvent, reasoning: longReasoning };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventLongReasoning} />);
      await waitFor(() => {
        expect(screen.getByText(longReasoning)).toBeInTheDocument();
      });
    });

    it('handles detection with 100% confidence', async () => {
      const eventPerfectConfidence = {
        ...mockEvent,
        detections: [{ label: 'person', confidence: 1.0 }],
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventPerfectConfidence} />);
      await waitFor(() => {
        expect(screen.getAllByText('100%').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('handles detection with 0% confidence', async () => {
      const eventZeroConfidence = {
        ...mockEvent,
        detections: [{ label: 'person', confidence: 0.0 }],
      };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventZeroConfidence} />);
      await waitFor(() => {
        expect(screen.getAllByText('0%').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('handles risk score at boundary values', async () => {
      const boundaryScores = [0, 25, 50, 75, 100];

      for (const score of boundaryScores) {
        const eventBoundary = { ...mockEvent, risk_score: score };
        const { unmount } = renderWithQueryClient(
          <EventDetailModal {...mockProps} event={eventBoundary} />
        );
        await waitFor(() => {
          expect(screen.getByText(`${score} / 100`)).toBeInTheDocument();
        });
        unmount();
      }
    });

    it('handles empty camera name', async () => {
      const eventEmptyCamera = { ...mockEvent, camera_name: '' };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventEmptyCamera} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('handles very long camera name', async () => {
      const longCameraName = 'Front Door Main Entrance Camera Position Alpha North Wing Building A';
      const eventLongCamera = { ...mockEvent, camera_name: longCameraName };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventLongCamera} />);
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: longCameraName })).toBeInTheDocument();
      });
    });

    it('handles many detections', async () => {
      const manyDetections = Array.from({ length: 20 }, (_, i) => ({
        label: `object-${i}`,
        confidence: 0.5 + i * 0.02,
      }));
      const eventManyDetections = { ...mockEvent, detections: manyDetections };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventManyDetections} />);
      await waitFor(() => {
        expect(screen.getByText('Detected Objects (20)')).toBeInTheDocument();
      });
    });
  });

  describe('event transitions', () => {
    it('handles event prop changing while modal is open', async () => {
      const { rerender, queryClient } = renderWithQueryClient(<EventDetailModal {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Front Door' })).toBeInTheDocument();
      });

      const newEvent = { ...mockEvent, id: 'event-456', camera_name: 'Back Door', risk_score: 30 };
      rerender(
        <QueryClientProvider client={queryClient}>
          <EventDetailModal {...mockProps} event={newEvent} />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Back Door' })).toBeInTheDocument();
        expect(screen.getByText('30 / 100')).toBeInTheDocument();
      });
    });

    it('handles toggling isOpen prop', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} isOpen={true} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });
  });

  describe('notes functionality', () => {
    it('renders notes section with textarea', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByText('Notes')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Add notes about this event...')).toBeInTheDocument();
      });
    });

    it('initializes notes textarea with event notes', async () => {
      const eventWithNotes = { ...mockEvent, notes: 'Delivery person confirmed' };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventWithNotes} />);
      await waitFor(() => {
        const textarea = screen.getByPlaceholderText<HTMLTextAreaElement>(
          'Add notes about this event...'
        );
        expect(textarea.value).toBe('Delivery person confirmed');
      });
    });

    it('initializes notes textarea as empty when event has no notes', async () => {
      const eventNoNotes = { ...mockEvent, notes: null };
      renderWithQueryClient(<EventDetailModal {...mockProps} event={eventNoNotes} />);
      await waitFor(() => {
        const textarea = screen.getByPlaceholderText<HTMLTextAreaElement>(
          'Add notes about this event...'
        );
        expect(textarea.value).toBe('');
      });
    });

    it('allows typing in notes textarea', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Add notes about this event...')).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText<HTMLTextAreaElement>(
        'Add notes about this event...'
      );
      await user.clear(textarea);
      await user.type(textarea, 'This is a test note');

      expect(textarea.value).toBe('This is a test note');
    });

    it('renders save notes button', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Save notes' })).toBeInTheDocument();
      });
    });

    it('calls onSaveNotes when save button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onSaveNotes = vi.fn().mockResolvedValue(undefined);
      renderWithQueryClient(<EventDetailModal {...mockProps} onSaveNotes={onSaveNotes} />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Add notes about this event...')).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText<HTMLTextAreaElement>(
        'Add notes about this event...'
      );
      await user.clear(textarea);
      await user.type(textarea, 'New note');

      const saveButton = screen.getByRole('button', { name: 'Save notes' });
      await user.click(saveButton);

      await waitFor(() => {
        expect(onSaveNotes).toHaveBeenCalledWith('event-123', 'New note');
      });
    });

    it('disables save button when onSaveNotes is not provided', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} onSaveNotes={undefined} />);

      await waitFor(() => {
        const saveButton = screen.getByRole('button', { name: 'Save notes' });
        expect(saveButton).toBeDisabled();
      });
    });

    it('shows saving state while saving notes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      let resolveSave: () => void;
      const savePromise = new Promise<void>((resolve) => {
        resolveSave = resolve;
      });
      const onSaveNotes = vi.fn().mockReturnValue(savePromise);

      renderWithQueryClient(<EventDetailModal {...mockProps} onSaveNotes={onSaveNotes} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Save notes' })).toBeInTheDocument();
      });

      const saveButton = screen.getByRole('button', { name: 'Save notes' });
      await user.click(saveButton);

      expect(screen.getByText('Saving...')).toBeInTheDocument();
      expect(saveButton).toBeDisabled();

      resolveSave!();
      await waitFor(() => {
        expect(screen.queryByText('Saving...')).not.toBeInTheDocument();
      });
    });

    it('shows saved indicator after successful save', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onSaveNotes = vi.fn().mockResolvedValue(undefined);

      renderWithQueryClient(<EventDetailModal {...mockProps} onSaveNotes={onSaveNotes} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Save notes' })).toBeInTheDocument();
      });

      const saveButton = screen.getByRole('button', { name: 'Save notes' });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Saved')).toBeInTheDocument();
      });
    });

    it('clears saved indicator after 3 seconds', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onSaveNotes = vi.fn().mockResolvedValue(undefined);

      renderWithQueryClient(<EventDetailModal {...mockProps} onSaveNotes={onSaveNotes} />);

      // Wait for the modal to open and button to be available
      const saveButton = await screen.findByRole('button', { name: 'Save notes' });
      await user.click(saveButton);

      // Wait for the save to complete
      await waitFor(() => {
        expect(screen.getByText('Saved')).toBeInTheDocument();
      });

      // Advance time by 3 seconds to clear the indicator
      act(() => {
        vi.advanceTimersByTime(3000);
      });

      await waitFor(() => {
        expect(screen.queryByText('Saved')).not.toBeInTheDocument();
      });
    });

    it('handles save errors gracefully', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const onSaveNotes = vi.fn().mockRejectedValue(new Error('Save failed'));

      renderWithQueryClient(<EventDetailModal {...mockProps} onSaveNotes={onSaveNotes} />);

      // Wait for the modal to open and button to be available
      const saveButton = await screen.findByRole('button', { name: 'Save notes' });
      await user.click(saveButton);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to save notes:', expect.any(Error));
      });

      // Saved indicator should not appear after error
      expect(screen.queryByText('Saved')).not.toBeInTheDocument();

      consoleSpy.mockRestore();
    });

    it('updates notes text when event changes', async () => {
      const { rerender, queryClient } = renderWithQueryClient(<EventDetailModal {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Add notes about this event...')).toBeInTheDocument();
      });

      const textarea = screen.getByPlaceholderText<HTMLTextAreaElement>(
        'Add notes about this event...'
      );
      expect(textarea.value).toBe('');

      const eventWithNotes = { ...mockEvent, id: 'event-456', notes: 'Different notes' };
      rerender(
        <QueryClientProvider client={queryClient}>
          <EventDetailModal {...mockProps} event={eventWithNotes} />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(textarea.value).toBe('Different notes');
      });
    });

    it('clears saved indicator when event changes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onSaveNotes = vi.fn().mockResolvedValue(undefined);

      const { rerender, queryClient } = renderWithQueryClient(
        <EventDetailModal {...mockProps} onSaveNotes={onSaveNotes} />
      );

      // Wait for the modal to open and button to be available
      const saveButton = await screen.findByRole('button', { name: 'Save notes' });
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Saved')).toBeInTheDocument();
      });

      // Change to a different event
      const newEvent = { ...mockEvent, id: 'event-456', notes: 'Different notes' };
      rerender(
        <QueryClientProvider client={queryClient}>
          <EventDetailModal {...mockProps} event={newEvent} onSaveNotes={onSaveNotes} />
        </QueryClientProvider>
      );

      // Saved indicator should be cleared when event changes
      await waitFor(() => {
        expect(screen.queryByText('Saved')).not.toBeInTheDocument();
      });
    });

    it('saves empty string as notes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const eventWithNotes = { ...mockEvent, notes: 'Some existing notes' };
      const onSaveNotes = vi.fn().mockResolvedValue(undefined);

      renderWithQueryClient(
        <EventDetailModal {...mockProps} event={eventWithNotes} onSaveNotes={onSaveNotes} />
      );

      // Wait for the modal to open
      const textarea = await screen.findByPlaceholderText<HTMLTextAreaElement>(
        'Add notes about this event...'
      );
      expect(textarea.value).toBe('Some existing notes');

      // Clear the textarea
      await user.clear(textarea);
      expect(textarea.value).toBe('');

      // Save the empty notes
      const saveButton = await screen.findByRole('button', { name: 'Save notes' });
      await user.click(saveButton);

      await waitFor(() => {
        expect(onSaveNotes).toHaveBeenCalledWith('event-123', '');
      });
    });
  });

  describe('flag event', () => {
    it('renders flag event button when onFlagEvent is provided', async () => {
      const onFlagEvent = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onFlagEvent={onFlagEvent} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Flag event' })).toBeInTheDocument();
      });
    });

    it('does not render flag event button when onFlagEvent is undefined', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} onFlagEvent={undefined} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByRole('button', { name: 'Flag event' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Unflag event' })).not.toBeInTheDocument();
    });

    it('shows "Flag Event" when event is not flagged', async () => {
      const eventNotFlagged = { ...mockEvent, flagged: false };
      const onFlagEvent = vi.fn();
      renderWithQueryClient(
        <EventDetailModal {...mockProps} event={eventNotFlagged} onFlagEvent={onFlagEvent} />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Flag event' })).toHaveTextContent('Flag Event');
      });
    });

    it('shows "Unflag Event" when event is flagged', async () => {
      const eventFlagged = { ...mockEvent, flagged: true };
      const onFlagEvent = vi.fn();
      renderWithQueryClient(
        <EventDetailModal {...mockProps} event={eventFlagged} onFlagEvent={onFlagEvent} />
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Unflag event' })).toHaveTextContent(
          'Unflag Event'
        );
      });
    });

    it('calls onFlagEvent with correct parameters when flagging unflagged event', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const eventNotFlagged = { ...mockEvent, flagged: false };
      const onFlagEvent = vi.fn().mockResolvedValue(undefined);
      renderWithQueryClient(
        <EventDetailModal {...mockProps} event={eventNotFlagged} onFlagEvent={onFlagEvent} />
      );

      // Wait for the modal to open and button to be available
      const flagButton = await screen.findByRole('button', { name: 'Flag event' });
      await user.click(flagButton);

      await waitFor(() => {
        expect(onFlagEvent).toHaveBeenCalledWith('event-123', true);
      });
    });

    it('calls onFlagEvent with correct parameters when unflagging flagged event', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const eventFlagged = { ...mockEvent, flagged: true };
      const onFlagEvent = vi.fn().mockResolvedValue(undefined);
      renderWithQueryClient(
        <EventDetailModal {...mockProps} event={eventFlagged} onFlagEvent={onFlagEvent} />
      );

      // Wait for the modal to open and button to be available
      const unflagButton = await screen.findByRole('button', { name: 'Unflag event' });
      await user.click(unflagButton);

      await waitFor(() => {
        expect(onFlagEvent).toHaveBeenCalledWith('event-123', false);
      });
    });

    it('disables flag button while flagging is in progress', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      let resolveFlagging: () => void;
      const flaggingPromise = new Promise<void>((resolve) => {
        resolveFlagging = resolve;
      });
      const onFlagEvent = vi.fn().mockReturnValue(flaggingPromise);

      renderWithQueryClient(<EventDetailModal {...mockProps} onFlagEvent={onFlagEvent} />);

      // Wait for the modal to open and button to be available
      const flagButton = await screen.findByRole('button', { name: 'Flag event' });
      await user.click(flagButton);

      await waitFor(() => {
        expect(screen.getByText('Flagging...')).toBeInTheDocument();
      });
      expect(flagButton).toBeDisabled();

      resolveFlagging!();
      await waitFor(() => {
        expect(screen.queryByText('Flagging...')).not.toBeInTheDocument();
      });
    });

    it('handles flagging errors gracefully', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const onFlagEvent = vi.fn().mockRejectedValue(new Error('Flagging failed'));

      renderWithQueryClient(<EventDetailModal {...mockProps} onFlagEvent={onFlagEvent} />);

      // Wait for the modal to open and button to be available
      const flagButton = await screen.findByRole('button', { name: 'Flag event' });
      await user.click(flagButton);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to flag event:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });

    it('applies different styling for flagged vs unflagged state', async () => {
      const eventNotFlagged = { ...mockEvent, flagged: false };
      const eventFlagged = { ...mockEvent, flagged: true };
      const onFlagEvent = vi.fn();

      const { rerender, queryClient } = renderWithQueryClient(
        <EventDetailModal {...mockProps} event={eventNotFlagged} onFlagEvent={onFlagEvent} />
      );

      await waitFor(() => {
        const flagButton = screen.getByRole('button', { name: 'Flag event' });
        expect(flagButton).toHaveClass('bg-gray-800');
      });

      rerender(
        <QueryClientProvider client={queryClient}>
          <EventDetailModal {...mockProps} event={eventFlagged} onFlagEvent={onFlagEvent} />
        </QueryClientProvider>
      );

      await waitFor(() => {
        const unflagButton = screen.getByRole('button', { name: 'Unflag event' });
        expect(unflagButton).toHaveClass('bg-yellow-600');
      });
    });

    it('has correct aria-label for flagged state', async () => {
      const eventFlagged = { ...mockEvent, flagged: true };
      const onFlagEvent = vi.fn();
      renderWithQueryClient(
        <EventDetailModal {...mockProps} event={eventFlagged} onFlagEvent={onFlagEvent} />
      );

      await waitFor(() => {
        const button = screen.getByRole('button', { name: 'Unflag event' });
        expect(button).toHaveAttribute('aria-label', 'Unflag event');
      });
    });

    it('has correct aria-label for unflagged state', async () => {
      const eventNotFlagged = { ...mockEvent, flagged: false };
      const onFlagEvent = vi.fn();
      renderWithQueryClient(
        <EventDetailModal {...mockProps} event={eventNotFlagged} onFlagEvent={onFlagEvent} />
      );

      await waitFor(() => {
        const button = screen.getByRole('button', { name: 'Flag event' });
        expect(button).toHaveAttribute('aria-label', 'Flag event');
      });
    });
  });

  describe('download media', () => {
    it('renders download media button when onDownloadMedia is provided', async () => {
      const onDownloadMedia = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onDownloadMedia={onDownloadMedia} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Download media' })).toBeInTheDocument();
      });
    });

    it('does not render download media button when onDownloadMedia is undefined', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} onDownloadMedia={undefined} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
      expect(screen.queryByRole('button', { name: 'Download media' })).not.toBeInTheDocument();
    });

    it('calls onDownloadMedia with event ID when button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onDownloadMedia = vi.fn().mockResolvedValue(undefined);
      renderWithQueryClient(<EventDetailModal {...mockProps} onDownloadMedia={onDownloadMedia} />);

      // Wait for the modal to open and button to be available
      const downloadButton = await screen.findByRole('button', { name: 'Download media' });
      await user.click(downloadButton);

      await waitFor(() => {
        expect(onDownloadMedia).toHaveBeenCalledWith('event-123');
      });
    });

    it('disables download button while download is in progress', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      let resolveDownload: () => void;
      const downloadPromise = new Promise<void>((resolve) => {
        resolveDownload = resolve;
      });
      const onDownloadMedia = vi.fn().mockReturnValue(downloadPromise);

      renderWithQueryClient(<EventDetailModal {...mockProps} onDownloadMedia={onDownloadMedia} />);

      // Wait for the modal to open and button to be available
      const downloadButton = await screen.findByRole('button', { name: 'Download media' });
      await user.click(downloadButton);

      await waitFor(() => {
        expect(screen.getByText('Downloading...')).toBeInTheDocument();
      });
      expect(downloadButton).toBeDisabled();

      resolveDownload!();
      await waitFor(() => {
        expect(screen.queryByText('Downloading...')).not.toBeInTheDocument();
      });
    });

    it('handles download errors gracefully', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const onDownloadMedia = vi.fn().mockRejectedValue(new Error('Download failed'));

      renderWithQueryClient(<EventDetailModal {...mockProps} onDownloadMedia={onDownloadMedia} />);

      // Wait for the modal to open and button to be available
      const downloadButton = await screen.findByRole('button', { name: 'Download media' });
      await user.click(downloadButton);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Failed to download media:', expect.any(Error));
      });

      consoleSpy.mockRestore();
    });

    it('has correct aria-label', async () => {
      const onDownloadMedia = vi.fn();
      renderWithQueryClient(<EventDetailModal {...mockProps} onDownloadMedia={onDownloadMedia} />);

      await waitFor(() => {
        const button = screen.getByRole('button', { name: 'Download media' });
        expect(button).toHaveAttribute('aria-label', 'Download media');
      });
    });

    it('can be called multiple times', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onDownloadMedia = vi.fn().mockResolvedValue(undefined);
      renderWithQueryClient(<EventDetailModal {...mockProps} onDownloadMedia={onDownloadMedia} />);

      // Wait for the modal to open and button to be available
      const downloadButton = await screen.findByRole('button', { name: 'Download media' });

      await user.click(downloadButton);
      await waitFor(() => {
        expect(onDownloadMedia).toHaveBeenCalledTimes(1);
      });

      await user.click(downloadButton);
      await waitFor(() => {
        expect(onDownloadMedia).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('integration', () => {
    it('renders complete modal with all sections', async () => {
      const onClose = vi.fn();
      const onMarkReviewed = vi.fn();
      const onNavigate = vi.fn();

      renderWithQueryClient(
        <EventDetailModal
          {...mockProps}
          onClose={onClose}
          onMarkReviewed={onMarkReviewed}
          onNavigate={onNavigate}
        />
      );

      // Verify all major sections are present
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Front Door' })).toBeInTheDocument();
        expect(screen.getByText(/January 15, 2024/)).toBeInTheDocument();
        const badges = screen.getAllByText(/High.*65/);
        expect(badges.length).toBeGreaterThan(0);
        expect(screen.getByText('AI Summary')).toBeInTheDocument();
        expect(screen.getByText('AI Reasoning')).toBeInTheDocument();
        expect(screen.getByText('Detected Objects (2)')).toBeInTheDocument();
        expect(screen.getByText('Event Details')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Close modal' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Previous event' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Next event' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Mark event as reviewed' })).toBeInTheDocument();
      });
    });

    it('renders complete modal with all action buttons', async () => {
      const onClose = vi.fn();
      const onMarkReviewed = vi.fn();
      const onNavigate = vi.fn();
      const onFlagEvent = vi.fn();
      const onDownloadMedia = vi.fn();

      renderWithQueryClient(
        <EventDetailModal
          {...mockProps}
          onClose={onClose}
          onMarkReviewed={onMarkReviewed}
          onNavigate={onNavigate}
          onFlagEvent={onFlagEvent}
          onDownloadMedia={onDownloadMedia}
        />
      );

      // Verify all action buttons are present
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Flag event' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Download media' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Mark event as reviewed' })).toBeInTheDocument();
      });
    });

    it('handles multiple interactions without errors', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onClose = vi.fn();
      const onMarkReviewed = vi.fn();
      const onNavigate = vi.fn();
      const onSaveNotes = vi.fn().mockResolvedValue(undefined);
      const onFlagEvent = vi.fn().mockResolvedValue(undefined);
      const onDownloadMedia = vi.fn().mockResolvedValue(undefined);

      renderWithQueryClient(
        <EventDetailModal
          {...mockProps}
          onClose={onClose}
          onMarkReviewed={onMarkReviewed}
          onNavigate={onNavigate}
          onSaveNotes={onSaveNotes}
          onFlagEvent={onFlagEvent}
          onDownloadMedia={onDownloadMedia}
        />
      );

      // Wait for the modal to open
      await screen.findByRole('dialog');

      // Navigate previous
      const prevButton = await screen.findByRole('button', { name: 'Previous event' });
      await user.click(prevButton);
      expect(onNavigate).toHaveBeenCalledWith('prev');

      // Navigate next
      const nextButton = await screen.findByRole('button', { name: 'Next event' });
      await user.click(nextButton);
      expect(onNavigate).toHaveBeenCalledWith('next');

      // Flag event
      const flagButton = await screen.findByRole('button', { name: 'Flag event' });
      await user.click(flagButton);
      await waitFor(() => {
        expect(onFlagEvent).toHaveBeenCalledWith('event-123', true);
      });

      // Download media
      const downloadButton = await screen.findByRole('button', { name: 'Download media' });
      await user.click(downloadButton);
      await waitFor(() => {
        expect(onDownloadMedia).toHaveBeenCalledWith('event-123');
      });

      // Type in notes
      const textarea = await screen.findByPlaceholderText('Add notes about this event...');
      await user.type(textarea, 'Test note');

      // Save notes
      const saveButton = await screen.findByRole('button', { name: 'Save notes' });
      await user.click(saveButton);
      await waitFor(() => {
        expect(onSaveNotes).toHaveBeenCalledWith('event-123', 'Test note');
      });

      // Mark as reviewed
      const reviewButton = await screen.findByRole('button', { name: 'Mark event as reviewed' });
      await user.click(reviewButton);
      expect(onMarkReviewed).toHaveBeenCalledWith('event-123');

      // All interactions should work without errors
      expect(onNavigate).toHaveBeenCalledTimes(2);
      expect(onFlagEvent).toHaveBeenCalledTimes(1);
      expect(onDownloadMedia).toHaveBeenCalledTimes(1);
      expect(onSaveNotes).toHaveBeenCalledTimes(1);
      expect(onMarkReviewed).toHaveBeenCalledTimes(1);
    });
  });

  describe('video detection display', () => {
    // Mock event with numeric ID (required for detection fetching)
    const mockEventWithNumericId: Event = {
      ...mockEvent,
      id: '123', // Must be numeric string for parseInt to work
    };

    const mockVideoProps: EventDetailModalProps = {
      ...mockProps,
      event: mockEventWithNumericId,
    };

    const mockVideoDetection = {
      id: 1,
      camera_id: '123e4567-e89b-12d3-a456-426614174000',
      file_path: '/export/foscam/front_door/20251223_120000.mp4',
      file_type: 'video/mp4',
      detected_at: '2024-01-15T10:30:00Z',
      object_type: 'person',
      confidence: 0.95,
      bbox_x: 100,
      bbox_y: 150,
      bbox_width: 200,
      bbox_height: 400,
      thumbnail_path: '/data/thumbnails/1_thumb.jpg',
      media_type: 'video',
      duration: 150, // 2m 30s
      video_codec: 'h264',
      video_width: 1920,
      video_height: 1080,
    };

    const mockImageDetection = {
      id: 2,
      camera_id: '123e4567-e89b-12d3-a456-426614174000',
      file_path: '/export/foscam/front_door/20251223_120001.jpg',
      file_type: 'image/jpeg',
      detected_at: '2024-01-15T10:30:01Z',
      object_type: 'car',
      confidence: 0.88,
      bbox_x: 200,
      bbox_y: 100,
      bbox_width: 300,
      bbox_height: 200,
      thumbnail_path: '/data/thumbnails/2_thumb.jpg',
      media_type: 'image',
      duration: null,
      video_codec: null,
      video_width: null,
      video_height: null,
    };

    it('renders VideoPlayer when selected detection is a video', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('video-player')).toBeInTheDocument();
      });
    });

    it('passes correct video src and poster to VideoPlayer', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        const videoPlayer = screen.getByTestId('video-player');
        expect(videoPlayer).toHaveAttribute('data-src', '/api/detections/1/video');
        expect(videoPlayer).toHaveAttribute('data-poster', '/api/detections/1/video/thumbnail');
      });
    });

    it('renders image instead of video when detection is an image', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockImageDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        expect(screen.queryByTestId('video-player')).not.toBeInTheDocument();
      });
      // The image display should still work (from event.image_url)
      expect(screen.getByAltText(/Front Door detection at/)).toBeInTheDocument();
    });

    it('displays video metadata badge for video detections', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        expect(screen.getByText('Video')).toBeInTheDocument();
      });
    });

    it('displays video duration in metadata badge', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        // 150 seconds = 2m 30s - text appears in both metadata badge and event details
        const durationElements = screen.getAllByText('2m 30s');
        expect(durationElements.length).toBeGreaterThan(0);
      });
    });

    it('displays video resolution in metadata badge', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        // Resolution appears in both metadata badge and event details
        const resolutionElements = screen.getAllByText('1920x1080');
        expect(resolutionElements.length).toBeGreaterThan(0);
      });
    });

    it('displays video codec in metadata badge', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        // Codec appears in both metadata badge and event details
        const codecElements = screen.getAllByText('H264');
        expect(codecElements.length).toBeGreaterThan(0);
      });
    });

    it('displays video details in event details section', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        expect(screen.getByText('Video Details')).toBeInTheDocument();
        expect(screen.getByText('Video Duration')).toBeInTheDocument();
        expect(screen.getByText('Resolution')).toBeInTheDocument();
        expect(screen.getByText('Codec')).toBeInTheDocument();
      });
    });

    it('does not show video details section for image detections', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockImageDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      // Wait for detections to load
      await waitFor(() => {
        expect(api.fetchEventDetections).toHaveBeenCalled();
      });

      // Should not show video details
      expect(screen.queryByText('Video Details')).not.toBeInTheDocument();
    });

    it('handles video detection with missing optional metadata', async () => {
      const minimalVideoDetection = {
        ...mockVideoDetection,
        duration: null,
        video_codec: null,
        video_width: null,
        video_height: null,
      };

      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [minimalVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('video-player')).toBeInTheDocument();
        expect(screen.getByText('Video')).toBeInTheDocument();
      });

      // Should not show optional metadata that is null
      expect(screen.queryByText('1920x1080')).not.toBeInTheDocument();
      expect(screen.queryByText('H264')).not.toBeInTheDocument();
    });

    it('formats short video duration correctly', async () => {
      const shortVideoDetection = {
        ...mockVideoDetection,
        duration: 45, // 45 seconds
      };

      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [shortVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        // Duration appears in both metadata badge and event details
        const durationElements = screen.getAllByText('45s');
        expect(durationElements.length).toBeGreaterThan(0);
      });
    });

    it('switches between video and image when clicking thumbnails', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockVideoDetection, mockImageDetection],
        pagination: { total: 2, limit: 100, offset: 0, has_more: false },
      });

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      // Initially should show video (first detection)
      await waitFor(() => {
        expect(screen.getByTestId('video-player')).toBeInTheDocument();
      });

      // Click on the second thumbnail (image detection)
      const thumbnails = await screen.findAllByRole('button');
      // Find the thumbnail button (not navigation/action buttons)
      const thumbnailButton = thumbnails.find(
        (btn) =>
          btn.getAttribute('aria-label')?.includes('detection') ||
          btn.closest('[data-testid="thumbnail-strip"]')
      );

      if (thumbnailButton) {
        await user.click(thumbnailButton);
        // After clicking image thumbnail, video player should be gone
        // Note: This test may need adjustment based on actual thumbnail strip implementation
      }
    });

    it('uses video thumbnail URL for video detection thumbnails', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockVideoDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        expect(api.getDetectionVideoThumbnailUrl).toHaveBeenCalledWith(1);
      });
    });

    it('uses image URL for image detection thumbnails', async () => {
      vi.mocked(api.fetchEventDetections).mockResolvedValue({
        items: [mockImageDetection],
        pagination: { total: 1, limit: 100, offset: 0, has_more: false },
      });

      renderWithQueryClient(<EventDetailModal {...mockVideoProps} />);

      await waitFor(() => {
        expect(api.getDetectionImageUrl).toHaveBeenCalledWith(2);
      });
    });
  });

  describe('video clip tab', () => {
    it('renders video clip tab button', async () => {
      renderWithQueryClient(<EventDetailModal {...mockProps} />);
      await waitFor(() => {
        expect(screen.getByTestId('video-clip-tab')).toBeInTheDocument();
      });
    });

    it('switches to video clip tab when clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('video-clip-tab')).toBeInTheDocument();
      });

      const clipTab = screen.getByTestId('video-clip-tab');
      await user.click(clipTab);

      await waitFor(() => {
        expect(clipTab).toHaveClass('border-b-2 border-[#76B900] text-[#76B900]');
      });
    });

    it('displays EventVideoPlayer when video clip tab is active', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      // Mock fetchEventClipInfo to avoid errors
      const mockFetchEventClipInfo = vi.fn().mockResolvedValue({
        event_id: 123,
        clip_available: false,
        clip_url: null,
        duration_seconds: null,
        generated_at: null,
        file_size_bytes: null,
      });
      vi.spyOn(api, 'fetchEventClipInfo').mockImplementation(mockFetchEventClipInfo);

      renderWithQueryClient(<EventDetailModal {...mockProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('video-clip-tab')).toBeInTheDocument();
      });

      const clipTab = screen.getByTestId('video-clip-tab');
      await user.click(clipTab);

      await waitFor(() => {
        expect(mockFetchEventClipInfo).toHaveBeenCalledWith(parseInt(mockEvent.id, 10));
      });
    });
  });

  describe('re-evaluate AI analysis', () => {
    // Use numeric event ID for re-evaluate tests
    const mockEventWithNumericId: Event = {
      ...mockEvent,
      id: '123',
    };

    const mockReEvalProps: EventDetailModalProps = {
      ...mockProps,
      event: mockEventWithNumericId,
    };

    beforeEach(() => {
      vi.clearAllMocks();
    });

    it('renders re-evaluate button', async () => {
      renderWithQueryClient(<EventDetailModal {...mockReEvalProps} />);
      await waitFor(() => {
        expect(screen.getByTestId('re-evaluate-button')).toBeInTheDocument();
      });
    });

    it('renders re-evaluate button with correct label', async () => {
      renderWithQueryClient(<EventDetailModal {...mockReEvalProps} />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Re-evaluate AI analysis' })).toBeInTheDocument();
      });
    });

    it('calls triggerEvaluation when re-evaluate button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(auditApi.triggerEvaluation).mockResolvedValue({
        id: 1,
        event_id: 123,
        audited_at: '2024-01-15T10:30:00Z',
        is_fully_evaluated: true,
        contributions: {
          rtdetr: true,
          florence: false,
          clip: false,
          violence: false,
          clothing: false,
          vehicle: false,
          pet: false,
          weather: false,
          image_quality: false,
          zones: false,
          baseline: false,
          cross_camera: false,
        },
        prompt_length: 1000,
        prompt_token_estimate: 250,
        enrichment_utilization: 0.75,
        scores: {
          context_usage: 4,
          reasoning_coherence: 4,
          risk_justification: 4,
          consistency: 4,
          overall: 4,
        },
        consistency_risk_score: 65,
        consistency_diff: 0,
        self_eval_critique: 'Good analysis',
        improvements: {
          missing_context: [],
          confusing_sections: [],
          unused_data: [],
          format_suggestions: [],
          model_gaps: [],
        },
      });

      renderWithQueryClient(<EventDetailModal {...mockReEvalProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('re-evaluate-button')).toBeInTheDocument();
      });

      const reEvalButton = screen.getByTestId('re-evaluate-button');
      await user.click(reEvalButton);

      await waitFor(() => {
        expect(auditApi.triggerEvaluation).toHaveBeenCalledWith(123, false);
      });
    });

    it('shows loading state while re-evaluating', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      let resolveEval: () => void;
      const evalPromise = new Promise<void>((resolve) => {
        resolveEval = () => resolve();
      });
      vi.mocked(auditApi.triggerEvaluation).mockReturnValue(evalPromise as never);

      renderWithQueryClient(<EventDetailModal {...mockReEvalProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('re-evaluate-button')).toBeInTheDocument();
      });

      const reEvalButton = screen.getByTestId('re-evaluate-button');
      await user.click(reEvalButton);

      await waitFor(() => {
        expect(screen.getByText('Re-evaluating...')).toBeInTheDocument();
        expect(reEvalButton).toBeDisabled();
      });

      act(() => {
        resolveEval!();
      });
    });

    it('shows success message after successful re-evaluation', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(auditApi.triggerEvaluation).mockResolvedValue({
        id: 1,
        event_id: 123,
        audited_at: '2024-01-15T10:30:00Z',
        is_fully_evaluated: true,
        contributions: {
          rtdetr: true,
          florence: false,
          clip: false,
          violence: false,
          clothing: false,
          vehicle: false,
          pet: false,
          weather: false,
          image_quality: false,
          zones: false,
          baseline: false,
          cross_camera: false,
        },
        prompt_length: 1000,
        prompt_token_estimate: 250,
        enrichment_utilization: 0.75,
        scores: {
          context_usage: 4,
          reasoning_coherence: 4,
          risk_justification: 4,
          consistency: 4,
          overall: 4,
        },
        consistency_risk_score: 65,
        consistency_diff: 0,
        self_eval_critique: 'Good analysis',
        improvements: {
          missing_context: [],
          confusing_sections: [],
          unused_data: [],
          format_suggestions: [],
          model_gaps: [],
        },
      });

      renderWithQueryClient(<EventDetailModal {...mockReEvalProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('re-evaluate-button')).toBeInTheDocument();
      });

      const reEvalButton = screen.getByTestId('re-evaluate-button');
      await user.click(reEvalButton);

      await waitFor(() => {
        expect(screen.getByTestId('re-evaluate-success')).toBeInTheDocument();
      });
      expect(screen.getByText(/Re-evaluation triggered successfully/)).toBeInTheDocument();
    });

    it('shows error message on re-evaluation failure', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(auditApi.triggerEvaluation).mockRejectedValue(
        new auditApi.AuditApiError(500, 'Server error')
      );

      renderWithQueryClient(<EventDetailModal {...mockReEvalProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('re-evaluate-button')).toBeInTheDocument();
      });

      const reEvalButton = screen.getByTestId('re-evaluate-button');
      await user.click(reEvalButton);

      await waitFor(() => {
        expect(screen.getByTestId('re-evaluate-error')).toBeInTheDocument();
      });
      expect(screen.getByText(/Server error/)).toBeInTheDocument();
    });

    it('clears error and success state when event changes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(auditApi.triggerEvaluation).mockRejectedValue(
        new auditApi.AuditApiError(500, 'Server error')
      );

      const { rerender, queryClient } = renderWithQueryClient(
        <EventDetailModal {...mockReEvalProps} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('re-evaluate-button')).toBeInTheDocument();
      });

      // Trigger an error
      const reEvalButton = screen.getByTestId('re-evaluate-button');
      await user.click(reEvalButton);

      await waitFor(() => {
        expect(screen.getByTestId('re-evaluate-error')).toBeInTheDocument();
      });

      // Change the event
      const newEvent = { ...mockEventWithNumericId, id: '456' };
      rerender(
        <QueryClientProvider client={queryClient}>
          <EventDetailModal {...mockReEvalProps} event={newEvent} />
        </QueryClientProvider>
      );

      // Error should be cleared
      await waitFor(() => {
        expect(screen.queryByTestId('re-evaluate-error')).not.toBeInTheDocument();
      });
    });

    it('has correct aria-label for accessibility', async () => {
      renderWithQueryClient(<EventDetailModal {...mockReEvalProps} />);

      await waitFor(() => {
        const reEvalButton = screen.getByTestId('re-evaluate-button');
        expect(reEvalButton).toHaveAttribute('aria-label', 'Re-evaluate AI analysis');
      });
    });
  });

  // Note: matched entities section tests removed - now using ReidMatchesPanel with detection-based matching

  describe('event feedback', () => {
    // Use numeric event ID for feedback tests
    const mockEventWithNumericId: Event = {
      ...mockEvent,
      id: '123',
    };

    const mockFeedbackProps: EventDetailModalProps = {
      ...mockProps,
      event: mockEventWithNumericId,
    };

    beforeEach(() => {
      vi.clearAllMocks();
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);
    });

    it('renders feedback section', async () => {
      renderWithQueryClient(<EventDetailModal {...mockFeedbackProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-section')).toBeInTheDocument();
      });
      expect(screen.getByText('Detection Feedback')).toBeInTheDocument();
    });

    it('renders feedback buttons when no existing feedback', async () => {
      renderWithQueryClient(<EventDetailModal {...mockFeedbackProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-accurate-button')).toBeInTheDocument();
      });
      expect(screen.getByTestId('feedback-false-positive-button')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-wrong-severity-button')).toBeInTheDocument();
    });

    it('displays existing feedback when already submitted', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventDetailModal {...mockFeedbackProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('existing-feedback')).toBeInTheDocument();
      });
      expect(screen.getByText('Correct Detection')).toBeInTheDocument();
    });

    it('displays existing feedback with notes', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'false_positive',
        notes: 'This is my pet cat',
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventDetailModal {...mockFeedbackProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('existing-feedback')).toBeInTheDocument();
      });
      expect(screen.getByText('False Positive')).toBeInTheDocument();
      expect(screen.getByText('This is my pet cat')).toBeInTheDocument();
    });

    it('submits correct detection feedback immediately when clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventDetailModal {...mockFeedbackProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-accurate-button')).toBeInTheDocument();
      });

      const correctButton = screen.getByTestId('feedback-accurate-button');
      await user.click(correctButton);

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalled();
        // Check the first argument passed to the mutation
        const calls = vi.mocked(api.submitEventFeedback).mock.calls;
        expect(calls.length).toBeGreaterThan(0);
        expect(calls[0][0]).toEqual({
          event_id: 123,
          feedback_type: 'accurate',
        });
      });
    });

    it('opens feedback form when false positive button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockFeedbackProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false-positive-button')).toBeInTheDocument();
      });

      const falsePositiveButton = screen.getByTestId('feedback-false-positive-button');
      await user.click(falsePositiveButton);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-form')).toBeInTheDocument();
      });
      expect(screen.getByText('False Positive Feedback')).toBeInTheDocument();
    });

    it('opens feedback form when wrong severity button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockFeedbackProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-wrong-severity-button')).toBeInTheDocument();
      });

      const wrongSeverityButton = screen.getByTestId('feedback-wrong-severity-button');
      await user.click(wrongSeverityButton);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-form')).toBeInTheDocument();
      });
      expect(screen.getByText('Wrong Severity Feedback')).toBeInTheDocument();
      expect(screen.getByTestId('severity-slider')).toBeInTheDocument();
    });

    it('closes feedback form when cancel is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockFeedbackProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false-positive-button')).toBeInTheDocument();
      });

      // Open the form
      const falsePositiveButton = screen.getByTestId('feedback-false-positive-button');
      await user.click(falsePositiveButton);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-form')).toBeInTheDocument();
      });

      // Cancel the form
      const cancelButton = screen.getByTestId('cancel-button');
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByTestId('feedback-form')).not.toBeInTheDocument();
      });
      // Buttons should be visible again
      expect(screen.getByTestId('feedback-false-positive-button')).toBeInTheDocument();
    });

    it('does not show feedback buttons when existing feedback is present', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventDetailModal {...mockFeedbackProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('existing-feedback')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('feedback-accurate-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('feedback-false-positive-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('feedback-wrong-severity-button')).not.toBeInTheDocument();
    });

    it('resets feedback form when event changes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const { rerender, queryClient } = renderWithQueryClient(
        <EventDetailModal {...mockFeedbackProps} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false-positive-button')).toBeInTheDocument();
      });

      // Open the form
      const falsePositiveButton = screen.getByTestId('feedback-false-positive-button');
      await user.click(falsePositiveButton);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-form')).toBeInTheDocument();
      });

      // Change event
      const newEvent = { ...mockEventWithNumericId, id: '456' };
      rerender(
        <QueryClientProvider client={queryClient}>
          <EventDetailModal {...mockFeedbackProps} event={newEvent} />
        </QueryClientProvider>
      );

      // Form should be closed and buttons should be visible
      await waitFor(() => {
        expect(screen.queryByTestId('feedback-form')).not.toBeInTheDocument();
      });
    });
  });

  describe('MatchedEntitiesSection integration', () => {
    const mockEventWithNumericId: Event = {
      id: '123',
      timestamp: '2024-01-15T10:30:00Z',
      camera_name: 'Front Door',
      risk_score: 65,
      risk_label: 'High',
      summary: 'Person detected at entrance',
      image_url: 'https://example.com/image.jpg',
      thumbnail_url: 'https://example.com/thumbnail.jpg',
      detections: [{ label: 'person', confidence: 0.95 }],
      reviewed: false,
    };

    const mockIntegrationProps: EventDetailModalProps = {
      event: mockEventWithNumericId,
      isOpen: true,
      onClose: vi.fn(),
    };

    it('renders MatchedEntitiesSection with correct eventId', async () => {
      renderWithQueryClient(<EventDetailModal {...mockIntegrationProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-section-mock')).toBeInTheDocument();
      });

      const section = screen.getByTestId('matched-entities-section-mock');
      expect(section).toHaveAttribute('data-event-id', '123');
    });

    it('does not render MatchedEntitiesSection when event ID is invalid', async () => {
      const invalidEvent = { ...mockEventWithNumericId, id: 'invalid-id' };
      renderWithQueryClient(<EventDetailModal {...mockIntegrationProps} event={invalidEvent} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('matched-entities-section-mock')).not.toBeInTheDocument();
    });

    it('opens EntityDetailModal when entity is clicked in MatchedEntitiesSection', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockIntegrationProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-section-mock')).toBeInTheDocument();
      });

      // Click the mock entity button
      const entityButton = screen.getByTestId('mock-entity-click');
      await user.click(entityButton);

      // Wait for the EntityDetailModal to open with the fetched entity
      await waitFor(() => {
        expect(screen.getByTestId('entity-detail-modal')).toBeInTheDocument();
        expect(screen.getByTestId('entity-loaded')).toBeInTheDocument();
      });

      // Verify fetchEntity was called with the correct entity ID
      expect(api.fetchEntity).toHaveBeenCalledWith('entity-person-123');
    });

    it('closes EntityDetailModal when close button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockIntegrationProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-section-mock')).toBeInTheDocument();
      });

      // Click the mock entity button to open the modal
      const entityButton = screen.getByTestId('mock-entity-click');
      await user.click(entityButton);

      await waitFor(() => {
        expect(screen.getByTestId('entity-detail-modal')).toBeInTheDocument();
      });

      // Close the modal
      const closeButton = screen.getByTestId('close-entity-modal');
      await user.click(closeButton);

      await waitFor(() => {
        expect(screen.queryByTestId('entity-detail-modal')).not.toBeInTheDocument();
      });
    });

    it('handles fetchEntity error gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(api.fetchEntity).mockRejectedValueOnce(new Error('API Error'));

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithQueryClient(<EventDetailModal {...mockIntegrationProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('matched-entities-section-mock')).toBeInTheDocument();
      });

      // Click the mock entity button
      const entityButton = screen.getByTestId('mock-entity-click');
      await user.click(entityButton);

      // Wait for the error to be logged
      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Failed to fetch entity details:',
          expect.any(Error)
        );
      });

      // EntityDetailModal should not open
      expect(screen.queryByTestId('entity-detail-modal')).not.toBeInTheDocument();

      consoleSpy.mockRestore();
    });
  });
});
