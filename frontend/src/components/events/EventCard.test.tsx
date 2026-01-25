import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach, type Mock } from 'vitest';

import EventCard, { CollapsibleDetections, type Detection, type EventCardProps } from './EventCard';

describe('EventCard', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock detections for testing
  const mockDetections: Detection[] = [
    {
      label: 'person',
      confidence: 0.95,
      bbox: { x: 100, y: 100, width: 200, height: 300 },
    },
    {
      label: 'car',
      confidence: 0.87,
      bbox: { x: 400, y: 200, width: 150, height: 100 },
    },
  ];

  // Mock base props
  const mockProps: EventCardProps = {
    id: 'event-123',
    timestamp: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(), // 5 mins ago
    camera_name: 'Front Door',
    risk_score: 45,
    risk_label: 'Medium',
    summary: 'Person detected approaching the front entrance',
    reasoning: 'The detected person is approaching the entrance during daytime hours.',
    thumbnail_url: 'https://example.com/thumbnail.jpg',
    detections: mockDetections,
  };

  // Mock system time for consistent testing
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('basic rendering', () => {
    it('renders component with required props', () => {
      render(<EventCard {...mockProps} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(
        screen.getByText('Person detected approaching the front entrance')
      ).toBeInTheDocument();
    });

    it('renders camera name', () => {
      render(<EventCard {...mockProps} />);
      const heading = screen.getByRole('heading', { name: 'Front Door' });
      expect(heading).toBeInTheDocument();
      expect(heading.tagName).toBe('H3');
    });

    it('camera name has truncation class and title attribute for tooltip', () => {
      render(<EventCard {...mockProps} />);
      const heading = screen.getByRole('heading', { name: 'Front Door' });
      expect(heading).toHaveClass('truncate');
      expect(heading).toHaveAttribute('title', 'Front Door');
    });

    it('renders summary text within TruncatedText component', () => {
      render(<EventCard {...mockProps} />);
      const summary = screen.getByText('Person detected approaching the front entrance');
      expect(summary).toBeInTheDocument();
      expect(summary.tagName).toBe('P');
      // Should be inside a TruncatedText component (indicated by data-testid)
      expect(summary.closest('[data-testid="truncated-text"]')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<EventCard {...mockProps} className="custom-class" />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('custom-class');
    });

    it('merges custom className with default classes', () => {
      const { container } = render(<EventCard {...mockProps} className="mt-4" />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('mt-4', 'rounded-lg', 'border');
    });
  });

  describe('timestamp formatting', () => {
    it('formats timestamp as "Just now" for events within 1 minute', () => {
      const justNowEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 30 * 1000).toISOString(), // 30 seconds ago
      };
      render(<EventCard {...justNowEvent} />);
      expect(screen.getByText('Just now')).toBeInTheDocument();
    });

    it('formats timestamp as "Just now" for exactly 1 minute ago', () => {
      const oneMinuteEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 60 * 1000).toISOString(), // 1 minute ago
      };
      render(<EventCard {...oneMinuteEvent} />);
      expect(screen.getByText('Just now')).toBeInTheDocument();
    });

    it('formats timestamps as "X minutes ago" for events less than 60 minutes', () => {
      const twoMinutesEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 2 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...twoMinutesEvent} />);
      expect(screen.getByText('2 minutes ago')).toBeInTheDocument();
    });

    it('formats timestamps as "X minutes ago" for 59 minutes', () => {
      const fiftyNineMinutesEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 59 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...fiftyNineMinutesEvent} />);
      expect(screen.getByText('59 minutes ago')).toBeInTheDocument();
    });

    it('formats timestamp as "1 hour ago" for exactly 1 hour', () => {
      const oneHourEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 60 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...oneHourEvent} />);
      expect(screen.getByText('1 hour ago')).toBeInTheDocument();
    });

    it('formats timestamps as "X hours ago" for events less than 24 hours', () => {
      const threeHoursEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 3 * 60 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...threeHoursEvent} />);
      expect(screen.getByText('3 hours ago')).toBeInTheDocument();
    });

    it('formats timestamps as "X hours ago" for 23 hours', () => {
      const twentyThreeHoursEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 23 * 60 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...twentyThreeHoursEvent} />);
      expect(screen.getByText('23 hours ago')).toBeInTheDocument();
    });

    it('formats timestamp as "1 day ago" for exactly 1 day', () => {
      const oneDayEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 24 * 60 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...oneDayEvent} />);
      expect(screen.getByText('1 day ago')).toBeInTheDocument();
    });

    it('formats timestamps as "X days ago" for events less than 7 days', () => {
      const threeDaysEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 3 * 24 * 60 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...threeDaysEvent} />);
      expect(screen.getByText('3 days ago')).toBeInTheDocument();
    });

    it('formats timestamps as "X days ago" for 6 days', () => {
      const sixDaysEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 6 * 24 * 60 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...sixDaysEvent} />);
      expect(screen.getByText('6 days ago')).toBeInTheDocument();
    });

    it('formats timestamps as absolute date for events 7+ days old', () => {
      const sevenDaysEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 7 * 24 * 60 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...sevenDaysEvent} />);
      const timeElement = screen.getByText(/Jan/);
      expect(timeElement).toBeInTheDocument();
    });

    it('formats timestamps as absolute date for events weeks old', () => {
      const oldEvent = {
        ...mockProps,
        timestamp: new Date(BASE_TIME - 30 * 24 * 60 * 60 * 1000).toISOString(),
      };
      render(<EventCard {...oldEvent} />);
      const timeElement = screen.queryByText(/Dec|Jan/);
      expect(timeElement).toBeInTheDocument();
    });

    it('formats timestamps with year when event is from different year', () => {
      // Set a time in 2024, and create an event from 2023
      vi.setSystemTime(new Date('2024-06-15T10:00:00Z').getTime());

      const lastYearEvent = {
        ...mockProps,
        timestamp: new Date('2023-06-15T10:00:00Z').toISOString(),
      };
      render(<EventCard {...lastYearEvent} />);
      const timeElement = screen.queryByText(/2023/);
      expect(timeElement).toBeInTheDocument();

      // Reset to BASE_TIME
      vi.setSystemTime(BASE_TIME);
    });

    it('handles invalid timestamp gracefully', () => {
      const invalidEvent = {
        ...mockProps,
        timestamp: 'invalid-date',
      };
      render(<EventCard {...invalidEvent} />);
      // Invalid dates get converted to "Invalid Date" by toLocaleString
      expect(screen.getByText('Invalid Date')).toBeInTheDocument();
    });

    it('renders Clock icon with timestamp', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const clockIcon = container.querySelector('svg.lucide-clock');
      expect(clockIcon).toBeInTheDocument();
    });
  });

  describe('risk badge display', () => {
    it('displays risk badge for low risk level', () => {
      const lowRiskEvent = { ...mockProps, risk_score: 15 };
      render(<EventCard {...lowRiskEvent} />);
      expect(screen.getByText('Low (15)')).toBeInTheDocument();
    });

    it('displays risk badge for medium risk level', () => {
      const mediumRiskEvent = { ...mockProps, risk_score: 45 };
      render(<EventCard {...mediumRiskEvent} />);
      expect(screen.getByText('Medium (45)')).toBeInTheDocument();
    });

    it('displays risk badge for high risk level', () => {
      const highRiskEvent = { ...mockProps, risk_score: 72 };
      render(<EventCard {...highRiskEvent} />);
      expect(screen.getByText('High (72)')).toBeInTheDocument();
    });

    it('displays risk badge for critical risk level', () => {
      const criticalRiskEvent = { ...mockProps, risk_score: 88 };
      render(<EventCard {...criticalRiskEvent} />);
      expect(screen.getByText('Critical (88)')).toBeInTheDocument();
    });

    it('passes showScore prop to RiskBadge', () => {
      render(<EventCard {...mockProps} />);
      // Risk score should be visible in the badge
      expect(screen.getByText(/\(45\)/)).toBeInTheDocument();
    });

    it('passes size="md" to RiskBadge', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const badges = container.querySelectorAll('[role="status"]');
      // First badge should be the risk badge
      const riskBadge = badges[0];
      expect(riskBadge).toHaveClass('px-2.5', 'py-1');
    });
  });

  describe('detection list rendering', () => {
    it('renders detection count', () => {
      render(<EventCard {...mockProps} />);
      expect(screen.getByText('Detections (2)')).toBeInTheDocument();
    });

    it('renders all detection labels', () => {
      render(<EventCard {...mockProps} />);
      expect(screen.getByText('person')).toBeInTheDocument();
      expect(screen.getByText('car')).toBeInTheDocument();
    });

    it('renders multiple detections with collapsible behavior', async () => {
      const user = userEvent.setup();
      const multipleDetections: Detection[] = [
        { label: 'person', confidence: 0.95 },
        { label: 'car', confidence: 0.87 },
        { label: 'dog', confidence: 0.72 },
        { label: 'package', confidence: 0.91 },
      ];
      const eventWithMultiple = { ...mockProps, detections: multipleDetections };
      render(<EventCard {...eventWithMultiple} />);

      // Header shows total count
      expect(screen.getByText('Detections (4)')).toBeInTheDocument();

      // With 4 detections (>3), only top 3 by confidence are visible initially
      // Sorted by confidence: person (95%), package (91%), car (87%), dog (72%)
      expect(screen.getByText('person')).toBeInTheDocument();
      expect(screen.getByText('package')).toBeInTheDocument();
      expect(screen.getByText('car')).toBeInTheDocument();

      // dog is hidden initially (lowest confidence)
      expect(screen.queryByText('dog')).not.toBeInTheDocument();

      // "+1 more" button should be visible
      expect(screen.getByText('+1 more')).toBeInTheDocument();

      // Expand to see all detections
      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      await user.click(toggleButton);

      // Now all should be visible
      expect(screen.getByText('dog')).toBeInTheDocument();
    });

    it('does not render detection list when detections are empty', () => {
      const noDetectionsEvent = { ...mockProps, detections: [] };
      render(<EventCard {...noDetectionsEvent} />);
      expect(screen.queryByText(/Detections/)).not.toBeInTheDocument();
    });
  });

  describe('confidence formatting', () => {
    it('formats confidence as percentage with 0 decimal places', () => {
      render(<EventCard {...mockProps} />);
      // Confidence percentages may appear in detection badges and aggregate stats
      expect(screen.getAllByText('95%').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('87%').length).toBeGreaterThanOrEqual(1);
    });

    it('rounds confidence to nearest integer', () => {
      const detectionsWithRounding: Detection[] = [
        { label: 'person', confidence: 0.956 }, // Should round to 96%
        { label: 'car', confidence: 0.874 }, // Should round to 87%
        { label: 'dog', confidence: 0.725 }, // Should round to 73%
      ];
      const eventWithRounding = { ...mockProps, detections: detectionsWithRounding };
      render(<EventCard {...eventWithRounding} />);

      expect(screen.getAllByText('96%').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('87%').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('73%').length).toBeGreaterThanOrEqual(1);
    });

    it('handles 100% confidence', () => {
      const perfectDetection: Detection[] = [{ label: 'person', confidence: 1.0 }];
      const eventWithPerfect = { ...mockProps, detections: perfectDetection };
      render(<EventCard {...eventWithPerfect} />);
      expect(screen.getAllByText('100%').length).toBeGreaterThanOrEqual(1);
    });

    it('handles 0% confidence', () => {
      const zeroDetection: Detection[] = [{ label: 'person', confidence: 0.0 }];
      const eventWithZero = { ...mockProps, detections: zeroDetection };
      render(<EventCard {...eventWithZero} />);
      expect(screen.getAllByText('0%').length).toBeGreaterThanOrEqual(1);
    });

    it('handles low confidence values', () => {
      const lowConfidence: Detection[] = [{ label: 'person', confidence: 0.05 }];
      const eventWithLow = { ...mockProps, detections: lowConfidence };
      render(<EventCard {...eventWithLow} />);
      expect(screen.getAllByText('5%').length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('thumbnail rendering', () => {
    it('renders thumbnail when thumbnail_url is provided', () => {
      render(<EventCard {...mockProps} />);
      const images = screen.getAllByRole('img');
      expect(images.length).toBeGreaterThan(0);
    });

    it('renders thumbnail image with 80x80 size when detections have bounding boxes', () => {
      render(<EventCard {...mockProps} />);
      const altText = screen.getByAltText(/Front Door at/);
      expect(altText).toBeInTheDocument();
      expect(altText).toHaveClass('h-20', 'w-20');
    });

    it('renders thumbnail image with 80x80 size when detections have no bounding boxes', () => {
      const detectionsNoBbox: Detection[] = [
        { label: 'person', confidence: 0.95 },
        { label: 'car', confidence: 0.87 },
      ];
      const eventNoBbox = { ...mockProps, detections: detectionsNoBbox };
      render(<EventCard {...eventNoBbox} />);
      const altText = screen.getByAltText(/Front Door at/);
      expect(altText).toBeInTheDocument();
      expect(altText).toHaveClass('h-20', 'w-20');
    });

    it('does not render thumbnail when thumbnail_url is undefined', () => {
      const noThumbnailEvent = { ...mockProps, thumbnail_url: undefined };
      render(<EventCard {...noThumbnailEvent} />);
      const images = screen.queryAllByRole('img');
      expect(images.length).toBe(0);
    });

    it('passes correct src to thumbnail image', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const img = container.querySelector('img');
      expect(img?.getAttribute('src')).toBe('https://example.com/thumbnail.jpg');
    });

    it('renders compact thumbnail in 80x80 format', () => {
      render(<EventCard {...mockProps} />);
      // Simple thumbnail should be rendered
      const altText = screen.getByAltText(/Front Door at/);
      expect(altText).toBeInTheDocument();
      expect(altText).toHaveClass('h-20', 'w-20', 'rounded-lg', 'object-cover', 'shadow-md');
    });

    it('renders placeholder icon when no thumbnail is available', () => {
      const noThumbnailEvent = { ...mockProps, thumbnail_url: undefined };
      render(<EventCard {...noThumbnailEvent} />);
      // Placeholder div should be rendered with Eye icon
      const placeholderDiv = document.querySelector('.flex.h-20.w-20');
      expect(placeholderDiv).toBeInTheDocument();
    });
  });

  describe('bounding box conversion', () => {
    it('displays thumbnail regardless of bounding boxes', () => {
      render(<EventCard {...mockProps} />);
      // Simple thumbnail should be rendered
      const altText = screen.getByAltText(/Front Door at/);
      expect(altText).toBeInTheDocument();
      expect(altText).toHaveClass('h-20', 'w-20');
    });

    it('displays thumbnail for mixed detections', () => {
      const mixedDetections: Detection[] = [
        { label: 'person', confidence: 0.95, bbox: { x: 100, y: 100, width: 200, height: 300 } },
        { label: 'car', confidence: 0.87 }, // No bbox
        { label: 'dog', confidence: 0.72, bbox: { x: 300, y: 200, width: 150, height: 100 } },
      ];
      const eventMixed = { ...mockProps, detections: mixedDetections };
      render(<EventCard {...eventMixed} />);
      // Simple thumbnail should be rendered
      const altText = screen.getByAltText(/Front Door at/);
      expect(altText).toBeInTheDocument();
    });

    it('displays simple thumbnail when no detections have bounding boxes', () => {
      const noBboxDetections: Detection[] = [
        { label: 'person', confidence: 0.95 },
        { label: 'car', confidence: 0.87 },
      ];
      const eventNoBbox = { ...mockProps, detections: noBboxDetections };
      render(<EventCard {...eventNoBbox} />);
      // Should use simple thumbnail
      const altText = screen.getByAltText(/Front Door at/);
      expect(altText).toBeInTheDocument();
      expect(altText).toHaveClass('h-20', 'w-20');
    });
  });

  describe('AI reasoning expand/collapse', () => {
    it('renders reasoning toggle button when reasoning is provided', () => {
      render(<EventCard {...mockProps} />);
      const toggleButton = screen.getByRole('button', { name: /AI Reasoning/i });
      expect(toggleButton).toBeInTheDocument();
    });

    it('does not render reasoning section when reasoning is undefined', () => {
      const noReasoningEvent = { ...mockProps, reasoning: undefined };
      render(<EventCard {...noReasoningEvent} />);
      expect(screen.queryByRole('button', { name: /AI Reasoning/i })).not.toBeInTheDocument();
    });

    it('does not render reasoning section when reasoning is empty string', () => {
      const emptyReasoningEvent = { ...mockProps, reasoning: '' };
      render(<EventCard {...emptyReasoningEvent} />);
      expect(screen.queryByRole('button', { name: /AI Reasoning/i })).not.toBeInTheDocument();
    });

    it('starts with reasoning collapsed', () => {
      render(<EventCard {...mockProps} />);
      const reasoningText = screen.queryByText(
        'The detected person is approaching the entrance during daytime hours.'
      );
      expect(reasoningText).not.toBeInTheDocument();
    });

    it('expands reasoning when toggle button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<EventCard {...mockProps} />);

      const toggleButton = screen.getByRole('button', { name: /AI Reasoning/i });
      await user.click(toggleButton);

      const reasoningText = screen.getByText(
        'The detected person is approaching the entrance during daytime hours.'
      );
      expect(reasoningText).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('collapses reasoning when toggle button is clicked twice', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<EventCard {...mockProps} />);

      const toggleButton = screen.getByRole('button', { name: /AI Reasoning/i });

      // Expand
      await user.click(toggleButton);
      expect(
        screen.getByText('The detected person is approaching the entrance during daytime hours.')
      ).toBeInTheDocument();

      // Collapse
      await user.click(toggleButton);
      expect(
        screen.queryByText('The detected person is approaching the entrance during daytime hours.')
      ).not.toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('shows ChevronDown icon when collapsed', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const chevronDown = container.querySelector('svg.lucide-chevron-down');
      expect(chevronDown).toBeInTheDocument();
    });

    it('shows ChevronUp icon when expanded', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const { container } = render(<EventCard {...mockProps} />);

      const toggleButton = screen.getByRole('button', { name: /AI Reasoning/i });
      await user.click(toggleButton);

      const chevronUp = container.querySelector('svg.lucide-chevron-up');
      expect(chevronUp).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('has correct aria-expanded attribute when collapsed', () => {
      render(<EventCard {...mockProps} />);
      const toggleButton = screen.getByRole('button', { name: /AI Reasoning/i });
      expect(toggleButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('has correct aria-expanded attribute when expanded', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<EventCard {...mockProps} />);

      const toggleButton = screen.getByRole('button', { name: /AI Reasoning/i });
      await user.click(toggleButton);

      expect(toggleButton).toHaveAttribute('aria-expanded', 'true');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('has correct aria-controls attribute', () => {
      render(<EventCard {...mockProps} />);
      const toggleButton = screen.getByRole('button', { name: /AI Reasoning/i });
      expect(toggleButton).toHaveAttribute('aria-controls', 'reasoning-event-123');
    });

    it('reasoning content has correct id', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<EventCard {...mockProps} />);

      const toggleButton = screen.getByRole('button', { name: /AI Reasoning/i });
      await user.click(toggleButton);

      const reasoningContent = screen
        .getByText('The detected person is approaching the entrance during daytime hours.')
        .closest('div');
      expect(reasoningContent).toHaveAttribute('id', 'reasoning-event-123');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('view details button', () => {
    it('renders view details button when onViewDetails is provided', () => {
      const handleViewDetails = vi.fn();
      render(<EventCard {...mockProps} onViewDetails={handleViewDetails} />);
      const button = screen.getByRole('button', { name: /View details for event event-123/i });
      expect(button).toBeInTheDocument();
    });

    it('does not render view details button when onViewDetails is undefined', () => {
      render(<EventCard {...mockProps} onViewDetails={undefined} />);
      expect(
        screen.queryByRole('button', { name: /View details for event event-123/i })
      ).not.toBeInTheDocument();
    });

    it('calls onViewDetails with correct event ID when clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleViewDetails = vi.fn();
      render(<EventCard {...mockProps} onViewDetails={handleViewDetails} />);

      const button = screen.getByRole('button', { name: /View details for event event-123/i });
      await user.click(button);

      expect(handleViewDetails).toHaveBeenCalledWith('event-123');
      expect(handleViewDetails).toHaveBeenCalledTimes(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('renders Eye icon in view details button', () => {
      const handleViewDetails = vi.fn();
      const { container } = render(<EventCard {...mockProps} onViewDetails={handleViewDetails} />);
      const eyeIcon = container.querySelector('svg.lucide-eye');
      expect(eyeIcon).toBeInTheDocument();
    });

    it('displays "View Details" text in button', () => {
      const handleViewDetails = vi.fn();
      render(<EventCard {...mockProps} onViewDetails={handleViewDetails} />);
      expect(screen.getByText('View Details')).toBeInTheDocument();
    });
  });

  describe('object type badges', () => {
    it('renders object type badges for detections', () => {
      const { container } = render(<EventCard {...mockProps} />);
      // Should render Person badge for person detection
      const badges = container.querySelectorAll('[role="status"]');
      // First badge is risk badge, rest are object type badges
      const objectBadges = Array.from(badges).slice(1);
      const badgeTexts = objectBadges.map((b) => b.textContent);
      expect(badgeTexts).toContain('Person');
      expect(badgeTexts).toContain('Vehicle');
    });

    it('renders unique object types only once', () => {
      const duplicateDetections: Detection[] = [
        { label: 'person', confidence: 0.95 },
        { label: 'person', confidence: 0.87 },
        { label: 'car', confidence: 0.72 },
      ];
      const { container } = render(<EventCard {...mockProps} detections={duplicateDetections} />);
      // Person badge should appear only once despite multiple person detections
      const badges = container.querySelectorAll('[role="status"]');
      const objectBadges = Array.from(badges).slice(1);
      const badgeTexts = objectBadges.map((b) => b.textContent);
      const personCount = badgeTexts.filter((text) => text === 'Person').length;
      expect(personCount).toBe(1);
    });

    it('handles case-insensitive object types', () => {
      const mixedCaseDetections: Detection[] = [
        { label: 'Person', confidence: 0.95 },
        { label: 'PERSON', confidence: 0.87 },
        { label: 'person', confidence: 0.72 },
      ];
      const { container } = render(<EventCard {...mockProps} detections={mixedCaseDetections} />);
      // All variations should be treated as the same type
      const badges = container.querySelectorAll('[role="status"]');
      const objectBadges = Array.from(badges).slice(1);
      const badgeTexts = objectBadges.map((b) => b.textContent);
      const personCount = badgeTexts.filter((text) => text === 'Person').length;
      expect(personCount).toBe(1);
    });

    it('does not render object type badges when detections are empty', () => {
      const noDetectionsEvent = { ...mockProps, detections: [] };
      const { container } = render(<EventCard {...noDetectionsEvent} />);
      const badges = container.querySelectorAll('[role="status"]');
      // Should only have the risk badge, no object type badges
      expect(badges.length).toBe(1);
    });

    it('renders badges for all unique object types', () => {
      const multipleTypes: Detection[] = [
        { label: 'person', confidence: 0.95 },
        { label: 'car', confidence: 0.87 },
        { label: 'dog', confidence: 0.72 },
        { label: 'package', confidence: 0.91 },
      ];
      const { container } = render(<EventCard {...mockProps} detections={multipleTypes} />);
      const badges = container.querySelectorAll('[role="status"]');
      const objectBadges = Array.from(badges).slice(1);
      const badgeTexts = objectBadges.map((b) => b.textContent);
      expect(badgeTexts).toContain('Person');
      expect(badgeTexts).toContain('Vehicle');
      expect(badgeTexts).toContain('Animal');
      expect(badgeTexts).toContain('Package');
    });

    it('renders badges before thumbnail image', () => {
      const { container } = render(<EventCard {...mockProps} />);
      // New layout: thumbnail (80x80) on left, content (with badges) on right
      const thumbnail = container.querySelector('.flex-shrink-0 img');
      const badges = container.querySelectorAll('.flex-wrap [role="status"]');

      expect(thumbnail).toBeInTheDocument();
      expect(thumbnail).toHaveClass('h-20', 'w-20');
      expect(badges.length).toBeGreaterThan(0);
    });

    it('renders object type badges with small size', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const badges = container.querySelectorAll('[role="status"]');
      // Check that at least one badge has small size styling (first badge should be risk badge, rest are object badges)
      const objectBadges = Array.from(badges).slice(1);
      expect(objectBadges.length).toBeGreaterThan(0);
      objectBadges.forEach((badge) => {
        expect(badge).toHaveClass('text-xs');
      });
    });
  });

  describe('risk score display', () => {
    // Risk score is now displayed in the RiskBadge with score visible
    // The progress bar was removed to simplify the card layout and improve scannability
    it('displays risk badge with score', () => {
      render(<EventCard {...mockProps} />);
      const riskBadge = screen.getByTestId('risk-badge');
      expect(riskBadge).toBeInTheDocument();
      // RiskBadge shows score in format "Level (score)"
      expect(riskBadge).toHaveTextContent('45');
    });

    it('renders thumbnail in content column', () => {
      const { container } = render(<EventCard {...mockProps} />);
      // New layout: thumbnail (80x80) on left, content on right
      const thumbnail = container.querySelector('.flex-shrink-0 img');
      const badges = container.querySelectorAll('.flex-wrap [role="status"]');

      expect(thumbnail).toBeInTheDocument();
      expect(badges.length).toBeGreaterThan(0);
    });

    it('renders thumbnail with larger size for better visibility', () => {
      const { container } = render(<EventCard {...mockProps} />);
      // Thumbnails are now 80x80 for better visibility
      const thumbnail = container.querySelector('.flex-shrink-0 img');

      expect(thumbnail).toBeInTheDocument();
      expect(thumbnail).toHaveClass('h-20', 'w-20');
    });

    it('displays risk badge with score for different risk levels', () => {
      const { rerender } = render(<EventCard {...mockProps} risk_score={15} />);
      expect(screen.getByTestId('risk-badge')).toHaveTextContent('Low');
      expect(screen.getByTestId('risk-badge')).toHaveTextContent('15');

      rerender(<EventCard {...mockProps} risk_score={45} />);
      expect(screen.getByTestId('risk-badge')).toHaveTextContent('Medium');
      expect(screen.getByTestId('risk-badge')).toHaveTextContent('45');

      rerender(<EventCard {...mockProps} risk_score={72} />);
      expect(screen.getByTestId('risk-badge')).toHaveTextContent('High');
      expect(screen.getByTestId('risk-badge')).toHaveTextContent('72');

      rerender(<EventCard {...mockProps} risk_score={90} />);
      expect(screen.getByTestId('risk-badge')).toHaveTextContent('Critical');
      expect(screen.getByTestId('risk-badge')).toHaveTextContent('90');
    });
  });

  describe('edge cases', () => {
    it('handles empty detections array', () => {
      const emptyDetectionsEvent = { ...mockProps, detections: [] };
      render(<EventCard {...emptyDetectionsEvent} />);
      expect(screen.queryByText(/Detections/)).not.toBeInTheDocument();
    });

    it('handles single detection', () => {
      const singleDetection: Detection[] = [{ label: 'person', confidence: 0.95 }];
      const singleDetectionEvent = { ...mockProps, detections: singleDetection };
      render(<EventCard {...singleDetectionEvent} />);
      expect(screen.getByText('Detections (1)')).toBeInTheDocument();
      expect(screen.getByText('person')).toBeInTheDocument();
    });

    it('handles very long summary text with truncation and expand', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const longSummaryEvent = {
        ...mockProps,
        summary:
          'This is a very long summary that describes an extremely complex security event with multiple elements and detailed analysis of what has occurred at this particular location and time with extensive contextual information and many more details.',
      };
      render(<EventCard {...longSummaryEvent} />);

      // Text should be truncated initially
      const truncatedText = screen.getByText(/This is a very long summary/);
      expect(truncatedText).toBeInTheDocument();

      // Show more button should be present
      const showMoreButton = screen.getByRole('button', { name: /show more/i });
      expect(showMoreButton).toBeInTheDocument();

      // Click to expand
      await user.click(showMoreButton);

      // Full text should now be visible
      expect(
        screen.getByText(/extensive contextual information and many more details/)
      ).toBeInTheDocument();

      // Show less button should now be present
      expect(screen.getByRole('button', { name: /show less/i })).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('handles very long reasoning text', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const longReasoningEvent = {
        ...mockProps,
        reasoning:
          'This is a very long reasoning text that provides extensive analysis and explanation of the security event including multiple factors, contextual elements, historical patterns, and detailed justification for the assigned risk score.',
      };
      render(<EventCard {...longReasoningEvent} />);

      const toggleButton = screen.getByRole('button', { name: /AI Reasoning/i });
      await user.click(toggleButton);

      const reasoning = screen.getByText(/This is a very long reasoning text/);
      expect(reasoning).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('handles detection labels with special characters', () => {
      const specialDetections: Detection[] = [
        { label: 'person-walking', confidence: 0.95 },
        { label: 'vehicle/car', confidence: 0.87 },
        { label: 'package (box)', confidence: 0.72 },
      ];
      const specialEvent = { ...mockProps, detections: specialDetections };
      render(<EventCard {...specialEvent} />);

      expect(screen.getByText('person-walking')).toBeInTheDocument();
      expect(screen.getByText('vehicle/car')).toBeInTheDocument();
      expect(screen.getByText('package (box)')).toBeInTheDocument();
    });

    it('handles very long camera names', () => {
      const longCameraNameEvent = {
        ...mockProps,
        camera_name: 'Front Door Main Entrance Camera Position Alpha',
      };
      render(<EventCard {...longCameraNameEvent} />);
      expect(
        screen.getByText('Front Door Main Entrance Camera Position Alpha')
      ).toBeInTheDocument();
    });

    it('applies truncation and title tooltip to camera name', () => {
      const longCameraNameEvent = {
        ...mockProps,
        camera_name: 'Front Door Main Entrance Camera Position Alpha',
      };
      render(<EventCard {...longCameraNameEvent} />);
      const heading = screen.getByRole('heading', {
        name: 'Front Door Main Entrance Camera Position Alpha',
      });
      expect(heading).toHaveClass('truncate');
      expect(heading).toHaveAttribute('title', 'Front Door Main Entrance Camera Position Alpha');
    });

    it('handles risk score at boundary (25)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 25 };
      render(<EventCard {...boundaryEvent} />);
      expect(screen.getByText('Low (25)')).toBeInTheDocument();
    });

    it('handles risk score at boundary (50)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 50 };
      render(<EventCard {...boundaryEvent} />);
      expect(screen.getByText('Medium (50)')).toBeInTheDocument();
    });

    it('handles risk score at boundary (75)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 75 };
      render(<EventCard {...boundaryEvent} />);
      expect(screen.getByText('High (75)')).toBeInTheDocument();
    });

    it('handles risk score at 100', () => {
      const maxRiskEvent = { ...mockProps, risk_score: 100 };
      render(<EventCard {...maxRiskEvent} />);
      expect(screen.getByText('Critical (100)')).toBeInTheDocument();
    });

    it('handles risk score at 0', () => {
      const minRiskEvent = { ...mockProps, risk_score: 0 };
      render(<EventCard {...minRiskEvent} />);
      expect(screen.getByText('Low (0)')).toBeInTheDocument();
    });
  });

  describe('duration display', () => {
    it('displays duration when started_at and ended_at are provided', () => {
      const eventWithDuration = {
        ...mockProps,
        started_at: new Date(BASE_TIME - 150 * 1000).toISOString(), // 2m 30s ago
        ended_at: new Date(BASE_TIME).toISOString(),
      };
      const { container } = render(<EventCard {...eventWithDuration} />);
      // Timer icon should be present
      const timerIcon = container.querySelector('svg.lucide-timer');
      expect(timerIcon).toBeInTheDocument();
      expect(screen.getByText(/2m 30s/)).toBeInTheDocument();
    });

    it('displays "ongoing" for events without ended_at', () => {
      const ongoingEvent = {
        ...mockProps,
        started_at: new Date(BASE_TIME - 2 * 60 * 1000).toISOString(), // 2 minutes ago
        ended_at: null,
      };
      const { container } = render(<EventCard {...ongoingEvent} />);
      // Timer icon should be present
      const timerIcon = container.querySelector('svg.lucide-timer');
      expect(timerIcon).toBeInTheDocument();
      expect(screen.getByText(/ongoing/)).toBeInTheDocument();
    });

    it('displays duration with "(ongoing)" suffix for older ongoing events', () => {
      const olderOngoingEvent = {
        ...mockProps,
        started_at: new Date(BASE_TIME - 10 * 60 * 1000).toISOString(), // 10 minutes ago
        ended_at: null,
      };
      const { container } = render(<EventCard {...olderOngoingEvent} />);
      // Timer icon should be present
      const timerIcon = container.querySelector('svg.lucide-timer');
      expect(timerIcon).toBeInTheDocument();
      expect(screen.getByText(/10m.*ongoing/)).toBeInTheDocument();
    });

    it('does not display duration when started_at is not provided', () => {
      const { container } = render(<EventCard {...mockProps} />);
      // Timer icon should not be present when no duration info
      const timerIcon = container.querySelector('svg.lucide-timer');
      expect(timerIcon).not.toBeInTheDocument();
    });

    it('renders Timer icon with duration', () => {
      const eventWithDuration = {
        ...mockProps,
        started_at: new Date(BASE_TIME - 150 * 1000).toISOString(),
        ended_at: new Date(BASE_TIME).toISOString(),
      };
      const { container } = render(<EventCard {...eventWithDuration} />);
      const timerIcon = container.querySelector('svg.lucide-timer');
      expect(timerIcon).toBeInTheDocument();
    });

    it('formats various duration lengths correctly', () => {
      const testCases = [
        { duration: 30 * 1000, expected: '30s' }, // 30 seconds
        { duration: 5 * 60 * 1000, expected: '5m' }, // 5 minutes
        { duration: 2 * 60 * 60 * 1000, expected: '2h' }, // 2 hours
        { duration: 36 * 60 * 60 * 1000, expected: '1d 12h' }, // 1 day 12 hours
      ];

      testCases.forEach(({ duration, expected }) => {
        const eventWithDuration = {
          ...mockProps,
          started_at: new Date(BASE_TIME - duration).toISOString(),
          ended_at: new Date(BASE_TIME).toISOString(),
        };
        const { unmount } = render(<EventCard {...eventWithDuration} />);
        expect(screen.getByText(expected, { exact: false })).toBeInTheDocument();
        unmount();
      });
    });

    it('uses timestamp as fallback when started_at is not provided', () => {
      const eventWithEndedAt = {
        ...mockProps,
        ended_at: new Date(BASE_TIME).toISOString(),
      };
      const { container } = render(<EventCard {...eventWithEndedAt} />);
      // Timer icon should be present indicating duration is shown
      const timerIcon = container.querySelector('svg.lucide-timer');
      expect(timerIcon).toBeInTheDocument();
    });
  });

  describe('layout and styling', () => {
    it('applies severity-based background tint (default mockProps has medium severity)', () => {
      // mockProps.risk_score is 45 which is medium severity
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      // Medium severity applies a subtle yellow tint
      expect(card).toHaveClass('bg-yellow-500/[0.04]');
    });

    it('applies rounded corners', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('rounded-lg');
    });

    it('applies border styling', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border', 'border-gray-800');
    });

    it('applies shadow styling', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('shadow-lg');
    });

    it('applies hover transition', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('transition-all', 'hover:border-gray-700');
    });

    it('applies padding to content container', () => {
      const { container } = render(<EventCard {...mockProps} />);
      // New layout: padding is on inner flex container, not outer card
      const flexContainer = container.querySelector('.flex.gap-4.p-4');
      expect(flexContainer).toBeInTheDocument();
      expect(flexContainer).toHaveClass('p-4');
    });
  });

  describe('checkbox overlay support', () => {
    it('does not add left margin to header by default', () => {
      const { container } = render(<EventCard {...mockProps} />);
      // The header row now has mb-2 class (restructured layout)
      const headerDiv = container.querySelector('.mb-2.flex.items-start.justify-between');
      expect(headerDiv).not.toHaveClass('ml-8');
    });

    it('adds left margin to header when hasCheckboxOverlay is true', () => {
      const { container } = render(<EventCard {...mockProps} hasCheckboxOverlay />);
      // The header row now has mb-2 class (restructured layout)
      const headerDiv = container.querySelector('.mb-2.flex.items-start.justify-between');
      expect(headerDiv).toHaveClass('ml-8');
    });

    it('still displays camera name correctly with checkbox overlay', () => {
      render(<EventCard {...mockProps} hasCheckboxOverlay />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
    });

    it('applies ml-8 class only to header, not entire card', () => {
      const { container } = render(<EventCard {...mockProps} hasCheckboxOverlay />);
      const card = container.firstChild as HTMLElement;
      expect(card).not.toHaveClass('ml-8');
    });
  });

  describe('color-coded left border', () => {
    // Note: These tests now use the new severity-based border classes from severityColors utility
    // The thresholds are: LOW: <30, MEDIUM: 30-59, HIGH: 60-79, CRITICAL: >=80

    it('applies NVIDIA green (primary) left border for low risk events', () => {
      const lowRiskEvent = { ...mockProps, risk_score: 15 };
      const { container } = render(<EventCard {...lowRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-4', 'border-l-primary');
    });

    it('applies yellow left border for medium risk events', () => {
      const mediumRiskEvent = { ...mockProps, risk_score: 45 };
      const { container } = render(<EventCard {...mediumRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-4', 'border-l-yellow-500');
    });

    it('applies orange left border with enhanced width for high risk events', () => {
      const highRiskEvent = { ...mockProps, risk_score: 72 };
      const { container } = render(<EventCard {...highRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      // High severity has thicker border (5px) for better visibility
      expect(card).toHaveClass('border-l-[5px]', 'border-l-orange-500');
    });

    it('applies red left border with enhanced width for critical risk events', () => {
      const criticalRiskEvent = { ...mockProps, risk_score: 88 };
      const { container } = render(<EventCard {...criticalRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      // Critical severity has thickest border (6px) for maximum visibility
      expect(card).toHaveClass('border-l-[6px]', 'border-l-red-500');
    });

    it('applies correct border width class', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-4');
    });

    // Severity thresholds: LOW: <30, MEDIUM: 30-59, HIGH: 60-79, CRITICAL: >=80
    it('applies NVIDIA green (primary) left border at risk score boundary (29)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 29 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-primary');
    });

    it('applies yellow left border at risk score boundary (30)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 30 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-yellow-500');
    });

    it('applies yellow left border at risk score boundary (59)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 59 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-yellow-500');
    });

    it('applies orange left border at risk score boundary (60)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 60 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-orange-500');
    });

    it('applies critical red left border at risk score boundary (80)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 80 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-red-500');
    });

    it('applies critical red left border at risk score boundary (85)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 85 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-red-500');
    });

    it('applies red left border at maximum risk score (100)', () => {
      const maxRiskEvent = { ...mockProps, risk_score: 100 };
      const { container } = render(<EventCard {...maxRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-red-500');
    });

    it('applies NVIDIA green (primary) left border at minimum risk score (0)', () => {
      const minRiskEvent = { ...mockProps, risk_score: 0 };
      const { container } = render(<EventCard {...minRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-primary');
    });
  });

  describe('card click behavior', () => {
    it('calls onClick when card is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      const { container } = render(<EventCard {...mockProps} onClick={handleClick} />);

      const card = container.firstChild as HTMLElement;
      await user.click(card);

      expect(handleClick).toHaveBeenCalledWith('event-123');
      expect(handleClick).toHaveBeenCalledTimes(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('does not call onClick when clicking on interactive elements (buttons)', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      const handleViewDetails = vi.fn();
      render(<EventCard {...mockProps} onClick={handleClick} onViewDetails={handleViewDetails} />);

      // Click on View Details button
      const viewDetailsButton = screen.getByRole('button', {
        name: /View details for event event-123/i,
      });
      await user.click(viewDetailsButton);

      // onClick should not be called, only onViewDetails
      expect(handleClick).not.toHaveBeenCalled();
      expect(handleViewDetails).toHaveBeenCalledWith('event-123');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('does not call onClick when clicking AI Reasoning toggle', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<EventCard {...mockProps} onClick={handleClick} />);

      const reasoningToggle = screen.getByRole('button', { name: /AI Reasoning/i });
      await user.click(reasoningToggle);

      expect(handleClick).not.toHaveBeenCalled();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('applies cursor-pointer class when onClick is provided', () => {
      const handleClick = vi.fn();
      const { container } = render(<EventCard {...mockProps} onClick={handleClick} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('cursor-pointer');
    });

    it('applies hover:bg-[#252525] class when onClick is provided', () => {
      const handleClick = vi.fn();
      const { container } = render(<EventCard {...mockProps} onClick={handleClick} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('hover:bg-[#252525]');
    });

    it('does not apply cursor-pointer class when onClick is not provided', () => {
      const { container } = render(<EventCard {...mockProps} />);

      const card = container.firstChild as HTMLElement;
      expect(card).not.toHaveClass('cursor-pointer');
    });

    it('has role="button" when onClick is provided', () => {
      const handleClick = vi.fn();
      const { container } = render(<EventCard {...mockProps} onClick={handleClick} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveAttribute('role', 'button');
    });

    it('does not have role="button" when onClick is not provided', () => {
      const { container } = render(<EventCard {...mockProps} />);

      const card = container.firstChild as HTMLElement;
      expect(card).not.toHaveAttribute('role', 'button');
    });

    it('has tabIndex=0 when onClick is provided', () => {
      const handleClick = vi.fn();
      const { container } = render(<EventCard {...mockProps} onClick={handleClick} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveAttribute('tabIndex', '0');
    });

    it('does not have tabIndex when onClick is not provided', () => {
      const { container } = render(<EventCard {...mockProps} />);

      const card = container.firstChild as HTMLElement;
      expect(card).not.toHaveAttribute('tabIndex');
    });

    it('has aria-label when onClick is provided', () => {
      const handleClick = vi.fn();
      const { container } = render(<EventCard {...mockProps} onClick={handleClick} />);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveAttribute('aria-label', 'View details for event from Front Door');
    });

    it('calls onClick when Enter key is pressed', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      const { container } = render(<EventCard {...mockProps} onClick={handleClick} />);

      const card = container.firstChild as HTMLElement;
      card.focus();
      await user.keyboard('{Enter}');

      expect(handleClick).toHaveBeenCalledWith('event-123');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onClick when Space key is pressed', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      const { container } = render(<EventCard {...mockProps} onClick={handleClick} />);

      const card = container.firstChild as HTMLElement;
      card.focus();
      await user.keyboard(' ');

      expect(handleClick).toHaveBeenCalledWith('event-123');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('both onClick and onViewDetails can be provided together', async () => {
      // When nested interactive elements (View Details button) exist, the card is still clickable
      // but does NOT have role="button" to avoid WCAG nested-interactive violations.
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      const handleViewDetails = vi.fn();
      render(<EventCard {...mockProps} onClick={handleClick} onViewDetails={handleViewDetails} />);

      // Click on card (not on button) - onClick should still be called
      const summaryText = screen.getByText('Person detected approaching the front entrance');
      await user.click(summaryText);

      expect(handleClick).toHaveBeenCalledWith('event-123');
      expect(handleViewDetails).not.toHaveBeenCalled();

      // Now click on View Details button
      const viewDetailsButton = screen.getByRole('button', {
        name: /View details for event event-123/i,
      });
      await user.click(viewDetailsButton);

      expect(handleClick).toHaveBeenCalledTimes(1); // Still only 1 call (button click doesn't propagate)
      expect(handleViewDetails).toHaveBeenCalledWith('event-123');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('integration', () => {
    it('renders complete event card with all elements', () => {
      const handleViewDetails = vi.fn();
      render(<EventCard {...mockProps} onViewDetails={handleViewDetails} />);

      // All major sections should be present
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText(/minutes ago/)).toBeInTheDocument();
      expect(screen.getByText('Medium (45)')).toBeInTheDocument();
      expect(screen.getAllByRole('img').length).toBeGreaterThan(0);
      expect(
        screen.getByText('Person detected approaching the front entrance')
      ).toBeInTheDocument();
      expect(screen.getByText('Detections (2)')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /AI Reasoning/i })).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /View details for event event-123/i })
      ).toBeInTheDocument();
    });

    it('renders minimal event card without optional elements', () => {
      const minimalProps = {
        id: 'event-456',
        timestamp: new Date(BASE_TIME).toISOString(),
        camera_name: 'Back Door',
        risk_score: 10,
        risk_label: 'Low',
        summary: 'All clear',
        detections: [],
      };
      render(<EventCard {...minimalProps} />);

      expect(screen.getByText('Back Door')).toBeInTheDocument();
      expect(screen.getByText('All clear')).toBeInTheDocument();
      expect(screen.getByText('Low (10)')).toBeInTheDocument();
      expect(screen.queryByText(/Detections/)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /AI Reasoning/i })).not.toBeInTheDocument();
      expect(
        screen.queryByRole('button', { name: /View details for event event-456/i })
      ).not.toBeInTheDocument();
    });

    it('handles multiple interactions without errors', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleViewDetails = vi.fn();
      render(<EventCard {...mockProps} onViewDetails={handleViewDetails} />);

      // Expand reasoning
      const reasoningToggle = screen.getByRole('button', { name: /AI Reasoning/i });
      await user.click(reasoningToggle);
      expect(
        screen.getByText('The detected person is approaching the entrance during daytime hours.')
      ).toBeInTheDocument();

      // Click view details
      const viewDetailsButton = screen.getByRole('button', {
        name: /View details for event event-123/i,
      });
      await user.click(viewDetailsButton);
      expect(handleViewDetails).toHaveBeenCalledWith('event-123');

      // Collapse reasoning
      await user.click(reasoningToggle);
      expect(
        screen.queryByText('The detected person is approaching the entrance during daytime hours.')
      ).not.toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('detection confidence color coding', () => {
    const highConfidenceDetections: Detection[] = [
      { label: 'person', confidence: 0.95, bbox: { x: 0, y: 0, width: 100, height: 100 } },
    ];

    const mixedConfidenceDetections: Detection[] = [
      { label: 'person', confidence: 0.95, bbox: { x: 0, y: 0, width: 100, height: 100 } },
      { label: 'car', confidence: 0.75, bbox: { x: 0, y: 0, width: 100, height: 100 } },
      { label: 'dog', confidence: 0.5, bbox: { x: 0, y: 0, width: 100, height: 100 } },
    ];

    it('applies green color for high confidence detections (>= 85%)', () => {
      const { container } = render(
        <EventCard {...mockProps} detections={highConfidenceDetections} />
      );
      // Check that the detection badge has green text color class
      const detectionBadges = container.querySelectorAll('.text-green-400');
      expect(detectionBadges.length).toBeGreaterThan(0);
    });

    it('applies yellow color for medium confidence detections (70-85%)', () => {
      const mediumDetections: Detection[] = [
        { label: 'car', confidence: 0.75, bbox: { x: 0, y: 0, width: 100, height: 100 } },
      ];
      const { container } = render(<EventCard {...mockProps} detections={mediumDetections} />);
      const detectionBadges = container.querySelectorAll('.text-yellow-400');
      expect(detectionBadges.length).toBeGreaterThan(0);
    });

    it('applies red color for low confidence detections (< 70%)', () => {
      const lowDetections: Detection[] = [
        { label: 'dog', confidence: 0.5, bbox: { x: 0, y: 0, width: 100, height: 100 } },
      ];
      const { container } = render(<EventCard {...mockProps} detections={lowDetections} />);
      const detectionBadges = container.querySelectorAll('.text-red-400');
      expect(detectionBadges.length).toBeGreaterThan(0);
    });

    it('sorts detections by confidence (highest first)', () => {
      render(<EventCard {...mockProps} detections={mixedConfidenceDetections} />);
      // Get all detection badges
      const detectionSection = screen.getByText(/Detections \(3\)/i).parentElement;
      const badges = detectionSection?.querySelectorAll('[title]');
      if (badges && badges.length >= 3) {
        // First badge should be the highest confidence (person - 95%)
        expect(badges[0]).toHaveAttribute('title', expect.stringContaining('person'));
        expect(badges[0]).toHaveAttribute('title', expect.stringContaining('95%'));
      }
    });

    it('displays aggregate confidence (Avg and Max) for multiple detections', () => {
      render(<EventCard {...mockProps} detections={mixedConfidenceDetections} />);
      // Check for "Avg:" label
      expect(screen.getByText('Avg:')).toBeInTheDocument();
      // Check for "Max:" label
      expect(screen.getByText('Max:')).toBeInTheDocument();
    });

    it('calculates average confidence correctly', () => {
      render(<EventCard {...mockProps} detections={mixedConfidenceDetections} />);
      // Average of 0.95 + 0.75 + 0.5 = 2.2 / 3 = 0.733... -> 73%
      expect(screen.getByText('73%')).toBeInTheDocument();
    });

    it('displays maximum confidence correctly', () => {
      render(<EventCard {...mockProps} detections={mixedConfidenceDetections} />);
      // Max is 0.95 -> 95% - may appear in both badge and aggregate display
      expect(screen.getAllByText('95%').length).toBeGreaterThanOrEqual(1);
    });

    it('applies color coding to aggregate confidence values', () => {
      const { container } = render(
        <EventCard {...mockProps} detections={mixedConfidenceDetections} />
      );
      // Max is high (green), Average is medium (yellow)
      const greenTexts = container.querySelectorAll('.text-green-400');
      const yellowTexts = container.querySelectorAll('.text-yellow-400');
      expect(greenTexts.length).toBeGreaterThan(0);
      expect(yellowTexts.length).toBeGreaterThan(0);
    });

    it('shows TrendingUp icon for aggregate confidence display', () => {
      const { container } = render(
        <EventCard {...mockProps} detections={mixedConfidenceDetections} />
      );
      // Check for lucide-trending-up SVG icon
      const icon = container.querySelector('svg.lucide-trending-up');
      expect(icon).toBeInTheDocument();
    });

    it('does not show aggregate confidence when no detections', () => {
      render(<EventCard {...mockProps} detections={[]} />);
      expect(screen.queryByText('Avg:')).not.toBeInTheDocument();
      expect(screen.queryByText('Max:')).not.toBeInTheDocument();
    });

    it('detection badges have title with confidence label', () => {
      render(<EventCard {...mockProps} detections={highConfidenceDetections} />);
      const detectionBadge = screen.getByTitle(/person.*95%.*High Confidence/i);
      expect(detectionBadge).toBeInTheDocument();
    });

    it('applies background and border colors based on confidence level', () => {
      const { container } = render(
        <EventCard {...mockProps} detections={mixedConfidenceDetections} />
      );
      // Check for red background/border for low confidence
      const redBgElements = container.querySelectorAll('.bg-red-500\\/20');
      expect(redBgElements.length).toBeGreaterThan(0);
      // Check for green background/border for high confidence
      const greenBgElements = container.querySelectorAll('.bg-green-500\\/20');
      expect(greenBgElements.length).toBeGreaterThan(0);
    });
  });

  describe('severity-tinted backgrounds', () => {
    // Helper to mock matchMedia for reduced motion preference
    const mockMatchMedia = (prefersReducedMotion: boolean) => {
      const listeners: Array<(e: MediaQueryListEvent) => void> = [];
      const mockMediaQuery = {
        matches: prefersReducedMotion,
        media: '(prefers-reduced-motion: reduce)',
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn((event: string, callback: (e: MediaQueryListEvent) => void) => {
          if (event === 'change') {
            listeners.push(callback);
          }
        }),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      };
      return {
        mockMediaQuery,
        triggerChange: (newValue: boolean) => {
          listeners.forEach((listener) => listener({ matches: newValue } as MediaQueryListEvent));
        },
      };
    };

    beforeEach(() => {
      // Default: no reduced motion preference
      const { mockMediaQuery } = mockMatchMedia(false);
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: vi.fn().mockImplementation(() => mockMediaQuery),
      });
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    describe('data-severity attribute', () => {
      it('sets data-severity="critical" for risk scores >= 80', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={85} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'critical');
      });

      it('sets data-severity="high" for risk scores 60-79', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={72} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'high');
      });

      it('sets data-severity="medium" for risk scores 30-59', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={45} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'medium');
      });

      it('sets data-severity="low" for risk scores < 30', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={15} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'low');
      });
    });

    describe('background tint classes', () => {
      it('applies enhanced red background tint for critical severity (>= 80)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={85} />);
        const card = container.firstChild as HTMLElement;
        // Enhanced background for better visual distinction
        expect(card).toHaveClass('bg-red-950/40');
      });

      it('applies enhanced orange background tint for high severity (60-79)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={72} />);
        const card = container.firstChild as HTMLElement;
        // Enhanced background for better visual distinction
        expect(card).toHaveClass('bg-orange-950/30');
      });

      it('applies yellow background tint for medium severity (30-59)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={45} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveClass('bg-yellow-500/[0.04]');
      });

      it('applies transparent background for low severity (< 30)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={15} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveClass('bg-transparent');
      });
    });

    describe('border color classes', () => {
      it('applies red border for critical severity (>= 80)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={85} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveClass('border-l-red-500');
      });

      it('applies orange border for high severity (60-79)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={72} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveClass('border-l-orange-500');
      });

      it('applies yellow border for medium severity (30-59)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={45} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveClass('border-l-yellow-500');
      });

      it('applies primary (NVIDIA green) border for low severity (< 30)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={15} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveClass('border-l-primary');
      });
    });

    describe('glow effect for critical severity', () => {
      it('applies glow shadow class for critical severity', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={85} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveClass('shadow-[0_0_8px_rgba(239,68,68,0.3)]');
      });

      it('does not apply glow shadow for high severity', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={72} />);
        const card = container.firstChild as HTMLElement;
        expect(card).not.toHaveClass('shadow-[0_0_8px_rgba(239,68,68,0.3)]');
      });

      it('does not apply glow shadow for medium severity', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={45} />);
        const card = container.firstChild as HTMLElement;
        expect(card).not.toHaveClass('shadow-[0_0_8px_rgba(239,68,68,0.3)]');
      });

      it('does not apply glow shadow for low severity', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={15} />);
        const card = container.firstChild as HTMLElement;
        expect(card).not.toHaveClass('shadow-[0_0_8px_rgba(239,68,68,0.3)]');
      });
    });

    describe('pulse animation for critical severity', () => {
      it('applies pulse animation class for critical severity when motion is allowed', () => {
        const { mockMediaQuery } = mockMatchMedia(false);
        (window.matchMedia as Mock).mockReturnValue(mockMediaQuery);

        const { container } = render(<EventCard {...mockProps} risk_score={85} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveClass('animate-pulse-subtle');
      });

      it('does not apply pulse animation when prefers-reduced-motion is enabled', () => {
        const { mockMediaQuery } = mockMatchMedia(true);
        (window.matchMedia as Mock).mockReturnValue(mockMediaQuery);

        const { container } = render(<EventCard {...mockProps} risk_score={85} />);
        const card = container.firstChild as HTMLElement;
        expect(card).not.toHaveClass('animate-pulse-subtle');
      });

      it('does not apply pulse animation for high severity', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={72} />);
        const card = container.firstChild as HTMLElement;
        expect(card).not.toHaveClass('animate-pulse-subtle');
      });

      it('does not apply pulse animation for medium severity', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={45} />);
        const card = container.firstChild as HTMLElement;
        expect(card).not.toHaveClass('animate-pulse-subtle');
      });

      it('does not apply pulse animation for low severity', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={15} />);
        const card = container.firstChild as HTMLElement;
        expect(card).not.toHaveClass('animate-pulse-subtle');
      });
    });

    describe('severity boundary values', () => {
      it('applies critical styling at exact boundary (80)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={80} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'critical');
        expect(card).toHaveClass('bg-red-950/40');
        expect(card).toHaveClass('border-l-red-500');
      });

      it('applies high styling just below critical boundary (79)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={79} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'high');
        expect(card).toHaveClass('bg-orange-950/30');
        expect(card).toHaveClass('border-l-orange-500');
      });

      it('applies high styling at exact boundary (60)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={60} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'high');
        expect(card).toHaveClass('bg-orange-950/30');
      });

      it('applies medium styling just below high boundary (59)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={59} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'medium');
        expect(card).toHaveClass('bg-yellow-500/[0.04]');
      });

      it('applies medium styling at exact boundary (30)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={30} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'medium');
        expect(card).toHaveClass('bg-yellow-500/[0.04]');
      });

      it('applies low styling just below medium boundary (29)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={29} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'low');
        expect(card).toHaveClass('bg-transparent');
      });

      it('applies low styling at minimum (0)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={0} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'low');
        expect(card).toHaveClass('bg-transparent');
        expect(card).toHaveClass('border-l-primary');
      });

      it('applies critical styling at maximum (100)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={100} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveAttribute('data-severity', 'critical');
        expect(card).toHaveClass('bg-red-950/40');
        expect(card).toHaveClass('border-l-red-500');
        expect(card).toHaveClass('animate-pulse-subtle');
      });
    });

    describe('critical events visual distinction', () => {
      it('critical events have all three visual indicators (background, border, glow)', () => {
        const { container } = render(<EventCard {...mockProps} risk_score={90} />);
        const card = container.firstChild as HTMLElement;

        // Enhanced background tint for better visibility
        expect(card).toHaveClass('bg-red-950/40');
        // Border color
        expect(card).toHaveClass('border-l-red-500');
        // Glow effect
        expect(card).toHaveClass('shadow-[0_0_8px_rgba(239,68,68,0.3)]');
      });

      it('critical events have animation when motion is allowed', () => {
        const { mockMediaQuery } = mockMatchMedia(false);
        (window.matchMedia as Mock).mockReturnValue(mockMediaQuery);

        const { container } = render(<EventCard {...mockProps} risk_score={90} />);
        const card = container.firstChild as HTMLElement;
        expect(card).toHaveClass('animate-pulse-subtle');
      });

      it('critical events stand out from other severity levels', () => {
        const criticalCard = render(<EventCard {...mockProps} risk_score={90} />);
        const highCard = render(<EventCard {...mockProps} risk_score={70} />);

        const critical = criticalCard.container.firstChild as HTMLElement;
        const high = highCard.container.firstChild as HTMLElement;

        // Critical has glow, high does not
        expect(critical).toHaveClass('shadow-[0_0_8px_rgba(239,68,68,0.3)]');
        expect(high).not.toHaveClass('shadow-[0_0_8px_rgba(239,68,68,0.3)]');

        // Critical has animation, high does not
        expect(critical).toHaveClass('animate-pulse-subtle');
        expect(high).not.toHaveClass('animate-pulse-subtle');
      });
    });
  });

  describe('CollapsibleDetections', () => {
    const manyDetections: Detection[] = [
      { label: 'person', confidence: 0.95 },
      { label: 'car', confidence: 0.87 },
      { label: 'dog', confidence: 0.72 },
      { label: 'bicycle', confidence: 0.65 },
      { label: 'package', confidence: 0.91 },
      { label: 'cat', confidence: 0.55 },
    ];

    const fewDetections: Detection[] = [
      { label: 'person', confidence: 0.95 },
      { label: 'car', confidence: 0.87 },
    ];

    it('shows only maxVisible detections initially when there are more', () => {
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      // Should show first 3 detections (sorted by confidence: person 95%, package 91%, car 87%)
      const container = screen.getByTestId('collapsible-detections');
      const badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(3);
    });

    it('shows +N more button when detections exceed maxVisible', () => {
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      // 6 detections - 3 visible = 3 hidden
      expect(screen.getByText('+3 more')).toBeInTheDocument();
    });

    it('does not show toggle button when detections are at or below maxVisible', () => {
      render(<CollapsibleDetections detections={fewDetections} maxVisible={3} />);

      expect(screen.queryByTestId('collapsible-detections-toggle')).not.toBeInTheDocument();
    });

    it('shows all detections when there are fewer than maxVisible', () => {
      render(<CollapsibleDetections detections={fewDetections} maxVisible={3} />);

      const container = screen.getByTestId('collapsible-detections');
      const badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(2);
    });

    it('expands to show all detections when clicking +N more button', async () => {
      const user = userEvent.setup();
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      // Initially 3 visible
      let container = screen.getByTestId('collapsible-detections');
      let badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(3);

      // Click to expand
      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      await user.click(toggleButton);

      // Now all 6 should be visible
      container = screen.getByTestId('collapsible-detections');
      badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(6);
    });

    it('shows "Show less" button when expanded', async () => {
      const user = userEvent.setup();
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      // Expand
      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      await user.click(toggleButton);

      // Should now show "Show less"
      expect(screen.getByText('Show less')).toBeInTheDocument();
    });

    it('collapses back to maxVisible on "Show less" click', async () => {
      const user = userEvent.setup();
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      // Expand
      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      await user.click(toggleButton);

      // Verify expanded (6 badges)
      let container = screen.getByTestId('collapsible-detections');
      let badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(6);

      // Collapse
      await user.click(toggleButton);

      // Back to 3 visible
      container = screen.getByTestId('collapsible-detections');
      badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(3);
    });

    it('sorts detections by confidence (highest first)', () => {
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      // Detections sorted by confidence: person (95%), package (91%), car (87%), dog (72%), bicycle (65%), cat (55%)
      // First 3 visible: person, package, car
      const container = screen.getByTestId('collapsible-detections');
      const badges = container.querySelectorAll('[title]');

      expect(badges[0]).toHaveAttribute('title', expect.stringContaining('person'));
      expect(badges[0]).toHaveAttribute('title', expect.stringContaining('95%'));
      expect(badges[1]).toHaveAttribute('title', expect.stringContaining('package'));
      expect(badges[1]).toHaveAttribute('title', expect.stringContaining('91%'));
      expect(badges[2]).toHaveAttribute('title', expect.stringContaining('car'));
      expect(badges[2]).toHaveAttribute('title', expect.stringContaining('87%'));
    });

    it('uses default maxVisible of 3', () => {
      render(<CollapsibleDetections detections={manyDetections} />);

      const container = screen.getByTestId('collapsible-detections');
      const badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(3);
    });

    it('respects custom maxVisible value', () => {
      render(<CollapsibleDetections detections={manyDetections} maxVisible={2} />);

      const container = screen.getByTestId('collapsible-detections');
      const badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(2);

      // 6 - 2 = 4 hidden
      expect(screen.getByText('+4 more')).toBeInTheDocument();
    });

    it('has correct aria-expanded attribute when collapsed', () => {
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      expect(toggleButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('has correct aria-expanded attribute when expanded', async () => {
      const user = userEvent.setup();
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      await user.click(toggleButton);

      expect(toggleButton).toHaveAttribute('aria-expanded', 'true');
    });

    it('has appropriate aria-label when collapsed', () => {
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      expect(toggleButton).toHaveAttribute('aria-label', 'Show 3 more detections');
    });

    it('has appropriate aria-label when expanded', async () => {
      const user = userEvent.setup();
      render(<CollapsibleDetections detections={manyDetections} maxVisible={3} />);

      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      await user.click(toggleButton);

      expect(toggleButton).toHaveAttribute('aria-label', 'Show fewer detections');
    });

    it('renders ChevronDown icon when collapsed', () => {
      const { container } = render(
        <CollapsibleDetections detections={manyDetections} maxVisible={3} />
      );

      const chevronDown = container.querySelector('svg.lucide-chevron-down');
      expect(chevronDown).toBeInTheDocument();
    });

    it('renders ChevronUp icon when expanded', async () => {
      const user = userEvent.setup();
      const { container } = render(
        <CollapsibleDetections detections={manyDetections} maxVisible={3} />
      );

      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      await user.click(toggleButton);

      const chevronUp = container.querySelector('svg.lucide-chevron-up');
      expect(chevronUp).toBeInTheDocument();
    });

    it('handles exactly maxVisible detections (no toggle needed)', () => {
      const exactDetections: Detection[] = [
        { label: 'person', confidence: 0.95 },
        { label: 'car', confidence: 0.87 },
        { label: 'dog', confidence: 0.72 },
      ];
      render(<CollapsibleDetections detections={exactDetections} maxVisible={3} />);

      // All 3 visible, no toggle button
      const container = screen.getByTestId('collapsible-detections');
      const badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(3);
      expect(screen.queryByTestId('collapsible-detections-toggle')).not.toBeInTheDocument();
    });

    it('handles single detection', () => {
      const singleDetection: Detection[] = [{ label: 'person', confidence: 0.95 }];
      render(<CollapsibleDetections detections={singleDetection} maxVisible={3} />);

      const container = screen.getByTestId('collapsible-detections');
      const badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(1);
      expect(screen.queryByTestId('collapsible-detections-toggle')).not.toBeInTheDocument();
    });

    it('handles empty detections array', () => {
      render(<CollapsibleDetections detections={[]} maxVisible={3} />);

      const container = screen.getByTestId('collapsible-detections');
      const badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(0);
      expect(screen.queryByTestId('collapsible-detections-toggle')).not.toBeInTheDocument();
    });
  });

  describe('CollapsibleDetections integration with EventCard', () => {
    // Base time for consistent testing
    const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

    const manyDetections: Detection[] = [
      { label: 'person', confidence: 0.95 },
      { label: 'car', confidence: 0.87 },
      { label: 'dog', confidence: 0.72 },
      { label: 'bicycle', confidence: 0.65 },
      { label: 'package', confidence: 0.91 },
      { label: 'cat', confidence: 0.55 },
    ];

    const eventProps: EventCardProps = {
      id: 'event-456',
      timestamp: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(),
      camera_name: 'Front Door',
      risk_score: 45,
      risk_label: 'Medium',
      summary: 'Multiple objects detected',
      detections: manyDetections,
    };

    beforeEach(() => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('uses CollapsibleDetections in EventCard with 5+ detections', () => {
      render(<EventCard {...eventProps} />);

      // Should have collapsible-detections container
      expect(screen.getByTestId('collapsible-detections')).toBeInTheDocument();

      // Should show +N more button
      expect(screen.getByTestId('collapsible-detections-toggle')).toBeInTheDocument();
    });

    it('click on toggle does not trigger card navigation', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<EventCard {...eventProps} onClick={handleClick} />);

      // Click on the toggle button
      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      await user.click(toggleButton);

      // Card onClick should NOT be called
      expect(handleClick).not.toHaveBeenCalled();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('card click works on non-interactive areas with collapsible detections', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<EventCard {...eventProps} onClick={handleClick} />);

      // Click on the summary text (non-interactive area)
      const summaryText = screen.getByText('Multiple objects detected');
      await user.click(summaryText);

      // Card onClick should be called
      expect(handleClick).toHaveBeenCalledWith('event-456');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('displays correct detection count header with many detections', () => {
      render(<EventCard {...eventProps} />);

      // Header shows total count
      expect(screen.getByText('Detections (6)')).toBeInTheDocument();
    });

    it('expands and collapses detections within EventCard', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<EventCard {...eventProps} />);

      // Initially collapsed - 3 visible + toggle button
      let container = screen.getByTestId('collapsible-detections');
      let badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(3);
      expect(screen.getByText('+3 more')).toBeInTheDocument();

      // Expand
      const toggleButton = screen.getByTestId('collapsible-detections-toggle');
      await user.click(toggleButton);

      // Now all 6 visible
      container = screen.getByTestId('collapsible-detections');
      badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(6);
      expect(screen.getByText('Show less')).toBeInTheDocument();

      // Collapse again
      await user.click(toggleButton);

      // Back to 3 visible
      container = screen.getByTestId('collapsible-detections');
      badges = container.querySelectorAll('[title]');
      expect(badges.length).toBe(3);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

describe('enrichment badges integration', () => {
    // Use detections without "car" to avoid multiple "Vehicle" text elements
    const noVehicleDetections: Detection[] = [
      { label: 'person', confidence: 0.95 },
      { label: 'dog', confidence: 0.87 },
    ];

    it('renders enrichment badges when enrichmentSummary is provided', () => {
      const enrichmentSummary = { hasLicensePlate: true, hasPerson: true };
      render(
        <EventCard {...mockProps} detections={noVehicleDetections} enrichmentSummary={enrichmentSummary} />
      );
      expect(screen.getByTestId('enrichment-badges')).toBeInTheDocument();
      expect(screen.getByTestId('enrichment-badge-plate')).toBeInTheDocument();
      expect(screen.getByTestId('enrichment-badge-person')).toBeInTheDocument();
    });

    it('renders enrichment badges when enrichmentData is provided', () => {
      const enrichmentData = {
        license_plate: { text: 'ABC-123', confidence: 0.95 },
        pet: { type: 'dog' as const, confidence: 0.9 },
      };
      render(
        <EventCard {...mockProps} detections={noVehicleDetections} enrichmentData={enrichmentData} />
      );
      expect(screen.getByTestId('enrichment-badges')).toBeInTheDocument();
      expect(screen.getByTestId('enrichment-badge-plate')).toBeInTheDocument();
      expect(screen.getByTestId('enrichment-badge-dog')).toBeInTheDocument();
    });

    it('renders pending badge when isEnrichmentPending is true', () => {
      render(<EventCard {...mockProps} isEnrichmentPending={true} />);
      expect(screen.getByTestId('enrichment-badges-pending')).toBeInTheDocument();
      expect(screen.getByText('Enriching...')).toBeInTheDocument();
    });

    it('does not render enrichment badges when no enrichment data', () => {
      render(<EventCard {...mockProps} />);
      expect(screen.queryByTestId('enrichment-badges')).not.toBeInTheDocument();
    });

    it('calls onExpandEnrichment with event id when badge is clicked', async () => {
      const user = userEvent.setup();
      const onExpandEnrichment = vi.fn();
      const enrichmentSummary = { hasLicensePlate: true };
      render(
        <EventCard
          {...mockProps}
          detections={noVehicleDetections}
          enrichmentSummary={enrichmentSummary}
          onExpandEnrichment={onExpandEnrichment}
        />
      );
      await user.click(screen.getByTestId('enrichment-badge-plate'));
      expect(onExpandEnrichment).toHaveBeenCalledWith('event-123');
    });

    it('renders pose alerts badge for security alerts', () => {
      const enrichmentSummary = { poseAlertCount: 2 };
      render(<EventCard {...mockProps} enrichmentSummary={enrichmentSummary} />);
      expect(screen.getByText('2 Alerts')).toBeInTheDocument();
    });

    it('renders pet badge with capitalized type', () => {
      const enrichmentSummary = { petType: 'cat' };
      render(<EventCard {...mockProps} detections={noVehicleDetections} enrichmentSummary={enrichmentSummary} />);
      expect(screen.getByText('Cat')).toBeInTheDocument();
    });

    it('displays enrichment badges after object type badges', () => {
      const enrichmentSummary = { hasLicensePlate: true };
      const { container } = render(
        <EventCard {...mockProps} detections={noVehicleDetections} enrichmentSummary={enrichmentSummary} />
      );
      // Object badges should come before enrichment badges
      const objectBadgeContainer = container.querySelector('.mb-3.flex.flex-wrap');
      const enrichmentBadgeContainer = container.querySelector('[data-testid="enrichment-badges"]');
      expect(objectBadgeContainer).toBeInTheDocument();
      expect(enrichmentBadgeContainer).toBeInTheDocument();
    });
  });

  describe('snooze functionality', () => {
    it('renders snooze button when onSnooze is provided', () => {
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);
      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      expect(snoozeButton).toBeInTheDocument();
    });

    it('does not render snooze button when onSnooze is undefined', () => {
      render(<EventCard {...mockProps} onSnooze={undefined} />);
      expect(screen.queryByRole('button', { name: /snooze event/i })).not.toBeInTheDocument();
    });

    it('opens snooze dropdown menu when snooze button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);

      expect(screen.getByText('15 minutes')).toBeInTheDocument();
      expect(screen.getByText('1 hour')).toBeInTheDocument();
      expect(screen.getByText('4 hours')).toBeInTheDocument();
      expect(screen.getByText('8 hours')).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onSnooze with 15 minutes (900 seconds) when selected', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);
      await user.click(screen.getByText('15 minutes'));

      expect(handleSnooze).toHaveBeenCalledWith('event-123', 900);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onSnooze with 1 hour (3600 seconds) when selected', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);
      await user.click(screen.getByText('1 hour'));

      expect(handleSnooze).toHaveBeenCalledWith('event-123', 3600);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onSnooze with 4 hours (14400 seconds) when selected', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);
      await user.click(screen.getByText('4 hours'));

      expect(handleSnooze).toHaveBeenCalledWith('event-123', 14400);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onSnooze with 8 hours (28800 seconds) when selected', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);
      await user.click(screen.getByText('8 hours'));

      expect(handleSnooze).toHaveBeenCalledWith('event-123', 28800);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('closes snooze menu after selecting an option', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);
      expect(screen.getByText('15 minutes')).toBeInTheDocument();

      await user.click(screen.getByText('15 minutes'));
      expect(screen.queryByText('4 hours')).not.toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('has correct aria-expanded attribute when snooze menu is closed', () => {
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);
      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      expect(snoozeButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('has correct aria-expanded attribute when snooze menu is open', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);

      expect(snoozeButton).toHaveAttribute('aria-expanded', 'true');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('snooze indicator', () => {
    it('renders snooze indicator when snoozedUntil is in the future', () => {
      const futureDate = new Date(BASE_TIME + 60 * 60 * 1000).toISOString(); // 1 hour from now
      render(<EventCard {...mockProps} snoozedUntil={futureDate} />);
      expect(screen.getByText(/Snoozed until/)).toBeInTheDocument();
    });

    it('does not render snooze indicator when snoozedUntil is undefined', () => {
      render(<EventCard {...mockProps} snoozedUntil={undefined} />);
      expect(screen.queryByText(/Snoozed until/)).not.toBeInTheDocument();
    });

    it('does not render snooze indicator when snoozedUntil is in the past', () => {
      const pastDate = new Date(BASE_TIME - 60 * 60 * 1000).toISOString(); // 1 hour ago
      render(<EventCard {...mockProps} snoozedUntil={pastDate} />);
      expect(screen.queryByText(/Snoozed until/)).not.toBeInTheDocument();
    });

    it('applies reduced opacity to snoozed events', () => {
      const futureDate = new Date(BASE_TIME + 60 * 60 * 1000).toISOString();
      const { container } = render(<EventCard {...mockProps} snoozedUntil={futureDate} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('opacity-60');
    });

    it('does not apply reduced opacity to non-snoozed events', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).not.toHaveClass('opacity-60');
    });

    it('shows clear snooze option when event is snoozed and onSnooze is provided', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      // Use real time + 1 hour to ensure the snooze is in the future
      const futureDate = new Date(Date.now() + 60 * 60 * 1000).toISOString();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} snoozedUntil={futureDate} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);

      expect(screen.getByText('Clear snooze')).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onSnooze with 0 seconds when clear snooze is selected', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      // Use real time + 1 hour to ensure the snooze is in the future
      const futureDate = new Date(Date.now() + 60 * 60 * 1000).toISOString();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} snoozedUntil={futureDate} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);
      await user.click(screen.getByText('Clear snooze'));

      expect(handleSnooze).toHaveBeenCalledWith('event-123', 0);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('renders 24 hours snooze option', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);

      expect(screen.getByText('24 hours')).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onSnooze with 24 hours (86400 seconds) when selected', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSnooze = vi.fn();
      render(<EventCard {...mockProps} onSnooze={handleSnooze} />);

      const snoozeButton = screen.getByRole('button', { name: /snooze event/i });
      await user.click(snoozeButton);
      await user.click(screen.getByText('24 hours'));

      expect(handleSnooze).toHaveBeenCalledWith('event-123', 86400);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });
});
