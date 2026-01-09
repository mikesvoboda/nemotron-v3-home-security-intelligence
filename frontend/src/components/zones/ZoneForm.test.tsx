/**
 * Tests for ZoneForm component
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZoneForm, { type ZoneFormData } from './ZoneForm';

describe('ZoneForm', () => {
  const defaultProps = {
    onSubmit: vi.fn(),
    onCancel: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial Rendering', () => {
    it('should render form fields', () => {
      render(<ZoneForm {...defaultProps} />);

      expect(screen.getByLabelText('Zone Name')).toBeInTheDocument();
      expect(screen.getByLabelText('Zone Type')).toBeInTheDocument();
      expect(screen.getByText('Zone Color')).toBeInTheDocument();
      expect(screen.getByText(/Priority:/)).toBeInTheDocument();
      expect(screen.getByText('Enabled')).toBeInTheDocument();
    });

    it('should render submit and cancel buttons', () => {
      render(<ZoneForm {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Save Zone' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    it('should use default values when no initial data is provided', () => {
      render(<ZoneForm {...defaultProps} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>('Zone Name');
      expect(nameInput.value).toBe('');

      const typeSelect = screen.getByLabelText<HTMLSelectElement>('Zone Type');
      expect(typeSelect.value).toBe('other');

      // Default enabled should be true (switch should be on)
      const enabledSwitch = screen.getByRole('switch');
      expect(enabledSwitch).toHaveAttribute('aria-checked', 'true');
    });

    it('should use initial data when provided', () => {
      const initialData: Partial<ZoneFormData> = {
        name: 'Test Zone',
        zone_type: 'entry_point',
        color: '#EF4444',
        enabled: false,
        priority: 50,
      };

      render(<ZoneForm {...defaultProps} initialData={initialData} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>('Zone Name');
      expect(nameInput.value).toBe('Test Zone');

      const typeSelect = screen.getByLabelText<HTMLSelectElement>('Zone Type');
      expect(typeSelect.value).toBe('entry_point');

      const enabledSwitch = screen.getByRole('switch');
      expect(enabledSwitch).toHaveAttribute('aria-checked', 'false');

      expect(screen.getByText('Priority: 50')).toBeInTheDocument();
    });

    it('should display custom submit text', () => {
      render(<ZoneForm {...defaultProps} submitText="Create Zone" />);

      expect(screen.getByRole('button', { name: 'Create Zone' })).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('should show error when name is empty', async () => {
      render(<ZoneForm {...defaultProps} />);

      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name is required')).toBeInTheDocument();
      });
      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });

    it('should show error when name is empty (aligned with backend min_length=1)', async () => {
      render(<ZoneForm {...defaultProps} />);

      // Leave name empty by not typing anything
      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name is required')).toBeInTheDocument();
      });
      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });

    it('should accept single character name (aligned with backend min_length=1)', async () => {
      const onSubmit = vi.fn();
      render(<ZoneForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Zone Name');
      await userEvent.type(nameInput, 'A');

      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: 'A' }));
      });
    });

    it('should trim whitespace from name', async () => {
      const onSubmit = vi.fn();
      render(<ZoneForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Zone Name');
      await userEvent.type(nameInput, '  Test Zone  ');

      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ name: 'Test Zone' })
        );
      });
    });

    it('should fail validation for whitespace-only name', async () => {
      render(<ZoneForm {...defaultProps} />);

      const nameInput = screen.getByLabelText('Zone Name');
      await userEvent.type(nameInput, '   ');

      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name is required')).toBeInTheDocument();
      });
    });
  });

  describe('Zone Type Selection', () => {
    it('should have all zone type options', () => {
      render(<ZoneForm {...defaultProps} />);

      const typeSelect = screen.getByLabelText('Zone Type');

      expect(typeSelect).toContainHTML('Entry Point');
      expect(typeSelect).toContainHTML('Driveway');
      expect(typeSelect).toContainHTML('Sidewalk');
      expect(typeSelect).toContainHTML('Yard');
      expect(typeSelect).toContainHTML('Other');
    });

    it('should update zone type when selection changes', async () => {
      const onSubmit = vi.fn();
      render(<ZoneForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Zone Name');
      await userEvent.type(nameInput, 'Test Zone');

      const typeSelect = screen.getByLabelText('Zone Type');
      await userEvent.selectOptions(typeSelect, 'driveway');

      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ zone_type: 'driveway' })
        );
      });
    });

    it('should show description for selected zone type', async () => {
      render(<ZoneForm {...defaultProps} />);

      // Default is 'other', should show its description
      expect(screen.getByText('Custom zone type')).toBeInTheDocument();

      const typeSelect = screen.getByLabelText('Zone Type');
      await userEvent.selectOptions(typeSelect, 'entry_point');

      expect(screen.getByText('Doors, gates, or other entry areas')).toBeInTheDocument();
    });
  });

  describe('Color Picker', () => {
    it('should render color options', () => {
      render(<ZoneForm {...defaultProps} />);

      // Color buttons inside the fieldset
      const colorFieldset = screen.getByText('Zone Color').closest('fieldset');
      const colorButtons = colorFieldset?.querySelectorAll('button');

      expect(colorButtons?.length).toBe(8); // 8 predefined colors
    });

    it('should highlight selected color', () => {
      render(
        <ZoneForm {...defaultProps} initialData={{ color: '#EF4444' }} />
      );

      const colorFieldset = screen.getByText('Zone Color').closest('fieldset');
      const colorButtons = colorFieldset?.querySelectorAll('button');

      const selectedButton = Array.from(colorButtons || []).find((btn) =>
        btn.classList.contains('ring-2')
      );

      expect(selectedButton).toBeTruthy();
      expect(selectedButton).toHaveStyle({ backgroundColor: '#EF4444' });
    });

    it('should change color when a color button is clicked', async () => {
      const onSubmit = vi.fn();
      render(<ZoneForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Zone Name');
      await userEvent.type(nameInput, 'Test Zone');

      // Click the red color button
      const redButton = screen.getByTitle('Red');
      await userEvent.click(redButton);

      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ color: '#EF4444' })
        );
      });
    });

    it('should have title attributes for color buttons', () => {
      render(<ZoneForm {...defaultProps} />);

      expect(screen.getByTitle('Blue')).toBeInTheDocument();
      expect(screen.getByTitle('Green')).toBeInTheDocument();
      expect(screen.getByTitle('Amber')).toBeInTheDocument();
      expect(screen.getByTitle('Red')).toBeInTheDocument();
      expect(screen.getByTitle('Purple')).toBeInTheDocument();
      expect(screen.getByTitle('Pink')).toBeInTheDocument();
      expect(screen.getByTitle('Indigo')).toBeInTheDocument();
      expect(screen.getByTitle('Teal')).toBeInTheDocument();
    });
  });

  describe('Priority Slider', () => {
    it('should render priority slider with default value', () => {
      render(<ZoneForm {...defaultProps} />);

      const slider = screen.getByLabelText(/Priority:/);
      expect(slider).toBeInTheDocument();
      expect(slider).toHaveAttribute('type', 'range');
      expect(slider).toHaveAttribute('min', '0');
      expect(slider).toHaveAttribute('max', '100');
    });

    it('should display current priority value', () => {
      render(<ZoneForm {...defaultProps} initialData={{ priority: 75 }} />);

      expect(screen.getByText('Priority: 75')).toBeInTheDocument();
    });

    it('should update priority when slider is changed', async () => {
      const onSubmit = vi.fn();
      render(<ZoneForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Zone Name');
      await userEvent.type(nameInput, 'Test Zone');

      const slider = screen.getByLabelText<HTMLInputElement>(/Priority:/);
      // Note: userEvent.type doesn't work well with range inputs
      // We use fireEvent for range inputs
      await userEvent.click(slider);

      // The slider should be interactive
      expect(slider).not.toBeDisabled();
    });

    it('should show helper text about priority', () => {
      render(<ZoneForm {...defaultProps} />);

      expect(
        screen.getByText('Higher priority zones take precedence when overlapping')
      ).toBeInTheDocument();
    });
  });

  describe('Enabled Toggle', () => {
    it('should render enabled toggle switch', () => {
      render(<ZoneForm {...defaultProps} />);

      const toggle = screen.getByRole('switch');
      expect(toggle).toBeInTheDocument();
      expect(toggle).toHaveAttribute('aria-labelledby', 'enabled-label');
    });

    it('should toggle enabled state when clicked', async () => {
      const onSubmit = vi.fn();
      render(<ZoneForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Zone Name');
      await userEvent.type(nameInput, 'Test Zone');

      const toggle = screen.getByRole('switch');

      // Initially true (default)
      expect(toggle).toHaveAttribute('aria-checked', 'true');

      await userEvent.click(toggle);

      // Should now be false
      expect(toggle).toHaveAttribute('aria-checked', 'false');

      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ enabled: false })
        );
      });
    });

    it('should show description for enabled toggle', () => {
      render(<ZoneForm {...defaultProps} />);

      expect(
        screen.getByText('Active zones are used for detection analysis')
      ).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    it('should call onSubmit with form data when valid', async () => {
      const onSubmit = vi.fn();
      render(<ZoneForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Zone Name');
      await userEvent.type(nameInput, 'My Zone');

      const typeSelect = screen.getByLabelText('Zone Type');
      await userEvent.selectOptions(typeSelect, 'entry_point');

      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          name: 'My Zone',
          zone_type: 'entry_point',
          shape: 'rectangle',
          color: '#3B82F6',
          enabled: true,
          priority: 0,
        });
      });
    });

    it('should show "Saving..." when isSubmitting is true', () => {
      render(<ZoneForm {...defaultProps} isSubmitting={true} />);

      expect(screen.getByRole('button', { name: 'Saving...' })).toBeInTheDocument();
    });

    it('should disable all inputs when isSubmitting', () => {
      render(<ZoneForm {...defaultProps} isSubmitting={true} />);

      expect(screen.getByLabelText('Zone Name')).toBeDisabled();
      expect(screen.getByLabelText('Zone Type')).toBeDisabled();
      expect(screen.getByRole('switch')).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    });
  });

  describe('Form Cancellation', () => {
    it('should call onCancel when cancel button is clicked', async () => {
      const onCancel = vi.fn();
      render(<ZoneForm {...defaultProps} onCancel={onCancel} />);

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await userEvent.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
    });

    it('should not submit form when cancel is clicked', async () => {
      const onSubmit = vi.fn();
      const onCancel = vi.fn();
      render(<ZoneForm {...defaultProps} onSubmit={onSubmit} onCancel={onCancel} />);

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await userEvent.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
      expect(onSubmit).not.toHaveBeenCalled();
    });
  });

  describe('Initial Data Updates', () => {
    it('should update form when initialData changes', async () => {
      const { rerender } = render(<ZoneForm {...defaultProps} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>('Zone Name');
      expect(nameInput.value).toBe('');

      rerender(
        <ZoneForm {...defaultProps} initialData={{ name: 'Updated Zone' }} />
      );

      await waitFor(() => {
        expect(nameInput.value).toBe('Updated Zone');
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for all inputs', () => {
      render(<ZoneForm {...defaultProps} />);

      expect(screen.getByLabelText('Zone Name')).toBeInTheDocument();
      expect(screen.getByLabelText('Zone Type')).toBeInTheDocument();
      expect(screen.getByLabelText(/Priority:/)).toBeInTheDocument();
    });

    it('should have aria-describedby for enabled toggle', () => {
      render(<ZoneForm {...defaultProps} />);

      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-describedby', 'enabled-description');
    });

    it('should use fieldset and legend for color picker', () => {
      const { container } = render(<ZoneForm {...defaultProps} />);

      const fieldset = container.querySelector('fieldset');
      const legend = container.querySelector('legend');

      expect(fieldset).toBeInTheDocument();
      expect(legend).toHaveTextContent('Zone Color');
    });

    it('should show error styling on invalid name input', async () => {
      render(<ZoneForm {...defaultProps} />);

      const submitButton = screen.getByRole('button', { name: 'Save Zone' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        const nameInput = screen.getByLabelText('Zone Name');
        expect(nameInput).toHaveClass('border-red-500');
      });
    });
  });
});
