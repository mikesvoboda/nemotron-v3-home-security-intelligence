/**
 * Tests for AuditResultsTable component
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import AuditResultsTable from './AuditResultsTable';

import type { AuditResult } from './AuditResultsTable';

const mockResults: AuditResult[] = [
  {
    eventId: 1001,
    originalScore: 75,
    reevaluatedScore: 65,
    delta: -10,
    qualityScore: 4.5,
    status: 'improved',
  },
  {
    eventId: 1002,
    originalScore: 50,
    reevaluatedScore: 55,
    delta: 5,
    qualityScore: 4.2,
    status: 'unchanged',
  },
  {
    eventId: 1003,
    originalScore: 30,
    reevaluatedScore: 45,
    delta: 15,
    qualityScore: 3.8,
    status: 'degraded',
  },
];

const renderWithRouter = (ui: React.ReactElement) => {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
};

describe('AuditResultsTable', () => {
  it('renders table with correct headers', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText('Event ID')).toBeInTheDocument();
    expect(screen.getByText('Original Score')).toBeInTheDocument();
    expect(screen.getByText('Re-evaluated')).toBeInTheDocument();
    expect(screen.getByText('Delta')).toBeInTheDocument();
    expect(screen.getByText('Quality')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
  });

  it('displays all audit results in table rows', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText('#1001')).toBeInTheDocument();
    expect(screen.getByText('#1002')).toBeInTheDocument();
    expect(screen.getByText('#1003')).toBeInTheDocument();
  });

  it('displays original scores correctly', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText('75')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
  });

  it('displays re-evaluated scores correctly', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText('65')).toBeInTheDocument();
    expect(screen.getByText('55')).toBeInTheDocument();
    expect(screen.getByText('45')).toBeInTheDocument();
  });

  it('displays delta with correct sign for improvements', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText('-10')).toBeInTheDocument();
  });

  it('displays delta with correct sign for degradations', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText('+15')).toBeInTheDocument();
  });

  it('displays quality scores with proper formatting', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText('4.5 / 5')).toBeInTheDocument();
    expect(screen.getByText('4.2 / 5')).toBeInTheDocument();
    expect(screen.getByText('3.8 / 5')).toBeInTheDocument();
  });

  it('displays status badges for each result', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText('Improved')).toBeInTheDocument();
    expect(screen.getByText('Unchanged')).toBeInTheDocument();
    expect(screen.getByText('Degraded')).toBeInTheDocument();
  });

  it('renders empty state when no results provided', () => {
    renderWithRouter(<AuditResultsTable results={[]} />);

    expect(screen.getByText(/no audit results/i)).toBeInTheDocument();
  });

  it('renders with correct data-testid', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByTestId('audit-results-table')).toBeInTheDocument();
  });

  it('makes event IDs clickable links', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    const eventLink = screen.getByRole('link', { name: /#1001/i });
    expect(eventLink).toHaveAttribute('href', '/events/1001');
  });

  it('applies correct color classes for improved status', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    const improvedBadge = screen.getByText('Improved');
    expect(improvedBadge).toHaveClass('bg-green-900/30', 'text-green-400');
  });

  it('applies correct color classes for degraded status', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    const degradedBadge = screen.getByText('Degraded');
    expect(degradedBadge).toHaveClass('bg-red-900/30', 'text-red-400');
  });

  it('applies correct color classes for unchanged status', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    const unchangedBadge = screen.getByText('Unchanged');
    expect(unchangedBadge).toHaveClass('bg-gray-800', 'text-gray-400');
  });

  it('displays table title', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText('Recent Audit Results')).toBeInTheDocument();
  });

  it('displays result count in subtitle', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    expect(screen.getByText(/showing 3 most recent/i)).toBeInTheDocument();
  });

  it('handles single result correctly', () => {
    const singleResult: AuditResult[] = [mockResults[0]];
    renderWithRouter(<AuditResultsTable results={singleResult} />);

    expect(screen.getByText(/showing 1 most recent/i)).toBeInTheDocument();
  });

  it('renders table rows with hover effects', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    const rows = screen.getAllByRole('row');
    // First row is header, subsequent rows are data
    expect(rows.length).toBe(mockResults.length + 1);
  });

  it('displays delta color coded based on improvement', () => {
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    // Negative delta (improvement) should be green
    const improvementDelta = screen.getByText('-10');
    expect(improvementDelta).toHaveClass('text-green-400');

    // Positive delta (degradation) should be red
    const degradationDelta = screen.getByText('+15');
    expect(degradationDelta).toHaveClass('text-red-400');
  });

  it('handles click on event link', async () => {
    const user = userEvent.setup();
    renderWithRouter(<AuditResultsTable results={mockResults} />);

    const eventLink = screen.getByRole('link', { name: /#1001/i });
    await user.click(eventLink);

    // Link should navigate (MemoryRouter will handle)
    expect(eventLink).toHaveAttribute('href', '/events/1001');
  });
});
