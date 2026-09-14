import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AnimatedList from './AnimatedList';

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
      custom,
      ...props
    }: {
      children?: React.ReactNode;
      className?: string;
      'data-testid'?: string;
      initial?: string | object;
      animate?: string | object;
      exit?: string | object;
      variants?: object;
      custom?: number;
      [key: string]: unknown;
    }) => (
      <div
        className={className}
        data-testid={testId}
        data-initial={JSON.stringify(initial)}
        data-animate={JSON.stringify(animate)}
        data-exit={JSON.stringify(exit)}
        data-variants={JSON.stringify(variants)}
        data-custom={custom}
        {...props}
      >
        {children}
      </div>
    ),
    ul: ({
      children,
      className,
      'data-testid': testId,
      variants,
      initial,
      animate,
      ...props
    }: {
      children?: React.ReactNode;
      className?: string;
      'data-testid'?: string;
      variants?: object;
      initial?: string;
      animate?: string;
      [key: string]: unknown;
    }) => (
      <ul
        className={className}
        data-testid={testId}
        data-variants={JSON.stringify(variants)}
        data-initial={initial}
        data-animate={animate}
        {...props}
      >
        {children}
      </ul>
    ),
    li: ({
      children,
      className,
      'data-testid': testId,
      variants,
      custom,
      ...props
    }: {
      children?: React.ReactNode;
      className?: string;
      'data-testid'?: string;
      variants?: object;
      custom?: number;
      [key: string]: unknown;
    }) => (
      <li
        className={className}
        data-testid={testId}
        data-variants={JSON.stringify(variants)}
        data-custom={custom}
        {...props}
      >
        {children}
      </li>
    ),
  },
  AnimatePresence: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="animate-presence">{children}</div>
  ),
  useReducedMotion: vi.fn(() => false),
}));

describe('AnimatedList', () => {
  const mockItems = [
    { id: '1', name: 'Item 1' },
    { id: '2', name: 'Item 2' },
    { id: '3', name: 'Item 3' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('basic rendering', () => {
    it('renders all items', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
        />
      );

      expect(screen.getByText('Item 1')).toBeInTheDocument();
      expect(screen.getByText('Item 2')).toBeInTheDocument();
      expect(screen.getByText('Item 3')).toBeInTheDocument();
    });

    it('renders empty state when no items', () => {
      type Item = { id: string; name: string };
      render(
        <AnimatedList<Item>
          items={[]}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
          emptyState={<div data-testid="empty-state">No items found</div>}
        />
      );

      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText('No items found')).toBeInTheDocument();
    });

    it('renders nothing when no items and no emptyState', () => {
      type Item = { id: string; name: string };
      const { container } = render(
        <AnimatedList<Item>
          items={[]}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
        />
      );

      const list = container.querySelector('[data-testid="animated-list"]');
      expect(list?.children.length).toBe(0);
    });
  });

  describe('stagger configuration', () => {
    it('applies stagger delay to items', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
          staggerDelay={0.1}
        />
      );

      const items = screen.getAllByTestId('animated-list-item');
      expect(items).toHaveLength(3);

      // Check custom index is passed for stagger calculation
      expect(items[0]).toHaveAttribute('data-custom', '0');
      expect(items[1]).toHaveAttribute('data-custom', '1');
      expect(items[2]).toHaveAttribute('data-custom', '2');
    });

    it('uses default stagger delay when not specified', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
        />
      );

      const items = screen.getAllByTestId('animated-list-item');
      expect(items).toHaveLength(3);
    });
  });

  describe('animation variants', () => {
    it('supports fadeIn variant', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
          variant="fadeIn"
        />
      );

      const container = screen.getByTestId('animated-list');
      expect(container).toBeInTheDocument();
    });

    it('supports slideIn variant', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
          variant="slideIn"
        />
      );

      const container = screen.getByTestId('animated-list');
      expect(container).toBeInTheDocument();
    });

    it('supports scaleIn variant', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
          variant="scaleIn"
        />
      );

      const container = screen.getByTestId('animated-list');
      expect(container).toBeInTheDocument();
    });
  });

  describe('reduced motion support', () => {
    it('respects prefers-reduced-motion setting', async () => {
      const { useReducedMotion } = await import('framer-motion');
      vi.mocked(useReducedMotion).mockReturnValue(true);

      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
        />
      );

      // All items should still render
      expect(screen.getByText('Item 1')).toBeInTheDocument();
      expect(screen.getByText('Item 2')).toBeInTheDocument();
      expect(screen.getByText('Item 3')).toBeInTheDocument();
    });

    it('applies reduced motion class when motion is reduced', async () => {
      const { useReducedMotion } = await import('framer-motion');
      vi.mocked(useReducedMotion).mockReturnValue(true);

      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
        />
      );

      const container = screen.getByTestId('animated-list');
      expect(container).toHaveClass('motion-reduce');
    });
  });

  describe('custom className', () => {
    it('applies custom className to list container', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
          className="custom-list-class"
        />
      );

      const container = screen.getByTestId('animated-list');
      expect(container).toHaveClass('custom-list-class');
    });

    it('applies custom itemClassName to list items', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
          itemClassName="custom-item-class"
        />
      );

      const items = screen.getAllByTestId('animated-list-item');
      items.forEach((item) => {
        expect(item).toHaveClass('custom-item-class');
      });
    });
  });

  describe('AnimatePresence integration', () => {
    it('wraps list in AnimatePresence for exit animations', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
        />
      );

      expect(screen.getByTestId('animate-presence')).toBeInTheDocument();
    });
  });

  describe('key extraction', () => {
    it('uses keyExtractor for unique keys', () => {
      const itemsWithCustomKey = [
        { customId: 'a', label: 'First' },
        { customId: 'b', label: 'Second' },
      ];

      render(
        <AnimatedList
          items={itemsWithCustomKey}
          renderItem={(item) => <span>{item.label}</span>}
          keyExtractor={(item) => item.customId}
        />
      );

      expect(screen.getByText('First')).toBeInTheDocument();
      expect(screen.getByText('Second')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('renders as semantic list by default', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
        />
      );

      const list = screen.getByTestId('animated-list');
      expect(list.tagName).toBe('UL');
    });

    it('renders list items as li elements', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
        />
      );

      const items = screen.getAllByTestId('animated-list-item');
      items.forEach((item) => {
        expect(item.tagName).toBe('LI');
      });
    });

    it('supports role attribute for non-list usage', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
          role="listbox"
        />
      );

      const list = screen.getByTestId('animated-list');
      expect(list).toHaveAttribute('role', 'listbox');
    });
  });

  describe('as prop for element type', () => {
    it('renders as div when as="div"', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
          as="div"
        />
      );

      const container = screen.getByTestId('animated-list');
      expect(container.tagName).toBe('DIV');
    });
  });

  describe('initial animation state', () => {
    it('starts items in initial state', () => {
      render(
        <AnimatedList
          items={mockItems}
          renderItem={(item) => <span>{item.name}</span>}
          keyExtractor={(item) => item.id}
        />
      );

      const container = screen.getByTestId('animated-list');
      expect(container).toHaveAttribute('data-initial', 'hidden');
      expect(container).toHaveAttribute('data-animate', 'visible');
    });
  });
});
