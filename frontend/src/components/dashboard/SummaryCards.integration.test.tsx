/**
 * Integration Tests for SummaryCards Component
 *
 * Tests real-world interaction flows including:
 * - Loading → success state transitions
 * - Loading → error → retry → success recovery flow
 * - WebSocket live updates
 * - Expand/collapse interactions (when onViewFull is provided)
 *
 * @see NEM-2930 - Comprehensive Summary Card Test Suite
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { SummaryCards } from './SummaryCards';

import type { Summary } from '@/types/summary';

import {
  mockSummaryHighSeverity,
  mockSummaryAllClear,
  mockSummaryMediumSeverity,
  createMockSummary,
} from '@/test/fixtures/summaries';

describe('SummaryCards Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading → Success Flow', () => {
    it('transitions from loading to success state with hourly summary', async () => {
      const { rerender } = render(
        <SummaryCards hourly={null} daily={null} isLoading={true} />
      );

      // Initially shows loading skeletons (now uses SummaryCardSkeleton)
      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();

      // Simulate data loaded
      rerender(<SummaryCards hourly={mockSummaryHighSeverity} daily={null} isLoading={false} />);

      // Loading skeletons should be gone
      await waitFor(() => {
        expect(screen.queryByTestId('summary-card-skeleton-hourly')).not.toBeInTheDocument();
      });

      // Hourly card should show with data
      expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();

      // Daily card should show empty state (now uses SummaryCardEmpty)
      expect(screen.getByTestId('summary-card-empty-daily')).toBeInTheDocument();
    });

    it('transitions from loading to success state with both summaries', async () => {
      const { rerender } = render(
        <SummaryCards hourly={null} daily={null} isLoading={true} />
      );

      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();

      // Simulate both summaries loaded
      rerender(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      await waitFor(() => {
        expect(screen.queryByTestId('summary-card-skeleton-hourly')).not.toBeInTheDocument();
      });

      // Both cards should show with data
      expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily')).toBeInTheDocument();
    });

    it('shows loading state only briefly before data appears', async () => {
      const { rerender } = render(
        <SummaryCards hourly={null} daily={null} isLoading={true} />
      );

      const loadingStart = Date.now();
      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();

      // Immediate data load (fast network)
      rerender(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      await waitFor(() => {
        expect(screen.queryByTestId('summary-card-skeleton-hourly')).not.toBeInTheDocument();
      });

      const loadingEnd = Date.now();
      // Loading state should transition quickly (< 1 second in test environment)
      expect(loadingEnd - loadingStart).toBeLessThan(1000);
    });
  });

  describe('Loading → Error → Retry → Success Flow', () => {
    it('transitions from loading to error state', async () => {
      // Note: SummaryCards now supports error state via error/onRetry props
      // We'll test the state transition behavior
      const { rerender } = render(
        <SummaryCards hourly={null} daily={null} isLoading={true} />
      );

      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();

      // Simulate error: loading stops but no data
      rerender(<SummaryCards hourly={null} daily={null} isLoading={false} />);

      await waitFor(() => {
        expect(screen.queryByTestId('summary-card-skeleton-hourly')).not.toBeInTheDocument();
      });

      // Should show empty states when loading completes with no data
      expect(screen.getByTestId('summary-card-empty-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-empty-daily')).toBeInTheDocument();
    });

    it('recovers from error state on retry with success', async () => {
      const { rerender } = render(
        <SummaryCards hourly={null} daily={null} isLoading={false} />
      );

      // Initially in empty state
      expect(screen.getByTestId('summary-card-empty-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-empty-daily')).toBeInTheDocument();

      // Simulate retry (loading again)
      rerender(<SummaryCards hourly={null} daily={null} isLoading={true} />);

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
        expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();
      });

      // Simulate success after retry
      rerender(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      await waitFor(() => {
        expect(screen.queryByTestId('summary-card-skeleton-hourly')).not.toBeInTheDocument();
      });

      // Should now show data
      expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily')).toBeInTheDocument();
      expect(screen.queryByText('No activity to summarize')).not.toBeInTheDocument();
    });

    it('handles multiple retry attempts', async () => {
      const { rerender } = render(
        <SummaryCards hourly={null} daily={null} isLoading={false} />
      );

      // Attempt 1: Retry fails
      rerender(<SummaryCards hourly={null} daily={null} isLoading={true} />);
      await waitFor(() => {
        expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      });

      rerender(<SummaryCards hourly={null} daily={null} isLoading={false} />);
      await waitFor(() => {
        expect(screen.getByTestId('summary-card-empty-hourly')).toBeInTheDocument();
      });

      // Attempt 2: Retry fails again
      rerender(<SummaryCards hourly={null} daily={null} isLoading={true} />);
      await waitFor(() => {
        expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      });

      rerender(<SummaryCards hourly={null} daily={null} isLoading={false} />);
      await waitFor(() => {
        expect(screen.getByTestId('summary-card-empty-hourly')).toBeInTheDocument();
      });

      // Attempt 3: Retry succeeds
      rerender(<SummaryCards hourly={null} daily={null} isLoading={true} />);
      rerender(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
        expect(screen.getByTestId('summary-card-daily')).toBeInTheDocument();
      });
    });
  });

  describe('WebSocket Update Flow', () => {
    it('updates hourly summary when WebSocket pushes new data', async () => {
      const { rerender } = render(
        <SummaryCards
          hourly={mockSummaryAllClear}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      // Initially shows all clear for both
      const initialBadges = screen.getAllByText('ALL CLEAR');
      expect(initialBadges).toHaveLength(2);

      // Simulate WebSocket update with high severity summary for hourly
      rerender(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      await waitFor(() => {
        // Should update to show critical badge on hourly card
        const badges = screen.getAllByTestId('severity-badge');
        const criticalBadge = badges.find((b) => b.getAttribute('data-severity') === 'critical');
        expect(criticalBadge).toBeInTheDocument();
        expect(criticalBadge).toHaveTextContent('CRITICAL');
      });
    });

    it('updates daily summary when WebSocket pushes new data', async () => {
      const initialDaily = createMockSummary({
        eventCount: 0,
        content: 'All clear. No events detected.',
      });

      const updatedDaily = createMockSummary({
        eventCount: 5,
        content: 'Multiple events detected throughout the day.',
        maxRiskScore: 65,
      });

      const { rerender } = render(
        <SummaryCards hourly={mockSummaryAllClear} daily={initialDaily} isLoading={false} />
      );

      // Initially shows 0 events
      const initialDailyCard = screen.getByTestId('summary-card-daily');
      expect(initialDailyCard.querySelector('[data-testid="summary-event-count-daily"]')).toHaveTextContent('0 events');

      // Simulate WebSocket update
      rerender(
        <SummaryCards hourly={mockSummaryAllClear} daily={updatedDaily} isLoading={false} />
      );

      await waitFor(() => {
        // Should update event count
        const updatedDailyCard = screen.getByTestId('summary-card-daily');
        expect(updatedDailyCard.querySelector('[data-testid="summary-event-count-daily"]')).toHaveTextContent('5 events');
      });
    });

    it('handles WebSocket updates during loading state', async () => {
      const { rerender } = render(
        <SummaryCards hourly={null} daily={null} isLoading={true} />
      );

      // Loading state
      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();

      // WebSocket update arrives while still loading (edge case)
      rerender(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={true}
        />
      );

      // Should still show loading (isLoading takes precedence)
      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();

      // Loading completes
      rerender(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      await waitFor(() => {
        expect(screen.queryByTestId('summary-card-skeleton-hourly')).not.toBeInTheDocument();
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      });
    });

    it('handles rapid WebSocket updates without flickering', async () => {
      const { rerender } = render(
        <SummaryCards hourly={mockSummaryAllClear} daily={null} isLoading={false} />
      );

      // Rapid updates (simulating real-time data)
      const updates = [
        mockSummaryMediumSeverity,
        mockSummaryHighSeverity,
        createMockSummary({ eventCount: 2, maxRiskScore: 55 }),
      ];

      for (const update of updates) {
        rerender(<SummaryCards hourly={update} daily={null} isLoading={false} />);
      }

      // Final state should reflect last update
      await waitFor(() => {
        const hourlyCard = screen.getByTestId('summary-card-hourly');
        expect(hourlyCard.querySelector('[data-testid="summary-event-count-hourly"]')).toHaveTextContent('2 events');
      });
    });
  });

  describe('Expand/Collapse Interaction', () => {
    it('calls onViewFull callback when View Full Summary is clicked', async () => {
      const user = userEvent.setup();
      const onViewFull = vi.fn();

      render(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
          onViewFull={onViewFull}
        />
      );

      // Find and click hourly "View Full Summary" button
      const hourlyViewFullButton = screen.getByTestId('summary-view-full-hourly');
      await user.click(hourlyViewFullButton);

      // Should call callback with hourly summary
      expect(onViewFull).toHaveBeenCalledTimes(1);
      expect(onViewFull).toHaveBeenCalledWith(mockSummaryHighSeverity);
    });

    it('calls onViewFull with correct summary for daily card', async () => {
      const user = userEvent.setup();
      const onViewFull = vi.fn();

      render(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
          onViewFull={onViewFull}
        />
      );

      // Find and click daily "View Full Summary" button
      const dailyViewFullButton = screen.getByTestId('summary-view-full-daily');
      await user.click(dailyViewFullButton);

      // Should call callback with daily summary
      expect(onViewFull).toHaveBeenCalledTimes(1);
      expect(onViewFull).toHaveBeenCalledWith(mockSummaryAllClear);
    });

    it('does not show View Full Summary button when onViewFull is not provided', () => {
      render(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      // Buttons should not be present
      expect(screen.queryByTestId('summary-view-full-hourly')).not.toBeInTheDocument();
      expect(screen.queryByTestId('summary-view-full-daily')).not.toBeInTheDocument();
    });

    it('handles multiple clicks on View Full Summary', async () => {
      const user = userEvent.setup();
      const onViewFull = vi.fn();

      render(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
          onViewFull={onViewFull}
        />
      );

      const hourlyViewFullButton = screen.getByTestId('summary-view-full-hourly');

      // Click multiple times
      await user.click(hourlyViewFullButton);
      await user.click(hourlyViewFullButton);
      await user.click(hourlyViewFullButton);

      // Should call callback 3 times
      expect(onViewFull).toHaveBeenCalledTimes(3);
      expect(onViewFull).toHaveBeenCalledWith(mockSummaryHighSeverity);
    });

    it('View Full Summary button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onViewFull = vi.fn();

      render(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
          onViewFull={onViewFull}
        />
      );

      const hourlyViewFullButton = screen.getByTestId('summary-view-full-hourly');

      // Focus and press Enter
      hourlyViewFullButton.focus();
      await user.keyboard('{Enter}');

      expect(onViewFull).toHaveBeenCalledTimes(1);
      expect(onViewFull).toHaveBeenCalledWith(mockSummaryHighSeverity);
    });
  });

  describe('Complex Integration Flows', () => {
    it('handles full lifecycle: loading → data → WebSocket update → expand', async () => {
      const user = userEvent.setup();
      const onViewFull = vi.fn();

      const { rerender } = render(
        <SummaryCards hourly={null} daily={null} isLoading={true} onViewFull={onViewFull} />
      );

      // 1. Loading state
      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();

      // 2. Initial data loaded
      rerender(
        <SummaryCards
          hourly={mockSummaryAllClear}
          daily={mockSummaryAllClear}
          isLoading={false}
          onViewFull={onViewFull}
        />
      );

      await waitFor(() => {
        expect(screen.queryByTestId('summary-card-skeleton-hourly')).not.toBeInTheDocument();
      });

      // 3. WebSocket update with high severity
      rerender(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
          onViewFull={onViewFull}
        />
      );

      await waitFor(() => {
        const badges = screen.getAllByTestId('severity-badge');
        const criticalBadge = badges.find((b) => b.getAttribute('data-severity') === 'critical');
        expect(criticalBadge).toHaveTextContent('CRITICAL');
      });

      // 4. User expands to view full summary
      const viewFullButton = screen.getByTestId('summary-view-full-hourly');
      await user.click(viewFullButton);

      expect(onViewFull).toHaveBeenCalledWith(mockSummaryHighSeverity);
    });

    it('handles simultaneous updates to both hourly and daily summaries', async () => {
      const { rerender } = render(
        <SummaryCards hourly={mockSummaryAllClear} daily={mockSummaryAllClear} isLoading={false} />
      );

      // Both show all clear
      const initialBadges = screen.getAllByText('ALL CLEAR');
      expect(initialBadges).toHaveLength(2);

      // Simultaneous WebSocket update for both
      rerender(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryMediumSeverity}
          isLoading={false}
        />
      );

      await waitFor(() => {
        // Hourly should be critical
        const hourlyCritical = screen.getByTestId('summary-card-hourly');
        expect(hourlyCritical.querySelector('[data-testid="severity-badge"]')).toHaveAttribute('data-severity', 'critical');

        // Daily should be medium
        const dailyMedium = screen.getByTestId('summary-card-daily');
        expect(dailyMedium.querySelector('[data-testid="severity-badge"]')).toHaveAttribute('data-severity', 'medium');
      });
    });

    it('maintains UI consistency during rapid state changes', async () => {
      const { rerender } = render(
        <SummaryCards hourly={null} daily={null} isLoading={true} />
      );

      // Rapid state changes (stress test)
      const states: Array<{
        hourly: Summary | null;
        daily: Summary | null;
        isLoading: boolean;
      }> = [
        { hourly: null, daily: null, isLoading: true },
        { hourly: mockSummaryAllClear, daily: null, isLoading: false },
        { hourly: mockSummaryHighSeverity, daily: mockSummaryAllClear, isLoading: false },
        { hourly: mockSummaryHighSeverity, daily: mockSummaryMediumSeverity, isLoading: false },
      ];

      for (const state of states) {
        rerender(<SummaryCards {...state} />);
      }

      // Final state should be stable and correct
      await waitFor(() => {
        expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
        expect(screen.getByTestId('summary-card-daily')).toBeInTheDocument();

        const hourlyCard = screen.getByTestId('summary-card-hourly');
        expect(hourlyCard.querySelector('[data-testid="severity-badge"]')).toHaveAttribute('data-severity', 'critical');

        const dailyCard = screen.getByTestId('summary-card-daily');
        expect(dailyCard.querySelector('[data-testid="severity-badge"]')).toHaveAttribute('data-severity', 'medium');
      });
    });
  });
});
