import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ThreatIndicator from './ThreatIndicator';

import type { ThreatData } from '../../types/threat';

describe('ThreatIndicator', () => {
  describe('rendering', () => {
    it('renders nothing when threats is null', () => {
      const { container } = render(<ThreatIndicator threats={null} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when threats is undefined', () => {
      const { container } = render(<ThreatIndicator threats={undefined} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders nothing when threats is empty array', () => {
      const { container } = render(<ThreatIndicator threats={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('has correct test id', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('threat-indicator')).toBeInTheDocument();
    });
  });

  describe('weapon type badge', () => {
    it('renders weapon type badge for gun', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('GUN')).toBeInTheDocument();
    });

    it('renders weapon type badge for knife', () => {
      const threats: ThreatData[] = [
        { class_name: 'knife', confidence: 0.92, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('KNIFE')).toBeInTheDocument();
    });

    it('renders weapon type badge for bat', () => {
      const threats: ThreatData[] = [
        { class_name: 'bat', confidence: 0.75, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('BAT')).toBeInTheDocument();
    });

    it('renders weapon type badge for crowbar', () => {
      const threats: ThreatData[] = [
        { class_name: 'crowbar', confidence: 0.68, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('CROWBAR')).toBeInTheDocument();
    });

    it('renders weapon type badge for pistol', () => {
      const threats: ThreatData[] = [
        { class_name: 'pistol', confidence: 0.95, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('PISTOL')).toBeInTheDocument();
    });

    it('renders weapon type badge for rifle', () => {
      const threats: ThreatData[] = [
        { class_name: 'rifle', confidence: 0.89, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('RIFLE')).toBeInTheDocument();
    });

    it('renders weapon type badge for machete', () => {
      const threats: ThreatData[] = [
        { class_name: 'machete', confidence: 0.81, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('MACHETE')).toBeInTheDocument();
    });

    it('converts class_name with underscores to uppercase display', () => {
      const threats: ThreatData[] = [
        { class_name: 'baseball_bat', confidence: 0.72, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('BASEBALL BAT')).toBeInTheDocument();
    });
  });

  describe('confidence percentage', () => {
    it('displays confidence as percentage for high confidence', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('87%')).toBeInTheDocument();
    });

    it('displays confidence as percentage for low confidence', () => {
      const threats: ThreatData[] = [
        { class_name: 'bat', confidence: 0.45, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('45%')).toBeInTheDocument();
    });

    it('rounds confidence to nearest integer', () => {
      const threats: ThreatData[] = [
        { class_name: 'knife', confidence: 0.876, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('88%')).toBeInTheDocument();
    });

    it('displays 100% confidence correctly', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 1.0, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    it('displays very low confidence correctly', () => {
      const threats: ThreatData[] = [
        { class_name: 'hammer', confidence: 0.25, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('25%')).toBeInTheDocument();
    });
  });

  describe('high-priority styling (firearms and knives)', () => {
    it('applies critical styling for gun (high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-red-600');
    });

    it('applies critical styling for pistol (high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'pistol', confidence: 0.91, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-red-600');
    });

    it('applies critical styling for rifle (high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'rifle', confidence: 0.88, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-red-600');
    });

    it('applies critical styling for knife (high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'knife', confidence: 0.92, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-red-600');
    });

    it('applies critical styling for machete (high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'machete', confidence: 0.79, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-red-600');
    });

    it('applies critical styling for sword (high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'sword', confidence: 0.85, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-red-600');
    });

    it('applies critical styling for firearm (high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'firearm', confidence: 0.94, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-red-600');
    });

    it('applies critical styling for handgun (high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'handgun', confidence: 0.89, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-red-600');
    });

    it('renders critical icon for high-priority threats', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('critical-icon')).toBeInTheDocument();
    });
  });

  describe('medium-priority styling (blunt weapons)', () => {
    it('applies warning styling for bat (not high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'bat', confidence: 0.75, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-orange-500');
    });

    it('applies warning styling for crowbar (not high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'crowbar', confidence: 0.68, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-orange-500');
    });

    it('applies warning styling for hammer (not high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'hammer', confidence: 0.71, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-orange-500');
    });

    it('applies warning styling for axe (not high-priority)', () => {
      const threats: ThreatData[] = [
        { class_name: 'axe', confidence: 0.66, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('bg-orange-500');
    });

    it('renders warning icon for medium-priority threats', () => {
      const threats: ThreatData[] = [
        { class_name: 'bat', confidence: 0.75, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('warning-icon')).toBeInTheDocument();
    });
  });

  describe('multiple threats', () => {
    it('renders multiple threat badges', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
        { class_name: 'knife', confidence: 0.72, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getAllByTestId(/threat-badge-/)).toHaveLength(2);
    });

    it('renders three threats correctly', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
        { class_name: 'knife', confidence: 0.72, is_high_priority: true },
        { class_name: 'bat', confidence: 0.65, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('GUN')).toBeInTheDocument();
      expect(screen.getByText('KNIFE')).toBeInTheDocument();
      expect(screen.getByText('BAT')).toBeInTheDocument();
    });

    it('applies correct styling to each threat based on priority', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
        { class_name: 'bat', confidence: 0.65, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);

      // After sorting by confidence, gun (0.87) should be first
      const badges = screen.getAllByTestId(/threat-badge-/);
      expect(badges[0]).toHaveClass('bg-red-600');
      expect(badges[1]).toHaveClass('bg-orange-500');
    });
  });

  describe('sorting by confidence', () => {
    it('sorts threats by confidence (highest first)', () => {
      const threats: ThreatData[] = [
        { class_name: 'bat', confidence: 0.65, is_high_priority: false },
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
        { class_name: 'knife', confidence: 0.72, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);

      const badges = screen.getAllByTestId(/threat-badge-/);

      // First badge should be gun (highest confidence 0.87)
      expect(within(badges[0]).getByText('GUN')).toBeInTheDocument();
      expect(within(badges[0]).getByText('87%')).toBeInTheDocument();

      // Second badge should be knife (0.72)
      expect(within(badges[1]).getByText('KNIFE')).toBeInTheDocument();
      expect(within(badges[1]).getByText('72%')).toBeInTheDocument();

      // Third badge should be bat (0.65)
      expect(within(badges[2]).getByText('BAT')).toBeInTheDocument();
      expect(within(badges[2]).getByText('65%')).toBeInTheDocument();
    });

    it('maintains order for equal confidence values', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.85, is_high_priority: true },
        { class_name: 'knife', confidence: 0.85, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);

      const badges = screen.getAllByTestId(/threat-badge-/);
      expect(badges).toHaveLength(2);
      // Both should have 85%
      expect(screen.getAllByText('85%')).toHaveLength(2);
    });
  });

  describe('compact mode', () => {
    it('renders in compact mode when prop is true', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} compact />);
      expect(screen.getByTestId('threat-indicator')).toHaveClass('compact');
    });

    it('renders in full mode when compact is false', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} compact={false} />);
      expect(screen.getByTestId('threat-indicator')).not.toHaveClass('compact');
    });

    it('renders in full mode by default', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('threat-indicator')).not.toHaveClass('compact');
    });

    it('shows abbreviated text in compact mode', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
        { class_name: 'knife', confidence: 0.72, is_high_priority: true },
        { class_name: 'bat', confidence: 0.65, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} compact />);
      // In compact mode, should show count badge for multiple threats
      expect(screen.getByText('+2')).toBeInTheDocument();
    });

    it('limits displayed badges in compact mode to first item plus count', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.95, is_high_priority: true },
        { class_name: 'knife', confidence: 0.72, is_high_priority: true },
        { class_name: 'bat', confidence: 0.65, is_high_priority: false },
        { class_name: 'crowbar', confidence: 0.55, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} compact />);
      // Should show highest confidence threat and +3 count
      expect(screen.getByText('GUN')).toBeInTheDocument();
      expect(screen.getByText('+3')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has aria-label on container describing threat count', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('threat-indicator')).toHaveAttribute(
        'aria-label',
        expect.stringContaining('1 threat detected')
      );
    });

    it('has aria-label with plural for multiple threats', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
        { class_name: 'knife', confidence: 0.72, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('threat-indicator')).toHaveAttribute(
        'aria-label',
        expect.stringContaining('2 threats detected')
      );
    });

    it('each badge has aria-label describing the threat', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveAttribute(
        'aria-label',
        expect.stringContaining('gun')
      );
      expect(badge).toHaveAttribute(
        'aria-label',
        expect.stringContaining('87%')
      );
    });

    it('high-priority badges indicate critical status in aria-label', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveAttribute(
        'aria-label',
        expect.stringContaining('high priority')
      );
    });

    it('has role="alert" for high-priority threats', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('threat-indicator')).toHaveAttribute('role', 'alert');
    });

    it('has role="status" for non-high-priority threats only', () => {
      const threats: ThreatData[] = [
        { class_name: 'bat', confidence: 0.75, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('threat-indicator')).toHaveAttribute('role', 'status');
    });

    it('has aria-live="assertive" for high-priority threats', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('threat-indicator')).toHaveAttribute('aria-live', 'assertive');
    });

    it('has aria-live="polite" for medium-priority threats only', () => {
      const threats: ThreatData[] = [
        { class_name: 'bat', confidence: 0.75, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByTestId('threat-indicator')).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} className="custom-class" />);
      expect(screen.getByTestId('threat-indicator')).toHaveClass('custom-class');
    });

    it('applies text-white class to badges', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('text-white');
    });

    it('applies border styling for high-priority threats', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('border-red-800');
    });

    it('applies border styling for medium-priority threats', () => {
      const threats: ThreatData[] = [
        { class_name: 'bat', confidence: 0.75, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('border-orange-700');
    });
  });

  describe('edge cases', () => {
    it('handles zero confidence gracefully', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('handles unknown threat class names', () => {
      const threats: ThreatData[] = [
        { class_name: 'unknown_weapon', confidence: 0.5, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      expect(screen.getByText('UNKNOWN WEAPON')).toBeInTheDocument();
    });

    it('handles empty class name', () => {
      const threats: ThreatData[] = [
        { class_name: '', confidence: 0.5, is_high_priority: false },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toBeInTheDocument();
    });

    it('handles very long threat names gracefully', () => {
      const threats: ThreatData[] = [
        {
          class_name: 'very_long_weapon_class_name_that_could_overflow',
          confidence: 0.75,
          is_high_priority: false,
        },
      ];
      render(<ThreatIndicator threats={threats} />);
      const badge = screen.getByTestId('threat-badge-0');
      expect(badge).toHaveClass('truncate');
    });

    it('handles single threat in compact mode without showing count', () => {
      const threats: ThreatData[] = [
        { class_name: 'gun', confidence: 0.87, is_high_priority: true },
      ];
      render(<ThreatIndicator threats={threats} compact />);
      expect(screen.queryByText(/\+\d+/)).not.toBeInTheDocument();
    });
  });
});
