/**
 * Tests for PromptPlayground component - Model Editors
 *
 * NEM-1320: Refactored from PromptPlayground.test.tsx into smaller, focused test files.
 *
 * B3.3 box 4 (R2a row 27): the Florence-2/YOLO-World/X-CLIP/Fashion-CLIP editor tests
 * retired with the models; nemotron is the only editor the playground offers.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import PromptPlayground from '../PromptPlayground';

// Mock the API functions
vi.mock('../../../services/api', () => ({
  // Required by the useRoutePrefetch -> routePrefetching/useCamerasQuery import
  // chain (module-eval references); omitting any of them crashes the whole
  // graph at import time under vitest.
  fetchCameras: vi.fn(() => Promise.resolve([])),
  fetchCamera: vi.fn(() => Promise.resolve({})),
  createCamera: vi.fn(() => Promise.resolve({})),
  updateCamera: vi.fn(() => Promise.resolve({})),
  deleteCamera: vi.fn(() => Promise.resolve({})),
  fetchFullHealth: vi.fn(() => Promise.resolve({})),
  fetchNotificationPreferences: vi.fn(() => Promise.resolve([])),
  // fetchEvents: PromptPlayground imports it directly (:51) for the test-prompt
  // event picker; strict vi.mock factories must define every imported export.
  fetchEvents: vi.fn(() =>
    Promise.resolve({
      items: [{ id: 101, camera_id: 'cam1', risk_score: 45, started_at: '2024-01-01T00:00:00Z' }],
      pagination: { total: 1, limit: 5, offset: 0, has_more: false },
    })
  ),
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

  it('shows the Nemotron editor fields', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-accordion')).toBeInTheDocument();
    });

    // Nemotron is expanded by default (first accordion); a click would close it.
    await waitFor(() => {
      expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    });
  });
});
