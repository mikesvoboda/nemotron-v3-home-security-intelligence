/**
 * Tests for NemotronConfigForm component
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import NemotronConfigForm from './NemotronConfigForm';

import type { NemotronConfig } from '../../../../types/promptManagement';

// ============================================================================
// Test Data
// ============================================================================

const defaultConfig: NemotronConfig = {
  system_prompt: 'You are an AI security analyst.',
};

const fullConfig = {
  system_prompt: 'You are an AI security analyst.',
  temperature: 0.7,
  max_tokens: 4096,
};

// ============================================================================
// Tests
// ============================================================================

describe('NemotronConfigForm', () => {
  describe('rendering', () => {
    it('renders the form with all fields', () => {
      render(<NemotronConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByTestId('nemotron-config-form')).toBeInTheDocument();
      expect(screen.getByLabelText(/System Prompt/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Temperature/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Max Tokens/i)).toBeInTheDocument();
    });

    it('displays the current system prompt', () => {
      render(<NemotronConfigForm config={defaultConfig} onChange={vi.fn()} />);

      const textarea = screen.getByLabelText(/System Prompt/i);
      expect(textarea).toHaveValue('You are an AI security analyst.');
    });

    it('displays temperature with default value', () => {
      render(<NemotronConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/Temperature: 0.7/i)).toBeInTheDocument();
    });

    it('displays provided temperature value', () => {
      render(
        <NemotronConfigForm
          config={{ ...defaultConfig, temperature: 1.5 } as NemotronConfig}
          onChange={vi.fn()}
        />
      );

      expect(screen.getByText(/Temperature: 1.5/i)).toBeInTheDocument();
    });

    it('disables fields when disabled prop is true', () => {
      render(<NemotronConfigForm config={defaultConfig} onChange={vi.fn()} disabled={true} />);

      expect(screen.getByLabelText(/System Prompt/i)).toBeDisabled();
      expect(screen.getByLabelText(/Temperature/i)).toBeDisabled();
    });
  });

  describe('system prompt changes', () => {
    it('calls onChange when system prompt is modified', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<NemotronConfigForm config={defaultConfig} onChange={handleChange} />);

      const textarea = screen.getByLabelText(/System Prompt/i);
      // Type a single character to trigger onChange
      await user.type(textarea, 'X');

      expect(handleChange).toHaveBeenCalled();
      // The last call should contain the updated prompt with the new character
      const lastCall = handleChange.mock.calls[handleChange.mock.calls.length - 1][0];
      expect(lastCall.system_prompt).toBe('You are an AI security analyst.X');
    });
  });

  describe('temperature changes', () => {
    it('calls onChange when temperature slider changes', () => {
      const handleChange = vi.fn();

      render(<NemotronConfigForm config={fullConfig as NemotronConfig} onChange={handleChange} />);

      const slider = screen.getByLabelText(/Temperature/i);
      fireEvent.change(slider, { target: { value: '1.0' } });

      expect(handleChange).toHaveBeenCalledWith(expect.objectContaining({ temperature: 1.0 }));
    });
  });

  describe('max tokens changes', () => {
    it('calls onChange when max tokens changes', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<NemotronConfigForm config={fullConfig as NemotronConfig} onChange={handleChange} />);

      const input = screen.getByLabelText(/Max Tokens/i);
      await user.clear(input);
      await user.type(input, '2048');

      expect(handleChange).toHaveBeenCalled();
    });
  });

  describe('help text', () => {
    it('displays help text for system prompt', () => {
      render(<NemotronConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/defines the AI's role/i)).toBeInTheDocument();
    });

    it('displays help text for temperature', () => {
      render(<NemotronConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/Lower values.*produce more focused/i)).toBeInTheDocument();
    });

    it('displays help text for max tokens', () => {
      render(<NemotronConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/Maximum number of tokens/i)).toBeInTheDocument();
    });
  });
});
