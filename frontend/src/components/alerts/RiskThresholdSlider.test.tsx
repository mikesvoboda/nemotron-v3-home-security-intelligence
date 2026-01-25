/**
 * Tests for RiskThresholdSlider component.
 *
 * @see NEM-3604 Alert Threshold Configuration
 */

import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import RiskThresholdSlider, {
  getSeverityZone,
  getThresholdColor,
  SEVERITY_ZONES,
} from './RiskThresholdSlider';

describe('RiskThresholdSlider', () => {
  const defaultProps = {
    value: 50,
    onChange: vi.fn(),
  };

  describe('Rendering', () => {
    it('should render the slider track', () => {
      render(<RiskThresholdSlider {...defaultProps} />);

      expect(screen.getByTestId('risk-threshold-track')).toBeInTheDocument();
    });

    it('should render the range slider input', () => {
      render(<RiskThresholdSlider {...defaultProps} />);

      const slider = screen.getByTestId('risk-threshold-slider');
      expect(slider).toBeInTheDocument();
      expect(slider).toHaveAttribute('type', 'range');
      expect(slider).toHaveAttribute('min', '0');
      expect(slider).toHaveAttribute('max', '100');
    });

    it('should render severity zone labels', () => {
      render(<RiskThresholdSlider {...defaultProps} />);

      expect(screen.getByText('Low')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });

    it('should render zone ranges', () => {
      render(<RiskThresholdSlider {...defaultProps} />);

      expect(screen.getByText('0-25')).toBeInTheDocument();
      expect(screen.getByText('26-50')).toBeInTheDocument();
      expect(screen.getByText('51-75')).toBeInTheDocument();
      expect(screen.getByText('76-100')).toBeInTheDocument();
    });

    it('should render numeric input when showNumericInput is true', () => {
      render(<RiskThresholdSlider {...defaultProps} showNumericInput={true} />);

      expect(screen.getByTestId('risk-threshold-numeric-input')).toBeInTheDocument();
    });

    it('should not render numeric input when showNumericInput is false', () => {
      render(<RiskThresholdSlider {...defaultProps} showNumericInput={false} />);

      expect(screen.queryByTestId('risk-threshold-numeric-input')).not.toBeInTheDocument();
    });

    it('should render zone badge with current zone', () => {
      render(<RiskThresholdSlider {...defaultProps} value={70} />);

      const badge = screen.getByTestId('risk-threshold-zone-badge');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent('High Risk');
    });

    it('should not render zone badge when value is null', () => {
      render(<RiskThresholdSlider {...defaultProps} value={null} />);

      expect(screen.queryByTestId('risk-threshold-zone-badge')).not.toBeInTheDocument();
    });
  });

  describe('Value Display', () => {
    it('should display the current value in numeric input', () => {
      render(<RiskThresholdSlider {...defaultProps} value={75} />);

      const numericInput = screen.getByTestId<HTMLInputElement>('risk-threshold-numeric-input');
      expect(numericInput.value).toBe('75');
    });

    it('should display empty string for null value', () => {
      render(<RiskThresholdSlider {...defaultProps} value={null} />);

      const numericInput = screen.getByTestId<HTMLInputElement>('risk-threshold-numeric-input');
      expect(numericInput.value).toBe('');
    });

    it('should set slider value to current value', () => {
      render(<RiskThresholdSlider {...defaultProps} value={30} />);

      const slider = screen.getByTestId<HTMLInputElement>('risk-threshold-slider');
      expect(slider.value).toBe('30');
    });
  });

  describe('Slider Interaction', () => {
    it('should call onChange when slider value changes', () => {
      const onChange = vi.fn();
      render(<RiskThresholdSlider {...defaultProps} onChange={onChange} />);

      const slider = screen.getByTestId('risk-threshold-slider');
      fireEvent.change(slider, { target: { value: '75' } });

      expect(onChange).toHaveBeenCalledWith(75);
    });

    it('should handle boundary values', () => {
      const onChange = vi.fn();
      render(<RiskThresholdSlider {...defaultProps} onChange={onChange} />);

      const slider = screen.getByTestId('risk-threshold-slider');

      // Test minimum boundary
      fireEvent.change(slider, { target: { value: '0' } });
      expect(onChange).toHaveBeenCalledWith(0);

      // Test maximum boundary
      fireEvent.change(slider, { target: { value: '100' } });
      expect(onChange).toHaveBeenCalledWith(100);
    });
  });

  describe('Numeric Input Interaction', () => {
    it('should call onChange when numeric input changes', () => {
      const onChange = vi.fn();
      render(<RiskThresholdSlider {...defaultProps} onChange={onChange} value={null} />);

      const numericInput = screen.getByTestId('risk-threshold-numeric-input');
      // Use fireEvent.change for more predictable behavior
      fireEvent.change(numericInput, { target: { value: '80' } });

      expect(onChange).toHaveBeenCalledWith(80);
    });

    it('should call onChange with null when input is cleared', async () => {
      const onChange = vi.fn();
      render(<RiskThresholdSlider {...defaultProps} onChange={onChange} value={50} />);

      const numericInput = screen.getByTestId('risk-threshold-numeric-input');
      await userEvent.clear(numericInput);

      expect(onChange).toHaveBeenCalledWith(null);
    });

    it('should clamp values above 100 to 100', () => {
      const onChange = vi.fn();
      render(<RiskThresholdSlider {...defaultProps} onChange={onChange} value={null} />);

      const numericInput = screen.getByTestId('risk-threshold-numeric-input');
      // Use fireEvent.change for direct value setting
      fireEvent.change(numericInput, { target: { value: '150' } });

      // The value should be clamped to 100
      expect(onChange).toHaveBeenCalledWith(100);
    });

    it('should clamp values below 0 to 0', () => {
      const onChange = vi.fn();
      render(<RiskThresholdSlider {...defaultProps} onChange={onChange} />);

      const numericInput = screen.getByTestId('risk-threshold-numeric-input');
      fireEvent.change(numericInput, { target: { value: '-10' } });

      expect(onChange).toHaveBeenCalledWith(0);
    });
  });

  describe('Disabled State', () => {
    it('should disable slider when disabled is true', () => {
      render(<RiskThresholdSlider {...defaultProps} disabled={true} />);

      const slider = screen.getByTestId('risk-threshold-slider');
      expect(slider).toBeDisabled();
    });

    it('should disable numeric input when disabled is true', () => {
      render(<RiskThresholdSlider {...defaultProps} disabled={true} />);

      const numericInput = screen.getByTestId('risk-threshold-numeric-input');
      expect(numericInput).toBeDisabled();
    });

    it('should apply opacity styling when disabled', () => {
      render(<RiskThresholdSlider {...defaultProps} disabled={true} />);

      const slider = screen.getByTestId('risk-threshold-slider');
      expect(slider).toHaveClass('opacity-50');
    });
  });

  describe('Accessibility', () => {
    it('should have proper aria attributes on slider', () => {
      render(<RiskThresholdSlider {...defaultProps} value={60} />);

      const slider = screen.getByTestId('risk-threshold-slider');
      expect(slider).toHaveAttribute('aria-label', 'Risk threshold slider');
      expect(slider).toHaveAttribute('aria-valuemin', '0');
      expect(slider).toHaveAttribute('aria-valuemax', '100');
      expect(slider).toHaveAttribute('aria-valuenow', '60');
    });

    it('should have proper aria-valuetext with zone info', () => {
      render(<RiskThresholdSlider {...defaultProps} value={80} />);

      const slider = screen.getByTestId('risk-threshold-slider');
      expect(slider).toHaveAttribute('aria-valuetext', '80 - Critical');
    });

    it('should have aria-label on numeric input', () => {
      render(<RiskThresholdSlider {...defaultProps} />);

      const numericInput = screen.getByTestId('risk-threshold-numeric-input');
      expect(numericInput).toHaveAttribute('aria-label', 'Risk threshold numeric input');
    });
  });

  describe('Custom Test ID Prefix', () => {
    it('should use custom testIdPrefix', () => {
      render(<RiskThresholdSlider {...defaultProps} testIdPrefix="custom" />);

      expect(screen.getByTestId('custom-slider')).toBeInTheDocument();
      expect(screen.getByTestId('custom-track')).toBeInTheDocument();
      expect(screen.getByTestId('custom-numeric-input')).toBeInTheDocument();
    });
  });
});

describe('getSeverityZone', () => {
  it('should return Low zone for values 0-25', () => {
    expect(getSeverityZone(0)?.label).toBe('Low');
    expect(getSeverityZone(12)?.label).toBe('Low');
    expect(getSeverityZone(25)?.label).toBe('Low');
  });

  it('should return Medium zone for values 26-50', () => {
    expect(getSeverityZone(26)?.label).toBe('Medium');
    expect(getSeverityZone(40)?.label).toBe('Medium');
    expect(getSeverityZone(50)?.label).toBe('Medium');
  });

  it('should return High zone for values 51-75', () => {
    expect(getSeverityZone(51)?.label).toBe('High');
    expect(getSeverityZone(60)?.label).toBe('High');
    expect(getSeverityZone(75)?.label).toBe('High');
  });

  it('should return Critical zone for values 76-100', () => {
    expect(getSeverityZone(76)?.label).toBe('Critical');
    expect(getSeverityZone(90)?.label).toBe('Critical');
    expect(getSeverityZone(100)?.label).toBe('Critical');
  });

  it('should return null for null value', () => {
    expect(getSeverityZone(null)).toBeNull();
  });
});

describe('getThresholdColor', () => {
  it('should return green for values 0-25', () => {
    expect(getThresholdColor(0)).toBe('#22c55e');
    expect(getThresholdColor(25)).toBe('#22c55e');
  });

  it('should return yellow for values 26-50', () => {
    expect(getThresholdColor(26)).toBe('#eab308');
    expect(getThresholdColor(50)).toBe('#eab308');
  });

  it('should return orange for values 51-75', () => {
    expect(getThresholdColor(51)).toBe('#f97316');
    expect(getThresholdColor(75)).toBe('#f97316');
  });

  it('should return red for values 76-100', () => {
    expect(getThresholdColor(76)).toBe('#ef4444');
    expect(getThresholdColor(100)).toBe('#ef4444');
  });
});

describe('SEVERITY_ZONES', () => {
  it('should have 4 zones', () => {
    expect(SEVERITY_ZONES).toHaveLength(4);
  });

  it('should cover full 0-100 range', () => {
    expect(SEVERITY_ZONES[0].min).toBe(0);
    expect(SEVERITY_ZONES[SEVERITY_ZONES.length - 1].max).toBe(100);
  });

  it('should have contiguous ranges', () => {
    for (let i = 1; i < SEVERITY_ZONES.length; i++) {
      expect(SEVERITY_ZONES[i].min).toBe(SEVERITY_ZONES[i - 1].max + 1);
    }
  });
});
