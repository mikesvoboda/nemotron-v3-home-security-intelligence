/**
 * Tests for RecommendationsPanel component
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RecommendationsPanel from './RecommendationsPanel';

import type { AiAuditRecommendationItem } from '../../services/api';

describe('RecommendationsPanel', () => {
  const mockRecommendations: AiAuditRecommendationItem[] = [
    {
      category: 'missing_context',
      suggestion: 'Add time since last motion',
      frequency: 50,
      priority: 'high',
    },
    {
      category: 'missing_context',
      suggestion: 'Include historical activity patterns',
      frequency: 35,
      priority: 'medium',
    },
    {
      category: 'unused_data',
      suggestion: 'Weather data not used for indoor cameras',
      frequency: 30,
      priority: 'medium',
    },
    {
      category: 'model_gaps',
      suggestion: 'Violence detection missing from prompt',
      frequency: 20,
      priority: 'high',
    },
    {
      category: 'format_suggestions',
      suggestion: 'Group detections by object type',
      frequency: 15,
      priority: 'low',
    },
  ];

  const defaultProps = {
    recommendations: mockRecommendations,
    totalEventsAnalyzed: 800,
  };

  it('renders the recommendations panel container', () => {
    render(<RecommendationsPanel {...defaultProps} />);
    expect(screen.getByTestId('recommendations-panel')).toBeInTheDocument();
  });

  it('renders the panel title', () => {
    render(<RecommendationsPanel {...defaultProps} />);
    expect(screen.getByText('Prompt Improvement Recommendations')).toBeInTheDocument();
  });

  it('displays total events analyzed', () => {
    render(<RecommendationsPanel {...defaultProps} />);
    expect(screen.getByText('From 800 events')).toBeInTheDocument();
  });

  it('displays high priority count badge', () => {
    render(<RecommendationsPanel {...defaultProps} />);
    // 2 high priority items
    expect(screen.getByText('2 High Priority')).toBeInTheDocument();
  });

  it('renders category accordions', () => {
    render(<RecommendationsPanel {...defaultProps} />);

    expect(screen.getByTestId('recommendation-category-missing_context')).toBeInTheDocument();
    expect(screen.getByTestId('recommendation-category-unused_data')).toBeInTheDocument();
    expect(screen.getByTestId('recommendation-category-model_gaps')).toBeInTheDocument();
    expect(screen.getByTestId('recommendation-category-format_suggestions')).toBeInTheDocument();
  });

  it('displays category labels', () => {
    render(<RecommendationsPanel {...defaultProps} />);

    expect(screen.getByText('Missing Context')).toBeInTheDocument();
    expect(screen.getByText('Unused Data')).toBeInTheDocument();
    expect(screen.getByText('Model Gaps')).toBeInTheDocument();
    expect(screen.getByText('Format Suggestions')).toBeInTheDocument();
  });

  it('displays item counts per category', () => {
    render(<RecommendationsPanel {...defaultProps} />);

    // Missing context has 2 items
    expect(screen.getByText('2 items')).toBeInTheDocument();
    // Others have 1 item each
    expect(screen.getAllByText('1 items')).toHaveLength(3);
  });

  it('renders empty state when no recommendations', () => {
    render(<RecommendationsPanel recommendations={[]} totalEventsAnalyzed={0} />);
    expect(screen.getByText('No recommendations available')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<RecommendationsPanel {...defaultProps} className="custom-class" />);
    const container = screen.getByTestId('recommendations-panel');
    expect(container).toHaveClass('custom-class');
  });

  it('does not show high priority badge when no high priority items', () => {
    const lowPriorityRecommendations: AiAuditRecommendationItem[] = [
      {
        category: 'format_suggestions',
        suggestion: 'Minor formatting change',
        frequency: 5,
        priority: 'low',
      },
    ];
    render(
      <RecommendationsPanel
        recommendations={lowPriorityRecommendations}
        totalEventsAnalyzed={100}
      />
    );
    expect(screen.queryByText(/High Priority/)).not.toBeInTheDocument();
  });
});

describe('RecommendationsPanel priority indicators', () => {
  it('displays high priority count in category header', () => {
    const recommendations: AiAuditRecommendationItem[] = [
      {
        category: 'missing_context',
        suggestion: 'High priority suggestion',
        frequency: 50,
        priority: 'high',
      },
      {
        category: 'missing_context',
        suggestion: 'Medium priority suggestion',
        frequency: 30,
        priority: 'medium',
      },
      {
        category: 'missing_context',
        suggestion: 'Low priority suggestion',
        frequency: 10,
        priority: 'low',
      },
    ];

    render(<RecommendationsPanel recommendations={recommendations} totalEventsAnalyzed={100} />);

    // Check that high priority badge is shown in the category header (1 high priority item)
    expect(screen.getByText('1 high')).toBeInTheDocument();
    // Overall high priority badge
    expect(screen.getByText('1 High Priority')).toBeInTheDocument();
  });

  it('displays item count badge in category header', () => {
    const recommendations: AiAuditRecommendationItem[] = [
      {
        category: 'missing_context',
        suggestion: 'Test suggestion',
        frequency: 42,
        priority: 'medium',
      },
    ];

    render(<RecommendationsPanel recommendations={recommendations} totalEventsAnalyzed={100} />);

    // Item count is shown in the accordion header, not the body
    expect(screen.getByText('1 items')).toBeInTheDocument();
  });
});
