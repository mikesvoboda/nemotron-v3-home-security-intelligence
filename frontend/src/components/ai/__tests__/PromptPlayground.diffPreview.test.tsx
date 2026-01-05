/**
 * Tests for PromptPlayground component - Diff Preview
 *
 * NEM-1320: Refactored from PromptPlayground.test.tsx into smaller, focused test files.
 *
 * This file covers:
 * - Diff preview display with suggestions
 * - Apply button functionality
 * - Dismiss button functionality
 * - Unsaved changes after applying suggestion
 * - Preview Changes button
 * - SuggestionExplanation rendering
 * - Event click handling
 * - showTips localStorage preference
 * - Explanation positioning
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

// Mock localStorage for useLocalStorage hook
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('PromptPlayground - Diff Preview', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  // Create an enriched suggestion for testing
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
    localStorageMock.clear();
  });

  it('shows diff preview when suggestion is active', async () => {
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('diff-preview-section')).toBeInTheDocument();
    });

    // Should show the suggestion diff view
    expect(screen.getByTestId('suggestion-diff-view')).toBeInTheDocument();
    // Should show Apply and Dismiss buttons
    expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    expect(screen.getByTestId('dismiss-suggestion-button')).toBeInTheDocument();
  });

  it('Apply button applies changes to prompt', async () => {
    const user = userEvent.setup();
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    });

    // Click Apply
    await user.click(screen.getByTestId('apply-suggestion-button'));

    // Diff preview should close
    await waitFor(() => {
      expect(screen.queryByTestId('diff-preview-section')).not.toBeInTheDocument();
    });

    // Applied banner should appear
    expect(screen.getByTestId('suggestion-applied-banner')).toBeInTheDocument();

    // Prompt should be modified (check the textarea contains the proposed variable)
    const promptTextarea = screen.getByTestId<HTMLTextAreaElement>('nemotron-system-prompt');
    expect(promptTextarea.value).toContain('{time_since_last_event}');
  });

  it('Dismiss button closes preview without changes', async () => {
    const user = userEvent.setup();
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('dismiss-suggestion-button')).toBeInTheDocument();
    });

    // Click Dismiss
    await user.click(screen.getByTestId('dismiss-suggestion-button'));

    // Diff preview should close
    await waitFor(() => {
      expect(screen.queryByTestId('diff-preview-section')).not.toBeInTheDocument();
    });

    // Applied banner should NOT appear
    expect(screen.queryByTestId('suggestion-applied-banner')).not.toBeInTheDocument();

    // Prompt should remain unchanged
    const promptTextarea = screen.getByTestId('nemotron-system-prompt');
    expect(promptTextarea).toHaveValue('You are a security analyzer.');
  });

  it('sets hasUnsavedChanges after applying suggestion', async () => {
    const user = userEvent.setup();
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('apply-suggestion-button')).toBeInTheDocument();
    });

    // Apply the suggestion
    await user.click(screen.getByTestId('apply-suggestion-button'));

    // Banner should indicate unsaved changes
    await waitFor(() => {
      expect(screen.getByTestId('suggestion-applied-banner')).toBeInTheDocument();
      expect(screen.getByText(/Test it or save to keep your changes/)).toBeInTheDocument();
    });

    // Save button should now be enabled (indicates hasUnsavedChanges)
    const saveButton = screen.getByTestId('nemotron-save');
    expect(saveButton).not.toBeDisabled();
  });

  it('clears activeSuggestion after dismiss', async () => {
    const user = userEvent.setup();
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('diff-preview-section')).toBeInTheDocument();
    });

    // Dismiss
    await user.click(screen.getByTestId('dismiss-suggestion-button'));

    // Preview should be gone
    await waitFor(() => {
      expect(screen.queryByTestId('diff-preview-section')).not.toBeInTheDocument();
    });

    // Preview Changes button should now be visible (since enrichedSuggestion still exists)
    expect(screen.getByTestId('nemotron-preview-changes')).toBeInTheDocument();
  });

  it('shows Preview Changes button when enrichedSuggestion is provided', async () => {
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-preview-changes')).toBeInTheDocument();
    });

    // Diff preview should NOT be shown initially
    expect(screen.queryByTestId('diff-preview-section')).not.toBeInTheDocument();
  });

  it('clicking Preview Changes opens diff preview', async () => {
    const user = userEvent.setup();
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-preview-changes')).toBeInTheDocument();
    });

    // Click Preview Changes
    await user.click(screen.getByTestId('nemotron-preview-changes'));

    // Diff preview should appear
    await waitFor(() => {
      expect(screen.getByTestId('diff-preview-section')).toBeInTheDocument();
    });
  });

  it('renders SuggestionExplanation when preview is active', async () => {
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('diff-preview-section')).toBeInTheDocument();
    });

    // SuggestionExplanation should be rendered (showTips defaults to true)
    expect(screen.getByTestId('suggestion-explanation')).toBeInTheDocument();
  });

  it('handleEventClick opens event in new tab', async () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    const user = userEvent.setup();

    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('suggestion-explanation')).toBeInTheDocument();
    });

    // Expand the explanation to see event links
    const explanationToggle = screen.getByRole('button', { name: /why this matters/i });
    await user.click(explanationToggle);

    // Find and click a "view event" link
    await waitFor(() => {
      expect(screen.getByText(/Event #142/)).toBeInTheDocument();
    });

    const viewEventLink = screen.getAllByLabelText(/view event/i)[0];
    await user.click(viewEventLink);

    // Verify window.open was called with correct URL
    expect(windowOpenSpy).toHaveBeenCalledWith('/timeline?event=142', '_blank');

    windowOpenSpy.mockRestore();
  });

  it('respects showTips preference from localStorage', async () => {
    // Set showTips to false in localStorage
    localStorageMock.setItem('promptPlayground.showTips', JSON.stringify(false));

    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('diff-preview-section')).toBeInTheDocument();
    });

    // SuggestionExplanation should NOT be rendered when showTips is false
    expect(screen.queryByTestId('suggestion-explanation')).not.toBeInTheDocument();
  });

  it('explanation appears below diff view', async () => {
    render(
      <PromptPlayground
        {...defaultProps}
        enrichedSuggestion={mockEnrichedSuggestion}
        initialShowDiffPreview={true}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('diff-preview-section')).toBeInTheDocument();
    });

    // Get the diff preview section
    const diffPreviewSection = screen.getByTestId('diff-preview-section');

    // Get the SuggestionDiffView and SuggestionExplanation within it
    const suggestionDiffView = diffPreviewSection.querySelector(
      '[data-testid="suggestion-diff-view"]'
    );
    const suggestionExplanation = diffPreviewSection.querySelector(
      '[data-testid="suggestion-explanation"]'
    );

    expect(suggestionDiffView).toBeInTheDocument();
    expect(suggestionExplanation).toBeInTheDocument();

    // Verify explanation comes after diff view in DOM order
    const children = Array.from(diffPreviewSection.children);
    const diffViewIndex = children.indexOf(suggestionDiffView as Element);
    const explanationIndex = children.indexOf(suggestionExplanation as Element);

    expect(explanationIndex).toBeGreaterThan(diffViewIndex);
  });
});
