/**
 * AlertForm - Reusable form component for creating and editing alert rules.
 *
 * Uses centralized validation utilities that match backend Pydantic schemas.
 * This component provides form-level validation with real-time error feedback.
 *
 * Features:
 * - Name and description fields
 * - Severity selection (low, medium, high, critical)
 * - Risk threshold and confidence inputs
 * - Object type and camera selection
 * - Schedule configuration (days, time range, timezone)
 * - Notification channel selection
 * - Cooldown configuration
 *
 * @see backend/api/schemas/alerts.py for validation rules
 */
import { clsx } from 'clsx';
import { AlertCircle, Bell, Calendar, Shield, X, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';

import { useInteractionTracking } from '../../hooks/useInteractionTracking';
import {
  validateAlertRuleName,
  validateRiskThreshold,
  validateMinConfidence,
  validateCooldownSeconds,
  VALIDATION_LIMITS,
} from '../../utils/validation';

// =============================================================================
// Types
// =============================================================================

/** Alert severity values aligned with backend AlertSeverity enum */
export type AlertSeverityValue = 'low' | 'medium' | 'high' | 'critical';

/** Day of week values aligned with backend VALID_DAYS */
export type DayOfWeekValue =
  | 'monday'
  | 'tuesday'
  | 'wednesday'
  | 'thursday'
  | 'friday'
  | 'saturday'
  | 'sunday';

export interface AlertFormData {
  name: string;
  description: string;
  enabled: boolean;
  severity: AlertSeverityValue;
  risk_threshold: number | null;
  object_types: string[];
  camera_ids: string[];
  min_confidence: number | null;
  schedule_enabled: boolean;
  schedule_days: DayOfWeekValue[];
  schedule_start_time: string;
  schedule_end_time: string;
  schedule_timezone: string;
  cooldown_seconds: number;
  channels: string[];
}

interface FormErrors {
  name?: string;
  risk_threshold?: string;
  min_confidence?: string;
  cooldown_seconds?: string;
}

export interface CameraOption {
  id: string;
  name: string;
}

export interface AlertFormProps {
  /** Initial form data for editing existing rules */
  initialData?: Partial<AlertFormData>;
  /** Available cameras for selection */
  cameras?: CameraOption[];
  /** Callback when form is submitted with valid data */
  onSubmit: (data: AlertFormData) => void | Promise<void>;
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

// =============================================================================
// Constants
// =============================================================================

/** Days of the week with labels */
const DAYS_OF_WEEK: readonly { value: DayOfWeekValue; label: string }[] = [
  { value: 'monday', label: 'Mon' },
  { value: 'tuesday', label: 'Tue' },
  { value: 'wednesday', label: 'Wed' },
  { value: 'thursday', label: 'Thu' },
  { value: 'friday', label: 'Fri' },
  { value: 'saturday', label: 'Sat' },
  { value: 'sunday', label: 'Sun' },
];

/** Object types for filtering */
const OBJECT_TYPES = ['person', 'vehicle', 'animal', 'package', 'face'];

/** Notification channels */
const CHANNELS = ['email', 'webhook', 'pushover'];

/** Severity options with styling */
const SEVERITY_OPTIONS: readonly {
  value: AlertSeverityValue;
  label: string;
}[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
];

/** Common timezones for schedule */
const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Asia/Tokyo',
];

/** Default form values */
const DEFAULT_FORM_DATA: AlertFormData = {
  name: '',
  description: '',
  enabled: true,
  severity: 'medium',
  risk_threshold: null,
  object_types: [],
  camera_ids: [],
  min_confidence: null,
  schedule_enabled: false,
  schedule_days: [],
  schedule_start_time: '22:00',
  schedule_end_time: '06:00',
  schedule_timezone: 'UTC',
  cooldown_seconds: 300,
  channels: [],
};

// =============================================================================
// Component
// =============================================================================

/**
 * AlertForm component for creating and editing alert rules.
 *
 * Uses centralized validation utilities to ensure frontend validation
 * matches backend Pydantic schemas exactly.
 */
export default function AlertForm({
  initialData,
  cameras = [],
  onSubmit,
  onCancel,
  isSubmitting = false,
  submitText = 'Save Rule',
  apiError,
  onClearApiError,
}: AlertFormProps) {
  const [formData, setFormData] = useState<AlertFormData>({
    ...DEFAULT_FORM_DATA,
    ...initialData,
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const { trackClick, trackSubmit, trackToggle } = useInteractionTracking('AlertForm');

  // Update form when initial data changes
  useEffect(() => {
    if (initialData) {
      setFormData({ ...DEFAULT_FORM_DATA, ...initialData });
    }
  }, [initialData]);

  // Validate the form
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Validate name using centralized validation (aligned with backend)
    const nameResult = validateAlertRuleName(formData.name);
    if (!nameResult.isValid) {
      newErrors.name = nameResult.error;
    }

    // Validate risk threshold using centralized validation (aligned with backend)
    const riskResult = validateRiskThreshold(formData.risk_threshold);
    if (!riskResult.isValid) {
      newErrors.risk_threshold = riskResult.error;
    }

    // Validate min confidence using centralized validation (aligned with backend)
    const confidenceResult = validateMinConfidence(formData.min_confidence);
    if (!confidenceResult.isValid) {
      newErrors.min_confidence = confidenceResult.error;
    }

    // Validate cooldown using centralized validation (aligned with backend)
    const cooldownResult = validateCooldownSeconds(formData.cooldown_seconds);
    if (!cooldownResult.isValid) {
      newErrors.cooldown_seconds = cooldownResult.error;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle form submission
  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      // Track successful form validation (actual success depends on API call)
      trackSubmit(true, {
        severity: formData.severity,
        has_schedule: formData.schedule_enabled,
        object_types_count: formData.object_types.length,
        channels_count: formData.channels.length,
      });
      void onSubmit({
        ...formData,
        name: formData.name.trim(),
        description: formData.description.trim(),
      });
    } else {
      // Track form validation failure
      trackSubmit(false, {
        validation_errors: Object.keys(errors),
      });
    }
  };

  // Toggle array value helper
  const toggleArrayValue = <T extends string>(field: keyof AlertFormData, value: T) => {
    const currentValues = formData[field] as T[];
    const newValues = currentValues.includes(value)
      ? currentValues.filter((v) => v !== value)
      : [...currentValues, value];
    setFormData({ ...formData, [field]: newValues });
  };

  // Handle input changes
  const handleInputChange = (field: keyof AlertFormData, value: unknown) => {
    setFormData({ ...formData, [field]: value });
  };

  return (
    <form onSubmit={handleFormSubmit} className="space-y-6" noValidate>
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

      {/* Basic Information Section */}
      <div className="space-y-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Bell className="h-4 w-4 text-primary" />
          Basic Information
        </h3>

        {/* Name Input */}
        <div>
          <label htmlFor="alert-name" className="block text-sm font-medium text-text-primary">
            Rule Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="alert-name"
            value={formData.name}
            onChange={(e) => handleInputChange('name', e.target.value)}
            maxLength={VALIDATION_LIMITS.alertRule.name.maxLength}
            className={clsx(
              'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
              errors.name
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-700 focus:border-primary focus:ring-primary'
            )}
            placeholder="e.g., Night Intruder Alert"
            disabled={isSubmitting}
          />
          {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name}</p>}
        </div>

        {/* Description Input */}
        <div>
          <label
            htmlFor="alert-description"
            className="block text-sm font-medium text-text-primary"
          >
            Description
          </label>
          <textarea
            id="alert-description"
            value={formData.description}
            onChange={(e) => handleInputChange('description', e.target.value)}
            rows={2}
            className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder="Alert for detecting people at night"
            disabled={isSubmitting}
          />
        </div>

        {/* Enabled Toggle & Severity Row */}
        <div className="grid grid-cols-2 gap-4">
          {/* Enabled Toggle */}
          <div>
            <span className="block text-sm font-medium text-text-primary">Status</span>
            <div className="mt-2 flex items-center gap-2">
              <button
                type="button"
                role="switch"
                aria-checked={formData.enabled}
                onClick={() => {
                  const newValue = !formData.enabled;
                  trackToggle('enabled', newValue);
                  handleInputChange('enabled', newValue);
                }}
                className={clsx(
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
                  formData.enabled ? 'bg-primary' : 'bg-gray-600'
                )}
                disabled={isSubmitting}
              >
                <span
                  className={clsx(
                    'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                    formData.enabled ? 'translate-x-6' : 'translate-x-1'
                  )}
                />
              </button>
              <span className="text-sm text-gray-300">
                {formData.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>

          {/* Severity Select */}
          <div>
            <label htmlFor="alert-severity" className="block text-sm font-medium text-text-primary">
              Severity
            </label>
            <select
              id="alert-severity"
              value={formData.severity}
              onChange={(e) => handleInputChange('severity', e.target.value as AlertSeverityValue)}
              className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
              disabled={isSubmitting}
            >
              {SEVERITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Trigger Conditions Section */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Shield className="h-4 w-4 text-primary" />
          Trigger Conditions
        </h3>

        {/* Risk Threshold & Confidence Row */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="alert-risk-threshold"
              className="block text-sm font-medium text-text-primary"
            >
              Risk Threshold ({VALIDATION_LIMITS.alertRule.riskThreshold.min}-
              {VALIDATION_LIMITS.alertRule.riskThreshold.max})
            </label>
            <input
              type="number"
              id="alert-risk-threshold"
              value={formData.risk_threshold ?? ''}
              onChange={(e) =>
                handleInputChange(
                  'risk_threshold',
                  e.target.value === '' ? null : Number(e.target.value)
                )
              }
              min={VALIDATION_LIMITS.alertRule.riskThreshold.min}
              max={VALIDATION_LIMITS.alertRule.riskThreshold.max}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                errors.risk_threshold
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-primary focus:ring-primary'
              )}
              placeholder="70"
              disabled={isSubmitting}
            />
            {errors.risk_threshold && (
              <p className="mt-1 text-sm text-red-500">{errors.risk_threshold}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="alert-min-confidence"
              className="block text-sm font-medium text-text-primary"
            >
              Min Confidence ({VALIDATION_LIMITS.alertRule.minConfidence.min}-
              {VALIDATION_LIMITS.alertRule.minConfidence.max})
            </label>
            <input
              type="number"
              id="alert-min-confidence"
              value={formData.min_confidence ?? ''}
              onChange={(e) =>
                handleInputChange(
                  'min_confidence',
                  e.target.value === '' ? null : Number(e.target.value)
                )
              }
              min={VALIDATION_LIMITS.alertRule.minConfidence.min}
              max={VALIDATION_LIMITS.alertRule.minConfidence.max}
              step={0.1}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
                errors.min_confidence
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-primary focus:ring-primary'
              )}
              placeholder="0.8"
              disabled={isSubmitting}
            />
            {errors.min_confidence && (
              <p className="mt-1 text-sm text-red-500">{errors.min_confidence}</p>
            )}
          </div>
        </div>

        {/* Object Types */}
        <div>
          <span className="block text-sm font-medium text-text-primary">Object Types</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {OBJECT_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => toggleArrayValue('object_types', type)}
                className={clsx(
                  'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                  formData.object_types.includes(type)
                    ? 'bg-primary text-gray-900'
                    : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                )}
                disabled={isSubmitting}
              >
                {type}
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-text-secondary">Leave empty to match all object types</p>
        </div>

        {/* Cameras */}
        <div>
          <span className="block text-sm font-medium text-text-primary">Cameras</span>
          {cameras.length === 0 ? (
            <p className="mt-2 text-sm text-text-secondary">No cameras available</p>
          ) : (
            <div className="mt-2 flex flex-wrap gap-2">
              {cameras.map((camera) => (
                <button
                  key={camera.id}
                  type="button"
                  onClick={() => toggleArrayValue('camera_ids', camera.id)}
                  className={clsx(
                    'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                    formData.camera_ids.includes(camera.id)
                      ? 'bg-primary text-gray-900'
                      : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                  )}
                  disabled={isSubmitting}
                >
                  {camera.name}
                </button>
              ))}
            </div>
          )}
          <p className="mt-1 text-xs text-text-secondary">Leave empty to match all cameras</p>
        </div>
      </div>

      {/* Schedule Section */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Calendar className="h-4 w-4 text-primary" />
            Schedule
          </h3>
          <button
            type="button"
            role="switch"
            aria-checked={formData.schedule_enabled}
            onClick={() => {
              const newValue = !formData.schedule_enabled;
              trackToggle('schedule_enabled', newValue);
              handleInputChange('schedule_enabled', newValue);
            }}
            className={clsx(
              'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
              formData.schedule_enabled ? 'bg-primary' : 'bg-gray-600'
            )}
            disabled={isSubmitting}
          >
            <span
              className={clsx(
                'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                formData.schedule_enabled ? 'translate-x-6' : 'translate-x-1'
              )}
            />
          </button>
        </div>

        {formData.schedule_enabled && (
          <div className="space-y-4">
            {/* Days */}
            <div>
              <span className="block text-sm font-medium text-text-primary">Days</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {DAYS_OF_WEEK.map((day) => (
                  <button
                    key={day.value}
                    type="button"
                    onClick={() => toggleArrayValue('schedule_days', day.value)}
                    className={clsx(
                      'rounded px-3 py-1.5 text-sm font-medium transition-colors',
                      formData.schedule_days.includes(day.value)
                        ? 'bg-primary text-gray-900'
                        : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                    )}
                    disabled={isSubmitting}
                  >
                    {day.label}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-xs text-text-secondary">Leave empty for all days</p>
            </div>

            {/* Time Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label
                  htmlFor="schedule-start-time"
                  className="block text-sm font-medium text-text-primary"
                >
                  Start Time
                </label>
                <input
                  type="time"
                  id="schedule-start-time"
                  value={formData.schedule_start_time}
                  onChange={(e) => handleInputChange('schedule_start_time', e.target.value)}
                  className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={isSubmitting}
                />
              </div>
              <div>
                <label
                  htmlFor="schedule-end-time"
                  className="block text-sm font-medium text-text-primary"
                >
                  End Time
                </label>
                <input
                  type="time"
                  id="schedule-end-time"
                  value={formData.schedule_end_time}
                  onChange={(e) => handleInputChange('schedule_end_time', e.target.value)}
                  className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={isSubmitting}
                />
              </div>
            </div>

            {/* Timezone */}
            <div>
              <label
                htmlFor="schedule-timezone"
                className="block text-sm font-medium text-text-primary"
              >
                Timezone
              </label>
              <select
                id="schedule-timezone"
                value={formData.schedule_timezone}
                onChange={(e) => handleInputChange('schedule_timezone', e.target.value)}
                className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                disabled={isSubmitting}
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Notifications Section */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Zap className="h-4 w-4 text-primary" />
          Notifications
        </h3>

        {/* Channels */}
        <div>
          <span className="block text-sm font-medium text-text-primary">Notification Channels</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {CHANNELS.map((channel) => (
              <button
                key={channel}
                type="button"
                onClick={() => toggleArrayValue('channels', channel)}
                className={clsx(
                  'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                  formData.channels.includes(channel)
                    ? 'bg-primary text-gray-900'
                    : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                )}
                disabled={isSubmitting}
              >
                {channel}
              </button>
            ))}
          </div>
        </div>

        {/* Cooldown */}
        <div>
          <label htmlFor="alert-cooldown" className="block text-sm font-medium text-text-primary">
            Cooldown (seconds)
          </label>
          <input
            type="number"
            id="alert-cooldown"
            value={formData.cooldown_seconds}
            onChange={(e) => handleInputChange('cooldown_seconds', Number(e.target.value))}
            min={VALIDATION_LIMITS.alertRule.cooldownSeconds.min}
            className={clsx(
              'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
              errors.cooldown_seconds
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-700 focus:border-primary focus:ring-primary'
            )}
            placeholder="300"
            disabled={isSubmitting}
          />
          <p className="mt-1 text-xs text-text-secondary">
            Minimum seconds between duplicate alerts
          </p>
          {errors.cooldown_seconds && (
            <p className="mt-1 text-sm text-red-500">{errors.cooldown_seconds}</p>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex justify-end gap-3 border-t border-gray-800 pt-6">
        <button
          type="button"
          onClick={() => {
            trackClick('cancel_button');
            onCancel();
          }}
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
