/**
 * CameraForm component for creating and editing cameras.
 *
 * This component uses Zod validation schemas that mirror the backend Pydantic schemas
 * in backend/api/schemas/camera.py for consistent validation.
 *
 * @see frontend/src/schemas/camera.ts - Zod validation schemas
 * @see backend/api/schemas/camera.py - Backend Pydantic schemas
 */

import { zodResolver } from '@hookform/resolvers/zod';
import { clsx } from 'clsx';
import { AlertCircle, X } from 'lucide-react';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';

import {
  cameraFormSchema,
  CAMERA_FOLDER_PATH_CONSTRAINTS,
  CAMERA_NAME_CONSTRAINTS,
  CAMERA_STATUS_VALUES,
  type CameraFormInput,
  type CameraFormOutput,
  type CameraStatusValue,
} from '../../schemas/camera';

/**
 * Form data interface for camera form.
 * All fields are required for display/edit.
 */
export interface CameraFormData {
  name: string;
  folder_path: string;
  status: CameraStatusValue;
}

/**
 * Props for the CameraForm component.
 */
export interface CameraFormProps {
  /** Initial form data (for editing) */
  initialData?: Partial<CameraFormData>;
  /** Callback when form is submitted with validated data */
  onSubmit: (data: CameraFormOutput) => void;
  /** Callback when form is cancelled */
  onCancel: () => void;
  /** Whether form is in submitting state */
  isSubmitting?: boolean;
  /** Submit button text */
  submitText?: string;
  /** API error message to display */
  apiError?: string | null;
  /** Callback to clear the API error */
  onClearApiError?: () => void;
}

/** Status options with labels for display */
const STATUS_OPTIONS: { value: CameraStatusValue; label: string; description: string }[] = [
  { value: 'online', label: 'Online', description: 'Camera is active and receiving images' },
  { value: 'offline', label: 'Offline', description: 'Camera is not currently active' },
  { value: 'error', label: 'Error', description: 'Camera is experiencing an error condition' },
  { value: 'unknown', label: 'Unknown', description: 'Camera status cannot be determined' },
];

/** Default form values */
const DEFAULT_FORM_DATA: CameraFormData = {
  name: '',
  folder_path: '',
  status: 'online',
};

/**
 * CameraForm component for creating and editing cameras.
 *
 * Features:
 * - Name input with length validation (1-255 chars)
 * - Folder path input with security validation
 * - Status dropdown (online, offline, error, unknown)
 * - Real-time validation feedback
 * - API error display with dismiss
 *
 * Validation rules match backend Pydantic schemas:
 * - Name: min_length=1, max_length=255
 * - Folder path: min_length=1, max_length=500, no path traversal, no forbidden chars
 * - Status: enum (online, offline, error, unknown)
 */
export default function CameraForm({
  initialData,
  onSubmit,
  onCancel,
  isSubmitting = false,
  submitText = 'Save Camera',
  apiError,
  onClearApiError,
}: CameraFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CameraFormInput>({
    resolver: zodResolver(cameraFormSchema),
    defaultValues: {
      ...DEFAULT_FORM_DATA,
      ...initialData,
    },
    mode: 'onBlur',
  });

  // Update form when initial data changes (for edit mode)
  useEffect(() => {
    if (initialData) {
      reset({
        ...DEFAULT_FORM_DATA,
        ...initialData,
      });
    }
  }, [initialData, reset]);

  const onFormSubmit = (data: CameraFormInput) => {
    // The Zod schema transforms and validates the data
    const result = cameraFormSchema.safeParse(data);
    if (result.success) {
      onSubmit(result.data);
    }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(onFormSubmit)(e)} className="space-y-4">
      {/* API Error Display */}
      {apiError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-2"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-red-500" />
          <span className="flex-1 text-sm text-red-400">{apiError}</span>
          {onClearApiError && (
            <button
              type="button"
              onClick={onClearApiError}
              className="text-red-400 hover:text-red-300"
              aria-label="Dismiss error"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      )}

      {/* Camera Name Input */}
      <div>
        <label htmlFor="camera-name" className="block text-sm font-medium text-text-primary">
          Camera Name
        </label>
        <input
          type="text"
          id="camera-name"
          data-testid="camera-name-input"
          {...register('name')}
          maxLength={CAMERA_NAME_CONSTRAINTS.maxLength}
          className={clsx(
            'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
            errors.name
              ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
              : 'border-gray-700 focus:border-primary focus:ring-primary'
          )}
          placeholder="e.g., Front Door, Driveway"
          disabled={isSubmitting}
        />
        {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name.message}</p>}
      </div>

      {/* Folder Path Input */}
      <div>
        <label htmlFor="camera-folder-path" className="block text-sm font-medium text-text-primary">
          Folder Path
        </label>
        <input
          type="text"
          id="camera-folder-path"
          data-testid="camera-folder-path-input"
          {...register('folder_path')}
          maxLength={CAMERA_FOLDER_PATH_CONSTRAINTS.maxLength}
          className={clsx(
            'mt-1 block w-full rounded-lg border bg-card px-3 py-2 font-mono text-sm text-text-primary focus:outline-none focus:ring-2',
            errors.folder_path
              ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
              : 'border-gray-700 focus:border-primary focus:ring-primary'
          )}
          placeholder="/export/foscam/front_door"
          disabled={isSubmitting}
        />
        {errors.folder_path && (
          <p className="mt-1 text-sm text-red-500">{errors.folder_path.message}</p>
        )}
        <p className="mt-1 text-xs text-text-secondary">
          File system path where camera uploads images via FTP
        </p>
      </div>

      {/* Status Select */}
      <div>
        <label htmlFor="camera-status" className="block text-sm font-medium text-text-primary">
          Status
        </label>
        <select
          id="camera-status"
          data-testid="camera-status-select"
          {...register('status')}
          className={clsx(
            'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
            errors.status
              ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
              : 'border-gray-700 focus:border-primary focus:ring-primary'
          )}
          disabled={isSubmitting}
        >
          {CAMERA_STATUS_VALUES.map((status) => (
            <option key={status} value={status}>
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </option>
          ))}
        </select>
        {errors.status && <p className="mt-1 text-sm text-red-500">{errors.status.message}</p>}
        <p className="mt-1 text-xs text-text-secondary">
          {STATUS_OPTIONS.find((s) => s.value === 'online')?.description}
        </p>
      </div>

      {/* Action Buttons */}
      <div className="flex justify-end gap-3 pt-4">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="rounded-lg border border-gray-700 px-4 py-2 font-medium text-text-primary transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-700 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          data-testid="camera-form-submit"
          className="rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        >
          {isSubmitting ? 'Saving...' : submitText}
        </button>
      </div>
    </form>
  );
}
