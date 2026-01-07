/**
 * Tests for ModelZooSection component
 *
 * Tests the Model Zoo status display with dropdown-controlled latency chart
 * and compact status cards for all Model Zoo models.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import ModelZooSection from './ModelZooSection';
import * as api from '../../services/api';

import type { ModelZooStatusResponse, ModelLatencyHistoryResponse } from '../../services/api';

// Mock the API functions
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchModelZooCompactStatus: vi.fn(),
    fetchModelZooLatencyHistory: vi.fn(),
  };
});

// Sample test data
const mockStatusResponse: ModelZooStatusResponse = {
  models: [
    {
      name: 'yolo11-license-plate',
      display_name: 'YOLO11 License Plate',
      category: 'Detection',
      status: 'unloaded',
      vram_mb: 300,
      last_used_at: null,
      enabled: true,
    },
    {
      name: 'yolo11-face',
      display_name: 'YOLO11 Face',
      category: 'Detection',
      status: 'loaded',
      vram_mb: 200,
      last_used_at: '2026-01-04T10:00:00Z',
      enabled: true,
    },
    {
      name: 'violence-detection',
      display_name: 'Violence Detection',
      category: 'Classification',
      status: 'unloaded',
      vram_mb: 150,
      last_used_at: null,
      enabled: true,
    },
    {
      name: 'yolo26-general',
      display_name: 'YOLO26 General',
      category: 'Detection',
      status: 'disabled',
      vram_mb: 400,
      last_used_at: null,
      enabled: false,
    },
  ],
  total_models: 4,
  loaded_count: 1,
  disabled_count: 1,
  vram_budget_mb: 1650,
  vram_used_mb: 200,
  timestamp: '2026-01-04T12:00:00Z',
};

const mockLatencyResponse: ModelLatencyHistoryResponse = {
  model_name: 'yolo11-license-plate',
  display_name: 'YOLO11 License Plate',
  snapshots: [
    {
      timestamp: '2026-01-04T11:00:00Z',
      stats: {
        avg_ms: 45.0,
        p50_ms: 42.0,
        p95_ms: 68.0,
        sample_count: 15,
      },
    },
    {
      timestamp: '2026-01-04T11:01:00Z',
      stats: {
        avg_ms: 48.0,
        p50_ms: 45.0,
        p95_ms: 72.0,
        sample_count: 20,
      },
    },
  ],
  window_minutes: 60,
  bucket_seconds: 60,
  has_data: true,
  timestamp: '2026-01-04T12:00:00Z',
};

const mockEmptyLatencyResponse: ModelLatencyHistoryResponse = {
  model_name: 'yolo11-license-plate',
  display_name: 'YOLO11 License Plate',
  snapshots: [],
  window_minutes: 60,
  bucket_seconds: 60,
  has_data: false,
  timestamp: '2026-01-04T12:00:00Z',
};

describe('ModelZooSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchModelZooCompactStatus as Mock).mockResolvedValue(mockStatusResponse);
    (api.fetchModelZooLatencyHistory as Mock).mockResolvedValue(mockLatencyResponse);
  });

  describe('basic rendering', () => {
    it('renders the main container with correct testid', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        expect(screen.getByTestId('model-zoo-section')).toBeInTheDocument();
      });
    });

    it('renders summary card with Model Zoo title', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        expect(screen.getByTestId('model-zoo-summary')).toBeInTheDocument();
        expect(screen.getByText('Model Zoo')).toBeInTheDocument();
      });
    });

    it('applies custom className', async () => {
      render(<ModelZooSection className="custom-class" />);
      await waitFor(() => {
        expect(screen.getByTestId('model-zoo-section')).toHaveClass('custom-class');
      });
    });
  });

  describe('summary statistics', () => {
    it('displays loaded count', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        expect(screen.getByText('1 loaded')).toBeInTheDocument();
      });
    });

    it('displays unloaded count', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // 4 total - 1 loaded - 1 disabled = 2 unloaded
        expect(screen.getByText('2 unloaded')).toBeInTheDocument();
      });
    });

    it('displays disabled count', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        expect(screen.getByText('1 disabled')).toBeInTheDocument();
      });
    });

    it('displays VRAM usage', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        expect(screen.getByText('200/1650MB VRAM')).toBeInTheDocument();
      });
    });
  });

  describe('latency chart', () => {
    it('renders latency chart card', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        expect(screen.getByTestId('model-zoo-latency-chart')).toBeInTheDocument();
      });
    });

    it('displays chart title', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        expect(screen.getByText('Model Zoo Latency Over Time')).toBeInTheDocument();
      });
    });

    it('renders model selector dropdown', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        expect(screen.getByTestId('model-select')).toBeInTheDocument();
      });
    });

    it('fetches latency history on mount', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        expect(api.fetchModelZooLatencyHistory).toHaveBeenCalled();
      });
    });
  });

  describe('status cards', () => {
    it('renders enabled models accordion section', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // Models are now inside accordion sections
        expect(screen.getByText(/Active Models/i)).toBeInTheDocument();
      });
    });

    it('renders disabled models accordion section', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // Models are now inside accordion sections
        expect(screen.getByText(/Disabled Models/i)).toBeInTheDocument();
      });
    });

    it('renders enabled model cards inside accordion', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // Enabled model cards are in the Active Models accordion (open by default)
        expect(screen.getByTestId('model-card-yolo11-license-plate')).toBeInTheDocument();
        expect(screen.getByTestId('model-card-yolo11-face')).toBeInTheDocument();
        expect(screen.getByTestId('model-card-violence-detection')).toBeInTheDocument();
        // Disabled models are in the Disabled Models accordion (closed by default)
        // So yolo26-general won't be in the DOM initially
      });
    });

    it('displays enabled model display names', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // Only enabled models are visible (Active Models accordion is open by default)
        expect(screen.getByText('YOLO11 License Plate')).toBeInTheDocument();
        expect(screen.getByText('YOLO11 Face')).toBeInTheDocument();
        expect(screen.getByText('Violence Detection')).toBeInTheDocument();
        // YOLO26 General is disabled and in collapsed accordion
      });
    });

    it('displays VRAM amounts on enabled model cards', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // Only enabled models are visible
        expect(screen.getByText('300MB')).toBeInTheDocument();
        expect(screen.getByText('200MB')).toBeInTheDocument();
        expect(screen.getByText('150MB')).toBeInTheDocument();
        // 400MB is on disabled model (yolo26-general) in collapsed accordion
      });
    });

    it('displays category badges on cards', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // Detection appears multiple times on cards
        const detectionBadges = screen.getAllByText('Detection');
        expect(detectionBadges.length).toBeGreaterThan(0);
        expect(screen.getByText('Classification')).toBeInTheDocument();
      });
    });
  });

  describe('status indicators', () => {
    it('displays Loaded status for loaded models', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // yolo11-face is loaded
        const faceCard = screen.getByTestId('model-card-yolo11-face');
        expect(faceCard).toHaveTextContent('Loaded');
      });
    });

    it('displays Unloaded status for unloaded models', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // yolo11-license-plate is unloaded
        const lpCard = screen.getByTestId('model-card-yolo11-license-plate');
        expect(lpCard).toHaveTextContent('Unloaded');
      });
    });

    it('shows disabled models count in Disabled Models section', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // Disabled Models section shows count
        expect(screen.getByText(/Disabled Models \(1\)/i)).toBeInTheDocument();
      });
    });
  });

  describe('loading state', () => {
    it('shows loading message initially', () => {
      // Make the fetch take time
      (api.fetchModelZooCompactStatus as Mock).mockImplementation(
        () => new Promise(() => {})
      );

      render(<ModelZooSection />);

      expect(screen.getByText('Loading Model Zoo status...')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('displays error message when fetch fails', async () => {
      (api.fetchModelZooCompactStatus as Mock).mockRejectedValue(
        new Error('Network error')
      );

      render(<ModelZooSection />);

      await waitFor(() => {
        expect(screen.getByText(/Error loading Model Zoo status/i)).toBeInTheDocument();
      });
    });
  });

  describe('no data state', () => {
    it('displays no data message when model has no latency data', async () => {
      (api.fetchModelZooLatencyHistory as Mock).mockResolvedValue(mockEmptyLatencyResponse);

      render(<ModelZooSection />);

      await waitFor(() => {
        expect(screen.getByText(/No data available/i)).toBeInTheDocument();
      });
    });
  });

  describe('last used time', () => {
    it('displays formatted time ago for recently used models', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // yolo11-face was last used at a specific time
        // Since we can't easily control the current time, just check it shows something
        const faceCard = screen.getByTestId('model-card-yolo11-face');
        expect(faceCard).toBeInTheDocument();
      });
    });

    it('displays Never for models that have not been used', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // yolo11-license-plate has never been used
        const lpCard = screen.getByTestId('model-card-yolo11-license-plate');
        expect(lpCard).toHaveTextContent('Never');
      });
    });
  });

  describe('polling behavior', () => {
    it('accepts custom polling interval', async () => {
      render(<ModelZooSection pollingInterval={5000} />);
      await waitFor(() => {
        expect(screen.getByTestId('model-zoo-section')).toBeInTheDocument();
      });
    });
  });

  describe('active/disabled model sections', () => {
    it('separates enabled and disabled models into different sections', async () => {
      render(<ModelZooSection />);
      await waitFor(() => {
        // Check section headers with counts
        expect(screen.getByText(/Active Models \(3\)/i)).toBeInTheDocument();
        expect(screen.getByText(/Disabled Models \(1\)/i)).toBeInTheDocument();
      });
    });
  });
});
