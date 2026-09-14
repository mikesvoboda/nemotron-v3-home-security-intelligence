/**
 * CalibrationPanel test suite
 *
 * Tests the CalibrationPanel component for the Settings page.
 *
 * @see NEM-2355 - Create CalibrationPanel component for Settings page
 * @see NEM-2356 - Add CalibrationPanel to Settings page
 */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import CalibrationPanel from './CalibrationPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchCalibration: vi.fn(),
  fetchCalibrationDefaults: vi.fn(),
  fetchFeedbackStats: vi.fn(),
  updateCalibration: vi.fn(),
  resetCalibration: vi.fn(),
}));

// Default mock data
const mockCalibration: api.CalibrationResponse = {
  id: 1,
  user_id: 'default',
  low_threshold: 30,
  medium_threshold: 60,
  high_threshold: 85,
  decay_factor: 0.1,
  false_positive_count: 5,
  missed_threat_count: 3,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockDefaults: api.CalibrationDefaultsResponse = {
  low_threshold: 30,
  medium_threshold: 60,
  high_threshold: 85,
  decay_factor: 0.1,
};

const mockFeedbackStats: api.FeedbackStatsResponse = {
  total_feedback: 10,
  by_type: {
    false_positive: 5,
    missed_detection: 3,
    correct: 2,
  },
  by_camera: {
    front_door: 6,
    back_yard: 4,
  },
};

describe('CalibrationPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Set up default mock implementations
    vi.mocked(api.fetchCalibration).mockResolvedValue(mockCalibration);
    vi.mocked(api.fetchCalibrationDefaults).mockResolvedValue(mockDefaults);
    vi.mocked(api.fetchFeedbackStats).mockResolvedValue(mockFeedbackStats);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the component', () => {
      render(<CalibrationPanel />);

      expect(screen.getByTestId('calibration-panel')).toBeInTheDocument();
    });

    it('renders the introduction card with title', () => {
      render(<CalibrationPanel />);

      expect(screen.getByText('AI Calibration')).toBeInTheDocument();
    });

    it('renders the introduction card description', () => {
      render(<CalibrationPanel />);

      expect(
        screen.getByText(/Fine-tune how the AI classifies security events/)
      ).toBeInTheDocument();
    });

    it('renders the How It Works section', () => {
      render(<CalibrationPanel />);

      expect(screen.getByText('How Calibration Works')).toBeInTheDocument();
    });

    it('renders all three feature cards', () => {
      render(<CalibrationPanel />);

      expect(screen.getByText('Threshold Adjustment')).toBeInTheDocument();
      expect(screen.getByText('Feedback Learning')).toBeInTheDocument();
      expect(screen.getByText('Learning Rate')).toBeInTheDocument();
    });

    it('renders RiskSensitivitySettings component', async () => {
      render(<CalibrationPanel />);

      await waitFor(() => {
        expect(screen.getByText('Risk Sensitivity')).toBeInTheDocument();
      });
    });

    it('renders the Tips section', () => {
      render(<CalibrationPanel />);

      expect(screen.getByText('Tips for Effective Calibration')).toBeInTheDocument();
    });

    it('renders all tips', () => {
      render(<CalibrationPanel />);

      expect(screen.getByText(/Start with defaults/)).toBeInTheDocument();
      expect(screen.getByText(/Provide consistent feedback/)).toBeInTheDocument();
      expect(screen.getByText(/Lower thresholds for more alerts/)).toBeInTheDocument();
      expect(screen.getByText(/Use a slower learning rate/)).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<CalibrationPanel className="custom-class" />);

      expect(screen.getByTestId('calibration-panel')).toHaveClass('custom-class');
    });

    it('renders with data-testid attribute', () => {
      render(<CalibrationPanel />);

      expect(screen.getByTestId('calibration-panel')).toBeInTheDocument();
    });
  });

  describe('RiskSensitivitySettings integration', () => {
    it('shows loading skeleton initially in RiskSensitivitySettings', () => {
      render(<CalibrationPanel />);

      expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
    });

    it('renders threshold sliders after loading', async () => {
      render(<CalibrationPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
        expect(screen.getByTestId('medium-threshold-slider')).toBeInTheDocument();
        expect(screen.getByTestId('high-threshold-slider')).toBeInTheDocument();
        expect(screen.getByTestId('learning-rate-slider')).toBeInTheDocument();
      });
    });

    it('displays threshold values from API', async () => {
      render(<CalibrationPanel />);

      await waitFor(() => {
        expect(screen.getByText('30')).toBeInTheDocument(); // low threshold
        expect(screen.getByText('60')).toBeInTheDocument(); // medium threshold
        expect(screen.getByText('85')).toBeInTheDocument(); // high threshold
      });
    });
  });

  describe('error handling', () => {
    it('displays error message when API fails', async () => {
      vi.mocked(api.fetchCalibration).mockRejectedValue(new Error('Failed to load'));

      render(<CalibrationPanel />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load')).toBeInTheDocument();
      });
    });
  });

  describe('feature card descriptions', () => {
    it('shows threshold adjustment description', () => {
      render(<CalibrationPanel />);

      expect(screen.getByText(/Set the risk score boundaries that determine/)).toBeInTheDocument();
    });

    it('shows feedback learning description', () => {
      render(<CalibrationPanel />);

      expect(
        screen.getByText(/Your feedback on event accuracy helps the system learn/)
      ).toBeInTheDocument();
    });

    it('shows learning rate description', () => {
      render(<CalibrationPanel />);

      expect(
        screen.getByText(/Control how quickly thresholds adapt based on feedback/)
      ).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has proper structure with multiple sections', () => {
      render(<CalibrationPanel />);

      // Check that main content sections exist
      // Tremor Title components render as h3 by default
      expect(screen.getByText('AI Calibration')).toBeInTheDocument();
      expect(screen.getByText('How Calibration Works')).toBeInTheDocument();
      expect(screen.getByText('Tips for Effective Calibration')).toBeInTheDocument();
    });
  });
});
