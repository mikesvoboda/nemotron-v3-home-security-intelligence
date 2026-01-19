/**
 * Accessibility Tests for SummaryCards Component
 *
 * Comprehensive WCAG 2.1 AA compliance testing using vitest-axe.
 * Tests all states (loading, error, empty, content) for accessibility violations.
 *
 * @see NEM-2930 - Comprehensive Summary Card Test Suite
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeAll, afterEach } from 'vitest';
import { axe } from 'vitest-axe';
import * as axeMatchers from 'vitest-axe/matchers';

// Import for type augmentation
import '@/__tests__/matchers';

import { SummaryCards, SummaryCard } from './SummaryCards';

import {
  mockSummaryHighSeverity,
  mockSummaryAllClear,
  mockSummaryMediumSeverity,
  mockSummaryEmpty,
  mockSummaryLongContent,
  createMockSummary,
} from '@/test/fixtures/summaries';

// Extend Vitest matchers with axe matchers
expect.extend(axeMatchers);

describe('SummaryCards Accessibility Tests', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  // Suppress console errors during axe tests (expected behavior)
  beforeAll(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    if (consoleErrorSpy) {
      consoleErrorSpy.mockRestore();
    }
  });

  describe('WCAG 2.1 AA Compliance - All States', () => {
    it('loading state has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCards hourly={null} daily={null} isLoading={true} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('empty state has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCards hourly={null} daily={null} isLoading={false} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('content state (hourly) has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={null}
          isLoading={false}
        />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('content state (daily) has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCards
          hourly={null}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('content state (both cards) has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('mixed state (hourly loading, daily content) has no violations', async () => {
      const { container, rerender } = render(
        <SummaryCards hourly={null} daily={mockSummaryAllClear} isLoading={false} />
      );

      // Change hourly to loading state
      rerender(
        <SummaryCards hourly={null} daily={mockSummaryAllClear} isLoading={true} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('critical severity state has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCard type="hourly" summary={mockSummaryHighSeverity} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('all clear severity state has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCard type="daily" summary={mockSummaryAllClear} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('medium severity state has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCard type="hourly" summary={mockSummaryMediumSeverity} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('empty content state has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCard type="hourly" summary={mockSummaryEmpty} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('long content state has no accessibility violations', async () => {
      const { container } = render(
        <SummaryCard type="hourly" summary={mockSummaryLongContent} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('Keyboard Navigation', () => {
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

      // Tab to focus View Full Summary button
      const viewFullButton = screen.getByTestId('summary-view-full-hourly');
      viewFullButton.focus();

      // Verify button is focused
      expect(viewFullButton).toHaveFocus();

      // Press Enter
      await user.keyboard('{Enter}');
      expect(onViewFull).toHaveBeenCalledWith(mockSummaryHighSeverity);

      // Press Space (should also work)
      viewFullButton.focus();
      await user.keyboard(' ');
      expect(onViewFull).toHaveBeenCalledTimes(2);
    });

    it('supports tab navigation between multiple summary cards', async () => {
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

      const hourlyButton = screen.getByTestId('summary-view-full-hourly');
      const dailyButton = screen.getByTestId('summary-view-full-daily');

      // Focus first button
      hourlyButton.focus();
      expect(hourlyButton).toHaveFocus();

      // Tab to second button
      await user.tab();
      expect(dailyButton).toHaveFocus();

      // Can activate second button
      await user.keyboard('{Enter}');
      expect(onViewFull).toHaveBeenCalledWith(mockSummaryAllClear);
    });

    it('has no keyboard traps in loading state', async () => {
      const user = userEvent.setup();

      render(<SummaryCards hourly={null} daily={null} isLoading={true} />);

      // Loading state should not trap keyboard focus
      // Tab should move through the document normally
      await user.tab();
      const activeElement = document.activeElement;

      // Should be able to tab to next element (not stuck in skeleton)
      expect(activeElement).not.toBe(screen.getByTestId('summary-card-hourly-loading'));
    });

    it('has no keyboard traps in empty state', async () => {
      const user = userEvent.setup();

      render(<SummaryCards hourly={null} daily={null} isLoading={false} />);

      // Empty state should not trap keyboard focus
      await user.tab();
      const activeElement = document.activeElement;

      // Should be able to tab through document
      expect(activeElement).toBeTruthy();
    });
  });

  describe('Screen Reader Compatibility', () => {
    it('has proper ARIA labels for time icons', () => {
      render(
        <SummaryCard type="hourly" summary={mockSummaryHighSeverity} />
      );

      const hourlyIcon = screen.getByTestId('summary-card-hourly').querySelector('svg.lucide-clock');
      expect(hourlyIcon).toHaveAttribute('aria-hidden', 'true');
    });

    it('has proper ARIA labels for calendar icons', () => {
      render(
        <SummaryCard type="daily" summary={mockSummaryAllClear} />
      );

      const dailyIcon = screen.getByTestId('summary-card-daily').querySelector('svg.lucide-calendar');
      expect(dailyIcon).toHaveAttribute('aria-hidden', 'true');
    });

    it('decorative icons are marked aria-hidden', () => {
      render(
        <SummaryCard type="hourly" summary={mockSummaryHighSeverity} />
      );

      // All decorative icons should have aria-hidden="true"
      const card = screen.getByTestId('summary-card-hourly');
      const icons = card.querySelectorAll('svg[aria-hidden="true"]');
      expect(icons.length).toBeGreaterThan(0);
    });

    it('provides meaningful text content for screen readers', () => {
      render(
        <SummaryCard type="hourly" summary={mockSummaryHighSeverity} />
      );

      // Title should be accessible
      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();

      // Time window should be accessible
      expect(screen.getByText('Last 60 minutes')).toBeInTheDocument();

      // Event count should be accessible
      expect(screen.getByTestId('summary-event-count-hourly')).toHaveTextContent('3 events analyzed');
    });

    it('severity badge has accessible text', () => {
      render(
        <SummaryCard type="hourly" summary={mockSummaryHighSeverity} />
      );

      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveTextContent('CRITICAL');
      expect(badge).toHaveAttribute('data-severity', 'critical');
    });

    it('loading state provides accessible text', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading={true} />);

      // Loading skeleton should be identifiable
      expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();

      // Title should still be accessible during loading
      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
    });

    it('empty state provides clear messaging', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading={false} />);

      // Empty state message should be accessible
      expect(screen.getByText(/No summary available yet/)).toBeInTheDocument();
      expect(screen.getByText(/Summaries are generated every 5 minutes/)).toBeInTheDocument();
    });

    it('View Full Summary button has descriptive text', () => {
      const onViewFull = vi.fn();

      render(
        <SummaryCard
          type="hourly"
          summary={mockSummaryHighSeverity}
          onViewFull={onViewFull}
        />
      );

      const button = screen.getByTestId('summary-view-full-hourly');
      expect(button).toHaveTextContent('View Full Summary');
      expect(button).toHaveAttribute('type', 'button');
    });
  });

  describe('Color Contrast and Visual Accessibility', () => {
    it('critical severity badge has sufficient contrast', async () => {
      const { container } = render(
        <SummaryCard type="hourly" summary={mockSummaryHighSeverity} />
      );

      // Run axe with color-contrast rule
      const results = await axe(container, {
        rules: {
          'color-contrast': { enabled: true },
        },
      });

      expect(results).toHaveNoViolations();
    });

    it('all clear badge has sufficient contrast', async () => {
      const { container } = render(
        <SummaryCard type="daily" summary={mockSummaryAllClear} />
      );

      const results = await axe(container, {
        rules: {
          'color-contrast': { enabled: true },
        },
      });

      expect(results).toHaveNoViolations();
    });

    it('loading state skeleton has sufficient contrast', async () => {
      const { container } = render(
        <SummaryCard type="hourly" summary={null} isLoading={true} />
      );

      const results = await axe(container, {
        rules: {
          'color-contrast': { enabled: true },
        },
      });

      expect(results).toHaveNoViolations();
    });

    it('empty state text has sufficient contrast', async () => {
      const { container } = render(
        <SummaryCard type="hourly" summary={null} isLoading={false} />
      );

      const results = await axe(container, {
        rules: {
          'color-contrast': { enabled: true },
        },
      });

      expect(results).toHaveNoViolations();
    });

    it('accent bar colors are visually distinct', () => {
      const { container: criticalContainer } = render(
        <SummaryCard type="hourly" summary={mockSummaryHighSeverity} />
      );

      const { container: clearContainer } = render(
        <SummaryCard type="daily" summary={mockSummaryAllClear} />
      );

      const criticalAccent = criticalContainer.querySelector('[data-testid="accent-bar"]');
      const clearAccent = clearContainer.querySelector('[data-testid="accent-bar"]');

      // Accent bars should have different colors
      expect(criticalAccent).toHaveStyle({ backgroundColor: 'rgb(239, 68, 68)' }); // red-500
      expect(clearAccent).toHaveStyle({ backgroundColor: 'rgb(16, 185, 129)' }); // emerald-500
    });
  });

  describe('Semantic HTML and Structure', () => {
    it('uses semantic HTML for card structure', async () => {
      const { container } = render(
        <SummaryCard type="hourly" summary={mockSummaryHighSeverity} />
      );

      // Should not have heading-level issues
      const results = await axe(container, {
        rules: {
          'heading-order': { enabled: true },
        },
      });

      expect(results).toHaveNoViolations();
    });

    it('uses button element for View Full Summary', () => {
      const onViewFull = vi.fn();

      render(
        <SummaryCard
          type="hourly"
          summary={mockSummaryHighSeverity}
          onViewFull={onViewFull}
        />
      );

      const button = screen.getByTestId('summary-view-full-hourly');
      expect(button.tagName).toBe('BUTTON');
      expect(button).toHaveAttribute('type', 'button');
    });

    it('has proper container structure', () => {
      render(
        <SummaryCards
          hourly={mockSummaryHighSeverity}
          daily={mockSummaryAllClear}
          isLoading={false}
        />
      );

      const container = screen.getByTestId('summary-cards');
      expect(container).toBeInTheDocument();
      expect(container).toHaveClass('space-y-4');
    });

    it('uses proper data attributes for testability', () => {
      render(
        <SummaryCard type="hourly" summary={mockSummaryHighSeverity} />
      );

      const card = screen.getByTestId('summary-card-hourly');
      expect(card).toHaveAttribute('data-severity', 'critical');
    });
  });

  describe('Interactive Elements', () => {
    it('View Full Summary button has hover state', () => {
      const onViewFull = vi.fn();

      render(
        <SummaryCard
          type="hourly"
          summary={mockSummaryHighSeverity}
          onViewFull={onViewFull}
        />
      );

      const button = screen.getByTestId('summary-view-full-hourly');

      // Button should have hover styles (transition-colors class)
      expect(button).toHaveClass('transition-colors');
      expect(button).toHaveClass('hover:text-blue-300');
    });

    it('View Full Summary button has focus state', () => {
      const onViewFull = vi.fn();

      render(
        <SummaryCard
          type="hourly"
          summary={mockSummaryHighSeverity}
          onViewFull={onViewFull}
        />
      );

      const button = screen.getByTestId('summary-view-full-hourly');
      button.focus();

      // Button should be focusable
      expect(button).toHaveFocus();
    });

    it('has no interactive elements in loading state', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading={true} />);

      // Loading state should not have buttons or interactive elements
      const buttons = screen.queryAllByRole('button');
      expect(buttons).toHaveLength(0);
    });

    it('has no interactive elements in empty state', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading={false} />);

      // Empty state should not have interactive elements
      const buttons = screen.queryAllByRole('button');
      expect(buttons).toHaveLength(0);
    });
  });

  describe('Dynamic Content Updates', () => {
    it('maintains accessibility when transitioning between states', async () => {
      const { container, rerender } = render(
        <SummaryCard type="hourly" summary={null} isLoading={true} />
      );

      // Loading state should be accessible
      let results = await axe(container);
      expect(results).toHaveNoViolations();

      // Transition to content state
      rerender(<SummaryCard type="hourly" summary={mockSummaryHighSeverity} />);

      // Content state should be accessible
      results = await axe(container);
      expect(results).toHaveNoViolations();

      // Transition to empty state
      rerender(<SummaryCard type="hourly" summary={null} isLoading={false} />);

      // Empty state should be accessible
      results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('maintains accessibility when severity changes', async () => {
      const { container, rerender } = render(
        <SummaryCard type="hourly" summary={mockSummaryAllClear} />
      );

      let results = await axe(container);
      expect(results).toHaveNoViolations();

      // Change to high severity
      rerender(<SummaryCard type="hourly" summary={mockSummaryHighSeverity} />);

      results = await axe(container);
      expect(results).toHaveNoViolations();

      // Change to medium severity
      rerender(<SummaryCard type="hourly" summary={mockSummaryMediumSeverity} />);

      results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('Edge Cases', () => {
    it('handles summary with no bullet points accessibly', async () => {
      const summaryNoBullets = createMockSummary({
        content: 'Simple text content without bullet points.',
        eventCount: 1,
        bulletPoints: [],
      });

      const { container } = render(
        <SummaryCard type="hourly" summary={summaryNoBullets} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('handles summary with many bullet points accessibly', async () => {
      const summaryManyBullets = createMockSummary({
        content: 'Multiple events detected.',
        eventCount: 10,
        bulletPoints: [
          { icon: 'alert', text: 'Event 1', severity: 80 },
          { icon: 'alert', text: 'Event 2', severity: 75 },
          { icon: 'alert', text: 'Event 3', severity: 70 },
          { icon: 'alert', text: 'Event 4', severity: 65 },
          { icon: 'alert', text: 'Event 5', severity: 60 },
          { icon: 'alert', text: 'Event 6', severity: 55 },
        ],
      });

      const { container } = render(
        <SummaryCard type="hourly" summary={summaryManyBullets} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('handles very long summary text accessibly', async () => {
      const { container } = render(
        <SummaryCard type="hourly" summary={mockSummaryLongContent} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('handles summary with special characters accessibly', async () => {
      const summarySpecialChars = createMockSummary({
        content: 'Summary with <special> & "characters" that need escaping.',
        eventCount: 1,
      });

      const { container } = render(
        <SummaryCard type="hourly" summary={summarySpecialChars} />
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
});
