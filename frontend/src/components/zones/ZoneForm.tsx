import { clsx } from 'clsx';
import { AlertCircle, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { validateZoneColor, validateZoneName, VALIDATION_LIMITS } from '../../utils/validation';

import type { ZoneShape, ZoneType } from '../../types/generated';

export interface ZoneFormData {
  name: string;
  zone_type: ZoneType;
  shape: ZoneShape;
  color: string;
  enabled: boolean;
  priority: number;
}

export interface ZoneFormProps {
  /** Initial form data (for editing) */
  initialData?: Partial<ZoneFormData>;
  /** Callback when form is submitted */
  onSubmit: (data: ZoneFormData) => void;
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

/** Zone type options with labels */
const ZONE_TYPES: { value: ZoneType; label: string; description: string }[] = [
  { value: 'entry_point', label: 'Entry Point', description: 'Doors, gates, or other entry areas' },
  { value: 'driveway', label: 'Driveway', description: 'Vehicle access areas' },
  { value: 'sidewalk', label: 'Sidewalk', description: 'Public walkway areas' },
  { value: 'yard', label: 'Yard', description: 'Private property areas' },
  { value: 'other', label: 'Other', description: 'Custom zone type' },
];

/** Predefined color options */
const COLOR_OPTIONS = [
  { value: '#3B82F6', label: 'Blue' },
  { value: '#10B981', label: 'Green' },
  { value: '#F59E0B', label: 'Amber' },
  { value: '#EF4444', label: 'Red' },
  { value: '#8B5CF6', label: 'Purple' },
  { value: '#EC4899', label: 'Pink' },
  { value: '#6366F1', label: 'Indigo' },
  { value: '#14B8A6', label: 'Teal' },
];

/** Default form values */
const DEFAULT_FORM_DATA: ZoneFormData = {
  name: '',
  zone_type: 'other',
  shape: 'rectangle',
  color: '#3B82F6',
  enabled: true,
  priority: 0,
};

/**
 * ZoneForm component for creating and editing zones.
 *
 * Features:
 * - Name input with validation
 * - Zone type dropdown
 * - Color picker with predefined colors
 * - Enabled toggle
 * - Priority slider
 */
export default function ZoneForm({
  initialData,
  onSubmit,
  onCancel,
  isSubmitting = false,
  submitText = 'Save Zone',
  apiError,
  onClearApiError,
}: ZoneFormProps) {
  const [formData, setFormData] = useState<ZoneFormData>({
    ...DEFAULT_FORM_DATA,
    ...initialData,
  });
  const [errors, setErrors] = useState<{ name?: string; color?: string }>({});

  // Update form when initial data changes
  useEffect(() => {
    if (initialData) {
      setFormData({ ...DEFAULT_FORM_DATA, ...initialData });
    }
  }, [initialData]);

  const validateForm = (): boolean => {
    const newErrors: { name?: string; color?: string } = {};

    // Validate name using centralized validation (aligned with backend)
    const nameResult = validateZoneName(formData.name);
    if (!nameResult.isValid) {
      newErrors.name = nameResult.error;
    }

    // Validate color format (aligned with backend hex color pattern)
    const colorResult = validateZoneColor(formData.color);
    if (!colorResult.isValid) {
      newErrors.color = colorResult.error;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      onSubmit({
        ...formData,
        name: formData.name.trim(),
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
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

      {/* Name Input */}
      <div>
        <label htmlFor="zone-name" className="block text-sm font-medium text-text-primary">
          Zone Name
        </label>
        <input
          type="text"
          id="zone-name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          maxLength={VALIDATION_LIMITS.zone.name.maxLength}
          className={clsx(
            'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
            errors.name
              ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
              : 'border-gray-700 focus:border-primary focus:ring-primary'
          )}
          placeholder="e.g., Front Door, Driveway"
          disabled={isSubmitting}
        />
        {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name}</p>}
      </div>

      {/* Zone Type Select */}
      <div>
        <label htmlFor="zone-type" className="block text-sm font-medium text-text-primary">
          Zone Type
        </label>
        <select
          id="zone-type"
          value={formData.zone_type}
          onChange={(e) => setFormData({ ...formData, zone_type: e.target.value as ZoneType })}
          className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
          disabled={isSubmitting}
        >
          {ZONE_TYPES.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-secondary">
          {ZONE_TYPES.find((t) => t.value === formData.zone_type)?.description}
        </p>
      </div>

      {/* Color Picker */}
      <fieldset>
        <legend className="block text-sm font-medium text-text-primary">Zone Color</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {COLOR_OPTIONS.map((color) => (
            <button
              key={color.value}
              type="button"
              onClick={() => setFormData({ ...formData, color: color.value })}
              className={clsx(
                'h-8 w-8 rounded-full border-2 transition-all',
                formData.color === color.value
                  ? 'border-white ring-2 ring-primary ring-offset-2 ring-offset-background'
                  : 'border-transparent hover:border-gray-400'
              )}
              style={{ backgroundColor: color.value }}
              title={color.label}
              disabled={isSubmitting}
            />
          ))}
        </div>
      </fieldset>

      {/* Priority Slider */}
      <div>
        <label htmlFor="zone-priority" className="block text-sm font-medium text-text-primary">
          Priority: {formData.priority}
        </label>
        <input
          type="range"
          id="zone-priority"
          min={0}
          max={100}
          value={formData.priority}
          onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value, 10) })}
          className="mt-2 w-full accent-primary"
          disabled={isSubmitting}
        />
        <p className="mt-1 text-xs text-text-secondary">
          Higher priority zones take precedence when overlapping
        </p>
      </div>

      {/* Enabled Toggle */}
      <div className="flex items-center justify-between">
        <div>
          <span id="enabled-label" className="text-sm font-medium text-text-primary">
            Enabled
          </span>
          <p id="enabled-description" className="text-xs text-text-secondary">
            Active zones are used for detection analysis
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={formData.enabled}
          aria-labelledby="enabled-label"
          aria-describedby="enabled-description"
          onClick={() => setFormData({ ...formData, enabled: !formData.enabled })}
          className={clsx(
            'relative h-6 w-11 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
            formData.enabled ? 'bg-primary' : 'bg-gray-600'
          )}
          disabled={isSubmitting}
        >
          <span
            className={clsx(
              'absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform',
              formData.enabled && 'translate-x-5'
            )}
          />
        </button>
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
          className="rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        >
          {isSubmitting ? 'Saving...' : submitText}
        </button>
      </div>
    </form>
  );
}
