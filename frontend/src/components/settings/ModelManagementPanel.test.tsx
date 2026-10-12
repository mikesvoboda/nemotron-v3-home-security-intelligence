/**
 * Tests for ModelManagementPanel component
 *
 * [r130f] F-125/F-129: the fixtures used to be shaped like the legacy
 * api.ts ModelRegistryResponse — a `display_name`/`vram_mb`/`status` model plus
 * a top-level `vram_budget_mb`. That payload is fiction: GET /api/system/models
 * answers with the registry ModelListResponse ({ models, service_status }),
 * whose items carry no status/display_name/vram_mb at all, and its VRAM numbers
 * live on a separate endpoint. Mocking the fiction is exactly why this suite
 * stayed green while the tab crashed on every real load (F2.3's measured
 * pageerror, inventory row F-125). Fixtures now mirror the measured wire shape
 * and the component's two hooks are mocked at their own module.
 *
 * The two helpers at the bottom pin the behaviour the row asks for: state is
 * derived from fields that exist (modelDisplayStatus), and a missing runtime
 * reads as No data rather than crashing or lying "unloaded". The indicator's
 * `?? FALLBACK` guard is a boundary against future union-vs-map drift; its
 * reachable instantiation today is the No-data state, covered below.
 */

import { render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

import ModelManagementPanel, { modelDisplayStatus } from './ModelManagementPanel';

import type { UseModelsReturn, UseVRAMSummaryReturn } from '../../hooks/useModelZoo';
import type {
  ModelStatus,
  ModelListResponse,
  VRAMSummaryResponse,
} from '../../services/modelZooApi';

// Fixtures in the shape the endpoint actually sends — verified against
// backend/api/schemas/model_management.py ModelStatus / VRAMTotals and the live
// payload keys the inventory records: [category, enabled, estimated_vram_mb,
// gpu_id, name, runtime, service].
const createMockModels = (): ModelStatus[] => [
  {
    name: 'yolo11-license-plate',
    category: 'Detection',
    estimated_vram_mb: 300,
    enabled: true,
    service: 'ai-enrichment-light',
    gpu_id: 1,
    runtime: {
      loaded: true,
      actual_vram_mb: 287,
      last_used: '2025-01-31T10:30:00Z',
      load_count: 5,
    },
  },
  {
    name: 'yolo11-face',
    category: 'Detection',
    estimated_vram_mb: 200,
    enabled: true,
    service: 'ai-enrichment-light',
    gpu_id: 1,
    runtime: {
      loaded: true,
      actual_vram_mb: 194,
      last_used: '2025-01-31T10:28:00Z',
      load_count: 3,
    },
  },
  {
    name: 'yolo11-pose',
    category: 'Pose',
    estimated_vram_mb: 250,
    enabled: true,
    service: 'ai-enrichment-light',
    gpu_id: 1,
    runtime: {
      loaded: false,
      actual_vram_mb: null,
      last_used: null,
      load_count: 0,
    },
  },
  {
    name: 'clip-embedding',
    category: 'Embedding',
    estimated_vram_mb: 400,
    enabled: true,
    service: 'ai-enrichment-light',
    gpu_id: 1,
    runtime: {
      loaded: false,
      actual_vram_mb: null,
      last_used: null,
      load_count: 0,
    },
  },
  {
    // enabled:false, runtime present — the disabled branch, independent of
    // what the runtime claims.
    name: 'yolo26-general',
    category: 'Detection',
    estimated_vram_mb: 500,
    enabled: false,
    service: 'ai-enrichment-light',
    gpu_id: 1,
    runtime: {
      loaded: false,
      actual_vram_mb: null,
      last_used: null,
      load_count: 0,
    },
  },
];

const MODELS = createMockModels();

const listResponse: ModelListResponse = {
  models: MODELS,
  service_status: { 'ai-enrichment-light': 'healthy' },
};

const vramResponse: VRAMSummaryResponse = {
  gpus: [
    {
      gpu_id: 1,
      service: 'ai-enrichment-light',
      budget_mb: 1650,
      used_mb: 500,
      available_mb: 1150,
      utilization_percent: 30.3,
      loaded_models: ['yolo11-license-plate', 'yolo11-face'],
    },
  ],
  totals: { budget_mb: 1650, used_mb: 500, available_mb: 1150, model_count: 2 },
};

const modelsReturn = (overrides: Partial<UseModelsReturn> = {}): UseModelsReturn => ({
  data: listResponse,
  models: listResponse.models,
  serviceStatus: listResponse.service_status,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
  ...overrides,
});

const vramReturn = (overrides: Partial<UseVRAMSummaryReturn> = {}): UseVRAMSummaryReturn => ({
  data: vramResponse,
  gpus: vramResponse.gpus,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
  ...overrides,
});

const mockUseModels: Mock<() => UseModelsReturn> = vi.fn(() => modelsReturn());
const mockUseVRAMSummary: Mock<() => UseVRAMSummaryReturn> = vi.fn(() => vramReturn());

vi.mock('../../hooks/useModelZoo', () => ({
  useModels: () => mockUseModels(),
  useVRAMSummary: () => mockUseVRAMSummary(),
}));

beforeEach(() => {
  mockUseModels.mockReturnValue(modelsReturn());
  mockUseVRAMSummary.mockReturnValue(vramReturn());
});

describe('ModelManagementPanel', () => {
  describe('VRAM Usage Section', () => {
    it('renders VRAM usage overview', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('vram-usage-section')).toBeInTheDocument();
      expect(screen.getByText(/VRAM Usage/i)).toBeInTheDocument();
    });

    it('shows the totals the vram-summary endpoint reports', () => {
      render(<ModelManagementPanel />);

      const vramSection = screen.getByTestId('vram-usage-section');
      // 500/1650 MB, formatted to GB by VRAMUsageCard when >= 1024.
      expect(within(vramSection).getByText('500 MB')).toBeInTheDocument();
      expect(within(vramSection).getByText('1.6 GB')).toBeInTheDocument();
      expect(within(vramSection).getByText('1.1 GB')).toBeInTheDocument();
    });

    it('computes the usage percentage from budget and used', () => {
      render(<ModelManagementPanel />);

      const vramSection = screen.getByTestId('vram-usage-section');
      // 500/1650 = 30.3% — computed here, not read off the wire. The deleted
      // legacy feed carried vram_used/vram_budget but no percentage, so the old
      // 30.3% figure in this suite could only come from the fixture, not the
      // code. This asserts the division, which is the thing the panel owns.
      expect(within(vramSection).getByTestId('usage-indicator')).toHaveTextContent('30.3%');
    });

    it('names the failure when the VRAM feed errors instead of rendering an empty card', () => {
      mockUseVRAMSummary.mockReturnValue(
        vramReturn({ data: undefined, gpus: [], error: new Error('vram summary exploded') })
      );
      render(<ModelManagementPanel />);

      // [r130f] The section used to collapse to an empty div on a missing VRAM
      // feed — "no data" indistinguishable from "this query failed".
      expect(screen.getByTestId('vram-usage-unavailable')).toHaveTextContent(
        'VRAM summary unavailable: vram summary exploded'
      );
    });
  });

  describe('Model Status Summary', () => {
    // Each tile is a div holding the number then the label, so the label's
    // parent is the tile. Reading the count by its label avoids matching a
    // number that appears on two tiles (loaded and unloaded are both 2 here).
    const tileValue = (label: string): string => {
      const summary = screen.getByTestId('model-status-summary');
      const tile = within(summary).getByText(label).parentElement as HTMLElement;
      return (tile.textContent ?? '').replace(label, '');
    };

    it('counts total, loaded, unloaded and disabled from the registry fields', () => {
      render(<ModelManagementPanel />);

      expect(tileValue('Total')).toBe('5');
      expect(tileValue('Loaded')).toBe('2');
      expect(tileValue('Unloaded')).toBe('2');
      expect(tileValue('Disabled')).toBe('1');
    });

    it('drops the tiles the deleted enum reserved for values no feed sends', () => {
      render(<ModelManagementPanel />);

      const summary = screen.getByTestId('model-status-summary');
      // The wire has no loading/error state for this panel — it has no
      // load/unload action. Two permanent-zero tiles are gone, not hidden.
      expect(within(summary).queryByText(/Loading/i)).not.toBeInTheDocument();
      expect(within(summary).queryByText(/Errors/i)).not.toBeInTheDocument();
    });

    it('hides the No data tile when every model reports a runtime', () => {
      render(<ModelManagementPanel />);

      expect(screen.queryByText(/^No data$/)).not.toBeInTheDocument();
    });

    it('shows the No data tile when a runtime is missing', () => {
      mockUseModels.mockReturnValue(
        modelsReturn({
          models: [{ ...MODELS[0], runtime: null }],
          data: { ...listResponse, models: [{ ...MODELS[0], runtime: null }] },
        })
      );
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('model-status-summary')).toHaveTextContent('No data');
    });
  });

  describe('Model Cards', () => {
    it('renders a card per model named by the model name', () => {
      render(<ModelManagementPanel />);

      // The registry sends name, not display_name — the card title is the name.
      expect(screen.getByTestId('model-card-yolo11-license-plate')).toBeInTheDocument();
      expect(screen.getByText('yolo11-license-plate')).toBeInTheDocument();
    });

    it('shows actual over estimated VRAM for a loaded model', () => {
      render(<ModelManagementPanel />);

      const card = screen.getByTestId('model-card-yolo11-license-plate');
      expect(within(card).getByText('287 MB')).toBeInTheDocument();
      expect(within(card).getByText('/ 300 MB')).toBeInTheDocument();
    });

    it('shows an estimate for an unloaded model', () => {
      render(<ModelManagementPanel />);

      const card = screen.getByTestId('model-card-yolo11-pose');
      expect(within(card).getByText('~250 MB')).toBeInTheDocument();
    });

    it('shows the load count only for models that have loaded', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('model-card-yolo11-license-plate')).toHaveTextContent('5 loads');
      expect(screen.getByTestId('model-card-yolo11-pose')).not.toHaveTextContent(/loads/);
    });

    it('marks a loaded model loaded', () => {
      render(<ModelManagementPanel />);

      const card = screen.getByTestId('model-card-yolo11-license-plate');
      expect(within(card).getByTestId('status-loaded')).toBeInTheDocument();
    });

    it('marks an enabled but unresident model unloaded', () => {
      render(<ModelManagementPanel />);

      const card = screen.getByTestId('model-card-yolo11-pose');
      expect(within(card).getByTestId('status-unloaded')).toBeInTheDocument();
    });

    it('marks a disabled model disabled', () => {
      render(<ModelManagementPanel />);

      const card = screen.getByTestId('model-card-yolo26-general');
      expect(within(card).getByTestId('status-disabled')).toBeInTheDocument();
    });

    it('marks a model with no runtime No data, not Unloaded', () => {
      // runtime:null means the enrichment service reported nothing. The old
      // enum forced it into 'unloaded' — a claim about GPU memory the backend
      // never made. [r130f]
      mockUseModels.mockReturnValue(
        modelsReturn({
          models: [{ ...MODELS[0], runtime: null }],
          data: { ...listResponse, models: [{ ...MODELS[0], runtime: null }] },
        })
      );
      render(<ModelManagementPanel />);

      const card = screen.getByTestId('model-card-yolo11-license-plate');
      expect(within(card).getByTestId('status-unknown')).toHaveTextContent('No data');
      expect(within(card).queryByTestId('status-unloaded')).not.toBeInTheDocument();
    });
  });

  describe('Empty model list with a live VRAM feed', () => {
    it('shows the empty state', () => {
      mockUseModels.mockReturnValue(modelsReturn({ models: [], data: undefined }));
      render(<ModelManagementPanel />);

      expect(screen.getByText('No models available')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading state when isLoading is true', () => {
      mockUseModels.mockReturnValue(modelsReturn({ isLoading: true, models: [], data: undefined }));
      render(<ModelManagementPanel />);

      expect(screen.getByText('Loading model status...')).toBeInTheDocument();
    });

    it('shows refetching indicator when isRefetching is true', () => {
      mockUseModels.mockReturnValue(modelsReturn({ isRefetching: true }));
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('refetch-indicator')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when error occurs', () => {
      mockUseModels.mockReturnValue(modelsReturn({ error: new Error('Models exploded') }));
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('error-message')).toBeInTheDocument();
      expect(screen.getByText('Models exploded')).toBeInTheDocument();
    });

    it('shows error styling', () => {
      mockUseModels.mockReturnValue(modelsReturn({ error: new Error('boom') }));
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('model-management-panel')).toHaveClass('border-red-800');
    });
  });

  describe('Empty State', () => {
    it('handles empty model list gracefully', () => {
      mockUseModels.mockReturnValue(modelsReturn({ models: [], data: undefined }));
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('model-management-panel')).toBeInTheDocument();
      expect(screen.getByText('No models available')).toBeInTheDocument();
    });
  });

  describe('Category Grouping', () => {
    it('groups models by category', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('category-detection')).toBeInTheDocument();
      expect(screen.getByTestId('category-pose')).toBeInTheDocument();
      expect(screen.getByTestId('category-embedding')).toBeInTheDocument();
    });

    it('shows model count per category', () => {
      render(<ModelManagementPanel />);

      const detection = screen.getByTestId('category-detection');
      // Three Detection models in the fixture (license-plate, face, yolo26),
      // two of them resident — the disabled one counts toward the total but not
      // the loaded figure.
      expect(within(detection).getByText('3 models (2 loaded)')).toBeInTheDocument();
    });
  });

  describe('Performance Metrics', () => {
    it('shows load count for loaded models', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('model-card-yolo11-face')).toHaveTextContent('3 loads');
    });
  });

  describe('Styling and Layout', () => {
    it('applies custom className', () => {
      render(<ModelManagementPanel className="custom-class" />);

      expect(screen.getByTestId('model-management-panel')).toHaveClass('custom-class');
    });

    it('renders with NVIDIA dark theme styling', () => {
      render(<ModelManagementPanel />);

      expect(screen.getByTestId('model-management-panel')).toBeInTheDocument();
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

      const card = screen.getByTestId('model-card-yolo11-license-plate');
      expect(within(card).getByLabelText('Status: Loaded')).toBeInTheDocument();
    });
  });

  describe('modelDisplayStatus (the derivation the fix turns on)', () => {
    it('derives loaded/unloaded/disabled/unknown from enabled + runtime', () => {
      expect(modelDisplayStatus(MODELS[0])).toBe('loaded'); // enabled, runtime.loaded
      expect(modelDisplayStatus(MODELS[2])).toBe('unloaded'); // enabled, not loaded
      expect(modelDisplayStatus(MODELS[4])).toBe('disabled'); // !enabled wins
      expect(modelDisplayStatus({ ...MODELS[0], runtime: null })).toBe('unknown');
    });

    it('lets a disabled model read disabled even if its runtime says loaded', () => {
      // Config beats runtime: the panel greys the card out either way, and a
      // model the operator disabled is not "loaded" for the operator's purpose.
      expect(
        modelDisplayStatus({
          ...MODELS[4],
          runtime: { loaded: true, actual_vram_mb: 500, last_used: null, load_count: 9 },
        })
      ).toBe('disabled');
    });

    it('is exhaustive: every derived state is one the summary renders', () => {
      // The summary's tiles always sum to Total because this function is total
      // over ModelStatus — no input falls through to a fifth bucket the summary
      // has no tile for. That is the property the golden spec re-asserts against
      // the live body.
      const produced = new Set(
        MODELS.flatMap((m) => [
          modelDisplayStatus(m),
          modelDisplayStatus({ ...m, runtime: null }),
          modelDisplayStatus({ ...m, enabled: false }),
        ])
      );
      // The four the fixture can reach, each of which has a summary tile.
      expect([...produced].sort()).toEqual(['disabled', 'loaded', 'unknown', 'unloaded']);
    });
  });
});
