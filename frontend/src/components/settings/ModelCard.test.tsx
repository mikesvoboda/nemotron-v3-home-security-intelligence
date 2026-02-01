/**
 * Unit tests for ModelCard component
 *
 * Tests the individual model card display including status indicators,
 * load/unload buttons, and confirmation dialogs.
 *
 * TDD RED PHASE: These tests will fail until the component is implemented.
 *
 * @see NEM-4788
 * @see docs/plans/2025-01-31-model-zoo-management-design.md
 */

import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ModelCard from './ModelCard';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type { ModelStatus } from '../../services/modelZooApi';

// ============================================================================
// Mock Data
// ============================================================================

const mockLoadedModel: ModelStatus = {
  name: 'threat-detection-yolov8n',
  category: 'detection',
  estimated_vram_mb: 300,
  enabled: true,
  service: 'ai-enrichment-light',
  gpu_id: 1,
  runtime: {
    loaded: true,
    actual_vram_mb: 287,
    last_used: '2026-01-31T10:30:00Z',
    load_count: 5,
  },
};

const mockUnloadedModel: ModelStatus = {
  name: 'vehicle-segment-classification',
  category: 'classification',
  estimated_vram_mb: 1500,
  enabled: true,
  service: 'ai-enrichment',
  gpu_id: 0,
  runtime: {
    loaded: false,
    actual_vram_mb: null,
    last_used: null,
    load_count: 0,
  },
};

const mockDisabledModel: ModelStatus = {
  name: 'fashion-clip',
  category: 'classification',
  estimated_vram_mb: 800,
  enabled: false,
  service: 'ai-enrichment',
  gpu_id: 0,
  runtime: null,
};

// ============================================================================
// Basic Rendering Tests
// ============================================================================

describe('ModelCard', () => {
  const defaultProps = {
    model: mockLoadedModel,
    onLoad: vi.fn(),
    onUnload: vi.fn(),
    isLoading: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('basic rendering', () => {
    it('displays model name and category', () => {
      renderWithProviders(<ModelCard {...defaultProps} />);

      expect(screen.getByText('threat-detection-yolov8n')).toBeInTheDocument();
      expect(screen.getByText('detection')).toBeInTheDocument();
    });

    it('displays estimated VRAM usage', () => {
      renderWithProviders(<ModelCard {...defaultProps} />);

      // Should show estimated or actual VRAM
      expect(screen.getByText(/300\s*MB/i)).toBeInTheDocument();
    });

    it('displays service name', () => {
      renderWithProviders(<ModelCard {...defaultProps} />);

      expect(screen.getByText(/ai-enrichment-light/i)).toBeInTheDocument();
    });

    it('displays GPU assignment', () => {
      renderWithProviders(<ModelCard {...defaultProps} />);

      expect(screen.getByText(/GPU\s*1/i)).toBeInTheDocument();
    });

    it('has correct test id', () => {
      renderWithProviders(<ModelCard {...defaultProps} />);

      expect(screen.getByTestId('model-card-threat-detection-yolov8n')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Status Indicator Tests
  // ============================================================================

  describe('status indicators', () => {
    it('shows loaded status indicator when loaded', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      const statusIndicator = screen.getByTestId('model-status-indicator');
      expect(statusIndicator).toHaveClass(/loaded|green|active/i);
      expect(screen.getByText(/loaded/i)).toBeInTheDocument();
    });

    it('shows unloaded status indicator when not loaded', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockUnloadedModel} />);

      const statusIndicator = screen.getByTestId('model-status-indicator');
      expect(statusIndicator).toHaveClass(/unloaded|gray|inactive/i);
      expect(screen.getByText(/unloaded/i)).toBeInTheDocument();
    });

    it('shows disabled status indicator when model is disabled', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockDisabledModel} />);

      expect(screen.getByText(/disabled/i)).toBeInTheDocument();
    });

    it('displays actual VRAM when loaded', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      // Should show actual VRAM (287 MB) when loaded
      expect(screen.getByText(/287\s*MB/i)).toBeInTheDocument();
    });

    it('displays estimated VRAM when not loaded', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockUnloadedModel} />);

      // Should show estimated VRAM (1500 MB) when not loaded
      expect(screen.getByText(/1500\s*MB/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Load Button Tests
  // ============================================================================

  describe('load button', () => {
    it('load button disabled when model is loaded', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      const loadButton = screen.getByRole('button', { name: /^load$/i });
      expect(loadButton).toBeDisabled();
    });

    it('load button enabled when model is not loaded', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockUnloadedModel} />);

      const loadButton = screen.getByRole('button', { name: /^load$/i });
      expect(loadButton).toBeEnabled();
    });

    it('load button disabled when model is disabled', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockDisabledModel} />);

      const loadButton = screen.queryByRole('button', { name: /^load$/i });
      // Button should either not exist or be disabled for disabled models
      if (loadButton) {
        expect(loadButton).toBeDisabled();
      }
    });

    it('calls onLoad when load button is clicked', async () => {
      const onLoad = vi.fn();
      const { user } = renderWithProviders(
        <ModelCard {...defaultProps} model={mockUnloadedModel} onLoad={onLoad} />
      );

      await user.click(screen.getByRole('button', { name: /^load$/i }));

      expect(onLoad).toHaveBeenCalledWith('vehicle-segment-classification');
    });

    it('load button disabled during loading operation', () => {
      renderWithProviders(
        <ModelCard {...defaultProps} model={mockUnloadedModel} isLoading={true} />
      );

      const loadButton = screen.getByRole('button', { name: /^load$/i });
      expect(loadButton).toBeDisabled();
    });
  });

  // ============================================================================
  // Unload Button Tests
  // ============================================================================

  describe('unload button', () => {
    it('unload button enabled when model is loaded', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      const unloadButton = screen.getByRole('button', { name: /^unload$/i });
      expect(unloadButton).toBeEnabled();
    });

    it('unload button disabled when model is not loaded', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockUnloadedModel} />);

      const unloadButton = screen.getByRole('button', { name: /^unload$/i });
      expect(unloadButton).toBeDisabled();
    });

    it('unload button shows confirmation dialog', async () => {
      const { user } = renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      await user.click(screen.getByRole('button', { name: /^unload$/i }));

      // Confirmation dialog should appear
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Dialog should have warning message
      expect(screen.getByText(/will need to reload/i)).toBeInTheDocument();
    });

    it('calls onUnload after confirmation', async () => {
      const onUnload = vi.fn();
      const { user } = renderWithProviders(
        <ModelCard {...defaultProps} model={mockLoadedModel} onUnload={onUnload} />
      );

      // Click unload button
      await user.click(screen.getByRole('button', { name: /^unload$/i }));

      // Confirm in dialog
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /confirm/i }));

      expect(onUnload).toHaveBeenCalledWith('threat-detection-yolov8n');
    });

    it('does not call onUnload when dialog is cancelled', async () => {
      const onUnload = vi.fn();
      const { user } = renderWithProviders(
        <ModelCard {...defaultProps} model={mockLoadedModel} onUnload={onUnload} />
      );

      // Click unload button
      await user.click(screen.getByRole('button', { name: /^unload$/i }));

      // Cancel in dialog
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onUnload).not.toHaveBeenCalled();
    });

    it('unload button disabled during loading operation', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} isLoading={true} />);

      const unloadButton = screen.getByRole('button', { name: /^unload$/i });
      expect(unloadButton).toBeDisabled();
    });
  });

  // ============================================================================
  // Loading State Tests
  // ============================================================================

  describe('loading state', () => {
    it('shows loading spinner during load operation', () => {
      renderWithProviders(
        <ModelCard {...defaultProps} model={mockUnloadedModel} isLoading={true} loadingAction="load" />
      );

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('shows loading spinner during unload operation', () => {
      renderWithProviders(
        <ModelCard {...defaultProps} model={mockLoadedModel} isLoading={true} loadingAction="unload" />
      );

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('disables all buttons during loading', () => {
      renderWithProviders(
        <ModelCard {...defaultProps} model={mockLoadedModel} isLoading={true} />
      );

      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button).toBeDisabled();
      });
    });
  });

  // ============================================================================
  // Last Used Display Tests
  // ============================================================================

  describe('last used display', () => {
    it('shows last used time for loaded model', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      // Should show relative time or formatted date
      expect(screen.getByText(/last used/i)).toBeInTheDocument();
    });

    it('shows never used for model without last_used', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockUnloadedModel} />);

      expect(screen.getByText(/never/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Load Count Display Tests
  // ============================================================================

  describe('load count display', () => {
    it('displays load count when available', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      // Load count is 5
      expect(screen.getByText(/5/)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Category Badge Tests
  // ============================================================================

  describe('category badge', () => {
    it('displays category as badge', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      const categoryBadge = screen.getByText('detection');
      expect(categoryBadge).toHaveClass(/badge|chip|tag/i);
    });

    it('displays different styling for different categories', () => {
      // Render first model and capture badge class
      const { unmount: unmount1 } = renderWithProviders(
        <ModelCard {...defaultProps} model={mockLoadedModel} />
      );
      const detectionBadgeText = screen.getByText('detection');
      const detectionBadgeClass = detectionBadgeText.parentElement?.className ?? '';
      unmount1();

      // Render second model and capture badge class
      renderWithProviders(<ModelCard {...defaultProps} model={mockUnloadedModel} />);
      const classificationBadgeText = screen.getByText('classification');
      const classificationBadgeClass = classificationBadgeText.parentElement?.className ?? '';

      // Badges should have different styling (compare parent Badge wrapper classes)
      expect(detectionBadgeClass).not.toBe(classificationBadgeClass);
    });
  });

  // ============================================================================
  // Accessibility Tests
  // ============================================================================

  describe('accessibility', () => {
    it('has accessible button labels', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      expect(screen.getByRole('button', { name: /^load$/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /^unload$/i })).toBeInTheDocument();
    });

    it('has appropriate ARIA attributes for status', () => {
      renderWithProviders(<ModelCard {...defaultProps} model={mockLoadedModel} />);

      const card = screen.getByTestId('model-card-threat-detection-yolov8n');
      expect(card).toHaveAttribute('role', 'article');
    });
  });

  // ============================================================================
  // Error State Tests
  // ============================================================================

  describe('error state', () => {
    it('displays error message when provided', () => {
      renderWithProviders(<ModelCard {...defaultProps} error="Failed to load model" />);

      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });

    it('clears error when operation succeeds', () => {
      const { rerender } = renderWithProviders(
        <ModelCard {...defaultProps} error="Failed to load model" />
      );

      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();

      rerender(<ModelCard {...defaultProps} error={undefined} />);

      expect(screen.queryByText(/failed to load/i)).not.toBeInTheDocument();
    });
  });
});
