import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import RiskSensitivitySettings from './RiskSensitivitySettings';
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

describe('RiskSensitivitySettings', () => {
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
    it('renders the component with title', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByText('Risk Sensitivity')).toBeInTheDocument();
      });
    });

    it('shows loading skeleton initially', () => {
      render(<RiskSensitivitySettings />);

      expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
    });

    it('renders all threshold sliders after loading', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
        expect(screen.getByTestId('medium-threshold-slider')).toBeInTheDocument();
        expect(screen.getByTestId('high-threshold-slider')).toBeInTheDocument();
        expect(screen.getByTestId('learning-rate-slider')).toBeInTheDocument();
      });
    });

    it('displays current threshold values', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByText('30')).toBeInTheDocument(); // low threshold
        expect(screen.getByText('60')).toBeInTheDocument(); // medium threshold
        expect(screen.getByText('85')).toBeInTheDocument(); // high threshold
        expect(screen.getByText('0.10')).toBeInTheDocument(); // decay factor
      });
    });

    it('displays feedback count', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        // Total feedback = false_positive_count + missed_threat_count = 5 + 3 = 8
        expect(screen.getByText('8')).toBeInTheDocument();
        expect(screen.getByText(/feedback submissions/)).toBeInTheDocument();
      });
    });

    it('displays feedback statistics', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        // Feedback stats labels
        expect(screen.getByText('False positives marked')).toBeInTheDocument();
        expect(screen.getByText('Missed detections marked')).toBeInTheDocument();
      });
    });

    it('applies custom className', async () => {
      render(<RiskSensitivitySettings className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('risk-sensitivity-settings')).toHaveClass('custom-class');
      });
    });
  });

  describe('error handling', () => {
    it('displays error message when API fails', async () => {
      vi.mocked(api.fetchCalibration).mockRejectedValue(new Error('Failed to load'));

      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load')).toBeInTheDocument();
      });
    });

    it('handles feedback stats failure gracefully', async () => {
      vi.mocked(api.fetchFeedbackStats).mockRejectedValue(new Error('Stats failed'));

      render(<RiskSensitivitySettings />);

      // Should still render, just without stats breakdown
      await waitFor(() => {
        expect(screen.getByText('Risk Sensitivity')).toBeInTheDocument();
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
      });
    });
  });

  describe('threshold validation', () => {
    it('shows validation error when low >= medium', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
      });

      // Change low threshold to be >= medium (60)
      const lowSlider = screen.getByLabelText('Low to Medium threshold');
      fireEvent.change(lowSlider, { target: { value: '65' } });

      await waitFor(() => {
        expect(
          screen.getByText(/Low threshold \(65\) must be less than Medium threshold \(60\)/)
        ).toBeInTheDocument();
      });
    });

    it('shows validation error when medium >= high', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('medium-threshold-slider')).toBeInTheDocument();
      });

      // Change medium threshold to be >= high (85)
      const mediumSlider = screen.getByLabelText('Medium to High threshold');
      fireEvent.change(mediumSlider, { target: { value: '90' } });

      await waitFor(() => {
        expect(
          screen.getByText(/Medium threshold \(90\) must be less than High threshold \(85\)/)
        ).toBeInTheDocument();
      });
    });

    it('disables save button when validation error exists', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
      });

      // Create validation error
      const lowSlider = screen.getByLabelText('Low to Medium threshold');
      fireEvent.change(lowSlider, { target: { value: '65' } });

      await waitFor(() => {
        const saveButton = screen.getByRole('button', { name: /Save Changes/i });
        expect(saveButton).toBeDisabled();
      });
    });
  });

  describe('saving changes', () => {
    it('enables save button when there are unsaved changes', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
      });

      // Initially save button should be disabled (no changes)
      expect(screen.getByRole('button', { name: /Save Changes/i })).toBeDisabled();

      // Change a value
      const lowSlider = screen.getByLabelText('Low to Medium threshold');
      fireEvent.change(lowSlider, { target: { value: '25' } });

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Save Changes/i })).not.toBeDisabled();
      });
    });

    it('calls updateCalibration when save is clicked', async () => {
      const mockUpdate = vi.mocked(api.updateCalibration);
      mockUpdate.mockResolvedValue({
        ...mockCalibration,
        low_threshold: 25,
      });

      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
      });

      // Change a value
      const lowSlider = screen.getByLabelText('Low to Medium threshold');
      fireEvent.change(lowSlider, { target: { value: '25' } });

      // Click save
      const saveButton = screen.getByRole('button', { name: /Save Changes/i });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(mockUpdate).toHaveBeenCalledWith({
          low_threshold: 25,
          medium_threshold: 60,
          high_threshold: 85,
          decay_factor: 0.1,
        });
      });
    });

    it('shows success message after saving', async () => {
      vi.mocked(api.updateCalibration).mockResolvedValue({
        ...mockCalibration,
        low_threshold: 25,
      });

      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
      });

      // Change and save
      const lowSlider = screen.getByLabelText('Low to Medium threshold');
      fireEvent.change(lowSlider, { target: { value: '25' } });
      fireEvent.click(screen.getByRole('button', { name: /Save Changes/i }));

      await waitFor(() => {
        expect(screen.getByText('Settings saved successfully!')).toBeInTheDocument();
      });
    });

    it('shows error message when save fails', async () => {
      vi.mocked(api.updateCalibration).mockRejectedValue(new Error('Save failed'));

      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
      });

      // Change and try to save
      const lowSlider = screen.getByLabelText('Low to Medium threshold');
      fireEvent.change(lowSlider, { target: { value: '25' } });
      fireEvent.click(screen.getByRole('button', { name: /Save Changes/i }));

      await waitFor(() => {
        expect(screen.getByText('Save failed')).toBeInTheDocument();
      });
    });
  });

  describe('discarding changes', () => {
    it('reverts to original values when discard is clicked', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
      });

      // Change a value
      const lowSlider = screen.getByLabelText('Low to Medium threshold');
      fireEvent.change(lowSlider, { target: { value: '25' } });

      // Verify value changed
      await waitFor(() => {
        expect(screen.getByText('25')).toBeInTheDocument();
      });

      // Click discard
      fireEvent.click(screen.getByRole('button', { name: /Discard/i }));

      // Verify value reverted
      await waitFor(() => {
        expect(screen.getByText('30')).toBeInTheDocument(); // original low threshold
      });
    });
  });

  describe('reset to defaults', () => {
    it('calls resetCalibration when reset button is clicked', async () => {
      const mockReset = vi.mocked(api.resetCalibration);
      mockReset.mockResolvedValue({
        message: 'Calibration reset to default values',
        calibration: mockCalibration,
      });

      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Reset to Defaults/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Reset to Defaults/i }));

      await waitFor(() => {
        expect(mockReset).toHaveBeenCalled();
      });
    });

    it('displays default values info', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Defaults: Low=30, Medium=60, High=85/)).toBeInTheDocument();
      });
    });
  });

  describe('learning rate slider', () => {
    it('updates decay factor when slider changes', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('learning-rate-slider')).toBeInTheDocument();
      });

      const slider = screen.getByLabelText('Learning rate');
      fireEvent.change(slider, { target: { value: '0.25' } });

      await waitFor(() => {
        expect(screen.getByText('0.25')).toBeInTheDocument();
      });
    });
  });

  describe('feedback stats breakdown', () => {
    it('shows feedback breakdown when stats are available', async () => {
      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByText(/Feedback by Type/)).toBeInTheDocument();
        expect(screen.getByText('false positive')).toBeInTheDocument();
        expect(screen.getByText('missed detection')).toBeInTheDocument();
      });
    });

    it('does not show feedback breakdown when stats total is 0', async () => {
      vi.mocked(api.fetchFeedbackStats).mockResolvedValue({
        total_feedback: 0,
        by_type: {},
        by_camera: {},
      });

      render(<RiskSensitivitySettings />);

      await waitFor(() => {
        expect(screen.getByTestId('low-threshold-slider')).toBeInTheDocument();
      });

      expect(screen.queryByText(/Feedback by Type/)).not.toBeInTheDocument();
    });
  });
});
