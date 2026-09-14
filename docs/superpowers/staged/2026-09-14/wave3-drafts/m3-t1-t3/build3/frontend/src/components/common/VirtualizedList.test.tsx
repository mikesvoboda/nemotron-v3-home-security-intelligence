/**
 * Tests for VirtualizedList component.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { VirtualizedList } from './VirtualizedList';

// ============================================================================
// Test Utilities
// ============================================================================

interface TestItem {
  id: string;
  name: string;
}

const mockItems: TestItem[] = Array.from({ length: 100 }, (_, i) => ({
  id: `item-${i}`,
  name: `Item ${i}`,
}));

// Mock window dimensions for virtualization
const originalOffsetHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
const originalOffsetWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');

beforeEach(() => {
  // Mock element dimensions
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
    configurable: true,
    value: 600,
  });
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
    configurable: true,
    value: 800,
  });
  // Mock getBoundingClientRect
  Element.prototype.getBoundingClientRect = vi.fn(() => ({
    width: 800,
    height: 100,
    top: 0,
    left: 0,
    bottom: 100,
    right: 800,
    x: 0,
    y: 0,
    toJSON: () => {},
  }));
});

afterEach(() => {
  if (originalOffsetHeight) {
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', originalOffsetHeight);
  }
  if (originalOffsetWidth) {
    Object.defineProperty(HTMLElement.prototype, 'offsetWidth', originalOffsetWidth);
  }
  vi.restoreAllMocks();
});

// ============================================================================
// Tests
// ============================================================================

describe('VirtualizedList', () => {
  describe('rendering', () => {
    it('renders items', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div data-testid={item.id}>{item.name}</div>}
          estimateSize={100}
          height={600}
        />
      );

      // Should render some items (first few + overscan)
      expect(screen.getByText('Item 0')).toBeInTheDocument();
    });

    it('renders with custom test id', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          estimateSize={100}
          height={600}
          testId="my-list"
        />
      );

      expect(screen.getByTestId('my-list')).toBeInTheDocument();
    });

    it('renders empty state when items array is empty', () => {
      render(
        <VirtualizedList
          items={[]}
          renderItem={(item: TestItem) => <div>{item.name}</div>}
          emptyState={<div data-testid="empty">No items found</div>}
          height={600}
        />
      );

      expect(screen.getByTestId('empty')).toBeInTheDocument();
      expect(screen.getByText('No items found')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          className="custom-class"
          testId="list"
          height={600}
        />
      );

      expect(screen.getByTestId('list')).toHaveClass('custom-class');
    });

    it('applies aria-label', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          ariaLabel="Test list"
          testId="list"
          height={600}
        />
      );

      expect(screen.getByTestId('list')).toHaveAttribute('aria-label', 'Test list');
    });
  });

  describe('virtualization', () => {
    it('does not render all items', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div data-testid={item.id}>{item.name}</div>}
          estimateSize={100}
          height={600}
          overscan={2}
        />
      );

      // With 600px height, 100px items, should render ~6 visible + 2 overscan each side
      // Should NOT render items far down the list
      expect(screen.queryByTestId('item-90')).not.toBeInTheDocument();
    });

    it('uses custom getItemKey function', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          getItemKey={(item) => item.id}
          height={600}
        />
      );

      // Should render without errors
      expect(screen.getByText('Item 0')).toBeInTheDocument();
    });
  });

  describe('scroll handling', () => {
    it('calls onScroll when scrolling', () => {
      const onScroll = vi.fn();

      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          onScroll={onScroll}
          testId="list"
          height={600}
        />
      );

      const list = screen.getByTestId('list');
      fireEvent.scroll(list, { target: { scrollTop: 200 } });

      expect(onScroll).toHaveBeenCalledWith(200);
    });

    it('calls onEndReached when near end', async () => {
      const onEndReached = vi.fn();

      // Create a smaller list so we can reach the end
      const smallItems = mockItems.slice(0, 10);

      render(
        <VirtualizedList
          items={smallItems}
          renderItem={(item) => <div style={{ height: '100px' }}>{item.name}</div>}
          estimateSize={100}
          onEndReached={onEndReached}
          endReachedThreshold={200}
          testId="list"
          height={600}
        />
      );

      const list = screen.getByTestId('list');
      // Mock the scroll properties
      Object.defineProperty(list, 'scrollHeight', { value: 1000, configurable: true });
      Object.defineProperty(list, 'clientHeight', { value: 600, configurable: true });
      Object.defineProperty(list, 'scrollTop', { value: 300, configurable: true });

      fireEvent.scroll(list);

      await waitFor(() => {
        expect(onEndReached).toHaveBeenCalled();
      });
    });

    it('does not call onEndReached when isLoadingMore is true', () => {
      const onEndReached = vi.fn();
      const smallItems = mockItems.slice(0, 10);

      render(
        <VirtualizedList
          items={smallItems}
          renderItem={(item) => <div style={{ height: '100px' }}>{item.name}</div>}
          estimateSize={100}
          onEndReached={onEndReached}
          isLoadingMore={true}
          endReachedThreshold={200}
          testId="list"
          height={600}
        />
      );

      const list = screen.getByTestId('list');
      Object.defineProperty(list, 'scrollHeight', { value: 1000, configurable: true });
      Object.defineProperty(list, 'clientHeight', { value: 600, configurable: true });
      Object.defineProperty(list, 'scrollTop', { value: 300, configurable: true });

      fireEvent.scroll(list);

      // Should not be called because isLoadingMore is true
      expect(onEndReached).not.toHaveBeenCalled();
    });
  });

  describe('loading and footer', () => {
    it('renders loading indicator when isLoadingMore', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          isLoadingMore={true}
          loadingIndicator={<div data-testid="loading">Loading...</div>}
          height={600}
        />
      );

      expect(screen.getByTestId('loading')).toBeInTheDocument();
    });

    it('renders footer when not loading', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          isLoadingMore={false}
          footer={<div data-testid="footer">End of list</div>}
          height={600}
        />
      );

      expect(screen.getByTestId('footer')).toBeInTheDocument();
    });

    it('does not render footer when loading more', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          isLoadingMore={true}
          footer={<div data-testid="footer">End of list</div>}
          height={600}
        />
      );

      expect(screen.queryByTestId('footer')).not.toBeInTheDocument();
    });

    it('does not render footer when no items', () => {
      render(
        <VirtualizedList
          items={[]}
          renderItem={(item: TestItem) => <div>{item.name}</div>}
          footer={<div data-testid="footer">End of list</div>}
          height={600}
        />
      );

      expect(screen.queryByTestId('footer')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has role="list" on container', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          testId="list"
          height={600}
        />
      );

      expect(screen.getByTestId('list')).toHaveAttribute('role', 'list');
    });

    it('has role="listitem" on each item', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          height={600}
        />
      );

      const listItems = screen.getAllByRole('listitem');
      expect(listItems.length).toBeGreaterThan(0);
    });
  });

  describe('height configuration', () => {
    it('accepts number height (pixels)', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          height={500}
          testId="list"
        />
      );

      const list = screen.getByTestId('list');
      expect(list).toHaveStyle({ height: '500px' });
    });

    it('accepts string height (CSS value)', () => {
      render(
        <VirtualizedList
          items={mockItems}
          renderItem={(item) => <div>{item.name}</div>}
          height="50vh"
          testId="list"
        />
      );

      const list = screen.getByTestId('list');
      expect(list).toHaveStyle({ height: '50vh' });
    });
  });
});
