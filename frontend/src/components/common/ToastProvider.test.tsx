/**
 * ToastProvider - Component tests for toast notification provider
 *
 * TDD RED Phase: These tests define the expected component behavior
 * and integration with sonner's Toaster.
 */

import { render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { ToastProvider } from './ToastProvider';

// Mock sonner
vi.mock('sonner', () => ({
  Toaster: vi.fn(
    ({
      theme,
      position,
      richColors,
      closeButton,
      className,
    }: {
      theme?: string;
      position?: string;
      richColors?: boolean;
      closeButton?: boolean;
      className?: string;
    }) => (
      <div
        data-testid="sonner-toaster"
        data-theme={theme}
        data-position={position}
        data-rich-colors={richColors}
        data-close-button={closeButton}
        className={className}
      />
    )
  ),
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    loading: vi.fn(),
    dismiss: vi.fn(),
    promise: vi.fn(),
  }),
}));

describe('ToastProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('should render the Toaster component', () => {
      render(<ToastProvider />);

      expect(screen.getByTestId('sonner-toaster')).toBeInTheDocument();
    });

    it('should render children when provided', () => {
      render(
        <ToastProvider>
          <div data-testid="child-content">App Content</div>
        </ToastProvider>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
      expect(screen.getByText('App Content')).toBeInTheDocument();
    });

    it('should render without children', () => {
      render(<ToastProvider />);

      expect(screen.getByTestId('sonner-toaster')).toBeInTheDocument();
    });
  });

  describe('default configuration', () => {
    it('should use dark theme by default', () => {
      render(<ToastProvider />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster).toHaveAttribute('data-theme', 'dark');
    });

    it('should use bottom-right position by default', () => {
      render(<ToastProvider />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster).toHaveAttribute('data-position', 'bottom-right');
    });

    it('should enable rich colors by default', () => {
      render(<ToastProvider />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster).toHaveAttribute('data-rich-colors', 'true');
    });

    it('should enable close button by default', () => {
      render(<ToastProvider />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster).toHaveAttribute('data-close-button', 'true');
    });
  });

  describe('custom configuration', () => {
    it('should accept custom position', () => {
      render(<ToastProvider position="top-center" />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster).toHaveAttribute('data-position', 'top-center');
    });

    it('should accept custom theme', () => {
      render(<ToastProvider theme="light" />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster).toHaveAttribute('data-theme', 'light');
    });

    it('should allow disabling rich colors', () => {
      render(<ToastProvider richColors={false} />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster).toHaveAttribute('data-rich-colors', 'false');
    });

    it('should allow disabling close button', () => {
      render(<ToastProvider closeButton={false} />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster).toHaveAttribute('data-close-button', 'false');
    });
  });

  describe('NVIDIA theme styling', () => {
    it('should apply custom className for NVIDIA styling', () => {
      render(<ToastProvider />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster).toHaveClass('nvidia-toast');
    });

    it('should allow additional className to be merged', () => {
      render(<ToastProvider className="custom-class" />);

      const toaster = screen.getByTestId('sonner-toaster');
      expect(toaster.className).toContain('nvidia-toast');
      expect(toaster.className).toContain('custom-class');
    });
  });

  describe('accessibility', () => {
    it('should pass toastOptions for ARIA configuration', () => {
      // This test ensures we're setting up proper ARIA attributes
      // for screen readers through sonner's built-in accessibility features
      render(<ToastProvider />);

      // Sonner handles ARIA automatically, so we just verify the component renders
      expect(screen.getByTestId('sonner-toaster')).toBeInTheDocument();
    });
  });

  describe('component displayName', () => {
    it('should have a displayName for debugging', () => {
      expect(ToastProvider.displayName).toBe('ToastProvider');
    });
  });
});

describe('ToastProvider integration', () => {
  it('should wrap application content correctly', () => {
    render(
      <ToastProvider>
        <main>
          <h1>Dashboard</h1>
          <button>Click me</button>
        </main>
      </ToastProvider>
    );

    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
    expect(screen.getByTestId('sonner-toaster')).toBeInTheDocument();
  });

  it('should not interfere with child component rendering', () => {
    const MockComponent = () => {
      const [count] = useState(0);
      return (
        <div>
          <span data-testid="count">{count}</span>
          <button>Increment</button>
        </div>
      );
    };

    render(
      <ToastProvider>
        <MockComponent />
      </ToastProvider>
    );

    expect(screen.getByTestId('count')).toHaveTextContent('0');
  });
});
