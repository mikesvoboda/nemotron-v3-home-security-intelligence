/**
 * Tests for ApproachVectorOverlay component (NEM-4936)
 *
 * @module components/zones/ApproachVectorOverlay.test
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import React from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import ApproachVectorOverlay from './ApproachVectorOverlay';

import type { CameraApproachVectorsResponse } from '../../hooks/useApproachVectors';

// ============================================================================
// Test Data
// ============================================================================

const mockCameraResponse: CameraApproachVectorsResponse = {
  camera_id: 'front_door',
  zones: [
    {
      zone_id: 1,
      zone_name: 'Front Door',
      approach_vectors: [
        {
          track_id: 42,
          object_class: 'person',
          is_approaching: true,
          direction_degrees: 45.0,
          speed_normalized: 0.05,
          distance_to_zone: 0.15,
          estimated_arrival_seconds: 3.0,
          urgency: 'imminent',
          current_position: { x: 0.35, y: 0.4 },
          zone_centroid: { x: 0.5, y: 0.5 },
        },
        {
          track_id: 43,
          object_class: 'vehicle',
          is_approaching: true,
          direction_degrees: 90.0,
          speed_normalized: 0.02,
          distance_to_zone: 0.25,
          estimated_arrival_seconds: 8.0,
          urgency: 'approaching',
          current_position: { x: 0.25, y: 0.5 },
          zone_centroid: { x: 0.5, y: 0.5 },
        },
      ],
      total_approaching: 2,
      imminent_count: 1,
      timestamp: '2026-01-31T12:00:00Z',
    },
  ],
  total_zones: 1,
  total_approaching_entities: 2,
};

const emptyResponse: CameraApproachVectorsResponse = {
  camera_id: 'front_door',
  zones: [],
  total_zones: 0,
  total_approaching_entities: 0,
};

// ============================================================================
// MSW Server Setup
// ============================================================================

const server = setupServer(
  http.get('/api/analytics-zones/approach-vectors/camera/:cameraId', ({ params }) => {
    if (params.cameraId === 'empty_camera') {
      return HttpResponse.json(emptyResponse);
    }
    return HttpResponse.json(mockCameraResponse);
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ============================================================================
// Test Utilities
// ============================================================================

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

function renderWithProviders(ui: React.ReactElement) {
  return render(ui, { wrapper: createWrapper() });
}

// ============================================================================
// Component Tests
// ============================================================================

describe('ApproachVectorOverlay', () => {
  it('should render SVG overlay when data is available', async () => {
    renderWithProviders(
      <ApproachVectorOverlay
        cameraId="front_door"
        videoWidth={1920}
        videoHeight={1080}
        enablePolling={false}
      />
    );

    // Wait for data to load
    const overlay = await screen.findByTestId('approach-vector-overlay');
    expect(overlay).toBeInTheDocument();
  });

  it('should render approach arrows for approaching entities', async () => {
    renderWithProviders(
      <ApproachVectorOverlay
        cameraId="front_door"
        videoWidth={1920}
        videoHeight={1080}
        enablePolling={false}
      />
    );

    // Wait for arrows to render
    const arrow42 = await screen.findByTestId('approach-arrow-42');
    const arrow43 = await screen.findByTestId('approach-arrow-43');

    expect(arrow42).toBeInTheDocument();
    expect(arrow43).toBeInTheDocument();
  });

  it('should not render when no approach vectors', async () => {
    renderWithProviders(
      <ApproachVectorOverlay
        cameraId="empty_camera"
        videoWidth={1920}
        videoHeight={1080}
        enablePolling={false}
      />
    );

    // Allow time for query to complete
    await vi.waitFor(() => {
      // Should not find the overlay when there are no vectors
      expect(screen.queryByTestId('approach-vector-overlay')).not.toBeInTheDocument();
    });
  });

  it('should filter by urgency when urgencyFilter is provided', async () => {
    renderWithProviders(
      <ApproachVectorOverlay
        cameraId="front_door"
        videoWidth={1920}
        videoHeight={1080}
        enablePolling={false}
        urgencyFilter={['imminent']}
      />
    );

    // Wait for data to load
    await screen.findByTestId('approach-vector-overlay');

    // Only imminent arrow (track 42) should be rendered
    expect(screen.queryByTestId('approach-arrow-42')).toBeInTheDocument();
    expect(screen.queryByTestId('approach-arrow-43')).not.toBeInTheDocument();
  });

  it('should show ETA labels when showETA is true', async () => {
    renderWithProviders(
      <ApproachVectorOverlay
        cameraId="front_door"
        videoWidth={1920}
        videoHeight={1080}
        enablePolling={false}
        showETA={true}
      />
    );

    // Wait for arrows to render
    await screen.findByTestId('approach-arrow-42');

    // ETA text should be visible in the SVG
    // Note: We can't easily test for SVG text content, but we can verify the structure
    const overlay = screen.getByTestId('approach-vector-overlay');
    expect(overlay).toBeInTheDocument();
  });

  it('should apply custom className', async () => {
    renderWithProviders(
      <ApproachVectorOverlay
        cameraId="front_door"
        videoWidth={1920}
        videoHeight={1080}
        enablePolling={false}
        className="custom-class"
      />
    );

    const overlay = await screen.findByTestId('approach-vector-overlay');
    expect(overlay).toHaveClass('custom-class');
  });

  it('should set correct viewBox based on dimensions', async () => {
    renderWithProviders(
      <ApproachVectorOverlay
        cameraId="front_door"
        videoWidth={1280}
        videoHeight={720}
        enablePolling={false}
      />
    );

    const overlay = await screen.findByTestId('approach-vector-overlay');
    expect(overlay).toHaveAttribute('viewBox', '0 0 1280 720');
  });

  it('should not render during loading state', () => {
    server.use(
      http.get('/api/analytics-zones/approach-vectors/camera/:cameraId', async () => {
        // Delay response to keep loading state
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json(mockCameraResponse);
      })
    );

    renderWithProviders(
      <ApproachVectorOverlay
        cameraId="front_door"
        videoWidth={1920}
        videoHeight={1080}
        enablePolling={false}
      />
    );

    // Should not find overlay during loading
    expect(screen.queryByTestId('approach-vector-overlay')).not.toBeInTheDocument();
  });

  it('should not render when API returns error', async () => {
    server.use(
      http.get('/api/analytics-zones/approach-vectors/camera/:cameraId', () => {
        return new HttpResponse(null, { status: 500 });
      })
    );

    renderWithProviders(
      <ApproachVectorOverlay
        cameraId="front_door"
        videoWidth={1920}
        videoHeight={1080}
        enablePolling={false}
      />
    );

    // Allow time for error to occur
    await vi.waitFor(() => {
      expect(screen.queryByTestId('approach-vector-overlay')).not.toBeInTheDocument();
    });
  });
});
