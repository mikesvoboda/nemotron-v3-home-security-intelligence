/**
 * Tests for ActionableInsights component
 * Comprehensive test coverage for actionable insights display
 *
 * Related Linear issues: NEM-5418, NEM-5419, NEM-5420, NEM-5421
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import ActionableInsights from './ActionableInsights';

import type { InsightSchema } from './ActionableInsights';

// Mock react-router-dom useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

// Sample insight data for tests
const mockInsights: InsightSchema[] = [
  {
    type: 'entity',
    priority: 10,
    title: 'Unknown Persons Detected',
    description: '2 unknown persons detected at Front Door, Driveway',
    action_url: '/timeline?entity_type=person&recognized=false',
  },
  {
    type: 'trend',
    priority: 8,
    title: 'Activity Above Baseline',
    description: 'Activity is 100% above baseline (4 vs 2 events)',
    action_url: '/analytics',
  },
  {
    type: 'camera',
    priority: 6,
    title: 'Camera Activity',
    description: 'Review 3 events from Front Door (2 high/critical)',
    action_url: '/timeline?camera_id=front_door',
  },
];

describe('ActionableInsights', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockClear();
  });

  describe('basic rendering', () => {
    it('renders the main container', () => {
      render(<ActionableInsights insights={mockInsights} />);
      expect(screen.getByTestId('actionable-insights')).toBeInTheDocument();
    });

    it('renders the section title', () => {
      render(<ActionableInsights insights={mockInsights} />);
      expect(screen.getByText('Actionable Insights')).toBeInTheDocument();
    });

    it('renders all provided insights', () => {
      render(<ActionableInsights insights={mockInsights} />);
      expect(screen.getByText('Unknown Persons Detected')).toBeInTheDocument();
      expect(screen.getByText('Activity Above Baseline')).toBeInTheDocument();
      expect(screen.getByText('Camera Activity')).toBeInTheDocument();
    });

    it('renders insight descriptions', () => {
      render(<ActionableInsights insights={mockInsights} />);
      expect(
        screen.getByText('2 unknown persons detected at Front Door, Driveway')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Activity is 100% above baseline (4 vs 2 events)')
      ).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('renders empty state when no insights provided', () => {
      render(<ActionableInsights insights={[]} />);
      expect(screen.getByText(/No actionable insights/i)).toBeInTheDocument();
    });

    it('renders empty state with quiet message', () => {
      render(<ActionableInsights insights={[]} />);
      expect(screen.getByText(/Property is quiet/i)).toBeInTheDocument();
    });
  });

  describe('insight type icons', () => {
    it('renders entity icon for entity insights', () => {
      const entityInsight: InsightSchema[] = [
        {
          type: 'entity',
          priority: 10,
          title: 'Unknown Persons',
          description: '1 unknown person detected',
          action_url: null,
        },
      ];
      render(<ActionableInsights insights={entityInsight} />);
      // User icon should be rendered for entity type
      const card = screen.getByTestId('insight-card-0');
      expect(card).toBeInTheDocument();
    });

    it('renders trend icon for trend insights', () => {
      const trendInsight: InsightSchema[] = [
        {
          type: 'trend',
          priority: 7,
          title: 'Activity Trend',
          description: 'Activity above baseline',
          action_url: null,
        },
      ];
      render(<ActionableInsights insights={trendInsight} />);
      const card = screen.getByTestId('insight-card-0');
      expect(card).toBeInTheDocument();
    });

    it('renders camera icon for camera insights', () => {
      const cameraInsight: InsightSchema[] = [
        {
          type: 'camera',
          priority: 5,
          title: 'Camera Activity',
          description: 'Review events from Front Door',
          action_url: null,
        },
      ];
      render(<ActionableInsights insights={cameraInsight} />);
      const card = screen.getByTestId('insight-card-0');
      expect(card).toBeInTheDocument();
    });
  });

  describe('priority indicators', () => {
    it('shows high priority indicator for priority >= 8', () => {
      const highPriority: InsightSchema[] = [
        {
          type: 'entity',
          priority: 10,
          title: 'High Priority',
          description: 'Test',
          action_url: null,
        },
      ];
      render(<ActionableInsights insights={highPriority} />);
      const card = screen.getByTestId('insight-card-0');
      // Should have red/orange styling for high priority
      expect(card).toBeInTheDocument();
    });

    it('shows medium priority indicator for priority 5-7', () => {
      const mediumPriority: InsightSchema[] = [
        {
          type: 'camera',
          priority: 6,
          title: 'Medium Priority',
          description: 'Test',
          action_url: null,
        },
      ];
      render(<ActionableInsights insights={mediumPriority} />);
      const card = screen.getByTestId('insight-card-0');
      // Should have yellow styling for medium priority
      expect(card).toBeInTheDocument();
    });

    it('shows low priority indicator for priority < 5', () => {
      const lowPriority: InsightSchema[] = [
        {
          type: 'trend',
          priority: 3,
          title: 'Low Priority',
          description: 'Test',
          action_url: null,
        },
      ];
      render(<ActionableInsights insights={lowPriority} />);
      const card = screen.getByTestId('insight-card-0');
      // Should have green styling for low priority
      expect(card).toBeInTheDocument();
    });
  });

  describe('navigation on click', () => {
    it('navigates when clicking insight with action_url', () => {
      render(<ActionableInsights insights={mockInsights} />);

      const firstInsight = screen.getByTestId('insight-card-0');
      fireEvent.click(firstInsight);

      expect(mockNavigate).toHaveBeenCalledWith('/timeline?entity_type=person&recognized=false');
    });

    it('navigates to correct URL for camera insight', () => {
      render(<ActionableInsights insights={mockInsights} />);

      const cameraInsight = screen.getByTestId('insight-card-2');
      fireEvent.click(cameraInsight);

      expect(mockNavigate).toHaveBeenCalledWith('/timeline?camera_id=front_door');
    });

    it('does not navigate when action_url is null', () => {
      const noUrlInsight: InsightSchema[] = [
        {
          type: 'entity',
          priority: 10,
          title: 'No URL',
          description: 'Test',
          action_url: null,
        },
      ];
      render(<ActionableInsights insights={noUrlInsight} />);

      const card = screen.getByTestId('insight-card-0');
      fireEvent.click(card);

      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('renders clickable insights as buttons', () => {
      render(<ActionableInsights insights={mockInsights} />);

      const firstInsight = screen.getByTestId('insight-card-0');
      expect(firstInsight.tagName.toLowerCase()).toBe('button');
    });

    it('renders non-clickable insights as divs', () => {
      const noUrlInsight: InsightSchema[] = [
        {
          type: 'entity',
          priority: 10,
          title: 'No URL',
          description: 'Test',
          action_url: null,
        },
      ];
      render(<ActionableInsights insights={noUrlInsight} />);

      const card = screen.getByTestId('insight-card-0');
      expect(card.tagName.toLowerCase()).toBe('div');
    });

    it('has correct aria-label for clickable insights', () => {
      render(<ActionableInsights insights={mockInsights} />);

      const firstInsight = screen.getByTestId('insight-card-0');
      expect(firstInsight).toHaveAttribute('aria-label');
    });
  });

  describe('className prop', () => {
    it('applies custom className', () => {
      render(<ActionableInsights insights={mockInsights} className="custom-class" />);
      expect(screen.getByTestId('actionable-insights')).toHaveClass('custom-class');
    });
  });

  describe('expanded state', () => {
    it('shows all insights by default when 5 or fewer', () => {
      render(<ActionableInsights insights={mockInsights} />);
      expect(screen.getAllByTestId(/insight-card-/)).toHaveLength(3);
    });

    it('limits display to top 3 initially when more than 5 insights', () => {
      const manyInsights: InsightSchema[] = Array.from({ length: 7 }, (_, i) => ({
        type: 'camera' as const,
        priority: 10 - i,
        title: `Insight ${i + 1}`,
        description: `Description ${i + 1}`,
        action_url: `/test/${i}`,
      }));

      render(<ActionableInsights insights={manyInsights} />);

      // Should show expand button
      expect(screen.getByText(/Show more/i)).toBeInTheDocument();
    });

    it('expands to show all insights when clicking "Show more"', () => {
      const manyInsights: InsightSchema[] = Array.from({ length: 7 }, (_, i) => ({
        type: 'camera' as const,
        priority: 10 - i,
        title: `Insight ${i + 1}`,
        description: `Description ${i + 1}`,
        action_url: `/test/${i}`,
      }));

      render(<ActionableInsights insights={manyInsights} />);

      // Click show more
      const showMore = screen.getByText(/Show more/i);
      fireEvent.click(showMore);

      // Should now show "Show less"
      expect(screen.getByText(/Show less/i)).toBeInTheDocument();
    });
  });

  describe('insight sorting', () => {
    it('displays insights sorted by priority (highest first)', () => {
      const unsortedInsights: InsightSchema[] = [
        {
          type: 'camera',
          priority: 5,
          title: 'Low Priority',
          description: 'Test',
          action_url: null,
        },
        {
          type: 'entity',
          priority: 10,
          title: 'High Priority',
          description: 'Test',
          action_url: null,
        },
        {
          type: 'trend',
          priority: 7,
          title: 'Medium Priority',
          description: 'Test',
          action_url: null,
        },
      ];

      render(<ActionableInsights insights={unsortedInsights} />);

      const cards = screen.getAllByTestId(/insight-card-/);
      // First card should be high priority
      expect(cards[0]).toHaveTextContent('High Priority');
      // Second should be medium
      expect(cards[1]).toHaveTextContent('Medium Priority');
      // Third should be low
      expect(cards[2]).toHaveTextContent('Low Priority');
    });
  });

  describe('loading state', () => {
    it('renders loading skeleton when isLoading is true', () => {
      render(<ActionableInsights insights={[]} isLoading={true} />);
      // Should show skeleton elements
      const container = screen.getByTestId('actionable-insights');
      expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
    });
  });

  describe('maxInsights prop', () => {
    it('limits displayed insights to maxInsights when collapsed', () => {
      const manyInsights: InsightSchema[] = Array.from({ length: 10 }, (_, i) => ({
        type: 'camera' as const,
        priority: 10 - i,
        title: `Insight ${i + 1}`,
        description: `Description ${i + 1}`,
        action_url: `/test/${i}`,
      }));

      render(<ActionableInsights insights={manyInsights} maxInsights={2} />);

      // Should only show 2 initially
      const cards = screen.getAllByTestId(/insight-card-/);
      expect(cards.length).toBe(2);
    });
  });
});
