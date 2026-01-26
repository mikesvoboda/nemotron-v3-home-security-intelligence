/**
 * ScheduledReportForm - Form for creating and editing scheduled reports
 *
 * Features:
 * - Report name field
 * - Frequency selector (daily, weekly, monthly)
 * - Schedule configuration (hour, minute, day_of_week, day_of_month, timezone)
 * - Output format (PDF, CSV, JSON)
 * - Email recipients (array input)
 * - Content options (include_charts, include_event_details checkboxes)
 * - Enable/disable toggle
 *
 * @module components/reports/ScheduledReportForm
 * @see NEM-3667 - Scheduled Reports Frontend UI
 */

import { clsx } from 'clsx';
import { AlertCircle, Plus, Trash2, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import {
  REPORT_FREQUENCIES,
  FREQUENCY_LABELS,
  REPORT_FORMATS,
  FORMAT_LABELS,
  DAY_OF_WEEK_LABELS,
  COMMON_TIMEZONES,
} from '../../types/scheduledReport';
import Button from '../common/Button';

import type {
  ScheduledReport,
  ScheduledReportCreate,
  ScheduledReportUpdate,
  ReportFrequency,
  ReportFormat,
} from '../../types/scheduledReport';

// ============================================================================
// Types
// ============================================================================

export interface ScheduledReportFormProps {
  /** Existing report for editing (undefined for create mode) */
  report?: ScheduledReport;
  /** Submit handler */
  onSubmit: (data: ScheduledReportCreate | ScheduledReportUpdate) => Promise<void>;
  /** Cancel handler */
  onCancel: () => void;
  /** Whether form is submitting */
  isSubmitting?: boolean;
  /** API error message */
  apiError?: string | null;
  /** Clear API error callback */
  onClearApiError?: () => void;
}

interface FormState {
  name: string;
  frequency: ReportFrequency;
  day_of_week: number;
  day_of_month: number;
  hour: number;
  minute: number;
  timezone: string;
  format: ReportFormat;
  enabled: boolean;
  email_recipients: string[];
  include_charts: boolean;
  include_event_details: boolean;
}

interface FormErrors {
  name?: string;
  day_of_week?: string;
  day_of_month?: string;
  email_recipients?: string;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_FORM_STATE: FormState = {
  name: '',
  frequency: 'weekly',
  day_of_week: 1, // Tuesday
  day_of_month: 1,
  hour: 8,
  minute: 0,
  timezone: 'UTC',
  format: 'pdf',
  enabled: true,
  email_recipients: [],
  include_charts: true,
  include_event_details: true,
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Convert scheduled report to form state
 */
function reportToFormState(report: ScheduledReport): FormState {
  return {
    name: report.name,
    frequency: report.frequency,
    day_of_week: report.day_of_week ?? 1,
    day_of_month: report.day_of_month ?? 1,
    hour: report.hour,
    minute: report.minute,
    timezone: report.timezone,
    format: report.format,
    enabled: report.enabled,
    email_recipients: report.email_recipients ?? [],
    include_charts: report.include_charts,
    include_event_details: report.include_event_details,
  };
}

/**
 * Convert form state to create/update payload
 */
function formStateToPayload(state: FormState): ScheduledReportCreate | ScheduledReportUpdate {
  const payload: ScheduledReportCreate | ScheduledReportUpdate = {
    name: state.name.trim(),
    frequency: state.frequency,
    hour: state.hour,
    minute: state.minute,
    timezone: state.timezone,
    format: state.format,
    enabled: state.enabled,
    email_recipients: state.email_recipients.length > 0 ? state.email_recipients : null,
    include_charts: state.include_charts,
    include_event_details: state.include_event_details,
  };

  // Add frequency-specific fields
  if (state.frequency === 'weekly') {
    payload.day_of_week = state.day_of_week;
    payload.day_of_month = null;
  } else if (state.frequency === 'monthly') {
    payload.day_of_month = state.day_of_month;
    payload.day_of_week = null;
  } else {
    payload.day_of_week = null;
    payload.day_of_month = null;
  }

  return payload;
}

/**
 * Validate form state
 */
function validateForm(state: FormState): FormErrors {
  const errors: FormErrors = {};

  // Name validation
  if (!state.name.trim()) {
    errors.name = 'Name is required';
  } else if (state.name.trim().length > 255) {
    errors.name = 'Name must be 255 characters or less';
  }

  // Day of week validation for weekly reports
  if (state.frequency === 'weekly') {
    if (state.day_of_week < 0 || state.day_of_week > 6) {
      errors.day_of_week = 'Day of week must be between 0 (Monday) and 6 (Sunday)';
    }
  }

  // Day of month validation for monthly reports
  if (state.frequency === 'monthly') {
    if (state.day_of_month < 1 || state.day_of_month > 31) {
      errors.day_of_month = 'Day of month must be between 1 and 31';
    }
  }

  // Email validation
  for (const email of state.email_recipients) {
    if (!email.includes('@') || email.length > 254) {
      errors.email_recipients = 'One or more email addresses are invalid';
      break;
    }
  }

  if (state.email_recipients.length > 10) {
    errors.email_recipients = 'Maximum of 10 email recipients allowed';
  }

  return errors;
}

/**
 * Validate a single email address
 */
function isValidEmail(email: string): boolean {
  return email.includes('@') && email.length <= 254;
}

// ============================================================================
// Component
// ============================================================================

/**
 * ScheduledReportForm component for creating and editing scheduled reports
 */
export default function ScheduledReportForm({
  report,
  onSubmit,
  onCancel,
  isSubmitting = false,
  apiError,
  onClearApiError,
}: ScheduledReportFormProps) {
  const isEdit = Boolean(report);

  // Form state
  const [state, setState] = useState<FormState>(() =>
    report ? reportToFormState(report) : DEFAULT_FORM_STATE
  );
  const [errors, setErrors] = useState<FormErrors>({});
  const [newEmail, setNewEmail] = useState('');

  // Reset form when report changes
  useEffect(() => {
    if (report) {
      setState(reportToFormState(report));
    } else {
      setState(DEFAULT_FORM_STATE);
    }
    setErrors({});
    setNewEmail('');
  }, [report]);

  // Handle field change
  const handleChange = useCallback(
    <K extends keyof FormState>(field: K, value: FormState[K]) => {
      setState((prev) => ({ ...prev, [field]: value }));
    },
    []
  );

  // Handle adding email recipient
  const handleAddEmail = useCallback(() => {
    const trimmedEmail = newEmail.trim();
    if (trimmedEmail && isValidEmail(trimmedEmail)) {
      if (!state.email_recipients.includes(trimmedEmail)) {
        setState((prev) => ({
          ...prev,
          email_recipients: [...prev.email_recipients, trimmedEmail],
        }));
      }
      setNewEmail('');
    }
  }, [newEmail, state.email_recipients]);

  // Handle removing email recipient
  const handleRemoveEmail = useCallback((email: string) => {
    setState((prev) => ({
      ...prev,
      email_recipients: prev.email_recipients.filter((e) => e !== email),
    }));
  }, []);

  // Handle email input keydown
  const handleEmailKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddEmail();
      }
    },
    [handleAddEmail]
  );

  // Handle form submission
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      const validationErrors = validateForm(state);
      setErrors(validationErrors);

      if (Object.keys(validationErrors).length > 0) {
        return;
      }

      const payload = formStateToPayload(state);
      await onSubmit(payload);
    },
    [state, onSubmit]
  );

  // Generate hour options
  const hourOptions = Array.from({ length: 24 }, (_, i) => i);

  // Generate minute options (0, 15, 30, 45)
  const minuteOptions = [0, 15, 30, 45];

  // Generate day of month options
  const dayOfMonthOptions = Array.from({ length: 31 }, (_, i) => i + 1);

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="space-y-6"
      noValidate
      data-testid="scheduled-report-form"
    >
      {/* API Error */}
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

      {/* Basic Information */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-white">Basic Information</h3>

        {/* Name */}
        <div>
          <label htmlFor="report-name" className="block text-sm font-medium text-gray-300">
            Report Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="report-name"
            value={state.name}
            onChange={(e) => handleChange('name', e.target.value)}
            maxLength={255}
            className={clsx(
              'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
              errors.name
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
            )}
            placeholder="Weekly Security Summary"
            disabled={isSubmitting}
          />
          {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name}</p>}
        </div>

        {/* Enabled Toggle */}
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-gray-300">Enabled</span>
            <p className="text-xs text-gray-500">Report will run on schedule when enabled</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={state.enabled}
            onClick={() => handleChange('enabled', !state.enabled)}
            className={clsx(
              'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1F1F1F]',
              state.enabled ? 'bg-[#76B900]' : 'bg-gray-600'
            )}
            disabled={isSubmitting}
          >
            <span
              className={clsx(
                'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                state.enabled ? 'translate-x-6' : 'translate-x-1'
              )}
            />
          </button>
        </div>
      </div>

      {/* Schedule Configuration */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <h3 className="text-sm font-semibold text-white">Schedule</h3>

        {/* Frequency */}
        <div>
          <label htmlFor="report-frequency" className="block text-sm font-medium text-gray-300">
            Frequency
          </label>
          <select
            id="report-frequency"
            value={state.frequency}
            onChange={(e) => handleChange('frequency', e.target.value as ReportFrequency)}
            className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            disabled={isSubmitting}
          >
            {REPORT_FREQUENCIES.map((freq) => (
              <option key={freq} value={freq}>
                {FREQUENCY_LABELS[freq]}
              </option>
            ))}
          </select>
        </div>

        {/* Day of Week (for weekly) */}
        {state.frequency === 'weekly' && (
          <div>
            <label
              htmlFor="report-day-of-week"
              className="block text-sm font-medium text-gray-300"
            >
              Day of Week
            </label>
            <select
              id="report-day-of-week"
              value={state.day_of_week}
              onChange={(e) => handleChange('day_of_week', parseInt(e.target.value))}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
                errors.day_of_week
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
              )}
              disabled={isSubmitting}
            >
              {Object.entries(DAY_OF_WEEK_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            {errors.day_of_week && (
              <p className="mt-1 text-sm text-red-500">{errors.day_of_week}</p>
            )}
          </div>
        )}

        {/* Day of Month (for monthly) */}
        {state.frequency === 'monthly' && (
          <div>
            <label
              htmlFor="report-day-of-month"
              className="block text-sm font-medium text-gray-300"
            >
              Day of Month
            </label>
            <select
              id="report-day-of-month"
              value={state.day_of_month}
              onChange={(e) => handleChange('day_of_month', parseInt(e.target.value))}
              className={clsx(
                'mt-1 block w-full rounded-lg border bg-[#1A1A1A] px-3 py-2 text-white focus:outline-none focus:ring-2',
                errors.day_of_month
                  ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                  : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]'
              )}
              disabled={isSubmitting}
            >
              {dayOfMonthOptions.map((day) => (
                <option key={day} value={day}>
                  {day}
                </option>
              ))}
            </select>
            {errors.day_of_month && (
              <p className="mt-1 text-sm text-red-500">{errors.day_of_month}</p>
            )}
          </div>
        )}

        {/* Time */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="report-hour" className="block text-sm font-medium text-gray-300">
              Hour
            </label>
            <select
              id="report-hour"
              value={state.hour}
              onChange={(e) => handleChange('hour', parseInt(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
              disabled={isSubmitting}
            >
              {hourOptions.map((hour) => (
                <option key={hour} value={hour}>
                  {hour.toString().padStart(2, '0')}:00
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="report-minute" className="block text-sm font-medium text-gray-300">
              Minute
            </label>
            <select
              id="report-minute"
              value={state.minute}
              onChange={(e) => handleChange('minute', parseInt(e.target.value))}
              className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
              disabled={isSubmitting}
            >
              {minuteOptions.map((minute) => (
                <option key={minute} value={minute}>
                  :{minute.toString().padStart(2, '0')}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Timezone */}
        <div>
          <label htmlFor="report-timezone" className="block text-sm font-medium text-gray-300">
            Timezone
          </label>
          <select
            id="report-timezone"
            value={state.timezone}
            onChange={(e) => handleChange('timezone', e.target.value)}
            className="mt-1 block w-full rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            disabled={isSubmitting}
          >
            {COMMON_TIMEZONES.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Output Configuration */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <h3 className="text-sm font-semibold text-white">Output</h3>

        {/* Format */}
        <div>
          <label htmlFor="report-format" className="block text-sm font-medium text-gray-300">
            Format
          </label>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {REPORT_FORMATS.map((fmt) => (
              <button
                key={fmt}
                type="button"
                onClick={() => handleChange('format', fmt)}
                className={clsx(
                  'rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                  state.format === fmt
                    ? 'border-[#76B900] bg-[#76B900]/10 text-white'
                    : 'border-gray-700 bg-[#1A1A1A] text-gray-400 hover:border-gray-600 hover:text-gray-300'
                )}
                disabled={isSubmitting}
              >
                {FORMAT_LABELS[fmt]}
              </button>
            ))}
          </div>
        </div>

        {/* Content Options */}
        <div className="space-y-3">
          <label className="flex items-center gap-3" aria-label="Include Charts">
            <input
              type="checkbox"
              checked={state.include_charts}
              onChange={(e) => handleChange('include_charts', e.target.checked)}
              className="h-4 w-4 rounded border-gray-700 bg-[#1A1A1A] text-[#76B900] focus:ring-[#76B900] focus:ring-offset-[#1F1F1F]"
              disabled={isSubmitting}
            />
            <div>
              <span className="text-sm font-medium text-gray-300">Include Charts</span>
              <p className="text-xs text-gray-500">Add visual charts and graphs to the report</p>
            </div>
          </label>

          <label className="flex items-center gap-3" aria-label="Include Event Details">
            <input
              type="checkbox"
              checked={state.include_event_details}
              onChange={(e) => handleChange('include_event_details', e.target.checked)}
              className="h-4 w-4 rounded border-gray-700 bg-[#1A1A1A] text-[#76B900] focus:ring-[#76B900] focus:ring-offset-[#1F1F1F]"
              disabled={isSubmitting}
            />
            <div>
              <span className="text-sm font-medium text-gray-300">Include Event Details</span>
              <p className="text-xs text-gray-500">Add detailed event breakdowns to the report</p>
            </div>
          </label>
        </div>
      </div>

      {/* Email Recipients */}
      <div className="space-y-4 border-t border-gray-800 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Email Recipients</h3>
            <p className="text-xs text-gray-500">Send report to these email addresses (max 10)</p>
          </div>
        </div>

        {/* Email input */}
        <div className="flex gap-2">
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            onKeyDown={handleEmailKeyDown}
            placeholder="email@example.com"
            className="flex-1 rounded-lg border border-gray-700 bg-[#1A1A1A] px-3 py-2 text-white focus:border-[#76B900] focus:outline-none focus:ring-2 focus:ring-[#76B900]"
            disabled={isSubmitting || state.email_recipients.length >= 10}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={handleAddEmail}
            disabled={
              isSubmitting ||
              !newEmail.trim() ||
              !isValidEmail(newEmail.trim()) ||
              state.email_recipients.length >= 10
            }
          >
            Add
          </Button>
        </div>

        {/* Email list */}
        {state.email_recipients.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {state.email_recipients.map((email) => (
              <span
                key={email}
                className="inline-flex items-center gap-1 rounded-full bg-gray-700 px-3 py-1 text-sm text-gray-300"
              >
                {email}
                <button
                  type="button"
                  onClick={() => handleRemoveEmail(email)}
                  className="ml-1 text-gray-400 hover:text-red-400"
                  aria-label={`Remove ${email}`}
                  disabled={isSubmitting}
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {errors.email_recipients && (
          <p className="text-sm text-red-500">{errors.email_recipients}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-3 border-t border-gray-800 pt-6">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" isLoading={isSubmitting}>
          {isEdit ? 'Save Changes' : 'Create Report'}
        </Button>
      </div>
    </form>
  );
}
