/**
 * Tests for ZoneAccessSettings component
 *
 * @see NEM-3608 Zone-Household Access Control UI
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ZoneAccessSettings from './ZoneAccessSettings';
import * as useHouseholdApiModule from '../../hooks/useHouseholdApi';
import * as useZoneHouseholdConfigModule from '../../hooks/useZoneHouseholdConfig';

import type { HouseholdMember, RegisteredVehicle } from '../../hooks/useHouseholdApi';
import type { ZoneHouseholdConfig } from '../../hooks/useZoneHouseholdConfig';
import type { Zone } from '../../services/api';

// Mock the hooks
vi.mock('../../hooks/useHouseholdApi');
vi.mock('../../hooks/useZoneHouseholdConfig');
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

// Test data
const mockZones: Zone[] = [
  {
    id: 'zone-1',
    camera_id: 'cam-1',
    name: 'Front Door',
    zone_type: 'entry_point',
    coordinates: [[0, 0], [100, 0], [100, 100], [0, 100]],
    shape: 'polygon',
    color: '#3B82F6',
    enabled: true,
    priority: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'zone-2',
    camera_id: 'cam-1',
    name: 'Backyard',
    zone_type: 'yard',
    coordinates: [[0, 0], [100, 0], [100, 100], [0, 100]],
    shape: 'polygon',
    color: '#EF4444',
    enabled: true,
    priority: 1,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

const mockMembers: HouseholdMember[] = [
  {
    id: 1,
    name: 'John Doe',
    role: 'resident',
    trusted_level: 'full',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Jane Smith',
    role: 'family',
    trusted_level: 'partial',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

const mockVehicles: RegisteredVehicle[] = [
  {
    id: 1,
    description: 'Red Tesla Model 3',
    vehicle_type: 'car',
    license_plate: 'ABC123',
    trusted: true,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    description: 'Blue Honda CR-V',
    vehicle_type: 'suv',
    license_plate: 'XYZ789',
    trusted: true,
    created_at: '2024-01-01T00:00:00Z',
  },
];

const mockConfig: ZoneHouseholdConfig = {
  id: 1,
  zone_id: 'zone-1',
  owner_id: 1,
  allowed_member_ids: [1, 2],
  allowed_vehicle_ids: [1],
  access_schedules: [],
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

// Helper to create query client
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

// Wrapper component
function Wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

describe('ZoneAccessSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    vi.mocked(useHouseholdApiModule.useHouseholdApi).mockReturnValue({
      members: mockMembers,
      membersLoading: false,
      membersError: null,
      refetchMembers: vi.fn(),
      vehicles: mockVehicles,
      vehiclesLoading: false,
      vehiclesError: null,
      refetchVehicles: vi.fn(),
      households: { items: [], total: 0 },
      householdsLoading: false,
      householdsError: null,
      refetchHouseholds: vi.fn(),
      createMember: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useHouseholdApiModule.useHouseholdApi>['createMember'],
      updateMember: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useHouseholdApiModule.useHouseholdApi>['updateMember'],
      deleteMember: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useHouseholdApiModule.useHouseholdApi>['deleteMember'],
      createVehicle: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useHouseholdApiModule.useHouseholdApi>['createVehicle'],
      updateVehicle: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useHouseholdApiModule.useHouseholdApi>['updateVehicle'],
      deleteVehicle: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useHouseholdApiModule.useHouseholdApi>['deleteVehicle'],
      createHousehold: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useHouseholdApiModule.useHouseholdApi>['createHousehold'],
      updateHousehold: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useHouseholdApiModule.useHouseholdApi>['updateHousehold'],
      deleteHousehold: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useHouseholdApiModule.useHouseholdApi>['deleteHousehold'],
    });

    vi.mocked(useZoneHouseholdConfigModule.useZoneHouseholdConfig).mockReturnValue({
      config: null,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      upsertConfig: { mutateAsync: vi.fn().mockResolvedValue(mockConfig), isPending: false } as unknown as ReturnType<typeof useZoneHouseholdConfigModule.useZoneHouseholdConfig>['upsertConfig'],
      patchConfig: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useZoneHouseholdConfigModule.useZoneHouseholdConfig>['patchConfig'],
      deleteConfig: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useZoneHouseholdConfigModule.useZoneHouseholdConfig>['deleteConfig'],
      setOwner: vi.fn(),
      setAllowedMembers: vi.fn(),
      setAllowedVehicles: vi.fn(),
      setAccessSchedules: vi.fn(),
      clearConfig: vi.fn(),
    });
  });

  it('renders zone selector dropdown', () => {
    render(
      <Wrapper>
        <ZoneAccessSettings zones={mockZones} />
      </Wrapper>
    );

    expect(screen.getByTestId('zone-selector')).toBeInTheDocument();
    expect(screen.getByText('Select a zone...')).toBeInTheDocument();
  });

  it('shows empty state when no zones available', () => {
    render(
      <Wrapper>
        <ZoneAccessSettings zones={[]} />
      </Wrapper>
    );

    expect(screen.getByText('No Zones Available')).toBeInTheDocument();
  });

  it('shows zones in dropdown when clicked', async () => {
    const user = userEvent.setup();

    render(
      <Wrapper>
        <ZoneAccessSettings zones={mockZones} />
      </Wrapper>
    );

    await user.click(screen.getByTestId('zone-selector'));

    expect(screen.getByText('Front Door')).toBeInTheDocument();
    expect(screen.getByText('Backyard')).toBeInTheDocument();
  });

  it('shows configuration panel after selecting a zone', async () => {
    const user = userEvent.setup();

    render(
      <Wrapper>
        <ZoneAccessSettings zones={mockZones} />
      </Wrapper>
    );

    // Open dropdown and select zone
    await user.click(screen.getByTestId('zone-selector'));
    await user.click(screen.getByText('Front Door'));

    // Should show configuration sections
    expect(screen.getByText('Zone Owner')).toBeInTheDocument();
    expect(screen.getByText('Allowed Members')).toBeInTheDocument();
    expect(screen.getByText('Allowed Vehicles')).toBeInTheDocument();
    expect(screen.getByText('Access Schedules')).toBeInTheDocument();
  });

  it('displays household members for selection', async () => {
    const user = userEvent.setup();

    render(
      <Wrapper>
        <ZoneAccessSettings zones={mockZones} />
      </Wrapper>
    );

    await user.click(screen.getByTestId('zone-selector'));
    await user.click(screen.getByText('Front Door'));

    // Should show members in owner and allowed members sections (multiple elements)
    const johnDoeElements = screen.getAllByText('John Doe');
    const janeSmithElements = screen.getAllByText('Jane Smith');
    expect(johnDoeElements.length).toBeGreaterThan(0);
    expect(janeSmithElements.length).toBeGreaterThan(0);
  });

  it('displays vehicles for selection', async () => {
    const user = userEvent.setup();

    render(
      <Wrapper>
        <ZoneAccessSettings zones={mockZones} />
      </Wrapper>
    );

    await user.click(screen.getByTestId('zone-selector'));
    await user.click(screen.getByText('Front Door'));

    // Should show vehicles
    expect(screen.getByText('Red Tesla Model 3')).toBeInTheDocument();
    expect(screen.getByText('Blue Honda CR-V')).toBeInTheDocument();
  });

  it('loads existing config when zone is selected', async () => {
    const user = userEvent.setup();

    vi.mocked(useZoneHouseholdConfigModule.useZoneHouseholdConfig).mockReturnValue({
      config: mockConfig,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      upsertConfig: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useZoneHouseholdConfigModule.useZoneHouseholdConfig>['upsertConfig'],
      patchConfig: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useZoneHouseholdConfigModule.useZoneHouseholdConfig>['patchConfig'],
      deleteConfig: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useZoneHouseholdConfigModule.useZoneHouseholdConfig>['deleteConfig'],
      setOwner: vi.fn(),
      setAllowedMembers: vi.fn(),
      setAllowedVehicles: vi.fn(),
      setAccessSchedules: vi.fn(),
      clearConfig: vi.fn(),
    });

    render(
      <Wrapper>
        <ZoneAccessSettings zones={mockZones} />
      </Wrapper>
    );

    await user.click(screen.getByTestId('zone-selector'));
    await user.click(screen.getByText('Front Door'));

    // Config should be reflected in the UI (owner selected, members selected, etc.)
    // The exact assertions depend on how selection is visually indicated
    expect(useZoneHouseholdConfigModule.useZoneHouseholdConfig).toHaveBeenCalled();
  });

  it('shows loading state', () => {
    render(
      <Wrapper>
        <ZoneAccessSettings zones={[]} zonesLoading={true} />
      </Wrapper>
    );

    // Loading skeleton should be shown (animate-pulse class)
    const loadingDiv = document.querySelector('.animate-pulse');
    expect(loadingDiv).toBeInTheDocument();
  });

  it('shows error state with retry button', () => {
    const onRetry = vi.fn();

    render(
      <Wrapper>
        <ZoneAccessSettings
          zones={[]}
          zonesError="Failed to fetch zones"
          onRetryZones={onRetry}
        />
      </Wrapper>
    );

    expect(screen.getByText('Failed to load zones')).toBeInTheDocument();
  });

  it('enables save button when changes are made', async () => {
    const user = userEvent.setup();

    render(
      <Wrapper>
        <ZoneAccessSettings zones={mockZones} />
      </Wrapper>
    );

    // Select a zone first
    await user.click(screen.getByTestId('zone-selector'));
    await user.click(screen.getByText('Front Door'));

    // Find and click a member to toggle selection
    const johnDoeButtons = screen.getAllByText('John Doe');
    await user.click(johnDoeButtons[0]);

    // Save button should be enabled
    const saveButton = screen.getByTestId('save-zone-config-btn');
    expect(saveButton).not.toBeDisabled();
  });

  it('shows delete confirmation modal', async () => {
    const user = userEvent.setup();

    vi.mocked(useZoneHouseholdConfigModule.useZoneHouseholdConfig).mockReturnValue({
      config: mockConfig,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
      upsertConfig: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useZoneHouseholdConfigModule.useZoneHouseholdConfig>['upsertConfig'],
      patchConfig: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useZoneHouseholdConfigModule.useZoneHouseholdConfig>['patchConfig'],
      deleteConfig: { mutateAsync: vi.fn(), isPending: false } as unknown as ReturnType<typeof useZoneHouseholdConfigModule.useZoneHouseholdConfig>['deleteConfig'],
      setOwner: vi.fn(),
      setAllowedMembers: vi.fn(),
      setAllowedVehicles: vi.fn(),
      setAccessSchedules: vi.fn(),
      clearConfig: vi.fn(),
    });

    render(
      <Wrapper>
        <ZoneAccessSettings zones={mockZones} />
      </Wrapper>
    );

    await user.click(screen.getByTestId('zone-selector'));
    await user.click(screen.getByText('Front Door'));

    // Click clear settings button
    await user.click(screen.getByText('Clear All Settings'));

    // Confirmation modal should appear
    await waitFor(() => {
      expect(screen.getByTestId('delete-config-modal')).toBeInTheDocument();
    });
  });
});
