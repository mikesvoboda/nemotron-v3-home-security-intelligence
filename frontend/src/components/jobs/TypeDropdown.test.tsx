import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import TypeDropdown, { JOB_TYPE_OPTIONS } from './TypeDropdown';

describe('TypeDropdown', () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  describe('Basic rendering', () => {
    it('renders the dropdown', () => {
      render(<TypeDropdown value={undefined} onChange={mockOnChange} />);
      expect(screen.getByLabelText(/type/i)).toBeInTheDocument();
    });

    it('renders all type options', () => {
      render(<TypeDropdown value={undefined} onChange={mockOnChange} />);
      const select = screen.getByLabelText(/type/i);
      JOB_TYPE_OPTIONS.forEach((option) => {
        const options = select.querySelectorAll('option');
        const hasOption = Array.from(options).some(
          (opt) => opt.textContent === option.label && opt.getAttribute('value') === option.value
        );
        expect(hasOption).toBe(true);
      });
    });

    it('applies custom className', () => {
      const { container } = render(
        <TypeDropdown value={undefined} onChange={mockOnChange} className="custom-class" />
      );
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('Selection behavior', () => {
    it('displays "All" when no value is selected', () => {
      render(<TypeDropdown value={undefined} onChange={mockOnChange} />);
      expect(screen.getByLabelText(/type/i)).toHaveValue('');
    });

    it('displays selected value', () => {
      render(<TypeDropdown value="export" onChange={mockOnChange} />);
      expect(screen.getByLabelText(/type/i)).toHaveValue('export');
    });

    it('calls onChange with type when selected', () => {
      render(<TypeDropdown value={undefined} onChange={mockOnChange} />);
      const select = screen.getByLabelText(/type/i);
      fireEvent.change(select, { target: { value: 'batch_audit' } });
      expect(mockOnChange).toHaveBeenCalledWith('batch_audit');
    });

    it('calls onChange with undefined when "All" is selected', () => {
      render(<TypeDropdown value="export" onChange={mockOnChange} />);
      const select = screen.getByLabelText(/type/i);
      fireEvent.change(select, { target: { value: '' } });
      expect(mockOnChange).toHaveBeenCalledWith(undefined);
    });
  });

  describe('Disabled state', () => {
    it('disables dropdown when disabled prop is true', () => {
      render(<TypeDropdown value={undefined} onChange={mockOnChange} disabled />);
      expect(screen.getByLabelText(/type/i)).toBeDisabled();
    });
  });

  describe('Custom label', () => {
    it('uses custom label', () => {
      render(<TypeDropdown value={undefined} onChange={mockOnChange} label="Job Type" />);
      expect(screen.getByLabelText(/job type/i)).toBeInTheDocument();
    });
  });
});
