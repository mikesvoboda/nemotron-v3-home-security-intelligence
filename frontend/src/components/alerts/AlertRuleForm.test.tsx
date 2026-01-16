/**
 * Tests for AlertRuleForm component
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AlertRuleForm, { type AlertRuleFormData } from './AlertRuleForm';

import type { Camera } from '../../services/api';

// Mock cameras for testing
const mockCameras: Camera[] = [
  {
    id: 'cam1',
    name: 'Front Door',
    folder_path: '/cameras/front',
    status: 'online',
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'cam2',
    name: 'Backyard',
    folder_path: '/cameras/back',
    status: 'online',
    created_at: '2025-01-01T00:00:00Z',
  },
];

describe('AlertRuleForm', () => {
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
    it('should render all form sections', () => {
      render(<AlertRuleForm {...defaultProps} />);

      // Basic Information section
      expect(screen.getByText('Basic Information')).toBeInTheDocument();
      expect(screen.getByLabelText('Rule Name *')).toBeInTheDocument();
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
      expect(screen.getByLabelText('Cooldown (seconds)')).toBeInTheDocument();
      expect(screen.getByText('Notification Channels')).toBeInTheDocument();
    });

    it('should render submit and cancel buttons', () => {
      render(<AlertRuleForm {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Save Rule' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    it('should use default values when no initial data is provided', () => {
      render(<AlertRuleForm {...defaultProps} />);

      const nameInput = screen.getByTestId<HTMLInputElement>('alert-rule-name-input');
      expect(nameInput.value).toBe('');

      const severitySelect = screen.getByTestId<HTMLSelectElement>('alert-rule-severity-select');
      expect(severitySelect.value).toBe('medium');

      const cooldownInput = screen.getByTestId<HTMLInputElement>('alert-rule-cooldown-input');
      expect(cooldownInput.value).toBe('300');
    });

    it('should use initial data when provided', () => {
      const initialData: Partial<AlertRuleFormData> = {
        name: 'Test Rule',
        description: 'A test description',
        enabled: false,
        severity: 'high',
        risk_threshold: 70,
        cooldown_seconds: 600,
      };

      render(<AlertRuleForm {...defaultProps} initialData={initialData} />);

      const nameInput = screen.getByTestId<HTMLInputElement>('alert-rule-name-input');
      expect(nameInput.value).toBe('Test Rule');

      const severitySelect = screen.getByTestId<HTMLSelectElement>('alert-rule-severity-select');
      expect(severitySelect.value).toBe('high');

      const cooldownInput = screen.getByTestId<HTMLInputElement>('alert-rule-cooldown-input');
      expect(cooldownInput.value).toBe('600');
    });

    it('should display custom submit text', () => {
      render(<AlertRuleForm {...defaultProps} submitText="Create Rule" />);

      expect(screen.getByRole('button', { name: 'Create Rule' })).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('should show error when name is empty', async () => {
      render(<AlertRuleForm {...defaultProps} />);

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name is required')).toBeInTheDocument();
      });
      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });

    it('should accept single character name (aligned with backend min_length=1)', async () => {
      const onSubmit = vi.fn();
      render(<AlertRuleForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByTestId('alert-rule-name-input');
      await userEvent.type(nameInput, 'A');

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalled();
      });
    });

    it('should trim whitespace from name', async () => {
      const onSubmit = vi.fn();
      render(<AlertRuleForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByTestId('alert-rule-name-input');
      await userEvent.type(nameInput, '  Test Rule  ');

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: 'Test Rule' }));
      });
    });
  });

  describe('Severity Selection', () => {
    it('should have all severity options', () => {
      render(<AlertRuleForm {...defaultProps} />);

      const severitySelect = screen.getByTestId('alert-rule-severity-select');

      expect(severitySelect).toContainHTML('Low');
      expect(severitySelect).toContainHTML('Medium');
      expect(severitySelect).toContainHTML('High');
      expect(severitySelect).toContainHTML('Critical');
    });

    it('should update severity when selection changes', async () => {
      const onSubmit = vi.fn();
      render(<AlertRuleForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByTestId('alert-rule-name-input');
      await userEvent.type(nameInput, 'Test Rule');

      const severitySelect = screen.getByTestId('alert-rule-severity-select');
      await userEvent.selectOptions(severitySelect, 'critical');

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ severity: 'critical' }));
      });
    });
  });

  describe('Object Types Selection', () => {
    it('should render all object type buttons', () => {
      render(<AlertRuleForm {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'person' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'vehicle' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'animal' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'package' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'face' })).toBeInTheDocument();
    });

    it('should toggle object type selection', async () => {
      const onSubmit = vi.fn();
      render(<AlertRuleForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByTestId('alert-rule-name-input');
      await userEvent.type(nameInput, 'Test Rule');

      // Select person and vehicle
      const personButton = screen.getByRole('button', { name: 'person' });
      const vehicleButton = screen.getByRole('button', { name: 'vehicle' });

      await userEvent.click(personButton);
      await userEvent.click(vehicleButton);

      // Verify they're selected (have bg-primary class)
      expect(personButton).toHaveClass('bg-primary');
      expect(vehicleButton).toHaveClass('bg-primary');

      // Deselect person
      await userEvent.click(personButton);
      expect(personButton).not.toHaveClass('bg-primary');

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ object_types: ['vehicle'] })
        );
      });
    });
  });

  describe('Cameras Selection', () => {
    it('should show loading state when cameras are loading', () => {
      render(<AlertRuleForm {...defaultProps} camerasLoading={true} />);

      expect(screen.getByText('Loading cameras...')).toBeInTheDocument();
    });

    it('should show error state when cameras fail to load', () => {
      const onRetryCameras = vi.fn();
      render(
        <AlertRuleForm
          {...defaultProps}
          camerasError="Failed to load cameras"
          onRetryCameras={onRetryCameras}
        />
      );

      expect(screen.getByTestId('cameras-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load cameras.')).toBeInTheDocument();

      const retryButton = screen.getByTestId('cameras-retry-button');
      expect(retryButton).toBeInTheDocument();
    });

    it('should call onRetryCameras when retry button is clicked', async () => {
      const onRetryCameras = vi.fn();
      render(
        <AlertRuleForm
          {...defaultProps}
          camerasError="Failed to load cameras"
          onRetryCameras={onRetryCameras}
        />
      );

      const retryButton = screen.getByTestId('cameras-retry-button');
      await userEvent.click(retryButton);

      expect(onRetryCameras).toHaveBeenCalled();
    });

    it('should show "No cameras available" when no cameras exist', () => {
      render(<AlertRuleForm {...defaultProps} cameras={[]} />);

      expect(screen.getByText('No cameras available')).toBeInTheDocument();
    });

    it('should render camera buttons when cameras are provided', () => {
      render(<AlertRuleForm {...defaultProps} cameras={mockCameras} />);

      expect(screen.getByRole('button', { name: 'Front Door' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Backyard' })).toBeInTheDocument();
    });

    it('should toggle camera selection', async () => {
      const onSubmit = vi.fn();
      render(<AlertRuleForm {...defaultProps} onSubmit={onSubmit} cameras={mockCameras} />);

      const nameInput = screen.getByTestId('alert-rule-name-input');
      await userEvent.type(nameInput, 'Test Rule');

      const frontDoorButton = screen.getByRole('button', { name: 'Front Door' });
      await userEvent.click(frontDoorButton);

      expect(frontDoorButton).toHaveClass('bg-primary');

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ camera_ids: ['cam1'] }));
      });
    });
  });

  describe('Schedule Configuration', () => {
    it('should not show schedule fields by default', () => {
      render(<AlertRuleForm {...defaultProps} />);

      expect(screen.queryByTestId('alert-rule-start-time-input')).not.toBeInTheDocument();
      expect(screen.queryByTestId('alert-rule-end-time-input')).not.toBeInTheDocument();
      expect(screen.queryByTestId('alert-rule-timezone-select')).not.toBeInTheDocument();
    });

    it('should show schedule fields when schedule is enabled', async () => {
      render(<AlertRuleForm {...defaultProps} initialData={{ schedule_enabled: true }} />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-rule-start-time-input')).toBeInTheDocument();
        expect(screen.getByTestId('alert-rule-end-time-input')).toBeInTheDocument();
        expect(screen.getByTestId('alert-rule-timezone-select')).toBeInTheDocument();
      });
    });

    it('should render day selection buttons when schedule is enabled', async () => {
      render(<AlertRuleForm {...defaultProps} initialData={{ schedule_enabled: true }} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Mon' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Tue' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Wed' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Thu' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Fri' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Sat' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Sun' })).toBeInTheDocument();
      });
    });

    it('should toggle day selection', async () => {
      const onSubmit = vi.fn();
      render(
        <AlertRuleForm
          {...defaultProps}
          onSubmit={onSubmit}
          initialData={{ schedule_enabled: true }}
        />
      );

      const nameInput = screen.getByTestId('alert-rule-name-input');
      await userEvent.type(nameInput, 'Test Rule');

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Mon' })).toBeInTheDocument();
      });

      const mondayButton = screen.getByRole('button', { name: 'Mon' });
      const fridayButton = screen.getByRole('button', { name: 'Fri' });

      await userEvent.click(mondayButton);
      await userEvent.click(fridayButton);

      expect(mondayButton).toHaveClass('bg-primary');
      expect(fridayButton).toHaveClass('bg-primary');

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

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
      render(<AlertRuleForm {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'email' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'webhook' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'pushover' })).toBeInTheDocument();
    });

    it('should toggle channel selection', async () => {
      const onSubmit = vi.fn();
      render(<AlertRuleForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByTestId('alert-rule-name-input');
      await userEvent.type(nameInput, 'Test Rule');

      const emailButton = screen.getByRole('button', { name: 'email' });
      const pushoverButton = screen.getByRole('button', { name: 'pushover' });

      await userEvent.click(emailButton);
      await userEvent.click(pushoverButton);

      expect(emailButton).toHaveClass('bg-primary');
      expect(pushoverButton).toHaveClass('bg-primary');

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ channels: ['email', 'pushover'] })
        );
      });
    });
  });

  describe('Form Submission', () => {
    it('should call onSubmit with form data when valid', async () => {
      const onSubmit = vi.fn();
      render(<AlertRuleForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByTestId('alert-rule-name-input');
      await userEvent.type(nameInput, 'My Alert Rule');

      const severitySelect = screen.getByTestId('alert-rule-severity-select');
      await userEvent.selectOptions(severitySelect, 'high');

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'My Alert Rule',
            severity: 'high',
            enabled: true,
          })
        );
      });
    });

    it('should show "Saving..." when isSubmitting is true', () => {
      render(<AlertRuleForm {...defaultProps} isSubmitting={true} />);

      expect(screen.getByRole('button', { name: /Saving/ })).toBeInTheDocument();
    });

    it('should disable all inputs when isSubmitting', () => {
      render(<AlertRuleForm {...defaultProps} isSubmitting={true} />);

      expect(screen.getByTestId('alert-rule-name-input')).toBeDisabled();
      expect(screen.getByTestId('alert-rule-severity-select')).toBeDisabled();
      expect(screen.getByTestId('alert-rule-cooldown-input')).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    });
  });

  describe('Form Cancellation', () => {
    it('should call onCancel when cancel button is clicked', async () => {
      const onCancel = vi.fn();
      render(<AlertRuleForm {...defaultProps} onCancel={onCancel} />);

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await userEvent.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
    });

    it('should not submit form when cancel is clicked', async () => {
      const onSubmit = vi.fn();
      const onCancel = vi.fn();
      render(<AlertRuleForm {...defaultProps} onSubmit={onSubmit} onCancel={onCancel} />);

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await userEvent.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
      expect(onSubmit).not.toHaveBeenCalled();
    });
  });

  describe('API Error Display', () => {
    it('should display API error when provided', () => {
      render(<AlertRuleForm {...defaultProps} apiError="Something went wrong" />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('should clear API error when dismiss button is clicked', async () => {
      const onClearApiError = vi.fn();
      render(
        <AlertRuleForm
          {...defaultProps}
          apiError="Something went wrong"
          onClearApiError={onClearApiError}
        />
      );

      const dismissButton = screen.getByLabelText('Dismiss error');
      await userEvent.click(dismissButton);

      expect(onClearApiError).toHaveBeenCalled();
    });

    it('should not show dismiss button if onClearApiError is not provided', () => {
      render(<AlertRuleForm {...defaultProps} apiError="Something went wrong" />);

      expect(screen.queryByLabelText('Dismiss error')).not.toBeInTheDocument();
    });
  });

  describe('Initial Data Updates', () => {
    it('should update form when initialData changes', async () => {
      const { rerender } = render(<AlertRuleForm {...defaultProps} />);

      const nameInput = screen.getByTestId<HTMLInputElement>('alert-rule-name-input');
      expect(nameInput.value).toBe('');

      rerender(<AlertRuleForm {...defaultProps} initialData={{ name: 'Updated Rule' }} />);

      await waitFor(() => {
        expect(nameInput.value).toBe('Updated Rule');
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for all inputs', () => {
      render(<AlertRuleForm {...defaultProps} />);

      expect(screen.getByLabelText('Rule Name *')).toBeInTheDocument();
      expect(screen.getByLabelText('Description')).toBeInTheDocument();
      expect(screen.getByLabelText('Severity')).toBeInTheDocument();
      expect(screen.getByLabelText(/Risk Threshold/)).toBeInTheDocument();
      expect(screen.getByLabelText(/Min Confidence/)).toBeInTheDocument();
      expect(screen.getByLabelText('Cooldown (seconds)')).toBeInTheDocument();
    });

    it('should show error styling on invalid name input', async () => {
      render(<AlertRuleForm {...defaultProps} />);

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        const nameInput = screen.getByTestId('alert-rule-name-input');
        expect(nameInput).toHaveClass('border-red-500');
      });
    });
  });

  describe('Enabled Toggle', () => {
    it('should toggle enabled state', async () => {
      const onSubmit = vi.fn();
      render(<AlertRuleForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByTestId('alert-rule-name-input');
      await userEvent.type(nameInput, 'Test Rule');

      // Find the status toggle (first switch in the form)
      const statusSection = screen.getByText('Status').closest('div');
      const toggle = within(statusSection!).getByRole('switch');

      // Initially enabled
      expect(toggle).toHaveAttribute('aria-label', 'Rule status: enabled');

      await userEvent.click(toggle);

      // Now disabled
      expect(toggle).toHaveAttribute('aria-label', 'Rule status: disabled');

      const submitButton = screen.getByTestId('alert-rule-form-submit');
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ enabled: false }));
      });
    });
  });
});
