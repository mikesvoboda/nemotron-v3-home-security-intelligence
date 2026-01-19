import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import ChartLegend from './ChartLegend';

const mockItems = [
  { name: 'Person', value: 150, color: '#10b981' },
  { name: 'Vehicle', value: 89, color: '#3b82f6' },
  { name: 'Animal', value: 45, color: '#f59e0b' },
  { name: 'Package', value: 23, color: '#8b5cf6' },
  { name: 'Other', value: 12, color: '#f43f5e' },
];

describe('ChartLegend', () => {
  describe('basic rendering', () => {
    it('renders all legend items', () => {
      render(<ChartLegend items={mockItems} />);

      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Animal')).toBeInTheDocument();
      expect(screen.getByText('Package')).toBeInTheDocument();
      expect(screen.getByText('Other')).toBeInTheDocument();
    });

    it('renders color dots for each item', () => {
      render(<ChartLegend items={mockItems} />);

      const colorDots = screen.getAllByTestId('legend-color-dot');
      expect(colorDots).toHaveLength(5);
    });

    it('renders with horizontal orientation by default', () => {
      render(<ChartLegend items={mockItems} />);

      const container = screen.getByTestId('chart-legend');
      expect(container).toHaveClass('flex-wrap');
    });

    it('renders with vertical orientation when specified', () => {
      render(<ChartLegend items={mockItems} orientation="vertical" />);

      const container = screen.getByTestId('chart-legend');
      expect(container).toHaveClass('flex-col');
    });
  });

  describe('collapsible behavior', () => {
    it('collapses items beyond maxVisibleItems', () => {
      render(<ChartLegend items={mockItems} maxVisibleItems={3} />);

      // Should show first 3 items
      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Animal')).toBeInTheDocument();

      // Should show "+2 more" button
      expect(screen.getByText('+2 more')).toBeInTheDocument();

      // Should not show the hidden items initially
      expect(screen.queryByText('Package')).not.toBeInTheDocument();
      expect(screen.queryByText('Other')).not.toBeInTheDocument();
    });

    it('expands to show all items when "+N more" is clicked', async () => {
      const user = userEvent.setup();
      render(<ChartLegend items={mockItems} maxVisibleItems={3} />);

      // Click expand button
      await user.click(screen.getByText('+2 more'));

      // Now all items should be visible
      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Animal')).toBeInTheDocument();
      expect(screen.getByText('Package')).toBeInTheDocument();
      expect(screen.getByText('Other')).toBeInTheDocument();

      // Should show "Show less" button
      expect(screen.getByText('Show less')).toBeInTheDocument();
    });

    it('collapses items when "Show less" is clicked', async () => {
      const user = userEvent.setup();
      render(<ChartLegend items={mockItems} maxVisibleItems={3} />);

      // Expand first
      await user.click(screen.getByText('+2 more'));
      expect(screen.getByText('Package')).toBeInTheDocument();

      // Collapse
      await user.click(screen.getByText('Show less'));

      // Hidden items should be gone again
      expect(screen.queryByText('Package')).not.toBeInTheDocument();
      expect(screen.getByText('+2 more')).toBeInTheDocument();
    });

    it('does not show expand button when items <= maxVisibleItems', () => {
      render(<ChartLegend items={mockItems.slice(0, 3)} maxVisibleItems={3} />);

      expect(screen.queryByText(/\+\d+ more/)).not.toBeInTheDocument();
    });
  });

  describe('item click handling', () => {
    it('calls onItemClick when an item is clicked', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();

      render(<ChartLegend items={mockItems} onItemClick={handleClick} />);

      await user.click(screen.getByText('Person'));

      expect(handleClick).toHaveBeenCalledWith(mockItems[0]);
    });

    it('passes the correct item to onItemClick', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();

      render(<ChartLegend items={mockItems} onItemClick={handleClick} />);

      await user.click(screen.getByText('Vehicle'));

      expect(handleClick).toHaveBeenCalledWith(mockItems[1]);
    });

    it('items are not clickable when onItemClick is not provided', () => {
      render(<ChartLegend items={mockItems} />);

      const items = screen.getAllByTestId('legend-item');
      // Items should not have button role when not clickable
      items.forEach((item) => {
        expect(item.tagName).not.toBe('BUTTON');
      });
    });
  });

  describe('touch target accessibility', () => {
    it('legend items have 44px minimum touch target', () => {
      render(<ChartLegend items={mockItems} />);

      const items = screen.getAllByTestId('legend-item');
      items.forEach((item) => {
        expect(item).toHaveClass('min-h-11'); // min-h-11 = 44px
      });
    });

    it('expand/collapse button has 44px minimum touch target', () => {
      render(<ChartLegend items={mockItems} maxVisibleItems={3} />);

      // Get the button element (parent of the text)
      const expandButton = screen.getByRole('button', { name: /show 2 more items/i });
      expect(expandButton).toHaveClass('min-h-11');
    });
  });

  describe('label truncation', () => {
    it('truncates long labels with max width', () => {
      const itemsWithLongNames = [
        { name: 'This is a very long label name', value: 100, color: '#10b981' },
      ];

      render(<ChartLegend items={itemsWithLongNames} />);

      const label = screen.getByText('This is a very long label name');
      expect(label).toHaveClass('truncate');
      expect(label).toHaveClass('max-w-[100px]');
    });

    it('uses smaller max width on compact mode', () => {
      const itemsWithLongNames = [
        { name: 'This is a very long label name', value: 100, color: '#10b981' },
      ];

      render(<ChartLegend items={itemsWithLongNames} compact />);

      const label = screen.getByText('This is a very long label name');
      expect(label).toHaveClass('max-w-[60px]');
    });
  });

  describe('auto orientation', () => {
    it('uses horizontal by default with auto orientation', () => {
      render(<ChartLegend items={mockItems} orientation="auto" />);

      const container = screen.getByTestId('chart-legend');
      // On desktop (default), should be horizontal
      expect(container).toHaveClass('flex-wrap');
    });
  });

  describe('empty state', () => {
    it('renders nothing when items array is empty', () => {
      const { container } = render(<ChartLegend items={[]} />);

      expect(container.firstChild).toBeNull();
    });
  });

  describe('custom styling', () => {
    it('applies custom className', () => {
      render(<ChartLegend items={mockItems} className="custom-class" />);

      const container = screen.getByTestId('chart-legend');
      expect(container).toHaveClass('custom-class');
    });
  });

  describe('keyboard accessibility', () => {
    it('items are focusable when clickable', () => {
      const handleClick = vi.fn();
      render(<ChartLegend items={mockItems} onItemClick={handleClick} />);

      const items = screen.getAllByTestId('legend-item');
      items.forEach((item) => {
        expect(item.tagName).toBe('BUTTON');
      });
    });

    it('handles keyboard activation', () => {
      const handleClick = vi.fn();
      render(<ChartLegend items={mockItems} onItemClick={handleClick} />);

      const firstItem = screen.getAllByTestId('legend-item')[0];
      firstItem.focus();

      fireEvent.keyDown(firstItem, { key: 'Enter' });
      expect(handleClick).toHaveBeenCalledWith(mockItems[0]);
    });
  });

  describe('value formatting', () => {
    it('displays value when showValue is true', () => {
      render(<ChartLegend items={mockItems} showValue />);

      expect(screen.getByText('150')).toBeInTheDocument();
      expect(screen.getByText('89')).toBeInTheDocument();
    });

    it('uses custom valueFormatter when provided', () => {
      render(
        <ChartLegend
          items={mockItems}
          showValue
          valueFormatter={(value) => `${value}%`}
        />
      );

      expect(screen.getByText('150%')).toBeInTheDocument();
      expect(screen.getByText('89%')).toBeInTheDocument();
    });

    it('hides value when showValue is false', () => {
      render(<ChartLegend items={mockItems} showValue={false} />);

      expect(screen.queryByText('150')).not.toBeInTheDocument();
      expect(screen.queryByText('89')).not.toBeInTheDocument();
    });
  });
});
