/**
 * Tests for FashionClipConfigForm component
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import FashionClipConfigForm from './FashionClipConfigForm';

import type { FashionClipConfig } from '../../../../types/promptManagement';

// ============================================================================
// Test Data
// ============================================================================

interface ExtendedFashionClipConfig extends FashionClipConfig {
  suspicious_indicators?: string[];
}

const defaultConfig: ExtendedFashionClipConfig = {
  clothing_categories: ['hoodie', 'jacket', 'uniform'],
  suspicious_indicators: ['face covering', 'all black'],
};

const emptyConfig: ExtendedFashionClipConfig = {
  clothing_categories: [],
  suspicious_indicators: [],
};

// ============================================================================
// Tests
// ============================================================================

describe('FashionClipConfigForm', () => {
  describe('rendering', () => {
    it('renders the form', () => {
      render(<FashionClipConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByTestId('fashionclip-config-form')).toBeInTheDocument();
      expect(screen.getByText(/Clothing Categories/i)).toBeInTheDocument();
      expect(screen.getByText(/Suspicious Indicators/i)).toBeInTheDocument();
    });

    it('displays existing clothing categories as tags', () => {
      render(<FashionClipConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText('hoodie')).toBeInTheDocument();
      expect(screen.getByText('jacket')).toBeInTheDocument();
      expect(screen.getByText('uniform')).toBeInTheDocument();
    });

    it('displays existing suspicious indicators as tags', () => {
      render(<FashionClipConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText('face covering')).toBeInTheDocument();
      expect(screen.getByText('all black')).toBeInTheDocument();
    });

    it('displays empty state when no categories', () => {
      render(<FashionClipConfigForm config={emptyConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/No clothing categories defined/i)).toBeInTheDocument();
      expect(screen.getByText(/No suspicious indicators defined/i)).toBeInTheDocument();
    });
  });

  describe('adding clothing categories', () => {
    it('adds a new category when Add button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<FashionClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new clothing category/i);
      await user.type(input, 'mask');

      const addButtons = screen.getAllByRole('button', { name: /Add/i });
      await user.click(addButtons[0]); // First Add button is for categories

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        clothing_categories: [...defaultConfig.clothing_categories, 'mask'],
      });
    });

    it('adds a new category when Enter is pressed', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<FashionClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new clothing category/i);
      await user.type(input, 'mask{enter}');

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        clothing_categories: [...defaultConfig.clothing_categories, 'mask'],
      });
    });

    it('does not add duplicate categories', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<FashionClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new clothing category/i);
      await user.type(input, 'hoodie');

      const addButtons = screen.getAllByRole('button', { name: /Add/i });
      await user.click(addButtons[0]);

      expect(handleChange).not.toHaveBeenCalled();
    });
  });

  describe('removing clothing categories', () => {
    it('removes a category when X button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<FashionClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const removeButton = screen.getByRole('button', { name: /Remove category: hoodie/i });
      await user.click(removeButton);

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        clothing_categories: ['jacket', 'uniform'],
      });
    });
  });

  describe('adding suspicious indicators', () => {
    it('adds a new indicator when Add button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<FashionClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new suspicious indicator/i);
      await user.type(input, 'gloves');

      const addButtons = screen.getAllByRole('button', { name: /Add/i });
      await user.click(addButtons[1]); // Second Add button is for indicators

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        suspicious_indicators: [...(defaultConfig.suspicious_indicators || []), 'gloves'],
      });
    });

    it('adds a new indicator when Enter is pressed', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<FashionClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new suspicious indicator/i);
      await user.type(input, 'gloves{enter}');

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        suspicious_indicators: [...(defaultConfig.suspicious_indicators || []), 'gloves'],
      });
    });

    it('does not add duplicate indicators', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<FashionClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new suspicious indicator/i);
      await user.type(input, 'face covering');

      const addButtons = screen.getAllByRole('button', { name: /Add/i });
      await user.click(addButtons[1]);

      expect(handleChange).not.toHaveBeenCalled();
    });
  });

  describe('removing suspicious indicators', () => {
    it('removes an indicator when X button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<FashionClipConfigForm config={defaultConfig} onChange={handleChange} />);

      const removeButton = screen.getByRole('button', { name: /Remove indicator: face covering/i });
      await user.click(removeButton);

      expect(handleChange).toHaveBeenCalledWith({
        ...defaultConfig,
        suspicious_indicators: ['all black'],
      });
    });
  });

  describe('disabled state', () => {
    it('disables all inputs when disabled', () => {
      render(<FashionClipConfigForm config={defaultConfig} onChange={vi.fn()} disabled={true} />);

      expect(screen.getByPlaceholderText(/Enter a new clothing category/i)).toBeDisabled();
      expect(screen.getByPlaceholderText(/Enter a new suspicious indicator/i)).toBeDisabled();

      const addButtons = screen.getAllByRole('button', { name: /Add/i });
      addButtons.forEach((button) => {
        expect(button).toBeDisabled();
      });

      const removeButtons = screen.getAllByRole('button', { name: /Remove/i });
      removeButtons.forEach((button) => {
        expect(button).toBeDisabled();
      });
    });
  });

  describe('help text', () => {
    it('displays help text for clothing categories', () => {
      render(<FashionClipConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/identify on detected persons/i)).toBeInTheDocument();
    });

    it('displays help text for suspicious indicators', () => {
      render(<FashionClipConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/indicate suspicious activity/i)).toBeInTheDocument();
    });
  });
});
