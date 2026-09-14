/**
 * GpuApplyButton Tests
 *
 * Tests for the GPU Apply Button component that provides:
 * - Save and Apply buttons
 * - Confirmation dialog
 * - Restart progress display
 * - Apply result feedback
 *
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import GpuApplyButton from './GpuApplyButton';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type { GpuApplyResult, ServiceStatus } from '../../hooks/useGpuConfig';

// ============================================================================
// Test Data
// ============================================================================

const mockApplyResultSuccess: GpuApplyResult = {
  success: true,
  warnings: [],
  restarted_services: ['ai-llm', 'ai-yolo26', 'ai-enrichment'],
  service_statuses: [
    { service: 'ai-llm', status: 'running', message: null },
    { service: 'ai-yolo26', status: 'running', message: null },
    { service: 'ai-enrichment', status: 'running', message: null },
  ],
};

const mockApplyResultWithFailures: GpuApplyResult = {
  success: false,
  warnings: ['Some services failed to restart'],
  restarted_services: ['ai-llm'],
  service_statuses: [
    { service: 'ai-llm', status: 'running', message: null },
    { service: 'ai-yolo26', status: 'error', message: 'Failed to restart' },
    { service: 'ai-enrichment', status: 'error', message: 'Failed to restart' },
  ],
};

const mockServiceStatuses: ServiceStatus[] = [
  { service: 'ai-llm', status: 'running', message: null },
  { service: 'ai-yolo26', status: 'starting', message: 'Restarting' },
  { service: 'ai-enrichment', status: 'running', message: null },
];

// ============================================================================
// Tests
// ============================================================================

describe('GpuApplyButton', () => {
  const defaultProps = {
    hasChanges: false,
    onSave: vi.fn().mockResolvedValue(undefined),
    onApply: vi.fn().mockResolvedValue(mockApplyResultSuccess),
  };

  describe('rendering', () => {
    it('should render button container', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} />);

      expect(screen.getByTestId('gpu-apply-button-card')).toBeInTheDocument();
    });

    it('should render save button', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} />);

      expect(screen.getByTestId('save-config-button')).toBeInTheDocument();
      expect(screen.getByTestId('save-config-button')).toHaveTextContent('Save Configuration');
    });

    it('should render apply button', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} />);

      expect(screen.getByTestId('apply-config-button')).toBeInTheDocument();
      expect(screen.getByTestId('apply-config-button')).toHaveTextContent('Save & Apply');
    });

    it('should render helper text', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} />);

      expect(screen.getByText(/saves changes without restarting services/i)).toBeInTheDocument();
      expect(screen.getByText(/saves changes and restarts affected services/i)).toBeInTheDocument();
    });
  });

  describe('save button', () => {
    it('should be disabled when no changes', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} hasChanges={false} />);

      expect(screen.getByTestId('save-config-button')).toBeDisabled();
    });

    it('should be enabled when there are changes', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} hasChanges />);

      expect(screen.getByTestId('save-config-button')).not.toBeDisabled();
    });

    it('should call onSave when clicked', async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      const { user } = renderWithProviders(
        <GpuApplyButton {...defaultProps} hasChanges onSave={onSave} />
      );

      await user.click(screen.getByTestId('save-config-button'));

      await waitFor(() => {
        expect(onSave).toHaveBeenCalled();
      });
    });

    it('should be disabled while saving', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} hasChanges isSaving />);

      expect(screen.getByTestId('save-config-button')).toBeDisabled();
    });
  });

  describe('apply button', () => {
    it('should always be enabled (unless disabled or loading)', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} />);

      expect(screen.getByTestId('apply-config-button')).not.toBeDisabled();
    });

    it('should show confirmation dialog when clicked', async () => {
      const { user } = renderWithProviders(<GpuApplyButton {...defaultProps} />);

      await user.click(screen.getByTestId('apply-config-button'));

      expect(screen.getByTestId('apply-confirmation-dialog')).toBeInTheDocument();
    });

    it('should be disabled while applying', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} isApplying />);

      expect(screen.getByTestId('apply-config-button')).toBeDisabled();
    });

    it('should be disabled when disabled prop is true', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} disabled />);

      expect(screen.getByTestId('apply-config-button')).toBeDisabled();
    });
  });

  describe('confirmation dialog', () => {
    it('should show warning message', async () => {
      const { user } = renderWithProviders(<GpuApplyButton {...defaultProps} />);

      await user.click(screen.getByTestId('apply-config-button'));

      expect(screen.getByText('Restart Services?')).toBeInTheDocument();
      expect(screen.getByText(/will restart the affected AI services/i)).toBeInTheDocument();
    });

    it('should have cancel button', async () => {
      const { user } = renderWithProviders(<GpuApplyButton {...defaultProps} />);

      await user.click(screen.getByTestId('apply-config-button'));

      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });

    it('should close dialog when cancel is clicked', async () => {
      const { user } = renderWithProviders(<GpuApplyButton {...defaultProps} />);

      await user.click(screen.getByTestId('apply-config-button'));
      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      expect(screen.queryByTestId('apply-confirmation-dialog')).not.toBeInTheDocument();
    });

    it('should call onApply when confirmed', async () => {
      const onApply = vi.fn().mockResolvedValue(mockApplyResultSuccess);
      const { user } = renderWithProviders(<GpuApplyButton {...defaultProps} onApply={onApply} />);

      await user.click(screen.getByTestId('apply-config-button'));
      await user.click(screen.getByRole('button', { name: /Apply Changes/i }));

      await waitFor(() => {
        expect(onApply).toHaveBeenCalled();
      });
    });
  });

  describe('unsaved changes indicator', () => {
    it('should show warning when hasChanges is true', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} hasChanges />);

      expect(screen.getByText(/You have unsaved changes/i)).toBeInTheDocument();
    });

    it('should not show warning when no changes', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} hasChanges={false} />);

      expect(screen.queryByText(/You have unsaved changes/i)).not.toBeInTheDocument();
    });

    it('should not show warning when loading', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} hasChanges isSaving />);

      expect(screen.queryByText(/You have unsaved changes/i)).not.toBeInTheDocument();
    });
  });

  describe('error display', () => {
    it('should show error when error prop is set', () => {
      renderWithProviders(
        <GpuApplyButton {...defaultProps} error="Failed to save configuration" />
      );

      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText('Failed to save configuration')).toBeInTheDocument();
    });

    it('should not show error when no error', () => {
      renderWithProviders(<GpuApplyButton {...defaultProps} error={null} />);

      expect(screen.queryByText('Error')).not.toBeInTheDocument();
    });
  });

  describe('restart progress', () => {
    it('should show restart progress when applying', () => {
      renderWithProviders(
        <GpuApplyButton {...defaultProps} isApplying serviceStatuses={mockServiceStatuses} />
      );

      expect(screen.getByText('Restart Progress')).toBeInTheDocument();
    });

    it('should show service statuses', () => {
      renderWithProviders(
        <GpuApplyButton {...defaultProps} isApplying serviceStatuses={mockServiceStatuses} />
      );

      expect(screen.getByText('ai-llm')).toBeInTheDocument();
      expect(screen.getByText('ai-yolo26')).toBeInTheDocument();
      expect(screen.getByText('ai-enrichment')).toBeInTheDocument();
    });

    it('should show running count', () => {
      renderWithProviders(
        <GpuApplyButton {...defaultProps} isApplying serviceStatuses={mockServiceStatuses} />
      );

      // 2 out of 3 running (ai-llm and ai-enrichment are running, ai-yolo26 is starting)
      expect(screen.getByText('2 / 3 running')).toBeInTheDocument();
    });
  });

  describe('apply result', () => {
    it('should show success result', () => {
      renderWithProviders(
        <GpuApplyButton {...defaultProps} lastApplyResult={mockApplyResultSuccess} />
      );

      expect(screen.getByTestId('apply-result')).toBeInTheDocument();
      expect(screen.getByText('Configuration applied successfully')).toBeInTheDocument();
    });

    it('should show restarted services', () => {
      renderWithProviders(
        <GpuApplyButton {...defaultProps} lastApplyResult={mockApplyResultSuccess} />
      );

      expect(screen.getByText(/ai-llm, ai-yolo26, ai-enrichment/)).toBeInTheDocument();
    });

    it('should show failure result', () => {
      renderWithProviders(
        <GpuApplyButton {...defaultProps} lastApplyResult={mockApplyResultWithFailures} />
      );

      expect(screen.getByText('Apply completed with errors')).toBeInTheDocument();
    });

    it('should show failed services', () => {
      renderWithProviders(
        <GpuApplyButton {...defaultProps} lastApplyResult={mockApplyResultWithFailures} />
      );

      expect(screen.getByText(/ai-yolo26, ai-enrichment/)).toBeInTheDocument();
    });

    it('should show warnings', () => {
      renderWithProviders(
        <GpuApplyButton {...defaultProps} lastApplyResult={mockApplyResultWithFailures} />
      );

      expect(screen.getByText('Some services failed to restart')).toBeInTheDocument();
    });

    it('should not show result while applying', () => {
      renderWithProviders(
        <GpuApplyButton
          {...defaultProps}
          isApplying
          lastApplyResult={mockApplyResultSuccess}
          serviceStatuses={mockServiceStatuses}
        />
      );

      expect(screen.queryByTestId('apply-result')).not.toBeInTheDocument();
    });
  });
});
