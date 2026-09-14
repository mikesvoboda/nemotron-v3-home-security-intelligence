/**
 * Tests for SuggestionDiffView component
 *
 * This component displays a GitHub-style diff view showing what will change
 * when a suggestion is applied to a prompt.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SuggestionDiffView from './SuggestionDiffView';

import type { DiffLine } from './SuggestionDiffView';
import type { EnrichedSuggestion } from '../../services/api';

describe('SuggestionDiffView', () => {
  const mockSuggestion: EnrichedSuggestion = {
    category: 'missing_context',
    suggestion: 'Add time since last detected motion or event',
    priority: 'high',
    frequency: 3,
    targetSection: 'Camera & Time Context',
    insertionPoint: 'append',
    proposedVariable: '{time_since_last_event}',
    proposedLabel: 'Time Since Last Event:',
    impactExplanation:
      'Adding time-since-last-event helps the AI distinguish between routine activity and unusual timing patterns.',
    sourceEventIds: [142, 156, 189],
  };

  const mockDiff: DiffLine[] = [
    { type: 'context', content: '## Camera & Time Context', lineNumber: 1 },
    { type: 'context', content: 'Camera: {camera_name}', lineNumber: 2 },
    { type: 'unchanged', content: 'Time: {timestamp}', lineNumber: 3 },
    { type: 'unchanged', content: 'Day: {day_of_week}', lineNumber: 4 },
    { type: 'unchanged', content: 'Lighting: {time_of_day}', lineNumber: 5 },
    { type: 'added', content: 'Time Since Last Event: {time_since_last_event}', lineNumber: 6 },
  ];

  const originalPrompt = `## Camera & Time Context
Camera: {camera_name}
Time: {timestamp}
Day: {day_of_week}
Lighting: {time_of_day}`;

  it('renders suggestion header', () => {
    render(
      <SuggestionDiffView
        originalPrompt={originalPrompt}
        suggestion={mockSuggestion}
        diff={mockDiff}
      />
    );

    // Suggestion text should be displayed in the header
    expect(screen.getByText('Add time since last detected motion or event')).toBeInTheDocument();
  });

  it('renders added lines with green styling', () => {
    render(
      <SuggestionDiffView
        originalPrompt={originalPrompt}
        suggestion={mockSuggestion}
        diff={mockDiff}
      />
    );

    const addedLine = screen.getByTestId('diff-line-added-5');
    expect(addedLine).toBeInTheDocument();
    // Check for green background styling class
    expect(addedLine).toHaveClass('bg-green-900/30');
    // Check for + prefix
    expect(addedLine).toHaveTextContent('+');
    expect(addedLine).toHaveTextContent('Time Since Last Event: {time_since_last_event}');
  });

  it('renders removed lines with red styling', () => {
    const diffWithRemoval: DiffLine[] = [
      { type: 'context', content: '## Camera & Time Context', lineNumber: 1 },
      { type: 'removed', content: 'Old Field: {old_field}', lineNumber: 2 },
      { type: 'added', content: 'New Field: {new_field}', lineNumber: 2 },
    ];

    render(
      <SuggestionDiffView
        originalPrompt={originalPrompt}
        suggestion={mockSuggestion}
        diff={diffWithRemoval}
      />
    );

    const removedLine = screen.getByTestId('diff-line-removed-1');
    expect(removedLine).toBeInTheDocument();
    // Check for red background styling class
    expect(removedLine).toHaveClass('bg-red-900/30');
    // Check for - prefix
    expect(removedLine).toHaveTextContent('-');
    expect(removedLine).toHaveTextContent('Old Field: {old_field}');
  });

  it('shows line numbers', () => {
    render(
      <SuggestionDiffView
        originalPrompt={originalPrompt}
        suggestion={mockSuggestion}
        diff={mockDiff}
      />
    );

    // Check line numbers are displayed
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument();
  });

  it('shows context lines', () => {
    render(
      <SuggestionDiffView
        originalPrompt={originalPrompt}
        suggestion={mockSuggestion}
        diff={mockDiff}
      />
    );

    // Context lines should have gray background
    const contextLine = screen.getByTestId('diff-line-context-0');
    expect(contextLine).toBeInTheDocument();
    expect(contextLine).toHaveClass('bg-gray-800/30');
    expect(contextLine).toHaveTextContent('## Camera & Time Context');
  });

  it('uses monospace font', () => {
    render(
      <SuggestionDiffView
        originalPrompt={originalPrompt}
        suggestion={mockSuggestion}
        diff={mockDiff}
      />
    );

    const diffContainer = screen.getByTestId('suggestion-diff-view');
    const codeBlock = diffContainer.querySelector('[data-testid="diff-code-block"]');
    expect(codeBlock).toBeInTheDocument();
    expect(codeBlock).toHaveClass('font-mono');
  });

  it('handles empty diff gracefully', () => {
    render(
      <SuggestionDiffView originalPrompt={originalPrompt} suggestion={mockSuggestion} diff={[]} />
    );

    // Should show empty state message
    expect(screen.getByText('No changes to display')).toBeInTheDocument();
  });

  it('applies className prop', () => {
    render(
      <SuggestionDiffView
        originalPrompt={originalPrompt}
        suggestion={mockSuggestion}
        diff={mockDiff}
        className="custom-class"
      />
    );

    const container = screen.getByTestId('suggestion-diff-view');
    expect(container).toHaveClass('custom-class');
  });
});

describe('SuggestionDiffView accessibility', () => {
  const mockSuggestion: EnrichedSuggestion = {
    category: 'missing_context',
    suggestion: 'Add time context',
    priority: 'high',
    frequency: 1,
    targetSection: 'Context',
    insertionPoint: 'append',
    proposedVariable: '{time}',
    proposedLabel: 'Time:',
    impactExplanation: 'Helps with timing analysis.',
    sourceEventIds: [1],
  };

  const mockDiff: DiffLine[] = [{ type: 'added', content: 'Time: {time}', lineNumber: 1 }];

  it('has proper ARIA labels for the diff region', () => {
    render(
      <SuggestionDiffView originalPrompt="original" suggestion={mockSuggestion} diff={mockDiff} />
    );

    // Check that the diff region has an accessible label
    const diffRegion = screen.getByRole('region', { name: /diff/i });
    expect(diffRegion).toBeInTheDocument();
  });

  it('marks added and removed lines with appropriate accessibility attributes', () => {
    const diffWithChanges: DiffLine[] = [
      { type: 'removed', content: 'Old line', lineNumber: 1 },
      { type: 'added', content: 'New line', lineNumber: 1 },
    ];

    render(
      <SuggestionDiffView
        originalPrompt="original"
        suggestion={mockSuggestion}
        diff={diffWithChanges}
      />
    );

    // Added lines should have aria-label indicating addition
    const addedLine = screen.getByTestId('diff-line-added-1');
    expect(addedLine).toHaveAttribute('aria-label', expect.stringContaining('added'));

    // Removed lines should have aria-label indicating removal
    const removedLine = screen.getByTestId('diff-line-removed-0');
    expect(removedLine).toHaveAttribute('aria-label', expect.stringContaining('removed'));
  });
});

describe('SuggestionDiffView section indicator', () => {
  const mockSuggestion: EnrichedSuggestion = {
    category: 'missing_context',
    suggestion: 'Add weather data',
    priority: 'medium',
    frequency: 2,
    targetSection: 'Environmental Context',
    insertionPoint: 'append',
    proposedVariable: '{weather}',
    proposedLabel: 'Weather:',
    impactExplanation: 'Weather affects detection accuracy.',
    sourceEventIds: [100, 101],
  };

  it('shows which section is affected', () => {
    const mockDiff: DiffLine[] = [
      { type: 'context', content: '## Environmental Context', lineNumber: 10 },
      { type: 'added', content: 'Weather: {weather}', lineNumber: 11 },
    ];

    render(
      <SuggestionDiffView originalPrompt="original" suggestion={mockSuggestion} diff={mockDiff} />
    );

    // Should display the target section name in the header
    // Use a more specific query to find the target section indicator
    expect(screen.getByText(/Target:/)).toBeInTheDocument();
    expect(screen.getByText(/Target:/).parentElement).toHaveTextContent('Environmental Context');
  });
});
