/**
 * Tests for PromptPlayground component
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import PromptPlayground from './PromptPlayground';

// Mock fetch globally
const mockFetch = vi.fn();
(globalThis as { fetch: typeof fetch }).fetch = mockFetch;

// Mock URL.createObjectURL and URL.revokeObjectURL
URL.createObjectURL = vi.fn(() => 'mock-url');
URL.revokeObjectURL = vi.fn();

// Mock window.confirm
const mockConfirm = vi.fn();
window.confirm = mockConfirm;

const mockPromptsResponse = {
  version: '1.0',
  exported_at: '2026-01-04T10:00:00Z',
  prompts: {
    nemotron: {
      system_prompt: 'You are a security analyst...',
      version: 1,
    },
    florence2: {
      queries: ['What is the person doing?', 'Describe the scene'],
    },
    yolo_world: {
      classes: ['knife', 'gun'],
      confidence_threshold: 0.35,
    },
    xclip: {
      action_classes: ['loitering', 'fighting'],
    },
    fashion_clip: {
      clothing_categories: ['dark hoodie', 'face mask'],
    },
  },
};

const mockHistoryResponse = {
  versions: [
    {
      id: 1,
      model: 'nemotron',
      version: 1,
      created_at: '2026-01-04T10:00:00Z',
      created_by: null,
      change_description: 'Initial version',
      is_active: true,
    },
  ],
  total_count: 1,
};

const mockTestResult = {
  model: 'nemotron',
  before_score: 50,
  after_score: 35,
  improved: true,
  test_duration_ms: 1500,
  error: null,
};

describe('PromptPlayground', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockConfirm.mockReturnValue(true);

    // Default mock implementations
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/ai-audit/prompts') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockPromptsResponse),
        });
      }
      if (url.includes('/api/ai-audit/prompts/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHistoryResponse),
        });
      }
      if (url === '/api/ai-audit/prompts/test') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTestResult),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('Rendering', () => {
    it('does not render when isOpen is false', () => {
      render(<PromptPlayground isOpen={false} onClose={vi.fn()} />);
      expect(screen.queryByTestId('prompt-playground')).not.toBeInTheDocument();
    });

    it('renders when isOpen is true', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByTestId('prompt-playground')).toBeInTheDocument();
      });
    });

    it('renders the title', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByText('Prompt Playground')).toBeInTheDocument();
      });
    });

    it('renders close button', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByTestId('close-button')).toBeInTheDocument();
      });
    });

    it('renders export button', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByTestId('export-button')).toBeInTheDocument();
      });
    });

    it('renders import button', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByTestId('import-button')).toBeInTheDocument();
      });
    });

    it('renders save button', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByTestId('save-button')).toBeInTheDocument();
      });
    });

    it('renders test event input', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);
      await waitFor(() => {
        expect(screen.getByTestId('test-event-input')).toBeInTheDocument();
      });
    });
  });

  describe('Model Editors', () => {
    it('renders all model editors after loading', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('model-editor-nemotron')).toBeInTheDocument();
        expect(screen.getByTestId('model-editor-florence2')).toBeInTheDocument();
        expect(screen.getByTestId('model-editor-yolo_world')).toBeInTheDocument();
        expect(screen.getByTestId('model-editor-xclip')).toBeInTheDocument();
        expect(screen.getByTestId('model-editor-fashion_clip')).toBeInTheDocument();
      });
    });

    it('expands nemotron by default', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('model-content-nemotron')).toBeInTheDocument();
      });
    });

    it('toggles model expansion when clicked', async () => {
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('model-editor-florence2')).toBeInTheDocument();
      });

      // Florence2 should be collapsed initially
      expect(screen.queryByTestId('model-content-florence2')).not.toBeInTheDocument();

      // Click to expand
      await user.click(screen.getByTestId('model-toggle-florence2'));

      await waitFor(() => {
        expect(screen.getByTestId('model-content-florence2')).toBeInTheDocument();
      });
    });

    it('renders nemotron editor with system prompt textarea', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('system-prompt-textarea')).toBeInTheDocument();
      });
    });
  });

  describe('Testing', () => {
    it('renders test button for each expanded model', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('test-button-nemotron')).toBeInTheDocument();
      });
    });

    it('runs test when test button is clicked', async () => {
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('test-button-nemotron')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('test-button-nemotron'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          '/api/ai-audit/prompts/test',
          expect.objectContaining({
            method: 'POST',
          })
        );
      });
    });

    it('displays test results after test completes', async () => {
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('test-button-nemotron')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('test-button-nemotron'));

      await waitFor(() => {
        expect(screen.getByTestId('test-result-details')).toBeInTheDocument();
      });
    });

    it('allows entering test event ID', async () => {
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('test-event-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('test-event-input');
      await user.type(input, '123');

      expect(input).toHaveValue('123');
    });
  });

  describe('Editing', () => {
    it('updates system prompt when edited', async () => {
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('system-prompt-textarea')).toBeInTheDocument();
      });

      const textarea = screen.getByTestId('system-prompt-textarea');
      await user.clear(textarea);
      await user.type(textarea, 'New prompt');

      expect(textarea).toHaveValue('New prompt');
    });

    it('resets config when reset button is clicked', async () => {
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('system-prompt-textarea')).toBeInTheDocument();
      });

      // Edit the textarea
      const textarea = screen.getByTestId('system-prompt-textarea');
      const originalValue = (textarea as HTMLTextAreaElement).value;
      await user.clear(textarea);
      await user.type(textarea, 'Modified prompt');

      // Reset
      await user.click(screen.getByTestId('reset-button-nemotron'));

      // Should be back to original
      await waitFor(() => {
        expect(textarea).toHaveValue(originalValue);
      });
    });
  });

  describe('Saving', () => {
    it('shows unsaved changes badge when config is modified', async () => {
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('system-prompt-textarea')).toBeInTheDocument();
      });

      // Edit the textarea
      const textarea = screen.getByTestId('system-prompt-textarea');
      await user.type(textarea, ' modified');

      await waitFor(() => {
        expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
      });
    });

    it('saves changes when save button is clicked', async () => {
      const user = userEvent.setup();

      mockFetch.mockImplementation((url: string, options?: RequestInit) => {
        if (url === '/api/ai-audit/prompts') {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockPromptsResponse),
          });
        }
        if (url.includes('/api/ai-audit/prompts/history')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockHistoryResponse),
          });
        }
        if (url.includes('/api/ai-audit/prompts/nemotron') && options?.method === 'PUT') {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ model: 'nemotron', version: 2 }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({}),
        });
      });

      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('system-prompt-textarea')).toBeInTheDocument();
      });

      // Edit the textarea
      const textarea = screen.getByTestId('system-prompt-textarea');
      await user.type(textarea, ' modified');

      // Save
      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          '/api/ai-audit/prompts/nemotron',
          expect.objectContaining({
            method: 'PUT',
          })
        );
      });
    });

    it('disables save button when no changes', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        const saveButton = screen.getByTestId('save-button');
        expect(saveButton).toBeDisabled();
      });
    });
  });

  describe('Closing', () => {
    it('calls onClose when close button is clicked without changes', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('close-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('close-button'));

      expect(onClose).toHaveBeenCalled();
    });

    it('shows confirmation when closing with unsaved changes', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('system-prompt-textarea')).toBeInTheDocument();
      });

      // Make changes
      const textarea = screen.getByTestId('system-prompt-textarea');
      await user.type(textarea, ' modified');

      // Try to close
      await user.click(screen.getByTestId('close-button'));

      expect(mockConfirm).toHaveBeenCalledWith(
        'You have unsaved changes. Are you sure you want to close?'
      );
    });

    it('closes when escape key is pressed', async () => {
      const onClose = vi.fn();
      render(<PromptPlayground isOpen={true} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByTestId('prompt-playground')).toBeInTheDocument();
      });

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('Version History', () => {
    it('renders version history section', async () => {
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('version-history-section')).toBeInTheDocument();
      });
    });

    it('expands version history when clicked', async () => {
      const user = userEvent.setup();
      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('version-history-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('version-history-toggle'));

      await waitFor(() => {
        expect(screen.getByTestId('version-history-list')).toBeInTheDocument();
      });
    });
  });

  describe('Export/Import', () => {
    it('triggers download when export button is clicked', async () => {
      const user = userEvent.setup();

      // Mock the anchor element and its methods
      const mockClick = vi.fn();
      const originalCreateElement = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
        if (tagName === 'a') {
          const anchor = originalCreateElement('a');
          anchor.click = mockClick;
          return anchor;
        }
        return originalCreateElement(tagName);
      });

      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('export-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('export-button'));

      // Verify that the download was triggered
      expect(mockClick).toHaveBeenCalled();

      vi.restoreAllMocks();
    });
  });

  describe('Loading State', () => {
    it('shows loading state while fetching configs', async () => {
      mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolve

      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('loading-state')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('shows error message when loading fails', async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url === '/api/ai-audit/prompts') {
          return Promise.resolve({
            ok: false,
            statusText: 'Internal Server Error',
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHistoryResponse),
        });
      });

      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
      });
    });

    it('shows error message when test fails', async () => {
      const user = userEvent.setup();
      const mockTestError = {
        model: 'nemotron',
        error: 'Test execution failed',
        test_duration_ms: 0,
      };

      mockFetch.mockImplementation((url: string) => {
        if (url === '/api/ai-audit/prompts') {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockPromptsResponse),
          });
        }
        if (url.includes('/api/ai-audit/prompts/history')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockHistoryResponse),
          });
        }
        if (url === '/api/ai-audit/prompts/test') {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockTestError),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({}),
        });
      });

      render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByTestId('test-button-nemotron')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('test-button-nemotron'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
      });
    });
  });

  describe('Recommendation Context', () => {
    it('displays recommendation when provided', async () => {
      const recommendation = {
        suggestion: 'Add more context about cross-camera activity',
        category: 'missing_context',
        eventId: 123,
        model: 'nemotron' as const,
      };

      render(
        <PromptPlayground
          isOpen={true}
          onClose={vi.fn()}
          recommendation={recommendation}
        />
      );

      await waitFor(() => {
        expect(
          screen.getByText(/Add more context about cross-camera activity/)
        ).toBeInTheDocument();
      });
    });

    it('highlights the recommended model', async () => {
      const recommendation = {
        suggestion: 'Test suggestion',
        category: 'missing_context',
        model: 'nemotron' as const,
      };

      render(
        <PromptPlayground
          isOpen={true}
          onClose={vi.fn()}
          recommendation={recommendation}
        />
      );

      await waitFor(() => {
        const modelEditor = screen.getByTestId('model-editor-nemotron');
        expect(modelEditor).toHaveClass('ring-2');
      });
    });
  });
});

describe('ListEditor (via Florence2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockConfirm.mockReturnValue(true);

    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/ai-audit/prompts') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockPromptsResponse),
        });
      }
      if (url.includes('/api/ai-audit/prompts/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHistoryResponse),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  it('can add new items to the list', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.getByTestId('model-editor-florence2')).toBeInTheDocument();
    });

    // Expand florence2
    await user.click(screen.getByTestId('model-toggle-florence2'));

    await waitFor(() => {
      expect(screen.getByTestId('new-item-input')).toBeInTheDocument();
    });

    // Add new item
    const input = screen.getByTestId('new-item-input');
    await user.type(input, 'New query');
    await user.click(screen.getByTestId('add-item-button'));

    // Verify item was added
    await waitFor(() => {
      expect(screen.getByText('New query')).toBeInTheDocument();
    });
  });
});

describe('YoloWorldEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockConfirm.mockReturnValue(true);

    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/ai-audit/prompts') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockPromptsResponse),
        });
      }
      if (url.includes('/api/ai-audit/prompts/history')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockHistoryResponse),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  it('renders confidence threshold slider', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId('model-editor-yolo_world')).toBeInTheDocument();
    });

    // Expand YOLO-World
    await user.click(screen.getByTestId('model-toggle-yolo_world'));

    await waitFor(() => {
      expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
    });
  });

  it('can adjust confidence threshold', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId('model-editor-yolo_world')).toBeInTheDocument();
    });

    // Expand YOLO-World
    await user.click(screen.getByTestId('model-toggle-yolo_world'));

    await waitFor(() => {
      expect(screen.getByTestId('confidence-slider')).toBeInTheDocument();
    });

    // Change slider value
    const slider = screen.getByTestId('confidence-slider');
    fireEvent.change(slider, { target: { value: '50' } });

    expect((slider as HTMLInputElement).value).toBe('50');
  });
});
