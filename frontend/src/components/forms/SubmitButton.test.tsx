/**
 * Tests for SubmitButton component.
 *
 * @see NEM-3356 - Implement useActionState and useFormStatus for forms
 */

import { render, screen } from '@testing-library/react';
import { Save } from 'lucide-react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import {
  SubmitButton,
  PrimarySubmitButton,
  SecondarySubmitButton,
  DangerSubmitButton,
} from './SubmitButton';

// Mock useFormStatus from react-dom
const mockUseFormStatus = vi.fn();

vi.mock('react-dom', async () => {
  const actual = await vi.importActual('react-dom');
  return {
    ...actual,
    useFormStatus: () => mockUseFormStatus(),
  };
});

describe('SubmitButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: not pending
    mockUseFormStatus.mockReturnValue({ pending: false });
  });

  describe('basic rendering', () => {
    it('renders children text', () => {
      render(<SubmitButton>Save Changes</SubmitButton>);

      expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument();
    });

    it('renders as submit button type', () => {
      render(<SubmitButton>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toHaveAttribute('type', 'submit');
    });

    it('applies custom className', () => {
      render(<SubmitButton className="custom-class">Submit</SubmitButton>);

      expect(screen.getByRole('button')).toHaveClass('custom-class');
    });

    it('renders with data-testid', () => {
      render(<SubmitButton data-testid="submit-btn">Submit</SubmitButton>);

      expect(screen.getByTestId('submit-btn')).toBeInTheDocument();
    });
  });

  describe('variants', () => {
    it('applies primary variant styles by default', () => {
      render(<SubmitButton>Primary</SubmitButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-[#76B900]');
    });

    it('applies secondary variant styles', () => {
      render(<SubmitButton variant="secondary">Secondary</SubmitButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-gray-700');
    });

    it('applies danger variant styles', () => {
      render(<SubmitButton variant="danger">Delete</SubmitButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-red-600');
    });
  });

  describe('sizes', () => {
    it('applies small size styles', () => {
      render(<SubmitButton size="sm">Small</SubmitButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('px-3', 'py-1.5', 'text-sm');
    });

    it('applies medium size styles by default', () => {
      render(<SubmitButton>Medium</SubmitButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('px-4', 'py-2', 'text-sm');
    });

    it('applies large size styles', () => {
      render(<SubmitButton size="lg">Large</SubmitButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('px-6', 'py-3', 'text-base');
    });
  });

  describe('pending state', () => {
    beforeEach(() => {
      mockUseFormStatus.mockReturnValue({ pending: true });
    });

    it('is disabled when pending', () => {
      render(<SubmitButton>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('shows pending text when provided', () => {
      render(<SubmitButton pendingText="Saving...">Save</SubmitButton>);

      expect(screen.getByRole('button')).toHaveTextContent('Saving...');
    });

    it('shows children when no pending text provided', () => {
      render(<SubmitButton>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toHaveTextContent('Submit');
    });

    it('renders spinning loader icon when pending', () => {
      const { container } = render(<SubmitButton>Submit</SubmitButton>);

      const loader = container.querySelector('.animate-spin');
      expect(loader).toBeInTheDocument();
    });

    it('sets aria-busy to true when pending', () => {
      render(<SubmitButton>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
    });
  });

  describe('disabled state', () => {
    it('is disabled when disabled prop is true', () => {
      mockUseFormStatus.mockReturnValue({ pending: false });
      render(<SubmitButton disabled>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('is disabled when form is pending even without disabled prop', () => {
      mockUseFormStatus.mockReturnValue({ pending: true });
      render(<SubmitButton>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('sets aria-disabled when disabled', () => {
      render(<SubmitButton disabled>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toHaveAttribute('aria-disabled', 'true');
    });
  });

  describe('icons', () => {
    beforeEach(() => {
      mockUseFormStatus.mockReturnValue({ pending: false });
    });

    it('renders custom icon when provided', () => {
      render(
        <SubmitButton icon={<Save data-testid="save-icon" />}>
          Save
        </SubmitButton>
      );

      expect(screen.getByTestId('save-icon')).toBeInTheDocument();
    });

    it('hides custom icon and shows loader when pending', () => {
      mockUseFormStatus.mockReturnValue({ pending: true });

      const { container } = render(
        <SubmitButton icon={<Save data-testid="save-icon" />}>
          Save
        </SubmitButton>
      );

      expect(screen.queryByTestId('save-icon')).not.toBeInTheDocument();
      expect(container.querySelector('.animate-spin')).toBeInTheDocument();
    });

    it('renders custom pending icon when provided', () => {
      mockUseFormStatus.mockReturnValue({ pending: true });

      render(
        <SubmitButton pendingIcon={<span data-testid="custom-loader">...</span>}>
          Save
        </SubmitButton>
      );

      expect(screen.getByTestId('custom-loader')).toBeInTheDocument();
    });
  });

  describe('fullWidth', () => {
    it('applies full width class when fullWidth is true', () => {
      render(<SubmitButton fullWidth>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toHaveClass('w-full');
    });

    it('does not apply full width class by default', () => {
      render(<SubmitButton>Submit</SubmitButton>);

      expect(screen.getByRole('button')).not.toHaveClass('w-full');
    });
  });

  describe('convenience components', () => {
    it('PrimarySubmitButton uses primary variant', () => {
      render(<PrimarySubmitButton>Primary</PrimarySubmitButton>);

      expect(screen.getByRole('button')).toHaveClass('bg-[#76B900]');
    });

    it('SecondarySubmitButton uses secondary variant', () => {
      render(<SecondarySubmitButton>Secondary</SecondarySubmitButton>);

      expect(screen.getByRole('button')).toHaveClass('bg-gray-700');
    });

    it('DangerSubmitButton uses danger variant', () => {
      render(<DangerSubmitButton>Delete</DangerSubmitButton>);

      expect(screen.getByRole('button')).toHaveClass('bg-red-600');
    });
  });

  describe('accessibility', () => {
    it('has correct button role', () => {
      render(<SubmitButton>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('is focusable when not disabled', () => {
      render(<SubmitButton>Submit</SubmitButton>);

      const button = screen.getByRole('button');
      button.focus();
      expect(document.activeElement).toBe(button);
    });

    it('has focus ring classes for keyboard navigation', () => {
      render(<SubmitButton>Submit</SubmitButton>);

      expect(screen.getByRole('button')).toHaveClass('focus:ring-2');
    });
  });
});
