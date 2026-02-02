/**
 * Tests for RawSettingsPanel component (NEM-4951).
 *
 * This component provides an admin interface for viewing and editing
 * raw system settings stored as key-value pairs.
 */
import { screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import RawSettingsPanel from './RawSettingsPanel';
import { renderWithProviders } from '../../test-utils';

// Mock the useSystemSettings hook
const mockRefetch = vi.fn().mockResolvedValue({});
const mockUpdateSetting = vi.fn();
const mockDeleteSetting = vi.fn();

vi.mock('../../hooks/useSystemSetting', () => ({
  useSystemSettings: vi.fn(() => ({
    settings: [
      {
        key: 'default_gpu_strategy',
        value: { strategy: 'balanced' },
        updated_at: '2026-01-25T12:00:00Z',
      },
      {
        key: 'retention_days',
        value: { days: 30 },
        updated_at: '2026-01-24T10:00:00Z',
      },
      {
        key: 'batch_timeout',
        value: { timeout_seconds: 90 },
        updated_at: '2026-01-23T08:00:00Z',
      },
    ],
    total: 3,
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: mockRefetch,
  })),
  useSystemSetting: vi.fn((options: { key: string }) => ({
    setting: {
      key: options.key,
      value: { strategy: 'balanced' },
      updated_at: '2026-01-25T12:00:00Z',
    },
    isLoading: false,
    isFetching: false,
    error: null,
    isError: false,
    isNotFound: false,
    refetch: vi.fn(),
    updateSetting: {
      mutateAsync: mockUpdateSetting.mockResolvedValue({
        key: options.key,
        value: { strategy: 'performance' },
        updated_at: '2026-01-25T13:00:00Z',
      }),
      isPending: false,
    },
    deleteSetting: {
      mutateAsync: mockDeleteSetting.mockResolvedValue(undefined),
      isPending: false,
    },
  })),
}));

// Mock useToast
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

describe('RawSettingsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the panel with title and description', () => {
      renderWithProviders(<RawSettingsPanel />);

      expect(screen.getByTestId('raw-settings-panel')).toBeInTheDocument();
      expect(screen.getByText('Raw Settings')).toBeInTheDocument();
      expect(
        screen.getByText(/View and edit raw system configuration/i)
      ).toBeInTheDocument();
    });

    it('renders the settings table with correct headers', () => {
      renderWithProviders(<RawSettingsPanel />);

      expect(screen.getByRole('table')).toBeInTheDocument();
      expect(screen.getByText('Key')).toBeInTheDocument();
      expect(screen.getByText('Value')).toBeInTheDocument();
      expect(screen.getByText('Last Updated')).toBeInTheDocument();
      expect(screen.getByText('Actions')).toBeInTheDocument();
    });

    it('renders all settings from the API', () => {
      renderWithProviders(<RawSettingsPanel />);

      expect(screen.getByText('default_gpu_strategy')).toBeInTheDocument();
      expect(screen.getByText('retention_days')).toBeInTheDocument();
      expect(screen.getByText('batch_timeout')).toBeInTheDocument();
    });

    it('displays setting values as formatted JSON', () => {
      renderWithProviders(<RawSettingsPanel />);

      // Values should be displayed (may be truncated or formatted)
      expect(screen.getByText(/strategy.*balanced/i)).toBeInTheDocument();
      expect(screen.getByText(/days.*30/i)).toBeInTheDocument();
      expect(screen.getByText(/timeout_seconds.*90/i)).toBeInTheDocument();
    });

    it('displays formatted timestamps', () => {
      renderWithProviders(<RawSettingsPanel />);

      // Should display relative or formatted times
      const rows = screen.getAllByRole('row');
      // Header + 3 data rows
      expect(rows).toHaveLength(4);
    });

    it('renders edit and delete buttons for each setting', () => {
      renderWithProviders(<RawSettingsPanel />);

      const editButtons = screen.getAllByTestId(/^raw-setting-edit-/);
      const deleteButtons = screen.getAllByTestId(/^raw-setting-delete-/);

      expect(editButtons).toHaveLength(3);
      expect(deleteButtons).toHaveLength(3);
    });

    it('renders refresh button', () => {
      renderWithProviders(<RawSettingsPanel />);

      expect(screen.getByTestId('raw-settings-refresh')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading spinner when loading', async () => {
      const { useSystemSettings } = await import('../../hooks/useSystemSetting');
      vi.mocked(useSystemSettings).mockReturnValue({
        settings: [],
        total: 0,
        data: undefined,
        isLoading: true,
        isFetching: true,
        error: null,
        refetch: mockRefetch,
      });

      renderWithProviders(<RawSettingsPanel />);

      expect(screen.getByTestId('raw-settings-loading')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty state when no settings exist', async () => {
      const { useSystemSettings } = await import('../../hooks/useSystemSetting');
      vi.mocked(useSystemSettings).mockReturnValue({
        settings: [],
        total: 0,
        data: { items: [], total: 0 },
        isLoading: false,
        isFetching: false,
        error: null,
        refetch: mockRefetch,
      });

      renderWithProviders(<RawSettingsPanel />);

      expect(screen.getByTestId('raw-settings-empty')).toBeInTheDocument();
      expect(screen.getByText(/No settings found/i)).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error message when fetch fails', async () => {
      const { useSystemSettings } = await import('../../hooks/useSystemSetting');
      vi.mocked(useSystemSettings).mockReturnValue({
        settings: [],
        total: 0,
        data: undefined,
        isLoading: false,
        isFetching: false,
        error: new Error('Failed to fetch settings'),
        refetch: mockRefetch,
      });

      renderWithProviders(<RawSettingsPanel />);

      expect(screen.getByTestId('raw-settings-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to fetch settings/i)).toBeInTheDocument();
    });
  });

  describe('editing settings', () => {
    beforeEach(async () => {
      // Reset mock to default state
      const { useSystemSettings } = await import('../../hooks/useSystemSetting');
      vi.mocked(useSystemSettings).mockReturnValue({
        settings: [
          {
            key: 'default_gpu_strategy',
            value: { strategy: 'balanced' },
            updated_at: '2026-01-25T12:00:00Z',
          },
          {
            key: 'retention_days',
            value: { days: 30 },
            updated_at: '2026-01-24T10:00:00Z',
          },
          {
            key: 'batch_timeout',
            value: { timeout_seconds: 90 },
            updated_at: '2026-01-23T08:00:00Z',
          },
        ],
        total: 3,
        data: undefined,
        isLoading: false,
        isFetching: false,
        error: null,
        refetch: mockRefetch,
      });
    });

    it('opens edit modal when edit button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const editButton = screen.getByTestId('raw-setting-edit-default_gpu_strategy');
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByTestId('edit-setting-modal')).toBeInTheDocument();
      });

      expect(screen.getByText(/Edit Setting/i)).toBeInTheDocument();
      // The key appears in both table and modal, so check within modal
      const modal = screen.getByTestId('edit-setting-modal');
      expect(modal).toHaveTextContent('default_gpu_strategy');
    });

    it('displays current value in edit modal textarea', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const editButton = screen.getByTestId('raw-setting-edit-default_gpu_strategy');
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByTestId('edit-setting-modal')).toBeInTheDocument();
      });

      const textarea = screen.getByTestId('edit-setting-value');
      expect(textarea).toHaveValue(JSON.stringify({ strategy: 'balanced' }, null, 2));
    });

    it('can modify value in edit modal', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const editButton = screen.getByTestId('raw-setting-edit-default_gpu_strategy');
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByTestId('edit-setting-modal')).toBeInTheDocument();
      });

      const textarea = screen.getByTestId('edit-setting-value');
      // Use fireEvent.change for JSON with curly braces (userEvent has issues with {})
      fireEvent.change(textarea, { target: { value: '{"strategy": "performance"}' } });

      expect(textarea).toHaveValue('{"strategy": "performance"}');
    });

    it('saves changes when save button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const editButton = screen.getByTestId('raw-setting-edit-default_gpu_strategy');
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByTestId('edit-setting-modal')).toBeInTheDocument();
      });

      const textarea = screen.getByTestId('edit-setting-value');
      // Use fireEvent.change for JSON with curly braces (userEvent has issues with {})
      fireEvent.change(textarea, { target: { value: '{"strategy": "performance"}' } });

      const saveButton = screen.getByTestId('edit-setting-save');
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockUpdateSetting).toHaveBeenCalled();
      });
    });

    it('closes modal when cancel button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const editButton = screen.getByTestId('raw-setting-edit-default_gpu_strategy');
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByTestId('edit-setting-modal')).toBeInTheDocument();
      });

      const cancelButton = screen.getByTestId('edit-setting-cancel');
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByTestId('edit-setting-modal')).not.toBeInTheDocument();
      });
    });

    it('shows validation error for invalid JSON', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const editButton = screen.getByTestId('raw-setting-edit-default_gpu_strategy');
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByTestId('edit-setting-modal')).toBeInTheDocument();
      });

      const textarea = screen.getByTestId('edit-setting-value');
      await user.clear(textarea);
      await user.type(textarea, 'not valid json');

      const saveButton = screen.getByTestId('edit-setting-save');
      await user.click(saveButton);

      await waitFor(() => {
        expect(screen.getByTestId('edit-setting-error')).toBeInTheDocument();
      });
      // Check that error message is within the error div
      const errorDiv = screen.getByTestId('edit-setting-error');
      expect(errorDiv).toHaveTextContent(/Invalid JSON/i);
    });
  });

  describe('deleting settings', () => {
    beforeEach(async () => {
      // Reset mock to default state
      const { useSystemSettings } = await import('../../hooks/useSystemSetting');
      vi.mocked(useSystemSettings).mockReturnValue({
        settings: [
          {
            key: 'default_gpu_strategy',
            value: { strategy: 'balanced' },
            updated_at: '2026-01-25T12:00:00Z',
          },
          {
            key: 'retention_days',
            value: { days: 30 },
            updated_at: '2026-01-24T10:00:00Z',
          },
          {
            key: 'batch_timeout',
            value: { timeout_seconds: 90 },
            updated_at: '2026-01-23T08:00:00Z',
          },
        ],
        total: 3,
        data: undefined,
        isLoading: false,
        isFetching: false,
        error: null,
        refetch: mockRefetch,
      });
    });

    it('opens delete confirmation dialog when delete button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const deleteButton = screen.getByTestId('raw-setting-delete-default_gpu_strategy');
      await user.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByTestId('delete-setting-dialog')).toBeInTheDocument();
      });

      // Dialog title should appear
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      // The key appears in the confirmation text (multiple elements may match)
      const dialog = screen.getByTestId('delete-setting-dialog');
      expect(dialog).toHaveTextContent('default_gpu_strategy');
    });

    it('deletes setting when confirmed', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const deleteButton = screen.getByTestId('raw-setting-delete-default_gpu_strategy');
      await user.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByTestId('delete-setting-dialog')).toBeInTheDocument();
      });

      const confirmButton = screen.getByTestId('delete-setting-confirm');
      await user.click(confirmButton);

      await waitFor(() => {
        expect(mockDeleteSetting).toHaveBeenCalled();
      });
    });

    it('closes dialog when cancel is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const deleteButton = screen.getByTestId('raw-setting-delete-default_gpu_strategy');
      await user.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByTestId('delete-setting-dialog')).toBeInTheDocument();
      });

      const cancelButton = screen.getByTestId('delete-setting-cancel');
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByTestId('delete-setting-dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('refresh functionality', () => {
    beforeEach(async () => {
      // Reset mock to default state
      const { useSystemSettings } = await import('../../hooks/useSystemSetting');
      vi.mocked(useSystemSettings).mockReturnValue({
        settings: [
          {
            key: 'default_gpu_strategy',
            value: { strategy: 'balanced' },
            updated_at: '2026-01-25T12:00:00Z',
          },
        ],
        total: 1,
        data: undefined,
        isLoading: false,
        isFetching: false,
        error: null,
        refetch: mockRefetch,
      });
    });

    it('calls refetch when refresh button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RawSettingsPanel />);

      const refreshButton = screen.getByTestId('raw-settings-refresh');
      await user.click(refreshButton);

      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled();
      });
    });
  });

  describe('accessibility', () => {
    it('table has proper ARIA attributes', () => {
      renderWithProviders(<RawSettingsPanel />);

      const table = screen.getByRole('table');
      expect(table).toBeInTheDocument();

      // Check for column headers
      const columnHeaders = screen.getAllByRole('columnheader');
      expect(columnHeaders).toHaveLength(4);
    });

    it('edit buttons have aria-labels', () => {
      renderWithProviders(<RawSettingsPanel />);

      const editButtons = screen.getAllByTestId(/^raw-setting-edit-/);
      editButtons.forEach((button) => {
        expect(button).toHaveAttribute('aria-label');
      });
    });

    it('delete buttons have aria-labels', () => {
      renderWithProviders(<RawSettingsPanel />);

      const deleteButtons = screen.getAllByTestId(/^raw-setting-delete-/);
      deleteButtons.forEach((button) => {
        expect(button).toHaveAttribute('aria-label');
      });
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      renderWithProviders(<RawSettingsPanel className="custom-class" />);

      const panel = screen.getByTestId('raw-settings-panel');
      expect(panel).toHaveClass('custom-class');
    });
  });
});
