/**
 * Tests for VehicleMatchBadge component (NEM-4865)
 *
 * Tests the badge component that displays whether a detected license plate
 * matches a registered household vehicle.
 *
 * @see frontend/src/components/plate-reads/VehicleMatchBadge.tsx
 */

import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, it, expect, beforeEach } from 'vitest';

import { VehicleMatchBadge } from './VehicleMatchBadge';
import { server } from '../../mocks/server';
import { renderWithProviders } from '../../test-utils/renderWithProviders';


import type { RegisteredVehicle, HouseholdMember } from '../../hooks/useHouseholdApi';

// Base URL from environment
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';

// ============================================================================
// Mock Data
// ============================================================================

const mockMember: HouseholdMember = {
  id: 1,
  name: 'John Doe',
  role: 'resident',
  trusted_level: 'full',
  notes: 'Primary resident',
  typical_schedule: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockVehicle: RegisteredVehicle = {
  id: 1,
  description: 'Silver Tesla Model 3',
  vehicle_type: 'car',
  license_plate: 'ABC123',
  color: 'silver',
  owner_id: 1,
  trusted: true,
  created_at: '2024-01-01T00:00:00Z',
};

const mockVehicleNoOwner: RegisteredVehicle = {
  id: 2,
  description: 'Blue Ford F-150',
  vehicle_type: 'truck',
  license_plate: 'TRK456',
  color: 'blue',
  owner_id: null,
  trusted: false,
  created_at: '2024-01-02T00:00:00Z',
};

// ============================================================================
// Tests
// ============================================================================

describe('VehicleMatchBadge', () => {
  beforeEach(() => {
    server.use(
      http.get(`${BASE_URL}/api/household/vehicles`, () => {
        return HttpResponse.json([mockVehicle, mockVehicleNoOwner]);
      }),
      http.get(`${BASE_URL}/api/household/members`, () => {
        return HttpResponse.json([mockMember]);
      })
    );
  });

  describe('known vehicle display', () => {
    it('renders "Known" badge for matched vehicle', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="ABC123" />);

      // Wait for loading to complete
      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge).toHaveClass('bg-green-500/10');
      expect(badge).toHaveClass('text-green-600');
    });

    it('shows vehicle description in title attribute', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="ABC123" showDetails />);

      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge.getAttribute('title')).toContain('Silver Tesla Model 3');
    });

    it('shows owner name in title when showDetails is true', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="ABC123" showDetails />);

      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge.getAttribute('title')).toContain('John Doe');
    });

    it('shows trust level in title for trusted vehicle', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="ABC123" showDetails />);

      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge.getAttribute('title')).toContain('Trusted');
    });

    it('renders Car icon for known vehicle', async () => {
      const { container } = renderWithProviders(<VehicleMatchBadge plateText="ABC123" />);

      await screen.findByText('Known');

      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-car');
    });
  });

  describe('unknown vehicle display', () => {
    it('renders "Unknown" badge for unmatched vehicle', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="UNKNOWN" />);

      await screen.findByText('Unknown');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge).toHaveClass('bg-amber-500/10');
      expect(badge).toHaveClass('text-amber-600');
    });

    it('renders AlertTriangle icon for unknown vehicle', async () => {
      const { container } = renderWithProviders(<VehicleMatchBadge plateText="UNKNOWN" />);

      await screen.findByText('Unknown');

      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg?.classList.toString()).toContain('lucide-triangle-alert');
    });

    it('shows informative title for unknown vehicle', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="UNKNOWN" showDetails />);

      await screen.findByText('Unknown');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge.getAttribute('title')).toContain('Not registered');
    });
  });

  describe('size variants', () => {
    it('renders small size with text-xs', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="ABC123" size="sm" />);

      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge).toHaveClass('text-xs');
      expect(badge).toHaveClass('px-1.5');
    });

    it('renders medium size with text-sm (default)', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="ABC123" />);

      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge).toHaveClass('text-sm');
      expect(badge).toHaveClass('px-2');
    });
  });

  describe('loading state', () => {
    it('shows loading indicator while fetching', async () => {
      server.use(
        http.get(`${BASE_URL}/api/household/vehicles`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json([mockVehicle]);
        })
      );

      const { container } = renderWithProviders(<VehicleMatchBadge plateText="ABC123" />);

      // Should show loading state initially
      const loadingElement = container.querySelector('[data-testid="vehicle-match-loading"]');
      expect(loadingElement).toBeInTheDocument();

      // Wait for data to load
      await screen.findByText('Known');
    });
  });

  describe('edge cases', () => {
    it('handles empty plate text gracefully', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="" />);

      // Should render unknown state for empty plate
      await screen.findByText('Unknown');
    });

    it('handles case-insensitive plate matching', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="abc123" />);

      await screen.findByText('Known');
    });

    it('renders vehicle without owner correctly', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="TRK456" showDetails />);

      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      // Should show vehicle description but no owner
      expect(badge.getAttribute('title')).toContain('Blue Ford F-150');
      expect(badge.getAttribute('title')).not.toContain('Owner:');
    });

    it('handles untrusted vehicle', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="TRK456" showDetails />);

      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge.getAttribute('title')).toContain('Untrusted');
    });
  });

  describe('accessibility', () => {
    it('includes aria-label describing the badge', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="ABC123" />);

      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge.getAttribute('aria-label')).toContain('Known vehicle');
    });

    it('includes role="status" for screen readers', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="ABC123" />);

      await screen.findByText('Known');

      const badge = screen.getByRole('status');
      expect(badge).toBeInTheDocument();
    });
  });

  describe('custom className', () => {
    it('applies custom className to badge', async () => {
      renderWithProviders(<VehicleMatchBadge plateText="ABC123" className="custom-class" />);

      await screen.findByText('Known');

      const badge = screen.getByTestId('vehicle-match-badge');
      expect(badge).toHaveClass('custom-class');
    });
  });

  describe('snapshots', () => {
    it('renders known vehicle badge correctly', async () => {
      const { container } = renderWithProviders(<VehicleMatchBadge plateText="ABC123" />);

      await screen.findByText('Known');

      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders unknown vehicle badge correctly', async () => {
      const { container } = renderWithProviders(<VehicleMatchBadge plateText="UNKNOWN" />);

      await screen.findByText('Unknown');

      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders small size variant correctly', async () => {
      const { container } = renderWithProviders(<VehicleMatchBadge plateText="ABC123" size="sm" />);

      await screen.findByText('Known');

      expect(container.firstChild).toMatchSnapshot();
    });
  });
});
