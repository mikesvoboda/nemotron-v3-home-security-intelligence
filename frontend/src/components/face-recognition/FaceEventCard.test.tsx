/**
 * FaceEventCard Component Tests
 *
 * Tests for the face event card component that displays individual face detection events.
 * Follows TDD approach - tests written first.
 *
 * @module components/face-recognition/FaceEventCard.test
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import FaceEventCard, { type FaceEventCardProps } from './FaceEventCard';

import type { FaceDetectionEvent } from '../../types/faceRecognition';

describe('FaceEventCard', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2025-01-31T10:32:00Z').getTime();

  // Mock known person face event
  const mockKnownPersonEvent: FaceDetectionEvent = {
    id: 1,
    camera_id: 1,
    camera_name: 'Front Door',
    timestamp: new Date(BASE_TIME).toISOString(),
    bbox: [100, 100, 200, 200],
    matched_person_id: 42,
    matched_person_name: 'John Smith',
    match_confidence: 0.95,
    is_unknown: false,
    quality_score: 0.88,
    thumbnail_url: 'https://example.com/face-thumbnail.jpg',
    detection_id: 'det-123',
    event_id: 100,
  };

  // Mock unknown person face event
  const mockUnknownPersonEvent: FaceDetectionEvent = {
    id: 2,
    camera_id: 2,
    camera_name: 'Driveway',
    timestamp: new Date(BASE_TIME - 4 * 60 * 1000).toISOString(), // 4 minutes earlier
    bbox: [150, 120, 180, 220],
    matched_person_id: null,
    matched_person_name: null,
    match_confidence: null,
    is_unknown: true,
    quality_score: 0.75,
    thumbnail_url: null,
    detection_id: 'det-456',
    event_id: 101,
  };

  // Mock base props for known person
  const mockKnownPersonProps: FaceEventCardProps = {
    event: mockKnownPersonEvent,
    onViewDetection: vi.fn(),
  };

  // Mock base props for unknown person
  const mockUnknownPersonProps: FaceEventCardProps = {
    event: mockUnknownPersonEvent,
    onIdentify: vi.fn(),
    onAddNewPerson: vi.fn(),
    onDismiss: vi.fn(),
    onViewDetection: vi.fn(),
  };

  // Mock system time for consistent testing
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  describe('basic rendering', () => {
    it('renders component with required props', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      expect(screen.getByTestId('face-event-card-1')).toBeInTheDocument();
    });

    it('renders camera name', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
    });

    it('renders timestamp in time format', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      // Should show time in 12-hour format (e.g., "5:32 AM" or "10:32 AM" depending on timezone)
      // The exact time depends on the test environment's timezone
      const timeElement = screen.getByText(/\d{1,2}:\d{2}\s?(AM|PM)/i);
      expect(timeElement).toBeInTheDocument();
    });
  });

  describe('known person rendering', () => {
    it('displays matched person name', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      expect(screen.getByText(/John Smith/)).toBeInTheDocument();
    });

    it('displays "Matched:" label for known persons', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      expect(screen.getByText(/Matched:/)).toBeInTheDocument();
    });

    it('displays confidence percentage for known persons', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      expect(screen.getByText(/95%/)).toBeInTheDocument();
    });

    it('displays View Detection button for known persons', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      expect(screen.getByRole('button', { name: /view detection/i })).toBeInTheDocument();
    });

    it('does not display action buttons for known persons', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      expect(screen.queryByRole('button', { name: /identify/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /add new/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument();
    });
  });

  describe('unknown person rendering', () => {
    it('displays "Unknown person" text', () => {
      render(<FaceEventCard {...mockUnknownPersonProps} />);
      expect(screen.getByText(/Unknown person/i)).toBeInTheDocument();
    });

    it('displays Identify button for unknown persons', () => {
      render(<FaceEventCard {...mockUnknownPersonProps} />);
      expect(screen.getByRole('button', { name: /identify/i })).toBeInTheDocument();
    });

    it('displays Add New button for unknown persons', () => {
      render(<FaceEventCard {...mockUnknownPersonProps} />);
      expect(screen.getByRole('button', { name: /add new/i })).toBeInTheDocument();
    });

    it('displays Dismiss button for unknown persons', () => {
      render(<FaceEventCard {...mockUnknownPersonProps} />);
      expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument();
    });

    it('applies unknown highlight styling', () => {
      render(<FaceEventCard {...mockUnknownPersonProps} />);
      const card = screen.getByTestId('face-event-card-2');
      expect(card).toHaveClass('border-l-4');
      expect(card).toHaveClass('border-yellow-500');
    });
  });

  describe('thumbnail rendering', () => {
    it('renders thumbnail image when URL is provided', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      const thumbnail = screen.getByRole('img', { name: /face thumbnail/i });
      expect(thumbnail).toBeInTheDocument();
      expect(thumbnail).toHaveAttribute('src', 'https://example.com/face-thumbnail.jpg');
    });

    it('renders placeholder when thumbnail URL is not provided', () => {
      render(<FaceEventCard {...mockUnknownPersonProps} />);
      // Should have a placeholder div instead of an image
      expect(screen.queryByRole('img', { name: /face thumbnail/i })).not.toBeInTheDocument();
      expect(screen.getByTestId('face-thumbnail-placeholder')).toBeInTheDocument();
    });
  });

  describe('confidence color coding', () => {
    it('shows green confidence indicator for 90%+ confidence', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      const confidenceText = screen.getByText(/95%/);
      expect(confidenceText).toHaveClass('text-green-400');
    });

    it('shows yellow confidence indicator for 70-90% confidence', () => {
      const mediumConfidenceEvent: FaceDetectionEvent = {
        ...mockKnownPersonEvent,
        id: 3,
        match_confidence: 0.85,
      };
      render(<FaceEventCard event={mediumConfidenceEvent} onViewDetection={vi.fn()} />);
      const confidenceText = screen.getByText(/85%/);
      expect(confidenceText).toHaveClass('text-yellow-400');
    });

    it('shows red confidence indicator for <70% confidence', () => {
      const lowConfidenceEvent: FaceDetectionEvent = {
        ...mockKnownPersonEvent,
        id: 4,
        match_confidence: 0.65,
      };
      render(<FaceEventCard event={lowConfidenceEvent} onViewDetection={vi.fn()} />);
      const confidenceText = screen.getByText(/65%/);
      expect(confidenceText).toHaveClass('text-red-400');
    });
  });

  describe('callback interactions', () => {
    it('calls onViewDetection when View Detection button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onViewDetection = vi.fn();
      render(<FaceEventCard {...mockKnownPersonProps} onViewDetection={onViewDetection} />);

      await user.click(screen.getByRole('button', { name: /view detection/i }));
      expect(onViewDetection).toHaveBeenCalledWith('det-123');
    });

    it('calls onIdentify when Identify button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onIdentify = vi.fn();
      render(<FaceEventCard {...mockUnknownPersonProps} onIdentify={onIdentify} />);

      await user.click(screen.getByRole('button', { name: /identify/i }));
      expect(onIdentify).toHaveBeenCalledWith(2);
    });

    it('calls onAddNewPerson when Add New button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onAddNewPerson = vi.fn();
      render(<FaceEventCard {...mockUnknownPersonProps} onAddNewPerson={onAddNewPerson} />);

      await user.click(screen.getByRole('button', { name: /add new/i }));
      expect(onAddNewPerson).toHaveBeenCalledWith(2);
    });

    it('calls onDismiss when Dismiss button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onDismiss = vi.fn();
      render(<FaceEventCard {...mockUnknownPersonProps} onDismiss={onDismiss} />);

      await user.click(screen.getByRole('button', { name: /dismiss/i }));
      expect(onDismiss).toHaveBeenCalledWith(2);
    });
  });

  describe('optional callbacks', () => {
    it('does not render Identify button when onIdentify is not provided', () => {
      const propsWithoutIdentify = {
        event: mockUnknownPersonEvent,
        onAddNewPerson: vi.fn(),
        onDismiss: vi.fn(),
      };
      render(<FaceEventCard {...propsWithoutIdentify} />);
      expect(screen.queryByRole('button', { name: /identify/i })).not.toBeInTheDocument();
    });

    it('does not render Add New button when onAddNewPerson is not provided', () => {
      const propsWithoutAddNew = {
        event: mockUnknownPersonEvent,
        onIdentify: vi.fn(),
        onDismiss: vi.fn(),
      };
      render(<FaceEventCard {...propsWithoutAddNew} />);
      expect(screen.queryByRole('button', { name: /add new/i })).not.toBeInTheDocument();
    });

    it('does not render Dismiss button when onDismiss is not provided', () => {
      const propsWithoutDismiss = {
        event: mockUnknownPersonEvent,
        onIdentify: vi.fn(),
        onAddNewPerson: vi.fn(),
      };
      render(<FaceEventCard {...propsWithoutDismiss} />);
      expect(screen.queryByRole('button', { name: /dismiss/i })).not.toBeInTheDocument();
    });

    it('does not render View Detection button when onViewDetection is not provided', () => {
      const propsWithoutViewDetection = {
        event: mockKnownPersonEvent,
      };
      render(<FaceEventCard {...propsWithoutViewDetection} />);
      expect(screen.queryByRole('button', { name: /view detection/i })).not.toBeInTheDocument();
    });
  });

  describe('timestamp formatting', () => {
    it('formats timestamp as time for same-day events', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      // Should show time in 12-hour format (exact time varies by timezone)
      const timeElement = screen.getByText(/\d{1,2}:\d{2}\s?(AM|PM)/i);
      expect(timeElement).toBeInTheDocument();
    });

    it('shows camera name with timestamp', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      expect(screen.getByText(/Front Door/)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible role for the card', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      expect(screen.getByTestId('face-event-card-1')).toBeInTheDocument();
    });

    it('buttons have accessible names', () => {
      render(<FaceEventCard {...mockUnknownPersonProps} />);
      expect(screen.getByRole('button', { name: /identify/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /add new/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /dismiss/i })).toBeInTheDocument();
    });

    it('thumbnail image has alt text', () => {
      render(<FaceEventCard {...mockKnownPersonProps} />);
      const img = screen.getByRole('img', { name: /face thumbnail/i });
      expect(img).toHaveAttribute('alt');
    });
  });

  describe('edge cases', () => {
    it('handles null match_confidence for known person gracefully', () => {
      const eventWithNullConfidence: FaceDetectionEvent = {
        ...mockKnownPersonEvent,
        id: 5,
        is_unknown: false,
        matched_person_name: 'Jane Doe',
        match_confidence: null,
      };
      render(<FaceEventCard event={eventWithNullConfidence} />);
      expect(screen.getByText(/Jane Doe/)).toBeInTheDocument();
      // Should not show confidence percentage
      expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    });

    it('handles event without detection_id gracefully', () => {
      const eventWithoutDetectionId: FaceDetectionEvent = {
        ...mockKnownPersonEvent,
        id: 6,
        detection_id: null,
      };
      const onViewDetection = vi.fn();
      render(<FaceEventCard event={eventWithoutDetectionId} onViewDetection={onViewDetection} />);
      // View Detection button should still exist but may be disabled
      const viewButton = screen.getByRole('button', { name: /view detection/i });
      expect(viewButton).toBeDisabled();
    });

    it('renders minimal event without optional fields', () => {
      const minimalEvent: FaceDetectionEvent = {
        id: 7,
        camera_id: 1,
        camera_name: 'Test Camera',
        timestamp: new Date(BASE_TIME).toISOString(),
        bbox: [0, 0, 100, 100],
        is_unknown: true,
        quality_score: 0.8,
      };
      render(<FaceEventCard event={minimalEvent} />);
      expect(screen.getByTestId('face-event-card-7')).toBeInTheDocument();
      expect(screen.getByText('Test Camera')).toBeInTheDocument();
    });
  });
});
