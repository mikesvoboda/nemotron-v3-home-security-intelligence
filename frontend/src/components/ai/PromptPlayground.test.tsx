/**
 * Tests for PromptPlayground component
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import PromptPlayground from './PromptPlayground';

// Mock the API functions
vi.mock('../../services/api', () => ({
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

describe('PromptPlayground', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders when open', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('prompt-playground-panel')).toBeInTheDocument();
    });
  });

  it('does not render when closed', () => {
    render(<PromptPlayground {...defaultProps} isOpen={false} />);

    expect(screen.queryByTestId('prompt-playground-panel')).not.toBeInTheDocument();
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

  it('loads and displays model accordions', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-accordion')).toBeInTheDocument();
      expect(screen.getByTestId('florence2-accordion')).toBeInTheDocument();
      expect(screen.getByTestId('yolo_world-accordion')).toBeInTheDocument();
      expect(screen.getByTestId('xclip-accordion')).toBeInTheDocument();
      expect(screen.getByTestId('fashion_clip-accordion')).toBeInTheDocument();
    });
  });

  it('displays Nemotron configuration fields', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-accordion')).toBeInTheDocument();
    });

    // Nemotron is expanded by default (first accordion)
    expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
  });

  it('displays recommendation context when provided', async () => {
    const recommendation = {
      category: 'missing_context',
      suggestion: 'Add time since last motion',
      frequency: 50,
      priority: 'high' as const,
    };

    render(
      <PromptPlayground {...defaultProps} recommendation={recommendation} sourceEventId={123} />
    );

    await waitFor(() => {
      expect(screen.getByText(/Add time since last motion/)).toBeInTheDocument();
      expect(screen.getByText(/#123/)).toBeInTheDocument();
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

  it('renders export and import buttons', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('export-button')).toBeInTheDocument();
      expect(screen.getByTestId('import-button')).toBeInTheDocument();
    });
  });

  it('renders test area with event ID input', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('test-event-id')).toBeInTheDocument();
      expect(screen.getByTestId('run-test-button')).toBeInTheDocument();
    });
  });

  it('pre-fills test event ID from sourceEventId prop', async () => {
    render(<PromptPlayground {...defaultProps} sourceEventId={456} />);

    await waitFor(() => {
      const input = screen.getByTestId('test-event-id');
      expect(input).toHaveValue(456);
    });
  });
});

describe('PromptPlayground model editors', () => {
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

describe('PromptPlayground actions', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows reset and save buttons for Nemotron', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-reset')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-save')).toBeInTheDocument();
    });
  });

  it('shows apply suggestion button when recommendation is provided', async () => {
    const recommendation = {
      category: 'missing_context',
      suggestion: 'Add time context',
      frequency: 50,
      priority: 'high' as const,
    };

    render(<PromptPlayground {...defaultProps} recommendation={recommendation} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-apply-suggestion')).toBeInTheDocument();
    });
  });

  it('enables save button when config is modified', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-system-prompt')).toBeInTheDocument();
    });

    const textarea = screen.getByTestId('nemotron-system-prompt');
    await user.clear(textarea);
    await user.type(textarea, 'New prompt content');

    // Save button should be enabled now
    const saveButton = screen.getByTestId('nemotron-save');
    expect(saveButton).not.toBeDisabled();
  });

  it('shows test results after running test', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('test-event-id')).toBeInTheDocument();
    });

    // Enter event ID
    const eventIdInput = screen.getByTestId('test-event-id');
    await user.type(eventIdInput, '123');

    // Click run test
    await user.click(screen.getByTestId('run-test-button'));

    // Wait for results
    await waitFor(() => {
      expect(screen.getByText('Before')).toBeInTheDocument();
      expect(screen.getByText('After')).toBeInTheDocument();
      expect(screen.getByText(/Configuration improved results/)).toBeInTheDocument();
    });
  });

  it('shows error when test event ID is invalid', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('test-event-id')).toBeInTheDocument();
    });

    // Enter invalid event ID (0 or negative)
    const eventIdInput = screen.getByTestId('test-event-id');
    await user.type(eventIdInput, '0');

    // Click run test
    await user.click(screen.getByTestId('run-test-button'));

    await waitFor(() => {
      expect(screen.getByText(/Please enter a valid Event ID/)).toBeInTheDocument();
    });
  });
});

describe('PromptPlayground keyboard shortcuts', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('closes panel when Escape key is pressed', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByTestId('prompt-playground-panel')).toBeInTheDocument();
    });

    await user.keyboard('{Escape}');

    expect(onClose).toHaveBeenCalled();
  });
});
