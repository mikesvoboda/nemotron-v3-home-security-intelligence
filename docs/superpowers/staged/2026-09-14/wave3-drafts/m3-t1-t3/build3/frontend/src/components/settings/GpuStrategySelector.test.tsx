/**
 * GpuStrategySelector Tests
 *
 * Tests for the GPU Strategy Selector component that displays:
 * - Strategy radio options
 * - Strategy descriptions
 * - Preview button and results
 *
 * @see NEM-3320 - Create GPU Settings UI component
 */

import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import GpuStrategySelector from './GpuStrategySelector';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type { StrategyPreviewResponse } from '../../hooks/useGpuConfig';

// ============================================================================
// Test Data
// ============================================================================

const availableStrategies = [
  'manual',
  'vram_based',
  'latency_optimized',
  'isolation_first',
  'balanced',
];

const mockPreviewResponse: StrategyPreviewResponse = {
  strategy: 'balanced',
  proposed_assignments: [
    { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
    { service: 'ai-yolo26', gpu_index: 1, vram_budget_override: null },
  ],
  warnings: [],
};

const mockPreviewResponseWithWarnings: StrategyPreviewResponse = {
  strategy: 'vram_based',
  proposed_assignments: [
    { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
    { service: 'ai-enrichment', gpu_index: 1, vram_budget_override: 3.5 },
  ],
  warnings: [
    'ai-enrichment VRAM budget (6.8 GB) exceeds GPU 1 (4 GB). Suggested budget: 3.5 GB.',
    'Some services may experience memory pressure.',
  ],
};

// ============================================================================
// Tests
// ============================================================================

describe('GpuStrategySelector', () => {
  const defaultProps = {
    selectedStrategy: 'manual',
    availableStrategies,
    onStrategyChange: vi.fn(),
    onPreview: vi.fn().mockResolvedValue(mockPreviewResponse),
  };

  describe('rendering', () => {
    it('should render strategy selector container', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} />);

      expect(screen.getByTestId('gpu-strategy-selector')).toBeInTheDocument();
    });

    it('should render title', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} />);

      expect(screen.getByText('Assignment Strategy')).toBeInTheDocument();
    });

    it('should render all strategy options', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} />);

      expect(screen.getByTestId('strategy-option-manual')).toBeInTheDocument();
      expect(screen.getByTestId('strategy-option-vram_based')).toBeInTheDocument();
      expect(screen.getByTestId('strategy-option-latency_optimized')).toBeInTheDocument();
      expect(screen.getByTestId('strategy-option-isolation_first')).toBeInTheDocument();
      expect(screen.getByTestId('strategy-option-balanced')).toBeInTheDocument();
    });

    it('should render strategy labels', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} />);

      expect(screen.getByText('Manual')).toBeInTheDocument();
      expect(screen.getByText('VRAM-based')).toBeInTheDocument();
      expect(screen.getByText('Latency-optimized')).toBeInTheDocument();
      expect(screen.getByText('Isolation-first')).toBeInTheDocument();
      expect(screen.getByText('Balanced')).toBeInTheDocument();
    });

    it('should render strategy descriptions', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} />);

      expect(screen.getByText('Manually assign GPUs to each AI service')).toBeInTheDocument();
      expect(screen.getByText('Assign GPUs based on VRAM requirements')).toBeInTheDocument();
    });
  });

  describe('selection', () => {
    it('should mark selected strategy as checked', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} />);

      const manualOption = screen.getByTestId('strategy-option-manual');
      const radioInput = manualOption.querySelector('input[type="radio"]');
      expect(radioInput).toBeChecked();
    });

    it('should call onStrategyChange when strategy is clicked', async () => {
      const onStrategyChange = vi.fn();
      const { user } = renderWithProviders(
        <GpuStrategySelector {...defaultProps} onStrategyChange={onStrategyChange} />
      );

      await user.click(screen.getByTestId('strategy-option-balanced'));

      expect(onStrategyChange).toHaveBeenCalledWith('balanced');
    });

    it('should mark different strategy as selected', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} selectedStrategy="balanced" />);

      const balancedOption = screen.getByTestId('strategy-option-balanced');
      const radioInput = balancedOption.querySelector('input[type="radio"]');
      expect(radioInput).toBeChecked();
    });
  });

  describe('preview button', () => {
    it('should render preview button', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} />);

      expect(screen.getByTestId('preview-strategy-button')).toBeInTheDocument();
    });

    it('should disable preview button when manual strategy is selected', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} selectedStrategy="manual" />);

      expect(screen.getByTestId('preview-strategy-button')).toBeDisabled();
    });

    it('should enable preview button when non-manual strategy is selected', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} selectedStrategy="balanced" />);

      expect(screen.getByTestId('preview-strategy-button')).not.toBeDisabled();
    });

    it('should call onPreview when preview button is clicked', async () => {
      const onPreview = vi.fn().mockResolvedValue(mockPreviewResponse);
      const { user } = renderWithProviders(
        <GpuStrategySelector {...defaultProps} selectedStrategy="balanced" onPreview={onPreview} />
      );

      await user.click(screen.getByTestId('preview-strategy-button'));

      await waitFor(() => {
        expect(onPreview).toHaveBeenCalledWith('balanced');
      });
    });
  });

  describe('preview results', () => {
    it('should show preview data when available', () => {
      renderWithProviders(
        <GpuStrategySelector
          {...defaultProps}
          selectedStrategy="balanced"
          previewData={mockPreviewResponse}
        />
      );

      expect(screen.getByText('Proposed Assignments')).toBeInTheDocument();
      expect(screen.getByText('ai-llm')).toBeInTheDocument();
      expect(screen.getByText('ai-yolo26')).toBeInTheDocument();
    });

    it('should show loading state during preview', () => {
      renderWithProviders(
        <GpuStrategySelector {...defaultProps} selectedStrategy="balanced" isPreviewLoading />
      );

      expect(screen.getByText('Loading preview...')).toBeInTheDocument();
    });

    it('should show error message on preview error', () => {
      renderWithProviders(
        <GpuStrategySelector
          {...defaultProps}
          selectedStrategy="balanced"
          previewError="Failed to load preview"
        />
      );

      expect(screen.getByText('Failed to load preview')).toBeInTheDocument();
    });
  });

  describe('unavailable strategies', () => {
    it('should mark unavailable strategies', () => {
      renderWithProviders(
        <GpuStrategySelector {...defaultProps} availableStrategies={['manual', 'balanced']} />
      );

      // Strategies not in availableStrategies should show "Unavailable" badge
      expect(screen.getAllByText('Unavailable')).toHaveLength(3);
    });

    it('should disable unavailable strategy options', () => {
      renderWithProviders(
        <GpuStrategySelector {...defaultProps} availableStrategies={['manual', 'balanced']} />
      );

      const vramOption = screen.getByTestId('strategy-option-vram_based');
      const radioInput = vramOption.querySelector('input[type="radio"]');
      expect(radioInput).toBeDisabled();
    });
  });

  describe('disabled state', () => {
    it('should disable all options when disabled prop is true', () => {
      renderWithProviders(<GpuStrategySelector {...defaultProps} disabled />);

      const manualOption = screen.getByTestId('strategy-option-manual');
      const radioInput = manualOption.querySelector('input[type="radio"]');
      expect(radioInput).toBeDisabled();
    });

    it('should disable preview button when disabled', () => {
      renderWithProviders(
        <GpuStrategySelector {...defaultProps} selectedStrategy="balanced" disabled />
      );

      expect(screen.getByTestId('preview-strategy-button')).toBeDisabled();
    });
  });

  describe('preview warnings', () => {
    it('should display warnings from preview response', () => {
      renderWithProviders(
        <GpuStrategySelector
          {...defaultProps}
          selectedStrategy="vram_based"
          previewData={mockPreviewResponseWithWarnings}
        />
      );

      expect(
        screen.getByText(/ai-enrichment VRAM budget \(6\.8 GB\) exceeds GPU 1/)
      ).toBeInTheDocument();
      expect(screen.getByText(/Some services may experience memory pressure/)).toBeInTheDocument();
    });

    it('should show warning icon for each warning', () => {
      renderWithProviders(
        <GpuStrategySelector
          {...defaultProps}
          selectedStrategy="vram_based"
          previewData={mockPreviewResponseWithWarnings}
        />
      );

      expect(screen.getByTestId('preview-warnings')).toBeInTheDocument();
    });

    it('should not show warnings section when no warnings', () => {
      renderWithProviders(
        <GpuStrategySelector
          {...defaultProps}
          selectedStrategy="balanced"
          previewData={mockPreviewResponse}
        />
      );

      expect(screen.queryByTestId('preview-warnings')).not.toBeInTheDocument();
    });

    it('should show strategy name in preview results', () => {
      renderWithProviders(
        <GpuStrategySelector
          {...defaultProps}
          selectedStrategy="vram_based"
          previewData={mockPreviewResponseWithWarnings}
        />
      );

      expect(screen.getByText(/vram_based/i)).toBeInTheDocument();
    });
  });
});
