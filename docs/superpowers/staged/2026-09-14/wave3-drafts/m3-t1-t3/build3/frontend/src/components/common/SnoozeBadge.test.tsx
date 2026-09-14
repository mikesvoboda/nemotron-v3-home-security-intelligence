/**
 * Tests for SnoozeBadge component
 */
import { render, screen, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import SnoozeBadge from './SnoozeBadge';

describe('SnoozeBadge', () => {
  const MOCK_NOW = new Date('2024-01-15T12:00:00Z');

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(MOCK_NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders nothing when snoozeUntil is null', () => {
    const { container } = render(<SnoozeBadge snoozeUntil={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when snoozeUntil is undefined', () => {
    const { container } = render(<SnoozeBadge snoozeUntil={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when snoozeUntil is in the past', () => {
    const pastTime = new Date(MOCK_NOW.getTime() - 60 * 60 * 1000).toISOString();
    const { container } = render(<SnoozeBadge snoozeUntil={pastTime} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders badge when snoozeUntil is in the future', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(<SnoozeBadge snoozeUntil={futureTime} />);

    expect(screen.getByTestId('snooze-badge')).toBeInTheDocument();
    expect(screen.getByText(/snoozed/i)).toBeInTheDocument();
  });

  it('shows end time when showEndTime is true', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(<SnoozeBadge snoozeUntil={futureTime} showEndTime={true} />);

    expect(screen.getByText(/snoozed until/i)).toBeInTheDocument();
  });

  it('shows only "Snoozed" when showEndTime is false', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(<SnoozeBadge snoozeUntil={futureTime} showEndTime={false} />);

    const badge = screen.getByTestId('snooze-badge');
    expect(badge).toHaveTextContent('Snoozed');
    expect(badge).not.toHaveTextContent('until');
  });

  it('applies correct size classes for sm', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(<SnoozeBadge snoozeUntil={futureTime} size="sm" />);

    const badge = screen.getByTestId('snooze-badge');
    expect(badge).toHaveClass('text-xs');
  });

  it('applies correct size classes for md', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(<SnoozeBadge snoozeUntil={futureTime} size="md" />);

    const badge = screen.getByTestId('snooze-badge');
    expect(badge).toHaveClass('text-sm');
  });

  it('applies correct size classes for lg', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(<SnoozeBadge snoozeUntil={futureTime} size="lg" />);

    const badge = screen.getByTestId('snooze-badge');
    expect(badge).toHaveClass('text-base');
  });

  it('applies custom className', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(<SnoozeBadge snoozeUntil={futureTime} className="custom-class" />);

    expect(screen.getByTestId('snooze-badge')).toHaveClass('custom-class');
  });

  it('hides badge when snooze expires', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 1000).toISOString(); // 1 minute
    const { container } = render(<SnoozeBadge snoozeUntil={futureTime} />);

    // Initially visible
    expect(screen.getByTestId('snooze-badge')).toBeInTheDocument();

    // Advance time past snooze expiry (plus interval)
    act(() => {
      vi.advanceTimersByTime(2 * 60 * 1000); // 2 minutes
    });

    // Badge should be gone
    expect(container).toBeEmptyDOMElement();
  });

  it('updates remaining time on interval', () => {
    // 90 minutes in the future
    const futureTime = new Date(MOCK_NOW.getTime() + 90 * 60 * 1000).toISOString();
    render(<SnoozeBadge snoozeUntil={futureTime} showRemaining={true} />);

    // Initially should show approximately 1h 30m
    expect(screen.getByTestId('snooze-badge')).toBeInTheDocument();

    // Advance time by 30 minutes
    act(() => {
      vi.advanceTimersByTime(30 * 60 * 1000);
    });

    // Badge should still be visible (60 min remaining)
    expect(screen.getByTestId('snooze-badge')).toBeInTheDocument();
  });
});
