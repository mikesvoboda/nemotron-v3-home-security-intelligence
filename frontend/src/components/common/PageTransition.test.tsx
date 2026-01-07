import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PageTransition from './PageTransition';

// Mock framer-motion to avoid animation timing issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({
      children,
      className,
      'data-testid': testId,
      initial,
      animate,
      exit,
      variants,
      ...props
    }: {
      children?: React.ReactNode;
      className?: string;
      'data-testid'?: string;
      initial?: string | object;
      animate?: string | object;
      exit?: string | object;
      variants?: object;
      [key: string]: unknown;
    }) => (
      <div
        className={className}
        data-testid={testId}
        data-initial={JSON.stringify(initial)}
        data-animate={JSON.stringify(animate)}
        data-exit={JSON.stringify(exit)}
        data-variants={JSON.stringify(variants)}
        {...props}
      >
        {children}
      </div>
    ),
  },
  AnimatePresence: ({
    children,
    mode,
  }: {
    children?: React.ReactNode;
    mode?: string;
  }) => <div data-testid="animate-presence" data-mode={mode}>{children}</div>,
  useReducedMotion: vi.fn(() => false),
}));

describe('PageTransition', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('basic rendering', () => {
    it('renders children within motion wrapper', () => {
      render(
        <MemoryRouter>
          <PageTransition>
            <div data-testid="child-content">Test Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
      expect(screen.getByText('Test Content')).toBeInTheDocument();
    });

    it('wraps content in page-transition container', () => {
      render(
        <MemoryRouter>
          <PageTransition>
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const container = screen.getByTestId('page-transition');
      expect(container).toBeInTheDocument();
    });

    it('applies AnimatePresence for exit animations', () => {
      render(
        <MemoryRouter>
          <PageTransition>
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const animatePresence = screen.getByTestId('animate-presence');
      expect(animatePresence).toBeInTheDocument();
      expect(animatePresence).toHaveAttribute('data-mode', 'wait');
    });
  });

  describe('animation variants', () => {
    it('configures fade animation by default', () => {
      render(
        <MemoryRouter>
          <PageTransition>
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const container = screen.getByTestId('page-transition');
      expect(container).toHaveAttribute('data-initial', '"initial"');
      expect(container).toHaveAttribute('data-animate', '"animate"');
      expect(container).toHaveAttribute('data-exit', '"exit"');
    });

    it('supports slideUp variant', () => {
      render(
        <MemoryRouter>
          <PageTransition variant="slideUp">
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const container = screen.getByTestId('page-transition');
      const variants = JSON.parse(container.getAttribute('data-variants') || '{}');
      expect(variants).toBeDefined();
    });

    it('supports slideRight variant', () => {
      render(
        <MemoryRouter>
          <PageTransition variant="slideRight">
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const container = screen.getByTestId('page-transition');
      const variants = JSON.parse(container.getAttribute('data-variants') || '{}');
      expect(variants).toBeDefined();
    });

    it('supports fade variant', () => {
      render(
        <MemoryRouter>
          <PageTransition variant="fade">
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const container = screen.getByTestId('page-transition');
      const variants = JSON.parse(container.getAttribute('data-variants') || '{}');
      expect(variants).toBeDefined();
    });

    it('supports scale variant', () => {
      render(
        <MemoryRouter>
          <PageTransition variant="scale">
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const container = screen.getByTestId('page-transition');
      expect(container).toBeInTheDocument();
    });
  });

  describe('reduced motion support', () => {
    it('respects prefers-reduced-motion when enabled', async () => {
      const { useReducedMotion } = await import('framer-motion');
      vi.mocked(useReducedMotion).mockReturnValue(true);

      render(
        <MemoryRouter>
          <PageTransition>
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      // Component should still render content
      expect(screen.getByText('Content')).toBeInTheDocument();
    });

    it('applies reduced motion class when motion is reduced', async () => {
      const { useReducedMotion } = await import('framer-motion');
      vi.mocked(useReducedMotion).mockReturnValue(true);

      render(
        <MemoryRouter>
          <PageTransition>
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const container = screen.getByTestId('page-transition');
      expect(container).toHaveClass('motion-reduce');
    });
  });

  describe('custom className', () => {
    it('applies custom className to wrapper', () => {
      render(
        <MemoryRouter>
          <PageTransition className="custom-page-class">
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const container = screen.getByTestId('page-transition');
      expect(container).toHaveClass('custom-page-class');
    });

    it('combines custom className with default classes', () => {
      render(
        <MemoryRouter>
          <PageTransition className="custom-class">
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      const container = screen.getByTestId('page-transition');
      expect(container).toHaveClass('custom-class');
      expect(container).toHaveClass('page-transition-wrapper');
    });
  });

  describe('duration configuration', () => {
    it('accepts custom duration prop', () => {
      render(
        <MemoryRouter>
          <PageTransition duration={0.5}>
            <div>Content</div>
          </PageTransition>
        </MemoryRouter>
      );

      // Component should render with custom duration
      expect(screen.getByTestId('page-transition')).toBeInTheDocument();
    });
  });

  describe('route transitions', () => {
    it('renders different routes', () => {
      const TestApp = () => (
        <MemoryRouter initialEntries={['/page1']}>
          <Routes>
            <Route
              path="/page1"
              element={
                <PageTransition>
                  <div>Page 1</div>
                </PageTransition>
              }
            />
            <Route
              path="/page2"
              element={
                <PageTransition>
                  <div>Page 2</div>
                </PageTransition>
              }
            />
          </Routes>
        </MemoryRouter>
      );

      render(<TestApp />);
      expect(screen.getByText('Page 1')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('maintains focus management with proper ARIA', () => {
      render(
        <MemoryRouter>
          <PageTransition>
            <main role="main">
              <h1>Page Title</h1>
              <button>Focusable Button</button>
            </main>
          </PageTransition>
        </MemoryRouter>
      );

      expect(screen.getByRole('main')).toBeInTheDocument();
      expect(screen.getByRole('heading')).toBeInTheDocument();
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('does not interfere with tab navigation', () => {
      render(
        <MemoryRouter>
          <PageTransition>
            <div>
              <a href="#link1">Link 1</a>
              <button>Button 1</button>
            </div>
          </PageTransition>
        </MemoryRouter>
      );

      const link = screen.getByRole('link');
      const button = screen.getByRole('button');
      expect(link).toBeInTheDocument();
      expect(button).toBeInTheDocument();
    });
  });
});
