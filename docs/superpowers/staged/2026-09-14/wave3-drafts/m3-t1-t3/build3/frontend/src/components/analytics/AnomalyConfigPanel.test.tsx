import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AnomalyConfigPanel from './AnomalyConfigPanel';
import * as api from '../../services/api';

import type { AnomalyConfig } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    updateAnomalyConfig: vi.fn(),
  };
});

describe('AnomalyConfigPanel', () => {
  const mockConfig: AnomalyConfig = {
    threshold_stdev: 2.0,
    min_samples: 10,
    decay_factor: 0.1,
    window_days: 30,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the component header', () => {
    render(<AnomalyConfigPanel config={mockConfig} />);

    expect(screen.getByText('Anomaly Detection Settings')).toBeInTheDocument();
  });

  it('displays current threshold value', () => {
    render(<AnomalyConfigPanel config={mockConfig} />);

    expect(screen.getByText('2.0 std')).toBeInTheDocument();
  });

  it('displays current min samples value', () => {
    render(<AnomalyConfigPanel config={mockConfig} />);

    const input = screen.getByTestId('min-samples-input');
    expect(input).toHaveValue(10);
  });

  it('shows sensitivity level with proper styling', () => {
    render(<AnomalyConfigPanel config={mockConfig} />);

    expect(screen.getByText('High Sensitivity')).toBeInTheDocument();
  });

  it('shows very high sensitivity for low threshold', () => {
    const lowThresholdConfig = { ...mockConfig, threshold_stdev: 1.5 };
    render(<AnomalyConfigPanel config={lowThresholdConfig} />);

    expect(screen.getByText('Very High Sensitivity')).toBeInTheDocument();
  });

  it('shows low sensitivity for high threshold', () => {
    const highThresholdConfig = { ...mockConfig, threshold_stdev: 3.0 };
    render(<AnomalyConfigPanel config={highThresholdConfig} />);

    expect(screen.getByText('Low Sensitivity')).toBeInTheDocument();
  });

  it('displays read-only system settings', () => {
    render(<AnomalyConfigPanel config={mockConfig} />);

    expect(screen.getByText('Decay Factor:')).toBeInTheDocument();
    expect(screen.getByText('0.1')).toBeInTheDocument();
    expect(screen.getByText('Window:')).toBeInTheDocument();
    expect(screen.getByText('30 days')).toBeInTheDocument();
  });

  it('shows save button when changes are made', () => {
    render(<AnomalyConfigPanel config={mockConfig} />);

    const slider = screen.getByTestId('threshold-slider');
    fireEvent.change(slider, { target: { value: '2.5' } });

    expect(screen.getByTestId('save-config-button')).toBeInTheDocument();
  });

  it('hides save button when no changes', () => {
    render(<AnomalyConfigPanel config={mockConfig} />);

    expect(screen.queryByTestId('save-config-button')).not.toBeInTheDocument();
  });

  it('calls updateAnomalyConfig when save is clicked', async () => {
    const mockUpdateAnomalyConfig = vi.mocked(api.updateAnomalyConfig);
    mockUpdateAnomalyConfig.mockResolvedValue({
      ...mockConfig,
      threshold_stdev: 2.5,
    });

    const onConfigUpdated = vi.fn();
    render(<AnomalyConfigPanel config={mockConfig} onConfigUpdated={onConfigUpdated} />);

    const slider = screen.getByTestId('threshold-slider');
    fireEvent.change(slider, { target: { value: '2.5' } });

    const saveButton = screen.getByTestId('save-config-button');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockUpdateAnomalyConfig).toHaveBeenCalledWith({
        threshold_stdev: 2.5,
      });
    });

    await waitFor(() => {
      expect(onConfigUpdated).toHaveBeenCalled();
    });
  });

  it('shows error message on update failure', async () => {
    const mockUpdateAnomalyConfig = vi.mocked(api.updateAnomalyConfig);
    mockUpdateAnomalyConfig.mockRejectedValue(new Error('Update failed'));

    render(<AnomalyConfigPanel config={mockConfig} />);

    const slider = screen.getByTestId('threshold-slider');
    fireEvent.change(slider, { target: { value: '2.5' } });

    const saveButton = screen.getByTestId('save-config-button');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText('Update failed')).toBeInTheDocument();
    });
  });

  it('updates min samples input', () => {
    render(<AnomalyConfigPanel config={mockConfig} />);

    const input = screen.getByTestId('min-samples-input');
    fireEvent.change(input, { target: { value: '15' } });

    expect(input).toHaveValue(15);
    expect(screen.getByTestId('save-config-button')).toBeInTheDocument();
  });

  describe('slider accessibility', () => {
    it('has proper aria attributes on threshold slider', () => {
      render(<AnomalyConfigPanel config={mockConfig} />);

      const slider = screen.getByTestId('threshold-slider');
      expect(slider).toHaveAttribute('aria-label', 'Detection threshold in standard deviations');
      expect(slider).toHaveAttribute('aria-valuemin', '1');
      expect(slider).toHaveAttribute('aria-valuemax', '4');
      expect(slider).toHaveAttribute('aria-valuenow', '2');
    });

    it('has proper aria-label on min samples input', () => {
      render(<AnomalyConfigPanel config={mockConfig} />);

      const input = screen.getByTestId('min-samples-input');
      expect(input).toHaveAttribute('aria-label', 'Minimum samples required for detection');
    });

    it('displays tick marks for slider guidance', () => {
      render(<AnomalyConfigPanel config={mockConfig} />);

      // Check for visual tick mark labels
      expect(screen.getByText('1.0')).toBeInTheDocument();
      expect(screen.getByText('2.0')).toBeInTheDocument();
      expect(screen.getByText('3.0')).toBeInTheDocument();
      expect(screen.getByText('4.0')).toBeInTheDocument();
    });

    it('uses nvidia-slider class for enhanced visibility', () => {
      render(<AnomalyConfigPanel config={mockConfig} />);

      const slider = screen.getByTestId('threshold-slider');
      expect(slider).toHaveClass('nvidia-slider');
    });

    it('uses nvidia-input class for enhanced input styling', () => {
      render(<AnomalyConfigPanel config={mockConfig} />);

      const input = screen.getByTestId('min-samples-input');
      expect(input).toHaveClass('nvidia-input');
    });
  });
});
