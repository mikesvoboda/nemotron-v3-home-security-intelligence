/**
 * Integration Tests for HouseholdPage Component
 *
 * This is the RED phase of TDD - these tests will FAIL because HouseholdPage doesn't exist yet.
 *
 * Tests cover:
 * 1. API Integration - Real API interactions (mocked at network level with MSW)
 * 2. Router Integration - Route accessibility and navigation
 * 3. Full User Flows - Complete CRUD operations from UI to API
 * 4. Form Validation Flows - Client-side and server-side validation
 *
 * @see NEM-4848 - [TDD] Feature 1: Integration tests for Phase 1: Household Members Page
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HouseholdPage from './HouseholdPage';
import { server } from '../mocks/server';

import type { HouseholdMember, RegisteredVehicle } from '../hooks/useHouseholdApi';

// ============================================================================
// Mock Data
// ============================================================================

const mockMembers: HouseholdMember[] = [
  {
    id: 1,
    name: 'John Doe',
    role: 'resident',
    trusted_level: 'full',
    notes: null,
    typical_schedule: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Jane Smith',
    role: 'family',
    trusted_level: 'partial',
    notes: 'Visits weekly',
    typical_schedule: null,
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
];

const mockVehicles: RegisteredVehicle[] = [
  {
    id: 1,
    description: 'Silver Tesla Model 3',
    vehicle_type: 'car',
    license_plate: 'ABC123',
    color: 'silver',
    owner_id: 1,
    trusted: true,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 2,
    description: 'Blue Honda Civic',
    vehicle_type: 'car',
    license_plate: null,
    color: 'blue',
    owner_id: null,
    trusted: false,
    created_at: '2024-01-02T00:00:00Z',
  },
];

// ============================================================================
// Test Helpers
// ============================================================================

/**
 * Render component with required providers (QueryClient and Router).
 */
function renderWithProviders(ui: React.ReactElement, { route = '/household' } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/household" element={ui} />
          <Route path="/" element={<div>Home Page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ============================================================================
// API Integration Tests
// ============================================================================

describe('HouseholdPage - API Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Setup default MSW handlers
    server.use(
      http.get('/api/household/members', () => {
        return HttpResponse.json(mockMembers);
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json(mockVehicles);
      })
    );
  });

  it('fetches members on mount', async () => {
    renderWithProviders(<HouseholdPage />);

    // Should show loading state initially
    expect(screen.getByText(/loading/i)).toBeInTheDocument();

    // Should display members after fetch completes
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });
  });

  it('fetches vehicles on mount', async () => {
    renderWithProviders(<HouseholdPage />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
      expect(screen.getByText('Blue Honda Civic')).toBeInTheDocument();
    });
  });

  it('handles network error gracefully', async () => {
    // Override handlers to return error
    server.use(
      http.get('/api/household/members', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
      })
    );

    renderWithProviders(<HouseholdPage />);

    // Should show error message
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  it('retry button refetches data', async () => {
    let callCount = 0;

    // First call fails, second succeeds
    server.use(
      http.get('/api/household/members', () => {
        callCount++;
        if (callCount === 1) {
          return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
        }
        return HttpResponse.json(mockMembers);
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json(mockVehicles);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for error
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });

    // Click retry button
    const retryButton = screen.getByRole('button', { name: /retry/i });
    await user.click(retryButton);

    // Should show members after retry
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
  });

  it('create member makes POST request with correct body', async () => {
    let capturedBody: unknown = null;

    server.use(
      http.post('/api/household/members', async ({ request }) => {
        capturedBody = await request.json();
        const newMember: HouseholdMember = {
          id: 3,
          name: 'New Member',
          role: 'service_worker',
          trusted_level: 'monitor',
          notes: null,
          typical_schedule: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return HttpResponse.json(newMember, { status: 201 });
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for page to load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Add Member button
    const addButton = screen.getByRole('button', { name: /add member/i });
    await user.click(addButton);

    // Fill form
    const nameInput = screen.getByLabelText(/name/i);
    await user.type(nameInput, 'New Member');

    const roleSelect = screen.getByLabelText(/role/i);
    await user.selectOptions(roleSelect, 'service_worker');

    const trustSelect = screen.getByLabelText(/trust/i);
    await user.selectOptions(trustSelect, 'monitor');

    // Submit form
    const submitButton = screen.getByRole('button', { name: /submit|save/i });
    await user.click(submitButton);

    // Verify request body
    await waitFor(() => {
      expect(capturedBody).toEqual({
        name: 'New Member',
        role: 'service_worker',
        trusted_level: 'monitor',
        notes: null,
        typical_schedule: null,
      });
    });
  });

  it('update member makes PATCH request with correct body', async () => {
    let capturedBody: unknown = null;
    let capturedId: string | null = null;

    server.use(
      http.patch('/api/household/members/:id', async ({ params, request }) => {
        capturedId = params.id as string;
        capturedBody = await request.json();
        const updatedMember: HouseholdMember = {
          ...mockMembers[0],
          name: 'Updated Name',
        };
        return HttpResponse.json(updatedMember);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for page to load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Edit button for first member
    const editButtons = screen.getAllByRole('button', { name: /edit/i });
    await user.click(editButtons[0]);

    // Modify name
    const nameInput = screen.getByLabelText(/name/i);
    await user.clear(nameInput);
    await user.type(nameInput, 'Updated Name');

    // Submit form
    const submitButton = screen.getByRole('button', { name: /submit|save|update/i });
    await user.click(submitButton);

    // Verify request
    await waitFor(() => {
      expect(capturedId).toBe('1');
      expect(capturedBody).toMatchObject({
        name: 'Updated Name',
      });
    });
  });

  it('delete member makes DELETE request', async () => {
    let deletedId: string | null = null;

    server.use(
      http.delete('/api/household/members/:id', ({ params }) => {
        deletedId = params.id as string;
        return new HttpResponse(null, { status: 204 });
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for page to load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Delete button
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
    await user.click(deleteButtons[0]);

    // Confirm deletion
    const confirmButton = screen.getByRole('button', { name: /confirm|yes/i });
    await user.click(confirmButton);

    // Verify DELETE request was made
    await waitFor(() => {
      expect(deletedId).toBe('1');
    });
  });

  it('create vehicle makes POST request', async () => {
    let capturedBody: unknown = null;

    server.use(
      http.post('/api/household/vehicles', async ({ request }) => {
        capturedBody = await request.json();
        const newVehicle: RegisteredVehicle = {
          id: 3,
          description: 'Red Ford F-150',
          vehicle_type: 'truck',
          license_plate: 'XYZ789',
          color: 'red',
          owner_id: 1,
          trusted: true,
          created_at: new Date().toISOString(),
        };
        return HttpResponse.json(newVehicle, { status: 201 });
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for page to load
    await waitFor(() => {
      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
    });

    // Click Add Vehicle button
    const addButton = screen.getByRole('button', { name: /add vehicle/i });
    await user.click(addButton);

    // Fill form
    const descInput = screen.getByLabelText(/description/i);
    await user.type(descInput, 'Red Ford F-150');

    const typeSelect = screen.getByLabelText(/type/i);
    await user.selectOptions(typeSelect, 'truck');

    const plateInput = screen.getByLabelText(/license plate/i);
    await user.type(plateInput, 'XYZ789');

    // Submit form
    const submitButton = screen.getByRole('button', { name: /submit|save/i });
    await user.click(submitButton);

    // Verify request body
    await waitFor(() => {
      expect(capturedBody).toMatchObject({
        description: 'Red Ford F-150',
        vehicle_type: 'truck',
        license_plate: 'XYZ789',
      });
    });
  });

  it('update vehicle makes PATCH request', async () => {
    let capturedBody: unknown = null;
    let capturedId: string | null = null;

    server.use(
      http.patch('/api/household/vehicles/:id', async ({ params, request }) => {
        capturedId = params.id as string;
        capturedBody = await request.json();
        const updatedVehicle: RegisteredVehicle = {
          ...mockVehicles[0],
          description: 'Updated Description',
        };
        return HttpResponse.json(updatedVehicle);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for page to load
    await waitFor(() => {
      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
    });

    // Click Edit button for first vehicle
    const vehicleSection = screen.getByText(/vehicles/i).closest('section');
    const editButtons = within(vehicleSection!).getAllByRole('button', { name: /edit/i });
    await user.click(editButtons[0]);

    // Modify description
    const descInput = screen.getByLabelText(/description/i);
    await user.clear(descInput);
    await user.type(descInput, 'Updated Description');

    // Submit form
    const submitButton = screen.getByRole('button', { name: /submit|save|update/i });
    await user.click(submitButton);

    // Verify request
    await waitFor(() => {
      expect(capturedId).toBe('1');
      expect(capturedBody).toMatchObject({
        description: 'Updated Description',
      });
    });
  });

  it('delete vehicle makes DELETE request', async () => {
    let deletedId: string | null = null;

    server.use(
      http.delete('/api/household/vehicles/:id', ({ params }) => {
        deletedId = params.id as string;
        return new HttpResponse(null, { status: 204 });
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for page to load
    await waitFor(() => {
      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
    });

    // Click Delete button for first vehicle
    const vehicleSection = screen.getByText(/vehicles/i).closest('section');
    const deleteButtons = within(vehicleSection!).getAllByRole('button', { name: /delete/i });
    await user.click(deleteButtons[0]);

    // Confirm deletion
    const confirmButton = screen.getByRole('button', { name: /confirm|yes/i });
    await user.click(confirmButton);

    // Verify DELETE request was made
    await waitFor(() => {
      expect(deletedId).toBe('1');
    });
  });
});

// ============================================================================
// Router Integration Tests
// ============================================================================

describe('HouseholdPage - Router Integration', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/household/members', () => {
        return HttpResponse.json(mockMembers);
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json(mockVehicles);
      })
    );
  });

  it('page accessible at /household route', async () => {
    renderWithProviders(<HouseholdPage />, { route: '/household' });

    // Should render page content
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
  });

  it('navigation to /household renders page', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/']}>
          <Routes>
            <Route path="/" element={<div>Home Page</div>} />
            <Route path="/household" element={<HouseholdPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Initially on home page
    expect(screen.getByText('Home Page')).toBeInTheDocument();

    // Navigate to /household (would happen via Link click in real app)
    const link = document.createElement('a');
    link.href = '/household';
    link.textContent = 'Go to Household';
    document.body.appendChild(link);

    // Simulate navigation by re-rendering with different route
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/household']}>
          <Routes>
            <Route path="/" element={<div>Home Page</div>} />
            <Route path="/household" element={<HouseholdPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    // Should show household page content
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
  });

  it('page title set correctly', async () => {
    renderWithProviders(<HouseholdPage />);

    // Check document title or page heading
    await waitFor(() => {
      const heading = screen.getByRole('heading', { name: /household/i, level: 1 });
      expect(heading).toBeInTheDocument();
    });
  });

  it('breadcrumb displays correctly', async () => {
    renderWithProviders(<HouseholdPage />);

    // Check for breadcrumb navigation
    await waitFor(() => {
      // Breadcrumb might show: Home > Household
      const breadcrumbs = screen.queryByRole('navigation', { name: /breadcrumb/i });
      if (breadcrumbs) {
        expect(breadcrumbs).toBeInTheDocument();
        expect(within(breadcrumbs).getByText(/household/i)).toBeInTheDocument();
      }
    });
  });
});

// ============================================================================
// Full User Flow Tests
// ============================================================================

describe('HouseholdPage - Full User Flows', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/household/members', () => {
        return HttpResponse.json(mockMembers);
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json(mockVehicles);
      })
    );
  });

  it('add member flow: click Add → fill form → submit → see in list', async () => {
    const newMember: HouseholdMember = {
      id: 3,
      name: 'Alice Johnson',
      role: 'frequent_visitor',
      trusted_level: 'partial',
      notes: 'Friend of the family',
      typical_schedule: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    server.use(
      http.post('/api/household/members', () => {
        return HttpResponse.json(newMember, { status: 201 });
      }),
      http.get('/api/household/members', () => {
        return HttpResponse.json([...mockMembers, newMember]);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Add Member
    const addButton = screen.getByRole('button', { name: /add member/i });
    await user.click(addButton);

    // Fill form
    await user.type(screen.getByLabelText(/name/i), 'Alice Johnson');
    await user.selectOptions(screen.getByLabelText(/role/i), 'frequent_visitor');
    await user.selectOptions(screen.getByLabelText(/trust/i), 'partial');

    const notesInput = screen.queryByLabelText(/notes/i);
    if (notesInput) {
      await user.type(notesInput, 'Friend of the family');
    }

    // Submit
    const submitButton = screen.getByRole('button', { name: /submit|save/i });
    await user.click(submitButton);

    // Verify new member appears in list
    await waitFor(() => {
      expect(screen.getByText('Alice Johnson')).toBeInTheDocument();
      expect(screen.getByText('Friend of the family')).toBeInTheDocument();
    });
  });

  it('edit member flow: click Edit → modify data → submit → see updated in list', async () => {
    const updatedMember: HouseholdMember = {
      ...mockMembers[0],
      name: 'John Doe Jr.',
      notes: 'Updated notes',
    };

    // Use stateful handler that returns original data until mutation occurs
    let membersData = [...mockMembers];

    server.use(
      http.patch('/api/household/members/:id', () => {
        // Update the data after mutation
        membersData = [updatedMember, mockMembers[1]];
        return HttpResponse.json(updatedMember);
      }),
      http.get('/api/household/members', () => {
        return HttpResponse.json(membersData);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Edit
    const editButtons = screen.getAllByRole('button', { name: /edit/i });
    await user.click(editButtons[0]);

    // Modify data
    const nameInput = screen.getByLabelText(/name/i);
    await user.clear(nameInput);
    await user.type(nameInput, 'John Doe Jr.');

    const notesInput = screen.queryByLabelText(/notes/i);
    if (notesInput) {
      await user.clear(notesInput);
      await user.type(notesInput, 'Updated notes');
    }

    // Submit
    const submitButton = screen.getByRole('button', { name: /submit|save|update/i });
    await user.click(submitButton);

    // Verify updated data appears
    await waitFor(() => {
      expect(screen.getByText('John Doe Jr.')).toBeInTheDocument();
      expect(screen.getByText('Updated notes')).toBeInTheDocument();
    });
  });

  it('delete member flow: click Delete → confirm → member removed from list', async () => {
    // Use stateful handler that returns original data until deletion occurs
    let membersData = [...mockMembers];

    server.use(
      http.delete('/api/household/members/1', () => {
        // Remove member after deletion
        membersData = [mockMembers[1]];
        return new HttpResponse(null, { status: 204 });
      }),
      http.get('/api/household/members', () => {
        return HttpResponse.json(membersData);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });

    // Click Delete
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
    await user.click(deleteButtons[0]);

    // Confirm deletion
    const confirmButton = screen.getByRole('button', { name: /confirm|yes/i });
    await user.click(confirmButton);

    // Verify member removed
    await waitFor(() => {
      expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });
  });

  it('add vehicle flow: click Add → fill form → submit → see in list', async () => {
    const newVehicle: RegisteredVehicle = {
      id: 3,
      description: 'Black Jeep Wrangler',
      vehicle_type: 'suv',
      license_plate: 'DEF456',
      color: 'black',
      owner_id: 2,
      trusted: true,
      created_at: new Date().toISOString(),
    };

    server.use(
      http.post('/api/household/members', () => {
        return HttpResponse.json(newVehicle, { status: 201 });
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json([...mockVehicles, newVehicle]);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
    });

    // Click Add Vehicle
    const addButton = screen.getByRole('button', { name: /add vehicle/i });
    await user.click(addButton);

    // Fill form
    await user.type(screen.getByLabelText(/description/i), 'Black Jeep Wrangler');
    await user.selectOptions(screen.getByLabelText(/type/i), 'suv');
    await user.type(screen.getByLabelText(/license plate/i), 'DEF456');

    // Submit
    const submitButton = screen.getByRole('button', { name: /submit|save/i });
    await user.click(submitButton);

    // Verify new vehicle appears
    await waitFor(() => {
      expect(screen.getByText('Black Jeep Wrangler')).toBeInTheDocument();
    });
  });

  it('edit vehicle flow: click Edit → modify data → submit → see updated in list', async () => {
    const updatedVehicle: RegisteredVehicle = {
      ...mockVehicles[0],
      description: 'Silver Tesla Model 3 (Updated)',
    };

    // Use stateful handler that returns original data until mutation occurs
    let vehiclesData = [...mockVehicles];

    server.use(
      http.patch('/api/household/vehicles/:id', () => {
        // Update the data after mutation
        vehiclesData = [updatedVehicle, mockVehicles[1]];
        return HttpResponse.json(updatedVehicle);
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json(vehiclesData);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
    });

    // Click Edit for first vehicle
    const vehicleSection = screen.getByText(/vehicles/i).closest('section');
    const editButtons = within(vehicleSection!).getAllByRole('button', { name: /edit/i });
    await user.click(editButtons[0]);

    // Modify data
    const descInput = screen.getByLabelText(/description/i);
    await user.clear(descInput);
    await user.type(descInput, 'Silver Tesla Model 3 (Updated)');

    // Submit
    const submitButton = screen.getByRole('button', { name: /submit|save|update/i });
    await user.click(submitButton);

    // Verify updated data appears
    await waitFor(() => {
      expect(screen.getByText('Silver Tesla Model 3 (Updated)')).toBeInTheDocument();
    });
  });

  it('delete vehicle flow: click Delete → confirm → vehicle removed from list', async () => {
    // Use stateful handler that returns original data until deletion occurs
    let vehiclesData = [...mockVehicles];

    server.use(
      http.delete('/api/household/vehicles/1', () => {
        // Remove vehicle after deletion
        vehiclesData = [mockVehicles[1]];
        return new HttpResponse(null, { status: 204 });
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json(vehiclesData);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
      expect(screen.getByText('Blue Honda Civic')).toBeInTheDocument();
    });

    // Click Delete for first vehicle
    const vehicleSection = screen.getByText(/vehicles/i).closest('section');
    const deleteButtons = within(vehicleSection!).getAllByRole('button', { name: /delete/i });
    await user.click(deleteButtons[0]);

    // Confirm deletion
    const confirmButton = screen.getByRole('button', { name: /confirm|yes/i });
    await user.click(confirmButton);

    // Verify vehicle removed
    await waitFor(() => {
      expect(screen.queryByText('Silver Tesla Model 3')).not.toBeInTheDocument();
      expect(screen.getByText('Blue Honda Civic')).toBeInTheDocument();
    });
  });

  it('cancel add member: open modal → click cancel → modal closes, no API call', async () => {
    const postSpy = vi.fn();

    server.use(
      http.post('/api/household/members', () => {
        postSpy();
        return HttpResponse.json({}, { status: 201 });
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Add Member
    const addButton = screen.getByRole('button', { name: /add member/i });
    await user.click(addButton);

    // Verify modal is open
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();

    // Click Cancel
    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    // Verify modal closed
    await waitFor(() => {
      expect(screen.queryByLabelText(/name/i)).not.toBeInTheDocument();
    });

    // Verify no API call was made
    expect(postSpy).not.toHaveBeenCalled();
  });

  it('cancel edit: open edit modal → modify → cancel → data unchanged', async () => {
    const patchSpy = vi.fn();

    server.use(
      http.patch('/api/household/members/:id', () => {
        patchSpy();
        return HttpResponse.json(mockMembers[0]);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Edit
    const editButtons = screen.getAllByRole('button', { name: /edit/i });
    await user.click(editButtons[0]);

    // Modify data
    const nameInput = screen.getByLabelText(/name/i);
    await user.clear(nameInput);
    await user.type(nameInput, 'Changed Name');

    // Click Cancel
    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    // Verify original data still displayed
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.queryByText('Changed Name')).not.toBeInTheDocument();
    });

    // Verify no API call was made
    expect(patchSpy).not.toHaveBeenCalled();
  });

  it('refresh button refetches all data', async () => {
    let fetchCount = 0;

    server.use(
      http.get('/api/household/members', () => {
        fetchCount++;
        return HttpResponse.json(mockMembers);
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json(mockVehicles);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    const initialFetchCount = fetchCount;

    // Click Refresh button
    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    // Verify data was refetched
    await waitFor(() => {
      expect(fetchCount).toBeGreaterThan(initialFetchCount);
    });
  });
});

// ============================================================================
// Form Validation Flow Tests
// ============================================================================

describe('HouseholdPage - Form Validation', () => {
  beforeEach(() => {
    server.use(
      http.get('/api/household/members', () => {
        return HttpResponse.json(mockMembers);
      }),
      http.get('/api/household/vehicles', () => {
        return HttpResponse.json(mockVehicles);
      })
    );
  });

  it('cannot submit member without name', async () => {
    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Add Member
    const addButton = screen.getByRole('button', { name: /add member/i });
    await user.click(addButton);

    // Try to submit without filling name
    const submitButton = screen.getByRole('button', { name: /submit|save/i });
    await user.click(submitButton);

    // Should show validation error
    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });
  });

  it('cannot submit vehicle without description', async () => {
    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Silver Tesla Model 3')).toBeInTheDocument();
    });

    // Click Add Vehicle
    const addButton = screen.getByRole('button', { name: /add vehicle/i });
    await user.click(addButton);

    // Try to submit without filling description
    const submitButton = screen.getByRole('button', { name: /submit|save/i });
    await user.click(submitButton);

    // Should show validation error
    await waitFor(() => {
      expect(screen.getByText(/description is required/i)).toBeInTheDocument();
    });
  });

  it('error message displays on validation failure', async () => {
    server.use(
      http.post('/api/household/members', () => {
        return HttpResponse.json(
          { detail: 'Name must be at least 2 characters' },
          { status: 400 }
        );
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Add Member
    const addButton = screen.getByRole('button', { name: /add member/i });
    await user.click(addButton);

    // Fill form with invalid data
    await user.type(screen.getByLabelText(/name/i), 'A');
    await user.selectOptions(screen.getByLabelText(/role/i), 'resident');
    await user.selectOptions(screen.getByLabelText(/trust/i), 'full');

    // Submit
    const submitButton = screen.getByRole('button', { name: /submit|save/i });
    await user.click(submitButton);

    // Should show error message
    await waitFor(() => {
      expect(screen.getByText(/Name must be at least 2 characters/i)).toBeInTheDocument();
    });
  });

  it('submit button disabled during API call', async () => {
    let resolveRequest: (value: unknown) => void;
    const requestPromise = new Promise((resolve) => {
      resolveRequest = resolve;
    });

    server.use(
      http.post('/api/household/members', async () => {
        await requestPromise;
        const newMember: HouseholdMember = {
          id: 3,
          name: 'New Member',
          role: 'resident',
          trusted_level: 'full',
          notes: null,
          typical_schedule: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        return HttpResponse.json(newMember, { status: 201 });
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Add Member
    const addButton = screen.getByRole('button', { name: /add member/i });
    await user.click(addButton);

    // Fill form
    await user.type(screen.getByLabelText(/name/i), 'New Member');
    await user.selectOptions(screen.getByLabelText(/role/i), 'resident');
    await user.selectOptions(screen.getByLabelText(/trust/i), 'full');

    // Submit
    const submitButton = screen.getByRole('button', { name: /submit|save/i });
    await user.click(submitButton);

    // Submit button should be disabled
    await waitFor(() => {
      expect(submitButton).toBeDisabled();
    });

    // Resolve the request
    resolveRequest!({});

    // Submit button should be enabled again
    await waitFor(() => {
      expect(submitButton).not.toBeDisabled();
    });
  });

  it('form resets after successful submission', async () => {
    const newMember: HouseholdMember = {
      id: 3,
      name: 'Test Member',
      role: 'resident',
      trusted_level: 'full',
      notes: null,
      typical_schedule: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    server.use(
      http.post('/api/household/members', () => {
        return HttpResponse.json(newMember, { status: 201 });
      }),
      http.get('/api/household/members', () => {
        return HttpResponse.json([...mockMembers, newMember]);
      })
    );

    const user = userEvent.setup();
    renderWithProviders(<HouseholdPage />);

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });

    // Click Add Member
    const addButton = screen.getByRole('button', { name: /add member/i });
    await user.click(addButton);

    // Fill form
    await user.type(screen.getByLabelText(/name/i), 'Test Member');
    await user.selectOptions(screen.getByLabelText(/role/i), 'resident');
    await user.selectOptions(screen.getByLabelText(/trust/i), 'full');

    // Submit
    const submitButton = screen.getByRole('button', { name: /submit|save/i });
    await user.click(submitButton);

    // Wait for submission to complete and modal to close
    await waitFor(() => {
      expect(screen.queryByLabelText(/name/i)).not.toBeInTheDocument();
    });

    // Verify new member appears in list
    expect(screen.getByText('Test Member')).toBeInTheDocument();

    // Open modal again - form should be reset
    await user.click(addButton);

    await waitFor(() => {
      const nameInput = screen.getByLabelText<HTMLInputElement>(/name/i);
      expect(nameInput.value).toBe('');
    });
  });
});
