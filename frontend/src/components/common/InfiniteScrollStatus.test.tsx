import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import InfiniteScrollStatus from './InfiniteScrollStatus';

describe('InfiniteScrollStatus', () => {
  describe('loading state', () => {
    it('shows loading indicator when fetching next page', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={true}
          hasNextPage={true}
        />
      );

      expect(screen.getByTestId('infinite-scroll-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading more...')).toBeInTheDocument();
    });

    it('shows custom loading message', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={true}
          hasNextPage={true}
          loadingMessage="Fetching events..."
        />
      );

      expect(screen.getByText('Fetching events...')).toBeInTheDocument();
    });

    it('shows loading spinner with correct styling', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={true}
          hasNextPage={true}
        />
      );

      const container = screen.getByTestId('infinite-scroll-loading');
      expect(container).toHaveClass('flex', 'items-center', 'justify-center');
    });
  });

  describe('end of list state', () => {
    it('shows end message when no more pages', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={false}
          hasNextPage={false}
        />
      );

      expect(screen.getByTestId('infinite-scroll-end')).toBeInTheDocument();
      expect(screen.getByText('All items loaded')).toBeInTheDocument();
    });

    it('shows custom end message', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={false}
          hasNextPage={false}
          endMessage="No more events to show"
        />
      );

      expect(screen.getByText('No more events to show')).toBeInTheDocument();
    });

    it('shows item count when provided', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={false}
          hasNextPage={false}
          totalCount={100}
          loadedCount={100}
        />
      );

      expect(screen.getByText('Showing 100 of 100 items')).toBeInTheDocument();
    });

    it('does not show item count when totalCount is not provided', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={false}
          hasNextPage={false}
        />
      );

      expect(screen.queryByText(/Showing \d+ of/)).not.toBeInTheDocument();
    });

    it('does not show item count when loadedCount is not provided', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={false}
          hasNextPage={false}
          totalCount={100}
        />
      );

      expect(screen.queryByText(/Showing \d+ of/)).not.toBeInTheDocument();
    });
  });

  describe('hidden state', () => {
    it('renders nothing when hasNextPage is true and not fetching', () => {
      const { container } = render(
        <InfiniteScrollStatus
          isFetchingNextPage={false}
          hasNextPage={true}
        />
      );

      expect(container.firstChild).toBeNull();
    });
  });

  describe('styling', () => {
    it('applies custom className to loading state', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={true}
          hasNextPage={true}
          className="mt-4"
        />
      );

      expect(screen.getByTestId('infinite-scroll-loading')).toHaveClass('mt-4');
    });

    it('applies custom className to end state', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={false}
          hasNextPage={false}
          className="mb-8"
        />
      );

      expect(screen.getByTestId('infinite-scroll-end')).toHaveClass('mb-8');
    });
  });

  describe('accessibility', () => {
    it('hides decorative icons from screen readers', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={true}
          hasNextPage={true}
        />
      );

      // Icons should have aria-hidden="true"
      const container = screen.getByTestId('infinite-scroll-loading');
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('aria-hidden', 'true');
    });

    it('hides decorative icons in end state from screen readers', () => {
      render(
        <InfiniteScrollStatus
          isFetchingNextPage={false}
          hasNextPage={false}
        />
      );

      const container = screen.getByTestId('infinite-scroll-end');
      const svg = container.querySelector('svg');
      expect(svg).toHaveAttribute('aria-hidden', 'true');
    });
  });
});
