import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import EventStatsPanel, { EventStatsPanelSkeleton } from './EventStatsPanel';

import type { EventStatsResponse } from '../../types/generated';

describe('EventStatsPanel', () => {
  const mockStats: EventStatsResponse = {
    total_events: 44,
    events_by_risk_level: {
      critical: 2,
      high: 5,
      medium: 12,
      low: 25,
    },
    risk_distribution: [
      { risk_level: 'critical', count: 2 },
      { risk_level: 'high', count: 5 },
      { risk_level: 'medium', count: 12 },
      { risk_level: 'low', count: 25 },
    ],
    events_by_camera: [
      { camera_id: 'front_door', camera_name: 'Front Door', event_count: 30 },
      { camera_id: 'back_door', camera_name: 'Back Door', event_count: 14 },
    ],
  };

  describe('rendering', () => {
    it('renders skeleton when isLoading is true', () => {
      render(<EventStatsPanel isLoading={true} />);

      expect(screen.getByTestId('event-stats-panel-skeleton')).toBeInTheDocument();
    });

    it('renders null when stats is undefined and not loading', () => {
      const { container } = render(<EventStatsPanel isLoading={false} />);

      expect(container.firstChild).toBeNull();
    });

    it('renders stats panel with data', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      expect(screen.getByTestId('event-stats-panel')).toBeInTheDocument();
    });

    it('displays total events count', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      expect(screen.getByText('44')).toBeInTheDocument();
      expect(screen.getByText('Total Events')).toBeInTheDocument();
    });

    it('displays critical risk count', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });

    it('displays high risk count', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
    });

    it('displays medium risk count', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      expect(screen.getByText('12')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
    });

    it('displays low risk count', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      expect(screen.getByText('25')).toBeInTheDocument();
      expect(screen.getByText('Low')).toBeInTheDocument();
    });
  });

  describe('risk distribution mini chart', () => {
    it('renders risk distribution visualization', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      expect(screen.getByTestId('risk-distribution-mini')).toBeInTheDocument();
    });

    it('shows risk distribution bars', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      // Should have bars for each risk level
      expect(screen.getByTestId('risk-bar-critical')).toBeInTheDocument();
      expect(screen.getByTestId('risk-bar-high')).toBeInTheDocument();
      expect(screen.getByTestId('risk-bar-medium')).toBeInTheDocument();
      expect(screen.getByTestId('risk-bar-low')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(
        <EventStatsPanel stats={mockStats} isLoading={false} className="custom-class" />
      );

      const panel = screen.getByTestId('event-stats-panel');
      expect(panel).toHaveClass('custom-class');
    });

    it('uses dark theme styling', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      const panel = screen.getByTestId('event-stats-panel');
      expect(panel).toHaveClass('bg-[#1F1F1F]');
      expect(panel).toHaveClass('border-gray-800');
    });
  });

  describe('responsive layout', () => {
    it('uses grid layout', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      const grid = screen.getByTestId('stats-grid');
      expect(grid).toHaveClass('grid');
      expect(grid).toHaveClass('grid-cols-2');
      expect(grid).toHaveClass('md:grid-cols-5');
    });
  });

  describe('accessibility', () => {
    it('has accessible stat cards', () => {
      render(<EventStatsPanel stats={mockStats} isLoading={false} />);

      // Check that stat cards have appropriate labels
      expect(screen.getByText('Total Events')).toBeInTheDocument();
      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
      expect(screen.getByText('Low')).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles zero counts gracefully', () => {
      const zeroStats: EventStatsResponse = {
        total_events: 0,
        events_by_risk_level: {
          critical: 0,
          high: 0,
          medium: 0,
          low: 0,
        },
        risk_distribution: [],
        events_by_camera: [],
      };

      render(<EventStatsPanel stats={zeroStats} isLoading={false} />);

      expect(screen.getAllByText('0')).toHaveLength(5); // Total + 4 risk levels
    });

    it('handles missing risk_distribution', () => {
      const statsWithoutDistribution: EventStatsResponse = {
        total_events: 10,
        events_by_risk_level: {
          critical: 1,
          high: 2,
          medium: 3,
          low: 4,
        },
        events_by_camera: [],
      };

      render(<EventStatsPanel stats={statsWithoutDistribution} isLoading={false} />);

      // Should still render without crashing
      expect(screen.getByTestId('event-stats-panel')).toBeInTheDocument();
    });

    it('handles large numbers with formatting', () => {
      const largeStats: EventStatsResponse = {
        total_events: 12500,
        events_by_risk_level: {
          critical: 250,
          high: 1500,
          medium: 4750,
          low: 6000,
        },
        risk_distribution: [],
        events_by_camera: [],
      };

      render(<EventStatsPanel stats={largeStats} isLoading={false} />);

      // Should format large numbers with commas
      expect(screen.getByText('12,500')).toBeInTheDocument();
      expect(screen.getByText('1,500')).toBeInTheDocument();
    });
  });
});

describe('EventStatsPanelSkeleton', () => {
  it('renders skeleton structure', () => {
    render(<EventStatsPanelSkeleton />);

    expect(screen.getByTestId('event-stats-panel-skeleton')).toBeInTheDocument();
  });

  it('renders multiple skeleton stat cards', () => {
    render(<EventStatsPanelSkeleton />);

    const skeletons = screen.getAllByTestId('stats-card-skeleton');
    expect(skeletons).toHaveLength(5); // Total + 4 risk levels
  });

  it('applies custom className', () => {
    render(<EventStatsPanelSkeleton className="custom-class" />);

    const skeleton = screen.getByTestId('event-stats-panel-skeleton');
    expect(skeleton).toHaveClass('custom-class');
  });

  it('uses dark theme styling', () => {
    render(<EventStatsPanelSkeleton />);

    const skeleton = screen.getByTestId('event-stats-panel-skeleton');
    expect(skeleton).toHaveClass('bg-[#1F1F1F]');
    expect(skeleton).toHaveClass('border-gray-800');
  });
});
