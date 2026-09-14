/**
 * Tests for HouseholdSettings component
 *
 * Phase 7.1: Create HouseholdSettings component (NEM-3134)
 * Part of the Orphaned Infrastructure Integration epic (NEM-3113).
 */

import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import HouseholdSettings from './HouseholdSettings';
import { renderWithProviders } from '../../test-utils';

import type {
  HouseholdMember,
  RegisteredVehicle,
  Household,
  HouseholdListResponse,
} from '../../hooks/useHouseholdApi';

// Mock data
const mockMembers: HouseholdMember[] = [
  {
    id: 1,
    name: 'John Doe',
    role: 'resident',
    trusted_level: 'full',
    notes: 'Test notes',
    typical_schedule: null,
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-01T12:00:00Z',
  },
  {
    id: 2,
    name: 'Jane Doe',
    role: 'family',
    trusted_level: 'partial',
    notes: null,
    typical_schedule: null,
    created_at: '2026-01-02T10:00:00Z',
    updated_at: '2026-01-02T12:00:00Z',
  },
];

const mockVehicles: RegisteredVehicle[] = [
  {
    id: 1,
    description: 'Silver Tesla Model 3',
    vehicle_type: 'car',
    license_plate: 'ABC123',
    color: 'Silver',
    owner_id: 1,
    trusted: true,
    created_at: '2026-01-01T10:00:00Z',
  },
  {
    id: 2,
    description: 'Blue Honda Civic',
    vehicle_type: 'car',
    license_plate: 'XYZ789',
    color: 'Blue',
    owner_id: null,
    trusted: false,
    created_at: '2026-01-02T10:00:00Z',
  },
];

const mockHousehold: Household = {
  id: 1,
  name: 'Svoboda Family',
  created_at: '2026-01-01T10:00:00Z',
};

const mockHouseholdList: HouseholdListResponse = {
  items: [mockHousehold],
  total: 1,
};

// Mock variables for controlling hook behavior
let mockMembersData: HouseholdMember[] | undefined = mockMembers;
let mockMembersLoading = false;
let mockMembersError: Error | null = null;
let mockVehiclesData: RegisteredVehicle[] | undefined = mockVehicles;
let mockVehiclesLoading = false;
let mockVehiclesError: Error | null = null;
let mockHouseholdsData: HouseholdListResponse | undefined = mockHouseholdList;
let mockHouseholdsLoading = false;

const mockCreateMember = vi.fn();
const mockUpdateMember = vi.fn();
const mockDeleteMember = vi.fn();
const mockCreateVehicle = vi.fn();
const mockUpdateVehicle = vi.fn();
const mockDeleteVehicle = vi.fn();
const mockUpdateHousehold = vi.fn();

// Mock the useHouseholdApi hook
vi.mock('../../hooks/useHouseholdApi', () => ({
  useHouseholdApi: () => ({
    members: mockMembersData,
    membersLoading: mockMembersLoading,
    membersError: mockMembersError,
    createMember: { mutateAsync: mockCreateMember, isPending: false },
    updateMember: { mutateAsync: mockUpdateMember, isPending: false },
    deleteMember: { mutateAsync: mockDeleteMember, isPending: false },
    vehicles: mockVehiclesData,
    vehiclesLoading: mockVehiclesLoading,
    vehiclesError: mockVehiclesError,
    createVehicle: { mutateAsync: mockCreateVehicle, isPending: false },
    updateVehicle: { mutateAsync: mockUpdateVehicle, isPending: false },
    deleteVehicle: { mutateAsync: mockDeleteVehicle, isPending: false },
    households: mockHouseholdsData,
    householdsLoading: mockHouseholdsLoading,
    householdsError: null,
    createHousehold: { mutateAsync: vi.fn(), isPending: false },
    updateHousehold: { mutateAsync: mockUpdateHousehold, isPending: false },
    deleteHousehold: { mutateAsync: vi.fn(), isPending: false },
  }),
}));

// Mock useToast hook
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

// Mock react-router-dom Link
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    Link: ({
      children,
      to,
      ...props
    }: {
      children: React.ReactNode;
      to: string;
      [key: string]: unknown;
    }) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
  };
});

describe('HouseholdSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock data to defaults
    mockMembersData = mockMembers;
    mockMembersLoading = false;
    mockMembersError = null;
    mockVehiclesData = mockVehicles;
    mockVehiclesLoading = false;
    mockVehiclesError = null;
    mockHouseholdsData = mockHouseholdList;
    mockHouseholdsLoading = false;
  });

  describe('rendering', () => {
    it('renders the household settings component', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('household-settings')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      renderWithProviders(<HouseholdSettings className="custom-class" />);

      const container = screen.getByTestId('household-settings');
      expect(container).toHaveClass('custom-class');
    });

    it('renders all main sections', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('household-name-section')).toBeInTheDocument();
      expect(screen.getByTestId('members-section')).toBeInTheDocument();
      expect(screen.getByTestId('vehicles-section')).toBeInTheDocument();
      expect(screen.getByTestId('properties-section')).toBeInTheDocument();
    });
  });

  describe('Household Name section', () => {
    it('displays the household name', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByText('Svoboda Family')).toBeInTheDocument();
    });

    it('shows edit button for household name', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('household-name-edit')).toBeInTheDocument();
    });

    it('enters edit mode when edit button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('household-name-edit'));

      expect(screen.getByTestId('household-name-input')).toBeInTheDocument();
      expect(screen.getByTestId('household-name-save')).toBeInTheDocument();
      expect(screen.getByTestId('household-name-cancel')).toBeInTheDocument();
    });

    it('cancels edit mode when cancel is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('household-name-edit'));
      await user.click(screen.getByTestId('household-name-cancel'));

      expect(screen.queryByTestId('household-name-input')).not.toBeInTheDocument();
      expect(screen.getByText('Svoboda Family')).toBeInTheDocument();
    });

    it('saves household name when save is clicked', async () => {
      const user = userEvent.setup();
      mockUpdateHousehold.mockResolvedValue(mockHousehold);
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('household-name-edit'));
      const input = screen.getByTestId('household-name-input');
      await user.clear(input);
      await user.type(input, 'New Family Name');
      await user.click(screen.getByTestId('household-name-save'));

      await waitFor(() => {
        expect(mockUpdateHousehold).toHaveBeenCalledWith({
          id: 1,
          data: { name: 'New Family Name' },
        });
      });
    });
  });

  describe('Members section', () => {
    it('renders members list', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('members-list')).toBeInTheDocument();
      expect(screen.getByTestId('member-1')).toBeInTheDocument();
      expect(screen.getByTestId('member-2')).toBeInTheDocument();
    });

    it('displays member names and badges', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
      expect(screen.getByText('Full Trust')).toBeInTheDocument();
      expect(screen.getByText('Partial')).toBeInTheDocument();
    });

    it('shows add member button', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('add-member-btn')).toBeInTheDocument();
    });

    it('shows edit and delete buttons for each member', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('edit-member-1')).toBeInTheDocument();
      expect(screen.getByTestId('delete-member-1')).toBeInTheDocument();
      expect(screen.getByTestId('edit-member-2')).toBeInTheDocument();
      expect(screen.getByTestId('delete-member-2')).toBeInTheDocument();
    });

    it('shows loading state when members are loading', () => {
      mockMembersLoading = true;
      mockMembersData = undefined;
      renderWithProviders(<HouseholdSettings />);

      const membersSection = screen.getByTestId('members-section');
      expect(membersSection).toBeInTheDocument();
      // Should show skeleton loading
      expect(screen.queryByTestId('members-list')).not.toBeInTheDocument();
    });

    it('shows error state when members fail to load', () => {
      mockMembersError = new Error('Failed to load');
      mockMembersData = undefined;
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByText('Failed to load members')).toBeInTheDocument();
    });

    it('shows empty state when no members exist', () => {
      mockMembersData = [];
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByText('No members yet')).toBeInTheDocument();
    });

    it('opens add member modal when add button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-member-btn'));

      expect(screen.getByTestId('member-modal')).toBeInTheDocument();
      expect(screen.getByText('Add Member')).toBeInTheDocument();
    });

    it('opens edit member modal when edit button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('edit-member-1'));

      expect(screen.getByTestId('member-modal')).toBeInTheDocument();
      expect(screen.getByText('Edit Member')).toBeInTheDocument();
      // Should be pre-populated with member data
      expect(screen.getByTestId('member-name-input')).toHaveValue('John Doe');
    });

    it('creates member when form is submitted', async () => {
      const user = userEvent.setup();
      mockCreateMember.mockResolvedValue(mockMembers[0]);
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-member-btn'));
      await user.type(screen.getByTestId('member-name-input'), 'New Member');
      await user.click(screen.getByTestId('member-modal-save'));

      await waitFor(() => {
        expect(mockCreateMember).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'New Member',
            role: 'resident',
            trusted_level: 'full',
          })
        );
      });
    });

    it('shows delete confirmation modal when delete is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('delete-member-1'));

      expect(screen.getByTestId('delete-member-modal')).toBeInTheDocument();
      expect(screen.getByText('Delete Member')).toBeInTheDocument();
    });

    it('deletes member when confirmed', async () => {
      const user = userEvent.setup();
      mockDeleteMember.mockResolvedValue(undefined);
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('delete-member-1'));
      await user.click(screen.getByTestId('confirm-delete-member'));

      await waitFor(() => {
        expect(mockDeleteMember).toHaveBeenCalledWith(1);
      });
    });
  });

  describe('Vehicles section', () => {
    it('renders vehicles list', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('vehicles-list')).toBeInTheDocument();
      expect(screen.getByTestId('vehicle-1')).toBeInTheDocument();
      expect(screen.getByTestId('vehicle-2')).toBeInTheDocument();
    });

    it('displays vehicle descriptions and badges', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
      expect(screen.getByText('Blue Honda Civic')).toBeInTheDocument();
      expect(screen.getByText('ABC123')).toBeInTheDocument();
      expect(screen.getByText('Trusted')).toBeInTheDocument();
    });

    it('shows add vehicle button', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('add-vehicle-btn')).toBeInTheDocument();
    });

    it('shows edit and delete buttons for each vehicle', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('edit-vehicle-1')).toBeInTheDocument();
      expect(screen.getByTestId('delete-vehicle-1')).toBeInTheDocument();
      expect(screen.getByTestId('edit-vehicle-2')).toBeInTheDocument();
      expect(screen.getByTestId('delete-vehicle-2')).toBeInTheDocument();
    });

    it('shows loading state when vehicles are loading', () => {
      mockVehiclesLoading = true;
      mockVehiclesData = undefined;
      renderWithProviders(<HouseholdSettings />);

      const vehiclesSection = screen.getByTestId('vehicles-section');
      expect(vehiclesSection).toBeInTheDocument();
      expect(screen.queryByTestId('vehicles-list')).not.toBeInTheDocument();
    });

    it('shows error state when vehicles fail to load', () => {
      mockVehiclesError = new Error('Failed to load');
      mockVehiclesData = undefined;
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByText('Failed to load vehicles')).toBeInTheDocument();
    });

    it('shows empty state when no vehicles exist', () => {
      mockVehiclesData = [];
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByText('No vehicles yet')).toBeInTheDocument();
    });

    it('opens add vehicle modal when add button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-vehicle-btn'));

      expect(screen.getByTestId('vehicle-modal')).toBeInTheDocument();
      expect(screen.getByText('Add Vehicle')).toBeInTheDocument();
    });

    it('opens edit vehicle modal when edit button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('edit-vehicle-1'));

      expect(screen.getByTestId('vehicle-modal')).toBeInTheDocument();
      expect(screen.getByText('Edit Vehicle')).toBeInTheDocument();
      expect(screen.getByTestId('vehicle-description-input')).toHaveValue('Silver Tesla Model 3');
    });

    it('creates vehicle when form is submitted', async () => {
      const user = userEvent.setup();
      mockCreateVehicle.mockResolvedValue(mockVehicles[0]);
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-vehicle-btn'));
      await user.type(screen.getByTestId('vehicle-description-input'), 'New Vehicle');
      await user.click(screen.getByTestId('vehicle-modal-save'));

      await waitFor(() => {
        expect(mockCreateVehicle).toHaveBeenCalledWith(
          expect.objectContaining({
            description: 'New Vehicle',
            vehicle_type: 'car',
            trusted: true,
          })
        );
      });
    });

    it('shows delete confirmation modal when delete is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('delete-vehicle-1'));

      expect(screen.getByTestId('delete-vehicle-modal')).toBeInTheDocument();
      expect(screen.getByText('Delete Vehicle')).toBeInTheDocument();
    });

    it('deletes vehicle when confirmed', async () => {
      const user = userEvent.setup();
      mockDeleteVehicle.mockResolvedValue(undefined);
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('delete-vehicle-1'));
      await user.click(screen.getByTestId('confirm-delete-vehicle'));

      await waitFor(() => {
        expect(mockDeleteVehicle).toHaveBeenCalledWith(1);
      });
    });
  });

  describe('Properties section', () => {
    it('renders properties section with manage link', () => {
      renderWithProviders(<HouseholdSettings />);

      expect(screen.getByTestId('properties-section')).toBeInTheDocument();
      expect(screen.getByTestId('manage-properties-link')).toBeInTheDocument();
      expect(screen.getByText('Manage')).toBeInTheDocument();
    });

    it('links to the properties management page', () => {
      renderWithProviders(<HouseholdSettings />);

      const link = screen.getByTestId('manage-properties-link');
      expect(link).toHaveAttribute('href', '/settings/properties');
    });
  });

  describe('Modal interactions', () => {
    it('closes member modal when cancel is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-member-btn'));
      expect(screen.getByTestId('member-modal')).toBeInTheDocument();

      await user.click(screen.getByTestId('member-modal-cancel'));

      await waitFor(() => {
        expect(screen.queryByTestId('member-modal')).not.toBeInTheDocument();
      });
    });

    it('closes vehicle modal when cancel is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-vehicle-btn'));
      expect(screen.getByTestId('vehicle-modal')).toBeInTheDocument();

      await user.click(screen.getByTestId('vehicle-modal-cancel'));

      await waitFor(() => {
        expect(screen.queryByTestId('vehicle-modal')).not.toBeInTheDocument();
      });
    });

    it('clears form data when opening modal for new member', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      // First, open edit modal to populate form
      await user.click(screen.getByTestId('edit-member-1'));
      expect(screen.getByTestId('member-name-input')).toHaveValue('John Doe');
      await user.click(screen.getByTestId('member-modal-cancel'));

      // Then open add modal - form should be cleared
      await waitFor(() => {
        expect(screen.queryByTestId('member-modal')).not.toBeInTheDocument();
      });
      await user.click(screen.getByTestId('add-member-btn'));
      expect(screen.getByTestId('member-name-input')).toHaveValue('');
    });
  });

  describe('Member form validation', () => {
    it('requires name field for members', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-member-btn'));
      // Try to save without entering name
      await user.click(screen.getByTestId('member-modal-save'));

      // Should not call create mutation
      expect(mockCreateMember).not.toHaveBeenCalled();
    });
  });

  describe('Vehicle form validation', () => {
    it('requires description field for vehicles', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-vehicle-btn'));
      // Try to save without entering description
      await user.click(screen.getByTestId('vehicle-modal-save'));

      // Should not call create mutation
      expect(mockCreateVehicle).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has accessible modal dialogs', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-member-btn'));

      // Dialog.Panel is rendered with role="dialog" on the outer Dialog element
      // or the Panel has a specific class; check the panel exists and is visible
      const modal = screen.getByTestId('member-modal');
      expect(modal).toBeInTheDocument();
      expect(modal).toBeVisible();
    });

    it('has form inputs in member modal', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-member-btn'));

      // Check that input fields exist with proper test IDs
      expect(screen.getByTestId('member-name-input')).toBeInTheDocument();
      expect(screen.getByTestId('member-role-select')).toBeInTheDocument();
      expect(screen.getByTestId('member-trust-select')).toBeInTheDocument();
    });

    it('has form inputs in vehicle modal', async () => {
      const user = userEvent.setup();
      renderWithProviders(<HouseholdSettings />);

      await user.click(screen.getByTestId('add-vehicle-btn'));

      // Check that input fields exist with proper test IDs
      expect(screen.getByTestId('vehicle-description-input')).toBeInTheDocument();
      expect(screen.getByTestId('vehicle-type-select')).toBeInTheDocument();
    });
  });
});
