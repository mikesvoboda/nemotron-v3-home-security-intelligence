/**
 * Tests for PropertyManagement component.
 *
 * @see NEM-3135 - Phase 7.2: Create PropertyManagement component
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PropertyManagement from './PropertyManagement';
import * as propertyHooks from '../../hooks/usePropertyQueries';

import type {
  PropertyResponse,
  AreaResponse,
  UsePropertyMutationsReturn,
  UseAreaMutationsReturn,
} from '../../hooks/usePropertyQueries';

// =============================================================================
// Mocks
// =============================================================================

vi.mock('../../hooks/usePropertyQueries', () => ({
  usePropertiesQuery: vi.fn(),
  useAreasQuery: vi.fn(),
  useAreaCamerasQuery: vi.fn(),
  usePropertyMutations: vi.fn(),
  useAreaMutations: vi.fn(),
}));

// Helper to create mock mutation object
function createMockMutation<TData, _TError, TVariables>(overrides?: {
  isPending?: boolean;
  mutateAsync?: (variables: TVariables) => Promise<TData>;
}) {
  return {
    mutate: vi.fn(),
    mutateAsync: overrides?.mutateAsync ?? vi.fn().mockResolvedValue(undefined),
    isPending: (overrides?.isPending ?? false) as false,
    isSuccess: false as const,
    isError: false as const,
    isIdle: true as const,
    data: undefined,
    error: null,
    reset: vi.fn(),
    context: undefined,
    failureCount: 0,
    failureReason: null,
    status: 'idle' as const,
    variables: undefined,
    submittedAt: 0,
    isPaused: false,
  };
}

// Default mock values
const createDefaultPropertyMutationsReturn = (): UsePropertyMutationsReturn => ({
  createProperty: createMockMutation() as UsePropertyMutationsReturn['createProperty'],
  updateProperty: createMockMutation() as UsePropertyMutationsReturn['updateProperty'],
  deleteProperty: createMockMutation() as UsePropertyMutationsReturn['deleteProperty'],
});

const createDefaultAreaMutationsReturn = (): UseAreaMutationsReturn => ({
  createArea: createMockMutation() as UseAreaMutationsReturn['createArea'],
  updateArea: createMockMutation() as UseAreaMutationsReturn['updateArea'],
  deleteArea: createMockMutation() as UseAreaMutationsReturn['deleteArea'],
  linkCamera: createMockMutation() as UseAreaMutationsReturn['linkCamera'],
  unlinkCamera: createMockMutation() as UseAreaMutationsReturn['unlinkCamera'],
});

// =============================================================================
// Test Data
// =============================================================================

const mockProperties: PropertyResponse[] = [
  {
    id: 1,
    household_id: 1,
    name: 'Main House',
    address: '123 Main St, City, ST 12345',
    timezone: 'America/New_York',
    created_at: '2026-01-15T10:00:00Z',
  },
  {
    id: 2,
    household_id: 1,
    name: 'Beach House',
    address: '456 Ocean Ave',
    timezone: 'America/Los_Angeles',
    created_at: '2026-01-16T10:00:00Z',
  },
];

const mockAreas: AreaResponse[] = [
  {
    id: 1,
    property_id: 1,
    name: 'Front Yard',
    description: 'Main entrance area',
    color: '#76B900',
    created_at: '2026-01-15T11:00:00Z',
  },
  {
    id: 2,
    property_id: 1,
    name: 'Backyard',
    description: 'Pool and patio area',
    color: '#3B82F6',
    created_at: '2026-01-15T12:00:00Z',
  },
];

// =============================================================================
// Tests
// =============================================================================

describe('PropertyManagement', () => {
  let mockPropertyMutations: UsePropertyMutationsReturn;
  let mockAreaMutations: UseAreaMutationsReturn;

  beforeEach(() => {
    vi.clearAllMocks();
    mockPropertyMutations = createDefaultPropertyMutationsReturn();
    mockAreaMutations = createDefaultAreaMutationsReturn();

    vi.mocked(propertyHooks.usePropertyMutations).mockReturnValue(mockPropertyMutations);
    vi.mocked(propertyHooks.useAreaMutations).mockReturnValue(mockAreaMutations);

    // Default mock for area cameras (used by AreaCameraCount)
    vi.mocked(propertyHooks.useAreaCamerasQuery).mockReturnValue({
      cameras: [],
      count: 0,
      areaName: '',
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Loading State', () => {
    it('should show loading state initially', () => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<PropertyManagement householdId={1} />);
      expect(screen.getByText('Loading properties...')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should show error state when fetch fails', () => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: false,
        isError: true,
        error: new Error('Network error'),
        refetch: vi.fn(),
      });

      render(<PropertyManagement householdId={1} />);

      expect(screen.getByText('Error loading properties')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
      expect(screen.getByText('Try again')).toBeInTheDocument();
    });

    it('should retry loading properties on error', async () => {
      const mockRefetch = vi.fn().mockResolvedValue({ data: mockProperties });

      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: false,
        isError: true,
        error: new Error('Network error'),
        refetch: mockRefetch,
      });

      render(<PropertyManagement householdId={1} />);

      const user = userEvent.setup();
      await user.click(screen.getByText('Try again'));

      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no properties exist', () => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<PropertyManagement householdId={1} />);

      expect(screen.getByText('No properties configured')).toBeInTheDocument();
      expect(
        screen.getByText('Add your first property to organize your cameras by location.')
      ).toBeInTheDocument();
    });
  });

  describe('Properties List', () => {
    beforeEach(() => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: mockProperties.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: mockAreas.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should display properties list', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      expect(screen.getByText('Beach House')).toBeInTheDocument();
      expect(screen.getByText('America/New_York')).toBeInTheDocument();
      expect(screen.getByText('America/Los_Angeles')).toBeInTheDocument();
    });

    it('should show property address when available', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      expect(screen.getByText('- 123 Main St, City, ST 12345')).toBeInTheDocument();
    });

    it('should expand property accordion on click', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const toggleButton = screen.getByTestId('property-toggle-1');
      await user.click(toggleButton);

      // After expanding, should show areas section
      await waitFor(() => {
        expect(screen.getByTestId('area-list-property-1')).toBeInTheDocument();
      });
    });

    it('should show areas when property is expanded', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const toggleButton = screen.getByTestId('property-toggle-1');
      await user.click(toggleButton);

      await waitFor(() => {
        expect(screen.getByText('Front Yard')).toBeInTheDocument();
        expect(screen.getByText('Backyard')).toBeInTheDocument();
      });
    });
  });

  describe('Add Property', () => {
    beforeEach(() => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should open add property modal', async () => {
      render(<PropertyManagement householdId={1} />);

      const user = userEvent.setup();
      await user.click(screen.getByTestId('add-property-btn'));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Property Name')).toBeInTheDocument();
      expect(screen.getByLabelText(/Address/)).toBeInTheDocument();
      expect(screen.getByLabelText('Timezone')).toBeInTheDocument();
    });

    it('should validate required fields', async () => {
      render(<PropertyManagement householdId={1} />);

      const user = userEvent.setup();
      await user.click(screen.getByTestId('add-property-btn'));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('save-property-btn'));

      await waitFor(() => {
        expect(screen.getByText('Property name is required')).toBeInTheDocument();
      });
    });

    it('should create a new property successfully', async () => {
      const newProperty: PropertyResponse = {
        id: 3,
        household_id: 1,
        name: 'Test Property',
        address: '789 Test St',
        timezone: 'America/Chicago',
        created_at: '2026-01-20T10:00:00Z',
      };

      const mockCreateMutateAsync = vi.fn().mockResolvedValue(newProperty);
      mockPropertyMutations.createProperty = createMockMutation({
        mutateAsync: mockCreateMutateAsync,
      }) as UsePropertyMutationsReturn['createProperty'];
      vi.mocked(propertyHooks.usePropertyMutations).mockReturnValue(mockPropertyMutations);

      render(<PropertyManagement householdId={1} />);

      const user = userEvent.setup();
      await user.click(screen.getByTestId('add-property-btn'));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText('Property Name'), 'Test Property');
      await user.type(screen.getByLabelText(/Address/), '789 Test St');
      await user.selectOptions(screen.getByLabelText('Timezone'), 'America/Chicago');

      await user.click(screen.getByTestId('save-property-btn'));

      await waitFor(() => {
        expect(mockCreateMutateAsync).toHaveBeenCalledWith({
          householdId: 1,
          data: {
            name: 'Test Property',
            address: '789 Test St',
            timezone: 'America/Chicago',
          },
        });
      });
    });

    it('should close modal on cancel', async () => {
      render(<PropertyManagement householdId={1} />);

      const user = userEvent.setup();
      await user.click(screen.getByTestId('add-property-btn'));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Edit Property', () => {
    beforeEach(() => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: mockProperties.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should open edit modal with property data', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('edit-property-1'));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByDisplayValue('Main House')).toBeInTheDocument();
      expect(screen.getByDisplayValue('123 Main St, City, ST 12345')).toBeInTheDocument();
    });

    it('should update property successfully', async () => {
      const updatedProperty: PropertyResponse = {
        ...mockProperties[0],
        name: 'Updated Main House',
      };

      const mockUpdateMutateAsync = vi.fn().mockResolvedValue(updatedProperty);
      mockPropertyMutations.updateProperty = createMockMutation({
        mutateAsync: mockUpdateMutateAsync,
      }) as UsePropertyMutationsReturn['updateProperty'];
      vi.mocked(propertyHooks.usePropertyMutations).mockReturnValue(mockPropertyMutations);

      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('edit-property-1'));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const nameInput = screen.getByLabelText('Property Name');
      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Main House');

      await user.click(screen.getByTestId('save-property-btn'));

      await waitFor(() => {
        expect(mockUpdateMutateAsync).toHaveBeenCalledWith({
          propertyId: 1,
          data: {
            name: 'Updated Main House',
            address: '123 Main St, City, ST 12345',
            timezone: 'America/New_York',
          },
        });
      });
    });
  });

  describe('Delete Property', () => {
    beforeEach(() => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: mockProperties.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: [],
        total: 0,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should open delete confirmation modal', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('delete-property-1'));

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Property' })).toBeInTheDocument();
      });

      expect(screen.getByText(/Are you sure you want to delete/)).toBeInTheDocument();
    });

    it('should delete property on confirmation', async () => {
      const mockDeleteMutateAsync = vi.fn().mockResolvedValue(undefined);
      mockPropertyMutations.deleteProperty = createMockMutation({
        mutateAsync: mockDeleteMutateAsync,
      }) as UsePropertyMutationsReturn['deleteProperty'];
      vi.mocked(propertyHooks.usePropertyMutations).mockReturnValue(mockPropertyMutations);

      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('delete-property-1'));

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Property' })).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('confirm-delete-property-btn'));

      await waitFor(() => {
        expect(mockDeleteMutateAsync).toHaveBeenCalledWith({
          propertyId: 1,
          householdId: 1,
        });
      });
    });

    it('should cancel delete operation', async () => {
      const mockDeleteMutateAsync = vi.fn();
      mockPropertyMutations.deleteProperty = createMockMutation({
        mutateAsync: mockDeleteMutateAsync,
      }) as UsePropertyMutationsReturn['deleteProperty'];
      vi.mocked(propertyHooks.usePropertyMutations).mockReturnValue(mockPropertyMutations);

      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('delete-property-1'));

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Property' })).toBeInTheDocument();
      });

      // Find the cancel button in the delete modal
      const dialogs = screen.getAllByRole('dialog');
      const deleteDialog = dialogs.find((dialog) =>
        dialog.textContent?.includes('Are you sure you want to delete')
      );
      expect(deleteDialog).toBeDefined();

      const cancelButton = within(deleteDialog!).getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      await waitFor(() => {
        const deleteHeadings = screen.queryAllByRole('heading', { name: 'Delete Property' });
        expect(deleteHeadings).toHaveLength(0);
      });

      expect(mockDeleteMutateAsync).not.toHaveBeenCalled();
    });
  });

  describe('Area Management', () => {
    beforeEach(() => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: mockProperties.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: mockAreas.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should display areas within expanded property', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('property-toggle-1'));

      await waitFor(() => {
        expect(screen.getByText('Front Yard')).toBeInTheDocument();
        expect(screen.getByText('Backyard')).toBeInTheDocument();
      });
    });

    it('should open add area modal', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('property-toggle-1'));

      await waitFor(() => {
        expect(screen.getByTestId('add-area-btn-property-1')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('add-area-btn-property-1'));

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Add Area' })).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Area Name')).toBeInTheDocument();
      expect(screen.getByLabelText(/Description/)).toBeInTheDocument();
    });

    it('should create a new area successfully', async () => {
      const newArea: AreaResponse = {
        id: 3,
        property_id: 1,
        name: 'Garage',
        description: 'Parking area',
        color: '#EF4444',
        created_at: '2026-01-20T10:00:00Z',
      };

      const mockCreateAreaMutateAsync = vi.fn().mockResolvedValue(newArea);
      mockAreaMutations.createArea = createMockMutation({
        mutateAsync: mockCreateAreaMutateAsync,
      }) as UseAreaMutationsReturn['createArea'];
      vi.mocked(propertyHooks.useAreaMutations).mockReturnValue(mockAreaMutations);

      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('property-toggle-1'));

      await waitFor(() => {
        expect(screen.getByTestId('add-area-btn-property-1')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('add-area-btn-property-1'));

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Add Area' })).toBeInTheDocument();
      });

      await user.type(screen.getByLabelText('Area Name'), 'Garage');
      await user.type(screen.getByLabelText(/Description/), 'Parking area');

      // Select red color
      await user.click(screen.getByTestId('area-color-EF4444'));

      await user.click(screen.getByTestId('save-area-btn'));

      await waitFor(() => {
        expect(mockCreateAreaMutateAsync).toHaveBeenCalledWith({
          propertyId: 1,
          data: {
            name: 'Garage',
            description: 'Parking area',
            color: '#EF4444',
          },
        });
      });
    });

    it('should open edit area modal with area data', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('property-toggle-1'));

      await waitFor(() => {
        expect(screen.getByText('Front Yard')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-area-1'));

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Edit Area' })).toBeInTheDocument();
      });

      expect(screen.getByDisplayValue('Front Yard')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Main entrance area')).toBeInTheDocument();
    });

    it('should delete area on confirmation', async () => {
      const mockDeleteAreaMutateAsync = vi.fn().mockResolvedValue(undefined);
      mockAreaMutations.deleteArea = createMockMutation({
        mutateAsync: mockDeleteAreaMutateAsync,
      }) as UseAreaMutationsReturn['deleteArea'];
      vi.mocked(propertyHooks.useAreaMutations).mockReturnValue(mockAreaMutations);

      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('property-toggle-1'));

      await waitFor(() => {
        expect(screen.getByText('Front Yard')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('delete-area-1'));

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Delete Area' })).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('confirm-delete-area-btn'));

      await waitFor(() => {
        expect(mockDeleteAreaMutateAsync).toHaveBeenCalledWith({
          areaId: 1,
          propertyId: 1,
        });
      });
    });
  });

  describe('Camera Count', () => {
    beforeEach(() => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: mockProperties.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: mockAreas.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should display camera count for areas', async () => {
      vi.mocked(propertyHooks.useAreaCamerasQuery).mockImplementation(({ areaId }) => ({
        cameras:
          areaId === 1
            ? [
                { id: 'cam-1', name: 'Front Camera', status: 'online' },
                { id: 'cam-2', name: 'Side Camera', status: 'online' },
              ]
            : [],
        count: areaId === 1 ? 2 : 0,
        areaName: areaId === 1 ? 'Front Yard' : '',
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      }));

      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('property-toggle-1'));

      await waitFor(() => {
        expect(screen.getByTestId('area-camera-count-1')).toBeInTheDocument();
      });

      expect(screen.getByTestId('area-camera-count-1')).toHaveTextContent('2');
    });
  });

  describe('Accessibility', () => {
    beforeEach(() => {
      vi.mocked(propertyHooks.usePropertiesQuery).mockReturnValue({
        properties: mockProperties,
        total: mockProperties.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });

      vi.mocked(propertyHooks.useAreasQuery).mockReturnValue({
        areas: mockAreas,
        total: mockAreas.length,
        isLoading: false,
        isError: false,
        error: null,
        refetch: vi.fn(),
      });
    });

    it('should have proper aria-labels for action buttons', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Edit Main House')).toBeInTheDocument();
      expect(screen.getByLabelText('Delete Main House')).toBeInTheDocument();
    });

    it('should have accessible modal close button', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByTestId('edit-property-1'));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Close modal')).toBeInTheDocument();
    });

    it('should have aria-expanded on accordion buttons', async () => {
      render(<PropertyManagement householdId={1} />);

      await waitFor(() => {
        expect(screen.getByText('Main House')).toBeInTheDocument();
      });

      const toggleButton = screen.getByTestId('property-toggle-1');
      expect(toggleButton).toHaveAttribute('aria-expanded', 'false');

      const user = userEvent.setup();
      await user.click(toggleButton);

      await waitFor(() => {
        expect(toggleButton).toHaveAttribute('aria-expanded', 'true');
      });
    });
  });
});
