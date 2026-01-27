import { render, screen, fireEvent, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import EventSearch from './EventSearch';

import type { EventSearchProps } from './EventSearch';

// Test wrapper that maintains state for controlled component testing
function TestWrapper({
  initialValue = '',
  onChange: externalOnChange,
  ...props
}: Partial<EventSearchProps> & { initialValue?: string }) {
  const [value, setValue] = useState(initialValue);

  const handleChange = (newValue: string) => {
    setValue(newValue);
    if (externalOnChange) {
      externalOnChange(newValue);
    }
  };

  return <EventSearch value={value} onChange={handleChange} {...props} />;
}

describe('EventSearch', () => {
  const mockOnChange = vi.fn();

  const defaultProps: EventSearchProps = {
    value: '',
    onChange: mockOnChange,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders search input with accessible label', () => {
      render(<EventSearch {...defaultProps} />);

      expect(screen.getByRole('textbox', { name: /search events/i })).toBeInTheDocument();
    });

    it('renders with default placeholder', () => {
      render(<EventSearch {...defaultProps} />);

      expect(screen.getByPlaceholderText('Search events...')).toBeInTheDocument();
    });

    it('renders with custom placeholder', () => {
      render(<EventSearch {...defaultProps} placeholder="Find security events..." />);

      expect(screen.getByPlaceholderText('Find security events...')).toBeInTheDocument();
    });

    it('displays current value', () => {
      render(<EventSearch {...defaultProps} value="test query" />);

      expect(screen.getByDisplayValue('test query')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<EventSearch {...defaultProps} className="custom-class" />);

      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('shows search icon by default', () => {
      const { container } = render(<EventSearch {...defaultProps} />);

      // Search icon is rendered via lucide-react
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('hides search icon when showIcon is false', () => {
      render(<EventSearch {...defaultProps} showIcon={false} />);

      // Input should not have the left padding for the icon
      const input = screen.getByRole('textbox', { name: /search events/i });
      expect(input).not.toHaveClass('pl-10');
    });
  });

  describe('Input interactions with useTransition', () => {
    it('calls onChange when input changes', () => {
      render(<TestWrapper onChange={mockOnChange} />);

      const input = screen.getByRole('textbox', { name: /search events/i });

      act(() => {
        fireEvent.change(input, { target: { value: 'test' } });
      });

      expect(mockOnChange).toHaveBeenCalledWith('test');
    });

    it('updates input value when typing', () => {
      render(<TestWrapper />);

      const input = screen.getByRole('textbox', { name: /search events/i });

      act(() => {
        fireEvent.change(input, { target: { value: 'test query' } });
      });

      expect(input).toHaveValue('test query');
    });

    it('clears input on Escape key', () => {
      render(<TestWrapper initialValue="test" onChange={mockOnChange} />);

      const input = screen.getByRole('textbox', { name: /search events/i });

      act(() => {
        fireEvent.keyDown(input, { key: 'Escape' });
      });

      expect(mockOnChange).toHaveBeenCalledWith('');
    });

    it('handles rapid typing', () => {
      render(<TestWrapper onChange={mockOnChange} />);

      const input = screen.getByRole('textbox', { name: /search events/i });

      act(() => {
        fireEvent.change(input, { target: { value: 'r' } });
        fireEvent.change(input, { target: { value: 'ra' } });
        fireEvent.change(input, { target: { value: 'rap' } });
        fireEvent.change(input, { target: { value: 'rapi' } });
        fireEvent.change(input, { target: { value: 'rapid' } });
      });

      // All changes should be captured
      expect(mockOnChange).toHaveBeenCalled();
    });
  });

  describe('Clear button', () => {
    it('shows clear button when input has value', () => {
      render(<EventSearch {...defaultProps} value="test" />);

      expect(screen.getByRole('button', { name: /clear search/i })).toBeInTheDocument();
    });

    it('hides clear button when input is empty', () => {
      render(<EventSearch {...defaultProps} value="" />);

      expect(screen.queryByRole('button', { name: /clear search/i })).not.toBeInTheDocument();
    });

    it('clears input when clear button is clicked', async () => {
      const user = userEvent.setup();
      render(<TestWrapper initialValue="test" onChange={mockOnChange} />);

      const clearButton = screen.getByRole('button', { name: /clear search/i });
      await user.click(clearButton);

      expect(mockOnChange).toHaveBeenCalledWith('');
    });
  });

  describe('useTransition loading indicator', () => {
    it('renders without loading indicator initially', () => {
      render(<EventSearch {...defaultProps} />);

      expect(screen.queryByTestId('search-loading-indicator')).not.toBeInTheDocument();
    });

    it('input remains responsive', () => {
      render(<TestWrapper />);

      const input = screen.getByRole('textbox', { name: /search events/i });
      expect(input).not.toBeDisabled();

      act(() => {
        fireEvent.change(input, { target: { value: 'test' } });
      });

      expect(input).toHaveValue('test');
    });
  });

  describe('Accessibility', () => {
    it('has accessible input with aria-label', () => {
      render(<EventSearch {...defaultProps} />);

      const input = screen.getByRole('textbox', { name: /search events/i });
      expect(input).toHaveAttribute('aria-label', 'Search events');
    });

    it('has accessible clear button', () => {
      render(<EventSearch {...defaultProps} value="test" />);

      const clearButton = screen.getByRole('button', { name: /clear search/i });
      expect(clearButton).toHaveAttribute('aria-label', 'Clear search');
    });
  });

  describe('Edge cases', () => {
    it('handles empty string value', () => {
      render(<EventSearch {...defaultProps} value="" />);

      const input = screen.getByRole('textbox', { name: /search events/i });
      expect(input).toHaveValue('');
    });

    it('handles special characters in query', () => {
      render(<TestWrapper onChange={mockOnChange} />);

      const input = screen.getByRole('textbox', { name: /search events/i });

      act(() => {
        fireEvent.change(input, { target: { value: 'test@#$%^&*()' } });
      });

      expect(input).toHaveValue('test@#$%^&*()');
      expect(mockOnChange).toHaveBeenCalledWith('test@#$%^&*()');
    });

    it('handles very long input strings', () => {
      const longString = 'a'.repeat(500);
      render(<TestWrapper onChange={mockOnChange} />);

      const input = screen.getByRole('textbox', { name: /search events/i });

      act(() => {
        fireEvent.change(input, { target: { value: longString } });
      });

      expect(input).toHaveValue(longString);
    });

    it('handles whitespace-only input', () => {
      render(<TestWrapper onChange={mockOnChange} />);

      const input = screen.getByRole('textbox', { name: /search events/i });

      act(() => {
        fireEvent.change(input, { target: { value: '   ' } });
      });

      expect(input).toHaveValue('   ');
      expect(mockOnChange).toHaveBeenCalledWith('   ');
    });

    it('handles external value updates', () => {
      const { rerender } = render(<EventSearch {...defaultProps} value="initial" />);

      expect(screen.getByDisplayValue('initial')).toBeInTheDocument();

      // Simulate parent component updating the value
      rerender(<EventSearch {...defaultProps} value="updated" />);

      expect(screen.getByDisplayValue('updated')).toBeInTheDocument();
    });
  });

  describe('Focus behavior', () => {
    it('input can receive focus', async () => {
      const user = userEvent.setup();
      render(<EventSearch {...defaultProps} />);

      const input = screen.getByRole('textbox', { name: /search events/i });
      await user.click(input);

      expect(input).toHaveFocus();
    });

    it('maintains focus after input change', () => {
      render(<TestWrapper />);

      const input = screen.getByRole('textbox', { name: /search events/i });
      input.focus();

      act(() => {
        fireEvent.change(input, { target: { value: 'test' } });
      });

      expect(input).toHaveFocus();
    });
  });
});
