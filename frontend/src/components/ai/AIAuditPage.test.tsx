/**
 * Tests for AIAuditPage component
 */

import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import AIAuditPage from './AIAuditPage';

// Mock the API functions
vi.mock('../../services/api', () => ({
  fetchAiAuditStats: vi.fn(() =>
    Promise.resolve({
      total_events: 1000,
      audited_events: 950,
      fully_evaluated_events: 800,
      avg_quality_score: 4.2,
      avg_consistency_rate: 4.0,
      avg_enrichment_utilization: 0.75,
      model_contribution_rates: {
        rtdetr: 1.0,
        florence: 0.85,
        clip: 0.6,
        violence: 0.3,
        clothing: 0.5,
        vehicle: 0.4,
        pet: 0.25,
        weather: 0.2,
        image_quality: 0.7,
        zones: 0.65,
        baseline: 0.55,
        cross_camera: 0.15,
      },
      audits_by_day: [],
    })
  ),
  fetchModelLeaderboard: vi.fn(() =>
    Promise.resolve({
      entries: [
        { model_name: 'rtdetr', contribution_rate: 1.0, quality_correlation: null, event_count: 1000 },
        { model_name: 'florence', contribution_rate: 0.85, quality_correlation: null, event_count: 850 },
        { model_name: 'image_quality', contribution_rate: 0.7, quality_correlation: null, event_count: 700 },
      ],
      period_days: 7,
    })
  ),
  fetchAuditRecommendations: vi.fn(() =>
    Promise.resolve({
      recommendations: [
        {
          category: 'missing_context',
          suggestion: 'Add time since last motion',
          frequency: 50,
          priority: 'high',
        },
        {
          category: 'unused_data',
          suggestion: 'Weather data not used for indoor cameras',
          frequency: 30,
          priority: 'medium',
        },
      ],
      total_events_analyzed: 800,
    })
  ),
}));

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <AIAuditPage />
    </MemoryRouter>
  );
};

describe('AIAuditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page title', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByText('AI Audit Dashboard')).toBeInTheDocument();
    });
  });

  it('renders the page description', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(
        screen.getByText(/Model contribution rates, quality metrics, and prompt improvement recommendations/)
      ).toBeInTheDocument();
    });
  });

  it('renders the refresh button', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
    });
  });

  it('renders the period selector', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('period-selector')).toBeInTheDocument();
    });
  });

  it('renders quality score trends section', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('quality-score-trends')).toBeInTheDocument();
    });
  });

  it('renders model contribution chart', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('model-contribution-chart')).toBeInTheDocument();
    });
  });

  it('renders model leaderboard', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('model-leaderboard')).toBeInTheDocument();
    });
  });

  it('renders recommendations panel', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('recommendations-panel')).toBeInTheDocument();
    });
  });

  it('has correct data-testid for the page', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('ai-audit-page')).toBeInTheDocument();
    });
  });
});

describe('AIAuditPage quality metrics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays average quality score card', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('quality-score-card')).toBeInTheDocument();
    });
  });

  it('displays consistency rate card', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('consistency-rate-card')).toBeInTheDocument();
    });
  });

  it('displays enrichment utilization card', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('enrichment-utilization-card')).toBeInTheDocument();
    });
  });

  it('displays evaluation coverage card', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('evaluation-coverage-card')).toBeInTheDocument();
    });
  });
});
