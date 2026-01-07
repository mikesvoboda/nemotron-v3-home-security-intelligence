import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import CameraCardSkeleton from './CameraCardSkeleton';

describe('CameraCardSkeleton', () => {
  it('renders skeleton container with correct test id', () => {
    render(<CameraCardSkeleton />);
    const skeleton = screen.getByTestId('camera-card-skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('matches CameraCard layout with thumbnail area', () => {
    render(<CameraCardSkeleton />);
    const thumbnail = screen.getByTestId('camera-card-skeleton-thumbnail');
    expect(thumbnail).toBeInTheDocument();
    expect(thumbnail).toHaveClass('aspect-video');
  });

  it('includes status indicator skeleton', () => {
    render(<CameraCardSkeleton />);
    const status = screen.getByTestId('camera-card-skeleton-status');
    expect(status).toBeInTheDocument();
  });

  it('includes camera name skeleton', () => {
    render(<CameraCardSkeleton />);
    const name = screen.getByTestId('camera-card-skeleton-name');
    expect(name).toBeInTheDocument();
  });

  it('applies custom className when provided', () => {
    render(<CameraCardSkeleton className="custom-class" />);
    const skeleton = screen.getByTestId('camera-card-skeleton');
    expect(skeleton).toHaveClass('custom-class');
  });

  it('has NVIDIA dark theme styling', () => {
    render(<CameraCardSkeleton />);
    const skeleton = screen.getByTestId('camera-card-skeleton');
    expect(skeleton).toHaveClass('bg-card');
    expect(skeleton).toHaveClass('border-gray-800');
  });

  it('has aria-hidden for accessibility', () => {
    render(<CameraCardSkeleton />);
    const skeleton = screen.getByTestId('camera-card-skeleton');
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
  });
});
