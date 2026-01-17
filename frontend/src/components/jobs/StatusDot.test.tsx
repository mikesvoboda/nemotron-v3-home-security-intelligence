/**
 * Tests for StatusDot component (NEM-2713)
 *
 * StatusDot displays a colored dot indicating job status
 * following the timeline styling specification.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import StatusDot from './StatusDot';

describe('StatusDot', () => {
  describe('rendering', () => {
    it('renders a dot element', () => {
      render(<StatusDot status="pending" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<StatusDot status="pending" className="custom-class" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('custom-class');
    });
  });

  describe('status colors', () => {
    it('renders gray dot for pending status', () => {
      render(<StatusDot status="pending" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('bg-gray-400');
    });

    it('renders gray dot for queued status', () => {
      render(<StatusDot status="queued" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('bg-gray-400');
    });

    it('renders blue dot for processing status', () => {
      render(<StatusDot status="processing" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('bg-blue-500');
    });

    it('renders blue dot for running status', () => {
      render(<StatusDot status="running" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('bg-blue-500');
    });

    it('renders green dot for completed status', () => {
      render(<StatusDot status="completed" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('bg-green-500');
    });

    it('renders red dot for failed status', () => {
      render(<StatusDot status="failed" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('bg-red-500');
    });

    it('renders yellow dot for cancelled status', () => {
      render(<StatusDot status="cancelled" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('bg-yellow-500');
    });

    it('renders gray dot for unknown status', () => {
      render(<StatusDot status="unknown-status" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('bg-gray-400');
    });
  });

  describe('dot style', () => {
    it('renders filled dot for final states (completed)', () => {
      render(<StatusDot status="completed" />);
      const dot = screen.getByTestId('status-dot');
      // Filled dot should not have ring styling
      expect(dot).not.toHaveClass('ring-2');
    });

    it('renders filled dot for final states (failed)', () => {
      render(<StatusDot status="failed" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).not.toHaveClass('ring-2');
    });

    it('renders filled dot for final states (cancelled)', () => {
      render(<StatusDot status="cancelled" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).not.toHaveClass('ring-2');
    });

    it('renders outline dot for pending states', () => {
      render(<StatusDot status="pending" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('ring-2');
    });

    it('renders pulsing dot for processing states', () => {
      render(<StatusDot status="processing" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('animate-pulse');
    });
  });

  describe('sizes', () => {
    it('renders small dot by default', () => {
      render(<StatusDot status="pending" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('h-3');
      expect(dot).toHaveClass('w-3');
    });

    it('renders large dot when size is lg', () => {
      render(<StatusDot status="pending" size="lg" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveClass('h-4');
      expect(dot).toHaveClass('w-4');
    });
  });

  describe('accessibility', () => {
    it('has aria-label describing the status', () => {
      render(<StatusDot status="completed" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveAttribute('aria-label', 'Status: completed');
    });

    it('has role of img for screen readers', () => {
      render(<StatusDot status="pending" />);
      const dot = screen.getByTestId('status-dot');
      expect(dot).toHaveAttribute('role', 'img');
    });
  });
});
