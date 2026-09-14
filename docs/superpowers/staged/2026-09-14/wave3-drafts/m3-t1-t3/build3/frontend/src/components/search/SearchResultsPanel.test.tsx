import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import SearchResultsPanel from './SearchResultsPanel';

import type { SearchResult } from '../../services/api';

describe('SearchResultsPanel', () => {
  const mockOnPageChange = vi.fn();
  const mockOnResultClick = vi.fn();
  const mockOnClearSearch = vi.fn();

  const mockResults: SearchResult[] = [
    {
      id: 1,
      camera_id: 'front_door',
      camera_name: 'Front Door',
      started_at: '2025-12-30T10:30:00Z',
      ended_at: '2025-12-30T10:32:00Z',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Suspicious person detected',
      reasoning: 'Unknown individual',
      reviewed: false,
      detection_count: 5,
      detection_ids: [1, 2, 3, 4, 5],
      object_types: 'person',
      relevance_score: 0.9,
    },
    {
      id: 2,
      camera_id: 'back_yard',
      camera_name: 'Back Yard',
      started_at: '2025-12-30T09:00:00Z',
      ended_at: '2025-12-30T09:05:00Z',
      risk_score: 45,
      risk_level: 'medium',
      summary: 'Vehicle detected in driveway',
      reasoning: 'Delivery vehicle',
      reviewed: true,
      detection_count: 3,
      detection_ids: [6, 7, 8],
      object_types: 'vehicle',
      relevance_score: 0.7,
    },
  ];

  beforeEach(() => {
    mockOnPageChange.mockClear();
    mockOnResultClick.mockClear();
    mockOnClearSearch.mockClear();
  });

  it('renders search results', () => {
    render(
      <SearchResultsPanel
        results={mockResults}
        totalCount={2}
        offset={0}
        limit={20}
        isLoading={false}
        onPageChange={mockOnPageChange}
      />
    );

    expect(screen.getByText('Suspicious person detected')).toBeInTheDocument();
    expect(screen.getByText('Vehicle detected in driveway')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(
      <SearchResultsPanel
        results={[]}
        totalCount={0}
        offset={0}
        limit={20}
        isLoading={true}
        onPageChange={mockOnPageChange}
      />
    );

    expect(screen.getByText(/searching events/i)).toBeInTheDocument();
  });

  it('shows error state', () => {
    render(
      <SearchResultsPanel
        results={[]}
        totalCount={0}
        offset={0}
        limit={20}
        isLoading={false}
        error="Search service unavailable"
        onPageChange={mockOnPageChange}
        onClearSearch={mockOnClearSearch}
      />
    );

    expect(screen.getByText('Search Failed')).toBeInTheDocument();
    expect(screen.getByText('Search service unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument();
  });

  it('shows empty state when no results', () => {
    render(
      <SearchResultsPanel
        results={[]}
        totalCount={0}
        offset={0}
        limit={20}
        isLoading={false}
        searchQuery="nonexistent"
        onPageChange={mockOnPageChange}
      />
    );

    expect(screen.getByText('No Results Found')).toBeInTheDocument();
    expect(screen.getByText(/nonexistent/)).toBeInTheDocument();
  });

  it('shows result count in header', () => {
    render(
      <SearchResultsPanel
        results={mockResults}
        totalCount={42}
        offset={0}
        limit={20}
        isLoading={false}
        onPageChange={mockOnPageChange}
      />
    );

    expect(screen.getByText(/1-2/)).toBeInTheDocument();
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });

  it('displays search query in header', () => {
    render(
      <SearchResultsPanel
        results={mockResults}
        totalCount={2}
        offset={0}
        limit={20}
        isLoading={false}
        searchQuery="suspicious person"
        onPageChange={mockOnPageChange}
      />
    );

    expect(screen.getByText(/suspicious person/)).toBeInTheDocument();
  });

  it('calls onResultClick when a result is clicked', async () => {
    const user = userEvent.setup();

    render(
      <SearchResultsPanel
        results={mockResults}
        totalCount={2}
        offset={0}
        limit={20}
        isLoading={false}
        onPageChange={mockOnPageChange}
        onResultClick={mockOnResultClick}
      />
    );

    // Click the first result card
    const firstResult = screen.getByText('Suspicious person detected').closest('[role="button"]');
    if (firstResult) {
      await user.click(firstResult);
    }

    expect(mockOnResultClick).toHaveBeenCalledWith(1);
  });

  it('calls onClearSearch when clear button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <SearchResultsPanel
        results={mockResults}
        totalCount={2}
        offset={0}
        limit={20}
        isLoading={false}
        onPageChange={mockOnPageChange}
        onClearSearch={mockOnClearSearch}
      />
    );

    const clearButton = screen.getByRole('button', { name: /clear search/i });
    await user.click(clearButton);

    expect(mockOnClearSearch).toHaveBeenCalled();
  });

  describe('pagination', () => {
    it('shows pagination controls when there are multiple pages', () => {
      render(
        <SearchResultsPanel
          results={mockResults}
          totalCount={100}
          offset={0}
          limit={20}
          isLoading={false}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByRole('button', { name: /previous page/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next page/i })).toBeInTheDocument();
      // Page text has numbers in span elements
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('does not show pagination when there is only one page', () => {
      render(
        <SearchResultsPanel
          results={mockResults}
          totalCount={2}
          offset={0}
          limit={20}
          isLoading={false}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.queryByRole('button', { name: /previous page/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /next page/i })).not.toBeInTheDocument();
    });

    it('disables previous button on first page', () => {
      render(
        <SearchResultsPanel
          results={mockResults}
          totalCount={100}
          offset={0}
          limit={20}
          isLoading={false}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByRole('button', { name: /previous page/i })).toBeDisabled();
    });

    it('disables next button on last page', () => {
      render(
        <SearchResultsPanel
          results={mockResults}
          totalCount={100}
          offset={80}
          limit={20}
          isLoading={false}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByRole('button', { name: /next page/i })).toBeDisabled();
    });

    it('calls onPageChange with correct offset when clicking next', async () => {
      const user = userEvent.setup();

      render(
        <SearchResultsPanel
          results={mockResults}
          totalCount={100}
          offset={0}
          limit={20}
          isLoading={false}
          onPageChange={mockOnPageChange}
        />
      );

      const nextButton = screen.getByRole('button', { name: /next page/i });
      await user.click(nextButton);

      expect(mockOnPageChange).toHaveBeenCalledWith(20);
    });

    it('calls onPageChange with correct offset when clicking previous', async () => {
      const user = userEvent.setup();

      render(
        <SearchResultsPanel
          results={mockResults}
          totalCount={100}
          offset={40}
          limit={20}
          isLoading={false}
          onPageChange={mockOnPageChange}
        />
      );

      const prevButton = screen.getByRole('button', { name: /previous page/i });
      await user.click(prevButton);

      expect(mockOnPageChange).toHaveBeenCalledWith(20);
    });

    it('displays correct page number', () => {
      render(
        <SearchResultsPanel
          results={mockResults}
          totalCount={100}
          offset={40}
          limit={20}
          isLoading={false}
          onPageChange={mockOnPageChange}
        />
      );

      // Page text has numbers in span elements
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  it('applies custom className', () => {
    const { container } = render(
      <SearchResultsPanel
        results={mockResults}
        totalCount={2}
        offset={0}
        limit={20}
        isLoading={false}
        onPageChange={mockOnPageChange}
        className="custom-class"
      />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('shows clear search button in empty state when onClearSearch is provided', () => {
    render(
      <SearchResultsPanel
        results={[]}
        totalCount={0}
        offset={0}
        limit={20}
        isLoading={false}
        searchQuery="test"
        onPageChange={mockOnPageChange}
        onClearSearch={mockOnClearSearch}
      />
    );

    expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument();
  });

  it('does not show clear button in empty state without onClearSearch', () => {
    render(
      <SearchResultsPanel
        results={[]}
        totalCount={0}
        offset={0}
        limit={20}
        isLoading={false}
        searchQuery="test"
        onPageChange={mockOnPageChange}
      />
    );

    expect(screen.queryByRole('button', { name: /clear search/i })).not.toBeInTheDocument();
  });
});
