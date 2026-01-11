import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import NotificationPreferencesForm from './NotificationPreferencesForm';
import * as notificationPreferencesQuery from '../../hooks/useNotificationPreferencesQuery';

import type {
  NotificationPreferences,
  QuietHoursPeriod,
} from '../../types/notificationPreferences';

// Mock the hooks
vi.mock('../../hooks/useNotificationPreferencesQuery', () => ({
  useGlobalNotificationPreferencesQuery: vi.fn(),
  useQuietHoursPeriodsQuery: vi.fn(),
  useNotificationPreferencesMutation: vi.fn(),
}));

const mockUseGlobalNotificationPreferencesQuery = vi.mocked(
  notificationPreferencesQuery.useGlobalNotificationPreferencesQuery
);
const mockUseQuietHoursPeriodsQuery = vi.mocked(
  notificationPreferencesQuery.useQuietHoursPeriodsQuery
);
const mockUseNotificationPreferencesMutation = vi.mocked(
  notificationPreferencesQuery.useNotificationPreferencesMutation
);

describe('NotificationPreferencesForm', () => {
  let queryClient: QueryClient;

  const mockPreferences: NotificationPreferences = {
    id: 1,
    enabled: true,
    sound: 'default',
    risk_filters: ['critical', 'high', 'medium'],
  };

  const mockQuietHoursPeriods: QuietHoursPeriod[] = [
    {
      id: 'period-1',
      label: 'Night Hours',
      start_time: '22:00:00',
      end_time: '06:00:00',
      days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
    },
  ];

  const mockUpdateGlobalMutation = {
    mutateAsync: vi.fn().mockResolvedValue(mockPreferences),
    isPending: false,
    error: null,
  };

  const mockCreateQuietHoursMutation = {
    mutateAsync: vi.fn().mockResolvedValue(mockQuietHoursPeriods[0]),
    isPending: false,
    error: null,
  };

  const mockDeleteQuietHoursMutation = {
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
    error: null,
  };

  const mockUpdateCameraMutation = {
    mutateAsync: vi.fn(),
    isPending: false,
    error: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    mockUseGlobalNotificationPreferencesQuery.mockReturnValue({
      preferences: mockPreferences,
      isLoading: false,
      isRefetching: false,
      error: null,
      refetch: vi.fn(),
    });

    mockUseQuietHoursPeriodsQuery.mockReturnValue({
      periods: mockQuietHoursPeriods,
      isLoading: false,
      isRefetching: false,
      error: null,
      refetch: vi.fn(),
    });

    mockUseNotificationPreferencesMutation.mockReturnValue({
      updateGlobalMutation: mockUpdateGlobalMutation as never,
      createQuietHoursMutation: mockCreateQuietHoursMutation as never,
      deleteQuietHoursMutation: mockDeleteQuietHoursMutation as never,
      updateCameraMutation: mockUpdateCameraMutation as never,
    });
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <NotificationPreferencesForm />
      </QueryClientProvider>
    );
  };

  // ============================================================================
  // Basic Rendering Tests
  // ============================================================================

  describe('Basic Rendering', () => {
    it('should render the form title', () => {
      renderComponent();
      expect(screen.getByText('Notification Preferences')).toBeInTheDocument();
    });

    it('should show loading state while fetching preferences', () => {
      mockUseGlobalNotificationPreferencesQuery.mockReturnValue({
        preferences: undefined,
        isLoading: true,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('should display error message when preferences fail to load', () => {
      mockUseGlobalNotificationPreferencesQuery.mockReturnValue({
        preferences: undefined,
        isLoading: false,
        isRefetching: false,
        error: new Error('Failed to fetch preferences'),
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByText('Failed to fetch preferences')).toBeInTheDocument();
    });

    it('should display retry button on error', async () => {
      const mockRefetch = vi.fn();
      mockUseGlobalNotificationPreferencesQuery.mockReturnValue({
        preferences: undefined,
        isLoading: false,
        isRefetching: false,
        error: new Error('Network error'),
        refetch: mockRefetch,
      });

      const user = userEvent.setup();
      renderComponent();

      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Global Notification Toggle Tests
  // ============================================================================

  describe('Global Notification Toggle', () => {
    it('should render the notifications enabled toggle', () => {
      renderComponent();
      expect(screen.getByRole('switch', { name: /enable notifications/i })).toBeInTheDocument();
    });

    it('should show toggle as checked when notifications are enabled', () => {
      renderComponent();
      const toggle = screen.getByRole('switch', { name: /enable notifications/i });
      expect(toggle).toHaveAttribute('aria-checked', 'true');
    });

    it('should show toggle as unchecked when notifications are disabled', () => {
      mockUseGlobalNotificationPreferencesQuery.mockReturnValue({
        preferences: { ...mockPreferences, enabled: false },
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent();
      const toggle = screen.getByRole('switch', { name: /enable notifications/i });
      expect(toggle).toHaveAttribute('aria-checked', 'false');
    });

    it('should call updateGlobalMutation when toggle is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      const toggle = screen.getByRole('switch', { name: /enable notifications/i });
      await user.click(toggle);

      expect(mockUpdateGlobalMutation.mutateAsync).toHaveBeenCalledWith({
        enabled: false,
      });
    });
  });

  // ============================================================================
  // Notification Sound Selection Tests
  // ============================================================================

  describe('Notification Sound Selection', () => {
    it('should render the sound selection dropdown', () => {
      renderComponent();
      expect(screen.getByText('Notification Sound')).toBeInTheDocument();
    });

    it('should display current sound selection', () => {
      renderComponent();
      // Use getAllByText since "Default" appears multiple times (hidden option + display span)
      const defaultElements = screen.getAllByText('Default');
      expect(defaultElements.length).toBeGreaterThanOrEqual(1);
    });

    it('should show all sound options when dropdown is opened', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Find and click the select to open it
      const selectButton = screen.getByRole('combobox');
      await user.click(selectButton);

      await waitFor(() => {
        expect(screen.getByRole('option', { name: /none \(silent\)/i })).toBeInTheDocument();
        expect(screen.getByRole('option', { name: /^default$/i })).toBeInTheDocument();
        expect(screen.getByRole('option', { name: /alert/i })).toBeInTheDocument();
        expect(screen.getByRole('option', { name: /chime/i })).toBeInTheDocument();
        expect(screen.getByRole('option', { name: /urgent/i })).toBeInTheDocument();
      });
    });

    it('should render dropdown with available options', async () => {
      const user = userEvent.setup();
      renderComponent();

      const selectButton = screen.getByRole('combobox');
      await user.click(selectButton);

      // Wait for dropdown to open and verify options are available
      const urgentOption = await screen.findByRole('option', { name: /urgent/i });
      expect(urgentOption).toBeInTheDocument();

      // Verify other options are available
      expect(screen.getByRole('option', { name: /alert/i })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: /chime/i })).toBeInTheDocument();
    });

    it('should render sound selector when notifications are enabled', () => {
      renderComponent();
      // Verify the select exists and is interactive
      const selectButton = screen.getByRole('combobox');
      expect(selectButton).toBeInTheDocument();
    });

    it('should render sound selector when notifications are disabled', () => {
      mockUseGlobalNotificationPreferencesQuery.mockReturnValue({
        preferences: { ...mockPreferences, enabled: false },
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent();
      // Verify the select exists - Tremor manages disabled state internally via the disabled prop
      const selectButton = screen.getByRole('combobox');
      expect(selectButton).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Risk Filter Tests
  // ============================================================================

  describe('Risk Filter Checkboxes', () => {
    it('should render all risk level checkboxes', () => {
      renderComponent();

      expect(screen.getByRole('button', { name: /critical/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /high/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /medium/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /low/i })).toBeInTheDocument();
    });

    it('should show checked risk filters based on preferences', () => {
      renderComponent();

      // Critical, High, Medium should be selected (in preferences)
      const criticalBtn = screen.getByRole('button', { name: /critical/i });
      const highBtn = screen.getByRole('button', { name: /high/i });
      const mediumBtn = screen.getByRole('button', { name: /medium/i });
      const lowBtn = screen.getByRole('button', { name: /low/i });

      // Selected buttons should have different styling (check aria or class)
      expect(criticalBtn).toHaveClass('bg-red-500/20');
      expect(highBtn).toHaveClass('bg-orange-500/20');
      expect(mediumBtn).toHaveClass('bg-yellow-500/20');
      expect(lowBtn).not.toHaveClass('bg-green-500/20');
    });

    it('should call updateGlobalMutation when risk filter is toggled', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Click on "low" to add it
      const lowBtn = screen.getByRole('button', { name: /low/i });
      await user.click(lowBtn);

      expect(mockUpdateGlobalMutation.mutateAsync).toHaveBeenCalledWith({
        risk_filters: ['critical', 'high', 'medium', 'low'],
      });
    });

    it('should remove risk filter when already selected filter is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Click on "critical" to remove it
      const criticalBtn = screen.getByRole('button', { name: /critical/i });
      await user.click(criticalBtn);

      expect(mockUpdateGlobalMutation.mutateAsync).toHaveBeenCalledWith({
        risk_filters: ['high', 'medium'],
      });
    });

    it('should show warning when no risk filters are selected', () => {
      mockUseGlobalNotificationPreferencesQuery.mockReturnValue({
        preferences: { ...mockPreferences, risk_filters: [] },
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent();
      expect(
        screen.getByText(/no risk levels selected.*will not receive any notifications/i)
      ).toBeInTheDocument();
    });

    it('should disable risk filters when notifications are disabled', () => {
      mockUseGlobalNotificationPreferencesQuery.mockReturnValue({
        preferences: { ...mockPreferences, enabled: false },
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent();

      const criticalBtn = screen.getByRole('button', { name: /critical/i });
      expect(criticalBtn).toBeDisabled();
    });
  });

  // ============================================================================
  // Quiet Hours Section Tests
  // ============================================================================

  describe('Quiet Hours Section', () => {
    it('should render quiet hours section header', () => {
      renderComponent();
      expect(screen.getByText('Quiet Hours')).toBeInTheDocument();
    });

    it('should display existing quiet hours periods', () => {
      renderComponent();
      expect(screen.getByText('Night Hours')).toBeInTheDocument();
      // Use getAllByText since the time pattern appears in badge and tip
      const timeElements = screen.getAllByText(/22:00.*06:00/);
      expect(timeElements.length).toBeGreaterThanOrEqual(1);
    });

    it('should show "Add Period" button', () => {
      renderComponent();
      expect(screen.getByRole('button', { name: /add period/i })).toBeInTheDocument();
    });

    it('should show create form when "Add Period" is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/start time/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/end time/i)).toBeInTheDocument();
      });
    });

    it('should hide create form when Cancel is clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      await waitFor(() => {
        expect(screen.queryByLabelText(/label/i)).not.toBeInTheDocument();
      });
    });

    it('should show empty state when no quiet hours exist', () => {
      mockUseQuietHoursPeriodsQuery.mockReturnValue({
        periods: [],
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn(),
      });

      renderComponent();
      expect(screen.getByText(/no quiet hours configured/i)).toBeInTheDocument();
    });

    it('should show delete button for each period', () => {
      renderComponent();
      // The delete button has aria-label="Delete"
      expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
    });

    it('should call deleteQuietHoursMutation when delete is confirmed', async () => {
      const user = userEvent.setup();
      renderComponent();

      // Find and click the delete button with aria-label
      const deleteBtn = screen.getByRole('button', { name: 'Delete' });
      await user.click(deleteBtn);

      // Confirm deletion
      await waitFor(() => {
        expect(screen.getByText('Delete?')).toBeInTheDocument();
      });
      const confirmBtn = screen.getByRole('button', { name: /^delete$/i });
      await user.click(confirmBtn);

      expect(mockDeleteQuietHoursMutation.mutateAsync).toHaveBeenCalledWith('period-1');
    });
  });

  // ============================================================================
  // Quiet Hours Form Validation Tests
  // ============================================================================

  describe('Quiet Hours Form Validation', () => {
    it('should show validation error when label is empty', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
      });

      // Try to submit without entering a label
      await user.click(screen.getByRole('button', { name: /create period/i }));

      await waitFor(() => {
        // Find error message in the form
        const form = screen.getByTestId('quiet-hours-form');
        expect(within(form).getByText(/label is required/i)).toBeInTheDocument();
      });
    });

    it('should respect maxLength on label input field', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
      });

      // Verify the input has maxLength attribute
      const labelInput = screen.getByLabelText(/label/i);
      expect(labelInput).toHaveAttribute('maxLength', '255');

      // Type a valid label and verify it works
      await user.type(labelInput, 'Test Label');
      expect(labelInput).toHaveValue('Test Label');
    });

    it('should validate label using validateQuietHoursLabel function', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
      });

      // Enter only whitespace (should fail validation)
      const labelInput = screen.getByLabelText(/label/i);
      await user.type(labelInput, '   ');

      await user.click(screen.getByRole('button', { name: /create period/i }));

      await waitFor(() => {
        const form = screen.getByTestId('quiet-hours-form');
        expect(within(form).getByText(/label is required/i)).toBeInTheDocument();
      });
    });

    it('should show validation error when start time equals end time', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
      });

      const labelInput = screen.getByLabelText(/label/i);
      await user.type(labelInput, 'Test Period');

      // Set same start and end time
      const startInput = screen.getByLabelText(/start time/i);
      const endInput = screen.getByLabelText(/end time/i);

      await user.clear(startInput);
      await user.type(startInput, '10:00');
      await user.clear(endInput);
      await user.type(endInput, '10:00');

      await user.click(screen.getByRole('button', { name: /create period/i }));

      await waitFor(() => {
        expect(screen.getByText(/start time must be different from end time/i)).toBeInTheDocument();
      });
    });

    it('should show validation error when no days are selected', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
      });

      const labelInput = screen.getByLabelText(/label/i);
      await user.type(labelInput, 'Test Period');

      // Click "None" to deselect all days
      await user.click(screen.getByRole('button', { name: /^none$/i }));

      await user.click(screen.getByRole('button', { name: /create period/i }));

      await waitFor(() => {
        expect(screen.getByText(/at least one day must be selected/i)).toBeInTheDocument();
      });
    });

    it('should successfully create period with valid data', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
      });

      const labelInput = screen.getByLabelText(/label/i);
      await user.type(labelInput, 'Work Hours');

      await user.click(screen.getByRole('button', { name: /create period/i }));

      await waitFor(() => {
        expect(mockCreateQuietHoursMutation.mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            label: 'Work Hours',
          })
        );
      });
    });
  });

  // ============================================================================
  // Day Selection Tests
  // ============================================================================

  describe('Day Selection in Quiet Hours Form', () => {
    it('should render all day buttons', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^mon$/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^tue$/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^wed$/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^thu$/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^fri$/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^sat$/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^sun$/i })).toBeInTheDocument();
      });
    });

    it('should select all days by default', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        // All days should be selected by default (have the selected class)
        const monButton = screen.getByRole('button', { name: /^mon$/i });
        expect(monButton).toHaveClass('border-[#76B900]');
      });
    });

    it('should toggle day selection when clicked', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^mon$/i })).toBeInTheDocument();
      });

      const monButton = screen.getByRole('button', { name: /^mon$/i });
      await user.click(monButton);

      // After clicking, Monday should be deselected
      expect(monButton).not.toHaveClass('border-[#76B900]');
    });

    it('should select weekdays preset', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^weekdays$/i })).toBeInTheDocument();
      });

      // First click "None" to deselect all
      await user.click(screen.getByRole('button', { name: /^none$/i }));

      // Then click "Weekdays"
      await user.click(screen.getByRole('button', { name: /^weekdays$/i }));

      // Check weekdays are selected
      expect(screen.getByRole('button', { name: /^mon$/i })).toHaveClass('border-[#76B900]');
      expect(screen.getByRole('button', { name: /^tue$/i })).toHaveClass('border-[#76B900]');
      expect(screen.getByRole('button', { name: /^wed$/i })).toHaveClass('border-[#76B900]');
      expect(screen.getByRole('button', { name: /^thu$/i })).toHaveClass('border-[#76B900]');
      expect(screen.getByRole('button', { name: /^fri$/i })).toHaveClass('border-[#76B900]');

      // Weekends should not be selected
      expect(screen.getByRole('button', { name: /^sat$/i })).not.toHaveClass('border-[#76B900]');
      expect(screen.getByRole('button', { name: /^sun$/i })).not.toHaveClass('border-[#76B900]');
    });

    it('should select weekends preset', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /^weekends$/i })).toBeInTheDocument();
      });

      // First click "None" to deselect all
      await user.click(screen.getByRole('button', { name: /^none$/i }));

      // Then click "Weekends"
      await user.click(screen.getByRole('button', { name: /^weekends$/i }));

      // Weekends should be selected
      expect(screen.getByRole('button', { name: /^sat$/i })).toHaveClass('border-[#76B900]');
      expect(screen.getByRole('button', { name: /^sun$/i })).toHaveClass('border-[#76B900]');

      // Weekdays should not be selected
      expect(screen.getByRole('button', { name: /^mon$/i })).not.toHaveClass('border-[#76B900]');
    });
  });

  // ============================================================================
  // Field Error Display Tests
  // ============================================================================

  describe('Field Error Display', () => {
    it('should display validation error near the label field', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create period/i }));

      await waitFor(() => {
        // Error should appear within the form, near the label field
        const form = screen.getByTestId('quiet-hours-form');
        expect(within(form).getByText(/label is required/i)).toBeInTheDocument();
      });
    });

    it('should clear validation error when field is corrected', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
      });

      // Submit with empty label to trigger error
      await user.click(screen.getByRole('button', { name: /create period/i }));

      await waitFor(() => {
        const form = screen.getByTestId('quiet-hours-form');
        expect(within(form).getByText(/label is required/i)).toBeInTheDocument();
      });

      // Type in the label field - use a simpler string
      const labelInput = screen.getByLabelText(/label/i);
      await user.type(labelInput, 'ValidLabel');

      // Error should be cleared
      await waitFor(() => {
        const form = screen.getByTestId('quiet-hours-form');
        expect(within(form).queryByText(/label is required/i)).not.toBeInTheDocument();
      });
    });
  });

  // ============================================================================
  // Mutation State Tests
  // ============================================================================

  describe('Mutation States', () => {
    it('should show loading state when updating preferences', () => {
      mockUseNotificationPreferencesMutation.mockReturnValue({
        updateGlobalMutation: { ...mockUpdateGlobalMutation, isPending: true } as never,
        createQuietHoursMutation: mockCreateQuietHoursMutation as never,
        deleteQuietHoursMutation: mockDeleteQuietHoursMutation as never,
        updateCameraMutation: mockUpdateCameraMutation as never,
      });

      renderComponent();

      // Toggle and other controls should be disabled during update
      const toggle = screen.getByRole('switch', { name: /enable notifications/i });
      expect(toggle).toHaveClass('opacity-50');
    });

    it('should display error when update fails', () => {
      mockUseNotificationPreferencesMutation.mockReturnValue({
        updateGlobalMutation: {
          ...mockUpdateGlobalMutation,
          error: new Error('Update failed'),
        } as never,
        createQuietHoursMutation: mockCreateQuietHoursMutation as never,
        deleteQuietHoursMutation: mockDeleteQuietHoursMutation as never,
        updateCameraMutation: mockUpdateCameraMutation as never,
      });

      renderComponent();
      expect(screen.getByText(/failed to update.*update failed/i)).toBeInTheDocument();
    });

    it('should show loading state when creating quiet hours', async () => {
      const user = userEvent.setup();

      mockUseNotificationPreferencesMutation.mockReturnValue({
        updateGlobalMutation: mockUpdateGlobalMutation as never,
        createQuietHoursMutation: { ...mockCreateQuietHoursMutation, isPending: true } as never,
        deleteQuietHoursMutation: mockDeleteQuietHoursMutation as never,
        updateCameraMutation: mockUpdateCameraMutation as never,
      });

      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        const submitButton = screen.getByRole('button', { name: /creating/i });
        expect(submitButton).toBeInTheDocument();
        expect(submitButton).toBeDisabled();
      });
    });

    it('should display error when creating quiet hours fails', async () => {
      const user = userEvent.setup();

      mockUseNotificationPreferencesMutation.mockReturnValue({
        updateGlobalMutation: mockUpdateGlobalMutation as never,
        createQuietHoursMutation: {
          ...mockCreateQuietHoursMutation,
          error: new Error('Creation failed'),
        } as never,
        deleteQuietHoursMutation: mockDeleteQuietHoursMutation as never,
        updateCameraMutation: mockUpdateCameraMutation as never,
      });

      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByText(/failed to create.*creation failed/i)).toBeInTheDocument();
      });
    });
  });

  // ============================================================================
  // Accessibility Tests
  // ============================================================================

  describe('Accessibility', () => {
    it('should have proper aria labels on form controls', () => {
      renderComponent();

      expect(screen.getByRole('switch', { name: /enable notifications/i })).toBeInTheDocument();
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('should have proper form labels', async () => {
      const user = userEvent.setup();
      renderComponent();

      await user.click(screen.getByRole('button', { name: /add period/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/start time/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/end time/i)).toBeInTheDocument();
      });
    });

    it('should have descriptive text for form sections', () => {
      renderComponent();

      expect(
        screen.getByText(/configure how and when you receive notifications/i)
      ).toBeInTheDocument();
    });
  });
});
