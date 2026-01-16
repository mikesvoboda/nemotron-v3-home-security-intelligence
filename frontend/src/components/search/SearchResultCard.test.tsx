import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import SearchResultCard from './SearchResultCard';

import type { SearchResult } from '../../services/api';

describe('SearchResultCard', () => {
  const mockResult: SearchResult = {
    id: 1,
    camera_id: 'front_door',
    camera_name: 'Front Door',
    started_at: '2025-12-30T10:30:00Z',
    ended_at: '2025-12-30T10:32:00Z',
    risk_score: 75,
    risk_level: 'high',
    summary: 'Suspicious person detected near entrance',
    reasoning: 'Unknown individual approaching during nighttime hours',
    reviewed: false,
    detection_count: 5,
    detection_ids: [1, 2, 3, 4, 5],
    object_types: 'person, vehicle',
    relevance_score: 0.85,
  };

  it('renders the search result summary', () => {
    render(<SearchResultCard result={mockResult} />);

    expect(screen.getByText('Suspicious person detected near entrance')).toBeInTheDocument();
  });

  it('displays the relevance score', () => {
    render(<SearchResultCard result={mockResult} />);

    // 0.85 * 100 = 85%
    expect(screen.getByText(/85% match/i)).toBeInTheDocument();
  });

  it('displays the camera name', () => {
    render(<SearchResultCard result={mockResult} />);

    expect(screen.getByText('Front Door')).toBeInTheDocument();
  });

  it('displays detection count', () => {
    render(<SearchResultCard result={mockResult} />);

    expect(screen.getByText(/5 detections/i)).toBeInTheDocument();
  });

  it('displays formatted date and time', () => {
    render(<SearchResultCard result={mockResult} />);

    // Date format: Dec 30, 2025
    expect(screen.getByText(/Dec 30, 2025/i)).toBeInTheDocument();
  });

  it('displays object types as badges', () => {
    render(<SearchResultCard result={mockResult} />);

    expect(screen.getByText('person')).toBeInTheDocument();
    expect(screen.getByText('vehicle')).toBeInTheDocument();
  });

  it('displays risk badge', () => {
    render(<SearchResultCard result={mockResult} />);

    expect(screen.getByText(/high/i)).toBeInTheDocument();
  });

  it('displays reasoning when available', () => {
    render(<SearchResultCard result={mockResult} />);

    expect(
      screen.getByText('Unknown individual approaching during nighttime hours')
    ).toBeInTheDocument();
  });

  it('does not display reasoning section when not available', () => {
    const resultWithoutReasoning = { ...mockResult, reasoning: null };
    render(<SearchResultCard result={resultWithoutReasoning} />);

    expect(
      screen.queryByText('Unknown individual approaching during nighttime hours')
    ).not.toBeInTheDocument();
  });

  it('calls onClick when card is clicked', async () => {
    const mockOnClick = vi.fn();
    const user = userEvent.setup();

    render(<SearchResultCard result={mockResult} onClick={mockOnClick} />);

    const card = screen.getByRole('button');
    await user.click(card);

    expect(mockOnClick).toHaveBeenCalledWith(1);
  });

  it('calls onClick when pressing Enter on the card', () => {
    const mockOnClick = vi.fn();

    render(<SearchResultCard result={mockResult} onClick={mockOnClick} />);

    const card = screen.getByRole('button');
    fireEvent.keyDown(card, { key: 'Enter' });

    expect(mockOnClick).toHaveBeenCalledWith(1);
  });

  it('calls onClick when pressing Space on the card', () => {
    const mockOnClick = vi.fn();

    render(<SearchResultCard result={mockResult} onClick={mockOnClick} />);

    const card = screen.getByRole('button');
    fireEvent.keyDown(card, { key: ' ' });

    expect(mockOnClick).toHaveBeenCalledWith(1);
  });

  it('shows reviewed status indicator when event is reviewed', () => {
    const reviewedResult = { ...mockResult, reviewed: true };
    render(<SearchResultCard result={reviewedResult} />);

    expect(screen.getByText('Reviewed')).toBeInTheDocument();
  });

  it('does not show reviewed indicator for unreviewed events', () => {
    render(<SearchResultCard result={mockResult} />);

    expect(screen.queryByText('Reviewed')).not.toBeInTheDocument();
  });

  it('applies selected styling when isSelected is true', () => {
    render(<SearchResultCard result={mockResult} isSelected={true} />);

    const card = screen.getByRole('button');
    expect(card).toHaveAttribute('aria-pressed', 'true');
  });

  it('uses camera_id when camera_name is not available', () => {
    const resultWithoutCameraName = { ...mockResult, camera_name: null };
    render(<SearchResultCard result={resultWithoutCameraName} />);

    expect(screen.getByText('front_door')).toBeInTheDocument();
  });

  it('displays "No summary available" when summary is null', () => {
    const resultWithoutSummary = { ...mockResult, summary: null };
    render(<SearchResultCard result={resultWithoutSummary} />);

    expect(screen.getByText('No summary available')).toBeInTheDocument();
  });

  it('handles single detection count correctly (no plural)', () => {
    const singleDetectionResult = { ...mockResult, detection_count: 1 };
    render(<SearchResultCard result={singleDetectionResult} />);

    expect(screen.getByText('1 detection')).toBeInTheDocument();
  });

  it('does not show object types section when empty', () => {
    const resultWithoutObjectTypes = { ...mockResult, object_types: null };
    render(<SearchResultCard result={resultWithoutObjectTypes} />);

    // Object type badges should not be present
    expect(screen.queryByText('person')).not.toBeInTheDocument();
    expect(screen.queryByText('vehicle')).not.toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(<SearchResultCard result={mockResult} className="custom-class" />);

    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('displays high relevance score with green color class', () => {
    const highRelevanceResult = { ...mockResult, relevance_score: 0.9 };
    render(<SearchResultCard result={highRelevanceResult} />);

    const matchText = screen.getByText(/90% match/i);
    expect(matchText).toHaveClass('text-green-400');
  });

  it('displays medium relevance score with NVIDIA green color class', () => {
    const mediumRelevanceResult = { ...mockResult, relevance_score: 0.6 };
    render(<SearchResultCard result={mediumRelevanceResult} />);

    const matchText = screen.getByText(/60% match/i);
    expect(matchText).toHaveClass('text-[#76B900]');
  });

  it('displays low relevance score with yellow color class', () => {
    const lowRelevanceResult = { ...mockResult, relevance_score: 0.35 };
    render(<SearchResultCard result={lowRelevanceResult} />);

    const matchText = screen.getByText(/35% match/i);
    expect(matchText).toHaveClass('text-yellow-400');
  });

  it('displays very low relevance score with gray color class', () => {
    const veryLowRelevanceResult = { ...mockResult, relevance_score: 0.1 };
    render(<SearchResultCard result={veryLowRelevanceResult} />);

    const matchText = screen.getByText(/10% match/i);
    expect(matchText).toHaveClass('text-gray-400');
  });
});
