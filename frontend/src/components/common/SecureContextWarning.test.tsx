/**
 * Tests for SecureContextWarning component
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import SecureContextWarning from './SecureContextWarning';

describe('SecureContextWarning', () => {
  // Store original window properties
  const originalIsSecureContext = Object.getOwnPropertyDescriptor(window, 'isSecureContext');

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Restore original window properties
    if (originalIsSecureContext) {
      Object.defineProperty(window, 'isSecureContext', originalIsSecureContext);
    } else {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
    }
  });

  describe('when in secure context', () => {
    beforeEach(() => {
      Object.defineProperty(window, 'isSecureContext', {
        value: true,
        writable: true,
        configurable: true,
      });
    });

    it('does not render when in secure context', () => {
      render(<SecureContextWarning />);

      expect(screen.queryByTestId('secure-context-warning')).not.toBeInTheDocument();
    });

    it('renders when forceShow is true even in secure context', () => {
      render(<SecureContextWarning forceShow />);

      expect(screen.getByTestId('secure-context-warning')).toBeInTheDocument();
    });
  });

  describe('when not in secure context', () => {
    beforeEach(() => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });
    });

    it('renders warning when not in secure context', () => {
      render(<SecureContextWarning />);

      expect(screen.getByTestId('secure-context-warning')).toBeInTheDocument();
    });

    it('displays insecure context message', () => {
      render(<SecureContextWarning />);

      expect(screen.getByText('Insecure Context Detected')).toBeInTheDocument();
    });

    it('displays recommendation for HTTPS', () => {
      render(<SecureContextWarning />);

      // Check that the recommendation text contains HTTPS
      const recommendation = screen.getByText(/Access the application via HTTPS/);
      expect(recommendation).toBeInTheDocument();
    });

    it('displays current protocol information', () => {
      render(<SecureContextWarning />);

      expect(screen.getByText('Current: HTTP')).toBeInTheDocument();
      expect(screen.getByText('Required: HTTPS or localhost')).toBeInTheDocument();
    });

    it('has correct role for accessibility', () => {
      render(<SecureContextWarning />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  describe('dismissible behavior', () => {
    beforeEach(() => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });
    });

    it('shows dismiss button by default', () => {
      render(<SecureContextWarning />);

      expect(screen.getByTestId('dismiss-warning-button')).toBeInTheDocument();
    });

    it('hides dismiss button when dismissible is false', () => {
      render(<SecureContextWarning dismissible={false} />);

      expect(screen.queryByTestId('dismiss-warning-button')).not.toBeInTheDocument();
    });

    it('hides warning when dismiss button is clicked', () => {
      render(<SecureContextWarning />);

      const dismissButton = screen.getByTestId('dismiss-warning-button');
      fireEvent.click(dismissButton);

      expect(screen.queryByTestId('secure-context-warning')).not.toBeInTheDocument();
    });

    it('calls onDismiss callback when dismissed', () => {
      const onDismiss = vi.fn();
      render(<SecureContextWarning onDismiss={onDismiss} />);

      const dismissButton = screen.getByTestId('dismiss-warning-button');
      fireEvent.click(dismissButton);

      expect(onDismiss).toHaveBeenCalledTimes(1);
    });

    it('dismiss button has accessible label', () => {
      render(<SecureContextWarning />);

      expect(screen.getByLabelText('Dismiss warning')).toBeInTheDocument();
    });
  });

  describe('custom styling', () => {
    beforeEach(() => {
      Object.defineProperty(window, 'isSecureContext', {
        value: false,
        writable: true,
        configurable: true,
      });
    });

    it('applies custom className', () => {
      render(<SecureContextWarning className="custom-class" />);

      expect(screen.getByTestId('secure-context-warning')).toHaveClass('custom-class');
    });
  });
});
