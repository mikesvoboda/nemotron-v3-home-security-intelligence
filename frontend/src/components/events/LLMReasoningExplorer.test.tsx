/**
 * Tests for LLMReasoningExplorer component.
 *
 * Tests the display of LLM reasoning data including:
 * - Think block display with expandable steps
 * - Enrichment sources visualization
 * - Truncation indicators
 * - Debug mode functionality
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import LLMReasoningExplorer from './LLMReasoningExplorer';
import * as llmReasoningApi from '../../services/llmReasoningApi';

import type { LLMReasoningResponse } from '../../types/llmReasoning';

// Mock only the fetchLLMReasoning function, keep LLMReasoningApiError real
vi.mock('../../services/llmReasoningApi', async (importOriginal) => {
  const actual = await importOriginal<typeof llmReasoningApi>();
  return {
    ...actual,
    fetchLLMReasoning: vi.fn(),
  };
});

const mockLLMReasoningResponse: LLMReasoningResponse = {
  id: 1,
  eventId: 123,
  createdAt: '2026-01-15T10:30:00Z',
  rawResponse: '<think>Test reasoning content here</think> Final analysis complete.',
  thinkBlock: {
    rawThinkBlock: 'Test reasoning content here',
    reasoningSteps: [
      {
        stepNumber: 1,
        content: 'First, I observe the person approaching the door.',
        keyFactors: ['proximity to entrance', 'time of day'],
        confidenceIndicator: 'high',
      },
      {
        stepNumber: 2,
        content: 'The person appears to be carrying a package.',
        keyFactors: ['package visible', 'normal behavior'],
        confidenceIndicator: 'medium',
      },
    ],
    keyObservations: ['Person at door', 'Carrying package', 'Daytime activity'],
    riskFactorsMentioned: ['Unknown individual', 'Approaching entrance'],
  },
  enrichmentSources: [
    {
      name: 'Florence-2 Vision Analysis',
      populated: true,
      fieldCount: 5,
      sampleFields: ['scene_description', 'objects', 'activities'],
    },
    {
      name: 'Weather Analysis',
      populated: true,
      fieldCount: 3,
      sampleFields: ['condition', 'visibility', 'lighting'],
    },
    {
      name: 'Violence Detection',
      populated: false,
      fieldCount: 0,
      sampleFields: [],
    },
  ],
  truncationInfo: {
    wasTruncated: true,
    originalLength: 8000,
    truncatedLength: 4096,
    droppedSections: ['historical_events', 'distant_correlations'],
    truncationReason: 'Token limit exceeded (max: 4096)',
  },
  householdMatches: [
    {
      entityType: 'person',
      entityName: 'John Doe',
      similarityScore: 0.92,
      matchMethod: 'face_recognition',
    },
  ],
  debugInfo: {
    promptLength: 4096,
    enrichmentSnapshotKeys: ['florence', 'weather', 'clip'],
    hasTruncationLog: true,
    hasHouseholdMatches: true,
  },
};

describe('LLMReasoningExplorer', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('Loading State', () => {
    it('displays loading spinner while fetching data', () => {
      // Create a promise that never resolves to keep loading state
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockImplementation(
        () => new Promise(() => {})
      );

      render(<LLMReasoningExplorer eventId={123} />);

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when API call fails', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockRejectedValue(
        new llmReasoningApi.LLMReasoningApiError(
          'No LLM reasoning data available',
          404,
          123,
          'Event was processed before tracking was enabled'
        )
      );

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        // Error message is displayed from the error.message
        expect(screen.getByText(/no llm reasoning data available/i)).toBeInTheDocument();
      });
    });

    it('displays retry button on error', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockRejectedValueOnce(
        new Error('Network error')
      );

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      });
    });
  });

  describe('Think Block Display', () => {
    it('renders think block section when data is available', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/reasoning steps/i)).toBeInTheDocument();
      });
    });

    it('displays individual reasoning steps', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      // Render with defaultExpanded=true to show reasoning steps content
      render(<LLMReasoningExplorer eventId={123} defaultExpanded={true} />);

      await waitFor(() => {
        expect(screen.getByText(/observe the person approaching/i)).toBeInTheDocument();
        expect(screen.getByText(/carrying a package/i)).toBeInTheDocument();
      });
    });

    it('shows key factors for each step', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      // Render with defaultExpanded=true to show key factors
      render(<LLMReasoningExplorer eventId={123} defaultExpanded={true} />);

      await waitFor(() => {
        expect(screen.getByText(/proximity to entrance/i)).toBeInTheDocument();
        expect(screen.getByText(/time of day/i)).toBeInTheDocument();
      });
    });

    it('displays confidence indicators', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      // Render with defaultExpanded=true to show confidence indicators
      render(<LLMReasoningExplorer eventId={123} defaultExpanded={true} />);

      await waitFor(() => {
        // Check for confidence badge/indicator
        expect(screen.getByText(/high/i)).toBeInTheDocument();
      });
    });

    it('expands and collapses reasoning steps', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);
      const user = userEvent.setup();

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/reasoning steps/i)).toBeInTheDocument();
      });

      // Find and click expand button
      const expandButton = screen.getByRole('button', { name: /expand/i });
      await user.click(expandButton);

      // Verify content is expanded
      expect(screen.getByTestId('reasoning-steps-expanded')).toBeInTheDocument();
    });
  });

  describe('Enrichment Sources', () => {
    it('displays enrichment sources section', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/enrichment sources/i)).toBeInTheDocument();
      });
    });

    it('shows populated and unpopulated sources differently', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/florence-2 vision analysis/i)).toBeInTheDocument();
        expect(screen.getByText(/weather analysis/i)).toBeInTheDocument();
        expect(screen.getByText(/violence detection/i)).toBeInTheDocument();
      });

      // Populated source should show field count
      expect(screen.getByText(/5 fields/i)).toBeInTheDocument();
    });

    it('displays sample fields for populated sources', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/scene_description/i)).toBeInTheDocument();
      });
    });
  });

  describe('Truncation Indicator', () => {
    it('displays truncation warning when content was truncated', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/context truncated/i)).toBeInTheDocument();
      });
    });

    it('shows dropped sections when truncation occurred', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/historical_events/i)).toBeInTheDocument();
        expect(screen.getByText(/distant_correlations/i)).toBeInTheDocument();
      });
    });

    it('does not show truncation warning when not truncated', async () => {
      const noTruncationResponse = {
        ...mockLLMReasoningResponse,
        truncationInfo: {
          wasTruncated: false,
          originalLength: null,
          truncatedLength: null,
          droppedSections: [],
          truncationReason: null,
        },
      };
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(noTruncationResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/reasoning steps/i)).toBeInTheDocument();
      });

      expect(screen.queryByText(/context truncated/i)).not.toBeInTheDocument();
    });
  });

  describe('Household Matches', () => {
    it('displays household matches when available', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/john doe/i)).toBeInTheDocument();
        expect(screen.getByText(/92%/i)).toBeInTheDocument(); // Similarity score
      });
    });

    it('shows match method for household matches', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/face_recognition/i)).toBeInTheDocument();
      });
    });
  });

  describe('Debug Mode', () => {
    it('shows debug toggle button', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /debug/i })).toBeInTheDocument();
      });
    });

    it('shows debug information when debug mode is enabled', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);
      const user = userEvent.setup();

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /debug/i })).toBeInTheDocument();
      });

      // Enable debug mode
      const debugButton = screen.getByRole('button', { name: /debug/i });
      await user.click(debugButton);

      // Should show debug info
      await waitFor(() => {
        expect(screen.getByText(/prompt length/i)).toBeInTheDocument();
      });
    });

    it('displays raw response in debug mode', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);
      const user = userEvent.setup();

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /debug/i })).toBeInTheDocument();
      });

      // Enable debug mode
      const debugButton = screen.getByRole('button', { name: /debug/i });
      await user.click(debugButton);

      // Should show raw response section
      await waitFor(() => {
        expect(screen.getByText(/raw response/i)).toBeInTheDocument();
      });
    });

    it('refetches with debug info when debug mode enabled', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);
      const user = userEvent.setup();

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /debug/i })).toBeInTheDocument();
      });

      // Clear mock calls
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockClear();
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      // Enable debug mode
      const debugButton = screen.getByRole('button', { name: /debug/i });
      await user.click(debugButton);

      // Should have called with includeDebug=true
      await waitFor(() => {
        expect(llmReasoningApi.fetchLLMReasoning).toHaveBeenCalledWith(123, true);
      });
    });
  });

  describe('Key Observations Section', () => {
    it('displays key observations', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/person at door/i)).toBeInTheDocument();
        expect(screen.getByText(/carrying package/i)).toBeInTheDocument();
      });
    });
  });

  describe('Risk Factors Section', () => {
    it('highlights risk factors mentioned in reasoning', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText(/unknown individual/i)).toBeInTheDocument();
        expect(screen.getByText(/approaching entrance/i)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has accessible section headings', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        // Check for proper heading structure - the main heading is "LLM Reasoning Explorer"
        expect(screen.getByRole('heading', { name: /llm reasoning explorer/i })).toBeInTheDocument();
      });
    });

    it('has proper ARIA labels on expandable sections', async () => {
      vi.mocked(llmReasoningApi.fetchLLMReasoning).mockResolvedValue(mockLLMReasoningResponse);

      render(<LLMReasoningExplorer eventId={123} />);

      await waitFor(() => {
        const expandButton = screen.getByRole('button', { name: /expand/i });
        expect(expandButton).toHaveAttribute('aria-expanded');
      });
    });
  });
});
