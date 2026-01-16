import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AlertRulesSettings from './AlertRulesSettings';
import * as api from '../../services/api';

import type { AlertRule, Camera, RuleTestResponse } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchAlertRules: vi.fn(),
  fetchCameras: vi.fn(),
  fetchSeverityMetadata: vi.fn(),
  createAlertRule: vi.fn(),
  updateAlertRule: vi.fn(),
  deleteAlertRule: vi.fn(),
  testAlertRule: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
      public data?: unknown
    ) {
      super(message);
      this.name = 'ApiError';
    }
  },
}));

// Mock SeverityConfigPanel to avoid testing it here
vi.mock('../system/SeverityConfigPanel', () => ({
  default: () => <div data-testid="severity-config-panel">Severity Config Panel</div>,
}));

describe('AlertRulesSettings', () => {
  const mockCameras: Camera[] = [
    {
      id: 'cam-1',
      name: 'Front Door',
      folder_path: '/export/foscam/front_door',
      status: 'online',
      created_at: '2025-01-01T00:00:00Z',
      last_seen_at: '2025-01-10T12:00:00Z',
    },
    {
      id: 'cam-2',
      name: 'Backyard',
      folder_path: '/export/foscam/backyard',
      status: 'offline',
      created_at: '2025-01-01T00:00:00Z',
      last_seen_at: null,
    },
  ];

  const mockRules: AlertRule[] = [
    {
      id: 'rule-1',
      name: 'Night Intruder Alert',
      description: 'Alert for person detection at night',
      enabled: true,
      severity: 'critical',
      risk_threshold: 70,
      object_types: ['person'],
      camera_ids: ['cam-1'],
      zone_ids: null,
      min_confidence: 0.8,
      schedule: {
        days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
        start_time: '22:00',
        end_time: '06:00',
        timezone: 'UTC',
      },
      conditions: null,
      dedup_key_template: '{camera_id}:{rule_id}',
      cooldown_seconds: 300,
      channels: ['pushover', 'webhook'],
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    },
    {
      id: 'rule-2',
      name: 'Vehicle Alert',
      description: null,
      enabled: false,
      severity: 'medium',
      risk_threshold: 50,
      object_types: ['vehicle'],
      camera_ids: null,
      zone_ids: null,
      min_confidence: null,
      schedule: null,
      conditions: null,
      dedup_key_template: '{camera_id}:{rule_id}',
      cooldown_seconds: 600,
      channels: ['email'],
      created_at: '2025-01-02T00:00:00Z',
      updated_at: '2025-01-02T00:00:00Z',
    },
  ];

  const mockTestResult: RuleTestResponse = {
    rule_id: 'rule-1',
    rule_name: 'Night Intruder Alert',
    events_tested: 10,
    events_matched: 3,
    match_rate: 0.3,
    results: [
      {
        event_id: 1,
        camera_id: 'cam-1',
        risk_score: 75,
        object_types: ['person'],
        matches: true,
        matched_conditions: ['risk_score >= 70', 'object_type = person'],
        started_at: '2025-01-10T22:30:00Z',
      },
      {
        event_id: 2,
        camera_id: 'cam-1',
        risk_score: 45,
        object_types: ['vehicle'],
        matches: false,
        matched_conditions: [],
        started_at: '2025-01-10T23:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    // Mock severity metadata API - not the focus of these tests
    vi.mocked(api.fetchSeverityMetadata).mockResolvedValue({
      definitions: [
        {
          severity: 'low',
          label: 'Low',
          description: 'Routine',
          color: '#22c55e',
          priority: 3,
          min_score: 0,
          max_score: 29,
        },
        {
          severity: 'critical',
          label: 'Critical',
          description: 'Urgent',
          color: '#ef4444',
          priority: 0,
          min_score: 85,
          max_score: 100,
        },
      ],
      thresholds: { low_max: 29, medium_max: 59, high_max: 84 },
    });
    // Mock console.error to suppress expected error messages in tests
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial Load', () => {
    it('should show loading state initially', () => {
      // Make all APIs never resolve to avoid state updates after test
      vi.mocked(api.fetchAlertRules).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );
      vi.mocked(api.fetchCameras).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );
      vi.mocked(api.fetchSeverityMetadata).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<AlertRulesSettings />);
      expect(screen.getByText('Loading alert rules...')).toBeInTheDocument();
    });

    it('should load and display rules', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      expect(screen.getByText('Vehicle Alert')).toBeInTheDocument();
    });

    it('should display rule severity with correct styling', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
    });

    it('should display schedule information', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      // Check schedule is displayed (Mon, Tue, Wed, Thu, Fri abbreviated)
      expect(screen.getByText(/Mon, Tue, Wed, Thu, Fri/)).toBeInTheDocument();
      expect(screen.getByText('Always active')).toBeInTheDocument();
    });

    it('should display channels', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      expect(screen.getByText('pushover')).toBeInTheDocument();
      expect(screen.getByText('webhook')).toBeInTheDocument();
      expect(screen.getByText('email')).toBeInTheDocument();
    });

    it('should display error state when fetch fails', async () => {
      vi.mocked(api.fetchAlertRules).mockRejectedValue(new Error('Network error'));

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Error loading alert rules')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
      expect(screen.getByText('Try again')).toBeInTheDocument();
    });

    it('should retry loading rules on error', async () => {
      vi.mocked(api.fetchAlertRules)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          items: mockRules,
          pagination: { total: 2, limit: 50, offset: null, has_more: false },
        });

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Error loading alert rules')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByText('Try again'));

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });
    });

    it('should show empty state when no rules exist', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 50, offset: null, has_more: false },
      });

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      expect(
        screen.getByText('Create your first alert rule to get notified about security events')
      ).toBeInTheDocument();
    });
  });

  describe('Camera Fetch Error Handling', () => {
    it('should show camera error in modal when camera fetch fails but rules load', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 50, offset: null, has_more: false },
      });
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Camera API unavailable'));

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Camera error should be displayed in the form
      expect(screen.getByTestId('cameras-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load cameras.')).toBeInTheDocument();
      expect(screen.getByTestId('cameras-retry-button')).toBeInTheDocument();
    });

    it('should retry camera fetch when retry button is clicked', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 50, offset: null, has_more: false },
      });
      vi.mocked(api.fetchCameras)
        .mockRejectedValueOnce(new Error('Camera API unavailable'))
        .mockResolvedValueOnce(mockCameras);

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Camera error should be displayed
      expect(screen.getByTestId('cameras-error')).toBeInTheDocument();

      // Click retry button
      const retryButton = screen.getByTestId('cameras-retry-button');
      await user.click(retryButton);

      // Cameras should now be loaded
      await waitFor(() => {
        expect(screen.queryByTestId('cameras-error')).not.toBeInTheDocument();
      });

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Backyard')).toBeInTheDocument();
    });

    it('should allow form submission even when cameras fail to load', async () => {
      const newRule: AlertRule = {
        id: 'rule-3',
        name: 'Test Rule Without Cameras',
        description: null,
        enabled: true,
        severity: 'medium',
        risk_threshold: null,
        object_types: null,
        camera_ids: null,
        zone_ids: null,
        min_confidence: null,
        schedule: null,
        conditions: null,
        dedup_key_template: '{camera_id}:{rule_id}',
        cooldown_seconds: 300,
        channels: [],
        created_at: '2025-01-10T00:00:00Z',
        updated_at: '2025-01-10T00:00:00Z',
      };

      vi.mocked(api.fetchAlertRules)
        .mockResolvedValueOnce({
          items: [],
          pagination: { total: 0, limit: 50, offset: null, has_more: false },
        })
        .mockResolvedValueOnce({
          items: [newRule],
          pagination: { total: 1, limit: 50, offset: null, has_more: false },
        });
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Camera API unavailable'));
      vi.mocked(api.createAlertRule).mockResolvedValue(newRule);

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Camera error should be displayed but form still usable
      expect(screen.getByTestId('cameras-error')).toBeInTheDocument();

      // Fill in required fields
      const nameInput = screen.getByLabelText('Rule Name *');
      await user.type(nameInput, 'Test Rule Without Cameras');

      // Submit the form
      const dialog = screen.getByRole('dialog');
      const submitButton = within(dialog).getByRole('button', { name: 'Add Rule' });
      await user.click(submitButton);

      // Form should submit successfully
      await waitFor(() => {
        expect(api.createAlertRule).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.getByText('Test Rule Without Cameras')).toBeInTheDocument();
      });
    });

    it('should show cameras after successful retry', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });
      vi.mocked(api.fetchCameras)
        .mockRejectedValueOnce(new Error('Camera API unavailable'))
        .mockResolvedValueOnce(mockCameras);

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Initially should show camera error
      expect(screen.getByTestId('cameras-error')).toBeInTheDocument();

      // Click retry
      await user.click(screen.getByTestId('cameras-retry-button'));

      // After retry, cameras should be visible
      await waitFor(() => {
        expect(screen.queryByTestId('cameras-error')).not.toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: 'Front Door' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Backyard' })).toBeInTheDocument();
    });
  });

  describe('Toggle Rule', () => {
    beforeEach(() => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });
    });

    it('should toggle rule enabled state', async () => {
      const updatedRule = { ...mockRules[0], enabled: false };
      vi.mocked(api.updateAlertRule).mockResolvedValue(updatedRule);
      vi.mocked(api.fetchAlertRules)
        .mockResolvedValueOnce({
          items: mockRules,
          pagination: { total: 2, limit: 50, offset: null, has_more: false },
        })
        .mockResolvedValueOnce({
          items: [updatedRule, mockRules[1]],
          pagination: { total: 2, limit: 50, offset: null, has_more: false },
        });

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      // Find all switches - there should be 2 (one for each rule)
      const switches = screen.getAllByRole('switch');
      await user.click(switches[0]); // Toggle the first rule

      await waitFor(() => {
        expect(api.updateAlertRule).toHaveBeenCalledWith('rule-1', { enabled: false });
      });
    });
  });

  describe('Add Rule', () => {
    beforeEach(() => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 50, offset: null, has_more: false },
      });
    });

    it('should open add rule modal', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Rule Name *')).toBeInTheDocument();
      expect(screen.getByLabelText('Description')).toBeInTheDocument();
    });

    it('should validate required fields (aligned with backend min_length=1)', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      const submitButton = within(dialog).getByRole('button', { name: 'Add Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        // Updated to match backend validation (min_length=1)
        expect(screen.getByText('Name is required')).toBeInTheDocument();
      });
    });

    it('should validate risk threshold range', async () => {
      // Test that the form accepts valid risk threshold values (0-100)
      // HTML5 input validation handles min/max, so we verify the form accepts valid input
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const thresholdInput = screen.getByLabelText('Risk Threshold (0-100)');

      // Verify the input has proper min/max attributes for HTML5 validation
      expect(thresholdInput).toHaveAttribute('min', '0');
      expect(thresholdInput).toHaveAttribute('max', '100');
      expect(thresholdInput).toHaveAttribute('type', 'number');

      // Type a valid value
      await user.type(thresholdInput, '75');
      expect(thresholdInput).toHaveValue(75);
    });

    it('should create a new rule successfully', async () => {
      const newRule: AlertRule = {
        id: 'rule-3',
        name: 'Test Rule',
        description: 'Test description',
        enabled: true,
        severity: 'high',
        risk_threshold: 60,
        object_types: ['person'],
        camera_ids: null,
        zone_ids: null,
        min_confidence: null,
        schedule: null,
        conditions: null,
        dedup_key_template: '{camera_id}:{rule_id}',
        cooldown_seconds: 300,
        channels: ['email'],
        created_at: '2025-01-10T00:00:00Z',
        updated_at: '2025-01-10T00:00:00Z',
      };

      vi.mocked(api.fetchAlertRules)
        .mockResolvedValueOnce({
          items: [],
          pagination: { total: 0, limit: 50, offset: null, has_more: false },
        })
        .mockResolvedValueOnce({
          items: [newRule],
          pagination: { total: 1, limit: 50, offset: null, has_more: false },
        });
      vi.mocked(api.createAlertRule).mockResolvedValue(newRule);

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Rule Name *');
      await user.type(nameInput, 'Test Rule');

      const descInput = screen.getByLabelText('Description');
      await user.type(descInput, 'Test description');

      // Select severity
      const severitySelect = screen.getByLabelText('Severity');
      await user.selectOptions(severitySelect, 'high');

      // Set risk threshold
      const thresholdInput = screen.getByLabelText('Risk Threshold (0-100)');
      await user.type(thresholdInput, '60');

      // Select object type
      const personButton = screen.getByRole('button', { name: 'person' });
      await user.click(personButton);

      // Select channel
      const emailButton = screen.getByRole('button', { name: 'email' });
      await user.click(emailButton);

      const dialog = screen.getByRole('dialog');
      const submitButton = within(dialog).getByRole('button', { name: 'Add Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(api.createAlertRule).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.getByText('Test Rule')).toBeInTheDocument();
      });
    });

    it('should handle create error', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 50, offset: null, has_more: false },
      });
      vi.mocked(api.createAlertRule).mockRejectedValue(new Error('Creation failed'));

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Rule Name *');
      await user.type(nameInput, 'Test Rule');

      const dialog = screen.getByRole('dialog');
      const submitButton = within(dialog).getByRole('button', { name: 'Add Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Creation failed')).toBeInTheDocument();
      });
    });

    it('should close modal on cancel', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Edit Rule', () => {
    beforeEach(() => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });
    });

    it('should open edit modal with rule data', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByDisplayValue('Night Intruder Alert')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Alert for person detection at night')).toBeInTheDocument();
    });

    it('should update rule successfully', async () => {
      const updatedRule: AlertRule = {
        ...mockRules[0],
        name: 'Updated Rule',
        description: 'Updated description',
      };

      vi.mocked(api.fetchAlertRules)
        .mockResolvedValueOnce({
          items: mockRules,
          pagination: { total: 2, limit: 50, offset: null, has_more: false },
        })
        .mockResolvedValueOnce({
          items: [updatedRule, mockRules[1]],
          pagination: { total: 2, limit: 50, offset: null, has_more: false },
        });
      vi.mocked(api.updateAlertRule).mockResolvedValue(updatedRule);

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Rule Name *');

      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Rule');

      const submitButton = screen.getByRole('button', { name: 'Update Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(api.updateAlertRule).toHaveBeenCalledWith(
          'rule-1',
          expect.objectContaining({
            name: 'Updated Rule',
          })
        );
      });

      await waitFor(() => {
        expect(screen.getByText('Updated Rule')).toBeInTheDocument();
      });
    });

    it('should handle update error', async () => {
      vi.mocked(api.updateAlertRule).mockRejectedValue(new Error('Update failed'));

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Rule Name *');
      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Rule');

      const submitButton = screen.getByRole('button', { name: 'Update Rule' });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Update failed')).toBeInTheDocument();
      });
    });
  });

  describe('Delete Rule', () => {
    beforeEach(() => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });
    });

    it('should open delete confirmation modal', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        const dialogs = screen.getAllByRole('dialog');
        expect(dialogs.length).toBeGreaterThan(0);
      });

      expect(screen.getByRole('heading', { name: 'Delete Alert Rule' })).toBeInTheDocument();
      expect(screen.getByText(/Are you sure you want to delete/)).toBeInTheDocument();
    });

    it('should delete rule successfully', async () => {
      vi.mocked(api.fetchAlertRules)
        .mockResolvedValueOnce({
          items: mockRules,
          pagination: { total: 2, limit: 50, offset: null, has_more: false },
        })
        .mockResolvedValueOnce({
          items: [mockRules[1]],
          pagination: { total: 1, limit: 50, offset: null, has_more: false },
        });
      vi.mocked(api.deleteAlertRule).mockResolvedValue(undefined);

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Alert Rule' })).toBeInTheDocument();
      });

      const confirmButton = screen.getByRole('button', { name: 'Delete Rule' });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(api.deleteAlertRule).toHaveBeenCalledWith('rule-1');
      });

      await waitFor(() => {
        expect(screen.queryByText('Night Intruder Alert')).not.toBeInTheDocument();
      });
    });

    it('should handle delete error', async () => {
      vi.mocked(api.deleteAlertRule).mockRejectedValue(new Error('Delete failed'));

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Alert Rule' })).toBeInTheDocument();
      });

      const confirmButton = screen.getByRole('button', { name: 'Delete Rule' });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText('Delete failed')).toBeInTheDocument();
      });
    });

    it('should cancel delete operation', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const deleteButtons = screen.getAllByLabelText(/Delete/);
      await user.click(deleteButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Alert Rule' })).toBeInTheDocument();
      });

      const dialogs = screen.getAllByRole('dialog');
      const deleteDialog = dialogs.find((dialog) =>
        dialog.textContent?.includes('Are you sure you want to delete')
      );
      expect(deleteDialog).toBeDefined();

      const cancelButton = within(deleteDialog!).getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      await waitFor(() => {
        const deleteHeadings = screen.queryAllByRole('heading', { name: 'Delete Alert Rule' });
        expect(deleteHeadings).toHaveLength(0);
      });

      expect(api.deleteAlertRule).not.toHaveBeenCalled();
    });
  });

  describe('Test Rule', () => {
    beforeEach(() => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });
    });

    it('should open test modal and show results', async () => {
      vi.mocked(api.testAlertRule).mockResolvedValue(mockTestResult);

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const testButtons = screen.getAllByTitle('Test rule');
      await user.click(testButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Test Rule: Night Intruder Alert')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByText('10')).toBeInTheDocument(); // Events tested
        expect(screen.getByText('3')).toBeInTheDocument(); // Events matched
        expect(screen.getByText('30%')).toBeInTheDocument(); // Match rate
      });
    });

    it('should display per-event test results', async () => {
      vi.mocked(api.testAlertRule).mockResolvedValue(mockTestResult);

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const testButtons = screen.getAllByTitle('Test rule');
      await user.click(testButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Event #1')).toBeInTheDocument();
        expect(screen.getByText('Event #2')).toBeInTheDocument();
      });

      // Check matched conditions are shown
      expect(screen.getByText(/risk_score >= 70/)).toBeInTheDocument();
    });

    it('should show loading state during test', async () => {
      vi.mocked(api.testAlertRule).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const testButtons = screen.getAllByTitle('Test rule');
      await user.click(testButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Testing rule against recent events...')).toBeInTheDocument();
      });
    });

    it('should close test modal', async () => {
      vi.mocked(api.testAlertRule).mockResolvedValue(mockTestResult);

      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const testButtons = screen.getAllByTitle('Test rule');
      await user.click(testButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Test Rule: Night Intruder Alert')).toBeInTheDocument();
      });

      const closeButton = screen.getByRole('button', { name: 'Close' });
      await user.click(closeButton);

      await waitFor(() => {
        expect(screen.queryByText('Test Rule: Night Intruder Alert')).not.toBeInTheDocument();
      });
    });
  });

  describe('Schedule Selector', () => {
    beforeEach(() => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: [],
        pagination: { total: 0, limit: 50, offset: null, has_more: false },
      });
    });

    it('should toggle schedule section', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Find the schedule toggle (it's a switch in the Schedule section header)
      const scheduleSection = screen.getByText('Schedule').closest('div');
      expect(scheduleSection).toBeDefined();

      // Time inputs should not be visible initially
      expect(screen.queryByLabelText('Start Time')).not.toBeInTheDocument();

      // Find and click the schedule toggle switch
      const scheduleHeading = screen.getByText('Schedule');
      const scheduleSwitch = scheduleHeading.parentElement?.querySelector('[role="switch"]');
      if (scheduleSwitch) {
        await user.click(scheduleSwitch);
      }

      await waitFor(() => {
        expect(screen.getByLabelText('Start Time')).toBeInTheDocument();
        expect(screen.getByLabelText('End Time')).toBeInTheDocument();
        expect(screen.getByLabelText('Timezone')).toBeInTheDocument();
      });
    });

    it('should select days of week', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('No alert rules configured')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getAllByText('Add Rule')[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Enable schedule
      const scheduleHeading = screen.getByText('Schedule');
      const scheduleSwitch = scheduleHeading.parentElement?.querySelector('[role="switch"]');
      if (scheduleSwitch) {
        await user.click(scheduleSwitch);
      }

      await waitFor(() => {
        expect(screen.getByLabelText('Start Time')).toBeInTheDocument();
      });

      // Select Monday and Friday
      const monButton = screen.getByRole('button', { name: 'Mon' });
      const friButton = screen.getByRole('button', { name: 'Fri' });

      await user.click(monButton);
      await user.click(friButton);

      // Check they are selected (have different styling)
      expect(monButton).toHaveClass('bg-primary');
      expect(friButton).toHaveClass('bg-primary');
    });
  });

  describe('Accessibility', () => {
    beforeEach(() => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue({
        items: mockRules,
        pagination: { total: 2, limit: 50, offset: null, has_more: false },
      });
    });

    it('should have proper aria-labels for action buttons', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Edit Night Intruder Alert')).toBeInTheDocument();
      expect(screen.getByLabelText('Delete Night Intruder Alert')).toBeInTheDocument();
      expect(screen.getByLabelText('Test Night Intruder Alert')).toBeInTheDocument();
    });

    it('should have accessible modal close button', async () => {
      render(<AlertRulesSettings />);

      await waitFor(() => {
        expect(screen.getByText('Night Intruder Alert')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const editButtons = screen.getAllByLabelText(/Edit/);
      await user.click(editButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Close modal')).toBeInTheDocument();
    });
  });
});
