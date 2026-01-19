import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import LazyEntityCard from './LazyEntityCard';

import type { EntityCardProps } from './EntityCard';

// Mock IntersectionObserver
const mockDisconnect = vi.fn();
const mockObserve = vi.fn();

interface MockIntersectionObserverCallback {
  (entries: IntersectionObserverEntry[]): void;
}

let observerCallback: MockIntersectionObserverCallback;

class MockIntersectionObserver {
  constructor(callback: MockIntersectionObserverCallback, _options?: IntersectionObserverInit) {
    observerCallback = callback;
  }

  observe = mockObserve;
  disconnect = mockDisconnect;
  unobserve = vi.fn();
  root = null;
  rootMargin = '';
  thresholds = [];
  takeRecords = () => [];
}

beforeEach(() => {
  mockDisconnect.mockClear();
  mockObserve.mockClear();

  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('LazyEntityCard', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock base props for an entity
  const mockEntityProps: EntityCardProps = {
    id: 'entity-lazy-123',
    entity_type: 'person',
    first_seen: new Date(BASE_TIME - 3 * 60 * 60 * 1000).toISOString(),
    last_seen: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(),
    appearance_count: 5,
    cameras_seen: ['front_door', 'garage'],
    thumbnail_url: 'https://example.com/lazy-thumb.jpg',
  };

  // Mock system time for consistent testing
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initial rendering', () => {
    it('renders skeleton initially when not visible', () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      // Should render skeleton, not the actual card
      expect(screen.getByTestId('entity-card-skeleton')).toBeInTheDocument();
      expect(screen.queryByTestId('entity-card')).not.toBeInTheDocument();
    });

    it('renders wrapper with correct test id', () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      expect(screen.getByTestId('lazy-entity-card-wrapper')).toBeInTheDocument();
    });

    it('observes the card ref element', () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      expect(mockObserve).toHaveBeenCalledTimes(1);
      expect(mockObserve).toHaveBeenCalledWith(expect.any(HTMLDivElement));
    });
  });

  describe('visibility behavior', () => {
    it('renders EntityCard when element becomes visible', async () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      // Initially shows skeleton
      expect(screen.getByTestId('entity-card-skeleton')).toBeInTheDocument();

      // Simulate intersection
      observerCallback([
        {
          isIntersecting: true,
          target: document.createElement('div'),
        } as unknown as IntersectionObserverEntry,
      ]);

      // Should now show the actual EntityCard
      await waitFor(() => {
        expect(screen.getByTestId('entity-card')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
    });

    it('does not render EntityCard when element is not intersecting', () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      // Simulate non-intersection
      observerCallback([
        {
          isIntersecting: false,
          target: document.createElement('div'),
        } as unknown as IntersectionObserverEntry,
      ]);

      // Should still show skeleton
      expect(screen.getByTestId('entity-card-skeleton')).toBeInTheDocument();
      expect(screen.queryByTestId('entity-card')).not.toBeInTheDocument();
    });

    it('disconnects observer after element becomes visible', async () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      // Simulate intersection
      observerCallback([
        {
          isIntersecting: true,
          target: document.createElement('div'),
        } as unknown as IntersectionObserverEntry,
      ]);

      await waitFor(() => {
        expect(mockDisconnect).toHaveBeenCalledTimes(1);
      });
    });

    it('does not disconnect observer if element is not intersecting', () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      // Simulate non-intersection
      observerCallback([
        {
          isIntersecting: false,
          target: document.createElement('div'),
        } as unknown as IntersectionObserverEntry,
      ]);

      // Disconnect should not have been called (only cleanup disconnect on unmount)
      expect(mockDisconnect).not.toHaveBeenCalled();
    });
  });

  describe('cleanup behavior', () => {
    it('disconnects observer on unmount', () => {
      const { unmount } = render(<LazyEntityCard {...mockEntityProps} />);

      unmount();

      expect(mockDisconnect).toHaveBeenCalled();
    });
  });

  describe('props forwarding', () => {
    it('passes all props to EntityCard when visible', async () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      // Make visible
      observerCallback([
        {
          isIntersecting: true,
          target: document.createElement('div'),
        } as unknown as IntersectionObserverEntry,
      ]);

      await waitFor(() => {
        expect(screen.getByTestId('entity-card')).toBeInTheDocument();
      });

      // Verify EntityCard renders with correct data
      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument(); // appearance count
      expect(screen.getByText('2')).toBeInTheDocument(); // cameras count
    });

    it('forwards className to EntityCard', async () => {
      render(<LazyEntityCard {...mockEntityProps} className="test-class" />);

      // Make visible
      observerCallback([
        {
          isIntersecting: true,
          target: document.createElement('div'),
        } as unknown as IntersectionObserverEntry,
      ]);

      await waitFor(() => {
        const entityCard = screen.getByTestId('entity-card');
        expect(entityCard).toHaveClass('test-class');
      });
    });

    it('forwards onClick handler to EntityCard', async () => {
      vi.useRealTimers();
      const handleClick = vi.fn();
      const { rerender } = render(<LazyEntityCard {...mockEntityProps} onClick={handleClick} />);

      // Make visible
      observerCallback([
        {
          isIntersecting: true,
          target: document.createElement('div'),
        } as unknown as IntersectionObserverEntry,
      ]);

      // Wait for re-render
      rerender(<LazyEntityCard {...mockEntityProps} onClick={handleClick} />);

      await waitFor(() => {
        expect(screen.getByTestId('entity-card')).toBeInTheDocument();
      });

      // The card should have the role="button" indicating it's clickable
      const card = screen.getByRole('button');
      expect(card).toBeInTheDocument();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('IntersectionObserver fallback', () => {
    it('renders EntityCard immediately if IntersectionObserver is not supported', () => {
      // Remove IntersectionObserver
      vi.stubGlobal('IntersectionObserver', undefined);

      render(<LazyEntityCard {...mockEntityProps} />);

      // Should render EntityCard immediately
      expect(screen.getByTestId('entity-card')).toBeInTheDocument();
      expect(screen.queryByTestId('entity-card-skeleton')).not.toBeInTheDocument();
    });
  });

  describe('different entity types', () => {
    it('renders person entity correctly when visible', async () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      observerCallback([
        {
          isIntersecting: true,
          target: document.createElement('div'),
        } as unknown as IntersectionObserverEntry,
      ]);

      await waitFor(() => {
        expect(screen.getByText('Person')).toBeInTheDocument();
      });
    });

    it('renders vehicle entity correctly when visible', async () => {
      const vehicleProps: EntityCardProps = {
        ...mockEntityProps,
        id: 'vehicle-lazy-456',
        entity_type: 'vehicle',
      };

      render(<LazyEntityCard {...vehicleProps} />);

      observerCallback([
        {
          isIntersecting: true,
          target: document.createElement('div'),
        } as unknown as IntersectionObserverEntry,
      ]);

      await waitFor(() => {
        expect(screen.getByText('Vehicle')).toBeInTheDocument();
      });
    });
  });

  describe('no layout shift', () => {
    it('skeleton maintains consistent height matching EntityCard structure', () => {
      render(<LazyEntityCard {...mockEntityProps} />);

      const skeleton = screen.getByTestId('entity-card-skeleton');
      // Verify skeleton has the expected structure that prevents layout shift
      expect(skeleton).toHaveClass('rounded-lg');
      expect(skeleton).toHaveClass('bg-[#1F1F1F]');
    });
  });
});
