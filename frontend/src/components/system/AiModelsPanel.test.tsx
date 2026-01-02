import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import AiModelsPanel from './AiModelsPanel';

import type { AiModelMetrics, NemotronMetrics } from '../../types/performance';

describe('AiModelsPanel', () => {
  const mockRtdetr: AiModelMetrics = {
    status: 'healthy',
    vram_gb: 0.17,
    model: 'rtdetr_r50vd_coco_o365',
    device: 'cuda:0',
  };

  const mockNemotron: NemotronMetrics = {
    status: 'healthy',
    slots_active: 1,
    slots_total: 2,
    context_size: 4096,
  };

  describe('rendering', () => {
    it('renders both model cards when data is provided', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      expect(screen.getByTestId('ai-models-panel')).toBeInTheDocument();
      expect(screen.getByTestId('rtdetr-card')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-card')).toBeInTheDocument();
    });

    it('renders RT-DETRv2 card title', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    });

    it('renders Nemotron card title', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });
  });

  describe('RT-DETRv2 model display', () => {
    it('displays RT-DETRv2 status badge', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      const statusBadge = screen.getByTestId('rtdetr-status-badge');
      expect(statusBadge).toBeInTheDocument();
      expect(statusBadge).toHaveTextContent('healthy');
    });

    it('displays RT-DETRv2 VRAM usage', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      expect(screen.getByText(/0\.17 GB/)).toBeInTheDocument();
    });

    it('displays RT-DETRv2 model name', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      expect(screen.getByText('rtdetr_r50vd_coco_o365')).toBeInTheDocument();
    });

    it('displays RT-DETRv2 device', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      expect(screen.getByText('cuda:0')).toBeInTheDocument();
    });
  });

  describe('Nemotron model display', () => {
    it('displays Nemotron status badge', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      const statusBadge = screen.getByTestId('nemotron-status-badge');
      expect(statusBadge).toBeInTheDocument();
      expect(statusBadge).toHaveTextContent('healthy');
    });

    it('displays Nemotron slots info', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      expect(screen.getByText(/1\/2 active/)).toBeInTheDocument();
    });

    it('displays Nemotron context size', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      // Note: toLocaleString() formats 4096 as "4,096" with comma separator
      expect(screen.getByText(/4,096 tokens/)).toBeInTheDocument();
    });
  });

  describe('null handling', () => {
    it('handles null rtdetr gracefully', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: null, nemotron: mockNemotron }} />);

      expect(screen.getByTestId('ai-models-panel')).toBeInTheDocument();
      expect(screen.getByTestId('rtdetr-card')).toBeInTheDocument();
      expect(screen.getByText('No data available')).toBeInTheDocument();
    });

    it('handles null nemotron gracefully', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: null }} />);

      expect(screen.getByTestId('ai-models-panel')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-card')).toBeInTheDocument();
      // Should show loading state for nemotron
      const nemotronCard = screen.getByTestId('nemotron-card');
      expect(nemotronCard).toHaveTextContent('No data available');
    });

    it('handles both null values gracefully', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: null, nemotron: null }} />);

      expect(screen.getByTestId('ai-models-panel')).toBeInTheDocument();
      expect(screen.getByTestId('rtdetr-card')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-card')).toBeInTheDocument();
    });

    it('handles undefined aiModels gracefully', () => {
      render(<AiModelsPanel />);

      expect(screen.getByTestId('ai-models-panel')).toBeInTheDocument();
      // Should show default cards with no data
      expect(screen.getByTestId('rtdetr-card')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-card')).toBeInTheDocument();
    });

    it('handles null aiModels gracefully', () => {
      render(<AiModelsPanel aiModels={null} />);

      expect(screen.getByTestId('ai-models-panel')).toBeInTheDocument();
      // Should show default cards with no data
      expect(screen.getByTestId('rtdetr-card')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-card')).toBeInTheDocument();
    });
  });

  describe('status indicators', () => {
    it('shows green badge for healthy status', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }} />);

      const rtdetrBadge = screen.getByTestId('rtdetr-status-badge');
      expect(rtdetrBadge).toBeInTheDocument();
    });

    it('shows different status for unhealthy model', () => {
      const unhealthyRtdetr: AiModelMetrics = {
        ...mockRtdetr,
        status: 'unhealthy',
      };

      render(<AiModelsPanel aiModels={{ rtdetr: unhealthyRtdetr, nemotron: mockNemotron }} />);

      const rtdetrBadge = screen.getByTestId('rtdetr-status-badge');
      expect(rtdetrBadge).toHaveTextContent('unhealthy');
    });

    it('shows loading status correctly', () => {
      const loadingRtdetr: AiModelMetrics = {
        ...mockRtdetr,
        status: 'loading',
      };

      render(<AiModelsPanel aiModels={{ rtdetr: loadingRtdetr, nemotron: mockNemotron }} />);

      const rtdetrBadge = screen.getByTestId('rtdetr-status-badge');
      expect(rtdetrBadge).toHaveTextContent('loading');
    });
  });

  describe('styling', () => {
    it('applies custom className when provided', () => {
      render(
        <AiModelsPanel
          aiModels={{ rtdetr: mockRtdetr, nemotron: mockNemotron }}
          className="custom-class"
        />
      );

      const panel = screen.getByTestId('ai-models-panel');
      expect(panel).toHaveClass('custom-class');
    });
  });

  describe('slots display', () => {
    it('shows 0 active slots correctly', () => {
      const idleNemotron: NemotronMetrics = {
        ...mockNemotron,
        slots_active: 0,
      };

      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: idleNemotron }} />);

      expect(screen.getByText(/0\/2 active/)).toBeInTheDocument();
    });

    it('shows all slots active correctly', () => {
      const busyNemotron: NemotronMetrics = {
        ...mockNemotron,
        slots_active: 2,
      };

      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr, nemotron: busyNemotron }} />);

      expect(screen.getByText(/2\/2 active/)).toBeInTheDocument();
    });
  });

  describe('dynamic model rendering', () => {
    it('renders only models provided in aiModels', () => {
      render(<AiModelsPanel aiModels={{ rtdetr: mockRtdetr }} />);

      expect(screen.getByTestId('ai-models-panel')).toBeInTheDocument();
      expect(screen.getByTestId('rtdetr-card')).toBeInTheDocument();
      expect(screen.queryByTestId('nemotron-card')).not.toBeInTheDocument();
    });

    it('renders custom model names with capitalized display', () => {
      const customModel: AiModelMetrics = {
        status: 'healthy',
        vram_gb: 1.5,
        model: 'custom_model_v1',
        device: 'cuda:1',
      };

      render(<AiModelsPanel aiModels={{ customdetector: customModel }} />);

      expect(screen.getByTestId('customdetector-card')).toBeInTheDocument();
      expect(screen.getByText('Customdetector')).toBeInTheDocument();
    });

    it('renders multiple custom models', () => {
      const model1: AiModelMetrics = {
        status: 'healthy',
        vram_gb: 1.0,
        model: 'model1',
        device: 'cuda:0',
      };
      const model2: NemotronMetrics = {
        status: 'healthy',
        slots_active: 2,
        slots_total: 4,
        context_size: 8192,
      };

      render(<AiModelsPanel aiModels={{ detector1: model1, llm1: model2 }} />);

      expect(screen.getByTestId('detector1-card')).toBeInTheDocument();
      expect(screen.getByTestId('llm1-card')).toBeInTheDocument();
    });

    it('maintains consistent ordering (rtdetr first, nemotron second)', () => {
      render(<AiModelsPanel aiModels={{ nemotron: mockNemotron, rtdetr: mockRtdetr }} />);

      const panel = screen.getByTestId('ai-models-panel');
      const cards = panel.querySelectorAll('[data-testid$="-card"]');

      expect(cards[0]).toHaveAttribute('data-testid', 'rtdetr-card');
      expect(cards[1]).toHaveAttribute('data-testid', 'nemotron-card');
    });
  });
});
