import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import PasswordInput from './PasswordInput';

describe('PasswordInput', () => {
  describe('rendering', () => {
    it('renders with label', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} />);
      expect(screen.getByLabelText('Password')).toBeInTheDocument();
    });

    it('renders password input field by default', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} />);
      const input = screen.getByLabelText('Password');
      expect(input).toHaveAttribute('type', 'password');
    });

    it('renders with placeholder text', () => {
      render(
        <PasswordInput label="Password" value="" onChange={() => {}} placeholder="Enter password" />
      );
      const input = screen.getByPlaceholderText('Enter password');
      expect(input).toBeInTheDocument();
    });

    it('renders with current value', () => {
      render(<PasswordInput label="Password" value="mypassword123" onChange={() => {}} />);
      const input = screen.getByLabelText('Password');
      expect(input).toHaveValue('mypassword123');
    });

    it('renders visibility toggle button', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} />);
      const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });
      expect(toggleButton).toBeInTheDocument();
    });

    it('renders Eye icon when password is hidden', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} />);
      const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });
      // Eye icon should be visible (svg with specific class or test id)
      expect(toggleButton.querySelector('svg')).toBeInTheDocument();
    });

    it('applies custom className to container', () => {
      const { container } = render(
        <PasswordInput label="Password" value="" onChange={() => {}} className="custom-class" />
      );
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('password visibility toggle', () => {
    it('switches input type to text when toggle button is clicked', async () => {
      const user = userEvent.setup();
      render(<PasswordInput label="Password" value="secret123" onChange={() => {}} />);

      const input = screen.getByLabelText('Password');
      const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });

      expect(input).toHaveAttribute('type', 'password');

      await user.click(toggleButton);

      expect(input).toHaveAttribute('type', 'text');
    });

    it('switches input type back to password on second toggle', async () => {
      const user = userEvent.setup();
      render(<PasswordInput label="Password" value="secret123" onChange={() => {}} />);

      const input = screen.getByLabelText('Password');
      const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });

      await user.click(toggleButton);
      expect(input).toHaveAttribute('type', 'text');

      await user.click(toggleButton);
      expect(input).toHaveAttribute('type', 'password');
    });

    it('renders EyeOff icon when password is visible', async () => {
      const user = userEvent.setup();
      render(<PasswordInput label="Password" value="secret123" onChange={() => {}} />);

      const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });

      // Click to show password
      await user.click(toggleButton);

      // EyeOff icon should be rendered (different from Eye icon)
      // Component should render lucide-react's EyeOff when visible
      expect(toggleButton.querySelector('svg')).toBeInTheDocument();
    });
  });

  describe('value management', () => {
    it('calls onChange when user types in the input', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<PasswordInput label="Password" value="" onChange={handleChange} />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'test');

      expect(handleChange).toHaveBeenCalled();
      // Should be called multiple times (once per character)
      expect(handleChange).toHaveBeenCalledTimes(4);
    });

    it('accepts empty value', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} />);
      const input = screen.getByLabelText('Password');
      expect(input).toHaveValue('');
    });

    it('accepts value with special characters', () => {
      render(
        <PasswordInput label="Password" value="P@ssw0rd!#$%^&*()" onChange={() => {}} />
      );
      const input = screen.getByLabelText('Password');
      expect(input).toHaveValue('P@ssw0rd!#$%^&*()');
    });

    it('accepts long password values', () => {
      const longPassword = 'a'.repeat(100);
      render(<PasswordInput label="Password" value={longPassword} onChange={() => {}} />);
      const input = screen.getByLabelText('Password');
      expect(input).toHaveValue(longPassword);
    });
  });

  describe('accessibility', () => {
    it('has accessible label for toggle button', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} />);
      const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });
      expect(toggleButton).toHaveAttribute('aria-label');
    });

    it('updates aria-label when toggling visibility', async () => {
      const user = userEvent.setup();
      render(<PasswordInput label="Password" value="" onChange={() => {}} />);

      const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });

      // Initially shows "Show password" or similar
      expect(toggleButton).toHaveAttribute('aria-label');
      const initialLabel = toggleButton.getAttribute('aria-label');

      await user.click(toggleButton);

      // After clicking, aria-label should change to "Hide password" or similar
      const updatedLabel = toggleButton.getAttribute('aria-label');
      expect(updatedLabel).not.toBe(initialLabel);
    });

    it('associates label with input using htmlFor', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} />);
      const input = screen.getByLabelText('Password');
      const label = screen.getByText('Password');
      expect(label).toHaveAttribute('for', input.id);
    });

    it('toggle button does not submit form', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} />);
      const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });
      expect(toggleButton).toHaveAttribute('type', 'button');
    });
  });

  describe('disabled state', () => {
    it('disables input when disabled prop is true', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} disabled />);
      const input = screen.getByLabelText('Password');
      expect(input).toBeDisabled();
    });

    it('disables toggle button when disabled prop is true', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} disabled />);
      const toggleButton = screen.getByRole('button', { name: /toggle password visibility/i });
      expect(toggleButton).toBeDisabled();
    });

    it('does not call onChange when disabled', async () => {
      const handleChange = vi.fn();
      const user = userEvent.setup();

      render(<PasswordInput label="Password" value="" onChange={handleChange} disabled />);

      const input = screen.getByLabelText('Password');
      await user.type(input, 'test');

      expect(handleChange).not.toHaveBeenCalled();
    });
  });

  describe('error state', () => {
    it('renders error message when error prop is provided', () => {
      render(
        <PasswordInput
          label="Password"
          value=""
          onChange={() => {}}
          error="Password is required"
        />
      );
      expect(screen.getByText('Password is required')).toBeInTheDocument();
    });

    it('applies error styling to input when error prop is provided', () => {
      render(
        <PasswordInput
          label="Password"
          value=""
          onChange={() => {}}
          error="Password is required"
        />
      );
      const input = screen.getByLabelText('Password');
      // Should have error border class (border-red-500 or similar)
      expect(input).toHaveClass('border-red-500');
    });

    it('associates error message with input using aria-describedby', () => {
      render(
        <PasswordInput
          label="Password"
          value=""
          onChange={() => {}}
          error="Password is required"
        />
      );
      const input = screen.getByLabelText('Password');
      const errorId = input.getAttribute('aria-describedby');
      expect(errorId).toBeTruthy();
      const errorMessage = document.getElementById(errorId!);
      expect(errorMessage).toHaveTextContent('Password is required');
    });
  });

  describe('required state', () => {
    it('marks input as required when required prop is true', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} required />);
      const input = screen.getByLabelText('Password');
      expect(input).toBeRequired();
    });

    it('shows required indicator in label when required prop is true', () => {
      render(<PasswordInput label="Password" value="" onChange={() => {}} required />);
      // Should render asterisk or similar indicator
      expect(screen.getByText('*')).toBeInTheDocument();
    });
  });
});
