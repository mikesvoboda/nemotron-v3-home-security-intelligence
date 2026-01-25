/**
 * Tests for PromptTestModal component
 *
 * @see NEM-2698 - Implement prompt A/B testing UI with real inference comparison
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import PromptTestModal from './PromptTestModal';
import { AIModelEnum } from '../../../types/promptManagement';

// ============================================================================
// Mocks
// ============================================================================

// Mock the API functions
vi.mock('../../../services/api', () => ({
  fetchEvents: vi.fn().mockResolvedValue({
    items: [
      {
        id: 1234,
        camera_id: 'front_door',
        started_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        detection_count: 3,
        risk_level: 'high',
        risk_score: 72,
        reviewed: false,
      },
      {
        id: 1233,
        camera_id: 'backyard',
        started_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
        detection_count: 2,
        risk_level: 'medium',
        risk_score: 45,
        reviewed: true,
      },
    ],
    total_count: 2,
  }),
}));

vi.mock('../../../services/promptManagementApi', () => ({
  fetchPromptForModel: vi.fn().mockResolvedValue({
    model: 'nemotron',
    config: { system_prompt: 'You are a security analyst.' },
    version: 3,
    created_at: '2025-01-15T10:00:00Z',
  }),
  testPrompt: vi.fn().mockImplementation(() =>
    Promise.resolve({
      model: 'nemotron',
      before_score: 72,
      after_score: 85,
      before_response: {
        risk_level: 'high',
        reasoning: 'Original reasoning',
        summary: 'Original summary',
      },
      after_response: {
        risk_level: 'critical',
        reasoning: 'Modified reasoning',
        summary: 'Modified summary',
      },
      improved: false,
      test_duration_ms: 1200,
    })
  ),
  fetchPromptHistory: vi.fn().mockResolvedValue({ versions: [], total_count: 0 }),
  updatePromptForModel: vi.fn(),
  restorePromptVersion: vi.fn(),
}));

// ============================================================================
// Test Utilities
// ============================================================================

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return {
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
    queryClient,
  };
}

// ============================================================================
// Test Data
// ============================================================================

const modifiedConfig = {
  system_prompt: 'You are an enhanced security analyst.',
  temperature: 0.8,
};

// ============================================================================
// Tests
// ============================================================================

describe('PromptTestModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders when open', () => {
      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      expect(screen.getByText(/A\/B Test Configuration/i)).toBeInTheDocument();
    });

    it('does not render when closed', () => {
      renderWithProviders(
        <PromptTestModal
          isOpen={false}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      expect(screen.queryByText(/A\/B Test Configuration/i)).not.toBeInTheDocument();
    });

    it('displays Select Test Event section', () => {
      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      expect(screen.getByText(/Select Test Event/i)).toBeInTheDocument();
    });

    it('displays Run Test button', () => {
      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      expect(screen.getByRole('button', { name: /Run Test/i })).toBeInTheDocument();
    });

    it('displays rate limit warning', () => {
      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      expect(screen.getByText(/A\/B testing is rate-limited/i)).toBeInTheDocument();
    });

    it('displays Close button', () => {
      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      // There are two close buttons - the X in header and the Close button in footer
      const closeButtons = screen.getAllByRole('button', { name: /Close/i });
      expect(closeButtons.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('event loading', () => {
    it('loads and displays events', async () => {
      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Event #1234/i)).toBeInTheDocument();
        expect(screen.getByText(/Event #1233/i)).toBeInTheDocument();
      });
    });
  });

  describe('interactions', () => {
    it('calls onClose when Close button is clicked', async () => {
      const handleClose = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={handleClose}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      // Get all close buttons and click the footer one (last one)
      const closeButtons = screen.getAllByRole('button', { name: /Close/i });
      await user.click(closeButtons[closeButtons.length - 1]);

      expect(handleClose).toHaveBeenCalled();
    });

    it('calls onClose when X button is clicked', async () => {
      const handleClose = vi.fn();
      const user = userEvent.setup();

      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={handleClose}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      // Click the X button specifically (aria-label="Close")
      const closeButtons = screen.getAllByRole('button', { name: /Close/i });
      // The first one should be the X button in the header
      await user.click(closeButtons[0]);

      expect(handleClose).toHaveBeenCalled();
    });

    it('disables Run Test button when no event is selected', async () => {
      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      await waitFor(() => {
        const runButton = screen.getByRole('button', { name: /Run Test/i });
        expect(runButton).toBeDisabled();
      });
    });

    it('enables Run Test button when event is selected', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      // Wait for events to load
      await waitFor(() => {
        expect(screen.getByText(/Event #1234/i)).toBeInTheDocument();
      });

      // Select an event
      await user.click(screen.getByTestId('event-option-1234'));

      // Run Test button should be enabled
      await waitFor(() => {
        const runButton = screen.getByRole('button', { name: /Run Test/i });
        expect(runButton).not.toBeDisabled();
      });
    });
  });

  describe('test execution', () => {
    it('runs A/B test when Run Test is clicked', async () => {
      const user = userEvent.setup();
      const { testPrompt } = await import('../../../services/promptManagementApi');

      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      // Wait for events to load
      await waitFor(() => {
        expect(screen.getByText(/Event #1234/i)).toBeInTheDocument();
      });

      // Select an event
      await user.click(screen.getByTestId('event-option-1234'));

      // Click Run Test
      await user.click(screen.getByRole('button', { name: /Run Test/i }));

      // Wait for the test to run - testPrompt should be called twice
      await waitFor(() => {
        expect(testPrompt).toHaveBeenCalled();
      });
    });

    it('displays results after test completes', async () => {
      const user = userEvent.setup();

      renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      // Wait for events to load
      await waitFor(() => {
        expect(screen.getByText(/Event #1234/i)).toBeInTheDocument();
      });

      // Select an event
      await user.click(screen.getByTestId('event-option-1234'));

      // Click Run Test
      await user.click(screen.getByRole('button', { name: /Run Test/i }));

      // Wait for results to appear
      await waitFor(
        () => {
          expect(screen.getByText(/Results/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('state reset', () => {
    it('resets state when modal reopens', async () => {
      const user = userEvent.setup();

      const { rerender, queryClient } = renderWithProviders(
        <PromptTestModal
          isOpen={true}
          onClose={vi.fn()}
          model={AIModelEnum.NEMOTRON}
          modifiedConfig={modifiedConfig}
        />
      );

      // Wait for events and select one
      await waitFor(() => {
        expect(screen.getByText(/Event #1234/i)).toBeInTheDocument();
      });
      await user.click(screen.getByTestId('event-option-1234'));

      // Close the modal
      rerender(
        <QueryClientProvider client={queryClient}>
          <PromptTestModal
            isOpen={false}
            onClose={vi.fn()}
            model={AIModelEnum.NEMOTRON}
            modifiedConfig={modifiedConfig}
          />
        </QueryClientProvider>
      );

      // Reopen the modal
      rerender(
        <QueryClientProvider client={queryClient}>
          <PromptTestModal
            isOpen={true}
            onClose={vi.fn()}
            model={AIModelEnum.NEMOTRON}
            modifiedConfig={modifiedConfig}
          />
        </QueryClientProvider>
      );

      // Run Test should be disabled again (no event selected)
      await waitFor(() => {
        const runButton = screen.getByRole('button', { name: /Run Test/i });
        expect(runButton).toBeDisabled();
      });
    });
  });
});
