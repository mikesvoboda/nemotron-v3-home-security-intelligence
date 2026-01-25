/**
 * Tests for FormField, FormTextarea, and FormSelect components.
 *
 * @see NEM-3356 - Implement useActionState and useFormStatus for forms
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Search } from 'lucide-react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { FormField, FormTextarea, FormSelect } from './FormField';

// Mock useFormStatus from react-dom
const mockUseFormStatus = vi.fn();

vi.mock('react-dom', async () => {
  const actual = await vi.importActual('react-dom');
  return {
    ...actual,
    useFormStatus: () => mockUseFormStatus(),
  };
});

describe('FormField', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseFormStatus.mockReturnValue({ pending: false });
  });

  describe('basic rendering', () => {
    it('renders label and input', () => {
      render(<FormField name="email" label="Email Address" />);

      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    });

    it('renders with correct name attribute', () => {
      render(<FormField name="username" label="Username" />);

      expect(screen.getByLabelText(/username/i)).toHaveAttribute('name', 'username');
    });

    it('renders with custom type', () => {
      render(<FormField name="password" label="Password" type="password" />);

      expect(screen.getByLabelText(/password/i)).toHaveAttribute('type', 'password');
    });

    it('renders with placeholder', () => {
      render(<FormField name="email" label="Email" placeholder="Enter email" />);

      expect(screen.getByPlaceholderText('Enter email')).toBeInTheDocument();
    });

    it('renders with data-testid', () => {
      render(<FormField name="test" label="Test" data-testid="test-field" />);

      expect(screen.getByTestId('test-field')).toBeInTheDocument();
    });
  });

  describe('required indicator', () => {
    it('shows asterisk when required', () => {
      render(<FormField name="email" label="Email" required />);

      expect(screen.getByText('*')).toBeInTheDocument();
    });

    it('does not show asterisk when not required', () => {
      render(<FormField name="email" label="Email" />);

      expect(screen.queryByText('*')).not.toBeInTheDocument();
    });

    it('sets required attribute on input', () => {
      render(<FormField name="email" label="Email" required />);

      expect(screen.getByLabelText(/email/i)).toBeRequired();
    });
  });

  describe('error display', () => {
    it('displays error message', () => {
      render(<FormField name="email" label="Email" error="Invalid email format" />);

      expect(screen.getByRole('alert')).toHaveTextContent('Invalid email format');
    });

    it('applies error styling to input', () => {
      render(<FormField name="email" label="Email" error="Invalid" />);

      expect(screen.getByLabelText(/email/i)).toHaveClass('border-red-500');
    });

    it('sets aria-invalid when error is present', () => {
      render(<FormField name="email" label="Email" error="Invalid" />);

      expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-invalid', 'true');
    });

    it('associates error with input via aria-describedby', () => {
      render(<FormField name="email" label="Email" error="Invalid email" />);

      const input = screen.getByLabelText(/email/i);
      const errorId = input.getAttribute('aria-describedby');
      expect(errorId).toBeTruthy();
      expect(screen.getByRole('alert')).toHaveAttribute('id', errorId);
    });
  });

  describe('help text', () => {
    it('displays help text', () => {
      render(<FormField name="email" label="Email" helpText="We will never share your email" />);

      expect(screen.getByText('We will never share your email')).toBeInTheDocument();
    });

    it('hides help text when error is shown', () => {
      render(<FormField name="email" label="Email" helpText="Help text" error="Error message" />);

      expect(screen.queryByText('Help text')).not.toBeInTheDocument();
      expect(screen.getByText('Error message')).toBeInTheDocument();
    });
  });

  describe('icons', () => {
    it('renders leading icon', () => {
      render(
        <FormField
          name="search"
          label="Search"
          leadingIcon={<Search data-testid="search-icon" />}
        />
      );

      expect(screen.getByTestId('search-icon')).toBeInTheDocument();
    });

    it('renders trailing icon', () => {
      render(
        <FormField
          name="password"
          label="Password"
          trailingIcon={<span data-testid="eye-icon">O</span>}
        />
      );

      expect(screen.getByTestId('eye-icon')).toBeInTheDocument();
    });

    it('applies padding for leading icon', () => {
      render(<FormField name="search" label="Search" leadingIcon={<Search />} />);

      expect(screen.getByLabelText(/search/i)).toHaveClass('pl-10');
    });
  });

  describe('pending state (useFormStatus)', () => {
    it('is disabled when form is pending', () => {
      mockUseFormStatus.mockReturnValue({ pending: true });
      render(<FormField name="email" label="Email" />);

      expect(screen.getByLabelText(/email/i)).toBeDisabled();
    });

    it('is not disabled when form is not pending', () => {
      mockUseFormStatus.mockReturnValue({ pending: false });
      render(<FormField name="email" label="Email" />);

      expect(screen.getByLabelText(/email/i)).not.toBeDisabled();
    });

    it('is disabled when explicitly disabled even if not pending', () => {
      mockUseFormStatus.mockReturnValue({ pending: false });
      render(<FormField name="email" label="Email" disabled />);

      expect(screen.getByLabelText(/email/i)).toBeDisabled();
    });
  });

  describe('user interaction', () => {
    it('accepts user input', async () => {
      const user = userEvent.setup();
      render(<FormField name="email" label="Email" />);

      const input = screen.getByLabelText(/email/i);
      await user.type(input, 'test@example.com');

      expect(input).toHaveValue('test@example.com');
    });

    it('can be focused', async () => {
      const user = userEvent.setup();
      render(<FormField name="email" label="Email" />);

      const input = screen.getByLabelText(/email/i);
      await user.click(input);

      expect(document.activeElement).toBe(input);
    });
  });

  describe('ref forwarding', () => {
    it('forwards ref to input element', () => {
      const ref = vi.fn();
      render(<FormField ref={ref} name="email" label="Email" />);

      expect(ref).toHaveBeenCalled();
      expect(ref.mock.calls[0][0]).toBeInstanceOf(HTMLInputElement);
    });
  });
});

describe('FormTextarea', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseFormStatus.mockReturnValue({ pending: false });
  });

  it('renders textarea with label', () => {
    render(<FormTextarea name="message" label="Message" />);

    expect(screen.getByLabelText(/message/i)).toBeInstanceOf(HTMLTextAreaElement);
  });

  it('shows error message', () => {
    render(<FormTextarea name="message" label="Message" error="Too short" />);

    expect(screen.getByRole('alert')).toHaveTextContent('Too short');
  });

  it('is disabled when form is pending', () => {
    mockUseFormStatus.mockReturnValue({ pending: true });
    render(<FormTextarea name="message" label="Message" />);

    expect(screen.getByLabelText(/message/i)).toBeDisabled();
  });

  it('accepts multiline input', async () => {
    const user = userEvent.setup();
    render(<FormTextarea name="message" label="Message" />);

    const textarea = screen.getByLabelText(/message/i);
    await user.type(textarea, 'Line 1{enter}Line 2');

    expect(textarea).toHaveValue('Line 1\nLine 2');
  });

  it('forwards ref to textarea element', () => {
    const ref = vi.fn();
    render(<FormTextarea ref={ref} name="message" label="Message" />);

    expect(ref).toHaveBeenCalled();
    expect(ref.mock.calls[0][0]).toBeInstanceOf(HTMLTextAreaElement);
  });
});

describe('FormSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseFormStatus.mockReturnValue({ pending: false });
  });

  it('renders select with label and options', () => {
    render(
      <FormSelect name="country" label="Country">
        <option value="">Select...</option>
        <option value="us">United States</option>
        <option value="uk">United Kingdom</option>
      </FormSelect>
    );

    expect(screen.getByLabelText(/country/i)).toBeInstanceOf(HTMLSelectElement);
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('shows error message', () => {
    render(
      <FormSelect name="country" label="Country" error="Please select a country">
        <option value="">Select...</option>
      </FormSelect>
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Please select a country');
  });

  it('is disabled when form is pending', () => {
    mockUseFormStatus.mockReturnValue({ pending: true });

    render(
      <FormSelect name="country" label="Country">
        <option value="">Select...</option>
      </FormSelect>
    );

    expect(screen.getByLabelText(/country/i)).toBeDisabled();
  });

  it('allows selection', async () => {
    const user = userEvent.setup();

    render(
      <FormSelect name="country" label="Country">
        <option value="">Select...</option>
        <option value="us">United States</option>
        <option value="uk">United Kingdom</option>
      </FormSelect>
    );

    const select = screen.getByLabelText(/country/i);
    await user.selectOptions(select, 'us');

    expect(select).toHaveValue('us');
  });

  it('forwards ref to select element', () => {
    const ref = vi.fn();
    render(
      <FormSelect ref={ref} name="country" label="Country">
        <option value="">Select...</option>
      </FormSelect>
    );

    expect(ref).toHaveBeenCalled();
    expect(ref.mock.calls[0][0]).toBeInstanceOf(HTMLSelectElement);
  });
});
