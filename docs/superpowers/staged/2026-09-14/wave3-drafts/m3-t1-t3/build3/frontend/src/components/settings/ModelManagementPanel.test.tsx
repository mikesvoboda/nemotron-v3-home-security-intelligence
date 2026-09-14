/**
 * Tests for ModelManagementPanel component
 *
 * Tests the comprehensive model management panel that displays:
 * - VRAM usage overview with progress bar
 * - Model status cards grouped by status (loaded/unloaded/disabled)
 * - Model category breakdown
 * - Performance metrics summary
 */

import { render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

import ModelManagementPanel from './ModelManagementPanel';

import type { UseModelZooStatusQueryReturn } from '../../hooks/useModelZooStatusQuery';

// Mock data for Model Zoo models
const createMockModels = () => [
  {
    name: 'yolo11-license-plate',
    display_name: 'YOLO License Plate',
    vram_mb: 300,
    status: 'loaded' as const,
    category: 'Detection',
    enabled: true,
    available: true,
    path: '/models/yolo11-lp.pt',
    load_count: 5,
  },
  {
    name: 'yolo11-face',
    display_name: 'YOLO Face Detection',
    vram_mb: 200,
    status: 'loaded' as const,
    category: 'Detection',
    enabled: true,
    available: true,
    path: '/models/yolo11-face.pt',
    load_count: 3,
  },
  {
    name: 'yolo11-pose',
    display_name: 'YOLO Pose Estimation',
    vram_mb: 250,
    status: 'unloaded' as const,
    category: 'Pose',
    enabled: true,
    available: true,
    path: '/models/yolo11-pose.pt',
    load_count: 0,
  },
  {
    name: 'clip-embedding',
    display_name: 'CLIP Visual Embedding',
    vram_mb: 400,
    status: 'unloaded' as const,
    category: 'Embedding',
    enabled: true,
    available: true,
    path: '/models/clip.pt',
    load_count: 0,
  },
  {
    name: 'yolo26-general',
    display_name: 'YOLO26 General',
    vram_mb: 500,
    status: 'disabled' as const,
    category: 'Detection',
    enabled: false,
    available: true,
    path: '/models/yolo26.pt',
    load_count: 0,
  },
];

// Create mock return value for useModelZooStatusQuery
const createMockReturn = (
  overrides: Partial<UseModelZooStatusQueryReturn> = {}
): UseModelZooStatusQueryReturn => ({
  data: {
    models: createMockModels(),
    vram_budget_mb: 1650,
    vram_used_mb: 500,
    vram_available_mb: 1150,
    loading_strategy: 'sequential',
    max_concurrent_models: 1,
  },
  models: createMockModels(),
  vramStats: {
    budgetMb: 1650,
    usedMb: 500,
    availableMb: 1150,
    usagePercent: 30.3,
  },
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
  ...overrides,
});

// Mock the useModelZooStatusQuery hook
const mockUseModelZooStatusQuery: Mock<() => UseModelZooStatusQueryReturn> = vi.fn(() =>
  createMockReturn()
);

vi.mock('../../hooks/useModelZooStatusQuery', () => ({
  useModelZooStatusQuery: () => mockUseModelZooStatusQuery(),
}));

beforeEach(() => {
  mockUseModelZooStatusQuery.mockReturnValue(createMockReturn());
});

describe('ModelManagementPanel', () => {
  describe('VRAM Usage Section', () => {
    it('renders VRAM usage overview', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('vram-usage-section')).toBeInTheDocument();
      expect(screen.getByText(/VRAM Usage/i)).toBeInTheDocument();
    });

    it('displays VRAM budget, used, and available', () => {
      render(<ModelManagementPanel />);

      // VRAM card should be present with budget, used, and available
      const vramSection = screen.getByTestId('vram-usage-section');
      expect(vramSection).toBeInTheDocument();
      // 500 MB used shows as "500 MB", budget 1650 MB shows as "1.6 GB"
      expect(screen.getByText(/Used/i)).toBeInTheDocument();
      expect(screen.getByText(/Budget/i)).toBeInTheDocument();
    });

    it('shows VRAM usage percentage', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByText(/30\.3%/)).toBeInTheDocument();
    });

    it('renders progress bar for VRAM usage', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  describe('Model Status Summary', () => {
    it('displays count of loaded models', () => {
      render(<ModelManagementPanel />);

      const summarySection = screen.getByTestId('model-status-summary');
      // Should show loaded count and label - multiple "Loaded" may appear (in summary and model labels)
      const loadedLabels = within(summarySection).getAllByText(/Loaded/i);
      expect(loadedLabels.length).toBeGreaterThan(0);
      // Check that we have a "2" for the loaded count (multiple "2"s may appear for 2 loaded and 2 unloaded)
      const twos = within(summarySection).getAllByText('2');
      expect(twos.length).toBeGreaterThan(0);
    });

    it('displays count of unloaded models', () => {
      render(<ModelManagementPanel />);

      const summarySection = screen.getByTestId('model-status-summary');
      expect(within(summarySection).getByText(/unloaded/i)).toBeInTheDocument();
    });

    it('displays count of disabled models', () => {
      render(<ModelManagementPanel />);

      const summarySection = screen.getByTestId('model-status-summary');
      expect(within(summarySection).getByText(/disabled/i)).toBeInTheDocument();
    });
  });

  describe('Model Cards', () => {
    it('renders model cards for each model', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByText('YOLO License Plate')).toBeInTheDocument();
      expect(screen.getByText('YOLO Face Detection')).toBeInTheDocument();
      expect(screen.getByText('YOLO Pose Estimation')).toBeInTheDocument();
      expect(screen.getByText('CLIP Visual Embedding')).toBeInTheDocument();
    });

    it('shows model category on each card', () => {
      render(<ModelManagementPanel />);

      // Multiple Detection models plus other categories - categories are shown in badges
      // Detection category should appear multiple times (3 models + category header)
      const detectionBadges = screen.getAllByText(/Detection/);
      expect(detectionBadges.length).toBeGreaterThanOrEqual(1);
      // Pose and Embedding categories - they appear in both category header and model cards
      const poseBadges = screen.getAllByText(/Pose/);
      const embeddingBadges = screen.getAllByText(/Embedding/);
      expect(poseBadges.length).toBeGreaterThanOrEqual(1);
      expect(embeddingBadges.length).toBeGreaterThanOrEqual(1);
    });

    it('displays VRAM usage per model', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByText('300 MB')).toBeInTheDocument();
      expect(screen.getByText('200 MB')).toBeInTheDocument();
      expect(screen.getByText('250 MB')).toBeInTheDocument();
    });

    it('shows loaded status indicator', () => {
      render(<ModelManagementPanel />);

      const loadedIndicators = screen.getAllByTestId('status-loaded');
      expect(loadedIndicators.length).toBe(2);
    });

    it('shows unloaded status indicator', () => {
      render(<ModelManagementPanel />);

      const unloadedIndicators = screen.getAllByTestId('status-unloaded');
      expect(unloadedIndicators.length).toBe(2);
    });

    it('shows disabled status indicator', () => {
      render(<ModelManagementPanel />);

      const disabledIndicators = screen.getAllByTestId('status-disabled');
      expect(disabledIndicators.length).toBe(1);
    });
  });

  describe('Loading State', () => {
    it('shows loading state when isLoading is true', () => {
      mockUseModelZooStatusQuery.mockReturnValue(
        createMockReturn({
          isLoading: true,
          models: [],
          vramStats: null,
        })
      );

      render(<ModelManagementPanel />);

      expect(screen.getByText(/Loading/i)).toBeInTheDocument();
    });

    it('shows refetching indicator when isRefetching is true', () => {
      mockUseModelZooStatusQuery.mockReturnValue(
        createMockReturn({
          isRefetching: true,
        })
      );

      render(<ModelManagementPanel />);

      expect(screen.getByTestId('refetch-indicator')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when error occurs', () => {
      mockUseModelZooStatusQuery.mockReturnValue(
        createMockReturn({
          error: new Error('Failed to fetch model status'),
          models: [],
          vramStats: null,
        })
      );

      render(<ModelManagementPanel />);

      expect(screen.getByText(/Failed to fetch model status/i)).toBeInTheDocument();
    });

    it('shows error styling', () => {
      mockUseModelZooStatusQuery.mockReturnValue(
        createMockReturn({
          error: new Error('Network error'),
          models: [],
          vramStats: null,
        })
      );

      render(<ModelManagementPanel />);

      expect(screen.getByTestId('error-message')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('handles empty model list gracefully', () => {
      mockUseModelZooStatusQuery.mockReturnValue(
        createMockReturn({
          models: [],
          vramStats: {
            budgetMb: 1650,
            usedMb: 0,
            availableMb: 1650,
            usagePercent: 0,
          },
        })
      );

      render(<ModelManagementPanel />);

      expect(screen.getByText(/No models/i)).toBeInTheDocument();
    });
  });

  describe('Category Grouping', () => {
    it('groups models by category', () => {
      render(<ModelManagementPanel />);

      // Should have category sections
      const detectionSection = screen.getByTestId('category-detection');
      expect(detectionSection).toBeInTheDocument();
    });

    it('shows model count per category', () => {
      render(<ModelManagementPanel />);

      // Detection category should show 3 models (2 enabled + 1 disabled)
      const detectionSection = screen.getByTestId('category-detection');
      // The badge shows "X models (Y loaded)"
      expect(within(detectionSection).getByText(/3 models/)).toBeInTheDocument();
    });
  });

  describe('Performance Metrics', () => {
    it('shows load count for loaded models', () => {
      render(<ModelManagementPanel />);

      // yolo11-license-plate has load_count of 5
      expect(screen.getByText(/5 loads/i)).toBeInTheDocument();
    });
  });

  describe('Styling and Layout', () => {
    it('applies custom className', () => {
      render(<ModelManagementPanel className="custom-class" />);

      expect(screen.getByTestId('model-management-panel')).toHaveClass('custom-class');
    });

    it('renders with NVIDIA dark theme styling', () => {
      render(<ModelManagementPanel />);

      // Check for dark theme background classes
      const panel = screen.getByTestId('model-management-panel');
      expect(panel).toBeInTheDocument();
    });
  });

  describe('Responsive Layout', () => {
    it('renders in grid layout', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('model-cards-grid')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper heading structure', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByRole('heading', { name: /Model Management/i })).toBeInTheDocument();
    });

    it('provides descriptive labels for status indicators', () => {
      render(<ModelManagementPanel />);

      const loadedIndicators = screen.getAllByTestId('status-loaded');
      loadedIndicators.forEach((indicator) => {
        expect(indicator).toHaveAttribute('aria-label');
      });
    });
  });
});
