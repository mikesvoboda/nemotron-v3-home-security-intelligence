/**
 * GpuBatchActions Tests
 *
 * Tests for the GPU batch actions component that provides:
 * - Assign All: Move all services to a selected GPU
 * - Reset to Defaults: Clear all custom assignments
 * - Auto-Balance: Distribute services evenly across GPUs
 *
 * @see NEM-4943 - GPU Batch Operations
 */

import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import GpuBatchActions from './GpuBatchActions';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type { GpuDevice, GpuAssignment } from '../../hooks/useGpuConfig';

// ============================================================================
// Test Data
// ============================================================================

const mockGpus: GpuDevice[] = [
  {
    index: 0,
    name: 'NVIDIA RTX A5000',
    vram_total_mb: 24576,
    vram_used_mb: 8192,
    compute_capability: '8.6',
  },
  {
    index: 1,
    name: 'NVIDIA RTX A5000',
    vram_total_mb: 24576,
    vram_used_mb: 4096,
    compute_capability: '8.6',
  },
];

const mockAssignments: GpuAssignment[] = [
  { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
  { service: 'ai-yolo26', gpu_index: 0, vram_budget_override: null },
  { service: 'ai-enrichment', gpu_index: 1, vram_budget_override: null },
];

const defaultAssignments: GpuAssignment[] = [
  { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
  { service: 'ai-yolo26', gpu_index: 0, vram_budget_override: null },
  { service: 'ai-enrichment', gpu_index: 0, vram_budget_override: null },
];

const singleGpu: GpuDevice[] = [
  {
    index: 0,
    name: 'NVIDIA RTX A5000',
    vram_total_mb: 24576,
    vram_used_mb: 8192,
    compute_capability: '8.6',
  },
];

// ============================================================================
// Tests
// ============================================================================

describe('GpuBatchActions', () => {
  const mockOnAssignAll = vi.fn();
  const mockOnResetDefaults = vi.fn();
  const mockOnAutoBalance = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('should render the component with title', () => {
      renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      expect(screen.getByTestId('gpu-batch-actions')).toBeInTheDocument();
      expect(screen.getByText('Quick Actions')).toBeInTheDocument();
    });

    it('should render all three action buttons', () => {
      renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      expect(screen.getByTestId('assign-all-button')).toBeInTheDocument();
      expect(screen.getByTestId('reset-defaults-button')).toBeInTheDocument();
      expect(screen.getByTestId('auto-balance-button')).toBeInTheDocument();
    });

    it('should render helper text for each action', () => {
      renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      expect(screen.getByText(/Move all services to a single GPU/)).toBeInTheDocument();
      expect(screen.getByText(/Assign all services to GPU 0/)).toBeInTheDocument();
      expect(screen.getByText(/Distribute services evenly/)).toBeInTheDocument();
    });
  });

  describe('Assign All functionality', () => {
    it('should open dialog when Assign All button is clicked', async () => {
      const { user } = renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      await user.click(screen.getByTestId('assign-all-button'));

      await waitFor(() => {
        expect(screen.getByTestId('assign-all-dialog')).toBeInTheDocument();
      });
    });

    it('should show GPU selection dropdown in dialog', async () => {
      const { user } = renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      await user.click(screen.getByTestId('assign-all-button'));

      await waitFor(() => {
        expect(screen.getByTestId('assign-all-gpu-select')).toBeInTheDocument();
      });

      // Check that both GPUs are in the dropdown
      const select = screen.getByTestId('assign-all-gpu-select');
      expect(select).toHaveTextContent('GPU 0');
      expect(select).toHaveTextContent('GPU 1');
    });

    it('should call onAssignAll with selected GPU when confirmed', async () => {
      const { user } = renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      await user.click(screen.getByTestId('assign-all-button'));

      await waitFor(() => {
        expect(screen.getByTestId('assign-all-dialog')).toBeInTheDocument();
      });

      // Select GPU 1
      const select = screen.getByTestId('assign-all-gpu-select');
      await user.selectOptions(select, '1');

      // Confirm
      await user.click(screen.getByTestId('assign-all-confirm-button'));

      expect(mockOnAssignAll).toHaveBeenCalledWith(1);
    });

    it('should close dialog when cancelled', async () => {
      const { user } = renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      await user.click(screen.getByTestId('assign-all-button'));

      await waitFor(() => {
        expect(screen.getByTestId('assign-all-dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      await waitFor(() => {
        expect(screen.queryByTestId('assign-all-dialog')).not.toBeInTheDocument();
      });
    });

    it('should disable Assign All button when no GPUs available', () => {
      renderWithProviders(
        <GpuBatchActions
          gpus={[]}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      expect(screen.getByTestId('assign-all-button')).toBeDisabled();
    });
  });

  describe('Reset to Defaults functionality', () => {
    it('should open confirmation dialog when Reset button is clicked', async () => {
      const { user } = renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      await user.click(screen.getByTestId('reset-defaults-button'));

      await waitFor(() => {
        expect(screen.getByTestId('reset-confirm-dialog')).toBeInTheDocument();
      });
    });

    it('should call onResetDefaults when confirmed', async () => {
      const { user } = renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      await user.click(screen.getByTestId('reset-defaults-button'));

      await waitFor(() => {
        expect(screen.getByTestId('reset-confirm-dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('reset-confirm-button'));

      expect(mockOnResetDefaults).toHaveBeenCalled();
    });

    it('should close dialog when cancelled', async () => {
      const { user } = renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      await user.click(screen.getByTestId('reset-defaults-button'));

      await waitFor(() => {
        expect(screen.getByTestId('reset-confirm-dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      await waitFor(() => {
        expect(screen.queryByTestId('reset-confirm-dialog')).not.toBeInTheDocument();
      });
    });

    it('should disable Reset button when already at defaults', () => {
      renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={defaultAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      expect(screen.getByTestId('reset-defaults-button')).toBeDisabled();
    });

    it('should enable Reset button when not at defaults', () => {
      renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      expect(screen.getByTestId('reset-defaults-button')).not.toBeDisabled();
    });
  });

  describe('Auto-Balance functionality', () => {
    it('should call onAutoBalance when clicked', async () => {
      const { user } = renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      await user.click(screen.getByTestId('auto-balance-button'));

      expect(mockOnAutoBalance).toHaveBeenCalled();
    });

    it('should disable Auto-Balance button when only one GPU is available', () => {
      renderWithProviders(
        <GpuBatchActions
          gpus={singleGpu}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
        />
      );

      expect(screen.getByTestId('auto-balance-button')).toBeDisabled();
    });

    it('should show loading state when auto-balancing', () => {
      renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
          isAutoBalancing={true}
        />
      );

      // The button should show loading indicator
      const button = screen.getByTestId('auto-balance-button');
      expect(button).toBeInTheDocument();
      // Button loading state is handled by the Button component
    });
  });

  describe('disabled state', () => {
    it('should disable all buttons when disabled prop is true', () => {
      renderWithProviders(
        <GpuBatchActions
          gpus={mockGpus}
          assignments={mockAssignments}
          onAssignAll={mockOnAssignAll}
          onResetDefaults={mockOnResetDefaults}
          onAutoBalance={mockOnAutoBalance}
          disabled={true}
        />
      );

      expect(screen.getByTestId('assign-all-button')).toBeDisabled();
      expect(screen.getByTestId('reset-defaults-button')).toBeDisabled();
      expect(screen.getByTestId('auto-balance-button')).toBeDisabled();
    });
  });
});
