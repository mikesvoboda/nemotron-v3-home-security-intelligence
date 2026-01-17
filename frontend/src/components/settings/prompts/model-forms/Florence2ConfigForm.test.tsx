/**
 * Tests for Florence2ConfigForm component
 *
 * @see NEM-2697 - Build Prompt Management page
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import Florence2ConfigForm from './Florence2ConfigForm';

import type { Florence2Config } from '../../../../types/promptManagement';

// ============================================================================
// Test Data
// ============================================================================

const defaultConfig: Florence2Config = {
  queries: ['What objects are in this scene?', 'Describe the activity in this image.'],
};

const emptyConfig: Florence2Config = {
  queries: [],
};

// ============================================================================
// Tests
// ============================================================================

describe('Florence2ConfigForm', () => {
  describe('rendering', () => {
    it('renders the form', () => {
      render(<Florence2ConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByTestId('florence2-config-form')).toBeInTheDocument();
      expect(screen.getByText(/Scene Analysis Queries/i)).toBeInTheDocument();
    });

    it('displays existing queries', () => {
      render(<Florence2ConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByText('What objects are in this scene?')).toBeInTheDocument();
      expect(screen.getByText('Describe the activity in this image.')).toBeInTheDocument();
    });

    it('displays empty state when no queries', () => {
      render(<Florence2ConfigForm config={emptyConfig} onChange={vi.fn()} />);

      expect(screen.getByText(/No queries defined/i)).toBeInTheDocument();
    });

    it('renders add button and input', () => {
      render(<Florence2ConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByPlaceholderText(/Enter a new scene analysis query/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Add/i })).toBeInTheDocument();
    });
  });

  describe('adding queries', () => {
    it('adds a new query when Add button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<Florence2ConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new scene analysis query/i);
      await user.type(input, 'New query');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(handleChange).toHaveBeenCalledWith({
        queries: [...defaultConfig.queries, 'New query'],
      });
    });

    it('adds a new query when Enter is pressed', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<Florence2ConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new scene analysis query/i);
      await user.type(input, 'New query{enter}');

      expect(handleChange).toHaveBeenCalledWith({
        queries: [...defaultConfig.queries, 'New query'],
      });
    });

    it('clears input after adding query', async () => {
      const user = userEvent.setup();

      render(<Florence2ConfigForm config={defaultConfig} onChange={vi.fn()} />);

      const input = screen.getByPlaceholderText(/Enter a new scene analysis query/i);
      await user.type(input, 'New query');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(input).toHaveValue('');
    });

    it('does not add empty queries', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<Florence2ConfigForm config={defaultConfig} onChange={handleChange} />);

      const input = screen.getByPlaceholderText(/Enter a new scene analysis query/i);
      await user.type(input, '   ');
      await user.click(screen.getByRole('button', { name: /Add/i }));

      expect(handleChange).not.toHaveBeenCalled();
    });

    it('disables Add button when input is empty', () => {
      render(<Florence2ConfigForm config={defaultConfig} onChange={vi.fn()} />);

      expect(screen.getByRole('button', { name: /Add/i })).toBeDisabled();
    });
  });

  describe('removing queries', () => {
    it('removes a query when X button is clicked', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<Florence2ConfigForm config={defaultConfig} onChange={handleChange} />);

      const removeButtons = screen.getAllByRole('button', { name: /Remove query/i });
      await user.click(removeButtons[0]);

      expect(handleChange).toHaveBeenCalledWith({
        queries: ['Describe the activity in this image.'],
      });
    });
  });

  describe('disabled state', () => {
    it('disables input and buttons when disabled', () => {
      render(<Florence2ConfigForm config={defaultConfig} onChange={vi.fn()} disabled={true} />);

      expect(screen.getByPlaceholderText(/Enter a new scene analysis query/i)).toBeDisabled();
      expect(screen.getByRole('button', { name: /Add/i })).toBeDisabled();

      const removeButtons = screen.getAllByRole('button', { name: /Remove query/i });
      removeButtons.forEach((button) => {
        expect(button).toBeDisabled();
      });
    });
  });
});
