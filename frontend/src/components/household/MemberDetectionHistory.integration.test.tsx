import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterAll, afterEach, beforeAll, describe, expect, test } from 'vitest';

import MemberDetectionHistory from './MemberDetectionHistory';

// Mock data
const mockMember = {
  id: 1,
  name: 'Mike',
  role: 'resident',
  trusted_level: 'full',
  notes: null,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
};

const mockDetections = [
  {
    detection_id: 1,
    event_id: 100,
    camera_name: 'Front Door',
    detected_at: '2025-01-31T10:00:00Z',
    confidence: 0.92,
    linked_at: '2025-01-31T10:05:00Z',
    event_summary: 'Person at front door',
    event_risk_score: 35,
    thumbnail_url: '/api/detections/1/thumbnail',
  },
  {
    detection_id: 2,
    event_id: 101,
    camera_name: 'Back Yard',
    detected_at: '2025-01-31T11:00:00Z',
    confidence: 0.88,
    linked_at: '2025-01-31T11:05:00Z',
    event_summary: 'Person in backyard',
    event_risk_score: 20,
    thumbnail_url: '/api/detections/2/thumbnail',
  },
  {
    detection_id: 3,
    event_id: 102,
    camera_name: 'Front Door',
    detected_at: '2025-01-31T12:00:00Z',
    confidence: 0.95,
    linked_at: '2025-01-31T12:05:00Z',
    event_summary: 'Person detected again',
    event_risk_score: 15,
    thumbnail_url: '/api/detections/3/thumbnail',
  },
  {
    detection_id: 4,
    event_id: 103,
    camera_name: 'Side Gate',
    detected_at: '2025-01-31T13:00:00Z',
    confidence: 0.90,
    linked_at: '2025-01-31T13:05:00Z',
    event_summary: 'Person at side gate',
    event_risk_score: 25,
    thumbnail_url: '/api/detections/4/thumbnail',
  },
  {
    detection_id: 5,
    event_id: 104,
    camera_name: 'Back Yard',
    detected_at: '2025-01-31T14:00:00Z',
    confidence: 0.87,
    linked_at: '2025-01-31T14:05:00Z',
    event_summary: 'Person in backyard again',
    event_risk_score: 18,
    thumbnail_url: '/api/detections/5/thumbnail',
  },
];

// MSW server setup
const server = setupServer(
  // GET member
  http.get('/api/household/members/:memberId', ({ params }) => {
    if (params.memberId === '1') {
      return HttpResponse.json(mockMember);
    }
    return HttpResponse.json({ detail: 'Member not found' }, { status: 404 });
  }),

  // GET member detections
  http.get('/api/household/members/:memberId/detections', ({ request }) => {
    const url = new URL(request.url);
    const offset = parseInt(url.searchParams.get('offset') || '0');
    const limit = parseInt(url.searchParams.get('limit') || '20');
    const cameraId = url.searchParams.get('camera_id');
    const startDate = url.searchParams.get('start_date');
    const endDate = url.searchParams.get('end_date');
    const sortBy = url.searchParams.get('sort_by') || 'detected_at';
    const sortOrder = url.searchParams.get('sort_order') || 'desc';

    let filteredDetections = [...mockDetections];

    // Apply camera filter
    if (cameraId) {
      filteredDetections = filteredDetections.filter(
        (d) => d.camera_name.toLowerCase() === cameraId.toLowerCase()
      );
    }

    // Apply date filters
    if (startDate) {
      filteredDetections = filteredDetections.filter(
        (d) => new Date(d.detected_at) >= new Date(startDate)
      );
    }
    if (endDate) {
      filteredDetections = filteredDetections.filter(
        (d) => new Date(d.detected_at) <= new Date(endDate)
      );
    }

    // Apply sorting
    filteredDetections.sort((a, b) => {
      const aVal = a[sortBy as keyof typeof a];
      const bVal = b[sortBy as keyof typeof b];
      const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      return sortOrder === 'asc' ? comparison : -comparison;
    });

    const paginatedDetections = filteredDetections.slice(offset, offset + limit);

    return HttpResponse.json({
      items: paginatedDetections,
      total: filteredDetections.length,
      offset,
      limit,
    });
  }),

  // DELETE unlink detection (success)
  http.delete('/api/household/members/:memberId/detections/:detectionId', () => {
    return new HttpResponse(null, { status: 204 });
  })
);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => server.close());

// Test wrapper with React Query and Router
const createWrapper = (initialPath = '/household/members/1/detections') => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/household/members/:memberId/detections" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe.skip('MemberDetectionHistory - Data Fetching', () => {
  test('initial load fetches GET /api/household/members/{id}/detections', async () => {
    let requestMade = false;
    server.use(
      http.get('/api/household/members/:memberId/detections', ({ params }) => {
        requestMade = true;
        expect(params.memberId).toBe('1');
        return HttpResponse.json({
          items: mockDetections.slice(0, 3),
          total: mockDetections.length,
          offset: 0,
          limit: 20,
        });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(requestMade).toBe(true);
    });

    // Should display detections
    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
      expect(screen.getByText('Person in backyard')).toBeInTheDocument();
    });
  });

  test('pagination: Load More fetches with offset parameter', async () => {
    const user = userEvent.setup();
    let requestCount = 0;
    let lastOffset = 0;

    server.use(
      http.get('/api/household/members/:memberId/detections', ({ request }) => {
        requestCount++;
        const url = new URL(request.url);
        lastOffset = parseInt(url.searchParams.get('offset') || '0');

        if (lastOffset === 0) {
          return HttpResponse.json({
            items: mockDetections.slice(0, 2),
            total: mockDetections.length,
            offset: 0,
            limit: 2,
          });
        } else {
          return HttpResponse.json({
            items: mockDetections.slice(2, 4),
            total: mockDetections.length,
            offset: 2,
            limit: 2,
          });
        }
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    // Click Load More
    const loadMoreButton = screen.getByRole('button', { name: /load more/i });
    await user.click(loadMoreButton);

    // Wait for second page
    await waitFor(() => {
      expect(requestCount).toBe(2);
      expect(lastOffset).toBe(2);
    });
  });

  test('filter by camera sends camera_id query param', async () => {
    const user = userEvent.setup();
    let capturedCameraId: string | null = null;

    server.use(
      http.get('/api/household/members/:memberId/detections', ({ request }) => {
        const url = new URL(request.url);
        capturedCameraId = url.searchParams.get('camera_id');
        const filtered = mockDetections.filter(
          (d) => !capturedCameraId || d.camera_name.toLowerCase() === capturedCameraId.toLowerCase()
        );
        return HttpResponse.json({
          items: filtered,
          total: filtered.length,
          offset: 0,
          limit: 20,
        });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    // Select camera filter
    const cameraFilter = screen.getByRole('combobox', { name: /filter by camera/i });
    await user.click(cameraFilter);
    await user.click(screen.getByText('Front Door'));

    await waitFor(() => {
      expect(capturedCameraId).toBe('front door');
    });
  });

  test('filter by date sends start_date/end_date params', async () => {
    const user = userEvent.setup();
    let capturedParams: { start_date: string | null; end_date: string | null } = {
      start_date: null,
      end_date: null,
    };

    server.use(
      http.get('/api/household/members/:memberId/detections', ({ request }) => {
        const url = new URL(request.url);
        capturedParams = {
          start_date: url.searchParams.get('start_date'),
          end_date: url.searchParams.get('end_date'),
        };
        return HttpResponse.json({
          items: mockDetections,
          total: mockDetections.length,
          offset: 0,
          limit: 20,
        });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    // Set date range
    const startDateInput = screen.getByLabelText(/start date/i);
    const endDateInput = screen.getByLabelText(/end date/i);

    await user.type(startDateInput, '2025-01-31');
    await user.type(endDateInput, '2025-01-31');

    await waitFor(() => {
      expect(capturedParams.start_date).toBe('2025-01-31');
      expect(capturedParams.end_date).toBe('2025-01-31');
    });
  });

  test('sort parameter sent correctly', async () => {
    const user = userEvent.setup();
    let capturedSort: { sort_by: string | null; sort_order: string | null } = {
      sort_by: null,
      sort_order: null,
    };

    server.use(
      http.get('/api/household/members/:memberId/detections', ({ request }) => {
        const url = new URL(request.url);
        capturedSort = {
          sort_by: url.searchParams.get('sort_by'),
          sort_order: url.searchParams.get('sort_order'),
        };
        return HttpResponse.json({
          items: mockDetections,
          total: mockDetections.length,
          offset: 0,
          limit: 20,
        });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    // Change sort
    const sortSelect = screen.getByRole('combobox', { name: /sort by/i });
    await user.click(sortSelect);
    await user.click(screen.getByText(/confidence/i));

    await waitFor(() => {
      expect(capturedSort.sort_by).toBe('confidence');
    });

    // Change order
    const orderButton = screen.getByRole('button', { name: /ascending/i });
    await user.click(orderButton);

    await waitFor(() => {
      expect(capturedSort.sort_order).toBe('asc');
    });
  });
});

describe.skip('MemberDetectionHistory - Unlink Flow', () => {
  test('click unlink → confirm → DELETE request sent', async () => {
    const user = userEvent.setup();
    let deleteCalled = false;
    let deletedDetectionId: string | null = null;

    server.use(
      http.delete('/api/household/members/:memberId/detections/:detectionId', ({ params }) => {
        deleteCalled = true;
        deletedDetectionId = params.detectionId as string;
        return new HttpResponse(null, { status: 204 });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    // Find first detection row
    const firstDetection = screen.getAllByTestId('detection-row')[0];
    const unlinkButton = within(firstDetection).getByRole('button', { name: /unlink/i });
    await user.click(unlinkButton);

    // Confirm dialog
    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(deleteCalled).toBe(true);
      expect(deletedDetectionId).toBe('1');
    });
  });

  test('after successful unlink, detection removed from list', async () => {
    const user = userEvent.setup();

    server.use(
      http.get('/api/household/members/:memberId/detections', () => {
        // Initially return 2 detections
        return HttpResponse.json({
          items: mockDetections.slice(0, 2),
          total: 2,
          offset: 0,
          limit: 20,
        });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
      expect(screen.getByText('Person in backyard')).toBeInTheDocument();
    });

    // After unlink, return only 1 detection
    server.use(
      http.get('/api/household/members/:memberId/detections', () => {
        return HttpResponse.json({
          items: mockDetections.slice(1, 2),
          total: 1,
          offset: 0,
          limit: 20,
        });
      })
    );

    // Unlink first detection
    const firstDetection = screen.getAllByTestId('detection-row')[0];
    const unlinkButton = within(firstDetection).getByRole('button', { name: /unlink/i });
    await user.click(unlinkButton);

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    await user.click(confirmButton);

    // First detection should be removed
    await waitFor(() => {
      expect(screen.queryByText('Person at front door')).not.toBeInTheDocument();
    });

    // Second detection should still be visible
    expect(screen.getByText('Person in backyard')).toBeInTheDocument();
  });

  test('handle 404 on unlink (detection already unlinked)', async () => {
    const user = userEvent.setup();

    server.use(
      http.delete('/api/household/members/:memberId/detections/:detectionId', () => {
        return HttpResponse.json(
          { detail: 'Detection link not found' },
          { status: 404 }
        );
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    const firstDetection = screen.getAllByTestId('detection-row')[0];
    const unlinkButton = within(firstDetection).getByRole('button', { name: /unlink/i });
    await user.click(unlinkButton);

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(screen.getByText(/detection link not found/i)).toBeInTheDocument();
    });
  });

  test('cancel unlink dialog does not call API', async () => {
    const user = userEvent.setup();
    let deleteCalled = false;

    server.use(
      http.delete('/api/household/members/:memberId/detections/:detectionId', () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    const firstDetection = screen.getAllByTestId('detection-row')[0];
    const unlinkButton = within(firstDetection).getByRole('button', { name: /unlink/i });
    await user.click(unlinkButton);

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    // Wait a bit to ensure no API call
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(deleteCalled).toBe(false);
  });
});

describe.skip('MemberDetectionHistory - Error States', () => {
  test('network error shows error message with retry', async () => {
    const user = userEvent.setup();

    server.use(
      http.get('/api/household/members/:memberId/detections', () => {
        return HttpResponse.error();
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/failed to load detections/i)).toBeInTheDocument();
    });

    // Should show retry button
    const retryButton = screen.getByRole('button', { name: /retry/i });
    expect(retryButton).toBeInTheDocument();

    // Mock successful retry
    server.use(
      http.get('/api/household/members/:memberId/detections', () => {
        return HttpResponse.json({
          items: mockDetections.slice(0, 2),
          total: mockDetections.length,
          offset: 0,
          limit: 20,
        });
      })
    );

    await user.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });
  });

  test('empty response shows empty state', async () => {
    server.use(
      http.get('/api/household/members/:memberId/detections', () => {
        return HttpResponse.json({
          items: [],
          total: 0,
          offset: 0,
          limit: 20,
        });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/no detections found/i)).toBeInTheDocument();
    });
  });

  test('500 error shows error message', async () => {
    server.use(
      http.get('/api/household/members/:memberId/detections', () => {
        return HttpResponse.json(
          { detail: 'Internal server error' },
          { status: 500 }
        );
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/internal server error/i)).toBeInTheDocument();
    });
  });
});

describe.skip('MemberDetectionHistory - UI and Display', () => {
  test('displays detection cards with thumbnails and metadata', async () => {
    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    // Check metadata
    expect(screen.getByText(/front door/i)).toBeInTheDocument();
    expect(screen.getByText(/confidence: 0.92/i)).toBeInTheDocument();
    expect(screen.getByText(/risk: 35/i)).toBeInTheDocument();
  });

  test('shows total detection count', async () => {
    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/showing .* of 5 detections/i)).toBeInTheDocument();
    });
  });

  test('displays member name in header', async () => {
    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/detections for mike/i)).toBeInTheDocument();
    });
  });

  test('shows linked timestamp for each detection', async () => {
    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    // Should show when it was linked
    expect(screen.getByText(/linked on/i)).toBeInTheDocument();
  });

  test('clicking detection navigates to event detail', async () => {
    const user = userEvent.setup();

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    const detectionCard = screen.getAllByTestId('detection-row')[0];
    const viewButton = within(detectionCard).getByRole('button', { name: /view event/i });

    await user.click(viewButton);

    // Should navigate to event detail
    await waitFor(() => {
      expect(window.location.pathname).toContain('/events/100');
    });
  });
});

describe.skip('MemberDetectionHistory - Filtering and Sorting', () => {
  test('camera filter shows unique camera names', async () => {
    const user = userEvent.setup();

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    const cameraFilter = screen.getByRole('combobox', { name: /filter by camera/i });
    await user.click(cameraFilter);

    // Should show unique camera names
    expect(screen.getByText('Front Door')).toBeInTheDocument();
    expect(screen.getByText('Back Yard')).toBeInTheDocument();
    expect(screen.getByText('Side Gate')).toBeInTheDocument();
  });

  test('date filter clears when reset button clicked', async () => {
    const user = userEvent.setup();

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    const startDateInput = screen.getByLabelText(/start date/i);
    await user.type(startDateInput, '2025-01-31');

    const resetButton = screen.getByRole('button', { name: /clear filters/i });
    await user.click(resetButton);

    expect(startDateInput).toHaveValue('');
  });

  test('sort order toggle button updates UI', async () => {
    const user = userEvent.setup();

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    const orderButton = screen.getByRole('button', { name: /descending/i });
    await user.click(orderButton);

    expect(screen.getByRole('button', { name: /ascending/i })).toBeInTheDocument();
  });
});

describe.skip('MemberDetectionHistory - Loading States', () => {
  test('shows loading spinner during initial fetch', async () => {
    server.use(
      http.get('/api/household/members/:memberId/detections', async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json({
          items: mockDetections,
          total: mockDetections.length,
          offset: 0,
          limit: 20,
        });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });
  });

  test('Load More button shows loading state when clicked', async () => {
    const user = userEvent.setup();

    server.use(
      http.get('/api/household/members/:memberId/detections', async ({ request }) => {
        const url = new URL(request.url);
        const offset = parseInt(url.searchParams.get('offset') || '0');

        if (offset > 0) {
          await new Promise((resolve) => setTimeout(resolve, 100));
        }

        return HttpResponse.json({
          items: mockDetections.slice(offset, offset + 2),
          total: mockDetections.length,
          offset,
          limit: 2,
        });
      })
    );

    render(<MemberDetectionHistory memberId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Person at front door')).toBeInTheDocument();
    });

    const loadMoreButton = screen.getByRole('button', { name: /load more/i });
    await user.click(loadMoreButton);

    expect(loadMoreButton).toBeDisabled();
    expect(within(loadMoreButton).getByRole('status')).toBeInTheDocument();
  });
});
