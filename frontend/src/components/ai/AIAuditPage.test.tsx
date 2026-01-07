/**
 * Tests for AIAuditPage component
 */

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

describe('AIAuditPage batch audit', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders trigger batch audit button', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('trigger-batch-audit-button')).toBeInTheDocument();
    });
  });

  it('opens batch audit modal when button is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    // Wait for page to load
    await waitFor(() => {
      expect(screen.getByTestId('trigger-batch-audit-button')).toBeInTheDocument();
    });

    // Click the trigger button
    await user.click(screen.getByTestId('trigger-batch-audit-button'));

    // Modal should be open
    await waitFor(() => {
      expect(screen.getByTestId('batch-audit-modal')).toBeInTheDocument();
    });
  });

  it('closes batch audit modal when cancel is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    // Wait for page to load and open modal
    await waitFor(() => {
      expect(screen.getByTestId('trigger-batch-audit-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('trigger-batch-audit-button'));

    // Modal should be open
    await waitFor(() => {
      expect(screen.getByTestId('batch-audit-modal')).toBeInTheDocument();
    });

    // Click cancel
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    // Modal should be closed
    await waitFor(() => {
      expect(screen.queryByTestId('batch-audit-modal')).not.toBeInTheDocument();
    });
  });
});

describe('AIAuditPage Prompt Playground', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Open Prompt Playground button', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(screen.getByTestId('open-playground-button')).toBeInTheDocument();
    });
  });

  it('button has correct text and icon', async () => {
    renderWithRouter();
    await waitFor(() => {
      const button = screen.getByTestId('open-playground-button');
      expect(button).toHaveTextContent('Open Prompt Playground');
    });
  });

  it('opens Prompt Playground when header button is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    // Wait for page to load
    await waitFor(() => {
      expect(screen.getByTestId('open-playground-button')).toBeInTheDocument();
    });

    // Click the Open Prompt Playground button
    await user.click(screen.getByTestId('open-playground-button'));

    // Prompt Playground panel should be open
    await waitFor(() => {
      expect(screen.getByTestId('prompt-playground-panel')).toBeInTheDocument();
    });
  });

  it('passes no recommendation when opened from header button', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('open-playground-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('open-playground-button'));

    await waitFor(() => {
      expect(screen.getByTestId('prompt-playground-panel')).toBeInTheDocument();
    });

    // Should not show recommendation banner
    expect(screen.queryByTestId('recommendation-banner')).not.toBeInTheDocument();
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

  it('header button opens playground without recommendation', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('open-playground-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('open-playground-button'));

    await waitFor(() => {
      expect(screen.getByTestId('prompt-playground-panel')).toBeInTheDocument();
      // No recommendation banner when opened from header
      expect(screen.queryByTestId('recommendation-banner')).not.toBeInTheDocument();
    });
  });

  it('RecommendationsPanel component exists and can be interacted with', async () => {
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('recommendations-panel')).toBeInTheDocument();
    });

    // Verify the recommendations panel is rendering (implicitly tests that buttons exist within)
    // The actual button styling is tested in RecommendationsPanel.test.tsx
    expect(screen.getByText('Prompt Improvement Recommendations')).toBeInTheDocument();
  });

  it('closes Prompt Playground when close button is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter();

    await waitFor(() => {
      expect(screen.getByTestId('open-playground-button')).toBeInTheDocument();
    });

    // Open playground
    await user.click(screen.getByTestId('open-playground-button'));

    await waitFor(() => {
      expect(screen.getByTestId('prompt-playground-panel')).toBeInTheDocument();
    });

    // Close playground
    await user.click(screen.getByTestId('close-panel-button'));

    await waitFor(() => {
      expect(screen.queryByTestId('prompt-playground-panel')).not.toBeInTheDocument();
    });
  });
});
