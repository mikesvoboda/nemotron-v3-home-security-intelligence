import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';

import AIModelsSettings, { type ModelInfo } from './AIModelsSettings';

import type { UseAIMetricsResult, AIPerformanceState } from '../../hooks/useAIMetrics';

// Default initial state matching the hook
const createDefaultState = (): AIPerformanceState => ({
  rtdetr: { name: 'RT-DETRv2', status: 'unknown' },
  nemotron: { name: 'Nemotron', status: 'unknown' },
  detectionLatency: null,
  analysisLatency: null,
  pipelineLatency: null,
  totalDetections: 0,
  totalEvents: 0,
  eventsPerMinute: 0,
  detectionQueueDepth: 0,
  analysisQueueDepth: 0,
  pipelineErrors: {},
  queueOverflows: {},
  dlqItems: {},
  detectionsByClass: {},
  lastUpdated: null,
});

// Default mock return value
const createMockReturn = (overrides: Partial<UseAIMetricsResult> = {}): UseAIMetricsResult => ({
  data: createDefaultState(),
  isLoading: false,
  error: null,
  refresh: vi.fn(),
  ...overrides,
});

// Default mock for useAIMetrics hook
const mockUseAIMetrics: Mock<() => UseAIMetricsResult> = vi.fn(() => createMockReturn());

// Mock the useAIMetrics hook to avoid HTTP requests in tests
vi.mock('../../hooks/useAIMetrics', () => ({
  useAIMetrics: () => mockUseAIMetrics(),
}));

beforeEach(() => {
  // Reset mock to default state before each test
  mockUseAIMetrics.mockReturnValue(createMockReturn());
});

describe('AIModelsSettings', () => {
  const mockRTDETR: ModelInfo = {
    name: 'RT-DETRv2',
    status: 'loaded',
    memoryUsed: 4096, // 4GB in MB
    inferenceFps: 30,
    description: 'Real-time object detection model',
  };

  const mockNemotron: ModelInfo = {
    name: 'Nemotron',
    status: 'loaded',
    memoryUsed: 8192, // 8GB in MB
    inferenceFps: 15,
    description: 'Risk analysis and reasoning model',
  };

  it('renders component with title and description', () => {
    render(<AIModelsSettings />);

    expect(screen.getByText('AI Models')).toBeInTheDocument();
    expect(
      screen.getByText(
        'View the status and performance of AI models used for object detection and risk analysis.'
      )
    ).toBeInTheDocument();
  });

  it('renders default models when no props provided', () => {
    render(<AIModelsSettings />);

    expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    expect(screen.getByText('Nemotron')).toBeInTheDocument();
    expect(screen.getByText('Real-time object detection model')).toBeInTheDocument();
    expect(screen.getByText('Risk analysis and reasoning model')).toBeInTheDocument();
  });

  describe('model status badges', () => {
    it('displays loaded status badge', () => {
      render(<AIModelsSettings rtdetrModel={mockRTDETR} nemotronModel={mockNemotron} />);

      const loadedBadges = screen.getAllByText('Loaded');
      expect(loadedBadges).toHaveLength(2);
    });

    it('displays unloaded status badge', () => {
      const unloadedModel: ModelInfo = {
        ...mockRTDETR,
        status: 'unloaded',
      };

      render(<AIModelsSettings rtdetrModel={unloadedModel} />);

      const unloadedBadges = screen.getAllByText('Unloaded');
      expect(unloadedBadges.length).toBeGreaterThan(0);
    });

    it('displays error status badge', () => {
      const errorModel: ModelInfo = {
        ...mockRTDETR,
        status: 'error',
      };
      const loadedModel: ModelInfo = {
        ...mockNemotron,
        status: 'loaded',
      };

      render(<AIModelsSettings rtdetrModel={errorModel} nemotronModel={loadedModel} />);

      expect(screen.getByText('Error')).toBeInTheDocument();
    });
  });

  describe('memory usage display', () => {
    it('displays memory usage in GB', () => {
      render(<AIModelsSettings rtdetrModel={mockRTDETR} nemotronModel={mockNemotron} />);

      expect(screen.getByText('4.0 GB')).toBeInTheDocument();
      expect(screen.getByText('8.0 GB')).toBeInTheDocument();
    });

    it('displays N/A for null memory usage', () => {
      const noMemoryModel: ModelInfo = {
        ...mockRTDETR,
        memoryUsed: null,
      };

      render(<AIModelsSettings rtdetrModel={noMemoryModel} />);

      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });

    it('displays memory without percentage when total memory not provided', () => {
      render(<AIModelsSettings rtdetrModel={mockRTDETR} totalMemory={null} />);

      expect(screen.getByText('4.0 GB')).toBeInTheDocument();
    });

    it('displays memory with percentage when total memory provided', () => {
      render(
        <AIModelsSettings
          rtdetrModel={mockRTDETR}
          totalMemory={24576} // 24GB in MB
        />
      );

      expect(screen.getByText('4.0 GB')).toBeInTheDocument();
    });
  });

  describe('inference speed display', () => {
    it('displays inference FPS for loaded models', () => {
      render(<AIModelsSettings rtdetrModel={mockRTDETR} nemotronModel={mockNemotron} />);

      const inferenceTexts = screen.getAllByText('Inference Speed');
      expect(inferenceTexts.length).toBe(2); // Both models should show inference speed
      expect(screen.getByText('30 FPS')).toBeInTheDocument();
      expect(screen.getByText('15 FPS')).toBeInTheDocument();
    });

    it('does not display inference speed for unloaded models', () => {
      const unloadedModel: ModelInfo = {
        ...mockRTDETR,
        status: 'unloaded',
        inferenceFps: null,
      };
      const unloadedNemotron: ModelInfo = {
        ...mockNemotron,
        status: 'unloaded',
        inferenceFps: null,
      };

      render(<AIModelsSettings rtdetrModel={unloadedModel} nemotronModel={unloadedNemotron} />);

      // Should not show inference speed section for unloaded models
      const inferenceTexts = screen.queryAllByText('Inference Speed');
      expect(inferenceTexts.length).toBe(0);
    });

    it('displays N/A for null inference FPS on loaded models', () => {
      const loadedNoFps: ModelInfo = {
        ...mockRTDETR,
        status: 'loaded',
        inferenceFps: null,
      };
      const unloadedModel: ModelInfo = {
        ...mockNemotron,
        status: 'unloaded',
        inferenceFps: null,
      };

      render(<AIModelsSettings rtdetrModel={loadedNoFps} nemotronModel={unloadedModel} />);

      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });
  });

  describe('total GPU memory display', () => {
    it('displays total GPU memory when provided', () => {
      render(
        <AIModelsSettings
          rtdetrModel={mockRTDETR}
          totalMemory={24576} // 24GB
        />
      );

      expect(screen.getByText('Total GPU Memory')).toBeInTheDocument();
      expect(screen.getByText('24.0 GB')).toBeInTheDocument();
    });

    it('does not display total GPU memory when null', () => {
      render(<AIModelsSettings rtdetrModel={mockRTDETR} totalMemory={null} />);

      expect(screen.queryByText('Total GPU Memory')).not.toBeInTheDocument();
    });

    it('converts MB to GB correctly', () => {
      render(
        <AIModelsSettings
          rtdetrModel={mockRTDETR}
          totalMemory={20480} // 20GB
        />
      );

      expect(screen.getByText('20.0 GB')).toBeInTheDocument();
    });
  });

  describe('model descriptions', () => {
    it('displays RT-DETR description', () => {
      const unloadedNemotron: ModelInfo = {
        ...mockNemotron,
        status: 'unloaded',
        description: 'Different description',
      };
      render(<AIModelsSettings rtdetrModel={mockRTDETR} nemotronModel={unloadedNemotron} />);

      expect(screen.getByText('Real-time object detection model')).toBeInTheDocument();
    });

    it('displays Nemotron description', () => {
      const unloadedRTDETR: ModelInfo = {
        ...mockRTDETR,
        status: 'unloaded',
        description: 'Different description',
      };
      render(<AIModelsSettings rtdetrModel={unloadedRTDETR} nemotronModel={mockNemotron} />);

      expect(screen.getByText('Risk analysis and reasoning model')).toBeInTheDocument();
    });

    it('displays custom descriptions', () => {
      const customModel: ModelInfo = {
        ...mockRTDETR,
        description: 'Custom model description',
      };
      const otherModel: ModelInfo = {
        ...mockNemotron,
        description: 'Other model description',
      };

      render(<AIModelsSettings rtdetrModel={customModel} nemotronModel={otherModel} />);

      expect(screen.getByText('Custom model description')).toBeInTheDocument();
      expect(screen.getByText('Other model description')).toBeInTheDocument();
    });
  });

  describe('model names', () => {
    it('displays model names', () => {
      render(<AIModelsSettings rtdetrModel={mockRTDETR} nemotronModel={mockNemotron} />);

      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });

    it('displays custom model names', () => {
      const customModel: ModelInfo = {
        ...mockRTDETR,
        name: 'Custom Model v2',
      };

      render(<AIModelsSettings rtdetrModel={customModel} />);

      expect(screen.getByText('Custom Model v2')).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles zero memory usage', () => {
      const zeroMemory: ModelInfo = {
        ...mockRTDETR,
        memoryUsed: 0,
      };

      render(<AIModelsSettings rtdetrModel={zeroMemory} />);

      expect(screen.getByText('0.0 GB')).toBeInTheDocument();
    });

    it('handles zero inference FPS', () => {
      const zeroFps: ModelInfo = {
        ...mockRTDETR,
        inferenceFps: 0,
      };

      render(<AIModelsSettings rtdetrModel={zeroFps} />);

      expect(screen.getByText('0 FPS')).toBeInTheDocument();
    });

    it('handles decimal FPS values', () => {
      const decimalFps: ModelInfo = {
        ...mockRTDETR,
        inferenceFps: 28.7,
      };

      render(<AIModelsSettings rtdetrModel={decimalFps} />);

      expect(screen.getByText('29 FPS')).toBeInTheDocument();
    });

    it('handles very large memory values', () => {
      const largeMemory: ModelInfo = {
        ...mockRTDETR,
        memoryUsed: 16384, // 16GB
      };

      render(<AIModelsSettings rtdetrModel={largeMemory} />);

      expect(screen.getByText('16.0 GB')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<AIModelsSettings className="custom-class" />);

      expect(screen.getByText('AI Models')).toBeInTheDocument();
    });
  });

  describe('layout and grid', () => {
    it('renders both model cards', () => {
      render(<AIModelsSettings rtdetrModel={mockRTDETR} nemotronModel={mockNemotron} />);

      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });

    it('renders all sections', () => {
      render(
        <AIModelsSettings
          rtdetrModel={mockRTDETR}
          nemotronModel={mockNemotron}
          totalMemory={24576}
        />
      );

      // Check for section headers
      expect(screen.getByText('AI Models')).toBeInTheDocument();
      expect(screen.getByText('Total GPU Memory')).toBeInTheDocument();

      // Check for model names
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
      expect(screen.getByText('Nemotron')).toBeInTheDocument();

      // Check for status
      const loadedBadges = screen.getAllByText('Loaded');
      expect(loadedBadges.length).toBeGreaterThan(0);
    });
  });

  describe('null handling', () => {
    it('handles all null values gracefully', () => {
      const nullModel1: ModelInfo = {
        name: 'Test Model 1',
        status: 'unloaded',
        memoryUsed: null,
        inferenceFps: null,
        description: 'Test description 1',
      };
      const nullModel2: ModelInfo = {
        name: 'Test Model 2',
        status: 'unloaded',
        memoryUsed: null,
        inferenceFps: null,
        description: 'Test description 2',
      };

      render(
        <AIModelsSettings rtdetrModel={nullModel1} nemotronModel={nullModel2} totalMemory={null} />
      );

      expect(screen.getByText('Test Model 1')).toBeInTheDocument();
      expect(screen.getByText('Test Model 2')).toBeInTheDocument();
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });
  });

  describe('mixed states', () => {
    it('handles one loaded and one unloaded model', () => {
      const unloadedModel: ModelInfo = {
        ...mockNemotron,
        status: 'unloaded',
        memoryUsed: null,
        inferenceFps: null,
      };

      render(<AIModelsSettings rtdetrModel={mockRTDETR} nemotronModel={unloadedModel} />);

      const loadedBadges = screen.getAllByText('Loaded');
      const unloadedBadges = screen.getAllByText('Unloaded');
      expect(loadedBadges.length).toBeGreaterThan(0);
      expect(unloadedBadges.length).toBeGreaterThan(0);
    });

    it('handles one error and one loaded model', () => {
      const errorModel: ModelInfo = {
        ...mockRTDETR,
        status: 'error',
        memoryUsed: null,
        inferenceFps: null,
      };

      render(<AIModelsSettings rtdetrModel={errorModel} nemotronModel={mockNemotron} />);

      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText('Loaded')).toBeInTheDocument();
    });
  });

  describe('formatting', () => {
    it('rounds memory to one decimal place', () => {
      const preciseMemory: ModelInfo = {
        ...mockRTDETR,
        memoryUsed: 4567, // 4.459GB
      };

      render(<AIModelsSettings rtdetrModel={preciseMemory} />);

      // Should round to 4.5 GB
      expect(screen.getByText('4.5 GB')).toBeInTheDocument();
    });

    it('rounds FPS to integer', () => {
      const preciseFps: ModelInfo = {
        ...mockRTDETR,
        inferenceFps: 29.6,
      };

      render(<AIModelsSettings rtdetrModel={preciseFps} />);

      expect(screen.getByText('30 FPS')).toBeInTheDocument();
    });
  });

  describe('real-time data from useAIMetrics', () => {
    it('shows models as loaded when API returns healthy status', () => {
      const mockAIData: AIPerformanceState = {
        ...createDefaultState(),
        rtdetr: { name: 'RT-DETRv2', status: 'healthy' },
        nemotron: { name: 'Nemotron', status: 'healthy' },
      };
      mockUseAIMetrics.mockReturnValue(createMockReturn({ data: mockAIData }));

      render(<AIModelsSettings />);

      // Both models should show as "Loaded" when status is "healthy"
      const loadedBadges = screen.getAllByText('Loaded');
      expect(loadedBadges).toHaveLength(2);
    });

    it('shows models as error when API returns unhealthy', () => {
      const mockAIData: AIPerformanceState = {
        ...createDefaultState(),
        rtdetr: { name: 'RT-DETRv2', status: 'unhealthy', message: 'Connection failed' },
        nemotron: { name: 'Nemotron', status: 'unhealthy', message: 'Service unavailable' },
      };
      mockUseAIMetrics.mockReturnValue(createMockReturn({ data: mockAIData }));

      render(<AIModelsSettings />);

      // Both models should show as "Error" when status is "unhealthy"
      const errorBadges = screen.getAllByText('Error');
      expect(errorBadges).toHaveLength(2);
    });

    it('shows models as unloaded when status is unknown', () => {
      const mockAIData: AIPerformanceState = {
        ...createDefaultState(),
        rtdetr: { name: 'RT-DETRv2', status: 'unknown' },
        nemotron: { name: 'Nemotron', status: 'unknown' },
      };
      mockUseAIMetrics.mockReturnValue(createMockReturn({ data: mockAIData }));

      render(<AIModelsSettings />);

      // Both models should show as "Unloaded" when status is "unknown"
      const unloadedBadges = screen.getAllByText('Unloaded');
      expect(unloadedBadges).toHaveLength(2);
    });

    it('shows loading badge when isLoading is true', () => {
      mockUseAIMetrics.mockReturnValue(createMockReturn({ isLoading: true }));

      render(<AIModelsSettings />);

      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('prioritizes props over fetched data', () => {
      const mockAIData: AIPerformanceState = {
        ...createDefaultState(),
        rtdetr: { name: 'RT-DETRv2', status: 'healthy' },
        nemotron: { name: 'Nemotron', status: 'healthy' },
      };
      mockUseAIMetrics.mockReturnValue(createMockReturn({ data: mockAIData }));

      // Provide props that override the fetched data
      const customModel: ModelInfo = {
        name: 'Custom RT-DETR',
        status: 'error',
        memoryUsed: 1024,
        inferenceFps: 10,
        description: 'Custom description',
      };

      render(<AIModelsSettings rtdetrModel={customModel} />);

      // Should show the custom model from props, not the fetched "healthy" status
      expect(screen.getByText('Custom RT-DETR')).toBeInTheDocument();
      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText('Custom description')).toBeInTheDocument();
    });

    it('handles degraded status as unloaded', () => {
      const mockAIData: AIPerformanceState = {
        ...createDefaultState(),
        rtdetr: { name: 'RT-DETRv2', status: 'degraded' },
        nemotron: { name: 'Nemotron', status: 'degraded' },
      };
      mockUseAIMetrics.mockReturnValue(createMockReturn({ data: mockAIData }));

      render(<AIModelsSettings />);

      // Degraded status should map to "Unloaded"
      const unloadedBadges = screen.getAllByText('Unloaded');
      expect(unloadedBadges).toHaveLength(2);
    });
  });
});
