/**
 * Tests for AlertForm component
 *
 * Tests cover:
 * - Initial rendering and form structure
 * - Form validation aligned with backend Pydantic schemas
 * - User interactions (inputs, toggles, selections)
 * - Form submission and cancellation
 * - API error display and dismissal
 * - Accessibility requirements
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AlertForm, { type AlertFormData, type CameraOption } from './AlertForm';

describe('AlertForm', () => {
  const defaultProps = {
    onSubmit: vi.fn(),
    onCancel: vi.fn(),
  };

  const mockCameras: CameraOption[] = [
    { id: 'cam-1', name: 'Front Door' },
    { id: 'cam-2', name: 'Backyard' },
    { id: 'cam-3', name: 'Garage' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial Rendering', () => {
    it('should render all form sections', () => {
      render(<AlertForm {...defaultProps} />);

      // Basic Information section
      expect(screen.getByText('Basic Information')).toBeInTheDocument();
      expect(screen.getByLabelText(/Rule Name/)).toBeInTheDocument();
      expect(screen.getByLabelText('Description')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByLabelText('Severity')).toBeInTheDocument();

      // Trigger Conditions section
      expect(screen.getByText('Trigger Conditions')).toBeInTheDocument();
      expect(screen.getByLabelText(/Risk Threshold/)).toBeInTheDocument();
      expect(screen.getByLabelText(/Min Confidence/)).toBeInTheDocument();
      expect(screen.getByText('Object Types')).toBeInTheDocument();
      expect(screen.getByText('Cameras')).toBeInTheDocument();

      // Schedule section
      expect(screen.getByText('Schedule')).toBeInTheDocument();

      // Notifications section
      expect(screen.getByText('Notifications')).toBeInTheDocument();
      expect(screen.getByText('Notification Channels')).toBeInTheDocument();
      expect(screen.getByLabelText(/Cooldown/)).toBeInTheDocument();
    });

    it('should render submit and cancel buttons', () => {
      render(<AlertForm {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Save Rule' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    it('should use default values when no initial data is provided', () => {
      render(<AlertForm {...defaultProps} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>(/Rule Name/);
      expect(nameInput.value).toBe('');

      const severitySelect = screen.getByLabelText<HTMLSelectElement>('Severity');
      expect(severitySelect.value).toBe('medium');

      // Default enabled should be true
      const enabledSwitch = screen.getAllByRole('switch')[0]; // First switch is status
      expect(enabledSwitch).toHaveAttribute('aria-checked', 'true');
    });

    it('should use initial data when provided', () => {
      const initialData: Partial<AlertFormData> = {
        name: 'Test Alert',
        description: 'Test description',
        enabled: false,
        severity: 'high',
        risk_threshold: 75,
        cooldown_seconds: 600,
      };

      render(<AlertForm {...defaultProps} initialData={initialData} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>(/Rule Name/);
      expect(nameInput.value).toBe('Test Alert');

      const descriptionInput = screen.getByLabelText<HTMLTextAreaElement>('Description');
      expect(descriptionInput.value).toBe('Test description');

      const severitySelect = screen.getByLabelText<HTMLSelectElement>('Severity');
      expect(severitySelect.value).toBe('high');

      const enabledSwitch = screen.getAllByRole('switch')[0];
      expect(enabledSwitch).toHaveAttribute('aria-checked', 'false');

      const riskInput = screen.getByLabelText<HTMLInputElement>(/Risk Threshold/);
      expect(riskInput.value).toBe('75');

      const cooldownInput = screen.getByLabelText<HTMLInputElement>(/Cooldown/);
      expect(cooldownInput.value).toBe('600');
    });

    it('should display custom submit text', () => {
      render(<AlertForm {...defaultProps} submitText="Create Rule" />);

      expect(screen.getByRole('button', { name: 'Create Rule' })).toBeInTheDocument();
    });
  });

  describe('Form Validation - Name Field', () => {
    it('should show error when name is empty (aligned with backend min_length=1)', async () => {
      const user = userEvent.setup();
      render(<AlertForm {...defaultProps} />);

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name is required')).toBeInTheDocument();
      });
      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });

    it('should accept single character name (aligned with backend min_length=1)', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'A');

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: 'A' }));
      });
    });

    it('should trim whitespace from name', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, '  Test Rule  ');

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: 'Test Rule' }));
      });
    });

    it('should fail validation for whitespace-only name', async () => {
      const user = userEvent.setup();
      render(<AlertForm {...defaultProps} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, '   ');

      // Blur to trigger validation
      await user.tab();

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name is required')).toBeInTheDocument();
      });
      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });
  });

  describe('Form Validation - Risk Threshold', () => {
    it('should accept values within range (0-100)', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      const riskInput = screen.getByLabelText(/Risk Threshold/);
      await user.clear(riskInput);
      await user.type(riskInput, '50');

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ risk_threshold: 50 }));
      });
    });

    it('should allow null/empty risk threshold', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      // Leave risk threshold empty
      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalled();
      });
    });
  });

  describe('Form Validation - Min Confidence', () => {
    it('should accept values within range (0-1)', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      const confidenceInput = screen.getByLabelText(/Min Confidence/);
      await user.clear(confidenceInput);
      await user.type(confidenceInput, '0.8');

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ min_confidence: 0.8 }));
      });
    });
  });

  describe('Form Validation - Cooldown Seconds', () => {
    it('should reject negative cooldown values (aligned with backend ge=0)', async () => {
      // Note: This test validates that the form uses initialData with negative cooldown
      // and shows the validation error. HTML number inputs with min=0 have browser
      // validation that may prevent typing negative values directly.
      const onSubmit = vi.fn();
      render(
        <AlertForm
          {...defaultProps}
          onSubmit={onSubmit}
          initialData={{ name: 'Test Rule', cooldown_seconds: -100 }}
        />
      );

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Cooldown cannot be negative')).toBeInTheDocument();
      });
      expect(onSubmit).not.toHaveBeenCalled();
    });

    it('should accept zero cooldown (edge case for ge=0)', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      const cooldownInput = screen.getByLabelText(/Cooldown/);
      await user.clear(cooldownInput);
      await user.type(cooldownInput, '0');

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ cooldown_seconds: 0 }));
      });
    });
  });

  describe('Severity Selection', () => {
    it('should have all severity options', () => {
      render(<AlertForm {...defaultProps} />);

      const severitySelect = screen.getByLabelText('Severity');
      expect(severitySelect).toContainHTML('Low');
      expect(severitySelect).toContainHTML('Medium');
      expect(severitySelect).toContainHTML('High');
      expect(severitySelect).toContainHTML('Critical');
    });

    it('should update severity when selection changes', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      const severitySelect = screen.getByLabelText('Severity');
      await user.selectOptions(severitySelect, 'critical');

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ severity: 'critical' }));
      });
    });
  });

  describe('Object Types Selection', () => {
    it('should render object type buttons', () => {
      render(<AlertForm {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'person' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'vehicle' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'animal' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'package' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'face' })).toBeInTheDocument();
    });

    it('should toggle object types when clicked', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      const personButton = screen.getByRole('button', { name: 'person' });
      const vehicleButton = screen.getByRole('button', { name: 'vehicle' });

      await user.click(personButton);
      await user.click(vehicleButton);

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ object_types: ['person', 'vehicle'] })
        );
      });
    });

    it('should deselect object type when clicked again', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(
        <AlertForm
          {...defaultProps}
          onSubmit={onSubmit}
          initialData={{ object_types: ['person', 'vehicle'] }}
        />
      );

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      // Deselect person
      const personButton = screen.getByRole('button', { name: 'person' });
      await user.click(personButton);

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ object_types: ['vehicle'] })
        );
      });
    });
  });

  describe('Camera Selection', () => {
    it('should display no cameras message when cameras array is empty', () => {
      render(<AlertForm {...defaultProps} cameras={[]} />);

      expect(screen.getByText('No cameras available')).toBeInTheDocument();
    });

    it('should render camera buttons when cameras are provided', () => {
      render(<AlertForm {...defaultProps} cameras={mockCameras} />);

      expect(screen.getByRole('button', { name: 'Front Door' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Backyard' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Garage' })).toBeInTheDocument();
    });

    it('should toggle camera selection when clicked', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} cameras={mockCameras} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      const frontDoorButton = screen.getByRole('button', { name: 'Front Door' });
      await user.click(frontDoorButton);

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ camera_ids: ['cam-1'] })
        );
      });
    });
  });

  describe('Schedule Configuration', () => {
    it('should not show schedule options when disabled', () => {
      render(<AlertForm {...defaultProps} />);

      expect(screen.queryByLabelText('Start Time')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('End Time')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Timezone')).not.toBeInTheDocument();
    });

    it('should show schedule options when enabled', async () => {
      const user = userEvent.setup();
      render(<AlertForm {...defaultProps} />);

      // Schedule toggle is the second switch
      const switches = screen.getAllByRole('switch');
      const scheduleToggle = switches[1];

      await user.click(scheduleToggle);

      expect(screen.getByLabelText('Start Time')).toBeInTheDocument();
      expect(screen.getByLabelText('End Time')).toBeInTheDocument();
      expect(screen.getByLabelText('Timezone')).toBeInTheDocument();
    });

    it('should render day selection buttons when schedule is enabled', async () => {
      const user = userEvent.setup();
      render(<AlertForm {...defaultProps} />);

      const switches = screen.getAllByRole('switch');
      await user.click(switches[1]);

      expect(screen.getByRole('button', { name: 'Mon' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Tue' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Wed' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Thu' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Fri' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Sat' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Sun' })).toBeInTheDocument();
    });

    it('should toggle day selection when clicked', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      // Enable schedule
      const switches = screen.getAllByRole('switch');
      await user.click(switches[1]);

      // Select Monday and Friday
      await user.click(screen.getByRole('button', { name: 'Mon' }));
      await user.click(screen.getByRole('button', { name: 'Fri' }));

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            schedule_enabled: true,
            schedule_days: ['monday', 'friday'],
          })
        );
      });
    });
  });

  describe('Notification Channels', () => {
    it('should render channel buttons', () => {
      render(<AlertForm {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'email' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'webhook' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'pushover' })).toBeInTheDocument();
    });

    it('should toggle channels when clicked', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      await user.click(screen.getByRole('button', { name: 'email' }));
      await user.click(screen.getByRole('button', { name: 'pushover' }));

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ channels: ['email', 'pushover'] })
        );
      });
    });
  });

  describe('Enabled Toggle', () => {
    it('should toggle enabled state when clicked', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText(/Rule Name/);
      await user.type(nameInput, 'Test Rule');

      const enabledSwitch = screen.getAllByRole('switch')[0];

      // Initially true
      expect(enabledSwitch).toHaveAttribute('aria-checked', 'true');

      await user.click(enabledSwitch);

      // Now false
      expect(enabledSwitch).toHaveAttribute('aria-checked', 'false');

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ enabled: false }));
      });
    });
  });

  describe('Form Submission', () => {
    it('should call onSubmit with complete form data when valid', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} cameras={mockCameras} />);

      await user.type(screen.getByLabelText(/Rule Name/), 'Test Alert');
      await user.type(screen.getByLabelText('Description'), 'Test description');
      await user.selectOptions(screen.getByLabelText('Severity'), 'high');
      await user.type(screen.getByLabelText(/Risk Threshold/), '75');
      await user.click(screen.getByRole('button', { name: 'person' }));
      await user.click(screen.getByRole('button', { name: 'Front Door' }));
      await user.click(screen.getByRole('button', { name: 'email' }));

      await user.click(screen.getByRole('button', { name: 'Save Rule' }));

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          name: 'Test Alert',
          description: 'Test description',
          enabled: true,
          severity: 'high',
          risk_threshold: 75,
          min_confidence: null,
          object_types: ['person'],
          camera_ids: ['cam-1'],
          schedule_enabled: false,
          schedule_days: [],
          schedule_start_time: '22:00',
          schedule_end_time: '06:00',
          schedule_timezone: 'UTC',
          cooldown_seconds: 300,
          channels: ['email'],
        });
      });
    });

    it('should show "Saving..." when isSubmitting is true', () => {
      render(<AlertForm {...defaultProps} isSubmitting={true} />);

      expect(screen.getByRole('button', { name: 'Saving...' })).toBeInTheDocument();
    });

    it('should disable all inputs when isSubmitting', () => {
      render(<AlertForm {...defaultProps} isSubmitting={true} cameras={mockCameras} />);

      expect(screen.getByLabelText(/Rule Name/)).toBeDisabled();
      expect(screen.getByLabelText('Description')).toBeDisabled();
      expect(screen.getByLabelText('Severity')).toBeDisabled();
      expect(screen.getByLabelText(/Risk Threshold/)).toBeDisabled();
      expect(screen.getByLabelText(/Min Confidence/)).toBeDisabled();
      expect(screen.getByLabelText(/Cooldown/)).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    });
  });

  describe('Form Cancellation', () => {
    it('should call onCancel when cancel button is clicked', async () => {
      const user = userEvent.setup();
      const onCancel = vi.fn();
      render(<AlertForm {...defaultProps} onCancel={onCancel} />);

      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      expect(onCancel).toHaveBeenCalled();
    });

    it('should not submit form when cancel is clicked', async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      const onCancel = vi.fn();
      render(<AlertForm {...defaultProps} onSubmit={onSubmit} onCancel={onCancel} />);

      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      expect(onCancel).toHaveBeenCalled();
      expect(onSubmit).not.toHaveBeenCalled();
    });
  });

  describe('API Error Display', () => {
    it('should display API error when provided', () => {
      render(<AlertForm {...defaultProps} apiError="Failed to save alert rule" />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Failed to save alert rule')).toBeInTheDocument();
    });

    it('should show dismiss button when onClearApiError is provided', () => {
      render(
        <AlertForm
          {...defaultProps}
          apiError="Failed to save"
          onClearApiError={vi.fn()}
        />
      );

      expect(screen.getByRole('button', { name: 'Dismiss error' })).toBeInTheDocument();
    });

    it('should call onClearApiError when dismiss button is clicked', async () => {
      const user = userEvent.setup();
      const onClearApiError = vi.fn();
      render(
        <AlertForm
          {...defaultProps}
          apiError="Failed to save"
          onClearApiError={onClearApiError}
        />
      );

      await user.click(screen.getByRole('button', { name: 'Dismiss error' }));

      expect(onClearApiError).toHaveBeenCalled();
    });

    it('should not display API error when null', () => {
      render(<AlertForm {...defaultProps} apiError={null} />);

      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for all inputs', () => {
      render(<AlertForm {...defaultProps} />);

      expect(screen.getByLabelText(/Rule Name/)).toBeInTheDocument();
      expect(screen.getByLabelText('Description')).toBeInTheDocument();
      expect(screen.getByLabelText('Severity')).toBeInTheDocument();
      expect(screen.getByLabelText(/Risk Threshold/)).toBeInTheDocument();
      expect(screen.getByLabelText(/Min Confidence/)).toBeInTheDocument();
      expect(screen.getByLabelText(/Cooldown/)).toBeInTheDocument();
    });

    it('should have proper aria-checked attribute on switches', () => {
      render(<AlertForm {...defaultProps} />);

      const switches = screen.getAllByRole('switch');
      expect(switches[0]).toHaveAttribute('aria-checked');
      expect(switches[1]).toHaveAttribute('aria-checked');
    });

    it('should show error styling on invalid inputs', async () => {
      const user = userEvent.setup();
      render(<AlertForm {...defaultProps} />);

      const submitButton = screen.getByRole('button', { name: 'Save Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        const nameInput = screen.getByLabelText(/Rule Name/);
        expect(nameInput).toHaveClass('border-red-500');
      });
    });

    it('should mark required field with asterisk', () => {
      render(<AlertForm {...defaultProps} />);

      // The Rule Name label should have a required indicator
      const nameLabel = screen.getByText(/Rule Name/);
      expect(nameLabel.closest('label')).toContainHTML('*');
    });
  });

  describe('Initial Data Updates', () => {
    it('should update form when initialData changes', async () => {
      const { rerender } = render(<AlertForm {...defaultProps} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>(/Rule Name/);
      expect(nameInput.value).toBe('');

      rerender(
        <AlertForm {...defaultProps} initialData={{ name: 'Updated Alert' }} />
      );

      await waitFor(() => {
        expect(nameInput.value).toBe('Updated Alert');
      });
    });
  });
});
