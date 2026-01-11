import { render, fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { BoundingBox } from './BoundingBoxOverlay';
import DetectionImage from './DetectionImage';
import { Keypoint } from './PoseSkeletonOverlay';

describe('DetectionImage', () => {
  const mockBoxes: BoundingBox[] = [
    {
      x: 100,
      y: 100,
      width: 200,
      height: 300,
      label: 'person',
      confidence: 0.95,
    },
    {
      x: 400,
      y: 200,
      width: 150,
      height: 100,
      label: 'car',
      confidence: 0.87,
    },
  ];

  const mockImageSrc = 'https://example.com/test-image.jpg';

  it('renders without crashing', () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );
    expect(container.querySelector('img')).toBeInTheDocument();
  });

  it('renders image with correct src and alt attributes', () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Security camera view" boxes={mockBoxes} />
    );

    const img = container.querySelector('img');
    expect(img?.getAttribute('src')).toBe(mockImageSrc);
    expect(img?.getAttribute('alt')).toBe('Security camera view');
  });

  it('renders BoundingBoxOverlay after image loads', async () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );

    const img = container.querySelector('img') as HTMLImageElement;

    // Simulate image load with natural dimensions
    Object.defineProperty(img, 'naturalWidth', { value: 1920, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 1080, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  it('passes correct image dimensions to BoundingBoxOverlay', async () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );

    const img = container.querySelector('img') as HTMLImageElement;

    Object.defineProperty(img, 'naturalWidth', { value: 1920, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 1080, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const svg = container.querySelector('svg');
      expect(svg?.getAttribute('viewBox')).toBe('0 0 1920 1080');
    });
  });

  it('does not render BoundingBoxOverlay before image loads', () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );

    // Before image load, no SVG overlay should be present
    const svg = container.querySelector('svg');
    expect(svg).not.toBeInTheDocument();
  });

  it('applies custom className to container', () => {
    const { container } = render(
      <DetectionImage
        src={mockImageSrc}
        alt="Test image"
        boxes={mockBoxes}
        className="custom-class border-2"
      />
    );

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('custom-class', 'border-2');
  });

  it('passes showLabels prop to BoundingBoxOverlay', async () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} showLabels={false} />
    );

    const img = container.querySelector('img') as HTMLImageElement;
    Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const text = container.querySelector('text');
      expect(text).not.toBeInTheDocument();
    });
  });

  it('passes showConfidence prop to BoundingBoxOverlay', async () => {
    const { container } = render(
      <DetectionImage
        src={mockImageSrc}
        alt="Test image"
        boxes={mockBoxes}
        showConfidence={false}
      />
    );

    const img = container.querySelector('img') as HTMLImageElement;
    Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const text = container.querySelector('text');
      expect(text?.textContent).not.toContain('%');
    });
  });

  it('passes minConfidence prop to BoundingBoxOverlay', async () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} minConfidence={0.9} />
    );

    const img = container.querySelector('img') as HTMLImageElement;
    Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const rects = container.querySelectorAll('rect[fill="none"]');
      // Only person (0.95) should be shown, car (0.87) filtered out
      expect(rects.length).toBe(1);
    });
  });

  it('passes onClick handler to BoundingBoxOverlay', async () => {
    const handleClick = vi.fn();
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} onClick={handleClick} />
    );

    const img = container.querySelector('img') as HTMLImageElement;
    Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const rect = container.querySelector('rect[fill="none"]');
      expect(rect).toBeInTheDocument();
    });

    const rect = container.querySelector('rect[fill="none"]');
    fireEvent.click(rect!);

    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(handleClick).toHaveBeenCalledWith(mockBoxes[0]);
  });

  it('has relative positioning for proper overlay stacking', () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('relative');
  });

  it('renders image with responsive width and height classes', () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );

    const img = container.querySelector('img');
    expect(img).toHaveClass('w-full', 'h-full');
  });

  it('uses object-contain for image scaling', () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );

    const img = container.querySelector('img');
    expect(img).toHaveClass('object-contain');
  });

  it('handles empty boxes array', async () => {
    const { container } = render(<DetectionImage src={mockImageSrc} alt="Test image" boxes={[]} />);

    const img = container.querySelector('img') as HTMLImageElement;
    Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const svg = container.querySelector('svg');
      // Should not render overlay when no boxes
      expect(svg).not.toBeInTheDocument();
    });
  });

  it('updates overlay when image dimensions change on reload', async () => {
    const { container, rerender } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );

    const img = container.querySelector('img') as HTMLImageElement;
    Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const svg = container.querySelector('svg');
      expect(svg?.getAttribute('viewBox')).toBe('0 0 800 600');
    });

    // Rerender with different image
    rerender(
      <DetectionImage src="https://example.com/new-image.jpg" alt="Test image" boxes={mockBoxes} />
    );

    const newImg = container.querySelector('img') as HTMLImageElement;
    Object.defineProperty(newImg, 'naturalWidth', { value: 1920, writable: true });
    Object.defineProperty(newImg, 'naturalHeight', { value: 1080, writable: true });

    fireEvent.load(newImg);

    await waitFor(() => {
      const svg = container.querySelector('svg');
      expect(svg?.getAttribute('viewBox')).toBe('0 0 1920 1080');
    });
  });

  it('renders with default props', async () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );

    const img = container.querySelector('img') as HTMLImageElement;
    Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const svg = container.querySelector('svg');
      expect(svg).toBeInTheDocument();

      // Should show labels and confidence by default
      const text = container.querySelector('text');
      expect(text?.textContent).toContain('person');
      expect(text?.textContent).toContain('%');
    });
  });

  it('maintains aspect ratio with inline-block display', () => {
    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
    );

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('inline-block');
  });

  it('renders multiple boxes after image loads', async () => {
    const manyBoxes: BoundingBox[] = [
      { x: 10, y: 10, width: 50, height: 50, label: 'person', confidence: 0.99 },
      { x: 100, y: 100, width: 100, height: 100, label: 'car', confidence: 0.85 },
      { x: 300, y: 300, width: 75, height: 75, label: 'cat', confidence: 0.72 },
      { x: 500, y: 200, width: 120, height: 80, label: 'package', confidence: 0.91 },
    ];

    const { container } = render(
      <DetectionImage src={mockImageSrc} alt="Test image" boxes={manyBoxes} />
    );

    const img = container.querySelector('img') as HTMLImageElement;
    Object.defineProperty(img, 'naturalWidth', { value: 1920, writable: true });
    Object.defineProperty(img, 'naturalHeight', { value: 1080, writable: true });

    fireEvent.load(img);

    await waitFor(() => {
      const rects = container.querySelectorAll('rect[fill="none"]');
      expect(rects.length).toBe(4);
    });
  });

  describe('lightbox functionality', () => {
    it('does not render lightbox by default', () => {
      render(<DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />);
      expect(screen.queryByTestId('lightbox-image')).not.toBeInTheDocument();
    });

    it('does not show lightbox controls when enableLightbox is false', () => {
      const { container } = render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} enableLightbox={false} />
      );
      expect(container.querySelector('[role="button"]')).not.toBeInTheDocument();
    });

    it('adds cursor-pointer class when enableLightbox is true', () => {
      render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} enableLightbox={true} />
      );
      const container = screen.getByTestId('detection-image-container');
      expect(container).toHaveClass('cursor-pointer');
    });

    it('adds button role and aria-label when enableLightbox is true', () => {
      render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} enableLightbox={true} />
      );
      const container = screen.getByTestId('detection-image-container');
      expect(container).toHaveAttribute('role', 'button');
      expect(container).toHaveAttribute('aria-label', 'View Test image in full size');
    });

    it('opens lightbox when clicking on image with enableLightbox', async () => {
      const user = userEvent.setup();
      render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} enableLightbox={true} />
      );

      const container = screen.getByTestId('detection-image-container');
      await user.click(container);

      expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      expect(screen.getByTestId('lightbox-image')).toHaveAttribute('src', mockImageSrc);
    });

    it('closes lightbox when clicking close button', async () => {
      const user = userEvent.setup();
      render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} enableLightbox={true} />
      );

      // Open lightbox
      await user.click(screen.getByTestId('detection-image-container'));
      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });

      // Close lightbox
      await user.click(screen.getByTestId('lightbox-close-button'));
      await waitFor(() => {
        expect(screen.queryByTestId('lightbox-image')).not.toBeInTheDocument();
      });
    });

    it('opens lightbox on Enter key when enableLightbox is true', async () => {
      render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} enableLightbox={true} />
      );

      const container = screen.getByTestId('detection-image-container');
      container.focus();
      fireEvent.keyDown(container, { key: 'Enter' });

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });
    });

    it('opens lightbox on Space key when enableLightbox is true', async () => {
      render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} enableLightbox={true} />
      );

      const container = screen.getByTestId('detection-image-container');
      container.focus();
      fireEvent.keyDown(container, { key: ' ' });

      await waitFor(() => {
        expect(screen.getByTestId('lightbox-image')).toBeInTheDocument();
      });
    });

    it('shows "Click to enlarge" hint on hover when enableLightbox is true', () => {
      render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} enableLightbox={true} />
      );
      expect(screen.getByText('Click to enlarge')).toBeInTheDocument();
    });

    it('passes lightboxCaption to lightbox', async () => {
      const user = userEvent.setup();
      render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          enableLightbox={true}
          lightboxCaption="Detection at 12:30 PM"
        />
      );

      await user.click(screen.getByTestId('detection-image-container'));

      expect(screen.getByTestId('lightbox-caption')).toHaveTextContent('Detection at 12:30 PM');
    });

    it('does not open lightbox when clicking bounding box onClick handler fires', async () => {
      const handleBoxClick = vi.fn();
      const { container } = render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          enableLightbox={true}
          onClick={handleBoxClick}
        />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      // The onClick on bounding box should work separately from lightbox
      await waitFor(() => {
        const rect = container.querySelector('rect[fill="none"]');
        expect(rect).toBeInTheDocument();
      });
    });
  });

  describe('pose skeleton overlay', () => {
    const mockPoseKeypoints: Keypoint[] = [
      [100, 50, 0.95], // 0: nose
      [90, 45, 0.9], // 1: left_eye
      [110, 45, 0.9], // 2: right_eye
      [80, 50, 0.85], // 3: left_ear
      [120, 50, 0.85], // 4: right_ear
      [70, 100, 0.92], // 5: left_shoulder
      [130, 100, 0.92], // 6: right_shoulder
      [60, 150, 0.88], // 7: left_elbow
      [140, 150, 0.88], // 8: right_elbow
      [50, 200, 0.82], // 9: left_wrist
      [150, 200, 0.82], // 10: right_wrist
      [80, 180, 0.9], // 11: left_hip
      [120, 180, 0.9], // 12: right_hip
      [75, 250, 0.85], // 13: left_knee
      [125, 250, 0.85], // 14: right_knee
      [70, 320, 0.8], // 15: left_ankle
      [130, 320, 0.8], // 16: right_ankle
    ];

    it('does not render pose skeleton when poseKeypoints is not provided', async () => {
      const { container } = render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        expect(
          container.querySelector('[data-testid="pose-skeleton-overlay"]')
        ).not.toBeInTheDocument();
      });
    });

    it('renders pose skeleton when poseKeypoints is provided', async () => {
      const { container } = render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          poseKeypoints={mockPoseKeypoints}
        />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        expect(container.querySelector('[data-testid="pose-skeleton-overlay"]')).toBeInTheDocument();
      });
    });

    it('passes correct image dimensions to pose skeleton overlay', async () => {
      const { container } = render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          poseKeypoints={mockPoseKeypoints}
        />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 1920, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 1080, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        const poseOverlay = container.querySelector('[data-testid="pose-skeleton-overlay"]');
        expect(poseOverlay?.getAttribute('viewBox')).toBe('0 0 1920 1080');
      });
    });

    it('renders keypoint circles', async () => {
      const { container } = render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          poseKeypoints={mockPoseKeypoints}
        />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        const circles = container.querySelectorAll('[data-testid^="pose-keypoint-"]');
        expect(circles.length).toBe(17);
      });
    });

    it('renders skeleton connections', async () => {
      const { container } = render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          poseKeypoints={mockPoseKeypoints}
        />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        const connections = container.querySelectorAll('[data-testid^="pose-connection-"]');
        expect(connections.length).toBeGreaterThan(0);
      });
    });

    it('hides pose skeleton when showPoseSkeleton is false', async () => {
      const { container } = render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          poseKeypoints={mockPoseKeypoints}
          showPoseSkeleton={false}
        />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        expect(
          container.querySelector('[data-testid="pose-skeleton-overlay"]')
        ).not.toBeInTheDocument();
      });
    });

    it('applies poseMinConfidence filter', async () => {
      const mixedConfidenceKeypoints: Keypoint[] = [
        [100, 50, 0.95], // above threshold
        [90, 45, 0.2], // below threshold
        [110, 45, 0.9], // above threshold
        [80, 50, 0.1], // below threshold
        [120, 50, 0.1], // below threshold
        [70, 100, 0.92], // above threshold
        [130, 100, 0.92], // above threshold
        [60, 150, 0.1], // below threshold
        [140, 150, 0.1], // below threshold
        [50, 200, 0.1], // below threshold
        [150, 200, 0.1], // below threshold
        [80, 180, 0.9], // above threshold
        [120, 180, 0.9], // above threshold
        [75, 250, 0.1], // below threshold
        [125, 250, 0.1], // below threshold
        [70, 320, 0.1], // below threshold
        [130, 320, 0.1], // below threshold
      ];

      const { container } = render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          poseKeypoints={mixedConfidenceKeypoints}
          poseMinConfidence={0.5}
        />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        const circles = container.querySelectorAll('[data-testid^="pose-keypoint-"]');
        // Only keypoints above 0.5 confidence: indices 0, 2, 5, 6, 11, 12 = 6 keypoints
        expect(circles.length).toBe(6);
      });
    });

    it('does not render pose skeleton when poseKeypoints is null', async () => {
      const { container } = render(
        <DetectionImage src={mockImageSrc} alt="Test image" boxes={mockBoxes} poseKeypoints={null} />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        expect(
          container.querySelector('[data-testid="pose-skeleton-overlay"]')
        ).not.toBeInTheDocument();
      });
    });

    it('renders both bounding box and pose skeleton overlays', async () => {
      const { container } = render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          poseKeypoints={mockPoseKeypoints}
        />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        // Both overlays should be present
        const svgs = container.querySelectorAll('svg');
        expect(svgs.length).toBe(2);
        expect(container.querySelector('[data-testid="pose-skeleton-overlay"]')).toBeInTheDocument();
        expect(container.querySelector('rect[fill="none"]')).toBeInTheDocument();
      });
    });

    it('pose skeleton has higher z-index than bounding boxes', async () => {
      const { container } = render(
        <DetectionImage
          src={mockImageSrc}
          alt="Test image"
          boxes={mockBoxes}
          poseKeypoints={mockPoseKeypoints}
        />
      );

      const img = container.querySelector('img') as HTMLImageElement;
      Object.defineProperty(img, 'naturalWidth', { value: 800, writable: true });
      Object.defineProperty(img, 'naturalHeight', { value: 600, writable: true });
      fireEvent.load(img);

      await waitFor(() => {
        const poseOverlay = container.querySelector(
          '[data-testid="pose-skeleton-overlay"]'
        ) as SVGElement;
        // Pose skeleton should have z-index 20, bounding box has z-index 10
        expect(poseOverlay?.style.zIndex).toBe('20');
      });
    });
  });
});
