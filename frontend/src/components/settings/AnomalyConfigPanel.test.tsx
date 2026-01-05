import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import AnomalyConfigPanel from './AnomalyConfigPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api');

describe('AnomalyConfigPanel', () => {
  const mockConfig: api.AnomalyConfig = {
    threshold_stdev: 2.0,
    min_samples: 10,
    decay_factor: 0.1,
    window_days: 30,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api.fetchAnomalyConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.updateAnomalyConfig).mockResolvedValue(mockConfig);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders component with title', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Anomaly Detection Settings')).toBeInTheDocument();
    });
  });

  it('shows loading state initially', () => {
    vi.mocked(api.fetchAnomalyConfig).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<AnomalyConfigPanel />);

    expect(screen.getByText('Loading configuration...')).toBeInTheDocument();
  });

  it('displays configuration after loading', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Detection Sensitivity')).toBeInTheDocument();
    });

    expect(screen.getByText('Minimum Learning Samples')).toBeInTheDocument();
  });

  it('displays current threshold value', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('2.0 std dev')).toBeInTheDocument();
    });
  });

  it('displays current min_samples value', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('10 samples')).toBeInTheDocument();
    });
  });

  it('displays sensitivity label based on threshold', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      // 2.0 std dev should be "Sensitive"
      expect(screen.getByText('Sensitive')).toBeInTheDocument();
    });
  });

  it('displays read-only decay factor', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Decay Factor')).toBeInTheDocument();
      expect(screen.getByText('0.1')).toBeInTheDocument();
    });
  });

  it('displays read-only window days', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Window')).toBeInTheDocument();
      expect(screen.getByText('30 days')).toBeInTheDocument();
    });
  });

  it('shows error when config fails to load', async () => {
    vi.mocked(api.fetchAnomalyConfig).mockRejectedValue(new Error('Network error'));

    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('save button is disabled when no changes', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Detection Sensitivity')).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: /save changes/i });
    expect(saveButton).toBeDisabled();
  });

  it('reset button is disabled when no changes', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Detection Sensitivity')).toBeInTheDocument();
    });

    const resetButton = screen.getByRole('button', { name: /reset/i });
    expect(resetButton).toBeDisabled();
  });

  it('enables save button after making changes', async () => {
    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Detection Sensitivity')).toBeInTheDocument();
    });

    // Find the first range slider (threshold)
    const sliders = document.querySelectorAll('input[type="range"]');
    const thresholdSlider = sliders[0];

    if (thresholdSlider) {
      fireEvent.change(thresholdSlider, { target: { value: '2.5' } });

      await waitFor(() => {
        const saveButton = screen.getByRole('button', { name: /save changes/i });
        expect(saveButton).not.toBeDisabled();
      });
    }
  });

  it('calls onConfigUpdate callback after successful save', async () => {
    const onConfigUpdate = vi.fn();
    const updatedConfig = { ...mockConfig, threshold_stdev: 2.5 };
    vi.mocked(api.updateAnomalyConfig).mockResolvedValue(updatedConfig);

    render(<AnomalyConfigPanel onConfigUpdate={onConfigUpdate} />);

    await waitFor(() => {
      expect(screen.getByText('Detection Sensitivity')).toBeInTheDocument();
    });

    // Find and change the threshold slider
    const sliders = document.querySelectorAll('input[type="range"]');
    const thresholdSlider = sliders[0]; // First slider is threshold

    if (thresholdSlider) {
      fireEvent.change(thresholdSlider, { target: { value: '2.5' } });

      const saveButton = screen.getByRole('button', { name: /save changes/i });

      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(onConfigUpdate).toHaveBeenCalledWith(updatedConfig);
      });
    }
  });

  it('shows success message after save', async () => {
    const updatedConfig = { ...mockConfig, threshold_stdev: 2.5 };
    vi.mocked(api.updateAnomalyConfig).mockResolvedValue(updatedConfig);

    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Detection Sensitivity')).toBeInTheDocument();
    });

    // Find and change the threshold slider
    const sliders = document.querySelectorAll('input[type="range"]');
    const thresholdSlider = sliders[0];

    if (thresholdSlider) {
      fireEvent.change(thresholdSlider, { target: { value: '2.5' } });

      const saveButton = screen.getByRole('button', { name: /save changes/i });

      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Saved')).toBeInTheDocument();
      });
    }
  });

  it('shows error when save fails', async () => {
    vi.mocked(api.updateAnomalyConfig).mockRejectedValue(new Error('Save failed'));

    render(<AnomalyConfigPanel />);

    await waitFor(() => {
      expect(screen.getByText('Detection Sensitivity')).toBeInTheDocument();
    });

    // Find and change the threshold slider
    const sliders = document.querySelectorAll('input[type="range"]');
    const thresholdSlider = sliders[0];

    if (thresholdSlider) {
      fireEvent.change(thresholdSlider, { target: { value: '2.5' } });

      const saveButton = screen.getByRole('button', { name: /save changes/i });

      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText('Save failed')).toBeInTheDocument();
      });
    }
  });

  it('applies custom className', async () => {
    const { container } = render(<AnomalyConfigPanel className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByText('Detection Sensitivity')).toBeInTheDocument();
    });

    expect(container.firstChild).toHaveClass('custom-class');
  });
});
