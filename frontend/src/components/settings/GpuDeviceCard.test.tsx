/**
 * GpuDeviceCard Tests
 *
 * Tests for the GPU Device Card component that displays:
 * - GPU name and index
 * - VRAM usage visualization
 * - Assigned services list
 * - Compute capability
 *
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import GpuDeviceCard from './GpuDeviceCard';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type { GpuDevice, GpuAssignment } from '../../hooks/useGpuConfig';

// ============================================================================
// Test Data
// ============================================================================

const mockGpu: GpuDevice = {
  index: 0,
  name: 'NVIDIA RTX A5000',
  vram_total_mb: 24576,
  vram_used_mb: 8192,
  compute_capability: '8.6',
};

const mockAssignments: GpuAssignment[] = [
  { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
  { service: 'ai-yolo26', gpu_index: 0, vram_budget_override: null },
];

// ============================================================================
// Tests
// ============================================================================

describe('GpuDeviceCard', () => {
  describe('rendering', () => {
    it('should render GPU name', () => {
      renderWithProviders(<GpuDeviceCard gpu={mockGpu} assignedServices={mockAssignments} />);

      expect(screen.getByText('NVIDIA RTX A5000')).toBeInTheDocument();
    });

    it('should render GPU index', () => {
      renderWithProviders(<GpuDeviceCard gpu={mockGpu} assignedServices={mockAssignments} />);

      expect(screen.getByText('GPU 0')).toBeInTheDocument();
    });

    it('should render compute capability', () => {
      renderWithProviders(<GpuDeviceCard gpu={mockGpu} assignedServices={mockAssignments} />);

      expect(screen.getByText('8.6')).toBeInTheDocument();
    });

    it('should render data-testid with gpu index', () => {
      renderWithProviders(<GpuDeviceCard gpu={mockGpu} assignedServices={mockAssignments} />);

      expect(screen.getByTestId('gpu-device-card-0')).toBeInTheDocument();
    });
  });

  describe('VRAM usage', () => {
    it('should display VRAM used and total', () => {
      renderWithProviders(<GpuDeviceCard gpu={mockGpu} assignedServices={mockAssignments} />);

      // 8192 MB = 8.0 GB, 24576 MB = 24.0 GB
      expect(screen.getByText('8.0 GB / 24.0 GB')).toBeInTheDocument();
    });

    it('should display VRAM available', () => {
      renderWithProviders(<GpuDeviceCard gpu={mockGpu} assignedServices={mockAssignments} />);

      // 24576 - 8192 = 16384 MB = 16.0 GB
      expect(screen.getByText(/Available: 16.0 GB/)).toBeInTheDocument();
    });

    it('should show low usage status for <50%', () => {
      const lowUsageGpu: GpuDevice = {
        ...mockGpu,
        vram_used_mb: 4000, // ~16% usage
      };

      renderWithProviders(<GpuDeviceCard gpu={lowUsageGpu} assignedServices={mockAssignments} />);

      const indicator = screen.getByTestId('gpu-usage-indicator-0');
      expect(indicator).toHaveAttribute('data-status', 'low');
    });

    it('should show moderate usage status for 50-80%', () => {
      const moderateUsageGpu: GpuDevice = {
        ...mockGpu,
        vram_used_mb: 15000, // ~61% usage
      };

      renderWithProviders(
        <GpuDeviceCard gpu={moderateUsageGpu} assignedServices={mockAssignments} />
      );

      const indicator = screen.getByTestId('gpu-usage-indicator-0');
      expect(indicator).toHaveAttribute('data-status', 'moderate');
    });

    it('should show high usage status for 80-90%', () => {
      const highUsageGpu: GpuDevice = {
        ...mockGpu,
        vram_used_mb: 21000, // ~85% usage
      };

      renderWithProviders(<GpuDeviceCard gpu={highUsageGpu} assignedServices={mockAssignments} />);

      const indicator = screen.getByTestId('gpu-usage-indicator-0');
      expect(indicator).toHaveAttribute('data-status', 'high');
    });

    it('should show critical usage status for >90%', () => {
      const criticalUsageGpu: GpuDevice = {
        ...mockGpu,
        vram_used_mb: 23000, // ~94% usage
      };

      renderWithProviders(
        <GpuDeviceCard gpu={criticalUsageGpu} assignedServices={mockAssignments} />
      );

      const indicator = screen.getByTestId('gpu-usage-indicator-0');
      expect(indicator).toHaveAttribute('data-status', 'critical');
    });
  });

  describe('assigned services', () => {
    it('should display assigned services', () => {
      renderWithProviders(<GpuDeviceCard gpu={mockGpu} assignedServices={mockAssignments} />);

      expect(screen.getByText('ai-llm')).toBeInTheDocument();
      expect(screen.getByText('ai-yolo26')).toBeInTheDocument();
    });

    it('should show empty message when no services assigned', () => {
      renderWithProviders(<GpuDeviceCard gpu={mockGpu} assignedServices={[]} />);

      expect(screen.getByText('No services assigned')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('should show loading skeleton when isLoading is true', () => {
      renderWithProviders(
        <GpuDeviceCard gpu={mockGpu} assignedServices={mockAssignments} isLoading />
      );

      expect(screen.getByTestId('gpu-card-loading-skeleton')).toBeInTheDocument();
    });
  });

  describe('different GPU indices', () => {
    it('should handle GPU index 1', () => {
      const gpu1: GpuDevice = {
        ...mockGpu,
        index: 1,
      };

      renderWithProviders(<GpuDeviceCard gpu={gpu1} assignedServices={[]} />);

      expect(screen.getByTestId('gpu-device-card-1')).toBeInTheDocument();
      expect(screen.getByText('GPU 1')).toBeInTheDocument();
    });
  });
});
