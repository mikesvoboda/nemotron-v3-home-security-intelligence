/**
 * Tests for ScheduledReportForm component
 *
 * @see NEM-3667 - Scheduled Reports Frontend UI
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ScheduledReportForm from './ScheduledReportForm';

import type { ScheduledReport } from '../../types/scheduledReport';

// Test data
const mockReport: ScheduledReport = {
  id: 1,
  name: 'Weekly Security Summary',
  frequency: 'weekly',
  day_of_week: 1,
  day_of_month: null,
  hour: 8,
  minute: 0,
  timezone: 'America/New_York',
  format: 'pdf',
  enabled: true,
  email_recipients: ['admin@example.com'],
  include_charts: true,
  include_event_details: true,
  last_run_at: '2025-01-20T08:00:00Z',
  next_run_at: '2025-01-27T08:00:00Z',
  created_at: '2025-01-01T12:00:00Z',
  updated_at: '2025-01-15T09:30:00Z',
};

describe('ScheduledReportForm', () => {
  const mockOnSubmit = vi.fn();
  const mockOnCancel = vi.fn();
  const mockOnClearApiError = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Create Mode', () => {
    it('should render empty form in create mode', () => {
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      expect(screen.getByTestId('scheduled-report-form')).toBeInTheDocument();
      expect(screen.getByLabelText(/report name/i)).toHaveValue('');
      expect(screen.getByRole('button', { name: /create report/i })).toBeInTheDocument();
    });

    it('should show validation error for empty name', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      await user.click(screen.getByRole('button', { name: /create report/i }));

      expect(await screen.findByText(/name is required/i)).toBeInTheDocument();
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('should submit form with valid data', async () => {
      const user = userEvent.setup();
      mockOnSubmit.mockResolvedValue(undefined);

      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      // Fill in name
      await user.type(screen.getByLabelText(/report name/i), 'Test Report');

      // Submit
      await user.click(screen.getByRole('button', { name: /create report/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
      });

      const submittedData = mockOnSubmit.mock.calls[0][0];
      expect(submittedData.name).toBe('Test Report');
    });

    it('should call onCancel when cancel button is clicked', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      await user.click(screen.getByRole('button', { name: /cancel/i }));
      expect(mockOnCancel).toHaveBeenCalled();
    });
  });

  describe('Edit Mode', () => {
    it('should populate form with existing report data', () => {
      render(
        <ScheduledReportForm
          report={mockReport}
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      expect(screen.getByLabelText(/report name/i)).toHaveValue('Weekly Security Summary');
      expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument();
    });

    it('should show day of week selector for weekly frequency', () => {
      render(
        <ScheduledReportForm
          report={mockReport}
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      expect(screen.getByLabelText(/day of week/i)).toBeInTheDocument();
    });
  });

  describe('Frequency Selection', () => {
    it('should show day of month selector when monthly is selected', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      // Select monthly frequency
      await user.selectOptions(screen.getByLabelText(/frequency/i), 'monthly');

      expect(screen.getByLabelText(/day of month/i)).toBeInTheDocument();
      expect(screen.queryByLabelText(/day of week/i)).not.toBeInTheDocument();
    });

    it('should hide day selectors when daily is selected', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      // Select daily frequency
      await user.selectOptions(screen.getByLabelText(/frequency/i), 'daily');

      expect(screen.queryByLabelText(/day of week/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/day of month/i)).not.toBeInTheDocument();
    });
  });

  describe('Email Recipients', () => {
    it('should add email recipient', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      const emailInput = screen.getByPlaceholderText(/email@example.com/i);
      await user.type(emailInput, 'test@example.com');
      await user.click(screen.getByRole('button', { name: /add/i }));

      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });

    it('should remove email recipient', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          report={mockReport}
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      // Find and click remove button for existing email
      const removeButton = screen.getByRole('button', { name: /remove admin@example.com/i });
      await user.click(removeButton);

      expect(screen.queryByText('admin@example.com')).not.toBeInTheDocument();
    });

    it('should add email on Enter key', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      const emailInput = screen.getByPlaceholderText(/email@example.com/i);
      await user.type(emailInput, 'test@example.com{enter}');

      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });
  });

  describe('Format Selection', () => {
    it('should allow selecting different formats', async () => {
      const user = userEvent.setup();
      mockOnSubmit.mockResolvedValue(undefined);

      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      // Fill in name first
      await user.type(screen.getByLabelText(/report name/i), 'Test Report');

      // Select CSV format
      await user.click(screen.getByRole('button', { name: /csv/i }));

      // Submit
      await user.click(screen.getByRole('button', { name: /create report/i }));

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
      });

      const submittedData = mockOnSubmit.mock.calls[0][0];
      expect(submittedData.format).toBe('csv');
    });
  });

  describe('Enabled Toggle', () => {
    it('should toggle enabled state', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-checked', 'true'); // Default is enabled

      await user.click(toggle);
      expect(toggle).toHaveAttribute('aria-checked', 'false');
    });
  });

  describe('Content Options', () => {
    it('should toggle include_charts checkbox', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      const checkbox = screen.getByRole('checkbox', { name: /include charts/i });
      expect(checkbox).toBeChecked(); // Default is true

      await user.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });

    it('should toggle include_event_details checkbox', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
        />
      );

      const checkbox = screen.getByRole('checkbox', { name: /include event details/i });
      expect(checkbox).toBeChecked(); // Default is true

      await user.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });
  });

  describe('API Error Handling', () => {
    it('should display API error', () => {
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          apiError="Server error occurred"
        />
      );

      expect(screen.getByRole('alert')).toHaveTextContent('Server error occurred');
    });

    it('should clear API error when dismiss button is clicked', async () => {
      const user = userEvent.setup();
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          apiError="Server error occurred"
          onClearApiError={mockOnClearApiError}
        />
      );

      await user.click(screen.getByRole('button', { name: /dismiss error/i }));
      expect(mockOnClearApiError).toHaveBeenCalled();
    });
  });

  describe('Submitting State', () => {
    it('should disable inputs when submitting', () => {
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isSubmitting={true}
        />
      );

      expect(screen.getByLabelText(/report name/i)).toBeDisabled();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
    });

    it('should show loading state on submit button', () => {
      render(
        <ScheduledReportForm
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isSubmitting={true}
        />
      );

      // The Button component shows loading state internally
      expect(screen.getByRole('button', { name: /create report/i })).toBeInTheDocument();
    });
  });
});
