import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import EventCardSkeleton from './EventCardSkeleton';

describe('EventCardSkeleton', () => {
  it('renders skeleton container with correct test id', () => {
    render(<EventCardSkeleton />);
    const skeleton = screen.getByTestId('event-card-skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('matches EventCard layout structure with header section', () => {
    render(<EventCardSkeleton />);
    // Should have header with camera name and risk badge skeleton
    const headerSection = screen.getByTestId('event-card-skeleton-header');
    expect(headerSection).toBeInTheDocument();
  });

  it('includes thumbnail skeleton area', () => {
    render(<EventCardSkeleton />);
    const thumbnail = screen.getByTestId('event-card-skeleton-thumbnail');
    expect(thumbnail).toBeInTheDocument();
    // Thumbnail should have aspect ratio for image placeholder
    expect(thumbnail).toHaveClass('aspect-video');
  });

  it('includes summary text skeleton lines', () => {
    render(<EventCardSkeleton />);
    const summary = screen.getByTestId('event-card-skeleton-summary');
    expect(summary).toBeInTheDocument();
  });

  it('includes detections skeleton area', () => {
    render(<EventCardSkeleton />);
    const detections = screen.getByTestId('event-card-skeleton-detections');
    expect(detections).toBeInTheDocument();
  });

  it('applies custom className when provided', () => {
    render(<EventCardSkeleton className="custom-class" />);
    const skeleton = screen.getByTestId('event-card-skeleton');
    expect(skeleton).toHaveClass('custom-class');
  });

  it('has NVIDIA dark theme styling', () => {
    render(<EventCardSkeleton />);
    const skeleton = screen.getByTestId('event-card-skeleton');
    expect(skeleton).toHaveClass('bg-[#1F1F1F]');
    expect(skeleton).toHaveClass('border-gray-800');
  });

  it('has aria-hidden for accessibility', () => {
    render(<EventCardSkeleton />);
    const skeleton = screen.getByTestId('event-card-skeleton');
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
  });
});
