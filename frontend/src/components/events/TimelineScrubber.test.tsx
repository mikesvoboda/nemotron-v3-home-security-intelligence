import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import TimelineScrubber, {
  type TimelineScrubberProps,
  type TimelineBucket,
} from './TimelineScrubber';

describe('TimelineScrubber', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T12:00:00Z').getTime();

  // Mock buckets for testing - represents events grouped by time
  const createMockBuckets = (count: number, startTime = BASE_TIME): TimelineBucket[] => {
    const buckets: TimelineBucket[] = [];
    const hourMs = 60 * 60 * 1000;

    for (let i = 0; i < count; i++) {
      buckets.push({
        timestamp: new Date(startTime - i * hourMs).toISOString(),
        eventCount: Math.floor(Math.random() * 20) + 1,
        maxSeverity: (['low', 'medium', 'high', 'critical'] as const)[i % 4],
      });
    }
    return buckets.reverse(); // oldest first
  };

  const defaultBuckets: TimelineBucket[] = [
    { timestamp: '2024-01-15T06:00:00Z', eventCount: 5, maxSeverity: 'low' },
    { timestamp: '2024-01-15T07:00:00Z', eventCount: 12, maxSeverity: 'medium' },
    { timestamp: '2024-01-15T08:00:00Z', eventCount: 3, maxSeverity: 'high' },
    { timestamp: '2024-01-15T09:00:00Z', eventCount: 8, maxSeverity: 'critical' },
    { timestamp: '2024-01-15T10:00:00Z', eventCount: 15, maxSeverity: 'medium' },
    { timestamp: '2024-01-15T11:00:00Z', eventCount: 2, maxSeverity: 'low' },
  ];

  const defaultProps: TimelineScrubberProps = {
    buckets: defaultBuckets,
    onTimeRangeChange: vi.fn(),
    zoomLevel: 'day',
  };

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
      render(<TimelineScrubber {...defaultProps} />);
      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    it('renders timeline scrubber container', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} />);
      expect(container.querySelector('[data-testid="timeline-scrubber"]')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} className="custom-class" />);
      const scrubber = container.querySelector('[data-testid="timeline-scrubber"]');
      expect(scrubber).toHaveClass('custom-class');
    });

    it('renders zoom controls', () => {
      render(<TimelineScrubber {...defaultProps} />);
      expect(screen.getByRole('group', { name: /zoom controls/i })).toBeInTheDocument();
    });

    it('renders bar chart visualization', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} />);
      const bars = container.querySelectorAll('[data-testid="timeline-bar"]');
      expect(bars.length).toBe(defaultBuckets.length);
    });
  });

  describe('bar chart visualization', () => {
    it('renders bars with correct severity colors', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} />);

      // Check for each severity color class
      const lowBar = container.querySelector('[data-severity="low"]');
      const mediumBar = container.querySelector('[data-severity="medium"]');
      const highBar = container.querySelector('[data-severity="high"]');
      const criticalBar = container.querySelector('[data-severity="critical"]');

      expect(lowBar).toBeInTheDocument();
      expect(mediumBar).toBeInTheDocument();
      expect(highBar).toBeInTheDocument();
      expect(criticalBar).toBeInTheDocument();
    });

    it('uses green (#76B900) for low severity bars', () => {
      const lowOnlyBuckets: TimelineBucket[] = [
        { timestamp: '2024-01-15T06:00:00Z', eventCount: 5, maxSeverity: 'low' },
      ];
      const { container } = render(<TimelineScrubber {...defaultProps} buckets={lowOnlyBuckets} />);
      const bar = container.querySelector('[data-severity="low"]');
      expect(bar).toHaveClass('bg-green-500');
    });

    it('renders empty state when no buckets provided', () => {
      render(<TimelineScrubber {...defaultProps} buckets={[]} />);
      expect(screen.getByText(/no events in selected range/i)).toBeInTheDocument();
    });

    it('displays event count tooltip on bar hover', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const { container } = render(<TimelineScrubber {...defaultProps} />);

      const firstBar = container.querySelector('[data-testid="timeline-bar"]');
      expect(firstBar).toBeInTheDocument();

      if (firstBar) {
        await user.hover(firstBar);
        // Tooltip should show event count
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
      }

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('zoom controls', () => {
    it('renders hour zoom button', () => {
      render(<TimelineScrubber {...defaultProps} />);
      expect(screen.getByRole('button', { name: /hour/i })).toBeInTheDocument();
    });

    it('renders day zoom button', () => {
      render(<TimelineScrubber {...defaultProps} />);
      expect(screen.getByRole('button', { name: /day/i })).toBeInTheDocument();
    });

    it('renders week zoom button', () => {
      render(<TimelineScrubber {...defaultProps} />);
      expect(screen.getByRole('button', { name: /week/i })).toBeInTheDocument();
    });

    it('highlights active zoom level', () => {
      render(<TimelineScrubber {...defaultProps} zoomLevel="day" />);
      const dayButton = screen.getByRole('button', { name: /day/i });
      expect(dayButton).toHaveClass('bg-[#76B900]');
    });

    it('calls onZoomChange when zoom button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onZoomChange = vi.fn();
      render(<TimelineScrubber {...defaultProps} onZoomChange={onZoomChange} />);

      const weekButton = screen.getByRole('button', { name: /week/i });
      await user.click(weekButton);

      expect(onZoomChange).toHaveBeenCalledWith('week');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('time range selection', () => {
    it('calls onTimeRangeChange when clicking on a bar', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onTimeRangeChange = vi.fn();
      const { container } = render(
        <TimelineScrubber {...defaultProps} onTimeRangeChange={onTimeRangeChange} />
      );

      const firstBar = container.querySelector('[data-testid="timeline-bar"]');
      if (firstBar) {
        await user.click(firstBar);
        expect(onTimeRangeChange).toHaveBeenCalled();
      }

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('passes correct time range when bar is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onTimeRangeChange = vi.fn();
      const { container } = render(
        <TimelineScrubber {...defaultProps} onTimeRangeChange={onTimeRangeChange} />
      );

      const firstBar = container.querySelector('[data-testid="timeline-bar"]');
      if (firstBar) {
        await user.click(firstBar);
        const callArgs = onTimeRangeChange.mock.calls[0][0];
        expect(callArgs).toHaveProperty('startDate');
        expect(callArgs).toHaveProperty('endDate');
      }

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('supports drag selection for time range', () => {
      const onTimeRangeChange = vi.fn();
      const { container } = render(
        <TimelineScrubber {...defaultProps} onTimeRangeChange={onTimeRangeChange} />
      );

      const barsContainer = container.querySelector('[data-testid="timeline-bars-container"]');
      expect(barsContainer).toBeInTheDocument();

      if (barsContainer) {
        // Mock getBoundingClientRect for the container
        const mockRect = { left: 0, width: 600, top: 0, height: 64 };
        vi.spyOn(barsContainer, 'getBoundingClientRect').mockReturnValue(mockRect as DOMRect);

        // Simulate drag start at x=50
        fireEvent.mouseDown(barsContainer, { clientX: 50 });
        // Simulate drag to x=300
        fireEvent.mouseMove(barsContainer, { clientX: 300 });
        // Simulate drag end at x=300
        fireEvent.mouseUp(barsContainer, { clientX: 300 });

        // Should be called with a time range since start and end indices differ
        expect(onTimeRangeChange).toHaveBeenCalled();
      }
    });
  });

  describe('current viewport indicator', () => {
    it('renders viewport indicator when currentRange is provided', () => {
      const { container } = render(
        <TimelineScrubber
          {...defaultProps}
          currentRange={{
            startDate: '2024-01-15T07:00:00Z',
            endDate: '2024-01-15T09:00:00Z',
          }}
        />
      );
      expect(container.querySelector('[data-testid="viewport-indicator"]')).toBeInTheDocument();
    });

    it('does not render viewport indicator when currentRange is not provided', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} />);
      expect(container.querySelector('[data-testid="viewport-indicator"]')).not.toBeInTheDocument();
    });

    it('positions viewport indicator correctly', () => {
      const { container } = render(
        <TimelineScrubber
          {...defaultProps}
          currentRange={{
            startDate: '2024-01-15T07:00:00Z',
            endDate: '2024-01-15T09:00:00Z',
          }}
        />
      );
      const indicator = container.querySelector('[data-testid="viewport-indicator"]');
      expect(indicator).toBeInTheDocument();
      // Verify the indicator has inline style for left and width
      expect(indicator).toHaveAttribute('style');
      const style = indicator?.getAttribute('style');
      expect(style).toContain('left:');
      expect(style).toContain('width:');
    });

    it('uses NVIDIA green color for viewport indicator border', () => {
      const { container } = render(
        <TimelineScrubber
          {...defaultProps}
          currentRange={{
            startDate: '2024-01-15T07:00:00Z',
            endDate: '2024-01-15T09:00:00Z',
          }}
        />
      );
      const indicator = container.querySelector('[data-testid="viewport-indicator"]');
      expect(indicator).toHaveClass('border-[#76B900]');
    });
  });

  describe('time labels', () => {
    it('renders time labels at regular intervals', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} />);
      const labels = container.querySelectorAll('[data-testid="time-label"]');
      expect(labels.length).toBeGreaterThan(0);
    });

    it('formats hour labels correctly for hour zoom', () => {
      render(<TimelineScrubber {...defaultProps} zoomLevel="hour" />);
      // Should show time labels with HH:MM format (e.g., "01:00 AM")
      const labels = screen.getAllByTestId('time-label');
      expect(labels.length).toBeGreaterThan(0);
      // At least one label should contain a time format
      const hasTimeFormat = labels.some((label) => /\d{1,2}:\d{2}/.test(label.textContent || ''));
      expect(hasTimeFormat).toBe(true);
    });

    it('formats day labels correctly for day zoom', () => {
      render(<TimelineScrubber {...defaultProps} zoomLevel="day" />);
      // Should show hour-level labels like "6 AM", "12 PM", etc.
      const labels = screen.getAllByTestId('time-label');
      expect(labels.length).toBeGreaterThan(0);
      // At least one label should contain AM/PM
      const hasAMPMFormat = labels.some((label) => /AM|PM/i.test(label.textContent || ''));
      expect(hasAMPMFormat).toBe(true);
    });

    it('formats week labels correctly for week zoom', () => {
      const weekBuckets = createMockBuckets(7 * 24, BASE_TIME);
      render(<TimelineScrubber {...defaultProps} buckets={weekBuckets} zoomLevel="week" />);
      // Should show day-level labels like "Mon", "Tue", etc.
      const labels = screen.getAllByTestId('time-label');
      expect(labels.length).toBeGreaterThan(0);
      // At least one label should contain a day abbreviation
      const hasDayFormat = labels.some((label) =>
        /Mon|Tue|Wed|Thu|Fri|Sat|Sun/i.test(label.textContent || '')
      );
      expect(hasDayFormat).toBe(true);
    });
  });

  describe('accessibility', () => {
    it('has slider role for the scrubber', () => {
      render(<TimelineScrubber {...defaultProps} />);
      expect(screen.getByRole('slider')).toBeInTheDocument();
    });

    it('has correct aria-label', () => {
      render(<TimelineScrubber {...defaultProps} />);
      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-label', expect.stringMatching(/timeline/i));
    });

    it('has aria-valuemin and aria-valuemax attributes', () => {
      render(<TimelineScrubber {...defaultProps} />);
      const slider = screen.getByRole('slider');
      expect(slider).toHaveAttribute('aria-valuemin');
      expect(slider).toHaveAttribute('aria-valuemax');
    });

    it('supports keyboard navigation', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onTimeRangeChange = vi.fn();
      render(<TimelineScrubber {...defaultProps} onTimeRangeChange={onTimeRangeChange} />);

      const slider = screen.getByRole('slider');
      slider.focus();

      // Arrow right should move forward
      await user.keyboard('{ArrowRight}');
      expect(onTimeRangeChange).toHaveBeenCalled();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('supports keyboard navigation with ArrowLeft', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onTimeRangeChange = vi.fn();
      render(<TimelineScrubber {...defaultProps} onTimeRangeChange={onTimeRangeChange} />);

      const slider = screen.getByRole('slider');
      slider.focus();

      // First move right to be able to move left
      await user.keyboard('{ArrowRight}');
      onTimeRangeChange.mockClear();

      // Now ArrowLeft should work
      await user.keyboard('{ArrowLeft}');
      expect(onTimeRangeChange).toHaveBeenCalled();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('zoom controls are keyboard accessible', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onZoomChange = vi.fn();
      render(<TimelineScrubber {...defaultProps} onZoomChange={onZoomChange} />);

      const hourButton = screen.getByRole('button', { name: /hour/i });
      hourButton.focus();
      await user.keyboard('{Enter}');

      expect(onZoomChange).toHaveBeenCalledWith('hour');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('loading state', () => {
    it('renders loading skeleton when isLoading is true', () => {
      render(<TimelineScrubber {...defaultProps} isLoading />);
      expect(screen.getByTestId('timeline-scrubber-skeleton')).toBeInTheDocument();
    });

    it('does not render bars when loading', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} isLoading />);
      expect(container.querySelector('[data-testid="timeline-bar"]')).not.toBeInTheDocument();
    });
  });

  describe('dark theme styling', () => {
    it('applies dark background', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} />);
      const scrubber = container.querySelector('[data-testid="timeline-scrubber"]');
      expect(scrubber).toHaveClass('bg-[#1F1F1F]');
    });

    it('applies border styling', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} />);
      const scrubber = container.querySelector('[data-testid="timeline-scrubber"]');
      expect(scrubber).toHaveClass('border-gray-800');
    });

    it('uses gray text for labels', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} />);
      const label = container.querySelector('[data-testid="time-label"]');
      expect(label).toHaveClass('text-gray-400');
    });
  });

  describe('summary stats', () => {
    it('displays total event count', () => {
      // Total events = 5+12+3+8+15+2 = 45
      render(<TimelineScrubber {...defaultProps} />);
      expect(screen.getByText(/45 events/i)).toBeInTheDocument();
    });

    it('displays time range', () => {
      render(<TimelineScrubber {...defaultProps} />);
      // Should show the time span covered by the buckets (06:00 to 11:00 = 5 hours)
      expect(screen.getByText(/5 hours/i)).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles single bucket', () => {
      const singleBucket: TimelineBucket[] = [
        { timestamp: '2024-01-15T06:00:00Z', eventCount: 5, maxSeverity: 'low' },
      ];
      const { container } = render(<TimelineScrubber {...defaultProps} buckets={singleBucket} />);
      const bars = container.querySelectorAll('[data-testid="timeline-bar"]');
      expect(bars.length).toBe(1);
    });

    it('handles buckets with zero events', () => {
      const bucketsWithZero: TimelineBucket[] = [
        { timestamp: '2024-01-15T06:00:00Z', eventCount: 0, maxSeverity: 'low' },
        { timestamp: '2024-01-15T07:00:00Z', eventCount: 5, maxSeverity: 'medium' },
      ];
      const { container } = render(
        <TimelineScrubber {...defaultProps} buckets={bucketsWithZero} />
      );

      // Zero event bucket should still render but with minimal height
      const firstBar = container.querySelector('[data-bucket-index="0"]');
      expect(firstBar).toBeInTheDocument();
    });

    it('handles large number of buckets', () => {
      const manyBuckets = createMockBuckets(100);
      const { container } = render(<TimelineScrubber {...defaultProps} buckets={manyBuckets} />);
      const bars = container.querySelectorAll('[data-testid="timeline-bar"]');
      expect(bars.length).toBe(100);
    });
  });

  describe('custom date range (NEM-3585)', () => {
    it('renders custom range button when onCustomRangeSelect is provided', () => {
      const onCustomRangeSelect = vi.fn();
      const { container } = render(
        <TimelineScrubber {...defaultProps} onCustomRangeSelect={onCustomRangeSelect} />
      );
      expect(container.querySelector('[data-testid="custom-range-button"]')).toBeInTheDocument();
    });

    it('does not render custom range button when onCustomRangeSelect is not provided', () => {
      const { container } = render(<TimelineScrubber {...defaultProps} />);
      expect(container.querySelector('[data-testid="custom-range-button"]')).not.toBeInTheDocument();
    });

    it('opens date picker modal when custom range button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber {...defaultProps} onCustomRangeSelect={onCustomRangeSelect} />
      );

      const customRangeButton = screen.getByTestId('custom-range-button');
      await user.click(customRangeButton);

      expect(screen.getByTestId('date-range-picker-modal')).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onCustomRangeSelect when date range is applied', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber
          {...defaultProps}
          onCustomRangeSelect={onCustomRangeSelect}
          initialStartDate="2024-01-01"
          initialEndDate="2024-01-15"
        />
      );

      // Open the date picker
      const customRangeButton = screen.getByTestId('custom-range-button');
      await user.click(customRangeButton);

      // Apply the date range
      const applyButton = screen.getByTestId('date-range-apply');
      await user.click(applyButton);

      expect(onCustomRangeSelect).toHaveBeenCalledWith('2024-01-01', '2024-01-15');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('renders reset button when isCustomRangeActive is true', () => {
      const onReset = vi.fn();
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber
          {...defaultProps}
          onCustomRangeSelect={onCustomRangeSelect}
          isCustomRangeActive
          onReset={onReset}
        />
      );
      expect(screen.getByTestId('timeline-reset-button')).toBeInTheDocument();
    });

    it('does not render reset button when isCustomRangeActive is false', () => {
      const onReset = vi.fn();
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber
          {...defaultProps}
          onCustomRangeSelect={onCustomRangeSelect}
          isCustomRangeActive={false}
          onReset={onReset}
        />
      );
      expect(screen.queryByTestId('timeline-reset-button')).not.toBeInTheDocument();
    });

    it('calls onReset when reset button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onReset = vi.fn();
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber
          {...defaultProps}
          onCustomRangeSelect={onCustomRangeSelect}
          isCustomRangeActive
          onReset={onReset}
        />
      );

      const resetButton = screen.getByTestId('timeline-reset-button');
      await user.click(resetButton);

      expect(onReset).toHaveBeenCalledTimes(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('custom range button shows active state when isCustomRangeActive is true', () => {
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber
          {...defaultProps}
          onCustomRangeSelect={onCustomRangeSelect}
          isCustomRangeActive
        />
      );
      const customRangeButton = screen.getByTestId('custom-range-button');
      expect(customRangeButton).toHaveClass('border-[#76B900]');
      expect(customRangeButton).toHaveClass('text-[#76B900]');
    });

    it('custom range button shows inactive state when isCustomRangeActive is false', () => {
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber
          {...defaultProps}
          onCustomRangeSelect={onCustomRangeSelect}
          isCustomRangeActive={false}
        />
      );
      const customRangeButton = screen.getByTestId('custom-range-button');
      expect(customRangeButton).toHaveClass('border-gray-700');
      expect(customRangeButton).toHaveClass('text-gray-400');
    });

    it('passes initial dates to the date picker modal', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber
          {...defaultProps}
          onCustomRangeSelect={onCustomRangeSelect}
          initialStartDate="2024-01-10"
          initialEndDate="2024-01-20"
        />
      );

      // Open the date picker
      const customRangeButton = screen.getByTestId('custom-range-button');
      await user.click(customRangeButton);

      // Check that initial dates are populated
      const startInput = screen.getByTestId('start-date-input');
      const endInput = screen.getByTestId('end-date-input');

      expect((startInput as HTMLInputElement).value).toBe('2024-01-10');
      expect((endInput as HTMLInputElement).value).toBe('2024-01-20');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('closes date picker modal when cancel is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber {...defaultProps} onCustomRangeSelect={onCustomRangeSelect} />
      );

      // Open the date picker
      const customRangeButton = screen.getByTestId('custom-range-button');
      await user.click(customRangeButton);
      expect(screen.getByTestId('date-range-picker-modal')).toBeInTheDocument();

      // Cancel
      const cancelButton = screen.getByTestId('date-range-cancel');
      await user.click(cancelButton);

      // Modal should be closed
      expect(screen.queryByTestId('date-range-picker-modal')).not.toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('has accessible label on custom range button', () => {
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber {...defaultProps} onCustomRangeSelect={onCustomRangeSelect} />
      );
      const customRangeButton = screen.getByTestId('custom-range-button');
      expect(customRangeButton).toHaveAttribute('aria-label', 'Select custom date range');
    });

    it('has accessible label on reset button', () => {
      const onReset = vi.fn();
      const onCustomRangeSelect = vi.fn();
      render(
        <TimelineScrubber
          {...defaultProps}
          onCustomRangeSelect={onCustomRangeSelect}
          isCustomRangeActive
          onReset={onReset}
        />
      );
      const resetButton = screen.getByTestId('timeline-reset-button');
      expect(resetButton).toHaveAttribute('aria-label', 'Reset to default date range');
    });
  });
});
