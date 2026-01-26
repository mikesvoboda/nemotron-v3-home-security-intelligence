/**
 * AlertForm - Reusable form component for creating and editing alert rules.
 *
 * Uses react-hook-form with Zod validation that matches backend Pydantic schemas.
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
 * - useWatch for dependent field updates (schedule fields)
 *
 * @see frontend/src/schemas/alert.ts - Zod validation schemas
 * @see backend/api/schemas/alerts.py for validation rules
 * @see NEM-3820 Migrate AlertForm to useForm with Zod
 * @see NEM-3822 Use useWatch for dependent field updates
 */
import { zodResolver } from '@hookform/resolvers/zod';
import { clsx } from 'clsx';
import { AlertCircle, Bell, Calendar, Shield, X, Zap } from 'lucide-react';
import { useEffect } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';

import { useInteractionTracking } from '../../hooks/useInteractionTracking';
import {
  alertFormSchema,
  ALERT_FORM_NAME_CONSTRAINTS,
  ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS,
  ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS,
  ALERT_FORM_COOLDOWN_SECONDS_CONSTRAINTS,
  type AlertFormInput,
  type AlertFormSeverityValue,
  type AlertFormDayOfWeekValue,
} from '../../schemas/alert';

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
const DAYS_OF_WEEK: readonly { value: AlertFormDayOfWeekValue; label: string }[] = [
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
  value: AlertFormSeverityValue;
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
const DEFAULT_FORM_DATA: AlertFormInput = {
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
// Isolated Schedule Section Component (NEM-3823 - Optimized Subscriptions)
// =============================================================================

interface ScheduleSectionProps {
  control: ReturnType<typeof useForm<AlertFormInput>>['control'];
  register: ReturnType<typeof useForm<AlertFormInput>>['register'];
  isSubmitting: boolean;
}

/**
 * Isolated Schedule Section - Only re-renders when schedule fields change.
 * Uses useWatch to subscribe to schedule_enabled field only.
 *
 * @see NEM-3822 Use useWatch for dependent field updates
 * @see NEM-3823 Optimize form state subscriptions
 */
function ScheduleSection({ control, register, isSubmitting }: ScheduleSectionProps) {
  // useWatch for dependent field - only subscribes to schedule_enabled
  const scheduleEnabled = useWatch({
    control,
    name: 'schedule_enabled',
  });

  return (
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
            <button
              type="button"
              role="switch"
              aria-checked={field.value}
              onClick={() => field.onChange(!field.value)}
              className={clsx(
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
                field.value ? 'bg-primary' : 'bg-gray-600'
              )}
              disabled={isSubmitting}
            >
              <span
                className={clsx(
                  'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                  field.value ? 'translate-x-6' : 'translate-x-1'
                )}
              />
            </button>
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
                        className={clsx(
                          'rounded px-3 py-1.5 text-sm font-medium transition-colors',
                          currentValue.includes(day.value)
                            ? 'bg-primary text-gray-900'
                            : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                        )}
                        disabled={isSubmitting}
                      >
                        {day.label}
                      </button>
                    ))}
                  </div>
                );
              }}
            />
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
                {...register('schedule_start_time')}
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
                {...register('schedule_end_time')}
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
  );
}

// =============================================================================
// Component
// =============================================================================

/**
 * AlertForm component for creating and editing alert rules.
 *
 * Uses react-hook-form with Zod validation to ensure frontend validation
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
  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<AlertFormInput>({
    resolver: zodResolver(alertFormSchema),
    defaultValues: {
      ...DEFAULT_FORM_DATA,
      ...initialData,
    },
    mode: 'onBlur',
  });

  const { trackClick, trackSubmit, trackToggle } = useInteractionTracking('AlertForm');

  // Update form when initial data changes
  useEffect(() => {
    if (initialData) {
      reset({
        ...DEFAULT_FORM_DATA,
        ...initialData,
      });
    }
  }, [initialData, reset]);

  // Handle form submission
  const onFormSubmit = (data: AlertFormInput) => {
    // Parse through Zod to get transformed output
    const result = alertFormSchema.safeParse(data);
    if (result.success) {
      // Track successful form validation
      trackSubmit(true, {
        severity: result.data.severity,
        has_schedule: result.data.schedule_enabled,
        object_types_count: result.data.object_types.length,
        channels_count: result.data.channels.length,
      });
      void onSubmit(result.data as AlertFormData);
    } else {
      // Track form validation failure
      trackSubmit(false, {
        validation_errors: result.error.issues.map((e) => e.path.join('.')),
      });
    }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(onFormSubmit)(e)} className="space-y-6" noValidate>
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
            {...register('name')}
            maxLength={ALERT_FORM_NAME_CONSTRAINTS.maxLength}
            className={clsx(
              'mt-1 block w-full rounded-lg border bg-card px-3 py-2 text-text-primary focus:outline-none focus:ring-2',
              errors.name
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-700 focus:border-primary focus:ring-primary'
            )}
            placeholder="e.g., Night Intruder Alert"
            disabled={isSubmitting}
          />
          {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name.message}</p>}
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
            {...register('description')}
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
            <Controller
              name="enabled"
              control={control}
              render={({ field }) => (
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={field.value}
                    onClick={() => {
                      const newValue = !field.value;
                      trackToggle('enabled', newValue);
                      field.onChange(newValue);
                    }}
                    className={clsx(
                      'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
                      field.value ? 'bg-primary' : 'bg-gray-600'
                    )}
                    disabled={isSubmitting}
                  >
                    <span
                      className={clsx(
                        'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                        field.value ? 'translate-x-6' : 'translate-x-1'
                      )}
                    />
                  </button>
                  <span className="text-sm text-gray-300">
                    {field.value ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              )}
            />
          </div>

          {/* Severity Select */}
          <div>
            <label htmlFor="alert-severity" className="block text-sm font-medium text-text-primary">
              Severity
            </label>
            <select
              id="alert-severity"
              {...register('severity')}
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
              Risk Threshold ({ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS.min}-
              {ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS.max})
            </label>
            <input
              type="number"
              id="alert-risk-threshold"
              {...register('risk_threshold', { valueAsNumber: true })}
              min={ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS.min}
              max={ALERT_FORM_RISK_THRESHOLD_CONSTRAINTS.max}
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

          <div>
            <label
              htmlFor="alert-min-confidence"
              className="block text-sm font-medium text-text-primary"
            >
              Min Confidence ({ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS.min}-
              {ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS.max})
            </label>
            <input
              type="number"
              id="alert-min-confidence"
              {...register('min_confidence', { valueAsNumber: true })}
              min={ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS.min}
              max={ALERT_FORM_MIN_CONFIDENCE_CONSTRAINTS.max}
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
                      className={clsx(
                        'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                        currentValue.includes(type)
                          ? 'bg-primary text-gray-900'
                          : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                      )}
                      disabled={isSubmitting}
                    >
                      {type}
                    </button>
                  ))}
                </div>
              );
            }}
          />
          <p className="mt-1 text-xs text-text-secondary">Leave empty to match all object types</p>
        </div>

        {/* Cameras */}
        <div>
          <span className="block text-sm font-medium text-text-primary">Cameras</span>
          {cameras.length === 0 ? (
            <p className="mt-2 text-sm text-text-secondary">No cameras available</p>
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
                        className={clsx(
                          'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                          currentValue.includes(camera.id)
                            ? 'bg-primary text-gray-900'
                            : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                        )}
                        disabled={isSubmitting}
                      >
                        {camera.name}
                      </button>
                    ))}
                  </div>
                );
              }}
            />
          )}
          <p className="mt-1 text-xs text-text-secondary">Leave empty to match all cameras</p>
        </div>
      </div>

      {/* Schedule Section - Isolated component for optimized re-renders (NEM-3822, NEM-3823) */}
      <ScheduleSection
        control={control}
        register={register}
        isSubmitting={isSubmitting}
      />

      {/* Notifications Section */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Zap className="h-4 w-4 text-primary" />
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
                      className={clsx(
                        'rounded-full px-3 py-1 text-sm font-medium transition-colors',
                        currentValue.includes(channel)
                          ? 'bg-primary text-gray-900'
                          : 'bg-gray-700 text-text-secondary hover:bg-gray-600'
                      )}
                      disabled={isSubmitting}
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
          <label htmlFor="alert-cooldown" className="block text-sm font-medium text-text-primary">
            Cooldown (seconds)
          </label>
          <input
            type="number"
            id="alert-cooldown"
            {...register('cooldown_seconds', { valueAsNumber: true })}
            min={ALERT_FORM_COOLDOWN_SECONDS_CONSTRAINTS.min}
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
