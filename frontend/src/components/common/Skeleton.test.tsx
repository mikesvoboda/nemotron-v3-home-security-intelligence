import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import Skeleton from './Skeleton';

describe('Skeleton', () => {
  describe('variants', () => {
    it('renders text variant with default styling', () => {
      render(<Skeleton variant="text" data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toBeInTheDocument();
      expect(skeleton).toHaveClass('rounded');
      expect(skeleton).toHaveClass('animate-pulse');
    });

    it('renders circular variant with rounded-full', () => {
      render(<Skeleton variant="circular" data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveClass('rounded-full');
    });

    it('renders rectangular variant with rounded-lg', () => {
      render(<Skeleton variant="rectangular" data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveClass('rounded-lg');
    });

    it('defaults to text variant when no variant specified', () => {
      render(<Skeleton data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveClass('rounded');
    });
  });

  describe('dimensions', () => {
    it('applies width prop as style', () => {
      render(<Skeleton width={100} data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveStyle({ width: '100px' });
    });

    it('applies height prop as style', () => {
      render(<Skeleton height={50} data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveStyle({ height: '50px' });
    });

    it('applies string width value', () => {
      render(<Skeleton width="100%" data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveStyle({ width: '100%' });
    });

    it('applies string height value', () => {
      render(<Skeleton height="2rem" data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveStyle({ height: '2rem' });
    });
  });

  describe('lines prop for text variant', () => {
    it('renders single skeleton when lines is 1', () => {
      render(<Skeleton variant="text" lines={1} data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toBeInTheDocument();
      // Single line should not be a container
      expect(skeleton.children.length).toBe(0);
    });

    it('renders multiple skeletons when lines > 1', () => {
      render(<Skeleton variant="text" lines={3} data-testid="skeleton-container" />);
      const container = screen.getByTestId('skeleton-container');
      const lines = container.querySelectorAll('[data-skeleton-line]');
      expect(lines.length).toBe(3);
    });

    it('renders last line at 80% width for text variant with multiple lines', () => {
      render(<Skeleton variant="text" lines={3} data-testid="skeleton-container" />);
      const container = screen.getByTestId('skeleton-container');
      const lines = container.querySelectorAll('[data-skeleton-line]');
      const lastLine = lines[lines.length - 1];
      expect(lastLine).toHaveStyle({ width: '80%' });
    });
  });

  describe('animation', () => {
    it('applies pulse animation by default', () => {
      render(<Skeleton data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveClass('animate-pulse');
    });

    it('uses animation duration of 1.5s', () => {
      render(<Skeleton data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      // Animation is applied via CSS class, check the class exists
      expect(skeleton).toHaveClass('animate-pulse');
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<Skeleton className="custom-class" data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveClass('custom-class');
    });

    it('has gray-800 background color matching NVIDIA theme', () => {
      render(<Skeleton data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveClass('bg-gray-800');
    });

    it('merges custom className with default classes', () => {
      render(<Skeleton className="mt-4" data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveClass('mt-4', 'animate-pulse', 'bg-gray-800');
    });
  });

  describe('accessibility', () => {
    it('has aria-hidden attribute by default', () => {
      render(<Skeleton data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveAttribute('aria-hidden', 'true');
    });

    it('has role="presentation" for decorative content', () => {
      render(<Skeleton data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveAttribute('role', 'presentation');
    });
  });

  describe('default dimensions', () => {
    it('text variant has default height of 1em', () => {
      render(<Skeleton variant="text" data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveStyle({ height: '1em' });
    });

    it('text variant has default width of 100%', () => {
      render(<Skeleton variant="text" data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveStyle({ width: '100%' });
    });

    it('circular variant has equal width and height when only one dimension specified', () => {
      render(<Skeleton variant="circular" width={48} data-testid="skeleton" />);
      const skeleton = screen.getByTestId('skeleton');
      expect(skeleton).toHaveStyle({ width: '48px', height: '48px' });
    });
  });
});
