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
  missed_detection_count: 3,
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
    it('renders the component with title', () => {
      render(<CalibrationPanel />);

      expect(screen.getByText('AI Calibration Settings')).toBeInTheDocument();
    });

    it('renders the info card with calibration explanation', () => {
      render(<CalibrationPanel />);

      expect(screen.getByText('How Calibration Works')).toBeInTheDocument();
      expect(screen.getByText(/Thresholds/)).toBeInTheDocument();
      expect(screen.getByText(/Learning Rate/)).toBeInTheDocument();
      expect(screen.getByText(/Feedback/)).toBeInTheDocument();
    });

    it('renders RiskSensitivitySettings component', async () => {
      render(<CalibrationPanel />);

      await waitFor(() => {
        expect(screen.getByText('Risk Sensitivity')).toBeInTheDocument();
      });
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

  describe('description text', () => {
    it('displays descriptive subtitle', () => {
      render(<CalibrationPanel />);

      expect(
        screen.getByText(/Fine-tune how the AI system categorizes risk scores/)
      ).toBeInTheDocument();
    });
  });
});
