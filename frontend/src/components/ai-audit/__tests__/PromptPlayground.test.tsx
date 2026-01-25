/**
 * Tests for PromptPlayground component re-exported from ai-audit/
 *
 * NEM-1894: Create PromptPlayground component for A/B testing
 *
 * This file verifies that the PromptPlayground component is properly
 * re-exported from the ai-audit barrel export and functions correctly.
 *
 * More comprehensive tests exist in:
 * - src/components/ai/__tests__/PromptPlayground.*.test.tsx
 * - src/components/ai/PromptPlayground.test.tsx
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

// Import from the ai-audit barrel export to verify re-export works
import {
  PromptPlayground,
  PromptABTest,
  ABTestStats,
  SuggestionDiffView,
  SuggestionExplanation,
  calculateStats,
} from '../index';

import type { ABTestResult, EnrichedSuggestion } from '../../../services/api';
import type { PromptPlaygroundProps } from '../index';

// Mock the API functions
vi.mock('../../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../services/api')>();
  return {
    ...actual,
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
    fetchEvents: vi.fn(() =>
      Promise.resolve({
        events: [],
        total: 0,
      })
    ),
  };
});

describe('PromptPlayground - Barrel Export Verification (NEM-1894)', () => {
  const defaultProps: PromptPlaygroundProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('is properly exported from ai-audit barrel', () => {
    expect(PromptPlayground).toBeDefined();
    expect(typeof PromptPlayground).toBe('function');
  });

  it('renders PromptPlayground when open', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('prompt-playground-panel')).toBeInTheDocument();
    });
  });

  it('renders the title and description', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Prompt Playground')).toBeInTheDocument();
      expect(
        screen.getByText(/Edit, test, and refine AI model prompts and configurations/)
      ).toBeInTheDocument();
    });
  });

  it('loads model accordions from API', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-accordion')).toBeInTheDocument();
    });
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByTestId('close-panel-button')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('close-panel-button'));
    expect(onClose).toHaveBeenCalled();
  });

  it('does not render when closed', () => {
    render(<PromptPlayground {...defaultProps} isOpen={false} />);
    expect(screen.queryByTestId('prompt-playground-panel')).not.toBeInTheDocument();
  });
});

describe('PromptABTest - Barrel Export Verification', () => {
  const mockResults: ABTestResult[] = [
    {
      eventId: 1,
      originalResult: {
        riskScore: 50,
        riskLevel: 'medium',
        reasoning: 'Original analysis',
        processingTimeMs: 100,
      },
      modifiedResult: {
        riskScore: 40,
        riskLevel: 'low',
        reasoning: 'Modified analysis',
        processingTimeMs: 110,
      },
      scoreDelta: -10,
    },
  ];

  it('is properly exported from ai-audit barrel', () => {
    expect(PromptABTest).toBeDefined();
    expect(typeof PromptABTest).toBe('function');
  });

  it('renders PromptABTest with results', () => {
    render(
      <PromptABTest
        originalPrompt="Original prompt"
        modifiedPrompt="Modified prompt"
        results={mockResults}
        isRunning={false}
        onRunTest={vi.fn()}
        onRunRandomTests={vi.fn()}
        onPromoteB={vi.fn()}
      />
    );

    expect(screen.getByTestId('prompt-ab-test')).toBeInTheDocument();
    expect(screen.getByTestId('panel-original')).toBeInTheDocument();
    expect(screen.getByTestId('panel-modified')).toBeInTheDocument();
  });

  it('displays delta indicator for test results', () => {
    render(
      <PromptABTest
        originalPrompt="Original prompt"
        modifiedPrompt="Modified prompt"
        results={mockResults}
        isRunning={false}
        onRunTest={vi.fn()}
        onRunRandomTests={vi.fn()}
        onPromoteB={vi.fn()}
      />
    );

    expect(screen.getByTestId('delta-indicator')).toBeInTheDocument();
    expect(screen.getByText(/Score Delta: -10/)).toBeInTheDocument();
  });
});

describe('ABTestStats - Barrel Export Verification', () => {
  const mockResults: ABTestResult[] = [
    {
      eventId: 1,
      originalResult: {
        riskScore: 50,
        riskLevel: 'medium',
        reasoning: 'Test',
        processingTimeMs: 100,
      },
      modifiedResult: {
        riskScore: 40,
        riskLevel: 'low',
        reasoning: 'Test',
        processingTimeMs: 100,
      },
      scoreDelta: -10,
    },
    {
      eventId: 2,
      originalResult: {
        riskScore: 60,
        riskLevel: 'medium',
        reasoning: 'Test',
        processingTimeMs: 100,
      },
      modifiedResult: {
        riskScore: 45,
        riskLevel: 'low',
        reasoning: 'Test',
        processingTimeMs: 100,
      },
      scoreDelta: -15,
    },
    {
      eventId: 3,
      originalResult: {
        riskScore: 55,
        riskLevel: 'medium',
        reasoning: 'Test',
        processingTimeMs: 100,
      },
      modifiedResult: {
        riskScore: 48,
        riskLevel: 'low',
        reasoning: 'Test',
        processingTimeMs: 100,
      },
      scoreDelta: -7,
    },
  ];

  it('is properly exported from ai-audit barrel', () => {
    expect(ABTestStats).toBeDefined();
    expect(typeof ABTestStats).toBe('function');
  });

  it('calculateStats is properly exported', () => {
    expect(calculateStats).toBeDefined();
    expect(typeof calculateStats).toBe('function');
  });

  it('renders ABTestStats with results', () => {
    render(<ABTestStats results={mockResults} />);

    expect(screen.getByTestId('ab-test-stats')).toBeInTheDocument();
    expect(screen.getByText(/Test Statistics/)).toBeInTheDocument();
    expect(screen.getByText(/3 tests completed/)).toBeInTheDocument();
  });

  it('calculateStats computes correct aggregate statistics', () => {
    const stats = calculateStats(mockResults);

    expect(stats.totalTests).toBe(3);
    expect(stats.avgScoreDelta).toBeCloseTo(-10.67, 1);
    expect(stats.improvementRate).toBeCloseTo(100, 0); // All results improved (< -5)
    expect(stats.regressionRate).toBe(0);
    expect(stats.neutralRate).toBe(0);
  });
});

describe('SuggestionDiffView - Barrel Export Verification', () => {
  const mockSuggestion: EnrichedSuggestion = {
    category: 'missing_context',
    suggestion: 'Add time since last motion variable',
    frequency: 10,
    priority: 'high',
    targetSection: 'context_variables',
    insertionPoint: 'append',
    proposedVariable: '{time_since_motion}',
    proposedLabel: 'Time Since Motion:',
    impactExplanation: 'Reduces false positives by considering motion patterns',
    sourceEventIds: [1, 2, 3],
  };

  const mockDiff = [
    { type: 'unchanged' as const, content: 'context_variables:', lineNumber: 1 },
    { type: 'unchanged' as const, content: '  camera_name: {camera_name}', lineNumber: 2 },
    { type: 'added' as const, content: '  time_since_motion: {time_since_motion}', lineNumber: 3 },
  ];

  it('is properly exported from ai-audit barrel', () => {
    expect(SuggestionDiffView).toBeDefined();
    expect(typeof SuggestionDiffView).toBe('function');
  });

  it('renders SuggestionDiffView with diff', () => {
    render(
      <SuggestionDiffView
        originalPrompt="Original prompt"
        suggestion={mockSuggestion}
        diff={mockDiff}
      />
    );

    expect(screen.getByTestId('suggestion-diff-view')).toBeInTheDocument();
    expect(screen.getByText(/Add time since last motion variable/)).toBeInTheDocument();
  });
});

describe('SuggestionExplanation - Barrel Export Verification', () => {
  const mockSuggestion: EnrichedSuggestion = {
    category: 'missing_context',
    suggestion: 'Add time since last motion variable',
    frequency: 10,
    priority: 'high',
    targetSection: 'context_variables',
    insertionPoint: 'append',
    proposedVariable: '{time_since_motion}',
    proposedLabel: 'Time Since Motion:',
    impactExplanation: 'Reduces false positives by considering motion patterns',
    sourceEventIds: [1, 2, 3],
  };

  it('is properly exported from ai-audit barrel', () => {
    expect(SuggestionExplanation).toBeDefined();
    expect(typeof SuggestionExplanation).toBe('function');
  });

  it('renders SuggestionExplanation', () => {
    render(<SuggestionExplanation suggestion={mockSuggestion} />);

    expect(screen.getByTestId('suggestion-explanation')).toBeInTheDocument();
    expect(screen.getByText(/Why this matters/)).toBeInTheDocument();
  });

  it('expands to show impact explanation when clicked', async () => {
    const user = userEvent.setup();
    render(<SuggestionExplanation suggestion={mockSuggestion} />);

    await user.click(screen.getByText(/Why this matters/));

    await waitFor(() => {
      expect(screen.getByText(/Reduces false positives/)).toBeInTheDocument();
    });
  });
});
