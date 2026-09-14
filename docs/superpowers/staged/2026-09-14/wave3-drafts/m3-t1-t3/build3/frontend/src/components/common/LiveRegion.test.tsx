/**
 * Tests for LiveRegion component.
 *
 * This test suite covers the LiveRegion component which provides
 * ARIA live regions for screen reader announcements of dynamic content.
 */
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { LiveRegion } from './LiveRegion';

describe('LiveRegion', () => {
  describe('rendering', () => {
    it('renders with default props', () => {
      render(<LiveRegion message="Test message" />);
      const region = screen.getByRole('status');
      expect(region).toBeInTheDocument();
    });

    it('renders the message text', () => {
      render(<LiveRegion message="Important announcement" />);
      expect(screen.getByText('Important announcement')).toBeInTheDocument();
    });

    it('renders empty string when message is empty', () => {
      render(<LiveRegion message="" />);
      const region = screen.getByRole('status');
      expect(region).toBeInTheDocument();
      expect(region).toHaveTextContent('');
    });
  });

  describe('ARIA attributes', () => {
    it('has role="status"', () => {
      render(<LiveRegion message="Test" />);
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has aria-live="polite" by default', () => {
      render(<LiveRegion message="Test" />);
      const region = screen.getByRole('status');
      expect(region).toHaveAttribute('aria-live', 'polite');
    });

    it('has aria-live="assertive" when politeness is assertive', () => {
      render(<LiveRegion message="Test" politeness="assertive" />);
      const region = screen.getByRole('status');
      expect(region).toHaveAttribute('aria-live', 'assertive');
    });

    it('has aria-atomic="true"', () => {
      render(<LiveRegion message="Test" />);
      const region = screen.getByRole('status');
      expect(region).toHaveAttribute('aria-atomic', 'true');
    });
  });

  describe('visual hiding (sr-only)', () => {
    it('is visually hidden with sr-only class', () => {
      render(<LiveRegion message="Test" />);
      const region = screen.getByRole('status');
      expect(region).toHaveClass('sr-only');
    });

    it('remains accessible to screen readers despite being visually hidden', () => {
      render(<LiveRegion message="Accessible content" />);
      // The element should be in the document and findable by role
      const region = screen.getByRole('status');
      expect(region).toBeInTheDocument();
      expect(region).toHaveTextContent('Accessible content');
    });
  });

  describe('politeness levels', () => {
    it.each([
      ['polite', 'polite'],
      ['assertive', 'assertive'],
    ] as const)('applies %s politeness level correctly', (politeness, expectedValue) => {
      render(<LiveRegion message="Test" politeness={politeness} />);
      const region = screen.getByRole('status');
      expect(region).toHaveAttribute('aria-live', expectedValue);
    });
  });

  describe('message updates', () => {
    it('updates displayed message when prop changes', () => {
      const { rerender } = render(<LiveRegion message="First message" />);
      expect(screen.getByText('First message')).toBeInTheDocument();

      rerender(<LiveRegion message="Second message" />);
      expect(screen.getByText('Second message')).toBeInTheDocument();
      expect(screen.queryByText('First message')).not.toBeInTheDocument();
    });

    it('handles special characters in message', () => {
      const specialMessage = '<script>alert("xss")</script> & "quotes"';
      render(<LiveRegion message={specialMessage} />);
      expect(screen.getByText(specialMessage)).toBeInTheDocument();
    });

    it('handles unicode characters in message', () => {
      const unicodeMessage = 'Success! Operation complete';
      render(<LiveRegion message={unicodeMessage} />);
      expect(screen.getByText(unicodeMessage)).toBeInTheDocument();
    });
  });
});
