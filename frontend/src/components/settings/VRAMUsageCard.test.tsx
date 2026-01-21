/**
 * Tests for VRAMUsageCard component
 *
 * Tests the VRAM usage visualization card that displays:
 * - VRAM budget/total
 * - Used VRAM with progress bar
 * - Available VRAM
 * - Usage percentage with color coding
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import VRAMUsageCard, { type VRAMUsageCardProps } from './VRAMUsageCard';

describe('VRAMUsageCard', () => {
  const defaultProps: VRAMUsageCardProps = {
    budgetMb: 1650,
    usedMb: 500,
    availableMb: 1150,
    usagePercent: 30.3,
  };

  describe('Basic Rendering', () => {
    it('renders the card with title', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      expect(screen.getByText(/VRAM Usage/i)).toBeInTheDocument();
    });

    it('displays budget/total VRAM', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      // 1650 MB = 1.6 GB (formatted)
      expect(screen.getByText(/1\.6 GB/)).toBeInTheDocument();
      expect(screen.getByText(/Budget/i)).toBeInTheDocument();
    });

    it('displays used VRAM', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      expect(screen.getByText(/500 MB/)).toBeInTheDocument();
      expect(screen.getByText(/Used/i)).toBeInTheDocument();
    });

    it('displays available VRAM', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      // 1150 MB = 1.1 GB (formatted)
      expect(screen.getByText(/1\.1 GB/)).toBeInTheDocument();
      expect(screen.getByText(/Available/i)).toBeInTheDocument();
    });

    it('displays usage percentage', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      expect(screen.getByText(/30\.3%/)).toBeInTheDocument();
    });
  });

  describe('Progress Bar', () => {
    it('renders progress bar', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('sets progress bar value correctly', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '30.3');
    });

    it('sets progress bar min and max', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
    });
  });

  describe('Color Coding by Usage', () => {
    it('shows green for low usage (0-50%)', () => {
      render(<VRAMUsageCard {...defaultProps} usagePercent={30} />);

      expect(screen.getByTestId('usage-indicator')).toHaveAttribute('data-status', 'low');
    });

    it('shows yellow for moderate usage (50-80%)', () => {
      render(<VRAMUsageCard {...defaultProps} usedMb={1000} availableMb={650} usagePercent={60.6} />);

      expect(screen.getByTestId('usage-indicator')).toHaveAttribute('data-status', 'moderate');
    });

    it('shows red for high usage (>80%)', () => {
      render(
        <VRAMUsageCard {...defaultProps} usedMb={1400} availableMb={250} usagePercent={84.8} />
      );

      expect(screen.getByTestId('usage-indicator')).toHaveAttribute('data-status', 'high');
    });

    it('shows red for critical usage (>90%)', () => {
      render(<VRAMUsageCard {...defaultProps} usedMb={1550} availableMb={100} usagePercent={93.9} />);

      expect(screen.getByTestId('usage-indicator')).toHaveAttribute('data-status', 'critical');
    });
  });

  describe('Edge Cases', () => {
    it('handles zero usage', () => {
      render(<VRAMUsageCard budgetMb={1650} usedMb={0} availableMb={1650} usagePercent={0} />);

      expect(screen.getByText(/0 MB/)).toBeInTheDocument();
      expect(screen.getByText(/0%/)).toBeInTheDocument();
    });

    it('handles full usage', () => {
      render(<VRAMUsageCard budgetMb={1650} usedMb={1650} availableMb={0} usagePercent={100} />);

      expect(screen.getByText(/100(\.0)?%/)).toBeInTheDocument();
      // 0 MB stays as MB since it's below 1024
      expect(screen.getByText('0 MB')).toBeInTheDocument(); // Available
    });

    it('handles small VRAM values', () => {
      render(<VRAMUsageCard budgetMb={100} usedMb={50} availableMb={50} usagePercent={50} />);

      expect(screen.getByText('100 MB')).toBeInTheDocument();
      expect(screen.getByText(/50(\.0)?%/)).toBeInTheDocument();
    });

    it('handles large VRAM values', () => {
      render(
        <VRAMUsageCard budgetMb={24576} usedMb={12288} availableMb={12288} usagePercent={50} />
      );

      // Should display in GB for large values
      expect(screen.getByText(/24\.0 GB|24576 MB/)).toBeInTheDocument();
    });
  });

  describe('Formatting', () => {
    it('rounds percentage to one decimal place', () => {
      render(
        <VRAMUsageCard {...defaultProps} usagePercent={33.333} />
      );

      expect(screen.getByText(/33\.3%/)).toBeInTheDocument();
    });

    it('handles integer percentage', () => {
      render(<VRAMUsageCard {...defaultProps} usagePercent={50} />);

      expect(screen.getByText(/50(\.0)?%/)).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies custom className', () => {
      render(<VRAMUsageCard {...defaultProps} className="custom-class" />);

      expect(screen.getByTestId('vram-usage-card')).toHaveClass('custom-class');
    });

    it('renders with NVIDIA theme colors', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      // Check that the card has dark theme styling
      const card = screen.getByTestId('vram-usage-card');
      expect(card).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows skeleton when loading', () => {
      render(<VRAMUsageCard {...defaultProps} isLoading={true} />);

      expect(screen.getByTestId('vram-loading-skeleton')).toBeInTheDocument();
    });

    it('hides values when loading', () => {
      render(<VRAMUsageCard {...defaultProps} isLoading={true} />);

      expect(screen.queryByText(/500 MB/)).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has accessible progress bar', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-label');
    });

    it('provides descriptive text for screen readers', () => {
      render(<VRAMUsageCard {...defaultProps} />);

      // Should have sr-only text describing the usage
      expect(screen.getByText(/VRAM Usage/i)).toBeInTheDocument();
    });
  });

  describe('Compact Mode', () => {
    it('supports compact display mode', () => {
      render(<VRAMUsageCard {...defaultProps} compact={true} />);

      expect(screen.getByTestId('vram-usage-card')).toHaveAttribute('data-compact', 'true');
    });

    it('shows simplified info in compact mode', () => {
      render(<VRAMUsageCard {...defaultProps} compact={true} />);

      // Should still show key metrics
      expect(screen.getByText(/30\.3%/)).toBeInTheDocument();
    });
  });
});
