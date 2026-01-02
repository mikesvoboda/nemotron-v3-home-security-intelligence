import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import AuditStatsCards from './AuditStatsCards';

import type { AuditLogStats } from '../../services/api';

describe('AuditStatsCards', () => {
  const mockStats: AuditLogStats = {
    total_logs: 100,
    logs_today: 5,
    by_action: {
      event_reviewed: 50,
      camera_created: 30,
      settings_updated: 20,
    },
    by_resource_type: {
      event: 50,
      camera: 30,
      settings: 20,
    },
    by_status: {
      success: 95,
      failure: 5,
    },
    recent_actors: ['admin', 'system', 'api'],
  };

  describe('Rendering', () => {
    it('renders all four main stats cards', () => {
      render(<AuditStatsCards stats={mockStats} />);

      expect(screen.getByText('Total Audit Entries')).toBeInTheDocument();
      expect(screen.getByText('Entries Today')).toBeInTheDocument();
      expect(screen.getByText('Successful Operations')).toBeInTheDocument();
      expect(screen.getByText('Failed Operations')).toBeInTheDocument();
    });

    it('displays stats values', () => {
      render(<AuditStatsCards stats={mockStats} />);

      expect(screen.getByText('100')).toBeInTheDocument(); // total_logs
      expect(screen.getByText('95')).toBeInTheDocument(); // success count

      // logs_today and failure count are both 5, so we use getAllByText
      const fives = screen.getAllByText('5');
      expect(fives.length).toBe(2); // logs_today and failure count
    });

    it('displays failure count', () => {
      render(<AuditStatsCards stats={mockStats} />);

      // The "5" for logs_today and failure count are both present
      const fives = screen.getAllByText('5');
      expect(fives.length).toBeGreaterThan(0);
    });

    it('applies custom className', () => {
      const { container } = render(
        <AuditStatsCards stats={mockStats} className="custom-class" />
      );

      const wrapper = container.querySelector('.custom-class');
      expect(wrapper).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('displays loading skeleton when loading', () => {
      const { container } = render(<AuditStatsCards stats={null} loading={true} />);

      // Look for animate-pulse class that indicates loading skeleton
      const loadingSkeleton = container.querySelector('.animate-pulse');
      expect(loadingSkeleton).toBeInTheDocument();
    });

    it('shows all card titles during loading', () => {
      render(<AuditStatsCards stats={null} loading={true} />);

      expect(screen.getByText('Total Audit Entries')).toBeInTheDocument();
      expect(screen.getByText('Entries Today')).toBeInTheDocument();
      expect(screen.getByText('Successful Operations')).toBeInTheDocument();
      expect(screen.getByText('Failed Operations')).toBeInTheDocument();
    });
  });

  describe('Null Stats', () => {
    it('displays zeros when stats is null', () => {
      render(<AuditStatsCards stats={null} />);

      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBeGreaterThanOrEqual(4); // All four cards should show 0
    });
  });

  describe('Failure Count Styling', () => {
    it('uses red styling when failures exist', () => {
      render(<AuditStatsCards stats={mockStats} />);

      // Find the Failed Operations card and check its value has red styling
      const failedCard = screen.getByText('Failed Operations').closest('div');
      expect(failedCard).toBeInTheDocument();

      // The value element with failures should have red color
      const valueElement = failedCard?.querySelector('.text-red-400');
      expect(valueElement).toBeInTheDocument();
    });

    it('uses gray styling when no failures', () => {
      const noFailureStats: AuditLogStats = {
        ...mockStats,
        by_status: {
          success: 100,
          failure: 0,
        },
      };

      render(<AuditStatsCards stats={noFailureStats} />);

      // Find the Failed Operations card
      const failedCard = screen.getByText('Failed Operations').closest('div');
      expect(failedCard).toBeInTheDocument();

      // The value element with 0 failures should have gray color
      const valueElement = failedCard?.querySelector('.text-gray-400');
      expect(valueElement).toBeInTheDocument();
    });
  });

  describe('Actions by Type Section', () => {
    it('displays action breakdown when actions exist', () => {
      render(<AuditStatsCards stats={mockStats} />);

      expect(screen.getByText('Actions by Type')).toBeInTheDocument();
    });

    it('displays action badges with counts', () => {
      render(<AuditStatsCards stats={mockStats} />);

      // Check for formatted action names
      expect(screen.getByText('Event Reviewed')).toBeInTheDocument();
      expect(screen.getByText('Camera Created')).toBeInTheDocument();
      expect(screen.getByText('Settings Updated')).toBeInTheDocument();

      // Check for counts
      expect(screen.getByText('50')).toBeInTheDocument();
      expect(screen.getByText('30')).toBeInTheDocument();
      expect(screen.getByText('20')).toBeInTheDocument();
    });

    it('sorts actions by count descending', () => {
      render(<AuditStatsCards stats={mockStats} />);

      const buttons = screen.getAllByRole('button');
      const actionButtons = buttons.filter(
        (btn) =>
          btn.textContent?.includes('Reviewed') ||
          btn.textContent?.includes('Created') ||
          btn.textContent?.includes('Updated')
      );

      // First action should be the one with highest count (event_reviewed with 50)
      expect(actionButtons[0]).toHaveTextContent('Event Reviewed');
    });

    it('limits to top 10 actions', () => {
      const manyActionsStats: AuditLogStats = {
        ...mockStats,
        by_action: {
          action_1: 100,
          action_2: 90,
          action_3: 80,
          action_4: 70,
          action_5: 60,
          action_6: 50,
          action_7: 40,
          action_8: 30,
          action_9: 20,
          action_10: 10,
          action_11: 5, // This one should not be displayed
          action_12: 1, // This one should not be displayed
        },
      };

      render(<AuditStatsCards stats={manyActionsStats} />);

      // Should show top 10, not 12
      expect(screen.getByText('Action 1')).toBeInTheDocument();
      expect(screen.getByText('Action 10')).toBeInTheDocument();
      expect(screen.queryByText('Action 11')).not.toBeInTheDocument();
      expect(screen.queryByText('Action 12')).not.toBeInTheDocument();
    });

    it('hides action breakdown when no actions', () => {
      const noActionsStats: AuditLogStats = {
        ...mockStats,
        by_action: {},
      };

      render(<AuditStatsCards stats={noActionsStats} />);

      expect(screen.queryByText('Actions by Type')).not.toBeInTheDocument();
    });
  });

  describe('Click Handlers - Stats Cards', () => {
    it('calls onFilterClick with "total" when Total card is clicked', async () => {
      const user = userEvent.setup();
      const mockOnFilterClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onFilterClick={mockOnFilterClick} />);

      const totalCard = screen.getByText('Total Audit Entries').closest('[role="button"]');
      await user.click(totalCard!);

      expect(mockOnFilterClick).toHaveBeenCalledWith('total');
    });

    it('calls onFilterClick with "today" when Entries Today card is clicked', async () => {
      const user = userEvent.setup();
      const mockOnFilterClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onFilterClick={mockOnFilterClick} />);

      const todayCard = screen.getByText('Entries Today').closest('[role="button"]');
      await user.click(todayCard!);

      expect(mockOnFilterClick).toHaveBeenCalledWith('today');
    });

    it('calls onFilterClick with "success" when Successful Operations card is clicked', async () => {
      const user = userEvent.setup();
      const mockOnFilterClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onFilterClick={mockOnFilterClick} />);

      const successCard = screen.getByText('Successful Operations').closest('[role="button"]');
      await user.click(successCard!);

      expect(mockOnFilterClick).toHaveBeenCalledWith('success');
    });

    it('calls onFilterClick with "failure" when Failed Operations card is clicked', async () => {
      const user = userEvent.setup();
      const mockOnFilterClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onFilterClick={mockOnFilterClick} />);

      const failureCard = screen.getByText('Failed Operations').closest('[role="button"]');
      await user.click(failureCard!);

      expect(mockOnFilterClick).toHaveBeenCalledWith('failure');
    });

    it('cards have cursor-pointer when onFilterClick is provided', () => {
      const mockOnFilterClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onFilterClick={mockOnFilterClick} />);

      const totalCard = screen.getByText('Total Audit Entries').closest('[role="button"]');
      expect(totalCard).toHaveClass('cursor-pointer');
    });

    it('cards do not have button role when onFilterClick is not provided', () => {
      render(<AuditStatsCards stats={mockStats} />);

      // Without onFilterClick, cards should not be buttons
      const totalCard = screen.getByText('Total Audit Entries').closest('div');
      expect(totalCard).not.toHaveAttribute('role', 'button');
    });
  });

  describe('Click Handlers - Action Badges', () => {
    it('calls onActionClick when action badge is clicked', async () => {
      const user = userEvent.setup();
      const mockOnActionClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onActionClick={mockOnActionClick} />);

      const eventReviewedBadge = screen.getByRole('button', { name: /Event Reviewed/i });
      await user.click(eventReviewedBadge);

      expect(mockOnActionClick).toHaveBeenCalledWith('event_reviewed');
    });

    it('action badges have cursor-pointer when onActionClick is provided', () => {
      const mockOnActionClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onActionClick={mockOnActionClick} />);

      const badge = screen.getByRole('button', { name: /Event Reviewed/i });
      expect(badge).toHaveClass('cursor-pointer');
    });
  });

  describe('Active States', () => {
    it('shows active ring on stats card when activeFilter matches', () => {
      render(
        <AuditStatsCards
          stats={mockStats}
          activeFilter="success"
          onFilterClick={vi.fn()}
        />
      );

      const successCard = screen.getByText('Successful Operations').closest('[role="button"]');
      expect(successCard).toHaveClass('ring-2');
    });

    it('shows active styling on action badge when activeActionFilter matches', () => {
      render(
        <AuditStatsCards
          stats={mockStats}
          activeActionFilter="event_reviewed"
          onActionClick={vi.fn()}
        />
      );

      const badge = screen.getByRole('button', { name: /Event Reviewed/i });
      expect(badge).toHaveClass('ring-2');
    });

    it('sets aria-pressed on stats card when active', () => {
      render(
        <AuditStatsCards
          stats={mockStats}
          activeFilter="total"
          onFilterClick={vi.fn()}
        />
      );

      const totalCard = screen.getByText('Total Audit Entries').closest('[role="button"]');
      expect(totalCard).toHaveAttribute('aria-pressed', 'true');
    });

    it('sets aria-pressed on action badge when active', () => {
      render(
        <AuditStatsCards
          stats={mockStats}
          activeActionFilter="camera_created"
          onActionClick={vi.fn()}
        />
      );

      const badge = screen.getByRole('button', { name: /Camera Created/i });
      expect(badge).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('Keyboard Accessibility', () => {
    it('stats cards can be activated with Enter key', async () => {
      const user = userEvent.setup();
      const mockOnFilterClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onFilterClick={mockOnFilterClick} />);

      const totalCard = screen.getByText('Total Audit Entries').closest('[role="button"]') as HTMLElement;
      totalCard.focus();
      await user.keyboard('{Enter}');

      expect(mockOnFilterClick).toHaveBeenCalledWith('total');
    });

    it('stats cards can be activated with Space key', async () => {
      const user = userEvent.setup();
      const mockOnFilterClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onFilterClick={mockOnFilterClick} />);

      const successCard = screen.getByText('Successful Operations').closest('[role="button"]') as HTMLElement;
      successCard.focus();
      await user.keyboard(' ');

      expect(mockOnFilterClick).toHaveBeenCalledWith('success');
    });

    it('stats cards have tabIndex when clickable', () => {
      const mockOnFilterClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onFilterClick={mockOnFilterClick} />);

      const totalCard = screen.getByText('Total Audit Entries').closest('[role="button"]');
      expect(totalCard).toHaveAttribute('tabIndex', '0');
    });

    it('stats cards have aria-label when clickable', () => {
      const mockOnFilterClick = vi.fn();

      render(<AuditStatsCards stats={mockStats} onFilterClick={mockOnFilterClick} />);

      const totalCard = screen.getByText('Total Audit Entries').closest('[role="button"]');
      expect(totalCard).toHaveAttribute('aria-label', 'Filter by Total Audit Entries');
    });
  });

  describe('Styling', () => {
    it('uses NVIDIA dark theme background colors', () => {
      const { container } = render(<AuditStatsCards stats={mockStats} />);

      const card = container.querySelector('.bg-\\[\\#1F1F1F\\]');
      expect(card).toBeInTheDocument();
    });

    it('uses green accent color for total card', () => {
      const { container } = render(<AuditStatsCards stats={mockStats} />);

      const greenValue = container.querySelector('.text-\\[\\#76B900\\]');
      expect(greenValue).toBeInTheDocument();
    });

    it('uses blue color for today card', () => {
      const { container } = render(<AuditStatsCards stats={mockStats} />);

      const blueValue = container.querySelector('.text-blue-400');
      expect(blueValue).toBeInTheDocument();
    });

    it('uses green color for success card', () => {
      const { container } = render(<AuditStatsCards stats={mockStats} />);

      const greenValue = container.querySelector('.text-green-400');
      expect(greenValue).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles undefined by_status gracefully', () => {
      const partialStats: AuditLogStats = {
        total_logs: 50,
        logs_today: 2,
        by_action: {},
        by_resource_type: {},
        by_status: {},
        recent_actors: [],
      };

      render(<AuditStatsCards stats={partialStats} />);

      // Should show 0 for success and failure
      expect(screen.getByText('Successful Operations')).toBeInTheDocument();
      expect(screen.getByText('Failed Operations')).toBeInTheDocument();
    });

    it('handles zero values correctly', () => {
      const zeroStats: AuditLogStats = {
        total_logs: 0,
        logs_today: 0,
        by_action: {},
        by_resource_type: {},
        by_status: {
          success: 0,
          failure: 0,
        },
        recent_actors: [],
      };

      render(<AuditStatsCards stats={zeroStats} />);

      const zeros = screen.getAllByText('0');
      expect(zeros.length).toBeGreaterThanOrEqual(4);
    });
  });

  describe('Grid Layout', () => {
    it('renders cards in a grid layout', () => {
      const { container } = render(<AuditStatsCards stats={mockStats} />);

      const grid = container.querySelector('.grid');
      expect(grid).toBeInTheDocument();
      expect(grid).toHaveClass('grid-cols-1');
    });

    it('action breakdown spans full width', () => {
      const { container } = render(<AuditStatsCards stats={mockStats} />);

      const actionBreakdown = container.querySelector('.col-span-full');
      expect(actionBreakdown).toBeInTheDocument();
    });
  });
});
