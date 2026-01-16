/**
 * Tests for AIAuditDashboard component
 *
 * Tests comprehensive AI audit dashboard functionality including:
 * - Quality metrics cards rendering
 * - Model leaderboard display
 * - Recommendations panel functionality
 * - Recent evaluations table
 * - Loading states and error handling
 * - Refresh functionality
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import AIAuditDashboard from './AIAuditDashboard';
import {
  fetchAiAuditStats,
  fetchModelLeaderboard,
  fetchAuditRecommendations,
} from '../../services/api';

import type {
  AiAuditStatsResponse,
  AiAuditLeaderboardResponse,
  AiAuditRecommendationsResponse,
} from '../../services/api';

// ============================================================================
// Mock Data
// ============================================================================

const mockStats: AiAuditStatsResponse = {
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
};

const mockLeaderboard: AiAuditLeaderboardResponse = {
  entries: [
    { model_name: 'rtdetr', contribution_rate: 1.0, quality_correlation: 0.85, event_count: 1000 },
    {
      model_name: 'florence',
      contribution_rate: 0.85,
      quality_correlation: 0.72,
      event_count: 850,
    },
    {
      model_name: 'image_quality',
      contribution_rate: 0.7,
      quality_correlation: 0.68,
      event_count: 700,
    },
    { model_name: 'zones', contribution_rate: 0.65, quality_correlation: 0.61, event_count: 650 },
    { model_name: 'clip', contribution_rate: 0.6, quality_correlation: 0.55, event_count: 600 },
  ],
  period_days: 7,
};

const mockRecommendations: AiAuditRecommendationsResponse = {
  recommendations: [
    {
      category: 'missing_context',
      suggestion: 'Add time since last motion event to prompt',
      frequency: 50,
      priority: 'high',
    },
    {
      category: 'unused_data',
      suggestion: 'Weather data not used for indoor cameras',
      frequency: 30,
      priority: 'medium',
    },
    {
      category: 'model_gaps',
      suggestion: 'Enable pet detection for backyard cameras',
      frequency: 15,
      priority: 'low',
    },
  ],
  total_events_analyzed: 800,
};

const mockEmptyStats: AiAuditStatsResponse = {
  total_events: 0,
  audited_events: 0,
  fully_evaluated_events: 0,
  avg_quality_score: null,
  avg_consistency_rate: null,
  avg_enrichment_utilization: null,
  model_contribution_rates: {},
  audits_by_day: [],
};

const mockEmptyLeaderboard: AiAuditLeaderboardResponse = {
  entries: [],
  period_days: 7,
};

const mockEmptyRecommendations: AiAuditRecommendationsResponse = {
  recommendations: [],
  total_events_analyzed: 0,
};

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../../services/api', () => ({
  fetchAiAuditStats: vi.fn(),
  fetchModelLeaderboard: vi.fn(),
  fetchAuditRecommendations: vi.fn(),
}));

const mockFetchAiAuditStats = vi.mocked(fetchAiAuditStats);
const mockFetchAuditLeaderboard = vi.mocked(fetchModelLeaderboard);
const mockFetchAuditRecommendations = vi.mocked(fetchAuditRecommendations);

// ============================================================================
// Helper Functions
// ============================================================================

const renderWithRouter = (props = {}) => {
  return render(
    <MemoryRouter>
      <AIAuditDashboard {...props} />
    </MemoryRouter>
  );
};

// ============================================================================
// Tests
// ============================================================================

describe('AIAuditDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchAiAuditStats.mockResolvedValue(mockStats);
    mockFetchAuditLeaderboard.mockResolvedValue(mockLeaderboard);
    mockFetchAuditRecommendations.mockResolvedValue(mockRecommendations);
  });

  describe('rendering', () => {
    it('renders the dashboard container', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('ai-audit-dashboard')).toBeInTheDocument();
      });
    });

    it('renders the dashboard title', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('AI Audit Dashboard')).toBeInTheDocument();
      });
    });

    it('renders the refresh button', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
      });
    });

    it('displays period days in description', async () => {
      renderWithRouter({ periodDays: 14 });

      await waitFor(() => {
        expect(screen.getByText(/last 14 days/i)).toBeInTheDocument();
      });
    });
  });

  describe('loading states', () => {
    it('shows loading skeletons while fetching data', async () => {
      // Delay the response to see loading state
      mockFetchAiAuditStats.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockStats), 100))
      );
      mockFetchAuditLeaderboard.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockLeaderboard), 100))
      );
      mockFetchAuditRecommendations.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockRecommendations), 100))
      );

      renderWithRouter();

      // Should show loading skeletons initially
      expect(screen.getByTestId('quality-metrics-loading')).toBeInTheDocument();
      expect(screen.getByTestId('model-leaderboard-loading')).toBeInTheDocument();
      expect(screen.getByTestId('recommendations-panel-loading')).toBeInTheDocument();
      expect(screen.getByTestId('recent-evaluations-loading')).toBeInTheDocument();

      // Wait for data to load
      await waitFor(() => {
        expect(screen.queryByTestId('quality-metrics-loading')).not.toBeInTheDocument();
      });
    });
  });

  describe('quality metrics cards', () => {
    it('renders all quality metrics cards', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('quality-metrics-cards')).toBeInTheDocument();
      });

      expect(screen.getByTestId('total-evaluations-card')).toBeInTheDocument();
      expect(screen.getByTestId('avg-quality-card')).toBeInTheDocument();
      expect(screen.getByTestId('model-accuracy-card')).toBeInTheDocument();
      expect(screen.getByTestId('processing-times-card')).toBeInTheDocument();
    });

    it('displays total evaluations count', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('800')).toBeInTheDocument(); // fully_evaluated_events
      });
    });

    it('displays average quality score', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('4.2 / 5')).toBeInTheDocument();
      });
    });

    it('displays enrichment utilization percentage', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('75%')).toBeInTheDocument();
      });
    });

    it('displays evaluation coverage percentage', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('80%')).toBeInTheDocument(); // 800/1000 = 80%
      });
    });
  });

  describe('model leaderboard', () => {
    it('renders model leaderboard section', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('model-leaderboard')).toBeInTheDocument();
      });
    });

    it('renders leaderboard table', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('leaderboard-table')).toBeInTheDocument();
      });
    });

    it('displays leaderboard entries sorted by contribution', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('leaderboard-row-rtdetr')).toBeInTheDocument();
      });

      expect(screen.getByTestId('leaderboard-row-florence')).toBeInTheDocument();
      expect(screen.getByTestId('leaderboard-row-image_quality')).toBeInTheDocument();
    });

    it('displays model names with human-readable labels', async () => {
      renderWithRouter();

      await waitFor(() => {
        // Use getAllByText since model names may appear in multiple places
        // (leaderboard table and recent evaluations table)
        expect(screen.getAllByText('RT-DETR').length).toBeGreaterThan(0);
      });
      expect(screen.getAllByText('Florence-2').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Image Quality').length).toBeGreaterThan(0);
    });

    it('displays contribution percentages', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('100%')).toBeInTheDocument();
      });
      expect(screen.getByText('85%')).toBeInTheDocument();
    });

    it('displays rank badges for top 3 models', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('1st')).toBeInTheDocument();
      });
      expect(screen.getByText('2nd')).toBeInTheDocument();
      expect(screen.getByText('3rd')).toBeInTheDocument();
    });

    it('displays period days in leaderboard header', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Last 7 days')).toBeInTheDocument();
      });
    });

    it('shows empty state when no leaderboard data', async () => {
      mockFetchAuditLeaderboard.mockResolvedValue(mockEmptyLeaderboard);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText(/no leaderboard data/i)).toBeInTheDocument();
      });
    });
  });

  describe('recommendations panel', () => {
    it('renders recommendations panel section', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('recommendations-panel')).toBeInTheDocument();
      });
    });

    it('displays recommendations list', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('recommendations-list')).toBeInTheDocument();
      });
    });

    it('displays recommendation items', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('recommendation-item-0')).toBeInTheDocument();
      });
      expect(screen.getByTestId('recommendation-item-1')).toBeInTheDocument();
      expect(screen.getByTestId('recommendation-item-2')).toBeInTheDocument();
    });

    it('displays recommendation suggestions', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Add time since last motion event to prompt')).toBeInTheDocument();
      });
      expect(screen.getByText('Weather data not used for indoor cameras')).toBeInTheDocument();
    });

    it('displays priority badges', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('high')).toBeInTheDocument();
      });
      expect(screen.getByText('medium')).toBeInTheDocument();
      expect(screen.getByText('low')).toBeInTheDocument();
    });

    it('displays high priority count badge', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('1 High Priority')).toBeInTheDocument();
      });
    });

    it('displays total events analyzed', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('From 800 events')).toBeInTheDocument();
      });
    });

    it('shows empty state when no recommendations', async () => {
      mockFetchAuditRecommendations.mockResolvedValue(mockEmptyRecommendations);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText(/no recommendations available/i)).toBeInTheDocument();
      });
    });

    it('renders apply buttons for recommendations', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('apply-recommendation-0')).toBeInTheDocument();
      });
    });

    it('apply button is clickable without error', async () => {
      const user = userEvent.setup();

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('apply-recommendation-0')).toBeInTheDocument();
      });

      // Click should not throw - handler is a placeholder for future functionality
      await user.click(screen.getByTestId('apply-recommendation-0'));

      // Verify button is still in document after click (no error occurred)
      expect(screen.getByTestId('apply-recommendation-0')).toBeInTheDocument();
    });
  });

  describe('recent evaluations table', () => {
    it('renders recent evaluations section', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('recent-evaluations')).toBeInTheDocument();
      });
    });

    it('renders evaluations table', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('evaluations-table')).toBeInTheDocument();
      });
    });

    it('shows empty state when no evaluations', async () => {
      // When stats show no evaluations, we get the main empty state instead
      // The recent evaluations component only shows its empty state when
      // there's other data but no evaluations specifically
      // Let's test a scenario with some data but no fully evaluated events
      const statsWithNoEvaluations: AiAuditStatsResponse = {
        ...mockStats,
        fully_evaluated_events: 0,
        model_contribution_rates: {},
      };
      mockFetchAiAuditStats.mockResolvedValue(statsWithNoEvaluations);

      renderWithRouter();

      await waitFor(() => {
        // When fully_evaluated_events is 0, recent evaluations shows empty state
        expect(screen.getByText(/no recent evaluations/i)).toBeInTheDocument();
      });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no audit data', async () => {
      mockFetchAiAuditStats.mockResolvedValue(mockEmptyStats);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      });
    });

    it('displays empty state message', async () => {
      mockFetchAiAuditStats.mockResolvedValue(mockEmptyStats);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('No Audit Data Available')).toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('shows error state when API fails', async () => {
      mockFetchAiAuditStats.mockRejectedValue(new Error('Network error'));

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('ai-audit-dashboard-error')).toBeInTheDocument();
      });
    });

    it('displays error message', async () => {
      mockFetchAiAuditStats.mockRejectedValue(new Error('Network error'));

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('displays retry button on error', async () => {
      mockFetchAiAuditStats.mockRejectedValue(new Error('Network error'));

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('retry-button')).toBeInTheDocument();
      });
    });

    it('retries loading when retry button is clicked', async () => {
      const user = userEvent.setup();
      mockFetchAiAuditStats.mockRejectedValueOnce(new Error('Network error'));
      mockFetchAiAuditStats.mockResolvedValueOnce(mockStats);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('retry-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('retry-button'));

      await waitFor(() => {
        expect(screen.getByTestId('ai-audit-dashboard')).toBeInTheDocument();
      });

      expect(mockFetchAiAuditStats).toHaveBeenCalledTimes(2);
    });
  });

  describe('refresh functionality', () => {
    it('refreshes data when refresh button is clicked', async () => {
      const user = userEvent.setup();

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('refresh-button'));

      await waitFor(() => {
        expect(mockFetchAiAuditStats).toHaveBeenCalledTimes(2);
      });
    });

    it('disables refresh button while refreshing', async () => {
      const user = userEvent.setup();

      // Make the API call slow
      mockFetchAiAuditStats.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockStats), 200))
      );

      renderWithRouter();

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('refresh-button')).toBeEnabled();
      });

      // Click refresh
      await user.click(screen.getByTestId('refresh-button'));

      // Button should be disabled during refresh
      expect(screen.getByTestId('refresh-button')).toBeDisabled();

      // Wait for refresh to complete
      await waitFor(() => {
        expect(screen.getByTestId('refresh-button')).toBeEnabled();
      });
    });
  });

  describe('API calls', () => {
    it('calls API with correct period days', async () => {
      renderWithRouter({ periodDays: 30 });

      await waitFor(() => {
        expect(mockFetchAiAuditStats).toHaveBeenCalledWith({ days: 30 });
      });

      expect(mockFetchAuditLeaderboard).toHaveBeenCalledWith({ days: 30 });
      expect(mockFetchAuditRecommendations).toHaveBeenCalledWith({ days: 30 });
    });

    it('uses default period of 7 days', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(mockFetchAiAuditStats).toHaveBeenCalledWith({ days: 7 });
      });
    });

    it('refetches when periodDays prop changes', async () => {
      const { rerender } = render(
        <MemoryRouter>
          <AIAuditDashboard periodDays={7} />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(mockFetchAiAuditStats).toHaveBeenCalledWith({ days: 7 });
      });

      rerender(
        <MemoryRouter>
          <AIAuditDashboard periodDays={14} />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(mockFetchAiAuditStats).toHaveBeenCalledWith({ days: 14 });
      });
    });
  });

  describe('accessibility', () => {
    it('has appropriate heading structure', async () => {
      renderWithRouter();

      await waitFor(() => {
        const headings = screen.getAllByRole('heading');
        expect(headings.length).toBeGreaterThan(0);
      });
    });

    it('renders tables with proper structure', async () => {
      renderWithRouter();

      await waitFor(() => {
        const tables = screen.getAllByRole('table');
        expect(tables.length).toBeGreaterThan(0);
      });
    });

    it('provides button labels for interactive elements', async () => {
      renderWithRouter();

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        expect(refreshButton).toHaveTextContent('Refresh');
      });
    });
  });

  describe('styling', () => {
    it('applies custom className when provided', async () => {
      renderWithRouter({ className: 'custom-class' });

      await waitFor(() => {
        expect(screen.getByTestId('ai-audit-dashboard')).toHaveClass('custom-class');
      });
    });
  });
});
