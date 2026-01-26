/**
 * Tests for BatchPresetSelector component
 *
 * @see NEM-3873 - Batch Config Validation
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import BatchPresetSelector from './BatchPresetSelector';
import { BATCH_PRESETS } from '../../utils/batchSettingsValidation';

describe('BatchPresetSelector', () => {
  const mockOnSelect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders all three presets', () => {
      render(<BatchPresetSelector onSelect={mockOnSelect} />);

      expect(screen.getByText('Real-time')).toBeInTheDocument();
      expect(screen.getByText('Balanced')).toBeInTheDocument();
      expect(screen.getByText('Efficient')).toBeInTheDocument();
    });

    it('renders preset descriptions', () => {
      render(<BatchPresetSelector onSelect={mockOnSelect} />);

      // Check for partial descriptions
      expect(screen.getByText(/Fastest response time/)).toBeInTheDocument();
      expect(screen.getByText(/balancing response time/i)).toBeInTheDocument();
      expect(screen.getByText(/Lower processing overhead/)).toBeInTheDocument();
    });

    it('renders preset values', () => {
      render(<BatchPresetSelector onSelect={mockOnSelect} />);

      // Real-time: 30s window, 10s idle
      expect(screen.getByText(/30s.*10s/)).toBeInTheDocument();
      // Balanced: 90s window, 30s idle
      expect(screen.getByText(/90s.*30s/)).toBeInTheDocument();
      // Efficient: 180s window, 60s idle
      expect(screen.getByText(/180s.*60s/)).toBeInTheDocument();
    });
  });

  describe('selection behavior', () => {
    it('calls onSelect when preset is clicked', () => {
      render(<BatchPresetSelector onSelect={mockOnSelect} />);

      const realtimePreset = screen.getByText('Real-time').closest('button');
      fireEvent.click(realtimePreset!);

      expect(mockOnSelect).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'realtime',
          windowSeconds: 30,
          idleTimeoutSeconds: 10,
        })
      );
    });

    it('calls onSelect with correct values for each preset', () => {
      render(<BatchPresetSelector onSelect={mockOnSelect} />);

      // Click Balanced
      const balancedPreset = screen.getByText('Balanced').closest('button');
      fireEvent.click(balancedPreset!);

      expect(mockOnSelect).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'balanced',
          windowSeconds: 90,
          idleTimeoutSeconds: 30,
        })
      );

      // Click Efficient
      const efficientPreset = screen.getByText('Efficient').closest('button');
      fireEvent.click(efficientPreset!);

      expect(mockOnSelect).toHaveBeenCalledWith(
        expect.objectContaining({
          id: 'efficient',
          windowSeconds: 180,
          idleTimeoutSeconds: 60,
        })
      );
    });
  });

  describe('current preset detection', () => {
    it('highlights Real-time when current values match', () => {
      render(
        <BatchPresetSelector
          onSelect={mockOnSelect}
          currentWindowSeconds={30}
          currentIdleTimeoutSeconds={10}
        />
      );

      const realtimePreset = screen.getByText('Real-time').closest('button');
      expect(realtimePreset).toHaveAttribute('aria-pressed', 'true');
    });

    it('highlights Balanced when current values match', () => {
      render(
        <BatchPresetSelector
          onSelect={mockOnSelect}
          currentWindowSeconds={90}
          currentIdleTimeoutSeconds={30}
        />
      );

      const balancedPreset = screen.getByText('Balanced').closest('button');
      expect(balancedPreset).toHaveAttribute('aria-pressed', 'true');
    });

    it('highlights Efficient when current values match', () => {
      render(
        <BatchPresetSelector
          onSelect={mockOnSelect}
          currentWindowSeconds={180}
          currentIdleTimeoutSeconds={60}
        />
      );

      const efficientPreset = screen.getByText('Efficient').closest('button');
      expect(efficientPreset).toHaveAttribute('aria-pressed', 'true');
    });

    it('no preset is highlighted for custom values', () => {
      render(
        <BatchPresetSelector
          onSelect={mockOnSelect}
          currentWindowSeconds={120}
          currentIdleTimeoutSeconds={45}
        />
      );

      const realtimePreset = screen.getByText('Real-time').closest('button');
      const balancedPreset = screen.getByText('Balanced').closest('button');
      const efficientPreset = screen.getByText('Efficient').closest('button');

      expect(realtimePreset).toHaveAttribute('aria-pressed', 'false');
      expect(balancedPreset).toHaveAttribute('aria-pressed', 'false');
      expect(efficientPreset).toHaveAttribute('aria-pressed', 'false');
    });
  });

  describe('disabled state', () => {
    it('disables all presets when disabled prop is true', () => {
      render(<BatchPresetSelector onSelect={mockOnSelect} disabled />);

      const realtimePreset = screen.getByText('Real-time').closest('button');
      const balancedPreset = screen.getByText('Balanced').closest('button');
      const efficientPreset = screen.getByText('Efficient').closest('button');

      expect(realtimePreset).toBeDisabled();
      expect(balancedPreset).toBeDisabled();
      expect(efficientPreset).toBeDisabled();
    });

    it('does not call onSelect when disabled', () => {
      render(<BatchPresetSelector onSelect={mockOnSelect} disabled />);

      const realtimePreset = screen.getByText('Real-time').closest('button');
      fireEvent.click(realtimePreset!);

      expect(mockOnSelect).not.toHaveBeenCalled();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<BatchPresetSelector onSelect={mockOnSelect} className="custom-class" />);

      const container = screen.getByTestId('batch-preset-selector');
      expect(container).toHaveClass('custom-class');
    });
  });

  describe('BATCH_PRESETS integration', () => {
    it('uses presets from batchSettingsValidation utility', () => {
      // Verify presets match the utility
      expect(BATCH_PRESETS).toHaveLength(3);
      expect(BATCH_PRESETS.find(p => p.id === 'realtime')).toBeDefined();
      expect(BATCH_PRESETS.find(p => p.id === 'balanced')).toBeDefined();
      expect(BATCH_PRESETS.find(p => p.id === 'efficient')).toBeDefined();
    });
  });
});
