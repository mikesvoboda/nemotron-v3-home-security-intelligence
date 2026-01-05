import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EntityTimeline, { type EntityTimelineProps, type EntityAppearance } from './EntityTimeline';

describe('EntityTimeline', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock appearances for testing
  const mockAppearances: EntityAppearance[] = [
    {
      detection_id: 'det-001',
      camera_id: 'front_door',
      camera_name: 'Front Door',
      timestamp: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(), // 5 mins ago
      thumbnail_url: 'https://example.com/thumb1.jpg',
      similarity_score: 0.95,
      attributes: { color: 'blue' },
    },
    {
      detection_id: 'det-002',
      camera_id: 'back_yard',
      camera_name: 'Back Yard',
      timestamp: new Date(BASE_TIME - 30 * 60 * 1000).toISOString(), // 30 mins ago
      thumbnail_url: 'https://example.com/thumb2.jpg',
      similarity_score: 0.88,
      attributes: {},
    },
    {
      detection_id: 'det-003',
      camera_id: 'garage',
      camera_name: 'Garage',
      timestamp: new Date(BASE_TIME - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      thumbnail_url: null,
      similarity_score: 0.92,
      attributes: {},
    },
  ];

  const mockProps: EntityTimelineProps = {
    entity_id: 'entity-abc123',
    entity_type: 'person',
    appearances: mockAppearances,
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
    it('renders timeline with appearances', () => {
      render(<EntityTimeline {...mockProps} />);
      expect(screen.getByText('Appearance Timeline')).toBeInTheDocument();
    });

    it('renders correct number of timeline items', () => {
      render(<EntityTimeline {...mockProps} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Back Yard')).toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
    });

    it('renders entity type label', () => {
      render(<EntityTimeline {...mockProps} />);
      expect(screen.getByText(/person/i)).toBeInTheDocument();
    });

    it('renders appearance count', () => {
      render(<EntityTimeline {...mockProps} />);
      expect(screen.getByText(/3.*person.*appearances/i)).toBeInTheDocument();
    });
  });

  describe('timeline items', () => {
    it('displays camera names for each appearance', () => {
      render(<EntityTimeline {...mockProps} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Back Yard')).toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
    });

    it('displays timestamps for each appearance', () => {
      render(<EntityTimeline {...mockProps} />);
      expect(screen.getByText(/5 minutes ago/)).toBeInTheDocument();
      expect(screen.getByText(/30 minutes ago/)).toBeInTheDocument();
      expect(screen.getByText(/2 hours ago/)).toBeInTheDocument();
    });

    it('displays similarity scores when available', () => {
      render(<EntityTimeline {...mockProps} />);
      expect(screen.getByText(/95%/)).toBeInTheDocument();
      expect(screen.getByText(/88%/)).toBeInTheDocument();
      expect(screen.getByText(/92%/)).toBeInTheDocument();
    });

    it('renders thumbnails when available', () => {
      render(<EntityTimeline {...mockProps} />);
      const images = screen.getAllByRole('img');
      expect(images.length).toBeGreaterThanOrEqual(2); // thumb1 and thumb2
    });

    it('renders placeholder when thumbnail is null', () => {
      render(<EntityTimeline {...mockProps} />);
      const placeholders = screen.getAllByTestId('timeline-placeholder');
      expect(placeholders.length).toBe(1); // Garage has no thumbnail
    });

    it('uses camera_id as fallback when camera_name is null', () => {
      const appearancesWithNullName = [
        {
          ...mockAppearances[0],
          camera_name: null,
        },
      ];
      render(<EntityTimeline {...mockProps} appearances={appearancesWithNullName} />);
      expect(screen.getByText('front_door')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('displays empty message when no appearances', () => {
      render(<EntityTimeline {...mockProps} appearances={[]} />);
      expect(screen.getByText(/No appearances recorded/i)).toBeInTheDocument();
    });

    it('renders timeline header even with no appearances', () => {
      render(<EntityTimeline {...mockProps} appearances={[]} />);
      expect(screen.getByText('Appearance Timeline')).toBeInTheDocument();
    });
  });

  describe('chronological order', () => {
    it('displays appearances in chronological order (most recent first)', () => {
      render(<EntityTimeline {...mockProps} />);

      // Get all camera names in order
      const cameraNames = screen
        .getAllByText(/Front Door|Back Yard|Garage/)
        .map((el) => el.textContent);

      // Should be in order: Front Door (5 mins), Back Yard (30 mins), Garage (2 hours)
      expect(cameraNames[0]).toBe('Front Door');
      expect(cameraNames[1]).toBe('Back Yard');
      expect(cameraNames[2]).toBe('Garage');
    });
  });

  describe('vehicle entity', () => {
    it('renders vehicle timeline correctly', () => {
      const vehicleProps = { ...mockProps, entity_type: 'vehicle' as const };
      render(<EntityTimeline {...vehicleProps} />);
      expect(screen.getByText(/vehicle/i)).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies NVIDIA theme colors', () => {
      const { container } = render(<EntityTimeline {...mockProps} />);
      const header = container.querySelector('.text-\\[\\#76B900\\]');
      expect(header).toBeInTheDocument();
    });

    it('applies timeline connector styling', () => {
      const { container } = render(<EntityTimeline {...mockProps} />);
      // Should have vertical line connectors between items
      const connectors = container.querySelectorAll('.border-l-2');
      expect(connectors.length).toBeGreaterThan(0);
    });

    it('applies dark theme background', () => {
      const { container } = render(<EntityTimeline {...mockProps} />);
      expect(container.firstChild).toHaveClass('bg-[#1F1F1F]');
    });
  });

  describe('accessibility', () => {
    it('uses semantic list for timeline items', () => {
      render(<EntityTimeline {...mockProps} />);
      const list = screen.getByRole('list');
      expect(list).toBeInTheDocument();
    });

    it('has appropriate heading level for title', () => {
      render(<EntityTimeline {...mockProps} />);
      const heading = screen.getByRole('heading', { name: /Appearance Timeline/i });
      expect(heading).toBeInTheDocument();
    });

    it('thumbnails have alt text', () => {
      render(<EntityTimeline {...mockProps} />);
      const images = screen.getAllByRole('img');
      images.forEach((img) => {
        expect(img).toHaveAttribute('alt');
      });
    });
  });

  describe('edge cases', () => {
    it('handles single appearance', () => {
      const singleAppearance = { ...mockProps, appearances: [mockAppearances[0]] };
      render(<EntityTimeline {...singleAppearance} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText(/1.*person.*appearance$/i)).toBeInTheDocument();
    });

    it('handles many appearances', () => {
      const manyAppearances = Array(20)
        .fill(null)
        .map((_, i) => ({
          ...mockAppearances[0],
          detection_id: `det-${i}`,
          timestamp: new Date(BASE_TIME - i * 60 * 1000).toISOString(),
        }));
      render(<EntityTimeline {...mockProps} appearances={manyAppearances} />);
      expect(screen.getByText(/20.*person.*appearances/i)).toBeInTheDocument();
    });

    it('handles null similarity_score', () => {
      const noScore = [
        {
          ...mockAppearances[0],
          similarity_score: null,
        },
      ];
      render(<EntityTimeline {...mockProps} appearances={noScore} />);
      // Should not crash and should not show percentage for this item
      expect(screen.getByText('Front Door')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<EntityTimeline {...mockProps} className="custom-class" />);
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });
});
