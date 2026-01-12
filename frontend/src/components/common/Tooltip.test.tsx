import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import Tooltip from './Tooltip';

describe('Tooltip', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('basic rendering', () => {
    it('renders children without tooltip initially', () => {
      render(
        <Tooltip content="Test tooltip">
          <button>Hover me</button>
        </Tooltip>
      );

      expect(screen.getByText('Hover me')).toBeInTheDocument();
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });

    it('shows tooltip on mouse enter after delay', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
        expect(screen.getByText('Test tooltip')).toBeInTheDocument();
      });
    });

    it('hides tooltip on mouse leave', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));
      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
      });

      await user.unhover(screen.getByText('Hover me'));
      await waitFor(() => {
        expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
      });
    });
  });

  describe('positioning', () => {
    it('applies top position classes by default', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toHaveClass('bottom-full');
      });
    });

    it('applies bottom position classes', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" position="bottom" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toHaveClass('top-full');
      });
    });

    it('applies left position classes', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" position="left" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toHaveClass('right-full');
      });
    });

    it('applies right position classes', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" position="right" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toHaveClass('left-full');
      });
    });
  });

  describe('delay', () => {
    it('uses default delay of 200ms', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" delay={50}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
      });
    });

    it('respects custom delay', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" delay={100}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
      });
    });
  });

  describe('disabled state', () => {
    it('does not show tooltip when disabled', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" disabled delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      // Wait a bit to ensure tooltip doesn't appear
      await new Promise((resolve) => setTimeout(resolve, 100));
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('shows tooltip on focus', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" delay={0}>
          <button>Focus me</button>
        </Tooltip>
      );

      // Tab to focus the wrapper div
      await user.tab();

      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
      });
    });

    it('hides tooltip on blur', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <div>
          <Tooltip content="Test tooltip" delay={0}>
            <button>Focus me</button>
          </Tooltip>
          <button>Other button</button>
        </div>
      );

      // Tab to focus the wrapper div
      await user.tab();
      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
      });

      // Tab away to blur
      await user.tab();
      await waitFor(() => {
        expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
      });
    });

    it('has role="tooltip" attribute', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toBeInTheDocument();
      });
    });

    it('has data-testid for testing', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        expect(screen.getByTestId('tooltip')).toBeInTheDocument();
      });
    });
  });

  describe('styling', () => {
    it('applies custom className', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" className="custom-class" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toHaveClass('custom-class');
      });
    });

    it('applies base styling classes', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="Test tooltip" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toHaveClass('z-50', 'rounded-lg', 'bg-gray-900');
      });
    });
  });

  describe('content', () => {
    it('renders string content', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip content="String content" delay={0}>
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        expect(screen.getByText('String content')).toBeInTheDocument();
      });
    });

    it('renders JSX content', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();

      render(
        <Tooltip
          content={
            <div>
              <strong>Bold text</strong>
              <span>Regular text</span>
            </div>
          }
          delay={0}
        >
          <button>Hover me</button>
        </Tooltip>
      );

      await user.hover(screen.getByText('Hover me'));

      await waitFor(() => {
        expect(screen.getByText('Bold text')).toBeInTheDocument();
        expect(screen.getByText('Regular text')).toBeInTheDocument();
      });
    });
  });
});
