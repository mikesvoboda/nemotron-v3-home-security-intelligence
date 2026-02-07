import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, it, expect } from 'vitest';

import EventEnrichmentSummary from './EventEnrichmentSummary';

// ============================================================================
// MSW Setup
// ============================================================================

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ============================================================================
// Test Data
// ============================================================================

const mockEnrichmentResponse = {
  event_id: 1,
  enrichments: [
    {
      detection_id: 101,
      enriched_at: '2026-01-15T10:00:00Z',
      license_plate: { detected: true, text: 'ABC-1234', confidence: 0.92 },
      face: { detected: true, count: 2, confidence: 0.88 },
      vehicle: { type: 'sedan', color: 'silver', confidence: 0.91 },
      clothing: {
        upper: 'red jacket',
        lower: 'blue jeans',
        is_suspicious: false,
        is_service_uniform: false,
        has_face_covered: false,
      },
      violence: { detected: false, score: 0.1 },
      pose: null,
      image_quality: { score: 0.85, quality_issues: [], is_blurry: false, is_low_quality: false },
      pet: null,
      errors: [],
    },
    {
      detection_id: 102,
      enriched_at: '2026-01-15T10:00:05Z',
      license_plate: { detected: false },
      face: { detected: false, count: 0 },
      vehicle: null,
      clothing: null,
      violence: { detected: true, score: 0.78 },
      pose: {
        posture: 'crouching',
        alerts: ['crouching'],
        security_alerts: ['crouching'],
        keypoints: [],
        confidence: 0.82,
      },
      image_quality: null,
      pet: { detected: true, type: 'dog', confidence: 0.94 },
      errors: [],
    },
  ],
  count: 2,
  total: 2,
  limit: 200,
  offset: 0,
  has_more: false,
};

// ============================================================================
// Tests
// ============================================================================

describe('EventEnrichmentSummary', () => {
  it('shows loading state initially', () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return new Promise(() => {
          // Never resolve - simulate loading
        });
      })
    );

    render(<EventEnrichmentSummary eventId={1} />, { wrapper: createWrapper() });
    expect(screen.getByText('Loading enrichment data...')).toBeInTheDocument();
  });

  it('renders enrichment summary with aggregated data', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json(mockEnrichmentResponse);
      })
    );

    render(<EventEnrichmentSummary eventId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('event-enrichment-summary')).toBeInTheDocument();
    });

    // Check heading
    expect(screen.getByText('AI Enrichment Summary')).toBeInTheDocument();

    // Check enrichment count
    expect(screen.getByText('2/2 detections enriched')).toBeInTheDocument();
  });

  it('shows threat indicators when violence is detected', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json(mockEnrichmentResponse);
      })
    );

    render(<EventEnrichmentSummary eventId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('threat-indicators')).toBeInTheDocument();
    });

    expect(screen.getByText('Violence Detected')).toBeInTheDocument();
    expect(screen.getByText('78% score')).toBeInTheDocument();
  });

  it('shows pose alerts in threat indicators', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json(mockEnrichmentResponse);
      })
    );

    render(<EventEnrichmentSummary eventId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('crouching')).toBeInTheDocument();
    });
  });

  it('shows face detection count', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json(mockEnrichmentResponse);
      })
    );

    render(<EventEnrichmentSummary eventId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Faces Detected')).toBeInTheDocument();
    });
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('shows vehicle details', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json(mockEnrichmentResponse);
      })
    );

    render(<EventEnrichmentSummary eventId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });
    expect(screen.getByText('silver sedan')).toBeInTheDocument();
  });

  it('shows license plate text', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json(mockEnrichmentResponse);
      })
    );

    render(<EventEnrichmentSummary eventId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('License Plate')).toBeInTheDocument();
    });
    expect(screen.getByText('ABC-1234')).toBeInTheDocument();
  });

  it('shows pet detection', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json(mockEnrichmentResponse);
      })
    );

    render(<EventEnrichmentSummary eventId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Pet')).toBeInTheDocument();
    });
    expect(screen.getByText('dog')).toBeInTheDocument();
  });

  it('shows clothing analysis', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json(mockEnrichmentResponse);
      })
    );

    render(<EventEnrichmentSummary eventId={1} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('clothing-details')).toBeInTheDocument();
    });
    expect(screen.getByText(/red jacket/)).toBeInTheDocument();
  });

  it('returns null when no enrichments', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json({
          event_id: 1,
          enrichments: [],
          count: 0,
          total: 0,
          limit: 200,
          offset: 0,
          has_more: false,
        });
      })
    );

    const { container } = render(<EventEnrichmentSummary eventId={1} />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(screen.queryByText('Loading enrichment data...')).not.toBeInTheDocument();
    });

    expect(container.innerHTML).toBe('');
  });

  it('does not render summary when enrichments have no meaningful data', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json({
          event_id: 1,
          enrichments: [
            {
              detection_id: 101,
              enriched_at: null,
              license_plate: { detected: false },
              face: { detected: false, count: 0 },
              vehicle: null,
              clothing: null,
              violence: { detected: false, score: 0 },
              pose: null,
              image_quality: null,
              pet: null,
              errors: [],
            },
          ],
          count: 1,
          total: 1,
          limit: 200,
          offset: 0,
          has_more: false,
        });
      })
    );

    const { container } = render(<EventEnrichmentSummary eventId={1} />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(screen.queryByText('Loading enrichment data...')).not.toBeInTheDocument();
    });

    // Should render nothing when all enrichments are empty
    expect(container.querySelector('[data-testid="event-enrichment-summary"]')).toBeNull();
  });

  it('applies custom className', async () => {
    server.use(
      http.get('/api/events/1/enrichments', () => {
        return HttpResponse.json(mockEnrichmentResponse);
      })
    );

    render(<EventEnrichmentSummary eventId={1} className="my-custom-class" />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      const summary = screen.getByTestId('event-enrichment-summary');
      expect(summary).toHaveClass('my-custom-class');
    });
  });
});
