import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import TableRowSkeleton from './TableRowSkeleton';

describe('TableRowSkeleton', () => {
  it('renders skeleton container with correct test id', () => {
    render(<TableRowSkeleton />);
    const skeleton = screen.getByTestId('table-row-skeleton');
    expect(skeleton).toBeInTheDocument();
  });

  it('renders default 4 columns', () => {
    render(<TableRowSkeleton />);
    const columns = screen.getAllByTestId(/table-row-skeleton-col-/);
    expect(columns.length).toBe(4);
  });

  it('renders specified number of columns', () => {
    render(<TableRowSkeleton columns={6} />);
    const columns = screen.getAllByTestId(/table-row-skeleton-col-/);
    expect(columns.length).toBe(6);
  });

  it('renders multiple rows when rows prop is specified', () => {
    render(<TableRowSkeleton rows={5} />);
    const rows = screen.getAllByTestId(/table-row-skeleton-row-/);
    expect(rows.length).toBe(5);
  });

  it('applies custom className when provided', () => {
    render(<TableRowSkeleton className="custom-class" />);
    const skeleton = screen.getByTestId('table-row-skeleton');
    expect(skeleton).toHaveClass('custom-class');
  });

  it('has NVIDIA dark theme styling', () => {
    render(<TableRowSkeleton />);
    const skeleton = screen.getByTestId('table-row-skeleton');
    expect(skeleton).toHaveClass('divide-gray-800');
  });

  it('has aria-hidden for accessibility', () => {
    render(<TableRowSkeleton />);
    const skeleton = screen.getByTestId('table-row-skeleton');
    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
  });
});
