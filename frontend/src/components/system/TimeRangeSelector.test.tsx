import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import TimeRangeSelector from './TimeRangeSelector';

describe('TimeRangeSelector', () => {
  describe('rendering', () => {
    it('renders all three time range options', () => {
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="5m" onRangeChange={onRangeChange} />);

      // Use exact text matching to avoid regex overlap (5m vs 15m)
      expect(screen.getByRole('button', { name: '5m' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '15m' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '60m' })).toBeInTheDocument();
    });

    it('renders the component with data-testid', () => {
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="5m" onRangeChange={onRangeChange} />);

      expect(screen.getByTestId('time-range-selector')).toBeInTheDocument();
    });

    it('highlights the selected range (5m)', () => {
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="5m" onRangeChange={onRangeChange} />);

      const button5m = screen.getByRole('button', { name: '5m' });
      expect(button5m).toHaveAttribute('aria-pressed', 'true');
    });

    it('highlights the selected range (15m)', () => {
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="15m" onRangeChange={onRangeChange} />);

      const button15m = screen.getByRole('button', { name: '15m' });
      expect(button15m).toHaveAttribute('aria-pressed', 'true');
    });

    it('highlights the selected range (60m)', () => {
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="60m" onRangeChange={onRangeChange} />);

      const button60m = screen.getByRole('button', { name: '60m' });
      expect(button60m).toHaveAttribute('aria-pressed', 'true');
    });

    it('non-selected ranges are not pressed', () => {
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="5m" onRangeChange={onRangeChange} />);

      const button15m = screen.getByRole('button', { name: '15m' });
      const button60m = screen.getByRole('button', { name: '60m' });

      expect(button15m).toHaveAttribute('aria-pressed', 'false');
      expect(button60m).toHaveAttribute('aria-pressed', 'false');
    });
  });

  describe('interactions', () => {
    it('calls onRangeChange when 15m button is clicked', async () => {
      const user = userEvent.setup();
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="5m" onRangeChange={onRangeChange} />);

      const button15m = screen.getByRole('button', { name: '15m' });
      await user.click(button15m);

      expect(onRangeChange).toHaveBeenCalledTimes(1);
      expect(onRangeChange).toHaveBeenCalledWith('15m');
    });

    it('calls onRangeChange when 60m button is clicked', async () => {
      const user = userEvent.setup();
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="5m" onRangeChange={onRangeChange} />);

      const button60m = screen.getByRole('button', { name: '60m' });
      await user.click(button60m);

      expect(onRangeChange).toHaveBeenCalledTimes(1);
      expect(onRangeChange).toHaveBeenCalledWith('60m');
    });

    it('calls onRangeChange when 5m button is clicked', async () => {
      const user = userEvent.setup();
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="60m" onRangeChange={onRangeChange} />);

      const button5m = screen.getByRole('button', { name: '5m' });
      await user.click(button5m);

      expect(onRangeChange).toHaveBeenCalledTimes(1);
      expect(onRangeChange).toHaveBeenCalledWith('5m');
    });

    it('calls onRangeChange when clicking the already selected range', async () => {
      const user = userEvent.setup();
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="5m" onRangeChange={onRangeChange} />);

      const button5m = screen.getByRole('button', { name: '5m' });
      await user.click(button5m);

      // Should still call the callback even if already selected
      expect(onRangeChange).toHaveBeenCalledTimes(1);
      expect(onRangeChange).toHaveBeenCalledWith('5m');
    });
  });

  describe('accessibility', () => {
    it('buttons have appropriate aria-pressed attributes', () => {
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="15m" onRangeChange={onRangeChange} />);

      const button5m = screen.getByRole('button', { name: '5m' });
      const button15m = screen.getByRole('button', { name: '15m' });
      const button60m = screen.getByRole('button', { name: '60m' });

      expect(button5m).toHaveAttribute('aria-pressed', 'false');
      expect(button15m).toHaveAttribute('aria-pressed', 'true');
      expect(button60m).toHaveAttribute('aria-pressed', 'false');
    });

    it('has a role of group for the button container', () => {
      const onRangeChange = vi.fn();
      render(<TimeRangeSelector selectedRange="5m" onRangeChange={onRangeChange} />);

      expect(screen.getByRole('group')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className when provided', () => {
      const onRangeChange = vi.fn();
      render(
        <TimeRangeSelector
          selectedRange="5m"
          onRangeChange={onRangeChange}
          className="custom-class"
        />
      );

      const selector = screen.getByTestId('time-range-selector');
      expect(selector).toHaveClass('custom-class');
    });
  });
});
