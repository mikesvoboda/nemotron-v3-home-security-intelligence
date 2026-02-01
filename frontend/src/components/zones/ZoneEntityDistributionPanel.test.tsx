/**
 * Tests for ZoneEntityDistributionPanel component (NEM-4937)
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { ZoneEntityDistributionPanel } from './ZoneEntityDistributionPanel';
import { createQueryWrapper } from '../../test-utils';

import type { ZoneEntityDistributionResponse } from '../../hooks/useZoneEntityDistribution';

// ============================================================================
// Test Data
// ============================================================================

const mockResponse: ZoneEntityDistributionResponse = {
  zones: [
    {
      zone_id: 1,
      zone_name: 'Front Yard',
      total_entities: 64,
      entity_types: [
        { entity_type: 'person', count: 42, percentage: 65.63 },
        { entity_type: 'vehicle', count: 15, percentage: 23.44 },
        { entity_type: 'dog', count: 7, percentage: 10.94 },
      ],
    },
    {
      zone_id: 2,
      zone_name: 'Back Yard',
      total_entities: 32,
      entity_types: [
        { entity_type: 'person', count: 20, percentage: 62.5 },
        { entity_type: 'cat', count: 12, percentage: 37.5 },
      ],
    },
  ],
  grand_total: 96,
  start_time: '2026-01-31T00:00:00Z',
  end_time: '2026-01-31T23:59:59Z',
};

const emptyResponse: ZoneEntityDistributionResponse = {
  zones: [],
  grand_total: 0,
  start_time: '2026-01-31T00:00:00Z',
  end_time: '2026-01-31T23:59:59Z',
};

const zeroEntityResponse: ZoneEntityDistributionResponse = {
  zones: [
    {
      zone_id: 1,
      zone_name: 'Empty Zone',
      total_entities: 0,
      entity_types: [],
    },
  ],
  grand_total: 0,
  start_time: '2026-01-31T00:00:00Z',
  end_time: '2026-01-31T23:59:59Z',
};

// ============================================================================
// Mocks
// ============================================================================

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch);
  mockFetch.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ============================================================================
// Tests
// ============================================================================

describe('ZoneEntityDistributionPanel', () => {
  it('should show loading state initially', () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves

    render(<ZoneEntityDistributionPanel />, { wrapper: createQueryWrapper() });

    expect(screen.getByTestId('entity-distribution-panel-loading')).toBeInTheDocument();
  });

  it('should render zone distribution cards after loading', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    render(<ZoneEntityDistributionPanel />, { wrapper: createQueryWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('entity-distribution-panel')).toBeInTheDocument();
    });

    expect(screen.getByText('Entity Distribution by Zone')).toBeInTheDocument();
    expect(screen.getByText('96')).toBeInTheDocument(); // Grand total
    expect(screen.getByText('2')).toBeInTheDocument(); // Zone count
    expect(screen.getByTestId('entity-distribution-card-1')).toBeInTheDocument();
    expect(screen.getByTestId('entity-distribution-card-2')).toBeInTheDocument();
  });

  it('should show empty state when no zones', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(emptyResponse),
    });

    render(<ZoneEntityDistributionPanel />, { wrapper: createQueryWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('entity-distribution-panel-empty')).toBeInTheDocument();
    });

    expect(screen.getByText('No polygon zones configured')).toBeInTheDocument();
  });

  it('should show no activity message when grand total is zero', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(zeroEntityResponse),
    });

    render(<ZoneEntityDistributionPanel />, { wrapper: createQueryWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('entity-distribution-panel')).toBeInTheDocument();
    });

    expect(screen.getByText('No entity activity detected in the last 24 hours.')).toBeInTheDocument();
  });

  it('should show error state on fetch failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      statusText: 'Internal Server Error',
    });

    render(<ZoneEntityDistributionPanel />, { wrapper: createQueryWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('entity-distribution-panel-error')).toBeInTheDocument();
    });

    expect(screen.getByText(/Failed to load entity distribution/)).toBeInTheDocument();
    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });

  it('should call onZoneSelect when zone card is clicked', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const handleZoneSelect = vi.fn();
    render(<ZoneEntityDistributionPanel onZoneSelect={handleZoneSelect} />, {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('entity-distribution-panel')).toBeInTheDocument();
    });

    const firstCard = screen.getByTestId('entity-distribution-card-1');
    fireEvent.click(firstCard);

    expect(handleZoneSelect).toHaveBeenCalledWith(1);
  });

  it('should highlight selected zone', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    render(<ZoneEntityDistributionPanel selectedZoneId={1} onZoneSelect={() => {}} />, {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('entity-distribution-panel')).toBeInTheDocument();
    });

    const selectedCard = screen.getByTestId('entity-distribution-card-1');
    expect(selectedCard).toHaveClass('border-[#76B900]');
  });

  it('should refetch on refresh button click', async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

    render(<ZoneEntityDistributionPanel />, { wrapper: createQueryWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId('entity-distribution-panel')).toBeInTheDocument();
    });

    const refreshButton = screen.getByTestId('refresh-button');
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });

  it('should pass cameraId to API call', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    render(<ZoneEntityDistributionPanel cameraId="front_door" />, {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('entity-distribution-panel')).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/analytics-zones/entity-distribution?camera_id=front_door'
    );
  });

  it('should apply custom className', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    render(<ZoneEntityDistributionPanel className="custom-class" />, {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByTestId('entity-distribution-panel')).toBeInTheDocument();
    });

    expect(screen.getByTestId('entity-distribution-panel')).toHaveClass('custom-class');
  });
});
