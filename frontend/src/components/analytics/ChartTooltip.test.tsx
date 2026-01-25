/**
 * Tests for ChartTooltip component
 *
 * @see NEM-3524
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ChartTooltip, { TooltipContent } from './ChartTooltip';

describe('ChartTooltip', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('basic rendering', () => {
    it('renders children without tooltip initially', () => {
      render(
        <ChartTooltip content="Test tooltip">
          <button>Hover me</button>
        </ChartTooltip>
      );

      expect(screen.getByRole('button', { name: 'Hover me' })).toBeInTheDocument();
      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });

    it('shows tooltip on mouse enter after delay', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(
        <ChartTooltip content="Test tooltip content" delay={100}>
          <button>Hover me</button>
        </ChartTooltip>
      );

      const button = screen.getByRole('button', { name: 'Hover me' });
      await user.hover(button);

      // Advance past the delay
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
        expect(screen.getByText('Test tooltip content')).toBeInTheDocument();
      });
    });

    it('hides tooltip on mouse leave', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(
        <ChartTooltip content="Test tooltip content" delay={100}>
          <button>Hover me</button>
        </ChartTooltip>
      );

      const button = screen.getByRole('button', { name: 'Hover me' });
      await user.hover(button);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
      });

      await user.unhover(button);

      await waitFor(() => {
        expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
      });
    });

    it('does not show tooltip when disabled', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(
        <ChartTooltip content="Test tooltip content" disabled delay={0}>
          <button>Hover me</button>
        </ChartTooltip>
      );

      const button = screen.getByRole('button', { name: 'Hover me' });
      await user.hover(button);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(50);
      });

      expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    });
  });

  describe('tooltip has correct testid', () => {
    it('tooltip has data-testid attribute', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(
        <ChartTooltip content="Test content" delay={0}>
          <button>Hover me</button>
        </ChartTooltip>
      );

      const button = screen.getByRole('button', { name: 'Hover me' });
      await user.hover(button);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      await waitFor(() => {
        expect(screen.getByTestId('chart-tooltip')).toBeInTheDocument();
      });
    });
  });

  describe('custom styling', () => {
    it('applies custom className to tooltip', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(
        <ChartTooltip content="Test content" className="custom-class" delay={0}>
          <button>Hover me</button>
        </ChartTooltip>
      );

      const button = screen.getByRole('button', { name: 'Hover me' });
      await user.hover(button);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toHaveClass('custom-class');
      });
    });
  });

  describe('complex content', () => {
    it('renders React node content', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(
        <ChartTooltip
          content={
            <div>
              <span data-testid="title">Title</span>
              <span data-testid="value">42</span>
            </div>
          }
          delay={0}
        >
          <button>Hover me</button>
        </ChartTooltip>
      );

      const button = screen.getByRole('button', { name: 'Hover me' });
      await user.hover(button);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      await waitFor(() => {
        expect(screen.getByTestId('title')).toBeInTheDocument();
        expect(screen.getByTestId('value')).toHaveTextContent('42');
      });
    });
  });
});

describe('TooltipContent', () => {
  it('renders title when provided', () => {
    render(<TooltipContent title="Test Title" />);
    expect(screen.getByText('Test Title')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(<TooltipContent title="Title" subtitle="Subtitle text" />);
    expect(screen.getByText('Subtitle text')).toBeInTheDocument();
  });

  it('renders items with labels and values', () => {
    render(
      <TooltipContent
        items={[
          { label: 'Average', value: '5.2' },
          { label: 'Count', value: 30 },
        ]}
      />
    );

    expect(screen.getByText('Average')).toBeInTheDocument();
    expect(screen.getByText('5.2')).toBeInTheDocument();
    expect(screen.getByText('Count')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
  });

  it('renders color indicators for items', () => {
    const { container } = render(
      <TooltipContent
        items={[{ label: 'Person', value: 10, color: '#76B900' }]}
      />
    );

    const colorIndicator = container.querySelector('[style*="background-color"]');
    expect(colorIndicator).toBeInTheDocument();
    expect(colorIndicator).toHaveStyle({ backgroundColor: '#76B900' });
  });

  it('renders footer when provided', () => {
    render(<TooltipContent footer="Peak activity hour" />);
    expect(screen.getByText('Peak activity hour')).toBeInTheDocument();
  });

  it('renders all elements together', () => {
    render(
      <TooltipContent
        title="Monday 8:00 AM"
        subtitle="Activity Data"
        items={[
          { label: 'Average', value: '5.2', color: '#76B900' },
          { label: 'Samples', value: 30 },
        ]}
        footer="Peak activity hour"
      />
    );

    expect(screen.getByText('Monday 8:00 AM')).toBeInTheDocument();
    expect(screen.getByText('Activity Data')).toBeInTheDocument();
    expect(screen.getByText('Average')).toBeInTheDocument();
    expect(screen.getByText('5.2')).toBeInTheDocument();
    expect(screen.getByText('Samples')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
    expect(screen.getByText('Peak activity hour')).toBeInTheDocument();
  });
});
