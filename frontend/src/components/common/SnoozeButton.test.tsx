/**
 * Tests for SnoozeButton component
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import SnoozeButton from './SnoozeButton';

describe('SnoozeButton', () => {
  const MOCK_NOW = new Date('2024-01-15T12:00:00Z');
  const mockOnSnooze = vi.fn();
  const mockOnUnsnooze = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(MOCK_NOW);
    mockOnSnooze.mockClear();
    mockOnUnsnooze.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders snooze button', () => {
    render(<SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} />);

    expect(screen.getByTestId('snooze-button')).toBeInTheDocument();
    expect(screen.getByText('Snooze')).toBeInTheDocument();
  });

  it('shows "Snoozed" when event is currently snoozed', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(
      <SnoozeButton
        snoozeUntil={futureTime}
        onSnooze={mockOnSnooze}
        onUnsnooze={mockOnUnsnooze}
      />
    );

    expect(screen.getByText('Snoozed')).toBeInTheDocument();
  });

  it('opens dropdown when clicked', () => {
    render(<SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} />);

    fireEvent.click(screen.getByTestId('snooze-button'));

    expect(screen.getByTestId('snooze-dropdown')).toBeInTheDocument();
  });

  it('shows snooze duration options in dropdown', () => {
    render(<SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} />);

    fireEvent.click(screen.getByTestId('snooze-button'));

    expect(screen.getByText('15 minutes')).toBeInTheDocument();
    expect(screen.getByText('1 hour')).toBeInTheDocument();
    expect(screen.getByText('4 hours')).toBeInTheDocument();
    expect(screen.getByText('24 hours')).toBeInTheDocument();
  });

  it('calls onSnooze with correct duration when option clicked', () => {
    render(<SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} />);

    fireEvent.click(screen.getByTestId('snooze-button'));
    fireEvent.click(screen.getByText('1 hour'));

    expect(mockOnSnooze).toHaveBeenCalledWith(60 * 60);
  });

  it('shows unsnooze option when event is snoozed', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(
      <SnoozeButton
        snoozeUntil={futureTime}
        onSnooze={mockOnSnooze}
        onUnsnooze={mockOnUnsnooze}
      />
    );

    fireEvent.click(screen.getByTestId('snooze-button'));

    expect(screen.getByTestId('unsnooze-option')).toBeInTheDocument();
    expect(screen.getByText('Unsnooze')).toBeInTheDocument();
  });

  it('calls onUnsnooze when unsnooze option clicked', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(
      <SnoozeButton
        snoozeUntil={futureTime}
        onSnooze={mockOnSnooze}
        onUnsnooze={mockOnUnsnooze}
      />
    );

    fireEvent.click(screen.getByTestId('snooze-button'));
    fireEvent.click(screen.getByTestId('unsnooze-option'));

    expect(mockOnUnsnooze).toHaveBeenCalled();
  });

  it('closes dropdown after selecting an option', () => {
    render(<SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} />);

    fireEvent.click(screen.getByTestId('snooze-button'));
    expect(screen.getByTestId('snooze-dropdown')).toBeInTheDocument();

    fireEvent.click(screen.getByText('15 minutes'));
    expect(screen.queryByTestId('snooze-dropdown')).not.toBeInTheDocument();
  });

  it('closes dropdown when clicking outside', () => {
    render(
      <div>
        <SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} />
        <div data-testid="outside">Outside</div>
      </div>
    );

    fireEvent.click(screen.getByTestId('snooze-button'));
    expect(screen.getByTestId('snooze-dropdown')).toBeInTheDocument();

    // Click outside
    fireEvent.mouseDown(screen.getByTestId('outside'));
    expect(screen.queryByTestId('snooze-dropdown')).not.toBeInTheDocument();
  });

  it('closes dropdown on Escape key', () => {
    render(<SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} />);

    fireEvent.click(screen.getByTestId('snooze-button'));
    expect(screen.getByTestId('snooze-dropdown')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByTestId('snooze-dropdown')).not.toBeInTheDocument();
  });

  it('disables button when disabled prop is true', () => {
    render(
      <SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} disabled={true} />
    );

    expect(screen.getByTestId('snooze-button')).toBeDisabled();
  });

  it('disables button when isLoading is true', () => {
    render(
      <SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} isLoading={true} />
    );

    expect(screen.getByTestId('snooze-button')).toBeDisabled();
  });

  it('applies correct size classes', () => {
    const { rerender } = render(
      <SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} size="sm" />
    );
    expect(screen.getByTestId('snooze-button')).toHaveClass('text-xs');

    rerender(
      <SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} size="md" />
    );
    expect(screen.getByTestId('snooze-button')).toHaveClass('text-sm');

    rerender(
      <SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} size="lg" />
    );
    expect(screen.getByTestId('snooze-button')).toHaveClass('text-base');
  });

  it('applies custom className', () => {
    render(
      <SnoozeButton
        onSnooze={mockOnSnooze}
        onUnsnooze={mockOnUnsnooze}
        className="custom-class"
      />
    );

    expect(screen.getByTestId('snooze-button').parentElement).toHaveClass('custom-class');
  });

  it('shows snooze status in dropdown when snoozed', () => {
    const futureTime = new Date(MOCK_NOW.getTime() + 60 * 60 * 1000).toISOString();
    render(
      <SnoozeButton
        snoozeUntil={futureTime}
        onSnooze={mockOnSnooze}
        onUnsnooze={mockOnUnsnooze}
      />
    );

    fireEvent.click(screen.getByTestId('snooze-button'));

    // Should show snooze status
    expect(screen.getByText(/snoozed until/i)).toBeInTheDocument();
  });

  it('has correct aria attributes', () => {
    render(<SnoozeButton onSnooze={mockOnSnooze} onUnsnooze={mockOnUnsnooze} />);

    const button = screen.getByTestId('snooze-button');
    expect(button).toHaveAttribute('aria-haspopup', 'menu');
    expect(button).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');

    const dropdown = screen.getByTestId('snooze-dropdown');
    expect(dropdown).toHaveAttribute('role', 'menu');
  });
});
