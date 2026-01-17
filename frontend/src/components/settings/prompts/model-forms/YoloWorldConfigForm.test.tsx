/**
 * Tests for YoloWorldConfigForm component
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import YoloWorldConfigForm from './YoloWorldConfigForm';

import type { YoloWorldConfig } from '../../../../types/promptManagement';

// ============================================================================
// Test Data
// ============================================================================

const defaultConfig: YoloWorldConfig = {
  classes: ['person', 'car', 'package'],
  confidence_threshold: 0.5,
};

const emptyConfig: YoloWorldConfig = {
  classes: [],
  confidence_threshold: 0.5,
};

// ============================================================================
// Tests
// ============================================================================

describe('YoloWorldConfigForm', () => {
  describe('rendering', () => {
    it('renders the form', () => {
      render(<YoloWorldConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByTestId('yoloworld-config-form')).toBeInTheDocument();
      // Check for the help text which is unique
      expect(screen.getByText(/open-vocabulary detection/i)).toBeInTheDocument();
      expect(screen.getByText(/Confidence Threshold/i)).toBeInTheDocument();
    });

    it('displays existing classes as tags', () => {
      render(<YoloWorldConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText('person')).toBeInTheDocument();
      expect(screen.getByText('car')).toBeInTheDocument();
      expect(screen.getByText('package')).toBeInTheDocument();
    });

    it('displays empty state when no classes', () => {
      render(<YoloWorldConfigForm config={emptyConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/No classes defined/i)).toBeInTheDocument();
    });

    it('displays current confidence threshold', () => {
      render(<YoloWorldConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/Confidence Threshold: 0.50/i)).toBeInTheDocument();
    });
  });

  describe('adding classes', () => {
    it('adds a new class when Add button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<YoloWorldConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new object class/i);
      await user.type(input, 'dog');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        classes: [...defaultConfig.classes, 'dog'],
      });
    });

    it('adds a new class when Enter is pressed', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<YoloWorldConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new object class/i);
      await user.type(input, 'dog{enter}');

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        classes: [...defaultConfig.classes, 'dog'],
      });
    });

    it('does not add duplicate classes', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<YoloWorldConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new object class/i);
      await user.type(input, 'person');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(handleChange).not.toHaveBeenCalled();
    });

    it('does not add empty classes', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<YoloWorldConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new object class/i);
      await user.type(input, '   ');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(handleChange).not.toHaveBeenCalled();
    });
  });

  describe('removing classes', () => {
    it('removes a class when X button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<YoloWorldConfigForm config={defaultConfig} onChange={handleChange} />);

      const removeButton = screen.getByRole('button', { name: /Remove class: person/i });
      await user.click(removeButton);

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        classes: ['car', 'package'],
      });
    });
  });

  describe('confidence threshold', () => {
    it('calls onChange when confidence slider changes', () => {
      const handleChange = vi.fn();

      render(<YoloWorldConfigForm config={defaultConfig} onChange={handleChange} />);

      const slider = screen.getByLabelText(/Confidence Threshold/i);
      fireEvent.change(slider, { target: { value: '0.75' } });

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        confidence_threshold: 0.75,
      });
    });
  });

  describe('disabled state', () => {
    it('disables all inputs when disabled', () => {
      render(<YoloWorldConfigForm config={defaultConfig} onChange={vi.fn()} disabled={true} />);

      expect(screen.getByPlaceholderText(/Enter a new object class/i)).toBeDisabled();
      expect(screen.getByRole('button', { name: /Add/i })).toBeDisabled();
      expect(screen.getByLabelText(/Confidence Threshold/i)).toBeDisabled();

      const removeButtons = screen.getAllByRole('button', { name: /Remove class/i });
      removeButtons.forEach((button) => {
        expect(button).toBeDisabled();
      });
    });
  });

  describe('help text', () => {
    it('displays help text for object classes', () => {
      render(<YoloWorldConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/open-vocabulary detection/i)).toBeInTheDocument();
    });

    it('displays help text for confidence threshold', () => {
      render(<YoloWorldConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/reduce false positives/i)).toBeInTheDocument();
    });
  });
});
