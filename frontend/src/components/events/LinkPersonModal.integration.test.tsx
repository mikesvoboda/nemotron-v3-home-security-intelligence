import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from 'vitest';

import LinkPersonModal from './LinkPersonModal';

// Mock data
const mockMembers = [
  {
    id: 1,
    name: 'Mike',
    role: 'resident',
    trusted_level: 'full',
    notes: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Jane',
    role: 'family',
    trusted_level: 'full',
    notes: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 3,
    name: 'Bob',
    role: 'guest',
    trusted_level: 'partial',
    notes: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
];

const mockDetection = {
  id: 123,
  object_type: 'person',
  confidence: 0.95,
  detected_at: '2025-01-31T10:00:00Z',
  thumbnail_url: '/api/detections/123/thumbnail',
};

const mockEvent = {
  id: 456,
  summary: 'Person detected at front door',
  risk_score: 35,
  created_at: '2025-01-31T10:00:00Z',
};

// MSW server setup
const server = setupServer(
  // GET household members
  http.get('/api/household/members', () => {
    return HttpResponse.json(mockMembers);
  }),

  // POST link detection (success)
  http.post('/api/household/members/:memberId/detections/:detectionId', async ({ params, request }) => {
    const body = (await request.json()) as { notes?: string; confidence?: number };
    return HttpResponse.json(
      {
        id: 1,
        member_id: Number(params.memberId),
        detection_id: Number(params.detectionId),
        linked_at: new Date().toISOString(),
        linked_by: 'user',
        notes: body.notes || null,
        confidence: body.confidence || 1.0,
      },
      { status: 201 }
    );
  })
);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => server.close());

// Test wrapper with React Query
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe.skip('LinkPersonModal - Full User Flows', () => {
  test('successful link flow: open modal → select member → confirm → see success', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onSuccess = vi.fn();

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={onClose}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={onSuccess}
      />,
      { wrapper: createWrapper() }
    );

    // Modal should be visible
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/link person to household member/i)).toBeInTheDocument();

    // Wait for members to load
    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    // Select a member
    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Jane'));

    // Add optional notes
    const notesInput = screen.getByRole('textbox', { name: /notes/i });
    await user.type(notesInput, 'Confirmed by facial features');

    // Confirm link
    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    // Wait for success
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(
        expect.objectContaining({
          member_id: 2,
          detection_id: 123,
        })
      );
    });

    expect(onClose).toHaveBeenCalled();
  });

  test('cancel flow: open modal → click cancel → modal closes, no API call', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onSuccess = vi.fn();

    let apiCalled = false;
    server.use(
      http.post('/api/household/members/:memberId/detections/:detectionId', () => {
        apiCalled = true;
        return HttpResponse.json({}, { status: 201 });
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={onClose}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={onSuccess}
      />,
      { wrapper: createWrapper() }
    );

    // Wait for members to load
    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    // Click cancel
    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    // Modal should close without API call
    expect(onClose).toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
    expect(apiCalled).toBe(false);
  });

  test('error flow: open modal → select → confirm → API error → show error message', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onSuccess = vi.fn();

    // Mock API error
    server.use(
      http.post('/api/household/members/:memberId/detections/:detectionId', () => {
        return HttpResponse.json(
          { detail: 'Failed to link detection' },
          { status: 500 }
        );
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={onClose}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={onSuccess}
      />,
      { wrapper: createWrapper() }
    );

    // Wait for members to load
    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    // Select member and confirm
    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Mike'));

    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    // Error message should appear
    await waitFor(() => {
      expect(screen.getByText(/failed to link detection/i)).toBeInTheDocument();
    });

    // Modal should remain open
    expect(onClose).not.toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
  });
});

describe.skip('LinkPersonModal - API Integration', () => {
  test('POST request sent with correct member_id and detection_id', async () => {
    const user = userEvent.setup();
    let capturedRequest: { memberId: string; detectionId: string } | null = null;

    server.use(
      http.post('/api/household/members/:memberId/detections/:detectionId', ({ params }) => {
        capturedRequest = {
          memberId: params.memberId as string,
          detectionId: params.detectionId as string,
        };
        return HttpResponse.json({ id: 1 }, { status: 201 });
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Mike'));

    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(capturedRequest).toEqual({
        memberId: '1',
        detectionId: '123',
      });
    });
  });

  test('request includes notes if provided', async () => {
    const user = userEvent.setup();
    let capturedBody: { notes?: string } | null = null;

    server.use(
      http.post('/api/household/members/:memberId/detections/:detectionId', async ({ request }) => {
        capturedBody = (await request.json()) as { notes?: string };
        return HttpResponse.json({ id: 1 }, { status: 201 });
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Mike'));

    const notesInput = screen.getByRole('textbox', { name: /notes/i });
    await user.type(notesInput, 'Test notes');

    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(capturedBody).toEqual(
        expect.objectContaining({
          notes: 'Test notes',
        })
      );
    });
  });

  test('request includes confidence if provided', async () => {
    const user = userEvent.setup();
    let capturedBody: { confidence?: number } | null = null;

    server.use(
      http.post('/api/household/members/:memberId/detections/:detectionId', async ({ request }) => {
        capturedBody = (await request.json()) as { confidence?: number };
        return HttpResponse.json({ id: 1 }, { status: 201 });
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Mike'));

    const confidenceSlider = screen.getByRole('slider', { name: /confidence/i });
    await user.click(confidenceSlider);
    // Simulate setting confidence to 0.8
    await user.keyboard('{ArrowLeft}{ArrowLeft}');

    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(capturedBody).toEqual(
        expect.objectContaining({
          confidence: expect.any(Number),
        })
      );
      expect(capturedBody?.confidence).toBeGreaterThan(0);
      expect(capturedBody?.confidence).toBeLessThanOrEqual(1);
    });
  });

  test('handle 404 when member not found', async () => {
    const user = userEvent.setup();

    server.use(
      http.post('/api/household/members/:memberId/detections/:detectionId', () => {
        return HttpResponse.json(
          { detail: 'Member not found' },
          { status: 404 }
        );
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Mike'));

    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(screen.getByText(/member not found/i)).toBeInTheDocument();
    });
  });

  test('handle 409 when already linked to different member', async () => {
    const user = userEvent.setup();

    server.use(
      http.post('/api/household/members/:memberId/detections/:detectionId', () => {
        return HttpResponse.json(
          { detail: 'Detection already linked to another member' },
          { status: 409 }
        );
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Jane'));

    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(screen.getByText(/already linked to another member/i)).toBeInTheDocument();
    });
  });

  test('handle network timeout', async () => {
    const user = userEvent.setup();

    server.use(
      http.post('/api/household/members/:memberId/detections/:detectionId', async () => {
        await new Promise((resolve) => setTimeout(resolve, 10000));
        return HttpResponse.json({ id: 1 });
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Mike'));

    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    // Should show loading state
    await waitFor(() => {
      expect(confirmButton).toBeDisabled();
    });
  });
});

describe.skip('LinkPersonModal - State Synchronization', () => {
  test('after successful link, event detail refreshes to show linked status', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();

    // Mock event detail refresh
    server.use(
      http.get('/api/events/:eventId', () => {
        return HttpResponse.json({
          ...mockEvent,
          detections: [
            {
              ...mockDetection,
              linked_member: {
                id: 1,
                name: 'Mike',
              },
            },
          ],
        });
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={onSuccess}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Mike'));

    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  test('after link, member detection history includes new detection', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();

    // Mock member detection history
    const newDetections = [
      {
        detection_id: 123,
        event_id: 456,
        camera_name: 'Front Door',
        detected_at: '2025-01-31T10:00:00Z',
        confidence: 0.95,
        linked_at: new Date().toISOString(),
        event_summary: 'Person detected at front door',
        event_risk_score: 35,
      },
    ];

    server.use(
      http.get('/api/household/members/:memberId/detections', () => {
        return HttpResponse.json({
          items: newDetections,
          total: newDetections.length,
          offset: 0,
          limit: 20,
        });
      })
    );

    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={onSuccess}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    const memberSelect = screen.getByLabelText(/select household member/i);
    await user.click(memberSelect);
    await user.click(screen.getByText('Mike'));

    const confirmButton = screen.getByRole('button', { name: /link/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(
        expect.objectContaining({
          detection_id: 123,
          member_id: 1,
        })
      );
    });
  });
});

describe.skip('LinkPersonModal - UI Validation', () => {
  test('link button disabled when no member selected', async () => {
    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    const confirmButton = screen.getByRole('button', { name: /link/i });
    expect(confirmButton).toBeDisabled();
  });

  test('shows member count and roles in dropdown', async () => {
    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByText('Mike')).toBeInTheDocument();
    });

    // All members should be visible with their roles
    expect(screen.getByText(/resident/i)).toBeInTheDocument();
    expect(screen.getByText(/family/i)).toBeInTheDocument();
    expect(screen.getByText(/guest/i)).toBeInTheDocument();
  });

  test('displays detection thumbnail and metadata', () => {
    render(
      <LinkPersonModal
        isOpen={true}
        onClose={vi.fn()}
        detection={mockDetection}
        eventId={mockEvent.id}
        onSuccess={vi.fn()}
      />,
      { wrapper: createWrapper() }
    );

    // Should show detection details
    expect(screen.getByText(/confidence: 0.95/i)).toBeInTheDocument();
    expect(screen.getByText(/detected at/i)).toBeInTheDocument();
  });
});
