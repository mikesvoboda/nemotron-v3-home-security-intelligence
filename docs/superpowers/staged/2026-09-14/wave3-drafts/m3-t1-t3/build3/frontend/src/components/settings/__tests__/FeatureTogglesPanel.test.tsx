import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import { useSettingsApi } from '../../../hooks/useSettingsApi';
import { renderWithProviders } from '../../../test-utils';
import FeatureTogglesPanel from '../FeatureTogglesPanel';

// Mock the useSettingsApi hook
vi.mock('../../../hooks/useSettingsApi', () => ({
  useSettingsApi: vi.fn(),
}));

const mockUseSettingsApi = useSettingsApi as Mock;

describe('FeatureTogglesPanel', () => {
  const mockSettings = {
    detection: {
      confidence_threshold: 0.5,
      fast_path_threshold: 0.9,
    },
    batch: {
      window_seconds: 90,
      idle_timeout_seconds: 30,
    },
    severity: {
      low_max: 29,
      medium_max: 59,
      high_max: 84,
    },
    features: {
      vision_extraction_enabled: true,
      reid_enabled: true,
      scene_change_enabled: false,
      clip_generation_enabled: true,
      image_quality_enabled: false,
      background_eval_enabled: true,
    },
    rate_limiting: {
      enabled: true,
      requests_per_minute: 60,
      burst_size: 10,
    },
    queue: {
      max_size: 10000,
      backpressure_threshold: 0.8,
    },
    retention: {
      days: 30,
      log_days: 7,
    },
  };

  const mockUpdateMutation = {
    mutateAsync: vi.fn().mockResolvedValue(mockSettings),
    isPending: false,
    isError: false,
    error: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSettingsApi.mockReturnValue({
      settings: mockSettings,
      isLoading: false,
      isError: false,
      error: null,
      updateMutation: mockUpdateMutation,
    });
  });

  describe('rendering', () => {
    it('renders the panel with title and description', () => {
      renderWithProviders(<FeatureTogglesPanel />);

      expect(screen.getByTestId('feature-toggles-panel')).toBeInTheDocument();
      expect(screen.getByText('Feature Toggles')).toBeInTheDocument();
      expect(screen.getByText('Enable or disable AI processing features')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      renderWithProviders(<FeatureTogglesPanel className="custom-class" />);

      const panel = screen.getByTestId('feature-toggles-panel');
      expect(panel).toHaveClass('custom-class');
    });

    it('renders all 6 feature toggles', () => {
      renderWithProviders(<FeatureTogglesPanel />);

      expect(screen.getByTestId('feature-toggle-vision_extraction_enabled')).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-reid_enabled')).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-scene_change_enabled')).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-clip_generation_enabled')).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-image_quality_enabled')).toBeInTheDocument();
      expect(screen.getByTestId('feature-toggle-background_eval_enabled')).toBeInTheDocument();
    });

    it('displays feature labels', () => {
      renderWithProviders(<FeatureTogglesPanel />);

      expect(screen.getByText('Vision Extraction')).toBeInTheDocument();
      expect(screen.getByText('Re-ID Tracking')).toBeInTheDocument();
      expect(screen.getByText('Scene Change Detection')).toBeInTheDocument();
      expect(screen.getByText('Clip Generation')).toBeInTheDocument();
      expect(screen.getByText('Image Quality Assessment')).toBeInTheDocument();
      expect(screen.getByText('Background Evaluation')).toBeInTheDocument();
    });

    it('displays feature descriptions', () => {
      renderWithProviders(<FeatureTogglesPanel />);

      expect(
        screen.getByText('Enable Florence-2 vision extraction for vehicle and person attributes')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Enable CLIP re-identification for tracking entities across cameras')
      ).toBeInTheDocument();
    });

    it('displays summary count of enabled features', () => {
      renderWithProviders(<FeatureTogglesPanel />);

      // 4 features are enabled in mockSettings
      expect(screen.getByTestId('feature-toggles-summary')).toHaveTextContent('4/6 enabled');
    });
  });

  describe('toggle state', () => {
    it('renders switches with correct initial state', () => {
      renderWithProviders(<FeatureTogglesPanel />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      const reidSwitch = screen.getByTestId('feature-toggle-reid_enabled-switch');
      const sceneSwitch = screen.getByTestId('feature-toggle-scene_change_enabled-switch');
      const clipSwitch = screen.getByTestId('feature-toggle-clip_generation_enabled-switch');
      const imageSwitch = screen.getByTestId('feature-toggle-image_quality_enabled-switch');
      const bgSwitch = screen.getByTestId('feature-toggle-background_eval_enabled-switch');

      // Check aria-checked for enabled features
      expect(visionSwitch).toHaveAttribute('aria-checked', 'true');
      expect(reidSwitch).toHaveAttribute('aria-checked', 'true');
      expect(clipSwitch).toHaveAttribute('aria-checked', 'true');
      expect(bgSwitch).toHaveAttribute('aria-checked', 'true');

      // Check aria-checked for disabled features
      expect(sceneSwitch).toHaveAttribute('aria-checked', 'false');
      expect(imageSwitch).toHaveAttribute('aria-checked', 'false');
    });

    it('calls updateMutation when toggle is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FeatureTogglesPanel />);

      const sceneSwitch = screen.getByTestId('feature-toggle-scene_change_enabled-switch');
      await user.click(sceneSwitch);

      expect(mockUpdateMutation.mutateAsync).toHaveBeenCalledWith({
        features: { scene_change_enabled: true },
      });
    });

    it('can toggle a feature off', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FeatureTogglesPanel />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      expect(visionSwitch).toHaveAttribute('aria-checked', 'true');

      await user.click(visionSwitch);

      expect(mockUpdateMutation.mutateAsync).toHaveBeenCalledWith({
        features: { vision_extraction_enabled: false },
      });
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton while fetching settings', () => {
      mockUseSettingsApi.mockReturnValue({
        settings: null,
        isLoading: true,
        isError: false,
        error: null,
        updateMutation: mockUpdateMutation,
      });

      renderWithProviders(<FeatureTogglesPanel />);

      expect(screen.getByTestId('feature-toggles-loading')).toBeInTheDocument();
      // Check for skeleton elements
      const skeletons = document.querySelectorAll('.skeleton');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('shows loading spinner on individual toggle when toggling', async () => {
      const user = userEvent.setup();
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockUpdateMutation.mutateAsync.mockImplementation(() => pendingPromise);

      renderWithProviders(<FeatureTogglesPanel />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      await user.click(visionSwitch);

      // Should show loading indicator
      await waitFor(() => {
        expect(
          screen.getByTestId('feature-toggle-vision_extraction_enabled-loading')
        ).toBeInTheDocument();
      });

      // Resolve the promise
      resolvePromise!(mockSettings);

      // Loading indicator should disappear
      await waitFor(() => {
        expect(
          screen.queryByTestId('feature-toggle-vision_extraction_enabled-loading')
        ).not.toBeInTheDocument();
      });
    });
  });

  describe('error state', () => {
    it('shows error message when settings fail to load', () => {
      mockUseSettingsApi.mockReturnValue({
        settings: null,
        isLoading: false,
        isError: true,
        error: new Error('Network error'),
        updateMutation: mockUpdateMutation,
      });

      renderWithProviders(<FeatureTogglesPanel />);

      expect(screen.getByTestId('feature-toggles-error')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('shows default error message when error has no message', () => {
      mockUseSettingsApi.mockReturnValue({
        settings: null,
        isLoading: false,
        isError: true,
        error: null,
        updateMutation: mockUpdateMutation,
      });

      renderWithProviders(<FeatureTogglesPanel />);

      expect(screen.getByTestId('feature-toggles-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load feature settings')).toBeInTheDocument();
    });

    it('shows mutation error when toggle update fails', () => {
      mockUseSettingsApi.mockReturnValue({
        settings: mockSettings,
        isLoading: false,
        isError: false,
        error: null,
        updateMutation: {
          ...mockUpdateMutation,
          isError: true,
          error: new Error('Failed to save'),
        },
      });

      renderWithProviders(<FeatureTogglesPanel />);

      expect(screen.getByTestId('feature-toggles-mutation-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to save')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('switches have proper aria-label attributes', () => {
      renderWithProviders(<FeatureTogglesPanel />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      expect(visionSwitch).toHaveAttribute('aria-label', 'Toggle Vision Extraction off');

      const sceneSwitch = screen.getByTestId('feature-toggle-scene_change_enabled-switch');
      expect(sceneSwitch).toHaveAttribute('aria-label', 'Toggle Scene Change Detection on');
    });

    it('switches have role="switch" attribute', () => {
      renderWithProviders(<FeatureTogglesPanel />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      expect(visionSwitch).toHaveAttribute('role', 'switch');
    });

    it('labels are associated with switches via htmlFor', () => {
      renderWithProviders(<FeatureTogglesPanel />);

      // Labels use htmlFor to associate with switch id
      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      expect(visionSwitch).toHaveAttribute('id', 'toggle-vision_extraction_enabled');

      // Click the label text should focus/toggle the switch
      const visionLabel = screen.getByText('Vision Extraction');
      expect(visionLabel.tagName.toLowerCase()).toBe('label');
      expect(visionLabel).toHaveAttribute('for', 'toggle-vision_extraction_enabled');
    });

    it('switch is disabled while toggling', async () => {
      const user = userEvent.setup();
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });

      mockUpdateMutation.mutateAsync.mockImplementation(() => pendingPromise);

      renderWithProviders(<FeatureTogglesPanel />);

      const visionSwitch = screen.getByTestId('feature-toggle-vision_extraction_enabled-switch');
      await user.click(visionSwitch);

      // Should be disabled while toggling
      await waitFor(() => {
        expect(visionSwitch).toHaveClass('opacity-50');
      });

      // Resolve the promise
      resolvePromise!(mockSettings);

      // Should be enabled again
      await waitFor(() => {
        expect(visionSwitch).not.toHaveClass('opacity-50');
      });
    });
  });

  describe('summary count', () => {
    it('shows correct count when all features are enabled', () => {
      const allEnabledSettings = {
        ...mockSettings,
        features: {
          vision_extraction_enabled: true,
          reid_enabled: true,
          scene_change_enabled: true,
          clip_generation_enabled: true,
          image_quality_enabled: true,
          background_eval_enabled: true,
        },
      };

      mockUseSettingsApi.mockReturnValue({
        settings: allEnabledSettings,
        isLoading: false,
        isError: false,
        error: null,
        updateMutation: mockUpdateMutation,
      });

      renderWithProviders(<FeatureTogglesPanel />);

      expect(screen.getByTestId('feature-toggles-summary')).toHaveTextContent('6/6 enabled');
    });

    it('shows correct count when all features are disabled', () => {
      const allDisabledSettings = {
        ...mockSettings,
        features: {
          vision_extraction_enabled: false,
          reid_enabled: false,
          scene_change_enabled: false,
          clip_generation_enabled: false,
          image_quality_enabled: false,
          background_eval_enabled: false,
        },
      };

      mockUseSettingsApi.mockReturnValue({
        settings: allDisabledSettings,
        isLoading: false,
        isError: false,
        error: null,
        updateMutation: mockUpdateMutation,
      });

      renderWithProviders(<FeatureTogglesPanel />);

      expect(screen.getByTestId('feature-toggles-summary')).toHaveTextContent('0/6 enabled');
    });
  });

  describe('multiple toggle interactions', () => {
    it('can toggle multiple features in sequence', async () => {
      const user = userEvent.setup();
      renderWithProviders(<FeatureTogglesPanel />);

      const sceneSwitch = screen.getByTestId('feature-toggle-scene_change_enabled-switch');
      const imageSwitch = screen.getByTestId('feature-toggle-image_quality_enabled-switch');

      await user.click(sceneSwitch);
      expect(mockUpdateMutation.mutateAsync).toHaveBeenCalledWith({
        features: { scene_change_enabled: true },
      });

      await user.click(imageSwitch);
      expect(mockUpdateMutation.mutateAsync).toHaveBeenCalledWith({
        features: { image_quality_enabled: true },
      });

      expect(mockUpdateMutation.mutateAsync).toHaveBeenCalledTimes(2);
    });
  });
});
