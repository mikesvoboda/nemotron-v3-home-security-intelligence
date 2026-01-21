/**
 * ZoneOwnershipPanel component tests
 *
 * Tests for the zone ownership panel component that displays and allows
 * editing of zone access control configuration.
 *
 * @see NEM-3191
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ZoneOwnershipPanel from './ZoneOwnershipPanel';

import type { HouseholdMember, RegisteredVehicle } from '../../hooks/useHouseholdApi';
import type { ZoneHouseholdConfig } from '../../hooks/useZoneHouseholdConfig';

// ============================================================================
// Test Data
// ============================================================================

const mockZoneId = 'zone-test-123';
const mockZoneName = 'Front Door';

const mockMembers: HouseholdMember[] = [
  {
    id: 1,
    name: 'John Doe',
    role: 'resident',
    trusted_level: 'full',
    notes: null,
    typical_schedule: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Jane Smith',
    role: 'family',
    trusted_level: 'partial',
    notes: null,
    typical_schedule: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 3,
    name: 'Bob Wilson',
    role: 'service_worker',
    trusted_level: 'monitor',
    notes: null,
    typical_schedule: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const mockVehicles: RegisteredVehicle[] = [
  {
    id: 1,
    description: 'Silver Tesla Model 3',
    vehicle_type: 'car',
    license_plate: 'ABC 123',
    color: 'Silver',
    owner_id: 1,
    trusted: true,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    description: 'Black Honda Civic',
    vehicle_type: 'car',
    license_plate: 'XYZ 789',
    color: 'Black',
    owner_id: 2,
    trusted: false,
    created_at: '2026-01-01T00:00:00Z',
  },
];

const mockConfig: ZoneHouseholdConfig = {
  id: 1,
  zone_id: mockZoneId,
  owner_id: 1,
  allowed_member_ids: [2],
  allowed_vehicle_ids: [1],
  access_schedules: [
    {
      member_ids: [3],
      cron_expression: '0 9-17 * * 1-5',
      description: 'Weekday business hours',
    },
  ],
  created_at: '2026-01-21T10:00:00Z',
  updated_at: '2026-01-21T12:00:00Z',
};

// ============================================================================
// Mock Setup
// ============================================================================

// Mock useToast
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

// Mock useZoneHouseholdConfig hook
const mockUpsertConfig = {
  mutateAsync: vi.fn(),
  isPending: false,
};
const mockPatchConfig = {
  mutateAsync: vi.fn(),
  isPending: false,
};
const mockDeleteConfig = {
  mutateAsync: vi.fn(),
  isPending: false,
};

const mockUseZoneHouseholdConfig = vi.fn(() => ({
  config: mockConfig as ZoneHouseholdConfig | null,
  isLoading: false,
  isError: false,
  error: null as Error | null,
  refetch: vi.fn(),
  upsertConfig: mockUpsertConfig,
  patchConfig: mockPatchConfig,
  deleteConfig: mockDeleteConfig,
  setOwner: vi.fn(),
  setAllowedMembers: vi.fn(),
  setAllowedVehicles: vi.fn(),
  setAccessSchedules: vi.fn(),
  clearConfig: vi.fn(),
}));

vi.mock('../../hooks/useZoneHouseholdConfig', () => ({
  useZoneHouseholdConfig: () => mockUseZoneHouseholdConfig(),
}));

// Mock useHouseholdApi hooks
const mockUseMembersQuery = vi.fn(() => ({
  data: mockMembers,
  isLoading: false,
}));

const mockUseVehiclesQuery = vi.fn(() => ({
  data: mockVehicles,
  isLoading: false,
}));

vi.mock('../../hooks/useHouseholdApi', () => ({
  useMembersQuery: () => mockUseMembersQuery(),
  useVehiclesQuery: () => mockUseVehiclesQuery(),
}));

// ============================================================================
// Render Helper
// ============================================================================

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function renderPanel(props: Partial<React.ComponentProps<typeof ZoneOwnershipPanel>> = {}) {
  const user = userEvent.setup();
  const result = render(
    <ZoneOwnershipPanel zoneId={mockZoneId} zoneName={mockZoneName} {...props} />,
    { wrapper: createWrapper() }
  );
  return { ...result, user };
}

// ============================================================================
// Tests
// ============================================================================

describe('ZoneOwnershipPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset default mock return values
    mockUseZoneHouseholdConfig.mockReturnValue({
      config: mockConfig,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      upsertConfig: mockUpsertConfig,
      patchConfig: mockPatchConfig,
      deleteConfig: mockDeleteConfig,
      setOwner: vi.fn(),
      setAllowedMembers: vi.fn(),
      setAllowedVehicles: vi.fn(),
      setAccessSchedules: vi.fn(),
      clearConfig: vi.fn(),
    });
    mockUseMembersQuery.mockReturnValue({
      data: mockMembers,
      isLoading: false,
    });
    mockUseVehiclesQuery.mockReturnValue({
      data: mockVehicles,
      isLoading: false,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Loading State', () => {
    it('should show loading skeleton while fetching config', () => {
      mockUseZoneHouseholdConfig.mockReturnValue({
        config: null,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
        upsertConfig: mockUpsertConfig,
        patchConfig: mockPatchConfig,
        deleteConfig: mockDeleteConfig,
        setOwner: vi.fn(),
        setAllowedMembers: vi.fn(),
        setAllowedVehicles: vi.fn(),
        setAccessSchedules: vi.fn(),
        clearConfig: vi.fn(),
      });

      renderPanel();

      expect(screen.getByTestId('zone-ownership-panel')).toBeInTheDocument();
      expect(screen.getByTestId('zone-ownership-panel').innerHTML).toContain('animate-pulse');
    });

    it('should show loading skeleton while fetching members', () => {
      mockUseMembersQuery.mockReturnValue({
        data: [],
        isLoading: true,
      });

      renderPanel();

      expect(screen.getByTestId('zone-ownership-panel').innerHTML).toContain('animate-pulse');
    });

    it('should show loading skeleton while fetching vehicles', () => {
      mockUseVehiclesQuery.mockReturnValue({
        data: [],
        isLoading: true,
      });

      renderPanel();

      expect(screen.getByTestId('zone-ownership-panel').innerHTML).toContain('animate-pulse');
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no config exists', () => {
      mockUseZoneHouseholdConfig.mockReturnValue({
        config: null,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
        upsertConfig: mockUpsertConfig,
        patchConfig: mockPatchConfig,
        deleteConfig: mockDeleteConfig,
        setOwner: vi.fn(),
        setAllowedMembers: vi.fn(),
        setAllowedVehicles: vi.fn(),
        setAccessSchedules: vi.fn(),
        clearConfig: vi.fn(),
      });

      renderPanel();

      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText('No ownership configured')).toBeInTheDocument();
    });

    it('should show configure button in empty state when editable', () => {
      mockUseZoneHouseholdConfig.mockReturnValue({
        config: null,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
        upsertConfig: mockUpsertConfig,
        patchConfig: mockPatchConfig,
        deleteConfig: mockDeleteConfig,
        setOwner: vi.fn(),
        setAllowedMembers: vi.fn(),
        setAllowedVehicles: vi.fn(),
        setAccessSchedules: vi.fn(),
        clearConfig: vi.fn(),
      });

      renderPanel({ editable: true });

      expect(screen.getByTestId('configure-btn')).toBeInTheDocument();
    });

    it('should not show configure button in empty state when not editable', () => {
      mockUseZoneHouseholdConfig.mockReturnValue({
        config: null,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
        upsertConfig: mockUpsertConfig,
        patchConfig: mockPatchConfig,
        deleteConfig: mockDeleteConfig,
        setOwner: vi.fn(),
        setAllowedMembers: vi.fn(),
        setAllowedVehicles: vi.fn(),
        setAccessSchedules: vi.fn(),
        clearConfig: vi.fn(),
      });

      renderPanel({ editable: false });

      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.queryByTestId('configure-btn')).not.toBeInTheDocument();
    });
  });

  describe('Display Mode', () => {
    it('should display zone name in header', () => {
      renderPanel();

      expect(screen.getByText('Front Door Access')).toBeInTheDocument();
    });

    it('should display owner with crown icon', () => {
      renderPanel();

      // Owner badge appears on the member card in non-compact mode
      expect(screen.getAllByText('Owner').length).toBeGreaterThan(0);
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByTestId('member-1')).toBeInTheDocument();
    });

    it('should display allowed members', () => {
      renderPanel();

      expect(screen.getByText('Allowed Members')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      expect(screen.getByTestId('member-2')).toBeInTheDocument();
    });

    it('should display allowed vehicles', () => {
      renderPanel();

      expect(screen.getByText('Allowed Vehicles')).toBeInTheDocument();
      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
      expect(screen.getByTestId('vehicle-1')).toBeInTheDocument();
    });

    it('should display access schedules', () => {
      renderPanel();

      expect(screen.getByText('Access Schedules')).toBeInTheDocument();
      expect(screen.getByText('Weekday business hours')).toBeInTheDocument();
      expect(screen.getByText('0 9-17 * * 1-5')).toBeInTheDocument();
      expect(screen.getByTestId('schedule-card')).toBeInTheDocument();
    });

    it('should display member badges in schedules', () => {
      renderPanel();

      const scheduleCard = screen.getByTestId('schedule-card');
      expect(scheduleCard).toHaveTextContent('Bob Wilson');
    });

    it('should show "No owner assigned" when owner_id is null', () => {
      mockUseZoneHouseholdConfig.mockReturnValue({
        config: { ...mockConfig, owner_id: null },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
        upsertConfig: mockUpsertConfig,
        patchConfig: mockPatchConfig,
        deleteConfig: mockDeleteConfig,
        setOwner: vi.fn(),
        setAllowedMembers: vi.fn(),
        setAllowedVehicles: vi.fn(),
        setAccessSchedules: vi.fn(),
        clearConfig: vi.fn(),
      });

      renderPanel();

      expect(screen.getByText('No owner assigned')).toBeInTheDocument();
    });

    it('should show "No additional members allowed" when allowed_member_ids is empty', () => {
      mockUseZoneHouseholdConfig.mockReturnValue({
        config: { ...mockConfig, allowed_member_ids: [] },
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
        upsertConfig: mockUpsertConfig,
        patchConfig: mockPatchConfig,
        deleteConfig: mockDeleteConfig,
        setOwner: vi.fn(),
        setAllowedMembers: vi.fn(),
        setAllowedVehicles: vi.fn(),
        setAccessSchedules: vi.fn(),
        clearConfig: vi.fn(),
      });

      renderPanel({ editable: true });

      expect(screen.getByText('No additional members allowed')).toBeInTheDocument();
    });
  });

  describe('Compact Mode', () => {
    it('should render in compact mode', () => {
      renderPanel({ compact: true });

      expect(screen.getByText('John Doe')).toBeInTheDocument();
      // Owner section label should still be present
      expect(screen.getAllByText('Owner').length).toBeGreaterThan(0);
    });
  });

  describe('Edit Mode', () => {
    it('should show edit button when editable', () => {
      renderPanel({ editable: true });

      expect(screen.getByTestId('edit-config-btn')).toBeInTheDocument();
    });

    it('should not show edit button when not editable', () => {
      renderPanel({ editable: false });

      expect(screen.queryByTestId('edit-config-btn')).not.toBeInTheDocument();
    });

    it('should show remove buttons on members when editable', () => {
      renderPanel({ editable: true });

      expect(screen.getByTestId('remove-member-2')).toBeInTheDocument();
    });

    it('should show add schedule button when editable', () => {
      renderPanel({ editable: true });

      expect(screen.getByTestId('add-schedule-btn')).toBeInTheDocument();
    });

    it('should open configure modal when edit button clicked', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('edit-config-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('configure-modal')).toBeInTheDocument();
      });

      expect(screen.getByText('Configure Zone Access')).toBeInTheDocument();
    });

    it('should open schedule modal when add schedule clicked', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('add-schedule-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('schedule-modal')).toBeInTheDocument();
      });

      expect(screen.getByText('Add Schedule')).toBeInTheDocument();
    });
  });

  describe('Configure Modal', () => {
    it('should display owner selection', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('edit-config-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('owner-select')).toBeInTheDocument();
      });

      expect(screen.getByText('Zone Owner')).toBeInTheDocument();
    });

    it('should display member checkboxes', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('edit-config-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('member-checkbox-1')).toBeInTheDocument();
        expect(screen.getByTestId('member-checkbox-2')).toBeInTheDocument();
        expect(screen.getByTestId('member-checkbox-3')).toBeInTheDocument();
      });
    });

    it('should display vehicle checkboxes', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('edit-config-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('vehicle-checkbox-1')).toBeInTheDocument();
        expect(screen.getByTestId('vehicle-checkbox-2')).toBeInTheDocument();
      });
    });

    it('should show delete button when config exists', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('edit-config-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('delete-config-btn')).toBeInTheDocument();
      });
    });

    it('should close modal when cancel clicked', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('edit-config-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('configure-modal')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Cancel'));

      await waitFor(() => {
        expect(screen.queryByTestId('configure-modal')).not.toBeInTheDocument();
      });
    });
  });

  describe('Schedule Modal', () => {
    it('should display schedule form fields', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('add-schedule-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('schedule-description-input')).toBeInTheDocument();
        expect(screen.getByTestId('schedule-cron-input')).toBeInTheDocument();
      });
    });

    it('should display common schedule presets', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('add-schedule-btn'));

      await waitFor(() => {
        expect(screen.getByText('Weekdays 9am-5pm')).toBeInTheDocument();
        expect(screen.getByText('Weekends all day')).toBeInTheDocument();
      });
    });

    it('should populate cron field when preset clicked', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('add-schedule-btn'));

      await waitFor(() => {
        expect(screen.getByText('Weekdays 9am-5pm')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Weekdays 9am-5pm'));

      const cronInput = screen.getByTestId<HTMLInputElement>('schedule-cron-input');
      expect(cronInput.value).toBe('0 9-17 * * 1-5');
    });

    it('should display member checkboxes for schedule', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('add-schedule-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('schedule-member-checkbox-1')).toBeInTheDocument();
        expect(screen.getByTestId('schedule-member-checkbox-2')).toBeInTheDocument();
        expect(screen.getByTestId('schedule-member-checkbox-3')).toBeInTheDocument();
      });
    });

    it('should disable save when no members or cron selected', async () => {
      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('add-schedule-btn'));

      await waitFor(() => {
        const saveBtn = screen.getByTestId('save-schedule-btn');
        expect(saveBtn).toBeDisabled();
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error state on fetch failure', () => {
      mockUseZoneHouseholdConfig.mockReturnValue({
        config: null,
        isLoading: false,
        isError: true,
        error: new Error('Server error'),
        refetch: vi.fn(),
        upsertConfig: mockUpsertConfig,
        patchConfig: mockPatchConfig,
        deleteConfig: mockDeleteConfig,
        setOwner: vi.fn(),
        setAllowedMembers: vi.fn(),
        setAllowedVehicles: vi.fn(),
        setAccessSchedules: vi.fn(),
        clearConfig: vi.fn(),
      });

      renderPanel();

      // Error state shows the error message from the error object
      expect(screen.getByText('Server error')).toBeInTheDocument();
    });

    it('should show retry button on error', () => {
      mockUseZoneHouseholdConfig.mockReturnValue({
        config: null,
        isLoading: false,
        isError: true,
        error: new Error('Server error'),
        refetch: vi.fn(),
        upsertConfig: mockUpsertConfig,
        patchConfig: mockPatchConfig,
        deleteConfig: mockDeleteConfig,
        setOwner: vi.fn(),
        setAllowedMembers: vi.fn(),
        setAllowedVehicles: vi.fn(),
        setAccessSchedules: vi.fn(),
        clearConfig: vi.fn(),
      });

      renderPanel();

      expect(screen.getByText('Retry')).toBeInTheDocument();
    });
  });

  describe('Integration', () => {
    it('should handle empty members list', async () => {
      mockUseMembersQuery.mockReturnValue({
        data: [],
        isLoading: false,
      });

      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('edit-config-btn'));

      await waitFor(() => {
        expect(screen.getByText('No household members available')).toBeInTheDocument();
      });
    });

    it('should handle empty vehicles list', async () => {
      mockUseVehiclesQuery.mockReturnValue({
        data: [],
        isLoading: false,
      });

      const { user } = renderPanel({ editable: true });

      await user.click(screen.getByTestId('edit-config-btn'));

      await waitFor(() => {
        expect(screen.getByText('No registered vehicles available')).toBeInTheDocument();
      });
    });

    it('should handle default zoneName when not provided', () => {
      render(<ZoneOwnershipPanel zoneId={mockZoneId} />, { wrapper: createWrapper() });

      expect(screen.getByText('Zone Access')).toBeInTheDocument();
    });
  });
});
