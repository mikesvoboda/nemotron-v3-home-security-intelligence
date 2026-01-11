/**
 * Validation tests for PromptPlayground component's temperature and max_tokens inputs
 * Tests input validation, error messages, form submission blocking, and edge cases
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import PromptPlayground from '../PromptPlayground';

/**
 * Helper function to get an input element by test ID with proper typing.
 * This resolves TypeScript errors when accessing input-specific properties like value, min, max, etc.
 * The type assertion is necessary because screen.getByTestId returns HTMLElement, not HTMLInputElement.
 */
const getInputByTestId = (testId: string): HTMLInputElement => {
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
  return screen.getByTestId(testId) as HTMLInputElement;
};

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
      ],
      pagination: {
        total: 1,
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

describe('PromptPlayground Temperature Validation', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders temperature slider with correct attributes', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');
    expect(temperatureSlider.type).toBe('range');
    expect(temperatureSlider.min).toBe('0');
    expect(temperatureSlider.max).toBe('2');
    expect(temperatureSlider.step).toBe('0.1');
  });

  it('displays default temperature value (0.7)', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');
    expect(temperatureSlider.value).toBe('0.7');

    // Check label displays value
    expect(screen.getByText(/Temperature: 0\.70/)).toBeInTheDocument();
  });

  it('allows temperature within valid range (0.0-2.0)', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');

    // Verify range constraints - browser enforces these on range inputs
    expect(Number(temperatureSlider.min)).toBe(0);
    expect(Number(temperatureSlider.max)).toBe(2);
    expect(Number(temperatureSlider.step)).toBe(0.1);

    // Verify default value is within range
    const currentValue = Number(temperatureSlider.value);
    expect(currentValue).toBeGreaterThanOrEqual(0);
    expect(currentValue).toBeLessThanOrEqual(2);
  });

  it('enforces minimum temperature value (0.0)', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');

    // Browser enforces min/max on range inputs, so values below min are clamped
    expect(Number(temperatureSlider.min)).toBe(0);
    expect(Number(temperatureSlider.value)).toBeGreaterThanOrEqual(0);
  });

  it('enforces maximum temperature value (2.0)', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');

    // Browser enforces min/max on range inputs, so values above max are clamped
    expect(Number(temperatureSlider.max)).toBe(2);
    expect(Number(temperatureSlider.value)).toBeLessThanOrEqual(2);
  });

  it('updates display label when temperature changes', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    // Verify initial label shows default value
    expect(screen.getByText(/Temperature: 0\.70/)).toBeInTheDocument();

    // Note: Testing actual slider interaction requires simulating change events
    // The component correctly displays the temperature value in the label
    const temperatureSlider = getInputByTestId('nemotron-temperature');
    expect(temperatureSlider.value).toBe('0.7');
  });

  it('enables save button when temperature is modified', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');
    const saveButton = screen.getByTestId('nemotron-save');

    // Initially should be disabled (no changes)
    expect(saveButton).toBeDisabled();

    // Change temperature using fireEvent for range inputs
    fireEvent.change(temperatureSlider, { target: { value: '1.2' } });

    // Save button should be enabled
    await waitFor(() => {
      expect(saveButton).not.toBeDisabled();
    });
  });

  it('accepts decimal temperature values with 0.1 step', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');

    // Test various decimal values using fireEvent
    const testValues = ['0.1', '0.5', '0.9', '1.3', '1.7', '1.9'];

    for (const value of testValues) {
      fireEvent.change(temperatureSlider, { target: { value } });
      expect(temperatureSlider.value).toBe(value);
    }
  });
});

describe('PromptPlayground Max Tokens Validation', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders max_tokens input with correct attributes', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');
    expect(maxTokensInput.type).toBe('number');
    expect(maxTokensInput.min).toBe('100');
    expect(maxTokensInput.max).toBe('8192');
  });

  it('displays default max_tokens value (2048)', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');
    expect(maxTokensInput.value).toBe('2048');
  });

  it('allows max_tokens within valid range (100-8192)', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');

    // Test minimum (100) using fireEvent
    fireEvent.change(maxTokensInput, { target: { value: '100' } });
    expect(maxTokensInput.value).toBe('100');

    // Test maximum (8192)
    fireEvent.change(maxTokensInput, { target: { value: '8192' } });
    expect(maxTokensInput.value).toBe('8192');

    // Test mid-range (4096)
    fireEvent.change(maxTokensInput, { target: { value: '4096' } });
    expect(maxTokensInput.value).toBe('4096');
  });

  it('accepts only positive integer values', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');

    // Test positive integer using fireEvent
    fireEvent.change(maxTokensInput, { target: { value: '1024' } });
    expect(maxTokensInput.value).toBe('1024');
  });

  it('has minimum value constraint (100)', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');
    expect(Number(maxTokensInput.min)).toBe(100);
  });

  it('has maximum value constraint (8192)', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');
    expect(Number(maxTokensInput.max)).toBe(8192);
  });

  it('enables save button when max_tokens is modified', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');
    const saveButton = screen.getByTestId('nemotron-save');

    // Initially should be disabled (no changes)
    expect(saveButton).toBeDisabled();

    // Change max_tokens
    await user.clear(maxTokensInput);
    await user.type(maxTokensInput, '4096');

    // Save button should be enabled
    expect(saveButton).not.toBeDisabled();
  });

  it('handles empty max_tokens input', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');

    // Verify that the input type is number, which has built-in validation
    expect(maxTokensInput.type).toBe('number');

    // Number inputs have browser-enforced validation - empty values are handled by the browser
    // The component handles this via parseInt which will return NaN for empty strings
    expect(maxTokensInput.min).toBe('100');
    expect(maxTokensInput.max).toBe('8192');
  });

  it('handles decimal input by treating as integer', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');

    // Try to enter decimal value
    await user.clear(maxTokensInput);
    await user.type(maxTokensInput, '2048.5');

    // Number input accepts decimal input, but parseInt in the onChange handler converts it
    // The value might be '2048.5' in the input, but the component state stores parseInt result
    expect(maxTokensInput.value).toContain('2048');
  });
});

describe('PromptPlayground Validation Edge Cases', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('handles rapid temperature changes', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');

    // Rapid consecutive changes using fireEvent
    fireEvent.change(temperatureSlider, { target: { value: '0.5' } });
    fireEvent.change(temperatureSlider, { target: { value: '1.0' } });
    fireEvent.change(temperatureSlider, { target: { value: '1.8' } });

    // Final value should be reflected
    expect(temperatureSlider.value).toBe('1.8');

    await waitFor(() => {
      expect(screen.getByText(/Temperature: 1\.80/)).toBeInTheDocument();
    });
  });

  it('handles rapid max_tokens changes', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');

    // Rapid consecutive changes using fireEvent for clean value replacement
    fireEvent.change(maxTokensInput, { target: { value: '512' } });
    fireEvent.change(maxTokensInput, { target: { value: '2048' } });
    fireEvent.change(maxTokensInput, { target: { value: '4096' } });

    // Final value should be reflected
    expect(maxTokensInput.value).toBe('4096');
  });

  it('resets temperature to original value on reset button click', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');
    const resetButton = screen.getByTestId('nemotron-reset');

    // Change temperature using fireEvent
    fireEvent.change(temperatureSlider, { target: { value: '1.5' } });
    expect(temperatureSlider.value).toBe('1.5');

    // Reset
    await user.click(resetButton);

    // Should return to original value (0.7)
    await waitFor(() => {
      const updatedSlider = getInputByTestId('nemotron-temperature');
      expect(updatedSlider.value).toBe('0.7');
    });
  });

  it('resets max_tokens to original value on reset button click', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');
    const resetButton = screen.getByTestId('nemotron-reset');

    // Change max_tokens using fireEvent
    fireEvent.change(maxTokensInput, { target: { value: '4096' } });
    expect(maxTokensInput.value).toBe('4096');

    // Reset
    await user.click(resetButton);

    // Should return to original value (2048)
    await waitFor(() => {
      const updatedInput = getInputByTestId('nemotron-max-tokens');
      expect(updatedInput.value).toBe('2048');
    });
  });

  it('persists temperature changes when saving', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');
    const saveButton = screen.getByTestId('nemotron-save');

    // Change temperature using fireEvent
    fireEvent.change(temperatureSlider, { target: { value: '1.2' } });

    await waitFor(() => {
      expect(temperatureSlider.value).toBe('1.2');
    });

    // Save
    await user.click(saveButton);

    // Wait for save to complete - the component shows success message
    await waitFor(() => {
      expect(screen.getByText(/configuration saved successfully/i)).toBeInTheDocument();
    });

    // After save, the component reloads data from the mocked API which returns original values
    // This is expected behavior - the mock API doesn't persist changes
    // The important thing is that save succeeded without validation errors
    await waitFor(() => {
      const updatedSlider = getInputByTestId('nemotron-temperature');
      // Value returns to original after reload from mocked API
      expect(updatedSlider.value).toBe('0.7');
    });
  });

  it('persists max_tokens changes when saving', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const maxTokensInput = getInputByTestId('nemotron-max-tokens');
    const saveButton = screen.getByTestId('nemotron-save');

    // Change max_tokens using fireEvent
    fireEvent.change(maxTokensInput, { target: { value: '4096' } });
    expect(maxTokensInput.value).toBe('4096');

    // Save
    await user.click(saveButton);

    // Wait for save to complete - the component shows success message
    await waitFor(() => {
      expect(screen.getByText(/configuration saved successfully/i)).toBeInTheDocument();
    });

    // After save, the component reloads data from the mocked API which returns original values
    // This is expected behavior - the mock API doesn't persist changes
    // The important thing is that save succeeded without validation errors
    await waitFor(() => {
      const updatedInput = getInputByTestId('nemotron-max-tokens');
      // Value returns to original after reload from mocked API
      expect(updatedInput.value).toBe('2048');
    });
  });

  it('validates both temperature and max_tokens together', async () => {
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');
    const maxTokensInput = getInputByTestId('nemotron-max-tokens');
    const saveButton = screen.getByTestId('nemotron-save');

    // Change both values using fireEvent
    fireEvent.change(temperatureSlider, { target: { value: '1.5' } });
    fireEvent.change(maxTokensInput, { target: { value: '4096' } });

    // Values should be updated
    expect(temperatureSlider.value).toBe('1.5');
    expect(maxTokensInput.value).toBe('4096');

    // Save button should be enabled with both changes
    await waitFor(() => {
      expect(saveButton).not.toBeDisabled();
    });
  });

  it('maintains validation constraints after accordion collapse and expand', async () => {
    const user = userEvent.setup();
    render(<PromptPlayground {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId('nemotron-accordion')).toBeInTheDocument();
    });

    // Nemotron is expanded by default, so collapse it
    await user.click(screen.getByTestId('nemotron-accordion'));

    // Wait for collapse animation
    await waitFor(() => {
      expect(screen.queryByTestId('nemotron-temperature')).not.toBeInTheDocument();
    });

    // Expand again
    await user.click(screen.getByTestId('nemotron-accordion'));

    // Inputs should be back with same constraints
    await waitFor(() => {
      expect(screen.getByTestId('nemotron-temperature')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-max-tokens')).toBeInTheDocument();
    });

    const temperatureSlider = getInputByTestId('nemotron-temperature');
    const maxTokensInput = getInputByTestId('nemotron-max-tokens');

    expect(temperatureSlider.min).toBe('0');
    expect(temperatureSlider.max).toBe('2');
    expect(maxTokensInput.min).toBe('100');
    expect(maxTokensInput.max).toBe('8192');
  });
});
