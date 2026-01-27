/**
 * GpuAssignmentTable Tests
 *
 * Tests for the GPU Assignment Table component that displays:
 * - Service names and GPU assignment dropdowns
 * - VRAM requirements
 * - Service health status
 *
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import GpuAssignmentTable from './GpuAssignmentTable';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type { GpuDevice, GpuAssignment, ServiceHealthStatus } from '../../hooks/useGpuConfig';

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

const mockServiceStatuses: ServiceHealthStatus[] = [
  { name: 'ai-llm', status: 'running', health: 'healthy', gpu_index: 0, restart_status: null },
  { name: 'ai-yolo26', status: 'running', health: 'healthy', gpu_index: 0, restart_status: null },
  {
    name: 'ai-enrichment',
    status: 'running',
    health: 'unhealthy',
    gpu_index: 1,
    restart_status: null,
  },
];

// ============================================================================
// Tests
// ============================================================================

describe('GpuAssignmentTable', () => {
  const defaultProps = {
    assignments: mockAssignments,
    gpus: mockGpus,
    serviceStatuses: mockServiceStatuses,
    strategy: 'manual',
    onAssignmentChange: vi.fn(),
  };

  describe('rendering', () => {
    it('should render table container', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      expect(screen.getByTestId('gpu-assignment-table')).toBeInTheDocument();
    });

    it('should render title', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      expect(screen.getByText('Service Assignments')).toBeInTheDocument();
    });

    it('should render table headers', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      expect(screen.getByText('Service')).toBeInTheDocument();
      expect(screen.getByText('Current GPU')).toBeInTheDocument();
      expect(screen.getByText('VRAM Required')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
    });

    it('should render all service rows', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      expect(screen.getByTestId('assignment-row-ai-llm')).toBeInTheDocument();
      expect(screen.getByTestId('assignment-row-ai-yolo26')).toBeInTheDocument();
      expect(screen.getByTestId('assignment-row-ai-enrichment')).toBeInTheDocument();
    });
  });

  describe('GPU assignment dropdown', () => {
    it('should render GPU select for each service', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      expect(screen.getByTestId('gpu-select-ai-llm')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-select-ai-yolo26')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-select-ai-enrichment')).toBeInTheDocument();
    });

    it('should have Auto option in dropdown', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      const select = screen.getByTestId('gpu-select-ai-llm');
      expect(select).toHaveTextContent('Auto');
    });

    it('should have GPU options in dropdown', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      const select = screen.getByTestId('gpu-select-ai-llm');
      expect(select).toHaveTextContent('GPU 0: NVIDIA RTX A5000');
      expect(select).toHaveTextContent('GPU 1: NVIDIA RTX A5000');
    });

    it('should select the assigned GPU', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      const select = screen.getByTestId('gpu-select-ai-llm');
      expect(select).toHaveValue('0');
    });

    it('should enable dropdown when strategy is manual', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} strategy="manual" />);

      expect(screen.getByTestId('gpu-select-ai-llm')).not.toBeDisabled();
    });

    it('should disable dropdown when strategy is not manual', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} strategy="balanced" />);

      expect(screen.getByTestId('gpu-select-ai-llm')).toBeDisabled();
    });

    it('should call onAssignmentChange when dropdown changes', async () => {
      const onAssignmentChange = vi.fn();
      const { user } = renderWithProviders(
        <GpuAssignmentTable {...defaultProps} onAssignmentChange={onAssignmentChange} />
      );

      const select = screen.getByTestId('gpu-select-ai-llm');
      await user.selectOptions(select, '1');

      expect(onAssignmentChange).toHaveBeenCalledWith('ai-llm', 1);
    });

    it('should call onAssignmentChange with null when Auto is selected', async () => {
      const onAssignmentChange = vi.fn();
      const { user } = renderWithProviders(
        <GpuAssignmentTable {...defaultProps} onAssignmentChange={onAssignmentChange} />
      );

      const select = screen.getByTestId('gpu-select-ai-llm');
      await user.selectOptions(select, 'auto');

      expect(onAssignmentChange).toHaveBeenCalledWith('ai-llm', null);
    });
  });

  describe('VRAM requirements', () => {
    it('should display default VRAM requirements', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      // Default VRAM for ai-llm is 8.0 GB
      expect(screen.getByText('8.0 GB')).toBeInTheDocument();
      // Default VRAM for ai-yolo26 is 4.0 GB
      expect(screen.getByText('4.0 GB')).toBeInTheDocument();
      // Default VRAM for ai-enrichment is 3.5 GB
      expect(screen.getByText('3.5 GB')).toBeInTheDocument();
    });

    it('should use override VRAM when specified', () => {
      const assignmentsWithOverride: GpuAssignment[] = [
        { service: 'ai-llm', gpu_index: 0, vram_budget_override: 12.0 },
      ];

      renderWithProviders(
        <GpuAssignmentTable {...defaultProps} assignments={assignmentsWithOverride} />
      );

      expect(screen.getByText('12.0 GB')).toBeInTheDocument();
    });
  });

  describe('service status', () => {
    it('should display healthy status badge', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      expect(screen.getByTestId('status-badge-ai-llm')).toHaveTextContent('Healthy');
    });

    it('should display unhealthy status badge', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      expect(screen.getByTestId('status-badge-ai-enrichment')).toHaveTextContent('Unhealthy');
    });

    it('should display restart status when restarting', () => {
      const statusesWithRestart: ServiceHealthStatus[] = [
        {
          name: 'ai-llm',
          status: 'running',
          health: 'healthy',
          gpu_index: 0,
          restart_status: 'Restarting',
        },
      ];

      renderWithProviders(
        <GpuAssignmentTable {...defaultProps} serviceStatuses={statusesWithRestart} />
      );

      expect(screen.getByTestId('status-badge-ai-llm')).toHaveTextContent('Restarting');
    });
  });

  describe('pending changes indicator', () => {
    it('should show unsaved changes badge when hasPendingChanges is true', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} hasPendingChanges />);

      expect(screen.getByText('Unsaved Changes')).toBeInTheDocument();
    });

    it('should not show badge when no pending changes', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} hasPendingChanges={false} />);

      expect(screen.queryByText('Unsaved Changes')).not.toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('should show loading rows when isLoading is true', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} isLoading />);

      // When loading, service rows should not be visible
      expect(screen.queryByTestId('assignment-row-ai-llm')).not.toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('should show empty message when no assignments', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} assignments={[]} />);

      expect(screen.getByText('No services configured')).toBeInTheDocument();
    });
  });

  describe('non-manual strategy note', () => {
    it('should show note when strategy is not manual', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} strategy="balanced" />);

      expect(screen.getByText(/GPU assignments are managed automatically/)).toBeInTheDocument();
    });

    it('should not show note when strategy is manual', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} strategy="manual" />);

      expect(
        screen.queryByText(/GPU assignments are managed automatically/)
      ).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('should have aria-label on GPU selects', () => {
      renderWithProviders(<GpuAssignmentTable {...defaultProps} />);

      const select = screen.getByTestId('gpu-select-ai-llm');
      expect(select).toHaveAttribute('aria-label', 'GPU assignment for ai-llm');
    });
  });

  describe('VRAM budget override editing', () => {
    const onVramOverrideChangeMock = vi.fn();

    it('should render VRAM override input in manual mode', () => {
      renderWithProviders(
        <GpuAssignmentTable
          {...defaultProps}
          strategy="manual"
          onVramOverrideChange={onVramOverrideChangeMock}
        />
      );

      expect(screen.getByTestId('vram-override-ai-llm')).toBeInTheDocument();
    });

    it('should not render VRAM override input in non-manual mode', () => {
      renderWithProviders(
        <GpuAssignmentTable
          {...defaultProps}
          strategy="balanced"
          onVramOverrideChange={onVramOverrideChangeMock}
        />
      );

      expect(screen.queryByTestId('vram-override-ai-llm')).not.toBeInTheDocument();
    });

    it('should show current VRAM value in input', () => {
      const assignmentsWithOverride: GpuAssignment[] = [
        { service: 'ai-llm', gpu_index: 0, vram_budget_override: 10.5 },
      ];

      renderWithProviders(
        <GpuAssignmentTable
          {...defaultProps}
          assignments={assignmentsWithOverride}
          onVramOverrideChange={onVramOverrideChangeMock}
        />
      );

      const input = screen.getByTestId('vram-override-ai-llm');
      // Input type="number" returns value as number
      expect(input).toHaveValue(10.5);
    });

    it('should show default VRAM when no override', () => {
      renderWithProviders(
        <GpuAssignmentTable {...defaultProps} onVramOverrideChange={onVramOverrideChangeMock} />
      );

      const input = screen.getByTestId('vram-override-ai-llm');
      // Default for ai-llm is 8.0 GB, value may be '8' or '8.0'
      expect(input).toHaveValue(8);
    });

    it('should call onVramOverrideChange when input changes', async () => {
      const onVramOverrideChange = vi.fn();
      const { user } = renderWithProviders(
        <GpuAssignmentTable {...defaultProps} onVramOverrideChange={onVramOverrideChange} />
      );

      const input = screen.getByTestId('vram-override-ai-llm');
      await user.clear(input);
      await user.type(input, '12.5');
      await user.tab(); // Trigger blur to commit change

      expect(onVramOverrideChange).toHaveBeenCalledWith('ai-llm', 12.5);
    });

    it('should call onVramOverrideChange with null when reset to default', async () => {
      const assignmentsWithOverride: GpuAssignment[] = [
        { service: 'ai-llm', gpu_index: 0, vram_budget_override: 10.5 },
      ];
      const onVramOverrideChange = vi.fn();
      const { user } = renderWithProviders(
        <GpuAssignmentTable
          {...defaultProps}
          assignments={assignmentsWithOverride}
          onVramOverrideChange={onVramOverrideChange}
        />
      );

      const resetButton = screen.getByTestId('vram-reset-ai-llm');
      await user.click(resetButton);

      expect(onVramOverrideChange).toHaveBeenCalledWith('ai-llm', null);
    });

    it('should show reset button only when override is set', () => {
      const assignmentsWithOverride: GpuAssignment[] = [
        { service: 'ai-llm', gpu_index: 0, vram_budget_override: 10.5 },
        { service: 'ai-yolo26', gpu_index: 0, vram_budget_override: null },
      ];

      renderWithProviders(
        <GpuAssignmentTable
          {...defaultProps}
          assignments={assignmentsWithOverride}
          onVramOverrideChange={onVramOverrideChangeMock}
        />
      );

      expect(screen.getByTestId('vram-reset-ai-llm')).toBeInTheDocument();
      expect(screen.queryByTestId('vram-reset-ai-yolo26')).not.toBeInTheDocument();
    });

    it('should validate VRAM input is a positive number', async () => {
      const onVramOverrideChange = vi.fn();
      const { user } = renderWithProviders(
        <GpuAssignmentTable {...defaultProps} onVramOverrideChange={onVramOverrideChange} />
      );

      const input = screen.getByTestId('vram-override-ai-llm');
      await user.clear(input);
      await user.type(input, '-5');
      await user.tab();

      // Should not call with invalid value
      expect(onVramOverrideChange).not.toHaveBeenCalledWith('ai-llm', -5);
    });
  });
});
