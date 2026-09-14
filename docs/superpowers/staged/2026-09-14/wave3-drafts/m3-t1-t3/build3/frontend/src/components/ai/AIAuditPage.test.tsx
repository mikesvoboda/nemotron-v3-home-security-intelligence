/**
 * Tests for AIAuditPage component
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import AIAuditPage from './AIAuditPage';

// Mock the auditApi functions
vi.mock('../../services/auditApi', () => ({
  triggerBatchAudit: vi.fn(),
  AuditApiError: class AuditApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      this.name = 'AuditApiError';
    }
  },
}));

// Mock the API functions
vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
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
  };
});

// Mock the useAIAuditPromptHistoryQuery hook for version history tab
vi.mock('../../hooks/useAIAuditQueries', () => ({
  useAIAuditPromptHistoryQuery: vi.fn(() => ({
    data: {
      versions: [],
      total_count: 0,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

// Mock the promptManagementApi
vi.mock('../../services/promptManagementApi', () => ({
  restorePromptVersion: vi.fn(),
  PromptApiError: class PromptApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      this.name = 'PromptApiError';
    }
  },
}));

// Create a test wrapper
const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function TestWrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
};

const renderWithRouter = () => {
  return render(<AIAuditPage />, { wrapper: createTestWrapper() });
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
        screen.getByText(
          /Model contribution rates, quality metrics, and prompt improvement recommendations/
        )
      ).toBeInTheDocument();
    });
  });

  it('renders the refresh button', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('ai-audit-refresh-button')).toBeInTheDocument();
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

describe('AIAuditPage tabbed interface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders tabs container', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('ai-audit-tabs')).toBeInTheDocument();
    });
  });

  it('renders all four tabs', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('tab-dashboard')).toBeInTheDocument();
      expect(screen.getByTestId('tab-playground')).toBeInTheDocument();
      expect(screen.getByTestId('tab-batch')).toBeInTheDocument();
      expect(screen.getByTestId('tab-history')).toBeInTheDocument();
    });
  });

  it('dashboard tab is selected by default', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('tab-panel-dashboard')).toBeInTheDocument();
    });
  });

  it('switches to Prompt Playground tab when clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-playground')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-playground'));

    await waitFor(() => {
      expect(screen.getByTestId('tab-panel-playground')).toBeInTheDocument();
    });
  });

  it('switches to Batch Audit tab when clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-batch')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-batch'));

    await waitFor(() => {
      expect(screen.getByTestId('tab-panel-batch')).toBeInTheDocument();
    });
  });

  it('switches to Version History tab when clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-history')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-history'));

    await waitFor(() => {
      expect(screen.getByTestId('tab-panel-history')).toBeInTheDocument();
    });
  });
});

describe('AIAuditPage Prompt Playground tab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Open Prompt Playground button in playground tab', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-playground')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-playground'));

    await waitFor(() => {
      expect(screen.getByTestId('open-playground-button')).toBeInTheDocument();
    });
  });

  it('button has correct text', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-playground')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-playground'));

    await waitFor(() => {
      const button = screen.getByTestId('open-playground-button');
      expect(button).toHaveTextContent('Open Prompt Playground');
    });
  });

  it('shows feature highlights in playground tab', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-playground')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-playground'));

    await waitFor(() => {
      expect(screen.getByText('Model Editors')).toBeInTheDocument();
      expect(screen.getByText('A/B Testing')).toBeInTheDocument();
      expect(screen.getByText('Import/Export')).toBeInTheDocument();
    });
  });

  it('opens Prompt Playground when button is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-playground')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-playground'));

    await waitFor(() => {
      expect(screen.getByTestId('open-playground-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('open-playground-button'));

    // Prompt Playground panel should be open
    await waitFor(() => {
      expect(screen.getByTestId('prompt-playground-panel')).toBeInTheDocument();
    });
  });
});

describe('AIAuditPage Batch Audit tab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders trigger batch audit button in batch tab', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-batch')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-batch'));

    await waitFor(() => {
      expect(screen.getByTestId('trigger-batch-audit-button')).toBeInTheDocument();
    });
  });

  it('opens batch audit modal when button is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-batch')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-batch'));

    await waitFor(() => {
      expect(screen.getByTestId('trigger-batch-audit-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('trigger-batch-audit-button'));

    // Modal should be open
    await waitFor(() => {
      expect(screen.getByTestId('batch-audit-modal')).toBeInTheDocument();
    });
  });

  it('shows batch stats in batch tab', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-batch')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-batch'));

    await waitFor(() => {
      expect(screen.getByText('Total Events')).toBeInTheDocument();
      expect(screen.getByText('Audited Events')).toBeInTheDocument();
      expect(screen.getByText('Fully Evaluated')).toBeInTheDocument();
    });
  });
});

describe('AIAuditPage Version History tab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders version history component in history tab', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-history')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-history'));

    await waitFor(() => {
      expect(screen.getByTestId('prompt-version-history')).toBeInTheDocument();
    });
  });

  it('shows version history title in history tab', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('tab-history')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('tab-history'));

    await waitFor(() => {
      expect(screen.getByText('Prompt Version History')).toBeInTheDocument();
    });
  });
});

describe('AIAuditPage recommendations integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('RecommendationsPanel component exists and can be interacted with', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('recommendations-panel')).toBeInTheDocument();
    });

    // Verify the recommendations panel is rendering
    expect(screen.getByText('Prompt Improvement Recommendations')).toBeInTheDocument();
  });

  it('recommendations panel renders with proper structure', async () => {
    renderWithRouter();

    // Wait for recommendations to load
    await waitFor(() => {
      expect(screen.getByTestId('recommendations-panel')).toBeInTheDocument();
    });

    // Verify the panel has recommendations accordion
    expect(screen.getByTestId('recommendations-accordion')).toBeInTheDocument();
  });
});

describe('AIAuditPage new features', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders model contribution chart section', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('model-contribution-chart')).toBeInTheDocument();
    });
  });

  it('displays empty state when no data available', async () => {
    // Override with empty stats response for this test
    const api = await import('../../services/api');
    vi.mocked(api.fetchAiAuditStats).mockReset().mockResolvedValue({
      total_events: 0,
      audited_events: 0,
      fully_evaluated_events: 0,
      avg_quality_score: null,
      avg_consistency_rate: null,
      avg_enrichment_utilization: null,
      model_contribution_rates: {},
      audits_by_day: [],
    });

    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByText(/no events have been audited yet/i)).toBeInTheDocument();
    });
  });

  it('shows trigger batch audit CTA in empty state', async () => {
    // Override with empty stats response for this test
    const api = await import('../../services/api');
    vi.mocked(api.fetchAiAuditStats).mockReset().mockResolvedValue({
      total_events: 0,
      audited_events: 0,
      fully_evaluated_events: 0,
      avg_quality_score: null,
      avg_consistency_rate: null,
      avg_enrichment_utilization: null,
      model_contribution_rates: {},
      audits_by_day: [],
    });

    renderWithRouter();

    // Wait for loading to complete and empty state to render
    await waitFor(() => {
      expect(screen.getByText(/no events have been audited yet/i)).toBeInTheDocument();
    });

    // Find the batch audit button by text
    const batchAuditButtons = screen.getAllByRole('button', { name: /trigger batch audit/i });
    expect(batchAuditButtons.length).toBeGreaterThanOrEqual(1);
  });
});
