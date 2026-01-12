/**
 * AlertRuleForm component for creating and editing alert rules.
 *
 * This component uses Zod validation schemas that mirror the backend Pydantic schemas
 * in backend/api/schemas/alerts.py for consistent validation.
 *
 * @see frontend/src/schemas/alertRule.ts - Zod validation schemas
 * @see backend/api/schemas/alerts.py - Backend Pydantic schemas
 */

import { Switch } from '@headlessui/react';
import { zodResolver } from '@hookform/resolvers/zod';
import { clsx } from 'clsx';
import {
  AlertCircle,
  AlertTriangle,
  Bell,
  Calendar,
  Loader2,
  X,
} from 'lucide-react';
import { useEffect } from 'react';
import { Controller, useForm } from 'react-hook-form';

import {
  alertRuleFormSchema,
  ALERT_RULE_NAME_CONSTRAINTS,
  ALERT_SEVERITY_VALUES,
  COOLDOWN_SECONDS_CONSTRAINTS,
  MIN_CONFIDENCE_CONSTRAINTS,
  RISK_THRESHOLD_CONSTRAINTS,
  type AlertRuleFormInput,
  type AlertRuleFormOutput,
  type AlertSeverityValue,
  type DayOfWeekValue,
} from '../../schemas/alertRule';

import type { Camera } from '../../services/api';

// =============================================================================
// Types
// =============================================================================

/**
 * Form data interface for alert rule form.
 * This mirrors the Zod schema output type.
 */
export interface AlertRuleFormData {
  name: string;
  description: string;
  enabled: boolean;
  severity: AlertSeverityValue;
  risk_threshold: number | null;
  object_types: string[];
  camera_ids: string[];
  zone_ids: string[];
  min_confidence: number | null;
  schedule_enabled: boolean;
  schedule_days: DayOfWeekValue[];
  schedule_start_time: string;
  schedule_end_time: string;
  schedule_timezone: string;
  cooldown_seconds: number;
  channels: string[];
}

/**
 * Props for the AlertRuleForm component.
 */
export interface AlertRuleFormProps {
  /** Initial form data (for editing) */
  initialData?: Partial<AlertRuleFormData>;
  /** Callback when form is submitted with validated data */
  onSubmit: (data: AlertRuleFormOutput) => void;
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
  /** Available cameras for selection */
  cameras?: Camera[];
  /** Whether cameras are loading */
  camerasLoading?: boolean;
  /** Camera loading error */
  camerasError?: string | null;
  /** Callback to retry loading cameras */
  onRetryCameras?: () => void;
}

// =============================================================================
// Constants
// =============================================================================

/** Days of the week for schedule selector */
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
const OBJECT_TYPES = ['person', 'vehicle', 'animal', 'package', 'face'] as const;

/** Notification channels */
const CHANNELS = ['email', 'webhook', 'pushover'] as const;

/** Severity configuration for display */
const SEVERITY_CONFIG: Record<AlertSeverityValue, { label: string; description: string }> = {
  low: { label: 'Low', description: 'Minor events, informational' },
  medium: { label: 'Medium', description: 'Standard events requiring attention' },
  high: { label: 'High', description: 'Important events requiring action' },
  critical: { label: 'Critical', description: 'Urgent events requiring immediate response' },
};

/** Common timezones */
const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Asia/Tokyo',
] as const;

/** Default form values */
const DEFAULT_FORM_DATA: AlertRuleFormData = {
  name: '',
  description: '',
  enabled: true,
  severity: 'medium',
  risk_threshold: null,
  object_types: [],
  camera_ids: [],
  zone_ids: [],
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
 * AlertRuleForm component for creating and editing alert rules.
 *
 * Features:
 * - Name input with length validation (1-255 chars)
 * - Description textarea
 * - Enabled toggle
 * - Severity selector
 * - Risk threshold input (0-100)
 * - Object type multi-select
 * - Camera multi-select
 * - Min confidence input (0-1)
 * - Schedule configuration (days, start/end time, timezone)
 * - Cooldown seconds input
 * - Notification channels multi-select
 *
 * Validation rules match backend Pydantic schemas:
 * - Name: min_length=1, max_length=255
 * - Risk threshold: ge=0, le=100 (optional)
 * - Min confidence: ge=0.0, le=1.0 (optional)
 * - Cooldown: ge=0
 * - Schedule times: HH:MM format, hours 00-23, minutes 00-59
 * - Schedule days: valid day names (monday-sunday)
 */
export default function AlertRuleForm({
  initialData,
  onSubmit,
  onCancel,
  isSubmitting = false,
  submitText = 'Save Rule',
  apiError,
  onClearApiError,
  cameras = [],
  camerasLoading = false,
  camerasError,
  onRetryCameras,
}: AlertRuleFormProps) {
  const {
    register,
    handleSubmit,
    control,
    reset,
    watch,
    formState: { errors },
  } = useForm<AlertRuleFormInput>({
    resolver: zodResolver(alertRuleFormSchema),
    defaultValues: {
      ...DEFAULT_FORM_DATA,
      ...initialData,
    },
    mode: 'onBlur',
  });

  // Watch for schedule_enabled to conditionally render schedule fields
  const scheduleEnabled = watch('schedule_enabled');

  // Update form when initial data changes (for edit mode)
  useEffect(() => {
    if (initialData) {
      reset({
        ...DEFAULT_FORM_DATA,
        ...initialData,
      });
    }
  }, [initialData, reset]);

  const onFormSubmit = (data: AlertRuleFormInput) => {
    // The Zod schema transforms and validates the data
    const result = alertRuleFormSchema.safeParse(data);
    if (result.success) {
      onSubmit(result.data);
    }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(onFormSubmit)(e)} className="space-y-6">
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
          <label htmlFor="alert-rule-name" className="block text-sm font-medium text-text-primary">
            Rule Name *
          </label>
          <input
            type="text"
            id="alert-rule-name"
            data-testid="alert-rule-name-input"
            {...register('name')}
            maxLength={ALERT_RULE_NAME_CONSTRAINTS.maxLength}
            className={clsx(
              'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
              errors.name
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-700 focus:border-primary focus:ring-primary'
            )}
            placeholder="Night Intruder Alert"
            disabled={isSubmitting}
          />
          {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name.message}</p>}
        </div>

        {/* Description Input */}
        <div>
          <label htmlFor="alert-rule-description" className="block text-sm font-medium text-text-primary">
            Description
          </label>
          <textarea
            id="alert-rule-description"
            data-testid="alert-rule-description-input"
            {...register('description')}
            rows={2}
            className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
            placeholder="Alert for detecting people at night"
            disabled={isSubmitting}
          />
        </div>

        {/* Enabled & Severity Row */}
        <div className="grid grid-cols-2 gap-4">
          {/* Enabled Toggle */}
          <div>
            <span className="block text-sm font-medium text-text-primary">Status</span>
            <Controller
              name="enabled"
              control={control}
              render={({ field }) => (
                <div className="mt-2 flex items-center gap-2">
                  <Switch
                    checked={field.value}
                    onChange={field.onChange}
                    disabled={isSubmitting}
                    aria-label={`Rule status: ${field.value ? 'enabled' : 'disabled'}`}
                    className={clsx(
                      'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-panel',
                      field.value ? 'bg-primary' : 'bg-gray-600'
                    )}
                  >
                    <span
                      className={clsx(
                        'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                        field.value ? 'translate-x-6' : 'translate-x-1'
                      )}
                    />
                  </Switch>
                  <span className="text-sm text-gray-300">
                    {field.value ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              )}
            />
          </div>

          {/* Severity Select */}
          <div>
            <label htmlFor="alert-rule-severity" className="block text-sm font-medium text-text-primary">
              Severity
            </label>
            <select
              id="alert-rule-severity"
              data-testid="alert-rule-severity-select"
              {...register('severity')}
              className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
              disabled={isSubmitting}
            >
              {ALERT_SEVERITY_VALUES.map((severity) => (
                <option key={severity} value={severity}>
                  {SEVERITY_CONFIG[severity].label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Trigger Conditions Section */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <AlertTriangle className="h-4 w-4 text-primary" />
          Trigger Conditions
        </h3>

        {/* Risk Threshold & Min Confidence Row */}
        <div className="grid grid-cols-2 gap-4">
          {/* Risk Threshold */}
          <div>
            <label htmlFor="alert-rule-risk-threshold" className="block text-sm font-medium text-text-primary">
              Risk Threshold ({RISK_THRESHOLD_CONSTRAINTS.min}-{RISK_THRESHOLD_CONSTRAINTS.max})
            </label>
            <input
              type="number"
              id="alert-rule-risk-threshold"
              data-testid="alert-rule-risk-threshold-input"
              {...register('risk_threshold', { valueAsNumber: true })}
              min={RISK_THRESHOLD_CONSTRAINTS.min}
              max={RISK_THRESHOLD_CONSTRAINTS.max}
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
              <p className="mt-1 text-sm text-red-500">{errors.risk_threshold.message}</p>
            )}
          </div>

          {/* Min Confidence */}
          <div>
            <label htmlFor="alert-rule-min-confidence" className="block text-sm font-medium text-text-primary">
              Min Confidence ({MIN_CONFIDENCE_CONSTRAINTS.min}-{MIN_CONFIDENCE_CONSTRAINTS.max})
            </label>
            <input
              type="number"
              id="alert-rule-min-confidence"
              data-testid="alert-rule-min-confidence-input"
              {...register('min_confidence', { valueAsNumber: true })}
              min={MIN_CONFIDENCE_CONSTRAINTS.min}
              max={MIN_CONFIDENCE_CONSTRAINTS.max}
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
              <p className="mt-1 text-sm text-red-500">{errors.min_confidence.message}</p>
            )}
          </div>
        </div>

        {/* Object Types */}
        <div>
          <span className="block text-sm font-medium text-text-primary">Object Types</span>
          <Controller
            name="object_types"
            control={control}
            render={({ field }) => {
              const currentValue = field.value ?? [];
              return (
                <div className="mt-2 flex flex-wrap gap-2">
                  {OBJECT_TYPES.map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => {
                        const newTypes = currentValue.includes(type)
                          ? currentValue.filter((t) => t !== type)
                          : [...currentValue, type];
                        field.onChange(newTypes);
                      }}
                      disabled={isSubmitting}
                      className={clsx(
                        'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                        currentValue.includes(type)
                          ? 'bg-primary text-gray-900'
                          : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                      )}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              );
            }}
          />
          <p className="mt-1 text-xs text-text-secondary">
            Leave empty to match all object types
          </p>
        </div>

        {/* Cameras */}
        <div>
          <span className="block text-sm font-medium text-text-primary">Cameras</span>
          {camerasError ? (
            <div
              className="mt-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3"
              data-testid="cameras-error"
            >
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-red-500" />
                <span className="text-sm text-red-400">Failed to load cameras.</span>
                {onRetryCameras && (
                  <button
                    type="button"
                    onClick={onRetryCameras}
                    disabled={camerasLoading}
                    className="inline-flex items-center gap-1 text-sm font-medium text-red-500 hover:text-red-400 disabled:opacity-50"
                    data-testid="cameras-retry-button"
                  >
                    {camerasLoading && <Loader2 className="h-3 w-3 animate-spin" />}
                    Retry
                  </button>
                )}
              </div>
            </div>
          ) : camerasLoading ? (
            <div className="mt-2 flex items-center gap-2 text-sm text-text-secondary">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading cameras...
            </div>
          ) : cameras.length === 0 ? (
            <div className="mt-2 text-sm text-text-secondary">No cameras available</div>
          ) : (
            <Controller
              name="camera_ids"
              control={control}
              render={({ field }) => {
                const currentValue = field.value ?? [];
                return (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {cameras.map((camera) => (
                      <button
                        key={camera.id}
                        type="button"
                        onClick={() => {
                          const newCameras = currentValue.includes(camera.id)
                            ? currentValue.filter((c) => c !== camera.id)
                            : [...currentValue, camera.id];
                          field.onChange(newCameras);
                        }}
                        disabled={isSubmitting}
                        className={clsx(
                          'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                          currentValue.includes(camera.id)
                            ? 'bg-primary text-gray-900'
                            : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                        )}
                      >
                        {camera.name}
                      </button>
                    ))}
                  </div>
                );
              }}
            />
          )}
          <p className="mt-1 text-xs text-text-secondary">
            Leave empty to match all cameras
          </p>
        </div>
      </div>

      {/* Schedule Section */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <Calendar className="h-4 w-4 text-primary" />
            Schedule
          </h3>
          <Controller
            name="schedule_enabled"
            control={control}
            render={({ field }) => (
              <Switch
                checked={field.value}
                onChange={field.onChange}
                disabled={isSubmitting}
                aria-label={`Schedule: ${field.value ? 'enabled' : 'disabled'}`}
                className={clsx(
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-panel',
                  field.value ? 'bg-primary' : 'bg-gray-600'
                )}
              >
                <span
                  className={clsx(
                    'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                    field.value ? 'translate-x-6' : 'translate-x-1'
                  )}
                />
              </Switch>
            )}
          />
        </div>

        {scheduleEnabled && (
          <div className="space-y-4">
            {/* Days */}
            <div>
              <span className="block text-sm font-medium text-text-primary">Days</span>
              <Controller
                name="schedule_days"
                control={control}
                render={({ field }) => {
                  const currentValue = field.value ?? [];
                  return (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {DAYS_OF_WEEK.map((day) => (
                        <button
                          key={day.value}
                          type="button"
                          onClick={() => {
                            const newDays = currentValue.includes(day.value)
                              ? currentValue.filter((d) => d !== day.value)
                              : [...currentValue, day.value];
                            field.onChange(newDays);
                          }}
                          disabled={isSubmitting}
                          className={clsx(
                            'rounded px-3 py-1.5 text-sm font-medium transition-colors',
                            currentValue.includes(day.value)
                              ? 'bg-primary text-gray-900'
                              : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                          )}
                        >
                          {day.label}
                        </button>
                      ))}
                    </div>
                  );
                }}
              />
              <p className="mt-1 text-xs text-text-secondary">Leave empty for all days</p>
              {errors.schedule_days && (
                <p className="mt-1 text-sm text-red-500">{errors.schedule_days.message}</p>
              )}
            </div>

            {/* Time Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="alert-rule-start-time" className="block text-sm font-medium text-text-primary">
                  Start Time
                </label>
                <input
                  type="time"
                  id="alert-rule-start-time"
                  data-testid="alert-rule-start-time-input"
                  {...register('schedule_start_time')}
                  className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={isSubmitting}
                />
                {errors.schedule_start_time && (
                  <p className="mt-1 text-sm text-red-500">{errors.schedule_start_time.message}</p>
                )}
              </div>
              <div>
                <label htmlFor="alert-rule-end-time" className="block text-sm font-medium text-text-primary">
                  End Time
                </label>
                <input
                  type="time"
                  id="alert-rule-end-time"
                  data-testid="alert-rule-end-time-input"
                  {...register('schedule_end_time')}
                  className="mt-1 block w-full rounded-lg border border-gray-700 bg-card px-3 py-2 text-text-primary focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={isSubmitting}
                />
                {errors.schedule_end_time && (
                  <p className="mt-1 text-sm text-red-500">{errors.schedule_end_time.message}</p>
                )}
              </div>
            </div>

            {/* Timezone */}
            <div>
              <label htmlFor="alert-rule-timezone" className="block text-sm font-medium text-text-primary">
                Timezone
              </label>
              <select
                id="alert-rule-timezone"
                data-testid="alert-rule-timezone-select"
                {...register('schedule_timezone')}
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
          <Bell className="h-4 w-4 text-primary" />
          Notifications
        </h3>

        {/* Channels */}
        <div>
          <span className="block text-sm font-medium text-text-primary">Notification Channels</span>
          <Controller
            name="channels"
            control={control}
            render={({ field }) => {
              const currentValue = field.value ?? [];
              return (
                <div className="mt-2 flex flex-wrap gap-2">
                  {CHANNELS.map((channel) => (
                    <button
                      key={channel}
                      type="button"
                      onClick={() => {
                        const newChannels = currentValue.includes(channel)
                          ? currentValue.filter((c) => c !== channel)
                          : [...currentValue, channel];
                        field.onChange(newChannels);
                      }}
                      disabled={isSubmitting}
                      className={clsx(
                        'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                        currentValue.includes(channel)
                          ? 'bg-primary text-gray-900'
                          : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                      )}
                    >
                      {channel}
                    </button>
                  ))}
                </div>
              );
            }}
          />
        </div>

        {/* Cooldown */}
        <div>
          <label htmlFor="alert-rule-cooldown" className="block text-sm font-medium text-text-primary">
            Cooldown (seconds)
          </label>
          <input
            type="number"
            id="alert-rule-cooldown"
            data-testid="alert-rule-cooldown-input"
            {...register('cooldown_seconds', { valueAsNumber: true })}
            min={COOLDOWN_SECONDS_CONSTRAINTS.min}
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
            <p className="mt-1 text-sm text-red-500">{errors.cooldown_seconds.message}</p>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex justify-end gap-3 border-t border-gray-800 pt-6">
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
          data-testid="alert-rule-form-submit"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-gray-900 transition-all hover:bg-primary-400 hover:shadow-nvidia-glow focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        >
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {isSubmitting ? 'Saving...' : submitText}
        </button>
      </div>
    </form>
  );
}
