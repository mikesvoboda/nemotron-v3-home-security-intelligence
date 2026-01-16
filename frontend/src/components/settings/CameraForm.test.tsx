/**
 * Tests for CameraForm component.
 *
 * Tests validation rules aligned with backend Pydantic schemas:
 * - Name: min_length=1, max_length=255
 * - Folder path: min_length=1, max_length=500, no path traversal, no forbidden chars
 * - Status: enum (online, offline, error, unknown)
 *
 * @see frontend/src/schemas/camera.ts - Zod validation schemas
 * @see backend/api/schemas/camera.py - Backend Pydantic schemas
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CameraForm, { type CameraFormData } from './CameraForm';

describe('CameraForm', () => {
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
    it('should render all form fields', () => {
      render(<CameraForm {...defaultProps} />);

      expect(screen.getByLabelText('Camera Name')).toBeInTheDocument();
      expect(screen.getByLabelText('Folder Path')).toBeInTheDocument();
      expect(screen.getByLabelText('Status')).toBeInTheDocument();
    });

    it('should render submit and cancel buttons', () => {
      render(<CameraForm {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Save Camera' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    it('should use default values when no initial data is provided', () => {
      render(<CameraForm {...defaultProps} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>('Camera Name');
      expect(nameInput.value).toBe('');

      const folderPathInput = screen.getByLabelText<HTMLInputElement>('Folder Path');
      expect(folderPathInput.value).toBe('');

      const statusSelect = screen.getByLabelText<HTMLSelectElement>('Status');
      expect(statusSelect.value).toBe('online');
    });

    it('should use initial data when provided', () => {
      const initialData: Partial<CameraFormData> = {
        name: 'Test Camera',
        folder_path: '/export/foscam/test',
        status: 'offline',
      };

      render(<CameraForm {...defaultProps} initialData={initialData} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>('Camera Name');
      expect(nameInput.value).toBe('Test Camera');

      const folderPathInput = screen.getByLabelText<HTMLInputElement>('Folder Path');
      expect(folderPathInput.value).toBe('/export/foscam/test');

      const statusSelect = screen.getByLabelText<HTMLSelectElement>('Status');
      expect(statusSelect.value).toBe('offline');
    });

    it('should display custom submit text', () => {
      render(<CameraForm {...defaultProps} submitText="Add Camera" />);

      expect(screen.getByRole('button', { name: 'Add Camera' })).toBeInTheDocument();
    });
  });

  describe('Name Validation (aligned with backend min_length=1, max_length=255)', () => {
    it('should show error when name is empty', async () => {
      render(<CameraForm {...defaultProps} />);

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/foscam/test');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name is required')).toBeInTheDocument();
      });
      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });

    it('should accept single character name (min_length=1)', async () => {
      const onSubmit = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'A');

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/foscam/test');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: 'A' }));
      });
    });

    it('should trim whitespace from name', async () => {
      const onSubmit = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, '  Front Door  ');

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/foscam/test');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: 'Front Door' }));
      });
    });

    it('should enforce max_length (255) via HTML maxLength attribute', () => {
      // The HTML maxLength attribute prevents typing more than 255 characters,
      // so we verify the attribute is set correctly rather than testing overflow validation
      render(<CameraForm {...defaultProps} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>('Camera Name');
      expect(nameInput).toHaveAttribute('maxLength', '255');
    });

    it('should accept name at exactly max_length (255)', async () => {
      const onSubmit = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Camera Name');
      const maxLengthName = 'a'.repeat(255);
      await userEvent.type(nameInput, maxLengthName);

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/foscam/test');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ name: maxLengthName }));
      });
    });
  });

  describe('Folder Path Validation (aligned with backend)', () => {
    it('should show error when folder path is empty', async () => {
      render(<CameraForm {...defaultProps} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'Test Camera');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Folder path is required')).toBeInTheDocument();
      });
      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });

    it('should accept valid folder paths', async () => {
      const onSubmit = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'Test Camera');

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/foscam/front_door');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ folder_path: '/export/foscam/front_door' })
        );
      });
    });

    it('should trim whitespace from folder path', async () => {
      const onSubmit = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'Test Camera');

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '  /export/foscam/test  ');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ folder_path: '/export/foscam/test' })
        );
      });
    });

    it('should reject path traversal attempts (..)', async () => {
      render(<CameraForm {...defaultProps} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'Test Camera');

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/../etc/passwd');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(
          screen.getByText('Path traversal (..) is not allowed in folder path')
        ).toBeInTheDocument();
      });
      expect(defaultProps.onSubmit).not.toHaveBeenCalled();
    });

    it.each(['<', '>', ':', '"', '|', '?', '*'])(
      'should reject forbidden character: %s',
      async (char) => {
        render(<CameraForm {...defaultProps} />);

        const nameInput = screen.getByLabelText('Camera Name');
        await userEvent.type(nameInput, 'Test Camera');

        const folderPathInput = screen.getByLabelText('Folder Path');
        await userEvent.type(folderPathInput, `/export/test${char}folder`);

        const submitButton = screen.getByRole('button', { name: 'Save Camera' });
        await userEvent.click(submitButton);

        await waitFor(() => {
          expect(
            screen.getByText(
              'Folder path contains forbidden characters (< > : " | ? * or control characters)'
            )
          ).toBeInTheDocument();
        });
        expect(defaultProps.onSubmit).not.toHaveBeenCalled();
      }
    );

    it('should enforce max_length (500) via HTML maxLength attribute', () => {
      // The HTML maxLength attribute prevents typing more than 500 characters,
      // so we verify the attribute is set correctly rather than testing overflow validation
      render(<CameraForm {...defaultProps} />);

      const folderPathInput = screen.getByLabelText<HTMLInputElement>('Folder Path');
      expect(folderPathInput).toHaveAttribute('maxLength', '500');
    });

    it('should accept folder path at exactly max_length (500)', async () => {
      const onSubmit = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'Test Camera');

      const folderPathInput = screen.getByLabelText('Folder Path');
      const maxLengthPath = '/export/' + 'a'.repeat(492); // Total 500 chars
      await userEvent.type(folderPathInput, maxLengthPath);

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(
          expect.objectContaining({ folder_path: maxLengthPath })
        );
      });
    });
  });

  describe('Status Validation (aligned with backend CameraStatus enum)', () => {
    it('should have all status options', () => {
      render(<CameraForm {...defaultProps} />);

      const statusSelect = screen.getByLabelText('Status');

      expect(statusSelect).toContainHTML('Online');
      expect(statusSelect).toContainHTML('Offline');
      expect(statusSelect).toContainHTML('Error');
      expect(statusSelect).toContainHTML('Unknown');
    });

    it('should default to "online" status', () => {
      render(<CameraForm {...defaultProps} />);

      const statusSelect = screen.getByLabelText<HTMLSelectElement>('Status');
      expect(statusSelect.value).toBe('online');
    });

    it('should update status when selection changes', async () => {
      const onSubmit = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'Test Camera');

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/foscam/test');

      const statusSelect = screen.getByLabelText('Status');
      await userEvent.selectOptions(statusSelect, 'offline');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ status: 'offline' }));
      });
    });

    it('should accept "unknown" status (NEM-2296)', async () => {
      const onSubmit = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'Test Camera');

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/foscam/test');

      const statusSelect = screen.getByLabelText('Status');
      await userEvent.selectOptions(statusSelect, 'unknown');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ status: 'unknown' }));
      });
    });
  });

  describe('Form Submission', () => {
    it('should call onSubmit with form data when valid', async () => {
      const onSubmit = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} />);

      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'Front Door');

      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/foscam/front_door');

      const statusSelect = screen.getByLabelText('Status');
      await userEvent.selectOptions(statusSelect, 'online');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          name: 'Front Door',
          folder_path: '/export/foscam/front_door',
          status: 'online',
        });
      });
    });

    it('should show "Saving..." when isSubmitting is true', () => {
      render(<CameraForm {...defaultProps} isSubmitting={true} />);

      expect(screen.getByRole('button', { name: 'Saving...' })).toBeInTheDocument();
    });

    it('should disable all inputs when isSubmitting', () => {
      render(<CameraForm {...defaultProps} isSubmitting={true} />);

      expect(screen.getByLabelText('Camera Name')).toBeDisabled();
      expect(screen.getByLabelText('Folder Path')).toBeDisabled();
      expect(screen.getByLabelText('Status')).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    });
  });

  describe('Form Cancellation', () => {
    it('should call onCancel when cancel button is clicked', async () => {
      const onCancel = vi.fn();
      render(<CameraForm {...defaultProps} onCancel={onCancel} />);

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await userEvent.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
    });

    it('should not submit form when cancel is clicked', async () => {
      const onSubmit = vi.fn();
      const onCancel = vi.fn();
      render(<CameraForm {...defaultProps} onSubmit={onSubmit} onCancel={onCancel} />);

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await userEvent.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
      expect(onSubmit).not.toHaveBeenCalled();
    });
  });

  describe('API Error Display', () => {
    it('should display API error when provided', () => {
      render(<CameraForm {...defaultProps} apiError="Camera with this name already exists" />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Camera with this name already exists')).toBeInTheDocument();
    });

    it('should show dismiss button when onClearApiError is provided', () => {
      const onClearApiError = vi.fn();
      render(
        <CameraForm {...defaultProps} apiError="Some error" onClearApiError={onClearApiError} />
      );

      expect(screen.getByLabelText('Dismiss error')).toBeInTheDocument();
    });

    it('should call onClearApiError when dismiss button is clicked', async () => {
      const onClearApiError = vi.fn();
      render(
        <CameraForm {...defaultProps} apiError="Some error" onClearApiError={onClearApiError} />
      );

      const dismissButton = screen.getByLabelText('Dismiss error');
      await userEvent.click(dismissButton);

      expect(onClearApiError).toHaveBeenCalled();
    });

    it('should not show dismiss button when onClearApiError is not provided', () => {
      render(<CameraForm {...defaultProps} apiError="Some error" />);

      expect(screen.queryByLabelText('Dismiss error')).not.toBeInTheDocument();
    });
  });

  describe('Initial Data Updates', () => {
    it('should update form when initialData changes', async () => {
      const { rerender } = render(<CameraForm {...defaultProps} />);

      const nameInput = screen.getByLabelText<HTMLInputElement>('Camera Name');
      expect(nameInput.value).toBe('');

      rerender(
        <CameraForm
          {...defaultProps}
          initialData={{
            name: 'Updated Camera',
            folder_path: '/export/foscam/updated',
            status: 'error',
          }}
        />
      );

      await waitFor(() => {
        expect(nameInput.value).toBe('Updated Camera');
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for all inputs', () => {
      render(<CameraForm {...defaultProps} />);

      expect(screen.getByLabelText('Camera Name')).toBeInTheDocument();
      expect(screen.getByLabelText('Folder Path')).toBeInTheDocument();
      expect(screen.getByLabelText('Status')).toBeInTheDocument();
    });

    it('should show error styling on invalid name input', async () => {
      render(<CameraForm {...defaultProps} />);

      // Fill in folder path but not name
      const folderPathInput = screen.getByLabelText('Folder Path');
      await userEvent.type(folderPathInput, '/export/foscam/test');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        const nameInput = screen.getByLabelText('Camera Name');
        expect(nameInput).toHaveClass('border-red-500');
      });
    });

    it('should show error styling on invalid folder path input', async () => {
      render(<CameraForm {...defaultProps} />);

      // Fill in name but not folder path
      const nameInput = screen.getByLabelText('Camera Name');
      await userEvent.type(nameInput, 'Test Camera');

      const submitButton = screen.getByRole('button', { name: 'Save Camera' });
      await userEvent.click(submitButton);

      await waitFor(() => {
        const folderPathInput = screen.getByLabelText('Folder Path');
        expect(folderPathInput).toHaveClass('border-red-500');
      });
    });

    it('should have helper text for folder path', () => {
      render(<CameraForm {...defaultProps} />);

      expect(
        screen.getByText('File system path where camera uploads images via FTP')
      ).toBeInTheDocument();
    });
  });

  describe('Data Test IDs', () => {
    it('should have data-testid attributes for form elements', () => {
      render(<CameraForm {...defaultProps} />);

      expect(screen.getByTestId('camera-name-input')).toBeInTheDocument();
      expect(screen.getByTestId('camera-folder-path-input')).toBeInTheDocument();
      expect(screen.getByTestId('camera-status-select')).toBeInTheDocument();
      expect(screen.getByTestId('camera-form-submit')).toBeInTheDocument();
    });
  });
});
