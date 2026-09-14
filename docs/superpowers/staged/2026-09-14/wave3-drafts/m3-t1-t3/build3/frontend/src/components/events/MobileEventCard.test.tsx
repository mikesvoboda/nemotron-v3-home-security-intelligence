import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import MobileEventCard from './MobileEventCard';

import type { Detection } from './EventCard';

describe('MobileEventCard', () => {
  const mockDetections: Detection[] = [
    { label: 'person', confidence: 0.95, bbox: { x: 100, y: 200, width: 300, height: 400 } },
    { label: 'car', confidence: 0.87, bbox: { x: 50, y: 100, width: 200, height: 250 } },
  ];

  const defaultProps = {
    id: 'event-123',
    timestamp: '2025-01-07T15:30:00Z',
    camera_name: 'Front Door',
    risk_score: 75,
    risk_label: 'High',
    summary: 'Person detected at front door with vehicle in frame',
    detections: mockDetections,
  };

  it('renders event information in compact layout', () => {
    render(<MobileEventCard {...defaultProps} />);

    expect(screen.getByText('Front Door')).toBeInTheDocument();
    expect(screen.getByText(/person detected at front door/i)).toBeInTheDocument();
  });

  it('displays thumbnail image when provided', () => {
    render(<MobileEventCard {...defaultProps} thumbnail_url="/test-image.jpg" />);

    const image = screen.getByRole('img', { name: /front door/i });
    expect(image).toBeInTheDocument();
    expect(image).toHaveAttribute('src', '/test-image.jpg');
  });

  it('displays risk score badge', () => {
    render(<MobileEventCard {...defaultProps} />);

    // RiskBadge displays "High (75)" format
    const badge = screen.getByRole('status', { name: /risk level/i });
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent('High (75)');
  });

  it('renders in single-line compact layout', () => {
    const { container } = render(<MobileEventCard {...defaultProps} />);

    // Check for flex row layout
    const card = container.querySelector('[data-testid="event-card-event-123"]');
    expect(card).toHaveClass('flex');
    expect(card).toHaveClass('flex-row');
  });

  it('has minimum touch target height of 44px', () => {
    const { container } = render(<MobileEventCard {...defaultProps} />);

    const card = container.querySelector('[data-testid="event-card-event-123"]');
    expect(card).toHaveClass('min-h-[44px]');
  });

  it('calls onSwipeLeft when swiped left', () => {
    const onSwipeLeft = vi.fn();
    render(<MobileEventCard {...defaultProps} onSwipeLeft={onSwipeLeft} />);

    const card = screen.getByTestId('event-card-event-123');

    // Simulate touch start
    fireEvent.touchStart(card, {
      touches: [{ clientX: 200, clientY: 100 }],
    });

    // Simulate touch end - swipe left
    fireEvent.touchEnd(card, {
      changedTouches: [{ clientX: 80, clientY: 100 }],
    });

    expect(onSwipeLeft).toHaveBeenCalledWith('event-123');
  });

  it('calls onSwipeRight when swiped right', () => {
    const onSwipeRight = vi.fn();
    render(<MobileEventCard {...defaultProps} onSwipeRight={onSwipeRight} />);

    const card = screen.getByTestId('event-card-event-123');

    // Simulate touch start
    fireEvent.touchStart(card, {
      touches: [{ clientX: 80, clientY: 100 }],
    });

    // Simulate touch end - swipe right
    fireEvent.touchEnd(card, {
      changedTouches: [{ clientX: 200, clientY: 100 }],
    });

    expect(onSwipeRight).toHaveBeenCalledWith('event-123');
  });

  it('displays action buttons when provided', () => {
    const onView = vi.fn();
    const onDelete = vi.fn();

    render(
      <MobileEventCard
        {...defaultProps}
        actions={[
          { label: 'View', onClick: onView, icon: 'eye' },
          { label: 'Delete', onClick: onDelete, icon: 'trash' },
        ]}
      />
    );

    expect(screen.getByLabelText(/view event-123/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/delete event-123/i)).toBeInTheDocument();
  });

  it('calls action callback when action button clicked', () => {
    const onView = vi.fn();

    render(
      <MobileEventCard
        {...defaultProps}
        actions={[{ label: 'View', onClick: onView, icon: 'eye' }]}
      />
    );

    const viewButton = screen.getByLabelText(/view event-123/i);
    fireEvent.click(viewButton);

    expect(onView).toHaveBeenCalledWith('event-123');
  });

  it('calls onClick when card is tapped', () => {
    const onClick = vi.fn();
    render(<MobileEventCard {...defaultProps} onClick={onClick} />);

    const card = screen.getByTestId('event-card-event-123');
    fireEvent.click(card);

    expect(onClick).toHaveBeenCalledWith('event-123');
  });

  it('does not call onClick when swiping', () => {
    const onClick = vi.fn();
    const onSwipeLeft = vi.fn();
    render(<MobileEventCard {...defaultProps} onClick={onClick} onSwipeLeft={onSwipeLeft} />);

    const card = screen.getByTestId('event-card-event-123');

    // Simulate swipe
    fireEvent.touchStart(card, {
      touches: [{ clientX: 200, clientY: 100 }],
    });
    fireEvent.touchEnd(card, {
      changedTouches: [{ clientX: 80, clientY: 100 }],
    });

    expect(onSwipeLeft).toHaveBeenCalled();
    expect(onClick).not.toHaveBeenCalled();
  });

  it('displays object type badges', () => {
    render(<MobileEventCard {...defaultProps} />);

    // ObjectTypeBadge displays capitalized names
    expect(screen.getByText('Person')).toBeInTheDocument();
    expect(screen.getByText('Vehicle')).toBeInTheDocument();
  });

  it('applies custom className to container', () => {
    const { container } = render(<MobileEventCard {...defaultProps} className="custom-class" />);

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('displays timestamp in relative format', () => {
    render(<MobileEventCard {...defaultProps} />);

    // Should show relative time like "X minutes ago" or "Just now"
    const timeElement = screen.getByText(/ago|now/i);
    expect(timeElement).toBeInTheDocument();
  });

  it('shows duration when started_at and ended_at provided', () => {
    render(
      <MobileEventCard
        {...defaultProps}
        started_at="2025-01-07T15:30:00Z"
        ended_at="2025-01-07T15:35:00Z"
      />
    );

    // Check for timer icon which indicates duration is shown
    const timerIcons = document.querySelectorAll('.lucide-timer');
    expect(timerIcons.length).toBeGreaterThan(0);
  });
});
