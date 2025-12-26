import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EventCard, { type Detection, type EventCardProps } from './EventCard';

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
    vi.useFakeTimers();
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('basic rendering', () => {
    it('renders component with required props', () => {
      render(<EventCard {...mockProps} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Person detected approaching the front entrance')).toBeInTheDocument();
    });

    it('renders camera name', () => {
      render(<EventCard {...mockProps} />);
      const heading = screen.getByRole('heading', { name: 'Front Door' });
      expect(heading).toBeInTheDocument();
      expect(heading.tagName).toBe('H3');
    });

    it('renders summary text', () => {
      render(<EventCard {...mockProps} />);
      const summary = screen.getByText('Person detected approaching the front entrance');
      expect(summary).toBeInTheDocument();
      expect(summary.tagName).toBe('P');
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

    it('renders multiple detections', () => {
      const multipleDetections: Detection[] = [
        { label: 'person', confidence: 0.95 },
        { label: 'car', confidence: 0.87 },
        { label: 'dog', confidence: 0.72 },
        { label: 'package', confidence: 0.91 },
      ];
      const eventWithMultiple = { ...mockProps, detections: multipleDetections };
      render(<EventCard {...eventWithMultiple} />);

      expect(screen.getByText('Detections (4)')).toBeInTheDocument();
      expect(screen.getByText('person')).toBeInTheDocument();
      expect(screen.getByText('car')).toBeInTheDocument();
      expect(screen.getByText('dog')).toBeInTheDocument();
      expect(screen.getByText('package')).toBeInTheDocument();
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
      expect(screen.getByText('95%')).toBeInTheDocument();
      expect(screen.getByText('87%')).toBeInTheDocument();
    });

    it('rounds confidence to nearest integer', () => {
      const detectionsWithRounding: Detection[] = [
        { label: 'person', confidence: 0.956 }, // Should round to 96%
        { label: 'car', confidence: 0.874 }, // Should round to 87%
        { label: 'dog', confidence: 0.725 }, // Should round to 73%
      ];
      const eventWithRounding = { ...mockProps, detections: detectionsWithRounding };
      render(<EventCard {...eventWithRounding} />);

      expect(screen.getByText('96%')).toBeInTheDocument();
      expect(screen.getByText('87%')).toBeInTheDocument();
      expect(screen.getByText('73%')).toBeInTheDocument();
    });

    it('handles 100% confidence', () => {
      const perfectDetection: Detection[] = [{ label: 'person', confidence: 1.0 }];
      const eventWithPerfect = { ...mockProps, detections: perfectDetection };
      render(<EventCard {...eventWithPerfect} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('handles 0% confidence', () => {
      const zeroDetection: Detection[] = [{ label: 'person', confidence: 0.0 }];
      const eventWithZero = { ...mockProps, detections: zeroDetection };
      render(<EventCard {...eventWithZero} />);
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('handles low confidence values', () => {
      const lowConfidence: Detection[] = [{ label: 'person', confidence: 0.05 }];
      const eventWithLow = { ...mockProps, detections: lowConfidence };
      render(<EventCard {...eventWithLow} />);
      expect(screen.getByText('5%')).toBeInTheDocument();
    });
  });

  describe('thumbnail rendering', () => {
    it('renders thumbnail when thumbnail_url is provided', () => {
      render(<EventCard {...mockProps} />);
      const images = screen.getAllByRole('img');
      expect(images.length).toBeGreaterThan(0);
    });

    it('renders DetectionImage when detections have bounding boxes', () => {
      render(<EventCard {...mockProps} />);
      const altText = screen.getByAltText(/Front Door detection at/);
      expect(altText).toBeInTheDocument();
    });

    it('renders plain img when detections have no bounding boxes', () => {
      const detectionsNoBbox: Detection[] = [
        { label: 'person', confidence: 0.95 },
        { label: 'car', confidence: 0.87 },
      ];
      const eventNoBbox = { ...mockProps, detections: detectionsNoBbox };
      render(<EventCard {...eventNoBbox} />);
      const altText = screen.getByAltText(/Front Door at/);
      expect(altText).toBeInTheDocument();
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

    it('passes showLabels=true to DetectionImage', () => {
      render(<EventCard {...mockProps} />);
      // DetectionImage will be rendered, so alt text should exist
      const altText = screen.getByAltText(/Front Door detection at/);
      expect(altText).toBeInTheDocument();
    });

    it('passes showConfidence=true to DetectionImage', () => {
      render(<EventCard {...mockProps} />);
      // DetectionImage will be rendered with confidence
      const altText = screen.getByAltText(/Front Door detection at/);
      expect(altText).toBeInTheDocument();
    });
  });

  describe('bounding box conversion', () => {
    it('converts detections with bounding boxes correctly', () => {
      render(<EventCard {...mockProps} />);
      // If conversion works, DetectionImage will be rendered
      const altText = screen.getByAltText(/Front Door detection at/);
      expect(altText).toBeInTheDocument();
    });

    it('filters out detections without bounding boxes', () => {
      const mixedDetections: Detection[] = [
        { label: 'person', confidence: 0.95, bbox: { x: 100, y: 100, width: 200, height: 300 } },
        { label: 'car', confidence: 0.87 }, // No bbox
        { label: 'dog', confidence: 0.72, bbox: { x: 300, y: 200, width: 150, height: 100 } },
      ];
      const eventMixed = { ...mockProps, detections: mixedDetections };
      render(<EventCard {...eventMixed} />);
      // DetectionImage should be used since some detections have bbox
      const altText = screen.getByAltText(/Front Door detection at/);
      expect(altText).toBeInTheDocument();
    });

    it('uses plain img when no detections have bounding boxes', () => {
      const noBboxDetections: Detection[] = [
        { label: 'person', confidence: 0.95 },
        { label: 'car', confidence: 0.87 },
      ];
      const eventNoBbox = { ...mockProps, detections: noBboxDetections };
      render(<EventCard {...eventNoBbox} />);
      // Should use plain img, not DetectionImage
      const altText = screen.getByAltText(/Front Door at/);
      expect(altText).toBeInTheDocument();
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

      vi.useFakeTimers();
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

      vi.useFakeTimers();
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

      vi.useFakeTimers();
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

      vi.useFakeTimers();
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

      vi.useFakeTimers();
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

      vi.useFakeTimers();
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
      // Get all direct children of the main card container
      const card = container.querySelector('.rounded-lg.border.border-gray-800');
      const children = card ? Array.from(card.children) : [];

      // Find indices of badges container and thumbnail container
      const badgesIndex = children.findIndex((el) =>
        el.classList.contains('flex') &&
        el.classList.contains('flex-wrap') &&
        el.textContent?.includes('Person')
      );
      const thumbnailIndex = children.findIndex((el) =>
        el.classList.contains('mb-3') &&
        el.querySelector('img')
      );

      // Badges should come before thumbnail
      expect(badgesIndex).toBeGreaterThan(-1);
      expect(thumbnailIndex).toBeGreaterThan(-1);
      expect(badgesIndex).toBeLessThan(thumbnailIndex);
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

  describe('risk score progress bar', () => {
    it('renders progress bar with correct label', () => {
      render(<EventCard {...mockProps} />);
      expect(screen.getByText('Risk Score')).toBeInTheDocument();
    });

    it('displays risk score as fraction', () => {
      render(<EventCard {...mockProps} />);
      expect(screen.getByText('45/100')).toBeInTheDocument();
    });

    it('renders progressbar with correct ARIA attributes', () => {
      render(<EventCard {...mockProps} />);
      const progressBar = screen.getByRole('progressbar', { name: 'Risk score: 45 out of 100' });
      expect(progressBar).toBeInTheDocument();
      expect(progressBar).toHaveAttribute('aria-valuenow', '45');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });

    it('sets progress bar width to match risk score', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={45} />);
      const progressFill = container.querySelector('[role="progressbar"] > div');
      expect(progressFill).toHaveStyle({ width: '45%' });
    });

    it('applies NVIDIA green color for low risk scores', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={15} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(118,\s*185,\s*0\)|#76B900/i);
    });

    it('applies NVIDIA yellow color for medium risk scores', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={45} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(255,\s*184,\s*0\)|#FFB800/i);
    });

    it('applies NVIDIA red color for high risk scores', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={72} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(231,\s*72,\s*86\)|#E74856/i);
    });

    it('applies red color for critical risk scores', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={88} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(239,\s*68,\s*68\)|#ef4444/i);
    });

    it('handles risk score of 0', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={0} />);
      const progressFill = container.querySelector('[role="progressbar"] > div');
      expect(progressFill).toHaveStyle({ width: '0%' });
      expect(screen.getByText('0/100')).toBeInTheDocument();
    });

    it('handles risk score of 100', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={100} />);
      const progressFill = container.querySelector('[role="progressbar"] > div');
      expect(progressFill).toHaveStyle({ width: '100%' });
      expect(screen.getByText('100/100')).toBeInTheDocument();
    });

    it('handles boundary risk score at 25', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={25} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill).toHaveStyle({ width: '25%' });
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(118,\s*185,\s*0\)|#76B900/i);
    });

    it('handles boundary risk score at 26', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={26} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill).toHaveStyle({ width: '26%' });
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(255,\s*184,\s*0\)|#FFB800/i);
    });

    it('handles boundary risk score at 50', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={50} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill).toHaveStyle({ width: '50%' });
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(255,\s*184,\s*0\)|#FFB800/i);
    });

    it('handles boundary risk score at 51', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={51} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill).toHaveStyle({ width: '51%' });
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(231,\s*72,\s*86\)|#E74856/i);
    });

    it('handles boundary risk score at 75', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={75} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill).toHaveStyle({ width: '75%' });
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(231,\s*72,\s*86\)|#E74856/i);
    });

    it('handles boundary risk score at 76', () => {
      const { container } = render(<EventCard {...mockProps} risk_score={76} />);
      const progressFill = container.querySelector('[role="progressbar"] > div') as HTMLElement;
      expect(progressFill).toHaveStyle({ width: '76%' });
      expect(progressFill?.style.backgroundColor).toMatch(/rgb\(239,\s*68,\s*68\)|#ef4444/i);
    });

    it('renders progress bar after object badges', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.querySelector('.rounded-lg.border');
      const children = card ? Array.from(card.children) : [];

      const badgesIndex = children.findIndex(
        (el) => el.classList.contains('flex') && el.textContent?.includes('Person')
      );
      const progressBarIndex = children.findIndex(
        (el) => el.querySelector('[role="progressbar"]') !== null
      );

      expect(badgesIndex).toBeGreaterThan(-1);
      expect(progressBarIndex).toBeGreaterThan(-1);
      expect(progressBarIndex).toBeGreaterThan(badgesIndex);
    });

    it('renders progress bar before thumbnail', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.querySelector('.rounded-lg.border');
      const children = card ? Array.from(card.children) : [];

      const progressBarIndex = children.findIndex(
        (el) => el.querySelector('[role="progressbar"]') !== null
      );
      const thumbnailIndex = children.findIndex((el) => el.querySelector('img') !== null);

      expect(progressBarIndex).toBeGreaterThan(-1);
      expect(thumbnailIndex).toBeGreaterThan(-1);
      expect(progressBarIndex).toBeLessThan(thumbnailIndex);
    });

    it('progress bar has transition animation', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const progressFill = container.querySelector('[role="progressbar"] > div');
      expect(progressFill).toHaveClass('transition-all', 'duration-500', 'ease-out');
    });

    it('progress bar container has correct styling', () => {
      render(<EventCard {...mockProps} />);
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveClass('h-2', 'w-full', 'overflow-hidden', 'rounded-full', 'bg-gray-800');
    });

    it('progress bar fill has correct styling', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const progressFill = container.querySelector('[role="progressbar"] > div');
      expect(progressFill).toHaveClass('h-full', 'rounded-full');
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

    it('handles very long summary text', () => {
      const longSummaryEvent = {
        ...mockProps,
        summary:
          'This is a very long summary that describes an extremely complex security event with multiple elements and detailed analysis of what has occurred at this particular location and time with extensive contextual information.',
      };
      render(<EventCard {...longSummaryEvent} />);
      const summary = screen.getByText(/This is a very long summary/);
      expect(summary).toBeInTheDocument();
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

      vi.useFakeTimers();
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
      expect(screen.getByText('Front Door Main Entrance Camera Position Alpha')).toBeInTheDocument();
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
      render(<EventCard {...eventWithDuration} />);
      expect(screen.getByText(/Duration:/)).toBeInTheDocument();
      expect(screen.getByText(/2m 30s/)).toBeInTheDocument();
    });

    it('displays "ongoing" for events without ended_at', () => {
      const ongoingEvent = {
        ...mockProps,
        started_at: new Date(BASE_TIME - 2 * 60 * 1000).toISOString(), // 2 minutes ago
        ended_at: null,
      };
      render(<EventCard {...ongoingEvent} />);
      expect(screen.getByText(/Duration:/)).toBeInTheDocument();
      expect(screen.getByText(/ongoing/)).toBeInTheDocument();
    });

    it('displays duration with "(ongoing)" suffix for older ongoing events', () => {
      const olderOngoingEvent = {
        ...mockProps,
        started_at: new Date(BASE_TIME - 10 * 60 * 1000).toISOString(), // 10 minutes ago
        ended_at: null,
      };
      render(<EventCard {...olderOngoingEvent} />);
      expect(screen.getByText(/Duration:/)).toBeInTheDocument();
      expect(screen.getByText(/10m.*ongoing/)).toBeInTheDocument();
    });

    it('does not display duration when started_at is not provided', () => {
      render(<EventCard {...mockProps} />);
      expect(screen.queryByText(/Duration:/)).not.toBeInTheDocument();
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
      render(<EventCard {...eventWithEndedAt} />);
      expect(screen.getByText(/Duration:/)).toBeInTheDocument();
    });
  });

  describe('layout and styling', () => {
    it('applies NVIDIA theme colors', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('bg-[#1F1F1F]');
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

    it('applies padding', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('p-4');
    });
  });

  describe('color-coded left border', () => {
    it('applies NVIDIA green left border for low risk events', () => {
      const lowRiskEvent = { ...mockProps, risk_score: 15 };
      const { container } = render(<EventCard {...lowRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-4', 'border-l-risk-low');
    });

    it('applies NVIDIA yellow left border for medium risk events', () => {
      const mediumRiskEvent = { ...mockProps, risk_score: 45 };
      const { container } = render(<EventCard {...mediumRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-4', 'border-l-risk-medium');
    });

    it('applies NVIDIA red left border for high risk events', () => {
      const highRiskEvent = { ...mockProps, risk_score: 72 };
      const { container } = render(<EventCard {...highRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-4', 'border-l-risk-high');
    });

    it('applies red left border for critical risk events', () => {
      const criticalRiskEvent = { ...mockProps, risk_score: 88 };
      const { container } = render(<EventCard {...criticalRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-4', 'border-l-red-500');
    });

    it('applies correct border width class', () => {
      const { container } = render(<EventCard {...mockProps} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-4');
    });

    it('applies NVIDIA green left border at risk score boundary (25)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 25 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-risk-low');
    });

    it('applies NVIDIA yellow left border at risk score boundary (26)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 26 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-risk-medium');
    });

    it('applies NVIDIA yellow left border at risk score boundary (50)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 50 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-risk-medium');
    });

    it('applies NVIDIA red left border at risk score boundary (51)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 51 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-risk-high');
    });

    it('applies NVIDIA red left border at risk score boundary (75)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 75 };
      const { container } = render(<EventCard {...boundaryEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-risk-high');
    });

    it('applies critical red left border at risk score boundary (76)', () => {
      const boundaryEvent = { ...mockProps, risk_score: 76 };
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

    it('applies NVIDIA green left border at minimum risk score (0)', () => {
      const minRiskEvent = { ...mockProps, risk_score: 0 };
      const { container } = render(<EventCard {...minRiskEvent} />);
      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('border-l-risk-low');
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
      expect(screen.getByText('Person detected approaching the front entrance')).toBeInTheDocument();
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

      vi.useFakeTimers();
      vi.setSystemTime(BASE_TIME);
    });
  });
});
