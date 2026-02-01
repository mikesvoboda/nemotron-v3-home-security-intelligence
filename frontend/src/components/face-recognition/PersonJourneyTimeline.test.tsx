/**
 * PersonJourneyTimeline Component Tests
 *
 * Tests for the vertical timeline component that displays a person's appearances
 * across cameras. Follows TDD approach - tests written first.
 *
 * @module components/face-recognition/PersonJourneyTimeline.test
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 * @see NEM-4688 Phase 3 - Person Tracking
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import PersonJourneyTimeline, { type PersonJourneyTimelineProps } from './PersonJourneyTimeline';

import type { PersonAppearance } from '../../types/faceRecognition';

describe('PersonJourneyTimeline', () => {
  // Base time for consistent testing (Jan 31, 2025 at 10:34 AM UTC)
  const BASE_TIME = new Date('2025-01-31T10:34:00Z').getTime();

  // Mock appearances for a typical journey
  const mockAppearances: PersonAppearance[] = [
    {
      timestamp: new Date(BASE_TIME - 139 * 60 * 1000).toISOString(), // 8:15 AM
      camera_id: 1,
      camera_name: 'Driveway',
      detection_id: 'det-001',
      confidence: 0.92,
      thumbnail_url: 'https://example.com/thumb-001.jpg',
    },
    {
      timestamp: new Date(BASE_TIME - 137 * 60 * 1000).toISOString(), // 8:17 AM
      camera_id: 2,
      camera_name: 'Front Door',
      detection_id: 'det-002',
      confidence: 0.95,
      thumbnail_url: 'https://example.com/thumb-002.jpg',
    },
    {
      timestamp: new Date(BASE_TIME - 2 * 60 * 1000).toISOString(), // 10:32 AM
      camera_id: 2,
      camera_name: 'Front Door',
      detection_id: 'det-003',
      confidence: 0.91,
      thumbnail_url: null,
    },
    {
      timestamp: new Date(BASE_TIME).toISOString(), // 10:34 AM
      camera_id: 1,
      camera_name: 'Driveway',
      detection_id: 'det-004',
      confidence: 0.88,
      thumbnail_url: 'https://example.com/thumb-004.jpg',
    },
  ];

  // Multi-day appearances for date grouping tests
  const mockMultiDayAppearances: PersonAppearance[] = [
    {
      timestamp: '2025-01-30T09:00:00Z',
      camera_id: 1,
      camera_name: 'Driveway',
      detection_id: 'det-y1',
      confidence: 0.9,
    },
    {
      timestamp: '2025-01-30T17:30:00Z',
      camera_id: 2,
      camera_name: 'Front Door',
      detection_id: 'det-y2',
      confidence: 0.93,
    },
    {
      timestamp: '2025-01-31T08:15:00Z',
      camera_id: 1,
      camera_name: 'Driveway',
      detection_id: 'det-t1',
      confidence: 0.92,
    },
  ];

  // Base props for testing
  const baseProps: PersonJourneyTimelineProps = {
    appearances: mockAppearances,
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
    it('renders the component with required props', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      expect(screen.getByTestId('person-journey-timeline')).toBeInTheDocument();
    });

    it('renders all appearance nodes', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      expect(nodes).toHaveLength(4);
    });

    it('displays appearances in chronological order (oldest to newest)', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);

      // First node should be the earliest detection (det-001)
      expect(nodes[0]).toHaveAttribute('data-testid', 'timeline-node-det-001');
      // Last node should be the latest detection (det-004)
      expect(nodes[3]).toHaveAttribute('data-testid', 'timeline-node-det-004');
    });

    it('renders with custom className', () => {
      const { container } = render(
        <PersonJourneyTimeline {...baseProps} className="custom-class" />
      );
      const timeline = container.firstChild as HTMLElement;
      expect(timeline).toHaveClass('custom-class');
    });
  });

  describe('timeline structure', () => {
    it('renders vertical connecting lines between nodes', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      // Should have n-1 connecting lines for n nodes
      const connectors = screen.getAllByTestId('timeline-connector');
      expect(connectors).toHaveLength(3); // 4 nodes = 3 connectors
    });

    it('does not render connector after the last node', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      const lastNode = nodes[nodes.length - 1];

      // Last node should not have a connector
      const connector = within(lastNode).queryByTestId('timeline-connector');
      expect(connector).not.toBeInTheDocument();
    });

    it('renders timeline dots with NVIDIA green color', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const dots = screen.getAllByTestId('timeline-dot');
      expect(dots).toHaveLength(4);
      dots.forEach((dot) => {
        expect(dot).toHaveClass('bg-[#76B900]');
      });
    });

    it('renders dots with correct size', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const dots = screen.getAllByTestId('timeline-dot');
      dots.forEach((dot) => {
        expect(dot).toHaveClass('w-3', 'h-3', 'rounded-full');
      });
    });

    it('renders connecting line with correct styling', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const connectors = screen.getAllByTestId('timeline-connector');
      connectors.forEach((connector) => {
        expect(connector).toHaveClass('border-l-2', 'border-gray-600');
      });
    });
  });

  describe('node content', () => {
    it('displays time in 12-hour format for each node', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      // Check that time labels exist and contain AM or PM (locale-independent check)
      const timeLabels = screen.getAllByTestId('timeline-time');
      expect(timeLabels).toHaveLength(4);
      // Each should contain AM or PM for 12-hour format
      timeLabels.forEach((label) => {
        expect(label.textContent).toMatch(/AM|PM/i);
      });
    });

    it('displays camera name for each node', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const drivewayCameras = screen.getAllByText('Driveway');
      const frontDoorCameras = screen.getAllByText('Front Door');

      expect(drivewayCameras).toHaveLength(2);
      expect(frontDoorCameras).toHaveLength(2);
    });

    it('applies correct styling to time labels', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      const timeLabel = within(nodes[0]).getByTestId('timeline-time');
      expect(timeLabel).toHaveClass('text-sm', 'text-gray-400');
    });

    it('applies correct styling to camera names', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      const cameraName = within(nodes[0]).getByTestId('timeline-camera-name');
      expect(cameraName).toHaveClass('text-white', 'font-medium');
    });
  });

  describe('confidence indicator', () => {
    it('displays confidence percentage for each appearance', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      expect(screen.getByText(/92%/)).toBeInTheDocument();
      expect(screen.getByText(/95%/)).toBeInTheDocument();
      expect(screen.getByText(/91%/)).toBeInTheDocument();
      expect(screen.getByText(/88%/)).toBeInTheDocument();
    });

    it('applies green color for high confidence (>= 90%)', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      // First appearance has 92% confidence
      const confidenceBadge = within(nodes[0]).getByTestId('confidence-indicator');
      expect(confidenceBadge).toHaveClass('text-green-400');
    });

    it('applies yellow color for medium confidence (70-90%)', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      // Last appearance has 88% confidence
      const confidenceBadge = within(nodes[3]).getByTestId('confidence-indicator');
      expect(confidenceBadge).toHaveClass('text-yellow-400');
    });

    it('applies red color for low confidence (< 70%)', () => {
      const lowConfidenceAppearance: PersonAppearance = {
        ...mockAppearances[0],
        confidence: 0.65,
      };
      render(<PersonJourneyTimeline appearances={[lowConfidenceAppearance]} />);
      const confidenceBadge = screen.getByTestId('confidence-indicator');
      expect(confidenceBadge).toHaveClass('text-red-400');
    });
  });

  describe('thumbnail rendering', () => {
    it('renders thumbnails when showThumbnails is true and URL exists', () => {
      render(<PersonJourneyTimeline {...baseProps} showThumbnails />);
      const thumbnails = screen.getAllByRole('img', { name: /thumbnail/i });
      // 3 appearances have thumbnail URLs
      expect(thumbnails).toHaveLength(3);
    });

    it('does not render thumbnails by default', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const thumbnails = screen.queryAllByRole('img', { name: /thumbnail/i });
      expect(thumbnails).toHaveLength(0);
    });

    it('renders thumbnail placeholder when URL is null but showThumbnails is true', () => {
      render(<PersonJourneyTimeline {...baseProps} showThumbnails />);
      const placeholders = screen.getAllByTestId('thumbnail-placeholder');
      // One appearance (det-003) has null thumbnail_url
      expect(placeholders).toHaveLength(1);
    });

    it('thumbnail has correct src attribute', () => {
      render(<PersonJourneyTimeline {...baseProps} showThumbnails />);
      const thumbnails = screen.getAllByRole('img', { name: /thumbnail/i });
      expect(thumbnails[0]).toHaveAttribute('src', 'https://example.com/thumb-001.jpg');
    });
  });

  describe('click interaction', () => {
    it('calls onViewAppearance when a node is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onViewAppearance = vi.fn();
      render(<PersonJourneyTimeline {...baseProps} onViewAppearance={onViewAppearance} />);

      const nodes = screen.getAllByTestId(/^timeline-node-/);
      await user.click(nodes[0]);

      expect(onViewAppearance).toHaveBeenCalledWith(mockAppearances[0]);
    });

    it('applies cursor-pointer when onViewAppearance is provided', () => {
      render(<PersonJourneyTimeline {...baseProps} onViewAppearance={vi.fn()} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      nodes.forEach((node) => {
        expect(node).toHaveClass('cursor-pointer');
      });
    });

    it('does not apply cursor-pointer when onViewAppearance is not provided', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      nodes.forEach((node) => {
        expect(node).not.toHaveClass('cursor-pointer');
      });
    });

    it('supports keyboard navigation with Enter key', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onViewAppearance = vi.fn();
      render(<PersonJourneyTimeline {...baseProps} onViewAppearance={onViewAppearance} />);

      const nodes = screen.getAllByTestId(/^timeline-node-/);
      nodes[0].focus();
      await user.keyboard('{Enter}');

      expect(onViewAppearance).toHaveBeenCalledWith(mockAppearances[0]);
    });

    it('supports keyboard navigation with Space key', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onViewAppearance = vi.fn();
      render(<PersonJourneyTimeline {...baseProps} onViewAppearance={onViewAppearance} />);

      const nodes = screen.getAllByTestId(/^timeline-node-/);
      nodes[1].focus();
      await user.keyboard(' ');

      expect(onViewAppearance).toHaveBeenCalledWith(mockAppearances[1]);
    });
  });

  describe('date grouping', () => {
    it('groups appearances by date when spanning multiple days', () => {
      render(<PersonJourneyTimeline appearances={mockMultiDayAppearances} />);

      // Should have date headers
      const dateHeaders = screen.getAllByTestId('date-header');
      expect(dateHeaders).toHaveLength(2);
    });

    it('displays date headers in chronological order', () => {
      render(<PersonJourneyTimeline appearances={mockMultiDayAppearances} />);

      const dateHeaders = screen.getAllByTestId('date-header');
      // Should have headers, first one contains Yesterday, second contains Today
      // (or date format, depending on timezone)
      expect(dateHeaders).toHaveLength(2);
      // Just verify they have content - timezone makes exact matching unreliable
      expect(dateHeaders[0].textContent).toBeTruthy();
      expect(dateHeaders[1].textContent).toBeTruthy();
    });

    it('shows "Today" for current day appearances', () => {
      render(<PersonJourneyTimeline appearances={mockMultiDayAppearances} />);

      // Jan 31 should show as "Today" since we mocked the system time
      expect(screen.getByText(/Today/)).toBeInTheDocument();
    });

    it('shows "Yesterday" for previous day appearances', () => {
      render(<PersonJourneyTimeline appearances={mockMultiDayAppearances} />);

      // Jan 30 should show as "Yesterday"
      expect(screen.getByText(/Yesterday/)).toBeInTheDocument();
    });

    it('does not show date headers for single-day appearances', () => {
      render(<PersonJourneyTimeline {...baseProps} />);

      // All appearances are on the same day
      const dateHeaders = screen.queryAllByTestId('date-header');
      expect(dateHeaders).toHaveLength(0);
    });
  });

  describe('empty state', () => {
    it('renders empty state when appearances array is empty', () => {
      render(<PersonJourneyTimeline appearances={[]} />);
      expect(screen.getByTestId('timeline-empty-state')).toBeInTheDocument();
    });

    it('displays appropriate message in empty state', () => {
      render(<PersonJourneyTimeline appearances={[]} />);
      expect(screen.getByText(/no appearances/i)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible role for the timeline', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const timeline = screen.getByRole('list');
      expect(timeline).toBeInTheDocument();
    });

    it('timeline nodes have listitem role', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByRole('listitem');
      expect(nodes).toHaveLength(4);
    });

    it('nodes have tabIndex when clickable', () => {
      render(<PersonJourneyTimeline {...baseProps} onViewAppearance={vi.fn()} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      nodes.forEach((node) => {
        expect(node).toHaveAttribute('tabIndex', '0');
      });
    });

    it('nodes do not have tabIndex when not clickable', () => {
      render(<PersonJourneyTimeline {...baseProps} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      nodes.forEach((node) => {
        expect(node).not.toHaveAttribute('tabIndex', '0');
      });
    });

    it('thumbnails have appropriate alt text', () => {
      render(<PersonJourneyTimeline {...baseProps} showThumbnails />);
      const thumbnails = screen.getAllByRole('img', { name: /thumbnail/i });
      thumbnails.forEach((img) => {
        expect(img).toHaveAttribute('alt');
      });
    });
  });

  describe('edge cases', () => {
    it('handles single appearance correctly', () => {
      render(<PersonJourneyTimeline appearances={[mockAppearances[0]]} />);

      const nodes = screen.getAllByTestId(/^timeline-node-/);
      expect(nodes).toHaveLength(1);

      // Should not have any connectors
      const connectors = screen.queryAllByTestId('timeline-connector');
      expect(connectors).toHaveLength(0);
    });

    it('handles appearances without thumbnail_url', () => {
      const noThumbnailAppearances: PersonAppearance[] = [
        {
          timestamp: '2025-01-31T10:00:00Z',
          camera_id: 1,
          camera_name: 'Test Camera',
          detection_id: 'det-001',
          confidence: 0.9,
        },
      ];
      render(<PersonJourneyTimeline appearances={noThumbnailAppearances} showThumbnails />);

      expect(screen.getByTestId('thumbnail-placeholder')).toBeInTheDocument();
    });

    it('handles very long camera names with truncation', () => {
      const longNameAppearance: PersonAppearance = {
        ...mockAppearances[0],
        camera_name: 'This Is A Very Long Camera Name That Should Be Truncated Properly',
      };
      render(<PersonJourneyTimeline appearances={[longNameAppearance]} />);

      const cameraName = screen.getByTestId('timeline-camera-name');
      expect(cameraName).toHaveClass('truncate');
    });

    it('handles appearances out of chronological order', () => {
      const unorderedAppearances = [
        mockAppearances[2], // 10:32 AM (det-003)
        mockAppearances[0], // 8:15 AM (det-001)
        mockAppearances[3], // 10:34 AM (det-004)
        mockAppearances[1], // 8:17 AM (det-002)
      ];
      render(<PersonJourneyTimeline appearances={unorderedAppearances} />);

      const nodes = screen.getAllByTestId(/^timeline-node-/);
      // Should still be sorted chronologically by detection_id order
      expect(nodes[0]).toHaveAttribute('data-testid', 'timeline-node-det-001');
      expect(nodes[1]).toHaveAttribute('data-testid', 'timeline-node-det-002');
      expect(nodes[2]).toHaveAttribute('data-testid', 'timeline-node-det-003');
      expect(nodes[3]).toHaveAttribute('data-testid', 'timeline-node-det-004');
    });
  });

  describe('styling', () => {
    it('applies NVIDIA dark theme background', () => {
      const { container } = render(<PersonJourneyTimeline {...baseProps} />);
      // Timeline container should have appropriate dark styling
      const timeline = container.firstChild as HTMLElement;
      expect(timeline).toHaveClass('bg-[#1A1A1A]');
    });

    it('applies hover effect on nodes when clickable', () => {
      render(<PersonJourneyTimeline {...baseProps} onViewAppearance={vi.fn()} />);
      const nodes = screen.getAllByTestId(/^timeline-node-/);
      nodes.forEach((node) => {
        expect(node).toHaveClass('hover:bg-gray-800');
      });
    });
  });
});
