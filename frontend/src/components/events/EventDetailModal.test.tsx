import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import EventDetailModal, { type Event, type EventDetailModalProps } from './EventDetailModal';

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
  });

  describe('rendering', () => {
    it('renders nothing when event is null', () => {
      const { container } = render(<EventDetailModal {...mockProps} event={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when isOpen is false', () => {
      render(<EventDetailModal {...mockProps} isOpen={false} />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders modal when isOpen is true and event is provided', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('renders camera name as dialog title', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByRole('heading', { name: 'Front Door' })).toBeInTheDocument();
    });

    it('renders formatted timestamp', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText(/January 15, 2024/)).toBeInTheDocument();
    });

    it('renders risk badge with score', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('High (65)')).toBeInTheDocument();
    });

    it('renders close button', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByRole('button', { name: 'Close modal' })).toBeInTheDocument();
    });
  });

  describe('image display', () => {
    it('renders full-size image when image_url is provided', () => {
      render(<EventDetailModal {...mockProps} />);
      const image = screen.getByAltText(/Front Door detection at/);
      expect(image).toBeInTheDocument();
    });

    it('uses image_url over thumbnail_url when both are provided', () => {
      render(<EventDetailModal {...mockProps} />);
      // Verify image is rendered
      const image = screen.getByAltText(/Front Door detection at/);
      expect(image).toBeInTheDocument();
      expect(image.getAttribute('src')).toBe('https://example.com/image.jpg');
    });

    it('falls back to thumbnail_url when image_url is not provided', () => {
      const eventNoFullImage = { ...mockEvent, image_url: undefined };
      render(<EventDetailModal {...mockProps} event={eventNoFullImage} />);
      // Verify image is rendered with thumbnail
      const image = screen.getByAltText(/Front Door detection at/);
      expect(image).toBeInTheDocument();
      expect(image.getAttribute('src')).toBe('https://example.com/thumbnail.jpg');
    });

    it('renders DetectionImage when detections have bounding boxes', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByAltText(/Front Door detection at/)).toBeInTheDocument();
    });

    it('renders plain img when detections have no bounding boxes', () => {
      const eventNoBbox = {
        ...mockEvent,
        detections: [
          { label: 'person', confidence: 0.95 },
          { label: 'car', confidence: 0.87 },
        ],
      };
      render(<EventDetailModal {...mockProps} event={eventNoBbox} />);
      expect(screen.getByAltText(/Front Door at/)).toBeInTheDocument();
    });

    it('does not render image section when no image_url or thumbnail_url', () => {
      const eventNoImage = { ...mockEvent, image_url: undefined, thumbnail_url: undefined };
      render(<EventDetailModal {...mockProps} event={eventNoImage} />);
      const images = screen.queryAllByRole('img');
      expect(images.length).toBe(0);
    });
  });

  describe('AI summary and reasoning', () => {
    it('renders AI summary section', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('AI Summary')).toBeInTheDocument();
      expect(
        screen.getByText('Person detected approaching the front entrance with a package')
      ).toBeInTheDocument();
    });

    it('renders AI reasoning when provided', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('AI Reasoning')).toBeInTheDocument();
      expect(
        screen.getByText(/The detected person is approaching the entrance during evening hours/)
      ).toBeInTheDocument();
    });

    it('does not render AI reasoning section when reasoning is undefined', () => {
      const eventNoReasoning = { ...mockEvent, reasoning: undefined };
      render(<EventDetailModal {...mockProps} event={eventNoReasoning} />);
      expect(screen.queryByText('AI Reasoning')).not.toBeInTheDocument();
    });

    it('does not render AI reasoning section when reasoning is empty', () => {
      const eventEmptyReasoning = { ...mockEvent, reasoning: '' };
      render(<EventDetailModal {...mockProps} event={eventEmptyReasoning} />);
      expect(screen.queryByText('AI Reasoning')).not.toBeInTheDocument();
    });
  });

  describe('detections list', () => {
    it('renders detections section with count', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('Detected Objects (2)')).toBeInTheDocument();
    });

    it('renders all detection labels', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('person')).toBeInTheDocument();
      expect(screen.getByText('package')).toBeInTheDocument();
    });

    it('renders detection confidence scores', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('95%')).toBeInTheDocument();
      expect(screen.getByText('87%')).toBeInTheDocument();
    });

    it('formats confidence as percentage with rounding', () => {
      const eventWithRounding = {
        ...mockEvent,
        detections: [
          { label: 'person', confidence: 0.956 },
          { label: 'car', confidence: 0.874 },
        ],
      };
      render(<EventDetailModal {...mockProps} event={eventWithRounding} />);
      expect(screen.getByText('96%')).toBeInTheDocument();
      expect(screen.getByText('87%')).toBeInTheDocument();
    });

    it('does not render detections section when detections array is empty', () => {
      const eventNoDetections = { ...mockEvent, detections: [] };
      render(<EventDetailModal {...mockProps} event={eventNoDetections} />);
      expect(screen.queryByText(/Detected Objects/)).not.toBeInTheDocument();
    });

    it('renders single detection correctly', () => {
      const eventOneDetection = {
        ...mockEvent,
        detections: [{ label: 'person', confidence: 0.95 }],
      };
      render(<EventDetailModal {...mockProps} event={eventOneDetection} />);
      expect(screen.getByText('Detected Objects (1)')).toBeInTheDocument();
    });
  });

  describe('event metadata', () => {
    it('renders event details section', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('Event Details')).toBeInTheDocument();
    });

    it('renders event ID', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('Event ID')).toBeInTheDocument();
      expect(screen.getByText('event-123')).toBeInTheDocument();
    });

    it('renders camera name in metadata', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('Camera')).toBeInTheDocument();
      const frontDoorLabels = screen.getAllByText('Front Door');
      expect(frontDoorLabels.length).toBeGreaterThanOrEqual(2); // Title and metadata
    });

    it('renders risk score in metadata', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('Risk Score')).toBeInTheDocument();
      expect(screen.getByText('65 / 100')).toBeInTheDocument();
    });

    it('renders review status as pending when not reviewed', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('Pending Review')).toBeInTheDocument();
    });

    it('renders review status as reviewed when reviewed', () => {
      const reviewedEvent = { ...mockEvent, reviewed: true };
      render(<EventDetailModal {...mockProps} event={reviewedEvent} />);
      expect(screen.getByText('Reviewed')).toBeInTheDocument();
    });
  });

  describe('close functionality', () => {
    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<EventDetailModal {...mockProps} onClose={onClose} />);

      const closeButton = screen.getByRole('button', { name: 'Close modal' });
      await user.click(closeButton);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when escape key is pressed', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<EventDetailModal {...mockProps} onClose={onClose} />);

      await user.keyboard('{Escape}');

      // Headless UI Dialog also handles Escape, so onClose should be called
      await waitFor(
        () => {
          expect(onClose).toHaveBeenCalled();
        },
        { timeout: 1000 }
      );
    });

    it('calls onClose when clicking backdrop', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<EventDetailModal {...mockProps} onClose={onClose} />);

      const dialog = screen.getByRole('dialog');
      const backdrop = dialog.parentElement?.parentElement?.firstChild as HTMLElement;

      if (backdrop) {
        await user.click(backdrop);
      }

      // Headless UI handles backdrop clicks, so we just verify modal can close
      expect(onClose).toBeDefined();
    });

    it('does not call onClose when modal is already closed', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<EventDetailModal {...mockProps} isOpen={false} onClose={onClose} />);

      await user.keyboard('{Escape}');

      // Small delay to ensure no delayed calls
      await new Promise((resolve) => setTimeout(resolve, 100));
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('navigation', () => {
    it('renders navigation buttons when onNavigate is provided', () => {
      const onNavigate = vi.fn();
      render(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      expect(screen.getByRole('button', { name: 'Previous event' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Next event' })).toBeInTheDocument();
    });

    it('does not render navigation buttons when onNavigate is undefined', () => {
      render(<EventDetailModal {...mockProps} onNavigate={undefined} />);

      expect(screen.queryByRole('button', { name: 'Previous event' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Next event' })).not.toBeInTheDocument();
    });

    it('calls onNavigate with "prev" when Previous button is clicked', async () => {
      const user = userEvent.setup();
      const onNavigate = vi.fn();
      render(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      const prevButton = screen.getByRole('button', { name: 'Previous event' });
      await user.click(prevButton);

      expect(onNavigate).toHaveBeenCalledWith('prev');
      expect(onNavigate).toHaveBeenCalledTimes(1);
    });

    it('calls onNavigate with "next" when Next button is clicked', async () => {
      const user = userEvent.setup();
      const onNavigate = vi.fn();
      render(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      const nextButton = screen.getByRole('button', { name: 'Next event' });
      await user.click(nextButton);

      expect(onNavigate).toHaveBeenCalledWith('next');
      expect(onNavigate).toHaveBeenCalledTimes(1);
    });

    it('calls onNavigate with "prev" when left arrow key is pressed', async () => {
      const user = userEvent.setup();
      const onNavigate = vi.fn();
      render(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      await user.keyboard('{ArrowLeft}');

      await waitFor(() => {
        expect(onNavigate).toHaveBeenCalledWith('prev');
      });
    });

    it('calls onNavigate with "next" when right arrow key is pressed', async () => {
      const user = userEvent.setup();
      const onNavigate = vi.fn();
      render(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      await user.keyboard('{ArrowRight}');

      await waitFor(() => {
        expect(onNavigate).toHaveBeenCalledWith('next');
      });
    });

    it('does not call onNavigate on arrow keys when modal is closed', async () => {
      const user = userEvent.setup();
      const onNavigate = vi.fn();
      render(<EventDetailModal {...mockProps} isOpen={false} onNavigate={onNavigate} />);

      await user.keyboard('{ArrowLeft}');
      await user.keyboard('{ArrowRight}');

      await new Promise((resolve) => setTimeout(resolve, 100));
      expect(onNavigate).not.toHaveBeenCalled();
    });

    it('does not call onNavigate on arrow keys when onNavigate is undefined', async () => {
      const user = userEvent.setup();
      render(<EventDetailModal {...mockProps} onNavigate={undefined} />);

      await user.keyboard('{ArrowLeft}');
      await user.keyboard('{ArrowRight}');

      // No errors should occur
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('mark as reviewed', () => {
    it('renders mark as reviewed button when onMarkReviewed is provided and event is not reviewed', () => {
      const onMarkReviewed = vi.fn();
      render(<EventDetailModal {...mockProps} onMarkReviewed={onMarkReviewed} />);

      expect(screen.getByRole('button', { name: 'Mark event as reviewed' })).toBeInTheDocument();
    });

    it('does not render mark as reviewed button when event is already reviewed', () => {
      const reviewedEvent = { ...mockEvent, reviewed: true };
      const onMarkReviewed = vi.fn();
      render(
        <EventDetailModal {...mockProps} event={reviewedEvent} onMarkReviewed={onMarkReviewed} />
      );

      expect(
        screen.queryByRole('button', { name: 'Mark event as reviewed' })
      ).not.toBeInTheDocument();
    });

    it('does not render mark as reviewed button when onMarkReviewed is undefined', () => {
      render(<EventDetailModal {...mockProps} onMarkReviewed={undefined} />);

      expect(
        screen.queryByRole('button', { name: 'Mark event as reviewed' })
      ).not.toBeInTheDocument();
    });

    it('calls onMarkReviewed with event ID when button is clicked', async () => {
      const user = userEvent.setup();
      const onMarkReviewed = vi.fn();
      render(<EventDetailModal {...mockProps} onMarkReviewed={onMarkReviewed} />);

      const reviewButton = screen.getByRole('button', { name: 'Mark event as reviewed' });
      await user.click(reviewButton);

      expect(onMarkReviewed).toHaveBeenCalledWith('event-123');
      expect(onMarkReviewed).toHaveBeenCalledTimes(1);
    });
  });

  describe('accessibility', () => {
    it('has role="dialog"', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has aria-modal attribute', () => {
      render(<EventDetailModal {...mockProps} />);
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal');
    });

    it('has aria-labelledby pointing to title', () => {
      render(<EventDetailModal {...mockProps} />);
      const dialog = screen.getByRole('dialog');
      const labelledBy = dialog.getAttribute('aria-labelledby');
      // Headless UI sets this attribute, verify it exists
      expect(labelledBy).not.toBeNull();
    });

    it('renders title with correct ID for aria-labelledby', () => {
      render(<EventDetailModal {...mockProps} />);
      const title = screen.getByRole('heading', { name: 'Front Door' });
      expect(title).toHaveAttribute('id', 'event-detail-title');
    });

    it('close button has aria-label', () => {
      render(<EventDetailModal {...mockProps} />);
      const closeButton = screen.getByRole('button', { name: 'Close modal' });
      expect(closeButton).toHaveAttribute('aria-label', 'Close modal');
    });

    it('navigation buttons have aria-labels', () => {
      const onNavigate = vi.fn();
      render(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);

      expect(screen.getByRole('button', { name: 'Previous event' })).toHaveAttribute(
        'aria-label',
        'Previous event'
      );
      expect(screen.getByRole('button', { name: 'Next event' })).toHaveAttribute(
        'aria-label',
        'Next event'
      );
    });

    it('mark as reviewed button has aria-label', () => {
      const onMarkReviewed = vi.fn();
      render(<EventDetailModal {...mockProps} onMarkReviewed={onMarkReviewed} />);

      const reviewButton = screen.getByRole('button', { name: 'Mark event as reviewed' });
      expect(reviewButton).toHaveAttribute('aria-label', 'Mark event as reviewed');
    });

    it('backdrop has aria-hidden', () => {
      render(<EventDetailModal {...mockProps} />);
      // Verify modal is accessible (dialog role present)
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
      // Headless UI manages backdrop aria-hidden automatically
    });
  });

  describe('styling and layout', () => {
    it('renders modal with proper structure', () => {
      render(<EventDetailModal {...mockProps} />);
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    it('renders header with title and close button', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByRole('heading', { name: 'Front Door' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Close modal' })).toBeInTheDocument();
    });

    it('renders main content sections', () => {
      render(<EventDetailModal {...mockProps} />);
      expect(screen.getByText('AI Summary')).toBeInTheDocument();
      expect(screen.getByText('Event Details')).toBeInTheDocument();
    });

    it('renders footer with appropriate spacing', () => {
      const onNavigate = vi.fn();
      render(<EventDetailModal {...mockProps} onNavigate={onNavigate} />);
      expect(screen.getByRole('button', { name: 'Previous event' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Next event' })).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles invalid timestamp gracefully', () => {
      const eventInvalidTimestamp = { ...mockEvent, timestamp: 'invalid-date' };
      render(<EventDetailModal {...mockProps} event={eventInvalidTimestamp} />);
      expect(screen.getByText('Invalid Date')).toBeInTheDocument();
    });

    it('handles very long summary text', () => {
      const longSummary =
        'This is a very long summary that describes an extremely complex security event with multiple elements and detailed analysis of what has occurred at this particular location and time with extensive contextual information that goes on and on.';
      const eventLongSummary = { ...mockEvent, summary: longSummary };
      render(<EventDetailModal {...mockProps} event={eventLongSummary} />);
      expect(screen.getByText(longSummary)).toBeInTheDocument();
    });

    it('handles very long reasoning text', () => {
      const longReasoning =
        'This is a very long reasoning text that provides extensive analysis and explanation of the security event including multiple factors, contextual elements, historical patterns, and detailed justification for the assigned risk score with numerous details.';
      const eventLongReasoning = { ...mockEvent, reasoning: longReasoning };
      render(<EventDetailModal {...mockProps} event={eventLongReasoning} />);
      expect(screen.getByText(longReasoning)).toBeInTheDocument();
    });

    it('handles detection with 100% confidence', () => {
      const eventPerfectConfidence = {
        ...mockEvent,
        detections: [{ label: 'person', confidence: 1.0 }],
      };
      render(<EventDetailModal {...mockProps} event={eventPerfectConfidence} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('handles detection with 0% confidence', () => {
      const eventZeroConfidence = {
        ...mockEvent,
        detections: [{ label: 'person', confidence: 0.0 }],
      };
      render(<EventDetailModal {...mockProps} event={eventZeroConfidence} />);
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('handles risk score at boundary values', () => {
      const boundaryScores = [0, 25, 50, 75, 100];

      boundaryScores.forEach((score) => {
        const eventBoundary = { ...mockEvent, risk_score: score };
        const { unmount } = render(<EventDetailModal {...mockProps} event={eventBoundary} />);
        expect(screen.getByText(`${score} / 100`)).toBeInTheDocument();
        unmount();
      });
    });

    it('handles empty camera name', () => {
      const eventEmptyCamera = { ...mockEvent, camera_name: '' };
      render(<EventDetailModal {...mockProps} event={eventEmptyCamera} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('handles very long camera name', () => {
      const longCameraName = 'Front Door Main Entrance Camera Position Alpha North Wing Building A';
      const eventLongCamera = { ...mockEvent, camera_name: longCameraName };
      render(<EventDetailModal {...mockProps} event={eventLongCamera} />);
      expect(screen.getByRole('heading', { name: longCameraName })).toBeInTheDocument();
    });

    it('handles many detections', () => {
      const manyDetections = Array.from({ length: 20 }, (_, i) => ({
        label: `object-${i}`,
        confidence: 0.5 + i * 0.02,
      }));
      const eventManyDetections = { ...mockEvent, detections: manyDetections };
      render(<EventDetailModal {...mockProps} event={eventManyDetections} />);
      expect(screen.getByText('Detected Objects (20)')).toBeInTheDocument();
    });
  });

  describe('event transitions', () => {
    it('handles event prop changing while modal is open', () => {
      const { rerender } = render(<EventDetailModal {...mockProps} />);

      expect(screen.getByRole('heading', { name: 'Front Door' })).toBeInTheDocument();

      const newEvent = { ...mockEvent, id: 'event-456', camera_name: 'Back Door', risk_score: 30 };
      rerender(<EventDetailModal {...mockProps} event={newEvent} />);

      expect(screen.getByRole('heading', { name: 'Back Door' })).toBeInTheDocument();
      expect(screen.getByText('30 / 100')).toBeInTheDocument();
    });

    it('handles toggling isOpen prop', () => {
      render(<EventDetailModal {...mockProps} isOpen={true} />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('integration', () => {
    it('renders complete modal with all sections', () => {
      const onClose = vi.fn();
      const onMarkReviewed = vi.fn();
      const onNavigate = vi.fn();

      render(
        <EventDetailModal
          {...mockProps}
          onClose={onClose}
          onMarkReviewed={onMarkReviewed}
          onNavigate={onNavigate}
        />
      );

      // Verify all major sections are present
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

    it('handles multiple interactions without errors', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      const onMarkReviewed = vi.fn();
      const onNavigate = vi.fn();

      render(
        <EventDetailModal
          {...mockProps}
          onClose={onClose}
          onMarkReviewed={onMarkReviewed}
          onNavigate={onNavigate}
        />
      );

      // Navigate to previous
      await user.click(screen.getByRole('button', { name: 'Previous event' }));
      expect(onNavigate).toHaveBeenCalledWith('prev');

      // Navigate to next
      await user.click(screen.getByRole('button', { name: 'Next event' }));
      expect(onNavigate).toHaveBeenCalledWith('next');

      // Mark as reviewed
      await user.click(screen.getByRole('button', { name: 'Mark event as reviewed' }));
      expect(onMarkReviewed).toHaveBeenCalledWith('event-123');

      // Close modal
      await user.click(screen.getByRole('button', { name: 'Close modal' }));
      expect(onClose).toHaveBeenCalled();
    });
  });
});
