import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import InfiniteScrollStatus from './InfiniteScrollStatus';

describe('InfiniteScrollStatus', () => {
  const createMockSentinelRef = () => vi.fn();

  describe('loading state', () => {
    it('renders loading indicator when isLoading is true', () => {
      const sentinelRef = createMockSentinelRef();

      render(<InfiniteScrollStatus sentinelRef={sentinelRef} isLoading={true} hasMore={true} />);

      expect(screen.getByTestId('infinite-scroll-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading more...')).toBeInTheDocument();
    });

    it('uses custom loading message', () => {
      const sentinelRef = createMockSentinelRef();

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={true}
          hasMore={true}
          loadingMessage="Fetching events..."
        />
      );

      expect(screen.getByText('Fetching events...')).toBeInTheDocument();
    });

    it('shows progress when totalCount and loadedCount are provided', () => {
      const sentinelRef = createMockSentinelRef();

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={true}
          hasMore={true}
          totalCount={100}
          loadedCount={50}
        />
      );

      expect(screen.getByText('Loaded 50 of 100')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('renders error message when error is provided', () => {
      const sentinelRef = createMockSentinelRef();
      const error = new Error('Network error');

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={true}
          error={error}
        />
      );

      expect(screen.getByTestId('infinite-scroll-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load more')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('renders retry button when onRetry is provided', () => {
      const sentinelRef = createMockSentinelRef();
      const onRetry = vi.fn();
      const error = new Error('Network error');

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={true}
          error={error}
          onRetry={onRetry}
        />
      );

      expect(screen.getByTestId('infinite-scroll-retry')).toBeInTheDocument();
    });

    it('calls onRetry when retry button is clicked', () => {
      const sentinelRef = createMockSentinelRef();
      const onRetry = vi.fn();
      const error = new Error('Network error');

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={true}
          error={error}
          onRetry={onRetry}
        />
      );

      fireEvent.click(screen.getByTestId('infinite-scroll-retry'));

      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('does not render retry button when onRetry is not provided', () => {
      const sentinelRef = createMockSentinelRef();
      const error = new Error('Network error');

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={true}
          error={error}
        />
      );

      expect(screen.queryByTestId('infinite-scroll-retry')).not.toBeInTheDocument();
    });
  });

  describe('end of list state', () => {
    it('renders end message when hasMore is false', () => {
      const sentinelRef = createMockSentinelRef();

      render(<InfiniteScrollStatus sentinelRef={sentinelRef} isLoading={false} hasMore={false} />);

      expect(screen.getByTestId('infinite-scroll-end')).toBeInTheDocument();
      expect(screen.getByText("You've reached the end")).toBeInTheDocument();
    });

    it('uses custom end message', () => {
      const sentinelRef = createMockSentinelRef();

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={false}
          endMessage="No more events to load"
        />
      );

      expect(screen.getByText('No more events to load')).toBeInTheDocument();
    });

    it('shows total count when provided', () => {
      const sentinelRef = createMockSentinelRef();

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={false}
          totalCount={150}
        />
      );

      expect(screen.getByText('150 items total')).toBeInTheDocument();
    });

    it('does not show end message when showEndMessage is false', () => {
      const sentinelRef = createMockSentinelRef();

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={false}
          showEndMessage={false}
        />
      );

      expect(screen.getByTestId('infinite-scroll-hidden')).toBeInTheDocument();
      expect(screen.queryByText("You've reached the end")).not.toBeInTheDocument();
    });
  });

  describe('sentinel state', () => {
    it('renders sentinel when hasMore is true and not loading', () => {
      const sentinelRef = createMockSentinelRef();

      render(<InfiniteScrollStatus sentinelRef={sentinelRef} isLoading={false} hasMore={true} />);

      expect(screen.getByTestId('infinite-scroll-sentinel')).toBeInTheDocument();
    });

    it('sentinel is aria-hidden', () => {
      const sentinelRef = createMockSentinelRef();

      render(<InfiniteScrollStatus sentinelRef={sentinelRef} isLoading={false} hasMore={true} />);

      expect(screen.getByTestId('infinite-scroll-sentinel')).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('ref attachment', () => {
    it('calls sentinelRef with the element in loading state', () => {
      const sentinelRef = createMockSentinelRef();

      render(<InfiniteScrollStatus sentinelRef={sentinelRef} isLoading={true} hasMore={true} />);

      expect(sentinelRef).toHaveBeenCalled();
    });

    it('calls sentinelRef with the element in error state', () => {
      const sentinelRef = createMockSentinelRef();
      const error = new Error('Test error');

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={true}
          error={error}
        />
      );

      expect(sentinelRef).toHaveBeenCalled();
    });

    it('calls sentinelRef with the element in end state', () => {
      const sentinelRef = createMockSentinelRef();

      render(<InfiniteScrollStatus sentinelRef={sentinelRef} isLoading={false} hasMore={false} />);

      expect(sentinelRef).toHaveBeenCalled();
    });

    it('calls sentinelRef with the element in sentinel state', () => {
      const sentinelRef = createMockSentinelRef();

      render(<InfiniteScrollStatus sentinelRef={sentinelRef} isLoading={false} hasMore={true} />);

      expect(sentinelRef).toHaveBeenCalled();
    });
  });

  describe('className prop', () => {
    it('applies custom className in loading state', () => {
      const sentinelRef = createMockSentinelRef();

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={true}
          hasMore={true}
          className="custom-class"
        />
      );

      expect(screen.getByTestId('infinite-scroll-loading')).toHaveClass('custom-class');
    });

    it('applies custom className in error state', () => {
      const sentinelRef = createMockSentinelRef();
      const error = new Error('Test error');

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={true}
          error={error}
          className="custom-class"
        />
      );

      expect(screen.getByTestId('infinite-scroll-error')).toHaveClass('custom-class');
    });

    it('applies custom className in end state', () => {
      const sentinelRef = createMockSentinelRef();

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={false}
          className="custom-class"
        />
      );

      expect(screen.getByTestId('infinite-scroll-end')).toHaveClass('custom-class');
    });

    it('applies custom className in sentinel state', () => {
      const sentinelRef = createMockSentinelRef();

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={false}
          hasMore={true}
          className="custom-class"
        />
      );

      expect(screen.getByTestId('infinite-scroll-sentinel')).toHaveClass('custom-class');
    });
  });

  describe('state priority', () => {
    it('error takes priority over loading', () => {
      const sentinelRef = createMockSentinelRef();
      const error = new Error('Test error');

      render(
        <InfiniteScrollStatus
          sentinelRef={sentinelRef}
          isLoading={true}
          hasMore={true}
          error={error}
        />
      );

      expect(screen.getByTestId('infinite-scroll-error')).toBeInTheDocument();
      expect(screen.queryByTestId('infinite-scroll-loading')).not.toBeInTheDocument();
    });

    it('loading takes priority over sentinel', () => {
      const sentinelRef = createMockSentinelRef();

      render(<InfiniteScrollStatus sentinelRef={sentinelRef} isLoading={true} hasMore={true} />);

      expect(screen.getByTestId('infinite-scroll-loading')).toBeInTheDocument();
      expect(screen.queryByTestId('infinite-scroll-sentinel')).not.toBeInTheDocument();
    });
  });
});
