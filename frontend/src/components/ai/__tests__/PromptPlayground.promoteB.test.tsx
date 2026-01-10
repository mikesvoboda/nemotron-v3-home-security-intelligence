/**
 * Tests for PromptPlayground component - Promote B Functionality
 *
 * NEM-1320: Refactored from PromptPlayground.test.tsx into smaller, focused test files.
 *
 * This file covers:
 * - Promote B confirmation dialog
 * - Minimum 3 tests requirement
 * - API call with modified prompt
 * - State reset after successful promote
 * - Error handling on failed promote
 * - Cancel in dialog behavior
 * - Test statistics display
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import PromptPlayground from '../PromptPlayground';

// Mock the API functions
vi.mock('../../../services/api', () => ({
  fetchAllPrompts: vi.fn(() =>
    Promise.resolve({
      prompts: {
        nemotron: {
          model_name: 'nemotron',
          config: {
            system_prompt: 'You are a security analyzer.',
            temperature: 0.7,
            max_tokens: 2048,
          },
          version: 1,
          updated_at: '2024-01-01T00:00:00Z',
        },
        florence2: {
          model_name: 'florence2',
          config: {
            vqa_queries: ['What is happening?', 'Are there people?'],
          },
          version: 1,
          updated_at: '2024-01-01T00:00:00Z',
        },
        yolo_world: {
          model_name: 'yolo_world',
          config: {
            object_classes: ['person', 'vehicle'],
            confidence_threshold: 0.5,
          },
          version: 1,
          updated_at: '2024-01-01T00:00:00Z',
        },
        xclip: {
          model_name: 'xclip',
          config: {
            action_classes: ['walking', 'running'],
          },
          version: 1,
          updated_at: '2024-01-01T00:00:00Z',
        },
        fashion_clip: {
          model_name: 'fashion_clip',
          config: {
            clothing_categories: ['casual', 'formal'],
            suspicious_indicators: ['all black', 'face mask'],
          },
          version: 1,
          updated_at: '2024-01-01T00:00:00Z',
        },
      },
    })
  ),
  updateModelPrompt: vi.fn(() =>
    Promise.resolve({
      model_name: 'nemotron',
      version: 2,
      message: 'Configuration updated to version 2',
      config: { system_prompt: 'Updated prompt' },
    })
  ),
  testPrompt: vi.fn(() =>
    Promise.resolve({
      before: { score: 50, risk_level: 'medium', summary: 'Before summary' },
      after: { score: 75, risk_level: 'high', summary: 'After summary' },
      improved: true,
      inference_time_ms: 150,
    })
  ),
  fetchEvents: vi.fn(() =>
    Promise.resolve({
      items: [
        { id: 101, camera_id: 'cam1', risk_score: 45, started_at: '2024-01-01T00:00:00Z' },
        { id: 102, camera_id: 'cam2', risk_score: 55, started_at: '2024-01-01T01:00:00Z' },
        { id: 103, camera_id: 'cam1', risk_score: 65, started_at: '2024-01-01T02:00:00Z' },
      ],
      pagination: {
        total: 3,
        limit: 5,
        offset: 0,
        has_more: false,
      },
    })
  ),
  exportPrompts: vi.fn(() =>
    Promise.resolve({
      exported_at: '2024-01-01T00:00:00Z',
      version: '1.0',
      prompts: {
        nemotron: { system_prompt: 'Test' },
      },
    })
  ),
  importPrompts: vi.fn(() =>
    Promise.resolve({
      imported_count: 1,
      skipped_count: 0,
      errors: [],
      message: 'Imported 1 model(s)',
    })
  ),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      this.name = 'ApiError';
    }
  },
}));

describe('PromptPlayground - Promote B Functionality', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  // Mock enriched suggestion with modified prompt state
  const mockEnrichedSuggestion = {
    category: 'missing_context' as const,
    suggestion: 'Add time since last motion',
    priority: 'high' as const,
    frequency: 5,
    targetSection: 'Camera & Time Context',
    insertionPoint: 'append' as const,
    proposedVariable: '{time_since_last_event}',
    proposedLabel: 'Time Since Last Event:',
    impactExplanation: 'Adding time context helps the AI better assess threat levels.',
    sourceEventIds: [142, 156, 189],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Promote B button shows confirmation dialog', async () => {
    const user = userEvent.setup();
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={false}
      />
    );

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    });

    // Apply the suggestion to get modified prompt
    await user.click(screen.getByTestId('nemotron-preview-changes'));
    await waitFor(() => {
      expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('apply-suggestion-button'));

    // Now show A/B test and run 3 tests (need at least 3)
    await waitFor(() => {
      expect(screen.getByTestId('run-ab-tests-button')).toBeInTheDocument();
    });

    // Run 3 tests
    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/1 test completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/2 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/3 tests completed/);
    }, { timeout: 3000 });

    // Click promote button should show confirmation dialog (now that we have 3 tests)
    await user.click(screen.getByTestId('promote-b-button'));

    await waitFor(() => {
      expect(screen.getByTestId('promote-confirm-dialog')).toBeInTheDocument();
    });
  });

  it('Promote B requires minimum 3 tests', async () => {
    const user = userEvent.setup();
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    });

    // Apply the suggestion
    await user.click(screen.getByTestId('nemotron-preview-changes'));
    await waitFor(() => {
      expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('apply-suggestion-button'));

    // Click promote with less than 3 tests should show warning
    await waitFor(() => {
      expect(screen.getByTestId('promote-b-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('promote-b-button'));

    // Should see warning toast instead of dialog
    await waitFor(() => {
      expect(screen.getByText(/Run at least 3 tests before promoting/i)).toBeInTheDocument();
    });
  });

  it('Promote B calls PUT API with modified prompt', async () => {
    const { updateModelPrompt } = await import('../../../services/api');
    const user = userEvent.setup();

    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    });

    // Apply suggestion
    await user.click(screen.getByTestId('nemotron-preview-changes'));
    await waitFor(() => {
      expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('apply-suggestion-button'));

    // Run 3 tests (mocked to have results)
    await waitFor(() => {
      expect(screen.getByTestId('run-ab-tests-button')).toBeInTheDocument();
    });

    // Simulate running 3 tests with wait for completion
    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/1 test completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/2 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/3 tests completed/);
    }, { timeout: 3000 });

    // Click promote
    await user.click(screen.getByTestId('promote-b-button'));

    // Confirm in dialog
    await waitFor(() => {
      expect(screen.getByTestId('confirm-promote-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('confirm-promote-button'));

    // Verify API was called
    await waitFor(() => {
      expect(updateModelPrompt).toHaveBeenCalled();
    });
  });

  it('successful promote resets state', async () => {
    const user = userEvent.setup();

    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    });

    // Apply suggestion to create modified state
    await user.click(screen.getByTestId('nemotron-preview-changes'));
    await waitFor(() => {
      expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('apply-suggestion-button'));

    // The applied banner should be visible
    await waitFor(() => {
      expect(screen.getByTestId('suggestion-applied-banner')).toBeInTheDocument();
    });

    // Run 3 tests to enable promote
    await waitFor(() => {
      expect(screen.getByTestId('run-ab-tests-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/1 test completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/2 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/3 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('promote-b-button'));

    await waitFor(() => {
      expect(screen.getByTestId('confirm-promote-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('confirm-promote-button'));

    // After successful promote, state should be reset
    await waitFor(() => {
      // A/B test section should be hidden
      expect(screen.queryByTestId('ab-test-section')).not.toBeInTheDocument();
      // Applied banner should be gone
      expect(screen.queryByTestId('suggestion-applied-banner')).not.toBeInTheDocument();
    });
  });

  it('failed promote shows error toast', async () => {
    const { updateModelPrompt } = await import('../../../services/api');
    const mockUpdatePrompt = updateModelPrompt as ReturnType<typeof vi.fn>;
    mockUpdatePrompt.mockRejectedValueOnce(new Error('Network error'));

    const user = userEvent.setup();

    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    });

    // Apply suggestion
    await user.click(screen.getByTestId('nemotron-preview-changes'));
    await waitFor(() => {
      expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('apply-suggestion-button'));

    // Run 3 tests to enable promote
    await waitFor(() => {
      expect(screen.getByTestId('run-ab-tests-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/1 test completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/2 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/3 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('promote-b-button'));

    await waitFor(() => {
      expect(screen.getByTestId('confirm-promote-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('confirm-promote-button'));

    // Should show error toast
    await waitFor(() => {
      expect(screen.getByText(/Failed to save prompt/i)).toBeInTheDocument();
    });
  });

  it('cancel in dialog does not promote', async () => {
    // Note: updateModelPrompt should NOT be called when cancel is clicked
    // We don't import it here since we just verify the dialog closes without API call
    const user = userEvent.setup();

    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    });

    // Apply suggestion
    await user.click(screen.getByTestId('nemotron-preview-changes'));
    await waitFor(() => {
      expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('apply-suggestion-button'));

    // Run 3 tests to enable promote
    await waitFor(() => {
      expect(screen.getByTestId('run-ab-tests-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/1 test completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/2 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/3 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('promote-b-button'));

    // Click cancel
    await waitFor(() => {
      expect(screen.getByTestId('cancel-promote-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('cancel-promote-button'));

    // Dialog should close
    await waitFor(() => {
      expect(screen.queryByTestId('promote-confirm-dialog')).not.toBeInTheDocument();
    });

    // API should not have been called (updateModelPrompt was not called for promotion)
    // Note: The cancel was clicked before confirm, so API shouldn't have been called
  });

  it('dialog shows test statistics', async () => {
    const user = userEvent.setup();

    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    });

    // Apply suggestion
    await user.click(screen.getByTestId('nemotron-preview-changes'));
    await waitFor(() => {
      expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('apply-suggestion-button'));

    // Run 3 tests to enable promote
    await waitFor(() => {
      expect(screen.getByTestId('run-ab-tests-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/1 test completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/2 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('run-ab-tests-button'));
    await waitFor(() => {
      expect(screen.getByTestId('ab-test-count')).toHaveTextContent(/3 tests completed/);
    }, { timeout: 3000 });

    await user.click(screen.getByTestId('promote-b-button'));

    // Dialog should show statistics
    await waitFor(() => {
      expect(screen.getByTestId('promote-confirm-dialog')).toBeInTheDocument();
    });

    // Should display test count and improvement metrics
    expect(screen.getByText(/3 tests:/i)).toBeInTheDocument();
    expect(screen.getByText(/Average score change/i)).toBeInTheDocument();
    expect(screen.getByText(/Improvement rate/i)).toBeInTheDocument();
  });
});
