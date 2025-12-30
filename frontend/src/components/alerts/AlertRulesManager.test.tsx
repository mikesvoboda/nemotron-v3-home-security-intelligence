import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AlertRulesManager from './AlertRulesManager';
import * as api from '../../services/api';

import type { AlertRule, AlertRuleListResponse } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

describe('AlertRulesManager', () => {
  const mockRules: AlertRule[] = [
    {
      id: 'rule-1',
      name: 'Night Intrusion Alert',
      description: 'Alert for person detection at night',
      enabled: true,
      severity: 'critical',
      risk_threshold: 70,
      object_types: ['person'],
      camera_ids: ['front_door'],
      zone_ids: null,
      min_confidence: 0.8,
      schedule: null,
      conditions: null,
      dedup_key_template: '{camera_id}:{rule_id}',
      cooldown_seconds: 300,
      channels: ['email', 'webhook'],
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'rule-2',
      name: 'Vehicle Detection',
      description: 'Alert for vehicle detection',
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
      channels: [],
      created_at: '2024-01-02T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    },
  ];

  const mockListResponse: AlertRuleListResponse = {
    rules: mockRules,
    count: 2,
    limit: 100,
    offset: 0,
  };

  const mockEmptyResponse: AlertRuleListResponse = {
    rules: [],
    count: 0,
    limit: 100,
    offset: 0,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the component header', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Alert Rules')).toBeInTheDocument();
      });

      expect(screen.getByText('Configure automated alert triggers')).toBeInTheDocument();
    });

    it('displays loading state initially', () => {
      vi.mocked(api.fetchAlertRules).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<AlertRulesManager />);

      expect(screen.getByText('Loading alert rules...')).toBeInTheDocument();
    });

    it('displays rules after loading', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      expect(screen.getByText('Vehicle Detection')).toBeInTheDocument();
    });

    it('displays rule descriptions', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Alert for person detection at night')).toBeInTheDocument();
      });
    });

    it('displays severity badges', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('critical')).toBeInTheDocument();
      });

      expect(screen.getByText('medium')).toBeInTheDocument();
    });

    it('displays condition badges', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('person')).toBeInTheDocument();
      });

      expect(screen.getByText('vehicle')).toBeInTheDocument();
    });

    it('displays cooldown times', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('5m')).toBeInTheDocument(); // 300s
      });

      expect(screen.getByText('10m')).toBeInTheDocument(); // 600s
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no rules exist', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockEmptyResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('No Alert Rules')).toBeInTheDocument();
      });

      expect(
        screen.getByText('Create your first alert rule to get notified about security events.')
      ).toBeInTheDocument();
    });

    it('shows Add Rule button in empty state', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockEmptyResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('No Alert Rules')).toBeInTheDocument();
      });

      // Should have two Add Rule buttons: header and empty state
      const addButtons = screen.getAllByText('Add Rule');
      expect(addButtons.length).toBe(2);
    });
  });

  describe('Enable/Disable Toggle', () => {
    it('displays enabled toggle for each rule', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      // Find toggle switches
      const toggles = screen.getAllByRole('switch');
      expect(toggles.length).toBe(2);
    });

    it('toggles rule enabled state when switch is clicked', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);
      vi.mocked(api.updateAlertRule).mockResolvedValue({
        ...mockRules[0],
        enabled: false,
      });

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const toggles = screen.getAllByRole('switch');
      await user.click(toggles[0]); // Click first toggle

      await waitFor(() => {
        expect(api.updateAlertRule).toHaveBeenCalledWith('rule-1', { enabled: false });
      });
    });
  });

  describe('Add Rule Modal', () => {
    it('opens add modal when Add Rule button is clicked', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByText('Add Alert Rule')).toBeInTheDocument();
    });

    it('displays form fields in add modal', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Rule Name *')).toBeInTheDocument();
      expect(screen.getByLabelText('Description')).toBeInTheDocument();
      expect(screen.getByLabelText('Severity')).toBeInTheDocument();
      expect(screen.getByLabelText('Min Risk Score')).toBeInTheDocument();
      expect(screen.getByLabelText('Min Confidence %')).toBeInTheDocument();
      expect(screen.getByLabelText('Object Types (comma-separated)')).toBeInTheDocument();
      expect(screen.getByLabelText('Cooldown (seconds)')).toBeInTheDocument();
    });

    it('validates required fields', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Try to submit with empty name
      const submitButton = screen.getByText('Create Rule');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name must be at least 2 characters')).toBeInTheDocument();
      });
    });

    it('creates rule when form is submitted with valid data', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);
      vi.mocked(api.createAlertRule).mockResolvedValue({
        id: 'rule-3',
        name: 'New Test Rule',
        description: 'Test description',
        enabled: true,
        severity: 'high',
        risk_threshold: 60,
        object_types: ['person', 'vehicle'],
        camera_ids: null,
        zone_ids: null,
        min_confidence: null,
        schedule: null,
        conditions: null,
        dedup_key_template: '{camera_id}:{rule_id}',
        cooldown_seconds: 300,
        channels: [],
        created_at: '2024-01-03T00:00:00Z',
        updated_at: '2024-01-03T00:00:00Z',
      });

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Fill form
      await user.type(screen.getByLabelText('Rule Name *'), 'New Test Rule');
      await user.type(screen.getByLabelText('Description'), 'Test description');
      await user.selectOptions(screen.getByLabelText('Severity'), 'high');
      await user.type(screen.getByLabelText('Min Risk Score'), '60');
      await user.type(screen.getByLabelText('Object Types (comma-separated)'), 'person, vehicle');

      // Submit
      const submitButton = screen.getByText('Create Rule');
      await user.click(submitButton);

      await waitFor(() => {
        expect(api.createAlertRule).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'New Test Rule',
            description: 'Test description',
            severity: 'high',
            risk_threshold: 60,
            object_types: ['person', 'vehicle'],
          })
        );
      });
    });

    it('closes modal when Cancel is clicked', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const cancelButton = screen.getByText('Cancel');
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Edit Rule Modal', () => {
    it('opens edit modal when Edit button is clicked', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const editButton = screen.getByLabelText('Edit Night Intrusion Alert');
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByText('Edit Alert Rule')).toBeInTheDocument();
    });

    it('pre-fills form with existing rule data', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const editButton = screen.getByLabelText('Edit Night Intrusion Alert');
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByDisplayValue('Night Intrusion Alert')).toBeInTheDocument();
      expect(
        within(dialog).getByDisplayValue('Alert for person detection at night')
      ).toBeInTheDocument();
      expect(within(dialog).getByDisplayValue('70')).toBeInTheDocument(); // risk_threshold
      expect(within(dialog).getByDisplayValue('person')).toBeInTheDocument();
    });

    it('updates rule when edit form is submitted', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);
      vi.mocked(api.updateAlertRule).mockResolvedValue({
        ...mockRules[0],
        name: 'Updated Rule Name',
      });

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const editButton = screen.getByLabelText('Edit Night Intrusion Alert');
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      const nameInput = within(dialog).getByLabelText('Rule Name *');

      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Rule Name');

      const submitButton = within(dialog).getByText('Update Rule');
      await user.click(submitButton);

      await waitFor(() => {
        expect(api.updateAlertRule).toHaveBeenCalledWith(
          'rule-1',
          expect.objectContaining({
            name: 'Updated Rule Name',
          })
        );
      });
    });
  });

  describe('Delete Rule', () => {
    it('opens delete confirmation modal when Delete button is clicked', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const deleteButton = screen.getByLabelText('Delete Night Intrusion Alert');
      await user.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText('Delete Alert Rule')).toBeInTheDocument();
      });

      // Check that the rule name appears in the delete confirmation
      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByText('Night Intrusion Alert')).toBeInTheDocument();
    });

    it('deletes rule when confirmed', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);
      vi.mocked(api.deleteAlertRule).mockResolvedValue(undefined);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const deleteButton = screen.getByLabelText('Delete Night Intrusion Alert');
      await user.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText('Delete Alert Rule')).toBeInTheDocument();
      });

      const confirmButton = screen.getByText('Delete Rule');
      await user.click(confirmButton);

      await waitFor(() => {
        expect(api.deleteAlertRule).toHaveBeenCalledWith('rule-1');
      });
    });

    it('closes delete modal when Cancel is clicked', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const deleteButton = screen.getByLabelText('Delete Night Intrusion Alert');
      await user.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText('Delete Alert Rule')).toBeInTheDocument();
      });

      const cancelButton = screen.getAllByText('Cancel')[0];
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByText('Delete Alert Rule')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching rules fails', async () => {
      vi.mocked(api.fetchAlertRules).mockRejectedValue(new Error('Network error'));

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('displays error when creating rule fails', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);
      vi.mocked(api.createAlertRule).mockRejectedValue(new Error('Failed to create rule'));

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText('Rule Name *'), 'Test Rule');

      const submitButton = screen.getByText('Create Rule');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Failed to create rule')).toBeInTheDocument();
      });
    });

    it('dismisses error when X button is clicked', async () => {
      vi.mocked(api.fetchAlertRules).mockRejectedValue(new Error('Network error'));

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      const dismissButton = screen.getByLabelText('Dismiss error');
      await user.click(dismissButton);

      await waitFor(() => {
        expect(screen.queryByText('Network error')).not.toBeInTheDocument();
      });
    });
  });

  describe('Refresh', () => {
    it('refreshes rules when refresh button is clicked', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      expect(api.fetchAlertRules).toHaveBeenCalledTimes(1);

      const refreshButton = screen.getByLabelText('Refresh rules');
      await user.click(refreshButton);

      await waitFor(() => {
        expect(api.fetchAlertRules).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Form Validation', () => {
    it('validates name is required and has minimum length', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Try to submit with single character name
      await user.type(screen.getByLabelText('Rule Name *'), 'A');

      const submitButton = screen.getByText('Create Rule');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('Name must be at least 2 characters')).toBeInTheDocument();
      });
    });

    it('submits form successfully with valid risk threshold', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);
      vi.mocked(api.createAlertRule).mockResolvedValue({
        id: 'rule-3',
        name: 'Test Rule',
        description: null,
        enabled: true,
        severity: 'medium',
        risk_threshold: 50,
        object_types: null,
        camera_ids: null,
        zone_ids: null,
        min_confidence: null,
        schedule: null,
        conditions: null,
        dedup_key_template: '{camera_id}:{rule_id}',
        cooldown_seconds: 300,
        channels: [],
        created_at: '2024-01-03T00:00:00Z',
        updated_at: '2024-01-03T00:00:00Z',
      });

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText('Rule Name *'), 'Test Rule');
      await user.type(screen.getByLabelText('Min Risk Score'), '50'); // Valid

      const submitButton = screen.getByText('Create Rule');
      await user.click(submitButton);

      await waitFor(() => {
        expect(api.createAlertRule).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'Test Rule',
            risk_threshold: 50,
          })
        );
      });
    });

    it('submits form successfully with valid min confidence', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);
      vi.mocked(api.createAlertRule).mockResolvedValue({
        id: 'rule-3',
        name: 'Test Rule',
        description: null,
        enabled: true,
        severity: 'medium',
        risk_threshold: null,
        object_types: null,
        camera_ids: null,
        zone_ids: null,
        min_confidence: 0.75,
        schedule: null,
        conditions: null,
        dedup_key_template: '{camera_id}:{rule_id}',
        cooldown_seconds: 300,
        channels: [],
        created_at: '2024-01-03T00:00:00Z',
        updated_at: '2024-01-03T00:00:00Z',
      });

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText('Rule Name *'), 'Test Rule');
      await user.type(screen.getByLabelText('Min Confidence %'), '75'); // Valid

      const submitButton = screen.getByText('Create Rule');
      await user.click(submitButton);

      await waitFor(() => {
        expect(api.createAlertRule).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'Test Rule',
            min_confidence: 0.75,
          })
        );
      });
    });

    it('submits form successfully with valid cooldown', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);
      vi.mocked(api.createAlertRule).mockResolvedValue({
        id: 'rule-3',
        name: 'Test Rule',
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
        cooldown_seconds: 600,
        channels: [],
        created_at: '2024-01-03T00:00:00Z',
        updated_at: '2024-01-03T00:00:00Z',
      });

      const user = userEvent.setup();
      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      const addButton = screen.getAllByText('Add Rule')[0];
      await user.click(addButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText('Rule Name *'), 'Test Rule');

      const cooldownInput = screen.getByLabelText('Cooldown (seconds)');
      await user.clear(cooldownInput);
      await user.type(cooldownInput, '600'); // Valid

      const submitButton = screen.getByText('Create Rule');
      await user.click(submitButton);

      await waitFor(() => {
        expect(api.createAlertRule).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'Test Rule',
            cooldown_seconds: 600,
          })
        );
      });
    });
  });

  describe('Accessibility', () => {
    it('has accessible labels for action buttons', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Edit Night Intrusion Alert')).toBeInTheDocument();
      expect(screen.getByLabelText('Delete Night Intrusion Alert')).toBeInTheDocument();
      expect(screen.getByLabelText('Edit Vehicle Detection')).toBeInTheDocument();
      expect(screen.getByLabelText('Delete Vehicle Detection')).toBeInTheDocument();
    });

    it('has accessible label for refresh button', async () => {
      vi.mocked(api.fetchAlertRules).mockResolvedValue(mockListResponse);

      render(<AlertRulesManager />);

      await waitFor(() => {
        expect(screen.getByText('Night Intrusion Alert')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Refresh rules')).toBeInTheDocument();
    });
  });
});
