/**
 * Tests for PromptPlayground component - Model Editors
 *
 * NEM-1320: Refactored from PromptPlayground.test.tsx into smaller, focused test files.
 *
 * This file covers:
 * - Florence-2 accordion and VQA queries
 * - YOLO-World accordion and object classes
 * - X-CLIP accordion and action classes
 * - Fashion-CLIP accordion and clothing categories
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

describe('PromptPlayground - Model Editors', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('can expand Florence-2 accordion and see VQA queries', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('florence2-accordion')).toBeInTheDocument();
    });

    // Click to expand Florence-2 accordion
    await user.click(screen.getByTestId('florence2-accordion'));

    await waitFor(() => {
      expect(screen.getByTestId('florence2-vqa-queries')).toBeInTheDocument();
    });
  });

  it('can expand YOLO-World accordion and see object classes', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('yolo_world-accordion')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('yolo_world-accordion'));

    await waitFor(() => {
      expect(screen.getByTestId('yolo_world-object-classes')).toBeInTheDocument();
      expect(screen.getByTestId('yolo_world-confidence')).toBeInTheDocument();
    });
  });

  it('can expand X-CLIP accordion and see action classes', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('xclip-accordion')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('xclip-accordion'));

    await waitFor(() => {
      expect(screen.getByTestId('xclip-action-classes')).toBeInTheDocument();
    });
  });

  it('can expand Fashion-CLIP accordion and see clothing categories', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('fashion_clip-accordion')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('fashion_clip-accordion'));

    await waitFor(() => {
      expect(screen.getByTestId('fashion_clip-clothing-categories')).toBeInTheDocument();
      expect(screen.getByTestId('fashion_clip-suspicious-indicators')).toBeInTheDocument();
    });
  });
});
