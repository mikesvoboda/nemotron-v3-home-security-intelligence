/**
 * Tests for ModelLeaderboard component
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ModelLeaderboard from './ModelLeaderboard';

import type { AiAuditModelLeaderboardEntry } from '../../services/api';

describe('ModelLeaderboard', () => {
  const mockEntries: AiAuditModelLeaderboardEntry[] = [
    { model_name: 'rtdetr', contribution_rate: 1.0, quality_correlation: null, event_count: 1000 },
    {
      model_name: 'florence',
      contribution_rate: 0.85,
      quality_correlation: 0.75,
      event_count: 850,
    },
    {
      model_name: 'image_quality',
      contribution_rate: 0.7,
      quality_correlation: 0.65,
      event_count: 700,
    },
    { model_name: 'zones', contribution_rate: 0.65, quality_correlation: null, event_count: 650 },
    { model_name: 'clip', contribution_rate: 0.6, quality_correlation: 0.5, event_count: 600 },
  ];

  const defaultProps = {
    entries: mockEntries,
    periodDays: 7,
  };

  it('renders the leaderboard container', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    expect(screen.getByTestId('model-leaderboard')).toBeInTheDocument();
  });

  it('renders the leaderboard title', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    expect(screen.getByText('Model Leaderboard')).toBeInTheDocument();
  });

  it('displays period days', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    expect(screen.getByText('Last 7 days')).toBeInTheDocument();
  });

  it('renders all model rows', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    expect(screen.getByTestId('leaderboard-row-rtdetr')).toBeInTheDocument();
    expect(screen.getByTestId('leaderboard-row-florence')).toBeInTheDocument();
    expect(screen.getByTestId('leaderboard-row-image_quality')).toBeInTheDocument();
  });

  it('displays human-readable model names', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    expect(screen.getByText('RT-DETR')).toBeInTheDocument();
    expect(screen.getByText('Florence-2')).toBeInTheDocument();
    expect(screen.getByText('Image Quality')).toBeInTheDocument();
  });

  it('displays contribution rates as percentages', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
    expect(screen.getByText('70%')).toBeInTheDocument();
  });

  it('displays event counts', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    expect(screen.getByText('1,000')).toBeInTheDocument();
    expect(screen.getByText('850')).toBeInTheDocument();
  });

  it('displays quality correlation when available', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    expect(screen.getByText('0.75')).toBeInTheDocument();
    expect(screen.getByText('0.65')).toBeInTheDocument();
  });

  it('displays dash for null quality correlation', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    // Should have multiple dashes for null correlations
    const dashes = screen.getAllByText('-');
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });

  it('renders empty state when no entries', () => {
    render(<ModelLeaderboard entries={[]} periodDays={7} />);
    expect(screen.getByText('No leaderboard data available')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<ModelLeaderboard {...defaultProps} className="custom-class" />);
    const container = screen.getByTestId('model-leaderboard');
    expect(container).toHaveClass('custom-class');
  });

  it('displays rank badges for top 3 models', () => {
    render(<ModelLeaderboard {...defaultProps} />);
    expect(screen.getByText('1st')).toBeInTheDocument();
    expect(screen.getByText('2nd')).toBeInTheDocument();
    expect(screen.getByText('3rd')).toBeInTheDocument();
  });
});

describe('ModelLeaderboard sorting', () => {
  const mockEntries: AiAuditModelLeaderboardEntry[] = [
    {
      model_name: 'florence',
      contribution_rate: 0.85,
      quality_correlation: null,
      event_count: 850,
    },
    { model_name: 'rtdetr', contribution_rate: 1.0, quality_correlation: null, event_count: 1000 },
    { model_name: 'clip', contribution_rate: 0.6, quality_correlation: null, event_count: 600 },
  ];

  it('sorts by contribution rate by default (descending)', () => {
    render(<ModelLeaderboard entries={mockEntries} periodDays={7} />);

    // Check that RT-DETR (highest contribution) appears before Florence
    const table = screen.getByTestId('leaderboard-table');
    const rows = table.querySelectorAll('tbody tr');

    // First row should have RT-DETR
    expect(rows[0]).toHaveTextContent('RT-DETR');
    expect(rows[1]).toHaveTextContent('Florence-2');
    expect(rows[2]).toHaveTextContent('CLIP');
  });

  it('can sort by model name', () => {
    render(<ModelLeaderboard entries={mockEntries} periodDays={7} />);

    // Click the Model header to sort
    const modelHeader = screen.getByText('Model');
    fireEvent.click(modelHeader);

    const table = screen.getByTestId('leaderboard-table');
    const rows = table.querySelectorAll('tbody tr');

    // Should be sorted alphabetically by display name (descending first click)
    // RT-DETR > Florence-2 > CLIP
    expect(rows[0]).toHaveTextContent('RT-DETR');
  });

  it('can sort by event count', () => {
    render(<ModelLeaderboard entries={mockEntries} periodDays={7} />);

    // Click the Events header to sort
    const eventsHeader = screen.getByText('Events');
    fireEvent.click(eventsHeader);

    const table = screen.getByTestId('leaderboard-table');
    const rows = table.querySelectorAll('tbody tr');

    // Should be sorted by event_count descending
    expect(rows[0]).toHaveTextContent('RT-DETR');
    expect(rows[1]).toHaveTextContent('Florence-2');
    expect(rows[2]).toHaveTextContent('CLIP');
  });
});
