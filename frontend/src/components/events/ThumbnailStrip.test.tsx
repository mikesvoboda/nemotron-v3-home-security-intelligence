import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ThumbnailStrip, { type DetectionThumbnail } from './ThumbnailStrip';

describe('ThumbnailStrip', () => {
  const mockDetections: DetectionThumbnail[] = [
    {
      id: 1,
      detected_at: '2024-01-15T10:30:00Z',
      thumbnail_url: 'https://example.com/thumb1.jpg',
      object_type: 'person',
      confidence: 0.95,
    },
    {
      id: 2,
      detected_at: '2024-01-15T10:30:02Z',
      thumbnail_url: 'https://example.com/thumb2.jpg',
      object_type: 'car',
      confidence: 0.87,
    },
    {
      id: 3,
      detected_at: '2024-01-15T10:30:05Z',
      thumbnail_url: 'https://example.com/thumb3.jpg',
      object_type: 'package',
      confidence: 0.92,
    },
  ];

  describe('rendering', () => {
    it('renders nothing when detections array is empty', () => {
      const { container } = render(<ThumbnailStrip detections={[]} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders loading state with skeleton thumbnails', () => {
      render(<ThumbnailStrip detections={[]} loading={true} />);
      expect(screen.getByText('Detection Sequence')).toBeInTheDocument();
    });

    it('renders detection sequence title with count', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      expect(screen.getByText('Detection Sequence (3)')).toBeInTheDocument();
    });

    it('renders all detection thumbnails', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      const images = screen.getAllByRole('img');
      expect(images).toHaveLength(3);
    });

    it('renders thumbnails with correct image sources', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      const images = screen.getAllByRole('img');
      expect(images[0]).toHaveAttribute('src', 'https://example.com/thumb1.jpg');
      expect(images[1]).toHaveAttribute('src', 'https://example.com/thumb2.jpg');
      expect(images[2]).toHaveAttribute('src', 'https://example.com/thumb3.jpg');
    });

    it('renders sequence numbers on thumbnails', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      expect(screen.getByText('#1')).toBeInTheDocument();
      expect(screen.getByText('#2')).toBeInTheDocument();
      expect(screen.getByText('#3')).toBeInTheDocument();
    });

    it('renders object types', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      expect(screen.getByText(/person/)).toBeInTheDocument();
      expect(screen.getByText(/car/)).toBeInTheDocument();
      expect(screen.getByText(/package/)).toBeInTheDocument();
    });

    it('renders confidence scores as percentages', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      expect(screen.getByText(/95%/)).toBeInTheDocument();
      expect(screen.getByText(/87%/)).toBeInTheDocument();
      expect(screen.getByText(/92%/)).toBeInTheDocument();
    });

    it('renders timestamps in HH:MM:SS format', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      // Each detection should have a timestamp displayed
      const timestamps = screen.getAllByText(/\d{2}:\d{2}:\d{2}/);
      expect(timestamps.length).toBeGreaterThanOrEqual(3);
    });

    it('renders relative time from first detection', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      // First detection should be 00:00
      expect(screen.getByText('00:00')).toBeInTheDocument();
      // Second detection should be 00:02 (2 seconds later)
      expect(screen.getByText('00:02')).toBeInTheDocument();
      // Third detection should be 00:05 (5 seconds later)
      expect(screen.getByText('00:05')).toBeInTheDocument();
    });
  });

  describe('selection', () => {
    it('highlights selected detection with visual indicator', () => {
      render(<ThumbnailStrip detections={mockDetections} selectedDetectionId={2} />);
      const buttons = screen.getAllByRole('button');
      // The second button (index 1) should have the selected class
      expect(buttons[1].className).toContain('ring-[#76B900]');
    });

    it('does not highlight any detection when selectedDetectionId is undefined', () => {
      render(<ThumbnailStrip detections={mockDetections} selectedDetectionId={undefined} />);
      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button.className).not.toContain('ring-[#76B900]');
      });
    });

    it('highlights only the selected detection', () => {
      render(<ThumbnailStrip detections={mockDetections} selectedDetectionId={1} />);
      const buttons = screen.getAllByRole('button');
      // First button should be selected
      expect(buttons[0].className).toContain('ring-[#76B900]');
      // Others should not be selected
      expect(buttons[1].className).not.toContain('ring-[#76B900]');
      expect(buttons[2].className).not.toContain('ring-[#76B900]');
    });
  });

  describe('interactions', () => {
    it('calls onThumbnailClick when thumbnail is clicked', async () => {
      const user = userEvent.setup();
      const onThumbnailClick = vi.fn();
      render(<ThumbnailStrip detections={mockDetections} onThumbnailClick={onThumbnailClick} />);

      const buttons = screen.getAllByRole('button');
      await user.click(buttons[0]);

      expect(onThumbnailClick).toHaveBeenCalledWith(1);
      expect(onThumbnailClick).toHaveBeenCalledTimes(1);
    });

    it('calls onThumbnailClick with correct detection ID for each thumbnail', async () => {
      const user = userEvent.setup();
      const onThumbnailClick = vi.fn();
      render(<ThumbnailStrip detections={mockDetections} onThumbnailClick={onThumbnailClick} />);

      const buttons = screen.getAllByRole('button');

      await user.click(buttons[0]);
      expect(onThumbnailClick).toHaveBeenCalledWith(1);

      await user.click(buttons[1]);
      expect(onThumbnailClick).toHaveBeenCalledWith(2);

      await user.click(buttons[2]);
      expect(onThumbnailClick).toHaveBeenCalledWith(3);

      expect(onThumbnailClick).toHaveBeenCalledTimes(3);
    });

    it('does not throw error when onThumbnailClick is undefined', async () => {
      const user = userEvent.setup();
      render(<ThumbnailStrip detections={mockDetections} />);

      const buttons = screen.getAllByRole('button');
      await user.click(buttons[0]);

      // Should not throw error
      expect(buttons[0]).toBeInTheDocument();
    });

    it('allows clicking multiple times on same thumbnail', async () => {
      const user = userEvent.setup();
      const onThumbnailClick = vi.fn();
      render(<ThumbnailStrip detections={mockDetections} onThumbnailClick={onThumbnailClick} />);

      const buttons = screen.getAllByRole('button');

      await user.click(buttons[0]);
      await user.click(buttons[0]);
      await user.click(buttons[0]);

      expect(onThumbnailClick).toHaveBeenCalledTimes(3);
      expect(onThumbnailClick).toHaveBeenCalledWith(1);
    });
  });

  describe('accessibility', () => {
    it('renders thumbnails as buttons', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      const buttons = screen.getAllByRole('button');
      expect(buttons).toHaveLength(3);
    });

    it('provides aria-label for each thumbnail button', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      expect(screen.getByLabelText(/View detection 1 at/)).toBeInTheDocument();
      expect(screen.getByLabelText(/View detection 2 at/)).toBeInTheDocument();
      expect(screen.getByLabelText(/View detection 3 at/)).toBeInTheDocument();
    });

    it('provides descriptive alt text for images', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      const images = screen.getAllByRole('img');
      expect(images[0]).toHaveAttribute('alt', 'Detection 1: person');
      expect(images[1]).toHaveAttribute('alt', 'Detection 2: car');
      expect(images[2]).toHaveAttribute('alt', 'Detection 3: package');
    });

    it('uses lazy loading for images', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      const images = screen.getAllByRole('img');
      images.forEach((img) => {
        expect(img).toHaveAttribute('loading', 'lazy');
      });
    });

    it('buttons have type="button" to prevent form submission', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      const buttons = screen.getAllByRole('button');
      buttons.forEach((button) => {
        expect(button).toHaveAttribute('type', 'button');
      });
    });
  });

  describe('edge cases', () => {
    it('handles single detection', () => {
      render(<ThumbnailStrip detections={[mockDetections[0]]} />);
      expect(screen.getByText('Detection Sequence (1)')).toBeInTheDocument();
      expect(screen.getAllByRole('button')).toHaveLength(1);
    });

    it('handles many detections', () => {
      const manyDetections = Array.from({ length: 20 }, (_, i) => ({
        id: i + 1,
        detected_at: `2024-01-15T10:30:${i.toString().padStart(2, '0')}Z`,
        thumbnail_url: `https://example.com/thumb${i + 1}.jpg`,
        object_type: `object-${i + 1}`,
        confidence: 0.5 + i * 0.02,
      }));

      render(<ThumbnailStrip detections={manyDetections} />);
      expect(screen.getByText('Detection Sequence (20)')).toBeInTheDocument();
      expect(screen.getAllByRole('button')).toHaveLength(20);
    });

    it('handles detection without object_type', () => {
      const detectionsNoType: DetectionThumbnail[] = [
        {
          id: 1,
          detected_at: '2024-01-15T10:30:00Z',
          thumbnail_url: 'https://example.com/thumb1.jpg',
        },
      ];

      render(<ThumbnailStrip detections={detectionsNoType} />);
      const img = screen.getByRole('img');
      expect(img).toHaveAttribute('alt', 'Detection 1: object');
    });

    it('handles detection without confidence', () => {
      const detectionsNoConfidence: DetectionThumbnail[] = [
        {
          id: 1,
          detected_at: '2024-01-15T10:30:00Z',
          thumbnail_url: 'https://example.com/thumb1.jpg',
          object_type: 'person',
        },
      ];

      render(<ThumbnailStrip detections={detectionsNoConfidence} />);
      expect(screen.getByText('person')).toBeInTheDocument();
      // Confidence percentage should not be rendered
      expect(screen.queryByText(/\d+%/)).not.toBeInTheDocument();
    });

    it('handles invalid timestamp gracefully', () => {
      const detectionsInvalidTime: DetectionThumbnail[] = [
        {
          id: 1,
          detected_at: 'invalid-date',
          thumbnail_url: 'https://example.com/thumb1.jpg',
          object_type: 'person',
        },
      ];

      render(<ThumbnailStrip detections={detectionsInvalidTime} />);
      // Should render fallback time (NaN:NaN for relative, Invalid Date for timestamp)
      expect(screen.getByText('NaN:NaN')).toBeInTheDocument();
      expect(screen.getByText('Invalid Date')).toBeInTheDocument();
    });

    it('handles 100% confidence correctly', () => {
      const detectionsPerfectConfidence: DetectionThumbnail[] = [
        {
          id: 1,
          detected_at: '2024-01-15T10:30:00Z',
          thumbnail_url: 'https://example.com/thumb1.jpg',
          object_type: 'person',
          confidence: 1.0,
        },
      ];

      render(<ThumbnailStrip detections={detectionsPerfectConfidence} />);
      expect(screen.getByText(/100%/)).toBeInTheDocument();
    });

    it('handles 0% confidence correctly', () => {
      const detectionsZeroConfidence: DetectionThumbnail[] = [
        {
          id: 1,
          detected_at: '2024-01-15T10:30:00Z',
          thumbnail_url: 'https://example.com/thumb1.jpg',
          object_type: 'person',
          confidence: 0.0,
        },
      ];

      render(<ThumbnailStrip detections={detectionsZeroConfidence} />);
      expect(screen.getByText(/0%/)).toBeInTheDocument();
    });

    it('rounds confidence to nearest integer', () => {
      const detectionsRoundedConfidence: DetectionThumbnail[] = [
        {
          id: 1,
          detected_at: '2024-01-15T10:30:00Z',
          thumbnail_url: 'https://example.com/thumb1.jpg',
          object_type: 'person',
          confidence: 0.956,
        },
      ];

      render(<ThumbnailStrip detections={detectionsRoundedConfidence} />);
      expect(screen.getByText(/96%/)).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('renders with dark theme colors', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      const container = screen.getByText('Detection Sequence (3)').parentElement;
      expect(container?.className).toContain('bg-black/20');
      expect(container?.className).toContain('border-gray-800');
    });

    it('applies NVIDIA green highlight to selected thumbnail', () => {
      render(<ThumbnailStrip detections={mockDetections} selectedDetectionId={1} />);
      const buttons = screen.getAllByRole('button');
      expect(buttons[0].className).toContain('ring-[#76B900]');
      expect(buttons[0].className).toContain('bg-[#76B900]/20');
    });

    it('makes thumbnails horizontally scrollable', () => {
      render(<ThumbnailStrip detections={mockDetections} />);
      const scrollContainer = screen.getByText('Detection Sequence (3)').nextElementSibling;
      expect(scrollContainer?.className).toContain('overflow-x-auto');
    });
  });

  describe('loading state', () => {
    it('renders loading skeleton with correct structure', () => {
      render(<ThumbnailStrip detections={[]} loading={true} />);
      expect(screen.getByText('Detection Sequence')).toBeInTheDocument();
      // Should render 3 skeleton items
      const skeletons = document.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('does not render actual thumbnails when loading', () => {
      render(<ThumbnailStrip detections={mockDetections} loading={true} />);
      // Should not render actual detection images
      const images = screen.queryAllByRole('img');
      expect(images).toHaveLength(0);
    });

    it('shows loading state even with detections provided', () => {
      render(<ThumbnailStrip detections={mockDetections} loading={true} />);
      expect(screen.getByText('Detection Sequence')).toBeInTheDocument();
      expect(screen.queryByText('Detection Sequence (3)')).not.toBeInTheDocument();
    });
  });
});
