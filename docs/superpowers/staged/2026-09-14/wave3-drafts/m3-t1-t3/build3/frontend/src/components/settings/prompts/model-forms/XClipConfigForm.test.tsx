/**
 * Tests for XClipConfigForm component
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import XClipConfigForm from './XClipConfigForm';

import type { XClipConfig } from '../../../../types/promptManagement';

// ============================================================================
// Test Data
// ============================================================================

const defaultConfig: XClipConfig = {
  action_classes: ['walking', 'running', 'standing'],
};

const emptyConfig: XClipConfig = {
  action_classes: [],
};

// ============================================================================
// Tests
// ============================================================================

describe('XClipConfigForm', () => {
  describe('rendering', () => {
    it('renders the form', () => {
      render(<XClipConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByTestId('xclip-config-form')).toBeInTheDocument();
      expect(screen.getByText(/Action Classes/i)).toBeInTheDocument();
    });

    it('displays existing action classes as tags', () => {
      render(<XClipConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText('walking')).toBeInTheDocument();
      expect(screen.getByText('running')).toBeInTheDocument();
      expect(screen.getByText('standing')).toBeInTheDocument();
    });

    it('displays empty state when no action classes', () => {
      render(<XClipConfigForm config={emptyConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/No action classes defined/i)).toBeInTheDocument();
    });
  });

  describe('adding action classes', () => {
    it('adds a new action when Add button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<XClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new action class/i);
      await user.type(input, 'jumping');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(handleChange).toHaveBeenCalledWith({
        action_classes: [...defaultConfig.action_classes, 'jumping'],
      });
    });

    it('adds a new action when Enter is pressed', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<XClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new action class/i);
      await user.type(input, 'jumping{enter}');

      expect(handleChange).toHaveBeenCalledWith({
        action_classes: [...defaultConfig.action_classes, 'jumping'],
      });
    });

    it('does not add duplicate action classes', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<XClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new action class/i);
      await user.type(input, 'walking');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(handleChange).not.toHaveBeenCalled();
    });

    it('does not add empty action classes', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<XClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new action class/i);
      await user.type(input, '   ');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(handleChange).not.toHaveBeenCalled();
    });

    it('clears input after adding action', async () => {
      const user = userEvent.setup();

      render(<XClipConfigForm config={defaultConfig} onChange={vi.fn()} />);

      const input = screen.getByPlaceholderText(/Enter a new action class/i);
      await user.type(input, 'jumping');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(input).toHaveValue('');
    });
  });

  describe('removing action classes', () => {
    it('removes an action when X button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<XClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const removeButton = screen.getByRole('button', { name: /Remove action: walking/i });
      await user.click(removeButton);

      expect(handleChange).toHaveBeenCalledWith({
        action_classes: ['running', 'standing'],
      });
    });
  });

  describe('disabled state', () => {
    it('disables all inputs when disabled', () => {
      render(<XClipConfigForm config={defaultConfig} onChange={vi.fn()} disabled={true} />);

      expect(screen.getByPlaceholderText(/Enter a new action class/i)).toBeDisabled();
      expect(screen.getByRole('button', { name: /Add/i })).toBeDisabled();

      const removeButtons = screen.getAllByRole('button', { name: /Remove action/i });
      removeButtons.forEach((button) => {
        expect(button).toBeDisabled();
      });
    });
  });

  describe('help text', () => {
    it('displays help text for action classes', () => {
      render(<XClipConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/recognize in video frames/i)).toBeInTheDocument();
    });
  });
});
