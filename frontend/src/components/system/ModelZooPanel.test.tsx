import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ModelZooPanel from './ModelZooPanel';

import type { VRAMStats } from '../../hooks/useModelZooStatus';
import type { ModelStatusResponse } from '../../services/api';

describe('ModelZooPanel', () => {
  const mockModels: ModelStatusResponse[] = [
    {
      name: 'clip_embedder',
      display_name: 'CLIP ViT-L/14',
      vram_mb: 400,
      status: 'loaded',
      category: 'embedding',
      enabled: true,
      available: true,
      path: '/models/clip-vit-l-14',
      load_count: 1547,
    },
    {
      name: 'yolo11-face',
      display_name: 'YOLO11 Face',
      vram_mb: 150,
      status: 'unloaded',
      category: 'detection',
      enabled: true,
      available: false,
      path: '/models/yolo11-face',
      load_count: 0,
    },
    {
      name: 'fashion-clip',
      display_name: 'FashionCLIP',
      vram_mb: 200,
      status: 'unloaded',
      category: 'embedding',
      enabled: true,
      available: false,
      path: '/models/fashion-clip',
      load_count: 0,
    },
    {
      name: 'vitpose-small',
      display_name: 'ViTPose Small',
      vram_mb: 180,
      status: 'disabled',
      category: 'pose',
      enabled: false,
      available: false,
      path: '/models/vitpose-small',
      load_count: 0,
    },
  ];

  const mockVramStats: VRAMStats = {
    budget_mb: 1650,
    used_mb: 450,
    available_mb: 1200,
    usage_percent: 27.27,
  };

  const mockRefresh = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the panel with title', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('model-zoo-panel')).toBeInTheDocument();
      expect(screen.getByText('AI Model Zoo')).toBeInTheDocument();
    });

    it('renders refresh button', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('model-zoo-refresh-btn')).toBeInTheDocument();
    });

    it('calls onRefresh when refresh button is clicked', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      fireEvent.click(screen.getByTestId('model-zoo-refresh-btn'));
      expect(mockRefresh).toHaveBeenCalledTimes(1);
    });
  });

  describe('VRAM usage display', () => {
    it('displays VRAM budget information', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('vram-progress-bar')).toBeInTheDocument();
      expect(screen.getByText(/450.*\/.*1650.*MB/i)).toBeInTheDocument();
    });

    it('displays VRAM usage percentage', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByText(/27%/)).toBeInTheDocument();
    });

    it('handles null vramStats gracefully', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={null}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('model-zoo-panel')).toBeInTheDocument();
    });
  });

  describe('model table', () => {
    it('renders all models in the table', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
          defaultShowAll={true}
        />
      );

      expect(screen.getByText('CLIP ViT-L/14')).toBeInTheDocument();
      expect(screen.getByText('YOLO11 Face')).toBeInTheDocument();
      expect(screen.getByText('FashionCLIP')).toBeInTheDocument();
      expect(screen.getByText('ViTPose Small')).toBeInTheDocument();
    });

    it('displays model VRAM requirements', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
          defaultShowAll={true}
        />
      );

      expect(screen.getByText('400 MB')).toBeInTheDocument();
      expect(screen.getByText('150 MB')).toBeInTheDocument();
      expect(screen.getByText('200 MB')).toBeInTheDocument();
      expect(screen.getByText('180 MB')).toBeInTheDocument();
    });

    it('displays load count for loaded models', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByText('1,547')).toBeInTheDocument();
    });

    it('displays dash for unloaded models load count', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
          defaultShowAll={true}
        />
      );

      // Count the dash characters for unloaded models
      const dashes = screen.getAllByText('-');
      expect(dashes.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('status indicators', () => {
    it('shows loaded status indicator', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('status-badge-clip_embedder')).toHaveTextContent('Loaded');
    });

    it('shows unloaded status indicator', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
          defaultShowAll={true}
        />
      );

      expect(screen.getByTestId('status-badge-yolo11-face')).toHaveTextContent('Unloaded');
    });

    it('shows disabled status indicator', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
          defaultShowAll={true}
        />
      );

      expect(screen.getByTestId('status-badge-vitpose-small')).toHaveTextContent('Disabled');
    });
  });

  describe('loading state', () => {
    it('shows loading state', () => {
      render(
        <ModelZooPanel
          models={[]}
          vramStats={null}
          isLoading={true}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('model-zoo-loading')).toBeInTheDocument();
    });

    it('disables refresh button while loading', () => {
      render(
        <ModelZooPanel
          models={[]}
          vramStats={null}
          isLoading={true}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('model-zoo-refresh-btn')).toBeDisabled();
    });
  });

  describe('error state', () => {
    it('shows error message', () => {
      render(
        <ModelZooPanel
          models={[]}
          vramStats={null}
          isLoading={false}
          error="Failed to fetch Model Zoo status"
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('model-zoo-error')).toBeInTheDocument();
      expect(screen.getByText(/Failed to fetch Model Zoo status/i)).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty state when no models', () => {
      render(
        <ModelZooPanel
          models={[]}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('model-zoo-empty')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
          className="custom-class"
        />
      );

      expect(screen.getByTestId('model-zoo-panel')).toHaveClass('custom-class');
    });
  });

  describe('table headers', () => {
    it('displays all column headers', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
          defaultShowAll={true}
        />
      );

      expect(screen.getByText('Model')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('VRAM')).toBeInTheDocument();
      expect(screen.getByText('Inferences')).toBeInTheDocument();
    });
  });

  describe('show all toggle', () => {
    it('renders show all toggle button', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('model-zoo-show-all-toggle')).toBeInTheDocument();
    });

    it('shows only loaded models by default', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      // Only CLIP ViT-L/14 is loaded
      expect(screen.getByText('CLIP ViT-L/14')).toBeInTheDocument();
      // Unloaded models should not be visible by default
      expect(screen.queryByText('YOLO11 Face')).not.toBeInTheDocument();
      expect(screen.queryByText('FashionCLIP')).not.toBeInTheDocument();
    });

    it('shows all models when toggle clicked', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      // Click show all toggle
      fireEvent.click(screen.getByTestId('model-zoo-show-all-toggle'));

      // All models should now be visible
      expect(screen.getByText('CLIP ViT-L/14')).toBeInTheDocument();
      expect(screen.getByText('YOLO11 Face')).toBeInTheDocument();
      expect(screen.getByText('FashionCLIP')).toBeInTheDocument();
      expect(screen.getByText('ViTPose Small')).toBeInTheDocument();
    });

    it('respects defaultShowAll prop', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
          defaultShowAll={true}
        />
      );

      // All models should be visible
      expect(screen.getByText('CLIP ViT-L/14')).toBeInTheDocument();
      expect(screen.getByText('YOLO11 Face')).toBeInTheDocument();
      expect(screen.getByText('FashionCLIP')).toBeInTheDocument();
      expect(screen.getByText('ViTPose Small')).toBeInTheDocument();
    });

    it('shows unloaded models count in summary', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      // Should show summary of unloaded models
      expect(screen.getByTestId('unloaded-models-summary')).toBeInTheDocument();
      expect(screen.getByText(/3 models unloaded/)).toBeInTheDocument();
    });

    it('hides unloaded models summary when showing all', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      // Click show all toggle
      fireEvent.click(screen.getByTestId('model-zoo-show-all-toggle'));

      // Summary should be hidden when showing all
      expect(screen.queryByTestId('unloaded-models-summary')).not.toBeInTheDocument();
    });
  });

  describe('VRAM inline summary', () => {
    it('displays inline VRAM summary in header', () => {
      render(
        <ModelZooPanel
          models={mockModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('vram-inline-summary')).toBeInTheDocument();
      expect(screen.getByText(/VRAM:.*0\.4\/2GB/)).toBeInTheDocument();
    });
  });

  describe('no active models state', () => {
    it('shows no active models state when all models unloaded', () => {
      const unloadedModels = mockModels.filter(m => m.status !== 'loaded');
      render(
        <ModelZooPanel
          models={unloadedModels}
          vramStats={mockVramStats}
          isLoading={false}
          error={null}
          onRefresh={mockRefresh}
        />
      );

      expect(screen.getByTestId('model-zoo-no-active')).toBeInTheDocument();
      expect(screen.getByText('No active models')).toBeInTheDocument();
    });
  });
});
