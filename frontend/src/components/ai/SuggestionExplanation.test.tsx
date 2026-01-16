/**
 * Tests for SuggestionExplanation component
 *
 * This component displays an expandable "Why This Matters" panel that provides
 * educational context about why a suggestion would improve the prompt.
 */

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SuggestionExplanation from './SuggestionExplanation';

import type { EnrichedSuggestion } from '../../services/api';

describe('SuggestionExplanation', () => {
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

  it('renders collapsed by default', () => {
    render(<SuggestionExplanation suggestion={mockSuggestion} />);

    // Should show collapsed header
    expect(screen.getByText('Why this matters')).toBeInTheDocument();

    // Content should be hidden (impact explanation not visible)
    expect(screen.queryByText(/Adding time-since-last-event helps/)).not.toBeVisible();
  });

  it('expands on click', () => {
    render(<SuggestionExplanation suggestion={mockSuggestion} />);

    // Click to expand
    const header = screen.getByRole('button', { name: /why this matters/i });
    fireEvent.click(header);

    // Content should now be visible
    expect(screen.getByText(/Adding time-since-last-event helps/)).toBeVisible();
  });

  it('shows impact explanation', () => {
    render(<SuggestionExplanation suggestion={mockSuggestion} defaultExpanded />);

    // Impact explanation should be visible
    expect(screen.getByText(/Adding time-since-last-event helps/)).toBeInTheDocument();

    // Impact section header should be present
    expect(screen.getByText('Impact')).toBeInTheDocument();
  });

  it('shows event count', () => {
    render(<SuggestionExplanation suggestion={mockSuggestion} defaultExpanded />);

    // Should show the count of events
    expect(screen.getByText(/3 events/i)).toBeInTheDocument();
  });

  it('clicking event link calls onEventClick', () => {
    const onEventClick = vi.fn();
    render(
      <SuggestionExplanation
        suggestion={mockSuggestion}
        onEventClick={onEventClick}
        defaultExpanded
      />
    );

    // Find and click an event link
    const eventLink = screen.getByRole('button', { name: /event #142/i });
    fireEvent.click(eventLink);

    // Callback should be fired with event ID
    expect(onEventClick).toHaveBeenCalledWith(142);
  });

  it('shows category-specific tip', () => {
    render(<SuggestionExplanation suggestion={mockSuggestion} defaultExpanded />);

    // Should show the tip for missing_context category
    expect(screen.getByText(/temporal context variables/i)).toBeInTheDocument();
  });

  it('respects defaultExpanded prop', () => {
    render(<SuggestionExplanation suggestion={mockSuggestion} defaultExpanded />);

    // Content should be visible when defaultExpanded is true
    expect(screen.getByText(/Adding time-since-last-event helps/)).toBeVisible();
  });

  it('handles empty sourceEventIds', () => {
    const suggestionWithNoEvents: EnrichedSuggestion = {
      ...mockSuggestion,
      sourceEventIds: [],
    };

    render(<SuggestionExplanation suggestion={suggestionWithNoEvents} defaultExpanded />);

    // Should not crash and show appropriate message
    expect(screen.getByText(/no events/i)).toBeInTheDocument();
  });
});

describe('SuggestionExplanation category tips', () => {
  const baseSuggestion: EnrichedSuggestion = {
    category: 'missing_context',
    suggestion: 'Test suggestion',
    priority: 'medium',
    frequency: 1,
    targetSection: 'Test Section',
    insertionPoint: 'append',
    proposedVariable: '{test}',
    proposedLabel: 'Test:',
    impactExplanation: 'Test impact explanation.',
    sourceEventIds: [1],
  };

  it('shows unused_data tip for unused_data category', () => {
    const suggestion: EnrichedSuggestion = {
      ...baseSuggestion,
      category: 'unused_data',
    };

    render(<SuggestionExplanation suggestion={suggestion} defaultExpanded />);

    expect(screen.getByText(/removing unused fields to reduce token count/i)).toBeInTheDocument();
  });

  it('shows model_gaps tip for model_gaps category', () => {
    const suggestion: EnrichedSuggestion = {
      ...baseSuggestion,
      category: 'model_gaps',
    };

    render(<SuggestionExplanation suggestion={suggestion} defaultExpanded />);

    expect(screen.getByText(/model-specific sections/i)).toBeInTheDocument();
  });

  it('shows format_suggestions tip for format_suggestions category', () => {
    const suggestion: EnrichedSuggestion = {
      ...baseSuggestion,
      category: 'format_suggestions',
    };

    render(<SuggestionExplanation suggestion={suggestion} defaultExpanded />);

    expect(screen.getByText(/section headers help the AI navigate/i)).toBeInTheDocument();
  });
});

describe('SuggestionExplanation accessibility', () => {
  const mockSuggestion: EnrichedSuggestion = {
    category: 'missing_context',
    suggestion: 'Add time context',
    priority: 'high',
    frequency: 2,
    targetSection: 'Context',
    insertionPoint: 'append',
    proposedVariable: '{time}',
    proposedLabel: 'Time:',
    impactExplanation: 'Helps with timing analysis.',
    sourceEventIds: [1, 2],
  };

  it('has keyboard accessible expand/collapse', () => {
    render(<SuggestionExplanation suggestion={mockSuggestion} />);

    const header = screen.getByRole('button', { name: /why this matters/i });

    // Should be focusable
    header.focus();
    expect(header).toHaveFocus();

    // Should expand on Enter
    fireEvent.keyDown(header, { key: 'Enter' });
    expect(screen.getByText(/Helps with timing analysis/)).toBeVisible();
  });

  it('event links are keyboard accessible', () => {
    const onEventClick = vi.fn();
    render(
      <SuggestionExplanation
        suggestion={mockSuggestion}
        onEventClick={onEventClick}
        defaultExpanded
      />
    );

    const eventLink = screen.getByRole('button', { name: /event #1/i });

    // Should be focusable
    eventLink.focus();
    expect(eventLink).toHaveFocus();

    // Should trigger on Enter
    fireEvent.keyDown(eventLink, { key: 'Enter' });
    expect(onEventClick).toHaveBeenCalledWith(1);
  });
});

describe('SuggestionExplanation styling', () => {
  const mockSuggestion: EnrichedSuggestion = {
    category: 'missing_context',
    suggestion: 'Test suggestion',
    priority: 'medium',
    frequency: 1,
    targetSection: 'Test',
    insertionPoint: 'append',
    proposedVariable: '{test}',
    proposedLabel: 'Test:',
    impactExplanation: 'Test impact.',
    sourceEventIds: [1],
  };

  it('applies className prop', () => {
    render(<SuggestionExplanation suggestion={mockSuggestion} className="custom-class" />);

    const container = screen.getByTestId('suggestion-explanation');
    expect(container).toHaveClass('custom-class');
  });
});
