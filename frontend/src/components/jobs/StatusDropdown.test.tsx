import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import StatusDropdown, { JOB_STATUS_OPTIONS } from './StatusDropdown';

describe('StatusDropdown', () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  describe('Basic rendering', () => {
    it('renders the dropdown', () => {
      render(<StatusDropdown value={undefined} onChange={mockOnChange} />);
      expect(screen.getByLabelText(/status/i)).toBeInTheDocument();
    });

    it('renders all status options', () => {
      render(<StatusDropdown value={undefined} onChange={mockOnChange} />);
      const select = screen.getByLabelText(/status/i);
      JOB_STATUS_OPTIONS.forEach((option) => {
        const options = select.querySelectorAll('option');
        const hasOption = Array.from(options).some(
          (opt) => opt.textContent === option.label && opt.getAttribute('value') === option.value
        );
        expect(hasOption).toBe(true);
      });
    });

    it('applies custom className', () => {
      const { container } = render(
        <StatusDropdown value={undefined} onChange={mockOnChange} className="custom-class" />
      );
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Selection behavior', () => {
    it('displays "All" when no value is selected', () => {
      render(<StatusDropdown value={undefined} onChange={mockOnChange} />);
      expect(screen.getByLabelText(/status/i)).toHaveValue('');
    });

    it('displays selected value', () => {
      render(<StatusDropdown value="failed" onChange={mockOnChange} />);
      expect(screen.getByLabelText(/status/i)).toHaveValue('failed');
    });

    it('calls onChange with status when selected', () => {
      render(<StatusDropdown value={undefined} onChange={mockOnChange} />);
      const select = screen.getByLabelText(/status/i);
      fireEvent.change(select, { target: { value: 'completed' } });
      expect(mockOnChange).toHaveBeenCalledWith('completed');
    });

    it('calls onChange with undefined when "All" is selected', () => {
      render(<StatusDropdown value="failed" onChange={mockOnChange} />);
      const select = screen.getByLabelText(/status/i);
      fireEvent.change(select, { target: { value: '' } });
      expect(mockOnChange).toHaveBeenCalledWith(undefined);
    });
  });

  describe('Disabled state', () => {
    it('disables dropdown when disabled prop is true', () => {
      render(<StatusDropdown value={undefined} onChange={mockOnChange} disabled />);
      expect(screen.getByLabelText(/status/i)).toBeDisabled();
    });
  });

  describe('Custom label', () => {
    it('uses custom label', () => {
      render(<StatusDropdown value={undefined} onChange={mockOnChange} label="Job Status" />);
      expect(screen.getByLabelText(/job status/i)).toBeInTheDocument();
    });
  });
});
