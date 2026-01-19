/**
 * Tests for SummaryBulletList Component
 *
 * @see NEM-2923
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SummaryBulletList } from './SummaryBulletList';

import type { SummaryBulletPoint } from '@/types/summary';


describe('SummaryBulletList', () => {
  const mockBullets: SummaryBulletPoint[] = [
    { icon: 'alert', text: 'Critical event detected', severity: 85 },
    { icon: 'location', text: 'Front door camera' },
    { icon: 'time', text: '2:15 PM - 3:00 PM' },
    { icon: 'pattern', text: 'Person detected', severity: 40 },
    { icon: 'weather', text: 'Clear conditions' },
  ];

  describe('rendering', () => {
    it('renders a list with correct role', () => {
      render(<SummaryBulletList bullets={mockBullets} />);
      const list = screen.getByRole('list', { name: /summary bullet points/i });
      expect(list).toBeInTheDocument();
    });

    it('renders the correct number of bullet items', () => {
      render(<SummaryBulletList bullets={mockBullets} maxItems={4} />);
      const items = screen.getAllByTestId(/summary-bullet-item-/);
      expect(items).toHaveLength(4);
    });

    it('renders bullet text correctly', () => {
      render(<SummaryBulletList bullets={mockBullets} />);
      expect(screen.getByText('Critical event detected')).toBeInTheDocument();
      expect(screen.getByText('Front door camera')).toBeInTheDocument();
      expect(screen.getByText('2:15 PM - 3:00 PM')).toBeInTheDocument();
    });

    it('renders with custom testIdPrefix', () => {
      render(<SummaryBulletList bullets={mockBullets} testIdPrefix="custom-bullet" />);
      expect(screen.getByTestId('custom-bullet-list')).toBeInTheDocument();
      expect(screen.getByTestId('custom-bullet-item-0')).toBeInTheDocument();
    });
  });

  describe('icons', () => {
    it('renders alert icon for alert type', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'alert', text: 'Alert text' }];
      const { container } = render(<SummaryBulletList bullets={bullets} />);
      // lucide-react uses 'lucide-triangle-alert' class name
      const icon = container.querySelector('svg.lucide-triangle-alert');
      expect(icon).toBeInTheDocument();
    });

    it('renders map-pin icon for location type', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'location', text: 'Location text' }];
      const { container } = render(<SummaryBulletList bullets={bullets} />);
      const icon = container.querySelector('svg.lucide-map-pin');
      expect(icon).toBeInTheDocument();
    });

    it('renders eye icon for pattern type', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'pattern', text: 'Pattern text' }];
      const { container } = render(<SummaryBulletList bullets={bullets} />);
      const icon = container.querySelector('svg.lucide-eye');
      expect(icon).toBeInTheDocument();
    });

    it('renders clock icon for time type', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'time', text: 'Time text' }];
      const { container } = render(<SummaryBulletList bullets={bullets} />);
      const icon = container.querySelector('svg.lucide-clock');
      expect(icon).toBeInTheDocument();
    });

    it('renders cloud icon for weather type', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'weather', text: 'Weather text' }];
      const { container } = render(<SummaryBulletList bullets={bullets} />);
      const icon = container.querySelector('svg.lucide-cloud');
      expect(icon).toBeInTheDocument();
    });

    it('icons have aria-hidden attribute', () => {
      const { container } = render(<SummaryBulletList bullets={mockBullets} />);
      const icons = container.querySelectorAll('svg');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });
  });

  describe('maxItems', () => {
    it('limits displayed items to maxItems value', () => {
      render(<SummaryBulletList bullets={mockBullets} maxItems={2} />);
      const items = screen.getAllByTestId(/summary-bullet-item-/);
      expect(items).toHaveLength(2);
    });

    it('shows overflow indicator when there are more items than maxItems', () => {
      render(<SummaryBulletList bullets={mockBullets} maxItems={3} />);
      expect(screen.getByText('+2 more')).toBeInTheDocument();
    });

    it('does not show overflow indicator when items fit within maxItems', () => {
      render(<SummaryBulletList bullets={mockBullets.slice(0, 2)} maxItems={4} />);
      expect(screen.queryByTestId('summary-bullet-overflow')).not.toBeInTheDocument();
    });

    it('defaults to maxItems of 4', () => {
      render(<SummaryBulletList bullets={mockBullets} />);
      const items = screen.getAllByTestId(/summary-bullet-item-/);
      expect(items).toHaveLength(4);
      expect(screen.getByText('+1 more')).toBeInTheDocument();
    });
  });

  describe('severity styling', () => {
    it('applies critical styling for severity >= 80', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'alert', text: 'Critical', severity: 85 }];
      render(<SummaryBulletList bullets={bullets} />);
      const item = screen.getByTestId('summary-bullet-item-0');
      expect(item).toHaveAttribute('data-severity', '85');
      const text = screen.getByText('Critical');
      expect(text).toHaveClass('text-red-400');
    });

    it('applies high styling for severity >= 60 and < 80', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'alert', text: 'High', severity: 65 }];
      render(<SummaryBulletList bullets={bullets} />);
      const text = screen.getByText('High');
      expect(text).toHaveClass('text-orange-400');
    });

    it('applies medium styling for severity >= 40 and < 60', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'alert', text: 'Medium', severity: 45 }];
      render(<SummaryBulletList bullets={bullets} />);
      const text = screen.getByText('Medium');
      expect(text).toHaveClass('text-yellow-400');
    });

    it('applies low styling for severity >= 20 and < 40', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'alert', text: 'Low', severity: 25 }];
      render(<SummaryBulletList bullets={bullets} />);
      const text = screen.getByText('Low');
      expect(text).toHaveClass('text-green-400');
    });

    it('applies clear styling for severity < 20', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'alert', text: 'Clear', severity: 10 }];
      render(<SummaryBulletList bullets={bullets} />);
      const text = screen.getByText('Clear');
      expect(text).toHaveClass('text-emerald-400');
    });

    it('applies default styling when severity is undefined', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'location', text: 'No severity' }];
      render(<SummaryBulletList bullets={bullets} />);
      const text = screen.getByText('No severity');
      expect(text).toHaveClass('text-gray-300');
    });
  });

  describe('edge cases', () => {
    it('renders empty list when bullets array is empty', () => {
      render(<SummaryBulletList bullets={[]} />);
      const list = screen.getByRole('list');
      expect(list).toBeInTheDocument();
      expect(screen.queryByTestId('summary-bullet-item-0')).not.toBeInTheDocument();
    });

    it('handles single bullet correctly', () => {
      const bullets: SummaryBulletPoint[] = [{ icon: 'alert', text: 'Single item' }];
      render(<SummaryBulletList bullets={bullets} />);
      expect(screen.getByText('Single item')).toBeInTheDocument();
      expect(screen.queryByTestId('summary-bullet-overflow')).not.toBeInTheDocument();
    });

    it('handles long text content', () => {
      const longText = 'This is a very long bullet point text that should wrap properly within the container without breaking the layout or causing any visual issues.';
      const bullets: SummaryBulletPoint[] = [{ icon: 'pattern', text: longText }];
      render(<SummaryBulletList bullets={bullets} />);
      expect(screen.getByText(longText)).toBeInTheDocument();
    });
  });
});
